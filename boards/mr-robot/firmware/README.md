# Mr. Robot SAO firmware (SAO++ edition)

Firmware for the Mr. Robot add-on: an "I2C sound card" shaped like the mask.
The badge sends a note number, the add-on plays it on its little sounder. It
runs on a Seeed Studio XIAO module, and the same source builds for all three
modules the board takes: **XIAO ESP32-C3** (the main target), **XIAO
ESP32-C6** and **XIAO ESP32-S3**.

**Credit.** The board and its badge protocol are by **davedarko (Dave
Darko)**, <https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Mr%20Robot%20Badge>.
His own Arduino sketches are in `../original/Arduino/`. This firmware is a
**clean re-implementation in Rust of what his add-on sketch does**, not a port
of his code. The modes, extra badge commands, tunes and sleep are new. The
permission notice in `../README.md` applies to this board.

> **Status: this firmware has NEVER run on hardware.** All three versions
> compile and the behaviour logic passes 60 automatic tests on a PC, but no
> SAO++ Mr. Robot board exists yet. Nobody has heard it make a sound. See
> [What still needs a real board](#what-still-needs-a-real-board).

## What it does

**At power-on** it plays a quick two-note chirp (high, then higher; about a
quarter of a second). The board has no lights, so the chirp is how it tells
you it is alive. Then it waits silently for the badge.

**The mode button** is the small **BOOT** button on the XIAO module itself.
Each short press moves to the next mode; after the third it starts again at
the first:

| Mode | What you hear |
|---|---|
| 0 (default) **Listen** | Nothing. The add-on waits for the badge. Pressing the button into this mode gives one short beep, so you know where you are. |
| 1 **Jukebox** | The seven built-in tunes (below), one after another, with 2 seconds of quiet between them, round and round. |
| 2 **Scale** | The maker's own demo: a rising scale of short beeps, notes 1 to 69, each on for 0.1 s and off for 0.1 s, then again from the bottom. The lowest notes are mostly clicks on a small sounder; that is expected. |

**The power switch** has three positions. In the middle **OFF** position the
firmware silences the sounder and puts the module into its deepest sleep.
Sliding the switch out of OFF wakes it up and it starts again from the
power-on chirp in mode 0 (it does not remember the last mode).

**The badge can take over** over I2C (details below). As soon as the badge
sends a valid command, the add-on stops its own mode and plays what the badge
asks for. A note the badge asks for keeps sounding until the badge says
otherwise, exactly as on the maker's board. Once the badge's sound has
stopped and the badge has sent nothing for 5 seconds, the add-on goes back to
its own mode. Pressing the mode button also takes control back, and silences
whatever the badge was playing.

### Built-in tunes

All seven were written for this firmware: short arpeggios, runs and alert
beeps. None of them is a copy of a TV theme, song or other existing music.

| Number | Name | Sounds like | Length |
|---|---|---|---|
| 0 | hello | four notes rising, last one held | 0.75 s |
| 1 | alert | two-tone "dee-da" three times | 0.75 s |
| 2 | power down | four notes falling, last one low and long | 0.9 s |
| 3 | chatter | fast high robot babble | 1.25 s |
| 4 | level up | a quick climb to a held high note | 1.25 s |
| 5 | error | two low tones, "nope" | 1.25 s |
| 6 | question | rising "huh?" | 0.75 s |

Lengths are at the normal tempo (120 beats a minute); the badge can change
the tempo.

## The sounder: type unknown, what to listen for

The board keeps the maker's sounder (Kingstate KMTG-1102). Nobody knows yet
whether it is a **coil** (magnetic) type or a **piezo** type; the board is
designed to be safe with either (see `../README.md`). The firmware does not
need to know: it only ever switches the sounder on and off, at most half the
time, and never leaves it switched on when silent.

On the first board:

1. **Measure first**, unpowered: across the sounder's two pads, some tens of
   ohms means coil; open circuit means piezo.
2. **Listen in Scale mode** (press BOOT twice). Small sounders of both types
   are loudest over a narrow band, usually somewhere between about 2,000 and
   4,000 Hz (notes 73 to 85, near the top of the scale), and quiet or
   clicky well below it. Note where it is loudest: that tells the badge
   writers which notes carry.
3. **Listen for a steady hum or hiss when it should be silent.** There must
   be none. Any sound in Listen mode (other than the chirp and the mode beep)
   means the pin is not being held low, which matters most for a coil type.
4. **Hold a note for a minute** (badge writes `47`, the A above middle C)
   and feel the sounder and the small transistor beside it: both should stay
   cool.

## Current limits

The board's two parallel 330-ohm resistors cap the sounder current at about
19 mA while the pin is high, whatever the sounder turns out to be. The
firmware's part:

- **Square wave of exactly 50 % at most**: the sounder is on for half of each
  cycle, so a note averages about 10 mA, never more.
- **Silent means pin low**, always: at power-on (first thing the firmware
  does), between notes, between tunes, in Listen mode, when the badge sends
  0, and through deep sleep (the pin is held low while the chip sleeps). A
  stuck-high pin would put a steady 19 mA through a coil for no sound. This
  rule is enforced in one place in the code and tested.
- **Wi-Fi and Bluetooth are never started** (no radio code is included at
  all), and the chip runs at 80 MHz, its slowest normal speed. That keeps the
  module itself at roughly 20 to 40 mA, so module plus a playing note stays
  inside the badge's 50 mA budget. The S3 is the hungriest of the three
  modules: prefer the C3 or C6 on badge power.
- **Volume cannot be changed.** The sounder is switched fully on and off;
  how loud it is depends only on the board's resistors. There is no volume
  command, on purpose.

## Which XIAO?

Any of the three. The C3 is the main target. All three build from this one
folder; you choose the chip when you build. Use the matching command below for
the module actually soldered to your board: firmware for one chip will not run
on another.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C (switch on USB, and **not on a badge** if the switch is on SAO). Run
these from the `mrrobot-fw` folder.

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
  `espflash flash --chip esp32c3 target/riscv32imc-unknown-none-elf/release/mrrobot-fw`
  (C6: `--chip esp32c6 target/riscv32imac-unknown-none-elf/release/mrrobot-fw`;
  S3: `--chip esp32s3 target/xtensa-esp32s3-none-elf/release/mrrobot-fw`).
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.
- The S3 build prints one linker notice ("LOAD segment with RWX
  permissions"). It is a notice about the memory layout esp-hal uses, not an
  error.

**For the maker's original badge code** (which talks to address 0x08 instead
of this board's 0x1D), add `--features maker-address` to any of the commands
above, for example `cargo c3 --features maker-address` or
`cargo flash-c3 --features maker-address`. That is the only difference. The
start-up log line shows which address a board was built for.

Tests of the behaviour logic run on any PC, no board needed:

```
cd mrrobot-core
cargo test
```

## Pin map

Same pins as Hack-Man and Mysterio; the sounder takes the pin they use for
their LEDs.

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| Sounder (through 1.3 k to transistor Q1; high = sounder on) | D10 | GPIO10 | GPIO18 | GPIO9 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| Mode button = module's BOOT button (active low; internal pull-up) | BOOT | GPIO9 | GPIO9 | GPIO0 |
| SAO GPIO1 (unused, left as input) | D7 | GPIO20 | GPIO17 | GPIO44 |
| SAO GPIO2 (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |

## I2C commands

The add-on is an I2C target at 7-bit address **0x1D** (the house numbering:
Hack-Man 0x1A, Mysterio 0x1B, Do Or Donut 0x1C), or **0x08**, the maker's
own, when built with `--features maker-address`. The badge supplies the
pull-up resistors; the firmware switches the module's own pull-ups off.

### The maker's commands (unchanged, so his badge code works)

In every write only the **last byte** counts; any bytes before it are
ignored.

| Last byte | What happens |
|---|---|
| 0 | Silence. |
| 1 to 89 | Play that note until the next command. 1 = B0 (31 Hz), 2 = C1, ... 38 = middle C (262 Hz), 47 = A (440 Hz), ... 89 = D#8 (4978 Hz): one semitone per step. |
| 90 to 255 | **Ignored.** (The maker's sketch had no check here and would have played a random pitch. This one does nothing, and keeps playing whatever it was playing.) |

An empty write is ignored too. Example (MicroPython on the badge):
`i2c.writeto(0x1D, bytes([47]))` plays A; `i2c.writeto(0x1D, bytes([0]))`
stops it.

The note frequencies are the standard ones (equal temperament, A = 440 Hz),
rounded to whole hertz like the maker's table, and checked by a test against
the formula. One differs from his table by 1 Hz: note 20 (F#2) is 92 Hz here,
93 Hz in his file; the true value is 92.5 Hz. Nobody will hear that.

### Extra commands (new)

Each extra command is 4 bytes:

```
0xE5, command, value, 0x5E
```

Several can go in one write, back to back.

| Command | Value | What happens |
|---|---|---|
| 1 | tune number 0 to 6 | Play that built-in tune once (stops any held note). |
| 2 | anything | Stop: silence everything. |
| 3 | beats per minute | Tempo for tunes. 0 = back to normal (120). Below 40 counts as 40, above 240 counts as 240. Stays until power-off. |

Unknown commands and tune numbers above 6 are ignored. There is no volume
command: this sounder's loudness is fixed by the board (see Current limits).

**Why these can never be mixed up with the maker's commands.** The maker's
rule only looks at the last byte of a write. Every extra command ends in
0x5E, which is 94: above 89, so under his rule it means "ignore". A badge
using only his commands therefore never sends anything that looks like an
extra command (its meaningful writes end in 0 to 89), and an extra command
sent to an original Mr. Robot board would be ignored rather than play a
wrong note. The firmware only treats a write as extra commands if its length
is a multiple of 4 and **every** 4-byte group starts with 0xE5 and ends with
0x5E; anything else is read with the maker's rule. Tests check every
possible 1- and 2-byte write and every 4-byte write that starts with 0xE5
and ends in 0 to 89.

Example: `i2c.writeto(0x1D, bytes([0xE5, 3, 90, 0x5E, 0xE5, 1, 4, 0x5E]))`
sets the tempo to 90 and plays "level up".

### Reading

Reading from the add-on returns 4 bytes:

| Byte | Meaning |
|---|---|
| 1 | firmware version, major (0) |
| 2 | firmware version, minor (1) |
| 3 | who is in charge: 0x40 = still chirping at power-on; 0, 1, 2 = the add-on, in that mode; 0x80 = the badge, silent; 0x81 = the badge, holding a note; 0x82 = the badge, playing a tune |
| 4 | the note sounding right now (1 to 89), or 0 for silence |

On the S3 the answer can be a few milliseconds out of date.

## How the code is laid out

- `mrrobot-core/`: everything about *behaviour*, with no hardware code,
  tested on a PC (60 tests):
  - `notes.rs`: the 89-note table, checked against the formula;
  - `tone.rs`: the two sounder rules (at most 50 %, silent = pin low) and the
    timer numbers for every note;
  - `tune.rs`: the tune player and the built-in tunes;
  - `i2c.rs`: the badge commands and the framing rule above;
  - `app.rs`: modes, button and switch handling, badge control;
  - `input.rs`: debouncing (an unchanged copy of Mysterio's).
- `mrrobot-fw/`: the thin hardware layer: reads pins, drives the sounder
  (`sounder.rs`), runs the I2C target, and sleeps.

**How the sound is made.** The chip's LEDC peripheral (its "LED PWM"
hardware, which all three chips have) generates the square wave by itself
from an 80 MHz clock, so the processor does no work per cycle and nothing
busy-waits. Each note just sets the LEDC's clock divider; the high time is
fixed at exactly half of each cycle. For silence the LEDC's output is
switched off with its resting level set to low, as well as the high time set
to zero. The firmware works out the divider itself rather than letting
esp-hal do it: on the C6, esp-hal 1.2.2 appears (from reading its source) to
calculate the divider from a 40 MHz clock while running the LEDC from an
80 MHz one, which would put every note an octave high.

**What is copied from Mysterio** (so fixes found on one board can be carried
to the other; compare with `diff`):

| File | Compared with Mysterio |
|---|---|
| `.gitignore` | identical |
| `mrrobot-fw/build.rs` | identical |
| `mrrobot-fw/rust-toolchain.toml` | identical |
| `mrrobot-fw/.cargo/config.toml` | identical |
| `mrrobot-core/src/input.rs` | identical |
| `mrrobot-fw/Cargo.lock` | same dependency versions; only the two crate names differ |
| `mrrobot-fw/Cargo.toml`, `mrrobot-core/Cargo.toml` | same pinned versions and chip features; adds the `maker-address` feature |
| `mrrobot-fw/src/i2c_target.rs` | the address comment, and a small `bus_busy()` helper on the S3 |
| `mrrobot-fw/src/main.rs` | same pins, I2C, sleep and panic handling; the LED code is replaced by the sounder, and the S3 refreshes its read answer when the status changes |
| `mrrobot-fw/src/sounder.rs`, everything else in `mrrobot-core/src/` | Mr. Robot's own |

Choices carried over from Mysterio and Hack-Man: bare-metal `esp-hal` 1.2.2
(no ESP-IDF, stable Rust on C3/C6); esp-hal's I2C target driver on the C3/C6,
stepped by hand from the main loop; the S3's I2C target programmed register
by register because esp-hal has no I2C target driver for the S3; exact
dependency versions pinned. The chip restarts itself if the firmware ever
crashes.

## What still needs a real board

**None of this firmware has run on hardware.** Each item below is something
only a real board can confirm:

1. **Any sound at all**, and the right pitch: hold note 47 and check with a
   tuner app that it reads 440 Hz (A). Do this on every module type,
   **especially the C6** (see the clock note above: an octave out would mean
   the workaround is wrong).
2. **Coil or piezo**, and where it is loudest (see "The sounder" above).
3. **Silence really is silence**: no hum between notes, in Listen mode, or in
   OFF. A scope or meter on D10 should read 0 V when silent.
4. **Current from a badge**: under 50 mA with a note playing (a USB power
   meter on USB/LiPo gives a first idea). The transistor and sounder stay
   cool with a note held for a minute.
5. **I2C target on the C3/C6** (esp-hal's unstable driver): that it answers
   at 0x1D, takes the maker's one-byte writes and the 4-byte extra commands,
   and that its clock stretching is tolerated by the badge.
6. **I2C target on the S3** (our own register code): everything about it,
   including reads.
7. **The maker's badge sketch** (`MasterMrRobot.ino`) against a board built
   with `--features maker-address`: it should play a rising scale of beeps.
8. **Internal I2C pull-ups really off** on all three (measure SDA/SCL with the
   badge unplugged: they should float, not sit at 3.3 V).
9. **Deep sleep and wake on each chip**: that OFF reaches deep sleep, that the
   pull-down on D1 holds during sleep, that sliding out of OFF wakes the
   module, and that the sounder pin stays low through sleep and is released
   again after wake (a board that wakes up mute would mean the pin hold was
   not released).
10. **The moments before the firmware runs**: during reset, flashing and the
    first few milliseconds after power-on the sounder pin is not driven, and
    the board has no resistor holding the transistor off. Listen for a click
    or buzz when plugging in or flashing; it should be harmless, but note it.
11. **The BOOT button as the mode button**: it is also the "download mode"
    button, so holding it while plugging in or resetting enters the flasher,
    by design of the module.
12. **Badge power into the XIAO's 3V3 pin** (see `../README.md`): a board
    question rather than a firmware one, but the first thing to check.
13. **Serial log** goes to the USB port; the XIAO's TX/RX pins (D6/D7, the
    SAO GPIO pins) are never driven.
