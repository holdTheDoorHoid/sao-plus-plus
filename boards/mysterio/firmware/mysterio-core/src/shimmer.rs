//! Mode 0: the maker's own "icy shimmer", re-implemented.
//!
//! Behaviour taken from davedarko's sketch for this board,
//! `original/Sketchbook/strandtest/strandtest.ino` (Arduino + Adafruit
//! NeoPixel). This is a clean re-implementation of what it does, not a port of
//! his code. What the sketch does, step by step:
//!
//! * Brightness is set to 200 (Adafruit NeoPixel: every channel becomes
//!   `(value * 201) >> 8`, so 255 becomes 200). See [`maker_scale`].
//! * A counter (`marker` in the sketch) starts at 0.
//! * Every 40 ms one LED is repainted, in chain order 0, 1, 2, 3 (D1..D4,
//!   right-hand LED first), with palette entry `(LED index + counter) % 12`.
//!   Then the counter goes up by one (and wraps at 12).
//! * After each pass over the four LEDs the counter jumps to a random value
//!   0..=7 (`random(8)`), and the next pass starts 40 ms later as usual.
//! * The LEDs start dark and the other LEDs keep their colour while one is
//!   repainted.
//!
//! Because the counter rises by one per LED, within one pass LED i shows
//! entry `(start + 2*i) % 12`: a gradient two palette steps apart per LED.
//!
//! Differences from the sketch, all deliberate or unavoidable:
//! * The random numbers come from a small xorshift generator with a fixed
//!   seed, not from the Arduino core's `random()`. His sketch never calls
//!   `randomSeed`, so his board also replays the same "random" sequence after
//!   every power-up; ours is a different (equally fixed) sequence.
//! * The step is exactly 40 ms. His was 40 ms plus the time to send the
//!   colours and the library's latch wait (well under 1 ms).
//! * The [`GLOBAL_BRIGHTNESS_CAP`](crate::GLOBAL_BRIGHTNESS_CAP) is applied on
//!   top of his 200/255 (by the caller, [`crate::app`]).
//! * Two palette entries differ by one from the hex colours in his own
//!   comment (`0x34` = 52 but he wrote 53; `0xBE` = 190 but he wrote 191).
//!   We use the numbers his code actually sends: 53 and 191.

use crate::{Frame, LED_COUNT, Rgb};

/// Time between repaints.
pub const STEP_MS: u32 = 40;

/// The maker's `strip.setBrightness(200)`.
pub const MAKER_BRIGHTNESS: u8 = 200;

/// The maker's 12-colour palette (his `stringOfFire`), deep blue -> cyan ->
/// white, exactly the numbers in his sketch.
pub const PALETTE: [Rgb; 12] = [
    Rgb::new(0, 11, 45),    // #000b2d
    Rgb::new(0, 53, 90),    // #00345a (sketch uses 53, the hex says 52)
    Rgb::new(0, 95, 133),   // #005f85
    Rgb::new(0, 142, 170),  // #008eaa
    Rgb::new(0, 191, 198),  // #00bec6 (sketch uses 191, the hex says 190)
    Rgb::new(38, 211, 217), // #26d3d9
    Rgb::new(61, 233, 236), // #3de9ec
    Rgb::new(81, 255, 255), // #51ffff
    Rgb::new(142, 253, 255), // #8efdff
    Rgb::new(200, 250, 255), // #c8faff
    Rgb::new(239, 250, 255), // #effaff
    Rgb::new(255, 255, 255), // #ffffff
];

/// How the Adafruit NeoPixel library applies `setBrightness(200)`: it stores
/// 201 and computes `(v * 201) >> 8`.
pub const fn maker_scale(v: u8) -> u8 {
    ((v as u16 * (MAKER_BRIGHTNESS as u16 + 1)) >> 8) as u8
}

const fn maker_colour(c: Rgb) -> Rgb {
    Rgb::new(maker_scale(c.r), maker_scale(c.g), maker_scale(c.b))
}

/// Fixed seed for the random jumps (any non-zero value works).
pub const SEED: u32 = 0x4D59_5354; // "MYST"

/// Small xorshift32 random number generator.
#[derive(Clone, Copy, Debug)]
pub struct Rng(u32);

impl Rng {
    pub const fn new(seed: u32) -> Self {
        Self(if seed == 0 { 1 } else { seed })
    }

    pub fn next_u32(&mut self) -> u32 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.0 = x;
        x
    }

    /// A value in `0..n` (like Arduino's `random(n)`).
    pub fn below(&mut self, n: u8) -> u8 {
        (self.next_u32() % n as u32) as u8
    }
}

/// If the caller falls this many steps behind (only possible if the main loop
/// stalls), skip ahead instead of replaying every missed step.
const MAX_CATCH_UP: u32 = 64;

#[derive(Clone, Copy, Debug)]
pub struct Shimmer {
    frame: Frame,
    next_led: usize,
    marker: u8,
    steps_done: u32,
    rng: Rng,
}

impl Shimmer {
    pub const fn new(seed: u32) -> Self {
        Self {
            frame: [Rgb::OFF; LED_COUNT],
            next_led: 0,
            marker: 0,
            steps_done: 0,
            rng: Rng::new(seed),
        }
    }

    /// Start again as at power-up: LEDs dark, counter 0, LED 0 next. The
    /// random sequence carries on where it was.
    pub fn restart(&mut self) {
        self.frame = [Rgb::OFF; LED_COUNT];
        self.next_led = 0;
        self.marker = 0;
        self.steps_done = 0;
    }

    /// The counter (`marker` in the sketch).
    pub fn marker(&self) -> u8 {
        self.marker
    }

    /// One repaint: exactly one pass of the sketch's inner loop body.
    pub fn step(&mut self) {
        let i = self.next_led;
        let pos = (i + self.marker as usize) % PALETTE.len();
        self.frame[i] = maker_colour(PALETTE[pos]);
        self.marker = (self.marker + 1) % 12;
        self.next_led += 1;
        if self.next_led == LED_COUNT {
            self.next_led = 0;
            self.marker = self.rng.below(8);
        }
    }

    /// The frame at `t_ms` since the mode started (after the maker's 200/255,
    /// before the global cap). Repaints happen at t = 0, 40, 80, ... ms.
    /// Call with non-decreasing `t_ms`; a smaller value restarts.
    pub fn frame_at(&mut self, t_ms: u32) -> Frame {
        let due = t_ms / STEP_MS + 1;
        if due < self.steps_done {
            self.restart();
        }
        if due - self.steps_done > MAX_CATCH_UP {
            self.steps_done = due - MAX_CATCH_UP;
        }
        while self.steps_done < due {
            self.step();
            self.steps_done += 1;
        }
        self.frame
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    #[test]
    fn palette_matches_the_sketch() {
        assert_eq!(PALETTE.len(), 12);
        assert_eq!(PALETTE[0], Rgb::new(0, 11, 45));
        assert_eq!(PALETTE[1], Rgb::new(0, 53, 90));
        assert_eq!(PALETTE[4], Rgb::new(0, 191, 198));
        assert_eq!(PALETTE[11], Rgb::WHITE);
        // Gets steadily lighter from deep blue to white.
        for w in PALETTE.windows(2) {
            let sum = |c: Rgb| c.r as u32 + c.g as u32 + c.b as u32;
            assert!(sum(w[1]) > sum(w[0]));
        }
    }

    #[test]
    fn adafruit_brightness_200() {
        assert_eq!(maker_scale(255), 200);
        assert_eq!(maker_scale(0), 0);
        assert_eq!(maker_scale(45), 35); // (45 * 201) >> 8
        assert_eq!(maker_scale(1), 0);
    }

    #[test]
    fn first_pass_is_exactly_the_sketch() {
        // marker starts at 0: LED0 gets entry 0, then marker=1 so LED1 gets
        // (1+1)=2, LED2 gets (2+2)=4, LED3 gets (3+3)=6.
        let mut s = Shimmer::new(SEED);
        let f = s.frame_at(0);
        assert_eq!(f[0], maker_colour(PALETTE[0]));
        assert!(f[1].is_off() && f[2].is_off() && f[3].is_off());
        let f = s.frame_at(39);
        assert!(f[1].is_off(), "next repaint only at 40 ms");
        let f = s.frame_at(40);
        assert_eq!(f[1], maker_colour(PALETTE[2]));
        assert!(f[2].is_off());
        let f = s.frame_at(120);
        assert_eq!(f[2], maker_colour(PALETTE[4]));
        assert_eq!(f[3], maker_colour(PALETTE[6]));
        assert_eq!(f[0], maker_colour(PALETTE[0]), "others keep their colour");
    }

    #[test]
    fn counter_jumps_to_0_to_7_after_each_pass() {
        let mut s = Shimmer::new(SEED);
        let mut seen = [false; 8];
        for pass in 0..400 {
            for _ in 0..LED_COUNT {
                s.step();
            }
            let m = s.marker();
            assert!(m < 8, "pass {pass}: {m}");
            seen[m as usize] = true;
        }
        assert!(seen.iter().all(|&x| x), "every value 0..=7 turns up");
    }

    #[test]
    fn each_pass_is_a_two_step_gradient_from_the_new_counter() {
        let mut s = Shimmer::new(SEED);
        for _ in 0..LED_COUNT {
            s.step();
        }
        for _ in 0..50 {
            let start = s.marker() as usize;
            for _ in 0..LED_COUNT {
                s.step();
            }
            for i in 0..LED_COUNT {
                assert_eq!(s.frame[i], maker_colour(PALETTE[(start + 2 * i) % 12]));
            }
        }
    }

    #[test]
    fn never_brighter_than_200() {
        let mut s = Shimmer::new(SEED);
        for t in (0..20_000).step_by(10) {
            for c in s.frame_at(t) {
                assert!(c.r <= 200 && c.g <= 200 && c.b <= 200);
            }
        }
    }

    #[test]
    fn same_seed_same_show_and_restart_goes_dark() {
        let mut a = Shimmer::new(SEED);
        let mut b = Shimmer::new(SEED);
        let fa: Vec<Frame> = (0..200).map(|k| a.frame_at(k * 10)).collect();
        let fb: Vec<Frame> = (0..200).map(|k| b.frame_at(k * 10)).collect();
        assert_eq!(fa, fb);
        a.restart();
        let f = a.frame_at(0);
        assert!(f[1].is_off() && f[2].is_off() && f[3].is_off());
    }

    #[test]
    fn keeps_changing() {
        let mut s = Shimmer::new(SEED);
        let frames: Vec<Frame> = (0..100).map(|k| s.frame_at(k * STEP_MS)).collect();
        let distinct = frames
            .iter()
            .enumerate()
            .filter(|(i, f)| *i == 0 || frames[i - 1] != **f)
            .count();
        assert!(distinct > 50);
    }

    #[test]
    fn stall_skips_ahead_without_hanging() {
        let mut s = Shimmer::new(SEED);
        s.frame_at(0);
        s.frame_at(3_600_000); // an hour later
        assert_eq!(s.steps_done, 3_600_000 / STEP_MS + 1);
    }
}
