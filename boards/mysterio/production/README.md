# Mysterio rev B — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> Read the permission notice in [../README.md](../README.md) before ordering anything, and note the Marvel character question there. The repo owner chose on 2026-11-11 to publish these files with permission pending; whether to have boards made before the maker answers is not decided.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `mysterio-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `mysterio-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`) and two drill files: `NPTH.drl` (the switch's two peg holes) and `PTH.drl` (four 0.3 mm vias: two on the LiPo + line, two joining the ground).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | the maker's board was 4-layer; this version moves his inner-layer helmet art to the back. One short LiPo track runs on the front, under mask, in the plain base strip |
| Size | single 50.4 × 52.9 mm; panel 117.9 × 132.8 mm | rev B is the maker's design scaled 1.3× plus a base strip (see ../README.md) |
| Thickness | 1.6 mm | the LEDs light the helmet through the board |
| Surface finish | **ENIG** | the collar, diamonds and chest buttons are bare copper art on the front |
| Solder mask | **Green** (the maker's file has no colour recorded; the renders and the art's look assume a dark green mask over the copper robe) | check a photo of a built original before ordering |
| Silkscreen | **White** | the robe highlights on the front, the credit on the back |
| Copper | 1 oz | |
| Via covering | **Tented** (covered with solder mask, both sides) | the four vias sit in the plain base strip on the front |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Either tell the assembler to skip U1 and solder it yourself by its edge pads (everything works that way), or send modules for them to fit (consignment), which also solders the pads underneath. USB socket toward the bottom edge.

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1 to D4** (SK6805-EC3210R) are **side-mounted**: the part lies on its side with the lens pointing along the board toward the small arrow printed beside it (toward the centre of the round helmet). Moisture sensitivity level 4. D1 and D4 sit at 45° and D2, D3 at 25°: they are not square to the board.
3. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the bottom edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. **J2** (JST-PH LiPo connector) opens toward the bottom edge. **R1** sits at 45°, like D1 beside it.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| D1–D4 RGB LED, OPSCO SK6805-EC3210R | C5378735 | in stock. "Extended" part at JLCPCB |
| J2 LiPo connector, JST S2B-PH-SM4-TB | C295747 | in stock |
| C1 100 nF | C14663 | in stock |
| R1–R4 330 Ω | C23138 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: one on the bottom edge (between the LiPo connector and the XIAO), one on the right edge of the base strip, one on the left arm, one on top of the left shoulder and one on top of the helmet (the back art ring loses 0.15 mm of its outer edge there and stays whole). The right arm has none (two tracks run up inside it), nor has the rest of the bottom edge (the switch's, LiPo connector's and XIAO's pads or USB end sit at it). 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py mysterio`. The front art steps back 0.55 mm from the edge at the tabs so the holes do not cut it.

The panel has its own rules file, `panel/mysterio-panel.kicad_dru` (a hand-made copy of the board's art rule, because panelize does not carry it over). Panel rule check: 0 errors, 0 unconnected; warnings only (52 "footprint library not found" for the panel's own frame parts, 20 copper slivers in the art). Every mouse-bite hole is at least 0.25 mm from copper (no hole-clearance errors).

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.5 mm; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py mysterio
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mysterio/hardware/build_board.py
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad tools/panelize.py mysterio
python3 tools/export_fab.py mysterio
```
(`production/panel/mysterio-panel.kicad_dru` is kept by hand: panelize does not touch it.)
