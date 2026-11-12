#!/usr/bin/env python3
"""Rebuild sao-modem.kicad_pcb from hamster's KiCad 6 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-modem/hardware/build_board.py

What the original is (read from the maker's board, schematic and BOM spreadsheet)
  - a 43.9 x 21.5 mm board shaped like a US Robotics Courier external modem, 1.2 mm thick. The front is silkscreen
    line art, a strip of bare board where the six lights glow through, bare-copper "3" and "0" in "D3F C0N", and
    eight bare-copper squares (the DIP switches). No brand name or logo is on the board.
  - on the back: a through-hole 2x3 SAO header at the foot; six red right-angle LEDs (Lite-On LTST-S220KRKT), each
    with a 47 ohm resistor to ground; one dual P-channel MOSFET (Diodes Inc. DMP3085LSD-13, SOIC-8); a 4.7 k and a
    10 k gate resistor; a 2 mm pad for the SYN light.
      AA  = badge 3.3 V -> LED -> 47 ohm -> GND (always on)
      OH  = 3.3 V -> MOSFET half 2 -> LED -> 47 ohm -> GND, gate on SCL through 4.7 k: lit while SCL is LOW
      SD  = 3.3 V -> MOSFET half 1 -> LED -> 47 ohm -> GND, gate on SDA through 10 k:  lit while SDA is LOW
      RTS = GPIO1 -> LED -> 47 ohm -> GND (the badge's pin drives the LED directly), CTS the same from GPIO2
      SYN = the pad -> LED -> 47 ohm -> GND

What this script does
  - enlarges the maker's whole design 2.0 times (outline.json, the three art footprints, the two back texts). That is
    the smallest size at which the shared CR2032 clip fits clear of the row of six lights (see README).
  - cuts the 2022 parts, tracks, vias, pours and window keep-outs out of the file text (KiCad 10's Python crashes on
    Remove()) and places the SAO++ parts on the back: connector in the foot, switch on the top edge, cell clip on the
    right (the cell slides in from the right edge), six reverse-mount red LEDs behind the maker's window strip, the
    maker's MOSFET and gate resistors, and the series cell diode.
  - routes everything on the back copper, with no vias: four of the LED resistors sit on the supply side of their LED
    and double as bridges (another track passes between their two pads).
  - back copper: GND, cleared around everything that is not GND and around each LED's light path.

Coordinates are millimetres in KiCad's front view (x grows right, y grows down); (0, 0) is the top-left corner of the
board's bounding box.
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
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks, bbox_mm,  # noqa: E402
                         add_filled, pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "sao-modem"
SRC = os.path.join(HERE, "..", "original", "modem", "modem.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

K = 2.0                     # enlargement of the maker's design (must match make_outline.py)
X0, Y0 = 129.88, 49.26      # top-left of the maker's outline in his file; becomes (0, 0)

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks in open board
THIN = 0.25         # tracks that pass between pads
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
LED_CLEAR = 1.62    # no copper this close to an LED's centre (the light goes through the board there)
WINDOW = (2.86, 1.55)   # half-size of the maker's copper-free window behind each light (1.43 x 0.775 mm, enlarged)
WINDOW_LEFT = {"D5": 46.0}   # CTS: the window stops 1.06 mm short on its left, where the only ground copper that
#                              reaches the connector's ground pin passes between the SDA track and this light


def S(x, y):
    """A point of the maker's board, in this board's coordinates."""
    return (round((x - X0) * K, 4), round((y - Y0) * K, 4))


# ---- placement (front view) -------------------------------------------------------------------
# The six lights: centres of the maker's six window keep-outs (his LEDs sat 1.5 mm above them and shone sideways).
LED_Y = S(0, 59.925)[1]
LED_X = {"D1": S(135.73, 0)[0], "D2": S(140.02, 0)[0], "D3": S(144.33, 0)[0],
         "D4": S(149.29, 0)[0], "D5": S(153.78, 0)[0], "D6": S(158.23, 0)[0]}
LED_NAME = {"D1": "AA", "D2": "OH", "D3": "SD", "D4": "RTS", "D5": "CTS", "D6": "SYN"}

CONN = (44.25, 33.0)        # in the foot, as on the original (his header centre scales to 43.94, 35.72); key slot up
VX = CONN[0] - 2.54         # the badge-supply track runs straight up this line from connector pin 1 to the switch
SW_X = VX + 3.0             # switch on the flat top edge, knob up; its pin 1 lands exactly on that line
BAT = (71.2, 19.9)          # clip centre; open end to the right: the cell slides in from the right-hand edge
BAT_OPEN = (1.0, 0.0)
Q1_AT = (46.0, 12.4)
R_AT = {                    # resistor centres; "h" = pads left / right, "v" = pads above / below
    "R1": ((VX, 6.1), "h"),             # AA, supply side: bridges the badge-supply track
    "R3": ((VX, 8.2), "h"),             # SD, supply side: bridge
    "R2": ((VX, 10.3), "h"),            # OH, supply side: bridge
    "R5": ((54.0, 36.4), "h"),          # CTS, supply side: bridges the GPIO1 track
    "R4": ((LED_X["D4"] - 1.55, 18.3), "v"),   # RTS, ground side, above the LED's cathode pad
    "R6": ((LED_X["D6"] - 1.55, 18.3), "v"),   # SYN, ground side
    "R7": ((42.98, 19.3), "v"),         # SCL gate resistor (4.7 k), in the gap between RTS and CTS
    "R8": ((44.55, 19.3), "v"),         # SDA gate resistor (10 k)
}
D7_AT = (56.4, 5.1)         # cell diode, between the clip and the switch
TP1_AT = (57.9, 26.8)       # the maker's SYN pad, below the SYN light
GPIO1_E, GPIO1_S, GPIO1_W = 54.0, 41.0, 40.3   # GPIO1 goes round the connector: east side, south side, west side

# ---- cut the 2022 electrical parts out of the file text, and enlarge the art ----------------------
_txt = open(SRC, encoding="utf-8").read()
_cut, _gone, _art = [], [], []
for a_, b_ in blocks(_txt, "footprint"):
    name = re.match(r'\n  \(footprint "([^"]+)"', _txt[a_:b_]).group(1)
    if name in ("lib_fp:copper", "lib_fp:silkscreen", "lib_fp:mask"):
        _art.append((a_, b_, name))
    else:
        _cut.append((a_, b_))
        _gone.append(name)
assert len(_art) == 3 and len(_gone) == 19, (len(_art), _gone)     # header, 6 LEDs, 8 resistors, MOSFET, pad, 2 panel tabs
for kind, n in (("segment", 122), ("arc", 75), ("via", 4), ("zone", 13), ("gr_curve", 42), ("gr_line", 40), ("gr_arc", 6)):
    found = list(blocks(_txt, kind))
    assert len(found) == n, (kind, len(found))
    _cut += found           # tracks, vias, the pour and the 12 window keep-outs, the outline curves, fab-layer sketches
_texts = list(blocks(_txt, "gr_text"))
assert len(_texts) == 2
_cut += _texts              # re-added below, enlarged
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n  \(net [1-9]\d* "[^"]*"\)', _txt)]


def _scaled_art(block):
    """One of the maker's three art footprints, enlarged K times about the board's top-left corner."""
    m = re.search(r"\n    \(at ([-0-9.]+) ([-0-9.]+)\)", block)
    x, y = S(float(m.group(1)), float(m.group(2)))
    block = block[:m.start()] + f"\n    (at {x} {y})" + block[m.end():]
    return re.sub(r"\(xy ([-0-9.]+) ([-0-9.]+)\)",
                  lambda q: f"(xy {float(q.group(1)) * K:.6f} {float(q.group(2)) * K:.6f})", block)


_edits = sorted([(a_, b_, "") for a_, b_ in _cut] + [(a_, b_, _scaled_art(_txt[a_:b_])) for a_, b_, _ in _art], reverse=True)
for a_, b_, new in _edits:
    _txt = _txt[:a_] + new + _txt[b_:]
_txt = _txt.replace("(thickness 1.2)", "(thickness 1.6)", 1).replace("(thickness 1.11)", "(thickness 1.51)", 1)
_tmp = os.path.join(tempfile.mkdtemp(), "modem.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []
for fp in board.GetFootprints():
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# ---- outline: the maker's 42 curves, enlarged, as one polygon (make_outline.py) --------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
_bb = bbox_mm(body)
assert abs(_bb[2] - 43.85 * K) < 0.1 and abs(_bb[3] - 21.51 * K) < 0.1, _bb
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)

# nothing of the enlarged art may fall outside the outline (the maker's silkscreen outline line sits on the edge itself)
for fp in board.GetFootprints():
    for it in fp.GraphicalItems():
        if hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY and it.GetLayer() != pcbnew.F_SilkS:
            out_ = pcbnew.SHAPE_POLY_SET(it.GetPolyShape())
            out_.BooleanSubtract(body)
            assert area_mm2(out_) < 0.01, "art outside the outline on " + board.GetLayerName(it.GetLayer())

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
    fp.SetFPID(pcbnew.LIB_ID(fpid.split(":")[0], fpid.split(":")[1]))
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
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    fp.Value().SetVisible(False)
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


def pp(fp, num):
    """Centre of pad `num` (the first one, if several share the number)."""
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


def pbox(fp, num):
    """(left, top, right, bottom) of pad `num` in mm."""
    pad = [p for p in fp.Pads() if p.GetNumber() == num][0]
    return bbox_mm(pad_poly(pad, B_Cu))


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
assert pp(conn, "5") == (CONN[0] + 2.54, CONN[1] - 3.4) and pp(conn, "2") == (CONN[0] - 2.54, CONN[1] + 3.4)

# switch on the flat top edge: outer solder tabs PAD_EDGE inside the edge, knob sticking out of the top
def _top_at(x):
    """y of the board's top edge above x."""
    pts = _ol["outer"]
    ys = [a[1] + (x - a[0]) * (b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(pts, pts[1:] + pts[:1]) if (a[0] - x) * (b[0] - x) < 0]
    return min(ys)


_top = max(_top_at(SW_X + dx) for dx in (-6, -3, 0, 3, 6))
assert _top - min(_top_at(SW_X + dx) for dx in (-6, -3, 0, 3, 6)) < 0.03, "top edge is not straight at the switch"
SW_Y = _top + PAD_EDGE + 1.83
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X - 3.0, SW_Y + 1.43)))    # pins toward the board; pin 1 (badge) lands left
assert abs(pp(sw, "4")[0] - (SW_X + 3.0)) < 0.01 and abs(pp(sw, "3")[0] - (SW_X + 1.5)) < 0.01
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetTop())
assert ToMM(_kb.GetBottom()) < SW_Y, "knob is not pointing up"
print(f"switch centre ({SW_X:.2f}, {SW_Y:.2f}); knob tip {_top - KNOB_TIP:.2f} mm past the top edge")

leds = {r: place(r, (x, LED_Y), ("2", (x + 1.55, LED_Y))) for r, x in LED_X.items()}     # anode on the right
res = {}
for r, ((x, y), way) in R_AT.items():
    res[r] = place(r, (x, y), ("1", (x + 0.825, y) if way == "h" else (x, y + 0.825)))   # pad 1 right, or below
q1 = place("Q1", Q1_AT, ("5", (Q1_AT[0] - 1.905, Q1_AT[1] - 2.475)))
# top row, left to right: 5 6 (drain 2), 7 8 (drain 1); bottom row: 4 (gate 2), 3 (source 2), 2 (gate 1), 1 (source 1)
assert pp(q1, "8") == (Q1_AT[0] + 1.905, Q1_AT[1] - 2.475) and pp(q1, "4") == (Q1_AT[0] - 1.905, Q1_AT[1] + 2.475)
assert pp(q1, "1") == (Q1_AT[0] + 1.905, Q1_AT[1] + 2.475)
d7 = place("D7", D7_AT, ("1", (D7_AT[0] - 0.7, D7_AT[1])))           # cathode toward the switch

# the SYN pad: bare copper, nothing to buy or place, so it is a board-only footprint (no schematic symbol), unchanged
# from KiCad's stock TestPoint_Pad_D2.0mm, the footprint the maker used
tp1 = pcbnew.FootprintLoad(LOCAL_LIB, "TestPoint_Pad_D2.0mm")
tp1.SetReference("TP1")
board.Add(tp1)
tp1.SetPosition(P(*TP1_AT))
tp1.Flip(P(*TP1_AT), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
tp1.Reference().SetVisible(False)
tp1.SetFPID(pcbnew.LIB_ID("TestPoint", "TestPoint_Pad_D2.0mm"))
tp1.SetValue("SYN pad")
tp1.Value().SetVisible(False)
tp1.SetAttributes(tp1.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
for pad in tp1.Pads():
    pad.SetNet(nets["SYN"])

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the open end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(-BAT_OPEN[1], -BAT_OPEN[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
link(bat, "BT1")
BAT_ANGLE = _rot - 0.1      # set at the end of this block: KiCad 10 reports the clip's courtyard as "malformed" at an
#                             exact right angle (see CLAUDE.md; Lumpy does the same). 0.1 degree moves a pad 0.02 mm
_strap = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
STRAP = (ToMM(_strap.GetLeft()), ToMM(_strap.GetTop()), ToMM(_strap.GetRight()), ToMM(_strap.GetBottom()))
assert abs(STRAP[0] - (BAT[0] - 11.05)) < 0.1 and abs(STRAP[2] - (BAT[0] + 4.35)) < 0.1, STRAP   # closed end on the left
print("battery clip angle", _rot, "; clip body x %.2f..%.2f y %.2f..%.2f" % (STRAP[0], STRAP[2], STRAP[1], STRAP[3]))
_strap_ps = poly([(STRAP[0], STRAP[1]), (STRAP[2], STRAP[1]), (STRAP[2], STRAP[3]), (STRAP[0], STRAP[3])])
_strap_ps.BooleanSubtract(pad_ok)
assert area_mm2(_strap_ps) < 0.001, "the clip body is not on the board"
_cell = pcbnew.SHAPE_POLY_SET()
add_circle(_cell, P(*BAT), 10.05)
_cell.BooleanSubtract(body)
assert area_mm2(_cell) < 0.001, "the cell overhangs the board"
# the clip's own silkscreen ('+' and the insertion arrow, which lands off the board) moves to the fab layer; the board
# gets its own labels below
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)
bat.SetOrientationDegrees(BAT_ANGLE)

NEW = set(PARTS) | {"TP1"}
for fp in board.GetFootprints():
    if fp.GetReference() in NEW:
        for pad in fp.Pads():
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
# each LED sits inside the maker's (enlarged) window: the long bare strip on the front
_mask = [it for fp in board.GetFootprints() for it in fp.GraphicalItems()
         if hasattr(it, "GetShape") and it.GetShape() == pcbnew.SHAPE_T_POLY and it.GetLayer() == pcbnew.F_Mask]
_strip = max(_mask, key=lambda it: it.GetBoundingBox().GetWidth()).GetBoundingBox()
for r, x in LED_X.items():
    assert ToMM(_strip.GetLeft()) + 1.5 < x < ToMM(_strip.GetRight()) - 1.5 and ToMM(_strip.GetTop()) + 0.9 < LED_Y < ToMM(_strip.GetBottom()) - 0.9, r
print("window strip on the front: x %.2f..%.2f y %.2f..%.2f; LEDs at y %.2f, x %s" % (
    ToMM(_strip.GetLeft()), ToMM(_strip.GetRight()), ToMM(_strip.GetTop()), ToMM(_strip.GetBottom()), LED_Y, sorted(LED_X.values())))


# ---- routing (back copper only, no vias) -----------------------------------------------------------
def route(net, pts, width=THIN, clear=CLEAR):
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


j = {n: pp(conn, n) for n in "123456"}
s1, s3, s4 = pp(sw, "1"), pp(sw, "3"), pp(sw, "4")
r = {name: (pp(fp, "1"), pp(fp, "2")) for name, fp in res.items()}       # (pad 1, pad 2) centres
la = {name: pp(fp, "2") for name, fp in leds.items()}                    # LED anodes (right pads)
lk = {name: pp(fp, "1") for name, fp in leds.items()}                    # LED cathodes (left pads)
PIN_BOTTOM = pbox(sw, "1")[3]
ROW_CELL = round(PIN_BOTTOM + 0.85, 3)        # cell supply leaves the switch along this row
assert abs(D7_AT[1] - ROW_CELL) < 0.3, (D7_AT, ROW_CELL)
assert abs(s1[0] - VX) < 0.005 and abs(j["1"][0] - VX) < 0.005

# badge 3.3 V: connector pin 1 straight up to switch pin 1, between the pads of R2, R3 and R1 and between RTS and CTS
route("VSAO", [j["1"], s1])
for name in ("R1", "R2", "R3"):
    assert abs(r[name][0][1] - r[name][1][1]) < 0.01 and r[name][1][0] < VX < r[name][0][0], name

# switched supply: switch pin 3 -> R1 (AA); -> round the right of the transistor to its two sources
Y1 = r["R1"][0][1]
q = {n: pp(q1, n) for n in "12345678"}
VL_X = Q1_AT[0] + 4.2
route("VLOAD", [s3, (s3[0], Y1), r["R1"][0]], width=TRACK)
route("VLOAD", [(s3[0], Y1), (VL_X, Y1), (VL_X, Q1_AT[1]), (q["1"][0], Q1_AT[1]), q["1"]], width=TRACK)
route("VLOAD", [(q["1"][0], Q1_AT[1]), (q["3"][0], Q1_AT[1]), q["3"]])
# AA: R1 -> west above everything -> down to the AA light
route("AA_A", [r["R1"][1], (24.5, Y1), (24.5, 15.0), (la["D1"][0], 15.0), la["D1"]])
# SD: transistor drain 1 (pins 7, 8) -> R3 -> west -> down onto the SD light
Y3 = r["R3"][0][1]
route("Q_SD", [q["7"], q["8"]])
route("Q_SD", [q["8"], (q["8"][0], Y3), r["R3"][0]])
route("SD_A", [r["R3"][1], (la["D3"][0], Y3), la["D3"]])
# OH: transistor drain 2 (pins 5, 6) -> R2 -> west -> down between SD and RTS -> under SD -> up into the OH light
route("Q_OH", [q["6"], q["5"], (r["R2"][0][0], q["5"][1]), r["R2"][0]])
OH_X = 34.0
route("OH_A", [r["R2"][1], (OH_X, r["R2"][1][1]), (OH_X, 24.0), (la["D2"][0], 24.0), la["D2"]])
# gates: SCL -> R7 -> gate 2 (pin 4); SDA -> R8 -> gate 1 (pin 2)
route("SCL", [j["4"], (j["4"][0], CONN[1]), (r["R7"][0][0], CONN[1]), r["R7"][0]])       # between the connector's two pad rows
route("SDA", [j["3"], (j["3"][0], 22.4), (r["R8"][0][0], 21.6), r["R8"][0]])
route("G_SCL", [r["R7"][1], (r["R7"][1][0], q["4"][1]), q["4"]])
route("G_SDA", [r["R8"][1], (r["R8"][1][0], 17.2), (q["2"][0], 17.2), q["2"]])
# RTS: GPIO1 leaves the connector to the right and goes round its south side to the RTS light (it cannot cross the
# badge-supply, SDA and SCL tracks that leave the connector upward)
route("GPIO1", [j["5"], (GPIO1_E, j["5"][1]), (GPIO1_E, GPIO1_S), (GPIO1_W, GPIO1_S), (GPIO1_W, la["D4"][1] + 1.3), la["D4"]])
route("RTS_K", [lk["D4"], r["R4"][0]])
# CTS: GPIO2 -> R5 (bridging the GPIO1 track) -> up -> the CTS light
assert abs(r["R5"][0][1] - j["6"][1]) < 0.01 and r["R5"][1][0] < GPIO1_E < r["R5"][0][0]
route("GPIO2", [j["6"], r["R5"][1]])                 # R5 pad 2 is its left pad (toward the connector), pad 1 the right one
route("CTS_A", [r["R5"][0], (r["R5"][0][0], 24.3), (la["D5"][0], 24.3), la["D5"]])
# AA, OH and SD have their cathode straight on ground: a short stub leads out of the copper-free window
# (CTS's cathode pad touches the ground copper directly)
for name in ("D1", "D2", "D3"):
    route("GND", [lk[name], (LED_X[name] - WINDOW[0] - 0.6, LED_Y)], width=TRACK)
# SYN: the pad -> the SYN light; its cathode -> R6 -> GND
route("SYN", [TP1_AT, (la["D6"][0], TP1_AT[1] - 0.6), la["D6"]])
route("SYN_K", [lk["D6"], r["R6"][0]])
# cell: clip -> diode -> switch pin 4. The clip joins its two solder tabs itself; a track round the closed end (under
# the clip, outside the cell) makes the board agree without relying on it.
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
bt.sort(key=lambda p: p[1])
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in range(270, 89, -5)]
assert all(x <= BAT[0] + 0.01 for x, _ in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]], width=TRACK)
d7a, d7k = pp(d7, "2"), pp(d7, "1")
route("VBAT", [d7a, (64.0, d7a[1]), (bt[0][0] - 2.2, bt[0][1]), bt[0]], width=TRACK)
route("VCELL", [d7k, (s4[0], d7k[1]), s4], width=TRACK)

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
for name, x in LED_X.items():                             # the maker's window behind each light, and the house keep-off
    add_circle(cut, P(x, LED_Y), LED_CLEAR)
    left = max(x - WINDOW[0], WINDOW_LEFT.get(name, 0))
    cut.Append(poly([(left, LED_Y - WINDOW[1]), (x + WINDOW[0], LED_Y - WINDOW[1]),
                     (x + WINDOW[0], LED_Y + WINDOW[1]), (left, LED_Y + WINDOW[1])]))
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    if t.GetNetCode() == gnd_code:
        continue                                          # ground stubs join the ground copper
    t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
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
n_gnd = n_art = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    touches = area_mm2(both) > 0.01
    if not touches:
        n_art += 1                                         # an island shut in between tracks (round the transistor,
        continue                                           # between the SDA and SCL tracks): left bare, not floating copper
    add_filled(board, piece, B_Cu, nets["GND"])
    n_gnd += 1
    print("  GND copper piece, mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper: GND pieces", n_gnd, "; islands left bare", n_art)
assert n_gnd == 1, "the ground copper is in more than one piece"

# ---- the maker's two back texts, enlarged -----------------------------------------------------------
TITLE_K = 1.5       # the title is enlarged 1.5 times, not 2: the switch now sits where it was, and at 2 times it is
#                     wider than any free stretch of the back


def text(txt, x, y, size, rot=0.0, layer=B_SilkS, thick=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick if thick else size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)
    return t


_title = text("SAO MODEM v1.69bis", 23.4, 12.6, 1.2 * TITLE_K, thick=0.2 * TITLE_K)          # was centred at the top
_cred = text("@hamster", *S(138.66, 64.75), 0.8 * K, rot=-23, layer=pcbnew.B_Mask, thick=0.12 * K)   # same place, as copper
for t_ in (_title, _cred):
    bb = t_.GetBoundingBox()
    box = poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))])
    _b = bbox_mm(box)
    print("maker's text '%s' at x %.1f..%.1f y %.1f..%.1f" % (t_.GetText(), _b[0], _b[2], _b[1], _b[3]))
    pads_under = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads_under.Append(pad_poly(pad, B_Cu, 0.2))
    hit = pcbnew.SHAPE_POLY_SET(box)
    hit.BooleanIntersection(pads_under)
    assert area_mm2(hit) < 0.001, "maker's text '%s' lies over a pad" % t_.GetText()
# '@hamster' is an opening in the solder mask, so it needs solid copper under it and no track through it
_cb = _cred.GetBoundingBox()
_cbox = poly([(ToMM(_cb.GetLeft()), ToMM(_cb.GetTop())), (ToMM(_cb.GetRight()), ToMM(_cb.GetTop())),
              (ToMM(_cb.GetRight()), ToMM(_cb.GetBottom())), (ToMM(_cb.GetLeft()), ToMM(_cb.GetBottom()))])
_hit = pcbnew.SHAPE_POLY_SET(_cbox)
_hit.BooleanIntersection(channels)
assert area_mm2(_hit) < 0.001, "a track runs through the maker's '@hamster'"

# ---- SAO++ back silkscreen labels ---------------------------------------------------------------
LABELS = [("SAO", SW_X - 8.4, 2.3, 1.0, 0), ("BAT", SW_X + 8.4, 2.3, 1.0, 0), ("OFF", SW_X, 5.2, 0.8, 0),
          ("CR2032  + UP", 58.2, 11.6, 1.0, 90),            # beside the clip's closed end
          ("SAO++ rA", 16.5, 26.6, 1.0, 0), ("1", 38.2, 27.2, 1.0, 0), ("SYN", 57.9, 29.2, 0.9, 0)]
for txt_, x, y, size, rot in LABELS:
    text(txt_, x, y, size, rot)

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("Q1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in q1.Pads()})
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.SetBoardThickness(FromMM(1.6))
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetDate("2026-11-11")
board.GetTitleBlock().SetCompany("SAO++")
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
