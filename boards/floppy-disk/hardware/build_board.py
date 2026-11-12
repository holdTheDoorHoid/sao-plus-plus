#!/usr/bin/env python3
"""Rebuild floppy-disk.kicad_pcb from Uri Shaked's KiCad 5 original (the SMD flavor) plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/floppy-disk/hardware/build_board.py

What the original is (original/floppy-sao-smd.kicad_pcb, checked against original/README.md and media/schematic.png)
  - a 41.5 x 43.6 mm board shaped like a 3.5 inch floppy disk: two small rectangular holes at the top corners, a white
    silkscreen label, a bare-copper (gold) shutter with a window at the bottom on BOTH sides, a small 'HD' mark in
    copper under the mask on the front
  - back: two I2C EEPROMs in SOIC-8 (U1 256 bytes at 0x50, U2 64 KB at 0x51), a 100 nF capacitor each, two 10 k I2C
    pull-ups, two solder bridges that write-protect a chip when closed, a 2x3 SMD header. No LED, no battery, no switch.
    Everything on the back copper, no vias.

What this script does
  - reads the art out of the original, then cuts every footprint out of the file text
    (KiCad 10's Python crashes on Remove()), and all tracks and the two pin-1 circles; the maker's '64KB' and
    copyright lettering stay exactly where they were, and his logo is
    drawn again in the same place
  - outline: the maker's, as polygons (outline.json: one outer path, two rectangular holes)
  - places the SAO++ parts on the back: CR2032 clip at the top (cell slides in from the top edge), the SAO connector
    below it (key up), the SAO / OFF / BAT switch on the edge below the maker's logo, the cell diode beside the clip,
    and the two EEPROMs with their capacitors and write-protect bridges in the free column on the other side
  - routes everything on the back copper only (no vias) and fills the rest of the back with GND
  - front: unchanged art (label, shutter, HD mark). The shutter copper now stops 0.55 mm short of the bottom edge.

Coordinates are millimetres in KiCad's front view (x grows right, y grows down), in the maker's own coordinates:
the board spans x 129.25..170.75, y 83.36..126.94.
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, B_Mask, F_Mask, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks, bbox_mm, add_filled,  # noqa: E402
                         pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "floppy-disk"
load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "floppy-sao-smd.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TIGHT = 0.25        # ... beside the fine tracks under the connector and round the EEPROMs
TRACK = 0.30        # supply tracks
FINE = 0.25         # SDA / SCL / GND under the connector
THIN = 0.20         # SDA / SCL / write-protect down the side of U2 (three tracks in 1.2 mm)
EDGE = 0.55         # all poured copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge

# ---- placement (front view) -------------------------------------------------------------------
BAT = (150.0, 93.85)        # clip centre: the 20 mm cell sits 0.4 mm inside the top edge
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in from the top edge
CONN = (150.0, 111.35)      # top pads 0.85 mm below the clip's closed end; key slot up
SW = (131.37, 119.2)        # on the left edge (front view), below the maker's logo; knob points out of the edge
D1_AT = (137.2, 90.7)       # cell diode, upright, beside the clip's left solder tab
U1_AT = (163.0, 110.7)      # 256-byte ID EEPROM (SOT-23-5)
JP1_AT = (166.8, 111.65)    # its write-protect bridge
C1_AT = (165.9, 107.825)    # its capacitor
U2_AT = (166.05, 118.3)     # 64 KB EEPROM (SOIC-8)
JP2_AT = (163.25, 114.0)    # its write-protect bridge
C2_AT = (169.075, 113.7)    # its capacitor
LOCK1_AT = (166.8, 109.9)   # the maker's padlock icons, one beside each bridge
LOCK2_AT = (165.5, 113.9)

# ---- read the art out of the original, then cut the old parts out of the file text ---------------
_orig = pcbnew.LoadBoard(SRC)


def _fp(name):
    return [f for f in _orig.GetFootprints() if f.GetFPIDAsString() == name]


def _polys(fp, layer):
    return [pcbnew.SHAPE_POLY_SET(g.GetPolyShape()) for g in fp.GraphicalItems()
            if g.GetClass() == "PCB_SHAPE" and g.GetShape() == pcbnew.SHAPE_T_POLY and g.GetLayer() == layer]


_disk = _fp("floppy:3.5-disk")
assert len(_disk) == 1
_disk = _disk[0]
LABEL = _polys(_disk, F_SilkS)                       # the white label
assert len(LABEL) == 1
_fcu = _polys(_disk, F_Cu)
HD_MARK = [p for p in _fcu if area_mm2(p) < 5]       # the 'HD' mark: six small copper shapes under the mask
_shut = [p for p in _fcu if area_mm2(p) > 100]
assert len(HD_MARK) == 6 and len(_shut) == 1
for lay in (F_Mask, B_Cu, B_Mask):                   # the shutter is the same shape on all four layers
    q = _polys(_disk, lay)
    assert len(q) == 1 and abs(area_mm2(q[0]) - area_mm2(_shut[0])) < 0.01
_o = _shut[0].Outline(0)
_xs = sorted({round(ToMM(_o.CPoint(k).x), 3) for k in range(_o.PointCount())})
_ys = sorted({round(ToMM(_o.CPoint(k).y), 3) for k in range(_o.PointCount())})
assert len(_xs) == 4 and len(_ys) == 4, (_xs, _ys)
SHUT = (_xs[0], _ys[0], _xs[3], _ys[3])              # shutter rectangle
WIN = (_xs[1], _ys[1], _xs[2], _ys[2])               # its window
print("shutter x %.2f..%.2f y %.2f..%.2f; window x %.2f..%.2f y %.2f..%.2f" % (SHUT[0], SHUT[2], SHUT[1], SHUT[3], WIN[0], WIN[2], WIN[1], WIN[3]))
_locks = _fp("floppy:lock")
assert len(_locks) == 2
LOCK = _polys(_locks[0], B_SilkS)[0]                 # one padlock, at the maker's position
LOCK_AT0 = mm(_locks[0].GetPosition())
_logo = _fp("floppy:wokwi-cu")
assert len(_logo) == 1
_lb = _logo[0].GetBoundingBox(False)
LOGO_BOX = (ToMM(_lb.GetLeft()), ToMM(_lb.GetTop()), ToMM(_lb.GetRight()), ToMM(_lb.GetBottom()))
LOGO = {lay: _polys(_logo[0], lay) for lay in (B_Cu, B_Mask)}      # six bare-copper shapes: copper and mask opening alike
assert len(LOGO[B_Cu]) == 6 and len(LOGO[B_Mask]) == 6
KEPT_TEXT = {}
for d in _orig.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in ("64KB", "© 2020 Uri Shaked"):
        b = d.GetBoundingBox()
        KEPT_TEXT[d.GetText()] = (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))
assert len(KEPT_TEXT) == 2

_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "module", 2))                # every footprint goes; the art comes back below as board drawings
assert len(_cut) == 13, len(_cut)
_seg = list(blocks(_txt, "segment", 2))
assert len(_seg) == 93
_cut += _seg
_circ = list(blocks(_txt, "gr_circle", 2))           # the two pin-1 rings beside the old chips
assert len(_circ) == 2
_cut += _circ
_old = [(a_, b_) for a_, b_ in blocks(_txt, "gr_text", 2) if re.match(r"\n  \(gr_text 0x5[01] ", _txt[a_:b_])]
assert len(_old) == 2                                # '0x50' / '0x51' are printed again beside the chips' new places
_cut += _old
_cut += [(m.start(), m.end()) for m in re.finditer(r"\n  \(net [1-9]\d* [^\n]*\)", _txt)]
_cut += [(m.start(), m.end()) for m in re.finditer(r"\n    \(add_net [^\n]*\)", _txt)]
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "floppy.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)
board = pcbnew.LoadBoard(_tmp)
assert len(board.GetFootprints()) == 0 and not board.GetTracks()
TRACKS = []

# ---- outline: the maker's, as polygons -------------------------------------------------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert len(_ol["holes"]) == 2
body = poly(_ol["outer"])
for ring in [_ol["outer"]] + _ol["holes"]:
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(poly(ring))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
# shrink the outer path and grow the holes separately (shrinking a shape that has a hole opens a slit)
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)
for h in _ol["holes"]:
    inner.BooleanSubtract(grown(poly(h), EDGE))
    pad_ok.BooleanSubtract(grown(poly(h), PAD_EDGE))
_bb = bbox_mm(body)
print("board %.2f x %.2f mm" % (_bb[2] - _bb[0], _bb[3] - _bb[1]))


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


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
    fp.SetFPID(pcbnew.LIB_ID(*fpid.split(":")))
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


def near(a, b, tol=0.02):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
assert near(padpos(conn, "2"), (CONN[0] - 2.54, CONN[1] + 3.4)) and near(padpos(conn, "4"), (CONN[0], CONN[1] + 3.4))

# switch on the left edge: pins toward the middle of the board, knob out of the edge. A part on the back is mirrored,
# so with the knob pointing left the coin-cell contact (pin 4) is the upper one and the badge contact (pin 1) the lower.
sw = place("SW1", SW, ("1", (SW[0] + 1.43, SW[1] + 3.0)))
assert near(padpos(sw, "4"), (SW[0] + 1.43, SW[1] - 3.0)) and near(padpos(sw, "3"), (SW[0] + 1.43, SW[1] - 1.5))
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetLeft())
assert ToMM(_kb.GetRight()) < SW[0], "knob is not pointing left"
print(f"switch knob tip x {KNOB_TIP:.2f}: {_bb[0] - KNOB_TIP:.2f} mm past the left edge")

d1 = place("D1", D1_AT, ("2", (D1_AT[0], D1_AT[1] - 0.7)))            # anode up (toward the clip tab's top end)
u1 = place("U1", U1_AT, ("3", (U1_AT[0] - 1.1375, U1_AT[1] - 0.95)))  # SDA / GND / SCL down the side facing the connector
assert near(padpos(u1, "1"), (U1_AT[0] - 1.1375, U1_AT[1] + 0.95)) and near(padpos(u1, "4"), (U1_AT[0] + 1.1375, U1_AT[1] - 0.95))
u2 = place("U2", U2_AT, ("8", (U2_AT[0] - 2.475, U2_AT[1] - 1.905)))  # VCC / WC / SCL / SDA down the left, E0 + three GND pins right
assert near(padpos(u2, "5"), (U2_AT[0] - 2.475, U2_AT[1] + 1.905)) and near(padpos(u2, "1"), (U2_AT[0] + 2.475, U2_AT[1] - 1.905))
jp1 = place("JP1", JP1_AT, ("1", (JP1_AT[0] - 0.65, JP1_AT[1])))
jp2 = place("JP2", JP2_AT, ("1", (JP2_AT[0] - 0.65, JP2_AT[1])))
c1 = place("C1", C1_AT, ("1", (C1_AT[0], C1_AT[1] + 0.775)))          # supply pad down (on the supply track), GND pad up
c2 = place("C2", C2_AT, ("1", (C2_AT[0] - 0.775, C2_AT[1])))          # supply pad left, GND pad right (in the GND strip at the edge)

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
STRAP = (ToMM(_sb.GetLeft()), ToMM(_sb.GetTop()), ToMM(_sb.GetRight()), ToMM(_sb.GetBottom()))
print("battery clip angle", _rot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f" % (STRAP[0], STRAP[2], STRAP[1], STRAP[3]))
assert STRAP[3] < CONN[1] - 5.6 - 0.8, "clip's closed end is too close to the connector's top pads"
# the clip's own silkscreen (insertion arrow off the top edge, '+', closed-end line) moves to the fab layer
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

NEW = set(PARTS)
for fp in board.GetFootprints():        # every pad of a new part sits on the board, PAD_EDGE inside the edge
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"


# ---- routing (back copper only, no vias) ----------------------------------------------------------
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


CX, CY = CONN
j1, j2, j3, j4 = (padpos(conn, n) for n in "1234")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
LANE_BAT, LANE_LOAD, LANE_SAO = 137.2, 137.8, 138.4      # three tracks between the maker's lettering and the clip / shutter
COR = CY - 6.05                                          # the 0.85 mm corridor between the clip's closed end and the connector's top pads
Y_SDA, Y_GND, Y_SCL = CY - 0.7, CY - 0.2, CY + 0.3       # three tracks between the connector's two pad rows, under its body

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in range(180, -1, -5)]
assert all(y >= BAT[1] - 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VCELL", [bt[0]] + arc[1:-1] + [bt[1]], width=0.4)
# ... -> cell diode (beside the left tab) -> down the left lane -> switch pin 4 (upper pin)
d1a, d1k = padpos(d1, "2"), padpos(d1, "1")
route("VCELL", [bt[0], (bt[0][0], d1a[1]), d1a], width=0.4)
route("VBAT", [d1k, (LANE_BAT, s4[1] - 0.2), (LANE_BAT - 0.6, s4[1] + 0.4), (s4[0] + 1.55, s4[1] + 0.4), (s4[0] + 1.15, s4[1]), s4])
# badge 3.3 V: connector pin 1 -> between the pad rows, under the connector body -> right lane -> switch pin 1 (lower pin)
route("VSAO", [j1, (j1[0], Y_SDA), (LANE_SAO, Y_SDA), (LANE_SAO, s1[1]), s1])
# switched supply: switch pin 3 -> middle lane -> along the corridor above the connector -> over U1 to its VCC pin,
# C1, the bridge JP1 -> down the right edge to C2 and U2's E0 pin -> under U2 to its VCC pin and the bridge JP2
u1v, u1wp, u2e0, u2v, u2wc = padpos(u1, "4"), padpos(u1, "5"), padpos(u2, "1"), padpos(u2, "8"), padpos(u2, "7")
c1v, c2v = padpos(c1, "1"), padpos(c2, "1")
XV = c2v[0]                                              # the supply's run down the right side
route("VLOAD", [s3, (LANE_LOAD, s3[1]), (LANE_LOAD, COR + 0.3), (LANE_LOAD + 0.3, COR)], width=TRACK)
route("VLOAD", [(LANE_LOAD + 0.3, COR), (u1v[0] - (c1v[1] - COR), COR), (u1v[0], c1v[1])], width=FINE, clear=TIGHT)
route("VLOAD", [(u1v[0], c1v[1]), u1v])
route("VLOAD", [(u1v[0], c1v[1]), c1v, (XV, c1v[1]), (XV, c2v[1]), (XV, u2e0[1]), u2e0, u2v])
route("VLOAD", [(XV, u1wp[1]), padpos(jp1, "2")])
route("VLOAD", [padpos(jp2, "2"), (padpos(jp2, "2")[0], u2v[1])])
# SDA: connector pin 3 -> under the connector -> U1 pin 3 -> on under U1's body -> down the side of U2 -> U2 pin 5
u1sda, u1gnd, u1scl = padpos(u1, "3"), padpos(u1, "2"), padpos(u1, "1")
u2sda, u2scl = padpos(u2, "5"), padpos(u2, "6")
X_SCL2, X_SDA2, X_WC = U2_AT[0] - 4.7, U2_AT[0] - 4.3, U2_AT[0] - 3.75
FAN0 = CX + 8.3                                          # just past the connector body: the three tracks spread to U1's pin pitch
route("SDA", [j3, (j3[0], Y_SDA - 0.3), (j3[0] + 0.3, Y_SDA), (FAN0, Y_SDA), (FAN0 + (Y_SDA - u1sda[1]), u1sda[1]), u1sda], width=FINE, clear=TIGHT)
route("SDA", [u1sda, (U1_AT[0], u1sda[1]), (U1_AT[0], U1_AT[1] + 1.8), (U1_AT[0] - 0.6, U1_AT[1] + 1.8)], width=FINE, clear=TIGHT)
route("SDA", [(U1_AT[0] - 0.6, U1_AT[1] + 1.8), (X_SDA2, U1_AT[1] + 1.8 + (U1_AT[0] - 0.6 - X_SDA2)), (X_SDA2, u2sda[1]), u2sda], width=THIN, clear=TIGHT)
# SCL: connector pin 4 -> under the connector -> U1 pin 1 -> down the side of U2, round its end, under its body -> U2 pin 6
Y_TURN = u2sda[1] + 0.75
route("SCL", [j4, (j4[0], Y_SCL + 0.3), (j4[0] + 0.3, Y_SCL), (FAN0 + 1.0, Y_SCL), (FAN0 + 1.0 + (Y_SCL - u1scl[1]), u1scl[1]), u1scl], width=FINE, clear=TIGHT)
route("SCL", [(X_SCL2, u1scl[1]), (X_SCL2, Y_TURN), (U2_AT[0] - 1.05, Y_TURN), (U2_AT[0] - 1.05, u2scl[1]), u2scl], width=THIN, clear=TIGHT)
# GND: connector pin 2 -> between SDA and SCL -> U1 pin 2; a stub ties pin 2 to the shutter copper
route("GND", [j2, (j2[0], CY + 0.9), (j2[0] + 1.1, Y_GND), (FAN0 + 0.5, Y_GND), (FAN0 + 0.5 + (Y_GND - u1gnd[1]), u1gnd[1]), u1gnd], width=FINE)
route("GND", [(j2[0], CY + 3.7), (j2[0] + 1.25, CY + 3.7)], width=FINE)
# GND: U2's three grounded pins, tied together and to the strip of GND copper that runs down the right edge
u2g = [padpos(u2, n) for n in "234"]
route("GND", [u2g[0], u2g[2], (u2g[2][0], u2g[2][1] + 1.5)])
c2g = padpos(c2, "2")
XG = 170.0
route("GND", [c2g, (XG, c2g[1] + 0.3), (XG, u2g[2][1] + 1.5), (u2g[2][0], u2g[2][1] + 1.5)], width=FINE)
# write protect: each chip's WP / WC pin to its solder bridge
route("WP1", [u1wp, padpos(jp1, "1")], width=FINE)
route("WP2", [u2wc, (X_WC, u2wc[1]), (X_WC, JP2_AT[1] + 0.2), padpos(jp2, "1")], width=THIN, clear=TIGHT)

# ---- back copper: GND everywhere, cleared around everything that is not GND ---------------------------
gnd_code = nets["GND"].GetNetCode()
shutter = rect(*SHUT)
window = rect(*WIN)
logo_keep = grown(rect(*LOGO_BOX), 0.5)                  # the maker's back logo keeps its own copper, with a clear margin
art = pcbnew.SHAPE_POLY_SET(inner)
art.BooleanSubtract(window)                              # the shutter's window stays free of copper, as drawn
art.BooleanSubtract(logo_keep)
cut = pcbnew.SHAPE_POLY_SET()
allpads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(allpads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
            if pad.GetNetCode() != gnd_code:
                pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
alltracks = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(alltracks, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
cut.Simplify()
art.BooleanSubtract(cut)
# drop slivers thinner than 0.3 mm (they would only be specks of copper)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.BooleanSubtract(window)
art.BooleanSubtract(logo_keep)
art.BooleanIntersection(inner)
art.Simplify()

# no track may touch the maker's lettering or logo, or cut into the shutter outside the connector's footprint
_keep = pcbnew.SHAPE_POLY_SET(logo_keep)
for b in KEPT_TEXT.values():
    _keep.Append(rect(*b))
_hit = pcbnew.SHAPE_POLY_SET(alltracks)
_hit.BooleanIntersection(_keep)
assert area_mm2(_hit) < 0.001, f"a track overlaps the maker's lettering or logo by {area_mm2(_hit):.3f} mm2"
_cb = conn.GetBoundingBox(False)
_vis = pcbnew.SHAPE_POLY_SET(shutter)
_vis.BooleanSubtract(rect(ToMM(_cb.GetLeft()), ToMM(_cb.GetTop()), ToMM(_cb.GetRight()), ToMM(_cb.GetBottom())))
_vis.BooleanIntersection(cut)
assert area_mm2(_vis) < 0.001, f"copper is cut out of the visible part of the back shutter ({area_mm2(_vis):.3f} mm2)"

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
for t, _ in TRACKS:
    if t.GetNetCode() == gnd_code:
        t.TransformShapeToPolygon(gnd_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_pads.Simplify()
n_gnd = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  GND copper piece, mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    elif area_mm2(piece) > 3:                            # walled in by tracks: plain copper, for stiffness round the connector
        add_filled(board, piece, B_Cu, None)
        print("  plain copper piece (reaches no GND pad), mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    else:                                                # specks between tracks: leave them out
        print("  speck left out, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back GND copper pieces:", n_gnd)


# ---- the maker's art, as board drawings ---------------------------------------------------------------
def art_add(ps, layer):
    add_filled(board, ps, layer, None)


art_add(LABEL[0], F_SilkS)                               # white label: unchanged
for p_ in HD_MARK:                                       # 'HD' mark: unchanged
    art_add(p_, F_Cu)
front_shut = pcbnew.SHAPE_POLY_SET(shutter)              # front shutter: the maker's, stopping EDGE short of the bottom edge
front_shut.BooleanSubtract(window)
front_shut.BooleanIntersection(inner)
art_add(front_shut, F_Cu)
art_add(front_shut, F_Mask)
# back shutter: the same bare-copper rectangle, but the solder mask stays on round the connector's pads and over the
# tracks under the connector, so nothing but GND copper is bare
back_open = pcbnew.SHAPE_POLY_SET(shutter)
back_open.BooleanSubtract(window)
back_open.BooleanIntersection(inner)
_dam = grown(allpads, 0.35)
_dam.Append(grown(alltracks, 0.2))
for g in conn.GraphicalItems():                          # ... and under the connector's printed outline, so it prints whole
    if g.GetLayer() == B_SilkS:
        g.TransformShapeToPolygon(_dam, B_SilkS, FromMM(0.15), ERR, pcbnew.ERROR_OUTSIDE)
_dam.Simplify()
back_open.BooleanSubtract(_dam)
back_open.Simplify()
art_add(back_open, B_Mask)
print("shutter bare copper, mm2: front %.1f, back %.1f (maker: %.1f each)" % (area_mm2(front_shut), area_mm2(back_open), area_mm2(_shut[0])))
for lay in (B_Cu, B_Mask):                               # the maker's back logo: unchanged, in place
    for p_ in LOGO[lay]:
        art_add(p_, lay)
for at in (LOCK1_AT, LOCK2_AT):                          # padlock icons, moved with the bridges
    q = pcbnew.SHAPE_POLY_SET(LOCK)
    q.Move(VECTOR2I(FromMM(at[0] - LOCK_AT0[0]), FromMM(at[1] - LOCK_AT0[1])))
    art_add(q, B_SilkS)

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("BAT", 134.45, 114.7, 0.8, 90, False), ("SAO", 134.45, 124.1, 0.8, 90, False),
          ("FLOPPY DISK", 163.6, 96.3, 1.0, 90, False), ("SAO++ rA", 165.5, 96.3, 0.9, 90, False),
          ("CR2032 + UP", 167.3, 96.3, 0.8, 90, False),
          ("1", 141.3, 107.6, 0.9, 0, False),
          ("0x50", 161.3, 107.2, 1.0, 0, False), ("0x51", 166.0, 122.2, 1.0, 0, False)]
for txt, x, y, size, rot, bold in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * (0.2 if bold else 0.15)))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- report -------------------------------------------------------------------------------------
for r, fp in (("J1", conn), ("SW1", sw), ("U1", u1), ("U2", u2), ("D1", d1)):
    print(r, "pads:", {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber()})
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
