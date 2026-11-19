//! Power-on presets: the settings registers (0xEC..=0xFC) kept in flash when
//! the badge writes 42 to the save register, as on the maker's board.
//!
//! Stored as 24 bytes: "duck", a format number, the 17 settings bytes, a
//! checksum and one spare byte. Anything that does not check out is ignored
//! and the factory settings are used. (The layout is this firmware's own; it
//! does not need to match the maker's, which lived in his chip's flash.)

use crate::regs::SETTINGS_LEN;

pub const MAGIC: [u8; 4] = *b"duck";
pub const FORMAT: u8 = 1;
pub const BLOB_LEN: usize = 24;

fn checksum(bytes: &[u8]) -> u8 {
    // a simple running sum with a twist, enough to reject erased (0xFF) or
    // half-written flash
    bytes.iter().fold(0x5Au8, |acc, &b| acc.rotate_left(1) ^ b)
}

pub fn encode(settings: &[u8; SETTINGS_LEN]) -> [u8; BLOB_LEN] {
    let mut out = [0u8; BLOB_LEN];
    out[..4].copy_from_slice(&MAGIC);
    out[4] = FORMAT;
    out[5..5 + SETTINGS_LEN].copy_from_slice(settings);
    out[5 + SETTINGS_LEN] = checksum(&out[..5 + SETTINGS_LEN]);
    out
}

pub fn decode(blob: &[u8]) -> Option<[u8; SETTINGS_LEN]> {
    if blob.len() < BLOB_LEN || blob[..4] != MAGIC || blob[4] != FORMAT {
        return None;
    }
    if checksum(&blob[..5 + SETTINGS_LEN]) != blob[5 + SETTINGS_LEN] {
        return None;
    }
    let mut s = [0u8; SETTINGS_LEN];
    s.copy_from_slice(&blob[5..5 + SETTINGS_LEN]);
    Some(s)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let s: [u8; SETTINGS_LEN] = core::array::from_fn(|i| (i * 13) as u8);
        assert_eq!(decode(&encode(&s)), Some(s));
    }

    #[test]
    fn rejects_erased_and_damaged() {
        assert_eq!(decode(&[0xFF; BLOB_LEN]), None);
        assert_eq!(decode(&[0; BLOB_LEN]), None);
        let s = [7u8; SETTINGS_LEN];
        let mut b = encode(&s);
        b[9] ^= 1;
        assert_eq!(decode(&b), None);
        let mut b = encode(&s);
        b[4] = FORMAT + 1;
        assert_eq!(decode(&b), None);
        assert_eq!(decode(&encode(&s)[..10]), None);
    }
}
