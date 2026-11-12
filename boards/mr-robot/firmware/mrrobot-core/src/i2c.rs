//! I2C command protocol. The add-on is an I2C target at 7-bit address
//! [`ADDRESS`]: 0x1D (house numbering: Hack-Man 0x1A, Mysterio 0x1B, Do Or
//! Donut 0x1C), or the maker's original 0x08 when built with the
//! `maker-address` cargo feature.
//!
//! # 1. The maker's protocol, unchanged
//!
//! From his `SlaveMrRobot.ino`: in every write only the **last byte**
//! matters; any earlier bytes are read and thrown away.
//!
//! | last byte | meaning |
//! |---|---|
//! | 0 | silence |
//! | 1..=89 | play that note (1 = B0 ... 89 = D#8) until the next write |
//! | 90..=255 | **ignored** (his code had no range check and would play a random frequency; ours does nothing) |
//!
//! An empty write (an address probe) is ignored too (his code would read
//! past the buffer).
//!
//! # 2. Extended commands (SAO++)
//!
//! Each extended command is 4 bytes, house style like Mysterio's:
//!
//! ```text
//! [ 0xE5, op, arg, 0x5E ]
//! ```
//!
//! A write is treated as extended only if its length is a non-zero multiple
//! of 4 **and every** 4-byte chunk starts with [`EXT_START`] (0xE5) and ends
//! with [`EXT_END`] (0x5E). Several commands may be sent in one write.
//! Anything else is read with the maker's rule.
//!
//! **Why this cannot collide with the maker's writes.** Under his rule a
//! write means whatever its last byte says. Every extended write ends in
//! 0x5E = 94, which is above 89: under his rule it means "ignore". So:
//! * any write his badge code sends that means something (last byte 0..=89)
//!   can never be mistaken for an extended command, and
//! * an extended command sent to an original board (with a range check) is
//!   ignored rather than played as a note.
//!
//! The leading 0xE5 is a second marker, so a stray 4-byte write ending in 94
//! is not taken for a command either.
//!
//! | op | arg | meaning |
//! |---|---|---|
//! | 0x01 | tune number 0..=6 | play a built-in tune once (stops any held note) |
//! | 0x02 | ignored | stop: silence everything (held note and tune) |
//! | 0x03 | beats per minute | tune tempo; 0 = back to 120; clamped to 40..=240 |
//!
//! Unknown op codes and tune numbers out of range are ignored, and do not
//! count as badge activity.
//!
//! **Volume** cannot be set: the sounder is switched fully on and off by a
//! transistor, and its loudness is fixed by the board's current-limiting
//! resistors (about 19 mA peak). There is deliberately no volume command.
//!
//! # 3. Reading
//!
//! A read returns 4 status bytes, see [`crate::app::App::status`].

use crate::notes::Note;
use crate::tune::TUNES;

/// House address. Hack-Man 0x1A, Mysterio 0x1B, Do Or Donut 0x1C.
pub const HOUSE_ADDRESS: u8 = 0x1D;
/// The maker's original address (his `Wire.begin(8)`).
pub const MAKER_ADDRESS: u8 = 0x08;

/// The 7-bit address this build answers at. Change it with the
/// `maker-address` cargo feature, nowhere else.
#[cfg(not(feature = "maker-address"))]
pub const ADDRESS: u8 = HOUSE_ADDRESS;
#[cfg(feature = "maker-address")]
pub const ADDRESS: u8 = MAKER_ADDRESS;

pub const EXT_START: u8 = 0xE5;
pub const EXT_END: u8 = 0x5E;
pub const EXT_LEN: usize = 4;

pub const OP_PLAY_TUNE: u8 = 0x01;
pub const OP_STOP: u8 = 0x02;
pub const OP_TEMPO: u8 = 0x03;

/// Highest note number the maker's protocol accepts.
pub const MAKER_MAX_NOTE: u8 = crate::notes::NOTE_COUNT;

// The framing argument above depends on these.
const _: () = assert!(EXT_END > MAKER_MAX_NOTE);
const _: () = assert!(EXT_START > MAKER_MAX_NOTE);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    /// Maker's protocol: 0.
    Silence,
    /// Maker's protocol: 1..=89, hold until the next command.
    Hold(Note),
    /// Extended: play built-in tune number `.0` (already range-checked).
    PlayTune(u8),
    /// Extended: stop everything.
    Stop,
    /// Extended: tempo in BPM as sent (the app clamps it).
    Tempo(u8),
}

/// Is this write in the extended framing?
pub fn is_extended(bytes: &[u8]) -> bool {
    !bytes.is_empty()
        && bytes.len().is_multiple_of(EXT_LEN)
        && bytes
            .as_chunks::<EXT_LEN>()
            .0
            .iter()
            .all(|c| c[0] == EXT_START && c[3] == EXT_END)
}

/// Parse one extended 4-byte chunk (already known to be framed).
fn parse_extended(op: u8, arg: u8) -> Option<Command> {
    match op {
        OP_PLAY_TUNE if (arg as usize) < TUNES.len() => Some(Command::PlayTune(arg)),
        OP_STOP => Some(Command::Stop),
        OP_TEMPO => Some(Command::Tempo(arg)),
        _ => None,
    }
}

/// The maker's rule: only the last byte counts.
pub fn parse_maker(bytes: &[u8]) -> Option<Command> {
    match *bytes.last()? {
        0 => Some(Command::Silence),
        b => Note::new(b).map(Command::Hold),
    }
}

/// Split a received write into commands, calling `sink` for each valid one
/// in order. Returns how many were valid.
pub fn parse_write(bytes: &[u8], mut sink: impl FnMut(Command)) -> usize {
    if is_extended(bytes) {
        let mut valid = 0;
        for c in bytes.as_chunks::<EXT_LEN>().0 {
            if let Some(cmd) = parse_extended(c[1], c[2]) {
                sink(cmd);
                valid += 1;
            }
        }
        valid
    } else if let Some(cmd) = parse_maker(bytes) {
        sink(cmd);
        1
    } else {
        0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    fn parse(bytes: &[u8]) -> Vec<Command> {
        let mut v = Vec::new();
        let n = parse_write(bytes, |c| v.push(c));
        assert_eq!(n, v.len());
        v
    }

    #[test]
    fn address_is_house_by_default() {
        #[cfg(not(feature = "maker-address"))]
        assert_eq!(ADDRESS, 0x1D);
        #[cfg(feature = "maker-address")]
        assert_eq!(ADDRESS, 0x08);
        // Distinct from the other house boards and outside the reserved
        // 0x00..=0x07 and 0x78..=0x7F ranges.
        for a in [HOUSE_ADDRESS, MAKER_ADDRESS] {
            assert!((0x08..=0x77).contains(&a));
            assert!(![0x1A, 0x1B, 0x1C].contains(&a));
        }
    }

    #[test]
    fn every_single_byte_write_follows_the_maker() {
        for b in 0..=255u8 {
            let got = parse(&[b]);
            match b {
                0 => assert_eq!(got, [Command::Silence]),
                1..=89 => assert_eq!(got, [Command::Hold(Note::new(b).unwrap())]),
                _ => assert!(got.is_empty(), "{b} must be ignored"),
            }
        }
    }

    #[test]
    fn every_two_byte_write_follows_the_maker() {
        for a in 0..=255u8 {
            for b in 0..=255u8 {
                assert_eq!(parse(&[a, b]), parse(&[b]), "[{a}, {b}]");
            }
        }
    }

    #[test]
    fn longer_maker_writes_use_the_last_byte() {
        assert_eq!(parse(&[9, 9, 9, 0]), [Command::Silence]);
        assert_eq!(
            parse(&[0xE5, 1, 2, 47]),
            [Command::Hold(Note::new(47).unwrap())]
        );
        assert_eq!(
            parse(&[1, 2, 3, 4, 5]),
            [Command::Hold(Note::new(5).unwrap())]
        );
        // A write that is almost extended but has one bad chunk falls back
        // to the maker's rule, and its last byte (94) means "ignore".
        assert!(parse(&[0xE5, OP_STOP, 0, 0x5E, 0xE4, OP_STOP, 0, 0x5E]).is_empty());
    }

    #[test]
    fn any_write_meaning_something_to_the_maker_is_never_extended() {
        // Exhaustive over all 4-byte writes with the extended start marker
        // and a meaningful last byte (the only 4-byte writes that could be
        // confused): none is extended.
        for op in 0..=255u8 {
            for arg in 0..=255u8 {
                for last in 0..=MAKER_MAX_NOTE {
                    assert!(!is_extended(&[EXT_START, op, arg, last]));
                }
            }
        }
    }

    #[test]
    fn every_extended_write_means_nothing_to_the_maker() {
        for op in 0..=255u8 {
            for arg in [0u8, 1, 6, 7, 89, 255] {
                let w = [EXT_START, op, arg, EXT_END];
                assert!(is_extended(&w));
                assert_eq!(parse_maker(&w), None);
            }
        }
    }

    #[test]
    fn extended_commands_parse() {
        assert_eq!(parse(&[0xE5, 1, 3, 0x5E]), [Command::PlayTune(3)]);
        assert_eq!(parse(&[0xE5, 2, 77, 0x5E]), [Command::Stop]);
        assert_eq!(parse(&[0xE5, 3, 90, 0x5E]), [Command::Tempo(90)]);
        assert_eq!(
            parse(&[0xE5, 3, 200, 0x5E, 0xE5, 1, 0, 0x5E]),
            [Command::Tempo(200), Command::PlayTune(0)]
        );
    }

    #[test]
    fn bad_extended_commands_are_ignored() {
        assert!(parse(&[0xE5, 1, TUNES.len() as u8, 0x5E]).is_empty());
        assert!(parse(&[0xE5, 0, 0, 0x5E]).is_empty());
        assert!(parse(&[0xE5, 4, 0, 0x5E]).is_empty());
        assert!(parse(&[0xE5, 0xFF, 0, 0x5E]).is_empty());
        // Good and bad mixed: only the good one counts.
        assert_eq!(
            parse(&[0xE5, 9, 0, 0x5E, 0xE5, 2, 0, 0x5E]),
            [Command::Stop]
        );
    }

    #[test]
    fn empty_write_is_ignored() {
        assert!(parse(&[]).is_empty());
        assert!(!is_extended(&[]));
    }
}
