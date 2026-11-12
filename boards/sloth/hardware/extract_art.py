#!/usr/bin/env python3
"""Read the maker's Eagle board (original/REV1/sloth_final.brd, XML) and write the outline and art as art/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/sloth/hardware/extract_art.py

Which folder: original/REV1 is the badge itself (40 x 30 mm rounded board, SOIC ATtiny85, 12 LEDs in a ring, CR2032
holder, brooch-pin pads). original/programTester is a programming / test jig: a rectangular board with a DIP-8 socket
footprint, the 12 LEDs in a straight row, a 2x3 AVR ISP box header and the silkscreen "SLOTHBADGE TESTER". Only REV1 is
used here.

What the Eagle file holds, and where it goes on the SAO++ board
  layer 20  Dimension  six lines (four 90-degree arcs, two straights): a 40 x 30 mm stadium        -> "outline"
  layer 30  bStop      ten filled polygons: the sloth face (Eagle BOTTOM) -> front solder-mask openings "mask"
                       over the maker's ground pour, so they show as bare gold copper
  layer 16  GND pour   copper over the whole bottom (the art side)                                   -> rebuilt by build_board.py
  LED1-12   0805 LEDs, mirrored = on Eagle's BOTTOM, around the rim of the face, facing forward      -> "leds"
  layer 21  DAVEDARKO2_LOGO (top silk, Eagle TOP = the back)                                        -> "back_logo"
  layer 25  top-silk texts: "hackaday.io/davedarko" (credit), "150 Ohm", "ATTINY13A", "ISP", "R1"   -> "back_text"
  layer 1/29 two 6.4 x 4 mm bare copper rectangles near the top of the back: the brooch-pin pads     -> "brooch_pads"
  OSHPARK_LOGO  the board house's logo on the back (not the maker's)                                 -> not carried

The art side is Eagle's bottom. Seen from the front it is Eagle's bottom seen from below, so x is mirrored. KiCad front
view (mm, x right, y down) with the board's top-left corner at (100, 100) and every length scaled by SCALE (see below):
x = 100 + SCALE * (40 - x_eagle),  y = 100 + SCALE * (30 - y_eagle).
The back (Eagle's top) uses the same mapping: it is the same physical spot.
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "REV1", "sloth_final.brd")
OUT = os.path.join(HERE, "..", "art", "art.json")
W, H = 40.0, 30.0
OX, OY = 100.0, 100.0
# Owner rule 2026-11-12: a board too small for the SAO connector, cell clip and switch may be scaled up uniformly.
# The maker's 40 x 30 mm board cannot hold those plus his chip, ISP pads and button (see README), so everything the
# maker drew (outline, art, LED centres, logo, lettering) is scaled by SCALE about the board's top-left corner.
SCALE = float(os.environ.get("SLOTH_SCALE", "1.3"))


def T(x, y):
    return [round(OX + SCALE * (W - x), 4), round(OY + SCALE * (H - y), 4)]


def area2(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


root = ET.parse(SRC).getroot()
plain = root.find(".//board/plain")

# ---- outline: walk the six dimension lines, expanding each arc into 1-degree steps ---------------------------
dim = [e for e in plain if e.tag == "wire" and e.get("layer") == "20"]
assert len(dim) == 6, len(dim)
pts = []
for e in dim:
    x1, y1, x2, y2 = (float(e.get(k)) for k in ("x1", "y1", "x2", "y2"))
    c = float(e.get("curve") or 0)
    if not c:
        pts.append((x1, y1))
        continue
    # Eagle: positive curve = counter-clockwise from (x1, y1) to (x2, y2)
    a = math.radians(c)
    ch = math.dist((x1, y1), (x2, y2))
    r = ch / 2 / math.sin(a / 2)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    d = math.sqrt(max(r * r - (ch / 2) ** 2, 0))
    ux, uy = (x2 - x1) / ch, (y2 - y1) / ch
    cx, cy = mx - uy * d * (1 if c > 0 else -1), my + ux * d * (1 if c > 0 else -1)
    a0 = math.atan2(y1 - cy, x1 - cx)
    n = int(abs(c))
    for k in range(n):
        t = a0 + a * k / n
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
for k in range(len(dim)):                      # the lines chain end to start
    a, b = dim[k], dim[(k + 1) % len(dim)]
    assert (a.get("x2"), a.get("y2")) == (b.get("x1"), b.get("y1")), k
outline = [T(x, y) for x, y in pts]
if area2(outline) < 0:
    outline.reverse()

# ---- mask openings (art) ----------------------------------------------------------------------------------
mask = []
for e in plain:
    if e.tag == "polygon":
        assert e.get("layer") == "30"
        assert all(v.get("curve") is None for v in e.findall("vertex")), "curved polygon edges are not handled"
        mask.append({"width": SCALE * float(e.get("width")), "pts": [T(float(v.get("x")), float(v.get("y"))) for v in e.findall("vertex")]})

brooch = []
for e in plain:
    if e.tag == "rectangle" and e.get("layer") == "1":
        a, b = T(float(e.get("x1")), float(e.get("y1"))), T(float(e.get("x2")), float(e.get("y2")))
        brooch.append([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])])

texts = []
for e in plain:
    if e.tag == "text":
        x, y = float(e.get("x")), float(e.get("y"))
        texts.append({"text": e.text, "anchor_eagle": [x, y], "size": SCALE * float(e.get("size")),
                      # left-bottom anchor seen from the back = right-bottom corner in KiCad front view
                      "right_bottom": T(x, y), "rot": e.get("rot", "R0")})

# ---- packages and elements ----------------------------------------------------------------------------------
pk = {p.get("name"): p for p in root.findall(".//board/libraries/library/packages/package")}


def place(el, lx, ly):
    rot = el.get("rot", "R0")
    mir = rot.startswith("M")
    ang = math.radians(float(rot.lstrip("MSR") or 0))
    if mir:
        lx = -lx
    x = lx * math.cos(ang) - ly * math.sin(ang) + float(el.get("x"))
    y = lx * math.sin(ang) + ly * math.cos(ang) + float(el.get("y"))
    return x, y


els = {e.get("name"): e for e in root.findall(".//board/elements/element")}
leds = {}
for k in range(1, 13):
    el = els[f"LED{k}"]
    assert el.get("rot", "").startswith("M"), "LED not on Eagle bottom"
    pads = {s.get("name"): (float(s.get("x")), float(s.get("y"))) for s in pk["CHIP-LED0805"].findall("smd")}
    c = T(float(el.get("x")), float(el.get("y")))
    an = T(*place(el, *pads["A"]))
    ca = T(*place(el, *pads["C"]))
    leds[f"LED{k}"] = {"centre": c, "anode": an, "cathode": ca, "eagle_rot": el.get("rot")}

logo = []
el = els["U$1"]
for p in pk["DAVEDARKO2_LOGO"].findall("polygon"):
    logo.append({"width": SCALE * float(p.get("width")), "layer": p.get("layer"),
                 "pts": [T(*place(el, float(v.get("x")), float(v.get("y")))) for v in p.findall("vertex")]})

old = {}
for name in ("U1", "U$2", "JP1", "S1", "R1", "R2", "R3", "R4"):
    old[name] = {"centre": T(float(els[name].get("x")), float(els[name].get("y"))), "eagle_rot": els[name].get("rot", "R0")}

art = {
    "source": "original/REV1/sloth_final.brd (Eagle XML), converted by hardware/extract_art.py",
    "scale": SCALE,
    "units": "mm, KiCad front view (x right, y down); the front is Eagle's bottom (the sloth face and the LED ring)",
    "outline": outline,
    "mask": mask,
    "leds": leds,
    "back_logo": logo,
    "back_text": texts,
    "brooch_pads": brooch,
    "maker_back_parts": old,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(art, open(OUT, "w"), indent=0)
xs, ys = [p[0] for p in outline], [p[1] for p in outline]
print(f"board {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm, {len(outline)} outline points; "
      f"mask openings {len(mask)}, logo polygons {len(logo)}, texts {[t['text'] for t in texts]}")
