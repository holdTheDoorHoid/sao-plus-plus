"""Helpers shared by the per-board build scripts (boards/<slug>/hardware/build_board.py).

Import from KiCad 10's Python only (needs pcbnew). Coordinates are millimetres in KiCad's front view.
Fat Pika's script predates this file and carries its own copies; new boards should import from here.
"""
import math
import re

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

ERR = FromMM(0.005)
ROUND = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def mm(v):
    return (round(ToMM(v.x), 3), round(ToMM(v.y), 3))


def add_circle(ps, c, r_mm, n=96):
    """Append a circle (an n-gon whose corners sit on the radius) to a SHAPE_POLY_SET. c is a VECTOR2I."""
    ps.NewOutline()
    for k in range(n):
        a = 2 * math.pi * k / n
        ps.Append(c.x + int(FromMM(r_mm) * math.cos(a)), c.y + int(FromMM(r_mm) * math.sin(a)))


def poly(pts):
    """SHAPE_POLY_SET with one outline from [(x, y), ...] in mm."""
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        ps.Append(FromMM(x), FromMM(y))
    return ps


def grown(ps, by_mm):
    """A copy of ps grown (or, with a negative value, shrunk) by by_mm. Do not shrink shapes that have holes."""
    out = pcbnew.SHAPE_POLY_SET(ps)
    out.Inflate(FromMM(by_mm), ROUND, ERR)
    return out


def area_mm2(ps):
    return ps.Area() / 1e12


def blocks(txt, opener, indent=2):
    """Yield (start, end) of each '(opener ...)' block at the given indent in a .kicad_pcb text, by matching parentheses.

    KiCad 10's Python crashes on Remove(), so build scripts cut unwanted items out of the file text before loading it."""
    for m in re.finditer(r"\n" + " " * indent + r"\(" + opener + r"[ \n]", txt):
        i = m.start() + 1 + indent
        depth = 0
        for j in range(i, len(txt)):
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    yield m.start(), j + 1
                    break


def cut_blocks(txt, spans):
    for a, b in sorted(spans, reverse=True):
        txt = txt[:a] + txt[b:]
    return txt


def stray_frames(txt, wider_than_mm):
    """Spans of footprint polygons wider than the board can be.

    2018-era SVG imports left a 2 mm frame around the page on every art layer, 10-15 mm outside the board outline.
    It is harmless on a lone board but lands on the neighbouring boards in a panel, so build scripts cut it out."""
    out = []
    for a, b in blocks(txt, "fp_poly", 4):
        xs = [float(m.group(1)) for m in re.finditer(r"\(xy ([-0-9.]+) [-0-9.]+\)", txt[a:b])]
        if xs and max(xs) - min(xs) > wider_than_mm:
            out.append((a, b))
    return out


def footprint_polys(board, layer):
    """Every polygon drawn inside footprints on one layer (how 2018-era SVG art was imported), as a list of SHAPE_POLY_SETs."""
    out = []
    for fp in board.GetFootprints():
        for it in fp.GraphicalItems():
            if hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY and it.GetLayer() == layer:
                out.append(pcbnew.SHAPE_POLY_SET(it.GetPolyShape()))
    return out


def bbox_mm(ps):
    b = ps.BBox()
    return (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))


def add_filled(board, ps, layer, net=None):
    """Add every outline of ps to the board as a filled polygon (holes are fractured in). Returns how many were added."""
    ps = pcbnew.SHAPE_POLY_SET(ps)
    ps.Fracture()
    for j in range(ps.OutlineCount()):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
        s.SetPolyShape(pcbnew.SHAPE_POLY_SET(ps.Polygon(j)))
        s.SetLayer(layer)
        s.SetFilled(True)
        s.SetWidth(0)
        if net is not None:
            s.SetNet(net)
        board.Add(s)
    return ps.OutlineCount()


def pad_poly(pad, layer, grow_mm=0.0):
    ps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(ps, layer, FromMM(grow_mm), ERR, pcbnew.ERROR_OUTSIDE)
    return ps
