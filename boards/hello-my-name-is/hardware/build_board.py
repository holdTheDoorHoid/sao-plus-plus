#!/usr/bin/env python3
"""Build hello-my-name-is.kicad_pcb from davedarko's "Hello My Name Is" SAO (blinkyparts-style version), scaled 1.1x.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/hello-my-name-is/hardware/build_board.py

The original is a 40 x 34 mm rounded rectangle. At that size the CR2032 clip, the SAO connector, the switch, the
maker's credit and four corner LEDs do not all fit (see README), so the whole board is scaled up 1.1x, uniformly, to
44.0 x 37.4 mm (owner rule of 2026-11-12). Everything is read from the untouched original and multiplied by SCALE
about the original's origin:
  front  - "HELLO" and "my name is" in Comic Sans (the glyph outlines the maker's KiCad stored with the text, so the
           lettering does not depend on the font being installed), davedarko's logo, the bare-board name window
           (no copper, no mask) and copper everywhere else under the mask, as in the original
  back   - the maker's credit and his "JLCJLCJLCJLC" order-number marker, plus the SAO++ parts, routed on the back
           copper only (no vias), with the rest of the back copper as the GND net
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import re
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_Cu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "hello-my-name-is"
SRC = os.path.join(HERE, "..", "original", "henlo_blinkyparts_style", "henlo_blinkyparts_style.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

SCALE = 1.1         # whole board, outline and art together
W, H, R = 40.0 * SCALE, 34.0 * SCALE, 3.0 * SCALE      # the maker's 40 x 34 mm board with 3 mm corners
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PWR = 0.40          # supply track width
SIG = 0.30          # LED anode track width
NAME_FINISH = "bare"  # the name window: "bare" = bare board as the maker drew it; "white" = solid white silkscreen like a paper name tag
WINDOW = 1.6        # radius kept free of copper on both sides around each LED centre so its light gets through


def S(v):
    return round(v * SCALE, 4)


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def rounded_rect(x0, y0, x1, y1, r, n=24):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((round(cx + r * math.cos(a), 4), round(cy + r * math.sin(a), 4)))
    return poly(pts)


# ---- art read from the untouched original --------------------------------------------------------
_txt = open(SRC, encoding="utf-8").read()


def render_cache(text):
    """The glyph outlines KiCad stored with a text item (one polygon per glyph), scaled."""
    m = re.search(r'\(render_cache "' + re.escape(text) + r'" 0(.*?)\n\t\t\)\n\t\)', _txt, re.S)
    assert m, text
    out = pcbnew.SHAPE_POLY_SET()
    for pm in re.finditer(r"\(polygon\s*\(pts(.*?)\)\s*\)", m.group(1), re.S):
        pts = [(S(float(a)), S(float(b))) for a, b in re.findall(r"\(xy ([-0-9.]+) ([-0-9.]+)\)", pm.group(1))]
        out.Append(poly(pts))
    return out


hello = render_cache("HELLO")
myname = render_cache("my name is")
assert hello.OutlineCount() == 5 and myname.OutlineCount() == 9, (hello.OutlineCount(), myname.OutlineCount())
lettering = pcbnew.SHAPE_POLY_SET(hello)
lettering.Append(myname)
lettering.Simplify()

_orig = pcbnew.LoadBoard(SRC)
logo = pcbnew.SHAPE_POLY_SET()
for fp in _orig.GetFootprints():
    if "logo" in str(fp.GetFPID().GetLibItemName()):
        for it in fp.GraphicalItems():
            if it.GetLayer() == pcbnew.F_SilkS and it.GetShape() == pcbnew.SHAPE_T_POLY:
                ps = it.GetPolyShape()
                for i in range(ps.OutlineCount()):
                    o = ps.Outline(i)
                    logo.Append(poly([(S(ToMM(o.CPoint(k).x)), S(ToMM(o.CPoint(k).y))) for k in range(o.PointCount())]))
assert logo.OutlineCount() == 3, logo.OutlineCount()
TEXTS = {}
for d in _orig.GetDrawings():
    if d.GetClass() == "PCB_TEXT":
        TEXTS[d.GetText().split("\n")[0]] = d
assert set(TEXTS) == {"HELLO", "my name is", "JLCJLCJLCJLC", "@davedarko 2024/09"}, set(TEXTS)

# the name window: the maker's mask opening (both sides) and copper keep-out (both layers), scaled
NAME_MASK = rect(S(1.0), S(10.5), S(39.0), S(26.5))
NAME_KEEPOUT = rect(S(0.75), S(10.25), S(39.25), S(26.75))

board = pcbnew.CreateEmptyBoard()
body = rounded_rect(0, 0, W, H, R)
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


def load(ref, pos):
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    return fp


def place(ref, pos, want, angles=(0, 90, 180, 270)):
    """Place on the back, then pick the rotation that puts pad `want[0]` nearest `want[1]`."""
    fp = load(ref, pos)
    best = None
    for rot in angles:
        fp.SetOrientationDegrees(rot)
        d = min(math.hypot(mm(p.GetPosition())[0] - want[1][0], mm(p.GetPosition())[1] - want[1][1])
                for p in fp.Pads() if p.GetNumber() == want[0])
        if best is None or d < best[0]:
            best = (d, rot)
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp, best[0]


def pp(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


# ---- placement ----------------------------------------------------------------------------------
CREDIT_BOTTOM = S(10.27)        # lowest ink of the maker's back credit (measured on the original: y 10.27 mm)
BAT = (11.8, 23.15)             # cell: open side at the left edge (it slides in from there), closed end toward the connector
CONN = (31.5, 24.5)             # the cell takes the left half, so the connector sits right of centre
SW = (29.5, H - 2.4)            # bottom edge, knob down; the knob ends about 0.7 mm past the edge
# LEDs: the maker's four corner positions, scaled, at the maker's 45-degree angles. The second pair of numbers is a
# point the anode should face (toward its resistor).
LEDS = {"D1": ((S(5.0125), S(5.5)), 45, (8.0, 3.0)),
        "D2": ((S(35.0), S(5.4875)), -45, (41.0, 9.0)),
        "D3": ((S(5.0), S(30.0125)), 135, (1.0, 32.0)),
        "D4": ((S(34.948179), S(30.551821)), -135, (42.0, 31.0))}
RES = {"R1": (8.9, 5.8, -1), "R2": (41.4, 9.6, +1), "R3": (0.98, 7.5, -1), "R4": (42.45, 29.8, -1)}   # -1: pad 1 (VLOAD) on top

conn, miss = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))      # VCC: top row, left in front view (as Mad Cat)
assert miss < 0.05, miss
sw, miss = place("SW1", SW, ("1", (SW[0] + 3.0, SW[1] - 1.43)))           # badge contact on the right, cell contact on the left
assert miss < 0.05, miss
led, res = {}, {}
for ref, (c, ang, toward) in LEDS.items():
    led[ref], _ = place(ref, c, ("2", toward), (ang, ang + 180))
for ref, (x, y, up) in RES.items():
    res[ref], miss = place(ref, (x, y), ("1", (x, y + up * 0.825)))
    assert miss < 0.05, (ref, miss)

# battery: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


for _rot in (0, 90, 180, 270):
    if abs(((_closed_dir(_rot) - 0) + 180) % 360 - 180) < 1:
        break
else:
    raise SystemExit("no clip angle puts the closed end toward +x")
bat.SetOrientationDegrees(_rot)
for g in list(bat.GraphicalItems()):          # the clip's own silk arrow and '+' land on the lettering: keep them on the fab layer
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)
link(bat, "BT1")
bt = sorted([mm(p.GetPosition()) for p in bat.Pads() if p.GetNumber() == "1"], key=lambda p: p[1])
bt_top, bt_bot = bt
_clip_box = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and hasattr(g, "GetShape") and g.GetShape() == pcbnew.SHAPE_T_RECT][0].GetBoundingBox()
print("clip body x %.2f..%.2f y %.2f..%.2f" % tuple(ToMM(v) for v in (_clip_box.GetLeft(), _clip_box.GetRight(), _clip_box.GetTop(), _clip_box.GetBottom())))
assert ToMM(_clip_box.GetTop()) > CREDIT_BOTTOM + 0.3, "clip covers the maker's credit"
CELL_R = 10.0
for ref, fp in led.items():
    for pad in fp.Pads():
        o = pad_poly(pad, B_Cu)
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            dmin = min(math.hypot(ToMM(ch.CPoint(k).x) - BAT[0], ToMM(ch.CPoint(k).y) - BAT[1]) for k in range(ch.PointCount()))
            assert dmin > CELL_R + 0.35, f"{ref} pad sits under the coin cell ({dmin:.2f} mm from its centre)"
            if dmin < CELL_R + 2:
                print(ref, "pad is %.2f mm outside the coin cell's edge" % (dmin - CELL_R))
    print(ref, "centre", mm(fp.GetPosition()), "angle", fp.GetOrientationDegrees(), "anode", pp(fp, "2"), "cathode", pp(fp, "1"))

NEW = set(PARTS)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(grown(body, -0.25))
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# ---- routing (back copper only) -----------------------------------------------------------------
TRACKS = []


def route(net, pts, width=PWR):
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


j1 = pp(conn, "1")
s1, s3, s4 = pp(sw, "1"), pp(sw, "3"), pp(sw, "4")
assert s4[0] < s3[0] < s1[0], (s1, s3, s4)
r1 = {r: pp(fp, "1") for r, fp in res.items()}
r2 = {r: pp(fp, "2") for r, fp in res.items()}
an = {d: pp(fp, "2") for d, fp in led.items()}
TOP = 3.18          # the corridor between the maker's "JLCJLCJLCJLC" marker and his credit
RIGHT = 43.0        # down the right edge
MID = 27.65         # between the clip's closed end and the connector's left column
OVER = 16.5         # above the connector

# badge 3.3 V: connector pin 1 -> up, round the right of the connector -> down to the switch's right-hand contact
route("VSAO", [j1, (j1[0], 17.4), (35.3, 17.4), (35.3, 31.4), (s1[0], 31.4), s1])

# coin cell +: link the two clip pads round the closed end (the clip joins them too; this makes the board agree
# without relying on it), then from that link to the switch's left-hand contact
_r = math.hypot(bt_top[0] - BAT[0], bt_top[1] - BAT[1])
arc = [(round(BAT[0] + _r * math.cos(math.radians(a)), 4), round(BAT[1] + _r * math.sin(math.radians(a)), 4)) for a in range(-90, 91, 10)]
route("VBAT", [bt_top] + arc[1:-1] + [bt_bot])
tap = arc[13]                                    # 40 degrees below the closed end
route("VBAT", [tap, (25.0, tap[1]), (s4[0], tap[1] + (s4[0] - 25.0)), s4])

# switched supply: switch centre contact -> up between clip and connector -> over the connector -> right edge,
# down to R4 and up to R2 -> along the top corridor to R1 -> R3 at the left edge
route("VLOAD", [s3, (s3[0], 31.6), (MID, 31.0), (MID, OVER), (RIGHT, OVER), (RIGHT, r1["R4"][1]), r1["R4"]])
route("VLOAD", [(RIGHT, OVER), (RIGHT, 5.0), (41.2, TOP), (r1["R1"][0], TOP), r1["R1"]])
route("VLOAD", [(r1["R2"][0], r1["R2"][1]), (RIGHT, r1["R2"][1])])
route("VLOAD", [(r1["R1"][0], TOP), (3.6, TOP), (r1["R3"][0], 5.3), r1["R3"]])

# each resistor to its LED's anode
route("LED1_A", [r2["R1"], an["D1"]], SIG)
route("LED2_A", [r2["R2"], an["D2"]], SIG)
route("LED3_A", [r2["R3"], (r2["R3"][0], 31.6), an["D3"]], SIG)
route("LED4_A", [r2["R4"], (r2["R4"][0], 31.2), an["D4"]], SIG)

# no track may run through the maker's back credit or his order-number marker
for key in ("@davedarko 2024/09", "JLCJLCJLCJLC"):
    t = TEXTS[key]
    bb = t.GetBoundingBox()
    box = rect(S(ToMM(bb.GetLeft())), S(ToMM(bb.GetTop())), S(ToMM(bb.GetRight())), S(ToMM(bb.GetBottom())))
    for tr in TRACKS:
        tp = pcbnew.SHAPE_POLY_SET()
        tr.TransformShapeToPolygon(tp, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
        tp.BooleanIntersection(box)
        assert area_mm2(tp) < 1e-4, f"a {tr.GetNetname()} track runs under '{key}'"

# ---- back copper: GND everywhere else ------------------------------------------------------------
gnd = pcbnew.SHAPE_POLY_SET(inner)
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
for t in TRACKS:
    t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for ref, (c, _a, _t) in LEDS.items():
    add_circle(cut, P(*c), WINDOW)
cut.Simplify()
gnd.BooleanSubtract(cut)
gnd.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
gnd_pads.Simplify()
n_gnd = n_drop = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  GND piece mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    elif area_mm2(piece) > 5:
        add_filled(board, piece, B_Cu)              # the strip above the top corridor: plain copper, so the back looks even
        n_drop += 1
        print("  plain copper (no net) mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    else:
        n_drop += 1
        print("  dropped scrap mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper: GND pieces", n_gnd, "other pieces", n_drop)

# ---- front: copper under the mask everywhere except the name window, the LED spots and the switch pegs ----
front = pcbnew.SHAPE_POLY_SET(inner)
fcut = pcbnew.SHAPE_POLY_SET(NAME_KEEPOUT)
for ref, (c, _a, _t) in LEDS.items():
    add_circle(fcut, P(*c), WINDOW)
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(fcut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
fcut.Simplify()
front.BooleanSubtract(fcut)
front.Simplify()
add_filled(board, front, F_Cu)
add_filled(board, NAME_MASK, pcbnew.F_Mask)          # the name window: bare board on the front, as the maker drew it
fsilk = pcbnew.SHAPE_POLY_SET(lettering)
fsilk.Append(logo)
if NAME_FINISH == "white":
    fsilk.Append(grown(NAME_MASK, -0.3))
else:
    assert NAME_FINISH == "bare", NAME_FINISH
fsilk.Simplify()
add_filled(board, fsilk, pcbnew.F_SilkS)


# ---- back silkscreen: the maker's two texts, scaled, plus the SAO++ labels -------------------------
def copy_text(src):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(src.GetText())
    t.SetLayer(B_SilkS)
    pos = src.GetTextPos()
    t.SetTextPos(P(S(ToMM(pos.x)), S(ToMM(pos.y))))
    sz = src.GetTextSize()
    t.SetTextSize(VECTOR2I(FromMM(S(ToMM(sz.x))), FromMM(S(ToMM(sz.y)))))
    t.SetTextThickness(FromMM(S(ToMM(src.GetTextThickness()))))
    t.SetHorizJustify(src.GetHorizJustify())
    t.SetVertJustify(src.GetVertJustify())
    t.SetMirrored(True)
    board.Add(t)
    return t


credit = copy_text(TEXTS["@davedarko 2024/09"])
jlc = copy_text(TEXTS["JLCJLCJLCJLC"])
for t in (credit, jlc):
    bb = t.GetBoundingBox()
    print(repr(t.GetText()[:20]), "x %.2f..%.2f y %.2f..%.2f" % (ToMM(bb.GetLeft()), ToMM(bb.GetRight()), ToMM(bb.GetTop()), ToMM(bb.GetBottom())))

LABELS = [("BAT", s4[0] - 0.2, s4[1] - 2.55, 0.8, 0), ("OFF", SW[0], s4[1] - 2.55, 0.8, 0), ("SAO", s1[0] + 0.2, s1[1] - 2.55, 0.8, 0),
          ("CR2032 + SIDE UP", 32.6, 12.5, 0.8, 0), ("HELLO MY NAME IS  SAO++ rA", 32.6, 13.8, 0.8, 0),
          ("best on badge power", 32.6, 15.1, 0.8, 0)]
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
print("board %.2f x %.2f mm (scale %.2f)" % (W, H, SCALE))
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", bt, "clip angle", _rot)
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
