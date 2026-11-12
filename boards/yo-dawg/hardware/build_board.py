#!/usr/bin/env python3
"""Rebuild yo-dawg.kicad_pcb from davedarko's KiCad 8 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/yo-dawg/hardware/build_board.py

What the original is (read from the maker's files, commit 4dd3db0):
  - a 40 x 50 mm "mother" add-on with no lights of its own. Its front carries three 3-way 1.27 mm sockets, each wired
    GND - VCC - GND, for 19 x 19 mm mini boards ("badges on your badge"); a 2x3 through-hole SAO header on the back
    feeds them straight from the badge's 3.3 V, with one unmarked 0805 capacitor beside each socket. I2C and GPIO are
    not connected. Ground copper fills both sides.
  - the front art is one thing: a dithered black-on-white portrait of the rapper Xzibit (the "Yo Dawg" meme), 1318
    silkscreen polygons made from a photograph. See PORTRAIT below.

What this script does
  - loads original/dawg/dawg.kicad_pcb and cuts out of the file text the maker's header, capacitors, sockets, tracks,
    ground zone, outline and the fab-house order-number slot "JLCJLCJLCJLC" (KiCad 10's Python crashes on Remove())
  - keeps, untouched and where the maker put them: his back lettering ("Yo - Dawg! ... @davedarko 2024/09"), his
    three "- + -" socket labels, the dotted lines that show where the mini boards sit, and his logo
  - outline: the same 40 x 50 mm rectangle with 1 mm corners, as one polygon (the panel tool needs that)
  - sockets J2, J3, J4: the same stock footprint at the maker's exact positions, on the front
  - J1: the shared SMD shrouded SAO connector on the back, key up, in the maker's spot (0.8 mm higher, see CONN)
  - C1, C2, C3: the shared 100 nF 0603 where the maker's 0805 capacitors were
  - the supply track follows the maker's route; ground copper on both sides, 0.55 mm back from the edge, with
    thermal spokes round the sockets' ground pins so they can be hand-soldered
  - no cell and no switch: "badge power only", a recorded exception (board.yml, README)

PORTRAIT. The portrait is a likeness of a real person made from a photograph that is not the maker's. It is NOT in
this repository: original/dawg/dawg.kicad_pcb is the maker's file with those 1318 polygons taken out, and the board
is built without them unless the owner decides otherwise. To build with the portrait, point YODAWG_PORTRAIT at an
untouched copy of the maker's dawg/dawg.kicad_pcb (commit 4dd3db0):
  flatpak run --filesystem=$PWD --env=YODAWG_PORTRAIT=$PWD/<path>/dawg.kicad_pcb --command=python3 org.kicad.KiCad \
      boards/yo-dawg/hardware/build_board.py

Coordinates are millimetres in KiCad's front view (x grows right, y grows down); the board is x 0..40, y 0..50.
"""
import json
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS, F_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, cut_blocks, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "yo-dawg"
load_local(SLUG)
SRC = os.path.join(HERE, "..", "original", "dawg", "dawg.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIBS = {"sao-plus-plus": os.path.join(ROOT, "lib", "sao-plus-plus.pretty"),
        SLUG + "-local": os.path.join(HERE, SLUG + "-local.pretty")}
PORTRAIT = os.environ.get("YODAWG_PORTRAIT", "")

W, H, CORNER = 40.0, 50.0, 1.0
EDGE = 0.55         # copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
CLEAR = 0.30        # gap cut into the ground copper round everything that is not ground
TRACK = 0.40        # the maker's supply track width
SPOKE = 0.40        # thermal spokes round the sockets' ground pins
RELIEF = 0.40       # gap between a socket ground pin and the ground copper, bridged by the spokes

# ---- placement (front view). Sockets and capacitors: the maker's positions -------------------------------------
SOCKETS = {"J3": (10.0, 18.0), "J4": (30.0, 18.0), "J2": (10.0, 38.0)}   # centre pin (VCC); pins 1.27 mm either side
CAPS = {"C1": ((7.0, 35.0), (1, 0)),      # supply pad toward +x (the track at x = 10)
        "C2": ((10.1, 14.0), (0, 1)),     # supply pad down, toward socket J3
        "C3": ((30.0, 14.0), (0, 1))}     # supply pad down, toward socket J4
# SAO connector: x as the maker's header (20.0). The maker's through-hole header sat at y 44.52, 0.5 mm from the bottom
# edge. The SMD connector's pads are 11.2 mm from end to end, so the lowest it can go is 43.9 (pads end 0.5 mm inside
# the edge), and that is also the highest it can go without its pads and printed frame landing on the maker's last line
# of lettering ("@davedarko 2024/09", ends y 38.24 there) or his "- + -" label under socket J2. Nothing of his moves.
# Cost: the connector body ends 1.65 mm from the bottom edge, not the 3 mm docs/standard.md section 2 asks for.
CONN = (20.0, 43.9)
PAD_EDGE = 0.49     # every pad at least this far inside the edge (the connector's lower pads: 0.50)
GAP = 0.05          # least distance between anything new on the back silkscreen / the connector pads and the maker's marks

# ---- cut the maker's electrical items out of the file text ------------------------------------------------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block of a KiCad 8 file (one tab of indent)."""
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
    if ref != "Ref**":                                  # everything except the maker's logo
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["C1", "C2", "C3", "J1", "J2", "J3", "J4"], _gone
for kind in ("segment", "via", "zone"):
    _cut += list(tblocks(_txt, kind))
_edge = [(a_, b_) for k in ("gr_line", "gr_arc") for a_, b_ in tblocks(_txt, k) if '(layer "Edge.Cuts")' in _txt[a_:b_]]
assert len(_edge) == 8, len(_edge)
_cut += _edge
_jlc = [(a_, b_) for a_, b_ in tblocks(_txt, "gr_text") if _txt[a_:b_].lstrip().startswith('(gr_text "JLCJLCJLCJLC"')]
assert len(_jlc) == 1
_cut += _jlc
assert not list(tblocks(_txt, "gr_poly")), "original/dawg/dawg.kicad_pcb must be the copy without the portrait"
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n\t\(net [1-9]\d* "[^"]*"\)', _txt)]
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "dawg.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)
board = pcbnew.LoadBoard(_tmp)

_texts = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)]
assert sorted(t.GetText()[:10] for t in _texts) == ["- + -", "- + -", "- + -", "Yo - Dawg!"], [t.GetText() for t in _texts]
_lines = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_SHAPE)]
assert len(_lines) == 7 and all(d.GetLayer() == B_SilkS for d in _lines)      # the dotted mini-board frames
logo = list(board.GetFootprints())
assert len(logo) == 1 and "logo" in logo[0].GetFPIDAsString()
logo = logo[0]
logo.SetAttributes(logo.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)


def box(item):
    b = item.GetBoundingBox(False) if isinstance(item, pcbnew.FOOTPRINT) else item.GetBoundingBox()
    return (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))


def ink(t):
    """Bounding box of the strokes of a text (its GetBoundingBox includes line spacing)."""
    ps = pcbnew.SHAPE_POLY_SET()
    t.TransformTextToPolySet(ps, 0, ERR, pcbnew.ERROR_INSIDE)
    return bbox_mm(ps), ps


CREDIT = [t for t in _texts if t.GetText().startswith("Yo - Dawg!")][0]
CREDIT_BOX, CREDIT_INK = ink(CREDIT)
print("maker's lettering (ink) x %.2f..%.2f y %.2f..%.2f" % (CREDIT_BOX[0], CREDIT_BOX[2], CREDIT_BOX[1], CREDIT_BOX[3]))
print("maker's logo x %.2f..%.2f y %.2f..%.2f" % (box(logo)[0], box(logo)[2], box(logo)[1], box(logo)[3]))

# ---- outline -----------------------------------------------------------------------------------------------
body = grown(poly([(CORNER, CORNER), (W - CORNER, CORNER), (W - CORNER, H - CORNER), (CORNER, H - CORNER)]), CORNER)
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0
_bb = bbox_mm(body)
assert max(abs(_bb[0]), abs(_bb[1]), abs(_bb[2] - W), abs(_bb[3] - H)) < 0.01, _bb
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)

# ---- the circuit (shared with the schematic generator) -----------------------------------------------------
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
        if fp.HasField(k):
            fp.GetField(k).SetText(v)
        else:                                   # KiCad's stock footprints carry no SAO++ fields: add them, hidden
            f = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), k)
            f.SetText(v)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab if fp.GetLayer() == F_Cu else pcbnew.B_Fab)
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


def place(ref, pos, want, back=True):
    """Place a part, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    lib, name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")
    fp = pcbnew.FootprintLoad(LIBS[lib], name)
    assert fp is not None, f"missing footprint {name} in {LIBS[lib]}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    if back:
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


FP = {}
FP["J1"] = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))      # VCC top left in front view: key slot up
for ref, (x, y) in SOCKETS.items():
    # the footprint's origin is pin 1; the maker's pin 1 is the left one (front view), 1.27 mm left of the centre pin
    FP[ref] = place(ref, (x - 1.27, y), ("3", (x + 1.27, y)), back=False)
    assert pp(FP[ref], "2") == (x, y) and FP[ref].GetLayer() == F_Cu, (ref, pp(FP[ref], "2"))
for ref, ((x, y), (dx, dy)) in CAPS.items():
    FP[ref] = place(ref, (x, y), ("1", (x + 0.775 * dx, y + 0.775 * dy)))
j = {str(n): pp(FP["J1"], str(n)) for n in range(1, 7)}
assert j["2"] == (CONN[0] - 2.54, round(CONN[1] + 3.4, 3)) and j["5"] == (CONN[0] + 2.54, round(CONN[1] - 3.4, 3)), j
for ref in sorted(FP):
    print(ref, "at", mm(FP[ref].GetPosition()), "rot", round(FP[ref].GetOrientationDegrees(), 1),
          "front" if FP[ref].GetLayer() == F_Cu else "back")

# every pad at least PAD_EDGE inside the edge
_ok = grown(body, -PAD_EDGE)
for fp in FP.values():
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the board edge"

# the connector's printed frame and pads stay clear of the maker's lettering, logo and socket labels
_j1 = pcbnew.SHAPE_POLY_SET()
for g in FP["J1"].GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.TransformShapeToPolygon(_j1, B_SilkS, FromMM(GAP), ERR, pcbnew.ERROR_OUTSIDE)
for pad in FP["J1"].Pads():
    _j1.Append(pad_poly(pad, B_Cu, GAP))
_j1.Simplify()
_art = pcbnew.SHAPE_POLY_SET()
for t in _texts:
    _art.Append(ink(t)[1])
_lb = box(logo)
_art.Append(poly([(_lb[0], _lb[1]), (_lb[2], _lb[1]), (_lb[2], _lb[3]), (_lb[0], _lb[3])]))
_art.Simplify()
_hit = pcbnew.SHAPE_POLY_SET(_j1)
_hit.BooleanIntersection(_art)
for _i in range(_hit.OutlineCount()):
    print("  overlap piece at", [round(v, 2) for v in bbox_mm(pcbnew.SHAPE_POLY_SET(_hit.Polygon(_i)))])
assert area_mm2(_hit) < 1e-4, f"the connector overlaps the maker's lettering or logo by {area_mm2(_hit):.3f} mm2"
print("connector pads / frame start y %.2f; maker's lettering ends y %.2f" % (bbox_mm(_j1)[1] + GAP, CREDIT_BOX[3]))

# ---- routing: back copper only, the maker's route ----------------------------------------------------------
TRACKS = []


def route(net, pts, width=TRACK):
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


s2, s3, s4 = SOCKETS["J2"], SOCKETS["J3"], SOCKETS["J4"]
RUN_Y = j["1"][1] - 0.7            # leaves the side of the connector's pin 1 pad, below socket J2's ground pin
# connector pin 1 -> left, under socket J2 -> up into J2's centre pin (the maker came in from below the same way)
route("VSAO", [(j["1"][0], RUN_Y), (s2[0] + 0.6, RUN_Y), (s2[0], RUN_Y - 0.6), s2])
# J2 -> straight up the maker's x = 10 line -> J3, with the maker's branch along y = 20 to J4
route("VSAO", [s2, (s2[0], 20.0), s3])
route("VSAO", [(s2[0], 20.0), (28.707, 20.0), (30.0, 18.707), s4])
# capacitors, one beside each socket as on the original
route("VSAO", [(s2[0], 35.0), pp(FP["C1"], "1")])
route("VSAO", [s3, (s3[0], 15.2), pp(FP["C2"], "1")])
route("VSAO", [s4, pp(FP["C3"], "1")])

# ---- ground copper, both sides ---------------------------------------------------------------------------
gnd_code = nets["GND"].GetNetCode()
THT_GND = [pad for r in SOCKETS for pad in FP[r].Pads() if pad.GetNetCode() == gnd_code]
assert len(THT_GND) == 6


def spokes(pad):
    """The ring round a socket ground pin, minus three bridges (up, down, and away from the centre pin)."""
    x, y = mm(pad.GetPosition())
    ring = pad_poly(pad, B_Cu, RELIEF)
    out = 1 if pad.GetNumber() == "3" else -1
    h = SPOKE / 2
    bars = poly([(x - h, y - 1.6), (x + h, y - 1.6), (x + h, y + 1.6), (x - h, y + 1.6)])
    bars.Append(poly([(x, y - h), (x + out * 1.6, y - h), (x + out * 1.6, y + h), (x, y + h)]))
    bars.Simplify()
    ring.BooleanSubtract(bars)
    return ring


def ground(layer):
    cut = pcbnew.SHAPE_POLY_SET()
    for fp in FP.values():
        for pad in fp.Pads():
            if pad.GetNetCode() != gnd_code and pad.IsOnLayer(layer):
                pad.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    if layer == B_Cu:
        for t in TRACKS:
            t.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for pad in THT_GND:
        cut.Append(spokes(pad))
    cut.Simplify()
    cu = pcbnew.SHAPE_POLY_SET(inner)
    cu.BooleanSubtract(cut)
    cu.Simplify()
    # drop slivers thinner than 0.2 mm
    cu.Inflate(-FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    cu.Inflate(FromMM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    cu.BooleanIntersection(inner)
    cu.BooleanSubtract(cut)
    cu.Simplify()
    seed = pcbnew.SHAPE_POLY_SET()
    for fp in FP.values():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd_code and pad.IsOnLayer(layer):
                seed.Append(pad_poly(pad, layer, 0.02))
    seed.Simplify()
    kept = 0
    for i in range(cu.OutlineCount()):
        piece = pcbnew.SHAPE_POLY_SET(cu.Polygon(i))
        both = pcbnew.SHAPE_POLY_SET(piece)
        both.BooleanIntersection(seed)
        if area_mm2(both) > 0.005 and area_mm2(piece) > 0.3:
            add_filled(board, piece, layer, nets["GND"])
            kept += 1
            print("  %s ground piece %.0f mm2" % (board.GetLayerName(layer), area_mm2(piece)))
        else:
            print("  %s crumb dropped: %.2f mm2 at %s" % (board.GetLayerName(layer), area_mm2(piece), [round(v, 1) for v in bbox_mm(piece)]))
    assert kept == 1, "the ground copper on each side must be one piece"
    # every ground pad on this layer is reached by copper at least 0.3 mm wide
    core = pcbnew.SHAPE_POLY_SET(cu)
    core.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    core.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    big = max(range(core.OutlineCount()), key=lambda i: area_mm2(pcbnew.SHAPE_POLY_SET(core.Polygon(i))))
    main = pcbnew.SHAPE_POLY_SET(core.Polygon(big))
    for fp in FP.values():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd_code and pad.IsOnLayer(layer):
                hit = pad_poly(pad, layer, 0.05)
                hit.BooleanIntersection(main)
                assert area_mm2(hit) > 0.02, f"{fp.GetReference()}.{pad.GetNumber()} is not solidly joined to ground on {board.GetLayerName(layer)}"


ground(B_Cu)
ground(F_Cu)

# ---- the portrait (only if the owner has said yes; see the note at the top) --------------------------------
if PORTRAIT:
    ptxt = open(PORTRAIT, encoding="utf-8").read()
    n = 0
    for a_, b_ in tblocks(ptxt, "gr_poly"):
        blk = ptxt[a_:b_]
        assert '(layer "F.SilkS")' in blk
        pts = [(float(x), float(y)) for x, y in re.findall(r"\(xy ([-0-9.]+) ([-0-9.]+)\)", blk)]
        shape = poly(pts)
        shape.BooleanIntersection(body)          # the maker's art runs 0.05 mm past the right and bottom edges
        n += add_filled(board, shape, F_SilkS)
    assert n >= 1318, n
    print("PORTRAIT INCLUDED:", n, "front silkscreen polygons from", PORTRAIT)
else:
    print("portrait not included (front silkscreen carries only the sockets' own outlines)")


# ---- back silkscreen labels the standard asks for ----------------------------------------------------------
def text(txt, x, y, size, thick=0.15):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * thick))
    t.SetMirrored(True)
    board.Add(t)
    return t


LX = 33.7                                              # the free corner right of the connector (back view: left of it)
NEW_TEXT = [text("BADGE POWER", LX, 41.0, 0.9, 0.17), text("ONLY", LX, 42.5, 0.9, 0.17),
            text("3 sockets share", LX, 44.3, 0.8), text("50 mA max", LX, 45.6, 0.8),
            text("SAO++ rA", LX, 47.6, 0.9),
            text("1", j["1"][0] - 1.4, j["1"][1] + 1.0, 0.9)]
_new = pcbnew.SHAPE_POLY_SET()
for t in NEW_TEXT:
    _new.Append(ink(t)[1])
_new.Simplify()
_nb = bbox_mm(_new)
print("new labels x %.2f..%.2f y %.2f..%.2f" % (_nb[0], _nb[2], _nb[1], _nb[3]))
_hit = pcbnew.SHAPE_POLY_SET(_new)
_keep = pcbnew.SHAPE_POLY_SET(_art)
_keep.Append(_j1)
_hit.BooleanIntersection(_keep)
assert area_mm2(_hit) < 1e-4, "a new label overlaps the maker's lettering, the logo or the connector"
_off = pcbnew.SHAPE_POLY_SET(_new)
_off.BooleanSubtract(grown(body, -0.6))
assert _off.OutlineCount() == 0, "a new label is closer than 0.6 mm to the board edge"

# ---- settings and save -------------------------------------------------------------------------------------
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

# ---- project file: kicad-cli (10.0.8) can rewrite it and drop custom severities, so the rules this board is checked
#      against are put back on every build
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
pro = json.load(open(PRO))
pro["meta"]["filename"] = SLUG + ".kicad_pro"
pro["board"]["design_settings"]["rules"].update({
    "min_clearance": 0.15, "min_copper_edge_clearance": 0.25, "min_hole_clearance": 0.25, "min_track_width": 0.2,
    "min_silk_clearance": 0.0, "solder_mask_to_copper_clearance": 0.0})
pro["board"]["design_settings"]["rule_severities"].update({
    "clearance": "error", "copper_edge_clearance": "error", "courtyards_overlap": "error", "shorting_items": "error",
    "solder_mask_bridge": "error", "tracks_crossing": "error", "unconnected_items": "error", "track_width": "error",
    "lib_footprint_mismatch": "warning", "lib_footprint_issues": "warning", "silk_overlap": "warning",
    "silk_over_copper": "warning", "copper_sliver": "warning"})
with open(PRO, "w") as f:
    json.dump(pro, f, indent=2, sort_keys=True)
    f.write("\n")
print("rules re-applied to", PRO)
