//! The maker's light show: what his PIC program does, as a list of frames.
//!
//! Read from `mad_cat_backpack_v0.asm` (V1, 04 Nov 2018) by Peter Shabino.
//! His program is one long loop of busy-waits. Here every animation is turned
//! into a list of [`Frame`]s (eight LED levels and how long to hold them)
//! when it starts, and the firmware steps through the list by the clock.
//!
//! What his board does after power-on:
//! 1. The smile fades in, then (after a random 0.13 to 8.3 s) the eyes.
//! 2. Then, for ever: all eight LEDs stay full on for a random 0 to 33 s;
//!    then one of eight animations plays, picked at random from a 32-entry
//!    table in which "blink" appears 10 times, "lick right", "lick left" and
//!    "eye bobble" 4 times each, "smile out and in", "piano teeth" and
//!    "talking" 3 times each, and "sparkles" once.
//!
//! His README says "between 0 and 8 minutes"; his code waits at most 255
//! ticks of a 131 ms timer, about 33 s. This follows the code.
//!
//! Timing. His chip runs from its 16 MHz internal clock. Short delays count
//! ticks of a 8.192 ms timer ([`STEP_US`]); the long waits count ticks of a
//! 131.072 ms timer ([`WAIT_US`]). On the PIC the first tick of each delay can
//! be a little shorter (the timer's divider is not reset); here every tick is
//! full length.
//!
//! Brightness. His 16-step dimming table ([`PWM`]) is used unchanged. His chip
//! dims each LED by switching it on for (level + 1) of every 256 counts
//! (level 0 = off, 255 = always on); the firmware here does the same job with
//! its own method, see [`crate::dim`].

use crate::lfsr::Lfsr;
use crate::{LEFT_EYE, LED_COUNT, Levels, RIGHT_EYE, TOOTH};

/// Length of one short-delay tick on the maker's board.
pub const STEP_US: u32 = 8_192;
/// Length of one long-wait tick on the maker's board.
pub const WAIT_US: u32 = 131_072;

/// The maker's 16 brightness steps (index 0 = off, 15 = full).
pub const PWM: [u8; 16] = [
    0x00, 0x01, 0x03, 0x07, 0x0B, 0x12, 0x1E, 0x28, 0x32, 0x41, 0x50, 0x64, 0x7D, 0xA0, 0xC8, 0xFF,
];

/// Level for a step number; like his table lookup, only the low four bits count.
pub const fn pwm(step: u8) -> u8 {
    PWM[(step & 0x0F) as usize]
}

/// The eight animations, numbered in the order of his program's jump table.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Anim {
    /// Eyes fade out, a pause, the smile fades out, a pause, the smile fades
    /// back in, a pause, the eyes fade back in.
    SmileOutIn = 0,
    /// One eye or both close for a random 25 ms to 1 s.
    Blink = 1,
    /// A dim spot runs along the teeth from the cat's left (viewer's left) to right.
    LickRight = 2,
    /// The same, right to left.
    LickLeft = 3,
    /// Tooth 5 fades out and in, then the even and odd teeth take turns, 1 to 7 times.
    Piano = 4,
    /// The left eye fades out and in, then the right; 1 to 7 times.
    EyeBobble = 5,
    /// The outer teeth and then the next pair in pulse like a talking mouth, 1 to 7 times.
    Talk = 6,
    /// Every LED jumps to a random level, many times quickly, then all full on.
    Sparkles = 7,
}

pub const ANIM_COUNT: u8 = 8;

impl Anim {
    pub const ALL: [Anim; 8] = [
        Anim::SmileOutIn,
        Anim::Blink,
        Anim::LickRight,
        Anim::LickLeft,
        Anim::Piano,
        Anim::EyeBobble,
        Anim::Talk,
        Anim::Sparkles,
    ];

    pub const fn from_number(n: u8) -> Option<Anim> {
        if n < ANIM_COUNT {
            Some(Self::ALL[n as usize])
        } else {
            None
        }
    }
}

/// His 32-entry choice table, in his order (the low five bits of a random
/// draw pick the entry).
pub const PICK: [Anim; 32] = {
    use Anim::*;
    [
        SmileOutIn, Blink, LickRight, LickLeft, Piano, EyeBobble, Talk, Sparkles, //
        Blink, Blink, SmileOutIn, LickRight, //
        LickLeft, Piano, EyeBobble, Talk, //
        Blink, Blink, Blink, Blink, //
        LickRight, LickLeft, EyeBobble, Blink, //
        Blink, Blink, SmileOutIn, LickRight, LickLeft, Piano, EyeBobble, Talk,
    ]
};

/// One step of an animation: what the eight LEDs show, and for how long.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Frame {
    pub levels: Levels,
    pub us: u32,
}

/// The longest animation (piano teeth with 7 repeats) is 465 frames; one more
/// for the wait before it.
pub const CAPACITY: usize = 480;

/// A list of frames being built or played.
#[derive(Clone, Debug)]
pub struct Script {
    frames: [Frame; CAPACITY],
    len: usize,
    /// What the LEDs show at the end of the frames built so far.
    levels: Levels,
}

impl Script {
    pub const fn new(levels: Levels) -> Self {
        Self {
            frames: [Frame {
                levels: [0; LED_COUNT],
                us: 0,
            }; CAPACITY],
            len: 0,
            levels,
        }
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    pub fn frames(&self) -> &[Frame] {
        &self.frames[..self.len]
    }

    pub fn get(&self, i: usize) -> Option<&Frame> {
        self.frames().get(i)
    }

    /// Levels after the last frame.
    pub fn end_levels(&self) -> Levels {
        self.levels
    }

    pub fn total_us(&self) -> u64 {
        self.frames().iter().map(|f| f.us as u64).sum()
    }

    /// Start a new list, carrying on from `levels`.
    pub fn restart(&mut self, levels: Levels) {
        self.len = 0;
        self.levels = levels;
    }

    fn set(&mut self, leds: &[usize], level: u8) {
        for &i in leds {
            self.levels[i] = level;
        }
    }

    fn hold(&mut self, ticks: u32, tick_us: u32) {
        if ticks == 0 {
            return;
        }
        // Capacity is sized for the longest animation; a full list simply
        // stops growing (a test checks that never happens).
        if self.len < CAPACITY {
            self.frames[self.len] = Frame {
                levels: self.levels,
                us: ticks * tick_us,
            };
            self.len += 1;
        }
    }

    /// Hold the current levels for `us` microseconds (used by the firmware's
    /// own modes, not by the maker's show).
    pub fn hold_us(&mut self, us: u32) {
        self.hold(1, us);
    }

    /// His short delay: `ticks` x 8.192 ms.
    fn step(&mut self, ticks: u8) {
        self.hold(ticks as u32, STEP_US);
    }

    /// His long wait: `ticks` x 131 ms (0 = no wait).
    fn wait(&mut self, ticks: u8) {
        self.hold(ticks as u32, WAIT_US);
    }

    /// Fade `leds` down through steps 15..=1 (his down-counting loops), then
    /// leave them at whatever `end` says.
    fn fade_out(&mut self, leds: &[usize], ticks: u8) {
        for s in (1..=15u8).rev() {
            self.set(leds, pwm(s));
            self.step(ticks);
        }
    }

    /// Fade `leds` up through steps 0..=15 (his loops that count 0xF0 to 0xFF).
    fn fade_in(&mut self, leds: &[usize], ticks: u8) {
        for s in 0..=15u8 {
            self.set(leds, pwm(s));
            self.step(ticks);
        }
    }
}

const EYES: [usize; 2] = [LEFT_EYE, RIGHT_EYE];
const T: [usize; 6] = TOOTH;

/// Repeat count for piano, bobble and talking: an odd number 1..=7.
fn repeats(r: &mut Lfsr) -> u8 {
    (r.next() & 0x07) | 0x01
}

/// The second half of "smile out and in", which is also what his board does at
/// power-on: smile fades in, a pause, eyes fade in.
pub fn smile_in(s: &mut Script, r: &mut Lfsr) {
    s.fade_in(&T, 7);
    s.wait((r.next() & 0x3F) | 0x01);
    s.fade_in(&EYES, 7);
}

/// Append one animation to `s`. Random choices are drawn from `r` in the same
/// order as his program draws them.
pub fn build(anim: Anim, s: &mut Script, r: &mut Lfsr) {
    match anim {
        Anim::SmileOutIn => {
            s.fade_out(&EYES, 7);
            s.set(&EYES, 0);
            s.wait((r.next() & 0x3F) | 0x01);
            s.fade_out(&T, 7);
            s.set(&T, 0);
            s.wait(r.next() | 0x10);
            smile_in(s, r);
        }
        Anim::Blink => {
            // He reads two bits left in the generator by the draw that chose
            // this animation: a clear bit closes that eye; both set closes both.
            let (b0, b1) = (r.third_byte_bit(0), r.third_byte_bit(1));
            if !b0 || (b0 && b1) {
                s.set(&[LEFT_EYE], 0);
            }
            if !b1 || (b0 && b1) {
                s.set(&[RIGHT_EYE], 0);
            }
            s.step((r.next() & 0x7F) | 0x03);
            s.set(&EYES, 0xFF);
        }
        Anim::LickRight | Anim::LickLeft => {
            let order: [usize; 6] = if anim == Anim::LickRight {
                T
            } else {
                [T[5], T[4], T[3], T[2], T[1], T[0]]
            };
            for t in order {
                s.set(&[t], 0x20);
                s.step(8);
                s.set(&[t], 0xFF);
            }
            // The last tooth goes back to full with no delay after it; the
            // next frame (the wait) shows that.
        }
        Anim::Piano => {
            let n = repeats(r);
            s.fade_out(&[T[4]], 1);
            s.fade_in(&[T[4]], 1);
            for _ in 0..n {
                let even = [T[1], T[3], T[5]];
                let odd = [T[0], T[2], T[4]];
                s.fade_out(&even, 1);
                s.fade_in(&even, 1);
                s.fade_out(&odd, 1);
                s.fade_in(&odd, 1);
            }
        }
        Anim::EyeBobble => {
            let n = repeats(r);
            for _ in 0..n {
                s.fade_out(&[LEFT_EYE], 1);
                s.fade_in(&[LEFT_EYE], 1);
                s.fade_out(&[RIGHT_EYE], 1);
                s.fade_in(&[RIGHT_EYE], 1);
            }
        }
        Anim::Talk => {
            let n = repeats(r);
            let outer = [T[0], T[5]];
            let inner = [T[1], T[4]];
            // His talking delay: a random 1..=3 short ticks per step.
            let pause = |r: &mut Lfsr| match r.next() & 0x03 {
                0 => 1,
                x => x,
            };
            for _ in 0..n {
                // outer pair dims from step 15 down to 8 ...
                for c in (8..=15u8).rev() {
                    s.set(&outer, pwm(c));
                    let p = pause(r);
                    s.step(p);
                }
                // ... then keeps dimming (7..1) while the inner pair starts dimming from full (15..9)
                for c in (1..=7u8).rev() {
                    s.set(&outer, pwm(c));
                    s.set(&inner, pwm(c + 8));
                    let p = pause(r);
                    s.step(p);
                }
                s.set(&outer, 0);
                // inner pair dims from step 8 to 1 ...
                for c in (1..=8u8).rev() {
                    s.set(&inner, pwm(c));
                    let p = pause(r);
                    s.step(p);
                }
                // ... and comes back up 0..8 ...
                for c in 0..=8u8 {
                    s.set(&inner, pwm(c));
                    let p = pause(r);
                    s.step(p);
                }
                // ... on up 9..14 while the outer pair comes back 1..6
                for c in 9..=14u8 {
                    s.set(&inner, pwm(c));
                    s.set(&outer, pwm(c - 8));
                    let p = pause(r);
                    s.step(p);
                }
                s.set(&inner, 0xFF);
                // outer pair carries on up 8..14, then full
                for c in 8..=14u8 {
                    s.set(&outer, pwm(c));
                    let p = pause(r);
                    s.step(p);
                }
                s.set(&outer, 0xFF);
            }
        }
        Anim::Sparkles => {
            // His loop count is a full random byte; 0 means 256 rounds.
            let rounds = match r.next() {
                0 => 256u32,
                x => x as u32,
            };
            for _ in 0..rounds {
                for t in T {
                    let v = pwm(r.next());
                    s.set(&[t], v);
                }
                let v = pwm(r.next());
                s.set(&[LEFT_EYE], v);
                let v = pwm(r.next());
                s.set(&[RIGHT_EYE], v);
                let p = match r.next() & 0x07 {
                    0 => 1,
                    x => x,
                };
                s.step(p);
            }
            s.set(&EYES, 0xFF);
            s.set(&T, 0xFF);
        }
    }
}

/// One turn of his main loop: the all-on wait, then the animation the next
/// draw picks. Returns the animation and the index of its first frame (the
/// wait, if any, comes before it).
pub fn build_cycle(s: &mut Script, r: &mut Lfsr) -> (Anim, usize) {
    let wait = r.next();
    s.wait(wait);
    let from = s.len();
    let anim = PICK[(r.next() & 0x1F) as usize];
    build(anim, s, r);
    (anim, from)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ALL_OFF, ALL_ON};

    fn fresh() -> Script {
        Script::new(ALL_ON)
    }

    #[test]
    fn pick_table_has_his_weights() {
        let count = |a: Anim| PICK.iter().filter(|&&x| x == a).count();
        assert_eq!(count(Anim::Blink), 10);
        assert_eq!(count(Anim::LickRight), 4);
        assert_eq!(count(Anim::LickLeft), 4);
        assert_eq!(count(Anim::EyeBobble), 4);
        assert_eq!(count(Anim::SmileOutIn), 3);
        assert_eq!(count(Anim::Piano), 3);
        assert_eq!(count(Anim::Talk), 3);
        assert_eq!(count(Anim::Sparkles), 1);
        // the first eight entries are the animations in his numbering
        for (i, a) in Anim::ALL.iter().enumerate() {
            assert_eq!(PICK[i], *a);
            assert_eq!(*a as usize, i);
        }
    }

    #[test]
    fn pwm_table_is_his() {
        assert_eq!(pwm(0), 0);
        assert_eq!(pwm(15), 255);
        assert_eq!(pwm(0xF7), pwm(7));
        assert!(PWM.windows(2).all(|w| w[0] < w[1]));
    }

    #[test]
    fn power_on_fades_smile_then_eyes() {
        let mut s = Script::new(ALL_OFF);
        let mut r = Lfsr::new();
        smile_in(&mut s, &mut r);
        let f = s.frames();
        assert_eq!(f.len(), 16 + 1 + 16);
        // first frame: smile at step 0 (off), eyes off
        assert_eq!(f[0].levels, ALL_OFF);
        // during the smile fade the eyes stay off
        assert!(f[..16].iter().all(|x| x.levels[LEFT_EYE] == 0 && x.levels[RIGHT_EYE] == 0));
        assert_eq!(f[15].levels[TOOTH[0]], 255);
        // a pause of 1..=63 long ticks
        assert!(f[16].us >= WAIT_US && f[16].us <= 63 * WAIT_US);
        assert_eq!(s.end_levels(), ALL_ON);
        // every fade step is 7 short ticks
        assert!(f[..16].iter().all(|x| x.us == 7 * STEP_US));
    }

    #[test]
    fn every_animation_ends_all_on_and_fits() {
        for seed in [Lfsr::SEED, 1, 0xDEAD_BEEF, 0x8000_0001, 0x1234_5678] {
            let mut r = Lfsr::with_state(seed);
            for _ in 0..300 {
                for a in Anim::ALL {
                    let mut s = fresh();
                    build(a, &mut s, &mut r);
                    assert!(s.len() < CAPACITY, "{a:?} is {} frames", s.len());
                    assert!(!s.is_empty());
                    assert_eq!(s.end_levels(), ALL_ON, "{a:?} does not end all on");
                }
            }
        }
    }

    #[test]
    fn worst_case_lengths() {
        // repeats are 1..=7: find a generator state that gives 7 and check the frame counts
        let mut r = Lfsr::new();
        loop {
            let mut probe = r;
            if probe.next() & 0x07 == 0x07 {
                break;
            }
            r.next();
        }
        let mut s = fresh();
        build(Anim::Piano, &mut s, &mut r.clone());
        assert_eq!(s.len(), 31 + 7 * 62);
        let mut s = fresh();
        build(Anim::EyeBobble, &mut s, &mut r.clone());
        assert_eq!(s.len(), 7 * 62);
        let mut s = fresh();
        build(Anim::Talk, &mut s, &mut r.clone());
        assert_eq!(s.len(), 7 * (8 + 7 + 8 + 9 + 6 + 7));
    }

    #[test]
    fn licks_run_the_right_way() {
        let mut r = Lfsr::new();
        let mut s = fresh();
        build(Anim::LickRight, &mut s, &mut r);
        let dim: std::vec::Vec<usize> = s
            .frames()
            .iter()
            .map(|f| f.levels.iter().position(|&v| v == 0x20).unwrap())
            .collect();
        assert_eq!(dim, std::vec![2, 3, 4, 5, 6, 7]);
        assert!(s.frames().iter().all(|f| f.us == 8 * STEP_US));
        let mut s = fresh();
        build(Anim::LickLeft, &mut s, &mut r);
        let dim: std::vec::Vec<usize> = s
            .frames()
            .iter()
            .map(|f| f.levels.iter().position(|&v| v == 0x20).unwrap())
            .collect();
        assert_eq!(dim, std::vec![7, 6, 5, 4, 3, 2]);
    }

    #[test]
    fn blink_closes_the_eye_his_bits_say() {
        // Try many generator states; check against his rule directly.
        let mut r = Lfsr::new();
        let mut seen = [false; 3];
        for _ in 0..2_000 {
            r.next();
            let (b0, b1) = (r.third_byte_bit(0), r.third_byte_bit(1));
            let mut s = fresh();
            build(Anim::Blink, &mut s, &mut r.clone());
            assert_eq!(s.len(), 1);
            let f = s.frames()[0];
            let (left_closed, right_closed) = (f.levels[LEFT_EYE] == 0, f.levels[RIGHT_EYE] == 0);
            match (b0, b1) {
                (true, false) => assert_eq!((left_closed, right_closed), (false, true)),
                (false, true) => assert_eq!((left_closed, right_closed), (true, false)),
                _ => assert_eq!((left_closed, right_closed), (true, true)),
            }
            seen[left_closed as usize + right_closed as usize] = true;
            // teeth untouched, blink 3..=127 short ticks
            assert!(TOOTH.iter().all(|&t| f.levels[t] == 255));
            assert!(f.us >= 3 * STEP_US && f.us <= 127 * STEP_US);
        }
        assert!(seen[1] && seen[2], "both one-eye and two-eye blinks happen");
    }

    #[test]
    fn talk_moves_outer_then_inner_pair_only() {
        let mut r = Lfsr::new();
        let mut s = fresh();
        build(Anim::Talk, &mut s, &mut r);
        for f in s.frames() {
            // eyes and the middle teeth never move
            assert_eq!(f.levels[LEFT_EYE], 255);
            assert_eq!(f.levels[RIGHT_EYE], 255);
            assert_eq!(f.levels[TOOTH[2]], 255);
            assert_eq!(f.levels[TOOTH[3]], 255);
            // the two teeth of each pair always match
            assert_eq!(f.levels[TOOTH[0]], f.levels[TOOTH[5]]);
            assert_eq!(f.levels[TOOTH[1]], f.levels[TOOTH[4]]);
            assert!(f.us >= STEP_US && f.us <= 3 * STEP_US);
        }
    }

    #[test]
    fn sparkles_use_only_table_levels() {
        let mut r = Lfsr::with_state(0x0BAD_F00D);
        let mut s = fresh();
        build(Anim::Sparkles, &mut s, &mut r);
        assert!(s.len() >= 1 && s.len() <= 256);
        for f in s.frames() {
            assert!(f.levels.iter().all(|v| PWM.contains(v)));
            assert!(f.us >= STEP_US && f.us <= 7 * STEP_US);
        }
    }

    #[test]
    fn cycle_wait_is_up_to_255_long_ticks_all_on() {
        let mut r = Lfsr::new();
        for _ in 0..500 {
            let mut s = fresh();
            let (_, from) = build_cycle(&mut s, &mut r);
            assert!(from <= 1);
            let f0 = s.frames()[0];
            if f0.levels == ALL_ON && f0.us % WAIT_US == 0 && f0.us >= WAIT_US {
                assert!(f0.us <= 255 * WAIT_US);
            }
        }
    }

    #[test]
    fn first_cycles_after_power_on_are_reproducible() {
        let run = || {
            let mut r = Lfsr::new();
            let mut s = Script::new(ALL_OFF);
            smile_in(&mut s, &mut r);
            let mut picks = std::vec::Vec::new();
            for _ in 0..20 {
                let mut c = fresh();
                picks.push(build_cycle(&mut c, &mut r).0);
            }
            picks
        };
        assert_eq!(run(), run());
        // over a long run every animation turns up, blink most often
        let mut r = Lfsr::new();
        let mut n = [0u32; 8];
        for _ in 0..4_000 {
            let mut c = fresh();
            n[build_cycle(&mut c, &mut r).0 as usize] += 1;
        }
        assert!(n.iter().all(|&k| k > 0), "{n:?}");
        let blink = n[Anim::Blink as usize];
        assert!(n.iter().all(|&k| k <= blink), "{n:?}");
    }
}
