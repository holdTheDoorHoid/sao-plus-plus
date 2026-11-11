//! The whole behaviour of the board as one state machine, independent of the
//! hardware. The firmware calls [`App::tick`] every few milliseconds and
//! [`App::on_i2c_write`] whenever the badge writes to address 0x1C.
//!
//! Same structure and decisions as the Mysterio and Hack-Man firmware:
//! * A mode-button press always means "next mode". If the board is in I2C
//!   mode, the press also hands control back from the badge to the board.
//! * Button presses during the 1 s boot glow are ignored.
//! * A valid I2C LED command during the boot glow ends it immediately.
//! * Entering I2C mode starts from all-off cues (brightness is remembered).
//! * Leaving I2C mode (timeout or button) restarts the current mode's
//!   animation from its beginning.
//! * Every power-on starts in mode 0.
//!
//! New here: the badge can also pick a built-in mode (command 8), which
//! leaves I2C mode at once. And every frame passes through the current cap
//! ([`crate::budget::limit`]) on its way out, in [`show`].

use crate::anim::{boot_frame, gamma};
use crate::budget;
use crate::i2c::{Command, I2C_TIMEOUT_MS, I2cState, parse_write};
use crate::input::Debounced;
use crate::modes::Mode;
use crate::{Frame, VERSION_MAJOR, VERSION_MINOR};

/// Boot: every sprinkle softly on for this long, then mode 0.
pub const BOOT_TOTAL_MS: u32 = 1_000;

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
    /// Show this frame: final PWM values in LED order (DA1 first), gamma and
    /// the current cap already applied.
    Show(Frame),
    /// The user selected OFF: blank the LEDs, put the driver in software
    /// shutdown and sleep until the switch leaves OFF.
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

impl App {
    /// `off_selected` is the switch position read once at power-on, so a board
    /// switched on into OFF goes straight back to sleep without flashing.
    pub fn new(now_ms: u32, off_selected: bool) -> Self {
        Self {
            boot_start: now_ms,
            booting: true,
            mode: Mode::Sprinkles,
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

    /// Handle one I2C write (any length). Commands are applied in order.
    /// Returns the number of valid commands.
    pub fn on_i2c_write(&mut self, bytes: &[u8], now_ms: u32) -> usize {
        parse_write(bytes, |c| self.apply(c, now_ms))
    }

    fn apply(&mut self, cmd: Command, now_ms: u32) {
        self.booting = false;
        match cmd {
            Command::SetMode(m) => {
                self.i2c_active = false;
                self.mode = m;
                self.mode_start = now_ms;
            }
            c => {
                if !self.i2c_active {
                    self.i2c.reset_colours();
                    self.i2c_active = true;
                }
                self.last_i2c = now_ms;
                self.i2c.apply(c);
            }
        }
    }

    /// Four status bytes for an I2C read: firmware major, minor, state
    /// (mode number 0..=4, or 0x80 in I2C mode, 0x40 while booting), and the
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
            if now_ms.wrapping_sub(self.boot_start) < BOOT_TOTAL_MS {
                return show_levels(boot_frame());
            }
            self.booting = false;
            self.mode_start = now_ms;
        }

        if self.i2c_active {
            if now_ms.wrapping_sub(self.last_i2c) >= I2C_TIMEOUT_MS {
                self.i2c_active = false;
                self.mode_start = now_ms;
            } else {
                return show(self.i2c.frame());
            }
        }

        show_levels(self.mode.render(now_ms.wrapping_sub(self.mode_start)))
    }
}

/// Built-in pictures are in perceived levels: gamma first, then out.
fn show_levels(levels: Frame) -> Output {
    let mut f = levels;
    for v in f.iter_mut() {
        *v = gamma(*v);
    }
    show(f)
}

/// Every frame leaves through here, so nothing can exceed the current cap.
fn show(mut pwm: Frame) -> Output {
    budget::limit(&mut pwm);
    Output::Show(pwm)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::LED_COUNT;
    use crate::budget::{LED_BUDGET_UA, MAX_PWM_SUM, estimate_ua, pwm_sum};

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
    fn boot_glow_is_even_and_inside_the_budget() {
        let mut a = App::new(1_000, false);
        let f = shown(a.tick(1_000, RUN));
        assert!(f.iter().all(|&v| v == f[0] && v > 0));
        assert!(pwm_sum(&f) <= MAX_PWM_SUM);
        assert_eq!(a.state(), State::Booting);
        a.tick(2_000, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
    }

    #[test]
    fn button_cycles_modes() {
        let mut a = after_boot();
        let mut t = 10_000;
        for expect in [
            Mode::Wave,
            Mode::Pulse,
            Mode::Drip,
            Mode::Off,
            Mode::Sprinkles,
        ] {
            press(&mut a, t);
            assert_eq!(a.state(), State::Mode(expect));
            t += 1_000;
        }
    }

    #[test]
    fn off_mode_is_dark_but_awake() {
        let mut a = after_boot();
        for t in [10_000, 11_000, 12_000, 13_000] {
            press(&mut a, t);
        }
        assert_eq!(a.state(), State::Mode(Mode::Off));
        assert_eq!(shown(a.tick(15_000, RUN)), [0; LED_COUNT]);
        a.on_i2c_write(&[0x10, 3, 99, 0, 6, 0, 0, 0], 15_100);
        assert_eq!(shown(a.tick(15_101, RUN))[3], 99);
    }

    #[test]
    fn holding_button_is_one_press() {
        let mut a = after_boot();
        for t in (5_000..8_000).step_by(5) {
            a.tick(t, PRESS);
        }
        assert_eq!(a.state(), State::Mode(Mode::Wave));
    }

    #[test]
    fn button_works_at_the_firmware_frame_rate() {
        // The firmware ticks every 20 ms; a 100 ms press must still count.
        let mut a = after_boot();
        let mut t = 5_000;
        for _ in 0..5 {
            a.tick(t, PRESS);
            t += 20;
        }
        for _ in 0..5 {
            a.tick(t, RUN);
            t += 20;
        }
        assert_eq!(a.state(), State::Mode(Mode::Wave));
    }

    #[test]
    fn button_ignored_during_boot() {
        let mut a = App::new(0, false);
        for t in (0..BOOT_TOTAL_MS).step_by(5) {
            a.tick(t, PRESS);
        }
        a.tick(BOOT_TOTAL_MS, PRESS);
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
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
        assert_eq!(a.on_i2c_write(&[0x10, 7, 40, 0, 6, 0, 0, 0], now), 2);
        assert_eq!(a.state(), State::I2c);
        let f = shown(a.tick(now + 1, RUN));
        assert_eq!(f[7], 40);
        assert_eq!(pwm_sum(&f), 40);
        a.tick(now + I2C_TIMEOUT_MS - 1, RUN);
        assert_eq!(a.state(), State::I2c);
        a.tick(now + I2C_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
    }

    #[test]
    fn the_badge_cannot_exceed_the_budget_either() {
        let mut a = after_boot();
        // Raw, full, everything: the worst a badge can ask for.
        a.on_i2c_write(&[0x91, 255, 0, 0, 6, 0, 0, 0], 5_000);
        let f = shown(a.tick(5_001, RUN));
        assert!(estimate_ua(&f) <= LED_BUDGET_UA);
        assert!(f.iter().all(|&v| v == f[0] && v > 0), "dimmed evenly");
    }

    #[test]
    fn badge_can_pick_a_mode() {
        let mut a = after_boot();
        a.on_i2c_write(&[0x11, 9, 0, 0, 6, 0, 0, 0], 5_000);
        assert_eq!(a.state(), State::I2c);
        assert_eq!(a.on_i2c_write(&[8, 3, 0, 0], 5_100), 1);
        assert_eq!(a.state(), State::Mode(Mode::Drip));
        // Next button press continues from there.
        press(&mut a, 6_000);
        assert_eq!(a.state(), State::Mode(Mode::Off));
        // Invalid mode number: nothing happens.
        assert_eq!(a.on_i2c_write(&[8, 5, 0, 0], 7_000), 0);
        assert_eq!(a.state(), State::Mode(Mode::Off));
    }

    #[test]
    fn mode_pick_during_boot_ends_boot() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[8, 1, 0, 0], 100);
        assert_eq!(a.state(), State::Mode(Mode::Wave));
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
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
    }

    #[test]
    fn invalid_command_does_not_enter_i2c_mode() {
        let mut a = after_boot();
        assert_eq!(a.on_i2c_write(&[42, 0, 0, 0], 5_000), 0);
        assert_eq!(a.on_i2c_write(&[0, 255, 255, 255], 5_000), 0);
        assert_eq!(a.on_i2c_write(&[0x10, 200, 1, 0], 5_000), 0);
        assert_eq!(a.on_i2c_write(&[6, 2], 5_000), 0);
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
    }

    #[test]
    fn i2c_during_boot_ends_boot() {
        let mut a = App::new(0, false);
        a.on_i2c_write(&[6, 0, 0, 0], 100);
        assert_eq!(a.state(), State::I2c);
        assert_eq!(shown(a.tick(101, RUN)), [0; LED_COUNT]);
        a.tick(100 + I2C_TIMEOUT_MS, RUN);
        assert_eq!(a.state(), State::Mode(Mode::Sprinkles));
    }

    #[test]
    fn button_leaves_i2c_mode() {
        let mut a = after_boot();
        a.on_i2c_write(&[6, 0, 0, 0], 5_000);
        press(&mut a, 5_100);
        assert_eq!(a.state(), State::Mode(Mode::Wave));
    }

    #[test]
    fn new_i2c_session_starts_dark_but_keeps_brightness() {
        let mut a = after_boot();
        a.on_i2c_write(&[7, 10, 0, 0, 0x11, 255, 0, 0, 6, 0, 0, 0], 5_000);
        a.tick(5_000 + I2C_TIMEOUT_MS, RUN);
        a.on_i2c_write(&[5, 0, 0, 0], 20_000);
        assert_eq!(shown(a.tick(20_001, RUN)), [0; LED_COUNT]);
        assert_eq!(a.status()[3], 10);
    }

    #[test]
    fn status_bytes() {
        let mut a = App::new(0, false);
        assert_eq!(a.status(), [VERSION_MAJOR, VERSION_MINOR, 0x40, 255]);
        a.tick(BOOT_TOTAL_MS, RUN);
        assert_eq!(a.status()[2], 0);
        a.on_i2c_write(&[7, 99, 0, 0], BOOT_TOTAL_MS + 1);
        assert_eq!(a.status(), [VERSION_MAJOR, VERSION_MINOR, 0x80, 99]);
        a.on_i2c_write(&[8, 4, 0, 0], BOOT_TOTAL_MS + 2);
        assert_eq!(a.status()[2], 4);
    }

    /// The safety requirement, end to end: whatever the board shows, in any
    /// mode, at any time, booting or not, the estimate stays in budget.
    #[test]
    fn every_mode_respects_the_budget_all_the_time() {
        let mut a = App::new(0, false);
        let mut t = 0;
        let mut scaled_somewhere = false;
        for _ in 0..5 {
            for _ in 0..800 {
                t += 23;
                let f = shown(a.tick(t, RUN));
                assert!(pwm_sum(&f) <= MAX_PWM_SUM, "t={t} {:?}", a.state());
                assert!(estimate_ua(&f) <= LED_BUDGET_UA);
                scaled_somewhere |= pwm_sum(&f) > MAX_PWM_SUM * 9 / 10;
            }
            t += 1_000;
            press(&mut a, t);
            t += 100;
        }
        assert!(scaled_somewhere, "the animations should use the budget");
    }

    #[test]
    fn animation_restarts_after_i2c_timeout() {
        let mut a = after_boot();
        a.tick(5_000, RUN);
        a.on_i2c_write(&[6, 0, 0, 0], 5_000);
        let back = 5_000 + I2C_TIMEOUT_MS;
        let f = shown(a.tick(back, RUN));
        let mut fresh = Mode::Sprinkles.render(0);
        for v in fresh.iter_mut() {
            *v = gamma(*v);
        }
        budget::limit(&mut fresh);
        assert_eq!(f, fresh);
    }
}
