# Spacehuhn rev A — ordering files

> Design-checked only. No board has been built from these files yet, and **permission is still pending from two people**: davedarko for the board, and Spacehuhn (Stefan Kremser) for the chicken logo (see [../README.md](../README.md)). Order a small first batch (5–10) only once the owner has decided, and go through the prototype checklist in the README first.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `spacehuhn-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `spacehuhn-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`), and the drill file (`NPTH.drl`; there are no plated holes, only the switch's two peg holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 49.9 × 50.0 mm; panel 116.8 × 127.0 mm | |
| Thickness | 1.6 mm | the eye LEDs shine through the board |
| Surface finish | **ENIG** | the chicken's face and beak, the stars, the maker's logo and marker rectangles are bare copper art, and the coin cell rests on a bare copper disc; ENIG keeps them gold and flat |
| Solder mask / silkscreen | not recorded in the maker's files; **white silkscreen** is required (the eyes, comb, wing and helmet are silkscreen art) | the mask colour is the owner's choice |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. Seen from the back, its **open end must face the right-hand edge**; its closed end faces the connector J1. The large round pad under it gets **no solder**.
3. **D1 and D2** are reverse-mount LEDs: lens faces **into** the board.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the bottom edge of the stand.
5. The two bare-copper rectangles near the top of the back are artwork, not pads: nothing is placed on them and they get no paste.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10 for Mad Cat, same parts)

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1, D2 white LED | C575513 | in stock. "Extended" part at JLCPCB: a small one-time loading fee |
| R1, R2 1.3 kΩ | C22767 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** At JLCPCB use Global Sourcing or send parts on consignment; at PCBWay they source it (Digikey 401-2017-1-ND, long lead time quoted). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge (24 tabs, 120 holes in all). 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py spacehuhn`. Panel DRC: 0 errors, 0 unconnected (the 0.25 mm hole-to-copper rule is checked and passes). The 28 warnings only say the panel project does not list the parts library (the parts are embedded in the file).

Tabs: top of the helmet, upper left and upper right of the helmet, the right side beside the maker's logo, and both sides of the stand. After snapping boards out, each leaves a small rough spot on the edge: a few strokes with a file clean it up. The front copper art steps back from 0.40 to 0.55 mm from the edge at the tabs only, so the mouse-bite holes do not cut it. No tab sits on the left side, where the cell slides in, or under the switch knob.

The only thing reaching past the board edge is the switch knob (0.7 mm, at the bottom of the stand), into the routed slot.

## Regenerating

```
python3 boards/spacehuhn/hardware/extract_art.py        # only if art/art.json is missing
python3 tools/gen_schematic.py spacehuhn
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/spacehuhn/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py spacehuhn
python3 tools/export_fab.py spacehuhn
```

`production/panel/spacehuhn-panel.kicad_dru` is a copy of `hardware/spacehuhn.kicad_dru` (the art rule only; panelize does not copy the board's rules).
