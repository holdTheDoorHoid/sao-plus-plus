# NorthSec Bandaid rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The back carries NorthSec's logo: see the note there before selling boards.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nsec-bandaid-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nsec-bandaid-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front copper (only the 46 round dots), back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (two 0.9 mm unplated holes for the switch pegs; there are no vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 68.0 × 26.0 mm; panel 153.0 × 79.0 mm | |
| Thickness | 1.6 mm | the LED shines through it |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc, and the 46 dots on the front are bare copper: gold with ENIG |
| Solder mask / silkscreen | **White silkscreen**; mask colour is the owner's choice | the gauze pad is white ink; the strip is the mask colour |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | rounded corners |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side. Nothing is placed on the top side; the 46 round gold dots there are art.
2. **R2 and R3 are NOT FITTED.** They are not in the BOM or the placement file. Their four pads get solder paste from a standard stencil; that is fine, leave them empty.
3. **D1** is a **reverse-mount** LED (Lite-On LTST-C230KRKT): the lens faces **into the board**.
4. **D2** is a small diode (SOD-523): mind its direction; the end with the bar (cathode) points toward the middle of the board, away from the cell clip.
5. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **nearest short end of the board**; the closed end goes toward the connector J1. The large round pad under it gets **no solder**.
6. **SW1**: its two plastic pegs go in the two 0.9 mm holes and its knob points out of the long edge.
7. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10 / 11)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1 red LED | C125107 | in stock |
| D2 cell diode | C232576 | in stock |
| R1 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** Digikey 401-2017-1-ND, long lead time quoted. This part decides the schedule |

To build the version with NorthSec's pull-ups, add two more of the R1 part (C22767) at R2 and R3 by hand, or ask for a BOM with them in (one line in `hardware/build_board.py` and one in `hardware/fix_schematic.py`: empty the `NOT_FITTED` list, then regenerate).

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: one in the middle of each short end, two on the top edge and one on the bottom edge (front view). None sits on the switch, above the supply track that runs just inside the top edge over the connector, or beside the cell clip's solder tabs. 5 mm rails top and bottom carry three fiducials and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py nsec-bandaid`.

Panel DRC: 0 errors, 0 unconnected. 32 warnings, all the same: the panel folder has no library table, so KiCad cannot compare the parts with the libraries.

The switch knob ends 0.97 mm past the board edge, into the 2 mm routed slot; that is intended.

## Regenerating

```
python3 boards/nsec-bandaid/hardware/make_local_footprints.py     # only if the local footprint folder is missing
python3 tools/gen_schematic.py nsec-bandaid
python3 boards/nsec-bandaid/hardware/fix_schematic.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-bandaid/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nsec-bandaid
python3 tools/export_fab.py nsec-bandaid
```
