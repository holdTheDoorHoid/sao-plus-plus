//! Board-independent logic for the Mad Cat Backpack, SAO++ edition.
//!
//! The default show (mode 0) reproduces what the maker's own firmware does,
//! `mad_cat_backpack_v0.asm` (PIC16F1503 assembly, V1 of 04 Nov 2018) by
//! Peter Shabino (Wireb), <https://github.com/Wireb/Mad_Cat_Backpack>,
//! MIT licence, Copyright (c) 2018 Peter Shabino. This is a re-implementation
//! in Rust written from a reading of that program (what it shows, in what
//! order, for how long), not a line-by-line translation. See [`show`].
//!
//! Nothing in this crate touches hardware. The firmware crate (`backpack-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, button/switch levels and
//! received I2C bytes, and shows the levels it returns on the eight LEDs.
//! Everything in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod dim;
pub mod i2c;
pub mod input;
pub mod lfsr;
pub mod show;

/// Number of LEDs on the board.
pub const LED_COUNT: usize = 8;

/// Brightness of every LED, 0 = off, 255 = full on.
///
/// Index order is the maker's: 0 = left eye, 1 = right eye, 2..=7 = teeth 1
/// to 6, left to right, all as seen from the front of the cat. Board
/// references: D1 left eye, D2 right eye, D3..D8 teeth 1..6.
pub type Levels = [u8; LED_COUNT];

pub const LEFT_EYE: usize = 0;
pub const RIGHT_EYE: usize = 1;
/// Index of tooth `n` (1..=6, left to right): `TOOTH[n - 1]`.
pub const TOOTH: [usize; 6] = [2, 3, 4, 5, 6, 7];

pub const ALL_ON: Levels = [255; LED_COUNT];
pub const ALL_OFF: Levels = [0; LED_COUNT];

/// Firmware version (reported in the I2C status bytes).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
