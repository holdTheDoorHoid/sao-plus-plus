#!/usr/bin/env python3
"""Rebuild frida.kicad_pcb from the 2018 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/frida/hardware/build_board.py

What it does
  - loads original/frida.kicad_pcb (KiCad 5) so the front art stays exactly as drawn
  - removes the 4-pin through-hole header, the five 3 mm through-hole LEDs, the one shared axial resistor, the old
    tracks, the old ground pour and the silkscreen marks that only labelled those parts (+, -, VCC, GND, pin-1 dot)
  - places the SAO++ parts on the back and routes them (single layer, back copper, no vias)
  - rebuilds the back copper (the 2018 ground pour) as the GND net, cleared around the new pads and tracks
  - opens a small bare window (no copper, no solder mask, both sides) in the middle of each flower for the light
  - moves the four-line "Thanks To" credit up above the FRIDA lettering, because the coin cell needs its old spot
    (see the note at BAT below: there is no place on this narrow head where the cell fits without that)

How the art is stored (svg2mod, 2018): the front is one footprint "frida" holding one front copper polygon (the gold
rim and earrings), one front mask polygon of the same shape (so the rim is bare gold), the white face on the front
silkscreen, and five silkscreen rings (32 short lines each) round the flowers. The back is one footprint "fridaback"
holding only back silkscreen: the words FRIDA / SAO / DEF CON 26. The thanks are four plain KiCad texts. There is no
copper art on the back: the back copper was a plain ground pour, and no art was drawn outside the board outline.

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
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         footprint_polys, bbox_mm, add_filled, pad_poly, stray_frames)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "frida"
SRC = os.path.join(HERE, "..", "original", "frida.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
PANEL = os.path.join(HERE, "..", "production", "panel.json")

CLEAR = 0.30        # copper-to-copper gap cut into the GND pour
TRACK = 0.40
THIN = 0.25         # the battery track that runs under the switch body
EDGE = 0.55         # back copper stops this far short of the board edge (panel mouse bites reach 0.25 mm in)
FRONT_EDGE = 0.28   # the front rim art is only trimmed this far (as on Mad Cat), except at the panel tabs
WINDOW = 1.6        # radius kept free of back copper behind each LED so light gets into the board
BARE = 1.0          # radius of the bare window (no copper, no solder mask, either side) in each flower

# ---- placement (centre x, y) ------------------------------------------------------------------
# The back has, top to bottom: five flower LEDs in the hair, FRIDA / SAO / DEF CON 26 (the maker's SVG lettering,
# y 78.8-97.7), the four-line thanks (y 105.8-113.2) and the 2018 header (y 122-127). The head is 50 mm wide at most
# and 33-37 mm wide below the lettering, so the 24 x 17 mm cell clip cannot sit anywhere without covering lettering
# or a flower. Least-bad choice (to be confirmed by the owner): the connector goes straight under DEF CON 26, the
# cell under it at the chin (its open side faces the bottom edge, so it slides in from below), and the thanks text,
# unchanged, moves up into the gap between the flowers and FRIDA.
CONN = (70.485, 102.75)     # same left-right position as the 2018 header; top pads 0.3 mm under the DEF CON 26 lettering
BAT = (70.485, 120.15)      # cell flush with the chin; clip's closed end 0.8 mm below the connector's lower pads
BAT_CLOSED = (0.0, -1.0)    # the clip's closed end points up (toward the connector); the open side faces the chin
SW = (47.55, 75.00)         # left side of the hair, the straightest 12 mm of edge; knob points left, ~0.9 mm past the edge
THANKS_DY = -35.56          # the credit block moves up by this much, from under DEF CON 26 to above FRIDA
# LEDs: the 2018 centres (midpoint of each LED's two holes), except D1. Last number: +1 = anode pad right of centre,
# -1 = left, 0 = LED turned upright with its anode below. D1's silkscreen ring was drawn 0.69 mm left of its 2018 LED,
# so it is centred on the ring instead (otherwise the bare window would cut through the ring), and turned upright to
# keep its pads clear of the notch in the hair just left of it.
LEDS = {
    "D1": (75.256, 57.431, 0),
    "D2": (61.722, 66.294, -1),
    "D3": (84.963, 61.214, -1),
    "D4": (72.644, 67.310, -1),
    "D5": (82.804, 71.628, -1),
}
RING = {"D1": (75.256, 57.431), "D2": (61.775, 66.301), "D3": (84.883, 61.342), "D4": (72.603, 67.352), "D5": (82.780, 71.611)}
RING_IN = 1.488 - 0.282 / 2  # inner edge of the maker's silkscreen rings
RES = {                     # each resistor's centre; pad 2 faces its LED's anode, pad 1 meets the supply bus
    "R1": (75.256, 61.40), "R2": (57.60, 66.294), "R3": (80.90, 61.214), "R4": (68.50, 67.310), "R5": (78.90, 71.628),
}
BUS_Y = 64.00               # the switched supply runs across the hair here, between the upper and lower flowers

# ---- strip the 2018 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "zone")) + list(blocks(_txt, "gr_circle"))
assert len(_cut) == 18 + 1 + 1, len(_cut)          # 18 tracks, the pour, the front pin-1 dot of the old header
_edges = [(a_, b_) for a_, b_ in blocks(_txt, "gr_line") if "(layer Edge.Cuts)" in _txt[a_:b_]]
assert len(_edges) == 364, len(_edges)
_cut += _edges
_marks = [(a_, b_) for a_, b_ in blocks(_txt, "gr_text") if re.match(r"\s*\(gr_text (\+|-|GND|VCC) ", _txt[a_:b_])]
assert len(_marks) == 12, len(_marks)              # + and - beside each old LED, VCC and GND beside the old header
_cut += _marks
_gone = []
for a_, b_ in blocks(_txt, "module"):
    ref = re.search(r"\(fp_text reference (\S+)", _txt[a_:b_]).group(1)
    if ref in ("J1", "R1") or re.fullmatch(r"D[1-5]", ref):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == sorted(["J1", "R1", "D1", "D2", "D3", "D4", "D5"]), _gone
_txt = cut_blocks(_txt, _cut)
# the front copper and front mask art is rebuilt below (switch pegs, panel tabs): read it from the untouched original
_polys = [(a_, b_) for a_, b_ in blocks(_txt, "fp_poly", 4)
          if any(f"(layer {L})" in _txt[b_ - 40:b_] for L in ("F.Cu", "F.Mask"))]
assert len(_polys) == 2, f"expected 1 front copper + 1 front mask art polygon, found {len(_polys)}"
_txt = cut_blocks(_txt, _polys)
assert not stray_frames(_txt, 55), "this board's SVG import was expected to have no page frame"
_tmp = os.path.join(tempfile.mkdtemp(), "frida.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
front = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, F_Cu):
    front.Append(p_)
fmask = pcbnew.SHAPE_POLY_SET()
for p_ in footprint_polys(_orig, pcbnew.F_Mask):
    fmask.Append(p_)
assert front.OutlineCount() == 1 and fmask.OutlineCount() == 1
_pours = [z for z in _orig.Zones() if not z.GetIsRuleArea()]
assert len(_pours) == 1, "expected the single 2018 ground pour on the back"
art = pcbnew.SHAPE_POLY_SET(_pours[0].Outline())   # the back copper was this pour (GND); made solid here
art.Simplify()
front.Simplify()
fmask.Simplify()

board = pcbnew.LoadBoard(_tmp)
TRACKS = []                              # (track, clearance to cut around it)

# ---- outline: the 2018 edge was 364 segments; outline.json is the same path as one closed polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)               # where back copper may be
art.BooleanIntersection(inner)

# ---- the maker's lettering on the back, kept as a no-go area for tracks ---------------------------
LETTERS = footprint_polys(_orig, B_SilkS)
assert len(LETTERS) == 16, len(LETTERS)  # F R I D A / S A O / D E F C O N 2 6 (svg2mod)
lettering = pcbnew.SHAPE_POLY_SET()
for p_ in LETTERS:
    lettering.Append(p_)
lettering.Simplify()
_lb = bbox_mm(lettering)
print("back lettering spans", [round(v, 2) for v in _lb])

# the thanks block moves up, unchanged (same words, font, size, centring)
THANKS = ("Thanks To", "@ANDnXOR", "@mrtwinkletwink", "@UriShaked")
_moved = 0
for d in board.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetText() in THANKS:
        d.Move(P(0, THANKS_DY))
        _moved += 1
        bb = d.GetBoundingBox()
        lettering.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                               (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
assert _moved == 4, _moved
lettering.Simplify()

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
    fp.Reference().SetVisible(False)    # the back is busy; refs live on the fab layer and in the README
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


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view = same corner as the 2018 header
# the connector's own pin-1 bar would print 0.3 mm over the bottom of the O and N of DEF CON 26 (the connector sits
# right under the lettering), so on this board it goes to the fabrication layer; the "1" label below marks pin 1
_bars = [g for g in conn.GraphicalItems() if g.GetLayer() == B_SilkS and g.GetShape() == pcbnew.SHAPE_T_SEGMENT
         and abs(ToMM(g.GetWidth()) - 0.3) < 0.01]
assert len(_bars) == 1, len(_bars)
_bars[0].SetLayer(pcbnew.B_Fab)
sw = place("SW1", SW, ("1", (SW[0] + 1.43, SW[1] + 3.0)))            # pins face inward, pin 1 (SAO) at the lower end, knob to the left
_pegs = sorted(mm(p.GetPosition()) for p in sw.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)
assert all(abs(x - (SW[0] - 0.33)) < 0.01 for x, _ in _pegs), f"switch is not knob-left: pegs at {_pegs}"
led, res = {}, {}
for ref, (x, y, s) in LEDS.items():
    n = ref[1:]
    anode = (x, y + 1.55) if s == 0 else (x + s * 1.55, y)
    led[ref] = place(ref, (x, y), ("2", anode))
    rx, ry = RES["R" + n]
    pad2 = (rx, ry - 0.825) if s == 0 else (rx - s * 0.825, ry)     # pad 2 toward the LED
    res["R" + n] = place("R" + n, (rx, ry), ("2", pad2))

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)             # (rectangles only stay rectangles at right angles, so measure there)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
_pa, _pb = [mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"]
assert abs((_pa[0] - _pb[0]) * BAT_CLOSED[0] + (_pa[1] - _pb[1]) * BAT_CLOSED[1]) < 0.05, "clip pads are not square to the closed end"
_fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
CLIP_TOP = ToMM(_fab.GetTop())                          # the clip's closed end
link(bat, "BT1")
print("battery clip angle", _rot, "closed end at y", round(CLIP_TOP, 2))

NEW = set(PARTS)
for fp in board.GetFootprints():        # the 2018 art lives in footprints with no schematic symbol: mark them board-only
    if fp.GetReference() not in NEW:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# every new part must sit on the board, at least 0.25 mm in
_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                off = pad_poly(pad, B_Cu)
                off.BooleanSubtract(_pad_ok)
                assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# the cell itself (20 mm) must stay inside the outline, and clear of the connector's pads
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.0)
_cell.BooleanSubtract(body)
assert area_mm2(_cell) < 0.01, f"the coin cell hangs over the board edge by {area_mm2(_cell):.2f} mm2"
_j1_low = max(ToMM(p.GetBoundingBox().GetBottom()) for p in conn.Pads())
_j1_top = min(ToMM(p.GetBoundingBox().GetTop()) for p in conn.Pads())
print("gap from connector pads to clip's closed end: %.2f mm" % (CLIP_TOP - _j1_low))
assert CLIP_TOP - _j1_low >= 0.75
# the connector's pads and plastic body, and the cell, must not cover any letter
_cover = pcbnew.SHAPE_POLY_SET()
add_circle(_cover, P(*BAT), 10.0)
for fp in (conn,):
    for g in fp.GraphicalItems():
        if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT:
            bb = g.GetBoundingBox()
            _cover.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                                (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
    for pad in fp.Pads():
        _cover.Append(pad_poly(pad, B_Cu, 0.3))
_cover.Simplify()
_hit = pcbnew.SHAPE_POLY_SET(_cover)
_hit.BooleanIntersection(lettering)
assert area_mm2(_hit) < 0.001, f"connector or cell covers lettering ({area_mm2(_hit):.3f} mm2)"
print("connector top pads end %.2f mm below the lowest letter above them" % (_j1_top - 96.82))


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
assert s4[1] < s3[1] < s1[1], "switch pins should run 4, 3, 2, 1 from top to bottom"

# each LED: resistor pad 2 -> straight across (or up) to the anode pad
for ref in LEDS:
    n = ref[1:]
    route(f"LED{n}_A", [padpos(res["R" + n], "2"), padpos(led[ref], "2")])
rp = {r: padpos(fp, "1") for r, fp in res.items()}       # supply-side pad of each resistor

# switched supply: switch pin 3 -> right, up the left of the hair -> one bus across the hair at BUS_Y,
# with a stub to each resistor (R1 and R3 above the bus, R2, R4 and R5 below it)
route("VLOAD", [s3, (51.0, s3[1]), (51.0, BUS_Y + 2.0), (53.0, BUS_Y), (rp["R3"][0], BUS_Y), rp["R3"]])
for r in ("R1", "R2", "R4", "R5"):
    route("VLOAD", [(rp[r][0], BUS_Y), rp[r]])

# badge 3.3 V: switch pin 1 (lower end) -> down the left side, inside the battery track -> under DEF CON 26 -> J1 pin 1
route("VSAO", [s1, (50.6, s1[1]), (50.6, 84.5), (51.4, 88.0), (52.3, 91.6), (53.3, 95.6), (53.3, 100.0), (j1[0], 100.0)])

# coin cell +: switch pin 4 is at the top end, but the cell is at the bottom and the switched supply leaves from
# pin 3 just below it. On one copper layer the only way past is underneath the switch: a thin track runs from pin 4
# along the knob side of the switch body, between the two peg holes and the edge, and out between the two metal
# tabs at the lower end. Then it follows the left edge, outside the badge-supply track, down to the clip.
route("VBAT", [s4, (s4[0], 71.3), (SW[0] - 1.2, 71.3), (SW[0] - 1.2, 78.7), (SW[0] - 0.33, 79.5), (SW[0] - 0.33, 82.0)], width=THIN, clear=0.25)
bt_l = padpos(bat, "1", pick=lambda p: p[0])            # clip pad on the left (front view)
bt_r = padpos(bat, "1", pick=lambda p: -p[0])
route("VBAT", [(SW[0] - 0.33, 82.0), (SW[0] - 0.33, 84.0), (48.6, 87.5), (49.5, 91.0), (51.3, 95.8), (52.0, 99.0), (52.0, 102.5),
               (53.6, 104.8), (54.3, 107.0), (54.3, 113.0), (57.8, 114.0), (bt_l[0], 116.0), bt_l])
# the clip itself joins its two pads; this link round the closed end (under the clip) makes the board agree without relying on it
_a0 = math.degrees(math.atan2(bt_l[1] - BAT[1], bt_l[0] - BAT[0]))
_r = math.hypot(bt_l[0] - BAT[0], bt_l[1] - BAT[1])
_arc = [(round(BAT[0] + _r * math.cos(math.radians(_a0 + d)), 4), round(BAT[1] + _r * math.sin(math.radians(_a0 + d)), 4)) for d in range(15, 180, 15)]
_mid = _arc[len(_arc) // 2]
assert (_mid[0] - BAT[0]) * BAT_CLOSED[0] + (_mid[1] - BAT[1]) * BAT_CLOSED[1] > 0, "pad link is on the open side of the clip"
route("VBAT", [bt_l] + _arc + [bt_r])

# ---- GND copper: the 2018 pour, cleared around everything that is not GND --------------------------
disc = pcbnew.SHAPE_POLY_SET()
add_circle(disc, P(*BAT), 8.55)                          # solid copper under the cell so the bare cell pad is whole
art.BooleanAdd(disc)
art.BooleanIntersection(inner)

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
for x, y, _s in LEDS.values():                           # light path behind each flower
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
art.BooleanSubtract(cut)
art.Simplify()

# no track may run through the lettering (the maker's SVG words and the moved thanks), or within 0.2 mm of it
_let = grown(lettering, 0.2)
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(_let)
assert area_mm2(_hit) < 0.001, f"a track channel overlaps the lettering by {area_mm2(_hit):.3f} mm2"
# and every track stays as far from the board edge as the ground pour does (no panel tab is near the switch either)
_out = pcbnew.SHAPE_POLY_SET()
for t, _c in TRACKS:
    t.TransformShapeToPolygon(_out, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
_out.BooleanSubtract(grown(body, -EDGE))
assert area_mm2(_out) < 0.001, f"{[[round(v,2) for v in bbox_mm(pcbnew.SHAPE_POLY_SET(_out.Polygon(i)))] for i in range(_out.OutlineCount())]} a track comes within EDGE of the board edge ({area_mm2(_out):.3f} mm2)"

# every separate piece becomes its own shape: pieces touching a GND pad carry the GND net, the rest stay plain copper.
# Thin strips and slivers left between a track and the edge are dropped: they were pour, not drawn art.
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = n_art = n_drop = 0
trimmed = pcbnew.SHAPE_POLY_SET()
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    # trim hair-thin points off the piece's outer edge (where a cut meets the board edge at a shallow angle); only the
    # hole-free outer path is shrunk and regrown, because shrinking a shape with holes opens slits in KiCad 10
    _outer = pcbnew.SHAPE_POLY_SET()
    _outer.AddOutline(art.Outline(i))
    _thin = pcbnew.SHAPE_POLY_SET(_outer)
    _thin.BooleanSubtract(grown(grown(_outer, -0.1), 0.1))
    piece.BooleanSubtract(_thin)
    trimmed.Append(piece)
trimmed.Simplify()
for i in range(trimmed.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(trimmed.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    touches = area_mm2(both) > 0.01
    _outer = pcbnew.SHAPE_POLY_SET()
    _outer.AddOutline(trimmed.Outline(i))
    if not touches and (area_mm2(piece) < 0.5 or area_mm2(grown(grown(_outer, -0.3), 0.3)) < 0.5):
        n_drop += 1                                       # a thin strip between a track and the edge: pour, not art
        continue
    add_filled(board, piece, B_Cu, nets["GND"] if touches else None)
    n_gnd += touches
    n_art += not touches
    if not touches:
        print("  plain copper piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain", n_art, "slivers and thin strips dropped", n_drop)

# ---- front: the 2018 rim and earring art, clear of the switch pegs and pulled back at the panel tabs ----
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
_bite = pcbnew.SHAPE_POLY_SET(front)
_bite.BooleanIntersection(pegs)
print("front rim copper removed round the two switch pegs, mm2:", round(area_mm2(_bite), 3))
tabzone = pcbnew.SHAPE_POLY_SET()
for tab in json.load(open(PANEL))["tabs"]:
    add_circle(tabzone, P(*tab["near"]), 3.2)
tabzone.BooleanSubtract(grown(body, -0.6))              # only the last 0.6 mm next to the edge, near each tab
front.BooleanSubtract(pegs)
front.BooleanSubtract(tabzone)
front.BooleanIntersection(grown(body, -FRONT_EDGE))
front.Simplify()
add_filled(board, front, F_Cu)
fmask.BooleanSubtract(pegs)                              # solder mask covers the small bites, rather than bare board
fmask.BooleanIntersection(body)
fmask.Simplify()
add_filled(board, fmask, pcbnew.F_Mask)

# the bare window in each flower: no copper on either side (the front has none in the hair; the back is cut above),
# and no solder mask on either side, so the LED shines through plain board inside the maker's silkscreen ring.
# (The LED footprint already opens a 1.9 mm mask window on the back; a wider one there would join the LED's two pads.)
for ref, (x, y, _s) in LEDS.items():
    rx, ry = RING[ref]
    assert math.hypot(x - rx, y - ry) + BARE < RING_IN - 0.15, f"{ref}: window would touch its ring"
    w = pcbnew.SHAPE_POLY_SET()
    add_circle(w, P(x, y), BARE)
    add_filled(board, w, pcbnew.F_Mask)
    _f = pcbnew.SHAPE_POLY_SET()
    add_circle(_f, P(x, y), WINDOW)
    _f.BooleanIntersection(front)
    assert area_mm2(_f) < 0.001, f"{ref}: front copper inside the light window"

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("SAO", 53.6, s1[1] + 1.6, 0.8, 0), ("OFF", 53.6, SW[1], 0.8, 0), ("BAT", 53.6, s4[1] - 1.6, 0.8, 0),
          ("CR2032", 81.9, 101.8, 0.8, 0), ("+ SIDE UP", 81.9, 103.2, 0.8, 0), ("SAO++ rA", 82.5, 88.0, 0.9, 0), ("1", 61.5, 101.6, 0.9, 0)]
labels = pcbnew.SHAPE_POLY_SET()
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
    labels.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                        (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
    _o = poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))])
    _o.BooleanSubtract(grown(body, -0.3))
    print("  label", repr(txt), "off-board mm2", round(area_mm2(_o), 3), [round(ToMM(v), 2) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())])
labels.Simplify()
# no label, letter or moved credit may sit on a pad, cross another label or leave the board
bare = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bare.Append(pad_poly(pad, B_Cu, 0.15))
bare.Simplify()
for what, shape in (("labels", labels), ("lettering", lettering)):
    h = pcbnew.SHAPE_POLY_SET(shape)
    h.BooleanIntersection(bare)
    assert area_mm2(h) < 0.001, f"{what} on a pad ({area_mm2(h):.3f} mm2)"
    h = pcbnew.SHAPE_POLY_SET(shape)
    h.BooleanSubtract(grown(body, -0.3))
    assert area_mm2(h) < 0.001, f"{what} off the board ({area_mm2(h):.3f} mm2)"
h = pcbnew.SHAPE_POLY_SET(labels)
h.BooleanIntersection(lettering)
assert area_mm2(h) < 0.001, "a label overlaps the maker's lettering"

# nothing on any layer may lie outside the outline (2018 SVG imports often carry a page frame; this one does not)
_bb = body.BBox()
_bb.Inflate(FromMM(0.3))
for d in board.GetDrawings():
    if d.GetLayer() != pcbnew.Edge_Cuts:
        assert _bb.Contains(d.GetBoundingBox()), f"drawing on {d.GetLayerName()} outside the board"
for fp in board.GetFootprints():
    if fp.GetReference() not in NEW:
        for g in fp.GraphicalItems():
            if g.IsVisible() if hasattr(g, "IsVisible") else True:
                assert _bb.Contains(g.GetBoundingBox()), f"art on {g.GetLayerName()} outside the board"

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()}, "pegs", _pegs)
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
