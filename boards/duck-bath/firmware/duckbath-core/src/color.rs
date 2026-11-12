//! Colour type.

/// One RGB colour, 0..=255 per channel, exactly as sent to the LED.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Rgb {
    pub r: u8,
    pub g: u8,
    pub b: u8,
}

impl Rgb {
    pub const fn new(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b }
    }

    pub const OFF: Rgb = Rgb::new(0, 0, 0);

    /// Bytes in the order the SK6805 / WS2812 shifts them in: G, R, B.
    pub const fn to_grb(self) -> [u8; 3] {
        [self.g, self.r, self.b]
    }
}
