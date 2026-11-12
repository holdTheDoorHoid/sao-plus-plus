#!/usr/bin/env python3
"""Rebuild lecco.kicad_pcb from davedarko's KiCad 9 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/lecco/hardware/build_board.py

What the original is (read from the files; the maker's readme only apologises for "the footprint fail"):
  - a 54 x 40 mm postcard with 7 mm round corners. Front: his engraving of the Azzone Visconti bridge in Lecco, as the
    40 mm art footprint (Lecco:leccoPostcard_40mm; the full-size leccoPostcard.kicad_mod in original/ is not used by
    his board), 'LECCO' as a solder-mask opening over copper (gold), and 'ITALY' as a mask opening on BOTH sides
    with a copper keep-out on both layers: a window of bare board, meant to glow.
  - back: a handwritten postcard message, signature, date and his logo; a 2x3 SMD footprint for the SAO header; and
    the LED that was never given a footprint: two round 2 mm pads marked VCC and GND just under the window, one
    0603 resistor ('bridge or add resistor') from the header's VCC to the + pad, and the note 'fancy a LED?'.
  - the "footprint fail": the header footprint is KiCad's PinSocket_2x03 SMD, whose pad rows are the mirror of a
    pin header's, so the header he asks for in the readme does not land the way the footprint says.

What this script does
  - cuts out of the file text: the header, resistor and two LED pads, tracks, via, both zones, the Edge.Cuts lines
    and arcs, the 'VCC' / 'GND' / 'bridge or add resistor' labels (no longer true), and the five texts drawn in fonts
    this machine does not have (Futura, Bradley Hand). Those five are re-added as the exact outlines KiCad cached when
    the maker saved the file (render_cache), so they come out as he drew them on any computer
  - scales the whole board up by SCALE (outline, art, lettering, logo, uniformly) so the SAO connector fits in the
    strip beside the message without covering it (owner rule 2026-11-12)
  - places on the back: the SAO connector (key up, pin 1 top left in front view), one shared 1.3 k resistor and one
    shared white reverse-mount LED shining through the board behind 'ITALY'
  - no coin cell and no switch: see README ("Why no battery")
  - front copper: a plain copper sheet (no net) like the maker's front pour, kept off the ITALY window
  - back copper: GND, cleared around everything that is not GND and off the ITALY window / LED light path

Coordinates are millimetres in KiCad's front view (x grows right, y grows down), AFTER scaling.
"""
import json
import os
import re
import sys
import tempfile
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import (ERR, P, mm, add_circle, poly, grown, area_mm2, cut_blocks, bbox_mm, add_filled,  # noqa: E402
                         pad_poly)
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "lecco"
SRC = os.path.join(HERE, "..", "original", "lecco", "lecco.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")

SCALE = 1.2         # 54 x 40 mm -> 64.8 x 48 mm. Smallest round factor that puts the connector's 15.3 mm plastic body
                    # in the strip right of the message with >= 0.3 mm to spare each side (1.18 is the bare minimum)
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
TRACK = 0.40
THIN = 0.30
EDGE = 0.55         # all copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
PAD_EDGE = 0.25
WINDOW_R = 1.6      # no copper on either side within this radius of the LED centre (docs/standard.md section 4)


def S(v):
    return v * SCALE


# ---- cut the original's electrical parts and unportable texts out of the file text -----------------
_txt = open(SRC, encoding="utf-8").read()


def tblocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block of a KiCad 9 file (one tab of indent)."""
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
    if ref in ("R1", "J1", "TP1", "TP2"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["J1", "R1", "TP1", "TP2"], _gone
for kind in ("segment", "via", "zone", "gr_line", "gr_arc"):
    _cut += list(tblocks(_txt, kind))
LAYER = {"B.SilkS": pcbnew.B_SilkS, "F.Mask": pcbnew.F_Mask, "B.Mask": pcbnew.B_Mask}
CACHED = []                     # (text, layer, [polygon point lists]) taken from render_cache
_labels = 0
for a_, b_ in tblocks(_txt, "gr_text"):
    blk = _txt[a_:b_]
    name = re.match(r'\n\t\(gr_text "([^"]*)"', blk).group(1)
    if name in ("VCC", "GND") or name.startswith("bridge"):
        _cut.append((a_, b_))
        _labels += 1
    elif "(render_cache" in blk:
        lay = re.search(r'\(layer "([^"]+)"', blk).group(1)
        polys = []
        for pm in re.finditer(r"\(polygon\s*\(pts((?:\s*\(xy [^)]*\))*)\s*\)", blk[blk.index("(render_cache"):], re.S):
            pts = [(float(x), float(y)) for x, y in re.findall(r"\(xy ([-\d.]+)\s+([-\d.]+)\s*\)", pm.group(1))]
            if len(pts) > 2:
                polys.append(pts)
        _cache = blk[blk.index("(render_cache"):]
        assert sum(len(q) for q in polys) == _cache.count("(xy "), f"{name[:12]}: lost points reading the cached outline"
        assert len(polys) == _cache.count("(polygon"), name[:12]
        CACHED.append((name, lay, polys))
        _cut.append((a_, b_))
assert _labels == 3, _labels
assert sorted(n[:6] for n, _, _ in CACHED) == ["- Dave", "Dear F", "ITALY", "ITALY", "LECCO"], CACHED
_cut += [(m.start(), m.end()) for m in re.finditer(r'\n\t\(net [1-9]\d* "[^"]*"\)', _txt)]
_txt = cut_blocks(_txt, _cut)
_tmp = os.path.join(tempfile.mkdtemp(), "lecco.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
TRACKS = []

# ---- scale everything the maker drew -------------------------------------------------------------
for fp in list(board.GetFootprints()):
    at = fp.GetPosition()
    fp.SetLocked(False)
    fp.SetPosition(VECTOR2I(0, 0))                   # children move with it: now relative to the origin
    for g in fp.GraphicalItems():
        if isinstance(g, pcbnew.PCB_SHAPE):
            g.Scale(SCALE)
            g.SetWidth(int(g.GetWidth() * SCALE))
    for f in (fp.Reference(), fp.Value()):
        f.SetPosition(VECTOR2I(int(f.GetPosition().x * SCALE), int(f.GetPosition().y * SCALE)))
        f.SetVisible(False)                        # 'G***' / 'Ref**' are library placeholders, not art
    fp.SetPosition(VECTOR2I(int(at.x * SCALE), int(at.y * SCALE)))
    fp.SetLocked(True)
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
ART = [fp for fp in board.GetFootprints() if "leccoPostcard_40mm" in fp.GetFPIDAsString()]
LOGO = [fp for fp in board.GetFootprints() if "logo" in fp.GetFPIDAsString()]
assert len(ART) == 1 and len(LOGO) == 1 and len(board.GetFootprints()) == 2
_texts = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT)]
assert sorted(t.GetText().split("\n")[0] for t in _texts) == ["2026-05-16/17", "fancy"], [t.GetText() for t in _texts]
for t in _texts:                                    # KiCad's own stroke font: scale position, size and stroke
    t.SetPosition(VECTOR2I(int(t.GetPosition().x * SCALE), int(t.GetPosition().y * SCALE)))
    t.SetTextSize(VECTOR2I(int(t.GetTextSize().x * SCALE), int(t.GetTextSize().y * SCALE)))
    t.SetTextThickness(int(t.GetTextThickness() * SCALE))
for d in board.GetDrawings():
    assert isinstance(d, pcbnew.PCB_TEXT), d.GetClass()

# the five font texts, as the outlines the maker's machine cached, scaled
TEXTPOLY = {}
for name, lay, polys in CACHED:
    ps = pcbnew.SHAPE_POLY_SET()
    for pts in polys:
        ps.NewOutline()
        for x, y in pts:
            ps.Append(FromMM(S(x)), FromMM(S(y)))
    TEXTPOLY[(name.split("\\n")[0], lay)] = ps   # the file stores line breaks as a literal backslash-n
    if lay == "B.Mask":
        continue                                    # the back ITALY window is added after routing (see below)
    for pts in polys:
        add_filled(board, poly([(S(x), S(y)) for x, y in pts]), LAYER[lay])
MESSAGE = pcbnew.SHAPE_POLY_SET(TEXTPOLY[("Dear Friend,", "B.SilkS")])
MESSAGE.Append(TEXTPOLY[("- Dave (@davedarko)", "B.SilkS")])
MSG_BOX = bbox_mm(MESSAGE)
ITALY = TEXTPOLY[("ITALY", "F.Mask")]
IT_BOX = bbox_mm(ITALY)
print("message x %.2f..%.2f y %.2f..%.2f; ITALY x %.2f..%.2f y %.2f..%.2f" % (MSG_BOX[0], MSG_BOX[2], MSG_BOX[1], MSG_BOX[3], *[IT_BOX[i] for i in (0, 2, 1, 3)]))
# the maker's copper keep-out round the word, both layers (41..50 x 9..12.25 before scaling)
KEEP = (S(41.0), S(9.0), S(50.0), S(12.25))
keep = poly([(KEEP[0], KEEP[1]), (KEEP[2], KEEP[1]), (KEEP[2], KEEP[3]), (KEEP[0], KEEP[3])])

# ---- outline: the maker's rounded rectangle, scaled -------------------------------------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly([(S(x), S(y)) for x, y in _ol["outer"]])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
BB = bbox_mm(body)
W, H = BB[2] - BB[0], BB[3] - BB[1]
print("board %.2f x %.2f mm (scale %.2f)" % (W, H, SCALE))
inner = grown(body, -EDGE)
pad_ok = grown(body, -PAD_EDGE)

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
    """Place on the back, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
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


# ---- placement -----------------------------------------------------------------------------------
BODY_HALF = 7.635                   # the connector's plastic body is 15.27 mm wide with the key slot up
CONN = (round(BB[2] - 0.30 - BODY_HALF, 2), 26.0)       # body 0.30 mm inside the right edge; mid-height of the board
assert CONN[0] - BODY_HALF - MSG_BOX[2] >= 0.3, "connector body would cover the message"
print("connector body x %.2f..%.2f; message ends at x %.2f (gap %.2f mm)" % (CONN[0] - BODY_HALF, CONN[0] + BODY_HALF, MSG_BOX[2], CONN[0] - BODY_HALF - MSG_BOX[2]))
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))     # VCC: top row, left in front view, as on Mad Cat
LED = (round((IT_BOX[0] + IT_BOX[2]) / 2, 2), round((IT_BOX[1] + IT_BOX[3]) / 2, 2))    # centre of the word ITALY
led = place("D1", LED, ("2", (LED[0] - 1.55, LED[1])))                 # anode on the left, toward the resistor
# the LED's cathode bar would sit on the back ITALY window (silk is not printed on bare board): fab layer instead;
# the assembler goes by the placement file, and the polarity is in the README
for g in led.GraphicalItems():
    if g.GetLayer() == B_SilkS:
        g.SetLayer(pcbnew.B_Fab)
j1 = padpos(conn, "1")
R1_AT = (j1[0], 17.6)
res = place("R1", R1_AT, ("1", (R1_AT[0], R1_AT[1] + 0.825)))          # VCC pad at the bottom, toward the connector

for fp in (conn, led, res):
    for pad in fp.Pads():
        off = pad_poly(pad, B_Cu)
        off.BooleanSubtract(pad_ok)
        assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than {PAD_EDGE} mm to the edge"


# ---- routing (back copper only, no vias) --------------------------------------------------------------
def route(net, pts, width=TRACK, clear=CLEAR):
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


r1, r2 = padpos(res, "1"), padpos(res, "2")
da, dk = padpos(led, "2"), padpos(led, "1")
route("VCC", [j1, r1])
route("LED_A", [r2, (r2[0], r2[1] - 0.6), (da[0], LED[1] + 2.4), da], width=THIN)
route("GND", [dk, (dk[0], LED[1] + 2.6)], width=THIN)          # out of the window into the GND copper below it

# ---- light path: no copper on either side within WINDOW_R of the LED, nor in the maker's ITALY keep-out ----
light = pcbnew.SHAPE_POLY_SET(keep)
add_circle(light, P(*LED), WINDOW_R)
light.Simplify()

# ---- front copper: the maker's front pour (no net), kept off the window --------------------------------------
front = pcbnew.SHAPE_POLY_SET(inner)
front.BooleanSubtract(light)
add_filled(board, front, F_Cu, None)

# ---- back copper: GND everywhere, cleared around everything that is not GND -------------------------
art = pcbnew.SHAPE_POLY_SET(inner)
cut = pcbnew.SHAPE_POLY_SET(light)
gnd_code = nets["GND"].GetNetCode()
for fp in (conn, led, res):
    for pad in fp.Pads():
        if pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
channels = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    if t.GetNetCode() != gnd_code:
        t.TransformShapeToPolygon(channels, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
channels.Simplify()
cut.Append(channels)
cut.Simplify()
art.BooleanSubtract(cut)
art.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
art.BooleanSubtract(cut)
art.Simplify()

# no track may run through the maker's lettering: the message, the signature, and the back ITALY window
_all = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(_all, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
_all.Simplify()
_hit = pcbnew.SHAPE_POLY_SET(_all)
_hit.BooleanIntersection(MESSAGE)
assert area_mm2(_hit) < 1e-4, "a track crosses the message"
_hit = pcbnew.SHAPE_POLY_SET(_all)
_hit.BooleanIntersection(TEXTPOLY[("ITALY", "B.Mask")])
print("track copper inside the back ITALY mask opening, mm2: %.3f" % area_mm2(_hit))
# The back ITALY is the maker's mask window that lets light into the board; the LED now sits right on it. The two short
# LED tracks leave their pads across the bottoms of the 'A' and the 'L'; the window is trimmed 0.1 mm clear of them
# so no bare track copper shows (the pads themselves have their own mask openings anyway).
_bwin = pcbnew.SHAPE_POLY_SET()
for name_, lay_, polys_ in CACHED:
    if lay_ == "B.Mask":
        for pts in polys_:
            _bwin.Append(poly([(S(x), S(y)) for x, y in pts]))
_bwin.Simplify()
_a0 = area_mm2(_bwin)
_tr = pcbnew.SHAPE_POLY_SET()
for t, clear in TRACKS:
    t.TransformShapeToPolygon(_tr, B_Cu, FromMM(0.1), ERR, pcbnew.ERROR_OUTSIDE)
_tr.Simplify()
_bwin.BooleanSubtract(_tr)
print("back ITALY window: %.2f mm2, trimmed by %.3f mm2 around the LED tracks" % (_a0, _a0 - area_mm2(_bwin)))
add_filled(board, _bwin, pcbnew.B_Mask)

n = 0
for i in range(art.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(art.Polygon(i))
    add_filled(board, piece, B_Cu, nets["GND"])
    n += 1
print("back GND copper pieces:", n)

# ---- back silkscreen labels ----------------------------------------------------------------------
LABELS = [("1", j1[0] - 1.6, j1[1] - 2.6, 0.9), ("SAO++ rA", CONN[0], 34.0, 0.9)]
for txt, x, y, size in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    board.Add(t)

# ---- report -------------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("D1 at", LED, "pads:", {p.GetNumber(): mm(p.GetPosition()) for p in led.Pads()})
print("R1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in res.Pads()})
print("logo box", [round(v, 2) for v in bbox_mm(poly([(ToMM(LOGO[0].GetBoundingBox(False).GetLeft()), ToMM(LOGO[0].GetBoundingBox(False).GetTop())),
                                                        (ToMM(LOGO[0].GetBoundingBox(False).GetRight()), ToMM(LOGO[0].GetBoundingBox(False).GetBottom())),
                                                        (ToMM(LOGO[0].GetBoundingBox(False).GetLeft()), ToMM(LOGO[0].GetBoundingBox(False).GetBottom()))]))])
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
