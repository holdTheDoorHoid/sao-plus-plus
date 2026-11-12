#!/usr/bin/env python3
"""Build mysterio.kicad_pcb (rev B) from the maker's KiCad 8 board plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mysterio/hardware/build_board.py

The maker's board is a 4-layer board: the helmet's skull-and-swirl art is copper on inner layer 2, lit from behind by
four side-firing RGB LEDs round the bottom of the helmet. SAO++ boards are 2-layer, so this script:
  - scales the maker's whole design (outline, every art layer, the credit, the LED positions) by SCALE about the
    middle of his outline. Parts keep their real size; only the LEDs, which are part of the picture, move with the art
  - copies the front art (copper, mask, silkscreen) and the back credit, scaled, exactly as drawn
  - moves the inner-layer helmet art to the back copper and opens the back mask only where the maker's mask was open
    AND there is no copper, so light gets into the board in the same places as on the original
  - uses the helmet's solid outer ring of art copper as the LEDs' 3.3 V conductor (it is copper anyway)
  - replaces the CH32V003, its two I2C pull-ups and the through-hole header with the XIAO, the SMD SAO connector,
    the power switch and the JST-PH LiPo connector, below and beside the helmet and on a base strip under the figure
  - keeps the six round pads of the old header on the front as plain copper "buttons" on the chest plate
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
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

SLUG = "mysterio"
SRC = os.path.join(HERE, "..", "original", "mysterio", "mysterio.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

# ---- the one scale factor (README "Why the board is bigger") ----------------------------------------
SCALE = 1.30        # the maker's outline and all art, about the middle of his outline. 1.25 left no room for R2/R3

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper and the art
EDGE = 0.55         # GND copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20
PWR = 0.30
VIA_D, VIA_W = 0.3, 0.6

# ---- the maker's art, scaled -----------------------------------------------------------------------
orig = pcbnew.LoadBoard(SRC)
_bb = orig.GetBoardEdgesBoundingBox()
C0 = (round(ToMM(_bb.GetCenter().x), 3), round(ToMM(_bb.GetCenter().y), 3))      # (24.6, 31.43)


def sc(x, y):
    return (C0[0] + SCALE * (x - C0[0]), C0[1] + SCALE * (y - C0[1]))


def scaled(ps):
    out = pcbnew.SHAPE_POLY_SET(ps)
    out.Scale(SCALE, SCALE, P(*C0))
    return out


ART = {}
for d in orig.GetDrawings():
    if d.GetClass() == "PCB_SHAPE" and d.GetShape() == pcbnew.SHAPE_T_POLY:
        ART.setdefault(d.GetLayer(), []).append(scaled(pcbnew.SHAPE_POLY_SET(d.GetPolyShape())))
assert len(ART[F_Cu]) == 12 and len(ART[pcbnew.In2_Cu]) == 23 and len(ART[pcbnew.B_Mask]) == 211, {k: len(v) for k, v in ART.items()}
CREDIT = [d for d in orig.GetDrawings() if d.GetClass() == "PCB_TEXT" and "davedarko" in d.GetText()]
assert len(CREDIT) == 1

HELMET = sc(24.94, 25.64)        # centre of the helmet circle (from the maker's inner-layer ring)
R_RING = 10.98 * SCALE           # outer edge of the helmet's art ring
R_LED = 11.7 * SCALE             # the maker put D2 and D3 at this radius; D1 and D4 are moved out to it (see below)


def union(parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in parts:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


def disc(cx, cy, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(cx, cy), r)
    return ps


# chest buttons: the front copper and front mask openings of the six old header pads, without their holes
_j1 = [fp for fp in orig.GetFootprints() if fp.GetReference() == "J1"][0]
btn_cu, btn_mask = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
for pad in _j1.Pads():
    pad.TransformShapeToPolygon(btn_cu, F_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    pad.TransformShapeToPolygon(btn_mask, pcbnew.F_Mask, 0, ERR, pcbnew.ERROR_OUTSIDE)
btn_cu.Simplify()
btn_mask.Simplify()
btn_cu, btn_mask = scaled(btn_cu), scaled(btn_mask)
LED_ORIG = {fp.GetReference(): fp for fp in orig.GetFootprints() if fp.GetReference().startswith("D")}

# ---- outline: the maker's outline, scaled, plus a base strip below it ---------------------------------
maker0 = pcbnew.SHAPE_POLY_SET()
assert orig.GetBoardPolygonOutlines(maker0, False)
maker0.Simplify()
assert maker0.OutlineCount() == 1
maker = scaled(maker0)

XL, XR = sc(5.21, 47.25)[0], sc(44.0, 47.25)[0]       # bottom outer corners of the two arms (unchanged above them)
Y_ARM = sc(0, 47.25)[1]
# ---- placement constants ---------------------------------------------------------------------------
XC, YC = 36.6, 51.6            # XIAO centre: USB end flush with the bottom edge, right pads clear of the arm's edge
B_EDGE = YC + 10.53            # bottom edge
JX, JY = 16.8, 45.9            # SAO connector: body clear of the maker's credit (left) and of LED D3 (above)
SX, SY = 6.3, B_EDGE - 2.1     # switch, knob out of the bottom edge
LX, LY = 17.2, B_EDGE - 4.9    # LiPo connector, plug in from the bottom edge


def rounded(pts, r, corners):
    """Polygon through pts, with the listed corner indices rounded to radius r (right-angle corners only)."""
    out = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i not in corners:
            out.append((x, y))
            continue
        (px, py), (nx, ny) = pts[i - 1], pts[(i + 1) % n]
        a = math.atan2(py - y, px - x)
        b = math.atan2(ny - y, nx - x)
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = math.cos(b), math.sin(b)
        cx, cy = x + (ux + vx) * r, y + (uy + vy) * r
        a0 = math.atan2(y + uy * r - cy, x + ux * r - cx)
        a1 = math.atan2(y + vy * r - cy, x + vx * r - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(9):
            t = a0 + da * k / 8
            out.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return out


# The strip starts at the arms' bottom corners and fills the two notches between arms and torso; its sides run
# straight down from those corners, so nothing above them changes.
_nl, _nr = sc(13.0, 42.3), sc(36.0, 42.3)
STRIP = rounded([sc(5.21, 47.254), _nl, _nr, sc(44.0, 47.254), (XR, B_EDGE), (XL, B_EDGE)], 1.0, (4, 5))
body = union([maker, poly(STRIP)])
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f} "
      f"(maker's: 38.80 x 34.14; scale {SCALE})")
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
    board.Add(fp)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    return fp


def place(ref, pos, want):
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` nearest `want[1]`."""
    fp = load(ref, pos)
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


# ---- LEDs: same part, same direction as the maker's, at the scaled positions --------------------------
def lens_dir(fp, layer):
    """Unit vector from the footprint origin toward the lens arc the footprint draws on `layer`."""
    arcs = [g for g in fp.GraphicalItems() if g.GetLayer() == layer and g.GetShape() == pcbnew.SHAPE_T_ARC]
    assert len(arcs) == 1, (fp.GetReference(), len(arcs))
    m = arcs[0].GetArcMid()
    o = fp.GetPosition()
    dx, dy = ToMM(m.x - o.x), ToMM(m.y - o.y)
    h = math.hypot(dx, dy)
    return dx / h, dy / h


led = {}
LED_SHIFT = {}
for ref in ("D1", "D2", "D3", "D4"):
    mf = LED_ORIG[ref]
    ox, oy = sc(*mm(mf.GetPosition()))        # the maker's footprint origin (middle of the pads' back edge), scaled
    ux, uy = lens_dir(mf, pcbnew.Dwgs_User)
    # D1 and D4 sat 0.74 mm (scaled: 0.96) further in than D2 and D3, with their pads over the helmet ring. On one
    # copper layer the ring carries 3.3 V and would be cut through at their pads, so they move out to D2/D3's radius.
    rx, ry = ox - HELMET[0], oy - HELMET[1]
    r0 = math.hypot(rx, ry)
    nx, ny = ox + rx / r0 * (R_LED - r0), oy + ry / r0 * (R_LED - r0)
    LED_SHIFT[ref] = round(math.hypot(nx - ox, ny - oy), 2)
    fp = load(ref, (nx, ny))
    want = math.degrees(math.atan2(uy, ux))
    fp.SetOrientationDegrees(0)
    vx, vy = lens_dir(fp, pcbnew.B_Fab)
    have = math.degrees(math.atan2(vy, vx))
    for sgn in (1, -1):
        fp.SetOrientationDegrees((sgn * (want - have)) % 360)
        vx, vy = lens_dir(fp, pcbnew.B_Fab)
        if vx * ux + vy * uy > 0.9999:
            break
    else:
        raise AssertionError(f"{ref}: could not match the lens direction")
    p1 = pp(fp, "1")
    p4 = pp(fp, "4")
    mid = ((p1[0] + p4[0]) / 2, (p1[1] + p4[1]) / 2)          # GND/VDD pad centres sit 0.25 in from the back edge
    back = (mid[0] - ux * 0.25, mid[1] - uy * 0.25)
    _fx, _fy = mm(fp.GetPosition())
    fp.SetPosition(P(_fx + nx - back[0], _fy + ny - back[1]))
    link(fp, ref)
    led[ref] = fp
    print(f"{ref}: at ({nx:.2f},{ny:.2f}), moved out {LED_SHIFT[ref]} mm from the scaled spot, lens {want:.1f} deg")

# ---- other parts ----------------------------------------------------------------------------------
xiao = place("U1", (XC, YC), ("14", (XC + 8.11, YC + 7.56)))      # USB end down, flush with the bottom edge
assert abs(pp(xiao, "1")[0] - (XC - 8.05)) < 0.01, "pads 1-7 (D0-D6) should face the connector"
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))          # VCC top-left in front view, key slot up
sw = place("SW1", (SX, SY), ("1", (SX + 3.0, SY - 1.43)))           # knob out of the bottom edge
jst = place("J2", (LX, LY), ("1", (LX + 1.0, LY - 2.85)))           # plug in from the bottom edge, + on the right (front view)

RCOL = 25.9                                    # R2 / R3 stand upright between the connector and the XIAO
R2_C, R3_C = (RCOL, 42.0), (RCOL, 46.4)
R4_C = (SX + 2.25, SY - 3.2)
r2 = place("R2", R2_C, ("1", (RCOL, R2_C[1] + 0.825)))      # GPIO1 in from below-left, D7 out of the top
r3 = place("R3", R3_C, ("1", (RCOL, R3_C[1] + 0.825)))      # GPIO2 in from below, D6 out of the top; SCL passes between its pads
r4 = place("R4", R4_C, ("1", (R4_C[0] - 0.825, R4_C[1])))   # OFF in on the left, out on the right; badge 3.3 V passes between its pads

# R1 stands on LED D1's own axis, just outside it, so the 3.3 V feed can cross the data line between R1's pads on its
# way to D1's supply pad (the two lines leave the XIAO in the opposite order to the one D1's pads need).
D1V, D1I = pp(led["D1"], "4"), pp(led["D1"], "3")
_l = lens_dir(led["D1"], pcbnew.B_Fab)
NO = (-_l[0], -_l[1])                                   # outward from the helmet
TD = ((D1I[0] - D1V[0]) / math.hypot(D1I[0] - D1V[0], D1I[1] - D1V[1]), (D1I[1] - D1V[1]) / math.hypot(D1I[0] - D1V[0], D1I[1] - D1V[1]))


def d1(t_, n_, base=D1I):
    return (round(base[0] + TD[0] * t_ + NO[0] * n_, 3), round(base[1] + TD[1] * t_ + NO[1] * n_, 3))


R1_C = d1(0, 3.0)
r1 = load("R1", R1_C)
for rot in range(0, 360, 45):
    r1.SetOrientationDegrees(rot)
    if math.hypot(pp(r1, "2")[0] - d1(0, 3.0 - 0.825)[0], pp(r1, "2")[1] - d1(0, 3.0 - 0.825)[1]) < 0.05:
        break
else:
    raise AssertionError("R1: no rotation puts pad 2 toward D1")
link(r1, "R1")
# C1 sits on the 3.3 V line where it leaves the XIAO's 3V3 pin, its ground pad in the ground copper below
C1_C = (XC + 8.11 + 1.375 + 1.95, YC + 2.48 + 0.775)     # clear of the XIAO's courtyard
c1 = place("C1", C1_C, ("1", (C1_C[0], C1_C[1] - 0.775)))

_pad_ok = grown(body, -0.25)
_crt_bad = disc(*HELMET, R_RING + 0.3)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"
    if fp.GetReference().startswith("D"):
        continue
    crt = pcbnew.SHAPE_POLY_SET()
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.B_CrtYd:
            g.TransformShapeToPolygon(crt, pcbnew.B_CrtYd, 0, ERR, pcbnew.ERROR_OUTSIDE)
    crt.BooleanIntersection(_crt_bad)
    assert area_mm2(crt) < 0.01, f"{fp.GetReference()} sits over the helmet (the LEDs' light path)"

# ---- routing ----------------------------------------------------------------------------------------
TRACKS = []
VIAS = []          # (x, y, net)


def route(net, pts, width=SIG, clear=CLEAR, layer=B_Cu):
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


def via(x, y, net):
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


s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
j = {n: pp(conn, n) for n in "123456"}
u = {n: pp(xiao, n) for n in ("2", "5", "6", "7", "8", "11", "12")}
GAP = JY                                   # between the connector's two pad rows
PAD_L = XC - 8.05 - 1.375                  # outer ends of the XIAO's left pads (D0..D6)
PAD_R = XC + 8.11 + 1.375                  # outer ends of its right pads (D7..D10, 3V3, GND, 5V)
CONN_BOT = JY + 5.6                        # bottom ends of the connector's lower pads
SDA_Y = (CONN_BOT + pp(jst, "1")[1] - 1.75) / 2      # lane between the connector's pads and the LiPo connector's pads
JST_LANE = (pp(jst, "1")[1] + 1.75 + LY + 2.9 - 1.7) / 2   # between the LiPo connector's signal pads and its hold-downs

# badge 3.3 V: switch pin 1 -> between R4's pads -> up the left of the connector -> connector pin 1 from the left
VSX = JX - 5.2
route("VSAO", [s1, (R4_C[0], s1[1] - 1.0), (R4_C[0], R4_C[1] - 1.4), (VSX, R4_C[1] - 1.4 - (VSX - R4_C[0])),
               (VSX, j["1"][1]), j["1"]], PWR)
# OFF: switch pin 2 -> R4 -> under the LiPo connector (between its signal pads and hold-downs) -> XIAO D1 from the left
route("OFF_SW", [s2, (pp(r4, "1")[0], s2[1] - 0.6), pp(r4, "1")])
route("OFF_SENSE", [pp(r4, "2"), (pp(r4, "2")[0] + 0.5, JST_LANE), (PAD_L - 1.0, JST_LANE), u["2"]])
# switched 3.3 V: switch pin 3 -> up the left arm (under the credit's lettering) -> LED D4's VDD pad from outside
OUTW = {k: ((mm(f.GetPosition())[0] - HELMET[0]), (mm(f.GetPosition())[1] - HELMET[1])) for k, f in led.items()}
OUTW = {k: (x / math.hypot(x, y), y / math.hypot(x, y)) for k, (x, y) in OUTW.items()}


def outside(ref, num, d):
    x, y = pp(led[ref], num)
    ox, oy = OUTW[ref]
    return (round(x + ox * d, 3), round(y + oy * d, 3))


V3L = SX
d4o = outside("D4", "4", 0.9)
route("V3V3", [s3, (s3[0], s3[1] - 1.6), (V3L, s3[1] - 1.6 - (s3[0] - V3L) if s3[0] > V3L else s3[1] - 1.6),
               (V3L, d4o[1] + (d4o[0] - V3L)), d4o, pp(led["D4"], "4")], PWR)

# SDA: connector pin 3 -> into the gap between the pad rows -> out on the left -> down -> along under the connector's
# lower pads -> up beside R2/R3 -> XIAO D4
SDA_X = PAD_L - 0.55
route("SDA", [j["3"], (j["3"][0], GAP - 0.5), (j["1"][0] - 1.2, GAP - 0.5), (j["1"][0] - 1.2, SDA_Y),
              (SDA_X, SDA_Y), (SDA_X, u["5"][1]), u["5"]])
# SCL: connector pin 4 -> into the gap -> out on the right -> between R3's pads -> XIAO D5
route("SCL", [j["4"], (j["4"][0], R3_C[1]), (u["6"][0], R3_C[1]), u["6"]])
# GPIO2: connector pin 6 -> R3 (from below) -> D6
route("SAO_GPIO2", [j["6"], (RCOL - 1.2, j["6"][1]), (RCOL, j["6"][1] - 1.2), pp(r3, "1")])
route("D6_TX", [pp(r3, "2"), (RCOL, u["7"][1]), u["7"]])
# GPIO1: connector pin 5 -> R2 (from below) -> under the XIAO's top end -> D7 from above
route("SAO_GPIO1", [j["5"], (RCOL - 1.4, j["5"][1]), (RCOL, j["5"][1] - 0.6 if j["5"][1] - 0.6 > pp(r2, "1")[1] else pp(r2, "1")[1]), pp(r2, "1")])
TOP = YC - 9.95
route("D7_RX", [pp(r2, "2"), (RCOL, TOP), (u["8"][0], TOP), u["8"]])

# right edge: LED data and the XIAO's 3V3 pin run up outside the right pads to R1 / C1 and LED D1
DX, VX = PAD_R + 0.30, PAD_R + 0.72
TURN = YC - 10.0
route("LED_DATA", [u["11"], (DX, u["11"][1]), (DX, TURN), d1(0, 5.0), pp(r1, "1")])
route("LED_DIN", [pp(r1, "2"), D1I])
route("V3V3", [(VX, u["12"][1]), pp(c1, "1")], 0.25)
route("V3V3", [u["12"], (VX, u["12"][1]), (VX, TURN - 0.4), d1(1.2, 4.0), d1(1.2, 3.0), d1(-0.98, 3.0, D1I),
               D1V], 0.25)

# LiPo +: connector pin 1 -> via -> a short front-copper track inside the plain base strip -> via under the XIAO ->
# the C3/S3 battery pad -> the C6 battery pad. It crosses the SDA, OFF and GPIO lanes on the front.
bp_a = pp(xiao, "15", pick=lambda p: -p[1])       # lower one (C3 / S3)
bp_b = pp(xiao, "15", pick=lambda p: p[1])        # upper one (C6)
lp = pp(jst, "1")
BAT_Y = lp[1] + 0.55
VB1 = (lp[0] + 2.0, BAT_Y)
VB2 = (bp_a[0] + 1.75, BAT_Y)
route("BAT+", [lp, (lp[0] + 0.6, BAT_Y), VB1], PWR)
route("BAT+", [VB1, VB2], PWR, CLEAR, F_Cu)
route("BAT+", [VB2, (VB2[0], bp_a[1]), bp_a], PWR)
route("BAT+", [(VB2[0], bp_a[1]), (VB2[0], bp_b[1]), bp_b], PWR)
via(*VB1, "BAT+")
via(*VB2, "BAT+")

# LED chain round the bottom of the helmet, outside the art ring
ARC = R_LED - 0.05


def rim(deg):
    return (round(HELMET[0] + ARC * math.cos(math.radians(deg)), 3), round(HELMET[1] + ARC * math.sin(math.radians(deg)), 3))


def ang(ref):
    x, y = mm(led[ref].GetPosition())
    return math.degrees(math.atan2(y - HELMET[1], x - HELMET[0]))


route("LED_D1", [pp(led["D1"], "2"), rim((ang("D1") + ang("D2")) / 2), pp(led["D2"], "3")], SIG, 0.2)
route("LED_D2", [pp(led["D2"], "2"), rim(ang("D2") + 0.33 * (ang("D3") - ang("D2"))), rim(ang("D2") + 0.67 * (ang("D3") - ang("D2"))),
                 pp(led["D3"], "3")], SIG, 0.2)
route("LED_D3", [pp(led["D3"], "2"), rim((ang("D3") + ang("D4")) / 2), pp(led["D4"], "3")], SIG, 0.2)
STUB = R_LED - R_RING + 0.2
for ref in led:
    x, y = pp(led[ref], "4")
    ox, oy = OUTW[ref]
    route("V3V3", [(x, y), (round(x - ox * STUB, 3), round(y - oy * STUB, 3))], 0.25, 0.2)

# ---- back copper: the helmet art -----------------------------------------------------------------
_ha = union(ART[pcbnew.In2_Cu])
helmet_art = sorted([pcbnew.SHAPE_POLY_SET(_ha.Polygon(i)) for i in range(_ha.OutlineCount())], key=lambda p_: -area_mm2(p_))
PANEL = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))
tab_keep = pcbnew.SHAPE_POLY_SET()
for t_ in PANEL["tabs"]:
    add_circle(tab_keep, P(*t_["near"]), 2.6)
tab_keep.BooleanIntersection(grown(body, 0.1))
tab_keep.BooleanSubtract(inner)
tab_keep.Simplify()
ring = pcbnew.SHAPE_POLY_SET(helmet_art[0])
others = union(helmet_art[1:])
clip = grown(body, -0.3)
ring.BooleanIntersection(clip)
others.BooleanIntersection(clip)
v3_code = nets["V3V3"].GetNetCode()
gnd_code = nets["GND"].GetNetCode()
cut_v3 = pcbnew.SHAPE_POLY_SET()
cut_gnd = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            for c_ in (cut_v3, cut_gnd):
                add_circle(c_, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            continue
        if not pad.IsOnLayer(B_Cu):
            continue
        if pad.GetNetCode() != v3_code:
            pad.TransformShapeToPolygon(cut_v3, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
        if pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut_gnd, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t, clear, net in TRACKS:
    if t.GetLayer() != B_Cu:
        continue
    if net != "V3V3":
        t.TransformShapeToPolygon(cut_v3, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
    if net != "GND":
        t.TransformShapeToPolygon(cut_gnd, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
for x, y, net in VIAS:
    for c_ in (cut_v3, cut_gnd):
        add_circle(c_, P(x, y), VIA_W / 2 + CLEAR)
for g in xiao.GraphicalItems():                                  # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut_gnd, g.GetCenter(), 0.85 + 0.15)
cut_v3.Simplify()
cut_gnd.Simplify()
ring.BooleanSubtract(cut_v3)
ring.BooleanSubtract(tab_keep)
ring.Simplify()
others.BooleanSubtract(cut_v3)
others.Simplify()

v3_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == v3_code and pad.IsOnLayer(B_Cu):
            v3_pads.Append(pad_poly(pad, B_Cu))
for t, clear, net in TRACKS:
    if net == "V3V3":
        t.TransformShapeToPolygon(v3_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
v3_pads.Simplify()
n_ring = 0
ring_v3 = pcbnew.SHAPE_POLY_SET()
for i in range(ring.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(ring.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(v3_pads)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["V3V3"])
        ring_v3.BooleanAdd(piece)
        n_ring += 1
    elif area_mm2(piece) > 0.02:
        others.BooleanAdd(piece)
others.BooleanSubtract(grown(ring_v3, CLEAR))
others.Simplify()
for i in range(others.OutlineCount()):
    add_filled(board, pcbnew.SHAPE_POLY_SET(others.Polygon(i)), B_Cu)
print("helmet art: 3.3 V pieces", n_ring, "plain art pieces", others.OutlineCount())

# ---- front copper: the maker's art, the chest buttons, and a plain base strip below the figure ----------
base = pcbnew.SHAPE_POLY_SET(grown(body, -EDGE))
base.BooleanSubtract(grown(maker, 0.1))
base.BooleanIntersection(poly([(-20, Y_ARM - 8), (80, Y_ARM - 8), (80, 90), (-20, 90)]))
torso = [p_ for p_ in ART[F_Cu] if bbox_mm(p_)[3] > sc(0, 48.0)[1]]
assert len(torso) == 1, "expected one front art piece reaching the old bottom edge (the torso)"
_tb = bbox_mm(torso[0])
bridge = poly([(sc(17.6, 0)[0], sc(0, 47.9)[1]), (sc(32.4, 0)[0], sc(0, 47.9)[1]), (sc(32.4, 0)[0], sc(0, 49.2)[1]),
               (sc(17.6, 0)[0], sc(0, 49.2)[1])])                        # the torso runs on into the base strip
bridge.BooleanIntersection(grown(body, -EDGE))
plate = union([torso[0], base, bridge])
fcu_other = union([p_ for p_ in ART[F_Cu] if p_ is not torso[0]] + [btn_cu])
fcut = pcbnew.SHAPE_POLY_SET()                     # holes in the front ground plate: switch pegs, LiPo vias and track
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
for t, clear, net in TRACKS:
    if t.GetLayer() == F_Cu:
        t.TransformShapeToPolygon(fcut, F_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
for x, y, net in VIAS:
    add_circle(fcut, P(x, y), VIA_W / 2 + CLEAR)
fcut.Simplify()
_front_trk = pcbnew.SHAPE_POLY_SET()
for t, clear, net in TRACKS:
    if t.GetLayer() == F_Cu:
        t.TransformShapeToPolygon(_front_trk, F_Cu, FromMM(0.4), ERR, pcbnew.ERROR_OUTSIDE)
_chk = pcbnew.SHAPE_POLY_SET(_front_trk)
_chk.BooleanIntersection(union(ART[F_Cu] + ART[pcbnew.F_SilkS] + ART[pcbnew.F_Mask] + [btn_cu]))
assert area_mm2(_chk) < 0.001, "the front LiPo track touches the maker's art"
plate.BooleanSubtract(fcut)
plate.BooleanIntersection(grown(body, -0.26))
plate.BooleanSubtract(tab_keep)
plate.Simplify()
fcu_other.BooleanSubtract(fcut)
fcu_other.BooleanIntersection(grown(body, -0.26))
fcu_other.BooleanSubtract(tab_keep)
fcu_other.Simplify()
plate_pieces = [pcbnew.SHAPE_POLY_SET(plate.Polygon(i)) for i in range(plate.OutlineCount())]
plate_pieces = [q for q in plate_pieces if area_mm2(q) > 1]
for q in plate_pieces:
    add_filled(board, q, F_Cu, nets["GND"])
print("front ground plate pieces", len(plate_pieces), [round(area_mm2(q), 1) for q in plate_pieces])
for i in range(fcu_other.OutlineCount()):
    add_filled(board, pcbnew.SHAPE_POLY_SET(fcu_other.Polygon(i)), F_Cu)
fmask = union(ART[pcbnew.F_Mask] + [btn_mask])
add_filled(board, fmask, pcbnew.F_Mask)
add_filled(board, union(ART[pcbnew.F_SilkS]), pcbnew.F_SilkS)

# ---- back ground everywhere else, except the helmet; each separate piece is stitched to the front plate ----
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(disc(*HELMET, 11.0 * SCALE + CLEAR))
gnd.BooleanSubtract(cut_gnd)
gnd.Simplify()
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
gnd_seed.Simplify()
base_ok = grown(base, -0.6)            # prefer stitching vias in the plain base strip, not in the maker's art
base_ok.BooleanSubtract(grown(fcut, 0.45))
_crt_all = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.B_CrtYd:                   # courtyards are outlines: take their extent
            _b = g.GetBoundingBox()
            _crt_all.BooleanAdd(poly([(ToMM(_b.GetLeft()), ToMM(_b.GetTop())), (ToMM(_b.GetRight()), ToMM(_b.GetTop())),
                                      (ToMM(_b.GetRight()), ToMM(_b.GetBottom())), (ToMM(_b.GetLeft()), ToMM(_b.GetBottom()))]))
_crt_all.Simplify()
base_ok.BooleanSubtract(grown(_crt_all, 0.1))      # and not under a part
plate_ok = grown(union(plate_pieces), -0.45)
_bb0 = bbox_mm(base_ok)
CAND_BASE = [(xx / 5, yy / 5) for yy in range(int(_bb0[3] * 5), int(_bb0[1] * 5) - 1, -1)
             for xx in range(int(_bb0[0] * 5), int(_bb0[2] * 5) + 1) if base_ok.Contains(P(xx / 5, yy / 5))]
n_drop = 0
STITCH = []
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_seed)
    if area_mm2(both) <= 0.005:
        n_drop += 1
        continue
    add_filled(board, piece, B_Cu, nets["GND"])
    inside = grown(piece, -0.45)
    spot = None
    bb = bbox_mm(piece)
    for x_, y_ in CAND_BASE:
        if bb[0] <= x_ <= bb[2] and bb[1] <= y_ <= bb[3] and inside.Contains(P(x_, y_)):
            spot = (x_, y_)
            break
    if spot is None:                   # no plain strip behind this piece: a via in the front art's ground (the torso)
        for yy in range(int(bb[3] * 5), int(bb[1] * 5), -1):
            for xx in range(int(bb[0] * 5), int(bb[2] * 5) + 1):
                q = P(xx / 5, yy / 5)
                if inside.Contains(q) and plate_ok.Contains(q):
                    spot = (xx / 5, yy / 5)
                    break
            if spot:
                break
    assert spot, f"no room for a stitching via in the ground piece at {[round(v_, 1) for v_ in bb]}"
    STITCH.append((spot, round(area_mm2(piece), 1)))
for (x, y), a in STITCH:
    via(x, y, "GND")
print("back ground pieces", len(STITCH), "scraps dropped", n_drop)
for (x, y), a in STITCH:
    print(f"  stitching via at ({x:.1f}, {y:.1f}) for a {a} mm2 ground piece")

# ---- back mask: open only where the maker's mask was open and there is no copper behind it now ------
bmask = union(ART[pcbnew.B_Mask])
bmask.BooleanSubtract(grown(union(helmet_art), 0.05))
bmask.BooleanIntersection(grown(body, -0.1))
bmask.Simplify()
add_filled(board, bmask, pcbnew.B_Mask)

# ---- back silkscreen: the maker's credit, scaled with the art, plus small labels -------------------------
cr = CREDIT[0]
t = pcbnew.PCB_TEXT(board)
t.SetText(cr.GetText())
t.SetLayer(B_SilkS)
t.SetTextSize(VECTOR2I(int(cr.GetTextSize().x * SCALE), int(cr.GetTextSize().y * SCALE)))
t.SetTextThickness(int(cr.GetTextThickness() * SCALE))
t.SetBold(cr.IsBold())
t.SetMirrored(cr.IsMirrored())
t.SetHorizJustify(cr.GetHorizJustify())
t.SetVertJustify(cr.GetVertJustify())
t.SetTextAngle(cr.GetTextAngle())
t.SetPosition(P(*sc(*mm(cr.GetPosition()))))
board.Add(t)
_a, _b = cr.GetBoundingBox(), t.GetBoundingBox()
_ca = sc(ToMM(_a.GetCenter().x), ToMM(_a.GetCenter().y))
assert math.hypot(_ca[0] - ToMM(_b.GetCenter().x), _ca[1] - ToMM(_b.GetCenter().y)) < 0.05, "credit not where the scaled art puts it"
assert abs(ToMM(_b.GetWidth()) - SCALE * ToMM(_a.GetWidth())) < 0.1, "credit not scaled with the art"

LABELS = [("MYSTERIO rB", 38.6, 37.3, 0.8, 0), ("SAO++", 38.6, 38.5, 0.8, 0), ("NO USB ON SAO", 38.6, 39.7, 0.8, 0),
          ("SAO", s1[0] + 0.6, SY - 5.0, 0.8, 0), ("USB/BAT", s3[0] - 1.6, SY - 5.0, 0.8, 0),
          ("+", lp[0] + 2.2, lp[1] - 1.0, 0.9, 0), ("-", pp(jst, "2")[0] - 1.6, lp[1] - 0.9, 0.9, 0),
          ("1", j["1"][0] - 1.6, j["1"][1] - 2.6, 0.8, 0)]
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
print("vias:", [(round(x, 2), round(y, 2), n) for x, y, n in VIAS])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
