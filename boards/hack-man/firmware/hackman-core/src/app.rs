//! The whole behaviour of the board as one state machine, independent of the
//! hardware. The firmware calls [`App::tick`] every few milliseconds and
//! [`App::on_i2c_write`] whenever the badge writes to address 0x1A.
//!
//! Decisions made here (the original description does not cover them):
//! * A mode-button press always means "next mode". If the board is in I2C
//!   mode, the press also hands control back from the badge to the board.
//! * Button presses during the 2 s boot sequence are ignored.
//! * A valid I2C command during the boot sequence ends it immediately.
//! * Entering I2C mode starts from all-black cues (brightness is remembered).
//! * Leaving I2C mode (timeout or button) restarts the current mode's
//!   animation from its beginning.
//! * The current mode is not remembered across "off" (the off position resets
//!   the chip on wake), so every power-on starts in mode 0.

use crate::i2c::{I2C_TIMEOUT_MS, I2cState, parse_write};
use crate::input::Debounced;
use crate::modes::Mode;
use crate::palette::CHARACTERS;
use crate::{DEFAULT_BRIGHTNESS, Frame, LED_COUNT, Rgb, VERSION_MAJOR, VERSION_MINOR, scale_frame};

/// Boot: character colours for this long...
pub const BOOT_COLOURS_MS: u32 = 1_000;
/// ...then the major version (white) and minor version (green) this long each.
pub const BOOT_VERSION_MS: u32 = 500;
pub const BOOT_TOTAL_MS: u32 = BOOT_COLOURS_MS + 2 * BOOT_VERSION_MS;

pub const BUTTON_DEBOUNCE_MS: u32 = 25;
pub const OFF_DEBOUNCE_MS: u32 = 30;

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
    /// Show this frame (final values, brightness already applied).
    Show(Frame),
    /// The user selected OFF: blank the LEDs and sleep until the switch
    /// leaves OFF.
    PowerOff,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    Booting,
    Mode(Mode),
    I2c,
}

pub struct App {
    boot_start: u32,
    booting: bool,
    mode: Mode,
    mode_start: u32,
    i2c_active: bool,
    last_i2c: u32,
    i2c: I2cState,
    button: Debounced,
    off: Debounced,
}

/// Binary display of `value` on the five LEDs: bit 0 on chain index 0 (the
/// rightmost character), so read left to right it is ordinary binary with the
/// most significant bit on Pac-Man. Zero shows all LEDs dark.
pub fn binary_frame(value: u8, color: Rgb) -> Frame {
    let mut f = [Rgb::OFF; LED_COUNT];
    for (bit, out) in f.iter_mut().enumerate() {
        if value & (1 << bit) != 0 {
            *out = color;
        }
    }
    f
}

/// The boot sequence frame at `t` ms after power-on (design units).
pub fn boot_frame(t: u32) -> Frame {
    if t < BOOT_COLOURS_MS {
        CHARACTERS
    } else if t < BOOT_COLOURS_MS + BOOT_VERSION_MS {
        binary_frame(VERSION_MAJOR, Rgb::WHITE)
    } else {
        binary_frame(VERSION_MINOR, Rgb::GREEN)
    }
}

impl App {
    /// `off_selected` is the switch position read once at power-on, so a board
    /// switched on into OFF goes straight back to sleep without flashing.
    pub fn new(now_ms: u32, off_selected: bool) -> Self {
        Self {
            boot_start: now_ms,
            booting: true,
            mode: Mode::Attract,
            mode_start: now_ms,
            i2c_active: false,
            last_i2c: now_ms,
            i2c: I2cState::new(),
            button: Debounced::new(false, BUTTON_DEBOUNCE_MS),
            off: Debounced::new(off_selected, OFF_DEBOUNCE_MS),
        }
    }

    pub fn state(&self) -> State {
        if self.i2c_active {
            State::I2c
        } else if self.booting {
            State::Booting
        } else {
            State::Mode(self.mode)
        }
    }

    /// Handle one I2C write (any length). Returns the number of valid commands.
    pub fn on_i2c_write(&mut self, bytes: &[u8], now_ms: u32) -> usize {
        let valid = parse_write(bytes, |_| {});
        if valid == 0 {
            return 0;
        }
        if !self.i2c_active {
            self.i2c.reset_colours();
            self.i2c_active = true;
            self.booting = false;
        }
        self.last_i2c = now_ms;
        let i2c = &mut self.i2c;
        parse_write(bytes, |c| i2c.apply(c))
    }

    /// Four status bytes for an I2C read: firmware major, minor, state
    /// (mode number 0..=3, or 0x80 in I2C mode, 0x40 while booting), and the
    /// current I2C brightness.
    pub fn status(&self) -> [u8; 4] {
        let state = match self.state() {
            State::Booting => 0x40,
            State::Mode(m) => m.number(),
            State::I2c => 0x80,
        };
        [VERSION_MAJOR, VERSION_MINOR, state, self.i2c.brightness]
    }

    pub fn tick(&mut self, now_ms: u32, inputs: Inputs) -> Output {
        self.off.update(inputs.off_selected, now_ms);
        if self.off.level() {
            return Output::PowerOff;
        }

        if self.button.update(inputs.button_down, now_ms) == Some(true) && !self.booting {
            self.i2c_active = false;
            self.mode = self.mode.next();
            self.mode_start = now_ms;
        }

        if self.booting {
            let t = now_ms.wrapping_sub(self.boot_start);
            if t < BOOT_TOTAL_MS {
                return Output::Show(scale_frame(&boot_frame(t), DEFAULT_BRIGHTNESS));
            }
            self.booting = false;
            self.mode_start = now_ms;
        }

        if self.i2c_active {
            if now_ms.wrapping_sub(self.last_i2c) >= I2C_TIMEOUT_MS {
                self.i2c_active = false;
                self.mode_start = now_ms;
            } else {
                return Output::Show(self.i2c.frame());
            }
        }

        let t = now_ms.wrapping_sub(self.mode_start);
        Output::Show(scale_frame(&self.mode.render(t), DEFAULT_BRIGHTNESS))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{PACMAN, PINK, palette};

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

    fn shown(o: Output) -> Frame {
        match o {
            Output::Show(f) => f,
            Output::PowerOff => panic!("unexpected PowerOff"),
        }
    }

    fn after_boot() -> App {
        let mut a = App::new(0, false);
        a.tick(BOOT_TOTAL_MS, RUN);
        a
    }

    fn press(a: &mut App, at: u32) {
        a.tick(at, PRESS);
        a.tick(at + BUTTON_DEBOUNCE_MS, PRESS);
        a.tick(at + BUTTON_DEBOUNCE_MS + 1, RUN);
        a.tick(at + 2 * BUTTON_DEBOUNCE_MS + 2, RUN);
    }

    #[test]
    fn boot_sequence() {
        let mut a = App::new(1_000, false);
        let f = shown(a.tick(1_000, RUN));
        assert_eq!(f, scale_frame(&palette::CHARACTERS, DEFAULT_BRIGHTNESS));
        let f = shown(a.tick(1_000 + BOOT_COLOURS_MS + 10, RUN));
        assert_eq!(
            f,
            scale_frame(&binary_frame(VERSION_MAJOR, Rgb::WHITE), DEFAULT_BRIGHTNESS)
        );
        let f = shown(a.tick(1_000 + BOOT_COLOURS_MS + BOOT_VERSION_MS + 10, RUN));
        assert_eq!(
            f,
            scale_frame(&binary_frame(VERSION_MINOR, Rgb::GREEN), DEFAULT_BRIGHTNESS)
        );
        assert_eq!(a.state(), State::Booting);
        a.tick(1_000 + BOOT_TOTAL_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn binary_display_bit_order() {
        let f = binary_frame(0b10011, Rgb::WHITE);
        assert_eq!(f[0], Rgb::WHITE);
        assert_eq!(f[1], Rgb::WHITE);
        assert_eq!(f[2], Rgb::OFF);
        assert_eq!(f[3], Rgb::OFF);
        assert_eq!(f[4], Rgb::WHITE);
        assert_eq!(binary_frame(0, Rgb::WHITE), [Rgb::OFF; LED_COUNT]);
    }

    #[test]
    fn mode_zero_starts_at_its_beginning_after_boot() {
        let mut a = after_boot();
        let f = shown(a.tick(BOOT_TOTAL_MS + 100, RUN));
        assert_eq!(
            f,
            scale_frame(&Mode::Attract.render(100), DEFAULT_BRIGHTNESS)
        );
    }

    #[test]
    fn button_cycles_modes() {
        let mut a = after_boot();
        let mut t = 10_000;
        for expect in [
            Mode::HueCycle,
            Mode::Larson,
            Mode::ActorLarson,
            Mode::Attract,
        ] {
            press(&mut a, t);
            assert_eq!(a.state(), State::Mode(expect));
            t += 1_000;
        }
    }

    #[test]
    fn holding_button_is_one_press() {
        let mut a = after_boot();
        for t in (5_000..8_000).step_by(5) {
            a.tick(t, PRESS);
        }
        assert_eq!(a.state(), State::Mode(Mode::HueCycle));
    }

    #[test]
    fn button_bounce_is_ignored() {
        let mut a = after_boot();
        for t in (5_000..5_100).step_by(10) {
            a.tick(t, if (t / 10) % 2 == 0 { PRESS } else { RUN });
        }
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn button_ignored_during_boot() {
        let mut a = App::new(0, false);
        for t in (0..BOOT_TOTAL_MS).step_by(5) {
            a.tick(t, PRESS);
        }
        a.tick(BOOT_TOTAL_MS, PRESS);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn off_switch_powers_off_after_debounce() {
        let mut a = after_boot();
        assert!(matches!(a.tick(5_000, OFF), Output::Show(_)));
        assert_eq!(a.tick(5_000 + OFF_DEBOUNCE_MS, OFF), Output::PowerOff);
    }

    #[test]
    fn off_glitch_does_not_power_off() {
        let mut a = after_boot();
        a.tick(5_000, OFF);
        assert!(matches!(a.tick(5_010, RUN), Output::Show(_)));
        assert!(matches!(a.tick(5_100, RUN), Output::Show(_)));
    }

    #[test]
    fn booting_into_off_never_shows_anything() {
        let mut a = App::new(0, true);
        assert_eq!(a.tick(0, OFF), Output::PowerOff);
    }

    #[test]
    fn i2c_takes_over_and_times_out() {
        let mut a = after_boot();
        let now = 5_000;
        assert_eq!(
            a.on_i2c_write(&[7, 255, 0, 0, 4, 10, 20, 30, 6, 0, 0, 0], now),
            3
        );
        assert_eq!(a.state(), State::I2c);
        let f = shown(a.tick(now + 1, RUN));
        assert_eq!(f[PACMAN], Rgb::new(10, 20, 30));
        assert_eq!(f[PINK], Rgb::OFF);
        // Still in I2C mode just before the timeout...
        a.tick(now + I2C_TIMEOUT_MS - 1, RUN);
        assert_eq!(a.state(), State::I2c);
        // ...and back to the animation after it.
        a.tick(now + I2C_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn valid_commands_extend_the_timeout_invalid_do_not() {
        let mut a = after_boot();
        a.on_i2c_write(&[6, 0, 0, 0], 5_000);
        a.on_i2c_write(&[6, 0, 0, 0], 8_000);
        a.tick(5_000 + I2C_TIMEOUT_MS + 100, RUN);
        assert_eq!(a.state(), State::I2c);
        assert_eq!(a.on_i2c_write(&[99, 0, 0, 0], 12_000), 0);
        a.tick(8_000 + I2C_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn invalid_command_does_not_enter_i2c_mode() {
        let mut a = after_boot();
        assert_eq!(a.on_i2c_write(&[42, 0, 0, 0], 5_000), 0);
        assert_eq!(a.on_i2c_write(&[1, 2], 5_000), 0);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn i2c_during_boot_ends_boot() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[6, 0, 0, 0], 100);
        assert_eq!(a.state(), State::I2c);
        assert_eq!(shown(a.tick(101, RUN)), [Rgb::OFF; LED_COUNT]);
        // Times out into mode 0, not back into the boot sequence.
        a.tick(100 + I2C_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Attract));
    }

    #[test]
    fn button_leaves_i2c_mode() {
        let mut a = after_boot();
        a.on_i2c_write(&[6, 0, 0, 0], 5_000);
        press(&mut a, 5_100);
        assert_eq!(a.state(), State::Mode(Mode::HueCycle));
    }

    #[test]
    fn new_i2c_session_starts_black_but_keeps_brightness() {
        let mut a = after_boot();
        a.on_i2c_write(&[7, 10, 0, 0, 0, 255, 255, 255, 6, 0, 0, 0], 5_000);
        a.tick(5_000 + I2C_TIMEOUT_MS, RUN);
        a.on_i2c_write(&[5, 0, 0, 0], 20_000);
        let f = shown(a.tick(20_001, RUN));
        assert_eq!(f, [Rgb::OFF; LED_COUNT]);
        assert_eq!(a.status()[3], 10);
    }

    #[test]
    fn status_bytes() {
        let mut a = App::new(0, false);
        assert_eq!(
            a.status(),
            [VERSION_MAJOR, VERSION_MINOR, 0x40, DEFAULT_BRIGHTNESS]
        );
        a.tick(BOOT_TOTAL_MS, RUN);
        assert_eq!(a.status()[2], 0);
        a.on_i2c_write(&[7, 99, 0, 0], BOOT_TOTAL_MS + 1);
        assert_eq!(a.status(), [VERSION_MAJOR, VERSION_MINOR, 0x80, 99]);
    }

    #[test]
    fn animation_output_respects_default_brightness() {
        let mut a = after_boot();
        for t in (BOOT_TOTAL_MS..BOOT_TOTAL_MS + 20_000).step_by(97) {
            let f = shown(a.tick(t, RUN));
            for c in f {
                assert!(
                    c.r <= DEFAULT_BRIGHTNESS
                        && c.g <= DEFAULT_BRIGHTNESS
                        && c.b <= DEFAULT_BRIGHTNESS
                );
            }
        }
    }
}
