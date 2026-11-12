# DC619 EEPROM rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The memory chip (U1) is a candidate part that the owner has not approved yet.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `dc619-eeprom-gerbers.zip` | `single/` |
| Bare boards, 6-up panel | `dc619-eeprom-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 … J601), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill files (two 0.3 mm plated vias per board; the panel adds its tooling and mouse-bite holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 24.0 × 24.0 mm; panel 96.0 × 75.0 mm | |
| Thickness | 1.6 mm | the lights shine through the board; the design assumes 1.6 mm |
| Surface finish | ENIG preferred | house standard; HASL would also work here (no cell contact on this board) |
| Solder mask / silkscreen | any colour; white silkscreen | the two light windows are bare board, so the mask colour does not tint the light |
| Copper | 1 oz | |
| Vias | **tented** (covered by mask both sides) | two small vias per board, one of them on the front face |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the front | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 6 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | rounded corners |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1, D2** are reverse-mount LEDs: the lens faces the board (down into the bare window), not up.
3. **J1** is a shrouded box header with no locating pegs; its key slot faces the top edge of the board (the edge with "DC619 EEPROM SAO++ rA" on the back).
4. Please confirm part rotations in your placement preview before running, **U1 (SOT-23-5) in particular**. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock (checked 2026-11-10) |
| U1 EEPROM, IDCHIP AD24C02 | C5125083 | 30,090 in stock, $0.0387 @100, reel of 3,000 (checked 2026-11-11). Candidate part, not yet approved |
| C1 100 nF | C14663 | in stock (2026-11-10) |
| R1, R2 1.3 kΩ | C22767 | in stock (2026-11-10) |
| D1, D2 red LED | C125107 | in stock (2026-11-10) |

No switch, cell clip or diode on this board, so the out-of-stock switch does not hold it up. In the PCBWay BOM the manufacturer column for U1 is empty (the shared export tool does not know the maker yet): it is IDCHIP.

The chips arrive blank. Writing the three ID bytes is a separate step after assembly (see the main README).

## The panel

3 × 2 boards, each in its own routed pocket (2 mm slot), held by four break-off tabs (one in the middle of each side) with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py dc619-eeprom`. The board has no extra design rules, so the panel needs no rule file of its own.

After snapping boards out, each tab leaves a small rough spot in the middle of each side; a few strokes with a file cleans it up.
