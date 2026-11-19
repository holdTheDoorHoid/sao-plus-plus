//! The touch chip: Microchip CAP1206 (six capacitive inputs, I2C address
//! 0x28), new on the SAO++ board. It replaces the maker's six 1 M resistors
//! and the six microcontroller pins his sketches timed by hand.
//!
//! Register numbers are the CAP12xx family's (Main Control 0x00, Sensor Input
//! Status 0x03, Sensitivity 0x1F, Repeat Rate Enable 0x28, Product ID 0xFD,
//! Manufacturer ID 0xFE). They are written down from the family's published
//! register map and must be checked against the CAP1206 datasheet before the
//! first board is tested (firmware README, "To check").
//!
//! How it is used: every poll reads the status register (one bit per input,
//! bit 0 = CS1), then clears the chip's interrupt flag so the bits show the
//! current touches next time (a held touch stays set).

use crate::bitbang::{BitBang, Error, Lines};

pub const ADDRESS: u8 = 0x28;
pub const REG_MAIN_CONTROL: u8 = 0x00;
pub const REG_INPUT_STATUS: u8 = 0x03;
pub const REG_SENSITIVITY: u8 = 0x1F;
pub const REG_REPEAT_ENABLE: u8 = 0x28;
pub const REG_PRODUCT_ID: u8 = 0xFD;
pub const PRODUCT_ID: u8 = 0x67;
pub const MANUFACTURER_ID: u8 = 0x5D;

/// Sensitivity: the chip's default (32x). The maker's touch areas are large
/// (about 10 x 15 mm and more), so the default should do; lower it here if
/// the pads trigger without a finger.
pub const SENSITIVITY: u8 = 0x2F;

/// Writes done once at start-up: normal mode with the interrupt flag clear,
/// default sensitivity, and no auto-repeat (the app does its own edges).
pub const SETUP: &[(u8, u8)] = &[(REG_MAIN_CONTROL, 0x00), (REG_SENSITIVITY, SENSITIVITY), (REG_REPEAT_ENABLE, 0x00)];

/// Is it there, and is it a CAP1206? Returns (product id, manufacturer id).
pub fn identify<L: Lines>(bus: &mut BitBang<L>) -> Result<(u8, u8), Error> {
    let mut b = [0u8; 2];
    bus.read_reg(ADDRESS, REG_PRODUCT_ID, &mut b)?;
    Ok((b[0], b[1]))
}

pub fn setup<L: Lines>(bus: &mut BitBang<L>) -> Result<(), Error> {
    for &(reg, val) in SETUP {
        bus.write(ADDRESS, &[reg, val])?;
    }
    Ok(())
}

/// One poll: the six-bit touch mask (bit 0 = CS1 ... bit 5 = CS6).
pub fn poll<L: Lines>(bus: &mut BitBang<L>) -> Result<u8, Error> {
    let mut s = [0u8; 1];
    bus.read_reg(ADDRESS, REG_INPUT_STATUS, &mut s)?;
    // clear the interrupt flag; touches still held set their bits again
    bus.write(ADDRESS, &[REG_MAIN_CONTROL, 0x00])?;
    Ok(s[0] & 0x3F)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bitbang::sim::Sim;

    #[test]
    fn identifies_sets_up_and_polls() {
        let mut s = Sim::new(ADDRESS);
        s.regs[REG_PRODUCT_ID as usize] = PRODUCT_ID;
        s.regs[REG_PRODUCT_ID as usize + 1] = MANUFACTURER_ID;
        s.regs[REG_INPUT_STATUS as usize] = 0b1100_0101;
        s.regs[REG_MAIN_CONTROL as usize] = 0x01; // interrupt flag set
        let mut bus = BitBang::new(s);
        assert_eq!(identify(&mut bus), Ok((PRODUCT_ID, MANUFACTURER_ID)));
        setup(&mut bus).unwrap();
        assert_eq!(bus.lines().regs[REG_SENSITIVITY as usize], SENSITIVITY);
        bus.lines().regs[REG_MAIN_CONTROL as usize] = 0x01;
        assert_eq!(poll(&mut bus), Ok(0b0000_0101)); // only the six inputs
        assert_eq!(bus.lines().regs[REG_MAIN_CONTROL as usize], 0x00);
    }

    #[test]
    fn missing_chip_is_reported() {
        let mut s = Sim::new(ADDRESS);
        s.present = false;
        let mut bus = BitBang::new(s);
        assert_eq!(poll(&mut bus), Err(Error::Nack));
    }
}
