//! I2C command protocol (the add-on is an I2C target at 7-bit address 0x1B).
//!
//! Same 4-byte protocol and command numbers as the Hack-Man SAO (address
//! 0x1A), so one badge-side driver works for both and the two can share a
//! bus. Only the address and the number of LEDs differ.
//!
//! Every command is exactly 4 bytes. A single I2C write may carry several
//! commands back to back (8, 12, ... bytes); trailing bytes that do not make a
//! whole command are ignored.
//!
//! | byte 0     | bytes 1..3        | meaning                                                        |
//! |------------|-------------------|----------------------------------------------------------------|
//! | 0 ..= 3    | R, G, B           | cue a colour for LED index (0 = D1, right-hand LED from the front) |
//! | 5          | ignored           | clear all cued colours (to black)                               |
//! | 6          | ignored           | latch: show the cued colours                                    |
//! | 7          | brightness, -, -  | brightness for cued colours, 0 = off, 255 = max                 |
//! | 128 ..= 131| R, G, B           | cue a colour for LED (byte0 - 128) that ignores the brightness setting |
//!
//! Anything else is invalid and ignored (it also does not count as activity
//! for the I2C-mode timeout). That includes 4 and 132: Hack-Man's fifth LED
//! does not exist here.
//!
//! The global brightness cap ([`crate::GLOBAL_BRIGHTNESS_CAP`]) still applies
//! on top of everything, raw colours included; it is applied by
//! [`crate::app::App`], not here.

use crate::{Frame, LED_COUNT, Rgb};

/// 7-bit target address.
pub const ADDRESS: u8 = 0x1B;

/// Brightness setting for cued colours when the board starts. Full, because
/// the global cap already keeps the LEDs modest (Hack-Man starts at 48, but
/// it has no separate cap).
pub const I2C_START_BRIGHTNESS: u8 = 255;

/// Length of every command.
pub const COMMAND_LEN: usize = 4;

/// Without a valid command for this long, the board leaves I2C mode and goes
/// back to its own animation.
pub const I2C_TIMEOUT_MS: u32 = 5_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Command {
    /// Cue a colour. `raw == true` means it ignores global brightness.
    Cue {
        index: u8,
        color: Rgb,
        raw: bool,
    },
    Clear,
    Latch,
    Brightness(u8),
}

impl Command {
    /// Parse one 4-byte command. `None` if it is not a valid command.
    pub fn parse(b: [u8; COMMAND_LEN]) -> Option<Command> {
        let color = Rgb::new(b[1], b[2], b[3]);
        match b[0] {
            i @ 0..=3 => Some(Command::Cue {
                index: i,
                color,
                raw: false,
            }),
            5 => Some(Command::Clear),
            6 => Some(Command::Latch),
            7 => Some(Command::Brightness(b[1])),
            i @ 128..=131 => Some(Command::Cue {
                index: i - 128,
                color,
                raw: true,
            }),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Cue {
    pub color: Rgb,
    pub raw: bool,
}

/// Cued and latched colours plus I2C brightness.
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
            cued: [Cue {
                color: Rgb::OFF,
                raw: false,
            }; LED_COUNT],
            latched: [Cue {
                color: Rgb::OFF,
                raw: false,
            }; LED_COUNT],
            brightness: I2C_START_BRIGHTNESS,
        }
    }

    /// Forget cued and latched colours (kept: brightness). Used when the
    /// board enters I2C mode fresh, so stale colours from an earlier session
    /// do not reappear.
    pub fn reset_colours(&mut self) {
        let b = self.brightness;
        *self = Self::new();
        self.brightness = b;
    }

    pub fn apply(&mut self, cmd: Command) {
        match cmd {
            Command::Cue { index, color, raw } => {
                if let Some(c) = self.cued.get_mut(index as usize) {
                    *c = Cue { color, raw };
                }
            }
            Command::Clear => self.cued = [Cue::default(); LED_COUNT],
            Command::Latch => self.latched = self.cued,
            Command::Brightness(b) => self.brightness = b,
        }
    }

    /// What the LEDs show in I2C mode (I2C brightness applied; the global cap
    /// is applied afterwards by the app).
    pub fn frame(&self) -> Frame {
        let mut f = [Rgb::OFF; LED_COUNT];
        for (out, cue) in f.iter_mut().zip(self.latched.iter()) {
            *out = if cue.raw {
                cue.color
            } else {
                cue.color.scale(self.brightness)
            };
        }
        f
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

    #[test]
    fn parses_every_opcode() {
        for i in 0..=3u8 {
            assert_eq!(
                Command::parse([i, 1, 2, 3]),
                Some(Command::Cue {
                    index: i,
                    color: Rgb::new(1, 2, 3),
                    raw: false
                })
            );
            assert_eq!(
                Command::parse([128 + i, 1, 2, 3]),
                Some(Command::Cue {
                    index: i,
                    color: Rgb::new(1, 2, 3),
                    raw: true
                })
            );
        }
        assert_eq!(Command::parse([5, 9, 9, 9]), Some(Command::Clear));
        assert_eq!(Command::parse([6, 9, 9, 9]), Some(Command::Latch));
        assert_eq!(
            Command::parse([7, 200, 9, 9]),
            Some(Command::Brightness(200))
        );
    }

    #[test]
    fn rejects_everything_else() {
        for op in 0..=255u8 {
            let valid = matches!(op, 0..=3 | 5..=7 | 128..=131);
            assert_eq!(Command::parse([op, 0, 0, 0]).is_some(), valid, "op={op}");
        }
    }

    #[test]
    fn cue_is_invisible_until_latched() {
        let mut s = I2cState::new();
        s.apply(Command::Brightness(255));
        s.apply(Command::Cue {
            index: 2,
            color: Rgb::new(10, 20, 30),
            raw: false,
        });
        assert_eq!(s.frame(), [Rgb::OFF; LED_COUNT]);
        s.apply(Command::Latch);
        assert_eq!(s.frame()[2], Rgb::new(10, 20, 30));
    }

    #[test]
    fn clear_affects_cues_not_display() {
        let mut s = I2cState::new();
        s.apply(Command::Brightness(255));
        s.apply(Command::Cue {
            index: 0,
            color: Rgb::WHITE,
            raw: false,
        });
        s.apply(Command::Latch);
        s.apply(Command::Clear);
        assert_eq!(s.frame()[0], Rgb::WHITE, "clear must wait for latch");
        s.apply(Command::Latch);
        assert_eq!(s.frame()[0], Rgb::OFF);
    }

    #[test]
    fn brightness_applies_immediately_except_raw() {
        let mut s = I2cState::new();
        s.apply(Command::Cue {
            index: 0,
            color: Rgb::new(200, 100, 50),
            raw: false,
        });
        s.apply(Command::Cue {
            index: 1,
            color: Rgb::new(200, 100, 50),
            raw: true,
        });
        s.apply(Command::Latch);
        s.apply(Command::Brightness(0));
        assert_eq!(s.frame()[0], Rgb::OFF);
        assert_eq!(s.frame()[1], Rgb::new(200, 100, 50));
        s.apply(Command::Brightness(128));
        assert_eq!(s.frame()[0], Rgb::new(200, 100, 50).scale(128));
    }

    #[test]
    fn i2c_brightness_starts_full() {
        assert_eq!(I2cState::new().brightness, I2C_START_BRIGHTNESS);
    }

    #[test]
    fn hack_man_fifth_led_is_not_a_command() {
        assert_eq!(Command::parse([4, 1, 2, 3]), None);
        assert_eq!(Command::parse([132, 1, 2, 3]), None);
        assert_eq!(ADDRESS, 0x1B);
    }

    #[test]
    fn multi_command_writes_and_partial_tail() {
        let bytes = [0, 1, 2, 3, 99, 0, 0, 0, 6, 0, 0, 0, 7, 1];
        let mut got = std::vec::Vec::new();
        let n = parse_write(&bytes, |c| got.push(c));
        assert_eq!(n, 2);
        assert_eq!(got[1], Command::Latch);
        assert_eq!(parse_write(&[0, 1, 2], |_| panic!()), 0);
    }

    #[test]
    fn reset_keeps_brightness() {
        let mut s = I2cState::new();
        s.apply(Command::Brightness(9));
        s.apply(Command::Cue {
            index: 3,
            color: Rgb::WHITE,
            raw: true,
        });
        s.apply(Command::Latch);
        s.reset_colours();
        assert_eq!(s.brightness, 9);
        assert_eq!(s.frame(), [Rgb::OFF; LED_COUNT]);
    }
}
