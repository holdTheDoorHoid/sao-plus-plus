# duckGLOW SAO firmware (SAO++ edition: Duck Bath and Duck Jaws)

Firmware for the two duckGLOW add-ons: **Duck Bath** (an RGB LED under a
rubber duck) and **Duck Jaws** (the same, plus red "background" LEDs round a
shark's mouth). One source for both boards and for all three modules the
boards take: **XIAO ESP32-C3** (the main target), **ESP32-C6** and **ESP32-S3**.

**Credit and licence.** The boards, the badge protocol and the behaviour are by
**Adrian Studer (astuder)**, <https://github.com/astuder/duckglow>, released
under the MIT licence:

> MIT License — Copyright (c) 2024 Adrian Studer (full text in `../original/LICENSE.md`)

His firmware (C, for the CH32V003 chip) is in `../original/code/`. This
firmware is a **clean re-implementation in Rust of what his firmware does**,
written from reading it, not a line-by-line port. It is MIT-licensed too, with
his copyright notice kept above. `duckglow-fw/src/i2c_target.rs` is shared
with the SAO++ Mr. Robot firmware.

> **Status: this firmware has NEVER run on hardware.** It compiles for all
> three modules and both boards, and the behaviour logic passes 43 automatic
> tests on a PC, but no SAO++ duck board exists yet. See
> [What still needs a real board](#what-still-needs-a-real-board).

## What it does (as on the maker's board)

**At power-on** the duck breathes: red and green fade slowly up to about a
third of full brightness and back (one breath about 11.5 s), blue stays off,
so the duck glows a warm yellow-orange. On Duck Jaws the red background LEDs
breathe at full brightness, half a breath out of step. These are the maker's
defaults. If settings were saved (below), those are used instead.

**The badge can change everything over I2C**: per colour, the brightest and
dimmest point of the breath, its speed (0 = steady, no breathing) and its
phase. Settings can be saved so they come back at the next power-on.

**Or the badge can drive the duck like an addressable LED** (WS2812 /
"NeoPixel") on SAO GPIO2: as soon as WS2812 data arrives, the duck shows the
colour sent and stops breathing; the next I2C write hands control back. Send
two LEDs' worth: LED 0's blue byte sets the background channel (Duck Jaws),
LED 1 sets the duck.

**The power switch** in the middle **OFF** position darkens the LEDs and puts
the module into deep sleep; sliding it out of OFF starts again from power-on.

There is no mode button: the maker's board has none, and the module's BOOT
button is left alone.

## I2C

7-bit address **0x22** (Duck Bath) / **0x23** (Duck Jaws), the SAO++ house
numbering. Build with `--features maker-address` for the maker's **0x6C**
(his boards could also be set to 0x6D–0x6F with solder jumpers; the SAO++
boards have none).

The register map is the maker's, unchanged:

| Register | What |
|---|---|
| 0x00–0xEB | text about the add-on (read only) |
| 0xEC–0xEF | max brightness: red, green, blue, background |
| 0xF0–0xF3 | min brightness, same order |
| 0xF4–0xF7 | fading speed (0 = steady at max) |
| 0xF8–0xFB | phase (where in the breath each colour starts) |
| 0xFC | mode: bits 0–1 = 0 auto, 1 I2C only, 2 WS2812 only; bit 4 = UV LED fitted (read only) |
| 0xFD | write 42: save the settings (0xEC–0xFC) for power-on; write 24: factory settings and restart |
| 0xFE | result of the last save: 0 ok, 1 no saved settings, 2 flash error, 3 nothing changed |

A write is the register number followed by data; the register number counts
up by one per byte. A read starts at the register last written. Example
(MicroPython on a badge): `i2c.writeto(0x22, bytes([0xEC, 255]))` and
`i2c.writeto(0x22, bytes([0xF4, 0]))` make the duck steady full red. The
maker's own badge examples in `../original/examples/` work after changing the
address (or with `maker-address`).

**Differences from the maker's board** (each deliberate, each small):

- **The text at 0x00.** His board carries a short poem by another author
  there; it is not copied. This edition's text names the board, the maker, the
  repository and the register map.
- **Reads do not move the register number on.** His board counts it up after
  a read too. The ESP32's I2C hardware does not tell the firmware how many
  bytes the badge actually read, so a read always starts at the register last
  written. All the maker's examples write the register number before each
  read, so they are unaffected.
- **UV LED.** His board tested at power-on whether an RGB or a UV LED was
  fitted, by reading the red pin through a pull-down. The ESP32's input
  thresholds make that test unreliable, so here it is a build option:
  `--features uv` for a board with a UV LED in the blue position.
- **WS2812 frames longer than 8 LEDs.** His board keeps the *last* colours of
  a frame of any length; this one sees the first 192 bits (8 LEDs). A badge
  driving the duck as a 2-LED strip, as in his examples, is unaffected.
- **Saved settings** live in the last 4 KB of the module's flash, in this
  firmware's own format; settings saved on a maker's board do not carry over.
- **Fading the other way.** If min is above max, the colour breathes downwards
  instead of doing what the maker's arithmetic happened to do.

## Pins

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| red (low = on, PWM) | D10 | GPIO10 | GPIO18 | GPIO9 |
| green (low = on, PWM) | D8 | GPIO8 | GPIO19 | GPIO7 |
| blue (low = on, PWM) | D7 | GPIO20 | GPIO17 | GPIO44 |
| background, Duck Jaws only (low = on, PWM) | D0 | GPIO2 | GPIO0 | GPIO1 |
| I2C SDA / SCL | D4 / D5 | GPIO6 / 7 | GPIO22 / 23 | GPIO5 / 6 |
| power switch OFF sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| SAO GPIO2: WS2812 data in | D6 | GPIO21 | GPIO16 | GPIO43 |

SAO GPIO1 is not connected on these boards. The LED PWM runs at 20 kHz with
10-bit steps (the maker's resolution) on the chip's LEDC peripheral; the
WS2812 input uses the RMT receiver (100 ns steps, a frame ends after 6 µs of
quiet, as on the maker's board).

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C (switch on USB, and **not on a badge** if the switch is on SAO). From
the `duckglow-fw` folder:

| Module | Build | Build, flash and watch the log |
|---|---|---|
| XIAO ESP32-C3 | `cargo c3` | `cargo flash-c3` |
| XIAO ESP32-C6 | `cargo c6` | `cargo flash-c6` |
| XIAO ESP32-S3 | `cargo +esp s3` | `cargo +esp flash-s3` |

Duck Bath is the default. **For Duck Jaws add `--features jaws`**, for example
`cargo flash-c3 --features jaws`. Other options: `--features maker-address`
(answer at 0x6C), `--features uv` (UV LED). The start-up log line names the
board, chip and address.

- C3 and C6 build on normal (stable) Rust; the S3 needs Espressif's toolchain
  (`espup install`, then `source ~/export-esp.sh`). The S3 build prints one
  linker notice about "RWX permissions": not an error.
- If the module does not show up for flashing, hold BOOT while plugging in.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.

Tests of the behaviour logic run on any PC:

```
cd duckglow-core
cargo test                    # Duck Bath
cargo test --features jaws    # Duck Jaws
```

## How the code is laid out

- `duckglow-core/` (no hardware code, 43 tests): `regs.rs` the register map;
  `fader.rs` the breathing; `curve.rs` + `build.rs` the breathing curve,
  computed from the formula; `ws2812.rs` turning pulse lengths into colours;
  `presets.rs` the saved-settings format; `app.rs` everything tied together
  (modes, saving, the power switch); `input.rs` debouncing (an unchanged copy
  of Mysterio's / Mr. Robot's).
- `duckglow-fw/`: the thin hardware layer: `leds.rs` (LEDC PWM),
  `ws_rx.rs` (RMT receiver), `presets_flash.rs` (flash, via `esp-storage`),
  `i2c_target.rs` (shared with Mr. Robot), `main.rs` (pins, main loop, sleep).
- Dependencies: the same pinned set as Mr. Robot, plus `esp-storage 0.10.0`
  (the version that goes with esp-hal 1.2.2) for saving settings.

## What still needs a real board

1. **Anything at all**: LEDs breathing at power-on on each module type.
2. **Colours the right way round** (red on D10, green on D8, blue on D7) and
   dark when told 0 (the pins are inverted: low = on).
3. **I2C target**: answers at 0x22 / 0x23; the maker's example scripts work;
   reading the text at 0x00 in one 236-byte read.
4. **Saving**: write 42, power off and on, settings come back; write 24
   restores the defaults.
5. **WS2812 input**: the maker's `demo-ws2812.py` drives the duck.
6. **Deep sleep on OFF** and waking when the switch leaves OFF.
7. **Current from a badge** (see the board README): under 50 mA all white.
8. **C3 start-up with the green LED on D8** (a start-up pin): normal boot and
   flashing still work.
9. **Internal I2C pull-ups really off** (SDA/SCL float with no badge).
