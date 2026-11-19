//! The two small pieces of board wiring the core crate cannot do itself:
//!
//! * [`PrivateBus`]: the private I2C lines (SDA = D0, SCL = D8) as open-drain
//!   pins for `tars_core::bitbang` (the touch chip and the second Qwiic
//!   socket). The board's 1.3 kOhm resistors R11/R12 pull them up; the
//!   internal pull-ups stay off. Same approach as Do Or Donut's driver bus.
//! * [`Display`]: the ST7735S on SPI (clock D7, data D3) with its
//!   data/command line on D6. Its chip-select is wired to ground.

use esp_hal::{
    Blocking,
    delay::Delay,
    gpio::{DriveMode, Flex, InputConfig, Output, OutputConfig, Pin, Pull},
    spi::master::Spi,
};
use tars_core::{bitbang::Lines, gfx::Frame, st7735};

/// Half an I2C clock period: about 100-150 kHz with the code around it,
/// well inside the touch chip's 400 kHz. Not measured.
const HALF_BIT_US: u32 = 3;

pub struct PrivateBus<'d> {
    sda: Flex<'d>,
    scl: Flex<'d>,
    delay: Delay,
}

fn open_drain<'d>(pin: impl Pin + 'd) -> Flex<'d> {
    let mut f = Flex::new(pin);
    f.set_high();
    f.apply_output_config(&OutputConfig::default().with_drive_mode(DriveMode::OpenDrain));
    f.apply_input_config(&InputConfig::default().with_pull(Pull::None));
    f.set_input_enable(true);
    f.set_output_enable(true);
    f
}

impl<'d> PrivateBus<'d> {
    pub fn new(sda: impl Pin + 'd, scl: impl Pin + 'd) -> Self {
        Self { sda: open_drain(sda), scl: open_drain(scl), delay: Delay::new() }
    }
}

impl Lines for PrivateBus<'_> {
    fn set_sda(&mut self, high: bool) {
        if high { self.sda.set_high() } else { self.sda.set_low() }
    }
    fn set_scl(&mut self, high: bool) {
        if high { self.scl.set_high() } else { self.scl.set_low() }
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

pub struct Display<'d> {
    spi: Spi<'d, Blocking>,
    dc: Output<'d>,
    delay: Delay,
    buf: [u8; 1024],
}

impl<'d> Display<'d> {
    pub fn new(spi: Spi<'d, Blocking>, dc: Output<'d>) -> Self {
        Self { spi, dc, delay: Delay::new(), buf: [0; 1024] }
    }

    fn command(&mut self, cmd: u8, data: &[u8]) {
        self.dc.set_low();
        let _ = self.spi.write(&[cmd]);
        if !data.is_empty() {
            self.dc.set_high();
            let _ = self.spi.write(data);
        }
    }

    /// The start-up sequence. There is no reset pin (the board resets the
    /// display at power-up with R16/C1), so it starts with a software reset.
    pub fn init(&mut self) {
        for s in st7735::INIT {
            self.command(s.cmd, s.data);
            if s.wait_ms > 0 {
                self.delay.delay_millis(s.wait_ms);
            }
        }
    }

    /// Send a whole frame.
    pub fn show(&mut self, frame: &Frame) {
        for (cmd, data) in st7735::window(0, 0, tars_core::gfx::WIDTH as u16 - 1, tars_core::gfx::HEIGHT as u16 - 1) {
            self.command(cmd, &data);
        }
        self.command(st7735::RAMWR, &[]);
        self.dc.set_high();
        let Self { spi, buf, .. } = self;
        frame.for_each_chunk(buf, |chunk| {
            let _ = spi.write(chunk);
        });
    }

    /// Put the controller to sleep (the backlight is wired to the supply and
    /// stays lit while the board has power: see README).
    pub fn sleep(&mut self) {
        self.command(0x28, &[]); // display off
        self.command(0x10, &[]); // sleep in
    }
}
