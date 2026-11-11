//! Board-independent logic for the Mysterio SAO, SAO++ edition.
//!
//! The default light show (mode 0) reproduces the behaviour of the maker's own
//! Arduino sketch for this board, `strandtest.ino` by davedarko (Dave Darko),
//! <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/MysterioSAO>.
//! This is a clean re-implementation of what that sketch does, written in Rust
//! from a reading of it; it is not a port of his code. See [`shimmer`] for the
//! details and the (small) differences.
//!
//! Nothing in this crate touches hardware. The firmware crate (`mysterio-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, button/switch levels and
//! received I2C bytes, and writes the frames it returns to the LEDs. Everything
//! in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod color;
pub mod i2c;
pub mod input;
pub mod modes;
pub mod shimmer;

pub use color::Rgb;

/// Number of LEDs on the board.
pub const LED_COUNT: usize = 4;

/// One frame for the whole board, indexed by **chain index**: index 0 is the
/// first LED on the data line, board reference D1, the RIGHT-hand LED of the
/// helmet seen from the front (lower right). Indices 1, 2, 3 (D2, D3, D4) go
/// on round the helmet to the left. This is the same order the maker's sketch
/// numbers them in.
pub type Frame = [Rgb; LED_COUNT];

/// Firmware version (reported in the I2C status bytes).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;

/// Global brightness cap, 0..=255, applied on top of everything the board
/// shows (built-in modes, the boot glow and I2C colours alike), as a plain
/// multiplier: 255 would mean "no cap".
///
/// Why: the four LEDs run from the 3.3 V rail (badge or the XIAO's own
/// regulator; a LiPo can be hand-soldered to the module), below the LEDs'
/// rated 3.7 V, and the light has to shine through the board, so it cannot
/// be as low as Hack-Man's 48. 96 (about 38 %) on top of the maker's own
/// 200/255 gives about 30 % of full output in mode 0. A first guess: tune by
/// eye on a real board.
pub const GLOBAL_BRIGHTNESS_CAP: u8 = 96;

/// Colours used by the built-in modes (design units, before the cap).
pub mod palette {
    use crate::Rgb;
    /// Boot glow: pale blue-white.
    pub const BOOT_GLOW: Rgb = Rgb::new(170, 200, 255);
    /// Mode 1, "fishbowl mist": a slightly bluish green.
    pub const MIST_GREEN: Rgb = Rgb::new(30, 255, 80);
}

/// Apply a global brightness to a whole frame.
pub fn scale_frame(frame: &Frame, level: u8) -> Frame {
    let mut out = *frame;
    for c in out.iter_mut() {
        *c = c.scale(level);
    }
    out
}

/// Serialise a frame into the 12 bytes the LED chain expects (G, R, B per
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
    fn grb_serialisation_puts_chain_index_0_first() {
        let mut f = [Rgb::OFF; LED_COUNT];
        f[0] = Rgb::new(0x11, 0x22, 0x33);
        f[3] = Rgb::new(0xAA, 0xBB, 0xCC);
        let b = frame_to_grb(&f);
        assert_eq!(b.len(), 12);
        assert_eq!(&b[0..3], &[0x22, 0x11, 0x33]);
        assert_eq!(&b[9..12], &[0xBB, 0xAA, 0xCC]);
    }

    #[test]
    fn cap_is_a_real_cap() {
        let f = scale_frame(&[Rgb::WHITE; LED_COUNT], GLOBAL_BRIGHTNESS_CAP);
        assert!(f.iter().all(|c| *c == Rgb::new(96, 96, 96)));
        const { assert!(GLOBAL_BRIGHTNESS_CAP < 255) };
    }
}
