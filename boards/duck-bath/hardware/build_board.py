#!/usr/bin/env python3
"""Build duck-bath.kicad_pcb from the maker's KiCad 8 board (original/duckbath/duckbath.kicad_pcb) plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-bath/hardware/build_board.py

The maker's board is a 40 x 20 mm bathtub with one 5 mm through-hole RGB LED standing on the FRONT, in the foam; a real
little rubber duck is pushed over that LED and glows. This script:
  - scales the maker's outline and front silkscreen art by SCALE about the middle of his outline (parts keep their size)
  - replaces the LED by a 5 mm round hole at the same spot, with two side-firing RGB LEDs on the back shining into it
    from the left and from below; the duck sits over the hole on the front
  - replaces the CH32V003, its boost converter and the through-hole header by the XIAO, the SMD SAO connector, the
    power switch and the JST-PH LiPo connector (docs/standard.md section 3a)
  - routes on the back, with two short hops on the front under solder mask (SDA and the badge's 3.3 V), each through
    two covered vias, and covered vias that tie the back ground copper to the front ground plate
All working coordinates are millimetres relative to the centre of the duck hole (x right, y down, KiCad front view);
h() turns them into board coordinates.
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
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "duck-bath"
SRC = os.path.join(HERE, "..", "original", "duckbath", "duckbath.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

SCALE = 1.6         # the maker's outline and art, about the middle of his outline (README "Why the board is bigger")
HOLE_R = 2.5        # the duck hole: the size of the 5 mm LED it replaces
CLEAR = 0.30        # copper-to-copper gap cut into the ground copper
EDGE = 0.55         # ground copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20
PWR = 0.40
VIA_D, VIA_W = 0.3, 0.6

# ---- the maker's board, scaled -----------------------------------------------------------------------
orig = pcbnew.LoadBoard(SRC)
_bb = orig.GetBoardEdgesBoundingBox()
C0 = (round(ToMM(_bb.GetCenter().x), 3), round(ToMM(_bb.GetCenter().y), 3))


def sc(x, y):
    return (C0[0] + SCALE * (x - C0[0]), C0[1] + SCALE * (y - C0[1]))


def scaled(ps):
    out = pcbnew.SHAPE_POLY_SET(ps)
    out.Scale(SCALE, SCALE, P(*C0))
    return out


def union(parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in parts:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


def disc(cx, cy, r, n=96):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(cx, cy), r, n)
    return ps


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


# The maker's LED (D1) stood where its four pads are; the hole goes at the middle of those pads.
_d1 = [fp for fp in orig.GetFootprints() if fp.GetReference() == "D1"][0]
_px = [mm(p.GetPosition()) for p in _d1.Pads()]
assert len(_px) == 4
H = sc(sum(p[0] for p in _px) / 4, sum(p[1] for p in _px) / 4)


def h(dx, dy):
    """Board coordinates of a point given relative to the duck hole's centre."""
    return (round(H[0] + dx, 4), round(H[1] + dy, 4))


# front silkscreen art: 19 polygon outlines (not filled), each drawn with a 0.5 or 0.26 mm pen. Each becomes the band
# between the polygon grown and shrunk by half the pen width (none has a hole, so shrinking is safe), then scaled.
SILK = []
for d in orig.GetDrawings():
    if d.GetClass() == "PCB_SHAPE" and d.GetShape() == pcbnew.SHAPE_T_POLY and d.GetLayer() == pcbnew.F_SilkS:
        assert not d.IsSolidFill(), "expected outline-only art"
        ps = pcbnew.SHAPE_POLY_SET(d.GetPolyShape())
        assert ps.OutlineCount() == 1 and ps.HoleCount(0) == 0
        band = grown(ps, ToMM(d.GetWidth()) / 2)
        band.BooleanSubtract(grown(ps, -ToMM(d.GetWidth()) / 2))
        SILK.append(scaled(band))
assert len(SILK) == 19, len(SILK)

maker0 = pcbnew.SHAPE_POLY_SET()
assert orig.GetBoardPolygonOutlines(maker0, False)
maker0.Simplify()
assert maker0.OutlineCount() == 1 and maker0.HoleCount(0) == 0
body = scaled(maker0)                       # the tub, with no hole
hole = disc(*H, HOLE_R)
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's: {(bx1 - bx0) / SCALE:.2f} x {(by1 - by0) / SCALE:.2f}; scale {SCALE}); "
      f"duck hole at ({H[0]:.2f}, {H[1]:.2f})")
inner = grown(body, -EDGE)
inner.BooleanSubtract(disc(*H, HOLE_R + 0.3))


def edge_y(dx, below=True):
    """y (relative to the hole) where the outline crosses the vertical line at dx: the lowest crossing, or the highest."""
    o = body.Outline(0)
    n = o.PointCount()
    x = H[0] + dx
    ys = []
    for i in range(n):
        a, b = o.CPoint(i), o.CPoint((i + 1) % n)
        x1, y1, x2, y2 = ToMM(a.x), ToMM(a.y), ToMM(b.x), ToMM(b.y)
        if (x1 - x) * (x2 - x) < 0:
            ys.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1) - H[1])
    return max(ys) if below else min(ys)


def edge_x(dy, left=True):
    """x (relative to the hole) where the outline crosses the horizontal line at dy: the leftmost or rightmost crossing."""
    o = body.Outline(0)
    n = o.PointCount()
    y = H[1] + dy
    xs = []
    for i in range(n):
        a, b = o.CPoint(i), o.CPoint((i + 1) % n)
        x1, y1, x2, y2 = ToMM(a.x), ToMM(a.y), ToMM(b.x), ToMM(b.y)
        if (y1 - y) * (y2 - y) < 0:
            xs.append(x1 + (x2 - x1) * (y - y1) / (y2 - y1) - H[0])
    return min(xs) if left else max(xs)


board = pcbnew.CreateEmptyBoard()
for shape in (body, hole):                  # the hole is drawn as a polygon: tools/panelize.py cannot take circles
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(pcbnew.SHAPE_POLY_SET(shape))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)

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


def place(ref, rel, want):
    """Place on the back at h(*rel), then pick the right-angle rotation that puts pad `want[0]` at h(*want[1])."""
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    pos = h(*rel)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    target = h(*want[1])
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = min(abs(mm(p.GetPosition())[0] - target[0]) + abs(mm(p.GetPosition())[1] - target[1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    """Pad centre, relative to the hole."""
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    pts = [(round(x - H[0], 3), round(y - H[1], 3)) for x, y in pts]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


def lens_dir(fp):
    """Unit vector from the footprint origin toward the lens arc the LED footprint draws on the back fab layer."""
    arcs = [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_ARC]
    assert len(arcs) == 1, (fp.GetReference(), len(arcs))
    m, o = arcs[0].GetArcMid(), fp.GetPosition()
    dx, dy = ToMM(m.x - o.x), ToMM(m.y - o.y)
    return dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)


# ---- placement (relative to the hole) ---------------------------------------------------------------
# XIAO: USB end down, between the hole and the right foot. Its end is 1.2 mm above the tub's bottom edge at the middle
# of the socket (the edge is bowed), so the socket still sticks out past the board and a plug seats fully.
XC, YC = 14.7, 11.87
xiao = place("U1", (XC, YC), ("14", (XC + 8.11, YC + 7.56)))
assert abs(pp(xiao, "1")[0] - (XC - 8.055)) < 0.01, "pads 1-7 (D0-D6) should face the connector"
USB_END = YC + 12.04                        # the socket's outer end
_plug = rect(*h(XC - 6.3, USB_END), *h(XC + 6.3, USB_END + 20))       # where a USB-C plug's body goes
_plug.BooleanIntersection(grown(body, 0.2))
assert area_mm2(_plug) < 0.001, "the board is in the way of a USB plug"
_over = rect(*h(XC - 8.94, YC - 10.53), *h(XC + 8.94, YC + 10.53))
_over.BooleanSubtract(body)
print(f"XIAO: module end {USB_END - 1.51 - edge_y(XC):.2f} mm from the tub edge at mid-socket (negative = inside); "
      f"{area_mm2(_over):.2f} mm2 of the module's end corner hangs over the notch beside the right foot")
assert area_mm2(_over) < 1.0

JX, JY = -3.3, 14.0                          # SAO connector, key slot up, 4.7 mm left of the hole's centre line
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))
assert edge_y(JX) - (JY + 4.5) >= 3.0, "connector body closer than 3 mm to the bottom edge"

SY = 9.8                                     # switch on the left wall of the tub, which is straight from y = 4.1 to 15.5
_wall = [edge_x(SY + k / 4) for k in range(-23, 24)]
WALL = max(_wall)                            # the wall wanders by 0.15 mm; the switch's tabs sit 0.27 mm inside its innermost point
print(f"left wall under the switch: x {min(_wall):.2f} .. {WALL:.2f}")
SX = round(WALL + 2.1 + 0.005, 2)
sw = place("SW1", (SX, SY), ("1", (SX + 1.43, SY + 3.0)))            # knob out of the left wall; pin 1 (SAO) lowest

LX = -16.3                                   # LiPo connector: plug in from the bottom edge, beside the left foot
LY = round(min(edge_y(LX + dx) for dx in (-4.1, -3.35, -2.6, 2.6, 3.35, 4.1)) - 0.3 - 4.6 - 0.02, 2)
jst = place("J2", (LX, LY), ("1", (LX + 1.0, LY - 2.85)))

LED1 = (0.0, HOLE_R + 0.1 + 1.05)            # below the hole, lens up: its tip stops 0.1 mm short of the hole's edge
LED2 = (-(HOLE_R + 0.1 + 1.05), 0.0)         # left of the hole, lens to the right
led1 = place("D1", LED1, ("3", (LED1[0] + 1.405, LED1[1] + 0.3)))
led2 = place("D2", LED2, ("3", (LED2[0] - 0.3, LED2[1] + 1.405)))
assert lens_dir(led1)[1] < -0.999 and lens_dir(led2)[0] > 0.999, "LED lenses must point into the hole"

R1_C, R2_C = (20.5, -2.1), (20.5, -0.1)      # above the XIAO: LED data resistor, and the one on SAO GPIO1
R3_C = (1.875, 20.9)                          # under the connector: the one on SAO GPIO2
C1_C = (-7.775, 2.6)
r1 = place("R1", R1_C, ("1", (R1_C[0] + 0.825, R1_C[1])))
r2 = place("R2", R2_C, ("1", (R2_C[0] - 0.825, R2_C[1])))
r3 = place("R3", R3_C, ("1", (R3_C[0] - 0.825, R3_C[1])))
c1 = place("C1", C1_C, ("1", (C1_C[0] + 0.775, C1_C[1])))

_pad_ok = grown(body, -0.25)
_pad_ok.BooleanSubtract(disc(*H, HOLE_R + 0.25))
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to an edge"

# ---- routing ----------------------------------------------------------------------------------------
TRACKS = []
VIAS = []          # (x, y, net) in board coordinates


def route(net, pts, width=SIG, clear=CLEAR, layer=B_Cu):
    pts = [h(*p_) for p_ in pts]
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear, net))


def via(rel, net):
    x, y = h(*rel)
    v = pcbnew.PCB_VIA(board)
    board.Add(v)
    v.SetPosition(P(x, y))
    v.SetDrill(FromMM(VIA_D))
    v.SetWidth(FromMM(VIA_W))
    v.SetNet(nets[net])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED)
    VIAS.append((x, y, net))


u = {n: pp(xiao, n) for n in ("2", "5", "6", "7", "8", "11", "12")}
j = {n: pp(conn, n) for n in "123456"}
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
PL = XC - 8.055 - 1.375                      # outer ends of the XIAO's left pads (D0..D6)
PLI = XC - 8.055 + 1.375                     # their inner ends, under the module
PR = XC + 8.11 + 1.375                       # outer ends of its right pads
PRI = XC + 8.11 - 1.375
J_TOP, J_BOT = JY - 5.6, JY + 5.6            # outer ends of the connector's two pad rows
GAPROW = JY                                  # the gap between the connector's pad rows

# 3.3 V rail. XIAO 3V3 pin -> under the module, up its right-hand side and across under its top end -> down beside
# the connector -> through the gap between the connector's pad rows -> left, above the LiPo connector -> switch
# pin 3 (the common). From there it carries on up and across to the two LEDs and their capacitor.
V_IN = XC + 5.5
V_TOP = YC - 9.47
route("V3V3", [u["12"], (V_IN, u["12"][1]), (V_IN, V_TOP), (4.0, V_TOP), (4.0, 6.0), (1.2, 8.8), (1.2, GAPROW),
               (JX - 4.0, GAPROW), (JX - 6.4, 11.6), (s3[0] + 3.1, 11.6), (s3[0] + 3.1, s3[1]), s3], PWR)
LED_V = 4.85                                 # the LEDs' 3.3 V line, just under LED D1's pads
V1, V2 = pp(led1, "4"), pp(led2, "4")
route("V3V3", [(s3[0] + 3.1, s3[1]), (s3[0] + 3.1, LED_V), (V1[0], LED_V), V1], 0.3)
C1P = pp(c1, "1")
route("V3V3", [(C1P[0], LED_V), C1P, (C1P[0], V2[1]), V2], 0.25)

# LED data: XIAO D10 -> up the outside of the module's right pads -> R1 -> along the top -> down beside the hole -> D1
route("LED_DATA", [u["11"], (PR + 1.2, u["11"][1]), (PR + 1.2, R1_C[1]), pp(r1, "1")])
D1I = pp(led1, "3")
route("LED_DIN", [pp(r1, "2"), (3.0, R1_C[1]), (3.0, D1I[1]), D1I])
D1O, D2I = pp(led1, "2"), pp(led2, "3")
route("LED_D1", [D1O, (-2.9, D1O[1]), (D2I[0], D1O[1] - (D2I[0] + 2.9) * -1), D2I], SIG, 0.2)

# SAO GPIO1: XIAO D7 -> R2 -> along the top, under the LED line -> down beside the hole -> connector pin 5 from above
route("D7_RX", [u["8"], (PR + 0.6, u["8"][1]), (PR + 0.6, R2_C[1]), pp(r2, "2")])
route("SAO_GPIO1", [pp(r2, "1"), (3.5, R2_C[1]), (3.5, 5.4), (j["5"][0], 5.4), (j["5"][0], J_TOP)])

# SAO GPIO2: XIAO D6 -> down the channel between the connector's pads and the XIAO -> R3 -> connector pin 6 from below
route("D6_TX", [u["7"], (4.7, u["7"][1]), (4.7, 6.1), (2.7, 8.1), (2.7, R3_C[1])])
route("SAO_GPIO2", [pp(r3, "1"), (j["6"][0], R3_C[1]), (j["6"][0], J_BOT)])

# SCL: XIAO D5 -> down the channel -> under R3 -> connector pin 4 from below
SCL_Y = 21.85
route("SCL", [u["6"], (4.9, u["6"][1]), (3.5, u["6"][1] + 1.4), (3.5, SCL_Y), (j["4"][0], SCL_Y), (j["4"][0], J_BOT)])

# SDA: XIAO D4 -> via beside its pad -> 6.6 mm on the front (under mask) -> via above the connector -> pin 3 from above.
# Three lines run down the channel between D4 and that pin, so SDA has to hop over them.
SDA_A, SDA_B = (PL - 0.87, u["5"][1]), (j["3"][0] + 1.3, J_TOP - 0.9)
route("SDA", [u["5"], SDA_A])
route("SDA", [SDA_A, SDA_B], SIG, 0.2, F_Cu)
route("SDA", [SDA_B, (j["3"][0], J_TOP - 0.9), (j["3"][0], J_TOP)])
via(SDA_A, "SDA")
via(SDA_B, "SDA")

# OFF sense: XIAO D1 -> under the module, down and out below pad D0 -> along the bottom edge under the connector ->
# up beside the LiPo connector -> under its body -> switch pin 2
OFF_X = PLI + 0.5
OFF_Y, BAT_Y = 22.75, 22.3
OFF_L = JX - 8.5                             # riser left of the connector
LANE_BAT, LANE_OFF = LY - 0.55, LY + 0.2     # two lanes under the LiPo connector's body, between its pads and hold-downs
route("OFF_SENSE", [u["2"], (OFF_X, u["2"][1]), (OFF_X, 21.0), (4.9, 21.0), (4.9, OFF_Y), (-7.6, OFF_Y), (-8.15, 22.2),
                    (OFF_L, 22.2), (OFF_L, LANE_OFF), (s2[0] + 2.3, LANE_OFF), (s2[0] + 2.3, s2[1]), s2])

# LiPo +: connector pin 1 -> under its body -> down beside the connector -> along the bottom edge -> up the channel ->
# between the XIAO's D2 and D1 pads -> the C3 / S3 battery pad -> the C6 battery pad
bp_a = pp(xiao, "15", pick=lambda p: -p[1])       # lower one (C3 / S3)
bp_b = pp(xiao, "15", pick=lambda p: p[1])        # upper one (C6)
lp = pp(jst, "1")
BAT_L = OFF_L + 0.5
BAT_GAP = (pp(xiao, "3")[1] + u["2"][1]) / 2      # between pads D2 and D1
BAT_UP = XC - 2.7                                  # between the battery pads and the module's own test pads
route("BAT+", [lp, (lp[0], LANE_BAT), (BAT_L, LANE_BAT), (BAT_L, 21.75), (-7.55, 21.75), (-7.0, BAT_Y), (4.2, BAT_Y)], 0.25)
route("BAT+", [(4.2, BAT_Y), (4.2, BAT_GAP), (BAT_UP, BAT_GAP)], SIG, 0.16)
route("BAT+", [(BAT_UP, BAT_GAP), (BAT_UP, bp_a[1]), bp_a], 0.25)
route("BAT+", [(BAT_UP, bp_a[1]), (BAT_UP, bp_b[1] + 2.0), (bp_b[0], bp_b[1] + 2.0), bp_b], 0.25)

# badge 3.3 V: connector pin 1 -> left -> via -> a 4 mm hop on the front over the 3.3 V rail and the OFF line -> via
# -> switch pin 1
VS_A, VS_B = (s3[0] + 4.0, 10.4), (s1[0] + 1.35, s1[1])
route("VSAO", [(j["1"][0], 10.4), VS_A], PWR)
route("VSAO", [VS_A, VS_B], PWR, 0.2, F_Cu)
route("VSAO", [VS_B, s1], 0.3)
via(VS_A, "VSAO")
via(VS_B, "VSAO")

# ---- ground copper on the back: everywhere, cut round everything that is not ground ---------------------
gnd_code = nets["GND"].GetNetCode()
cut_b, cut_f = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            for c_ in (cut_b, cut_f):
                add_circle(c_, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu) and pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut_b, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t, clear, net in TRACKS:
    t.TransformShapeToPolygon(cut_b if t.GetLayer() == B_Cu else cut_f, t.GetLayer(), FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
for x, y, net in VIAS:
    for c_ in (cut_b, cut_f):
        add_circle(c_, P(x, y), VIA_W / 2 + CLEAR)
n_keep = 0
for g in xiao.GraphicalItems():              # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut_b, g.GetCenter(), 0.85 + 0.15)
        n_keep += 1
assert n_keep == 8, n_keep
cut_b.Simplify()
cut_f.Simplify()

# front: one ground plate under the mask, as on the maker's board (his was a ground fill too)
plate = pcbnew.SHAPE_POLY_SET(inner)
plate.BooleanSubtract(cut_f)
plate.Simplify()
_pp = sorted([pcbnew.SHAPE_POLY_SET(plate.Polygon(i)) for i in range(plate.OutlineCount())], key=lambda q: -area_mm2(q))
assert len(_pp) >= 1 and all(area_mm2(q) < 1 for q in _pp[1:]), "the front ground plate is split"
plate = _pp[0]
add_filled(board, plate, F_Cu, nets["GND"])
plate_ok = grown(plate, -0.45)

gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(cut_b)
gnd.Simplify()
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
gnd_seed.Simplify()
no_via = pcbnew.SHAPE_POLY_SET()             # stitching vias stay out from under parts, and off the front art's lines
for fp in board.GetFootprints():
    b_ = fp.GetBoundingBox(False)
    no_via.BooleanAdd(rect(ToMM(b_.GetLeft()) - 0.3, ToMM(b_.GetTop()) - 0.3, ToMM(b_.GetRight()) + 0.3, ToMM(b_.GetBottom()) + 0.3))
silk_all = union(SILK)
no_via.BooleanAdd(grown(silk_all, 0.5))
no_via.Simplify()
STITCH, n_drop = [], 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_seed)
    if area_mm2(both) <= 0.005 and area_mm2(piece) < 15:
        n_drop += 1                          # a scrap cut off between tracks, touching no ground pad: left out
        continue                             # (a big one is kept: its via makes it ground like the rest)
    add_filled(board, piece, B_Cu, nets["GND"])
    inside = grown(piece, -0.45)
    bb = bbox_mm(piece)
    # the via goes as near as it can to where the ground current is: the XIAO's GND pad for the main piece, the SAO
    # connector's GND pad for the others; out from under parts and off the lines of the front art where possible
    want = h(PR + 2.2, pp(xiao, "13")[1]) if area_mm2(piece) > 400 else h(*pp(conn, "2"))
    spot = None
    for strict in (True, False):
        best = None
        for yy in range(int(bb[1] * 4), int(bb[3] * 4) + 1):
            for xx in range(int(bb[0] * 4), int(bb[2] * 4) + 1):
                q = P(xx / 4, yy / 4)
                d_ = math.hypot(xx / 4 - want[0], yy / 4 - want[1])
                if (best is None or d_ < best[0]) and inside.Contains(q) and plate_ok.Contains(q) and not (strict and no_via.Contains(q)):
                    best = (d_, (xx / 4, yy / 4))
        if best:
            spot = best[1]
            break
    assert spot, f"no room for a stitching via in the ground piece at {[round(v_, 1) for v_ in bb]}"
    STITCH.append((spot, round(area_mm2(piece), 1)))
for (x, y), a in STITCH:
    via((x - H[0], y - H[1]), "GND")
    print(f"  ground piece of {a} mm2 on the back, tied to the front plate by a via at hole{(round(x - H[0], 2), round(y - H[1], 2))}")
print("back ground pieces", len(STITCH), "scraps dropped", n_drop)

# ---- front silkscreen: the maker's art, scaled; kept off the hole ------------------------------------------
art = pcbnew.SHAPE_POLY_SET(silk_all)
art.BooleanSubtract(disc(*H, HOLE_R + 0.2))
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        _peg = pcbnew.SHAPE_POLY_SET()
        add_circle(_peg, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.2)
        art.BooleanSubtract(_peg)
art.Simplify()
add_filled(board, art, pcbnew.F_SilkS)
_out = pcbnew.SHAPE_POLY_SET(silk_all)
_out.BooleanSubtract(grown(body, 0.01))
print(f"front art outside the outline: {area_mm2(_out):.3f} mm2 (the maker's white outline runs to the edge)")

# ---- back silkscreen ----------------------------------------------------------------------------------
LABELS = json.load(open(os.path.join(HERE, "labels.json")))["labels"]
for txt, x, y, size, rot in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(*h(x, y)))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- rules, title, save -------------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_ViasMinSize = FromMM(0.5)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.15))
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
print("vias:", [(round(x - H[0], 2), round(y - H[1], 2), n) for x, y, n in VIAS])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)

# kicad-cli 10.0.8 can rewrite the project file and drop the house rule severities: put them back every build.
SEVERITIES = json.load(open(os.path.join(HERE, "severities.json")))
if os.path.exists(PRO):
    pro = json.load(open(PRO))
    pro["board"]["design_settings"]["rule_severities"] = SEVERITIES["drc"]
    if SEVERITIES.get("erc") is not None:
        pro.setdefault("erc", {})["rule_severities"] = SEVERITIES["erc"]
    json.dump(pro, open(PRO, "w"), indent=2)
    print("re-applied rule severities to", PRO)
