//! A tiny tune player: a tune is a list of notes and rests, each a whole
//! number of sixteenth notes long, played at a tempo in beats (quarter notes)
//! per minute.
//!
//! The built-in tunes are short jingles, arpeggios and alert beeps written
//! for this firmware. None of them is a transcription of existing music.

use crate::notes::{Note, name::*};

/// Tempo the board starts with, in beats (quarter notes) per minute.
pub const DEFAULT_BPM: u8 = 120;
/// Tempo limits; a badge asking for more or less gets the limit.
pub const MIN_BPM: u8 = 40;
pub const MAX_BPM: u8 = 240;

/// Every note ends with a short silence, so two equal notes in a row are
/// heard as two. Never more than a quarter of the note.
pub const GAP_MS: u32 = 15;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Step {
    /// A note lasting this many sixteenths.
    Note(Note, u8),
    /// Silence lasting this many sixteenths.
    Rest(u8),
}

impl Step {
    pub const fn sixteenths(self) -> u8 {
        match self {
            Step::Note(_, l) | Step::Rest(l) => l,
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct Tune {
    pub name: &'static str,
    pub steps: &'static [Step],
}

const fn n(note: Note, sixteenths: u8) -> Step {
    Step::Note(note, sixteenths)
}
const fn r(sixteenths: u8) -> Step {
    Step::Rest(sixteenths)
}

/// The built-in tunes, by number (the badge's "play tune n" command and the
/// jukebox mode use these numbers).
pub const TUNES: [Tune; 7] = [
    Tune {
        // Rising major arpeggio.
        name: "hello",
        steps: &[n(C5, 1), n(E5, 1), n(G5, 1), n(C6, 3)],
    },
    Tune {
        // Two-tone alert, three times.
        name: "alert",
        steps: &[n(A5, 1), n(E5, 1), n(A5, 1), n(E5, 1), n(A5, 1), n(E5, 1)],
    },
    Tune {
        // Falling arpeggio, ending low and long.
        name: "power down",
        steps: &[n(G5, 1), n(E5, 1), n(C5, 1), n(G4, 4)],
    },
    Tune {
        // Fast high-pitched robot babble.
        name: "chatter",
        steps: &[
            n(C7, 1),
            n(E6, 1),
            n(G7, 1),
            n(D6, 1),
            n(B6, 1),
            r(1),
            n(F6, 1),
            n(C7, 1),
            n(A6, 2),
        ],
    },
    Tune {
        // Climbing run with a held top note.
        name: "level up",
        steps: &[
            n(C5, 1),
            n(D5, 1),
            n(E5, 1),
            n(G5, 1),
            n(C6, 1),
            n(E6, 1),
            n(G6, 4),
        ],
    },
    Tune {
        // Two low tones: "nope".
        name: "error",
        steps: &[n(E3, 3), r(1), n(C3, 6)],
    },
    Tune {
        // Rising "huh?".
        name: "question",
        steps: &[n(G4, 1), n(C5, 1), r(1), n(D5, 3)],
    },
];

/// Played once at power-on, so a board with no lights can say it is alive.
pub const BOOT_CHIRP: &[Step] = &[n(E6, 1), n(A6, 1)];

/// Played when the mode button selects "listen" mode.
pub const MODE_BEEP: &[Step] = &[n(C6, 1)];

/// Clamp a badge-supplied tempo; 0 means "back to the default".
pub const fn clamp_bpm(bpm: u8) -> u8 {
    if bpm == 0 {
        DEFAULT_BPM
    } else if bpm < MIN_BPM {
        MIN_BPM
    } else if bpm > MAX_BPM {
        MAX_BPM
    } else {
        bpm
    }
}

/// Length of one sixteenth note in milliseconds.
pub const fn sixteenth_ms(bpm: u8) -> u32 {
    15_000 / clamp_bpm(bpm) as u32
}

/// Length of a step in milliseconds.
pub const fn step_ms(step: Step, bpm: u8) -> u32 {
    step.sixteenths() as u32 * sixteenth_ms(bpm)
}

/// Total length of a tune in milliseconds.
pub fn tune_ms(steps: &[Step], bpm: u8) -> u32 {
    steps.iter().map(|s| step_ms(*s, bpm)).sum()
}

/// Plays one tune through, once.
#[derive(Clone, Copy, Debug, Default)]
pub struct Sequencer {
    steps: Option<&'static [Step]>,
    index: usize,
    step_start: u32,
}

impl Sequencer {
    pub const fn new() -> Self {
        Self {
            steps: None,
            index: 0,
            step_start: 0,
        }
    }

    pub fn start(&mut self, steps: &'static [Step], now_ms: u32) {
        self.steps = if steps.is_empty() { None } else { Some(steps) };
        self.index = 0;
        self.step_start = now_ms;
    }

    pub fn stop(&mut self) {
        self.steps = None;
    }

    pub fn is_playing(&self) -> bool {
        self.steps.is_some()
    }

    /// What should sound at `now_ms`. Returns `None` for rests, gaps and once
    /// the tune has finished (after which [`Self::is_playing`] is false).
    pub fn update(&mut self, now_ms: u32, bpm: u8) -> Option<Note> {
        let steps = self.steps?;
        loop {
            let Some(&step) = steps.get(self.index) else {
                self.steps = None;
                return None;
            };
            let dur = step_ms(step, bpm);
            let t = now_ms.wrapping_sub(self.step_start);
            if t >= dur {
                // Next step starts exactly where this one ended, so timing
                // does not drift even if updates come late.
                self.step_start = self.step_start.wrapping_add(dur);
                self.index += 1;
                continue;
            }
            return match step {
                Step::Note(note, _) if t < dur - gap_ms(dur) => Some(note),
                _ => None,
            };
        }
    }
}

const fn gap_ms(note_ms: u32) -> u32 {
    if GAP_MS < note_ms / 4 {
        GAP_MS
    } else {
        note_ms / 4
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tempo_maths() {
        assert_eq!(sixteenth_ms(120), 125);
        assert_eq!(sixteenth_ms(60), 250);
        assert_eq!(sixteenth_ms(0), 125, "0 = default");
        assert_eq!(sixteenth_ms(1), sixteenth_ms(MIN_BPM));
        assert_eq!(sixteenth_ms(255), sixteenth_ms(MAX_BPM));
        assert_eq!(clamp_bpm(100), 100);
    }

    #[test]
    fn plays_steps_in_order_with_gaps_then_ends() {
        static T: &[Step] = &[n(C5, 1), r(1), n(E5, 2)];
        let mut s = Sequencer::new();
        s.start(T, 1_000);
        assert!(s.is_playing());
        assert_eq!(s.update(1_000, 120), Some(C5));
        assert_eq!(s.update(1_000 + 125 - GAP_MS - 1, 120), Some(C5));
        assert_eq!(s.update(1_000 + 125 - GAP_MS, 120), None, "gap");
        assert_eq!(s.update(1_000 + 125, 120), None, "rest");
        assert_eq!(s.update(1_000 + 250, 120), Some(E5));
        assert_eq!(s.update(1_000 + 499 - GAP_MS, 120), Some(E5));
        assert_eq!(s.update(1_000 + 500, 120), None);
        assert!(!s.is_playing());
        assert_eq!(s.update(5_000, 120), None);
    }

    #[test]
    fn late_updates_do_not_drift() {
        static T: &[Step] = &[n(C5, 1), n(D5, 1), n(E5, 1)];
        let mut s = Sequencer::new();
        s.start(T, 0);
        // Jump straight into the third note.
        assert_eq!(s.update(260, 120), Some(E5));
        assert_eq!(s.update(375, 120), None);
        assert!(!s.is_playing());
    }

    #[test]
    fn tempo_scales_length() {
        let fast = tune_ms(TUNES[0].steps, 120);
        let slow = tune_ms(TUNES[0].steps, 60);
        assert_eq!(slow, fast * 2);
    }

    #[test]
    fn stop_silences() {
        let mut s = Sequencer::new();
        s.start(TUNES[1].steps, 0);
        assert!(s.update(10, 120).is_some());
        s.stop();
        assert_eq!(s.update(20, 120), None);
        assert!(!s.is_playing());
    }

    #[test]
    fn empty_tune_is_not_playing() {
        let mut s = Sequencer::new();
        s.start(&[], 0);
        assert!(!s.is_playing());
    }

    #[test]
    fn built_in_tunes_are_short_and_sane() {
        for t in TUNES.iter() {
            assert!(!t.steps.is_empty(), "{}", t.name);
            let ms = tune_ms(t.steps, DEFAULT_BPM);
            assert!(ms > 0 && ms <= 2_500, "{} is {ms} ms", t.name);
            for s in t.steps {
                assert!(s.sixteenths() > 0, "{}", t.name);
                if let Step::Note(note, _) = s {
                    // Stay where a small sounder makes an audible tone.
                    assert!(
                        note.hz() >= 120 && note.hz() <= 4_200,
                        "{} {note:?}",
                        t.name
                    );
                }
            }
        }
        assert!(tune_ms(BOOT_CHIRP, DEFAULT_BPM) <= 300);
        assert!(tune_ms(MODE_BEEP, DEFAULT_BPM) <= 150);
    }

    #[test]
    fn tune_names_are_unique() {
        for (i, a) in TUNES.iter().enumerate() {
            for b in &TUNES[i + 1..] {
                assert_ne!(a.name, b.name);
            }
        }
    }

    #[test]
    fn gap_never_eats_more_than_a_quarter() {
        assert_eq!(gap_ms(125), GAP_MS);
        assert_eq!(gap_ms(40), 10);
        // Shortest possible note at the fastest tempo still sounds.
        let shortest = sixteenth_ms(MAX_BPM);
        assert!(shortest - gap_ms(shortest) >= shortest * 3 / 4);
    }
}
