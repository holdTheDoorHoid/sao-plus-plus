#!/usr/bin/env python3
"""Extract the maker's outline and art from his KiCad 8 import into hardware/art.json, mirrored to the SAO++ side.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mr-robot/hardware/extract_art.py

The maker put his parts on the top and the face on the BOTTOM (bottom copper, bottom silkscreen, the words "dave" and
"darko" as openings in the bottom mask). SAO++ puts the art on the front and the parts on the back, so the whole board
is mirrored left-right: seen from its art side the face looks exactly as before, and his parts side (with his gold
"ds" logo) becomes our back. Output coordinates: mm, KiCad front view, board's left edge at x = 10, top at y = 10.
"""
import json
import os

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "KiCad8", "saomr.kicad_pcb")
PRL = SRC[:-len("kicad_pcb")] + "kicad_prl"
_prl = open(PRL, "rb").read()          # LoadBoard rewrites the maker's project-local file: put it back afterwards
b = pcbnew.LoadBoard(SRC)
bb = b.GetBoardEdgesBoundingBox()
X0, X1, Y0 = ToMM(bb.GetLeft()), ToMM(bb.GetRight()), ToMM(bb.GetTop())


def T(v):
    """Maker's coordinates -> SAO++ front view (mirrored left-right)."""
    return [round(X1 - ToMM(v.x) + 10.0, 4), round(ToMM(v.y) - Y0 + 10.0, 4)]


def chain(c):
    return [T(c.CPoint(k)) for k in range(c.PointCount())]


def polys(ps):
    return [{"outer": chain(ps.Outline(i)), "holes": [chain(ps.Hole(i, h)) for h in range(ps.HoleCount(i))]}
            for i in range(ps.OutlineCount())]


edge = pcbnew.SHAPE_POLY_SET()
assert b.GetBoardPolygonOutlines(edge, False)
edge.Simplify()
assert edge.OutlineCount() == 1 and edge.HoleCount(0) == 0
out = {"source": "original/KiCad8/saomr.kicad_pcb, mirrored left-right", "outline": chain(edge.Outline(0)),
       "copper": [], "silk": [], "mask_text": [], "logo": {}}
for z in b.Zones():
    layer = z.GetLayer()
    if layer == pcbnew.B_Cu:
        out["copper"] += polys(z.Outline())            # face art: becomes front copper
    elif layer == pcbnew.B_SilkS:
        out["silk"] += polys(z.Outline())              # moustache, brows, ears: becomes front silkscreen
    else:
        assert layer == pcbnew.F_Cu and z.GetNetname() == "N$4", (z.GetLayerName(), z.GetNetname())   # his ground pour: dropped
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.B_Mask:
        out["mask_text"].append({"text": d.GetText(), "at": T(d.GetPosition()), "size": round(ToMM(d.GetTextSize().x), 6),
                                 "thickness": round(ToMM(d.GetTextThickness()), 6), "angle": d.GetTextAngleDegrees()})
for fp in b.GetFootprints():
    if fp.GetFPIDAsString().endswith("DAVEDARKO_GOLD"):
        for g in fp.GraphicalItems():
            if g.GetShape() == pcbnew.SHAPE_T_POLY and g.GetLayer() in (pcbnew.F_Cu, pcbnew.F_Mask, pcbnew.F_SilkS):
                ps = pcbnew.SHAPE_POLY_SET()
                g.TransformShapeToPolygon(ps, g.GetLayer(), 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
                ps.Simplify()
                out["logo"].setdefault(g.GetLayerName(), []).extend(polys(ps))
print({k: len(v) for k, v in out.items() if isinstance(v, (list, dict))}, {k: len(v) for k, v in out["logo"].items()})
print("outline pts", len(out["outline"]), "size", ToMM(bb.GetWidth()), ToMM(bb.GetHeight()))
json.dump(out, open(os.path.join(HERE, "art.json"), "w"))
open(PRL, "wb").write(_prl)
