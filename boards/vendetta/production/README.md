# Guy Fawkes remembers (Vendetta) rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). **Permission from the maker is still pending; the owner chose on 2026-11-12 to publish these files, and has not decided whether to order** (see the README). The memory chip U1 has no LCSC number yet (see below). Before ordering, also read "Does the coin cell do anything?" in the README: the owner may prefer the simpler version without the switch, clip and diode.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `vendetta-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `vendetta-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | only the back copper is used; the front has no copper |
| Size | single 42.3 × 56.3 mm (the maker's board scaled 1.23×); panel 101.7 × 139.5 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | **white mask, black silkscreen** | the halftone mask on the front is drawn as dark print on a light face; the maker's colours are not recorded in his files |
| Vias | none | |
| "Remove order number" | yes, or it gets printed on the art | |
| Assembly side | **bottom only** | |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **R1–R4 are not fitted** (marked DNP). They are not in the BOM or the placement file; leave the pads empty.
3. **BT1 (CR2032 clip)** fits its pads both ways round: its **open end must face the top of the board** (toward the printed quote). The large round pad under it gets no solder.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. **U1** is the wide (208 mil / 5.3 mm body) SOIC-8 version of the CAT24C256, not the common narrow (150 mil) one.
6. Please confirm part rotations in your placement preview; they come straight from KiCad and have not been tried on a real line.

## Parts with no LCSC number yet

U1 CAT24C256XI-T2 (onsemi, SOIC-8 EIAJ). D1 RB751S40T1G is LCSC C232576. The other parts are the shared SAO++ parts on [docs/parts.md](../../../docs/parts.md); the switch SW1 is out of stock at LCSC (see Mad Cat's notes).

## The panel

2 × 2 boards, each in a routed pocket (2 mm slot), held by six break-off tabs per board with 0.5 mm mouse-bite holes on the edge:

- top of the forehead;
- both temples (above the switch on one side, above the badge-power track on the other);
- both cheeks;
- point of the chin.

No tab is placed where the switch knob sticks out, or along the edge where the badge-power track runs 0.6 mm inside the outline. Rails top and bottom carry fiducials and tooling holes.

Panel DRC: 0 errors, 0 unconnected. 48 warnings, all "footprint library not found" (the panel's mouse-bite, fiducial and tooling footprints and the maker's two art footprints, which come from libraries this project does not load). None of the 120 mouse-bite holes comes within 0.25 mm of copper (checked separately). The panel DRC takes about 25 minutes because of the 4 × 5,449 halftone dots.

The board's art rule is repeated in `panel/vendetta-panel.kicad_dru`.

## Regenerating

```
python3 tools/gen_schematic.py vendetta
python3 boards/vendetta/hardware/fix_schematic.py
python3 boards/vendetta/hardware/make_local_footprints.py      # only if the local footprints change
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/vendetta/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py vendetta
cp boards/vendetta/hardware/vendetta.kicad_dru boards/vendetta/production/panel/vendetta-panel.kicad_dru
python3 tools/export_fab.py vendetta
```
