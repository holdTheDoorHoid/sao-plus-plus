#!/usr/bin/env python3
"""Rebuild soot-sprite.kicad_pcb from davedarko's KiCad 9 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/soot-sprite/hardware/build_board.py

What the original is (it is not documented anywhere by the maker; read from the files):
  - a 40 mm round board. The front is the sprite: two copper halves under (black) solder mask, split by a zigzag gap,
    and two white silkscreen eyes. The halves were the power planes: left = GND, right = VCC.
  - the back had a Keystone 1060 CR2032 holder and a 2x3 SMD header drawn ON TOP OF EACH OTHER in the middle, so a
    builder fitted one or the other; one 1206 resistor in the header's supply line, shorted by a track you cut
    ("cut before adding resistor"); and four bare 4 x 4 mm pads (two VCC, two GND) for the legs of hand-soldered
    5 mm LEDs, which wear the 3D-printed konpeito candies made by original/Soot Sprites/Kompeito.scad.

What this script does
  - loads the original and cuts out of the file text the old parts, tracks, vias, pours, the round Edge.Cuts circle,
    a back mask window, and the maker's 'VCC' / 'GND' / 'cut before adding resistor' labels (KiCad 10's Python
    crashes on Remove())
  - outline: the same 40.00 mm circle, as one polygon (outline.json) so the panel tool can read it
  - places the SAO++ parts on the back: CR2032 clip at the top (cell slides in from the top edge), the SAO connector
    below the middle, the SAO / OFF / BAT switch with its knob at the bottom edge, one 1.3 k resistor per + pad
  - keeps the four 4 x 4 mm pads; the two foot pads move outward ~2.5 mm and the left arm pad 0.7 mm left, to clear
    the new parts. The maker's credit stays exactly where it was; the maker's logo moves down the same side, unchanged
  - front copper: the maker's two halves exactly as drawn, again as power planes: left = GND, right = the switched
    supply (VLOAD). Four tented vias (two GND, two VLOAD), all under the connector body or behind the right half,
    replace the maker's five edge vias; this is what lets everything else route on the back without crossings
  - back copper: GND, cleared around everything that is not GND

Coordinates are millimetres in KiCad's front view (x grows right, y grows down). Board centre (20, 20), radius 20.
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

SLUG = "soot-sprite"
SRC = os.path.join(HERE, "..", "original", "Soot Sprites", "soot", "soot.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks
THIN = 0.30         # tracks that pass between connector pads
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge

C0 = (20.0, 20.0)   # board centre
RAD = 20.0

# ---- placement (front view) -------------------------------------------------------------------
BAT = (17.1, 10.9)          # clip centre. 1.9 mm left of centre so its right solder tab clears the maker's credit
                            # lettering (0.28 mm), 0.9 mm down so the 20 mm cell stays 0.45 mm inside the round edge
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in from the top edge
CONN = (20.0, 28.4)         # under the middle; top pads 0.9 mm below the clip's closed end, key slot up
SW_X = 20.0                 # switch centred on the bottom edge, knob pointing down
R1_AT = (7.0, 23.6)         # feeds the left arm pad (TP4)
R2_AT = (9.75, 28.0)        # feeds the left foot pad (TP3)
TPS = {                     # the maker's four 4 x 4 mm pads: (new centre, maker's centre)
    "TP1": ((30.25, 33.0), (27.5, 33.0)),   # right foot, -  (moved out 2.75 mm: the connector body is 15.3 mm wide)
    "TP2": ((36.0, 20.0), (36.0, 20.0)),    # right arm, -   (unchanged)
    "TP3": ((9.75, 33.0), (12.0, 33.0)),    # left foot, +   (moved out 2.25 mm)
    "TP4": ((3.3, 20.0), (4.0, 20.0)),      # left arm, +    (moved 0.7 mm left, clear of the clip's side rail)
}
# + and - swap sides compared with the maker's VCC / GND labels: a part on the back is mirrored, so with its pins facing
# the connector the switch's badge contact (pin 1) can only sit on the right (front view) and the coin-cell contact on
# the left. The switched supply therefore leaves on the left, and the + pads are the left ones. Nothing else changes.
LOGO_AT = (31.0, 26.0)      # maker's logo (was at 8.5, 9.2, where the clip's left solder tab now sits): same size, right side
VIA_LOAD_J1 = (18.73, 31.8)  # switched supply to the front left half: between the connector's lower pads, under its body
VIA_LOAD_R = (8.5, 25.0)     # ... and back up beside R1 / R2
VIA_GND_J1 = (21.27, 27.6)   # GND inside the connector footprint (pin 2's island), joined through the front right half
VIA_GND_MAIN = (25.6, 24.5)  # ... to the main back GND (also under the connector body)

# ---- cut the 2026 electrical parts out of the file text ------------------------------------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block of a KiCad 9 file (one tab of indent)."""
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
    if ref in ("R1", "J1", "BT1", "TP1", "TP2", "TP3", "TP4"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["BT1", "J1", "R1", "TP1", "TP2", "TP3", "TP4"], _gone
for kind in ("segment", "via", "zone"):
    _cut += list(tblocks(_txt, kind))
_texts = [(a_, b_) for a_, b_ in tblocks(_txt, "gr_text") if re.match(r'\n\t\(gr_text "(VCC|GND|cut before)', _txt[a_:b_])]
assert len(_texts) == 3, len(_texts)
_cut += _texts
_other = [(a_, b_) for k in ("gr_rect", "gr_circle") for a_, b_ in tblocks(_txt, k)
          if '(layer "B.Mask")' in _txt[a_:b_] or '(layer "Edge.Cuts")' in _txt[a_:b_]]
assert len(_other) == 2, len(_other)          # the back mask window at the top, and the round outline
_cut += _other
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n\t\(net [1-9]\d* "[^"]*"\)', _txt)]
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "soot.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

_orig = pcbnew.LoadBoard(SRC)
_zones = {z.GetNetname(): pcbnew.SHAPE_POLY_SET(z.Outline()) for z in _orig.Zones()}
assert sorted(_zones) == ["GND", "VCC"], sorted(_zones)
_vcc_priority = [z.GetAssignedPriority() for z in _orig.Zones() if z.GetNetname() == "VCC"][0]
assert _vcc_priority > [z.GetAssignedPriority() for z in _orig.Zones() if z.GetNetname() == "GND"][0]
_cred = [d for d in _orig.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT) and "davedarko" in d.GetText()]
assert len(_cred) == 1
CREDIT_BOX = bbox_mm(poly([(ToMM(_cred[0].GetBoundingBox().GetLeft()), ToMM(_cred[0].GetBoundingBox().GetTop())),
                           (ToMM(_cred[0].GetBoundingBox().GetRight()), ToMM(_cred[0].GetBoundingBox().GetBottom())),
                           (ToMM(_cred[0].GetBoundingBox().GetLeft()), ToMM(_cred[0].GetBoundingBox().GetBottom()))]))

board = pcbnew.LoadBoard(_tmp)
TRACKS = []

# ---- outline: the maker's 40 mm circle as one polygon -----------------------------------------------
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
pad_ok = grown(body, -PAD_EDGE)

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

# switch: as low as it can go with its outer solder tabs still PAD_EDGE inside the round edge, so the knob reaches out
# of the bottom edge as far as the circle allows
SW_Y = C0[1] + math.sqrt((RAD - PAD_EDGE - 0.01) ** 2 - 5.65 ** 2) - 1.83
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X + 3.0, SW_Y - 1.43)))   # pins toward the connector; pin 1 (badge) lands right
assert abs(padpos(sw, "4")[0] - (SW_X - 3.0)) < 0.01 and padpos(sw, "4")[1] < SW_Y
_knob = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User]
_kb = _knob[0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetBottom())
assert ToMM(_kb.GetTop()) > SW_Y, "knob is not pointing down"
print(f"switch centre y {SW_Y:.3f}; knob tip {KNOB_TIP:.2f}, {KNOB_TIP - (C0[1] + RAD):.2f} mm past the bottom of the circle")

res = {"R1": place("R1", R1_AT, ("1", (R1_AT[0] + 0.825, R1_AT[1]))),           # supply pad on the right
       "R2": place("R2", R2_AT, ("1", (R2_AT[0], R2_AT[1] - 0.825)))}           # supply pad on top
# the four pads: bare copper, nothing to buy or place, so they are board-only footprints (no schematic symbol), taken
# unchanged from KiCad's stock TestPoint_Pad_4.0x4.0mm, the footprint the maker used (copy in soot-sprite-local.pretty)
TP_NET = {"TP1": "GND", "TP2": "GND", "TP3": "LEG_A", "TP4": "ARM_A"}
tp = {}
for r, (at, _) in TPS.items():
    fp = pcbnew.FootprintLoad(LOCAL_LIB, "TestPoint_Pad_4.0x4.0mm")
    fp.SetReference(r)
    board.Add(fp)
    fp.SetPosition(P(*at))
    fp.Flip(P(*at), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    fp.SetFPID(pcbnew.LIB_ID("TestPoint", "TestPoint_Pad_4.0x4.0mm"))   # its name in KiCad's stock library
    fp.SetValue("LED leg pad")
    fp.Value().SetVisible(False)
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    for pad in fp.Pads():
        pad.SetNet(nets[TP_NET[r]])
    tp[r] = fp

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
_strap = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0]
STRAP = bbox_mm(poly([(ToMM(_strap.GetBoundingBox().GetLeft()), ToMM(_strap.GetBoundingBox().GetTop())),
                      (ToMM(_strap.GetBoundingBox().GetRight()), ToMM(_strap.GetBoundingBox().GetBottom())),
                      (ToMM(_strap.GetBoundingBox().GetLeft()), ToMM(_strap.GetBoundingBox().GetBottom()))]))
print("battery clip angle", _rot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f" % (STRAP[0], STRAP[2], STRAP[1], STRAP[3]))
# the clip's own silkscreen (insertion arrow off the top edge, '+' and closed-end line under the cell) moves to the fab
# layer; the board gets its own labels below
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

# the 2026 logo: same footprint, same size and angle, moved down the same side
NEW = set(PARTS) | set(TPS)
logo = [fp for fp in board.GetFootprints() if fp.GetReference() not in NEW]
assert len(logo) == 1 and "logo" in logo[0].GetFPIDAsString()
logo = logo[0]
_lb0 = bbox_mm(poly([(ToMM(logo.GetBoundingBox(False).GetLeft()), ToMM(logo.GetBoundingBox(False).GetTop())),
                     (ToMM(logo.GetBoundingBox(False).GetRight()), ToMM(logo.GetBoundingBox(False).GetBottom())),
                     (ToMM(logo.GetBoundingBox(False).GetLeft()), ToMM(logo.GetBoundingBox(False).GetBottom()))]))
logo.SetLocked(False)
logo.SetPosition(P(*LOGO_AT))
logo.SetLocked(True)
logo.SetAttributes(logo.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
_lb = logo.GetBoundingBox(False)
LOGO_BOX = (ToMM(_lb.GetLeft()), ToMM(_lb.GetTop()), ToMM(_lb.GetRight()), ToMM(_lb.GetBottom()))
print("logo moved from x %.2f..%.2f y %.2f..%.2f" % (_lb0[0], _lb0[2], _lb0[1], _lb0[3]),
      "to x %.2f..%.2f y %.2f..%.2f" % (LOGO_BOX[0], LOGO_BOX[2], LOGO_BOX[1], LOGO_BOX[3]))

# every pad of a new part sits on the board, PAD_EDGE inside the edge
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"


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
s1, s3, s4 = padpos(sw, "1"), padpos(sw, "3"), padpos(sw, "4")
UNDER = 34.5                # the row between the connector's lower pads (end 33.8) and the switch pins (start 34.91)

# badge 3.3 V: switch pin 1 (right) -> right of the connector pads, under its body -> up -> along the top of the
# connector, between its top pads and the cell link -> into pin 1 from above
TOP = 22.3
route("VSAO", [s1, (s1[0], UNDER), (24.0, UNDER), (24.0, TOP), (j1[0], TOP), j1], width=THIN)

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. A branch drops from it down the left of the connector to pin 4.
bt_l = [mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"]
bt_l.sort()
_r = math.hypot(bt_l[0][0] - BAT[0], bt_l[0][1] - BAT[1])
_deg = list(range(180, -1, -5))
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in _deg]
assert all(y >= BAT[1] - 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt_l[0]] + arc[1:-1] + [bt_l[1]])
_drop = arc[_deg.index(105)]                                # just left of the bottom of the link
route("VBAT", [s4, (s4[0], UNDER), (_drop[0], UNDER), _drop], width=THIN)

# switched supply: switch pin 3 -> via between the connector's lower pads -> front left half -> via -> R1, R2
route("VLOAD", [s3, (s3[0], UNDER), (VIA_LOAD_J1[0], UNDER - 0.3), VIA_LOAD_J1], width=THIN)
via("VLOAD", VIA_LOAD_J1)
via("VLOAD", VIA_LOAD_R)
r1a, r1b = padpos(res["R1"], "1"), padpos(res["R1"], "2")
r2a, r2b = padpos(res["R2"], "1"), padpos(res["R2"], "2")
route("VLOAD", [VIA_LOAD_R, (r1a[0], VIA_LOAD_R[1] - 0.7), r1a])
route("VLOAD", [VIA_LOAD_R, (r2a[0], VIA_LOAD_R[1] + 1.25), r2a])
# resistor -> its pad (the pad is the + of a hand-soldered LED)
tp4, tp3 = padpos(tp["TP4"], "1"), padpos(tp["TP3"], "1")
route("ARM_A", [r1b, (tp4[0] + 1.3, r1b[1]), (tp4[0] + 1.0, tp4[1] + 1.3)])
route("LEG_A", [r2b, (r2b[0], tp3[1] - 1.4)])
# GND: pin 2's island inside the connector footprint reaches the main back GND through the front right half
via("GND", VIA_GND_J1)
via("GND", VIA_GND_MAIN)

# ---- front copper: the maker's two halves, as power planes again (left = switched supply, right = GND) ----
front_r = pcbnew.SHAPE_POLY_SET(_zones["VCC"])            # higher priority in the original: it fills first
front_r.BooleanIntersection(inner)
front_l = pcbnew.SHAPE_POLY_SET(_zones["GND"])
front_l.BooleanIntersection(inner)
front_l.BooleanSubtract(grown(front_r, 0.5))              # the original pours kept 0.5 mm apart
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.27)
for half, net in ((front_l, "VLOAD"), (front_r, "GND")):
    half.BooleanSubtract(pegs)
    foreign = pcbnew.SHAPE_POLY_SET()
    for v in VIAS:
        if v.GetNetname() != net:
            add_circle(foreign, v.GetPosition(), 0.3 + CLEAR + 0.02)
    half.BooleanSubtract(foreign)
    half.Simplify()
    for v in VIAS:                                         # each via lands well inside its own half
        if v.GetNetname() == net:
            ring = pcbnew.SHAPE_POLY_SET()
            add_circle(ring, v.GetPosition(), 0.3 + 0.15)
            ring.BooleanSubtract(half)
            assert area_mm2(ring) < 1e-4, f"{net} via at {mm(v.GetPosition())} is not inside its front half"
    add_filled(board, half, F_Cu, nets[net])
print("front halves, mm2: left (VLOAD) %.0f, right (GND) %.0f" % (area_mm2(front_l), area_mm2(front_r)))

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
for v in VIAS:
    if v.GetNetCode() != gnd_code:
        add_circle(channels, v.GetPosition(), 0.3 + CLEAR + 0.02)
channels.Simplify()
cut.Append(channels)
cut.Simplify()
art.BooleanSubtract(cut)
# drop slivers thinner than 0.3 mm (they would only be specks of copper)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.Simplify()

# no track may run through the maker's lettering or logo
_txtbox = poly([(CREDIT_BOX[0], CREDIT_BOX[1]), (CREDIT_BOX[2], CREDIT_BOX[1]), (CREDIT_BOX[2], CREDIT_BOX[3]), (CREDIT_BOX[0], CREDIT_BOX[3])])
_txtbox.Append(poly([(LOGO_BOX[0], LOGO_BOX[1]), (LOGO_BOX[2], LOGO_BOX[1]), (LOGO_BOX[2], LOGO_BOX[3]), (LOGO_BOX[0], LOGO_BOX[3])]))
_hit = pcbnew.SHAPE_POLY_SET(channels)
_hit.BooleanIntersection(_txtbox)
assert area_mm2(_hit) < 0.01, f"a track channel overlaps the maker's credit or logo by {area_mm2(_hit):.3f} mm2"

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
for v in VIAS:
    if v.GetNetCode() == gnd_code:
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
    if not touches:
        print("  plain copper piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper pieces: GND", n_gnd, "plain", n_art)

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("BAT", 12.4, 37.0, 0.8, 0, False), ("SAO", 27.6, 37.0, 0.8, 0, False),
          ("CR2032 + UP", 35.65, 13.5, 0.8, 90, False), ("SAO++ rA", 35.6, 26.7, 0.9, 90, False),
          ("1", 13.0, 23.3, 0.9, 0, False),
          ("+", 3.3, 16.6, 1.4, 0, True), ("+", 6.3, 33.0, 1.4, 0, True),
          ("-", 32.7, 20.0, 1.4, 0, True), ("-", 33.5, 33.0, 1.4, 0, True)]
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
print("TP pads:", {r: mm(fp.GetPosition()) for r, fp in tp.items()})
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
