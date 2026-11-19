#!/usr/bin/env python3
"""Extract the maker's outline and front art from his KiCad 8 board into hardware/art.json.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-bath/hardware/extract_art.py

The maker's art is all on the front already (front ground copper under green mask, white silkscreen drawing of the
tub, bubbles and feet), and his parts are on the back, as in SAO++. Nothing is mirrored. Output: mm, KiCad front view,
board's left edge at x = 10, top at y = 10. His RGB LED (D1) position is kept too: it is the point of the board.
"""
import json
import os
import shutil
import tempfile

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "duckbath", "duckbath.kicad_pcb")
# LoadBoard rewrites the project-local file next to the board: read a copy instead, so original/ stays untouched
TMP = os.path.join(HERE, "_extract_tmp.kicad_pcb")
shutil.copy(SRC, TMP)
b = pcbnew.LoadBoard(TMP)
bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = ToMM(bb.GetLeft()), ToMM(bb.GetTop())


def T(v):
    return [round(ToMM(v.x) - X0 + 10.0, 4), round(ToMM(v.y) - Y0 + 10.0, 4)]


def chain(c):
    return [T(c.CPoint(k)) for k in range(c.PointCount())]


def polys(ps):
    return [{"outer": chain(ps.Outline(i)), "holes": [chain(ps.Hole(i, h)) for h in range(ps.HoleCount(i))]}
            for i in range(ps.OutlineCount())]


def shape_poly(d):
    ps = pcbnew.SHAPE_POLY_SET()
    d.TransformShapeToPolygon(ps, d.GetLayer(), 0, pcbnew.FromMM(0.003), pcbnew.ERROR_OUTSIDE)
    ps.Simplify()
    return ps


edge = pcbnew.SHAPE_POLY_SET()
assert b.GetBoardPolygonOutlines(edge, False)
edge.Simplify()
assert edge.OutlineCount() == 1
out = {"source": os.path.relpath(SRC, os.path.join(HERE, "..")), "outline": chain(edge.Outline(0)),
       "outline_holes": [chain(edge.Hole(0, h)) for h in range(edge.HoleCount(0))],
       "silk": [], "teeth": [], "back_mask": [], "back_keepout": [], "led": {}, "back_text": []}
for d in b.GetDrawings():
    L = d.GetLayer()
    if d.GetClass() == "PCB_SHAPE" and L == pcbnew.F_SilkS:
        out["silk"] += polys(shape_poly(d))
    elif d.GetClass() == "PCB_SHAPE" and L == pcbnew.F_Cu:
        out["teeth"] += polys(shape_poly(d))          # exposed gold copper art (Duck Jaws' teeth); F.Mask matches it
    elif d.GetClass() == "PCB_SHAPE" and L == pcbnew.B_Mask:
        out["back_mask"] += polys(shape_poly(d))
    elif d.GetClass() == "PCB_TEXT" and L == pcbnew.B_SilkS:
        out["back_text"].append({"text": d.GetShownText(False), "at": T(d.GetPosition()),
                                 "size": round(ToMM(d.GetTextSize().x), 4), "thickness": round(ToMM(d.GetTextThickness()), 4)})
for z in b.Zones():
    if z.GetIsRuleArea() and z.IsOnLayer(pcbnew.B_Cu):
        out["back_keepout"] += polys(z.Outline())
for fp in b.GetFootprints():
    if fp.GetReference() == "D1":
        out["led"] = {"at": T(fp.GetPosition()), "pads": {p.GetNumber(): T(p.GetPosition()) for p in fp.Pads()}}
print({k: len(v) for k, v in out.items() if isinstance(v, (list, dict))})
print("outline pts", len(out["outline"]), "holes", len(out["outline_holes"]), "size", ToMM(bb.GetWidth()), ToMM(bb.GetHeight()))
json.dump(out, open(os.path.join(HERE, "art.json"), "w"))
for f in (TMP, TMP[:-len("kicad_pcb")] + "kicad_prl", TMP[:-len("kicad_pcb")] + "kicad_pro"):
    if os.path.exists(f):
        os.remove(f)
