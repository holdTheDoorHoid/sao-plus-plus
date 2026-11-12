#!/usr/bin/env python3
"""Rebuild sao-nunchuck.kicad_pcb from ageppert's KiCad 8 original plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/sao-nunchuck/hardware/build_board.py

What the original is (read from the maker's files, commit 6b02ca0):
  - a 38.1 x 50.8 mm board with rounded corners and a notch in the top edge. In the notch stands a 6.3 mm wide tongue
    with five gold fingers (three on the back, two on the front): a Nunchuck controller's plug slides onto it.
  - a passive adaptor: 3.3 V, ground, SDA and SCL run from the SAO header straight to the fingers and to two Qwiic
    sockets (JST SH 4-pin) on the back. No chip, no LED, no resistor, no pull-ups.
  - the SAO header was a through-hole 2x3 at the bottom, doubled by edge fingers for a right-angle socket.
  - front art: a Wii Remote and a Nunchuck joined by a chain like a pair of nunchaku, in bare (gold) copper.
  - back silkscreen: 'SAO NUNCHUCK', the I2C address, the makers' credit and logo, 'Manufactured by PCBX.COM',
    '2024', 'V1.0'.

What this script does
  - loads the original and cuts out of the file text (KiCad 10's Python crashes on Remove()): the four connector
    footprints, the outline lines, the maker's construction lines and dimensions, 'Manufactured by PCBX.COM', and
    every track that ran down to the old header
  - outline: the maker's, unchanged, as one polygon (outline.json) so the panel tool can read it
  - SAO++ connector J1 on the back at the bottom, key slot up, in the old header's columns (no holes in the front)
  - the maker's finger footprint X2 and Qwiic footprints X3 / X4 go back exactly where they were (from
    sao-nunchuck-local.pretty); the Qwiic sockets are pads only, not fitted
  - the maker's tracks and vias round the plug and the Qwiic pads stay exactly as drawn; four new back tracks run
    down his four columns to J1
  - new: a ground copper fill on the back (docs/standard.md section 2 asks for copper round the connector), kept off
    the plug tongue
  - back silkscreen: 'SAO++ rA   BADGE POWER ONLY' and a pin-1 mark. Everything of the maker's stays except the
    'Manufactured by PCBX.COM' line, which would not be true of SAO++ boards
  - re-applies the project's rule settings to sao-nunchuck.kicad_pro (kicad-cli 10.0.8 can rewrite that file)

Coordinates are millimetres in KiCad's front view, the maker's own (board spans x 88.47..126.57, y 114.23..165.03).
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
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, cut_blocks, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402

SLUG = "sao-nunchuck"
SRC = os.path.join(HERE, "..", "original", "Electronic Design", "SAO Nunchuck V1 Design Files KiCAD 8", "SAO_Nunchuck.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))

CLEAR = 0.30        # gap cut into the ground fill round other copper
EDGE = 0.55         # the fill stops this far short of the board edge (clear of the panel's mouse-bite holes)
PWR, SIG = 0.4064, 0.2032   # the maker's two track widths (16 and 8 mil)

CX = 107.5182               # the board's centre line; the maker's header and plug both sit on it
J1_AT = (CX, 156.0)         # connector centre: bottom pads end 3.4 mm from the bottom edge (the rule is 3 mm)
X2_AT = (107.5182, 114.2251)                     # the maker's positions, unchanged
X3_AT, X3_PAD1 = (120.2182, 121.2101), (118.2182, 119.7101)
X4_AT, X4_PAD1 = (94.6612, 121.2101), (96.6612, 122.7101)
# the four columns the maker's tracks came down the board in, and where each one starts (his via or junction)
COL = {"3V3": (104.9782, 124.3851), "GND": (106.2990, 125.1471), "SDA": (107.5182, 125.7821), "SCL": (108.7882, 126.2901)}

# ---- cut the old connectors, outline and bottom tracks out of the file text ------------------------
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
    if ref in ("X1", "X2", "X3", "X4"):
        _cut.append((a_, b_))
        _gone.append(ref)
assert sorted(_gone) == ["X1", "X2", "X3", "X4"], _gone
_n = len(_cut)
for kind in ("gr_line", "gr_arc", "gr_rect"):
    _cut += [(a_, b_) for a_, b_ in tblocks(_txt, kind) if '(layer "Edge.Cuts")' in _txt[a_:b_] or '(layer "Dwgs.User")' in _txt[a_:b_]]
assert len(_cut) - _n == 13, len(_cut) - _n            # 9 outline pieces + 4 construction lines
_dims = list(tblocks(_txt, "dimension"))
assert len(_dims) == 2
_cut += _dims
_pcbx = [(a_, b_) for a_, b_ in tblocks(_txt, "gr_text") if _txt[a_:b_].startswith('\n\t(gr_text "Manufactured by PCBX.COM"')]
assert len(_pcbx) == 1
_cut += _pcbx
_low = []
for a_, b_ in tblocks(_txt, "segment"):
    ys = [float(y) for y in re.findall(r"\((?:start|end) [-0-9.]+ ([-0-9.]+)\)", _txt[a_:b_])]
    if max(ys) > 150:
        _low.append((a_, b_))
assert len(_low) == 19, len(_low)                      # the four long runs and everything round the old header
_cut += _low
_nc = [(m.start(), m.end()) for m in re.finditer(r'\n\t\(net \d+ "unconnected-[^"]*"\)', _txt)]
assert len(_nc) == 9, len(_nc)
_cut += _nc
_txt = cut_blocks(_txt, _cut)
for old, new in (('"/SDA"', '"SDA"'), ('"/SCL"', '"SCL"')):     # the generated schematic uses global labels: no slash
    assert old in _txt
    _txt = _txt.replace(old, new)
_tmp = os.path.join(tempfile.mkdtemp(), "nunchuck.kicad_pcb")
open(_tmp, "w", encoding="utf-8").write(_txt)

board = pcbnew.LoadBoard(_tmp)
assert len(board.GetFootprints()) == 1 and len(board.GetTracks()) == 64 + 16 - 19

# ---- outline: the maker's, as one polygon ------------------------------------------------------------
_ol = json.load(open(os.path.join(HERE, "outline.json")))
assert not _ol["holes"]
body = poly(_ol["outer"])
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(_ol["outer"]))
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
    nets[n] = board.FindNet(n)
    assert nets[n] is not None, f"the maker's board has no net {n}"


# ---- footprints ---------------------------------------------------------------------------------
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
        else:
            f = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), k)
            f.SetText(v)
            f.SetVisible(False)
            f.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)
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
    """Place the part, then pick the right-angle rotation that puts pad `want[0]` at `want[1]`."""
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)                       # add first: flipping a footprint that has no board crashes KiCad 10
    fp.SetPosition(P(*pos))
    if back:
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber() == want[0] and pad.IsOnLayer(B_Cu if want[2] == "B" else F_Cu):
                px, py = mm(pad.GetPosition())
                d = abs(px - want[1][0]) + abs(py - want[1][1])
                if best is None or d < best[0]:
                    best = (d, rot)
    assert best[0] < 0.01, f"{ref}: no rotation puts pad {want[0]} at {want[1]} (best miss {best[0]:.3f} mm)"
    fp.SetOrientationDegrees(best[1])
    link(fp, ref)
    return fp


def padpos(fp, num):
    return [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num][0]


# J1: 3.3 V (pin 1) top left in front view = top right seen from the back, as on every SAO++ board; key slot up
conn = place("J1", J1_AT, ("1", (J1_AT[0] - 2.54, J1_AT[1] - 3.4), "B"))
conn.Reference().SetVisible(False)
assert padpos(conn, "2") == (round(J1_AT[0] - 2.54, 3), round(J1_AT[1] + 3.4, 3))
# the maker's fingers: back SDA right (front view), detect middle, 3.3 V left; front SCL left, GND right
plug = place("X2", X2_AT, ("1", (109.5502, 119.3051), "B"), back=False)
assert padpos(plug, "3") == (105.486, 119.305) and padpos(plug, "4") == (105.486, 119.305) and padpos(plug, "6") == (109.55, 119.305)
qw3 = place("X3", X3_AT, ("1", X3_PAD1, "B"))
qw4 = place("X4", X4_AT, ("1", X4_PAD1, "B"))
assert padpos(qw3, "4") == (118.218, 122.71) and padpos(qw4, "4") == (96.661, 119.71)
# The maker's 'X2' / 'X3' / 'X4' marks on the back stay, but as plain lettering: the panel tool renumbers parts
# (X3 -> X103 ...), and a part's own reference text would be reprinted with the new number on every board.
for fp in (plug, qw3, qw4):
    fp.Value().SetVisible(False)
    r = fp.Reference()
    assert r.GetLayer() == B_SilkS and r.IsVisible()
    t = pcbnew.PCB_TEXT(board)
    t.SetText(fp.GetReference())
    t.SetLayer(B_SilkS)
    t.SetAttributes(r)                  # the maker's size, thickness, mirroring and alignment
    t.SetPosition(r.GetPosition())
    t.SetTextAngleDegrees(r.GetTextAngleDegrees() % 180)   # a part's reference is kept upright by KiCad; plain text is not
    t.SetVisible(True)
    board.Add(t)
    r.SetVisible(False)
logo = [fp for fp in board.GetFootprints() if fp.GetReference() not in PARTS]
assert len(logo) == 1 and "logo" in logo[0].GetFPIDAsString()
logo[0].SetAttributes(logo[0].GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

# ---- routing: the maker's four columns, now ending on J1's pads (back copper only) ---------------------
NEW_TRACKS = []


def route(net, pts, width):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        NEW_TRACKS.append(t)


p1, p2, p3, p4 = (padpos(conn, n) for n in "1234")
MID = J1_AT[1]                               # the gap between the connector's two pad rows (pads end 1.2 mm either side)
route("3V3", [COL["3V3"], p1], PWR)                                             # straight down into pin 1
route("SDA", [COL["SDA"], p3], SIG)                                             # straight down into pin 3
# GND and SCL come down between the top-row pads (0.57 mm clear of each), then step one column left to the bottom row
route("GND", [COL["GND"], (COL["GND"][0], MID - 0.3), (p2[0], MID - 0.3 + (COL["GND"][0] - p2[0])), p2], PWR)
route("SCL", [COL["SCL"], (COL["SCL"][0], MID - 0.3), (p4[0], MID - 0.3 + (COL["SCL"][0] - p4[0])), p4], SIG)

# ---- back copper: ground fill, cleared round everything that is not ground -----------------------------
gnd_code = nets["GND"].GetNetCode()
fill = pcbnew.SHAPE_POLY_SET(inner)
# keep the fill off the tongue and out of the notch corners: the plug's contacts and shell slide there
fill.BooleanSubtract(poly([(99.5, 113.0), (115.5, 113.0), (115.5, 123.7), (99.5, 123.7)]))
cut = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() != gnd_code and pad.IsOnLayer(B_Cu):
            pad.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
gnd_cu = pcbnew.SHAPE_POLY_SET()
for t in board.GetTracks():
    is_via = t.Type() == pcbnew.PCB_VIA_T
    if t.GetNetCode() == gnd_code:
        if is_via:
            add_circle(gnd_cu, t.GetPosition(), 0.2)
        elif t.GetLayer() == B_Cu:
            t.TransformShapeToPolygon(gnd_cu, B_Cu, 0, ERR, pcbnew.ERROR_INSIDE)
    elif is_via:
        add_circle(cut, t.GetPosition(), ToMM(t.GetWidth(B_Cu)) / 2 + CLEAR + 0.02)
    elif t.GetLayer() == B_Cu:
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
cut.Simplify()
fill.BooleanSubtract(cut)
fill.Inflate(-FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)      # drop slivers thinner than 0.3 mm
fill.Inflate(FromMM(0.15), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
fill.BooleanSubtract(cut)
fill.Simplify()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code and pad.IsOnLayer(B_Cu):
            gnd_cu.Append(pad_poly(pad, B_Cu))
gnd_cu.Simplify()
n_gnd = 0
for i in range(fill.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(fill.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_cu)
    if area_mm2(both) > 0.01:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        print("  ground fill piece, mm2: %.0f" % area_mm2(piece))
    else:                                           # an island that touches no ground: leave it out
        print("  dropped island, mm2: %.2f" % area_mm2(piece))
assert n_gnd >= 1

# ---- back silkscreen labels (mirrored, so they read from the back) ----------------------------------
# one line between the maker's credit (ends y 145.5) and the connector's own pin-1 bar (y 149.9)
LABELS = [("SAO++ rA   BADGE POWER ONLY", CX, 147.7, 1.0), ("1", 98.6, 152.6, 1.0)]
for txt, x, y, size in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    board.Add(t)

# ---- report and save -------------------------------------------------------------------------------
print("J1 pads:", {p.GetNumber(): mm(p.GetPosition()) for p in conn.Pads()})
print("X2 pads:", [(p.GetNumber(), p.GetNetname(), mm(p.GetPosition()), "back" if p.IsOnLayer(B_Cu) else "front") for p in plug.Pads()])
print("new tracks:", len(NEW_TRACKS), "| maker's tracks and vias kept:", len(board.GetTracks()) - len(NEW_TRACKS))
ds = board.GetDesignSettings()
ds.m_SolderMaskExpansion = 0                # the maker's setting
ds.m_SolderMaskMinWidth = 0
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.2)
_nc = ds.m_NetSettings.GetDefaultNetclass()     # the maker's own spacing: his closest tracks and vias are 6 mil (0.1524 mm) apart
_nc.SetClearance(FromMM(0.15))
_nc.SetTrackWidth(FromMM(SIG))
_nc.SetViaDiameter(FromMM(0.508))
_nc.SetViaDrill(FromMM(0.3048))
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)

# ---- project file: rule settings (kicad-cli 10.0.8 can rewrite the .kicad_pro and drop these) -------------
if os.path.exists(PRO):
    pro = json.load(open(PRO))
    sev = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rule_severities", {})
    sev.update({
        "lib_footprint_issues": "warning", "lib_footprint_mismatch": "warning",
        "silk_over_copper": "warning", "silk_overlap": "warning", "silk_edge_clearance": "warning",
        "text_height": "warning", "text_thickness": "warning", "isolated_copper": "warning", "copper_sliver": "warning",
        "missing_courtyard": "ignore", "footprint_type_mismatch": "ignore",
    })
    pro["board"]["design_settings"].setdefault("rules", {}).update({
        "min_clearance": 0.15, "min_copper_edge_clearance": 0.25, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
        "min_track_width": 0.2, "min_via_diameter": 0.5, "min_via_annular_width": 0.1, "min_through_hole_diameter": 0.3,
        "solder_mask_to_copper_clearance": 0.0,
    })
    json.dump(pro, open(PRO, "w"), indent=2)
    print("re-applied rule settings to", PRO)
else:
    print("NOTE: no", PRO, "yet")
sys.stdout.flush()
os._exit(0)          # KiCad 10's Python can crash while tidying up at exit, after the board is saved
