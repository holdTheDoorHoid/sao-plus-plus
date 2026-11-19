//! The LED outputs, made with the chip's LEDC (LED PWM) peripheral: one timer
//! at 20 kHz with 10-bit resolution (the maker's resolution), one channel per
//! colour.
//!
//! The board's LEDs are wired "common anode": each colour pin lights its LED
//! by pulling LOW. So a brightness of 0..=1023 from the core becomes a high
//! time of 1024 - brightness: brightness 0 = pin high all the time = dark.
//! (Duck Jaws' background LEDs are wired the same way on the SAO++ board.)

use duckglow_core::CHANNELS;
use esp_hal::{
    gpio::{DriveMode, interconnect::PeripheralOutput},
    ledc::{
        LSGlobalClkSource, Ledc, LowSpeed,
        channel::{self, ChannelHW, ChannelIFace},
        timer::{self, TimerIFace},
    },
    time::Rate,
};

/// Full period in counts at 10 bits; a duty of this many counts is "high all
/// the time".
const FULL: u32 = 1 << 10;

pub struct Leds<'d> {
    ch: [Option<channel::Channel<'d, LowSpeed>>; CHANNELS],
}

/// The LEDC timer, set up once in `main` and kept there for the whole program
/// (the channels borrow it).
pub fn timer<'d>(ledc: &mut Ledc<'d>) -> timer::Timer<'d, LowSpeed> {
    ledc.set_global_slow_clock(LSGlobalClkSource::APBClk);
    let mut tmr = ledc.timer::<LowSpeed>(timer::Number::Timer0);
    tmr.configure(timer::config::Config {
        duty: timer::config::Duty::Duty10Bit,
        clock_source: timer::LSClockSource::APBClk,
        frequency: Rate::from_khz(20),
    })
    .expect("LEDC timer");
    tmr
}

impl<'d> Leds<'d> {
    pub fn new(
        ledc: &Ledc<'d>,
        tmr: &'d timer::Timer<'d, LowSpeed>,
        red: impl PeripheralOutput<'d>,
        green: impl PeripheralOutput<'d>,
        blue: impl PeripheralOutput<'d>,
        background: impl PeripheralOutput<'d>,
    ) -> Self {
        let cfg = |c: &mut channel::Channel<'d, LowSpeed>| {
            c.configure(channel::config::Config { timer: tmr, duty_pct: 100, drive_mode: DriveMode::PushPull })
                .expect("LEDC channel");
            c.set_duty_hw(FULL);
        };
        let mut r = ledc.channel(channel::Number::Channel0, red);
        cfg(&mut r);
        let mut g = ledc.channel(channel::Number::Channel1, green);
        cfg(&mut g);
        let mut b = ledc.channel(channel::Number::Channel2, blue);
        cfg(&mut b);
        // Duck Bath has nothing on the background pin: leave it alone.
        let bg = if cfg!(feature = "jaws") {
            let mut c = ledc.channel(channel::Number::Channel3, background);
            cfg(&mut c);
            Some(c)
        } else {
            drop(background);
            None
        };
        Self { ch: [Some(r), Some(g), Some(b), bg] }
    }
}

impl Leds<'_> {
    /// Show brightness 0..=1023 per channel.
    pub fn show(&mut self, b: [u16; CHANNELS]) {
        for (c, v) in self.ch.iter().zip(b) {
            if let Some(c) = c {
                c.set_duty_hw(FULL - (v.min(1023) as u32));
            }
        }
    }

    /// All dark (pins high), before sleeping.
    pub fn release(&mut self) {
        self.show([0; CHANNELS]);
    }
}
