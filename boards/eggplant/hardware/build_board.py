#!/usr/bin/env python3
"""Build eggplant.kicad_pcb from the maker's art (hardware/art.json) plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root (art.json comes from hardware/extract_art.py):
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/eggplant/hardware/build_board.py

What it does:
  - takes the maker's outline and his two-sided art (stem and calyx in bare copper, the body under copper with a
    copper-free light stripe, leaf and highlight in silkscreen) and scales all of it up by SCALE (owner rule of
    2026-11-12: scale the whole board rather than leave parts off it)
  - puts every part on the back: the XIAO across the round bottom with its USB-C out of the left-hand side, the SAO
    connector in the upper body turned 45 degrees as the maker had it (so the board leans like the eggplant emoji
    when worn), the switch knob out of the right-hand side of the bulb with the LiPo socket below it, and the maker's
    five two-colour LEDs, each with one resistor per colour
  - routes on the back copper, with tented vias and short links on the front (under the mask, inside the dark body
    copper) only where a line cannot get past another; router.py does this, with hard time and rip-up limits
  - fills the rest of the back with ground copper and makes the maker's front body copper the ground plane, joining
    every back ground piece to it with a tented via
  - keeps his back art and lettering, moving a piece of lettering (unchanged) only where a new part covers it
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import sys
import time
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "eggplant"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
STAGE = os.environ.get("EGG_STAGE", "full")      # "place" stops after placement (for looking at the layout)

SCALE = 1.35            # see README "Why it is 35 % bigger": 1.30 has no room for the switch and LiPo socket together
O = 10.0                # scaling origin: the maker's board's top-left corner in art.json coordinates
CLEAR = 0.30            # copper-to-copper gap cut into the ground copper
EDGE = 0.55             # ground copper stops this far short of the board edge (panel mouse-bite holes reach 0.25 mm in)

ART = json.load(open(os.path.join(HERE, "art.json")))


def S(p):
    return (O + (p[0] - O) * SCALE, O + (p[1] - O) * SCALE)


def polyset(entries):
    """SHAPE_POLY_SET from a list of point lists (art.json), scaled."""
    out = pcbnew.SHAPE_POLY_SET()
    for pts in entries:
        out.BooleanAdd(poly([S(p) for p in pts]))
    out.Simplify()
    return out


def unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


# ---- outline -------------------------------------------------------------------------------------
OL = [S(p) for p in ART["outline"]]
maker = poly(OL)
maker.Simplify()
assert maker.OutlineCount() == 1


def inside(ps, p):
    return ps.Contains(P(*p))


def nearest_edge(p):
    """Closest point of the maker's (scaled) outline to p, and the outward normal there."""
    best = None
    for a, b in zip(OL, OL[1:] + OL[:1]):
        d = (b[0] - a[0], b[1] - a[1])
        L2 = dot(d, d)
        t = max(0.0, min(1.0, dot((p[0] - a[0], p[1] - a[1]), d) / L2)) if L2 else 0.0
        q = add(a, d, t)
        dist = math.dist(p, q)
        if best is None or dist < best[0]:
            best = (dist, q)
    q = best[1]
    n = unit((q[0] - p[0], q[1] - p[1]))
    return q, n


# ---- board and nets --------------------------------------------------------------------------------
board = pcbnew.CreateEmptyBoard()
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


def pads_of(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]


def centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def orient_by(fp, getters):
    """Like orient(), but each want is (function fp -> from point, function fp -> to point, direction)."""
    best = None
    for k in range(720):
        fp.SetOrientationDegrees(k / 2)
        err = sum(1 - dot(unit((g2(fp)[0] - g1(fp)[0], g2(fp)[1] - g1(fp)[1])), unit(d)) for g1, g2, d in getters)
        if best is None or err < best[0]:
            best = (err, k / 2)
    fp.SetOrientationDegrees(best[1])
    assert best[0] < 0.01, f"{fp.GetReference()}: no angle fits ({best[0]:.3f})"
    return best[1]


def pc(num):
    return lambda fp: centroid(pads_of(fp, num))


def fpc(fp):
    return mm(fp.GetPosition())


def pads_inside(fp, ps, margin):
    ok = grown(ps, -margin)
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(ok)
        if off.OutlineCount():
            return False
    return True


def slide(fp, start, d, margin, test=None):
    """Move fp from `start` along direction d (outward) as far as its pads stay `margin` inside the maker's outline."""
    last = None
    for k in range(0, 400):
        p = add(start, d, k * 0.05)
        fp.SetPosition(P(*p))
        if not pads_inside(fp, maker, margin) or (test and not test(fp)):
            break
        last = p
    assert last is not None, f"{fp.GetReference()} does not fit at {start}"
    fp.SetPosition(P(*last))
    return last


# ---- placement ------------------------------------------------------------------------------------
# XIAO: across the round bottom of the eggplant, its USB-C end out of the left-hand side, where the outline runs
# almost straight up and down for the module's whole width (a fit search over every angle: this is the one direction
# that needs no flattening at all). It slides left until its pads are 0.3 mm inside the edge.
USB_DIR = (-1.0, 0.0)
xiao = load("U1", (24.0, 56.0))
orient_by(xiao, [(fpc, lambda f: centroid(pads_of(f, "1") + pads_of(f, "14")), USB_DIR)])
link(xiao, "U1")


def body_corners_inside(fp):
    """The module's own body (21 x 17.8 mm, its fab outline) must sit on the board, not only its pads."""
    c = mm(fp.GetPosition())
    for a in (-1, 1):
        for b in (-1, 1):
            p = add(add(c, USB_DIR, a * 10.48), (-USB_DIR[1], USB_DIR[0]), b * 8.89)
            if not grown(maker, -0.10).Contains(P(*p)):
                return False
    return True


XC = slide(xiao, (24.0, 56.0), USB_DIR, 0.30, body_corners_inside)
X_USB_FACE = 10.48 + 1.51          # the USB-C socket's face, from the module's centre along USB_DIR
print("XIAO centre", [round(v, 2) for v in XC], "angle", xiao.GetOrientationDegrees())

# SAO connector: in the upper body, key slot toward "up when worn". The maker turned his connector 45 degrees so
# the eggplant hangs leaning, like the emoji; worn, his up is the board's up-right diagonal (front view).
KEY_DIR = unit((1, -1))
PIN1_DIR = unit((-1, -1))           # pin 1 (VCC) is to the left of pin 3 when the key is up, as on Mad Cat / Mr. Robot
JC = (25.6, 35.2)
conn = load("J1", JC)
orient_by(conn, [(pc("4"), pc("3"), KEY_DIR), (pc("3"), pc("1"), PIN1_DIR)])
link(conn, "J1")


def edge_mount(ref, near, face_from, face_to, margin, depth):
    """Put a part whose face (direction face_from -> face_to pads) must sit at the board edge nearest `near`."""
    fp = load(ref, near)
    q, n = nearest_edge(near)
    t = (-n[1], n[0])                          # use the chord over the part's length, not the tangent at one point
    q1, _ = nearest_edge(add(q, t, 6.0))
    q2, _ = nearest_edge(add(q, t, -6.0))
    c = unit((q2[0] - q1[0], q2[1] - q1[1]))
    n2 = (c[1], -c[0])
    n = n2 if dot(n2, n) > 0 else (-n2[0], -n2[1])
    orient_by(fp, [(face_from, face_to, n)])
    link(fp, ref)
    pos = slide(fp, add(q, n, -depth - 2.0), n, margin)
    return fp, pos, n


# switch: knob out of the right-hand side of the bulb. The knob points from the switch's pins toward its pegs.
peg = lambda f: centroid([mm(p.GetPosition()) for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH])
sw, SWP, SWN = edge_mount("SW1", (45.5, 62.0), lambda f: centroid([pads_of(f, n)[0] for n in "1234"]), peg, 0.30, 2.0)
# LiPo socket: opening out of the lower right-hand side, below the switch (the bottom of the bulb is kept for the
# maker's credit). The plug goes in from the signal pads toward the hold-down pads.
hold = lambda f: centroid([mm(p.GetPosition()) for p in f.Pads() if p.GetNumber() == ""])
jst, JSTP, JSTN = edge_mount("J2", (42.0, 76.5), lambda f: centroid(pads_of(f, "1") + pads_of(f, "2")), hold, 0.30, 5.0)
print("switch", [round(v, 2) for v in SWP], "LiPo", [round(v, 2) for v in JSTP])


def place2(ref, pos, axis):
    """A two-pad part (resistor) on the back, pad 1 -> pad 2 along `axis`."""
    fp = load(ref, pos)
    orient_by(fp, [(pc("1"), pc("2"), axis)])
    link(fp, ref)
    return fp


# small parts
s2 = pads_of(sw, "2")[0]
R1 = place2("R1", add(s2, (-unit(SWN)[0], -unit(SWN)[1]), 2.6), (-SWN[0], -SWN[1]))   # OFF sense, beside the switch
R2 = place2("R2", (33.8, 47.6), (0, 1))                # SAO GPIO1 -> D7
R3 = place2("R3", (30.5, 44.5), (1, 0))                # SAO GPIO2 -> D6

# the maker's five LEDs, at his positions (scaled) except where a new part now sits, anodes toward the given
# direction (on the back the blue anode, pad 1, then falls on a fixed side); each with its blue (330) and red (1.3 k)
# resistor standing off its anodes
LEDS = {  # ref: (maker's name, position, anode direction)
    "D1": ("LED1", (34.0, 27.6), (-1, 0)),
    "D2": ("LED2", S(ART["leds"]["LED2"]), (0, 1)),
    "D3": ("LED3", (36.5, 53.2), (0, -1)),
    "D4": ("LED4", (16.0, 73.0), (0, -1)),
    "D5": ("LED5", (22.0, 79.0), (0, -1)),
}
LEDFP = {}
for k, (ref, (name, pos, adir)) in enumerate(LEDS.items()):
    fp = load(ref, pos)
    orient_by(fp, [(lambda f: centroid(pads_of(f, "3") + pads_of(f, "4")), lambda f: centroid(pads_of(f, "1") + pads_of(f, "2")), adir)])
    link(fp, ref)
    LEDFP[ref] = fp
    a = unit(adir)
    s = unit((pc("1")(fp)[0] - pc("2")(fp)[0], pc("1")(fp)[1] - pc("2")(fp)[1]))      # toward the blue anode
    an = centroid(pads_of(fp, "1") + pads_of(fp, "2"))
    rb = place2(f"R{4 + k}", add(add(an, a, 2.6), s, 1.15), (-a[0], -a[1]))     # blue: 330 ohm
    rr = place2(f"R{9 + k}", add(add(an, a, 2.6), s, -1.15), (-a[0], -a[1]))    # red: 1.3 k
    print(ref, "(maker's", name + ")", [round(v, 2) for v in pos])

# ---- the board outline: the maker's, with two shallow flats -------------------------------------------
# where the USB-C socket's face and the switch knob's face meet the edge, the outline is cut flat (as on Mr. Robot)
SW_FACE = 2.1                                           # switch: the board edge belongs 2.1 mm from its origin
body = pcbnew.SHAPE_POLY_SET(maker)


def cut_beyond(origin, d, dist, half):
    """Remove what lies farther than dist from `origin` in direction d, within `half` mm either side of the line."""
    n = (-d[1], d[0])
    c = add(origin, d, dist)
    big = [add(c, n, half), add(add(c, n, half), d, 20), add(add(c, n, -half), d, 20), add(c, n, -half)]
    before = area_mm2(body)
    body.BooleanSubtract(poly(big))
    body.Simplify()
    return before - area_mm2(body)


cut_usb = cut_beyond(XC, USB_DIR, X_USB_FACE, 5.0)
_pins = centroid([pads_of(sw, n)[0] for n in "1234"])
KNOB = unit((peg(sw)[0] - _pins[0], peg(sw)[1] - _pins[1]))        # the switch's own axis (SWN is within 0.25 deg)
cut_sw = cut_beyond(SWP, KNOB, SW_FACE, 6.5)
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm; flats cut off {cut_usb:.2f} mm2 (USB) and {cut_sw:.2f} mm2 (switch)")
inner = grown(body, -EDGE)
FPS = list(board.GetFootprints())
for fp in FPS:
    if not pads_inside(fp, body, 0.25):
        for pad in fp.Pads():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and not pad_poly(pad, B_Cu).IsEmpty():
                o = pad_poly(pad, B_Cu)
                o.BooleanSubtract(grown(body, -0.25))
                if o.OutlineCount():
                    print("  too close:", fp.GetReference(), pad.GetNumber(), mm(pad.GetPosition()), round(area_mm2(o), 4))
        raise AssertionError(f"{fp.GetReference()} has a pad closer than 0.25 mm to the edge")

if STAGE == "place":
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
    pcbnew.SaveBoard(OUT, board)
    print("saved placement only")
    sys.exit(0)

# ---- the maker's art, scaled ------------------------------------------------------------------------
def art_set(side, key):
    return polyset(ART[side][key])


def body_copper(side):
    """The maker's ground pour on one side: his pour outline minus his copper keep-out (the light stripe)."""
    ps = art_set(side, "body")
    ps.BooleanSubtract(art_set(side, "restrict"))
    ps.BooleanIntersection(inner)
    ps.Simplify()
    return ps


F_BODY = body_copper("front")          # front: becomes the ground plane, under solder mask, as the maker had it
F_STEM = art_set("front", "stem")      # front: stem and calyx, bare gold (mask opening), no net
B_STEM = art_set("back", "stem")       # back: the same, kept as art where no part needs the room
B_STRIPE = art_set("back", "restrict")  # back: the light stripe, kept free of copper as on the original
F_STRIPE = art_set("front", "restrict")

# ---- routing (back copper first; tented vias and short front links only where a line cannot get past) ---------
from router import Router  # noqa: E402

CLASSES = {"sig": (0.10, 0.20), "pwr": (0.15, 0.20)}         # (half width, clearance kept from other nets)
TABS = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))["tabs"] if os.path.exists(
    os.path.join(HERE, "..", "production", "panel.json")) else []
rt = Router(bx0 - 1, by0 - 1, bx1 + 1, by1 + 1, CLASSES)


def outlines(ps):
    ps = pcbnew.SHAPE_POLY_SET(ps)
    ps.Simplify()
    return [[mm(ps.COutline(i).CPoint(k)) for k in range(ps.COutline(i).PointCount())] for i in range(ps.OutlineCount())]


def outline_pts(ps):
    return outlines(ps)[0]


tab_keep = pcbnew.SHAPE_POLY_SET()
for t_ in TABS:                                                # nothing near a panel tab
    add_circle(tab_keep, P(*t_["near"]), 3.0)
back_area = grown(body, -0.65)                                 # track centres 0.65 mm in: copper 0.5 mm from the edge
back_area.BooleanSubtract(tab_keep)
back_area.BooleanSubtract(grown(B_STEM, 0.45))                 # keep the maker's back stem and calyx art whole
back_area.Simplify()
front_area = grown(F_BODY, -0.45)                              # front links only inside the dark ground plane
front_area.BooleanSubtract(tab_keep)
front_area.Simplify()
rt.set_area(1, outlines(back_area))
rt.set_area(0, outlines(front_area))

NETID = {}
ROUTED_NETS = sorted({n for d in PADNETS.values() for n in d.values()} - {"GND"})
for i, n in enumerate(ROUTED_NETS):
    NETID[n] = i
NETID["GND"] = len(NETID)
ALLC = list(rt.classes)

for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = ToMM(pad.GetDrillSize().x) / 2
            shapes = {}
            for cl in ALLC:
                ps = pcbnew.SHAPE_POLY_SET()
                add_circle(ps, pad.GetPosition(), r + 0.25 + rt.grow_of(cl))
                shapes[cl] = outline_pts(ps)
            rt.add_fixed((0, 1), shapes, -2)
            continue
        if not pad.IsOnLayer(B_Cu):
            continue
        net = pad.GetNetname()
        nid = NETID.get(net, -2)          # unconnected pads and hold-down tabs block everyone
        rt.add_fixed((1,), {cl: outline_pts(pad_poly(pad, B_Cu, rt.grow_of(cl))) for cl in ALLC}, nid)
        if net in NETID and net != "GND":
            rt.add_target(NETID[net], fp.GetReference() + "." + pad.GetNumber(), 1, outline_pts(pad_poly(pad, B_Cu)))
for g in xiao.GraphicalItems():           # the module's own underside test pads: no copper of ours under them
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        shapes = {}
        for cl in ALLC:
            ps = pcbnew.SHAPE_POLY_SET()
            add_circle(ps, g.GetCenter(), ToMM(g.GetRadius()) + 0.15 + rt.grow_of(cl) - rt.classes[cl][1])
            shapes[cl] = outline_pts(ps)
        rt.add_fixed((1,), shapes, -2)

for fp in FPS:                            # no via under a part's body (the XIAO and the connectors sit flat on them)
    if fp.GetReference() in ("U1", "SW1", "J2") or fp.GetReference().startswith("D"):
        bb = fp.GetBoundingBox(False)
        x0_, y0_, x1_, y1_ = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
        rt.block_vias([(x0_, y0_), (x1_, y0_), (x1_, y1_), (x0_, y1_)])

ORDER = [("BAT+", "pwr"), ("V3V3", "pwr"), ("VSAO", "pwr"), ("OFF_SW", "sig"), ("OFF_SENSE", "sig"),
         ("SDA", "sig"), ("SCL", "sig"), ("SAO_GPIO2", "sig"), ("D6_TX", "sig"), ("SAO_GPIO1", "sig"), ("D7_RX", "sig")]
LEDNETS = [(f"BLUE{k}", "sig") for k in range(1, 6)] + [(f"RED{k}", "sig") for k in range(1, 6)]
LEDNETS += [("LED_RED", "sig"), ("LED_BLUE", "sig")]
ORDER = LEDNETS + ORDER if os.environ.get("EGG_ORDER", "leds-first") == "leds-first" else ORDER + LEDNETS
assert sorted(n for n, _ in ORDER) == ROUTED_NETS, set(ROUTED_NETS) ^ {n for n, _ in ORDER}
NAME = {v: k for k, v in NETID.items()}
routed, vias = rt.route_all([(NETID[n], c) for n, c in ORDER], NAME, strict=(STAGE != "route"))
TRACKS, VIAS = [], []
for nid, segs in routed.items():
    for L, pts, cl in segs:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a))
            t.SetEnd(P(*b))
            t.SetWidth(FromMM(2 * CLASSES[cl][0]))
            t.SetLayer(B_Cu if L == 1 else F_Cu)
            t.SetNet(nets[NAME[nid]])
            board.Add(t)
            TRACKS.append((t, NAME[nid]))
VIA_D, VIA_DRILL = 0.6, 0.3


def add_via(x, y, net):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    v.SetWidth(FromMM(VIA_D))
    v.SetDrill(FromMM(VIA_DRILL))
    v.SetNet(nets[net])
    board.Add(v)
    VIAS.append((v, net))
    return v


for nid, vl in vias.items():
    for x, y in vl:
        add_via(x, y, NAME[nid])
print("tracks", len(TRACKS), "signal vias", len(VIAS), "front track pieces", sum(1 for t, _ in TRACKS if t.GetLayer() == F_Cu))
for nid, vl in vias.items():
    print("  vias on", NAME[nid], vl)

if STAGE == "route":
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
    pcbnew.SaveBoard(OUT, board)
    sys.exit(0)

# ---- copper: back ground fill, front ground plane, stitching vias ------------------------------------
gnd_code = nets["GND"].GetNetCode()
pegs = pcbnew.SHAPE_POLY_SET()                                  # the switch's two peg holes, both sides
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)


def other_net_copper(layer):
    """Everything on `layer` that is not ground, grown by the ground clearance."""
    cut = pcbnew.SHAPE_POLY_SET()
    for fp in FPS:
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            if pad.IsOnLayer(layer) and pad.GetNetCode() != gnd_code:
                pad.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for t, net in TRACKS:
        if t.GetLayer() == layer and net != "GND":
            t.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for v, net in VIAS:
        if net != "GND":
            add_circle(cut, v.GetPosition(), VIA_D / 2 + CLEAR)
    cut.BooleanAdd(pegs)
    cut.Simplify()
    return cut


# back: ground everywhere else, except the maker's light stripe and his stem / calyx art
b_gnd = pcbnew.SHAPE_POLY_SET(inner)
b_gnd.BooleanSubtract(other_net_copper(B_Cu))
for g in xiao.GraphicalItems():                                  # the module's own underside test pads
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        c_ = pcbnew.SHAPE_POLY_SET()
        add_circle(c_, g.GetCenter(), ToMM(g.GetRadius()) + 0.15)
        b_gnd.BooleanSubtract(c_)
# The maker kept his light stripe free of copper on both sides. The front stripe is kept whole. On the back (now the
# parts side, where nobody sees it) it is ground copper like the rest: the LEDs and the XIAO in it need the ground.
stripe_cut = pcbnew.SHAPE_POLY_SET()
b_gnd.BooleanSubtract(stripe_cut)
tab_ring = pcbnew.SHAPE_POLY_SET(tab_keep)        # at a panel tab, art copper stays as far back as the ground does
tab_ring.BooleanSubtract(inner)
tab_ring.Simplify()
b_stem_cu = pcbnew.SHAPE_POLY_SET(B_STEM)
b_stem_cu.BooleanIntersection(grown(body, -0.3))
b_stem_cu.BooleanSubtract(tab_ring)
b_stem_cu.Simplify()
b_gnd.BooleanSubtract(grown(b_stem_cu, CLEAR))
b_gnd.Simplify()

# front: the maker's body pour becomes the ground plane; his stem and calyx stay bare gold, not connected
f_stem_cu = pcbnew.SHAPE_POLY_SET(F_STEM)
f_stem_cu.BooleanIntersection(grown(body, -0.3))
f_stem_cu.BooleanSubtract(tab_ring)
f_stem_cu.BooleanSubtract(pegs)
f_stem_cu.Simplify()
f_gnd = pcbnew.SHAPE_POLY_SET(F_BODY)
f_gnd.BooleanSubtract(other_net_copper(F_Cu))
f_gnd.BooleanSubtract(grown(f_stem_cu, CLEAR))
f_gnd.Simplify()
f_pieces = sorted((pcbnew.SHAPE_POLY_SET(f_gnd.Polygon(i)) for i in range(f_gnd.OutlineCount())), key=lambda p: -area_mm2(p))
F_MAIN = f_pieces[0]
print("front ground plane:", round(area_mm2(F_MAIN), 1), "mm2; other front body pieces (kept as plain art):",
      [round(area_mm2(p), 2) for p in f_pieces[1:]])

gnd_pads = []
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_pads.append((fp.GetReference() + "." + pad.GetNumber(), pad_poly(pad, B_Cu)))
via_spot = grown(F_MAIN, -(VIA_D / 2 + 0.05))                  # where a ground via can reach the front plane
blocked = pcbnew.SHAPE_POLY_SET()       # not under the switch, the LiPo socket or an LED (under the XIAO and the
for fp in FPS:                          # connector's plastic shroud is fine for a tented via, clear of their pads)
    if fp.GetReference() in ("SW1", "J2") or fp.GetReference().startswith("D"):
        bb = fp.GetBoundingBox(False)
        blocked.BooleanAdd(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                                 (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
via_spot.BooleanSubtract(blocked)
via_spot.Simplify()
n_gnd = n_drop = 0
stitch = []
for i in range(b_gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(b_gnd.Polygon(i))
    has_pad = []
    for name, pp_ in gnd_pads:
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(pp_)
        if area_mm2(both) > 0.005:
            has_pad.append(name)
    if not has_pad and area_mm2(piece) < 2.0:
        n_drop += 1
        continue
    spot = grown(piece, -(VIA_D / 2 + 0.05))
    spot.BooleanIntersection(via_spot)
    spot.Simplify()
    if spot.OutlineCount() == 0:
        if has_pad:
            print("  WARNING: ground piece with", has_pad, "has no room for a via to the front plane")
        else:
            n_drop += 1
            continue
    else:
        big = max(range(spot.OutlineCount()), key=lambda k: area_mm2(pcbnew.SHAPE_POLY_SET(spot.Polygon(k))))
        c = spot.COutline(big)
        # a point well inside: the centroid of the piece's vertices, if inside, else its first vertex
        cx_ = sum(ToMM(c.CPoint(k).x) for k in range(c.PointCount())) / c.PointCount()
        cy_ = sum(ToMM(c.CPoint(k).y) for k in range(c.PointCount())) / c.PointCount()
        if not spot.Contains(P(cx_, cy_)):
            cx_, cy_ = ToMM(c.CPoint(0).x), ToMM(c.CPoint(0).y)
        stitch.append((round(cx_, 3), round(cy_, 3)))
    add_filled(board, piece, B_Cu, nets["GND"])
    n_gnd += 1
for x, y in stitch:
    add_via(x, y, "GND")
print("back ground pieces", n_gnd, "scraps dropped", n_drop, "stitching vias", len(stitch))
add_filled(board, F_MAIN, F_Cu, nets["GND"])
for p in f_pieces[1:]:
    if area_mm2(p) > 0.05:
        add_filled(board, p, F_Cu)
add_filled(board, f_stem_cu, F_Cu)
add_filled(board, b_stem_cu, B_Cu)

# ---- solder mask and silkscreen art -------------------------------------------------------------------
f_mask = art_set("front", "mask")
f_mask.BooleanIntersection(f_stem_cu)                           # bare gold only where there is copper under it
add_filled(board, f_mask, pcbnew.F_Mask)
b_mask = art_set("back", "mask")
b_mask.BooleanIntersection(grown(b_stem_cu, -0.05))
b_mask.Simplify()
add_filled(board, b_mask, pcbnew.B_Mask)
f_silk = grown(art_set("front", "silk"), 0.05)                  # Eagle drew these polygons with a 0.1 mm outline
f_silk.BooleanIntersection(grown(body, -0.15))
f_silk.BooleanSubtract(pegs)
f_silk.Simplify()
add_filled(board, f_silk, pcbnew.F_SilkS)
b_silk = grown(art_set("back", "silk"), 0.05)
b_silk.BooleanIntersection(grown(body, -0.15))
pads_keep = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            pad.TransformShapeToPolygon(pads_keep, B_Cu, FromMM(0.15), ERR, pcbnew.ERROR_OUTSIDE)
for v, _ in VIAS:
    add_circle(pads_keep, v.GetPosition(), VIA_D / 2 + 0.1)
b_silk.BooleanSubtract(pads_keep)
b_silk.BooleanSubtract(grown(b_mask, 0.1))
b_silk.Simplify()
add_filled(board, b_silk, B_SilkS)
print("art: front stem", round(area_mm2(f_stem_cu), 1), "mm2, back stem", round(area_mm2(b_stem_cu), 1), "mm2")

# ---- the maker's lettering on the back: his three texts and his 16 short strokes, as he set them --------------
# Eagle "MR45": mirrored (it is on his bottom side) and turned 45 degrees. His vector font at 8 % stroke; sizes scale
# with the board. Positions: see CREDIT_AT below (moved only where a new part now covers the spot).
TEXT_ANGLE = float(os.environ.get("EGG_TA", "-45"))
CREDIT_AT = {0: None, 1: None, 2: None}       # None = the maker's own position (scaled)
# Eagle -> KiCad for mirrored text: angle 45 -> -45, and his "top" anchor becomes KiCad's "bottom" (checked: this
# is the one setting that puts his three-line credit back inside the outline where he drew it, reading the right
# way up from the back when the board hangs at his 45 degrees)
JUST = {"top-left": (pcbnew.GR_TEXT_H_ALIGN_LEFT, pcbnew.GR_TEXT_V_ALIGN_BOTTOM),
        "bottom-center": (pcbnew.GR_TEXT_H_ALIGN_CENTER, pcbnew.GR_TEXT_V_ALIGN_TOP),
        "bottom-left": (pcbnew.GR_TEXT_H_ALIGN_LEFT, pcbnew.GR_TEXT_V_ALIGN_TOP)}
MAKER_TEXTS = []
for k, tx in enumerate(ART["back_texts"]):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(tx["text"])
    t.SetLayer(B_SilkS)
    at = CREDIT_AT[k] or S(tx["at"])
    t.SetPosition(P(*at))
    size = tx["size"] * SCALE
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * tx["ratio"] / 100))
    ang = float(tx["rot"].lstrip("SMR"))
    t.SetTextAngleDegrees(TEXT_ANGLE if ang == 45 else TEXT_ANGLE + 180)
    t.SetMirrored(True)
    h, v = JUST[tx["align"]]
    t.SetHorizJustify(h)
    t.SetVertJustify(v)
    board.Add(t)
    MAKER_TEXTS.append(t)
for a, b, w in ART["back_strokes"]:
    s_ = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s_.SetStart(P(*S(a)))
    s_.SetEnd(P(*S(b)))
    s_.SetWidth(FromMM(w * SCALE))
    s_.SetLayer(B_SilkS)
    board.Add(s_)

# Where a new part now covers the maker's lettering, the lettering moves (unchanged) to the nearest spot where it is
# visible: on the board, off every part's body, pad and via, and off his other back art. His 16 strokes travel with
# the base64 line they sit on.
STROKES = [d for d in board.GetDrawings() if d.GetClass() == "PCB_SHAPE" and d.GetLayer() == B_SilkS
           and d.GetShape() == pcbnew.SHAPE_T_SEGMENT]
keep_txt = pcbnew.SHAPE_POLY_SET()
for fp in FPS:
    fp.BuildCourtyardCaches()
    keep_txt.BooleanAdd(grown(fp.GetCourtyard(pcbnew.B_CrtYd), 0.2))
keep_txt.BooleanAdd(grown(pads_keep, 0.1))
keep_txt.BooleanAdd(grown(b_silk, 0.3))
keep_txt.BooleanAdd(grown(b_stem_cu, 0.2))
keep_txt.Simplify()
ok_area = grown(body, -0.4)


def shape_of(items):
    """The ink itself (each stroke of each letter), grown by 0.1 mm, not the text's whole box."""
    ps = pcbnew.SHAPE_POLY_SET()
    for it in items:
        if it.GetClass() == "PCB_TEXT":
            it.TransformTextToPolySet(ps, FromMM(0.1), ERR, pcbnew.ERROR_OUTSIDE)
        else:
            it.TransformShapeToPolygon(ps, B_SilkS, FromMM(0.1), ERR, pcbnew.ERROR_OUTSIDE)
    ps.Simplify()
    return ps


def fits_here(ps):
    out = pcbnew.SHAPE_POLY_SET(ps)
    out.BooleanSubtract(ok_area)
    if area_mm2(out) > 1e-4:
        return False
    hit = pcbnew.SHAPE_POLY_SET(ps)
    hit.BooleanIntersection(keep_txt)
    return area_mm2(hit) < 1e-4


GROUPS = [("credit", [MAKER_TEXTS[0]], 20), ("krux was here", [MAKER_TEXTS[2]], 20), ("base64 line and strokes", [MAKER_TEXTS[1]] + STROKES, 15)]
MOVED = {}
for name, items, reach in GROUPS:
    base = shape_of(items)
    best = None
    for r10 in range(0, reach * 10, 2):
        r = r10 / 10
        steps = max(1, int(2 * math.pi * r / 0.5))
        for k in range(steps):
            dx, dy = r * math.cos(2 * math.pi * k / steps), r * math.sin(2 * math.pi * k / steps)
            ps = pcbnew.SHAPE_POLY_SET(base)
            ps.Move(P(dx, dy))
            if fits_here(ps):
                best = (dx, dy)
                break
        if best:
            break
    if not best:
        out_ = pcbnew.SHAPE_POLY_SET(base); out_.BooleanSubtract(ok_area)
        hit_ = pcbnew.SHAPE_POLY_SET(base); hit_.BooleanIntersection(keep_txt)
        print("   at his spot: off-board", round(area_mm2(out_), 3), "mm2, on parts/art", round(area_mm2(hit_), 3), "mm2 at",
              [round(v, 1) for v in bbox_mm(hit_)] if hit_.OutlineCount() else "-", "bbox", [round(v, 1) for v in bbox_mm(base)])
        print(f"  NO visible spot for the maker's {name}: left where he put it")
        MOVED[name] = None
        continue
    for it in items:
        it.Move(P(*best))
    keep_txt.BooleanAdd(grown(shape_of(items), 0.3))
    MOVED[name] = round(math.hypot(*best), 2)
print("maker's lettering moved by (mm):", MOVED)

# ---- SAO++ labels on the back: each put at the nearest free spot to where it belongs, turned like the maker's
# lettering so it reads level when the board hangs at his 45 degrees
def label(txt, near, size=0.8, reach=8.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(0.15))
    t.SetTextAngleDegrees(TEXT_ANGLE)
    t.SetMirrored(True)
    t.SetPosition(P(*near))
    board.Add(t)
    base = shape_of([t])
    for r10 in range(0, int(reach * 10), 3):
        r = r10 / 10
        steps = max(1, int(2 * math.pi * r / 0.5))
        for k in range(steps):
            d = (r * math.cos(2 * math.pi * k / steps), r * math.sin(2 * math.pi * k / steps))
            ps = pcbnew.SHAPE_POLY_SET(base)
            ps.Move(P(*d))
            if fits_here(ps):
                t.Move(P(*d))
                keep_txt.BooleanAdd(grown(ps, 0.25))
                return t
    raise AssertionError(f"no room for the label {txt!r} near {near}")


s1_, s4_ = pads_of(sw, "1")[0], pads_of(sw, "4")[0]
along = unit((s4_[0] - s1_[0], s4_[1] - s1_[1]))
inward = (-SWN[0], -SWN[1])
label("SAO", add(add(s1_, along, -3.2), inward, 1.0), 0.8, 15)
label("USB", add(add(s4_, along, 3.2), inward, 1.0), 0.8, 15)
jp, jn = pads_of(jst, "1")[0], pads_of(jst, "2")[0]
jd = unit((jn[0] - jp[0], jn[1] - jp[1]))
label("+", add(jp, jd, -1.6), 1.0)
label("-", add(jn, jd, 1.6), 1.0)
label("LiPo", add(JSTP, (-JSTN[0], -JSTN[1]), 6.5), 0.8, 15)
label("1", add(pads_of(conn, "1")[0], unit((-1, -1)), 3.4), 1.0)
label("EGGPLANT rA", (22.0, 44.0), 0.8, 30)
label("SAO++", (22.0, 46.0), 0.8, 30)
label("NO USB", (37.0, 58.0), 0.8, 30)
label("ON SAO", (37.0, 59.5), 0.8, 30)

# ---- design settings, title, save ----------------------------------------------------------------------
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
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
