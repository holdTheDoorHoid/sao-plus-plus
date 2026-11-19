//! The maker's I2C protocol, re-implemented from his `eggplant_i2c_api.txt` and
//! from what his sketch actually does (where the two differ, the sketch wins,
//! because that is what badges were written against).
//!
//! # Address
//! House address [`HOUSE_ADDRESS`] (0x28), or his 0x36 ("EG") with the
//! `maker-address` cargo feature.
//!
//! # How a badge talks to it
//! A write is `[pointer, bytes...]`: the first byte says where in a 16-byte
//! register file the rest goes. His notes tell badge writers to send a zero
//! first, then `noun, verb, data...`, so the noun lands in register 0 and the
//! verb in register 1. A one-byte write only moves the pointer. The badge then
//! reads, and gets the answer to the noun and verb in registers 0 and 1.
//!
//! | noun | verb | data | answer |
//! |---|---|---|---|
//! | 0x00 | 0 / 1 / 2 / 3 | | type `EGGPLANT` / version `1.0.0` / serial (8 chars) / name (up to 12) |
//! | 0x01 | 3 | up to 12 printable characters | sets the name; answers name + `|OK` |
//! | 0x02 | | | 14 bytes of light-show state: mode, red, blue, red bounces, blue bounces, red counter, blue counter, red slowdown, blue slowdown, red min, blue min, red max, blue max, 96 |
//! | 0x03 | mode | | mode 0..=5 (anything above 5 becomes 0, as in his sketch); answers mode + `|OK` |
//! | 0x04 | 0 | | "try to infect me": his infection byte with each bug passed on only by chance (0x40 half the time, 0x80 three times in ten); + `|INFECTED` or `|AOK` |
//! | 0x04 | 1 | | his true status: infection byte, lasting byte; + `|INFECTED` or `|AOK` |
//! | 0x05 | 0 | bits | infect: sets bits 0x40 / 0x80 (others ignored); 0x80 also lasts; + `|INFECTED` or `|NOCHANGE` |
//! | 0x05 | 1 | bits | cure: clears them (a lasting 0x80 comes back at power-on, nine times in ten); + `|CURED` or `|NOCHANGE` |
//! | 0x08 | addr lo, addr hi, n | | n (up to 16) bytes of the 512-byte memory (see `store`) |
//! | 0x09 | addr lo, addr hi, n, data | | writes n (up to 10) bytes; answers them + `|OK` |
//! | other | | | `ERROR F` (bad verbs give `ERROR 0`, `1`, `4`, `5`) |
//!
//! Any answer to an infection that is (still) present makes the eggplant
//! flash red; a cure flashes blue.
//!
//! **One deliberate difference:** his ATtiny worked the answer out when the
//! badge read, so reading twice re-rolled "try to infect me". This firmware
//! works it out once, when the command is written (the ESP32-S3 cannot answer
//! late), and every read until the next command gets the same answer.

use crate::fade::{Engine, Show};
use crate::rng::Rng;
use crate::store::{self, Store};

pub const HOUSE_ADDRESS: u8 = 0x28;
pub const MAKER_ADDRESS: u8 = 0x36;

#[cfg(not(feature = "maker-address"))]
pub const ADDRESS: u8 = HOUSE_ADDRESS;
#[cfg(feature = "maker-address")]
pub const ADDRESS: u8 = MAKER_ADDRESS;

pub const REGS: usize = 16;
pub const REPLY_MAX: usize = 16;

/// An answer waiting for the badge to read it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Reply {
    pub buf: [u8; REPLY_MAX],
    pub len: usize,
}

impl Reply {
    pub const fn empty() -> Self {
        Self { buf: [0; REPLY_MAX], len: 0 }
    }

    pub fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.len]
    }

    fn push(&mut self, b: &[u8]) {
        for &x in b {
            if self.len < REPLY_MAX {
                self.buf[self.len] = x;
                self.len += 1;
            }
        }
    }

    fn of(parts: &[&[u8]]) -> Self {
        let mut r = Self::empty();
        for p in parts {
            r.push(p);
        }
        r
    }
}

pub struct Protocol {
    pub regs: [u8; REGS],
    pointer: usize,
    pub reply: Reply,
}

impl Default for Protocol {
    fn default() -> Self {
        Self::new()
    }
}

impl Protocol {
    pub const fn new() -> Self {
        Self { regs: [0; REGS], pointer: 0, reply: Reply::empty() }
    }

    /// A finished write from the badge. Returns true if it carried a command
    /// (more than the pointer byte), which is then carried out at once.
    pub fn on_write(&mut self, bytes: &[u8], store: &mut Store, leds: &mut Engine, rng: &mut Rng) -> bool {
        let Some((&p, rest)) = bytes.split_first() else {
            return false;
        };
        self.pointer = p as usize % REGS;
        if rest.is_empty() {
            return false;
        }
        for &b in rest {
            self.regs[self.pointer] = b;
            self.pointer = (self.pointer + 1) % REGS;
        }
        self.reply = answer(&self.regs, store, leds, rng);
        true
    }
}

fn mark(infected: bool) -> &'static [u8] {
    if infected { b"|INFECTED" } else { b"|AOK" }
}

/// Work out the answer to the command in the registers, doing what it asks.
pub fn answer(r: &[u8; REGS], store: &mut Store, leds: &mut Engine, rng: &mut Rng) -> Reply {
    match r[0] {
        0x00 => match r[1] {
            0 => Reply::of(&[store.field(store::TYPE_AT, 9)]),
            1 => Reply::of(&[store.field(store::VERSION_AT, 9)]),
            2 => Reply::of(&[store.field(store::SERIAL_AT, 9)]),
            3 => Reply::of(&[store.field(store::NAME_AT, 13)]),
            _ => Reply::of(&[b"ERROR 0"]),
        },
        0x01 => match r[1] {
            3 => {
                let mut name = [0u8; store::NAME_MAX];
                let mut n = 0;
                for &c in &r[2..2 + store::NAME_MAX] {
                    if !(32..=126).contains(&c) {
                        break;
                    }
                    name[n] = c;
                    n += 1;
                }
                store.set_name(&name[..n]);
                let mut rep = Reply::of(&[store.field(store::NAME_AT, 13)]);
                rep.push(b"|OK");
                rep
            }
            _ => Reply::of(&[b"ERROR 1"]),
        },
        0x02 => {
            let (rd, bl) = (&leds.red, &leds.blue);
            let b = |v: i16| v as u8;
            Reply::of(&[&[
                leds.show().number(),
                b(rd.value),
                b(bl.value),
                rd.bounces as u8,
                bl.bounces as u8,
                b(rd.counter),
                b(bl.counter),
                b(rd.slowdown),
                b(bl.slowdown),
                b(rd.min),
                b(bl.min),
                b(rd.max),
                b(bl.max),
                crate::fade::CYCLE as u8,
            ]])
        }
        0x03 => {
            let mode = if r[1] > 5 { 0 } else { r[1] };
            leds.select(Show::from_number(mode));
            store.set_option(0, mode);
            Reply::of(&[&[mode], b"|OK"])
        }
        0x04 => match r[1] {
            0 => {
                let mut d = store.option(1);
                if rng.below(100) < 50 {
                    d &= !store::BUG_A;
                }
                if rng.below(100) < 70 {
                    d &= !store::BUG_B;
                }
                if d != 0 {
                    leds.flash(Show::Infected);
                }
                Reply::of(&[&[d], mark(d != 0)])
            }
            1 => {
                let (a, b) = (store.option(1), store.option(2));
                if a != 0 || b != 0 {
                    leds.flash(Show::Infected);
                }
                Reply::of(&[&[a, b], mark(a != 0 || b != 0)])
            }
            _ => Reply::of(&[b"ERROR 4"]),
        },
        0x05 => {
            let bits = r[2] & store::BUGS;
            let now = store.option(1);
            match r[1] {
                0 => {
                    let d = now | bits;
                    if d == now {
                        return Reply::of(&[&[now], b"|NOCHANGE"]);
                    }
                    store.set_option(1, d);
                    if d & store::BUG_B != 0 {
                        store.set_option(2, store::BUG_B);
                    }
                    leds.flash(Show::Infected);
                    Reply::of(&[&[d], b"|INFECTED"])
                }
                1 => {
                    let d = now & !bits;
                    if d == now {
                        return Reply::of(&[&[now], b"|NOCHANGE"]);
                    }
                    store.set_option(1, d);
                    leds.flash(Show::Cured);
                    Reply::of(&[&[d], b"|CURED"])
                }
                _ => Reply::of(&[b"ERROR 5"]),
            }
        }
        0x08 => {
            let addr = r[1] as usize | (r[2] as usize) << 8;
            let n = (r[3] as usize).min(16);
            let mut rep = Reply::empty();
            for k in 0..n {
                rep.push(&[store.read(addr + k)]);
            }
            rep
        }
        0x09 => {
            let addr = r[1] as usize | (r[2] as usize) << 8;
            let n = (r[3] as usize).min(10);
            let mut rep = Reply::empty();
            for k in 0..n {
                let v = r[4 + k];
                store.write(addr + k, v);
                rep.push(&[v]);
            }
            rep.push(b"|OK");
            rep
        }
        _ => Reply::of(&[b"ERROR F"]),
    }
}

/// At power-on: a lasting bug (0x80 in the lasting byte) comes back nine
/// times in ten, as on his board. Returns true if it did (the caller flashes).
pub fn relapse(store: &mut Store, rng: &mut Rng) -> bool {
    if store.option(2) & store::BUG_B != 0 && rng.below(100) >= 10 {
        store.set_option(1, store.option(1) | store::BUG_B);
        return true;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rig() -> (Protocol, Store, Engine, Rng) {
        (Protocol::new(), Store::new(*b"0123ABCD"), Engine::new(Show::SlowRedBlue), Rng::new(7))
    }

    fn ask(p: &mut Protocol, s: &mut Store, e: &mut Engine, r: &mut Rng, cmd: &[u8]) -> std::vec::Vec<u8> {
        let mut w = std::vec![0u8];
        w.extend_from_slice(cmd);
        assert!(p.on_write(&w, s, e, r));
        p.reply.as_bytes().to_vec()
    }

    #[test]
    fn system_info() {
        let (mut p, mut s, mut e, mut r) = rig();
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0, 0]), b"EGGPLANT");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0, 1]), b"1.0.0");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0, 2]), b"0123ABCD");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0, 9]), b"ERROR 0");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0x77]), b"ERROR F");
    }

    #[test]
    fn rename() {
        let (mut p, mut s, mut e, mut r) = rig();
        let mut cmd = std::vec![1u8, 3];
        cmd.extend_from_slice(b"Aubergine\0junk");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &cmd), b"Aubergine|OK");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[0, 3]), b"Aubergine");
    }

    #[test]
    fn pointer_only_write_changes_nothing() {
        let (mut p, mut s, mut e, mut r) = rig();
        ask(&mut p, &mut s, &mut e, &mut r, &[0, 0]);
        assert!(!p.on_write(&[0], &mut s, &mut e, &mut r));
        assert_eq!(p.reply.as_bytes(), b"EGGPLANT");
        assert!(!p.on_write(&[], &mut s, &mut e, &mut r));
    }

    #[test]
    fn set_mode_and_clamp() {
        let (mut p, mut s, mut e, mut r) = rig();
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[3, 4]), [&[4u8][..], b"|OK"].concat());
        assert_eq!(e.show(), Show::RedPulse);
        assert_eq!(s.option(0), 4);
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[3, 6]), [&[0u8][..], b"|OK"].concat());
        assert_eq!(e.show(), Show::SlowRedBlue);
        let st = ask(&mut p, &mut s, &mut e, &mut r, &[2]);
        assert_eq!(st.len(), 14);
        assert_eq!(st[13], 96);
    }

    #[test]
    fn infect_cure_cycle() {
        let (mut p, mut s, mut e, mut r) = rig();
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[4, 1]), [&[0u8, 0][..], b"|AOK"].concat());
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[5, 0, 0xFF]), [&[0xC0u8][..], b"|INFECTED"].concat());
        assert_eq!(e.show(), Show::Infected);
        assert_eq!(s.option(2), 0x80, "the 0x80 bug lasts");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[5, 0, 0x40]), [&[0xC0u8][..], b"|NOCHANGE"].concat());
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[5, 1, 0xC0]), [&[0u8][..], b"|CURED"].concat());
        assert_eq!(e.show(), Show::Cured);
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[4, 1]), [&[0u8, 0x80][..], b"|INFECTED"].concat());
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[5, 7, 0]), b"ERROR 5");
    }

    #[test]
    fn try_to_infect_passes_bugs_by_chance() {
        let (mut p, mut s, mut e, mut r) = rig();
        s.set_option(1, 0xC0);
        let (mut a, mut b) = (0, 0);
        for _ in 0..2000 {
            let rep = ask(&mut p, &mut s, &mut e, &mut r, &[4, 0]);
            a += (rep[0] & 0x40 != 0) as u32;
            b += (rep[0] & 0x80 != 0) as u32;
        }
        assert!((850..1150).contains(&a), "0x40 passed {a} of 2000");
        assert!((450..750).contains(&b), "0x80 passed {b} of 2000");
        assert_eq!(s.option(1), 0xC0, "asking does not cure");
    }

    #[test]
    fn memory_read_and_write() {
        let (mut p, mut s, mut e, mut r) = rig();
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[8, 0, 0, 8]), b"EGGPLANT");
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[8, 0, 0, 40]).len(), 16);
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[9, 0x00, 0x01, 3, 7, 8, 9]), [&[7u8, 8, 9][..], b"|OK"].concat());
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[8, 0x00, 0x01, 3]), [7, 8, 9]);
        // addresses wrap at 512, as his did
        assert_eq!(ask(&mut p, &mut s, &mut e, &mut r, &[8, 0x00, 0x02, 2]), b"EG");
    }

    #[test]
    fn relapse_mostly_comes_back() {
        let mut back = 0;
        for seed in 1..=500u32 {
            let mut s = Store::new(*b"00000000");
            s.set_option(2, 0x80);
            let mut r = Rng::new(seed);
            back += relapse(&mut s, &mut r) as u32;
        }
        assert!((400..=490).contains(&back), "{back} of 500");
        let mut s = Store::new(*b"00000000");
        assert!(!relapse(&mut s, &mut Rng::new(3)));
    }

    #[test]
    fn address_is_the_house_one_by_default() {
        #[cfg(not(feature = "maker-address"))]
        assert_eq!(ADDRESS, 0x28);
        #[cfg(feature = "maker-address")]
        assert_eq!(ADDRESS, 0x36);
    }
}
