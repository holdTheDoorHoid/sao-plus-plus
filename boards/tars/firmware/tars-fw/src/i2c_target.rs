//! The I2C target ("slave") side, address 0x27. Taken from Mr. Robot's
//! firmware (boards/mr-robot/firmware/mrrobot-fw/src/i2c_target.rs), without
//! its ESP32-S3 part, which this firmware does not support yet.
//!
//! * ESP32-C3 and ESP32-C6: esp-hal 1.2.2's own `I2cSlave` driver (marked
//!   unstable in esp-hal). Its blocking `listen()` would block until the badge
//!   talks, which would freeze the animations, so we use its async
//!   `listen_async()` and poll that future by hand with a no-op waker from the
//!   main loop. No async executor is needed.
//! On both, the internal pull-ups the drivers switch on are switched off
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
    io_mux.gpio(gpio).modify(|_, w| w.fun_wpu().clear_bit());
}
