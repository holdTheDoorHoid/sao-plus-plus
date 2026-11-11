#!/usr/bin/env python3
"""Read the maker's Eagle board (original/penghitopoco.brd, XML) and write the outline and art as art/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/penghito-poco/hardware/extract_art.py

What the Eagle file holds, and where it goes on the SAO++ board
  layer 20  Dimension   1439 short lines, one closed loop (with a 0.0 mm-ish gap at the start) -> "outline"
  layer 26  bNames      four filled polygons: face, belly, ... (drawn on Eagle's BOTTOM) -> front silkscreen "silk"
  layer 30  bStop       five filled polygons: horn, beak, two feet (Eagle BOTTOM) -> front solder-mask openings "mask"
  GND pour  layers 1+16 copper over the whole board on both sides -> rebuilt by build_board.py
  elements  LED1, LED2 (5 mm through-hole, the eyes) and JP1 (2x2 header, on the right wing) -> "leds", "old_header"

The maker drew the art on Eagle's bottom side, and the OSH Park picture (original/penghitoOSHPark.png) shows that side.
So the picture's view is Eagle's bottom seen from below: mirrored left-right. The penguin is also drawn turned 45
degrees in Eagle (head toward the top-right corner). Both are undone here, so art.json is in KiCad's front view
(mm, x right, y down) with the penguin upright, exactly as in the picture.
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "penghitopoco.brd")
OUT = os.path.join(HERE, "..", "art", "art.json")
R2 = math.sqrt(2)


def view(x, y):
    """Eagle (x, y; y up; seen from the top) -> upright, seen from Eagle's bottom, KiCad axes before the offset."""
    u = (y - x) / R2          # mirror x (bottom view), then turn 45 degrees clockwise
    v = (x + y) / R2          # v points up the penguin
    return u, -v


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


root = ET.parse(SRC).getroot()
plain = root.find(".//plain")

# outline: chain the dimension lines end to end
segs = [((e.get("x1"), e.get("y1")), (e.get("x2"), e.get("y2"))) for e in plain if e.tag == "wire" and e.get("layer") == "20"]
assert len(segs) == 1439, len(segs)
assert all(e.get("curve") is None for e in plain if e.tag == "wire"), "curved dimension lines are not handled"
adj = {}
for i, (a, b) in enumerate(segs):
    adj.setdefault(a, []).append(i)
    adj.setdefault(b, []).append(i)
ends = [p for p, l in adj.items() if len(l) == 1]
assert len(ends) == 2, ends
start = ends[0]
chain, used, cur = [start], set(), start
while True:
    nxt = [i for i in adj[cur] if i not in used]
    if not nxt:
        break
    i = nxt[0]
    used.add(i)
    a, b = segs[i]
    cur = b if a == cur else a
    chain.append(cur)
assert len(used) == len(segs)
gap = math.dist(tuple(map(float, ends[0])), tuple(map(float, ends[1])))
print(f"outline: {len(chain)} points, gap between the two open ends {gap * 1000:.1f} um (closed here)")
outline = [view(float(x), float(y)) for x, y in chain]
if math.dist(outline[0], outline[-1]) < 1e-6:
    outline.pop()
xs, ys = [p[0] for p in outline], [p[1] for p in outline]
OX, OY = 100.0 - min(xs), 100.0 - min(ys)      # top-left of the board at (100, 100)


def T(x, y):
    u, v = view(x, y)
    return [round(u + OX, 4), round(v + OY, 4)]


outline = [[round(x + OX, 4), round(y + OY, 4)] for x, y in outline]
if area2(outline) < 0:
    outline.reverse()

polys = {"26": [], "30": []}
for e in plain:
    if e.tag == "polygon":
        assert all(v.get("curve") is None for v in e.findall("vertex")), "curved polygon edges are not handled"
        polys[e.get("layer")].append([T(float(v.get("x")), float(v.get("y"))) for v in e.findall("vertex")])

el = {e.get("name"): e for e in root.findall(".//elements/element")}
leds = {k: T(float(el[k].get("x")), float(el[k].get("y"))) for k in ("LED1", "LED2")}
# header JP1: four pads on a 2.54 mm square, package placed mirrored and turned 315 degrees
jx, jy = float(el["JP1"].get("x")), float(el["JP1"].get("y"))
pads = []
for px, py in ((0, 0), (0, 2.54), (2.54, 0), (2.54, 2.54)):
    a = math.radians(315)
    px = -px                                         # M = mirrored
    rx, ry = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    pads.append(T(jx + rx, jy + ry))

art = {
    "source": "original/penghitopoco.brd (Eagle XML), converted by hardware/extract_art.py",
    "units": "mm, KiCad front view (x right, y down); the front is the art side shown in original/penghitoOSHPark.png",
    "outline": outline,
    "silk": polys["26"],
    "mask": polys["30"],
    "leds": leds,
    "old_header_pads": pads,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(art, open(OUT, "w"), indent=0)
xs, ys = [p[0] for p in outline], [p[1] for p in outline]
print(f"board {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm; silk polygons {len(polys['26'])}, mask openings {len(polys['30'])}")
print("LED centres", leds)
print("old header pads", pads)
