//! What TARS does: the maker's menu, his piano, his display demos, the click,
//! the cue light, the badge's commands and the power switch.
//!
//! From his `TARS_tone` sketch: an orange menu showing three entries (the one
//! above, the chosen one in a dark frame, the one below), "up" and "down"
//! move with a 1 kHz click, "A" opens the chosen entry. His entries were
//! TV-B-Gone, Tesla-B-Gone, Trolololo, bingo and Piano; only Piano did
//! anything. Here the first four show "COMING SOON" (TV-B-Gone would need an
//! infrared LED, which neither board has), and his three demo sketches are
//! added as entries. Piano: each pad plays a note and fills the screen with a
//! colour while held; ten seconds without a touch goes back to the menu, as
//! his did. On the demo screens any tap goes back to the menu.

use crate::demos;
use crate::gfx::{self, Frame};
use crate::i2c::{self, Command};
use crate::input::{Edges, Pad};
use crate::tone;
use crate::{VERSION_MAJOR, VERSION_MINOR};

pub const MENU: [&str; 8] = ["TV-B-Gone", "Tesla-B-Gone", "Trolololo", "bingo", "Piano", "Hack Planet", "Code Rain", "Scroller"];
const PIANO_ENTRY: usize = 4;
pub const PIANO_TIMEOUT_MS: u32 = 10_000;
pub const MESSAGE_MS: u32 = 1_500;
/// Demo screens are redrawn this often.
pub const DEMO_FRAME_MS: u32 = 50;
/// His piano colours, in his pad order A, up, B, left, down, right.
pub const PIANO_COLOURS: [gfx::Color; 6] = [gfx::RED, gfx::YELLOW, gfx::GREEN, gfx::BLUE, gfx::PURPLE, gfx::WHITE];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Screen {
    Menu,
    Piano,
    HackPlanet,
    CodeRain,
    Scroller,
    ComingSoon,
}

impl Screen {
    pub fn id(self) -> u8 {
        match self {
            Screen::Menu => 0,
            Screen::Piano => 1,
            Screen::HackPlanet => 2,
            Screen::CodeRain => 3,
            Screen::Scroller => 4,
            Screen::ComingSoon => 5,
        }
    }

    fn from_id(id: u8) -> Screen {
        match id {
            1 => Screen::Piano,
            2 => Screen::HackPlanet,
            3 => Screen::CodeRain,
            4 => Screen::Scroller,
            _ => Screen::Menu,
        }
    }

    fn animated(self) -> bool {
        matches!(self, Screen::HackPlanet | Screen::CodeRain | Screen::Scroller)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cue {
    Off,
    On,
    Auto,
}

/// What the hardware should do after a tick.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Out {
    /// Note to play, in Hz; 0 = silent.
    pub tone_hz: u32,
    pub cue_on: bool,
    /// The screen changed: draw it with [`App::render`] and send it.
    pub redraw: bool,
    /// The switch is on OFF: blank everything and sleep.
    pub power_off: bool,
}

pub struct App {
    screen: Screen,
    menu: usize,
    mask: u8,
    entered: u32,
    last_touch: u32,
    click_until: Option<u32>,
    piano_hz: u32,
    badge_note_hz: u32,
    cue: Cue,
    dirty: bool,
    last_frame: u32,
}

impl App {
    pub fn new(now: u32) -> Self {
        Self {
            screen: Screen::Menu,
            menu: 0,
            mask: 0,
            entered: now,
            last_touch: now,
            click_until: None,
            piano_hz: 0,
            badge_note_hz: 0,
            cue: Cue::Auto,
            dirty: true,
            last_frame: now,
        }
    }

    pub fn screen(&self) -> Screen {
        self.screen
    }

    pub fn menu_index(&self) -> usize {
        self.menu
    }

    fn go(&mut self, s: Screen, now: u32) {
        self.screen = s;
        self.entered = now;
        self.last_touch = now;
        self.piano_hz = 0;
        self.dirty = true;
    }

    fn click(&mut self, now: u32) {
        self.click_until = Some(now.wrapping_add(tone::CLICK_MS));
    }

    fn handle(&mut self, e: Edges, now: u32) {
        if e.held != 0 || e.pressed != 0 {
            self.last_touch = now;
        }
        if e.pressed != 0 {
            self.badge_note_hz = 0; // a touch takes over from the badge's note
        }
        match self.screen {
            Screen::Menu => {
                if e.pressed(Pad::Up) {
                    self.menu = (self.menu + MENU.len() - 1) % MENU.len();
                    self.click(now);
                    self.dirty = true;
                } else if e.pressed(Pad::Down) {
                    self.menu = (self.menu + 1) % MENU.len();
                    self.click(now);
                    self.dirty = true;
                } else if e.pressed(Pad::A) {
                    let s = match self.menu {
                        PIANO_ENTRY => Screen::Piano,
                        5 => Screen::HackPlanet,
                        6 => Screen::CodeRain,
                        7 => Screen::Scroller,
                        _ => Screen::ComingSoon,
                    };
                    self.go(s, now);
                }
            }
            Screen::Piano => {
                // as the maker's loop: of the pads held, the last in his order wins
                let mut hz = 0;
                for i in 0..6u8 {
                    if e.held & (1 << i) != 0 {
                        hz = tone::piano_hz(i as usize);
                    }
                }
                if hz != self.piano_hz || e.pressed != 0 || e.released != 0 {
                    self.dirty = true;
                }
                self.piano_hz = hz;
                if e.held == 0 && now.wrapping_sub(self.last_touch) > PIANO_TIMEOUT_MS {
                    self.go(Screen::Menu, now);
                }
            }
            Screen::HackPlanet | Screen::CodeRain | Screen::Scroller => {
                if e.pressed != 0 {
                    self.go(Screen::Menu, now);
                }
            }
            Screen::ComingSoon => {
                if e.pressed != 0 || now.wrapping_sub(self.entered) > MESSAGE_MS {
                    self.go(Screen::Menu, now);
                }
            }
        }
    }

    /// Advance. `mask` is the touch chip's six-bit mask (0 if it did not
    /// answer), `off` is true when the switch is on OFF.
    pub fn tick(&mut self, now: u32, mask: u8, off: bool) -> Out {
        if off {
            return Out { tone_hz: 0, cue_on: false, redraw: false, power_off: true };
        }
        let e = Edges::between(self.mask, mask & 0x3F);
        self.mask = mask & 0x3F;
        self.handle(e, now);
        if self.screen.animated() && now.wrapping_sub(self.last_frame) >= DEMO_FRAME_MS {
            self.dirty = true;
        }
        let mut tone_hz = if self.screen == Screen::Piano { self.piano_hz } else { 0 };
        if let Some(until) = self.click_until {
            if (until.wrapping_sub(now) as i32) > 0 {
                tone_hz = tone::CLICK_HZ;
            } else {
                self.click_until = None;
            }
        }
        if tone_hz == 0 {
            tone_hz = self.badge_note_hz;
        }
        let cue_on = match self.cue {
            Cue::On => true,
            Cue::Off => false,
            Cue::Auto => self.mask != 0,
        };
        let redraw = self.dirty;
        if redraw {
            self.dirty = false;
            self.last_frame = now;
        }
        Out { tone_hz, cue_on, redraw, power_off: false }
    }

    pub fn on_i2c_write(&mut self, bytes: &[u8], now: u32) -> usize {
        let Some((cmds, n)) = i2c::parse(bytes) else { return 0 };
        for c in cmds.iter().take(n).flatten() {
            match *c {
                Command::Screen(id) => self.go(Screen::from_id(id), now),
                Command::Note(0) => self.badge_note_hz = 0,
                Command::Note(m) => self.badge_note_hz = tone::midi_hz(m),
                Command::Cue(0) => self.cue = Cue::Off,
                Command::Cue(1) => self.cue = Cue::On,
                Command::Cue(_) => self.cue = Cue::Auto,
                Command::Tap(p) => {
                    let bit = 1u8 << p;
                    self.handle(Edges { held: bit, pressed: bit, released: 0 }, now);
                    self.handle(Edges { held: 0, pressed: 0, released: bit }, now);
                }
            }
        }
        n
    }

    pub fn status(&self) -> [u8; 4] {
        [VERSION_MAJOR, VERSION_MINOR, self.screen.id(), self.mask]
    }

    pub fn render(&self, f: &mut Frame, now: u32) {
        match self.screen {
            Screen::Menu => draw_menu(f, self.menu),
            Screen::Piano => {
                let mut colour = gfx::BLACK;
                for i in 0..6 {
                    if self.mask & (1 << i) != 0 {
                        colour = PIANO_COLOURS[i];
                    }
                }
                f.fill(colour);
                if colour == gfx::BLACK {
                    f.text(56, 36, "PIANO", 1, gfx::GOOD_ORANGE);
                }
            }
            Screen::HackPlanet => demos::hack_the_planet(f, now.wrapping_sub(self.entered)),
            Screen::CodeRain => demos::code_rain(f, now.wrapping_sub(self.entered)),
            Screen::Scroller => demos::scroller(f, now.wrapping_sub(self.entered)),
            Screen::ComingSoon => {
                f.fill(gfx::BORDER_ORANGE);
                f.text(80 - crate::font::text_width("COMING SOON", 2) / 2, 32, "COMING SOON", 2, gfx::BLACK);
            }
        }
    }
}

/// The maker's menu layout: an orange card, three rows, the middle one framed.
pub fn draw_menu(f: &mut Frame, sel: usize) {
    let (ox, oy) = (16, 8);
    f.fill(gfx::BORDER_ORANGE);
    f.fill_rect(ox, oy, 128, 64, gfx::GOOD_ORANGE);
    f.fill_round_rect(ox, oy + 22, 128 - 4, 22, 3, gfx::BLACK);
    f.fill_round_rect(ox + 1, oy + 23, 128 - 8, 22 - 4, 2, gfx::GOOD_ORANGE);
    for k in 0..3 {
        f.fill_round_rect(ox + 2, oy + 2 + 22 * k, 16, 16, 2, gfx::BLACK);
    }
    let n = MENU.len();
    for (k, idx) in [(sel + n - 1) % n, sel, (sel + 1) % n].iter().enumerate() {
        f.text(ox + 23, oy + 7 + 22 * k as i32, MENU[*idx], 1, gfx::BLACK);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tap(app: &mut App, t: &mut u32, p: Pad) -> Out {
        *t += 20;
        let o = app.tick(*t, p.bit(), false);
        *t += 20;
        app.tick(*t, 0, false);
        o
    }

    #[test]
    fn menu_moves_with_a_click_and_wraps() {
        let mut t = 0;
        let mut app = App::new(t);
        assert!(app.tick(t, 0, false).redraw);
        let o = tap(&mut app, &mut t, Pad::Up);
        assert_eq!(app.menu_index(), MENU.len() - 1);
        assert!(o.redraw);
        assert_eq!(o.tone_hz, tone::CLICK_HZ);
        t += 20;
        assert_eq!(app.tick(t, 0, false).tone_hz, 0); // the click is short
        tap(&mut app, &mut t, Pad::Down);
        assert_eq!(app.menu_index(), 0);
    }

    #[test]
    fn piano_plays_and_times_out() {
        let mut t = 0;
        let mut app = App::new(t);
        for _ in 0..PIANO_ENTRY {
            tap(&mut app, &mut t, Pad::Down);
        }
        tap(&mut app, &mut t, Pad::A);
        assert_eq!(app.screen(), Screen::Piano);
        t += 20;
        let o = app.tick(t, Pad::Down.bit(), false);
        assert_eq!(o.tone_hz, tone::piano_hz(4));
        assert!(o.redraw);
        t += 20;
        assert_eq!(app.tick(t, 0, false).tone_hz, 0);
        t += PIANO_TIMEOUT_MS + 100;
        app.tick(t, 0, false);
        assert_eq!(app.screen(), Screen::Menu);
    }

    #[test]
    fn placeholders_say_coming_soon_then_return() {
        let mut t = 0;
        let mut app = App::new(t);
        tap(&mut app, &mut t, Pad::A);
        assert_eq!(app.screen(), Screen::ComingSoon);
        t += MESSAGE_MS + 50;
        app.tick(t, 0, false);
        assert_eq!(app.screen(), Screen::Menu);
    }

    #[test]
    fn demos_redraw_and_any_tap_leaves() {
        let mut t = 0;
        let mut app = App::new(t);
        app.on_i2c_write(&[0xE5, 1, 3, 0x5E], t);
        assert_eq!(app.screen(), Screen::CodeRain);
        t += DEMO_FRAME_MS;
        assert!(app.tick(t, 0, false).redraw);
        t += 10;
        assert!(!app.tick(t, 0, false).redraw);
        tap(&mut app, &mut t, Pad::B);
        assert_eq!(app.screen(), Screen::Menu);
    }

    #[test]
    fn badge_note_cue_and_status() {
        let mut t = 0;
        let mut app = App::new(t);
        app.on_i2c_write(&[0xE5, 2, 69, 0x5E], t);
        t += 20;
        assert_eq!(app.tick(t, 0, false).tone_hz, 440);
        app.on_i2c_write(&[0xE5, 2, 0, 0x5E, 0xE5, 3, 1, 0x5E], t);
        t += 20;
        let o = app.tick(t, 0, false);
        assert_eq!(o.tone_hz, 0);
        assert!(o.cue_on);
        app.on_i2c_write(&[0xE5, 3, 2, 0x5E], t);
        t += 20;
        let o = app.tick(t, Pad::Left.bit(), false);
        assert!(o.cue_on); // automatic: lit while touched
        assert_eq!(app.status(), [VERSION_MAJOR, VERSION_MINOR, 0, Pad::Left.bit()]);
    }

    #[test]
    fn badge_tap_moves_the_menu() {
        let mut app = App::new(0);
        app.on_i2c_write(&[0xE5, 4, 4, 0x5E], 0);
        assert_eq!(app.menu_index(), 1);
    }

    #[test]
    fn off_switch_powers_off_silently() {
        let mut app = App::new(0);
        app.on_i2c_write(&[0xE5, 2, 69, 0x5E], 0);
        let o = app.tick(10, 0, true);
        assert!(o.power_off && o.tone_hz == 0 && !o.cue_on);
    }

    #[test]
    fn menu_drawing_frames_the_middle_row() {
        let mut f = Frame::new();
        draw_menu(&mut f, 2);
        assert_eq!(f.get(0, 0), gfx::BORDER_ORANGE);
        assert_eq!(f.get(16 + 60, 8 + 22), gfx::BLACK); // the frame's top edge
        assert!(f.count(gfx::BLACK) > 500);
    }

    #[test]
    fn every_screen_renders() {
        let mut f = Frame::new();
        let mut app = App::new(0);
        for id in 0..5 {
            app.on_i2c_write(&[0xE5, 1, id, 0x5E], 0);
            app.render(&mut f, 1234);
        }
        app.go(Screen::ComingSoon, 0);
        app.render(&mut f, 10);
        assert!(f.count(gfx::BLACK) > 0);
    }
}
