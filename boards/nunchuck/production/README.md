# SAO Nunchuck rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) and try a real Wii Nunchuk plug on the tongue before any production run (see the prototype list in [../README.md](../README.md)). **The Qwiic sockets J3/J4 have no LCSC number filled in yet.**

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nunchuck-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nunchuck-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both are used: the Nunchuk tongue has fingers on both sides |
| Size | single 38.1 × 50.8 mm; panel 93.2 × 128.6 mm | |
| Thickness | **1.6 mm** | the Nunchuk plug grips the tongue: a thinner or thicker board will not fit or will be loose |
| Surface finish | **ENIG** | the tongue's fingers are contacts that rub against the plug; ENIG is the house finish. Hard gold on the fingers is better for many plug-ins but costs more; not needed for a first batch |
| Solder mask / silkscreen | the maker's colours are not recorded in the files; green or black mask with white silkscreen both suit the gold art | |
| Vias | **tented** (covered by mask) both sides, 0.3 mm drill / 0.6 mm pad, 8 per board | they sit on the art side, under the tongue |
| "Remove order number" | yes, or it gets printed on the art | |
| Assembly side | **bottom only**: J1, J3, J4 | |
| Board outline | milled (routed), **including the two slots beside the tongue and their 1 mm side notches**: ask for a 1.0 mm or smaller cutter if the factory asks | |

## Notes for the assembler (paste into the order remarks)

1. All parts go on the **bottom** side. Nothing on the top.
2. The gold fingers on the top edge (J2) are part of the board: **no part**, keep them free of solder and paste.
3. J1 is the 2×3 shrouded box header; its key slot faces the top edge (the gold-finger tongue).
4. J3/J4 are JST SH 4-pin side-entry sockets (SM04B-SRSS-TB): openings face the left and right board edges.
5. Please confirm part rotations in your placement preview; they come straight from KiCad and have not been tried on a real line.

## Parts with no LCSC number yet

J3, J4: JST **SM04B-SRSS-TB(LF)(SN)**. J1 is the shared SAO++ connector already on [docs/parts.md](../../../docs/parts.md).

## The panel

2 × 2 boards, each in a routed pocket (2 mm slot), held by six break-off tabs per board with 0.5 mm mouse-bite holes on the edge:

- left and right sides, level with the remote's lower half (below the Qwiic sockets, whose openings stay clear);
- bottom edge, left and right of the SAO connector;
- top edge, left and right of the tongue slots.

**No tab on the tongue**: its tip and fingers must break clean. Rails top and bottom carry fiducials and tooling holes.

Panel DRC: 0 errors, 0 warnings, 0 unconnected. The mouse-bite holes keep at least 0.25 mm from copper (the ground copper stops 0.55 mm from the edge). The board's extra rule for the tongue fingers is repeated in `panel/nunchuck-panel.kicad_dru`, and `panel/fp-lib-table` points KiCad at the footprints so it does not warn about them.

## Regenerating

```
python3 boards/nunchuck/hardware/make_local_footprints.py
python3 tools/gen_schematic.py nunchuck
python3 boards/nunchuck/hardware/fix_schematic.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nunchuck/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nunchuck
python3 tools/export_fab.py nunchuck
```
