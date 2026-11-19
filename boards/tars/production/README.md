# TARS rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> The maker's design is MIT-licensed, so no permission is needed; keep his copyright notice with the files ([../README.md](../README.md)). Note the separate question about the *Interstellar* character there before selling boards.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `tars-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `tars-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

Each zip holds front/back copper, solder mask, paste and silkscreen, the outline (`Edge_Cuts.gm1`) and the drill files (the covered vias, 0.3 mm, and the switch's two 0.9 mm peg holes).

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **2** | |
| Size | single 40.0 × 50.0 mm; panel 97.0 × 127.0 mm (2 × 2) | the maker's size, unchanged |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the gold slabs on the front are bare copper; ENIG also solders the flat pads best |
| Solder mask | Black (the maker's look: gold slabs on black) | owner's choice; the renders use green |
| Silkscreen | White | |
| Copper | 1 oz | |
| Vias | **Tented** (covered by solder mask) | all vias sit under the display glass |
| "Remove order number" | The maker left "JLCJLCJLCJLC" on the back for JLCPCB's order number; choose "specify location" at JLCPCB, or remove it | |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Both**: the display, the cue light D1 and its resistor R10 are on the **front**; everything else on the back | |
| Board outline | milled, rectangular with 0.5 mm corners | |

## Parts the assembler cannot source from these files

- **U2, the XIAO module** has no LCSC number: skip it and solder it by hand, or send modules for consignment. Its battery pads underneath need paste and reflow if the LiPo socket is used. USB socket at the top edge.
- **U1, the display** (0.96 in 80 × 160 ST7735S IPS with a 13-pin 0.7 mm solder ribbon): the maker gives no part number. It is soldered by hand after assembly: the ribbon is folded under the glass onto the 13 pads, and the glass is stuck to the board.
- **U3 (Microchip CAP1206-1-SL)**, **J2 (Molex 53261-0271)**, **J3/J4 (JST SM04B-SRSS-TB)** and **R9 (11 Ω, 0603WAF110JT5E)**: LCSC numbers not filled in yet (to be checked by the orchestrator).
- **SW1 (C&K PCM13SMTR)** is out of stock at LCSC (as for the other boards): Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND.
- **The speaker** is not on the board: any small 8 Ω speaker with a Molex PicoBlade 2-pin plug, glued in the "reserved for speaker" box on the back.

## Notes for the assembler (paste into the order remarks)

1. Parts on **both** sides: front = D1, R10 only (U1 the display is fitted by hand later). Back = everything else.
2. **U2** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the board edge. [Delete whichever does not apply:] Skip U2, we fit it ourselves. / U2 is supplied by us; it also has pads underneath, which need paste.
3. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
4. **JP1** is a solder jumper, not a part: leave it as it is (pads 1 and 2 are joined by copper).
5. **TP1–TP6** are bare copper dots, not parts.
6. **J5** (LiPo socket): its opening faces the right edge (seen from the front).
7. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock (2026-11-10) |
| J5 LiPo socket | C295747 | in stock (2026-11-10) |
| R13–R15 330 Ω | C23138 | in stock |
| R10–R12, R16 1.3 k | C22767 | in stock |
| C1, C2 100 nF | C14663 | in stock |
| D1 red 0603 LTST-C191KRKT | C125099 | checked for Knight Rider (2026-11-11) |
| U3 CAP1206-1-SL | — | to be checked |
| R9 11 Ω 0603WAF110JT5E | — | to be checked |
| J2 Molex 53261-0271 | — | to be checked |
| J3, J4 JST SM04B-SRSS-TB(LF)(SN) | — | to be checked |
| SW1 PCM13SMTR | C221842 | out of stock at LCSC |
