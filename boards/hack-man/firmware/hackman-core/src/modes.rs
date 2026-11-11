//! The four built-in light shows, selected with the mode button.

use crate::color::{gamma, hue};
use crate::palette::CHARACTERS;
use crate::{Frame, LED_COUNT, Rgb, attract, chain_index_of_front};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// Mode 0 (default): arcade attract-mode story, see [`crate::attract`].
    Attract,
    /// Mode 1: slow hue cycle (a gentle rainbow drifting across the five).
    HueCycle,
    /// Mode 2: discrete Larson scanner whose colour slowly changes.
    Larson,
    /// Mode 3: slower, smooth Larson scanner in each character's own colour.
    ActorLarson,
}

impl Mode {
    pub const ALL: [Mode; 4] = [
        Mode::Attract,
        Mode::HueCycle,
        Mode::Larson,
        Mode::ActorLarson,
    ];

    pub const fn next(self) -> Mode {
        match self {
            Mode::Attract => Mode::HueCycle,
            Mode::HueCycle => Mode::Larson,
            Mode::Larson => Mode::ActorLarson,
            Mode::ActorLarson => Mode::Attract,
        }
    }

    pub const fn number(self) -> u8 {
        match self {
            Mode::Attract => 0,
            Mode::HueCycle => 1,
            Mode::Larson => 2,
            Mode::ActorLarson => 3,
        }
    }

    /// Frame at `t_ms` since the mode was entered, in design units.
    pub fn render(self, t_ms: u32) -> Frame {
        match self {
            Mode::Attract => attract::frame(t_ms),
            Mode::HueCycle => hue_cycle(t_ms),
            Mode::Larson => larson(t_ms),
            Mode::ActorLarson => actor_larson(t_ms),
        }
    }
}

/// Mode 1: one trip round the colour wheel takes this long.
pub const HUE_CYCLE_MS: u32 = 12_000;
/// Mode 1: hue offset between neighbouring characters (256 = full wheel).
pub const HUE_SPREAD: u8 = 14;

/// Mode 2: time on each position.
pub const LARSON_STEP_MS: u32 = 120;
/// Mode 2: one trip round the colour wheel takes this long.
pub const LARSON_HUE_MS: u32 = 30_000;

/// Mode 3: one sweep left-to-right-and-back takes this long.
pub const ACTOR_SWEEP_MS: u32 = 5_000;
/// Mode 3: how far (in LEDs) the glow reaches either side of the scanner.
pub const ACTOR_GLOW_WIDTH: u32 = 3;

fn hue_at(t_ms: u32, period_ms: u32) -> u8 {
    ((t_ms % period_ms) as u64 * 256 / period_ms as u64) as u8
}

fn hue_cycle(t_ms: u32) -> Frame {
    let base = hue_at(t_ms, HUE_CYCLE_MS);
    let mut f = [Rgb::OFF; LED_COUNT];
    for pos in 0..LED_COUNT {
        f[chain_index_of_front(pos)] = hue(base.wrapping_add(HUE_SPREAD * pos as u8));
    }
    f
}

/// Bounce sequence of front positions: 0 1 2 3 4 3 2 1 | 0 1 ...
pub fn larson_position(step: u32) -> usize {
    let period = 2 * (LED_COUNT as u32 - 1); // 8
    let s = step % period;
    (if s < LED_COUNT as u32 { s } else { period - s }) as usize
}

fn larson(t_ms: u32) -> Frame {
    let pos = larson_position(t_ms / LARSON_STEP_MS);
    let mut f = [Rgb::OFF; LED_COUNT];
    f[chain_index_of_front(pos)] = hue(hue_at(t_ms, LARSON_HUE_MS));
    f
}

fn actor_larson(t_ms: u32) -> Frame {
    // Scanner position in 1/256ths of an LED, bouncing 0 ..= 4*256.
    let span = (LED_COUNT as u32 - 1) * 256;
    let p = (t_ms % ACTOR_SWEEP_MS) as u64 * (2 * span) as u64 / ACTOR_SWEEP_MS as u64;
    let p = p as u32;
    let x = if p <= span { p } else { 2 * span - p };

    let width = ACTOR_GLOW_WIDTH * 256 / 2; // fade to zero this far away
    let mut f = [Rgb::OFF; LED_COUNT];
    for pos in 0..LED_COUNT {
        let centre = pos as u32 * 256;
        let d = centre.abs_diff(x);
        let k = if d >= width { 0 } else { 255 - d * 255 / width } as u8;
        let idx = chain_index_of_front(pos);
        f[idx] = CHARACTERS[idx].scale(gamma(k));
    }
    f
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mode_cycle_visits_all_and_wraps() {
        let mut m = Mode::Attract;
        for (i, expect) in Mode::ALL.iter().enumerate() {
            assert_eq!(m, *expect);
            assert_eq!(m.number() as usize, i);
            m = m.next();
        }
        assert_eq!(m, Mode::Attract);
    }

    #[test]
    fn hue_cycle_changes_slowly_and_lights_all() {
        let a = hue_cycle(0);
        assert!(a.iter().all(|c| !c.is_off()));
        let b = hue_cycle(HUE_CYCLE_MS / 2);
        assert_ne!(a, b);
        assert_eq!(hue_cycle(5), hue_cycle(HUE_CYCLE_MS + 5));
        // 16 ms (one frame) never moves the hue by more than one wheel step.
        for t in (0..HUE_CYCLE_MS).step_by(16) {
            let d = hue_at(t + 16, HUE_CYCLE_MS).wrapping_sub(hue_at(t, HUE_CYCLE_MS));
            assert!(d <= 1, "t={t}");
        }
    }

    #[test]
    fn larson_bounces_end_to_end() {
        let seq: std::vec::Vec<usize> = (0..10).map(larson_position).collect();
        assert_eq!(seq, [0, 1, 2, 3, 4, 3, 2, 1, 0, 1]);
    }

    #[test]
    fn larson_is_discrete_one_led() {
        for t in (0..5_000).step_by(37) {
            let lit = larson(t).iter().filter(|c| !c.is_off()).count();
            assert_eq!(lit, 1, "t={t}");
        }
        // Starts at Pac-Man (front position 0 = chain index 4).
        assert!(!larson(0)[crate::PACMAN].is_off());
        // Hue changes over time.
        assert_ne!(
            larson(0)[crate::PACMAN],
            larson(LARSON_HUE_MS / 3 + 8 * LARSON_STEP_MS * 10)[crate::PACMAN]
        );
    }

    #[test]
    fn actor_larson_uses_character_colours_and_fades() {
        let f = actor_larson(0);
        assert_eq!(f[crate::PACMAN], CHARACTERS[crate::PACMAN]);
        assert!(f[crate::PINK].is_off());
        // Half-way through the sweep the scanner is at the far right (pink).
        let f = actor_larson(ACTOR_SWEEP_MS / 2);
        assert_eq!(f[crate::PINK], CHARACTERS[crate::PINK]);
        // Every lit colour is a dimmed copy of that character's colour:
        // no channel lit that the character does not have.
        for t in (0..ACTOR_SWEEP_MS).step_by(50) {
            let f = actor_larson(t);
            for i in 0..LED_COUNT {
                let c = f[i];
                let own = CHARACTERS[i];
                assert!(c.r <= own.r && c.g <= own.g && c.b <= own.b);
            }
        }
        // Fades: brightness of a middle LED takes intermediate values.
        let mids: std::vec::Vec<u8> = (0..ACTOR_SWEEP_MS)
            .step_by(20)
            .map(|t| actor_larson(t)[crate::ORANGE].r)
            .collect();
        assert!(mids.iter().any(|&v| v > 20 && v < 200));
    }
}
