#!/usr/bin/env python3
"""Read the maker's Eagle board (original/eggplant/eggplant.brd, Eagle XML) and write hardware/art.json.

Run with the system Python, from the repo root (no KiCad needed):
  python3 boards/eggplant/hardware/extract_art.py

What the Eagle file holds (Eagle layer numbers), and where it goes
  20  Dimension   203 straight lines, one closed loop                         -> "outline"
  1   Top copper  net N$2: stem and calyx (exposed: tStop opening over it)    -> "front_copper" (art, no net)
                  net GND pour: the body, cut by the tRestrict areas (41)    -> "front_copper" (art, no net)
  41  tRestrict   the light stripe down the left of the body and a sliver by the calyx: no copper there
  29  tStop       mask opening over the stem and calyx                       -> "front_mask"
  25  tNames      two filled shapes: calyx leaf and the highlight on the body -> "front_silk"
  16/42/30/26     the same art again on the BOTTOM (net N$3 stem, GND pour cut by bRestrict, bStop, bNames)
                  -> "back_*": the eggplant is two-sided. Its parts sat on the bottom too, as SAO++ does.
  26  bNames      also the maker's lettering, as text: the DC Darknet credit, "krux was here", a base64 joke,
                  and 16 short 45-degree strokes beside the joke                 -> "back_texts", "back_strokes"
  elements        LED1..LED5 (bicolour 0805, on the bottom)                      -> "leds"

Eagle draws the board seen from the top with y up. art.json is KiCad's front view (mm, x right, y down), board's
left edge at x = 10 and top at y = 10. The top is the front, so nothing is mirrored; the back layers keep the same
coordinates (KiCad draws back layers in front-view coordinates too).
"""
import json
import math
import os
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "eggplant", "eggplant.brd")
OUT = os.path.join(HERE, "art.json")

root = ET.parse(SRC).getroot()
plain = root.find(".//plain")
signals = {s.get("name"): s for s in root.find(".//signals")}

segs = [(float(w.get("x1")), float(w.get("y1")), float(w.get("x2")), float(w.get("y2")))
        for w in plain.findall("wire") if w.get("layer") == "20"]
assert all(w.get("curve") is None for w in plain.findall("wire")), "curved lines are not handled"
loop = [segs[0][:2], segs[0][2:]]
rest = segs[1:]
while rest:
    end = loop[-1]
    for i, s in enumerate(rest):
        if math.dist(s[:2], end) < 1e-3:
            loop.append(s[2:]); rest.pop(i); break
        if math.dist(s[2:], end) < 1e-3:
            loop.append(s[:2]); rest.pop(i); break
    else:
        raise SystemExit("outline does not close")
assert math.dist(loop[0], loop[-1]) < 1e-6
loop.pop()
X0 = min(p[0] for p in loop)
Y1 = max(p[1] for p in loop)


def T(x, y):
    return [round(x - X0 + 10.0, 4), round(Y1 - y + 10.0, 4)]


def verts(p):
    assert all(v.get("curve") is None for v in p.findall("vertex")), "curved polygon edges are not handled"
    return [T(float(v.get("x")), float(v.get("y"))) for v in p.findall("vertex")]


def plain_polys(layer):
    return [verts(p) for p in plain.findall("polygon") if p.get("layer") == layer]


def sig_polys(net, layer):
    return [verts(p) for p in signals[net].findall("polygon") if p.get("layer") == layer]


art = {
    "source": "original/eggplant/eggplant.brd (Eagle XML), converted by hardware/extract_art.py",
    "units": "mm, KiCad front view (x right, y down); front = the maker's top side",
    "outline": [T(*p) for p in loop],
    "front": {"stem": sig_polys("N$2", "1"), "body": sig_polys("GND", "1"), "restrict": plain_polys("41"),
              "mask": plain_polys("29"), "silk": plain_polys("25")},
    "back": {"stem": sig_polys("N$3", "16"), "body": sig_polys("GND", "16"), "restrict": plain_polys("42"),
             "mask": plain_polys("30"), "silk": plain_polys("26")},
    "back_texts": [dict(text=t.text, at=T(float(t.get("x")), float(t.get("y"))), size=float(t.get("size")),
                        ratio=float(t.get("ratio") or 8), rot=t.get("rot"), align=t.get("align") or "bottom-left",
                        font=t.get("font"))
                   for t in plain.findall("text") if t.get("layer") == "26"],
    "back_strokes": [[T(float(w.get("x1")), float(w.get("y1"))), T(float(w.get("x2")), float(w.get("y2"))),
                      float(w.get("width"))] for w in plain.findall("wire") if w.get("layer") == "26"],
    "leds": {e.get("name"): T(float(e.get("x")), float(e.get("y")))
             for e in root.findall(".//elements/element") if e.get("name").startswith("LED")},
    "old_header": T(*[float(e.get(k)) for e in root.findall(".//elements/element") if e.get("name") == "U$1" for k in "xy"]),
}
json.dump(art, open(OUT, "w"), indent=0)
xs = [p[0] for p in art["outline"]]
ys = [p[1] for p in art["outline"]]
print(f"board {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm, outline {len(xs)} points")
print({side: {k: len(v) for k, v in art[side].items()} for side in ("front", "back")})
print("texts", [t["text"] for t in art["back_texts"]], "strokes", len(art["back_strokes"]))
print("leds", art["leds"], "old header", art["old_header"])
