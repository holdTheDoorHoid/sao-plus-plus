//! Dimming eight plain LEDs from eight ordinary pins ("bit-angle" dimming).
//!
//! The XIAO's LED-dimming hardware has only six channels on the C3 and C6,
//! and this board has eight LEDs, so the firmware dims them itself (the
//! maker's PIC did the same in software). Each repeat ("frame") is split into
//! eight slices of 1, 2, 4 ... 128 units. During slice `b` an LED is on if
//! bit `b` of its level is set, so over one frame it is on for exactly
//! `level` of 255 units: level 0 = off, 255 = on all the time. That needs only
//! eight pin updates per frame instead of 255.
//!
//! With a 30 us unit a frame lasts 7.65 ms, so each LED is refreshed about
//! 130 times a second: too fast to see flicker, as on the maker's board
//! (about 117 times a second).
//!
//! The maker's chip lit an LED for (level + 1) of 256 counts (level 0 off);
//! here it is level of 255. The largest difference is one count, at the
//! dimmest step (level 1): invisible.

use crate::{LED_COUNT, Levels};

/// Number of slices per frame (one per bit of the level).
pub const SLICES: u8 = 8;
/// Length of the shortest slice.
pub const UNIT_US: u32 = 30;
/// One whole frame.
pub const FRAME_US: u32 = UNIT_US * 255;

/// How long slice `b` lasts.
pub const fn slice_us(b: u8) -> u32 {
    UNIT_US << b
}

/// Which LEDs are lit during slice `b`: bit `i` of the result is LED `i`.
pub fn slice_mask(levels: &Levels, b: u8) -> u8 {
    let mut m = 0u8;
    for (i, &v) in levels.iter().enumerate().take(LED_COUNT) {
        if v & (1 << b) != 0 {
            m |= 1 << i;
        }
    }
    m
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn on_time_equals_level() {
        for level in 0..=255u8 {
            let levels = [level; LED_COUNT];
            let on: u32 = (0..SLICES)
                .filter(|&b| slice_mask(&levels, b) & 1 != 0)
                .map(slice_us)
                .sum();
            assert_eq!(on, level as u32 * UNIT_US);
        }
        assert_eq!((0..SLICES).map(slice_us).sum::<u32>(), FRAME_US);
    }

    #[test]
    fn each_led_on_its_own_bit() {
        let levels = [1, 2, 4, 8, 16, 32, 64, 128];
        for b in 0..SLICES {
            assert_eq!(slice_mask(&levels, b), 1 << b);
        }
        assert_eq!(slice_mask(&[0; LED_COUNT], 3), 0);
        assert_eq!(slice_mask(&[255; LED_COUNT], 7), 0xFF);
    }

    #[test]
    fn refresh_is_flicker_free() {
        assert!(1_000_000 / FRAME_US >= 100);
    }
}
