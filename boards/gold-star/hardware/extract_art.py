#!/usr/bin/env python3
"""Read the maker's star.svg and write the SAO++ board outline and front art as plain numbers.

  python3 boards/gold-star/hardware/extract_art.py        (plain Python 3, no KiCad needed)

The maker published no board layout (his .kicad_pcb is a 51-byte placeholder). What he drew is this one Inkscape file
on a 100 x 100 mm page (the svg2shenzhen layer template):
  layer "Edge.Cuts"  one ellipse, 100.54 x 99.46 mm: a round board
  layer "F.Silk"     a five-pointed star, 77.5 mm across, drawn as an Inkscape star and stretched a little
  layer "B.Silk"     two lines of text along the rim: "@greymanhw" and "star 1.0.0"
A 100 mm disc is far too big for an add-on, and nothing in the repo says the drawing was at final size. This script
keeps every proportion (outline shape, star shape, star size and position inside the outline) and scales the lot by
SCALE. The one change to the shape is a 12.4 mm flat on the right-hand edge for the slide switch.

Writes (millimetres, KiCad front view: x grows right, y grows down, board centre at 0, 0):
  hardware/outline.json   {"outer": [[x, y], ...], "holes": []}
  art/art.json            star polygon, outline numbers and the maker's two text lines
"""
import json
import math
import os
import re
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(HERE, "..", "original", "star.svg")

SCALE = 0.48            # 100.54 x 99.46 mm drawing -> 48.26 x 47.74 mm board (see README: why this size)
FLAT_HALF = 6.2         # half the length of the straight edge the switch needs
FLAT_SIDE = +1          # +1 = right-hand edge in front view

NS = {"svg": "http://www.w3.org/2000/svg", "ink": "http://www.inkscape.org/namespaces/inkscape"}
root = ET.parse(SVG).getroot()


def layer(label):
    for g in root.iter("{%s}g" % NS["svg"]):
        if g.get("{%s}label" % NS["ink"]) == label:
            return g
    raise KeyError(label)


# ---- outline: the one ellipse on Edge.Cuts -----------------------------------------------------------
ell = list(layer("Edge.Cuts").iter("{%s}ellipse" % NS["svg"]))
assert len(ell) == 1
ecx, ecy, erx, ery = (float(ell[0].get(k)) for k in ("cx", "cy", "rx", "ry"))
RX, RY = erx * SCALE, ery * SCALE


def to_board(x, y):
    return (round((x - ecx) * SCALE, 4), round((y - ecy) * SCALE, 4))


xf = RX * math.sqrt(1 - (FLAT_HALF / RY) ** 2)            # where the flat sits
t0 = math.asin(FLAT_HALF / RY)
N = 240
outer = []
for k in range(N + 1):
    t = t0 + (2 * math.pi - 2 * t0) * k / N                 # from the flat's lower corner round to its upper corner
    outer.append([round(FLAT_SIDE * RX * math.cos(t), 4), round(RY * math.sin(t), 4)])
assert abs(outer[0][0] - FLAT_SIDE * xf) < 1e-3 and abs(outer[0][1] - FLAT_HALF) < 1e-3
assert abs(outer[-1][0] - FLAT_SIDE * xf) < 1e-3 and abs(outer[-1][1] + FLAT_HALF) < 1e-3

# ---- the star on F.Silk --------------------------------------------------------------------------------
g_star = layer("star")
paths = list(g_star.iter("{%s}path" % NS["svg"]))
assert len(paths) == 1
m = re.match(r"matrix\(([^)]*)\)", paths[0].get("transform"))
a, b, c, d, e, f = (float(v) for v in m.group(1).split(","))
tr = re.match(r"translate\(([^)]*)\)", g_star.get("transform"))
tx, ty = (float(v) for v in tr.group(1).split(","))
tok = paths[0].get("d").split()
assert tok[0] == "m" and tok[-1] == "z"
pts, cur = [], (0.0, 0.0)
for pair in tok[1:-1]:
    dx, dy = (float(v) for v in pair.split(","))
    cur = (cur[0] + dx, cur[1] + dy)
    pts.append(cur)
assert len(pts) == 10
star = [to_board(a * x + c * y + e + tx, b * x + d * y + f + ty) for x, y in pts]     # tip, notch, tip, ... clockwise from the top
sx = float(paths[0].get("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}cx"))
sy = float(paths[0].get("{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}cy"))
star_centre = to_board(a * sx + c * sy + e + tx, b * sx + d * sy + f + ty)

# ---- the two text lines on B.Silk ------------------------------------------------------------------------
credits = []
for t in layer("greymanhw").iter("{%s}text" % NS["svg"]):
    words = "".join(s.text or "" for s in t.iter("{%s}tspan" % NS["svg"])).strip()
    if not words:
        continue                                             # the file has one empty text box
    rot = float(re.match(r"rotate\(([^)]*)\)", t.get("transform")).group(1))
    size = float(re.search(r"font-size:([0-9.]+)px", t.get("style")).group(1))
    x, y = float(t.get("x")), float(t.get("y"))
    r = math.radians(rot)
    credits.append({"text": words, "start_100mm_page": [round(x * math.cos(r) - y * math.sin(r), 2), round(x * math.sin(r) + y * math.cos(r), 2)],
                    "rotate_deg": rot, "font_px": round(size, 3), "font_mm_at_scale": round(size * SCALE, 2)})
assert [c_["text"] for c_ in credits] == ["@greymanhw", "star 1.0.0"], credits

json.dump({"outer": outer, "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
os.makedirs(os.path.join(HERE, "..", "art"), exist_ok=True)
json.dump({"note": "Made by hardware/extract_art.py from original/star.svg. Millimetres, KiCad front view, board centre at 0,0.",
           "scale": SCALE, "outline_rx_ry": [round(RX, 4), round(RY, 4)],
           "flat": {"side": FLAT_SIDE, "x": round(FLAT_SIDE * xf, 4), "half_length": FLAT_HALF},
           "star": star, "star_centre": star_centre, "back_silk_text": credits},
          open(os.path.join(HERE, "..", "art", "art.json"), "w"), indent=1)
w = max(p[0] for p in outer) - min(p[0] for p in outer)
h = max(p[1] for p in outer) - min(p[1] for p in outer)
print(f"board {w:.2f} x {h:.2f} mm (ellipse {2 * RX:.2f} x {2 * RY:.2f}, flat at x = {FLAT_SIDE * xf:.2f})")
print("star centre", star_centre, "tips and notches:", star)
print("back text:", credits)
