//! The add-on's little memory, laid out exactly like the maker's ATtiny85
//! EEPROM, so a badge reading it byte by byte (his command 0x08) sees what it
//! saw on his board:
//!
//! | address | bytes | what |
//! |---|---|---|
//! | 0x00 | 9 | type, `EGGPLANT`, zero-terminated |
//! | 0x09 | 9 | version, `1.0.0`, zero-terminated |
//! | 0x12 | 9 | options: [0] LED mode, [1] infection bits, [2] lasting infection bits |
//! | 0x1B | 9 | serial number, 8 characters, zero-terminated |
//! | 0x24 | 13 | name, up to 12 characters, zero-terminated |
//! | rest | | 0xFF, free for the badge (his command 0x09) |
//!
//! **This edition keeps it in RAM**: it is lost when the add-on loses power.
//! The maker's board kept it in the ATtiny's EEPROM. Saving it to the
//! XIAO's flash is listed in the firmware README as the next step.

pub const SIZE: usize = 512;
pub const TYPE_AT: usize = 0x00;
pub const VERSION_AT: usize = 0x09;
pub const OPTIONS_AT: usize = 0x12;
pub const SERIAL_AT: usize = 0x1B;
pub const NAME_AT: usize = 0x24;
pub const NAME_MAX: usize = 12;

pub const TYPE: &[u8] = b"EGGPLANT";
/// The version string a badge reads. Kept as the maker's, so badge code that
/// checks it still works; this firmware's own version is in `crate::VERSION_*`.
pub const VERSION: &[u8] = b"1.0.0";

/// Infection bits in options[1] (his "bit 7" and "bit 8", i.e. 0x40 and 0x80).
pub const BUG_A: u8 = 0x40;
pub const BUG_B: u8 = 0x80;
pub const BUGS: u8 = BUG_A | BUG_B;

/// Names a fresh board starts with, one picked by its serial number. These
/// are the maker's own list from his `make-eeprom.pl` (MIT), which gave every
/// board a random one when it was programmed.
pub const NAMES: [&str; 38] = [
    "#EGGPLANT", "Unnamed-EP", "SteveEggplnt", ":eggplant:", "DstryrofEggs", "UnnamedEggie", "Just-An-EP",
    "GULOFAN4196", "PLZ NAME ME", "NOTAROBOT", "NEVERGOINGTO", "LETYOUDOWN", "GIVEYOUUP", "RUNAROUND",
    "ANDDESERTYOU", "MAKEYOUCRY", "SAYGOODBYE", "TELLALIE", "ANDHURTYOU", "MARVWASHERE", "Shi-Te-Addon",
    "TotalyClean", "NotInfected", "Not A Camera", "ChristItsHot", "Gen-er-ic", "WillUBMyFRND", "MKEPsGRTAGIN",
    "SomethinRude", "WinaaarIzU!", "NotRandom", "StimulusPkg", "PurpleThang", "CatchTheWave", "SexyTime",
    "UberEggPlant", "NoNameEggie", "NotAClue",
];

#[derive(Clone)]
pub struct Store {
    pub mem: [u8; SIZE],
}

impl Store {
    /// A fresh memory for one board. `serial` is 8 printable characters
    /// (see [`serial_from`]); the name is picked from [`NAMES`] by it.
    pub fn new(serial: [u8; 8]) -> Self {
        let mut mem = [0xFFu8; SIZE];
        put_str(&mut mem[TYPE_AT..TYPE_AT + 9], TYPE);
        put_str(&mut mem[VERSION_AT..VERSION_AT + 9], VERSION);
        mem[OPTIONS_AT..OPTIONS_AT + 9].fill(0);
        put_str(&mut mem[SERIAL_AT..SERIAL_AT + 9], &serial);
        let pick = serial.iter().fold(0u32, |h, &b| h.wrapping_mul(31).wrapping_add(b as u32)) as usize % NAMES.len();
        put_str(&mut mem[NAME_AT..NAME_AT + 13], NAMES[pick].as_bytes());
        Self { mem }
    }

    pub fn read(&self, addr: usize) -> u8 {
        self.mem[addr % SIZE]
    }

    pub fn write(&mut self, addr: usize, v: u8) {
        self.mem[addr % SIZE] = v;
    }

    pub fn option(&self, i: usize) -> u8 {
        self.mem[OPTIONS_AT + i]
    }

    pub fn set_option(&mut self, i: usize, v: u8) {
        self.mem[OPTIONS_AT + i] = v;
    }

    /// A zero-terminated field, without its terminator.
    pub fn field(&self, at: usize, len: usize) -> &[u8] {
        let f = &self.mem[at..at + len];
        let n = f.iter().position(|&b| b == 0 || b == 0xFF).unwrap_or(len);
        &f[..n]
    }

    pub fn set_name(&mut self, name: &[u8]) {
        put_str(&mut self.mem[NAME_AT..NAME_AT + NAME_MAX + 1], name);
    }
}

fn put_str(dst: &mut [u8], s: &[u8]) {
    dst.fill(0);
    let n = s.len().min(dst.len() - 1);
    dst[..n].copy_from_slice(&s[..n]);
}

/// 8 serial-number characters from any 32-bit seed, in the maker's alphabet
/// (his firmware drew each from `0`-`9` and `A`-`E`).
pub fn serial_from(mut seed: u32) -> [u8; 8] {
    const ALPHA: &[u8; 15] = b"0123456789ABCDE";
    let mut out = [b'0'; 8];
    for c in out.iter_mut() {
        seed = crate::rng::step(seed | 1);
        *c = ALPHA[(seed % 15) as usize];
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout_matches_his_eeprom_map() {
        let s = Store::new(*b"12AB34CD");
        assert_eq!(&s.mem[0..9], b"EGGPLANT\0");
        assert_eq!(&s.mem[9..15], b"1.0.0\0");
        assert_eq!(&s.mem[0x12..0x1B], &[0u8; 9]);
        assert_eq!(&s.mem[0x1B..0x24], b"12AB34CD\0");
        assert!(NAMES.iter().any(|n| s.field(NAME_AT, 13) == n.as_bytes()));
        assert_eq!(s.mem[0x31], 0xFF);
        assert_eq!(s.mem[SIZE - 1], 0xFF);
    }

    #[test]
    fn names_fit_twelve_characters() {
        assert!(NAMES.iter().all(|n| n.len() <= NAME_MAX && n.is_ascii()));
    }

    #[test]
    fn serial_alphabet_and_repeatable() {
        let a = serial_from(0xDEAD_BEEF);
        assert!(a.iter().all(|c| c.is_ascii_digit() || (b'A'..=b'E').contains(c)));
        assert_eq!(a, serial_from(0xDEAD_BEEF));
        assert_ne!(a, serial_from(0x1234_5678));
    }

    #[test]
    fn name_is_cut_at_twelve() {
        let mut s = Store::new(*b"00000000");
        s.set_name(b"ABCDEFGHIJKLMNOP");
        assert_eq!(s.field(NAME_AT, 13), b"ABCDEFGHIJKL");
    }
}
