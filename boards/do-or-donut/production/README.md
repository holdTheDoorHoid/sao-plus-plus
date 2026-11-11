# Do Or Donut rev A — ordering files

> Design-checked only. No board has been built from these files yet: order a small first batch (5–10) before any production run, and go through the prototype checklist in [../README.md](../README.md).
>
> Read the permission notice in [../README.md](../README.md) first. **Not yet decided:** the repo owner has not said whether this board may be published or made before davedarko answers.

## What to upload

| You want | Upload | From |
|---|---|---|
| Bare boards, one design per board | `do-or-donut-gerbers.zip` | `single/` |
| Bare boards, 4-up panel | `do-or-donut-panel-gerbers.zip` | `panel/` |
| Assembled by **JLCPCB** | the Gerber zip, then `…-bom-jlcpcb.csv` and `…-cpl-jlcpcb.csv` | `single/` or `panel/` |
| Assembled by **PCBWay** | the Gerber zip, then `…-bom-pcbway.csv` and `…-centroid-pcbway.csv` | `single/` or `panel/` |

Use the files from **one** folder together. The panel's parts are numbered per board (J101, J201 …; the LEDs DA101, DB201 …), so the panel BOM and placement files only match the panel Gerbers.

## Order settings

| Setting | Value | Why |
|---|---|---|
| Layers | **4** | the maker's matrix routing on the outer layers, the SAO++ additions on the two inner ones (see ../README.md). Stack-up: the fab's standard 4-layer 1.6 mm |
| Size | single 50.8 × 50.8 mm (round, with an 18.9 × 15.5 mm hole); panel 118.6 × 128.6 mm | |
| Thickness | 1.6 mm | |
| Minimum track / gap | **0.127 mm (5 mil)** | the maker's matrix routing is drawn at 5 mil; standard at JLCPCB and PCBWay for 2 layers |
| Vias | 0.3 mm drill / 0.6 mm pad (new) and 0.33 / 0.686 mm (the maker's), all through-hole and **tented** (covered by mask) | |
| Surface finish | ENIG or HASL | nothing on this board is bare copper art; ENIG solders the 0.65 mm-pitch driver and the 0603 LEDs flatter |
| Solder mask | **Your choice — it is the icing.** The bare-board rim and the ring round the hole are the "dough" (no mask there) | The maker's files do not say what colour he used; pink or white mask suits the idea. Check a photo on his project page |
| Silkscreen | White | the credit and logos are on the back |
| Copper | 1 oz | |
| "Remove order number" / "specify location" | Remove it, or put it on the back | the front is all LEDs and icing |
| Panel option at the fab | single files: "single piece". Panel files: "panel by customer", 4 boards | |
| Assembly side | **Both sides** | the 144 LEDs are on the **front**; everything else is on the back |
| Board outline | milled (routed), not V-cut | round, with a hole in the middle |

## The XIAO module (U2) is yours to supply

U2 is in the BOM and placement files with **no LCSC number**. Either fit it yourself afterwards with an iron (the LiPo connector then does not work, because the module's battery pads are underneath it), or have the assembler fit modules you send them. Its USB-C socket goes to the bottom edge, overhanging it slightly.

## Notes for the assembler (paste into the order remarks)

1. Parts on **both** sides: 144 LEDs (DA1–DA72, DB1–DB72) on the **top**; everything else on the **bottom**.
2. **All 144 LEDs are the same part.** Pad 1 is the cathode. The LEDs sit at many different angles (they follow the donut); please check the polarity of a few in your preview.
3. **U1 (IS31FL3731, SSOP-28, 0.65 mm pitch)** on the bottom.
4. **U2** is a Seeed Studio XIAO module soldered flat by its castellated edges, USB socket at the board edge. [Delete whichever does not apply:] Skip U2, we fit it ourselves. / U2 is supplied by us; it also has battery pads underneath, which need paste.
5. **SW1** has two plastic pegs that sit in the two 0.9 mm holes.
6. Please confirm part rotations in your placement preview before running. The rotation values come straight from KiCad and have **not** been tried on a real line.

## Parts availability

LCSC numbers for the three parts only this board uses (the LEDs, the IS31FL3731 and the 20 kΩ resistor) are **not filled in yet**: the colour of the LEDs is still to be chosen, and the other two are to be looked up and checked. Shared parts are as listed in `docs/parts.md`. **SW1 (C&K PCM13SMTR) is out of stock at LCSC**, as for the other boards.

## The panel

2 × 2 boards, each in its own routed pocket (2 mm slot), held by five break-off tabs each with 0.5 mm mouse-bite holes on the board edge: at 3, 5, 7, 9 and 11 o'clock (seen from the front). They sit where all copper is at least 0.55 mm from the edge, so the holes stay clear of it, and away from the USB-C end (6 o'clock), the switch (about 2 o'clock) and the LiPo connector (about 8 o'clock). 5 mm rails top and bottom carry fiducials and tooling holes. Recipe: `panel.json`; rebuilt by `tools/panelize.py do-or-donut`.

Panel rule check: 0 errors, 0 unconnected. Warnings only (the board's own, four times over, plus the panel file not finding the board's local footprint library).

## Regenerating

```
python3 boards/do-or-donut/hardware/extract_matrix.py
python3 boards/do-or-donut/hardware/make_circuit.py
python3 tools/gen_schematic.py do-or-donut
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/do-or-donut/hardware/build_board.py
flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py do-or-donut
python3 tools/export_fab.py do-or-donut
python3 boards/do-or-donut/production/add_inner_layers.py   # export_fab only knows two-layer boards
```

`build_board.py` replays the router's saved result (`hardware/routes.json`) and takes a few minutes. To route again from scratch, set `DONUT_REROUTE=1` (about five minutes on four layers; the router stops by itself after 20).
