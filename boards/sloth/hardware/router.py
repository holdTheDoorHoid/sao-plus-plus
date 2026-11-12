"""A small two-layer grid router (imported by build_board.py; KiCad 10 Python, needs numpy).

Copied from boards/knight-rider/hardware/router.py, with a hard cap added (DEADLINE: 5 minutes of CPU time, 20 minutes wall-clock): if routing takes
longer than that, it stops with an error instead of running on.

Clearance model: a cell is usable by net N if no copper of another net lies within (its own half-width + 0.15 mm
clearance + 0.15 mm worst-case half-width of the new track + 0.05 mm grid slack). DRC checks the real result.
"""
import heapq
import math
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

STEP = 0.1
CLR = 0.15
SLACK = 0.06
HW_MAX = 0.15                 # widest track half-width
VIA_R = 0.3                   # 0.6 mm via pad
B, F = 0, 1
START = time.time()
CPU0 = time.process_time()
DEADLINE = 300.0              # CPU seconds for the whole routing run; the build fails loudly past this
WALL_DEADLINE = 1200.0        # and a wall-clock backstop (the shared machine can be heavily loaded by other builds)


class Grid:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.W = int(round((x1 - x0) / STEP)) + 1
        self.H = int(round((y1 - y0) / STEP)) + 1
        self.owner = np.zeros((2, self.H, self.W), dtype=np.int32)      # 0 free, >0 net code, -1 blocked
        self.cost = np.ones((2, self.H, self.W), dtype=np.float32)
        self.noVia = np.zeros((self.H, self.W), dtype=bool)
        self.viaOnly = {}                                                   # net -> bool mask where its vias may not go
        xs = self.x0 + np.arange(self.W) * STEP
        ys = self.y0 + np.arange(self.H) * STEP
        self.X, self.Y = np.meshgrid(xs, ys)

    def ij(self, x, y):
        return int(round((x - self.x0) / STEP)), int(round((y - self.y0) / STEP))

    def xy(self, i, j):
        return round(float(self.x0 + i * STEP), 4), round(float(self.y0 + j * STEP), 4)

    def stamp(self, layer, mask, net):
        """Mark cells in mask as near copper of `net` (net 0 / -1 = hard block)."""
        o = self.owner[layer]
        if net <= 0:
            o[mask] = -1
            return
        free = mask & (o == 0)
        o[free] = net
        clash = mask & (o != net) & (o != 0)
        o[clash] = -1

    def seg_mask(self, a, b, r):
        ax, ay = a
        bx, by = b
        x0, x1 = min(ax, bx) - r, max(ax, bx) + r
        y0, y1 = min(ay, by) - r, max(ay, by) + r
        i0, j0 = self.ij(x0, y0)
        i1, j1 = self.ij(x1, y1)
        i0, j0 = max(i0 - 1, 0), max(j0 - 1, 0)
        i1, j1 = min(i1 + 1, self.W - 1), min(j1 + 1, self.H - 1)
        X = self.X[j0:j1 + 1, i0:i1 + 1]
        Y = self.Y[j0:j1 + 1, i0:i1 + 1]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        t = np.zeros_like(X) if L == 0 else np.clip(((X - ax) * dx + (Y - ay) * dy) / L, 0, 1)
        d = np.hypot(X - ax - t * dx, Y - ay - t * dy)
        m = np.zeros((self.H, self.W), dtype=bool)
        m[j0:j1 + 1, i0:i1 + 1] = d <= r
        return m

    def poly_mask(self, ps, grow):
        """Cells whose centre lies inside polygon set ps grown by `grow` mm."""
        g = pcbnew.SHAPE_POLY_SET(ps)
        if grow:
            g.Inflate(FromMM(grow), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, FromMM(0.005))
        bb = g.BBox()
        i0, j0 = self.ij(ToMM(bb.GetLeft()), ToMM(bb.GetTop()))
        i1, j1 = self.ij(ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        m = np.zeros((self.H, self.W), dtype=bool)
        for j in range(max(j0 - 1, 0), min(j1 + 2, self.H)):
            for i in range(max(i0 - 1, 0), min(i1 + 2, self.W)):
                x, y = self.xy(i, j)
                if g.Contains(VECTOR2I(FromMM(x), FromMM(y))):
                    m[j, i] = True
        return m


def route_net(g, net, targets, width, via_cost, max_vias=None):
    """targets: list of (layer, bool mask) for each pad. Returns list of paths [(layer, i, j), ...] or None."""
    hw = width / 2
    usable = [(g.owner[L] == 0) | (g.owner[L] == net) for L in (B, F)]
    via_ok = (usable[B] & usable[F] & ~g.noVia)
    # a via needs more room than a track: shrink the via-allowed area by the extra radius
    extra = int(math.ceil((VIA_R - HW_MAX) / STEP))
    if extra > 0:
        bad = ~via_ok
        from numpy.lib.stride_tricks import sliding_window_view  # noqa: F401
        pad = np.pad(bad, extra, constant_values=True)
        acc = np.zeros_like(bad)
        for dj in range(-extra, extra + 1):
            for di in range(-extra, extra + 1):
                if di * di + dj * dj <= extra * extra:
                    acc |= pad[extra + dj:extra + dj + g.H, extra + di:extra + di + g.W]
        via_ok = ~acc
    if net in g.viaOnly:
        via_ok &= ~g.viaOnly[net]
    # flat arrays (index = layer * H * W + j * W + i): plain Python lists are much faster to index than numpy here
    W_, H_ = g.W, g.H
    HW = W_ * H_
    ub = np.concatenate([usable[B].ravel(), usable[F].ravel()]).tolist()
    cost = np.concatenate([g.cost[B].ravel(), g.cost[F].ravel()]).astype(float).tolist()
    vok = via_ok.ravel().tolist()

    def cells(L, m):
        return [L * HW + int(k) for k in np.flatnonzero(m.ravel())]

    tree = set(cells(*targets[0]))
    remaining = list(range(1, len(targets)))
    paths = []
    nb = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    INFD = 1e18
    while remaining:
        goal = {}
        for k in remaining:
            for c in cells(*targets[k]):
                goal[c] = k
        dist = {}
        prev = {}
        h = []
        for s_ in tree:
            dist[s_] = 0.0
            h.append((0.0, s_))
        heapq.heapify(h)
        hit = None
        pops = 0
        while h:
            pops += 1
            if pops & 4095 == 0 and (time.process_time() - CPU0 > DEADLINE or time.time() - START > WALL_DEADLINE):
                raise RuntimeError(f"router: over the {DEADLINE:.0f} s CPU / {WALL_DEADLINE:.0f} s wall cap; stopping")
            d, s_ = heapq.heappop(h)
            if d > dist.get(s_, INFD):
                continue
            if s_ in goal:
                hit = s_
                break
            L, r = divmod(s_, HW)
            j, i = divmod(r, W_)
            base = L * HW
            for di, dj, c in nb:
                ii, jj = i + di, j + dj
                if ii < 0 or jj < 0 or ii >= W_ or jj >= H_:
                    continue
                t = base + jj * W_ + ii
                if not ub[t]:
                    continue
                if di and dj and not (ub[base + j * W_ + ii] and ub[base + jj * W_ + i]):
                    continue
                nd = d + c * cost[t]
                if nd < dist.get(t, INFD):
                    dist[t] = nd
                    prev[t] = s_
                    heapq.heappush(h, (nd, t))
            if vok[r]:
                t = (1 - L) * HW + r
                nd = d + via_cost
                if nd < dist.get(t, INFD):
                    dist[t] = nd
                    prev[t] = s_
                    heapq.heappush(h, (nd, t))
        if hit is None:
            return None
        path = [hit]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        for s_ in path:
            tree.add(s_)
        k = goal[hit]
        tree.update(cells(*targets[k]))
        remaining.remove(k)
        out = []
        for s_ in path:
            L, r = divmod(s_, HW)
            j, i = divmod(r, W_)
            out.append((L, i, j))
        paths.append(out)
    return paths


def simplify(g, path):
    """Path of grid cells -> (segments [(layer, (x,y), (x,y))], vias [(x,y)])."""
    segs, vias = [], []
    run = [path[0]]
    for s in path[1:]:
        if s[0] != run[-1][0]:
            if len(run) > 1:
                segs.append(run)
            vias.append(g.xy(s[1], s[2]))
            run = [s]
        else:
            run.append(s)
    if len(run) > 1:
        segs.append(run)
    out = []
    for r in segs:
        pts = [(r[0][1], r[0][2])]
        for k in range(1, len(r)):
            pts.append((r[k][1], r[k][2]))
        # keep only corners
        keep = [pts[0]]
        for k in range(1, len(pts) - 1):
            a, b, c = keep[-1], pts[k], pts[k + 1]
            if (b[0] - a[0]) * (c[1] - b[1]) != (b[1] - a[1]) * (c[0] - b[0]):
                keep.append(b)
        keep.append(pts[-1])
        L = r[0][0]
        for a, b in zip(keep, keep[1:]):
            out.append((L, g.xy(*a), g.xy(*b)))
    return out, vias
