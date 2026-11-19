//! A whole-screen picture in memory (160 x 80 pixels, 16-bit colour) and the
//! few drawing operations the screens need.
//!
//! The XIAO has plenty of RAM for one 25.6 kB frame, so every screen is drawn
//! here first and then sent to the display in one go: no flicker, and the
//! drawing is testable on the host.

use crate::font;

pub const WIDTH: i32 = 160;
pub const HEIGHT: i32 = 80;
pub const PIXELS: usize = (WIDTH * HEIGHT) as usize;

/// 16-bit RGB565 colour, as the ST7735S takes it.
pub type Color = u16;

pub const fn rgb(r: u8, g: u8, b: u8) -> Color {
    ((r as u16 & 0xF8) << 8) | ((g as u16 & 0xFC) << 3) | (b as u16 >> 3)
}

pub const BLACK: Color = 0x0000;
pub const WHITE: Color = 0xFFFF;
pub const RED: Color = rgb(255, 0, 0);
pub const GREEN: Color = rgb(0, 255, 0);
pub const BLUE: Color = rgb(0, 0, 255);
pub const YELLOW: Color = rgb(255, 255, 0);
pub const PURPLE: Color = rgb(128, 0, 128);
/// The maker's menu colours (his `good_orange` #ff8200 and `border_orange` #ff9700).
pub const GOOD_ORANGE: Color = rgb(255, 130, 0);
pub const BORDER_ORANGE: Color = rgb(255, 151, 0);
/// His "hack the planet" phone-screen colours.
pub const LIME: Color = rgb(168, 168, 44);
pub const CHAR_COL: Color = rgb(60, 65, 44);

pub struct Frame {
    px: [Color; PIXELS],
}

impl Default for Frame {
    fn default() -> Self {
        Self::new()
    }
}

impl Frame {
    pub const fn new() -> Self {
        Self { px: [BLACK; PIXELS] }
    }

    pub fn get(&self, x: i32, y: i32) -> Color {
        if (0..WIDTH).contains(&x) && (0..HEIGHT).contains(&y) {
            self.px[(y * WIDTH + x) as usize]
        } else {
            BLACK
        }
    }

    pub fn set(&mut self, x: i32, y: i32, c: Color) {
        if (0..WIDTH).contains(&x) && (0..HEIGHT).contains(&y) {
            self.px[(y * WIDTH + x) as usize] = c;
        }
    }

    pub fn fill(&mut self, c: Color) {
        self.px.fill(c);
    }

    /// Filled rectangle, clipped to the screen.
    pub fn fill_rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: Color) {
        let (x0, y0) = (x.max(0), y.max(0));
        let (x1, y1) = ((x + w).min(WIDTH), (y + h).min(HEIGHT));
        for yy in y0..y1 {
            let row = (yy * WIDTH) as usize;
            self.px[row + x0 as usize..row + x1.max(x0) as usize].fill(c);
        }
    }

    pub fn hline(&mut self, x: i32, y: i32, w: i32, c: Color) {
        self.fill_rect(x, y, w, 1, c);
    }

    /// Rectangle outline one pixel wide.
    pub fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, c: Color) {
        self.fill_rect(x, y, w, 1, c);
        self.fill_rect(x, y + h - 1, w, 1, c);
        self.fill_rect(x, y, 1, h, c);
        self.fill_rect(x + w - 1, y, 1, h, c);
    }

    /// Filled rectangle with rounded corners of radius `r`.
    pub fn fill_round_rect(&mut self, x: i32, y: i32, w: i32, h: i32, r: i32, c: Color) {
        let r = r.min(w / 2).min(h / 2).max(0);
        for yy in 0..h {
            // rows inside a corner start further in, following a quarter circle
            let dy = if yy < r {
                r - yy
            } else if yy >= h - r {
                yy - (h - r - 1)
            } else {
                0
            };
            let inset = if dy == 0 { 0 } else { r - isqrt(r * r - dy * dy) };
            self.hline(x + inset, y + yy, w - 2 * inset, c);
        }
    }

    /// Draw `text` with its top-left corner at (x, y). Only set pixels are
    /// drawn (transparent background). Returns the x after the last cell.
    pub fn text(&mut self, x: i32, y: i32, text: &str, scale: i32, c: Color) -> i32 {
        let mut cx = x;
        for ch in text.chars() {
            for gy in 0..font::GLYPH_H {
                for gx in 0..font::GLYPH_W {
                    if font::pixel(ch, gx, gy) {
                        self.fill_rect(cx + gx * scale, y + gy * scale, scale, scale, c);
                    }
                }
            }
            cx += font::CELL_W * scale;
        }
        cx
    }

    /// The frame as the display wants it: two bytes per pixel, high byte first,
    /// row by row. Calls `out` with chunks of up to `buf.len()` bytes.
    pub fn for_each_chunk(&self, buf: &mut [u8], mut out: impl FnMut(&[u8])) {
        let per = buf.len() / 2;
        assert!(per > 0);
        for chunk in self.px.chunks(per) {
            for (i, p) in chunk.iter().enumerate() {
                buf[2 * i] = (p >> 8) as u8;
                buf[2 * i + 1] = *p as u8;
            }
            out(&buf[..chunk.len() * 2]);
        }
    }

    pub fn count(&self, c: Color) -> usize {
        self.px.iter().filter(|p| **p == c).count()
    }
}

fn isqrt(v: i32) -> i32 {
    if v <= 0 {
        return 0;
    }
    let mut r = 0;
    while (r + 1) * (r + 1) <= v {
        r += 1;
    }
    r
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    #[test]
    fn colours() {
        assert_eq!(rgb(255, 255, 255), 0xFFFF);
        assert_eq!(rgb(255, 0, 0), 0xF800);
        assert_eq!(rgb(0, 255, 0), 0x07E0);
        assert_eq!(rgb(0, 0, 255), 0x001F);
    }

    #[test]
    fn rect_is_clipped() {
        let mut f = Frame::new();
        f.fill_rect(-10, -10, 20, 20, WHITE);
        assert_eq!(f.count(WHITE), 100);
        f.fill_rect(150, 70, 100, 100, RED);
        assert_eq!(f.count(RED), 100);
        f.fill_rect(10, 10, -5, 4, BLUE);
        assert_eq!(f.count(BLUE), 0);
    }

    #[test]
    fn outline_has_no_inside() {
        let mut f = Frame::new();
        f.rect(10, 10, 6, 6, WHITE);
        assert_eq!(f.count(WHITE), 20);
        assert_eq!(f.get(12, 12), BLACK);
    }

    #[test]
    fn round_rect_cuts_its_corners_only() {
        let mut f = Frame::new();
        f.fill_round_rect(0, 0, 20, 10, 3, WHITE);
        assert_eq!(f.get(0, 0), BLACK);
        assert_eq!(f.get(19, 9), BLACK);
        assert_eq!(f.get(10, 0), WHITE);
        assert_eq!(f.get(0, 5), WHITE);
        let mut g = Frame::new();
        g.fill_round_rect(0, 0, 20, 10, 0, WHITE);
        assert_eq!(g.count(WHITE), 200);
    }

    #[test]
    fn text_draws_and_advances() {
        let mut f = Frame::new();
        let end = f.text(0, 0, "TA", 1, WHITE);
        assert_eq!(end, 12);
        assert!(f.get(0, 0) == WHITE && f.get(4, 0) == WHITE); // T's bar
        let mut g = Frame::new();
        g.text(0, 0, "T", 2, WHITE);
        assert_eq!(g.count(WHITE), 4 * (5 + 6));
    }

    #[test]
    fn chunks_cover_the_frame_high_byte_first() {
        let mut f = Frame::new();
        f.set(0, 0, 0x1234);
        let mut buf = [0u8; 1000];
        let mut all = Vec::new();
        f.for_each_chunk(&mut buf, |c| all.extend_from_slice(c));
        assert_eq!(all.len(), PIXELS * 2);
        assert_eq!(&all[..2], &[0x12, 0x34]);
    }
}
