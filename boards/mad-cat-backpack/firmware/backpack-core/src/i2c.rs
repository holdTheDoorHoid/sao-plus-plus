//! I2C command protocol (the add-on is an I2C target at 7-bit address 0x24).
//!
//! The 2018 backpack had no I2C at all (its PIC only animated the LEDs), so
//! there is no maker's protocol to keep. This uses the house style of the
//! SAO++ boards with single-colour LEDs (Do Or Donut, 0x1C): every command is
//! exactly 4 bytes, one write may carry several back to back, and Clear (5),
//! Latch (6), Brightness (7) and Mode (8) have the same numbers and meaning.
//! One command is new here: Play (9), which runs one of the maker's
//! animations on demand.
//!
//! | byte 0 | bytes 1..3          | meaning                                                         |
//! |--------|---------------------|-----------------------------------------------------------------|
//! | 5      | ignored             | clear all cued LEDs (to off). Not shown until latched           |
//! | 6      | ignored             | latch: show the cued LEDs                                       |
//! | 7      | brightness, -, -    | brightness for cued LEDs, 0 = off, 255 = full. Takes effect at once |
//! | 8      | mode, -, -          | leave I2C mode and run built-in mode 0..=2                      |
//! | 9      | animation, -, -     | leave I2C mode and play the maker's animation 0..=7 now         |
//! | 0x10   | LED 0..=7, level, - | cue one LED                                                     |
//! | 0x11   | level, -, -         | cue every LED                                                   |
//! | 0x90   | LED 0..=7, level, - | cue one LED, ignoring the brightness setting                    |
//! | 0x91   | level, -, -         | cue every LED, ignoring the brightness setting                  |
//!
//! LED numbers: 0 = left eye, 1 = right eye, 2..=7 = teeth left to right (as
//! seen from the front). Levels: 0 = off, 255 = full, linear in on-time.
//!
//! Anything else is invalid and ignored (it also does not count as activity
//! for the I2C-mode timeout), including a mode number >= 3, an animation
//! number >= 8 or an LED number >= 8.

use crate::LED_COUNT;
use crate::show::{ANIM_COUNT, Anim};

/// 7-bit target address (house numbering: 0x24 for this board).
pub const ADDRESS: u8 = 0x24;

/// Brightness setting for cued LEDs when the board starts.
pub const I2C_START_BRIGHTNESS: u8 = 255;

pub const COMMAND_LEN: usize = 4;

/// Without a valid command for this long, the board leaves I2C mode and goes
/// back to its own show.
pub const I2C_TIMEOUT_MS: u32 = 5_000;

pub const OP_CLEAR: u8 = 5;
pub const OP_LATCH: u8 = 6;
pub const OP_BRIGHTNESS: u8 = 7;
pub const OP_MODE: u8 = 8;
pub const OP_PLAY: u8 = 9;
pub const OP_CUE: u8 = 0x10;
pub const OP_CUE_ALL: u8 = 0x11;
/// Added to OP_CUE / OP_CUE_ALL: ignore the brightness setting.
pub const RAW: u8 = 0x80;

/// Number of built-in modes (see `app::Mode`).
pub const MODE_COUNT: u8 = 3;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    Cue { index: u8, level: u8, raw: bool },
    CueAll { level: u8, raw: bool },
    Clear,
    Latch,
    Brightness(u8),
    SetMode(u8),
    Play(Anim),
}

impl Command {
    /// Parse one 4-byte command. `None` if it is not a valid command.
    pub fn parse(b: [u8; COMMAND_LEN]) -> Option<Command> {
        let raw = b[0] & RAW != 0;
        match b[0] {
            OP_CLEAR => Some(Command::Clear),
            OP_LATCH => Some(Command::Latch),
            OP_BRIGHTNESS => Some(Command::Brightness(b[1])),
            OP_MODE if b[1] < MODE_COUNT => Some(Command::SetMode(b[1])),
            OP_PLAY if b[1] < ANIM_COUNT => Anim::from_number(b[1]).map(Command::Play),
            0x10 | 0x90 if (b[1] as usize) < LED_COUNT => Some(Command::Cue {
                index: b[1],
                level: b[2],
                raw,
            }),
            0x11 | 0x91 => Some(Command::CueAll { level: b[1], raw }),
            _ => None,
        }
    }

    /// True for the commands that put the board under the badge's control.
    pub const fn takes_over(&self) -> bool {
        !matches!(self, Command::SetMode(_) | Command::Play(_))
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Cue {
    pub level: u8,
    pub raw: bool,
}

const OFF: Cue = Cue {
    level: 0,
    raw: false,
};

/// Cued and latched LEDs plus I2C brightness.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct I2cState {
    pub cued: [Cue; LED_COUNT],
    pub latched: [Cue; LED_COUNT],
    pub brightness: u8,
}

impl Default for I2cState {
    fn default() -> Self {
        Self::new()
    }
}

impl I2cState {
    pub const fn new() -> Self {
        Self {
            cued: [OFF; LED_COUNT],
            latched: [OFF; LED_COUNT],
            brightness: I2C_START_BRIGHTNESS,
        }
    }

    /// Forget cued and latched LEDs (kept: brightness).
    pub fn reset_levels(&mut self) {
        let b = self.brightness;
        *self = Self::new();
        self.brightness = b;
    }

    /// Apply an LED command. Mode and Play are handled by the app, not here.
    pub fn apply(&mut self, cmd: Command) {
        match cmd {
            Command::Cue { index, level, raw } => {
                if let Some(c) = self.cued.get_mut(index as usize) {
                    *c = Cue { level, raw };
                }
            }
            Command::CueAll { level, raw } => self.cued = [Cue { level, raw }; LED_COUNT],
            Command::Clear => self.cued = [OFF; LED_COUNT],
            Command::Latch => self.latched = self.cued,
            Command::Brightness(b) => self.brightness = b,
            Command::SetMode(_) | Command::Play(_) => {}
        }
    }

    /// What the LEDs show in I2C mode.
    pub fn levels(&self) -> crate::Levels {
        let mut out = [0u8; LED_COUNT];
        for (o, c) in out.iter_mut().zip(self.latched.iter()) {
            *o = if c.raw {
                c.level
            } else {
                ((c.level as u16 * self.brightness as u16 + 127) / 255) as u8
            };
        }
        out
    }
}

/// Split a received write into commands. Returns how many were valid.
/// `sink` is called for each valid command in order.
pub fn parse_write(bytes: &[u8], mut sink: impl FnMut(Command)) -> usize {
    let mut valid = 0;
    for chunk in bytes.as_chunks::<COMMAND_LEN>().0 {
        if let Some(cmd) = Command::parse(*chunk) {
            sink(cmd);
            valid += 1;
        }
    }
    valid
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    #[test]
    fn parses_every_opcode() {
        assert_eq!(Command::parse([5, 9, 9, 9]), Some(Command::Clear));
        assert_eq!(Command::parse([6, 9, 9, 9]), Some(Command::Latch));
        assert_eq!(Command::parse([7, 200, 9, 9]), Some(Command::Brightness(200)));
        assert_eq!(Command::parse([8, 2, 0, 0]), Some(Command::SetMode(2)));
        assert_eq!(Command::parse([9, 6, 0, 0]), Some(Command::Play(Anim::Talk)));
        for i in 0..8u8 {
            assert_eq!(
                Command::parse([0x10, i, 77, 0]),
                Some(Command::Cue { index: i, level: 77, raw: false })
            );
            assert_eq!(
                Command::parse([0x90, i, 77, 0]),
                Some(Command::Cue { index: i, level: 77, raw: true })
            );
        }
        assert_eq!(Command::parse([0x11, 5, 0, 0]), Some(Command::CueAll { level: 5, raw: false }));
        assert_eq!(Command::parse([0x91, 5, 0, 0]), Some(Command::CueAll { level: 5, raw: true }));
    }

    #[test]
    fn rejects_everything_else() {
        for op in 0..=255u8 {
            for arg in [0u8, 2, 3, 7, 8, 200] {
                let valid = match op {
                    5..=7 | 0x11 | 0x91 => true,
                    8 => arg < 3,
                    9 => arg < 8,
                    0x10 | 0x90 => arg < 8,
                    _ => false,
                };
                assert_eq!(Command::parse([op, arg, 1, 1]).is_some(), valid, "op {op} arg {arg}");
            }
        }
    }

    #[test]
    fn several_commands_in_one_write_and_partial_tail_ignored() {
        let mut got = Vec::new();
        let n = parse_write(&[0x10, 0, 255, 0, 0x10, 9, 1, 1, 6, 0, 0, 0, 7, 1], |c| got.push(c));
        assert_eq!(n, 2);
        assert_eq!(got, std::vec![Command::Cue { index: 0, level: 255, raw: false }, Command::Latch]);
    }

    #[test]
    fn brightness_scales_cued_but_not_raw() {
        let mut s = I2cState::new();
        s.apply(Command::Cue { index: 0, level: 200, raw: false });
        s.apply(Command::Cue { index: 1, level: 200, raw: true });
        s.apply(Command::Brightness(128));
        assert_eq!(s.levels(), [0; LED_COUNT], "nothing shows until latched");
        s.apply(Command::Latch);
        let l = s.levels();
        assert_eq!(l[0], 100);
        assert_eq!(l[1], 200);
        s.apply(Command::Clear);
        assert_eq!(s.levels()[0], 100, "clear acts on the cue, not on what is shown");
        s.apply(Command::Latch);
        assert_eq!(s.levels(), [0; LED_COUNT]);
    }

    #[test]
    fn mode_and_play_do_not_take_over() {
        assert!(!Command::SetMode(0).takes_over());
        assert!(!Command::Play(Anim::Blink).takes_over());
        assert!(Command::Latch.takes_over());
        assert!(Command::Brightness(1).takes_over());
    }
}
