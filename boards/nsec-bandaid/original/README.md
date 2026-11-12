# Original files

NorthSec's `Sao_Bandaid` (KiCad 8), from https://github.com/nsec/nsec-badge at commit `0ea779f281ac538fa21b333b027250784b5d3cbf` (2025-07-14), folder `hw/2025/sao/Sao_Bandaid/`, plus the shared `hw/2025/sao/libs/` folder its footprints come from. Licence: MIT, see `LICENSE` (the upstream repository's root licence file, unchanged). No file of this board states a different licence.

**This is not a complete copy, on purpose.** The maker's plaster (outline, gauze pad, air-hole dots) was traced from a picture, and neither the picture nor the tracing is kept here. What is kept is the circuit: the schematic, the board file's parts, pads, tracks, vias and back silkscreen, the footprints, the BOM and placement lists, and the licence.

Cut out, and why:

- **The picture embedded in `Sao_Bandaid.kicad_pcb` is removed** (one `(image ...)` block on the non-printing layer User.1, 1.95 MB). It is a 5105 × 1831 pixel PNG: a flat-colour illustration of a sticking plaster, with a peach strip outlined in navy blue, a cream gauze pad with rounded corners and thirteen small oval air holes each side. No watermark, signature or author in its metadata. It is the kind of picture sold or given away as clip-art; nothing in the repository says where it came from or that NorthSec drew it, so its licence is unknown. It was scaled so that the plaster was about 46 mm long, the size of the board. (Upstream has no separate copy of the picture; the embedded one was the only one.)
- **The traced geometry is removed from `Sao_Bandaid.kicad_pcb`:**
  - the board outline (2 lines and 2 arcs on Edge.Cuts: a 47.5 × 14 mm strip with half-round ends);
  - the gauze pad and strip drawn on the front (4 lines and 4 arcs on F.Cu, 6 lines and 6 arcs on F.Mask, one polygon on F.SilkS, one on F.Mask, and the unconnected copper fill of the strip: one zone on F.Cu);
  - **the 26 `Pin 1 smd` pads on the front.** These are single round 1.35 mm copper pads connected to nothing: the plaster's air holes. Each sits on one of the picture's 26 dots (three checked by calculation: all within 0.3 mm);
  - 2 groups that only listed the removed items.

  As a result this board file has no outline and will not pass KiCad's own checks; it is here as a record of the circuit, not to be manufactured.
- **`jlcpcb/gerber/` and `jlcpcb/production_files/GERBER-Sao_Bandaid.zip` are not copied**, because Gerbers contain the same outline, pad and dots. The BOM and placement CSVs are kept.
- **Stray files of another board are not copied:** upstream's `Sao_Bandaid/jlcpcb/production_files/` also holds `BOM-Sao_Bomb.csv`, `CPL-Sao_Bomb.csv` and `GERBER-Sao_Bomb.zip`, which belong to the Bomb add-on.
- `fp-info-cache`, `Sao_Bandaid.kicad_prl`, `jlcpcb/project.db` (KiCad and plug-in caches) and `sym-lib-table` (as on the sister boards) are not copied.
- In upstream, `Sao_Bandaid/libs` is a link to `../libs`; here `libs/` sits beside `Sao_Bandaid/`.

Still in the board file: D1 (the LED, on the front), R1 (330 Ω), R2 and R3 (1 k, from SCL and SDA to +3V3), J1 (the SAO connector), every track, the four vias, the front "+" and "-" marks, the back's "nsec 2025" logo and the 5 × 5 mm white box.

The SAO++ board in `../hardware/` takes from these files only the circuit, the "nsec 2025" logo footprint and the 5 × 5 mm white box. Its outline and front art are SAO++'s own drawing (`../art/bandage.svg`).
