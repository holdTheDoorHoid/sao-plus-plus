//! The two LED lines (all five red anodes on D2, all five blue anodes on D3)
//! as two channels of the chip's LEDC (LED PWM) peripheral on one timer.
//!
//! The maker made his brightness with a software loop of 96 steps. Here the
//! LEDC does it in hardware at 2 kHz (well above flicker) with 10-bit steps,
//! and the core crate's 0..=96 brightness is scaled onto that.
//!
//! Dark means pin low: duty 0 and the channel's output switched to its idle
//! level (low), so a pin is never left high by accident (5 LEDs on one pin).

use esp_hal::ledc::{
    LowSpeed,
    channel::{Channel, ChannelHW},
    timer,
};
use esp_hal::time::Rate;

pub const DUTY: timer::config::Duty = timer::config::Duty::Duty10Bit;
pub const FULL: u32 = 1 << 10;
pub const TIMER: timer::Number = timer::Number::Timer0;
pub const RED: esp_hal::ledc::channel::Number = esp_hal::ledc::channel::Number::Channel0;
pub const BLUE: esp_hal::ledc::channel::Number = esp_hal::ledc::channel::Number::Channel1;

pub fn timer_config() -> timer::config::Config<timer::LSClockSource> {
    timer::config::Config {
        duty: DUTY,
        clock_source: timer::LSClockSource::APBClk,
        frequency: Rate::from_hz(2_000),
    }
}

pub struct Leds<'a> {
    red: Channel<'a, LowSpeed>,
    blue: Channel<'a, LowSpeed>,
}

impl<'a> Leds<'a> {
    pub fn new(red: Channel<'a, LowSpeed>, blue: Channel<'a, LowSpeed>) -> Self {
        let mut l = Self { red, blue };
        l.set(0, 0);
        l
    }

    /// Brightness 0..=96 each (the core crate's scale).
    pub fn set(&mut self, red: u16, blue: u16) {
        let c = eggplant_core::fade::CYCLE as u32;
        self.red.set_duty_hw((red as u32).min(c) * FULL / c);
        self.blue.set_duty_hw((blue as u32).min(c) * FULL / c);
    }
}
