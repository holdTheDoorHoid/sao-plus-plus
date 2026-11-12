# Duck Bath rev A — ordering files

> Design-checked only. No board has been built from these files yet, and the firmware has never been compiled: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The first thing to find out is whether the duck glows brightly enough through the hole.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `duck-bath-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `duck-bath-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`, which also carries the 5 mm duck hole: it is milled, not drilled) and two drill files: `NPTH.drl` (the switch's two peg holes) and `PTH.drl` (eight 0.3 mm vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 64.1 × 32.0 mm; panel 145.1 × 91.0 mm | the maker's design scaled 1.6× (see ../README.md) |
| Thickness | 1.6 mm | |
| Surface finish | ENIG preferred (house standard); HASL would do | no bare copper art on this board |
| Solder mask | **White** | the maker's built boards are white with black lines (photo in his repository). His file records no colour; the pictures in this folder use KiCad's default green |
| Silkscreen | **Black** | the tub and foam are drawn in silkscreen lines |
| Copper | 1 oz | |
| Via covering | **Tented** (covered with solder mask, both sides) | eight vias come through to the art side |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular, and has one inside cut-out (the duck hole, 5 mm) |

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Either tell the assembler to skip U1 and solder it yourself by its edge pads (everything works that way except the LiPo connector), or send modules for them to fit (consignment), which also solders the pads underneath. USB socket toward the bottom edge.

## The duck is yours to supply too

It is not in the BOM. Glue it to the front over the hole after assembly, and fill the hole with clear hot glue or a piece of 5 mm clear rod so the light gets into the duck (untried: see ../README.md).

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1 and D2** (SK6805-EC3210R) are **side-mounted**: the part lies on its side with the lens pointing along the board toward the small arrow printed beside it, into the round 5 mm hole. D1 points up the board, D2 points sideways. Moisture sensitivity level 4.
3. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the bottom edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the board's side edge.
5. **J2** (JST-PH LiPo connector) opens toward the bottom edge.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from docs/parts.md, checked 2026-11-10; not re-checked for this board)

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| D1, D2 RGB LED, OPSCO SK6805-EC3210R | C5378735 | in stock. "Extended" part at JLCPCB |
| J2 LiPo connector, JST S2B-PH-SM4-TB | C295747 | in stock |
| C1 100 nF | C14663 | in stock |
| R1–R3 330 Ω | C23138 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on top of foam bubbles (left and right of the duck), one on the right wall, one on the left end of the rim above the switch, and one under each foot. The bottom edge between the feet has none: the USB socket and the LiPo connector are there and tracks run close to it. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py duck-bath`.

Panel rule check: 0 errors, 0 unconnected; warnings only (40 "footprint library not found", because the panel folder has no library table of its own, and 4 copper slivers, the single board's one repeated four times). The board has no extra rules, so the panel needs no rules file.

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.0 mm; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py duck-bath
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-bath/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py duck-bath
python3 tools/export_fab.py duck-bath
```
