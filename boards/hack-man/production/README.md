# Hack-Man rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> Read the permission notice in [../README.md](../README.md) before ordering anything for sale.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `hack-man-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `hack-man-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | 2 | |
| Size | single 92.0 × 42.3 mm; panel 201.0 × 111.6 mm | |
| Thickness | 1.6 mm | |
| Surface finish | **ENIG** | the lettering and pellets are bare copper on the front; ENIG makes them gold and flat |
| Solder mask | Your choice. The maker's built boards are **black**; his design drawing is blue | |
| Silkscreen | **White** | the sprite outlines and the whites of the eyes |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or it gets printed on the art | costs a little extra at JLCPCB |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Bottom only** | every part is on the back |
| Board outline | milled (routed), not V-cut | the shape is irregular |

## The XIAO module (U1) is yours to supply

U1 is in the BOM and placement files with **no LCSC number**. Choose one:

- **Fit it yourself afterwards.** Tell the assembler to skip U1. Solder it by its edge pads with an iron. The LiPo connector will not work this way (its pads are under the module); everything else will.
- **Have the assembler fit it** from modules you send them (consignment) or that they buy for you. This is the only way the pads under the module get soldered, unless you reflow it yourself with paste and hot air or a hot plate.

Whichever XIAO you use (ESP32-C3, S3 or C6), it goes USB socket toward the board edge. Program it over USB-C before or after fitting; see [../firmware/README.md](../firmware/README.md).

## Notes for the assembler (paste into the order remarks)

1. All parts are on the **bottom** side.
2. **D1 to D5** (SK6805-EC3210R) are **side-mounted**: the part lies on its side with the lens pointing along the board toward the small arrow printed beside it (toward the cut-out character shapes). Moisture sensitivity level 4.
3. **U1** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket overhanging the board edge. [Delete whichever does not apply:] Skip U1, we fit it ourselves. / U1 is supplied by us; it also has two pads underneath (BAT+ and BAT−), which need paste.
4. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
5. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability (checked 2026-11-10)

| Part | LCSC | Note |
|---|---|---|
| J1 SAO connector | C492445 | in stock |
| J2 LiPo connector, JST S2B-PH-SM4-TB | C295747 | in stock (2,710) |
| D1–D5 RGB LED, OPSCO SK6805-EC3210R | C5378735 | in stock (18,397), $0.056 @500. "Extended" part at JLCPCB |
| C1–C4 100 nF | C14663 | in stock |
| R1–R3 330 Ω | C23138 | in stock |
| **SW1 switch, C&K PCM13SMTR** | C221842 | **out of stock at LCSC**, as for the other boards. Global Sourcing / consignment at JLCPCB; Digikey 401-2017-1-ND |
| U1 XIAO | — | from Seeed or a distributor |

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs with 0.5 mm mouse-bite holes on the board edge: two on the bottom edge, two on top of the red and cyan ghosts' heads, one on the left end. The right end has no tab, because the USB socket overhangs it. 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py hack-man`.

Panel rule check: no unconnected nets. It reports four "courtyards overlap" errors, which are the single board's allowed data-resistor spacing repeated four times (the panel file does not carry the board's extra rule).

If the XIAO is fitted while the boards are still in the panel, its USB socket overhangs into the 2 mm routed slot by 1.5 mm; that is intended.

## Regenerating

```
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/hack-man/hardware/build_board.py
flatpak run --filesystem=$PWD --filesystem=/tmp --command=python3 org.kicad.KiCad tools/panelize.py hack-man
python3 tools/export_fab.py hack-man
```
