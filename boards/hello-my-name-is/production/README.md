# Hello My Name Is rev A — ordering files

> Design-checked only. No board has been built from these files yet, and davedarko's permission is still pending (see [../README.md](../README.md)). Order a small first batch (5–10) before any production run, and go through the prototype checklist in the README.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `hello-my-name-is-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `hello-my-name-is-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill files (no plated holes at all; two 0.9 mm unplated holes for the switch pegs).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 44.0 × 37.4 mm; panel 105.0 × 101.8 mm | the maker's 40 × 34 mm board scaled 1.1× |
| Thickness | 1.6 mm | the LEDs shine through it |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat. The name window has no copper, so the finish does not show there |
| Solder mask / silkscreen | Any mask colour, **white silkscreen**. The maker ordered green, red and blue | the name window is bare board whatever the mask colour |
| Copper | 1 oz | |
| Order number | **"Specify a location"** at JLCPCB: the back carries the maker's `JLCJLCJLCJLC` marker, top corner, where it gets printed. Elsewhere (or with "remove order number") those letters print as they are | the maker's blue boards had the number printed on the front |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. Its **open** end must face the **left edge of the board in the top (front) view**, which is the right-hand edge when you look at the bottom side; the closed end faces the connector J1. The large round pad under it gets **no solder**.
3. **D1–D4** are reverse-mount LEDs (lens facing into the board) at 45-degree angles. Please check each one's polarity in your placement preview: pad 1 is the cathode.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the bottom edge; its knob points out of the bottom edge.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D4 white reverse-mount LED | C575513 | in stock |
| R1–R4 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: three on the top edge, two on the bottom edge (one below the cell clip, one right of the switch). The side edges have none, because each carries a wire 0.8 mm in from the edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py hello-my-name-is`. The board's keep-out exception for the panel is in `panel/hello-my-name-is-panel.kicad_dru` (hand-written; the panel tool does not copy it).

After snapping boards out, each tab leaves a small rough spot on the top or bottom edge. A few strokes with a file cleans it up.

The switch knob ends about 0.7 mm past the bottom edge, into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py hello-my-name-is
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/hello-my-name-is/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py hello-my-name-is
python3 tools/export_fab.py hello-my-name-is
```
