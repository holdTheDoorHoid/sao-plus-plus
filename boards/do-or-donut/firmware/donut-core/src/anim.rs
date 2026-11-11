//! The built-in animations. Each is a pure function of time: the same `t`
//! always gives the same picture, so they are easy to test and restart.
//!
//! They work in *levels* (0..=255, as bright as it looks), using each LED's
//! real position from the LED map, and leave conversion to PWM ([`gamma`])
//! and the current cap ([`crate::budget`]) to the caller.
//!
//! All arithmetic is integer: no floating point on the microcontroller.

use crate::leds::{LEDS, R_MAX_UM, R_MIN_UM};
use crate::{Frame, LED_COUNT};

/// Perceived level to PWM value: squared, which is close to the eye's
/// response and to the 64-step gamma table in the IS31FL3731 datasheet.
/// Any lit level stays at least 1, so faint tails do not vanish.
pub const fn gamma(level: u8) -> u8 {
    let l = level as u32;
    (l * l).div_ceil(255) as u8
}

/// Smooth hump: 0 at phase 0, 255 at half a cycle, back to 0. `phase` is
/// one full cycle per 65536. (Smoothstep of a triangle: close to a raised
/// cosine, without trigonometry.)
pub const fn hump(phase: u16) -> u8 {
    let tri = if phase < 0x8000 {
        (phase as u32) * 2
    } else {
        (0xFFFF - phase as u32) * 2
    }; // 0..=65534
    let t = tri as u64;
    let s = t * t * (3 * 65536 - 2 * t) / (65536 * 65536); // 0..=65535
    (s * 255 / 65535) as u8
}

/// A fixed per-LED "random" number (lowbias32 hash).
pub const fn hash(mut x: u32) -> u32 {
    x ^= x >> 16;
    x = x.wrapping_mul(0x7feb_352d);
    x ^= x >> 15;
    x = x.wrapping_mul(0x846c_a68b);
    x ^= x >> 16;
    x
}

/// Linear fade from 255 at `d == 0` to 0 at `d >= width`.
const fn fade(d: u32, width: u32) -> u8 {
    if d >= width {
        0
    } else {
        (255 * (width - d) / width) as u8
    }
}

// --- Mode 0: sprinkles -----------------------------------------------------

/// Each sprinkle flashes on its own: a soft 0.8 s twinkle, then darkness,
/// repeating every 2.6 to 6.6 s (different for every LED, fixed per LED).
pub const TWINKLE_MS: u32 = 800;
pub const SPRINKLE_PEAK: u8 = 220;

pub fn sprinkles(t: u32, out: &mut Frame) {
    for (i, v) in out.iter_mut().enumerate() {
        let h = hash(i as u32 ^ 0x5eed);
        let period = 2_600 + h % 4_000;
        let local = (t.wrapping_add(h >> 8)) % period;
        *v = if local < TWINKLE_MS {
            let phase = (local * 65_536 / TWINKLE_MS) as u16;
            (hump(phase) as u32 * SPRINKLE_PEAK as u32 / 255) as u8
        } else {
            0
        };
    }
}

// --- Mode 1: glaze wave round the ring ------------------------------------

/// One lap every 3 s, anticlockwise (seen from the front), with a fading
/// tail 100 degrees long behind the bright head.
pub const WAVE_LAP_MS: u32 = 3_000;
pub const WAVE_TAIL_DEG: u32 = 100;

pub fn wave(t: u32, out: &mut Frame) {
    // Head angle in hundredths of a degree.
    let head = (t % WAVE_LAP_MS) * 36_000 / WAVE_LAP_MS;
    for (v, led) in out.iter_mut().zip(LEDS.iter()) {
        let behind = (head + 36_000 - led.angle_deg as u32 * 100) % 36_000;
        *v = fade(behind, WAVE_TAIL_DEG * 100);
    }
}

// --- Mode 2: radial pulse ---------------------------------------------------

/// A ring of light grows from the hole to the outer edge every 1.8 s, then
/// a short pause before the next.
pub const PULSE_MS: u32 = 1_800;
/// Half-width of the bright ring, micrometres (about one ring spacing).
pub const PULSE_WIDTH_UM: u32 = 1_800;

pub fn radial_pulse(t: u32, out: &mut Frame) {
    let p = t % PULSE_MS;
    // Travel from a little inside the inner ring to a little outside the
    // outer one, so the pulse fades in and out instead of popping.
    let from = R_MIN_UM - PULSE_WIDTH_UM;
    let to = R_MAX_UM + PULSE_WIDTH_UM;
    let r = from + (to - from) * p / PULSE_MS;
    for (v, led) in out.iter_mut().zip(LEDS.iter()) {
        *v = fade(led.r_um.abs_diff(r), PULSE_WIDTH_UM);
    }
}

// --- Mode 3: icing drip -----------------------------------------------------

/// A slow band of light slides from the top of the donut to the bottom over
/// 7 s, then starts again. Its lower edge (the "drip front") is wavy, a
/// little lower in some places than others, and it leaves a fading trail.
pub const DRIP_MS: u32 = 7_000;
pub const DRIP_TRAIL_UM: u32 = 14_000;
/// How far (micrometres) the front can hang below its average line.
pub const DRIP_WOBBLE_UM: u32 = 5_000;
const TOP_UM: i32 = 22_860 + DRIP_WOBBLE_UM as i32 + 500;
const BOTTOM_UM: i32 = -22_860 - DRIP_TRAIL_UM as i32;

/// How far below the average front the drip hangs at horizontal position
/// `x_um`: a few fixed "drips" across the width, from the hash.
fn wobble(x_um: i32) -> u32 {
    // 6 mm wide columns, each with its own depth.
    let col = (x_um + 30_000) / 6_000;
    hash(col as u32 ^ 0xd21b) % DRIP_WOBBLE_UM
}

pub fn icing_drip(t: u32, out: &mut Frame) {
    let p = (t % DRIP_MS) as i64;
    let front = TOP_UM as i64 - (TOP_UM - BOTTOM_UM) as i64 * p / DRIP_MS as i64;
    for (v, led) in out.iter_mut().zip(LEDS.iter()) {
        let f = front - wobble(led.x_um) as i64;
        // Above the front: lit, fading with distance. Below: dark.
        let above = led.y_um as i64 - f;
        *v = if above < 0 {
            0
        } else {
            fade(above as u32, DRIP_TRAIL_UM)
        };
    }
}

/// Boot glow: every sprinkle at full level (the budget then dims it evenly).
pub const fn boot_frame() -> Frame {
    [255; LED_COUNT]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lit(f: &Frame) -> usize {
        f.iter().filter(|&&v| v > 0).count()
    }

    #[test]
    fn gamma_endpoints_and_monotone() {
        assert_eq!(gamma(0), 0);
        assert_eq!(gamma(1), 1);
        assert_eq!(gamma(255), 255);
        assert_eq!(gamma(128), 65);
        for l in 1..=255u8 {
            assert!(gamma(l) >= gamma(l - 1));
        }
    }

    #[test]
    fn hump_shape() {
        assert_eq!(hump(0), 0);
        assert_eq!(hump(0x8000), 255);
        assert!(hump(0xFFFF) <= 1);
        assert!(hump(0x4000).abs_diff(hump(0xC000)) <= 1);
        let mut prev = 0;
        for p in (0..0x8000u32).step_by(256) {
            let h = hump(p as u16);
            assert!(h >= prev);
            prev = h;
        }
    }

    #[test]
    fn sprinkles_twinkle_independently() {
        let mut f = [0; LED_COUNT];
        let mut ever = [false; LED_COUNT];
        let mut counts = std::vec::Vec::new();
        for t in (0..20_000).step_by(50) {
            sprinkles(t, &mut f);
            counts.push(lit(&f));
            for (e, &v) in ever.iter_mut().zip(f.iter()) {
                *e |= v > 0;
            }
            assert!(f.iter().all(|&v| v <= SPRINKLE_PEAK));
        }
        assert!(ever.iter().all(|&e| e), "every sprinkle twinkles in 20 s");
        // Never all dark, never all lit: a scattered twinkle.
        assert!(counts.iter().all(|&n| n > 5 && n < 80), "{counts:?}");
    }

    #[test]
    fn wave_head_moves_anticlockwise() {
        let mut f = [0; LED_COUNT];
        for (t, deg) in [(0, 0u16), (750, 90), (1_500, 180), (2_250, 270)] {
            wave(t, &mut f);
            for (led, &v) in LEDS.iter().zip(f.iter()) {
                if led.angle_deg == deg {
                    assert_eq!(v, 255, "t={t} {}", led.name);
                }
                // 10 degrees ahead of the head is dark.
                if led.angle_deg == (deg + 10) % 360 {
                    assert_eq!(v, 0, "t={t} {}", led.name);
                }
            }
        }
        // Roughly 100/360 of the LEDs are lit.
        wave(1_000, &mut f);
        assert!((30..=50).contains(&lit(&f)), "{}", lit(&f));
    }

    #[test]
    fn wave_wraps_seamlessly() {
        let (mut a, mut b) = ([0; LED_COUNT], [0; LED_COUNT]);
        wave(0, &mut a);
        wave(WAVE_LAP_MS, &mut b);
        assert_eq!(a, b);
    }

    #[test]
    fn pulse_moves_outward() {
        let mut f = [0; LED_COUNT];
        let mut peak_r = std::vec::Vec::new();
        for t in (200..1_600).step_by(200) {
            radial_pulse(t, &mut f);
            let (i, _) = f.iter().enumerate().max_by_key(|(_, v)| **v).unwrap();
            peak_r.push(LEDS[i].r_um);
            // Same radius, same brightness: the pulse is round.
            for (a, va) in LEDS.iter().zip(f.iter()) {
                for (b, vb) in LEDS.iter().zip(f.iter()) {
                    if a.r_um == b.r_um {
                        assert_eq!(va, vb);
                    }
                }
            }
        }
        assert!(peak_r.windows(2).all(|w| w[1] >= w[0]), "{peak_r:?}");
        assert!(peak_r.first() < peak_r.last());
    }

    #[test]
    fn pulse_starts_and_ends_dark() {
        let mut f = [0; LED_COUNT];
        radial_pulse(0, &mut f);
        assert_eq!(lit(&f), 0);
        radial_pulse(PULSE_MS - 1, &mut f);
        assert_eq!(lit(&f), 0);
    }

    #[test]
    fn drip_moves_down() {
        let mut f = [0; LED_COUNT];
        icing_drip(0, &mut f);
        assert_eq!(lit(&f), 0, "starts above the donut");
        let mut lowest = std::vec::Vec::new();
        for t in (1_000..6_000).step_by(1_000) {
            icing_drip(t, &mut f);
            assert!(lit(&f) > 0, "t={t}");
            let low = LEDS
                .iter()
                .zip(f.iter())
                .filter(|(_, v)| **v > 0)
                .map(|(l, _)| l.y_um)
                .min()
                .unwrap();
            lowest.push(low);
        }
        assert!(lowest.windows(2).all(|w| w[1] <= w[0]), "{lowest:?}");
        icing_drip(DRIP_MS - 1, &mut f);
        assert_eq!(lit(&f), 0, "ends below the donut");
    }

    #[test]
    fn drip_front_is_wavy() {
        let depths: std::collections::BTreeSet<u32> = (-4..4).map(|c| wobble(c * 6_000)).collect();
        assert!(depths.len() > 3);
    }

    #[test]
    fn animations_survive_timer_wrap() {
        let mut f = [0; LED_COUNT];
        for t in [u32::MAX - 5, u32::MAX] {
            sprinkles(t, &mut f);
            wave(t, &mut f);
            radial_pulse(t, &mut f);
            icing_drip(t, &mut f);
        }
    }
}
