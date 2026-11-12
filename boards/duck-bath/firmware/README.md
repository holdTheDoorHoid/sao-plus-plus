# Duck Bath SAO firmware (SAO++ edition)

Firmware for the Duck Bath add-on: a toy duck in a bathtub, lit from behind
by two small colour LEDs. It runs on a Seeed Studio XIAO module, and the same
source is meant to build for all three modules the board takes: **XIAO
ESP32-C3** (the main target), **XIAO ESP32-C6** and **XIAO ESP32-S3**.

## Status: NEVER COMPILED

**This code has not been through a compiler even once.** The machine it was
written on has no Rust toolchain (no `cargo`, no `rustup`), and installing one
was not allowed. That is a step worse than the Hack-Man firmware, which
compiles and passes its tests but has not run on a board. Here:

- nothing has been built, for any chip;
- the 19 tests in `duckbath-core` have never been run. The fading arithmetic
  was re-typed in Python and checked there once (it matches the maker's
  formula within 0.22 % of full scale); that is all the checking there has
  been;
- expect typing mistakes and compiler complaints on the first build. Budget
  time for someone who knows Rust to fix them before trusting any of it.

To keep that risk small:

- `duckbath-fw` (the hardware layer) is the Hack-Man board's `hackman-fw`,
  which does compile, with the smallest changes that would do: the mode
  button is taken out and the I2C replies changed. `leds.rs` and
  `i2c_target.rs` are unchanged apart from comments. The dependency list and
  `Cargo.lock` are Hack-Man's with the two crate names changed by hand.
- `duckbath-core` (the behaviour) is new, about 350 lines without tests, with
  no dependencies and no hardware code.

**This is a new program, not a copy.** The original duckGLOW firmware by
Adrian Studer (<https://github.com/astuder/duckglow>, MIT licence) is C for a
CH32V003 driving one plain LED by PWM. None of it is used here; what is kept
is what the add-on does and its I2C register map, so that code written for a
real duckGLOW should work with this board. No licence has been chosen for
this firmware yet (same open question as for Hack-Man).

## What it does

**On power-up** the duck starts breathing yellow: it fades from dim to bright
and back over about ten seconds, rests at its dimmest for a second, and
repeats (one cycle is 11.5 s). These are the maker's default settings.

**A badge can change it** over I2C at address **0x6C**, with the maker's
register map (below): the brightest and dimmest value, the fading speed and
the starting point of each of red, green and blue. Setting a speed to 0 holds
that colour steady. The duck always shows what the registers say; there is no
time-out and no button.

**The power switch**: in the middle **OFF** position the firmware turns the
LEDs off and puts the module into its deepest sleep. Sliding the switch out
of OFF wakes it and it starts again with the default yellow breath.

Both LEDs always show the same colour: together they stand in for the maker's
single LED.

## I2C registers

Address 0x6C. Write the register address, then data; the address moves on by
one after each data byte. A read returns bytes starting at the address last
written.

| Address | Name | Meaning |
|---|---|---|
| 0x00–0xEB | docs | a short text about the add-on (read-only) |
| 0xEC–0xEF | max | brightest value for red, green, blue, (background) |
| 0xF0–0xF3 | min | dimmest value for red, green, blue, (background) |
| 0xF4–0xF7 | speed | fading speed per channel; 0 = steady at max |
| 0xF8–0xFB | phase | where in the fading cycle each channel starts |
| 0xFC | mode | stored, but has no effect here |
| 0xFD | save | 42 = keep settings (not supported), 24 = back to defaults |
| 0xFE | debug | result of the last save: 0 = fine, 4 = not supported |

The maker's own example works unchanged (Arduino): write `0xEC, 0xFF` then
`0xF4, 0x00` and the red channel goes to full, steady.

### What is different from a real duckGLOW

| Original | Here |
|---|---|
| **WS2812 mode**: the add-on can be driven like one addressable LED through the GPIO2 pin, and notices such a signal by itself | **Not implemented.** GPIO2 is wired to the module but the firmware ignores it. Writing the mode register does nothing |
| **Save (42)** stores the settings in the chip so they survive power-off | **Not implemented.** Settings last until power-off. Writing 42 sets the debug register to 4 |
| **Factory reset (24)** erases the stored settings and restarts the chip | Puts the default settings back at once |
| Address 0x6C–0x6F by solder jumpers | 0x6C only (`ADDRESS` in `duckbath-core/src/registers.rs`) |
| "Background" channel (fourth value in each group) lights duckJAWS's extra LEDs | Stored and readable; drives nothing (duckBATH has no such LEDs either) |
| UV-LED detection (mode bit 4) | Always reads 0 |
| Reading moves the register address on, so a long read can be done in pieces | A read always starts at the address last **written**, and returns at most 16 bytes. To read the docs text, write a new address before each 16-byte read |
| Docs text at address 0 includes a poem | Our own short text. The poem is Ogden Nash's, not the maker's to license, so it is not copied |
| 10-bit brightness steps | 8-bit (what the LEDs take): very dim fades are a little coarser. With the default settings the top of the breath is 79, not 80 |

## Building and flashing

Not yet done by anyone. The steps are Hack-Man's. You need Rust and
`espflash` (`cargo install espflash`). Plug the XIAO into USB-C. Run these
from the `duckbath-fw` folder.

| Module | Build | Build, flash and watch the log |
|---|---|---|
| XIAO ESP32-C3 | `cargo c3` | `cargo flash-c3` |
| XIAO ESP32-C6 | `cargo c6` | `cargo flash-c6` |
| XIAO ESP32-S3 | `cargo +esp s3` | `cargo +esp flash-s3` |

- C3 and C6 use normal (stable) Rust. One-time setup:
  `rustup target add riscv32imc-unknown-none-elf riscv32imac-unknown-none-elf`.
- The S3 needs Espressif's Rust toolchain: `espup install` once, then in each
  new terminal `source ~/export-esp.sh` before building.
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.
- If cargo complains about `Cargo.lock`, delete it and let cargo write a new
  one (it was edited by hand; the exact versions are also in `Cargo.toml`).

First do the tests of the behaviour logic, which need no board:

```
cd duckbath-core
cargo test
```

## Pin map

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| LED data (330 ohm series resistor on the board) | D10 | GPIO10 | GPIO18 | GPIO9 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| SAO GPIO1 (unused, left as input) | D7 | GPIO20 | GPIO17 | GPIO44 |
| SAO GPIO2 (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |

The module's BOOT button is not used. LED 0 on the data line is the one below
the duck hole, LED 1 the one to its left (seen from the front).

## How the code is laid out

- `duckbath-core/` - the behaviour: `registers.rs` (the I2C register map),
  `fader.rs` (the breathing curve), `app.rs` (ties them to the 20 ms clock
  and the power switch), `input.rs` (switch debouncing, from Hack-Man),
  `color.rs`. No hardware code.
- `duckbath-fw/` - the hardware layer, from Hack-Man: `main.rs` (pins, main
  loop, sleep), `leds.rs` (LED signal on the RMT peripheral), `i2c_target.rs`
  (I2C target; esp-hal's driver on the C3/C6, direct register code on the S3).

## What still needs a real board

Everything, after it compiles. The list in the Hack-Man firmware README
applies here item for item (LED timing at 3.3 V, the I2C target on each chip,
internal pull-ups off, deep sleep and wake, the data line held low in sleep,
power use), because the hardware layer is the same. Specific to this board:

1. **Register reads.** A badge normally writes a register address and reads
   straight after, without releasing the bus in between. Whether esp-hal's
   I2C target driver reports that as a write followed by a read (which this
   firmware expects) has not been tried. If it does not, reads return data
   from the wrong address; writes are not affected.
2. **On the S3**, the read data is queued ahead of time and queued again
   after every finished transaction. That hand-written register code is the
   least-backed part, as on Hack-Man.
3. **Two LEDs, 49 pulse codes per frame**: one more than fits the RMT's
   memory block, so the driver's refill path is used, as on Hack-Man.
4. **Brightness in the duck**: the default yellow tops out at 80 of 255. Raise
   the `max` registers (or `Settings::DEFAULT`) if it is too dim behind the
   hole.

## Coin-cell safety

As on Hack-Man: in the USB-BAT switch position the module runs from its own
power while the badge's I2C wires are still connected, so the firmware turns
the module's internal pull-ups on SDA and SCL off right after starting the
I2C driver. Confirm with a meter.
