//! Do Or Donut SAO (SAO++ edition) firmware for the Seeed Studio XIAO
//! ESP32-C3 / ESP32-C6 / ESP32-S3.
//!
//! The board is by davedarko (Dave Darko), 2019,
//! <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Do%20Or%20DoNut>.
//! He published no firmware; this is new.
//!
//! This file is the thin hardware layer: pins, the LED driver bus, the badge
//! I2C, sleep. All the behaviour (animations, modes, I2C commands,
//! debouncing, the current cap, the IS31FL3731 register sequence and the
//! software I2C protocol) lives in the `donut-core` crate and is unit-tested
//! on the host. The structure, the badge I2C code, sleep and panic handling
//! are the Mysterio / Hack-Man firmware's; the LED side is new.

#![no_std]
#![no_main]

mod driver_bus;
mod i2c_target;

use core::panic::PanicInfo;

use donut_core::{
    Frame, LED_COUNT, VERSION_MAJOR, VERSION_MINOR,
    app::{App, Inputs, Output as AppOutput},
    bitbang::BitBangI2c,
    i2c::ADDRESS,
    is31fl3731::{self, Is31fl3731},
    leds::to_pwm_registers,
};
use esp_hal::{
    clock::CpuClock,
    gpio::{Event, Input, InputConfig, Pull, WakeupConfig},
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    system::software_reset,
    time::Instant,
};
use esp_println::println;

use crate::driver_bus::DriverBus;

esp_bootloader_esp_idf::esp_app_desc!();

/// Frame / input-sampling interval. One full LED update takes roughly
/// 6-7 ms on the software bus, so 20 ms (50 frames a second) leaves the
/// main loop free most of the time.
const FRAME_MS: u32 = 20;

/// If the LED driver does not answer, try to set it up again this often.
const DRIVER_RETRY_MS: u32 = 1_000;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//                     C3      C6      S3
//   D10 driver SDA    GPIO10  GPIO18  GPIO9
//   D3  driver SCL    GPIO5   GPIO21  GPIO4
//   D4  badge SDA     GPIO6   GPIO22  GPIO5
//   D5  badge SCL     GPIO7   GPIO23  GPIO6
//   D1  OFF sense     GPIO3   GPIO1   GPIO2
//   BOOT button       GPIO9   GPIO9   GPIO0
//   D7  SAO GPIO1     GPIO20  GPIO17  GPIO44   (unused, input)
//   D6  SAO GPIO2     GPIO21  GPIO16  GPIO43   (unused, input)
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            $p.GPIO10, $p.GPIO5, $p.GPIO6, $p.GPIO7, $p.GPIO3, $p.GPIO9, $p.GPIO20, $p.GPIO21,
        )
    };
}
#[cfg(feature = "esp32c3")]
const SDA_SCL_GPIO: (usize, usize) = (6, 7);
#[cfg(feature = "esp32c3")]
const CHIP: &str = "ESP32-C3";

#[cfg(feature = "esp32c6")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            $p.GPIO18, $p.GPIO21, $p.GPIO22, $p.GPIO23, $p.GPIO1, $p.GPIO9, $p.GPIO17, $p.GPIO16,
        )
    };
}
#[cfg(feature = "esp32c6")]
const SDA_SCL_GPIO: (usize, usize) = (22, 23);
#[cfg(feature = "esp32c6")]
const CHIP: &str = "ESP32-C6";

#[cfg(feature = "esp32s3")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            $p.GPIO9, $p.GPIO4, $p.GPIO5, $p.GPIO6, $p.GPIO2, $p.GPIO0, $p.GPIO44, $p.GPIO43,
        )
    };
}
#[cfg(feature = "esp32s3")]
const SDA_SCL_GPIO: (usize, usize) = (5, 6);
#[cfg(feature = "esp32s3")]
const CHIP: &str = "ESP32-S3";

fn now_ms() -> u32 {
    Instant::now().duration_since_epoch().as_millis() as u32
}

type Driver<'d> = Is31fl3731<BitBangI2c<DriverBus<'d>>>;

/// The LED driver chip and what we last sent it.
struct Leds<'d> {
    driver: Option<Driver<'d>>,
    /// Set up and answering.
    ready: bool,
    last_try: Option<u32>,
    /// PWM registers last written successfully (chip order).
    sent: Option<[u8; LED_COUNT]>,
}

impl<'d> Leds<'d> {
    fn new(bus: DriverBus<'d>) -> Self {
        Self {
            driver: Some(Is31fl3731::new(BitBangI2c::new(bus))),
            ready: false,
            last_try: None,
            sent: None,
        }
    }

    fn driver(&mut self) -> &mut Driver<'d> {
        self.driver.as_mut().expect("driver present")
    }

    /// Clear a half-finished transfer, then run the full init sequence.
    fn setup(&mut self, regs: &[u8; LED_COUNT]) -> bool {
        let mut bb = self.driver.take().expect("driver present").release();
        if bb.recover().is_err() {
            println!("LED bus: SDA or SCL held low");
        }
        let mut d = Is31fl3731::new(bb);
        let ok = d.init(regs).is_ok();
        self.driver = Some(d);
        ok
    }

    fn show(&mut self, frame: &Frame, now: u32) {
        let regs = to_pwm_registers(frame);
        if !self.ready {
            if self
                .last_try
                .is_some_and(|t| now.wrapping_sub(t) < DRIVER_RETRY_MS)
            {
                return;
            }
            self.last_try = Some(now);
            self.ready = self.setup(&regs);
            if self.ready {
                println!(
                    "LED driver IS31FL3731 ready at 0x{:02X}",
                    is31fl3731::ADDRESS
                );
                self.sent = Some(regs);
            } else {
                println!("LED driver did not answer at 0x{:02X}", is31fl3731::ADDRESS);
            }
            return;
        }
        if self.sent == Some(regs) {
            return;
        }
        match self.driver().write_pwm(&regs) {
            Ok(()) => self.sent = Some(regs),
            Err(e) => {
                println!("LED driver write failed: {:?}", e);
                self.ready = false;
                self.sent = None;
            }
        }
    }

    /// Blank all LEDs and put the chip in software shutdown.
    fn off(&mut self) {
        let d = self.driver();
        if d.write_pwm(&[0; LED_COUNT]).is_err() || d.set_shutdown(true).is_err() {
            println!("LED driver did not take the shutdown");
        }
    }
}

struct Board<'d> {
    leds: Leds<'d>,
    button: Input<'d>,
    off: Input<'d>,
    lpwr: LowPower<'d>,
    app: App,
    last_frame: u32,
}

impl Board<'_> {
    /// Called continuously from the main loop. Every FRAME_MS it samples the
    /// inputs, advances the app and sends a frame.
    fn idle(&mut self) {
        let now = now_ms();
        if now.wrapping_sub(self.last_frame) < FRAME_MS {
            return;
        }
        self.last_frame = now;
        let inputs = Inputs {
            button_down: self.button.is_low(), // BOOT button: active low
            off_selected: self.off.is_high(),  // switch ties D1 to 3.3 V in OFF
        };
        match self.app.tick(now, inputs) {
            AppOutput::Show(frame) => self.leds.show(&frame, now),
            AppOutput::PowerOff => self.power_off(),
        }
    }

    /// Blank the LEDs, shut the driver down and go to deep sleep until the
    /// switch leaves OFF. Waking from deep sleep resets the chip, so this
    /// never returns.
    fn power_off(&mut self) -> ! {
        println!("off: LEDs blank, driver shut down, deep sleep until D1 goes low");
        self.leds.off();

        // Wake when D1 goes low (switch moved out of OFF). The internal
        // pull-down stays on during sleep and keeps the pad low when the
        // switch no longer drives it.
        self.off.listen(Event::LowLevel);
        if self
            .off
            .apply_wakeup_config(&WakeupConfig::default().with_low_power_path(true))
            .is_err()
        {
            println!("off pin cannot wake from deep sleep; resetting instead");
            software_reset();
        }
        if self.off.is_low() {
            // Switched back on while we were getting ready.
            software_reset();
        }
        // Returns only if the hardware rejects the sleep because the wake
        // condition is already true: then just start again.
        self.lpwr.sleep_deep_with_rejection(RtcSleepConfig::deep());
        software_reset()
    }
}

#[esp_hal::main]
fn main() -> ! {
    // 80 MHz is plenty and saves power over 160/240 MHz (and the current
    // budget assumes it).
    let peripherals = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let p = peripherals;
    let (drv_sda, drv_scl, sda, scl, off_pin, button_pin, sao1, sao2) = board_pins!(p);

    // Unused SAO GPIO pins: plain inputs, no pulls, never driven.
    let _sao1 = Input::new(sao1, InputConfig::default().with_pull(Pull::None));
    let _sao2 = Input::new(sao2, InputConfig::default().with_pull(Pull::None));

    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));
    let button = Input::new(button_pin, InputConfig::default().with_pull(Pull::Up));
    // Let the pull-down settle before the first read.
    let t0 = Instant::now();
    while t0.elapsed().as_micros() < 200 {}
    let off_at_boot = off.is_high();

    let leds = Leds::new(DriverBus::new(drv_sda, drv_scl));

    println!(
        "Do Or Donut SAO++ firmware {}.{} on {} (I2C target 0x{:02X})",
        VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS
    );

    let mut board = Board {
        leds,
        button,
        off,
        lpwr: LowPower::new(p.LPWR),
        app: App::new(now_ms(), off_at_boot),
        last_frame: now_ms().wrapping_sub(FRAME_MS),
    };

    run_i2c(&mut board, p.I2C0, sda, scl)
}

#[cfg(any(feature = "esp32c3", feature = "esp32c6"))]
fn run_i2c<'d>(
    board: &mut Board<'d>,
    i2c: esp_hal::peripherals::I2C0<'d>,
    sda: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
    scl: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
) -> ! {
    use esp_hal::i2c::slave::{Command, Config, I2cSlave};
    use i2c_target::poll_with;

    let mut slave = I2cSlave::new(i2c, Config::new(ADDRESS))
        .expect("I2C target init")
        .with_sda(sda)
        .with_scl(scl)
        .into_async();
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.0);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.1);

    let mut rx = [0u8; 32];
    loop {
        let heard = poll_with(slave.listen_async(&mut rx), || board.idle(), || false);
        match heard {
            Some(Ok(Command::Write(n))) => {
                board.app.on_i2c_write(&rx[..n], now_ms());
            }
            Some(Ok(Command::Read)) => {
                // The badge asked to read: answer with 4 status bytes. SCL is
                // being stretched until we do, so answer now, but never wait
                // more than 100 ms for the badge to finish.
                let status = board.app.status();
                let start = now_ms();
                let _ = poll_with(
                    slave.respond_to_read_async(&status),
                    || board.idle(),
                    || now_ms().wrapping_sub(start) > 100,
                );
            }
            // Bus timeout / arbitration loss: just listen again.
            Some(Err(_)) | None => {}
        }
    }
}

#[cfg(feature = "esp32s3")]
fn run_i2c<'d>(
    board: &mut Board<'d>,
    i2c: esp_hal::peripherals::I2C0<'d>,
    sda: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
    scl: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
) -> ! {
    let mut target = i2c_target::s3::S3Target::new(i2c, sda, scl, ADDRESS);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.0);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.1);
    target.set_read_data(&board.app.status());

    loop {
        if let Some(bytes) = target.poll() {
            board.app.on_i2c_write(bytes, now_ms());
            let status = board.app.status();
            target.set_read_data(&status);
        }
        board.idle();
    }
}

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    println!("panic: {}", info);
    // A badge add-on should come back by itself rather than sit dark.
    software_reset()
}
