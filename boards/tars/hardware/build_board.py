#!/usr/bin/env python3
"""Build tars.kicad_pcb from the maker's KiCad board plus the SAO++ changes.

Run with KiCad 10's Python, from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/tars/hardware/build_board.py

What it does
  - loads original/KiCad/TARS/TARS.kicad_pcb with every part, track and via cut out of the file text, so the outline,
    the front art (the gold slabs: copper zones under solder-mask openings, and the six touch areas), the front lettering,
    the maker's back-silkscreen quote, credit, logo, socket labels and speaker box all stay exactly as drawn
  - drops the back-silkscreen labels that named the old RP2040 module's pins (USB, GND, VCC, CL, DA, DC, CS, RST, ...)
  - puts back the maker's display, cue light and its resistor on the FRONT where he had them
  - puts everything else on the back: the XIAO (USB-C at the top edge), the SAO connector where his header was, the
    slide switch on the left edge, the LiPo socket on the right edge, his speaker socket and jumper, his two Qwiic
    sockets, and the new touch chip below the XIAO
  - routes with router.py: back copper everywhere, front copper and vias only under the display glass (hidden), plus a
    short landing into each touch area
  - fills the back with ground copper (0.55 mm back from the edge) and refills the maker's front zones
Coordinates are millimetres in KiCad's front view (x grows right, y grows down).
"""
import json
import math
import os
import re
import sys
import tempfile
import uuid

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
from saopp_board import ERR as ERR_, P, mm, poly, grown, pad_poly, add_filled  # noqa: E402
from saopp_symbols import SYMBOLS, load_local  # noqa: E402
import router  # noqa: E402
from router import B as RB, F as RF  # noqa: E402

SLUG = "tars"
SRC = os.path.join(HERE, "..", "original", "KiCad", "TARS", "TARS.kicad_pcb")
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
LOCAL_LIB = os.path.join(HERE, SLUG + "-local.pretty")
LOCAL = set(load_local(SLUG))
W_, H_ = 40.0, 50.0                 # the maker's board: 40 x 50 mm, 0.5 mm corner radius
SIG = 0.2
POWER = {"V3V3": 0.25, "VSAO": 0.25, "BAT+": 0.25, "GND": 0.25}
VIA_D, VIA_HOLE = 0.6, 0.3
EDGE_GND = 0.55                     # back ground copper stops this far short of the edge (panel mouse bites)

# the maker's back-silkscreen labels for the old module's pins: meaningless with the XIAO, so they go
OLD_PIN_LABELS = {"VCC", "RST", "R", "D", "GND", "?", "SDA", "L", "USB", "SCL", "CUE LIGHT", "B", "CS", "A",
                  "SAO SDA", "DA", "DC", "U", "CL", "SAO SCL"}
KEEP_FPS = ("kibuzzard-66F12846", "kibuzzard-66F128E4", "davedarko:davedarko_logo_silk_outline")


def tab_blocks(txt, opener):
    """(start, end) of each top-level '(opener ...' block in a KiCad 8 (tab-indented) file."""
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


# ---- cut the maker's parts, tracks, vias and old pin labels out of the file text ----------------------
txt = open(SRC, encoding="utf-8").read()
cut = list(tab_blocks(txt, "segment")) + list(tab_blocks(txt, "via"))
assert len(cut) == 203 + 30, len(cut)
n_fp = 0
for a, b in tab_blocks(txt, "footprint"):
    name = re.match(r'\n\t\(footprint "([^"]+)"', txt[a:b]).group(1)
    if name not in KEEP_FPS:
        cut.append((a, b))
        n_fp += 1
assert n_fp == 20, n_fp
dropped = []
for a, b in tab_blocks(txt, "gr_text"):
    t = re.match(r'\n\t\(gr_text "((?:[^"\\]|\\.)*)"', txt[a:b]).group(1)
    if t in OLD_PIN_LABELS and '(layer "B.SilkS")' in txt[a:b]:
        cut.append((a, b))
        dropped.append(t)
assert sorted(dropped) == sorted(OLD_PIN_LABELS), sorted(set(OLD_PIN_LABELS) - set(dropped))
for a, b in tab_blocks(txt, "zone"):               # the maker's back ground pour: rebuilt below, 0.55 mm from the edge
    if '(layer "B.Cu")' in txt[a:b]:
        cut.append((a, b))
for a, b in tab_blocks(txt, "gr_line"):           # the little corner mark beside the old "CL" label
    if '(layer "B.SilkS")' in txt[a:b]:
        cut.append((a, b))
for a, b in sorted(cut, reverse=True):
    txt = txt[:a] + txt[b:]
tmp = os.path.join(tempfile.mkdtemp(), "TARS.kicad_pcb")
open(tmp, "w", encoding="utf-8").write(txt)
board = pcbnew.LoadBoard(tmp)
assert board is not None
for fp in board.GetFootprints():          # the maker's logo and labels are art, not parts: no schematic, BOM or placement
    fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
print("kept from the original:", len(list(board.Zones())), "zones,", len(list(board.GetDrawings())), "drawings,",
      len(list(board.GetFootprints())), "art footprints")
body = poly([(0, 0), (W_, 0), (W_, H_), (0, H_)])

# ---- circuit and nets ------------------------------------------------------------------------------
CIRCUIT = json.load(open(os.path.join(HERE, "circuit.json")))
PARTS = {p["ref"]: p for p in CIRCUIT["parts"]}
PADNETS = {r: p.get("nets", {}) for r, p in PARTS.items()}
PINNAMES = {r: {num: name for num, name, *_ in SYMBOLS[p["symbol"]][5]} for r, p in PARTS.items()}
_NS = uuid.UUID("5a0b1b15-0000-4000-8000-00000000a011")          # same namespace as tools/gen_schematic.py


def sch_uuid(what):
    return str(uuid.uuid5(_NS, SLUG + ":" + what))


nets = {}
for n in sorted({n for d in PADNETS.values() for n in d.values()}):
    ni = board.FindNet(n)
    if ni is None:
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
    nets[n] = ni


def link(fp, ref):
    sym = PARTS[ref]["symbol"]
    _, value, fpid, fields, _, _ = SYMBOLS[sym]
    fp.SetFPID(pcbnew.LIB_ID(SLUG + "-local" if sym in LOCAL else "sao-plus-plus", fpid.split(":")[1]))
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


def load(ref, pos, back=True, rot=None):
    sym = PARTS[ref]["symbol"]
    name = SYMBOLS[sym][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LOCAL_LIB if sym in LOCAL else LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    fp.SetPosition(P(*pos))
    if back:
        fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    if rot is not None:
        fp.SetOrientationDegrees(rot)
        link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


def place(ref, pos, want, back=True):
    """Place, then pick the right-angle rotation that puts pad `want[0]` nearest `want[1]`."""
    fp = load(ref, pos, back)
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


def near(a, b, tol=0.02):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


# ---- front: the maker's display, cue light and resistor, where he had them --------------------------------------
disp = load("U1", (20.9, 22.5), back=False, rot=180)
assert near(pp(disp, "1"), (23.9, 18.3)) and near(pp(disp, "13"), (23.9, 26.7)), (pp(disp, "1"), pp(disp, "13"))
d1 = place("D1", (5.9, 17.5), ("1", (5.9, 16.625)), back=False)          # cathode up, as the maker had it
r10 = place("R10", (5.9, 21.1), ("2", (5.9, 20.275)), back=False)        # pad 2 (to the LED) up
# a 1 mm marker dot inside each touch area, in the middle of a gold slab beside the band the display hides
TPS = {"TP1": (8.75, 14.0), "TP2": (16.0, 14.0), "TP3": (31.25, 14.0), "TP4": (8.75, 31.0), "TP5": (23.0, 31.0), "TP6": (31.25, 31.0)}
for ref, xy in TPS.items():
    tp = load(ref, xy, back=False, rot=0)
    for pad in tp.Pads():
        pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)   # merge into the gold, no thermal-relief cross

# ---- back --------------------------------------------------------------------------------------------------
XC, YC = 20.0, 11.99                     # XIAO: USB-C socket face on the top edge
xiao = place("U2", (XC, YC), ("14", (XC - 8.11, YC - 7.56)))
assert abs(pp(xiao, "1")[0] - (XC + 8.055)) < 0.01, "pads 1-7 (D0-D6) should be on the right (front view)"
conn = place("J1", (20.0, 42.0), ("1", (17.46, 38.6)))                   # where the maker's header was; pin 1 top-left
SWX, SWY = 2.13, 19.0                                                    # left edge, knob out to the left
sw = place("SW1", (SWX, SWY), ("1", (SWX + 1.43, SWY + 3.0)))           # pin 1 (SAO) toward the connector
lipo = load("J5", (35.1, 24.5))                                          # right edge, plug from the right
for rot in (0, 90, 180, 270):
    lipo.SetOrientationDegrees(rot)
    sig = [mm(p.GetPosition()) for p in lipo.Pads() if p.GetNumber() in ("1", "2")]
    hold = [mm(p.GetPosition()) for p in lipo.Pads() if p.GetNumber() == ""]
    if all(x < 33 for x, _ in sig) and all(x > 36 for x, _ in hold):
        break
else:
    raise AssertionError("no rotation opens the LiPo socket to the right")
link(lipo, "J5")
# the maker's speaker socket, jumper and Qwiic sockets, where and how he placed them
spk = load("J2", (4.92, 8.1), rot=180)
assert near(pp(spk, "1"), (5.55, 5.7)) and near(pp(spk, "2"), (4.3, 5.7)), (pp(spk, "1"), pp(spk, "2"))
jp = load("JP1", (6.8, 2.7), rot=0)
assert near(pp(jp, "1"), (5.5, 2.7)) and near(pp(jp, "3"), (8.1, 2.7)), (pp(jp, "1"), pp(jp, "3"))
# (both 0.1 mm further from the right edge than his, so their mounting pads keep 0.25 mm from it)
q3 = load("J3", (36.9, 45.0), rot=-90)
assert near(pp(q3, "1"), (34.9, 43.5)) and near(pp(q3, "4"), (34.9, 46.5)), (pp(q3, "1"), pp(q3, "4"))
q4 = load("J4", (36.9, 35.0), rot=-90)
assert near(pp(q4, "1"), (34.9, 33.5)), pp(q4, "1")
# the touch chip below the XIAO, pins 1-7 on the upper row
cap = place("U3", (20.0, 26.7), ("1", (20.0 - 3.81, 26.7 - 2.475)))
v_cap = pp(cap, "7")
c2 = place("C2", (v_cap[0] + 1.9, v_cap[1] + 0.8), ("1", (v_cap[0] + 1.9, v_cap[1] + 0.8 - 0.775)))
r11 = place("R11", (13.6, 25.3), ("1", (13.6, 25.3 - 0.825)))
r12 = place("R12", (13.6, 28.3), ("1", (13.6, 28.3 - 0.825)))
r16 = place("R16", (27.6, 24.6), ("1", (27.6, 24.6 - 0.825)))
c1 = place("C1", (27.6, 27.6), ("1", (27.6, 27.6 - 0.775)))
r9 = place("R9", (29.2, 27.6), ("1", (29.2, 27.6 - 0.825)))
r13 = place("R13", (6.4, 24.0), ("1", (6.4 - 0.825, 24.0)))
r14 = place("R14", (8.0, 12.5), ("1", (8.0 + 0.825, 12.5)))      # beside D10, below the speaker socket
r15 = place("R15", (8.0, 14.0), ("1", (8.0 + 0.825, 14.0)))

FPS = list(board.GetFootprints())
_pad_ok = grown(body, -0.25)
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            lay = F_Cu if pad.IsOnLayer(F_Cu) else B_Cu
            off = pad_poly(pad, lay)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# ---- routing ---------------------------------------------------------------------------------------------
g = router.Grid(-0.2, -0.2, W_ + 0.2, H_ + 0.2)
EDGE_C = 0.5 + router.HW_MAX + 0.02                  # track centres this far in: copper stays 0.5 mm from the edge
ok = g.rect(EDGE_C, EDGE_C, W_ - EDGE_C, H_ - EDGE_C)
g.allowed[RB] &= ok
GLASS = (6.95, 15.85, 34.85, 29.15)                  # the display glass (maker's outline on Dwgs.User): hides the front
g.allowed[RF] = g.rect(GLASS[0] + 0.1, GLASS[1] + 0.1, GLASS[2] - 0.1, GLASS[3] - 0.1) | g.rect(5.0, 15.5, 7.0, 23.2)
g.noVia |= ~g.rect(GLASS[0] + 0.4, GLASS[1] + 0.4, GLASS[2] - 0.4, GLASS[3] - 0.4)
INF = router.CLR + router.HW_MAX + router.SLACK
codes = {}


def code(name):
    if name not in codes:
        codes[name] = len(codes) + 1
    return codes[name]


# the maker's back-silkscreen art and lettering: no tracks under it
ART_BACK = {"quote": (33.2, 0.3, 39.81, 18.84), "credit": (14.41, 31.48, 25.39, 35.52), "logo": (0.68, 27.49, 5.52, 33.51),
            "SAO I2C": (33.39, 30.06, 39.81, 31.34), "BADGE I2C": (31.46, 40.06, 39.74, 41.34),
            "reserved for speaker": (2.58, 39.27, 9.42, 44.53), "SPEAKER": (0.1, 0.02, 2.15, 7.18), "JLC": (27.21, 48.3, 37.6, 49.82)}
for x0, y0, x1, y1 in ART_BACK.values():
    g.allowed[RB] &= ~g.rect(x0 - 0.15, y0 - 0.15, x1 + 0.15, y1 + 0.15)
# the XIAO's own underside test pads: no carrier copper under them
for gi in xiao.GraphicalItems():
    if gi.GetLayer() == pcbnew.Dwgs_User and gi.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        g.stamp(RB, g.disc(mm(gi.GetCenter()), 0.85 + 0.2 + router.HW_MAX), -1)
# a landing strip from each touch dot into the band the glass hides, usable only by that touch net
for ref, (x, y) in TPS.items():
    net = PADNETS[ref]["1"]
    ys = (y - 0.6, GLASS[1] + 0.3) if y < 20 else (GLASS[3] - 0.3, y + 0.6)
    g.netOnly[(RF, code(net))] = g.rect(x - 0.6, ys[0], x + 0.6, ys[1])

PADS = []
for fp in FPS:
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            r = ToMM(pad.GetDrillSize().x) / 2 + 0.25 + router.HW_MAX + router.SLACK
            m = g.disc(mm(pad.GetPosition()), r)
            g.stamp(RB, m, -1)
            g.stamp(RF, m, -1)
            continue
        L = RF if pad.IsOnLayer(F_Cu) else RB
        lay = F_Cu if L == RF else B_Cu
        n = pad.GetNetname() or f"nc-{fp.GetReference()}-{pad.GetNumber()}"
        ps = pad_poly(pad, lay)
        g.stamp(L, g.poly_mask(ps, INF), code(n))
        PADS.append((fp.GetReference(), pad.GetNumber(), n, L, ps))

ORDER = ["V3V3", "TFT_SCLK", "TFT_MOSI", "TFT_DC", "SPK_B", "SPK_A", "LED_K", "OFF_SENSE", "PRIV_SDA", "PRIV_SCL", "SDA", "SCL",
         "TOUCH_A", "TOUCH_UP", "TOUCH_B", "TOUCH_LEFT", "TOUCH_DOWN", "TOUCH_RIGHT",
         "TFT_RST", "LEDA", "LED_A", "SPK_AR", "SPK_1", "OFF_SW", "BAT+", "VSAO", "GND"]
# ground is routed too (a thin tree joining every ground pad, front and back), so it stays one net even where the
# back ground copper is cut into pieces by the tracks; the copper and the stitching vias then add to it
_tcache = {}


def targets(netc):
    if netc in _tcache:
        return _tcache[netc]
    name = [k for k, v in codes.items() if v == netc][0]
    tg = []
    for ref, num, n, L, ps in PADS:
        if n != name:
            continue
        if name == "GND" and ref in ("J1", "J3", "J4"):
            continue                         # these connectors' ground pins join through the back ground copper round them
        tg.append((L, g.poly_mask(ps, 0)))
    _tcache[netc] = tg
    return tg


assert all(n in codes for n in ORDER)
names = {v: k for k, v in codes.items()}
ROUTES = os.path.join(HERE, "routes.json")
if os.path.exists(ROUTES) and not os.environ.get("TARS_REROUTE"):
    # replay the saved result of the last full routing run (TARS_REROUTE=1 routes again, a few minutes)
    saved = json.load(open(ROUTES))
    res = {code(n): ([(L, tuple(a), tuple(b)) for L, a, b in r["segs"]], [tuple(v) for v in r["vias"]]) for n, r in saved.items()}
    failed, passes = [], 0
    print("routes replayed from routes.json")
else:
    res, failed, passes = router.route_all(g, [code(n) for n in ORDER], targets,
                                           lambda c: POWER.get(names[c], SIG), lambda c: 25.0)
    if not failed:
        json.dump({names[c]: {"segs": [[L, list(a), list(b)] for L, a, b in segs], "vias": [list(v) for v in vias]}
                   for c, (segs, vias) in res.items()}, open(ROUTES, "w"), indent=0)
        print("routes saved to routes.json")
DEBUG = os.environ.get("TARS_DEBUG_PARTIAL")
if failed:
    print("ROUTE FAILED:", [names[c] for c in failed])
    if not DEBUG:
        sys.exit(1)

TRACKS, VIAS = [], []
gfinal = g.copy()
for c, (segs, vias) in res.items():
    net, w = names[c], POWER.get(names[c], SIG)
    for L, a, b in segs:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(w))
        t.SetLayer(B_Cu if L == RB else F_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((L, net))
    for xy in vias:
        VIAS.append((xy, net))
    router.commit(gfinal, c, segs, vias, w)

# ground stitching: tie the front ground under the glass to the back ground copper, where there is room
gnd_c = code("GND")
inf_v = router.VIA_R + INF
for y in np.arange(16.6, 28.6, 2.4):
    for x in np.arange(7.6, 34.4, 3.6):
        m = gfinal.disc((x, y), inf_v)
        if gfinal.noVia[m].any():
            continue
        if all(((gfinal.owner[L][m] == 0) | (gfinal.owner[L][m] == gnd_c)).all() and gfinal.allowed[L][m].all() for L in (RB, RF)):
            VIAS.append(((round(float(x), 2), round(float(y), 2)), "GND"))
            gfinal.stamp(RB, m, gnd_c)
            gfinal.stamp(RF, m, gnd_c)
for xy, net in VIAS:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*xy))
    v.SetDrill(FromMM(VIA_HOLE))
    v.SetWidth(FromMM(VIA_D))
    v.SetNet(nets[net])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED)
    board.Add(v)
import collections  # noqa: E402
print(f"routed in {passes} pass(es); vias: {len(VIAS)} ({dict(collections.Counter(n for _, n in VIAS))}); "
      f"front segments: {sum(1 for L, _ in TRACKS if L == RF)}, back segments: {sum(1 for L, _ in TRACKS if L == RB)}")

# ---- back ground copper (a zone, 0.55 mm back from the edge), kept off the XIAO's underside test pads ----------
c_ = 1.0
z = pcbnew.ZONE(board)
z.SetLayer(B_Cu)
z.SetNet(nets["GND"])
ol = z.Outline()
ol.NewOutline()
e = EDGE_GND
for x, y in [(e + c_, e), (W_ - e - c_, e), (W_ - e, e + c_), (W_ - e, H_ - e - c_), (W_ - e - c_, H_ - e), (e + c_, H_ - e),
             (e, H_ - e - c_), (e, e + c_)]:
    ol.Append(FromMM(x), FromMM(y))
z.SetLocalClearance(FromMM(0.3))
z.SetMinThickness(FromMM(0.25))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
z.SetThermalReliefGap(FromMM(0.3))
z.SetThermalReliefSpokeWidth(FromMM(0.3))
z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
z.SetZoneName("back ground")
board.Add(z)
for gi in xiao.GraphicalItems():
    if gi.GetLayer() == pcbnew.Dwgs_User and gi.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        k.SetLayer(B_Cu)
        k.SetDoNotAllowZoneFills(True)
        k.SetDoNotAllowTracks(False)
        k.SetDoNotAllowVias(False)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        cx, cy = mm(gi.GetCenter())
        ko = k.Outline()
        ko.NewOutline()
        for i in range(16):
            a = 2 * np.pi * i / 16
            ko.Append(FromMM(float(cx + 1.0 * np.cos(a))), FromMM(float(cy + 1.0 * np.sin(a))))
        board.Add(k)

# panel tabs: the mouse-bite holes reach 0.25 mm into the board, so no copper of any kind (the front art included)
# within 0.6 mm of the edge along each tab
TABS = json.load(open(os.path.join(HERE, "..", "production", "panel.json")))["tabs"]
for t_ in TABS:
    (x, y), d = t_["near"], t_["dir"]
    hw, dp = 1.8, 0.6
    if d in ("-y", "+y"):
        y0 = 0.0 if d == "-y" else H_ - dp
        r = (x - hw, y0, x + hw, y0 + dp)
    else:
        x0 = 0.0 if d == "-x" else W_ - dp
        r = (x0, y - hw, x0 + dp, y + hw)
    for lay in (F_Cu, B_Cu):
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        k.SetLayer(lay)
        k.SetDoNotAllowZoneFills(True)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(True)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        ko = k.Outline()
        ko.NewOutline()
        for px, py in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])):
            ko.Append(FromMM(px), FromMM(py))
        board.Add(k)

# ---- back silkscreen labels --------------------------------------------------------------------------------
s1, s4 = pp(sw, "1"), pp(sw, "4")
lp1, lp2 = pp(lipo, "1"), pp(lipo, "2")
j1p = pp(conn, "1")
LABELS = [("TARS rA", 31.0, 36.6, 0.8), ("SAO++", 31.0, 37.8, 0.8), ("NO USB", 31.0, 43.6, 0.8), ("ON SAO", 31.0, 44.8, 0.8),
          ("SAO", 5.8, s1[1], 0.8), ("USB", 5.8, s4[1], 0.8),
          ("+", lp1[0] - 2.4, lp1[1], 0.9), ("-", lp2[0] - 2.4, lp2[1], 0.9), ("LiPo", 35.0, 29.2, 0.8),
          ("1", j1p[0] - 1.3, j1p[1] - 2.9, 0.8)]
for t_, x, y, size in LABELS:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(t_)
    t.SetLayer(B_SilkS)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    board.Add(t)

# ---- rules, fill, save ----------------------------------------------------------------------------------------
ds = board.GetDesignSettings()
ds.m_CopperEdgeClearance = FromMM(0.25)
ds.m_MinClearance = FromMM(0.15)
ds.m_HoleClearance = FromMM(0.25)
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_ViasMinSize = FromMM(0.5)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_NetSettings.GetDefaultNetclass().SetClearance(FromMM(0.15))
board.GetTitleBlock().SetTitle(CIRCUIT["title"])
board.GetTitleBlock().SetRevision(CIRCUIT["rev"])
board.GetTitleBlock().SetComment(0, CIRCUIT["credit"])
board.BuildConnectivity()                 # the filler needs it to drop ground islands that touch nothing
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
if failed:
    OUT = os.path.join(HERE, "_partial.kicad_pcb")      # a look at what did route; not the board
    pcbnew.SaveBoard(OUT, board)
    print("saved", OUT)
    sys.exit(1)

# ---- freeze the zones into plain filled shapes, and the outline into one polygon -----------------------------
# tools/panelize.py copies footprints, drawings and tracks to the other boards of the panel, not zones, and reads the
# outline as one closed polygon. So every filled zone (the maker's front art and touch areas, the ground copper, the
# solder-mask openings) becomes board-level filled polygons with the same net, as on the other SAO++ boards.
FILLED = []
for z in board.Zones():
    if z.GetIsRuleArea():
        continue
    for lay in z.GetLayerSet().Seq():
        fp_ = z.GetFilledPolysList(lay)
        if fp_.OutlineCount():
            # kept as plain point lists (holes fractured in): the zone's own polygon data does not outlive its board
            ps_ = pcbnew.SHAPE_POLY_SET(fp_)
            ps_.Fracture()
            for i in range(ps_.OutlineCount()):
                ch = ps_.Outline(i)
                FILLED.append((lay, z.GetNetname(), [(ch.CPoint(k).x, ch.CPoint(k).y) for k in range(ch.PointCount())]))
for d in board.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetLayer() == F_Cu:
        assert d.GetText() in ("TARS", "T A R S"), d.GetText()
tmp2 = os.path.join(tempfile.mkdtemp(), "stage.kicad_pcb")
pcbnew.SaveBoard(tmp2, board)
txt = open(tmp2, encoding="utf-8").read()
cut = list(tab_blocks(txt, "zone"))
cut += [(a, b) for opener in ("gr_line", "gr_arc") for a, b in tab_blocks(txt, opener) if '(layer "Edge.Cuts")' in txt[a:b]]
cut += [(a, b) for a, b in tab_blocks(txt, "gr_text") if '(layer "F.Cu"' in txt[a:b]]
assert len([1 for a, b in tab_blocks(txt, "gr_text") if '(layer "F.Cu"' in txt[a:b]]) == 2
for a, b in sorted(cut, reverse=True):
    txt = txt[:a] + txt[b:]
open(tmp2, "w", encoding="utf-8").write(txt)
board = pcbnew.LoadBoard(tmp2)
TP_AT = {PADNETS[r]["1"]: xy for r, xy in TPS.items()}
n_island = 0
for lay, net, pts_ in FILLED:
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts_:
        ps.Append(x, y)
    for i in range(ps.OutlineCount()):
        piece = pcbnew.SHAPE_POLY_SET(ps.Polygon(i))
        n_ = net
        if net in TP_AT and not piece.Contains(P(*TP_AT[net])):
            n_ = None                    # a scrap of a touch area cut off by the lettering: art only, as on the maker's board
            n_island += 1
        add_filled(board, piece, lay, board.FindNet(n_) if n_ else None)
# The maker's two "TARS" words are knockout text on the front copper inside the "down" touch area; his zone was filled
# round them, so the letters are the holes in that fill (which is what shows: dark letters in the gold). The frozen
# fill keeps those holes exactly; the text items themselves are left out (cut above), as they would only duplicate them.
print("touch-area scraps cut off by the lettering (kept as plain art copper):", n_island)
R_ = 0.5                                                  # the maker's 0.5 mm corner radius, as 8 steps per corner
pts = []
for cx, cy, a0 in ((W_ - R_, R_, -90), (W_ - R_, H_ - R_, 0), (R_, H_ - R_, 90), (R_, R_, 180)):
    for k in range(9):
        a = math.radians(a0 + k * 90 / 8)
        pts.append((cx + R_ * math.cos(a), cy + R_ * math.sin(a)))
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(poly(pts))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
print("froze the zone fills into", len(FILLED), "filled shapes")
pcbnew.SaveBoard(OUT, board)
print("saved", OUT)
