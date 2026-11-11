//! I2C command protocol (the add-on is an I2C target at 7-bit address 0x1C).
//!
//! Same style as the Hack-Man (0x1A) and Mysterio (0x1B) firmware: every
//! command is exactly 4 bytes, one write may carry several back to back, and
//! the commands Clear (5), Latch (6) and Brightness (7) have the same numbers
//! and meaning. The LED commands are different because this board has 144
//! single-colour LEDs instead of a few colour ones. Hack-Man's and Mysterio's
//! colour commands (0..=4, 128..=132) are deliberately NOT valid here, so a
//! badge driver aimed at the wrong address does nothing.
//!
//! | byte 0 | bytes 1..3              | meaning                                                         |
//! |--------|-------------------------|-----------------------------------------------------------------|
//! | 5      | ignored                 | clear all cued LEDs (to off). Not shown until latched           |
//! | 6      | ignored                 | latch: show the cued LEDs                                       |
//! | 7      | brightness, -, -        | brightness for cued LEDs, 0 = off, 255 = full. Takes effect at once |
//! | 8      | mode, -, -              | leave I2C mode and run built-in mode 0..=4                      |
//! | 0x10   | LED 0..=143, level, -   | cue one LED                                                     |
//! | 0x11   | level, -, -             | cue every LED                                                   |
//! | 0x90   | LED 0..=143, level, -   | cue one LED, ignoring the brightness setting                    |
//! | 0x91   | level, -, -             | cue every LED, ignoring the brightness setting                  |
//!
//! LED numbers are the maker's order (0 = DA1 ... 71 = DA72, 72 = DB1 ...
//! 143 = DB72; positions in `hardware/matrix.json`). Levels are the chip's
//! PWM values directly (0..=255, linear in current, not gamma-corrected).
//!
//! Anything else is invalid and ignored (it also does not count as activity
//! for the I2C-mode timeout), including a mode number >= 5 or an LED number
//! >= 144.
//!
//! The current cap ([`crate::budget`]) still applies on top of everything,
//! "ignoring brightness" ones included; it is applied by [`crate::app::App`].

use crate::modes::{MODE_COUNT, Mode};
use crate::{Frame, LED_COUNT};

/// 7-bit target address.
pub const ADDRESS: u8 = 0x1C;

/// Brightness setting for cued LEDs when the board starts. Full: the
/// current cap already keeps the LEDs safe.
pub const I2C_START_BRIGHTNESS: u8 = 255;

pub const COMMAND_LEN: usize = 4;

/// Without a valid command for this long, the board leaves I2C mode and goes
/// back to its own animation.
pub const I2C_TIMEOUT_MS: u32 = 5_000;

pub const OP_CLEAR: u8 = 5;
pub const OP_LATCH: u8 = 6;
pub const OP_BRIGHTNESS: u8 = 7;
pub const OP_MODE: u8 = 8;
pub const OP_CUE: u8 = 0x10;
pub const OP_CUE_ALL: u8 = 0x11;
/// Added to OP_CUE / OP_CUE_ALL: ignore the brightness setting.
pub const RAW: u8 = 0x80;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    Cue { index: u8, level: u8, raw: bool },
    CueAll { level: u8, raw: bool },
    Clear,
    Latch,
    Brightness(u8),
    SetMode(Mode),
}

impl Command {
    /// Parse one 4-byte command. `None` if it is not a valid command.
    pub fn parse(b: [u8; COMMAND_LEN]) -> Option<Command> {
        let raw = b[0] & RAW != 0;
        match b[0] {
            OP_CLEAR => Some(Command::Clear),
            OP_LATCH => Some(Command::Latch),
            OP_BRIGHTNESS => Some(Command::Brightness(b[1])),
            OP_MODE if b[1] < MODE_COUNT => Mode::from_number(b[1]).map(Command::SetMode),
            0x10 | 0x90 if (b[1] as usize) < LED_COUNT => Some(Command::Cue {
                index: b[1],
                level: b[2],
                raw,
            }),
            0x11 | 0x91 => Some(Command::CueAll { level: b[1], raw }),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Cue {
    pub level: u8,
    pub raw: bool,
}

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

const OFF: Cue = Cue {
    level: 0,
    raw: false,
};

impl I2cState {
    pub const fn new() -> Self {
        Self {
            cued: [OFF; LED_COUNT],
            latched: [OFF; LED_COUNT],
            brightness: I2C_START_BRIGHTNESS,
        }
    }

    /// Forget cued and latched LEDs (kept: brightness).
    pub fn reset_colours(&mut self) {
        let b = self.brightness;
        *self = Self::new();
        self.brightness = b;
    }

    /// Apply an LED command. `SetMode` is handled by the app, not here.
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
            Command::SetMode(_) => {}
        }
    }

    /// PWM values the badge asked for (brightness applied; the current cap
    /// is applied afterwards by the app).
    pub fn frame(&self) -> Frame {
        let mut f = [0u8; LED_COUNT];
        for (out, cue) in f.iter_mut().zip(self.latched.iter()) {
            *out = if cue.raw {
                cue.level
            } else {
                scale8(cue.level, self.brightness)
            };
        }
        f
    }
}

/// `v * level / 255`, rounded to nearest (same arithmetic as Mysterio's).
pub const fn scale8(v: u8, level: u8) -> u8 {
    let p = v as u16 * level as u16 + 128;
    ((p + (p >> 8)) >> 8) as u8
}

/// Split a received write into commands. Returns how many were valid.
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

    #[test]
    fn parses_every_opcode() {
        assert_eq!(Command::parse([5, 9, 9, 9]), Some(Command::Clear));
        assert_eq!(Command::parse([6, 9, 9, 9]), Some(Command::Latch));
        assert_eq!(
            Command::parse([7, 200, 9, 9]),
            Some(Command::Brightness(200))
        );
        assert_eq!(
            Command::parse([8, 2, 0, 0]),
            Some(Command::SetMode(Mode::Pulse))
        );
        assert_eq!(
            Command::parse([0x10, 143, 77, 0]),
            Some(Command::Cue {
                index: 143,
                level: 77,
                raw: false
            })
        );
        assert_eq!(
            Command::parse([0x90, 0, 77, 0]),
            Some(Command::Cue {
                index: 0,
                level: 77,
                raw: true
            })
        );
        assert_eq!(
            Command::parse([0x11, 5, 0, 0]),
            Some(Command::CueAll {
                level: 5,
                raw: false
            })
        );
        assert_eq!(
            Command::parse([0x91, 5, 0, 0]),
            Some(Command::CueAll {
                level: 5,
                raw: true
            })
        );
    }

    #[test]
    fn rejects_everything_else() {
        for op in 0..=255u8 {
            let valid = matches!(op, 5..=8 | 0x10 | 0x11 | 0x90 | 0x91);
            assert_eq!(Command::parse([op, 0, 0, 0]).is_some(), valid, "op={op}");
        }
    }

    #[test]
    fn out_of_range_arguments_are_invalid() {
        assert_eq!(Command::parse([0x10, 144, 1, 0]), None);
        assert_eq!(Command::parse([0x90, 255, 1, 0]), None);
        assert_eq!(Command::parse([8, MODE_COUNT, 0, 0]), None);
        assert_eq!(Command::parse([8, 255, 0, 0]), None);
    }

    #[test]
    fn hack_man_and_mysterio_colour_commands_are_ignored() {
        for op in [0, 1, 2, 3, 4, 128, 129, 130, 131, 132] {
            assert_eq!(Command::parse([op, 255, 255, 255]), None);
        }
        assert_eq!(ADDRESS, 0x1C);
    }

    #[test]
    fn cue_is_invisible_until_latched() {
        let mut s = I2cState::new();
        s.apply(Command::Cue {
            index: 9,
            level: 50,
            raw: false,
        });
        assert_eq!(s.frame(), [0; LED_COUNT]);
        s.apply(Command::Latch);
        assert_eq!(s.frame()[9], 50);
    }

    #[test]
    fn clear_affects_cues_not_display() {
        let mut s = I2cState::new();
        s.apply(Command::CueAll {
            level: 20,
            raw: false,
        });
        s.apply(Command::Latch);
        s.apply(Command::Clear);
        assert_eq!(s.frame(), [20; LED_COUNT], "clear must wait for latch");
        s.apply(Command::Latch);
        assert_eq!(s.frame(), [0; LED_COUNT]);
    }

    #[test]
    fn brightness_applies_immediately_except_raw() {
        let mut s = I2cState::new();
        s.apply(Command::Cue {
            index: 0,
            level: 200,
            raw: false,
        });
        s.apply(Command::Cue {
            index: 1,
            level: 200,
            raw: true,
        });
        s.apply(Command::Latch);
        s.apply(Command::Brightness(0));
        assert_eq!(s.frame()[0], 0);
        assert_eq!(s.frame()[1], 200);
        s.apply(Command::Brightness(128));
        assert_eq!(s.frame()[0], 100);
    }

    #[test]
    fn scale8_endpoints() {
        for v in 0..=255u8 {
            assert_eq!(scale8(v, 255), v);
            assert_eq!(scale8(v, 0), 0);
        }
    }

    #[test]
    fn multi_command_writes_and_partial_tail() {
        let bytes = [0x10, 1, 2, 0, 99, 0, 0, 0, 6, 0, 0, 0, 7, 1];
        let mut got = std::vec::Vec::new();
        assert_eq!(parse_write(&bytes, |c| got.push(c)), 2);
        assert_eq!(got[1], Command::Latch);
        assert_eq!(parse_write(&[6, 0, 0], |_| panic!()), 0);
    }

    #[test]
    fn reset_keeps_brightness() {
        let mut s = I2cState::new();
        s.apply(Command::Brightness(9));
        s.apply(Command::CueAll {
            level: 255,
            raw: true,
        });
        s.apply(Command::Latch);
        s.reset_colours();
        assert_eq!(s.brightness, 9);
        assert_eq!(s.frame(), [0; LED_COUNT]);
    }
}
