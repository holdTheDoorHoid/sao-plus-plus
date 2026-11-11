# Frida rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `frida-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `frida-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (`NPTH.drl`; there are no plated holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 50.8 × 79.6 mm; panel 118.6 × 186.2 mm | |
| Thickness | 1.6 mm | the flower LEDs shine through the board |
| Surface finish | **ENIG** | the gold rim on the front is bare copper art, and the coin cell rests on a bare copper disc; ENIG keeps both clean and flat |
| Solder mask / silkscreen | **Your choice; the 2018 colours are not recorded in the files.** White silkscreen is needed for the face | the face is white silkscreen on dark mask, framed by the bare gold rim; check a photo of the original on hackaday.io before ordering |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. Its closed end must face the connector J1 (toward the thin silkscreen line under J1); its open side faces the bottom edge of the board. The clip's printed arrow is cut off by the board edge, so please follow this note. The large round pad under it gets **no solder**.
3. **D1 to D5** are reverse-mount LEDs: lens faces **into** the board, over the small unmasked window.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes. A track runs under the switch body; please make sure no solder bridges form under it.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D5 red LED | C125107 | in stock (54,960) |
| R1–R5 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py frida`. `panel/frida-panel.kicad_dru` carries the same two design rules as the single board, with the panel's part numbers.

After snapping boards out, each tab leaves a small rough spot on the edge (top of both lobes of hair, right side of the hair, right side above the earring, left earring, right of the chin). A few strokes with a file cleans it up. At each tab the front gold rim stops 0.55 mm short of the edge instead of 0.28 mm, so the mouse-bite holes do not cut into it.

The switch knob sticks about 0.85 mm out of the left side of each head into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py frida
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/frida/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py frida
python3 tools/export_fab.py frida
```
