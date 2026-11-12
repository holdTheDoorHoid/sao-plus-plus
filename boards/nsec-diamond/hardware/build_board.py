#!/usr/bin/env python3
"""Build nsec-diamond.kicad_pcb: NorthSec's 2025 Sao_Diamond circuit on SAO++'s own gem drawing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-diamond/hardware/build_board.py

What the original is (read from the files; the maker left no description):
  - a 41.0 x 35.4 mm diamond-shaped board, white silkscreen facets on the front, no copper art.
  - two 3 mm through-hole LEDs standing on the FRONT where facets meet, two 330 ohm through-hole resistors on the
    back, an SMD 2x3 SAO connector wired to 3.3 V and GND only. No battery, no switch.
  - back silkscreen: the "nsec 2025" logo and a blank 5 x 5 mm white box.
  - its outline and facets were traced by the maker from a third-party picture. NONE of that geometry is used here or
    kept in this repository (see original/README.md and the art_note in board.yml).

What this script does
  - draws SAO++'s own gem from the numbers in GEM below: a brilliant-cut stone seen from the side, with a flat table,
    a crown of seven triangles, a girdle band and a four-facet pavilion running down to the point (culet). 52 x 46 mm.
    The same drawing is written to art/gem.svg.
  - front: the fifteen facets in white silkscreen, 0.6 mm apart, with a 3.2 mm round window left clear over each LED
    and a 1.5 mm clear spot round each of the two switch-peg holes. No copper on the front.
  - back: SAO connector top centre (key up); white through-board LEDs D1 / D2 on the girdle where five facet lines
    meet, each with its own 1.3 k resistor; CR2032 clip in the pavilion (closed end up, the cell slides in from the
    point); the SAO / OFF / BAT switch on the right crown edge (front view). Routed on the back only: no vias.
  - back silkscreen: the maker's logo at 0.75 size in the left crown corner (front view), the maker's 5 x 5 mm box,
    and the SAO++ labels.
  - back copper: GND everywhere, 0.55 mm back from the edge, cleared around everything that is not GND and behind
    each LED.

Local coordinates (u, v) are millimetres from the middle of the girdle, front view (u right, v down); board
coordinates add OFFSET.
"""
import json
import math
import os
import re
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly,  # noqa: E402
                         footprint_polys)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "nsec-diamond"
SRC = os.path.join(HERE, "..", "original", "Sao_Diamond", "Sao_Diamond.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

OFFSET = (30.0, 18.0)    # where the middle of the girdle sits on the board
GAP = 0.6           # dark line between two facets (each facet is drawn GAP / 2 inside its own outline)
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40
THIN = 0.30
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25
WINDOW = 1.7        # radius kept free of back copper behind each LED
SILK_WINDOW = 1.6   # radius kept free of front silkscreen over each LED (the maker's 3 mm LED covered about this)
LOGO_SCALE = 0.75   # the maker's logo is drawn this much smaller, to fit the crown corner


def A(u, v):
    """local -> board coordinates"""
    return (round(OFFSET[0] + u, 4), round(OFFSET[1] + v, 4))


# ---- the gem: SAO++'s own drawing, from these numbers only (local coordinates) ----------------------
GEM = {"table": 14.0,      # half-width of the flat top (the table is 54 % of the stone's width, as on a brilliant cut)
       "crown": 12.0,      # height of the crown above the girdle band
       "girdle": 26.0,     # half-width at the girdle
       "band": 1.0,        # half-height of the girdle band
       "pavilion": 32.0,   # depth from the girdle band down to the point
       "junction": 10.5}   # where the inner facet lines meet the girdle, left and right of the middle (the LED spots)
_t, _g, _b, _j = GEM["table"], GEM["girdle"], GEM["band"], GEM["junction"]
_top, _tip = -_b - GEM["crown"], _b + GEM["pavilion"]
_T = [(-_t, _top), (-_t / 3, _top), (_t / 3, _top), (_t, _top)]                 # points along the table edge
_G = [(-_g, -_b), (-_j, -_b), (0.0, -_b), (_j, -_b), (_g, -_b)]                 # points along the top of the girdle band
_P = [(u, _b) for u, _ in _G]                                                  # ... and along its bottom
_C = (0.0, _tip)                                                               # the point (culet)
GEM_OUTLINE = [_T[0], _T[3], _G[4], _P[4], _C, _P[0], _G[0]]
GEM_FACETS = ([[_G[i], _T[i], _G[i + 1]] for i in range(4)]                     # crown: four triangles standing on the girdle
              + [[_T[i], _T[i + 1], _G[i + 1]] for i in range(3)]              # ... and three hanging from the table
              + [[_G[i], _G[i + 1], _P[i + 1], _P[i]] for i in range(4)]       # girdle band, in four pieces
              + [[_P[i], _P[i + 1], _C] for i in range(4)])                    # pavilion: four facets down to the point

# ---- placement (local coordinates) ------------------------------------------------------------------
LEDS = {"D1": (A(-_j, 0.0), -1), "D2": (A(_j, 0.0), +1)}   # on the girdle band, where five facet lines meet; anode pad outward
CONN = A(0.0, _top + 3.0 + 4.45)   # plastic body 3.0 mm below the table edge, key slot up
BAT = A(0.0, 13.8)           # cell 2.1 mm inside both pavilion edges; 1.6 mm of board (for ground copper) left outside
                             # each solder tab; clip's closed end 2.75 mm below the connector pads
BAT_CLOSED = (0.0, -1.0)     # closed end up; the cell slides in over the bottom tip
R1_AT = A(-13.8, 0.0)        # upright, left of D1
R2_AT = A(14.9, 0.0)         # flat, right of D2
BOX_AT = A(-17.6, 4.4)       # the maker's blank 5 x 5 mm white box, in the pavilion's left corner
LOGO_AT = A(-13.6, -4.9)     # centre of the maker's logo, left crown corner in front view
ROW = 1.9                    # v of the switched-supply track that crosses under both LEDs (outside their light windows)

# ---- the maker's art, read from the original ---------------------------------------------------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    for m in re.finditer(r"\n\t\(" + opener + r"[ \n]", txt):
        i = m.start() + 2
        depth = 0
        for j in range(i, len(txt)):
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    yield txt[i:j + 1]
                    break


_rect = [b for b in tblocks(_txt, "gr_rect") if '(layer "B.SilkS")' in b]
assert len(_rect) == 1 and "(start 162.6 47.5)" in _rect[0] and "(end 167.6 52.5)" in _rect[0]      # the 5 x 5 mm box

OUTLINE = [A(u, v) for u, v in GEM_OUTLINE]
json.dump({"outer": [list(p) for p in OUTLINE], "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
body = poly(OUTLINE)
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's board: 41.0 x 35.4)")
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)

_orig = pcbnew.LoadBoard(SRC)
_logo_fp = [f for f in _orig.GetFootprints() if "nsec-2025" in f.GetFPIDAsString()]
assert len(_logo_fp) == 1
LOGO_POLYS = []
for it in _logo_fp[0].GraphicalItems():
    if it.GetLayer() == pcbnew.B_SilkS and hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY:
        ol = it.GetPolyShape().Outline(0)
        assert it.GetPolyShape().OutlineCount() == 1 and it.GetPolyShape().HoleCount(0) == 0
        LOGO_POLYS.append([(ToMM(ol.CPoint(n).x), ToMM(ol.CPoint(n).y)) for n in range(ol.PointCount())])
_lt = [it for it in _logo_fp[0].GraphicalItems() if isinstance(it, pcbnew.PCB_TEXT) and it.GetLayer() == pcbnew.B_SilkS]
assert len(LOGO_POLYS) == 2 and len(_lt) == 1 and _lt[0].GetText() == "2025"
_lt = _lt[0]
_tb = _lt.GetBoundingBox()
_lx = [x for pl in LOGO_POLYS for x, _ in pl] + [ToMM(_tb.GetLeft()), ToMM(_tb.GetRight())]
_ly = [y for pl in LOGO_POLYS for _, y in pl] + [ToMM(_tb.GetTop()), ToMM(_tb.GetBottom())]
_lc = ((min(_lx) + max(_lx)) / 2, (min(_ly) + max(_ly)) / 2)


def LG(x, y):
    return (LOGO_AT[0] + (x - _lc[0]) * LOGO_SCALE, LOGO_AT[1] + (y - _lc[1]) * LOGO_SCALE)


LOGO_BOX = LG(min(_lx), min(_ly)) + LG(max(_lx), max(_ly))
print("logo: maker's %.1f x %.1f mm, here %.1f x %.1f mm" % (max(_lx) - min(_lx), max(_ly) - min(_ly),
                                                             LOGO_BOX[2] - LOGO_BOX[0], LOGO_BOX[3] - LOGO_BOX[1]))

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(OUTLINE))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
TRACKS = []

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
    for k, v in fields.items():
        assert fp.HasField(k), f"{ref}: footprint has no {k} field"
        fp.GetField(k).SetText(v)
    for pad in fp.Pads():
        num = pad.GetNumber()
        net = PADNETS[ref].get(num)
        if not net and num in PINNAMES[ref]:
            net = f"unconnected-({ref}-{PINNAMES[ref][num]}-Pad{num})"
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def load(ref, pos):
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    return fp


def place(ref, pos, want):
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    fp = load(ref, pos)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber() == want[0]:
                px, py = mm(pad.GetPosition())
                d = abs(px - want[1][0]) + abs(py - want[1][1])
                if best is None or d < best[0]:
                    best = (d, rot)
    assert best[0] < 0.05, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def padpos(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
led, res = {}, {}
for ref, ((x, y), s) in LEDS.items():
    led[ref] = place(ref, (x, y), ("2", (x + s * 1.55, y)))
res["R1"] = place("R1", R1_AT, ("1", (R1_AT[0], R1_AT[1] + 0.825)))     # supply pad at the bottom
res["R2"] = place("R2", R2_AT, ("1", (R2_AT[0] + 0.825, R2_AT[1])))     # supply pad on the right

# switch: on the right crown edge (front view), knob pointing straight out of it. A part on the back is
# mirrored, so on this edge the badge contact (pin 1) lands at the top end, next to the connector's supply pin, and the
# cell contact (pin 4) at the lower end, toward the cell. On the upper-left edge they would land the wrong way round.
_ea, _eb = OUTLINE[1], OUTLINE[2]                       # top-right corner -> right corner
_el = math.hypot(_eb[0] - _ea[0], _eb[1] - _ea[1])
_ed = ((_eb[0] - _ea[0]) / _el, (_eb[1] - _ea[1]) / _el)
KN = (_ed[1], -_ed[0])                                  # outward normal: the knob direction
assert KN[0] > 0 and KN[1] < 0
SW_IN = 1.83 + PAD_EDGE + 0.05                            # outer solder tabs PAD_EDGE inside the edge
SW = ((_ea[0] + _eb[0]) / 2 - KN[0] * SW_IN, (_ea[1] + _eb[1]) / 2 - KN[1] * SW_IN)
sw = load("SW1", SW)


def _knob_dir():
    pins = [mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber() in ("1", "2", "3", "4")]
    cx, cy = sum(p[0] for p in pins) / 4, sum(p[1] for p in pins) / 4
    d = math.hypot(SW[0] - cx, SW[1] - cy)
    return ((SW[0] - cx) / d, (SW[1] - cy) / d)


_want = math.degrees(math.atan2(KN[1], KN[0]))
_best = None
for _k in range(3600):
    sw.SetOrientationDegrees(_k / 10.0)
    _kd = _knob_dir()
    _dot = _kd[0] * KN[0] + _kd[1] * KN[1]
    if _best is None or _dot > _best[0]:
        _best = (_dot, _k / 10.0)
sw.SetOrientationDegrees(_best[1])
assert _best[0] > 0.99999, _best
link(sw, "SW1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
assert s1[1] < s4[1], "badge contact is not at the top end of the switch"
KNOB_TIP = (SW[0] + KN[0] * 3.1, SW[1] + KN[1] * 3.1)
print("switch at (%.2f, %.2f), angle %.1f; knob tip %.2f mm past the edge" % (SW[0], SW[1], _best[1], 3.1 - SW_IN))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
link(bat, "BT1")
_sb = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
STRAP = (ToMM(_sb.GetLeft()), ToMM(_sb.GetRight()), ToMM(_sb.GetTop()), ToMM(_sb.GetBottom()))
print("battery clip angle", _rot, "; clip body x %.2f..%.2f y %.2f..%.2f" % STRAP)
assert STRAP[2] < BAT[1] - 10.9, "clip's closed end is not up"
for g in bat.GraphicalItems():          # the clip's own arrow and '+' move to the fab layer; the board has its own labels
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

for fp in board.GetFootprints():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
# the cell itself (20 mm) stays inside the outline
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_cell.BooleanSubtract(grown(body, -0.5))
assert _cell.OutlineCount() == 0, "the cell is closer than 0.5 mm to the edge"


# ---- routing (back copper only, no vias) ---------------------------------------------------------
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


def inward(p, d):
    return (round(p[0] - KN[0] * d, 4), round(p[1] - KN[1] * d, 4))


j1 = padpos(conn, "1")
# badge 3.3 V: connector pin 1 -> up -> along the top edge above the connector -> down the right -> switch pin 1
route("VSAO", [j1, (j1[0], A(0, -11.9)[1]), A(5.3, -11.9), A(10.8, -6.4), inward(s1, 1.6), s1], width=THIN)

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. The right tab then runs up the right side to switch pin 4.
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in range(180, 361, 5)]
assert all(y <= BAT[1] + 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]])
route("VBAT", [s4, inward(s4, 1.6), A(18.5, 2.0), A(13.2, 7.3), A(11.0, 9.5), (bt[1][0], bt[1][1] - 1.8)], width=THIN)

# switched supply: switch pin 3 -> R2 -> one row under D2, the connector and D1 -> R1
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")
route("VLOAD", [s3, inward(s3, 1.6), r2a, (r2a[0], A(0, ROW - 0.65)[1]), (r2a[0] - 0.65, A(0, ROW)[1]), (r1a[0], A(0, ROW)[1]), r1a], width=THIN)
d1a, d2a = padpos(led["D1"], "2"), padpos(led["D2"], "2")
route("LED1_A", [r1b, (d1a[0] - 0.3, r1b[1]), (d1a[0], d1a[1] - 0.4)], width=THIN)
route("LED2_A", [r2b, d2a], width=THIN)

# ---- back copper: GND everywhere, cleared around everything that is not GND -------------------------
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for (x, y), _s in LEDS.values():                          # light path behind each LED
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)      # drop slivers thinner than 0.3 mm
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        print("  GND piece mm2", round(area_mm2(piece), 1), [round(v, 1) for v in bbox_mm(piece)])
        n_gnd += 1
    else:                                                 # an island that reaches no GND pad: leave it out
        print("  dropped copper island, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back GND copper pieces:", n_gnd)
assert n_gnd == 1, "the ground copper is in more than one piece"

# ---- front: the gem's fifteen facets in silkscreen ------------------------------------------------
holes = pcbnew.SHAPE_POLY_SET()
for (x, y), _s in LEDS.values():
    add_circle(holes, P(x, y), SILK_WINDOW)
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(holes, pad.GetPosition(), 0.75)
holes.Simplify()
_fa = 0.0
_svg = []
for f in GEM_FACETS:
    ps = grown(poly([A(u, v) for u, v in f]), -GAP / 2)
    ol = ps.Outline(0)
    _svg.append(" ".join("%.3f,%.3f" % (ToMM(ol.CPoint(n).x) - OFFSET[0], ToMM(ol.CPoint(n).y) - OFFSET[1]) for n in range(ol.PointCount())))
    ps.BooleanSubtract(holes)
    ps.Simplify()
    _fa += area_mm2(ps)
    add_filled(board, ps, F_SilkS)
print("front facets: %d, %.0f mm2 of silkscreen" % (len(GEM_FACETS), _fa))
# the drawing on its own (facets white, board dark), for anyone who wants to re-use or re-render it
os.makedirs(os.path.join(HERE, "..", "art"), exist_ok=True)
with open(os.path.join(HERE, "..", "art", "gem.svg"), "w") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<!-- SAO++ gem: a brilliant-cut stone seen from the side. Drawn by boards/nsec-diamond/hardware/build_board.py'
             ' from the numbers in GEM. CC-BY-SA-4.0, SAO++ project. Units: mm, origin at the middle of the girdle. -->\n'
             '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="%g %g %g %g">\n'
             % (2 * _g, _tip - _top, -_g, _top, 2 * _g, _tip - _top))
    fh.write('  <polygon fill="#16324a" points="%s"/>\n' % " ".join("%g,%g" % p for p in GEM_OUTLINE))
    for pts in _svg:
        fh.write('  <polygon fill="#ffffff" points="%s"/>\n' % pts)
    fh.write("</svg>\n")

# ---- back silkscreen: the maker's logo and box, then the SAO++ labels -----------------------------
for pl in LOGO_POLYS:
    add_filled(board, poly([LG(x, y) for x, y in pl]), B_SilkS)
t = pcbnew.PCB_TEXT(board)
t.SetText("2025")
t.SetLayer(B_SilkS)
t.SetTextSize(VECTOR2I(FromMM(ToMM(_lt.GetTextSize().x) * LOGO_SCALE), FromMM(ToMM(_lt.GetTextSize().y) * LOGO_SCALE)))
t.SetTextThickness(FromMM(ToMM(_lt.GetTextThickness()) * LOGO_SCALE))
t.SetBold(_lt.IsBold())
t.SetMirrored(_lt.IsMirrored())
t.SetHorizJustify(_lt.GetHorizJustify())
t.SetVertJustify(_lt.GetVertJustify())
t.SetTextAngleDegrees(_lt.GetTextAngleDegrees())
t.SetPosition(P(*LG(*mm(_lt.GetPosition()))))
board.Add(t)
_logo = poly([(LOGO_BOX[0], LOGO_BOX[1]), (LOGO_BOX[2], LOGO_BOX[1]), (LOGO_BOX[2], LOGO_BOX[3]), (LOGO_BOX[0], LOGO_BOX[3])])
_off = pcbnew.SHAPE_POLY_SET(_logo)
_off.BooleanSubtract(grown(body, -0.6))
print("logo box corners outside the 0.6 mm margin, mm2 (empty corner of the logo):", round(area_mm2(_off), 2))
add_filled(board, poly([(BOX_AT[0] - 2.5, BOX_AT[1] - 2.5), (BOX_AT[0] + 2.5, BOX_AT[1] - 2.5),
                        (BOX_AT[0] + 2.5, BOX_AT[1] + 2.5), (BOX_AT[0] - 2.5, BOX_AT[1] + 2.5)]), B_SilkS)

_ang = -math.degrees(math.atan2(_ed[1], _ed[0]))          # text running along the switch's edge


def along(d_edge, d_in):
    """A point d_edge mm along the switch (toward its lower end) and d_in mm inward from the switch centre."""
    return (SW[0] + _ed[0] * d_edge - KN[0] * d_in, SW[1] + _ed[1] * d_edge - KN[1] * d_in)


LABELS = [("SAO", along(-4.4, 3.9), 0.8, _ang, False), ("BAT", along(4.4, 3.9), 0.8, _ang, False),
          ("1", (CONN[0] - 9.3, CONN[1] - 3.4), 0.9, 0, False),
          ("+", A(-12.9, 13.8), 1.1, 0, True), ("CR2032", A(0, 26.0), 0.8, 0, False), ("+ UP", A(0, 27.5), 0.8, 0, False),
          ("orig. design:", A(17.0, 3.6), 0.8, 0, False), ("NorthSec", A(16.6, 4.9), 0.8, 0, False),
          ("SAO++ rA", A(16.0, 6.2), 0.8, 0, False), ("DIAMOND", A(15.2, 7.5), 0.8, 0, False)]
for txt, (x, y), size, rot, bold in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * (0.2 if bold else 0.15)))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)
    bb = t.GetBoundingBox()
    lab = poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))])
    if rot == 0:
        lab.BooleanSubtract(grown(body, -0.4))
        assert lab.OutlineCount() == 0, f"label {txt} is off the board or within 0.4 mm of the edge"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LEDs:", {r: mm(fp.GetPosition()) for r, fp in led.items()})
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
