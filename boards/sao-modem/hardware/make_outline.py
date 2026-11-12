#!/usr/bin/env python3
"""Write a board file that holds only the maker's outline, enlarged, so tools/extract_outline.py can turn it into
outline.json (one polygon).

The maker drew the outline as 42 curves (from images/outline.svg in his repo; a copy is in original/modem/). They are
scaled here as curves, before KiCad turns them into short straight pieces, so the rounded corners stay smooth at the
larger size. Run from the repo root:

  python3 boards/sao-modem/hardware/make_outline.py
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/extract_outline.py \
      boards/sao-modem/hardware/.tmp/outline_scaled.kicad_pcb boards/sao-modem/hardware/outline.json
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
K = 2.0                       # enlargement (see README: the smallest whole design that takes the cell clip)
X0, Y0 = 129.88, 49.26        # top-left corner of the maker's outline in his file; becomes (0, 0)

txt = (HERE.parent / "original" / "modem" / "modem.kicad_pcb").read_text()
curves = re.findall(r'\(gr_curve \(pts ((?:\(xy [-0-9.]+ [-0-9.]+\) ?){4})\) \(layer "Edge.Cuts"\)', txt)
assert len(curves) == 42, len(curves)
out = '(kicad_pcb (version 20211014) (generator pcbnew)\n  (general (thickness 1.6))\n  (paper "A4")\n' \
      '  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))\n'
for c in curves:
    pts = [((float(x) - X0) * K, (float(y) - Y0) * K) for x, y in re.findall(r"\(xy ([-0-9.]+) ([-0-9.]+)\)", c)]
    out += "  (gr_curve (pts " + " ".join(f"(xy {x:.6f} {y:.6f})" for x, y in pts) + ') (layer "Edge.Cuts") (width 0.1))\n'
out += ")\n"
tmp = HERE / ".tmp"
tmp.mkdir(exist_ok=True)
(tmp / "outline_scaled.kicad_pcb").write_text(out)
print("wrote", tmp / "outline_scaled.kicad_pcb", "with", len(curves), "curves, scale", K)
