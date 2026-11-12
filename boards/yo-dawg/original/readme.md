# The maker's files

From https://github.com/davedarko/YoDawgSAO, commit `4dd3db0f05816ee4440da673cd56837ef299c66e` (2024-10-11), MIT licence (`LICENSE`, copyright 2024 davedarko).

| File | What it is | Changed? |
|---|---|---|
| `LICENSE` | the repository's licence | no |
| `README.md` | the repository's front page | no (its picture is a link to his repository, not a copy) |
| `dawg/dawg.kicad_sch`, `dawg/dawg.kicad_pro` | the mother board's schematic and project (KiCad 8) | no |
| `dawg/dawg.kicad_pcb` | the mother board | **yes: the front portrait is removed** (1318 filled front-silkscreen polygons and the group that held them). Nothing else is touched |
| `StandardSAOAO/SAOAO.pretty/squareSAOAO.kicad_mod` | his footprint for a 19 x 19 mm mini board's 3-pin header | no |

Why the portrait is removed: it is a likeness of a real person (the rapper Xzibit, the "Yo Dawg" meme) made from a photograph that is not the maker's, so his licence cannot cover it. See `../board.yml` (`art_note`) and `../README.md`.

Not copied: `reference/` (the portrait as an SVG with the picture inside it, and a render showing it), `dawg/production/` (his Gerbers, which include the portrait), `badges/` (his four mini boards, three of which carry other people's logos or characters) and the three other footprints in `StandardSAOAO/`.
