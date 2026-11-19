//! The whole add-on, without hardware: feed it the time, the button and switch
//! levels and the badge's I2C writes; it says how bright red and blue should be
//! and what to answer when the badge reads.

use crate::fade::{Engine, Show, TICK_US};
use crate::input::Debounced;
use crate::proto::{self, Protocol};
use crate::rng::Rng;
use crate::store::{self, Store};

/// How long the button / switch must hold a level to count, in ms.
pub const DEBOUNCE_MS: u32 = 25;
/// At most this many engine ticks are caught up in one call (after a stall).
const MAX_CATCH_UP: u32 = 50;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Inputs {
    /// The XIAO's BOOT button is held.
    pub button_down: bool,
    /// The power switch is on OFF (it ties D1 high).
    pub off_selected: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Output {
    /// Red and blue brightness, 0..=96 each (see `fade::CYCLE`).
    Leds(u16, u16),
    /// The switch is on OFF: go dark and sleep.
    PowerOff,
}

pub struct App {
    pub leds: Engine,
    pub store: Store,
    proto: Protocol,
    rng: Rng,
    button: Debounced,
    off: Debounced,
    last_us: u32,
}

impl App {
    /// `seed`: anything board-specific (the firmware uses the MAC address).
    pub fn new(seed: u32, now_us: u32, off_at_start: bool) -> Self {
        let mut rng = Rng::new(seed);
        let mut store = Store::new(store::serial_from(seed));
        let mode = Show::from_number(store.option(0));
        let mut leds = Engine::new(mode);
        if proto::relapse(&mut store, &mut rng) {
            leds.flash(Show::Infected);
        }
        Self {
            leds,
            store,
            proto: Protocol::new(),
            rng,
            button: Debounced::new(false, DEBOUNCE_MS),
            off: Debounced::new(off_at_start, DEBOUNCE_MS),
            last_us: now_us,
        }
    }

    pub fn tick(&mut self, now_us: u32, inp: Inputs) -> Output {
        let now_ms = now_us / 1000;
        self.off.update(inp.off_selected, now_ms);
        if self.off.level() {
            return Output::PowerOff;
        }
        if self.button.update(inp.button_down, now_ms) == Some(true) {
            let next = self.leds.saved().next_for_button();
            self.leds.select(next);
            self.store.set_option(0, next.number());
        }
        let mut n = 0;
        while now_us.wrapping_sub(self.last_us) >= TICK_US && n < MAX_CATCH_UP {
            self.leds.tick();
            self.last_us = self.last_us.wrapping_add(TICK_US);
            n += 1;
        }
        if n == MAX_CATCH_UP {
            self.last_us = now_us;
        }
        let (r, b) = self.leds.levels();
        Output::Leds(r, b)
    }

    /// A finished write from the badge.
    pub fn on_i2c_write(&mut self, bytes: &[u8], now_us: u32) {
        self.rng.stir(now_us);
        self.proto.on_write(bytes, &mut self.store, &mut self.leds, &mut self.rng);
    }

    /// What a badge read gets now.
    pub fn reply(&self) -> &[u8] {
        self.proto.reply.as_bytes()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const UP: Inputs = Inputs { button_down: false, off_selected: false };
    const DOWN: Inputs = Inputs { button_down: true, off_selected: false };

    #[test]
    fn starts_in_mode_zero_and_animates() {
        let mut a = App::new(42, 0, false);
        assert_eq!(a.leds.show(), Show::SlowRedBlue);
        let mut seen_lit = false;
        for t in 0..400u32 {
            if let Output::Leds(r, b) = a.tick(t * 1000, UP) {
                seen_lit |= r > 0 || b > 0;
            }
        }
        assert!(seen_lit);
    }

    #[test]
    fn button_cycles_modes() {
        let mut a = App::new(42, 0, false);
        let mut t = 0u32;
        for expect in [1u8, 2, 3, 4, 5, 6, 0] {
            for _ in 0..40 {
                t += 1000;
                a.tick(t, DOWN);
            }
            for _ in 0..40 {
                t += 1000;
                a.tick(t, UP);
            }
            assert_eq!(a.leds.saved().number(), expect);
            assert_eq!(a.store.option(0), expect);
        }
    }

    #[test]
    fn off_switch_means_power_off() {
        let mut a = App::new(42, 0, false);
        let off = Inputs { button_down: false, off_selected: true };
        let mut out = Output::Leds(0, 0);
        for t in 0..60u32 {
            out = a.tick(t * 1000, off);
        }
        assert_eq!(out, Output::PowerOff);
        let mut b = App::new(42, 0, true);
        assert_eq!(b.tick(0, off), Output::PowerOff);
    }

    #[test]
    fn badge_command_through_the_app() {
        let mut a = App::new(42, 0, false);
        a.on_i2c_write(&[0, 0, 0], 5);
        assert_eq!(a.reply(), b"EGGPLANT");
        a.on_i2c_write(&[0, 3, 2], 6);
        assert_eq!(a.leds.show(), Show::BluePulse);
    }

    #[test]
    fn a_long_stall_does_not_replay_forever() {
        let mut a = App::new(42, 0, false);
        a.tick(10_000_000, UP);
        let before = a.leds.blue.value;
        a.tick(10_001_000, UP);
        assert_ne!(a.leds.blue.value, before);
    }
}
