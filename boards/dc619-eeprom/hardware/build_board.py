#!/usr/bin/env python3
"""Build dc619-eeprom.kicad_pcb: a NEW SAO++ layout of AND!XOR's DC27 "DC619 EEPROM" SAO reference design.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/dc619-eeprom/hardware/build_board.py

What the original is: the maker published a schematic picture only (original/DC619-EEPROM_sao1.69bis/
dc619-eeprom-schematic.png, "DC858/DC619 SAO", rev 2, 2019-03-02), no board file and no artwork. The circuit on it:
  - J1, the 6-pin SAO v1.69bis header
  - U1, an AT24C02N I2C EEPROM (SOIC-8): A0 A1 A2 to GND (address 0x50), WP to GND (writable), VCC to SAO pin 1,
    SDA / SCL straight to SAO pins 3 / 4. No pull-ups, no supply capacitor
  - R1 4.7k from SAO pin 5 (GPIO1) to LED D2 to GND, and R2 4.7k from SAO pin 6 (GPIO2) to LED D1 to GND: two lights
    the BADGE switches on by driving its GPIO lines high
There is no battery and no switch on it. So everything drawn here (outline, placement, routing, front artwork) is
SAO++'s own; only the circuit is the maker's.

What this script draws
  - a 24 x 24 mm board with rounded corners
  - back: the SAO++ connector (key up), the EEPROM in SOT-23-5 with a 100 nF supply capacitor, two red through-board
    LEDs near the lower corners, each with the shared 1.3 k resistor. One copper layer of routing; ground copper
    everywhere else
  - front: ground copper under solder mask with two bare-board windows where the LEDs shine through, and plain
    white lettering (a chip outline with the I2C address, the ID byte order). Two tented vias tie the front copper
    to ground
  - BADGE POWER ONLY: no coin cell and no SAO / OFF / BAT switch (a recorded exception, see README)

Coordinates in this file are millimetres from the board's top-left corner, front view (x right, y down);
the board sits at (OX, OY) on the KiCad sheet.
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, ROUND, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "dc619-eeprom"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

OX, OY = 100.0, 100.0   # where the board's top-left corner sits on the sheet
W, H, RAD = 24.0, 24.0, 2.5

CLEAR = 0.30        # copper-to-copper gap cut into the ground copper
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25     # every pad at least this far inside the edge
SIG = 0.30          # track width
THIN = 0.25         # the ground link under the EEPROM body
VIA_D, VIA_HOLE = 0.6, 0.3
WINDOW_B = 1.6      # radius kept free of back copper behind each LED (docs/standard.md section 4)
WINDOW_F = 2.0      # ... and of front copper
WINDOW_MASK = 1.4   # front solder mask opened inside the copper window: bare board, no copper edge showing

# ---- placement (board coordinates, front view) -----------------------------------------------------
CONN = (12.0, 9.2)          # centred left-right; pads start 3.6 mm from the top edge, body 4.36 mm from the sides
U1_AT = (11.2, 17.6)        # EEPROM, just below the connector
C1_AT = (7.6, 17.775)       # its supply capacitor, beside it
R1_AT = (2.3, 13.6)         # GPIO1 resistor, in the left margin beside the connector
R2_AT = (17.2, 16.2)        # GPIO2 resistor, below the connector
D2_AT = (4.4, 19.0)         # GPIO1 light, lower left (front view)
D1_AT = (19.6, 19.0)        # GPIO2 light, lower right
VIA_U1 = (11.2, 20.2)       # ground via below the EEPROM
VIA_J1 = (5.6, 9.25)        # ground via under the connector body


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def loc(v):
    x, y = mm(v)
    return (round(x - OX, 4), round(y - OY, 4))


def rounded_rect(x0, y0, x1, y1, r, n=16):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90.0 * k / n)
            pts.append((round(OX + cx + r * math.cos(a), 4), round(OY + cy + r * math.sin(a), 4)))
    return pts


def circle(c, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(*c), r)
    return ps


# ---- outline ------------------------------------------------------------------------------------
OUTLINE = rounded_rect(0, 0, W, H, RAD)
json.dump({"outer": OUTLINE, "holes": []}, open(os.path.join(HERE, "outline.json"), "w"))
body = poly(OUTLINE)
board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)         # one polygon, not arcs or circles: tools/panelize.py reads polygons
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
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

# the maker's circuit, checked against the schematic picture every build
assert PADNETS["J1"] == {"1": "VSAO", "2": "GND", "3": "SDA", "4": "SCL", "5": "SAO_GPIO1", "6": "SAO_GPIO2"}
assert PADNETS["U1"] == {"1": "SCL", "2": "GND", "3": "SDA", "4": "VSAO", "5": "GND"}     # SOT-23-5: 5 = WP, tied low
assert all(len(d) == len(PINNAMES[r]) for r, d in PADNETS.items()), "every pin is wired on this board"


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
    fp.SetFPID(pcbnew.LIB_ID(fpid.split(":")[0], fpid.split(":")[1]))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
    fp.SetValue(PARTS[ref].get("value", value))
    for k, v in fields.items():
        assert fp.HasField(k), f"{ref}: footprint has no {k} field"
        fp.GetField(k).SetText(v)
    for pad in fp.Pads():
        pad.SetNet(nets[PADNETS[ref][pad.GetNumber()]])


def place(ref, pos, want):
    """Place a part on the back at the right-angle rotation that puts pad want[0] at want[1]."""
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
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = min(abs(loc(p.GetPosition())[0] - want[1][0]) + abs(loc(p.GetPosition())[1] - want[1][1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.02, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pp(fp, num):
    return [loc(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))          # VCC top-left in front view = key slot up
u1 = place("U1", U1_AT, ("1", (U1_AT[0] + 1.1375, U1_AT[1] - 0.95)))       # SCL / GND / SDA column on the right
c1 = place("C1", C1_AT, ("1", (C1_AT[0], C1_AT[1] + 0.775)))               # supply pad at the bottom, level with U1 pin 4
r1 = place("R1", R1_AT, ("1", (R1_AT[0], R1_AT[1] - 0.825)))               # GPIO1 enters at the top
r2 = place("R2", R2_AT, ("1", (R2_AT[0] - 0.825, R2_AT[1])))               # GPIO2 enters on the left
d2 = place("D2", D2_AT, ("2", (D2_AT[0] - 1.55, D2_AT[1])))                # anode toward the left edge
d1 = place("D1", D1_AT, ("2", (D1_AT[0] - 1.55, D1_AT[1])))                # anode toward the middle
LEDS = {"D1": D1_AT, "D2": D2_AT}

# connector pin order, as docs/standard.md section 1 draws it (seen from the front it is mirrored: VCC SDA GPIO1 / GND SCL GPIO2)
def near(a, b, tol=0.002):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


assert all(near(pp(conn, n), (CONN[0] + dx, CONN[1] - 3.4)) for n, dx in zip("135", (-2.54, 0, 2.54)))
assert all(near(pp(conn, n), (CONN[0] + dx, CONN[1] + 3.4)) for n, dx in zip("246", (-2.54, 0, 2.54)))
# EEPROM pins, front view: right column SCL / GND / SDA (top to bottom), left column WP (top), VCC (bottom)
assert near(pp(u1, "5"), (U1_AT[0] - 1.1375, U1_AT[1] - 0.95)) and near(pp(u1, "4"), (U1_AT[0] - 1.1375, U1_AT[1] + 0.95))
assert near(pp(u1, "2"), (U1_AT[0] + 1.1375, U1_AT[1])) and near(pp(u1, "3"), (U1_AT[0] + 1.1375, U1_AT[1] + 0.95))

# every pad on the board, PAD_EDGE inside the edge; the connector 3 mm or more from every edge (standard section 2)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"
_cb = pcbnew.SHAPE_POLY_SET()
for pad in conn.Pads():
    _cb.Append(pad_poly(pad, B_Cu))
for g in conn.GraphicalItems():
    if g.GetLayer() == pcbnew.B_Fab:
        bb = g.GetBoundingBox()
        _cb.Append(poly([(ToMM(bb.GetLeft()), ToMM(bb.GetTop())), (ToMM(bb.GetRight()), ToMM(bb.GetTop())),
                         (ToMM(bb.GetRight()), ToMM(bb.GetBottom())), (ToMM(bb.GetLeft()), ToMM(bb.GetBottom()))]))
_x0, _y0, _x1, _y1 = bbox_mm(_cb)
CONN_MARGIN = min(_x0 - OX, _y0 - OY, OX + W - _x1, OY + H - _y1)
print("connector (pads and body) to the nearest board edge: %.2f mm" % CONN_MARGIN)
assert CONN_MARGIN >= 3.0

# ---- routing: back copper only --------------------------------------------------------------------
TRACKS = []


def route(net, pts, width=SIG):
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
        TRACKS.append(t)


VIAS = []


def via(net, at):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*at))
    v.SetWidth(FromMM(VIA_D))
    v.SetDrill(FromMM(VIA_HOLE))
    v.SetLayerPair(F_Cu, B_Cu)
    v.SetNet(nets[net])
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    VIAS.append(v)


cx, cy = CONN
ux, uy = U1_AT
LANE_L, LANE_R = cx - 1.27, cx + 1.27       # the two gaps between the connector's lower pads
MID = cy - 0.6                              # where the top-row signals turn, under the connector body
BELOW = cy + 3.4 + 2.2 + 0.4                # 0.4 mm below the ends of the lower pads

# badge 3.3 V: pin 1 (top left) -> under the connector body -> between pins 2 and 4 -> round the left of the EEPROM ->
# its VCC pin (lower left), with a branch to the capacitor
u4 = pp(u1, "4")
VX = ux - 2.4                               # the drop left of the EEPROM
route("VSAO", [pp(conn, "1"), (cx - 2.54, MID), (LANE_L, MID + 1.27), (LANE_L, BELOW + 0.05), (LANE_L - 0.4, BELOW + 0.45),
               (VX + 0.4, BELOW + 0.45), (VX, BELOW + 0.85), (VX, u4[1]), u4])
route("VSAO", [(VX, u4[1]), pp(c1, "1")])
# SCL: pin 4 (bottom middle) straight down to the EEPROM's top right pin
u1p = pp(u1, "1")
route("SCL", [pp(conn, "4"), (cx, BELOW), (u1p[0], BELOW + 0.34), u1p])
# SDA: pin 3 (top middle) -> under the body -> between pins 4 and 6 -> round the right of the EEPROM -> lower right pin
u3 = pp(u1, "3")
SX = ux + 2.7
route("SDA", [pp(conn, "3"), (cx, MID), (LANE_R, MID + 1.27), (LANE_R, BELOW + 0.2), (SX, BELOW + 0.2 + (SX - LANE_R)), (SX, u3[1]), u3])
# GPIO2: pin 6 (bottom right) -> R2 -> the right-hand light
r2a, r2b = pp(r2, "1"), pp(r2, "2")
route("SAO_GPIO2", [pp(conn, "6"), (cx + 2.54, r2a[1] - 0.8), (cx + 2.54 + 0.8, r2a[1]), r2a])
d1a = pp(d1, "2")
route("LED1_A", [r2b, (d1a[0], r2b[1] + 0.7), d1a])
# GPIO1: pin 5 (top right) -> along the top edge above the connector -> down the left margin -> R1 -> the left-hand light
TOPY, LEFTX = cy - 3.4 - 2.2 - 0.8, R1_AT[0]
route("SAO_GPIO1", [pp(conn, "5"), (cx + 2.54, TOPY + 0.4), (cx + 2.54 - 0.4, TOPY), (LEFTX + 0.8, TOPY), (LEFTX, TOPY + 0.8), pp(r1, "1")])
d2a = pp(d2, "2")
route("LED2_A", [pp(r1, "2"), (LEFTX, d2a[1] - 1.1), (d2a[0], d2a[1] - 1.1 + (d2a[0] - LEFTX)), d2a])
# ground: the EEPROM's GND pin (middle right) and WP pin (upper left) are boxed in by its other pins, so they are
# linked under the chip body and brought out below it to a via. (Each LED's cathode pad reaches out of its light
# window into the ground copper by itself; that overlap is checked below.)
u2, u5 = pp(u1, "2"), pp(u1, "5")
route("GND", [u2, (ux, uy), (ux, VIA_U1[1])], width=THIN)
route("GND", [(ux, uy), (u5[0] + 0.5, u5[1]), u5], width=THIN)
via("GND", VIA_U1)
via("GND", VIA_J1)

# ---- back copper: GND everywhere, cleared around everything that is not GND, and behind the LEDs -------
gnd_code = nets["GND"].GetNetCode()
back = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for at in LEDS.values():
    add_circle(cut, P(*at), WINDOW_B)
cut.Simplify()
back.BooleanSubtract(cut)
back.Inflate(-FromMM(0.15), ROUND, ERR)         # drop slivers thinner than 0.3 mm
back.Inflate(FromMM(0.15), ROUND, ERR)
back.BooleanSubtract(cut)
back.Simplify()
gnd_cu = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_cu.Append(pad_poly(pad, B_Cu))
for t in TRACKS:
    if t.GetNetCode() == gnd_code:
        t.TransformShapeToPolygon(gnd_cu, B_Cu, 0, ERR, pcbnew.ERROR_INSIDE)
for v in VIAS:
    add_circle(gnd_cu, v.GetPosition(), VIA_D / 2)
gnd_cu.Simplify()
n_gnd = 0
for i in range(back.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(back.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_cu)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
    else:                                       # a loose island would be dead copper: leave it out
        print("  dropped loose back copper piece, mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back GND copper pieces:", n_gnd)
assert n_gnd == 1
for ref, fp in (("D1", d1), ("D2", d2)):                 # each LED cathode pad sits solidly in the ground copper
    k = [pad_poly(p, B_Cu) for p in fp.Pads() if p.GetNumber() == "1"][0]
    k.BooleanIntersection(back)
    print(f"{ref} cathode pad overlaps the ground copper by {area_mm2(k):.2f} mm2")
    assert area_mm2(k) > 0.4

# ---- front: GND copper under mask, with a bare window in front of each LED ---------------------------
front = pcbnew.SHAPE_POLY_SET(inner)
for at in LEDS.values():
    front.BooleanSubtract(circle(at, WINDOW_F))
front.Simplify()
assert front.OutlineCount() == 1
add_filled(board, front, F_Cu, nets["GND"])
for at in LEDS.values():
    add_filled(board, circle(at, WINDOW_MASK), pcbnew.F_Mask)


# ---- lettering --------------------------------------------------------------------------------------
def text(txt, x, y, size, layer, rot=0, thick=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(thick or size * 0.15))
    t.SetMirrored(layer == B_SilkS)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(x, y))
    board.Add(t)
    bb = t.GetBoundingBox()
    box = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
    assert box[0] > 0.8 and box[1] > 0.45 and box[2] < W - 0.8 and box[3] < H - 0.45, f"'{txt}' runs off the board: {box}"
    return box


def line(a, b, width, layer=F_SilkS):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetWidth(FromMM(width))
    s.SetLayer(layer)
    board.Add(s)


def ring(c, r, width, layer=F_SilkS):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(P(*c))
    s.SetEnd(P(c[0] + r, c[1]))
    s.SetWidth(FromMM(width))
    s.SetFilled(False)
    s.SetLayer(layer)
    board.Add(s)


# back (mirrored so it reads from the back). The maker's credit, the board name and the power note
BACK_TEXT = [text("DC619 EEPROM  SAO++ rA", W / 2, 1.45, 0.9, B_SilkS),
             text("1", cx - 4.6, cy - 6.1, 0.9, B_SilkS),                         # beside the connector's own pin-1 bar
             text("G1", 4.4, 16.55, 0.8, B_SilkS), text("G2", 20.6, 16.55, 0.8, B_SilkS),
             text("orig. design: AND!XOR", W / 2, 21.55, 0.8, B_SilkS),
             text("BADGE POWER ONLY  I2C 0x50", W / 2, 22.8, 0.8, B_SilkS)]
# no back lettering on a solder pad
_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        _pads.Append(pad_poly(pad, B_Cu, 0.15))
_pads.Simplify()
for x0, y0, x1, y1 in BACK_TEXT:
    hit = poly([(OX + x0, OY + y0), (OX + x1, OY + y0), (OX + x1, OY + y1), (OX + x0, OY + y1)])
    hit.BooleanIntersection(_pads)
    assert area_mm2(hit) < 1e-6, "back lettering lands on a pad"

# front: SAO++'s own plain artwork. A chip outline holding the I2C address, the name above it, the ID byte order below.
# No AND!XOR or DC619 logo: the maker's repository has none, and none is drawn here.
FRONT_TEXT = [text("DC619 EEPROM", W / 2, 3.3, 1.6, F_SilkS, thick=0.26),
              text("0x50", W / 2, 10.4, 2.6, F_SilkS, thick=0.42),
              text("G1", 8.2, 19.0, 1.0, F_SilkS), text("G2", 15.8, 19.0, 1.0, F_SilkS),
              text("0 YEAR  1 MAKER  2 TYPE", W / 2, 22.4, 0.9, F_SilkS)]
CHIP = (6.4, 6.6, 17.6, 14.2)
for a, b in (((CHIP[0], CHIP[1]), (CHIP[2], CHIP[1])), ((CHIP[2], CHIP[1]), (CHIP[2], CHIP[3])),
             ((CHIP[2], CHIP[3]), (CHIP[0], CHIP[3])), ((CHIP[0], CHIP[3]), (CHIP[0], CHIP[1]))):
    line(a, b, 0.3)
LEGS = [(CHIP[0] - 1.7, y, CHIP[0], y) for y in (8.0, 10.4, 12.8)] + [(CHIP[2], y, CHIP[2] + 1.7, y) for y in (8.0, 12.8)]
for x0, y0, x1, y1 in LEGS:                                                       # three legs and two: a SOT-23-5
    line((x0, y0), (x1, y1), 0.7)
ring((CHIP[0] + 1.0, CHIP[3] - 1.0), 0.35, 0.2)                                   # pin-1 dot
for at in LEDS.values():
    ring(at, WINDOW_F + 0.35, 0.2)
# the two vias come up under solder mask on the front: keep them clear of the lettering and the drawing
for v in VIAS:
    vx, vy = loc(v.GetPosition())
    for x0, y0, x1, y1 in FRONT_TEXT + [(min(a, c) - 0.35, min(b, d) - 0.35, max(a, c) + 0.35, max(b, d) + 0.35) for a, b, c, d in LEGS]:
        assert not (x0 - 0.4 < vx < x1 + 0.4 and y0 - 0.4 < vy < y1 + 0.4), f"via at {(vx, vy)} is under front lettering"
    assert abs(vx - CHIP[0]) > 0.6 and abs(vx - CHIP[2]) > 0.6 and abs(vy - CHIP[1]) > 0.6 and abs(vy - CHIP[3]) > 0.6

# ---- report and save ------------------------------------------------------------------------------
for fp in (conn, u1, c1, r1, r2, d1, d2):
    print(fp.GetReference(), {p.GetNumber(): loc(p.GetPosition()) for p in fp.Pads()})
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
print("saved", OUT)

# ---- project file: put the house check settings back ------------------------------------------------
# kicad-cli 10.0.8 can rewrite the .kicad_pro and reset the DRC severities and minimums to KiCad's defaults, which
# would silently change what "DRC clean" means. They are written here on every build (same values as the other boards).
SEVERITIES = {
    "connection_width": "warning", "copper_sliver": "warning", "courtyards_overlap": "error", "duplicate_footprints": "warning",
    "extra_footprint": "warning", "footprint_symbol_field_mismatch": "warning", "footprint_symbol_mismatch": "warning",
    "footprint_type_mismatch": "ignore", "isolated_copper": "warning", "lib_footprint_issues": "warning",
    "lib_footprint_mismatch": "warning", "malformed_courtyard": "error", "missing_courtyard": "ignore",
    "missing_footprint": "warning", "net_conflict": "warning", "npth_inside_courtyard": "error", "pth_inside_courtyard": "error",
    "silk_edge_clearance": "warning", "silk_over_copper": "warning", "silk_overlap": "warning", "solder_mask_bridge": "error",
    "text_height": "warning", "text_thickness": "warning", "track_dangling": "warning", "unconnected_items": "error",
    "via_dangling": "warning",
}
RULES = {"min_clearance": 0.15, "min_copper_edge_clearance": 0.25, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
         "min_text_height": 0.8, "min_text_thickness": 0.08, "min_through_hole_diameter": 0.3, "min_track_width": 0.15,
         "min_via_annular_width": 0.1, "min_via_diameter": 0.6, "min_silk_clearance": 0.0, "solder_mask_to_copper_clearance": 0.0}
pro = json.load(open(PRO)) if os.path.exists(PRO) else {}
dsj = pro.setdefault("board", {}).setdefault("design_settings", {})
dsj.setdefault("rule_severities", {}).update(SEVERITIES)
dsj.setdefault("rules", {}).update(RULES)
pro.setdefault("meta", {"version": 3})["filename"] = SLUG + ".kicad_pro"
json.dump(pro, open(PRO, "w"), indent=2, sort_keys=True)
open(PRO, "a").write("\n")
print("wrote house DRC settings into", PRO)
