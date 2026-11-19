//! The speaker on J2, driven "push-pull" from two pins with the LEDC (LED PWM)
//! hardware: channel 0 on D10 (through R14 || R15, 165 ohm), channel 1 on D2
//! (through jumper JP1). Both channels share timer 0, so they run at the same
//! note; channel 1's high time starts half a cycle after channel 0's, so the
//! speaker is pushed one way and then the other (the maker's
//! `setPWMPushPull`). Settings come from `tars_core::tone::push_pull`.
//!
//! As in Mr. Robot's `sounder.rs`, the timer's divider is written straight to
//! the LEDC registers from its real 80 MHz clock, and silence switches both
//! outputs off with their idle level low, so neither pin is left high.

use esp_hal::ledc::{
    LowSpeed,
    channel::{Channel, ChannelHW},
    timer,
};
use esp_hal::time::Rate;
use tars_core::tone::{self, DUTY_BITS};

#[cfg(feature = "esp32c3")]
use esp32c3 as pac;
#[cfg(feature = "esp32c6")]
use esp32c6 as pac;

pub const DUTY: timer::config::Duty = timer::config::Duty::Duty10Bit;
const _: () = assert!(DUTY as u32 == DUTY_BITS);
pub const TIMER: timer::Number = timer::Number::Timer0;
pub const CH_A: esp_hal::ledc::channel::Number = esp_hal::ledc::channel::Number::Channel0;
pub const CH_B: esp_hal::ledc::channel::Number = esp_hal::ledc::channel::Number::Channel1;

pub fn timer_config() -> timer::config::Config<timer::LSClockSource> {
    timer::config::Config { duty: DUTY, clock_source: timer::LSClockSource::APBClk, frequency: Rate::from_hz(1000) }
}

fn ledc() -> &'static pac::ledc::RegisterBlock {
    // SAFETY: the LEDC is owned by the `Ledc` driver created in main, which
    // lives for the whole program and only drives these two channels and this
    // timer; these are single register accesses to them.
    unsafe { &*pac::LEDC::ptr() }
}

fn set_output_enabled(ch: usize, enabled: bool) {
    ledc().ch(ch).conf0().modify(|_, w| {
        w.idle_lv().clear_bit();
        w.sig_out_en().bit(enabled);
        w.para_up().set_bit()
    });
}

pub struct Speaker<'a> {
    a: Channel<'a, LowSpeed>,
    b: Channel<'a, LowSpeed>,
    playing: u32,
}

impl<'a> Speaker<'a> {
    pub fn new(a: Channel<'a, LowSpeed>, b: Channel<'a, LowSpeed>) -> Self {
        let mut s = Self { a, b, playing: 1 };
        s.set(0);
        s
    }

    /// Play `hz` (0 = silence). Does nothing if it is already playing.
    pub fn set(&mut self, hz: u32) {
        if hz == self.playing {
            return;
        }
        self.playing = hz;
        let Some(pp) = tone::push_pull(hz) else {
            set_output_enabled(CH_A as usize, false);
            set_output_enabled(CH_B as usize, false);
            self.a.set_duty_hw(0);
            self.b.set_duty_hw(0);
            return;
        };
        let t = ledc().timer(TIMER as usize);
        t.conf().modify(|_, w| unsafe {
            w.clk_div().bits(pp.div_q8);
            w.duty_res().bits(DUTY_BITS as u8)
        });
        t.conf().modify(|_, w| w.para_up().set_bit());
        ledc().ch(CH_A as usize).hpoint().write(|w| unsafe { w.hpoint().bits(0) });
        ledc().ch(CH_B as usize).hpoint().write(|w| unsafe { w.hpoint().bits(pp.hpoint_b as _) });
        self.a.set_duty_hw(pp.duty); // esp-hal adds the register's 4 fraction bits
        self.b.set_duty_hw(pp.duty);
        set_output_enabled(CH_A as usize, true);
        set_output_enabled(CH_B as usize, true);
    }
}
