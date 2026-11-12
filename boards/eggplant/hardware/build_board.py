#!/usr/bin/env python3
"""Build eggplant.kicad_pcb from scratch: the maker's art (art/art.json), the parts and the routing.

Run with KiCad 10's Python, from the repo root:
  python3 boards/eggplant/hardware/extract_art.py        (only when original/eggplant.brd changes)
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad boards/eggplant/hardware/build_board.py

The maker's board is an Eagle file, which KiCad 10's Python will not load here, so extract_art.py reads the XML
and this script draws everything new:
  front  - the maker's art, 1.3 times the maker's size: body copper under mask, bare-metal stalk and leaves
           (the "calyx"), two silkscreen marks, and the copper-free stripe down one side that lets light through
  back   - XIAO module, SAO connector, power switch, LiPo connector, five side-firing RGB LEDs near the edge,
           routed on the back copper only (no vias: nothing but the switch's two peg holes shows on the art side)

Two sets of coordinates are used, both millimetres in KiCad's front view (x right, y down):
  world  - the board as worn: the old header's "up" is up, so the eggplant hangs tilted like the maker's did
  A      - the eggplant standing upright as the maker drew it in Eagle (stalk up), top-left of its box at (0, 0).
           Most parts line up with the eggplant, so they are thought out in A and turned 45 degrees by A().
"""
import json
import math
import os
import sys
import uuid

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I, B_Cu, B_SilkS, F_Cu

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from saopp_board import ERR, ROUND, P, mm, add_circle, poly, grown, area_mm2, bbox_mm, add_filled, pad_poly  # noqa: E402
from saopp_symbols import SYMBOLS  # noqa: E402

SLUG = "eggplant"
OUT = os.path.join(HERE, SLUG + ".kicad_pcb")
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
ART = json.load(open(os.path.join(HERE, "..", "art", "art.json")))

SCALE = 1.3         # the whole design is this much bigger than the maker's: the smallest size the standard parts fit
CLEAR = 0.30        # copper-to-copper gap cut into the GND copper
EDGE = 0.55         # ground copper stops this far short of the board edge (clear of the panel's mouse-bite holes)
SIG = 0.20          # signal track width
PWR = 0.40
R2 = math.sqrt(2)
EX0, EY0 = 8.906653125, 63.33485      # Eagle x of the left edge and y of the top edge of the maker's outline


RULE_SEVERITIES = {
    "annular_width": "error",
    "clearance": "error",
    "connection_width": "warning",
    "copper_edge_clearance": "error",
    "copper_sliver": "warning",
    "courtyards_overlap": "error",
    "creepage": "error",
    "diff_pair_gap_out_of_range": "error",
    "diff_pair_uncoupled_length_too_long": "error",
    "drill_out_of_range": "error",
    "duplicate_footprints": "warning",
    "extra_footprint": "warning",
    "footprint": "error",
    "footprint_filters_mismatch": "ignore",
    "footprint_symbol_field_mismatch": "warning",
    "footprint_symbol_mismatch": "warning",
    "footprint_type_mismatch": "ignore",
    "hole_clearance": "error",
    "hole_to_hole": "warning",
    "holes_co_located": "warning",
    "invalid_outline": "error",
    "isolated_copper": "warning",
    "item_on_disabled_layer": "error",
    "items_not_allowed": "error",
    "length_out_of_range": "error",
    "lib_footprint_issues": "warning",
    "lib_footprint_mismatch": "warning",
    "malformed_courtyard": "error",
    "microvia_drill_out_of_range": "error",
    "mirrored_text_on_front_layer": "warning",
    "missing_courtyard": "ignore",
    "missing_footprint": "warning",
    "missing_tuning_profile": "warning",
    "net_conflict": "warning",
    "nonmirrored_text_on_back_layer": "warning",
    "npth_inside_courtyard": "error",
    "padstack": "warning",
    "pth_inside_courtyard": "error",
    "shorting_items": "error",
    "silk_edge_clearance": "warning",
    "silk_over_copper": "warning",
    "silk_overlap": "warning",
    "skew_out_of_range": "error",
    "solder_mask_bridge": "error",
    "starved_thermal": "error",
    "text_height": "warning",
    "text_on_edge_cuts": "error",
    "text_thickness": "warning",
    "through_hole_pad_without_hole": "error",
    "too_many_vias": "error",
    "track_angle": "error",
    "track_dangling": "warning",
    "track_not_centered_on_via": "ignore",
    "track_on_post_machined_layer": "error",
    "track_segment_length": "error",
    "track_width": "error",
    "tracks_crossing": "error",
    "tuning_profile_track_geometries": "ignore",
    "unconnected_items": "error",
    "unresolved_variable": "error",
    "via_dangling": "warning",
    "zones_intersect": "error"
}
RULES = {
    "max_error": 0.005,
    "min_clearance": 0.15,
    "min_connection": 0.0,
    "min_copper_edge_clearance": 0.25,
    "min_groove_width": 0.0,
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.25,
    "min_microvia_diameter": 0.2,
    "min_microvia_drill": 0.1,
    "min_resolved_spokes": 2,
    "min_silk_clearance": 0.0,
    "min_text_height": 0.8,
    "min_text_thickness": 0.08,
    "min_through_hole_diameter": 0.3,
    "min_track_width": 0.15,
    "min_via_annular_width": 0.1,
    "min_via_diameter": 0.5,
    "solder_mask_to_copper_clearance": 0.0,
    "use_height_for_length_calcs": True
}


def S(p):
    """A point of art.json (worn position, maker's size, box corner at 100, 100) -> world, scaled about that corner."""
    return (100 + SCALE * (p[0] - 100), 100 + SCALE * (p[1] - 100))


def A(ax, ay):
    """Upright-eggplant coordinates (mm at the SAO++ size) -> world."""
    ex, ey = EX0 + ax / SCALE, EY0 - ay / SCALE
    return S(((ex - ey) / R2 + ART["offset"][0], -(ex + ey) / R2 + ART["offset"][1]))


def Ad(ax, ay):
    """A direction in A -> the same direction in world."""
    return ((ax + ay) / R2, (ay - ax) / R2)


def toA(w):
    o = A(0, 0)
    u, v = w[0] - o[0], w[1] - o[1]
    return ((u - v) / R2, (u + v) / R2)


def add(p, *terms):
    x, y = p
    for k, d in terms:
        x, y = x + k * d[0], y + k * d[1]
    return (x, y)


def union(parts):
    out = pcbnew.SHAPE_POLY_SET()
    for p_ in parts:
        out.BooleanAdd(p_)
    out.Simplify()
    return out


def trim_thin(ps):
    """Cut hair-thin strips and points (under 0.16 mm wide) out of a copper shape, in place.

    The shapes have holes, and shrinking a shape with holes opens slits in KiCad 10, so the thin parts are found
    on a fractured copy and subtracted from the real shape."""
    fat = pcbnew.SHAPE_POLY_SET(ps)
    fat.Fracture()
    fat = grown(grown(fat, -0.08), 0.085)
    thin = pcbnew.SHAPE_POLY_SET(ps)
    thin.BooleanSubtract(fat)
    for k in range(thin.OutlineCount()):
        q = pcbnew.SHAPE_POLY_SET(thin.Polygon(k))
        if area_mm2(q) > 0.003:
            ps.BooleanSubtract(grown(q, 0.01))
    ps.Simplify()


def disc(c, r):
    ps = pcbnew.SHAPE_POLY_SET()
    add_circle(ps, P(*c), r)
    return ps


# ---- outline and a walk along it ------------------------------------------------------------------
OUTLINE = [S(p) for p in ART["outline"]]
if sum(OUTLINE[i][0] * OUTLINE[(i + 1) % len(OUTLINE)][1] - OUTLINE[(i + 1) % len(OUTLINE)][0] * OUTLINE[i][1]
       for i in range(len(OUTLINE))) > 0:
    OUTLINE.reverse()                      # anticlockwise as seen from the front: down the eggplant's left side first
_i0 = min(range(len(OUTLINE)), key=lambda i: OUTLINE[i][1])
OUTLINE = OUTLINE[_i0:] + OUTLINE[:_i0]    # distances along the edge are counted from the tip of the stalk
body = poly(OUTLINE)
assert body.OutlineCount() == 1
bx0, by0, bx1, by1 = bbox_mm(body)
print(f"board as worn {bx1 - bx0:.2f} x {by1 - by0:.2f} mm ({SCALE} x the maker's {(bx1 - bx0) / SCALE:.2f} x {(by1 - by0) / SCALE:.2f})")
N = len(OUTLINE)
SEG = [math.dist(OUTLINE[i], OUTLINE[(i + 1) % N]) for i in range(N)]
CUM = [0.0]
for d_ in SEG:
    CUM.append(CUM[-1] + d_)
PERIM = CUM[-1]


def frame(s):
    """Point on the outline at distance s along it, with the direction of travel and the inward direction there."""
    s %= PERIM
    i = max(k for k in range(N) if CUM[k] <= s)
    a, b = OUTLINE[i], OUTLINE[(i + 1) % N]
    f = (s - CUM[i]) / SEG[i]
    t = ((b[0] - a[0]) / SEG[i], (b[1] - a[1]) / SEG[i])
    return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])), t, (t[1], -t[0])


def s_near(w):
    """Distance along the outline of the outline point nearest to w."""
    best = None
    for i in range(N):
        a, b = OUTLINE[i], OUTLINE[(i + 1) % N]
        f = max(0.0, min(1.0, ((w[0] - a[0]) * (b[0] - a[0]) + (w[1] - a[1]) * (b[1] - a[1])) / SEG[i] ** 2))
        q = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
        d = math.dist(q, w)
        if best is None or d < best[0]:
            best = (d, CUM[i] + f * SEG[i])
    return best[1]


def inset(s, d, along=0.0):
    """The point d mm inside the edge at distance s along it (and `along` mm further on, measured on a straight line)."""
    p, t, n = frame(s)
    return add(p, (d, n), (along, t))


def edge_run(s0, s1, d, step=0.4):
    """A line that follows the edge d mm inside it, from s0 to s1 along the outline."""
    k = max(2, int(math.ceil((s1 - s0) / step)) + 1)
    return [inset(s0 + (s1 - s0) * i / (k - 1), d) for i in range(k)]


board = pcbnew.CreateEmptyBoard()
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
for n_ in sorted({n_ for d_ in PADNETS.values() for n_ in d_.values()}):
    ni = pcbnew.NETINFO_ITEM(board, n_)
    board.Add(ni)
    nets[n_] = ni


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
            net = f"unconnected-({ref}-{PINNAMES[ref][num].replace('/', '{slash}')}-Pad{num})"      # as the schematic names it
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
        if net:
            pad.SetNet(nets[net])


def ang(v):
    """Angle of a direction, anticlockwise on screen, in degrees."""
    return math.degrees(math.atan2(-v[1], v[0]))


def place(ref, pos, want, also=None):
    """Place on the back and turn the part so pad `want[0]` lands on `want[1]` (world). `also` checks a second pad."""
    name = SYMBOLS[PARTS[ref]["symbol"]][2].split(":")[1]
    fp = pcbnew.FootprintLoad(LIB, name)
    assert fp is not None, f"missing footprint {name}"
    fp.SetReference(ref)
    board.Add(fp)
    fp.SetPosition(P(*pos))
    fp.Flip(P(*pos), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetVisible(False)
    fp.SetOrientationDegrees(0)
    p0 = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == want[0]][0]
    turn = ang((want[1][0] - pos[0], want[1][1] - pos[1])) - ang((p0[0] - pos[0], p0[1] - pos[1]))
    fp.SetOrientationDegrees(round(turn, 3))
    for num, where in [want] + ([also] if also else []):
        miss = min(math.dist(mm(p.GetPosition()), where) for p in fp.Pads() if p.GetNumber() == num)
        assert miss < 0.03, f"{ref}: pad {num} misses {where} by {miss:.2f} mm (wrong way round?)"
    link(fp, ref)
    return fp


def pp(fp, num, pick=None):
    pts = [mm(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]
    return pts[0] if pick is None else sorted(pts, key=pick)[0]


# ---- placement ----------------------------------------------------------------------------------
# XIAO: lies across the fat part of the body, USB-C at the eggplant's left edge (the only long straight-ish edge)
XA = (None, 47.2)
_left = min(toA(p)[0] for p in OUTLINE if abs(toA(p)[1] - XA[1]) < 9.5)
XA = (_left + 10.48, XA[1])                                     # module end flush with the edge where it bulges most
E_, S_ = Ad(1, 0), Ad(0, 1)                                     # the eggplant's own "right" and "down" in world
xiao = place("U1", A(*XA), ("14", A(XA[0] - 7.56, XA[1] + 8.11)), ("1", A(XA[0] - 7.56, XA[1] - 8.055)))


def xp(num, pick=None):
    return toA(pp(xiao, num, pick))


# SAO connector: square to the world (key slot up when worn), in the neck, at least 3 mm from every edge
CONN = A(14.5, 28.6)
conn = place("J1", CONN, ("1", (CONN[0] - 2.54, CONN[1] - 3.4)), ("6", (CONN[0] + 2.54, CONN[1] + 3.4)))
_body3 = grown(body, -3.0)
_cb = poly([(CONN[0] + sx * 7.635, CONN[1] + sy * 4.45) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
_cb.BooleanSubtract(_body3)
assert _cb.OutlineCount() == 0, f"connector body closer than 3 mm to the edge by {area_mm2(_cb):.2f} mm2"

# power switch: on the straight stretch of the neck's right edge, knob out of the edge
SW_S = s_near(A((28.7 - EX0) * SCALE, (EY0 - 48.0) * SCALE)) - 0.6
sw_p, sw_t, sw_n = frame(SW_S)
_a, _b = frame(SW_S - 5.65)[0], frame(SW_S + 5.65)[0]
sw_t = ((_b[0] - _a[0]) / math.dist(_a, _b), (_b[1] - _a[1]) / math.dist(_a, _b))      # chord under the switch
sw_n = (sw_t[1], -sw_t[0])
SW = add(((_a[0] + _b[0]) / 2, (_a[1] + _b[1]) / 2), (2.18, sw_n))      # tabs end 0.27 mm inside the edge, as the part is drawn
sw = place("SW1", SW, ("1", add(SW, (3.0, sw_t), (1.43, sw_n))), ("4", add(SW, (-3.0, sw_t), (1.43, sw_n))))

# LiPo connector: plug goes in from the right-hand edge, beside the XIAO
JST_S = s_near(A(35.6, 55.5)) - 1.5
_a, _b = frame(JST_S - 4.1)[0], frame(JST_S + 4.1)[0]
j_t = ((_b[0] - _a[0]) / math.dist(_a, _b), (_b[1] - _a[1]) / math.dist(_a, _b))
j_n = (j_t[1], -j_t[0])
JST = add(((_a[0] + _b[0]) / 2, (_a[1] + _b[1]) / 2), (5.0, j_n))        # hold-down pads end 0.4 mm inside the edge
jst = place("J2", JST, ("1", add(JST, (1.0, j_t), (2.85, j_n))), ("2", add(JST, (-1.0, j_t), (2.85, j_n))))

# LEDs: near the edge, firing outward, in the order the data line visits them (anticlockwise seen from the front)
D_STRIP, D_LED, D_DATA = 0.93, 1.675, 1.975       # how far inside the edge: 3.3 V strip, LED centres, data line
LED_AT = {                                        # ref: the maker's light it stands for, and where (A coordinates)
    "D1": ("LED4, moved 7 mm along the stripe (the module is where it was)", (2.9, 63.0)),
    "D2": ("LED2, moved 42 mm to the far end of the stripe (the connector is where it was)", (13.5, 72.3)),
    "D3": ("LED5, 3 mm nearer the edge", ((27.7075906 - EX0) * SCALE, (EY0 - 12.0904594) * SCALE)),
    "D4": ("LED3, 1.5 mm nearer the edge", ((32.4929469 - EX0) * SCALE, (EY0 - 26.4465219) * SCALE)),
    "D5": ("LED1, moved 5 mm toward the edge (the connector is where it was)", (26.5, 31.5)),
}
led, cap, LED_S = {}, {}, {}
for i, ref in enumerate(sorted(LED_AT)):
    s_ = s_near(A(*LED_AT[ref][1]))
    LED_S[ref] = s_

    p_, t_, n_ = frame(s_)
    c_ = add(p_, (D_LED, n_))
    led[ref] = place(ref, c_, ("3", add(c_, (-1.405, t_), (0.3, n_))), ("4", add(c_, (-0.425, t_), (0.4, n_))))
    for g in led[ref].GraphicalItems():            # the footprint's silkscreen lens mark would be cut by the board edge
        if g.GetLayer() == B_SilkS:
            g.SetLayer(pcbnew.B_Fab)
    sc = s_ + (-3.6 if ref == "D5" else 3.6)       # its capacitor: just downstream (D5: upstream, the switch is next), across the strip and the data line
    p_, t_, n_ = frame(sc)
    cc = add(p_, (D_DATA, n_))
    cap["C" + ref[1]] = place("C" + ref[1], cc, ("1", add(cc, (-0.775, n_))))

EDGE_BAD = []
_pad_ok = grown(body, -0.25)      # the switch's hold-down tabs sit 0.27 mm from the edge by design
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.IsOnLayer(B_Cu) and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            off = pad_poly(pad, B_Cu)
            off.BooleanSubtract(_pad_ok)
            if off.OutlineCount():
                EDGE_BAD.append(f"{fp.GetReference()} pad {pad.GetNumber()}")

print("pads closer than 0.25 mm to the edge:", EDGE_BAD)
TRACKS = []



def LABELS():
    """Back silkscreen lettering: (text, where, letter height, angle). Everything reads level when the board is worn."""
    sa = ang(sw_t) + 180
    jp1, jp2 = pp(jst, "1"), pp(jst, "2")
    name = add(A(22.0, 60.2), (1.9, (1, 0)), (-0.9, (0, 1)))
    dn = (0, 1)
    out = [("SAO", swp(-3.8, -2.85), 0.8, sa), ("OFF", swp(-0.8, -2.85), 0.8, sa), ("USB/BAT", swp(3.3, -2.85), 0.8, sa),
           ("+", add(jp1, (2.9, j_n)), 1.2, 0), ("-", add(jp2, (2.9, j_n)), 1.2, 0), ("LiPo 3.7V", add(jp1, (2.9, j_n), (-3.5, (1, 0)), (-2.6, (0, 1))), 0.8, 0),
           ("1", (CX - 8.7, j["1"][1]), 0.9, 0),
           ("EGGPLANT SAO", name, 0.95, 0)]
    # the maker's own back lettering, word for word (it was three blocks spread over the back of his board)
    y = 1.8
    for line in ART["back_text"][0]["text"].split("\n"):
        out.append((line.strip(), add(name, (y, dn)), 0.8, 0))
        y += 1.25
    out.append((" ".join(ART["back_text"][2]["text"].split()), add(name, (y, dn)), 0.8, 0))
    out += [("orig. design: Krux, 2018", add(name, (y + 1.5, dn)), 0.8, 0),
            ("SAO++ rA, XIAO ESP32", add(name, (y + 2.9, dn)), 0.8, 0),
            ("USB: NOT ON 'SAO'", add(name, (y + 4.2, dn)), 0.8, 0)]
    return out


# ---- routing (back copper only, no vias) ----------------------------------------------------------
def route(net, pts, width=SIG, clear=CLEAR):
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 1e-6:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(width))
        t.SetLayer(B_Cu)
        t.SetNet(nets[net])
        board.Add(t)
        TRACKS.append((t, clear, net))


def swp(fx, fy):
    """A point given in the switch footprint's own coordinates (pins at fy -1.43, knob and board edge at fy +2.1)."""
    return add(SW, (-fx, sw_t), (-fy, sw_n))


def jp(fx, fy):
    """A point in the LiPo connector footprint's own coordinates (signal pads at fy -2.85, opening at fy +4.4)."""
    return add(JST, (-fx, j_t), (-fy, j_n))


CX, CY = CONN
XX, XY = XA
j = {n: pp(conn, n) for n in "123456"}

# badge 3.3 V: connector pin 1 (top of its pad) -> switch pin 1
route("VSAO", [(j["1"][0], j["1"][1] - 1.8), (j["1"][0] - 0.9, CY - 6.6), swp(-3.0, -3.1), swp(-3.0, -1.43)], PWR)

# I2C: SDA drops between the bottom row's first two pads, SCL leaves the bottom of its own pad; both run to the XIAO's top row
d4, d5 = pp(xiao, "5"), pp(xiao, "6")
TIP = Ad(0, -1.375 - 0.5)                                       # from a top-row pad's centre to just beyond its outer end
t4, t5 = add(d4, (1, TIP)), add(d5, (1, TIP))
assert t4[1] > CY + 6.9, "SDA would not clear SCL below the connector"
route("SDA", [j["3"], (j["3"][0], CY - 0.75), (CX - 1.27, CY + 0.2), (CX - 1.27, t4[1]), t4, d4])
route("SCL", [j["4"], (CX, CY + 6.2), (CX + 3.6, CY + 6.2), t5, d5])

# OFF sense: XIAO D1 -> under the module, between its top pad row and the C3/S3 battery pads -> out of the module's
# far end -> up past the right-hand end of the connector -> along above its top pads -> switch pin 2
d1 = xp("2")
_turn = A(XX + 9.3, XY - 10.3)                                  # just past the module's last pad (D6), 0.6 mm clear of it
LANE_X = CX + 5.0                                              # under the connector's shroud, 1.9 mm right of its GPIO pads
route("OFF_SENSE", [A(*d1), A(d1[0], XY - 6.19), A(XX + 9.3, XY - 6.19), _turn, (LANE_X, _turn[1]), (LANE_X, CY - 6.15),
                    (CX - 1.0, CY - 6.15), swp(-1.5, -3.0), swp(-1.5, -1.43)])

# LiPo +: connector pin 1 -> in at the module's far end -> the C6's battery pad -> the C3 / S3's battery pad
bp6 = xp("15", pick=lambda p: -toA(p)[0])
bp3 = xp("15", pick=lambda p: toA(p)[0])
route("BAT+", [pp(jst, "1"), jp(-1.0, -5.1), A(XX + 11.4, bp6[1]), A(*bp6), A(bp6[0] - 4.1, bp6[1]), A(bp3[0], bp3[1] + 1.0), A(*bp3)], 0.3)

# 3.3 V: XIAO 3V3 pad -> a strip that follows the edge past every LED (between each LED and the edge) -> under the
# LiPo connector -> under the switch body from its lower end -> switch pin 3 (the common)
v33, d10 = xp("12"), xp("11")
S0 = LED_S["D1"] - 4.6                                           # where the strip starts, just before the first LED
JS0, JS1 = JST_S - 7.0, JST_S + 7.0                             # the strip and the data line leave the edge here to pass under J2
S_END = SW_S - 5.65 - 1.6
strip = [A(*v33), A(v33[0], v33[1] + 2.3), A(v33[0] - 2.0, v33[1] + 2.3)] + edge_run(S0, JS0, D_STRIP)
strip += [jp(5.3, 5.0 - D_STRIP), jp(5.3, 0.45), jp(-5.3, 0.45), jp(-5.3, 5.0 - D_STRIP)] + edge_run(JS1, S_END, D_STRIP)
route("V3V3", strip, PWR, 0.25)
route("V3V3", [inset(S_END, D_STRIP), swp(6.6, 0.33), swp(4.2, 0.33), swp(3.45, 1.25), swp(1.85, 1.25), swp(1.5, 0.7), swp(1.5, -1.43)], 0.3, 0.25)
for ref in led:                                                  # each LED's supply pad and its capacitor reach out to the strip
    p4 = pp(led[ref], "4")
    s4 = s_near(p4)
    route("V3V3", [p4, inset(s4, D_STRIP)], 0.25, 0.2)
    c1 = pp(cap["C" + ref[1]], "1")
    route("V3V3", [c1, inset(s_near(c1), D_STRIP)], 0.4, 0.2)

# LED data: XIAO D10 -> 330 ohm -> D1 ... D5, along the edge just inside the strip, between each capacitor's pads
R1_A = (d10[0], d10[1] + 2.75)                                  # end-on to the D10 pad
r1 = place("R1", A(*R1_A), ("1", A(R1_A[0], R1_A[1] - 0.825)))
route("LED_DATA", [A(*d10), pp(r1, "1")])
din = pp(led["D1"], "3")
route("LED_DIN", [pp(r1, "2"), A(R1_A[0] - 1.0, R1_A[1] + 1.6), inset(s_near(din) - 1.4, D_DATA + 0.9), inset(s_near(din) - 0.9, D_DATA), din])
for k in range(1, 5):
    a_, b_ = pp(led[f"D{k}"], "2"), pp(led[f"D{k + 1}"], "3")
    sa, sb = s_near(a_), s_near(b_)
    if sa < JST_S < sb:
        mid = edge_run(sa, JS0 - 0.6, D_DATA) + [jp(5.9, 5.0 - D_DATA), jp(5.9, -0.2), jp(-5.9, -0.2), jp(-5.9, 5.0 - D_DATA)] + edge_run(JS1 + 0.6, sb, D_DATA)
    else:
        mid = edge_run(sa, sb, D_DATA)
    route(f"LED_D{k}", [a_] + mid + [b_], SIG, 0.2)
# the XIAO's GND pad sits on the copper-free stripe too: a short track under the module takes it to the ground copper
g13 = xp("13")
route("GND", [A(*g13), A(g13[0], XY + 5.9), A(XX + 3.8, XY + 5.9)], 0.3)
# ground for the two LEDs that sit on the copper-free stripe: LED -> its capacitor -> inward to the ground copper
for ref in ("D1", "D2"):
    g1, c2 = pp(led[ref], "1"), pp(cap["C" + ref[1]], "2")
    route("GND", [g1, inset(s_near(g1), 2.95), inset(s_near(c2) - 0.9, 2.95), c2, inset(s_near(c2) + 1.5, 8.6)], 0.3)
print("along the edge (mm): " + ", ".join(f"{r} {LED_S[r]:.1f}" for r in sorted(LED_S)) + f"; J2 {JST_S:.1f}; SW1 {SW_S:.1f}; perimeter {PERIM:.1f}")


# ---- art, front and back ---------------------------------------------------------------------------
def art(name):
    return union([poly([S(p) for p in pl]) for pl in ART[name]])


stripe = art("no_copper")          # the maker kept copper out of a long stripe and a short streak: the board shows through
calyx = art("calyx")               # stalk and leaves: bare metal
calyx_open = art("calyx_mask")
marks = art("silk")                # a vein on the calyx and the shine mark on the body
pegs = pcbnew.SHAPE_POLY_SET()
for pad in sw.Pads():
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        add_circle(pegs, pad.GetPosition(), ToMM(pad.GetDrillSize().x) / 2 + 0.3)

# ---- back copper: ground everywhere except the stripe ----------------------------------------------
gnd = pcbnew.SHAPE_POLY_SET(inner)
gnd.BooleanSubtract(grown(stripe, 0.1))
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
for t, clear, net in TRACKS:
    if net != "GND":
        t.TransformShapeToPolygon(cut, B_Cu, FromMM(clear), ERR, pcbnew.ERROR_OUTSIDE)
n_keep = 0
for g in xiao.GraphicalItems():                                  # the module's own underside test pads: no carrier copper there
    if g.GetLayer() == pcbnew.Dwgs_User and g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
        add_circle(cut, g.GetCenter(), 0.85 + 0.15)
        n_keep += 1
assert n_keep == 8, n_keep
cut.Simplify()
gnd.BooleanSubtract(cut)
gnd.Simplify()
trim_thin(gnd)

gnd_pads = pcbnew.SHAPE_POLY_SET()
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if pad.GetNetCode() == gnd_code:
            gnd_pads.Append(pad_poly(pad, B_Cu))
for t, clear, net in TRACKS:
    if net == "GND":
        t.TransformShapeToPolygon(gnd_pads, B_Cu, 0, ERR, pcbnew.ERROR_OUTSIDE)
gnd_pads.Simplify()
n_gnd = n_drop = 0
GND_DBG = []
for i in range(gnd.OutlineCount()):
    piece = pcbnew.SHAPE_POLY_SET(gnd.Polygon(i))
    both = pcbnew.SHAPE_POLY_SET(piece)
    both.BooleanIntersection(gnd_pads)
    o = piece.Outline(0)
    if area_mm2(both) > 0.005:
        add_filled(board, piece, B_Cu, nets["GND"])
        n_gnd += 1
        GND_DBG.append([(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())])
        print("  GND piece mm2:", round(area_mm2(piece), 1), "at", [round(v, 1) for v in bbox_mm(piece)])
    else:
        n_drop += 1                                              # copper that touches no ground pad: left out
        print("  left out (touches no ground pad) mm2:", round(area_mm2(piece), 2), "at", [round(v, 1) for v in bbox_mm(piece)])
print("back copper: GND pieces", n_gnd, "pieces left out", n_drop)
if os.environ.get("EGG_DEBUG"):
    dbg = {"outline": OUTLINE, "pads": [], "tracks": [], "art": {k: [[S(p) for p in pl] for pl in ART[k]] for k in ("body", "calyx", "no_copper", "silk")}}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            ps = pad_poly(pad, B_Cu) if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH else disc(mm(pad.GetPosition()), 0.45)
            o = ps.Outline(0)
            dbg["pads"].append([fp.GetReference(), pad.GetNumber(), pad.GetNetname(), [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]])
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.B_Fab, pcbnew.Dwgs_User) and hasattr(g, "GetShape"):
                bb = g.GetBoundingBox()
                if g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
                    dbg["pads"].append([fp.GetReference(), "", "keepout", [(ToMM(g.GetCenter().x) + 0.85 * math.cos(a / 8 * math.pi), ToMM(g.GetCenter().y) + 0.85 * math.sin(a / 8 * math.pi)) for a in range(16)]])
                else:
                    ps = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(ps, g.GetLayer(), 0, ERR, pcbnew.ERROR_INSIDE)
                    o = ps.Outline(0)
                    dbg["pads"].append([fp.GetReference(), "", "fab", [(ToMM(o.CPoint(k).x), ToMM(o.CPoint(k).y)) for k in range(o.PointCount())]])
    dbg["tracks"] = [[n_, ToMM(t.GetWidth()), mm(t.GetStart()), mm(t.GetEnd())] for t, _, n_ in TRACKS]
    dbg["gnd"] = GND_DBG
    json.dump(dbg, open(os.environ["EGG_DEBUG"], "w"))
    print("debug dump written")
    sys.stdout.flush()
    os._exit(0)

# ---- front: the maker's art ------------------------------------------------------------------------
fcu = art("body")                                                # body copper under mask, as the maker had it
fcu.BooleanSubtract(grown(stripe, 0.0))
fcu.BooleanAdd(calyx)
fcu.BooleanIntersection(inner)
trim_thin(fcu)
fcu.BooleanSubtract(pegs)
fcu.Simplify()
add_filled(board, fcu, F_Cu)                                     # no net: nothing on the front is connected to anything
add_filled(board, calyx_open, pcbnew.F_Mask)
add_filled(board, marks, pcbnew.F_SilkS)

# ---- back silkscreen -------------------------------------------------------------------------------
def text(txt, at, size, rot=0, layer=B_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(P(*at))
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetMirrored(True)
    t.SetTextAngleDegrees(rot)
    board.Add(t)


for txt, at, size, rot in LABELS():
    text(txt, at, size, rot)

# the maker's tally marks and the two-line code beside them: kept as a group, moved up the neck (the switch and the
# connector are where they were) and still upright when worn
MARKS_AT = (107.6, 112.0)
_m = [(S(a_), S(b_), w_) for a_, b_, w_ in ART["back_marks"]]
_mx = [v for a_, b_, _ in _m for v in (a_[0], b_[0])]
_my = [v for a_, b_, _ in _m for v in (a_[1], b_[1])]
_dx, _dy = MARKS_AT[0] - (min(_mx) + max(_mx)) / 2, MARKS_AT[1] - (min(_my) + max(_my)) / 2
for a_, b_, w_ in _m:
    ln = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    ln.SetStart(P(a_[0] + _dx, a_[1] + _dy))
    ln.SetEnd(P(b_[0] + _dx, b_[1] + _dy))
    ln.SetWidth(FromMM(w_ * SCALE))
    ln.SetLayer(B_SilkS)
    board.Add(ln)
print(f"tally marks: {max(_mx) - min(_mx):.1f} x {max(_my) - min(_my):.1f} mm, moved by {_dx:.1f}, {_dy:.1f}")
for k, line in enumerate(ART["back_text"][1]["text"].split("\n")):
    text(line, (MARKS_AT[0], MARKS_AT[1] + (max(_my) - min(_my)) / 2 + 1.3 + 1.3 * k), 0.8)

# ---- report ---------------------------------------------------------------------------------------
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

# kicad-cli 10.0.8 can rewrite the project file and drop these: put the board's rule settings back every build
PRO = os.path.join(HERE, SLUG + ".kicad_pro")
pro = json.load(open(PRO))
pro["board"]["design_settings"]["rule_severities"] = RULE_SEVERITIES
pro["board"]["design_settings"]["rules"] = RULES
json.dump(pro, open(PRO, "w"), indent=2)
assert not EDGE_BAD, f"pads closer than 0.25 mm to the board edge: {EDGE_BAD}"
sys.stdout.flush()
os._exit(0)          # KiCad 10's Python can crash while tidying up at exit, after the board is saved
