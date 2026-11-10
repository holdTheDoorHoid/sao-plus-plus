# Shared library

Everything a board needs that is not specific to its art. Boards reference these by **project-relative path** (`${KIPRJMOD}/../../../lib/...`) so a fresh clone works with no setup.

| Path | Contents | Status |
|---|---|---|
| `sao-plus-plus.kicad_sym` | Symbols carrying the `SAOPP-…` id, MPN, LCSC and Digikey fields, so BOM exports are ready to order | to build |
| `sao-plus-plus.pretty/` | Footprints for CONN-01, SW-01/02, BAT-01/02, LED (LTST-S270 side-view), all drawn for the **back** side | to build |
| `3dmodels/` | STEP models for the above, for 3D checks and the archive's model viewer | to build |
| `blocks/power-select.kicad_sch` | Hierarchical sheet: connector → 3-position switch → load, coin cell holder, optional series diode, optional ID EEPROM | to build |
| `template/` | Starter KiCad 10 project: block placed, connector and switch at their house positions, design rules (2-layer, 1.6 mm, ENIG), back-silk labels | to build |

Rules:
- Footprints come from the manufacturer's drawing, never from a guess. Write the drawing's URL in the footprint description.
- Change a shared footprint only by adding a new revision (`_v2`); boards already built must not silently move.
