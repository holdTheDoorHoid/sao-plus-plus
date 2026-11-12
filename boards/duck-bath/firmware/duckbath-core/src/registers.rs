//! The I2C register map of the maker's duckGLOW add-on (7-bit address 0x6C).
//!
//! A write is one register address followed by data bytes; the address moves
//! on by one after each data byte. A read returns bytes starting at the
//! address of the last write.
//!
//! | address   | name  | meaning                                                   |
//! |-----------|-------|-----------------------------------------------------------|
//! | 0x00-0xEB | docs  | a short text about the add-on (read-only)                 |
//! | 0xEC-0xEF | max   | brightest value for red, green, blue, background          |
//! | 0xF0-0xF3 | min   | dimmest value for red, green, blue, background            |
//! | 0xF4-0xF7 | speed | fading speed per channel; 0 = steady at max               |
//! | 0xF8-0xFB | phase | where in the fading cycle each channel starts             |
//! | 0xFC      | mode  | bits 0..1: LED control 0 = auto, 1 = I2C, 2 = WS2812      |
//! | 0xFD      | save  | write 42 to keep settings, 24 to go back to the defaults  |
//! | 0xFE      | debug | result code of the last save / reset                      |
//!
//! What is different on this board (see the firmware README):
//! * the "background" channel exists only on the maker's duckJAWS board; it is
//!   stored and can be read back, but drives nothing here;
//! * mode is stored but the WS2812 input is not implemented, and the "UV LED
//!   detected" bit (bit 4) always reads 0;
//! * save (42) is not implemented: settings are lost at power-off, and the
//!   debug register then reads [`ERR_SAVE_NOT_SUPPORTED`]. 24 restores the
//!   defaults at once;
//! * the docs text is our own. The maker's holds a poem that is not his to
//!   license, so it is not copied.

/// 7-bit I2C address. The maker's two solder jumpers (0x6D..0x6F) are not on
/// this board; change this constant instead.
pub const ADDRESS: u8 = 0x6C;

pub const CHANNELS: usize = 4;

pub const REG_MAX: u8 = 0xEC;
pub const REG_MIN: u8 = 0xF0;
pub const REG_SPEED: u8 = 0xF4;
pub const REG_PHASE: u8 = 0xF8;
pub const REG_MODE: u8 = 0xFC;
pub const REG_SAVE: u8 = 0xFD;
pub const REG_DEBUG: u8 = 0xFE;

pub const SAVE_STORE: u8 = 42;
pub const SAVE_FACTORY_RESET: u8 = 24;

pub const ERR_NONE: u8 = 0;
/// Not one of the maker's codes (his are 0..=3).
pub const ERR_SAVE_NOT_SUPPORTED: u8 = 4;

/// Text returned from address 0 (zero-terminated, then zeros up to 0xEB).
pub const DOCS: &[u8] = b"Duck Bath SAO, SAO++ edition.\n\
Original duckGLOW / duckBATH by Adrian Studer\n\
github.com/astuder/duckglow\n\
hackaday.io/project/198918-duckglow-sao\n\
Registers: EC max, F0 min, F4 speed, F8 phase (R,G,B,-)\n";

const _: () = assert!(DOCS.len() < REG_MAX as usize);

/// The settings a badge can change.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Settings {
    pub max: [u8; CHANNELS],
    pub min: [u8; CHANNELS],
    pub speed: [u8; CHANNELS],
    pub phase: [u8; CHANNELS],
    pub mode: u8,
}

impl Settings {
    /// The maker's power-on values: a slow yellow breath.
    pub const DEFAULT: Settings = Settings {
        max: [80, 80, 0, 255],
        min: [10, 10, 0, 0],
        speed: [2, 2, 0, 2],
        phase: [0, 0, 0, 128],
        mode: 0,
    };
}

#[derive(Clone, Copy, Debug)]
pub struct Registers {
    pub settings: Settings,
    pub debug: u8,
    save: u8,
    pointer: u8,
}

impl Registers {
    pub const fn new() -> Self {
        Self {
            settings: Settings::DEFAULT,
            debug: ERR_NONE,
            save: 0,
            pointer: 0,
        }
    }

    /// The byte at one register address.
    pub fn read(&self, addr: u8) -> u8 {
        let s = &self.settings;
        match addr {
            0x00..=0xEB => DOCS.get(addr as usize).copied().unwrap_or(0),
            0xEC..=0xEF => s.max[(addr - REG_MAX) as usize],
            0xF0..=0xF3 => s.min[(addr - REG_MIN) as usize],
            0xF4..=0xF7 => s.speed[(addr - REG_SPEED) as usize],
            0xF8..=0xFB => s.phase[(addr - REG_PHASE) as usize],
            REG_MODE => s.mode,
            REG_SAVE => self.save,
            REG_DEBUG => self.debug,
            _ => 0,
        }
    }

    fn write_one(&mut self, addr: u8, value: u8) {
        let s = &mut self.settings;
        match addr {
            0xEC..=0xEF => s.max[(addr - REG_MAX) as usize] = value,
            0xF0..=0xF3 => s.min[(addr - REG_MIN) as usize] = value,
            0xF4..=0xF7 => s.speed[(addr - REG_SPEED) as usize] = value,
            0xF8..=0xFB => s.phase[(addr - REG_PHASE) as usize] = value,
            // bit 4 (UV LED detected) is read-only and always 0 here
            REG_MODE => s.mode = value & 0x03,
            REG_SAVE => self.save = value,
            REG_DEBUG => self.debug = value,
            _ => {} // docs text and 0xFF: read-only
        }
    }

    /// Handle one I2C write: the register address, then data bytes.
    pub fn on_write(&mut self, bytes: &[u8]) {
        let Some((&addr, data)) = bytes.split_first() else {
            return;
        };
        self.pointer = addr;
        for &value in data {
            self.write_one(self.pointer, value);
            self.pointer = self.pointer.wrapping_add(1);
        }
        match self.save {
            SAVE_STORE => {
                self.save = 0;
                self.debug = ERR_SAVE_NOT_SUPPORTED;
            }
            SAVE_FACTORY_RESET => {
                self.save = 0;
                self.settings = Settings::DEFAULT;
                self.debug = ERR_NONE;
            }
            _ => {}
        }
    }

    /// Fill `out` with the bytes a badge gets when it reads now.
    pub fn read_into(&self, out: &mut [u8]) {
        let mut addr = self.pointer;
        for b in out.iter_mut() {
            *b = self.read(addr);
            addr = addr.wrapping_add(1);
        }
    }
}

impl Default for Registers {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maker_example_set_red_to_full_and_steady() {
        let mut r = Registers::new();
        r.on_write(&[0xEC, 0xFF]);
        r.on_write(&[0xF4, 0x00]);
        assert_eq!(r.settings.max[0], 255);
        assert_eq!(r.settings.speed[0], 0);
        assert_eq!(r.settings.max[1], 80, "other registers untouched");
    }

    #[test]
    fn write_auto_increments_and_read_starts_at_last_address() {
        let mut r = Registers::new();
        r.on_write(&[0xEC, 1, 2, 3, 4, 5]);
        assert_eq!(r.settings.max, [1, 2, 3, 4]);
        assert_eq!(r.settings.min[0], 5);
        r.on_write(&[0xEC]);
        let mut out = [0u8; 3];
        r.read_into(&mut out);
        assert_eq!(out, [1, 2, 3]);
    }

    #[test]
    fn docs_are_read_only_text() {
        let mut r = Registers::new();
        r.on_write(&[0x00, b'X']);
        r.on_write(&[0x00]);
        let mut out = [0u8; 4];
        r.read_into(&mut out);
        assert_eq!(&out, b"Duck");
        assert_eq!(r.read(0xEB), 0);
    }

    #[test]
    fn save_and_reset() {
        let mut r = Registers::new();
        r.on_write(&[REG_MAX, 1]);
        r.on_write(&[REG_SAVE, SAVE_STORE]);
        assert_eq!(r.read(REG_SAVE), 0);
        assert_eq!(r.read(REG_DEBUG), ERR_SAVE_NOT_SUPPORTED);
        assert_eq!(r.settings.max[0], 1);
        r.on_write(&[REG_SAVE, SAVE_FACTORY_RESET]);
        assert_eq!(r.settings, Settings::DEFAULT);
        assert_eq!(r.read(REG_DEBUG), ERR_NONE);
    }

    #[test]
    fn mode_keeps_only_the_control_bits() {
        let mut r = Registers::new();
        r.on_write(&[REG_MODE, 0xFF]);
        assert_eq!(r.read(REG_MODE), 0x03);
    }

    #[test]
    fn writes_past_the_end_are_ignored() {
        let mut r = Registers::new();
        r.on_write(&[0xFE, 7, 9, 9]);
        assert_eq!(r.read(REG_DEBUG), 7);
        assert_eq!(r.read(0xFF), 0);
        assert_eq!(r.read(0x00), b'D');
    }
}
