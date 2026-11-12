#!/usr/bin/env python3
"""Rebuild lumpy.kicad_pcb from the 2018 original plus the SAO++ changes (rev B: the whole board scaled up).

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/lumpy/hardware/build_board.py

What it does
  - loads original/lumpyv2.kicad_pcb (KiCad 5) and scales the outline and every piece of the maker's art by SCALE
    about the centre of the board's bounding box, so the drawing keeps its proportions (rev B, owner decision
    2026-11-12: scale up rather than squeeze). Parts do not scale: footprints keep their real size. Only the two
    LEDs, which are part of the picture (the star and the crown tip), move with the art.
  - removes the 4-pin through-hole header, the two 2018 LEDs (a reverse-mount TOPLED behind the star and a
    through-hole 3 mm LED standing up on the FRONT at the tip of the crown spike), both resistors, the old tracks,
    and the four small 2018 labels that belonged to those parts ("VCC", "+", "-" on the back, a pin-1 "o" on the front)
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - pours the back copper as the GND net (the 2018 back had no copper art at all, only silkscreen), cleared around
    the new pads and tracks and behind both LEDs
  - front copper art: the same shapes, with the old header's window filled and the switch's two peg holes cleared
  - front mask: a bare window at the tip of the spike, where the 2018 LED's legs went through

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).

The art footprints were made by svg2mod. How their layers map (checked 2026-11-10):
  lumpyTop    F.Cu (head + crown), F.Mask (two openings: the gold crown, and the star window)
  lumpyBottom F.Cu (the body, under mask), F.SilkS (eyes and teeth)
  lumpyback   B.SilkS ("OH MY GLOB / SAO / DEF CON 26"), B.Mask (a 2 mm window behind the star)
  board text  B.SilkS "Thanks To @UriShaked @mrtwinkletwink @ANDnXOR" (a KiCad text, not art)
So the back has no copper art: nothing of the maker's is rebuilt on the back, it is only added to.
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_Cu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

# ---- the one number that sets the board's size --------------------------------------------------
SCALE = 1.30        # rev B. 1.0 (rev A) needed two vias, an overhanging cell and a 0.4 mm knob; see README for 1.15/1.2

SLUG = "lumpy"
SRC = os.path.join(HERE, "..", "original", "lumpyv2.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND pour
TRACK = 0.30        # normal track width
THIN = 0.25         # track width up the crown spike and under R1
EDGE = 0.30         # copper stops this far short of the board edge
TAB_EDGE = 0.55     # ... and this far at the panel tabs, where 0.5 mm mouse-bite holes sit on the edge line

# ---- scaling about the centre of the 2018 outline's bounding box ---------------------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
_xs = [p[0] for p in _ol["outer"]]
_ys = [p[1] for p in _ol["outer"]]
CX, CY = (min(_xs) + max(_xs)) / 2, (min(_ys) + max(_ys)) / 2


def S(x, y):
    """A point of the 2018 drawing, moved to where it lands on the scaled board."""
    return (CX + SCALE * (x - CX), CY + SCALE * (y - CY))


ART_MODULES = ("lumpyv2:lumpyTop ", "lumpyv2:lumpyBottom ", "lumpyback:lumpyback ")


def scale_art(txt):
    """Scale the three svg2mod art footprints and the credits text in the KiCad 5 file text."""
    edits = []
    n = 0
    for a, b in blocks(txt, "module"):
        blk = txt[a:b]
        if not any(("(module " + m) in blk[:80] for m in ART_MODULES):
            continue
        n += 1
        blk = re.sub(r"\(at ([-0-9.]+) ([-0-9.]+)",
                     lambda m: "(at %.6f %.6f" % S(float(m.group(1)), float(m.group(2))), blk, count=1)
        blk = re.sub(r"\(xy ([-0-9.]+) ([-0-9.]+)\)",
                     lambda m: "(xy %.6f %.6f)" % (SCALE * float(m.group(1)), SCALE * float(m.group(2))), blk)
        edits.append((a, b, blk))
    assert n == 3, n
    for a, b in blocks(txt, "gr_text"):
        blk = txt[a:b]
        if '"Thanks To' not in blk[:30]:
            continue
        blk = re.sub(r"\(at ([-0-9.]+) ([-0-9.]+)\)",
                     lambda m: "(at %.6f %.6f)" % S(float(m.group(1)), float(m.group(2))), blk, count=1)
        blk = re.sub(r"\(size ([-0-9.]+) ([-0-9.]+)\)",
                     lambda m: "(size %.6f %.6f)" % (SCALE * float(m.group(1)), SCALE * float(m.group(2))), blk)
        blk = re.sub(r"\(thickness ([-0-9.]+)\)", lambda m: "(thickness %.6f)" % (SCALE * float(m.group(1))), blk)
        edits.append((a, b, blk))
    assert len(edits) == 4, len(edits)
    for a, b, blk in sorted(edits, reverse=True):
        txt = txt[:a] + blk + txt[b:]
    return txt


# ---- placement (centre x, y) on the scaled board ---------------------------------------------------
TIP = S(93.9292, 72.8472)   # 2018 D1 (3 mm LED, front) centre: pad 1 was at 92.6592 and pad 2 2.54 mm to its right
STAR = S(93.2972, 93.1164)  # 2018 D2 (TOPLED, back) centre, behind the star on the forehead
WINDOW = 1.6                # radius kept free of copper on both sides behind each LED so light gets into the board
TIP_MASK = 1.0              # radius of the bare (no copper, no mask) front window at the spike tip
CONN = (102.5, 139.0)       # J1, in the bottom lobes below the credits, as far from the edges as the lettering allows
SW = (103.64, 90.16)        # SW1 on the right side of the head: footprint origin, found by a search of the whole edge
SW_KNOB = -3.0              # direction the knob points, degrees in the front view (0 = right, -90 = up)
BAT = (115.4, 121.6)        # BT1 in the right lobe: cell fully on the board, no lettering under the cell or the clip
BAT_OPEN = -65.0            # direction the clip's open side faces, degrees: up and right, toward the edge above the cell

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_raw = open(SRC, encoding="utf-8").read()
_txt = scale_art(_raw)
_tmp_dir = tempfile.mkdtemp()
_scaled_src = os.path.join(_tmp_dir, "lumpyv2_scaled.kicad_pcb")
open(_scaled_src, "w", encoding="utf-8").write(_txt)
_cut = list(blocks(_txt, "segment"))
assert len(_cut) == 32, len(_cut)
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 578, len(_edges)
_cut += _edges
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("J1", "D1", "D2", "R1", "R2"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["D1", "D2", "J1", "R1", "R2"], _gone
_old_labels = []
for a_, b_ in blocks(_txt, "gr_text"):
    s_ = _txt[a_:b_]
    if re.match(r'\s*\(gr_text (VCC|o|-|\+) ', s_):
        _cut.append((a_, b_))
        _old_labels.append(s_.split()[1])
assert sorted(_old_labels) == ["+", "-", "VCC", "o"], _old_labels
# the front copper art is rebuilt below (old header window filled, peg holes cleared): read it from the scaled original
_fcu = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer F.Cu)" in _txt[b_ - 40:b_]]
assert len(_fcu) == 2, f"expected 2 front copper art polygons (head, body), found {len(_fcu)}"
_cut += _fcu
# The maker's 2 mm back mask window behind the star touched the new LED's pad openings (a DRC "mask bridge"). The
# LED footprint brings its own 1.9 mm window in the same place, so the 2018 one is dropped.
_bmask = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer B.Mask)" in _txt[b_ - 40:b_]]
assert len(_bmask) == 1, len(_bmask)
_cut += _bmask
_txt = cut_blocks(_txt, _cut)
_frames = stray_frames(_txt, 52 * SCALE)  # this board's svg2mod art carries no 2018 page frame; prove it
assert not _frames, f"{len(_frames)} stray page-frame polygons found"
_tmp = os.path.join(_tmp_dir, "lumpyv2.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(_scaled_src)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, F_Cu):
    front.Append(p_)
front.Simplify()
assert not footprint_polys(_orig, B_Cu), "the 2018 back had no copper art"

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 578 short lines; outline.json is the same path as one closed polygon ----
OUTLINE = [S(x, y) for x, y in _ol["outer"]]
body = poly(OUTLINE)
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(OUTLINE))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where copper may be
pour_area = grown(body, -TAB_EDGE)       # the back pour keeps 0.55 mm back everywhere (it is not art, so nothing is lost)
_bb = bbox_mm(body)
print("board size %.2f x %.2f mm (scale %.2f)" % (_bb[2] - _bb[0], _bb[3] - _bb[1], SCALE))

# ---- the maker's back lettering (silkscreen): nothing new may cover it -----------------------------
LETTERS = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(board, B_SilkS):
    LETTERS.Append(p_)
_thanks = [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetText().startswith("Thanks To")]
assert len(_thanks) == 1
_thanks[0].TransformTextToPolySet(LETTERS, 0, ERR, pcbnew.ERROR_INSIDE)
LETTERS.Simplify()
print("maker lettering on the back, mm2:", round(area_mm2(LETTERS), 1))

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
    fp.Reference().SetVisible(False)    # the back carries the maker's lettering; refs live on the fab layer and in the README
    return fp


def place(ref, pos, want, angles=(0, 90, 180, 270)):
    """Place on the back, then pick the rotation that puts pad `want[0]` at `want[1]`."""
    fp = load(ref, pos)
    best = None
    for rot in angles:
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


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def turn_to(fp, centre, direction_of, want, step=0.5):
    """Rotate fp (in `step` degree steps) until direction_of(fp) points along `want` degrees."""
    best = None
    for k in range(int(360 / step)):
        rot = k * step
        fp.SetOrientationDegrees(rot)
        d = angle_diff(direction_of(fp), want)
        if best is None or d < best[0]:
            best = (d, rot)
    fp.SetOrientationDegrees(best[1])
    assert best[0] < step, f"{fp.GetReference()}: cannot point at {want} degrees"
    return best[1]


# J1: VCC (pin 1) top row, left in front view = the same corner as the 2018 header's VCC pin; key slot up
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))


# SW1: the knob points away from the pins, through the middle of the two locating pegs
def _knob_dir(fp):
    pegs = [p.GetPosition() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    pins = [p.GetPosition() for p in fp.Pads() if p.GetNumber() in ("1", "4")]
    mx, my = sum(ToMM(p.x) for p in pegs) / 2, sum(ToMM(p.y) for p in pegs) / 2
    nx, ny = sum(ToMM(p.x) for p in pins) / 2, sum(ToMM(p.y) for p in pins) / 2
    return math.degrees(math.atan2(my - ny, mx - nx))


sw = load("SW1", SW)
SW_ROT = turn_to(sw, SW, _knob_dir, SW_KNOB)
link(sw, "SW1")

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the open side faces
bat = load("BT1", BAT)


def _open_dir(fp):
    fab = [g for g in fp.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and hasattr(g, "GetShape") and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY)
           and ToMM(g.GetBoundingBox().GetWidth()) > 15]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(BAT[1] - ToMM(c.y), BAT[0] - ToMM(c.x)))


# Measured at 0/90/180/270 degrees (a rectangle turns into a polygon at other angles): the open side faces the
# direction from the body rectangle's centre to the clip's centre. Then the clip is turned by the remaining angle.
for _r in (0, 90, 180, 270):
    bat.SetOrientationDegrees(_r)
    _d0 = _open_dir(bat)
    if angle_diff(_d0, 0.0) < 1:
        break
else:
    raise AssertionError("no right-angle rotation turns the clip's open side to the right")
# turning the footprint by +a degrees turns its open side by -a degrees in the front view (y grows down)
BAT_ROT = (_r - BAT_OPEN) % 360
bat.SetOrientationDegrees(BAT_ROT)
# KiCad 10 calls this clip's courtyard (a circle overlapping a rectangle) "malformed" at exact right angles and, it
# turns out, at some others (325-332 degrees fail, 335 passes): check it here rather than wait for DRC.
bat.BuildCourtyardCaches()
assert not bat.GetFlags() & pcbnew.MALFORMED_COURTYARDS, f"KiCad finds the clip's courtyard malformed at {BAT_ROT} degrees"
link(bat, "BT1")
# The clip is one piece of metal joining its two "+" pads; the footprint is told so (KiCad 9+ "jumper" pads), and
# only the pad nearer the switch is routed.
bat.SetDuplicatePadNumbersAreJumpers(True)
# The clip's own silkscreen (closed-end line, open-side arrow, "+") moves to the fab drawing; the board carries its
# own labels (see below), placed clear of the maker's lettering.
for it in bat.GraphicalItems():
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
print("battery clip angle", BAT_ROT)

_od = _open_dir(bat)
assert angle_diff(_od, BAT_OPEN) < 1, f"clip open side faces {_od:.1f}, wanted {BAT_OPEN}"

# D1 (tip, red) and D2 (star, white): reverse-mount, lens into the board, centred on the art
d1 = load("D1", TIP)
d2 = load("D2", STAR)
for _fp in (d1, d2):
    _fp.SetOrientationDegrees(0)
    link(_fp, _fp.GetReference())

# Resistors, beside the switch. R1 stands upright so the badge-power wire (VSAO) can pass straight between its two
# pads (0.85 mm apart: 0.3 mm of clearance on each side of a 0.25 mm wire, under the resistor's solder mask). That is
# how the badge supply gets past the LED-supply wire on one copper layer without vias (see "Routing" below).
P1 = padpos(sw, "1")
R1C = (99.5, P1[1])                  # gap centred on switch pin 1's height, so VSAO runs dead straight
R2C = (97.15, STAR[1])               # level with the star LED, east of it, outside its light window
r1 = place("R1", R1C, ("1", (R1C[0], R1C[1] + 0.825)))     # pad 1 (LED supply) below, pad 2 (to the tip LED) above
r2 = place("R2", R2C, ("1", (R2C[0] + 0.825, R2C[1])))     # pad 1 (LED supply) east, pad 2 west toward the star

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board, and no new pad may touch the maker's lettering
CLIP_EDGE = 1.0                          # the cell clip's pads and bare disc stay at least 1 mm inside the edge
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                keep = CLIP_EDGE if fp.GetReference() == "BT1" else (0.25 if fp.GetReference() == "SW1" else EDGE)
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(grown(body, -keep))
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {keep} mm to the board edge"
                hit = pad_poly(pad, B_Cu, 0.3)
                hit.BooleanIntersection(LETTERS)
                assert area_mm2(hit) < 1e-4, f"{fp.GetReference()} pad {pad.GetNumber()} is within 0.3 mm of the maker's lettering"
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                off = pcbnew.SHAPE_POLY_SET()
                add_circle(off, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.25)
                off.BooleanSubtract(body)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} peg hole is too close to the edge"
# the fitted cell (20 mm) lies wholly on the board and covers none of the maker's lettering
CELL = pcbnew.SHAPE_POLY_SET()
add_circle(CELL, P(*BAT), 10.0)
_c = pcbnew.SHAPE_POLY_SET(CELL)
_c.BooleanSubtract(body)
assert area_mm2(_c) < 1e-4, "the cell overhangs the board edge"
_c = grown(CELL, 0.3)
_c.BooleanIntersection(LETTERS)
assert area_mm2(_c) < 1e-4, "the cell covers the maker's lettering"
# and no part body covers lettering either: J1's shroud, the clip and the switch are opaque. A body is the largest
# outline on the part's fab drawing, plus its pads.
def fab_body(fp):
    best = None
    for it in fp.GraphicalItems():
        if it.GetLayer() != pcbnew.B_Fab or not hasattr(it, "GetShape"):
            continue
        if it.GetShape() == pcbnew.SHAPE_T_RECT:
            ps = poly([mm(c) for c in it.GetRectCorners()])
        elif it.GetShape() == pcbnew.SHAPE_T_POLY:
            ps = pcbnew.SHAPE_POLY_SET(it.GetPolyShape())
        else:
            continue
        if best is None or area_mm2(ps) > area_mm2(best):
            best = ps
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu):
            best.Append(pad_poly(pad, B_Cu))
    best.Simplify()
    return best


for ref in ("J1", "BT1", "SW1"):
    fp = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    cy = fab_body(fp)
    cy.BooleanIntersection(grown(LETTERS, 0.3))
    print(f"{ref} body within 0.3 mm of the maker's lettering, mm2:", round(area_mm2(cy), 3))
    assert area_mm2(cy) < 1e-3, f"{ref} would hide some of the maker's lettering"


def edge_dist(fp):
    """Smallest distance from a part's body and pads to the board edge (mm), in 0.05 mm steps."""
    cy = fab_body(fp)
    for k in range(0, 200):
        g = grown(cy, k * 0.05)
        g.BooleanSubtract(body)
        if area_mm2(g) > 1e-4:
            return k * 0.05
    return 10.0


print("J1 body and pads to the board edge, mm:", edge_dist(conn))

for ref in ("J1", "SW1", "BT1", "D1", "D2", "R1", "R2"):
    fp = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    print(ref, "at", mm(fp.GetPosition()), "rot", round(fp.GetOrientationDegrees(), 2), {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber()})


# ---- how far the switch knob sticks out past the edge ----------------------------------------------
def knob_proud():
    """(at the middle position, worst over the whole slide) distance the knob tip reaches past the board edge."""
    k = _knob_dir(sw)
    u = (math.cos(math.radians(k)), math.sin(math.radians(k)))
    v = (-u[1], u[0])
    o = mm(sw.GetPosition())

    def furthest_board(xs):
        far = 1.6
        for x in xs:
            for i in range(0, 31):
                y = 1.6 + i * 0.05
                pt = P(o[0] + x * v[0] + y * u[0], o[1] + x * v[1] + y * u[1])
                if body.Contains(pt):
                    far = max(far, y)
        return far
    mid = 3.1 - furthest_board([x / 10 for x in range(-6, 7)])
    worst = 3.1 - furthest_board([x / 10 for x in range(-21, 22)])
    return round(mid, 2), round(worst, 2)


print("switch knob past the edge (middle position, worst position), mm:", knob_proud())

if os.environ.get("PLACE_ONLY"):
    pcbnew.SaveBoard(OUT, board)
    sys.exit(0)


# ---- Routing (back copper only, no vias) ------------------------------------------------------------
# The switch's common pin 3 lies between its badge pin 1 and cell pin 4, and the LED supply that leaves pin 3 has to
# reach the tip of the crown, at the board edge. So on one layer the LED-supply wire always fences pin 1 off from
# pin 4: one of the two supplies has to get across it. Rev A crossed with two vias. Here the badge supply crosses
# between the two pads of R1, the resistor that sits in that wire, under the resistor's solder mask.
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


def spike_centre(y):
    """Middle of the crown spike at height y (front view), from the outline."""
    xs = []
    for (x1, y1), (x2, y2) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        if (y1 <= y) != (y2 <= y):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    xs = sorted(x for x in xs if abs(x - TIP[0]) < 6)
    return ((xs[0] + xs[1]) / 2, xs[1] - xs[0]) if len(xs) == 2 else None


s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
bt = padpos(bat, "1", pick=lambda p: p[1])               # the clip pad nearer the switch (the upper one)
d1a, d1k = padpos(d1, "2"), padpos(d1, "1")
d2a = padpos(d2, "2")
r1p1, r1p2 = padpos(r1, "1"), padpos(r1, "2")
r2p1, r2p2 = padpos(r2, "1"), padpos(r2, "2")
j1 = padpos(conn, "1")

# LED supply: switch pin 3 -> west -> up into R1's lower pad, with a branch to R2's east pad
VX = r1p1[0]
route("VLOAD", [s3, (VX + 0.7, s3[1]), (VX, s3[1] - 0.7), r1p1])
route("VLOAD", [(VX, r2p1[1]), r2p1])
# star: R2 west pad -> straight across to the anode
route("LED2_A", [r2p2, d2a])
# crown spike: the tip LED's anode wire on the east side of the spike, its cathode (GND) wire on the west side,
# 0.8 mm apart, following the middle of the spike down to its base
SPIKE = []
for k in range(0, 20):
    y = d1a[1] + 3.6 + k * 1.2
    cw = spike_centre(y)
    if cw is None:
        break
    SPIKE.append((round(y, 3), cw[0], cw[1]))
print("spike centre/width (y, x, w):", [(round(a, 1), round(b, 2), round(c, 2)) for a, b, c in SPIKE[:4]], "...")
assert min(w for _, _, w in SPIKE) > 2.4, "spike too narrow for two wires"
route("LED1_A", [d1a, (d1a[0], SPIKE[0][0] - 1.0)] + [(c + 0.4, y) for y, c, w in SPIKE] +
      [(r1p2[0], r1p2[1] - 2.0), r1p2], width=THIN)
route("GND", [d1k, (d1k[0], SPIKE[0][0] - 1.0)] + [(c - 0.4, y) for y, c, w in SPIKE] +
      [(SPIKE[-1][1] - 1.2, SPIKE[-1][0] + 2.0)], width=THIN)
# badge 3.3 V: switch pin 1 -> straight west between R1's pads -> along the top of the star's light window ->
# down the west side of the star -> south-west across the neck -> down the left side of the board, outside the
# lettering -> east under the credits -> into connector pin 1 from the west
SX = STAR[0] - WINDOW - 1.6
route("VSAO", [s1, (VX - 1.2, s1[1]), (SX, s1[1]), (SX, STAR[1] + 3.0), (80.5, 97.0), (72.5, 99.5), (72.5, 108.5),
               (75.5, 111.5), (75.5, 134.0), (77.0, j1[1] + 1.2), (j1[0] - 1.6, j1[1] + 1.2), (j1[0] - 0.55, j1[1] + 1.2)], width=THIN)
# coin cell +: switch pin 4 -> round the switch's lower solder tab -> down the right side of "OH" -> the clip's upper pad
# (into the clip pad from its outer end, so the wire stays outside the 20 mm circle the cell covers)
_ax = ((bt[0] - BAT[0]) / 10.5, (bt[1] - BAT[1]) / 10.5)
_end = (bt[0] - 1.6 * _ax[1], bt[1] + 1.6 * _ax[0]) if _ax[0] < 0 else (bt[0] + 1.6 * _ax[1], bt[1] - 1.6 * _ax[0])
route("VBAT", [s4, (s4[0] - 0.7, s4[1] + 0.7), (s4[0] - 0.7, 96.6), (104.5, 97.6), (110.8, 100.5), (110.8, 111.8),
               (_end[0], _end[1] - 0.6), _end])

# every track inside the board, clear of the edge, and none across the maker's lettering
for t, _c in TRACKS:
    o = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(o, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    o.BooleanSubtract(inner)
    assert area_mm2(o) < 1e-4, f"track {mm(t.GetStart())}-{mm(t.GetEnd())} comes within {EDGE} mm of the edge"
    o = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(o, B_Cu, FromMM(0.5), ERR, pcbnew.ERROR_OUTSIDE)
    o.BooleanIntersection(LETTERS)
    assert area_mm2(o) < 1e-4, f"track {mm(t.GetStart())}-{mm(t.GetEnd())} comes within 0.5 mm of the maker's lettering"
    if t.GetNetCode() != nets["GND"].GetNetCode():
        o = pcbnew.SHAPE_POLY_SET()
        t.TransformShapeToPolygon(o, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
        o.BooleanIntersection(CELL)
        assert area_mm2(o) < 1e-4, f"track {mm(t.GetStart())}-{mm(t.GetEnd())} runs under the coin cell"

# ---- GND copper: one pour over the back, cleared around everything that is not GND -----------------
art = pcbnew.SHAPE_POLY_SET(pour_area)
_spike_box = [S(85, 60), S(103, 60), S(103, 84.3), S(85, 84.3)]
art.BooleanSubtract(poly(_spike_box))   # no pour up the spike: only its two wires
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)                          # solid copper under the cell so the bare cell pad is whole
disc.BooleanIntersection(grown(body, -0.27))
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
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for c_ in (TIP, STAR):                                   # light path behind the star and the spike tip
    add_circle(cut, P(*c_), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# every separate piece that touches a GND pad or the spike's GND track carries the GND net; the rest is dropped
gnd_cu = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_cu.Append(pad_poly(pad, B_Cu))
for t, _c in TRACKS:
    if t.GetNetCode() == gnd_code:
        t.TransformShapeToPolygon(gnd_cu, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_cu.Simplify()
n_gnd = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_cu)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
    else:
        print("  dropped loose pour piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back GND pour pieces:", n_gnd)
assert n_gnd == 1, "the ground pour should be one piece"

# ---- front copper art: same shapes as 2018, minus the window the old through-hole header sat in ----
fgaps = pcbnew.SHAPE_POLY_SET(grown(body, -0.3))
fgaps.BooleanSubtract(front)
fgaps.BooleanIntersection(poly([S(94.0, 133.0), S(104.5, 133.0), S(104.5, 141.5), S(94.0, 141.5)]))
fgaps.Simplify()
_filled = 0
for i in range(fgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(fgaps.Polygon(i))
    if one.Contains(P(*S(99.31, 137.31))):               # centre of the 2018 header
        front.BooleanAdd(grown(one, 0.05))
        _filled = area_mm2(one)
assert 10 * SCALE ** 2 < _filled < 60 * SCALE ** 2, f"front window at the old header: {_filled:.1f} mm2"
print("filled old header window on the front, area mm2:", round(_filled, 1))
_star = pcbnew.SHAPE_POLY_SET(front)
_win = pcbnew.SHAPE_POLY_SET()
add_circle(_win, P(*STAR), WINDOW)
_star.BooleanIntersection(_win)
print("front copper art inside the star LED's 1.6 mm window (left as drawn), mm2:", round(area_mm2(_star), 3))
_tipf = pcbnew.SHAPE_POLY_SET(front)
_win = pcbnew.SHAPE_POLY_SET()
add_circle(_win, P(*TIP), WINDOW)
_tipf.BooleanIntersection(_win)
assert area_mm2(_tipf) < 1e-4, "front copper at the spike tip"
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
front.BooleanSubtract(pegs)
front.BooleanIntersection(inner)
# at the panel's break-off tabs the front art also steps back to 0.55 mm, clear of the mouse-bite holes
PANEL = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))
band = pcbnew.SHAPE_POLY_SET(body)
band.BooleanSubtract(grown(body, -TAB_EDGE))
tabzone = pcbnew.SHAPE_POLY_SET()
for t_ in PANEL["tabs"]:
    add_circle(tabzone, P(*t_["near"]), 3.2)
tabzone.Simplify()
band.BooleanIntersection(tabzone)
front.BooleanSubtract(band)
front.Simplify()
add_filled(board, front, F_Cu)
# nothing electrical sits near a panel tab: the mouse-bite holes reach 0.25 mm into the board
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu):
                h = pad_poly(pad, B_Cu, 0.3)
                h.BooleanIntersection(band)
                assert area_mm2(h) < 1e-4, f"{fp.GetReference()} pad {pad.GetNumber()} is too near a panel tab"

# front mask: a bare window at the spike tip (the 2018 LED's legs went through here; now light comes through)
tipmask = pcbnew.SHAPE_POLY_SET()
add_circle(tipmask, P(*TIP), TIP_MASK)
add_filled(board, tipmask, pcbnew.F_Mask)

# ---- back silkscreen (none may touch the maker's lettering or a pad) --------------------------------
_od = math.radians(BAT_OPEN)
_lbl = (BAT[0] + 13.0 * math.cos(_od) - 3.0, BAT[1] + 13.0 * math.sin(_od) + 1.0)
LABELS = [("SAO", 100.5, r1p2[1] - 1.9, 0.8, 90), ("OFF", 100.5, r1p1[1] + 2.1, 0.8, 90),
          ("BAT", 100.5, s4[1] + 0.4, 0.8, 90),
          ("CR2032", 117.6, 102.6, 0.8, 0), ("+ SIDE UP", 117.6, 103.9, 0.8, 0),
          ("SAO++ rB", 78.0, 129.0, 0.9, 0), ("1", 97.9, j1[1], 0.9, 0)]
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.15))
bare.Simplify()
SILK = []
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
    ps = pcbnew.SHAPE_POLY_SET()
    t.TransformTextToPolySet(ps, 0, ERR, pcbnew.ERROR_INSIDE)
    SILK.append((txt, ps))
# an arrow at the clip's open side, pointing at the cell: it slides in from here
# (the edge is only about 10.6 mm from the cell's centre on that side, so the arrow sits on the cell's rim, outside the bare disc)
_tip_a = (BAT[0] + 9.0 * math.cos(_od), BAT[1] + 9.0 * math.sin(_od))
_tail_a = (BAT[0] + 10.05 * math.cos(_od), BAT[1] + 10.05 * math.sin(_od))
for a_, b_ in [(_tail_a, _tip_a), (_tip_a, (_tip_a[0] + 0.5 * math.cos(_od + 0.6), _tip_a[1] + 0.5 * math.sin(_od + 0.6))),
               (_tip_a, (_tip_a[0] + 0.5 * math.cos(_od - 0.6), _tip_a[1] + 0.5 * math.sin(_od - 0.6)))]:
    ln = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    ln.SetStart(P(*a_))
    ln.SetEnd(P(*b_))
    ln.SetWidth(FromMM(0.15))
    ln.SetLayer(B_SilkS)
    board.Add(ln)
    ps = pcbnew.SHAPE_POLY_SET()
    ln.TransformShapeToPolygon(ps, B_SilkS, 0, ERR, pcbnew.ERROR_OUTSIDE)
    SILK.append(("arrow", ps))
for txt, ps in SILK:
    for other, what in ((LETTERS, "the maker's lettering"), (bare, "a pad")):
        h = pcbnew.SHAPE_POLY_SET(ps)
        h.BooleanIntersection(grown(other, 0.15))
        assert area_mm2(h) < 1e-4, f"label {txt!r} touches {what}"
    o = pcbnew.SHAPE_POLY_SET(ps)
    o.BooleanSubtract(grown(body, -0.2))
    assert area_mm2(o) < 1e-4, f"label {txt!r} is off the board"

# ---- nothing may lie outside the outline on any manufactured layer --------------------------------
MADE = [pcbnew.F_Cu, B_Cu, pcbnew.F_SilkS, B_SilkS, pcbnew.F_Mask, pcbnew.B_Mask, pcbnew.F_Paste, pcbnew.B_Paste]
_bbx = body.BBox()
_bbx.Inflate(FromMM(0.05))
for it in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()] + \
        [p for fp in board.GetFootprints() for p in fp.Pads()] + list(board.Tracks()):
    lays = [L for L in MADE if it.IsOnLayer(L)]
    if lays and it.GetClass() != "PCB_FIELD":
        bb = it.GetBoundingBox()
        assert _bbx.Contains(bb.GetOrigin()) and _bbx.Contains(bb.GetEnd()), f"{it.GetClass()} on {board.GetLayerName(lays[0])} lies outside the board outline"

# ---- report -------------------------------------------------------------------------------------
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
