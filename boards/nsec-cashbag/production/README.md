# Cash Bag rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The back carries NorthSec's "nsec 2025" logo: ask them before selling.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `nsec-cashbag-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `nsec-cashbag-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and one drill file (two 0.9 mm unplated holes per board for the switch pegs; there are no vias).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | front copper is the art (gold where the mask is open, lighter green under mask), back copper is the circuit |
| Size | single 65.7 × 37.8 mm; panel 148.4 × 102.6 mm | |
| Thickness | 1.6 mm | the LEDs shine through it |
| Surface finish | **ENIG** | the two '$', the coin's rim, the sack's tie and the paper band are bare gold; the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | **Green mask, white silkscreen** | the drawing relies on two greens (mask over copper, mask over bare board); the three white LEDs shine through the mask |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the outline is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **bottom edge of the board** (the long straight edge under the big round pad); the closed end goes toward the sack's scalloped top. The large round pad under it gets **no solder**.
3. **D1, D2, D3 are reverse-mount LEDs** (Lite-On LTW-C230DS): the lens faces **down, into the board**. The cathode is marked by the silkscreen bar beside each LED.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes near the left edge (seen from the front); its knob points out of that edge.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (taken from docs/parts.md, checked there 2026-11-10; not re-checked for this board)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D3 white reverse-mount LED | C575513 | in stock |
| R1–R3 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge: top of the sack, top edge of the tucked note, under the wad of notes, and the top, right and bottom of the coin. None on the left edge (switch knob) or under the sack (where the cell slides in). 5 mm rails top and bottom carry three fiducials and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py nsec-cashbag`. `panel/nsec-cashbag-panel.kicad_dru` repeats the board's one art rule (the panel tool does not copy it).

Panel DRC: 0 errors, 0 unconnected. 40 warnings, all the same harmless one ("footprint library not configured": the panel folder has no library table).

The switch knob reaches about 1 mm into the 2 mm routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py nsec-cashbag
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-cashbag/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py nsec-cashbag
python3 tools/export_fab.py nsec-cashbag
```
