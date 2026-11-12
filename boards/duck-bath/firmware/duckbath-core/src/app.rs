//! The whole behaviour of the board, independent of the hardware. The
//! firmware calls [`App::tick`] every few milliseconds and
//! [`App::on_i2c_write`] whenever the badge writes to address 0x6C.
//!
//! There is no button and no "badge has taken over" state: as on the maker's
//! board, the duck always shows whatever the registers say, and a badge
//! changes the registers.

use crate::fader::Fader;
use crate::input::Debounced;
use crate::registers::Registers;
use crate::{Frame, LED_COUNT, Rgb};

/// The fader moves on once per this many milliseconds (the maker's loop time).
pub const STEP_MS: u32 = 20;
pub const OFF_DEBOUNCE_MS: u32 = 30;

/// How many bytes are offered to a badge that reads.
pub const READ_LEN: usize = 16;

/// Raw input levels, already converted to meaning (not electrical level).
#[derive(Clone, Copy, Debug, Default)]
pub struct Inputs {
    /// Power switch is in its middle "OFF" position right now.
    pub off_selected: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Output {
    /// Show this frame.
    Show(Frame),
    /// The user selected OFF: blank the LEDs and sleep until the switch
    /// leaves OFF.
    PowerOff,
}

pub struct App {
    regs: Registers,
    fader: Fader,
    off: Debounced,
    last_step: u32,
    colour: Rgb,
}

impl App {
    /// `off_selected` is the switch position read once at power-on, so a board
    /// switched on into OFF goes straight back to sleep without flashing.
    pub fn new(now_ms: u32, off_selected: bool) -> Self {
        Self {
            regs: Registers::new(),
            fader: Fader::new(),
            off: Debounced::new(off_selected, OFF_DEBOUNCE_MS),
            last_step: now_ms.wrapping_sub(STEP_MS),
            colour: Rgb::OFF,
        }
    }

    /// Handle one I2C write (register address, then data).
    pub fn on_i2c_write(&mut self, bytes: &[u8]) {
        self.regs.on_write(bytes);
    }

    /// The bytes to send if the badge reads now.
    pub fn read_data(&self) -> [u8; READ_LEN] {
        let mut out = [0u8; READ_LEN];
        self.regs.read_into(&mut out);
        out
    }

    pub fn tick(&mut self, now_ms: u32, inputs: Inputs) -> Output {
        self.off.update(inputs.off_selected, now_ms);
        if self.off.level() {
            return Output::PowerOff;
        }
        if now_ms.wrapping_sub(self.last_step) >= STEP_MS {
            self.last_step = now_ms;
            let v = self.fader.step(&self.regs.settings);
            // v[3] is the duckJAWS background channel: nothing to drive here.
            self.colour = Rgb::new(v[0], v[1], v[2]);
        }
        Output::Show([self.colour; LED_COUNT])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RUN: Inputs = Inputs { off_selected: false };
    const OFF: Inputs = Inputs { off_selected: true };

    #[test]
    fn starts_with_the_dim_end_of_a_yellow_breath() {
        let mut app = App::new(0, false);
        assert_eq!(app.tick(0, RUN), Output::Show([Rgb::new(10, 10, 0); LED_COUNT]));
    }

    #[test]
    fn badge_sets_a_steady_colour() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0xEC, 200, 0, 50]); // max R, G, B
        app.on_i2c_write(&[0xF4, 0, 0, 0]); // speed 0 = steady
        assert_eq!(app.tick(20, RUN), Output::Show([Rgb::new(200, 0, 50); LED_COUNT]));
        assert_eq!(app.tick(40, RUN), Output::Show([Rgb::new(200, 0, 50); LED_COUNT]));
    }

    #[test]
    fn fader_only_moves_every_20_ms() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0xF4, 255, 255]); // fast, so each step changes the colour
        let a = app.tick(0, RUN);
        assert_eq!(app.tick(10, RUN), a);
        assert_ne!(app.tick(20, RUN), a);
    }

    #[test]
    fn off_position_powers_off_after_debounce() {
        let mut app = App::new(0, false);
        assert_ne!(app.tick(0, OFF), Output::PowerOff);
        assert_eq!(app.tick(OFF_DEBOUNCE_MS, OFF), Output::PowerOff);
        let mut app = App::new(0, true);
        assert_eq!(app.tick(0, OFF), Output::PowerOff);
    }

    #[test]
    fn read_returns_registers_from_the_last_written_address() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0xEC]);
        assert_eq!(&app.read_data()[..8], &[80, 80, 0, 255, 10, 10, 0, 0]);
    }
}
