//! Board-independent logic for the duckGLOW SAOs, SAO++ edition: Duck Bath
//! (an RGB LED under a rubber duck) and Duck Jaws (the same, plus red
//! "background" LEDs round a shark's mouth).
//!
//! The behaviour and the badge protocol follow the maker's own firmware,
//! `code/duckglow.c` by Adrian Studer (astuder), <https://github.com/astuder/duckglow>,
//! MIT licence, Copyright (c) 2024 Adrian Studer. This crate is a clean
//! re-implementation in Rust of what his firmware does (register map,
//! fading, WS2812 input, presets), written from reading it, not a
//! line-by-line port. See `../README.md` for what is the same and what is not.
//!
//! Nothing in this crate touches hardware. The firmware crate
//! (`duckglow-fw`) feeds [`app::App`] with timestamps, the power-switch level,
//! bytes from the I2C bus and pulse lengths from the SAO GPIO2 pin, and sets
//! the LED PWM to what it gets back. Everything here is unit-tested on the
//! host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod curve;
pub mod fader;
pub mod input;
pub mod presets;
pub mod regs;
pub mod ws2812;

/// Firmware version (in the docs text at register 0x00).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;

/// Number of LED channels this board drives: red, green, blue of the duck LED,
/// and on Duck Jaws the red background LEDs.
#[cfg(feature = "jaws")]
pub const CHANNELS_USED: usize = 4;
#[cfg(not(feature = "jaws"))]
pub const CHANNELS_USED: usize = 3;

/// The register map always has four channels (as the maker's does on both
/// boards); on Duck Bath the fourth simply drives nothing.
pub const CHANNELS: usize = 4;

/// 7-bit I2C address. House numbering: Duck Bath 0x22, Duck Jaws 0x23. With
/// the `maker-address` feature both answer at the maker's 0x6C (his solder
/// jumpers for 0x6D..0x6F are not on the SAO++ boards).
#[cfg(feature = "maker-address")]
pub const ADDRESS: u8 = 0x6C;
#[cfg(all(not(feature = "maker-address"), feature = "jaws"))]
pub const ADDRESS: u8 = 0x23;
#[cfg(all(not(feature = "maker-address"), not(feature = "jaws")))]
pub const ADDRESS: u8 = 0x22;

/// PWM resolution used throughout: 10 bits (0..=1023), as the maker's.
pub const PWM_MAX: u16 = 1023;

/// Board name, for the docs text and the start-up log.
#[cfg(feature = "jaws")]
pub const BOARD: &str = "Duck Jaws";
#[cfg(not(feature = "jaws"))]
pub const BOARD: &str = "Duck Bath";
