//! Brightness for the four red mouth LEDs, which are plain LEDs on one pin.
//!
//! The firmware calls [`Dimmer::step`] at a steady rate and switches the pin
//! on or off with the answer. Out of every 255 calls the pin is on `level`
//! times, spread as evenly as possible, so the eye sees a steady brightness
//! (this is a first-order sigma-delta modulator).

#[derive(Clone, Copy, Debug, Default)]
pub struct Dimmer {
    acc: u8,
}

impl Dimmer {
    pub const fn new() -> Self {
        Self { acc: 0 }
    }

    /// Whether the LEDs should be on until the next call. `level` 0 is always
    /// off, 255 always on.
    pub fn step(&mut self, level: u8) -> bool {
        let sum = self.acc as u16 + level as u16;
        if sum >= 255 {
            self.acc = (sum - 255) as u8;
            true
        } else {
            self.acc = sum as u8;
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn on_exactly_level_times_in_255_calls() {
        for level in [0u8, 1, 2, 77, 128, 254, 255] {
            let mut d = Dimmer::new();
            // run in a while first: the count must not depend on where it starts
            for _ in 0..100 {
                d.step(level);
            }
            let on = (0..255).filter(|_| d.step(level)).count();
            assert_eq!(on, level as usize, "level {level}");
        }
    }

    #[test]
    fn half_brightness_alternates() {
        let mut d = Dimmer::new();
        let mut longest_run = 0;
        let mut run = 0;
        let mut last = d.step(128);
        for _ in 0..1000 {
            let now = d.step(128);
            run = if now == last { run + 1 } else { 0 };
            longest_run = longest_run.max(run);
            last = now;
        }
        assert!(longest_run <= 1, "pulses should be spread out, not bunched");
    }
}
