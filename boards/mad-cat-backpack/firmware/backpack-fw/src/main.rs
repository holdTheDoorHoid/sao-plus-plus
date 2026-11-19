//! Mad Cat Backpack (SAO++ edition) firmware for the Seeed Studio XIAO
//! ESP32-C3 / ESP32-C6 / ESP32-S3: animates the Mad Cat's eyes and teeth.
//!
//! The light show is the maker's: `mad_cat_backpack_v0.asm` by Peter Shabino
//! (Wireb), <https://github.com/Wireb/Mad_Cat_Backpack>, MIT licence,
//! Copyright (c) 2018 Peter Shabino. It is re-implemented in Rust from a
//! reading of his program, in the `backpack-core` crate, and unit-tested
//! there on the host.
//!
//! This file is the thin hardware layer: pins, LEDs, I2C, sleep. Pins, I2C,
//! sleep and panic handling follow the Mr. Robot and Do Or Donut firmware.
//!
//! No radio driver is linked: Wi-Fi and Bluetooth are never started, so they
//! draw nothing on badge power.

#![no_std]
#![no_main]

mod i2c_target;
mod leds;

use core::panic::PanicInfo;

use backpack_core::{
    VERSION_MAJOR, VERSION_MINOR,
    app::{App, Inputs, Output as AppOutput},
    i2c::ADDRESS,
};
use esp_hal::{
    clock::CpuClock,
    gpio::{AnyPin, Event, Input, InputConfig, Pull, WakeupConfig},
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    system::software_reset,
    time::Instant,
};
use esp_println::println;

use crate::leds::Leds;

esp_bootloader_esp_idf::esp_app_desc!();

/// Input-sampling / show step interval.
const TICK_MS: u32 = 2;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//   LED (index)          XIAO   C3      C6      S3
//   left eye    (0) D1   D8     GPIO8   GPIO19  GPIO7
//   right eye   (1) D2   D7     GPIO20  GPIO17  GPIO44
//   tooth 1     (2) D3   D9     GPIO9   GPIO20  GPIO8    (C3: also the BOOT button)
//   tooth 2     (3) D4   D10    GPIO10  GPIO18  GPIO9
//   tooth 3     (4) D5   D0     GPIO2   GPIO0   GPIO1
//   tooth 4     (5) D6   D2     GPIO4   GPIO2   GPIO3
//   tooth 5     (6) D7   D3     GPIO5   GPIO21  GPIO4
//   tooth 6     (7) D8   D6     GPIO21  GPIO16  GPIO43
//   I2C SDA              D4     GPIO6   GPIO22  GPIO5
//   I2C SCL              D5     GPIO7   GPIO23  GPIO6
//   OFF sense            D1     GPIO3   GPIO1   GPIO2
//   BOOT button          -      GPIO9   GPIO9   GPIO0
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            [
                AnyPin::from($p.GPIO8),
                AnyPin::from($p.GPIO20),
                AnyPin::from($p.GPIO9),
                AnyPin::from($p.GPIO10),
                AnyPin::from($p.GPIO2),
                AnyPin::from($p.GPIO4),
                AnyPin::from($p.GPIO5),
                AnyPin::from($p.GPIO21),
            ],
            $p.GPIO6,
            $p.GPIO7,
            $p.GPIO3,
            None::<AnyPin>,
        )
    };
}
#[cfg(feature = "esp32c3")]
const SDA_SCL_GPIO: (usize, usize) = (6, 7);
#[cfg(feature = "esp32c3")]
const CHIP: &str = "ESP32-C3";
/// LED index whose pin is also the BOOT button.
#[cfg(feature = "esp32c3")]
const SHARED_WITH_BOOT: Option<usize> = Some(2);

#[cfg(feature = "esp32c6")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            [
                AnyPin::from($p.GPIO19),
                AnyPin::from($p.GPIO17),
                AnyPin::from($p.GPIO20),
                AnyPin::from($p.GPIO18),
                AnyPin::from($p.GPIO0),
                AnyPin::from($p.GPIO2),
                AnyPin::from($p.GPIO21),
                AnyPin::from($p.GPIO16),
            ],
            $p.GPIO22,
            $p.GPIO23,
            $p.GPIO1,
            Some(AnyPin::from($p.GPIO9)),
        )
    };
}
#[cfg(feature = "esp32c6")]
const SDA_SCL_GPIO: (usize, usize) = (22, 23);
#[cfg(feature = "esp32c6")]
const CHIP: &str = "ESP32-C6";
#[cfg(feature = "esp32c6")]
const SHARED_WITH_BOOT: Option<usize> = None;

#[cfg(feature = "esp32s3")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            [
                AnyPin::from($p.GPIO7),
                AnyPin::from($p.GPIO44),
                AnyPin::from($p.GPIO8),
                AnyPin::from($p.GPIO9),
                AnyPin::from($p.GPIO1),
                AnyPin::from($p.GPIO3),
                AnyPin::from($p.GPIO4),
                AnyPin::from($p.GPIO43),
            ],
            $p.GPIO5,
            $p.GPIO6,
            $p.GPIO2,
            Some(AnyPin::from($p.GPIO0)),
        )
    };
}
#[cfg(feature = "esp32s3")]
const SDA_SCL_GPIO: (usize, usize) = (5, 6);
#[cfg(feature = "esp32s3")]
const CHIP: &str = "ESP32-S3";
#[cfg(feature = "esp32s3")]
const SHARED_WITH_BOOT: Option<usize> = None;

fn now_us() -> u64 {
    Instant::now().duration_since_epoch().as_micros()
}

struct Board<'d> {
    leds: Leds<'d>,
    /// The BOOT button on its own pin (C6, S3). On the C3 it shares an LED pin.
    button: Option<Input<'d>>,
    off: Input<'d>,
    lpwr: LowPower<'d>,
    app: App,
    last_tick_ms: u32,
}

impl Board<'_> {
    /// Called continuously from the main loop: keeps the LED dimming going,
    /// and every TICK_MS samples the inputs and advances the show.
    fn idle(&mut self) {
        self.leds.service();
        let now = now_us();
        let now_ms = (now / 1000) as u32;
        if now_ms.wrapping_sub(self.last_tick_ms) < TICK_MS {
            return;
        }
        self.step(now);
    }

    fn step(&mut self, now: u64) {
        self.last_tick_ms = (now / 1000) as u32;
        let button_down = match &self.button {
            Some(b) => b.is_low(), // BOOT button: active low
            None => self.leds.shared_button_down(),
        };
        let inputs = Inputs {
            button_down,
            off_selected: self.off.is_high(), // switch ties D1 to 3.3 V in OFF
        };
        match self.app.tick(now, inputs) {
            AppOutput::Leds(levels) => self.leds.set(levels),
            AppOutput::PowerOff => self.power_off(),
        }
    }

    /// A badge write: act on it at once.
    fn on_write(&mut self, bytes: &[u8]) {
        let now = now_us();
        if self.app.on_i2c_write(bytes, now) > 0 {
            self.step(now);
        }
    }

    /// All LEDs dark, then deep sleep until the switch leaves OFF. Waking from
    /// deep sleep resets the chip, so this never returns.
    fn power_off(&mut self) -> ! {
        self.leds.blank_and_hold();
        println!("off: deep sleep until D1 goes low");
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
            software_reset();
        }
        self.lpwr.sleep_deep_with_rejection(RtcSleepConfig::deep());
        software_reset()
    }
}

#[esp_hal::main]
fn main() -> ! {
    // 80 MHz is plenty for eight LEDs and keeps the module's own draw low on badge power.
    let peripherals = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let p = peripherals;
    let (led_pins, sda, scl, off_pin, button_pin) = board_pins!(p);

    // First of all: every LED pin high (LEDs dark), holds from the last power-off released.
    let leds = Leds::new(led_pins, SHARED_WITH_BOOT);

    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));
    let button = button_pin.map(|b| Input::new(b, InputConfig::default().with_pull(Pull::Up)));
    // Let the pull-down settle before the first read.
    let t0 = Instant::now();
    while t0.elapsed().as_micros() < 200 {}
    let off_at_boot = off.is_high();

    println!(
        "Mad Cat Backpack SAO++ firmware {}.{} on {} (I2C target 0x{:02X})",
        VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS
    );

    let mut board = Board {
        leds,
        button,
        off,
        lpwr: LowPower::new(p.LPWR),
        app: App::new(now_us(), off_at_boot),
        last_tick_ms: ((now_us() / 1000) as u32).wrapping_sub(TICK_MS),
    };

    run_i2c(&mut board, p.I2C0, sda, scl)
}

#[cfg(any(feature = "esp32c3", feature = "esp32c6"))]
fn run_i2c<'d>(
    board: &mut Board<'_>,
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
            Some(Ok(Command::Write(n))) => board.on_write(&rx[..n]),
            Some(Ok(Command::Read)) => {
                // The badge asked to read: answer with 4 status bytes. SCL is
                // being stretched until we do, so answer now, but never wait
                // more than 100 ms for the badge to finish.
                let status = board.app.status();
                let start = now_us();
                let _ = poll_with(
                    slave.respond_to_read_async(&status),
                    || board.idle(),
                    || now_us().wrapping_sub(start) > 100_000,
                );
            }
            // Bus timeout / arbitration loss: just listen again.
            Some(Err(_)) | None => {}
        }
    }
}

#[cfg(feature = "esp32s3")]
fn run_i2c<'d>(
    board: &mut Board<'_>,
    i2c: esp_hal::peripherals::I2C0<'d>,
    sda: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
    scl: impl esp_hal::gpio::interconnect::PeripheralInput<'d>
    + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
) -> ! {
    let mut target = i2c_target::s3::S3Target::new(i2c, sda, scl, ADDRESS);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.0);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.1);
    let mut queued = board.app.status();
    target.set_read_data(&queued);

    loop {
        if let Some(bytes) = target.poll() {
            board.on_write(bytes);
        }
        board.idle();
        // Keep the read answer current, but never swap it mid-transaction.
        let status = board.app.status();
        if status != queued && !target.bus_busy() {
            target.set_read_data(&status);
            queued = status;
        }
    }
}

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    println!("panic: {}", info);
    // A badge add-on should come back by itself rather than sit dark.
    software_reset()
}
