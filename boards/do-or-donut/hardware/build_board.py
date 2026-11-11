#!/usr/bin/env python3
"""Build do-or-donut.kicad_pcb from the maker's Eagle board plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/do-or-donut/hardware/build_board.py

What it does
  - reads original/donut.brd (Eagle 7.6 XML) directly: outline, the 144 front LEDs and the IS31FL3731 at the maker's
    exact positions and angles, every track and via of the 18 matrix nets, the front solder-mask art (the bare "dough"
    rim and the ring round the hole, with the mask colour as the icing), and the back silkscreen (twelve "ds" logos and
    the DO OR DONUT / @davedarko / 2019 credit)
  - leaves out the maker's through-hole SAO header, his audio test pad, the parts on its circuit that change, and the
    tracks that fed them
  - places the SAO++ parts on the back: the XIAO module (USB-C out of the bottom edge), the SMD SAO connector (top,
    above the hole), the power switch and the LiPo connector (lower edge, either side of the XIAO)
  - takes out the maker's back-side tracks and vias that the new parts land on, and routes the broken matrix
    connections and every new connection with hardware/router.py (both layers, tented vias where needed)
  - pours ground on the back and writes the silkscreen labels
Coordinates are millimetres in KiCad's front view (x grows right, y grows down). Eagle (y up) maps to KiCad by
X = 100 + x, Y = 150.8 - y, so the board's centre is (125.4, 125.4).
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
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402
import eagle  # noqa: E402
from router import Grid  # noqa: E402

SLUG = "do-or-donut"
OUT = os.environ.get("DONUT_OUT") or os.path.join(HERE, SLUG + ".kicad_pcb")      # (override only for experiments)
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

OX, OY = 100.0, 150.8
CX, CY = 125.4, 125.4               # board centre
R_OUT = 25.4                        # the board is a 50.8 mm circle

EDGE_GND = 0.55     # ground pour stops this far short of every board edge (clear of the panel's mouse-bite holes)
SIG_W = 0.127       # new signal tracks: the maker's own 5 mil track ...
SIG_CLEAR = 0.127   # ... and 5 mil gap, so a track fits between two of the XIAO's edge pads (0.54 mm apart)
PWR_W = 0.30        # new supply tracks
PWR2_W = 0.20       # supply tracks where 0.3 mm does not fit
CLEAR = 0.15        # gap kept by the supply tracks
MAKER_VIA_D = 0.686
KL = [F_Cu, B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu]      # router layer index -> KiCad layer
ALL_L = (0, 1, 2, 3)
VIA_D, VIA_DRILL = 0.6, 0.3       # new vias: the house size, tented (no mask opening). The maker's are 0.686 / 0.33


def T(x, y):
    """Eagle mm (y up) -> KiCad mm (y down)."""
    return (OX + x, OY - y)


E = eagle.load()

# ---- outline -------------------------------------------------------------------------------------
loops = [[T(x, y) for x, y in lp] for lp in eagle.chain_wires(E["outline"], step_deg=0.5)]
loops.sort(key=lambda lp: -abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(lp, lp[1:] + lp[:1]))))
OUTER, HOLE = loops
assert all(abs(math.hypot(x - CX, y - CY) - R_OUT) < 0.002 for x, y in OUTER), "outer edge is not the 50.8 mm circle"
board_poly = poly(OUTER)
board_poly.BooleanSubtract(poly(HOLE))
hole_poly = poly(HOLE)

board = pcbnew.CreateEmptyBoard()
board.SetCopperLayerCount(4)                 # four layers: see the README (the maker's was two)
for lp in (OUTER, HOLE):
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    e.SetPolyShape(poly(lp))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
hb = bbox_mm(hole_poly)
print(f"board 50.80 x 50.80 mm; centre hole {hb[2] - hb[0]:.2f} x {hb[3] - hb[1]:.2f} mm")

# ---- the circuit ---------------------------------------------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
MATRIX = json.load(open(os.path.join(HERE, "matrix.json")))
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


def load_fp(ref):
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LOCAL_LIB if lib == SLUG + "-local" else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    return fp


def link(fp, ref):
    _, value, fpid, fields, _, _ = SYMBOLS[PARTS[ref]["symbol"]]
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


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


def place_back(ref, pos, want, angles=(0, 90, 180, 270)):
    """Place on the back, then pick the rotation that puts pad want[0] nearest want[1]."""
    fp = load_fp(ref)
    board.Add(fp)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    best = None
    for rot in angles:
        fp.SetOrientationDegrees(rot)
        d = min(math.hypot(mm(p.GetPosition())[0] - want[1][0], mm(p.GetPosition())[1] - want[1][1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.3f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def place_back_at_angle(ref, theta_deg, inset, fp=None):
    """A back-side part on the round edge: its local +y (knob / plug opening) points out along the radius at angle theta
    (degrees counter-clockwise from 3 o'clock, front view). `inset` = distance from the board centre to the part's origin.
    Pass `fp` to move a part placed earlier."""
    th = math.radians(theta_deg)
    pos = (CX + inset * math.cos(th), CY - inset * math.sin(th))
    if fp is None:
        fp = load_fp(ref)
        board.Add(fp)
        fp.SetPosition(P(*pos))
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.Reference().SetVisible(False)
        link(fp, ref)
    fp.SetPosition(P(*pos))
    # local +y must point out along the radius. Which of two opposite orientations does that on a flipped footprint is
    # checked, not assumed: the unnumbered pads (switch tabs and pegs, connector hold-downs) sit on the +y side.
    phi = math.degrees(math.atan2(math.cos(th), -math.sin(th)))
    for cand in (phi, phi + 180):
        fp.SetOrientationDegrees(cand)
        r_un = [math.hypot(*np.subtract(mm(p.GetPosition()), (CX, CY))) for p in fp.Pads() if p.GetNumber() == ""]
        r_num = [math.hypot(*np.subtract(mm(p.GetPosition()), (CX, CY))) for p in fp.Pads() if p.GetNumber() != ""]
        if sum(r_un) / len(r_un) > sum(r_num) / len(r_num):
            return fp
    raise AssertionError(f"{ref}: cannot point it outward")


# ---- the maker's parts that stay: 144 LEDs (front) and the driver (back), at his exact positions ------------------
EL = E["elements"]
led_fp = {}
for d in MATRIX["leds"]:
    el = EL[d["maker_ref"]]
    fp = load_fp(d["ref"])
    board.Add(fp)
    fp.SetPosition(P(*T(el["x"], el["y"])))
    fp.SetOrientationDegrees(el["angle"])
    fp.Reference().SetVisible(False)
    link(fp, d["ref"])
    for num, eg in (("1", "C"), ("2", "A")):
        want = T(*el["pads"][eg])
        got = pp(fp, num)
        assert math.hypot(got[0] - want[0], got[1] - want[1]) < 0.002, (d["ref"], num, got, want)
    led_fp[d["ref"]] = fp
u1_el = EL["U1"]
u1 = place_back("U1", T(u1_el["x"], u1_el["y"]), ("1", T(*u1_el["pads"]["1"])))
for num in ("1", "14", "15", "28"):
    want, got = T(*u1_el["pads"][num]), pp(u1, num)
    assert math.hypot(got[0] - want[0], got[1] - want[1]) < 0.002, ("U1", num, got, want)

# ---- new parts on the back ---------------------------------------------------------------------------------------
XIAO_D = 24.0                                      # USB end of the module, from the centre: its corners touch the round edge
XIAO_C = (CX, CY + XIAO_D - 10.48)
xiao = place_back("U2", XIAO_C, ("1", (XIAO_C[0] - 8.055, XIAO_C[1] + 7.56)))   # USB down: D0 bottom-left (front view)
CONN = (CX, OY - 43.4)                             # above the hole, centred left to right
conn = place_back("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))            # VCC top-left in front view, key slot up
SW_ANGLE = 62.0                                    # upper right (front view), between the SAO connector and the driver:
                                                   # short supply runs to both
JST_ANGLE = 216.0                                  # lower left, beside the XIAO's battery pads


def max_inset(ref):
    """How far out an edge part can sit: no pad within 0.27 mm of the round edge. In the part's own frame +y is the
    outward direction and x runs along the edge (the flip to the back only mirrors x), so a pad corner (x, y) lands
    at distance hypot(inset + y, x) from the centre."""
    fp = load_fp(ref)
    corners = []
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        ps = pad_poly(pad, F_Cu)
        for i in range(ps.OutlineCount()):
            ch = ps.Outline(i)
            corners += [(ToMM(ch.CPoint(v).x), ToMM(ch.CPoint(v).y)) for v in range(ch.PointCount())]
    lim = R_OUT - 0.27
    return min(math.sqrt(lim * lim - x * x) - y for x, y in corners)


def courtyard(fp):
    fp.BuildCourtyardCaches()
    return pcbnew.SHAPE_POLY_SET(fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd))


def cy_pts(fp):
    c = courtyard(fp)
    ch = c.Outline(0)
    return [(ToMM(ch.CPoint(i).x), ToMM(ch.CPoint(i).y)) for i in range(ch.PointCount())]


def gap_mm(a, b):
    """Smallest gap between two courtyards (negative = they overlap)."""
    inter = pcbnew.SHAPE_POLY_SET(a)
    inter.BooleanIntersection(b)
    if inter.OutlineCount():
        return -1.0
    for g in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5):
        inter = grown(a, g)
        inter.BooleanIntersection(b)
        if inter.OutlineCount():
            return g
    return 9.9


def edge_part(ref, angle, step, avoid):
    """Put an edge part at `angle`, then turn it round the edge (by `step` degrees at a time) until its courtyard
    is 0.25 mm clear of the parts in `avoid`."""
    inset = max_inset(ref)
    cys = [courtyard(f) for f in avoid]
    fp = None
    for k in range(120):
        fp = place_back_at_angle(ref, angle + k * step, inset, fp)
        c = courtyard(fp)
        if all(gap_mm(c, o) >= 0.25 for o in cys):
            return fp, angle + k * step, inset
    raise AssertionError(f"{ref}: no clear spot")


sw, SW_ANGLE, SW_INSET = edge_part("SW1", SW_ANGLE, -0.5, [xiao, conn, u1])
jst, JST_ANGLE, JST_INSET = edge_part("J2", JST_ANGLE, -0.5, [xiao, conn, u1, sw])
print(f"switch at {SW_ANGLE:.1f} deg ({SW_INSET:.2f} mm out); LiPo connector at {JST_ANGLE:.1f} deg ({JST_INSET:.2f} mm out)")
real_fps = list(board.GetFootprints())
NEWBACK = [xiao, conn, sw, jst]

# every pad on the board and >= 0.25 mm from the edge
EDGE_BAD = []
_pad_ok = poly(OUTER)
_pad_ok.Inflate(-FromMM(0.25), ROUND, ERR)
_pad_ok.BooleanSubtract(grown(hole_poly, 0.25))     # (shrinking a shape with a hole opens a slit: shrink and grow separately)
for fp in real_fps:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        lay = F_Cu if pad.IsOnLayer(F_Cu) else B_Cu
        off = pad_poly(pad, lay)
        off.BooleanSubtract(_pad_ok)
        if off.OutlineCount():
            EDGE_BAD.append(f"{fp.GetReference()} pad {pad.GetNumber()}")

# ---- keep-outs the new parts need on the back --------------------------------------------------------------------
KEEP_B = []                         # shapes on the back where no other copper may be (besides the parts' own pads)
xiao_test = [g for g in xiao.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE]
assert len(xiao_test) == 8
TEST_KEEP = [(mm(g.GetCenter()), 0.85 + 0.15) for g in xiao_test]       # the module's own test pads underneath
for c, r in TEST_KEEP:
    KEEP_B.append(("circle", c[0], c[1], r))
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        c = mm(pad.GetPosition())
        KEEP_B.append(("circle", c[0], c[1], ToMM(pad.GetDrillSize().x) / 2 + 0.25))


def pad_shape(pad):
    c = mm(pad.GetPosition())
    sz = pad.GetSize(pad.GetPrincipalLayer()) if hasattr(pad, "GetPrincipalLayer") else pad.GetSize()
    ang = pad.GetOrientationDegrees()
    return ("rect", c[0], c[1], ToMM(sz.x) / 2, ToMM(sz.y) / 2, -ang)


# ---- the maker's matrix tracks and vias, minus those under the new parts ---------------------------------------
MATRIX_NETS = [f"C{m}{i}" for m in "AB" for i in range(1, 10)]


def seg_hits(shape, ax, ay, bx, by, hw, gap):
    """Does a track (centreline a-b, half width hw) come within `gap` of a shape?"""
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.02))
    for k in range(n + 1):
        x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
        if shape_dist(shape, x, y) < hw + gap:
            return True
    return False


def shape_dist(shape, x, y):
    if shape[0] == "circle":
        return math.hypot(x - shape[1], y - shape[2]) - shape[3]
    if shape[0] == "rect":
        _, cx, cy, hw, hh, ang = shape
        a = math.radians(ang)
        u = (x - cx) * math.cos(a) + (y - cy) * math.sin(a)
        v = -(x - cx) * math.sin(a) + (y - cy) * math.cos(a)
        return math.hypot(max(abs(u) - hw, 0), max(abs(v) - hh, 0))
    raise ValueError(shape)


NEW_PAD_SHAPES = [pad_shape(p) for f in NEWBACK for p in f.Pads() if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
RIP = NEW_PAD_SHAPES + KEEP_B


def rect_of(fp, grow):
    """A footprint's courtyard as a ('rect', ...) shape grown by `grow` (courtyards here are rectangles)."""
    pts = cy_pts(fp)
    (x0, y0), (x1, y1), (x2, y2) = pts[0], pts[1], pts[2]
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    return ("rect", (x0 + x2) / 2, (y0 + y2) / 2, math.hypot(x1 - x0, y1 - y0) / 2 + grow, math.hypot(x2 - x1, y2 - y1) / 2 + grow, ang)


# the switch's two peg holes go right through the board: the maker's FRONT tracks must clear them too
PEGS = [("circle", mm(p_.GetPosition())[0], mm(p_.GetPosition())[1], ToMM(p_.GetDrillSize().x) / 2 + 0.25)
        for p_ in sw.Pads() if p_.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
tracks_kept, vias_kept, n_rip_t, n_rip_v = [], [], 0, 0
for name in MATRIX_NETS:
    s = E["signals"][name]
    for (x1, y1, x2, y2, w, layer) in s["wires"]:
        a, b = T(x1, y1), T(x2, y2)
        if (layer == "16" and any(seg_hits(sh, a[0], a[1], b[0], b[1], w / 2, CLEAR) for sh in RIP)) or \
                any(seg_hits(sh, a[0], a[1], b[0], b[1], w / 2, 0.02) for sh in PEGS):
            n_rip_t += 1
            continue
        tracks_kept.append((name, a, b, w, F_Cu if layer == "1" else B_Cu))
    for (x, y, drill) in s["vias"]:
        c = T(x, y)
        if any(shape_dist(sh, c[0], c[1]) < MAKER_VIA_D / 2 + CLEAR for sh in RIP + PEGS):
            n_rip_v += 1
            continue
        vias_kept.append((name, c, drill))
print(f"maker's matrix routing: kept {len(tracks_kept)} tracks and {len(vias_kept)} vias; "
      f"took out {n_rip_t} tracks and {n_rip_v} vias under the new parts and beside the switch's peg holes")


def add_track(net, a, b, w, layer):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(FromMM(w))
    t.SetLayer(layer)
    t.SetNet(nets[net])
    board.Add(t)
    return t


def add_via(net, c, drill=VIA_DRILL, dia=VIA_D):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c))
    v.SetWidth(FromMM(dia))
    v.SetDrill(FromMM(drill))
    v.SetNet(nets[net])
    board.Add(v)
    return v


# the maker's kept copper goes on the board after routing, once the dead-end stubs left by the lifting are pruned

# ---- routing -------------------------------------------------------------------------------------------------
t0 = time.time()
CLASSES = {"sig": (SIG_W / 2, SIG_CLEAR), "pwr": (PWR_W / 2, CLEAR), "pwr2": (PWR2_W / 2, CLEAR), "via": (VIA_D / 2, SIG_CLEAR)}
# router layers: 0 front, 1 back (the maker's routing and the parts), 2 and 3 the inner layers for the new routing.
# The outer layers cost more, so new tracks only use them for the short hop from a pad to a via.
grid = Grid(CX - R_OUT - 0.5, CY - R_OUT - 0.5, CX + R_OUT + 0.5, CY + R_OUT + 0.5, CLASSES, n_layers=4,
            layer_cost=[4.0, 3.0, 1.0, 1.0])
NETID = {n: i for i, n in enumerate(sorted(nets))}

# edges: tracks keep 0.3 mm from the board edge and the hole edge (vias the same plus their radius)
Xg, Yg = np.meshgrid(grid.xs, grid.ys)
rr = np.hypot(Xg - CX, Yg - CY)
inside_hole = np.zeros_like(rr, bool)
hx = np.array([p[0] for p in HOLE])
hy = np.array([p[1] for p in HOLE])
hx2, hy2 = np.roll(hx, -1), np.roll(hy, -1)
d_hole = np.full_like(rr, np.inf)
i0, i1, j0, j1 = grid.window(hx.min() - 2, hy.min() - 2, hx.max() + 2, hy.max() + 2)
Xw, Yw = Xg[i0:i1, j0:j1], Yg[i0:i1, j0:j1]
ins, dh = np.zeros_like(Xw, bool), np.full_like(Xw, np.inf)
for k in range(len(hx)):
    cond = ((hy[k] > Yw) != (hy2[k] > Yw)) & (Xw < (hx2[k] - hx[k]) * (Yw - hy[k]) / (hy2[k] - hy[k] + 1e-12) + hx[k])
    ins ^= cond
    np.minimum(dh, Grid.d_segment(Xw, Yw, hx[k], hy[k], hx2[k], hy2[k]), out=dh)
inside_hole[i0:i1, j0:j1] = ins
d_hole[i0:i1, j0:j1] = dh
d_edge = np.where(inside_hole, -d_hole, np.minimum(R_OUT - rr, d_hole))
for cls, (half, _) in grid.classes.items():
    blocked = d_edge < 0.30 + half + 0.05
    for L in ALL_L:
        grid.cnt[cls][L][blocked] = 2

# everything already on the board, labelled by net
for fp in real_fps:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            c = mm(pad.GetPosition())
            r = ToMM(pad.GetDrillSize().x) / 2
            grid.add_fixed(("circle", c[0], c[1], r + 0.25 - SIG_CLEAR), ALL_L, -1)
            grid.add_fixed_drill(c[0], c[1], r, 0.25, VIA_DRILL / 2)
            continue
        net = pad.GetNetname()
        layers = (0,) if pad.IsOnLayer(F_Cu) else (1,)
        grid.add_fixed(pad_shape(pad), layers, NETID.get(net, -1) if net else -1)
for name, c, drill in vias_kept:
    grid.add_fixed(("circle", c[0], c[1], MAKER_VIA_D / 2), ALL_L, NETID[name])
    grid.add_fixed_drill(c[0], c[1], drill / 2, 0.25, VIA_DRILL / 2)
for name, a, b, w, layer in tracks_kept:
    grid.add_fixed(("seg", a[0], a[1], b[0], b[1], w / 2), (KL.index(layer),), NETID[name])
for sh in KEEP_B:
    grid.add_fixed(sh, (1,), -1)
print(f"router grid {grid.nx} x {grid.ny} x {grid.nl} ready in {time.time() - t0:.1f} s")


# ---- small parts: each goes to the free spot on the back nearest the pin it serves ------------------------------
def convex_cells(pts, grow):
    """Cells inside a convex polygon (KiCad mm points) grown by `grow`."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    i0, i1, j0, j1 = grid.window(min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow)
    X, Y = np.meshgrid(grid.xs[j0:j1], grid.ys[i0:i1])
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    sgn = 1 if area2 > 0 else -1
    m = np.ones_like(X, bool)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ey)
        m &= sgn * (ex * (Y - a[1]) - ey * (X - a[0])) / L >= -grow
    return (i0, i1, j0, j1), m


place_block = np.zeros((grid.ny, grid.nx), bool)
for fp in real_fps:
    if fp.IsFlipped():
        (i0, i1, j0, j1), m = convex_cells(cy_pts(fp), 0.1)
        place_block[i0:i1, j0:j1] |= m

SMALL = [("R6", u1, "6"), ("R1", u1, "3"), ("C3", u1, "2"), ("C4", u1, "5"), ("C1", u1, "16"), ("C5", xiao, "12"),
         ("R5", u1, "19"), ("R4", u1, "20"), ("R7", xiao, "8"), ("R8", xiao, "7")]
G2 = 0.05 * 0.05
OFFS = sorted(((dx * 0.1, dy * 0.1) for dx in range(-80, 81) for dy in range(-80, 81)), key=lambda d: math.hypot(*d))
small = {}
for ref, host, pin in SMALL:
    anchor_xy = pp(host, pin)
    fp = load_fp(ref)
    board.Add(fp)
    fp.SetPosition(P(*anchor_xy))
    fp.Flip(P(*anchor_xy), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    link(fp, ref)
    frees = {}
    for pad in fp.Pads():
        n = pad.GetNetname()
        if n not in frees:
            frees[n] = grid.base_free("sig", NETID[n])[1]
    done = False
    for dx, dy in OFFS:
        for rot in (0, 90):
            fp.SetPosition(P(anchor_xy[0] + dx, anchor_xy[1] + dy))
            fp.SetOrientationDegrees(rot)
            ok = True
            for pad in fp.Pads():
                sh = pad_shape(pad)
                (i0, i1, j0, j1), m = grid._mask(sh, 0.0)
                if m.sum() < 0.8 * 4 * sh[3] * sh[4] / G2 or (d_edge[i0:i1, j0:j1][m] < 0.4).any() \
                        or not frees[pad.GetNetname()][i0:i1, j0:j1][m].all() or place_block[i0:i1, j0:j1][m].any():
                    ok = False
                    break
            if ok:
                (i0, i1, j0, j1), m = convex_cells(cy_pts(fp), 0.0)
                ok = not place_block[i0:i1, j0:j1][m].any()
            if ok:
                done = True
                break
        if done:
            break
    assert done, f"no room for {ref}"
    (i0, i1, j0, j1), m = convex_cells(cy_pts(fp), 0.1)
    place_block[i0:i1, j0:j1] |= m
    for pad in fp.Pads():
        grid.add_fixed(pad_shape(pad), (1,), NETID[pad.GetNetname()])
    small[ref] = fp
    real_fps.append(fp)
    print(f"  {ref} at {mm(fp.GetPosition())} rot {fp.GetOrientationDegrees():.0f}, {math.hypot(dx, dy):.1f} mm from {host.GetReference()} pin {pin}")


FIXED = {}                          # net -> fixed copper items [(shape, layers)]
for fp in real_fps:
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and pad.GetNetname():
            FIXED.setdefault(pad.GetNetname(), []).append((pad_shape(pad), (0,) if pad.IsOnLayer(F_Cu) else (1,)))
for name, c, drill in vias_kept:
    FIXED.setdefault(name, []).append((("circle", c[0], c[1], MAKER_VIA_D / 2), ALL_L))
for name, a_, b_, w, layer in tracks_kept:
    FIXED.setdefault(name, []).append((("seg", a_[0], a_[1], b_[0], b_[1], w / 2), (KL.index(layer),)))
ROUTES = {}                         # net -> {"segs": [(layer, a, b, width)], "vias": [(x, y)]}


def net_items(net):
    items = list(FIXED.get(net, []))
    r = ROUTES.get(net)
    if r:
        items += [(("seg", a[0], a[1], b[0], b[1], w / 2), (L,)) for L, a, b, w in r["segs"]]
        items += [(("circle", c[0], c[1], VIA_D / 2), ALL_L) for c in r["vias"]]
    return items


def touch(i1, i2):
    (s1, l1), (s2, l2) = i1, i2
    if not set(l1) & set(l2):
        return False
    if s1[0] == "seg" and s2[0] == "seg":
        for (x, y) in ((s1[1], s1[2]), (s1[3], s1[4])):
            if Grid.d_segment(np.array(x), np.array(y), s2[1], s2[2], s2[3], s2[4]) <= s1[5] + s2[5] - 0.001:
                return True
        for (x, y) in ((s2[1], s2[2]), (s2[3], s2[4])):
            if Grid.d_segment(np.array(x), np.array(y), s1[1], s1[2], s1[3], s1[4]) <= s1[5] + s2[5] - 0.001:
                return True
        return False
    if s1[0] == "seg":
        s1, s2 = s2, s1
    if s2[0] == "seg":
        return seg_hits(s1, s2[1], s2[2], s2[3], s2[4], s2[5], -0.001)
    if s1[0] == "circle" and s2[0] == "circle":
        return math.hypot(s1[1] - s2[1], s1[2] - s2[2]) < s1[3] + s2[3]
    if s1[0] == "circle":
        s1, s2 = s2, s1
    if s2[0] == "circle":
        return shape_dist(s1, s2[1], s2[2]) < s2[3]
    return shape_dist(s1, s2[1], s2[2]) < 0.05


def groups(items):
    parent = list(range(len(items)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(items)):
        for j in range(i):
            if f(i) != f(j) and touch(items[i], items[j]):
                parent[f(i)] = f(j)
    out = {}
    for i in range(len(items)):
        out.setdefault(f(i), []).append(items[i])
    return list(out.values())


def cells(group):
    m = np.zeros((grid.nl, grid.ny, grid.nx), bool)
    for sh, layers in group:
        if sh[0] == "seg":
            m |= grid.cells_of(("seg",) + sh[1:5] + (max(sh[5] - 0.03, 0.01),), layers)
        elif sh[0] == "circle":
            m |= grid.cells_of(("circle", sh[1], sh[2], max(sh[3] - 0.08, 0.02)), layers)
        else:
            m |= grid.cells_of(sh, layers, shrink=0.05)
    return m


def rip(net):
    grid.unclaim(NETID[net])
    ROUTES.pop(net, None)


def commit(net, width, runs, vias):
    nid = NETID[net]
    r = ROUTES.setdefault(net, {"segs": [], "vias": []})
    for L, pts in runs:
        for a, b in zip(pts, pts[1:]):
            r["segs"].append((L, a, b, width))
            grid.claim_shape(nid, ("seg", a[0], a[1], b[0], b[1], width / 2), (L,))
    for c in vias:
        r["vias"].append(c)
        grid.claim_shape(nid, ("circle", c[0], c[1], VIA_D / 2), ALL_L)
        grid.claim_drill(nid, c[0], c[1], VIA_DRILL / 2, 0.25, VIA_DRILL / 2)


def route_net(net, cls, width, allow_rip=True):
    """Connect every group of a net. Returns (ok, nets ripped up on the way)."""
    nid = NETID[net]
    ripped = set()
    while True:
        gs = groups(net_items(net))
        if len(gs) <= 1:
            return True, ripped
        gs.sort(key=lambda g: -len(g))
        src = cells(gs[0])
        dst = np.zeros_like(src)
        for g in gs[1:]:
            dst |= cells(g)
        free, vfree, _ = grid.usable(cls, nid)
        path = grid.route(free, vfree, src, dst)
        victims = set()
        if path is None and allow_rip:
            free_s, vfree_s, soft = grid.usable(cls, nid, soft=True)
            path = grid.route(free_s, vfree_s, src, dst, soft=soft)
            if path is not None:
                grid.add_history(cls, path, nid)
                victims = grid.nets_claiming(cls, path, nid)
                vcells = [(0, i, j) for k, (L, i, j) in enumerate(path) if k and path[k - 1][0] != L]
                victims |= grid.nets_claiming("via", vcells, nid)
                free = free_s & ~soft            # straighten only through cells nobody else claims
        if path is None:
            print(f"    {net}: no path from a group of {len(gs[0])} items to {len(gs) - 1} other group(s) "
                  f"(searched {getattr(grid, 'last_expanded', 0)} cells)", flush=True)
            return False, ripped
        if victims:
            id2net = {v: k for k, v in NETID.items()}
            for v in victims:
                rip(id2net[v])
                ripped.add(id2net[v])
            free, vfree, _ = grid.usable(cls, nid)       # the way is clear now: search again for a clean path
            clean = grid.route(free, vfree, src, dst)
            if clean is not None:
                path = clean
        runs, vias = grid.simplify(path, free)
        commit(net, width, runs, vias)


# The maker's matrix lines broken by the new parts first, then the new nets, shortest first; supplies last.
ORDER = [*[(n, "sig", SIG_W) for n in MATRIX_NETS], ("GND", "pwr2", PWR2_W),
         ("SDB", "sig", SIG_W), ("R_EXT", "sig", SIG_W), ("C_FILT", "sig", SIG_W), ("LED_SDA", "sig", SIG_W), ("LED_SCL", "sig", SIG_W),
         ("D7_RX", "sig", SIG_W), ("D6_TX", "sig", SIG_W), ("SAO_GPIO1", "sig", SIG_W), ("SAO_GPIO2", "sig", SIG_W),
         ("SDA", "sig", SIG_W), ("SCL", "sig", SIG_W), ("OFF_SENSE", "sig", SIG_W),
         ("BAT+", "pwr", PWR_W), ("VSAO", "pwr2", PWR2_W), ("V3V3", "pwr2", PWR2_W)]
# Ground goes last and rips nothing: what it cannot reach by track, the back ground pour joins (checked by DRC).
CLS_OF = {n: (c, w) for n, c, w in ORDER}
FALLBACK = {"pwr": ("pwr2", PWR2_W), "pwr2": ("sig", SIG_W)}
ROUTE_CACHE = os.environ.get("DONUT_CACHE") or os.path.join(HERE, "routes.json")
CACHED = os.path.exists(ROUTE_CACHE) and not os.environ.get("DONUT_REROUTE") and not os.environ.get("NOROUTE")
if CACHED:            # the router's last result (it takes about an hour): replay it instead of routing again
    for net, r in json.load(open(ROUTE_CACHE)).items():
        recommit_cached = {"segs": [(L, tuple(a), tuple(b), w) for L, a, b, w in r["segs"]], "vias": [tuple(c) for c in r["vias"]]}
        ROUTES[net] = {"segs": [], "vias": []}
        nid = NETID[net]
        for L, a, b, w in recommit_cached["segs"]:
            ROUTES[net]["segs"].append((L, a, b, w))
            grid.claim_shape(nid, ("seg", a[0], a[1], b[0], b[1], w / 2), (L,))
        for c in recommit_cached["vias"]:
            ROUTES[net]["vias"].append(c)
            grid.claim_shape(nid, ("circle", c[0], c[1], VIA_D / 2), ALL_L)
    print("routing replayed from hardware/routes.json (set DONUT_REROUTE=1 to route again)")
queue = [n for n, _, _ in ORDER] if not (os.environ.get("NOROUTE") or CACHED) else []
if os.environ.get("DONUT_NEW_FIRST"):              # experiment: the new connections before the maker's broken ones
    queue = [n for n in queue if n not in MATRIX_NETS] + [n for n in queue if n in MATRIX_NETS]
FAILED, n_rips, t_route = [], 0, time.time()
RIP_LIMIT = int(os.environ.get("DONUT_RIPS", "60"))
TIME_LIMIT = 1200.0                                # seconds: the router stops and reports rather than looping
while queue:
    if time.time() - t_route > TIME_LIMIT:
        print(f"  ROUTER TIME LIMIT: giving up on {queue}", flush=True)
        FAILED += queue
        break
    net = queue.pop(0)
    cls, w = CLS_OF[net]
    t1 = time.time()
    ok, ripped = route_net(net, cls, w, allow_rip=n_rips < RIP_LIMIT)
    while not ok and cls in FALLBACK:                 # a supply that will not fit at full width: try narrower
        cls, w = FALLBACK[cls]
        CLS_OF[net] = (cls, w)
        ok, more = route_net(net, cls, w, allow_rip=n_rips < RIP_LIMIT)
        ripped |= more
    n_rips += len(ripped)
    for v in ripped:
        if v not in queue:
            queue.append(v)
    if not ok:
        FAILED.append(net)
    r = ROUTES.get(net, {"segs": [], "vias": []})
    print(f"  {net}: {'ok' if ok else 'FAILED'} ({cls}), {len(r['segs'])} tracks, {len(r['vias'])} vias, "
          f"ripped {sorted(ripped)} in {time.time() - t1:.1f} s", flush=True)


# Repair pass: for each net still broken, rip what blocks it, route it, then re-route every net it ripped without
# ripping anything further. Keep the result only if all of them succeed; otherwise put everything back as it was.
# The board can only get better in this pass.
def recommit(net, saved):
    nid = NETID[net]
    r = ROUTES.setdefault(net, {"segs": [], "vias": []})
    for L, a, b, w in saved["segs"]:
        r["segs"].append((L, a, b, w))
        grid.claim_shape(nid, ("seg", a[0], a[1], b[0], b[1], w / 2), (L,))
    for c in saved["vias"]:
        r["vias"].append(c)
        grid.claim_shape(nid, ("circle", c[0], c[1], VIA_D / 2), ALL_L)
        grid.claim_drill(nid, c[0], c[1], VIA_DRILL / 2, 0.25, VIA_DRILL / 2)


def broken():
    return [n for n, _, _ in ORDER if len(groups(net_items(n))) > 1]


CLS_OF.setdefault("GND", ("pwr2", PWR2_W))
for rnd in range(2 if not (os.environ.get("NOROUTE") or CACHED) else 0):
    todo = broken()
    if not todo:
        break
    for net in todo:
        snap = {k: {"segs": list(v["segs"]), "vias": list(v["vias"])} for k, v in ROUTES.items()}
        cls, w = CLS_OF[net]
        if cls == "pwr":
            cls, w = "pwr2", PWR2_W
        ok, ripped = route_net(net, cls, w, allow_rip=True)
        good = ok and all(route_net(v, *CLS_OF[v], allow_rip=False)[0] for v in sorted(ripped))
        if not good:
            for k in {net} | ripped:
                rip(k)
                if k in snap:
                    recommit(k, snap[k])
        print(f"  repair {rnd} {net}: {'fixed' if good else 'no luck'} (ripped and re-routed {sorted(ripped)})", flush=True)

for cls, w in (("pwr2", PWR2_W), ("sig", SIG_W)):
    if CACHED or os.environ.get("NOROUTE"):
        break
    ok, _ = route_net("GND", cls, w, allow_rip=False)
    print(f"  GND ({cls}): {'ok' if ok else 'left to the pour'}, {len(ROUTES.get('GND', {'segs': []})['segs'])} tracks", flush=True)
    if ok:
        break
GND_LEFT = len(groups(net_items("GND"))) - 1
FAILED = [n for n in dict.fromkeys(FAILED) if len(groups(net_items(n))) > 1]

if not CACHED and not os.environ.get("NOROUTE"):
    json.dump({n: {"segs": [[L, list(a), list(b), w] for L, a, b, w in r["segs"]], "vias": [list(c) for c in r["vias"]]}
               for n, r in ROUTES.items()}, open(ROUTE_CACHE, "w"))
# ---- prune the dead ends: maker tracks or vias that now lead nowhere (their other end was lifted) -----------------
PADS_BY_NET = {}
for fp in real_fps:
    for pad in fp.Pads():
        if pad.GetNetname() and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            PADS_BY_NET.setdefault(pad.GetNetname(), []).append((pad_shape(pad), 0 if pad.IsOnLayer(F_Cu) else 1))
mk_t = [[n, a, b, w, KL.index(L), True] for n, a, b, w, L in tracks_kept]
mk_v = [[n, c, d, True] for n, c, d in vias_kept]
rt_t = [(n, a, b, w, L) for n, r in ROUTES.items() for L, a, b, w in r["segs"]]
rt_v = [(n, c) for n, r in ROUTES.items() for c in r["vias"]]


def end_ok(net, L, e, me):
    for sh, pl in PADS_BY_NET.get(net, []):
        if pl == L and shape_dist(sh, e[0], e[1]) < 0.01:
            return True
    for n, c, d, alive in mk_v:
        if alive and n == net and math.hypot(c[0] - e[0], c[1] - e[1]) < MAKER_VIA_D / 2:
            return True
    for n, c in rt_v:
        if n == net and math.hypot(c[0] - e[0], c[1] - e[1]) < VIA_D / 2:
            return True
    for t in mk_t:
        if t is not me and t[5] and t[0] == net and t[4] == L and \
                float(Grid.d_segment(np.array(e[0]), np.array(e[1]), t[1][0], t[1][1], t[2][0], t[2][1])) <= t[3] / 2 + 0.01:
            return True
    for n, a, b, w, L2 in rt_t:
        if n == net and L2 == L and float(Grid.d_segment(np.array(e[0]), np.array(e[1]), a[0], a[1], b[0], b[1])) <= w / 2 + 0.01:
            return True
    return False


def body_touched(t):
    """Does any new (routed) copper end on this track anywhere along it? Then it stays."""
    n, a, b, w, L = t[0], t[1], t[2], t[3], t[4]
    for n2, a2, b2, w2, L2 in rt_t:
        if n2 == n and L2 == L:
            for e in (a2, b2):
                if float(Grid.d_segment(np.array(e[0]), np.array(e[1]), a[0], a[1], b[0], b[1])) <= w / 2 + w2 / 2:
                    return True
    for n2, c in rt_v:
        if n2 == n and float(Grid.d_segment(np.array(c[0]), np.array(c[1]), a[0], a[1], b[0], b[1])) <= w / 2 + VIA_D / 2:
            return True
    return False


n_pruned_t = n_pruned_v = 0
changed = True
while changed:
    changed = False
    for t in mk_t:
        if t[5] and not (end_ok(t[0], t[4], t[1], t) and end_ok(t[0], t[4], t[2], t)) and not body_touched(t):
            t[5] = False
            n_pruned_t += 1
            changed = True
    for v in mk_v:
        if not v[3]:
            continue
        n_conn = sum(1 for t in mk_t if t[5] and t[0] == v[0] and min(math.hypot(t[1][0] - v[1][0], t[1][1] - v[1][1]),
                                                                      math.hypot(t[2][0] - v[1][0], t[2][1] - v[1][1])) < MAKER_VIA_D / 2)
        n_conn += 2 * sum(1 for n, a, b, w, L in rt_t if n == v[0] and float(Grid.d_segment(np.array(v[1][0]), np.array(v[1][1]), a[0], a[1], b[0], b[1])) < MAKER_VIA_D / 2 + w / 2)
        n_conn += sum(1 for sh, pl in PADS_BY_NET.get(v[0], []) if shape_dist(sh, v[1][0], v[1][1]) < MAKER_VIA_D / 2)
        if n_conn <= 1:
            v[3] = False
            n_pruned_v += 1
            changed = True
for n, a, b, w, L, alive in mk_t:
    if alive:
        add_track(n, a, b, w, KL[L])
for n, c, d, alive in mk_v:
    if alive:
        add_via(n, c, d, MAKER_VIA_D)
print(f"pruned {n_pruned_t} dead-end tracks and {n_pruned_v} vias of the maker's left behind by the lifting")

ROUTED = {"tracks": 0, "vias": 0, "length": 0.0}
for net, r in ROUTES.items():
    for L, a, b, w in r["segs"]:
        add_track(net, a, b, w, KL[L])
        ROUTED["tracks"] += 1
        ROUTED["length"] += math.hypot(b[0] - a[0], b[1] - a[1])
    for c in r["vias"]:
        add_via(net, c)
        ROUTED["vias"] += 1
print(f"routing: {ROUTED['tracks']} new tracks ({ROUTED['length']:.0f} mm), {ROUTED['vias']} new vias, {n_rips} rip-ups, "
      f"unrouted {FAILED}, {time.time() - t_route:.0f} s")

pcbnew.SaveBoard(OUT, board)                 # keep the routing even if a later step stops

# ---- back copper: ground poured over whatever room the routing leaves ------------------------------------------
def rule_area(shape_pts, layer, name):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayer(layer)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName(name)
    ol = pcbnew.SHAPE_POLY_SET()
    ol.NewOutline()
    for x, y in shape_pts:
        ol.Append(FromMM(x), FromMM(y))
    z.SetOutline(ol)
    board.Add(z)


for k, (c, r) in enumerate(TEST_KEEP):          # the XIAO's own test pads underneath: no copper of ours under them
    rule_area([(c[0] + r * math.cos(a * math.pi / 16), c[1] + r * math.sin(a * math.pi / 16)) for a in range(32)], B_Cu, f"XIAO test pad {k + 1}")

gz = pcbnew.ZONE(board)
gz.SetLayer(B_Cu)
gz.SetNet(nets["GND"])
gz.SetZoneName("GND back")
gol = pcbnew.SHAPE_POLY_SET()
gol.NewOutline()
_o = grown(poly(OUTER), -EDGE_GND)
_ch = _o.COutline(0)
for v in range(_ch.PointCount()):
    gol.Append(_ch.CPoint(v).x, _ch.CPoint(v).y)
gol.NewHole()
_h = grown(hole_poly, EDGE_GND)
_ch = _h.COutline(0)
for v in range(_ch.PointCount()):
    gol.Append(_ch.CPoint(v).x, _ch.CPoint(v).y)
gz.SetOutline(gol)
gz.SetLocalClearance(FromMM(0.2))
gz.SetMinThickness(FromMM(0.2))
gz.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
gz.SetThermalReliefGap(FromMM(0.25))
gz.SetThermalReliefSpokeWidth(FromMM(0.3))
gz.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
board.Add(gz)
board.BuildConnectivity()
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
print(f"back ground pour: {area_mm2(gz.GetFilledPolysList(B_Cu)):.0f} mm2 in {gz.GetFilledPolysList(B_Cu).OutlineCount()} pieces")

# ---- front solder mask art: the bare "dough" rim and the ring round the hole ------------------------------------
wavy_outer, inner = None, None
for pts in E["stop_polys"]:
    xs = [p[0] for p in pts]
    if max(xs) - min(xs) > 50:          # the outer one: the icing's wavy edge, then a cut out to a square frame
        k = max(i for i, p in enumerate(pts) if i > 0 and abs(p[0] - pts[0][0]) < 1e-6 and abs(p[1] - pts[0][1]) < 1e-6) \
            if any(abs(p[0] - pts[0][0]) < 1e-6 and abs(p[1] - pts[0][1]) < 1e-6 for p in pts[1:]) else None
        wavy_outer = [T(x, y) for x, y in pts[:k]]
    else:
        inner = [T(x, y) for x, y in pts]
icing = poly(wavy_outer)
icing.BooleanSubtract(poly(inner))
dough = pcbnew.SHAPE_POLY_SET(board_poly)
dough.BooleanSubtract(icing)
# The maker left the copper inside the bare rim uncovered. Here every track and via on the front is kept under mask
# (a 0.1 mm mask margin round it), so no exposed copper of two nets can be bridged; the LED pads stay open as before.
tent = pcbnew.SHAPE_POLY_SET()
for t in board.Tracks():
    if t.IsOnLayer(F_Cu):
        t.TransformShapeToPolygon(tent, F_Cu, FromMM(0.1), ERR, pcbnew.ERROR_OUTSIDE)
tent.Simplify()
dough.BooleanSubtract(tent)
dough.Simplify()
add_filled(board, dough, pcbnew.F_Mask)
print(f"front mask art: {dough.OutlineCount()} bare areas, {area_mm2(dough):.0f} mm2 of bare board")

# ---- back silkscreen: the maker's credit, his twelve logos, and the SAO++ labels -----------------------------------
# Silk is checked on its own 0.1 mm raster: nothing may land on a back pad, under a back part, off the board, or on
# other silk. The maker's credit block (DO OR DONUT / @davedarko / 2019) sat exactly where the SAO connector now is,
# so it moves, unchanged in wording and size, to the upper left (seen from the front; upper right seen from the back),
# turned to follow the ring. Logos that would end up under a part move to the nearest free spot, unchanged.
SG = 0.1
sx0, sy0 = CX - R_OUT - 0.5, CY - R_OUT - 0.5
snx = sny = int((2 * R_OUT + 1) / SG) + 1
SXs, SYs = np.meshgrid(sx0 + np.arange(snx) * SG, sy0 + np.arange(sny) * SG)


def raster(ps, grow=0.0):
    """Cells (on the silk raster) inside a SHAPE_POLY_SET grown by `grow` mm (even-odd over outlines and holes)."""
    ps = grown(ps, grow) if grow else pcbnew.SHAPE_POLY_SET(ps)
    out = np.zeros((sny, snx), bool)
    for i in range(ps.OutlineCount()):
        chains = [ps.Outline(i)] + [ps.Hole(i, k) for k in range(ps.HoleCount(i))]
        bx = ps.Outline(i).BBox()
        j0 = max(0, int((ToMM(bx.GetLeft()) - sx0) / SG) - 1)
        j1 = min(snx, int((ToMM(bx.GetRight()) - sx0) / SG) + 2)
        i0 = max(0, int((ToMM(bx.GetTop()) - sy0) / SG) - 1)
        i1 = min(sny, int((ToMM(bx.GetBottom()) - sy0) / SG) + 2)
        X, Y = SXs[i0:i1, j0:j1], SYs[i0:i1, j0:j1]
        m = np.zeros_like(X, bool)
        for ch in chains:
            px = np.array([ToMM(ch.CPoint(v).x) for v in range(ch.PointCount())])
            py = np.array([ToMM(ch.CPoint(v).y) for v in range(ch.PointCount())])
            qx, qy = np.roll(px, -1), np.roll(py, -1)
            for k in range(len(px)):
                if py[k] == qy[k]:
                    continue
                m ^= ((py[k] > Y) != (qy[k] > Y)) & (X < (qx[k] - px[k]) * (Y - py[k]) / (qy[k] - py[k]) + px[k])
        out[i0:i1, j0:j1] |= m
    return out


silk_block = np.zeros((sny, snx), bool)
_rr = np.hypot(SXs - CX, SYs - CY)
silk_block |= _rr > R_OUT - 0.5
silk_block |= raster(grown(hole_poly, 0.5))
for fp in real_fps:
    if fp.IsFlipped():
        silk_block |= raster(courtyard(fp))
        for pad in fp.Pads():
            silk_block |= raster(pad_poly(pad, B_Cu), 0.2)
used = np.zeros_like(silk_block)
_fs = pcbnew.SHAPE_POLY_SET()                       # the parts' own silkscreen outlines count as used too
for fp in real_fps:
    if fp.IsFlipped():
        for g in fp.GraphicalItems():
            if g.GetLayer() == B_SilkS:
                g.TransformShapeToPolygon(_fs, B_SilkS, 0, ERR, pcbnew.ERROR_OUTSIDE)
PART_SILK = raster(_fs, 0.2)
used |= PART_SILK

# -- the maker's credit, three lines exactly as he set them (2.54 mm vector font, 12 % stroke), turned to follow the ring
CREDIT = [t for t in E["texts"] if t["layer"] == "26" and t["size"] > 2]
CREDIT.sort(key=lambda t: -t["y"])                      # top line first
assert [t["text"] for t in CREDIT] == ["DO OR DONUT", "@davedarko", "2019"], CREDIT
LINE = CREDIT[0]["y"] - CREDIT[1]["y"]                  # his line spacing, 3.81 mm


def make_text(txt, pos, size, angle, thick):
    pos = (float(pos[0]), float(pos[1]))
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetMirrored(True)
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    t.SetTextAngleDegrees(angle)
    t.SetPosition(P(*pos))
    return t


def text_raster(texts, grow=0.25):
    ps = pcbnew.SHAPE_POLY_SET()
    for t in texts:
        t.TransformShapeToPolygon(ps, B_SilkS, 0, ERR, pcbnew.ERROR_OUTSIDE)
    return raster(ps, grow)


def credit_at(theta, rc, tilt=0.0):
    """The credit block centred at angle theta (front view, deg CCW from 3 o'clock), radius rc, its three lines
    parallel, text 'up' pointing outward, turned a further `tilt` degrees."""
    th = math.radians(theta)
    up = math.radians(theta + tilt)
    out = (math.cos(up), -math.sin(up))                  # the text's 'up', screen coordinates
    c = (CX + rc * math.cos(th), CY - rc * math.sin(th))
    ts = []
    for k, t in enumerate(CREDIT):
        off = (1 - k) * LINE                             # top line outermost
        pos = (float(c[0] + off * out[0]), float(c[1] + off * out[1]))
        ts.append(make_text(t["text"], pos, t["size"], CREDIT_SIGN * (theta + tilt - 90), t["size"] * t["ratio"] / 100))
    return ts


CREDIT_SIGN = 1           # checked on the back render: the lines run along the ring and read correctly from the back
best = None
for theta in [150 + d * s_ for d in range(0, 50) for s_ in (1, -1)][1:]:
    for tilt in (0, -10, 10, -20, 20, -30, 30):
        for rc in [18.5 - 0.5 * k for k in range(11)]:
            ts = credit_at(theta, rc, tilt)
            m = text_raster(ts)
            bad = int((m & silk_block).sum())
            if best is None or bad < best[4]:
                best = (theta, rc, ts, m, bad, tilt)
            if bad == 0:
                break
        if best[4] == 0:
            break
    if best[4] == 0:
        break
CREDIT_THETA, CREDIT_R, credit_texts, m, CREDIT_OVERLAP, CREDIT_TILT = best
for t in credit_texts:
    board.Add(t)
used |= m
print(f"maker's credit moved to {CREDIT_THETA:.0f} deg, {CREDIT_R:.2f} mm from the centre, tilt {CREDIT_TILT} deg "
      f"(seen from the front); silk cells on parts: {CREDIT_OVERLAP}")

# -- logos: each stays where the maker put it unless a part now covers it; then it moves to the nearest free spot
LOGO_MOVED = {}
logo_shapes = {}
for name, el in sorted(EL.items(), key=lambda kv: int(kv[0][2:]) if kv[0].startswith("U$") else 0):
    if el["package"] != "DAVEDARKO2_LOGO":
        continue
    sp = pcbnew.SHAPE_POLY_SET()
    for layer, width, pts in el["polygons"]:
        q = poly([T(x, y) for x, y in pts])
        q.Inflate(FromMM(width / 2), ROUND, ERR)
        sp.BooleanAdd(q)
    sp.Simplify()
    logo_shapes[name] = sp
stay = {n: raster(sp, 0.2) for n, sp in logo_shapes.items()}
movers = [n for n in logo_shapes if (stay[n] & (silk_block | used)).any()]     # under a part, or under the moved credit
SPIRAL = sorted(((dx * 0.25, dy * 0.25) for dx in range(-80, 81) for dy in range(-80, 81)), key=lambda d: math.hypot(*d))
silk = pcbnew.SHAPE_POLY_SET()
for n, sp in logo_shapes.items():
    if n not in movers:
        silk.BooleanAdd(sp)
        used |= stay[n]

# -- SAO++ labels (0.8-1.0 mm), each at the free spot nearest where it belongs
LABEL_LOG = []
LABEL_MISSING = []


def label(txt, near, size=0.8, angle=0.0, reach=14.0):
    t = make_text(txt, near, size, angle, size * 0.15)
    for dx, dy in SPIRAL:
        if math.hypot(dx, dy) > reach:
            break
        t.SetPosition(P(float(near[0] + dx), float(near[1] + dy)))
        m = text_raster([t], 0.15)
        bb = t.GetBoundingBox()
        inside = all(math.hypot(ToMM(x) - CX, ToMM(y) - CY) < R_OUT - 0.6
                     for x in (bb.GetLeft(), bb.GetRight()) for y in (bb.GetTop(), bb.GetBottom()))
        if inside and not (m & (silk_block | used)).any():
            board.Add(t)
            used[:] |= m
            LABEL_LOG.append((txt, mm(t.GetPosition())))
            return t
    print("NO ROOM FOR LABEL", txt)
    LABEL_MISSING.append(txt)
    return None


def toward_centre(p_, d):
    v = np.subtract((CX, CY), p_)
    v = v / np.linalg.norm(v)
    return (p_[0] + v[0] * d, p_[1] + v[1] * d)


j1p = pp(conn, "1")
label("1", (j1p[0] - 3.2, j1p[1]), 0.9)
s1, s2, s4 = pp(sw, "1"), pp(sw, "2"), pp(sw, "4")
sw_tan = SW_ANGLE - 90                                   # switch labels run along its edge
label("SAO", toward_centre(s1, 1.6), 0.8, CREDIT_SIGN * sw_tan)
label("OFF", toward_centre(s2, 1.6), 0.8, CREDIT_SIGN * sw_tan)
label("USB/BAT", toward_centre(s4, 1.9), 0.8, CREDIT_SIGN * sw_tan)
jp1, jp2 = pp(jst, "1"), pp(jst, "2")
label("+", toward_centre(jp1, 2.6), 1.2)
label("-", toward_centre(jp2, 2.6), 1.2)
label("LiPo 3.7V", toward_centre(mm(jst.GetPosition()), 6.0), 0.8)
label("SAO++ rA", (CX, CY - 12.5), 0.9)
label("USB: NOT ON SAO", (CX + 12.0, CY + 18.0), 0.8)
label("XIAO C3/S3/C6", (CX - 12.0, CY + 18.0), 0.8)
print("labels:", LABEL_LOG)

# -- logos a part now covers: nearest free visible spot; if the back has none left, the nearest spot under a part's
#    body (still printed, unchanged, but hidden by the part) that is clear of every pad
pad_block = np.zeros_like(silk_block)
pad_block |= _rr > R_OUT - 0.5
pad_block |= raster(grown(hole_poly, 0.5))
for fp in real_fps:
    if fp.IsFlipped():
        for pad in fp.Pads():
            pad_block |= raster(pad_poly(pad, B_Cu), 0.3)
LOGO_HIDDEN = []
SPIRAL_WIDE = sorted(((dx * 0.5, dy * 0.5) for dx in range(-90, 91) for dy in range(-90, 91)), key=lambda d: math.hypot(*d))
for n in movers:
    sp = logo_shapes[n]
    base = raster(sp, 0.2)
    ii, jj = np.nonzero(base)
    found = None
    for block, hidden, spiral in ((silk_block, False, SPIRAL), (pad_block, True, SPIRAL_WIDE)):
        for dx, dy in spiral:
            di, dj = int(round(dy / SG)), int(round(dx / SG))
            i2, j2 = ii + di, jj + dj
            if i2.min() < 0 or j2.min() < 0 or i2.max() >= sny or j2.max() >= snx:
                continue
            occ = (used & ~PART_SILK) if hidden else used      # hidden under a body, a part's own outline may cross it
            if not (block[i2, j2] | occ[i2, j2]).any():
                found = (di, dj, i2, j2, hidden)
                break
        if found:
            break
    assert found, f"no room at all for logo {n}"
    di, dj, i2, j2, hidden = found
    moved = pcbnew.SHAPE_POLY_SET(sp)
    moved.Move(VECTOR2I(FromMM(dj * SG), FromMM(di * SG)))
    used[i2, j2] = True
    silk.BooleanAdd(moved)
    LOGO_MOVED[n] = (round(dj * SG, 2), round(di * SG, 2))
    if hidden:
        LOGO_HIDDEN.append(n)
silk.Simplify()
add_filled(board, silk, B_SilkS)
print(f"logos moved (dx, dy mm): {LOGO_MOVED}; hidden under a part: {LOGO_HIDDEN}")

ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.127)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.127)
_nc = ds.m_NetSettings.GetDefaultNetclass()          # the maker's 5 mil rules for the whole board (written to the .kicad_pro)
_nc.SetClearance(FromMM(0.127))
_nc.SetTrackWidth(FromMM(0.15))
_nc.SetViaDiameter(FromMM(VIA_D))       # (the maker's own vias keep his 0.686 mm)
_nc.SetViaDrill(FromMM(VIA_DRILL))
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
assert not EDGE_BAD, f"pads closer than 0.25 mm to an edge: {EDGE_BAD}"
assert not FAILED, f"unrouted: {FAILED}"
sys.stdout.flush()
os._exit(0)          # KiCad 10's Python can crash while tidying up at exit, after the board is saved
