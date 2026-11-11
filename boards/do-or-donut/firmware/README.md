# Do Or Donut SAO firmware (SAO++ edition)

Firmware for the Do Or Donut add-on: a 51 mm donut whose 144 sprinkles are
tiny single-colour LEDs, driven by an IS31FL3731 LED driver chip. It runs on a
Seeed Studio XIAO module on the back of the board, and the same source builds
for all three modules the board takes: **XIAO ESP32-C3** (the main target),
**XIAO ESP32-C6** and **XIAO ESP32-S3**.

**Credit.** The board is by **davedarko (Dave Darko)**, 2019,
<https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Do%20Or%20DoNut>.
He published no firmware for it (on his board the badge drove the LED chip
directly), so everything here is new. The permission notice in `../README.md`
applies to this board.

> **Status: this firmware has NEVER run on hardware.** It compiles for all
> three chips and its logic passes 77 automatic tests on a PC, but no SAO++
> Do Or Donut board exists yet. Nothing here has been seen working: not the
> LEDs, not the badge connection, not the power switch. In particular **the
> brightness cap is calculated, not measured** (see below). See
> [What still needs a real board](#what-still-needs-a-real-board).

This firmware is a sibling of the Mysterio and Hack-Man firmware
(`../../mysterio/firmware/`, `../../hack-man/firmware/`): same module, same
switch and button habits, same style of I2C commands, and their badge-I2C and
sleep code copied unchanged (list below). What is new is the LED side.

## What it does

**At power-on** every sprinkle glows softly and evenly for one second. Then
the default show starts.

**The mode button** is the small **BOOT** button on the XIAO module itself.
Each short press moves to the next mode; after the last it starts again at
the first:

| Mode | What you see |
|---|---|
| 0 (default) | **Sprinkles.** Each sprinkle twinkles on its own: a soft flash just under a second long, then dark for a few seconds. Every sprinkle has its own rhythm, so the donut sparkles at random. |
| 1 | **Glaze wave.** A bright spot runs round the ring anticlockwise (seen from the front), one lap every 3 seconds, with a fading tail behind it. It uses each LED's real angle, so the inner and outer rings move together. |
| 2 | **Ripple.** A ring of light grows from the hole out to the edge, every 1.8 seconds, using each LED's real distance from the centre. |
| 3 | **Icing drip.** A slow band of light slides from the top of the donut to the bottom over 7 seconds, with a wavy lower edge (some "drips" hang lower than others) and a fading trail. |
| 4 | **All off.** The board stays awake (and still obeys the badge); use the OFF switch position to really switch off. |

**The power switch** has three positions. In the middle **OFF** position the
firmware sets every LED to zero, puts the LED chip into its own "software
shutdown", and puts the module into its deepest sleep. Sliding the switch out
of OFF wakes it and it starts again from the power-on glow in mode 0 (it does
not remember the last mode).

**The badge can take over the lights** over I2C (details below), or just
pick one of the built-in modes. As soon as the badge sends a valid light
command the add-on stops its own show and shows what the badge asks for. If
the badge goes quiet for 5 seconds the add-on goes back to its own show.
Pressing the mode button also takes control back.

## The brightness cap (a safety limit)

A badge can give an add-on only about 50 mA (the SAO++ rule). All 144 LEDs
at full brightness would need roughly ten times that. So **every picture the
board shows, the badge's included, passes through a current cap**: the
firmware adds up how bright all the LEDs are, estimates the current, and if
the estimate is over the limit it dims the whole picture evenly until it
fits. A picture that is already under the limit is not changed.

The numbers, and how sure they are:

- **Each LED at full brightness: 3.2 mA on average.** This is the LED chip's
  datasheet figure for the 20 kOhm resistor on this board (it already allows
  for the chip lighting only one ninth of the LEDs at any instant). It is the
  datasheet's *typical* value, not a maximum, and it has **not been
  measured** on this board.
- **Current is proportional to brightness** (datasheet).
- **Limit for the LEDs: 25 mA.** Worked out as 50 mA allowed, minus about
  20 mA guessed for the XIAO itself (not measured), minus 2.2 mA for the LED
  chip (datasheet), minus a little margin.

What that means in practice: the whole donut lit evenly comes out at about
5 % brightness (13 of 255), or about 7 LEDs at full. That is stricter than
the rough guide in `../README.md` ("all 144 at about 10 %, or about a dozen at
full, near 40 mA"), because that guide counted the LEDs only and left nothing
for the XIAO. The animations are designed to light only part of the donut at
a time, so the lit part can be brighter.

The two numbers are `LED_FULL_AVG_UA` and `LED_BUDGET_UA` in
`donut-core/src/budget.rs`. **Measure the board's current from a badge before
raising either.** The cap is the same on USB or a LiPo: the XIAO cannot tell
which power source the switch has chosen.

## Which XIAO?

Any of the three. The C3 is the main target. All three build from this one
folder; you choose the chip when you build. Use the matching command below
for the module actually soldered to your board: firmware for one chip will
not run on another.

## Building and flashing

You need Rust and `espflash` (`cargo install espflash`). Plug the XIAO into
USB-C (switch on USB-BAT, and **not on a badge** if the switch is on SAO).
Run these from the `donut-fw` folder.

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
  `espflash flash --chip esp32c3 target/riscv32imc-unknown-none-elf/release/donut-fw`
  (C6: `--chip esp32c6 target/riscv32imac-unknown-none-elf/release/donut-fw`;
  S3: `--chip esp32s3 target/xtensa-esp32s3-none-elf/release/donut-fw`).
- If the module does not show up for flashing, hold BOOT while plugging in USB.
- Plain `cargo build` fails on purpose with a message telling you to pick a chip.
- The S3 build prints one linker notice ("LOAD segment with RWX
  permissions"). It is a notice about the memory layout esp-hal uses, not an
  error.

Tests of the behaviour logic run on any PC, no board needed:

```
cd donut-core
cargo test
```

The serial log says `LED driver IS31FL3731 ready at 0x74` once the LED chip
has answered, or `LED driver did not answer` (retried every second) if not.

## Pin map

| Job | XIAO pin | C3 | C6 | S3 |
|---|---|---|---|---|
| LED chip SDA (private bus; 1.3 kOhm pull-up R5 on the board) | D10 | GPIO10 | GPIO18 | GPIO9 |
| LED chip SCL (private bus; 1.3 kOhm pull-up R4 on the board) | D3 | GPIO5 | GPIO21 | GPIO4 |
| Badge I2C SDA | D4 | GPIO6 | GPIO22 | GPIO5 |
| Badge I2C SCL | D5 | GPIO7 | GPIO23 | GPIO6 |
| Power switch "OFF" sense (high = OFF; internal pull-down) | D1 | GPIO3 | GPIO1 | GPIO2 |
| Mode button = module's BOOT button (active low; internal pull-up) | BOOT | GPIO9 | GPIO9 | GPIO0 |
| SAO GPIO1, through 330 ohm (unused, left as input) | D7 | GPIO20 | GPIO17 | GPIO44 |
| SAO GPIO2, through 330 ohm (unused, left as input) | D6 | GPIO21 | GPIO16 | GPIO43 |

The D3 numbers were checked against Seeed's pin tables and other published
pinouts (C3: GPIO5, C6: GPIO21, S3: GPIO4); the rest are the same as Mysterio.

**Why the LED chip is driven "by hand".** The ESP32-C3 has only one I2C
controller, and it is busy answering the badge on D4/D5. So the firmware
talks to the LED chip on D10/D3 by switching the two pins itself ("bit-banged"
I2C, about 200-250 kHz; the chip allows up to 400 kHz). The C6 and S3 use the
same code, so there is one path to test. One full update of all 144 LEDs
takes roughly 6-7 ms, and the firmware sends one every 20 ms only when the
picture has changed.

## I2C commands

The add-on is an I2C target at 7-bit address **0x1C** (Hack-Man is 0x1A,
Mysterio 0x1B, so all three can share a badge). The badge supplies the
pull-up resistors; the firmware switches the module's own pull-ups off.
Every command is 4 bytes; one write may contain up to 8 commands back to back
(32 bytes).

| Bytes | Meaning |
|---|---|
| `[0x10, n, level, x]` | Cue LED number *n* (0..143) at *level* (0 = off, 255 = full). Not shown until latched. |
| `[0x11, level, x, x]` | Cue every LED at *level*. Not shown until latched. |
| `[5, x, x, x]` | Clear all cues (to off). Not shown until latched. |
| `[6, x, x, x]` | Latch: show the cued LEDs. |
| `[7, brightness, x, x]` | Brightness for cued LEDs, 0 = off, 255 = full. Takes effect at once. Starts at 255. |
| `[0x90, n, level, x]` | Like `0x10`, but ignores the brightness setting. |
| `[0x91, level, x, x]` | Like `0x11`, but ignores the brightness setting. |
| `[8, mode, x, x]` | Stop taking over and run built-in mode 0..4 (table above). |

Commands 5, 6 and 7 have the same numbers and meaning as on Hack-Man and
Mysterio. Their colour commands (0..4 and 128..132) are **not** valid here,
so a badge driver aimed at the wrong address does nothing. Anything invalid
(including LED numbers above 143 and mode numbers above 4) is ignored and
does not keep I2C mode alive.

- **LED numbers** follow the maker's order: 0..71 are DA1..DA72 (his
  LED1..LED72), 72..143 are DB1..DB72 (his LED73..LED144). Where each one
  sits on the donut (position and angle) is listed in
  `../hardware/matrix.json`.
- **Levels** go straight to the LED chip (linear in current; the built-in
  modes add their own brightness curve, the badge's levels do not).
- **The brightness cap still applies** to whatever the badge sends, the
  "ignore brightness" commands included. Asking for every LED at full gets
  every LED at about 13 of 255.
- **Reading** from 0x1C returns 4 status bytes, as on Hack-Man and Mysterio:
  version major, version minor, state (0..4 = mode number, 0x80 = I2C mode,
  0x40 = still booting), current I2C brightness. On the S3 the answer can be
  one transaction out of date.
- Entering I2C mode starts from all-off; the brightness setting is
  remembered.

Example (MicroPython on the badge), light LED 0 and LED 72 at level 100, then
switch to the ripple mode a few seconds later:

```
i2c.writeto(0x1C, bytes([0x10,0,100,0, 0x10,72,100,0, 6,0,0,0]))
i2c.writeto(0x1C, bytes([8,2,0,0]))
```

## The LED chip: what was checked against its datasheet

Checked against the ISSI IS31FL3731 datasheet, Rev. D (April 2013), read for
this firmware:

- Address 0x74 with the AD pin on ground; 400 kHz maximum clock.
- The page/command register (0xFD); frame pages 0..7 and the function page
  0x0B; the frame layout (on/off 0x00-0x11, blink 0x12-0x23, brightness
  0x24-0xB3); the function registers used (configuration 0x00, picture
  display 0x01, display option 0x05, audio sync 0x06, breath 0x08/0x09,
  shutdown 0x0A, AGC 0x0B) and what their bits mean; that the chip
  auto-increments the register address; that frame contents are random at
  power-on (so the firmware writes every register of the frame it uses before
  switching the display on); that registers can be written during software
  shutdown and keep their contents.
- **Which LED pin is the "row".** The datasheet's LED-array drawing
  (Figure 8) puts each LED's **cathode** on the row pin. That is the
  convention `matrix.json` calls `frame`, so the firmware uses it (and a host
  test re-derives every LED's register from its pins with the datasheet's
  rule). If the first board shows LEDs lighting in the wrong places, flip
  `ROW_IS_CATHODE` in `donut-core/src/leds.rs`.
- LED current: 3.2 mA average per LED at full brightness with 20 kOhm
  (formula 64.7 / R_EXT); 2.2 mA chip supply current; about 230 microamps in
  software shutdown.

Not checked: nothing in the register map was taken from memory alone.
The current figures above are typical values; the datasheet gives no
maximum.

## How the code is laid out

- `donut-core/`: everything about *behaviour*, no hardware code, tested on a
  PC (77 tests):
  - `leds.rs` + `led_table.rs`: the LED map. `led_table.rs` is generated from
    `../hardware/matrix.json` by `gen_led_table.py` (run
    `python3 gen_led_table.py` after changing the JSON); a test re-reads the
    JSON and fails if the table is out of date.
  - `budget.rs`: the current cap.
  - `is31fl3731.rs`: the LED chip's register sequence, tested against a
    model of the chip's registers.
  - `bitbang.rs`: the hand-driven I2C for the LED chip, tested against a
    simulated chip that watches the two wires bit by bit.
  - `anim.rs`, `modes.rs`: the animations and modes.
  - `app.rs`, `i2c.rs`, `input.rs`: boot, button, switch, badge commands.
- `donut-fw/`: the thin hardware layer: reads pins, drives the two LED-bus
  pins (`driver_bus.rs`), runs the badge I2C target, sleeps.

**What is copied from Mysterio** (so fixes found on one board can be carried
to the others; compare with `diff`):

| File | Compared with Mysterio |
|---|---|
| `.gitignore` | identical |
| `donut-fw/build.rs` | identical |
| `donut-fw/rust-toolchain.toml` | identical |
| `donut-fw/.cargo/config.toml` | identical |
| `donut-core/src/input.rs` | identical |
| `donut-fw/src/i2c_target.rs` | one comment line (the address, 0x1C) |
| `donut-fw/Cargo.lock` | same dependency versions; crate names differ and donut-core uses `embedded-hal` (already in the tree via esp-hal) |
| `donut-fw/Cargo.toml` | same pinned versions and features; names, descriptions and one comment differ |
| `donut-fw/src/main.rs` | pins, badge I2C, deep sleep and panic handling are Mysterio's; the LED part is new |
| `donut-core/src/app.rs`, `i2c.rs` | same structure and rules; 144 single-colour LEDs and the extra "pick a mode" command |

Choices carried over: bare-metal `esp-hal` 1.2.2 (no ESP-IDF, stable Rust on
C3/C6); esp-hal's I2C target driver on the C3/C6, stepped by hand from the
main loop; the S3's I2C target programmed register by register because
esp-hal has none for the S3; exact dependency versions pinned; CPU at 80 MHz.
The chip restarts itself if the firmware ever crashes (panics).

## What still needs a real board

Nothing below has been tested. Each item is a thing only real hardware can
confirm:

1. **The current cap.** Measure the current from a badge (or a bench supply
   on the SAO pins) in every mode, with a badge driving all LEDs at full
   (`[0x91,255,0,0, 6,0,0,0]`), and with the module idle. Then set
   `LED_FULL_AVG_UA` and `LED_BUDGET_UA` from the measurements. The XIAO's
   own current (about 20 mA guessed) is part of the same 50 mA.
2. **LED positions.** Light LEDs one at a time from the badge
   (`[0x10,n,255,0, 6,0,0,0]`) and check each lands where `matrix.json` says.
   If they light in the wrong places, flip `ROW_IS_CATHODE`.
3. **The LED chip answering** on D10/D3 at 0x74, and the software I2C timing
   (look with a logic analyser: clock about 200-250 kHz, low phase over
   1.3 us). The 1.3 kOhm pull-ups should give clean edges.
4. **Animations by eye**: speeds, tail lengths and the drip may need tuning,
   and the cap may make them dimmer than hoped. The gamma curve is a simple
   square.
5. **Badge I2C target on the C3/C6** (esp-hal's driver): that it answers at
   0x1C and copes with the main loop being busy for about 7 ms while an LED
   update goes out. Writes longer than 32 bytes are not supported.
6. **Badge I2C target on the S3** (our own register code, no clock
   stretching): everything about it, including reads, and whether a badge
   write that arrives during an LED update is caught (the FIFO holds 32
   bytes).
7. **Hack-Man, Mysterio and Do Or Donut on one bus** at 0x1A/0x1B/0x1C.
8. **Internal I2C pull-ups really off** on the badge pins on all three.
9. **Deep sleep and wake on each chip**, and the **current in OFF with a
   LiPo**: the LED chip stays powered from the XIAO and its software shutdown
   still draws about 230 microamps (datasheet), more than the sleeping XIAO.
   The chip's SDB pin is tied on by a resistor, so firmware cannot cut that.
10. **The BOOT button as the mode button**: it is also the "download mode"
    button, so holding it while plugging in or resetting enters the flasher.
11. **Badge power into the XIAO's 3V3 pin** (see `../README.md`): a board
    question rather than a firmware one, but the first thing to check.
12. **Serial log** goes to the USB port; the XIAO's TX/RX pins (D6/D7, the
    SAO GPIO pins) are never driven.
