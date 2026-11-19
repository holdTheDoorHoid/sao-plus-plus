//! Tones for the speaker, as the LED-PWM (LEDC) hardware wants them.
//!
//! The speaker sits between two XIAO pins (D10 through 165 ohm, and D2 through
//! the maker's jumper JP1). As in the maker's `TARS_tone` sketch, the two pins
//! play the same note in "push-pull": one pin is high for the first 30 % of
//! each cycle, the other for 30 % starting half a cycle later, so the speaker
//! is pushed one way, then the other. The maker used 30 % on purpose; it also
//! keeps the average current down (current flows 60 % of the time).
//!
//! With JP1 changed to its other position (D2 side to ground) only the D10
//! half plays: the same note, quieter.
//!
//! The LEDC counts a 10-bit cycle from an 80 MHz clock through a fractional
//! divider (10 integer bits, 8 fraction bits); this computes the divider.

pub const LEDC_SOURCE_HZ: u32 = 80_000_000;
pub const DUTY_BITS: u32 = 10;
pub const RANGE: u32 = 1 << DUTY_BITS;
/// The maker's 30 % duty.
pub const DUTY_PCT: u32 = 30;
/// Largest divider the LEDC timer register takes (18 bits).
pub const MAX_DIV_Q8: u32 = (1 << 18) - 1;

/// The maker's piano: C4 D4 E4 F4 G4 A4, played three times higher (his
/// sketch multiplied by 3), one per touch area in his order A, up, B, left,
/// down, right.
pub const PIANO_HZ: [f32; 6] = [261.63, 293.66, 329.63, 349.23, 392.0, 440.0];
pub const PIANO_MULT: f32 = 3.0;
/// His menu click: 1 kHz for 5 ms.
pub const CLICK_HZ: u32 = 1000;
pub const CLICK_MS: u32 = 5;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PushPull {
    /// Timer divider in 1/256 steps.
    pub div_q8: u32,
    /// High time of each pin, in counts of [`RANGE`].
    pub duty: u32,
    /// Where the second pin's high time starts.
    pub hpoint_b: u32,
}

/// The LEDC settings for `hz`, or None if the LEDC cannot make it.
pub fn push_pull(hz: u32) -> Option<PushPull> {
    if hz == 0 {
        return None;
    }
    let div = (LEDC_SOURCE_HZ as u64 * 256) / (hz as u64 * RANGE as u64);
    if !(256..=MAX_DIV_Q8 as u64).contains(&div) {
        return None;
    }
    Some(PushPull { div_q8: div as u32, duty: RANGE * DUTY_PCT / 100, hpoint_b: RANGE / 2 })
}

/// The frequency the LEDC really makes for a divider.
pub fn actual_hz(div_q8: u32) -> f32 {
    LEDC_SOURCE_HZ as f32 * 256.0 / (div_q8 as f32 * RANGE as f32)
}

/// Piano note for touch area `i` (0..6), in Hz.
pub fn piano_hz(i: usize) -> u32 {
    (PIANO_HZ[i] * PIANO_MULT + 0.5) as u32
}

/// A MIDI note number as Hz (for the badge's "play note" command).
pub fn midi_hz(note: u8) -> u32 {
    // 440 * 2^((n - 69) / 12) without floating-point powers: octave shifts of
    // a table of the twelve semitones above A4.
    const SEMI: [f32; 12] = [440.0, 466.16, 493.88, 523.25, 554.37, 587.33, 622.25, 659.26, 698.46, 739.99, 783.99, 830.61];
    let d = note as i32 - 69;
    let oct = d.div_euclid(12);
    let s = d.rem_euclid(12) as usize;
    let mut f = SEMI[s];
    if oct >= 0 {
        for _ in 0..oct {
            f *= 2.0;
        }
    } else {
        for _ in 0..-oct {
            f /= 2.0;
        }
    }
    (f + 0.5) as u32
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn piano_and_click_are_within_a_tenth_of_a_percent() {
        for i in 0..6 {
            let hz = piano_hz(i);
            let pp = push_pull(hz).unwrap();
            let err = (actual_hz(pp.div_q8) - hz as f32).abs() / hz as f32;
            assert!(err < 0.001, "{} Hz off by {}", hz, err);
        }
        assert!(push_pull(CLICK_HZ).is_some());
    }

    #[test]
    fn halves_do_not_overlap() {
        let pp = push_pull(785).unwrap();
        assert!(pp.duty <= pp.hpoint_b);
        assert!(pp.hpoint_b + pp.duty <= RANGE);
        assert_eq!(pp.duty, 307);
    }

    #[test]
    fn out_of_range_is_silence() {
        assert_eq!(push_pull(0), None);
        assert_eq!(push_pull(10), None); // divider too big
        assert_eq!(push_pull(1_000_000), None); // divider below 1
        assert!(push_pull(80).is_some());
        assert!(push_pull(20_000).is_some());
    }

    #[test]
    fn midi() {
        assert_eq!(midi_hz(69), 440);
        assert_eq!(midi_hz(81), 880);
        assert_eq!(midi_hz(60), 262);
        assert_eq!(midi_hz(57), 220);
    }
}
