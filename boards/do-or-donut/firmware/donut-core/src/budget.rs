//! The current budget: a safety limit, not a style choice.
//!
//! A badge may give an SAO++ board at most 50 mA in total (docs/standard.md).
//! 144 LEDs at full brightness would need several hundred. So every frame
//! leaves the core through [`limit`], which scales the whole frame down
//! (keeping the shape of the picture) until its *estimated* average LED
//! current fits under [`LED_BUDGET_UA`].
//!
//! # The numbers, and how sure they are
//!
//! * **Per-LED current at full PWM: 3.2 mA average** ([`LED_FULL_AVG_UA`]).
//!   This is the IS31FL3731 datasheet's *typical* figure for R_EXT = 20 kOhm
//!   (Rev. D 2013, Electrical Characteristics "I_LED", and Formula (2):
//!   I_LED = 64.7 / R_EXT). It already includes the chip's 1-in-9 scanning.
//!   It is an ASSUMPTION for this board until measured: the datasheet gives
//!   no maximum, and the real LEDs at 3.3 V may draw less.
//! * **Current scales linearly with the PWM value**, I = I_LED x PWM / 256
//!   (datasheet Formula (1)).
//! * **Budget for the LEDs: 25 mA** ([`LED_BUDGET_UA`]). Calculated, not
//!   measured: 50 mA allowed, minus about 20 mA guessed for the XIAO running
//!   at 80 MHz with no radio, minus 2.2 mA for the driver chip itself
//!   (datasheet typical quiescent current), minus a little margin.
//!
//! With these numbers the cap is a total PWM of [`MAX_PWM_SUM`] = 2000 across
//! the frame: for example all 144 LEDs at about 13/255 (5 %), or 7 LEDs at
//! full. Change the two constants once the board has been measured; the
//! tests below hold for any values.

use crate::{Frame, LED_COUNT};

/// Assumed average current of one LED at PWM 255/256, microamps. See above.
pub const LED_FULL_AVG_UA: u32 = 3_200;

/// The chip's PWM has 256 steps: current = full x value / 256.
pub const PWM_STEPS: u32 = 256;

/// The most average LED current a frame may need, microamps. See above.
pub const LED_BUDGET_UA: u32 = 25_000;

/// The cap expressed as a sum of PWM values over the whole frame.
pub const MAX_PWM_SUM: u32 = LED_BUDGET_UA * PWM_STEPS / LED_FULL_AVG_UA;

const _: () = assert!(MAX_PWM_SUM > 0);
const _: () = assert!(
    MAX_PWM_SUM < 255 * LED_COUNT as u32,
    "the cap must actually bite"
);

/// Sum of the PWM values in a frame.
pub fn pwm_sum(frame: &Frame) -> u32 {
    frame.iter().map(|&v| v as u32).sum()
}

/// Estimated average LED current of a frame, microamps (rounded up).
pub fn estimate_ua(frame: &Frame) -> u32 {
    (pwm_sum(frame) * LED_FULL_AVG_UA).div_ceil(PWM_STEPS)
}

/// Scale `frame` down in place so that its PWM sum is at most
/// [`MAX_PWM_SUM`]. Frames already inside the budget are left untouched.
/// Returns `true` if the frame had to be scaled.
///
/// Each value becomes `v * MAX / sum`, rounded down, so the new sum can only
/// be at or below `MAX` and no LED ever gets brighter.
pub fn limit(frame: &mut Frame) -> bool {
    let sum = pwm_sum(frame);
    if sum <= MAX_PWM_SUM {
        return false;
    }
    for v in frame.iter_mut() {
        *v = (*v as u32 * MAX_PWM_SUM / sum) as u8;
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Small deterministic generator for "any frame" tests.
    struct Lcg(u64);
    impl Lcg {
        fn next(&mut self) -> u8 {
            self.0 = self
                .0
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (self.0 >> 56) as u8
        }
    }

    fn assert_within(f: &Frame) {
        assert!(pwm_sum(f) <= MAX_PWM_SUM);
        assert!(estimate_ua(f) <= LED_BUDGET_UA);
    }

    #[test]
    fn the_cap_is_2000() {
        assert_eq!(MAX_PWM_SUM, 2000);
    }

    #[test]
    fn everything_full_on_is_capped() {
        let mut f = [255u8; LED_COUNT];
        assert_eq!(estimate_ua(&f), 459_000);
        assert!(limit(&mut f));
        assert_within(&f);
        // Even, and as bright as the budget allows: 2000 / 144 = 13.
        assert!(f.iter().all(|&v| v == 13));
    }

    #[test]
    fn no_frame_can_exceed_the_budget() {
        let mut rng = Lcg(1);
        for case in 0..20_000 {
            let mut f = [0u8; LED_COUNT];
            // Mix of densities: sparse, dense, all-max, single-valued.
            let density = case % 8;
            for v in f.iter_mut() {
                let r = rng.next();
                *v = match density {
                    0 => 255,
                    1 => r,
                    2 if r < 32 => 255,
                    3 => r / 8,
                    4 => (case % 256) as u8,
                    _ if r.is_multiple_of(density as u8) => rng.next(),
                    _ => 0,
                };
            }
            let before = f;
            limit(&mut f);
            assert_within(&f);
            for (a, b) in before.iter().zip(f.iter()) {
                assert!(b <= a, "limit made an LED brighter");
            }
        }
    }

    #[test]
    fn frames_inside_the_budget_are_untouched() {
        let mut f = [0u8; LED_COUNT];
        for (i, v) in f.iter_mut().enumerate().take(7) {
            *v = 255 - i as u8;
        }
        let before = f;
        assert!(!limit(&mut f));
        assert_eq!(f, before);
        let mut exact = [0u8; LED_COUNT];
        exact[..8].copy_from_slice(&[250; 8]);
        assert_eq!(pwm_sum(&exact), MAX_PWM_SUM);
        assert!(!limit(&mut exact));
    }

    #[test]
    fn scaling_keeps_the_picture_shape() {
        let mut f = [0u8; LED_COUNT];
        f[0] = 255;
        f[1] = 128;
        for v in f[2..20].iter_mut() {
            *v = 200;
        }
        limit(&mut f);
        assert!(f[0] > f[1] && f[1] > 0);
        assert!(f[2..20].iter().all(|&v| v == f[2]));
    }

    #[test]
    fn about_a_dozen_at_full_matches_the_readme_order_of_magnitude() {
        // README: "all 144 at about 10 %, or about a dozen at full, stays near
        // 40 mA" (LEDs only). This budget is stricter (25 mA, leaving room for
        // the XIAO): check the arithmetic agrees with that statement scaled.
        let per_full = LED_FULL_AVG_UA * 255 / PWM_STEPS;
        assert!((12 * per_full) > 35_000 && (12 * per_full) < 40_000);
        assert!(LED_BUDGET_UA / per_full == 7);
    }
}
