#!/usr/bin/env python3
"""Build nsec-cashbag.kicad_pcb: SAO++'s own money-bag drawing, with the circuit of the NorthSec 2025 "Sao_CashBag".

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-cashbag/hardware/build_board.py

What the original is (read from the files; the maker wrote nothing down):
  - a 38.4 x 25.2 mm add-on with three 1206 LEDs on the FRONT, each with its own 330 ohm 1206 resistor on the back,
    wired straight across the badge's 3.3 V and GND. No battery, no switch, no chip; SDA, SCL and both GPIO pins
    unconnected. An SMD 2x3 header on the back, the 'nsec 2025' logo and a white write-on square.
  - its outline and front picture were traced from a stock illustration. NONE of that is used here or kept in
    original/ (see original/README.md).

What this script does
  - DRAWS THE BOARD FROM NUMBERS (section "the drawing"): a banded wad of bank notes with a second note tucked behind
    it, a tied sack with a '$', and one big coin with a '$'. Every shape is generated below from a few dimensions; the
    same shapes are written to art/cash-bag.svg. Nothing is read from the maker's art.
  - takes from the maker's board file only the 'nsec 2025' logo footprint and the white write-on square (both on the
    back, both at their real size)
  - back: CR2032 clip behind the sack (cell slides in from the bottom edge), SAO connector behind the coin, SAO / OFF /
    BAT switch on the left edge behind the notes, three reverse-mount white LEDs shining through the board (the sack's
    gathered top, the bank note's round medallion, a glint on the coin), one 1.3 k resistor each. No vias.
  - back copper: GND, cleared around everything that is not GND and 1.6 mm around each LED

Coordinates are millimetres in KiCad's front view (x right, y down).
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, cut_blocks, bbox_mm, add_filled,  # noqa: E402
                         pad_poly)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "nsec-cashbag"
SRC = os.path.join(HERE, "..", "original", "Sao_CashBag", "Sao_CashBag.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
SVG = os.path.join(HERE, "..", "art", "cash-bag.svg")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.30
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
WINDOW = 1.6        # radius kept free of copper on both sides at each LED, so light gets through the board

# ---- the drawing: every dimension of the art (front view, mm) ----------------------------------------
BASE = 139.5                                    # the ground line everything stands on
NOTE = (100.0, 122.2, 124.0, 133.2)             # face of the top bank note of the wad: left, top, right, bottom
NOTE2 = ((114.0, 120.3), 24.0, 11.0, 9.0)       # the note tucked behind: centre, width, height, tilt in degrees
BAND = (104.4, 107.0)                           # gold paper band round the wad: left, right
MEDAL = ((112.0, 127.7), 3.4)                   # round medallion on the note: centre, radius
SACK = ((132.0, 126.5), 13.2, 16.0, 2.7)        # sack body, a superellipse: centre, half-width, half-height, exponent
NECK = 4.2                                      # half-width of the sack's neck
NECK_Y = (107.0, 112.0)
FRILL = (7.4, 103.2, 5)                         # gathered top: half-width, height of the scallop centres, scallops
ROPE = (108.9, 111.2)                           # gold tie across the neck: top, bottom
COIN = ((153.2, 127.0), 12.5)                   # the big coin: centre, radius
COIN_RING = 10.8                                # inner radius of its gold rim
S_SACK = ((132.0, 126.6), 3.3, 2.0, 1.3, 1.2)   # '$' on the sack: centre, loop radius, stroke, bar width, bar overshoot
S_COIN = ((153.2, 128.3), 2.3, 1.5, 1.0, 0.7)   # '$' on the coin

# ---- placement of the parts on the back ---------------------------------------------------------------
LEDS = {"D1": (SACK[0][0], 105.8),              # the sack's gathered top
        "D2": MEDAL[0],                         # the note's medallion
        "D3": (COIN[0][0], COIN[0][1] - 8.8)}   # a glint at the top of the coin's face
BAT = (132.0, 126.3)        # clip centre, behind the sack
BAT_CLOSED = (0.0, -1.0)    # closed end up; the cell slides in from the bottom edge
CONN = COIN[0]              # behind the coin, key slot up: 3.6 mm of board all round its body
SW_Y = 131.5                # switch on the straight left edge of the wad, knob pointing left
R_AT = {"R1": (136.5, 112.8), "R2": (116.2, 127.7), "R3": (148.4, 117.9)}
LOGO_BOX_AT = (106.0, 131.0)       # top-left corner of the 'nsec 2025' logo, behind the wad
NOTE_AT = (107.15, 118.55)         # centre of the maker's 5.1 mm write-on square, behind the tucked note


# ---- small geometry helpers for the drawing ---------------------------------------------------------
def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def disc(c, r, n=144):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(*c), r, n)
    return ps


def union(*parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p in parts:
        out.BooleanAdd(p)
    out.Simplify()
    return out


def minus(a, *bs):
    out = pcbnew.SHAPE_POLY_SET(a)
    for b in bs:
        out.BooleanSubtract(b)
    out.Simplify()
    return out


def both(a, b):
    out = pcbnew.SHAPE_POLY_SET(a)
    out.BooleanIntersection(b)
    out.Simplify()
    return out


def stroke(pts, w):
    """A line of width w through the points, round ends and joints."""
    out = pcbnew.SHAPE_POLY_SET()
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        d = math.hypot(bx - ax, by - ay)
        if d < 1e-6:
            continue
        nx, ny = -(by - ay) / d * w / 2, (bx - ax) / d * w / 2
        out.BooleanAdd(poly([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]))
    for p in pts:
        out.BooleanAdd(disc(p, w / 2, 20))
    out.Simplify()
    return out


def outline_of(shape, inset, w):
    """A line of width w running `inset` inside the edge of a shape."""
    return minus(grown(shape, -inset), grown(shape, -inset - w))


def turned(c, w, h, deg):
    a = math.radians(deg)
    return poly([(c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))
                 for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))])


def dollar(c, r, w, barw, over):
    """A '$': two loops of radius r drawn with a stroke of width w, and an upright bar through them."""
    pts = [(c[0] + r * math.cos(math.radians(t)), c[1] - r - r * math.sin(math.radians(t))) for t in range(25, 271, 7)]
    pts += [(c[0] + r * math.cos(math.radians(t)), c[1] + r - r * math.sin(math.radians(t))) for t in range(90, -156, -7)]
    return union(stroke(pts, w), rect(c[0] - barw / 2, c[1] - 2 * r - w / 2 - over, c[0] + barw / 2, c[1] + 2 * r + w / 2 + over))


# ---- the drawing: shapes ------------------------------------------------------------------------------
note = rect(*NOTE)
wad = rect(NOTE[0], NOTE[1], NOTE[2], BASE)                    # the note's face with the edges of the notes under it
note2 = turned(*NOTE2)
_c, _a, _b, _n = SACK
_se = []
for k in range(180):
    t = 2 * math.pi * k / 180
    _se.append((_c[0] + _a * math.copysign(abs(math.cos(t)) ** (2 / _n), math.cos(t)),
                _c[1] + _b * math.copysign(abs(math.sin(t)) ** (2 / _n), math.sin(t))))
_fw, _fy, _fn = FRILL
_fr = _fw / _fn                                                 # scallop radius
sack = union(both(poly(_se), rect(0, 0, 300, BASE)),
             rect(_c[0] - NECK, NECK_Y[0], _c[0] + NECK, NECK_Y[1]),
             poly([(_c[0] - NECK, NECK_Y[0] + 3.0), (_c[0] - _fw, _fy), (_c[0] + _fw, _fy), (_c[0] + NECK, NECK_Y[0] + 3.0)]),
             *[disc((_c[0] - _fw + _fr * (2 * k + 1), _fy), _fr, 48) for k in range(_fn)])
coin = disc(*COIN)
body = union(wad, note2, sack, coin)
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0, "the drawing's outline is not one simple shape"
OUTLINE = [(round(ToMM(body.Outline(0).CPoint(k).x), 4), round(ToMM(body.Outline(0).CPoint(k).y), 4))
           for k in range(body.Outline(0).PointCount())]
json.dump({"outer": [list(p) for p in OUTLINE], "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
body = poly(OUTLINE)
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)
_bb = bbox_mm(body)
print("outline: %.2f x %.2f mm, x %.2f..%.2f y %.2f..%.2f, area %.0f mm2, %d points" % (
    _bb[2] - _bb[0], _bb[3] - _bb[1], _bb[0], _bb[2], _bb[1], _bb[3], area_mm2(body), len(OUTLINE)))
assert _bb[0] > NOTE[0] - 0.001, "something sticks out past the wad's straight left edge"
LEFT_X, LEFT_TOP, LEFT_BOT = NOTE[0], NOTE[1], BASE

led_holes = pcbnew.SHAPE_POLY_SET()
for _at in LEDS.values():
    led_holes.BooleanAdd(disc(_at, WINDOW, 64))

# what is in front of what: coin, then sack, then the wad, then the tucked note
coin_gap = grown(coin, 0.6)
sack_gap = grown(sack, 0.5)
# copper under mask (shows as lighter green): the sack, with three creases below the tie
_creases = union(stroke([(_c[0] - 5.2, 113.6), (_c[0] - 7.4, 116.4), (_c[0] - 8.4, 119.6)], 0.6),
                 stroke([(_c[0] - 1.6, 113.8), (_c[0] - 2.2, 116.2), (_c[0] - 2.0, 118.6)], 0.6),
                 stroke([(_c[0] + 6.8, 113.4), (_c[0] + 8.6, 115.8), (_c[0] + 9.6, 118.4)], 0.6))
sack_cu = minus(both(sack, inner), coin_gap, led_holes, _creases)
# bare gold (copper with the mask opened over it)
_gold_ok = grown(sack_cu, -0.12)
gold_sack = both(union(dollar(*S_SACK),
                       rect(_c[0] - 8, ROPE[0], _c[0] + 8, ROPE[1]),                       # the tie
                       stroke([(_c[0] + 2.4, ROPE[1] - 0.3), (_c[0] + 3.6, 113.4), (_c[0] + 4.6, 115.6)], 1.1),   # its two ends
                       stroke([(_c[0] + 1.6, ROPE[1] - 0.3), (_c[0] + 1.2, 113.8), (_c[0] + 1.6, 116.2)], 1.1)), _gold_ok)
_rim = minus(disc(COIN[0], COIN[1] - EDGE), disc(COIN[0], COIN_RING))
gold_coin = union(minus(grown(_rim, -0.1), led_holes), dollar(*S_COIN))
coin_cu = union(minus(_rim, led_holes), grown(dollar(*S_COIN), 0.1))
_band = both(rect(BAND[0], NOTE[1] + EDGE, BAND[1], BASE - EDGE), minus(inner, sack_gap))
gold_band = grown(_band, -0.1)
front_cu = union(sack_cu, coin_cu, _band)
gold = union(gold_sack, gold_coin, gold_band)
_o = minus(gold, grown(front_cu, -0.05))
assert area_mm2(_o) < 0.01, "a mask opening is not backed by copper"
_o = both(front_cu, led_holes)
assert area_mm2(_o) < 0.01

# white silkscreen
_wad_seen = minus(both(wad, grown(body, -0.45)), sack_gap, coin_gap, grown(_band, 0.3))
_note2_seen = minus(both(note2, grown(body, -0.45)), grown(wad, 0.45), sack_gap)
_m = MEDAL
_g = LEDS["D3"]
silk = union(
    both(union(outline_of(note, 0.9, 0.35),                                                    # the note's frame
               minus(disc(_m[0], _m[1]), disc(_m[0], _m[1] - 0.3)),                            # its medallion
               *[stroke([(NOTE[0], y), (NOTE[2], y)], 0.3) for y in (NOTE[3], 134.7, 136.0, 137.3, 138.6)]), _wad_seen),   # edges of the wad
    both(outline_of(note2, 0.9, 0.35), _note2_seen),
    *[stroke([(_g[0] + 2.1 * math.cos(math.radians(t)), _g[1] + 2.1 * math.sin(math.radians(t))),
              (_g[0] + 3.3 * math.cos(math.radians(t)), _g[1] + 3.3 * math.sin(math.radians(t)))], 0.35)
      for t in (0, 55, 125, 180)])                                                              # the glint's rays
silk = minus(silk, grown(gold, 0.15), led_holes)
_o = minus(silk, grown(body, -0.3))
assert area_mm2(_o) < 0.01, "silkscreen runs off the board"


def svg_path(ps):
    out = []
    for i in range(ps.OutlineCount()):
        rings = [ps.Outline(i)] + [ps.Hole(i, h) for h in range(ps.HoleCount(i))]
        for c in rings:
            out.append("M" + " L".join("%.3f,%.3f" % (ToMM(c.CPoint(k).x), ToMM(c.CPoint(k).y)) for k in range(c.PointCount())) + "Z")
    return " ".join(out)


os.makedirs(os.path.dirname(SVG), exist_ok=True)
with open(SVG, "w", encoding="utf-8") as f:
    f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.1f %.1f %.1f %.1f" width="%.1fmm" height="%.1fmm">\n' % (
        _bb[0] - 1, _bb[1] - 1, _bb[2] - _bb[0] + 2, _bb[3] - _bb[1] + 2, _bb[2] - _bb[0] + 2, _bb[3] - _bb[1] + 2))
    f.write("<!-- Cash Bag front art, SAO++'s own drawing (CC-BY-SA-4.0). Generated by hardware/build_board.py; edit the numbers there. -->\n")
    for name, ps, colour in (("board (solder mask)", body, "#1d5b34"), ("copper under mask", front_cu, "#2e8048"),
                             ("bare gold", gold, "#e2b63c"), ("white silkscreen", silk, "#ffffff"),
                             ("LED behind the board", led_holes, "#fff6b0")):
        f.write('<path id="%s" fill="%s" fill-rule="evenodd"%s d="%s"/>\n' % (
            name.split(" (")[0].replace(" ", "-"), colour, ' fill-opacity="0.45"' if "LED" in name else "", svg_path(ps)))
    f.write("</svg>\n")
print("wrote", SVG)

# ---- the maker's board file: only the logo and the write-on square are used ----------------------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block of a KiCad 8 file (one tab of indent)."""
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


_cut, _gone = [], []
for a_, b_ in tblocks(_txt, "footprint"):
    ref = re.search(r'\(property "Reference" "([^"]+)"', _txt[a_:b_]).group(1)
    if ref != "REF**":                      # REF** is the 'nsec 2025' logo
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["D1", "D2", "D3", "J1", "R1", "R2", "R3"], _gone
for kind in ("segment", "via"):
    _cut += list(tblocks(_txt, kind))
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n\t\(net [1-9]\d* "[^"]*"\)', _txt)]
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "cashbag.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []
_draw = list(board.GetDrawings())
assert len(_draw) == 1 and _draw[0].GetLayer() == B_SilkS, "original/ should hold no art but the write-on square"
assert len(list(board.Zones())) == 0
_note = _draw[0]
_c = _note.GetBoundingBox().GetCenter()
_note.Move(VECTOR2I(FromMM(NOTE_AT[0]) - _c.x, FromMM(NOTE_AT[1]) - _c.y))
_nb = _note.GetBoundingBox()
NOTE_BOX = (ToMM(_nb.GetLeft()), ToMM(_nb.GetTop()), ToMM(_nb.GetRight()), ToMM(_nb.GetBottom()))

e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(OUTLINE))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
SW_X = LEFT_X + PAD_EDGE + 0.01 + 1.83          # outer solder tabs PAD_EDGE inside the edge; the knob sticks out
assert LEFT_TOP + PAD_EDGE + 5.65 <= SW_Y <= LEFT_BOT - PAD_EDGE - 5.65, "the switch does not fit on the left edge"

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


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X + 1.43, SW_Y + 3.0)))    # pins toward the middle; pin 1 (badge) lowest
assert abs(padpos(sw, "4")[1] - (SW_Y - 3.0)) < 0.01
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetLeft())
assert ToMM(_kb.GetRight()) < SW_X, "knob is not pointing left"
print(f"switch centre ({SW_X:.2f}, {SW_Y}); knob tip x {KNOB_TIP:.2f}, {LEFT_X - KNOB_TIP:.2f} mm past the left edge")

led = {"D1": place("D1", LEDS["D1"], ("2", (LEDS["D1"][0] + 1.55, LEDS["D1"][1]))),     # anode right
       "D2": place("D2", LEDS["D2"], ("2", (LEDS["D2"][0] + 1.55, LEDS["D2"][1]))),     # anode right
       "D3": place("D3", LEDS["D3"], ("2", (LEDS["D3"][0] - 1.55, LEDS["D3"][1])))}     # anode left
res = {"R1": place("R1", R_AT["R1"], ("1", (R_AT["R1"][0] + 0.825, R_AT["R1"][1]))),    # supply pad on the right
       "R2": place("R2", R_AT["R2"], ("1", (R_AT["R2"][0] + 0.825, R_AT["R2"][1]))),    # supply pad on the right
       "R3": place("R3", R_AT["R3"], ("1", (R_AT["R3"][0] - 0.825, R_AT["R3"][1])))}    # supply pad on the left

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
link(bat, "BT1")
_sb = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
print("battery clip angle", _rot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f" % (ToMM(_sb.GetLeft()), ToMM(_sb.GetRight()), ToMM(_sb.GetTop()), ToMM(_sb.GetBottom())))
assert ToMM(_sb.GetTop()) < BAT[1] - 11, "the clip's closed end is not up"
# the clip's own silkscreen (insertion arrow, '+', closed-end line) moves to the fab layer; the board gets its own labels
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

# the 'nsec 2025' logo: same footprint, real size, same way up, behind the wad of notes
NEW = set(PARTS)
logo = [fp for fp in board.GetFootprints() if fp.GetReference() not in NEW]
assert len(logo) == 1 and "nsec-2025" in logo[0].GetFPIDAsString()
logo = logo[0]
logo.SetLocked(False)
_lb = logo.GetBoundingBox()
logo.Move(VECTOR2I(FromMM(LOGO_BOX_AT[0]) - _lb.GetLeft(), FromMM(LOGO_BOX_AT[1]) - _lb.GetTop()))
logo.SetLocked(True)
logo.SetAttributes(logo.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
_lb = logo.GetBoundingBox()
LOGO_BOX = (ToMM(_lb.GetLeft()), ToMM(_lb.GetTop()), ToMM(_lb.GetRight()), ToMM(_lb.GetBottom()))
print("logo x %.2f..%.2f y %.2f..%.2f" % (LOGO_BOX[0], LOGO_BOX[2], LOGO_BOX[1], LOGO_BOX[3]),
      "; write-on square x %.2f..%.2f y %.2f..%.2f" % (NOTE_BOX[0], NOTE_BOX[2], NOTE_BOX[1], NOTE_BOX[3]))
for box in (LOGO_BOX, NOTE_BOX):
    _o = rect(*box)
    _o.BooleanSubtract(grown(body, -0.2))
    assert _o.OutlineCount() == 0, "back art hangs over the board edge"

# every pad of a new part sits on the board, PAD_EDGE inside the edge, and off the maker's back silkscreen
_silk = union(rect(*LOGO_BOX), rect(*NOTE_BOX))
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                continue
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
            on = pad_poly(pad, B_Cu, 0.2)
            on.BooleanIntersection(_silk)
            assert on.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} sits on the logo or the write-on square"
# the resting cell (20 mm) stays on the board ...
_o = minus(disc(BAT, 10.0), body)
print("cell area off the board, mm2: %.2f" % area_mm2(_o))
assert area_mm2(_o) < 0.01
# ... and nothing stands in its way as it slides in from the bottom edge
for fp in board.GetFootprints():
    if fp.GetReference() in NEW and fp.GetReference() != "BT1":
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            assert ToMM(b.GetBottom()) < BAT[1] or ToMM(b.GetRight()) < BAT[0] - 10.3 or ToMM(b.GetLeft()) > BAT[0] + 10.3, \
                f"{fp.GetReference()} is in the path of the cell"
# the connector's plastic body keeps 3 mm of board all round it (standard.md section 2)
_o = minus(grown(rect(CONN[0] - 7.65, CONN[1] - 4.45, CONN[0] + 7.65, CONN[1] + 4.45), 3.0), body)
assert area_mm2(_o) < 0.01, "the connector is closer than 3 mm to the edge"


# ---- routing (back copper only, no vias) ---------------------------------------------------------
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


s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
j1 = padpos(conn, "1")
X_LOAD, X_SAO = 145.5, 146.5        # the two supply tracks climb between the clip's right tab and the connector's pads
Y_LOAD, Y_SAO = 137.2, 137.9        # ... after running along the bottom edge, below the cell
Y_TURN = 131.5                      # ... and crossing from the sack to the coin above the nick between them

# badge 3.3 V: switch pin 1 (lowest) -> along the bottom edge -> up, under the connector's left end -> pin 1
route("VSAO", [s1, (104.6, s1[1]), (104.6, Y_SAO - 1.3), (105.9, Y_SAO), (X_SAO - (Y_SAO - Y_TURN), Y_SAO), (X_SAO, Y_TURN),
               (X_SAO, j1[1]), j1])

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. The left tab runs on, above the note's LED, to switch pin 4.
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] - _r * math.sin(math.radians(d)), 4)) for d in range(180, -1, -5)]
assert all(y <= BAT[1] + 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]])
route("VBAT", [s4, (105.6, s4[1]), (105.6, 123.6), (119.5, 123.6), (120.5, 124.6), (bt[0][0], 124.6)])

# switched supply: switch pin 3 -> down -> along the bottom edge (above the badge track) -> up, then three branches
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")
r3a, r3b = padpos(res["R3"], "1"), padpos(res["R3"], "2")
Y_SPLIT = 121.6
route("VLOAD", [s3, (106.0, s3[1]), (106.0, Y_LOAD - 1.0), (107.0, Y_LOAD), (X_LOAD - (Y_LOAD - Y_TURN), Y_LOAD),
                (X_LOAD, Y_TURN), (X_LOAD, Y_SPLIT)])
route("VLOAD", [(106.0, 130.7), (118.2, 130.7), (118.2, r2a[1] + 1.2), r2a])                    # R2, for the note's LED
route("VLOAD", [(X_LOAD, Y_SPLIT), (144.2, 120.3), (141.5, 117.2), (138.0, 113.7), r1a])        # R1, for the sack's LED
route("VLOAD", [(X_LOAD, Y_SPLIT), (146.6, 120.5), (146.6, 118.9), r3a])                        # R3, for the coin's LED

# resistor -> LED anode
d1a, d2a, d3a = padpos(led["D1"], "2"), padpos(led["D2"], "2"), padpos(led["D3"], "2")
route("D1_A", [r1b, (134.0, 111.2), (d1a[0], 109.5), d1a])      # up through the sack's neck
route("D2_A", [r2b, d2a])
route("D3_A", [r3b, (150.4, d3a[1]), d3a])

for t, _ in TRACKS:                                              # every track stays EDGE inside the outline
    _p = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(_p, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    _p.BooleanSubtract(inner)
    assert area_mm2(_p) < 1e-4, f"{t.GetNetname()} track near {mm(t.GetStart())} is closer than {EDGE} mm to the edge"

# ---- front: the drawing ---------------------------------------------------------------------------
front = pcbnew.SHAPE_POLY_SET(front_cu)
_before = area_mm2(front)
holes = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(holes, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(holes)
front.Simplify()
assert abs(_before - area_mm2(front)) < 1e-6, "a switch peg comes through the front copper"
print("front copper, mm2: %.1f; bare gold %.1f; silkscreen %.1f" % (area_mm2(front), area_mm2(gold), area_mm2(silk)))
add_filled(board, front, F_Cu)
add_filled(board, gold, pcbnew.F_Mask)
add_filled(board, silk, pcbnew.F_SilkS)

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
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for at in LEDS.values():                                 # light path behind each LED
    add_circle(cut, P(*at), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
# drop slivers thinner than 0.3 mm (they would only be specks of copper)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.Simplify()

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  GND copper piece, mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    else:                                                  # an island that touches nothing: leave it bare board
        print("  dropped floating piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
assert n_gnd == 1, "the GND copper is not one piece"

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("SAO", 105.15, s1[1], 0.8, 90, False), ("OFF", 105.15, SW_Y, 0.8, 90, False), ("BAT", 105.15, s4[1], 0.8, 90, False),
          ("CR2032  + UP", BAT[0], 138.0, 0.9, 0, False),
          ("1", 148.3, 120.9, 0.9, 0, False),
          ("CASH BAG", CONN[0], 135.0, 1.0, 0, True), ("SAO++ rA", CONN[0], 136.8, 0.9, 0, False)]
for txt, x, y, size, rot, bold in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * (0.2 if bold else 0.15)))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LEDs:", {r: mm(fp.GetPosition()) for r, fp in led.items()})
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
