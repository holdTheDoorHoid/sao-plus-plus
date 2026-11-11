#!/usr/bin/env python3
"""Rebuild big-green.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/big-green/hardware/build_board.py

What it does
  - loads original/Piccolo_PCB.kicad_pcb (KiCad 4) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header, the two TOPLEDs, the single shared resistor, the old tracks and the old pour
  - places the SAO++ parts on the back and routes them (single layer, back copper)
  - rebuilds the back copper (art + the old pour behind the chin) as the GND net, cleared around the new pads and tracks
  - rebuilds the back silkscreen art (the dragon) without the 2018 page frame and without ink on the new pads

Coordinates are millimetres in KiCad's front view (x grows right, y grows down). "Left" and "right" below are as seen
from the FRONT (the face); on the back everything is mirrored.

Layout in one paragraph: the connector sits under the mouth on the chin, where the 2018 header was. The switch sits on
the left side of the head (front view), its knob poking into the notch between the head and the left ear. The coin
cell sits on the back of the right half of the forehead and slides in from the top of the head. The three supply wires
run from the switch down the left side of the head, then across under the forehead art, to the cell, the two eye
resistors and the connector. The maker's credit (left ear), the title "BIG GREEN" (right ear), the two dragon balls,
the kanji and the Goku portrait in the back copper are all routed around, not through.
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

SLUG = "big-green"
SRC = os.path.join(HERE, "..", "original", "Piccolo_PCB.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND art
TRACK = 0.40
EDGE = 0.28         # copper stops this far short of the board edge
LANE = 0.80         # spacing of parallel tracks (0.4 mm copper, 0.4 mm gap)

# ---- placement (centre x, y) ------------------------------------------------------------------
# Connector: on the chin, centred left-to-right, where the 2018 header was (145.0, 117.6), moved 9 mm up the chin
# so its plastic body stays 3 mm from the pointed jaw edges (the chin is only 14 mm wide at the old header).
CONN = (144.78, 108.5)
# Switch: on the left side of the head, the one spot on the outline that is nearly straight for 12 mm and has no
# lettering behind it (the ear edges are straight but carry the credit and the title). Knob points left into the
# notch between head and ear. SW_X is worked out below: as close to the edge as the pads allow.
SW_Y = 77.0
# Coin cell: on the right half of the forehead, over the kanji's sweeping right stroke. The open side faces the top of
# the head, so the cell slides in from the top edge over bare board. Clear of the connector, switch, eyes and lettering.
BAT = (156.0, 81.0)
BAT_CLOSED = (0.0, 1.0)     # which way the clip's closed end points (down, toward the eyes)
# LEDs keep their 2018 centres (the two pupils). Last number: +1 = anode pad right of centre, -1 = left.
LEDS = {"D1": (135.763, 95.5675, +1), "D2": (152.654, 95.123, +1)}
R_EYE = 5.4                 # each eye LED's resistor sits this far to the right, outside the eye's clear window
WINDOW = 1.6                # radius kept free of copper (both sides) and back ink behind each LED so light gets in

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
assert len(_cut) == 9 + 3, len(_cut)
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 2957, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("X1", "R1", "D1", "D2"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["D1", "D2", "R1", "X1"], _gone
_txt = cut_blocks(_txt, _cut)
# the art on the layers this script rebuilds (both copper layers, back silkscreen) is read from the untouched original below
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4)
          if any(f"(layer {L})" in _txt[b_ - 40:b_] for L in ("B.Cu", "F.Cu", "B.SilkS"))]
assert len(_polys) == 28 + 13 + 465, f"expected 28 back copper + 13 front copper + 465 back silk art polygons, found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
_frames = stray_frames(_txt, 85)         # the 2018 SVG export's page frame (90 mm wide), still on the front silk and front mask
assert len(_frames) == 2, len(_frames)
_txt = cut_blocks(_txt, _frames)
_tmp = os.path.join(tempfile.mkdtemp(), "Piccolo_PCB.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
art = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, B_Cu):
    art.Append(p_)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, pcbnew.F_Cu):
    front.Append(p_)
silk_parts = footprint_polys(_orig, B_SilkS)
assert len(silk_parts) == 465
_pours = [z for z in _orig.Zones() if not z.GetIsRuleArea()]
assert len(_pours) == 1, "expected the single 2018 ground pour behind the chin"
# in 2018 the area behind the eyes and chin was a ground pour, not drawn art: made solid here. The art's cut-out for the
# pour is a hair smaller than the pour's outline, which leaves hairline slits along its edges; growing the pour 0.2 mm closes them
art.Append(grown(_pours[0].Outline(), 0.2))
art.Simplify()
front.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 2957 short segments; outline.json is the same path as one closed polygon ----
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
# At the panel's break-off tabs (production/panel.json) the 0.5 mm mouse-bite holes sit on the edge line and reach
# 0.25 mm in: there, both copper layers stop 0.55 mm short of the edge so the holes stay 0.25 mm clear of copper.
TABZONE = pcbnew.SHAPE_POLY_SET()
for _t in json.load(open(os.path.join(HERE, "..", "production", "panel.json")))["tabs"]:
    add_circle(TABZONE, P(*_t["near"]), 4.0)
TABZONE.Simplify()
_band = pcbnew.SHAPE_POLY_SET(body)
_band.BooleanSubtract(grown(body, -0.55))
TABZONE.BooleanIntersection(_band)       # the thin strip along the edge beside each tab
art.BooleanIntersection(inner)
ART_2018 = pcbnew.SHAPE_POLY_SET(art)    # kept to check that new tracks do not run through the lettering or the drawn art

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


def pads_inside(fp):
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(inner)
            if off.OutlineCount():
                return False
    return True


def edge_x_left(y):
    """x of the left side of the head on the horizontal line y (front view), from the outline."""
    pts = _ol["outer"]
    xs = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        if (ay - y) * (by - y) < 0:
            xs.append(ax + (y - ay) / (by - ay) * (bx - ax))
    return max(x for x in xs if 115 < x < 125)        # (the left ear's top edge crosses further left)


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as the 2018 header
# Switch: on the back the footprint is mirrored, so with the knob pointing left pin 1 is the bottom pin.
# Slide it toward the edge until a pad would come closer than EDGE to the outline; one step back is SW_X.
SW_X = None
sw = None
for k in range(0, 200):
    x = round(121.4 + 0.01 * k, 2)
    if sw is None:
        sw = place("SW1", (x, SW_Y), ("1", (x + 1.43, SW_Y + 3.0)))
    else:
        sw.SetPosition(P(x, SW_Y))
    if pads_inside(sw):
        SW_X = x
        break
assert SW_X is not None and SW_X < 123.0, SW_X
SW = (SW_X, SW_Y)
KNOB_OUT = edge_x_left(SW_Y) - (SW_X - 3.1)                # knob tip is 3.1 mm from the switch centre
print(f"switch centre x {SW_X}; knob tip {KNOB_OUT:.2f} mm past the edge")
assert KNOB_OUT > 0.5, "knob does not reach far enough past the edge"
led, res = {}, {}
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    led[ref] = place(ref, (x, y), ("2", (x + s * 1.55, y)))
    res["R" + n] = place("R" + n, (x + s * R_EYE, y), ("1", (x + s * (R_EYE + 0.825), y)))   # pad 1 (supply side) away from the LED

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
assert abs(_closed_dir(_rot) - math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0]))) < 1, "clip closed end points the wrong way"
_pa, _pb = [mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"]
assert abs((_pa[0] - _pb[0]) * BAT_CLOSED[0] + (_pa[1] - _pb[1]) * BAT_CLOSED[1]) < 0.05, "clip pads are not square to the closed end"
link(bat, "BT1")
print("battery clip angle", _rot)
# the clip body (metal over the cell): anything drawn under it is hidden once the part is fitted
_cb = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
CLIP_BODY = poly([(ToMM(_cb.GetLeft()), ToMM(_cb.GetTop())), (ToMM(_cb.GetRight()), ToMM(_cb.GetTop())),
                  (ToMM(_cb.GetRight()), ToMM(_cb.GetBottom())), (ToMM(_cb.GetLeft()), ToMM(_cb.GetBottom()))])

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        assert pads_inside(fp), f"{fp.GetReference()}: a pad is closer than {EDGE} mm to the board edge"


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
assert s4[1] < s3[1] < s1[1], "expected switch pins 4, 3, 1 from top to bottom"
rp = {r: padpos(fp, "1") for r, fp in res.items()}       # supply-side pad of each resistor

# each LED: resistor pad 2 -> straight across to the anode pad
for ref in LEDS:
    n = ref[1:]
    route(f"LED{n}_A", [padpos(res["R" + n], "2"), padpos(led[ref], "2")])

# Three wires leave the switch to the right and run down the plain copper strip between the head's left edge and the
# kanji, in three lanes. The top pin (cell) takes the inside lane, the bottom pin (badge) the outside lane, so they never cross.
X_SAO = 125.0                            # outside lane: clear of the credit lettering ("By ...") by > 1 mm
X_LOAD = X_SAO + LANE
X_BAT = X_SAO + 2 * LANE                 # inside lane: clear of the kanji's lower-left stroke by > 1 mm
Y_BAT = 89.9                             # cell wire runs across under the kanji ...
Y_LOAD = 92.3                            # ... the LED supply below it, below the bottom of the cell clip's ground loop
bt_l = padpos(bat, "1", pick=lambda p: p[0])            # clip pad on the left (front view), toward the eyes
bt_r = padpos(bat, "1", pick=lambda p: -p[0])

# coin cell +: switch pin 4 -> inside lane -> across under the forehead art -> up into the left clip pad (under the clip)
route("VBAT", [s4, (X_BAT, s4[1]), (X_BAT, Y_BAT), (bt_l[0], Y_BAT), bt_l])
# the clip itself joins its two pads; this link round the closed end (hidden under the clip) makes the board agree
_a0 = math.degrees(math.atan2(bt_r[1] - BAT[1], bt_r[0] - BAT[0]))
_r = math.hypot(bt_r[0] - BAT[0], bt_r[1] - BAT[1])
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 + d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 + d)), 4)) for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_r] + _arc + [bt_l])
assert max(p[1] for p in _arc) + TRACK + 0.15 < Y_LOAD, "pad link runs into the LED supply"

# switched supply: switch pin 3 -> middle lane -> across below the cell wire -> one drop to each eye resistor
route("VLOAD", [s3, (X_LOAD, s3[1]), (X_LOAD, Y_LOAD), (rp["R1"][0], Y_LOAD), rp["R1"]])
route("VLOAD", [(rp["R1"][0], Y_LOAD), (rp["R2"][0], Y_LOAD), rp["R2"]])

# badge 3.3 V: switch pin 1 -> outside lane -> round the left dragon ball -> down the left cheek -> connector pin 1
Y_TURN = Y_LOAD + LANE                   # passes under the LED supply's corner
X_CHEEK = 128.6                          # between the left dragon ball and the left eye LED
route("VSAO", [s1, (X_SAO, s1[1]), (X_SAO, Y_TURN), (X_CHEEK, Y_TURN), (X_CHEEK, 99.5), (X_CHEEK + (j1[1] - 99.5), j1[1]), j1])

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
lights = pcbnew.SHAPE_POLY_SET()
for x, y, _s in LEDS.values():                           # light path behind the eyes
    add_circle(lights, P(x, y), WINDOW)
cut.Append(lights)
cut.Simplify()
art.BooleanSubtract(cut)
art.BooleanSubtract(TABZONE)
art.Simplify()

# no new track may run through the maker's lettering or the drawn art: every channel must lie on copper that was
# solid in 2018, except under the cell clip (hidden by the clip once fitted)
_let = grown(body, -0.9)                                 # (the 2018 art stops ~0.45 mm short of the edge: that margin is not art)
_let.BooleanSubtract(ART_2018)
_let.BooleanSubtract(CLIP_BODY)
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(_let)
assert area_mm2(_hit) < 0.01, f"a track channel overlaps lettering or drawn art by {area_mm2(_hit):.3f} mm2 at {bbox_mm(_hit)}"
# and the credit lettering (left ear) and title (right ear) keep their shape: no copper is removed within 0.5 mm of
# any letter (the letters are cut out of the copper, so a cut near one would merge into it)
for name, box in (("credit", [(105, 66), (124.4, 66), (124.4, 101), (105, 101)]), ("title", [(165.5, 70), (185, 70), (185, 95), (165.5, 95)])):
    letters = grown(body, -0.9)
    letters.BooleanSubtract(ART_2018)
    letters.BooleanIntersection(poly(box))
    near = grown(letters, 0.5)
    lost = pcbnew.SHAPE_POLY_SET(ART_2018)
    lost.BooleanSubtract(art)
    lost.BooleanIntersection(near)
    print(f"  {name}: back copper removed within 0.5 mm of a letter: {area_mm2(lost):.3f} mm2")
    assert area_mm2(lost) < 0.01, f"{name} lettering touched at {bbox_mm(lost)}"

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
    if not touches and area_mm2(piece) > 1:
        print("  plain art piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain art", n_art)

# ---- front copper art: same shapes as 2018, minus the window the old through-hole header sat in ----
fgaps = pcbnew.SHAPE_POLY_SET(body)
fgaps.BooleanSubtract(front)
fgaps.BooleanIntersection(poly([(141.5, 114.0), (148.5, 114.0), (148.5, 120.6), (141.5, 120.6)]))
fgaps.Simplify()
_filled = 0
for i in range(fgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(fgaps.Polygon(i))
    if one.Contains(P(145.034, 117.602)):
        front.BooleanAdd(one)
        _filled = area_mm2(one)
assert 10 < _filled < 40, f"front window at the old header: {_filled:.1f} mm2"
print("filled old header window on the front, area mm2:", round(_filled, 1))
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(pegs)
front.BooleanIntersection(inner)
_t0 = area_mm2(front)
front.BooleanSubtract(TABZONE)
print("front copper trimmed at the panel tabs, mm2:", round(_t0 - area_mm2(front), 3))
_eyes = pcbnew.SHAPE_POLY_SET(front)
_eyes.BooleanIntersection(lights)
print("front copper removed inside the LED windows, mm2:", round(area_mm2(_eyes), 2))
front.BooleanSubtract(lights)                            # the 2018 eye outline reached a little way into the 1.6 mm windows
front.Simplify()
add_filled(board, front, pcbnew.F_Cu)

# ---- back silkscreen labels (the dragon is cleared behind each one so it reads) -----------------
LABELS = [("BAT", 130.0, s4[1], 0.8, 0), ("OFF", 130.0, SW[1], 0.8, 0), ("SAO", 130.0, s1[1], 0.8, 0),
          ("CR2032 + SIDE UP", BAT[0], BAT[1] - 13.6, 0.9, 0), ("SAO++ rA", CONN[0], 117.4, 0.9, 0),
          ("1", 136.2, j1[1] - 1.9, 0.9, 0)]
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

# ---- back silkscreen art: the 2018 dragon, minus the page frame, minus ink on the new pads and LED windows ----
silk = pcbnew.SHAPE_POLY_SET()
_frame = 0
for p_ in silk_parts:
    x0, y0, x1, y1 = bbox_mm(p_)
    if x0 < 104 and x1 - x0 > 85:
        _frame += 1                                      # the stray page frame from the 2018 SVG export
        continue
    silk.Append(p_)
assert _frame == 1, _frame
silk.Simplify()
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.2))
bare.Append(lights)                                      # no ink between each LED's lens and the board
bare.Simplify()
_before = area_mm2(silk)
silk.BooleanSubtract(bare)
silk.BooleanSubtract(behind)
silk.BooleanIntersection(body)
silk.Simplify()
print("back silk ink removed (pads, LED windows, behind labels), mm2:", round(_before - area_mm2(silk), 2))
add_filled(board, silk, B_SilkS)


# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("SW1 pegs:", [mm(p.GetPosition()) for p in sw.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH])
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
