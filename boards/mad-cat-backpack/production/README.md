# Mad Cat Backpack rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> The maker's design is MIT-licensed (keep his notice with the boards; see [../README.md](../README.md)). This board is only useful behind a Mad Cat, whose maker has not yet given permission: read [../../mad-cat/README.md](../../mad-cat/README.md) before ordering Mad Cats for sale.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `mad-cat-backpack-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `mad-cat-backpack-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

You also need one **bare SAO++ Mad Cat** per backpack (`boards/mad-cat/production/`, ordered as bare boards with **no assembly**).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 63.0 × 39.0 mm; panel 143.0 × 104.9 mm | |
| Thickness | 1.6 mm | the Mad Cat's light windows and this board's holes are sized for it |
| Surface finish | HASL or ENIG | ENIG makes the eight bond holes easier to solder flat against the Mad Cat |
| Solder mask | Any colour; **dark** (black, matte black) keeps light from glowing sideways through the board | the LEDs shine into this board on their way to the Mad Cat |
| Silkscreen | White | |
| Copper | 1 oz | |
| Vias | 11 tented vias (0.3 mm hole, 0.6 mm pad), "tented" / "covered by solder mask" | they sit on the side pressed against the Mad Cat |
| "Remove order number" / "specify location" | either; the board is hidden | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular; it also has eight **1.0 mm round cut-outs** (the light holes). If the board house asks, they may be drilled as 1.0 mm unplated holes instead: same result |

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Choose one:

- **Fit it yourself afterwards.** Tell the assembler to skip U1. Solder it by its edge pads with an iron. The LiPo socket will not work this way (its pads are under the module); everything else will.
- **Have the assembler fit it** from modules you send them (consignment) or that they buy for you. This is the only way the pads under the module get soldered, unless you reflow it yourself with paste and hot air or a hot plate.

Whichever XIAO you use (ESP32-C3, S3 or C6), its USB socket goes toward the board's right-hand edge (the haunch). Program it over USB-C before or after fitting; see [../firmware/README.md](../firmware/README.md).

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side. The top side has no parts.
2. **D1 to D8** (Lite-On LTW-C230DS, white) are **reverse-mount** LEDs: the lens faces **into the board**, over the small round hole between each LED's pads.
3. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket overhanging the board edge by 1.5 mm. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has two pairs of pads underneath (BAT+ and BAT−), which need paste.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. The eight bare plated rings (0.7 mm holes) beside some LEDs are **bond holes, not parts**: leave them bare, no paste, no solder.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| J2 LiPo socket, JST S2B-PH-SM4-TB | C295747 | in stock |
| D1–D8 white reverse-mount LED, Lite-On LTW-C230DS | C575513 | in stock |
| R1–R8 330 Ω | C23138 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: one on the left cheek, one left of the paws beside the switch, one on the top edge over the face, and two on the bottom of the haunch. The right-hand edge has no tab: both the LiPo plug and the USB-C socket are there, and the XIAO's keep-out box covers most of it. The switch knob's edge under the paws is also left free. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py mad-cat-backpack`.

Panel rule check (with `panel/mad-cat-backpack-panel.kicad_dru`, the single board's rules with the panel's part numbers): **0 errors, 0 unconnected**. Warnings: 80 "footprint library not configured" (the panel project has no library table; harmless), 12 silkscreen lines clipped at board edges and 4 "text too small" (the maker's lettering), each the single board's repeated four times. The nearest mouse-bite hole is 0.30 mm from any copper.

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.5 mm; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py mad-cat-backpack
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mad-cat-backpack/hardware/build_board.py
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad tools/panelize.py mad-cat-backpack
python3 tools/export_fab.py mad-cat-backpack
```

The panel's rule file (`panel/mad-cat-backpack-panel.kicad_dru`) is written by hand; `panelize.py` does not copy the board's rules.
