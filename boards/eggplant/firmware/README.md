# Eggplant SAO firmware (SAO++ edition)

Firmware for the Eggplant add-on: five two-colour (blue and red) LEDs that
fade and pulse in the maker's patterns, a badge-facing I2C "memory" with a
name and serial number, and the maker's infection game. It runs on a Seeed
Studio XIAO module, and the same source builds for all three modules the board
takes: **XIAO ESP32-C3** (the main target), **XIAO ESP32-C6** and **XIAO
ESP32-S3**.

**Credit and licence.** The board, its badge protocol and its light shows are
by **Krux / DC Darknet (thedarknet)**, 2018:
<https://github.com/thedarknet/dc26-badge> (folder `dc26-sao`, commit 63ec6ed).
His Arduino sketch, his protocol notes and his EEPROM script are in
`../original/dc26-sao/`. This firmware is a **re-implementation in Rust of
what his sketch does**, written from reading it, not a line-by-line
translation. His code is under the MIT licence, and so is this firmware:

> MIT License — Copyright (c) 2017 (the maker's notice gives no name; the
> sketch header says "Designed by Krux - 2018").
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to
> deal in the Software without restriction, including without limitation the
> rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
> sell copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions: The above copyright
> notice and this permission notice shall be included in all copies or
> substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS",
> WITHOUT WARRANTY OF ANY KIND (full text: `../original/LICENSE`).

The list of 38 starting names (one is picked per board) is the maker's own,
from his `make-eeprom.pl`.

> **Status: this firmware has NEVER run on hardware.** It compiles for all
> three modules and its behaviour passes 31 automatic tests on a PC, but no
> SAO++ Eggplant exists yet. See [What still needs a real board](#what-still-needs-a-real-board).

## What it does

**The light shows.** All five red LEDs are on one wire and all five blue LEDs
on another, as on the maker's board, so every LED shows the same colour at
once. Two brightnesses walk up and down; red and blue together look purple.

| Mode | What you see (the maker's own patterns) |
|---|---|
| 0 (start) | slow red fade under a faster blue pulse |
| 1 | red and blue fading at the same speed, out of step |
| 2 | blue only, pulsing |
| 3 | purple pulse (red and blue together) |
| 4 | red only, pulsing |
| 5 | "rollers": red rising while blue falls, then the other way |
| off | dark (button only) |

**The button** is the small **BOOT** button on the XIAO module. Each press goes
to the next mode, then off, then back to 0.

**The power switch** in the middle **OFF** position makes the firmware go dark
and put the module into its deepest sleep; sliding it out of OFF starts again.

**The badge** can do everything the maker's badge code could, at I2C address
**0x28** (the SAO++ house address for this board), or the maker's **0x36** in a
build with the `maker-address` option:

- read the add-on's type (`EGGPLANT`), version (`1.0.0`, kept as the maker's so
  badge code that checks it still works), serial number and name
- rename it (up to 12 characters)
- set the light mode (0 to 5)
- play the **infection game**: infect it with one or both of two "bugs", cure
  it, ask for its true status, or ask "would you infect me?" (each bug passes on
  only by chance: one half the time, the other three times in ten). A board
  that is or becomes infected flashes red ten times; a cured one flashes blue.
  The second bug "lasts": curing it clears it for now, but at the next power-on
  it comes back nine times in ten
- read and write its 512-byte memory, laid out exactly like the maker's

The full command table is at the top of `eggplant-core/src/proto.rs`. In short:
write `0, noun, verb, data...`, then read the answer.

## Differences from the maker's board, on purpose

1. **The memory is not kept when the power goes off.** His board kept name,
   mode and infections in the ATtiny85's EEPROM. This first version keeps them
   in RAM only. Keeping them needs the `esp-storage` crate (flash storage),
   which is not in the house's checked set of crates yet; it is the next step.
   Until then, every power-on starts at mode 0, with a fresh name picked from
   the maker's list by the module's serial number, and no infection (so the
   "lasting bug" cannot come back yet either).
2. **The serial number** is made from the XIAO's own factory MAC address
   instead of being rolled at random on first use, so it is the same every
   power-on. Same alphabet as his (0-9 and A-E).
3. **An answer is worked out when the badge writes the command**, not when it
   reads. On his board, reading "would you infect me?" twice rolled the dice
   twice; here both reads get the same answer until the next command. The S3
   cannot answer late, so all three chips behave this way.
4. **His mode command clamps 6 and above to 0** (his notes say 6 means off,
   his code does not). The badge behaviour follows his code; "off" is reachable
   with the button.
5. **Brightness steps.** He switched the pins in a 96-step software loop; here
   the chip's LED PWM hardware does it at 2 kHz. The fade speed is set by one
   number, `TICK_US` in `eggplant-core/src/fade.rs` (1 ms per step), which is
   an estimate of how fast his ATtiny loop ran. Adjust it on the first board
   if the fades look too fast or too slow next to a video of an original.
6. **Colour names.** His sketch calls the pin that his schematic wires to the
   **blue** anodes "red", and the other one "blue". This firmware follows the
   LED's own pad names (pad AB = blue, AR = red, from his footprint): D2 drives
   the red anodes, D3 the blue ones. If the first board shows the colours
   swapped, swap `RED` and `BLUE` in `eggplant-fw/src/leds.rs` (one line each)
   and the 330 ohm / 1.3 k resistors on the board (see `../README.md`).

## Pin map

| XIAO pin | C3 | C6 | S3 | Goes to |
|---|---|---|---|---|
| D2 | GPIO4 | GPIO2 | GPIO3 | the five red anodes, through 1.3 k each |
| D3 | GPIO5 | GPIO21 | GPIO4 | the five blue anodes, through 330 ohm each |
| D4 / D5 | GPIO6 / 7 | GPIO22 / 23 | GPIO5 / 6 | SAO SDA / SCL (I2C target; no pull-ups on the add-on) |
| D1 | GPIO3 | GPIO1 | GPIO2 | power switch OFF sense (high = OFF) |
| D7 / D6 | GPIO20 / 21 | GPIO17 / 16 | GPIO44 / 43 | SAO GPIO1 / GPIO2 through 330 ohm (not used yet; inputs) |
| BOOT | GPIO9 | GPIO9 | GPIO0 | mode button |

D2 rather than the house's usual LED pin D10: the two colour lines leave the
module side by side, which the board needs (see `../README.md`). D2 is a
start-up ("strapping") pin only for the S3's JTAG choice, which is ignored
unless a fuse is burnt, so it is safe here.

## Current

With every LED fully on: red about 5 x 1.1 mA, blue about 5 x 1.5 mA, so about
13 mA for the LEDs at most, plus the module (about 20-40 mA, radio off, 80 MHz).
That stays within the badge's 50 mA budget. Wi-Fi and Bluetooth are never
started (no radio code is linked).

## Building

Same tools as the Mr. Robot and Do Or Donut firmware in this repository.

```
cd eggplant-core && cargo test          # 31 tests, on the PC
cd ../eggplant-fw
cargo c3                                # XIAO ESP32-C3
cargo c6                                # XIAO ESP32-C6
. ~/export-esp.sh && cargo +esp s3      # XIAO ESP32-S3 (Xtensa toolchain from espup)
cargo c3 --features maker-address       # answer at the maker's 0x36 instead of 0x28
cargo flash-c3                          # build, flash with espflash, open the serial monitor
```

Checked on 2026-11-12: `cargo test` 31 passed; `cargo c3`, `cargo c6` and
`cargo +esp s3` all build (release). Nothing has been flashed.

## What still needs a real board

1. **Colours**: mode 2 must be blue only and mode 4 red only (see difference 6).
2. **Fade speed**: compare with the original (difference 5).
3. **Brightness**: blue through 330 ohm and red through 1.3 k should look about
   even; if one colour swamps the other in mode 3, change the resistor value,
   not the code.
4. **I2C** against a real badge at 0x28 (and 0x36 with `maker-address`): read the
   type, rename, set a mode, infect and cure. The maker's notes say his badges
   sent a leading 0 before every command; this firmware expects exactly that.
5. **OFF sleep and wake** with the switch, and that the LEDs stay dark in OFF.
6. **Badge power into the XIAO's 3V3 pin**, as on every SAO++ XIAO board.
