//! Debouncing for the BOOT button and the power switch's OFF sense pin: a
//! level only counts once it has held still for a while.

#[derive(Clone, Copy, Debug)]
pub struct Debounced {
    stable: bool,
    pending: bool,
    since_ms: u32,
    hold_ms: u32,
}

impl Debounced {
    pub const fn new(level: bool, hold_ms: u32) -> Self {
        Self { stable: level, pending: level, since_ms: 0, hold_ms }
    }

    pub const fn level(&self) -> bool {
        self.stable
    }

    /// Feed a raw reading; returns the new level on the reading where it changes.
    pub fn update(&mut self, raw: bool, now_ms: u32) -> Option<bool> {
        if raw != self.pending {
            self.pending = raw;
            self.since_ms = now_ms;
        }
        if self.pending != self.stable && now_ms.wrapping_sub(self.since_ms) >= self.hold_ms {
            self.stable = self.pending;
            return Some(self.stable);
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn short_glitches_are_ignored() {
        let mut d = Debounced::new(false, 20);
        assert_eq!(d.update(true, 0), None);
        assert_eq!(d.update(false, 5), None);
        assert_eq!(d.update(true, 10), None);
        assert_eq!(d.update(true, 29), None);
        assert_eq!(d.update(true, 30), Some(true));
        assert!(d.level());
    }

    #[test]
    fn works_across_the_clock_wrapping() {
        let mut d = Debounced::new(false, 10);
        d.update(true, u32::MAX - 2);
        assert_eq!(d.update(true, 8), Some(true));
    }
}
