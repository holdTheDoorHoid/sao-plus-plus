#!/usr/bin/env python3
"""Rebuild nunchuck.kicad_pcb from the maker's 2024 board plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root (after make_local_footprints.py and tools/gen_schematic.py):
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/nunchuck/hardware/build_board.py

What it does
  - loads original/.../SAO_Nunchuck.kicad_pcb (KiCad 8) so the front art, the back lettering and the logo stay exactly
    as drawn
  - removes the maker's through-hole + edge-finger SAO header, the tongue (put back from nunchuck-local, same pads, same
    place), both Qwiic sockets (put back from nunchuck-local, same place), every old track and via, the old outline
    lines (replaced by outline.json: the same path as one polygon) and the drawing-layer dimensions
  - adds the shared SMD SAO connector J1 on the back where the old header was
  - routes it: three trunks on the back from the tongue down to J1, short cross-links on the front in the dark band
    between the tongue and the chain art (the maker ran his front tracks in the same band), 8 tented vias
  - makes the rest of the back copper the GND net, 0.55 mm back from the edge, kept off the tongue

This board has no switch, no coin cell and no controller: it is a passive adapter driven by the badge (see README).
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
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
from saopp_board import ERR, P, mm, poly, grown, area_mm2, cut_blocks, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "nunchuck"
SRC = os.path.join(HERE, "..", "original", "Electronic Design", "SAO Nunchuck V1 Design Files KiCAD 8", "SAO_Nunchuck.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

CLEAR = 0.30        # gap cut into the GND copper round everything that is not GND
POUR_EDGE = 0.55    # GND copper stops this far short of the board edge (panel mouse bites reach 0.25 mm in)
SIG = 0.25          # signal track width
PWR = 0.30          # 3V3 track width on the back
VIA_D, VIA_HOLE = 0.6, 0.3

CX = 107.5182       # the maker's centre line: tongue, old header and the art are all on it
TONGUE_AT = (CX, 114.2251)                      # the maker's tongue footprint origin (unchanged)
J3_AT, J4_AT = (120.2182, 121.2101), (94.6612, 121.2101)   # the maker's Qwiic sockets (X3 right, X4 left in front view)
CONN = (CX, 157.0)  # J1 centre: same centre line as the old header (157.4..160.0), 3.6 mm of board below its body

# ---- strip the maker's electrical parts and drawing aids out of the file text (KiCad 10's Python crashes on Remove()) ----
_txt = open(SRC, encoding="utf-8").read()


def tab_blocks(txt, opener):
    """(start, end) of each top-level '(opener ...)' block of a KiCad 8 file (tab indented)."""
    for m in re.finditer(r"\n\t\(" + opener + r"[ \n]", txt):
        i, depth = m.start() + 2, 0
        for j in range(i, len(txt)):
            depth += txt[j] == "("
            depth -= txt[j] == ")"
            if depth == 0:
                yield m.start(), j + 1
                break


_cut = list(tab_blocks(_txt, "segment")) + list(tab_blocks(_txt, "via")) + list(tab_blocks(_txt, "group")) \
    + list(tab_blocks(_txt, "dimension"))
_cut += [s for s in tab_blocks(_txt, "net") if not _txt[s[0]:s[1]].startswith('\n\t(net 0 ')]
_edges = [s for o in ("gr_line", "gr_arc") for s in tab_blocks(_txt, o) if '(layer "Edge.Cuts")' in _txt[s[0]:s[1]]]
_dwgs = [s for o in ("gr_line", "gr_rect") for s in tab_blocks(_txt, o) if '(layer "Dwgs.User")' in _txt[s[0]:s[1]]]
assert len(_edges) == 9 and len(_dwgs) == 4, (len(_edges), len(_dwgs))
_cut += _edges + _dwgs
# The maker's six lines of back lettering are TrueType text in fonts this machine (and most fab houses' tools) do not
# have ("Apple Chancery", "Comic Sans MS"). KiCad then draws them in a substitute font: wider, and "SAO NUNCHUCK" runs off
# the board. His file also stores each line exactly as his KiCad drew it (the render cache), which matches his own
# 2024 Gerbers. Those shapes are kept as plain silkscreen polygons, so the lettering stays his, letter for letter.
LETTERING = []                                     # [(text, [[outline, hole, ...], ...]), ...]
_texts = [s_ for s_ in tab_blocks(_txt, "gr_text") if '(layer "B.SilkS")' in _txt[s_[0]:s_[1]]]
assert len(_texts) == 6, len(_texts)
for a_, b_ in _texts:
    blk = _txt[a_:b_]
    name = re.search(r'\(gr_text "((?:[^"\\]|\\.)*)"', blk).group(1)
    k = blk.index("(render_cache")
    shapes = []
    for pm in re.finditer(r"\(polygon\s", blk[k:]):
        i, depth = k + pm.start(), 0
        for j in range(i, len(blk)):
            depth += blk[j] == "("
            depth -= blk[j] == ")"
            if depth == 0:
                break
        rings, poly_txt = [], blk[i:j + 1]
        for qm in re.finditer(r"\(pts\s", poly_txt):          # match each (pts ...) by its parentheses: some (xy ...) wrap lines
            d2 = 0
            for q in range(qm.start(), len(poly_txt)):
                d2 += poly_txt[q] == "("
                d2 -= poly_txt[q] == ")"
                if d2 == 0:
                    break
            rings.append([(float(x), float(y)) for x, y in re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\s*\)", poly_txt[qm.start():q + 1])])
        assert rings and all(len(r) >= 3 for r in rings), name
        shapes.append(rings)
    assert shapes, name
    LETTERING.append((name, shapes))
_cut += _texts
_gone = []
for a_, b_ in tab_blocks(_txt, "footprint"):
    ref = re.search(r'\(property "Reference" "([^"]+)"', _txt[a_:b_]).group(1)
    if ref in ("X1", "X2", "X3", "X4"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["X1", "X2", "X3", "X4"], _gone
_txt = cut_blocks(_txt, _cut)
_txt = re.sub(r'\(net \d+\)\n', '', _txt)        # (nothing left refers to the old nets)
_tmp = os.path.join(tempfile.mkdtemp(), "SAO_Nunchuck.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)
board = pcbnew.LoadBoard(_tmp)
assert len(board.GetFootprints()) == 1, "only the maker's logo (L1) should be left"
art_cu = [d for d in board.GetDrawings() if d.GetLayer() == F_Cu]
assert len(art_cu) == 17, len(art_cu)

# ---- outline: the maker's 9 board lines + the 19 tongue/slot lines of his tongue footprint, as one polygon ----
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.05))
board.Add(e)

# ---- the circuit (shared with the schematic generator) ------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p["ref"]: p for p in CIRCUIT["parts"]}
PADNETS = {r: p.get("nets", {}) for r, p in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for r, p in PARTS.items()}
_NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")          # same namespace as tools/gen_schematic.py
nets = {}
for n in sorted({n for d in PADNETS.values() for n in d.values()}):
    nets[n] = pcbnew.NETINFO_ITEM(board, n)
    board.Add(nets[n])


def link(fp, ref):
    """Tie the footprint to its schematic symbol (path, part fields, nets) so KiCad's schematic-parity check passes."""
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
    lib, name = fpid.split(":")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPath(pcbnew.KIID_PATH("/" + str(uuid.uuid5(_NS, SLUG + ":" + ref))))
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


def place(ref, pos, want, back=True):
    """Pick the right-angle rotation that puts every pad named in `want` at its given spot."""
    fp = load(ref, pos, back)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        d = 0.0
        for num, (x, y) in want.items():
            px, py = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]
            d += abs(px - x) + abs(py - y)
        if best is None or d < best[0]:
            best = (d, rot)
    assert best[0] < 0.02 * len(want), f"{ref}: no rotation puts the pads where wanted (miss {best[0]:.3f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def pad_at(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


# the tongue stays exactly where the maker drew it, on the front layer (its fingers are on both sides)
tongue = place("J2", TONGUE_AT, {"1": (109.5502, 119.3051), "4": (105.4862, 119.3051)}, back=False)
# the Qwiic sockets: the maker's pad positions (read from his board), openings at the left and right edges
j3 = place("J3", J3_AT, {"1": (118.2182, 119.7101), "4": (118.2182, 122.7101)})
j4 = place("J4", J4_AT, {"1": (96.6612, 122.7101), "4": (96.6612, 119.7101)})
# SAO connector: VCC top-left in front view (= the corner Mad Cat uses), key slot toward the tongue (top)
conn = place("J1", CONN, {"1": (CONN[0] - 2.54, CONN[1] - 3.4)})

for fp in board.GetFootprints():
    if fp.GetReference() not in PARTS:     # the maker's logo: board-only art (its library is the maker's, not shipped here)
        fp.SetFPID(pcbnew.LIB_ID("", "Machine_Ideas_logo"))
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# ---- routing ------------------------------------------------------------------------------------
TRACKS = []


def route(net, pts, layer=B_Cu, width=SIG):
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
        TRACKS.append(t)


VIAS = []


def via(c, net):
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


T3V3, TSDA, TSCL, TGND = pad_at(tongue, "3"), pad_at(tongue, "1"), pad_at(tongue, "4"), pad_at(tongue, "6")
J1 = {n: pad_at(conn, n) for n in "1234"}
Q3 = {n: pad_at(j3, n) for n in "1234"}
Q4 = {n: pad_at(j4, n) for n in "1234"}
X3V3, XSDA = T3V3[0], TSDA[0]               # the back trunks run straight down from the fingers
GAP = CONN[1]                               # between J1's two pad rows (rows at y -/+ 3.4, pads 4.4 long)

# front cross-links, in the dark band between the tongue (slot bottoms at y 122.63) and the chain art (from y 126.76)
Y_SCL, Y_SDA, Y_3V3 = 124.3, 125.0, 125.7
V_SCL = (102.0, Y_SCL)                      # SCL: front finger -> back trunk
V_SDA = (XSDA, Y_SDA)                       # SDA: left socket's SDA lands on the SDA trunk
V_3V3 = (X3V3, Y_3V3)                       # 3V3: both sockets' 3V3 land on the 3V3 trunk
V_GND = (110.6, 123.5)                      # GND: front finger -> back ground copper
V_Q4SDA, V_Q4_3V3 = (98.2, Q4["3"][1]), (98.2, Q4["2"][1])      # beside the left socket's pads
V_Q3_3V3, V_Q3SCL = (116.6, Q3["2"][1]), (116.6, Q3["4"][1])    # beside the right socket's pads
for c, n in ((V_SCL, "SCL"), (V_SDA, "SDA"), (V_3V3, "3V3"), (V_GND, "GND"),
             (V_Q4SDA, "SDA"), (V_Q4_3V3, "3V3"), (V_Q3_3V3, "3V3"), (V_Q3SCL, "SCL")):
    via(c, n)

# back: 3V3 trunk  finger 3 -> J1 pin 1 (top-left)
route("3V3", [T3V3, V_3V3, (X3V3, 149.9), (J1["1"][0], 150.4), J1["1"]], width=PWR)
# back: SDA trunk  finger 1 -> J1 pin 3 (top middle); the right socket's SDA joins it under the tongue
Y_Q3SDA = 124.6
route("SDA", [TSDA, (XSDA, Y_Q3SDA), V_SDA, (XSDA, 149.4), (J1["3"][0], 151.43), J1["3"]])
route("SDA", [Q3["3"], (115.7, Q3["3"][1]), (115.7, Y_Q3SDA), (XSDA, Y_Q3SDA)])
# back: SCL trunk  left socket's SCL -> down the left -> between J1's pad rows -> J1 pin 4 (bottom middle)
route("SCL", [Q4["4"], (99.8, Q4["4"][1]), (99.8, 123.3), (100.8, Y_SCL), V_SCL, (V_SCL[0], GAP), (J1["4"][0], GAP), J1["4"]])
# back: the socket pins that cross over on the front go straight to their vias
route("SDA", [Q4["3"], V_Q4SDA])
route("3V3", [Q4["2"], V_Q4_3V3])
route("3V3", [Q3["2"], V_Q3_3V3])
route("SCL", [Q3["4"], V_Q3SCL])

# front: SCL finger 4 -> SCL trunk via, and -> the right socket's SCL via
route("SCL", [TSCL, (TSCL[0], Y_SCL)], layer=F_Cu)
route("SCL", [V_SCL, (TSCL[0], Y_SCL), (V_Q3SCL[0], Y_SCL), V_Q3SCL], layer=F_Cu)
# front: GND finger 6 -> its via
route("GND", [TGND, (TGND[0], 122.9), V_GND], layer=F_Cu)
# front: the left socket's SDA -> SDA trunk via
route("SDA", [V_Q4SDA, (99.4, V_Q4SDA[1]), (99.4, Y_SDA), V_SDA], layer=F_Cu)
# front: both sockets' 3V3 -> 3V3 trunk via (the right one goes round the outside of the right socket's SCL via)
route("3V3", [V_Q4_3V3, (V_Q4_3V3[0], Y_3V3), V_3V3, (117.7, Y_3V3), (117.7, 121.3), V_Q3_3V3], layer=F_Cu)

# every new pad and via on the board, and pads (other than the tongue's edge fingers) >= 0.25 mm from the edge
inner25 = grown(body, -0.25)
for fp in board.GetFootprints():
    if fp.GetReference() in PARTS and fp.GetReference() != "J2":
        for pad in fp.Pads():
            for L in (B_Cu, F_Cu):
                if pad.IsOnLayer(L):
                    off = pad_poly(pad, L)
                    off.BooleanSubtract(inner25)
                    assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the edge"

# ---- back copper: GND everywhere else, kept off the tongue ---------------------------------------
gnd = grown(body, -POUR_EDGE)
gnd.BooleanSubtract(poly([(100.0, 110.0), (115.0, 110.0), (115.0, 123.45), (100.0, 123.45)]))   # the tongue and the slots
cut = pcbnew.SHAPE_POLY_SET()
gnd_code = nets["GND"].GetNetCode()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetNetCode() != gnd_code:
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
for t in board.Tracks():
    if t.GetNetname() != "GND" and (t.GetClass() == "PCB_VIA" or t.GetLayer() == B_Cu):
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
cut.Simplify()
_full = pcbnew.SHAPE_POLY_SET(gnd)
_full.BooleanSubtract(cut)
# open the copper by 0.1 mm to drop slivers narrower than 0.2 mm (between the Qwiic pads and the pad stubs):
# erode as (outline shrunk) minus (cut grown), which never shrinks a shape with holes, then grow back inside the full pour
_er = grown(gnd, -0.1)
_er.BooleanSubtract(grown(cut, 0.1))
gnd = grown(_er, 0.1)
gnd.BooleanIntersection(_full)
gnd.Simplify()
gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_pads.Append(pad_poly(pad, B_Cu))
for t in board.Tracks():
    if t.GetNetname() == "GND" and t.GetClass() == "PCB_VIA":
        t.TransformShapeToPolygon(gnd_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_pads.Simplify()
n_gnd = n_drop = 0
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    if area_mm2(both) > 0.005 and area_mm2(piece) > 1.0:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
    else:
        n_drop += 1
        print("  dropped a ground island that touches no ground pad, mm2:", round(area_mm2(piece), 2))
print("back ground pieces:", n_gnd, "dropped:", n_drop)

# ---- back silkscreen: the maker's lettering and logo stay as they were; small SAO++ labels -------------
def text(txt, x, y, size, rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    t.SetPosition(P(x, y))
    board.Add(t)
    return t


let = pcbnew.SHAPE_POLY_SET()
for name, shapes in LETTERING:
    for rings in shapes:
        let.NewOutline()
        for x, y in rings[0]:
            let.Append(FromMM(x), FromMM(y))
        for h in rings[1:]:
            let.NewHole()
            for x, y in h:
                let.Append(FromMM(x), FromMM(y), -1, let.HoleCount(let.OutlineCount() - 1) - 1)
let.Simplify()
_lb = let.BBox()
print("maker's lettering:", len(LETTERING), "lines,", sum(len(sh) for _, sh in LETTERING), "glyph shapes, x",
      round(ToMM(_lb.GetLeft()), 2), "..", round(ToMM(_lb.GetRight()), 2))
add_filled(board, let, B_SilkS)

text("1", CONN[0] - 8.7, J1["1"][1], 0.9)              # pin 1 (VCC) marker, as Mad Cat
text("SAO++ rA", 119.6, 160.4, 0.9)
text("Qwiic", Q3["1"][0] + 1.6, 125.7, 0.8)
text("Qwiic", Q4["1"][0] - 1.6, 125.7, 0.8)

# ---- report -------------------------------------------------------------------------------------
for fp in (conn, tongue, j3, j4):
    print(fp.GetReference(), {p.GetNumber(): mm(p.GetPosition()) for p in fp.Pads()})
print("vias:", len(VIAS))
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
