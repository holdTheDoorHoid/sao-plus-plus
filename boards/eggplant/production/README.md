# Eggplant rev A — ordering files

> Design-checked only. No board has been built from these files yet, and the firmware has never been compiled: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `eggplant-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `eggplant-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 57.5 × 58.5 mm; panel 132.1 × 144.0 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the stalk and leaves are bare metal on the front; ENIG makes them gold and flat |
| Solder mask | **Purple**, as the maker's boards were (an eggplant in any other colour is the owner's call) | the body is copper under the mask: lighter purple; the stripe has no copper: darker and translucent |
| Silkscreen | **White** | the shine mark on the body and the vein on the leaves |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Choose one:

- **Fit it yourself afterwards.** Tell the assembler to skip U1. Solder it by its edge pads with an iron. The LiPo connector will not work this way (its pads are under the module); everything else will. Two of its pads (D5, D6) are 0.7 mm from the SAO connector's shroud, so this needs a fine tip; it is easier if the assembler also leaves J1 off and you fit it last.
- **Have the assembler fit it** from modules you send them or that they buy for you. This is the only way the pads under the module get soldered, unless you reflow it yourself.

Whichever XIAO you use (ESP32-C3, S3 or C6), it goes USB socket toward the board edge. Program it over USB-C before or after fitting; see [../firmware/README.md](../firmware/README.md).

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1 to D5** (SK6805-EC3210R) are **side-mounted**: the part lies on its side with the lens pointing along the board toward the nearest board edge. Moisture sensitivity level 4.
3. D1 to D5, J2 and SW1 sit at odd angles (they follow the curved edge), and U1 at 45 degrees. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.
4. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket overhanging the board edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has two pads underneath (BAT+ and BAT−), which need paste.
5. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.

## Parts availability

As listed in [../../../docs/parts.md](../../../docs/parts.md), checked 2026-11-10 and 2026-11-11 (not re-checked for this board):

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| J2 LiPo connector, JST S2B-PH-SM4-TB | C295747 | in stock |
| D1–D5 RGB LED, OPSCO SK6805-EC3210R | C5378735 | in stock |
| C1–C5 100 nF | C14663 | in stock |
| R1 330 Ω | C23138 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the left (the leaves, and the stripe above the USB socket), one on top of the neck, one on the upper edge, one at the bottom and one at the right-hand end. The lower-left edge has no tab where the USB socket overhangs it. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py eggplant`.

Three of the tabs (upper edge, bottom, right-hand end) sit where the 3.3 V strip runs 0.7 mm inside the edge on the back. That clears the mouse-bite holes by 0.5 mm and passes the rule check, but break those tabs with cutters rather than by bending.

Panel rule check: 0 errors, 0 unconnected. 60 warnings, all the same one: the panel folder has no library table of its own, so KiCad cannot compare the footprints with the library (the single board is where that comparison is made). `panel/eggplant-panel.kicad_dru` repeats the single board's three courtyard exceptions for each copy.

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.5 mm; that is intended.

## Regenerating

```
python3 boards/eggplant/hardware/extract_art.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/eggplant/hardware/build_board.py
python3 tools/gen_schematic.py eggplant
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py eggplant
python3 tools/export_fab.py eggplant
```
