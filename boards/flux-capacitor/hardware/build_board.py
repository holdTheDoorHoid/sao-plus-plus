#!/usr/bin/env python3
"""Build flux-capacitor.kicad_pcb from the maker's artwork (art/art.json), scaled up, plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/flux-capacitor/hardware/build_board.py

The maker's board is 25.4 x 30.47 mm. The SAO connector, the CR2032 clip and the switch do not fit on it together
(see README), so by the owner's rule of 2026-11-11 the whole board is scaled up uniformly: outline, Y artwork, warning
text, bare-copper cables, electrode holes, LED positions and the maker's credit, all by SCALE about the top-left corner.
Parts keep their real sizes. What this script adds:
  front  - the maker's nine LEDs, facing forward where he had them (they are the art), the maker's ground copper with
           the three bare cables, and the front half of a two-layer route (tented vias, short tracks under the mask)
  back   - the SAO connector, the SAO / OFF / BAT switch, the CR2032 clip and its series diode, the maker's ATtiny,
           ISP pads and three resistors, a 100 nF capacitor; ground copper everywhere else
Coordinates are millimetres in KiCad's front view of the new board (x grows right, y grows down).
"""
import collections
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "flux-capacitor"
SCALE = float(os.environ.get("FLUX_SCALE", "1.35"))
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))

CLEAR = 0.30        # copper-to-copper gap cut into the ground and art copper
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20
VIA_D, VIA_HOLE = 0.6, 0.3


def S(x, y):
    """Maker's coordinates (art.json, top-left corner at 100, 100) -> scaled board."""
    return (round(100 + (x - 100) * SCALE, 4), round(100 + (y - 100) * SCALE, 4))


def stadium(a, b, r, n=24):
    """Polygon of a round-ended stroke from a to b, half-width r (mm)."""
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    pts = []
    for c_, a0 in ((b, ang - math.pi / 2), (a, ang + math.pi / 2)):
        for k in range(n + 1):
            t = a0 + math.pi * k / n
            pts.append((c_[0] + r * math.cos(t), c_[1] + r * math.sin(t)))
    return poly(pts)


# ---- outline and art ----------------------------------------------------------------------------
body = poly([S(*p_) for p_ in ART["outline"]])
bx0, by0, bx1, by1 = bbox_mm(body)
W, H = bx1 - bx0, by1 - by0
CX = (bx0 + bx1) / 2
print(f"scale {SCALE}: board {W:.2f} x {H:.2f} mm (maker's 25.40 x 30.47)")

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)

art_silk = pcbnew.SHAPE_POLY_SET()
for s_ in ART["front_silk"]:                         # filled polygon drawn with a round stroke, as Eagle does
    art_silk.BooleanAdd(grown(poly([S(*p_) for p_ in s_["pts"]]), s_["stroke"] * SCALE / 2))
art_mask = pcbnew.SHAPE_POLY_SET()                   # the bare copper cables
for m_ in ART["front_mask_open"]:
    pts = [S(*p_) for p_ in m_["pts"]]
    for a_, b_ in zip(pts, pts[1:]):
        art_mask.BooleanAdd(stadium(a_, b_, m_["width"] * SCALE / 2))
art_mask.Simplify()

# ---- the circuit (shared with the schematic generator) ------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p_["ref"]: p_ for p_ in CIRCUIT["parts"]}
PADNETS = {r: p_.get("nets", {}) for r, p_ in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p_["symbol"]][5]} for r, p_ in PARTS.items()}
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
            net = f"unconnected-({ref}-{PINNAMES[ref][num]}-Pad{num})"
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def place(ref, pos, want, back=True):
    """Place a part (on the back unless told otherwise) at the right-angle rotation that puts pad want[0] nearest want[1]."""
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
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = min(math.dist(mm(p_.GetPosition()), want[1]) for p_ in fp.Pads() if p_.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num):
    return [mm(p_.GetPosition()) for p_ in fp.Pads() if p_.GetNumber() == num][0]


# ---- placement ----------------------------------------------------------------------------------
# front: the maker's nine LEDs, each centred where he had it (scaled), anode the same way round
led = {}
for k in range(1, 10):
    v = ART["leds"][f"L{k}"]
    c = S(*v["centre"])
    dx, dy = v["anode_dir"]
    led[k] = place(f"D{k}", c, ("2", (c[0] + 1.4 * dx, c[1] + 1.4 * dy)), back=False)   # stock 1206: pads 2.8 mm apart

elec = [S(*e_["at"]) for e_ in ART["electrodes"]]
EL_D = ART["electrodes"][0]["diameter"] * SCALE
EL_HOLE = ART["electrodes"][0]["drill"] * SCALE
el_tl = min(elec, key=lambda q: q[0] + q[1])
el_tr = max(elec, key=lambda q: q[0] - q[1])

# connector: top centre, 3 mm from the top edge, key slot up, pin 1 (VCC) top-left in front view as on Mad Cat
CONN = (round(CX, 2), round(by0 + 3.0 + 5.6, 2))
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))

# coin cell: bottom centre, its edge 0.6 mm inside the bottom edge; closed end up (toward the connector), so the cell
# slides in from the bottom edge
BAT = (round(CX, 2), round(by1 - 0.6 - 10.0, 2))
bat = place("BT1", BAT, ("1", (BAT[0] - 10.5, BAT[1])))


def _closed_dir():
    fab = [g_ for g_ in bat.GraphicalItems() if g_.GetLayer() == pcbnew.B_Fab and g_.GetShape() == pcbnew.SHAPE_T_RECT]
    return ToMM(fab[0].GetBoundingBox().GetCenter().y) - BAT[1]


if _closed_dir() > 0:
    bat.SetOrientationDegrees(bat.GetOrientationDegrees() + 180)
assert _closed_dir() < -3, _closed_dir()

# switch: left edge, knob out to the left, below the top-left electrode; pin 1 (badge) down, pin 4 (cell) up
SW_FACE = bx0 + 0.7                                   # body face 0.7 mm inside the edge: the knob sticks out 0.8 mm, shell tabs 0.52 mm from the edge
SWY = round(el_tl[1] + EL_D / 2 + 0.35 + 5.92, 2)
sw = place("SW1", (SW_FACE + 1.65, SWY), ("1", (SW_FACE + 1.65 + 1.43, SWY + 3.0)))   # on the back with the knob left, pin 1 is the lower end

# chip: right column below the top-right electrode; pins 5-8 face the connector
U1_C = (round(bx1 - 0.55 - 2.3, 2), round(el_tr[1] + EL_D / 2 + 0.4 + 4.5, 2))
u1 = place("U1", U1_C, ("8", (U1_C[0] + 1.905, U1_C[1] - 3.3528)))      # on the back: pin 8 top-right in front view
# ISP pads: left column under the switch
ISP = (round(bx0 + 0.55 + 2.25, 2), round(SWY + 5.92 + 3.75, 2))
isp = place("JP1", ISP, ("P$1", (ISP[0] + 1.27, ISP[1] - 2.54)))

# the strip between the connector and the clip: three ring resistors and the capacitor; the diode by the switch
STRIP = round(BAT[1] - 11.53 - 0.95, 2)              # 0603 keep-clear boxes just above the clip's
RSTRIP = round(BAT[1] - 11.53 - 1.65, 2)             # the resistors stand upright: chip side up, ring side down
res = {}
for k, x in zip((1, 2, 3), (CX + 1.6, CX + 4.0, CX + 6.4)):
    res[k] = place(f"R{k}", (x, RSTRIP), ("1", (x, RSTRIP - 0.825)))
c1 = place("C1", (CX - 3.0, STRIP), ("1", (CX - 3.0 + 0.825, STRIP)))
D10_C = (round(bx0 + 6.6, 2), round(pp(sw, "4")[1] + 0.3, 2))       # beside the switch's cell end, out of the crowded corner
d10 = place("D10", D10_C, ("2", (D10_C[0], D10_C[1] + 0.7)))        # anode (cell side) down

_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, F_Cu if pad.IsOnLayer(F_Cu) else B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the edge"

if os.environ.get("FLUX_PLACE_ONLY"):
    pcbnew.SaveBoard(OUT, board)
    print("placement only, saved")
    sys.exit(0)

# ---- the maker's three electrodes: big ground vias at the ends of the Y, bare on the front as he drew them ------------
ELEC_VIAS = []
for c in elec:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c))
    v.SetDrill(FromMM(EL_HOLE))
    v.SetWidth(FromMM(EL_D))
    v.SetNet(nets["GND"])
    if hasattr(v, "SetFrontTentingMode"):
        v.SetFrontTentingMode(pcbnew.TENTING_MODE_NOT_TENTED)
        v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    ELEC_VIAS.append(v)


# ---- text helpers ---------------------------------------------------------------------------------
def make_text(txt, layer, size, thick, mirrored=False, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetMirrored(mirrored)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(0, 0))
    board.Add(t)
    return t


def fit_box(t, x0, y0, x1, y1):
    """Stretch the text's width so its box matches (x0..x1 along the reading direction) and move it into the box."""
    bb = t.GetBoundingBox()
    horiz = abs(t.GetTextAngleDegrees()) % 180 == 0
    have = ToMM(bb.GetWidth() if horiz else bb.GetHeight())
    want = (x1 - x0) if horiz else (y1 - y0)
    sz = t.GetTextSize()
    t.SetTextSize(VECTOR2I(int(sz.x * want / have), sz.y))
    bb = t.GetBoundingBox()
    t.Move(VECTOR2I(FromMM((x0 + x1) / 2) - bb.GetCenter().x, FromMM((y0 + y1) / 2) - bb.GetCenter().y))
    return t


# The maker's lettering, in Eagle's vector font: rebuilt here in KiCad's stroke font at the same height (scaled),
# the same stroke (8 % of the height, Eagle's default), from the same start point. Eagle's font is a little wider
# than KiCad's; each line is stretched so it ends where his did. The three front lines are centred on the board in his
# file (each starts as far from the centre line as it ends), so they end at the mirror of their start.
TEXT_BOXES = []          # (side, (x0, y0, x1, y1)) for keeping tracks and vias off the lettering
for tx in ART["texts"]:
    h = tx["size"] * SCALE
    ax, ay = S(*tx["at"])
    if tx["side"] == "front":
        t = make_text(tx["text"], F_SilkS, h, h * tx["ratio"])
        box = (ax, ay - h, 2 * CX - ax, ay)
    else:
        t = make_text(tx["text"], B_SilkS, h, h * tx["ratio"], mirrored=True, rot=270)
        n = len(tx["text"])
        L = n * 0.885 * tx["size"] * SCALE - 0.2 * tx["size"] * SCALE     # Eagle vector-font advance (see README)
        # Eagle MR270 on the bottom. Eagle keeps vector text readable (no "spin" flag), so seen from the back it reads
        # upward and the anchor is the END of the line: both lines start together near the bottom edge, the
        # "hackaday.io/davedarko" line nearer the board edge, as a two-line credit should.
        box = (ax - h, ay, ax, ay + L)
    fit_box(t, *box)
    TEXT_BOXES.append((tx["side"], box))
    print(f"text {tx['text']!r}: box {tuple(round(q, 2) for q in box)}")

# ---- routing: two copper layers, the front only for the LED wiring as the maker did ----------------------------
import router  # noqa: E402
from router import B as RB, F as RF  # noqa: E402

g = router.Grid(bx0 - 0.2, by0 - 0.2, bx1 + 0.2, by1 + 0.2)
EDGE_C = 0.5 + router.HW_MAX + 0.02
okarea = g.poly_mask(body, -EDGE_C)
for L in (RB, RF):
    g.stamp(L, ~okarea, -1)
CELL_KEEP = 10.4                                     # no back copper of any other net under the coin cell
cell_m = (g.X - BAT[0]) ** 2 + (g.Y - BAT[1]) ** 2 <= CELL_KEEP ** 2
g.stamp(RB, cell_m, -1)
INF = router.CLR + router.HW_MAX + router.SLACK
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
for c in elec:
    m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (EL_D / 2 + INF) ** 2
    g.stamp(RB, m, code("GND"))
    g.stamp(RF, m, code("GND"))
g.stamp(RF, g.poly_mask(art_mask, 0.35), -1)            # no front tracks across the bare cables
for side, (x0, y0, x1, y1) in TEXT_BOXES:               # nothing through the maker's lettering, on its own side
    m = (g.X > x0 - 0.3) & (g.X < x1 + 0.3) & (g.Y > y0 - 0.3) & (g.Y < y1 + 0.3)
    g.stamp(RF if side == "front" else RB, m, -1)
    g.noVia |= m
g.noVia |= g.poly_mask(art_silk, 0.4)                   # no via bumps in the white Y
g.noVia |= g.poly_mask(art_mask, 0.6)
g.cost[RF] = 1.6                                         # the LED wiring runs on the front, as the maker's did

TRACKS, VIAS = [], []


def add_track(L, a, b_, w, net):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(w))
    t.SetLayer(B_Cu if L == RB else F_Cu)
    t.SetNet(nets[net])
    board.Add(t)
    TRACKS.append((L, a, b_, w, net))
    g.stamp(L, g.seg_mask(a, b_, w / 2 + INF), code(net))


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
    m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (VIA_D / 2 + INF) ** 2
    g.stamp(RB, m, code(net))
    g.stamp(RF, m, code(net))


# the clip joins its two + pads itself; this arc under the cell's rim (outside the bare contact disc, where the cell's
# own + can sits) makes the board agree, as on Knight Rider
_r = 9.25
_arc = [(round(BAT[0] + _r * math.cos(math.radians(a_)), 3), round(BAT[1] + _r * math.sin(math.radians(a_)), 3))
        for a_ in range(180, -1, -10)]
_arc = [(BAT[0] - 10.5, BAT[1] + 2.0), (BAT[0] - 10.5 + 0.9, BAT[1] + 2.0)] + _arc[1:-1] + [(BAT[0] + 10.5, BAT[1] + 2.0)]
for a_, b_ in zip(_arc, _arc[1:]):
    add_track(RB, a_, b_, 0.3, "VCELL")

# the maker's own front wiring of the three LED rings, scaled; where his track met an LED pad it now meets ours
MAKER_ANODE = {tuple(v): k for k, v in ART["maker_anode_pads"].items()}


def ring_point(q):
    for mq, k in MAKER_ANODE.items():
        if math.dist(mq, q) < 0.05:
            return pp(led[int(k[1:])], "2")
    return S(*q)


RING_MASK = {}
for tr in ART["front_tracks"]:
    a_, b_ = ring_point(tr["a"]), ring_point(tr["b"])
    w = 0.3 if tr["width"] > 0.3 else SIG
    add_track(RF, a_, b_, w, tr["net"])
    m = g.seg_mask(a_, b_, 0.05)
    RING_MASK[tr["net"]] = m if tr["net"] not in RING_MASK else (RING_MASK[tr["net"]] | m)

POWER = {"VLOAD": 0.3, "VSAO": 0.3, "VBAT": 0.3, "VCELL": 0.3, "GND": 0.3}
ORDER = ["MISO", "MOSI", "SCK", "RST", "RING1", "RING2", "RING3", "VLOAD", "VSAO", "VBAT", "VCELL", "GND"]
ROUTE_FAIL = []
VIA_COST = float(os.environ.get("FLUX_VIA_COST", "40"))   # in 0.1 mm grid steps: a via costs as much as 4 mm of track
for net in ORDER:
    tg = [(L, g.poly_mask(ps, 0)) for ref, num, n, L, ps in PADS if n == net and not (ref == "BT1" and num == "2")
          and not (L == RF and (net == "GND" or net.startswith("RING")))]
    if net.startswith("RING"):  # the ring's LEDs are already joined on the front by the maker's tracks: take it to its resistor
        tg = [(RF, RING_MASK[net])] + tg
    if net == "VCELL":          # one + pad is enough: the arc joins the other
        tg = [t_ for t_, q in zip(tg, [q for q in PADS if q[2] == "VCELL"]) if mm(q[4].BBox().GetCenter())[0] < BAT[0]]
    if net == "GND":            # the front is ground copper almost everywhere: each back ground pad needs only a via
        front_free = (g.owner[RF] == 0) & ~g.noVia
        tg = [(RF, front_free)] + tg
    w = POWER.get(net, SIG)
    paths = router.route_net(g, code(net), tg, w, via_cost=VIA_COST)
    if paths is None:
        ROUTE_FAIL.append(net)
        print("ROUTE FAILED:", net)
        continue
    for path in paths:
        segs, vias_ = router.simplify(g, path)
        for L, a_, b_ in segs:
            if net == "GND" and L == RF:       # the via already stands in the front ground copper: no stub needed
                continue
            add_track(L, a_, b_, w, net)
        for c in vias_:
            add_via(c, net)
print("vias by net:", dict(collections.Counter(n for _, n in VIAS)))
print("routed; vias:", len(VIAS), "front segments:", sum(1 for t in TRACKS if t[0] == RF), "failed:", ROUTE_FAIL)


# ---- copper pours: ground on the back, the maker's ground copper on the front -----------------------------------
def ground_pour(layer, pads_anchor=True):
    gnd = pcbnew.SHAPE_POLY_SET(inner)
    cut = pcbnew.SHAPE_POLY_SET()
    gnd_code = nets["GND"].GetNetCode()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            elif pad.IsOnLayer(layer) and pad.GetNetCode() != gnd_code:
                pad.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for t in board.Tracks():
        if t.GetNetCode() != gnd_code and (t.GetClass() == "PCB_VIA" or t.GetLayer() == layer):
            t.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    cut.Simplify()
    gnd.BooleanSubtract(cut)
    gnd.Simplify()
    anchors = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd_code and pad.IsOnLayer(layer) and pads_anchor:
                anchors.Append(pad_poly(pad, layer))
    for t in board.Tracks():
        if t.GetNetCode() == gnd_code and (t.GetClass() == "PCB_VIA" or t.GetLayer() == layer):
            t.TransformShapeToPolygon(anchors, layer, 0, ERR, pcbnew.ERROR_OUTSIDE)
    anchors.Simplify()
    kept, dropped = pcbnew.SHAPE_POLY_SET(), 0.0
    for i in range(gnd.OutlineCount()):
        piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(anchors)
        if area_mm2(both) > 0.005 and area_mm2(piece) > 0.5:
            kept.BooleanAdd(piece)
        else:
            dropped += area_mm2(piece)
    add_filled(board, kept, layer, nets["GND"])
    return kept, dropped


back_gnd, back_drop = ground_pour(B_Cu)
front_gnd, front_drop = ground_pour(F_Cu, pads_anchor=False)   # front pieces must reach a ground via
print(f"ground copper: back {area_mm2(back_gnd):.0f} mm2 (dropped {back_drop:.1f}), front {area_mm2(front_gnd):.0f} mm2 (dropped {front_drop:.1f})")
bare = pcbnew.SHAPE_POLY_SET(art_mask)
bare.BooleanSubtract(front_gnd)
print(f"bare cables without copper under them: {area_mm2(bare):.3f} mm2")

# ---- front art: the bare cables (mask openings) and the white Y, cleared off the LED pads ---------------------
add_filled(board, art_mask, pcbnew.F_Mask)
fsilk = pcbnew.SHAPE_POLY_SET(art_silk)
fbare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(fbare, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.2)
        elif pad.IsOnLayer(pcbnew.F_Mask):
            fbare.Append(pad_poly(pad, F_Cu, 0.15))
for v in ELEC_VIAS:
    add_circle(fbare, v.GetPosition(), EL_D / 2 + 0.15)
fbare.Simplify()
fsilk.BooleanSubtract(fbare)
fsilk.BooleanIntersection(body)
add_filled(board, fsilk, F_SilkS)
for fp in board.GetFootprints():          # the LEDs' own silk would print over the maker's Y: keep it on the fab layer
    if fp.GetReference().startswith("D") and fp.GetLayer() == F_Cu:
        for g_ in fp.GraphicalItems():
            if g_.GetLayer() == F_SilkS:
                g_.SetLayer(pcbnew.F_Fab)

# ---- back silkscreen labels ---------------------------------------------------------------------------------
def label(txt, x, y, size=0.8, rot=0):
    t = make_text(txt, B_SilkS, size, 0.12, mirrored=True, rot=rot)
    bb = t.GetBoundingBox()
    t.Move(VECTOR2I(FromMM(x) - bb.GetCenter().x, FromMM(y) - bb.GetCenter().y))
    return t


s1, s4 = pp(sw, "1"), pp(sw, "4")
LBLX = s1[0] + 1.45
label("SAO", LBLX, s1[1] + 1.6, rot=90)        # beside the pin-1 (badge) end, as on Mad Cat: knob toward SAO = badge
label("OFF", LBLX, SWY, rot=90)
label("BAT", LBLX, s4[1] - 1.6, rot=90)
label("CR2032 +", BAT[0], BAT[1] + 9.0)
label("SAO++ rA", CX - 4.5, by0 + 1.3)
label("Flux Capacitor", CX + 5.0, by0 + 1.3)
for g_ in bat.GraphicalItems():                  # the clip's silk arrow: fab layer, as on the other boards
    if g_.GetLayer() == B_SilkS:
        g_.SetLayer(pcbnew.B_Fab)

# ---- design settings and save -----------------------------------------------------------------------------
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
board.GetTitleBlock().SetComment(1, f"Scaled {SCALE}x from the maker's 25.40 x 30.47 mm to {W:.2f} x {H:.2f} mm")
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
if ROUTE_FAIL:
    print("UNROUTED NETS:", ROUTE_FAIL)
    sys.exit(1)
