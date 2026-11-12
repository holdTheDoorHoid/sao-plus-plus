# Sauce Arm rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The back carries a small Open Sauce logo, a trademark that SAO++'s licenses do not cover and that the repo owner has not yet approved for this board (see the README).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `open-sauce-arm-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `open-sauce-arm-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`, which includes the 3.84 mm key-ring hole as a routed cut-out), and one drill file (two 0.9 mm unplated holes per board for the switch pegs; the panel adds its mouse-bite and tooling holes). There are no plated holes and no vias.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 56.9 × 57.2 mm; panel 130.7 × 141.4 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the jaws and the elbow are drawn in bare gold; the coin cell also rests on a bare copper disc |
| Solder mask / silkscreen | Any mask colour **except black**; white silkscreen. Colour is not recorded in the maker's files | the gripper's palm lights up through the mask, and black mask blocks the light |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the outline is the arm's shape |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **gripper (the two-jawed end of the board)**; the closed end goes toward the ribbed bottom edge. The large round pad under it gets **no solder**.
3. **D1** is a reverse-mount LED: the lens faces **into the board**.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the board edge.
5. **J1** sits 0.45 mm from the board edge at one corner and 1.0 mm from BT1.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (as listed in docs/parts.md, checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1 red LED | C125107 | in stock |
| R1 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by eight break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py open-sauce-arm`. `panel/open-sauce-arm-panel.kicad_dru` is a copy of the board's art rule (the panel tool does not copy it). Panel DRC: 0 errors, 0 unconnected; 20 warnings, all "footprint library not configured" (the panel folder has no library table).

The L shape leaves a lot of empty frame in each pocket; a board house's own panelizing may nest the boards tighter.

After snapping boards out, each tab leaves a small rough spot on the edge: on the outer side of each jaw, on the right of the upper arm, on top of the forearm, twice under the forearm, on the left of the elbow and at its lower left. A few strokes with a file cleans it up. The wire stub at the torn end has no tab: handle the panel with that in mind.

The switch knob ends about 0.3 mm past the outermost point of the board edge, into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py open-sauce-arm
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/open-sauce-arm/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py open-sauce-arm
python3 tools/export_fab.py open-sauce-arm
```
