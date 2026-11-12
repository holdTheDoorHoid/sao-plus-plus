# Duck Jaws SAO firmware (SAO++ edition)

Firmware for the Duck Jaws add-on: a toy duck in a shark's mouth. Two small
colour LEDs light the duck from behind; four red LEDs light the mouth. It runs
on a Seeed Studio XIAO module, and the same source is meant to build for all
three modules the board takes: **XIAO ESP32-C3** (the main target), **XIAO
ESP32-C6** and **XIAO ESP32-S3**.

## Status: NEVER COMPILED

**This code has not been through a compiler even once**, exactly like Duck
Bath's, which it is built on. The machine it was written on has no Rust
toolchain (no `cargo`, no `rustup`), and installing one was not allowed.

- Nothing has been built, for any chip.
- The 8 tests in `duckjaws-core` have never been run (nor have Duck Bath's 19).
- Expect typing mistakes and compiler complaints on the first build. Budget
  time for someone who knows Rust to fix them before trusting any of it.
- Get **Duck Bath's firmware building first**. Most of this program is that
  code; what is left here is small.

## How much is shared with Duck Bath

The maker's two boards run one firmware. Here too, as far as could be done
without touching Duck Bath's folder:

| Piece | Where it lives | Shared? |
|---|---|---|
| I2C register map, fader, switch debouncing, colour type | `boards/duck-bath/firmware/duckbath-core` | **Used from there**, as a normal dependency. Not copied |
| LED driver (`leds.rs`), I2C target driver (`i2c_target.rs`) | `boards/duck-bath/firmware/duckbath-fw/src` | **Used from there**: two `#[path]` lines in `duckjaws-fw/src/main.rs` build those very files into this program. Not copied |
| The "app" that ties registers, fader and switch together | `duckjaws-core/src/app.rs` | Its own, about 110 lines without tests: Duck Bath's throws the fourth (mouth) channel away and answers with Duck Bath's name, and neither can be changed from outside |
| Dimming of the red LEDs | `duckjaws-core/src/dimmer.rs` | New, 30 lines |
| Pins, main loop, sleep (`main.rs`) | `duckjaws-fw/src/main.rs` | A copy of Duck Bath's with about 70 lines added or changed for the mouth LEDs |
| `Cargo.toml`, `Cargo.lock`, `build.rs`, `.cargo/config.toml`, `rust-toolchain.toml` | `duckjaws-fw/` | Copies with the names changed (build settings cannot be shared across folders) |

**What should become one shared crate** (not done here, because it means
editing Duck Bath):

1. Give `duckbath-core`'s `App` the fourth channel in its output and take the
   board's name / help text as a parameter. Then `duckjaws-core/src/app.rs`
   goes away entirely.
2. Move `leds.rs`, `i2c_target.rs` and the main loop with its sleep code into
   a library both boards (and Hack-Man, which they came from) depend on, so
   the `#[path]` lines and the copied `main.rs` go away. Each board would keep
   a pin table and a few lines.
3. One workspace with one `Cargo.lock` for the duck boards.

Because of the `#[path]` lines and the dependency, **this folder does not
build without `boards/duck-bath/` beside it**, and a change to Duck Bath's
firmware changes this one.

**This is new code, not a copy of the maker's.** The original duckGLOW
firmware by Adrian Studer (<https://github.com/astuder/duckglow>, MIT licence)
is C for a CH32V003. None of it is used; what is kept is what the add-on does
and its I2C register map. No licence has been chosen for this firmware yet
(same open question as for Hack-Man and Duck Bath).

## What it does

**On power-up** the duck starts breathing yellow and the mouth breathes red,
half a breath apart: the mouth is brightest when the duck is dimmest. One
cycle is 11.5 s. These are the maker's default settings.

**A badge can change it** over I2C at address **0x6C**, with the maker's
register map: the brightest and dimmest value, the fading speed and the
starting point of each of red, green, blue (the duck) and the **fourth
channel, the red mouth lights**. Setting a speed to 0 holds that channel
steady.

**The power switch**: in the middle **OFF** position the firmware turns all
LEDs off and puts the module into its deepest sleep. Sliding the switch out of
OFF wakes it and it starts again with the defaults.

## I2C registers

Address 0x6C. Write the register address, then data; the address moves on by
one after each data byte. A read returns bytes starting at the address last
written.

| Address | Name | Meaning |
|---|---|---|
| 0x00–0xEB | docs | a short text about the add-on (read-only) |
| 0xEC–0xEF | max | brightest value for red, green, blue, **mouth** |
| 0xF0–0xF3 | min | dimmest value for red, green, blue, **mouth** |
| 0xF4–0xF7 | speed | fading speed per channel; 0 = steady at max |
| 0xF8–0xFB | phase | where in the fading cycle each channel starts |
| 0xFC | mode | stored, but has no effect here |
| 0xFD | save | 42 = keep settings (not supported), 24 = back to defaults |
| 0xFE | debug | result of the last save: 0 = fine, 4 = not supported |

Example (Arduino): write `0xEF, 0x20` then `0xF7, 0x00` and the mouth glows
dimly and steadily.

### What is different from a real duckJAWS

Everything in the same table of Duck Bath's firmware README applies (no
WS2812 mode, no saving, one address, 16-byte reads, our own help text, 8-bit
brightness), except that the fourth channel does drive lights here. In
addition:

| Original | Here |
|---|---|
| Red LEDs dimmed by the chip's PWM timer, 10 bits | Dimmed in software from the main loop, 255 steps (see below) |
| About 2 mA per red LED (680 Ω) | About 1.1 mA (1.3 kΩ, the house value) |

## The red LEDs' dimming: a stop-gap

The four red LEDs are plain LEDs on one pin (XIAO D3), so their brightness is
made by switching the pin on and off quickly. This firmware does that **in
software**: 20,000 times a second the main loop decides "on" or "off" so that
the pin is on for the right share of the time (`dimmer.rs`).

The proper tool is the chip's LED PWM peripheral (LEDC). It is not used yet
for one reason: its programming interface could not be checked without a
compiler, and the software way needs nothing that Duck Bath's code does not
already use. **Once this builds, replace `Board::dim` with LEDC.** Until then
expect, and check for:

- a faint shimmer in the red at very low brightness;
- a tiny dip in the red every 10 ms while the duck's LEDs are updated;
- the red holding still (on or off) for any moment the processor is busy
  elsewhere, for example inside the I2C driver.

## Building and flashing

Not yet done by anyone. The steps are Duck Bath's and Hack-Man's. You need
Rust and `espflash` (`cargo install espflash`). Plug the XIAO into USB-C. Run
these from the `duckjaws-fw` folder.

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
cd ../../duck-bath/firmware/duckbath-core && cargo test
cd ../../../duck-jaws/firmware/duckjaws-core && cargo test
```

## Pin map

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| Duck LED data (330 ohm series resistor on the board) | D10 | GPIO10 | GPIO18 | GPIO9 |
| Red mouth LEDs (four, 1.3 k each; high = on) | D3 | GPIO5 | GPIO21 | GPIO4 |
| I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| SAO GPIO2 (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |
| Not connected on this board (input with pull-down) | D7 | GPIO20 | GPIO17 | GPIO44 |

D3 is not a start-up (strapping) pin on any of the three chips. The GPIO
numbers for D3 come from Seeed's pin tables as remembered (they fit the
pattern of the other pins, which Hack-Man checked), not re-read for this
board: check them against the module's pinout card before flashing.
The module's BOOT button is not used. LED 0 on the data line is the one left
of the duck hole, LED 1 the one to its right (seen from the front).

## How the code is laid out

- `duckjaws-core/` - what differs from Duck Bath in behaviour: `app.rs` (ties
  Duck Bath's registers and fader to the clock and the power switch, and
  hands out the mouth brightness) and `dimmer.rs`. No hardware code.
- `duckjaws-fw/` - the hardware layer: `main.rs` only (pins, main loop,
  sleep). The LED and I2C drivers come from Duck Bath's folder.

## What still needs a real board

Everything, after it compiles. The lists in the Hack-Man and Duck Bath
firmware READMEs apply item for item. Specific to this board:

1. **The red LEDs' dimming** (above): smooth, and dark when the level is 0.
2. **Red LEDs in sleep.** In OFF the pin is set low and then left to the
   chip's sleep state. Check the mouth stays dark in OFF with a LiPo attached.
3. **The `#[path]` lines.** If the compiler cannot find Duck Bath's files,
   the relative paths in `main.rs` are the first thing to look at.

## Coin-cell safety

As on Hack-Man and Duck Bath: in the USB-BAT switch position the module runs
from its own power while the badge's I2C wires are still connected, so the
firmware turns the module's internal pull-ups on SDA and SCL off right after
starting the I2C driver. Confirm with a meter. The red LED pin only ever
drives the LEDs on this board.
