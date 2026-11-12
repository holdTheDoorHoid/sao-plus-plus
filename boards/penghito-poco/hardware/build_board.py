#!/usr/bin/env python3
"""Build penghito-poco.kicad_pcb from scratch: the maker's outline and art (art/art.json), the parts and the routing.

Run with KiCad 10's Python, from the repo root:
  python3 boards/penghito-poco/hardware/extract_art.py          (only if art/art.json is missing; system Python)
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/penghito-poco/hardware/build_board.py

The original is an Eagle board (original/penghitopoco.brd). KiCad 10 does not load it from Python, so
hardware/extract_art.py reads the Eagle XML and writes the outline and the art as art/art.json, already turned upright
and seen from the art side (see that script for why). This script draws:
  front  - copper over the whole board (the maker's ground pour on the art side, now plain art copper), the maker's
           solder-mask openings (horn, beak, two feet: bare gold) and the maker's silkscreen (face, belly, eye rims),
           plus a 2 mm bare-board window in the middle of each eye where the LED shines through
  back   - the SAO connector, the power switch, the coin-cell clip, two reverse-mount LEDs behind the eyes and their
           resistors, routed on the back copper only (no vias); the rest of the back copper is the GND net
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

SLUG = "penghito-poco"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

# ---- scale (rev B) --------------------------------------------------------------------------------
# The whole outline and all the maker's art are scaled up by SCALE about the centre of the board's bounding box, so the
# coin cell and its clip fit inside the outline (owner decision 2026-11-12, see README "Size"). 42.1 x 43.0 mm at 1.0;
# 58.9 x 60.2 mm at 1.4. Parts keep their real size; only the two eye LEDs move with the art (they are the pupils).
# Smaller factors were searched (1.15, 1.2, 1.25, 1.3, 1.35) and none fits the cell, its clip, the connector (3 mm from
# the edge) and the switch without overlapping keep-out boxes. The part positions below are for SCALE = 1.4.
SCALE = 1.40
_RAW = json.load(open(os.path.join(HERE, "..", "art", "art.json")))
_xs = [p[0] for p in _RAW["outline"]]
_ys = [p[1] for p in _RAW["outline"]]
CENTRE = ((min(_xs) + max(_xs)) / 2, (min(_ys) + max(_ys)) / 2)


def _sc(p):
    return [CENTRE[0] + (p[0] - CENTRE[0]) * SCALE, CENTRE[1] + (p[1] - CENTRE[1]) * SCALE]


ART = {"outline": [_sc(p) for p in _RAW["outline"]],
       "silk": [[_sc(p) for p in pts] for pts in _RAW["silk"]],
       "mask": [[_sc(p) for p in pts] for pts in _RAW["mask"]],
       "leds": {k: _sc(v) for k, v in _RAW["leds"].items()}}

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # copper (both sides) stops this far short of the board edge (the maker's pour stopped at 0.38 mm;
                    # 0.55 keeps it clear of the panel's mouse-bite holes)
FRONT_EDGE = 0.40   # front art copper: as the maker's pour (0.38 mm), except at panel tabs (see below)
TRACK = 0.40
WINDOW = 1.6        # radius kept free of copper on both sides around each LED centre (house rule)
MASK_WINDOW = 1.0   # radius of the bare-board window in the front solder mask over each LED (2 mm across)

# ---- placement (centre x, y) ------------------------------------------------------------------
# The eyes sit in the middle of the board, so the 20 mm cell and the 15 mm connector still cannot both go on the centre
# line (that needs SCALE 1.5, see README). Same arrangement as rev A, now with room: connector right of centre below the
# right eye, near where the maker's header was; cell lower left with the clip's open side toward the left edge; switch on
# the bottom edge between the feet. Found by a grid search over positions (keep-out boxes may not overlap; clip pads
# >= 1 mm, cell >= 0.3 mm and connector shroud >= 3 mm inside the edge).
CONN = (130.4, 127.4)
BAT = (110.4, 127.9)
BAT_ROT = 89.9      # pads vertical (89.9, not 90: KiCad 10 calls the clip's keep-out "malformed" at exact right angles)
BAT_OPEN = (-1.0, 0.0)   # the open side faces the left edge; the cell slides in from there
SW_X = 121.54
LEDS = {"D1": tuple(ART["leds"]["LED1"]), "D2": tuple(ART["leds"]["LED2"])}    # D1 right eye, D2 left eye (front view)
# where each LED's anode pad sits relative to its centre: toward the middle of the face, where its resistor is.
ANODE_AT = {"D1": (-1.55, 0.0), "D2": (1.55, 0.0)}
RES_PAD2 = {"R1": +1, "R2": -1}           # resistor pad 2 (LED side) toward its LED: +1 = right of centre
RES = {"R1": (LEDS["D1"][0] - 4.3, LEDS["D1"][1]), "R2": (LEDS["D2"][0] + 4.3, LEDS["D2"][1])}

# ---- outline -----------------------------------------------------------------------------------
body = poly(ART["outline"])
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f}")

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

# switch: on the bottom edge between the feet, knob pointing down. Pushed as far down as its lower solder tabs allow
# (they must stay 0.3 mm inside the edge), so as much knob as possible shows past the toes.
sw = None
for k in range(0, 800):
    sy = by1 - 1.5 - k * 0.01
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
print(f"switch at {SW}: knob tip y {_knob:.2f}; lowest board edge across the knob's travel y {_edge_below:.2f}")

# LEDs at the maker's LED centres (the middle of each eye), resistors toward the middle of the face
led, res = {}, {}
for ref, (x, y) in LEDS.items():
    dx, dy = ANODE_AT[ref]
    led[ref] = place(ref, (x, y), ("2", (x + dx, y + dy)))
    r = "R" + ref[1:]
    rx, ry = RES[r]
    res[r] = place(r, (rx, ry), ("2", (rx + RES_PAD2[r] * 0.825, ry)))

# battery clip
bat = load("BT1", BAT)


def _open_dir():
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(BAT[1] - ToMM(c.y), BAT[0] - ToMM(c.x)))


# measure which way the open side faces at the two right angles nearest BAT_ROT (rectangles stay rectangles there)
_want = math.degrees(math.atan2(BAT_OPEN[1], BAT_OPEN[0]))
_choice = None
for base in (90, 270):
    bat.SetOrientationDegrees(base)
    if abs((_open_dir() - _want + 180) % 360 - 180) < 45:
        _choice = base
assert _choice is not None
bat.SetOrientationDegrees(_choice + (BAT_ROT - 90))
link(bat, "BT1")
bat.SetDuplicatePadNumbersAreJumpers(True)   # the clip is one piece of metal joining its two "+" pads (as on Lumpy)
_stop = None
for it in bat.GraphicalItems():              # its own silk (arrow, "+", closed-end line) would print off the board
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
        if isinstance(it, pcbnew.PCB_SHAPE) and it.GetShape() == pcbnew.SHAPE_T_SEGMENT and ToMM(it.GetLength()) > 15:
            _stop = it                       # the 16 mm line across the clip's closed end (its back stop)
# the back stop stands at cell height beside the connector's shroud: keep it at least 0.3 mm clear
_shroud = poly([(CONN[0] - 7.65, CONN[1] - 4.45), (CONN[0] + 7.65, CONN[1] - 4.45), (CONN[0] + 7.65, CONN[1] + 4.45), (CONN[0] - 7.65, CONN[1] + 4.45)])
_band = pcbnew.SHAPE_POLY_SET()
_stop.TransformShapeToPolygon(_band, pcbnew.B_Fab, FromMM(0.3), ERR, pcbnew.ERROR_OUTSIDE)
_band.BooleanIntersection(_shroud)
assert area_mm2(_band) < 1e-6, "the clip's closed end comes within 0.3 mm of the connector shroud"
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_cell.BooleanSubtract(body)
_deep = max(min(math.hypot(ToMM(_cell.Outline(0).CPoint(i).x) - ToMM(body.Outline(0).CPoint(j).x),
                           ToMM(_cell.Outline(0).CPoint(i).y) - ToMM(body.Outline(0).CPoint(j).y))
                for j in range(body.Outline(0).PointCount()))
            for i in range(_cell.Outline(0).PointCount())) if _cell.OutlineCount() else 0
print(f"cell outside the outline: {area_mm2(_cell):.1f} mm2 in {_cell.OutlineCount()} piece(s), reaching {_deep:.2f} mm past the edge")
print("battery clip angle", round(bat.GetOrientationDegrees(), 1))

# rev B: the cell, its clip and the clip's 17 mm ground disc are all inside the outline (rev A trimmed the disc and the
# cell overhung the left edge by 3.3 mm). Checked here so a change to SCALE or BAT cannot quietly bring it back.
_disc = [p for p in bat.Pads() if p.GetNumber() == "2"][0]
_x = pcbnew.SHAPE_POLY_SET(pad_poly(_disc, B_Cu))
_x.BooleanSubtract(grown(body, -0.55))
assert area_mm2(_x) < 1e-6, "the clip's ground disc reaches the edge copper limit"
assert _cell.OutlineCount() == 0, "the coin cell overhangs the board edge"
_cin = pcbnew.SHAPE_POLY_SET()
add_circle(_cin, P(*BAT), 10.0)
_cin.BooleanSubtract(grown(body, -0.3))
assert area_mm2(_cin) < 1e-6, "the coin cell comes within 0.3 mm of the board edge"
_fab_body = None
for g in bat.GraphicalItems():
    if g.GetLayer() == pcbnew.B_Fab and isinstance(g, pcbnew.PCB_SHAPE) and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
        _fab_body = pcbnew.SHAPE_POLY_SET()
        g.TransformShapeToPolygon(_fab_body, pcbnew.B_Fab, 0, ERR, pcbnew.ERROR_OUTSIDE)
        break
_fab_body.BooleanSubtract(grown(body, -0.25))
assert area_mm2(_fab_body) < 1e-6, "the clip's body comes within 0.25 mm of the board edge"

NEW = set(PARTS)
for fp in board.GetFootprints():
    assert fp.GetReference() in NEW
    m = clearance_to_edge(fp)
    print(f"  {fp.GetReference()}: pads at least {m} mm inside the edge")
    assert m >= 0.3, f"{fp.GetReference()} has a pad within {m} mm of the board edge"
    if fp.GetReference() == "BT1":
        assert m >= 1.0, f"the clip's pads are only {m} mm inside the edge (want 1 mm)"
_sh = pcbnew.SHAPE_POLY_SET(poly([(CONN[0] - 7.65, CONN[1] - 4.45), (CONN[0] + 7.65, CONN[1] - 4.45),
                                  (CONN[0] + 7.65, CONN[1] + 4.45), (CONN[0] - 7.65, CONN[1] + 4.45)]))
_sh.BooleanSubtract(grown(body, -3.0))
assert area_mm2(_sh) < 1e-6, "the connector's plastic shroud comes within 3 mm of the board edge"
print("connector shroud: at least 3 mm inside the edge")


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
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
bt_low = padpos(bat, "1", pick=lambda p: -p[1])          # the clip pad nearer the switch (the lower one)
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")

# each LED: resistor pad 2 -> straight across to the anode
route("LED1_A", [r1b, padpos(led["D1"], "2")])
route("LED2_A", [r2b, padpos(led["D2"], "2")])

# switched supply: switch pin 3 -> up between the cell's ground disc and the connector -> between the eyes, where it
# feeds R2 (left eye, higher) at the top and R1 (right eye) on the way
TRUNK = 122.4
route("VLOAD", [s3, (s3[0], SW[1] - 3.5), (TRUNK, SW[1] - 4.9), (TRUNK, r2a[1]), r2a])
route("VLOAD", [(TRUNK, r1a[1]), r1a])

# badge 3.3 V: switch pin 1 -> up the left side of the connector -> into pin 1 (top left, front view) from the left
VSAO_X = 125.6
route("VSAO", [s1, (s1[0], SW[1] - 3.5), (VSAO_X, SW[1] - 4.5), (VSAO_X, j1[1]), j1])

# coin cell +: switch pin 4 -> left -> the clip's lower pad
route("VBAT", [s4, (s4[0], bt_low[1]), bt_low])

# ---- back copper: GND everywhere else ----------------------------------------------------------
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
cut.Simplify()
art.BooleanSubtract(cut)
# the light window cuts the ground copper to sharp horns where it meets each LED's cathode pad; a 0.3 mm collar of
# copper round the cathode pad fills them in (it reaches 0.3 mm into the window, beside the pad only)
for ref in LEDS:
    for pad in led[ref].Pads():
        if pad.GetNetCode() == gnd_code:
            art.BooleanAdd(pad_poly(pad, B_Cu, 0.3))
art.Simplify()
# thin strips of ground copper squeezed between a pad's clearance and the edge copper limit (beside the switch's lower
# tabs, beside the clip's top pad) are cut away: copper narrower than 0.2 mm that would only flake. Found as what a
# 0.1 mm shrink-and-grow removes; the shrink is done on a copy and only the strips themselves are subtracted.
_open = grown(grown(art, -0.1), 0.1)
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

# ---- front: the maker's art --------------------------------------------------------------------
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
# In the original the whole art side was one ground pour, stopping 0.38 mm from the edge. It is kept at 0.40 mm, so the
# maker's mask openings at the toes keep their copper to the edge of the opening, except within 2.5 mm of each panel
# tab, where it steps back to 0.55 mm (clear of the mouse-bite holes).
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


def eagle_polys(key):
    ps = pcbnew.SHAPE_POLY_SET()
    for pts in ART[key]:
        one = poly(pts)
        one.Simplify()                          # Eagle draws holes as cut-in lines; Simplify turns them into real holes
        ps.BooleanAdd(one)
    # the cut-in lines can survive as hairline slits; growing by 0.01 mm closes them (and moves every art edge 10 um)
    ps.Inflate(FromMM(0.01), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    ps.Simplify()
    return ps


mask = eagle_polys("mask")
_m_area = area_mm2(mask)
for x, y in LEDS.values():
    add_circle(mask, P(x, y), MASK_WINDOW)
mask.Simplify()
# where a maker's opening comes closer to the edge than the copper now does, it would show a hairline of bare board:
_bare = pcbnew.SHAPE_POLY_SET(eagle_polys("mask"))
_bare.BooleanSubtract(grown(body, -FRONT_EDGE))
print(f"front mask openings {_m_area:.1f} mm2 (maker) + 2 LED windows; opening area outside the copper: {area_mm2(_bare):.3f} mm2")
mask.BooleanIntersection(body)
add_filled(board, mask, pcbnew.F_Mask)

silk = eagle_polys("silk")
_s_area = area_mm2(silk)
silk.BooleanIntersection(body)
assert abs(area_mm2(silk) - _s_area) < 0.01, "maker's silkscreen reaches past the outline"
_hit = pcbnew.SHAPE_POLY_SET(silk)
_w = pcbnew.SHAPE_POLY_SET()
for x, y in LEDS.values():
    add_circle(_w, P(x, y), WINDOW)
_hit.BooleanIntersection(_w)
assert area_mm2(_hit) < 0.01, "maker's silkscreen covers an LED window"
add_filled(board, silk, pcbnew.F_SilkS)
print(f"front silk {_s_area:.1f} mm2")

# ---- back silkscreen labels ---------------------------------------------------------------------
LABELS = [("SAO", s1[0] + 0.4, SW[1] - 3.3, 0.8, 0), ("OFF", SW[0], SW[1] - 3.3, 0.8, 0),
          ("BAT", s4[0] - 0.2, SW[1] - 3.3, 0.8, 0),
          ("1", j1[0] - 1.6, j1[1] + 1.2, 0.9, 0),
          ("CR2032", BAT[0], bt_low[1] + 2.9, 0.8, 0), ("+ UP", BAT[0], bt_low[1] + 4.3, 0.8, 0),
          ("PENGHITO POCO", 121.5, 103.2, 0.9, 0), ("by davedarko", 121.5, 104.8, 0.8, 0),
          ("SAO++ r" + CIRCUIT["rev"], 121.5, 106.4, 0.8, 0)]
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
    bb = t.GetBoundingBox()
    x0, y0, x1, y1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
    box = poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    box.BooleanSubtract(grown(body, -0.2))
    assert area_mm2(box) < 1e-6, f"label {txt!r} reaches the board edge"
    _bb = pcbnew.SHAPE_POLY_SET(poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                _h = pcbnew.SHAPE_POLY_SET(_bb)
                _h.BooleanIntersection(pad_poly(pad, B_Cu, 0.1))
                assert area_mm2(_h) < 1e-6, f"label {txt!r} prints on {fp.GetReference()} pad {pad.GetNumber()}"

# the connector's silk outline runs off the board where its shroud overhangs the right shoulder: those strokes go to
# the fab drawing (the "1" label marks pin 1)
for it in conn.GraphicalItems():
    if it.GetLayer() == B_SilkS and isinstance(it, pcbnew.PCB_SHAPE):
        bb = it.GetBoundingBox()
        for q in (bb.GetOrigin(), bb.GetEnd()):
            if not grown(body, -0.2).Contains(q):
                it.SetLayer(pcbnew.B_Fab)
                break


# ---- real gaps between the parts (rev A needed DRC exceptions for them; rev B has none, keep-out boxes do not overlap)
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


_cellc = pcbnew.SHAPE_POLY_SET()
add_circle(_cellc, P(*BAT), 10.0)
_shroud_ps = pcbnew.SHAPE_POLY_SET(_shroud)
_stop_ps = pcbnew.SHAPE_POLY_SET()
_stop.TransformShapeToPolygon(_stop_ps, pcbnew.B_Fab, 0, ERR, pcbnew.ERROR_OUTSIDE)
_cu = {r: pcbnew.SHAPE_POLY_SET() for r in PARTS}
for r in PARTS:
    fp = [f for f in board.GetFootprints() if f.GetReference() == r][0]
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and not (r == "BT1" and pad.GetNumber() == "2"):
            _cu[r].Append(pad_poly(pad, B_Cu))
    _cu[r].Simplify()
GAPS = {
    "cell to D2 body": gap(_cellc, rect_of(led["D2"], pcbnew.B_Fab)),
    "cell to R2 body": gap(_cellc, rect_of(res["R2"], pcbnew.B_Fab)),
    "clip closed end to J1 shroud": gap(_stop_ps, _shroud_ps),
    "cell to J1 shroud": gap(_cellc, _shroud_ps),
    "clip pads to SW1 pads": gap(_cu["BT1"], _cu["SW1"]),
    "clip pads to D2 pads": gap(_cu["BT1"], _cu["D2"]),
    "cell to SW1 body": gap(_cellc, rect_of(sw, pcbnew.B_Fab)),
    "D1 body to J1 shroud": gap(rect_of(led["D1"], pcbnew.B_Fab), _shroud_ps),
    "D1 pads to J1 pads": gap(_cu["D1"], _cu["J1"]),
    "R1 to the clip's outline": gap(rect_of(res["R1"], pcbnew.B_Fab), rect_of(bat, pcbnew.B_Fab)),
    "clip's outline to J1 shroud": gap(rect_of(bat, pcbnew.B_Fab), _shroud_ps),
}
for k, v in GAPS.items():
    print(f"  gap {k}: {v} mm")

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
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
