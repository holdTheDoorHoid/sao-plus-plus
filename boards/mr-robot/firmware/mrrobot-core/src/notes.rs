//! The maker's 89-note table: note numbers 1..=89 are B0 (31 Hz) up to D#8
//! (4978 Hz) in semitone steps, exactly as numbered in his `SlaveMrRobot.ino`
//! (`notes[1]` = B0, `notes[2]` = C1, ... `notes[89]` = D#8). Note 0 is "off"
//! and is not a [`Note`].
//!
//! The frequencies are equal temperament with A4 = 440 Hz, rounded to whole
//! hertz. They are not trusted from a copy: a test recomputes every one from
//! the formula. Against his `pitches.h` the table differs in one place only:
//! F#2 (note 20) is 92 Hz here, 93 Hz in his file (the true value is 92.50 Hz;
//! 93 is a long-standing slip in the Arduino example `pitches.h`). The
//! difference is under 1 % and cannot be heard on a small sounder.

/// How many notes the maker's protocol can address (1..=89).
pub const NOTE_COUNT: u8 = 89;

/// Frequencies in Hz, index `note number - 1`.
const NOTE_HZ: [u16; NOTE_COUNT as usize] = [
    31, 33, 35, 37, 39, 41, 44, 46, 49, 52, //
    55, 58, 62, 65, 69, 73, 78, 82, 87, 92, //
    98, 104, 110, 117, 123, 131, 139, 147, 156, 165, //
    175, 185, 196, 208, 220, 233, 247, 262, 277, 294, //
    311, 330, 349, 370, 392, 415, 440, 466, 494, 523, //
    554, 587, 622, 659, 698, 740, 784, 831, 880, 932, //
    988, 1047, 1109, 1175, 1245, 1319, 1397, 1480, 1568, 1661, //
    1760, 1865, 1976, 2093, 2217, 2349, 2489, 2637, 2794, 2960, //
    3136, 3322, 3520, 3729, 3951, 4186, 4435, 4699, 4978,
];

/// A playable note, number 1..=89 in the maker's numbering. Holding one of
/// these is proof the number is in range: there is no way to build a `Note`
/// for 0 or for 90 and up.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct Note(u8);

impl Note {
    /// `None` for 0 (the maker's "off") and for anything above 89.
    pub const fn new(number: u8) -> Option<Note> {
        if number >= 1 && number <= NOTE_COUNT {
            Some(Note(number))
        } else {
            None
        }
    }

    /// The maker's note number, 1..=89.
    pub const fn number(self) -> u8 {
        self.0
    }

    /// MIDI note number (B0 = 23, middle C = 60, A4 = 69).
    pub const fn midi(self) -> u8 {
        self.0 + 22
    }

    /// Frequency in whole hertz.
    pub const fn hz(self) -> u32 {
        NOTE_HZ[(self.0 - 1) as usize] as u32
    }

    /// The same note `semitones` higher (or lower), if still in range.
    pub const fn shifted(self, semitones: i8) -> Option<Note> {
        let n = self.0 as i16 + semitones as i16;
        if n >= 1 && n <= NOTE_COUNT as i16 {
            Some(Note(n as u8))
        } else {
            None
        }
    }
}

/// Note names for writing tunes. Octave numbers are scientific pitch
/// (C4 = middle C = note 38). `S` = sharp.
#[allow(dead_code)]
pub mod name {
    use super::Note;

    /// Note number of C in octave `octave` (1..=8).
    const fn c(octave: u8) -> u8 {
        2 + 12 * (octave - 1)
    }
    const fn n(octave: u8, semis: u8) -> Note {
        Note(c(octave) + semis)
    }

    pub const B0: Note = Note(1);
    pub const C3: Note = n(3, 0);
    pub const D3: Note = n(3, 2);
    pub const E3: Note = n(3, 4);
    pub const F3: Note = n(3, 5);
    pub const G3: Note = n(3, 7);
    pub const A3: Note = n(3, 9);
    pub const B3: Note = n(3, 11);
    pub const C4: Note = n(4, 0);
    pub const D4: Note = n(4, 2);
    pub const E4: Note = n(4, 4);
    pub const F4: Note = n(4, 5);
    pub const G4: Note = n(4, 7);
    pub const A4: Note = n(4, 9);
    pub const B4: Note = n(4, 11);
    pub const C5: Note = n(5, 0);
    pub const D5: Note = n(5, 2);
    pub const E5: Note = n(5, 4);
    pub const F5: Note = n(5, 5);
    pub const FS5: Note = n(5, 6);
    pub const G5: Note = n(5, 7);
    pub const A5: Note = n(5, 9);
    pub const B5: Note = n(5, 11);
    pub const C6: Note = n(6, 0);
    pub const D6: Note = n(6, 2);
    pub const E6: Note = n(6, 4);
    pub const F6: Note = n(6, 5);
    pub const G6: Note = n(6, 7);
    pub const A6: Note = n(6, 9);
    pub const B6: Note = n(6, 11);
    pub const C7: Note = n(7, 0);
    pub const E7: Note = n(7, 4);
    pub const G7: Note = n(7, 7);
    pub const C8: Note = n(8, 0);
    pub const DS8: Note = n(8, 3);
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The maker's `pitches.h`, transcribed only to compare against.
    const MAKER: [u16; 89] = [
        31, 33, 35, 37, 39, 41, 44, 46, 49, 52, 55, 58, 62, 65, 69, 73, 78, 82, 87, 93, 98, 104,
        110, 117, 123, 131, 139, 147, 156, 165, 175, 185, 196, 208, 220, 233, 247, 262, 277, 294,
        311, 330, 349, 370, 392, 415, 440, 466, 494, 523, 554, 587, 622, 659, 698, 740, 784, 831,
        880, 932, 988, 1047, 1109, 1175, 1245, 1319, 1397, 1480, 1568, 1661, 1760, 1865, 1976,
        2093, 2217, 2349, 2489, 2637, 2794, 2960, 3136, 3322, 3520, 3729, 3951, 4186, 4435, 4699,
        4978,
    ];

    fn equal_tempered(midi: u8) -> f64 {
        440.0 * 2f64.powf((midi as f64 - 69.0) / 12.0)
    }

    #[test]
    fn every_note_is_equal_temperament_rounded() {
        for n in 1..=NOTE_COUNT {
            let note = Note::new(n).unwrap();
            let exact = equal_tempered(note.midi());
            assert_eq!(note.hz(), exact.round() as u32, "note {n} ({exact:.2} Hz)");
        }
    }

    #[test]
    fn range_is_b0_to_d_sharp_8() {
        assert_eq!(Note::new(1).unwrap().hz(), 31);
        assert_eq!(Note::new(1).unwrap().midi(), 23); // B0
        assert_eq!(Note::new(89).unwrap().hz(), 4978);
        assert_eq!(Note::new(89).unwrap().midi(), 111); // D#8
        assert_eq!(name::C4.hz(), 262);
        assert_eq!(name::A4.hz(), 440);
        assert_eq!(name::DS8.number(), 89);
        assert_eq!(name::B0.number(), 1);
    }

    #[test]
    fn zero_and_above_89_are_not_notes() {
        for n in 0..=255u8 {
            assert_eq!(Note::new(n).is_some(), (1..=89).contains(&n), "{n}");
        }
    }

    #[test]
    fn matches_the_makers_table_except_f_sharp_2() {
        let mut differ = std::vec::Vec::new();
        for (i, &m) in MAKER.iter().enumerate() {
            let ours = Note::new(i as u8 + 1).unwrap().hz();
            if ours != m as u32 {
                differ.push((i + 1, m, ours));
            }
        }
        assert_eq!(differ, [(20, 93, 92)]);
    }

    #[test]
    fn strictly_rising() {
        for n in 1..NOTE_COUNT {
            assert!(Note::new(n + 1).unwrap().hz() > Note::new(n).unwrap().hz());
        }
    }

    #[test]
    fn shifting_stays_in_range() {
        assert_eq!(name::C4.shifted(12), Some(name::C5));
        assert_eq!(name::C4.shifted(-12).unwrap().hz(), 131);
        assert_eq!(Note::new(1).unwrap().shifted(-1), None);
        assert_eq!(Note::new(89).unwrap().shifted(1), None);
    }
}
