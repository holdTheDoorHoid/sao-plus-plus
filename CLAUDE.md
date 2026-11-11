# SAO++: notes for agents

Read `README.md`, `docs/standard.md`, `docs/parts.md`, and `docs/porting-guide.md` before touching a board.

- **Owner:** not an engineer by training. Report decisions and what they will see or measure, in plain language. File paths and part numbers belong in footnotes.
- **Permission first.** (Fat Pika and Mad Cat were each published with permission pending by the owner's explicit decision on 2026-11-10, asked separately for each; that is recorded in each `board.yml` and is not a default. Ask the owner each time.) Never commit a third-party design (files, art, or derived layout) until its `board.yml` `original:` block shows an open license or recorded written permission. Non-commercial licenses (CC-BY-NC) are **not** OK for this project without written permission.
- **Controller standard (owner decision 2026-11-10):** any board that needs a chip uses a Seeed Studio XIAO ESP32 module (C3, S3 or C6, one shared footprint `SAOPP-MCU-01`), a JST-PH LiPo connector and the SAO / OFF / USB-BAT switch wiring in `docs/standard.md` section 3a. Keep the pin habits in `docs/parts.md` so firmware carries between boards. Firmware is Rust. Hack-Man is the worked example, including a single-layer route with no vias.
- **A recreation is not a port.** Hack-Man's maker published pictures only; its art was redrawn and its firmware is new. Do not copy a maker's images into the repo; link to them. Hack-Man was published with permission pending by the owner's decision on 2026-11-10, like the other two.
- **Fewest different parts across all boards** is an owner priority. Before adding a part, check whether one already on the list does the job (Mad Cat's white LEDs run on the same 1.3 k resistor as red ones for this reason), and say what a new part costs in reels when you propose one.
- **Parts:** use `docs/parts.md` ids. Anything marked `verify` must be verified (and the row updated) by the first board that uses it. Do not invent part numbers or prices; quote the live distributor page and date it. LCSC pages render in a browser but block curl.
- **Shared library is the product.** A footprint or block used by two boards lives in `lib/`, never copied into a board folder.
- **Coin-cell safety is non-negotiable:** no circuit may let the SAO 3.3 V rail, I2C pull-ups, or GPIO push current into the CR2032. Read standard.md section 3.
- **KiCad 10** is installed as the flatpak `org.kicad.KiCad` (`flatpak run --command=kicad-cli org.kicad.KiCad ...`).
- **Git:** public repo `holdTheDoorHoid/sao-plus-plus`. Work on a branch per board (`board/<slug>`), open a PR on this repo, and let the owner merge. Run `python3 tools/check_boards.py` before every commit.
- Do not order boards or parts. Produce the files and a cost estimate; the owner orders.

## KiCad 10 scripting quirks found on the first board (flatpak 10.0.6)

- `board.Remove(...)` and `footprint.Remove(...)` crash Python. Cut unwanted items out of the file text before `LoadBoard` instead (see `boards/fat-pika/hardware/build_board.py`).
- `footprint.Flip()` crashes unless the footprint was added to the board first.
- Shrinking (`Inflate` with a negative value) a polygon that has a hole opens a real slit between hole and edge. Shrink the outer path and grow the hole separately.
- Board-level copper polygons can carry a net (`PCB_SHAPE.SetNet`), which is how copper art doubles as GND and still passes DRC.
- LCSC datasheets open in the in-app browser's PDF viewer; `PDFViewerApplication.pdfDocument` gives the text. Do not fetch them with curl.
- Always look at a flat copper export (`kicad-cli pcb export svg --layers B.Cu,Edge.Cuts`), not only the 3D render, before trusting art copper.
- Rectangles in a footprint stop being rectangles when it sits at an angle that is not a multiple of 90 degrees (they become polygons). Measure anything that depends on them at 0 or 90 degrees first (see the battery clip in `boards/mad-cat/hardware/build_board.py`).
- Footprint fields are read with `fp.HasField(name)` / `fp.GetField(name)`; there is no `GetFieldByName`.
- **2018-era SVG art imports carry a 2 mm "page frame" polygon on every art layer, 10-15 mm outside the board outline.** It is invisible on a lone board and lands on the neighbouring boards in a panel. Cut it in the build script (`saopp_board.stray_frames`) and check every new board for art outside its outline before panelizing.
- New build scripts import `tools/saopp_board.py`; do not copy helpers into a board folder.
- Keep ground copper 0.55 mm back from the board edge: the panel's 0.5 mm mouse-bite holes sit on the edge and reach 0.25 mm in. Run DRC on the panel file too, and keep tracks out from under tab positions.
- `kicad-cli` in the flatpak can only write inside `--filesystem` paths (the repo); `/tmp` output silently goes nowhere.

## Lessons from the six-board batch (2026-11-10/11)

- Six boards were ported in parallel by one agent each, working only inside its own `boards/<slug>/` folder from a shared brief and Mad Cat as the worked example. That works; keep shared files (tools, lib, docs, root README) for the orchestrator.
- `tools/extract_outline.py` turns thousands of Edge.Cuts lines into one polygon per loop. Nibbler's original failed it because its SVG path overshoots its own start by 2 micrometres (see `boards/nibbler/hardware/fix_outline.py`).
- Outlines with 10,000+ points make KiCad's DRC run out of memory (La Bomba, Nibbler). Thin them (1-5 micrometre tolerance) in the build script.
- `tools/panelize.py` does not carry the board's `.kicad_dru` to the panel, and panel parts are renumbered (J101 ...). Boards with extra rules keep a hand-written `production/panel/<slug>-panel.kicad_dru`.
- The shared cell-clip footprint's courtyard is reported "malformed" at exact right angles in KiCad 10 (Lumpy uses 269.9 degrees), and its silk arrow often lands on lettering or off the board: several boards move it to the fab layer and add their own label.
- Small boards run out of room: the 24 x 17 mm clip, the 15 mm connector and a straight 12 mm of edge for the switch. Accepted compromises so far, each recorded in that board's README: moving a maker's credit block without changing it (Frida), a cell that overhangs the edge by 1 mm (RBG), the connector moved away from the old header spot (La Bomba, Nibbler, Big Green).
- LED colours on the 2018 boards are not recorded in the files. The batch used only white (LED-11) and red (LED-10) with the 1.3 k resistor: no new parts.
