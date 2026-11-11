//! The four built-in light shows, selected with the mode button.

use crate::color::{gamma, hue, triangle};
use crate::palette::MIST_GREEN;
use crate::{Frame, LED_COUNT, Rgb};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Mode 0 (default): the maker's icy shimmer, see [`crate::shimmer`].
    /// It has state, so [`crate::app::App`] renders it, not [`Mode::render`].
    Shimmer,
    /// Mode 1: slow green "fishbowl mist" pulse, drifting round the helmet.
    Mist,
    /// Mode 2: slow hue cycle.
    HueCycle,
    /// Mode 3: all LEDs off (the board stays awake and listens on I2C).
    Off,
}

impl Mode {
    pub const ALL: [Mode; 4] = [Mode::Shimmer, Mode::Mist, Mode::HueCycle, Mode::Off];

    pub const fn next(self) -> Mode {
        match self {
            Mode::Shimmer => Mode::Mist,
            Mode::Mist => Mode::HueCycle,
            Mode::HueCycle => Mode::Off,
            Mode::Off => Mode::Shimmer,
        }
    }

    pub const fn number(self) -> u8 {
        match self {
            Mode::Shimmer => 0,
            Mode::Mist => 1,
            Mode::HueCycle => 2,
            Mode::Off => 3,
        }
    }

    /// Frame at `t_ms` since the mode was entered, in design units, for the
    /// stateless modes. Returns all-off for [`Mode::Shimmer`].
    pub fn render(self, t_ms: u32) -> Frame {
        match self {
            Mode::Shimmer | Mode::Off => [Rgb::OFF; LED_COUNT],
            Mode::Mist => mist(t_ms),
            Mode::HueCycle => hue_cycle(t_ms),
        }
    }
}

/// Mode 1: one breath (dim -> bright -> dim) takes this long.
pub const MIST_PERIOD_MS: u32 = 6_000;
/// Mode 1: the dimmest point of a breath (0..=255, before gamma), so the
/// helmet never goes fully dark.
pub const MIST_FLOOR: u8 = 50;

/// Mode 2: one trip round the colour wheel takes this long.
pub const HUE_CYCLE_MS: u32 = 16_000;
/// Mode 2: hue offset between neighbouring LEDs (256 = full wheel).
pub const HUE_SPREAD: u8 = 16;

fn mist(t_ms: u32) -> Frame {
    let mut f = [Rgb::OFF; LED_COUNT];
    for (i, out) in f.iter_mut().enumerate() {
        // Each LED a quarter-breath behind the previous one, so the glow
        // seems to swirl slowly round the bowl.
        let phase = i as u32 * MIST_PERIOD_MS / LED_COUNT as u32;
        let tri = triangle(t_ms.wrapping_add(phase), MIST_PERIOD_MS) as u32;
        let level = MIST_FLOOR as u32 + tri * (255 - MIST_FLOOR as u32) / 255;
        *out = MIST_GREEN.scale(gamma(level as u8));
    }
    f
}

fn hue_at(t_ms: u32, period_ms: u32) -> u8 {
    ((t_ms % period_ms) as u64 * 256 / period_ms as u64) as u8
}

fn hue_cycle(t_ms: u32) -> Frame {
    let base = hue_at(t_ms, HUE_CYCLE_MS);
    let mut f = [Rgb::OFF; LED_COUNT];
    for (i, out) in f.iter_mut().enumerate() {
        *out = hue(base.wrapping_add(HUE_SPREAD * i as u8));
    }
    f
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mode_cycle_visits_all_and_wraps() {
        let mut m = Mode::Shimmer;
        for (i, expect) in Mode::ALL.iter().enumerate() {
            assert_eq!(m, *expect);
            assert_eq!(m.number() as usize, i);
            m = m.next();
        }
        assert_eq!(m, Mode::Shimmer);
    }

    #[test]
    fn mist_is_green_never_dark_and_breathes() {
        let mut min = 255u8;
        let mut max = 0u8;
        for t in (0..MIST_PERIOD_MS).step_by(20) {
            for c in mist(t) {
                assert!(c.g >= c.r && c.g >= c.b, "green dominates: {c:?}");
                assert!(!c.is_off(), "t={t}");
                min = min.min(c.g);
                max = max.max(c.g);
            }
        }
        assert_eq!(max, 255);
        assert!(min < 30, "dims well down: {min}");
        // Repeats every period, and the four LEDs are out of step.
        assert_eq!(mist(123), mist(MIST_PERIOD_MS + 123));
        let f = mist(0);
        assert_ne!(f[0], f[2]);
    }

    #[test]
    fn mist_is_slow() {
        // One 10 ms frame never jumps more than a few levels.
        for t in (0..MIST_PERIOD_MS).step_by(10) {
            let a = mist(t)[0].g as i32;
            let b = mist(t + 10)[0].g as i32;
            assert!((a - b).abs() <= 3, "t={t}");
        }
    }

    #[test]
    fn hue_cycle_changes_slowly_and_lights_all() {
        let a = hue_cycle(0);
        assert!(a.iter().all(|c| !c.is_off()));
        assert_ne!(a, hue_cycle(HUE_CYCLE_MS / 2));
        assert_eq!(hue_cycle(5), hue_cycle(HUE_CYCLE_MS + 5));
        for t in (0..HUE_CYCLE_MS).step_by(10) {
            let d = hue_at(t + 10, HUE_CYCLE_MS).wrapping_sub(hue_at(t, HUE_CYCLE_MS));
            assert!(d <= 1, "t={t}");
        }
    }

    #[test]
    fn off_is_off() {
        for t in [0, 1_000, 99_999] {
            assert_eq!(Mode::Off.render(t), [Rgb::OFF; LED_COUNT]);
        }
    }
}
