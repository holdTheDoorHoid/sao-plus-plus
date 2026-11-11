#!/usr/bin/env python3
"""Build spacehuhn.kicad_pcb from scratch: the maker's outline and art (art/art.json), the parts and the routing.

Run with KiCad 10's Python, from the repo root:
  python3 boards/spacehuhn/hardware/extract_art.py          (only if art/art.json is missing; system Python)
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/spacehuhn/hardware/build_board.py

The original is an Eagle board (original/rev3/badge_spacehuhn.brd, the newest of the maker's three revisions). KiCad
10 does not load it from Python, so hardware/extract_art.py reads the Eagle XML and writes the outline and the art as
art/art.json, mirrored into KiCad's front view (the maker drew the art on Eagle's bottom). This script draws:
  front  - copper over the whole board (the maker's ground pour on the art side, now plain art copper) under the
           maker's solder-mask openings (the chicken's face and beak, nine stars: bare gold) and the maker's
           silkscreen (helmet, polka dots, comb, eyes, wing). Copper is cleared 1.6 mm round each eye's centre so the
           LED behind it can shine through; the mask and silkscreen over the eyes are left exactly as drawn.
  back   - the SAO connector, the power switch, the coin-cell clip, two reverse-mount white LEDs behind the eyes and
           their resistors, routed on the back copper only (no vias). The rest of the back copper is the GND net.
           The maker's back art is kept: his gold logo (mask openings over the ground copper), the two credit lines
           and his two bare-copper "markers used for multicolor PCBs".
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_Cu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "spacehuhn"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
MARKER_CLEAR = 0.4064   # the maker's polygon isolation (16 mil) round his two marker rectangles, kept as drawn
EDGE = 0.55         # back copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
FRONT_EDGE = 0.40   # front art copper: as the maker's pour (Eagle's 15 mil copper-to-dimension = 0.38 mm), except
                    # within reach of a panel tab, where it steps back to 0.55 mm
TRACK = 0.40
WINDOW = 1.6        # radius kept free of copper on both sides round each LED centre (house rule)

# ---- placement (centre x, y) ------------------------------------------------------------------
# Back of the board, seen through from the front: the maker's two credit lines run across the upper middle, his two
# marker rectangles sit above them, his logo is on the right at eye height, and the eyes are right of centre.
# Everything new therefore goes in the lower half (see README "Where the parts went"):
#   cell clip lower left, open side to the left edge (the cell slides in from there);
#   connector lower middle, just right of the clip's closed end, key slot up;
#   switch on the straight bottom edge of the helmet's base, knob down.
BAT = (111.5, 132.5)
BAT_OPEN = (-1.0, 0.0)
CONN = (131.3, 137.6)
SW_X = 125.0
LEDS = {"D1": tuple(ART["leds"]["LED1"]), "D2": tuple(ART["leds"]["LED2"])}    # D1 front eye (left), D2 back eye
ANODE_AT = {"D1": (-1.55, 0.0), "D2": (-1.55, 0.0)}      # anode pads toward the resistors, on the left of each eye
RES = {"R1": (125.6, 129.4), "R2": (132.2, 126.9)}        # both stand upright, pad 2 (LED side) at the top

# ---- outline -----------------------------------------------------------------------------------
body = poly(ART["outline"])
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f}, {body.Outline(0).PointCount()} points")

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
    assert fp is not None, f"missing footprint {name} in {LIB}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    return fp


def place(ref, pos, want):
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    fp = load(ref, pos)
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
    link(fp, ref)
    return fp


def padpos(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


_EDGE_CHAIN = body.Outline(0)


def clearance_to_edge(fp):
    """Smallest gap (mm) between any copper pad of fp and the board edge, measured on the pad outlines."""
    worst = 99.0
    for pad in fp.Pads():
        if not pad.IsOnLayer(B_Cu) or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            continue
        pp = pad_poly(pad, B_Cu)
        ch = pp.Outline(0)
        for i in range(ch.PointCount()):
            a, b = ch.CPoint(i), ch.CPoint((i + 1) % ch.PointCount())
            n = max(1, int(ToMM((b - a).EuclideanNorm()) / 0.05))
            for k in range(n):
                q = VECTOR2I(int(a.x + (b.x - a.x) * k / n), int(a.y + (b.y - a.y) * k / n))
                d = ToMM(int(math.sqrt(_EDGE_CHAIN.SquaredDistance(q, True))))
                worst = min(worst, d if body.Contains(q) else -d)
    return round(worst, 3)


# connector: VCC (pin 1) top row, left in front view, as on Mad Cat; key slot toward the top
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))

# switch: on the bottom edge of the helmet's base, knob pointing down. Pushed as far down as its lower solder tabs
# allow (they must stay 0.3 mm inside the edge), so as much knob as possible shows below the base.
sw = None
for k in range(0, 400):
    sy = 149.5 - k * 0.01
    sw_try = (SW_X, sy)
    if sw is None:
        sw = place("SW1", sw_try, ("1", (SW_X + 3.0, sy - 1.43)))
    else:
        sw.SetPosition(P(*sw_try))
    tabs = [p for p in sw.Pads() if p.GetNumber() == "" and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH]
    ok = True
    for t in tabs:
        off = pad_poly(t, B_Cu, 0.30)
        off.BooleanSubtract(body)
        ok &= area_mm2(off) < 1e-6
    if ok:
        break
SW = (SW_X, round(sy, 2))
assert padpos(sw, "1")[0] > SW_X, "switch pin 1 should be on the right (front view)"
_knob = SW[1] + 3.1
_edge_below = max(ToMM(y) for y in [body.Outline(0).CPoint(i).y for i in range(body.Outline(0).PointCount())
                                     if abs(ToMM(body.Outline(0).CPoint(i).x) - SW_X) < 2.2])
print(f"switch at {SW}: knob tip y {_knob:.2f}; lowest board edge across the knob's travel y {_edge_below:.2f}"
      f" -> knob shows {_knob - _edge_below:.2f} mm")

# LEDs at the maker's LED centres (the middle of each eye), resistors upright below-left of each
led, res = {}, {}
for ref, (x, y) in LEDS.items():
    dx, dy = ANODE_AT[ref]
    led[ref] = place(ref, (x, y), ("2", (x + dx, y + dy)))
    r = "R" + ref[1:]
    rx, ry = RES[r]
    res[r] = place(r, (rx, ry), ("2", (rx, ry - 0.825)))

# battery clip
bat = load("BT1", BAT)


def _open_dir():
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(BAT[1] - ToMM(c.y), BAT[0] - ToMM(c.x)))


_want = math.degrees(math.atan2(BAT_OPEN[1], BAT_OPEN[0]))
_choice = None
for base in (0, 90, 180, 270):
    bat.SetOrientationDegrees(base)
    if abs((_open_dir() - _want + 180) % 360 - 180) < 45:
        _choice = base
assert _choice is not None
# 0.1 degree off square: at exact right angles KiCad 10 reports the clip's two-part courtyard as malformed (as Lumpy)
bat.SetOrientationDegrees(_choice - 0.1)
link(bat, "BT1")
bat.SetDuplicatePadNumbersAreJumpers(True)   # the clip is one piece of metal joining its two "+" pads (as on Lumpy)
_stop = None
for it in bat.GraphicalItems():              # its own silk (arrow, "+", closed-end line) moves to the fab drawing;
    if it.GetLayer() == B_SilkS:             # the arrow would print off the board; labels are added below instead
        it.SetLayer(pcbnew.B_Fab)
        if isinstance(it, pcbnew.PCB_SHAPE) and it.GetShape() == pcbnew.SHAPE_T_SEGMENT and ToMM(it.GetLength()) > 15:
            _stop = it
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_out = pcbnew.SHAPE_POLY_SET(_cell)
_out.BooleanSubtract(body)
assert area_mm2(_out) < 1e-6, f"the cell overhangs the edge ({area_mm2(_out):.2f} mm2)"
_cm = 99.0
for i in range(_cell.Outline(0).PointCount()):
    _cm = min(_cm, ToMM(int(math.sqrt(_EDGE_CHAIN.SquaredDistance(_cell.Outline(0).CPoint(i), True)))))
print(f"battery clip angle {bat.GetOrientationDegrees():.1f}; cell stays {_cm:.2f} mm inside the edge")

NEW = set(PARTS)
for fp in board.GetFootprints():
    assert fp.GetReference() in NEW
    m = clearance_to_edge(fp)
    print(f"  {fp.GetReference()}: pads at least {m} mm inside the edge")
    assert m >= 0.3, f"{fp.GetReference()} has a pad within {m} mm of the board edge"


# ---- routing (back copper only) -----------------------------------------------------------------
TRACKS = []


def route(net, pts, width=TRACK, clear=CLEAR):
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
        TRACKS.append((t, clear))


j1 = padpos(conn, "1")
j3 = padpos(conn, "3")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
bt_low = padpos(bat, "1", pick=lambda p: -p[1])          # the clip pad nearer the switch (the lower one)
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")
d1a, d2a = padpos(led["D1"], "2"), padpos(led["D2"], "2")
PAD_TOP = s1[1] - 0.75                                   # top end of the switch's signal pads

# each LED: resistor pad 2 -> up to the anode
route("LED1_A", [r1b, (r1b[0], d1a[1] + 0.4), (d1a[0], d1a[1] + 0.4)])
route("LED2_A", [r2b, (r2b[0], d2a[1] + 0.4), (d2a[0], d2a[1] + 0.4)])

# switched supply: switch pin 3 -> up under the connector's plastic body, left of its pads -> R1, then right to R2
TRUNK = round(j1[0] - 2.2, 3)
route("VLOAD", [s3, (s3[0], PAD_TOP - 0.6), (TRUNK, PAD_TOP - 0.6 - (TRUNK - s3[0])), (TRUNK, r1a[1] + 1.2), (r1a[0], r1a[1] + 1.2), r1a])
route("VLOAD", [(r1a[0], r1a[1] + 1.2), (r2a[0], r1a[1] + 1.2), r2a])

# badge 3.3 V: switch pin 1 -> up between the connector's left two pad columns -> pin 1 from below
GAP_X = round((j1[0] + j3[0]) / 2, 3)
ROWGAP_Y = CONN[1]
route("VSAO", [s1, (s1[0], PAD_TOP - 0.4), (GAP_X, PAD_TOP - 0.4 - abs(GAP_X - s1[0])), (GAP_X, ROWGAP_Y), (j1[0], ROWGAP_Y), (j1[0], j1[1] + 1.6)])

# coin cell +: switch pin 4 -> up and left, below the cell -> the clip's lower pad
route("VBAT", [s4, (s4[0], PAD_TOP - 0.3), (s4[0] - 1.0, PAD_TOP - 1.3), (bt_low[0] + 3.0, PAD_TOP - 1.3), bt_low])

# ---- back copper: GND everywhere else ----------------------------------------------------------
markers = [poly(r) for r in ART["markers_copper"]]
art = pcbnew.SHAPE_POLY_SET(inner)
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
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for x, y in LEDS.values():
    add_circle(cut, P(x, y), WINDOW)
for m in markers:
    cut.Append(grown(m, MARKER_CLEAR))
cut.Simplify()
art.BooleanSubtract(cut)
for ref in LEDS:                      # fill the sharp horns the light window leaves beside each cathode pad
    for pad in led[ref].Pads():
        if pad.GetNetCode() == gnd_code:
            art.BooleanAdd(pad_poly(pad, B_Cu, 0.3))
art.Simplify()
_open = grown(grown(art, -0.1), 0.1)  # strips of copper narrower than 0.2 mm would only flake: cut them away
_thin = pcbnew.SHAPE_POLY_SET(art)
_thin.BooleanSubtract(_open)
_strips = pcbnew.SHAPE_POLY_SET()
for i in range(_thin.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(_thin.Polygon(i))
    if area_mm2(one) > 0.008:
        _strips.Append(grown(one, 0.03))
_strips.Simplify()
print(f"thin ground-copper strips removed: {_strips.OutlineCount()}, {area_mm2(_strips):.3f} mm2")
art.BooleanSubtract(_strips)
art.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = n_art = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    touches = area_mm2(both) > 0.01
    add_filled(board, piece, B_Cu, nets["GND"] if touches else None)
    n_gnd += touches
    n_art += not touches
    print(f"  back copper piece {i}: {area_mm2(piece):.1f} mm2, {'GND' if touches else 'no GND pad'}, bbox",
          [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain", n_art)


def eagle_polys(key, grow):
    """The maker's filled shapes. Eagle draws each with a pen of the polygon's width, so the real shape is the vertex
    path grown by half that width; growing also closes the hairline cut-in lines Eagle uses to draw holes."""
    ps = pcbnew.SHAPE_POLY_SET()
    for pts in ART[key]:
        one = poly(pts)
        one.Simplify()
        ps.BooleanAdd(one)
    ps.Inflate(FromMM(grow), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    ps.Simplify()
    return ps


# the maker's back art: two bare-copper marker rectangles (net-less, as in his file) with their mask openings, and
# his gold logo: mask openings over the ground copper
for m in markers:
    add_filled(board, m, B_Cu)
_mk_mask = pcbnew.SHAPE_POLY_SET()
for r in ART["markers_mask"]:
    _mk_mask.Append(poly(r))
_mk_mask.Simplify()
logo = eagle_polys("logo_mask", ART["logo_grow"])
_lg = pcbnew.SHAPE_POLY_SET(logo)
_lg.BooleanSubtract(art)
print(f"logo {area_mm2(logo):.2f} mm2, of which over no ground copper: {area_mm2(_lg):.4f} mm2")
assert area_mm2(_lg) < 1e-4, "something cuts the ground copper under the maker's logo"
back_mask = pcbnew.SHAPE_POLY_SET(_mk_mask)
back_mask.Append(logo)
back_mask.Simplify()
add_filled(board, back_mask, pcbnew.B_Mask)

# ---- front: the maker's art --------------------------------------------------------------------
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front = grown(body, -FRONT_EDGE)
_tabzone = pcbnew.SHAPE_POLY_SET()
for t in json.load(open(os.path.join(HERE, "..", "production", "panel.json")))["tabs"]:
    add_circle(_tabzone, P(*t["near"]), 3.5)
_tabzone.Simplify()
_ring = pcbnew.SHAPE_POLY_SET(front)
_ring.BooleanSubtract(inner)
_ring.BooleanIntersection(_tabzone)
front.BooleanSubtract(_ring)
holes = pcbnew.SHAPE_POLY_SET()
for x, y in LEDS.values():
    add_circle(holes, P(x, y), WINDOW)
holes.Append(pegs)
holes.Simplify()
front.BooleanSubtract(holes)
front.Simplify()
add_filled(board, front, F_Cu)

mask = eagle_polys("mask", ART["mask_grow"])
_bare = pcbnew.SHAPE_POLY_SET(mask)
_bare.BooleanSubtract(front)
print(f"front mask openings {area_mm2(mask):.1f} mm2; of which over no copper: {area_mm2(_bare):.3f} mm2")
mask.BooleanIntersection(body)
add_filled(board, mask, pcbnew.F_Mask)

silk = eagle_polys("silk", ART["silk_grow"])
_s_area = area_mm2(silk)
silk.BooleanIntersection(body)
print(f"front silk {_s_area:.1f} mm2, inside the outline {area_mm2(silk):.1f} mm2")
add_filled(board, silk, pcbnew.F_SilkS)
_eye = pcbnew.SHAPE_POLY_SET()
for x, y in LEDS.values():
    add_circle(_eye, P(x, y), WINDOW)
_eye.BooleanIntersection(silk)
print(f"eye windows (2 x {math.pi * WINDOW ** 2:.1f} mm2) covered by the maker's white eye silkscreen: {area_mm2(_eye):.2f} mm2")


# ---- back silkscreen: the maker's two credit lines, then the SAO++ labels -----------------------
def add_text(txt, x, y, size, thick, h=pcbnew.GR_TEXT_H_ALIGN_CENTER, v=pcbnew.GR_TEXT_V_ALIGN_CENTER):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetMirrored(True)
    t.SetHorizJustify(h)
    t.SetVertJustify(v)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


def text_box(t):
    bb = t.GetBoundingBox()
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


CREDITS = []
for c in ART["texts"]:
    # Eagle anchors a text at its bottom left as read; read from the back, that is the bottom RIGHT in front view.
    ax, ay = c["anchor_bottom_left_back_view"]
    t = add_text(c["text"], ax, ay, c["size"], max(0.15, c["size"] * c["ratio_percent"] / 100),
                 pcbnew.GR_TEXT_H_ALIGN_LEFT, pcbnew.GR_TEXT_V_ALIGN_BOTTOM)
    x0, y0, x1, y1 = text_box(t)
    t.Move(P(ax - x1, 0))
    CREDITS.append(t)
    print(f"  maker's credit {c['text']!r}: {[round(v, 2) for v in text_box(t)]}")

LABELS = [("SAO", s1[0] + 0.3, PAD_TOP - 1.0, 0.8), ("OFF", SW[0], PAD_TOP - 2.2, 0.8), ("BAT", s4[0] - 1.6, PAD_TOP - 2.2, 0.8),
          ("1", j1[0] - 1.6, j1[1] - 1.95, 0.9),
          ("CR2032", 103.8, 122.9, 0.8), ("+ UP", 103.8, 124.3, 0.8),
          ("SPACEHUHN", 139.0, 114.4, 0.9), ("SAO++ rA", 139.0, 116.0, 0.8)]
_parts_keep = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(pcbnew.B_Mask):
            _parts_keep.Append(pad_poly(pad, B_Cu, 0.1))
_parts_keep.Append(back_mask)
_parts_keep.Simplify()
for txt, x, y, size in LABELS + [(c.GetText(), None, None, None) for c in CREDITS]:
    t = add_text(txt, x, y, size, size * 0.15) if x is not None else [c for c in CREDITS if c.GetText() == txt][0]
    x0, y0, x1, y1 = text_box(t)
    box = poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    _o = pcbnew.SHAPE_POLY_SET(box)
    _o.BooleanSubtract(grown(body, -0.2))
    assert area_mm2(_o) < 1e-6, f"label {txt!r} reaches the board edge"
    _h = pcbnew.SHAPE_POLY_SET(box)
    _h.BooleanIntersection(_parts_keep)
    assert area_mm2(_h) < 1e-6, f"label {txt!r} prints on a pad or the maker's back art"
    for t2, _c in TRACKS:
        if x is None:                   # the maker's lettering: no track may run through it
            _tt = pcbnew.SHAPE_POLY_SET()
            t2.TransformShapeToPolygon(_tt, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
            _tt.BooleanIntersection(box)
            assert area_mm2(_tt) < 1e-6, f"a track runs through the maker's lettering {txt!r}"

# connector silk strokes that would print off the board, or on the maker's lettering, go to the fab drawing
for it in conn.GraphicalItems():
    if it.GetLayer() == B_SilkS and isinstance(it, pcbnew.PCB_SHAPE):
        bb = it.GetBoundingBox()
        for q in (bb.GetOrigin(), bb.GetEnd()):
            if not grown(body, -0.2).Contains(q):
                it.SetLayer(pcbnew.B_Fab)
                break


# ---- real gaps between parts (written into the .kicad_dru where keep-out boxes overlap) ------------
def rect_of(fp, layer):
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer and isinstance(g, pcbnew.PCB_SHAPE) and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
            ps = pcbnew.SHAPE_POLY_SET()
            g.TransformShapeToPolygon(ps, layer, 0, ERR, pcbnew.ERROR_OUTSIDE)
            return ps
    raise KeyError(fp.GetReference())


def gap(a, b):
    """Smallest distance between two polygon sets (0 if they touch or overlap), sampled every 0.05 mm."""
    t = pcbnew.SHAPE_POLY_SET(a)
    t.BooleanIntersection(b)
    if area_mm2(t) > 0:
        return 0.0
    best = 99.0
    for src, dst in ((a, b), (b, a)):
        for k in range(src.OutlineCount()):
            ch = src.Outline(k)
            for i in range(ch.PointCount()):
                p0, p1 = ch.CPoint(i), ch.CPoint((i + 1) % ch.PointCount())
                n = max(1, int(ToMM((p1 - p0).EuclideanNorm()) / 0.05))
                for j in range(n):
                    q = VECTOR2I(int(p0.x + (p1.x - p0.x) * j / n), int(p0.y + (p1.y - p0.y) * j / n))
                    for m in range(dst.OutlineCount()):
                        best = min(best, ToMM(int(math.sqrt(dst.Outline(m).SquaredDistance(q, True)))))
    return round(best, 2)


_shroud = poly([(CONN[0] - 7.65, CONN[1] - 4.45), (CONN[0] + 7.65, CONN[1] - 4.45), (CONN[0] + 7.65, CONN[1] + 4.45), (CONN[0] - 7.65, CONN[1] + 4.45)])
_stop_ps = pcbnew.SHAPE_POLY_SET()
_stop.TransformShapeToPolygon(_stop_ps, pcbnew.B_Fab, 0, ERR, pcbnew.ERROR_OUTSIDE)
GAPS = {
    "clip outline to J1 shroud": gap(rect_of(bat, pcbnew.B_Fab), _shroud),
    "cell to J1 shroud": gap(_cell, _shroud),
    "cell to SW1 body": gap(_cell, rect_of(sw, pcbnew.B_Fab)),
    "clip outline to SW1 body": gap(rect_of(bat, pcbnew.B_Fab), rect_of(sw, pcbnew.B_Fab)),
    "J1 shroud to SW1 body": gap(_shroud, rect_of(sw, pcbnew.B_Fab)),
    "J1 shroud to R1 body": gap(_shroud, rect_of(res["R1"], pcbnew.B_Fab)),
    "J1 shroud to R2 body": gap(_shroud, rect_of(res["R2"], pcbnew.B_Fab)),
    "clip outline to R1 body": gap(rect_of(bat, pcbnew.B_Fab), rect_of(res["R1"], pcbnew.B_Fab)),
}
for k, v in GAPS.items():
    print(f"  gap {k}: {v} mm")

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("centre of the board's outline:", [round(v, 2) for v in mm(body.BBox().Centre())], "connector centre", CONN)
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
