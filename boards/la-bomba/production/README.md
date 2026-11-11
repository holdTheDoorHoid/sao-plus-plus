# La Bomba rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `la-bomba-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `la-bomba-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`, three closed paths: the bomb and the two holes in its wind-up key), and the drill file (`NPTH.drl`; there are no plated holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 70.0 × 72.5 mm; panel 157.0 × 171.9 mm | |
| Thickness | 1.6 mm | the eye and spark LEDs shine through the board |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc, and the wind-up key is bare gold on the front |
| Solder mask / silkscreen | **Your choice; the 2018 colours are not recorded.** White silkscreen is needed for the half-tone drawing on the back | Check a photo of the original on hackaday.io before ordering |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular, and the key has two holes |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The closed end must point toward the connector J1 (toward the thin silkscreen line); the open side faces the "Made By TwinkleTwinkie" lettering. The large round pad under it gets **no solder**.
3. **D1 to D4** are reverse-mount LEDs: lens faces **into** the board. D1–D3 are white, D4 is red.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes. It sits at an angle on the edge of the right foot; its knob must stick out past the edge.
5. **R4** has a track running between its two pads; that is intended.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line (SW1 at −106° and D4 at −30° are not right angles).

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D3 white LED | C575513 | in stock (56,700). "Extended" part at JLCPCB: a small one-time loading fee |
| D4 red LED | C125107 | in stock (54,960) |
| R1–R4 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py la-bomba`. The two holes in each wind-up key are milled with the rest of the outline.

After snapping boards out, each tab leaves a small rough spot on the edge (left side of the body, tip of the left foot, top of the body left of the fuse, outer side and bottom of the key, bottom of the right foot). A few strokes with a file cleans it up. No track runs along the edge at any tab, and the copper is pulled 0.6 mm back there.

The switch knob sticks 0.64 mm out of each right foot into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py la-bomba
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/la-bomba/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py la-bomba
python3 tools/export_fab.py la-bomba
```
