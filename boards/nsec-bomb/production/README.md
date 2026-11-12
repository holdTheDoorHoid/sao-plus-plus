# NorthSec Bomb rev A — ordering files

> Design-checked only. No board has been built from these files yet, and the question of NorthSec's logo on the back is open (see [../README.md](../README.md)). Order a small first batch (5–10) before any production run, and go through the prototype checklist in the README.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nsec-bomb-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nsec-bomb-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers. The eight square wire pads on the front (J2–J9) are bare copper: they are in the Gerbers but not in the BOM or placement files, because nothing is placed on them by the factory.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill files (five 0.3 mm plated vias, two 0.9 mm unplated holes for the switch pegs).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 54.0 × 38.0 mm; panel 125.0 × 103.0 mm | |
| Thickness | 1.6 mm | the LEDs shine through it |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; the display digits and wire pads are bare copper on the art side |
| Solder mask / silkscreen | **Red mask, white silkscreen** (as drawn in `art/nsec-bomb-front.svg`) | dynamite; red mask also passes the red LEDs' light |
| Copper | 1 oz | |
| Vias | **tented** (covered by mask both sides) | five small vias, all visible from the front otherwise |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the outline has rounded ends and a notch each side |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **top edge** of the board (toward the "CR2032 + UP" lettering and arrow); the closed end goes toward the bottom edge, where the switch SW1 is. The large round pad under it gets **no solder**.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the bottom edge; its knob points out of the bottom edge.
4. **D1–D4** are reverse-mount LEDs: lens **down**, facing the board.
5. **J2–J9** (eight 1.6 mm square pads on the top side) get **no solder paste and no part**; the buyer solders wires to them by hand.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## About the panel file

`panel/nsec-bomb-panel.kicad_pcb` is made by `tools/panelize.py nsec-bomb` from `panel.json` (five break-off tabs per board: three on the top edge, two on the bottom edge either side of the switch). Its DRC: 0 errors, 0 unconnected. The only warnings are 80 "footprint library not configured" notices, because the panel folder has no library table of its own; they say nothing about the copper.
