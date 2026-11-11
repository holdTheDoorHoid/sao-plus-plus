//! Board-independent logic for the Do Or Donut SAO, SAO++ edition.
//!
//! The board is by davedarko (Dave Darko), 2019,
//! <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Do%20Or%20DoNut>.
//! He published no firmware for it; everything here is new.
//!
//! Nothing in this crate touches hardware. The firmware crate (`donut-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, button/switch levels
//! and received I2C bytes, and sends the frames it returns to the LED driver
//! through [`is31fl3731`] over the software I2C bus in [`bitbang`].
//! Everything in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod anim;
pub mod app;
pub mod bitbang;
pub mod budget;
pub mod i2c;
pub mod input;
pub mod is31fl3731;
mod led_table;
pub mod leds;
pub mod modes;

/// Number of LEDs on the board.
pub const LED_COUNT: usize = 144;

/// One value per LED, in the maker's order: index 0..=71 are DA1..DA72,
/// 72..=143 are DB1..DB72 (see [`leds`]). Depending on where it is in the
/// pipeline it holds perceived levels (animations) or PWM values (output).
pub type Frame = [u8; LED_COUNT];

/// Firmware version (reported in the I2C status bytes).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
