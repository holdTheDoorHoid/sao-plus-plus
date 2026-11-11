#!/usr/bin/env python3
"""Rebuild rbg.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/rbg/hardware/build_board.py

What it does
  - loads original/RBG.kicad_pcb (KiCad 5) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header, the four 3 mm through-hole LEDs, their four 0805 resistors, the old
    tracks, the old back pour, the eight +/- polarity marks the old LEDs needed and the header's front pin-1 dot
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - rebuilds the back copper (the 2018 pour) as the GND net, cleared around the new pads and tracks
  - keeps the front art as drawn: the crown's gold copper (pulled back from the board edge), its mask opening and
    all the front silkscreen. The four jewels were already bare board (no copper, no mask) with the old LED's two
    plated holes inside each one; the holes go with the old LEDs and the jewels are left as plain bare ovals

The art footprint was made by svg2mod: its F.Cu polygon is the crown (one polygon, the jewels are keyhole cut-outs
in it), its three F.Mask polygons open the mask over the crown, and its F.SilkS polygons are the face and lettering.
There is no copper or silk art on the back: the back is the 2018 ground pour plus two lines of silkscreen text.

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "rbg"
SRC = os.path.join(HERE, "..", "original", "RBG.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND pour
TRACK = 0.40
THIN = 0.30         # supply track where it squeezes past the neck and the ear
EDGE = 0.28         # front art copper stops this far short of the board edge (as on Mad Cat)
GND_EDGE = 0.55     # back pour stops this far short of the edge, so panel mouse bites (0.25 mm in) never reach it

# ---- placement (centre x, y) ------------------------------------------------------------------
CONN = (134.5, 110.0)       # bottom right, over the 2018 header; the "Thanks To" credit fills the bottom middle
SW = (90.52, 112.8)         # the straight left edge at the bottom; knob points left, ~0.75 mm past the edge. On the
                            # front its two peg holes land in plain shirt left of "R.B.G." (on the bottom edge they read as extra full stops)
BAT = (112.5, 77.0)         # behind the face: the only spot big enough that covers no lettering. Pushed left (the open
                            # side) so the ground pour can still pass the load track between the clip and the right side of the neck
BAT_CLOSED = (1.0, 0.0)     # closed end of the clip toward the right ear; the cell slides in from the left side of the head
# LEDs keep the 2018 centres: the middle of each old 3 mm LED, i.e. the middle of its two holes, inside each jewel.
# Last number: +1 = anode pad right of centre, -1 = left. (Numbered as in 2018: left to right D2, D1, D4, D3.)
LEDS = {"D2": (106.3515, 58.2495, +1), "D1": (112.4475, 60.2815, -1),
        "D4": (118.7975, 61.6785, -1), "D3": (125.5285, 62.6945, -1)}
# Resistors stand upright (pads above each other). Their LED-side pad 2 is level with the anode pad, pad 1 is below.
# D2 sits too close to the left edge for a resistor beside it, so its resistor sits under it.
RES = {"R2": (106.3515, 61.40), "R1": (109.40, 61.10), "R4": (115.60, 62.50), "R3": (122.15, 63.50)}
BUS_Y = 64.5                # the supply bus that feeds the four resistors, between the jewels and the cell clip
WINDOW = 1.6                # radius kept free of back copper behind each LED so light gets into the board

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 369, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref == "J1" or re.fullmatch(r"[DR][1-4]", ref):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == sorted(["J1"] + [f"D{i}" for i in range(1, 5)] + [f"R{i}" for i in range(1, 5)]), _gone
# the old LEDs' +/- marks on the back (they would sit on the new pads and point the wrong way) and the header's
# little pin-1 "o" on the front; the two lines of maker text on the back stay untouched
_marks = [(a_, b_) for a_, b_ in blocks(_txt, "gr_text") if re.match(r'\s*\(gr_text [-+o] \(at ', _txt[a_:b_])]
assert len(_marks) == 9, len(_marks)
_cut += _marks
_txt = cut_blocks(_txt, _cut)
# the crown's copper is redrawn below (pulled back from the edge), so it is read from the untouched original
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer F.Cu)" in _txt[b_ - 40:b_]]
assert len(_polys) == 1, f"expected the single front copper art polygon (the crown), found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
_frames = stray_frames(_txt, 60)          # no 2018 page frame in this file, but check: the board is 57 mm wide
assert not _frames, len(_frames)
_tmp = os.path.join(tempfile.mkdtemp(), "RBG.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, pcbnew.F_Cu):
    front.Append(p_)
front.Simplify()
_pours = [z for z in _orig.Zones() if not z.GetIsRuleArea()]
assert len(_pours) == 1, "expected the single 2018 ground pour on the back"
art = pcbnew.SHAPE_POLY_SET(_pours[0].Outline())     # the 2018 back was one pour over the whole silhouette
art.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 369 short segments; outline.json is the same path as one closed polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where front art copper may be
art.BooleanIntersection(grown(body, -GND_EDGE))

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
    for k, v in fields.items():           # the library footprint carries the first part that used it; this board's part wins
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


def load(ref, pos):
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name} in {LIB}"
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


def padpos(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as Mad Cat
sw = place("SW1", SW, ("1", (SW[0] + 1.43, SW[1] + 3.0)))            # knob toward the left edge, badge position at the bottom
led, res = {}, {}
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    led[ref] = place(ref, (x, y), ("2", (x + s * 1.55, y)))
    rx, ry = RES["R" + n]
    res["R" + n] = place("R" + n, (rx, ry), ("2", (rx, ry - 0.825)))  # pad 2 (LED side) on top

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
assert abs(_closed_dir(_rot) - math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0]))) < 1, "clip closed end is not where it should be"
link(bat, "BT1")
print("battery clip angle", _rot)

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in a footprint with no schematic symbol: mark it board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board, every pad at least 0.25 mm in from the edge
_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(_pad_ok)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"


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


j1 = padpos(conn, "1")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
bt_top = padpos(bat, "1", pick=lambda p: p[1])           # clip pad toward the jewels
bt_bot = padpos(bat, "1", pick=lambda p: -p[1])          # clip pad toward the neck

# each LED: resistor pad 2 -> anode pad; each resistor pad 1 -> down to the bus
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    r2, r1 = padpos(res["R" + n], "2"), padpos(res["R" + n], "1")
    a = padpos(led[ref], "2")
    if ref == "D2":
        route("LED2_A", [r2, (a[0], r2[1] - 0.6), a])  # up from under the LED to its right-hand (anode) pad
    else:
        route(f"LED{n}_A", [r2, a])
    route("VLOAD", [r1, (r1[0], BUS_Y)])

# The three supplies leave the switch side by side (top to bottom: cell, load, unused, badge) and
# never cross: the badge supply goes right under the lettering to the connector, the load goes right above it and
# up the right side of the neck to the jewels, and the cell supply goes up the left shoulder to the clip.
route("VSAO", [s1, (99.5, s1[1]), (99.5, 102.8), (j1[0], 102.8), j1])
route("VLOAD", [s3, (95.0, s3[1]), (95.0, 100.8), (133.5, 100.8), (133.5, 94.0), (127.0, 88.0), (124.0, 86.2)])
# up between the clip's closed end and the right side of the neck and ear, leaving room outside it for the ground
# pour, which joins the ground under the connector to the rest of the board only along this side
route("VLOAD", [(124.0, 86.2), (124.0, 65.3), (123.2, BUS_Y)], width=THIN)
route("VLOAD", [(123.2, BUS_Y), (padpos(res["R2"], "1")[0], BUS_Y)])
route("VBAT", [s4, (93.5, s4[1]), (93.5, 101.5), (96.8, 96.0), (99.6, 93.6), (105.4, 89.9), (108.0, 88.4), (111.0, bt_bot[1]), bt_bot])
# the clip itself joins its two pads; this link round the closed end makes the board agree without relying on it
_r = 9.7                                                 # just inside the pads' inner ends, under the clip and the cell's + rim (both VBAT),
                                                         # clear of the - disc, and leaving room for ground between it and the load track
_a0 = math.degrees(math.atan2(bt_bot[1] - BAT[1], bt_bot[0] - BAT[0]))
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 - d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 - d)), 4)) for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_bot] + _arc + [bt_top])

# ---- GND copper: the 2018 pour, cleared around everything that is not GND ------------------------------
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)                          # solid copper under the cell so the bare cell pad is whole
art.BooleanAdd(disc)
art.BooleanIntersection(grown(body, -GND_EDGE))

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
for x, y, _s in LEDS.values():                           # light path behind each jewel
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()
# drop ground slivers narrower than 0.3 mm (between the cell track and the shoulder edge, between the switch pins
# and its pegs): open the shape (shrink, then grow back) one piece at a time on the outer path only, then cut the
# clearances again, so no slit opens to a hole (KiCad quirk)
_open = pcbnew.SHAPE_POLY_SET()
for i in range(art.OutlineCount()):
    o_ = pcbnew.SHAPE_POLY_SET()
    o_.AddOutline(art.Outline(i))
    _open.Append(grown(grown(o_, -0.15), 0.15))
_open.Simplify()
_before = area_mm2(art)
art.BooleanIntersection(_open)
art.BooleanSubtract(cut)
art.Simplify()
print("ground slivers removed, mm2:", round(_before - area_mm2(art), 3))

# no new track or part may run through the maker's lettering on the back: keep every track channel and every
# new part's pads and body out of the two text blocks (each line's glyph box, grown 0.3 mm)
lettering = pcbnew.SHAPE_POLY_SET()
_credit_texts = 0
for d in board.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == B_SilkS:
        _credit_texts += 1
        d.TransformTextToPolySet(lettering, FromMM(0.3), ERR, pcbnew.ERROR_OUTSIDE)
assert _credit_texts == 2, _credit_texts
lettering.Simplify()
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(lettering)
assert area_mm2(_hit) < 0.001, f"a track channel overlaps the back lettering by {area_mm2(_hit):.3f} mm2"
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        hull = pcbnew.SHAPE_POLY_SET()
        bb = fp.GetBoundingBox(False)
        hull.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                          (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
        if fp.GetReference() == "BT1":                   # the cell itself (20 mm) is wider than the clip's drawing
            add_circle(hull, P(*BAT), 10.0)
        hull.Simplify()
        hull.BooleanIntersection(lettering)
        assert area_mm2(hull) < 0.001, f"{fp.GetReference()} covers back lettering ({area_mm2(hull):.2f} mm2)"

# every separate piece becomes its own shape: pieces touching a GND pad carry the GND net. The back has no drawn
# copper art (it was all pour in 2018), so a piece cut off from ground is just a floating strip and is dropped
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
    if touches:
        add_filled(board, piece, B_Cu, nets["GND"])
    else:
        print("  dropped floating copper strip, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
    n_gnd += touches
    n_art += not touches
print("back copper pieces: GND", n_gnd, "dropped", n_art)
assert n_gnd == 1, "the ground pour should be one connected piece"

# ---- front copper art: the crown as drawn, pulled back from the board edge ------------------------
# (no hole of the switch's pegs lands on it; the jewels stay the bare ovals they were drawn as)
for x, y, _s in LEDS.values():
    _w = pcbnew.SHAPE_POLY_SET()
    add_circle(_w, P(x, y), WINDOW)
    _w.BooleanIntersection(front)
    assert area_mm2(_w) < 0.0005, f"front copper within {WINDOW} mm of the LED at {x}, {y}"
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
_pk = pcbnew.SHAPE_POLY_SET(pegs)
_pk.BooleanIntersection(front)
assert area_mm2(_pk) == 0, "a switch peg hole lands on the crown"
_before = area_mm2(front)
front.BooleanIntersection(inner)
front.Simplify()
print("front crown copper trimmed at the edge, mm2:", round(_before - area_mm2(front), 2))
add_filled(board, front, pcbnew.F_Cu)

# ---- back silkscreen labels ------------------------------------------------------------------------
LABELS = [("SAO", 97.25, 114.4, 0.8, 0), ("OFF", 97.25, 111.6, 0.8, 0), ("BAT", 97.25, 108.8, 0.8, 0),
          ("CR2032 + SIDE UP", 126.6, 72.0, 0.8, 90), ("SAO++ rA", 105.5, 108.0, 0.9, 0), ("1", CONN[0] - 8.7, j1[1], 0.9, 0)]
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

# ---- nothing may be left outside the outline on any layer (no 2018 page frame here, but check) ----
# The front collar lace (silkscreen) and the crown's mask opening were drawn to run off the shoulders and crown
# by up to 0.2 mm, as in 2018; the board house trims ink and mask at the edge, so that is left as drawn. Anything
# further out than 0.25 mm would be a stray frame and would land on the neighbouring board in a panel.
_out, _near = 0.0, 0.0
for fp in board.GetFootprints():
    if fp.GetReference() not in NEW:
        for it in fp.GraphicalItems():
            if hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY:
                o_ = pcbnew.SHAPE_POLY_SET(it.GetPolyShape())
                o_.BooleanSubtract(body)
                _near += area_mm2(o_)
                o_.BooleanSubtract(grown(body, 0.25))
                _out += area_mm2(o_)
_eb = board.GetBoardEdgesBoundingBox()
for d in board.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts:
        assert _eb.Contains(d.GetBoundingBox().GetCenter()), f"board item outside the outline on {d.GetLayerName()}"
print("art past the edge: within 0.25 mm, mm2:", round(_near, 3), "; further out, mm2:", round(_out, 4))
assert _out < 0.001, _out

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
