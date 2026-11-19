//! The maker's LED light show: two colour channels (all five red anodes on
//! one pin, all five blue anodes on another), each a brightness that walks up
//! and down between two limits, as his `fadeUpDownLEDs()` does.
//!
//! How his engine works (described here in our own words, re-implemented,
//! not copied): each channel has a brightness `value`, a signed `step`, and a
//! `slowdown` count. Every engine tick a channel's private counter goes up by
//! one; when it reaches `slowdown`, it resets, the value bounces off its
//! limits (clamped to the limit, step reversed, bounce counted) and then
//! moves by `step`. The pin is on for `value` out of every [`CYCLE`] slots
//! of his software PWM loop, so the brightness is `value / CYCLE`, clipped to
//! 0..=1. Several of his presets let `value` run past [`CYCLE`] (full on for a
//! while) or below zero (off for a while): that is part of the look and is
//! kept.
//!
//! Timing: his loop ran one engine tick per software-PWM sweep. On an
//! ATtiny85 at 8 MHz that sweep is roughly a millisecond; his files do not
//! say, so [`TICK_US`] is an estimate to adjust on the first board.

/// Software-PWM slots per sweep in his loop: brightness = value / CYCLE.
pub const CYCLE: i16 = 96;

/// One engine tick, in microseconds (estimate of his ATtiny85 loop time).
pub const TICK_US: u32 = 1_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Channel {
    pub value: i16,
    pub step: i16,
    pub counter: i16,
    pub slowdown: i16,
    pub min: i16,
    pub max: i16,
    /// How many times the value has bounced off a limit since the preset
    /// started (his flash modes end after a number of bounces).
    pub bounces: u16,
}

impl Channel {
    pub const fn new(value: i16, step: i16, counter: i16, slowdown: i16, min: i16, max: i16) -> Self {
        Self { value, step, counter, slowdown, min, max, bounces: 0 }
    }

    pub const fn dark() -> Self {
        Self::new(0, 0, 0, 1, 0, 0)
    }

    /// One engine tick.
    pub fn tick(&mut self) {
        self.counter += 1;
        if self.counter < self.slowdown {
            return;
        }
        self.counter = 0;
        if self.value >= self.max {
            self.value = self.max;
            self.step = -self.step;
            self.bounces = self.bounces.saturating_add(1);
        }
        if self.value <= self.min {
            self.value = self.min;
            self.step = -self.step;
            self.bounces = self.bounces.saturating_add(1);
        }
        self.value += self.step;
    }

    /// Brightness 0..=CYCLE (the number of on-slots in his PWM sweep).
    pub fn level(&self) -> u16 {
        self.value.clamp(0, CYCLE) as u16
    }

    /// Duty for a PWM peripheral with `full` counts per period.
    pub fn duty(&self, full: u32) -> u32 {
        self.level() as u32 * full / CYCLE as u32
    }
}

/// The light shows. 0..=5 are the maker's selectable modes (badge command or
/// the BOOT button); `Off` is selectable from the button only (his I2C command
/// never reaches it, see `proto`); `Infected` and `Cured` are his short
/// flashes that play after the infection game changes, then hand back to the
/// saved mode.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Show {
    SlowRedBlue,
    RedBlue,
    BluePulse,
    PurplePulse,
    RedPulse,
    Rollers,
    Off,
    Infected,
    Cured,
}

impl Show {
    /// His mode numbers. Anything above 5 that is not 16 or 17 is dark.
    pub fn from_number(n: u8) -> Self {
        match n {
            0 => Show::SlowRedBlue,
            1 => Show::RedBlue,
            2 => Show::BluePulse,
            3 => Show::PurplePulse,
            4 => Show::RedPulse,
            5 => Show::Rollers,
            16 => Show::Infected,
            17 => Show::Cured,
            _ => Show::Off,
        }
    }

    pub fn number(self) -> u8 {
        match self {
            Show::SlowRedBlue => 0,
            Show::RedBlue => 1,
            Show::BluePulse => 2,
            Show::PurplePulse => 3,
            Show::RedPulse => 4,
            Show::Rollers => 5,
            Show::Off => 6,
            Show::Infected => 16,
            Show::Cured => 17,
        }
    }

    /// The next mode for the BOOT button: 0 -> 1 -> ... -> 5 -> off -> 0.
    pub fn next_for_button(self) -> Self {
        match self {
            Show::Off | Show::Infected | Show::Cured => Show::SlowRedBlue,
            other => Show::from_number(other.number() + 1),
        }
    }

    /// Starting state of (red, blue) for this show: his presets.
    pub fn preset(self) -> (Channel, Channel) {
        //                 value step counter slowdown min max
        match self {
            Show::SlowRedBlue => (Channel::new(0, 1, 0, 4, 0, 90), Channel::new(0, 1, 0, 1, 12, 140)),
            Show::RedBlue => (Channel::new(0, 1, 0, 1, 0, 90), Channel::new(0, 1, 0, 1, 12, 112)),
            Show::BluePulse => (Channel::new(0, 0, 0, 1, 0, 0), Channel::new(0, 1, 0, 3, 12, 112)),
            Show::PurplePulse => (Channel::new(0, 1, 0, 3, 12, 112), Channel::new(0, 1, 0, 3, 12, 112)),
            Show::RedPulse => (Channel::new(0, 1, 0, 3, 12, 112), Channel::new(0, 0, 0, 1, 0, 0)),
            Show::Rollers => (Channel::new(33, 6, 0, 1, -30, 96), Channel::new(33, -6, 0, 1, -30, 96)),
            Show::Off => (Channel::dark(), Channel::dark()),
            Show::Infected => (Channel::new(0, 6, 0, 1, 0, 90), Channel::new(0, 1, 5, 1, 12, 30)),
            Show::Cured => (Channel::new(0, 1, 5, 1, 0, 15), Channel::new(0, 6, 0, 1, 12, 140)),
        }
    }
}

/// Bounces after which a flash show ends: his "flash ten times" (each flash is
/// two bounces, up and down).
pub const FLASH_BOUNCES: u16 = 20;

/// The running light show.
#[derive(Clone, Copy, Debug)]
pub struct Engine {
    show: Show,
    /// The mode to go back to after a flash.
    saved: Show,
    pub red: Channel,
    pub blue: Channel,
}

impl Engine {
    pub fn new(show: Show) -> Self {
        let (red, blue) = show.preset();
        Self { show, saved: show, red, blue }
    }

    pub fn show(&self) -> Show {
        self.show
    }

    pub fn saved(&self) -> Show {
        self.saved
    }

    /// Start a selectable mode (and remember it to come back to after flashes).
    pub fn select(&mut self, show: Show) {
        self.saved = show;
        self.start(show);
    }

    /// Play a flash (Infected / Cured); afterwards the saved mode resumes.
    pub fn flash(&mut self, show: Show) {
        self.start(show);
    }

    fn start(&mut self, show: Show) {
        self.show = show;
        let (r, b) = show.preset();
        self.red = r;
        self.blue = b;
    }

    /// One engine tick.
    pub fn tick(&mut self) {
        if self.show == Show::Off {
            return;
        }
        self.blue.tick();
        self.red.tick();
        let done = match self.show {
            Show::Infected => self.red.bounces >= FLASH_BOUNCES,
            Show::Cured => self.blue.bounces >= FLASH_BOUNCES,
            _ => false,
        };
        if done {
            let s = self.saved;
            self.start(s);
        }
    }

    /// (red, blue) brightness, 0..=CYCLE each.
    pub fn levels(&self) -> (u16, u16) {
        if self.show == Show::Off {
            (0, 0)
        } else {
            (self.red.level(), self.blue.level())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounces_between_limits() {
        let mut c = Channel::new(0, 1, 0, 1, 12, 20);
        let mut seen = std::vec::Vec::new();
        for _ in 0..40 {
            c.tick();
            seen.push(c.value);
        }
        // as in his sketch, a value starting below `min` is clamped, the step
        // flips, and it dips one step below before climbing (11 here)
        assert!(seen.iter().all(|&v| (11..=21).contains(&v)), "{seen:?}");
        assert!(c.bounces >= 2);
    }

    #[test]
    fn slowdown_divides_the_rate() {
        let mut fast = Channel::new(50, 1, 0, 1, 0, 90);
        let mut slow = Channel::new(50, 1, 0, 4, 0, 90);
        for _ in 0..8 {
            fast.tick();
            slow.tick();
        }
        assert_eq!(fast.value, 58);
        assert_eq!(slow.value, 52);
    }

    #[test]
    fn level_clips_to_the_sweep() {
        assert_eq!(Channel::new(140, 0, 0, 1, 0, 140).level(), 96);
        assert_eq!(Channel::new(-30, 0, 0, 1, -30, 96).level(), 0);
        assert_eq!(Channel::new(48, 0, 0, 1, 0, 96).duty(1024), 512);
    }

    #[test]
    fn red_only_and_blue_only_modes() {
        let mut e = Engine::new(Show::RedPulse);
        for _ in 0..2000 {
            e.tick();
            assert_eq!(e.levels().1, 0, "blue must stay dark in red pulse");
        }
        let mut e = Engine::new(Show::BluePulse);
        for _ in 0..2000 {
            e.tick();
            assert_eq!(e.levels().0, 0, "red must stay dark in blue pulse");
        }
    }

    #[test]
    fn purple_pulse_moves_both_together() {
        let mut e = Engine::new(Show::PurplePulse);
        for _ in 0..1000 {
            e.tick();
            assert_eq!(e.red.value, e.blue.value);
        }
    }

    #[test]
    fn rollers_run_opposite() {
        let mut e = Engine::new(Show::Rollers);
        e.tick();
        assert_eq!((e.red.value, e.blue.value), (39, 27));
    }

    #[test]
    fn infected_flash_returns_to_saved_mode() {
        let mut e = Engine::new(Show::RedBlue);
        e.select(Show::BluePulse);
        e.flash(Show::Infected);
        assert_eq!(e.show(), Show::Infected);
        let mut n = 0;
        while e.show() == Show::Infected {
            e.tick();
            n += 1;
            assert!(n < 10_000, "flash never ended");
        }
        assert_eq!(e.show(), Show::BluePulse);
        // red climbs 0..90 in steps of 6: 15 ticks per sweep, 20 bounces
        assert!((250..=350).contains(&n), "{n} ticks");
    }

    #[test]
    fn cured_flash_returns_too() {
        let mut e = Engine::new(Show::SlowRedBlue);
        e.flash(Show::Cured);
        for _ in 0..10_000 {
            e.tick();
        }
        assert_eq!(e.show(), Show::SlowRedBlue);
    }

    #[test]
    fn off_is_dark_and_button_cycle_wraps() {
        let e = Engine::new(Show::Off);
        assert_eq!(e.levels(), (0, 0));
        let mut s = Show::SlowRedBlue;
        let mut order = std::vec::Vec::new();
        for _ in 0..8 {
            order.push(s.number());
            s = s.next_for_button();
        }
        assert_eq!(order, [0, 1, 2, 3, 4, 5, 6, 0]);
        assert_eq!(Show::Infected.next_for_button(), Show::SlowRedBlue);
    }

    #[test]
    fn mode_numbers_round_trip() {
        for n in [0u8, 1, 2, 3, 4, 5, 16, 17] {
            assert_eq!(Show::from_number(n).number(), n);
        }
        assert_eq!(Show::from_number(9), Show::Off);
    }
}
