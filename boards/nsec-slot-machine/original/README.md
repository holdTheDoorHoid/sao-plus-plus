# Original files (circuit only)

`Sao_SlotMachine_v2/` is what is kept of NorthSec's KiCad 8 project, from
https://github.com/nsec/nsec-badge/tree/0ea779f281ac538fa21b333b027250784b5d3cbf/hw/2025/sao/Sao_SlotMachine_v2
(branch `nsec25`, commit 0ea779f, 2025-07-14). `LICENSE` is that repository's root licence file (MIT, "except
otherwise stated in respective files"; no file of this board states an exception).

**Why things were cut.** The maker drew the board's outline and front art over a screenshot of a slot-machine icon
of unknown origin (a stock-icon style picture). That picture is not the maker's to license, and an outline traced
from it may not be either. The SAO++ board uses its own drawing instead, so the traced material is not published
here. Upstream still has everything.

## Kept, unchanged

- `Sao_SlotMachine_v2.kicad_sch` (the schematic), `Sao_SlotMachine_v2.kicad_pro`, `fp-lib-table`, `sym-lib-table`
- `libs/` (upstream this is a link to the shared `hw/2025/sao/libs/` folder; here it is a real copy): the maker's
  footprints, including the `nsec-2025` logo, and the connector symbol
- `jlcpcb/production_files/BOM-…csv` and `CPL-…csv` (the maker's parts list and placement list)

## Kept, with parts cut out: `Sao_SlotMachine_v2.kicad_pcb`

Still in the file: all eight footprints where the maker placed them (three LEDs, three resistors, the header, the
logo), all 27 track segments, the two vias that carry a net, the net list, the board setup, and the white square on
the back silkscreen. Cut from the file, and nothing else:

| Cut | How many | Why |
|---|---|---|
| The embedded picture on layer `User.1` (`(image …)`) | 1 | the third-party icon screenshot itself |
| Board outline and slots (`Edge.Cuts` shapes) | 6 | traced over the icon (outline, three 7-shaped slots, two coin slots) |
| Front copper areas (`F.Cu` zones, no net) | 4 | front art laid out on the traced outline |
| Front solder-mask openings (`F.Mask` shapes) | 9 | front art |
| Front silkscreen (`F.SilkS` shapes and texts) | 10 | front art: outline tracing, lever, reel panel, "$ Jackpot $", two rows of card suits |
| Vias with no net | 8 | decorative "bulbs", part of the front art |

Without an outline the file no longer describes a manufacturable board; it is kept as the record of the circuit.

## Left out entirely

- `image.png` (the icon screenshot as a loose file) and `DiamondArt.jpg` (a picture belonging to another board)
- `jlcpcb/gerber/`, `jlcpcb/production_files/GERBER-Sao_SlotMachine_v2.zip`, `jlcpcb/project.db` (the maker's
  manufacturing output: it contains the traced outline and front art)
- `fp-info-cache`, `.kicad_prl` (KiCad caches)
- The older `Sao_SlotMachine/` (v1) was not ported and is not copied here.
