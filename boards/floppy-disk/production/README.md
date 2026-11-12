# Floppy Disk rev A — ordering files

> Design-checked only. No board has been built from these files yet. Order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md). The two memory chips are not yet approved parts (see the README, "Decisions").

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `floppy-disk-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `floppy-disk-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers. The two solder bridges (JP1, JP2) are bare copper: they are in the Gerbers but not in the BOM or placement files.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline (`Edge_Cuts.gm1`, which includes the two rectangular corner holes, 2.3 × 1.75 mm, to be milled), and one drill file (two 0.9 mm unplated holes for the switch pegs). There are no plated holes and no vias.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | the front carries copper art (shutter, small mark) |
| Size | single 41.5 × 43.6 mm; panel 100.0 × 114.2 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the shutter is bare copper on both sides and must be gold; the coin cell rests on a bare copper disc |
| Solder mask / silkscreen | any dark mask (the maker's photo shows several colours), **white silkscreen** | the label is white silkscreen |
| Copper | 1 oz | |
| Minimum track / gap | 0.2 mm / 0.2 mm | three fine wires beside U2 |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | two inner cut-outs and a cut corner |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The open end must face the **top edge** of the board (away from the connector J1); the closed end goes toward J1. The large round pad under it gets **no solder**.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; its knob points out of the board edge.
4. **JP1, JP2** (two small two-part pads with a padlock printed beside them) get **no solder paste and no part**, and must stay open.
5. The large bare-copper rectangle on both sides (the "shutter") is artwork: no paste.
6. Please confirm part rotations in your placement preview before running, **especially U1 (SOT-23-5) and U2 (SOIC-8)**. The rotation values come straight from KiCad and have **not** been tried on a real line. (The maker's own JLCPCB note for his board: his two SOIC chips needed +90°.)

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock (per `docs/parts.md`, 2026-11-10) |
| BT1 cell clip | C7501066 | in stock (low: ~1,500; 2026-11-10) |
| C1, C2 100 nF | C14663 | in stock (2026-11-10) |
| D1 cell diode RB751S40T1G | C232576 | in stock (2026-11-11) |
| U1 AD24C02 (SOT-23-5) | C5125083 | 30,090 in stock, $0.039 @100, reel of 3,000 (LCSC product page, 2026-11-11). **Candidate, not yet approved** |
| U2 M24512-RMN6TP (SOIC-8) | C79991 | 147,342 in stock, $0.39 @10, $0.26 @500, reel of 2,500 (LCSC search listing, 2026-11-11). **Not yet approved** |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC** (per `docs/parts.md`). At JLCPCB use Global Sourcing or consignment; Digikey 401-2017-1-ND. This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge. 5 mm rails top and bottom carry three fiducials (both sides) and four tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py floppy-disk`. The board's extra keep-out rule for the panel is in `panel/floppy-disk-panel.kicad_dru` (hand-written; the panel tool does not copy it).

Tabs: one in the middle of the top edge (where the cell slides in: file it smooth before fitting a cell), one on each side edge in the upper half, and two on the bottom edge either side of the gold shutter (none on the shutter itself). The switch knob reaches 1 mm into the 2 mm routed slot; that is intended.
