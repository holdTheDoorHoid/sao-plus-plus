# Oh My Glob (LSP) — SAO++ edition

Originally the **LSP SAO** ("Oh My Glob SAO") by **lemons4all**, made for DEF CON 26 (2018): https://hackaday.io/project/161510-lsp-sao

> **Permission pending — this board is not open-licensed.** The original hackaday.io page states no license, and lemons4all has not yet been asked or answered (draft request: ../rbg/docs/permission-request.md). The repo owner chose on 2026-11-10 to publish this port anyway. Until the maker says otherwise:
> - the original design in `original/`, the outline and all artwork remain **© lemons4all, all rights reserved**; the repo's CERN-OHL-S / CC-BY-SA licenses cover only the SAO++ additions (new parts placement, routing, scripts, documentation), not the original work
> - do not treat these files as cleared for manufacture or sale
>
> **The character belongs to someone else too.** The board is drawn as Lumpy Space Princess from the cartoon *Adventure Time*, owned by Cartoon Network / Warner Bros. Discovery. That is separate from the maker's permission: even with lemons4all's blessing, selling boards with her likeness needs the rights holder's permission or new art.
>
> **lemons4all, or anyone with rights in this design:** open an issue and it will be changed or removed.

![front](docs/render-front.png) ![back](docs/render-back.png)

The star on her forehead glows white and the ball on the tip of her crown glows red, both lit from behind through the bare board.

## What changed from the 2018 board

| | 2018 original | SAO++ rev A |
|---|---|---|
| Connector | 4-pin through-hole in the middle bottom lobe (pins visible on the art side) | 6-pin SAO v1.69bis, surface-mount, shrouded and keyed, in the same lobe. Nothing shows on the front |
| Power | Badge only | Slide switch on the right side of the head: **SAO / OFF / BAT**. Runs from the badge or from its own CR2032, clipped to the right lobe on the back |
| Star LED | OSRAM TOPLED (obsolete) on the back | White reverse-mount 1206 LED in the same spot, 1.3 kΩ resistor |
| Crown-tip LED | 3 mm LED standing up on the **front**, legs through the board | Red reverse-mount 1206 LED on the **back**, shining through a 2 mm bare window (no copper, no solder mask) at the same spot. Nothing sticks out of the art any more |
| Front art | — | Unchanged apart from: two 0.9 mm holes on the right side of the head (the switch's pegs), a 2 mm window at the crown tip, two tiny covered holes in the mouth (see below), and the old header's holes gone |
| Back art | — | "OH MY GLOB / SAO / DEF CON 26" and the "Thanks To" credits are where they were and untouched. The fitted cell hides the end of "DEF CON 26" (see below). Labels added: SAO / OFF / BAT, "CR2032 + SIDE UP", an arrow for the cell, "SAO++ rA", "1" at the connector |

## The trade-offs on this board (owner, please look)

This outline is all round lobes, and the back is mostly lettering, so the standard parts only just fit. What was given up:

1. **Two tiny holes in the mouth.** On one copper layer the badge-power wire and the LED-supply wire have to cross once. They cross inside the open mouth: two 0.6 mm holes (vias), covered by solder mask on both sides, joined by a 1.6 mm copper link on the front. The mouth is the dark area of the art, so they sit on dark mask between the teeth; up close they may show as two pinprick bumps and a faint line. This was option B, approved 2026-11-11. Moving the "Thanks To" credits instead (as on Frida) was considered first. It would not have helped: without holes, the switch has to sit on the short stretch of edge between the connector and the cell, and no spot there leaves any knob showing without the switch hitting one of them. (This was worked out from the layout and a search of switch positions. A version with the credits moved was not built.)
2. **The coin cell covers the end of "DEF CON 26".** Its 17 mm contact disc fits in exactly one spot on the back without printing over lettering. While a cell is fitted it hides about 1.2 mm² of ink ("26"). The disc's edge also trims a 0.005 mm² sliver (a few hundredths of a millimetre) off the tip of the "6". The cell overhangs the edge by about 1 mm at the notch below it.
3. **The switch knob only just shows.** No part of this edge is straight for 10 mm; every lobe curves. A search over the whole outline found no spot where more than about 0.45 mm of the knob sticks out past the edge. Here it is about 0.4 mm, on the side of the head. A fingernail moves it; a thumb may not.
4. **Two wires run between words.** The LED supply goes down the gap between "OH" and "MY", and the badge supply down the gap between "MY" and "GLOB" and round the end of "SAO". No wire crosses a letter (the script checks this; the closest is 0.5 mm), but under the mask they show as two faint lines through the lettering block.

## Things to check on the first prototype

1. **Brightness.** Red tip: about 1.0 mA on a cell, 1.2 mA on the badge. White star: about 0.2 mA on a fresh cell, 0.45 mA on the badge; white is the weakest colour on a coin cell. If the star is too dim, change R2 alone to 330 Ω (SAOPP-R-02).
2. **Knob.** Check the switch can be slid comfortably (about 0.4 mm of knob shows). The labels assume "knob toward the SAO label = badge power"; if it is the other way round, swap SAO and BAT on the silkscreen.
3. **Connector and cell clip.** The connector's plastic shroud ends 0.1 mm from the clip's lower solder pad (DRC rule in `hardware/lumpy.kicad_dru`). Check the clip's leg clears the shroud. The clip's open side faces the right edge (the "<" arrow): the cell slides in from there.
4. **Vias.** Check the two covered holes in the mouth are not noticeable, and that the board house tented them (no copper showing).
5. **Pin 1 position.** VCC and GND are in the same corner as on the 2018 header. Confirm against a v1.69bis badge.
6. **Weight.** A 51 × 71 mm board hanging from one surface-mount connector at the bottom, with the cell on one side. Check it sits firmly in a badge.
7. **Notches.** The outline has very narrow notches between lobes (as in 2018). The router cannot cut them as narrow as drawn; they will come out slightly rounded.

**Battery life (calculated, not measured):** about 1.2 mA total on a cell, so roughly 150 hours from a CR2032, the white star fading first.

## Files

- `hardware/lumpy.kicad_pro`: KiCad 10 project (schematic + board). ERC: 0. DRC: 0 errors, 0 unconnected, schematic matches the board. Warnings left: 3 for the art footprints' libraries not being installed; 1 because BT1 differs from its library copy (see below); 3 silkscreen clipped by pads (the "6" sliver, and the connector's outline line where it meets the clip pad); 2 connector outline lines clipped by the board edge at the bottom notches.
- `hardware/circuit.json`: the circuit as data; `tools/gen_schematic.py lumpy` and `hardware/build_board.py` both read it. Standard switch wiring: pin 1 badge, pin 3 LEDs, pin 4 cell.
- `hardware/build_board.py`: rebuilds the board from `original/` plus the SAO++ changes. Board-specific workarounds, all explained in comments there:
  - the clip's two "+" pads are declared joined inside the part (`SetDuplicatePadNumbersAreJumpers`) instead of by a track that would have to cross the lettering;
  - the clip sits at 269.9° rather than 270°, because KiCad 10 calls the shared clip footprint's courtyard "malformed" at exact right angles;
  - the clip's own silkscreen (closed-end line, arrow, "+") moved to the fab layer, because it would print across the credits and off the edge; the board carries its own labels;
  - the maker's 2 mm back mask window behind the star was dropped: it touched the new LED's pad openings, and the LED brings its own 1.9 mm window;
  - the ground pour's two halves (split by the LED-supply wire) join in the gap between R1's pads.
- `hardware/lumpy.kicad_dru`: the art rule, plus one rule letting the connector's and clip's keep-out boxes overlap (real gap 0.1 mm, see prototype item 3).
- `production/`: everything a board house needs, for one board and a 2×2 panel. Start with [production/README.md](production/README.md).
- `original/`: the untouched 2018 KiCad 5 project and zip from hackaday.io.

## Parts cost (parts only, list prices checked 2026-11-10)

| Part | Qty | Each @ ~100 boards |
|---|---|---|
| Connector XFCN BH254VS-6P (LCSC C492445) | 1 | $0.12 |
| Switch C&K PCM13SMTR (Digikey) | 1 | ~$0.90 |
| CR2032 clip TE BAT-HLD-001 (LCSC C7501066) | 1 | $0.61 |
| LED Lite-On LTST-C230KRKT red (LCSC C125107) | 1 | $0.037 |
| LED Lite-On LTW-C230DS white (LCSC C575513) | 1 | $0.055 |
| Resistor 0603 1.3 kΩ (LCSC C22767) | 2 | <$0.01 |
| **Total** | | **about $1.73** |

The CR2032 cell and the bare board (51 × 71 mm) are not included. No new parts: everything is already on the SAO++ list.
