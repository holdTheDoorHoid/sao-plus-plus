//! A small xorshift random number generator. The maker seeded his from the
//! time of the first I2C request; this firmware seeds from the module's own
//! factory MAC address and stirs in the time of every badge command.

pub fn step(mut x: u32) -> u32 {
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    x
}

#[derive(Clone, Copy, Debug)]
pub struct Rng(u32);

impl Rng {
    pub fn new(seed: u32) -> Self {
        Self(if seed == 0 { 0x9E37_79B9 } else { seed })
    }

    pub fn next(&mut self) -> u32 {
        self.0 = step(self.0);
        self.0
    }

    /// 0..n (n > 0).
    pub fn below(&mut self, n: u32) -> u32 {
        self.next() % n
    }

    /// Mix in something unpredictable (a time stamp).
    pub fn stir(&mut self, v: u32) {
        self.0 = step(self.0 ^ v.wrapping_mul(0x9E37_79B9)) | 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn never_sticks_at_zero_and_spreads() {
        let mut r = Rng::new(0);
        let mut buckets = [0u32; 10];
        for _ in 0..10_000 {
            buckets[r.below(10) as usize] += 1;
        }
        assert!(buckets.iter().all(|&b| (800..1200).contains(&b)), "{buckets:?}");
    }
}
