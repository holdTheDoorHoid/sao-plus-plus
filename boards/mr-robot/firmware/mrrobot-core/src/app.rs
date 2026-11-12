//! The whole behaviour of the board as one state machine, independent of the
//! hardware. The firmware calls [`App::tick`] every couple of milliseconds
//! and [`App::on_i2c_write`] whenever the badge writes to the board, and
//! passes the note it gets back to [`crate::tone::ToneGen`].
//!
//! Same structure and the same decisions as the Hack-Man and Mysterio
//! firmware, adapted to sound:
//! * Power-on plays a short two-note chirp (the board has no lights, so this
//!   is how it says it is alive). Button presses during the chirp are
//!   ignored; a valid badge command ends it at once.
//! * A mode-button press always means "next mode", and also takes control
//!   back from the badge (silencing whatever the badge was playing).
//! * The badge takes control with any valid command. It keeps control while
//!   it keeps sending, **and while a note it asked for is still sounding**:
//!   the maker's protocol holds a note until the next command, so a held note
//!   never times out. Once the badge's sound has stopped and nothing valid
//!   has arrived for 5 s, the board goes back to its own mode.
//! * The mode is not remembered across "off" (the off position resets the
//!   chip on wake), so every power-on starts in mode 0.

use crate::i2c::{Command, parse_write};
use crate::input::Debounced;
use crate::notes::Note;
use crate::tune::{BOOT_CHIRP, DEFAULT_BPM, MODE_BEEP, Sequencer, TUNES, clamp_bpm};
use crate::{VERSION_MAJOR, VERSION_MINOR};

pub const BUTTON_DEBOUNCE_MS: u32 = 25;
pub const OFF_DEBOUNCE_MS: u32 = 30;

/// With nothing sounding and no valid command for this long, the badge
/// loses control and the board's own mode resumes.
pub const BADGE_TIMEOUT_MS: u32 = 5_000;

/// Jukebox: silence between tunes.
pub const JUKEBOX_PAUSE_MS: u32 = 2_000;

/// Scale mode (the maker's own badge demo, `MasterMrRobot.ino`): notes
/// 1..=69 rising, each on for 100 ms then off for 100 ms, then again.
pub const SCALE_TOP_NOTE: u8 = 69;
pub const SCALE_ON_MS: u32 = 100;
pub const SCALE_OFF_MS: u32 = 100;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Silent; waits for the badge. The default.
    Listen,
    /// Plays the built-in tunes one after another, with a pause, forever.
    Jukebox,
    /// The maker's demo: a rising scale of short beeps, forever.
    Scale,
}

impl Mode {
    pub const fn next(self) -> Mode {
        match self {
            Mode::Listen => Mode::Jukebox,
            Mode::Jukebox => Mode::Scale,
            Mode::Scale => Mode::Listen,
        }
    }
    pub const fn number(self) -> u8 {
        match self {
            Mode::Listen => 0,
            Mode::Jukebox => 1,
            Mode::Scale => 2,
        }
    }
}

/// Raw input levels, already converted to meaning (not electrical level).
#[derive(Clone, Copy, Debug, Default)]
pub struct Inputs {
    /// Mode button held down right now.
    pub button_down: bool,
    /// Power switch is in its middle "OFF" position right now.
    pub off_selected: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Output {
    /// Sound this note now, or be silent (pin low) for `None`.
    Sound(Option<Note>),
    /// The user selected OFF: silence and sleep until the switch leaves OFF.
    PowerOff,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    Booting,
    Mode(Mode),
    Badge,
}

pub struct App {
    booting: bool,
    mode: Mode,
    mode_start: u32,
    badge: bool,
    last_badge: u32,
    /// A note held by the maker's protocol (badge mode only).
    held: Option<Note>,
    /// Plays the boot chirp, the mode beep, jukebox tunes and badge tunes.
    /// Only one of those can be active at a time.
    seq: Sequencer,
    jukebox_next: usize,
    jukebox_waiting: bool,
    jukebox_idle_since: u32,
    bpm: u8,
    sounding: Option<Note>,
    button: Debounced,
    off: Debounced,
}

impl App {
    /// `off_selected` is the switch position read once at power-on, so a board
    /// switched on into OFF goes straight back to sleep without a chirp.
    pub fn new(now_ms: u32, off_selected: bool) -> Self {
        let mut seq = Sequencer::new();
        seq.start(BOOT_CHIRP, now_ms);
        Self {
            booting: true,
            mode: Mode::Listen,
            mode_start: now_ms,
            badge: false,
            last_badge: now_ms,
            held: None,
            seq,
            jukebox_next: 0,
            jukebox_waiting: false,
            jukebox_idle_since: now_ms,
            bpm: DEFAULT_BPM,
            sounding: None,
            button: Debounced::new(false, BUTTON_DEBOUNCE_MS),
            off: Debounced::new(off_selected, OFF_DEBOUNCE_MS),
        }
    }

    pub fn state(&self) -> State {
        if self.badge {
            State::Badge
        } else if self.booting {
            State::Booting
        } else {
            State::Mode(self.mode)
        }
    }

    pub fn bpm(&self) -> u8 {
        self.bpm
    }

    /// Handle one I2C write (any length). Returns the number of valid
    /// commands; invalid writes change nothing at all.
    pub fn on_i2c_write(&mut self, bytes: &[u8], now_ms: u32) -> usize {
        let valid = parse_write(bytes, |_| {});
        if valid == 0 {
            return 0;
        }
        if !self.badge {
            self.badge = true;
            self.booting = false;
            self.seq.stop();
            self.held = None;
        }
        self.last_badge = now_ms;
        parse_write(bytes, |c| self.apply(c, now_ms))
    }

    fn apply(&mut self, cmd: Command, now_ms: u32) {
        match cmd {
            Command::Silence | Command::Stop => {
                self.held = None;
                self.seq.stop();
            }
            Command::Hold(n) => {
                self.seq.stop();
                self.held = Some(n);
            }
            Command::PlayTune(i) => {
                self.held = None;
                if let Some(t) = TUNES.get(i as usize) {
                    self.seq.start(t.steps, now_ms);
                }
            }
            Command::Tempo(b) => self.bpm = clamp_bpm(b),
        }
    }

    /// Four status bytes for an I2C read: firmware major, minor, state, and
    /// the note sounding right now (0 = silent).
    ///
    /// State: 0x40 while booting; 0, 1, 2 = mode number (listen, jukebox,
    /// scale) when the board is in charge; 0x80 when the badge is in charge,
    /// plus 1 while a held note sounds or plus 2 while a tune plays.
    pub fn status(&self) -> [u8; 4] {
        let state = match self.state() {
            State::Booting => 0x40,
            State::Mode(m) => m.number(),
            State::Badge => {
                0x80 | if self.held.is_some() {
                    1
                } else if self.seq.is_playing() {
                    2
                } else {
                    0
                }
            }
        };
        let note = self.sounding.map_or(0, Note::number);
        [VERSION_MAJOR, VERSION_MINOR, state, note]
    }

    fn start_mode(&mut self, now_ms: u32, by_button: bool) {
        self.mode_start = now_ms;
        self.seq.stop();
        match self.mode {
            Mode::Listen => {
                if by_button {
                    self.seq.start(MODE_BEEP, now_ms);
                }
            }
            Mode::Jukebox => {
                if by_button {
                    self.jukebox_next = 0;
                }
                // Start the next tune straight away.
                self.jukebox_waiting = true;
                self.jukebox_idle_since = now_ms.wrapping_sub(JUKEBOX_PAUSE_MS);
            }
            Mode::Scale => {}
        }
    }

    pub fn tick(&mut self, now_ms: u32, inputs: Inputs) -> Output {
        self.off.update(inputs.off_selected, now_ms);
        if self.off.level() {
            self.sounding = None;
            return Output::PowerOff;
        }
        let sound = self.sound_at(now_ms, inputs);
        self.sounding = sound;
        Output::Sound(sound)
    }

    fn sound_at(&mut self, now_ms: u32, inputs: Inputs) -> Option<Note> {
        if self.button.update(inputs.button_down, now_ms) == Some(true) && !self.booting {
            self.badge = false;
            self.held = None;
            self.mode = self.mode.next();
            self.start_mode(now_ms, true);
        }

        if self.booting {
            let n = self.seq.update(now_ms, DEFAULT_BPM);
            if self.seq.is_playing() {
                return n;
            }
            self.booting = false;
            self.start_mode(now_ms, false);
        }

        if self.badge {
            let tune = self.seq.update(now_ms, self.bpm);
            let quiet = self.held.is_none() && !self.seq.is_playing();
            if quiet && now_ms.wrapping_sub(self.last_badge) >= BADGE_TIMEOUT_MS {
                self.badge = false;
                self.start_mode(now_ms, false);
            } else {
                return self.held.or(tune);
            }
        }

        match self.mode {
            Mode::Listen => self.seq.update(now_ms, DEFAULT_BPM),
            Mode::Jukebox => self.jukebox(now_ms),
            Mode::Scale => scale_note(now_ms.wrapping_sub(self.mode_start)),
        }
    }

    fn jukebox(&mut self, now_ms: u32) -> Option<Note> {
        if self.seq.is_playing() {
            let n = self.seq.update(now_ms, self.bpm);
            if self.seq.is_playing() {
                return n;
            }
            self.jukebox_waiting = true;
            self.jukebox_idle_since = now_ms;
            return None;
        }
        if self.jukebox_waiting && now_ms.wrapping_sub(self.jukebox_idle_since) >= JUKEBOX_PAUSE_MS
        {
            self.jukebox_waiting = false;
            self.seq.start(TUNES[self.jukebox_next].steps, now_ms);
            self.jukebox_next = (self.jukebox_next + 1) % TUNES.len();
            return self.seq.update(now_ms, self.bpm);
        }
        None
    }
}

/// The maker's demo scale at time `t` since the mode started.
pub fn scale_note(t: u32) -> Option<Note> {
    let step = SCALE_ON_MS + SCALE_OFF_MS;
    let i = (t / step) % SCALE_TOP_NOTE as u32;
    if t % step < SCALE_ON_MS {
        Note::new(i as u8 + 1)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::i2c::{EXT_END as E, EXT_START as S, OP_PLAY_TUNE, OP_STOP, OP_TEMPO};
    use crate::tone::{ToneGen, mock::MockPin, mock::Pin};
    use crate::tune::{MAX_BPM, MIN_BPM, tune_ms};

    const RUN: Inputs = Inputs {
        button_down: false,
        off_selected: false,
    };
    const PRESS: Inputs = Inputs {
        button_down: true,
        off_selected: false,
    };
    const OFF: Inputs = Inputs {
        button_down: false,
        off_selected: true,
    };

    fn note(n: u8) -> Note {
        Note::new(n).unwrap()
    }

    fn sound(o: Output) -> Option<Note> {
        match o {
            Output::Sound(n) => n,
            Output::PowerOff => panic!("unexpected PowerOff"),
        }
    }

    fn boot_ms() -> u32 {
        tune_ms(BOOT_CHIRP, DEFAULT_BPM)
    }

    fn after_boot() -> App {
        let mut a = App::new(0, false);
        a.tick(boot_ms(), RUN);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
        a
    }

    fn press(a: &mut App, at: u32) {
        a.tick(at, PRESS);
        a.tick(at + BUTTON_DEBOUNCE_MS, PRESS);
        a.tick(at + BUTTON_DEBOUNCE_MS + 1, RUN);
        a.tick(at + 2 * BUTTON_DEBOUNCE_MS + 2, RUN);
    }

    #[test]
    fn boot_chirps_then_listens_silently() {
        let mut a = App::new(1_000, false);
        assert_eq!(a.state(), State::Booting);
        assert_eq!(sound(a.tick(1_000, RUN)), Some(crate::notes::name::E6));
        assert_eq!(sound(a.tick(1_130, RUN)), Some(crate::notes::name::A6));
        a.tick(1_000 + boot_ms(), RUN);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
        for t in (1_300..20_000).step_by(7) {
            assert_eq!(sound(a.tick(t, RUN)), None);
        }
    }

    #[test]
    fn button_cycles_modes_and_listen_beeps() {
        let mut a = after_boot();
        let mut t = 10_000;
        for expect in [Mode::Jukebox, Mode::Scale, Mode::Listen, Mode::Jukebox] {
            press(&mut a, t);
            assert_eq!(a.state(), State::Mode(expect));
            t += 1_000;
        }
        // Back to listen: a short beep, then silence.
        press(&mut a, t);
        press(&mut a, t + 1_000);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
        assert_eq!(sound(a.tick(t + 3_000, RUN)), None);
    }

    #[test]
    fn listen_mode_beep_is_heard() {
        let mut a = after_boot();
        for t in [10_000, 11_000] {
            press(&mut a, t);
        }
        a.tick(12_000, PRESS);
        let o = sound(a.tick(12_000 + BUTTON_DEBOUNCE_MS, PRESS));
        assert_eq!(a.state(), State::Mode(Mode::Listen));
        assert_eq!(o, Some(crate::notes::name::C6));
        assert_eq!(sound(a.tick(12_500, RUN)), None);
    }

    #[test]
    fn button_ignored_during_boot_chirp() {
        let mut a = App::new(0, false);
        for t in (0..boot_ms()).step_by(5) {
            a.tick(t, PRESS);
        }
        a.tick(boot_ms(), PRESS);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
    }

    #[test]
    fn makers_demo_drives_the_board_like_his_add_on() {
        // His MasterMrRobot loop: note i, 100 ms, 0, 100 ms, for i in 1..70.
        let mut a = after_boot();
        let mut t = 1_000;
        for i in 1..70u8 {
            assert_eq!(a.on_i2c_write(&[i], t), 1);
            assert_eq!(sound(a.tick(t + 1, RUN)), Some(note(i)));
            assert_eq!(sound(a.tick(t + 99, RUN)), Some(note(i)));
            assert_eq!(a.on_i2c_write(&[0], t + 100), 1);
            assert_eq!(sound(a.tick(t + 101, RUN)), None);
            t += 200;
        }
        assert_eq!(a.state(), State::Badge);
    }

    #[test]
    fn held_note_never_times_out() {
        let mut a = after_boot();
        a.on_i2c_write(&[47], 1_000);
        for t in (1_000..60_000).step_by(997) {
            assert_eq!(sound(a.tick(t, RUN)), Some(note(47)));
        }
        assert_eq!(a.state(), State::Badge);
        assert_eq!(a.status()[2], 0x81);
        assert_eq!(a.status()[3], 47);
    }

    #[test]
    fn out_of_range_note_is_ignored_and_keeps_the_old_one() {
        let mut a = after_boot();
        a.on_i2c_write(&[10], 1_000);
        assert_eq!(a.on_i2c_write(&[90], 1_100), 0);
        assert_eq!(a.on_i2c_write(&[255], 1_200), 0);
        assert_eq!(a.on_i2c_write(&[], 1_300), 0);
        assert_eq!(sound(a.tick(1_400, RUN)), Some(note(10)));
    }

    #[test]
    fn invalid_writes_do_not_take_control() {
        let mut a = after_boot();
        press(&mut a, 2_000); // jukebox
        assert_eq!(a.on_i2c_write(&[200], 5_000), 0);
        assert_eq!(a.on_i2c_write(&[S, 9, 9, E], 5_000), 0);
        assert_eq!(a.state(), State::Mode(Mode::Jukebox));
    }

    #[test]
    fn badge_gives_back_control_after_silence_and_timeout() {
        let mut a = after_boot();
        press(&mut a, 1_000); // jukebox
        a.on_i2c_write(&[30], 5_000);
        a.on_i2c_write(&[0], 6_000);
        a.tick(6_000 + BADGE_TIMEOUT_MS - 1, RUN);
        assert_eq!(a.state(), State::Badge);
        a.tick(6_000 + BADGE_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Jukebox));
    }

    #[test]
    fn badge_tune_plays_then_times_out() {
        let mut a = after_boot();
        assert_eq!(a.on_i2c_write(&[S, OP_PLAY_TUNE, 0, E], 1_000), 1);
        assert_eq!(sound(a.tick(1_001, RUN)), Some(crate::notes::name::C5));
        assert_eq!(a.status()[2], 0x82);
        let len = tune_ms(TUNES[0].steps, DEFAULT_BPM);
        assert_eq!(sound(a.tick(1_000 + len, RUN)), None);
        assert_eq!(a.status()[2], 0x80);
        a.tick(1_000 + BADGE_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
    }

    #[test]
    fn slow_badge_tune_plays_to_the_end() {
        let mut a = after_boot();
        a.on_i2c_write(&[S, OP_TEMPO, MIN_BPM, E, S, OP_PLAY_TUNE, 4, E], 1_000);
        let len = tune_ms(TUNES[4].steps, MIN_BPM);
        // Last note (G6) still sounding just before the end.
        assert_eq!(
            sound(a.tick(1_000 + len - 100, RUN)),
            Some(crate::notes::name::G6)
        );
        assert_eq!(a.state(), State::Badge);
        assert_eq!(sound(a.tick(1_000 + len, RUN)), None);
        a.tick(1_000 + BADGE_TIMEOUT_MS.max(len) + 1, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Listen));
    }

    #[test]
    fn note_stops_tune_and_tune_stops_note() {
        let mut a = after_boot();
        a.on_i2c_write(&[S, OP_PLAY_TUNE, 1, E], 1_000);
        a.on_i2c_write(&[20], 1_050);
        assert_eq!(sound(a.tick(1_300, RUN)), Some(note(20)));
        a.on_i2c_write(&[S, OP_PLAY_TUNE, 2, E], 1_400);
        assert_eq!(sound(a.tick(1_401, RUN)), Some(crate::notes::name::G5));
        a.on_i2c_write(&[S, OP_STOP, 0, E], 1_450);
        assert_eq!(sound(a.tick(1_451, RUN)), None);
    }

    #[test]
    fn maker_zero_also_stops_a_tune() {
        let mut a = after_boot();
        a.on_i2c_write(&[S, OP_PLAY_TUNE, 1, E], 1_000);
        a.on_i2c_write(&[0], 1_010);
        assert_eq!(sound(a.tick(1_020, RUN)), None);
    }

    #[test]
    fn tempo_is_clamped_and_applies() {
        let mut a = after_boot();
        a.on_i2c_write(&[S, OP_TEMPO, 255, E], 1_000);
        assert_eq!(a.bpm(), MAX_BPM);
        a.on_i2c_write(&[S, OP_TEMPO, 1, E], 1_000);
        assert_eq!(a.bpm(), MIN_BPM);
        a.on_i2c_write(&[S, OP_TEMPO, 0, E], 1_000);
        assert_eq!(a.bpm(), DEFAULT_BPM);
        a.on_i2c_write(&[S, OP_TEMPO, 60, E, S, OP_PLAY_TUNE, 0, E], 2_000);
        // At 60 BPM a sixteenth is 250 ms: still the first note at 2 200.
        assert_eq!(sound(a.tick(2_200, RUN)), Some(crate::notes::name::C5));
        assert_eq!(sound(a.tick(2_260, RUN)), Some(crate::notes::name::E5));
    }

    #[test]
    fn button_takes_control_back_and_silences() {
        let mut a = after_boot();
        a.on_i2c_write(&[40], 1_000);
        press(&mut a, 2_000);
        assert_eq!(a.state(), State::Mode(Mode::Jukebox));
        // Jukebox starts the first tune straight away, not the held note.
        assert_eq!(sound(a.tick(2_100, RUN)), Some(crate::notes::name::C5));
    }

    #[test]
    fn badge_during_boot_ends_the_chirp() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[0], 50);
        assert_eq!(a.state(), State::Badge);
        assert_eq!(sound(a.tick(60, RUN)), None);
    }

    #[test]
    fn jukebox_plays_every_tune_in_turn_with_pauses() {
        let mut a = after_boot();
        press(&mut a, 1_000);
        let mut heard_first = std::vec::Vec::new();
        let mut was_silent = true;
        let mut t = 1_100;
        while t < 60_000 {
            let s = sound(a.tick(t, RUN));
            if let (Some(n), true) = (s, was_silent) {
                heard_first.push(n);
            }
            was_silent = s.is_none();
            t += 1;
        }
        // The first note of each tune appears, in order, with real pauses
        // in between (within-tune gaps also start new runs, so look for the
        // tunes' opening notes as a subsequence).
        let mut it = heard_first.iter();
        for tune in TUNES.iter().chain(TUNES.iter()) {
            let crate::tune::Step::Note(first, _) = tune.steps[0] else {
                panic!()
            };
            assert!(it.any(|n| *n == first), "tune {} missing", tune.name);
        }
    }

    #[test]
    fn scale_mode_is_the_makers_demo() {
        assert_eq!(scale_note(0), Some(note(1)));
        assert_eq!(scale_note(99), Some(note(1)));
        assert_eq!(scale_note(100), None);
        assert_eq!(scale_note(200), Some(note(2)));
        assert_eq!(scale_note(68 * 200), Some(note(69)));
        assert_eq!(scale_note(69 * 200), Some(note(1)), "wraps");
        let mut a = after_boot();
        press(&mut a, 1_000);
        press(&mut a, 2_000);
        assert_eq!(a.state(), State::Mode(Mode::Scale));
    }

    #[test]
    fn off_switch_powers_off_after_debounce() {
        let mut a = after_boot();
        a.on_i2c_write(&[47], 4_000);
        assert!(matches!(a.tick(5_000, OFF), Output::Sound(_)));
        assert_eq!(a.tick(5_000 + OFF_DEBOUNCE_MS, OFF), Output::PowerOff);
        assert_eq!(a.status()[3], 0);
    }

    #[test]
    fn off_glitch_does_not_power_off() {
        let mut a = after_boot();
        a.tick(5_000, OFF);
        assert!(matches!(a.tick(5_010, RUN), Output::Sound(_)));
        assert!(matches!(a.tick(5_100, RUN), Output::Sound(_)));
    }

    #[test]
    fn booting_into_off_never_makes_a_sound() {
        let mut a = App::new(0, true);
        assert_eq!(a.tick(0, OFF), Output::PowerOff);
    }

    #[test]
    fn status_bytes() {
        let mut a = App::new(0, false);
        assert_eq!(a.status()[..3], [VERSION_MAJOR, VERSION_MINOR, 0x40]);
        a.tick(boot_ms(), RUN);
        assert_eq!(a.status(), [VERSION_MAJOR, VERSION_MINOR, 0, 0]);
        a.on_i2c_write(&[S, OP_TEMPO, 100, E], boot_ms() + 1);
        assert_eq!(a.status()[2], 0x80);
    }

    #[test]
    fn whole_board_never_leaves_the_pin_high_when_silent() {
        // Drive app + tone generator together with a long pseudo-random mix
        // of badge writes, button presses and OFF, as the firmware does.
        // Whenever the app asks for silence or power-off, the pin is low.
        let mut a = App::new(0, false);
        let mut tone = ToneGen::new(MockPin::new());
        let mut x: u32 = 7;
        let mut button = false;
        let mut off = false;
        for t in (0..400_000u32).step_by(3) {
            x = x.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            let r = x >> 24;
            match r {
                0..=3 => {
                    a.on_i2c_write(&[(x >> 8) as u8 % 100], t);
                }
                4 => {
                    a.on_i2c_write(&[S, (x >> 8) as u8 % 4, (x >> 16) as u8 % 9, E], t);
                }
                5 => button = !button,
                6 => off = !off,
                _ => {}
            }
            let out = a.tick(
                t,
                Inputs {
                    button_down: button,
                    off_selected: off,
                },
            );
            match out {
                Output::Sound(n) => tone.set(n),
                Output::PowerOff => tone.silence(),
            }
            match (out, tone.hw().pin) {
                (Output::PowerOff, p) | (Output::Sound(None), p) => assert_eq!(p, Pin::Low),
                (Output::Sound(Some(_)), Pin::Square(_)) => {}
                (o, p) => panic!("{o:?} with pin {p:?}"),
            }
        }
    }
}
