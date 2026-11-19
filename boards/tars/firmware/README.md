# TARS firmware (SAO++ edition)

New Rust firmware for the TARS add-on rebuilt around a Seeed Studio XIAO ESP32 module. It does what the maker's Arduino sketches did on his RP2040 board, written fresh from reading them.

**Credit and licence.** The original TARS SAO and its sketches are by davedarko (Dave Darko), 2024, https://github.com/davedarko/TARS-SAO, under the MIT licence:

> Copyright (c) 2024 davedarko
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND (full text: `../original/LICENSE`).

This firmware is released under the same MIT terms. His touch sketches used Tod Kurt's TouchyTouch library (`original/Sketchbook/*/TouchyTouch.h`); nothing of it is used here, because the new board reads its touch areas with a touch chip instead.

## What it does

| | The maker's sketches (RP2040) | This firmware |
|---|---|---|
| Menu | Orange card with three rows, the middle one framed; up / down move it with a 1 kHz click; A opens the entry (`TARS_tone`) | The same layout and colours. His five entries (TV-B-Gone, Tesla-B-Gone, Trolololo, bingo, Piano) plus his three demo sketches as entries |
| TV-B-Gone, Tesla-B-Gone, Trolololo, bingo | Listed, but did nothing | Show "COMING SOON" for 1.5 s. (TV-B-Gone would need an infrared LED; neither board has one) |
| Piano | Each pad plays a note (C4 to A4, three times higher) and fills the screen with a colour while held; 10 s without a touch goes back to the menu | The same notes, colours and timeout, played push-pull on both speaker pins at 30 % duty as he did |
| Demos | Separate sketches: `hack_the_planet`, `TARS_chatGPT_free` (code rain), `TARS` (typing scroller) | Menu entries; any tap goes back. The phone screen in "hack the planet" says TARSNET instead of his "vodafone" (a company's trademark) |
| Cue light | Wired to GPIO7, never used | Lit while a pad is touched; the badge can switch it on or off |
| Badge (I2C) | Not used | I2C target at **0x27** (house address), commands below |
| Power switch | (no switch) | OFF: silence, blank the display, deep sleep until the switch moves |

There is no `maker-address` option: the maker's board never answered on the badge's I2C bus, so there is nothing to be compatible with.

## Badge commands (I2C address 0x27)

Each command is 4 bytes, `[0xE5, op, arg, 0x5E]`, several per write allowed.

| op | arg | meaning |
|---|---|---|
| 0x01 | 0-4 | show a screen: 0 menu, 1 piano, 2 hack the planet, 3 code rain, 4 scroller |
| 0x02 | MIDI note 1-127, 0 = stop | play a note until stopped (a touch takes over) |
| 0x03 | 0 off, 1 on, 2 automatic | cue light |
| 0x04 | 0-5 | act as if a pad were tapped: 0 A, 1 up, 2 B, 3 left, 4 down, 5 right |

A read returns 4 bytes: firmware version (major, minor), the screen shown, and the touch mask (bit 0 = A ... bit 5 = right).

## Pin map

| XIAO pin | C3 | C6 | Job |
|---|---|---|---|
| D10 | GPIO10 | GPIO18 | speaker side A (through R14 ∥ R15, 165 Ω) |
| D2 | GPIO4 | GPIO2 | speaker side B (through jumper JP1) |
| D7 | GPIO20 | GPIO17 | display clock |
| D3 | GPIO5 | GPIO21 | display data |
| D6 | GPIO21 | GPIO16 | display data/command |
| D0 | GPIO2 | GPIO0 | private I2C data (touch chip, Qwiic socket J4), 1.3 k pull-up |
| D8 | GPIO8 | GPIO19 | private I2C clock, 1.3 k pull-up |
| D9 | GPIO9 | GPIO20 | cue light, pulled low to light (on the C3 also the BOOT button) |
| D1 | GPIO3 | GPIO1 | high when the switch is on OFF |
| D4 / D5 | GPIO6 / GPIO7 | GPIO22 / GPIO23 | the badge's I2C (this board is a target) |

## Building

From `tars-fw/`: `cargo c3` (XIAO ESP32-C3) or `cargo c6` (XIAO ESP32-C6). Flash with `cargo flash-c3` / `cargo flash-c6` (needs `espflash`). Tests: `cargo test` in `tars-core/` (40 tests, all on the computer, no hardware). Both chip builds were compiled on 2026-11-11; nothing has been run on a board yet.

**The XIAO ESP32-S3 is not supported yet.** esp-hal 1.2.2 has no I2C target driver for it; Mr. Robot's firmware has a register-level one (`boards/mr-robot/firmware/mrrobot-fw/src/i2c_target.rs`, module `s3`) that could be added, plus the S3's own pin numbers. The S3 also draws more current on badge power.

## To check on the first board

1. **Display placement and colours.** The 80 x 160 panel sits at an offset inside the controller's memory (`X_OFFSET` 1 / `Y_OFFSET` 26 in `tars-core/src/st7735.rs`) and most of these panels need colour inversion and BGR order. If the picture is shifted, mirrored or has red and blue swapped, change those constants or `MADCTL`.
2. **Display without chip-select or reset pin.** The board ties the display's chip-select to ground and resets it with a resistor and capacitor at power-up (no XIAO pin was left). If the display starts up garbled after a USB re-flash (when its supply did not switch off), the firmware's software reset should fix it; if not, that is a hardware change.
3. **Touch chip registers.** The CAP1206 register numbers in `tars-core/src/cap1206.rs` follow the CAP12xx family map; check them and the product ID (0x67) against the datasheet, and tune `SENSITIVITY` on real pads.
4. **Speaker loudness.** 165 Ω in the loop keeps the peak current near 19 mA; it is quieter than the maker's direct drive.
5. **Current from a badge.** XIAO C3 at 80 MHz with no radio (about 20 mA), display backlight (about 20-30 mA, fixed by R9), touch chip (well under 1 mA), speaker (about 12 mA average while a note plays). That is more than the 50 mA SAO++ budget while a note plays.
