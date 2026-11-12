//! Board-independent logic for the Mr. Robot SAO, SAO++ edition: an "I2C
//! sound card". The badge sends a note number, the add-on plays it on its
//! sounder.
//!
//! The badge protocol keeps the maker's own, from his sketches
//! `SlaveMrRobot.ino` / `MasterMrRobot.ino` by davedarko (Dave Darko),
//! <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Mr%20Robot%20Badge>,
//! and adds a few commands on top that cannot be confused with his (see
//! [`i2c`]). This is a clean re-implementation in Rust of what his sketch
//! does, not a port of his code. The built-in tunes are new.
//!
//! Nothing in this crate touches hardware. The firmware crate (`mrrobot-fw`)
//! reads the pins, feeds [`app::App`] with timestamps, button/switch levels
//! and received I2C bytes, and hands the note it gets back to a
//! [`tone::ToneGen`], which owns the rule "silent means pin low". Everything
//! in here is unit-tested on the host with `cargo test`.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod i2c;
pub mod input;
pub mod notes;
pub mod tone;
pub mod tune;

pub use notes::Note;

/// Firmware version (reported in the I2C status bytes).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
