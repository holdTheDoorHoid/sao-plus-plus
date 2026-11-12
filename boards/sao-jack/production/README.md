# SAO Jack rev A — ordering files

> Design-checked only. No board has been built from these files yet. Two things are still open (see [../README.md](../README.md)): the owner has not yet agreed to keeping this board as a through-hole solder kit, and the artwork is DEF CON's trademark. Order a small first batch (5–10) before any production run, and go through the prototype checklist in the README.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `sao-jack-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `sao-jack-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

**The BOM and placement files list three parts only: connector, switch, cell clip.** The four LEDs (D1–D4) and two resistors (R1, R2) are the kit: they go in a bag with the board and the buyer solders them. They are deliberately not in the assembly files.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill files. Per board: 38 plated holes (4 vias of 0.3 mm, 4 resistor holes of 0.7 mm, 8 LED holes of 0.9 mm, 22 decorative holes of 1.0 mm) and 2 unplated 0.9 mm holes for the switch pegs.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 35.6 × 37.4 mm; panel 88.3 × 101.9 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc; ENIG keeps that contact clean and flat. The eyes, smile, "3", "0" and the dots are bare copper too and will be gold-coloured (the maker's photos show a silver-coloured finish) |
| Solder mask / silkscreen | **Black mask, white silkscreen**, as in the maker's photos (not recorded in his files) | the skull, bones and four of the letters are white ink |
| Copper | 1 oz | |
| Vias | **tented** (covered by mask both sides) | four small vias; three are on the art side |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB. The maker's fab-layer box marking a place for it is gone: the connector sits there now |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | the three machine-placed parts are on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. Place **only J1, SW1 and BT1**, all on the **bottom** side. **Do not fit D1–D4, R1 or R2**, and leave their holes open (no solder): the customer solders those by hand.
2. All other plated holes without a designator (22 per board, 1.0 mm) are decoration. Leave them open.
3. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **top of the round head** (away from the connector J1); the closed end goes toward J1. The large round pad under it gets **no solder**.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the bottom edge; its knob points out of the bottom edge.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10, from docs/parts.md)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

**The kit bag is not part of the order and no parts are chosen for it:** four 3 mm (T-1) through-hole LEDs in two colours, and two 680 Ω 1/8 W axial resistors (body about 3.6 mm long, legs bent to 7.62 mm). See the README for what the maker used in 2022 and why the resistor value changed.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py sao-jack`. The board's keep-out rules for the panel are in `panel/sao-jack-panel.kicad_dru` (hand-written; the panel tool does not copy them).

Panel rule check (KiCad 10): 0 errors, 0 unconnected, 200 warnings: the single board's silkscreen and loose-dot warnings four times over, plus one per part saying the footprint libraries are not set up for the panel file. The "schematic matches board" test does not run on a panel. The panel's KiCad project file is not kept in the repository (house rule); `tools/panelize.py` writes it again with this board's settings. Checked without it, KiCad calls the 44 loose-dot items errors instead of warnings.

After snapping boards out, each tab leaves a small rough spot on the edge: at the top of the head (where the cell slides in), on both sides level with the dots, on the lower right side, and on the bottom edge under the resistors. There is no tab on the lower left side or on the bottom edge left of the resistors: a track runs just inside the edge there. A few strokes with a file cleans the spots up; do the one on the head before fitting a cell.

The switch knob ends 1.0 mm past the bottom edge of each board, into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py sao-jack
python3 boards/sao-jack/hardware/fix_schematic.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-jack/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py sao-jack
python3 tools/export_fab.py sao-jack
```

(`hardware/make_local_footprints.py` only needs running again if the two kit footprints are to be re-lifted from the maker's file.)
