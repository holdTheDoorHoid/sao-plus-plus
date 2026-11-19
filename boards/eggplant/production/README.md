# Eggplant rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> The original is MIT-licensed (maker's notice kept in `../original/LICENSE`); no permission is needed. Read the three owner decisions in the main README before ordering.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `eggplant-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `eggplant-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`) and the drill files: 33 plated 0.3 mm via holes and the switch's two 0.9 mm peg holes.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 37.3 × 75.4 mm; panel 91.6 × 177.8 mm | 1.35× the maker's board (see the main README) |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the stem and calyx are bare copper on both sides; ENIG keeps them gold and solders the flat pads best |
| Solder mask | **Purple** suits the eggplant (the colour the maker used is not recorded in his files) | **Owner's choice**; the renders use green. Whatever the colour, the light stripe (no copper under it) shows paler than the body |
| Silkscreen | **White** | leaf and highlight on both sides, his lettering on the back |
| Copper | 1 oz | |
| Vias | **Tented** (covered by mask on both sides), 0.3 mm drill, 0.6 mm pad | they sit in the front artwork |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the front | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Parts the assembler cannot source from these files

- **U1, the XIAO module** has no LCSC number: skip it and solder it yourself by its edge pads (everything except the LiPo socket works that way, because the battery reaches the module through pads underneath), or send modules for consignment. USB socket toward the left-hand side of the bulb.
- **D1–D5, the maker's two-colour LED** ("PHBM2012QBDSURKC" in his BOM) has no LCSC number yet: to be found and checked against his land pattern (four pads, 2.0 × 1.25 mm body).
- **SW1 (C&K PCM13SMTR)** is out of stock at LCSC (as for the other boards): Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND.

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the board edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
4. **D1–D5** are four-pad two-colour LEDs: the anode side is marked on the fab drawing (pad 1 = blue anode, pad 2 = red anode); the lens faces away from the board.
5. **J2** (LiPo socket): its opening faces the nearest board edge (lower right of the bulb, seen from the front).
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock (2026-11-10) |
| J2 LiPo socket | C295747 | in stock (2026-11-10) |
| R1–R8 330 Ω | C23138 | in stock |
| R9–R13 1.3 k | C22767 | in stock |
| D1–D5 two-colour LED | — | to be found |
| SW1 C&K PCM13SMTR | C221842 | **out of stock at LCSC**; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: upper left of the calyx, right of the upper body, left of the upper body, lower left of the bulb, and the very bottom. The USB-C side, the switch knob and the LiPo socket's opening have no tabs. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py eggplant`. No track runs within 3 mm of a tab, and copper stays at least 0.55 mm from the edge there.

The panel has its own copy of the board's rules file, `panel/eggplant-panel.kicad_dru`. Panel rule check: 0 errors, 0 unconnected; warnings only (128 printed-outline overlaps, 88 "footprint library" notices for the panel's frame parts and copied footprints, 44 copper slivers, 24 base64-line-over-pad notices, 8 thin-lettering notices: four copies of the single board's warnings). No mouse-bite hole comes within 0.25 mm of copper.

## Regenerating

```
python3 boards/eggplant/hardware/extract_art.py                    # only if original/ changes
python3 boards/eggplant/hardware/make_local_footprints.py
python3 tools/gen_schematic.py eggplant
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/eggplant/hardware/build_board.py
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad tools/panelize.py eggplant
cp boards/eggplant/hardware/eggplant.kicad_dru boards/eggplant/production/panel/eggplant-panel.kicad_dru
python3 tools/export_fab.py eggplant
```
