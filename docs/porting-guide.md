# Porting an old SAO to SAO++

The order matters: permission first, then electrical, then art.

## 1. Permission (before any work is published)

Fill in `original:` in `board.yml` first.

| Original license | What we can do |
|---|---|
| CERN-OHL-S/W/P, CC-BY, CC-BY-SA, MIT, BSD, Apache, GPL | Port, publish, and sell, with credit. Keep the original notice in the board README. CC-BY-SA / GPL / CERN-OHL-S originals stay share-alike, which matches this repo. |
| CC-BY-NC or CC-BY-NC-SA | **Do not port for sale** without written permission. Non-commercial terms conflict with the mass-production goal. |
| CC-BY-ND | No derivatives at all without permission. |
| No license stated, "open source" in a tweet, files on a forum | **All rights reserved by default.** Ask the maker in writing; record the reply in `boards/<slug>/docs/permission.md` and set `permission: written`. |
| Art from a third party (logos, characters, con branding) | Separate from the board license. Needs its own permission, or replace the art. |

Credit the original maker in the board README and on the back silkscreen where space allows ("orig. design: <name>").

## 2. Electrical port

1. Start from `lib/template/` (KiCad 10). It already has the SAO++ connector, the power-select block, and the board-edge keep-outs on the right sides.
2. Replace any 4-pin v1 header with the 6-pin v1.69bis connector (`SAOPP-CONN-01`, back side).
3. Run power through the shared power block (`lib/blocks/power-select`), never straight from the header.
4. Move every component to the **back**. The front is art only: copper, mask, silkscreen, and nothing that needs a drill hit you can see, except deliberate vias in the art.
5. Swap one-off parts for the approved list in [parts.md](parts.md). An off-list part is allowed when the board's character depends on it; note why in the README.
6. If the board has a microcontroller, read [standard.md](standard.md) for the I2C and GPIO conventions.

## 3. Art

Keep the original look unless the README says otherwise. Store source art in `art/` (SVG preferred) so the next person can re-render it.

## 4. Done means

- `python3 tools/check_boards.py` passes
- ERC and DRC clean in KiCad 10 (exceptions written in the README)
- BOM and placement files exported to `production/`
- `status:` set honestly: `prototype` once one has been built, `verified` once it has been tested in a badge **and** on coin cell
