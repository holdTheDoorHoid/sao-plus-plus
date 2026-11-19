//! The whole behaviour of the board, without any hardware: modes, the mode
//! button, the power switch, and the badge taking over through I2C.
//!
//! The firmware calls [`App::tick`] every couple of milliseconds with the
//! time and the two inputs, and shows the levels it gets back. A badge write
//! goes to [`App::on_i2c_write`]; a badge read gets [`App::status`].

use crate::i2c::{Command, I2C_TIMEOUT_MS, I2cState, parse_write};
use crate::input::Debounced;
use crate::lfsr::Lfsr;
use crate::show::{self, Anim, Script};
use crate::{ALL_OFF, ALL_ON, Levels, VERSION_MAJOR, VERSION_MINOR};

pub const BUTTON_DEBOUNCE_MS: u32 = 25;
pub const OFF_DEBOUNCE_MS: u32 = 30;
/// Parade mode: all eight on for this long between animations.
pub const PARADE_GAP_US: u32 = 1_000_000;

/// Built-in modes, chosen with the BOOT button (or I2C command 8).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// The maker's show: random waits, random animations (his weights).
    Show = 0,
    /// All eight animations in his order, one second apart, round and round.
    /// Handy for checking every LED.
    Parade = 1,
    /// All eight LEDs steadily on, like his board between animations.
    Still = 2,
}

impl Mode {
    pub const fn from_number(n: u8) -> Option<Mode> {
        match n {
            0 => Some(Mode::Show),
            1 => Some(Mode::Parade),
            2 => Some(Mode::Still),
            _ => None,
        }
    }

    pub const fn next(self) -> Mode {
        match self {
            Mode::Show => Mode::Parade,
            Mode::Parade => Mode::Still,
            Mode::Still => Mode::Show,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Inputs {
    /// The mode (BOOT) button is held down.
    pub button_down: bool,
    /// The power switch is on OFF (it ties D1 to 3.3 V there).
    pub off_selected: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Output {
    /// Show these levels.
    Leds(Levels),
    /// Blank everything and sleep until the switch leaves OFF.
    PowerOff,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    /// The board runs its own mode.
    Own(Mode),
    /// The badge sets the LEDs (I2C mode).
    Badge,
}

/// Steps through a [`Script`] by the clock and makes the next one when it ends.
#[derive(Clone, Debug)]
struct Player {
    script: Script,
    pos: usize,
    frame_start_us: u64,
    lfsr: Lfsr,
    anim: Option<Anim>,
    anim_from: usize,
    parade_next: u8,
}

impl Player {
    fn new(now_us: u64) -> Self {
        let mut p = Self {
            script: Script::new(ALL_OFF),
            pos: 0,
            frame_start_us: now_us,
            lfsr: Lfsr::new(),
            anim: None,
            anim_from: 0,
            parade_next: 0,
        };
        p.power_on(now_us);
        p
    }

    /// What the maker's board does when it is switched on: smile, then eyes, fade in.
    fn power_on(&mut self, now_us: u64) {
        self.script.restart(ALL_OFF);
        show::smile_in(&mut self.script, &mut self.lfsr);
        self.begin(None, 0, now_us);
    }

    fn begin(&mut self, anim: Option<Anim>, from: usize, now_us: u64) {
        self.pos = 0;
        self.frame_start_us = now_us;
        self.anim = anim;
        self.anim_from = from;
    }

    /// Start a mode from its beginning.
    fn restart(&mut self, mode: Mode, now_us: u64) {
        match mode {
            Mode::Show => self.power_on(now_us),
            Mode::Parade => {
                self.parade_next = 0;
                self.next(mode, now_us);
            }
            Mode::Still => self.next(mode, now_us),
        }
    }

    /// Play one of the maker's animations now, then carry on with the mode.
    fn play_now(&mut self, anim: Anim, now_us: u64) {
        self.script.restart(ALL_ON);
        show::build(anim, &mut self.script, &mut self.lfsr);
        self.begin(Some(anim), 0, now_us);
    }

    /// Make the next script for `mode` (the current one has ended).
    fn next(&mut self, mode: Mode, now_us: u64) {
        match mode {
            Mode::Show => {
                self.script.restart(self.script.end_levels());
                let (anim, from) = show::build_cycle(&mut self.script, &mut self.lfsr);
                self.begin(Some(anim), from, now_us);
            }
            Mode::Parade => {
                let anim = Anim::ALL[self.parade_next as usize % Anim::ALL.len()];
                self.parade_next = (self.parade_next + 1) % show::ANIM_COUNT;
                self.script.restart(ALL_ON);
                self.script.hold_us(PARADE_GAP_US);
                show::build(anim, &mut self.script, &mut self.lfsr);
                self.begin(Some(anim), 1, now_us);
            }
            Mode::Still => {
                self.script.restart(ALL_ON);
                self.script.hold_us(1_000_000);
                self.begin(None, 0, now_us);
            }
        }
    }

    fn levels(&mut self, mode: Mode, now_us: u64) -> Levels {
        // Bounded: each script lasts at least a few milliseconds, so a late
        // call catches up in a few rounds at most.
        for _ in 0..64 {
            match self.script.get(self.pos) {
                Some(f) => {
                    let end = self.frame_start_us + f.us as u64;
                    if now_us < end {
                        return f.levels;
                    }
                    self.frame_start_us = end;
                    self.pos += 1;
                }
                None => {
                    // Carry on from where the last script ended in time, unless
                    // we are far behind (the board was busy or asleep).
                    let start = if now_us.saturating_sub(self.frame_start_us) < 1_000_000 {
                        self.frame_start_us
                    } else {
                        now_us
                    };
                    self.next(mode, start);
                }
            }
        }
        self.frame_start_us = now_us;
        self.script.end_levels()
    }

    fn playing(&self) -> Option<Anim> {
        if self.pos >= self.anim_from && self.pos < self.script.len() {
            self.anim
        } else {
            None
        }
    }
}

#[derive(Clone, Debug)]
pub struct App {
    mode: Mode,
    state: State,
    button: Debounced,
    off: Debounced,
    i2c: I2cState,
    last_i2c_ms: u32,
    player: Player,
}

fn ms(now_us: u64) -> u32 {
    (now_us / 1000) as u32
}

impl App {
    pub fn new(now_us: u64, off_selected: bool) -> Self {
        Self {
            mode: Mode::Show,
            state: State::Own(Mode::Show),
            button: Debounced::new(false, BUTTON_DEBOUNCE_MS),
            off: Debounced::new(off_selected, OFF_DEBOUNCE_MS),
            i2c: I2cState::new(),
            last_i2c_ms: ms(now_us),
            player: Player::new(now_us),
        }
    }

    pub fn state(&self) -> State {
        self.state
    }

    pub fn mode(&self) -> Mode {
        self.mode
    }

    /// The maker's animation playing right now, if any.
    pub fn playing(&self) -> Option<Anim> {
        match self.state {
            State::Own(_) => self.player.playing(),
            State::Badge => None,
        }
    }

    fn set_mode(&mut self, mode: Mode, now_us: u64) {
        self.mode = mode;
        self.state = State::Own(mode);
        self.player.restart(mode, now_us);
    }

    /// A badge write. Returns how many valid commands it held.
    pub fn on_i2c_write(&mut self, bytes: &[u8], now_us: u64) -> usize {
        parse_write(bytes, |c| self.apply(c, now_us))
    }

    fn apply(&mut self, cmd: Command, now_us: u64) {
        self.last_i2c_ms = ms(now_us);
        match cmd {
            Command::SetMode(n) => {
                if let Some(m) = Mode::from_number(n) {
                    self.set_mode(m, now_us);
                }
            }
            Command::Play(anim) => {
                self.state = State::Own(self.mode);
                self.player.play_now(anim, now_us);
            }
            other => {
                if self.state != State::Badge {
                    self.i2c.reset_levels();
                    self.state = State::Badge;
                }
                self.i2c.apply(other);
            }
        }
    }

    /// Four bytes for a badge read: version major, minor, who is in charge
    /// (0, 1, 2 = the board in that mode; 0x80 = the badge), and the maker's
    /// animation playing now (0..=7) or 0xFF for none.
    pub fn status(&self) -> [u8; 4] {
        let who = match self.state {
            State::Own(m) => m as u8,
            State::Badge => 0x80,
        };
        let anim = self.playing().map(|a| a as u8).unwrap_or(0xFF);
        [VERSION_MAJOR, VERSION_MINOR, who, anim]
    }

    pub fn tick(&mut self, now_us: u64, inputs: Inputs) -> Output {
        let now = ms(now_us);
        self.off.update(inputs.off_selected, now);
        if self.off.level() {
            return Output::PowerOff;
        }
        if self.button.update(inputs.button_down, now) == Some(true) {
            let mode = match self.state {
                // The badge had control: take it back, same mode.
                State::Badge => self.mode,
                State::Own(m) => m.next(),
            };
            self.set_mode(mode, now_us);
        }
        if self.state == State::Badge && now.wrapping_sub(self.last_i2c_ms) >= I2C_TIMEOUT_MS {
            self.state = State::Own(self.mode);
            self.player.restart(self.mode, now_us);
        }
        Output::Leds(match self.state {
            State::Badge => self.i2c.levels(),
            State::Own(m) => self.player.levels(m, now_us),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::show::{STEP_US, WAIT_US};

    const NO: Inputs = Inputs {
        button_down: false,
        off_selected: false,
    };

    fn leds(o: Output) -> Levels {
        match o {
            Output::Leds(l) => l,
            Output::PowerOff => panic!("unexpected power-off"),
        }
    }

    #[test]
    fn starts_dark_and_fades_the_smile_in_first() {
        let mut a = App::new(0, false);
        assert_eq!(leds(a.tick(0, NO)), ALL_OFF);
        // halfway through the smile fade the eyes are still dark
        let l = leds(a.tick(8 * 7 * STEP_US as u64, NO));
        assert!(l[2] > 0 && l[0] == 0 && l[1] == 0);
        // well after power-on (at most 16 + 16 steps + 63 waits) all are on
        let t = (32 * 7 * STEP_US + 63 * WAIT_US) as u64 + 10;
        assert_eq!(leds(a.tick(t, NO)), ALL_ON);
    }

    #[test]
    fn show_runs_for_hours_without_sticking() {
        let mut a = App::new(0, false);
        let mut seen = [false; 8];
        let mut t = 0u64;
        // two simulated hours in 2 ms steps would be slow; 20 ms steps are enough here
        while t < 2 * 3600 * 1_000_000 {
            a.tick(t, NO);
            if let Some(x) = a.playing() {
                seen[x as usize] = true;
            }
            t += 20_000;
        }
        assert!(seen.iter().all(|&s| s), "{seen:?}");
    }

    #[test]
    fn button_cycles_modes() {
        let mut a = App::new(0, false);
        let mut t = 1_000u64;
        let press = |a: &mut App, t: &mut u64| {
            for _ in 0..20 {
                a.tick(*t, Inputs { button_down: true, off_selected: false });
                *t += 2_000;
            }
            for _ in 0..20 {
                a.tick(*t, NO);
                *t += 2_000;
            }
        };
        press(&mut a, &mut t);
        assert_eq!(a.state(), State::Own(Mode::Parade));
        press(&mut a, &mut t);
        assert_eq!(a.state(), State::Own(Mode::Still));
        assert_eq!(leds(a.tick(t, NO)), ALL_ON);
        press(&mut a, &mut t);
        assert_eq!(a.state(), State::Own(Mode::Show));
    }

    #[test]
    fn parade_plays_all_eight_in_order() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[8, 1, 0, 0], 0);
        let mut order = std::vec::Vec::new();
        let mut t = 0u64;
        while order.len() < 9 && t < 3_600_000_000 {
            a.tick(t, NO);
            if let Some(x) = a.playing() {
                if order.last() != Some(&(x as u8)) {
                    order.push(x as u8);
                }
            }
            t += 2_000;
        }
        assert_eq!(&order[..9], &[0, 1, 2, 3, 4, 5, 6, 7, 0]);
    }

    #[test]
    fn off_switch_powers_off_after_debounce() {
        let mut a = App::new(0, false);
        let off = Inputs { button_down: false, off_selected: true };
        assert!(matches!(a.tick(1_000, off), Output::Leds(_)));
        assert_eq!(a.tick(40_000, off), Output::PowerOff);
        // switched on in OFF: off at once
        let mut b = App::new(0, true);
        assert_eq!(b.tick(0, off), Output::PowerOff);
    }

    #[test]
    fn badge_takes_over_and_times_out() {
        let mut a = App::new(0, false);
        assert_eq!(a.on_i2c_write(&[0x10, 0, 255, 0, 6, 0, 0, 0], 1_000_000), 2);
        assert_eq!(a.state(), State::Badge);
        let l = leds(a.tick(1_001_000, NO));
        assert_eq!(l, [255, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(a.status()[2], 0x80);
        // still in charge 4.9 s later, not 5.1 s later
        a.tick(5_900_000, NO);
        assert_eq!(a.state(), State::Badge);
        a.tick(6_100_000, NO);
        assert_eq!(a.state(), State::Own(Mode::Show));
    }

    #[test]
    fn invalid_writes_do_not_take_over() {
        let mut a = App::new(0, false);
        assert_eq!(a.on_i2c_write(&[0x10, 8, 255, 0], 0), 0);
        assert_eq!(a.on_i2c_write(&[1, 2, 3], 0), 0);
        assert_eq!(a.state(), State::Own(Mode::Show));
    }

    #[test]
    fn play_command_runs_that_animation_then_carries_on() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[9, 2, 0, 0], 50_000_000);
        assert_eq!(a.playing(), Some(Anim::LickRight));
        assert_eq!(a.status()[3], 2);
        // the lick takes 6 x 8 steps; after that it is the show again
        let mut t = 50_000_000u64;
        let mut l = leds(a.tick(t, NO));
        assert_eq!(l[2], 0x20);
        t += (6 * 8 * STEP_US) as u64 + 1;
        l = leds(a.tick(t, NO));
        assert_eq!(l, ALL_ON, "back to all on (the show's wait) or a new animation's first frame");
        assert_eq!(a.state(), State::Own(Mode::Show));
    }

    #[test]
    fn button_takes_control_back_from_the_badge() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[0x11, 9, 0, 0, 6, 0, 0, 0], 0);
        assert_eq!(a.state(), State::Badge);
        let mut t = 1_000;
        for _ in 0..20 {
            a.tick(t, Inputs { button_down: true, off_selected: false });
            t += 2_000;
        }
        assert_eq!(a.state(), State::Own(Mode::Show));
    }

    #[test]
    fn status_reports_version() {
        let a = App::new(0, false);
        let s = a.status();
        assert_eq!(&s[..3], &[VERSION_MAJOR, VERSION_MINOR, 0]);
        assert_eq!(s[3], 0xFF, "the power-on fade is not one of his eight animations");
    }

    #[test]
    fn many_commands_in_one_write_all_apply() {
        let mut a = App::new(0, false);
        let mut w = std::vec::Vec::new();
        for i in 0..8u8 {
            w.extend_from_slice(&[0x10, i, 10 * (i + 1), 0]);
        }
        w.extend_from_slice(&[7, 255, 0, 0, 6, 0, 0, 0]);
        assert_eq!(a.on_i2c_write(&w, 0), 10);
        assert_eq!(leds(a.tick(1, NO)), [10, 20, 30, 40, 50, 60, 70, 80]);
    }
}
