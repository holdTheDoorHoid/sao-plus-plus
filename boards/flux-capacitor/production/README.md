# Flux Capacitor rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). **The light colour is still the owner's choice** (red as drawn), and the light has no LCSC number yet (see below). Do not order assembly until that is filled in.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `flux-capacitor-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `flux-capacitor-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both are used for wiring on this board |
| Size | single 34.3 × 41.1 mm; panel 85.6 × 109.3 mm | the maker's board scaled up 1.35 times |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc, and the three cables and electrode rings on the front are bare copper meant to look gold |
| Solder mask / silkscreen | the maker's colours are not recorded in the files; a dark mask with white silkscreen suits the white Y | |
| Vias | **tented** (covered by mask) both sides, 0.3 mm drill / 0.6 mm pad, 20 per board. The three large electrode holes (1.2 mm drill) are bare on the front by design | |
| "Remove order number" | yes, or it gets printed on the art | |
| Assembly side | **both**: D1–D9 on the top (art side), everything else on the bottom | |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. **D1–D9** (1206 LEDs) go on the **top** side, cathode as marked; all other parts on the **bottom**.
2. **JP1** is bare programming pads: **no part**. Leave that BOM line unmatched.
3. **BT1 (CR2032 clip)** fits its pads both ways round: its **open end must face the bottom edge** of the board (away from the connector). The large round pad under it gets no solder.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. Please confirm part rotations in your placement preview; they come straight from KiCad and have not been tried on a real line.

## Parts with no LCSC number yet

D1–D9 Lite-On LTST-C150KRKT (red 1206). U1 (ATtiny85V-10SU, C152192) and D10 (RB751S40T1G, C232576) are the parts Knight Rider already uses. The other parts are the shared SAO++ parts on [docs/parts.md](../../../docs/parts.md); the switch SW1 is out of stock at LCSC (see Mad Cat's notes).

## The panel

2 × 2 boards, each in a routed pocket (2 mm slot), held by five break-off tabs per board with 0.5 mm mouse-bite holes on the edge:

- left side, below the switch;
- right side, at the top beside the right electrode;
- middle of the top edge;
- bottom edge, left and right of centre.

No tab is placed where the switch knob sticks out of the left edge. Rails top and bottom carry fiducials and tooling holes.

Panel DRC: 0 errors, 0 unconnected. Warnings: 76 "footprint not found in library" (the panel's own mouse-bite and fiducial footprints) and 12 thin slivers in the ground copper (3 per board).

The board's art rule is repeated in `panel/flux-capacitor-panel.kicad_dru`.

## Regenerating

```
python3 boards/flux-capacitor/hardware/extract_art.py
python3 boards/flux-capacitor/hardware/make_local_footprints.py
python3 tools/gen_schematic.py flux-capacitor
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/flux-capacitor/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py flux-capacitor
python3 tools/export_fab.py flux-capacitor
```
