#!/usr/bin/env python3
"""Build open-sauce-logo.kicad_pcb from Caleb Marting's KiCad 10 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/open-sauce-logo/hardware/build_board.py

What the original is (read from original/Open Sauce Logo SAO/logo.kicad_pcb and logo.kicad_sch)
  - a 30.9 x 40.3 mm board in the shape of the Open Sauce logo (the cube-headed robot with its lightning-bolt aerial).
    Both sides are one solid ground pour. The picture is made only of openings in the front solder mask: bare (gold)
    copper where the logo is light, mask colour where it is dark. There is no front silkscreen.
  - a solder-it-yourself kit: two 5 mm through-hole red LEDs pushed through the robot's eyes from the front, two 1 k
    axial resistors lying along the lightning bolts on the back, a through-hole CR2032 holder (MYOUNG BS-02-A1AJ010) and
    a 2x3 SAO header drawn on top of each other (fit one or the other), a 12 mm solder pad for a pin back, a 3 mm hole in
    the loop at the top, and a 3-pad solder jumper "LED SELECT" that feeds the LEDs from SAO pin 1 (3.3 V, the default)
    or from SAO pin 6 (GPIO2), so a badge could blink them.

What this script does
  - reads the outline, the 3 mm hole and the front mask art from the original and ENLARGES THEM BY 15 % (SCALE below):
    at the original size the two eye LEDs sit where the shared coin-cell clip, connector and switch all need to be, and
    no arrangement fits (see the README). Nothing else about the art changes.
  - builds a new board: front copper solid as before (but not connected to anything), front mask art as before. The
    copper is left out under the two pupils (the tall dark ovals inside the eyes); the mask stays, so each pupil is
    where a through-board LED's light comes out. On the back the copper is clear of each pupil and of a 1.6 mm circle
    round the LED
  - writes outline.json (the enlarged outline and hole) for the record
  - places the SAO++ parts on the back: CR2032 clip behind the top of the cube (the cell slides in from the top), the
    SAO connector at the lower left of the front view, the SAO / OFF / BAT switch on the right edge of the front view,
    one red through-board LED behind each eye, one 1.3 k resistor per LED
  - routes everything on the back (no vias) and fills the rest of the back with ground copper. Two patches that the
    supply tracks cut off from ground are left bare rather than floating
  - the maker's back silkscreen was all assembly instructions for the kit parts ("1K Resistor", "Red LED Long Leg Thru
    Circle", "PIN BACK", "CR2032 HOLDER", "SAO PORT", "LED SELECT VCC / IO2"); none of it is true any more, so the back
    gets the SAO++ labels and a credit line instead.

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

SLUG = "open-sauce-logo"
SRC = os.path.join(HERE, "..", "original", "Open Sauce Logo SAO", "logo.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

SCALE = 1.15                    # the whole logo, outline and hole, enlarged by this much (see the README for why)
ORIGIN = (136.55, 71.0193)      # top left corner of the maker's outline on his sheet

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks
THIN = 0.30         # tracks in tight places
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
WINDOW = 1.6        # radius kept free of copper on both sides at each LED


def T(x, y):
    """Maker's sheet coordinates -> this board's coordinates."""
    return (round((x - ORIGIN[0]) * SCALE, 4), round((y - ORIGIN[1]) * SCALE, 4))


def chain_pts(ch):
    return [T(ToMM(ch.CPoint(k).x), ToMM(ch.CPoint(k).y)) for k in range(ch.PointCount())]


# ---- read the original: outline, hole, LED positions, front mask art -----------------------------------
_orig = pcbnew.LoadBoard(SRC)
_ps = pcbnew.SHAPE_POLY_SET()
assert _orig.GetBoardPolygonOutlines(_ps, False) and _ps.OutlineCount() == 1
_ps.Simplify()
OUTER = chain_pts(_ps.Outline(0))
_fps = {fp.GetReference(): fp for fp in _orig.GetFootprints()}
assert sorted(_fps) == ["B1", "D1", "D2", "JP1", "R3", "R4", "REF**", "U1", "X1"], sorted(_fps)
_hole = _fps["REF**"]
assert "MountingHole_3mm" in _hole.GetFPIDAsString()
HOLE_AT = T(*[ToMM(v) for v in _hole.GetPosition()])
HOLE_R = 1.5 * SCALE
LED_2026 = {}
for _r in ("D1", "D2"):         # the maker's 5 mm LED sat between its two legs
    _pp = [p.GetPosition() for p in _fps[_r].Pads()]
    LED_2026[_r] = T(ToMM(_pp[0].x + _pp[1].x) / 2, ToMM(_pp[0].y + _pp[1].y) / 2)
mask_art = pcbnew.SHAPE_POLY_SET()
_n_mask = _n_junk = 0
for d in _orig.GetDrawings():
    if isinstance(d, pcbnew.PCB_SHAPE) and d.GetLayer() == pcbnew.F_Mask:
        assert d.GetShape() == pcbnew.SHAPE_T_POLY
        src = d.GetPolyShape()
        if src.Area() / 1e12 < 0.001:      # two specks 0.01 mm across, left over from the maker's SVG import
            _n_junk += 1
            continue
        for i in range(src.OutlineCount()):
            one = poly(chain_pts(src.Outline(i)))
            for h in range(src.HoleCount(i)):
                one.BooleanSubtract(poly(chain_pts(src.Hole(i, h))))
            mask_art.Append(one)
        _n_mask += 1
assert (_n_mask, _n_junk) == (28, 2), (_n_mask, _n_junk)
mask_art.Simplify()
# Each eye is a gold oval with a tall dark pupil in it (mask left on). The maker's 5 mm LED stood on the pupil, 0.3 to
# 0.6 mm off its middle. The SAO++ LED sits behind the middle of the pupil and the pupil is where its light comes out.
PUPIL, EYES = {}, {}
for _r, (_x, _y) in LED_2026.items():
    _d = pcbnew.SHAPE_POLY_SET()
    add_circle(_d, P(_x, _y), 4.5)
    _d.BooleanSubtract(mask_art)
    _d.Simplify()
    _hit = [pcbnew.SHAPE_POLY_SET(_d.Polygon(i)) for i in range(_d.OutlineCount())
            if pcbnew.SHAPE_POLY_SET(_d.Polygon(i)).Contains(P(_x, _y))]
    assert len(_hit) == 1 and 7 < area_mm2(_hit[0]) < 11, f"{_r}: pupil not found"
    PUPIL[_r] = _hit[0]
    _b = bbox_mm(_hit[0])
    EYES[_r] = (round((_b[0] + _b[2]) / 2, 2), round((_b[1] + _b[3]) / 2, 2))
    print(f"{_r}: pupil {_b[2] - _b[0]:.2f} x {_b[3] - _b[1]:.2f} mm, middle {EYES[_r]}; the maker's LED was "
          f"{math.hypot(EYES[_r][0] - _x, EYES[_r][1] - _y) / SCALE:.2f} mm from it on his board")
_back_silk = [d for d in _orig.GetDrawings() if d.GetLayer() == B_SilkS]
assert len(_back_silk) == 29 and not [d for d in _orig.GetDrawings() if d.GetLayer() == pcbnew.F_SilkS]

# ---- placement (front view) ------------------------------------------------------------------------------
BAT = (16.55, 15.5)         # clip centre: its closed end stops 0.7 mm above the left eye's LED, the cell's top edge
                            # stops just short of the hole in the loop, and it sits between the switch and the right eye
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in from the top
CONN = (13.8, 35.8)         # lower left (front view), key slot up
SW_Y = 30.0                 # switch on the left edge (front view), below the clip
LED_DIR = {"D1": (-1, 0), "D2": (0, 1)}     # where each LED's + pad sits from its centre: D1 left, D2 below
R_AT = {"R1": (17.4, EYES["D1"][1]), "R2": (28.6, 30.0)}     # each resistor's supply pad (1) is its left one

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
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's {(bx1 - bx0) / SCALE:.2f} x {(by1 - by0) / SCALE:.2f}); "
      f"hole {2 * HOLE_R:.2f} mm at {HOLE_AT}; eyes {EYES}")
inner = grown(body, -EDGE)                       # shrink the outer path and grow the hole separately (KiCad quirk)
_keep = pcbnew.SHAPE_POLY_SET()
add_circle(_keep, P(*HOLE_AT), HOLE_R + EDGE, 72)
inner.BooleanSubtract(_keep)
pad_ok = grown(body, -PAD_EDGE)

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
_real = [p for p in sw.Pads() if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
_tab_l = min(ToMM(p.GetBoundingBox().GetLeft()) for p in _real)
_y0 = SW_Y + min(ToMM(p.GetBoundingBox().GetTop()) for p in _real)
_y1 = SW_Y + max(ToMM(p.GetBoundingBox().GetBottom()) for p in _real)
_edge_x = max(x for x, y in OUTER if x < 3 and _y0 - 1.5 < y < _y1 + 1.5)      # the left edge beside the switch
SW_X = round(_edge_x + PAD_EDGE - _tab_l, 2)
while True:                              # the edge leans in a little along the switch: step in until every pad is clear
    sw.SetPosition(P(SW_X, SW_Y))
    _off = pcbnew.SHAPE_POLY_SET()
    for _p in _real:
        _off.Append(pad_poly(_p, B_Cu))
    _off.BooleanSubtract(pad_ok)
    if _off.OutlineCount() == 0:
        break
    SW_X = round(SW_X + 0.01, 2)
link(sw, "SW1")
KNOB_TIP = box_of([g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0])[0]
print(f"switch centre ({SW_X}, {SW_Y}), angle {_rot}; knob tip x {KNOB_TIP:.2f}, {_edge_x - KNOB_TIP:.2f} mm past the left edge ({_edge_x:.2f})")

led = {}
for ref, (dx, dy) in LED_DIR.items():
    x, y = EYES[ref]
    led[ref] = place(ref, (x, y), ("2", (x + dx * 1.55, y + dy * 1.55)))
res = {r: place(r, at, ("1", (at[0] - 0.825, at[1]))) for r, at in R_AT.items()}

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
for g in bat.GraphicalItems():          # the clip's own arrow and '+' land on the loop and the hole: fab layer instead
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

NEW = set(PARTS)
for fp in board.GetFootprints():         # every pad sits on the board, PAD_EDGE inside the edge
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"

# things only hardware can prove, but the numbers should at least be right: gaps between the clip and its neighbours
_led_top = min(ToMM(p.GetBoundingBox().GetTop()) for p in led["D1"].Pads())
_d2_left = min(ToMM(p.GetBoundingBox().GetLeft()) for p in led["D2"].Pads())
GAP_CLIP_D1 = _led_top - (BAT[1] + 11.0)
GAP_CLIP_D2 = _d2_left - (BAT[0] + 11.45)
GAP_CELL_HOLE = math.hypot(HOLE_AT[0] - BAT[0], HOLE_AT[1] - BAT[1]) - 10.0 - HOLE_R
print(f"clip closed end to D1 pads {GAP_CLIP_D1:.2f} mm; clip side to D2 pads {GAP_CLIP_D2:.2f} mm; cell edge to hole edge {GAP_CELL_HOLE:.2f} mm")
assert GAP_CLIP_D1 > 0.6 and GAP_CLIP_D2 > 0.4 and GAP_CELL_HOLE > 0
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_cell.BooleanSubtract(body)
print(f"cell area outside the board outline (seen in the notches beside the neck): {area_mm2(_cell):.1f} mm2")


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
assert s4[1] < s3[1] < s1[1], "switch pins are not in the order the routing expects (cell pin on top)"
j1 = padpos(conn, "1")

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. From the left tab a track drops to the switch's top pin.
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in range(180, -1, -5)]
assert all(y >= BAT[1] - 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]])
VB_X = 4.0                                  # between the switch's upper solder tab and the clip
route("VBAT", [(bt[0][0], bt[0][1] + 2.0), (VB_X, bt[0][1] + 2.0 + (bt[0][0] - VB_X)), (VB_X, s4[1]), s4], width=THIN)

# badge 3.3 V: switch bottom pin straight across, under the connector's shroud, into pin 1
assert abs(s1[1] - j1[1]) < 2.0
route("VSAO", [s1, (j1[0], s1[1])], width=THIN)

# switched supply: switch pin 3 -> along the gap between the clip and the connector -> R1 -> on under the left eye -> R2
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")
route("VLOAD", [s3, (5.2, s3[1]), (5.2 + (s3[1] - r1a[1]), r1a[1]), r1a], width=THIN)
route("VLOAD", [r1a, (r1a[0], r2a[1] - 0.8), (r1a[0] + 0.825, r2a[1]), r2a], width=THIN)
# resistor -> LED +
route("LED1_A", [r1b, padpos(led["D1"], "2")], width=THIN)
d2a = padpos(led["D2"], "2")
route("LED2_A", [r2b, (d2a[0], r2b[1] - (d2a[0] - r2b[0])), d2a], width=THIN)

# ---- copper ----------------------------------------------------------------------------------------------
windows = pcbnew.SHAPE_POLY_SET()         # back: the LED's round window plus the whole pupil
for r, (x, y) in EYES.items():
    add_circle(windows, P(x, y), WINDOW)
    windows.Append(PUPIL[r])
windows.Simplify()
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)

# front: solid copper as the maker had it (his was a ground pour; here it is not connected to anything, so the front
# needs no via), with no copper under the two pupils (the mask stays on them: the light comes through the mask, in the
# shape of the pupil) and a ring of clearance round the two switch-peg holes
front = pcbnew.SHAPE_POLY_SET(inner)
for r in PUPIL:
    front.BooleanSubtract(PUPIL[r])
front.BooleanSubtract(pegs)
front.Simplify()
add_filled(board, front, F_Cu)
# front mask art: the maker's openings, enlarged, nothing else
_out = pcbnew.SHAPE_POLY_SET(mask_art)
_out.BooleanSubtract(body)
assert area_mm2(_out) < 0.01, f"mask art outside the outline: {area_mm2(_out):.2f} mm2"
add_filled(board, mask_art, pcbnew.F_Mask)
# back: GND everywhere, cleared around everything that is not GND
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET(windows)
cut.Append(pegs)
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
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

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("BAT", 2.7, 23.2, 0.8, 0, False), ("OFF", 5.3, SW_Y, 0.8, 90, False), ("SAO", 2.8, 36.9, 0.8, 0, False),
          ("+", 3.6, BAT[1], 1.4, 0, True), ("CR2032 + UP", 32.0, 19.0, 0.8, 90, False),
          ("1", 9.8, 30.6, 0.9, 0, False),
          ("Open Sauce Logo", 28.1, 33.3, 0.8, 0, False), ("SAO++ rA", 28.1, 34.8, 0.9, 0, False),
          ("orig. design:", 28.0, 37.0, 0.8, 0, False), ("Caleb Marting", 28.0, 38.4, 0.8, 0, False),
          ("Open Sauce 2026", 27.5, 39.8, 0.8, 0, False)]
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        bare.Append(pad_poly(pad, B_Cu, 0.15))
bare.Simplify()
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
    _o = pcbnew.SHAPE_POLY_SET()
    b_ = box_of(t)
    _o = poly([(b_[0], b_[1]), (b_[2], b_[1]), (b_[2], b_[3]), (b_[0], b_[3])])
    _o.BooleanSubtract(grown(body, -0.3))
    assert area_mm2(_o) < 1e-6, f"label {txt!r} reaches the board edge: box {[round(v, 2) for v in b_]}"
    _o = poly([(b_[0], b_[1]), (b_[2], b_[1]), (b_[2], b_[3]), (b_[0], b_[3])])
    _o.BooleanIntersection(bare)
    assert area_mm2(_o) < 1e-6, f"label {txt!r} lies on a pad: box {[round(v, 2) for v in b_]}"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LED pads:", {r: {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads()} for r, fp in led.items()})
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
