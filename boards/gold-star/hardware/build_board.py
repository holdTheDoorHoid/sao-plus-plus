#!/usr/bin/env python3
"""Build gold-star.kicad_pcb: a NEW layout of greymanhw's 2019 "Gold Star" circuit and star drawing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/gold-star/hardware/build_board.py

The maker published a schematic and one drawing (original/star.svg), never a board. extract_art.py turns the drawing
into outline.json (the maker's round outline, scaled, with a flat for the switch) and art/art.json (the star).
This script draws the board from nothing:
  front  - copper over the whole disc (ground), the maker's star opened in the solder mask so it shows as bare gold,
           ten 2 mm dots of bare board where the lights shine through; in the dark area left of the star's top point,
           covered vias and four short tracks under the solder mask where three LED lines hop over the others
  back   - SAO connector, SAO / OFF / BAT switch on the right-hand flat, CR2032 clip, the timer and counter chips and
           their parts, ten reverse-mount LEDs on a ring around the star, the tracks, ground copper everywhere else
Power, clock and the timer's nets are laid by hand (HAND, below). The ten LED lines are finished by the small grid
router written for Knight Rider (imported from that board's folder, not copied), inside this one run, with a hard
time limit; the result is the same every run. Ground is joined through the front copper by covered vias.
Set GS_DEBUG_PNG=<file> (and GS_DEBUG_CROP=x0,y0,x1,y1) to get a picture of what the router sees.
Coordinates are millimetres in KiCad's front view (x grows right, y grows down); the board centre is (0, 0).
"""
import json
import math
import os
import sys
import time
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "boards", "knight-rider", "hardware"))       # router.py lives there (see README: should move to tools/)
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402
import router  # noqa: E402
from router import B as RB, F as RF  # noqa: E402

T0 = time.time()
ROUTE_LIMIT_S = 300          # hard limit on routing; past it the script stops routing and says which nets are left

SLUG = "gold-star"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))
OUTLINE = json.load(open(os.path.join(HERE, "outline.json")))

STAR_FINISH = "gold"    # "gold": the star is bare ENIG copper (a solder-mask opening). "silk": white silkscreen, the layer the maker drew it on
CLEAR = 0.30            # copper-to-copper gap cut into the ground copper
EDGE = 0.55             # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20              # signal track width
PWR = 0.30              # supply track width
VIA_D, VIA_HOLE = 0.6, 0.3
R_LED = 21.4            # the ten LEDs sit on a circle of this radius
R_RING = 22.75          # the LEDs' shared return track runs round the outside of them at this radius
WINDOW = 1.6            # copper kept off both sides this far around each LED centre (docs/standard.md section 4)
DOT = 1.0               # radius of the bare-board dot on the front over each LED

# ---- outline and art ----------------------------------------------------------------------------
body = poly(OUTLINE["outer"])
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0 and not OUTLINE["holes"]
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm")
star = poly(ART["star"])
XF = ART["flat"]["x"]
assert ART["flat"]["side"] == 1 and abs(bx1 - XF) < 0.01

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
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
            net = f"unconnected-({ref}-{PINNAMES[ref][num]}-Pad{num})"      # KiCad's name for a pin with a no-connect flag
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def place(ref, pos, want, angles=(0, 90, 180, 270)):
    """Place a part on the back, at whichever of `angles` puts pad want[0] nearest the point want[1]."""
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    best = None
    for rot in angles:
        fp.SetOrientationDegrees(rot)
        d = min(math.hypot(ToMM(p.GetPosition().x) - want[1][0], ToMM(p.GetPosition().y) - want[1][1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.06, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- placement ----------------------------------------------------------------------------------
# Down the middle: connector (key up) above the coin cell. The cell slides in from the bottom edge.
CONN = (0.0, -8.0)
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view (as on Mad Cat)
BAT = (0.0, 9.8)
bat = place("BT1", BAT, ("1", (BAT[0] - 10.5, BAT[1])))


def _closed_dir():
    fab = [g_ for g_ in bat.GraphicalItems() if g_.GetLayer() == pcbnew.B_Fab and g_.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return ToMM(c.y) - BAT[1]


if _closed_dir() > 0:                                    # want the closed end UP (toward the connector), open end DOWN
    bat.SetOrientationDegrees(bat.GetOrientationDegrees() + 180)
assert _closed_dir() < -3, _closed_dir()

# Switch on the flat at the right-hand edge, knob pointing out to the right. Its body face sits 0.75 mm inside the flat
# (as on the other boards: the shell's solder tabs reach 0.18 mm past the face and need copper-to-edge room).
SW = (XF - 2.40, 0.0)
sw = place("SW1", SW, ("1", (SW[0] - 1.43, -3.0)))       # pin 1 (badge) is the upper pin, pin 4 (cell) the lower: asserted below
assert pp(sw, "4")[1] > 2.9 and pp(sw, "3")[1] > 1.4, "switch pin order is not badge-up / cell-down"
_knob = [g_ for g_ in sw.GraphicalItems() if g_.GetLayer() == pcbnew.B_Fab and g_.GetShape() == pcbnew.SHAPE_T_RECT]
_knob_x = max(ToMM(g_.GetBoundingBox().GetRight()) for g_ in _knob)
assert _knob_x > XF + 0.7, f"the switch knob does not reach past the edge ({_knob_x:.2f} vs {XF:.2f})"
print(f"switch knob sticks {_knob_x - XF:.2f} mm past the flat")

# Chips either side of the connector: counter on the left, timer on the right (front view).
U2_C = (-12.3, -7.4)
u2 = place("U2", U2_C, ("1", (U2_C[0] - 2.475, U2_C[1] + 4.445)))    # pin 1 bottom-left: Q5 Q1 Q0 Q2 Q6 Q7 Q3 GND up the left side; VCC bottom-right
U1_C = (15.1, -3.3)
u1 = place("U1", U1_C, ("1", (U1_C[0] - 1.905, U1_C[1] - 2.475)))    # top row GND TRIG OUT RESET, bottom row VCC DIS THR CV (left to right)

# Ten LED places round the star, anticlockwise in front view. Elevation angles in degrees, 0 = right, 90 = up.
# Three gaps: the switch at 3 o'clock, its mirror image at 9 o'clock, and the way in for the coin cell at the bottom.
PLACES = [25, 51, 77, 103, 129, 155, 205, 229, -49, -25]
START = 2        # D1 (counter output Q0) sits at PLACES[START]; D2, D3 ... follow anticlockwise. Chosen for the fewest crossings (see ORDER).
LED_ANGLE = {f"D{k + 1}": PLACES[(k + START) % 10] for k in range(10)}
ANODE_SIDE = {ref: (+1 if 0 < a < 180 and a != 129 else -1) for ref, a in LED_ANGLE.items()}   # +1: anode on the anticlockwise end (the end its track arrives from)


def polar(r, deg):
    a = math.radians(deg)
    return (round(r * math.cos(a), 4), round(-r * math.sin(a), 4))


led = {}
for ref, a in LED_ANGLE.items():
    c = polar(R_LED, a)
    want = (c[0] + 1.55 * math.sin(math.radians(a)) * -ANODE_SIDE[ref], c[1] + 1.55 * math.cos(math.radians(a)) * -ANODE_SIDE[ref])
    led[ref] = place(ref, c, ("2", want), angles=(a + 90, a - 90, 90 - a, -90 - a))

# Small parts. The timer's parts sit below the timer, between it and the switch; the LED resistor in the 9 o'clock gap.
SMALL = {
    #       centre          pad 1 at
    "R2": ((15.1, 1.3), (14.275, 1.3)),         # under the timer's DIS and THR pins: DIS left, TIM right
    "C2": ((15.85, 3.6), (15.85, 2.825)),       # timing capacitor: TIM up, GND down
    "C1": ((17.4, 1.95), (17.4, 1.175)),        # control-pin capacitor: CV up, GND down
    "C3": ((17.4, 5.0), (17.4, 5.775)),         # supply capacitor: GND up, VLOAD down
    "R1": ((13.45, 2.85), (12.625, 2.85)),      # three 3.3 M in parallel, stacked: VLOAD left, DIS right
    "R4": ((13.45, 4.4), (12.625, 4.4)),
    "R5": ((13.45, 5.95), (12.625, 5.95)),
    "R3": ((-20.4, 0.0), (-21.225, 0.0)),       # LED resistor in the 9 o'clock gap: LED return on the outside, GND inside
}
small = {}
for ref, (c, p1) in SMALL.items():
    small[ref] = place(ref, c, ("1", p1))

_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"
LEDC = {ref: mm(fp.GetPosition()) for ref, fp in led.items()}
_star_keep = grown(star, 0.5)
for ref, c in LEDC.items():
    w = pcbnew.SHAPE_POLY_SET()
    add_circle(w, P(*c), WINDOW)
    w.BooleanIntersection(_star_keep)
    assert w.OutlineCount() == 0, f"{ref}: its window would bite into the star"

# ---- routing grid -------------------------------------------------------------------------------------
g = router.Grid(bx0 - 0.2, by0 - 0.2, bx1 + 0.2, by1 + 0.2)
EDGE_C = EDGE + router.HW_MAX + 0.02
okarea = g.poly_mask(body, -EDGE_C)
for L in (RB, RF):
    g.stamp(L, ~okarea, -1)
CELL_KEEP = 10.4                                     # no back copper of any other net under the coin cell
cell_m = (g.X - BAT[0]) ** 2 + (g.Y - BAT[1]) ** 2 <= CELL_KEEP ** 2
g.stamp(RB, cell_m, -1)
INF = router.CLR + router.HW_MAX + router.SLACK
netcode = {}


def code(name):
    if name not in netcode:
        netcode[name] = len(netcode) + 1
    return netcode[name]


PADS = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = ToMM(pad.GetDrillSize().x) / 2 + 0.25 + router.HW_MAX + router.SLACK
            c = mm(pad.GetPosition())
            m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= r * r
            g.stamp(RB, m, -1)
            g.stamp(RF, m, -1)
            g.noVia |= (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (r + 0.3) ** 2
            continue
        n = pad.GetNetname() or f"nc-{fp.GetReference()}-{pad.GetNumber()}"
        ps = pad_poly(pad, B_Cu)
        g.stamp(RB, g.poly_mask(ps, INF), code(n))
        g.noVia |= g.poly_mask(ps, 0.45)
        PADS.append((fp.GetReference(), pad.GetNumber(), n, RB, ps))
for ref, c in LEDC.items():                          # nothing under an LED between its pads, nothing on the front in its window
    g.stamp(RB, (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= 1.05 ** 2, -1)
    g.stamp(RF, (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (WINDOW + 0.1) ** 2, -1)
    g.noVia |= (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (WINDOW + 0.6) ** 2
# vias: never in the star (they would show as holes in the gold), never under the coin cell
g.noVia |= g.poly_mask(star, 0.6)
g.noVia |= (g.X - BAT[0]) ** 2 + (g.Y - BAT[1]) ** 2 <= 11.0 ** 2
# The front is one sheet of ground copper. LED lines may hop over each other on it, but only in the dark area outside
# the star (a front track shows as a faint line under the solder mask), and at a high price so that it happens rarely.
front_copper = okarea & (g.owner[RF] == 0)
g.stamp(RF, g.poly_mask(star, 0.45), -1)
g.cost[RF] = 4.0
VIA_COST = 150.0

TRACKS, VIAS = [], []          # (layer, a, b, width, net) / ((x, y), net)


def add_track(a, b_, w, net, L=RB):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(w))
    t.SetLayer(B_Cu if L == RB else F_Cu)
    t.SetNet(nets[net])
    board.Add(t)
    TRACKS.append((L, a, b_, w, net))
    g.stamp(L, g.seg_mask(a, b_, w / 2 + INF), code(net))


def add_via(c, net):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c))
    v.SetDrill(FromMM(VIA_HOLE))
    v.SetWidth(FromMM(VIA_D))
    v.SetNet(nets[net])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append((c, net))
    m = (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= (VIA_D / 2 + INF) ** 2
    g.stamp(RB, m, code(net))
    g.stamp(RF, m, code(net))


def run(pts, w, net):
    for a, b_ in zip(pts, pts[1:]):
        if a != b_:
            add_track(a, b_, w, net)


# ---- hand-laid tracks ---------------------------------------------------------------------------------
# 1. The LEDs' shared return (LEDK): a ring outside the LEDs from D6 (right of top) anticlockwise round to D7, broken only
#    at the switch. Each cathode pad gets a short spoke out to it. R3 hangs on it in the 9 o'clock gap.
def ang_of(p):
    a = math.degrees(math.atan2(-p[1], p[0]))
    return a if a >= 0 else a + 360


spokes = []
for ref, fp in led.items():
    k = pp(fp, "1")
    spokes.append((ang_of(k), k))
k3 = pp(small["R3"], "1")
spokes.append((ang_of(k3), k3))
spokes.sort()
a_lo, a_hi = spokes[0][0], spokes[-1][0]
assert 15 < a_lo < 30 and 330 < a_hi < 345, (a_lo, a_hi)
ring_a = sorted(set([round(a_lo + 2.0 * i, 4) for i in range(int((a_hi - a_lo) / 2.0) + 1)] + [round(s[0], 4) for s in spokes]))
run([polar(R_RING, a) for a in ring_a], SIG, "LEDK")
for a, k in spokes:
    run([k, polar(R_RING, round(a, 4))], SIG, "LEDK")

# 2. The clip joins its two + pads itself; this arc under the cell's rim (outside the bare contact disc, on the closed-end
#    side) makes the board agree.
_r = 9.25
_arc = [(round(BAT[0] + _r * math.cos(math.radians(a_)), 3), round(BAT[1] - _r * math.sin(math.radians(a_)), 3)) for a_ in range(180, -1, -10)]
_arc = [(BAT[0] - 10.5, BAT[1] - 2.0), (BAT[0] - 10.5 + 0.9, BAT[1] - 2.0)] + _arc[1:-1] + [(BAT[0] + 10.5 - 0.9, BAT[1] - 2.0), (BAT[0] + 10.5, BAT[1] - 2.0)]
for a_, b_ in zip(_arc, _arc[1:]):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a_))
    t.SetEnd(P(*b_))
    t.SetWidth(FromMM(PWR))
    t.SetLayer(B_Cu)
    t.SetNet(nets["VBAT"])
    board.Add(t)
    TRACKS.append((RB, a_, b_, PWR, "VBAT"))

# 3. Power, clock and the timer's own nets, laid by hand. The order of the switch pins (badge on top, load, cell at the
#    bottom) and the 555's pinout leave one way to do this on one layer without crossing; see the README.
A_X = 18.25                      # the load supply runs up and down just inside the switch pins
HAND = [
    # badge supply: up from switch pin 1, then along the middle of the connector to the bottom end of its pin 1 pad
    ("VSAO", PWR, [(19.47, -3.0), (19.2, -3.0), (19.2, -5.9), (17.1, -8.0), (-2.54, -8.0), (-2.54, -9.6)]),
    # coin cell: down from switch pin 4, under the timer's parts, to the right-hand clip pad
    ("VBAT", PWR, [(19.47, 3.0), (19.2, 3.0), (19.2, 6.2), (17.4, 8.0), (10.5, 8.0)]),
    # load supply: from switch pin 3 up to the timer's RESET pin, and down round the timer's parts to its VCC pin
    ("VLOAD", PWR, [(19.47, 1.5), (A_X, 1.5), (A_X, -5.5), (17.005, -5.5)]),
    ("VLOAD", PWR, [(A_X, 1.5), (A_X, 6.3), (17.25, 7.3), (12.625, 7.3), (12.625, 5.95)]),
    ("VLOAD", SIG, [(12.625, 5.95), (12.625, 1.2), (13.1, 0.4), (13.195, 0.0)]),
    ("VLOAD", PWR, [(17.4, 5.775), (A_X, 5.775)]),
    # ... and on to the counter, under the bottom edge of the connector
    ("VLOAD", PWR, [(12.625, 1.6), (9.775, -1.25), (-9.4, -1.25), (-9.4, -2.955)]),
    # clock: timer OUT, over the timer's top-left pins, down its left side, under the connector to counter pin 14
    ("CLK", SIG, [(15.735, -6.2), (15.735, -7.25), (12.4, -7.25), (12.4, -1.85), (-8.3, -1.85), (-8.3, -5.495), (-9.825, -5.495)]),
    # timer: TRIG to THR under the chip; DIS and THR down to their parts; CV to its capacitor
    ("TIM", SIG, [(14.465, -5.3), (14.465, -4.4), (15.735, -2.2), (15.735, -1.3)]),
    ("TIM", SIG, [(15.735, -0.5), (15.735, 0.6), (15.925, 1.3), (15.85, 2.825)]),
    ("DIS", SIG, [(14.465, -0.4), (14.465, 0.6), (14.275, 1.3), (14.275, 5.95)]),
    ("CV", SIG, [(17.005, -0.5), (17.005, 0.4), (17.4, 0.9), (17.4, 1.175)]),
    # timer ground pin: under the chip, out between its VCC and DIS pins, under the three timing resistors (between
    # their pads) to a covered via in the dark area right of the star; the two capacitors' ground pads join it
    ("GND", SIG, [(13.195, -5.3), (13.195, -4.3), (13.83, -3.5), (13.83, 0.25), (13.45, 0.75), (13.45, 6.8), (16.4, 6.8), (16.4, 5.2), (15.85, 4.375)]),
    ("GND", SIG, [(15.85, 4.375), (17.4, 4.225)]),
    ("GND", SIG, [(17.4, 2.725), (17.4, 4.225)]),
    # counter: clock-enable and reset pins (both tied to ground) joined under the chip
    ("GND", SIG, [(-9.825, -4.225), (-11.0, -4.225), (-11.4, -4.6), (-11.4, -6.4), (-11.0, -6.765), (-9.825, -6.765)]),
    # counter ground pin (top left): in under the chip to a covered via
    ("GND", SIG, [(-14.775, -11.845), (-12.9, -11.845)]),
    # counter outputs that leave under the chip: Q7 and Q6 out of its bottom end, Q9 out of its top end
    ("LED8_A", SIG, [(-14.775, -9.305), (-12.6, -9.305), (-12.2, -8.9), (-12.2, -2.1)]),
    ("LED7_A", SIG, [(-14.775, -8.035), (-13.0, -8.035), (-12.6, -7.635), (-12.6, -2.1)]),
    ("LED10_A", SIG, [(-9.825, -9.305), (-11.0, -9.305), (-11.4, -9.7), (-11.4, -12.7)]),
    # Q0 up the left side of the chip, close in, so that Q1 can pass outside it
    ("LED1_A", SIG, [(-14.775, -5.495), (-16.25, -5.495), (-16.25, -12.4), (-15.6, -13.05), (-13.0, -13.05)]),
    # counter outputs that have to hop over others (see below): Q3 and Q2 go in under the chip, each to a covered via
    ("LED4_A", SIG, [(-14.775, -10.575), (-12.6, -10.575)]),
    ("LED3_A", SIG, [(-14.775, -6.765), (-13.25, -6.765)]),
]
START_AT = {"LED1_A": (RB, (-13.0, -13.05)), "LED8_A": (RB, (-12.2, -2.1)), "LED7_A": (RB, (-12.6, -2.1)), "LED10_A": (RB, (-11.4, -12.7)),
            "LED4_A": (RF, (-12.6, -10.575)), "LED3_A": (RF, (-13.25, -6.765))}       # where the router carries on from
# The cell's bare contact disc is boxed in by the cell's own supply arc above it and the LED lines that pass below it,
# and no via may sit under the cell: it gets its own track out to a covered via in the dark area left of the star.
CELL_GND_VIA = (-12.5, 14.0)
HAND.append(("GND", 0.25, [(-7.11, 12.19), CELL_GND_VIA]))
for net, w, pts in HAND:
    run(pts, w, net)
add_via((16.4, 5.8), "GND")
add_via(CELL_GND_VIA, "GND")
add_via((-12.9, -11.845), "GND")
add_via(START_AT["LED4_A"][1], "LED4_A")
add_via(START_AT["LED3_A"][1], "LED3_A")

# ---- routed tracks (back only): the ten LED lines ----------------------------------------------------------
# The 4017's outputs come out of the chip in the order Q5 Q1 Q0 Q2 Q6 Q7 Q3 / Q8 Q4 Q9, and the lights must run in the
# order Q0 ... Q9 round the ring, so the ten lines cannot all be laid on one side without crossing: seven at most,
# whichever light Q0 starts at and whichever way round they run (checked by search). With D1 at 77 degrees and the
# lights running anticlockwise, the seven are Q8 Q9 Q0 Q1 (over the top), Q5 (down the left) and Q6 Q7 (under the
# chip, round the bottom of the cell); Q3, Q2 and Q4 each hop over the others on the front, in the dark area.
ORDER = [f"LED{k}_A" for k in (8, 7, 6, 9, 10, 2, 1, 4, 3, 5)]
HOPPERS = {"LED4_A", "LED3_A", "LED5_A"}             # only these may use the front
if os.environ.get("GS_ORDER"):                       # for trying another order, e.g. GS_ORDER=8,7,6,9,10,2,1,4,3,5
    ORDER = [f"LED{k}_A" for k in os.environ["GS_ORDER"].split(",")]
print("routing order:", ORDER)
ROUTE_FAIL = []
g.cost[RB][g.X ** 2 + g.Y ** 2 > (R_LED - 1.6) ** 2] = 2.5       # lines keep in from the LED ring unless they are going to an LED
for ref, fp in led.items():                           # keep the way in to each anode pad free for its own line
    a_, k_ = pp(fp, "2"), pp(fp, "1")
    ux, uy = (a_[0] - k_[0]) / 3.1, (a_[1] - k_[1]) / 3.1
    for d_ in (0.5, 0.9):
        g.stamp(RB, (g.X - a_[0] - ux * d_) ** 2 + (g.Y - a_[1] - uy * d_) ** 2 <= 0.6 ** 2, code(PADNETS[ref]["2"]))
for net in ORDER:
    if time.time() - T0 > ROUTE_LIMIT_S:
        ROUTE_FAIL.append(net)
        print("ROUTE SKIPPED (time limit):", net)
        continue
    tg = [(L, g.poly_mask(ps, 0)) for ref, num, n, L, ps in PADS if n == net]
    if net in START_AT:                               # the chip end is already laid by hand: carry on from where it stops
        L0, (x0_, y0_) = START_AT[net]
        tg = [(L0, (g.X - x0_) ** 2 + (g.Y - y0_) ** 2 <= 0.12 ** 2)] + [t_ for t_, q in zip(tg, [q for q in PADS if q[2] == net]) if q[0] != "U2"]
    w = SIG
    t1 = time.time()
    paths = router.route_net(g, code(net), tg, w, via_cost=VIA_COST if net in HOPPERS else 1e9)
    if paths is None:
        ROUTE_FAIL.append(net)
        print("ROUTE FAILED:", net)
        continue
    n_seg = 0
    for path in paths:
        segs, vias_ = router.simplify(g, path)
        for L, a_, b_ in segs:
            add_track(a_, b_, w, net, L)
            n_seg += 1
        for c in vias_:
            add_via(c, net)
    print(f"routed {net}: {n_seg} segments, {len([v for v in VIAS if v[1] == net])} vias, {time.time() - t1:.1f} s")

# ---- back copper: ground everywhere, cleared around everything that is not ground ----------------------
gnd_code = nets["GND"].GetNetCode()


def back_ground():
    gnd = pcbnew.SHAPE_POLY_SET(inner)
    cut = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            elif pad.GetNetCode() != gnd_code:
                pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for t in board.Tracks():
        if t.GetNetname() != "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
            t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for c in LEDC.values():
        add_circle(cut, P(*c), WINDOW + 0.05)
    cut.Simplify()
    gnd.BooleanSubtract(cut)
    gnd.Simplify()
    return gnd


def gnd_things():
    s = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd_code and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                s.Append(pad_poly(pad, B_Cu))
    for t in board.Tracks():
        if t.GetNetname() == "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
            t.TransformShapeToPolygon(s, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
    s.Simplify()
    return s


# Join the ground. Every ground pad must reach the others: through a piece of back ground copper, or by a track and a
# covered via up to the front copper. Each piece of back copper that holds a ground pad is one target for the router;
# the front is open to this net only, at next to no cost, so the router adds the fewest vias it can.
fo = g.owner[RF]
fo[front_copper & (fo <= 0)] = code("GND")           # everything on the front that is not near a hop is ground copper
g.cost[RF] = 0.02
pieces = back_ground()
things = gnd_things()
targets = []
used_pad = set()
gpads = [q for q in PADS if q[2] == "GND"]
for i in range(pieces.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(pieces.Polygon(i))
    if area_mm2(piece) < 1.0:
        continue
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(things)
    if area_mm2(both) < 0.005:
        continue
    m = g.poly_mask(piece, -0.2) & ((g.owner[RB] == 0) | (g.owner[RB] == code("GND")))
    holds = []
    for k, q in enumerate(gpads):
        t = pcbnew.SHAPE_POLY_SET(grown(q[4], 0.05))
        t.BooleanIntersection(piece)
        if area_mm2(t) > 0.002:
            holds.append(k)
    if not holds or not m.any():
        continue
    used_pad.update(holds)
    g.stamp(RB, m, code("GND"))
    targets.append((area_mm2(piece), (RB, m)))
targets.sort(key=lambda t: -t[0])
targets = [t for _, t in targets]
lonely = [q for k, q in enumerate(gpads) if k not in used_pad]
print("ground: back copper pieces holding a ground pad:", len(targets), "| ground pads no piece reaches:", [(q[0], q[1]) for q in lonely])
for q in lonely:
    targets.append((RB, g.poly_mask(q[4], 0)))
# what the hand-placed ground vias already tie to the front sheet: spread out from them through ground-owned back cells
import numpy as np  # noqa: E402
gb = g.owner[RB] == code("GND")
conn = np.zeros_like(gb)
for c, n_ in VIAS:
    if n_ == "GND":
        conn |= (g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= 0.3 ** 2
conn &= gb
while True:
    grow = conn.copy()
    grow[1:, :] |= conn[:-1, :]
    grow[:-1, :] |= conn[1:, :]
    grow[:, 1:] |= conn[:, :-1]
    grow[:, :-1] |= conn[:, 1:]
    grow &= gb
    if (grow == conn).all():
        break
    conn = grow
todo = [t for t in targets if not (t[1] & conn).any()]
print("ground: already tied to the front by the hand-placed vias:", len(targets) - len(todo), "| still to tie:", len(todo))
targets = [(RF, fo == code("GND"))] + todo            # the front sheet first, then every piece or pad not yet on it
if len(targets) > 1 and time.time() - T0 < ROUTE_LIMIT_S + 120:
    t1 = time.time()
    paths = router.route_net(g, code("GND"), targets, 0.25, via_cost=40.0)
    if paths is None:
        ROUTE_FAIL.append("GND")
        print("ROUTE FAILED: GND")
        for k in range(1, len(targets)):                     # say which piece cannot be reached
            if router.route_net(g, code("GND"), [targets[0], targets[k]], 0.25, via_cost=40.0) is None:
                jj, ii = [int(v.mean()) for v in targets[k][1].nonzero()]
                print("  cannot reach the ground piece around", g.xy(ii, jj), "cells:", int(targets[k][1].sum()))
    else:
        for path in paths:
            segs, vias_ = router.simplify(g, path)
            for L, a_, b_ in segs:
                if L == RB:
                    add_track(a_, b_, 0.25, "GND", RB)
            for c in vias_:
                add_via(c, "GND")
        print(f"ground joined: {len(VIAS)} vias, {time.time() - t1:.1f} s")
elif len(targets) > 1:
    ROUTE_FAIL.append("GND")
print("vias:", [v[0] for v in VIAS], "| failed:", ROUTE_FAIL)

if os.environ.get("GS_DEBUG_PNG"):                  # a picture of the router's view of the back, for whoever edits the placement
    import struct
    import zlib
    import numpy as np
    o = g.owner[RB]
    pal = np.random.RandomState(3).randint(60, 255, size=(len(netcode) + 2, 3)).astype(np.uint8)
    img = np.zeros(o.shape + (3,), dtype=np.uint8) + 255
    img[o == -1] = (40, 40, 40)
    for name, k in netcode.items():
        img[o == k] = pal[k] if name != "GND" else (200, 230, 200)
    for L, a_, b_, w, n in TRACKS:
        img[g.seg_mask(a_, b_, w / 2)] = ((255, 0, 0) if n != "GND" else (0, 120, 0)) if L == RB else (255, 0, 255)
    for c, n in VIAS:
        img[(g.X - c[0]) ** 2 + (g.Y - c[1]) ** 2 <= 0.3 ** 2] = (0, 0, 0)
    for ref, num, n, L, ps in PADS:
        img[g.poly_mask(ps, 0)] = (0, 0, 255) if n != "GND" else (0, 160, 160)
    _z = 2
    if os.environ.get("GS_DEBUG_CROP"):                 # "x0,y0,x1,y1" in mm: a close-up at 0.1 mm = 8 pixels
        cx0, cy0, cx1, cy1 = (float(v) for v in os.environ["GS_DEBUG_CROP"].split(","))
        (i0, j0), (i1, j1) = g.ij(cx0, cy0), g.ij(cx1, cy1)
        img = img[j0:j1, i0:i1]
        _z = 8
    img = np.repeat(np.repeat(img, _z, axis=0), _z, axis=1)
    raw = b"".join(b"\x00" + img[j].tobytes() for j in range(img.shape[0]))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(os.environ["GS_DEBUG_PNG"], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", img.shape[1], img.shape[0], 8, 2, 0, 0, 0))
                                                 + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))

gnd = back_ground()
things = gnd_things()
n_gnd = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(things)
    if area_mm2(both) > 0.005 and area_mm2(piece) > 1.0:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
print("back ground pieces:", n_gnd)

# ---- front: one sheet of ground copper; the star is a window in the solder mask -------------------------
fcu = pcbnew.SHAPE_POLY_SET(inner)
fcut = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
for c in LEDC.values():
    add_circle(fcut, P(*c), WINDOW)
for t in board.Tracks():
    if t.GetNetname() != "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == F_Cu):
        t.TransformShapeToPolygon(fcut, F_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
fcut.Simplify()
fcu.BooleanSubtract(fcut)
fcu.Simplify()
_big = max(range(fcu.OutlineCount()), key=lambda i: abs(fcu.Outline(i).Area()))
add_filled(board, pcbnew.SHAPE_POLY_SET(fcu.Polygon(_big)), F_Cu, nets["GND"])
_isl = 0
for i in range(fcu.OutlineCount()):                   # copper boxed in between two hops stays, unconnected, so the front looks even
    if i != _big and abs(fcu.Outline(i).Area()) / 1e12 > 0.15:
        assert abs(fcu.Outline(i).Area()) / 1e12 < 12.0, "the front copper is cut into two large pieces"
        add_filled(board, pcbnew.SHAPE_POLY_SET(fcu.Polygon(i)), F_Cu)
        _isl += 1
print("front copper islands between hops (left unconnected):", _isl)
if STAR_FINISH == "gold":
    add_filled(board, star, pcbnew.F_Mask)
else:
    add_filled(board, star, pcbnew.F_SilkS)
dots = pcbnew.SHAPE_POLY_SET()
for c in LEDC.values():
    add_circle(dots, P(*c), DOT)
add_filled(board, dots, pcbnew.F_Mask)


# ---- back silkscreen ------------------------------------------------------------------------------------
def text(txt, x, y, size, thick, rot=0, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick))
    t.SetBold(bold)
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


# The maker's two lines of back text, same words, set straight above the connector (in his drawing they ran along the
# rim of a 100 mm disc; here the rim is taken by the LEDs). His letters scaled with the board would be 2.0 mm; these are 1.3.
text("@greymanhw", 0.0, -17.75, 1.3, 0.18)
text("star 1.0.0", 0.0, -15.6, 1.3, 0.18)
# SAO++ labels. Seen from the back the switch is on the left edge: knob up = badge power, knob down = coin cell,
# middle = off (no room to print OFF). The two words sit just inboard of the two ends of the switch.
text("SAO", 17.9, -7.4, 0.8, 0.12)
text("BAT", 17.2, 8.8, 0.8, 0.12)
text("Gold Star", -15.6, 3.6, 1.0, 0.15, rot=90)
text("SAO++ rA", -13.9, 3.6, 0.8, 0.12, rot=90)
text("CR2032", 13.9, 11.9, 0.9, 0.13, rot=90)

# ---- save -------------------------------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT, f"({time.time() - T0:.0f} s)")
if ROUTE_FAIL:
    sys.exit("NOT ROUTED: " + ", ".join(ROUTE_FAIL))
