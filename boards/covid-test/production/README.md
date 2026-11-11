# COVID-19 Test rev A — ordering files

> Design-checked only. No board has been built from these files yet, and the maker's permission is pending (see [../README.md](../README.md)). Order a small first batch (5–10) before any production run, and go through the prototype checklist there.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `covid-test-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `covid-test-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and two drill files (`NPTH.drl` for the switch pegs; `PTH.drl` for the two 0.3 mm vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 16.0 × 50.0 mm; panel 55.0 × 133.0 mm | |
| Thickness | 1.6 mm | the LEDs shine through the board |
| Surface finish | **ENIG** | the coin cell rests on a bare copper contact; ENIG keeps it clean and flat |
| Solder mask / silkscreen | Your choice; the maker's colour is not recorded in his files. White silkscreen (the shading is silkscreen) | |
| Vias | 0.3 mm hole, 0.6 mm pad, **tented (covered) both sides** | they must not show on the front |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. Its **open side faces the left edge** (seen from the front, i.e. the right edge seen from the back, the side with the "CR2032" label); its closed end sticks out about 3 mm past the opposite edge. The large pad under it gets **no solder**.
3. **D1, D2** are reverse-mount LEDs: lens faces **into** the board.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob sticks 0.75 mm past the top edge.
5. **U1** pin 1 is at the corner marked by the small triangle.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | Source | Note |
|---|---|---|
| J1 connector | LCSC C492445 | in stock (2026-11-10) |
| BT1 cell clip | LCSC C7501066 | in stock (2026-11-10) |
| D1, D2 red LED | LCSC C125107 | in stock (2026-11-10) |
| R3, R4 1.3 kΩ | LCSC C22767 | in stock (2026-11-10) |
| C1, C2 100 nF | LCSC C14663 | in stock (2026-11-10) |
| **U1 TI LMC555CMX/NOPB** | LCSC number **not yet looked up** | new part for SAO++ |
| **R1, R2 3.3 MΩ 0603 (UNI-ROYAL 0603WAF3304T5E)** | LCSC number **not yet looked up** | new part for SAO++ |
| **SW1 switch, C&K PCM13SMTR** | LCSC C221842 | **out of stock at LCSC** (2026-11-10); Digikey 401-2017-1-ND. This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket, held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge (two on the top edge either side of the switch knob, two on the left edge, one on the bottom-left). 5 mm rails top and bottom carry the fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py covid-test`.

- The slot is **3.5 mm** instead of the usual 2 mm: the coin-cell clip's closed end hangs 3.1 mm past each board's right edge, over the slot.
- No tab on the right edge: the cell's supply track runs 0.3 mm from that edge, then the clip sticks out.
- Panel DRC: 0 unconnected; every mouse-bite hole is at least 0.25 mm from copper. It reports 44 "hole inside courtyard" errors, all from keep-out boxes that reach past the board edge: 40 from the switch's box (it includes the knob, which sticks out past the top edge; the holes are 1.4 mm or more from the knob itself) and 4 from the clip's box (one hole of the bottom tab is 0.28 mm from the clip's outline; the cell itself is not fitted at the factory). The hand-written `panel/covid-test-panel.kicad_dru` carries the board's art rule.

After snapping boards out, each tab leaves a small rough spot on the edge. A few strokes with a file cleans it up.

## Regenerating

```
python3 tools/gen_schematic.py covid-test
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/covid-test/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py covid-test
python3 tools/export_fab.py covid-test
```
