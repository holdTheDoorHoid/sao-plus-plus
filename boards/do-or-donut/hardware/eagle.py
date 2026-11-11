"""Read the maker's Eagle board (original/donut.brd, Eagle 7.6 XML) for build_board.py and the helper scripts.

Plain Python (no KiCad): returns positions in Eagle's own frame (mm, y up). build_board.py converts to KiCad.
"""
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

BRD = Path(__file__).resolve().parent.parent / "original" / "donut.brd"


def rot_of(s):
    """Eagle rotation string ('R90', 'MR270', ...) -> (mirrored, degrees counter-clockwise)."""
    m = re.match(r"S?(M?)R([0-9.]+)", s or "R0")
    return bool(m.group(1)), float(m.group(2))


def place(x, y, mir, ang, px, py):
    """A package point (px, py) on an element at (x, y): Eagle rotates first, then mirrors (x -> -x)."""
    a = math.radians(ang)
    qx, qy = px * math.cos(a) - py * math.sin(a), px * math.sin(a) + py * math.cos(a)
    if mir:
        qx = -qx
    return x + qx, y + qy


def arc_pts(x1, y1, x2, y2, ang, step_deg=1.0):
    """Points along an Eagle arc from (x1, y1) to (x2, y2) sweeping `ang` degrees (positive = counter-clockwise),
    excluding the start, including the end."""
    a = math.radians(ang)
    dx, dy = x2 - x1, y2 - y1
    c = math.hypot(dx, dy)
    r = c / 2 / math.sin(abs(a) / 2)
    h = math.sqrt(max(r * r - (c / 2) ** 2, 0.0))
    nx, ny = -dy / c, dx / c
    s = 1 if (ang > 0) == (abs(ang) < 180) else -1
    cx, cy = (x1 + x2) / 2 + s * nx * h, (y1 + y2) / 2 + s * ny * h
    a0 = math.atan2(y1 - cy, x1 - cx)
    n = max(2, int(math.ceil(abs(ang) / step_deg)))
    pts = [(cx + r * math.cos(a0 + a * k / n), cy + r * math.sin(a0 + a * k / n)) for k in range(1, n)]
    return pts + [(x2, y2)]


def polygon_pts(vertices, step_deg=1.0):
    """Eagle <polygon> vertices [(x, y, curve or None)] -> closed point list."""
    out = []
    for i, (x, y, cv) in enumerate(vertices):
        out.append((x, y))
        nx, ny, _ = vertices[(i + 1) % len(vertices)]
        if cv and float(cv) != 0:
            out += arc_pts(x, y, nx, ny, float(cv), step_deg)[:-1]
    return out


def chain_wires(wires, step_deg=0.5):
    """Join outline wires [(x1, y1, x2, y2, curve)] into closed loops of points."""
    segs = []
    for x1, y1, x2, y2, cv in wires:
        pts = [(x1, y1)] + (arc_pts(x1, y1, x2, y2, cv, step_deg) if cv else [(x2, y2)])
        segs.append(pts)
    loops = []
    while segs:
        loop = segs.pop(0)
        while True:
            end = loop[-1]
            if math.hypot(end[0] - loop[0][0], end[1] - loop[0][1]) < 1e-3 and len(loop) > 2:
                loops.append(loop[:-1])
                break
            for i, s in enumerate(segs):
                if math.hypot(s[0][0] - end[0], s[0][1] - end[1]) < 1e-3:
                    loop += s[1:]
                    segs.pop(i)
                    break
                if math.hypot(s[-1][0] - end[0], s[-1][1] - end[1]) < 1e-3:
                    loop += s[::-1][1:]
                    segs.pop(i)
                    break
            else:
                raise ValueError("outline does not close")
    return loops


def load():
    root = ET.parse(BRD).getroot()
    b = root.find("drawing/board")
    packages = {}
    for lib in b.find("libraries"):
        for p in lib.find("packages"):
            packages[(lib.get("name"), p.get("name"))] = p
    elements = {}
    for e in b.find("elements"):
        mir, ang = rot_of(e.get("rot"))
        x, y = float(e.get("x")), float(e.get("y"))
        pkg = packages[(e.get("library"), e.get("package"))]
        pads = {}
        for s in pkg:
            if s.tag in ("smd", "pad"):
                px, py = place(x, y, mir, ang, float(s.get("x")), float(s.get("y")))
                pads[s.get("name")] = (px, py)
        polys = []
        for s in pkg:
            if s.tag == "polygon":
                vs = [(float(v.get("x")), float(v.get("y")), v.get("curve")) for v in s]
                polys.append((s.get("layer"), float(s.get("width")),
                              [place(x, y, mir, ang, px, py) for px, py in polygon_pts(vs, 3.0)]))
        elements[e.get("name")] = dict(x=x, y=y, mirrored=mir, angle=ang, package=e.get("package"), pads=pads, polygons=polys)
    signals = {}
    for s in b.find("signals"):
        signals[s.get("name")] = dict(
            wires=[(float(w.get("x1")), float(w.get("y1")), float(w.get("x2")), float(w.get("y2")), float(w.get("width")), w.get("layer"))
                   for w in s.findall("wire")],
            vias=[(float(v.get("x")), float(v.get("y")), float(v.get("drill"))) for v in s.findall("via")],
            pads=[(c.get("element"), c.get("pad")) for c in s.findall("contactref")])
    plain = b.find("plain")
    outline = [(float(w.get("x1")), float(w.get("y1")), float(w.get("x2")), float(w.get("y2")), float(w.get("curve") or 0))
               for w in plain.findall("wire") if w.get("layer") == "20"]
    stop_polys = [polygon_pts([(float(v.get("x")), float(v.get("y")), v.get("curve")) for v in p], 1.0)
                  for p in plain.findall("polygon") if p.get("layer") == "29"]
    texts = [dict(text=t.text, x=float(t.get("x")), y=float(t.get("y")), size=float(t.get("size")), ratio=float(t.get("ratio") or 8),
                  layer=t.get("layer"), rot=t.get("rot"), align=t.get("align")) for t in plain.findall("text")]
    return dict(elements=elements, signals=signals, outline=outline, stop_polys=stop_polys, texts=texts)
