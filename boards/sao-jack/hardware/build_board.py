#!/usr/bin/env python3
"""Rebuild sao-jack.kicad_pcb from hamster's KiCad 6 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-jack/hardware/build_board.py

What the original is (hamster's README is a soldering guide; the rest is read from his files):
  - a 35.6 x 37.4 mm learn-to-solder kit, already SAO v1.69bis. A smiling skull and crossbones over "D3FC0N".
  - four 3 mm through-hole LEDs at the four bone ends, lens on the FRONT, legs soldered on the back; two small axial
    resistors with their bodies on the BACK, legs soldered on the front; a 2x3 through-hole shrouded header on the back.
    Each resistor feeds two LEDs side by side: R1 the two left ones (front view), R2 the two right ones.
  - front: one ground copper area in the shape of the skull, bones and base, under mask; eyes, smile, "3" and "0" are
    bare copper; skull, bones and the other letters are white silkscreen; 25 loose plated holes on the 2.54 mm grid
    (footprint 'front-eco', connected to nothing) scattered round it as dots, so the real part holes hide among them.
  - back: "D3FC0N" again, a hand-drawn circuit diagram (battery, resistors, a diode symbol by each LED), and
    "@hamster" in copper.

What this script does
  - cuts out of the file text: the old header X1, the kit parts (they come back from sao-jack-local.pretty in the same
    places), all tracks, the copper zone, the 41 outline curves, a fab-layer note, three of the 25 dots that would sit
    on the new connector's pads, and every piece of the maker's BACK silkscreen that would land under the coin cell,
    its clip, the connector, the switch or a new label (KiCad 10's Python crashes on Remove())
  - outline: the same shape as one polygon (outline.json, made by tools/extract_outline.py)
  - SAO++ parts on the back, stacked down the middle because nothing else fits: CR2032 clip in the skull's head (the
    cell slides in over the top of the head), the 6-pin SMD connector under it, the SAO / OFF / BAT switch at the
    bottom edge. The connector and switch sit 2.6 mm left of centre (front view) to clear the two resistors.
  - the four LEDs and two resistors stay through-hole, exactly where the maker had them (this is the kit)
  - front copper: the maker's ground area, rebuilt as netted polygons with the same 0.508 mm gaps and thermal spokes
  - back copper: ground, which the maker's board did not have (the standard asks for it round the SMD connector)
  - routing: back copper, plus two runs on the front between through-hole pads / one covered via (see ROUTING)

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
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks, bbox_mm, add_filled,  # noqa: E402
                         pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "sao-jack"
SRC = os.path.join(HERE, "..", "original", "jack", "jack.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

CLEAR = 0.30        # copper-to-copper gap cut into the ground copper round SMD pads, tracks and vias
TH_CLEAR = 0.508    # ... round through-hole pads and the bare-copper art: the maker's own zone clearance
TH_SPOKE = 0.508    # thermal spokes on the four LED cathode pads (maker's zone setting), so a beginner's iron can heat them
TRACK = 0.25        # the maker's track width; the gaps between the 2.54 mm dots leave room for nothing wider
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge

# ---- placement (front view) -------------------------------------------------------------------
BAT = (146.57, 75.5)        # clip centre: middle of the skull's head. The head is smaller than the cell, so the cell shows
                            # past it by up to 0.56 mm; the 0.07 mm sideways is the balance between that and keeping both
                            # solder tabs at least 1 mm from the hand-soldered LED pads beside them
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in over the top of the head
CONN = (143.4, 93.0)        # top pads 0.85 mm below the clip's closed end (as on Soot Sprite); body 3.1 mm from the left
                            # edge and 0.5 mm from resistor R1; key slot up
SW_X = 143.4                # switch under the connector, knob out of the straight bottom edge
# the maker's kit parts: reference -> (position, angle) read from his file below; nothing here moves them
KIT_LEDS = ("D1", "D2", "D3", "D4")
KIT_RES = ("R1", "R2")
# three of the maker's 25 loose dots cannot stay: each would touch a pad of the SMD connector (pads are 1.1 mm wide on
# the same 2.54 mm pitch as the dots, so no sideways shift of the connector clears all of them)
DROP_DOTS = [(144.756, 88.702), (147.296, 88.702), (139.676, 91.242)]
HAMSTER_AT = (152.0, 87.95)  # maker's copper credit, unchanged, moved from under the new connector to beside it
VIA_LOAD = (148.8, 93.6)     # switched supply up to the front, under the connector body
VIA_GND = (139.55, 96.4)     # connector pin 2's pocket of back ground, joined to the front ground
VIA_GND2 = (136.95, 100.45)  # the back ground left of, below and right of the connector, joined to the front ground
VIA_GND3 = (146.57, 68.4)     # the cell's own contact disc (and the back ground round it), joined to the front ground. It
                             # is inside the bare disc on the back and under the skull's white ink on the front

# back silkscreen labels: (text, x, y, size, angle, bold). Boxes round them also clear the maker's back art.
LABELS = [("BAT", 135.75, 101.35, 0.8, 0, False), ("SAO", 150.35, 101.75, 0.8, 0, False),
          ("SAO++ Jack rA", 135.0, 87.8, 0.6, 0, False), ("1", 139.7, 87.8, 0.6, 0, False),
          ("CR2032 +UP", 153.85, 89.6, 0.5, 0, False)]
LABEL_H = 0.8               # every label is 0.8 mm high; the number in LABELS is the letter WIDTH (0.5, 0.6 = condensed)


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def circle(c, r, n=96):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(*c), r, n)
    return ps


def label_box(txt, x, y, size, rot, _bold):
    w, h = len(txt) * size * 0.92 + 0.3, LABEL_H * 1.5 + 0.1
    if rot in (90, 270):
        w, h = h, w
    return rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


# ---- 1. read what is needed from the maker's board ---------------------------------------------------
_orig = pcbnew.LoadBoard(SRC)
_zone = [z for z in _orig.Zones()]
assert len(_zone) == 1 and _zone[0].GetNetname() == "GND" and _zone[0].GetLayer() == F_Cu
ZONE = pcbnew.SHAPE_POLY_SET(_zone[0].Outline())
KIT = {}
for fp in _orig.GetFootprints():
    r = fp.GetReference()
    if r in KIT_LEDS + KIT_RES:
        KIT[r] = {"at": mm(fp.GetPosition()), "deg": fp.GetOrientationDegrees(), "back": fp.IsFlipped(),
                  "pads": {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads()}}
assert sorted(KIT) == sorted(KIT_LEDS + KIT_RES)

# where the new parts will be, as plain shapes, to decide which of the maker's back silkscreen can stay
SW_Y = None  # set below from the outline
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
BOTTOM = max(y for _, y in _ol["outer"])
SW_Y = BOTTOM - PAD_EDGE - 1.83          # outer solder tabs PAD_EDGE inside the straight bottom edge
KEEP_OFF = circle(BAT, 10.35)                                                        # the cell
for _shape in [rect(BAT[0] - 11.8, BAT[1] - 4.6, BAT[0] + 11.8, BAT[1] + 11.3),              # the clip
               rect(CONN[0] - 7.9, CONN[1] - 5.8, CONN[0] + 7.9, CONN[1] + 5.8),            # connector body and pads
               rect(SW_X - 6.0, SW_Y - 2.4, SW_X + 6.0, BOTTOM + 1),                        # switch
               rect(HAMSTER_AT[0] - 3.9, HAMSTER_AT[1] - 0.95, HAMSTER_AT[0] + 3.9, HAMSTER_AT[1] + 0.95)
               ] + [label_box(*lab) for lab in LABELS]:
    KEEP_OFF.BooleanAdd(_shape)
KEEP_OFF.Simplify()


def _hits(ps):
    both = pcbnew.SHAPE_POLY_SET(ps)
    both.BooleanIntersection(KEEP_OFF)
    return area_mm2(both) > 0.001


_drop_ids, _silk_kept, _silk_dropped = set(), 0, 0
for fp in _orig.GetFootprints():
    name = str(fp.GetFPID().GetLibItemName())
    if name == "back-silkscreen":
        for g in fp.GraphicalItems():
            assert g.GetShape() == pcbnew.SHAPE_T_POLY and g.GetLayer() == B_SilkS
            _ps = pcbnew.SHAPE_POLY_SET(g.GetPolyShape())
            if _hits(_ps) or area_mm2(_ps) < 0.01:          # (one of the 27 is a zero-size speck)
                _drop_ids.add(g.m_Uuid.AsString())
                _silk_dropped += 1
            else:
                _silk_kept += 1
    if name == "front-eco":
        _dots = {p.m_Uuid.AsString(): mm(p.GetPosition()) for p in fp.Pads()}
for d in _orig.GetDrawings():                    # the 31 loose lines: four diode symbols and the old header's outline box
    if d.GetLayer() == B_SilkS and d.GetClass() == "PCB_SHAPE":
        ps = pcbnew.SHAPE_POLY_SET()
        d.TransformShapeToPolygon(ps, B_SilkS, 0, ERR, pcbnew.ERROR_OUTSIDE)
        _lone = not _hits(ps)                    # one line survives the test: the left side of the old header's box
        _drop_ids.add(d.m_Uuid.AsString())
        _silk_dropped += 1
        assert not _lone or ToMM(d.GetStart().x) < 134, "a line of the maker's back drawing could have stayed: look at it"
assert _silk_kept == 0
print(f"maker's back silkscreen drawing: all {_silk_dropped} pieces removed (each one under the cell, clip, connector, switch or a label)")
assert len(_dots) == 25
for want in DROP_DOTS:
    hit = [u for u, at in _dots.items() if abs(at[0] - want[0]) < 0.05 and abs(at[1] - want[1]) < 0.05]
    assert len(hit) == 1, want
    _drop_ids.add(hit[0])
DOTS_KEPT = [at for u, at in _dots.items() if u not in _drop_ids]

# ---- 2. cut the old electrical parts out of the file text --------------------------------------------
_txt = open(SRC, encoding="utf-8").read()
_cut, _gone = [], []
for a_, b_ in blocks(_txt, "footprint"):
    ref = re.search(r'\(fp_text reference "([^"]+)"', _txt[a_:b_]).group(1)
    if ref == "X1" or ref in KIT:
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == sorted(["X1"] + list(KIT)), _gone
for kind in ("segment", "arc", "zone", "group", "gr_curve", "gr_rect"):
    _cut += list(blocks(_txt, kind))
_cut += [(a_, b_) for a_, b_ in blocks(_txt, "gr_text") if "FAB MARKINGS HERE" in _txt[a_:b_]]
_n = len(_cut)
for kind, indent in (("gr_line", 2), ("fp_poly", 4), ("pad", 4)):
    for a_, b_ in blocks(_txt, kind, indent):
        m = re.search(r"\(tstamp ([0-9a-f-]+)\)", _txt[a_:b_])
        if m and m.group(1) in _drop_ids:
            _cut.append((a_, b_))
assert len(_cut) - _n == len(_drop_ids), (len(_cut) - _n, len(_drop_ids))
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n  \(net [1-9]\d* "[^"]*"\)', _txt)]
_txt = cut_blocks(_txt, _cut)
assert "Edge.Cuts\")" not in _txt.split("(setup")[1].split("(net 0")[1], "an outline item survived the cut"
_tmp = os.path.join(tempfile.mkdtemp(), "jack.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)
board = pcbnew.LoadBoard(_tmp)
assert not list(board.Tracks()) and not list(board.Zones())

# ---- 3. outline: the maker's shape as one polygon ----------------------------------------------------
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)

# ---- 4. the circuit (shared with the schematic generator) --------------------------------------------
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


# ---- 5. footprints -----------------------------------------------------------------------------------
def link(fp, ref):
    """Tie the footprint to its schematic symbol (path, part fields, nets) so KiCad's schematic-parity check passes."""
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
    fp.SetFPID(pcbnew.LIB_ID(*fpid.split(":")))
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


def load(ref, pos, back=True):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    if back:
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    return fp


def place(ref, pos, want, back=True):
    """Place, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    fp = load(ref, pos, back)
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
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X + 3.0, SW_Y - 1.43)))   # pins toward the connector; pin 1 (badge) lands right
assert abs(padpos(sw, "4")[0] - (SW_X - 3.0)) < 0.01 and padpos(sw, "4")[1] < SW_Y
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
assert ToMM(_kb.GetTop()) > SW_Y, "knob is not pointing down"
print(f"switch centre y {SW_Y:.3f}; knob tip {ToMM(_kb.GetBottom()):.2f}, {ToMM(_kb.GetBottom()) - BOTTOM:.2f} mm past the bottom edge")

# the kit parts, in the maker's places. LEDs on the front (lens on the art side), resistors on the back.
KIT_ATTR = pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES     # hand-soldered by the buyer, never by the assembler
kit = {}
for r in KIT_LEDS:
    k = KIT[r]
    assert not k["back"]
    fp = load(r, k["at"], back=False)
    fp.SetOrientationDegrees(k["deg"])
    link(fp, r)
    kit[r] = fp
for r in KIT_RES:
    k = KIT[r]
    assert k["back"]
    kit[r] = place(r, k["at"], ("2", k["pads"]["2"]))      # pad 1 is the footprint's origin, so pad 2 sets the angle
for r, fp in kit.items():
    fp.SetAttributes(fp.GetAttributes() | KIT_ATTR)
    fp.Value().SetVisible(False)
    for num, at in KIT[r]["pads"].items():
        got = padpos(fp, num)
        assert abs(got[0] - at[0]) < 0.002 and abs(got[1] - at[1]) < 0.002, f"{r} pad {num} is at {got}, the maker had it at {at}"
print("kit parts: all 12 holes are exactly where the maker drilled them")

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
STRAP = (ToMM(_sb.GetLeft()), ToMM(_sb.GetTop()), ToMM(_sb.GetRight()), ToMM(_sb.GetBottom()))
print("battery clip angle", _rot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f" % (STRAP[0], STRAP[2], STRAP[1], STRAP[3]))
assert STRAP[3] > BAT[1] + 10, "closed end is not pointing down"
# the clip's own silkscreen (arrow, '+', closed-end line) would print on the bare cell disc or off the head: fab layer
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)
# how far the 20 mm cell overhangs the skull's head
_over = circle(BAT, 10.0, 360)
_over.BooleanSubtract(body)
_far = 0.0
for k in range(720):
    a = math.pi * k / 360
    pt = P(BAT[0] + 10.0 * math.cos(a), BAT[1] + 10.0 * math.sin(a))
    if not body.Contains(pt):
        _far = max(_far, ToMM(body.Outline(0).Distance(pt)))
print(f"cell overhang past the head: {area_mm2(_over):.1f} mm2, at most {_far:.2f} mm")
assert _far < 0.6

# how close the hand-soldered LED pads come to the clip's solder tabs (cell +): a beginner's solder blob must not bridge it
for r in ("D1", "D2"):
    gap = 99.0
    for cp in bat.Pads():
        if cp.GetNumber() != "1":
            continue
        tab = pad_poly(cp, B_Cu)                 # (keep a name on every polygon: KiCad frees unnamed ones while in use)
        for lp in kit[r].Pads():
            led = pad_poly(lp, B_Cu)
            ring = led.Outline(0)
            for k in range(ring.PointCount()):
                gap = min(gap, ToMM(tab.Outline(0).Distance(ring.CPoint(k))))
    print(f"{r}: nearest LED pad to a clip tab {gap:.2f} mm (the LED's own two pads are 0.74 mm apart)")
    assert gap > 0.99

# the maker's art footprints stay as they are (they are not parts)
NEW = set(PARTS)
ART = [fp for fp in board.GetFootprints() if fp.GetReference() not in NEW]
assert sorted(str(fp.GetFPID().GetLibItemName()) for fp in ART) == ["back-silkscreen", "front-eco", "front-mask", "front-silkscreen"]
for fp in ART:
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
DOT_PADS = [p for fp in ART for p in fp.Pads()]
assert len(DOT_PADS) == 22 and all(not p.GetNetname() for p in DOT_PADS)

# every pad of a new part sits on the board, PAD_EDGE inside the edge; no new SMD pad or peg hole touches a dot
_newcu = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            lay = B_Cu if pad.IsOnLayer(B_Cu) else F_Cu
            off = pad_poly(pad, lay)
            off.BooleanSubtract(pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
            if fp.GetReference() in ("J1", "SW1", "BT1"):
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    _newcu.BooleanAdd(circle(mm(pad.GetPosition()), ToMM(pad.GetDrillSize().x) / 2 + 0.25))
                else:
                    _newcu.BooleanAdd(pad_poly(pad, B_Cu, 0.2))
_newcu.Simplify()
for p in DOT_PADS:
    d = pad_poly(p, B_Cu)
    d.BooleanIntersection(_newcu)
    assert area_mm2(d) == 0, f"dot at {mm(p.GetPosition())} touches a new pad: add it to DROP_DOTS"

# ---- 6. ROUTING ----------------------------------------------------------------------------------------
# The switch is mirrored on the back, so its badge contact is on the right and its cell contact on the left, while
# connector pin 1 is on the left: the three supplies have to cross between switch and connector. On the back alone
# that cannot be done (the clip's closed end leaves no room above the connector). So:
#   back:  badge 3.3 V   switch pin 1 -> right -> up beside the connector pads -> between its two pad rows -> pin 1
#          coin cell     switch pin 4 -> left -> up between the dot columns -> clip left pad; and across the top of the
#                        connector (under the clip's own closed end, same net) -> right -> up -> clip right pad
#          switched      switch pin 3 -> up between two connector pads -> one covered via under the connector body
#          LED nets      R2 -> the two right LEDs; left LED to left LED
#   front: switched supply, via -> R1 (3.6 mm); and R1 -> left LEDs round the bottom edge and up the left side, pad to
#          pad (through-hole pads, so no extra holes). Both run inside the maker's ground copper, under mask.
TRACKS, VIAS = [], []


def route(net, pts, layer=B_Cu, width=TRACK):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append(t)


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


j1, j2 = padpos(conn, "1"), padpos(conn, "2")
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
PIN_ROW = 99.5              # leaves the switch pins sideways, between the connector's lower pads (end 98.6) and the tabs
LANE_SAO, LANE_LOAD = 92.4, 93.6    # the two lanes between the connector's pad rows (91.8 .. 94.2), under its body
assert abs(j1[1] + 2.2 - (CONN[1] - 1.2)) < 0.01

# badge 3.3 V
route("VSAO", [(s1[0], PIN_ROW), (150.3, PIN_ROW), (150.3, LANE_SAO), (j1[0], LANE_SAO), (j1[0], j1[1] + 1.5)])
# switched supply: up between connector pads 2 and 4 to the via; R1 and R2 top pads joined on the back
route("VLOAD", [(142.0, s3[1]), (142.0, LANE_LOAD), VIA_LOAD])
via("VLOAD", VIA_LOAD)
r1t, r1b = padpos(kit["R1"], "2"), padpos(kit["R1"], "1")
r2t, r2b = padpos(kit["R2"], "2"), padpos(kit["R2"], "1")
assert r1t[1] < r1b[1] and r2t[1] < r2b[1]
route("VLOAD", [VIA_LOAD, r1t], layer=F_Cu)
route("VLOAD", [r1t, r2t])
# coin cell
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
RISE = 138.38               # between the dot columns at 137.1 and 139.7
LINK = CONN[1] - 5.6 - 0.55   # across the top of the connector pads, 0.425 mm above them
route("VBAT", [(s4[0], PIN_ROW), (RISE, PIN_ROW), (RISE, 82.4), (136.5, 80.3), (136.5, bt[0][1] + 2.0)])
route("VBAT", [(RISE, LINK), (146.9, LINK), (147.6, LINK + 0.7), (147.6, 89.0), (148.3, 89.7), (156.19, 89.7), (156.19, 82.4),
               (157.0, 81.6), (157.0, bt[1][1] + 2.0)])
# right LEDs: R2 bottom pad -> up between R2 and the two dots -> D4 anode -> up between the dot columns -> D2 anode
d = {r: (padpos(kit[r], "1"), padpos(kit[r], "2")) for r in KIT_LEDS}
route("LED_R", [r2b, (156.115, r2b[1] - 1.195), (156.115, 93.5), (157.0, 92.6)])
route("LED_R", [(157.45, 91.2), (157.45, 88.4), (158.73, 87.3), (158.73, 79.9), d["D2"][1]])
# left LEDs: D3 anode -> up -> between the dot columns -> D1 anode (back); R1 bottom pad -> D3 anode (front)
route("LED_L", [(134.95, 91.6), (134.95, 88.2), (134.4, 87.65), (133.85, 87.65), (133.3, 87.1), (133.3, 79.9), (131.9, 78.0)])
# ... on the front it follows the board edge, in the outermost 0.55-0.8 mm where the ground copper's rim was, so the
# maker's copper area keeps its shape (a run straight across would have cut the bottom-left corner off the ground)
_rim_ps = grown(body, -(EDGE + TRACK / 2 + 0.01))
_rim = [mm(_rim_ps.Outline(0).CPoint(k)) for k in range(_rim_ps.Outline(0).PointCount())]
_a = min(range(len(_rim)), key=lambda k: math.hypot(_rim[k][0] - 151.6, _rim[k][1] - 110))       # on the bottom edge
_step = 1 if any(_rim[(_a + k) % len(_rim)][0] < 140 and _rim[(_a + k) % len(_rim)][1] > 95 for k in range(1, 12)) else -1
_run, _k, _top = [(151.6, _rim[_a][1])], _a, 93.95        # start below R1; stop on the left edge just below D3's anode
while len(_run) < 150:
    _k = (_k + _step) % len(_rim)
    x_, y_ = _rim[_k]
    if y_ < _top:                                        # walked up the left edge past D3: stop at _top exactly
        px_, py_ = _run[-1]
        _run.append((round(px_ + (x_ - px_) * (_top - py_) / (y_ - py_), 3), _top))
        break
    if x_ < 151.6:
        _run.append((x_, y_))
print("edge run:", len(_run), "points, from", _run[0], "to", _run[-1])
assert len(_run) < 150 and _run[-1][0] < 134 and all(x_ < 152 for x_, _ in _run), "the edge run went the wrong way round the board"
route("LED_L", [r1b] + _run + [(134.2, 93.0)], layer=F_Cu)
# ground: connector pin 2 sits in a pocket of back ground fenced in by the cell track; one via joins it to the front
route("GND", [(j2[0], VIA_GND[1]), VIA_GND])
via("GND", VIA_GND)
via("GND", VIA_GND2)
via("GND", VIA_GND3)

# ---- 7. the maker's credit, moved (not changed) ------------------------------------------------------------
_cred = [t for t in board.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetText() == "@hamster"]
assert len(_cred) == 1 and _cred[0].GetLayer() == B_Cu
_cred[0].SetPosition(P(*HAMSTER_AT))
_cb = _cred[0].GetBoundingBox()
CREDIT = (ToMM(_cb.GetLeft()), ToMM(_cb.GetTop()), ToMM(_cb.GetRight()), ToMM(_cb.GetBottom()))
print("@hamster copper lettering now x %.2f..%.2f y %.2f..%.2f" % (CREDIT[0], CREDIT[2], CREDIT[1], CREDIT[3]))
CREDIT_WIN = rect(CREDIT[0] - 0.3, CREDIT[1] - 0.25, CREDIT[2] + 0.3, CREDIT[3] + 0.25)

# ---- 8. ground copper, both sides ------------------------------------------------------------------------
gnd_code = nets["GND"].GetNetCode()
ART_CU = pcbnew.SHAPE_POLY_SET()        # the maker's bare-copper art on the front: eyes, smile, "3", "0"
for fp in ART:
    for g in fp.GraphicalItems():
        if g.GetLayer() == F_Cu:
            ART_CU.BooleanAdd(pcbnew.SHAPE_POLY_SET(g.GetPolyShape()))
ART_CU.Simplify()
print("front bare-copper art: %d shapes, %.0f mm2" % (ART_CU.OutlineCount(), area_mm2(ART_CU)))


def spokes(pad, layer):
    """A plus sign of copper across a through-hole ground pad, lined up with the pad's own sides."""
    c = pad.GetPosition()
    shape = pad_poly(pad, layer)
    o = shape.Outline(0)
    a = math.atan2(o.CPoint(1).y - o.CPoint(0).y, o.CPoint(1).x - o.CPoint(0).x)
    reach = ToMM(pad.GetSize(layer).x) / 2 + TH_CLEAR + 0.4
    out = pcbnew.SHAPE_POLY_SET()
    for b in (a, a + math.pi / 2):
        ux, uy = math.cos(b), math.sin(b)
        vx, vy = -uy * TH_SPOKE / 2, ux * TH_SPOKE / 2
        cx, cy = ToMM(c.x), ToMM(c.y)
        out.BooleanAdd(poly([(cx - ux * reach - vx, cy - uy * reach - vy), (cx + ux * reach - vx, cy + uy * reach - vy),
                         (cx + ux * reach + vx, cy + uy * reach + vy), (cx - ux * reach + vx, cy - uy * reach + vy)]))
    out.Simplify()
    return out


def ground(layer, base, extra_cut=None):
    cut, relief, bars, anchors = (pcbnew.SHAPE_POLY_SET() for _ in range(4))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                cut.BooleanAdd(circle(mm(pad.GetPosition()), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02))
            elif not pad.IsOnLayer(layer):
                continue
            elif pad.GetNetCode() == gnd_code:
                anchors.BooleanAdd(pad_poly(pad, layer))
                if pad.GetDrillSize().x:
                    relief.BooleanAdd(pad_poly(pad, layer, TH_CLEAR))
                    bars.BooleanAdd(spokes(pad, layer))
            else:
                cut.BooleanAdd(pad_poly(pad, layer, TH_CLEAR if pad.GetDrillSize().x else CLEAR))
    for t in TRACKS:
        if t.GetLayer() == layer and t.GetNetCode() != gnd_code:
            ch = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(ch, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
            cut.BooleanAdd(ch)
    for v in VIAS:
        if v.GetNetCode() != gnd_code:
            cut.BooleanAdd(circle(mm(v.GetPosition()), 0.3 + CLEAR + 0.02))
        else:
            anchors.BooleanAdd(circle(mm(v.GetPosition()), 0.3))
    if extra_cut is not None:
        cut.BooleanAdd(extra_cut)
    cut.Simplify()
    relief.Simplify()
    bars.BooleanIntersection(base)
    cu = pcbnew.SHAPE_POLY_SET(base)
    cu.BooleanSubtract(relief)
    cu.BooleanAdd(bars)
    cu.BooleanSubtract(cut)
    # drop necks and slivers thinner than 0.3 mm. (Done by growing what is NOT copper: shrinking a polygon that has
    # holes opens slits in KiCad 10.)
    gaps = pcbnew.SHAPE_POLY_SET(base)
    gaps.BooleanSubtract(cu)
    core = grown(base, -0.15)
    core.BooleanSubtract(grown(gaps, 0.15))
    core = grown(core, 0.15)
    core.BooleanIntersection(cu)
    core.Simplify()
    anchors.Simplify()
    kept = dropped = 0
    kept_mm2 = 0.0
    for i in range(core.OutlineCount()):
        piece = pcbnew.SHAPE_POLY_SET(core.Polygon(i))
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(anchors)
        if area_mm2(both) > 0.01:
            add_filled(board, piece, layer, nets["GND"])
            kept += 1
            kept_mm2 += area_mm2(piece)
        else:
            dropped += 1
            print("  %s: left out a loose piece of %.2f mm2 at" % (board.GetLayerName(layer), area_mm2(piece)), [round(v, 1) for v in bbox_mm(piece)])
    print("%s ground: %d pieces, %.0f mm2; %d loose pieces left out" % (board.GetLayerName(layer), kept, kept_mm2, dropped))


front = pcbnew.SHAPE_POLY_SET(ZONE)
front.BooleanIntersection(inner)
ground(F_Cu, front, grown(ART_CU, TH_CLEAR))
ground(B_Cu, inner, CREDIT_WIN)

# ---- 9. back silkscreen labels ---------------------------------------------------------------------------
for txt, x, y, size, rot, bold in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(LABEL_H)))
    t.SetTextThickness(FromMM(0.12))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- report -----------------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = 0             # the maker's setting; his dots and art are drawn for it
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetDate("2026-11-11")
board.GetTitleBlock().SetCompany("")
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
# SaveBoard rewrites the project file with default rule severities. One is deliberately lowered here: "plated hole inside
# a part's keep-out box" fires for eleven of the maker's loose dots that lie under the clip's and connector's boxes
# (they are joined to nothing and nothing is soldered in them), so it is a warning to read, not an error.
_pro = OUT.replace(".kicad_pcb", ".kicad_pro")
_p = json.load(open(_pro))
_p["board"]["design_settings"]["rule_severities"]["pth_inside_courtyard"] = "warning"
json.dump(_p, open(_pro, "w"), indent=2)
print("saved", OUT)
