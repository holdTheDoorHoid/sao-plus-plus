# Sloth Badge rev A — ordering files

> **Permission pending.** davedarko has not yet said whether this design may be made; see [../README.md](../README.md). Do not order until the owner decides.
>
> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). **The button SW2 has no confirmed part number yet** (the same open item as Knight Rider). Do not order assembly until it is chosen.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `sloth-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `sloth-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both are used for wiring on this board |
| Size | single 52.0 × 39.0 mm; panel 121.0 × 105.0 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the sloth face is bare gold, and the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | the maker's colours are not recorded in the files; a dark mask makes the gold sloth stand out | |
| Vias | **tented** (covered by mask) both sides, 0.3 mm drill / 0.6 mm pad, 25 per board | they sit on the art side, in the dark ring round the face |
| "Remove order number" | yes, or it gets printed on the art | |
| Assembly side | **both**: D1–D12 on the top (face side), everything else on the bottom | |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. **D1–D12** (red 0603 LEDs) go on the **top** side, at the angles in the placement file (most are not at right angles); all other parts on the **bottom**.
2. **JP1** is bare programming pads: **no part**. Leave that BOM line unmatched.
3. **BT1 (CR2032 clip)** fits its pads both ways round: its open end must face the **left edge as seen from the face side** (the right edge seen from the back), where the cell slides in. The large round pad under it gets no solder.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob sticks out of the top edge.
5. **SW2** (button): part number still to be chosen; 6 × 3.5 mm two-pad SMD tactile switch, pads 6.3 mm apart.
6. Please confirm part rotations in your placement preview; they come straight from KiCad and have not been tried on a real line.

## Parts

All LCSC numbers below are either the shared SAO++ parts on [docs/parts.md](../../../docs/parts.md) or the already-checked local parts copied from Knight Rider (U1 C152192, D1–D12 C125099, D13 C232576). The switch SW1 is out of stock at LCSC (see Mad Cat's notes).

## The panel

2 × 2 boards, each in a routed pocket (2 mm slot), held by five break-off tabs per board with 0.5 mm mouse-bite holes on the edge:

- left and right ends;
- the bottom edge, left of the bottom light;
- the top-left and top-right shoulders.

No tab is placed where the switch knob sticks out of the top edge. Rails carry fiducials and tooling holes. The nearest copper to any mouse-bite hole is 0.30 mm away.

Panel DRC: 0 errors, 0 unconnected. Warnings:
- 100 "footprint library issues", from the panel's mouse-bite footprints;
- 16 art slivers (4 per board).

The board's extra keep-clear rule is repeated in `panel/sloth-panel.kicad_dru`.

## Regenerating

```
python3 boards/sloth/hardware/extract_art.py
python3 boards/sloth/hardware/make_local_footprints.py
python3 tools/gen_schematic.py sloth
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sloth/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py sloth
python3 tools/export_fab.py sloth
```

The board build takes about 2 minutes of computer time (most of it the router), longer on a busy machine.
