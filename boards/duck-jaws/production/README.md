# Duck Jaws rev A — ordering files

> Design-checked only. No board has been built from these files yet, and the firmware has never been compiled: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The first thing to find out is whether the duck glows brightly enough through the hole.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `duck-jaws-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `duck-jaws-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`, which also carries the mouth cut-out and the 5 mm duck hole: both are milled, not drilled) and two drill files: `NPTH.drl` (the switch's two peg holes) and `PTH.drl` (fourteen 0.3 mm vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 72.1 × 90.1 mm; panel 161.2 × 207.2 mm | the maker's design scaled 1.8× (see ../README.md) |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG (gold)** | the fourteen teeth are bare copper: with ENIG they are gold, as on the maker's board. HASL would make them silver |
| Solder mask | **Black** | the maker's built boards are black (photo in his repository). His file records no colour; the pictures in this folder use KiCad's default green |
| Silkscreen | **White** | the lips, eyes and nostrils are white print |
| Copper | 1 oz | |
| Via covering | **Tented** (covered with solder mask, both sides) | fourteen vias come through to the art side |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular, with a large inside cut-out (the mouth, with sharp inside corners between the teeth: the router leaves them rounded to its bit, usually 0.5–1 mm radius) and the 5 mm duck hole |

Two things a board house may ask about:

- **A 0.9 mm strip of board** separates the duck hole from the mouth, with one track in it. Say it is intended.
- **Bare board on the back of the tooth tips** (no mask, no copper), and a 0.3 mm rim without copper round each tooth on the front. Both intended.

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Either tell the assembler to skip U1 and solder it yourself by its edge pads (everything works that way except the LiPo connector), or send modules for them to fit (consignment), which also solders the pads underneath. USB socket toward the bottom edge.

## The duck is yours to supply too

It is not in the BOM. Glue it to the front over the hole after assembly, and fill the hole with clear hot glue or a piece of 5 mm clear rod so the light gets into the duck (untried: see ../README.md).

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1 and D2** (SK6805-EC3210R) are **side-mounted**: the part lies on its side with the lens pointing along the board into the round 5 mm hole between them. Moisture sensitivity level 4.
3. **D3, D4, D5, D6** (LTST-S270KRKT) are **side-view LEDs**: the lens points along the board, off the edge of the board into the large cut-out. D4 and D5 point toward the bottom of the board, D3 and D6 toward its middle. The short printed bar marks the cathode end.
4. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the bottom edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
5. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the board's side edge.
6. **J2** (JST-PH LiPo connector) opens toward the bottom edge.
7. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line. D3–D6 use a footprint drawn for this board that no board has been built with.

## Parts availability (from docs/parts.md, checked 2026-11-10; only the red LED was re-checked for this board)

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| D1, D2 RGB LED, OPSCO SK6805-EC3210R | C5378735 | in stock. "Extended" part at JLCPCB |
| D3–D6 red side-view LED, Lite-On LTST-S270KRKT | C125114 | 21,040 in stock on 2026-11-11 (LCSC page) |
| J2 LiPo connector, JST S2B-PH-SM4-TB | C295747 | in stock |
| C1 100 nF | C14663 | in stock |
| R1, R2 330 Ω | C23138 | in stock |
| R3–R6 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

In `…-bom-pcbway.csv` the maker column for D3–D6 is empty (the export tool does not know this part yet): it is Lite-On.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: one on the tip of the snout, one on each side edge of the lower jaw (beside the SAO connector, and below the switch), and two on the bottom edge left and right of the middle. The middle of the bottom edge has none: the USB socket and the LiPo connector are there. The upper side edges have none either: the badge's 3.3 V track runs 1.5 mm inside the outline there. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py duck-jaws`.

Panel rule check: 0 errors, 0 unconnected; 68 warnings, all "footprint library not found", because the panel folder has no library table of its own (17 parts × 4 boards). The board has no extra rules, so the panel needs no rules file.

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.3 mm; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py duck-jaws
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-jaws/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py duck-jaws
python3 tools/export_fab.py duck-jaws
```
