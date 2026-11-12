#!/usr/bin/env python3
"""Build nsec-bandaid.kicad_pcb: NorthSec's 2025 Sao_Bandaid circuit on SAO++'s own sticking-plaster drawing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-bandaid/hardware/build_board.py

What the original is (read from the files; the maker left no description):
  - a 47.5 x 14 mm sticking plaster. Front: a copper strip, a white gauze pad, 26 bare round copper pads as the
    "air holes" (connected to nothing), and ONE hand-soldered 1206 LED in the middle of the pad with a 330 ohm resistor.
  - back: an SMD 2x3 SAO connector and two 1 k resistors from SDA and from SCL to the badge's 3.3 V: I2C pull-ups.
    The NorthSec 2025 badge has no pull-ups of its own on that bus, so this add-on is, literally, the band-aid for it.
  - back silkscreen: the "nsec 2025" logo and a blank 5 x 5 mm white box. No battery, no switch.
  - its outline, pad and the positions of the 26 dots were traced by the maker from a picture embedded in the board
    file. NONE of that geometry is used here or kept in this repository (see original/README.md and board.yml).

What this script does
  - draws SAO++'s own plaster from the numbers in PLASTER below: a 68 x 26 mm strip with 9 mm corners (two short flat
    ends, not half-circles), a 20 mm square gauze pad in the middle and a regular lattice of 23 air holes each side.
    The same drawing is written to art/bandage.svg.
  - front: the gauze pad in white silkscreen with a drop-shaped window left clear in its middle (the LED sits behind
    the round part of the drop); the 46 air holes as bare copper dots (gold with ENIG). Nothing else: no parts, no
    tracks, no vias.
  - back: SAO connector top centre (key up); red through-board LED D1 with its 1.3 k resistor just below it, under the
    middle of the gauze pad; CR2032 clip at the left end in front view (the cell slides in over that end), the series
    cell diode D2 right after it; the SAO / OFF / BAT switch on the bottom edge. R2 / R3 (the pull-ups) have pads but
    are not fitted by default. Routed on the back only.
  - back silkscreen: the maker's logo at 0.7 size and the maker's 5 x 5 mm box at the right end, and the SAO++ labels.
  - back copper: GND everywhere, 0.55 mm back from the edge, cleared around everything that is not GND and behind
    the LED.

Local coordinates (u, v) are millimetres from the middle of the plaster, front view (u right, v down); board
coordinates add OFFSET.
"""
import json
import math
import os
import re
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS, F_Mask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "nsec-bandaid"
load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "Sao_Bandaid", "Sao_Bandaid.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

OFFSET = (45.0, 25.0)   # where the middle of the plaster sits on the board
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40
THIN = 0.30
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25
WINDOW = 1.7        # radius kept free of back copper behind the LED
SILK_WINDOW = 1.6   # radius that must stay free of front silkscreen over the LED (the drop-shaped window is larger)
LOGO_SCALE = 0.7    # the maker's logo is drawn this much smaller: it is the credit, not the subject


def A(u, v):
    """local -> board coordinates"""
    return (round(OFFSET[0] + u, 4), round(OFFSET[1] + v, 4))


# ---- the plaster: SAO++'s own drawing, from these numbers only (local coordinates) ---------------------
PLASTER = {"length": 68.0,     # sized around the parts: 24 mm cell clip + 15 mm connector + room for switch and credit
           "width": 26.0,      # the cell clip is 22.8 mm across its solder tabs; 1.6 mm of board outside each
           "corner": 9.0,      # corner radius: leaves an 8 mm flat at each end (a fabric plaster, not a pill shape)
           "gauze": 20.0,      # the gauze pad is a square this size in the middle
           "gauze_corner": 2.5,
           "drop": (2.5, 1.5, -3.5),   # the drop-shaped window in the pad: radius and v of its round part, v of its tip
           "hole": 1.5,        # air hole diameter
           "hole_first": 14.0,  # the first column of holes is this far from the middle
           "hole_step": 2.0,   # columns are this far apart ...
           "hole_rows": (6.0, 3.0)}   # ... alternating between three holes (0 and +-6 mm) and two holes (+-3 mm)


def rounded_rect(hx, hy, r, step=3):
    """Corner points of a rectangle 2*hx by 2*hy with corners rounded to radius r, clockwise from the top-left arc."""
    pts = []
    for cx, cy, a0 in ((-hx + r, -hy + r, 180), (hx - r, -hy + r, 270), (hx - r, hy - r, 0), (-hx + r, hy - r, 90)):
        for a in range(a0, a0 + 91, step):
            pts.append((round(cx + r * math.cos(math.radians(a)), 4), round(cy + r * math.sin(math.radians(a)), 4)))
    return pts


HL, HW = PLASTER["length"] / 2, PLASTER["width"] / 2
STRIP = rounded_rect(HL, HW, PLASTER["corner"])
HG = PLASTER["gauze"] / 2
GAUZE = rounded_rect(HG, HG, PLASTER["gauze_corner"], 5)
_dr, _dc, _dt = PLASTER["drop"]
_da = math.degrees(math.acos(_dr / (_dc - _dt)))            # where the two straight sides touch the round part
DROP = [(0.0, _dt)] + [(round(_dr * math.sin(math.radians(a)), 4), round(_dc - _dr * math.cos(math.radians(a)), 4))
                       for a in [_da + k * (360 - 2 * _da) / 48 for k in range(49)]]
HOLES = []
for side in (-1, 1):
    for k in range(9):
        u = side * (PLASTER["hole_first"] + k * PLASTER["hole_step"])
        rows = (-PLASTER["hole_rows"][0], 0.0, PLASTER["hole_rows"][0]) if k % 2 == 0 else (-PLASTER["hole_rows"][1], PLASTER["hole_rows"][1])
        HOLES += [(u, v) for v in rows]
assert len(HOLES) == 46

# ---- placement (local coordinates) ------------------------------------------------------------------
CONN = A(0.0, -HW + 3.0 + 4.45)   # plastic body 3.0 mm below the top edge, key slot up, in the middle of the length
LED = A(0.0, 2.05)           # as near the middle of the gauze pad as the connector's keep-out box allows: 2 mm below it,
                             # inside the round part of the drop-shaped window
R1_AT = A(5.5, 2.05)         # flat, right of the LED
BAT = A(-22.0, 0.0)          # cell 2 mm inside the left end, 3 mm inside both long edges
BAT_CLOSED = (1.0, 0.0)      # closed end toward the connector; the cell slides in over the left end
D2_AT = A(-8.2, 6.0)         # the cell diode, flat, just outside the clip's closed end
R3_AT = A(10.2, -8.0)        # optional pull-ups, upright, right of the connector
R2_AT = A(12.8, -8.0)
SW_U = 15.0                  # the switch sits on the bottom edge, its middle this far right of the board's middle
BOX_AT = A(22.0, -8.0)       # the maker's blank 5 x 5 mm white box
LOGO_AT = A(26.3, -1.9)      # centre of the maker's logo, right end in front view
TOP_ROW = -HW + 1.1          # v of the badge-supply track that runs along the top edge above the connector

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
assert len(_rect) == 1 and "(start 127.5 93.5)" in _rect[0] and "(end 132.5 98.5)" in _rect[0]      # the 5 x 5 mm box

OUTLINE = [A(u, v) for u, v in STRIP]
json.dump({"outer": [list(p) for p in OUTLINE], "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
body = poly(OUTLINE)
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's board: 47.5 x 14.0)")
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
assert len(LOGO_POLYS) == 2 and len(_lt) == 1 and _lt[0].GetText() == "2025", (len(LOGO_POLYS), len(_lt))
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
NOT_FITTED = ("R2", "R3")                                         # same list as fix_schematic.py
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
    fp.SetFPID(pcbnew.LIB_ID(*fpid.split(":")))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
    fp.SetValue(PARTS[ref].get("value", value))
    for k, v in fields.items():
        assert fp.HasField(k), f"{ref}: footprint has no {k} field"
        fp.GetField(k).SetText(v)
    if ref in NOT_FITTED:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_DNP)
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
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    fp.Value().SetVisible(False)
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
led = place("D1", LED, ("2", (LED[0] + 1.55, LED[1])))                 # anode pad on the right, toward R1
r1 = place("R1", R1_AT, ("1", (R1_AT[0] + 0.825, R1_AT[1])))           # switched-supply pad on the right
r2 = place("R2", R2_AT, ("1", (R2_AT[0], R2_AT[1] - 0.825)))           # badge-supply pad at the top
r3 = place("R3", R3_AT, ("1", (R3_AT[0], R3_AT[1] - 0.825)))
d2 = place("D2", D2_AT, ("2", (D2_AT[0] - 0.7, D2_AT[1])))             # anode on the left, toward the cell

# switch: on the bottom edge, knob pointing straight down out of it. A part on the back is mirrored, so here the cell
# contact (pin 4) lands on the left, toward the cell, and the badge contact (pin 1) on the right.
KN = (0.0, 1.0)                                           # the knob direction
SW_IN = 1.83 + PAD_EDGE + 0.05                            # outer solder tabs PAD_EDGE inside the edge
SW = A(SW_U, HW - SW_IN)
sw = load("SW1", SW)


def _knob_dir():
    pins = [mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber() in ("1", "2", "3", "4")]
    cx, cy = sum(p[0] for p in pins) / 4, sum(p[1] for p in pins) / 4
    d = math.hypot(SW[0] - cx, SW[1] - cy)
    return ((SW[0] - cx) / d, (SW[1] - cy) / d)


_best = None
for _rot in (0, 90, 180, 270):
    sw.SetOrientationDegrees(_rot)
    _kd = _knob_dir()
    _dot = _kd[0] * KN[0] + _kd[1] * KN[1]
    if _best is None or _dot > _best[0]:
        _best = (_dot, _rot)
sw.SetOrientationDegrees(_best[1])
assert _best[0] > 0.99999, _best
link(sw, "SW1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
assert s4[0] < s3[0] < s1[0], "cell contact is not at the left end of the switch"
print("switch at (%.2f, %.2f), angle %d; knob tip %.2f mm past the edge" % (SW[0], SW[1], _best[1], 3.1 - SW_IN))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _strap(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    b = fab[0].GetBoundingBox()                          # the clip body rectangle is off-centre toward the closed end
    return (ToMM(b.GetLeft()), ToMM(b.GetRight()), ToMM(b.GetTop()), ToMM(b.GetBottom()))


_rot = None
for _r in (0, 90, 180, 270):
    _s = _strap(_r)
    _c = ((_s[0] + _s[1]) / 2 - BAT[0], (_s[2] + _s[3]) / 2 - BAT[1])
    if _c[0] * BAT_CLOSED[0] + _c[1] * BAT_CLOSED[1] > 3.0:
        _rot = _r
assert _rot is not None
STRAP = _strap(_rot)
link(bat, "BT1")
print("battery clip angle", _rot, "; clip body x %.2f..%.2f y %.2f..%.2f" % STRAP)
assert STRAP[1] > BAT[0] + 10.9, "clip's closed end is not toward the connector"
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
_cell.BooleanSubtract(grown(body, -1.5))
assert _cell.OutlineCount() == 0, "the cell is closer than 1.5 mm to the edge"
# house rule: the connector's plastic body (15.27 x 8.9 mm) is at least 3 mm from every edge
_cb = poly([(CONN[0] - 7.635, CONN[1] - 4.45), (CONN[0] + 7.635, CONN[1] - 4.45), (CONN[0] + 7.635, CONN[1] + 4.45), (CONN[0] - 7.635, CONN[1] + 4.45)])
_cb.BooleanSubtract(grown(body, -2.999))
assert _cb.OutlineCount() == 0, "the connector body is closer than 3 mm to an edge"
# house rule: the switch sits on a straight edge: its whole 11.8 mm keep-out is inside the flat part of the bottom edge
assert SW_U + 5.9 <= HL - PLASTER["corner"], "the switch reaches into a rounded corner"


# ---- routing (back copper only, no vias) ---------------------------------------------------------
def route(net, pts, width=THIN, clear=CLEAR):
    pts = [(round(x, 4), round(y, 4)) for x, y in pts]
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


j1, j3, j4 = padpos(conn, "1"), padpos(conn, "3"), padpos(conn, "4")
assert j1[1] < CONN[1] and j3[1] < CONN[1] < j4[1] and abs(j3[0] - CONN[0]) < 0.01 and abs(j4[0] - CONN[0]) < 0.01
r1a, r1b = padpos(r1, "1"), padpos(r1, "2")
r2a, r2b = padpos(r2, "1"), padpos(r2, "2")
r3a, r3b = padpos(r3, "1"), padpos(r3, "2")
top = A(0, TOP_ROW)[1]

# badge 3.3 V: connector pin 1 -> up -> along the top edge above the connector -> down the right -> switch pin 1.
# The two pull-up pads hang from the same track.
route("VSAO", [j1, (j1[0], top + 0.5), (j1[0] + 0.5, top), (s1[0] - 1.5, top), (s1[0], top + 1.5), s1])
route("VSAO", [(r3a[0], top), r3a])
route("VSAO", [(r2a[0], top), r2a])

# SDA and SCL leave their pads under the connector's plastic body (between its two rows of pads) and go right to the
# pull-up pads. SDA is the upper track, SCL the lower one.
_sda_v, _scl_v = CONN[1] - 0.6, CONN[1] + 0.6
route("SDA", [j3, (j3[0], _sda_v - 0.55), (j3[0] + 0.55, _sda_v), (r3b[0] - 1.0, _sda_v), (r3b[0], _sda_v - 1.0), r3b])
route("SCL", [j4, (j4[0], _scl_v + 0.55), (j4[0] + 0.55, _scl_v), (r2b[0] - 1.0, _scl_v), (r2b[0], _scl_v - 1.0), r2b])

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. The diode D2 is fed from a point on that link.
bt = sorted((mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"), key=lambda p: p[1])
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
d2a, d2k = padpos(d2, "2"), padpos(d2, "1")
_feed = math.degrees(math.asin((d2a[1] - BAT[1]) / _r))
_angs = sorted(set(list(range(-90, 91, 5)) + [_feed]))
arc = [(BAT[0] + _r * math.cos(math.radians(d)), BAT[1] + _r * math.sin(math.radians(d))) for d in _angs]
assert all(x >= BAT[0] - 0.01 for x, _ in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]], width=TRACK)
route("VBAT", [(BAT[0] + _r * math.cos(math.radians(_feed)), d2a[1]), d2a])

# after the diode: along the lower half to switch pin 4 (the left one)
route("VCELL", [d2k, (s4[0] - 1.0, d2k[1]), (s4[0], d2k[1] + 1.0), s4])
# switched supply: switch pin 3 -> up -> R1 -> LED
route("VLOAD", [s3, (s3[0], r1a[1] + 0.6), (s3[0] - 0.6, r1a[1]), r1a])
route("LED_A", [r1b, padpos(led, "2")])

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
add_circle(cut, P(*LED), WINDOW)                           # light path behind the LED
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

# ---- front: the gauze pad in silkscreen, the air holes as bare copper dots ---------------------------
drop = poly([A(u, v) for u, v in DROP])
_lens = pcbnew.SHAPE_POLY_SET()
add_circle(_lens, P(*LED), SILK_WINDOW)
_lens.BooleanSubtract(drop)
assert _lens.OutlineCount() == 0, "the drop-shaped window does not clear the LED by %.1f mm all round" % SILK_WINDOW
gauze = poly([A(u, v) for u, v in GAUZE])
gauze.BooleanSubtract(drop)
gauze.Simplify()
add_filled(board, gauze, F_SilkS)
_pegs = [mm(p.GetPosition()) for p in sw.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
for u, v in HOLES:
    x, y = A(u, v)
    assert all(math.hypot(x - px, y - py) > 2.0 for px, py in _pegs), "an air hole dot is on a switch-peg hole"
    assert abs(u) - PLASTER["hole"] / 2 > HG + 1.0
    dot = pcbnew.SHAPE_POLY_SET()
    add_circle(dot, P(x, y), PLASTER["hole"] / 2)
    off = pcbnew.SHAPE_POLY_SET(dot)
    off.BooleanSubtract(grown(body, -1.5))
    assert off.OutlineCount() == 0, "an air hole dot is closer than 1.5 mm to the edge"
    add_filled(board, dot, F_Cu)
    opening = pcbnew.SHAPE_POLY_SET()
    add_circle(opening, P(x, y), PLASTER["hole"] / 2 + 0.05)
    add_filled(board, opening, F_Mask)
print("front: gauze pad %.0f mm2 of silkscreen, %d air-hole dots" % (area_mm2(gauze), len(HOLES)))
# the drawing on its own, for anyone who wants to re-use or re-render it
os.makedirs(os.path.join(HERE, "..", "art"), exist_ok=True)
with open(os.path.join(HERE, "..", "art", "bandage.svg"), "w") as fh:
    fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<!-- SAO++ sticking plaster. Drawn by boards/nsec-bandaid/hardware/build_board.py'
             ' from the numbers in PLASTER. CC-BY-SA-4.0, SAO++ project. Units: mm, origin at the middle of the plaster. -->\n'
             '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="%g %g %g %g">\n'
             % (2 * HL, 2 * HW, -HL, -HW, 2 * HL, 2 * HW))
    fh.write('  <polygon fill="#1f5c3a" points="%s"/>\n' % " ".join("%g,%g" % p for p in STRIP))
    fh.write('  <polygon fill="#ffffff" points="%s"/>\n' % " ".join("%g,%g" % p for p in GAUZE))
    fh.write('  <polygon fill="#b3261e" points="%s"/>\n' % " ".join("%g,%g" % p for p in DROP))
    for u, v in HOLES:
        fh.write('  <circle fill="#d9b24a" cx="%g" cy="%g" r="%g"/>\n' % (u, v, PLASTER["hole"] / 2))
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
assert _off.OutlineCount() == 0, "the logo is within 0.6 mm of the edge"
add_filled(board, poly([(BOX_AT[0] - 2.5, BOX_AT[1] - 2.5), (BOX_AT[0] + 2.5, BOX_AT[1] - 2.5),
                        (BOX_AT[0] + 2.5, BOX_AT[1] + 2.5), (BOX_AT[0] - 2.5, BOX_AT[1] + 2.5)]), B_SilkS)

# (text, where, size, angle, bold). The column between the cell clip and the connector reads bottom to top.
_col = -9.35
LABELS = [("BAT", (SW[0] - 4.4, SW[1] - 3.35), 0.8, 0, False), ("OFF", (SW[0], SW[1] - 3.35), 0.8, 0, False),
          ("SAO", (SW[0] + 4.4, SW[1] - 3.35), 0.8, 0, False),
          ("1", A(_col, -8.95), 0.9, 0, False),
          ("CR2032", A(_col, -3.6), 0.8, 90, False), ("+ UP", A(_col, 2.5), 1.0, 90, True),
          ("R3", (R3_AT[0], R3_AT[1] + 2.1), 0.8, 0, False), ("R2", (R2_AT[0] + 0.3, R2_AT[1] + 2.1), 0.8, 0, False),
          ("orig. design:", A(26.0, 2.4), 0.8, 0, False), ("NorthSec", A(26.0, 3.7), 0.8, 0, False),
          ("SAO++ rA", A(26.0, 5.0), 0.8, 0, False), ("BANDAID", A(26.0, 6.3), 0.8, 0, False)]
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
    print("  label %-14s x %.2f..%.2f  y %.2f..%.2f" % (txt, ToMM(bb.GetLeft()) - OFFSET[0], ToMM(bb.GetRight()) - OFFSET[0],
                                                       ToMM(bb.GetTop()) - OFFSET[1], ToMM(bb.GetBottom()) - OFFSET[1]))
    lab.BooleanSubtract(grown(body, -0.4))
    assert lab.OutlineCount() == 0, f"label {txt} is off the board or within 0.4 mm of the edge"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LED:", mm(led.GetPosition()), "D2:", mm(d2.GetPosition()))
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

# kicad-cli 10.0.8 can rewrite the .kicad_pro and drop the house severities: put them back every build
_pro = os.path.join(HERE, SLUG + ".kicad_pro")
_p = json.load(open(_pro))
for key, val in json.load(open(os.path.join(HERE, "project_rules.json"))).items():
    node = _p
    *path, last = key.split(".")
    for k in path:
        node = node.setdefault(k, {})
    node[last] = val
json.dump(_p, open(_pro, "w"), indent=2)
print("re-applied project rules to", os.path.basename(_pro))
sys.stdout.flush()
os._exit(0)          # KiCad 10's Python can crash while tidying up at exit, after the board is saved
