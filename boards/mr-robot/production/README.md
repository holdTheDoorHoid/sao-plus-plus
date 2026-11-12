# Mr. Robot rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> Read the permission notice in [../README.md](../README.md) before ordering anything, and note the third-party question about the *Mr. Robot* mask there. Whether to publish or have boards made before the maker answers is **not decided**.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `mr-robot-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `mr-robot-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`) and one drill file, `NPTH.drl` (the switch's two peg holes). There are no vias.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 44.0 × 42.7 mm; panel 105.0 × 112.3 mm | 1.10× the maker's board (see the main README) |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the maker's gold logo on the back is bare copper; ENIG also solders the flat pads best |
| Solder mask | The maker ordered OSH Park **"After Dark"**: black board, **clear** solder mask, so the copper face shows as copper on black. The nearest at JLCPCB / PCBWay is a black or matte black mask (the copper face then shows only as a raised texture) | **Owner's choice.** Check what the board house offers; the renders here use green |
| Silkscreen | **White** | the moustache, brows and ear highlights on the front |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the face | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Parts the assembler cannot source from these files

- **U1, the XIAO module** has no LCSC number: skip it and solder it yourself by its edge pads (everything except the LiPo socket works that way, because the battery reaches the module through pads underneath), or send modules for consignment. USB socket toward the top of the head.
- **LS1, the sounder (Kingstate KMTG1102-A1)** and **Q1, the transistor (BC847B,215)** have no LCSC number yet: to be checked by the orchestrator. Any BC847B/C in SOT-23 fits Q1.
- **SW1 (C&K PCM13SMTR)** is out of stock at LCSC (as for the other boards): Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND.

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the board edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
4. **LS1** is an 11 × 9 mm SMD sounder with two end pads. If it has a "+" mark, the "+" goes to the pad nearer the top of the head (pad 2).
5. **J2** (LiPo socket): its opening faces the nearest board edge (the left edge when looking at the parts side with the head upright).
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock (2026-11-10) |
| J2 LiPo socket | C295747 | in stock (2026-11-10) |
| R2–R6 330 Ω | C23138 | in stock |
| R1, R7 1.3 k | C22767 | in stock |
| D1 RB751S40T1G | C232576 | in stock (2026-11-11) |
| Q1 BC847B,215 | — | to be checked |
| LS1 KMTG1102-A1 | — | to be checked |
| SW1 C&K PCM13SMTR | C221842 | **out of stock at LCSC**; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: one on top of each ear, one on each cheek (the right one below the LiPo socket's opening) and one on the left jaw. The top of the head (USB-C), the chin (switch knob) and the right jaw (a track runs 0.6 mm inside it) have no tabs. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py mr-robot`. The front art and the back ground copper stay at least 0.55 mm from the edge at every tab.

The panel needs its own rules file, `panel/mr-robot-panel.kicad_dru` (a hand-made copy of the board's, because the panel renumbers parts). Panel rule check: 0 errors, 0 unconnected; warnings only (56 "footprint library" notices for the panel's own frame parts and copied footprints, 12 copper slivers in the face art). No mouse-bite hole comes within 0.25 mm of copper (no hole-clearance errors).

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot; that is intended.

## Regenerating

```
python3 boards/mr-robot/hardware/make_local_footprints.py
python3 tools/gen_schematic.py mr-robot
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mr-robot/hardware/extract_art.py   # only if original/ changes
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mr-robot/hardware/build_board.py
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad tools/panelize.py mr-robot
python3 tools/export_fab.py mr-robot
```
(`production/panel/mr-robot-panel.kicad_dru` is kept by hand: panelize does not touch it.)
