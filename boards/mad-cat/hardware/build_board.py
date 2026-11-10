#!/usr/bin/env python3
"""Rebuild mad-cat.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mad-cat/hardware/build_board.py

What it does
  - loads original/Cheshire_Cat_PCB.kicad_pcb (KiCad 4) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header, the eight TOPLEDs, the single shared resistor, the old tracks and the old pour
  - places the SAO++ parts on the back and routes them (single layer, back copper)
  - rebuilds the back copper (art + the old face pour) as the GND net, cleared around the new pads and tracks
  - rebuilds the back silkscreen art without the 2018 PCBWay logo and without ink on the new pads

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
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
from saopp_board import (ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "mad-cat"
SRC = os.path.join(HERE, "..", "original", "Cheshire_Cat_PCB.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND art
TRACK = 0.40
EDGE = 0.28         # copper stops this far short of the board edge

# ---- placement (centre x, y) ------------------------------------------------------------------
CONN = (147.0, 132.8)       # under the mouth, at the paws, where the 2018 header was
SW = (138.5, 99.43)         # flat top of the head between the ears; the knob points up and ends ~0.75 mm past the edge
BAT = (168.0, 79.0)         # on the tail, where the 2018 PCBWay logo was
BAT_CLOSED = (0.5, -0.866)  # which way the clip's closed end points; the cell slides in from the gap between head and tail
# LEDs keep their 2018 centres (eyes D1 D2, teeth D3..D8). Last number: +1 = anode pad right of centre, -1 = left.
LEDS = {
    "D1": (128.905, 109.284, +1), "D2": (148.082, 109.474, -1),
    "D3": (123.952, 119.317, +1), "D4": (128.969, 124.142, +1), "D5": (135.636, 125.730, +1),
    "D6": (142.177, 125.476, -1), "D7": (148.399, 124.333, -1), "D8": (153.352, 119.444, -1),
}
R_UP = 2.5                  # each tooth LED's resistor sits this far above it
R_EYE = 5.4                 # each eye LED's resistor sits this far toward the nose, outside the eye's clear window
WINDOW = 1.6                # radius kept free of back copper behind each LED so light gets into the board

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 3797, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("X1", "R1") or re.fullmatch(r"D[1-8]", ref):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == sorted(["X1", "R1"] + list(LEDS)), _gone
_txt = cut_blocks(_txt, _cut)
# the art on the layers this script rebuilds (both copper layers, back silkscreen) is read from the untouched original below
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4)
          if any(f"(layer {L})" in _txt[b_ - 40:b_] for L in ("B.Cu", "F.Cu", "B.SilkS"))]
assert len(_polys) == 19 + 26 + 14, f"expected 19 back copper + 26 front copper + 14 back silk art polygons, found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
_frames = stray_frames(_txt, 95)         # the 2018 SVG export's page frame, still on the front silk and front mask layers
assert len(_frames) == 2, len(_frames)
_txt = cut_blocks(_txt, _frames)
_tmp = os.path.join(tempfile.mkdtemp(), "Cheshire_Cat_PCB.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
art = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, B_Cu):
    art.Append(p_)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, pcbnew.F_Cu):
    front.Append(p_)
silk_parts = footprint_polys(_orig, B_SilkS)
assert len(silk_parts) == 14
_pours = [z for z in _orig.Zones() if not z.GetIsRuleArea()]
assert len(_pours) == 1, "expected the single 2018 ground pour behind the face"
art.Append(_pours[0].Outline())          # in 2018 the face and paws were a ground pour, not drawn art: same copper, made solid here
art.Simplify()
front.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 3797 short segments; outline.json is the same path as one closed polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where copper may be; also drops the stray frame the 2018 SVG export left outside the board
art.BooleanIntersection(inner)
ART_2018 = pcbnew.SHAPE_POLY_SET(art)    # kept to check that new tracks do not run through the lettering

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


def padpos(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as the 2018 header
sw = place("SW1", SW, ("1", (SW[0] - 3.0, SW[1] + 1.43)))            # knob toward the top edge
EYES = ("D1", "D2")
led, res = {}, {}
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    led[ref] = place(ref, (x, y), ("2", (x + s * 1.55, y)))
    if ref in EYES:
        res["R" + n] = place("R" + n, (x + s * R_EYE, y), ("1", (x + s * (R_EYE + 0.825), y)))
    else:
        res["R" + n] = place("R" + n, (x, y - R_UP), ("1", (x - s * 0.825, y - R_UP)))   # pad 1 (supply side) away from the anode

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
_pa, _pb = [mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"]
assert abs((_pa[0] - _pb[0]) * BAT_CLOSED[0] + (_pa[1] - _pb[1]) * BAT_CLOSED[1]) < 0.05, "clip pads are not square to the closed end"
_best = (1, _rot)
link(bat, "BT1")
print("battery clip angle", _best[1])

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(inner)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {EDGE} mm to the board edge"


# ---- routing (back copper only) -----------------------------------------------------------------
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


j1 = padpos(conn, "1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")

# each LED: resistor pad 2 -> across -> down to the anode pad
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    if ref in EYES:
        route(f"LED{n}_A", [padpos(res["R" + n], "2"), padpos(led[ref], "2")])
    else:
        route(f"LED{n}_A", [padpos(res["R" + n], "2"), (x + s * 1.55, y - R_UP), padpos(led[ref], "2")])
rp = {r: padpos(fp, "1") for r, fp in res.items()}       # supply-side pad of each resistor

# switched supply: switch pin 3 -> straight down the middle of the face
FORK = (s3[0], 119.6)
route("VLOAD", [s3, FORK])
route("VLOAD", [rp["R1"], (s3[0], rp["R1"][1])])        # eye resistors sit either side of that line
route("VLOAD", [rp["R2"], (s3[0], rp["R2"][1])])
# ... and two branches that follow the smile above the teeth, one stub down to each tooth resistor
UP = 1.42
route("VLOAD", [FORK, (137.8, rp["R5"][1] - UP), (rp["R5"][0], rp["R5"][1] - UP), rp["R5"]])
route("VLOAD", [(rp["R5"][0], rp["R5"][1] - UP), (130.6, rp["R4"][1] - UP), (rp["R4"][0], rp["R4"][1] - UP), rp["R4"]])
route("VLOAD", [(rp["R4"][0], rp["R4"][1] - UP), (126.9, 119.0), (126.9, rp["R3"][1] - UP), (rp["R3"][0], rp["R3"][1] - UP), rp["R3"]])
route("VLOAD", [FORK, (141.95, rp["R6"][1] - UP), (rp["R6"][0], rp["R6"][1] - UP), rp["R6"]])
route("VLOAD", [(rp["R6"][0], rp["R6"][1] - UP), (147.6, rp["R7"][1] - UP), (rp["R7"][0], rp["R7"][1] - UP), rp["R7"]])
route("VLOAD", [(rp["R7"][0], rp["R7"][1] - UP), (150.4, 119.2), (150.4, 116.4), (151.3, rp["R8"][1] - UP), (rp["R8"][0], rp["R8"][1] - UP), rp["R8"]])

# badge 3.3 V: connector pin 1 -> under the teeth -> up the left cheek -> across the forehead -> switch pin 1
route("VSAO", [j1, (j1[0], 128.4), (127.4, 128.4), (120.8, 121.8), (120.8, 108.8), (125.6, 104.0), (133.4, 104.0), (s1[0], 101.9), s1])

# coin cell +: switch pin 4 -> across the forehead -> down the right cheek -> haunch -> past the lettering -> up the tail
# The maker's credit lettering is cut out of the haunch copper edge to edge, so the only way past without touching a
# letter is the 1.3 mm between the first letter and the board edge: a thin track follows the edge there.
HUG = 0.25                                               # track width beside the lettering
_in = grown(body, -(EDGE + HUG / 2 + 0.02))
_o = _in.Outline(0)
_pts = [(ToMM(_o.CPoint(k).x), ToMM(_o.CPoint(k).y)) for k in range(_o.PointCount())]
_sel = [k for k, (x, y) in enumerate(_pts) if 164.3 < x < 170.4 and 101.5 < y < 107.6]
assert _sel and _sel == list(range(_sel[0], _sel[-1] + 1)), "edge points beside the lettering are not one run"
hug = [_pts[k] for k in _sel]
if hug[0][1] < hug[-1][1]:
    hug.reverse()                                        # run from the head end (low on the board) to the tail end
_thin = [hug[0]]
for p_ in hug[1:]:
    if math.hypot(p_[0] - _thin[-1][0], p_[1] - _thin[-1][1]) >= 0.3:
        _thin.append(p_)
hug = [(round(x, 4), round(y, 4)) for x, y in _thin]
bt_a = padpos(bat, "1", pick=lambda p: -p[0])            # clip pad nearer the tail's root (right in front view)
bt_b = padpos(bat, "1", pick=lambda p: p[0])
route("VBAT", [s4, (s4[0], 102.2), (143.3, 104.0), (152.3, 104.0), (156.6, 108.3), (156.6, 114.5), (158.0, 115.9),
               (161.6, 115.9), (163.5, 111.6)])
route("VBAT", [(163.5, 111.6)] + hug + [(173.0, 103.2)], width=HUG, clear=0.2)
route("VBAT", [(173.0, 103.2), (178.4, 103.2), (181.2, 100.4), (181.2, 91.0), bt_a])
# the clip itself joins its two pads; this link round the closed end makes the board agree without relying on it
_a0 = math.degrees(math.atan2(bt_a[1] - BAT[1], bt_a[0] - BAT[0]))
_r = math.hypot(bt_a[0] - BAT[0], bt_a[1] - BAT[1])
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 - d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 - d)), 4)) for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_a] + _arc + [bt_b])

# ---- GND copper: 2018 art + pour, cleared around everything that is not GND ------------------------
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
for x, y, _s in LEDS.values():                           # light path behind the eyes and teeth
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# no new track may run through the maker's lettering: every channel must lie on copper that was solid in 2018,
# except on the tail (the cell area) and where it meets its own pads
_let = grown(body, -0.9)                                 # (the 2018 art already stopped ~0.45 mm short of the edge: that margin is not lettering)
_let.BooleanSubtract(ART_2018)
_let.BooleanIntersection(poly([(161.5, 100.5), (188, 100.5), (188, 137), (161.5, 137)]))   # the haunch, where the lettering is
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(_let)
assert area_mm2(_hit) < 0.01, f"a track channel overlaps the haunch lettering by {area_mm2(_hit):.3f} mm2"

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
    add_filled(board, piece, B_Cu, nets["GND"] if touches else None)
    n_gnd += touches
    n_art += not touches
    if not touches:
        print("  plain art piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain art", n_art)

# ---- front copper art: same shapes as 2018, minus the window the old through-hole header sat in ----
fgaps = pcbnew.SHAPE_POLY_SET(body)
fgaps.BooleanSubtract(front)
fgaps.BooleanIntersection(poly([(143.2, 132.0), (150.9, 132.0), (150.9, 139.4), (143.2, 139.4)]))
fgaps.Simplify()
_filled = 0
for i in range(fgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(fgaps.Polygon(i))
    if one.Contains(P(147.002, 135.7)):
        front.BooleanAdd(one)
        _filled = area_mm2(one)
assert 15 < _filled < 60, f"front window at the old header: {_filled:.1f} mm2"
print("filled old header window on the front, area mm2:", round(_filled, 1))
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(pegs)
front.BooleanIntersection(inner)
front.Simplify()
add_filled(board, front, pcbnew.F_Cu)

# ---- back silkscreen labels (the art is cleared behind each one so it reads on dark mask) -----------
LABELS = [("SAO", s1[0] - 1.6, 102.75, 0.8, 0), ("OFF", SW[0], 102.75, 0.8, 0), ("BAT", s4[0] + 1.6, 102.75, 0.8, 0),
          ("CR2032 + SIDE UP", 186.0, 84.0, 0.9, 90), ("SAO++ rA", 132.0, 114.0, 0.9, 0), ("1", CONN[0] - 8.7, j1[1], 0.9, 0)]
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
    behind.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                        (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
behind.Simplify()

# ---- back silkscreen art: 2018 shapes, minus the PCBWay logo, minus ink on the new pads -------------
LOGO = [(153.3, 86.0), (154.3, 81.6), (165.5, 75.0), (169.6, 77.4), (169.9, 80.2), (157.4, 88.2)]     # the dark tail stripe the logo sat on
silk = pcbnew.SHAPE_POLY_SET()
_dropped = 0
for p_ in silk_parts:
    x0, y0, x1, y1 = bbox_mm(p_)
    if x1 - x0 > 60:
        if (x0, y0) < (110, 45):
            continue                                     # the stray frame from the 2018 SVG export
    elif 157 < x0 and x1 < 168.5 and 76 < y0 and y1 < 85:
        _dropped += 1                                    # a logo letter
        continue
    silk.Append(p_)
assert _dropped == 5, f"expected 5 separate logo letters, dropped {_dropped}"
silk.Simplify()
# the rest of the logo (the 'y' and the underline) is joined to the stripe below it: inside the logo's stripe, keep
# only ink thicker than 0.9 mm (the stripes), which drops the thin strokes
_win = poly(LOGO)
_in_win = pcbnew.SHAPE_POLY_SET(silk)
_in_win.BooleanIntersection(_win)
_before = area_mm2(_in_win)
_in_win.Fracture()
_keep = pcbnew.SHAPE_POLY_SET()
for i in range(_in_win.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET()
    one.AddOutline(_in_win.Outline(i))
    one.Inflate(-FromMM(0.45), ROUND, ERR)
    one.Inflate(FromMM(0.45), ROUND, ERR)
    _keep.Append(one)
_keep.Simplify()
_keep.BooleanIntersection(_win)
silk.BooleanSubtract(_win)
silk.BooleanAdd(_keep)
print("logo remnants removed from the back silk, mm2:", round(_before - area_mm2(_keep), 2))
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.2))
bare.Simplify()
silk.BooleanSubtract(bare)
silk.BooleanSubtract(behind)
silk.BooleanIntersection(body)
silk.Simplify()
add_filled(board, silk, B_SilkS)


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
