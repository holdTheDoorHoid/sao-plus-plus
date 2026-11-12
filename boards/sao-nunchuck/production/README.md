# SAO Nunchuck rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) and go through the prototype checklist in [../README.md](../README.md) before any production run.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `sao-nunchuck-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `sao-nunchuck-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401), so the panel BOM and placement files only match the panel Gerbers.

There is exactly **one part to place**: the connector J1. The gold fingers at the top (X2) are board copper. The two small 4-pin pad groups near the top corners (X3, X4, Qwiic) are in the Gerbers but not in the BOM or placement files and have no solder-paste openings: nothing is placed on them.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`) and one drill file (16 plated 0.3 mm vias, all the maker's).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 38.1 × 50.8 mm; panel 93.2 × 128.6 mm | |
| Thickness | **1.6 mm** | the top edge is a plug-in tongue: a Nunchuck plug grips the board itself. The maker's stack-up is 1.6 mm. Do not change it |
| Surface finish | **ENIG** (gold) | the five fingers are sliding contacts, and the front art is bare copper |
| Gold fingers / bevelled edge option | **No** | "Gold fingers" at a fab usually means hard gold plus a 30–45° bevel on one straight edge. The tongue sits inside a notch, so that option does not apply; plain ENIG is what the maker's boards had as far as the files show |
| Solder mask / silkscreen | **Black mask, white silkscreen** (as in the maker's photo; not recorded in his files) | |
| Copper | 1 oz | |
| Vias | as in the files | the maker's 16 small vias, in a band across the front just above the chain |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | the one part is on the back |
| Board outline | milled (routed), not V-cut | the notch has inside corners; the narrowest slot is 3.1 mm |

## Notes for the assembler (paste into the order remarks)

1. One part, J1, on the **bottom** side. Its key slot faces the top of the board (the edge with the notch).
2. **X3 and X4** (two 4-pin + 2-tab pad groups near the top corners) get **no paste and no part**.
3. Keep solder and flux off the five gold fingers on the tongue in the top notch (both sides).
4. Please confirm J1's rotation in your placement preview. The rotation value comes straight from KiCad and has **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 connector, XFCN BH254VS-6P | C492445 | listed in stock when docs/parts.md was checked (2026-11-10); re-check before ordering |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs (two on each side, two on the bottom) with 0.5 mm mouse-bite holes on the board edge. No tab touches the top edge, so the notch and tongue come out clean. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py sao-nunchuck`. The panel's rules are in `panel/sao-nunchuck-panel.kicad_dru` (hand-written; the panel tool does not copy the board's).

Panel DRC: 0 errors, 0 unconnected. 24 warnings: 20 are "footprint library not configured" (the panel has no library table of its own), 4 are the maker's 'SAO NUNCHUCK' title touching the board edge, as on the single board.

After snapping boards out, each tab leaves a small rough spot on the edge. A few strokes with a file cleans it up.

## Regenerating

```
python3 tools/gen_schematic.py sao-nunchuck
python3 boards/sao-nunchuck/hardware/fix_schematic.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-nunchuck/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py sao-nunchuck
python3 tools/export_fab.py sao-nunchuck
```

`hardware/make_local_footprints.py` (run once, already done) lifts the two maker footprints out of his board file into `hardware/sao-nunchuck-local.pretty/`.
