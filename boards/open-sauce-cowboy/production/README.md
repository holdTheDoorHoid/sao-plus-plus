# Cowboy rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The owner has not yet decided whether the Open Sauce logo stays on the back (see the README).

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `open-sauce-cowboy-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `open-sauce-cowboy-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`, which includes the 3 mm key-ring hole as a routed circle), and the drill files (two 0.3 mm plated vias, two 0.9 mm unplated holes for the switch pegs).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | both sides carry copper |
| Size | single 57.2 × 27.1 mm; panel 131.3 × 81.2 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the hat's highlights are bare copper, so the finish *is* the gold; the coin cell also rests on a bare copper disc |
| Solder mask / silkscreen | **Red mask, white silkscreen** suggested | not recorded in the maker's board files; his concept drawing is a red hat. Owner's decision |
| Copper | 1 oz | |
| Vias | **tented** (covered by mask both sides) | two small vias; they must not show as bare spots on the hat |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the board is a hat |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **nearest long board edge (the bottom of the hat, the same edge the switch SW1 is on)**; the closed end faces away from it. The large round pad under it gets **no solder**.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the board edge.
4. **D1** is a reverse-mount LED: its lens faces **into** the board.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (from `docs/parts.md`, checked there 2026-11-10; not re-checked for this board)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1 red reverse-mount LED | C125107 | in stock |
| R1 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py open-sauce-cowboy`. The board's extra keep-out rules for the panel are in `panel/open-sauce-cowboy-panel.kicad_dru` (hand-written; the panel tool does not copy them).

Panel rule check: 0 errors, 0 unconnected. 24 warnings: the maker's white rim touching each board's edge (4), and "footprint library not configured" for each of the 20 parts (the panel folder has no library table; the parts themselves are the checked ones from the single board).

After snapping boards out, each tab leaves a small rough spot: on top of the left brim, on top of the right brim, at the tip of the right brim, and two along the bottom between the cell and the switch. There is no tab on the crown (the connector is too close to that edge) and none where the cell overhangs. A few strokes with a file cleans them up.

The switch knob ends about 1 mm past the bottom edge, into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py open-sauce-cowboy
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/open-sauce-cowboy/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py open-sauce-cowboy
python3 tools/export_fab.py open-sauce-cowboy
```
