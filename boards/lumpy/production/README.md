# Oh My Glob (LSP) rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `lumpy-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `lumpy-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and two drill files: `NPTH.drl` (the switch's two peg holes) and `PTH.drl` (two 0.3 mm vias in the mouth).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 50.8 × 71.4 mm; panel 118.5 × 169.7 mm | |
| Thickness | 1.6 mm | the star and crown-tip LEDs shine through the board |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc, and the crown is exposed gold art |
| Solder mask / silkscreen | **Your choice; the 2018 colours are not recorded.** White silkscreen is needed for the eyes, teeth and back lettering | Check a photo of the original on hackaday.io before ordering |
| Copper | 1 oz | |
| Via covering | **Tented** (vias covered with solder mask, both sides) | the two vias sit in the mouth art and must not show |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the board's right-hand edge (the "<" arrow printed beside the cell spot). The large round pad under it gets **no solder**.
3. **D1 and D2** are reverse-mount LEDs: lens faces **into** the board. D1 is red (crown tip), D2 is white (star).
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. BT1's placement angle is 269.9°, not 270°: that is a KiCad workaround, so place it square.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1 red LED | C125107 | in stock |
| D2 white LED | C575513 | in stock. "Extended" part at JLCPCB: a small one-time loading fee |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py lumpy`. The panel needs its own rules file, `panel/lumpy-panel.kicad_dru` (a hand-made copy of the board's, because the panel renumbers parts). Panel DRC: 0 errors, 0 unconnected.

After snapping boards out, each tab leaves a small rough spot on the edge: the left arm lobe, the lower left lobe, the bottom of the lower left lobe, the right lobe, and the tops of both shoulders. A few strokes with a file cleans it up. The front art steps back 0.55 mm from the edge at those six spots so the mouse-bite holes do not cut through it.

## Regenerating

```
python3 tools/gen_schematic.py lumpy
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/lumpy/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py lumpy
python3 tools/export_fab.py lumpy
```
(`production/panel/lumpy-panel.kicad_dru` is kept by hand: panelize does not touch it.)
