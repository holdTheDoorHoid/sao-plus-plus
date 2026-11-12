# NorthSec Diamond rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The back carries NorthSec's logo: see the note there before selling boards.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nsec-diamond-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nsec-diamond-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper (the front copper layer is empty), solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (two 0.9 mm unplated holes for the switch pegs; there are no vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | only the back carries copper, but 2-layer is the standard cheap stack |
| Size | single 52.0 × 46.0 mm; panel 121.0 × 119.0 mm | |
| Thickness | 1.6 mm | the LEDs shine through it |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | **White silkscreen**; mask colour is the owner's choice (a dark colour makes the facet lines read) | the facets are white ink, the lines between them are bare mask |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | slanted edges |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1, D2** are **reverse-mount** LEDs (Lite-On LTW-C230DS): the lens faces **into the board**.
3. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **bottom point of the gem**; the closed end goes toward the connector J1. The large round pad under it gets **no solder**.
4. **SW1** sits at 45° on a slanted edge; its two plastic pegs go in the two 0.9 mm holes and its knob points out of that edge.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1, D2 white LED | C575513 | in stock |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** Digikey 401-2017-1-ND, long lead time quoted. This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the top (table) edge, one on the left crown edge and one low on each pavilion edge, below the cell clip (front view). The crown edge with the switch has none. 5 mm rails top and bottom carry three fiducials and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py nsec-diamond`.

Panel DRC: 0 errors, 0 unconnected. 28 warnings, all the same: the panel folder has no library table, so KiCad cannot compare the parts with the shared library.

The switch knob ends 0.97 mm past the board edge, into the 2 mm routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py nsec-diamond
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-diamond/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nsec-diamond
python3 tools/export_fab.py nsec-diamond
```
