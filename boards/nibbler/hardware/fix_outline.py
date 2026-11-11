#!/usr/bin/env python3
"""Write outline.json for Nibbler from the 2018 Edge.Cuts drawing, repairing the one defect that made
tools/extract_outline.py fail on this board.

Run with plain system Python, from the repo root:
  python3 boards/nibbler/hardware/fix_outline.py

What was wrong (found 2026-11-10)
  The 2018 edge is 10,700 short straight lines (an SVG path, each line 16-27 micrometres long). They are NOT broken:
  every end point meets exactly one other end point, there are no duplicates and no stray pieces, and they form a
  single loop. The fault is at the very top of the stalk (x 138.43, y 55.46), where the SVG path ends: its last two
  lines run 2.3 micrometres past the starting point and come back to it. That makes a tiny sliver where the path crosses
  itself, 2.3 micrometres long and a few hundredths of a micrometre wide. KiCad reads it as a second, 3-corner outline, decides the board edge is
  not one clean loop, and falls back to a plain 60 x 75 mm rectangle.

The repair
  Drop the one overshooting corner (138.43488, 55.46367), so the path goes straight from the last good corner back to
  the start. Nothing else moves; the dropped corner sat 0.02 micrometres off the new line. No gap had to be closed
  (the largest gap in the drawing is zero).

Then the 10,699 remaining corners are thinned to the ones the shape needs (none moves more than 1 micrometre; see TOL).

Writes hardware/outline.json in the format tools/extract_outline.py uses: {"outer": [[x, y], ...], "holes": []},
mm, KiCad front view, rounded to 0.1 micrometre.
"""
import collections
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "original", "Nibbler_PCB.kicad_pcb")
OUT = os.path.join(HERE, "outline.json")
OVERSHOOT = (138.43488, 55.46367)      # the corner past the start point, see above

txt = open(SRC, encoding="utf-8").read()
segs = [tuple(map(float, m.groups())) for m in re.finditer(
    r"\(gr_line \(start ([-\d.]+) ([-\d.]+)\) \(end ([-\d.]+) ([-\d.]+)\) \(layer Edge.Cuts\)", txt)]
assert len(segs) == 10700, len(segs)
assert not re.search(r"\(gr_(arc|circle|curve|poly)[^\n]*Edge\.Cuts", txt), "edge has non-line pieces"

# every end point must be shared by exactly two lines (no gaps, no T-junctions, no duplicates)
deg = collections.Counter()
for x1, y1, x2, y2 in segs:
    deg[(x1, y1)] += 1
    deg[(x2, y2)] += 1
assert set(deg.values()) == {2}, collections.Counter(deg.values())

# walk the lines into loops
adj = collections.defaultdict(list)
for i, (x1, y1, x2, y2) in enumerate(segs):
    adj[(x1, y1)].append(i)
    adj[(x2, y2)].append(i)
used = [False] * len(segs)
loops = []
for i in range(len(segs)):
    if used[i]:
        continue
    used[i] = True
    start, cur = segs[i][:2], segs[i][2:]
    pts = [start]
    while cur != start:
        pts.append(cur)
        j = next(k for k in adj[cur] if not used[k])
        used[j] = True
        s = segs[j]
        cur = s[2:] if s[:2] == cur else s[:2]
    loops.append(pts)
assert len(loops) == 1, f"{len(loops)} loops"
pts = loops[0]


def crossings(p):
    """Pairs of non-neighbouring edges that properly cross (grid-bucketed so 10,700 edges check fast)."""
    n = len(p)
    seg = [(p[k], p[(k + 1) % n]) for k in range(n)]
    g = 0.5
    grid = collections.defaultdict(list)
    for k, (a, b) in enumerate(seg):
        for gx in range(int(min(a[0], b[0]) / g), int(max(a[0], b[0]) / g) + 1):
            for gy in range(int(min(a[1], b[1]) / g), int(max(a[1], b[1]) / g) + 1):
                grid[(gx, gy)].append(k)

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    hits = set()
    for cell in grid.values():
        for x in range(len(cell)):
            for y in range(x + 1, len(cell)):
                i, j = cell[x], cell[y]
                if abs(i - j) <= 1 or abs(i - j) == n - 1:
                    continue
                (p1, p2), (p3, p4) = seg[i], seg[j]
                if cr(p3, p4, p1) * cr(p3, p4, p2) < 0 and cr(p1, p2, p3) * cr(p1, p2, p4) < 0:
                    hits.add((min(i, j), max(i, j)))
    return hits


before = crossings(pts)
print("self-crossings in the 2018 edge:", len(before))
assert len(before) == 1
k = pts.index(OVERSHOOT)
a, b, c = pts[k - 1], pts[k], pts[(k + 1) % len(pts)]
off = abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / math.dist(a, c)
print(f"dropping overshoot corner {b}: {math.dist(b, c) * 1000:.2f} um past the start, {off * 1000:.2f} um off the new line")
del pts[k]

# 10,700 lines of 16-27 micrometres each are far more corners than the shape needs, and they make KiCad's checks on the
# 2x2 panel run out of memory. Drop every corner that lies within TOL of the straight line between its neighbours that
# are kept (Douglas-Peucker), so the outline moves by at most TOL anywhere.
TOL = 0.001                              # mm (1 micrometre)


def simplify(p, tol):
    ring = p + [p[0]]
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = ring[i], ring[j]
        dx, dy = bx - ax, by - ay
        ll = math.hypot(dx, dy)
        best, bk = -1.0, None
        for k in range(i + 1, j):
            px, py = ring[k]
            d = abs(dx * (ay - py) - dy * (ax - px)) / ll if ll > 0 else math.hypot(px - ax, py - ay)
            if d > best:
                best, bk = d, k
        if bk is not None and best > tol:
            keep[bk] = True
            stack += [(i, bk), (bk, j)]
    return [q for q, k in zip(ring[:-1], keep[:-1]) if k]


_n = len(pts)
pts = simplify(pts, TOL)
print(f"corners: {_n} -> {len(pts)} (nothing moved more than {TOL * 1000:.0f} micrometre)")

out = []
for x, y in pts:
    q = [round(x, 4), round(y, 4)]
    if not out or q != out[-1]:
        out.append(q)
if out[0] == out[-1]:
    out.pop()
after = crossings([tuple(q) for q in out])
assert not after, after
area = sum(out[i][0] * out[(i + 1) % len(out)][1] - out[(i + 1) % len(out)][0] * out[i][1] for i in range(len(out))) / 2
xs, ys = [q[0] for q in out], [q[1] for q in out]
print(f"outline: {len(out)} corners, {abs(area):.1f} mm2, {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm, "
      f"x {min(xs):.2f}..{max(xs):.2f}, y {min(ys):.2f}..{max(ys):.2f}; no self-crossings")
json.dump({"outer": out, "holes": []}, open(OUT, "w"))
print("wrote", OUT)
