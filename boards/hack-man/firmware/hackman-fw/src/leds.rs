//! Minimal SK6805 / WS2812 driver on the RMT peripheral.
//!
//! Five LEDs = 120 bits. Each bit is one RMT pulse code (high time, low
//! time). The data line idles low between frames; the >80 us "reset" gap the
//! LEDs need to latch comes for free because frames are sent every ~16 ms.

use esp_hal::{
    Blocking,
    gpio::{Level, interconnect::PeripheralOutput},
    rmt::{Channel, PulseCode, Tx, TxChannelConfig, TxChannelCreator},
};
use hackman_core::{Frame, LED_COUNT, frame_to_grb};

/// RMT tick rate we ask for. 80 MHz -> 12.5 ns per tick.
pub const RMT_MHZ: u32 = 80;

// Bit timings in nanoseconds. SK6805-EC3210R datasheet values are close to
// WS2812B: T0H ~0.3 us, T1H ~0.6-0.9 us, bit period ~1.25 us (800 kbit/s).
// These sit in the middle of the usual tolerance windows. UNVERIFIED on the
// real LEDs at 3.3 V: check with a logic analyser if colours glitch.
const T0H_NS: u32 = 350;
const T0L_NS: u32 = 900;
const T1H_NS: u32 = 800;
const T1L_NS: u32 = 450;

const fn ticks(ns: u32) -> u16 {
    (ns * RMT_MHZ / 1000) as u16
}

const ZERO: PulseCode = PulseCode::new(Level::High, ticks(T0H_NS), Level::Low, ticks(T0L_NS));
const ONE: PulseCode = PulseCode::new(Level::High, ticks(T1H_NS), Level::Low, ticks(T1L_NS));

const BITS: usize = LED_COUNT * 24;

pub struct Leds<'d> {
    // `transmit` consumes the channel and hands it back; Option bridges that.
    channel: Option<Channel<'d, Blocking, Tx>>,
    buf: [PulseCode; BITS + 1],
}

impl<'d> Leds<'d> {
    pub fn new(
        creator: impl TxChannelCreator<'d, Blocking>,
        pin: impl PeripheralOutput<'d>,
    ) -> Self {
        let config = TxChannelConfig::default()
            .with_clk_divider(1)
            .with_idle_output_level(Level::Low)
            .with_idle_output(true)
            .with_carrier_modulation(false)
            // One RMT memory block (48 codes). The 121-code frame is longer, so
            // esp-hal refills the block while sending ("wrap" mode); we send
            // with interrupts off so the refill cannot be starved.
            .with_memsize(1);
        let channel = creator
            .configure_tx(&config)
            .expect("RMT TX config")
            .with_pin(pin);
        Self {
            channel: Some(channel),
            buf: [PulseCode::end_marker(); BITS + 1],
        }
    }

    /// Send one frame (final values; brightness already applied).
    pub fn write(&mut self, frame: &Frame) {
        let bytes = frame_to_grb(frame);
        let mut i = 0;
        for byte in bytes {
            for bit in (0..8).rev() {
                self.buf[i] = if byte & (1 << bit) != 0 { ONE } else { ZERO };
                i += 1;
            }
        }
        self.buf[BITS] = PulseCode::end_marker();

        let Some(ch) = self.channel.take() else {
            return;
        };
        // ~150 us with interrupts masked. The I2C peripheral keeps receiving
        // into its hardware FIFO meanwhile, so no bytes are lost.
        let result = critical_section::with(|_| match ch.transmit(&self.buf) {
            Ok(tx) => tx.wait().map_err(|(_, ch)| ch),
            Err((_, ch)) => Err(ch),
        });
        self.channel = Some(match result {
            Ok(ch) | Err(ch) => ch,
        });
    }
}
