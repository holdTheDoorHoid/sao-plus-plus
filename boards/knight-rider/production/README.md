# Knight Rider rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). **The button SW2 has no confirmed part number yet**, and four parts have no LCSC number (see below). Do not order assembly until those are filled in.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `knight-rider-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `knight-rider-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both are used for wiring on this board |
| Size | single 50.0 × 30.0 mm; panel 117.0 × 86.9 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | black mask, white silkscreen suit the car; the maker's colours are not recorded in the files | |
| Vias | **tented** (covered by mask) both sides, 0.3 mm drill / 0.6 mm pad, 36 per board | they sit on the art side |
| "Remove order number" | yes, or it gets printed on the art | |
| Assembly side | **both**: D1–D8 on the top (art side), everything else on the bottom | |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. **D1–D8** (red 0603 LEDs) go on the **top** side; all other parts on the **bottom**.
2. **JP1** is bare programming pads: **no part**. Leave that BOM line unmatched.
3. **BT1 (CR2032 clip)** fits its pads both ways round: its open end must face the top of the car (the roof). The large round pad under it gets no solder.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. **SW2** (button): part number still to be chosen; 6 × 3.5 mm two-pad SMD tactile switch, pads 6.3 mm apart.
6. Please confirm part rotations in your placement preview; they come straight from KiCad and have not been tried on a real line.

## Parts with no LCSC number yet

U1 ATtiny85V-10SU, D1–D8 LTST-C191KRKT, D9 RB751S40T1G, SW2 (to be chosen). The other parts are the shared SAO++ parts already on [docs/parts.md](../../../docs/parts.md); the switch SW1 is out of stock at LCSC (see Mad Cat's notes).

## The panel

2 × 2 boards, each in a routed pocket (2 mm slot), held by five break-off tabs per board with 0.5 mm mouse-bite holes on the edge:

- left and right sides of the car;
- middle of the roof;
- bottom of each wheel.

No tab is placed where the switch knob sticks out of the bottom edge. Rails top and bottom carry fiducials and tooling holes.

Panel DRC: 0 errors, 0 unconnected. Warnings:
- 100 "footprint not found in library", from the panel's mouse-bite and fiducial footprints;
- 40 art slivers;
- 8 footprint silk overlaps.

The board's extra keep-clear rule is repeated in `panel/knight-rider-panel.kicad_dru`.

## Regenerating

```
python3 tools/gen_schematic.py knight-rider
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/knight-rider/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py knight-rider
python3 tools/export_fab.py knight-rider
```
