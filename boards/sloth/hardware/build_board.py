#!/usr/bin/env python3
"""Build sloth.kicad_pcb from the maker's art (art/art.json) plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root:
  python3 boards/sloth/hardware/extract_art.py              (only if art/art.json is missing; system Python)
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sloth/hardware/build_board.py

The maker's board (original/REV1, Eagle 2017) is a 40 x 30 mm brooch: the sloth face in bare gold on one side with
twelve LEDs round it, the ATtiny85, its programming pads, a button and a cell holder on the other. art.json holds that
board scaled up by 1.3 (owner rule 2026-11-12: at 40 x 30 mm the SAO connector, cell clip and switch do not fit beside
the maker's chip, pads and button; see README) and seen from the face side. This script draws:
  front  - the maker's copper over the whole face side with his solder-mask openings (the gold sloth), his twelve LEDs
           facing forward in his positions, and the front half of a two-layer route: tented vias and short tracks under
           the solder mask in the dark ring round the face (never inside the gold)
  back   - the SAO connector, the SAO / OFF / BAT switch (knob out of the top edge), the CR2032 clip and its series
           diode, the maker's ATtiny85, ISP pads and button, five resistors and a capacitor; ground copper everywhere
           else; the maker's credit line and logo unchanged in place (scaled with the board)
Routing is done by router.py (a small two-layer grid router, deterministic, capped at 5 minutes) in this one run.
Coordinates are millimetres in KiCad's front view of the new board (x grows right, y grows down).
"""
import collections
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

SLUG = "sloth"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))
assert abs(ART["scale"] - 1.3) < 1e-9, "placements below are for the 1.3 scale"

CLEAR = 0.30        # copper-to-copper gap cut into the ground and art copper
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
PWR = 0.30          # supply track width
VIA_D, VIA_HOLE = 0.6, 0.3
GOLD_KEEP = 0.6     # front tracks and vias stay this far from the maker's gold (mask openings), so the gold is never cut

# ---- outline and art ----------------------------------------------------------------------------
body = poly(ART["outline"])
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm")


def union(polys):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in polys:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


def eagle_poly(item):
    """An Eagle filled polygon is its outline drawn with a pen of the given width: grow by half the width."""
    return grown(poly(item["pts"]), item["width"] / 2)


gold = union([eagle_poly(m) for m in ART["mask"]])          # the maker's solder-mask openings: the gold sloth
_g = pcbnew.SHAPE_POLY_SET(gold)
_g.BooleanSubtract(grown(body, -EDGE))
assert area_mm2(_g) < 0.01, "maker's art reaches the board edge"

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)

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
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
    fp.SetFPID(pcbnew.LIB_ID(fpid.split(":")[0], fpid.split(":")[1]))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
    fp.SetValue(PARTS[ref].get("value", value))
    for k, v in fields.items():
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


def load(ref, pos, back=True):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    if back:
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    return fp


def place(ref, pos, want, back=True, angles=(0, 90, 180, 270)):
    """Place a part at the rotation that puts pad want[0] nearest want[1]."""
    fp = load(ref, pos, back)
    best = None
    for rot in angles:
        fp.SetOrientationDegrees(rot)
        d = min(math.dist(mm(p.GetPosition()), want[1]) for p in fp.Pads() if p.GetNumber() == want[0])
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
# front: the maker's twelve LEDs at his centres, each turned as he turned it (anode pad toward his anode pad)
led = {}
for k in range(1, 13):
    v = ART["leds"][f"LED{k}"]
    c, an = v["centre"], v["anode"]
    u = (an[0] - c[0], an[1] - c[1])
    n_ = math.hypot(*u)
    want = (c[0] + 0.875 * u[0] / n_, c[1] + 0.875 * u[1] / n_)        # the 0603 pattern's anode pad sits 0.875 mm out
    led[f"D{k}"] = place(f"D{k}", tuple(c), ("2", want), back=False, angles=range(0, 360, 15))

# coin cell: left, its two + pads above and below the cell, closed end toward the middle, open toward the left edge
BAT = (112.5, 119.5)
bat = load("BT1", BAT)
link(bat, "BT1")


def _closed_dir():
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return ToMM(c.x) - BAT[0], ToMM(c.y) - BAT[1]


for rot in (90, 270):
    bat.SetOrientationDegrees(rot)
    if _closed_dir()[0] > 3:
        break
assert _closed_dir()[0] > 3, _closed_dir()
assert abs(pp(bat, "1", pick=lambda p: p[1])[1] - (BAT[1] - 10.5)) < 0.01      # + pads above and below the cell

# The maker's credit line runs across the right half just above the middle and his logo sits at the bottom centre
# (both on the back, kept where he had them). Everything that talks to the chip sits below the credit line; only the
# switch sits above it. The cell's feed to the switch (VBAT) goes the long way round, down the right-hand edge and along
# the bottom to the cell diode beside the clip's lower + pad, so it never has to cross the badge and board supplies.
CONN = (131.5, 121.0)       # right of the cell, key slot up
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC top-left in front view, as on Mad Cat
SWX, SW_FACE = 126.0, 100.5                                          # knob out of the flat top edge (shell tabs 0.25 mm inside it)
sw = place("SW1", (SWX, SW_FACE + 1.6), ("1", (SWX - 3.0, SW_FACE + 3.03)))   # knob up: pin 1 (badge) left, pin 4 (cell) right
U1_C = (144.6, 120.5)
u1 = place("U1", U1_C, ("1", (U1_C[0] - 1.905, U1_C[1] - 3.378)))  # upright, pin 1 top-left: 1-4 along the top, 8-5 along the bottom
ISP = (141.3, 131.3)
isp = place("JP1", ISP, ("P$1", (ISP[0] - 2.54, ISP[1] - 1.27)), angles=(90, 270))   # lying down, under the chip
BTN = (118.5, 135.0)
btn = place("SW2", BTN, ("P$1", (BTN[0] + 3.15, BTN[1])))           # below the cell: MISO pad right, ground pad left
C1_C = (140.8, 124.0)
c1 = place("C1", C1_C, ("1", (C1_C[0], C1_C[1] + 0.825)))           # between the connector and the chip: VCC down, by pin 8
D13_C = (124.6, 131.7)
d13 = place("D13", D13_C, ("2", (D13_C[0] - 0.7, D13_C[1])))         # beside the clip's lower + pad: anode (cell) left, cathode right
res = {}
# each LED resistor beside the chip pin that drives it: PB3 / PB4 (top row) above the chip, SCK to its left, MOSI to its
# right; the space between the chip and the ISP pads stays clear for the four programming lines
for ref, (x, y) in {"R3": (142.6, 113.6), "R4": (146.0, 113.6)}.items():
    res[ref] = place(ref, (x, y), ("1", (x - 0.825, y)))              # pad 1 (chip side) left
res["R2"] = place("R2", (140.8, 120.0), ("1", (140.8, 120.0 + 0.825)))  # pad 1 (SCK) down
res["R1"] = place("R1", (148.9, 122.6), ("1", (148.9, 122.6 + 0.825)))  # pad 1 (MOSI) down
res["R5"] = place("R5", (135.3, 127.8), ("1", (135.3 + 0.825, 127.8)))  # MISO right, badge GPIO2 left

_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            layer = F_Cu if pad.IsOnLayer(F_Cu) else B_Cu
            off = pad_poly(pad, layer)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"
# no LED pad may touch the gold
for ref, fp in led.items():
    for pad in fp.Pads():
        hit = pad_poly(pad, F_Cu, CLEAR)
        hit.BooleanIntersection(gold)
        assert area_mm2(hit) < 1e-4, f"{ref} pad {pad.GetNumber()} is within {CLEAR} mm of the gold art"


# ---- back silkscreen: the maker's credit line and logo, unchanged, where he had them -----------------
def text(txt, x, y, size, thick, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


SILK_KEEP = []          # (x0, y0, x1, y1): no back track, no via through the maker's lettering and logo
for c in ART["back_text"]:
    if c["text"] == "hackaday.io/davedarko":       # the maker's credit; his notes "150 Ohm", "ATTINY13A", "R1" no longer hold
        rx, by = c["right_bottom"]                  # Eagle anchors text at its bottom-left; seen from the front that is bottom-right
        t = text(c["text"], rx, by, c["size"], 0.15)
        bb = t.GetBoundingBox()
        t.Move(VECTOR2I(FromMM(rx) - bb.GetRight(), FromMM(by) - bb.GetBottom()))
        bb = t.GetBoundingBox()
        SILK_KEEP.append((ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())))
logo = union([eagle_poly(m) for m in ART["back_logo"]])
add_filled(board, logo, B_SilkS)
SILK_KEEP.append(bbox_mm(logo))
print("maker's back silk boxes:", [tuple(round(v, 2) for v in b) for b in SILK_KEEP])

# ---- routing: two copper layers (front LEDs need it; front copper stays in the dark ring) ----------
import router  # noqa: E402
from router import B as RB, F as RF  # noqa: E402

g = router.Grid(bx0 - 0.2, by0 - 0.2, bx1 + 0.2, by1 + 0.2)
EDGE_C = 0.5 + router.HW_MAX + 0.02                 # track centres this far in: copper stays 0.5 mm from the edge (mouse bites)
okarea = g.poly_mask(body, -EDGE_C)
for L in (RB, RF):
    g.stamp(L, ~okarea, -1)
CELL_KEEP = 10.4                                     # no back copper of any other net under the coin cell
cell_m = (g.X - BAT[0]) ** 2 + (g.Y - BAT[1]) ** 2 <= CELL_KEEP ** 2
g.stamp(RB, cell_m, -1)
INF = router.CLR + router.HW_MAX + router.SLACK
NOVIA_PARTS = None
for x0, y0, x1, y1 in SILK_KEEP:
    m = (g.X > x0 - 0.25) & (g.X < x1 + 0.25) & (g.Y > y0 - 0.25) & (g.Y < y1 + 0.25)
    g.stamp(RB, m, -1)
    g.noVia |= (g.X > x0 - 0.5) & (g.X < x1 + 0.5) & (g.Y > y0 - 0.5) & (g.Y < y1 + 0.5)
NOVIA_PARTS = g.noVia.copy()       # lettering only so far; the part bodies are added below
gold_m = g.poly_mask(gold, GOLD_KEEP)
g.stamp(RF, gold_m, -1)
g.noVia |= g.poly_mask(gold, GOLD_KEEP + 0.2)
g.cost[RF] = 3.0                                     # front copper is dearer than back copper
netcode = {}


def code(name):
    if name not in netcode:
        netcode[name] = len(netcode) + 1
    return netcode[name]


PADS = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = ToMM(pad.GetDrillSize().x) / 2 + 0.25 + router.HW_MAX + router.SLACK
            c = mm(pad.GetPosition())
            m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= r * r
            g.stamp(RB, m, -1)
            g.stamp(RF, m, -1)
            continue
        L = RF if pad.IsOnLayer(F_Cu) else RB
        lay = F_Cu if L == RF else B_Cu
        n = pad.GetNetname() or f"nc-{fp.GetReference()}-{pad.GetNumber()}"
        ps = pad_poly(pad, lay)
        g.stamp(L, g.poly_mask(ps, INF), code(n))
        PADS.append((fp.GetReference(), pad.GetNumber(), n, L, ps))
# no via under a part's body on the back (switch, connector, clip, chip, button)
for fp in board.GetFootprints():
    if fp.GetReference() in ("SW1", "J1", "U1", "SW2"):
        cy_ = pcbnew.SHAPE_POLY_SET()
        for gi in fp.GraphicalItems():
            if gi.GetLayer() == pcbnew.B_CrtYd:
                gi.TransformShapeToPolygon(cy_, pcbnew.B_CrtYd, 0, ERR, pcbnew.ERROR_OUTSIDE)
        if cy_.OutlineCount():
            bb = cy_.BBox()
            _m = (g.X > ToMM(bb.GetLeft())) & (g.X < ToMM(bb.GetRight())) & (g.Y > ToMM(bb.GetTop())) & (g.Y < ToMM(bb.GetBottom()))
            g.noVia |= _m
            NOVIA_PARTS |= _m

TRACKS, VIAS = [], []          # (layer, a, b, width, net) / ((x, y), net): what goes on the board once routing succeeds


def stamp_track(L, a, b_, w, net):
    g.stamp(L, g.seg_mask(a, b_, w / 2 + INF), code(net))


def stamp_via(c, net):
    m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (VIA_D / 2 + INF) ** 2
    g.stamp(RB, m, code(net))
    g.stamp(RF, m, code(net))


def add_track(L, a, b_, w, net):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(w))
    t.SetLayer(B_Cu if L == RB else F_Cu)
    t.SetNet(nets[net])
    board.Add(t)
    TRACKS.append((L, a, b_, w, net))


def add_via(c, net):
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


# nothing of another net under the switch's metal body on the back
for fp in (sw,):
    cy_ = pcbnew.SHAPE_POLY_SET()
    for gi in fp.GraphicalItems():
        if gi.GetLayer() == pcbnew.B_CrtYd:
            gi.TransformShapeToPolygon(cy_, pcbnew.B_CrtYd, 0, ERR, pcbnew.ERROR_OUTSIDE)
    bb = cy_.BBox()
    m = (g.X > ToMM(bb.GetLeft())) & (g.X < ToMM(bb.GetRight())) & (g.Y > ToMM(bb.GetTop())) & (g.Y < ToMM(bb.GetBottom()))
    g.owner[RB][m & (g.owner[RB] == 0)] = -1


# the clip joins its two + pads itself; this arc under the cell's rim (outside the bare contact disc) makes the board agree
_r = 9.25
_top, _bot = pp(bat, "1", pick=lambda p: p[1]), pp(bat, "1", pick=lambda p: -p[1])
_open = -1 if _closed_dir()[0] > 0 else 1            # run the arc on the open side (left), away from the middle of the board
_arc = [(round(BAT[0] + _open * _r * math.sin(math.radians(a_)), 3), round(BAT[1] - _r * math.cos(math.radians(a_)), 3))
        for a_ in range(0, 181, 10)]
_arc = [(_top[0] + _open * 2.0, _top[1])] + _arc[1:-1] + [(_bot[0] + _open * 2.0, _bot[1])]
for a_, b_ in zip(_arc, _arc[1:]):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a_))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(0.3))
    t.SetLayer(B_Cu)
    t.SetNet(nets["VCELL"])
    board.Add(t)
    TRACKS.append((RB, a_, b_, 0.3, "VCELL"))
    stamp_track(RB, a_, b_, 0.3, "VCELL")

POWER = {"VLOAD": 0.3, "VSAO": 0.3, "VBAT": 0.3, "VCELL": 0.3, "GND": 0.3}
GND_ROUTED = ()      # ground is not routed: it is the back copper, stitched to the front face copper (below)


# Waypoints that steer two programming lines through the room under the chip's body (between its two rows of pins) and
# out of its left end. The chip and the ISP pads are both on the back, so their pin orders run the same way round and
# at least one line has to pass under one of them; without these the greedy router boxes MISO in.
WAYPOINTS = {"MISO": [(141.7, 122.1)], "SCK": [(143.4, 120.9)]}


def targets(net):
    extra = [(RB, (g.X - x) ** 2 + (g.Y - y) ** 2 <= 0.06 ** 2) for x, y in WAYPOINTS.get(net, [])]
    return targets_(net) + extra


def targets_(net):
    if net == "VCELL":          # the lower + pad only; the arc joins the upper one
        return [(L, g.poly_mask(ps, 0)) for ref, num, n, L, ps in PADS if n == "VCELL" and mm(ps.BBox().GetCenter())[1] > BAT[1]]
    return [(L, g.poly_mask(ps, 0)) for ref, num, n, L, ps in PADS if n == net and not (ref == "BT1" and num == "2")
            and not (net == "GND" and ref not in GND_ROUTED)]


def route(net, plan):
    w = POWER.get(net, SIG)
    front_net = net.startswith("NODE_")
    g.cost[RB] = 6.0 if front_net else 1.0          # LED nodes: front ring cheap, back dear; all other nets the other way round
    g.cost[RF] = 1.0 if front_net else 3.0
    paths = router.route_net(g, code(net), targets(net), w, via_cost=40.0 if front_net or net in POWER else 15.0)
    if paths is None:
        return False
    for path in paths:
        segs, vias_ = router.simplify(g, path)
        for L, a_, b_ in segs:
            stamp_track(L, a_, b_, w, net)
            plan.append(("t", L, a_, b_, w, net))
        for c in vias_:
            stamp_via(c, net)
            plan.append(("v", c, net))
    return True


# 1. the LED nodes, on the front ring (fixed once found)
PLAN = []
for net in ["NODE_A", "NODE_B", "NODE_C", "NODE_D"]:
    ok = route(net, PLAN)
    print(f"  {net}: {'ok' if ok else 'FAILED'} at {time.process_time() - router.CPU0:.0f} s CPU", flush=True)
    if not ok:
        raise SystemExit(f"routing failed: {net}")
# 2. the back: a few net orders are tried in turn (bounded by the router's 5-minute cap); the first that routes wins.
#    Two supplies are fenced (FENCE): VLOAD may not ring the chip's top pins, and the cell feed VBAT goes round the outside.
#    The first order routes today; the others are kept as fall-backs if a part is moved. Ground is not routed (see below).
SNAP = g.owner.copy()
FENCE = {
    # the board supply must not ring the chip's top pins
    "VLOAD": (g.X > 139.5) & (g.Y < 123.6) & (g.Y > 111.5),
    # the cell feed goes round the outside: right along under the switch, down the right edge, along the bottom
    "VBAT": (g.X > 115.0) & (g.X < 146.0) & (g.Y > 105.6) & (g.Y < 128.6),
}
SUPPLY = ["VCELL", "VSAO", "VLOAD"]
TRIES = [
    SUPPLY + ["PB3", "PB4", "SCK", "MISO", "MOSI", "RST", "SAO_GPIO2", "VBAT"],
    SUPPLY + ["SCK", "MISO", "MOSI", "RST", "PB3", "PB4", "SAO_GPIO2", "VBAT"],
    SUPPLY + ["SCK", "MISO", "RST", "MOSI", "PB3", "PB4", "SAO_GPIO2", "VBAT"],
    SUPPLY + ["MISO", "SCK", "MOSI", "PB3", "PB4", "RST", "SAO_GPIO2", "VBAT"],
]
if os.environ.get("SLOTH_ORDER"):                         # debugging aid: try one given order of the back nets
    TRIES = [SUPPLY + os.environ["SLOTH_ORDER"].split(",")]
ROUTE_FAIL = None
for k, order in enumerate(TRIES):
    g.owner[:] = SNAP
    plan = []
    fails = []
    try:
        for net in order:
            saved = None
            if net in FENCE:
                saved = g.owner[RB].copy()
                g.owner[RB][FENCE[net] & (g.owner[RB] == 0)] = -1
            ok = route(net, plan)
            if saved is not None:
                keep = g.owner[RB] == code(net)
                g.owner[RB][:] = np.where(keep, g.owner[RB], saved)
            if not ok:
                fails.append(net)
                break
    except RuntimeError as e:
        print("  try", k + 1, ":", e)
        fails.append("(time cap)")
        ROUTE_FAIL = fails
        break
    print(f"  try {k + 1}: {'ok' if not fails else 'failed ' + ','.join(fails)} at {time.process_time() - router.CPU0:.0f} s CPU", flush=True)
    ROUTE_FAIL = fails
    if not fails:
        PLAN += plan
        break
else:
    if os.environ.get("SLOTH_DEBUG"):
        PLAN += plan            # debug: keep the last try's partial routing to look at


def _pt_seg(p_, a, b_):
    ax, ay = a
    bx, by = b_
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p_[0] - ax) * dx + (p_[1] - ay) * dy) / L))
    return math.hypot(p_[0] - ax - t * dx, p_[1] - ay - t * dy)


def prune(plan):
    """Drop track ends that lead nowhere (left behind where a waypoint sat off the final path)."""
    pads = {}
    for ref, num, n, L, ps in PADS:
        pads.setdefault(n, []).append((L, ps))
    while True:
        segs = [it for it in plan if it[0] == "t"]
        vias = [it for it in plan if it[0] == "v"]
        drop = None
        for it in segs:
            _, L, a, b_, w, net = it
            for end in (a, b_):
                on = any(o is not it and o[1] == L and o[5] == net and _pt_seg(end, o[2], o[3]) < 0.01 for o in segs)
                on = on or any(v[2] == net and math.dist(v[1], end) < 0.01 for v in vias)
                on = on or any(Lp == L and ps.Contains(P(*end)) for Lp, ps in pads.get(net, []))
                if not on:
                    drop = it
                    break
            if drop:
                break
        if not drop:
            return plan
        plan.remove(drop)


PLAN = prune(PLAN)
for item in PLAN:
    if item[0] == "t":
        add_track(*item[1:])
    else:
        add_via(*item[1:])
print("vias by net:", dict(collections.Counter(n for _, n in VIAS)))
print("routed; vias:", len(VIAS), "front segments:", sum(1 for t in TRACKS if t[0] == RF), "failed:", ROUTE_FAIL)
if ROUTE_FAIL and not os.environ.get("SLOTH_DEBUG"):
    raise SystemExit(f"routing failed: {ROUTE_FAIL}")

# ---- back copper: ground everywhere, cleared around every pad that is not ground --------------------
gnd = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu) and pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in board.Tracks():
    if t.GetNetname() != "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
cut.Simplify()
gnd.BooleanSubtract(cut)
gnd.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_pads.Append(pad_poly(pad, B_Cu))
for t in board.Tracks():
    if t.GetNetname() == "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
        t.TransformShapeToPolygon(gnd_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_pads.Simplify()

# ---- front: the maker's copper over the whole face side, cleared round the LEDs, tracks, vias and switch pegs ----
def front_copper():
    fcut = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            elif pad.IsOnLayer(F_Cu):
                pad.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for t in board.Tracks():
        if (t.GetClass() == "PCB_VIA" and t.GetNetname() != "GND") or (t.GetClass() != "PCB_VIA" and t.GetLayer() == F_Cu):
            t.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    fcut.Simplify()
    _hit = pcbnew.SHAPE_POLY_SET(fcut)
    _hit.BooleanIntersection(gold)
    assert area_mm2(_hit) < 1e-3, "a front clearance cut reaches into the gold"
    out = pcbnew.SHAPE_POLY_SET(inner)
    out.BooleanSubtract(fcut)
    out.Simplify()
    return out


fcu = front_copper()
_pieces = sorted(range(fcu.OutlineCount()), key=lambda i: -area_mm2(pcbnew.SHAPE_POLY_SET(fcu.Polygon(i))))
fmain = pcbnew.SHAPE_POLY_SET(fcu.Polygon(_pieces[0]))        # the big piece inside the LED ring: the whole face
print(f"front copper: {fcu.OutlineCount()} pieces, the face piece {area_mm2(fmain):.0f} mm2")


def fits(ps, x, y, r):
    c = pcbnew.SHAPE_POLY_SET()
    add_circle(c, P(x, y), r, 24)
    c.BooleanSubtract(ps)
    return area_mm2(c) < 1e-5


def clear_of_gold(x, y):
    c = pcbnew.SHAPE_POLY_SET()
    add_circle(c, P(x, y), VIA_D / 2 + 0.05 + 0.15, 24)          # via pad + mask expansion + mask web
    c.BooleanIntersection(gold)
    return area_mm2(c) < 1e-6


def stitch_spot(piece):
    """A place for a ground via joining this back ground piece to the front face copper, hidden under solder mask."""
    x0, y0, x1, y1 = bbox_mm(piece)
    best = None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for j in range(int((y1 - y0) / 0.25) + 1):
        for i in range(int((x1 - x0) / 0.25) + 1):
            x, y = round(x0 + i * 0.25, 3), round(y0 + j * 0.25, 3)
            gi, gj = g.ij(x, y)
            if not (0 <= gi < g.W and 0 <= gj < g.H) or NOVIA_PARTS[gj, gi] or math.dist((x, y), BAT) < 11.0:
                continue
            d = (x - cx) ** 2 + (y - cy) ** 2
            if best is not None and d >= best[0]:
                continue
            # inside both ground pieces, and with solder mask between it and the gold (0.15 mm web at least)
            if fits(piece, x, y, VIA_D / 2 + 0.05) and fits(fmain, x, y, VIA_D / 2 + 0.05) and clear_of_gold(x, y):
                best = (d, (x, y))
    return best and best[1]


# keep each back ground piece that has a ground pad on it; tie every kept piece (and any piece that can be tied) to the
# front face copper with one tented via, so the scattered ground islands round the chip are all one ground
n_gnd, STITCH = 0, []
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    if area_mm2(piece) < 1.0:
        continue
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    has_pad = area_mm2(both) > 0.005
    spot = stitch_spot(piece)
    if spot:
        add_via(spot, "GND")
        STITCH.append(spot)
    if has_pad or spot:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
    elif area_mm2(piece) > 3:
        print(f"  dropped a back ground piece of {area_mm2(piece):.1f} mm2 near {tuple(round(v, 1) for v in bbox_mm(piece)[:2])}")
print("back ground pieces:", n_gnd, "; ground stitching vias:", STITCH)
fcu = front_copper()                                       # again, now with the stitching vias
for i in range(fcu.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(fcu.Polygon(i))
    joined = STITCH and any(piece.Contains(P(*v)) for v in STITCH)
    if not joined and area_mm2(piece) < 1.0:
        continue                                           # crumbs left between front wires: too small to make, left off
    add_filled(board, piece, F_Cu, nets["GND"] if joined else None)
fmask = pcbnew.SHAPE_POLY_SET(gold)
fmask.BooleanIntersection(body)
add_filled(board, fmask, pcbnew.F_Mask)              # the gold sloth: bare copper, as the maker drew it

# ---- back silkscreen labels ------------------------------------------------------------------------
s1, s4 = pp(sw, "1"), pp(sw, "4")
order = "SAO  OFF  BAT" if s1[0] > s4[0] else "BAT  OFF  SAO"     # as read from the back (mirrored view)
text(order, SWX - 4.0, 106.6, 0.8, 0.12)
text("CR2032 +", BAT[0], 106.4, 0.8, 0.12)
text("ISP", ISP[0] + 4.6, ISP[1], 0.8, 0.12, rot=90)
text("SAO++ rA", 137.2, 135.3, 0.8, 0.12)
for g_ in bat.GraphicalItems():                       # the clip's own silk arrow and "+" land under the cell or off the board
    if g_.GetLayer() == B_SilkS:
        g_.SetLayer(pcbnew.B_Fab)
for fp in (isp,):                                     # the ISP pads' outline runs past the board's curved edge
    for g_ in fp.GraphicalItems():
        if g_.GetLayer() == B_SilkS:
            g_.SetLayer(pcbnew.B_Fab)

# ---- report ---------------------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT if not ROUTE_FAIL else os.path.join(HERE, "_debug.kicad_pcb"), board)
print("saved", OUT)
