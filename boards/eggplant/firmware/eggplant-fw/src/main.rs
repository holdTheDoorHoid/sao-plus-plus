//! Eggplant SAO (SAO++ edition) firmware for the Seeed Studio XIAO
//! ESP32-C3 / ESP32-C6 / ESP32-S3.
//!
//! The behaviour is a Rust re-implementation of the maker's ATtiny85 sketch
//! (Krux, DC Darknet, DEF CON 26; MIT; kept in ../../original/firmware) and
//! lives in the `eggplant-core` crate. This file is the thin hardware layer:
//! pins, LEDs, I2C, sleep. It is the Hack-Man board's hardware layer with the
//! I2C read path changed (this board answers every read with a fresh reply).
//!
//! NEVER COMPILED: no Rust toolchain was available where this was written.

#![no_std]
#![no_main]

mod i2c_target;
mod leds;

use core::panic::PanicInfo;

use eggplant_core::{ADDRESS, App, Inputs, LED_COUNT, Output as AppOutput, Rgb, VERSION_MAJOR, VERSION_MINOR};
use esp_hal::{
    clock::CpuClock,
    gpio::{Event, Input, InputConfig, Level, Output, OutputConfig, Pull, WakeupConfig},
    rmt::Rmt,
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    system::software_reset,
    time::{Instant, Rate},
};
use esp_println::println;

use crate::leds::Leds;

esp_bootloader_esp_idf::esp_app_desc!();

/// Frame / input-sampling interval.
const FRAME_MS: u32 = 10;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//                 C3      C6      S3
//   D10 LED data  GPIO10  GPIO18  GPIO9
//   D4  I2C SDA   GPIO6   GPIO22  GPIO5
//   D5  I2C SCL   GPIO7   GPIO23  GPIO6
//   D1  OFF sense GPIO3   GPIO1   GPIO2
//   BOOT button   GPIO9   GPIO9   GPIO0
//   D7            GPIO20  GPIO17  GPIO44   (not wired on this board, input)
//   D6            GPIO21  GPIO16  GPIO43   (not wired on this board, input)
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        (
            $p.GPIO10, $p.GPIO6, $p.GPIO7, $p.GPIO3, $p.GPIO9, $p.GPIO20, $p.GPIO21,
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
            $p.GPIO18, $p.GPIO22, $p.GPIO23, $p.GPIO1, $p.GPIO9, $p.GPIO17, $p.GPIO16,
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
            $p.GPIO9, $p.GPIO5, $p.GPIO6, $p.GPIO2, $p.GPIO0, $p.GPIO44, $p.GPIO43,
        )
    };
}
#[cfg(feature = "esp32s3")]
const SDA_SCL_GPIO: (usize, usize) = (5, 6);
#[cfg(feature = "esp32s3")]
const CHIP: &str = "ESP32-S3";

/// The LED data pin again, for the power-off path (the RMT channel holds the
/// original). Only used right before deep sleep, after the last frame.
fn steal_led_pin() -> esp_hal::gpio::AnyPin<'static> {
    // SAFETY: called once, after the final RMT transmission has completed;
    // the RMT channel is never used again (deep sleep follows, then reset).
    unsafe {
        #[cfg(feature = "esp32c3")]
        let p = esp_hal::peripherals::GPIO10::steal();
        #[cfg(feature = "esp32c6")]
        let p = esp_hal::peripherals::GPIO18::steal();
        #[cfg(feature = "esp32s3")]
        let p = esp_hal::peripherals::GPIO9::steal();
        p.into()
    }
}

fn now_ms() -> u32 {
    Instant::now().duration_since_epoch().as_millis() as u32
}

fn now_us() -> u32 {
    Instant::now().duration_since_epoch().as_micros() as u32
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
        match self.app.tick(inputs) {
            AppOutput::Show(frame) => self.leds.write(&frame),
            AppOutput::PowerOff => self.power_off(),
        }
    }

    /// Blank the LEDs and go to deep sleep until the switch leaves OFF.
    /// Waking from deep sleep resets the chip, so this never returns.
    fn power_off(&mut self) -> ! {
        println!("off: deep sleep until D1 goes low");
        self.leds.write(&[Rgb::OFF; LED_COUNT]);

        // Hold the LED data line low through the sleep, so noise on a floating
        // line cannot clock random colours into the LEDs.
        let mut data = Output::new(steal_led_pin(), Level::Low, OutputConfig::default());
        data.set_pad_hold(true);

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
    // 80 MHz is plenty for five LEDs and saves power over 160/240 MHz.
    let peripherals = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let p = peripherals;
    let (led_pin, sda, scl, off_pin, button_pin, sao1, sao2) = board_pins!(p);

    // D6 / D7 are not connected on this board (the maker's had a 4-pin
    // header, so the SAO GPIO pins stay unconnected): plain inputs, never driven.
    let _sao1 = Input::new(sao1, InputConfig::default().with_pull(Pull::None));
    let _sao2 = Input::new(sao2, InputConfig::default().with_pull(Pull::None));

    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));
    let button = Input::new(button_pin, InputConfig::default().with_pull(Pull::Up));
    // Let the pull-down settle before the first read.
    let t0 = Instant::now();
    while t0.elapsed().as_micros() < 200 {}

    let rmt = Rmt::new(p.RMT, Rate::from_mhz(leds::RMT_MHZ)).expect("RMT init");
    let leds = Leds::new(rmt.channel0, led_pin);

    println!(
        "Eggplant SAO++ firmware {}.{} on {} (I2C target 0x{:02X})",
        VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS
    );

    let mut board = Board {
        leds,
        button,
        off,
        lpwr: LowPower::new(p.LPWR),
        app: App::new(),
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
                board.app.on_i2c_write(&rx[..n]);
            }
            Some(Ok(Command::Read)) => {
                // The badge asked to read: carry out the command it wrote just
                // before and answer. The badge reads more bytes than most
                // answers have (up to 33), so the answer is padded with zeros.
                // SCL is being stretched until we answer, so answer now, but
                // never wait more than 100 ms for the badge to finish.
                let mut reply = [0u8; 33];
                let answer = board.app.on_i2c_read(now_us());
                reply[..answer.len()].copy_from_slice(answer);
                let start = now_ms();
                let _ = poll_with(
                    slave.respond_to_read_async(&reply),
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
    // No clock stretching on the S3, so the answer has to be waiting before
    // the badge reads: every write is carried out at once and its answer
    // queued. (On the C3 / C6, and on the maker's board, the command is
    // carried out when the badge reads.) A read with no write before it gets
    // the previous answer again. The S3's FIFO holds 32 bytes.
    let mut reply = [0u8; 32];
    loop {
        if let Some(bytes) = target.poll() {
            if !bytes.is_empty() {
                board.app.on_i2c_write(bytes);
                let answer = board.app.on_i2c_read(now_us());
                reply = [0u8; 32];
                reply[..answer.len()].copy_from_slice(answer);
            }
            target.set_read_data(&reply);
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
