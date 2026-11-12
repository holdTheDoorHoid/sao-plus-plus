# NorthSec's original files for the "Bomb" SAO: circuit only

From https://github.com/nsec/nsec-badge/tree/nsec25/hw/2025/sao/Sao_Bomb at commit 0ea779f (2025-07-14), plus the shared
`hw/2025/sao/libs/` folder the project points at. Licence: MIT (`LICENSE`, the repository's root licence file, which
says "except otherwise stated in respective files"; no file of this board states anything else).

**These are not the untouched upstream files.** NorthSec drew this board's outline and front art over a picture of a
cartoon time bomb (four red dynamite sticks, two dark straps, a clock, curly wires) that has no watermark, credit or
source and looks like stock clip-art. Nobody here can say who owns that picture, so neither it nor anything traced
from it is kept in this repository. What is kept is the circuit, which is NorthSec's own work.

## Kept

- `Sao_Bomb/Sao_Bomb.kicad_sch`, `.kicad_pro`, library tables — the schematic and project, unchanged.
- `Sao_Bomb/Sao_Bomb.kicad_pcb` — the board file with its 18 footprints (parts, wire holes, logo), tracks, vias and
  the 5 x 5 mm white square on the back, **minus the items listed below**.
- `Sao_Bomb/jlcpcb/production_files/BOM-Sao_Bomb.csv`, `CPL-Sao_Bomb.csv`, `jlcpcb/project.db` — the maker's parts
  list and placement list.
- `libs/` — the footprints and the connector symbol the project uses, unchanged (`Sao_Bomb/libs` links to it, as upstream).

## Cut, and why

| What | Why |
|---|---|
| `Sao_Bomb/Untitled.png` (not copied) | The picture itself (436 x 354 pixels). Origin and licence unknown. |
| In `Sao_Bomb.kicad_pcb`: the `(image ...)` block on layer `User.9` | The same picture, byte for byte, embedded in the board file as a tracing aid. |
| In `Sao_Bomb.kicad_pcb`: the board outline (1 polygon on `Edge.Cuts`) | Traced from the picture. |
| In `Sao_Bomb.kicad_pcb`: the front silkscreen drawing (2 strap polygons, 6 stick lines, 2 clock circles on `F.SilkS`) | Traced from the picture. |
| In `Sao_Bomb.kicad_pcb`: the clock (2 copper hands and the hub on `F.Cu`, the round window on `F.Mask`) | Traced from the picture. |
| `Sao_Bomb/jlcpcb/gerber/` (13 files) and `jlcpcb/production_files/GERBER-Sao_Bomb.zip` (not copied) | The maker's manufacturing files, which contain the outline and art above. |
| `fp-info-cache`, `Sao_Bomb.kicad_prl` (not copied) | KiCad cache and per-user window state, not design data. |

That is 15 drawing items and the picture removed from the board file; nothing else in it is changed. Without its
outline the file no longer opens as a complete board: it is here as the record of the circuit and of where the maker
put the parts. The SAO++ board does not read anything from this folder; its outline and art are drawn from scratch by
`hardware/build_board.py`. Upstream has the unmodified files.
