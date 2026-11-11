# Hack-Man SAO firmware (SAO++ edition)

Firmware for the Hack-Man add-on: five little lights behind Pac-Man and the
four ghosts. It runs on a Seeed Studio XIAO module, and the same source builds
for all three modules the board takes: **XIAO ESP32-C3** (the main target),
**XIAO ESP32-C6** and **XIAO ESP32-S3**.

**This is a new program, not a copy.** The original Hack-Man add-on by
InstantArcade (Bob), <https://hackaday.io/project/198301-hack-man-sao>, ran on
a different chip and its code was never published. This firmware was written
from scratch from his public description of what the board does.

**Status: built, not yet tried on a board.** All three versions compile and
the behaviour logic passes 52 automatic tests on a PC, but no Hack-Man board
existed when this was written. Nothing here has been seen working on real
hardware. See [What still needs a real board](#what-still-needs-a-real-board).

## What it does

**At power-on** all five characters light in their own colours for one second.
Then the firmware version flashes in binary (read left to right, Pac-Man is the
biggest digit): the first number in white for half a second, the second number
in green for half a second. This is version 0.1, so the white flash shows
nothing and the green one lights only the pink ghost on the far right.

**The mode button** is the small **BOOT** button on the XIAO module itself.
Each short press moves to the next light show, and after the fourth it starts
again at the first:

| Mode | What you see |
|---|---|
| 0 (default) | The arcade's demo screen, told in colours (timeline below). Repeats every 20 seconds. |
| 1 | A slow rainbow drifting across the five characters (12 s per lap of the colour wheel). |
| 2 | A "Larson scanner": one light at a time sweeps left and right, about once a second, slowly changing colour. |
| 3 | A slower, softer sweep (5 s there and back) where every character glows in its own colour and fades in and out. |

**The power switch** has three positions (see the SAO++ standard, section 3a).
In the middle **OFF** position the firmware turns all lights off and puts the
module into its deepest sleep. Sliding the switch out of OFF wakes it up and it
starts again from the power-on sequence in mode 0 (it does not remember the
last mode).

**The badge can take over the lights** over I2C (details below). As soon as
the badge sends a valid command the add-on stops its own show and displays
what the badge asks for. If the badge goes quiet for 5 seconds the add-on goes
back to its own show. Pressing the mode button also takes control back.

### Mode 0 timeline (one 20-second loop)

| Seconds | What happens |
|---|---|
| 0.0 - 2.5 | Cast intro: red, pink, cyan and orange ghosts fade in one by one, then Pac-Man. |
| 2.5 - 6.0 | Chase: ghosts in their colours with a faint shimmer; Pac-Man "chomps" (pulses 4 times a second). |
| 6.0 | Power pellet: Pac-Man flashes white, all ghosts turn blue. |
| 6.0 - 13.0 | Ghosts are frightened (blue). From 11.0 s the ones still blue flash blue/white. |
| 7.0 / 8.5 / 10.0 | Pac-Man eats the red, then orange, then cyan ghost. The eaten ghost shows the cyan "points" colour for 0.6 s while Pac-Man disappears (as the arcade does when showing the score), then only dim "eyes" remain. Two seconds after being eaten, that ghost is back in its own colour. |
| 13.0 | The pink ghost, never caught, recovers. |
| 13.0 - 16.0 | Chase again. |
| 16.0 - 17.0 | Caught! Everything freezes. |
| 17.0 - 18.5 | Ghosts vanish, Pac-Man shrinks away in steps. |
| 18.5 - 18.7 | A small dim white "pop". |
| 18.7 - 20.0 | Dark, then it starts again. |

### Brightness

The built-in shows run at about 19 % brightness (`DEFAULT_BRIGHTNESS = 48` out
of 255, in `hackman-core/src/lib.rs`). The lights run from 3.3 V and possibly a
small LiPo, so this is deliberately modest. The character colours
(`palette` in the same file) are first guesses tuned for an RGB LED rather than
the arcade palette, and should be adjusted by eye on a real board.

## Which XIAO?

Any of the three. The C3 is the main target. All three build from this one
folder; you choose the chip when you build. Use the matching command below for
the module actually soldered to your board: firmware for one chip will not run
on another.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C. Run these from the `hackman-fw` folder.

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
  `espflash flash --chip esp32c3 target/riscv32imc-unknown-none-elf/release/hackman-fw`
  (C6: `--chip esp32c6 target/riscv32imac-unknown-none-elf/...`;
  S3: `--chip esp32s3 target/xtensa-esp32s3-none-elf/...`).
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.

Tests of the behaviour logic run on any PC, no board needed:

```
cd hackman-core
cargo test
```

## Pin map

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| LED data (330 ohm series resistor on the board) | D10 | GPIO10 | GPIO18 | GPIO9 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| Mode button = module's BOOT button (active low; internal pull-up) | BOOT | GPIO9 | GPIO9 | GPIO0 |
| SAO GPIO1 (unused, left as input) | D7 | GPIO20 | GPIO17 | GPIO44 |
| SAO GPIO2 (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |

LED chain order: the first LED on the data line (index 0) is the **rightmost**
character seen from the front. Left to right on the front: Pac-Man (4), red
ghost (3), orange ghost (2), cyan ghost (1), pink ghost (0).

## I2C commands

The add-on is an I2C target at 7-bit address **0x1A**. The badge supplies the
pull-up resistors; the firmware switches the module's own pull-ups off (see
coin-cell note below). Every command is 4 bytes; one write may contain several
commands back to back.

| Bytes | Meaning |
|---|---|
| `[0..4, R, G, B]` | Cue a colour for LED 0..4 (0 = rightmost, pink ghost). Not shown until latched. |
| `[5, x, x, x]` | Clear all cued colours (to black). Not shown until latched. |
| `[6, x, x, x]` | Latch: show the cued colours. |
| `[7, brightness, x, x]` | Brightness for cued colours, 0 = off, 255 = full. Takes effect at once. Starts at 48. |
| `[128..132, R, G, B]` | Cue a colour for LED (first byte - 128) that ignores the brightness setting. |

Anything else is ignored and does not keep I2C mode alive. Example (MicroPython
on the badge): `i2c.writeto(0x1A, bytes([4,255,200,0, 6,0,0,0]))` lights
Pac-Man yellow.

Notes and decisions:

- The maker's page says both "0-5 Led Index" and "5 = clear". The board has
  five LEDs (0..4), so **5 means clear** here.
- Entering I2C mode starts from all-black; the brightness setting is remembered.
- Reading from 0x1A returns 4 status bytes: version major, version minor, state
  (0..3 = mode number, 0x80 = I2C mode, 0x40 = still booting), current I2C
  brightness. This is an addition, not in the original description. On the S3
  the answer can be one transaction out of date (see below).

## How the code is laid out

- `hackman-core/` - everything about *behaviour*: colours, the mode-0 story,
  the other modes, the boot sequence, button and switch handling, the I2C
  command rules. It has no hardware code and is tested on a PC (52 tests).
- `hackman-fw/` - the thin hardware layer: reads pins, sends colours to the
  LEDs (with the chip's RMT peripheral), runs the I2C target, and sleeps.

Choices made, and why:

- **Bare-metal `esp-hal` 1.2.2**, no ESP-IDF. It is pure Rust, builds with
  stable Rust on the C3/C6, and its I2C target driver (`I2cSlave`, marked
  "unstable" by esp-hal) exists for the C3 and C6. The firmware uses that
  driver's async functions, stepped by hand from the main loop, so the lights
  keep animating while it waits for the badge; no async runtime is needed.
- **The S3 is different:** esp-hal 1.2.2 does not offer its I2C target driver
  on the S3. Rather than pull in the whole ESP-IDF for one chip, the S3 build
  programs the I2C hardware registers directly (`hackman-fw/src/i2c_target.rs`),
  following the same steps esp-hal uses on the C3/C6, but without clock
  stretching. This part has the least backing of anything here.
- **LEDs:** a small RMT driver of our own (about 80 lines) (`hackman-fw/src/leds.rs`) rather
  than `esp-hal-smartled`, whose current release drags in an RTOS dependency.
- Exact dependency versions are pinned in `hackman-fw/Cargo.toml` and
  `Cargo.lock`.

## What still needs a real board

Nothing below has been tested. Each item is a thing only real hardware can
confirm:

1. **LED timing at 3.3 V.** Bit timings (0: 350/900 ns, 1: 800/450 ns) are
   mid-tolerance for WS2812-style LEDs; the SK6805-EC3210R at 3.3 V through
   330 ohm should be checked with a logic analyser if colours glitch.
2. **LED sending with one RMT memory block.** A frame (121 codes) is longer
   than the block (48), so esp-hal refills it on the fly with interrupts off
   for ~150 us. Should be fine; unverified.
3. **I2C target on the C3/C6** (esp-hal's unstable driver): that it ACKs
   0x1A, receives 4- and multi-command writes, and that its clock stretching
   (it holds SCL low until the firmware answers, typically well under 1 ms,
   at most one LED frame) is tolerated by the badge's I2C controller. Some
   bit-banged badge masters do not support stretching at all.
4. **I2C target on the S3** (our own register code): everything about it,
   including reads (it pre-loads the status bytes and relies on the
   "send automatically" bit).
5. **Internal I2C pull-ups really off** on all three (measure SDA/SCL with the
   badge unplugged: they should float, not sit at 3.3 V).
6. **Deep sleep and wake on each chip**: that OFF reaches deep sleep, that the
   pull-down on D1 holds during sleep, and that sliding out of OFF wakes the
   module (C3 GPIO3, C6 GPIO1 and S3 GPIO2 are all low-power-capable pins, but
   each chip wakes through a different mechanism). Measure the sleep current.
   The five LEDs stay powered in OFF and draw their idle current; that is
   likely more than the sleeping chip.
7. **LED data line held low during sleep** (pad hold on GPIO10 / GPIO18 /
   GPIO9) so the dark LEDs do not pick up noise and light randomly.
8. **The BOOT button as the mode button**: it is also the "download mode"
   button, so holding it while plugging in or resetting enters the flasher,
   by design of the module.
9. **Power use while running**: the main loop never sleeps (it keeps checking
   the I2C bus); the CPU runs at 80 MHz to save power. Not measured.
10. **Colours** behind the translucent characters: tune `palette` by eye.
11. **Serial log** goes to the USB port; the XIAO's TX/RX pins (D6/D7, the SAO
    GPIO pins) are never driven.

## Coin-cell safety

In the USB-BAT switch position the module runs from its own LiPo while the
badge's I2C wires are still connected. If the module's internal pull-ups were
on, they could push current into an unpowered badge and its coin cell. The
firmware therefore turns them off on SDA and SCL right after starting the I2C
driver. This should be confirmed with a meter (item 5 above).
