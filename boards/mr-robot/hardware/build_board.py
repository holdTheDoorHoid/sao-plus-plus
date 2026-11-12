#!/usr/bin/env python3
"""Build mr-robot.kicad_pcb from the maker's art (hardware/art.json) plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root (art.json comes from hardware/extract_art.py):
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mr-robot/hardware/build_board.py

What it does:
  - takes the maker's outline and face art (his bottom copper, bottom silkscreen and the "dave" / "darko" mask
    lettering), already mirrored so the face is on the front, and scales all of it up by SCALE (owner rule of
    2026-11-12: scale the whole board rather than squeeze parts over the edge)
  - flattens the very top of the head (USB-C socket) and the very bottom of the chin (switch knob) by well under 1 mm
  - puts every part on the back: the XIAO (USB-C at the top of the head), the SAO connector below it, the switch knob
    out of the chin, the LiPo socket in the right cheek (front view), the maker's sounder in the left cheek with a
    plain transistor driver round it
  - routes everything on the back copper with no vias; three of the 330 ohm / 1.3 k resistors let one other track pass
    between their pads
  - fills the rest of the back with ground copper, and keeps the maker's gold logo as a solder-mask opening on the back
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
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "mr-robot"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

SCALE = 1.10            # smallest step (of 1.05 / 1.10 / 1.15) at which XIAO, connector, switch and sounder all fit; see README
CX, CY = 30.0, 30.0     # scaling centre (the middle of the maker's board in art.json coordinates)
CLEAR = 0.30            # copper-to-copper gap cut into the ground copper
EDGE = 0.55             # ground copper stops this far short of the board edge (panel mouse-bite holes reach 0.25 mm in)
SIG, PWR = 0.20, 0.40

ART = json.load(open(os.path.join(HERE, "art.json")))


def S(p):
    return (CX + (p[0] - CX) * SCALE, CY + (p[1] - CY) * SCALE)


def polyset(entries):
    """SHAPE_POLY_SET (outlines with holes) from art.json entries, scaled."""
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


# ---- outline -------------------------------------------------------------------------------------
OL = [S(p) for p in ART["outline"]]


def edge_y(x, top=True):
    """Where a vertical line at x meets the maker's (scaled) outline, at the top or the bottom of the head."""
    ys = []
    for (x1, y1), (x2, y2) in zip(OL, OL[1:] + OL[:1]):
        if (x1 - x) * (x2 - x) < 0:
            ys.append(y1 + (x - x1) * (y2 - y1) / (x2 - x1))
    return min(ys) if top else max(ys)


XC = 30.0                                                  # XIAO centre: middle of the head
YT = round(max(edge_y(XC - 8.9), edge_y(XC + 8.9)) + 0.10, 2)   # module top: both top corners 0.1 mm inside the dome
YC = YT + 10.5
YB = YT + 21.0
Y_CROWN = YT - 1.5          # the USB-C socket's face; the dome above it is cut flat so a plug body does not hit the board
JX = 27.3                   # SAO connector, 2.7 mm left of centre: its body stays clear of the maker's gold logo (right of it)
JY = round(YB + 8.1, 2)     # below the XIAO with room for R2 between them
SX = 30.0                   # switch: knob out of the chin
SY = round(min(edge_y(SX - 5.65, False), edge_y(SX + 5.65, False)) - 0.30 - 1.83, 2)   # hold-down tabs 0.25 mm inside the chin
Y_CHIN = SY + 2.1           # the switch body's face; the chin below it is cut flat so the knob sticks out
assert SY - (JY + 5.6) > 3.8, "no room between the connector and the switch"
print(f"scale {SCALE}: XIAO top {YT}, bottom {YB}; connector y {JY}; switch y {SY}; crown cut at {Y_CROWN:.2f} "
      f"(dome top {edge_y(XC):.2f}), chin cut at {Y_CHIN:.2f} (chin {edge_y(XC, False):.2f})")

maker = poly(OL)
maker.Simplify()
body = pcbnew.SHAPE_POLY_SET(maker)
body.BooleanIntersection(poly([(0, Y_CROWN), (70, Y_CROWN), (70, Y_CHIN), (0, Y_CHIN)]))
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
mx0, my0, mx1, my1 = bbox_mm(poly([p for p in ART["outline"]]))
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm (maker's {mx1 - mx0:.2f} x {my1 - my0:.2f}); "
      f"flattened: crown {Y_CROWN - edge_y(XC):.2f} mm, chin {edge_y(XC, False) - Y_CHIN:.2f} mm")
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


def load(ref, pos):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
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


# ---- placement ----------------------------------------------------------------------------------
xiao = place("U1", (XC, YC), ("14", (XC - 8.11, YC - 7.56)))       # USB-C up, at the top of the head; 5V pad top-left
assert abs(pp(xiao, "1")[0] - (XC + 8.055)) < 0.01, "pads 1-7 (D0-D6) should be on the right (front view)"
conn = place("J1", (JX, JY), ("1", (JX - 2.54, JY - 3.4)))          # VCC top-left in front view, key slot up
sw = place("SW1", (SX, SY), ("1", (SX + 3.0, SY - 1.43)))          # pins up, knob down out of the chin; pin 1 (SAO) right
u = {n: pp(xiao, n) for n in ("2", "5", "6", "7", "8", "11", "12", "13")}
OUTX_L = XC - 8.11 - 1.375                 # outer ends of the XIAO's left pads
INX_R = XC + 8.055 - 1.375                 # inner ends of its right pads
OUTX_R = XC + 8.055 + 1.375

# the sounder (maker's KMTG-1102, his footprint) stands upright in the left cheek, + pad at the top
SPX = 14.9
SP_TOP = u["11"][1] + 0.8                  # body top: just below the D10 base resistor
SPY = SP_TOP + 5.5
spk = place("LS1", (SPX, SPY), ("2", (SPX, SPY - 7.0)))
V3X = 19.65                                # 3.3 V riser up the left side, through R1's pads
AX, BX = 17.9, 18.825                      # sounder + node and transistor base, run down under the sounder's body
r1 = place("R1", (V3X, u["11"][1]), ("1", (V3X + 0.825, u["11"][1])))     # D10 -> base resistor, 3.3 V passes between its pads
r5 = place("R5", (17.9, 19.25), ("1", (17.9 + 0.825, 19.25)))              # 2 x 330 ohm in parallel: 3.3 V -> sounder +
r6 = place("R6", (17.9, 17.75), ("1", (17.9 + 0.825, 17.75)))
spb = pp(spk, "1")                                                          # sounder - pad (bottom)
d1 = place("D1", (AX - 0.7, spb[1] - 0.73), ("1", (AX, spb[1] - 0.73)))    # flyback diode: cathode on the + node
r7 = place("R7", (AX - 0.825, spb[1] + 0.72), ("1", (AX, spb[1] + 0.72)))  # bleed resistor across the sounder
QX, QY = spb[0] + 1.3, spb[1] + 1.5 + 1.475                                 # transistor below the sounder, collector up into its - pad
q1 = place("Q1", (QX, QY), ("3", (QX, QY - 0.9375)))
qb, qe = pp(q1, "1"), pp(q1, "2")
print("Q1 base at", qb, "emitter at", qe)

# R2 (SAO GPIO1) stands on the connector's pin 5, between connector and XIAO; a ground track passes between its pads
j = {n: pp(conn, n) for n in "123456"}
R2_C = (j["5"][0], round(YB + 1.475, 3))   # 0.3 mm clear of the module end
r2 = place("R2", R2_C, ("1", (R2_C[0], R2_C[1] + 0.825)))
R3_C = (37.6, 33.9)
r3 = place("R3", R3_C, ("1", (R3_C[0], R3_C[1] + 0.825)))
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
R4_C = (s1[0], round(s1[1] - 0.75 - 0.3 - 0.475 - 0.03, 3))               # just above switch pin 1; badge 3.3 V passes between its pads
r4 = place("R4", R4_C, ("1", (R4_C[0] - 0.825, R4_C[1])))

# LiPo socket in the right cheek, opening to the right edge
JST = (46.3, 27.6)
jst = load("J2", JST)
for rot in (0, 90, 180, 270):
    jst.SetOrientationDegrees(rot)
    sig = [mm(p.GetPosition()) for p in jst.Pads() if p.GetNumber() in ("1", "2")]
    hold = [mm(p.GetPosition()) for p in jst.Pads() if p.GetNumber() == ""]
    if all(x < JST[0] - 2 for x, _ in sig) and all(x > JST[0] + 2 for x, _ in hold):
        break
else:
    raise AssertionError("no rotation puts the LiPo socket's opening to the right")
link(jst, "J2")
jp, jn = pp(jst, "1"), pp(jst, "2")
print("LiPo + at", jp, "- at", jn)

FPS = list(board.GetFootprints())
_pad_ok = grown(body, -0.25)
for fp in FPS:
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"


def body_of(fp, layer=pcbnew.B_Fab):
    ps = pcbnew.SHAPE_POLY_SET()
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY, pcbnew.SHAPE_T_SEGMENT):
            g.TransformShapeToPolygon(ps, layer, 0, ERR, pcbnew.ERROR_OUTSIDE)
    return ps


sb = bbox_mm(body_of(spk))
print("sounder body (fab)", [round(v, 2) for v in sb])
for x, y in ((sb[0], sb[1]), (sb[2], sb[1]), (sb[0], sb[3]), (sb[2], sb[3])):
    assert body.Contains(P(x, y)), f"sounder body corner ({x:.2f}, {y:.2f}) is off the board"

# ---- routing (back copper only) -----------------------------------------------------------------
TRACKS = []
_trk_ok = grown(body, -0.35)


def route(net, pts, width=SIG, clear=CLEAR):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        for q in (a, b):
            assert _trk_ok.Contains(P(*q)), f"{net}: track point {q} is within 0.35 mm of the edge"
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear, net))


# --- J1 channel: three lanes run right between the connector's two pad rows (under its plastic body) ---
TOPROW_BOT, BOTROW_TOP = JY - 1.2, JY + 1.2
L1, L2, L3 = TOPROW_BOT + 0.6, JY, BOTROW_TOP - 0.6
SDA_X, SCL_X, G2_X = 33.6, 34.2, 34.8          # risers into the XIAO's underside, right of pin 5, under the connector's body
route("SDA", [(j["3"][0], TOPROW_BOT), (j["3"][0], L1), (SDA_X, L1), (SDA_X, u["5"][1]), (INX_R, u["5"][1])])
route("SCL", [(j["4"][0], BOTROW_TOP), (j["4"][0], L2), (SCL_X, L2), (SCL_X, u["6"][1]), (INX_R, u["6"][1])])
G2_Y = 36.6
route("SAO_GPIO2", [(j["6"][0], BOTROW_TOP), (j["6"][0], L3), (G2_X, L3), (G2_X, G2_Y), (R3_C[0], G2_Y), pp(r3, "1")])
route("D6_TX", [pp(r3, "2"), (R3_C[0], u["7"][1] + 1.0)])

# --- GPIO1: pin 5 -> R2 (standing on it) -> under the XIAO's end -> up into D7 from below ---
D7_Y = YB - 0.57
route("SAO_GPIO1", [(j["5"][0], JY - 3.4 - 2.2), pp(r2, "1")])
route("D7_RX", [pp(r2, "2"), (R2_C[0], D7_Y), (22.4, D7_Y), (22.4, u["8"][1] + 1.0)])
# a 0.25 mm strip of ground copper between R2's pads joins the ground round the connector to the ground under the
# XIAO (added to the ground fill below, so it is one piece with it)
GND_BRIDGE = poly([(R2_C[0] - 1.6, R2_C[1] - 0.125), (R2_C[0] + 1.6, R2_C[1] - 0.125), (R2_C[0] + 1.6, R2_C[1] + 0.125),
                   (R2_C[0] - 1.6, R2_C[1] + 0.125)])

# --- badge 3.3 V: switch pin 1 -> up between R4's pads -> left -> up between pins 2 and 4 -> pin 1 ---
VS_Y = round(JY + 5.6 + 0.53, 2)
GAPB1 = (j["2"][0] + j["4"][0]) / 2
route("VSAO", [(s1[0], s1[1] - 0.75), (s1[0], VS_Y)], 0.25)          # 0.25 mm where it passes between R4's pads
route("VSAO", [(s1[0], VS_Y), (GAPB1, VS_Y), (GAPB1, L1), (j["1"][0], L1), (j["1"][0], TOPROW_BOT)], 0.3)

# --- OFF sense: switch pin 2 -> R4 -> right under the logo, up the right side outside the XIAO's pads -> D1 ---
route("OFF_SW", [(s2[0], s2[1] - 0.75), (s2[0], R4_C[1] + 0.35), pp(r4, "1")])
OFFX = OUTX_R + 0.57
route("OFF_SENSE", [pp(r4, "2"), (38.6, R4_C[1]), (41.0, 44.5), (41.0, 37.2), (OFFX, 36.2), (OFFX, u["2"][1]), (OUTX_R, u["2"][1])])

# --- switched 3.3 V: switch pin 3 -> left -> up the left jaw -> between R1's pads -> XIAO 3V3; R5/R6 hang off it ---
V3_Y = round(s3[1] - 0.75 - 0.5, 2)
route("V3V3", [(s3[0], s3[1] - 0.75), (s3[0], V3_Y), (22.6, V3_Y), (V3X, 42.5), (V3X, u["11"][1] + 0.9)], PWR)
route("V3V3", [(V3X, u["11"][1] + 0.9), (V3X, u["11"][1] - 0.9)], 0.25)          # between R1's pads
route("V3V3", [(V3X, u["11"][1] - 0.9), (V3X, u["12"][1]), (OUTX_L, u["12"][1])], PWR)
route("V3V3", [(V3X, u["12"][1]), (V3X, 17.75), pp(r6, "1")], 0.3)
route("V3V3", [pp(r5, "1"), (V3X, 19.25)], 0.3)

# --- sounder driver ---
spt = pp(spk, "2")
route("AUDIO", [u["11"], pp(r1, "1")], 0.25)
route("SPK_PLUS", [pp(r6, "2"), (spt[0] + 1.2, SP_TOP - 2.8)], 0.3)
route("SPK_PLUS", [pp(r5, "2"), (spt[0] + 1.3, 19.25)], 0.3)
route("SPK_PLUS", [(spt[0] + 1.3, spt[1] + 1.2), (AX, spt[1] + 1.2), pp(d1, "1"), pp(r7, "1")], 0.25)
route("Q_BASE", [pp(r1, "2"), (BX, u["11"][1] + 0.5), (BX, qb[1] - 1.4), (qb[0], qb[1] - 0.6), qb])
route("SPK_MINUS", [pp(d1, "2"), (spb[0] + 1.3, pp(d1, "2")[1])], 0.3)
route("SPK_MINUS", [pp(r7, "2"), (spb[0] + 1.3, pp(r7, "2")[1])], 0.3)
route("SPK_MINUS", [pp(q1, "3"), (pp(q1, "3")[0], spb[1] + 1.2)], 0.4)

# --- LiPo +: socket pin 1 -> up the right cheek -> between the XIAO's pads 1 and 2 -> both battery pad positions ---
bp_c6 = pp(xiao, "15", pick=lambda p: -p[1])           # lower one = C6 position
bp_c3 = pp(xiao, "15", pick=lambda p: p[1])
GAP12 = (pp(xiao, "1")[1] + pp(xiao, "2")[1]) / 2
if jp[1] < jn[1]:                                      # + is the upper pin: straight up from it
    BATX = jp[0] - 1.25
    route("BAT+", [jp, (BATX, jp[1])], 0.3)
else:                                                  # + is the lower pin: out of its inner end, then up past the - pin
    BATX = jp[0] - 2.55
    route("BAT+", [jp, (BATX, jp[1])], 0.3)
route("BAT+", [(BATX, jp[1]), (BATX, GAP12), (INX_R - 0.3, GAP12)], 0.2)          # 0.2 mm between the XIAO's pads 1 and 2
route("BAT+", [(INX_R - 0.3, GAP12), (INX_R - 0.48, GAP12), (INX_R - 0.48, bp_c3[1]), bp_c3], 0.3)
route("BAT+", [bp_c3, (bp_c3[0], 22.3), (bp_c6[0], 22.3), bp_c6], 0.3)

# ---- back copper ----------------------------------------------------------------------------------
gnd_code = nets["GND"].GetNetCode()
cut_gnd = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut_gnd, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            continue
        if pad.IsOnLayer(B_Cu) and pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut_gnd, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t, clear, net in TRACKS:
    if net != "GND":
        t.TransformShapeToPolygon(cut_gnd, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
for g in xiao.GraphicalItems():                                  # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut_gnd, g.GetCenter(), 0.85 + 0.15)

# the maker's gold "ds" logo (his parts side = our back): a solder-mask opening over its own copper island
logo = polyset(ART["logo"]["F.Mask"])
logo_cu = grown(logo, 0.08)
assert inner.Contains(P(*[(a + b) / 2 for a, b in zip(bbox_mm(logo)[:2], bbox_mm(logo)[2:])]))
add_filled(board, logo_cu, B_Cu)
add_filled(board, logo, pcbnew.B_Mask)
cut_gnd.BooleanAdd(grown(logo_cu, CLEAR))
cut_gnd.Simplify()

gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(cut_gnd)
gnd.BooleanAdd(GND_BRIDGE)
gnd.Simplify()
gnd_seed = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_seed.Append(pad_poly(pad, B_Cu))
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
print("back ground pieces", n_gnd, "scraps dropped", n_drop)

# ---- front: the maker's face art --------------------------------------------------------------------
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
TABS = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))["tabs"] if os.path.exists(
    os.path.join(HERE, "..", "production", "panel.json")) else []
tab_keep = pcbnew.SHAPE_POLY_SET()
for t_ in TABS:
    add_circle(tab_keep, P(*t_["near"]), 2.6)
tab_keep.BooleanIntersection(grown(body, 0.1))
tab_keep.BooleanSubtract(inner)
tab_keep.Simplify()

fcu = polyset(ART["copper"])
fcu.BooleanIntersection(grown(body, -0.3))
fcu.BooleanSubtract(pegs)
fcu.BooleanSubtract(tab_keep)
fcu.Simplify()
n_f = 0
for i in range(fcu.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(fcu.Polygon(i))
    if area_mm2(piece) > 0.02:
        n_f += add_filled(board, piece, F_Cu)
print("front art copper pieces", n_f)
fsilk = grown(polyset(ART["silk"]), 0.05)       # Eagle drew these polygons with a 0.1 mm outline
fsilk.BooleanIntersection(grown(body, -0.15))
fsilk.BooleanSubtract(pegs)
fsilk.Simplify()
add_filled(board, fsilk, pcbnew.F_SilkS)
for mt in ART["mask_text"]:                     # "dave" / "darko": openings in the front mask, in the eyes
    t = pcbnew.PCB_TEXT(board)
    t.SetText(mt["text"])
    t.SetLayer(pcbnew.F_Mask)
    t.SetPosition(P(*S(mt["at"])))
    t.SetTextSize(VECTOR2I(FromMM(mt["size"] * SCALE), FromMM(mt["size"] * SCALE)))
    t.SetTextThickness(FromMM(mt["thickness"] * SCALE))
    t.SetTextAngleDegrees(mt["angle"])
    board.Add(t)

# ---- back silkscreen labels ---------------------------------------------------------------------------
LABELS = [("MR. ROBOT rA", 45.6, 32.4, 0.8), ("SAO++", 45.6, 33.6, 0.8), ("NO USB", 45.6, 34.8, 0.8), ("ON SAO", 45.0, 36.0, 0.8),
          ("SAO", s1[0] + 4.3, SY - 2.0, 0.8), ("USB", SX - 7.3, SY - 2.0, 0.8),
          ("+", jp[0] - 2.4, jp[1], 0.9), ("-", jn[0] - 2.4, jn[1], 0.9), ("LiPo", JST[0] + 0.2, JST[1] - 5.0, 0.8),
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
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.15))   # LiPo + passes 0.17 mm from the XIAO's pads 1 and 2
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
