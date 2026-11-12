#!/usr/bin/env python3
"""Build nsec-slot-machine.kicad_pcb from nothing but the numbers in this file.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-slot-machine/hardware/build_board.py

The circuit is NorthSec 2025's Sao_SlotMachine_v2 (three always-on LEDs, one resistor each, MIT) with the SAO++ power
block added. The OUTLINE AND ALL FRONT ART ARE SAO++'S OWN DRAWING, designed here around the parts. Nothing is read from
the maker's board file: NorthSec's outline was drawn over a third-party icon, so it is not used, scaled or copied.
The only maker item on the board is the 'nsec 2025' logo footprint on the back (original/.../libs/footprints).

The drawing (front view, mm, x right, y down, origin at the top-left corner of the cabinet's bounding box):
  - a 33 mm wide cabinet with a round marquee on top (the coin cell sits behind it and slides in over the top),
    a lever on the right (ball, arm, elbow), flat bottom (the switch knob comes out of it)
  - the whole front is copper under solder mask; 'gold' shapes are openings in the mask; the three 7s are holes in
    the copper with no mask (bare board), each with a reverse-mount LED behind it, so only the 7s glow
  - white silkscreen: JACKPOT, the reel frame, the lever arm, a button ring and a coin slot
It also writes art/front.svg (the same shapes, for people) and hardware/outline.json (for the panel tool).
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS, F_Mask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, mm, add_circle, grown, area_mm2, add_filled, pad_poly, bbox_mm  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "nsec-slot-machine"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOGO_LIB = os.path.join(HERE, "..", "original", "Sao_SlotMachine_v2", "libs", "footprints")

OX, OY = 100.0, 60.0    # where the drawing's origin sits on the KiCad page
CLEAR = 0.30            # copper-to-copper gap cut into the GND copper
TRACK = 0.40
THIN = 0.30
EDGE = 0.55             # all copper stops this far short of the board edge
PAD_EDGE = 0.25

# ================= the drawing: every number of the outline and the art =================
W, H = 33.0, 46.6                   # cabinet width, board height
CX = W / 2
YS = 7.0                            # shoulder height: the cabinet's flat top either side of the marquee
DOME = (CX, 11.5, 11.5)             # marquee: centre x, centre y, radius (the 20 mm cell sits concentric behind it)
BALL = (37.4, 10.3, 2.5)            # lever ball
ARM = (36.0, 38.8)                  # lever arm, left and right edge
ELBOW = (22.0, 27.0)                # where the lever joins the cabinet, top and bottom
REELS = (7.5, 16.5, 25.5)           # reel centres
REEL_Y = 26.0                       # LED height = middle of the 7s
SEVEN = [(-2.0, -2.8), (2.0, -2.8), (2.0, -1.4), (0.35, 2.8), (-1.25, 2.8), (0.2, -1.3), (-2.0, -1.3)]   # about a reel centre
LED_DX = 0.6                        # the 7's stem crosses the middle row 0.6 mm right of the reel centre: the LED goes there


def arc(cx, cy, r, a0, a1, step=3.0):
    """Points on a circle from angle a0 to a1 (degrees; 0 = right, 90 = down, as seen on the board)."""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
            for k in range(n + 1)]


def rrect(x0, y0, x1, y1, r):
    return (arc(x0 + r, y0 + r, r, 180, 270) + arc(x1 - r, y0 + r, r, 270, 360)
            + arc(x1 - r, y1 - r, r, 0, 90) + arc(x0 + r, y1 - r, r, 90, 180))


def star(cx, cy, ro, ri):
    return [(cx + (ro if k % 2 == 0 else ri) * math.cos(math.radians(-90 + 36 * k)),
             cy + (ro if k % 2 == 0 else ri) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)]


_dome_a = math.degrees(math.asin((DOME[1] - YS) / DOME[2]))             # where the marquee meets the shoulders
_ball_a = math.degrees(math.acos((BALL[0] - ARM[0]) / BALL[2]))          # where the arm meets the ball
OUTLINE = (arc(2, YS + 2, 2, 180, 270)                                   # left shoulder corner
           + arc(DOME[0], DOME[1], DOME[2], 180 + _dome_a, 360 - _dome_a)   # marquee
           + arc(W - 2, YS + 2, 2, 270, 360)                             # right shoulder corner
           + arc(W + 1, ELBOW[0] - 1, 1, 180, 90, 15)                    # down the side into the notch behind the arm
           + arc(ARM[0] - 1, ELBOW[0] - 1, 1, 90, 0, 15)
           + arc(BALL[0], BALL[1], BALL[2], 180 - _ball_a, 360 + _ball_a)   # up the arm, round the ball
           + arc(ARM[1] - 1.5, ELBOW[1] - 1.5, 1.5, 0, 90, 10)           # down the arm, round the elbow
           + [(W, ELBOW[1])]
           + arc(W - 2, H - 2, 2, 0, 90) + arc(2, H - 2, 2, 90, 180))    # the flat bottom

# gold = openings in the solder mask over the front copper. Each entry: [outer ring, hole, hole ...]
GOLD = {
    "marquee arch": [arc(DOME[0], DOME[1], 9.7, 180, 360) + arc(DOME[0], DOME[1], 8.5, 360, 180)],
    "big star": [star(CX, 6.0, 2.1, 0.9)],
    "left star": [star(CX - 5.6, 8.6, 1.25, 0.55)],
    "right star": [star(CX + 5.6, 8.6, 1.25, 0.55)],
    "trim line": [rrect(4.0, 33.1, 29.0, 33.9, 0.4)],
    "button": [arc(5.8, 37.3, 1.6, 0, 360, 10)[:-1]],
    "coin slit": [rrect(26.95, 35.7, 27.65, 38.7, 0.3)],
    "payout tray": [rrect(9.5, 38.1, 23.5, 41.9, 1.2), rrect(10.7, 39.2, 22.3, 40.8, 0.7)],
    "base": [rrect(1.6, 43.7, 31.4, 45.95, 0.6)],
    "lever ball": [arc(BALL[0], BALL[1], BALL[2] - 0.6, 0, 360, 10)[:-1]],
    "lever elbow": [rrect(33.9, 22.75, 38.15, 26.35, 0.8)],
}
for _i, _c in enumerate(REELS):
    GOLD[f"reel {_i + 1}"] = [rrect(_c - 3.5, REEL_Y - 4.0, _c + 3.5, REEL_Y + 4.0, 0.8),
                              [(_c + x, REEL_Y + y) for x, y in SEVEN]]
SEVENS = [[(c + x, REEL_Y + y) for x, y in SEVEN] for c in REELS]       # bare board: no copper, no mask
# white silkscreen lines: (points, line width, closed?)
SILK = [
    (rrect(2.4, 20.4, 30.6, 31.6, 1.6), 0.6, True),                      # frame round the reels
    ([(BALL[0], BALL[1] + BALL[2] + 0.5), (BALL[0], 22.0)], 1.0, False),  # lever arm
    (arc(5.8, 37.3, 2.5, 0, 360, 10)[:-1], 0.4, True),                   # ring round the button
    (rrect(26.0, 34.7, 28.6, 39.7, 0.6), 0.4, True),                     # coin slot plate
]
TITLE = ("JACKPOT", CX, 15.6, 2.4, 2.8, 0.45)                            # text, centre x, centre y, char width, height, line

# ================= parts (back side; positions in the same front-view coordinates) =================
BAT = (DOME[0], DOME[1])            # cell concentric with the marquee; open end up, closed end down
CONN = (CX, 35.2)
SW = (CX, H - 2.08)                 # outer solder tabs end PAD_EDGE inside the bottom edge; the knob sticks out 1.07 mm
LEDS = {"D1": (REELS[0] + LED_DX, REEL_Y, -1), "D2": (REELS[1] + LED_DX, REEL_Y, 1), "D3": (REELS[2] + LED_DX, REEL_Y, 1)}  # +1: anode right
RES = {"R1": (3.3, REEL_Y), "R2": (21.0, REEL_Y), "R3": (30.0, REEL_Y)}
BUS_Y = 28.1                        # switched supply, under the resistors
LANE_A, LANE_B = 41.25, 41.85       # two tracks between the connector's lower pads and the switch pins
LOGO_AT = (26.75, 35.9)


def V(x, y):
    return VECTOR2I(FromMM(x + OX), FromMM(y + OY))


def lmm(v):
    return (round(ToMM(v.x) - OX, 3), round(ToMM(v.y) - OY, 3))


def lpoly(rings):
    """SHAPE_POLY_SET from [outer, hole, ...] in drawing coordinates."""
    if rings and isinstance(rings[0], tuple):
        rings = [rings]
    out = None
    for ring in rings:
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for x, y in ring:
            ps.Append(FromMM(x + OX), FromMM(y + OY))
        if out is None:
            out = ps
        else:
            out.BooleanSubtract(ps)
    return out


board = pcbnew.CreateEmptyBoard()
TRACKS = []

# ---- outline ---------------------------------------------------------------------------------
body = lpoly(OUTLINE)
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(lpoly(OUTLINE))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
json.dump({"outer": [[round(x + OX, 4), round(y + OY, 4)] for x, y in OUTLINE], "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)
_bb = bbox_mm(body)
print("board %.1f x %.1f mm" % (_bb[2] - _bb[0], _bb[3] - _bb[1]))

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
    fp.SetPosition(V(*pos))
    fp.Flip(V(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
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
                px, py = lmm(pad.GetPosition())
                d = abs(px - want[1][0]) + abs(py - want[1][1])
                if best is None or d < best[0]:
                    best = (d, rot)
    assert best[0] < 0.05, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def padpos(fp, num):
    return [lmm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))      # 3.3 V top left in front view, key slot up
sw = place("SW1", SW, ("1", (SW[0] + 3.0, SW[1] - 1.43)))            # pins toward the connector; pin 1 (badge) lands right
assert abs(padpos(sw, "4")[0] - (SW[0] - 3.0)) < 0.01
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
print("switch knob tip %.2f mm past the bottom edge" % (ToMM(_kb.GetBottom()) - OY - H))
led = {r: place(r, (x, y), ("1", (x - s * 1.55, y))) for r, (x, y, s) in LEDS.items()}
res = {r: place(r, c, ("1", (c[0], c[1] + 0.825))) for r, c in RES.items()}       # supply pad at the bottom

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - OY - BAT[1], ToMM(c.x) - OX - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (90 - _d0)) % 360                 # closed end pointing down (+y)
bat.SetOrientationDegrees(_rot)
link(bat, "BT1")
_strap = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
print("battery clip angle", _rot, "; clip body y %.2f..%.2f" % (ToMM(_strap.GetTop()) - OY, ToMM(_strap.GetBottom()) - OY))
assert ToMM(_strap.GetBottom()) - OY > BAT[1] + 10, "the clip's closed end is not pointing down"
for g in bat.GraphicalItems():                           # the clip's own silkscreen goes to the fab layer; labels below
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

# the maker's 'nsec 2025' logo, turned on its side beside the connector
logo = pcbnew.FootprintLoad(LOGO_LIB, "nsec-2025")
assert logo is not None
board.Add(logo)
logo.SetPosition(V(*LOGO_AT))
logo.Flip(V(*LOGO_AT), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
logo.SetOrientationDegrees(90)
logo.Reference().SetVisible(False)
logo.SetFPID(pcbnew.LIB_ID("footprints", "nsec-2025"))
logo.SetAttributes(logo.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
_lb = logo.GetBoundingBox(False)
print("logo x %.2f..%.2f y %.2f..%.2f" % (ToMM(_lb.GetLeft()) - OX, ToMM(_lb.GetRight()) - OX, ToMM(_lb.GetTop()) - OY, ToMM(_lb.GetBottom()) - OY))

for fp in board.GetFootprints():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
# the whole cell stays on the board
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, V(*BAT), 10.05)
_cell.BooleanSubtract(body)
assert _cell.OutlineCount() == 0, "the cell overhangs the board"
# the connector's pads are 3 mm or more from every edge
for pad in conn.Pads():
    off = pad_poly(pad, B_Cu)
    off.BooleanSubtract(grown(body, -3.0))
    assert off.OutlineCount() == 0, "connector pad closer than 3 mm to an edge"


# ---- routing (back copper only, no vias) ----------------------------------------------------------
def route(net, pts, width=TRACK, clear=CLEAR):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(*a))
        t.SetEnd(V(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear))


j1 = padpos(conn, "1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
RIGHT_X = CONN[0] + 4.0             # lane right of the connector pads, under its body
LEFT_X = CONN[0] - 4.9              # lane left of them
SIDE_X = 1.3                        # lane up the cabinet's left side (front view)

# badge 3.3 V: switch pin 1 -> right of the connector pads -> between its two pad rows -> into pin 1 from below
# (not over the top of the pads: that would wall the connector's GND pad in)
route("VSAO", [s1, (s1[0], LANE_B + 0.15), (RIGHT_X, LANE_B - 0.85), (RIGHT_X, CONN[1]), (j1[0], CONN[1]), j1], width=THIN)
# switched supply: switch pin 3 -> left of the connector pads -> a rail under the three resistors
route("VLOAD", [s3, (s3[0], LANE_A), (LEFT_X, LANE_A), (LEFT_X, BUS_Y)], width=THIN)
route("VLOAD", [(RES["R1"][0], BUS_Y), (RES["R3"][0], BUS_Y)])
for r, fp in res.items():
    a = padpos(fp, "1")
    route("VLOAD", [(a[0], BUS_Y), a])
# coin cell: the clip joins its two solder tabs itself; a link round the closed end (outside the cell) makes the board
# agree without relying on it. From the left tab the cell supply runs down the cabinet's left side to switch pin 4,
# outside everything else, so the GND copper is never cut in two.
bt = sorted(lmm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
link_pts = arc(BAT[0], BAT[1], _r, 180, 0, 5)
route("VBAT", [bt[0]] + [(round(x, 4), round(y, 4)) for x, y in link_pts[1:-1]] + [bt[1]])
route("VBAT", [bt[0], (SIDE_X + 1.5, bt[0][1]), (SIDE_X, bt[0][1] + 1.5), (SIDE_X, LANE_B), (s4[0], LANE_B), s4], width=THIN)
# resistor -> LED anode; LED cathode -> a short tail out into the GND copper
for n in "123":
    ra, la, k = padpos(res["R" + n], "2"), padpos(led["D" + n], "2"), padpos(led["D" + n], "1")
    s = 1 if ra[0] > la[0] else -1
    route(f"LED{n}_A", [la, (ra[0] - s * 0.825, la[1]), ra])
    route("GND", [k, (k[0] - s * 0.95, k[1] - 0.25)], clear=0)

# ---- front: copper everywhere under the mask, except the 7s ----------------------------------------
sevens = pcbnew.SHAPE_POLY_SET()
for s7 in SEVENS:
    sevens.Append(lpoly(s7))
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
front = pcbnew.SHAPE_POLY_SET(inner)
front.BooleanSubtract(sevens)
front.BooleanSubtract(pegs)
front.Simplify()
add_filled(board, front, F_Cu)
gold_area = 0
for name, rings in GOLD.items():
    g = lpoly(rings)
    g.BooleanIntersection(inner)
    g.BooleanSubtract(pegs)
    gold_area += area_mm2(g)
    add_filled(board, g, F_Mask)
print("front copper %.0f mm2, of which bare gold %.0f mm2" % (area_mm2(front), gold_area))
for r, (x, y, _) in LEDS.items():                       # the LED really is behind its 7
    spot = pcbnew.SHAPE_POLY_SET()
    add_circle(spot, V(x, y), 0.6)
    spot.BooleanSubtract(sevens)
    assert spot.OutlineCount() == 0, f"{r} is not behind the stem of its 7"
for pts, width, closed in SILK:
    for a, b in zip(pts, pts[1:] + (pts[:1] if closed else [])):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a))
        s.SetEnd(V(*b))
        s.SetWidth(FromMM(width))
        s.SetLayer(F_SilkS)
        board.Add(s)
t = pcbnew.PCB_TEXT(board)
t.SetText(TITLE[0])
t.SetLayer(F_SilkS)
t.SetPosition(V(TITLE[1], TITLE[2]))
t.SetTextSize(VECTOR2I(FromMM(TITLE[3]), FromMM(TITLE[4])))
t.SetTextThickness(FromMM(TITLE[5]))
board.Add(t)
_tb = t.GetBoundingBox()
print("JACKPOT x %.1f..%.1f y %.1f..%.1f" % (ToMM(_tb.GetLeft()) - OX, ToMM(_tb.GetRight()) - OX, ToMM(_tb.GetTop()) - OY, ToMM(_tb.GetBottom()) - OY))

# ---- back copper: GND, cleared around everything that is not GND and out from behind the 7s ----------
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
cut.Append(grown(sevens, 0.2))
for x, y, _ in LEDS.values():
    add_circle(cut, V(x, y), 1.62)                # the LED footprint's keep-clear circle
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for trk, clear in TRACKS:
    if clear:
        trk.TransformShapeToPolygon(cut, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
cut.Simplify()
art.BooleanSubtract(cut)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)     # drop slivers thinner than 0.3 mm
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.BooleanIntersection(inner)
art.Simplify()
gnd_touch = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_touch.Append(pad_poly(pad, B_Cu))
for trk, clear in TRACKS:
    if trk.GetNetCode() == gnd_code:
        trk.TransformShapeToPolygon(gnd_touch, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_touch.Simplify()
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_touch)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        print("  GND copper piece, mm2: %.0f" % area_mm2(piece), "x %.1f..%.1f y %.1f..%.1f" % tuple(bbox_mm(piece)[i] - o for i, o in ((0, OX), (2, OX), (1, OY), (3, OY))))
    else:                                         # cut off from GND by tracks: leave it out rather than float
        print("  left out (not joined to GND), mm2: %.1f" % area_mm2(piece), "x %.1f..%.1f y %.1f..%.1f" % tuple(bbox_mm(piece)[i] - o for i, o in ((0, OX), (2, OX), (1, OY), (3, OY))))

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("SLOT MACHINE", 3.4, 35.0, 0.8, 90), ("SAO++ rA", 5.0, 35.0, 0.8, 90), ("orig. design: NorthSec", 6.6, 35.0, 0.8, 90),
          ("CR2032 + UP", 30.6, 15.5, 0.8, 90),
          ("BAT", 8.6, 45.0, 0.8, 0), ("OFF", 16.5, 41.52, 0.8, 0), ("SAO", 24.4, 45.0, 0.8, 0),
          ("1", 12.7, 29.95, 0.8, 0)]
for txt, x, y, size, rot in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(V(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- art/front.svg: the same drawing, for people -------------------------------------------------
def _path(ring):
    return "M" + " L".join("%.3f,%.3f" % p for p in ring) + " Z"


_svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 %.1f %.1f" width="%.0fmm" height="%.0fmm">' % (_bb[2] - _bb[0] + 2, H + 2, _bb[2] - _bb[0] + 2, H + 2),
        "<!-- Slot Machine front art. Drawn by SAO++ (CC-BY-SA-4.0). Generated by hardware/build_board.py: edit that, not this file. -->",
        '<path d="%s" fill="#a31621" stroke="#333" stroke-width="0.1"/>' % _path(OUTLINE)]
for name, rings in GOLD.items():
    _svg.append('<path d="%s" fill="#e3bd55" fill-rule="evenodd"><title>%s (bare gold copper)</title></path>' % (" ".join(_path(r) for r in rings), name))
for s7 in SEVENS:
    _svg.append('<path d="%s" fill="#5a4a2c"><title>7 (bare board, lit from behind)</title></path>' % _path(s7))
for pts, width, closed in SILK:
    _svg.append('<path d="%s" fill="none" stroke="#fff" stroke-width="%.2f" stroke-linecap="round" stroke-linejoin="round"/>'
                % (_path(pts) if closed else _path(pts)[:-2], width))
_svg.append('<text x="%.2f" y="%.2f" font-family="monospace" font-weight="bold" font-size="3.6" fill="#fff" text-anchor="middle">%s</text>'
            % (TITLE[1], TITLE[2] + 1.3, TITLE[0]))
_svg.append("</svg>")
os.makedirs(os.path.join(HERE, "..", "art"), exist_ok=True)
open(os.path.join(HERE, "..", "art", "front.svg"), "w").write("\n".join(_svg) + "\n")

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): lmm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): lmm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), lmm(p.GetPosition())) for p in bat.Pads()])
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = 0                # the front mask openings are the artwork
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
# the intended finish, written into the file so KiCad's 3D view and renders show it: red mask, white silkscreen, ENIG
_STACKUP = """(stackup
			(layer "F.SilkS" (type "Top Silk Screen") (color "White"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (color "Red") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (color "Red") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
		"""
_t = open(OUT, encoding="utf-8").read()
assert "(stackup" not in _t and "\n\t(setup\n\t\t" in _t
open(OUT, "w", encoding="utf-8").write(_t.replace("\n\t(setup\n\t\t", "\n\t(setup\n\t\t" + _STACKUP, 1))
print("saved", OUT)
