# The SAO++ house standard

Every SAO++ board follows SAO v1.69bis electrically, plus the house rules below. The house rules are what make the boards share parts, tooling, and assembly setups, which is what makes them cheap to build in quantity.

Part numbers live in [parts.md](parts.md). This page refers to them by id (`SAOPP-…`).

## 1. SAO v1.69bis, as we apply it

Source: Hackaday, "Introducing the Shitty Add-On V1.69bis Standard" (2019-03-20), https://hackaday.com/2019/03/20/introducing-the-shitty-add-on-v1-69bis-standard/ and the hackaday.io project log 159806. The spec calls itself "not the official, final release". Where it is silent, SAO++ picks a rule and writes it down here.

| Pin | Signal | SAO++ rule |
|---|---|---|
| 1 | VCC 3.3 V | Goes only to the power-select switch, never straight to the load |
| 2 | GND | Common ground for both power sources |
| 3 | SDA | No pull-up on the add-on (the badge provides it) |
| 4 | SCL | No pull-up on the add-on |
| 5 | GPIO1 | ≥ 330 Ω series resistor if the add-on drives it (spec requirement) |
| 6 | GPIO2 | ≥ 330 Ω series resistor if the add-on drives it |

> **Verify before first layout:** the numbering above is the widely used one and matches the spec's wording ("GPIO1 and GPIO2 to the right"), but no source we could read printed a numbered table. The first board must check it against the spec diagram image and a known-good v1.69bis badge, then delete this note.

- **Signal levels:** design for 3.3 V. Nothing on the header may exceed 3.6 V.
- **Current:** the spec gives no real number. SAO++ boards budget **≤ 50 mA** from the badge, so they work on any badge.
- **GPIO roles, if used:** WS2812-style data on GPIO1; APA102 data on GPIO1 and clock on GPIO2; UART 115200 with GPIO1 = badge TX → add-on RX and GPIO2 = add-on TX → badge RX (the add-on stays silent until it receives something).
- **Identification EEPROM:** *not* part of v1.69bis. It is a community convention (AND!XOR reference designs; EEPROM at 7-bit address 0x50, byte 0 year, byte 1 maker id, byte 2 type id). SAO++ boards **may** fit one footprint for it, unpopulated by default, so the option costs nothing.
- **Unused pins:** leave SDA/SCL/GPIO unconnected on LED-only boards.

## 2. Connector

- **Add-on side:** 2×3, 2.54 mm, **shrouded and keyed SMD box header** (`SAOPP-CONN-01`), mounted on the **back** of the board, pins pointing away from the art. This is the gender the spec asks for on the add-on. It mates with the standard badge-side 2×3 socket.
- **No through-hole on the front.** The connector is SMD so the art side stays clean.
- **Mechanical strength:** an SMD connector is held on by its solder pads only. To compensate:
  - use the full-size pads from the shared footprint (do not shrink them)
  - keep the connector at least 3 mm from any board edge, with copper pour tied to GND around it so the board does not flex at the joint
  - put the header near the board's centre of mass, so the board does not lever on the joint when it hangs
- **Key orientation:** the key slot faces the board's **top edge** (the edge that is "up" when the badge is worn). Pin 1 is marked on the back silkscreen.

## 3. Power: SAO / OFF / BATTERY

Every board with a coin cell uses the shared power block (`lib/blocks/power-select`):

```
SAO pin 1 (3.3 V) ──── throw A ┐
         (no connection) throw B ├── common ──► board load (LEDs, MCU)
CR2032 (+) ─────────── throw C ┘
```

- **Switch:** 3-position SMD slide switch, side-actuated at the board edge (`SAOPP-SW-01`). Positions: **SAO** (badge power), **OFF**, **BATTERY**.
- **Why this layout:** the badge's 3.3 V and the coin cell sit on different contacts and are never connected to each other, in any position. A CR2032 is a non-rechargeable lithium cell; pushing current into it can make it leak, swell, or catch fire. This layout makes that impossible by construction, needs no extra parts, has no voltage loss, and draws zero current when OFF.
- **Not chosen:** diode "auto-switch" circuits. They pick badge power automatically, but they lose 0.2–0.3 V (enough to dim blue and white LEDs on a coin cell), and a plain Schottky diode leaks a little current back toward the cell.
- **Boards with a microcontroller or anything on SDA/SCL/GPIO:** the badge's I2C pull-ups can still feed a small current into the add-on's supply through the chip's protection diodes, even in BATTERY position, and that supply is the coin cell. These boards **must** add the series cell diode (`SAOPP-D-01`) right after the holder, and say so in the README. LED-only boards do not need it.
- **Battery:** CR2032 (`SAOPP-BAT-01` holder, back side). About 70–100 hours at 2 mA, so 6–8 days of 12-hour wear. CR2450/2477 last longer but are too heavy for a board hanging from one header.
- **Battery markings:** a clear "+" and "CR2032" on the back silkscreen next to the holder. Holders have no polarity protection.

## 4. LEDs

- **One package family for the whole project:** side-firing LEDs on the back, shining into the board edge or through cutouts. See `SAOPP-LED-*` in [parts.md](parts.md) for the chosen package and colour list.
- **Drive current:** about 1 mA per LED by default. That looks bright through FR4 and keeps coin cell life in days.
- **Colours and coin cells:** red, orange, yellow, and yellow-green work well from a coin cell. Blue, white, and true green need about 3 V and fade early as the cell drains. Boards may use them, but must say "best on badge power" in the README.
- **Blinking stretches battery life.** A 25 % blink duty roughly quadruples runtime and still looks bright.

## 5. Layout rules

- **Front = art only:** copper, mask, silk, and deliberate art vias. No components and no visible through-hole joints.
- **Back = everything else:** connector, switch, holder, LEDs, resistors, optional MCU.
- **Board:** 1.6 mm FR4, 2 layers, ENIG finish preferred (it looks better as exposed-copper art, and it solders flat SMD pads more reliably than HASL). Any colour.
- **Back silkscreen** carries: board name, "SAO++", revision, pin-1 marker, battery "+", switch labels (SAO / OFF / BAT), and the original maker credit.
- **Panel-friendly outlines:** add mouse bites or V-score points at the outline; avoid internal cutouts narrower than 1 mm.
- **KiCad 10**, using `lib/` footprints only (the global KiCad library is fine for passives).

## 6. Labelling a design "SAO++"

A board may carry the SAO++ name when it passes `tools/check_boards.py`, follows sections 1–5, and its `board.yml` status is `verified` or `released`.
