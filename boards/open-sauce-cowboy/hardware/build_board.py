#!/usr/bin/env python3
"""Rebuild open-sauce-cowboy.kicad_pcb from Caleb Marting's KiCad 10 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/open-sauce-cowboy/hardware/build_board.py

What the original is (read from the files; the maker's README does not describe this board):
  - a 57 x 27 mm cowboy hat. Front: copper under solder mask for the hat's shading, bare (gold) copper brush strokes,
    a white silkscreen rim, two white crease lines and a white sheriff's star. A 5 mm through-hole LED pokes through
    the middle of the star from the front.
  - back: a through-hole 2x3 SAO header, a through-hole CR2032 holder (BS-02-A1AJ010) whose minus leg shares a hole
    with the header's GND pin, a through-hole 1 k resistor, a 12 mm bare copper disc for soldering on a pin back, a
    3 mm key-ring hole, and a 3-pad solder jumper 'LED SELECT' that feeds the LED from badge VCC (default) or from
    badge GPIO2. The cell's plus is wired straight to the LED and, through the default jumper, to the badge's 3.3 V.

What this script does
  - loads the original and cuts out of the file text every footprint, track and pour, the maker's assembly labels
    ('1K Resistor', 'Long Leg', 'Thru Circle', 'LED SELECT', 'IO2', 'VCC', 'CR2032 HOLDER', 'Pin Back', 'Key Ring',
    'SAO PORT') and the little LED drawing (KiCad 10's Python crashes on Remove())
  - outline: the maker's polygon, unchanged (outline.json), with the 3 mm key-ring hole as a round cut-out
  - SAO++ parts, all on the back: CR2032 clip on the brim (cell slides in from the bottom edge), SAO connector on the
    crown (key slot up), SAO / OFF / BAT switch on the straight bottom edge, one red through-board LED behind the
    middle of the star with its 1.3 k resistor
  - front copper: the maker's copper shape (his pour outline, filtered at his 0.25 mm minimum width), again GND. A
    3.2 mm round window is cleared in the copper, and a 2.9 mm one in the white star, so the LED shines through
  - back copper: GND, cleared around everything that is not GND. Two tented vias join the cell side and the connector
    side of the back GND through the front copper (the coin cell's supply track runs between them)
  - back silkscreen: the Open Sauce logo moves from under the cell to the right-hand brim, unchanged; new labels

Coordinates are millimetres in KiCad's front view (x grows right, y grows down), the maker's own page position.
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, cut_blocks, bbox_mm, add_filled,  # noqa: E402
                         pad_poly)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "open-sauce-cowboy"
SRC = os.path.join(HERE, "..", "original", "Cowboy", "Cowboy.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks
THIN = 0.30         # tracks in tight places
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
WINDOW = 1.6        # radius kept free of copper on both sides around the LED (docs/standard.md section 4)
SILK_WINDOW = 1.45  # radius of the round opening in the white star in front of the LED
MIN_W = 0.25        # the maker's pour dropped copper thinner than this; so does this script

# ---- placement (front view) -------------------------------------------------------------------
KEEP_OPEN_SAUCE_LOGO = True  # the event's logo on the back. The owner has not been asked about it for this board.
HOLE = (230.4, 87.4)        # the maker's 3.0 mm key-ring hole, unchanged
HOLE_R = 1.5
LED = (244.45, 95.0)        # middle of the star. The largest circle that fits inside the star is centred 0.27 mm
                            # higher; the LED sits this much lower so its upper pad clears the connector's body
BAT = (222.1, 97.7)         # clip centre, on the brim. As far left as its left solder tab can go, and low enough that
                            # the clip's top plate clears the connector's plastic body
BAT_CLOSED = (0.0, -1.0)    # the clip's closed end points up; the cell slides in from the bottom edge
CONN = (240.1, 88.2)        # on the crown, above the star, key slot up
SW_X = 249.6                # switch on the straight part of the bottom edge, knob pointing down
R1_X_OFF, R1_UP = 0.0, 2.9  # R1 sits straight above switch pin 3
FEED_Y = 101.0              # the coin cell's supply track runs along this line to switch pin 4
VIA_N = (235.5, 99.4)       # GND through the front copper: above the cell's supply track (connector / LED side) ...
VIA_S = (240.75, 101.9)     # ... and below it (cell side)
LOGO_TO = (261.3, 97.2)     # new centre of the Open Sauce logo

# ---- cut the 2026 electrical parts and labels out of the file text ----------------------------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block (one tab of indent)."""
    for m in re.finditer(r"\n\t\(" + opener + r"[ \n]", txt):
        i = m.start() + 2
        depth = 0
        for j in range(i, len(txt)):
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    yield m.start(), j + 1
                    break


def _box(block):
    xy = [(float(a), float(b)) for a, b in re.findall(r"\(xy ([-0-9.]+) ([-0-9.]+)\)", block)]
    return min(x for x, _ in xy), min(y for _, y in xy), max(x for x, _ in xy), max(y for _, y in xy), len(xy)


_cut, _gone = [], []
for a_, b_ in tblocks(_txt, "footprint"):
    _gone.append(re.search(r'\(property "Reference" "([^"]+)"', _txt[a_:b_]).group(1))
    _cut.append((a_, b_))
assert sorted(_gone) == ["B1", "D1", "JP1", "R3", "REF**", "U1", "X1"], _gone
for kind, n in (("segment", 30), ("zone", 2), ("gr_text", 10), ("gr_line", 6), ("gr_circle", 1), ("group", 5)):
    found = list(tblocks(_txt, kind))
    assert len(found) == n, (kind, len(found))
    if kind in ("gr_line", "gr_circle"):                 # the little LED drawing beside the old LED
        assert all('(layer "B.SilkS")' in _txt[a_:b_] for a_, b_ in found)
    _cut += found
_n = {"edge": 0, "star": 0, "icon": 0, "logo": 0}
for a_, b_ in tblocks(_txt, "gr_poly"):
    blk = _txt[a_:b_]
    x0, y0, x1, y1, npts = _box(blk)
    if '(layer "Edge.Cuts")' in blk:
        _n["edge"] += 1                                  # redrawn below from outline.json
        _cut.append((a_, b_))
    elif '(layer "F.SilkS")' in blk and npts < 200:
        _n["star"] += 1                                  # redrawn below with the LED window in it
        _cut.append((a_, b_))
    elif '(layer "B.SilkS")' in blk and x0 > 240:
        _n["icon"] += 1                                  # two more pieces of the LED drawing
        _cut.append((a_, b_))
    elif '(layer "B.SilkS")' in blk:
        assert 211 < x0 and x1 < 217 and 95 < y0 and y1 < 102, (x0, y0, x1, y1)
        _n["logo"] += 1
        if not KEEP_OPEN_SAUCE_LOGO:
            _cut.append((a_, b_))
assert _n == {"edge": 1, "star": 1, "icon": 2, "logo": 23}, _n
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "cowboy.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
_fz = [z for z in _orig.Zones() if z.GetFirstLayer() == F_Cu]
assert len(_fz) == 1 and _fz[0].GetNetname() == "GND" and abs(ToMM(_fz[0].GetMinThickness()) - MIN_W) < 1e-6
front = pcbnew.SHAPE_POLY_SET(_fz[0].Outline())
_star = [pcbnew.SHAPE_POLY_SET(d.GetPolyShape()) for d in _orig.GetDrawings()
         if isinstance(d, pcbnew.PCB_SHAPE) and d.GetShape() == pcbnew.SHAPE_T_POLY and d.GetLayer() == F_SilkS
         and d.GetPolyShape().Outline(0).PointCount() < 200]
assert len(_star) == 1
star = _star[0]

board = pcbnew.LoadBoard(_tmp)
TRACKS = []

# ---- outline: the maker's polygon, plus his 3 mm hole -------------------------------------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert len(_ol["holes"]) == 1
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
h = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)      # a 120-sided polygon: tools/panelize.py reads polygons only
h.SetPolyShape(poly(_ol["holes"][0]))
h.SetLayer(pcbnew.Edge_Cuts)
h.SetFilled(False)
h.SetWidth(FromMM(0.1))
board.Add(h)
assert all(abs(math.hypot(x - HOLE[0], y - HOLE[1]) - HOLE_R) < 1e-3 for x, y in _ol["holes"][0])


def disc(c, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(*c), r)
    return ps


inner = grown(body, -EDGE)                  # shrink first (no holes yet), then take the hole out, grown
inner.BooleanSubtract(disc(HOLE, HOLE_R + EDGE))
pad_ok = grown(body, -PAD_EDGE)
pad_ok.BooleanSubtract(disc(HOLE, HOLE_R + PAD_EDGE))

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


# ---- footprints ---------------------------------------------------------------------------------
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
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
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


def padpos(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


def box_of(item):
    b = item.GetBoundingBox()
    return (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))


def rect(b):
    return poly([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])])


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
# the connector's own outline strokes that would print over the board edge move to the fab drawing
for g in conn.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        off = rect(box_of(g))
        off.BooleanSubtract(grown(body, -0.3))
        if area_mm2(off) > 1e-4:
            g.SetLayer(pcbnew.B_Fab)

# switch: as low as it can go with its solder tabs PAD_EDGE inside the straight bottom edge, so the knob sticks out
_bottom = min(y for x, y in _ol["outer"] if SW_X - 6.2 < x < SW_X + 6.2 and y > 100)
SW_Y = _bottom - PAD_EDGE - 1.83 - 0.01
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X + 3.0, SW_Y - 1.43)))   # pins toward the star; pin 1 (badge) lands right
assert abs(padpos(sw, "4")[0] - (SW_X - 3.0)) < 0.01 and padpos(sw, "4")[1] < SW_Y
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetBottom())
assert ToMM(_kb.GetTop()) > SW_Y, "knob is not pointing down"
print(f"switch centre y {SW_Y:.3f}; bottom edge there y {_bottom:.3f}; knob tip {KNOB_TIP:.2f} = {KNOB_TIP - _bottom:.2f} mm past the edge")

s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
R1_AT = (s3[0] + R1_X_OFF, s3[1] - R1_UP)
r1 = place("R1", R1_AT, ("1", (R1_AT[0], R1_AT[1] + 0.825)))         # supply pad at the bottom, toward the switch
led = place("D1", LED, ("1", (LED[0], LED[1] + 1.55)))               # cathode at the bottom, anode toward the connector

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
assert abs(_closed_dir(_rot) - math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0]))) < 1
link(bat, "BT1")
print("battery clip angle", _rot)
# the clip's own silkscreen (insertion arrow, '+', closed-end line) would land on the cell disc and off the board:
# it moves to the fab layer and the board gets its own labels below
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

# The real clip (TE drawing BAT-HLD-001, read 2026-11-11): a plate 21.1 mm wide that reaches 7.2 mm from the pad line
# at the closed end (corners cut off about 2.9 x 2.7 mm) and 8.1 mm at the open end. The shared footprint's fab
# rectangle is only an estimate, so the clearance to the connector's plastic body is checked against the drawing here.
_s = -1 if BAT_CLOSED[1] < 0 else 1
plate = poly([(BAT[0] - 10.55, BAT[1] + _s * 4.5), (BAT[0] - 7.65, BAT[1] + _s * 7.2), (BAT[0] + 7.65, BAT[1] + _s * 7.2),
              (BAT[0] + 10.55, BAT[1] + _s * 4.5), (BAT[0] + 10.55, BAT[1] - _s * 4.5), (BAT[0] + 6.3, BAT[1] - _s * 8.1),
              (BAT[0] - 6.3, BAT[1] - _s * 8.1), (BAT[0] - 10.55, BAT[1] - _s * 4.5)])
conn_body = rect((CONN[0] - 7.65, CONN[1] - 4.45, CONN[0] + 7.65, CONN[1] + 4.45))
_hit = grown(plate, 0.25)
_hit.BooleanIntersection(conn_body)
assert area_mm2(_hit) < 1e-4, "clip plate closer than 0.25 mm to the connector body"
_hit = disc(BAT, 10.0 + 0.2)
_hit.BooleanIntersection(conn_body)
assert area_mm2(_hit) < 1e-4, "cell closer than 0.2 mm to the connector body"
_over = disc(BAT, 10.0)
_over.BooleanSubtract(body)
print("cell past the board edge: %.1f mm2" % area_mm2(_over), "within", [round(v, 2) for v in bbox_mm(_over)] if _over.OutlineCount() else "-")

NEW = set(PARTS)
# every pad sits on the board, PAD_EDGE inside the edge
for fp in board.GetFootprints():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"

# ---- the Open Sauce logo: same drawing, moved from under the cell to the right-hand brim ----------------
_logo = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_SHAPE) and d.GetLayer() == B_SilkS]
LOGO_BOX = None
if KEEP_OPEN_SAUCE_LOGO:
    assert len(_logo) == 23
    _lb = [min(box_of(d)[0] for d in _logo), min(box_of(d)[1] for d in _logo), max(box_of(d)[2] for d in _logo), max(box_of(d)[3] for d in _logo)]
    _dx, _dy = LOGO_TO[0] - (_lb[0] + _lb[2]) / 2, LOGO_TO[1] - (_lb[1] + _lb[3]) / 2
    for d in _logo:
        d.Move(VECTOR2I(FromMM(_dx), FromMM(_dy)))
    LOGO_BOX = (_lb[0] + _dx, _lb[1] + _dy, _lb[2] + _dx, _lb[3] + _dy)
    _off = rect(LOGO_BOX)
    _off.BooleanSubtract(grown(body, -0.6))
    assert area_mm2(_off) < 1e-4, "logo too close to the edge"
    print("logo moved from", [round(v, 2) for v in _lb], "to", [round(v, 2) for v in LOGO_BOX])
else:
    assert not _logo


# ---- routing (back copper only) -----------------------------------------------------------------
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


VIAS = []


def via(net, at):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*at))
    v.SetWidth(FromMM(0.6))
    v.SetDrill(FromMM(0.3))
    v.SetLayerPair(F_Cu, B_Cu)
    v.SetNet(nets[net])
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append(v)


j1 = padpos(conn, "1")
led_k, led_a = padpos(led, "1"), padpos(led, "2")
r1a, r1b = padpos(r1, "1"), padpos(r1, "2")
assert led_a[1] < led_k[1] and r1b[1] < r1a[1]

# badge 3.3 V: connector pin 1 -> down into the gap between the connector's two pad rows -> right, under its body ->
# down the right-hand side of the crown, outside the LED and R1 -> switch pin 1
MID = CONN[1]
route("VSAO", [j1, (j1[0], MID), (247.3, MID), (247.3, 90.5), (248.3, 93.0), (249.6, 96.0), (249.6, 97.0),
               (s1[0], s1[1] - 1.6), s1], width=THIN)

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
_deg = list(range(180, -1, -5))
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _s * _r * math.sin(math.radians(d)), 4)) for d in _deg]
assert all((y - BAT[1]) * BAT_CLOSED[1] >= -0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]])
# ... and from the right-hand tab along the bottom of the crown to switch pin 4, arriving from the left
route("VBAT", [bt[1], (bt[1][0], bt[1][1] + 2.2), (bt[1][0] + FEED_Y - bt[1][1] - 2.2, FEED_Y), (s4[0], FEED_Y)], width=THIN)
assert abs(FEED_Y - s4[1]) < 0.55

# switched supply: switch pin 3 -> R1 -> up the right of the LED window -> LED anode
route("VLOAD", [s3, r1a])
LA_X = LED[0] + WINDOW + 0.5
route("LED_A", [r1b, (LA_X, r1b[1] - (r1b[0] - LA_X)), (LA_X, led_a[1]), led_a], width=THIN)

# GND: the cell's supply track and its link round the clip split the back GND into a cell side and a connector side
# that only meet through narrow necks (0.45 mm under the connector, then between the switch pins and under the switch).
# Two tented vias join the two sides solidly through the front copper, which is GND as on the maker's board.
via("GND", VIA_N)
via("GND", VIA_S)

# ---- front copper: the maker's shape, GND, with the LED window -----------------------------------------
front.Simplify()
front.BooleanIntersection(inner)
_before = area_mm2(front)
front.Inflate(-FromMM(MIN_W / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)     # no holes yet, so shrinking is safe
front.Inflate(FromMM(MIN_W / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
front.BooleanIntersection(inner)
front.SimplifyOutlines(FromMM(0.003))
front.Simplify()
print("front copper mm2: outline %.1f, after dropping strokes thinner than %.2f mm %.1f; pieces %d, points %d"
      % (_before, MIN_W, area_mm2(front), front.OutlineCount(), sum(front.Outline(i).PointCount() for i in range(front.OutlineCount()))))
holes_f = pcbnew.SHAPE_POLY_SET()
add_circle(holes_f, P(*LED), WINDOW)
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(holes_f, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
holes_f.Simplify()
front.BooleanSubtract(holes_f)
front.Simplify()
n_f = [0, 0]
for i in range(front.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(front.Polygon(i))
    has_via = False
    for v in VIAS:
        ring = pcbnew.SHAPE_POLY_SET()
        add_circle(ring, v.GetPosition(), 0.3 + 0.15)
        inside = pcbnew.SHAPE_POLY_SET(ring)
        inside.BooleanIntersection(piece)
        if area_mm2(inside) > 1e-4:
            ring.BooleanSubtract(piece)
            assert area_mm2(ring) < 1e-4, f"via at {mm(v.GetPosition())} is not fully inside the front copper"
            has_via = True
    if not has_via and area_mm2(piece) < 0.05:
        continue                                        # specks
    add_filled(board, piece, F_Cu, nets["GND"] if has_via else None)
    n_f[0 if has_via else 1] += 1
    if not has_via:
        print("  plain front copper piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
assert n_f[0] == 1, f"the vias land in {n_f[0]} separate pieces of front copper"
print("front copper pieces: GND", n_f[0], "plain", n_f[1])

# the star, with a round opening in front of the LED
_room = pcbnew.SHAPE_POLY_SET(disc(LED, SILK_WINDOW + 0.2))
_room.BooleanSubtract(star)
assert area_mm2(_room) < 1e-4, "the LED window would break through the side of the star"
star.BooleanSubtract(disc(LED, SILK_WINDOW))
add_filled(board, star, F_SilkS)

# ---- back copper: GND everywhere, cleared around everything that is not GND -------------------------
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
        elif pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
add_circle(cut, P(*LED), WINDOW)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
cut.Simplify()
art.BooleanSubtract(cut)
# drop slivers thinner than 0.3 mm (they would only be specks of copper)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.BooleanIntersection(inner)
art.Simplify()

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
for v in VIAS:
    add_circle(gnd_pads, v.GetPosition(), 0.3)
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
    print("  back copper piece, mm2:", round(area_mm2(piece), 1), "GND" if touches else "plain", "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain", n_art)

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("BAT", 241.6, 103.55, 0.8, 0), ("SAO", 257.5, 102.5, 0.8, 0),
          ("orig. design:", 238.7, 95.4, 0.8, 0), ("Caleb Marting", 238.7, 96.65, 0.8, 0),
          ("CR2032 + UP", 238.7, 98.1, 0.8, 0),
          ("COWBOY", 255.4, 97.2, 0.9, 0), ("SAO++ rA", 255.4, 98.6, 0.8, 0),
          ("1", 231.2, 85.3, 0.9, 0)]
_pads_b = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            _pads_b.Append(pad_poly(pad, B_Cu, 0.15))
_pads_b.Simplify()
_taken = []
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
    b = box_of(t)
    r_ = rect(b)
    off = pcbnew.SHAPE_POLY_SET(r_)
    off.BooleanSubtract(grown(body, -0.4))
    assert area_mm2(off) < 1e-4, f"label {txt!r} is closer than 0.4 mm to the board edge: {[round(v, 2) for v in b]}"
    on = pcbnew.SHAPE_POLY_SET(r_)
    on.BooleanIntersection(_pads_b)
    assert area_mm2(on) < 1e-4, f"label {txt!r} sits on a pad: {[round(v, 2) for v in b]}"
    for other, ob in _taken + ([("logo", LOGO_BOX)] if LOGO_BOX else []):
        # KiCad's text box is about 0.28 mm taller than the letters at top and bottom
        assert b[2] < ob[0] or ob[2] < b[0] or b[3] - 0.25 < ob[1] + 0.25 or ob[3] - 0.25 < b[1] + 0.25, f"label {txt!r} overlaps {other!r}"
    _taken.append((txt, b))
    print("label %-14r x %.2f..%.2f y %.2f..%.2f" % (txt, b[0], b[2], b[1], b[3]))

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("D1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in led.Pads()}, "R1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in r1.Pads()})
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
