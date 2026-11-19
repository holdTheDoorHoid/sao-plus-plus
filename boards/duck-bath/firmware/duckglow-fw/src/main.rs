//! duckGLOW SAO (SAO++ edition: Duck Bath and Duck Jaws) firmware for the
//! Seeed Studio XIAO ESP32-C3 / ESP32-C6 / ESP32-S3.
//!
//! Behaviour and badge protocol follow the maker's firmware (`code/duckglow.c`
//! by Adrian Studer, <https://github.com/astuder/duckglow>, MIT licence,
//! Copyright (c) 2024 Adrian Studer). This is a clean re-implementation in
//! Rust, not a port of his code.
//!
//! This file is the thin hardware layer: LED PWM, I2C target, the WS2812
//! receiver on SAO GPIO2, the presets in flash, and sleep. The behaviour lives
//! in the `duckglow-core` crate and is unit-tested on the host.
//!
//! No radio driver is linked: Wi-Fi and Bluetooth are never started.

#![no_std]
#![no_main]

mod i2c_target;
mod leds;
mod presets_flash;
mod ws_rx;

use core::panic::PanicInfo;

use duckglow_core::{
    ADDRESS, BOARD, CHANNELS_USED, VERSION_MAJOR, VERSION_MINOR,
    app::{Action, App},
};
use esp_hal::{
    clock::CpuClock,
    gpio::{Event, Input, InputConfig, Pull, WakeupConfig},
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    system::software_reset,
    time::Instant,
};
use esp_println::println;

use crate::leds::Leds;

esp_bootloader_esp_idf::esp_app_desc!();

/// How often the app is stepped (fading itself runs every 20 ms).
const TICK_MS: u32 = 1;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//                         C3      C6      S3
//   D10 red   (low = on)  GPIO10  GPIO18  GPIO9
//   D8  green (low = on)  GPIO8   GPIO19  GPIO7
//   D7  blue  (low = on)  GPIO20  GPIO17  GPIO44
//   D0  background (Jaws) GPIO2   GPIO0   GPIO1
//   D4  I2C SDA           GPIO6   GPIO22  GPIO5
//   D5  I2C SCL           GPIO7   GPIO23  GPIO6
//   D1  OFF sense         GPIO3   GPIO1   GPIO2
//   D6  SAO GPIO2 (WS2812 in) GPIO21 GPIO16 GPIO43
//   SAO GPIO1 is not connected on these boards (D7 drives the blue LED).
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO10, $p.GPIO8, $p.GPIO20, $p.GPIO2, $p.GPIO6, $p.GPIO7, $p.GPIO3, $p.GPIO21)
    };
}
#[cfg(feature = "esp32c3")]
const SDA_SCL_GPIO: (usize, usize) = (6, 7);
#[cfg(feature = "esp32c3")]
const CHIP: &str = "ESP32-C3";

#[cfg(feature = "esp32c6")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO18, $p.GPIO19, $p.GPIO17, $p.GPIO0, $p.GPIO22, $p.GPIO23, $p.GPIO1, $p.GPIO16)
    };
}
#[cfg(feature = "esp32c6")]
const SDA_SCL_GPIO: (usize, usize) = (22, 23);
#[cfg(feature = "esp32c6")]
const CHIP: &str = "ESP32-C6";

#[cfg(feature = "esp32s3")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO9, $p.GPIO7, $p.GPIO44, $p.GPIO1, $p.GPIO5, $p.GPIO6, $p.GPIO2, $p.GPIO43)
    };
}
#[cfg(feature = "esp32s3")]
const SDA_SCL_GPIO: (usize, usize) = (5, 6);
#[cfg(feature = "esp32s3")]
const CHIP: &str = "ESP32-S3";

fn now_ms() -> u32 {
    Instant::now().duration_since_epoch().as_millis() as u32
}

struct Board<'d> {
    leds: Leds<'d>,
    off: Input<'d>,
    ws: ws_rx::WsReceiver<'d>,
    flash: presets_flash::Presets<'d>,
    lpwr: LowPower<'d>,
    app: App,
    last_tick: u32,
}

impl Board<'_> {
    /// Called continuously from the main loop.
    fn idle(&mut self) {
        // WS2812 frames: as soon as one has arrived
        if self.app.ws2812_wanted() {
            if let Some(frame) = self.ws.poll() {
                self.app.on_ws2812_frame(frame);
                self.leds.show(self.app.brightness());
            }
        }
        let now = now_ms();
        if now.wrapping_sub(self.last_tick) < TICK_MS {
            return;
        }
        self.last_tick = now;
        match self.app.tick(now, self.off.is_high()) {
            Action::None => {}
            Action::SavePresets(blob) => {
                let ok = self.flash.save(&blob);
                println!("presets saved: {}", ok);
                self.app.saved(ok);
            }
            Action::FactoryReset => {
                self.flash.erase();
                println!("factory reset");
                software_reset();
            }
            Action::PowerOff => self.power_off(),
        }
        self.leds.show(self.app.brightness());
    }

    fn on_write(&mut self, bytes: &[u8]) {
        self.app.on_i2c_write(bytes);
        self.leds.show(self.app.brightness());
    }

    /// LEDs dark and deep sleep until the switch leaves OFF. Waking from deep
    /// sleep resets the chip, so this never returns.
    fn power_off(&mut self) -> ! {
        self.leds.release();
        println!("off: deep sleep until D1 goes low");
        self.off.listen(Event::LowLevel);
        if self
            .off
            .apply_wakeup_config(&WakeupConfig::default().with_low_power_path(true))
            .is_err()
        {
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
    let peripherals = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let p = peripherals;
    let (red, green, blue, background, sda, scl, off_pin, sao2) = board_pins!(p);

    // LEDs dark first of all (all colour pins high = off)
    let mut ledc = esp_hal::ledc::Ledc::new(p.LEDC);
    let tmr = leds::timer(&mut ledc);
    let leds = Leds::new(&ledc, &tmr, red, green, blue, background);

    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));
    let t0 = Instant::now();
    while t0.elapsed().as_micros() < 200 {}
    let off_at_boot = off.is_high();

    let mut flash = presets_flash::Presets::new(p.FLASH);
    let mut stored = [0u8; duckglow_core::presets::BLOB_LEN];
    let have = flash.load(&mut stored);
    // The maker's board told a UV LED from an RGB one by testing the red pin;
    // the ESP32's input levels make that test unreliable, so the LED type is
    // a build option (see README).
    let uv = cfg!(feature = "uv");
    let app = App::new(now_ms(), uv, if have { Some(&stored[..]) } else { None }, off_at_boot);

    let ws = ws_rx::WsReceiver::new(p.RMT, sao2);

    println!(
        "{} SAO++ firmware {}.{} on {} (I2C target 0x{:02X}, {} LED channels)",
        BOARD, VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS, CHANNELS_USED
    );

    let mut board = Board {
        leds,
        off,
        ws,
        flash,
        lpwr: LowPower::new(p.LPWR),
        app,
        last_tick: now_ms().wrapping_sub(TICK_MS),
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

    let mut rx = [0u8; 40];
    let mut tx = [0u8; 255];
    loop {
        let heard = poll_with(slave.listen_async(&mut rx), || board.idle(), || false);
        match heard {
            Some(Ok(Command::Write(n))) => board.on_write(&rx[..n]),
            Some(Ok(Command::Read)) => {
                // Everything from the current register to the end; the badge
                // stops reading when it has what it wants. Never wait more than
                // 100 ms for it.
                let n = 255 - board.app.registers().pointer() as usize;
                let n = n.max(1);
                board.app.i2c_read(&mut tx[..n]);
                let start = now_ms();
                let _ = poll_with(
                    slave.respond_to_read_async(&tx[..n]),
                    || board.idle(),
                    || now_ms().wrapping_sub(start) > 100,
                );
            }
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
    let mut answer = [0u8; 32];
    board.app.i2c_read(&mut answer);
    target.set_read_data(&answer);
    loop {
        if let Some(bytes) = target.poll() {
            if !bytes.is_empty() {
                let mut copy = [0u8; 32];
                let n = bytes.len().min(32);
                copy[..n].copy_from_slice(&bytes[..n]);
                board.on_write(&copy[..n]);
                // the next read starts at the register just written (never swap mid-transaction)
                board.app.i2c_read(&mut answer);
                while target.bus_busy() {}
                target.set_read_data(&answer);
            }
        }
        board.idle();
    }
}

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    println!("panic: {}", info);
    software_reset()
}
