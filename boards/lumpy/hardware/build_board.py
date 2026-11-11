#!/usr/bin/env python3
"""Rebuild lumpy.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/lumpy/hardware/build_board.py

What it does
  - loads original/lumpyv2.kicad_pcb (KiCad 5) so the art stays exactly as drawn
  - removes the 4-pin through-hole header, the two 2018 LEDs (a reverse-mount TOPLED behind the star and a
    through-hole 3 mm LED standing up on the FRONT at the tip of the crown spike), both resistors, the old tracks,
    and the four small 2018 labels that belonged to those parts ("VCC", "+", "-" on the back, a pin-1 "o" on the front)
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - pours the back copper as the GND net (the 2018 back had no copper art at all, only silkscreen), cleared around
    the new pads and tracks and behind both LEDs
  - front copper art: the same shapes, with the old header's window filled and the switch's two peg holes cleared
  - front mask: a 2 mm bare window at the tip of the spike, where the 2018 LED's legs went through

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

SLUG = "lumpy"
SRC = os.path.join(HERE, "..", "original", "lumpyv2.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND pour
TRACK = 0.30        # normal track width
THIN = 0.25         # track width up the crown spike, which is 2.06 mm wide at its narrowest
EDGE = 0.30         # copper stops this far short of the board edge
TAB_EDGE = 0.55     # ... and this far at the panel tabs, where 0.5 mm mouse-bite holes sit on the edge line

# ---- placement (centre x, y) ------------------------------------------------------------------
TIP = (93.9292, 72.8472)    # 2018 D1 (3 mm LED, front) centre: pad 1 was at 92.6592 and pad 2 2.54 mm to its right
STAR = (93.2972, 93.1164)   # 2018 D2 (TOPLED, back) centre, behind the star on the forehead
WINDOW = 1.6                # radius kept free of copper on both sides behind each LED so light gets into the board
TIP_MASK = 1.0              # radius of the bare (no copper, no mask) front window at the spike tip
CONN = (99.3, 134.05)       # J1, in the middle bottom lobe where the 2018 header was; as low as the lobe allows
SW = (101.6, 95.0)          # SW1 on the right side of the head, knob pointing right (found by a search of the whole edge)
SW_ROT = 280                # footprint rotation on the back: knob right and 10 degrees up, pin 1 at the top
BAT = (108.8, 118.1)        # BT1 on the right side: the only place a 17 mm cell disc fits at all (see README).
                            # Its bare disc pad comes to 0.25 mm from the edge (KiCad's minimum) at the notch below it,
                            # and grazes the tip of the "6" in "DEF CON 26" (about 0.01 mm2, a nick the fab clips off the ink)

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
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
# the front copper art is rebuilt below (old header window filled, peg holes cleared): read it from the untouched original
_fcu = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer F.Cu)" in _txt[b_ - 40:b_]]
assert len(_fcu) == 2, f"expected 2 front copper art polygons (head, body), found {len(_fcu)}"
_cut += _fcu
# The maker's 2 mm back mask window behind the star touched the new LED's pad openings (a DRC "mask bridge"). The
# LED footprint brings its own 1.9 mm window in the same place, so the 2018 one is dropped.
_bmask = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4) if "(layer B.Mask)" in _txt[b_ - 40:b_]]
assert len(_bmask) == 1, len(_bmask)
_cut += _bmask
_txt = cut_blocks(_txt, _cut)
_frames = stray_frames(_txt, 52)         # this board's svg2mod art carries no 2018 page frame; prove it
assert not _frames, f"{len(_frames)} stray page-frame polygons found"
_tmp = os.path.join(tempfile.mkdtemp(), "lumpyv2.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, F_Cu):
    front.Append(p_)
front.Simplify()
assert not footprint_polys(_orig, B_Cu), "the 2018 back had no copper art"

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 578 short lines; outline.json is the same path as one closed polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where copper may be
pour_area = grown(body, -TAB_EDGE)       # the back pour keeps 0.55 mm back everywhere (it is not art, so nothing is lost)

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


# J1: VCC (pin 1) top row, left in front view = the same corner as the 2018 header's VCC pin; key slot up
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))
# SW1: a search over the whole outline (every pad >= 0.25 mm inside the edge, peg holes inside, switch body no more
# than 0.25 mm2 past the edge) found no spot where more than ~0.45 mm of knob shows: every lobe of this outline curves
# too tightly for a 10 mm long switch. This spot, on the side of the head just above the shoulder, is among the best.
sw = load("SW1", SW)
sw.SetOrientationDegrees(SW_ROT)
link(sw, "SW1")
# D1 (tip, red): anode (pad 2) on the left, so the anode track takes the left side of the spike and its resistor sits
# on the left of the spike base; the cathode track takes the right side.  D2 (star, white): anode on the left, toward R2.
d1 = place("D1", TIP, ("2", (TIP[0] - 1.55, TIP[1])))
d2 = place("D2", STAR, ("2", (STAR[0] - 1.55, STAR[1])))
R1C = (93.55, 86.60)        # vertical, in line with the spike's anode track; pad 2 (LED side) at the top
R2C = (88.90, STAR[1])      # horizontal, left of the star, outside its light window; pad 2 (LED side) toward the LED
r1 = place("R1", R1C, ("2", (R1C[0], R1C[1] - 0.825)))
r2 = place("R2", R2C, ("2", (R2C[0] + 0.825, R2C[1])))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the open side faces
bat = load("BT1", BAT)
BAT_OPEN = (1.0, 0.0)                    # the open side faces the right-hand board edge; the cell slides in from there


def _open_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(BAT[1] - ToMM(c.y), BAT[0] - ToMM(c.x)))


for _rot in (0, 90, 180, 270):
    _d = _open_dir(_rot)
    if abs((_d - math.degrees(math.atan2(BAT_OPEN[1], BAT_OPEN[0])) + 180) % 360 - 180) < 1:
        break
else:
    raise AssertionError("no right-angle rotation turns the clip's open side to the right")
# KiCad 10 reports the shared clip footprint's courtyard (a circle overlapping a rectangle) as "malformed" at exactly
# 0/90/180/270 degrees; 0.1 degree off a right angle it is accepted. The 0.1 degree moves nothing by more than 0.02 mm.
bat.SetOrientationDegrees(_rot - 0.1)
link(bat, "BT1")
# The clip is one piece of metal joining its two "+" pads. Mad Cat also joins them with a track round the closed end;
# here that track would have to run through the maker's lettering ("26" and the credits), so instead the footprint is
# told that pads with the same number are joined inside the part (KiCad 9+ "jumper" pads). Only the lower pad is routed.
bat.SetDuplicatePadNumbersAreJumpers(True)
# The clip's own silkscreen (closed-end line, open-side arrow, "+") would print across the lettering and off the
# board edge here; it moves to the fab drawing, and the board carries its own marks (see labels below).
for it in bat.GraphicalItems():
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
print("battery clip angle", _rot)

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board, and no new pad may touch the maker's lettering
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                disc = fp.GetReference() == "BT1" and pad.GetNumber() == "2"
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(grown(body, -0.25) if (disc or fp.GetReference() == "SW1") else inner)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {EDGE} mm to the board edge"
                hit = pad_poly(pad, B_Cu, 0.0 if disc else 0.05)
                hit.BooleanIntersection(LETTERS)
                if disc:
                    print("cell disc over the maker's lettering, mm2:", round(area_mm2(hit), 4))
                assert area_mm2(hit) < (0.02 if disc else 0.005), f"{fp.GetReference()} pad {pad.GetNumber()} lies on the maker's lettering ({area_mm2(hit):.3f} mm2)"
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                off = pcbnew.SHAPE_POLY_SET()
                add_circle(off, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.2)
                off.BooleanSubtract(body)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} peg hole is too close to the edge"

for ref in ("J1", "SW1", "BT1", "D1", "D2", "R1", "R2"):
    fp = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    print(ref, "at", mm(fp.GetPosition()), "rot", fp.GetOrientationDegrees(), {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber()})

if os.environ.get("PLACE_ONLY"):
    pcbnew.SaveBoard(OUT, board)
    sys.exit(0)


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
bt = padpos(bat, "1", pick=lambda p: p[1])               # the clip pad nearer the switch (the upper one)
d1a, d1k = padpos(d1, "2"), padpos(d1, "1")
d2a = padpos(d2, "2")

# How the wires get past each other on one layer. The LED supply (switch pin 3) runs to R2, R1 and up the spike to
# the tip, so with the switch on the head it fences in pin 1 (badge 3.3 V), which must reach the connector at the
# bottom. Pin 1's wire therefore hops over the LED supply once: two small holes ("vias", covered by solder mask on
# both sides) inside the dark open mouth on the front, joined by a 1.6 mm copper link under the mask.
VIA_A, VIA_B = (90.6, 110.8), (90.6, 112.2)   # the only spots in the mouth clear of teeth, copper and back lettering

# LED supply: switch pin 3 -> down the gap between "OH" and "MY" -> across under the mouth, between "SAO" and
# "DEF CON 26" (and between the two vias) -> up the left side, outside the lettering -> into the head -> R2 -> R1
TRUNK = [s3, (99.15, 97.5), (99.15, 109.0), (98.0, 111.5), (79.8, 111.5), (79.8, 100.5), (84.6, 98.0),
         (padpos(r2, "1")[0], 95.6), padpos(r2, "1")]
route("VLOAD", TRUNK)
r1p1 = padpos(r1, "1")
route("VLOAD", [padpos(r2, "1"), (padpos(r2, "1")[0], 90.4), (91.4, 88.6), (r1p1[0], 88.6), r1p1])
# badge 3.3 V: switch pin 1 -> down beside the star -> the gap between "MY" and "GLOB" -> round the end of "SAO" ->
# via A ... (front link) ... via B -> left under "DEF CON 26" -> down the left side -> into connector pin 1
route("VSAO", [s1, (97.6, s1[1]), (97.0, 92.9), (97.0, 99.5), (91.14, 101.6), (91.14, 105.9), (89.3, 106.9),
               (89.3, VIA_A[1]), VIA_A])
route("VSAO", [VIA_B, (85.6, 112.45), (85.6, j1[1]), j1])
# coin cell +: switch pin 4 -> down past the switch's lower solder tabs -> across the shoulder -> the upper clip pad
route("VBAT", [s4, (s4[0], 101.4), (106.3, 101.4), (bt[0] - 1.2, bt[1] - 0.9)])
# star: R2 pad 2 -> straight across to the anode
route("LED2_A", [padpos(r2, "2"), d2a])
# spike: anode track on the left, cathode (GND) track on the right; 0.25 mm wide, 0.55 mm apart through the 2.06 mm neck
NECK_A, NECK_K = 93.55, 94.35
route("LED1_A", [padpos(r1, "2"), (NECK_A, 76.2), (NECK_A, 75.6), (d1a[0], 74.3), d1a], width=THIN)
route("GND", [d1k, (d1k[0], 74.3), (NECK_K, 75.6), (NECK_K, 77.3), (94.6, 78.2), (94.6, 85.9)], width=THIN)

VIAS = []
for c_ in (VIA_A, VIA_B):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c_))
    v.SetWidth(FromMM(0.6))
    v.SetDrill(FromMM(0.3))
    v.SetLayerPair(pcbnew.F_Cu, B_Cu)
    v.SetNet(nets["VSAO"])
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append(v)
link_ = pcbnew.PCB_TRACK(board)
link_.SetStart(P(*VIA_A))
link_.SetEnd(P(*VIA_B))
link_.SetWidth(FromMM(THIN))
link_.SetLayer(F_Cu)
link_.SetNet(nets["VSAO"])
board.Add(link_)

# every track inside the board, clear of the edge
for t, _c in TRACKS:
    o = pcbnew.SHAPE_POLY_SET()
    t.TransformShapeToPolygon(o, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    o.BooleanSubtract(inner)
    assert area_mm2(o) < 1e-4, f"track {mm(t.GetStart())}-{mm(t.GetEnd())} comes within {EDGE} mm of the edge"

# ---- GND copper: one pour over the back, cleared around everything that is not GND -----------------
art = pcbnew.SHAPE_POLY_SET(pour_area)
art.BooleanSubtract(poly([(85, 60), (103, 60), (103, 84.3), (85, 84.3)]))  # no pour up the spike: only its two tracks
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
            # R1 is narrower: the gap between its two pads is the copper bridge that joins the left and right halves
            # of the ground pour (the LED-supply track runs from the switch to the spike tip and would split it)
            c_ = 0.2 if fp.GetReference() == "R1" else CLEAR
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(c_), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
for v in VIAS:
    add_circle(cut, v.GetPosition(), 0.3 + CLEAR)
for c_ in (TIP, STAR):                                   # light path behind the star and the spike tip
    add_circle(cut, P(*c_), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# no new track may run through the maker's lettering
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(grown(LETTERS, 0.1))
assert area_mm2(_hit) < 0.001, f"a track channel overlaps the maker's lettering by {area_mm2(_hit):.3f} mm2"
for v in VIAS:                                           # the vias: their pads clear of the back lettering ...
    _h = pcbnew.SHAPE_POLY_SET()
    add_circle(_h, v.GetPosition(), 0.3)
    _h.BooleanIntersection(grown(LETTERS, 0.15))
    assert area_mm2(_h) < 1e-4, "a via touches the back lettering"

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

# ---- front copper art: same shapes as 2018, minus the window the old through-hole header sat in ----
fgaps = pcbnew.SHAPE_POLY_SET(grown(body, -0.3))
fgaps.BooleanSubtract(front)
fgaps.BooleanIntersection(poly([(94.0, 133.0), (104.5, 133.0), (104.5, 141.5), (94.0, 141.5)]))
fgaps.Simplify()
_filled = 0
for i in range(fgaps.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(fgaps.Polygon(i))
    if one.Contains(P(99.31, 137.31)):                   # centre of the 2018 header
        front.BooleanAdd(grown(one, 0.05))
        _filled = area_mm2(one)
assert 10 < _filled < 60, f"front window at the old header: {_filled:.1f} mm2"
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
# ... and on the front they sit in bare dark mouth: no art copper within 0.25 mm, no white tooth within 0.1 mm
_fv = pcbnew.SHAPE_POLY_SET()
for v in VIAS:
    add_circle(_fv, v.GetPosition(), 0.3 + 0.25)
link_.TransformShapeToPolygon(_fv, F_Cu, FromMM(0.25), ERR, pcbnew.ERROR_OUTSIDE)
_fv.BooleanIntersection(front)
assert area_mm2(_fv) < 1e-4, "front art copper too close to the vias or their link"
_fs = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(board, pcbnew.F_SilkS):
    _fs.Append(p_)
_fv = pcbnew.SHAPE_POLY_SET()
for v in VIAS:
    add_circle(_fv, v.GetPosition(), 0.4)
_fv.BooleanIntersection(_fs)
assert area_mm2(_fv) < 1e-4, "a via lands on a white tooth"
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

# front mask: a bare 2 mm window at the spike tip (the 2018 LED's legs went through here; now light comes through)
tipmask = pcbnew.SHAPE_POLY_SET()
add_circle(tipmask, P(*TIP), TIP_MASK)
add_filled(board, tipmask, pcbnew.F_Mask)

# ---- back silkscreen labels (none may touch the maker's lettering or a pad) ------------------------
LABELS = [("SAO", 98.0, 91.9, 0.8, 90), ("OFF", 98.0, 94.6, 0.8, 90), ("BAT", 98.0, 97.3, 0.8, 90),
          ("CR2032", 111.2, 100.4, 0.8, 0), ("+ SIDE UP", 111.2, 101.7, 0.8, 0), ("<", 118.7, BAT[1], 1.0, 0),
          ("SAO++ rA", 81.0, 127.0, 0.9, 0), ("1", 95.0, 128.8, 0.9, 0)]
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.15))
bare.Simplify()
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
    for other, what in ((LETTERS, "the maker's lettering"), (bare, "a pad")):
        h = pcbnew.SHAPE_POLY_SET(ps)
        h.BooleanIntersection(grown(other, 0.15))
        assert area_mm2(h) < 1e-4, f"label {txt!r} touches {what}"
    o = pcbnew.SHAPE_POLY_SET(ps)
    o.BooleanSubtract(grown(body, -0.3))
    assert area_mm2(o) < 1e-4, f"label {txt!r} is off the board"

# ---- nothing may lie outside the outline on any manufactured layer --------------------------------
MADE = [pcbnew.F_Cu, B_Cu, pcbnew.F_SilkS, B_SilkS, pcbnew.F_Mask, pcbnew.B_Mask, pcbnew.F_Paste, pcbnew.B_Paste]
_bb = body.BBox()
_bb.Inflate(FromMM(0.05))
for it in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()] + \
        [p for fp in board.GetFootprints() for p in fp.Pads()] + list(board.Tracks()):
    lays = [L for L in MADE if it.IsOnLayer(L)]
    if lays and it.GetClass() != "PCB_FIELD":
        bb = it.GetBoundingBox()
        assert _bb.Contains(bb.GetOrigin()) and _bb.Contains(bb.GetEnd()), f"{it.GetClass()} on {board.GetLayerName(lays[0])} lies outside the board outline"

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
