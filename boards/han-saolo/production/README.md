# Han SAOlo rev A — ordering files

> Design-checked only. No board has been built from these files yet, and **the repo owner has not yet decided whether this board may be published or made before the maker's permission** (see [../README.md](../README.md)). Order nothing until that is settled; then order a small first batch (5–10) and go through the prototype checklist.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `han-saolo-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `han-saolo-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201, J301, J401 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds: front/back copper, solder mask, paste and silkscreen, the board outline, and the drill files (plated: the four small ground vias; non-plated: the switch's two peg holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 27.0 × 67.0 mm; panel 71.0 × 161.0 mm | |
| Thickness | 1.6 mm | the LED light travels through the board to the side-panel windows and the face |
| Surface finish | **HASL (tin), as the maker intended** — or ENIG | The front picture is bare copper left open in the solder mask; the maker's write-up says "exposed and tinned copper", i.e. silver-coloured HASL. ENIG (gold) works too and suits the coin cell's bare contact pad better, but turns the carbonite gold. Owner's choice |
| Solder mask / silkscreen | the maker's colours are not recorded in the files; a dark mask (black or dark green) gives the carbonite look in his photos. White silkscreen | |
| Via treatment | **tented** (covered by solder mask on both sides) | the four vias sit in dark parts of the front art and must stay hidden |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | the maker's back silkscreen has a "JLCJLCJLCJLC" marker on the right edge: at JLCPCB the order number is printed there. Elsewhere, remove it or it may land on the art | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed) | |

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **BT1 (CR2032 clip)** fits its pads both ways round. The **open end must face the top of the board** (toward the maker's "IIC ready" logo); the closed end faces the connector. The large round pad under it gets **no solder**.
3. **D1 to D5** (SK6805-EC3210R) are **side-mounted**: each lies on its side with its lens pointing **away from the board's centre line**: D1–D4 point to the right-hand edge (into the window cut-outs), D5 points left (into the face). Moisture sensitivity level 4.
4. **U1** (ATtiny412) is supplied **blank**; it is programmed after assembly through the round "UPDI" pad. Pin 1 is at the top left as seen from the back (the parts side), the end nearest the cell clip.
5. **D6** diode: cathode toward the board's left edge.
6. **SW1** has two plastic pegs that sit in the two 0.9 mm holes; the knob sticks out of the left edge.
7. **JP1, TP1, TP2, TP3** are bare copper: nothing to place.
8. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 connector | C492445 | in stock (checked 2026-11-10) |
| BT1 cell clip | C7501066 | in stock (low: ~1,500) |
| D1–D5 RGB LED | C5378735 | in stock (18,397); "Extended" part at JLCPCB |
| C1–C5 100 nF | C14663 | in stock |
| U1 ATtiny412 (ATTINY412-SSN) | **not yet looked up** | to be filled in by the orchestrator |
| D6 RB751S40T1G | **not yet looked up** | to be filled in by the orchestrator; also check its current rating (see README) |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC.** Global Sourcing or consignment at JLCPCB; PCBWay sources it (Digikey 401-2017-1-ND). This part decides the schedule |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by six break-off tabs with 0.5 mm mouse-bite holes on the board edge: top edge above the credit, left edge beside the credit, two on the right edge (between LED windows, and beside the jumper legend), two on the bottom. They avoid the switch knob, the coin-cell track down the left edge, the two tracks up the right edge and the data track along the top. 5 mm rails top and bottom carry three fiducials (both sides) and four 1.152 mm tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py han-saolo`. `panel/han-saolo-panel.kicad_dru` carries the board's art rule (the panel tool does not copy it).

The switch knob sticks about 1 mm out of each board's left edge into the routed slot; that is intended.

## Regenerating

```
python3 tools/gen_schematic.py han-saolo
python3 boards/han-saolo/hardware/fix_schematic.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/han-saolo/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py han-saolo
python3 tools/export_fab.py han-saolo
```
(panelize.py writes a fresh panel board; copy `hardware/han-saolo.kicad_pro` to `production/panel/han-saolo-panel.kicad_pro` if it is missing, so DRC picks up the panel's rule file.)
