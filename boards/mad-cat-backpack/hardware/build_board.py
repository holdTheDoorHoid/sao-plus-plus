#!/usr/bin/env python3
"""Build mad-cat-backpack.kicad_pcb from scratch.

Run with KiCad 10's Python, from the repo root (after `python3 tools/gen_schematic.py mad-cat-backpack`):
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/mad-cat-backpack/hardware/build_board.py

What the board is
  The 2018 Mad Cat Backpack (Peter Shabino / Wireb, MIT) is a small board soldered flat against the BACK of a Mad Cat
  SAO. It carries the eight LEDs (they light the Mad Cat's eyes and teeth from behind) and a chip that animates them.
  This SAO++ version keeps that idea and replaces the PIC with a Seeed XIAO ESP32 (docs/standard.md section 3a).

  It is made for the SAO++ Mad Cat (boards/mad-cat) built as a BARE board (none of its parts fitted). Both boards use the
  same coordinates (KiCad front view, mm), so each LED here sits exactly behind the spot the Mad Cat lights, and this
  board's SAO connector sits exactly where the Mad Cat's own connector would be: the stack hangs from the badge the same
  way a plain Mad Cat does.

  "Front" of this board = the side pressed against the Mad Cat's back. It is never seen, so (unlike the art boards) it
  carries a ground plane, a few short tracks and tented vias. "Back" = the side facing the badge: every part sits there.

  - LEDs: the shared reverse-mount white LED (it shines INTO the board), each over a 1.0 mm round cut-out, so its light
    goes through this board and into the Mad Cat board in front of it at the same spot as the Mad Cat's own LED.
  - Eight bond holes (plated 0.7 mm holes with bare 1.5 mm rings on both sides, on the ground net) sit over eight bare
    pads of the Mad Cat (its unused LED pads at the eyes and at teeth 2 and 3): solder fed into each hole from the back
    joins the two boards, as the 2018 build soldered four pads.
  - The outline is the Mad Cat's own outline, 0.35 mm smaller all round, cut to the face, the haunch (for the XIAO) and
    the root of the tail (for the LiPo socket). Nothing of this board shows past the Mad Cat from the front.
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, F_Cu, B_SilkS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "mad-cat-backpack"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
MADCAT_OUTLINE = os.path.join(ROOT, "boards", "mad-cat", "hardware", "outline.json")
ORIGINAL = os.path.join(HERE, "..", "original", "kicad", "Mad_Cat_backpack.kicad_pcb")

MARGIN = 0.35       # this board's edge sits this far inside the Mad Cat's edge
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # ground copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
SIG_FINE = 0.15     # the two lanes squeezed between the XIAO's C3/S3 battery pads and its bottom pad row
PWR = 0.30          # 3.3 V rail
VIA_D, VIA_HOLE = 0.6, 0.3
BOND_D, BOND_HOLE = 1.5, 0.7      # bond holes: as KiCad's stock TestPoint_THTPad_D1.5mm_Drill0.7mm
LIGHT_R = 0.5                       # light hole radius

# ---- the Mad Cat (same coordinates) -----------------------------------------------------------------
# LED centres of boards/mad-cat (its build_board.py LEDS): eyes D1 D2, teeth D3..D8 left to right
LED_C = {"D1": (128.905, 109.284), "D2": (148.082, 109.474),
         "D3": (123.952, 119.317), "D4": (128.969, 124.142), "D5": (135.636, 125.730),
         "D6": (142.177, 125.476), "D7": (148.399, 124.333), "D8": (153.352, 119.444)}
MC_PAD_DX = 1.55    # the Mad Cat's LED pads sit 1.55 mm either side of each centre, side by side (left/right)
BONDS = ("D1", "D2", "D4", "D5")   # under these LEDs the Mad Cat's two (unused) LED pads get a bond hole each

# ---- placement ---------------------------------------------------------------------------------------
CONN = (147.0, 132.8)               # exactly where the Mad Cat's own SAO connector is
SW = (132.6, 135.4)                 # paws, left of the connector; knob out of the bottom edge
SW_EDGE_Y = 137.5                   # straight bottom edge under the switch (the knob ends ~0.75 mm past it)
XIAO_END = 181.0                    # the module's USB end is flush with this edge (the USB-C socket overhangs 1.5 mm)
XIAO_C = (XIAO_END - 10.48, 121.25)
JST = (175.0, 106.5)                # LiPo socket at the root of the tail, plug goes in from the right (behind the tail)
REGION_TOP_FACE = 103.2             # top of the board over the face (above the eye resistors)
REGION_TOP_TAIL = 100.8             # top of the board at the root of the tail (the LiPo socket)


def rect(x0, y0, x1, y1):
    return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def union(parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in parts:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


# ---- outline ---------------------------------------------------------------------------------------
_mc = poly(json.load(open(MADCAT_OUTLINE))["outer"])
region = union([rect(118.0, REGION_TOP_FACE, 162.0, 141.0), rect(155.0, REGION_TOP_TAIL, XIAO_END, 141.0)])
region.BooleanSubtract(rect(124.0, SW_EDGE_Y, 139.2, 142.0))     # straight edge for the switch knob
body = grown(_mc, -MARGIN)
body.BooleanIntersection(region)
body.Simplify()
assert body.OutlineCount() == 1 and body.HoleCount(0) == 0, (body.OutlineCount(),)
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, x {bx0:.2f}..{bx1:.2f}, y {by0:.2f}..{by1:.2f}, "
      f"{body.Outline(0).PointCount()} outline points")

board = pcbnew.CreateEmptyBoard()
e = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
e.SetPolyShape(pcbnew.SHAPE_POLY_SET(body))
e.SetLayer(pcbnew.Edge_Cuts)
e.SetFilled(False)
e.SetWidth(FromMM(0.1))
board.Add(e)
inner = grown(body, -EDGE)
for _c in LED_C.values():                      # light holes: round cut-outs in the outline (a drill would do the same job)
    _h = pcbnew.SHAPE_POLY_SET()
    add_circle(_h, P(*_c), LIGHT_R, 48)
    hs = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    hs.SetPolyShape(_h)
    hs.SetLayer(pcbnew.Edge_Cuts)
    hs.SetFilled(False)
    hs.SetWidth(FromMM(0.1))
    board.Add(hs)
    inner.BooleanSubtract(grown(_h, CLEAR))

# ---- the circuit (shared with the schematic generator) ----------------------------------------------
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


# ---- parts ------------------------------------------------------------------------------------------
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)))      # VCC top-left in front view, key slot up (as the Mad Cat)
sw = place("SW1", SW, ("1", (SW[0] + 3.0, SW[1] - 1.43)))             # knob out of the bottom edge, pin 1 toward the connector
xiao = place("U1", XIAO_C, ("14", (XIAO_C[0] + 7.56, XIAO_C[1] - 8.11)))   # USB end right, 5V pad top row at the USB end
jst = place("J2", JST, ("1", (JST[0] - 2.85, JST[1] - 1.0)))          # plug from the right; pin 1 (BAT+) on top

# LEDs: anode toward the outside of the face (up for the eyes, down for the teeth; D7 to the right, beside the connector).
# The resistor sits on the anode side, between the anode and the 3.3 V rail; the cathode faces the middle of the face,
# where the XIAO's tracks come in.
ANODE = {"D1": (0, -1), "D2": (0, -1), "D3": (0, 1), "D4": (0, 1), "D5": (0, 1), "D6": (0, 1), "D7": (1, 0), "D8": (0, 1)}
R_GAP = 0.55                        # pad-to-pad gap between an LED's anode pad and its resistor (courtyards just clear)
led, res = {}, {}
for ref, (x, y) in LED_C.items():
    n = ref[1:]
    ax, ay = ANODE[ref]
    led[ref] = place(ref, (x, y), ("2", (x + ax * 1.55, y + ay * 1.55)))
    if ref == "D7":                 # resistor stands upright to the right of the anode (no room below: connector pads)
        rc = (x + 1.55 + 0.475 + 0.6 + 0.475, y)
        res["R" + n] = place("R" + n, rc, ("1", (rc[0], rc[1] - 0.825)))
    elif ref == "D6":               # resistor lies to the left of the anode: below it is the connector's plastic body
        rc = (x - 2.98, y + 1.55)
        res["R" + n] = place("R" + n, rc, ("1", (rc[0] + 0.825, rc[1])))
    else:
        d = 1.55 + 0.475 + R_GAP + 0.4 + 0.825          # LED centre -> resistor centre along the anode direction
        rc = (x + ax * d, y + ay * d)
        res["R" + n] = place("R" + n, rc, ("1", (rc[0] - ax * 0.825, rc[1] - ay * 0.825)))

NEW = set(PARTS)
_pad_ok = grown(body, -0.25)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            assert off.OutlineCount() == 0, f"{fp.GetReference()} pad {pad.GetNumber()} is closer than 0.25 mm to the board edge"

# ---- tracks and vias --------------------------------------------------------------------------------
TRACKS = []                         # (track, clearance cut into copper, net)
VIAS = []


def route(net, pts, width=SIG, layer=B_Cu, clear=CLEAR):
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
        TRACKS.append((t, clear, net))


def via(c, net, d=VIA_D, hole=VIA_HOLE, tented=True):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*c))
    v.SetDrill(FromMM(hole))
    v.SetWidth(FromMM(d))
    v.SetNet(nets[net])
    for fn in ("SetFrontTentingMode", "SetBackTentingMode"):
        if hasattr(v, fn):
            getattr(v, fn)(pcbnew.TENTING_MODE_TENTED if tented else pcbnew.TENTING_MODE_NOT_TENTED)
    board.Add(v)
    VIAS.append((c, net, v))
    return c


# bond holes: over the Mad Cat's two (unused) LED pads at each LED listed in BONDS. Bare rings both sides, ground net
# (on a bare Mad Cat those pads are dead copper; tying them to ground is harmless and makes each hole a ground stitch too)
BOND_AT = [(LED_C[r][0] + s * MC_PAD_DX, LED_C[r][1]) for r in BONDS for s in (-1, 1)]
for c in BOND_AT:
    via(c, "GND", BOND_D, BOND_HOLE, tented=False)


u = {str(k): pp(xiao, str(k)) for k in range(1, 15)}
ROW_T, ROW_B = u["8"][1], u["7"][1]            # y of the top (pads 8..14) and bottom (pads 1..7) pad rows
assert ROW_T < XIAO_C[1] < ROW_B and u["1"][0] > u["7"][0] and u["14"][0] > u["8"][0]
IN_T, IN_B = ROW_T + 1.375, ROW_B - 1.375      # inner ends of the pads
bat15_c6 = pp(xiao, "15", pick=lambda p: p[0])     # left one = C6 position
bat15_c3 = pp(xiao, "15", pick=lambda p: -p[0])
bat16_c6 = pp(xiao, "16", pick=lambda p: p[0])
bat16_c3 = pp(xiao, "16", pick=lambda p: -p[0])
print("XIAO rows", ROW_T, ROW_B, "BAT15", bat15_c6, bat15_c3, "BAT16", bat16_c6, bat16_c3)
C3_BAT_BOTTOM = bat15_c3[1] + 1.25             # the C3/S3 battery pads are 2.5 mm tall here
C3_BAT_TOP = bat15_c3[1] - 1.25
C6_BAT15_BOTTOM = bat15_c6[1] + 0.55

# the corridor: eight LED tracks enter the face from the right, between the right eye and the right outer tooth.
# Order top -> bottom = the order of their LEDs going round the face anticlockwise from the right eye.
LANE0, LANE_P = 113.39, 0.5
LANES = {"LED2_K": 0, "LED1_K": 1, "LED3_K": 2, "LED4_K": 3, "LED5_K": 4, "LED6_K": 5, "LED7_K": 6, "LED8_K": 7}
LY = {k: LANE0 + i * LANE_P for k, i in LANES.items()}
cat = {r: pp(led[r], "1") for r in LED_C}      # cathode pads

# -- top pad row (pads 8..11): pad 8 runs straight left; 9..11 drop into the strip under the module, then left
x_rise = {"9": 160.95, "10": 160.45, "11": 159.95}
strip = {"9": IN_T + 0.55, "10": IN_T + 1.05, "11": IN_T + 1.55}
route("LED2_K", [u["8"], (u["8"][0] - 1.5, LY["LED2_K"])])
for pin, netn in (("9", "LED1_K"), ("10", "LED3_K"), ("11", "LED4_K")):
    route(netn, [u[pin], (u[pin][0], strip[pin]), (x_rise[pin], strip[pin]), (x_rise[pin] - 0.5, LY[netn])])
# -- bottom pad row (pads 1, 3, 4, 7): into the module strip (1 above the C3/S3 battery pads, 3 and 4 below them),
#    out of the module's left end, then up the bridge between face and haunch
L1_Y = C3_BAT_TOP - 0.25 - SIG / 2 - 0.12     # between the module's underside test pads and the battery pads
L3_Y = C3_BAT_BOTTOM + 0.23 + SIG_FINE / 2
L4_Y = L3_Y + SIG_FINE + 0.23
assert L4_Y + SIG_FINE / 2 + 0.2 <= IN_B, (L4_Y, IN_B)
x_climb = {"LED5_K": 157.6, "LED6_K": 157.1, "LED7_K": 156.6, "LED8_K": 156.1}
route("LED5_K", [u["1"], (u["1"][0], L1_Y), (x_climb["LED5_K"] + 0.4, L1_Y), (x_climb["LED5_K"], L1_Y - 0.4),
                 (x_climb["LED5_K"], LY["LED5_K"] + 0.4), (x_climb["LED5_K"] - 0.4, LY["LED5_K"])], SIG)
route("LED6_K", [u["3"], (u["3"][0], L3_Y), (x_climb["LED6_K"] + 0.4, L3_Y), (x_climb["LED6_K"], L3_Y - 0.4),
                 (x_climb["LED6_K"], LY["LED6_K"] + 0.4), (x_climb["LED6_K"] - 0.4, LY["LED6_K"])], SIG_FINE)
route("LED7_K", [u["4"], (u["4"][0], L4_Y), (x_climb["LED7_K"] + 0.4, L4_Y), (x_climb["LED7_K"], L4_Y - 0.4),
                 (x_climb["LED7_K"], LY["LED7_K"] + 0.4), (x_climb["LED7_K"] - 0.4, LY["LED7_K"])], SIG_FINE)
route("LED8_K", [u["7"], (x_climb["LED8_K"] + 0.4, u["7"][1]), (x_climb["LED8_K"], u["7"][1] - 0.4),
                 (x_climb["LED8_K"], LY["LED8_K"] + 0.4), (x_climb["LED8_K"] - 0.4, LY["LED8_K"])])

# -- across the face: each lane runs left at its height and turns to its LED's cathode
XS = 155.3                                     # where every lane is at its corridor height
for netn in ("LED1_K", "LED3_K", "LED4_K"):
    route(netn, [(x_rise[{"LED1_K": "9", "LED3_K": "10", "LED4_K": "11"}[netn]] - 0.5, LY[netn]), (XS, LY[netn])])
route("LED2_K", [(u["8"][0] - 1.5, LY["LED2_K"]), (XS, LY["LED2_K"])])
for netn in ("LED5_K", "LED6_K", "LED7_K", "LED8_K"):
    route(netn, [(x_climb[netn] - 0.4, LY[netn]), (XS, LY[netn])], SIG if netn in ("LED5_K", "LED8_K") else SIG_FINE)
for r in LED_C:
    netn = f"LED{r[1:]}_K"
    cx, cy = cat[r]
    if r == "D7":                              # cathode pad on the left of D7: come down beside it
        route(netn, [(XS, LY[netn]), (cx, LY[netn]), (cx, cy)])
    else:
        route(netn, [(XS, LY[netn]), (cx, LY[netn]), (cx, cy)])

# ---- 3.3 V rail -------------------------------------------------------------------------------------
# Left group: over the eyes, down the left cheek, under the teeth to tooth 4; the switch common taps in under tooth 2.
# Right group (teeth 5 and 6) is fed separately; the two groups and the XIAO's 3V3 pad are joined on the front copper.
rr = {r: pp(fp, "2") for r, fp in res.items()}  # rail end of every resistor
RAIL_TOP, RAIL_LEFT = 104.0, 120.6
s1, s2, s3 = pp(sw, "1"), pp(sw, "2"), pp(sw, "3")
route("V3V3", [rr["R2"], (rr["R2"][0], RAIL_TOP), (RAIL_LEFT, RAIL_TOP), (RAIL_LEFT, 124.8), (rr["R3"][0] + 1.6, 124.8),
               (rr["R4"][0] - 1.4, rr["R4"][1] + 0.9), (rr["R4"][0] + 1.0, rr["R4"][1] + 0.9),
               (rr["R5"][0] - 1.6, rr["R5"][1] + 0.9), (rr["R6"][0], rr["R5"][1] + 0.9), rr["R6"]], PWR)   # R6 lies left of D6
route("V3V3", [rr["R1"], (rr["R1"][0], RAIL_TOP)], PWR)
route("V3V3", [rr["R3"], (rr["R3"][0], 124.8)], PWR)
route("V3V3", [rr["R4"], (rr["R4"][0], rr["R4"][1] + 0.9)], PWR)
route("V3V3", [rr["R5"], (rr["R5"][0], rr["R5"][1] + 0.9)], PWR)
_ry = rr["R4"][1] + 0.9 + (s3[0] - rr["R4"][0] - 1.0) * ((rr["R5"][1] - rr["R4"][1]) / (rr["R5"][0] - 1.6 - rr["R4"][0] - 1.0))
route("V3V3", [s3, (s3[0], _ry)], PWR)                         # switch common up to the rail
VB = via((rr["R6"][0], rr["R5"][1] + 0.9), "V3V3")              # left group joins the front copper here, under R6
# right group
VA = via((152.55, 126.05), "V3V3")
route("V3V3", [VA, (rr["R7"][0], VA[1]), rr["R7"]], PWR)
route("V3V3", [VA, (rr["R8"][0], VA[1] - 0.8), rr["R8"]], PWR)
# anode -> resistor links
for r in LED_C:
    n = r[1:]
    a = pp(led[r], "2")
    b = pp(res["R" + n], "1")
    if r in ("D7", "D6"):
        route(f"LED{n}_A", [a, (a[0] + (0.6 if r == "D7" else -0.3), b[1]), b], PWR)
    else:
        route(f"LED{n}_A", [a, b], PWR)
# XIAO 3V3 pad -> via just inside it -> front copper to the two groups
V3 = via((u["12"][0], IN_T + 0.55), "V3V3")
route("V3V3", [u["12"], V3], PWR)
route("V3V3", [V3, (V3[0], 128.6), (156.0, 128.6), VA], PWR, F_Cu)       # front: down past the battery vias, then left
route("V3V3", [VA, (150.4, 128.2), (141.0, 128.2), VB], PWR, F_Cu)

# ---- badge power and the switch ----------------------------------------------------------------------
j = {n: pp(conn, n) for n in "123456"}
VSAO_Y = j["1"][1] + 2.6
route("VSAO", [j["1"], (j["1"][0], VSAO_Y), (s1[0], VSAO_Y), s1], 0.4)

# OFF sense: switch pin 2 -> under the switch body (as Hack-Man) -> up into the gap between the connector's pad rows ->
# right, under the connector -> under the XIAO's bottom pad row -> D1
GAP_SDA, GAP_SNS = j["1"][1] + 2.85, j["1"][1] + 3.45
sns = [s2, (s2[0], SW[1] + 1.25), (SW[0] + 3.6, SW[1] + 1.25), (SW[0] + 4.3, SW[1] + 0.33), (SW[0] + 6.3, SW[1] + 0.33),
       (139.6, GAP_SNS + 0.7), (140.3, GAP_SNS)]
# SDA: connector pin 3 -> down into the gap -> right (above the sense track) -> under the XIAO -> D4
LOW_SDA, LOW_SNS = ROW_B + 2.7, ROW_B + 3.35   # under the module's bottom pad row, left part (the board edge drops away to the left)
HIGH_SNS = ROW_B + 2.05                         # under the right part, where the edge comes up
route("SDA", [j["3"], (j["3"][0], GAP_SDA), (154.2, GAP_SDA), (156.0, LOW_SDA), (u["5"][0], LOW_SDA), u["5"]])
route("OFF_SENSE", sns + [(153.6, GAP_SNS), (155.6, LOW_SNS), (u["5"][0] + 0.9, LOW_SNS), (u["5"][0] + 1.9, HIGH_SNS),
                          (u["2"][0], HIGH_SNS), u["2"]])
# SCL: connector pin 4 -> via in the gap -> front copper -> via under the XIAO's SCL pad
VS1 = via((j["4"][0] + 1.1, j["4"][1] - 2.6), "SCL")
route("SCL", [j["4"], (j["4"][0], VS1[1] + 0.4), (VS1[0] - 0.4, VS1[1] + 0.4), VS1])
VS2 = via((u["6"][0], ROW_B + 1.95), "SCL")
route("SCL", [u["6"], VS2])
route("SCL", [VS1, (150.8, VS1[1]), (154.0, 135.2), (VS2[0] - 3.0, 135.2), VS2], SIG, F_Cu)

# ---- LiPo -------------------------------------------------------------------------------------------
jp1, jp2 = pp(jst, "1"), pp(jst, "2")
VB1 = via((jp1[0] - 2.4, jp1[1]), "BAT+")
route("BAT+", [jp1, VB1], PWR)
VB2 = via((bat15_c6[0] - 2.1, bat15_c6[1]), "BAT+")
route("BAT+", [VB2, bat15_c6], PWR)
VB3 = via((bat15_c3[0] - 1.45, bat15_c3[1]), "BAT+")
route("BAT+", [VB3, bat15_c3], PWR)
route("BAT+", [VB1, (VB1[0], 112.4), (VB2[0] + 0.2, 117.6), VB2], PWR, F_Cu)
route("BAT+", [VB2, (VB3[0] - 1.0, VB2[1]), VB3], PWR, F_Cu)

# ---- ground: front plane + back copper, joined by vias --------------------------------------------
VG = [via((bat16_c3[0] + 1.45, bat16_c3[1]), "GND"),            # C3/S3 battery minus (boxed in under the module)
      via((j["2"][0] - 1.6, j["2"][1] + 0.3), "GND"),           # beside the connector's GND pin
      via((u["11"][0] + 0.6, ROW_T - 2.2), "GND")]              # top: the XIAO's GND pad and the LiPo socket's minus
route("GND", [VG[0], bat16_c3], PWR)

gnd_code = nets["GND"].GetNetCode()


def keepout(layer):
    """Everything that is not GND on one copper layer, grown by the clearance."""
    cut = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                add_circle(cut, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + CLEAR + 0.02)
            elif pad.GetNetCode() != gnd_code and pad.IsOnLayer(layer):
                pad.TransformShapeToPolygon(cut, layer, FromMM(CLEAR), ERR, pcbnew.ERROR_OUTSIDE)
    for t, clear, net in TRACKS:
        if net != "GND" and t.GetLayer() == layer:
            t.TransformShapeToPolygon(cut, layer, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
    for c, net, v in VIAS:
        if net != "GND":
            add_circle(cut, P(*c), ToMM(v.GetWidth(F_Cu)) / 2 + CLEAR)
    cut.Simplify()
    return cut


def gnd_touch(layer):
    ps = pcbnew.SHAPE_POLY_SET()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd_code and pad.IsOnLayer(layer):
                ps.Append(pad_poly(pad, layer))
    for t, clear, net in TRACKS:
        if net == "GND" and t.GetLayer() == layer:
            t.TransformShapeToPolygon(ps, layer, 0, ERR, pcbnew.ERROR_OUTSIDE)
    for c, net, v in VIAS:
        if net == "GND":
            add_circle(ps, P(*c), ToMM(v.GetWidth(F_Cu)) / 2)
    ps.Simplify()
    return ps


# back
back = pcbnew.SHAPE_POLY_SET(inner)
cut = keepout(B_Cu)
n_keep = 0
for g in xiao.GraphicalItems():                # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut, g.GetCenter(), 0.85 + 0.15)
        n_keep += 1
assert n_keep == 8, n_keep
LOGO_BOX = None                                # filled in below (the maker's Metroid icon is copper art)
back.BooleanSubtract(cut)
back.Simplify()

# front: one plane
front = pcbnew.SHAPE_POLY_SET(inner)
front.BooleanSubtract(keepout(F_Cu))
front.Simplify()

# ---- the maker's art: credit lettering and Metroid icon (back) ----------------------------------------
orig = pcbnew.LoadBoard(ORIGINAL)
credit = [d for d in orig.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT) and "Backpack" in d.GetText() and d.GetLayer() == B_SilkS]
assert len(credit) == 1, len(credit)
c0 = credit[0]
CREDIT_AT = (138.4, 119.9)                     # middle of the face, between the lanes and the teeth (the 2018 spot is under the connector now)
t = pcbnew.PCB_TEXT(board)
t.SetText(c0.GetText())
t.SetLayer(B_SilkS)
t.SetTextSize(c0.GetTextSize())
t.SetTextThickness(c0.GetTextThickness())
t.SetMirrored(True)
t.SetTextAngleDegrees(0)
t.SetPosition(P(*CREDIT_AT))
board.Add(t)
print("credit text size (w, h) mm:", ToMM(c0.GetTextSize().x), ToMM(c0.GetTextSize().y), "thickness", ToMM(c0.GetTextThickness()),
      "2018 angle", c0.GetTextAngleDegrees())

icon = [fp for fp in orig.GetFootprints() if fp.GetValue() == "Metroid"]
assert len(icon) == 1
ICON_FROM = mm(icon[0].GetPosition())
ICON_AT = (166.4, 108.9)                       # root of the tail, left of the LiPo socket (the 2018 spot is under the connector now)
dx, dy = ICON_AT[0] - ICON_FROM[0], ICON_AT[1] - ICON_FROM[1]
icon_cu = pcbnew.SHAPE_POLY_SET()
n_icon = 0
for g in icon[0].GraphicalItems():
    if not isinstance(g, pcbnew.PCB_SHAPE) or g.GetLayer() not in (B_Cu, B_SilkS):
        continue
    s = pcbnew.PCB_SHAPE(board, g.GetShape())
    s.SetLayer(g.GetLayer())
    s.SetWidth(g.GetWidth())
    if g.GetShape() == pcbnew.SHAPE_T_ARC:
        s.SetArcGeometry(g.GetStart() + P(dx, dy), g.GetArcMid() + P(dx, dy), g.GetEnd() + P(dx, dy))
    else:
        s.SetStart(g.GetStart() + P(dx, dy))
        s.SetEnd(g.GetEnd() + P(dx, dy))
    board.Add(s)
    n_icon += 1
    if g.GetLayer() == B_Cu:
        s.TransformShapeToPolygon(icon_cu, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
icon_cu.Simplify()
print("Metroid icon items copied:", n_icon, "copper bbox", [round(v, 2) for v in bbox_mm(icon_cu)])
back.BooleanSubtract(grown(icon_cu, CLEAR))
back.Simplify()
OPEN = 0.12                                    # drop copper necks thinner than 0.24 mm (slivers between close tracks)
back = grown(grown(back, -OPEN), OPEN)
front = grown(grown(front, -OPEN), OPEN)

# back copper: keep only the pieces that touch a ground pad, via or track
touch_b = gnd_touch(B_Cu)
n_gnd = n_drop = 0
for i in range(back.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(back.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(touch_b)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
    else:
        n_drop += 1
print("back copper: GND pieces", n_gnd, "unconnected pieces left out", n_drop)
touch_f = gnd_touch(F_Cu)
n_f = 0
for i in range(front.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(front.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(touch_f)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, F_Cu, nets["GND"])
        n_f += 1
    else:
        print("  front piece with no ground via, left out, mm2:", round(area_mm2(piece), 2), [round(v, 1) for v in bbox_mm(piece)])
print("front plane pieces:", n_f)

# ---- back silkscreen ---------------------------------------------------------------------------------
LABELS = [("SAO", s1[0] + 0.9, SW[1] - 3.0, 0.8, 0), ("OFF", SW[0], SW[1] - 3.0, 0.8, 0), ("USB/BAT", s3[0] - 3.4, SW[1] - 3.0, 0.8, 0),
          ("1", CONN[0] - 8.7, j["1"][1], 0.9, 0),
          ("+", 168.9, 104.4, 1.2, 0), ("-", 168.9, 108.0, 1.2, 0),
          ("LiPo", 167.9, 106.2, 0.8, 0),
          ("SAO++ rA", 161.2, 134.6, 0.8, 0),
          ("USB: NOT ON 'SAO'", 138.5, 111.3, 0.8, 0)]
for txt, x, y, size, rot in LABELS:
    tt = pcbnew.PCB_TEXT(board)
    tt.SetText(txt)
    tt.SetLayer(B_SilkS)
    tt.SetPosition(P(x, y))
    tt.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    tt.SetTextThickness(FromMM(size * 0.15))
    tt.SetMirrored(True)
    tt.SetTextAngleDegrees(rot)
    board.Add(tt)

# ---- report ---------------------------------------------------------------------------------------------
print("J1 pads:", {n: j[n] for n in "123456"})
print("SW1 pads:", {"1": s1, "2": s2, "3": s3})
print("U1 pads:", u)
print("J2 pads:", jp1, jp2)
print("vias:", [(c, n) for c, n, _ in VIAS])
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

