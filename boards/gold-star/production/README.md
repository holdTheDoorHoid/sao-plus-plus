# Gold Star rev A — ordering files

> Design-checked only. No board has been built from these files yet, and **one part is not chosen**: U2, the 74HC4017 counter, has no part number (see [../README.md](../README.md), owner decision 1). Order a small first batch (5–10) before any production run, and go through the prototype checklist there.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `gold-star-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `gold-star-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers. The BOM line for U2 has an empty part number: fill it in before uploading.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and two drill files (`NPTH.drl` for the two switch pegs; `PTH.drl` for the twelve 0.3 mm vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 47.4 × 47.7 mm; panel 111.9 × 122.5 mm | |
| Thickness | 1.6 mm | the LEDs shine through the board |
| Surface finish | **ENIG** | the star is bare plating, and the coin cell rests on a bare contact |
| Solder mask | Your choice; dark colours set the gold star off best. The maker's files name none | |
| Silkscreen | White. Back only: nothing is printed on the front | |
| Vias | 0.3 mm hole, 0.6 mm pad, **tented (covered) both sides** | they must not show on the front |
| Minimum track / gap | 0.2 mm / 0.2 mm | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. Its **open side faces the bottom edge** of the board (the edge with the printed arrow); its closed end is toward the connector. The large round pad under it gets **no solder**.
3. **D1–D10** are reverse-mount LEDs: lens faces **into** the board. The printed bar marks the cathode end.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob sticks 0.75 mm past the flat part of the edge.
5. **U1** (8 pins) and **U2** (16 pins): pin 1 is at the corner marked by the small printed triangle.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line; the ten LEDs sit at odd angles round a ring.

## Parts availability

| Part | Source | Note |
|---|---|---|
| J1 connector | LCSC C492445 | in stock (2026-11-10) |
| BT1 cell clip | LCSC C7501066 | in stock (2026-11-10) |
| D1–D10 red LED | LCSC C125107 | in stock (2026-11-10) |
| R3 1.3 kΩ, R2 330 Ω | LCSC C22767, C23138 | in stock (2026-11-10) |
| C1–C3 100 nF | LCSC C14663 | in stock (2026-11-10) |
| R1, R4, R5 3.3 MΩ 0603 (UNI-ROYAL 0603WAF3304T5E) | LCSC C26096 | number from docs/parts.md; stock and price not re-checked for this board |
| U1 TI LMC555CMX/NOPB | LCSC C90760 | number from docs/parts.md; stock and price not re-checked for this board |
| **U2 74HC4017, SOIC-16 narrow** | **not chosen** | not yet checked at any distributor |
| **SW1 switch, C&K PCM13SMTR** | LCSC C221842 | **out of stock at LCSC** (2026-11-10); Digikey 401-2017-1-ND. This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: top, bottom, left, and upper and lower right. None on the flat where the switch knob is, none beside an LED. 5 mm rails top and bottom carry the fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py gold-star`.

- Panel DRC: 0 errors, 0 unconnected. 108 warnings: 92 "footprint library not found" (the panel folder has no library table; the footprints are inside the file) and 16 copper slivers (the single board's four, times four).
- The nearest track to any tab is the LEDs' shared return ring, 1.0 mm inside the edge; the mouse-bite holes reach 0.25 mm in.

After snapping boards out, each tab leaves a small rough spot on the edge. A few strokes with a file cleans it up; do the bottom one properly, the coin cell slides in over it.

## Regenerating

```
python3 boards/gold-star/hardware/extract_art.py
python3 tools/gen_schematic.py gold-star
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/gold-star/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py gold-star
python3 tools/export_fab.py gold-star
```
