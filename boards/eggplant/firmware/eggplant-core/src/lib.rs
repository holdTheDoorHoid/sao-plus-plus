//! Behaviour of the Eggplant SAO (SAO++ edition), with no hardware code.
//!
//! This is a Rust re-implementation of the maker's Arduino sketch for the
//! ATtiny85 (`original/firmware/eggplant.ino`, "Designed by Krux - 2018",
//! MIT licence, from github.com/thedarknet/dc26-badge). The fade tables, the
//! I2C answers and the "infection" game follow that sketch line by line;
//! where this file departs from it, the comment says so.
//!
//! What is different on purpose:
//! * The maker's board had five red/blue LEDs driven as two groups. Here five
//!   RGB LEDs all show the same red + blue mix, so "red" and "blue" below are
//!   the two colour channels of every LED.
//! * The ATtiny kept its name, serial number, light mode and infection in
//!   EEPROM. Here that memory is a 512-byte array in RAM: it answers the same
//!   I2C reads and writes, but it is forgotten when power is removed.
//! * The BOOT button steps through the six light modes (the maker's board had
//!   no button; only a badge could change the mode).
//!
//! NEVER COMPILED: no Rust toolchain was available on the machine this was
//! written on. Treat every line as unchecked until `cargo test` has run.

#![cfg_attr(not(test), no_std)]

/// 7-bit I2C address: "0x36 - i.e. EGplant, or the best you can do in 7 bits".
pub const ADDRESS: u8 = 0x36;
pub const LED_COUNT: usize = 5;
pub const VERSION_MAJOR: u8 = 0;
pub const VERSION_MINOR: u8 = 1;

/// Full-scale level of each colour channel, 0..=255. The LEDs run from 3.3 V
/// and five of them at full red + blue would ask for about 50 mA, the whole
/// SAO budget, so the fades top out at roughly a quarter of that.
pub const MAX_LEVEL: u8 = 64;

/// How many maker "loops" run per 10 ms frame. The ATtiny's loop time was
/// never measured; 1 gives a blue breath of about 2.5 s. Tune on a real board.
pub const STEPS_PER_FRAME: u8 = 1;

/// The I2C register window (TinyWireS buffer size in the sketch).
pub const REG_COUNT: usize = 16;
pub const MEM_SIZE: usize = 512;

// Layout of the maker's EEPROM (eggplant_i2c_api.txt).
const MEM_TYPE: usize = 0;
const MEM_VERSION: usize = 9;
const MEM_OPTIONS: usize = 18;
const MEM_SERIAL: usize = 27;
const MEM_NAME: usize = 36;
const NAME_LEN: usize = 12;

const TYPE: &[u8] = b"EGGPLANT";
/// The protocol version string the maker's board reports. Kept, so a badge
/// that checks it sees the board it expects.
const VERSION: &[u8] = b"1.0.0";
const DEFAULT_NAME: &[u8] = b"NonameEggie";

const MODE_INFECTED: u8 = 16;
const MODE_CURED: u8 = 17;
/// Light modes a badge or the button can choose: 0..=5.
pub const MODE_COUNT: u8 = 6;

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub const OFF: Rgb = Rgb { r: 0, g: 0, b: 0 };
    /// Byte order the SK6805 expects.
    pub const fn to_grb(self) -> [u8; 3] {
        [self.g, self.r, self.b]
    }
}

pub type Frame = [Rgb; LED_COUNT];

pub fn frame_to_grb(frame: &Frame) -> [u8; LED_COUNT * 3] {
    let mut out = [0u8; LED_COUNT * 3];
    for (i, c) in frame.iter().enumerate() {
        out[i * 3..i * 3 + 3].copy_from_slice(&c.to_grb());
    }
    out
}

/// The sketch's fade variables, same names, same meaning.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fader {
    pub blue: i16,
    pub red: i16,
    blue_mode: i16,
    red_mode: i16,
    blue_counter: i16,
    red_counter: i16,
    blue_counter_max: i16,
    red_counter_max: i16,
    pub blue_flip_counter: i16,
    pub red_flip_counter: i16,
    blue_min: i16,
    red_min: i16,
    blue_max: i16,
    red_max: i16,
    led_cycle_max: i16,
}

impl Fader {
    /// The starting values the sketch loads for each mode, in its order:
    /// (blue, red, blue_mode, red_mode, blue_counter, red_counter,
    ///  blue_counter_max, red_counter_max, blue_min, red_min, blue_max, red_max).
    pub fn preset(mode: u8) -> Option<Fader> {
        let t: [i16; 12] = match mode {
            0 => [0, 0, 1, 1, 0, 0, 1, 4, 12, 0, 140, 90], // slow red, normal blue
            1 => [0, 0, 1, 1, 0, 0, 1, 1, 12, 0, 112, 90], // normal red, normal blue
            2 => [0, 0, 1, 0, 0, 0, 3, 1, 12, 0, 112, 0],  // blue only pulse
            3 => [0, 0, 1, 1, 0, 0, 3, 3, 12, 12, 112, 112], // purple only pulse
            4 => [0, 0, 0, 1, 0, 0, 1, 3, 0, 12, 0, 112],  // red only pulse
            5 => [33, 33, -6, 6, 0, 0, 1, 1, -30, -30, 96, 96], // rollers
            MODE_INFECTED => [0, 0, 1, 6, 5, 0, 1, 1, 12, 0, 30, 90], // quick red flashes
            MODE_CURED => [0, 0, 6, 1, 0, 5, 1, 1, 12, 0, 140, 15], // quick blue flashes
            _ => return None,
        };
        Some(Fader {
            blue: t[0],
            red: t[1],
            blue_mode: t[2],
            red_mode: t[3],
            blue_counter: t[4],
            red_counter: t[5],
            blue_counter_max: t[6],
            red_counter_max: t[7],
            blue_flip_counter: 0,
            red_flip_counter: 0,
            blue_min: t[8],
            red_min: t[9],
            blue_max: t[10],
            red_max: t[11],
            led_cycle_max: 96,
        })
    }

    /// One pass of the first half of the sketch's `fadeUpDownLEDs()`.
    pub fn step(&mut self) {
        self.blue_counter += 1;
        if self.blue_counter >= self.blue_counter_max {
            self.blue_counter = 0;
            if self.blue >= self.blue_max {
                self.blue = self.blue_max;
                self.blue_mode = -self.blue_mode;
                self.blue_flip_counter = self.blue_flip_counter.wrapping_add(1);
            }
            if self.blue <= self.blue_min {
                self.blue = self.blue_min;
                self.blue_mode = -self.blue_mode;
                self.blue_flip_counter = self.blue_flip_counter.wrapping_add(1);
            }
            self.blue += self.blue_mode;
        }
        self.red_counter += 1;
        if self.red_counter >= self.red_counter_max {
            self.red_counter = 0;
            if self.red >= self.red_max {
                self.red = self.red_max;
                self.red_mode = -self.red_mode;
                self.red_flip_counter = self.red_flip_counter.wrapping_add(1);
            }
            if self.red <= self.red_min {
                self.red = self.red_min;
                self.red_mode = -self.red_mode;
                self.red_flip_counter = self.red_flip_counter.wrapping_add(1);
            }
            self.red += self.red_mode;
        }
    }

    /// The second half of `fadeUpDownLEDs()` switched each LED group on for
    /// `value` out of `led_cycle_max` (96) slices. Values above 96 are simply
    /// full on and values below 0 are off, which is how the maker got the
    /// pauses at the top and bottom of some fades. Same here, as a level.
    fn level(&self, value: i16) -> u8 {
        let v = value.clamp(0, self.led_cycle_max) as u32;
        (v * MAX_LEVEL as u32 / self.led_cycle_max as u32) as u8
    }

    pub fn colour(&self) -> Rgb {
        Rgb {
            r: self.level(self.red),
            g: 0,
            b: self.level(self.blue),
        }
    }
}

/// Small pseudo-random generator standing in for Arduino's `random()`.
/// Seeded from the time of the first I2C read, as the sketch does.
#[derive(Clone, Copy, Debug)]
struct Rng(u32);

impl Rng {
    fn next(&mut self) -> u32 {
        // xorshift32
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        self.0 = x;
        x
    }
    /// 0..n
    fn below(&mut self, n: u32) -> u32 {
        self.next() % n
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Inputs {
    /// The XIAO's BOOT button is held down.
    pub button_down: bool,
    /// The power switch is in OFF (it ties D1 to the 3.3 V rail).
    pub off_selected: bool,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Output {
    Show(Frame),
    /// Blank the LEDs and sleep until the switch leaves OFF.
    PowerOff,
}

/// Longest answer to one read: the sketch warns "max send 16 bytes - else
/// crash", but its own answers reach 20 (a 16-byte EEPROM read plus "|OK").
pub const TX_MAX: usize = 32;

pub struct App {
    mem: [u8; MEM_SIZE],
    regs: [u8; REG_COUNT],
    led_mode: u8,
    led_save_mode: u8,
    fader: Option<Fader>,
    rng: Rng,
    seed_set: bool,
    tx: [u8; TX_MAX],
    tx_len: usize,
    button_was_down: bool,
    button_frames: u8,
    off_frames: u8,
}

impl App {
    pub fn new() -> Self {
        let mut mem = [0xFFu8; MEM_SIZE]; // a blank EEPROM reads 0xFF
        // "#fakeROM" and the just-been-flashed defaults of the sketch's setup()
        put_str(&mut mem, MEM_TYPE, 9, TYPE);
        put_str(&mut mem, MEM_VERSION, 9, VERSION);
        for b in &mut mem[MEM_OPTIONS..MEM_OPTIONS + 9] {
            *b = 0;
        }
        put_str(&mut mem, MEM_SERIAL, 9, b"");
        put_str(&mut mem, MEM_NAME, NAME_LEN + 1, DEFAULT_NAME);
        let mut app = App {
            mem,
            regs: [0; REG_COUNT],
            led_mode: 0,
            led_save_mode: 0,
            fader: None,
            rng: Rng(0x2545_F491),
            seed_set: false,
            tx: [0; TX_MAX],
            tx_len: 0,
            button_was_down: false,
            button_frames: 0,
            off_frames: 0,
        };
        // "Herpes bit 8, 10% reoccuring percentage ... surprise herpes". With
        // the memory in RAM the permanent bit is never set at power-on, so
        // this does nothing until the memory is made to survive power-off.
        let mut ee = app.mem[MEM_OPTIONS + 2] & 128;
        if app.rng.below(100) < 10 {
            ee &= !128;
        }
        if ee != 0 {
            app.mem[MEM_OPTIONS + 1] |= ee;
            app.led_mode = MODE_INFECTED;
        }
        app
    }

    pub fn led_mode(&self) -> u8 {
        self.led_mode
    }

    pub fn name(&self) -> &[u8] {
        c_str(&self.mem[MEM_NAME..MEM_NAME + NAME_LEN + 1])
    }

    /// Call every 10 ms.
    pub fn tick(&mut self, inputs: Inputs) -> Output {
        // Power switch: OFF must be seen on 5 frames running (50 ms).
        if inputs.off_selected {
            self.off_frames = self.off_frames.saturating_add(1);
            if self.off_frames >= 5 {
                return Output::PowerOff;
            }
        } else {
            self.off_frames = 0;
        }

        // BOOT button: a press that lasts 3 frames (30 ms) steps the mode.
        if inputs.button_down {
            self.button_frames = self.button_frames.saturating_add(1);
            if self.button_frames == 3 && !self.button_was_down {
                self.button_was_down = true;
                self.set_mode((self.led_save_mode + 1) % MODE_COUNT);
            }
        } else {
            self.button_frames = 0;
            self.button_was_down = false;
        }

        for _ in 0..STEPS_PER_FRAME {
            self.step();
        }
        let c = match &self.fader {
            Some(f) => f.colour(),
            None => Rgb::OFF,
        };
        Output::Show([c; LED_COUNT])
    }

    /// One pass of the sketch's `loop()`.
    fn step(&mut self) {
        if self.fader.is_none() {
            self.fader = Fader::preset(self.led_mode); // `led_mode_set = 1`
        }
        let Some(f) = self.fader.as_mut() else {
            return; // the sketch's `default:` case: both LED groups off
        };
        // "flash red quickly ten times" / "flash blue quickly ten times"
        let done = match self.led_mode {
            MODE_INFECTED => f.red_flip_counter >= 20,
            MODE_CURED => f.blue_flip_counter >= 20,
            _ => false,
        };
        if done {
            self.led_mode = self.led_save_mode;
            self.fader = Fader::preset(self.led_mode);
            if self.fader.is_none() {
                return;
            }
        }
        if let Some(f) = self.fader.as_mut() {
            f.step();
        }
    }

    fn set_mode(&mut self, mode: u8) {
        self.led_mode = mode;
        self.led_save_mode = mode;
        self.fader = None;
        self.mem[MEM_OPTIONS] = mode;
    }

    fn flash(&mut self, mode: u8) {
        self.led_mode = mode;
        self.fader = None;
    }

    /// The badge wrote bytes to us. As in the sketch's `receiveEvent()`, the
    /// first byte is a position in the register window and the rest are
    /// stored from there on (the badge always sends 0 first, then noun,
    /// verb, data). Nothing else happens until the badge reads.
    pub fn on_i2c_write(&mut self, bytes: &[u8]) {
        if bytes.is_empty() || bytes.len() > REG_COUNT {
            return;
        }
        let mut pos = bytes[0] as usize;
        for &b in &bytes[1..] {
            if pos >= REG_COUNT {
                pos = 0;
            }
            self.regs[pos] = b;
            pos += 1;
        }
    }

    /// The badge is reading from us: carry out the command in the register
    /// window and return the answer (the sketch's `requestEvent()`). The
    /// sketch ran this once per byte the badge clocked out; here it runs once
    /// per read, which is what its author clearly meant.
    /// `now_us` seeds the random numbers on the first call, as `micros()` did.
    pub fn on_i2c_read(&mut self, now_us: u32) -> &[u8] {
        if !self.seed_set {
            self.rng = Rng(now_us | 1);
            self.seed_set = true;
        }
        self.tx_len = 0;
        let (noun, verb) = (self.regs[0], self.regs[1]);
        match noun {
            0 => match verb {
                0 => self.send_mem_str(MEM_TYPE, 9),
                1 => self.send_mem_str(MEM_VERSION, 9),
                2 => {
                    let first = self.mem[MEM_SERIAL];
                    if !(32..=126).contains(&first) {
                        // "invalid serial number, so generate a new one"
                        for i in 0..8 {
                            let mut c = 48 + self.rng.below(15) as u8; // random(48, 63)
                            if c > 57 {
                                c += 7;
                            }
                            self.mem[MEM_SERIAL + i] = c;
                        }
                        self.mem[MEM_SERIAL + 8] = 0;
                    }
                    self.send_mem_str(MEM_SERIAL, 9);
                }
                3 => self.send_mem_str(MEM_NAME, NAME_LEN + 1),
                _ => self.send(b"ERROR 0"),
            },
            1 => match verb {
                3 => {
                    let mut name = [0u8; NAME_LEN + 1];
                    for i in 0..NAME_LEN {
                        let c = self.regs[2 + i];
                        if (32..=126).contains(&c) {
                            name[i] = c;
                        } else {
                            break;
                        }
                    }
                    self.mem[MEM_NAME..MEM_NAME + NAME_LEN + 1].copy_from_slice(&name);
                    self.send_mem_str(MEM_NAME, NAME_LEN + 1);
                    self.send(b"|OK");
                }
                _ => self.send(b"ERROR 1"),
            },
            2 => {
                // "Read LED Mode": the mode, then the fade variables as a debug dump.
                let f = self.fader.or_else(|| Fader::preset(self.led_mode));
                self.push(self.led_mode);
                if let Some(f) = f {
                    for v in [
                        f.red,
                        f.blue,
                        f.red_flip_counter,
                        f.blue_flip_counter,
                        f.red_counter,
                        f.blue_counter,
                        f.red_counter_max,
                        f.blue_counter_max,
                        f.red_min,
                        f.blue_min,
                        f.red_max,
                        f.blue_max,
                        f.led_cycle_max,
                    ] {
                        self.push(v as u8);
                    }
                }
            }
            3 => {
                // "Write LED Mode": the sketch takes the mode from the verb
                // byte (its API text says the byte after; the badge sends
                // {0, 3, mode}). Anything above 5 becomes 0.
                let mode = if verb > 5 { 0 } else { verb };
                self.regs[1] = mode;
                self.set_mode(mode);
                self.push(mode);
                self.send(b"|OK");
            }
            4 => match verb {
                0 => {
                    // "Try to infect me": roll the dice on each disease.
                    let mut ee = self.mem[MEM_OPTIONS + 1];
                    if self.rng.below(100) < 50 {
                        ee &= !64; // Chlamydia, 50 % transmission
                    }
                    if self.rng.below(100) < 70 {
                        ee &= !128; // Herpes, 30 % transmission
                    }
                    self.push(ee);
                    if ee != 0 {
                        self.send(b"|INFECTED");
                        self.flash(MODE_INFECTED);
                    } else {
                        self.send(b"|AOK");
                    }
                }
                1 => {
                    // "Report true infection status"
                    let (o1, o2) = (self.mem[MEM_OPTIONS + 1], self.mem[MEM_OPTIONS + 2]);
                    self.push(o1);
                    self.push(o2);
                    if o1 != 0 || o2 != 0 {
                        self.send(b"|INFECTED");
                        self.flash(MODE_INFECTED);
                    } else {
                        self.send(b"|AOK");
                    }
                }
                _ => self.send(b"ERROR 4"),
            },
            5 => {
                let bits = self.regs[2] & 192; // "only act on bits 7 & 8"
                self.regs[2] = bits;
                let old = self.mem[MEM_OPTIONS + 1];
                match verb {
                    0 => {
                        let new = old | bits;
                        if new != old {
                            self.mem[MEM_OPTIONS + 1] = new;
                            self.flash(MODE_INFECTED);
                            self.push(new);
                            self.send(b"|INFECTED");
                            if new & 128 != 0 {
                                // "it can't be really ever cured"
                                self.mem[MEM_OPTIONS + 2] = new & 128;
                            }
                        } else {
                            self.push(old);
                            self.send(b"|NOCHANGE");
                        }
                    }
                    1 => {
                        let new = old & !bits;
                        if new != old {
                            self.mem[MEM_OPTIONS + 1] = new;
                            self.flash(MODE_CURED);
                            self.push(new);
                            self.send(b"|CURED");
                        } else {
                            self.push(old);
                            self.send(b"|NOCHANGE");
                        }
                    }
                    _ => self.send(b"ERROR 5"),
                }
            }
            8 => {
                // "Read EEPROM - address is Little-endian", up to 16 bytes
                let mut addr = ((self.regs[2] as usize) << 8) | self.regs[1] as usize;
                let n = self.regs[3].min(16);
                for _ in 0..n {
                    if addr >= MEM_SIZE {
                        addr = 0;
                    }
                    self.push(self.mem[addr]);
                    addr += 1;
                }
            }
            9 => {
                // "Write EEPROM", up to 10 bytes, echoed back, then "|OK"
                let mut addr = ((self.regs[2] as usize) << 8) | self.regs[1] as usize;
                let n = self.regs[3].min(10) as usize;
                for i in 0..n {
                    if addr >= MEM_SIZE {
                        addr = 0;
                    }
                    let b = self.regs[4 + i];
                    self.mem[addr] = b;
                    self.push(b);
                    addr += 1;
                }
                self.send(b"|OK");
            }
            _ => self.send(b"ERROR F"),
        }
        &self.tx[..self.tx_len]
    }

    fn push(&mut self, b: u8) {
        if self.tx_len < TX_MAX {
            self.tx[self.tx_len] = b;
            self.tx_len += 1;
        }
    }

    fn send(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.push(b);
        }
    }

    fn send_mem_str(&mut self, at: usize, max: usize) {
        let mut tmp = [0u8; NAME_LEN + 1];
        let s = c_str(&self.mem[at..at + max]);
        let n = s.len();
        tmp[..n].copy_from_slice(s);
        self.send(&tmp[..n]);
    }
}

impl Default for App {
    fn default() -> Self {
        Self::new()
    }
}

fn put_str(mem: &mut [u8], at: usize, field: usize, s: &[u8]) {
    for i in 0..field {
        mem[at + i] = if i < s.len() { s[i] } else { 0 };
    }
}

/// The bytes before the first 0 (the whole slice if there is none).
fn c_str(bytes: &[u8]) -> &[u8] {
    let n = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
    &bytes[..n]
}

#[cfg(test)]
mod tests {
    use super::*;

    const IDLE: Inputs = Inputs {
        button_down: false,
        off_selected: false,
    };

    fn ask(app: &mut App, cmd: &[u8]) -> Vec<u8> {
        app.on_i2c_write(cmd);
        app.on_i2c_read(12345).to_vec()
    }

    #[test]
    fn identifies_itself_like_the_original() {
        let mut app = App::new();
        assert_eq!(ask(&mut app, &[0, 0, 0]), b"EGGPLANT");
        assert_eq!(ask(&mut app, &[0, 0, 1]), b"1.0.0");
        assert_eq!(ask(&mut app, &[0, 0, 3]), b"NonameEggie");
    }

    #[test]
    fn serial_is_made_once_and_kept() {
        let mut app = App::new();
        let a = ask(&mut app, &[0, 0, 2]);
        assert_eq!(a.len(), 8);
        assert!(a.iter().all(|c| c.is_ascii_digit() || (b'A'..=b'F').contains(c)));
        assert_eq!(ask(&mut app, &[0, 0, 2]), a);
    }

    #[test]
    fn badge_can_rename_it() {
        let mut app = App::new();
        // what the Darknet 7 badge sends: {0, 1, 3, name..., 0}
        let mut cmd = vec![0u8, 1, 3];
        cmd.extend_from_slice(b"Aubergine\0\0\0\0");
        assert_eq!(ask(&mut app, &cmd), b"Aubergine|OK");
        assert_eq!(app.name(), b"Aubergine");
    }

    #[test]
    fn badge_sets_the_light_mode() {
        let mut app = App::new();
        assert_eq!(ask(&mut app, &[0, 3, 4]), [4, b'|', b'O', b'K']);
        assert_eq!(app.led_mode(), 4);
        assert_eq!(ask(&mut app, &[0, 3, 9])[0], 0); // above 5 becomes 0
    }

    #[test]
    fn infect_then_cure() {
        let mut app = App::new();
        assert_eq!(ask(&mut app, &[0, 4, 1]), [0, 0, b'|', b'A', b'O', b'K']);
        let a = ask(&mut app, &[0, 5, 0, 64]);
        assert_eq!(a[0], 64);
        assert_eq!(&a[1..], b"|INFECTED");
        assert_eq!(app.led_mode(), MODE_INFECTED);
        assert_eq!(&ask(&mut app, &[0, 5, 0, 64])[1..], b"|NOCHANGE");
        let c = ask(&mut app, &[0, 5, 1, 64]);
        assert_eq!(c[0], 0);
        assert_eq!(&c[1..], b"|CURED");
        assert_eq!(app.led_mode(), MODE_CURED);
    }

    #[test]
    fn herpes_is_remembered_after_a_cure() {
        let mut app = App::new();
        ask(&mut app, &[0, 5, 0, 128]);
        ask(&mut app, &[0, 5, 1, 128]);
        let s = ask(&mut app, &[0, 4, 1]);
        assert_eq!((s[0], s[1]), (0, 128));
        assert_eq!(&s[2..], b"|INFECTED");
    }

    #[test]
    fn flashes_end_and_the_chosen_mode_comes_back() {
        let mut app = App::new();
        ask(&mut app, &[0, 3, 2]);
        ask(&mut app, &[0, 5, 0, 64]);
        assert_eq!(app.led_mode(), MODE_INFECTED);
        for _ in 0..2000 {
            app.tick(IDLE);
        }
        assert_eq!(app.led_mode(), 2);
    }

    #[test]
    fn memory_reads_and_writes() {
        let mut app = App::new();
        assert_eq!(ask(&mut app, &[0, 8, 0, 0, 8]), b"EGGPLANT");
        assert_eq!(ask(&mut app, &[0, 9, 100, 0, 3, 7, 8, 9]), [7, 8, 9, b'|', b'O', b'K']);
        assert_eq!(ask(&mut app, &[0, 8, 100, 0, 3]), [7, 8, 9]);
    }

    #[test]
    fn mode_0_breathes_purple_and_stays_in_range() {
        let mut app = App::new();
        let (mut max_r, mut max_b, mut saw_dark_red) = (0u8, 0u8, false);
        for _ in 0..3000 {
            let Output::Show(f) = app.tick(IDLE) else {
                panic!("switched off by itself")
            };
            assert!(f.iter().all(|c| *c == f[0] && c.g == 0));
            max_r = max_r.max(f[0].r);
            max_b = max_b.max(f[0].b);
            saw_dark_red |= f[0].r == 0;
        }
        assert!(max_r > 0 && max_r <= MAX_LEVEL);
        assert_eq!(max_b, MAX_LEVEL);
        assert!(saw_dark_red);
    }

    #[test]
    fn button_steps_through_the_modes() {
        let mut app = App::new();
        let down = Inputs {
            button_down: true,
            off_selected: false,
        };
        for expect in [1u8, 2, 3, 4, 5, 0] {
            for _ in 0..5 {
                app.tick(down);
            }
            for _ in 0..5 {
                app.tick(IDLE);
            }
            assert_eq!(app.led_mode(), expect);
        }
    }

    #[test]
    fn off_switch_powers_down_after_50_ms() {
        let mut app = App::new();
        let off = Inputs {
            button_down: false,
            off_selected: true,
        };
        for _ in 0..4 {
            assert!(matches!(app.tick(off), Output::Show(_)));
        }
        assert_eq!(app.tick(off), Output::PowerOff);
    }
}
