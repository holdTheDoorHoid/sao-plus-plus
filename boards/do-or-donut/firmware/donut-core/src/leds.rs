//! The LED map: where each of the 144 LEDs sits and which IS31FL3731
//! register drives it.
//!
//! The table itself ([`LEDS`]) is generated from `hardware/matrix.json` by
//! `gen_led_table.py`; a test below re-reads the JSON and checks every field.
//!
//! **LED numbers.** Everything in this crate (frames, animations, I2C
//! commands) numbers the LEDs 0..=143 in the maker's order: 0..=71 are board
//! references DA1..DA72 (his LED1..LED72), 72..=143 are DB1..DB72 (his
//! LED73..LED144). Only [`to_pwm_registers`] knows about the chip's order.
//!
//! **Matrix convention.** The chip scans its matrix one "row" pin (CAx/CBx)
//! at a time. Figure 8 of the IS31FL3731 datasheet (Rev. D, 2013) draws LED
//! Cx-y with its CATHODE on pin CAx (matrix A) / CBx (matrix B), and its anode
//! on the y-th other pin of the same matrix. That is exactly the `frame`
//! mapping in matrix.json, so [`ROW_IS_CATHODE`] is `true`. The other
//! mapping is kept so a surprise on the first board is a one-line change.

use crate::{Frame, LED_COUNT};

pub use crate::led_table::LEDS;

/// Which pin of an LED the chip's "row" is. `true` = cathode, as drawn in
/// the datasheet's Figure 8 (checked against the PDF, not yet on a board).
pub const ROW_IS_CATHODE: bool = true;

/// One LED. Positions are seen from the FRONT, from the board centre, x to
/// the right and y UP, in micrometres. `angle_deg` is counter-clockwise from
/// 3 o'clock, 0..=359.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Led {
    pub name: &'static str,
    pub x_um: i32,
    pub y_um: i32,
    pub r_um: u32,
    pub angle_deg: u16,
    /// Position in the chip's PWM registers (0..=143, register 0x24 + this)
    /// if the row pin is the cathode (the datasheet's drawing).
    pub index_cathode_row: u8,
    /// The same if the row pin turned out to be the anode.
    pub index_anode_row: u8,
}

impl Led {
    /// Position in the chip's 144 PWM / LED-control slots, with the
    /// convention in force.
    pub const fn chip_index(&self) -> usize {
        if ROW_IS_CATHODE {
            self.index_cathode_row as usize
        } else {
            self.index_anode_row as usize
        }
    }
}

/// Innermost and outermost ring radius (micrometres): 0.55" and 0.90".
pub const R_MIN_UM: u32 = 13_970;
pub const R_MAX_UM: u32 = 22_860;

/// Reorder a frame (LED order) into the chip's PWM register order
/// (register 0x24 + i holds element i).
pub fn to_pwm_registers(frame: &Frame) -> [u8; LED_COUNT] {
    let mut out = [0u8; LED_COUNT];
    for (led, &v) in LEDS.iter().zip(frame.iter()) {
        out[led.chip_index()] = v;
    }
    out
}

/// The 18 LED-control (on/off) register bytes, 0x00..=0x11: a bit is set
/// for every slot that has an LED soldered to it. On this board every slot
/// is used, so this is all 0xFF, but it is computed from the map so a
/// missing LED would be switched off (the datasheet asks for unused
/// positions to be off, or they disturb their neighbours).
pub fn led_control_bytes() -> [u8; 18] {
    let mut out = [0u8; 18];
    for led in LEDS.iter() {
        let i = led.chip_index();
        out[i / 8] |= 1 << (i % 8);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    fn matrix_json() -> serde_json::Value {
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../hardware/matrix.json");
        let text = std::fs::read_to_string(path).expect("read hardware/matrix.json");
        serde_json::from_str(&text).expect("parse matrix.json")
    }

    fn um(v: &serde_json::Value) -> i64 {
        (v.as_f64().unwrap() * 1000.0).round() as i64
    }

    fn hex(v: &serde_json::Value) -> usize {
        usize::from_str_radix(v.as_str().unwrap().trim_start_matches("0x"), 16).unwrap()
    }

    #[test]
    fn led_table_matches_matrix_json() {
        let j = matrix_json();
        let leds = j["leds"].as_array().unwrap();
        assert_eq!(leds.len(), LED_COUNT);
        for (i, (l, t)) in leds.iter().zip(LEDS.iter()).enumerate() {
            assert_eq!(l["ref"].as_str().unwrap(), t.name, "LED {i}");
            assert_eq!(um(&l["x_mm"]), t.x_um as i64, "{} x", t.name);
            assert_eq!(um(&l["y_mm"]), t.y_um as i64, "{} y", t.name);
            assert_eq!(um(&l["r_mm"]), t.r_um as i64, "{} r", t.name);
            let a = l["angle_deg"].as_f64().unwrap().round() as i64;
            assert_eq!(a.rem_euclid(360), t.angle_deg as i64, "{} angle", t.name);
            for (key, idx) in [
                ("frame", t.index_cathode_row),
                ("frame_if_row_is_anode", t.index_anode_row),
            ] {
                let f = &l[key];
                let idx = idx as usize;
                assert_eq!(
                    f["index"].as_u64().unwrap() as usize,
                    idx,
                    "{} {key}",
                    t.name
                );
                // The register facts in the JSON follow from the index, as in
                // the datasheet's Table 7.
                assert_eq!(hex(&f["pwm_reg"]), 0x24 + idx, "{} {key} pwm", t.name);
                assert_eq!(hex(&f["ctrl_reg"]), idx / 8, "{} {key} ctrl", t.name);
                assert_eq!(f["ctrl_bit"].as_u64().unwrap() as usize, idx % 8);
            }
        }
    }

    #[test]
    fn row_pin_in_json_is_the_cathode() {
        // The datasheet convention this firmware uses: `frame.row_pin` is the
        // cathode for every LED.
        let j = matrix_json();
        for l in j["leds"].as_array().unwrap() {
            assert_eq!(l["frame"]["row_pin"], l["cathode"]);
            assert_eq!(l["frame_if_row_is_anode"]["row_pin"], l["anode"]);
        }
    }

    /// Recompute each LED's chip slot from its pins using the datasheet's
    /// Figure 8 / Table 7 rule, independently of extract_matrix.py: LED Cx-y
    /// has its cathode on pin x; its anode is pin y if y < x, else pin y+1.
    /// Slot = 16*(x-1) + (8 if matrix B) + (y-1).
    #[test]
    fn chip_slots_follow_datasheet_figure_8() {
        let j = matrix_json();
        for (l, t) in j["leds"].as_array().unwrap().iter().zip(LEDS.iter()) {
            let pin = |s: &str| s[2..].parse::<usize>().unwrap();
            let (k, a) = (
                pin(l["cathode"].as_str().unwrap()),
                pin(l["anode"].as_str().unwrap()),
            );
            let b = l["matrix"].as_str().unwrap() == "B";
            assert_ne!(k, a);
            let y = if a < k { a } else { a - 1 };
            let slot = 16 * (k - 1) + if b { 8 } else { 0 } + (y - 1);
            assert_eq!(slot, t.index_cathode_row as usize, "{}", t.name);
        }
    }

    #[test]
    fn every_chip_slot_used_exactly_once_in_both_conventions() {
        for f in [|l: &Led| l.index_cathode_row, |l: &Led| l.index_anode_row] {
            let mut seen = [false; LED_COUNT];
            for l in LEDS.iter() {
                let i = f(l) as usize;
                assert!(!seen[i], "slot {i} used twice");
                seen[i] = true;
            }
        }
    }

    #[test]
    fn positions_are_consistent() {
        for l in LEDS.iter() {
            assert!((R_MIN_UM..=R_MAX_UM).contains(&l.r_um), "{}", l.name);
            assert!(l.angle_deg < 360);
            let r = ((l.x_um as f64).powi(2) + (l.y_um as f64).powi(2)).sqrt();
            assert!((r - l.r_um as f64).abs() < 5.0, "{}", l.name);
            let a = (l.y_um as f64)
                .atan2(l.x_um as f64)
                .to_degrees()
                .rem_euclid(360.0);
            let d = (a - l.angle_deg as f64).abs();
            assert!(d.min(360.0 - d) < 0.1, "{} angle {a}", l.name);
        }
        // 8 rings of 18 LEDs.
        let mut radii: Vec<u32> = LEDS.iter().map(|l| l.r_um).collect();
        radii.sort();
        radii.dedup();
        assert_eq!(radii.len(), 8);
    }

    #[test]
    fn register_order_round_trip() {
        let mut f = [0u8; LED_COUNT];
        f[0] = 11; // DA1: cathode CA1, anode CA9 -> C1-8 -> register 0x2B
        f[143] = 22;
        let regs = to_pwm_registers(&f);
        assert_eq!(regs[0x2B - 0x24], 11);
        assert_eq!(regs[LEDS[143].chip_index()], 22);
        assert_eq!(regs.iter().map(|&v| v as u32).sum::<u32>(), 33);
    }

    #[test]
    fn all_leds_enabled() {
        assert_eq!(led_control_bytes(), [0xFF; 18]);
    }
}
