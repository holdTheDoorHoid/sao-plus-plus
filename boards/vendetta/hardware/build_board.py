#!/usr/bin/env python3
"""Rebuild vendetta.kicad_pcb from davedarko's 2022 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/vendetta/hardware/build_board.py

What it does
  - loads original/VendettaSAO/VendettaSAO.kicad_pcb (KiCad 6, September 2022), the newest of the maker's files
  - cuts the maker's parts (header, EEPROM, capacitor, four resistors), tracks, via, copper pour, the outline
    footprint, the four A0/A1/A2/WP labels and the "JLCJLCJLCJLC" order-number placeholder out of the file text
  - scales the whole design up by SCALE (outline, mask art, quote, logo and credit together, same proportions):
    at the original 34.4 x 45.7 mm the cell clip, the connector, the quote, the logo and the credit do not all fit
    (owner rule 2026-11-12: scale up rather than move a credit or overhang the cell)
  - turns the board over: the maker drew the mask on the BACK silkscreen and put the parts, the quote and his credit
    on the front. SAO++ wants the art on the front, so the mask becomes the front and the quote and credit the back
  - places the SAO++ parts on the back and routes them on the back copper, which is otherwise GND

Placement is worked out in "back view" coordinates: the maker's own front-view coordinates (his parts side), scaled
about O. That is how the back looks when you hold it. KiCad's front view is the mirror: x_kicad = 2 * O.x - x_back.
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, blocks, cut_blocks,  # noqa: E402
                         bbox_mm, add_filled, pad_poly)
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "vendetta"
LOCAL = load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "VendettaSAO", "VendettaSAO.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

SCALE = 1.23        # smallest factor (in 0.01 steps) at which clip, cell and connector clear the quote, logo and credit
O = (25.4, 25.0)    # scaling centre and mirror line (x = 25.4), in the maker's coordinates
CLEAR = 0.25        # copper-to-copper gap cut into the GND copper
TRACK = 0.25
EDGE = 0.55         # GND copper stops this far short of the board edge (panel mouse bites reach 0.25 mm in)


def S(x, y):
    """maker's coordinates -> scaled back-view coordinates"""
    return (O[0] + SCALE * (x - O[0]), O[1] + SCALE * (y - O[1]))


def K(x, y):
    """back-view coordinates -> KiCad front-view coordinates"""
    return (round(2 * O[0] - x, 4), round(y, 4))


def KP(x, y):
    return P(*K(x, y))


# ---- strip the maker's electrical parts, outline and labels out of the file text -----------------
_txt = open(SRC, encoding="utf-8").read()
_cut = list(blocks(_txt, "segment")) + list(blocks(_txt, "via")) + list(blocks(_txt, "zone"))
_gone = []
for a_, b_ in blocks(_txt, "footprint"):
    s_ = _txt[a_:b_]
    m = re.search(r'\(fp_text reference "([^"]+)"', s_)
    if m and m.group(1) in ("J1", "U1", "R1", "R2", "R3", "R4", "C1"):
        _cut.append((a_, b_))
        _gone.append(m.group(1))
    elif "vendettaSAO_outline" in s_[:120]:
        _cut.append((a_, b_))
        _gone.append("outline")
assert sorted(_gone) == ["C1", "J1", "R1", "R2", "R3", "R4", "U1", "outline"], _gone
_labels = 0
for a_, b_ in blocks(_txt, "gr_text"):
    m = re.match(r'\s*\(gr_text "([^"]*)"', _txt[a_:b_])
    if m.group(1) in ("A0", "A1", "A2", "WP", "JLCJLCJLCJLC"):
        _cut.append((a_, b_))
        _labels += 1
assert _labels == 5, _labels
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "vendetta.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []

# ---- outline: the maker's 299 Edge.Cuts lines chained into one loop, scaled and mirrored -------------------
def maker_outline():
    """Chain the 299 Edge.Cuts lines of the maker's outline footprint into one closed loop (maker's coordinates).
    tools/extract_outline.py cannot be used: KiCad's board-outline builder rejects this footprint outline."""
    src = pcbnew.LoadBoard(SRC)
    segs = []
    for fp in src.GetFootprints():
        if fp.GetFPID().GetUniStringLibItemName() == "vendettaSAO_outline":
            for g in fp.GraphicalItems():
                if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == pcbnew.Edge_Cuts:
                    assert g.GetShape() == pcbnew.SHAPE_T_SEGMENT
                    segs.append((mm(g.GetStart()), mm(g.GetEnd())))
    assert len(segs) == 299, len(segs)
    loop = [segs[0][0], segs[0][1]]
    rest = segs[1:]
    while rest:
        end = loop[-1]
        i = min(range(len(rest)), key=lambda k: min(math.dist(end, rest[k][0]), math.dist(end, rest[k][1])))
        a, b = rest.pop(i)
        gap = min(math.dist(end, a), math.dist(end, b))
        assert gap < 0.002, f"outline gap {gap:.4f} mm"
        loop.append(b if math.dist(end, a) <= math.dist(end, b) else a)
    assert math.dist(loop[0], loop[-1]) < 0.002
    return loop[:-1]


_ol = maker_outline()
BACK_OUTLINE = [S(x, y) for x, y in _ol]
outline_k = [K(x, y) for x, y in BACK_OUTLINE]
json.dump({"outer": [list(p) for p in outline_k], "holes": [], "note": "generated by build_board.py"},
          open(os.path.join(HERE, "outline.json"), "w"))
body = poly(outline_k)
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(outline_k))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)
_bb = body.BBox()
SIZE = (ToMM(_bb.GetWidth()), ToMM(_bb.GetHeight()))
print("board %.2f x %.2f mm (x %.2f..%.2f, y %.2f..%.2f)" % (SIZE + (ToMM(_bb.GetLeft()), ToMM(_bb.GetRight()), ToMM(_bb.GetTop()), ToMM(_bb.GetBottom()))))


def edge_x(y, side):
    """x (back view) where the outline crosses height y; side -1 = left, +1 = right (back view)"""
    xs = []
    for (x1, y1), (x2, y2) in zip(BACK_OUTLINE, BACK_OUTLINE[1:] + BACK_OUTLINE[:1]):
        if (y1 - y) * (y2 - y) <= 0 and y1 != y2:
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    return min(xs) if side < 0 else max(xs)


# ---- art: scale the mask, the logo and both texts about O, then turn everything over ----------------
def scale_footprint(fp):
    shapes = []
    for it in fp.GraphicalItems():
        if it.GetClass() == "PCB_SHAPE" and it.GetShape() == pcbnew.SHAPE_T_POLY:
            ps = it.GetPolyShape()
            outl = []
            for k in range(ps.OutlineCount()):
                c = ps.Outline(k)
                outl.append([S(ToMM(c.CPoint(i).x), ToMM(c.CPoint(i).y)) for i in range(c.PointCount())])
            shapes.append((it, outl))
        elif it.GetClass() == "PCB_SHAPE":
            raise AssertionError("unexpected non-polygon art item")
    px, py = mm(fp.GetPosition())
    fp.SetPosition(P(*S(px, py)))
    for it, outl in shapes:
        ps = pcbnew.SHAPE_POLY_SET()
        for pts in outl:
            ps.NewOutline()
            for x, y in pts:
                ps.Append(FromMM(x), FromMM(y))
        it.SetPolyShape(ps)
        it.SetWidth(FromMM(ToMM(it.GetWidth()) * SCALE))
    return len(shapes)


ART = None
LOGO = None
for fp in board.GetFootprints():
    name = fp.GetFPID().GetUniStringLibItemName()
    if name == "vendettaSAO":
        ART = fp
    elif name == "davedarko_logo_silk_outline":
        LOGO = fp
assert ART and LOGO
print("mask art polygons scaled:", scale_footprint(ART), "; logo polygons:", scale_footprint(LOGO))
TEXTS = {}
for d in board.GetDrawings():
    if d.GetClass() == "PCB_TEXT":
        x, y = mm(d.GetPosition())
        d.SetPosition(P(*S(x, y)))
        d.SetTextSize(VECTOR2I(FromMM(ToMM(d.GetTextSize().x) * SCALE), FromMM(ToMM(d.GetTextSize().y) * SCALE)))
        d.SetTextThickness(FromMM(ToMM(d.GetTextThickness()) * SCALE))
        TEXTS["quote" if "Remember" in d.GetText() else "credit"] = d
assert sorted(TEXTS) == ["credit", "quote"], TEXTS
MIRROR = P(O[0], 0)
for fp in (ART, LOGO):
    fp.Flip(MIRROR, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
for d in TEXTS.values():
    d.Flip(MIRROR, pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
assert ART.GetLayer() == pcbnew.F_Cu and LOGO.GetLayer() == B_Cu
assert all(d.GetLayer() == B_SilkS for d in TEXTS.values())
for fp in (ART, LOGO):          # art footprints have no schematic symbol: board-only
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)


def back_bbox(item, fp=False):
    b = item.GetBoundingBox(False) if fp else item.GetBoundingBox()
    x0, x1 = 2 * O[0] - ToMM(b.GetRight()), 2 * O[0] - ToMM(b.GetLeft())
    return (x0, ToMM(b.GetTop()), x1, ToMM(b.GetBottom()))


KEEP = {"quote": back_bbox(TEXTS["quote"]), "credit": back_bbox(TEXTS["credit"]), "logo": back_bbox(LOGO, True)}
for k, v in KEEP.items():
    print("back art %-6s x %.2f..%.2f y %.2f..%.2f (back view)" % ((k,) + (v[0], v[2], v[1], v[3])))
_ab = ART.GetBoundingBox(False)
print("front art x %.2f..%.2f y %.2f..%.2f" % (ToMM(_ab.GetLeft()), ToMM(_ab.GetRight()), ToMM(_ab.GetTop()), ToMM(_ab.GetBottom())))

# ---- the circuit (shared with the schematic generator) ------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p["ref"]: p for p in CIRCUIT["parts"]}
PADNETS = {r: p.get("nets", {}) for r, p in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for r, p in PARTS.items()}
DNP = ("R1", "R2", "R3", "R4")          # the maker's address / write-protect straps, not fitted (see circuit.json)
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
    if ref in DNP:
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_DNP | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)


def load(ref, pos_back):
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name} in {LIBS[lib]}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(KP(*pos_back))
    fp.Flip(KP(*pos_back), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
    return fp


def padpos(fp, num):
    """pad centre in back-view coordinates"""
    x, y = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]
    return (round(2 * O[0] - x, 3), y)


def place(ref, pos, want):
    """Place on the back at `pos` (back view); pick the right-angle rotation that puts pad want[0] at want[1] (back view)."""
    fp = load(ref, pos)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        px, py = padpos(fp, want[0])
        d = abs(px - want[1][0]) + abs(py - want[1][1])
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.05, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.2f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


# ---- placement (back view: how the back looks in your hand, x grows right, y grows down) ----------
BAT = (O[0], 20.3)              # cell under the quote, open side up toward the quote (the cell slides in from the top)
CONN = (23.2, 38.6)             # connector below the clip, between the logo (left) and the credit (right): as low as
                                # the credit allows, 1.7 mm below the clip body, 2.2 mm left of centre
SWY = 17.0                      # switch on the left edge (back view), knob out of the side
SW = (round(edge_x(SWY, -1) + 2.37, 3), SWY)
U1C = (41.4, 22.0)              # EEPROM in the right-hand strip beside the cell
RCOL = {"R1": (43.1, 13.4), "R2": (41.5, 13.4), "R3": (39.9, 13.4)}   # address straps in a row above A0 / A1 / A2
R4C = (42.035, 28.3)            # write-protect strap straight below WP
C1C = (38.0, 13.0)              # supply capacitor between the clip and the straps, on the supply line
D1C = (11.5, 20.0)              # cell diode on the line from switch pin 4 to the clip's left pad

FP = {}
# connector: VCC (pin 1) top right in back view = top left in KiCad's front view; key slot up
FP["J1"] = place("J1", CONN, ("1", (CONN[0] + 2.54, CONN[1] - 3.4)))
# switch: pins face into the board, knob out of the left edge (back view); pin 1 at the top (the only way round on this side)
FP["SW1"] = place("SW1", SW, ("1", (SW[0] + 1.43, SW[1] - 3.0)))
# EEPROM with its pin rows across the board: top row A0 A1 A2 GND (right to left), bottom row SDA SCL WP VCC (left to right)
FP["U1"] = place("U1", U1C, ("1", (U1C[0] + 1.905, U1C[1] - 3.5875)))
for ref, (x, y) in RCOL.items():
    FP[ref] = place(ref, (x, y), ("1", (x, y - 0.825)))                        # supply end up
FP["R4"] = place("R4", R4C, ("2", (R4C[0], R4C[1] - 0.825)))                   # WP end up, supply end down
FP["C1"] = place("C1", C1C, ("1", (C1C[0], C1C[1] - 0.775)))                   # supply up, GND down
FP["D1"] = place("D1", D1C, ("1", (D1C[0] - 0.7, D1C[1])))                    # cathode toward the switch, anode toward the cell
u = {n: padpos(FP["U1"], n) for n in "12345678"}

# battery: both clip pads are "1"; choose the angle by where the open side faces (up, toward the quote)
bat = load("BT1", BAT)
FP["BT1"] = bat


def _open_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    kx, ky = K(*BAT)
    return math.degrees(math.atan2(ky - ToMM(c.y), kx - ToMM(c.x)))


for _rot in (0, 90, 180, 270):
    if abs((_open_dir(_rot) - (-90) + 180) % 360 - 180) < 1:
        break
else:
    raise AssertionError("no right-angle rotation turns the clip's open side up")
_bpads = sorted([(round(2 * O[0] - mm(p.GetPosition())[0], 3), mm(p.GetPosition())[1]) for p in bat.Pads() if p.GetNumber() == "1"])
assert abs(_bpads[0][1] - BAT[1]) < 0.01 and abs(_bpads[1][1] - BAT[1]) < 0.01, "clip pads are not across the board"
bat.SetOrientationDegrees(_rot - 0.1)        # KiCad 10 calls the clip's courtyard "malformed" at exact right angles
link(bat, "BT1")
bat.SetDuplicatePadNumbersAreJumpers(True)    # the clip joins its two "+" pads; only the left one is routed
for it in bat.GraphicalItems():               # its silk arrow and "+" would land on the quote: fab layer only
    if it.GetLayer() == B_SilkS:
        it.SetLayer(pcbnew.B_Fab)
BT_L, BT_R = _bpads                           # back view: left and right "+" pads
print("clip pads (back view)", _bpads)

NEW = set(PARTS)

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
    print(ref, "rot", round(fp.GetOrientationDegrees(), 1), "pads (back view)",
          {p.GetNumber(): padpos(fp, p.GetNumber()) for p in fp.Pads() if p.GetNumber()})

if os.environ.get("PLACE_ONLY"):
    pcbnew.SaveBoard(OUT, board)
    sys.exit(0)



# ---- routing (back copper only, no vias). Waypoints in back view ----------------------------------------
def route(net, pts, width=TRACK, clear=CLEAR):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(KP(*a))
        t.SetEnd(KP(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear))


sw = {n: padpos(FP["SW1"], n) for n in "1234"}
j = {n: padpos(FP["J1"], n) for n in "1234"}
r = {ref: {n: padpos(FP[ref], n) for n in "12"} for ref in ("R1", "R2", "R3", "R4", "C1", "D1")}
I2C = 0.2
TOP_SAO, TOP_LOAD = 10.45, 10.95     # the two tracks over the top of the cell, just under the quote's bbox (10.04)
X_SAO_L, X_LOAD_L = 11.9, 12.6       # where they rise beside the switch
X_LOAD_R, X_SAO_R = 44.2, 44.75      # where they come down on the right (VSAO outermost)
Y_SDA, Y_SCL, Y_SAO = 29.6, 30.1, 30.6   # the run under the clip, between the cell and the connector
X_SCL_J = CONN[0] + 1.27                       # between connector pins 3 and 1

# badge 3.3 V: switch pin 1 -> up, over the cell, down the right edge, under the clip -> connector pin 1
route("VSAO", [sw["1"], (X_SAO_L, sw["1"][1]), (X_SAO_L, TOP_SAO), (X_SAO_R, TOP_SAO), (X_SAO_R, Y_SAO - 0.75),
               (X_SAO_R - 0.75, Y_SAO), (j["1"][0], Y_SAO), (j["1"][0], j["1"][1] - 1.3)])     # corner cut: the edge curves in
# switched supply: switch pin 3 -> over the cell (inside the VSAO track) -> capacitor, straps, down to VCC and R4
route("VLOAD", [sw["3"], (X_LOAD_L, sw["3"][1]), (X_LOAD_L, TOP_LOAD), (X_LOAD_R, TOP_LOAD), (X_LOAD_R, u["8"][1]), u["8"]])
route("VLOAD", [u["8"], (u["8"][0], r["R4"]["1"][1]), r["R4"]["1"]])
for ref in ("C1", "R3", "R2", "R1"):
    route("VLOAD", [(r[ref]["1"][0], TOP_LOAD), r[ref]["1"]])
# cell: switch pin 4 -> D1 cathode; D1 anode -> clip's left "+" pad
route("VBAT", [sw["4"], r["D1"]["1"]])
route("VCELL", [r["D1"]["2"], (BT_L[0] - 0.3, r["D1"]["2"][1])])
# address and write-protect straps
for net, ref, pin in (("A0", "R1", "1"), ("A1", "R2", "2"), ("A2", "R3", "3")):      # short jogs from the row to the pins
    route(net, [r[ref]["2"], (r[ref]["2"][0], 15.3), (u[pin][0], 16.6), u[pin]])
route("WP", [r["R4"]["2"], u["7"]])
# I2C: connector pins 3 / 4 -> under the clip -> up into the EEPROM's SDA / SCL
route("SDA", [(j["3"][0], j["3"][1] - 0.8), (j["3"][0], Y_SDA), (u["5"][0], Y_SDA), u["5"]], width=I2C)
route("SCL", [(j["4"][0], j["4"][1] - 1.6), (j["4"][0], CONN[1]), (X_SCL_J, CONN[1]), (X_SCL_J, Y_SCL), (u["6"][0], Y_SCL), u["6"]],
      width=I2C)


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
gnd_pads.Simplify()
pieces = []
for i in range(back.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(back.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    g = area_mm2(both) > 0.01
    pieces.append((piece, g))
    if not g:
        continue                       # copper with no GND pad in it would float: leave that patch bare
    add_filled(board, piece, B_Cu, nets["GND"])
print("back copper pieces (area mm2, bbox, GND?):", [(round(area_mm2(p), 1), [round(v, 1) for v in bbox_mm(p)], g) for p, g in pieces])

# ---- back silkscreen labels (back view positions; text mirrored so it reads from the back) ---------
LABELS = [("SAO", 6.9, 9.9, 0.8, 0), ("BAT", 6.9, 24.1, 0.8, 0), ("OFF", 10.25, 17.0, 0.8, 90),
          ("CR2032", 9.6, 26.9, 0.8, 0), ("+ UP", 9.6, 28.1, 0.8, 0),
          ("A2 A1 A0", 41.5, 16.0, 0.8, 0), ("WP", 44.0, 27.9, 0.8, 90),
          ("SAO++ rA", 12.3, 39.5, 0.8, 0)]
for txt, x, y, size, rot in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(KP(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(max(0.12, size * 0.15)))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)

# ---- design settings and save ---------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
board.GetTitleBlock().SetComment(1, "Scaled x%.2f from the maker's 34.4 x 45.7 mm to %.1f x %.1f mm" % ((SCALE,) + SIZE))
pcbnew.SaveBoard(OUT, board)

# Board colours for the renders: white solder mask with black silkscreen, so the front reads as the mask (white face,
# black brows, eyes and moustache) the way the maker's halftone is drawn. KiCad 10's Python cannot set the stackup,
# so it is written into the saved file. The maker's files do not record his colours; this is the reading of the art.
_pcb = open(OUT, encoding="utf-8").read()
assert "(stackup" not in _pcb
_stack = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "Black"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "White") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "White") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "Black"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""
_pcb = _pcb.replace("\t(setup\n", "\t(setup\n" + _stack, 1)
open(OUT, "w", encoding="utf-8").write(_pcb)
print("saved", OUT)
