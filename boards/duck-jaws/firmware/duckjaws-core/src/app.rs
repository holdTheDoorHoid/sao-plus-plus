//! The whole behaviour of the board, independent of the hardware. The
//! firmware calls [`App::tick`] every few milliseconds and
//! [`App::on_i2c_write`] whenever the badge writes to address 0x6C.
//!
//! This is Duck Bath's `App` with two differences: the fourth fader channel
//! (the maker's "background") is handed out as the brightness of the red
//! mouth lights, and the text at register address 0 is this board's.

use duckbath_core::fader::Fader;
use duckbath_core::input::Debounced;
use duckbath_core::registers::{REG_MAX, Registers};
use duckbath_core::{Frame, LED_COUNT, Rgb};

/// The fader moves on once per this many milliseconds (the maker's loop time).
pub const STEP_MS: u32 = 20;
pub const OFF_DEBOUNCE_MS: u32 = 30;

/// How many bytes are offered to a badge that reads.
pub const READ_LEN: usize = 16;

/// Text returned from address 0 (zero-terminated, then zeros up to 0xEB).
/// Our own text: the maker's holds a poem that is not his to license.
pub const DOCS: &[u8] = b"Duck Jaws SAO, SAO++ edition.\n\
Original duckGLOW / duckJAWS by Adrian Studer\n\
github.com/astuder/duckglow\n\
hackaday.io/project/198918-duckglow-sao\n\
Registers: EC max, F0 min, F4 speed, F8 phase (R,G,B,mouth)\n";

const _: () = assert!(DOCS.len() < REG_MAX as usize);

/// Raw input levels, already converted to meaning (not electrical level).
#[derive(Clone, Copy, Debug, Default)]
pub struct Inputs {
    /// Power switch is in its middle "OFF" position right now.
    pub off_selected: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Output {
    /// Show this: the frame for the two LEDs in the duck, and the brightness
    /// (0..=255) of the four red LEDs round the mouth.
    Show { duck: Frame, mouth: u8 },
    /// The user selected OFF: blank everything and sleep until the switch
    /// leaves OFF.
    PowerOff,
}

pub struct App {
    regs: Registers,
    fader: Fader,
    off: Debounced,
    last_step: u32,
    colour: Rgb,
    mouth: u8,
    /// Register address a read starts at: where the last write left off.
    /// (Duck Bath's `Registers` keeps its own copy but does not show it.)
    pointer: u8,
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
            mouth: 0,
            pointer: 0,
        }
    }

    /// Handle one I2C write (register address, then data).
    pub fn on_i2c_write(&mut self, bytes: &[u8]) {
        if let Some((&addr, data)) = bytes.split_first() {
            self.pointer = addr.wrapping_add(data.len() as u8);
        }
        self.regs.on_write(bytes);
    }

    /// The bytes to send if the badge reads now.
    pub fn read_data(&self) -> [u8; READ_LEN] {
        let mut out = [0u8; READ_LEN];
        let mut addr = self.pointer;
        for b in out.iter_mut() {
            *b = if addr < REG_MAX {
                DOCS.get(addr as usize).copied().unwrap_or(0)
            } else {
                self.regs.read(addr)
            };
            addr = addr.wrapping_add(1);
        }
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
            self.colour = Rgb::new(v[0], v[1], v[2]);
            self.mouth = v[3];
        }
        Output::Show {
            duck: [self.colour; LED_COUNT],
            mouth: self.mouth,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const RUN: Inputs = Inputs { off_selected: false };
    const OFF: Inputs = Inputs { off_selected: true };

    #[test]
    fn starts_with_a_dim_yellow_duck_and_a_bright_red_mouth() {
        // The maker's defaults: the mouth starts half a breath ahead of the
        // duck (phase 128), so it is at its brightest when the duck is dimmest.
        let mut app = App::new(0, false);
        assert_eq!(
            app.tick(0, RUN),
            Output::Show { duck: [Rgb::new(10, 10, 0); LED_COUNT], mouth: 254 }
        );
    }

    #[test]
    fn badge_sets_the_mouth_steady() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0xEF, 40]); // max of the fourth channel
        app.on_i2c_write(&[0xF7, 0]); // its speed: 0 = steady
        match app.tick(20, RUN) {
            Output::Show { mouth, .. } => assert_eq!(mouth, 40),
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn badge_sets_a_steady_duck_colour() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0xEC, 200, 0, 50]); // max R, G, B
        app.on_i2c_write(&[0xF4, 0, 0, 0]); // speed 0 = steady
        match app.tick(20, RUN) {
            Output::Show { duck, .. } => assert_eq!(duck, [Rgb::new(200, 0, 50); LED_COUNT]),
            other => panic!("{other:?}"),
        }
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
        // after writing two data bytes the next read starts two further on
        app.on_i2c_write(&[0xEC, 80, 80]);
        assert_eq!(&app.read_data()[..2], &[0, 255]);
    }

    #[test]
    fn docs_text_is_this_boards() {
        let mut app = App::new(0, false);
        app.on_i2c_write(&[0x00]);
        assert_eq!(&app.read_data()[..9], b"Duck Jaws");
        // past the end of the text, and up to the first register, it reads 0
        app.on_i2c_write(&[0xE0]);
        assert_eq!(&app.read_data()[..13], &[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 80]);
    }
}
