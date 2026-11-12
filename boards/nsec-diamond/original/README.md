# Original files

NorthSec's `Sao_Diamond` (KiCad 8), from https://github.com/nsec/nsec-badge at commit `0ea779f281ac538fa21b333b027250784b5d3cbf` (2025-07-14), folder `hw/2025/sao/Sao_Diamond/`, plus the shared `hw/2025/sao/libs/` folder its footprints come from. Licence: MIT, see `LICENSE` (the upstream repository's root licence file, unchanged).

**This is not a complete copy, on purpose.** The maker's diamond (outline and facets) was traced from a third-party picture, and neither the picture nor the tracing is kept here. What is kept is the circuit: schematic, the board file's parts, pads, tracks and back silkscreen, the footprints, the BOM and placement lists, and the licence.

Cut out, and why:

- **`DiamondArt.jpg` is not copied**, and the copy of it embedded in `Sao_Diamond.kicad_pcb` (an `(image ...)` block on the non-printing layer User.9) is removed. It is a 180 × 168 pixel web thumbnail of a gold gem logo template lettered "DIAMOND LOGO / COMPANY TAGLINE HERE": not NorthSec's own drawing, source and licence unknown, no watermark visible. The embedded copy was the same file byte for byte, scaled so that its gem was about 40 mm wide.
- **The traced geometry is removed from `Sao_Diamond.kicad_pcb`:** the board outline (one 5-point polygon on Edge.Cuts), the ten facet triangles (polygons on F.SilkS) and the five construction lines on User.1 that the facets were drawn from. They followed the picture's gem line for line. As a result this board file has no outline and will not pass KiCad's own checks; it is here as a record of the circuit, not to be manufactured.
- **`jlcpcb/gerber/` and `jlcpcb/production_files/GERBER-Sao_Diamond.zip` are not copied**, because Gerbers contain the same outline and facets. The BOM and placement CSVs are kept.
- `fp-info-cache`, `Sao_Diamond.kicad_prl`, `jlcpcb/project.db` (KiCad and plug-in caches) and `sym-lib-table` (points at a path on the maker's own computer) are not copied.
- In upstream, `Sao_Diamond/libs` is a link to `../libs`; here `libs/` sits beside `Sao_Diamond/`.

The SAO++ board in `../hardware/` takes from these files only the circuit, the "nsec 2025" logo footprint and the 5 × 5 mm white box. Its outline and front art are SAO++'s own drawing (`../art/gem.svg`).
