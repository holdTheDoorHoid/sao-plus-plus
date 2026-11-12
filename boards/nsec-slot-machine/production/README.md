# Slot Machine rev A — ordering files

> Design-checked only. No board has been built from these files. Order a small first batch (5–10) and go through the prototype checklist in [../README.md](../README.md). Settle the "nsec 2025" logo question there before selling any.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nsec-slot-machine-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nsec-slot-machine-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the board outline, and one drill file (two 0.9 mm unplated holes per board for the switch pegs; there are no vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 39.9 × 46.6 mm; panel 96.8 × 120.2 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the reels, stars, tray and base are bare copper: gold is the look. The coin cell also rests on a bare copper disc |
| Solder mask / silkscreen | **white silkscreen**; mask colour is your choice (the renders show red) | |
| Copper | 1 oz | |
| "Remove order number" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | |
| Board outline | milled (routed), not V-cut | |

## Notes for the assembler

1. All parts are on the **bottom** side.
2. **D1–D3 are reverse-mount LEDs (lens toward the board).** Do not substitute a normal top-emitting 1206.
3. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **round top of the board** (away from the connector J1). The large round pad under it gets **no solder**.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the bottom edge; its knob points out of the bottom edge.
5. J1's shroud key faces the round top of the board.
6. Please confirm part rotations in your placement preview. The rotation values come straight from KiCad and have not been tried on a real line.

## Parts availability (as listed in docs/parts.md, 2026-11-10)

The switch (C&K PCM13SMTR) was out of stock at LCSC; source it through Digikey (401-2017-1-ND) or the assembler's global sourcing. Everything else was in stock.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge: one at the top of the marquee, two on the left side, one on the right below the lever, two on the bottom edge either side of the switch. No tab is on the lever. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py nsec-slot-machine`. Panel DRC: 0 errors, 0 unconnected; the 40 warnings are all "library not installed" notes, one per part.

## Regenerating

```
python3 tools/gen_schematic.py nsec-slot-machine
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-slot-machine/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nsec-slot-machine
python3 tools/export_fab.py nsec-slot-machine
```
