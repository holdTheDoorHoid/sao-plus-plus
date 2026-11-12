//! Time-based debouncing for the power-switch sense pin.

/// A level that only changes after the raw input has held the new value for
/// `settle_ms`.
#[derive(Clone, Copy, Debug)]
pub struct Debounced {
    stable: bool,
    candidate: bool,
    since_ms: u32,
    settle_ms: u32,
}

impl Debounced {
    pub const fn new(initial: bool, settle_ms: u32) -> Self {
        Self {
            stable: initial,
            candidate: initial,
            since_ms: 0,
            settle_ms,
        }
    }

    pub const fn level(&self) -> bool {
        self.stable
    }

    /// Feed a raw sample. Returns `Some(new_level)` on the sample where the
    /// debounced level changes.
    pub fn update(&mut self, raw: bool, now_ms: u32) -> Option<bool> {
        if raw != self.candidate {
            self.candidate = raw;
            self.since_ms = now_ms;
        }
        if self.candidate != self.stable && now_ms.wrapping_sub(self.since_ms) >= self.settle_ms {
            self.stable = self.candidate;
            return Some(self.stable);
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ignores_bounces_shorter_than_settle_time() {
        let mut d = Debounced::new(false, 30);
        assert_eq!(d.update(true, 0), None);
        assert_eq!(d.update(false, 5), None);
        assert_eq!(d.update(true, 10), None);
        assert_eq!(d.update(true, 39), None);
        assert_eq!(d.update(true, 40), Some(true));
        assert_eq!(d.update(true, 100), None);
        assert!(d.level());
    }

    #[test]
    fn reports_release_too() {
        let mut d = Debounced::new(false, 10);
        d.update(true, 0);
        assert_eq!(d.update(true, 10), Some(true));
        d.update(false, 50);
        assert_eq!(d.update(false, 60), Some(false));
    }

    #[test]
    fn survives_timer_wrap() {
        let mut d = Debounced::new(false, 10);
        d.update(true, u32::MAX - 3);
        assert_eq!(d.update(true, 6), Some(true));
    }
}
