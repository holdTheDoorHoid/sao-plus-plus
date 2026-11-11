//! IS31FL3731 LED driver, over any `embedded_hal::i2c::I2c` bus.
//!
//! Register facts below were checked against the ISSI datasheet
//! "IS31FL3731 Audio Modulated Matrix LED Driver", Rev. D, 04/22/2013
//! (Table 2 command register, Table 3 register list, Table 7 frame register
//! addresses, Tables 8, 9, 12, 13, 16, 17 function registers):
//!
//! * Writing a page number to the command register 0xFD picks what the
//!   following register addresses mean: pages 0x00..=0x07 are frames 1..8,
//!   page 0x0B is the function registers.
//! * Frame page: 0x00..=0x11 LED on/off (18 bytes), 0x12..=0x23 blink
//!   enable (18 bytes), 0x24..=0xB3 PWM (144 bytes, 256 steps).
//! * Function page: 0x00 configuration (mode bits D4:D3, 00 = picture mode),
//!   0x01 picture display (frame shown in picture mode), 0x05 display option
//!   (blink enable), 0x06 audio sync, 0x08/0x09 breath control, 0x0A
//!   shutdown (bit 0: 0 = software shutdown, 1 = normal operation),
//!   0x0B AGC.
//! * The address pointer auto-increments after each data byte, so a whole
//!   page can be written in one transaction.
//! * Frame registers are "not assured" at power-on, so [`init`] writes all
//!   of frame 1 before switching the display on. All registers keep their
//!   values in software shutdown and can be written there.
//!
//! This firmware uses picture mode and frame 1 only. The chip's own
//! animation, blink, breath and audio features are switched off; all
//! animation happens in the XIAO.
//!
//! [`init`]: Is31fl3731::init

use embedded_hal::i2c::I2c;

use crate::LED_COUNT;
use crate::leds::led_control_bytes;

/// 7-bit address with the AD pin tied to ground (datasheet Table 1:
/// 11101 AD AD -> 0b1110100).
pub const ADDRESS: u8 = 0x74;

pub const REG_COMMAND: u8 = 0xFD;
pub const PAGE_FRAME_1: u8 = 0x00;
pub const PAGE_FUNCTION: u8 = 0x0B;

// Frame page.
pub const REG_LED_CONTROL: u8 = 0x00;
pub const REG_BLINK: u8 = 0x12;
pub const REG_PWM: u8 = 0x24;
pub const CONTROL_BYTES: usize = 18;

// Function page.
pub const REG_CONFIG: u8 = 0x00;
pub const REG_PICTURE_DISPLAY: u8 = 0x01;
pub const REG_AUTOPLAY_1: u8 = 0x02;
pub const REG_AUTOPLAY_2: u8 = 0x03;
pub const REG_DISPLAY_OPTION: u8 = 0x05;
pub const REG_AUDIO_SYNC: u8 = 0x06;
pub const REG_BREATH_1: u8 = 0x08;
pub const REG_BREATH_2: u8 = 0x09;
pub const REG_SHUTDOWN: u8 = 0x0A;
pub const REG_AGC: u8 = 0x0B;

pub const SHUTDOWN: u8 = 0x00;
pub const NORMAL_OPERATION: u8 = 0x01;
/// Configuration: picture mode (MODE = 00), frame-start bits unused.
pub const CONFIG_PICTURE_MODE: u8 = 0x00;

/// The function-page writes [`Is31fl3731::init`] does, in order, while the
/// chip is in software shutdown: (register, value).
pub const FUNCTION_SETUP: [(u8, u8); 9] = [
    (REG_CONFIG, CONFIG_PICTURE_MODE),
    (REG_PICTURE_DISPLAY, 0x00), // show frame 1
    (REG_AUTOPLAY_1, 0x00),
    (REG_AUTOPLAY_2, 0x00),
    (REG_DISPLAY_OPTION, 0x00), // blink off, per-frame intensity
    (REG_AUDIO_SYNC, 0x00),     // audio modulation off
    (REG_BREATH_1, 0x00),
    (REG_BREATH_2, 0x00), // breath off
    (REG_AGC, 0x00),
];

/// One write that fills all of frame 1, starting at register 0x00:
/// 18 LED on/off bytes, 18 blink bytes (all off), 144 PWM bytes.
pub fn full_frame_write(control: &[u8; CONTROL_BYTES], pwm: &[u8; LED_COUNT]) -> [u8; 181] {
    let mut buf = [0u8; 1 + 2 * CONTROL_BYTES + LED_COUNT];
    buf[0] = REG_LED_CONTROL;
    buf[1..1 + CONTROL_BYTES].copy_from_slice(control);
    // buf[19..37]: blink enables, left at 0.
    buf[1 + 2 * CONTROL_BYTES..].copy_from_slice(pwm);
    buf
}

/// One write that updates all 144 PWM registers (register 0x24 onwards).
pub fn pwm_write(pwm: &[u8; LED_COUNT]) -> [u8; 1 + LED_COUNT] {
    let mut buf = [0u8; 1 + LED_COUNT];
    buf[0] = REG_PWM;
    buf[1..].copy_from_slice(pwm);
    buf
}

pub struct Is31fl3731<I> {
    i2c: I,
    /// The page the command register points at, if known.
    page: Option<u8>,
}

impl<I: I2c> Is31fl3731<I> {
    pub const fn new(i2c: I) -> Self {
        Self { i2c, page: None }
    }

    pub fn release(self) -> I {
        self.i2c
    }

    fn select_page(&mut self, page: u8) -> Result<(), I::Error> {
        if self.page != Some(page) {
            self.page = None; // unknown until the write succeeds
            self.i2c.write(ADDRESS, &[REG_COMMAND, page])?;
            self.page = Some(page);
        }
        Ok(())
    }

    fn write_function(&mut self, reg: u8, value: u8) -> Result<(), I::Error> {
        self.select_page(PAGE_FUNCTION)?;
        self.i2c.write(ADDRESS, &[reg, value])
    }

    /// Bring the chip from any state to: picture mode, frame 1 shown, every
    /// LED enabled at the PWM values in `pwm` (chip order, see
    /// [`crate::leds::to_pwm_registers`]), display on.
    ///
    /// Order: shut down first (the matrix stays dark while registers are
    /// still random), configure, fill frame 1, then switch on.
    pub fn init(&mut self, pwm: &[u8; LED_COUNT]) -> Result<(), I::Error> {
        self.page = None;
        self.write_function(REG_SHUTDOWN, SHUTDOWN)?;
        for (reg, value) in FUNCTION_SETUP {
            self.write_function(reg, value)?;
        }
        self.select_page(PAGE_FRAME_1)?;
        self.i2c
            .write(ADDRESS, &full_frame_write(&led_control_bytes(), pwm))?;
        self.write_function(REG_SHUTDOWN, NORMAL_OPERATION)
    }

    /// Update the 144 PWM registers of frame 1 (chip order).
    pub fn write_pwm(&mut self, pwm: &[u8; LED_COUNT]) -> Result<(), I::Error> {
        self.select_page(PAGE_FRAME_1)?;
        self.i2c.write(ADDRESS, &pwm_write(pwm))
    }

    /// Software shutdown (`true`: matrix blanked, ~230 uA typ.) or normal
    /// operation (`false`). Registers keep their contents either way.
    pub fn set_shutdown(&mut self, shutdown: bool) -> Result<(), I::Error> {
        self.write_function(
            REG_SHUTDOWN,
            if shutdown { SHUTDOWN } else { NORMAL_OPERATION },
        )
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use embedded_hal::i2c::{ErrorKind, ErrorType, NoAcknowledgeSource, Operation};
    use std::vec::Vec;

    /// A model of the chip's register file, fed with the bytes of each write.
    pub struct ChipModel {
        pub command: u8,
        pub frames: [[u8; 0xB4]; 8],
        pub function: [u8; 0x0D],
        pub writes: Vec<Vec<u8>>,
        pub fail_after: Option<usize>,
    }

    impl ChipModel {
        pub fn new() -> Self {
            // Power-on: frame registers random (0xA5 here), function regs 0.
            Self {
                command: 0,
                frames: [[0xA5; 0xB4]; 8],
                function: [0; 0x0D],
                writes: Vec::new(),
                fail_after: None,
            }
        }

        pub fn apply(&mut self, bytes: &[u8]) {
            self.writes.push(bytes.to_vec());
            let (&reg, data) = bytes.split_first().expect("empty write");
            if reg == REG_COMMAND {
                assert_eq!(data.len(), 1);
                assert!(data[0] <= 7 || data[0] == PAGE_FUNCTION, "reserved page");
                self.command = data[0];
                return;
            }
            for (k, &b) in data.iter().enumerate() {
                let r = reg as usize + k;
                if self.command == PAGE_FUNCTION {
                    assert!(r < self.function.len() && r != 4, "bad function reg {r:#x}");
                    self.function[r] = b;
                } else {
                    assert!(r < 0xB4, "past the PWM registers: {r:#x}");
                    self.frames[self.command as usize][r] = b;
                }
            }
        }

        pub fn shutdown(&self) -> bool {
            self.function[REG_SHUTDOWN as usize] & 1 == 0
        }

        pub fn pwm(&self, frame: usize) -> &[u8] {
            &self.frames[frame][0x24..0xB4]
        }
    }

    impl ErrorType for ChipModel {
        type Error = ErrorKind;
    }

    impl I2c for ChipModel {
        fn transaction(&mut self, address: u8, ops: &mut [Operation<'_>]) -> Result<(), ErrorKind> {
            if address != ADDRESS {
                return Err(ErrorKind::NoAcknowledge(NoAcknowledgeSource::Address));
            }
            if self.fail_after.is_some_and(|n| self.writes.len() >= n) {
                return Err(ErrorKind::NoAcknowledge(NoAcknowledgeSource::Data));
            }
            for op in ops {
                match op {
                    Operation::Write(b) => self.apply(b),
                    Operation::Read(_) => panic!("driver never reads"),
                }
            }
            Ok(())
        }
    }

    fn ramp() -> [u8; LED_COUNT] {
        core::array::from_fn(|i| i as u8)
    }

    #[test]
    fn init_leaves_a_fully_defined_frame_1_and_display_on() {
        let mut d = Is31fl3731::new(ChipModel::new());
        d.init(&ramp()).unwrap();
        let chip = d.release();
        assert!(!chip.shutdown());
        assert_eq!(chip.function[REG_CONFIG as usize], CONFIG_PICTURE_MODE);
        assert_eq!(chip.function[REG_PICTURE_DISPLAY as usize], 0);
        assert_eq!(chip.function[REG_DISPLAY_OPTION as usize], 0);
        assert_eq!(chip.function[REG_BREATH_2 as usize], 0);
        assert_eq!(chip.function[REG_AUDIO_SYNC as usize], 0);
        assert_eq!(&chip.frames[0][0..18], &[0xFF; 18]);
        assert_eq!(&chip.frames[0][0x12..0x24], &[0; 18]);
        assert_eq!(chip.pwm(0), &ramp()[..]);
        // Frames 2..8 are never touched.
        assert!(chip.frames[1].iter().all(|&b| b == 0xA5));
    }

    #[test]
    fn init_shuts_down_first_and_switches_on_last() {
        let mut d = Is31fl3731::new(ChipModel::new());
        d.init(&ramp()).unwrap();
        let w = &d.release().writes;
        assert_eq!(w[0], [REG_COMMAND, PAGE_FUNCTION]);
        assert_eq!(w[1], [REG_SHUTDOWN, SHUTDOWN]);
        assert_eq!(w[w.len() - 1], [REG_SHUTDOWN, NORMAL_OPERATION]);
        assert_eq!(w[w.len() - 2], [REG_COMMAND, PAGE_FUNCTION]);
        // Exactly one big write, of 1 + 180 bytes, to frame 1.
        let big: Vec<_> = w.iter().filter(|b| b.len() > 2).collect();
        assert_eq!(big.len(), 1);
        assert_eq!(big[0].len(), 181);
    }

    #[test]
    fn pwm_updates_select_the_frame_page_once() {
        let mut d = Is31fl3731::new(ChipModel::new());
        d.init(&[0; LED_COUNT]).unwrap();
        let n = d.i2c.writes.len();
        d.write_pwm(&ramp()).unwrap();
        d.write_pwm(&[7; LED_COUNT]).unwrap();
        let chip = d.release();
        assert_eq!(chip.writes.len(), n + 3, "page select + two PWM writes");
        assert_eq!(chip.writes[n], [REG_COMMAND, PAGE_FRAME_1]);
        assert_eq!(chip.pwm(0), &[7; LED_COUNT][..]);
    }

    #[test]
    fn shutdown_and_wake_keep_the_picture() {
        let mut d = Is31fl3731::new(ChipModel::new());
        d.init(&ramp()).unwrap();
        d.set_shutdown(true).unwrap();
        assert!(d.i2c.shutdown());
        d.set_shutdown(false).unwrap();
        assert!(!d.i2c.shutdown());
        assert_eq!(d.i2c.pwm(0), &ramp()[..]);
        // And the next PWM write re-selects frame 1 after the function page.
        d.write_pwm(&[1; LED_COUNT]).unwrap();
        assert_eq!(d.i2c.pwm(0), &[1; LED_COUNT][..]);
    }

    #[test]
    fn a_failed_write_forgets_the_page() {
        let mut chip = ChipModel::new();
        chip.fail_after = Some(0);
        let mut d = Is31fl3731::new(chip);
        assert!(d.write_pwm(&[0; LED_COUNT]).is_err());
        assert_eq!(d.page, None);
        d.i2c.fail_after = None;
        d.write_pwm(&[3; LED_COUNT]).unwrap();
        assert_eq!(d.i2c.writes[0], [REG_COMMAND, PAGE_FRAME_1]);
    }

    #[test]
    fn address_is_0x74() {
        assert_eq!(ADDRESS, 0b1110100);
    }
}
