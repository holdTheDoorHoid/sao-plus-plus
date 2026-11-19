//! The six touch areas, and turning the touch chip's mask into presses.
//!
//! Which touch-chip input goes to which area is fixed by the board's wiring
//! (hardware/circuit.json): CS1 = A (top left), CS2 = up (top middle),
//! CS3 = B (top right), CS4 = left (bottom left, the "<"), CS5 = down
//! (bottom middle), CS6 = right (bottom right, the ">"). The maker's
//! sketches named them the same way.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Pad {
    A = 0,
    Up = 1,
    B = 2,
    Left = 3,
    Down = 4,
    Right = 5,
}

pub const PADS: [Pad; 6] = [Pad::A, Pad::Up, Pad::B, Pad::Left, Pad::Down, Pad::Right];

impl Pad {
    /// The touch-chip input (bit in its status mask) wired to this area.
    pub const fn bit(self) -> u8 {
        1 << (self as u8)
    }

    pub fn from_index(i: u8) -> Option<Pad> {
        PADS.get(i as usize).copied()
    }
}

/// Edges between two polls. A short dropout (one poll) is ignored by the
/// chip itself, which filters touches; this only compares masks.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Edges {
    pub held: u8,
    pub pressed: u8,
    pub released: u8,
}

impl Edges {
    pub fn between(before: u8, now: u8) -> Self {
        Self { held: now, pressed: now & !before, released: before & !now }
    }

    pub fn pressed(&self, p: Pad) -> bool {
        self.pressed & p.bit() != 0
    }

    pub fn held(&self, p: Pad) -> bool {
        self.held & p.bit() != 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bits_are_the_wiring() {
        assert_eq!(Pad::A.bit(), 0x01);
        assert_eq!(Pad::Right.bit(), 0x20);
        assert_eq!(Pad::from_index(4), Some(Pad::Down));
        assert_eq!(Pad::from_index(6), None);
    }

    #[test]
    fn edges() {
        let e = Edges::between(Pad::A.bit(), Pad::A.bit() | Pad::Up.bit());
        assert!(e.pressed(Pad::Up) && !e.pressed(Pad::A) && e.held(Pad::A));
        let e = Edges::between(Pad::A.bit(), 0);
        assert_eq!(e.released, Pad::A.bit());
    }
}
