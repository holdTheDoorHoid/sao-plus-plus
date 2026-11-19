//! Lighting the duck like an addressable (WS2812 / "NeoPixel") LED: the badge
//! sends WS2812 data on SAO GPIO2 and the add-on behaves like the LAST LEDs of
//! the chain, as on the maker's board:
//!
//! - the last colour sent (green, red, blue: WS2812 order) sets the duck LED;
//! - the blue byte of the colour before it sets the background channel
//!   (Duck Jaws' red LEDs). So a badge drives a duck as a 2-LED strip:
//!   LED 0 = (anything, anything, background), LED 1 = the duck's colour.
//!
//! Timing, also as on the maker's board (looser than the WS2812 datasheet, so
//! slow or sloppy badges still work): a high pulse shorter than 0.5 us is a 0,
//! up to 2 us is a 1, anything longer is not WS2812 and the frame is dropped.
//! Low for 6 us or more ends the frame and the colours are shown.
//!
//! The firmware measures the pulses (with the chip's RMT receiver) and hands
//! them over as (high ns, low ns) pairs.

/// High pulses shorter than this are a 0 bit.
pub const ZERO_MAX_NS: u32 = 500;
/// High pulses shorter than this (and at least ZERO_MAX_NS) are a 1 bit.
pub const ONE_MAX_NS: u32 = 2000;
/// A low time at least this long ends the frame.
pub const LATCH_NS: u32 = 6000;

/// Colours to show after a frame: duck red, green, blue and background, each
/// 0..=255.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Latch {
    pub rgb: [u8; 3],
    pub background: u8,
}

/// True if a high pulse of this length looks like WS2812 data (used to switch
/// to WS2812 mode automatically, as the maker's board does).
pub fn looks_like_ws2812(high_ns: u32) -> bool {
    high_ns > 0 && high_ns < ONE_MAX_NS
}

/// Decode one frame. `pulses` are (high ns, low ns) in order; the frame ends
/// at the first low time of LATCH_NS or more, or at the end of the slice (the
/// receiver stops on a long idle, which is the latch). Returns None if any
/// pulse is too long to be WS2812 or there was nothing to decode.
pub fn decode(pulses: &[(u32, u32)]) -> Option<Latch> {
    let mut bits: u32 = 0;
    let mut n = 0usize;
    for &(high, low) in pulses {
        if high == 0 {
            break;
        }
        let bit = if high < ZERO_MAX_NS {
            0
        } else if high < ONE_MAX_NS {
            1
        } else {
            return None;
        };
        bits = (bits << 1) | bit;
        n += 1;
        if low >= LATCH_NS {
            break;
        }
    }
    if n == 0 {
        return None;
    }
    Some(Latch {
        rgb: [(bits >> 8) as u8, (bits >> 16) as u8, bits as u8],
        background: (bits >> 24) as u8,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    /// Encode bytes as a WS2812 stream with typical timing (0: 350/800, 1: 700/600).
    fn encode(bytes: &[u8]) -> Vec<(u32, u32)> {
        let mut v = Vec::new();
        for &b in bytes {
            for i in (0..8).rev() {
                v.push(if b >> i & 1 == 1 { (700, 600) } else { (350, 800) });
            }
        }
        if let Some(last) = v.last_mut() {
            last.1 = 50_000;
        }
        v
    }

    #[test]
    fn single_led() {
        // one colour: G=0x11, R=0x22, B=0x33; nothing before it
        let l = decode(&encode(&[0x11, 0x22, 0x33])).unwrap();
        assert_eq!(l.rgb, [0x22, 0x11, 0x33]);
        assert_eq!(l.background, 0);
    }

    #[test]
    fn two_leds_background_is_first_blue() {
        let l = decode(&encode(&[0x01, 0x02, 0xAB, 0x40, 0x50, 0x60])).unwrap();
        assert_eq!(l.rgb, [0x50, 0x40, 0x60]);
        assert_eq!(l.background, 0xAB);
    }

    #[test]
    fn long_chain_keeps_the_last() {
        let mut bytes = std::vec![0xEEu8; 30];
        bytes.extend_from_slice(&[9, 9, 0x77, 1, 2, 3]);
        let l = decode(&encode(&bytes)).unwrap();
        assert_eq!((l.rgb, l.background), ([2, 1, 3], 0x77));
    }

    #[test]
    fn sloppy_timing_still_works() {
        // 0.45 us zeros and 1.9 us ones are accepted, as on the maker's board
        let mut v = Vec::new();
        for i in 0..24 {
            v.push(if i % 2 == 0 { (450, 900) } else { (1900, 400) });
        }
        let l = decode(&v).unwrap();
        assert_eq!(l.rgb, [0x55, 0x55, 0x55]);
    }

    #[test]
    fn too_long_pulse_drops_the_frame() {
        let mut v = encode(&[1, 2, 3]);
        v[5].0 = 2500;
        assert_eq!(decode(&v), None);
    }

    #[test]
    fn latch_ends_the_frame() {
        let mut v = encode(&[0, 0, 0xFF]);
        v[23].1 = 7000;
        v.extend(encode(&[0xFF, 0xFF, 0xFF]));
        let l = decode(&v).unwrap();
        assert_eq!(l.rgb, [0, 0, 0xFF]);
    }

    #[test]
    fn detection() {
        assert!(looks_like_ws2812(350));
        assert!(looks_like_ws2812(1999));
        assert!(!looks_like_ws2812(0));
        assert!(!looks_like_ws2812(2000));
        assert_eq!(decode(&[]), None);
    }
}
