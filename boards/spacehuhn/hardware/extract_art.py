#!/usr/bin/env python3
"""Read the maker's newest Eagle board (original/rev3/badge_spacehuhn.brd, XML) and write art/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/spacehuhn/hardware/extract_art.py

Which revision: the maker's folder holds three boards with the same schematic: the top level (parts at odd angles,
65 degrees), rev2 (115 degrees) and rev3 (parts square to the board, the most art: 349 silkscreen and 10 mask shapes,
the outline redrawn from a new DXF). rev3 is the newest and is the one used.

What the Eagle file holds, and where it goes on the SAO++ board
  layer 20  Dimension   478 straight lines, one closed loop                         -> "outline"
  layer 26  bNames      349 filled shapes: helmet ring, polka dots, comb, eyes, wing  -> front silkscreen "silk"
  layer 30  bStop       10 mask openings: the chicken's face/beak (bare gold) and nine tiny stars -> front mask "mask"
  layer 1 + 29 (top)    two 5.1 x 3.8 mm copper rectangles with mask openings: the maker's "markers used for
                        multicolor PCBs", kept exactly as drawn on the back                 -> "markers"
  layer 25  tNames      the two credit lines "@spacehuhn tribute", "@davedarko design" (back) -> "texts"
  element U$2           the maker's DAVEDARKO_GOLD logo: three mask openings on the back (gold) -> "logo"
  elements LED1, LED2   5 mm through-hole LEDs, one in the middle of each eye             -> "leds"
  GND pour  layers 1+16 copper over the whole board on both sides -> rebuilt by build_board.py
The art is drawn on Eagle's BOTTOM (the parts sat on Eagle's top), so the art side is Eagle's bottom seen from below:
mirrored left-right. Every coordinate is mirrored here, art and back items alike, so art.json is in KiCad's front
view (mm, x right, y down) as KiCad stores both sides.
Eagle polygons are drawn with a pen of the polygon's width, so every filled shape is really its vertex path grown by
half that width; that is kept as "grow" for build_board.py to apply.
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "rev3", "badge_spacehuhn.brd")
OUT = os.path.join(HERE, "..", "art", "art.json")

root = ET.parse(SRC).getroot()
plain = root.find(".//plain")


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


segs = [((e.get("x1"), e.get("y1")), (e.get("x2"), e.get("y2"))) for e in plain if e.tag == "wire" and e.get("layer") == "20"]
assert len(segs) == 478, len(segs)
assert all(e.get("curve") is None for e in plain if e.tag == "wire"), "curved dimension lines are not handled"
adj = {}
for i, (a, b) in enumerate(segs):
    adj.setdefault(a, []).append(i)
    adj.setdefault(b, []).append(i)
ends = [p for p, l in adj.items() if len(l) != 2]
start = ends[0] if ends else segs[0][0]
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
assert len(used) == len(segs), (len(used), len(segs), ends)
gap = math.dist(tuple(map(float, chain[0])), tuple(map(float, chain[-1])))
print(f"outline: {len(chain)} points, open ends {len(ends)}, gap {gap * 1000:.1f} um (closed here)")
pts = [(float(x), float(y)) for x, y in chain]
XMAX = max(p[0] for p in pts)
YMAX = max(p[1] for p in pts)
OX, OY = 100.0 + XMAX, 100.0 + YMAX       # mirror x and flip y; board's top-left corner lands at about (100, 100)


def T(x, y):
    return [round(OX - x, 4), round(OY - y, 4)]


outline = [T(*p) for p in pts]
if math.dist(outline[0], outline[-1]) < 1e-6:
    outline.pop()
if area2(outline) < 0:
    outline.reverse()


def arc_pts(p0, p1, ang):
    """Points along an Eagle 'curve' edge from p0 to p1 turning ang degrees (positive = counter-clockwise), p0 excluded."""
    a = math.radians(ang)
    d = math.dist(p0, p1)
    r = d / 2 / math.sin(abs(a) / 2)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    h = math.sqrt(max(r * r - (d / 2) ** 2, 0))
    ux, uy = (p1[0] - p0[0]) / d, (p1[1] - p0[1]) / d
    s = 1 if ang > 0 else -1
    cx, cy = mx - s * uy * h, my + s * ux * h        # centre to the left of p0->p1 for a counter-clockwise arc
    if abs(ang) > 180:
        cx, cy = mx + s * uy * h, my - s * ux * h
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    n = max(4, int(abs(ang) / 7.5))
    out = [(cx + r * math.cos(a0 + a * k / n), cy + r * math.sin(a0 + a * k / n)) for k in range(1, n)]
    return out + [p1]


def eagle_poly(e, dx=0.0, dy=0.0):
    vs = e.findall("vertex")
    out = []
    for i, v in enumerate(vs):
        p0 = (float(v.get("x")) + dx, float(v.get("y")) + dy)
        nv = vs[(i + 1) % len(vs)]
        p1 = (float(nv.get("x")) + dx, float(nv.get("y")) + dy)
        out.append(p0)
        if v.get("curve"):
            out.extend(arc_pts(p0, p1, float(v.get("curve")))[:-1])
    return [T(*p) for p in out]


polys = {"26": [], "30": []}
widths = {"26": set(), "30": set()}
for e in plain:
    if e.tag == "polygon":
        polys[e.get("layer")].append(eagle_poly(e))
        widths[e.get("layer")].add(float(e.get("width")))
assert len(widths["26"]) == 1 and len(widths["30"]) == 1

rects = {"1": [], "29": []}
for e in plain:
    if e.tag == "rectangle":
        x1, y1, x2, y2 = (float(e.get(k)) for k in ("x1", "y1", "x2", "y2"))
        rects[e.get("layer")].append([T(x1, y1), T(x2, y1), T(x2, y2), T(x1, y2)])

texts = []
for e in plain:
    if e.tag == "text":
        assert e.get("rot") is None and e.get("align") is None
        texts.append({"text": e.text, "anchor_bottom_left_back_view": T(float(e.get("x")), float(e.get("y"))),
                      "size": float(e.get("size")), "ratio_percent": float(e.get("ratio", "8"))})

el = {e.get("name"): e for e in root.findall(".//elements/element")}
leds = {k: T(float(el[k].get("x")), float(el[k].get("y"))) for k in ("LED1", "LED2")}
lg = el["U$2"]
assert lg.get("rot") is None
pkg = [p for p in root.iter("package") if p.get("name") == "DAVEDARKO_GOLD"][0]
logo = [eagle_poly(p, float(lg.get("x")), float(lg.get("y"))) for p in pkg.findall("polygon")]
logo_w = {float(p.get("width")) for p in pkg.findall("polygon")}
assert {p.get("layer") for p in pkg.findall("polygon")} == {"29"} and len(logo_w) == 1
old = {k: T(float(el[k].get("x")), float(el[k].get("y"))) for k in ("S1", "U$1")}

art = {
    "source": "original/rev3/badge_spacehuhn.brd (Eagle XML), converted by hardware/extract_art.py",
    "units": "mm, KiCad front view (x right, y down); the front is the art side (Eagle's bottom)",
    "outline": outline,
    "silk": polys["26"], "silk_grow": widths["26"].pop() / 2,
    "mask": polys["30"], "mask_grow": widths["30"].pop() / 2,
    "markers_copper": rects["1"], "markers_mask": rects["29"],
    "texts": texts,
    "logo_mask": logo, "logo_grow": logo_w.pop() / 2,
    "leds": leds,
    "old_parts": old,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(art, open(OUT, "w"), indent=0)
xs, ys = [p[0] for p in outline], [p[1] for p in outline]
print(f"board {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm, x {min(xs):.2f}..{max(xs):.2f}, y {min(ys):.2f}..{max(ys):.2f}")
print(f"silk {len(polys['26'])}, mask {len(polys['30'])}, logo {len(logo)}, markers {len(rects['1'])}")
print("LED centres", leds, "texts", texts)
