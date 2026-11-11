//! The I2C target ("slave") side, address 0x1B.
//!
//! * ESP32-C3 and ESP32-C6: esp-hal 1.2.2's own `I2cSlave` driver (marked
//!   unstable in esp-hal). Its blocking `listen()` would block until the badge
//!   talks, which would freeze the animations, so we use its async
//!   `listen_async()` and poll that future by hand with a no-op waker from the
//!   main loop. No async executor is needed.
//! * ESP32-S3: esp-hal 1.2.2 does not offer `I2cSlave` on the S3, so
//!   [`s3::S3Target`] programs the I2C0 registers directly through the PAC,
//!   following the same register sequence esp-hal uses on the C3/C6. It runs
//!   without clock stretching and is polled the same way.
//!
//! On all three, the internal pull-ups the drivers switch on are switched off
//! again: the badge provides the bus pull-ups, and an internal pull-up to this
//! module's 3.3 V could push current into an unpowered badge (and its coin
//! cell) when the XIAO runs from its own battery.

/// Poll `fut` to completion, calling `idle` between polls. Returns `None` if
/// `give_up` says so first (the future is then dropped, which also disables
/// the driver's interrupt sources).
#[cfg(any(feature = "esp32c3", feature = "esp32c6"))]
pub fn poll_with<F: core::future::Future>(
    fut: F,
    mut idle: impl FnMut(),
    mut give_up: impl FnMut() -> bool,
) -> Option<F::Output> {
    use core::task::{Context, Poll, Waker};
    let mut fut = core::pin::pin!(fut);
    let mut cx = Context::from_waker(Waker::noop());
    loop {
        if let Poll::Ready(v) = fut.as_mut().poll(&mut cx) {
            return Some(v);
        }
        if give_up() {
            return None;
        }
        idle();
    }
}

/// Turn off the internal pull-up of a GPIO pad (the badge has the pull-ups).
pub fn disable_internal_pullup(gpio: usize) {
    // SAFETY: a single read-modify-write of this pad's IO_MUX register; the
    // pad belongs to the I2C driver we just configured and nothing else
    // touches its pull bits afterwards.
    #[cfg(feature = "esp32c3")]
    let io_mux = unsafe { &*esp32c3::IO_MUX::ptr() };
    #[cfg(feature = "esp32c6")]
    let io_mux = unsafe { &*esp32c6::IO_MUX::ptr() };
    #[cfg(feature = "esp32s3")]
    let io_mux = unsafe { &*esp32s3::IO_MUX::ptr() };
    io_mux.gpio(gpio).modify(|_, w| w.fun_wpu().clear_bit());
}

#[cfg(feature = "esp32s3")]
pub mod s3 {
    use esp_hal::{
        Blocking,
        gpio::interconnect::{PeripheralInput, PeripheralOutput},
        i2c::master::{Config, I2c},
        peripherals::I2C0,
    };
    use esp32s3::i2c0::RegisterBlock;

    const FIFO_LEN: usize = 32;

    pub struct S3Target<'d> {
        // Kept alive only for what its constructor did: enable the I2C0 clock,
        // and route SDA/SCL through the GPIO matrix as open-drain pins. We
        // never call a master method on it.
        _clock_and_pins: I2c<'d, Blocking>,
        rx: [u8; FIFO_LEN],
        len: usize,
    }

    fn regs() -> &'static RegisterBlock {
        // SAFETY: I2C0 is owned by `_clock_and_pins`, which nothing else uses.
        unsafe { &*esp32s3::I2C0::ptr() }
    }

    impl<'d> S3Target<'d> {
        pub fn new(
            i2c: I2C0<'d>,
            sda: impl PeripheralInput<'d> + PeripheralOutput<'d>,
            scl: impl PeripheralInput<'d> + PeripheralOutput<'d>,
            address: u8,
        ) -> Self {
            let master = I2c::new(i2c, Config::default())
                .expect("I2C0 init")
                .with_sda(sda)
                .with_scl(scl);

            let r = regs();
            r.int_ena().write(|w| unsafe { w.bits(0) });
            r.ctr().modify(|_, w| {
                w.ms_mode().clear_bit(); // target (slave) mode
                w.sda_force_out().set_bit();
                w.scl_force_out().set_bit();
                w.arbitration_en().clear_bit();
                w.tx_lsb_first().clear_bit();
                w.rx_lsb_first().clear_bit();
                w.rx_full_ack_level().clear_bit();
                w.addr_broadcasting_en().clear_bit();
                // Send whatever is in the TX FIFO when the badge reads.
                w.slv_tx_auto_start_en().set_bit();
                w.clk_en().set_bit()
            });
            r.slave_addr().write(|w| unsafe {
                w.slave_addr().bits(address as u16);
                w.addr_10bit_en().clear_bit()
            });
            r.fifo_conf().modify(|_, w| unsafe {
                w.nonfifo_en().clear_bit();
                w.fifo_prt_en().set_bit();
                w.rxfifo_wm_thrhd().bits(0x1F);
                w.txfifo_wm_thrhd().bits(0)
            });
            r.to().modify(|_, w| unsafe {
                w.time_out_en().set_bit();
                w.time_out_value().bits(14)
            });
            r.sda_hold().write(|w| unsafe { w.time().bits(10) });
            r.sda_sample().write(|w| unsafe { w.time().bits(10) });
            // No clock stretching: 4-byte commands fit the 32-byte FIFO easily,
            // and the main loop drains it every few hundred microseconds.
            r.scl_stretch_conf()
                .modify(|_, w| w.slave_scl_stretch_en().clear_bit());
            r.int_clr().write(|w| unsafe { w.bits(0x3ffff) });
            reset_fifos();
            r.ctr().modify(|_, w| w.conf_upgate().set_bit());

            Self {
                _clock_and_pins: master,
                rx: [0; FIFO_LEN],
                len: 0,
            }
        }

        /// Queue the bytes a badge will get if it reads from us.
        pub fn set_read_data(&mut self, bytes: &[u8]) {
            let r = regs();
            r.fifo_conf().modify(|_, w| w.tx_fifo_rst().set_bit());
            r.fifo_conf().modify(|_, w| w.tx_fifo_rst().clear_bit());
            for &b in bytes {
                r.data().write(|w| unsafe { w.fifo_rdata().bits(b) });
            }
        }

        /// Non-blocking. Returns the bytes of a finished write transaction
        /// (empty after a read transaction), or `None` if nothing finished.
        pub fn poll(&mut self) -> Option<&[u8]> {
            let r = regs();
            let raw = r.int_raw().read();
            if raw.time_out().bit_is_set() || raw.arbitration_lost().bit_is_set() {
                r.int_clr().write(|w| {
                    w.time_out().clear_bit_by_one();
                    w.arbitration_lost().clear_bit_by_one()
                });
                r.fifo_conf().modify(|_, w| w.rx_fifo_rst().set_bit());
                r.fifo_conf().modify(|_, w| w.rx_fifo_rst().clear_bit());
                self.len = 0;
                return None;
            }
            self.drain();
            if raw.trans_complete().bit_is_set() {
                r.int_clr().write(|w| w.trans_complete().clear_bit_by_one());
                self.drain();
                let n = self.len;
                self.len = 0;
                return Some(&self.rx[..n]);
            }
            None
        }

        fn drain(&mut self) {
            let r = regs();
            while r.sr().read().rxfifo_cnt().bits() > 0 {
                let b = r.data().read().fifo_rdata().bits();
                if self.len < FIFO_LEN {
                    self.rx[self.len] = b;
                    self.len += 1;
                }
            }
        }
    }

    fn reset_fifos() {
        let r = regs();
        r.fifo_conf().modify(|_, w| {
            w.tx_fifo_rst().set_bit();
            w.rx_fifo_rst().set_bit()
        });
        r.fifo_conf().modify(|_, w| {
            w.tx_fifo_rst().clear_bit();
            w.rx_fifo_rst().clear_bit()
        });
    }
}
