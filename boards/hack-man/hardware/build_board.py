#!/usr/bin/env python3
"""Build hack-man.kicad_pcb from scratch: the art (art/art.json), the outline, the parts and the routing.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/hack-man/hardware/build_board.py

The maker published pictures, not design files, so nothing is loaded from an original board. What this script draws:
  front  - the five sprites as bare-board windows with a white outline and white eyes, HACK-MAN as bare copper
           lettering, and a row of pellets in the strip that was added below the lettering
  back   - five side-firing RGB LEDs under the sprites' feet, the XIAO module, the SAO connector, the power switch
           and the LiPo connector, routed on the back copper only (no vias: nothing shows on the art side)
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_Cu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "hack-man"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # ground copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
PWR = 0.40
BOTTOM = 122.3      # bottom edge of the board. The maker's board ended at about 113; the extra strip is what the XIAO needs
LETTER_DY = 2.9    # lettering moved down from the maker's position so it sits midway between the sprites' feet and the pellets (owner request)
PELLETS = True      # front: a row of pellets in that extra strip (set False for plain mask)

S = ART["px_to_mm"]


def X(px):
    return ART["origin_mm"][0] + (px - ART["origin_px"][0]) * S


def Y(px):
    return ART["origin_mm"][1] + (px - ART["origin_px"][1]) * S


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def union(parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in parts:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


def disc(cx, cy, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(cx, cy), r)
    return ps


def stroke(pts, w):
    """A polyline drawn with a round pen of width w, as a polygon."""
    parts = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        nx, ny = -(by - ay) / L * w / 2, (bx - ax) / L * w / 2
        parts.append(poly([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]))
    parts += [disc(x, y, w / 2) for x, y in pts]
    return union(parts)


# ---- art ----------------------------------------------------------------------------------------
pac = union([rect(X(x0), Y(y0), X(x1), Y(y1)) for y0, y1, x0, x1 in ART["pacman_rows"]])
cw, ch = ART["ghost_cell_px"]
gy = ART["ghost_top_px"]
bodies_l, whites_l, pupils_l = [pac], [], []
SPRITE_CX = [(X(min(r[2] for r in ART["pacman_rows"])) + X(max(r[3] for r in ART["pacman_rows"]))) / 2]
for g in ART["ghosts"]:
    cells = {"#": [], "o": [], "P": []}
    for j, row in enumerate(ART["ghost_bitmap"]):
        for i, c in enumerate(row):
            if c != ".":
                cells[c].append(rect(X(g["x0"] + i * cw), Y(gy + j * ch), X(g["x0"] + (i + 1) * cw), Y(gy + (j + 1) * ch)))
    bodies_l.append(union(cells["#"] + cells["o"] + cells["P"]))
    whites_l.append(union(cells["o"]))
    pupils_l.append(union(cells["P"]))
    SPRITE_CX.append(X(g["x0"] + 7 * cw))
bodies = union(bodies_l)
whites, pupils = union(whites_l), union(pupils_l)
eyes = union([whites, pupils])
window = pcbnew.SHAPE_POLY_SET(bodies)          # bare board on both sides: this is what glows
window.BooleanSubtract(eyes)
FEET = max(bbox_mm(bodies)[3], 0)               # y of the lowest sprite edge

letters_l, details_l = [], []
_Y0 = Y


def Y(px):                                       # from here on only the lettering is drawn: shift it
    return _Y0(px) + LETTER_DY


for L in ART["letters"]:
    if "disc" in L:
        cx, cy, r = L["disc"]
        shape = disc(X(cx), Y(cy), r * S)
        shape.BooleanSubtract(poly([(X(x), Y(y)) for x, y in L["wedge"]]))
    else:
        shape = poly([(X(x), Y(y)) for x, y in L["outer"]])
    for cx, cy, r in L.get("holes", []):
        shape.BooleanSubtract(disc(X(cx), Y(cy), r * S))
    letters_l.append(shape)
    for d in L["details"]:
        details_l.append(stroke([(X(x), Y(y)) for x, y in d], ART["detail_width_px"] * S))
letters = union(letters_l)
details = union(details_l)
lb = bbox_mm(letters)

pellets = pcbnew.SHAPE_POLY_SET()
if PELLETS:
    py = 117.3
    x = lb[0] + 3.3
    while x < lb[2] - 9:
        pellets.BooleanAdd(rect(x - 1.1, py - 1.1, x + 1.1, py + 1.1))
        x += 8.8
    pellets.BooleanAdd(disc(lb[2] - 3.4, py, 2.75))            # the power pellet
    pellets.Simplify()

# ---- outline: everything, grown by the maker's margin with round corners -------------------------
MARGIN = ART["outline_margin_px"] * S
band = rect(lb[0], lb[1] - LETTER_DY, lb[2], BOTTOM - MARGIN)     # the outline keeps the maker's shape: it does not follow the moved lettering
body = union([bodies, letters, band])
body.Inflate(FromMM(MARGIN + 1.0), ROUND, ERR)
body.Inflate(-FromMM(1.0), ROUND, ERR)           # rounds the inside corners between the heads so a router bit can cut them
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
bx0, by0, bx1, by1 = bbox_mm(body)
assert abs(by1 - BOTTOM) < 0.02, by1
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f}; feet line y {FEET:.2f}")

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


def place(ref, pos, want):
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` nearest `want[1]`."""
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = min(abs(mm(p.GetPosition())[0] - want[1][0]) + abs(mm(p.GetPosition())[1] - want[1][1])
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
LED_Y = FEET + 2.0                    # LED row: lens tips end about 1 mm below the sprites' feet
DATA_Y = LED_Y + 0.30                 # the data pads' centre line; the data chain runs along it
STRIP_Y = LED_Y - 0.97                # 3.3 V strip between the feet and the LEDs
XIAO_C = (bx1 - 10.48, LED_Y + 0.65 + 0.9 + 1.375 + 8.11)      # USB end flush with the right edge; 0.9 mm below the LED pads
xiao = place("U1", XIAO_C, ("14", (XIAO_C[0] + 7.56, XIAO_C[1] - 8.11)))     # 5V pad: top row, at the USB end
d10, v33, d7 = pp(xiao, "11"), pp(xiao, "12"), pp(xiao, "8")
assert abs(d10[1] - (XIAO_C[1] - 8.11)) < 0.01 and v33[0] > d10[0] > d7[0]

# LED 1 (first in the chain) is under the right-hand ghost, shifted left so the data resistor fits beside it over D10
R1_C = (d10[0] - 0.28, DATA_Y)
LED_X = [SPRITE_CX[4], SPRITE_CX[3], SPRITE_CX[2], SPRITE_CX[1], SPRITE_CX[0]]      # D1 pink ... D5 Pac-Man
LED_X[0] = R1_C[0] - 0.825 - 0.4 - 0.4 - 0.275 - 1.405
led = {}
for i, x in enumerate(LED_X):
    led[i] = place(f"D{i + 1}", (x, LED_Y), ("3", (x + 1.405, DATA_Y)))          # DIN on the right, lens up
    assert abs(pp(led[i], "4")[0] - (x + 0.425)) < 0.01
r1 = place("R1", R1_C, ("2", (R1_C[0] - 0.825, DATA_Y)))
cap = {}
for i in range(4):
    cx_ = (LED_X[i] + LED_X[i + 1]) / 2 - (1.1 if i == 0 else 0)                 # C1 nudged clear of the XIAO's corner
    cap[i] = place(f"C{i + 1}", (cx_, DATA_Y), ("1", (cx_, DATA_Y - 0.775)))     # pad 1 on the 3.3 V strip, pad 2 in the ground copper

CONN = (146.0, 110.2)
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))                # VCC top-left in front view, key slot up
SW = (128.0, BOTTOM - 2.1)
sw = place("SW1", SW, ("1", (SW[0] + 3.0, SW[1] - 1.43)))                       # knob out of the bottom edge
JST = (166.0, BOTTOM - 0.3 - 4.6)
jst = place("J2", JST, ("1", (JST[0] + 1.0, JST[1] - 2.85)))                    # plug goes in from the bottom edge
R2_C, R3_C = (156.5, CONN[1] - 5.0), (156.5, CONN[1] + 4.6)        # just clear of the connector's shroud
r2 = place("R2", R2_C, ("1", (R2_C[0] - 0.825, R2_C[1])))
r3 = place("R3", R3_C, ("1", (R3_C[0] - 0.825, R3_C[1])))

NEW = set(PARTS)
_pad_ok = grown(body, -0.25)      # the switch's hold-down tabs sit 0.27 mm from the edge by design
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# ---- routing (back copper only) -----------------------------------------------------------------
TRACKS = []


def route(net, pts, width=SIG, clear=CLEAR):
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
        TRACKS.append((t, clear, net))


# 3.3 V: strip under the feet, fed from the XIAO's 3V3 pad at the right end, wrapping round the left of the last LED down to the switch
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
WRAP_X = LED_X[4] - 3.5
route("V3V3", [v33, (v33[0] + 0.4, v33[1] - 1.6), (v33[0] + 0.4, STRIP_Y), (WRAP_X, STRIP_Y), (WRAP_X, SW[1] - 3.7), (s3[0], SW[1] - 3.7), s3], PWR)
for i in led:
    vx, vy = pp(led[i], "4")
    route("V3V3", [(vx, vy), (vx, STRIP_Y)], 0.25, 0.2)
gx, gy_ = pp(led[0], "1")                                       # LED 1 sits over the XIAO's pads: its ground runs left along the gap
c1g = pp(cap[0], "2")                                           # ... to C1's ground pad. The other LEDs' ground pads sit straight on the ground copper
route("GND", [(gx, gy_), (gx, c1g[1]), c1g], 0.25)

# LED data chain
route("LED_DATA", [d10, (pp(r1, "1")[0], d10[1] - 0.9), pp(r1, "1")])
route("LED_DIN", [pp(r1, "2"), pp(led[0], "3")])
for i in range(4):
    route(f"LED_D{i + 1}", [pp(led[i], "2"), pp(led[i + 1], "3")], SIG, 0.2)

# badge 3.3 V: connector pin 1 -> switch pin 1
j = {n: pp(conn, n) for n in "123456"}
route("VSAO", [(j["1"][0] - 0.3, j["1"][1] + 0.7), (135.0, j["1"][1] + 0.7), (s1[0], j["1"][1] + 4.7), s1], PWR)

# SAO GPIO1 -> 330R -> D7, along the top
route("SAO_GPIO1", [(j["5"][0] + 0.3, R2_C[1]), pp(r2, "1")])
route("D7_RX", [pp(r2, "2"), (d7[0] - 4.4, R2_C[1]), (d7[0] - 2.9, d7[1]), d7])

# under the LiPo connector: four tracks pass between its signal pads and its hold-down pads
T0 = JST[1] - 1.1 + 0.45
LANE = [T0, T0 + 0.45, T0 + 0.9, T0 + 1.35]                     # SDA, SCL, GPIO2, OFF sense
d4, d5, d6, d1 = pp(xiao, "5"), pp(xiao, "6"), pp(xiao, "7"), pp(xiao, "2")
GAP_Y = (CONN[1] - 0.4, CONN[1] + 0.4)                          # between the connector's two pad rows
route("SDA", [j["3"], (j["3"][0], GAP_Y[0]), (160.5, GAP_Y[0]), (160.5, LANE[0]), (d4[0], LANE[0]), d4])
route("SCL", [j["4"], (j["4"][0], GAP_Y[1]), (159.9, GAP_Y[1]), (159.9, LANE[1]), (d5[0], LANE[1]), d5])
route("SAO_GPIO2", [(j["6"][0] + 0.3, R3_C[1]), pp(r3, "1")])
JR = JST[0] + 4.1                                               # right edge of the connector's right hold-down pad
route("D6_TX", [pp(r3, "2"), (159.3, R3_C[1]), (159.3, LANE[2]), (JR + 1.2, LANE[2]), (JR + 1.2, d6[1]), d6])

# OFF sense: switch pin 2 -> under the switch body -> 1.8 mm above the bottom edge (clear of the panel tab there)
# -> under the LiPo connector -> along the edge below the XIAO's pads -> D1
EDGE_Y = BOTTOM - 0.55
route("OFF_SENSE", [s2, (s2[0], SW[1] + 1.25), (SW[0] + 3.6, SW[1] + 1.25), (SW[0] + 4.3, SW[1] + 0.33), (SW[0] + 6.3, SW[1] + 0.33),
                    (158.7, SW[1] + 0.33), (158.7, LANE[3]), (JR + 0.6, LANE[3]), (JR + 0.6, EDGE_Y), (d1[0], EDGE_Y), d1])

# LiPo +: connector pin 1 -> the C6's battery pad -> the C3 / S3's battery pad
bp6 = pp(xiao, "15", pick=lambda p: p[0])                        # left one = C6 position
bp3 = pp(xiao, "15", pick=lambda p: -p[0])
jp = pp(jst, "1")
route("BAT+", [(jp[0], bp6[1]), bp6, (bp3[0] - 1.95, bp6[1]), (bp3[0] - 1.95, bp3[1]), bp3], 0.3)

# ---- back copper: ground everywhere except behind the sprites ------------------------------------
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(grown(window, 0.35))
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
for t, clear, net in TRACKS:
    if net != "GND":
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
n_keep = 0
for g in xiao.GraphicalItems():                                  # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut, g.GetCenter(), 0.85 + 0.15)
        n_keep += 1
assert n_keep == 8, n_keep
cut.Simplify()
gnd.BooleanSubtract(cut)
gnd.Simplify()

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
for t, clear, net in TRACKS:
    if net == "GND":
        t.TransformShapeToPolygon(gnd_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_pads.Simplify()
eyes_big = grown(eyes, 0.05)
n_gnd = n_art = n_drop = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  GND piece mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
        continue
    inside = pcbnew.SHAPE_POLY_SET(piece)
    inside.BooleanSubtract(eyes_big)
    if area_mm2(inside) < 0.01 and area_mm2(piece) > 0.5:
        add_filled(board, piece, B_Cu)                           # copper behind a ghost's eyes: keeps the eyes dark
        n_art += 1
    else:
        n_drop += 1                                              # a scrap cut off between tracks: left out
        print("  dropped scrap mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper: GND pieces", n_gnd, "eye pieces", n_art, "scraps dropped", n_drop)

# ---- front copper, mask and silkscreen ------------------------------------------------------------
fcu = union([grown(letters, 0.1), grown(pellets, 0.1) if PELLETS else pcbnew.SHAPE_POLY_SET(), pupils])
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
fcu.BooleanSubtract(pegs)
add_filled(board, fcu, F_Cu)
letters_open = pcbnew.SHAPE_POLY_SET(letters)
letters_open.BooleanSubtract(details)                            # the thin lines inside the letters stay under mask
add_filled(board, union([window, letters_open, pellets]), pcbnew.F_Mask)
add_filled(board, window, pcbnew.B_Mask)
ring = grown(bodies, 0.40)
ring.BooleanSubtract(grown(bodies, 0.10))
w_ = pcbnew.SHAPE_POLY_SET(whites)
w_.BooleanSubtract(grown(window, 0.10))
add_filled(board, union([ring, w_]), pcbnew.F_SilkS)

# ---- back silkscreen ------------------------------------------------------------------------------
jn = pp(jst, "2")
LABELS = [("SAO", s1[0] + 1.3, SW[1] - 3.0, 0.8, 0), ("OFF", SW[0], SW[1] - 3.0, 0.8, 0), ("USB/BAT", pp(sw, "4")[0] - 2.6, SW[1] - 3.0, 0.8, 0),
          ("+", jp[0] + 0.1, JST[1] - 5.5, 1.2, 0), ("-", jn[0] - 0.1, JST[1] - 5.5, 1.2, 0), ("LiPo 3.7V", JST[0], JST[1] - 7.0, 0.8, 0),
          ("1", CONN[0] - 8.7, j["1"][1], 0.9, 0),
          ("HACK-MAN SAO", 117.0, 104.6, 1.1, 0), ("by InstantArcade (Bob)", 117.0, 106.5, 0.8, 0),
          ("SAO++ rA", 117.0, 108.6, 0.9, 0), ("XIAO ESP32 C3/S3/C6", 117.0, 110.4, 0.8, 0),
          ("USB: NOT ON 'SAO'", 117.0, 112.2, 0.8, 0)]
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

# ---- report ---------------------------------------------------------------------------------------
print("U1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in xiao.Pads() if p.GetNumber() in ("1", "7", "8", "14")}, "BAT+", bp6, bp3)
print("LED x:", [round(x, 2) for x in LED_X], "row y", round(LED_Y, 2))
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
