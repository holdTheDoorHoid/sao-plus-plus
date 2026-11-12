# GPIO-16 rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `gpio-16-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `gpio-16-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, and the outline (`Edge_Cuts.gm1`). There is **no drill file for the single board: it has no holes at all**. The panel has one (`gpio-16-panel-NPTH.drl`: break-off holes and tooling holes). The front copper file is empty on purpose.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | only the back carries copper, but 2-layer is the cheapest standard order |
| Size | single 31.3 × 31.0 mm; panel 79.6 × 89.0 mm | |
| Thickness | 1.6 mm | the LEDs are meant to shine through 1.6 mm |
| Surface finish | ENIG preferred, HASL works | the chip's pins are 0.65 mm apart; ENIG's flat pads solder them more reliably |
| Solder mask | any colour | the sixteen light windows are openings in the front mask, so the mask colour does not tint the light. The renders use green |
| Silkscreen | White | |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the front | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1–D16** are **reverse-mount** 1206 LEDs (Lite-On LTST-C230KRKT): the lens faces the board. There is no hole under them; that is intended.
3. **U1** (MCP23017, SSOP-28): pin 1 is marked by a dot on the silkscreen beside the pad.
4. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| U1 MCP23017T-E/SS | C558584 | 2,840 in stock, reel of 2,100 (live page, 2026-11-12) |
| D1–D16 LTST-C230KRKT | C125107 | in stock (2026-11-10) |
| R1–R16 1.3 kΩ | C22767 | in stock (2026-11-10) |
| C1 100 nF | C14663 | in stock (2026-11-10) |
| J1 SAO connector | C492445 | in stock (2026-11-10) |

Every part has an LCSC number; nothing needs consignment.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by four break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the top edge and two on the bottom edge, 6 mm either side of centre. The left and right edges have no tabs (the LED resistors stand 1.5 mm inside them). 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py gpio-16`. The ground copper stays 0.55 mm from the edge everywhere and no track runs near a tab.

Panel rule check: 0 errors, 0 unconnected. 140 warnings, all the same notice ("footprint library not in the current configuration"), which every SAO++ panel gets because the panel file sits outside the board's project folder. The board has no extra rules file, so the panel needs none.

## Regenerating

```
python3 boards/gpio-16/hardware/make_local_footprints.py
python3 tools/gen_schematic.py gpio-16
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/gpio-16/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py gpio-16
python3 tools/export_fab.py gpio-16
```
