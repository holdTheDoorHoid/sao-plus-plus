//! What the ST7735S display controller has to be told, as plain bytes.
//!
//! The display is the maker's 0.96 in 80 x 160 IPS panel, used sideways
//! (160 wide, 80 tall) as in his sketches (`setRotation(1)`). His sketches
//! used the TFT_eSPI library set up for this panel; the start-up sequence
//! below is the ST7735S's own minimum (reset, wake, 16-bit colour, turn,
//! colour inversion for IPS, on), not a copy of that library.
//!
//! On this board the display's chip-select is tied to ground (there were not
//! enough XIAO pins), so the display listens to every byte on its two wires.
//! Nothing else shares them, so that is safe.
//!
//! Two things only a real panel can settle (see the firmware README):
//! * where the 80 x 160 visible area sits inside the controller's 132 x 162
//!   memory: [`X_OFFSET`] / [`Y_OFFSET`] (1 and 26 for the common panels);
//! * the colour order (BGR on the common panels: [`MADCTL`] bit 3).

pub const SWRESET: u8 = 0x01;
pub const SLPOUT: u8 = 0x11;
pub const NORON: u8 = 0x13;
pub const INVON: u8 = 0x21;
pub const DISPON: u8 = 0x29;
pub const CASET: u8 = 0x2A;
pub const RASET: u8 = 0x2B;
pub const RAMWR: u8 = 0x2C;
pub const MADCTL_REG: u8 = 0x36;
pub const COLMOD: u8 = 0x3A;

/// Memory access control: MY | MV (sideways, as the maker's rotation 1) | BGR.
pub const MADCTL: u8 = 0x80 | 0x20 | 0x08;
/// 16 bits per pixel (RGB565).
pub const COLMOD_16BIT: u8 = 0x05;
pub const X_OFFSET: u16 = 1;
pub const Y_OFFSET: u16 = 26;

/// One step of the start-up sequence: command, its data, then a pause.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Step {
    pub cmd: u8,
    pub data: &'static [u8],
    pub wait_ms: u32,
}

pub const INIT: &[Step] = &[
    Step { cmd: SWRESET, data: &[], wait_ms: 150 },
    Step { cmd: SLPOUT, data: &[], wait_ms: 120 },
    Step { cmd: COLMOD, data: &[COLMOD_16BIT], wait_ms: 10 },
    Step { cmd: MADCTL_REG, data: &[MADCTL], wait_ms: 0 },
    Step { cmd: INVON, data: &[], wait_ms: 0 },
    Step { cmd: NORON, data: &[], wait_ms: 10 },
    Step { cmd: DISPON, data: &[], wait_ms: 100 },
];

/// The column / row address commands that select a window (inclusive
/// corners, in screen pixels) for the next [`RAMWR`].
pub fn window(x0: u16, y0: u16, x1: u16, y1: u16) -> [(u8, [u8; 4]); 2] {
    let (a, b) = (x0 + X_OFFSET, x1 + X_OFFSET);
    let (c, d) = (y0 + Y_OFFSET, y1 + Y_OFFSET);
    [
        (CASET, [(a >> 8) as u8, a as u8, (b >> 8) as u8, b as u8]),
        (RASET, [(c >> 8) as u8, c as u8, (d >> 8) as u8, d as u8]),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gfx::{HEIGHT, WIDTH};

    #[test]
    fn starts_with_reset_and_ends_with_display_on() {
        assert_eq!(INIT.first().unwrap().cmd, SWRESET);
        assert_eq!(INIT.last().unwrap().cmd, DISPON);
        // the controller needs 120 ms after waking before more commands
        let wake = INIT.iter().find(|s| s.cmd == SLPOUT).unwrap();
        assert!(wake.wait_ms >= 120);
    }

    #[test]
    fn whole_screen_window_fits_the_controller_memory() {
        let [(c1, cols), (c2, rows)] = window(0, 0, WIDTH as u16 - 1, HEIGHT as u16 - 1);
        assert_eq!((c1, c2), (CASET, RASET));
        let x_end = u16::from_be_bytes([cols[2], cols[3]]);
        let y_end = u16::from_be_bytes([rows[2], rows[3]]);
        // sideways: columns run along the controller's 162, rows along its 132
        assert!(x_end < 162 && y_end < 132);
        assert_eq!(u16::from_be_bytes([cols[0], cols[1]]), X_OFFSET);
        assert_eq!(u16::from_be_bytes([rows[0], rows[1]]), Y_OFFSET);
    }

    #[test]
    fn sideways_and_sixteen_bit() {
        assert_ne!(MADCTL & 0x20, 0);
        assert_eq!(COLMOD_16BIT, 0x05);
    }
}
