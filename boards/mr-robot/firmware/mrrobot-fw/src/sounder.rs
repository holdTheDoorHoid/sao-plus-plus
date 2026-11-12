//! The sounder output on D10, made with the chip's LEDC (LED PWM) peripheral.
//!
//! Why LEDC: it exists on all three chips (C3, C6, S3) with the same esp-hal
//! 1.2.2 driver, a hardware timer makes the square wave so the CPU does
//! nothing per cycle (no busy-waiting, no interrupts), and at 12-bit
//! resolution from its 80 MHz clock it covers every note of the maker's
//! table (31..4978 Hz) to within 0.1 % (checked in `mrrobot-core`'s tests).
//! MCPWM would also work on the C6 and S3 but the C3 has none.
//!
//! esp-hal sets up the LEDC (clock, timer resolution, channel, pin routing)
//! once at start-up. Retuning for each note writes the timer's clock divider
//! directly, computed by `mrrobot_core::tone::SquareWave::ledc_divider_q8`
//! from the LEDC's real 80 MHz clock. Two reasons: esp-hal's channel keeps a
//! borrow of the timer, so the timer cannot be reconfigured through esp-hal
//! afterwards; and on the C6, esp-hal 1.2.2 works out the divider from the
//! APB clock (40 MHz at our 80 MHz CPU setting) although it feeds the LEDC
//! from the 80 MHz PLL clock, which on paper would put every note an octave
//! too high. On the C3 and S3 the APB clock is 80 MHz and both agree.
//!
//! The duty is fixed at exactly half the counter range (2048 of 4096), so the
//! pin is high at most 50 % of the time. Silence is not just "duty 0": the
//! channel's output is also switched off with its idle level set low, which
//! makes the LEDC hold the pin low whatever its timer does.

use esp_hal::ledc::{
    LowSpeed,
    channel::{Channel, ChannelHW},
    timer,
};
use esp_hal::time::Rate;
use mrrobot_core::tone::{LEDC_DUTY_BITS, LEDC_SOURCE_HZ, SquareWave, ToneHw};

/// The LEDC timer resolution, matching `LEDC_DUTY_BITS` in the core crate.
pub const DUTY: timer::config::Duty = timer::config::Duty::Duty12Bit;
const _: () = assert!(DUTY as u32 == LEDC_DUTY_BITS);

/// The LEDC timer and channel used for the sounder.
pub const TIMER: timer::Number = timer::Number::Timer0;
pub const CHANNEL: esp_hal::ledc::channel::Number = esp_hal::ledc::channel::Number::Channel0;

/// Start-up configuration for the timer (the frequency is replaced before
/// the first note sounds).
pub fn timer_config() -> timer::config::Config<timer::LSClockSource> {
    timer::config::Config {
        duty: DUTY,
        clock_source: timer::LSClockSource::APBClk,
        frequency: Rate::from_hz(440),
    }
}

#[cfg(feature = "esp32c3")]
use esp32c3 as pac;
#[cfg(feature = "esp32c6")]
use esp32c6 as pac;
#[cfg(feature = "esp32s3")]
use esp32s3 as pac;

fn ledc() -> &'static pac::ledc::RegisterBlock {
    // SAFETY: the LEDC is owned by the `Ledc` driver created in main, which
    // lives for the whole program and only ever drives this one channel and
    // timer; these are single register accesses to that channel/timer.
    unsafe { &*pac::LEDC::ptr() }
}

pub struct Sounder<'a> {
    channel: Channel<'a, LowSpeed>,
}

impl<'a> Sounder<'a> {
    /// `channel` must already be configured on [`TIMER`] with [`DUTY`]
    /// resolution. The pin is forced low before this returns.
    pub fn new(channel: Channel<'a, LowSpeed>) -> Self {
        let mut s = Self { channel };
        s.output_low();
        s
    }
}

/// Switch the channel's output on (follow the timer) or off (hold the idle
/// level, which is always low).
fn set_output_enabled(enabled: bool) {
    ledc().ch(CHANNEL as usize).conf0().modify(|_, w| {
        w.idle_lv().clear_bit();
        w.sig_out_en().bit(enabled);
        w.para_up().set_bit()
    });
}

impl ToneHw for Sounder<'_> {
    fn output_square(&mut self, wave: SquareWave) {
        let Some(div) = wave.ledc_divider_q8(LEDC_SOURCE_HZ, LEDC_DUTY_BITS) else {
            // Cannot make this frequency: stay silent rather than guess.
            self.output_low();
            return;
        };
        ledc().timer(TIMER as usize).conf().modify(|_, w| unsafe {
            w.clk_div().bits(div);
            w.duty_res().bits(LEDC_DUTY_BITS as u8)
        });
        ledc()
            .timer(TIMER as usize)
            .conf()
            .modify(|_, w| w.para_up().set_bit());
        self.channel.set_duty_hw(wave.ledc_duty(LEDC_DUTY_BITS));
        set_output_enabled(true);
    }

    fn output_low(&mut self) {
        set_output_enabled(false);
        self.channel.set_duty_hw(0);
    }
}
