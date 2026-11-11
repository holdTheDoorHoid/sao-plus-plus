#!/usr/bin/env python3
"""Turn a board's Edge.Cuts drawing (often thousands of short lines from an SVG import) into one clean polygon per loop.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/extract_outline.py <board.kicad_pcb> <outline.json>

Writes {"outer": [[x, y], ...], "holes": [[[x, y], ...], ...]} in mm, KiCad front view. Build scripts read it
(see boards/mad-cat/hardware/build_board.py). Prints the size and how many loops it found; a board whose outline
is not closed fails here rather than later at the fab.
"""
import json
import sys

import pcbnew
from pcbnew import ToMM


def main(src, dst):
    board = pcbnew.LoadBoard(src)
    ps = pcbnew.SHAPE_POLY_SET()
    ok = board.GetBoardPolygonOutlines(ps, False)
    assert ok and ps.OutlineCount() >= 1, "the Edge.Cuts drawing does not form a closed outline"
    ps.Simplify()
    best = max(range(ps.OutlineCount()), key=lambda i: abs(ps.Outline(i).Area()))

    def pts(chain):
        return [[round(ToMM(chain.CPoint(k).x), 4), round(ToMM(chain.CPoint(k).y), 4)] for k in range(chain.PointCount())]

    out = {"outer": pts(ps.Outline(best)), "holes": [pts(ps.Hole(best, h)) for h in range(ps.HoleCount(best))]}
    b = ps.BBox()
    print(f"{src}: {ToMM(b.GetWidth()):.2f} x {ToMM(b.GetHeight()):.2f} mm, x {ToMM(b.GetLeft()):.2f}..{ToMM(b.GetRight()):.2f}, "
          f"y {ToMM(b.GetTop()):.2f}..{ToMM(b.GetBottom()):.2f}; outlines {ps.OutlineCount()}, outer points {len(out['outer'])}, holes {len(out['holes'])}")
    json.dump(out, open(dst, "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
