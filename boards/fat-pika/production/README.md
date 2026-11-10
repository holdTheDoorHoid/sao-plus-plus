# Fat Pika rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `fat-pika-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `fat-pika-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (`NPTH.drl`; there are no plated holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 70.1 × 75.1 mm; panel 157.2 × 177.2 mm | |
| Thickness | 1.6 mm | the cheek LEDs are sized to shine through this |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat |
| Solder mask / silkscreen | **Yellow mask, black silkscreen** matches the 2018 original | PCBWay offers black-on-yellow. JLCPCB prints white silk on yellow, which will not look like the original; ask before ordering there |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must point to the arrow printed next to it; the closed end goes toward the thin silkscreen line. The large round pad under it gets **no solder**.
3. **D1, D2** are reverse-mount LEDs: lens faces **into** the board.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1, D2 LED | C125107 | in stock |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py fat-pika`.

After snapping boards out, each tab leaves a small rough spot on the edge (left cheek, top of head, tail, belly, lower right). A few strokes with a file cleans it up.

## Regenerating

```
python3 tools/gen_schematic.py fat-pika
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad boards/fat-pika/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py fat-pika
python3 tools/export_fab.py fat-pika
```
