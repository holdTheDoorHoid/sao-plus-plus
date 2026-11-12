//! The fading waveform, per channel, as the maker's firmware defines it.
//!
//! One cycle is 1152 steps: 1024 steps of a smooth "breath" from dark to
//! bright and back (a raised cosine), then 128 steps of darkness. Every 20 ms
//! a channel moves on by its `speed` register, so speed 2 gives one breath
//! every 11.5 seconds. The `phase` register shifts a channel along the cycle
//! by four steps per count. The brightness swings between the channel's `min`
//! and `max` registers. Speed 0 means "steady at max".
//!
//! Differences from the original, all small:
//! * the maker's chip drove the LED with 10-bit PWM; the addressable LEDs here
//!   take 8 bits per colour, so very dim fades have coarser steps;
//! * the curve is computed with an integer approximation instead of a stored
//!   table (it differs from a true cosine by less than 0.4 % of full scale);
//! * if `min` is set above `max` the channel simply stays at `min`.

use crate::registers::{CHANNELS, Settings};

/// Steps in the bright part of the cycle.
pub const WAVE_STEPS: u16 = 1024;
/// Dark steps after it.
pub const DARK_STEPS: u16 = 128;
/// Whole cycle.
pub const CYCLE_STEPS: u16 = WAVE_STEPS + DARK_STEPS;

/// The waveform at step `pos` (0..CYCLE_STEPS), 0 = dark, 65535 = brightest.
///
/// For the first 1024 steps this is sin^2(pi * pos / 1024), which is the same
/// curve as the maker's lookup table, (1 - cos(2 pi pos / 1024)) / 2. The sine
/// comes from Bhaskara's approximation, which needs only integers.
pub fn wave(pos: u16) -> u16 {
    if pos >= WAVE_STEPS {
        return 0;
    }
    let n = pos as u64;
    let p = n * (1024 - n); // 0..=262144
    // sin(pi n / 1024) ~= 16 p / (5 * 1024^2 - 4 p), here scaled by 65536.
    let s = ((16 * p) << 16) / (5 * 1_048_576 - 4 * p); // 0..=65536
    let w = (s * s) >> 16;
    if w > 65535 { 65535 } else { w as u16 }
}

/// Where each channel is in its cycle.
#[derive(Clone, Copy, Debug)]
pub struct Fader {
    idx: [u16; CHANNELS],
}

impl Fader {
    pub const fn new() -> Self {
        Self { idx: [0; CHANNELS] }
    }

    /// Advance one 20 ms step and return the four channel values
    /// (red, green, blue, background).
    pub fn step(&mut self, s: &Settings) -> [u8; CHANNELS] {
        let mut out = [0u8; CHANNELS];
        for ch in 0..CHANNELS {
            if s.speed[ch] == 0 {
                out[ch] = s.max[ch];
                continue;
            }
            let pos = (self.idx[ch] + ((s.phase[ch] as u16) << 2)) % CYCLE_STEPS;
            let span = s.max[ch].saturating_sub(s.min[ch]) as u32;
            out[ch] = ((wave(pos) as u32 * span) >> 16) as u8 + s.min[ch];
            self.idx[ch] = (self.idx[ch] + s.speed[ch] as u16) % CYCLE_STEPS;
        }
        out
    }
}

impl Default for Fader {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wave_shape() {
        assert_eq!(wave(0), 0);
        assert_eq!(wave(512), 65535);
        assert_eq!(wave(1024), 0);
        assert_eq!(wave(1151), 0);
        // symmetric, and rising through the first half
        for n in 1..512u16 {
            assert_eq!(wave(n), wave(1024 - n));
            assert!(wave(n) >= wave(n - 1));
        }
        // quarter points of a raised cosine are at half height (within 1 %)
        let q = wave(256) as i32;
        assert!((q - 32768).abs() < 656, "{q}");
    }

    #[test]
    fn steady_when_speed_is_zero() {
        let mut s = Settings::DEFAULT;
        s.speed = [0; CHANNELS];
        s.max = [9, 8, 7, 6];
        let mut f = Fader::new();
        assert_eq!(f.step(&s), [9, 8, 7, 6]);
        assert_eq!(f.step(&s), [9, 8, 7, 6]);
    }

    #[test]
    fn default_breath_stays_between_min_and_max() {
        let s = Settings::DEFAULT;
        let mut f = Fader::new();
        let (mut lo, mut hi) = (255u8, 0u8);
        for _ in 0..(CYCLE_STEPS / 2) {
            let v = f.step(&s);
            lo = lo.min(v[0]);
            hi = hi.max(v[0]);
            assert_eq!(v[2], 0, "blue is off by default");
        }
        // 79, not 80: the top of the swing is 65535/65536 of (max - min), rounded down
        assert_eq!((lo, hi), (10, 79));
    }

    #[test]
    fn min_above_max_does_not_overflow() {
        let mut s = Settings::DEFAULT;
        s.max[0] = 10;
        s.min[0] = 200;
        let mut f = Fader::new();
        for _ in 0..CYCLE_STEPS {
            assert_eq!(f.step(&s)[0], 200);
        }
    }
}
