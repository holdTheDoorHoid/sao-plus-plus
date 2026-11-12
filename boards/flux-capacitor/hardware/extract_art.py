#!/usr/bin/env python3
"""Read the maker's Eagle board (original/attiny45.brd, XML) and write the outline and art as art/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/flux-capacitor/hardware/extract_art.py

What the Eagle file holds, and where it goes (the maker's front = Eagle top, so no mirroring):
  layer 20  Dimension   8 lines and arcs: a 25.4 x 30.47 mm rectangle with 2.54 mm rounded corners -> "outline"
  layer 25  tNames      the Y of the flux capacitor (one filled polygon, 0.41 mm stroke) and three warning lines
                        ("DISCONNECT CAPACITOR DRIVE" / "BEFORE OPENING" / "SHIELD EYES FROM LIGHT") -> front silkscreen
  layer 29  tStop       9 wires and arcs: bare-copper "cables" from the three electrodes -> front solder-mask openings
  layer 26  bNames      the maker's credit, two lines on the back right edge -> back silkscreen, kept as drawn
  GND vias  three 0.9 mm drill / 1.778 mm vias at the ends of the Y (the "electrodes"; bigger than Eagle's 35 mil
            tenting limit, so bare on both sides) -> "electrodes"
  elements  L1-L9: 1206 LEDs on the front (the art) -> "leds"
  N$1/3/5   the maker's front tracks joining the three LEDs of each ring -> "front_tracks" (his wiring, kept)
  dropped   the two bare back pads for a brooch pin (layer 16 + 30 rectangles), every back part, the maker's tracks
            and his six small routing vias: build_board.py rebuilds all of that
Coordinates in art.json are KiCad front view at the maker's size (mm, x right, y down, top-left corner at 100, 100);
build_board.py scales them.
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "attiny45.brd")
OUT = os.path.join(HERE, "..", "art", "art.json")
TOP = 27.93                                   # Eagle y of the top edge


def T(x, y):
    return [round(100.0 + x, 4), round(100.0 + TOP - y, 4)]


def arc_pts(x1, y1, x2, y2, curve, step_deg=5):
    """Points of an Eagle wire with a 'curve' (degrees, counter-clockwise from start to end), Eagle coordinates."""
    a = math.radians(curve)
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    r = d / 2 / math.sin(a / 2)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    h = r * math.cos(a / 2)
    cx, cy = mx - h * dy / d, my + h * dx / d          # centre to the left of start->end for a positive (CCW) curve
    a0 = math.atan2(y1 - cy, x1 - cx)
    n = max(2, int(abs(curve) / step_deg))
    return [(cx + abs(r) * math.cos(a0 + a * k / n), cy + abs(r) * math.sin(a0 + a * k / n)) for k in range(n + 1)]


def wire_pts(w):
    x1, y1, x2, y2 = (float(w.get(k)) for k in ("x1", "y1", "x2", "y2"))
    if w.get("curve"):
        return arc_pts(x1, y1, x2, y2, float(w.get("curve")))
    return [(x1, y1), (x2, y2)]


root = ET.parse(SRC).getroot()
board = root.find(".//board")
plain = board.find("plain")

# outline: chain the 8 dimension wires
dims = [wire_pts(w) for w in plain if w.tag == "wire" and w.get("layer") == "20"]
chain = list(dims[0])
left = dims[1:]
while left:
    for k, seg in enumerate(left):
        if math.dist(seg[0], chain[-1]) < 1e-3:
            chain += seg[1:]
            break
        if math.dist(seg[-1], chain[-1]) < 1e-3:
            chain += seg[::-1][1:]
            break
    else:
        raise SystemExit("outline does not close")
    left.pop(k)
assert math.dist(chain[0], chain[-1]) < 1e-3
outline = [T(*p) for p in chain[:-1]]

silk = []
for e in plain:
    if e.tag == "polygon" and e.get("layer") == "25":
        silk.append({"pts": [T(float(v.get("x")), float(v.get("y"))) for v in e.findall("vertex")], "stroke": float(e.get("width"))})
texts = []
for e in plain:
    if e.tag == "text" and e.get("layer") in ("25", "26"):
        texts.append({"text": e.text, "at": T(float(e.get("x")), float(e.get("y"))), "size": float(e.get("size")),
                      "rot": e.get("rot", "R0"), "side": "front" if e.get("layer") == "25" else "back",
                      "ratio": 0.08})          # Eagle's default stroke ratio (8 % of the height)
mask = []
for e in plain:
    if e.tag == "wire" and e.get("layer") == "29":
        mask.append({"pts": [T(*p) for p in wire_pts(e)], "width": float(e.get("width"))})

el = {e.get("name"): e for e in board.find("elements")}
leds = {}
for k in range(1, 10):
    e = el[f"L{k}"]
    x, y = float(e.get("x")), float(e.get("y"))
    rot = e.get("rot", "R0")
    assert not rot.startswith("M"), "LEDs are on the front"
    a = math.radians(float(rot[1:]))
    ax, ay = x + 1.75 * math.cos(a), y + 1.75 * math.sin(a)       # SML1206: anode pad at +1.75 mm along the package x
    leds[f"L{k}"] = {"centre": T(x, y), "anode_dir": [round(math.cos(a), 3), round(-math.sin(a), 3)]}
electrodes = []
for s in board.find("signals"):
    for v in s.findall("via"):
        if float(v.get("drill")) > 0.8:
            assert s.get("name") == "GND"
            electrodes.append({"at": T(float(v.get("x")), float(v.get("y"))), "drill": float(v.get("drill")),
                               "diameter": float(v.get("diameter"))})

# the maker's own front wiring of the three LED rings (N$1 / N$3 / N$5): kept, scaled, by build_board.py. The short
# stubs down to his three vias are left out (build_board.py makes its own way to the back).
RINGS = {"N$1": "RING1", "N$3": "RING2", "N$5": "RING3"}
via_xy = {s_.get("name"): [(float(v.get("x")), float(v.get("y"))) for v in s_.findall("via")] for s_ in board.find("signals")}
front_tracks = []
for s_ in board.find("signals"):
    if s_.get("name") not in RINGS:
        continue
    vx, vy = via_xy[s_.get("name")][0]
    for w in s_.findall("wire"):
        if w.get("layer") != "1":
            continue
        a, b = wire_pts(w)
        if s_.get("name") == "N$3" and float(w.get("width")) < 0.3:       # stub to the via
            continue
        if s_.get("name") == "N$5" and any(abs(x - vx) < 0.01 for x, _ in (a, b)):
            continue
        front_tracks.append({"net": RINGS[s_.get("name")], "a": T(*a), "b": T(*b), "width": float(w.get("width"))})
anode_pads = {k: [round(v["centre"][0] + 1.75 * v["anode_dir"][0], 4), round(v["centre"][1] + 1.75 * v["anode_dir"][1], 4)]
              for k, v in leds.items()}

art = {
    "source": "original/attiny45.brd (Eagle XML), converted by hardware/extract_art.py",
    "units": "mm, KiCad front view (x right, y down), maker's size, top-left corner at (100, 100)",
    "outline": outline, "front_silk": silk, "texts": texts, "front_mask_open": mask,
    "leds": leds, "electrodes": electrodes, "front_tracks": front_tracks, "maker_anode_pads": anode_pads,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(art, open(OUT, "w"), indent=0)
xs, ys = [p[0] for p in outline], [p[1] for p in outline]
print(f"board {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm, {len(outline)} outline points; "
      f"silk {len(silk)}, texts {len(texts)}, mask wires {len(mask)}, leds {len(leds)}, electrodes {len(electrodes)}")
