//! What the badge can say to TARS over the SAO's I2C pins.
//!
//! The maker's board had no I2C protocol: his RP2040 sketches never listened
//! on the badge's bus. So there is nothing to stay compatible with, and no
//! `maker-address` option; TARS answers at the house address [`ADDRESS`]
//! (0x27) only.
//!
//! Commands are 4 bytes, house style (as Mysterio and Mr. Robot):
//!
//! ```text
//! [ 0xE5, op, arg, 0x5E ]
//! ```
//!
//! Several may be sent in one write. A write whose length is not a multiple
//! of 4, or any chunk without both markers, is ignored as a whole.
//!
//! | op | arg | meaning |
//! |---|---|---|
//! | 0x01 | screen 0..=4 | show a screen: 0 menu, 1 piano, 2 hack the planet, 3 code rain, 4 scroller |
//! | 0x02 | MIDI note 1..=127, 0 = stop | play a note on the speaker until told to stop (a touch takes over) |
//! | 0x03 | 0 off, 1 on, 2 automatic | the cue light; automatic = lit while a pad is touched |
//! | 0x04 | pad 0..=5 | act as if that pad were tapped (0 A, 1 up, 2 B, 3 left, 4 down, 5 right) |
//!
//! A read returns 4 bytes: firmware major, minor, the screen shown, and the
//! six-bit touch mask (bit 0 = A ... bit 5 = right).

pub const ADDRESS: u8 = 0x27;
pub const EXT_START: u8 = 0xE5;
pub const EXT_END: u8 = 0x5E;
pub const OP_SCREEN: u8 = 0x01;
pub const OP_NOTE: u8 = 0x02;
pub const OP_CUE: u8 = 0x03;
pub const OP_TAP: u8 = 0x04;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    Screen(u8),
    Note(u8),
    Cue(u8),
    Tap(u8),
}

/// Parse one write. Returns the commands (up to 8) or None if the write is
/// not well-formed.
pub fn parse(bytes: &[u8]) -> Option<([Option<Command>; 8], usize)> {
    if bytes.is_empty() || bytes.len() % 4 != 0 || bytes.len() > 32 {
        return None;
    }
    let mut out = [None; 8];
    let mut n = 0;
    for c in bytes.chunks(4) {
        if c[0] != EXT_START || c[3] != EXT_END {
            return None;
        }
        let cmd = match c[1] {
            OP_SCREEN if c[2] <= 4 => Some(Command::Screen(c[2])),
            OP_NOTE if c[2] <= 127 => Some(Command::Note(c[2])),
            OP_CUE if c[2] <= 2 => Some(Command::Cue(c[2])),
            OP_TAP if c[2] <= 5 => Some(Command::Tap(c[2])),
            _ => None,
        };
        if cmd.is_some() {
            out[n] = cmd;
            n += 1;
        }
    }
    Some((out, n))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn one_and_several() {
        let (c, n) = parse(&[0xE5, 1, 2, 0x5E]).unwrap();
        assert_eq!((c[0], n), (Some(Command::Screen(2)), 1));
        let (c, n) = parse(&[0xE5, 2, 60, 0x5E, 0xE5, 3, 1, 0x5E]).unwrap();
        assert_eq!(n, 2);
        assert_eq!(c[1], Some(Command::Cue(1)));
    }

    #[test]
    fn junk_is_ignored() {
        assert!(parse(&[]).is_none());
        assert!(parse(&[1, 2, 3]).is_none());
        assert!(parse(&[0xE5, 1, 2, 0x5F]).is_none());
        let (_, n) = parse(&[0xE5, 9, 0, 0x5E]).unwrap(); // unknown op
        assert_eq!(n, 0);
        let (_, n) = parse(&[0xE5, 1, 5, 0x5E]).unwrap(); // no screen 5
        assert_eq!(n, 0);
    }
}
