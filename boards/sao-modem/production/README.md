# SAO Modem 1.69bis rev A — ordering files

> Design-checked only. No board has been built from these files yet. Three parts (Q1, R7, R8) have **no distributor part number yet**: see "Parts availability". Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `sao-modem-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `sao-modem-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers. The round SYN pad (TP1) is bare copper: it is in the Gerbers but not in the BOM or placement files.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and one drill file (two 0.9 mm unplated holes per board for the switch pegs; there are no plated holes or vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | the front carries a little copper art |
| Size | single 87.7 × 43.0 mm; panel 192.4 × 113.1 mm | |
| Thickness | 1.6 mm | house standard (the 2022 board was 1.2 mm) |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; the "3", "0" and the eight squares on the front and "@hamster" on the back are bare copper and look gold |
| Solder mask / silkscreen | **Black mask, white silkscreen** | as in the maker's photos |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the outline is not rectangular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1–D6 are reverse-mount LEDs**: the lens faces the board. Cathode toward the printed bar.
3. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **nearest board edge** (away from the row of LEDs); the closed end goes toward LED D6. The large round pad under it gets **no solder**.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the top edge; its knob points out of the top edge.
5. **TP1** (round 2 mm pad marked SYN) gets **no solder paste and no part**.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock when the parts list was checked (2026-11-10) |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D6 red LED | C125107 | in stock |
| R1–R6 1.3 kΩ | C22767 | in stock |
| D7 cell diode RB751S40T1G | C232576 | in stock (checked 2026-11-11) |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |
| **Q1 DMP3085LSD-13** (Diodes Inc.) | **not looked up** | the maker's part. The LCSC column in the BOM files is empty: find it (or have the assembler source it) before ordering |
| **R7 4.7 kΩ 0603, R8 10 kΩ 0603** | **not looked up** | any maker's 0603 part of that value will do; the LCSC column is empty |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the shoulders of the lid, two on the bottom edge at the far left and right, one under the foot. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py sao-modem`. The panel's rule file is `panel/sao-modem-panel.kicad_dru` (a hand copy of the board's; the panel tool does not copy it). Panel DRC: 0 errors, 0 unconnected; 100 warnings, all "library not installed" or the maker's front art as on the single board.

After snapping boards out, each tab leaves a small rough spot; a few strokes with a file cleans it up. None is on the right-hand edge, where the cell slides in.

The switch knob ends about 1 mm past the top edge of each board, into the routed slot; that is intended.

## Regenerating

```
python3 boards/sao-modem/hardware/make_local_footprints.py
python3 boards/sao-modem/hardware/make_outline.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/extract_outline.py boards/sao-modem/hardware/.tmp/outline_scaled.kicad_pcb boards/sao-modem/hardware/outline.json
python3 tools/gen_schematic.py sao-modem
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-modem/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py sao-modem
python3 tools/export_fab.py sao-modem
```
