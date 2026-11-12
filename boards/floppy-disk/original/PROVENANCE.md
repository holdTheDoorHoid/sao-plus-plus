# Where these files came from

Everything in this folder is Uri Shaked's work, copied unchanged from
https://github.com/urish/floppy-disk-sao at commit `2f58b513ef4f505b3f192de60a3604e9ec1169e4`
(commit date 2022-04-09; fetched 2026-11-11).

**Licence.** The repository has no LICENSE file. Its `README.md` (kept here as `README.md`) ends with:

> ## License
>
> Copyright (C) 2020, Uri Shaked. Released under the MIT License.

No file in the repository carries a licence note of its own.

**Left out on purpose** (not Uri Shaked's own work, and not needed to read the design):

- `lib/badgelife_shitty_addon_v169bis.lib` / `.dcm` and `floppy.pretty/Badgelife-SAOv169-SAO-2x3.kicad_mod`:
  a third party's SAO connector symbol and footprint
- `floppy-sao-cache.lib`, `floppy-sao-smd-cache.lib`: KiCad's cached copies of that symbol and of KiCad's stock symbols
- `.gitignore`

Without them KiCad 5 shows the connector symbol as missing when the schematics are opened; `media/schematic.png`
shows the complete schematic.

The SAO++ version was built from `floppy-sao-smd.kicad_pcb` (the SMD flavor) by `../hardware/build_board.py`.
