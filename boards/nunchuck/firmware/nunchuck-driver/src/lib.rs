//! Badge-side driver for the **SAO Nunchuck** (SAO++ edition).
//!
//! The SAO Nunchuck is a passive adapter: a Wii Nunchuk plugs onto its edge fingers and the badge's own I2C master
//! talks to the Nunchuk through the SAO header. There is no chip on the add-on, so this crate is meant to be linked
//! by the badge's firmware. It needs only an [`embedded_hal::i2c::I2c`] bus and an [`embedded_hal::delay::DelayNs`].
//!
//! What it does, in the order a badge uses it:
//! 1. [`Nunchuk::init`] wakes the Nunchuk in its plain (unencrypted) mode.
//! 2. [`Nunchuk::identify`] reads the 6-byte accessory id and checks it is a Nunchuk.
//! 3. [`Nunchuk::read`] fetches one 6-byte report and decodes it into a [`Reading`]:
//!    stick X/Y (0-255), three accelerometer axes (10 bits each), buttons C and Z.
//! 4. [`Stick`] turns raw stick values into signed, dead-banded steps for menus or cursors,
//!    and [`Buttons`] turns two readings into "pressed" / "released" events.
//!
//! The bus address is fixed by the Nunchuk itself: 0x52 ([`ADDRESS`]). Nothing on the add-on can change it.
//!
//! The report layout and wake-up sequence are the widely documented Wii-extension ones (the same that the libraries
//! the maker points to, WiiChuck and NintendoExtensionCtrl, use). This is a fresh implementation, not a port of
//! either library.
#![no_std]
#![deny(missing_docs)]

use embedded_hal::delay::DelayNs;
use embedded_hal::i2c::I2c;

/// 7-bit I2C address of every Wii extension controller, the Nunchuk included.
pub const ADDRESS: u8 = 0x52;

/// The accessory id a genuine Nunchuk (and most clones) answers with.
pub const NUNCHUK_ID: [u8; 6] = [0x00, 0x00, 0xA4, 0x20, 0x00, 0x00];

/// Microseconds to wait between asking for data and reading it. The Nunchuk needs a moment to fill its registers;
/// 200 us is a conservative figure that works on the controllers the common libraries were tested with.
pub const CONVERSION_DELAY_US: u32 = 200;

/// Microseconds to wait between the two wake-up writes.
pub const INIT_STEP_DELAY_US: u32 = 1_000;

/// Something went wrong talking to the Nunchuk.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error<E> {
    /// The I2C bus reported an error (most often: no Nunchuk plugged in, so nobody acknowledged 0x52).
    Bus(E),
    /// The bus worked but every byte came back 0xFF: the Nunchuk is not initialised, or was unplugged and plugged
    /// back in. Call [`Nunchuk::init`] again.
    NotReady,
    /// Something answered at 0x52 but it is not a Nunchuk (a Classic Controller, a guitar, ...). Its id is given.
    NotANunchuk([u8; 6]),
}

/// One decoded Nunchuk report.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Reading {
    /// Stick left/right, 0 (left) ..= 255 (right); about 128 at rest.
    pub joy_x: u8,
    /// Stick down/up, 0 (down) ..= 255 (up); about 128 at rest.
    pub joy_y: u8,
    /// Accelerometer X, 0 ..= 1023; about 512 when that axis is level.
    pub accel_x: u16,
    /// Accelerometer Y, 0 ..= 1023.
    pub accel_y: u16,
    /// Accelerometer Z, 0 ..= 1023.
    pub accel_z: u16,
    /// The round C button is held.
    pub c: bool,
    /// The big Z trigger is held.
    pub z: bool,
}

impl Reading {
    /// Decode the six bytes the Nunchuk sends (plain mode, as set up by [`Nunchuk::init`]).
    ///
    /// Byte 0 and 1 are the stick. Bytes 2-4 hold the top 8 bits of each accelerometer axis; byte 5 holds the two
    /// low bits of each axis (bits 2-3 X, 4-5 Y, 6-7 Z) and the two buttons in bits 0 (Z) and 1 (C), where 0 means
    /// pressed. Returns [`None`] for an all-0xFF report, which is what an uninitialised Nunchuk sends.
    pub fn decode(raw: &[u8; 6]) -> Option<Self> {
        if raw.iter().all(|&b| b == 0xFF) {
            return None;
        }
        let low = raw[5];
        Some(Self {
            joy_x: raw[0],
            joy_y: raw[1],
            accel_x: (u16::from(raw[2]) << 2) | u16::from((low >> 2) & 0b11),
            accel_y: (u16::from(raw[3]) << 2) | u16::from((low >> 4) & 0b11),
            accel_z: (u16::from(raw[4]) << 2) | u16::from((low >> 6) & 0b11),
            z: low & 0b01 == 0,
            c: low & 0b10 == 0,
        })
    }

    /// The accelerometer axes as signed values around zero (level = about 0), range -512 ..= 511.
    pub fn accel_signed(&self) -> (i16, i16, i16) {
        let s = |v: u16| v as i16 - 512;
        (s(self.accel_x), s(self.accel_y), s(self.accel_z))
    }
}

/// A Wii Nunchuk on an I2C bus.
pub struct Nunchuk<I2C> {
    i2c: I2C,
}

impl<I2C: I2c> Nunchuk<I2C> {
    /// Wrap the bus. Nothing is sent until [`Nunchuk::init`].
    pub fn new(i2c: I2C) -> Self {
        Self { i2c }
    }

    /// Give the bus back (for badges that share it with other add-ons).
    pub fn release(self) -> I2C {
        self.i2c
    }

    /// Wake the Nunchuk up in plain (unencrypted) mode: write 0x55 to register 0xF0, then 0x00 to register 0xFB.
    /// Needed once after power-up and again after the Nunchuk is unplugged and plugged back in.
    pub fn init<D: DelayNs>(&mut self, delay: &mut D) -> Result<(), Error<I2C::Error>> {
        self.i2c.write(ADDRESS, &[0xF0, 0x55]).map_err(Error::Bus)?;
        delay.delay_us(INIT_STEP_DELAY_US);
        self.i2c.write(ADDRESS, &[0xFB, 0x00]).map_err(Error::Bus)?;
        delay.delay_us(INIT_STEP_DELAY_US);
        Ok(())
    }

    /// Read the accessory id (register 0xFA) and check that it is a Nunchuk.
    pub fn identify<D: DelayNs>(&mut self, delay: &mut D) -> Result<[u8; 6], Error<I2C::Error>> {
        let id = self.read_raw(0xFA, delay)?;
        if id.iter().all(|&b| b == 0xFF) {
            return Err(Error::NotReady);
        }
        if id != NUNCHUK_ID {
            return Err(Error::NotANunchuk(id));
        }
        Ok(id)
    }

    /// Fetch and decode one report (register 0x00).
    pub fn read<D: DelayNs>(&mut self, delay: &mut D) -> Result<Reading, Error<I2C::Error>> {
        let raw = self.read_raw(0x00, delay)?;
        Reading::decode(&raw).ok_or(Error::NotReady)
    }

    /// Point the Nunchuk at `register`, wait for it, read six bytes. Two separate transactions (write, then read)
    /// rather than a repeated start: Nunchuks need the pause in between.
    pub fn read_raw<D: DelayNs>(&mut self, register: u8, delay: &mut D) -> Result<[u8; 6], Error<I2C::Error>> {
        self.i2c.write(ADDRESS, &[register]).map_err(Error::Bus)?;
        delay.delay_us(CONVERSION_DELAY_US);
        let mut buf = [0u8; 6];
        self.i2c.read(ADDRESS, &mut buf).map_err(Error::Bus)?;
        Ok(buf)
    }
}

/// Turns the raw stick (0-255) into signed steps, with a dead band round the rest position so a stick that does
/// not centre perfectly reads as zero. Every Nunchuk rests at a slightly different spot: call [`Stick::calibrate`]
/// with a reading taken while nobody touches the stick.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Stick {
    /// Rest position, X.
    pub centre_x: u8,
    /// Rest position, Y.
    pub centre_y: u8,
    /// Distance from the rest position that still counts as "not moved".
    pub dead_band: u8,
}

impl Default for Stick {
    fn default() -> Self {
        Self { centre_x: 128, centre_y: 128, dead_band: 16 }
    }
}

impl Stick {
    /// Take the rest position from a reading made with the stick untouched.
    pub fn calibrate(&mut self, at_rest: &Reading) {
        self.centre_x = at_rest.joy_x;
        self.centre_y = at_rest.joy_y;
    }

    /// Signed position, -128 ..= 127 per axis, right and up positive, 0 inside the dead band. Outside the band
    /// the value starts again from 0, so there is no jump at the edge of the band.
    pub fn position(&self, r: &Reading) -> (i8, i8) {
        (self.axis(r.joy_x, self.centre_x), self.axis(r.joy_y, self.centre_y))
    }

    fn axis(&self, raw: u8, centre: u8) -> i8 {
        let d = i16::from(raw) - i16::from(centre);
        let band = i16::from(self.dead_band);
        let v = if d > band {
            d - band
        } else if d < -band {
            d + band
        } else {
            0
        };
        v.clamp(-128, 127) as i8
    }

    /// The direction the stick is pushed, for menus: one of the four, or [`None`] while inside the dead band.
    /// The larger axis wins; a perfect diagonal counts as left/right.
    pub fn direction(&self, r: &Reading) -> Option<Direction> {
        let (x, y) = self.position(r);
        if x == 0 && y == 0 {
            return None;
        }
        Some(if i16::from(x).abs() >= i16::from(y).abs() {
            if x > 0 { Direction::Right } else { Direction::Left }
        } else if y > 0 {
            Direction::Up
        } else {
            Direction::Down
        })
    }
}

/// Stick direction for menus.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    /// Pushed up (away from you).
    Up,
    /// Pulled down.
    Down,
    /// Pushed left.
    Left,
    /// Pushed right.
    Right,
}

/// What changed on the two buttons between two readings.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Buttons {
    /// C went down.
    pub c_pressed: bool,
    /// C came up.
    pub c_released: bool,
    /// Z went down.
    pub z_pressed: bool,
    /// Z came up.
    pub z_released: bool,
}

impl Buttons {
    /// Compare the previous reading with the new one.
    pub fn between(previous: &Reading, now: &Reading) -> Self {
        Self {
            c_pressed: !previous.c && now.c,
            c_released: previous.c && !now.c,
            z_pressed: !previous.z && now.z,
            z_released: previous.z && !now.z,
        }
    }

    /// Anything happened at all.
    pub fn any(&self) -> bool {
        self.c_pressed || self.c_released || self.z_pressed || self.z_released
    }
}
