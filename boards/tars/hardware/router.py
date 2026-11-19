"""A small two-layer grid router for TARS (imported by build_board.py; KiCad 10 Python, needs numpy).

Adapted from boards/knight-rider/hardware/router.py (same grid, clearance model and Dijkstra search). What is new here:
  - per-layer "allowed" masks: the front copper may only be used where the display glass hides it (and in a short
    landing strip into each touch area), and vias may only go under the glass
  - route_all(): negotiated congestion (the "PathFinder" idea): each net is routed against the fixed obstacles only,
    paying a growing price for running through another net's clearance; nets that still overlap are ripped up and
    routed again. Hard limits: MAX_PASSES passes and MAX_SECONDS wall-clock. If it does not settle it says so and
    returns the nets still in conflict (the build script then stops loudly).
Grid 0.1 mm, A* search. Every net is grown as a tree from its first pad. Deterministic.

Clearance model: a cell is usable by net N if no copper of another net lies within (its own half-width + 0.15 mm
clearance + 0.125 mm worst-case half-width of the new track + 0.03 mm grid slack). DRC checks the real result.
"""
import heapq
import math
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

STEP = 0.1
CLR = 0.15
SLACK = 0.03
HW_MAX = 0.125                # widest track half-width (power 0.25 mm)
VIA_R = 0.3                   # 0.6 mm via pad
B, F = 0, 1
MAX_PASSES = 30
MAX_SECONDS = 480


class Grid:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.W = int(round((x1 - x0) / STEP)) + 1
        self.H = int(round((y1 - y0) / STEP)) + 1
        self.owner = np.zeros((2, self.H, self.W), dtype=np.int32)      # 0 free, >0 net code, -1 blocked
        self.cost = np.ones((2, self.H, self.W), dtype=np.float32)
        self.noVia = np.zeros((self.H, self.W), dtype=bool)
        self.allowed = np.ones((2, self.H, self.W), dtype=bool)            # where each layer may carry copper at all
        self.netOnly = {}                                                   # (layer, net) -> extra cells only that net may use
        xs = self.x0 + np.arange(self.W) * STEP
        ys = self.y0 + np.arange(self.H) * STEP
        self.X, self.Y = np.meshgrid(xs, ys)

    def copy(self):
        g = Grid.__new__(Grid)
        g.x0, g.y0, g.W, g.H = self.x0, self.y0, self.W, self.H
        g.owner = self.owner.copy()
        g.cost = self.cost
        g.noVia = self.noVia
        g.allowed = self.allowed
        g.netOnly = self.netOnly
        g.X, g.Y = self.X, self.Y
        return g

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

    def rect(self, x0, y0, x1, y1):
        return (self.X >= x0) & (self.X <= x1) & (self.Y >= y0) & (self.Y <= y1)

    def disc(self, c, r):
        return (self.X - c[0]) ** 2 + (self.Y - c[1]) ** 2 <= r * r

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


def _dilate(bad, r):
    pad = np.pad(bad, r, constant_values=True)
    acc = np.zeros_like(bad)
    H, W = bad.shape
    for dj in range(-r, r + 1):
        for di in range(-r, r + 1):
            if di * di + dj * dj <= r * r:
                acc |= pad[r + dj:r + dj + H, r + di:r + di + W]
    return acc


def route_net(g, net, targets, width, via_cost, extra=None):
    """targets: list of (layer, bool mask) for each pad. Returns list of paths [(layer, i, j), ...] or None."""
    usable = []
    for L in (B, F):
        allow = g.allowed[L]
        only = g.netOnly.get((L, net))
        if only is not None:
            allow = allow | only
        usable.append(allow & ((g.owner[L] == 0) | (g.owner[L] == net)))
    via_ok = usable[B] & usable[F] & ~g.noVia
    grow = int(math.ceil((VIA_R - HW_MAX) / STEP))
    if grow > 0:
        via_ok = ~_dilate(~via_ok, grow)
    vextra = None
    if extra is not None:
        # a via's pad covers a disc, not a cell: charge it the worst congestion under that disc, on both layers
        both = extra[0] + extra[1]
        vextra = both.copy()
        r = int(math.ceil((VIA_R + 0.05) / STEP))
        H, W = both.shape
        pad = np.pad(both, r)
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                if di * di + dj * dj <= r * r:
                    np.maximum(vextra, pad[r + dj:r + dj + H, r + di:r + di + W], out=vextra)
    tree = {}
    L0, m0 = targets[0]
    for j, i in zip(*np.nonzero(m0)):
        tree[(L0, i, j)] = True
    remaining = list(range(1, len(targets)))
    paths = []
    nb = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    while remaining:
        goal = {}
        boxes = []
        for k in remaining:
            L, m = targets[k]
            js, is_ = np.nonzero(m)
            boxes.append((is_.min(), is_.max(), js.min(), js.max()))
            for j, i in zip(js, is_):
                goal[(L, i, j)] = k

        def hfun(i, j):
            # A* estimate: straight-line distance (in cells) to the nearest target's bounding box; every step costs >= 1
            best = 1e18
            for i0, i1, j0, j1 in boxes:
                dx = i0 - i if i < i0 else (i - i1 if i > i1 else 0)
                dy = j0 - j if j < j0 else (j - j1 if j > j1 else 0)
                best = min(best, math.hypot(dx, dy))
            return best

        dist = {}
        prev = {}
        h = []
        for s in tree:
            dist[s] = 0.0
            heapq.heappush(h, (hfun(s[1], s[2]), s))
        hit = None
        while h:
            f, s = heapq.heappop(h)
            d = dist[s]
            if f > d + hfun(s[1], s[2]) + 1e-6:
                continue
            if s in goal:
                hit = s
                break
            L, i, j = s
            for di, dj, c in nb:
                ii, jj = i + di, j + dj
                if not (0 <= ii < g.W and 0 <= jj < g.H) or not usable[L][jj, ii]:
                    continue
                if di and dj and not (usable[L][j, ii] and usable[L][jj, i]):
                    continue
                nd = d + c * (g.cost[L, jj, ii] if extra is None else g.cost[L, jj, ii] + extra[L, jj, ii])
                t = (L, ii, jj)
                if nd < dist.get(t, 1e18):
                    dist[t] = nd
                    prev[t] = s
                    heapq.heappush(h, (nd + hfun(ii, jj), t))
            if via_ok[j, i]:
                t = (1 - L, i, j)
                nd = d + via_cost + (0.0 if vextra is None else 8.0 * vextra[j, i])
                if nd < dist.get(t, 1e18):
                    dist[t] = nd
                    prev[t] = s
                    heapq.heappush(h, (nd + hfun(i, j), t))
        if hit is None:
            return None
        path = [hit]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        paths.append(path)
        for s in path:
            tree[s] = True
        k = goal[hit]
        Lk, mk = targets[k]
        for j, i in zip(*np.nonzero(mk)):
            tree[(Lk, i, j)] = True
        remaining.remove(k)
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
        pts = [(c[1], c[2]) for c in r]
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


def commit(g, net, segs, vias, width):
    """Stamp a routed net's copper into the grid so later nets keep clear of it."""
    inf = CLR + HW_MAX + SLACK
    for L, a, b in segs:
        g.stamp(L, g.seg_mask(a, b, width / 2 + inf), net)
    for c in vias:
        m = g.disc(c, VIA_R + inf)
        g.stamp(B, m, net)
        g.stamp(F, m, net)


def _footprint(g, segs, vias, width):
    """Cells this net's copper keeps other nets' track centres out of, per layer."""
    inf = CLR + HW_MAX + SLACK
    m = np.zeros((2, g.H, g.W), dtype=bool)
    for L, a, b in segs:
        m[L] |= g.seg_mask(a, b, width / 2 + inf)
    for c in vias:
        d = g.disc(c, VIA_R + inf)
        m[0] |= d
        m[1] |= d
    return m


def _centres(g, segs, vias):
    """Cells under this net's track centre lines and via pads (what must stay out of other nets' footprints)."""
    m = np.zeros((2, g.H, g.W), dtype=bool)
    for L, a, b in segs:
        m[L] |= g.seg_mask(a, b, 0.5 * STEP)
    for c in vias:
        d = g.disc(c, VIA_R - HW_MAX)
        m[0] |= d
        m[1] |= d
    return m


def route_all(base, order, targets_of, width_of, via_cost_of):
    """Negotiated-congestion routing (the PathFinder idea): every net is routed on the static obstacles only, with
    a growing penalty for running inside another net's clearance; nets that still overlap are ripped up and routed
    again. Hard limits MAX_PASSES and MAX_SECONDS. Returns (results {net: (segs, vias)}, failed nets, passes)."""
    t0 = time.time()
    order = list(order)
    hist = np.zeros((2, base.H, base.W), dtype=np.float32)
    foot, cent, res = {}, {}, {}
    pres = 1.0
    best = None
    todo = list(order)
    failed = []
    p = 0
    for p in range(1, MAX_PASSES + 1):
        failed = []
        for net in todo:
            res.pop(net, None)
            foot.pop(net, None)
            cent.pop(net, None)
            occ = np.zeros((2, base.H, base.W), dtype=np.float32)
            for n2, f in foot.items():
                occ += f
            extra = hist + pres * occ * 10.0
            paths = route_net(base, net, targets_of(net), width_of(net), via_cost_of(net), extra)
            if paths is None:
                failed.append(net)
                continue
            segs, vias = [], []
            for path in paths:
                s_, v_ = simplify(base, path)
                segs += s_
                vias += v_
            res[net] = (segs, vias)
            foot[net] = _footprint(base, segs, vias, width_of(net))
            cent[net] = _centres(base, segs, vias)
        # which nets still run through another net's clearance?
        bad = set()
        nets = list(res)
        over = np.zeros((2, base.H, base.W), dtype=bool)
        for a in nets:
            for b in nets:
                if a != b and (cent[a] & foot[b]).any():
                    bad.add(a)
                    over |= cent[a] & foot[b]
        hist[over] += 1.0
        print(f"  router pass {p}: {len(res)} routed, {len(bad)} overlapping, unroutable {failed}, {time.time() - t0:.0f} s")
        if not bad and not failed:
            return res, [], p
        if best is None or len(bad) + len(failed) < best[0]:
            best = (len(bad) + len(failed), {n: res[n] for n in res if n not in bad}, [n for n in order if n in bad or n in failed])
        if time.time() - t0 > MAX_SECONDS * 0.7:
            break
        pres *= 1.5
        # usually only the nets in conflict are ripped up; every third pass all of them are, so nets that are not in
        # conflict themselves can move out of the way
        if p % 3 == 0:
            todo = [n for n in order if n in bad or n in failed] + [n for n in order if n not in bad and n not in failed]
        else:
            todo = [n for n in order if n in bad or n in failed]
    # finishing: keep the best pass's clean nets as fixed copper and route the few left over strictly (no overlap
    # allowed), trying them in different orders until one fits or the time runs out
    _, keep, left = best
    print(f"  finishing: {len(keep)} nets fixed, {len(left)} to place strictly: {left}")
    import itertools
    tried = 0
    for perm in itertools.permutations(left):
        if time.time() - t0 > MAX_SECONDS or tried >= 120:
            break
        tried += 1
        g = base.copy()
        for n, (segs, vias) in keep.items():
            commit(g, n, segs, vias, width_of(n))
        out = dict(keep)
        ok = True
        for n in perm:
            paths = route_net(g, n, targets_of(n), width_of(n), via_cost_of(n))
            if paths is None:
                ok = False
                break
            segs, vias = [], []
            for path in paths:
                s_, v_ = simplify(g, path)
                segs += s_
                vias += v_
            commit(g, n, segs, vias, width_of(n))
            out[n] = (segs, vias)
        if ok:
            print(f"  finishing: all placed (order {tried}), {time.time() - t0:.0f} s")
            return out, [], p
    print(f"  finishing: no order of {tried} tried fits, {time.time() - t0:.0f} s")
    return dict(keep), list(left), p
