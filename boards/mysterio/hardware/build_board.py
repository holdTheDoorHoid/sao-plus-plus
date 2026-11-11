#!/usr/bin/env python3
"""Build mysterio.kicad_pcb from the maker's KiCad 8 board plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mysterio/hardware/build_board.py

The maker's board is a 4-layer board: the helmet's skull-and-swirl art is copper on inner layer 2, lit from behind by
four side-firing RGB LEDs round the bottom of the helmet. SAO++ boards are 2-layer, so this script:
  - copies the front art (copper, mask, silkscreen) and the back credit exactly as drawn
  - moves the inner-layer helmet art to the back copper (seen from the front through the board it sits 0.1 mm
    deeper than before), and opens the back mask only where the maker's mask was open AND there is no copper, so
    light gets into the board in the same places as on the original
  - uses the helmet's solid outer ring of art copper as the LEDs' 3.3 V conductor (it is copper anyway)
  - replaces the CH32V003, its two I2C pull-ups and the through-hole header with the XIAO, the SMD SAO connector
    and the power switch, on a strip added below the figure and a slightly wider right arm (see README)
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
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "mysterio"
SRC = os.path.join(HERE, "..", "original", "mysterio", "mysterio.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper and the art
EDGE = 0.55         # GND copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20
PWR = 0.30
HELMET = (24.94, 25.64)   # centre of the helmet circle (from the maker's inner-layer ring)
R_LED = 11.7              # the maker put D2 and D3 at this radius; D1 and D4 are moved out to it (see below)

# ---- placement constants (see README "Why the board grew") ----
L_EDGE = 5.0        # new straight left edge below the arm (the maker's edge is at 5.26 there)
E_EDGE = 45.7       # new straight right edge (the maker's right arm ends at 43.95)
XC = 35.2           # XIAO centre x: its USB end is flush with the new bottom edge
B_EDGE = 60.55      # new bottom edge (the maker's figure ends at 48.5)
YC = B_EDGE - 10.5
JX, JY = 17.8, 51.4  # SAO connector: body top 46.95, just below the maker's credit (which ends at 46.73)
SX, SY = L_EDGE + 2.1, 53.2   # switch, knob out of the left edge below the credit

# ---- the maker's art -----------------------------------------------------------------------------
orig = pcbnew.LoadBoard(SRC)
ART = {}
for d in orig.GetDrawings():
    if d.GetClass() == "PCB_SHAPE" and d.GetShape() == pcbnew.SHAPE_T_POLY:
        ART.setdefault(d.GetLayer(), []).append(pcbnew.SHAPE_POLY_SET(d.GetPolyShape()))
assert len(ART[F_Cu]) == 12 and len(ART[pcbnew.In2_Cu]) == 23 and len(ART[pcbnew.B_Mask]) == 211, {k: len(v) for k, v in ART.items()}
CREDIT = [d for d in orig.GetDrawings() if d.GetClass() == "PCB_TEXT" and "davedarko" in d.GetText()]
assert len(CREDIT) == 1


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
LED_ORIG = {fp.GetReference(): fp for fp in orig.GetFootprints() if fp.GetReference().startswith("D")}

# ---- outline: the maker's outline plus a strip below and a straightened right arm ---------------
_ol = orig.GetBoardEdgesBoundingBox()
maker = pcbnew.SHAPE_POLY_SET()
assert orig.GetBoardPolygonOutlines(maker, False)
maker.Simplify()
assert maker.OutlineCount() == 1


def rounded(pts, r, corners):
    """Polygon through pts, with the listed corner indices rounded to radius r."""
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
        cx, cy = x + (ux + vx) * r, y + (uy + vy) * r          # right-angle corners only
        a0 = math.atan2(y + uy * r - cy, x + ux * r - cx)
        a1 = math.atan2(y + vy * r - cy, x + vx * r - cx)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(9):
            t = a0 + da * k / 8
            out.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return out


EXT = rounded([(5.58, 45.5), (14.0, 40.0), (24.0, 38.0), (41.64, 34.0), (E_EDGE, 39.0), (E_EDGE, B_EDGE), (L_EDGE, B_EDGE), (L_EDGE, 47.4)], 1.0, (5, 6))
body = union([maker, poly(EXT)])
print("outlines", body.OutlineCount(), [body.HoleCount(i) for i in range(body.OutlineCount())], [bbox_mm(pcbnew.SHAPE_POLY_SET(body.Polygon(i))) for i in range(body.OutlineCount())])
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f} (maker's: 38.80 x 34.14)")
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


# ---- LEDs: same part, same direction as the maker's ---------------------------------------------
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
    ox, oy = mm(mf.GetPosition())             # the maker's footprint origin = middle of the pads' back edge
    ux, uy = lens_dir(mf, pcbnew.Dwgs_User)
    # D1 and D4 sat 0.74 mm further in than D2 and D3, with their pads over the helmet ring. On one copper layer the ring
    # carries 3.3 V and would be cut through at their pads, so they move out along their own axis to D2/D3's radius.
    rx, ry = ox - HELMET[0], oy - HELMET[1]
    r0 = math.hypot(rx, ry)
    nx, ny = ox + rx / r0 * (R_LED - r0), oy + ry / r0 * (R_LED - r0)
    LED_SHIFT[ref] = round(math.hypot(nx - ox, ny - oy), 2)
    fp = load(ref, (nx, ny))
    want = math.degrees(math.atan2(uy, ux))
    fp.SetOrientationDegrees(0)
    vx, vy = lens_dir(fp, pcbnew.B_Fab)
    have = math.degrees(math.atan2(vy, vx))
    for sgn in (1, -1):                        # which way an orientation step turns a flipped footprint
        fp.SetOrientationDegrees((sgn * (want - have)) % 360)
        vx, vy = lens_dir(fp, pcbnew.B_Fab)
        if vx * ux + vy * uy > 0.9999:
            break
    else:
        raise AssertionError(f"{ref}: could not match the lens direction")
    # shared footprint: pads' back edge is at local y = -0.65; put its middle where the maker's origin (moved) is
    p1 = pp(fp, "1")
    p4 = pp(fp, "4")
    mid = ((p1[0] + p4[0]) / 2, (p1[1] + p4[1]) / 2)          # GND/VDD pad centres sit 0.25 in from the back edge
    back = (mid[0] - ux * 0.25, mid[1] - uy * 0.25)
    _fx, _fy = mm(fp.GetPosition())
    fp.SetPosition(P(_fx + nx - back[0], _fy + ny - back[1]))
    link(fp, ref)
    led[ref] = fp
    toward = -(rx * ux + ry * uy) / r0
    print(f"{ref}: maker at ({ox:.2f},{oy:.2f}) moved {LED_SHIFT[ref]} mm, lens {math.degrees(math.atan2(uy, ux)):.1f} deg, "
          f"points {toward:.2f} toward the helmet centre, rot {fp.GetOrientationDegrees():.1f}")

# ---- other parts ----------------------------------------------------------------------------------
xiao = place("U1", (XC, YC), ("14", (XC + 8.11, YC + 7.56)))      # USB end down, flush with the bottom edge
assert abs(pp(xiao, "1")[0] - (XC - 8.05)) < 0.01, "pads 1-7 (D0-D6) should face the connector"
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))          # VCC top-left in front view, key slot up
sw = place("SW1", (SX, SY), ("1", (SX + 1.43, SY + 3.0)))           # knob out of the left edge; on the back, pin 1 is the lowest

R1_C, R2_C, R3_C, R4_C, C1_C = (39.3, 37.0), (JX + 2.54, 44.0), (22.4, 57.9), (10.05, 57.4), (36.3, 38.3)
r1 = place("R1", R1_C, ("1", (R1_C[0] + 0.82, R1_C[1])))       # data in from the XIAO on the right; the 3.3 V feed passes between its pads
r2 = place("R2", R2_C, ("1", (R2_C[0], R2_C[1] + 0.82)))       # on GPIO1, above connector pin 5; SDA passes between its pads
r3 = place("R3", R3_C, ("1", (R3_C[0], R3_C[1] - 0.82)))       # on GPIO2, below the connector; SCL passes between its pads
r4 = place("R4", R4_C, ("1", (R4_C[0], R4_C[1] - 0.82)))       # on the OFF sense line, just below the connector body; badge 3.3 V passes between its pads
c1 = place("C1", C1_C, ("1", (C1_C[0] + 0.78, C1_C[1])))       # 3.3 V on the right (under the feed to the LEDs), ground on the left

_pad_ok = grown(body, -0.25)
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
    crt.BooleanIntersection(disc(*HELMET, 11.28))
    assert area_mm2(crt) < 0.01, f"{fp.GetReference()} sits over the helmet (the LEDs' light path)"

# ---- routing (back copper only) -----------------------------------------------------------------
TRACKS = []


def route(net, pts, width=SIG, clear=CLEAR):
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
        TRACKS.append((t, clear, net))


s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
j = {n: pp(conn, n) for n in "123456"}
u = {n: pp(xiao, n) for n in ("2", "5", "6", "7", "8", "11", "12")}
GAP = JY                                  # between the connector's two pad rows
PAD_IN_L = XC - 8.05 + 1.375              # inner ends of the XIAO's left pads (D0..D6)
PAD_OUT_R = XC + 8.11 + 1.375             # outer ends of its right pads (D7..D10, 3V3, GND, 5V)

# badge 3.3 V: switch pin 1 (lowest) -> through R4 -> connector pin 1
route("VSAO", [s1, (9.2, R4_C[1]), (12.0, R4_C[1]), (12.0, 49.0), (j["1"][0], 49.0)], PWR)
# OFF sense: switch pin 2 -> R4 -> through the gap between the connector's pad rows -> XIAO D1 from outside
route("OFF_SW", [s2, (R4_C[0], s2[1]), pp(r4, "1")])
route("OFF_SENSE", [pp(r4, "2"), (R4_C[0], 59.0), (13.6, 59.0), (13.6, GAP), (24.0, GAP), (24.0, u["2"][1]), u["2"]])
# switched 3.3 V: switch pin 3 (above) -> up beside the connector, past the credit -> LED D4's VDD pad from outside
V3X = 13.0
d4v = pp(led["D4"], "4")
OUTW = {k: ((mm(f.GetPosition())[0] - HELMET[0]), (mm(f.GetPosition())[1] - HELMET[1])) for k, f in led.items()}
OUTW = {k: (x / math.hypot(x, y), y / math.hypot(x, y)) for k, (x, y) in OUTW.items()}


def outside(ref, num, d):
    x, y = pp(led[ref], num)
    ox, oy = OUTW[ref]
    return (round(x + ox * d, 3), round(y + oy * d, 3))


route("V3V3", [s3, (11.2, s3[1]), (11.2, 47.1), (V3X, 47.1), (V3X, 34.6), outside("D4", "4", 0.75), d4v], PWR)

# I2C and GPIO
route("SDA", [j["3"], (j["3"][0], R2_C[1]), (23.2, R2_C[1]), (23.2, u["5"][1]), u["5"]])         # under R2
route("SAO_GPIO1", [j["5"], pp(r2, "1")])
TOP = YC - 9.6                                                                                   # just inside the XIAO's top end
route("D7_RX", [pp(r2, "2"), (R2_C[0], TOP), (u["8"][0], TOP), u["8"]])
route("SCL", [j["4"], (j["4"][0], R3_C[1]), (23.5, R3_C[1]), (23.5, YC + 8.85), (PAD_IN_L + 0.29, YC + 8.85),
              (PAD_IN_L + 0.29, u["6"][1]), u["6"]])                                             # under R3, then under the XIAO
route("SAO_GPIO2", [j["6"], (j["6"][0] + 0.2, 56.0), (R3_C[0], 56.0), pp(r3, "1")])
route("D6_TX", [pp(r3, "2"), (R3_C[0], YC + 9.25), (PAD_IN_L + 0.68, YC + 9.25), (PAD_IN_L + 0.68, u["7"][1]), u["7"]])

# right edge: LED data and the XIAO's 3V3 pin run up outside the right pads, cross at R1, and feed LED D1
DX, VX = PAD_OUT_R + 0.26, PAD_OUT_R + 0.64
_n = (-0.776, 0.63)                                   # inward normal of the slanted edge above the XIAO
_t = (-0.63, -0.776)
_o = (E_EDGE + _n[0] * 0.45, 39.0 + _n[1] * 0.45)     # 3V3 line runs 0.45 inside that edge


def slant_x(off, x):
    x0, y0 = _o[0] + _n[0] * off, _o[1] + _n[1] * off
    k = (x - x0) / _t[0]
    return (x, round(y0 + _t[1] * k, 3))


def on_slant(off, y):
    x0, y0 = _o[0] + _n[0] * off, _o[1] + _n[1] * off
    k = (y - y0) / _t[1]
    return (round(x0 + _t[0] * k, 3), y)


route("LED_DATA", [u["11"], (DX, u["11"][1]), slant_x(0.43, DX), on_slant(0.43, 38.2), (pp(r1, "1")[0] + 0.6, R1_C[1]), pp(r1, "1")])
route("LED_DIN", [pp(r1, "2"), outside("D1", "3", 0.75), pp(led["D1"], "3")])
route("V3V3", [u["12"], (VX, u["12"][1]), slant_x(0.0, VX), on_slant(0.0, 36.2), (R1_C[0], 36.2), (R1_C[0], 37.8), (C1_C[0], 37.8),
               outside("D1", "4", 0.75), pp(led["D1"], "4")], 0.24)
route("V3V3", [pp(c1, "1"), (pp(c1, "1")[0], 37.8)], 0.24)
route("unconnected-(U1-BAT+-Pad15)", [pp(xiao, "15", pick=lambda p: p[1]), (pp(xiao, "15", pick=lambda p: -p[1])[0], 47.2),
               pp(xiao, "15", pick=lambda p: -p[1])], SIG)      # the two BAT+ pad positions (C6 / C3-S3) joined; no LiPo connector on this board, so the net goes nowhere else
# LED chain round the bottom of the helmet, kept outside the art ring
ARC = 11.65


def rim(deg):
    return (round(HELMET[0] + ARC * math.cos(math.radians(deg)), 3), round(HELMET[1] + ARC * math.sin(math.radians(deg)), 3))


route("LED_D1", [pp(led["D1"], "2"), rim(49), pp(led["D2"], "3")], SIG, 0.2)
route("LED_D2", [pp(led["D2"], "2"), rim(82), rim(98), pp(led["D3"], "3")], SIG, 0.2)
route("LED_D3", [pp(led["D3"], "2"), rim(131.8), pp(led["D4"], "3")], SIG, 0.2)
# each LED's VDD pad reaches in to the ring
for ref in led:
    x, y = pp(led[ref], "4")
    ox, oy = OUTW[ref]
    route("V3V3", [(x, y), (round(x - ox * 0.75, 3), round(y - oy * 0.75, 3))], 0.25, 0.2)

# ---- tented ground vias: the front art copper is the ground that joins the back's ground pieces ------------
# The maker's board had seven ground vias in the front art; this one has two.
VIAS = [(23.5, 49.0),      # ground under the helmet (LEDs D1-D3, C1), between the connector and the XIAO -> torso / base strip
        (15.6, 57.9)]      # everything else (connector ground pin, XIAO ground pin, left arm) -> base strip
gnd_code = nets["GND"].GetNetCode()
for x, y in VIAS:
    v = pcbnew.PCB_VIA(board)
    board.Add(v)
    v.SetPosition(P(x, y))
    v.SetDrill(FromMM(0.3))
    v.SetWidth(FromMM(0.6))
    v.SetNet(nets["GND"])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED)

# ---- back copper ----------------------------------------------------------------------------------
# 1. the maker's inner-layer helmet art, now on the back. Its biggest piece (the outer ring and the swirl joined to it)
#    is the LEDs' 3.3 V; the skull and the loose swirl flecks are plain art.
_ha = union(ART[pcbnew.In2_Cu])                   # overlapping pieces merge here
helmet_art = sorted([pcbnew.SHAPE_POLY_SET(_ha.Polygon(i)) for i in range(_ha.OutlineCount())], key=lambda p_: -area_mm2(p_))
# where the panel's break-off tabs meet the board (production/panel.json) no copper may come within EDGE of the edge:
# the mouse-bite holes reach 0.25 mm in. The maker's art comes to 0.2-0.3 mm of his edge, so it is nibbled back there.
TAB_EDGE = [(6.4, 41.0), (10.5, 32.0), (39.5, 31.5)]
tab_keep = pcbnew.SHAPE_POLY_SET()
for x, y in TAB_EDGE:
    add_circle(tab_keep, P(x, y), 2.6)
tab_keep.BooleanIntersection(grown(body, 0.1))
tab_keep.BooleanSubtract(inner)
tab_keep.Simplify()
ring = pcbnew.SHAPE_POLY_SET(helmet_art[0])
others = union(helmet_art[1:])
clip = grown(body, -0.3)
ring.BooleanIntersection(clip)
others.BooleanIntersection(clip)
v3_code = nets["V3V3"].GetNetCode()
cut_v3 = pcbnew.SHAPE_POLY_SET()           # around everything that is not 3.3 V
cut_gnd = pcbnew.SHAPE_POLY_SET()          # around everything that is not ground
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
    if net != "V3V3":
        t.TransformShapeToPolygon(cut_v3, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
    if net != "GND":
        t.TransformShapeToPolygon(cut_gnd, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
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
for i in range(ring.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(ring.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(v3_pads)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["V3V3"])
        n_ring += 1
        print("  3.3 V ring piece mm2:", round(area_mm2(piece), 1))
    elif area_mm2(piece) > 0.02:
        others.BooleanAdd(piece)
others.Simplify()
for i in range(others.OutlineCount()):
    add_filled(board, pcbnew.SHAPE_POLY_SET(others.Polygon(i)), B_Cu)
print("helmet art: 3.3 V pieces", n_ring, "plain art pieces", others.OutlineCount())

# 2. ground everywhere else on the back, except the helmet (the LEDs light it from behind)
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(disc(*HELMET, 11.0 + CLEAR))
gnd.BooleanSubtract(cut_gnd)
gnd.Simplify()
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
for x, y in VIAS:
    add_circle(gnd_seed, P(x, y), 0.3)
gnd_seed.Simplify()
n_gnd = n_drop = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_seed)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  GND piece mm2:", round(area_mm2(piece), 1), "at", [round(v_, 1) for v_ in bbox_mm(piece)])
    else:
        n_drop += 1
        print("  dropped scrap mm2:", round(area_mm2(piece), 2), "at", [round(v_, 1) for v_ in bbox_mm(piece)])
print("back ground pieces", n_gnd, "scraps dropped", n_drop)

# 3. back mask: open only where the maker's mask was open and there is no copper behind it now
bmask = union(ART[pcbnew.B_Mask])
bmask.BooleanSubtract(grown(union(helmet_art), 0.05))
bmask.BooleanIntersection(grown(body, -0.1))
bmask.Simplify()
add_filled(board, bmask, pcbnew.B_Mask)

# ---- front copper: the maker's art, the chest buttons, and a plain base strip below the figure ----------
maker_in = grown(maker, -0.4)                     # the base strip stays 0.4 mm clear of the maker's outline (a dark line)
base = pcbnew.SHAPE_POLY_SET(grown(body, -EDGE))          # ground: kept clear of the panel's mouse-bite holes
base.BooleanSubtract(grown(maker, 0.1))
base.BooleanIntersection(poly([(0, 47.3), (60, 47.3), (60, 70), (0, 70)]))
torso = [p_ for p_ in ART[F_Cu] if bbox_mm(p_)[3] > 48.0]
assert len(torso) == 1, "expected one front art piece reaching the old bottom edge (the torso)"
bridge = poly([(17.6, 47.9), (32.4, 47.9), (32.4, 49.2), (17.6, 49.2)])      # the torso runs on into the base strip
bridge.BooleanIntersection(grown(body, -EDGE))
plate = union([torso[0], base, bridge])
fcu_other = union([p_ for p_ in ART[F_Cu] if p_ is not torso[0]] + [btn_cu])
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
plate.BooleanSubtract(pegs)
plate.BooleanIntersection(grown(body, -0.26))
plate.BooleanSubtract(tab_keep)
plate.Simplify()
fcu_other.BooleanSubtract(pegs)
fcu_other.BooleanIntersection(grown(body, -0.26))   # the maker's art came within 0.20 mm of his edge in three places
fcu_other.BooleanSubtract(tab_keep)
fcu_other.Simplify()
for i in range(plate.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(plate.Polygon(i))
    if area_mm2(piece) > 1:
        add_filled(board, piece, F_Cu, nets["GND"])
if os.environ.get("VIAFIND"):
    _bp = grown(plate, -0.45)
    _bk = [pcbnew.SHAPE_POLY_SET(gnd.Polygon(i)) for i in range(gnd.OutlineCount())]
    _bk = grown([q for q in _bk if q.Contains(P(24.94, 38.6))][0], -0.45)
    for yy in range(300, 600, 5):
        row = [xx / 10 for xx in range(50, 460, 5) if _bp.Contains(P(xx / 10, yy / 10)) and _bk.Contains(P(xx / 10, yy / 10))]
        if row:
            print("via ok y", yy / 10, row[:12])
for x, y in VIAS:
    assert plate.Contains(P(x, y)), f"via at ({x}, {y}) does not land on the front ground plate"
for i in range(fcu_other.OutlineCount()):
    add_filled(board, pcbnew.SHAPE_POLY_SET(fcu_other.Polygon(i)), F_Cu)
fmask = union(ART[pcbnew.F_Mask] + [btn_mask])
add_filled(board, fmask, pcbnew.F_Mask)
add_filled(board, union(ART[pcbnew.F_SilkS]), pcbnew.F_SilkS)

# ---- back silkscreen: the maker's credit exactly as drawn, plus small labels ----------------------------
cr = CREDIT[0]
t = pcbnew.PCB_TEXT(board)
t.SetText(cr.GetText())
t.SetLayer(B_SilkS)
t.SetTextSize(cr.GetTextSize())
t.SetTextThickness(cr.GetTextThickness())
t.SetBold(cr.IsBold())
t.SetMirrored(cr.IsMirrored())
t.SetHorizJustify(cr.GetHorizJustify())
t.SetVertJustify(cr.GetVertJustify())
t.SetTextAngle(cr.GetTextAngle())
t.SetPosition(cr.GetPosition())
board.Add(t)
_a, _b = cr.GetBoundingBox(), t.GetBoundingBox()
assert (_a.GetX(), _a.GetY(), _a.GetWidth(), _a.GetHeight()) == (_b.GetX(), _b.GetY(), _b.GetWidth(), _b.GetHeight()), "credit moved"

# The switch sits between the connector and the edge with no room for labels beside it, so its legend goes with the
# board name in the free patch of ground copper under the helmet.
LABELS = [("NO USB ON SAO", 17.6, 37.9, 0.8, 0), ("MYSTERIO rA", 16.4, 39.1, 0.8, 0), ("SAO++", 16.4, 40.3, 0.8, 0),
          ("SW UP: USB", 16.1, 41.5, 0.8, 0), ("SW DN: SAO", 16.1, 42.7, 0.8, 0),
          ("1", 13.9, j["1"][1] - 2.7, 0.9, 0)]
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
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.15))   # the lanes under the XIAO are 0.19 mm apart
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
