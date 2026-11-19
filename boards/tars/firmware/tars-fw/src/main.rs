//! TARS SAO (SAO++ edition) firmware for the Seeed Studio XIAO ESP32-C3 /
//! ESP32-C6.
//!
//! Behaviour reimplemented from the maker's Arduino sketches (davedarko,
//! 2024, MIT licence, <https://github.com/davedarko/TARS-SAO>): the menu, the
//! piano, the click and his display demos. All of that lives in `tars-core`
//! and is unit-tested on the host. This file is the thin hardware layer:
//! pins, display, touch chip, speaker, cue light, badge I2C, sleep. Its
//! structure (I2C polling, deep sleep on OFF, panic handling) follows the
//! Mr. Robot firmware in this repository.
//!
//! No radio driver is linked: Wi-Fi and Bluetooth are never started.

#![no_std]
#![no_main]

mod hw;
mod i2c_target;
mod speaker;

use core::panic::PanicInfo;

use esp_hal::{
    clock::CpuClock,
    gpio::{DriveMode, Event, Input, InputConfig, Level, Output, OutputConfig, Pull, WakeupConfig},
    ledc::{
        LSGlobalClkSource, Ledc, LowSpeed,
        channel::{self, ChannelIFace},
        timer::TimerIFace,
    },
    rtc_cntl::sleep::{LowPower, RtcSleepConfig},
    spi::{
        Mode,
        master::{Config as SpiConfig, Spi},
    },
    system::software_reset,
    time::{Instant, Rate},
};
use esp_println::println;
use tars_core::{
    VERSION_MAJOR, VERSION_MINOR,
    app::App,
    bitbang::BitBang,
    cap1206,
    gfx::Frame,
    i2c::ADDRESS,
};

use crate::{
    hw::{Display, PrivateBus},
    speaker::Speaker,
};

esp_bootloader_esp_idf::esp_app_desc!();

const TICK_MS: u32 = 2;
const TOUCH_MS: u32 = 20;

// ---------------------------------------------------------------------------
// Pin map: XIAO pin -> GPIO, per chip. (README has the same table.)
//
//                   C3      C6
//   D10 speaker A   GPIO10  GPIO18
//   D2  speaker B   GPIO4   GPIO2
//   D7  TFT clock   GPIO20  GPIO17
//   D3  TFT data    GPIO5   GPIO21
//   D6  TFT D/C     GPIO21  GPIO16
//   D0  private SDA GPIO2   GPIO0
//   D8  private SCL GPIO8   GPIO19
//   D9  cue light   GPIO9   GPIO20   (low = lit; the C3's BOOT button too)
//   D1  OFF sense   GPIO3   GPIO1
//   D4  badge SDA   GPIO6   GPIO22
//   D5  badge SCL   GPIO7   GPIO23
// ---------------------------------------------------------------------------

#[cfg(feature = "esp32c3")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO10, $p.GPIO4, $p.GPIO20, $p.GPIO5, $p.GPIO21, $p.GPIO2, $p.GPIO8, $p.GPIO9, $p.GPIO3, $p.GPIO6, $p.GPIO7)
    };
}
#[cfg(feature = "esp32c3")]
const SDA_SCL_GPIO: (usize, usize) = (6, 7);
#[cfg(feature = "esp32c3")]
const CHIP: &str = "ESP32-C3";

#[cfg(feature = "esp32c6")]
macro_rules! board_pins {
    ($p:ident) => {
        ($p.GPIO18, $p.GPIO2, $p.GPIO17, $p.GPIO21, $p.GPIO16, $p.GPIO0, $p.GPIO19, $p.GPIO20, $p.GPIO1, $p.GPIO22, $p.GPIO23)
    };
}
#[cfg(feature = "esp32c6")]
const SDA_SCL_GPIO: (usize, usize) = (22, 23);
#[cfg(feature = "esp32c6")]
const CHIP: &str = "ESP32-C6";

static mut FRAME: Frame = Frame::new();

fn now_ms() -> u32 {
    Instant::now().duration_since_epoch().as_millis() as u32
}

struct Board<'d> {
    app: App,
    frame: &'d mut Frame,
    display: Display<'d>,
    touch: BitBang<PrivateBus<'d>>,
    touch_ok: bool,
    mask: u8,
    speaker: Speaker<'d>,
    cue: Output<'d>,
    off: Input<'d>,
    lpwr: LowPower<'d>,
    last_tick: u32,
    last_touch: u32,
}

impl Board<'_> {
    fn idle(&mut self) {
        let now = now_ms();
        if now.wrapping_sub(self.last_tick) < TICK_MS {
            return;
        }
        self.step(now);
    }

    fn step(&mut self, now: u32) {
        self.last_tick = now;
        if now.wrapping_sub(self.last_touch) >= TOUCH_MS {
            self.last_touch = now;
            if self.touch_ok {
                match cap1206::poll(&mut self.touch) {
                    Ok(m) => self.mask = m,
                    Err(_) => {
                        // a stuck bus (e.g. a Qwiic device unplugged mid-transfer): free it, try again next time
                        let _ = self.touch.recover();
                    }
                }
            }
        }
        let out = self.app.tick(now, self.mask, self.off.is_high());
        if out.power_off {
            self.power_off();
        }
        self.speaker.set(out.tone_hz);
        if out.cue_on { self.cue.set_low() } else { self.cue.set_high() }
        if out.redraw {
            self.app.render(self.frame, now);
            self.display.show(self.frame);
        }
    }

    fn on_write(&mut self, bytes: &[u8]) {
        let now = now_ms();
        if self.app.on_i2c_write(bytes, now) > 0 {
            self.step(now);
        }
    }

    /// Silence, blank, and deep-sleep until the switch leaves OFF. Waking
    /// from deep sleep resets the chip, so this never returns.
    fn power_off(&mut self) -> ! {
        self.speaker.set(0);
        self.cue.set_high();
        self.frame.fill(tars_core::gfx::BLACK);
        self.display.show(self.frame);
        self.display.sleep();
        println!("off: deep sleep until D1 goes low");
        self.off.listen(Event::LowLevel);
        if self.off.apply_wakeup_config(&WakeupConfig::default().with_low_power_path(true)).is_err() {
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
    let p = esp_hal::init(esp_hal::Config::default().with_cpu_clock(CpuClock::_80MHz));
    let (spk_a, spk_b, sclk, mosi, dc, priv_sda, priv_scl, cue_pin, off_pin, sda, scl) = board_pins!(p);

    // Cue light: open-drain on D9, released (dark) at start. Open-drain so that
    // pressing the C3's BOOT button (same pin, to ground) never fights it.
    let cue = Output::new(cue_pin, Level::High, OutputConfig::default().with_drive_mode(DriveMode::OpenDrain));
    let off = Input::new(off_pin, InputConfig::default().with_pull(Pull::Down));

    // Speaker: LEDC timer 0, channels 0 (D10) and 1 (D2), silent.
    let mut ledc = Ledc::new(p.LEDC);
    ledc.set_global_slow_clock(LSGlobalClkSource::APBClk);
    let mut ls_timer = ledc.timer::<LowSpeed>(speaker::TIMER);
    ls_timer.configure(speaker::timer_config()).expect("LEDC timer");
    let mut ch_a = ledc.channel(speaker::CH_A, spk_a);
    ch_a.configure(channel::config::Config { timer: &ls_timer, duty_pct: 0, drive_mode: DriveMode::PushPull })
        .expect("LEDC channel A");
    let mut ch_b = ledc.channel(speaker::CH_B, spk_b);
    ch_b.configure(channel::config::Config { timer: &ls_timer, duty_pct: 0, drive_mode: DriveMode::PushPull })
        .expect("LEDC channel B");
    let speaker = Speaker::new(ch_a, ch_b);

    // Display: SPI mode 0 at 20 MHz, no chip-select (tied to ground on the board).
    let spi = Spi::new(p.SPI2, SpiConfig::default().with_frequency(Rate::from_mhz(20)).with_mode(Mode::_0))
        .expect("SPI")
        .with_sck(sclk)
        .with_mosi(mosi);
    let mut display = Display::new(spi, Output::new(dc, Level::High, OutputConfig::default()));
    display.init();

    // Touch chip on the private bus.
    let mut touch = BitBang::new(PrivateBus::new(priv_sda, priv_scl));
    let _ = touch.recover();
    let touch_ok = match cap1206::identify(&mut touch) {
        Ok((pid, mid)) => {
            println!("touch chip: product 0x{:02X}, maker 0x{:02X}", pid, mid);
            cap1206::setup(&mut touch).is_ok()
        }
        Err(e) => {
            println!("touch chip not answering: {:?}", e);
            false
        }
    };

    println!("TARS SAO++ firmware {}.{} on {} (I2C target 0x{:02X})", VERSION_MAJOR, VERSION_MINOR, CHIP, ADDRESS);

    // SAFETY: the only reference to FRAME, taken once here and kept by the board.
    let frame = unsafe { &mut *core::ptr::addr_of_mut!(FRAME) };
    let mut board = Board {
        app: App::new(now_ms()),
        frame,
        display,
        touch,
        touch_ok,
        mask: 0,
        speaker,
        cue,
        off,
        lpwr: LowPower::new(p.LPWR),
        last_tick: now_ms().wrapping_sub(TICK_MS),
        last_touch: now_ms(),
    };

    run_i2c(&mut board, p.I2C0, sda, scl)
}

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
                let status = board.app.status();
                let start = now_ms();
                let _ = poll_with(slave.respond_to_read_async(&status), || board.idle(), || now_ms().wrapping_sub(start) > 100);
            }
            Some(Err(_)) | None => {}
        }
    }
}

#[panic_handler]
fn panic(info: &PanicInfo) -> ! {
    println!("panic: {}", info);
    software_reset()
}
