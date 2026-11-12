#!/usr/bin/env python3
"""Build duck-jaws.kicad_pcb from the maker's KiCad 8 board (original/duckjaws/duckjaws.kicad_pcb) plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/duck-jaws/hardware/build_board.py

The maker's board is a 40 x 50 mm shark's head seen from the front, with the open mouth milled out. The teeth are bare
gold copper. One 5 mm through-hole RGB LED stands on the FRONT between the two middle lower teeth; a toy rubber duck is
pushed over it. Four small red LEDs on the back, at the rim of the mouth, shine sideways into the opening. This script:
  - scales the maker's outline, mouth, teeth and silkscreen art by SCALE about the middle of his outline
  - replaces the duck LED by a 5 mm round hole (HOLE_DROP lower, to leave a wall above it) with two side-firing RGB
    LEDs on the back, left and right of it, shining into it, exactly as on Duck Bath
  - replaces the four red LEDs by SAOPP-LED-01 side-firing red LEDs with 1.3 k each, all driven from XIAO pin D3
  - replaces the CH32V003, its boost converter and the pin header by the XIAO, the SMD SAO connector, the power
    switch and the JST-PH LiPo connector (docs/standard.md section 3a)
  - routes on the back, with short hops on the front under solder mask where two lines have to cross
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
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "duck-jaws"
load_local(SLUG)                              # the side-firing red LED: hardware/parts_local.py
SRC = os.path.join(HERE, "..", "original", "duckjaws", "duckjaws.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

SCALE = 1.8         # the maker's outline and art, about the middle of his outline (README "Why the board is bigger")
HOLE_R = 2.5        # the duck hole: the size of the 5 mm LED it replaces
HOLE_WALL = 0.9     # board left between the duck hole and the mouth above it
CLEAR = 0.30        # copper-to-copper gap cut into the ground copper
EDGE = 0.55         # ground copper stops this far short of the outer edge (clear of the panel's mouse-bite holes)
MOUTH_EDGE = 0.30   # ... and this far short of the mouth and the duck hole (no panel tabs there)
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


def crossings(chain, x=None, y=None):
    """Board coordinates where a closed outline crosses the vertical line at x, or the horizontal line at y."""
    n = chain.PointCount()
    out = []
    for i in range(n):
        a, b = chain.CPoint(i), chain.CPoint((i + 1) % n)
        x1, y1, x2, y2 = ToMM(a.x), ToMM(a.y), ToMM(b.x), ToMM(b.y)
        if x is not None and (x1 - x) * (x2 - x) < 0:
            out.append(y1 + (y2 - y1) * (x - x1) / (x2 - x1))
        if y is not None and (y1 - y) * (y2 - y) < 0:
            out.append(x1 + (x2 - x1) * (y - y1) / (y2 - y1))
    return sorted(out)


maker0 = pcbnew.SHAPE_POLY_SET()
assert orig.GetBoardPolygonOutlines(maker0, False)
maker0.Simplify()
assert maker0.OutlineCount() == 1 and maker0.HoleCount(0) == 1
outer = pcbnew.SHAPE_POLY_SET()
outer.AddOutline(maker0.Outline(0))
outer = scaled(outer)                        # the shark's head, with no hole
mouth = pcbnew.SHAPE_POLY_SET()
mouth.AddOutline(maker0.Hole(0, 0))
mouth = scaled(mouth)                        # the open mouth; the teeth are notches in its edge
if area_mm2(mouth) < 0:
    mouth.Outline(0).Reverse()

# The maker's duck LED (D1) stood where its four pads are, between the two middle lower teeth. The hole goes there,
# moved down so that HOLE_WALL of board is left between it and the mouth.
_d1 = [fp for fp in orig.GetFootprints() if fp.GetReference() == "D1"][0]
_px = [mm(p.GetPosition()) for p in _d1.Pads()]
assert len(_px) == 4
_led = sc(sum(p[0] for p in _px) / 4, sum(p[1] for p in _px) / 4)
_lip = max(y for y in crossings(mouth.Outline(0), x=_led[0]) if y < _led[1])      # the mouth's edge above the LED
HOLE_DROP = round(max(0.0, HOLE_WALL + HOLE_R - (_led[1] - _lip)), 3)
H = (_led[0], _led[1] + HOLE_DROP)


def h(dx, dy):
    """Board coordinates of a point given relative to the duck hole's centre."""
    return (round(H[0] + dx, 4), round(H[1] + dy, 4))


hole = disc(*H, HOLE_R)
solid = pcbnew.SHAPE_POLY_SET(outer)         # the board itself
solid.BooleanSubtract(mouth)
solid.BooleanSubtract(hole)
bx0, by0, bx1, by1 = bbox_mm(outer)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's: {(bx1 - bx0) / SCALE:.2f} x {(by1 - by0) / SCALE:.2f}; scale {SCALE}); "
      f"duck hole at ({H[0]:.2f}, {H[1]:.2f}), {HOLE_DROP} mm below the maker's LED; outline centre line at hole{(round((bx0 + bx1) / 2 - H[0], 2),)}")
# where copper may be: shrink the outer path and grow the holes separately (shrinking a shape that has a hole slits it)
inner = grown(outer, -EDGE)
inner.BooleanSubtract(grown(mouth, MOUTH_EDGE))
inner.BooleanSubtract(disc(*H, HOLE_R + MOUTH_EDGE))
inner.Simplify()

# the maker's front art
TEETH, SILK, BACKMASK = [], [], []
for d in orig.GetDrawings():
    if d.GetClass() == "PCB_SHAPE" and d.GetShape() == pcbnew.SHAPE_T_POLY:
        ps = pcbnew.SHAPE_POLY_SET(d.GetPolyShape())
        if d.GetLayer() == pcbnew.F_Mask:
            TEETH.append(scaled(ps))         # each tooth is a mask opening over a copper polygon of the same shape
        elif d.GetLayer() == pcbnew.F_SilkS:
            assert d.IsSolidFill()
            SILK.append(scaled(ps))
        elif d.GetLayer() == pcbnew.B_Mask:
            BACKMASK.append(scaled(ps))
assert (len(TEETH), len(SILK), len(BACKMASK)) == (14, 5, 2), (len(TEETH), len(SILK), len(BACKMASK))
teeth = union(TEETH)
teeth.BooleanIntersection(solid)
teeth.Simplify()


def edge_y(dx, below=True):
    """y (relative to the hole) where the outer outline crosses the vertical line at dx: the lowest crossing, or the highest."""
    ys = [y - H[1] for y in crossings(outer.Outline(0), x=H[0] + dx)]
    return max(ys) if below else min(ys)


def edge_x(dy, left=True):
    """x (relative to the hole) where the outer outline crosses the horizontal line at dy: the leftmost or rightmost crossing."""
    xs = [x - H[0] for x in crossings(outer.Outline(0), y=H[1] + dy)]
    return min(xs) if left else max(xs)


def mouth_x(dy):
    """x (relative to the hole) of the mouth's leftmost and rightmost edge on the horizontal line at dy."""
    xs = [x - H[0] for x in crossings(mouth.Outline(0), y=H[1] + dy)]
    return min(xs), max(xs)


def mouth_top(dx):
    """y (relative to the hole) of the mouth's upper edge (the gum between two upper teeth) on the vertical line at dx."""
    return min(y - H[1] for y in crossings(mouth.Outline(0), x=H[0] + dx))


board = pcbnew.CreateEmptyBoard()
for shape in (outer, mouth, hole):           # all drawn as polygons: tools/panelize.py cannot take circles
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
            # a "/" in a pin name (D6/TX) is written {slash} in a net name, or the schematic parity check complains
            net = f"unconnected-({ref}-{PINNAMES[ref][num].replace('/', '{slash}')}-Pad{num})"
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def lens_dir(fp):
    """Unit vector from the footprint origin toward the lens arc the LED footprints draw on the back fab layer."""
    arcs = [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_ARC]
    assert len(arcs) == 1, (fp.GetReference(), len(arcs))
    m, o = arcs[0].GetArcMid(), fp.GetPosition()
    dx, dy = ToMM(m.x - o.x), ToMM(m.y - o.y)
    return dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)


def place(ref, rel, want=None, lens=None):
    """Place on the back at h(*rel). The right-angle rotation is the one that puts pad `want[0]` at h(*want[1]), or,
    for an LED, the one that points its lens along the unit vector `lens`."""
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    pos = h(*rel)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        if lens:
            lx, ly = lens_dir(fp)
            d = abs(lx - lens[0]) + abs(ly - lens[1])
        else:
            target = h(*want[1])
            d = min(abs(mm(p.GetPosition())[0] - target[0]) + abs(mm(p.GetPosition())[1] - target[1])
                    for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no right-angle rotation fits (best miss {best[0]:.2f})"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    """Pad centre, relative to the hole."""
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    pts = [(round(x - H[0], 3), round(y - H[1], 3)) for x, y in pts]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- placement (relative to the hole) ---------------------------------------------------------------
CX = round((bx0 + bx1) / 2 - H[0], 2)        # the outline's centre line

# XIAO: on the centre line, USB end down. The bottom edge is bowed (lowest in the middle): the module's end is level
# with the edge at the module's two corners, so nothing hangs over, and sits a little inside it at the middle.
XC = CX
YC = round(min(edge_y(XC - 8.9), edge_y(XC + 8.9)) - 10.53 - 0.02, 2)
xiao = place("U1", (XC, YC), ("14", (XC + 8.11, YC + 7.56)))
assert abs(pp(xiao, "1")[0] - (XC - 8.055)) < 0.01, "pads 1-7 (D0-D6) should be on the left (front view)"
USB_END = YC + 12.04                         # the socket's outer end
_plug = rect(*h(XC - 6.3, USB_END), *h(XC + 6.3, USB_END + 20))       # where a USB-C plug's body goes
_plug.BooleanIntersection(grown(outer, 0.2))
assert area_mm2(_plug) < 0.001, "the board is in the way of a USB plug"
_over = rect(*h(XC - 8.94, YC - 10.53), *h(XC + 8.94, YC + 10.53))
_over.BooleanSubtract(solid)
print(f"XIAO: module end {edge_y(XC) - (YC + 10.53):.2f} mm inside the edge at mid-socket, socket sticks out {USB_END - edge_y(XC):.2f}; "
      f"{area_mm2(_over):.2f} mm2 of the module is off the board; its top end is at y {YC - 10.53:.2f}, the gum line above it at "
      f"{max(max(y - H[1] for y in crossings(mouth.Outline(0), x=H[0] + XC + k / 4)) for k in range(-35, 36)):.2f}")
assert area_mm2(_over) < 0.05, "the module shows in the mouth or hangs over the edge"
PT = YC - 7.68 - 1.0                         # top of the XIAO's top pads (D6, D7)
PL, PLI = XC - 8.055 - 1.375, XC - 8.055 + 1.375        # outer and inner ends of its left pads (D0..D6)
PRI, PR = XC + 8.11 - 1.375, XC + 8.11 + 1.375          # inner and outer ends of its right pads


def gap(n):
    """y of the middle of the gap between XIAO pad rows n and n+1, counted from the top (row 0 = D6 / D7)."""
    return YC - 7.68 + 2.54 * n + 1.27


JX, JY = -21.0, round(YC - 0.5, 2)                          # SAO connector, key slot up, in the left half of the lower jaw
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))
assert edge_y(JX) - (JY + 4.5) >= 3.0, "connector body closer than 3 mm to the bottom edge"

SY = 9.6                                     # switch on the right edge of the lower jaw, the straightest stretch of outline
_wall = [edge_x(SY + k / 4, left=False) for k in range(-23, 24)]
WALL = min(_wall)                            # the edge bows by ~0.6 mm along the switch; the tabs sit inside its innermost point
print(f"right edge under the switch: x {min(_wall):.2f} .. {max(_wall):.2f}")
SX = round(WALL - 2.1 - 0.005, 2)
sw = place("SW1", (SX, SY), ("1", (SX - 1.43, SY - 3.0)))            # knob out of the right edge; pin 1 (SAO) highest

LX = 17.0                                    # LiPo connector: plug in from the bottom edge, right of the XIAO
LY = round(min(edge_y(LX + dx) for dx in (-4.1, -3.35, -2.6, 2.6, 3.35, 4.1)) - 0.3 - 4.6 - 0.02, 2)
jst = place("J2", (LX, LY), ("1", (LX + 1.0, LY - 2.85)))

# the duck light: two RGB LEDs left and right of the hole, lenses 0.1 mm short of its edge
LEDX = HOLE_R + 0.1 + 1.05
led1 = place("D1", (-LEDX, 0.0), lens=(1, 0))
led2 = place("D2", (LEDX, 0.0), lens=(-1, 0))
assert pp(led1, "3")[1] > 1.3 and pp(led2, "3")[1] < -1.3, "expected D1's data input at the bottom and D2's at the top"

R1_C = (PR + 1.05, PT + 1.1)                 # LED data resistor, standing beside the XIAO's top right pad
r1 = place("R1", R1_C, ("2", (R1_C[0], R1_C[1] - 0.825)))
R2_C = (PL - 2.6, PT + 0.7)                  # the one on SAO GPIO2, left of the XIAO's top left pad
r2 = place("R2", R2_C, ("2", (R2_C[0] + 0.825, R2_C[1])))
VX = PR + 2.15                               # the 3.3 V riser right of the XIAO
C1_C = (VX + 0.975, YC - 4.0)
c1 = place("C1", C1_C, ("1", (C1_C[0] - 0.775, C1_C[1])))

# the four red lights. The lens tip of the side-firing LED is 0.81 mm ahead of the footprint's origin; it stops
# 0.1 mm short of the mouth's edge. Each has its resistor in line with it, on the anode side.
RED_Y = -8.8                                 # the two on the side walls of the mouth
RED_UP = (-6.6, 8.5)                         # the two in the upper gum, in the gaps between teeth 2-3 and 4-5
TIP = 0.81 + 0.1
mlx, mrx = mouth_x(RED_Y)
for dy_ in (-0.6, 0.6):
    assert abs(mouth_x(RED_Y + dy_)[0] - mlx) < 0.1 and abs(mouth_x(RED_Y + dy_)[1] - mrx) < 0.1, "mouth wall not straight at the side LEDs"
red = {}
red["D3"] = place("D3", (mlx - TIP, RED_Y), lens=(1, 0))
red["D6"] = place("D6", (mrx + TIP, RED_Y), lens=(-1, 0))
for ref, dx in zip(("D4", "D5"), RED_UP):
    top = min(mouth_top(dx + k / 10) for k in range(-16, 17))        # the gum slopes a little: clear its highest point under the pads
    assert all(abs(mouth_top(dx + k / 10) - top) < 0.3 for k in range(-6, 7)), f"{ref}: no flat gum under the lens"
    red[ref] = place(ref, (dx, top - TIP), lens=(0, 1))
RES = {"D3": "R3", "D4": "R4", "D5": "R5", "D6": "R6"}
rres = {}
for dref, rref in RES.items():
    a, k = pp(red[dref], "2"), pp(red[dref], "1")
    ux, uy = (a[0] - k[0]) / 2.0, (a[1] - k[1]) / 2.0          # unit vector from cathode to anode
    c = (round(a[0] + ux * 2.725, 3), round(a[1] + uy * 2.725, 3))
    rres[dref] = place(rref, c, ("2", (round(c[0] - ux * 0.825, 3), round(c[1] - uy * 0.825, 3))))

_pad_ok = grown(outer, -0.25)
_pad_ok.BooleanSubtract(grown(mouth, 0.25))
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


u = {n: pp(xiao, n) for n in ("2", "4", "5", "6", "7", "11", "12")}
j = {n: pp(conn, n) for n in "123456"}
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
J_TOP, J_BOT = JY - 5.6, JY + 5.6            # outer ends of the connector's two pad rows
SLOT = (j["1"][0] + j["3"][0]) / 2           # middle of the slot between the connector's first and second pad columns

# --- left of the XIAO: the three lines to the SAO connector. They leave the XIAO in the order GPIO2, SCL, SDA from
# the top; SCL and GPIO2 pass over the top of the connector and come down the slot between its pad columns.
G2_Y, SCL_Y = PT + 0.7, PT + 1.7
route("D6_TX", [u["7"], (PL - 0.55, u["7"][1]), (PL - 0.55, G2_Y), pp(r2, "2")])
G2_X, SCL_X = SLOT - 0.28, SLOT + 0.27
G2_LOW = J_BOT + 0.6
route("SAO_GPIO2", [pp(r2, "1"), (G2_X, G2_Y), (G2_X, G2_LOW), (j["6"][0], G2_LOW), (j["6"][0], J_BOT - 0.6)])
GAP_SCL, GAP_SDA = JY + 0.4, JY - 0.3        # two lanes in the gap between the connector's pad rows
route("SCL", [u["6"], (PL - 1.15, u["6"][1]), (PL - 1.15, SCL_Y), (SCL_X, SCL_Y), (SCL_X, GAP_SCL), (j["4"][0], GAP_SCL), (j["4"][0], J_BOT - 4.2)])
SDA_X = j["5"][0] + 1.85                     # down the right-hand side of the connector's pads
route("SDA", [u["5"], (SDA_X, u["5"][1]), (SDA_X, GAP_SDA), (j["3"][0], GAP_SDA), (j["3"][0], J_TOP + 4.2)])

# --- the duck LEDs. D1 (left) is first on the data line; its output goes over the top of the hole to D2.
CH_Y = -(HOLE_R + (HOLE_WALL / 2))
route("LED_D1", [pp(led1, "2"), (pp(led1, "2")[0], CH_Y), (pp(led2, "3")[0], CH_Y), pp(led2, "3")])
LD_Y, LV1_Y, LV2_Y = 4.3, 4.9, 2.9           # lanes under the XIAO's top (antenna) end
LD_HI = PT - 0.6                             # LED data where it passes over the XIAO's top right pad
RX1 = -(LEDX + 1.1)                          # D1's 3.3 V comes out on the far side of the LED and goes down
RX2 = LEDX + 1.15
V1, V2 = pp(led1, "4"), pp(led2, "4")
LV1_X = PRI - 0.6
route("V3V3", [V1, (RX1, V1[1]), (RX1, LV1_Y), (LV1_X, LV1_Y), (LV1_X, u["12"][1]), u["12"]], 0.25)
route("V3V3", [V2, (RX2, V2[1]), (RX2, LV2_Y), (VX, LV2_Y), (VX, u["12"][1]), u["12"]], 0.25)
route("V3V3", [(VX, C1_C[1]), pp(c1, "1")], 0.25)
D1I = pp(led1, "3")
route("LED_DIN", [D1I, (D1I[0], LD_Y), (LV1_X - 0.8, LD_Y), (LV1_X - 0.2, LD_HI), (R1_C[0], LD_HI), pp(r1, "2")])
route("LED_DATA", [pp(r1, "1"), (R1_C[0], u["11"][1]), u["11"]])

# --- 3.3 V rail to the switch's common (pin 3), above the LiPo connector's pads
V_SW = LY - 2.85 - 1.75 - 1.35
route("V3V3", [(VX, V_SW), (s3[0] - 3.3, V_SW), (s3[0] - 3.3, s3[1]), s3], PWR)

# --- LiPo +: the two battery pads under the module -> between the module's test pads -> out between the 3V3 and
# GND pads -> up and over the LiPo connector's ground pad -> its + pad
bp_a = pp(xiao, "15", pick=lambda p: p[1])        # upper one (C6)
bp_b = pp(xiao, "15", pick=lambda p: -p[1])       # lower one (C3 / S3)
lp = pp(jst, "1")
BAT_X = bp_b[0] + 1.25 + 0.48                     # between the lower battery pads and the module's own test pads
BAT_LANE = gap(3) + 1.01                          # between two rows of test pads
BAT_OUT_X = PRI - 1.3
BAT_UP = lp[0] - 3.7
BAT_Y = LY - 2.85 - 1.75 - 0.48
route("BAT+", [bp_a, (bp_a[0], bp_a[1] + 2.2), (BAT_X, bp_a[1] + 2.2), (BAT_X, BAT_LANE)], 0.25)
route("BAT+", [bp_b, (BAT_X, bp_b[1])], 0.25)
route("BAT+", [(BAT_X, BAT_LANE), (BAT_OUT_X, BAT_LANE), (BAT_OUT_X, gap(4)), (PR + 0.5, gap(4))], SIG, 0.16)
route("BAT+", [(PR + 0.5, gap(4)), (BAT_UP, gap(4)), (BAT_UP, BAT_Y), (lp[0], BAT_Y), lp], 0.25)

# --- OFF sense: XIAO D1 -> under the module between two rows of test pads -> out between the GND and 5V pads ->
# under the LiPo connector's body -> up beside the switch -> a 4.3 mm hop on the front over the 3.3 V rail -> pin 2
OFF_LANE = u["2"][1] - 0.26
OFF_Y = LY + 0.25
OFF_X = s2[0] - 2.27
HOP_A, HOP_B = (OFF_X, s3[1] + 2.8), (OFF_X, s3[1] - 1.5)
route("OFF_SENSE", [u["2"], (u["2"][0], OFF_LANE), (BAT_OUT_X, OFF_LANE), (BAT_OUT_X, gap(5)), (PR + 1.35, gap(5)),
                    (PR + 1.35, OFF_Y), (OFF_X, OFF_Y), HOP_A], SIG, 0.16)
route("OFF_SENSE", [HOP_A, HOP_B], SIG, 0.2, F_Cu)
route("OFF_SENSE", [HOP_B, (OFF_X, s2[1]), s2])
via(HOP_A, "OFF_SENSE")
via(HOP_B, "OFF_SENSE")

# --- the two lines that go round the head: the badge's 3.3 V (outer) from the SAO connector to the switch's top pin,
# and the red LEDs' drive line (inner) from XIAO D3. Both follow the outer edge.
V_OFF, B_OFF = 1.5, 2.3                      # distance from the outer edge
F_V, F_B = -36.0, -35.2                      # where they cross the forehead
SIDE = (-1.0, -4.0, -10.0, -16.0, -22.0, -28.0, -32.5)
VS_Y, BG_Y = J_TOP - 0.6, PT - 0.4
vs = [(j["1"][0], J_TOP + 0.6), (j["1"][0], VS_Y), (edge_x(VS_Y) + V_OFF, VS_Y)]
vs += [(edge_x(d) + V_OFF, d) for d in SIDE]
vs += [(CX - 22.6, F_V), (CX + 22.6, F_V)]
vs += [(edge_x(d, False) - V_OFF, d) for d in reversed(SIDE) if d <= -10]
vs += [(s1[0] - 1.4, -5.0), (s1[0] - 1.4, s1[1]), s1]
route("VSAO", vs, PWR)

BG_X = PLI + 0.41                            # up the inside of the XIAO's left pads
bg = [u["4"], (BG_X, u["4"][1]), (BG_X, BG_Y), (edge_x(BG_Y) + B_OFF, BG_Y)]
left = [(edge_x(d) + B_OFF, d) for d in SIDE]
right = [(edge_x(d, False) - B_OFF, d) for d in reversed(SIDE)]


def on_path(pts, y):
    """Point on a polyline (monotonic in y) at height y."""
    for a, b in zip(pts, pts[1:]):
        if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
            return (round(a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), 3), y)
    raise ValueError(y)


f3, f4, f5, f6 = (pp(rres[d], "1") for d in ("D3", "D4", "D5", "D6"))
t3, t6 = on_path(left, f3[1]), on_path(right, f6[1])
left = sorted(left + [t3], key=lambda p: -p[1])
right = sorted([p for p in right if p[1] < t6[1]] + [t6], key=lambda p: p[1])
bg += left + [(CX - 22.27, F_B), (f4[0], F_B), (f5[0], F_B), (CX + 22.27, F_B)] + right
route("BG_DRIVE", bg, 0.25)
route("BG_DRIVE", [f3, t3], 0.25)
route("BG_DRIVE", [f6, t6], 0.25)
route("BG_DRIVE", [f4, (f4[0], F_B)], 0.25)
route("BG_DRIVE", [f5, (f5[0], F_B)], 0.25)
for n_, d in enumerate(("D3", "D4", "D5", "D6")):
    route(f"BG_A{n_ + 1}", [pp(red[d], "2"), pp(rres[d], "2")], 0.25)

# every track must lie on the board, 0.3 mm or more from any edge
_ok = grown(outer, -0.3)
_ok.BooleanSubtract(grown(mouth, 0.3))
_ok.BooleanSubtract(disc(*H, HOLE_R + 0.3))
for t, clear, net in TRACKS:
    q = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(q, t.GetLayer(), 0, ERR, pcbnew.ERROR_OUTSIDE)
    q.BooleanSubtract(_ok)
    assert area_mm2(q) < 1e-4, f"{net} track {tuple(round(v - H[i], 2) for i, v in enumerate(mm(t.GetStart())))} -> {tuple(round(v - H[i], 2) for i, v in enumerate(mm(t.GetEnd())))} is too close to an edge"


# ---- the backs of the teeth: bare board, as on the maker's --------------------------------------------
# The maker left the back of both rows of teeth without solder mask or copper. Here that is kept for the parts of
# the teeth that stick out into the mouth (found by closing the mouth's outline over the tooth notches), and only
# where no pad or track is near.
_closed = grown(grown(mouth, 3.0), -3.0)
tips = pcbnew.SHAPE_POLY_SET(_closed)
tips.BooleanSubtract(mouth)
tips.BooleanIntersection(union(BACKMASK))
tips.BooleanIntersection(solid)
_near = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu):
            _near.Append(pad_poly(pad, B_Cu, 0.6))
for t, clear, net in TRACKS:
    if t.GetLayer() == B_Cu:
        t.TransformShapeToPolygon(_near, B_Cu, FromMM(0.6), ERR, pcbnew.ERROR_OUTSIDE)
_near.Simplify()
tips.BooleanSubtract(_near)
tips.Simplify()
BARE = [pcbnew.SHAPE_POLY_SET(tips.Polygon(i)) for i in range(tips.OutlineCount())]
BARE = [q for q in BARE if area_mm2(q) > 1.0]
print(f"bare tooth backs: {len(BARE)} pieces, {sum(area_mm2(q) for q in BARE):.0f} mm2")
bare = union(BARE)
for q in BARE:
    add_filled(board, q, pcbnew.B_Mask)

# ---- ground copper on the back: everywhere, cut round everything that is not ground ---------------------
gnd_code = nets["GND"].GetNetCode()
cut_b, cut_f = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
pads_b = pcbnew.SHAPE_POLY_SET()             # every pad on the back, with a margin: no via goes there
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            for c_ in (cut_b, cut_f):
                add_circle(c_, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            add_circle(pads_b, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.6)
        elif pad.IsOnLayer(B_Cu):
            pads_b.Append(pad_poly(pad, B_Cu, 0.35))
            if pad.GetNetCode() != gnd_code:
                pad.TransformShapeToPolygon(cut_b, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
pads_b.Simplify()
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
cut_b.BooleanAdd(grown(bare, 0.25))
cut_b.Simplify()
cut_f.Simplify()

# front: one ground plate, as on the maker's board (his was a ground fill too). The teeth are openings in the solder
# mask over it, so they show as bare gold-plated copper; the plate stops MOUTH_EDGE short of the mouth's edge, which
# leaves a thin rim of bare board round each tooth where the maker's copper ran to the edge.
plate = pcbnew.SHAPE_POLY_SET(inner)
plate.BooleanSubtract(cut_f)
plate.Simplify()
_pp = sorted([pcbnew.SHAPE_POLY_SET(plate.Polygon(i)) for i in range(plate.OutlineCount())], key=lambda q: -area_mm2(q))
assert len(_pp) >= 1 and all(area_mm2(q) < 1 for q in _pp[1:]), "the front ground plate is split"
plate = _pp[0]
add_filled(board, plate, F_Cu, nets["GND"])
plate_ok = grown(plate, -0.45)
for q in TEETH:
    q = pcbnew.SHAPE_POLY_SET(q)
    q.BooleanIntersection(solid)
    add_filled(board, q, pcbnew.F_Mask)
_cut_teeth = pcbnew.SHAPE_POLY_SET(cut_f)
_cut_teeth.BooleanIntersection(teeth)
assert area_mm2(_cut_teeth) < 1e-4, "a front track or a via shows in a tooth"

gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(cut_b)
gnd.Simplify()
# take out slivers narrower than 2 x THIN: shrink the copper by THIN, grow it back, keep what was copper before.
# (The shrinking is done by growing the cuts, because shrinking a shape that has holes slits it.)
THIN = 0.13
_thin = grown(outer, -(EDGE + THIN))
_thin.BooleanSubtract(grown(mouth, MOUTH_EDGE + THIN))
_thin.BooleanSubtract(disc(*H, HOLE_R + MOUTH_EDGE + THIN))
_thin.BooleanSubtract(grown(cut_b, THIN))
_thin.Simplify()
_thin = grown(_thin, THIN)
_a0 = area_mm2(gnd)
gnd.BooleanIntersection(_thin)
gnd.Simplify()
print(f"back ground copper: {_a0:.1f} mm2, {area_mm2(gnd):.1f} mm2 after taking out slivers")
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
gnd_seed.Simplify()
silk_all = union(SILK)
never = pcbnew.SHAPE_POLY_SET(pads_b)        # a via never goes on a pad, in a tooth (bare copper on the front) or on the hop
never.BooleanAdd(grown(teeth, 0.4))
never.Simplify()
avoid_silk = grown(silk_all, 0.3)            # ... and keeps off the white lips where it can
avoid_parts = pcbnew.SHAPE_POLY_SET()        # ... and out from under parts where it can
for fp in board.GetFootprints():
    if fp is xiao or fp.GetReference() == "U1":
        continue                             # under the module is fine: nothing shows, and its own test pads are already cut out
    b_ = fp.GetBoundingBox(False)
    avoid_parts.BooleanAdd(rect(ToMM(b_.GetLeft()) - 0.3, ToMM(b_.GetTop()) - 0.3, ToMM(b_.GetRight()) + 0.3, ToMM(b_.GetBottom()) + 0.3))
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
    # One via per piece, as near as it can be to a ground pad of that piece. The main piece gets one near each of
    # the XIAO's GND pin, the SAO connector's GND pin, the capacitor, a duck LED and three of the red LEDs.
    def _at(fp_, num):
        return [mm(pad.GetPosition()) for pad in fp_.Pads() if pad.GetNumber() == num and pad.GetNetCode() == gnd_code
                and piece.Contains(pad.GetPosition())]
    seeds = [mm(pad.GetPosition()) for fp in board.GetFootprints() for pad in fp.Pads()
             if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu) and piece.Contains(pad.GetPosition())]
    wants = sum([_at(xiao, "13"), _at(conn, "2"), _at(c1, "2"), _at(led1, "1"), _at(red["D3"], "1"), _at(red["D4"], "1"),
                 _at(red["D6"], "1")], []) if area_mm2(piece) > 400 else []
    wants = wants or seeds[:1] or [((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)]
    got = []
    for want in wants:
        spot = None
        for level in (0, 1, 2):
            best = None
            for yy in range(int(bb[1] * 4), int(bb[3] * 4) + 1):
                for xx in range(int(bb[0] * 4), int(bb[2] * 4) + 1):
                    q = P(xx / 4, yy / 4)
                    d_ = math.hypot(xx / 4 - want[0], yy / 4 - want[1])
                    if (best is None or d_ < best[0]) and inside.Contains(q) and plate_ok.Contains(q) and not never.Contains(q) \
                            and not (level < 2 and avoid_silk.Contains(q)) and not (level < 1 and avoid_parts.Contains(q)):
                        best = (d_, (xx / 4, yy / 4))
            if best:
                spot = best[1]
                break
        assert spot, f"no room for a stitching via in the ground piece at {[round(v_ - H[k % 2], 1) for k, v_ in enumerate(bb)]} ({area_mm2(piece):.1f} mm2)"
        if all(math.hypot(spot[0] - g_[0], spot[1] - g_[1]) > 3 for g_ in got):
            got.append(spot)
            STITCH.append((spot, round(area_mm2(piece), 1), level, len(seeds)))
for (x, y), a, level, n_s in STITCH:
    via((x - H[0], y - H[1]), "GND")
    print(f"  ground piece of {a} mm2 on the back ({n_s} ground pads), tied to the front plate by a via at hole{(round(x - H[0], 2), round(y - H[1], 2))}"
          + ("" if level == 0 else " (under a part)" if level == 1 else " (under the white lip print)"))
print("back ground pieces", len(STITCH), "scraps dropped", n_drop)

# ---- front silkscreen: the maker's lips, eyes and nostrils, scaled ------------------------------------------
art = pcbnew.SHAPE_POLY_SET(silk_all)
_a0 = area_mm2(art)
art.BooleanSubtract(grown(teeth, 0.15))
art.BooleanIntersection(grown(outer, -0.15))
art.BooleanSubtract(grown(mouth, 0.15))
art.BooleanSubtract(disc(*H, HOLE_R + 0.2))
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        _peg = pcbnew.SHAPE_POLY_SET()
        add_circle(_peg, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.2)
        art.BooleanSubtract(_peg)
art.Simplify()
add_filled(board, art, pcbnew.F_SilkS)
print(f"front print: {_a0:.1f} mm2 as the maker drew it, {area_mm2(art):.1f} mm2 after keeping it off the teeth, the edges and the holes")

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

if os.environ.get("SAOPP_DEBUG"):            # a picture of the back for whoever is editing the routes: dumps the geometry as JSON
    dbg_extra = {"gnd": [[mm(gnd.Outline(k).CPoint(i)) for i in range(gnd.Outline(k).PointCount())] for k in range(gnd.OutlineCount())],
                 "bare": [[mm(q.Outline(0).CPoint(i)) for i in range(q.Outline(0).PointCount())] for q in BARE]}
    dbg = {"outer": [mm(outer.Outline(0).CPoint(i)) for i in range(outer.Outline(0).PointCount())],
           "mouth": [mm(mouth.Outline(0).CPoint(i)) for i in range(mouth.Outline(0).PointCount())],
           "teeth": [[mm(teeth.Outline(k).CPoint(i)) for i in range(teeth.Outline(k).PointCount())] for k in range(teeth.OutlineCount())],
           "H": H, "pads": [], "crt": [], "keep": [], "tracks": [], "vias": [(x, y) for x, y, n in VIAS], **dbg_extra}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            q = pad_poly(pad, B_Cu) if pad.IsOnLayer(B_Cu) else None
            if q and q.OutlineCount():
                dbg["pads"].append((fp.GetReference(), pad.GetNumber(), pad.GetNetname(), [mm(q.Outline(0).CPoint(i)) for i in range(q.Outline(0).PointCount())]))
        b_ = fp.GetBoundingBox(False)
        dbg["crt"].append((fp.GetReference(), ToMM(b_.GetLeft()), ToMM(b_.GetTop()), ToMM(b_.GetRight()), ToMM(b_.GetBottom())))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
                dbg["keep"].append((mm(g.GetCenter()), ToMM(g.GetRadius())))
    for t, clear, net in TRACKS:
        dbg["tracks"].append((mm(t.GetStart()), mm(t.GetEnd()), ToMM(t.GetWidth()), "F" if t.GetLayer() == F_Cu else "B", net))
    os.makedirs(os.path.join(HERE, ".tmp"), exist_ok=True)
    json.dump(dbg, open(os.path.join(HERE, ".tmp", "dbg.json"), "w"))
