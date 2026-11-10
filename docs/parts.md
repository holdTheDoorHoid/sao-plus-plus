# SAO++ approved parts

Every board draws from this list first. Shared parts mean one reel feeds every board, which is where mass-production savings come from. Each part has an id (`SAOPP-…`) that `board.yml` refers to.

**Prices** are LCSC list prices checked live on 2026-11-10 (USD per piece) unless marked otherwise. They move; re-check before ordering. **Status** says how far each choice has been proven:

- `chosen`: picked, live price/stock confirmed, not yet on a built board
- `verify`: picked, but something specific must be confirmed by the first board (listed in the row)
- `open`: no decision yet

## Connector

| Id | Part | Where | Price | Status |
|---|---|---|---|---|
| `SAOPP-CONN-01` | XFCN **BH254VS-6P**: 2×3 2.54 mm shrouded, keyed SMD box header, vertical. PA6T body (survives reflow), gold-plated contacts, 3 A. Body 15.3 × 8.9 mm, 9.05 mm tall. Drawing checked 2026-11-10: six 1.1 × 4.0 mm pads, **no hold-down legs or pegs** | LCSC [C492445](https://www.lcsc.com/product-detail/C492445.html), 3,370 in stock, tray of 340 | $0.100 @340, $0.091 @2,380 | `verify`: test-fit a real part against a badge socket (footprint is drawn; pads lengthened to 4.4 mm for strength) |
| `SAOPP-CONN-02` (alternate) | Any 2×3 2.54 mm SMD shrouded box header with the **same land pattern** as CONN-01 | to be found | — | `open`: the first board should find one drop-in second source (Digikey/Mouser) |

Notes: the photo on LCSC shows a proper shroud with a key slot and gull-wing SMD legs. No metal hold-down tabs are visible, so the [layout rules in standard.md](standard.md#2-connector) about pad size and copper pour matter.

## Power switch

| Id | Part | Where | Price | Status |
|---|---|---|---|---|
| `SAOPP-SW-01` | C&K **PCM13SMTR**: 3-position slide (SP3T), knob sticks out of the board edge, 300 mA, metal shell with four solder tabs and two locating pegs. Pin 3 is the common; pins 1 / 2 / 4 are the three positions, so OFF (pin 2, left unconnected) sits between the two supplies | Digikey 401-2017-1-ND (stock unconfirmed; 14-week lead time quoted). LCSC [C221842](https://www.lcsc.com/product-detail/C221842.html): **out of stock**, $2.13 @30 reference | ~£0.70 @100, ~£0.58 @1000 (Digikey UK) | `verify`: on a prototype, which way the knob sits for position 1 (sets the SAO / BAT label order) |
| `SAOPP-SW-02` (candidate) | A cheaper clone with the PCM13 land pattern | to be found | — | `open`: the switch is the most expensive part on a simple board |
| not suitable | XKB **SS-3235D-03-L3** (LCSC C2884764) | — | — | Rejected 2026-11-10: the drawing shows a 2-position switch with the knob on top, not what its listing category suggested |
| not preferred | XKB **SS-3336S-02-L3** (LCSC C500060), $0.09 | — | — | Is 3-position, but the knob is on top (faces the badge when plugged in) and it is 13 mm long. Usable only where the knob can be reached |

The PCM13's two locating pegs need 0.9 mm holes through the board. They are the only holes an SAO++ board puts through the art side; place the switch where two pinholes do not hurt the art.

## Coin cell

| Id | Part | Where | Price | Status |
|---|---|---|---|---|
| `SAOPP-BAT-01` | TE / Linx **BAT-HLD-001**: SMD CR2032 retainer clip (also takes CR2025). The clip is the + contact; the − contact is a bare 17 mm copper disc on the board under the cell, so use ENIG finish. The clip fits its pads both ways round, so the assembler must be told which side is open | LCSC [C7501066](https://www.lcsc.com/product-detail/C7501066.html) (1,540 in stock), Digikey and Mouser (~13k) | LCSC $0.61 @100, $0.53 @1000; Digikey cheaper | `chosen` |
| `SAOPP-BAT-02` (alternate) | Keystone **3034**: SMD 20 mm holder, cell slides in from the side | Digikey 36-3034-ND only (not at LCSC) | ~$0.24 @1000 (Digikey) | `chosen`, different footprint |
| `SAOPP-BAT-03` (candidate) | LCSC clones (Q&J CR2032-BS-6-1 C70377, MYOUNG BS-08-B2BA013 C6937132) | LCSC | — | `open`: overlay on BAT-01's footprint; a match gives us a cheap drop-in second source |

**Cell:** CR2032. At 2 mA (two LEDs at 1 mA) expect about 70–100 hours, so 6–8 days of 12-hour wear. Blinking at 25 % roughly quadruples that.

## Side-firing LEDs: Lite-On LTST-S270 family

One footprint (1.6 × 1.2 mm "0603 side-view", about 1.15 mm tall) for every colour. Many pin-compatible clones exist.

| Id | Colour | Part | LCSC | Price | Coin cell? | Status |
|---|---|---|---|---|---|---|
| `SAOPP-LED-01` | Red | LTST-S270KRKT | [C125114](https://www.lcsc.com/product-detail/C125114.html), 21,100 in stock | $0.026 @200, $0.018 @4,000 | Great: brightest | `chosen` |
| `SAOPP-LED-02` | Yellow | LTST-S270KSKT | [C133119](https://www.lcsc.com/product-detail/C133119.html), 9,680 in stock | $0.028 @200, $0.020 @4,000 | Good | `chosen` |
| `SAOPP-LED-03` | Yellow-green | LTST-S270GKT | [C913078](https://www.lcsc.com/product-detail/C913078.html) 1,810 in stock; Digikey 160-1475-1-ND (~106k) | $0.058 @500 (LCSC); cheaper at Digikey | Good, but dimmest at 1 mA | `chosen` |
| `SAOPP-LED-04` | Blue | LTST-S270TBKT | [C125115](https://www.lcsc.com/product-detail/C125115.html), 16,260 in stock | $0.029 @200, $0.020 @4,000 | **Poor**: badge power only | `chosen` |
| `SAOPP-LED-05` | Orange | LTST-S270KFKT | Digikey / RS | — | Good | `verify`: LCSC listing |
| `SAOPP-LED-06` | White | none in this family | — | — | **Poor** | `open`: Everlight EAST16084WB0 is a candidate if its footprint matches |

## Through-board LED

For boards whose art is lit from behind through bare board (no copper on either side at that spot) rather than from the edge.

| Id | Colour | Part | LCSC | Price | Status |
|---|---|---|---|---|---|
| `SAOPP-LED-10` | Red | Lite-On **LTST-C230KRKT**, 1206 reverse-mount (lens faces the board) | [C125107](https://www.lcsc.com/product-detail/C125107.html), 54,960 in stock | $0.037 @100, $0.027 @6,000 | `verify`: brightness through 1.6 mm board at 1 mA |

| `SAOPP-LED-11` | White | Lite-On **LTW-C230DS**, 1206 reverse-mount, same package and footprint as LED-10 | [C575513](https://www.lcsc.com/product-detail/C575513.html), 56,700 in stock | $0.055 @100, $0.037 @6,000 | `verify`: land pattern against its own datasheet (taken as the LTST-C230 family pattern); brightness on a coin cell |

The footprint has no hole: the LED shines into the board itself, which keeps the art side unbroken. Other colours in the LTST-C230 family share the footprint.

**White on a coin cell.** White needs about 2.6-2.7 V before it lights, which is most of what a CR2032 gives, so it is the weakest colour on battery. With the standard 1.3 kΩ resistor (R-01) a white LED draws roughly 0.45 mA on badge power and roughly 0.2 mA on a fresh cell, and fades as the cell drops. White LEDs give far more light per milliamp than red, so this is expected to be enough to light art from behind, but it is **calculated, not measured**: Mad Cat's first prototype decides. Using R-01 keeps white boards on the same resistor reel as everything else; R-02 (330 Ω) is the fallback if they are too dim.

**Addressable RGB (SK6812 "side" 4020 and similar): not approved.** They are rated for 3.7 V minimum, above both the 3.3 V SAO rail and a coin cell, and each one draws about 0.4–0.6 mA even when dark, which would flatten a CR2032 in a couple of weeks while "off". Use separate single-colour LEDs instead.

## Passives and protection

| Id | Part | Use | Status |
|---|---|---|---|
| `SAOPP-R-01` | 1.3 kΩ 0603 1 %: UNI-ROYAL 0603WAF1301T5E, LCSC [C22767](https://www.lcsc.com/product-detail/C22767.html) (307,000 in stock, $0.002); any maker's equivalent is fine | LED resistor for red / yellow / green / orange: ~1.0 mA from a 3.0 V cell, ~1.2 mA from 3.3 V. One value for both supplies. Also used for through-board white (LED-11): ~0.45 mA on 3.3 V, ~0.2 mA on a cell | `verify`: bench-measure brightness at 1 mA |
| `SAOPP-R-02` | 330 Ω 0603 | Blue/white LED on badge power only; also the spec's minimum series resistor on driven GPIO pins | `chosen` |
| `SAOPP-D-01` | Low-leakage Schottky (RB751S40 class, SOD-523) | Series diode after the coin cell holder, **required** on boards with a microcontroller or anything wired to SDA/SCL/GPIO ([why](standard.md#3-power-sao--off--battery)) | `open`: pick part, confirm reverse leakage < 1 µA at 0.3 V |
| `SAOPP-EE-01` | 24C02-class I2C EEPROM, SOT-23-5, address 0x50 | Optional ID chip footprint, unpopulated by default | `open` |
