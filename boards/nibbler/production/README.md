# Nibbler rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nibbler-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nibbler-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (`NPTH.drl`; there are no plated holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 60.0 × 75.0 mm; panel 137.0 × 177.0 mm | |
| Thickness | 1.6 mm | the eye LEDs shine through the board |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat |
| Solder mask / silkscreen | **Your choice; the 2018 colours are not recorded in the files.** White silkscreen is needed for the diaper and the eyes on the back | the art is drawn as mask over bare board, bare board (eyes, mouth, feet) and bare gold copper (cape, collar). Check a photo on the hackaday.io page before ordering |
| Copper | 1 oz | |
| Minimum track / gap | 0.25 mm / 0.3 mm (design rules allow 0.15 mm) | the LED supply passes between the connector's pins and up the stalk as a 0.25 mm track |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must point to the arrow printed next to it (down, toward the foot); the closed end goes toward the thin silkscreen line across the chest. The large round pad under it gets **no solder**.
3. **D1 to D3** are reverse-mount LEDs: lens faces **into** the board.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes. It sits at a 4° angle to follow the curve of the head.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D3 white LED | C575513 | in stock (56,700). "Extended" part at JLCPCB: a small one-time loading fee |
| R1–R3 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py nibbler`. `panel/nibbler-panel.kicad_dru` is a hand-kept copy of the board's two design-rule exceptions for the renumbered panel parts (the panel tool does not copy it); keep it in step with `hardware/nibbler.kicad_dru`. Panel DRC: 0 errors, 0 unconnected; 64 warnings (36 art footprints whose libraries are not installed, 28 = 4 × the board's 7 silkscreen overlaps).

After snapping boards out, each tab leaves a small rough spot on the edge (right side of the head, the bump right of the switch, the right foot, the bottom of the left foot, the left hand, the right side of the body). A few strokes with a file cleans it up. No tab touches the cape (it is gold copper on the front) or the stalk.

The switch knob sticks about 0.75 mm out of the top of each head into the routed slot; that is intended.

## Regenerating

```
python3 boards/nibbler/hardware/fix_outline.py
python3 tools/gen_schematic.py nibbler
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nibbler/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nibbler
python3 tools/export_fab.py nibbler
```
