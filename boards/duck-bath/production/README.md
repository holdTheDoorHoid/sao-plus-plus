# Duck Bath rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> The design is the maker's, under the MIT licence (and CERN-OHL-P, both in `../original/LICENSE.md`): ordering and selling boards is allowed; keep his credit on the back and his licence file with the design.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `duck-bath-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `duck-bath-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline and the drill files: the LED's four leg holes and four small vias (plated), and the switch's two peg holes (not plated).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 58.1 × 29.0 mm; panel 133.1 × 85.0 mm | 1.45× the maker's board (see the main README) |
| Thickness | 1.6 mm | |
| Surface finish | ENIG or HASL | nothing on the front is bare copper; ENIG solders the flat pads best |
| Solder mask | **White** (the maker's look: a white tub) | Owner's choice; the renders here use green |
| Silkscreen | **Black** | the drawing of the tub and bubbles is silkscreen |
| Vias | **Tented** (covered by mask) | the four ground vias in the tub |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the tub | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom** for the SMD parts; the LED is through-hole on the **top** | |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## Parts the assembler cannot source from these files

- **U1, the XIAO module** has no LCSC number: skip it and solder it yourself by its edge pads, or send modules for consignment. Note that the LiPo socket only works if the module's **battery pads underneath** are soldered too (paste and hot air, a hot plate, or the assembler). USB socket toward the tub bottom.
- **D1, the 5 mm RGB LED** has no part number yet (the maker's files give none): a 5 mm, 4-leg, **common-anode** RGB LED with legs in the order red, anode (longest), green, blue. It is through-hole, from the front; hand-solder it after the SMD parts. The square pad is red.
- **SW1 (C&K PCM13SMTR)** is out of stock at LCSC (as for the other boards): Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND.
- **R1–R3, 100 Ω**: the maker's LCSC number (C22775) is in the files; to be checked by the orchestrator.

## Notes for the assembler (paste into the order remarks)

1. All SMD parts are on the **bottom** side. D1 (5 mm LED) is through-hole from the top: leave it out, we fit it.
2. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the board edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has pads underneath, which need paste.
3. Two tracks pass between U1's edge pads with 0.17 mm gaps: please check for solder bridges there.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. **J2** (LiPo socket): its opening faces the nearest board edge (the tub's side wall).
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock (2026-11-10) |
| J2 LiPo socket | C295747 | in stock (2026-11-10) |
| R4, R6 330 Ω | C23138 | in stock |
| R1–R3 100 Ω | C22775 | the maker's number, not re-checked |
| SW1 PCM13SMTR | C221842 | out of stock at LCSC; Digikey |
| D1 5 mm RGB LED | — | to be chosen |
| U1 XIAO ESP32 | — | Seeed |

The rubber duck is not part of the order: any small bath duck with a hole in its base for the 5 mm LED.
