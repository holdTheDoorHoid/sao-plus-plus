//! The two pins of the private LED-driver bus (SDA = D10, SCL = D3), as
//! open-drain lines for the software I2C controller in
//! `donut_core::bitbang`.
//!
//! Why software I2C at all: the ESP32-C3 has a single I2C peripheral and it
//! is busy being the badge's target on D4/D5 (see `i2c_target.rs`). The C6
//! and S3 use the same code so there is one path to test.
//!
//! The pins are open-drain outputs with their input buffers on, so the code
//! can read the real line level (for ACKs and to notice a stuck bus). The
//! internal pull-ups stay off: the board has 1.3 kOhm pull-ups (R4, R5) to
//! 3.3 V on both lines.

use donut_core::bitbang::OpenDrainLines;
use esp_hal::{
    delay::Delay,
    gpio::{DriveMode, Flex, InputConfig, OutputConfig, Pin, Pull},
};

/// Half a clock period. 2 us gives roughly 200-250 kHz with the code
/// overhead, under the IS31FL3731's 400 kHz limit. Not measured.
const HALF_BIT_US: u32 = 2;

pub struct DriverBus<'d> {
    sda: Flex<'d>,
    scl: Flex<'d>,
    delay: Delay,
}

fn open_drain<'d>(pin: impl Pin + 'd) -> Flex<'d> {
    let mut f = Flex::new(pin);
    // Released (high) before the driver is enabled, so no glitch.
    f.set_high();
    f.apply_output_config(&OutputConfig::default().with_drive_mode(DriveMode::OpenDrain));
    f.apply_input_config(&InputConfig::default().with_pull(Pull::None));
    f.set_input_enable(true);
    f.set_output_enable(true);
    f
}

impl<'d> DriverBus<'d> {
    pub fn new(sda: impl Pin + 'd, scl: impl Pin + 'd) -> Self {
        Self {
            sda: open_drain(sda),
            scl: open_drain(scl),
            delay: Delay::new(),
        }
    }
}

impl OpenDrainLines for DriverBus<'_> {
    fn set_sda(&mut self, high: bool) {
        if high {
            self.sda.set_high()
        } else {
            self.sda.set_low()
        }
    }
    fn set_scl(&mut self, high: bool) {
        if high {
            self.scl.set_high()
        } else {
            self.scl.set_low()
        }
    }
    fn sda(&mut self) -> bool {
        self.sda.is_high()
    }
    fn scl(&mut self) -> bool {
        self.scl.is_high()
    }
    fn delay(&mut self) {
        self.delay.delay_micros(HALF_BIT_US);
    }
}
