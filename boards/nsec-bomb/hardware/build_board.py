#!/usr/bin/env python3
"""Build nsec-bomb.kicad_pcb from nothing but the numbers in this file and hardware/circuit.json.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nsec-bomb/hardware/build_board.py

The circuit is NorthSec's (Sao_Bomb, NorthSec 2025, MIT): four LEDs, each with a resistor, none of them connected to
the supply until someone solders a wire from a supply point to that LED's point; cut the wire and the LED goes out.

The drawing is SAO++'s own. NorthSec's outline and front art were traced over a third-party picture of unknown
origin, so none of it is used: this script does not read anything from original/, and every line of the outline and
art below is generated from the numbers in the ART section.

  - three sticks of dynamite stacked flat, the top and bottom ones 3 mm longer at each end than the middle one
  - two white bands of tape, "TNT" on the top stick, "DANGER" on the bottom one
  - a timer box strapped across the middle: white frame, four corner screws, a display reading 00:07 in bare copper
  - an LED behind each end of the top and bottom sticks (the detonators), shining through a small bare window
  - eight 1.6 mm square wire pads: four "+" terminals on the timer, one numbered terminal (1-4) beside each detonator

Back: CR2032 clip on the left (front view), cell slides in from the straight top edge; SAO connector on the right;
SAO / OFF / BAT switch on the straight bottom edge; NorthSec's "nsec 2025" logo and 5 x 5 mm white square.

Coordinates in this file are millimetres from the board's top-left corner, front view (x right, y down); the board
sits at (OX, OY) on the KiCad page. The script also writes hardware/outline.json and art/nsec-bomb-front.svg.
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS, F_Mask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, add_circle, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "nsec-bomb"
LOCAL = load_local(SLUG)
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
OX, OY = 100.0, 60.0    # where the board's top-left corner sits on the KiCad page

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40        # supply tracks
THIN = 0.30         # LED tracks, front tracks
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
WINDOW = 1.62       # radius kept free of copper (both sides) around each LED centre so light gets into the board


def P(x, y):
    """Board millimetres -> KiCad point."""
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def mm(v):
    """KiCad point -> board millimetres."""
    return (round(ToMM(v.x) - OX, 3), round(ToMM(v.y) - OY, 3))


def poly(pts):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        ps.Append(FromMM(OX + x), FromMM(OY + y))
    return ps


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def rrect(x0, y0, x1, y1, r):
    """Rectangle with rounded corners."""
    return grown(rect(x0 + r, y0 + r, x1 - r, y1 - r), r)


def ring(x0, y0, x1, y1, r, w):
    """Outline of a rounded rectangle, w wide, centred on the given edges."""
    out = rrect(x0 - w / 2, y0 - w / 2, x1 + w / 2, y1 + w / 2, r + w / 2)
    out.BooleanSubtract(rrect(x0 + w / 2, y0 + w / 2, x1 - w / 2, y1 - w / 2, max(r - w / 2, 0.05)))
    return out


def disc(x, y, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(x, y), r)
    return ps


def join(*sets):
    out = pcbnew.SHAPE_POLY_SET()
    for s in sets:
        out.BooleanAdd(s)
    return out


# ================================== ART: every number of the drawing is here ==================================
W, H = 54.0, 38.0           # overall size
STICK = 12.4                # height of the top and bottom sticks; the middle one gets the rest (13.2)
SHORT = 3.5                 # the middle stick is this much shorter at each end
R_OUT, R_IN = 2.6, 1.0      # corner radius of the stick ends; fillet where a long stick meets the short one
LINE = 0.25                 # silkscreen line width for stick edges and end caps
CAP_X, CAP_MID = 6.8, 5.4   # end-cap line: distance from the stick's end (long sticks; middle stick)
BAND = (11.5, 15.0)         # left tape band, x from..to; the right one mirrors it
TIMER = (16.5, 10.0, 37.5, 28.0)        # timer box (x0, y0, x1, y1), frame 0.5 wide, corner radius 1.2
DISPLAY = (19.9, 13.4, 34.1, 24.6)      # display frame inside it, 0.3 wide
DIGITS = "00:07"            # what the display reads, in bare copper
DIG_W, DIG_H, DIG_T = 2.2, 6.4, 0.6     # one digit: width, height, stroke
LED_Y = (6.2, 31.8)         # centre line of the top and bottom sticks: LEDs and numbered terminals sit on it
LED_X = 3.6                 # LED centre, from each end
TERM_X = 9.0                # numbered terminal pad, from each end
PLUS_X, PLUS_Y = 18.2, (14.5, 23.5)     # "+" terminal pads on the timer: x from each side of the board, two rows

body = join(rrect(0, 0, W, STICK, R_OUT), rrect(0, H - STICK, W, H, R_OUT), rect(SHORT, STICK / 2, W - SHORT, H - STICK / 2))
body = grown(grown(body, R_IN), -R_IN)          # rounds the four inside corners where the sticks meet
body.Simplify()
_b = bbox_mm(body)
assert abs(_b[2] - _b[0] - W) < 0.02 and abs(_b[3] - _b[1] - H) < 0.02 and body.OutlineCount() == 1 and body.HoleCount(0) == 0
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)
silk_ok = grown(body, -0.3)                     # silkscreen stops 0.3 mm short of the edge

silk = pcbnew.SHAPE_POLY_SET()
for y in (STICK, H - STICK):                    # the two lines between the sticks, broken by the bands and the timer
    for x0, x1 in ((SHORT + 0.4, BAND[0]), (BAND[1], TIMER[0]), (TIMER[2], W - BAND[1]), (W - BAND[0], W - SHORT - 0.4)):
        silk.BooleanAdd(rect(x0, y - LINE / 2, x1, y + LINE / 2))
for x in (CAP_X, W - CAP_X):                    # end caps of the long sticks
    silk.BooleanAdd(rect(x - LINE / 2, 0, x + LINE / 2, STICK))
    silk.BooleanAdd(rect(x - LINE / 2, H - STICK, x + LINE / 2, H))
for x in (SHORT + CAP_MID, W - SHORT - CAP_MID):  # end caps of the middle stick
    silk.BooleanAdd(rect(x - LINE / 2, STICK, x + LINE / 2, H - STICK))
for x0, x1 in (BAND, (W - BAND[1], W - BAND[0])):  # the tape
    silk.BooleanAdd(rect(x0, 0, x1, H))
silk.BooleanAdd(ring(*TIMER, 1.2, 0.5))
silk.BooleanAdd(ring(*DISPLAY, 0.6, 0.3))
for sx in (DISPLAY[0] + 1.1, DISPLAY[2] - 1.1):     # four screws (small rings) above and below the display
    for sy in (TIMER[1] + 1.7, TIMER[3] - 1.7):
        screw = disc(sx, sy, 0.75)
        screw.BooleanSubtract(disc(sx, sy, 0.45))
        silk.BooleanAdd(screw)
silk.BooleanIntersection(silk_ok)
silk.Simplify()

# the display digits: seven-segment shapes
SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
       "8": "abcdefg", "9": "abcdfg"}


def digit(ch, x, y):
    w, h, t = DIG_W, DIG_H, DIG_T
    seg = {"a": (0, 0, w, t), "g": (0, (h - t) / 2, w, (h + t) / 2), "d": (0, h - t, w, h),
           "f": (0, 0, t, h / 2 + t / 2), "e": (0, h / 2 - t / 2, t, h), "b": (w - t, 0, w, h / 2 + t / 2), "c": (w - t, h / 2 - t / 2, w, h)}
    return join(*[rect(x + a, y + b, x + c, y + d) for a, b, c, d in (seg[s] for s in SEG[ch])])


_gap, _colon = 0.7, 0.6
_wide = sum(DIG_W if c != ":" else _colon for c in DIGITS) + _gap * (len(DIGITS) - 1)
_x = (DISPLAY[0] + DISPLAY[2]) / 2 - _wide / 2
_y = (DISPLAY[1] + DISPLAY[3]) / 2 - DIG_H / 2
digits = pcbnew.SHAPE_POLY_SET()
for c in DIGITS:
    if c == ":":
        digits.BooleanAdd(rect(_x, _y + 1.7, _x + _colon, _y + 1.7 + _colon))
        digits.BooleanAdd(rect(_x, _y + DIG_H - 1.7 - _colon, _x + _colon, _y + DIG_H - 1.7))
        _x += _colon + _gap
    else:
        digits.BooleanAdd(digit(c, _x, _y))
        _x += DIG_W + _gap
digits.Simplify()
assert _y - DISPLAY[1] > 0.9 and (DISPLAY[2] - DISPLAY[0] - _wide) / 2 > 0.9, "digits too close to the display frame"

# front lettering: (text, x, y, height, stroke)
FRONT_TEXT = [("TNT", W / 2, 5.0, 4.4, 0.75), ("DANGER", W / 2, 32.4, 2.6, 0.45),
              ("+", PLUS_X, 19.0, 1.5, 0.3), ("+", W - PLUS_X, 19.0, 1.5, 0.3),
              ("1", TERM_X, LED_Y[0] - 2.6, 1.4, 0.25), ("2", W - TERM_X, LED_Y[0] - 2.6, 1.4, 0.25),
              ("3", TERM_X, LED_Y[1] + 2.6, 1.4, 0.25), ("4", W - TERM_X, LED_Y[1] + 2.6, 1.4, 0.25)]

# ================================== PLACEMENT (board mm, front view) ==========================================
BAT = (16.5, 15.0)          # clip centre: cell x 6.5..26.5, y 5..25; it slides in 5 mm from the straight top edge
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down
CONN = (37.5, 19.0)         # connector: mid-height, 10.5 mm right of centre, shroud 8.8 mm from the right edge; key slot up
SW_X = W / 2                # switch in the middle of the straight bottom edge, knob down
# LEDs lie along their sticks. ref -> (centre, which way the anode pad points: -1 = left, +1 = right)
LEDS = {"D1": ((LED_X, LED_Y[0]), -1), "D3": ((W - LED_X, LED_Y[0]), +1),
        "D2": ((LED_X, LED_Y[1]), -1), "D4": ((W - LED_X, LED_Y[1]), +1)}
R_DY = 3.1                  # each resistor sits this far from its LED, toward the middle of the board
RES = {"R1": "D1", "R2": "D2", "R3": "D3", "R4": "D4"}
# wire pads: ref -> (centre, net)
WIRE = {"J2": ((PLUS_X, PLUS_Y[0]), "VLOAD"), "J4": ((W - PLUS_X, PLUS_Y[0]), "VLOAD"),
        "J6": ((PLUS_X, PLUS_Y[1]), "VLOAD"), "J8": ((W - PLUS_X, PLUS_Y[1]), "VLOAD"),
        "J3": ((TERM_X, LED_Y[0]), "CONN1"), "J7": ((W - TERM_X, LED_Y[0]), "CONN2"),
        "J5": ((TERM_X, LED_Y[1]), "CONN3"), "J9": ((W - TERM_X, LED_Y[1]), "CONN4")}
VIA_DX = 1.0                # each numbered terminal's via: this far toward the stick's end, level with the resistor
VIA_LOAD = (SW_X - 1.5, 28.0)   # switched supply up to the front, hidden under the bottom line of the timer's frame
LOGO_TO = (31.0, 1.2)       # top-left corner of NorthSec's logo on the back (above the connector)
BOX = (38.5, 26.6, 5.0)     # NorthSec's 5 x 5 mm white square on the back

# ---- the board ----------------------------------------------------------------------------------
board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
TRACKS = []

CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p["ref"]: p for p in CIRCUIT["parts"]}
PADNETS = {r: p.get("nets", {}) for r, p in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for r, p in PARTS.items()}
_NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")          # same namespace as tools/gen_schematic.py
for r, (_, net) in WIRE.items():
    assert PADNETS[r] == {"1": net}, r
for r, d in RES.items():
    assert PADNETS[r]["2"] == PADNETS[d]["2"], (r, d)


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
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
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

SW_Y = H - PAD_EDGE - 1.83                                          # outer solder tabs PAD_EDGE inside the bottom edge
sw = place("SW1", (SW_X, SW_Y), ("1", (SW_X + 3.0, SW_Y - 1.43)))   # pins up; pin 1 (badge) lands right, pin 4 (cell) left
assert abs(padpos(sw, "4")[0] - (SW_X - 3.0)) < 0.01 and padpos(sw, "4")[1] < SW_Y
_kb = [g for g in sw.GraphicalItems() if g.GetLayer() == pcbnew.Dwgs_User][0].GetBoundingBox()
KNOB_TIP = ToMM(_kb.GetBottom()) - OY
assert ToMM(_kb.GetTop()) - OY > SW_Y, "knob is not pointing down"
print(f"switch centre y {SW_Y:.3f}; knob tip {KNOB_TIP - H:.2f} mm past the straight bottom edge")

leds, res, VIA_CONN = {}, {}, {}
for r, ((x, y), out) in LEDS.items():
    leds[r] = place(r, (x, y), ("2", (x + 1.55 * out, y)))              # anode at the stick's end, cathode inboard
for r, d in RES.items():
    (x, y), out = LEDS[d]
    ry = y + (R_DY if y < H / 2 else -R_DY)
    res[r] = place(r, (x, ry), ("2", (x + 0.825 * out, ry)))            # pad 2 (LED side) under the LED's anode
    j = [k for k in WIRE if WIRE[k][1] == PADNETS[r]["1"]][0]
    VIA_CONN[j] = (WIRE[j][0][0] + VIA_DX * out, ry)

wire = {}
for r, (at, net) in WIRE.items():                                       # on the FRONT: bare copper, nothing fitted
    fp = load(r, at, back=False)
    link(fp, r)
    fp.Value().SetVisible(False)
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    wire[r] = fp

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = mm(fab[0].GetBoundingBox().GetCenter())         # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(c[1] - BAT[1], c[0] - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot)
link(bat, "BT1")
_sb = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
print("battery clip angle", _rot, "; clip body (fab outline) x %.2f..%.2f y %.2f..%.2f"
      % (ToMM(_sb.GetLeft()) - OX, ToMM(_sb.GetRight()) - OX, ToMM(_sb.GetTop()) - OY, ToMM(_sb.GetBottom()) - OY))

# NorthSec's logo (their back-of-board footprint, unchanged; a copy is in the local library)
logo = pcbnew.FootprintLoad(LOCAL_LIB, "nsec-2025")
board.Add(logo)
logo.SetPosition(P(0, 0))
logo.Flip(P(0, 0), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)


def _silk_box(fp):
    ps = pcbnew.SHAPE_POLY_SET()
    for g in fp.GraphicalItems():
        if g.GetLayer() == B_SilkS:
            b = g.GetBoundingBox()
            x0, y0, x1, y1 = ToMM(b.GetLeft()) - OX, ToMM(b.GetTop()) - OY, ToMM(b.GetRight()) - OX, ToMM(b.GetBottom()) - OY
            ps.Append(rect(x0, y0, x1, y1))
    b = bbox_mm(ps)
    return (b[0] - OX, b[1] - OY, b[2] - OX, b[3] - OY)


_lb0 = _silk_box(logo)
logo.SetPosition(P(LOGO_TO[0] - _lb0[0], LOGO_TO[1] - _lb0[1]))
logo.SetFPID(pcbnew.LIB_ID(SLUG + "-local", "nsec-2025"))
logo.Reference().SetVisible(False)
logo.SetAttributes(logo.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
LOGO_BOX = _silk_box(logo)
print("logo on the back: x %.2f..%.2f y %.2f..%.2f" % (LOGO_BOX[0], LOGO_BOX[2], LOGO_BOX[1], LOGO_BOX[3]))

# every pad sits on the board, PAD_EDGE inside the edge
for fp in board.GetFootprints():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu if pad.IsOnLayer(B_Cu) else F_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"


# ---- routing ------------------------------------------------------------------------------------
def route(net, pts, width=TRACK, clear=CLEAR, layer=B_Cu):
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
        if layer == B_Cu:
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

# badge 3.3 V: connector pin 1 -> up off the end of its pad -> left -> down between the clip and the connector -> switch pin 1
VSAO_X = 29.1
route("VSAO", [j1, (j1[0], CONN[1] - 6.3), (VSAO_X + 0.5, CONN[1] - 6.3), (VSAO_X, CONN[1] - 5.8), (VSAO_X, s1[1] - 2.4),
               (s1[0], s1[1] - 1.5), s1], width=THIN)

# coin cell: the clip joins its two solder tabs itself; this link round the closed end (under the clip, outside the
# cell) makes the board agree without relying on it. A branch drops from it to switch pin 4.
bt = sorted(mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1")
_r = math.hypot(bt[0][0] - BAT[0], bt[0][1] - BAT[1])
_deg = list(range(180, -1, -5))
arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in _deg]
assert all(y >= BAT[1] - 0.01 for _, y in arc), "pad link is on the open side of the clip"
route("VBAT", [bt[0]] + arc[1:-1] + [bt[1]])
_drop = arc[_deg.index(45)]
route("VBAT", [_drop, (s4[0], _drop[1] + abs(s4[0] - _drop[0])), s4], width=THIN)

# switched supply: switch pin 3 -> via -> front -> along under the timer frame's bottom line -> up each side of the timer to its "+" pads
route("VLOAD", [s3, VIA_LOAD], width=THIN)
via("VLOAD", VIA_LOAD)
w = {r: WIRE[r][0] for r in WIRE}
route("VLOAD", [VIA_LOAD, (w["J6"][0], VIA_LOAD[1]), w["J6"], w["J2"]], width=THIN, layer=F_Cu)
route("VLOAD", [VIA_LOAD, (w["J8"][0], VIA_LOAD[1]), w["J8"], w["J4"]], width=THIN, layer=F_Cu)

# each numbered terminal -> via beside it -> resistor -> LED anode (cathode straight into the GND copper)
for r, d in RES.items():
    j = [k for k in VIA_CONN if PADNETS[k]["1"] == PADNETS[r]["1"]][0]
    net = PADNETS[j]["1"]
    route(net, [w[j], VIA_CONN[j]], width=THIN, layer=F_Cu)
    via(net, VIA_CONN[j])
    route(net, [VIA_CONN[j], padpos(res[r], "1")], width=THIN)
    route(PADNETS[r]["2"], [padpos(res[r], "2"), padpos(leds[d], "2")], width=THIN)

# ---- front art ----------------------------------------------------------------------------------
windows = pcbnew.SHAPE_POLY_SET()                      # bare board in front of each LED: 3.2 x 1.6 mm, along the stick
for (x, y), _ in LEDS.values():
    windows.BooleanAdd(rrect(x - 1.6, y - 0.8, x + 1.6, y + 0.8, 0.4))
add_filled(board, windows, F_Mask)
add_filled(board, digits, F_Cu)                        # the display digits: copper, no net, no solder mask over them
add_filled(board, grown(digits, 0.05), F_Mask)
add_filled(board, silk, F_SilkS)

SVG_TEXT = pcbnew.SHAPE_POLY_SET()


def text(txt, x, y, size, layer, thick=None, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick if thick else size * 0.15))
    t.SetMirrored(layer == B_SilkS)
    t.SetTextAngleDegrees(rot)
    board.Add(t)
    if layer == F_SilkS:
        t.TransformTextToPolySet(SVG_TEXT, 0, ERR, pcbnew.ERROR_INSIDE)


for txt, x, y, size, thick in FRONT_TEXT:
    text(txt, x, y, size, F_SilkS, thick)

# no front copper near an LED or across the display; the lettering stays clear of the art lines and of bare copper
keep = pcbnew.SHAPE_POLY_SET()
for (x, y), _ in LEDS.values():
    keep.BooleanAdd(disc(x, y, WINDOW))
keep.BooleanAdd(rect(DISPLAY[0] - 0.3, DISPLAY[1] - 0.3, DISPLAY[2] + 0.3, DISPLAY[3] + 0.3))
for t in board.GetTracks():
    if t.GetLayer() == F_Cu or t.Type() == pcbnew.PCB_VIA_T:
        ps = pcbnew.SHAPE_POLY_SET()
        t.TransformShapeToPolygon(ps, F_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
        ps.BooleanIntersection(keep)
        assert area_mm2(ps) < 1e-6, f"front copper at {mm(t.GetStart())} is inside an LED window or the display"
front_bare = join(windows, grown(digits, 0.05))
for fp in wire.values():
    for pad in fp.Pads():
        front_bare.BooleanAdd(pad_poly(pad, F_Cu, 0.05))
_hit = pcbnew.SHAPE_POLY_SET(SVG_TEXT)
_hit.BooleanIntersection(grown(silk, 0.15))
assert area_mm2(_hit) < 1e-4, f"front lettering touches the art lines ({area_mm2(_hit):.3f} mm2)"
_hit = join(SVG_TEXT, silk)
_hit.BooleanIntersection(front_bare)
assert area_mm2(_hit) < 1e-4, f"front silkscreen overlaps bare copper or an LED window ({area_mm2(_hit):.3f} mm2)"

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
for (x, y), _ in LEDS.values():
    add_circle(cut, P(x, y), WINDOW)
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
    else:                                              # an island that reaches no GND pad would only be loose copper
        b = bbox_mm(piece)
        print("  dropped loose copper piece, mm2:", round(area_mm2(piece), 2), "at", [round(b[0] - OX, 1), round(b[1] - OY, 1)])
    n_gnd += touches
    n_art += not touches
print("back copper pieces: GND", n_gnd, "dropped", n_art)

# ---- back silkscreen ------------------------------------------------------------------------------
s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)       # NorthSec's white square, same size
s.SetStart(P(BOX[0], BOX[1]))
s.SetEnd(P(BOX[0] + BOX[2], BOX[1] + BOX[2]))
s.SetLayer(B_SilkS)
s.SetFilled(True)
s.SetWidth(FromMM(0.1))
board.Add(s)
for txt, x, y, size in [("BAT", s4[0] - 1.3, 32.5, 0.8), ("OFF", SW_X, 32.5, 0.8), ("SAO", s1[0] + 1.3, 32.5, 0.8),
                        ("CR2032 + UP", BAT[0], 1.4, 0.9), ("1", j1[0] - 1.9, CONN[1] - 7.6, 0.9),
                        ("BOMB  SAO++ rA", 41.0, 33.5, 0.8), ("circuit: NorthSec", 41.0, 35.0, 0.8),
                        ("2025 (MIT)", 41.0, 36.5, 0.8)]:
    text(txt, x, y, size, B_SilkS)


# ---- art/nsec-bomb-front.svg and hardware/outline.json: the drawing, from the same shapes ---------------
def svg_path(ps):
    d = []
    for i in range(ps.OutlineCount()):
        for chain in [ps.Outline(i)] + [ps.Hole(i, h) for h in range(ps.HoleCount(i))]:
            pts = [mm(chain.CPoint(k)) for k in range(chain.PointCount())]
            d.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in pts) + "Z")
    return " ".join(d)


pads_front = pcbnew.SHAPE_POLY_SET()
for fp in wire.values():
    for pad in fp.Pads():
        pads_front.BooleanAdd(pad_poly(pad, F_Cu))
    for g in fp.GraphicalItems():
        if g.GetLayer() == F_SilkS:
            g.TransformShapeToPolygon(SVG_TEXT, F_SilkS, 0, ERR, pcbnew.ERROR_INSIDE)
holes = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(holes, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2)
os.makedirs(os.path.join(HERE, "..", "art"), exist_ok=True)
with open(os.path.join(HERE, "..", "art", SLUG + "-front.svg"), "w", encoding="utf-8") as f:
    f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 {W + 2:g} {H + 3:g}" width="{(W + 2) * 10:g}" height="{(H + 3) * 10:g}">\n'
            '<!-- SAO++ time bomb, front art. Drawn by boards/nsec-bomb/hardware/build_board.py (edit the ART numbers there,\n'
            '     not this file). Units: mm. (c) SAO++ contributors, CC-BY-SA-4.0. -->\n')
    for name, ps, fill in (("board (solder mask)", body, "#a3211c"), ("bare board in front of each LED", windows, "#d8c9a0"),
                           ("bare copper: wire pads and display digits", join(pads_front, digits), "#e2b842"),
                           ("silkscreen art", silk, "#ffffff"), ("silkscreen lettering and pad corner marks", SVG_TEXT, "#ffffff"),
                           ("holes: switch locating pegs", holes, "#000000")):
        f.write(f'<path fill="{fill}" fill-rule="evenodd" d="{svg_path(ps)}"><title>{name}</title></path>\n')
    f.write("</svg>\n")
json.dump({"outer": [list(mm(body.Outline(0).CPoint(k))) for k in range(body.Outline(0).PointCount())], "holes": [],
           "origin_on_page_mm": [OX, OY]}, open(os.path.join(HERE, "outline.json"), "w"))

# ---- report -------------------------------------------------------------------------------------
print("outline points:", body.Outline(0).PointCount(), "; board area mm2: %.0f" % area_mm2(body))
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("LED anodes:", {r: padpos(fp, "2") for r, fp in leds.items()})
print("vias:", [(v.GetNetname(), mm(v.GetPosition())) for v in VIAS])
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
