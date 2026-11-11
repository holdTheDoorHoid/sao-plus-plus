# Big Green rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `big-green-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `big-green-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (`NPTH.drl`; there are no plated holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 80.0 × 72.0 mm; panel 177.0 × 171.0 mm | |
| Thickness | 1.6 mm | the pupil LEDs shine through the board |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat |
| Solder mask / silkscreen | **Your choice; the 2018 colours are not recorded.** White silkscreen is needed for the eyes, teeth and the dragon | The name and the face suggest a green board; check a photo of the original on hackaday.io before ordering |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must point to the arrow printed next to it (toward the top of the head); the closed end goes toward the thin silkscreen line. The large round pad under it gets **no solder**.
3. **D1, D2** are reverse-mount LEDs: lens faces **into** the board.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1, D2 white LED | C575513 | in stock (56,700). "Extended" part at JLCPCB: a small one-time loading fee |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py big-green`. Beside each tab, both copper layers stop 0.55 mm short of the edge (elsewhere 0.28 mm), so the mouse-bite holes never touch copper.

After snapping boards out, each tab leaves a small rough spot on the edge (top of the head, the outer edge of each ear near its tip, each side of the jaw, the point of the chin). A few strokes with a file cleans it up. No tab sits near the lettering or the switch.

The switch knob sticks about 0.7 mm out of the left side of each head into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py big-green
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/big-green/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py big-green
python3 tools/export_fab.py big-green
```
