//! Board-independent logic for the Hack-Man SAO, SAO++ edition.
//!
//! This is a clean re-implementation written from the public description of
//! the original add-on by InstantArcade (Bob),
//! <https://hackaday.io/project/198301-hack-man-sao>. The original ran on a
//! different microcontroller and its source code was never published, so none
//! of it is copied or ported here; only the described behaviour is reproduced.
//!
//! Nothing in this crate touches hardware. The firmware crate (`hackman-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, button/switch levels and
//! received I2C bytes, and writes the frames it returns to the LEDs. Everything
//! in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod attract;
pub mod color;
pub mod i2c;
pub mod input;
pub mod modes;

pub use color::Rgb;

/// Number of LEDs on the board.
pub const LED_COUNT: usize = 5;

/// One frame for the whole board, indexed by **chain index**: index 0 is the
/// first LED on the data line, which is the RIGHTMOST character seen from the
/// front (the pink ghost). Index 4 is Pac-Man, on the far left.
pub type Frame = [Rgb; LED_COUNT];

/// Firmware version shown at boot (major in white, minor in green, in binary).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;

/// Brightness used for the built-in animations, 0..=255. The LEDs run from
/// 3.3 V (and possibly a small LiPo), so this is kept modest. Raise it with
/// care: full white on all five SK6805s draws far more than an idle badge.
pub const DEFAULT_BRIGHTNESS: u8 = 48;

/// Chain indices of the characters (see [`Frame`]).
pub const PINK: usize = 0;
pub const CYAN: usize = 1;
pub const ORANGE: usize = 2;
pub const RED: usize = 3;
pub const PACMAN: usize = 4;

/// Chain index of the LED at front position `pos` (0 = leftmost, Pac-Man;
/// 4 = rightmost, pink ghost).
pub const fn chain_index_of_front(pos: usize) -> usize {
    LED_COUNT - 1 - pos
}

/// Character colours, indexed by chain index. These are tuned for an RGB LED
/// rather than copied from the arcade palette: the arcade's pink (255,184,255)
/// and orange (255,184,82) look almost white or yellow on an LED. They are a
/// first guess and should be adjusted by eye on a real board behind the
/// translucent characters.
pub mod palette {
    use crate::Rgb;
    pub const PACMAN_YELLOW: Rgb = Rgb::new(255, 170, 0);
    pub const BLINKY_RED: Rgb = Rgb::new(255, 0, 0);
    pub const CLYDE_ORANGE: Rgb = Rgb::new(255, 70, 0);
    pub const INKY_CYAN: Rgb = Rgb::new(0, 200, 255);
    pub const PINKY_PINK: Rgb = Rgb::new(255, 40, 120);
    /// Frightened ghosts.
    pub const SCARED_BLUE: Rgb = Rgb::new(0, 0, 255);
    /// The white half of the "about to recover" flash.
    pub const SCARED_FLASH: Rgb = Rgb::new(220, 220, 255);
    /// Eaten ghost: only the eyes travel home.
    pub const EYES: Rgb = Rgb::new(40, 40, 60);
    /// Points pop-up colour when a ghost is eaten (cyan in the arcade).
    pub const SCORE: Rgb = Rgb::new(0, 255, 255);

    /// Each character's own colour, by chain index.
    pub const CHARACTERS: crate::Frame = [
        PINKY_PINK,    // 0, rightmost
        INKY_CYAN,     // 1
        CLYDE_ORANGE,  // 2
        BLINKY_RED,    // 3
        PACMAN_YELLOW, // 4, leftmost
    ];
}

/// Apply a global brightness to a whole frame.
pub fn scale_frame(frame: &Frame, level: u8) -> Frame {
    let mut out = *frame;
    for c in out.iter_mut() {
        *c = c.scale(level);
    }
    out
}

/// Serialise a frame into the 15 bytes the LED chain expects (G, R, B per
/// LED, chain index 0 first).
pub fn frame_to_grb(frame: &Frame) -> [u8; LED_COUNT * 3] {
    let mut out = [0u8; LED_COUNT * 3];
    for (i, c) in frame.iter().enumerate() {
        out[i * 3..i * 3 + 3].copy_from_slice(&c.to_grb());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn front_positions_map_to_chain() {
        assert_eq!(chain_index_of_front(0), PACMAN);
        assert_eq!(chain_index_of_front(1), RED);
        assert_eq!(chain_index_of_front(2), ORANGE);
        assert_eq!(chain_index_of_front(3), CYAN);
        assert_eq!(chain_index_of_front(4), PINK);
    }

    #[test]
    fn grb_serialisation_puts_chain_index_0_first() {
        let mut f = [Rgb::OFF; LED_COUNT];
        f[0] = Rgb::new(0x11, 0x22, 0x33);
        f[4] = Rgb::new(0xAA, 0xBB, 0xCC);
        let b = frame_to_grb(&f);
        assert_eq!(&b[0..3], &[0x22, 0x11, 0x33]);
        assert_eq!(&b[12..15], &[0xBB, 0xAA, 0xCC]);
    }

    #[test]
    fn palette_order_matches_constants() {
        assert_eq!(palette::CHARACTERS[PACMAN], palette::PACMAN_YELLOW);
        assert_eq!(palette::CHARACTERS[RED], palette::BLINKY_RED);
        assert_eq!(palette::CHARACTERS[ORANGE], palette::CLYDE_ORANGE);
        assert_eq!(palette::CHARACTERS[CYAN], palette::INKY_CYAN);
        assert_eq!(palette::CHARACTERS[PINK], palette::PINKY_PINK);
    }
}
