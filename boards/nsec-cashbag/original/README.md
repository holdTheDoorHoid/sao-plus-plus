# Original files: NorthSec 2025 `Sao_CashBag` (circuit only)

From https://github.com/nsec/nsec-badge, branch `nsec25`, commit `0ea779f281ac538fa21b333b027250784b5d3cbf` (2025-07-14):
`hw/2025/sao/Sao_CashBag/` and the shared `hw/2025/sao/libs/` (a symlink upstream, a real folder here).
Licence: MIT, `LICENSE` in this folder (the repository's root licence; no file of this board states an exception).

**Why this folder is incomplete on purpose.** The maker's outline and front picture were traced from a stock
illustration: a watermarked stock-library preview sat in the folder as `Untitled.png`, and the same picture was
embedded in the board file as a tracing layer. That drawing was not NorthSec's to license. SAO++ uses its own drawing
instead (`../art/cash-bag.svg`), and nothing traced from the stock picture is kept here. What is kept is the maker's
circuit and the two things on the back that are NorthSec's own.

## Kept, unchanged

- `Sao_CashBag/Sao_CashBag.kicad_sch`, `.kicad_pro`, `fp-lib-table`, `sym-lib-table`: the schematic and project.
- `Sao_CashBag/jlcpcb/production_files/BOM-Sao_CashBag.csv` and `CPL-Sao_CashBag.csv`: the maker's parts list and placements.
- `libs/`: the maker's footprints and symbol (LED, resistor, SAO connector, pin, and the `nsec-2025` logo).
- `LICENSE`.

## Kept, with the traced art cut out: `Sao_CashBag/Sao_CashBag.kicad_pcb`

Still in the file: all eight footprints (three LEDs, three resistors, the connector, the `nsec 2025` logo) at the
maker's positions, every track and via, the nets, the board settings, and the white write-on square on the back
silkscreen. Cut from it, by whole top-level blocks and nothing else:

| Cut | How many | Layer | Why |
|---|---|---|---|
| Embedded picture `(image ...)` | 1 | User.9 | the stock illustration itself |
| Outline polygon | 1 | Edge.Cuts | traced from the picture |
| Lines, arcs, circles, rectangles, polygons | 32 + 2 + 3 + 3 + 4 = 44 | F.SilkS | traced line art |
| Text "50" | 2 | F.SilkS | part of the traced bank notes |
| Circles, rectangles, polygons | 2 + 11 + 8 = 21 | F.Mask | traced gold and bare-board areas |
| Rectangles, polygon | 2 + 1 = 3 | F.Cu | traced gold bands and "$" |
| Copper pours (zones) | 2 | F.Cu | traced coin stack and coin ring |

The file no longer has a board outline, so KiCad will open it but cannot make a board from it.

## Not copied at all

- `Untitled.png`: the stock-library preview.
- `DiamondArt.jpg`: a stock "diamond logo" picture belonging to a different board, left in this folder upstream.
- `jlcpcb/gerber/` and `jlcpcb/production_files/GERBER-Sao_CashBag.zip`: the maker's manufacturing files, which contain
  the traced outline and art.
- `fp-info-cache`, `.kicad_prl`, `jlcpcb/project.db`: editor caches.
