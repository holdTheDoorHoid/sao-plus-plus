#!/usr/bin/env python3
"""Rebuild covid-test.kicad_pcb from davedarko's 2022 original plus the SAO++ changes (rev B: scaled up).

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/covid-test/hardware/build_board.py

What it does
  - loads original/KiCad/drawing.kicad_pcb (KiCad 6, the 2022/11 revision)
  - removes the through-hole header, the 555, the resistors, the capacitor, the two LEDs, the tracks, both copper pours
    and the maker's back assembly note (it names his old parts and would sit under the cell)
  - scales the outline and ALL the remaining art (front art, mask windows, the maker's back credits and logo) by SCALE
    about the board centre, so the cassette keeps its proportions; parts keep their real size
  - places the SAO++ parts on the back around the maker's credits, which stay where he put them (scaled)
  - routes everything on the back copper only, no vias, and fills the rest of the back with GND
  - rebuilds the front copper as the maker's pour (window and sample well left bare), unconnected as he had it

Coordinates are millimetres in KiCad's front view (x grows right, y grows down); the board is centred on (0, 0).
Part positions below are laid out for SCALE = 1.48; the assertions stop the build if a change of scale breaks them.
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

SCALE = 1.48        # 16 x 50 mm -> 23.68 x 74.0 mm. The smallest factor at which the cell sits inside the outline without
                    # covering the maker's back URL (see README "Why 1.48")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         bbox_mm, add_filled, pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "covid-test"
LOCAL = load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "KiCad", "drawing.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

S = SCALE
W, L = 8.0 * S, 25.0 * S    # half width, half length
CLEAR = 0.25        # copper-to-copper gap cut into the GND copper
TRACK = 0.25
THIN = 0.20
EDGE = 0.55         # GND copper stops this far short of the board edge (panel mouse bites reach 0.25 mm in)
WINDOW = 1.6        # radius kept free of back copper behind each LED (house rule; not scaled)

# ---- placement (centre x, y) ------------------------------------------------------------------
SW = (W - 2.35, 4.4)        # right edge, knob out to the right; between the maker's logo and the cell clip
CONN = (0.0, -13.48 * S)    # where the maker's header was, scaled with the art
LED = {"D1": (0.0, -5.5 * S), "D2": (0.0, -1.5 * S)}     # under the maker's C and T line windows (art-tied: scaled)
U1C = (-1.4, 5.8)           # 555 below the result window, pins in two columns
R1C = (-7.4, 5.8)           # RA, left of the 555
R2C = (-5.9, 5.8)           # RB, between RA and the 555
C1C = (3.1, 4.53)           # timing capacitor right of pins 1 and 2
C2C = (-6.4, 2.75)          # supply decoupling, on the supply track left of pin 8
R3C = (-3.875, LED["D1"][1])   # control-line LED resistor, left of D1
R4C = (-3.875, LED["D2"][1])   # test-line LED resistor, left of D2
BAT = (0.45, 23.4)          # cell clip, lengthwise; the closed end toward the right edge
BAT_OPEN = (-1.0, 0.0)      # open side to the left (front view): the cell slides in from the left

# ---- strip the 2022 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone"))
_gone = []
for a_, b_ in blocks(_txt, "footprint"):
    m = re.search(r'\(fp_text reference "([^"]+)"', _txt[a_:b_])
    if m and m.group(1) in ("J1", "U1", "R1", "R2", "R3", "R4", "C1", "D1", "D2"):
        _cut.append((a_, b_))
        _gone.append(m.group(1))
assert sorted(_gone) == ["C1", "D1", "D2", "J1", "R1", "R2", "R3", "R4", "U1"], _gone
_n = 0
for a_, b_ in blocks(_txt, "gr_rect"):
    s = _txt[a_:b_]
    if '(layer "B.Mask")' in s and "12.446" not in s:   # the mask windows behind the old LEDs (the new LED footprint has its own)
        _cut.append((a_, b_))
        _n += 1
assert _n == 2, _n
for a_, b_ in blocks(_txt, "gr_text"):
    if "C1+R2 main blink parts" in _txt[a_:b_]:        # the maker's assembly note: it names the old parts and sits under the cell
        _cut.append((a_, b_))
        _n += 1
assert _n == 3
_edges = [(a_, b_) for op in ("gr_line", "gr_arc") for a_, b_ in blocks(_txt, op) if '(layer "Edge.Cuts")' in _txt[a_:b_]]
assert len(_edges) == 8, len(_edges)
_cut += _edges
_txt = cut_blocks(_txt, _cut)

# ---- scale every remaining art item (footprints, mask rectangles, texts) about the board centre -----
_NUM = r"(-?[0-9.]+)"


def _f(v):
    return ("%.6f" % (float(v) * S)).rstrip("0").rstrip(".")


def _scale_block(t):
    t = re.sub(r"\((xy|start|end|mid|center|size) " + _NUM + " " + _NUM + r"\)",
               lambda m: "(%s %s %s)" % (m.group(1), _f(m.group(2)), _f(m.group(3))), t)
    t = re.sub(r"\(at " + _NUM + " " + _NUM, lambda m: "(at %s %s" % (_f(m.group(1)), _f(m.group(2))), t)
    t = re.sub(r"\((thickness|width) " + _NUM + r"\)", lambda m: "(%s %s)" % (m.group(1), _f(m.group(2))), t)
    return t


_spans = sorted([sp for op in ("footprint", "gr_rect", "gr_text") for sp in blocks(_txt, op)], reverse=True)
_nscaled = 0
for a_, b_ in _spans:
    _txt = _txt[:a_] + _scale_block(_txt[a_:b_]) + _txt[b_:]
    _nscaled += 1
assert _nscaled == 3 + 4 + 6, _nscaled          # stopmask, shading, logo; 4 mask rectangles; 6 texts
_tmp = os.path.join(tempfile.mkdtemp(), "drawing.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the maker's rounded rectangle, scaled, as one polygon (tools/panelize.py needs that) ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
OUTER = [(x * S, y * S) for x, y in _ol["outer"]]
body = poly(OUTER)
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(OUTER))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)

# the maker's back credits after scaling: parts must not cover them
CREDITS = {}
for d in board.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == B_SilkS:
        bb = d.GetBoundingBox()
        CREDITS[d.GetText()] = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
for fp in board.GetFootprints():
    if fp.GetFPID().GetUniStringLibItemName() == "davedarko_logo_silk_ext":
        bb = fp.GetBoundingBox(False)
        CREDITS["logo"] = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
assert len(CREDITS) == 4, CREDITS
for k, v in CREDITS.items():
    print("credit %-36s x %.2f..%.2f y %.2f..%.2f" % (k, v[0], v[2], v[1], v[3]))

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
    lib, name = fpid.split(":")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
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


def load(ref, pos):
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name} in {LIBS[lib]}"
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


FP = {}
FP["SW1"] = place("SW1", SW, ("1", (SW[0] - 1.43, SW[1] - 3.0)))                    # knob to the right, pin 1 (SAO) at the top
FP["J1"] = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))                # VCC top left in front view, key up
for ref, (x, y) in LED.items():
    FP[ref] = place(ref, (x, y), ("2", (x - 1.55, y)))                               # anode to the left
FP["U1"] = place("U1", U1C, ("1", (U1C[0] + 2.475, U1C[1] - 1.905)))               # pin 1 top right, pins 1-4 down the right
FP["R1"] = place("R1", R1C, ("1", (R1C[0], R1C[1] + 0.825)))                        # VLOAD pad at the bottom
FP["R2"] = place("R2", R2C, ("1", (R2C[0], R2C[1] + 0.825)))                        # TIM pad at the bottom, DIS at the top
FP["C1"] = place("C1", C1C, ("1", (C1C[0], C1C[1] - 0.775)))                        # GND pad at the top (beside pin 1)
FP["C2"] = place("C2", C2C, ("1", (C2C[0], C2C[1] + 0.775)))                        # VLOAD pad at the bottom, on the supply
FP["R3"] = place("R3", R3C, ("1", (R3C[0] - 0.825, R3C[1])))                        # VLOAD pad left
FP["R4"] = place("R4", R4C, ("1", (R4C[0] - 0.825, R4C[1])))                        # OUT pad left
u = {n: padpos(FP["U1"], n) for n in "12345678"}
assert abs(u["4"][0] - u["1"][0]) < 0.01 and u["4"][1] > u["1"][1], u          # pins 1-4 down the right column
assert abs(u["8"][1] - u["1"][1]) < 0.01 and u["8"][0] < u["1"][0], u          # pin 8 top left

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the open side faces
bat = load("BT1", BAT)
FP["BT1"] = bat


def _open_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(BAT[1] - ToMM(c.y), BAT[0] - ToMM(c.x)))


for _rot in (0, 90, 180, 270):
    if abs((_open_dir(_rot) - math.degrees(math.atan2(BAT_OPEN[1], BAT_OPEN[0])) + 180) % 360 - 180) < 1:
        break
else:
    raise AssertionError("no right-angle rotation turns the clip's open side to the left")
_pads = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
assert abs(_pads[0][0] - BAT[0]) < 0.01 and abs(_pads[1][0] - BAT[0]) < 0.01, "clip pads are not along the board"
_bb = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
CLIP_BODY = (ToMM(_bb.GetLeft()) + 0.05, ToMM(_bb.GetTop()) + 0.05, ToMM(_bb.GetRight()) - 0.05, ToMM(_bb.GetBottom()) - 0.05)   # less the 0.1 mm line
# KiCad 10 calls the clip's courtyard (circle + rectangle) "malformed" at exact right angles; 0.1 degree off is accepted
bat.SetOrientationDegrees(_rot - 0.1)
link(bat, "BT1")
bat.SetDuplicatePadNumbersAreJumpers(True)               # the clip joins its two "+" pads; only the top one is routed
for it in bat.GraphicalItems():                          # its silk arrow and "+" land on the maker's credits: fab layer only
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
print("clip body (fab) x %.2f..%.2f, y %.2f..%.2f" % (CLIP_BODY[0], CLIP_BODY[2], CLIP_BODY[1], CLIP_BODY[3]))
print("clip pads", _pads)

NEW = set(PARTS)
for fp in board.GetFootprints():        # the maker's art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# ---- checks: every new pad >= 0.25 mm inside the edge (clip pads >= 1 mm), the clip body and the cell on the board,
#      and no part (courtyard) over the maker's credits; the cell clear of the credits too
_edge25 = grown(body, -0.25)
_edge1 = grown(body, -1.0)
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                off = pcbnew.SHAPE_POLY_SET()
                add_circle(off, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.25)
            else:
                off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_edge1 if fp.GetReference() == "BT1" else _edge25)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is too close to the board edge"
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_clip = poly([(CLIP_BODY[0], CLIP_BODY[1]), (CLIP_BODY[2], CLIP_BODY[1]), (CLIP_BODY[2], CLIP_BODY[3]), (CLIP_BODY[0], CLIP_BODY[3])])
for name, shape in (("cell", _cell), ("clip body", _clip)):
    o = pcbnew.SHAPE_POLY_SET(shape)
    o.BooleanSubtract(_edge25)
    assert o.OutlineCount() == 0, f"the {name} is not 0.25 mm inside the outline"
for cname, (x0, y0, x1, y1) in CREDITS.items():
    box = poly([(x0 - 0.2, y0 - 0.2), (x1 + 0.2, y0 - 0.2), (x1 + 0.2, y1 + 0.2), (x0 - 0.2, y1 + 0.2)])
    for fp in board.GetFootprints():
        if fp.GetReference() in NEW:
            fp.BuildCourtyardCaches()
            cy = fp.GetCourtyard(pcbnew.B_CrtYd)
            o = pcbnew.SHAPE_POLY_SET(cy)
            o.BooleanIntersection(box)
            assert o.OutlineCount() == 0, f"{fp.GetReference()} sits on the maker's credit '{cname}'"
    o = pcbnew.SHAPE_POLY_SET(_cell)
    o.BooleanIntersection(box)
    assert o.OutlineCount() == 0, f"the cell covers the maker's credit '{cname}'"

for ref in sorted(FP):
    fp = FP[ref]
    print(ref, "at", mm(fp.GetPosition()), "rot", round(fp.GetOrientationDegrees(), 1),
          {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber()})

if os.environ.get("PLACE_ONLY"):
    pcbnew.SaveBoard(OUT, board)
    sys.exit(0)


# ---- routing (back copper only, no vias) --------------------------------------------------------
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


sw = {n: padpos(FP["SW1"], n) for n in "134"}
j1 = padpos(FP["J1"], "1")
r = {ref: {n: padpos(FP[ref], n) for n in "12"} for ref in ("R1", "R2", "R3", "R4", "C1", "C2")}
bt_top = min(_pads, key=lambda p: p[1])
d1a, d2a = padpos(FP["D1"], "2"), padpos(FP["D2"], "2")

# badge 3.3 V: switch pin 1 -> up the right of the window -> between the connector's two pin rows -> pin 1
VSAO_X = 5.0
route("VSAO", [sw["1"], (VSAO_X, sw["1"][1]), (VSAO_X, CONN[1]), (j1[0], CONN[1]), j1])

# switched supply (VLOAD): switch pin 3 -> down and under the 555 to pin 4 (from below) -> on round the left of the
# chip to pin 8 (this loop encloses only pins 5-7 and the two timing resistors, so no GND is boxed in) -> up the left
# to R3 beside the control-line LED
SUP_X = 6.2
LOOP_Y = 9.0
LOOP_X = -8.4
route("VLOAD", [sw["3"], (SUP_X, sw["3"][1]), (SUP_X, LOOP_Y), (u["4"][0] + 0.4, LOOP_Y), (u["4"][0] + 0.4, u["4"][1])])
route("VLOAD", [(u["4"][0] + 0.4, LOOP_Y), (LOOP_X, LOOP_Y), (LOOP_X, u["8"][1]), (u["8"][0], u["8"][1])])
route("VLOAD", [r["R1"]["1"], (LOOP_X, r["R1"]["1"][1])], width=THIN)
route("VLOAD", [(LOOP_X, u["8"][1]), (LOOP_X, r["R3"]["1"][1]), r["R3"]["1"]])
route("VLOAD", [r["C2"]["1"], (r["C2"]["1"][0], u["8"][1])])

# coin cell +: switch pin 4 -> down, under the supply loop -> top clip pad
VBAT_X = 7.0
VBAT_Y = 10.6
route("VBAT", [sw["4"], (VBAT_X, sw["4"][1]), (VBAT_X, VBAT_Y), (2.5, VBAT_Y), (2.5, bt_top[1])], width=0.3)

# timing: pin 2 <-> pin 6 under the chip; pin 6 -> RB; pin 7 -> RB and RA; pin 2 -> C1
route("TIM", [(u["2"][0] - 0.675, u["2"][1]), (u["6"][0] + 0.675, u["6"][1])], width=THIN)     # inner pad ends, under the body
route("TIM", [u["6"], r["R2"]["1"]], width=THIN)
route("DIS", [u["7"], r["R2"]["2"]], width=THIN)
route("DIS", [r["R2"]["2"], r["R1"]["2"]], width=THIN)
route("TIM", [u["2"], r["C1"]["2"]], width=THIN)
route("GND", [u["1"], r["C1"]["1"]], width=THIN)

# output: pin 3 -> right, up past C1, left above the chip (below the result window) -> up to R4
OUT_X = 4.1
OUT_Y = 2.6
OUT_UP = r["R4"]["1"][0]
route("OUT", [u["3"], (OUT_X, u["3"][1]), (OUT_X, OUT_Y), (OUT_UP, OUT_Y), r["R4"]["1"]], width=THIN)
# LED anodes: each resistor's right pad -> across to the anode pad, ending inside the pad outside the window
route("LED1_A", [r["R3"]["2"], (d1a[0] - 0.35, r["R3"]["2"][1])])
route("LED2_A", [r["R4"]["2"], (d2a[0] - 0.35, r["R4"]["2"][1])])


# ---- GND copper on the back: the whole board, cleared around everything that is not GND -----------
def is_gnd(item):
    return item.GetNetname() == "GND"


back = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.05)
        elif pad.IsOnLayer(B_Cu) and not is_gnd(pad):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t, clear in TRACKS:
    if not is_gnd(t):
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
for x, y in LED.values():
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
back.BooleanSubtract(cut)
back.Simplify()
# drop slivers the clearances leave (thinner than 0.2 mm) so DRC sees no hair-thin copper
back.Inflate(-FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
back.Inflate(FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
back.BooleanIntersection(inner)
back.BooleanSubtract(cut)
back.Simplify()

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if is_gnd(pad):
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
pieces = []
for i in range(back.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(back.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    pieces.append((piece, area_mm2(both) > 0.01))
    if not pieces[-1][1] and area_mm2(piece) < 2.0:
        continue                                         # crumbs left between tracks: not worth keeping as art
    add_filled(board, piece, B_Cu, nets["GND"] if pieces[-1][1] else None)
print("back copper pieces:", [(round(area_mm2(p), 1), [round(v, 1) for v in bbox_mm(p)], g) for p, g in pieces])

# ---- front copper: the maker's pour (window and sample well bare), unconnected as he had it ----
front = grown(body, -0.508)                              # the maker's pour stopped 0.508 mm from the edge
front.BooleanSubtract(poly([(-1.25 * S, -8.5 * S), (1.25 * S, -8.5 * S), (1.25 * S, 1.5 * S), (-1.25 * S, 1.5 * S)]))   # result window
front.BooleanSubtract(poly([(-1.6 * S, 12.2 * S), (1.6 * S, 12.2 * S), (1.6 * S, 15.3 * S), (-1.6 * S, 15.3 * S)]))     # sample well
pegs = pcbnew.SHAPE_POLY_SET()
for pad in FP["SW1"].Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
front.BooleanSubtract(pegs)
front.Simplify()
add_filled(board, front, F_Cu, None)

# ---- back silkscreen labels (the maker's credits are already there, scaled, where he put them) -------
LABELS = [("SAO", SW[0], SW[1] - 6.4, 0.8, 0), ("BAT", SW[0], SW[1] + 6.4, 0.8, 0),
          ("CR2032", -6.3, 33.9, 0.8, 0), ("+ UP", -6.3, 35.0, 0.8, 0),
          ("SAO++ rB", 5.6, 35.9, 0.8, 0)]
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
