//! The maker's stand-alone display sketches, as screens of the menu.
//!
//! Each is drawn fresh from the time alone (no stored state), so the app can
//! switch between them freely and the tests can check any moment.
//! * [`hack_the_planet`]: his `hack_the_planet` sketch, an old phone screen
//!   (signal, "N", battery boxes) saying GRAND CENTRAL / HACK / THE PLANET,
//!   the last line blinking once a second. His sketch shows "vodafone" as the
//!   network name; that is a company's trademark, so this shows "TARSNET".
//! * [`code_rain`]: his `TARS_chatGPT_free` sketch, two halves of random
//!   green and white dashes drifting up and down.
//! * [`scroller`]: his `TARS` sketch, two lines of "typed" text built from
//!   2 x 2 pixel blocks, one half rising, one falling.

use crate::gfx::{self, Frame, BLACK, CHAR_COL, GREEN, LIME, WHITE};

fn hash(mut x: u32) -> u32 {
    x ^= x >> 16;
    x = x.wrapping_mul(0x7feb_352d);
    x ^= x >> 15;
    x = x.wrapping_mul(0x846c_a68b);
    x ^ (x >> 16)
}

pub fn hack_the_planet(f: &mut Frame, t_ms: u32) {
    f.fill(LIME);
    f.text(2, 2, "TARSNET", 1, CHAR_COL);
    // the aerial
    f.fill_rect(96, 2, 6, 2, CHAR_COL);
    f.fill_rect(97, 4, 4, 2, CHAR_COL);
    f.fill_rect(98, 6, 2, 4, CHAR_COL);
    f.text(108, 2, "N", 1, CHAR_COL);
    for i in 0..4 {
        f.rect(152 - 8 * i, 2, 6, 6, CHAR_COL);
        f.rect(153 - 8 * i, 3, 4, 4, CHAR_COL);
    }
    f.text(2, 24, "GRAND CENTRAL", 2, CHAR_COL);
    f.text(56, 40, "HACK", 2, CHAR_COL);
    if (t_ms / 1000) % 2 == 0 {
        f.text(20, 56, "THE PLANET", 2, CHAR_COL);
    }
}

pub fn code_rain(f: &mut Frame, t_ms: u32) {
    f.fill(BLACK);
    let left = (t_ms / 200 * 2) % 80;
    let right = 80 - (t_ms / 300 * 2) % 80;
    for (x0, scroll, colour, salt) in [(0, left, GREEN, 0u32), (80, right, WHITE, 7919u32)] {
        for j in 0..40u32 {
            let y = ((2 * (j + scroll)) % 80) as i32;
            let mut x = 0i32;
            for k in 0..8u32 {
                // the same row always gets the same "words", so it scrolls rather than flickers
                let len = (hash(salt + j * 31 + k + scroll / 80 * 1013) % 8) as i32;
                if len > 0 && x < 80 {
                    f.hline(x0 + x, y, len.min(80 - x), colour);
                }
                x += 1 + len;
            }
        }
        f.hline(x0, scroll as i32 % 80, 80, BLACK);
    }
}

const UP_TEXT: &str = "Scrolling up! ";
const DOWN_TEXT: &str = "Scrolling down! ";

/// One "typed" character: a 3 x 4 checker of 2 x 2 blocks (as his sketch drew).
fn block_char(f: &mut Frame, x: i32, y: i32) {
    for row in 0..4 {
        for col in 0..3 {
            if (row + col) % 2 == 0 {
                f.fill_rect(x + col * 2, y + row * 2, 2, 2, GREEN);
            }
        }
    }
}

fn typed(f: &mut Frame, text: &str, n: usize, x: i32, y: i32) {
    for (i, c) in text.chars().take(n).enumerate() {
        if c != ' ' {
            block_char(f, x + i as i32 * 6, y);
        }
    }
}

pub fn scroller(f: &mut Frame, t_ms: u32) {
    f.fill(BLACK);
    // left half: one step every 150 ms, 2 pixels up per step, one more letter per pass
    let s = t_ms / 150;
    let pos = (s * 2 % 80) as i32;
    let n = (s * 2 / 80) as usize % UP_TEXT.len() + 1;
    typed(f, UP_TEXT, n, 5, 80 - pos);
    // right half: every 200 ms, downwards
    let s = t_ms / 200;
    let pos = (s * 2 % 80) as i32;
    let n = (s * 2 / 80) as usize % DOWN_TEXT.len() + 1;
    typed(f, DOWN_TEXT, n, 90, pos - 80 + 72);
    let _ = gfx::WIDTH;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hack_the_planet_blinks_its_last_line() {
        let mut a = Frame::new();
        let mut b = Frame::new();
        hack_the_planet(&mut a, 500);
        hack_the_planet(&mut b, 1500);
        assert!(a.count(CHAR_COL) > b.count(CHAR_COL));
        assert_eq!(a.get(0, 79), LIME);
    }

    #[test]
    fn code_rain_has_both_colours_in_their_halves_and_moves() {
        let mut a = Frame::new();
        code_rain(&mut a, 0);
        let mut green_right = 0;
        let mut white_left = 0;
        for y in 0..80 {
            for x in 0..80 {
                white_left += (a.get(x, y) == WHITE) as u32;
                green_right += (a.get(x + 80, y) == GREEN) as u32;
            }
        }
        assert_eq!((white_left, green_right), (0, 0));
        assert!(a.count(GREEN) > 100 && a.count(WHITE) > 100);
        let mut b = Frame::new();
        code_rain(&mut b, 1000);
        assert!((0..80).any(|y| (0..160).any(|x| a.get(x, y) != b.get(x, y))));
    }

    #[test]
    fn scroller_types_more_over_time() {
        let mut a = Frame::new();
        scroller(&mut a, 150 * 30);
        assert!(a.count(GREEN) > 0);
        let mut b = Frame::new();
        scroller(&mut b, 150 * 40 * 3 + 150 * 30);
        assert!(b.count(GREEN) >= a.count(GREEN));
    }
}
