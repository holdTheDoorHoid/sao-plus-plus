//! Board-independent logic for the Duck Bath SAO, SAO++ edition.
//!
//! The original duckGLOW / duckBATH add-on is by Adrian Studer (astuder),
//! <https://github.com/astuder/duckglow>. It ran on a CH32V003 and lit one
//! ordinary RGB LED with three PWM outputs. This board has a different
//! controller and addressable LEDs, so this is new code: it reproduces what
//! the maker's README and firmware say the add-on *does* (the I2C register
//! map at address 0x6C and the per-channel fading), not how his code does it.
//!
//! Nothing in this crate touches hardware. The firmware crate (`duckbath-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, the power-switch level
//! and received I2C bytes, and writes the frames it returns to the LEDs.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod color;
pub mod fader;
pub mod input;
pub mod registers;

pub use color::Rgb;

/// Number of LEDs on the board. Both shine into the duck hole and always
/// show the same colour: together they stand in for the maker's single LED.
pub const LED_COUNT: usize = 2;

/// One frame for the whole board, in data-line order.
pub type Frame = [Rgb; LED_COUNT];

/// Firmware version (printed on the serial log at start-up).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;

/// Serialise a frame into the bytes the LED chain expects (G, R, B per LED).
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
    fn grb_order() {
        let f = [Rgb::new(0x11, 0x22, 0x33), Rgb::new(0xAA, 0xBB, 0xCC)];
        assert_eq!(frame_to_grb(&f), [0x22, 0x11, 0x33, 0xBB, 0xAA, 0xCC]);
    }
}
