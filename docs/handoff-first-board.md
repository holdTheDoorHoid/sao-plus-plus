# Handoff: the first SAO++ board

Brief for the agent building board #1. The first board does double duty: it **builds the shared library** that every later board reuses, and it **proves** the parts marked `verify` in [parts.md](parts.md).

## Board

**Board to port:** _<set by the owner: name, original source link, original license>_

Before any layout: fill in `boards/<slug>/board.yml` `original:` and confirm the permission basis ([porting-guide.md §1](porting-guide.md)). If it is unclear, stop and ask the owner.

## Phase 1: shared library (`lib/`)

Build these from manufacturer drawings (link each drawing in the footprint description):

1. Footprints, back side: `SAOPP-CONN-01` (XFCN BH254VS-6P), `SAOPP-SW-01` (XKB SS-3235D-03-L3) and `SW-02`, `SAOPP-BAT-01` (TE BAT-HLD-001) and `BAT-02` (Keystone 3034), the LTST-S270 side-view LED, 0603 passives (KiCad stock is fine for those).
2. Symbols with fields: `SAOPP_ID`, `MPN`, `LCSC`, `Digikey`.
3. `lib/blocks/power-select.kicad_sch` as drawn in [standard.md §3](standard.md#3-power-sao--off--battery), with the series diode and ID EEPROM as optional (DNP) parts.
4. `lib/template/`: starter project using the block, house design rules, back-silk labels.

## Phase 2: verify the `verify` rows

Each item ends with the parts.md row updated (status → `chosen`, and what was checked):

- **SAO pin numbering**: confirm 1 VCC, 2 GND, 3 SDA, 4 SCL, 5 GPIO1, 6 GPIO2 from the v1.69bis diagram image (hackaday.io project 52950, log 159806); then delete the "Verify before first layout" note in standard.md.
- **CONN-01**: datasheet drawing (pads, any hold-down legs, height), key orientation vs. the badge socket. Find a drop-in second source for `CONN-02`.
- **SW-01**: pinout, and that the switch breaks before it makes (the two sources must never touch during a slide).
- **BAT-03**: overlay the LCSC clone holders on BAT-01's footprint.
- **R-01**: 1.3 kΩ gives ~1 mA; flag it for a bench brightness check on the first prototypes.
- **D-01**: only if this board has a microcontroller or uses SDA/SCL/GPIO.

## Phase 3: the board

Port per [porting-guide.md §2–4](porting-guide.md). Deliverables:

- KiCad 10 project in `boards/<slug>/hardware/`, ERC/DRC clean
- `production/`: BOM (with LCSC and Digikey columns) and placement file; Gerbers via `kicad-cli` (not committed)
- 3D render of front and back (PNG) in `boards/<slug>/docs/`
- a per-board cost estimate at 100 and 1000 units (parts only, live prices, dated)
- `board.yml` status `porting` → `prototype` only once a physical board exists

Work on branch `board/<slug>`, open a PR on `holdTheDoorHoid/sao-plus-plus`, and leave merging to the owner.

## Out of scope for board #1

Firmware, addressable LEDs, panelisation for a specific fab, ordering anything.
