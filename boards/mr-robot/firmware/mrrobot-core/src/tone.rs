//! Tone output rules, independent of the chip.
//!
//! The sounder hangs on a transistor switched by one pin (XIAO D10). Pin high
//! = current flows through the sounder (up to about 19 mA, set by the board's
//! resistors). Two rules follow, and this module is where they are enforced:
//!
//! 1. **At most 50 % duty.** A note is a square wave whose high time is never
//!    more than half its period. [`SquareWave`] can only be built through
//!    constructors that guarantee this, and its LEDC duty value is exactly
//!    half the counter range.
//! 2. **Never high when idle.** A pin left high puts a steady DC current
//!    through a coil-type sounder (19 mA for no sound, and heat). The hardware
//!    layer implements [`ToneHw`], whose `output_low` must drive the pin low
//!    and keep it there. [`ToneGen`] is the only thing the firmware uses to
//!    make sound; it calls `output_low` when created, on every silence, and
//!    when dropped, so "silent" and "pin low" are the same state.
//!
//! The firmware drives the pin with the chip's LEDC (LED PWM) peripheral: a
//! hardware timer generates the square wave, so the CPU does no work per
//! cycle. The LEDC numbers (clock divider and duty) are worked out here so
//! they can be checked on a PC for all 89 notes.

use crate::notes::Note;

/// Lowest and highest frequency a [`SquareWave`] may have. The maker's notes
/// span 31..=4978 Hz; this leaves a little room either side.
pub const MIN_HZ: u32 = 20;
pub const MAX_HZ: u32 = 10_000;

/// LEDC counter resolution the firmware uses (12 bits: counts 0..4095).
pub const LEDC_DUTY_BITS: u32 = 12;

/// LEDC clock on all three chips (80 MHz APB / PLL clock).
pub const LEDC_SOURCE_HZ: u32 = 80_000_000;

/// Largest LEDC clock divider (10 integer + 8 fraction bits); smallest is 1.0.
const LEDC_DIV_MAX_Q8: u64 = 0x3FFFF;
const LEDC_DIV_MIN_Q8: u64 = 256;

/// A square wave with at most 50 % duty. The only way to get one is
/// [`SquareWave::for_note`] or [`SquareWave::for_hz`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SquareWave {
    freq_hz: u32,
}

impl SquareWave {
    pub const fn for_note(note: Note) -> SquareWave {
        SquareWave { freq_hz: note.hz() }
    }

    /// `None` outside [`MIN_HZ`]..=[`MAX_HZ`].
    pub const fn for_hz(freq_hz: u32) -> Option<SquareWave> {
        if freq_hz >= MIN_HZ && freq_hz <= MAX_HZ {
            Some(SquareWave { freq_hz })
        } else {
            None
        }
    }

    pub const fn freq_hz(&self) -> u32 {
        self.freq_hz
    }

    /// Period in ticks of a timer running at `clock_hz` (rounded).
    pub const fn period_ticks(&self, clock_hz: u32) -> u32 {
        (clock_hz + self.freq_hz / 2) / self.freq_hz
    }

    /// High time in ticks: half the period, rounded down, so never more
    /// than 50 %.
    pub const fn high_ticks(&self, clock_hz: u32) -> u32 {
        self.period_ticks(clock_hz) / 2
    }

    /// LEDC duty value for a counter of `bits` bits: exactly half the range.
    pub const fn ledc_duty(&self, bits: u32) -> u32 {
        1 << (bits - 1)
    }

    /// The LEDC clock divider (fixed point, 8 fraction bits) esp-hal 1.2.2
    /// will program for this frequency, using the same formula it does.
    /// `None` if the LEDC cannot make this frequency at this resolution
    /// (esp-hal would then return an error).
    pub const fn ledc_divider_q8(&self, source_hz: u32, bits: u32) -> Option<u32> {
        let div = ((source_hz as u64) << 8) / self.freq_hz as u64 / (1u64 << bits);
        if div >= LEDC_DIV_MIN_Q8 && div <= LEDC_DIV_MAX_Q8 {
            Some(div as u32)
        } else {
            None
        }
    }

    /// The frequency the LEDC really produces with that divider, in
    /// millihertz.
    pub const fn ledc_actual_mhz(&self, source_hz: u32, bits: u32) -> Option<u64> {
        match self.ledc_divider_q8(source_hz, bits) {
            Some(div) => Some(((source_hz as u64) << 8) * 1000 / (div as u64 * (1u64 << bits))),
            None => None,
        }
    }
}

/// What the hardware layer must provide.
pub trait ToneHw {
    /// Output this square wave (start it, or retune a running one). The
    /// hardware must not exceed the wave's duty: 50 % at most.
    fn output_square(&mut self, wave: SquareWave);
    /// Stop any waveform, drive the pin low and keep it low. Must be safe to
    /// call at any time, any number of times. If setting a square wave fails,
    /// the implementation must fall back to this.
    fn output_low(&mut self);
}

/// The one way the firmware makes sound. Silent means pin low, always.
pub struct ToneGen<H: ToneHw> {
    hw: H,
    playing: Option<Note>,
}

impl<H: ToneHw> ToneGen<H> {
    /// Takes the hardware and immediately forces the pin low.
    pub fn new(mut hw: H) -> Self {
        hw.output_low();
        Self { hw, playing: None }
    }

    /// Play `note`, or go silent for `None`. Only touches the hardware when
    /// something changes (a held note is not restarted every tick).
    pub fn set(&mut self, note: Option<Note>) {
        if note == self.playing {
            return;
        }
        self.playing = note;
        match note {
            Some(n) => self.hw.output_square(SquareWave::for_note(n)),
            None => self.hw.output_low(),
        }
    }

    /// Silence. Always forces the pin low again, even if already silent, so
    /// it can be used as a "make sure" before sleep.
    pub fn silence(&mut self) {
        self.playing = None;
        self.hw.output_low();
    }

    pub fn playing(&self) -> Option<Note> {
        self.playing
    }

    #[cfg(test)]
    pub fn hw(&self) -> &H {
        &self.hw
    }
}

impl<H: ToneHw> Drop for ToneGen<H> {
    fn drop(&mut self) {
        self.hw.output_low();
    }
}

#[cfg(test)]
pub mod mock {
    //! A pretend pin that records what the hardware layer was told, and
    //! checks the two rules on every call.
    use super::*;

    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub enum Pin {
        /// Never touched: on real hardware the level is unknown. A ToneGen
        /// must never leave the pin in this state.
        Untouched,
        Low,
        Square(SquareWave),
    }

    pub struct MockPin {
        pub pin: Pin,
        pub calls: u32,
    }

    impl Default for MockPin {
        fn default() -> Self {
            Self::new()
        }
    }

    impl MockPin {
        pub const fn new() -> Self {
            Self {
                pin: Pin::Untouched,
                calls: 0,
            }
        }
    }

    impl ToneHw for MockPin {
        fn output_square(&mut self, wave: SquareWave) {
            // Rule 1, for every clock the chips might use.
            for clock in [1_000_000, 40_000_000, 80_000_000, 160_000_000] {
                assert!(wave.high_ticks(clock) * 2 <= wave.period_ticks(clock));
            }
            assert_eq!(wave.ledc_duty(LEDC_DUTY_BITS) * 2, 1 << LEDC_DUTY_BITS);
            self.pin = Pin::Square(wave);
            self.calls += 1;
        }
        fn output_low(&mut self) {
            self.pin = Pin::Low;
            self.calls += 1;
        }
    }

    /// A shared-state version, so a test can still look at the pin after the
    /// ToneGen that owned it is dropped.
    pub struct SharedPin<'a>(pub &'a core::cell::Cell<Pin>);

    impl ToneHw for SharedPin<'_> {
        fn output_square(&mut self, wave: SquareWave) {
            self.0.set(Pin::Square(wave));
        }
        fn output_low(&mut self) {
            self.0.set(Pin::Low);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::mock::{MockPin, Pin, SharedPin};
    use super::*;
    use crate::notes::NOTE_COUNT;

    fn all_notes() -> impl Iterator<Item = Note> {
        (1..=NOTE_COUNT).map(|n| Note::new(n).unwrap())
    }

    #[test]
    fn duty_never_above_half_for_any_note_or_clock() {
        for note in all_notes() {
            let w = SquareWave::for_note(note);
            for clock in [1_000_000, 16_000_000, 40_000_000, 80_000_000, 240_000_000] {
                let p = w.period_ticks(clock);
                assert!(p > 0);
                assert!(w.high_ticks(clock) * 2 <= p, "{note:?} @ {clock}");
            }
            for bits in 1..=14 {
                assert_eq!(w.ledc_duty(bits) * 2, 1 << bits);
            }
        }
    }

    #[test]
    fn period_matches_frequency() {
        let w = SquareWave::for_note(crate::notes::name::A4);
        assert_eq!(w.period_ticks(1_000_000), 2273); // 1e6 / 440 = 2272.7
        assert_eq!(w.high_ticks(1_000_000), 1136);
        assert_eq!(
            SquareWave::for_hz(1000).unwrap().period_ticks(80_000_000),
            80_000
        );
    }

    #[test]
    fn for_hz_rejects_out_of_range() {
        assert!(SquareWave::for_hz(0).is_none());
        assert!(SquareWave::for_hz(MIN_HZ - 1).is_none());
        assert!(SquareWave::for_hz(MIN_HZ).is_some());
        assert!(SquareWave::for_hz(MAX_HZ).is_some());
        assert!(SquareWave::for_hz(MAX_HZ + 1).is_none());
    }

    #[test]
    fn ledc_can_make_every_note_at_12_bits() {
        for note in all_notes() {
            let w = SquareWave::for_note(note);
            assert!(
                w.ledc_divider_q8(LEDC_SOURCE_HZ, LEDC_DUTY_BITS).is_some(),
                "{note:?}"
            );
            // And it comes out within 0.5 % (under 9 cents) of the asked
            // frequency; in practice the worst note is far closer.
            let actual = w.ledc_actual_mhz(LEDC_SOURCE_HZ, LEDC_DUTY_BITS).unwrap();
            let want = w.freq_hz() as u64 * 1000;
            assert!(
                actual.abs_diff(want) * 200 <= want,
                "{note:?}: {actual} mHz"
            );
        }
    }

    #[test]
    fn ledc_limits_are_where_expected() {
        // 12 bits from 80 MHz: about 19 Hz .. 19.5 kHz.
        assert!(
            SquareWave::for_hz(20)
                .unwrap()
                .ledc_divider_q8(80_000_000, 12)
                .is_some()
        );
        assert!(
            SquareWave::for_hz(10_000)
                .unwrap()
                .ledc_divider_q8(80_000_000, 12)
                .is_some()
        );
        // 14 bits cannot reach the top note, which is why 12 is used.
        assert!(
            SquareWave::for_hz(4978)
                .unwrap()
                .ledc_divider_q8(80_000_000, 14)
                .is_none()
        );
        // 10 bits cannot reach the bottom note.
        assert!(
            SquareWave::for_hz(31)
                .unwrap()
                .ledc_divider_q8(80_000_000, 10)
                .is_none()
        );
    }

    #[test]
    fn new_forces_pin_low_immediately() {
        let t = ToneGen::new(MockPin::new());
        assert_eq!(t.hw().pin, Pin::Low);
        assert_eq!(t.playing(), None);
    }

    #[test]
    fn silence_is_always_pin_low() {
        let mut t = ToneGen::new(MockPin::new());
        t.set(Some(crate::notes::name::A4));
        assert!(matches!(t.hw().pin, Pin::Square(_)));
        t.set(None);
        assert_eq!(t.hw().pin, Pin::Low);
        t.set(Some(crate::notes::name::C4));
        t.silence();
        assert_eq!(t.hw().pin, Pin::Low);
        // silence() re-asserts low even if already silent.
        let before = t.hw().calls;
        t.silence();
        assert_eq!(t.hw().calls, before + 1);
    }

    #[test]
    fn held_note_is_not_retriggered() {
        let mut t = ToneGen::new(MockPin::new());
        t.set(Some(crate::notes::name::A4));
        let calls = t.hw().calls;
        for _ in 0..100 {
            t.set(Some(crate::notes::name::A4));
        }
        assert_eq!(t.hw().calls, calls);
    }

    #[test]
    fn drop_leaves_pin_low() {
        let cell = core::cell::Cell::new(Pin::Untouched);
        {
            let mut t = ToneGen::new(SharedPin(&cell));
            t.set(Some(crate::notes::name::E5));
            assert!(matches!(cell.get(), Pin::Square(_)));
        }
        assert_eq!(cell.get(), Pin::Low);
    }

    #[test]
    fn idle_invariant_under_random_use() {
        // Pseudo-random sequence of set/silence; after each call, "not
        // playing" must mean "pin low", and playing must mean the right wave.
        let mut t = ToneGen::new(MockPin::new());
        let mut x: u32 = 12345;
        for _ in 0..20_000 {
            x = x.wrapping_mul(1_103_515_245).wrapping_add(12_345);
            let r = (x >> 16) as u8;
            match r % 4 {
                0 => t.silence(),
                1 => t.set(None),
                _ => t.set(Note::new(r % 100)),
            }
            match t.playing() {
                None => assert_eq!(t.hw().pin, Pin::Low),
                Some(n) => assert_eq!(t.hw().pin, Pin::Square(SquareWave::for_note(n))),
            }
        }
    }
}
