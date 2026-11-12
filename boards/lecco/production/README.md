# Lecco Postcard rev A — ordering files

> Design-checked only. No board has been built from these files yet, and davedarko's permission is still pending (see [../README.md](../README.md)). Order a small first batch (5–10) before any production run, and go through the prototype checklist in the README.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `lecco-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `lecco-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, and the board outline (`Edge_Cuts.gm1`). The single board has **no holes at all** (no vias, no switch pegs), so its zip has no drill file; the panel zip's drill file has only the 144 mouse-bite and tooling holes.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 64.8 × 48.0 mm; panel 146.6 × 123.0 mm | the maker's 54 × 40 mm postcard scaled up 1.2× |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** suggested | LECCO on the front is bare copper showing through the mask; ENIG keeps it gold |
| Solder mask / silkscreen | **Dark green mask, white silkscreen** suggested (not recorded in the maker's files; matches his renders) | the engraving is white silkscreen on the mask |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | rounded corners |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1** is a **reverse-mount** LED (Lite-On LTW-C230DS): it sits lens-down over the board and shines *through* it. Pad 1 is the cathode. Its polarity mark is on the assembly (fab) layer, not the silkscreen, because the silkscreen would fall on the bare-board ITALY window. Please check its rotation in your placement preview.
3. Please confirm all part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| D1 white reverse-mount LED | C575513 | in stock |
| R1 1.3 kΩ | C22767 | in stock |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by seven break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the top edge, two on the bottom, one on the left, two on the right (one above and one below the connector). 5 mm rails top and bottom carry three fiducials and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py lecco`. The art rule for the panel is in `panel/lecco-panel.kicad_dru` (hand-written copy; the panel tool does not copy it). Panel DRC: 0 errors, 0 unconnected; the closest mouse-bite hole is 0.30 mm from any copper.

After snapping boards out, each tab leaves a small rough spot on the edge; a few strokes with a file cleans it up.

## Regenerating

```
python3 tools/gen_schematic.py lecco
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/lecco/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py lecco
python3 tools/export_fab.py lecco
```
