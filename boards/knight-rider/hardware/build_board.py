#!/usr/bin/env python3
"""Build knight-rider.kicad_pcb from the maker's 2024 artwork (art/art.json) plus the SAO++ parts and routing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/knight-rider/hardware/build_board.py

The maker's last design (original/KiCad8, 2024) has its parts on one side and the car on the other. art.json (made by
extract_art.py) holds that car turned over onto the front: copper, white silkscreen and the bare bumper-light windows.
What this script adds:
  front  - the maker's eight red scanner LEDs, in the maker's exact positions, facing forward as on every one of the
           maker's revisions (see README: a through-board LED cannot be used here because the coin cell has to sit behind
           the scanner), plus the front half of a two-layer route: tented vias and short tracks under the solder mask
  back   - the SAO connector, the SAO / OFF / BAT switch, the CR2032 clip and its series diode, the maker's ATtiny85,
           ISP pads and push button, nine resistors and a capacitor; ground copper everywhere else
Routing is done by router.py (a small two-layer grid router, deterministic) inside this one run: about a minute.
Coordinates are millimetres in KiCad's front view of the new board (x grows right, y grows down).
"""
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
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "knight-rider"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))

CLEAR = 0.30        # copper-to-copper gap cut into the ground and art copper
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
PWR = 0.30          # supply track width
VIA_D, VIA_HOLE = 0.6, 0.3

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


art_cu = union([poly(p_) for p_ in ART["front_cu"]])
art_silk = union([poly(p_) for p_ in ART["front_silk"]])
art_mask = union([poly(p_) for p_ in ART["front_mask_open"]])

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


def place(ref, pos, want, back=True):
    """Place a part (on the back unless told otherwise) at the right-angle rotation that puts pad want[0] nearest want[1]."""
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
# front: the maker's eight scanner LEDs exactly where the 2024 board had them (anode up)
led = {}
for ref, v in ART["leds"].items():
    led[ref] = place(ref, tuple(v["centre"]), ("2", tuple(v["anode"])), back=False)

# coin cell: left half, closed end down, open end up (the cell slides in from the roof's left shoulder, over bare board)
BAT = (138.0, 106.8)
bat = place("BT1", BAT, ("1", (BAT[0] - 10.5, BAT[1])))
assert abs(pp(bat, "1", pick=lambda p: -p[0])[0] - (BAT[0] + 10.5)) < 0.01   # pads left and right of the cell


def _closed_dir():
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return ToMM(c.y) - BAT[1]


if _closed_dir() < 0:                                    # want the closed end DOWN: turn the clip half a turn
    bat.SetOrientationDegrees(bat.GetOrientationDegrees() + 180)
assert _closed_dir() > 3, _closed_dir()

CONN = (158.5, 107.7)       # right half, key slot up
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC top-left in front view, as on Mad Cat
SWX, SW_FACE = 155.5, 117.5                                         # switch body's knob face just inside the flat bottom edge
sw = place("SW1", (SWX, SW_FACE - 1.6), ("1", (SWX + 3.0, SW_FACE - 3.03)))   # knob down: pin 1 (badge) right, pin 4 (cell) left
U1_C = (169.0, 106.8)
u1 = place("U1", U1_C, ("8", (U1_C[0] + 1.905, U1_C[1] - 3.3528)))   # pins 5-8 along the top (MOSI MISO SCK VCC), RST bottom-right
ISP = (167.6, 115.2)
isp = place("JP1", ISP, ("P$1", (ISP[0] - 2.54, ISP[1] - 1.27)))   # top row MISO SCK RST, bottom row VCC MOSI GND
BTN = (163.5, 98.3)
btn = place("SW2", BTN, ("P$1", (BTN[0] - 3.15, BTN[1])))          # PB4 pad on the left
C1_C = (162.8, 115.8)
c1 = place("C1", C1_C, ("1", (C1_C[0], C1_C[1] - 0.825)))
D9_C = (150.16, 112.2)
d9 = place("D9", D9_C, ("2", (D9_C[0], D9_C[1] - 0.7)))             # anode (cell side) up
R9_C = (164.0, 101.8)
res = {"R9": place("R9", R9_C, ("1", (R9_C[0], R9_C[1] - 0.825)))}   # vertical: PB4 up, badge GPIO2 down

RX = [149.0 + 1.5 * k for k in range(6)]       # resistor row between the "davedarko" line and the connector
R_SLOTS = {}
for k, ref in enumerate(["R5", "R1", "R6", "R2", "R7", "R3"]):
    R_SLOTS[ref] = (RX[k], 100.05)
R_SLOTS["R8"] = (154.6, 97.0)                 # two more right of "davedarko", under the end of "hackaday..."
R_SLOTS["R4"] = (156.1, 97.0)
for ref, (x, y) in R_SLOTS.items():
    res[ref] = place(ref, (x, y), ("1", (x, y - 0.825)))               # pad 1 (drive side) up

NEW = set(PARTS)
_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            layer = F_Cu if pad.IsOnLayer(F_Cu) else B_Cu
            off = pad_poly(pad, layer)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# ---- routing: two copper layers (accepted exception for this board, see README) ---------------------------
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
g.stamp(RF, g.poly_mask(art_mask, 0.25), -1)            # no front copper inside the bumper-light windows
# vias: never through the maker's credit lettering, nor through the white silkscreen art on the front
for c_ in ART["back_text"]:
    if c_["text"] in ("davedarko", "hackaday.io/project/25944"):
        x0, y0, x1, y1 = c_["bbox"]
        g.noVia |= (g.X > x0 - 0.4) & (g.X < x1 + 0.4) & (g.Y > y0 - 0.4) & (g.Y < y1 + 0.4)
g.noVia |= g.poly_mask(art_silk, 0.4)
# front copper is dear; least dear around the scanner and along the bumper, where the front is already busy or dark
g.cost[RF] = 8.0
zone = (g.X > 139.5) & (g.X < 162) & (g.Y > 100.5) & (g.Y < 113.0)
g.cost[RF][zone] = 2.5

TRACKS, VIAS = [], []          # (layer, a, b, width, net) / ((x, y), net)


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


# the clip joins its two + pads itself; this arc under the cell's rim (outside the bare contact disc) makes the board agree
_r = 9.25
_arc = [(round(BAT[0] + _r * math.cos(math.radians(a_)), 3), round(BAT[1] + _r * math.sin(math.radians(a_)), 3)) for a_ in range(180, -1, -10)]
_arc = [(BAT[0] - 10.5, BAT[1] + 2.0)] + _arc[1:-1] + [(BAT[0] + 10.5, BAT[1] + 2.0)]
_arc[1:1] = [(BAT[0] - 10.5 + 0.9, BAT[1] + 2.0)]
for a_, b_ in zip(_arc, _arc[1:]):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a_))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(0.3))
    t.SetLayer(B_Cu)
    t.SetNet(nets["VCELL"])
    board.Add(t)
    TRACKS.append((RB, a_, b_, 0.3, "VCELL"))

POWER = {"VLOAD": 0.3, "VSAO": 0.3, "VBAT": 0.3, "VCELL": 0.3, "GND": 0.3}
ORDER = [f"LED{k}_A" for k in range(4, 0, -1)] + [f"LED{k}_K" for k in range(5, 9)] + \
        ["MOSI", "MISO", "SCK", "PB3", "RST", "PB4", "SAO_GPIO2", "VSAO", "VBAT", "VCELL", "VLOAD", "GND"]
ROUTE_FAIL = []
for net in ORDER:
    tg = [(L, g.poly_mask(ps, 0)) for ref, num, n, L, ps in PADS if n == net and not (ref == "BT1" and num == "2")
          and not (net == "GND" and L == RB and ref not in ("J1", "U1", "JP1", "C1", "SW2"))]   # the rest join through the ground copper
    if net == "GND":            # and one anchor in the big ground area on the roof, so the right-hand pieces join it
        tg.append((RB, (g.X - 146.0) ** 2 + (g.Y - 92.4) ** 2 <= 0.2 ** 2))
    if net == "VCELL":
        tg = [t_ for t_, (ref, num, n, L, ps) in zip(tg, [q for q in PADS if q[2] == "VCELL"]) if mm(ps.BBox().GetCenter())[0] > BAT[0]]
    w = POWER.get(net, SIG)
    paths = router.route_net(g, code(net), tg, w, via_cost=100.0)
    if paths is None:
        ROUTE_FAIL.append(net)
        print("ROUTE FAILED:", net)
        continue
    for path in paths:
        segs, vias_ = router.simplify(g, path)
        for L, a_, b_ in segs:
            add_track(L, a_, b_, w, net)
        for c in vias_:
            add_via(c, net)
import collections as _c
print("vias by net:", dict(_c.Counter(n for _, n in VIAS)))
print("routed; vias:", len(VIAS), "front segments:", sum(1 for t in TRACKS if t[0] == RF), "failed:", ROUTE_FAIL)

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
n_gnd = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.005 and area_mm2(piece) > 1.0:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
print("back ground pieces:", n_gnd)

# ---- front: the maker's art, cleared around the scanner LEDs' pads and the switch pegs ---------------
fcut = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(F_Cu):
            pad.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in board.Tracks():
    if t.GetClass() == "PCB_VIA" or t.GetLayer() == F_Cu:
        t.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
fcut.Simplify()
fcu = pcbnew.SHAPE_POLY_SET(art_cu)
fcu.BooleanSubtract(fcut)
fcu.BooleanIntersection(inner)
fcu.Simplify()
add_filled(board, fcu, F_Cu)
fsilk = pcbnew.SHAPE_POLY_SET(art_silk)
fbare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(fbare, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.2)
        elif pad.IsOnLayer(pcbnew.F_Mask):
            fbare.Append(pad_poly(pad, F_Cu, 0.2))
fbare.Simplify()
fsilk.BooleanSubtract(fbare)
fsilk.BooleanIntersection(body)
add_filled(board, fsilk, F_SilkS)
add_filled(board, art_mask, pcbnew.F_Mask)          # the bumper lights: bare board windows, as the maker drew them

# ---- back silkscreen: the maker's credit lines, unchanged, where the 2024 board had them; SAO++ labels ----
def text(txt, x, y, size, thick, bold=False, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetBold(bold)
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


for c in ART["back_text"]:
    if c["text"] in ("davedarko", "hackaday.io/project/25944"):      # the maker's credits; "JLCJLCJLCJLC" (a fab order-number slot) and "SAO" are not carried
        x0, y0, x1, y1 = c["bbox"]
        t = text(c["text"], (x0 + x1) / 2, (y0 + y1) / 2, c["size"], c["thickness"], c["bold"])
        bb = t.GetBoundingBox()
        t.Move(VECTOR2I(int((x0 + x1) / 2 * 1e6) - bb.GetCenter().x, int((y0 + y1) / 2 * 1e6) - bb.GetCenter().y))
s1, s4 = pp(sw, "1"), pp(sw, "4")
# switch positions as seen from the back (mirrored text reads correctly from there): badge, off, cell
text("SAO  OFF  BAT", 133.6, 97.55, 0.8, 0.12)
text("CR2032 +", 125.45, 111.3, 0.8, 0.12, rot=90)
text("SAO++ rA", 133.5, 117.3, 0.8, 0.12)
for g_ in bat.GraphicalItems():                       # the clip's own silk arrow lands on the maker's credit line: keep it on the fab layer
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
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
