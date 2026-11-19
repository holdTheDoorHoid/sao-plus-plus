//! Board-independent logic for the TARS SAO, SAO++ edition.
//!
//! The maker's board (davedarko, 2024, <https://github.com/davedarko/TARS-SAO>,
//! MIT licence) ran Arduino sketches on an RP2040: a menu on the 160 x 80
//! display driven by six touch pads, a six-note "piano" that also colours the
//! screen, a click on every menu move, and a few stand-alone display demos
//! ("hack the planet", code rain, a typing scroller). This crate does the same
//! things, written fresh in Rust from reading his sketches; it is not a
//! line-by-line translation of them.
//!
//! Nothing here touches hardware. The firmware crate (`tars-fw`) reads the
//! touch chip and the switch, feeds [`app::App`], draws [`gfx::Frame`] to the
//! display with the bytes from [`st7735`], and plays the tones [`app::App`]
//! asks for. Everything in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod bitbang;
pub mod cap1206;
pub mod demos;
pub mod font;
pub mod gfx;
pub mod i2c;
pub mod input;
pub mod st7735;
pub mod tone;

/// Firmware version (reported in the I2C status bytes).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
