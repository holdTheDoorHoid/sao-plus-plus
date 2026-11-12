# COVID-19 Test — SAO++ edition

Originally the **COVID-19 Test SAO** by **davedarko (Dave Darko)**, 2022: https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/COVID-19%20Test%20SAO (project page https://hackaday.io/project/187615-covid-19-sao-simple-add-on)

> **Permission pending — this board is not open-licensed.** davedarko's repository and project page state no license, and he has not yet been asked or answered (draft request: [../han-saolo/docs/permission-request.md](../han-saolo/docs/permission-request.md)). The repo owner chose on 2026-11-11 to publish this port anyway. Until the maker says otherwise:
> - the original design in `original/`, the outline and all artwork remain **© davedarko, all rights reserved**; the repo's CERN-OHL-S / CC-BY-SA licenses would cover only the SAO++ additions (new parts placement, routing, scripts, documentation), not the original work
> - do not treat these files as cleared for manufacture or sale
>
> **davedarko, or anyone with rights in this design:** open an issue and it will be changed or removed.

![front](docs/render-front.png) ![back](docs/render-back.png)

A rapid antigen test cassette, 23.7 × 74 mm (rev B: the maker's 16 × 50 mm board scaled up 1.48 times, see "Rev B: why the board grew"). The control line **C** stays lit; the test line **T** blinks, positive, negative, positive: the maker's joke about not knowing.

## What changed from the 2022 board

| | 2022 original | SAO++ rev B |
|---|---|---|
| Size | 16 × 50 mm | **23.68 × 74.0 mm**: outline and all art scaled 1.48× together, same proportions; parts keep their real size |
| Connector | 2×3 through-hole IDC header (pins visible on the front) | 6-pin SAO v1.69bis, surface-mount shrouded and keyed, where the maker's header was (scaled). Nothing shows on the front |
| Power | Badge only | Slide switch on the right edge (front view), knob out to the right: **SAO / OFF / BAT**. Runs from the badge or from its own CR2032, which clips over the lower part of the back |
| Timer | Readme: LMC555. Schematic and board: NE555D | **LMC555**. The NE555 needs 4.5 V and will not run from 3.3 V or a coin cell; the LMC555 runs down to 1.5 V, same pins |
| LEDs | 2 ordinary red LEDs soldered upside down | 2 red LEDs made to be mounted upside down (same Lite-On family the other boards use), in the same spots (scaled with the art), one 1.3 kΩ resistor each |
| Blink | see below: three different answers in the maker's files | T on 0.46 s, off 0.23 s, about 1.5 times a second |
| Art | — | Everything the maker drew, scaled 1.48×: front window, C and T lines, sample well, shading and "COVID-19Ag"; on the back his URL, handle, date and dd logo **where he put them**. **Added:** two 0.9 mm holes near the right edge of the front (the switch's pegs). **Removed:** his back assembly note (it names his old parts and would sit under the cell) |

**Parts shared with the rest of SAO++:** connector, switch, cell clip, red LED, 1.3 kΩ resistor and 100 nF capacitor. **New parts:** the LMC555 timer and one resistor value (3.3 MΩ, used twice). The clip uses the shared footprint unchanged.

### The blink, and the three sets of values

The maker's readme, schematic and board file each list different parts. In a 555 blinker two resistors and one capacitor set the speed (R1 and R2 with C1 here); the other two resistors only limit LED current (R3 for C, R4 for T).

| Source | Timing parts | T blinks | LED resistors | Side effect |
|---|---|---|---|---|
| Readme | 100 Ω, 390 kΩ, 1 µF | 0.27 s on / 0.27 s off | 150 Ω (C), 100 Ω (T): ~10 mA each | 33 mA wasted in R1 every off half |
| Schematic | 100 Ω, 39 kΩ, 10 µF | 0.27 s on / 0.27 s off (same speed) | 100 Ω each | same 33 mA waste |
| Board file, iBOM (what was built) | 1 kΩ, 470 kΩ, 1 µF | 0.33 s on / 0.33 s off | 1 kΩ each: ~1.5 mA | 3.3 mA wasted every off half |
| **SAO++** | **3.3 MΩ, 3.3 MΩ, 100 nF** | **0.46 s on / 0.23 s off** | **1.3 kΩ each: ~1 mA** | under 1 µA |

Why not keep the built board's 50/50 rhythm: with a 555, an even blink needs a small R1, and a small R1 is a short from the supply to ground half of the time. With the shared 1.3 kΩ there it would waste about 1.2 mA on average, nearly doubling the drain on the coin cell. Making R1 equal to R2 removes that waste and needs only one new resistor value; the price is a longer "on" than "off". The capacitor is the shared 100 nF, so the speed varies about ±15 % between boards.

**Battery life (calculated, not measured):** C lit ~0.9 mA + T on two-thirds of the time ~0.6 mA + timer ~0.1 mA ≈ 1.6 mA, so a CR2032 should last roughly 100–130 hours, dimming toward the end. Both LEDs still glow at 2.4 V.

## Rev B: why the board grew

Rev A kept the maker's 16 × 50 mm and paid for it: the 20 mm coin cell hung 2 mm past both long edges, the clip's closed end stuck out 3.1 mm, the clip needed a home-made narrowed footprint, the maker's back credits had to move to the front, and two covered vias tied the front copper in as ground. The owner decided on 2026-11-12 that tight boards may be scaled up instead. Rev B scales the outline and all the art together by **1.48** (23.68 × 74.0 mm); the parts keep their real size.

**Why 1.48 and not less.** The cell clip lies lengthwise (its pads 21 mm apart run along the board): cell on one side, the clip's closed end on the other, 21 mm in all. That needs the board at least 21.5 mm wide (**1.344**), and at that size everything is on the board. But the maker's hackaday URL runs up the left edge of the back, and from 1.344 up to 1.47 the cell would sit over its first few letters ("https:"). At 1.344 the switch also has no room between the maker's logo and the clip. **1.48 is the smallest factor at which the cell, clip, switch and connector all fit with every one of the maker's credits uncovered.** Tried: 1.344, 1.375, 1.45 (URL start hidden under the cell), 1.48 (clean).

**If a slight overhang is acceptable instead** (calculated, not built): letting the cell and the clip's closed end stick out up to 1 mm, the smallest factor is **1.41** (22.6 × 70.5 mm) with the URL still uncovered, or **1.36** (21.8 × 68 mm) if the cell may also cover the start of the URL. Below about 1.36 the switch no longer fits between the logo and the clip, so overhang buys little: the cell is not the only thing that is tight.

### The coin cell

The cell sits in the shared clip, lengthwise on the lower part of the back, wholly on the board: 2.3 mm inside the left edge (front view), where its open side faces and the cell slides in; the clip's closed end is 0.39 mm inside the right edge, and its pads are at least 2 mm from the bottom edge. The full 17 mm contact disc is used. The cell still covers the back of the sample well, as in rev A.

### Where things are on the back

Seen from the front, so mirrored compared with looking at the back: at the top, the maker's "2022/11" and "@davedarko@chaos.social", then the connector (where his header was, 4.2 mm from each long edge). His URL runs up the left edge, his dd logo sits right of the result window. The switch is on the right edge between the logo and the cell clip; the two LED resistors sit left of the LEDs; the timer and its timing parts sit below the result window, the timing capacitor right of it and the supply capacitor left of it; then the cell clip.

Everything is routed on the back copper, which is otherwise ground. **No vias.** The front copper is the maker's pour, unconnected, as he had it.

## Things to check on the first prototype

1. **Blink and brightness.** Both LEDs at about 1 mA through 1.6 mm of board. Check C and T in room light, on badge power and on a cell. If too dim, R3/R4 can drop to the shared 330 Ω (about 3–4 mA each, shorter cell life).
2. **Coin cell fit.** Check the cell slides in from the left (front view) and seats firmly on the contact.
3. **Pin 1 position.** VCC is top left in front view, as on Mad Cat. Confirm against a v1.69bis badge.
4. **Switch labels.** "SAO" is printed above the switch and "BAT" below it (on the back). The labels assume the knob points at the label for that position; if wrong, swap them.
5. **Size and weight.** The board is now 23.7 × 74 mm, with the cell near the bottom; check it hangs well from the badge connector.

## Decisions for the owner

1. **Publish or not before davedarko answers:** the owner chose on 2026-11-11 to publish with permission pending.
2. **1.48 (no overhang, every credit visible) or smaller.** Built at 1.48. Alternatives: 1.41 with up to 1 mm of cell and clip past the edges, or 1.36 if the cell may also hide the start of the maker's URL (see "Rev B: why the board grew").
3. **Switch on the side.** It moved from the top edge to the right edge, because the top of the back is the maker's credit block.

## Files

- `hardware/covid-test.kicad_pro` — KiCad 10 project. ERC: 0 violations. DRC: 0 errors, 0 unconnected, schematic matches board. 21 warnings, none electrical: 17 the maker's shading dots crossing his own mask windows (as in 2022), 3 art libraries not installed, 1 "clip footprint differs from library" (its silk moved to the fab layer).
- `hardware/circuit.json` — the circuit as data; `tools/gen_schematic.py covid-test` and `hardware/build_board.py` both read it.
- `hardware/build_board.py` — rebuilds the board from `original/` plus the SAO++ changes; `SCALE` at the top is the scale factor.
- `hardware/parts_local.py`, `hardware/covid-test-local.pretty/` — the two board-only parts (timer, 3.3 MΩ resistor).
- `production/` — files for one board and a 2×2 panel; see [production/README.md](production/README.md).
- `original/` — the maker's files, untouched. The three Gerber zips are three revisions: `CovidSAO.zip` (2022-09-06, back reads "2022/08", one long front window, different LED layout), `CovidSAO2.zip` (2022-09-21, "2022/09", same copper as the board file), `CovidSAO3.zip` (2022-11-14, "2022/11", Mastodon handle, URL, assembly note) — **the last one matches `drawing.kicad_pcb`**, which is what this port starts from. The iBOM (2022-09-21) lists the board file's values.

## Parts cost (parts only, list prices from docs/parts.md, 2026-11-10)

| Part | Qty | Each @ ~100 boards |
|---|---|---|
| Connector XFCN BH254VS-6P (LCSC C492445) | 1 | $0.12 |
| Switch C&K PCM13SMTR (Digikey) | 1 | ~$0.90 |
| CR2032 clip TE BAT-HLD-001 (LCSC C7501066) | 1 | $0.61 |
| LED Lite-On LTST-C230KRKT red (LCSC C125107) | 2 | $0.037 |
| Resistor 0603 1.3 kΩ (LCSC C22767) | 2 | <$0.01 |
| Capacitor 0603 100 nF (LCSC C14663) | 2 | <$0.01 |
| Timer TI LMC555CMX/NOPB | 1 | price not yet checked |
| Resistor 0603 3.3 MΩ (UNI-ROYAL 0603WAF3304T5E) | 2 | price not yet checked |
| **Total** | | **about $1.75 plus the timer** |

New reels for SAO++: the LMC555 and the 3.3 MΩ resistor (two new lines; every other part is shared).
