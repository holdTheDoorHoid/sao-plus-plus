#!/usr/bin/env python3
"""Rebuild covid-test.kicad_pcb from davedarko's 2022 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/covid-test/hardware/build_board.py

What it does
  - loads original/KiCad/drawing.kicad_pcb (KiCad 6, the 2022/11 revision) so the front art stays exactly as drawn
  - removes the through-hole header, the 555, the resistors, the capacitor, the two LEDs, the tracks and both copper pours
  - places the SAO++ parts on the back (switch at the top, connector where the header was, 555 and parts beside the
    result window, coin cell over the lower half) and routes them on the back copper
  - rebuilds the back copper as GND, cleared around the new pads and tracks and behind the two LEDs
  - rebuilds the front copper exactly as the maker's pour (window and sample well left bare), now tied to GND
  - moves the maker's back-side credits, which the switch, connector and cell would cover, to blank spots on the front,
    unchanged in wording and size

Coordinates are millimetres in KiCad's front view (x grows right, y grows down); the board is centred on (0, 0).
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
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         bbox_mm, add_filled, pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "covid-test"
LOCAL = load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "KiCad", "drawing.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

CLEAR = 0.25        # copper-to-copper gap cut into the GND copper
TRACK = 0.25
THIN = 0.20         # where a track passes between two pads
EDGE = 0.55         # GND copper stops this far short of the board edge (panel mouse bites reach 0.25 mm in)
WINDOW = 1.6        # radius kept free of back copper behind each LED (house rule)

# ---- placement (centre x, y) ------------------------------------------------------------------
SW = (0.0, -22.65)          # top edge, knob up; the knob ends 0.75 mm past the edge
CONN = (0.0, -14.1)         # where the maker's header was (-13.48), 0.6 mm higher to clear the switch
LED = {"D1": (0.0, -5.5), "D2": (0.0, -1.5)}     # under the maker's C and T line windows, unchanged
U1C = (-5.05, -2.65)        # 555 left of the result window, turned so its pins run across the board
C1C = (-5.95, -7.17)        # timing capacitor above the 555, between pin 1 (GND) and pin 2 (TRIG)
R1C = (-6.28, 1.78)         # RA below the 555, between pin 8 (VCC) and pin 7 (DIS)
R2C = (-6.28, 3.24)         # RB below RA; the corner beside the clip's open side is the only room left
R3C = (3.2, -6.0)           # control-line LED resistor, right of D1
R4C = (3.2, -2.6)           # test-line LED resistor, right of D2
C2C = (4.9, -6.0)           # supply decoupling
BAT = (0.0, 13.3)           # cell centred across the board, clip pads 0.3 mm inside the bottom edge
BAT_OPEN = (-1.0, 0.0)      # open side to the left (front view): cell slides in from the left, the clip's closed end is on the right
VIAS = []                   # tented GND vias to the front copper (added below)
VIA_AT = [(-6.35, -2.65), (6.4, 1.2)]   # see "front copper" below

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
_tmp = os.path.join(tempfile.mkdtemp(), "drawing.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the maker's 16 x 50 mm rounded rectangle, as one polygon (tools/panelize.py needs that) ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
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
FP["SW1"] = place("SW1", SW, ("1", (SW[0] - 3.0, SW[1] + 1.43)))                    # knob toward the top edge
FP["J1"] = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))                # VCC top left in front view, key up
for ref, (x, y) in LED.items():
    FP[ref] = place(ref, (x, y), ("2", (x + 1.55, y)))                               # anode to the right
FP["U1"] = place("U1", U1C, ("1", (U1C[0] - 1.905, U1C[1] - 2.475)))               # pin 1 top-left; pins 1-4 along the top row
FP["C1"] = place("C1", C1C, ("1", (C1C[0] - 0.775, C1C[1])))                        # GND pad left, over pin 1
FP["R1"] = place("R1", R1C, ("1", (R1C[0] - 0.825, R1C[1])))                        # VLOAD pad left, under pin 8
FP["R2"] = place("R2", R2C, ("1", (R2C[0] - 0.825, R2C[1])))                        # TIM pad left, DIS pad right (under R1's DIS pad)
FP["R3"] = place("R3", R3C, ("1", (R3C[0], R3C[1] - 0.825)))                        # VLOAD at the top
FP["R4"] = place("R4", R4C, ("1", (R4C[0], R4C[1] - 0.825)))                        # OUT at the top
FP["C2"] = place("C2", C2C, ("1", (C2C[0], C2C[1] - 0.775)))                        # VLOAD at the top
u = {n: padpos(FP["U1"], n) for n in "12345678"}
assert abs(u["4"][0] - (U1C[0] + 1.905)) < 0.01 and abs(u["4"][1] - u["1"][1]) < 0.01, u
assert abs(u["8"][0] - u["1"][0]) < 0.01 and u["8"][1] > U1C[1], u

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
# KiCad 10 calls the clip's courtyard (circle + rectangle) "malformed" at exact right angles; 0.1 degree off is accepted
bat.SetOrientationDegrees(_rot - 0.1)
link(bat, "BT1")
bat.SetDuplicatePadNumbersAreJumpers(True)               # the clip joins its two "+" pads; only the top one is routed
for it in bat.GraphicalItems():                          # its silk arrow and "+" would land off the board: fab layer only
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
_bb = None
for g in bat.GraphicalItems():
    if g.GetLayer() == pcbnew.B_Fab and g.GetClass() == "PCB_SHAPE" and g.GetShape() in (pcbnew.SHAPE_T_RECT, pcbnew.SHAPE_T_POLY):
        _bb = g.GetBoundingBox()
print("clip body (fab) x %.2f..%.2f, y %.2f..%.2f" % (ToMM(_bb.GetLeft()), ToMM(_bb.GetRight()), ToMM(_bb.GetTop()), ToMM(_bb.GetBottom())))
print("clip pads", _pads)

NEW = set(PARTS)
for fp in board.GetFootprints():        # the maker's art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new pad must sit on the board, >= 0.25 mm from the edge
_edge25 = grown(body, -0.25)
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                off = pcbnew.SHAPE_POLY_SET()
                add_circle(off, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.25)
            else:
                off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_edge25)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

for ref in sorted(FP):
    fp = FP[ref]
    print(ref, "at", mm(fp.GetPosition()), "rot", round(fp.GetOrientationDegrees(), 1),
          {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber()})

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


sw = {n: padpos(FP["SW1"], n) for n in "134"}
j1 = padpos(FP["J1"], "1")
r = {ref: {n: padpos(FP[ref], n) for n in "12"} for ref in ("R1", "R2", "R3", "R4", "C1", "C2")}
bt_top = min(_pads, key=lambda p: p[1])
EDGE_X = 7.58                                            # the two edge tracks: 0.3 mm from the board edge

# badge 3.3 V: switch pin 1 -> connector pin 1
route("VSAO", [sw["1"], (sw["1"][0], -20.2), (j1[0], -19.74), j1])

# switched supply. From switch pin 3 down between the connector's pin columns, then
#  - west along the gap between the connector's two pin rows and down the left edge to RA and pin 8 (VCC)
#  - from the left edge across above the timing capacitor to pin 4 (RESET)
#  - on down to the bus above the result window and east to R3 and C2
CORR = -14.6                                             # between the connector's pin rows (pads end at -15.3 and -12.9)
BUS = -8.05                                              # above the C window (it starts at -7.1), below the connector pads (-8.5)
X127 = 1.27
route("VLOAD", [sw["3"], (X127, -20.2), (X127, CORR)])
route("VLOAD", [(X127, CORR), (-EDGE_X + 0.4, CORR), (-EDGE_X, CORR + 0.4), (-EDGE_X, r["R1"]["1"][1]), r["R1"]["1"]], width=THIN)
route("VLOAD", [u["8"], (u["8"][0], r["R1"]["1"][1])])
route("VLOAD", [(-EDGE_X, BUS), (u["4"][0], BUS), u["4"]], width=THIN)
route("VLOAD", [(X127, CORR), (X127, BUS), (r["C2"]["1"][0], BUS), r["C2"]["1"]])
route("VLOAD", [(r["R3"]["1"][0], BUS), r["R3"]["1"]])

# coin cell +: switch pin 4 -> right edge -> top clip pad
route("VBAT", [sw["4"], (sw["4"][0], -20.1), (EDGE_X - 0.4, -20.1), (EDGE_X, -19.7), (EDGE_X, bt_top[1] - 0.4),
               (EDGE_X - 0.4, bt_top[1]), bt_top], width=0.3)

# timing: C1 -> pin 2 (TRIG); pin 2 -> under the chip -> pin 6 (THR); pin 6 -> round RA and RB -> RB
route("TIM", [r["C1"]["2"], (r["C1"]["2"][0], -6.62), (u["2"][0], -6.2), u["2"]], width=THIN)
route("TIM", [u["2"], (u["2"][0], -4.0), (u["6"][0], -1.6), u["6"]], width=THIN)
TIMX = -4.55
TIMY = 4.05
route("TIM", [u["6"], (u["6"][0], 0.9), (TIMX, 1.2), (TIMX, TIMY), (r["R2"]["1"][0], TIMY), r["R2"]["1"]], width=THIN)
# discharge: pin 7 -> RA -> RB
route("DIS", [u["7"], (u["7"][0], 0.95), (r["R1"]["2"][0], 1.3), r["R1"]["2"]], width=THIN)
route("DIS", [r["R1"]["2"], r["R2"]["2"]], width=THIN)
route("GND", [u["1"], r["C1"]["1"]], width=THIN)
# output: pin 3 -> under the chip -> out between pins 4 and 5 -> between the two LED windows -> R4
OUTY = -3.5
route("OUT", [u["3"], (u["3"][0], OUTY), (r["R4"]["1"][0], OUTY), r["R4"]["1"]], width=THIN)
# LED anodes: each resistor's lower pad -> across to the anode pad, ending inside the pad outside the window
d1a, d2a = padpos(FP["D1"], "2"), padpos(FP["D2"], "2")
route("LED1_A", [r["R3"]["2"], (d1a[0] + 0.35, r["R3"]["2"][1])])
route("LED2_A", [r["R4"]["2"], (d2a[0] + 0.35, r["R4"]["2"][1])])


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
for pos in VIA_AT:
    add_circle(gnd_pads, P(*pos), 0.3)
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

# ---- front copper: the maker's pour (window and sample well bare), tied to GND through tented vias ----
front = grown(body, -0.508)                              # the maker's pour stopped 0.508 mm from the edge
front.BooleanSubtract(poly([(-1.25, -8.5), (1.25, -8.5), (1.25, 1.5), (-1.25, 1.5)]))      # result window
front.BooleanSubtract(poly([(-1.6, 12.2), (1.6, 12.2), (1.6, 15.3), (-1.6, 15.3)]))        # sample well
pegs = pcbnew.SHAPE_POLY_SET()
for pad in FP["SW1"].Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
front.BooleanSubtract(pegs)
front.Simplify()


def add_via(pos):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*pos))
    v.SetDrill(FromMM(0.3))
    v.SetWidth(FromMM(0.6))
    v.SetNet(nets["GND"])
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append(pos)


# The timing capacitor's GND pad and the 555's pin 1 sit in a pocket closed off by the supply (left edge, above) and the
# timing net (right, below): one tented via under the chip body joins them to the front copper, which is GND, and a
# second one right of the test-line resistor joins the front copper to the rest of the back GND.
for _v in VIA_AT:
    add_via(_v)
add_filled(board, front, F_Cu, nets["GND"] if VIAS else None)
print("GND vias:", VIAS)

# ---- the maker's back-side credits: the switch, connector and cell would cover them; same words and size, on the front ----
# target box (x0, y0, x1, y1) on the front for each text, and its angle there
MOVES = {"2022/11": ((4.85, -14.3, 7.65, -3.56), 90),            # its old spot is where the switch's two peg holes go: blank strip right of the window
         "https://hackaday.io/project/187615": ((-7.88, -8.01, -6.52, 14.7), 90),   # same strip, front side, reads upward
         "@davedarko@chaos.social": ((-7.89, 16.99, 7.89, 18.35), 0)}   # its old line would touch "COVID-19Ag"
for d in board.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == B_SilkS and d.GetText() in MOVES:
        (x0, y0, x1, y1), ang = MOVES[d.GetText()]
        w0, h0 = d.GetBoundingBox().GetWidth(), d.GetBoundingBox().GetHeight()
        d.SetLayer(F_SilkS)
        d.SetMirrored(False)
        d.SetTextAngleDegrees(ang)
        bb = d.GetBoundingBox()
        assert abs(bb.GetWidth() * bb.GetHeight() - w0 * h0) < 1e-3 * w0 * h0 + 1, "text size changed"
        d.Move(VECTOR2I(FromMM((x0 + x1) / 2) - bb.GetCenter().x, FromMM((y0 + y1) / 2) - bb.GetCenter().y))
        bb = d.GetBoundingBox()
        print("front text %-36s x %.2f..%.2f y %.2f..%.2f" % (d.GetText(), ToMM(bb.GetLeft()), ToMM(bb.GetRight()), ToMM(bb.GetTop()), ToMM(bb.GetBottom())))
logo = [fp for fp in board.GetFootprints() if fp.GetFPID().GetUniStringLibItemName() == "davedarko_logo_silk_ext"][0]
logo.Flip(logo.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
logo.SetOrientationDegrees(0)
_lb = logo.GetBoundingBox(False)
logo.Move(VECTOR2I(-(_lb.GetLeft() + _lb.GetRight()) // 2, FromMM(24.55) - _lb.GetBottom()))   # centred, bottom of the front
_lb = logo.GetBoundingBox(False)
print("logo now x %.2f..%.2f y %.2f..%.2f" % (ToMM(_lb.GetLeft()), ToMM(_lb.GetRight()), ToMM(_lb.GetTop()), ToMM(_lb.GetBottom())))

# ---- back silkscreen labels -----------------------------------------------------------------------
LABELS = [("SAO", -6.85, -22.2, 0.8, 0), ("BAT", 6.85, -22.2, 0.8, 0),
          ("CR2032", -5.75, 22.75, 0.8, 0), ("+ UP", -5.75, 23.85, 0.8, 0),
          ("SAO++ rA", 6.4, -3.0, 0.8, 90)]
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
