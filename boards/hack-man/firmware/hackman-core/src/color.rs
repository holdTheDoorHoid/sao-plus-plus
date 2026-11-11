//! Colour type and integer colour math (no floats, so it is cheap on the
//! ESP32-C3, which has no FPU).

/// One RGB colour, 0..=255 per channel, in "design" units (before global
/// brightness is applied).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub const fn new(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b }
    }

    pub const OFF: Rgb = Rgb::new(0, 0, 0);
    pub const WHITE: Rgb = Rgb::new(255, 255, 255);
    pub const GREEN: Rgb = Rgb::new(0, 255, 0);

    /// Scale every channel by `level / 255`, rounding so that `level == 255`
    /// returns the colour unchanged and `level == 0` returns black.
    pub const fn scale(self, level: u8) -> Rgb {
        Rgb::new(
            scale8(self.r, level),
            scale8(self.g, level),
            scale8(self.b, level),
        )
    }

    /// Linear blend: `t == 0` gives `self`, `t == 255` gives `other`.
    pub const fn lerp(self, other: Rgb, t: u8) -> Rgb {
        Rgb::new(
            lerp8(self.r, other.r, t),
            lerp8(self.g, other.g, t),
            lerp8(self.b, other.b, t),
        )
    }

    /// Bytes in the order the SK6805 / WS2812 shifts them in: G, R, B.
    pub const fn to_grb(self) -> [u8; 3] {
        [self.g, self.r, self.b]
    }

    pub const fn is_off(self) -> bool {
        self.r == 0 && self.g == 0 && self.b == 0
    }
}

/// `v * level / 255`, rounded to nearest, exact at both ends.
pub const fn scale8(v: u8, level: u8) -> u8 {
    let p = v as u16 * level as u16;
    // (p + 127) / 255 without a division: standard trick, exact for 0..=65025.
    let p = p + 128;
    ((p + (p >> 8)) >> 8) as u8
}

const fn lerp8(a: u8, b: u8, t: u8) -> u8 {
    let a = a as i32;
    let b = b as i32;
    let t = t as i32;
    let v = a + ((b - a) * t + if b >= a { 127 } else { -127 }) / 255;
    v as u8
}

/// Hue wheel: `hue` 0..=255 covers one full turn (red -> green -> blue -> red),
/// full saturation and value. Integer-only.
pub const fn hue(hue: u8) -> Rgb {
    let region = hue / 43; // 0..=5
    let rem = (hue - region * 43) as u16 * 6; // 0..=252
    let up = rem as u8;
    let down = 255 - up;
    match region {
        0 => Rgb::new(255, up, 0),
        1 => Rgb::new(down, 255, 0),
        2 => Rgb::new(0, 255, up),
        3 => Rgb::new(0, down, 255),
        4 => Rgb::new(up, 0, 255),
        _ => Rgb::new(255, 0, down),
    }
}

/// Perceptual brightness curve (approximately gamma 2.2) for fades, so a
/// linear ramp in time looks like a linear ramp to the eye.
pub const fn gamma(v: u8) -> u8 {
    // Quadratic approximation of gamma 2.2: v^2 / 255, with a small linear
    // floor so the bottom of a fade does not snap off.
    let sq = (v as u16 * v as u16 + 127) / 255;
    let lin = v as u16 / 16;
    let out = if sq > lin { sq } else { lin };
    out as u8
}

/// Triangle wave: rises 0 -> 255 over the first half of `period`, falls back
/// over the second half. Used for breathing and chomping effects.
pub const fn triangle(t_ms: u32, period_ms: u32) -> u8 {
    if period_ms < 2 {
        return 255;
    }
    let p = t_ms % period_ms;
    let half = period_ms / 2;
    let v = if p < half {
        p as u64 * 255 / half as u64
    } else {
        (period_ms - p) as u64 * 255 / (period_ms - half) as u64
    };
    if v > 255 { 255 } else { v as u8 }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scale_endpoints_are_exact() {
        for v in 0..=255u8 {
            assert_eq!(scale8(v, 255), v);
            assert_eq!(scale8(v, 0), 0);
            assert_eq!(scale8(255, v), v);
        }
    }

    #[test]
    fn scale_rounds_to_nearest() {
        for v in 0..=255u16 {
            for l in [1u16, 17, 40, 128, 200, 254] {
                let exact = (v * l) as f32 / 255.0;
                let got = scale8(v as u8, l as u8) as f32;
                assert!((got - exact).abs() <= 0.5 + 1e-3, "v={v} l={l}");
            }
        }
    }

    #[test]
    fn grb_order() {
        assert_eq!(Rgb::new(1, 2, 3).to_grb(), [2, 1, 3]);
    }

    #[test]
    fn lerp_endpoints() {
        let a = Rgb::new(10, 200, 30);
        let b = Rgb::new(250, 0, 100);
        assert_eq!(a.lerp(b, 0), a);
        assert_eq!(a.lerp(b, 255), b);
        let mid = a.lerp(b, 128);
        assert!(mid.r > 120 && mid.r < 135);
    }

    #[test]
    fn hue_primaries_and_full_saturation() {
        assert_eq!(hue(0), Rgb::new(255, 0, 0));
        assert_eq!(hue(86).g, 255);
        assert_eq!(hue(172).b, 255);
        for h in 0..=255u8 {
            let c = hue(h);
            // Always fully saturated: one channel at max, one near zero.
            let max = c.r.max(c.g).max(c.b);
            let min = c.r.min(c.g).min(c.b);
            assert_eq!(max, 255, "h={h}");
            assert!(min <= 6, "h={h} {c:?}");
        }
    }

    #[test]
    fn gamma_is_monotonic_with_fixed_ends() {
        assert_eq!(gamma(0), 0);
        assert_eq!(gamma(255), 255);
        for v in 1..=255u8 {
            assert!(gamma(v) >= gamma(v - 1));
        }
    }

    #[test]
    fn triangle_shape() {
        assert_eq!(triangle(0, 1000), 0);
        assert_eq!(triangle(500, 1000), 255);
        assert_eq!(triangle(1000, 1000), 0);
        assert!(triangle(250, 1000) > 120 && triangle(250, 1000) < 135);
    }
}
