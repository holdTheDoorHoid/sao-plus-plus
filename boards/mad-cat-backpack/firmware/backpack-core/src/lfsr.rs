//! The maker's random-number generator.
//!
//! His PIC program draws every random choice (how long to wait, which
//! animation, how many repeats, which eye blinks, sparkle levels) from one
//! 32-bit linear-feedback shift register, seeded with 0x55555555 at power-on.
//! Each draw shifts it eight times and returns its low byte. Using the same
//! generator, with the same seed and the same order of draws, gives the same
//! sequence of animations his board shows after power-on.

/// 32-bit shift register; feedback from bits 0, 2, 6 and 7, shifted in at the
/// top as the register moves one place down.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Lfsr {
    state: u32,
}

impl Default for Lfsr {
    fn default() -> Self {
        Self::new()
    }
}

impl Lfsr {
    /// The maker's power-on value: every one of the four bytes is 0x55.
    pub const SEED: u32 = 0x5555_5555;

    pub const fn new() -> Self {
        Self { state: Self::SEED }
    }

    /// Start from any value (never zero: an all-zero register stays zero).
    pub const fn with_state(state: u32) -> Self {
        Self {
            state: if state == 0 { Self::SEED } else { state },
        }
    }

    pub const fn state(&self) -> u32 {
        self.state
    }

    fn shift(&mut self) {
        let s = self.state;
        let feedback = (s ^ (s >> 2) ^ (s >> 6) ^ (s >> 7)) & 1;
        self.state = (s >> 1) | (feedback << 31);
    }

    /// One draw: eight shifts, then the low byte.
    pub fn next(&mut self) -> u8 {
        for _ in 0..8 {
            self.shift();
        }
        self.state as u8
    }

    /// Bit `n` (0..=7) of the register's third byte, as left by the last draw.
    /// The blink animation decides which eye closes from two of these bits.
    pub const fn third_byte_bit(&self, n: u32) -> bool {
        (self.state >> (16 + n)) & 1 == 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    /// The same register worked the way the PIC does it: four separate bytes,
    /// a carry flag, and a rotate-right-through-carry of each byte from the
    /// top one down. Written independently of `Lfsr::shift` as a cross-check.
    struct PicBytes {
        b: [u8; 4], // b[0] = low byte ... b[3] = top byte
    }

    impl PicBytes {
        fn draw(&mut self) -> u8 {
            for _ in 0..8 {
                let x = self.b[0];
                let mut t = x & 1;
                if x & 0x04 != 0 {
                    t ^= 1;
                }
                if x & 0x40 != 0 {
                    t ^= 1;
                }
                if x & 0x80 != 0 {
                    t ^= 1;
                }
                let mut carry = t;
                for i in (0..4).rev() {
                    let out = self.b[i] & 1;
                    self.b[i] = (self.b[i] >> 1) | (carry << 7);
                    carry = out;
                }
            }
            self.b[0]
        }
    }

    #[test]
    fn matches_a_byte_by_byte_model_of_the_pic() {
        let mut a = Lfsr::new();
        let mut b = PicBytes { b: [0x55; 4] };
        for _ in 0..5_000 {
            assert_eq!(a.next(), b.draw());
            let bytes = a.state().to_le_bytes();
            assert_eq!(bytes, b.b);
        }
    }

    #[test]
    fn is_deterministic_from_the_seed() {
        let first: Vec<u8> = {
            let mut l = Lfsr::new();
            (0..16).map(|_| l.next()).collect()
        };
        let again: Vec<u8> = {
            let mut l = Lfsr::new();
            (0..16).map(|_| l.next()).collect()
        };
        assert_eq!(first, again);
        // not stuck
        assert!(first.iter().any(|&x| x != first[0]));
    }

    #[test]
    fn does_not_fall_into_zero_and_has_a_long_period() {
        let mut l = Lfsr::new();
        for _ in 0..100_000 {
            l.next();
            assert_ne!(l.state(), 0);
            assert_ne!(l.state(), Lfsr::SEED, "came back to the seed too early");
        }
    }

    #[test]
    fn zero_state_is_refused() {
        assert_eq!(Lfsr::with_state(0).state(), Lfsr::SEED);
    }
}
