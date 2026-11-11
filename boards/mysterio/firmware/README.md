# Mysterio SAO firmware (SAO++ edition)

Firmware for the Mysterio add-on: four colour-changing lights round the rim of
Mysterio's glass helmet, shining across the back of the board so the helmet
glows. It runs on a Seeed Studio XIAO module, and the same source builds for
all three modules the board takes: **XIAO ESP32-C3** (the main target),
**XIAO ESP32-C6** and **XIAO ESP32-S3**.

**Credit.** The board and its default light show are by **davedarko (Dave
Darko)**, <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/MysterioSAO>.
His own Arduino sketch for it is in `../original/Sketchbook/strandtest/`. This
firmware is a **clean re-implementation in Rust of what his sketch does**, not
a port of his code: it was written from a reading of the sketch's behaviour,
and the rest (modes, I2C, sleep) is new. The permission notice in
`../README.md` applies to this board.

**Status: built, not yet tried on a board.** All three versions compile and
the behaviour logic passes 55 automatic tests on a PC, but no SAO++ Mysterio
board exists yet. Nothing here has been seen working on real hardware. See
[What still needs a real board](#what-still-needs-a-real-board).

This firmware is a sister of the Hack-Man firmware
(`../../hack-man/firmware/`): same module, same pins, same I2C command set, and
most of the hardware code is an unchanged copy (list below).

## What it does

**At power-on** all four lights glow pale blue-white for one second. Then the
default show starts.

**The mode button** is the small **BOOT** button on the XIAO module itself.
Each short press moves to the next mode, and after the fourth it starts again
at the first:

| Mode | What you see |
|---|---|
| 0 (default) | **The maker's icy shimmer.** Every 40 ms one light changes colour, going round the four in turn, picking from his 12 shades of deep blue, cyan and white. After each round it jumps to a new random starting shade, so the helmet keeps flickering like cold light in a glass bowl. |
| 1 | **Fishbowl mist:** a slow green glow that breathes in and out (6 s per breath), each light a quarter-breath behind the last, so it seems to swirl round the bowl. Never fully dark. |
| 2 | **Slow rainbow:** all four drift round the colour wheel together (16 s per lap), each slightly ahead of its neighbour. |
| 3 | **All off.** The board stays awake (and still obeys the badge); use the OFF switch position to really switch off. |

**The power switch** has three positions. In the middle **OFF** position the
firmware turns all lights off and puts the module into its deepest sleep.
Sliding the switch out of OFF wakes it up and it starts again from the
power-on glow in mode 0 (it does not remember the last mode).

**The badge can take over the lights** over I2C (details below). As soon as
the badge sends a valid command the add-on stops its own show and displays
what the badge asks for. If the badge goes quiet for 5 seconds the add-on goes
back to its own show. Pressing the mode button also takes control back.

### Mode 0 compared with the maker's sketch

What his sketch does, checked line by line against `strandtest.ino`, and
reproduced here:

- Brightness 200 out of 255, applied the way his LED library does it (each
  colour value times 201, divided by 256: full 255 becomes 200).
- A 12-shade palette from deep blue (#000b2d) through cyan to white (#ffffff).
- A counter starts at 0. Every 40 ms the next light (1, 2, 3, 4, starting
  with the right-hand light seen from the front) is repainted with shade
  number (light number + counter), wrapping round at 12, and the counter goes
  up by one. The other lights keep their colour. The lights start dark and
  fill in over the first 160 ms.
- After each round of four the counter jumps to a random number from 0 to 7.
- Because the counter goes up once per light, each round shows a gradient
  two shades apart from light to light.

Differences (all small):

- **Two shades are off by one from his own notes.** His comment lists the hex
  colours #00345a and #00bec6, but his code sends green 53 and 191 (the hex
  values are 52 and 190). This firmware sends what his code sends: 53 and 191.
- **Random numbers.** His sketch never seeds the random generator, so his
  board replays the same "random" sequence after every power-up. This one
  does too (a fixed seed), but it is a different sequence, from a different
  generator.
- **Timing.** His step is 40 ms plus the time to send the colours (well under
  1 ms); this one is exactly 40 ms.
- **The brightness cap** below is applied on top of his 200/255.

### Brightness

On top of everything (boot glow, all modes, and colours the badge sends) the
firmware applies a fixed **brightness cap of 96 out of 255, about 38 %**
(`GLOBAL_BRIGHTNESS_CAP` in `mysterio-core/src/lib.rs`). In mode 0 that comes
to about 30 % of the LEDs' full output (96/255 times his 200/255). Why: the
lights run from 3.3 V (the badge, the XIAO's own regulator, or a hand-soldered
LiPo), below the LEDs' rated 3.7 V, and four of them at full white would be a
real load on a badge. It cannot be as low as Hack-Man's 48, because here the
light has to shine through the board. It is a first guess: tune it by eye on a
real board. The mist green and boot glow colours (`palette` in the same file)
are first guesses too.

## Which XIAO?

Any of the three. The C3 is the main target. All three build from this one
folder; you choose the chip when you build. Use the matching command below for
the module actually soldered to your board: firmware for one chip will not run
on another.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C (switch on USB, and **not on a badge** if the switch is on SAO). Run
these from the `mysterio-fw` folder.

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
  `espflash flash --chip esp32c3 target/riscv32imc-unknown-none-elf/release/mysterio-fw`
  (C6: `--chip esp32c6 target/riscv32imac-unknown-none-elf/release/mysterio-fw`;
  S3: `--chip esp32s3 target/xtensa-esp32s3-none-elf/release/mysterio-fw`).
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.
- The S3 build prints one linker notice ("LOAD segment with RWX
  permissions"). It is a notice about the memory layout esp-hal uses, not an
  error.

Tests of the behaviour logic run on any PC, no board needed:

```
cd mysterio-core
cargo test
```

## Pin map

Identical to Hack-Man.

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| LED data (330 ohm series resistor on the board) | D10 | GPIO10 | GPIO18 | GPIO9 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| Mode button = module's BOOT button (active low; internal pull-up) | BOOT | GPIO9 | GPIO9 | GPIO0 |
| SAO GPIO1 (unused, left as input) | D7 | GPIO20 | GPIO17 | GPIO44 |
| SAO GPIO2 (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |

LED chain order: the first LED on the data line (index 0, board part D1) is
the **right-hand** LED of the helmet seen from the front (lower right). Indices
1, 2, 3 (D2, D3, D4) go on round to the left. This is the same order the
maker's sketch counts them in. The LEDs are SK6805-EC3210R (WS2812-style,
green-red-blue byte order, 800 kHz).

## I2C commands

The add-on is an I2C target at 7-bit address **0x1B**. It uses exactly the
same commands as Hack-Man (address 0x1A), so one badge driver works for both,
and the two can sit on one badge together. The badge supplies the pull-up
resistors; the firmware switches the module's own pull-ups off. Every command
is 4 bytes; one write may contain several commands back to back.

| Bytes | Meaning |
|---|---|
| `[0..3, R, G, B]` | Cue a colour for LED 0..3 (0 = right-hand LED from the front). Not shown until latched. |
| `[5, x, x, x]` | Clear all cued colours (to black). Not shown until latched. |
| `[6, x, x, x]` | Latch: show the cued colours. |
| `[7, brightness, x, x]` | Brightness for cued colours, 0 = off, 255 = full. Takes effect at once. Starts at 255 (see below). |
| `[128..131, R, G, B]` | Cue a colour for LED (first byte - 128) that ignores the brightness setting. |

Anything else is ignored and does not keep I2C mode alive. That includes `4`
and `132`, which on Hack-Man address its fifth LED: Mysterio has only four.
Example (MicroPython on the badge):
`i2c.writeto(0x1B, bytes([0,0,255,255, 6,0,0,0]))` lights the right-hand LED
cyan.

Differences from Hack-Man, and why:

- **Brightness starts at 255, not 48.** The brightness cap (above) is applied
  to everything this board shows, I2C colours included, even the "ignore
  brightness" ones. Starting at 48 as well would make badge colours very dim
  (48/255 of 38 %). So a badge asking for full white gets 38 %.
- Reading from 0x1B returns 4 status bytes, as on Hack-Man: version major,
  version minor, state (0..3 = mode number, 0x80 = I2C mode, 0x40 = still
  booting), current I2C brightness. On the S3 the answer can be one
  transaction out of date.
- Entering I2C mode starts from all-black; the brightness setting is
  remembered.

## How the code is laid out

- `mysterio-core/`: everything about *behaviour*: the maker's shimmer
  (`shimmer.rs`), the other modes (`modes.rs`), the boot glow, button and
  switch handling (`app.rs`), the I2C command rules (`i2c.rs`). No hardware
  code; tested on a PC (55 tests).
- `mysterio-fw/`: the thin hardware layer: reads pins, sends colours to the
  LEDs (with the chip's RMT peripheral), runs the I2C target, and sleeps.

**What is copied unchanged from Hack-Man** (so fixes found on one board can be
carried to the other; compare with `diff`):

| File | Compared with Hack-Man |
|---|---|
| `.gitignore` | identical |
| `mysterio-fw/build.rs` | identical |
| `mysterio-fw/rust-toolchain.toml` | identical |
| `mysterio-fw/.cargo/config.toml` | identical |
| `mysterio-core/src/color.rs` | identical |
| `mysterio-core/src/input.rs` | identical |
| `mysterio-fw/Cargo.lock` | same dependency versions; only the two crate names differ |
| `mysterio-fw/Cargo.toml`, `mysterio-core/Cargo.toml` | same pinned versions and features; only names and descriptions differ |
| `mysterio-fw/src/i2c_target.rs` | one comment line (the address, 0x1B) |
| `mysterio-fw/src/leds.rs` | the crate name and two comments (LED and code counts) |
| `mysterio-fw/src/main.rs` | the header comment, the crate name, one comment and the start-up banner. Pins, I2C, sleep and panic handling are unchanged |
| `mysterio-core/src/i2c.rs` | address 0x1B, LED indices 0..3, starting brightness, docs |
| `mysterio-core/src/lib.rs`, `app.rs`, `modes.rs`, `shimmer.rs` | Mysterio's own (same structure as Hack-Man's) |

Choices carried over from Hack-Man: bare-metal `esp-hal` 1.2.2 (no ESP-IDF,
stable Rust on C3/C6); esp-hal's I2C target driver on the C3/C6, stepped by
hand from the main loop; the S3's I2C target programmed register by register
because esp-hal has no I2C target driver for the S3; a small RMT LED driver of
our own; exact dependency versions pinned. The chip restarts itself if the
firmware ever crashes (panics).

## What still needs a real board

Nothing below has been tested. Each item is a thing only real hardware can
confirm:

1. **LED timing at 3.3 V.** Bit timings (0: 350/900 ns, 1: 800/450 ns) are
   mid-tolerance for WS2812-style LEDs; check with a logic analyser if colours
   glitch. The SK6805s are rated from 3.7 V; at 3.3 V blue and white may look
   dimmer or shifted. The maker ran them at 3.3 V too.
2. **LED order and colours on the board**: that index 0 really is the
   right-hand LED, and that the shimmer looks like his (side-by-side with an
   original if possible). Tune the cap and the mist/boot colours by eye.
3. **LED sending with one RMT memory block.** A frame (97 codes) is longer
   than the block (48), so esp-hal refills it on the fly with interrupts off
   for about 120 us. Same as Hack-Man; unverified on both.
4. **I2C target on the C3/C6** (esp-hal's unstable driver): that it answers at
   0x1B, receives 4- and multi-command writes, and that its clock stretching
   is tolerated by the badge. Some bit-banged badge controllers cannot handle
   stretching.
5. **I2C target on the S3** (our own register code): everything about it,
   including reads.
6. **Hack-Man and Mysterio on one bus** at 0x1A and 0x1B: not tried.
7. **Internal I2C pull-ups really off** on all three (measure SDA/SCL with the
   badge unplugged: they should float, not sit at 3.3 V).
8. **Deep sleep and wake on each chip**: that OFF reaches deep sleep, that the
   pull-down on D1 holds during sleep, and that sliding out of OFF wakes the
   module. On this board the OFF sense passes through a 330 ohm resistor
   (R4); it should make no difference. Measure the sleep current; the LEDs
   stay powered in OFF only if USB is plugged in.
9. **LED data line held low during sleep**, so the dark LEDs do not pick up
   noise and light randomly.
10. **The BOOT button as the mode button**: it is also the "download mode"
    button, so holding it while plugging in or resetting enters the flasher,
    by design of the module.
11. **Power use while running**: the main loop never sleeps; the CPU runs at
    80 MHz. Mode 3 (all off) saves the LED current but not the chip's. Not
    measured.
12. **Badge power into the XIAO's 3V3 pin** (see `../README.md`): a board
    question rather than a firmware one, but the first thing to check.
13. **Serial log** goes to the USB port; the XIAO's TX/RX pins (D6/D7, the
    SAO GPIO pins) are never driven.
