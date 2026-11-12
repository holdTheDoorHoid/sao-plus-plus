# Penghito Poco — SAO++ edition

Originally **Penghito Poco** by **davedarko (Dave Darko)**, from his Simple-Add-ons-SAO collection: https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/Penghito%20Poco ("Small version of the Phengicorn Badge as a simple Add-on").

> **Permission pending — this board is not open-licensed.** The maker's repository states no license, and davedarko has not yet been asked or answered (draft request: [../han-saolo/docs/permission-request.md](../han-saolo/docs/permission-request.md)). The repo owner chose on 2026-11-11 to publish this port anyway. Until the maker says otherwise:
> - the original design in `original/`, the outline and all artwork remain **© davedarko, all rights reserved**; the repo's CERN-OHL-S / CC-BY-SA licenses would cover only the SAO++ additions (new parts placement, routing, scripts, documentation), not the original work
> - do not treat these files as cleared for manufacture or sale
>
> **davedarko, or anyone with rights in this design:** open an issue and it will be changed or removed.
>
> **Where the character comes from is not recorded.** This penguin-unicorn is a small version of the maker's larger "Penghicorn" badge. Nothing in the files says who created that character: it may be davedarko's own or someone else's. Ask the maker; that question is separate from permission for the board.

![front](docs/render-front.png) ![back](docs/render-back.png)

The penguin's two eyes light up white from behind, through the bare board.

## What changed from the original

| | Original (Eagle) | SAO++ rev B |
|---|---|---|
| Connector | 4-pin through-hole header on the right wing (pins and pads visible on the art side) | 6-pin SAO v1.69bis, surface-mount, shrouded and keyed, on the back below the right eye, near where the old header was. Nothing shows on the front |
| Power | Badge only | Slide switch on the bottom edge, between the feet: **SAO / OFF / BAT**. Runs from the badge or from its own CR2032, clipped to the lower left of the back, wholly inside the outline |
| LEDs | 2 × 5 mm round LEDs in the eyes, wired straight to the badge's 3.3 V with **no resistor** | 2 × white reverse-mount 1206 LEDs on the back, at exactly the same two centres, one 1.3 kΩ resistor each |
| Brightness and current | Not limited by anything on the board (each LED took whatever the badge's 3.3 V pushed through it, likely 10 mA or more) | About 0.45 mA per LED on badge power, about 0.2 mA on a fresh cell. **Much dimmer on purpose**, so a coin cell lasts weeks. See the prototype checklist |
| Front art | — | The same shapes: face and belly (silkscreen), horn, beak and feet (bare gold), everything else dark. Changes: the eight old holes are gone; a 2 mm bare-board dot in the middle of each eye; two 0.9 mm holes in the inner toes (the switch's pegs) |
| Back | All copper (ground), nothing printed | Ground copper again, plus the parts and small labels: board name, "by davedarko", "SAO++ rB", SAO / OFF / BAT, "CR2032 + UP", and "1" beside the connector's pin 1 |
| Size | 42.1 × 43.0 mm | **58.9 × 60.2 mm**: the maker's outline and all the art scaled up 1.4 times, same proportions (rev B). Rev A kept the original size |

### How the eyes look now

The old board had two domed 5 mm LEDs standing about 8 mm proud of the front, one in each eye, like two glass beads. **Those are gone, and that is a visible change of character.** The front is now flat: each eye is a dark disc with a small 2 mm dot of bare board in its centre, which looks like a pale pupil or glint when off and glows white when on. The glow is soft and diffused by the board rather than a bright point, and much less bright than the old LEDs. Whether the owner accepts this trade (a flat, robust board with a gentle glow, instead of two eyes that stick out) is a decision for the owner.

**Why white:** the two LEDs are the eyes, sitting exactly where pupils go. White reads as a glint in the eye; red eyes would make a cute penguin-unicorn look menacing. The maker's files do not record the original LED colour. White is the same LED Mad Cat uses for its eyes, so it adds no new part. Its cost: white is the weakest colour on a coin cell (see below).

## Size: scaled up 1.4 times (rev B)

Rev A kept the maker's 42 × 43 mm and paid for it: the coin cell stuck out of the left side by up to 3.3 mm (a silver crescent visible from the front), the clip's ground disc had to be trimmed, two corners of the connector's plastic shroud poked 1.4 mm past the edge beside the right wing, the connector's pads were 0.4 mm from the edge, and two DRC exceptions let the parts' keep-out boxes overlap. The owner decided on 2026-11-12 that a board may be scaled up instead.

Rev B scales the whole outline and all the art by **1.4** about the middle of the board: **58.9 × 60.2 mm** (from 42.1 × 43.0). Every shape keeps its proportions; the eyes, and so the two eye LEDs, move with the art. The parts themselves are real parts and keep their size.

**Why 1.4 and not less:** a search over positions at 1.15, 1.2, 1.25, 1.3 and 1.35 found no layout that puts the cell, its clip, the connector (3 mm from the edge) and the switch on the board without their keep-out boxes overlapping. Even allowing the boxes to overlap where the parts themselves stay 0.3 mm apart (what rev A's exceptions did), nothing fitted below 1.4. The penguin's body is about 28 mm wide below the eyes at 1.0 (not counting the wings); the 22 mm clip and the 16 mm connector side by side need about 1.4 times that. The search tried the clip at right angles only and kept the switch on the bottom edge.

**Why not centred:** the eyes sit in the middle of the board, so a centred connector has to go below them, with the cell stacked below it. That needs **1.5** (63 × 64.5 mm). 1.4 keeps rev A's arrangement (connector right of centre, cell lower left) and is the smallest factor that fixes everything else. The connector centred is an option for the owner (see the list at the end).

## Where the parts went

- **Connector:** below the right eye, 9.4 mm right of and 5.9 mm below the middle of the board, near where the maker's old header was. Its plastic shroud is at least 3 mm inside the edge everywhere; its nearest pad is 7.2 mm from the edge. Key slot up, pin 1 marked.
- **Coin cell:** lower left, with the clip's open side facing the left edge so the cell slides in from there. **The whole cell is inside the outline** (at least 0.3 mm, about 0.4 mm at the closest point, below the left wing), so it does not show from the front. The clip's pads are 1.9 mm inside the edge, and its full 17 mm ground disc is back (rev A trimmed it).
- **Switch:** the bottom edge between the feet, as before. The knob now reaches at least 0.7 mm past the lowest point of the edge across its travel (rev A: 0.2 to 0.6 mm). Its two locating pegs still need two 0.9 mm holes, which land in the feet.
- **Eye LEDs and resistors:** each LED lies flat at its (scaled) eye centre, anode toward the middle of the face, with its resistor 4.3 mm inboard of it. Rev A had to stand the left-eye LED upright to clear the clip; that is no longer needed.
- **Routing:** back copper only, no vias, as before. Nothing touches more than its own pads, and no DRC exceptions are needed for the parts any more.

Real gaps between parts (from the build script): clip's closed end to connector shroud 1.1 mm, cell to connector shroud 2.4 mm, cell to left-eye LED 4.8 mm, clip pads to switch pads 9.2 mm.

**Parts shared with the rest of SAO++:** connector, switch, cell clip, white LED and resistor are the same reels as Mad Cat. **No new parts.**

**Battery life (calculated, not measured):** two white LEDs at about 0.2 mA each is about 0.4 mA, so a CR2032 should last a few hundred hours, getting dimmer toward the end. White LEDs need most of a coin cell's voltage, so they fade early: **best on badge power.**

## Things to check on the first prototype

1. **Brightness.** The LEDs run at a small fraction of the original current. Check the eyes in room light on badge power, then on a fresh cell, then a half-used one. If too dim, change both resistors from 1.3 kΩ to 330 Ω (SAOPP-R-02, already approved): about 1.5 mA per LED on the badge.
2. **The eye windows from the front.** The dot of bare board should glow evenly. Check the light does not spill into a ring around the dot (the copper is cleared 3.2 mm across and the solder mask 2 mm across).
3. **Cell fit.** The cell is now wholly inside the outline. Check it does not show from the front, that it slides in from the left edge, and that it stays put when the board hangs from a badge.
4. **Clip beside the connector.** The clip's closed end sits 1.1 mm from the connector's plastic shroud (calculated from the drawings; rev A: 0.42 mm). Check both sit flat.
5. **Connector strength.** The connector is now 3 mm or more inside the edge with ground copper round it, but it is still 9.4 mm right of the middle. Check it holds firmly.
6. **Knob reach.** The knob tip ends at least 0.7 mm past the edge between the feet. Check it can be slid with a fingernail.
7. **Pin 1 position.** VCC is in the same corner as on Mad Cat and the other boards. Confirm against a v1.69bis badge before a production run.
8. **Switch labels.** As on Mad Cat, the silkscreen assumes "knob toward the SAO label = badge power". If it is the other way round, swap the SAO and BAT labels (OFF is the middle either way).
9. **Weight.** A 59 × 60 mm board (about twice the area of rev A) on a connector right of centre, with the cell on the left. Check it hangs straight and the solder joints survive being knocked. If it hangs crooked, the centred-connector layout at 1.5 is the fix (see below).

## For the owner to decide

- **Size.** 58.9 × 60.2 mm is large for an add-on (rev A was 42.1 × 43.0). It is the smallest uniform scale at which the cell stops showing; nothing smaller was found.
- **Centred connector.** At 1.5 (63.1 × 64.5 mm) the connector can sit in the middle under the eyes with the cell below it, so the board hangs straight. Not built.

## Files

- `hardware/penghito-poco.kicad_pro`: KiCad 10 project (schematic + board). ERC: 0 issues. DRC: 0 errors, 0 unconnected, schematic matches the board. 1 warning: the cell clip differs from its library copy (its own silkscreen arrow and stop line moved to the fab drawing, as on other boards; its two + pads are marked as one piece of metal).
- `hardware/circuit.json`: the circuit as data. `tools/gen_schematic.py penghito-poco` and `hardware/build_board.py` both read it.
- `hardware/extract_art.py`: reads the maker's Eagle file and writes `art/art.json`, the outline and art turned upright and seen from the art side. The maker drew the penguin at 45 degrees, on Eagle's bottom layers.
- `hardware/build_board.py`: builds the whole board from `art/art.json` and `circuit.json`, scaled by `SCALE` (1.4) at the top. Every placement and routing decision is in there with a comment, and it stops with an error if the cell, clip or connector come too close to the edge.
- `hardware/penghito-poco.kicad_dru`: the art rule only. Rev A's two rules letting keep-out boxes overlap are gone.
- `production/`: everything a board house needs, for one board (`single/`) and a 2×2 panel (`panel/`). Start with [production/README.md](production/README.md).
- `original/`: the maker's untouched Eagle board and schematic, the OSH Park picture and readme.

## Parts cost (parts only, list prices checked 2026-11-10 for Mad Cat)

| Part | Qty | Each @ ~100 boards |
|---|---|---|
| Connector XFCN BH254VS-6P (LCSC C492445) | 1 | $0.12 |
| Switch C&K PCM13SMTR (Digikey) | 1 | ~$0.90 |
| CR2032 clip TE BAT-HLD-001 (LCSC C7501066) | 1 | $0.61 |
| LED Lite-On LTW-C230DS white (LCSC C575513) | 2 | $0.055 |
| Resistor 0603 1.3 kΩ (LCSC C22767) | 2 | <$0.01 |
| **Total** | | **about $1.75** |

The CR2032 cell and the bare board are not included.
