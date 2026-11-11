#!/usr/bin/env python3
"""Rebuild la-bomba.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/la-bomba/hardware/build_board.py

What it does
  - loads original/BobOmb_PCB.kicad_pcb (KiCad 4) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header (right foot), the four TOPLEDs, the two resistors, the old tracks and the old pour
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - rebuilds the back copper (the 2018 board was one solid ground pour on the back) as the GND net,
    cleared around the new pads and tracks
  - rebuilds the back silkscreen art without ink on the new pads and behind the new labels
  - fills the old header's holes in the front solder-mask art of the right shoe

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).

Why the parts sit where they do (the board is tight: one round body, two eyes, the credit lettering, a coin cell and a
6-pin connector all want the same 44 mm circle):
  - the coin cell only fits in the body, right of the eyes and above the lettering; its closed end points up
  - the connector goes above the cell, under the fuse cap, near the middle left-to-right (the only spot left where it
    is fully on the board); the old spot in the right foot is too narrow for the new connector's body
  - the slide switch sits on the straight outer edge of the right foot, knob pointing right
  - the badge-power track (VSAO) has to cross the LED supply on its way to the connector: it passes UNDER resistor R4
    (between its two pads), the usual single-layer trick, so no via is needed
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "la-bomba"
SRC = os.path.join(HERE, "..", "original", "BobOmb_PCB.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper around other nets
TRACK = 0.30        # default track width (all tracks carry a few mA)
EDGE = 0.28         # copper stops this far short of the board edge
WINDOW = 1.6        # radius kept free of back copper behind each LED so light gets into the board

# ---- placement (centre x, y) ------------------------------------------------------------------
CONN = (150.6, 71.4)        # top of the body, its top-left pin tucked under the fuse cap
BAT = (153.0, 89.0)         # right half of the body, between the eyes and the key; cell bottom stops 0.2 mm above "Made"
BAT_CLOSED = (0.0, -1.0)    # closed end up (toward the connector); the cell slides in and out downward
# LEDs keep their 2018 centres. D1 D2 = near eye, D3 = far eye (white), D4 = spark at the end of the fuse (red).
LEDS = {"D1": (138.049, 88.646), "D2": (138.049, 83.058), "D3": (128.905, 85.852), "D4": (161.163, 55.753)}
ANODE = {                   # where each anode pad goes (the cathode is the other pad, on GND copper)
    "D1": (138.049 - 1.55, 88.646), "D2": (138.049 - 1.55, 83.058),       # near eye: anodes on the left, toward R1/R2
    "D3": (128.905, 85.852 - 1.55),                                         # far eye: upright, anode on top, toward R3
    "D4": (161.163 + 1.55 * math.cos(math.radians(30)), 55.753 + 1.55 * math.sin(math.radians(30))),  # 2018 axis; anode lower right
}
RES = {                     # resistor centre and where its pad 1 (supply side, VLOAD) goes
    "R1": ((133.6, 88.646), (132.775, 88.646)),
    "R2": ((136.5, 79.6), (136.5, 78.775)),
    "R3": ((128.905, 81.3), (128.905, 80.475)),
    "R4": ((160.2, 74.0), (160.2, 74.825)),        # straddles the VSAO track (pad 1 below it, pad 2 above it)
}
CORRIDOR = 77.5             # VLOAD runs left along this line, between the connector's lower pins (77.0) and the clip (78.0)
HUG = 0.25                  # width of the tracks that follow the board edge
LANE1, LANE2 = 0.45, 0.95   # their distance from the edge (centre line): outer and inner lane

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 14360, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("X1", "R1", "R2") or re.fullmatch(r"D[1-4]", ref):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == sorted(["X1", "R1", "R2", "D1", "D2", "D3", "D4"]), _gone
_txt = cut_blocks(_txt, _cut)
# the art on the layers this script rebuilds (front copper, front mask, back silkscreen) is read from the untouched original
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4)
          if any(f"(layer {L})" in _txt[b_ - 40:b_] for L in ("F.Cu", "F.Mask", "B.SilkS"))]
assert len(_polys) == 2 + 10 + 581, f"expected 2 front copper + 10 front mask + 581 back silk art polygons, found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
_frames = stray_frames(_txt, 80)         # the 2018 SVG export's page frame, still on the front silk layer
assert len(_frames) == 1, len(_frames)
_txt = cut_blocks(_txt, _frames)
_tmp = os.path.join(tempfile.mkdtemp(), "BobOmb_PCB.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)


def thin(ps):
    """Drop points that bend the outline by less than 0.01 mm. The 2018 outline and art carry a point every 0.03 mm,
    which makes KiCad's DRC run out of memory on this board; 0.01 mm is far below what a board house can make."""
    ps.SimplifyOutlines(FromMM(0.01))
    return ps


def no_frame(parts):
    """Drop the stray page frame (wider than the 70 mm board) from a list of art polygons."""
    keep = [p for p in parts if bbox_mm(p)[2] - bbox_mm(p)[0] < 80]
    assert len(keep) == len(parts) - 1, "expected exactly one page frame on this layer"
    return keep


_orig = pcbnew.LoadBoard(SRC)
front = pcbnew.SHAPE_POLY_SET()
for p_ in no_frame(footprint_polys(_orig, pcbnew.F_Cu)):
    front.Append(p_)
fmask = pcbnew.SHAPE_POLY_SET()
for p_ in no_frame(footprint_polys(_orig, pcbnew.F_Mask)):
    fmask.Append(p_)
silk_parts = no_frame(footprint_polys(_orig, B_SilkS))
front.Simplify()
fmask.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 14360 short segments; outline.json is the same path as three closed polygons ----
# (the body, and the two holes in the wind-up key). Each loop is its own Edge.Cuts polygon.
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert len(_ol["holes"]) == 2, "La Bomba has two holes, both in the wind-up key"
# The extracted path has a point every 0.03 mm (14073 on the outer loop); dropping points that bend it by less than
# 0.005 mm keeps the shape exactly as far as any router can tell, and keeps KiCad's DRC within memory on the 2x2 panel.
outer = poly(_ol["outer"])
outer.SimplifyOutlines(FromMM(0.005))
holes = [poly(h) for h in _ol["holes"]]
for h in holes:
    h.SimplifyOutlines(FromMM(0.005))
print("outline points after thinning:", [outer.Outline(0).PointCount()] + [h.Outline(0).PointCount() for h in holes])
for loop in [outer] + holes:
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(pcbnew.SHAPE_POLY_SET(loop))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
body = pcbnew.SHAPE_POLY_SET(outer)      # the board itself: outer loop minus the key holes
for h in holes:
    body.BooleanSubtract(h)
# where copper may be. Shrinking a polygon that has holes opens slits in KiCad, so shrink the outer loop and grow
# the holes separately.
inner = grown(outer, -EDGE)
for h in holes:
    inner.BooleanSubtract(grown(h, EDGE))

# ---- the circuit (shared with the schematic generator) ------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p["ref"]: p for p in CIRCUIT["parts"]}
PADNETS = {r: p.get("nets", {}) for r, p in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for r, p in PARTS.items()}
_NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")          # same namespace as tools/gen_schematic.py


def sch_uuid(what):
    return str(uuid.uuid5(_NS, SLUG + ":" + what))


nets = {}
for n in sorted({n for d in PADNETS.values() for n in d.values()}):
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni)
    nets[n] = ni


# ---- footprints ---------------------------------------------------------------------------------
def link(fp, ref):
    """Tie the footprint to its schematic symbol (path, part fields, nets) so KiCad's schematic-parity check passes."""
    _, value, fpid, fields, _, _ = SYMBOLS[PARTS[ref]["symbol"]]
    fp.SetFPID(pcbnew.LIB_ID("sao-plus-plus", fpid.split(":")[1]))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
    fp.SetValue(PARTS[ref].get("value", value))
    for k, v in fields.items():           # the library footprint carries the first part that used it; this board's part wins
        assert fp.HasField(k), f"{ref}: footprint has no {k} field"
        fp.GetField(k).SetText(v)
    for pad in fp.Pads():
        num = pad.GetNumber()
        net = PADNETS[ref].get(num)
        if not net and num in PINNAMES[ref]:
            net = f"unconnected-({ref}-{PINNAMES[ref][num]}-Pad{num})"      # KiCad's name for a pin with a no-connect flag
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def load(ref, pos):
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name} in {LIB}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # the back is busy with art; refs live on the fab layer and in the README
    return fp


def place(ref, pos, want, step=90):
    """Place on the back, then pick the rotation (in `step` degrees) that puts pad `want[0]` at `want[1]`."""
    fp = load(ref, pos)
    best = None
    for k in range(int(round(360 / step))):
        rot = k * step
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber() == want[0]:
                px, py = mm(pad.GetPosition())
                d = math.hypot(px - want[1][0], py - want[1][1])
                if best is None or d < best[0]:
                    best = (d, rot)
    assert best[0] < 0.05, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def padpos(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as the 2018 header
led, res = {}, {}
for ref, (x, y) in LEDS.items():
    led[ref] = place(ref, (x, y), ("2", ANODE[ref]), step=90 if ref != "D4" else 0.5)
for ref, (pos, p1) in RES.items():
    res[ref] = place(ref, pos, ("1", p1))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)             # (rectangles only stay rectangles at right angles, so measure there)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
assert abs(((_closed_dir(_rot) - math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0]))) + 180) % 360 - 180) < 1
bat.SetOrientationDegrees(_rot)
link(bat, "BT1")
# The footprint's silkscreen arrow marks the open side; here the open side faces the maker's lettering, so the arrow
# would be printed across "Made". It goes to the fab layer instead (the line across the closed end stays).
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS and hasattr(g, "GetShape") and g.GetShape() == pcbnew.SHAPE_T_SEGMENT:
        a_, b_ = mm(g.GetStart()), mm(g.GetEnd())
        if min(a_[1], b_[1]) > BAT[1] + 5:
            g.SetLayer(pcbnew.B_Fab)
print("battery clip angle", _rot)


# ---- switch: on the straight outer edge of the right foot, knob pointing out of the board ----------
def edge_run(lo, hi):
    """Outline points between two y values on the right foot's outer edge (x > 162)."""
    return [(x, y) for x, y in _ol["outer"] if lo <= y <= hi and x > 162.0]


_run = edge_run(106.5, 119.0)
_a, _b = _run[0], _run[-1]
if _a[1] > _b[1]:
    _a, _b = _b, _a
_dx, _dy = _b[0] - _a[0], _b[1] - _a[1]
_L = math.hypot(_dx, _dy)
_t = (_dx / _L, _dy / _L)                                # along the edge, top to bottom
_n = (_t[1], -_t[0])                                     # outward normal (points right)
assert _n[0] > 0.9
_dev = max(abs((x - _a[0]) * _n[0] + (y - _a[1]) * _n[1]) for x, y in _run)
print(f"right-foot edge: {_L:.1f} mm long, bulges {_dev:.2f} mm from its chord, outward normal {_n[0]:.3f},{_n[1]:.3f}")
SW_ALONG = 0.45 * _L                                     # where along the chord the switch centre sits
SW_IN = 1.95                                             # chord to switch centre (the chord is inside the bulging edge)
SW = (_a[0] + _t[0] * SW_ALONG - _n[0] * SW_IN, _a[1] + _t[1] * SW_ALONG - _n[1] * SW_IN)
sw = load("SW1", SW)
_want_knob = math.degrees(math.atan2(_n[1], _n[0]))
_best = None
for k in range(720):
    rot = k * 0.5
    sw.SetOrientationDegrees(rot)
    knob = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY)
            and ToMM(g.GetBoundingBox().GetWidth()) < 3.5 and ToMM(g.GetBoundingBox().GetHeight()) < 3.5]
    c = knob[0].GetBoundingBox().GetCenter()
    ang = math.degrees(math.atan2(ToMM(c.y) - SW[1], ToMM(c.x) - SW[0]))
    miss = abs((ang - _want_knob + 180) % 360 - 180)
    if _best is None or miss < _best[0]:
        _best = (miss, rot)
sw.SetOrientationDegrees(_best[1])
# slide the switch along and into the edge: the knob should stick out as far as possible while every pad keeps
# EDGE + 0.05 mm of board around it (the edge bulges, so the pads at the ends of the switch set the limit)
_inner_sw = grown(outer, -(EDGE + 0.05))
_sw_best = None
for _ia in range(0, 21):
    for _ii in range(0, 25):
        along, depth = _L * (0.30 + 0.02 * _ia), 1.6 + 0.05 * _ii
        c = (_a[0] + _t[0] * along - _n[0] * depth, _a[1] + _t[1] * along - _n[1] * depth)
        sw.SetPosition(P(*c))
        ok_ = True
        for pad in sw.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                o_ = pad_poly(pad, B_Cu)
                o_.BooleanSubtract(_inner_sw)
                if o_.OutlineCount():
                    ok_ = False
                    break
        if ok_:
            tip = (c[0] + _n[0] * 3.1, c[1] + _n[1] * 3.1)
            outside = not outer.Contains(P(*tip))
            d_ = min(math.hypot(tip[0] - x, tip[1] - y) for x, y in _run)
            out_ = d_ if outside else -d_
            if _sw_best is None or out_ > _sw_best[0] + 1e-6:
                _sw_best = (out_, c)
            break                                        # deeper only shortens the knob
assert _sw_best and _sw_best[0] > 0.4, f"switch knob would barely reach past the edge: {_sw_best}"
SW = _sw_best[1]
sw.SetPosition(P(*SW))
link(sw, "SW1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
assert s1[1] < s3[1] < s4[1], "expected pin 1 at the top of the foot"     # fixed by the part's handedness
_tip = (SW[0] + _n[0] * 3.1, SW[1] + _n[1] * 3.1)       # knob tip (3.1 mm from the switch centre)
_knob_out = -min(math.hypot(_tip[0] - x, _tip[1] - y) for x, y in _ol["outer"])
print(f"switch at {SW[0]:.2f},{SW[1]:.2f} angle {_best[1]}; knob tip {-_knob_out:.2f} mm past the edge")

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new pad must sit on the board, clear of the edge (and of the key holes)
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(inner)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {EDGE} mm to the board edge"


# ---- routing helpers (back copper only) ---------------------------------------------------------
def route(net, pts, width=TRACK, clear=CLEAR):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear))


_contours = {}


def hug(offset, start, end, keep=lambda p: True, via=None):
    """Points along the board edge at `offset` mm inside it, from the point nearest `start` to the one nearest `end`.

    Walks whichever way round passes nearer `via` (or the shorter way), drops points failing `keep`, and thins the
    rest to >= 0.3 mm spacing. The outer loop is shrunk on its own (it has no holes, so no slits)."""
    if offset not in _contours:
        g = grown(outer, -offset)
        best = max(range(g.OutlineCount()), key=lambda i: g.Outline(i).PointCount())
        o = g.Outline(best)
        _contours[offset] = [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]
    pts = _contours[offset]
    n = len(pts)

    def near(q):
        return min(range(n), key=lambda k: (pts[k][0] - q[0]) ** 2 + (pts[k][1] - q[1]) ** 2)
    i, j = near(start), near(end)
    fwd = [pts[(i + k) % n] for k in range((j - i) % n + 1)]
    bwd = [pts[(i - k) % n] for k in range((i - j) % n + 1)]
    if via is not None:
        dv = [min(math.hypot(x - via[0], y - via[1]) for x, y in w) for w in (fwd, bwd)]
        run = fwd if dv[0] < dv[1] else bwd
    else:
        run = fwd if len(fwd) < len(bwd) else bwd
    run = [p for p in run if keep(p)]
    out = [run[0]]
    for p in run[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= 0.3:
            out.append(p)
    if out[-1] != run[-1]:
        out.append(run[-1])
    return [(round(x, 4), round(y, 4)) for x, y in out]


def inward(p, d):
    """A point d mm in from switch pad p, toward the inside of the foot."""
    return (round(p[0] - _n[0] * d, 4), round(p[1] - _n[1] * d, 4))


j1 = padpos(conn, "1")
rp1 = {r: padpos(fp, "1") for r, fp in res.items()}
rp2 = {r: padpos(fp, "2") for r, fp in res.items()}
an = {r: padpos(fp, "2") for r, fp in led.items()}

# each LED anode: resistor pad 2 -> LED pad 2
route("LED1_A", [rp2["R1"], an["D1"]])
route("LED2_A", [rp2["R2"], an["D2"]])
route("LED3_A", [rp2["R3"], an["D3"]])

# VSAO (badge 3.3 V): switch pin 1 -> up the outside of the right channel (outer lane) -> under R4 -> through the
# gap between the connector's two rows of pins -> connector pin 1 from below.
_keep_body = lambda p: p[0] < 167.0                      # drop the part of the edge that runs round the wind-up key
v_sao = hug(LANE1, (161.1, 103.4), (163.0, 74.2), keep=_keep_body, via=(167.0, 95.0))
route("VSAO", [s1, inward(s1, 0.9), (161.85, 105.0)] + v_sao + [(163.0, 74.0), (rp1["R4"][0] - 1.6, 74.0),
               (CONN[0] + 4.1, CONN[1]), (j1[0] + 1.25, CONN[1]), (j1[0], j1[1] + 1.8)], width=HUG, clear=0.25)

# VLOAD (switched supply): switch pin 3 -> up the inner lane -> along under the connector (CORRIDOR) -> the eye resistors,
# with a stub up to R4 for the spark
v_load = hug(LANE2, (160.6, 103.8), (164.6, 78.0), keep=lambda p: p[0] < 166.5, via=(166.5, 95.0))
route("VLOAD", [s3, inward(s3, 1.5), (160.55, 106.0)] + v_load + [(v_load[-1][0] - 0.5, CORRIDOR), (rp1["R3"][0], CORRIDOR), rp1["R3"]],
      width=HUG, clear=0.25)
route("VLOAD", [(rp1["R4"][0], CORRIDOR), rp1["R4"]], width=HUG, clear=0.25)
route("VLOAD", [(rp1["R2"][0], CORRIDOR), rp1["R2"]], width=HUG, clear=0.25)
route("VLOAD", [(rp1["R1"][0], CORRIDOR), rp1["R1"]], width=HUG, clear=0.25)

# LED4_A: R4 pad 2 -> past the fuse cap's notch -> up the right side of the fuse -> spark LED D4.
# Ground reaches the spark along the left side of the fuse, from the cap above the connector.
v_fuse = hug(LANE1, (155.0, 63.2), (159.0, 59.4), via=(156.5, 61.0))
route("LED4_A", [rp2["R4"], (rp2["R4"][0], 72.6), (159.0, 70.6), (157.0, 68.9), (155.4, 65.6)] + v_fuse + [(160.6, 58.2), an["D4"]],
      width=HUG, clear=0.25)

# VBAT (coin cell +): switch pin 4 -> round the top of the slot between the right foot and the body -> along the bottom
# of the body under the lettering -> round the left foot's slot -> up the left side -> under the near eye -> clip pad
v_bot = hug(LANE1, (158.6, 107.5), (136.3, 106.0), via=(157.2, 104.9))
v_left = hug(LANE1, (131.4, 102.2), (126.9, 96.6), via=(129.0, 100.0))
bt_l = padpos(bat, "1", pick=lambda p: p[0])            # clip pad on the left (toward the eyes)
bt_r = padpos(bat, "1", pick=lambda p: -p[0])
route("VBAT", [s4, inward(s4, 2.1), (158.9, 108.5)] + v_bot + [(134.3, 104.1), (132.4, 102.7)] + v_left +
      [(141.6, 96.6), (bt_l[0], 95.6), bt_l], width=HUG, clear=0.25)
# the clip itself joins its two pads; this link round the closed end makes the board agree without relying on it
_a0 = math.degrees(math.atan2(bt_l[1] - BAT[1], bt_l[0] - BAT[0]))
_r = math.hypot(bt_l[0] - BAT[0], bt_l[1] - BAT[1])
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 + d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 + d)), 4))
        for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_l] + _arc + [bt_r])

# ---- GND copper: the 2018 back was one solid ground pour; rebuilt here, cleared around everything that is not GND ----
art = pcbnew.SHAPE_POLY_SET(inner)
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)                          # solid copper under the cell so the bare cell pad is whole
art.BooleanAdd(disc)

cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            continue
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for x, y in LEDS.values():                               # light path behind the eyes and the spark
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# ---- the maker's lettering: no track, pad or part may sit on it ------------------------------------
# On the back the credit is drawn as gaps in a white silkscreen band ("Made By TwinkleTwinkie / DEF CON 26 Add-on /
# @MrTwinkleTwink"). These boxes hold the three lines; the letters themselves are the un-inked parts inside them.
ROWS = [(130.8, 98.9, 161.0, 101.2), (134.7, 101.4, 158.3, 103.5), (137.6, 103.7, 153.8, 105.7)]
silk_all = pcbnew.SHAPE_POLY_SET()
for p_ in silk_parts:
    silk_all.Append(p_)
silk_all.Simplify()
letters = pcbnew.SHAPE_POLY_SET()
for x0, y0, x1, y1 in ROWS:
    letters.BooleanAdd(poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
letters.BooleanSubtract(silk_all)                        # what is left in the boxes is the lettering itself
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(letters)
assert area_mm2(_hit) < 0.01, f"a track channel overlaps the maker's lettering by {area_mm2(_hit):.3f} mm2"
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        cy = pcbnew.SHAPE_POLY_SET(fp.GetCourtyard(pcbnew.B_CrtYd))
        cy.BooleanIntersection(letters)
        assert area_mm2(cy) < 0.01, f"{fp.GetReference()} sits on the maker's lettering"
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)                         # the CR2032 itself (20 mm) must not hide any letter either
_cell.BooleanIntersection(letters)
assert area_mm2(_cell) < 0.01, f"the coin cell covers {area_mm2(_cell):.2f} mm2 of the lettering"

# ---- panel tabs: the mouse-bite holes sit on the edge and reach 0.25 mm in, so copper stays 0.6 mm back there ----
_panel = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))
tabcut = pcbnew.SHAPE_POLY_SET()
_band = pcbnew.SHAPE_POLY_SET(outer)
_band.BooleanSubtract(grown(outer, -0.6))
for tab in _panel["tabs"]:
    ex, ey = min(_ol["outer"], key=lambda q: (q[0] - tab["near"][0]) ** 2 + (q[1] - tab["near"][1]) ** 2)
    win = pcbnew.SHAPE_POLY_SET()
    add_circle(win, P(ex, ey), tab["width"] / 2 + 1.0 if "width" in tab else _panel["tab_width"] / 2 + 1.0)
    _hit = pcbnew.SHAPE_POLY_SET(channels)
    _hit.BooleanIntersection(win)
    assert area_mm2(_hit) < 0.001, f"a track runs under the panel tab at {tab['why']}"
    win.BooleanIntersection(_band)
    tabcut.BooleanAdd(win)
art.BooleanSubtract(tabcut)
art.Simplify()

# every separate piece becomes its own shape: pieces touching a GND pad carry the GND net, the rest stay plain art
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = n_art = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    touches = area_mm2(both) > 0.01
    add_filled(board, thin(piece), B_Cu, nets["GND"] if touches else None)
    n_gnd += touches
    n_art += not touches
    if not touches and area_mm2(piece) > 1:
        print("  plain art piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain art", n_art)
# every GND pad must be on one single GND piece, or a light would have no return path
_gpieces = [i for i in range(art.OutlineCount())]
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            hits = 0
            for i in _gpieces:
                both = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
                both.BooleanIntersection(pad_poly(pad, B_Cu))
                hits += area_mm2(both) > 0.01
            assert hits >= 1, f"{fp.GetReference()} pad {pad.GetNumber()} touches no ground copper"

# ---- front copper art: same shapes as 2018 (the old header sat in a bare shoe, so there is nothing to fill) ----
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(pegs)
front.BooleanSubtract(tabcut)
front.BooleanIntersection(inner)
front.Simplify()
add_filled(board, thin(front), pcbnew.F_Cu)

# ---- front solder-mask art: the right shoe's opening had round cut-outs for the old header's pads; fill them ----
mgaps = pcbnew.SHAPE_POLY_SET(body)
mgaps.BooleanSubtract(fmask)
mgaps.BooleanIntersection(poly([(155.0, 112.0), (162.5, 112.0), (162.5, 120.0), (155.0, 120.0)]))
mgaps.Simplify()
_filled = []
for i in range(mgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(mgaps.Polygon(i))
    x0, y0, x1, y1 = bbox_mm(one)
    if x0 > 155.2 and x1 < 162.3 and y0 > 112.2 and y1 < 119.8:   # fully enclosed by the shoe's opening
        fmask.BooleanAdd(one)
        _filled.append(round(area_mm2(one), 2))
assert 1 <= len(_filled) <= 5 and 15 < sum(_filled) < 40, f"expected the old pad cut-outs (they overlap into one blob), got {_filled}"
print("filled old header cut-outs in the front mask, mm2:", _filled)
fmask.BooleanIntersection(body)
fmask.Simplify()
add_filled(board, thin(fmask), pcbnew.F_Mask)

# ---- back silkscreen labels (the art is cleared behind each one so it reads on dark mask) -----------
_lab = (SW[0] - _n[0] * 4.6, SW[1] - _n[1] * 4.6)      # a line parallel to the switch, inside the pins
_ang = -math.degrees(math.atan2(_t[1], _t[0])) + 180    # text reads along the edge
LABELS = [("SAO", _lab[0] + _t[0] * -3.3, _lab[1] + _t[1] * -3.3, 0.8, _ang),
          ("OFF", _lab[0], _lab[1], 0.8, _ang),
          ("BAT", _lab[0] + _t[0] * 3.3, _lab[1] + _t[1] * 3.3, 0.8, _ang),
          ("CR2032 + SIDE UP", 165.25, 86.0, 0.8, 90),
          ("SAO++ rA", 137.0, 70.8, 0.9, 0),
          ("1", j1[0] - 1.6, j1[1] + 0.6, 0.9, 0)]
behind = pcbnew.SHAPE_POLY_SET()
for txt, x, y, size, rot in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)
    bb = t.GetBoundingBox()
    bb.Inflate(FromMM(0.3))
    tp = poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
              (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))])
    _l = pcbnew.SHAPE_POLY_SET(tp)
    _l.BooleanIntersection(letters)
    assert area_mm2(_l) < 0.01, f"label {txt} would cover the maker's lettering"
    behind.Append(tp)
behind.Simplify()

# ---- back silkscreen art: 2018 shapes, minus ink on the new pads, behind the labels and in the LED light windows ----
silk = pcbnew.SHAPE_POLY_SET(silk_all)
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.2))
for x, y in LEDS.values():
    add_circle(bare, P(x, y), 1.15)
bare.Simplify()
_before = area_mm2(silk)
silk.BooleanSubtract(bare)
silk.BooleanSubtract(behind)
silk.BooleanIntersection(body)
silk.Simplify()
print("back silk ink removed for pads, labels and light windows, mm2:", round(_before - area_mm2(silk), 1))
_l = pcbnew.SHAPE_POLY_SET(letters)                     # the lettering must be exactly as before: no new gaps inside its boxes
_rows = pcbnew.SHAPE_POLY_SET()
for x0, y0, x1, y1 in ROWS:
    _rows.BooleanAdd(poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
_now = pcbnew.SHAPE_POLY_SET(_rows)
_now.BooleanSubtract(silk)
_now.BooleanSubtract(letters)
assert area_mm2(_now) < 0.01, f"back silk around the lettering changed by {area_mm2(_now):.3f} mm2"
add_filled(board, thin(silk), B_SilkS)

# nothing may stick out of the board on any layer (the 2018 SVG frames are gone)
_out = pcbnew.SHAPE_POLY_SET()
for d in board.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts and hasattr(d, "GetShape") and d.GetShape() == pcbnew.SHAPE_T_POLY:
        _out.Append(pcbnew.SHAPE_POLY_SET(d.GetPolyShape()))
for fp in board.GetFootprints():
    if fp.GetReference() not in NEW:
        for it in fp.GraphicalItems():
            if hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY:
                _out.Append(pcbnew.SHAPE_POLY_SET(it.GetPolyShape()))
_out.Simplify()
_out.BooleanSubtract(grown(outer, 0.05))
assert area_mm2(_out) < 0.01, f"{area_mm2(_out):.2f} mm2 of art lies outside the board outline"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
