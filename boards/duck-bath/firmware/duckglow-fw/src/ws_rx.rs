//! Receiving WS2812 data on SAO GPIO2 with the chip's RMT receiver, which
//! measures every high and low time in hardware (100 ns resolution here) and
//! stops by itself after 6 us of quiet: the WS2812 "latch". The pulse lengths
//! go to `duckglow_core::ws2812`, which turns them into colours.
//!
//! The RMT buffer holds 192 pulses, so the add-on sees the first 8 LEDs' worth
//! of a frame. The maker's board keeps the LAST LEDs of a frame; on a longer
//! chain this one would see the wrong ones. Badges driving a duck as a 2-LED
//! strip (the maker's examples) are unaffected.

use duckglow_core::ws2812::LATCH_NS;
use esp_hal::{
    Blocking,
    gpio::{Level, interconnect::PeripheralInput},
    peripherals::RMT,
    rmt::{Channel, PulseCode, Rmt, RxChannelConfig, RxChannelCreator, RxTransaction},
    time::Rate,
    rmt::Rx,
};

/// RMT clock 80 MHz / 8 = 10 MHz: one tick is 100 ns.
const DIV: u8 = 8;
const NS_PER_TICK: u32 = 100;
const CODES: usize = 192;

static mut BUF: [PulseCode; CODES] = [PulseCode(0); CODES];

enum State<'d> {
    Idle(Channel<'d, Blocking, Rx>),
    Busy(RxTransaction<'d, 'static>),
    Gone,
}

pub struct WsReceiver<'d> {
    state: State<'d>,
    pairs: [(u32, u32); CODES],
}

impl<'d> WsReceiver<'d> {
    pub fn new(rmt: RMT<'d>, pin: impl PeripheralInput<'d>) -> Self {
        let rmt = Rmt::new(rmt, Rate::from_mhz(80)).expect("RMT");
        let cfg = RxChannelConfig::default()
            .with_clk_divider(DIV)
            .with_idle_threshold((LATCH_NS / NS_PER_TICK) as u16)
            .with_filter_threshold(8) // ignore glitches under 0.1 us
            .with_memsize(4);
        #[cfg(any(feature = "esp32c3", feature = "esp32c6"))]
        let ch = rmt.channel2.configure_rx(&cfg).expect("RMT rx").with_pin(pin);
        #[cfg(feature = "esp32s3")]
        let ch = rmt.channel4.configure_rx(&cfg).expect("RMT rx").with_pin(pin);
        Self { state: State::Idle(ch), pairs: [(0, 0); CODES] }
    }

    /// Non-blocking: returns a finished frame as (high ns, low ns) pairs.
    pub fn poll(&mut self) -> Option<&[(u32, u32)]> {
        match core::mem::replace(&mut self.state, State::Gone) {
            State::Idle(ch) => {
                // SAFETY: BUF is only ever lent to the one transaction in flight.
                let buf: &'static mut [PulseCode; CODES] = unsafe { &mut *core::ptr::addr_of_mut!(BUF) };
                match ch.receive(buf) {
                    Ok(t) => self.state = State::Busy(t),
                    Err((_, ch)) => self.state = State::Idle(ch),
                }
                None
            }
            State::Busy(mut t) => {
                if !t.poll() {
                    self.state = State::Busy(t);
                    return None;
                }
                let (n, ch) = match t.wait() {
                    Ok((n, ch)) => (n, ch),
                    Err((_, ch)) => {
                        self.state = State::Idle(ch);
                        return None;
                    }
                };
                self.state = State::Idle(ch);
                // SAFETY: the transaction that borrowed BUF has ended.
                let buf: &[PulseCode; CODES] = unsafe { &*core::ptr::addr_of!(BUF) };
                let mut k = 0;
                for c in buf.iter().take(n.min(CODES)) {
                    if c.length1() == 0 {
                        break;
                    }
                    // WS2812 idles low, so each code is (high, low)
                    let (h, l) = if c.level1() == Level::High {
                        (c.length1(), c.length2())
                    } else {
                        (c.length2(), c.length1())
                    };
                    let low = if l == 0 { LATCH_NS / NS_PER_TICK } else { l as u32 };
                    self.pairs[k] = (h as u32 * NS_PER_TICK, low * NS_PER_TICK);
                    k += 1;
                }
                if k == 0 { None } else { Some(&self.pairs[..k]) }
            }
            State::Gone => None,
        }
    }
}
