#!/usr/bin/env python3
"""Pull the artwork out of the maker's KiCad 8 board into art/art.json, turned over so the art side becomes the front.

Run once with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/knight-rider/hardware/extract_art.py

The 2024 KiCad 8 board (original/KiCad8/kitt_0805.kicad_pcb) has its parts on the front and the car drawing on the
back copper, back mask and back silkscreen. SAO++ puts the art on the front, so every shape is mirrored about the
board's centre line (x -> 297 - x) and moved to the matching front layer: the same physical board, turned over.
What is written (mm, KiCad front view of the NEW board):
  outline            the board edge, one closed path
  front_cu           the eight copper art shapes (from B.Cu zones), as drawn: no clearances cut
  front_silk         the four white shapes (from B.Silkscreen zones)
  front_mask_open    the six bare-board windows (from B.Mask zones): the bumper lights
  leds               centre of each 2024 scanner LED (D1..D8) and which end its anode is
  back_text          the maker's credit lines from the old front silkscreen, which is now the back
"""
import json
import os

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "KiCad8", "kitt_0805.kicad_pcb")
OUT = os.path.join(HERE, "..", "art", "art.json")
MX = 297.0                      # mirror line x = 148.5, the middle of the 2024 board (123.5 .. 173.5)


def mx(v):
    return [round(MX - ToMM(v.x), 4), round(ToMM(v.y), 4)]


def chain(c):
    return [mx(c.CPoint(k)) for k in range(c.PointCount())]


b = pcbnew.LoadBoard(SRC)
art = {"source": "original/KiCad8/kitt_0805.kicad_pcb (KiCad 8, 2024-09-05 production files), mirrored x -> 297 - x",
       "front_cu": [], "front_silk": [], "front_mask_open": []}
dest = {pcbnew.B_Cu: "front_cu", pcbnew.B_SilkS: "front_silk", pcbnew.B_Mask: "front_mask_open"}
for z in b.Zones():
    if z.GetLayer() in dest and not z.GetNetname():
        o = z.Outline()
        assert o.OutlineCount() == 1 and o.HoleCount(0) == 0
        art[dest[z.GetLayer()]].append(chain(o.Outline(0)))
assert [len(art[k]) for k in ("front_cu", "front_silk", "front_mask_open")] == [8, 4, 6]

ps = pcbnew.SHAPE_POLY_SET()
assert b.GetBoardPolygonOutlines(ps, False) and ps.OutlineCount() == 1
ps.Simplify()
art["outline"] = chain(ps.Outline(0))

art["leds"] = {}
for fp in b.GetFootprints():
    r = fp.GetReference()
    if r.startswith("D"):
        pads = {p.GetNumber(): mx(p.GetPosition()) for p in fp.Pads()}
        art["leds"][r] = {"centre": mx(fp.GetPosition()), "anode": pads["2"], "cathode": pads["1"]}
assert len(art["leds"]) == 8

art["back_text"] = []
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS:
        bb = d.GetBoundingBox()
        art["back_text"].append({"text": d.GetText(), "size": round(ToMM(d.GetTextSize().y), 4),
                                 "thickness": round(ToMM(d.GetTextThickness()), 4), "bold": d.IsBold(),
                                 "bbox": [round(MX - ToMM(bb.GetRight()), 3), round(ToMM(bb.GetTop()), 3),
                                          round(MX - ToMM(bb.GetLeft()), 3), round(ToMM(bb.GetBottom()), 3)]})
json.dump(art, open(OUT, "w"), indent=0)
print("wrote", OUT, {k: len(v) for k, v in art.items() if isinstance(v, (list, dict))})
for t in art["back_text"]:
    print(t)
