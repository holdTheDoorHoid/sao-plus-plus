//! Smooth fading of one LED channel, as on the maker's board: every step
//! (20 ms) the channel moves `speed` places along the fading curve and its
//! brightness is set between `min` and `max` by the curve's height there.
//! `phase` shifts the channel along the curve, so channels can breathe out of
//! step. Speed 0 means "steady at max".

use crate::{PWM_MAX, curve};

/// Time between fading steps, as on the maker's board.
pub const STEP_MS: u32 = 20;

#[derive(Clone, Copy, Debug, Default)]
pub struct Fader {
    idx: u16,
    pos: u16,
}

impl Fader {
    /// A channel starting at the beginning of the curve, shifted by `phase`.
    pub fn new(phase: u8) -> Self {
        Self { idx: 0, pos: wrap(phase as u16 * 4) }
    }

    /// One step: the brightness (0..=1023) to show now, then move on.
    pub fn step(&mut self, max: u8, min: u8, speed: u8, phase: u8) -> u16 {
        let hi = (max as i32) << 2;
        let lo = (min as i32) << 2;
        if speed == 0 {
            return (hi as u16).min(PWM_MAX);
        }
        let h = curve::CURVE[self.pos as usize] as i32;
        // from `min` (curve at 0) to `max` (curve at the top); if min > max the
        // channel simply fades the other way
        let v = lo + ((h * (hi - lo)) >> 16);
        self.idx = wrap(self.idx + speed as u16);
        self.pos = wrap(self.idx + phase as u16 * 4);
        (v.clamp(0, PWM_MAX as i32)) as u16
    }
}

fn wrap(v: u16) -> u16 {
    if v >= curve::LEN { v - curve::LEN } else { v }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    #[test]
    fn steady_when_speed_zero() {
        let mut f = Fader::new(0);
        assert_eq!(f.step(80, 10, 0, 0), 320);
        assert_eq!(f.step(255, 0, 0, 0), 1020);
        assert_eq!(f.step(0, 0, 0, 0), 0);
    }

    #[test]
    fn breathes_between_min_and_max() {
        let mut f = Fader::new(0);
        let v: Vec<u16> = (0..1152).map(|_| f.step(80, 10, 1, 0)).collect();
        assert_eq!(v[0], 40);
        assert_eq!(*v.iter().min().unwrap(), 40);
        let top = *v.iter().max().unwrap();
        assert!((319..=320).contains(&top), "top {top}");
        assert_eq!(v[512], top);
        // the rest at the bottom: the last 128 steps stay at min
        assert!(v[1024..].iter().all(|&x| x == 40));
    }

    #[test]
    fn speed_two_breathes_every_11_5_seconds() {
        // the maker's default: 1152 / 2 = 576 steps of 20 ms, about 11.5 s per breath
        let mut f = Fader::new(0);
        let v: Vec<u16> = (0..2000).map(|_| f.step(255, 0, 2, 0)).collect();
        for k in 0..(2000 - 576) {
            assert_eq!(v[k], v[k + 576], "step {k}");
        }
        assert!(v[..576].iter().filter(|&&x| x == 0).count() < 80);
    }

    #[test]
    fn phase_shifts_the_breath() {
        let mut a = Fader::new(0);
        let mut b = Fader::new(128);
        let va: Vec<u16> = (0..1152).map(|_| a.step(255, 0, 1, 0)).collect();
        let vb: Vec<u16> = (0..1152).map(|_| b.step(255, 0, 1, 128)).collect();
        for k in 0..1152 {
            assert_eq!(vb[k], va[(k + 512) % 1152], "step {k}");
        }
    }

    #[test]
    fn reversed_range_fades_downwards() {
        let mut f = Fader::new(0);
        let v: Vec<u16> = (0..1152).map(|_| f.step(10, 200, 1, 0)).collect();
        assert_eq!(v[0], 800);
        assert!(v[512] <= 41);
        assert!(v.iter().all(|&x| (40..=800).contains(&x)));
    }

    #[test]
    fn fast_speeds_stay_in_range() {
        let mut f = Fader::new(255);
        for _ in 0..5000 {
            let v = f.step(255, 255, 255, 255);
            assert!(v <= PWM_MAX);
        }
    }
}
