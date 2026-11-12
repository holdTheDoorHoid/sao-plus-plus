# Mysterio — SAO++ edition

Originally **Mysterio SAO** by **davedarko (Dave Darko)**, January 2025: https://github.com/davedarko/Simple-Add-ons-SAO/tree/main/MysterioSAO

> **Permission pending — this board is not open-licensed.** The maker's repository states no license anywhere, and he has not yet been asked (draft request: [../han-saolo/docs/permission-request.md](../han-saolo/docs/permission-request.md)). The repo owner chose on 2026-11-11 to publish this port anyway. Until the maker says otherwise:
> - the original design in `original/`, the outline and all artwork remain **© davedarko, all rights reserved**; the repo's CERN-OHL-S / CC-BY-SA licenses cover only the SAO++ additions (new parts placement, routing, scripts, documentation), not the original work
> - do not treat these files as cleared for manufacture or sale
>
> **The character belongs to someone else too.** Mysterio, the Spider-Man villain with the glass-bowl helmet, is a Marvel character, owned by Marvel / Disney. That is separate from the maker's permission: even with davedarko's blessing, selling boards with his likeness needs the rights holder's permission or new art.
>
> **Credit where the maker gives it:** his write-up says the design was heavily inspired by the Marvel hero simple add-ons by Simen (https://mastodon.social/@simenzhor/).
>
> **davedarko, or anyone with rights in this design:** open an issue and it will be changed or removed.

![front](docs/render-front.png) ![back](docs/render-back.png)

Mysterio's fishbowl helmet glows from inside: four colour-changing LEDs round the bottom of the helmet shine across the back of the board, and the light comes through the bare board on the front, with the skull and the smoky swirl drawn in copper as shadows.

## What changed from the original

| | Original (2025) | SAO++ rev B |
|---|---|---|
| Controller | WCH CH32V003 (8-pin chip, programmed by the Supercon badge) | **Seeed Studio XIAO ESP32** module soldered flat on the back: C3, S3 or C6 all fit the same pads. USB-C at the bottom edge for power and programming |
| Board | 4 copper layers. 38.8 × 34.1 mm | **2 copper layers**, like every SAO++ board. The maker's whole design **scaled up 1.3×** (39 → 50.4 mm wide), plus a 10 mm base strip below the arms: **50.4 × 52.9 mm** (see "Why the board is bigger") |
| Helmet art | Skull and swirl in copper on the inner layer nearest the back | The same shapes, 1.3× larger, on the back copper (0.1 mm further from the front). The back's solder mask is open only where the maker's was open **and** no copper is behind it, so light gets into the board in the same places |
| Connector | 2×3 through-hole IDC header, its six pads showing on the chest | 6-pin SAO v1.69bis, surface-mount, shrouded and keyed, on the back, below the helmet and left of middle. The six round pads stay on the chest as plain copper "buttons" (no holes) |
| Power | Badge only | Slide switch on the bottom edge: **SAO** (badge power) / **OFF** / **USB/BAT** (the module's own USB-C or a LiPo). **JST-PH LiPo connector** on the bottom edge, charged by the XIAO |
| LEDs | 4 × SK6805-EC3210R side-firing RGB, chained right to left (seen from the front) | Same part, **same order, same count, same directions**, at the scaled-up positions. D2 and D3 exactly there; D1 and D4 **0.96 mm and 0.78 mm further out** along their own aim line (see below) |
| Other parts | two 10 kΩ, one 100 nF | 100 nF kept (now beside the XIAO's 3V3 pin). The two 10 kΩ were I2C pull-ups to the chip's supply; the SAO standard leaves those to the badge, so they are gone. Four 330 Ω resistors added (all one part, see below) |
| Front art | Robe, collar, chest plate, diamonds, helmet window; seven tiny via dots | All unchanged except bigger, plus a plain **base strip** below the arms (copper under the mask, the same green as the robe, joined to the chest plate). The maker's seven via dots are gone. In the base strip only: four covered vias (pinpricks), one thin covered line 13.7 mm long (see "What shows on the front"), and two 0.9 mm holes (the switch's pegs). The art steps back from the edge at the panel tabs |
| Back | Maker's credit "@davedarko 2025/01" | The credit is scaled with the art (1.3× larger) and sits where the art puts it, on the left arm. Labels added: "NO USB ON SAO", "MYSTERIO rB", "SAO++", the switch legend, "+" / "−" at the LiPo connector, "1" at the connector |

**Parts shared with the rest of SAO++:** connector, switch, XIAO footprint, LiPo connector, RGB LED, 100 nF capacitor and the 330 Ω resistor. **No new parts.**

## Why the board is bigger (owner decision 2026-11-12)

Rev A kept the maker's size and paid for it: a 12 mm strip under the figure, a straightened right arm (up to 3.4 mm wider), no LiPo connector (the controller standard asks for one), the connector 7.5 mm left of middle, and extra rule-check exceptions letting R2, R3, R4 and the XIAO crowd into the connector's space. Under the owner's scaling rule rev B scales the maker's whole design up **1.3×** (outline, all art, the credit and the LED positions together, about the middle of his outline; the parts keep their real size).

| | rev A | rev B |
|---|---|---|
| Scale | 1.0 | **1.3** |
| Size | 40.7 × 46.2 mm | **50.4 × 52.9 mm** |
| Base strip below the arms | 12.1 mm, plus a straightened right arm | **10.1 mm** (shrunk), arms exactly as the maker drew them (scaled) |
| LiPo connector | none | **yes**, JST-PH on the bottom edge |
| Connector | 7.5 mm left of the board's middle, centre 9 mm above the bottom | 7.8 mm left of the middle, centre 16 mm above the bottom (higher, under the helmet; not more central sideways) |
| Rule exceptions for crowded parts | 3 | **none** |
| Vias | 2, in the front art | **4**, all in the plain base strip, plus one short covered front track (below) |

**Why 1.3 and not less.** The base strip cannot go: the XIAO is 21 × 17.8 mm and its USB end must sit at an edge, and the maker's figure (a helmet on shoulders, with notches between arms and torso) only has room for it at about 1.8× (some 70 × 61 mm). So the strip stays and the question was how little to scale. Below about 1.15× the XIAO and the connector do not fit side by side between the maker's credit and the unstraightened right arm. At 1.25× they fit (about 48.5 × 51 mm), but the two 330 Ω resistors on the SAO GPIO lines (R2, R3) have nowhere to go outside the connector's and the XIAO's space (0.9 mm between them), which would bring back the rule exceptions. At 1.3× there is 2.3 mm between connector and XIAO, enough for R2 and R3 to stand there upright, and every part has its own space.

## What shows on the front

All of it is in the plain base strip below the figure, under the green mask; none of it touches the maker's art or lettering.

- **Four covered vias** (0.3 mm holes, covered by mask both sides): pinprick bumps. Two carry the LiPo + line (at 20.2, 54.9 and 33.9, 54.9 mm); two join the back's ground to the front's ground plate (at 10.6, 56.4 and 22.2, 60.8 mm).
- **One thin line**, 13.7 mm long, between the two LiPo vias: a 0.3 mm copper track with a 0.3 mm gap either side in the strip's ground copper. Under green mask it shows as a faint straight line.
- **Two 0.9 mm holes** for the switch's locating pegs, bottom left.

The LiPo + line has to cross the SDA, OFF and connector-ground copper between the LiPo connector and the module's battery pads. That was chosen over squeezing it between two of the XIAO's edge pads with only 0.17 mm to spare.

## How the power switch works here

The switch now sits on the bottom edge, knob pointing down.

| Knob (labels "SAO" and "USB/BAT" printed beside it on the back) | Badge 3.3 V | What runs the board |
|---|---|---|
| **SAO** | connected to the XIAO's 3V3 pin and the LEDs | the badge |
| **OFF** (middle) | disconnected | nothing from the badge. If USB or a LiPo is connected, the switch tells the XIAO to blank the LEDs and sleep (with a LiPo this is a sleep, not a hard cut) |
| **USB/BAT** | disconnected | the XIAO's own regulator, from USB-C or the LiPo |

- **Do not plug in USB while the knob is on SAO and the board is on a badge.** Two 3.3 V regulators would be joined. It is printed on the back.
- **LiPo:** a 3.7 V single cell on the JST-PH connector, wired to the XIAO's battery pads (both the C3/S3 and the C6 positions). The XIAO charges it from USB-C. "+" and "−" are printed beside the connector; many cheap cells are wired the other way round and there is no protection, so check before plugging in.
- **Feeding the XIAO through its 3V3 pin** is how badge power reaches it, as on Hack-Man. Seeed documents that pin as an output only. First thing to test on each module type.
- **No coin cell:** these LEDs and an ESP32 need far more than a CR2032 gives.

## How it is wired

Nearly everything is on the back copper:

- The helmet's solid outer ring of art copper (it was copper on the maker's board too) **carries the LEDs' 3.3 V**: each LED's supply pad reaches into it. Ground comes from the copper outside the ring. That is why D1 and D4 moved out 0.96 / 0.78 mm: at their scaled spots their pads would sit on the ring.
- The switched 3.3 V runs from the switch up the left arm (under the credit's lettering) to LED D4; the XIAO's 3V3 pin feeds LED D1 from the right. Both reach the ring.
- **R1** (LED data) stands on LED D1's own axis just outside it, and the 3.3 V feed to D1 passes between its two pads; **R3** (SAO GPIO2) lets SCL pass between its pads; **R4** (the switch's OFF sense line) lets the badge 3.3 V pass between its pads. R4 exists only for this; a 330 Ω in a sense line changes nothing.
- The LiPo + line hops to the front for 13.7 mm (above).
- The back's ground comes out in two pieces (the small one round the LiPo connector's − pin, and everything else); each is joined to the front's ground plate by one covered via.

## Things to check on the first prototype

1. **Badge power into the XIAO's 3V3 pin** (above). Check it boots from a badge with nothing else attached, and that nothing gets warm.
2. **LiPo polarity and charging.** Plug a known-good cell in the right way round (+ as printed), check the XIAO charges it from USB-C, and that the board runs from it with the knob on USB/BAT.
3. **The glow.** The helmet art is now on the back copper instead of 0.1 mm inside the board, and 1.3× larger. Compare with a built original if you can.
4. **LED land pattern.** The shared LED footprint's pads are smaller than the maker's (which he built and which worked): see "LED footprint" below. Check the LEDs sit square and the lenses point at the helmet's centre. Hack-Man's maker needed a blob of hot glue over each LED as a diffuser.
5. **LED supply.** They are rated 3.7–5.5 V and run here from 3.3 V, as on the original.
6. **Switch labels.** Which way the knob sits for "position 1" (SAO) is not drawn in the datasheet. If SAO and USB/BAT turn out swapped, the silkscreen is wrong, not the wiring.
7. **Connector position and pin 1** against a v1.69bis badge. The board is now bigger (50 × 53 mm) and hangs from one SMD connector 7.8 mm left of its middle: check it hangs straight and the joint does not flex.
8. **USB plug clearance** at the bottom edge, and that the XIAO, its USB-C socket, the LiPo plug and the connector clear the badge behind.
9. **XIAO pads underneath.** The ground and battery pads under the module only solder with paste and hot air or a hot plate. **The LiPo only reaches the module through those battery pads**, so a board with a LiPo needs the module reflowed (or the pads hand-tinned first). Without a LiPo, hand-soldering the edge pads only is enough.
10. **The front line.** Look at the 13.7 mm LiPo track and the four vias in the base strip on a real board, to see how much they show through the mask.

## Pin map

Unchanged from rev A, so the firmware in `firmware/` applies as it is. Same four LEDs, same order.

| XIAO pin | Goes to |
|---|---|
| D10 | LED data, through R1 (330 Ω). LED 1 is the right-hand LED seen from the front (lower right of the helmet), then D2, D3, D4 round to the left, as on the original |
| D4 / D5 | SAO SDA / SCL (no pull-ups on the board) |
| D7 / D6 | SAO GPIO1 / GPIO2, each through 330 Ω (R2 / R3) |
| D1 | switch OFF sense, through R4 (330 Ω): high when the knob is on OFF |
| 3V3, GND | the board's 3.3 V rail (switch common, LEDs) and ground |
| BAT+ (two positions under the module) | the LiPo connector's + pin (new in rev B) |
| D0, D2, D3, D8, D9, 5V | not connected (D0, D2, D8, D9 are start-up strapping pins on one module or another) |

## Firmware

The SAO++ firmware (Rust, built but not yet run on a board) is in [firmware/](firmware/README.md); rev B did not change any pin, so it applies unchanged. The maker's sketch for it is `original/Sketchbook/strandtest/strandtest.ino` (Arduino, Adafruit NeoPixel library, 4 LEDs; the other four sketches in that folder are for other projects: an 84-LED "hexaFlower", an SD-card test and a WAV player). What it does, so it can be reproduced:

- brightness 200 of 255; colours from a 12-step palette running from deep blue (#000b2d) through cyan to white (#ffffff)
- every 40 ms it repaints one LED, in order 1→4, with palette entry (LED number + a counter) mod 12, and adds one to the counter
- after each pass over the four LEDs the counter jumps to a random value 0–7

The effect is an icy blue-to-white shimmer that keeps changing. To run something like it here: drive the four LEDs from XIAO D10 (GRB order, 800 kHz), and treat D1 high as "off".

## LED footprint: maker's vs shared

Both put the four pads in a row (DOUT, GND, VDD, DIN) with their back edges level and the longer outer pads reaching toward the lens. The differences:

| | Maker's footprint (built) | Shared `LED_RGB_Side_SK6805` |
|---|---|---|
| Outer pads (DOUT, DIN) | 0.70 × 1.00 mm, centres 3.01 mm apart | 0.55 × 0.70 mm, centres 2.81 mm apart |
| Inner pads (GND, VDD) | 0.50 × 0.50 mm, centres 0.85 mm apart | 0.55 × 0.50 mm, centres 0.85 mm apart |
| Overall width of the pad row | 3.71 mm | 3.36 mm |
| Where it draws the lens face | 0.88 mm in front of the pads' back edge | 1.17 mm in front |

The shared pads sit almost entirely inside the maker's (within 0.03 mm), so a part that solders on his pads should solder on these. The two footprints disagree by about 0.3 mm about where the body sits; neither drawing is dimensioned in the datasheet. The maker's board being built is evidence for his pad sizes, not for his body outline. This board aligns the pads' back edges with the maker's.

## Files

- `hardware/mysterio.kicad_pro`: KiCad 10 project (schematic + board). ERC: 0. DRC: 0 errors, 0 unconnected, schematic matches the board; 5 warnings, all "copper sliver" in the art (thin points in the maker's swirl and robe copper).
- `hardware/circuit.json`: the circuit as data; `tools/gen_schematic.py mysterio` and `hardware/build_board.py` both read it.
- `hardware/build_board.py`: rebuilds the whole board from the maker's file in `original/` in one run; the scale is the constant `SCALE` at the top, and every placement and routing choice is commented there.
- `hardware/mysterio.kicad_dru`: the art rule only (rev A's crowded-part exceptions are gone).
- `production/`: everything a board house needs, for one board and a 2×2 panel. Start with [production/README.md](production/README.md).
- `original/`: the maker's untouched KiCad 8 project, art and sketches.

## Parts cost (parts only, LCSC list prices checked 2026-11-10)

| Part | Qty | Each @ ~100 boards |
|---|---|---|
| Connector XFCN BH254VS-6P (LCSC C492445) | 1 | $0.12 |
| Switch C&K PCM13SMTR (Digikey) | 1 | ~$0.90 |
| LiPo connector JST S2B-PH-SM4-TB (LCSC C295747) | 1 | $0.16–0.18 |
| RGB LED OPSCO SK6805-EC3210R (LCSC C5378735) | 4 | $0.068 |
| Capacitor 100 nF 0603 (LCSC C14663) | 1 | <$0.01 |
| Resistor 330 Ω 0603 (LCSC C23138) | 4 | <$0.01 |
| **Total without the module** | | **about $1.50** |
| Seeed Studio XIAO ESP32-C3 / S3 / C6 | 1 | not priced here: check Seeed |

The bare board is not included. It is bigger than rev A (50.4 × 52.9 mm instead of 40.7 × 46.2 mm), which may move it into a dearer size bracket at some board houses.
