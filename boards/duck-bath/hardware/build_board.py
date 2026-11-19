#!/usr/bin/env python3
"""Build duck-bath.kicad_pcb from the maker's art (hardware/art.json) plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root (art.json comes from hardware/extract_art.py):
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-bath/hardware/build_board.py

What it does:
  - takes the maker's outline, his front silkscreen drawing (tub, bubbles, feet) and the position of his 5 mm RGB LED,
    and scales outline and drawing up by SCALE (owner rule of 2026-11-12: scale the whole board rather than squeeze);
    the LED itself keeps its true size, centred where his was
  - puts every other part on the back: the XIAO with its USB-C socket out of the bottom of the tub between the feet,
    the SAO connector left of it under the LED, the switch knob out of the tub bottom under the connector, the LiPo
    socket at the left wall, the six resistors in free spots
  - routes with router.py: back copper is cheap; front copper only where nobody can see it (under the black
    silkscreen lines and under the LED's body), and a via only there too
  - fills the front with copper under the mask, as the maker did, and the rest of the back with ground copper
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import sys
import time
import uuid

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402
import router  # noqa: E402
from router import B as RB, F as RF  # noqa: E402

SLUG = "duck-bath"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
T0 = time.time()

SCALE = float(os.environ.get("DUCK_SCALE", "1.45"))   # smallest step at which the XIAO, its USB plug and the LED all fit; see README
CLEAR = 0.30            # copper-to-copper gap cut into the ground copper and the front copper
EDGE = 0.55             # ground copper stops this far short of the board edge (panel mouse-bite holes reach 0.25 mm in)
SIG, PWR = 0.20, 0.30
VIA_D, VIA_HOLE = 0.6, 0.3
LED_HIDE_R = 2.3        # front copper and vias within this radius of the LED's centre are under its 5 mm body
FRONT_W = 0.15          # front tracks: thin, so a track and its gap in the front copper (0.55 mm) fit under a 0.73 mm silk line
CLEAR_F = 0.20          # gap cut into the front copper round front tracks and vias

ART = json.load(open(os.path.join(HERE, "art.json")))
_xs = [p[0] for p in ART["outline"]]
_ys = [p[1] for p in ART["outline"]]
CX, CY = (min(_xs) + max(_xs)) / 2, (min(_ys) + max(_ys)) / 2


def S(p):
    return (CX + (p[0] - CX) * SCALE, CY + (p[1] - CY) * SCALE)


def polyset(entries):
    out = pcbnew.SHAPE_POLY_SET()
    for e in entries:
        ps = pcbnew.SHAPE_POLY_SET()
        ps.NewOutline()
        for p in e["outer"]:
            x, y = S(p)
            ps.Append(FromMM(x), FromMM(y))
        for h in e["holes"]:
            ps.NewHole()
            for p in h:
                x, y = S(p)
                ps.Append(FromMM(x), FromMM(y), -1, 0)
        out.BooleanAdd(ps)
    out.Simplify()
    return out


# ---- outline ---------------------------------------------------------------------------------------
OL = [S(p) for p in ART["outline"]]


def edge_y(x, top=False):
    ys = []
    for (x1, y1), (x2, y2) in zip(OL, OL[1:] + OL[:1]):
        if (x1 - x) * (x2 - x) < 0:
            ys.append(y1 + (x - x1) * (y2 - y1) / (x2 - x1))
    return min(ys) if top else max(ys)


def bottom_of_tub(x):
    """The tub's bottom edge at x (between the feet: the second-lowest crossing where a foot hangs below)."""
    ys = []
    for (x1, y1), (x2, y2) in zip(OL, OL[1:] + OL[:1]):
        if (x1 - x) * (x2 - x) < 0:
            ys.append(y1 + (x - x1) * (y2 - y1) / (x2 - x1))
    ys.sort()
    return ys[1] if len(ys) >= 4 else ys[-1]


maker = poly(OL)
maker.Simplify()
mx0, my0, mx1, my1 = bbox_mm(maker)

# the LED: true size, centred where the maker's was (his footprint origin is pin 1; pins on 1.27 mm pitch)
LED0 = S((ART["led"]["at"][0] + 1.905, ART["led"]["at"][1]))
LEDX, LEDY = round(LED0[0], 3), round(LED0[1], 3)
LED_PIN1 = (round(LEDX - 1.905, 3), LEDY)

# the XIAO: USB-C down out of the tub bottom, right of the LED. Its centre must be (a) far enough right that its pads
# clear the LED's legs, and (b) far enough left that a USB-C plug (about 12.4 mm wide) clears the right foot
FOOT_R = None
for k in range(2000):                       # where the right foot starts: the tub bottom turns down sharply
    x = CX + k * 0.02
    if edge_y(x) - bottom_of_tub(x) > 0.05 or edge_y(x + 0.3) - edge_y(x) > 0.25:
        FOOT_R = x
        break
XC_MIN = LEDX + 1.905 + 0.535 + 0.5 + 9.43
XC_MAX = FOOT_R - 6.4
assert XC_MIN <= XC_MAX, f"scale {SCALE}: XIAO cannot sit between the LED ({XC_MIN:.2f}) and the right foot ({XC_MAX:.2f})"
XC = round(XC_MIN + (XC_MAX - XC_MIN) * float(os.environ.get("DUCK_XC_POS", "0.5")), 2)
YB = round(float(min(edge_y(float(x)) for x in np.arange(XC - 8.9, XC + 8.91, 0.1))) - 0.05, 2)    # module end: both corners on board
YC = round(YB - 10.53, 2)
print(f"scale {SCALE}: board {mx1 - mx0:.2f} x {my1 - my0:.2f}; LED at ({LEDX}, {LEDY}); XIAO x {XC} "
      f"(allowed {XC_MIN:.2f}..{XC_MAX:.2f}), end {YB} (edge under USB {edge_y(XC):.2f}); right foot at x {FOOT_R:.2f}")

# SAO connector: left of the XIAO, below the LED
JX = round(XC - 9.43 - 0.3 - 8.18, 2)
JY = round(LEDY + 0.9 + 0.30 + 6.12, 2)
# switch: under the connector, knob down out of the tub bottom
SX = JX
SY = round(min(edge_y(SX - 5.65), edge_y(SX + 5.65)) - 0.30 - 1.83, 2)
Y_CHIN = round(SY + 2.1, 2)            # the switch body's face: the tub bottom is cut flat here so the knob sticks out
assert SY - 2.48 > JY + 5.6 + 1.5, "no room between the connector and the switch"
print(f"connector ({JX}, {JY}) [{JX - CX:+.2f} from the middle], switch ({SX}, {SY}), flat at {Y_CHIN:.2f} "
      f"(tub bottom there {edge_y(SX):.2f})")

body = pcbnew.SHAPE_POLY_SET(maker)
cutbox = poly([(SX - 7.0, Y_CHIN), (SX + 7.0, Y_CHIN), (SX + 7.0, Y_CHIN + 5), (SX - 7.0, Y_CHIN + 5)])
body.BooleanSubtract(cutbox)
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
inner = grown(body, -EDGE)

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
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
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
    fp.SetFPID(pcbnew.LIB_ID(SLUG + "-local" if sym in LOCAL else "sao-plus-plus", fpid.split(":")[1]))
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


def load(ref, pos, back=True):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    fp.SetPosition(P(*pos))
    if back:
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    return fp


def place(ref, pos, want, back=True):
    """Place, then pick the right-angle rotation that puts pad `want[0]` nearest `want[1]`."""
    fp = load(ref, pos, back)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = min(abs(mm(p.GetPosition())[0] - want[1][0]) + abs(mm(p.GetPosition())[1] - want[1][1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- placement ----------------------------------------------------------------------------------
xiao = place("U1", (XC, YC), ("1", (XC - 8.05, YC + 7.56)))        # USB-C down; D0..D6 on the left, bottom to top
led = place("D1", LED_PIN1, ("4", (LED_PIN1[0] + 3.81, LEDY)), back=False)    # on the FRONT, legs through
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))          # VCC top-left in front view, key slot up
sw = place("SW1", (SX, SY), ("1", (SX + 3.0, SY - 1.43)))          # pins up, knob down; pin 1 (SAO) right
u = {n: pp(xiao, n) for n in [str(k) for k in range(1, 15)]}
j = {n: pp(conn, n) for n in "123456"}
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")

# LiPo socket at the left wall, opening to the left
WALL_L = min(x for x, y in OL if abs(y - JY) < 3.0)
JST = (round(WALL_L + 0.75 + 4.45, 2), JY)
jst = load("J2", JST)
for rot in (0, 90, 180, 270):
    jst.SetOrientationDegrees(rot)
    sig = [mm(p.GetPosition()) for p in jst.Pads() if p.GetNumber() in ("1", "2")]
    hold = [mm(p.GetPosition()) for p in jst.Pads() if p.GetNumber() == ""]
    if all(x > JST[0] + 2 for x, _ in sig) and all(x < JST[0] - 2 for x, _ in hold):
        break
else:
    raise AssertionError("no rotation puts the LiPo socket's opening to the left")
link(jst, "J2")
jp, jn = pp(jst, "1"), pp(jst, "2")

# ---- the XIAO's pad geometry (front view; USB down, so D0..D6 run up the left side, D7..D10, 3V3, GND, 5V down the right)
OUTX_L = round(XC - 8.05 - 1.375, 3)       # outer ends of the left pads
INX_L = round(XC - 8.05 + 1.375, 3)        # inner ends of the left pads
OUTX_R = round(XC + 8.11 + 1.375, 3)       # outer ends of the right pads
uy = {n: u[n][1] for n in u}
DOOR45 = round((uy["5"] + uy["4"]) / 2, 3)  # the 0.54 mm gaps between the left pads: a 0.2 mm track passes 0.17 mm from each
DOOR34 = round((uy["4"] + uy["3"]) / 2, 3)
c3_15 = pp(xiao, "15", pick=lambda q: q[0])  # C3/S3 battery + (left of the module's middle)
c6_15 = pp(xiao, "15", pick=lambda q: -q[0])   # C6 battery + (top middle)

# ---- resistors (back) -----------------------------------------------------------------------------------
# GPIO2 (WS2812 data in): lying in its own track between the connector's pin 6 and the XIAO
r6 = place("R6", (round(j["6"][0] + 0.55 + 0.25 + 1.225, 2), DOOR34), ("1", (round(j["6"][0] + 0.55 + 0.25 + 0.4, 2), DOOR34)))
# OFF sense: standing on the switch's pin 2; the badge 3.3 V line passes between its pads (VS_Y)
VS_Y = round(s2[1] - 0.75 - 0.25 - 0.4 - 0.825, 3)
r4 = place("R4", (s2[0], VS_Y), ("1", (s2[0], VS_Y + 0.825)))
# LED resistors in the channel right of the XIAO, one lane each (see the routing below)
LANE_B, LANE_G, LANE_P, LANE_R = round(OUTX_R + 0.645, 2), round(OUTX_R + 2.145, 2), round(OUTX_R + 2.995, 2), round(OUTX_R + 3.845, 2)
r3 = place("R3", (LANE_B, round(uy["8"] + 0.1, 2)), ("2", (LANE_B, round(uy["8"] + 0.1 - 0.825, 2))))   # blue, beside D7
r2 = place("R2", (LANE_G, round(uy["9"] - 2.2, 2)), ("2", (LANE_G, round(uy["9"] - 2.2 - 0.825, 2))))  # green, above D8
r1 = place("R1", (LANE_P, uy["11"]), ("2", (LANE_P + 0.825, uy["11"])))                                # red: 3.3 V passes between its pads
FPS = list(board.GetFootprints())
_pad_ok = grown(body, -0.25)
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            layer = F_Cu if pad.IsOnLayer(F_Cu) and not pad.IsOnLayer(B_Cu) else B_Cu
            off = pad_poly(pad, layer)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"


def crt(fp):
    ps = pcbnew.SHAPE_POLY_SET()
    for g_ in fp.GraphicalItems():
        if g_.GetLayer() in (pcbnew.B_CrtYd, pcbnew.F_CrtYd):
            g_.TransformShapeToPolygon(ps, g_.GetLayer(), 0, ERR, pcbnew.ERROR_OUTSIDE)
    ps.Simplify()
    return ps


# courtyards on the back must not overlap (the LED's is on the front and only its legs come through)
back = [fp for fp in FPS if fp.GetReference() != "D1"]
for a_i in range(len(back)):
    for b_i in range(a_i + 1, len(back)):
        ov = crt(back[a_i])
        ov.BooleanIntersection(crt(back[b_i]))
        if ov.OutlineCount() and area_mm2(ov) > 0.01:
            print(f"  courtyard overlap {back[a_i].GetReference()}/{back[b_i].GetReference()}: {area_mm2(ov):.2f} mm2")

# ---- art layers needed by the router ----------------------------------------------------------------
silk = polyset(ART["silk"])
silk.BooleanIntersection(grown(body, -0.15))
silk.Simplify()

# ---- routing ------------------------------------------------------------------------------------------
g = router.Grid(bx0 - 0.2, by0 - 0.2, bx1 + 0.2, by1 + 0.2)


def fast_poly_mask(ps, grow):
    """Same result as router.Grid.poly_mask (cells whose centre lies inside ps grown by `grow`), by scanlines:
    the router's own version tests every cell one by one, which takes minutes on the maker's detailed art."""
    q = pcbnew.SHAPE_POLY_SET(ps)
    if grow:
        q.Inflate(FromMM(grow), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FromMM(0.005))
    q.Simplify()
    segs = []
    for i in range(q.OutlineCount()):
        chains = [q.Outline(i)] + [q.Hole(i, h) for h in range(q.HoleCount(i))]
        for c in chains:
            pts = [(ToMM(c.CPoint(k).x), ToMM(c.CPoint(k).y)) for k in range(c.PointCount())]
            segs += [(a_[0], a_[1], b_[0], b_[1]) for a_, b_ in zip(pts, pts[1:] + pts[:1])]
    m = np.zeros((g.H, g.W), dtype=bool)
    if not segs:
        return m
    S_ = np.array(segs)
    x1, y1, x2, y2 = S_[:, 0], S_[:, 1], S_[:, 2], S_[:, 3]
    xs = g.x0 + np.arange(g.W) * router.STEP
    for jj in range(g.H):
        y = g.y0 + jj * router.STEP
        hit = (y1 <= y) != (y2 <= y)
        if not hit.any():
            continue
        xc = np.sort(x1[hit] + (y - y1[hit]) * (x2[hit] - x1[hit]) / (y2[hit] - y1[hit]))
        cnt = np.searchsorted(xc, xs, side="right")
        m[jj] = (cnt % 2) == 1
    return m


g.poly_mask = fast_poly_mask
EDGE_C = 0.5 + router.HW_MAX + 0.02
okarea = g.poly_mask(body, -EDGE_C)
for L in (RB, RF):
    g.stamp(L, ~okarea, -1)
INF = router.CLR + router.HW_MAX + router.SLACK
netcode = {}


def code(name):
    if name not in netcode:
        netcode[name] = len(netcode) + 1
    return netcode[name]


PADS = []
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = ToMM(pad.GetDrillSize().x) / 2 + 0.25 + router.HW_MAX + router.SLACK
            c = mm(pad.GetPosition())
            m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= r * r
            g.stamp(RB, m, -1)
            g.stamp(RF, m, -1)
            continue
        n = pad.GetNetname() or f"nc-{fp.GetReference()}-{pad.GetNumber()}"
        for L, lay in ((RB, B_Cu), (RF, F_Cu)):
            if pad.IsOnLayer(lay):
                ps = pad_poly(pad, lay)
                g.stamp(L, g.poly_mask(ps, INF), code(n))
                PADS.append((fp.GetReference(), pad.GetNumber(), n, L, ps))
# nothing under the switch's metal shell (between its pins and its knob), and nothing under the LiPo socket
for fp_, lay_ in ((sw, pcbnew.B_Fab), (jst, pcbnew.B_Fab)):
    ps_ = pcbnew.SHAPE_POLY_SET()
    for g_ in fp_.GraphicalItems():
        if g_.GetLayer() == lay_ and g_.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
            g_.TransformShapeToPolygon(ps_, lay_, 0, ERR, pcbnew.ERROR_OUTSIDE)
    g.stamp(RB, g.poly_mask(ps_, 0.1), -1)
# the module's own test pads underneath: no copper of ours under them
for g_ in xiao.GraphicalItems():
    if g_.GetLayer() == pcbnew.Dwgs_User and g_.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        c = mm(g_.GetCenter())
        g.stamp(RB, (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (1.0 + router.HW_MAX) ** 2, -1)
# front copper and vias only where they are hidden: under the black silkscreen lines, or under the LED's body
hide_trk = g.poly_mask(silk, -(CLEAR_F + FRONT_W / 2 + 0.03))
led_m = (g.X - LEDX) ** 2 + (g.Y - LEDY) ** 2 <= LED_HIDE_R ** 2
g.cost[RF] = float(os.environ.get("DUCK_FRONT_VISIBLE", "5000"))    # visible front copper: only if there is no other way
g.cost[RF][hide_trk | led_m] = 4.0
g.noVia |= ~(g.poly_mask(silk, -0.05) | ((g.X - LEDX) ** 2 + (g.Y - LEDY) ** 2 <= (LED_HIDE_R - 0.3) ** 2))
# no vias under the connector, switch or LiPo socket bodies (under the flat XIAO module a tented via is harmless)
for fp in (conn, sw, jst):
    g.noVia |= g.poly_mask(crt(fp), 0.1)
print(f"grid ready {time.time() - T0:.0f} s; hidden front cells {int(hide_trk.sum())}, LED cells {int(led_m.sum())}")

TRACKS, VIAS = [], []
POWER = {"VSAO": PWR, "V3V3": PWR, "BAT+": PWR, "GND": PWR}

# ---- hand routing: everything except the battery, the switched 3.3 V and ground ----------------------------
# The plan (front view): the SAO connector sits left of the XIAO and under the LED. SDA crosses straight to D4.
# SCL and GPIO2 slip between the XIAO's left pads into the space under the module (Mr. Robot does the same) and
# come up to D5 and D6 from underneath, so the three never cross. The LED's four legs go right, under the top end
# of the module, and down a channel between the module and the right wall to D7, D8, D10 and 3V3; the red
# resistor R1 lets the 3.3 V line pass between its pads. R4 (OFF sense) lets the badge's 3.3 V pass between its.
HAND = []


def hand(net, pts, w=SIG):
    for a_, b_ in zip(pts, pts[1:]):
        if a_ == b_:
            continue
        HAND.append((RB, a_, b_, w, net))
        g.stamp(RB, g.seg_mask(a_, b_, w / 2 + INF), code(net))


ledp = {n: pp(led, n) for n in "1234"}
LED_TOP = round(LEDY - 0.9, 3)
BAND = {"LED_BK": 12.0, "LED_GK": 11.55, "V3V3": 11.05, "LED_RK": 10.55}     # lanes under the module's top end
OVER = {"LED_GK": 10.3, "V3V3": 9.75, "LED_RK": 9.2}                         # over the LED's legs first
DROP = {"LED_GK": 32.55, "V3V3": 33.05, "LED_RK": 33.55}                     # where each drops into its lane
# SDA: straight across in the connector's middle lane
hand("SDA", [(j["3"][0], j["3"][1] + 2.2), (j["3"][0], uy["5"]), (OUTX_L, uy["5"])])
# SCL: middle lane just below SDA, through the gap between D4 and D3... (D4/D5 pads), up under the module to D5
SCL_X = round(INX_L + 0.55, 3)
hand("SCL", [(j["4"][0], j["4"][1] - 2.2), (j["4"][0], DOOR45), (SCL_X, DOOR45), (SCL_X, uy["6"]), (INX_L, uy["6"])])
# GPIO2: pin 6 -> R6 -> through the gap between D3 and D2, up under the module (left of the C3 battery pad, then
# over it) and into D6 from underneath
G2_X1, G2_X2 = round(INX_L + 0.49, 3), round(c3_15[0] - 0.37, 3)
G2_JOG = round(c3_15[1] - 0.55 - 0.32, 3)
hand("SAO_GPIO2", [(j["6"][0], DOOR34), pp(r6, "1")])
hand("D6_TX", [pp(r6, "2"), (G2_X1, DOOR34), (G2_X1, G2_JOG), (G2_X2, G2_JOG), (G2_X2, uy["7"]), (INX_L, uy["7"])])
# OFF sense: switch pin 2 -> R4 (standing on it) -> right to D1
hand("OFF_SW", [(s2[0], s2[1] - 0.75), pp(r4, "1")])
hand("OFF_SENSE", [pp(r4, "2"), (round(OUTX_L - 1.2, 3), pp(r4, "2")[1]), (OUTX_L, uy["2"])])
# badge 3.3 V: connector pin 1 -> down between pins 2 and 4 -> between R4's pads -> switch pin 1
VSX = round((j["2"][0] + j["4"][0]) / 2, 3)
hand("VSAO", [(j["1"][0], j["1"][1] + 2.2), (j["1"][0], j["1"][1] + 2.9), (VSX, j["1"][1] + 3.6), (VSX, VS_Y), (s1[0], VS_Y), (s1[0], s1[1] - 0.75)], PWR)
# LED: blue straight out of its leg's side; the others over the legs, then down into their lanes
hand("LED_BK", [ledp["4"], (ledp["4"][0], BAND["LED_BK"]), (LANE_B, BAND["LED_BK"]), pp(r3, "2")])
for net, leg, lane in (("LED_GK", "3", LANE_G), ("V3V3", "2", LANE_P), ("LED_RK", "1", LANE_R)):
    w = PWR if net == "V3V3" else SIG
    hand(net, [ledp[leg], (ledp[leg][0], OVER[net]), (DROP[net], OVER[net]), (DROP[net] + 0.5, BAND[net]),
               (lane, BAND[net])], w)
hand("LED_GK", [(LANE_G, BAND["LED_GK"]), pp(r2, "2")])
hand("LED_G", [pp(r2, "1"), (LANE_G, uy["9"]), (OUTX_R, uy["9"])])
hand("LED_B", [pp(r3, "1"), (OUTX_R - 0.2, pp(r3, "1")[1])])
hand("V3V3", [(LANE_P, BAND["V3V3"]), (LANE_P, uy["12"]), (OUTX_R, uy["12"])], PWR)
hand("LED_RK", [(LANE_R, BAND["LED_RK"]), (LANE_R, uy["11"]), pp(r1, "2")])
hand("LED_R", [pp(r1, "1"), (OUTX_R, uy["11"])])
print("hand-routed:", sorted({n for *_, n in HAND}))

NETS_TO_ROUTE = ["BAT+", "V3V3", "GND"]
BASE_ORDER = os.environ.get("DUCK_ORDER", "BAT+,V3V3,GND").split(",")
SNAP = (g.owner.copy(), g.cost.copy(), g.noVia.copy())
TARGETS = {}
for net in BASE_ORDER:
    seen, tg = set(), []
    for ref, num, n, L, ps in PADS:
        if net == "V3V3" and ref == "D1":            # the LED's anode is already joined to the XIAO's 3V3 by hand
            continue
        key = (ref, num, mm(ps.BBox().GetCenter()))  # a through-hole leg counts once (either layer)
        if n == net and key not in seen:
            seen.add(key)
            tg.append((L, g.poly_mask(ps, 0)))
    TARGETS[net] = tg
_hid = hide_trk | led_m


def trial(order):
    """Route every net in this order on a fresh copy of the grid. Returns (segments, vias, failed, score)."""
    g.owner[:], g.cost[:], g.noVia[:] = SNAP[0], SNAP[1], SNAP[2]
    segs_all, vias_all, failed = [], [], []
    for net in order:
        w = POWER.get(net, SIG)
        if net == "GND":            # the front copper is ground: ground may use it anywhere, and stitch to it with vias
            g.cost[RF] = 1.0
            g.noVia[:] = False
            for fp in (conn, sw, jst):
                g.noVia |= g.poly_mask(crt(fp), 0.1)
        paths = router.route_net(g, code(net), TARGETS[net], w, via_cost=float(os.environ.get("DUCK_VIA", "60")))
        if paths is None:
            failed.append(net)
            continue
        for path in paths:
            sg, vs = router.simplify(g, path)
            for L, a_, b_ in sg:
                ww = w if L == RB else FRONT_W
                segs_all.append((L, a_, b_, ww, net))
                g.stamp(L, g.seg_mask(a_, b_, ww / 2 + INF), code(net))
            for c in vs:
                vias_all.append((c, net))
                m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (VIA_D / 2 + INF) ** 2
                g.stamp(RB, m, code(net))
                g.stamp(RF, m, code(net))
    vis = 0.0
    for L, a_, b_, w_, net in segs_all:
        if L != RF or net == "GND":
            continue
        n_ = max(2, int(math.dist(a_, b_) / 0.05))
        for k in range(n_ + 1):
            i_, j_ = g.ij(a_[0] + (b_[0] - a_[0]) * k / n_, a_[1] + (b_[1] - a_[1]) * k / n_)
            if not _hid[j_, i_]:
                vis += math.dist(a_, b_) / n_
    nsv = sum(1 for c, n in vias_all if n != "GND")
    length = sum(math.dist(a_, b_) for L, a_, b_, w_, n in segs_all)
    score = 1000 * len(failed) + 100 * vis + 10 * nsv + length / 10
    return segs_all, vias_all, failed, score, vis, nsv


import random  # noqa: E402
rng = random.Random(1)
ORDERS = [BASE_ORDER]
signals = [n for n in BASE_ORDER if n not in ("GND",)]
ORDERS.append(["V3V3", "BAT+", "GND"])
for _ in range(int(os.environ.get("DUCK_TRIALS", "0"))):
    o = signals[:]
    rng.shuffle(o)
    ORDERS.append(o + ["GND"])
best = None
for k, order in enumerate(ORDERS):
    t1 = time.time()
    res = trial(order)
    print(f"  trial {k}: failed {res[2]}, visible {res[4]:.1f} mm, signal vias {res[5]}, score {res[3]:.0f} ({time.time() - t1:.0f} s)")
    if best is None or res[3] < best[3]:
        best = res + (order,)
    if time.time() - T0 > 420:
        print("  trial budget used up (7 minutes)")
        break
segs_all, vias_all, ROUTE_FAIL, _, _, _, ORDER = best
segs_all = HAND + segs_all
print("chosen order:", ",".join(ORDER))
for L, a_, b_, w_, net in segs_all:
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a_))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(w_))
    t.SetLayer(B_Cu if L == RB else F_Cu)
    t.SetNet(nets[net])
    board.Add(t)
    TRACKS.append((L, a_, b_, w_, net))
for c, net in vias_all:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c))
    v.SetDrill(FromMM(VIA_HOLE))
    v.SetWidth(FromMM(VIA_D))
    v.SetNet(nets[net])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append((c, net))
print("routed; vias:", len(VIAS), "front segments:", sum(1 for t in TRACKS if t[0] == RF), "failed:", ROUTE_FAIL)
# how much signal copper on the front is NOT hidden (should be none); ground on the front is part of the front copper
VISIBLE = {}
for L, a_, b_, w_, net in TRACKS:
    if L != RF or net == "GND":
        continue
    n_ = max(2, int(math.dist(a_, b_) / 0.05))
    for k in range(n_ + 1):
        x_, y_ = a_[0] + (b_[0] - a_[0]) * k / n_, a_[1] + (b_[1] - a_[1]) * k / n_
        i_, j_ = g.ij(x_, y_)
        if not _hid[j_, i_]:
            VISIBLE[net] = VISIBLE.get(net, 0) + math.dist(a_, b_) / n_
VIS_VIAS = [(c, n) for c, n in VIAS if n != "GND" and not _hid[g.ij(*c)[1], g.ij(*c)[0]]]
print("signal vias:", [(n, c) for c, n in VIAS if n != "GND"])
print("visible front signal copper (mm):", {k: round(v, 1) for k, v in VISIBLE.items()}, "vias off the silk/LED:", VIS_VIAS)

# ---- back copper: ground everywhere, cleared round every pad and track that is not ground ----------------
gnd_code = nets["GND"].GetNetCode()
cut = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu) and pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in board.Tracks():
    if t.GetNetname() != "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for g_ in xiao.GraphicalItems():
    if g_.GetLayer() == pcbnew.Dwgs_User and g_.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut, g_.GetCenter(), 0.85 + 0.15)
cut.Simplify()
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(cut)
gnd.Simplify()
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
for t in board.Tracks():
    if t.GetNetname() == "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
        t.TransformShapeToPolygon(gnd_seed, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_seed.Simplify()
GND_PIECES = []
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_seed)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["GND"])
        GND_PIECES.append(round(area_mm2(piece), 1))
gnd_pads_hit = {}
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            for i in range(gnd.OutlineCount()):
                piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
                pp_ = pad_poly(pad, B_Cu)
                pp_.BooleanIntersection(piece)
                if area_mm2(pp_) > 0.005:
                    gnd_pads_hit[f"{fp.GetReference()}.{pad.GetNumber()}"] = i
print("back ground pieces (mm2):", GND_PIECES, "ground pads -> piece:", gnd_pads_hit)

# ---- front: copper under the mask (the maker's front was a copper pour), and his silkscreen drawing ---------
fcut = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(F_Cu):
            pad.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.35)
for t in board.Tracks():
    if (t.GetClass() == "PCB_VIA" or t.GetLayer() == F_Cu) and t.GetNetname() != "GND":
        t.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR_F), ERR, pcbnew.ERROR_OUTSIDE)
fcut.Simplify()
fseed = pcbnew.SHAPE_POLY_SET()
for t in board.Tracks():
    if (t.GetClass() == "PCB_VIA" or t.GetLayer() == F_Cu) and t.GetNetname() == "GND":
        t.TransformShapeToPolygon(fseed, F_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
fseed.Simplify()
fcu = pcbnew.SHAPE_POLY_SET(inner)
fcu.BooleanSubtract(fcut)
fcu.Simplify()
n_f = 0
for i in range(fcu.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(fcu.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(fseed)
    on_gnd = area_mm2(both) > 0.005
    if area_mm2(piece) > 0.05 and not os.environ.get("DUCK_NOFILL"):      # DUCK_NOFILL=1: leave it out, to look at the routing
        n_f += add_filled(board, piece, F_Cu, nets["GND"] if on_gnd else None)
        print("  front piece mm2", round(area_mm2(piece), 1), "ground" if on_gnd else "loose")
print("front copper pieces", n_f)
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
fsilk = pcbnew.SHAPE_POLY_SET(silk)
fsilk.BooleanSubtract(pegs)
fsilk.Simplify()
add_filled(board, fsilk, pcbnew.F_SilkS)

# ---- back silkscreen ------------------------------------------------------------------------------------
LABELS = [("duckBATH", 11.0, 25.2, 1.2), ("SAO++ rA", 11.0, 26.8, 0.8), ("Adrian Studer 2024", 11.0, 28.1, 0.8),
          ("NO USB", 11.0, 29.4, 0.8), ("ON SAO", 11.0, 30.6, 0.8),
          ("SAO", s1[0] + 4.0, SY - 2.2, 0.8), ("USB", SX - 6.9, SY - 0.2, 0.8),
          ("+", jp[0] + 2.6, jp[1], 0.9), ("-", jn[0] + 2.6, jn[1], 0.9), ("LiPo", JST[0], JST[1] - 6.6, 0.8),
          ("1", j["1"][0] - 1.4, j["1"][1] - 2.6, 0.8)]
for txt, x, y, size in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    board.Add(t)

# ---- report ---------------------------------------------------------------------------------------
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
pcbnew.SaveBoard(OUT, board)
print(f"saved {OUT} in {time.time() - T0:.0f} s; board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm")
