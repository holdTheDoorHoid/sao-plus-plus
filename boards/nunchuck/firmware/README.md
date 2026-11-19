# SAO Nunchuck — badge-side driver (Rust)

The SAO Nunchuck has **no chip of its own**, so there is no firmware to put *on* it. The badge's processor reads the
Wii Nunchuk directly over the SAO connector's I2C wires. What this folder holds is the other half: a small Rust
library, `nunchuck-driver/`, that a **badge's** firmware links to read the Nunchuk.

It is a plain `no_std` library that works with any badge whose Rust support speaks
[embedded-hal 1.0](https://docs.rs/embedded-hal/1.0.0) (esp-hal, rp-hal, embassy, stm32 HALs and so on). It needs an
I2C bus and a delay, nothing else.

> **Status: never run against a real Nunchuk.** It compiles for a PC and for a bare RISC-V microcontroller target,
> and 15 automatic tests pass against a simulated Nunchuk. No SAO++ Nunchuck board exists yet.

## What it does

| Step | Call | What happens on the wire |
|---|---|---|
| Wake the Nunchuk | `Nunchuk::init` | writes `0x55` to register `0xF0`, waits 1 ms, writes `0x00` to register `0xFB`, waits 1 ms. This is the "plain" start-up that works on genuine and clone Nunchuks alike |
| Check what is plugged in | `Nunchuk::identify` | reads the 6-byte id from register `0xFA`; a Nunchuk answers `00 00 A4 20 00 00`. Anything else (a Classic Controller, a guitar) is reported as "not a Nunchuk" |
| Read it | `Nunchuk::read` | points at register `0x00`, waits 200 µs, reads 6 bytes and decodes them |

A reading gives: stick left/right and down/up (0–255, about 128 at rest), the three motion-sensor axes (0–1023,
about 512 when level), and buttons **C** and **Z**.

Helpers for games and menus:

- `Stick` turns the stick into signed steps with a dead band round the rest position, so a stick that does not
  quite centre reads as still. `Stick::calibrate` takes the rest position from a reading made hands-off.
  `Stick::direction` gives up / down / left / right for menus.
- `Buttons::between(previous, now)` reports "C pressed", "Z released" and so on, so a badge acts once per press.

Errors are kept simple: the bus failed (usually: nothing plugged in), the Nunchuk answered all `0xFF` (it needs
`init` again, typically after being unplugged and plugged back in), or something else is plugged in.

The address is **0x52**, fixed by the Nunchuk. The board has no chip, so the SAO++ house address scheme (and a
`maker-address` option) does not apply.

## Example (badge side)

```rust
use nunchuck_driver::{Buttons, Nunchuk, Stick};

let mut chuck = Nunchuk::new(i2c);          // the badge's I2C bus on the SAO connector
chuck.init(&mut delay)?;
chuck.identify(&mut delay)?;                // optional: is it really a Nunchuk?
let mut last = chuck.read(&mut delay)?;
let mut stick = Stick::default();
stick.calibrate(&last);                     // stick untouched at start-up
loop {
    let now = chuck.read(&mut delay)?;
    if Buttons::between(&last, &now).z_pressed { /* fire! */ }
    if let Some(dir) = stick.direction(&now) { /* move the cursor */ }
    last = now;
    delay.delay_ms(10);                     // ~100 readings a second is plenty
}
```

## What the maker's code does, and what this is

The maker's folder has one sketch, `original/Firmware/SAO_Nunchuck_RP2040_W_Arduino_Demo/`, for an RP2040 acting as
the **badge**: it starts the Nunchuk with the NintendoExtensionCtrl Arduino library and prints the Z button, the stick's
Y axis and the X motion axis to the serial port (with an optional OLED screen). It shows that the board is meant to be
read by the badge, which is what this driver does. The driver is written from the widely documented Wii-extension
report layout, not ported from that sketch or from either Arduino library; `a_badge_loop_end_to_end` in the tests
does what his demo does.

**Credit and licence.** The SAO Nunchuck hardware and demo are by Andy and Jared Geppert (ageppert, Machine Ideas),
MIT licence, *Copyright (c) 2024 Andrew Geppert* (full text in [../original/LICENSE.md](../original/LICENSE.md)). This
driver is released under the same MIT licence.

## Building and testing

```
cd nunchuck-driver
cargo test                                                         # 15 tests, on the PC
cargo build --release --target riscv32imc-unknown-none-elf         # proves it builds with no standard library
```

Do not turn on `incremental` builds on this machine (it uses sccache).

## What still needs a real board

1. That 200 µs between "point at register 0" and "read" is enough for genuine and clone Nunchuks on a badge's bus;
   some clones are slower. If readings come back all `0xFF` or stale, raise `CONVERSION_DELAY_US`.
2. Bus speed: the Nunchuk is happiest at 100 kHz. Badges that run their SAO bus at 400 kHz should be tried.
3. Unplug / replug while the badge is running: the driver reports `NotReady`, and the badge should call `init`
   again.
