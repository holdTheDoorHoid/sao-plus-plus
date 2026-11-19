//! Eggplant SAO (SAO++ edition) firmware for the Seeed Studio XIAO ESP32-C3 /
//! ESP32-C6 / ESP32-S3.
//!
//! The behaviour is the maker's (Krux / DC Darknet, 2018, MIT): his light
//! shows, his I2C commands and his infection game, re-implemented in the
//! `eggplant-core` crate. This file is the thin hardware layer: pins, the two
//! LED channels, I2C, sleep. Its structure (I2C polling, sleep, panic) follows
//! the Mr. Robot firmware in this repository.
//!
//! No radio driver is linked: Wi-Fi and Bluetooth are never started, so they
//! draw nothing on badge power.

#![no_std]
#![no_main]

mod i2c_target;
mod leds;

use core::panic::PanicInfo;

use eggplant_core::{
    VERSION_MAJOR, VERSION_MINOR,
    app::{App, Inputs, Output as AppOutput},
    proto::ADDRESS,
};
use esp_hal::{
    clock::CpuClock,
    gpio::{DriveMode, Event, Input, InputConfig, Level, Output, OutputConfig, Pull, WakeupConfig},
    ledc::{
        LSGlobalClkSource, Ledc, LowSpeed,
        channel::{self, ChannelIFace},
        timer::TimerIFace,
    },
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    system::software_reset,
    time::Instant,
};
use esp_println::println;

use crate::leds::Leds;

esp_bootloader_esp_idf::esp_app_desc!();

/// Input sampling interval (the light show keeps its own 1 ms clock).
const TICK_US: u32 = 500;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//                 C3      C6      S3
//   D2  red LEDs  GPIO4   GPIO2   GPIO3    (high = on, through 1.3 k each)
//   D3  blue LEDs GPIO5   GPIO21  GPIO4    (high = on, through 330 ohm each)
//   D4  I2C SDA   GPIO6   GPIO22  GPIO5
//   D5  I2C SCL   GPIO7   GPIO23  GPIO6
//   D1  OFF sense GPIO3   GPIO1   GPIO2
//   BOOT button   GPIO9   GPIO9   GPIO0
//   D7  SAO GPIO1 GPIO20  GPIO17  GPIO44   (unused, input)
//   D6  SAO GPIO2 GPIO21  GPIO16  GPIO43   (unused, input)
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO4, $p.GPIO5, $p.GPIO6, $p.GPIO7, $p.GPIO3, $p.GPIO9, $p.GPIO20, $p.GPIO21)
    };
}
#[cfg(feature = "esp32c3")]
const SDA_SCL_GPIO: (usize, usize) = (6, 7);
#[cfg(feature = "esp32c3")]
const CHIP: &str = "ESP32-C3";

#[cfg(feature = "esp32c6")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO2, $p.GPIO21, $p.GPIO22, $p.GPIO23, $p.GPIO1, $p.GPIO9, $p.GPIO17, $p.GPIO16)
    };
}
#[cfg(feature = "esp32c6")]
const SDA_SCL_GPIO: (usize, usize) = (22, 23);
#[cfg(feature = "esp32c6")]
const CHIP: &str = "ESP32-C6";

#[cfg(feature = "esp32s3")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO3, $p.GPIO4, $p.GPIO5, $p.GPIO6, $p.GPIO2, $p.GPIO0, $p.GPIO44, $p.GPIO43)
    };
}
#[cfg(feature = "esp32s3")]
const SDA_SCL_GPIO: (usize, usize) = (5, 6);
#[cfg(feature = "esp32s3")]
const CHIP: &str = "ESP32-S3";

/// The two LED pins again, for the power-off path (the LEDC channels hold the
/// originals). Only used right before deep sleep, after both are dark.
fn steal_led_pins() -> (esp_hal::gpio::AnyPin<'static>, esp_hal::gpio::AnyPin<'static>) {
    // SAFETY: called once, after both LEDC outputs were set to duty 0; the
    // LEDC channels are never used again (deep sleep follows, then reset).
    unsafe {
        #[cfg(feature = "esp32c3")]
        let p = (esp_hal::peripherals::GPIO4::steal().into(), esp_hal::peripherals::GPIO5::steal().into());
        #[cfg(feature = "esp32c6")]
        let p = (esp_hal::peripherals::GPIO2::steal().into(), esp_hal::peripherals::GPIO21::steal().into());
        #[cfg(feature = "esp32s3")]
        let p = (esp_hal::peripherals::GPIO3::steal().into(), esp_hal::peripherals::GPIO4::steal().into());
        p
    }
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
    last_tick: u32,
}

impl Board<'_> {
    /// Called continuously from the main loop.
    fn idle(&mut self) {
        let now = now_us();
        if now.wrapping_sub(self.last_tick) < TICK_US {
            return;
        }
        self.last_tick = now;
        let inputs = Inputs {
            button_down: self.button.is_low(), // BOOT button: active low
            off_selected: self.off.is_high(),  // switch ties D1 to 3.3 V in OFF
        };
        match self.app.tick(now, inputs) {
            AppOutput::Leds(r, b) => self.leds.set(r, b),
            AppOutput::PowerOff => self.power_off(),
        }
    }

    fn on_write(&mut self, bytes: &[u8]) {
        self.app.on_i2c_write(bytes, now_us());
    }

    /// Go dark and deep-sleep until the switch leaves OFF. Waking from deep
    /// sleep resets the chip, so this never returns.
    fn power_off(&mut self) -> ! {
        self.leds.set(0, 0);
        println!("off: deep sleep until D1 goes low");
        let (r, b) = steal_led_pins();
        let mut r = Output::new(r, Level::Low, OutputConfig::default());
        let mut b = Output::new(b, Level::Low, OutputConfig::default());
        r.set_pad_hold(true);
        b.set_pad_hold(true);

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
    // 80 MHz is plenty for two fading LED lines and keeps the module well
    // inside the badge's current budget.
    let peripherals = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let p = peripherals;
    let (mut red_pin, mut blue_pin, sda, scl, off_pin, button_pin, sao1, sao2) = board_pins!(p);

    // First of all: both LED lines low, and release the hold the last
    // power-off put on them (a pad hold survives deep sleep and its reset).
    {
        let mut r = Output::new(red_pin.reborrow(), Level::Low, OutputConfig::default());
        let mut b = Output::new(blue_pin.reborrow(), Level::Low, OutputConfig::default());
        r.set_pad_hold(false);
        b.set_pad_hold(false);
        r.set_low();
        b.set_low();
    }

    // Unused SAO GPIO pins: plain inputs, no pulls, never driven.
    let _sao1 = Input::new(sao1, InputConfig::default().with_pull(Pull::None));
    let _sao2 = Input::new(sao2, InputConfig::default().with_pull(Pull::None));

    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));
    let button = Input::new(button_pin, InputConfig::default().with_pull(Pull::Up));
    let t0 = Instant::now();
    while t0.elapsed().as_micros() < 200 {}
    let off_at_boot = off.is_high();

    // LEDs: LEDC timer 0, channel 0 = red (D2), channel 1 = blue (D3).
    let mut ledc = Ledc::new(p.LEDC);
    ledc.set_global_slow_clock(LSGlobalClkSource::APBClk);
    let mut ls_timer = ledc.timer::<LowSpeed>(leds::TIMER);
    ls_timer.configure(leds::timer_config()).expect("LEDC timer");
    let mut red = ledc.channel(leds::RED, red_pin);
    red.configure(channel::config::Config { timer: &ls_timer, duty_pct: 0, drive_mode: DriveMode::PushPull })
        .expect("LEDC red");
    let mut blue = ledc.channel(leds::BLUE, blue_pin);
    blue.configure(channel::config::Config { timer: &ls_timer, duty_pct: 0, drive_mode: DriveMode::PushPull })
        .expect("LEDC blue");

    // Seed: the module's factory MAC address (unique per module).
    let mac = esp_hal::efuse::base_mac_address();
    let m = mac.as_bytes();
    let seed = u32::from_le_bytes([m[2], m[3], m[4], m[5]]) ^ ((m[0] as u32) << 8 | m[1] as u32);

    println!(
        "Eggplant SAO++ firmware {}.{} on {} (I2C target 0x{:02X})",
        VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS
    );

    let mut board = Board {
        leds: Leds::new(red, blue),
        button,
        off,
        lpwr: LowPower::new(p.LPWR),
        app: App::new(seed, now_us(), off_at_boot),
        last_tick: now_us().wrapping_sub(TICK_US),
    };

    run_i2c(&mut board, p.I2C0, sda, scl)
}

#[cfg(any(feature = "esp32c3", feature = "esp32c6"))]
fn run_i2c<'d>(
    board: &mut Board<'_>,
    i2c: esp_hal::peripherals::I2C0<'d>,
    sda: impl esp_hal::gpio::interconnect::PeripheralInput<'d> + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
    scl: impl esp_hal::gpio::interconnect::PeripheralInput<'d> + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
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
                // Answer with the reply to the last command. SCL is stretched
                // until we do; never wait more than 100 ms for the badge.
                let mut reply = [0u8; 16];
                let r = board.app.reply();
                let n = r.len().max(1);
                reply[..r.len()].copy_from_slice(r);
                let start = now_us();
                let _ = poll_with(
                    slave.respond_to_read_async(&reply[..n]),
                    || board.idle(),
                    || now_us().wrapping_sub(start) > 100_000,
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
    sda: impl esp_hal::gpio::interconnect::PeripheralInput<'d> + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
    scl: impl esp_hal::gpio::interconnect::PeripheralInput<'d> + esp_hal::gpio::interconnect::PeripheralOutput<'d>,
) -> ! {
    let mut target = i2c_target::s3::S3Target::new(i2c, sda, scl, ADDRESS);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.0);
    i2c_target::disable_internal_pullup(SDA_SCL_GPIO.1);
    let mut queued = [0u8; 16];
    let mut qlen = 0usize;
    loop {
        if let Some(bytes) = target.poll() {
            board.on_write(bytes);
        }
        board.idle();
        // Queue the current reply for the next read, never mid-transaction.
        let r = board.app.reply();
        if (r.len() != qlen || r != &queued[..qlen]) && !target.bus_busy() {
            queued[..r.len()].copy_from_slice(r);
            qlen = r.len();
            target.set_read_data(&queued[..qlen]);
        }
    }
}

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    println!("panic: {}", info);
    software_reset()
}
