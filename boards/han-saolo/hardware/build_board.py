#!/usr/bin/env python3
"""Rebuild han-saolo.kicad_pcb from davedarko's 2024 KiCad 8 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/han-saolo/hardware/build_board.py

What it does
  - loads original/SoloCarbonite/SoloCarbonite.kicad_pcb so the front art (copper, mask, silk) stays exactly as drawn
  - removes every old part, track, via and zone; the front copper is put back as fixed shapes cut from the maker's own
    zone fills (so it looks exactly as he made it), minus the two new switch peg holes
  - keeps the maker's circuit: ATtiny412 driving five SK6805-EC3210R side-firing RGB LEDs from PA6, with the maker's
    LED-data jumper. New: the shared SMD SAO connector, the SAO / OFF / BAT switch, the CR2032 clip, the series cell
    diode, a UPDI programming pad
  - places everything on the back and routes it on the back copper; the back copper is the GND net, 0.55 mm clear of
    the edge, cleared around the maker's four LED windows and the face window
  - joins the separate ground islands through the front copper (the maker's design did the same) with tented vias,
    each placed where the front art is covered by solder mask
  - keeps the back silkscreen art; the maker's jumper legend is moved (same words, same size) next to the jumper

Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import time
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

_T0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly)  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "han-saolo"
SRC = os.path.join(HERE, "..", "original", "SoloCarbonite", "SoloCarbonite.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # GND copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
PWR = 0.40          # supply track width

# ---- placement (front-view mm) --------------------------------------------------------------------------------------
BAT = (13.5, 35.6)          # cell centre: as high as the IIC-ready logo allows (cell edge 10.2 mm from its corner)
BAT_CLOSED = (0.0, 1.0)     # the clip's closed end points down; the cell slides in from the top, where nothing is tall
SW = (2.1, 53.15)           # left edge below the cell; knob out of the left edge; pin 4 (BAT) on top, pin 1 (SAO) at the bottom
CONN = (15.3, 59.6)         # bottom, 2.95 mm above the bottom edge, 1.8 mm right of centre: its body just clears the
                            # maker's "PULL-UPS? On my PCB?" lettering along the bottom-left corner
U1C = (12.2, 50.75)         # the ATtiny, between the supply track and the connector
LED_LENS_X = 0.65           # shared LED footprint origin sits this far toward the lens from the maker's origin
LEDS = {                    # maker's centre, lens direction (+1 = toward +x)
    "D1": ((21.37, 50.40), +1), "D2": ((21.39, 20.97), +1), "D3": ((21.37, 13.04), +1), "D4": ((21.37, 4.85), +1),
    "D5": ((12.89, 9.95), -1),
}
TRUNK_X = 19.8              # 3.3 V trunk up the LED column
CORR_V, CORR_D = 25.55, 26.15   # the two tracks that pass the cell on the right: 3.3 V and LED data

# ---- cut the 2024 electrical parts out of the file text (KiCad 10's Python crashes on Remove()) ---------------------
def tab_blocks(txt, opener):
    """(start, end) of each top-level '(opener ...' block in a tab-indented KiCad 8 file."""
    for m in re.finditer(r"\n\t\(" + opener + r"[ \n\t]", txt):
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


_txt = open(SRC, encoding="utf-8").read()
_cut = []
for kind, n in (("footprint", 20), ("segment", 130), ("via", 6), ("zone", 21)):
    found = list(tab_blocks(_txt, kind))
    assert len(found) == n, (kind, len(found))
    _cut += found
for a_, b_ in sorted(_cut, reverse=True):
    _txt = _txt[:a_] + _txt[b_:]
_tmp = os.path.join(tempfile.mkdtemp(), "SoloCarbonite.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

print("[0]", "read what is needed", round(time.time() - _T0, 1), flush=True)
# ---- read what is needed from the untouched original ---------------------------------------------------------------
_orig = pcbnew.LoadBoard(SRC)
front_fill = {}                                 # zone name -> its 2024 fill on F.Cu
keep_f, keep_b = pcbnew.SHAPE_POLY_SET(), pcbnew.SHAPE_POLY_SET()
face_mask = None
for z in _orig.Zones():
    ls = z.GetLayerSet()
    if z.GetIsRuleArea():
        if ls.Contains(F_Cu):
            keep_f.Append(z.Outline())
        if ls.Contains(B_Cu):
            keep_b.Append(z.Outline())
        continue
    if ls.Contains(F_Cu):
        x0, y0, x1, y1 = bbox_mm(z.Outline())
        name = "panel" if x0 > 22 else ("floor" if y0 > 62 else "slab")
        front_fill[name] = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(F_Cu))
    elif ls.Contains(pcbnew.B_Mask):
        face_mask = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(pcbnew.B_Mask))     # mask opening behind the face
assert sorted(front_fill) == ["floor", "panel", "slab"] and face_mask is not None
keep_f.Simplify()
keep_b.Simplify()
assert keep_b.OutlineCount() == 5, "expected the maker's four side-panel LED windows and the face window on B.Cu"
fmask = pcbnew.SHAPE_POLY_SET()                 # front solder-mask openings = where the tinned copper art shows
for d in _orig.GetDrawings():
    if d.GetLayer() == pcbnew.F_Mask and d.GetShape() == pcbnew.SHAPE_T_POLY:
        fmask.Append(d.GetPolyShape())
fmask.Simplify()
_old_pegs = []
for fp in _orig.GetFootprints():
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            _old_pegs.append(mm(pad.GetPosition()))
assert len(_old_pegs) == 2, _old_pegs           # the 2024 PCM12 switch's pegs in the side panel

board = pcbnew.LoadBoard(_tmp)
_ol = json.load(open(os.path.join(HERE, "outline.json")))
body = poly(_ol["outer"])
_edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
assert len(_edges) == 1 and len(_ol["outer"]) == 6                  # the maker's clean 6-corner outline is kept as drawn
inner = grown(body, -EDGE)
for d in board.GetDrawings():                   # nothing of the art may sit outside the outline
    if d.GetLayer() != pcbnew.Edge_Cuts:
        bb = d.GetBoundingBox()
        assert -0.3 < ToMM(bb.GetLeft()) and ToMM(bb.GetRight()) < 27.3 and -0.3 < ToMM(bb.GetTop()) and ToMM(bb.GetBottom()) < 67.3, \
            (board.GetLayerName(d.GetLayer()), mm(bb.GetOrigin()), mm(bb.GetEnd()))

print("[0]", "the circuit", round(time.time() - _T0, 1), flush=True)
# ---- the circuit (shared with the schematic generator) -----------------------------------------------------------
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
    lib, name = fpid.split(":")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH("/" + sch_uuid(ref)))
    fp.SetValue(PARTS[ref].get("value", value))
    for k, v in fields.items():
        if fp.HasField(k):
            fp.GetField(k).SetText(v)
        else:                                   # KiCad's stock footprints carry no SAO++ fields: add them, hidden
            f = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), k)
            f.SetText(v)
            f.SetVisible(False)
            f.SetLayer(pcbnew.B_Fab)
            fp.Add(f)
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


def load(ref, pos):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)    # the back is busy with art; refs live on the fab layer and in the README
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


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- footprints -----------------------------------------------------------------------------------------------------
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC top-left in front view (as Mad Cat), key slot up
sw = place("SW1", SW, ("4", (SW[0] + 1.43, SW[1] - 3.0)))           # pins face the board, pin 4 (BAT) on top
u1 = place("U1", U1C, ("1", (U1C[0] + 2.475, U1C[1] - 1.905)))      # pin 1 top-right: VCC up, SDA/SCL down, PA6 right
led = {}
for ref, ((x, y), s) in LEDS.items():
    ox = x + s * LED_LENS_X
    led[ref] = place(ref, (ox, y), ("4", (ox - s * 0.4, y + s * 0.425)))    # VDD pad: lens points to +x (or -x for D5)
D6C = (2.0, 29.6)
d6 = place("D6", D6C, ("2", (D6C[0] + 0.7, D6C[1])))                # above the clip (clear of its courtyard): anode right
JP1C = (17.9, 50.95)
jp1 = place("JP1", JP1C, ("1", (JP1C[0], JP1C[1] - 1.3)))           # pad 1 (PA6) on top, 2 = LED data, 3 (GPIO1) below
TP2C = (6.2, 52.0)
tp2 = place("TP2", TP2C, ("1", TP2C))
tp1 = place("TP1", (12.49, 14.12), ("1", (12.49, 14.12)))           # the maker's chain-out pad, where he had it
tp3 = place("TP3", (13.5, 2.35), ("1", (13.5, 2.35)))               # the maker's ground pad (his TP4), where he had it
CAPS = {"C1": (18.6, 7.4, "h"), "C2": (18.6, 16.6, "h"), "C3": (18.6, 24.3, "h"), "C4": (6.6, 48.725, "v"), "C5": (15.6, 10.3, "v")}
cap = {}
for ref, (x, y, o) in CAPS.items():
    if o == "h":                                # pad 1 (3.3 V) on the trunk to the right
        cap[ref] = place(ref, (x, y), ("1", (x + 0.775, y)))
    else:                                       # pad 1 (3.3 V) on the supply track above
        cap[ref] = place(ref, (x, y), ("1", (x, y - 0.775)))

# battery clip: both clip pads are "1" and the clip fits either way, so choose the angle by where the closed end points
bat = load("BT1", BAT)


def _closed_dir(rot):
    bat.SetOrientationDegrees(rot)
    fab = [g for g in bat.GraphicalItems() if g.GetLayer() == pcbnew.B_Fab and g.GetShape() == pcbnew.SHAPE_T_RECT]
    c = fab[0].GetBoundingBox().GetCenter()             # the clip body rectangle is off-centre toward the closed end
    return math.degrees(math.atan2(ToMM(c.y) - BAT[1], ToMM(c.x) - BAT[0]))


_d0, _d90 = _closed_dir(0), _closed_dir(90)
_sense = 1 if round((_d90 - _d0) % 360) == 90 else -1
_rot = round(_sense * (math.degrees(math.atan2(BAT_CLOSED[1], BAT_CLOSED[0])) - _d0)) % 360
bat.SetOrientationDegrees(_rot - 0.1)       # 0.1 degree off square: KiCad 10 calls this courtyard malformed at exactly 90/270
link(bat, "BT1")
print("battery clip angle", _rot - 0.1)

NEW = set(PARTS)
for fp in board.GetFootprints():
    assert fp.GetReference() in NEW, fp.GetReference()

_pad_ok = grown(body, -0.25)      # the switch's hold-down tabs sit 0.27 mm from the edge by design (as on Hack-Man)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

print("[0]", "routing (back", round(time.time() - _T0, 1), flush=True)
# ---- routing (back copper only) -------------------------------------------------------------------------------------
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


s1, s3, s4 = pp(sw, "1"), pp(sw, "3"), pp(sw, "4")
j = {n: pp(conn, n) for n in "123456"}
u = {n: pp(u1, n) for n in "12345678"}
L = {r: {n: pp(f, n) for n in "1234"} for r, f in led.items()}

# 3.3 V (VLOAD): switch common -> up past the ATtiny -> along under the cell -> up the right edge -> the LED column
V_Y = 47.95
VLOAD = [s3, (4.85, s3[1]), (4.85, V_Y), (19.5, V_Y), (CORR_V, V_Y - (CORR_V - 19.5)), (CORR_V, 27.75), (21.0, 27.75),
         (TRUNK_X, 26.55), (TRUNK_X, L["D4"]["4"][1]), L["D4"]["4"]]
route("VLOAD", VLOAD, PWR)
route("VLOAD", [(19.5, V_Y), (19.5, L["D1"]["4"][1]), L["D1"]["4"]], 0.3)                  # D1
for r in ("D2", "D3"):
    route("VLOAD", [(TRUNK_X, L[r]["4"][1]), L[r]["4"]], 0.3)
route("VLOAD", [(TRUNK_X, L["D5"]["4"][1]), L["D5"]["4"]], 0.3)                              # D5 (the face)
route("VLOAD", [u["1"], (u["1"][0], V_Y)], 0.3)                                              # ATtiny VCC

# LED data: PA6 -> jumper -> D1 -> up the right edge -> D2 -> D3 -> D4 -> across the top -> D5 (face) -> TP1
jpp = {n: pp(jp1, n) for n in "123"}
route("NEO_PA6", [u["2"], (15.4, u["2"][1]), (15.94, jpp["1"][1]), jpp["1"]])
route("LED_DIN", [jpp["2"], (19.0, jpp["2"][1]), (19.15, L["D1"]["3"][1]), L["D1"]["3"]])
route("SAO_GPIO1", [(j["5"][0], j["5"][1] - 2.0), jpp["3"]])
d1o = L["D1"]["2"]
route("LED_D1", [d1o, (22.3, d1o[1] - 0.6), (CORR_D, d1o[1] - 0.6 - (CORR_D - 22.3)), (CORR_D, 27.1), (22.35, 27.1),
                 (22.35, L["D2"]["3"][1] + 0.6), L["D2"]["3"]])
LINK_X = 22.15              # links between the LEDs run just right of their pads (still left of the windows), so a
                            # ground via fits between each LED's pads and the trunk, on the front's dark border strip
for a_, b_ in (("D2", "D3"), ("D3", "D4")):
    o_, i_ = L[a_]["2"], L[b_]["3"]
    route(f"LED_{a_}", [o_, (LINK_X, o_[1] - 0.4), (LINK_X, i_[1] + 0.4), i_])
d4o, d5i = L["D4"]["2"], L["D5"]["3"]
TOP_Y = 1.6                 # D4 -> D5 runs along the top edge, so D4's ground pocket reaches the dark strip above D4
route("LED_D4", [d4o, (22.0, d4o[1] - 0.3), (22.0, TOP_Y), (16.0, TOP_Y), (15.45, 4.45), (d5i[0], 6.0), d5i])
route("LED_D5", [L["D5"]["2"], pp(tp1, "1")])

# SAO bus: SDA / SCL straight down to the connector (SCL between its pad columns), badge 3.3 V to the switch
route("SDA", [u["4"], (j["3"][0], u["4"][1] + 0.95), (j["3"][0], j["3"][1] - 1.9)])
SCL_Y = u["5"][1] + 0.7
route("SCL", [u["5"], (u["5"][0], SCL_Y), (j["1"][0] + 1.27, SCL_Y), (j["1"][0] + 1.27, CONN[1]), (j["4"][0], CONN[1]),
              (j["4"][0], j["4"][1] - 1.9)])
route("VSAO", [s1, (j["1"][0], s1[1])], PWR)
route("UPDI", [u["6"], pp(tp2, "1")])

# coin cell: clip -> D6 (series diode) -> switch pin 4, down the left edge between the switch's hold-down tabs
bt_l = pp(bat, "1", pick=lambda p: p[0])
bt_r = pp(bat, "1", pick=lambda p: -p[0])
route("VBAT", [(bt_l[0], bt_l[1] - 2.0), (bt_l[0], 31.0), pp(d6, "2")], PWR)
route("VBAT_D", [pp(d6, "1"), (1.0, D6C[1] + 0.6), (1.0, 46.9), (1.77, 47.67), (1.77, 49.4), (s4[0] - 0.63, s4[1]), s4], 0.3)
# the clip itself joins its two pads; this link round the closed end (just outside the cell) makes the board agree
_r = 10.5
_arc = [(round(BAT[0] + _r * math.cos(math.radians(d)), 4), round(BAT[1] + _r * math.sin(math.radians(d)), 4)) for d in range(0, 181, 10)]
route("VBAT", [bt_r] + _arc[1:-1] + [bt_l], 0.3)

print("[0]", "back copper: GND", round(time.time() - _T0, 1), flush=True)
# ---- back copper: GND everywhere, cleared round every other net and kept off the LED and face windows -------------
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(grown(keep_b, 0.0))
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
    for it in fp.GraphicalItems():              # the jumper's copper bridge belongs to its pads 1-2 (not GND)
        if it.GetLayer() == B_Cu:
            it.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t, clear, net in TRACKS:
    if net != "GND":
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
cut.Simplify()
gnd.BooleanSubtract(cut)
gnd.Simplify()

gnd_pads = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.append((fp.GetReference(), pad_poly(pad, B_Cu)))
pieces = []                                     # [(piece, [GND pads on it])]
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    on = []
    for ref, pp_ in gnd_pads:
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(pp_)
        if area_mm2(both) > 0.005:
            on.append(ref)
    pieces.append((piece, on))

print("[0]", "vias: one per", round(time.time() - _T0, 1), flush=True)
# ---- vias: one per separate ground island, joining them through the front copper -----------------------------------
# The front copper was a ground plane in the maker's design too (he used five ground vias). Each via is tented and sits
# where the front art is under solder mask (dark), as far from the nearest tinned (bright) spot as the island allows.
front_cu = pcbnew.SHAPE_POLY_SET()
for k_ in ("slab", "floor", "panel"):
    front_cu.Append(front_fill[k_])
_peg_patch = pcbnew.SHAPE_POLY_SET()            # the old switch's lower peg left a hole in the side-panel copper: fill it
for x, y in _old_pegs:
    one = pcbnew.SHAPE_POLY_SET()
    add_circle(one, P(x, y), 0.95)
    _peg_patch.Append(one)
_peg_patch.Simplify()
_panel_zone = poly([(22.14, 0.05), (27.14, 5.05), (27.14, 66.55), (22.14, 66.55)])     # (bounding check only)
_peg_patch.BooleanSubtract(grown(keep_f, 0.0))
_peg_patch.BooleanIntersection(grown(body, -0.5))
front_cu.BooleanAdd(_peg_patch)
front_cu.Simplify()
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)
front_cu.BooleanSubtract(pegs)
front_cu.Simplify()
slab = max((pcbnew.SHAPE_POLY_SET(front_cu.Polygon(i)) for i in range(front_cu.OutlineCount())), key=area_mm2)


def _open_area(c, r, local):
    ring = pcbnew.SHAPE_POLY_SET()
    add_circle(ring, c, r, 24)
    ring.BooleanIntersection(local)
    return area_mm2(ring)


def dark_spot(piece, near, box=3.0):
    """Best via centre in a ground island: inside the island and the front slab, under front mask, near `near`."""
    win = poly([(near[0] - box - 1.5, near[1] - box - 1.5), (near[0] + box + 1.5, near[1] - box - 1.5),
                (near[0] + box + 1.5, near[1] + box + 1.5), (near[0] - box - 1.5, near[1] + box + 1.5)])
    inside_b = grown(piece, -0.33)              # via copper (0.3 mm radius) stays inside the island
    inside_b.BooleanIntersection(win)
    inside_f = grown(slab, -0.15)               # the via lands on the front slab (it may overhang the slab's edge)
    inside_f.BooleanIntersection(win)
    local = pcbnew.SHAPE_POLY_SET(fmask)        # only the art near the search box: keeps the boolean work small
    local.BooleanIntersection(win)
    k = 0.05 if box < 1.6 else 0.1
    nx = int(box / k)
    cands = []
    for ix in range(-nx, nx + 1):
        for iy in range(-nx, nx + 1):
            x, y = near[0] + ix * k, near[1] + iy * k
            if inside_b.Contains(P(x, y)) and inside_f.Contains(P(x, y)):
                cands.append(((ix * ix + iy * iy) * k * k, x, y))
    cands.sort()
    scored = []
    for d2, x, y in cands[:800]:
        c = P(x, y)
        if _open_area(c, 0.32, local) > 0:        # the whole via ring (0.3 mm radius) under mask
            continue
        scored.append((d2 + 2.0 * sum(_open_area(c, r_, local) for r_ in (0.45, 0.6, 0.8)), (round(x, 2), round(y, 2))))
        if len(scored) >= 25:
            break
    return min(scored)[1] if scored else None


VIA_NEAR = {"main": (16.5, 21.5, 3.0), "top": (21.28, 2.45, 0.3), "D3": (21.35, 9.0, 1.5), "D2": (21.35, 17.0, 1.5),
            "bottom": (21.35, 56.0, 2.0)}
vias = []
n_gnd = n_art = 0
for piece, on in pieces:
    if not on:
        if area_mm2(piece) > 0.3:
            add_filled(board, piece, B_Cu)          # copper with no ground pad on it stays as plain (unconnected) copper
            n_art += 1
        continue
    add_filled(board, piece, B_Cu, nets["GND"])
    n_gnd += 1
    key = ("main" if "BT1" in on else "top" if "D4" in on else "D3" if "D3" in on else "D2" if "D2" in on
           else "bottom" if "J1" in on else None)
    assert key, f"ground island with pads {on} has no via spot defined"
    print("   island", key, round(area_mm2(piece), 1), [round(v, 1) for v in bbox_mm(piece)], sorted(set(on)),
          "points", piece.FullPointCount(), round(time.time() - _T0, 1), flush=True)
    spot = dark_spot(piece, VIA_NEAR[key][:2], VIA_NEAR[key][2])
    assert spot, f"no dark spot for the {key} ground via"
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*spot))
    v.SetDrill(FromMM(0.3))
    v.SetWidth(FromMM(0.6))
    v.SetNet(nets["GND"])
    v.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
    vias.append((key, spot, sorted(set(on))))
    print(f"  ground island '{key}' {area_mm2(piece):.1f} mm2, pads {sorted(set(on))}: via at {spot}")
print("back copper pieces: GND", n_gnd, "plain", n_art, "| vias", len(vias))

print("[0]", "front copper: the", round(time.time() - _T0, 1), flush=True)
# ---- front copper: the maker's fills, as fixed shapes; the slab is ground (the vias land on it) ---------------------
n_front = 0
for i in range(front_cu.OutlineCount()):
    one = pcbnew.SHAPE_POLY_SET(front_cu.Polygon(i))
    hit = any(one.Contains(P(*s)) for _, s, _ in vias)
    add_filled(board, one, F_Cu, nets["GND"] if hit else None)
    n_front += 1
print("front copper pieces:", n_front)
add_filled(board, face_mask, pcbnew.B_Mask)     # the maker's mask opening behind the face (was a filled zone)

print("[0]", "back silkscreen ---", round(time.time() - _T0, 1), flush=True)
# ---- back silkscreen ------------------------------------------------------------------------------------------------
# the maker's jumper legend (PA6 / NEO / SWT and PA0 / RST / IO2) sat where the switch now is. It moves, words, letter
# size and layout unchanged, to the free space between "Really? ..." and the top of the cell (the only gap it fits)
legend = [t for t in board.GetDrawings() if t.GetLayer() == B_SilkS and isinstance(t, pcbnew.PCB_TEXT)
          and t.GetText().split("\n")[0] in ("PA6", "NEO", "PA0")]
assert len(legend) == 3, [t.GetText() for t in legend]
lb = pcbnew.BOX2I()
for t in legend:
    lb.Merge(t.GetBoundingBox())
_lc = lb.GetCenter()
LEG_C = (10.555, 22.89)
for t in legend:
    t.Move(VECTOR2I(P(*LEG_C).x - _lc.x, P(*LEG_C).y - _lc.y))
lb2 = pcbnew.BOX2I()
for t in legend:
    lb2.Merge(t.GetBoundingBox())
print("jumper legend moved from", mm(lb.GetOrigin()), mm(lb.GetEnd()), "to", mm(lb2.GetOrigin()), mm(lb2.GetEnd()))

LABELS = [("BAT", 3.4, 46.4, 0.8, 0), ("OFF", 5.6, 55.1, 0.6, 0), ("SAO", 6.3, 57.55, 0.7, 0),
          ("UPDI", TP2C[0], TP2C[1] + 1.4, 0.5, 0), ("1", j["1"][0] - 1.15, j["1"][1] - 1.85, 0.8, 0),
          ("CR2032 +", 23.8, 30.45, 0.7, 90), ("SAO++ rA", 23.9, 65.4, 0.7, 0)]
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

# the clip's silk arrow and outline: moved to the fab layer (they land on the maker's lettering, as on other boards)
for g in bat.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)

# ---- report ---------------------------------------------------------------------------------------------------------
print("J1 pads:", {n: j[n] for n in "123456"})
print("SW1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in sw.Pads() if p.GetNumber()})
print("BT1 pads:", [(p.GetNumber(), mm(p.GetPosition())) for p in bat.Pads()])
print("U1 pads:", u)
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = FromMM(0.05)
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_ViasMinSize = FromMM(0.6)
ds.m_ViasMinAnnularWidth = FromMM(0.15)
ds.m_TentViasFront = True
ds.m_TentViasBack = True
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
