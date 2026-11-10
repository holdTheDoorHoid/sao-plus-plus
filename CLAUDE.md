# SAO++: notes for agents

Read `README.md`, `docs/standard.md`, `docs/parts.md`, and `docs/porting-guide.md` before touching a board.

- **Owner:** not an engineer by training. Report decisions and what they will see or measure, in plain language. File paths and part numbers belong in footnotes.
- **Permission first.** Never commit a third-party design (files, art, or derived layout) until its `board.yml` `original:` block shows an open license or recorded written permission. Non-commercial licenses (CC-BY-NC) are **not** OK for this project without written permission.
- **Parts:** use `docs/parts.md` ids. Anything marked `verify` must be verified (and the row updated) by the first board that uses it. Do not invent part numbers or prices; quote the live distributor page and date it. LCSC pages render in a browser but block curl.
- **Shared library is the product.** A footprint or block used by two boards lives in `lib/`, never copied into a board folder.
- **Coin-cell safety is non-negotiable:** no circuit may let the SAO 3.3 V rail, I2C pull-ups, or GPIO push current into the CR2032. Read standard.md section 3.
- **KiCad 10** is installed as the flatpak `org.kicad.KiCad` (`flatpak run --command=kicad-cli org.kicad.KiCad ...`).
- **Git:** public repo `holdTheDoorHoid/sao-plus-plus`. Work on a branch per board (`board/<slug>`), open a PR on this repo, and let the owner merge. Run `python3 tools/check_boards.py` before every commit.
- Do not order boards or parts. Produce the files and a cost estimate; the owner orders.
