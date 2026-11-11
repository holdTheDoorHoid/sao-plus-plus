//! Mode 0: the arcade "attract mode", told with five lights.
//!
//! Each LED sits behind one character, so the story is told by what colour
//! each character is at each moment, not by movement. One loop lasts
//! [`LOOP_MS`] (20 s). Timeline, in seconds from the start of the loop:
//!
//! | time        | what you see                                                        |
//! |-------------|---------------------------------------------------------------------|
//! | 0.0 - 2.5   | Cast intro: red, pink, cyan, orange ghosts fade in one by one (0.5 s apart, the order the arcade introduces them), then Pac-Man. |
//! | 2.5 - 6.0   | Chase: ghosts in their colours with a faint shimmer (their wavy skirts); Pac-Man "chomps" (yellow pulses 4 times a second). |
//! | 6.0         | Power pellet: Pac-Man flashes white, every ghost turns blue.         |
//! | 6.0 - 13.0  | Frightened: ghosts blue. From 11.0 s the still-blue ghosts flash blue/white (they are about to recover). |
//! | 7.0         | Red ghost eaten: its light shows the cyan "points" colour for 0.6 s while Pac-Man vanishes (the arcade freezes and hides Pac-Man to show the score). Then only dim "eyes" remain while they run home. |
//! | 8.5         | Orange ghost eaten (same sequence).                                  |
//! | 10.0        | Cyan ghost eaten (same sequence).                                    |
//! | eaten + 2.0 | That ghost is back in its own colour, no longer frightened.          |
//! | 13.0        | Pink ghost (never caught) recovers.                                  |
//! | 13.0 - 16.0 | Chase again.                                                         |
//! | 16.0 - 17.0 | Caught! Everything freezes: chomping stops.                          |
//! | 17.0 - 18.5 | Ghosts vanish; Pac-Man shrinks away (fades out in steps).            |
//! | 18.5 - 18.7 | The little "pop" at the end of the death animation (dim white).     |
//! | 18.7 - 20.0 | Dark, then the loop starts again.                                    |

use crate::color::{gamma, triangle};
use crate::palette::*;
use crate::{CYAN, Frame, LED_COUNT, ORANGE, PACMAN, PINK, RED, Rgb};

pub const LOOP_MS: u32 = 20_000;

// Phase boundaries (ms from loop start).
pub const INTRO_END: u32 = 2_500;
pub const PELLET_AT: u32 = 6_000;
pub const PELLET_FLASH_MS: u32 = 150;
pub const FLASH_FROM: u32 = 11_000;
pub const FRIGHT_END: u32 = 13_000;
pub const CAUGHT_AT: u32 = 16_000;
pub const DEATH_AT: u32 = 17_000;
pub const POP_AT: u32 = 18_500;
pub const DARK_AT: u32 = 18_700;

/// How long the "points" colour shows after a ghost is eaten.
pub const SCORE_MS: u32 = 600;
/// From being eaten to being back in colour.
pub const RESPAWN_MS: u32 = 2_000;
/// Blue/white flash half-period near the end of the frightened time.
pub const FLASH_HALF_MS: u32 = 250;
/// Pac-Man chomp period.
pub const CHOMP_MS: u32 = 250;

/// When each ghost is eaten (chain index, time). Pink is never caught.
pub const EATEN: [(usize, u32); 3] = [(RED, 7_000), (ORANGE, 8_500), (CYAN, 10_000)];

/// When each character appears during the intro (chain index, time).
const INTRO: [(usize, u32); LED_COUNT] = [
    (RED, 0),
    (PINK, 500),
    (CYAN, 1_000),
    (ORANGE, 1_500),
    (PACMAN, 2_000),
];
const INTRO_FADE_MS: u32 = 250;

/// The frame at time `t_ms` since the mode started (wraps every [`LOOP_MS`]).
/// Returned in design units; the caller applies global brightness.
pub fn frame(t_ms: u32) -> Frame {
    let t = t_ms % LOOP_MS;
    let mut f = [Rgb::OFF; LED_COUNT];

    if t < INTRO_END {
        for &(idx, at) in INTRO.iter() {
            if t >= at {
                let k = ((t - at).min(INTRO_FADE_MS) * 255 / INTRO_FADE_MS) as u8;
                f[idx] = CHARACTERS[idx].scale(gamma(k));
            }
        }
        return f;
    }

    if t >= DEATH_AT {
        if t < POP_AT {
            // Shrinking: 8 visible steps, each a bit dimmer.
            let progress = (t - DEATH_AT) * 8 / (POP_AT - DEATH_AT); // 0..=7
            let level = 255 - (progress * 255 / 8) as u8;
            f[PACMAN] = PACMAN_YELLOW.scale(gamma(level));
        } else if t < DARK_AT {
            f[PACMAN] = Rgb::new(120, 120, 120);
        }
        return f;
    }

    let frozen = (CAUGHT_AT..DEATH_AT).contains(&t);

    // Ghosts.
    for idx in [PINK, CYAN, ORANGE, RED] {
        f[idx] = ghost(idx, t, frozen);
    }

    // Pac-Man.
    let score_freeze = EATEN.iter().any(|&(_, at)| t >= at && t < at + SCORE_MS);
    f[PACMAN] = if score_freeze {
        Rgb::OFF
    } else if (PELLET_AT..PELLET_AT + PELLET_FLASH_MS).contains(&t) {
        Rgb::WHITE
    } else if frozen {
        PACMAN_YELLOW
    } else {
        chomp(t)
    };
    f
}

fn chomp(t: u32) -> Rgb {
    // Pulse between ~35 % and 100 %: mouth open / closed.
    let k = 90 + (triangle(t, CHOMP_MS) as u32 * 165 / 255) as u8;
    PACMAN_YELLOW.scale(k)
}

fn shimmer(c: Rgb, t: u32, idx: usize) -> Rgb {
    // Two-frame skirt animation, offset per ghost so they do not pulse together.
    if ((t + idx as u32 * 37) / 125).is_multiple_of(2) {
        c
    } else {
        c.scale(215)
    }
}

fn ghost(idx: usize, t: u32, frozen: bool) -> Rgb {
    let own = CHARACTERS[idx];
    let normal = if frozen { own } else { shimmer(own, t, idx) };

    if !(PELLET_AT..FRIGHT_END).contains(&t) {
        return normal;
    }
    if let Some(&(_, at)) = EATEN.iter().find(|&&(i, _)| i == idx)
        && t >= at
    {
        return if t < at + SCORE_MS {
            SCORE
        } else if t < at + RESPAWN_MS {
            EYES
        } else {
            normal
        };
    }
    // Still frightened.
    if t >= FLASH_FROM && ((t - FLASH_FROM) / FLASH_HALF_MS) % 2 == 1 {
        SCARED_FLASH
    } else {
        SCARED_BLUE
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn intro_reveals_characters_in_order() {
        let f = frame(100);
        assert!(!f[RED].is_off());
        assert!(f[PINK].is_off() && f[CYAN].is_off() && f[ORANGE].is_off() && f[PACMAN].is_off());
        let f = frame(1_300);
        assert!(!f[RED].is_off() && !f[PINK].is_off() && !f[CYAN].is_off());
        assert!(f[ORANGE].is_off() && f[PACMAN].is_off());
        let f = frame(2_400);
        assert!(f.iter().all(|c| !c.is_off()));
        // Fully faded in once INTRO_FADE_MS has passed.
        assert_eq!(frame(400)[RED], BLINKY_RED);
    }

    #[test]
    fn chase_shows_character_colours() {
        let f = frame(3_000);
        for idx in [PINK, CYAN, ORANGE, RED] {
            let c = f[idx];
            assert!(
                c == CHARACTERS[idx] || c == CHARACTERS[idx].scale(215),
                "{idx}"
            );
        }
        // Pac-Man is yellow-ish (no blue) and actually chomps.
        assert_eq!(f[PACMAN].b, 0);
        let levels: std::vec::Vec<u8> = (0..CHOMP_MS)
            .step_by(10)
            .map(|d| frame(3_000 + d)[PACMAN].r)
            .collect();
        assert!(levels.iter().max().unwrap() - levels.iter().min().unwrap() > 100);
    }

    #[test]
    fn power_pellet_turns_ghosts_blue() {
        let f = frame(PELLET_AT + 10);
        assert_eq!(f[PACMAN], Rgb::WHITE);
        for idx in [PINK, CYAN, ORANGE, RED] {
            assert_eq!(f[idx], SCARED_BLUE);
        }
        assert_ne!(frame(PELLET_AT + PELLET_FLASH_MS + 10)[PACMAN], Rgb::WHITE);
    }

    #[test]
    fn ghosts_are_eaten_one_by_one() {
        // Red eaten: score colour, Pac-Man hidden.
        let f = frame(7_100);
        assert_eq!(f[RED], SCORE);
        assert!(f[PACMAN].is_off());
        assert_eq!(f[ORANGE], SCARED_BLUE);
        // Eyes travelling home.
        let f = frame(7_000 + SCORE_MS + 100);
        assert_eq!(f[RED], EYES);
        assert!(!f[PACMAN].is_off());
        // Red back in colour while pink is still frightened.
        let f = frame(9_100);
        assert!(f[RED] == BLINKY_RED || f[RED] == BLINKY_RED.scale(215));
        assert_eq!(f[PINK], SCARED_BLUE);
        assert_eq!(frame(8_600)[ORANGE], SCORE);
        assert_eq!(frame(10_100)[CYAN], SCORE);
    }

    #[test]
    fn frightened_ghosts_flash_near_the_end() {
        let a = frame(FLASH_FROM + 10)[PINK];
        let b = frame(FLASH_FROM + FLASH_HALF_MS + 10)[PINK];
        assert_eq!(a, SCARED_BLUE);
        assert_eq!(b, SCARED_FLASH);
        // Pink recovers at FRIGHT_END.
        let c = frame(FRIGHT_END + 10)[PINK];
        assert!(c == PINKY_PINK || c == PINKY_PINK.scale(215));
        // Before FLASH_FROM there is no white.
        for t in (PELLET_AT..FLASH_FROM).step_by(50) {
            assert_ne!(frame(t)[PINK], SCARED_FLASH, "t={t}");
        }
    }

    #[test]
    fn caught_freezes_then_death() {
        let a = frame(CAUGHT_AT + 10);
        let b = frame(CAUGHT_AT + 400);
        assert_eq!(a, b, "frozen frame must not change");
        assert_eq!(a[PACMAN], PACMAN_YELLOW);
        let d = frame(DEATH_AT + 10);
        for idx in [PINK, CYAN, ORANGE, RED] {
            assert!(d[idx].is_off());
        }
        assert!(!d[PACMAN].is_off());
        // Pac-Man gets dimmer through the death animation.
        let mut prev = 255u8;
        for t in (DEATH_AT..POP_AT).step_by(100) {
            let r = frame(t)[PACMAN].r;
            assert!(r <= prev, "t={t}");
            prev = r;
        }
        assert!(frame(DARK_AT + 10).iter().all(|c| c.is_off()));
    }

    #[test]
    fn loop_wraps() {
        assert_eq!(frame(123), frame(LOOP_MS + 123));
        assert_eq!(frame(7_100), frame(3 * LOOP_MS + 7_100));
    }

    #[test]
    fn no_overlapping_eat_windows() {
        for w in EATEN.windows(2) {
            assert!(w[0].1 + SCORE_MS <= w[1].1);
        }
        for &(_, at) in EATEN.iter() {
            assert!(at >= PELLET_AT && at + SCORE_MS < FRIGHT_END);
        }
    }
}
