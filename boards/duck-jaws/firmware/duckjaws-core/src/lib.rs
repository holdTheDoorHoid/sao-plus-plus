//! Board-independent logic for the Duck Jaws SAO, SAO++ edition.
//!
//! Duck Jaws and Duck Bath are the two variants of the duckGLOW add-on by
//! Adrian Studer (astuder), <https://github.com/astuder/duckglow>: one
//! circuit, one firmware, two shapes. Duck Jaws has one thing more: four red
//! lights round the shark's mouth, which the maker calls the "background"
//! channel (the fourth value in each register group).
//!
//! So this crate is small. The I2C register map, the fader and the switch
//! debouncing are Duck Bath's (`duckbath-core`), used where they are. What is
//! here is the part that differs: [`app::App`] hands the fourth channel on to
//! the firmware instead of dropping it and answers with this board's own
//! text, and [`dimmer::Dimmer`] turns a brightness into an on/off pattern for
//! the plain red LEDs.
//!
//! NEVER COMPILED, like Duck Bath's firmware: see ../README.md.

#![no_std]

#[cfg(test)]
extern crate std;

pub mod app;
pub mod dimmer;

pub use duckbath_core::{Frame, LED_COUNT, Rgb};

/// Firmware version (printed on the serial log at start-up).
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;
