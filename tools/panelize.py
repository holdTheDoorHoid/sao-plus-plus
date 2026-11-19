#!/usr/bin/env python3
"""Panelize one SAO++ board: boards/<slug>/production/panel.json -> production/panel/<slug>-panel.kicad_pcb

Run with KiCad 10's Python from the repo root:
  flatpak run --filesystem=$PWD --command=python3 org.kicad.KiCad tools/panelize.py <slug>

Each board sits in its own pocket: a routed slot (default 2 mm) all the way round, held by break-off tabs
with a row of 0.5 mm mouse-bite holes on the board's edge line. A frame with top and bottom rails carries
three fiducials and four tooling holes. Board copies get their own nets (B2-GND ...) and their own
reference numbers (J1 -> J101, J201 ...), so the panel's BOM and placement files cover every part.
"""
import json
import os
import re
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from saopp_paths import board_dir  # noqa: E402
from pcbnew import FromMM, ToMM, VECTOR2I

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = os.path.join(ROOT, "lib", "sao-plus-plus.pretty")
ERR = FromMM(0.005)


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def ring_pts(chain):
    return [(ToMM(chain.CPoint(i).x), ToMM(chain.CPoint(i).y)) for i in range(chain.PointCount())]


def poly_from(pts):
    """A one-outline polygon set. Points are put in a consistent winding; KiCad's boolean ops ignore the other one."""
    pts = list(pts)
    area2 = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area2 < 0:
        pts.reverse()
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in pts:
        ps.Append(FromMM(x), FromMM(y))
    return ps


def edge_crossing(ring, near, direction, lateral):
    """Where the outline crosses the line through `near` (shifted sideways by `lateral`) along `direction`."""
    axis = 0 if direction[1] == "x" else 1          # axis the tab runs along
    fixed = near[1 - axis] + lateral
    best = None
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        fa, fb = a[1 - axis] - fixed, b[1 - axis] - fixed
        if fa == fb or (fa > 0) == (fb > 0):
            continue
        t = fa / (fa - fb)
        v = a[axis] + t * (b[axis] - a[axis])
        if best is None or abs(v - near[axis]) < abs(best - near[axis]):
            best = v
    assert best is not None and abs(best - near[axis]) < 3.0, f"no board edge within 3 mm of tab point {near}"
    return (best, fixed) if axis == 0 else (fixed, best)


def main(slug):
    prod = os.path.join(str(board_dir(slug)), "production")
    cfg = json.load(open(os.path.join(prod, "panel.json")))
    src = os.path.join(str(board_dir(slug)), "hardware", f"{slug}.kicad_pcb")
    board = pcbnew.LoadBoard(src)
    slot, web, rail, tabw = cfg["slot"], cfg["web"], cfg["rail"], cfg["tab_width"]

    footprints = list(board.GetFootprints())
    drawings = list(board.GetDrawings())
    tracks = list(board.Tracks())

    # ---- the single board's outline --------------------------------------------------------------
    edges = [d for d in drawings if d.GetLayer() == pcbnew.Edge_Cuts]
    rings = sorted((ring_pts(e.GetPolyShape().Outline(0)) for e in edges),
                   key=lambda r: -abs(sum(r[i][0] * r[(i + 1) % len(r)][1] - r[(i + 1) % len(r)][0] * r[i][1] for i in range(len(r)))))
    outer, holes = rings[0], rings[1:]
    xs, ys = [p[0] for p in outer], [p[1] for p in outer]
    x0, y0, w, h = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    pitch_x, pitch_y = w + 2 * slot + web, h + 2 * slot + web
    px0, py0 = x0 - slot - web, y0 - slot - web - rail
    pw = cfg["cols"] * pitch_x + web
    ph = cfg["rows"] * pitch_y + web + 2 * rail
    print(f"single board {w:.1f} x {h:.1f} mm; panel {pw:.1f} x {ph:.1f} mm")

    material = poly_from([(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)])
    pockets = pcbnew.SHAPE_POLY_SET()
    bodies = pcbnew.SHAPE_POLY_SET()
    tabs = pcbnew.SHAPE_POLY_SET()
    bites = []

    netcache = {}
    edge_ids = {id(e) for e in edges}
    fp_refs = {}                                             # original reference of every real part, read before any renaming
    for fp in footprints:
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", fp.GetReference())
        fp_refs[id(fp)] = (m.group(1), int(m.group(2))) if (m and not (fp.GetAttributes() & pcbnew.FP_BOARD_ONLY)) else None
    renames = []

    def net_for(item, k):
        name = item.GetNetname()
        if not name or k == 0:
            return None
        new = f"B{k + 1}-{name}"
        if new not in netcache:
            netcache[new] = pcbnew.NETINFO_ITEM(board, new)
            board.Add(netcache[new])
        return netcache[new]

    k = 0
    for r in range(cfg["rows"]):
        for c in range(cfg["cols"]):
            dx, dy = c * pitch_x, r * pitch_y
            off = VECTOR2I(FromMM(dx), FromMM(dy))
            # pocket, body, tabs
            pocket = poly_from([(x + dx, y + dy) for x, y in outer])
            pocket.Inflate(FromMM(slot), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
            pockets.BooleanAdd(pocket)
            body = poly_from([(x + dx, y + dy) for x, y in outer])
            for hl in holes:
                body.BooleanSubtract(poly_from([(x + dx, y + dy) for x, y in hl]))
            bodies.BooleanAdd(body)
            for t in cfg["tabs"]:
                d = t["dir"]
                sign = 1 if d[0] == "+" else -1
                axis = 0 if d[1] == "x" else 1
                ex, ey = edge_crossing(outer, t["near"], d, 0.0)
                a0, a1 = -0.8, slot + 0.8                    # along the tab: a little into the board, a little into the frame
                if axis == 0:
                    rect = [(ex + sign * a0, ey - tabw / 2), (ex + sign * a1, ey - tabw / 2), (ex + sign * a1, ey + tabw / 2), (ex + sign * a0, ey + tabw / 2)]
                else:
                    rect = [(ex - tabw / 2, ey + sign * a0), (ex + tabw / 2, ey + sign * a0), (ex + tabw / 2, ey + sign * a1), (ex - tabw / 2, ey + sign * a1)]
                tabs.BooleanAdd(poly_from([(x + dx, y + dy) for x, y in rect]))
                for i in range(-2, 3):                        # five holes on the board's edge line
                    bx, by = edge_crossing(outer, t["near"], d, i * 0.75)
                    bites.append((bx + dx, by + dy))
            # copies of everything except the outline
            for it in footprints + drawings + tracks:
                if id(it) in edge_ids:
                    continue
                is_fp = id(it) in fp_refs
                if k == 0:
                    item = it
                else:
                    item = it.Duplicate(False) if is_fp else it.Duplicate()
                    if hasattr(item, "Cast"):
                        item = item.Cast()               # Duplicate() hands back a generic item; get the real type back
                    item.Move(off)
                    board.Add(item)
                    if is_fp:
                        for pad in item.Pads():
                            n = net_for(pad, k)
                            if n:
                                pad.SetNet(n)
                    elif hasattr(item, "GetNetname") and hasattr(item, "SetNet"):
                        n = net_for(item, k)
                        if n:
                            item.SetNet(n)
                if is_fp and fp_refs[id(it)]:
                    prefix, num = fp_refs[id(it)]
                    renames.append((item, f"{prefix}{(k + 1) * 100 + num}"))
            k += 1

    # Tidy the routed area before cutting it out of the frame:
    #  - a slot round a board with deep bays can pinch off loose islands of frame (inside the curl of the tail);
    #    loose pieces would rattle free in the router, so enclosed islands are milled out with the slot;
    #  - thin fingers of frame (narrower than `min_frame`) between two bays snap off, so they are milled out too.
    # (Outlines are rebuilt without holes before any shrink: shrinking a polygon with holes makes slits in KiCad.)
    def outers_only(ps):
        out = pcbnew.SHAPE_POLY_SET()
        for i in range(ps.OutlineCount()):
            out.BooleanAdd(poly_from(ring_pts(ps.Outline(i))))
        return out

    min_frame = cfg.get("min_frame", 2.5)
    pockets.Simplify()
    pockets = outers_only(pockets)
    pockets.Inflate(FromMM(min_frame / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    pockets = outers_only(pockets)
    pockets.Inflate(-FromMM(min_frame / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    material.BooleanSubtract(pockets)
    material.Simplify()
    if material.OutlineCount() > 1:
        main_i = max(range(material.OutlineCount()), key=lambda i: pcbnew.SHAPE_POLY_SET(material.Polygon(i)).Area())
        material = pcbnew.SHAPE_POLY_SET(material.Polygon(main_i))
    material.BooleanAdd(bodies)
    material.BooleanAdd(tabs)
    for item, ref in renames:
        item.SetReference(ref)
    refs = [ref for _, ref in renames]
    assert len(refs) == len(set(refs)), "duplicate part references on the panel"

    material.Simplify()
    assert material.OutlineCount() == 1, f"panel fell into {material.OutlineCount()} pieces: a tab is not reaching the frame"

    # ---- new outline; park the single-board outline on a non-fab layer --------------------------
    for e in edges:
        e.SetLayer(pcbnew.Cmts_User)
    n_rings = 0
    for i in range(material.OutlineCount()):
        chains = [material.Outline(i)] + [material.Hole(i, j) for j in range(material.HoleCount(i))]
        for ch in chains:
            s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
            s.SetPolyShape(poly_from(ring_pts(ch)))
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetFilled(False)
            s.SetWidth(FromMM(0.1))
            board.Add(s)
            n_rings += 1
    print("outline paths:", n_rings, "| tabs:", len(cfg["tabs"]) * k, "| mouse-bite holes:", len(bites))

    def add_fp(name, x, y):
        fp = pcbnew.FootprintLoad(LIB, name)
        board.Add(fp)
        fp.SetPosition(P(x, y))
        fp.SetReference("")
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

    for x, y in bites:
        add_fp("SAOPP_PANEL_MouseBite_0.5mm", x, y)
    m = rail / 2
    for x, y in ((px0 + 5, py0 + m), (px0 + pw - 5, py0 + m), (px0 + 5, py0 + ph - m), (px0 + pw - 5, py0 + ph - m)):
        add_fp("SAOPP_PANEL_ToolingHole_1.152mm", x, y)
    for x, y in ((px0 + 10, py0 + m), (px0 + pw - 10, py0 + m), (px0 + 10, py0 + ph - m)):      # three, not four: the gap shows which way up
        add_fp("SAOPP_PANEL_Fiducial_1mm_BothSides", x, y)

    for layer, mirror in ((pcbnew.F_SilkS, False), (pcbnew.B_SilkS, True)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(f"SAO++  {slug}  rev {board.GetTitleBlock().GetRevision()}  panel {cfg['rows']}x{cfg['cols']}")
        t.SetLayer(layer)
        t.SetPosition(P(px0 + pw / 2, py0 + m))
        t.SetTextSize(VECTOR2I(FromMM(1.5), FromMM(1.5)))
        t.SetTextThickness(FromMM(0.2))
        t.SetMirrored(mirror)
        board.Add(t)

    out_dir = os.path.join(prod, "panel")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{slug}-panel.kicad_pcb")
    board.GetTitleBlock().SetTitle(board.GetTitleBlock().GetTitle() + f" - panel {cfg['rows']}x{cfg['cols']}")
    pcbnew.SaveBoard(out, board)
    json.dump({"panel_mm": [round(pw, 2), round(ph, 2)], "board_mm": [round(w, 2), round(h, 2)], "boards": k},
              open(os.path.join(out_dir, "panel-info.json"), "w"))
    print("saved", out)


if __name__ == "__main__":
    main(sys.argv[1])
