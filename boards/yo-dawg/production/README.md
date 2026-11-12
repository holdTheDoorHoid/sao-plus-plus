# Yo Dawg rev A — ordering files

> Design-checked only. No board has been built from these files. Order a small first batch (5–10) and go through the prototype checklist in [../README.md](../README.md) before any production run.
>
> **Do not order assembly yet:** the socket (J2, J3, J4) has no chosen part number. Bare boards can be ordered.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `yo-dawg-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `yo-dawg-panel-gerbers.zip` | `panel/` |
| Assembled | the Gerber zip, then the BOM and placement files for JLCPCB (`…-bom-jlcpcb.csv`, `…-cpl-jlcpcb.csv`) or PCBWay (`…-bom-pcbway.csv`, `…-centroid-pcbway.csv`) | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 40 × 50 mm; panel 97 × 127 mm | |
| Thickness | 1.6 mm | |
| Solder mask / silkscreen | **white mask, black print** is the maker's look. Any colour works | the renders are in default green |
| Surface finish | ENIG preferred, HASL works | |
| Copper | 1 oz | |
| "Remove order number" | Yes | the maker's slot for it was removed |
| Panel option | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly | **both sides**: J1, C1–C3 on the bottom (surface-mount); J2–J4 on the top (through-hole, soldered from the bottom) | or have the bottom assembled and solder the three sockets by hand |

## Notes for the assembler

1. J1 (bottom): key slot toward the board's top edge; pin 1 is marked "1".
2. J2, J3, J4 are through-hole sockets fitted from the **top**.
3. Rotation values come straight from KiCad and have not been tried on a real line. Check the placement preview.

## Panel

2 × 2, 2 mm routed slots, six break-off tabs per board on the top, left and right edges. There is no tab on the bottom edge, where the connector's pads end 0.5 mm from the edge. Three fiducials and four tooling holes on the frame.
