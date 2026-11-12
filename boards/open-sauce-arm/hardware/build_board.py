#!/usr/bin/env python3
"""Build open-sauce-arm.kicad_pcb from Caleb Marting's KiCad 10 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/open-sauce-arm/hardware/build_board.py

What the original is (read from original/Sauce Arm/Sauce Arm.kicad_pcb and .kicad_sch)
  - a 44.4 x 44.7 mm board in the shape of a bent robot arm: a two-jawed gripper at the top, a ribbed (bellows) upper
    arm, a round elbow joint, a ribbed forearm and a torn-off end with wires hanging out. The front is one ground pour
    under the solder mask, white silkscreen line art, and bare (gold) copper for the jaws, the elbow ring and one wire.
  - a solder-it-yourself kit with ONE light: a 5 mm through-hole LED whose legs go through the round "palm" of the
    gripper and whose body is bent up to lie in the notch between the jaws, so the arm holds the LED. One 1 k axial
    resistor across the collar under the gripper.
  - badge or battery, not both: a 2x3 through-hole SAO header and a through-hole CR2032 holder (MYOUNG BS-02-A1AJ010)
    drawn on top of each other on the forearm (the holder hangs 9 mm past the torn end), a 3-pad solder jumper that
    feeds the LED from SAO pin 1 (default) or from SAO pin 6 (GPIO2), a 12 mm solder pad for a pin back behind the
    elbow, and a 3 mm key-ring hole in the upper arm.
  - back silkscreen: assembly instructions and a small Open Sauce logo. No maker's name.

What this script does
  - reads the outline, the key-ring hole, the front silkscreen art, the gold art and the back-side Open Sauce logo from
    the original and ENLARGES THEM BY 25 % (SCALE below): at the maker's size the shared coin-cell clip does not fit
    on the board at all (its 17 mm contact disc is wider than the arm), and clip, connector and switch only fit beside
    each other from about 23 % up (see the README)
  - builds a new board: front copper solid as before (but not connected to anything), the maker's silkscreen and gold
    art on top. The copper is left out under the round palm of the gripper (inside the white ring), on both sides: that
    is where the through-board LED's light comes out, through the solder mask
  - places the SAO++ parts on the back: CR2032 clip on the forearm (the cell slides in from above, in the crook of the
    arm), the SAO connector behind the elbow, the SAO / OFF / BAT switch on the outer edge of the upper arm, one red
    through-board LED behind the palm, one 1.3 k resistor
  - routes everything on the back (no vias) and fills the rest of the back with ground copper. Patches that the
    supply tracks cut off from ground are left bare rather than floating
  - the maker's back silkscreen instructions ("Long Leg / Thru Circle", "1K Resistor", "Keyring Hole", "Battery
    Holder", "SAO Port", "Pin Back", "VCC / GPIO2") are no longer true, so the back gets the SAO++ labels and a credit
    line instead. The small Open Sauce logo is kept (OPEN_SAUCE_LOGO below), moved 6.5 mm toward the middle of the upper
    arm because the switch is where it was.

Coordinates are millimetres in KiCad's front view (x grows right, y grows down), measured from the top left corner of
the enlarged board.
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "open-sauce-arm"
SRC = os.path.join(HERE, "..", "original", "Sauce Arm", "Sauce Arm.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

SCALE = 1.28                # the whole design (outline, art, hole) enlarged by this much (see the README for why)
OPEN_SAUCE_LOGO = True      # the small Open Sauce logo on the back. It is that event's trademark: the repo owner has
                            # approved it on the Open Sauce Logo board only (2026-11-12). False leaves it off this board
LOGO_AT = (13.6, 44.6)      # top left corner of the logo (front view). The maker had it on the upper arm, where the switch is now

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks
THIN = 0.30         # tracks in tight places
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
WINDOW = 1.6        # radius kept free of copper on both sides at the LED
PEG_EDGE = 0.5      # board left between the switch's peg holes and the board edge

# ---- read the original ---------------------------------------------------------------------------------
_orig = pcbnew.LoadBoard(SRC)
_ps = pcbnew.SHAPE_POLY_SET()
assert _orig.GetBoardPolygonOutlines(_ps, False) and _ps.OutlineCount() == 1 and _ps.HoleCount(0) == 0
_ps.Simplify()
_bb = _ps.BBox()
ORIGIN = (ToMM(_bb.GetLeft()), ToMM(_bb.GetTop()))      # top left corner of the maker's outline on his sheet


def T(x, y):
    """Maker's sheet coordinates -> this board's coordinates."""
    return (round((x - ORIGIN[0]) * SCALE, 4), round((y - ORIGIN[1]) * SCALE, 4))


def chain_pts(ch):
    return [T(ToMM(ch.CPoint(k).x), ToMM(ch.CPoint(k).y)) for k in range(ch.PointCount())]


def scaled(src):
    """A maker's polygon set, enlarged and moved to this board's coordinates."""
    out = pcbnew.SHAPE_POLY_SET()
    for i in range(src.OutlineCount()):
        one = poly(chain_pts(src.Outline(i)))
        for h in range(src.HoleCount(i)):
            one.BooleanSubtract(poly(chain_pts(src.Hole(i, h))))
        out.Append(one)
    return out


OUTER = chain_pts(_ps.Outline(0))
_fps = {fp.GetReference(): fp for fp in _orig.GetFootprints()}
assert sorted(_fps) == ["B1", "D1", "JP1", "R1", "REF**", "U1", "X1"], sorted(_fps)
_hole = _fps["REF**"]
assert "MountingHole_3mm" in _hole.GetFPIDAsString()
HOLE_AT = T(*[ToMM(v) for v in _hole.GetPosition()])
HOLE_R = 1.5 * SCALE
_pp = [p.GetPosition() for p in _fps["D1"].Pads()]       # the maker's LED legs: one each side of the palm's middle
LED_2026 = T(ToMM(_pp[0].x + _pp[1].x) / 2, ToMM(_pp[0].y + _pp[1].y) / 2)

gold = pcbnew.SHAPE_POLY_SET()          # bare copper art: polygons the maker drew on F.Cu and F.Mask together
silk_f = pcbnew.SHAPE_POLY_SET()        # front silkscreen line art
logo = pcbnew.SHAPE_POLY_SET()          # the Open Sauce logo on the back
_n = {"gold": 0, "silk": 0, "logo": 0, "back_other": 0}
for d in _orig.GetDrawings():
    if not isinstance(d, pcbnew.PCB_SHAPE):
        continue
    if d.GetShape() != pcbnew.SHAPE_T_POLY:
        assert d.GetLayer() == B_SilkS, d.GetLayerName()        # the LED outline drawn beside the gripper
        _n["back_other"] += 1
        continue
    if d.IsOnLayer(F_Cu):
        assert d.IsOnLayer(pcbnew.F_Mask)
        gold.Append(scaled(d.GetPolyShape()))
        _n["gold"] += 1
    elif d.GetLayer() == pcbnew.F_SilkS:
        silk_f.Append(scaled(d.GetPolyShape()))
        _n["silk"] += 1
    elif d.GetLayer() == B_SilkS:
        b = d.GetBoundingBox()
        x0, y0 = ToMM(b.GetLeft()) - ORIGIN[0], ToMM(b.GetTop()) - ORIGIN[1]
        x1, y1 = ToMM(b.GetRight()) - ORIGIN[0], ToMM(b.GetBottom()) - ORIGIN[1]
        if 2.4 < x0 and x1 < 7.2 and 17.7 < y0 and y1 < 24.0:      # the logo: a 4.5 x 6.1 mm block on the upper arm
            logo.Append(scaled(d.GetPolyShape()))
            _n["logo"] += 1
        else:                                                    # the arrow of the LED drawing
            _n["back_other"] += 1
assert _n == {"gold": 6, "silk": 13, "logo": 23, "back_other": 9}, _n
gold.Simplify()
silk_f.Simplify()
logo.Simplify()

# The palm: the round patch inside the white ring at the base of the jaws, where the maker's LED legs went through.
_d = pcbnew.SHAPE_POLY_SET()
add_circle(_d, P(*LED_2026), 4.0 * SCALE)
_d.BooleanSubtract(silk_f)
_d.BooleanSubtract(gold)
_d.Simplify()
_hit = [pcbnew.SHAPE_POLY_SET(_d.Polygon(i)) for i in range(_d.OutlineCount())
        if pcbnew.SHAPE_POLY_SET(_d.Polygon(i)).Contains(P(*LED_2026))]
assert len(_hit) == 1, "palm not found"
PALM = _hit[0]
_b = bbox_mm(PALM)
LED_AT = (round((_b[0] + _b[2]) / 2, 2), round((_b[1] + _b[3]) / 2, 2))
PALM_R = round(min(_b[2] - _b[0], _b[3] - _b[1]) / 2, 2)
print(f"palm {_b[2] - _b[0]:.2f} x {_b[3] - _b[1]:.2f} mm, middle {LED_AT}; the maker's LED legs straddled {LED_2026}")
assert abs((_b[2] - _b[0]) - (_b[3] - _b[1])) < 0.1 and PALM_R >= WINDOW, "the palm is not a circle big enough for the LED window"

# ---- placement (front view) ------------------------------------------------------------------------------
BAT = (31.0, 43.6)          # clip centre, on the forearm
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in from above, in the crook of the arm
CONN = (10.8, 37.15)         # behind the elbow, key slot up
SW_Y = 25.1                 # switch on the left edge (front view) of the upper arm
SW_TILT = 0                 # degrees off square, to follow the ribbed edge
R_AT = (10.0, SW_Y - 1.5)   # the resistor's middle, level with the switch's common pin; pads left (supply) and right (LED)
LABELS = [("BAT", 6.9, 20.9, 0.8, 0, False), ("OFF", 6.9, 25.2, 0.8, 0, False), ("SAO", 6.9, 29.4, 0.8, 0, False),
          ("+", 44.4, 43.6, 1.4, 0, True), ("CR2032", 46.5, 45.4, 0.8, 0, False), ("+ UP", 46.3, 46.7, 0.8, 0, False),
          ("1", 6.3, 31.9, 0.9, 0, False),
          ("orig. design:", 14.3, 17.2, 0.8, 0, False), ("Caleb Marting", 14.3, 18.7, 0.8, 0, False),
          ("Open Sauce 2026", 14.3, 20.2, 0.8, 0, False),
          ("Sauce Arm", 9.0, 44.4, 0.8, 0, False), ("SAO++ rA", 9.6, 45.9, 0.9, 0, False)]      # (text, x, y, size, angle, bold)

# ---- new board, outline ------------------------------------------------------------------------------------
board = pcbnew.CreateEmptyBoard()
TRACKS = []
body = poly(OUTER)
hole = pcbnew.SHAPE_POLY_SET()
add_circle(hole, P(*HOLE_AT), HOLE_R, 72)
HOLE = [list(mm(hole.Outline(0).CPoint(k))) for k in range(hole.Outline(0).PointCount())]
json.dump({"outer": [list(p) for p in OUTER], "holes": [HOLE]}, open(os.path.join(HERE, "outline.json"), "w"))
for pts in (OUTER, HOLE):
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(poly(pts))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's {(bx1 - bx0) / SCALE:.2f} x {(by1 - by0) / SCALE:.2f}), "
      f"{len(OUTER)} outline points; hole {2 * HOLE_R:.2f} mm at {HOLE_AT}")
inner = grown(body, -EDGE)                       # shrink the outer path and grow the hole separately (KiCad quirk)
_keep = pcbnew.SHAPE_POLY_SET()
add_circle(_keep, P(*HOLE_AT), HOLE_R + EDGE, 72)
inner.BooleanSubtract(_keep)
pad_ok = grown(body, -PAD_EDGE)
_keep = pcbnew.SHAPE_POLY_SET()
add_circle(_keep, P(*HOLE_AT), HOLE_R + PAD_EDGE, 72)
pad_ok.BooleanSubtract(_keep)

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


def box_of(item):
    b = item.GetBoundingBox()
    return (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))


def off_board(fp, region):
    """Area of the footprint's real pads that lies outside `region`."""
    out = pcbnew.SHAPE_POLY_SET()
    for p in fp.Pads():
        if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            out.Append(pad_poly(p, B_Cu))
    out.BooleanSubtract(region)
    return area_mm2(out)


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat

# switch: knob out of the left edge (front view). Measured at this right angle, where its rectangles are rectangles.
sw = load("SW1", (0, 0))
for _rot in (0, 90, 180, 270):
    sw.SetOrientationDegrees(_rot)
    _k = box_of([g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0])
    if _k[2] < -1.0:                     # knob travel box lies to the left of the footprint's centre
        break
else:
    raise AssertionError("no rotation points the switch knob left")
_k0 = _k                                 # the knob's whole travel, measured with the switch at (0, 0)


def try_switch(y, tilt):
    """Put the switch at height y, turned `tilt` degrees from square, as far left as its pads allow.
    Returns its x and how far the knob's tip is past the board edge at 21 points along its travel."""
    sw.SetOrientationDegrees(_rot + tilt)
    x = 0.6
    while True:                          # the edge is ribbed: step in until every pad is on the board
        sw.SetPosition(P(x, y))
        pegs_ = pcbnew.SHAPE_POLY_SET()
        for p in sw.Pads():              # the two locating-peg holes keep PEG_EDGE of board between them and the edge
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                add_circle(pegs_, p.GetPosition(), ToMM(p.GetDrillSize().x) / 2 + PEG_EDGE, 24)
        pegs_.BooleanSubtract(body)
        if off_board(sw, pad_ok) == 0 and area_mm2(pegs_) == 0:
            break
        x = round(x + 0.02, 2)
        if x > 7:
            return None, [-9]
    ca, sa = math.cos(math.radians(-tilt)), math.sin(math.radians(-tilt))      # KiCad angles turn anticlockwise on screen
    reach = []
    for k in range(21):
        v = _k0[1] + (_k0[3] - _k0[1]) * k / 20
        tip = (x + _k0[0] * ca - v * sa, y + _k0[0] * sa + v * ca)
        out = (-ca, -sa)                 # the way the knob points
        r = -2.0
        while r < 3 and not body.Contains(P(tip[0] - out[0] * r, tip[1] - out[1] * r)):
            r += 0.02                    # walk back from 2 mm beyond the tip until the board is under the point
        reach.append(round(r, 2) if r > -2.0 else -9)
        # r > 0: the edge is r behind the tip (the knob sticks out by r); r < 0: the board goes on past the tip
    return x, reach


SW_X, _reach = try_switch(SW_Y, SW_TILT)
link(sw, "SW1")
KNOB_REACH = (min(_reach), sum(_reach) / len(_reach))
print(f"switch centre ({SW_X}, {SW_Y}), angle {_rot} + {SW_TILT}; knob tip is {KNOB_REACH[0]:.2f} to {max(_reach):.2f} mm past the "
      f"ribbed edge along its travel (average {KNOB_REACH[1]:.2f})")
assert KNOB_REACH[0] > 0, "the switch knob does not reach the edge"

led = place("D1", LED_AT, ("2", (LED_AT[0] - 1.55, LED_AT[1])))          # + pad on the left (front view)
res = place("R1", R_AT, ("1", (R_AT[0] - 0.825, R_AT[1])))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_brot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_brot)
link(bat, "BT1")
STRAP = box_of([g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0])
print("battery clip angle", _brot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f" % (STRAP[0], STRAP[2], STRAP[1], STRAP[3]))
for g in bat.GraphicalItems():          # the clip's own arrow and '+' land off the board and on the connector: fab layer
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

for fp in board.GetFootprints():         # every pad sits on the board, PAD_EDGE inside the edge
    assert off_board(fp, pad_ok) == 0, f"{fp.GetReference()} has a pad closer than {PAD_EDGE} mm to the board edge"

# things only hardware can prove, but the numbers should at least be right
_strap = poly([(STRAP[0], STRAP[1]), (STRAP[2], STRAP[1]), (STRAP[2], STRAP[3]), (STRAP[0], STRAP[3])])
_o = pcbnew.SHAPE_POLY_SET(_strap)
_o.BooleanSubtract(body)
CLIP_OFF = area_mm2(_o)
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_o = pcbnew.SHAPE_POLY_SET(_cell)
_o.BooleanSubtract(body)
CELL_OFF = area_mm2(_o)
_ob = bbox_mm(_o) if CELL_OFF > 0 else None
print(f"clip body outside the outline: {CLIP_OFF:.2f} mm2; cell outside the outline: {CELL_OFF:.1f} mm2"
      + (f" (reaches y {_ob[1]:.2f}, the ribs' valleys)" if _ob else ""))
_jb = box_of([g for g in conn.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab][0])
_jbody = [box_of(g) for g in conn.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab]
_jb = (min(b[0] for b in _jbody), min(b[1] for b in _jbody), max(b[2] for b in _jbody), max(b[3] for b in _jbody))
_o = poly([(_jb[0], _jb[1]), (_jb[2], _jb[1]), (_jb[2], _jb[3]), (_jb[0], _jb[3])])
_o.BooleanSubtract(body)
_swb = box_of(sw)
print(f"connector body x {_jb[0]:.2f}..{_jb[2]:.2f} y {_jb[1]:.2f}..{_jb[3]:.2f}, outside the outline {area_mm2(_o):.2f} mm2; "
      f"gap to the clip body {STRAP[0] - _jb[2]:.2f} mm; switch box y {_swb[1]:.2f}..{_swb[3]:.2f}, gap to the connector body {_jb[1] - _swb[3]:.2f} mm")
assert area_mm2(_o) == 0 and CLIP_OFF == 0 and STRAP[0] - _jb[2] > 0.8 and _jb[1] - _swb[3] > 0


# ---- routing (back copper only, no vias) ------------------------------------------------------------
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


s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
print("switch pins 1, 3, 4 at", s1, s3, s4)
j1 = padpos(conn, "1")
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
r1a, r1b = padpos(res, "1"), padpos(res, "2")
d1a = padpos(led, "2")
print("J1 pin 1", j1, "clip pads", bt, "R1", r1a, r1b, "LED +", d1a)

# The switch's pins run down the edge: 4 (cell) on top, 3 (common), 2 (off, not connected), 1 (badge) at the bottom.
assert s4[1] < s3[1] < s1[1], "switch pins are not in the order the routing expects (cell pin on top)"

# badge 3.3 V: connector pin 1 (top left pad) straight up, then across to the switch's bottom pin
route("VSAO", [j1, (j1[0], s1[1] + 1.9), (j1[0] - 1.9, s1[1]), s1], width=THIN)

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it.
LINK_Y = BAT[1] + 9.9
route("VBAT", [bt[0], (bt[0][0], LINK_Y - 3.8), (bt[0][0] + 3.8, LINK_Y), (bt[1][0] - 3.8, LINK_Y), (bt[1][0], LINK_Y - 3.8), bt[1]])
# Cell track, from the clip to the switch's top pin. Any track from the clip to a switch on the board edge cuts the
# back copper in two, and with no vias the three ground points (connector pin 2, the cell's contact disc, the LED)
# must all end up on the same side of it. So the track leaves the link at the clip's closed end, runs along inside
# the lower left edge of the elbow, then goes UNDER THE CONNECTOR: up past the left end of its pads, across between
# the two rows, up between pins 1 and 3, and then BETWEEN THE RESISTOR'S TWO PADS (the resistor bridges it: the one
# crossing on the board) to the switch. That leaves the connector's top row (badge 3.3 V) on the switch's side of
# the track and its bottom row (ground) on the ground side, with the cell and the LED.
j3 = padpos(conn, "3")
GAP_X = round((j1[0] + j3[0]) / 2, 3)        # between connector pins 1 and 3
ROW_Y = CONN[1] - 0.5                        # between the connector's two rows of pads, nearer the top row
LEFT_X = j1[0] - 1.36                        # left of the connector's pads, under the end of its shroud
VB_X = R_AT[0]                               # under the middle of the resistor
ELBOW = [(13.5, 52.0), (15.5, 52.6)]         # two corners that keep the track about 2 mm inside the elbow's ribbed edge
route("VBAT", [(bt[0][0] + 3.8, LINK_Y)] + ELBOW[::-1] + [(LEFT_X, 44.0), (LEFT_X, ROW_Y + 0.4), (LEFT_X + 0.4, ROW_Y),
               (GAP_X - 0.4, ROW_Y), (GAP_X, ROW_Y - 0.4), (GAP_X, j1[1] - 2.9), (VB_X, j1[1] - 2.9 - (VB_X - GAP_X))], width=THIN)
route("VBAT", [(VB_X, j1[1] - 2.9 - (VB_X - GAP_X)), (VB_X, s4[1] + 0.9), (VB_X - 0.9, s4[1]), s4], width=0.25, clear=0.25)

# switched supply: switch pin 3 straight across into the resistor
assert abs(r1a[1] - s3[1]) < 0.01
route("VLOAD", [s3, r1a], width=THIN)
# resistor -> up the upper arm and the gripper's stem -> LED +
LA_X = r1b[0] + 0.8
route("LED1_A", [r1b, (LA_X, r1b[1] - 0.8), (LA_X, d1a[1] + 2.9), (d1a[0], d1a[1] + 2.9 - (LA_X - d1a[0])), d1a], width=THIN)

_tr = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(_tr, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
_tr.BooleanSubtract(inner)
assert area_mm2(_tr) < 1e-6, f"a track is closer than {EDGE} mm to the board edge or the hole: {[round(v, 2) for v in bbox_mm(_tr)]}"

# ---- copper ----------------------------------------------------------------------------------------------
window = pcbnew.SHAPE_POLY_SET()          # back: the LED's round window
add_circle(window, P(*LED_AT), WINDOW)
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)

# front: solid copper as the maker had it (his was a ground pour; here it is not connected to anything, so the front
# needs no via), with no copper under the palm (the mask stays on it: the light comes through the mask, as a round
# glowing patch inside the white ring) and a ring of clearance round the two switch-peg holes
front = pcbnew.SHAPE_POLY_SET(inner)
front.BooleanSubtract(PALM)
front.BooleanSubtract(pegs)
front.Simplify()
add_filled(board, front, F_Cu)
# gold art: the maker's bare-copper shapes (the two jaws, the elbow ring, one wire and the two bare wire ends), as
# openings in the front mask. They stop where the copper stops, 0.55 mm from the edge.
_lost = pcbnew.SHAPE_POLY_SET(gold)
_lost.BooleanSubtract(body)
gold_on = pcbnew.SHAPE_POLY_SET(gold)
gold_on.BooleanIntersection(inner)
gold_on.Simplify()
print(f"gold art: {area_mm2(gold):.1f} mm2 drawn, {area_mm2(_lost):.1f} mm2 of it outside the outline, "
      f"{area_mm2(gold_on):.1f} mm2 kept")
add_filled(board, gold_on, pcbnew.F_Mask)
# front silkscreen line art, as the maker drew it
_lost = pcbnew.SHAPE_POLY_SET(silk_f)
_lost.BooleanSubtract(body)
print(f"front silkscreen: {area_mm2(silk_f):.1f} mm2, {area_mm2(_lost):.2f} mm2 outside the outline")
_silk_ok = grown(body, -0.1)              # silkscreen stops 0.1 mm short of the edge and of the key-ring hole (the maker
_keep = pcbnew.SHAPE_POLY_SET()           # printed a white disc right across the hole; the board house would clip it anyway)
add_circle(_keep, P(*HOLE_AT), HOLE_R + 0.1, 72)
_silk_ok.BooleanSubtract(_keep)
silk_f.BooleanIntersection(_silk_ok)
add_filled(board, silk_f, pcbnew.F_SilkS)

# back: GND everywhere, cleared around everything that is not GND
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET(window)
cut.Append(pegs)
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
cut.Simplify()
art.BooleanSubtract(cut)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)      # drop slivers thinner than 0.3 mm
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.BooleanIntersection(inner)
art.Simplify()
for t, clear in TRACKS:                  # the ground track is part of the ground copper
    if t.GetNetCode() == gnd_code:
        t.TransformShapeToPolygon(art, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
art.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
n_gnd_pads = 0
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
            n_gnd_pads += 1
n_gnd = n_art = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    hits = 0
    for j in range(gnd_pads.OutlineCount()):
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(pcbnew.SHAPE_POLY_SET(gnd_pads.Polygon(j)))
        hits += area_mm2(both) > 0.01
    if hits:                             # a piece that reaches no GND pad would be a floating island between the
        add_filled(board, piece, B_Cu, nets["GND"])     # supply tracks: leave that copper out
    n_gnd += bool(hits)
    n_art += not hits
    print("  back copper piece, mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)], "GND pads on it:", hits)
print("back copper pieces: GND", n_gnd, "left out", n_art, "; GND pads", n_gnd_pads)
assert n_gnd == 1, "the ground copper is not in one piece"

# ---- back silkscreen ---------------------------------------------------------------------------------
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bare.Append(pad_poly(pad, B_Cu, 0.15))
bare.Simplify()
if OPEN_SAUCE_LOGO:
    _b = bbox_mm(logo)
    moved = pcbnew.SHAPE_POLY_SET(logo)
    moved.Move(VECTOR2I(FromMM(LOGO_AT[0] - _b[0]), FromMM(LOGO_AT[1] - _b[1])))
    _o = pcbnew.SHAPE_POLY_SET(moved)
    _o.BooleanSubtract(grown(inner, 0.25))
    assert area_mm2(_o) < 1e-6, "the logo reaches the board edge or the hole"
    _o = pcbnew.SHAPE_POLY_SET(moved)
    _o.BooleanIntersection(bare)
    assert area_mm2(_o) < 1e-6, "the logo lies on a pad"
    add_filled(board, moved, B_SilkS)
    print(f"Open Sauce logo on the back: {_b[2] - _b[0]:.2f} x {_b[3] - _b[1]:.2f} mm, moved from ({_b[0]:.2f}, {_b[1]:.2f}) to {LOGO_AT}")
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
    b_ = box_of(t)
    _o = poly([(b_[0], b_[1]), (b_[2], b_[1]), (b_[2], b_[3]), (b_[0], b_[3])])
    _o.BooleanSubtract(grown(inner, 0.25))
    assert area_mm2(_o) < 1e-6, f"label {txt!r} reaches the board edge: box {[round(v, 2) for v in b_]}"
    _o = poly([(b_[0], b_[1]), (b_[2], b_[1]), (b_[2], b_[3]), (b_[0], b_[3])])
    _o.BooleanIntersection(bare)
    assert area_mm2(_o) < 1e-6, f"label {txt!r} lies on a pad: box {[round(v, 2) for v in b_]}"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LED pads:", {p.GetNumber(): mm(p.GetPosition()) for p in led.Pads()})
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
