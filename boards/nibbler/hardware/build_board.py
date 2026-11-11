#!/usr/bin/env python3
"""Rebuild nibbler.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  python3 boards/nibbler/hardware/fix_outline.py            (system Python; only needed if outline.json is missing)
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nibbler/hardware/build_board.py

What it does
  - loads original/Nibbler_PCB.kicad_pcb (KiCad 4) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header, the three TOPLEDs, the single shared resistor, the old tracks and zones
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - rebuilds the back copper as the GND net: the 2018 board was one big ground pour with the mouth and the belly kept
    bare; that is kept, except that the mouth under the new connector and the belly under the coin cell are now covered
  - rebuilds the front mask so the foot, where the old header was, is plain bare board
  - rebuilds the back silkscreen art without ink on the new pads, behind the new labels and behind the clip's markings

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).

Why the parts sit where they do (the short version; details next to each number below)
  - The coin cell needs a clear 20 mm circle. On this board the only such circle that does not cover the maker's
    lettering or an eye is in the lower body (the diaper), so the cell goes there, open side down toward the foot.
  - The 2018 header sat in the foot, which is 9 mm wide; the new connector's body is 15.3 mm wide. With the cell in the
    lower body, the only place left for the connector is the chest, under the mouth, between the two eyes.
  - The switch needs a straight edge about 12 mm long. The best there is is the top of the head, just right of the
    stalk: a gentle arc, so the switch is tilted 4 degrees to follow it, knob up.
  - Routing on one layer with no vias: the switch pins run SAO, OFF, LOAD, BAT from left to right, so the badge-power
    track (left pin) would cut the stalk and left eye off from the LED supply. The LED supply instead passes under the
    connector, between its two rows of pins (where pins 3-6 are unused), and comes back up on the left of the connector.
    The battery track loops round the right eye so that eye stays on the LED-supply side.
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, B_Mask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "nibbler"
SRC = os.path.join(HERE, "..", "original", "Nibbler_PCB.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND art
TRACK = 0.40
THIN = 0.25         # tracks that squeeze between connector pins, past an eye, or up the stalk
EDGE = 0.55         # copper stops this far short of the board edge (the panel's mouse-bite holes reach 0.25 mm in)
WINDOW = 1.6        # radius kept free of back copper behind each LED so light gets into the board

# ---- placement (centre x, y) ------------------------------------------------------------------
CONN = (143.1, 88.0)        # chest, under the mouth, between the eyes (see the docstring for why not the foot)
BAT = (139.0, 111.0)        # lower body; a 10.3 mm circle here clears the lettering, the eyes and the board edge
BAT_CLOSED = (0.0, -1.0)    # closed end of the clip points up; the cell slides in from below, over the foot
SW_X, TILT = 143.5, 4.0      # the head top is an arc, not a straight line. A scan of centre and tilt (tabs >= 0.27 mm
                            # inside, body corners on the board) found the knob reaches furthest past the edge with the
                            # switch at the left end of the arc, tilted 4 degrees to follow it, its left tabs at the
                            # foot of the stalk: 0.8 mm past the edge here, against ~0.3 mm in the middle of the arc
KNOB_OUT = 0.75             # how far the knob tip should reach past the edge (Mad Cat: 0.75)
# LEDs keep their 2018 centres. Last item: the direction from the centre to the anode pad.
LEDS = {
    "D1": (136.9568, 81.7372, (+1, 0)),     # left eye; anode right, toward its resistor
    "D2": (153.7716, 79.9084, (-1, 0)),     # right eye; anode left, toward its resistor
    "D3": (138.3792, 59.5376, (+1, 0)),     # third eye on the stalk; anode right, the stalk track arrives there
}
LEG = 139.5                 # x of the LED-supply track that runs back up on the left of the connector
R1_AT = (LEG - 0.825, 79.0)  # D1's resistor: supply pad sits on that track, other pad just above the eye's anode
R2_AT = (149.9, 79.9084)     # D2's resistor, left of the right eye
R3_AT = (LEG - 1.9, 76.3)    # D3's resistor, left of that track's top end, under the stalk

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
assert len(_cut) == 42 + 7, len(_cut)
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 10700, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("X1", "R1", "D1", "D2", "D3"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["D1", "D2", "D3", "R1", "X1"], _gone
_txt = cut_blocks(_txt, _cut)
# the art on the layers this script rebuilds (front copper and mask, back silkscreen and mask) is read from the untouched original
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4)
          if any(f"(layer {L})" in _txt[b_ - 40:b_] for L in ("F.Cu", "F.Mask", "B.SilkS", "B.Mask"))]
assert len(_polys) == 9 + 13 + 68 + 3, f"expected 9 front copper + 13 front mask + 68 back silk + 3 back mask polygons, found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
_frames = stray_frames(_txt, 70)         # the 2018 SVG export's page frame, still on the front silk layer
assert len(_frames) == 1, len(_frames)
_txt = cut_blocks(_txt, _frames)
_tmp = os.path.join(tempfile.mkdtemp(), "Nibbler_PCB.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)


def no_frame(parts):
    """Drop the page frame (the only art polygon wider than 70 mm)."""
    keep = [p_ for p_ in parts if bbox_mm(p_)[2] - bbox_mm(p_)[0] < 70]
    assert len(keep) == len(parts) - 1, "expected exactly one page frame"
    return keep


_orig = pcbnew.LoadBoard(SRC)
front = pcbnew.SHAPE_POLY_SET()
for p_ in no_frame(footprint_polys(_orig, pcbnew.F_Cu)):
    front.Append(p_)
front.Simplify()
silk_parts = no_frame(footprint_polys(_orig, B_SilkS))
mask_parts = no_frame(footprint_polys(_orig, B_Mask))
fmask_parts = no_frame(footprint_polys(_orig, pcbnew.F_Mask))
assert len(silk_parts) == 67 and len(mask_parts) == 2
# the 2018 back copper was one pour over the whole board; six keep-out areas held it off the LEDs, the mouth and the belly
_keep = [z for z in _orig.Zones() if z.GetIsRuleArea()]
assert len(_keep) == 6, len(_keep)
bare_2018 = pcbnew.SHAPE_POLY_SET()      # where the 2018 back had no copper (mouth and belly; the LED squares are redone below)
for z in _keep:
    o = z.Outline()
    if area_mm2(o) > 1.0:                # (the three LED squares are ~9 mm2 each; the mouth and belly are far bigger)
        if area_mm2(o) > 20:
            bare_2018.Append(o)
    else:
        bare_2018.Append(o)              # a 0.03 mm2 sliver the maker drew at the corner of the mouth
assert bare_2018.OutlineCount() == 3, bare_2018.OutlineCount()
bare_2018.Simplify()

# lettering: "Made By TwinkleTwinkie" and "Nibbler - A DC26 Add-on" are back silkscreen letters along the left side
LETTERS = pcbnew.SHAPE_POLY_SET()
for p_ in silk_parts:
    x0, y0, x1, y1 = bbox_mm(p_)
    if x1 - x0 < 2.3 and y1 - y0 < 2.3 and x1 < 135:
        LETTERS.Append(p_)
assert LETTERS.OutlineCount() == 47, LETTERS.OutlineCount()
LETTERS.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 10,700 short segments with a tiny self-crossing at the top of the stalk.
#      fix_outline.py repaired it into outline.json; it is drawn here as one closed polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where copper may be
padzone = grown(body, -0.27)             # every new pad must lie inside this (brief: >= 0.25 mm from the edge)

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


def inside(ps, zone):
    off = pcbnew.SHAPE_POLY_SET(ps)
    off.BooleanSubtract(zone)
    return area_mm2(off) < 1e-6


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as Mad Cat
led, res = {}, {}
for ref, (x, y, (dx, dy)) in LEDS.items():
    led[ref] = place(ref, (x, y), ("2", (x + 1.55 * dx, y + 1.55 * dy)))
res["R1"] = place("R1", R1_AT, ("1", (R1_AT[0] + 0.825, R1_AT[1])))    # supply pad right, on the supply track
res["R2"] = place("R2", R2_AT, ("1", (R2_AT[0] - 0.825, R2_AT[1])))    # supply pad left, away from the eye
res["R3"] = place("R3", R3_AT, ("1", (R3_AT[0] + 0.825, R3_AT[1])))    # supply pad right, on the supply track

# ---- switch: tilted TILT degrees, then pushed out until the knob reaches KNOB_OUT past the edge, as long as every
#      solder tab stays inside ----
sw = load("SW1", (SW_X, 76.0))


def sw_geometry(fp):
    """Knob tip and body corners from the pad positions (the pin row is 1.43 mm behind the footprint centre)."""
    c = mm(fp.GetPosition())
    pins = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() in ("1", "2", "3", "4")]
    m = (sum(p_[0] for p_ in pins) / 4, sum(p_[1] for p_ in pins) / 4)
    u = ((c[0] - m[0]) / 1.43, (c[1] - m[1]) / 1.43)                 # unit vector toward the knob
    v = (-u[1], u[0])
    tip = (c[0] + 3.1 * u[0], c[1] + 3.1 * u[1])
    corners = [(c[0] + 1.6 * u[0] + s * 4.85 * v[0], c[1] + 1.6 * u[1] + s * 4.85 * v[1]) for s in (-1, 1)]
    return u, tip, corners


best = None
for rot in (0, 90, 180, 270):            # which right-angle orientation points the knob up with pin 1 on the left
    sw.SetOrientationDegrees(rot - TILT)   # KiCad angles turn anticlockwise on screen
    u, _, _ = sw_geometry(sw)
    p1 = padpos(sw, "1")
    p4 = padpos(sw, "4")
    if u[1] < -0.9 and p1[0] < p4[0]:
        best = rot
assert best is not None
sw.SetOrientationDegrees(best - TILT)
_placed = None
for k in range(0, 400):                  # slide the switch up 0.01 mm at a time
    off = 4.0 - k * 0.01
    u, _, _ = sw_geometry(sw)
    sw.SetPosition(P(SW_X, 72.0 + off))
    u, tip, corners = sw_geometry(sw)
    tabs_in = all(inside(pad_poly(p, B_Cu), padzone) for p in sw.Pads() if p.IsOnLayer(B_Cu))
    if not tabs_in:
        break
    if not body.Contains(P(*tip)):
        # how far past the edge is the tip?  step back along u until we are back on the board
        out = 0.0
        while not body.Contains(P(tip[0] - out * u[0], tip[1] - out * u[1])) and out < 3:
            out += 0.01
        _placed = (mm(sw.GetPosition()), out)
        if out >= KNOB_OUT:
            break
assert _placed is not None and _placed[1] >= 0.7, ("the switch knob does not reach far enough past the edge", _placed)
sw.SetPosition(P(*_placed[0]))
SW = _placed[0]
link(sw, "SW1")
_u, _tip, _corners = sw_geometry(sw)
KNOB_REACH = _placed[1]
print(f"switch at {SW}, tilt {TILT:.1f} deg, knob tip {KNOB_REACH:.2f} mm past the edge, body corners on board:",
      [body.Contains(P(*c_)) for c_ in _corners])

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
link(bat, "BT1")
print("battery clip angle", _rot)

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board, every pad at least 0.27 mm in from the edge
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                assert inside(pad_poly(pad, B_Cu), padzone), f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.27 mm to the board edge"

# the cell must not cover any lettering or part: its 10.3 mm circle may only hold the clip itself
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.3)
assert inside(_cell, body), "the coin cell hangs over the board edge"
_hit = pcbnew.SHAPE_POLY_SET(_cell)
_hit.BooleanIntersection(LETTERS)
assert area_mm2(_hit) < 1e-6, "the coin cell covers lettering"
for fp in board.GetFootprints():
    if fp.GetReference() in NEW and fp.GetReference() != "BT1":
        for pad in fp.Pads():
            h_ = pad_poly(pad, B_Cu)
            h_.BooleanIntersection(_cell)
            assert area_mm2(h_) < 1e-6, f"{fp.GetReference()} sits under the coin cell"


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
rp = {r: (padpos(fp, "1"), padpos(fp, "2")) for r, fp in res.items()}      # (supply pad, LED pad) of each resistor
an = {r: padpos(fp, "2") for r, fp in led.items()}                          # anode pad of each LED
GAP13 = j1[0] + 1.27                     # x between connector pins 1 and 3 (both rows have 1.44 mm between pads)
ROW = CONN[1]                            # y between the connector's two rows (2.4 mm between pad ends)

# badge 3.3 V: switch pin 1 -> straight down between the eyes -> top of connector pin 1
route("VSAO", [s1, (s1[0], 79.6), (j1[0], 81.8), j1])

# LED supply (switch pin 3). One branch to the right eye's resistor; the other goes down between connector pins 1 and 3,
# along the gap between the two rows of pins, out on the left, and back up past the left eye to the stalk.
KNEE = (s3[0], 77.6)
route("VLOAD", [s3, KNEE, (rp["R2"][0][0], KNEE[1]), rp["R2"][0]])
route("VLOAD", [KNEE, (KNEE[0], 80.0), (GAP13, 82.0), (GAP13, ROW), (LEG, ROW), rp["R1"][0], (LEG, R3_AT[1]), rp["R3"][0]], width=THIN)
route("LED1_A", [rp["R1"][1], (an["D1"][0], 79.9), an["D1"]], width=THIN)
route("LED2_A", [rp["R2"][1], an["D2"]], width=THIN)

# third eye: from its resistor along the right-hand wall of the stalk and the bottom of the eye circle, up to the anode.
# The stalk is 2.67 mm wide at its narrowest; the track keeps EDGE from the wall and leaves ~1 mm of GND copper beside it.
_in = grown(body, -(EDGE + THIN / 2 + 0.03))
_o = _in.Outline(0)
_pts = [(ToMM(_o.CPoint(k).x), ToMM(_o.CPoint(k).y)) for k in range(_o.PointCount())]
_sel = [k for k, (x, y) in enumerate(_pts)          # the stalk's right wall, then the bottom of the eye circle
        if (63.75 <= y < 70.0 and 135.0 < x < 137.0) or (61.8 < y < 63.75 and 136.3 < x < 139.3)]
assert _sel and _sel == list(range(_sel[0], _sel[-1] + 1)), "stalk wall points are not one run"
hug = [_pts[k] for k in _sel]
if hug[0][1] < hug[-1][1]:
    hug.reverse()                        # from the head end (low on the board) up to the eye
_thin = [hug[0]]
for p_ in hug[1:]:
    if math.hypot(p_[0] - _thin[-1][0], p_[1] - _thin[-1][1]) >= 0.3:
        _thin.append(p_)
hug = [(round(x, 4), round(y, 4)) for x, y in _thin]
route("LED3_A", [rp["R3"][1], (rp["R3"][1][0], 71.6), hug[0]] + hug + [(an["D3"][0], an["D3"][1] + 2.0), an["D3"]], width=THIN)

# coin cell +: switch pin 4 -> over and round the right eye -> under it -> down the right of the connector -> right clip pad
bt_r = padpos(bat, "1", pick=lambda p: -p[0])
bt_l = padpos(bat, "1", pick=lambda p: p[0])
route("VBAT", [s4, (s4[0], 76.6), (155.4, 76.6), (156.7, 77.9), (156.7, 81.2), (155.85, 82.05), (149.6, 82.05),
               (147.4, 90.0), (147.4, 97.5), (148.6, 103.5), bt_r], width=0.3)
# the clip itself joins its two pads; this link round the closed end makes the board agree without relying on it
_a0 = math.degrees(math.atan2(bt_r[1] - BAT[1], bt_r[0] - BAT[0]))
_r = math.hypot(bt_r[0] - BAT[0], bt_r[1] - BAT[1])
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 - d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 - d)), 4)) for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_r] + _arc + [bt_l], width=0.3)

# ---- GND copper: the 2018 pour, cleared around everything that is not GND ---------------------------
# The connector sits on the mouth, which the 2018 back left bare. Under the connector's body the mouth becomes copper,
# so the connector has ground pour round its pads; two small extensions cover the top of the nose (where the battery track
# comes in) and join the connector's pins to the chest copper below. The rest of the mouth (left corner, lower lip,
# snout) stays bare.
J1_BODY = (CONN[0] - 7.65, CONN[1] - 4.45, CONN[0] + 7.65, CONN[1] + 4.45)
PATCH = pcbnew.SHAPE_POLY_SET()
for x0, y0, x1, y1 in (J1_BODY, (144.0, 82.3, 150.4, J1_BODY[1] + 0.01), (139.6, J1_BODY[3] - 0.01, 148.0, 95.6)):
    PATCH.Append(poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
PATCH.Simplify()
CELL = pcbnew.SHAPE_POLY_SET()           # under the coin cell nothing may be bare: the cell's rim would sit on it
add_circle(CELL, P(*BAT), 11.0)
art = pcbnew.SHAPE_POLY_SET(inner)
_bare = pcbnew.SHAPE_POLY_SET(bare_2018)
_bare.BooleanSubtract(PATCH)
art.BooleanSubtract(_bare)
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)                          # solid copper under the cell so the bare cell pad is whole
art.BooleanAdd(disc)
art.BooleanIntersection(inner)

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
for x, y, _d in LEDS.values():                           # light path behind the three eyes
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()


def acute_tips(ps, limit=25.0):
    """Corners sharper than `limit` degrees: where two clearance cuts meet they leave copper wedges that DRC calls slivers."""
    tips = []
    for i in range(ps.OutlineCount()):
        for ch in [ps.Outline(i)] + [ps.Hole(i, h) for h in range(ps.HoleCount(i))]:
            n = ch.PointCount()
            pts = [(ToMM(ch.CPoint(k).x), ToMM(ch.CPoint(k).y)) for k in range(n)]
            for k in range(n):
                a, b, c = pts[k - 1], pts[k], pts[(k + 1) % n]
                v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
                l1, l2 = math.hypot(*v1), math.hypot(*v2)
                if l1 > 1e-4 and l2 > 1e-4:
                    cosang = (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                    if math.degrees(math.acos(max(-1.0, min(1.0, cosang)))) < limit:
                        tips.append(b)
    return tips


_n_tips = 0
for _ in range(3):                       # blunt every copper wedge tip with a 0.15 mm bite
    _tips = acute_tips(art)
    if not _tips:
        break
    _bite = pcbnew.SHAPE_POLY_SET()
    for x_, y_ in _tips:
        add_circle(_bite, P(x_, y_), 0.15, 24)
    _n_tips += len(_tips)
    art.BooleanSubtract(_bite)
    art.Simplify()
print("copper wedge tips blunted:", _n_tips, "left:", len(acute_tips(art)))

# no track may run through the maker's lettering, and no track may come closer to the edge than the copper does
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(grown(LETTERS, 0.05))
assert area_mm2(_hit) < 1e-4, f"a track channel overlaps the lettering by {area_mm2(_hit):.4f} mm2"
_trk = pcbnew.SHAPE_POLY_SET()
for t, _c in TRACKS:
    t.TransformShapeToPolygon(_trk, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
_trk.Simplify()
_near = []
for t, _c in TRACKS:
    _one = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(_one, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    if not inside(_one, inner):
        _near.append((t.GetNetname(), mm(t.GetStart()), mm(t.GetEnd())))
assert not _near, ("tracks closer than EDGE to the board edge", _near)
# and no track may lie on bare (unmasked) art: checked against the back mask below

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
    if area_mm2(grown(pcbnew.SHAPE_POLY_SET(piece.Outline(0)), -0.1)) < 1e-4:
        print("  dropped a copper sliver narrower than 0.2 mm, mm2:", round(area_mm2(piece), 3), "at", [round(v, 1) for v in bbox_mm(piece)])
        continue
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    touches = area_mm2(both) > 0.01
    add_filled(board, piece, B_Cu, nets["GND"] if touches else None)
    n_gnd += touches
    n_art += not touches
    if not touches:
        print("  plain art piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain art", n_art)

# ---- back mask art: the bare mouth and belly, minus the part now under the connector and under the cell ----
bmask = pcbnew.SHAPE_POLY_SET()
for p_ in mask_parts:
    bmask.Append(p_)
bmask.Simplify()
_before = area_mm2(bmask)
bmask.BooleanSubtract(grown(PATCH, 0.25))      # (mask laps 0.25 mm onto the new copper so no copper edge shows)
bmask.BooleanSubtract(CELL)
_over = grown(_trk, 0.3)                 # where a track has to cross what is left of the bare belly, mask covers the track
_o2 = pcbnew.SHAPE_POLY_SET(bmask)
_o2.BooleanIntersection(_over)
print(f"mask bridged over tracks crossing bare art: {area_mm2(_o2):.2f} mm2")
bmask.BooleanSubtract(_over)
bmask.BooleanIntersection(body)
bmask.Simplify()
_keep = pcbnew.SHAPE_POLY_SET()
for i in range(bmask.OutlineCount()):     # drop slivers left over at the edge of the cell (narrower than 0.5 mm)
    one = pcbnew.SHAPE_POLY_SET(bmask.Polygon(i))
    if area_mm2(grown(pcbnew.SHAPE_POLY_SET(one.Outline(0)), -0.25)) < 1e-4:
        print("  dropped a bare sliver, mm2:", round(area_mm2(one), 2), "at", [round(v, 1) for v in bbox_mm(one)])
        continue
    _keep.Append(one)
bmask = _keep
print(f"back bare art (mouth + belly): {_before:.1f} mm2 in 2018, {area_mm2(bmask):.1f} mm2 now")
_hit = pcbnew.SHAPE_POLY_SET(_trk)
_hit.BooleanIntersection(grown(bmask, 0.1))
assert area_mm2(_hit) < 1e-6, ("a track runs through bare (unmasked) art on the back", [bbox_mm(pcbnew.SHAPE_POLY_SET(_hit.Polygon(i))) for i in range(_hit.OutlineCount())])
add_filled(board, bmask, B_Mask)

# ---- front copper art: same shapes as 2018, minus the switch's two peg holes ----
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
_fa = area_mm2(front)
front.BooleanSubtract(pegs)
front.BooleanIntersection(grown(body, -0.3))
front.Simplify()
print(f"front copper art: {_fa:.2f} mm2 in 2018, {area_mm2(front):.2f} mm2 now (pegs and a 0.3 mm edge margin)")
add_filled(board, front, pcbnew.F_Cu)

# ---- front mask art: the foot is bare board, and the maker drew a masked "socket" round the 2018 header's four pins
#      (a four-lobed island with a pin-1 dot). With the header gone the island would be an odd blob, so the foot is
#      made bare all over; the toe line above it stays ----
fmask = pcbnew.SHAPE_POLY_SET()
for p_ in fmask_parts:
    fmask.Append(p_)
fmask.Simplify()
_foot = [i for i in range(fmask.OutlineCount()) if fmask.Outline(i).PointInside(P(137.3, 129.0))]
assert len(_foot) == 1 and fmask.HoleCount(_foot[0]) >= 1, "front mask: the foot opening was not found"
_foot_outline = pcbnew.SHAPE_LINE_CHAIN(fmask.Outline(_foot[0]))
_island = pcbnew.SHAPE_POLY_SET()
for h in range(fmask.HoleCount(_foot[0])):
    one = pcbnew.SHAPE_POLY_SET()
    one.AddOutline(fmask.Hole(_foot[0], h))
    if one.Contains(P(137.3, 125.5)):    # the old header's centre
        _island.Append(one)
assert _island.OutlineCount() == 1, "front mask: the socket island round the old header was not found"
_socket = poly([(133.5, 122.5), (141.5, 122.5), (141.5, 129.8), (133.5, 129.8)])       # below the top of the toe line
_socket.BooleanSubtract(poly([(136.58, 122.4), (137.08, 122.4), (136.91, 122.75), (136.41, 122.75)]))  # but not the toe line
_socket.BooleanAdd(poly([(133.5, 121.6), (136.35, 121.6), (136.35, 122.6), (133.5, 122.6)]))  # left of the toe line
add_circle(_socket, P(134.95, 122.9), 1.0)                                               # the pin-1 dot
_socket.Simplify()
_island.BooleanIntersection(_socket)
print(f"front mask: socket island round the old header made bare, mm2: {area_mm2(_island):.1f}")
assert 8 < area_mm2(_island) < 30
fmask.BooleanAdd(_island)
fmask.BooleanIntersection(body)
fmask.Simplify()
add_filled(board, fmask, pcbnew.F_Mask)

# ---- back silkscreen labels (the art is cleared behind each one so it reads) -----------------------
LABELS = [("SAO", s1[0] - 0.4, 77.25, 0.8, -TILT), ("OFF", SW[0], 77.6, 0.8, -TILT), ("BAT", s4[0] + 1.1, 77.85, 0.8, -TILT),
          ("CR2032", 137.9, 124.6, 0.9, 0), ("+ SIDE UP", 137.9, 126.0, 0.9, 0),
          ("SAO++ rA", 112.6, 107.6, 0.9, 0), ("1", 134.6, j1[1] + 2.4, 0.9, 0)]
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
_hit = pcbnew.SHAPE_POLY_SET(behind)
_hit.BooleanIntersection(LETTERS)
assert area_mm2(_hit) < 1e-6, "a new label overlaps the maker's lettering"

# ---- back silkscreen art: 2018 shapes, minus ink on the new pads and behind the new labels and the clip's marks ----
silk = pcbnew.SHAPE_POLY_SET()
for p_ in silk_parts:
    silk.Append(p_)
silk.Simplify()
# the back of the foot carries the same "socket" island round the old header as the front (there it is a gap in the
# foot's ink): fill it the same way, inside the foot's outline as the front mask draws it
_island = pcbnew.SHAPE_POLY_SET()
_island.AddOutline(_foot_outline)
_island = grown(_island, 0.0)
_island.BooleanIntersection(_socket)
_island.BooleanSubtract(silk)
print(f"back silk: socket island round the old header filled, mm2: {area_mm2(_island):.1f}")
assert 8 < area_mm2(_island) < 40
silk.BooleanAdd(_island)
silk.Simplify()
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.2))
for g in bat.GraphicalItems():            # the clip's own markings (+, closed-end line, slide-in arrow) must read too
    if g.GetLayer() == B_SilkS:
        g.TransformShapeToPolygon(bare, B_SilkS, FromMM(0.3), ERR, pcbnew.ERROR_OUTSIDE)
bare.Simplify()
_let = pcbnew.SHAPE_POLY_SET(LETTERS)
_let.BooleanIntersection(bare)
assert area_mm2(_let) < 1e-6, "a new pad lands on the lettering"
silk.BooleanSubtract(bare)
silk.BooleanSubtract(behind)
silk.BooleanIntersection(body)
silk.Simplify()
add_filled(board, silk, B_SilkS)

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
for r_, fp in sorted(list(led.items()) + list(res.items())):
    print(r_, mm(fp.GetPosition()), fp.GetOrientationDegrees())
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
