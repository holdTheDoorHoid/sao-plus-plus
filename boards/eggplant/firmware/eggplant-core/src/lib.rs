//! Board-independent logic for the Eggplant SAO, SAO++ edition.
//!
//! The original is the DC Darknet "Official" Eggplant Emoji Shitty Add-on by
//! Krux / thedarknet (2018), <https://github.com/thedarknet/dc26-badge>, MIT
//! licence (see `../README.md` for the full notice). It ran on an ATtiny85.
//! This crate re-implements what his sketch did, in Rust, for a Seeed XIAO
//! ESP32: his five light shows plus "off", his I2C commands and memory map,
//! and his infection game. It was written from reading his code, not by
//! translating it line by line.
//!
//! Nothing in this crate touches hardware; everything is tested on a PC with
//! `cargo test`. The firmware crate (`eggplant-fw`) feeds [`app::App`] with
//! time, button and switch levels and I2C writes, and sets the two LED pins.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod fade;
pub mod input;
pub mod proto;
pub mod rng;
pub mod store;

/// This firmware's own version (the version string a badge reads stays the
/// maker's "1.0.0").
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
