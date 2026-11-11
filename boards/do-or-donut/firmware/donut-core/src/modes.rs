//! The built-in modes, cycled by the BOOT button (and selectable by the
//! badge over I2C).

use crate::anim::{icing_drip, radial_pulse, sprinkles, wave};
use crate::{Frame, LED_COUNT};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// 0 (default): sprinkles twinkling at random.
    Sprinkles,
    /// 1: a wave of light running round the ring.
    Wave,
    /// 2: rings of light growing from the hole outward.
    Pulse,
    /// 3: a slow band of light dripping from top to bottom.
    Drip,
    /// 4: all off, but awake (still obeys the badge).
    Off,
}

pub const MODE_COUNT: u8 = 5;

impl Mode {
    pub const fn number(self) -> u8 {
        match self {
            Mode::Sprinkles => 0,
            Mode::Wave => 1,
            Mode::Pulse => 2,
            Mode::Drip => 3,
            Mode::Off => 4,
        }
    }

    pub const fn from_number(n: u8) -> Option<Mode> {
        match n {
            0 => Some(Mode::Sprinkles),
            1 => Some(Mode::Wave),
            2 => Some(Mode::Pulse),
            3 => Some(Mode::Drip),
            4 => Some(Mode::Off),
            _ => None,
        }
    }

    pub const fn next(self) -> Mode {
        match Mode::from_number((self.number() + 1) % MODE_COUNT) {
            Some(m) => m,
            None => Mode::Sprinkles,
        }
    }

    /// The picture `t` ms after the mode started, in levels (before gamma
    /// and the current cap).
    pub fn render(self, t: u32) -> Frame {
        let mut f = [0u8; LED_COUNT];
        match self {
            Mode::Sprinkles => sprinkles(t, &mut f),
            Mode::Wave => wave(t, &mut f),
            Mode::Pulse => radial_pulse(t, &mut f),
            Mode::Drip => icing_drip(t, &mut f),
            Mode::Off => {}
        }
        f
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers_round_trip_and_cycle() {
        for n in 0..MODE_COUNT {
            let m = Mode::from_number(n).unwrap();
            assert_eq!(m.number(), n);
            assert_eq!(m.next().number(), (n + 1) % MODE_COUNT);
        }
        assert_eq!(Mode::from_number(MODE_COUNT), None);
    }

    #[test]
    fn off_is_dark() {
        assert_eq!(Mode::Off.render(12_345), [0; LED_COUNT]);
    }

    #[test]
    fn animated_modes_change_over_time() {
        for m in [Mode::Sprinkles, Mode::Wave, Mode::Pulse, Mode::Drip] {
            assert_ne!(m.render(1_000), m.render(1_300), "{m:?}");
        }
    }
}
