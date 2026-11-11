# Soot Sprite rev A — ordering files

> Design-checked only. No board has been built from these files yet, and davedarko's permission is still pending (see [../README.md](../README.md)). Order a small first batch (5–10) before any production run, and go through the prototype checklist in the README.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `soot-sprite-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `soot-sprite-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers. The four big square pads (TP1–TP4) are bare copper: they are in the Gerbers but not in the BOM or placement files, because nothing is placed on them by the factory.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill files (four 0.3 mm plated vias, two 0.9 mm unplated holes for the switch pegs).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 40.0 mm round (40.0 × 40.0); panel 97.0 × 107.0 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat. It also takes the hand-soldered LED legs well |
| Solder mask / silkscreen | **Black mask, white silkscreen** suggested (not recorded in the maker's files) | the face is copper under mask, so the mask colour *is* the sprite; the eyes are white silkscreen |
| Copper | 1 oz | |
| Vias | **tented** (covered by mask both sides) | four small vias; they must not show as bare spots on the face |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the board is round |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **top edge of the round board** (away from the connector J1); the closed end goes toward J1. The large round pad under it gets **no solder**.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the bottom edge; its knob points out of the bottom edge.
4. **TP1–TP4** (four 4 × 4 mm square pads) get **no solder paste and no part**; the buyer solders LED legs to them by hand.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

The 5 mm LEDs and the 3D-printed candies are not part of the order: the buyer adds them.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py soot-sprite`. The board's extra keep-out rules for the panel are in `panel/soot-sprite-panel.kicad_dru` (hand-written; the panel tool does not copy them).

After snapping boards out, each tab leaves a small rough spot on the round edge: at the top (where the cell slides in), and on both sides level with the middle of the cell and just above the foot pads. A few strokes with a file cleans it up; do it before fitting a cell.

The switch knob ends about 0.2 mm past the bottom of each circle, into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py soot-sprite
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/soot-sprite/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py soot-sprite
python3 tools/export_fab.py soot-sprite
```
