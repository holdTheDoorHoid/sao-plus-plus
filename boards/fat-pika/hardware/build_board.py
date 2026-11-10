#!/usr/bin/env python3
"""Rebuild fat-pika.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/fat-pika/hardware/build_board.py

What it does
  - loads original/Pikachu_PCB.kicad_pcb (KiCad 4) so every art layer and the outline stay exactly as drawn
  - removes the 4-pin through-hole header, the two TOPLEDs, the single shared resistor and the old tracks
  - places the SAO++ parts on the back and routes them (single layer, back copper)
  - turns the back copper art into the GND net, as the original did, clearing it around the new pads and tracks

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(HERE, "..", "original", "Pikachu_PCB.kicad_pcb")
OUT = os.path.join(HERE, "fat-pika.kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND art
TRACK = 0.40
ERR = FromMM(0.005)

# ---- placement (centre x, y) ------------------------------------------------------------------
CONN = (143.5, 105.5)       # lower right, ~12 mm above the foot
SW = (134.5, 114.9)         # bottom edge; knob tip ends ~0.5 mm past the edge
BAT = (120.0, 100.5)         # cell slides in from the left edge
D1 = (130.683, 85.9028)     # cheeks: unchanged from the original
D2 = (106.1974, 86.0044)
R1 = (133.0, 89.9)
R2 = (109.2, 85.2)


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def add_circle(ps, c, r_mm, n=96):
    """Append a circle (as an n-gon whose corners sit on the radius) to a SHAPE_POLY_SET."""
    import math
    ps.NewOutline()
    for k in range(n):
        a = 2 * math.pi * k / n
        ps.Append(c.x + int(FromMM(r_mm) * math.cos(a)), c.y + int(FromMM(r_mm) * math.sin(a)))


def mm(v):
    return (round(ToMM(v.x), 3), round(ToMM(v.y), 3))


# KiCad 10's Python crashes on Remove(), so the old parts are cut out of the file text before loading:
# the four old track segments, the two cheek keep-out zones, the old header / LEDs / resistor, and the
# back copper art polygons (read separately from the untouched original, then re-added as netted copper).
import re
import tempfile


def blocks(txt, opener, indent=2):
    """Yield (start, end) of each '(opener ...)' block at the given indent, by matching parentheses."""
    for m in re.finditer(r"\n" + " " * indent + r"\(" + opener + r"[ \n]", txt):
        i = m.start() + 1 + indent
        depth = 0
        for j in range(i, len(txt)):
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    yield m.start(), j + 1
                    break


_txt = open(SRC, encoding="utf-8").read()
_cut = []
for a_, b_ in blocks(_txt, "segment"):
    _cut.append((a_, b_))
for a_, b_ in blocks(_txt, "zone"):
    _cut.append((a_, b_))
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 4267, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    blk = _txt[a_:b_]
    ref = re.search(r"\(fp_text reference (\S+)", blk).group(1)
    if ref in ("X1", "D1", "D2", "R1"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["D1", "D2", "R1", "X1"], _gone
for a_, b_ in sorted(_cut, reverse=True):
    _txt = _txt[:a_] + _txt[b_:]
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer B.Cu)" in _txt[b_ - 40:b_] or "(layer F.Cu)" in _txt[b_ - 40:b_]]
assert len(_polys) == 127, f"expected 125 back + 2 front copper art polygons, found {len(_polys)}"
for a_, b_ in sorted(_polys, reverse=True):
    _txt = _txt[:a_] + _txt[b_:]
_tmp = os.path.join(tempfile.mkdtemp(), "Pikachu_PCB.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

art = pcbnew.SHAPE_POLY_SET()
front = pcbnew.SHAPE_POLY_SET()
_orig = pcbnew.LoadBoard(SRC)
for fp in _orig.GetFootprints():
    for it in fp.GraphicalItems():
        if not hasattr(it, "GetShape") or it.GetShape() != pcbnew.SHAPE_T_POLY:
            continue
        if it.GetLayer() == B_Cu:
            art.Append(it.GetPolyShape())
        elif it.GetLayer() == pcbnew.F_Cu:
            front.Append(it.GetPolyShape())
assert art.OutlineCount() >= 125, "back copper art not found"
assert front.OutlineCount() >= 2, "front copper art not found"
art.Simplify()
front.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []

# The 2018 outline is 4267 short segments with stray zero-area loops that KiCad 10 cannot chain, so it is
# replaced by the same path as two clean closed polygons (outer edge + the cut-out by the tail); see outline.json.
import json
_ol = json.load(open(os.path.join(HERE, "outline.json")))
body = pcbnew.SHAPE_POLY_SET()
body.NewOutline()
for x, y in _ol["outer"]:
    body.Append(FromMM(x), FromMM(y))
for h in _ol["holes"]:
    body.NewHole()
    for x, y in h:
        body.Append(FromMM(x), FromMM(y))
for ring in [_ol["outer"]] + _ol["holes"]:
    e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in ring:
        ps.Append(FromMM(x), FromMM(y))
    e.SetPolyShape(ps)
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetFilled(False)
    e.SetWidth(FromMM(0.1))
    board.Add(e)
# Copper stops 0.28 mm short of the edge (the 2018 art ran copper over the edge, which fabs trim anyway);
# this also drops the stray rectangle the 2018 SVG export left outside the board.
# (Shrink the outer edge and grow the cut-out separately: shrinking a polygon that has a hole turns KiCad's
# internal seam between hole and edge into a real 0.5 mm slit.)
inner = pcbnew.SHAPE_POLY_SET()
inner.NewOutline()
for x, y in _ol["outer"]:
    inner.Append(FromMM(x), FromMM(y))
inner.Inflate(-FromMM(0.28), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
for h in _ol["holes"]:
    hp = pcbnew.SHAPE_POLY_SET()
    hp.NewOutline()
    for x, y in h:
        hp.Append(FromMM(x), FromMM(y))
    hp.Inflate(FromMM(0.28), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    inner.BooleanSubtract(hp)
art.BooleanIntersection(inner)

# ---- the circuit (shared with the schematic generator) ------------------------------------------
import uuid
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PADNETS = {p["ref"]: p.get("nets", {}) for p in CIRCUIT["parts"]}
_NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")          # same namespace as tools/gen_schematic.py


sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_symbols import SYMBOLS  # noqa: E402
PINNAMES = {p["ref"]: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for p in CIRCUIT["parts"]}


def sch_uuid(what):
    return str(uuid.uuid5(_NS, "fat-pika:" + what))


# ---- nets ---------------------------------------------------------------------------------------
nets = {}
for n in sorted({n for d in PADNETS.values() for n in d.values()}):
    ni = pcbnew.NETINFO_ITEM(board, n)
    board.Add(ni)
    nets[n] = ni


# ---- footprints ---------------------------------------------------------------------------------
def link(fp, ref, name):
    """Tie the footprint to its schematic symbol so KiCad's schematic-parity check passes."""
    fp.SetFPID(pcbnew.LIB_ID("sao-plus-plus", name))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
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


def place(lib, name, ref, value, pos, want):
    """Place on the back, then pick the rotation that puts pad `want[0]` at `want[1]`."""
    fp = pcbnew.FootprintLoad(lib, name)
    assert fp is not None, f"missing footprint {name} in {lib}"
    fp.SetReference(ref)
    fp.SetValue(value)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber() == want[0]:
                px, py = mm(pad.GetPosition())
                d = abs(px - want[1][0]) + abs(py - want[1][1])
                if best is None or d < best[0]:
                    best = (d, rot)
    assert best[0] < 0.05, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref, name)
    return fp


conn = place(LIB, "SAOPP_CONN-01_BoxHeader_2x03_P2.54mm_SMD_XFCN_BH254VS-6P", "J1", "SAO v1.69bis", CONN,
             ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))          # VCC: top row, left in front view = same corner as the 2018 header
sw = place(LIB, "SAOPP_SW-01_Slide_SP3T_CK_PCM13SMTR", "SW1", "SAO / OFF / BAT", SW,
           ("1", (SW[0] + 3.0, SW[1] - 1.43)))          # pin 1 toward the connector, knob toward the bottom edge
led1 = place(LIB, "SAOPP_LED-10_1206_ReverseMount_ThroughBoard", "D1", "red", D1, ("2", (D1[0], D1[1] + 1.55)))
led2 = place(LIB, "SAOPP_LED-10_1206_ReverseMount_ThroughBoard", "D2", "red", D2, ("2", (D2[0], D2[1] + 1.55)))
r1 = place(LIB, "SAOPP_R_0603_1608Metric", "R1", "1.3k", R1, ("1", (R1[0], R1[1] + 0.825)))
r2 = place(LIB, "SAOPP_R_0603_1608Metric", "R2", "1.3k", R2, ("1", (R2[0], R2[1] - 0.825)))

# battery: both clip pads are "1", so choose the rotation by where the closed end lands (right = away from the left edge)
bat = pcbnew.FootprintLoad(LIB, "SAOPP_BAT-01_CR2032_SMD_TE_BAT-HLD-001")
bat.SetReference("BT1")
bat.SetValue("CR2032")
board.Add(bat)
bat.SetPosition(P(*BAT))
bat.Flip(P(*BAT), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
for rot in (90, 270):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    if ToMM(fab[0].GetBoundingBox().GetCenter().x) > BAT[0]:
        break
else:
    raise AssertionError("battery clip orientation not found")
link(bat, "BT1", "SAOPP_BAT-01_CR2032_SMD_TE_BAT-HLD-001")

# the 2018 art lives in footprints with no schematic symbol: mark them board-only
NEW = {"J1", "SW1", "BT1", "D1", "D2", "R1", "R2"}
for fp in board.GetFootprints():
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

for fp in (conn, sw, bat, led1, led2, r1, r2):
    fp.Reference().SetVisible(False)       # the back is busy with art; refs live on the fab layer and in the README


def padpos(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- routing (back copper only) -----------------------------------------------------------------
def route(net, pts, width=TRACK):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append(t)


j1 = padpos(conn, "1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
bt_top = padpos(bat, "1", pick=lambda p: p[1])
bt_bot = padpos(bat, "1", pick=lambda p: -p[1])
d1a, d2a = padpos(led1, "2"), padpos(led2, "2")
r1a, r1b = padpos(r1, "1"), padpos(r1, "2")
r2a, r2b = padpos(r2, "1"), padpos(r2, "2")

# badge 3.3 V: connector pin 1 -> switch pin 1 (runs under the connector body)
route("VSAO", [j1, (138.7, j1[1]), (138.7, 110.6), (s1[0], 111.8), s1])
# coin cell +: lower clip pad -> switch pin 4, and a link round the cell pad to the upper clip pad
route("VBAT", [bt_bot, (130.1, bt_bot[1]), (s4[0], 112.4), s4])
route("VBAT", [bt_top, (129.6, bt_top[1]), (129.6, 110.5), (130.1, bt_bot[1])])
# switched supply: switch pin 3 -> both LED resistors
route("VLOAD", [s3, (s3[0], 111.6), (134.6, 110.0), (134.6, 83.9), (133.0, 82.3), (128.0, 82.3), (126.1, 84.2), (r2a[0], 84.2), r2a])
route("VLOAD", [r1a, (134.6, r1a[1])])
# resistor -> LED anode
route("LED1_A", [r1b, (r1b[0], 88.4), (132.05, d1a[1]), d1a])
route("LED2_A", [r2b, (r2b[0], 87.0), (108.65, d2a[1]), d2a])

# ---- GND art: restore the old routing channels, then clear around everything that is not GND ----
# The 2018 board left bare channels in the art for its tracks and header. Fill only those: the gaps are
# intersected with hand-drawn windows over the old channels, so lettering and characters keep their gaps.
def window(pts):
    w = pcbnew.SHAPE_POLY_SET()
    w.NewOutline()
    for x, y in pts:
        w.Append(FromMM(x), FromMM(y))
    return w


OLD_CHANNELS = [
    [(102.5, 86.3), (135.6, 86.3), (135.6, 91.6), (102.5, 91.6)],                       # LED-to-LED row
    [(127.3, 80.3), (135.6, 80.3), (135.6, 86.3), (127.3, 86.3)],                       # around old D1
    [(102.5, 80.3), (109.2, 80.3), (109.2, 86.3), (102.5, 86.3)],                       # around old D2
    [(127.8, 91.6), (135.6, 91.6), (135.6, 97.5), (148.5, 111.0), (148.5, 120.5), (140.5, 120.5),
     (140.5, 114.5), (127.8, 102.0)],                                                   # resistor, run to the header, header
    [(109.3, 92.3), (123.8, 92.3), (123.8, 97.2), (109.3, 97.2)],                       # "DEF CON 26" lettering: the cell pad cuts it in half,
]                                                                                       # so it goes (the tail still says DEF CON 26)
gaps = pcbnew.SHAPE_POLY_SET(inner)
gaps.BooleanSubtract(art)
windows = pcbnew.SHAPE_POLY_SET()
for w in OLD_CHANNELS:
    windows.BooleanAdd(window(w))
gaps.BooleanIntersection(windows)
gaps.Simplify()
print("restored old track channels, area mm2:", round(gaps.Area() / 1e12, 1))
art.BooleanAdd(gaps)

# solid copper under the cell so the bare cell pad is whole
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)
art.BooleanAdd(disc)

cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            continue
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in TRACKS:
    t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for c in (D1, D2):                                   # light path for the cheeks
    add_circle(cut, P(*c), 1.6)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# every separate piece becomes its own shape: pieces touching a GND pad carry the GND net, the rest stay plain art
gnd_pads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gnd_code]
n_gnd = n_art = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    touches = any(piece.Collide(p.GetPosition(), FromMM(0.05)) for p in gnd_pads)
    piece.Fracture()
    for j in range(piece.OutlineCount()):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
        s.SetPolyShape(pcbnew.SHAPE_POLY_SET(piece.Polygon(j)))
        s.SetLayer(B_Cu)
        s.SetFilled(True)
        s.SetWidth(0)
        if touches:
            s.SetNet(nets["GND"])
        board.Add(s)
    n_gnd += touches
    n_art += not touches
print("back copper pieces: GND", n_gnd, "plain art", n_art)


# ---- front copper art: same shapes as 2018, minus the hole the old through-hole header left ---------
fgaps = pcbnew.SHAPE_POLY_SET(body)
fgaps.BooleanSubtract(front)
fgaps.Simplify()
old_header = P(144.3228, 117.2464)
for i in range(fgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(fgaps.Polygon(i))
    if one.Contains(old_header):
        assert one.Area() / 1e12 < 60, "front gap at the old header is bigger than a header; refusing to fill it"
        front.BooleanAdd(one)
        print("filled old header window on the front, area mm2:", round(one.Area() / 1e12, 1))
        break
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(pegs)
front.BooleanIntersection(inner)
front.Simplify()
front.Fracture()
for j in range(front.OutlineCount()):
    s_ = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    s_.SetPolyShape(pcbnew.SHAPE_POLY_SET(front.Polygon(j)))
    s_.SetLayer(pcbnew.F_Cu)
    s_.SetFilled(True)
    s_.SetWidth(0)
    board.Add(s_)

# ---- back silkscreen labels ---------------------------------------------------------------------
def label(txt, x, y, size=1.0, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)


label("SAO", 139.0, 111.9, 0.8)
label("OFF", SW[0], 110.6, 0.8)
label("BAT", 130.0, 111.9, 0.8)
label("CR2032 + SIDE UP", BAT[0], BAT[1] + 13.3, 0.8)
label("SAO++ rA", 141.5, 97.6, 0.9)
label("1", j1[0] - 1.7, j1[1] - 2.6, 0.9)

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle("Fat Pika - SAO++ edition")
board.GetTitleBlock().SetRevision("A")
board.GetTitleBlock().SetComment(0, "Original design: TwinkleTwinkie, DEF CON 26 (2018), hackaday.io/project/158665")
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
