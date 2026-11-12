#!/usr/bin/env python3
"""Read the maker's Eagle board (original/eggplant.brd, XML) and write the outline and art as art/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/eggplant/hardware/extract_art.py

What the Eagle file holds, and where it goes on the SAO++ board
  layer 20     Dimension  203 straight lines, one closed loop                       -> "outline"
  layers 1+16  copper     two polygons per side, the same on both sides: the body (on GND) and the
                          stalk-and-leaves ("calyx", a net of its own, N$2 / N$3, connected to nothing) -> "body", "calyx"
  layers 29+30 tStop/bStop  one polygon per side, the calyx: bare metal there          -> "calyx_mask"
  layers 41+42 restrict   two polygons per side: the long stripe down one side of the body and a short
                          streak on the calyx where there is no copper (the board shows through) -> "no_copper"
  layers 25+26 tNames/bNames  two filled polygons per side: a vein on the calyx and the shine mark on the body -> "silk"
  layer 26     bNames     16 short lines (a block of tally marks), back only            -> "back_marks"
  layer 26     three blocks of text, back only                                         -> "back_text"
  elements     five two-colour LEDs and the 4-pin add-on header                        -> "leds", "old_header"

The maker's art is the same on both faces; parts are on Eagle's bottom. The SAO++ front is Eagle's top.
The add-on header sits turned 45 degrees in Eagle, so the board hangs tilted on a badge. art.json is in the
worn position: KiCad's front view (mm, x right, y down), turned so the old header's "up" is up.
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "eggplant.brd")
OUT = os.path.join(HERE, "..", "art", "art.json")
R2 = math.sqrt(2)


def view(x, y):
    """Eagle top view (y up) -> turned 45 degrees anticlockwise (header square), KiCad axes before the offset."""
    return (x - y) / R2, -(x + y) / R2


root = ET.parse(SRC).getroot()
board = root.find(".//board")
plain = board.find("plain")
assert all(e.get("curve") is None for e in board.iter("wire") if e.get("layer") == "20"), "curved outline lines are not handled"
assert all(v.get("curve") is None for v in board.iter("vertex")), "curved polygon edges are not handled"

segs = [((e.get("x1"), e.get("y1")), (e.get("x2"), e.get("y2"))) for e in plain if e.tag == "wire" and e.get("layer") == "20"]
adj = {}
for i, (a, b) in enumerate(segs):
    adj.setdefault(a, []).append(i)
    adj.setdefault(b, []).append(i)
assert all(len(v) == 2 for v in adj.values()), "outline is not one clean closed loop"
start = segs[0][0]
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
assert len(used) == len(segs) and chain[0] == chain[-1]
chain.pop()
raw = [view(float(x), float(y)) for x, y in chain]
OX, OY = 100.0 - min(p[0] for p in raw), 100.0 - min(p[1] for p in raw)      # top-left of the board at (100, 100)


def T(x, y):
    u, v = view(float(x), float(y))
    return [round(u + OX, 4), round(v + OY, 4)]


def polys(parent, layer):
    return [[T(v.get("x"), v.get("y")) for v in e.findall("vertex")] for e in parent.findall("polygon") if e.get("layer") == layer]


sig = {s.get("name"): s for s in board.find("signals")}
art = {
    "source": "original/eggplant.brd (Eagle XML), converted by hardware/extract_art.py",
    "units": "mm, KiCad front view (x right, y down), in the worn position (old header square, its top row up)",
    "eagle_to_here": "x = (ex - ey) / sqrt(2) + offset[0], y = -(ex + ey) / sqrt(2) + offset[1]",
    "offset": [round(OX, 4), round(OY, 4)],
    "outline": [T(x, y) for x, y in chain],
    "body": polys(sig["GND"], "1"),
    "calyx": polys(sig["N$2"], "1"),
    "calyx_mask": polys(plain, "29"),
    "no_copper": polys(plain, "41"),
    "silk": polys(plain, "25"),
    "back_marks": [[T(e.get("x1"), e.get("y1")), T(e.get("x2"), e.get("y2")), float(e.get("width"))]
                   for e in plain if e.tag == "wire" and e.get("layer") == "26"],
    "back_text": [{"at": T(e.get("x"), e.get("y")), "size": float(e.get("size")), "rot": e.get("rot"), "text": e.text}
                  for e in plain.findall("text")],
}
# the back copies of the art must be the same shapes (they are, to within the maker's own redraw of a few points)
for name, front, back in (("body", art["body"], polys(sig["GND"], "16")), ("calyx", art["calyx"], polys(sig["N$3"], "16")),
                          ("mask", art["calyx_mask"], polys(plain, "30")), ("no_copper", art["no_copper"], polys(plain, "42")),
                          ("silk", art["silk"], polys(plain, "26"))):
    for f, b in zip(front, back):
        fx, bx = [p[0] for p in f], [p[0] for p in b]
        fy, by = [p[1] for p in f], [p[1] for p in b]
        d = max(abs(min(fx) - min(bx)), abs(max(fx) - max(bx)), abs(min(fy) - min(by)), abs(max(fy) - max(by)))
        print(f"{name}: front {len(f)} points, back {len(b)} points, bounding boxes differ by {d:.3f} mm")

el = {e.get("name"): e for e in board.find("elements")}
art["leds"] = {k: T(el[k].get("x"), el[k].get("y")) for k in ("LED1", "LED2", "LED3", "LED4", "LED5")}
art["old_header"] = T(el["U$1"].get("x"), el["U$1"].get("y"))
art["old_chip"] = T(el["U1"].get("x"), el["U1"].get("y"))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(art, open(OUT, "w"), indent=0)
xs, ys = [p[0] for p in art["outline"]], [p[1] for p in art["outline"]]
print(f"outline {len(art['outline'])} points; board in the worn position {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm")
print("LEDs", art["leds"], "old header", art["old_header"])
for t in art["back_text"]:
    print("back text", t)
