//! The I2C register map, kept the same as the maker's so badge code written
//! for his duckGLOW boards works unchanged:
//!
//! | register | what |
//! |---|---|
//! | 0x00..=0xEB | text about the add-on (read only) |
//! | 0xEC..=0xEF | max brightness: red, green, blue, background |
//! | 0xF0..=0xF3 | min brightness, same order |
//! | 0xF4..=0xF7 | fading speed, same order (0 = steady at max) |
//! | 0xF8..=0xFB | phase (offset into the fade), same order |
//! | 0xFC | mode: bits 0-1 LED control 0 auto / 1 I2C / 2 WS2812; bit 4 LED type 0 RGB / 1 UV (read only) |
//! | 0xFD | save: write 42 to keep the settings over power-off, 24 for factory settings |
//! | 0xFE | debug: result of the last save (0 ok, 1 no saved settings, 2 flash error, 3 nothing to save) |
//!
//! A write is the register number followed by data bytes; the register
//! number counts up by one for every byte written or read, so several
//! registers can be written or read in one go. Reading uses the register
//! number set by the last write.

/// First register of each block.
pub const REG_DOCS: u8 = 0x00;
pub const REG_MAX: u8 = 0xEC;
pub const REG_MIN: u8 = 0xF0;
pub const REG_SPEED: u8 = 0xF4;
pub const REG_PHASE: u8 = 0xF8;
pub const REG_MODE: u8 = 0xFC;
pub const REG_SAVE: u8 = 0xFD;
pub const REG_DEBUG: u8 = 0xFE;

/// Registers that can be written (0xEC..=0xFD). The text below them and the
/// debug register above them are read only.
pub const FIRST_RW: u8 = REG_MAX;
pub const LAST_RW: u8 = REG_SAVE;
/// Number of registers (0x00..=0xFE), as on the maker's board. Reads past the
/// end return 0xFF; writes past the end are ignored.
pub const SIZE: usize = 0xFF;

/// Mode register bits.
pub const MODE_CTRL_MASK: u8 = 0x03;
pub const MODE_AUTO: u8 = 0;
pub const MODE_I2C: u8 = 1;
pub const MODE_WS2812: u8 = 2;
pub const MODE_UV: u8 = 0x10;

/// Save register commands.
pub const SAVE_PRESETS: u8 = 42;
pub const FACTORY_RESET: u8 = 24;

/// Debug register values (the maker's numbering).
pub const DBG_OK: u8 = 0;
pub const DBG_NO_PRESETS: u8 = 1;
pub const DBG_FLASH_ERROR: u8 = 2;
pub const DBG_UNCHANGED: u8 = 3;

/// Power-on settings, the maker's: a slow orange-ish breath on red and green,
/// blue off, background full and breathing half a cycle out of step.
pub const DEFAULT_MAX: [u8; 4] = [80, 80, 0, 255];
pub const DEFAULT_MIN: [u8; 4] = [10, 10, 0, 0];
pub const DEFAULT_SPEED: [u8; 4] = [2, 2, 0, 2];
pub const DEFAULT_PHASE: [u8; 4] = [0, 0, 0, 128];

/// The settings block that presets store: registers 0xEC..=0xFC (17 bytes).
pub const SETTINGS_LEN: usize = (REG_MODE - REG_MAX + 1) as usize;

pub struct Registers {
    data: [u8; SIZE],
    pointer: u8,
}

impl Registers {
    /// Factory settings and the docs text. `uv` is the detected LED type.
    pub fn new(uv: bool) -> Self {
        let mut r = Self { data: [0; SIZE], pointer: 0 };
        let text = docs_text();
        let n = text.len().min(FIRST_RW as usize - 1);
        r.data[..n].copy_from_slice(&text[..n]);
        r.factory(uv);
        r
    }

    /// Put the factory settings back (the text is not touched).
    pub fn factory(&mut self, uv: bool) {
        for ch in 0..4 {
            self.data[(REG_MAX as usize) + ch] = DEFAULT_MAX[ch];
            self.data[(REG_MIN as usize) + ch] = DEFAULT_MIN[ch];
            self.data[(REG_SPEED as usize) + ch] = DEFAULT_SPEED[ch];
            self.data[(REG_PHASE as usize) + ch] = DEFAULT_PHASE[ch];
        }
        if uv {
            // a UV LED sits on the blue position only: let it breathe, full range
            self.data[(REG_MAX + 2) as usize] = 255;
            self.data[(REG_MIN + 2) as usize] = 0;
            self.data[(REG_SPEED + 2) as usize] = 2;
        }
        self.data[REG_MODE as usize] = 0;
        self.data[REG_SAVE as usize] = 0;
        self.set_uv(uv);
    }

    pub fn get(&self, reg: u8) -> u8 {
        self.data.get(reg as usize).copied().unwrap_or(0xFF)
    }

    fn put(&mut self, reg: u8, v: u8) {
        if (FIRST_RW..=LAST_RW).contains(&reg) {
            self.data[reg as usize] = v;
        }
    }

    pub fn max(&self, ch: usize) -> u8 {
        self.get(REG_MAX + ch as u8)
    }
    pub fn min(&self, ch: usize) -> u8 {
        self.get(REG_MIN + ch as u8)
    }
    pub fn speed(&self, ch: usize) -> u8 {
        self.get(REG_SPEED + ch as u8)
    }
    pub fn phase(&self, ch: usize) -> u8 {
        self.get(REG_PHASE + ch as u8)
    }
    pub fn mode_ctrl(&self) -> u8 {
        self.get(REG_MODE) & MODE_CTRL_MASK
    }

    /// The LED-type bit is read only: whatever the badge writes, it shows what
    /// was detected at power-on.
    pub fn set_uv(&mut self, uv: bool) {
        let m = self.data[REG_MODE as usize];
        self.data[REG_MODE as usize] = if uv { m | MODE_UV } else { m & !MODE_UV };
    }

    /// Take the save command (if any) out of the save register.
    pub fn take_save(&mut self) -> u8 {
        core::mem::take(&mut self.data[REG_SAVE as usize])
    }

    pub fn set_debug(&mut self, v: u8) {
        self.data[REG_DEBUG as usize] = v;
    }

    /// One write transaction from the badge: the register number, then data.
    /// Returns the number of data bytes (0 for a write that only sets the
    /// register number before a read).
    pub fn write(&mut self, bytes: &[u8]) -> usize {
        let Some((&reg, data)) = bytes.split_first() else {
            return 0;
        };
        self.pointer = reg;
        for &b in data {
            self.put(self.pointer, b);
            self.pointer = self.pointer.wrapping_add(1);
        }
        data.len()
    }

    /// Fill `out` from the current register onwards (what a badge read gets).
    /// Call [`Registers::advance`] afterwards with the number actually read.
    pub fn read_into(&self, out: &mut [u8]) {
        let mut p = self.pointer;
        for o in out.iter_mut() {
            *o = self.get(p);
            p = p.wrapping_add(1);
        }
    }

    pub fn advance(&mut self, n: usize) {
        self.pointer = self.pointer.wrapping_add(n as u8);
    }

    pub fn pointer(&self) -> u8 {
        self.pointer
    }

    /// The settings block (0xEC..=0xFC) for saving.
    pub fn settings(&self) -> [u8; SETTINGS_LEN] {
        let mut s = [0; SETTINGS_LEN];
        s.copy_from_slice(&self.data[REG_MAX as usize..=REG_MODE as usize]);
        s
    }

    /// Load a saved settings block. The LED-type bit is set again afterwards.
    pub fn load_settings(&mut self, s: &[u8; SETTINGS_LEN], uv: bool) {
        self.data[REG_MAX as usize..=REG_MODE as usize].copy_from_slice(s);
        self.set_uv(uv);
    }
}

/// The text at register 0x00 (NUL-terminated, at most 235 bytes). The maker's
/// board carries a short poem here; this edition carries its own text instead.
pub fn docs_text() -> &'static [u8] {
    #[cfg(feature = "jaws")]
    const T: &[u8] = b"duckJAWS SAO, SAO++ edition. Design: Adrian Studer,\n\
github.com/astuder/duckGLOW (MIT). Firmware v0.1, XIAO ESP32.\n\
Registers: EC max, F0 min, F4 speed, F8 phase (R,G,B,background),\n\
FC mode, FD save (42 keep, 24 reset), FE debug.\n\0";
    #[cfg(not(feature = "jaws"))]
    const T: &[u8] = b"duckBATH SAO, SAO++ edition. Design: Adrian Studer,\n\
github.com/astuder/duckGLOW (MIT). Firmware v0.1, XIAO ESP32.\n\
Registers: EC max, F0 min, F4 speed, F8 phase (R,G,B,background),\n\
FC mode, FD save (42 keep, 24 reset), FE debug.\n\0";
    T
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn map_is_the_makers() {
        assert_eq!(REG_MAX, 0xEC);
        assert_eq!(REG_MIN, 0xF0);
        assert_eq!(REG_SPEED, 0xF4);
        assert_eq!(REG_PHASE, 0xF8);
        assert_eq!(REG_MODE, 0xFC);
        assert_eq!(REG_SAVE, 0xFD);
        assert_eq!(REG_DEBUG, 0xFE);
        assert_eq!(SETTINGS_LEN, 17);
    }

    #[test]
    fn docs_text_fits_and_is_terminated() {
        let t = docs_text();
        assert!(t.len() < FIRST_RW as usize, "{} bytes", t.len());
        assert_eq!(*t.last().unwrap(), 0);
        assert!(t.is_ascii());
        let r = Registers::new(false);
        let mut out = [0u8; 8];
        r.read_into(&mut out);
        assert_eq!(&out[..4], b"duck");
    }

    #[test]
    fn defaults() {
        let r = Registers::new(false);
        for ch in 0..4 {
            assert_eq!(r.max(ch), DEFAULT_MAX[ch]);
            assert_eq!(r.min(ch), DEFAULT_MIN[ch]);
            assert_eq!(r.speed(ch), DEFAULT_SPEED[ch]);
            assert_eq!(r.phase(ch), DEFAULT_PHASE[ch]);
        }
        assert_eq!(r.get(REG_MODE), 0);
        let u = Registers::new(true);
        assert_eq!((u.max(2), u.min(2), u.speed(2)), (255, 0, 2));
        assert_eq!(u.get(REG_MODE), MODE_UV);
    }

    #[test]
    fn write_with_auto_increment() {
        let mut r = Registers::new(false);
        assert_eq!(r.write(&[REG_MAX, 1, 2, 3, 4, 5]), 5);
        assert_eq!([r.max(0), r.max(1), r.max(2), r.max(3)], [1, 2, 3, 4]);
        assert_eq!(r.min(0), 5);
        assert_eq!(r.pointer(), REG_MIN + 1);
    }

    #[test]
    fn text_and_debug_are_read_only() {
        let mut r = Registers::new(false);
        r.write(&[0x00, b'X', b'Y']);
        assert_eq!(r.get(0), b'd');
        r.set_debug(3);
        r.write(&[REG_DEBUG, 0]);
        assert_eq!(r.get(REG_DEBUG), 3);
        // past the end: ignored, reads 0xFF
        r.write(&[0xFF, 9]);
        assert_eq!(r.get(0xFF), 0xFF);
    }

    #[test]
    fn uv_bit_is_read_only() {
        let mut r = Registers::new(true);
        r.write(&[REG_MODE, 0x02]);
        r.set_uv(true);
        assert_eq!(r.get(REG_MODE), 0x12);
        let mut r = Registers::new(false);
        r.write(&[REG_MODE, 0x13]);
        r.set_uv(false);
        assert_eq!(r.get(REG_MODE), 0x03);
    }

    #[test]
    fn read_from_pointer() {
        let mut r = Registers::new(false);
        assert_eq!(r.write(&[REG_MAX]), 0);
        let mut out = [0u8; 3];
        r.read_into(&mut out);
        assert_eq!(out, [80, 80, 0]);
        r.advance(3);
        r.read_into(&mut out[..1]);
        assert_eq!(out[0], 255);
    }

    #[test]
    fn settings_round_trip() {
        let mut r = Registers::new(false);
        r.write(&[REG_SPEED, 7, 8, 9, 10]);
        let s = r.settings();
        let mut q = Registers::new(false);
        q.load_settings(&s, false);
        assert_eq!(q.settings(), s);
        assert_eq!(q.speed(3), 10);
    }

    #[test]
    fn save_register_is_taken_once() {
        let mut r = Registers::new(false);
        r.write(&[REG_SAVE, SAVE_PRESETS]);
        assert_eq!(r.take_save(), 42);
        assert_eq!(r.take_save(), 0);
    }
}
