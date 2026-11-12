#!/usr/bin/env python3
"""Build gpio-16.kicad_pcb: a NEW layout for AND!XOR's DC27 "MCP23017 16 GPIO Reference Design".

The maker published a schematic picture and a parts list, no board. The circuit is the maker's (hardware/circuit.json,
read from original/mcp23017.png); the outline, the placement, the routing and the lettering are all SAO++'s own.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/gpio-16/hardware/build_board.py

Layout (front view, x grows right, y grows down, board centred on 0, 0):
  - 31.3 x 31.0 mm rounded rectangle
  - two columns of eight through-board LEDs: port B down the left edge (B7 at the top), port A down the right edge
    (A0 at the top), so the sixteen lights run clockwise from bottom left in pin order GPB0..GPB7, GPA0..GPA7
  - SAO connector in the upper middle (key up), the MCP23017 below it with its power / I2C end toward the connector
  - each LED's resistor stands outside it, with its ground end in a ground ring that runs round the board edge
  - every track is on the back copper; there are no vias and no holes. The front carries no copper at all.
Every position below is checked by an assertion or by KiCad's rule check; nothing is searched for (no router).
"""
import json
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_SilkS, F_Mask

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "gpio-16"
load_local(SLUG)
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}

W, H, CORNER = 15.65, 15.5, 2.5     # half width, half height, corner radius
EDGE = 0.55                         # ground copper stops this far short of the edge (panel mouse bites reach 0.25 mm in)
CLEAR = 0.25                        # gap cut into the ground copper round everything that is not ground
WINDOW = 1.6                        # radius kept free of copper behind each LED (house rule)
SIG, PWR = 0.20, 0.30               # track widths

YJ = -6.0                           # SAO connector centre (x = 0)
YC = 7.1                            # MCP23017 centre (x = 0), long side upright
XL = 10.45                          # LED columns at x = -XL and +XL: 0.02 mm outside the connector's courtyard
XR = 13.65                          # resistor columns: their printed outline just clear of the LED's cathode bar
ROW = [-12.25 + 3.5 * k for k in range(8)]
C1C = (1.2, 0.85)                   # supply capacitor between the connector and the chip
SLOT = [5.45, 5.85, 6.25, 6.65, 7.05, 7.45, 7.85]      # |x| of the seven upward LED tracks beside the chip
VDD_X = 4.9                         # |x| of the supply track, innermost on the left

# LED of each chip pin. Left column top to bottom = pins 8..1 (GPB7..GPB0); right column top to bottom = pins 21..28
# (GPA0..GPA7). D1..D8 = GPA0..GPA7, D9..D16 = GPB0..GPB7 (circuit.json).
LEFT = [(f"D{9 + b}", b) for b in range(7, -1, -1)]      # (ref, bit) for rows 0..7
RIGHT = [(f"D{1 + b}", b) for b in range(8)]

# ---- outline: one polygon (tools/panelize.py needs that) ------------------------------------------
body = grown(poly([(-W + CORNER, -H + CORNER), (W - CORNER, -H + CORNER), (W - CORNER, H - CORNER), (-W + CORNER, H - CORNER)]), CORNER)
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
print("board %.2f x %.2f mm, outline points %d" % (bbox_mm(body)[2] - bbox_mm(body)[0], bbox_mm(body)[3] - bbox_mm(body)[1],
                                                 body.Outline(0).PointCount()))
inner = grown(body, -EDGE)

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)

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


def place(ref, pos, want):
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name} in {LIBS[lib]}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # refs live on the fab layer and in the README
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
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


# ---- placement ----------------------------------------------------------------------------------
FP = {}
FP["J1"] = place("J1", (0, YJ), ("1", (-2.54, YJ - 3.4)))            # VCC top left in front view: key slot up
FP["U1"] = place("U1", (0, YC), ("1", (-3.6, YC + 4.225)))           # pin 1 bottom left: the supply / I2C end is up
FP["C1"] = place("C1", C1C, ("2", (C1C[0] - 0.775, C1C[1])))         # ground pad on the left, supply pad on the right
for side, col in ((-1, LEFT), (1, RIGHT)):
    for k, (ref, bit) in enumerate(col):
        y = ROW[k]
        FP[ref] = place(ref, (side * XL, y), ("2", (side * (XL - 1.55), y)))            # anode toward the chip
        r = "R" + ref[1:]
        FP[r] = place(r, (side * XR, y), ("1", (side * XR, y - 0.825)))                 # LED end up, ground end down
u = {str(n): pp(FP["U1"], str(n)) for n in range(1, 29)}
j = {str(n): pp(FP["J1"], str(n)) for n in range(1, 7)}
assert u["14"][1] < u["1"][1] and u["14"][0] < 0 < u["15"][0] and abs(u["15"][1] - u["14"][1]) < 0.01, u
assert j["3"] == (0.0, YJ - 3.4) and j["2"] == (-2.54, YJ + 3.4) and j["4"] == (0.0, YJ + 3.4), j
for ref in sorted(FP, key=lambda r: (r[0], int(r[1:]))):
    fp = FP[ref]
    print(ref, "at", mm(fp.GetPosition()), "rot", round(fp.GetOrientationDegrees(), 1))

# every pad at least 0.7 mm inside the edge
_edge = grown(body, -0.7)
for fp in FP.values():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(_edge)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is too close to the board edge"

# ---- routing: back copper only, no vias. Written out by hand; see the README for the plan ---------
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


def netof(ref, num):
    return PADNETS[ref][num]


# the sixteen LED lines: out of the pin, along to its own lane beside the chip, up (or down) to its row, across to the anode
for side, col, pins in ((-1, LEFT, [8, 7, 6, 5, 4, 3, 2, 1]), (1, RIGHT, [21, 22, 23, 24, 25, 26, 27, 28])):
    for k, ((ref, bit), pin) in enumerate(zip(col, pins)):
        px, py = u[str(pin)]
        lane = SLOT[k] if k < 7 else SLOT[0]                 # the bottom LED is the only one below its pin: its lane is free
        ax = side * (XL - 1.55 - 0.3)                        # end inside the anode pad, outside the light window
        net = netof("U1", str(pin))
        assert net == netof(ref, "2"), (ref, pin)
        assert (ROW[k] < py) == (k < 7)
        route(net, [(px, py), (side * lane, py), (side * lane, ROW[k]), (ax, ROW[k])])
        # cathode -> its resistor's upper pad, a short link outside the light window
        r = "R" + ref[1:]
        route(netof(ref, "1"), [(side * (XL + 1.75), ROW[k] - 0.6), (side * XR, ROW[k] - 0.6)], 0.25)

# badge 3.3 V: connector pin 1 -> down the left of the connector -> innermost lane on the left of the chip -> pin 9
route("VSAO", [j["1"], (-VDD_X, j["1"][1]), (-VDD_X, u["9"][1]), u["9"]], PWR)
# ... and on under the chip from pin 9's inner end: across to RESET (pin 18) and up to the supply capacitor
c1v, c1g = pp(FP["C1"], "1"), pp(FP["C1"], "2")
VX = c1v[0] - 0.025
route("VSAO", [u["9"], (VX, u["9"][1]), (VX, u["18"][1]), u["18"]], PWR)
route("VSAO", [(VX, u["18"][1]), (VX, c1v[1]), c1v], PWR)
# ground: pin 10 -> under the chip -> up to the capacitor's ground pad; address pins 15-17 joined and taken up clear of the chip
GX = c1g[0] + 0.025
route("GND", [u["10"], (GX, u["10"][1]), (GX, c1g[1]), c1g], PWR)
route("GND", [u["17"], u["15"], (u["15"][0], YC - 6.1)], PWR)
# I2C: under the chip and straight up. SCL into the bottom of connector pin 4; SDA between pins 2 and 4, then across
# between the connector's two pad rows into the bottom of pin 3
SCL_X, SDA_X = -0.4, -1.4
route("SCL", [u["12"], (SCL_X, u["12"][1]), (SCL_X, j["4"][1])])
route("SDA", [u["13"], (SDA_X, u["13"][1]), (SDA_X, YJ + 0.7), (0.0, YJ + 0.7), (0.0, j["3"][1] + 1.6)])

# ---- ground copper on the back: the whole board, cleared round everything that is not ground -------
gnd_code = nets["GND"].GetNetCode()
cut = pcbnew.SHAPE_POLY_SET()
for fp in FP.values():
    for pad in fp.Pads():
        if pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
LEDS = [(side * XL, y) for side in (-1, 1) for y in ROW]
for x, y in LEDS:
    add_circle(cut, P(x, y), WINDOW)
cut.Simplify()
back = pcbnew.SHAPE_POLY_SET(inner)
back.BooleanSubtract(cut)
back.Simplify()
# drop slivers thinner than 0.2 mm so the board house and DRC see no hair-thin copper
back.Inflate(-FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
back.Inflate(FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
back.BooleanIntersection(inner)
back.BooleanSubtract(cut)
back.Simplify()

seed = pcbnew.SHAPE_POLY_SET()
for fp in FP.values():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            seed.Append(pad_poly(pad, B_Cu))
for t in TRACKS:
    if t.GetNetCode() == gnd_code:
        t.TransformShapeToPolygon(seed, B_Cu, 0, ERR, pcbnew.ERROR_INSIDE)
seed.Simplify()
kept = dropped = 0
for i in range(back.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(back.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(seed)
    if area_mm2(both) > 0.01 and area_mm2(piece) > 0.3:
        add_filled(board, piece, B_Cu, nets["GND"])
        kept += 1
        print("  ground piece %.1f mm2 at %s" % (area_mm2(piece), [round(v, 1) for v in bbox_mm(piece)]))
    else:
        dropped += 1                                         # crumbs boxed in between tracks: not connected to anything
print("back ground pieces kept", kept, "dropped", dropped)
assert kept == 1, "the ground copper must be one piece"
# ... and it must still be one piece, touching every ground pad, when every neck narrower than 0.5 mm is ignored
_core = pcbnew.SHAPE_POLY_SET(back)
_core.Inflate(-FromMM(0.25), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
_core.Inflate(FromMM(0.25), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
_big = max(range(_core.OutlineCount()), key=lambda i: area_mm2(pcbnew.SHAPE_POLY_SET(_core.Polygon(i))))
_main = pcbnew.SHAPE_POLY_SET(_core.Polygon(_big))
_weak = []
for fp in FP.values():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            hit = pad_poly(pad, B_Cu, 0.05)
            hit.BooleanIntersection(_main)
            if area_mm2(hit) < 0.02:
                _weak.append(fp.GetReference() + "." + pad.GetNumber())
print("ground pads reached only through necks under 0.5 mm:", _weak or "none")
assert set(_weak) <= {"U1.10", "U1.15", "U1.16", "U1.17"}, _weak     # those four have their own 0.3 mm tracks (below the chip)


# ---- lettering -------------------------------------------------------------------------------------
def text(txt, x, y, size, layer, mirrored=False, thick=0.15):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * thick))
    t.SetMirrored(mirrored)
    board.Add(t)
    return t


# front: no copper. A round opening in the solder mask over each LED (bare board, so any mask colour lets the light out),
# and beside it the name of the chip pin that lights it
for side, col in ((-1, LEFT), (1, RIGHT)):
    for k, (ref, bit) in enumerate(col):
        x, y = side * XL, ROW[k]
        m = pcbnew.SHAPE_POLY_SET()
        add_circle(m, P(x, y), 1.45)
        add_filled(board, m, F_Mask)
        text(("B" if side < 0 else "A") + str(bit), side * (XL - 3.6), y, 1.1, F_SilkS)
    frame = grown(poly([(side * XL - 0.01, ROW[0]), (side * XL + 0.01, ROW[0]), (side * XL + 0.01, ROW[7]), (side * XL - 0.01, ROW[7])]), 2.0)
    f = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)             # one printed frame round each column of eight
    f.SetPolyShape(frame)
    f.SetLayer(F_SilkS)
    f.SetFilled(False)
    f.SetWidth(FromMM(0.15))
    board.Add(f)
text("GPIO-16", 0, -7.0, 1.7, F_SilkS, thick=0.16)
text("16 LEDs on I2C", 0, -3.5, 1.0, F_SilkS)
text("MCP23017", 0, 0.0, 1.2, F_SilkS)
text("I2C 0x20", 0, 3.5, 1.2, F_SilkS)
text("SAO++", 0, 7.0, 1.4, F_SilkS)
# back: what the standard asks for, plus the plain warning that this board has no battery
text("circuit: AND!XOR DC27", 0, -13.7, 0.8, B_SilkS, True)
text("1", j["1"][0] - 1.5, j["1"][1] - 2.75, 0.8, B_SilkS, True)
text("GPIO-16 rA  SAO++", 0, 13.3, 0.8, B_SilkS, True)
text("BADGE POWER ONLY", 0, 14.4, 0.8, B_SilkS, True)

# ---- settings and save --------------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.15))   # the chip's pads are 0.20 mm apart (Microchip's own land pattern)
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)

# ---- project file: SaveBoard does not write the rules into gpio-16.kicad_pro on this KiCad (10.0.8), and kicad-cli can
#      rewrite the file and drop custom severities, so the rules this board is checked against are put back on every build
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
pro = json.load(open(PRO))
pro["meta"]["filename"] = SLUG + ".kicad_pro"
pro["board"]["design_settings"]["rules"].update({
    "min_clearance": 0.15, "min_copper_edge_clearance": 0.25, "min_hole_clearance": 0.25, "min_track_width": 0.15,
    "min_silk_clearance": 0.0, "solder_mask_to_copper_clearance": 0.0})
pro["board"]["design_settings"]["rule_severities"].update({
    "clearance": "error", "copper_edge_clearance": "error", "courtyards_overlap": "error", "shorting_items": "error",
    "solder_mask_bridge": "error", "tracks_crossing": "error", "unconnected_items": "error", "track_width": "error",
    "lib_footprint_mismatch": "warning", "lib_footprint_issues": "warning", "silk_overlap": "warning",
    "silk_over_copper": "warning", "copper_sliver": "warning"})
for nc in pro["net_settings"]["classes"]:
    if nc["name"] == "Default":
        nc.update({"clearance": 0.15, "track_width": SIG})
with open(PRO, "w") as f:
    json.dump(pro, f, indent=2, sort_keys=True)
    f.write("\n")
print("rules re-applied to", PRO)
