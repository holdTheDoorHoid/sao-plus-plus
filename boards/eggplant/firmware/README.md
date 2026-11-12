# Eggplant SAO firmware (SAO++ edition)

Firmware for the Eggplant add-on: five RGB lights round the edge of a purple
eggplant, and an I2C "personality" a badge can talk to. It runs on a Seeed
Studio XIAO module: **XIAO ESP32-C3** (the main target), **XIAO ESP32-C6** or
**XIAO ESP32-S3**.

**Status: never compiled.** There was no Rust toolchain on the machine this
was written on, and nothing was installed to get one. The code has been read
through carefully, not built. Expect to fix compile errors before anything
else. `Cargo.lock` in both folders is Hack-Man's lock file with the two crate
names changed (the dependencies are identical); if cargo complains, delete it
and let cargo write a new one.

## Where it comes from

The behaviour is a line-by-line re-implementation, in Rust, of the maker's
Arduino sketch for the original board's ATtiny85:
`../original/firmware/eggplant.ino`, "Designed by Krux - 2018", MIT licence,
from <https://github.com/thedarknet/dc26-badge>. The fade numbers, the I2C
commands and replies, and the "infection" game are his. The hardware layer
(`eggplant-fw`) is the Hack-Man board's, with the I2C read path changed.

## What it does

**Lights.** All five LEDs show the same mix of red and blue, each fading up
and down on its own timetable, as the maker's two LED groups did:

| Mode | The maker's name for it |
|---|---|
| 0 | slow red, normal blue (the power-on mode) |
| 1 | normal red, normal blue |
| 2 | blue only pulse |
| 3 | purple only pulse |
| 4 | red only pulse |
| 5 | rollers (red and blue chase each other) |

**The mode button** is the small **BOOT** button on the XIAO: each press goes
to the next mode. (The maker's board had no button; only a badge could change
the mode. Holding BOOT while plugging in USB puts the module in its flashing
mode instead, by design of the module.)

**The power switch.** In OFF the lights go dark and the module sleeps until
the switch is moved.

**Infection.** A badge can try to infect the eggplant, cure it, or ask how it
is. An infected eggplant flashes red ten times, a cured one blue ten times,
then goes back to its mode. The two "diseases" are bits 64 and 128 of one
byte; the maker's sketch names them after two sexually transmitted diseases,
and the second "can't be really ever cured" (it is remembered separately).

## What is different from the maker's board

- **Nothing is remembered after power-off.** The ATtiny stored the name, the
  serial number, the light mode and the infection in its EEPROM. Here the same
  512 bytes live in RAM: every I2C command works, but a power cut resets it to
  "NonameEggie", mode 0, healthy, and a new random serial number. Saving it in
  the module's flash is the obvious next step once the firmware builds.
- **Speed is a guess.** The fades advance one of the maker's steps every
  10 ms (`STEPS_PER_FRAME` in `eggplant-core/src/lib.rs`). How fast his chip
  really ran its loop is not recorded.
- **Brightness is capped** at a quarter (`MAX_LEVEL = 64`): five RGB LEDs at
  full red + blue would take the whole 50 mA an add-on may draw from a badge.
- **One reply per read.** The maker's chip re-ran the command for every byte
  the badge read (a quirk of its I2C library). Here a command runs once.
- **On the S3** the command is carried out when the badge writes it, not when
  the badge reads the answer (see "How the code is laid out").

## I2C commands

Address **0x36** (7-bit). The badge supplies the pull-ups. To do anything the
badge **writes** `[0, noun, verb, data…]` (the leading 0 is a position in a
16-byte register window, always 0 in practice) and then **reads** the reply.
Replies are padded with zeros to the length the badge asks for.

| Write | Reply | Meaning |
|---|---|---|
| `0, 0, 0` | `EGGPLANT` | type |
| `0, 0, 1` | `1.0.0` | protocol version (the maker's string, kept) |
| `0, 0, 2` | 8 characters | serial number, random, made on first request |
| `0, 0, 3` | up to 12 characters | name |
| `0, 1, 3, name…` | `name|OK` | set the name (up to 12 printable characters) |
| `0, 2` | mode, then 13 bytes | light mode and the fade's internal numbers |
| `0, 3, mode` | `mode|OK` | set the light mode 0–5 (anything higher becomes 0) |
| `0, 4, 0` | byte, `|INFECTED` or `|AOK` | "try to infect me": what a partner would catch (a dice roll) |
| `0, 4, 1` | two bytes, `|INFECTED` or `|AOK` | true infection status |
| `0, 5, 0, bits` | byte, `|INFECTED` or `|NOCHANGE` | infect (only bits 64 and 128 count) |
| `0, 5, 1, bits` | byte, `|CURED` or `|NOCHANGE` | cure |
| `0, 8, lo, hi, n` | n bytes | read n (up to 16) bytes of the 512-byte memory |
| `0, 9, lo, hi, n, data…` | the bytes, `|OK` | write n (up to 10) bytes of memory |

The maker's own notes (`../original/firmware/eggplant_i2c_api.txt`) describe
"set light mode" with the mode one byte later and a mode 6 = off. His code,
and his badge, do it as above; the code is what this follows.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C. Run these from the `eggplant-fw` folder.

| Module | Build | Build, flash and watch the log |
|---|---|---|
| XIAO ESP32-C3 | `cargo c3` | `cargo flash-c3` |
| XIAO ESP32-C6 | `cargo c6` | `cargo flash-c6` |
| XIAO ESP32-S3 | `cargo +esp s3` | `cargo +esp flash-s3` |

C3 and C6 use stable Rust (`rustup target add riscv32imc-unknown-none-elf
riscv32imac-unknown-none-elf`). The S3 needs Espressif's toolchain (`espup
install`, then `source ~/export-esp.sh`). Plain `cargo build` fails on purpose
with a message telling you to pick a chip.

Tests of the behaviour run on any PC, no board needed (11 tests, never run):

```
cd eggplant-core
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
| Not wired on this board (left as inputs) | D7, D6 | GPIO20, 21 | GPIO17, 16 | GPIO44, 43 |

## How the code is laid out

- `eggplant-core/` — everything about behaviour: the fades, the modes, the
  button and switch, the I2C commands and the memory. No hardware code; meant
  to be tested on a PC.
- `eggplant-fw/` — the hardware layer, copied from Hack-Man: LED sending with
  the RMT peripheral (`leds.rs`), the I2C target (`i2c_target.rs`), sleep.
  Same pinned `esp-hal` 1.2.2 and the same reasons (see
  `../../hack-man/firmware/README.md`).
- On the C3 and C6 the firmware holds the I2C clock while it works out a
  reply (clock stretching), so the command runs when the badge reads, as on
  the maker's board. The S3 path cannot stretch the clock, so it runs the
  command as soon as it is written and has the reply waiting.

## What still needs a real board

Everything in Hack-Man's list (LED timing at 3.3 V, the I2C target driver,
pull-ups really off, deep sleep and wake, the BOOT button) applies here
unchanged, and none of it has been tried on that board either. Added by this
board:

1. That it compiles.
2. Long reads: the Darknet 7 badge reads 33 bytes at a time. The C3 / C6
   driver has to hand over 33 bytes; the S3's hardware buffer holds 32.
3. The fade speed and the brightness, by eye.
4. Whether a real Darknet 7 badge (if one can be found) recognises it.

## Coin-cell safety

As on Hack-Man: in the USB-BAT position the module runs from its own power
while the badge's I2C wires are still connected, so the firmware turns the
module's internal pull-ups on SDA and SCL off right after starting the I2C
driver. Confirm with a meter.
