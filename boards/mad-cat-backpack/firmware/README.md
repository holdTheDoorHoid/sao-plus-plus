# Mad Cat Backpack firmware (SAO++ edition)

Firmware for the Mad Cat Backpack: it animates the eight white LEDs behind a
Mad Cat's eyes and teeth. It runs on a Seeed Studio XIAO module, and the same
source builds for all three modules the board takes: **XIAO ESP32-C3** (the
main target), **XIAO ESP32-C6** and **XIAO ESP32-S3**.

**Credit and licence.** The light show is the maker's: **Peter Shabino
(Wireb)**, `mad_cat_backpack_v0.asm` (PIC16F1503 assembly, version V1 of
04 Nov 2018) in <https://github.com/Wireb/Mad_Cat_Backpack>, also in
`../original/mplab/`. His work is MIT-licensed:

> Copyright (c) 2018 Peter Shabino. Permission is hereby granted, free of
> charge, to any person obtaining a copy of this hardware, software, and
> associated documentation files (the "Product"), to deal in the Product
> without restriction, including without limitation the rights to use, copy,
> modify, merge, publish, distribute, sublicense, and/or sell copies of the
> Product, and to permit persons to whom the Product is furnished to do so,
> subject to the following conditions: The above copyright notice and this
> permission notice shall be included in all copies or substantial portions of
> the Product. THE PRODUCT IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
> EXPRESS OR IMPLIED (full text: `../original/LICENSE`).

This firmware is a **re-implementation in Rust of what his program does**,
written from a reading of it (which LEDs, what levels, in what order, for how
long, with which random choices), not a line-by-line translation. Both crates
carry the MIT licence too. The modes, button, power switch handling and I2C
commands are new.

> **Status: this firmware has NEVER run on hardware.** It builds for all three
> modules and its behaviour passes 37 automatic tests on a PC, but no SAO++
> Mad Cat Backpack exists yet. See
> [What still needs a real board](#what-still-needs-a-real-board).

## What it does

**At power-on**, like the maker's board: the six teeth (the smile) fade in,
then after a random pause of 0.13 to 8.3 s the two eyes fade in.

**Mode 0, the maker's show (default).** Over and over: all eight LEDs stay
full on for a random 0 to 33 s, then one of his eight animations plays:

| # | Animation | What you see |
|---|---|---|
| 0 | smile out and in | eyes fade out; pause; smile fades out; pause (2 to 33 s, all dark); smile fades in; pause; eyes fade in |
| 1 | blink | one eye, the other, or both close for 25 ms to 1 s |
| 2 | lick right | a dim spot runs along the teeth from left to right (as seen from the front) |
| 3 | lick left | the same, right to left |
| 4 | piano teeth | tooth 5 fades out and in, then the even and odd teeth take turns fading, 1 to 7 times |
| 5 | eye bobble | the left eye fades out and in, then the right, 1 to 7 times |
| 6 | talking | the outer teeth, then the next pair in, pulse like a talking mouth, 1 to 7 times |
| 7 | sparkles | every LED jumps to a random brightness, up to 256 times in quick succession, then all full on |

They are chosen at random with his weights: out of 32 draws, blink 10,
lick right 4, lick left 4, eye bobble 4, smile 3, piano 3, talking 3,
sparkles 1. His random-number generator is reproduced exactly (same 32-bit
shift register, same starting value, same order of draws), so a board running
this firmware shows the same sequence after power-on that his did.

**The mode button** is the small **BOOT** button on the XIAO. Each short press
moves to the next mode; after the last it starts again at mode 0:

| Mode | What you see |
|---|---|
| 0 (default) **Show** | The maker's show, above. Pressing into it restarts from the power-on fade. |
| 1 **Parade** | All eight animations in his order, one second apart, round and round. Good for checking every LED. |
| 2 **Still** | All eight on, steadily: the cat's resting face. |

**The power switch** has three positions. In the middle **OFF** position the
firmware puts all LEDs dark and the module into its deepest sleep. Sliding the
switch out of OFF wakes it and it starts again from the power-on fade in mode 0.

**The badge can take over** over I2C (below). After the badge's last valid
command, the board waits 5 s and then goes back to its own mode. Pressing the
mode button also takes control back.

### Where this differs from the maker's board (on purpose, and small)

- **The wait between animations.** His readme says "between 0 and 8
  minutes". His code waits a random number (0 to 255) of ticks of a 131 ms
  timer, at most about 33 s. This firmware follows the code.
- **Tick lengths.** His short delays count 8.192 ms ticks and his long waits
  131.072 ms ticks, from his chip's 16 MHz clock; on his chip the first tick of
  each delay can come up a little short. Here every tick is full length.
- **Dimming.** He used a 16-step brightness table; it is used unchanged. His
  chip lit an LED for (level + 1) of every 256 counts; here it is level of 255.
  The biggest difference is one count at the dimmest step: invisible.

## Which XIAO?

Any of the three. The C3 is the main target and the most frugal on badge power.
All three build from this one folder; you choose the chip when you build. Use
the matching command below for the module actually soldered to your board:
firmware for one chip will not run on another.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C (switch on USB/BAT, and **not on a badge** if the switch is on SAO). Run
these from the `backpack-fw` folder.

| Module | Build | Build, flash and watch the log |
|---|---|---|
| XIAO ESP32-C3 | `cargo c3` | `cargo flash-c3` |
| XIAO ESP32-C6 | `cargo c6` | `cargo flash-c6` |
| XIAO ESP32-S3 | `cargo +esp s3` | `cargo +esp flash-s3` |

- C3 and C6 use normal (stable) Rust. One-time setup:
  `rustup target add riscv32imc-unknown-none-elf riscv32imac-unknown-none-elf`.
- The S3 needs Espressif's Rust toolchain: `espup install` once, then in each
  new terminal `source ~/export-esp.sh` before building.
- To flash a file you already built, without the shortcuts:
  `espflash flash --chip esp32c3 target/riscv32imc-unknown-none-elf/release/backpack-fw`
  (C6: `--chip esp32c6 target/riscv32imac-unknown-none-elf/release/backpack-fw`;
  S3: `--chip esp32s3 target/xtensa-esp32s3-none-elf/release/backpack-fw`).
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.
- The S3 build prints one linker notice ("LOAD segment with RWX
  permissions"). It is a notice about the memory layout esp-hal uses, not an
  error.

Tests of the behaviour logic run on any PC, no board needed:

```
cd backpack-core
cargo test
```

## Pin map

LED numbers are the maker's order: 0 = left eye, 1 = right eye, 2..7 = teeth
1 to 6 from left to right, all as seen from the front of the cat. Every LED is
wired 3.3 V → 330 Ω → LED → pin, so **a pin driven low lights its LED**.

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| LED 0, left eye (D1) | D8 | GPIO8 | GPIO19 | GPIO7 |
| LED 1, right eye (D2) | D7 | GPIO20 | GPIO17 | GPIO44 |
| LED 2, tooth 1 (D3) | D9 | GPIO9 (also BOOT) | GPIO20 | GPIO8 |
| LED 3, tooth 2 (D4) | D10 | GPIO10 | GPIO18 | GPIO9 |
| LED 4, tooth 3 (D5) | D0 | GPIO2 | GPIO0 | GPIO1 |
| LED 5, tooth 4 (D6) | D2 | GPIO4 | GPIO2 | GPIO3 |
| LED 6, tooth 5 (D7) | D3 | GPIO5 | GPIO21 | GPIO4 |
| LED 7, tooth 6 (D8) | D6 | GPIO21 | GPIO16 | GPIO43 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| Mode button = module's BOOT button (active low) | BOOT | GPIO9 (shared with tooth 1) | GPIO9 | GPIO0 |

On the **C3** the BOOT button and tooth 1 share GPIO9. That pin is driven
open-drain (it only ever pulls low, so pressing the button can never short a
pin that is driving high), and once per dimming frame (every 7.65 ms) the pin
is let go for 5 µs and read: low means the button is pressed. Pressing it also
lights tooth 1, which is harmless.

## How the dimming works

The XIAO's LED-dimming hardware has six channels on the C3 and C6, two short
of eight, so the firmware dims the LEDs itself, as the maker's PIC did. Each 7.65 ms frame is cut into eight slices of 30, 60, 120 ... 3840 µs;
in slice *b* an LED is on if bit *b* of its brightness is set, so it is on for
exactly its brightness out of 255. That needs only eight pin changes per frame.
About 130 frames a second: no visible flicker (his board managed about 117).
The work is done from the main loop, which also polls the I2C bus; a badge
transfer can stretch one slice by a fraction of a millisecond.

## I2C commands

The add-on is an I2C target at 7-bit address **0x24** (house numbering). The
2018 backpack had no I2C, so there is no maker's protocol to keep; this one is
the house style of the SAO++ boards with single-colour LEDs (Do Or Donut,
0x1C), with one extra command. The badge supplies the pull-up resistors; the
firmware switches the module's own pull-ups off.

Every command is 4 bytes; several can go in one write, back to back.

| Bytes | Meaning |
|---|---|
| `[0x10, n, level, x]` | Cue LED *n* (0..7, order above) at *level* (0 = off, 255 = full). Not shown until latched. |
| `[0x11, level, x, x]` | Cue all eight LEDs at *level*. Not shown until latched. |
| `[5, x, x, x]` | Clear all cues (to off). Not shown until latched. |
| `[6, x, x, x]` | Latch: show the cued LEDs. |
| `[7, brightness, x, x]` | Brightness for cued LEDs, 0 = off, 255 = full. Takes effect at once. Starts at 255. |
| `[0x90, n, level, x]` | Like `0x10`, but ignores the brightness setting. |
| `[0x91, level, x, x]` | Like `0x11`, but ignores the brightness setting. |
| `[8, mode, x, x]` | Stop taking over and run built-in mode 0..2 (table above). |
| `[9, animation, x, x]` | **New:** play the maker's animation 0..7 (table above) now, then carry on with the board's own mode. Does not take over. |

Any LED command (0x10, 0x11, 5, 6, 7, 0x90, 0x91) puts the board under the
badge's control, starting from all LEDs off. Anything else is ignored and does
not count as activity: unknown first bytes, LED numbers 8 and up, modes 3 and
up, animations 8 and up, and a leftover of fewer than 4 bytes.

Example (MicroPython on the badge): `i2c.writeto(0x24, bytes([9, 6, 0, 0]))`
makes the cat talk; `i2c.writeto(0x24, bytes([0x11, 0, 0, 0, 0x10, 0, 255, 0, 6, 0, 0, 0]))`
leaves only the left eye lit.

### Reading

Reading from the add-on returns 4 bytes:

| Byte | Meaning |
|---|---|
| 1 | firmware version, major (0) |
| 2 | firmware version, minor (1) |
| 3 | who is in charge: 0, 1, 2 = the add-on, in that mode; 0x80 = the badge |
| 4 | the maker's animation playing right now (0..7), or 0xFF for none (waiting, still, or the power-on fade) |

On the S3 the answer can be a few milliseconds out of date.

## How the code is laid out

- `backpack-core/`: everything about *behaviour*, with no hardware code,
  tested on a PC (37 tests):
  - `lfsr.rs`: the maker's random-number generator, checked against a
    byte-by-byte model of how his PIC does it;
  - `show.rs`: his brightness table, his 32-entry choice table and his eight
    animations, built as lists of (levels, how long) frames;
  - `dim.rs`: the slice plan for the software dimming;
  - `i2c.rs`: the badge commands;
  - `app.rs`: modes, button and switch, badge control and time-out;
  - `input.rs`: debouncing (an unchanged copy of Mysterio's and Mr. Robot's).
- `backpack-fw/`: the thin hardware layer: pins (`main.rs`), the LED pins and
  dimming (`leds.rs`), the I2C target (`i2c_target.rs`), sleep.

**What is copied from Mr. Robot** (so fixes found on one board can be carried
to the other; compare with `diff`):

| File | Compared with Mr. Robot |
|---|---|
| `.gitignore` | identical |
| `backpack-fw/build.rs` | identical |
| `backpack-fw/rust-toolchain.toml` | identical |
| `backpack-fw/.cargo/config.toml` | identical |
| `backpack-core/src/input.rs` | identical |
| `backpack-fw/Cargo.lock` | same dependency versions; only the two crate names differ |
| `backpack-fw/Cargo.toml`, `backpack-core/Cargo.toml` | same pinned versions and chip features; names, descriptions and licence differ; no `maker-address` feature (the maker's board had no I2C address) |
| `backpack-fw/src/i2c_target.rs` | the address in the first comment line |
| `backpack-fw/src/main.rs` | same I2C, sleep and panic handling; the pins and the sounder are replaced by the eight LEDs |
| `backpack-fw/src/leds.rs`, everything else in `backpack-core/src/` | this board's own |

Choices carried over from Mysterio, Mr. Robot and Hack-Man: bare-metal
`esp-hal` 1.2.2 (no ESP-IDF, stable Rust on C3/C6); esp-hal's I2C target driver
on the C3/C6, stepped by hand from the main loop; the S3's I2C target
programmed register by register because esp-hal has no I2C target driver for
the S3; exact dependency versions pinned; Wi-Fi and Bluetooth never started; the
chip runs at 80 MHz and restarts itself if the firmware ever crashes.

## What still needs a real board

**None of this firmware has run on hardware.** Each item below is something
only a real board can confirm:

1. **Every LED lights, in the right place.** Use mode 1 (Parade): smile fade
   first, then blink, lick right (left to right as seen from the front), lick
   left, piano, eye bobble (left eye first), talking, sparkles. A lick running
   the wrong way, or the wrong eye bobbing first, means a pin-map mistake.
2. **No flicker** at any brightness, also while a badge talks to it over I2C,
   on each module type.
3. **The BOOT button on the C3** (shared with tooth 1): presses are seen,
   tooth 1 still dims smoothly, and holding BOOT while plugging in still enters
   the flasher.
4. **Start-up pins.** On the C3, D0, D8 and D9 are start-up ("strapping")
   pins with an LED on them; the module must still start normally from a badge,
   from USB and from a LiPo. On the C3 and S3, tooth 6 (D6) is the serial-console
   pin and may flicker at start-up: harmless.
5. **Current from a badge**, all LEDs on: under 50 mA (a USB power meter on
   USB/LiPo gives a first idea; on the badge, measure the SAO 3.3 V line).
6. **I2C target on the C3/C6** (esp-hal's unstable driver): it answers at
   0x24, takes the commands above, and its clock stretching is tolerated by the
   badge. **On the S3** (our own register code): everything, including reads.
7. **Internal I2C pull-ups really off** on all three (measure SDA/SCL with the
   badge unplugged: they should float, not sit at 3.3 V).
8. **Deep sleep and wake on each chip**: OFF goes dark and sleeps, the
   pull-down on D1 holds during sleep, sliding out of OFF wakes the module, and
   the LEDs stay dark through sleep (their pins are held high) and work again
   after wake.
9. **Badge power into the XIAO's 3V3 pin** (see `../README.md`): a board
   question rather than a firmware one, but the first thing to check.
10. **Serial log** goes to the USB port (the XIAO's TX/RX pins D6/D7 drive
    LEDs here).
