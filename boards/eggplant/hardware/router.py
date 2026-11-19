"""A small two-layer grid router for build_board.py (KiCad 10's Python: needs numpy, not pcbnew).

Everything is routed on the back copper where it can be. Where a line cannot get past another on one layer, it may
drop through a tented via and cross on the FRONT, but only inside the area the build script allows there: the dark,
copper-covered body of the eggplant under solder mask (never the bare-gold stem and calyx, never the light stripe).
A front track costs several times a back track and every via costs a lot, so the router uses the front only where
it must.

  - The board is a grid of G = 0.1 mm cells on two layers (0 = front, 1 = back).
  - FIXED copper (pads, holes, keep-outs) is drawn into the grid once per layer and track class, grown by the
    clearance that class needs and labelled with its net. A cell is usable by net N if nothing of another net is
    too close. Class "via" is the via pad (0.6 mm), so a via may only stand where both layers allow it.
  - ROUTED copper is kept per net, so a net can be ripped up again.
  - A* (8 directions, a small penalty per turn, layer changes through vias) grows a net from everything it already
    has to the nearest pad of the net it does not reach yet, until all its pads are joined.
  - If a net cannot be routed, it is tried again treating other nets' routed copper as passable at a high price; the
    nets it crosses are ripped up and routed again afterwards. Capped by MAX_RIPUPS and TIME_LIMIT_S: it fails
    loudly instead of iterating for hours.
  - Paths are straightened where a straight line stays in usable cells.

Safety margin: a straight line between cell centres can pass up to G/2 closer to an obstacle than the centres do, so
every obstacle is grown by MARGIN = 0.06 mm extra. KiCad's rule check confirms the clearances afterwards.
"""
import heapq
import math
import os
import time

import numpy as np

G = 0.1
MARGIN = 0.06
MAX_RIPUPS = int(os.environ.get("EGG_RIPUPS", "40"))
TIME_LIMIT_S = 300
FRONT_COST = float(os.environ.get("EGG_FC", "6.0"))          # a front cell costs this many back cells
VIA_COST = float(os.environ.get("EGG_VC", "200.0"))           # a via costs this many back cells


def fill_polygon(mask, pts, x0, y0, value=True):
    """Even-odd scanline fill of a polygon (list of (x, y) mm) into a boolean grid whose cell (i, j) centre is at
    (x0 + j*G, y0 + i*G)."""
    ny, nx = mask.shape
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    xb, yb = np.roll(xs, -1), np.roll(ys, -1)
    i0 = max(0, int(math.floor((ys.min() - y0) / G)))
    i1 = min(ny - 1, int(math.ceil((ys.max() - y0) / G)))
    for i in range(i0, i1 + 1):
        y = y0 + i * G
        sel = (ys > y) != (yb > y)
        if not sel.any():
            continue
        xc = np.sort(xs[sel] + (y - ys[sel]) * (xb[sel] - xs[sel]) / (yb[sel] - ys[sel]))
        for a, b in zip(xc[0::2], xc[1::2]):
            j0 = max(0, int(math.ceil((a - x0) / G)))
            j1 = min(nx - 1, int(math.floor((b - x0) / G)))
            if j1 >= j0:
                mask[i, j0:j1 + 1] = value


class Router:
    def __init__(self, x0, y0, x1, y1, classes, via=(0.3, 0.2)):
        """classes: {name: (track half-width, clearance to other nets)}; via: (pad radius, clearance)."""
        self.x0, self.y0 = x0, y0
        self.nx = int(math.ceil((x1 - x0) / G)) + 1
        self.ny = int(math.ceil((y1 - y0) / G)) + 1
        self.classes = dict(classes)
        self.classes["via"] = via
        shp = (2, self.ny, self.nx)
        self.free = np.zeros(shp, bool)                               # where track centres may go, per layer
        self.owner = {c: np.full(shp, -1, np.int32) for c in self.classes}    # -1 free, -2 everyone, else net
        self.conflict = {c: np.zeros(shp, bool) for c in self.classes}       # two different nets too close
        self.routed = {}                                              # net -> [(layer, points, class)]
        self.vias = {}                                                # net -> [(x, y)]
        self.rmask = {}                                               # net -> {class: (2, ny, nx) bool}
        self.targets = {}                                             # net -> [(name, (2, ny, nx) bool)]
        self.Xs = x0 + np.arange(self.nx) * G
        self.Ys = y0 + np.arange(self.ny) * G
        self.failed = []
        self.via_block = np.zeros((self.ny, self.nx), bool)          # no via may stand here (under a part)

    # ---- geometry ---------------------------------------------------------------------------------
    def xy(self, i, j):
        return (round(self.x0 + j * G, 4), round(self.y0 + i * G, 4))

    def poly_mask(self, pts):
        m = np.zeros((self.ny, self.nx), bool)
        fill_polygon(m, pts, self.x0, self.y0)
        return m

    def disc_mask(self, c, r):
        return self.capsule_mask(c, c, r)

    def capsule_mask(self, a, b, r):
        xmin, xmax = min(a[0], b[0]) - r, max(a[0], b[0]) + r
        ymin, ymax = min(a[1], b[1]) - r, max(a[1], b[1]) + r
        j0, j1 = max(0, int((xmin - self.x0) / G)), min(self.nx, int((xmax - self.x0) / G) + 2)
        i0, i1 = max(0, int((ymin - self.y0) / G)), min(self.ny, int((ymax - self.y0) / G) + 2)
        X, Y = np.meshgrid(self.Xs[j0:j1], self.Ys[i0:i1])
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / L2, 0, 1) if L2 else 0
        d = np.hypot(X - (a[0] + t * dx), Y - (a[1] + t * dy))
        m = np.zeros((self.ny, self.nx), bool)
        m[i0:i1, j0:j1] = d <= r
        return m

    def grow_of(self, cls):
        half, clear = self.classes[cls]
        return half + clear + MARGIN

    # ---- set-up ------------------------------------------------------------------------------------
    def set_area(self, layer, pts_list):
        """Where track and via centres may go on a layer: the union of the given polygons."""
        for pts in pts_list:
            self.free[layer] |= self.poly_mask(pts)

    def add_fixed(self, layers, shapes_by_class, net):
        """shapes_by_class: {class: polygon points already grown for that class}; net = id, or -2 for a keep-out."""
        for c, pts in shapes_by_class.items():
            m = self.poly_mask(pts)
            for L in layers:
                own = self.owner[c][L]
                self.conflict[c][L] |= m & (own != -1) & (own != net)
                own[m & (own == -1)] = net

    def block_vias(self, pts):
        self.via_block |= self.poly_mask(pts)

    def add_target(self, net, name, layer, pts):
        m = np.zeros((2, self.ny, self.nx), bool)
        m[layer] = self.poly_mask(pts)
        self.targets.setdefault(net, []).append((name, m))

    # ---- routing -----------------------------------------------------------------------------------
    def usable(self, net, cls, soft=False):
        """(2, ny, nx) usable cells for this net's tracks of class cls, and the via-usable cells (ny, nx)."""
        def base(c, soft=soft):
            own = self.owner[c]
            ok = self.free & ~(self.conflict[c] & (own != net)) & ((own == -1) | (own == net))
            if not soft:
                for n2, by in self.rmask.items():
                    if n2 != net:
                        ok &= ~by[c]
            return ok
        trk = base(cls)
        v = base("via", soft=False)       # a via never lands on another net's copper, even when ripping up
        return trk, v[0] & v[1] & ~self.via_block

    def soft_cost(self, net, cls):
        cost = np.zeros((2, self.ny, self.nx), np.float32)
        who = {}
        for n2, by in self.rmask.items():
            if n2 != net:
                cost[by[cls]] += 60.0
                who[n2] = by[cls]
        return cost, who

    def _astar(self, sources, goal, usable, via_ok, extra=None):
        ny, nx = self.ny, self.nx
        gl, gi, gj = np.nonzero(goal)
        if len(gi) == 0:
            return None
        gc = (gi.mean(), gj.mean())
        dist = np.full((2, ny, nx), np.float32(1e30), np.float32)
        prev = np.full((2, ny, nx), -1, np.int64)
        pdir = np.full((2, ny, nx), -1, np.int8)
        heap = []
        sl, si, sj = np.nonzero(sources & (usable | goal))
        if len(si) == 0:
            sl, si, sj = np.nonzero(sources)
        for L, i, j in zip(sl, si, sj):
            dist[L, i, j] = 0
            heapq.heappush(heap, (math.hypot(i - gc[0], j - gc[1]) * 0.9, 0.0, int(L), int(i), int(j)))
        dirs = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
                (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
        expanded = 0
        lcost = (FRONT_COST, 1.0)
        while heap:
            f, g, L, i, j = heapq.heappop(heap)
            if g > dist[L, i, j]:
                continue
            if goal[L, i, j]:
                path = [(L, i, j)]
                k = prev[L, i, j]
                while k >= 0:
                    L2, r = divmod(int(k), ny * nx)
                    i2, j2 = divmod(r, nx)
                    path.append((L2, i2, j2))
                    k = prev[L2, i2, j2]
                return path[::-1]
            expanded += 1
            if expanded > 1500000:
                return None
            here = L * ny * nx + i * nx + j
            for k, (di, dj, w) in enumerate(dirs):
                a, b = i + di, j + dj
                if a < 0 or b < 0 or a >= ny or b >= nx or not (usable[L, a, b] or goal[L, a, b]):
                    continue
                c = g + w * lcost[L] + (0.4 if pdir[L, i, j] not in (-1, k) else 0.0)
                if extra is not None:
                    c += extra[L, a, b]
                if c < dist[L, a, b]:
                    dist[L, a, b] = c
                    prev[L, a, b] = here
                    pdir[L, a, b] = k
                    heapq.heappush(heap, (c + math.hypot(a - gc[0], b - gc[1]) * 0.9, c, L, a, b))
            if via_ok[i, j]:
                L2 = 1 - L
                if usable[L2, i, j] or goal[L2, i, j]:
                    c = g + VIA_COST
                    if c < dist[L2, i, j]:
                        dist[L2, i, j] = c
                        prev[L2, i, j] = here
                        pdir[L2, i, j] = -1
                        heapq.heappush(heap, (c + math.hypot(i - gc[0], j - gc[1]) * 0.9, c, L2, i, j))
        return None

    def _line_ok(self, ok, p, q):
        n = int(max(abs(p[0] - q[0]), abs(p[1] - q[1])) * 2) + 1
        for k in range(n + 1):
            t = k / n
            if not ok[int(round(p[0] + (q[0] - p[0]) * t)), int(round(p[1] + (q[1] - p[1]) * t))]:
                return False
        return True

    def _split(self, path):
        """Cell path -> runs of cells on one layer, and the via cells between them."""
        runs, vias = [], []
        cur = [path[0]]
        for a, b in zip(path, path[1:]):
            if b[0] != a[0]:
                runs.append(cur)
                vias.append((b[1], b[2]))
                cur = [b]
            else:
                cur.append(b)
        runs.append(cur)
        return runs, vias

    def _straighten(self, cells, ok):
        cells = [(i, j) for _, i, j in cells]
        out = [cells[0]]
        k = 0
        while k < len(cells) - 1:
            far = k + 1
            for m in range(len(cells) - 1, k + 1, -1):
                if self._line_ok(ok, cells[k], cells[m]):
                    far = m
                    break
            out.append(cells[far])
            k = far
        return out

    def _commit(self, net, cls, runs_pts, vias):
        rec = self.routed.setdefault(net, [])
        by = self.rmask.setdefault(net, {c: np.zeros((2, self.ny, self.nx), bool) for c in self.classes})
        for L, pts in runs_pts:
            rec.append((L, pts, cls))
            for c in self.classes:
                r = self.classes[cls][0] + self.classes[c][1] + self.classes[c][0] + MARGIN
                for a, b in zip(pts, pts[1:]):
                    by[c][L] |= self.capsule_mask(a, b, r)
                if len(pts) == 1:
                    by[c][L] |= self.disc_mask(pts[0], r)
        for v in vias:
            self.vias.setdefault(net, []).append(v)
            for c in self.classes:
                r = self.classes["via"][0] + self.classes[c][1] + self.classes[c][0] + MARGIN
                m = self.disc_mask(v, r)
                by[c][0] |= m
                by[c][1] |= m

    def route_net(self, net, cls, soft=False):
        usable, via_ok = self.usable(net, cls, soft)
        extra, who = (self.soft_cost(net, cls) if soft else (None, {}))
        tg = self.targets[net]
        joined = tg[0][1].copy()
        todo = list(range(1, len(tg)))
        crossed = set()
        while todo:
            goal = np.zeros_like(joined)
            for k in todo:
                goal |= tg[k][1]
            path = self._astar(joined, goal, usable, via_ok, extra)
            if path is None:
                return False, crossed
            hit = [k for k in todo if tg[k][1][path[-1]]][0]
            todo.remove(hit)
            runs, vias = self._split(path)
            runs_pts = []
            for run in runs:
                L = run[0][0]
                ok = usable[L] | joined[L] | tg[hit][1][L]
                cells = self._straighten(run, ok) if not soft else [(i, j) for _, i, j in run]
                runs_pts.append((L, [self.xy(i, j) for i, j in cells]))
            vias_xy = [self.xy(i, j) for i, j in vias]
            if soft:
                for n2, m in who.items():
                    if any(m[L, i, j] for L, i, j in path):
                        crossed.add(n2)
            self._commit(net, cls, runs_pts, vias_xy)
            line = np.zeros_like(joined)
            r = self.classes[cls][0] + G
            for L, pts in runs_pts:
                for a, b in zip(pts, pts[1:]):
                    line[L] |= self.capsule_mask(a, b, r)
                line[L] |= self.disc_mask(pts[0], r) | self.disc_mask(pts[-1], r)
            for v in vias_xy:
                m = self.disc_mask(v, r)
                line[0] |= m
                line[1] |= m
            joined |= tg[hit][1] | line
        return True, crossed

    def rip(self, net):
        self.routed.pop(net, None)
        self.rmask.pop(net, None)
        self.vias.pop(net, None)

    def route_all(self, order, names=None, strict=True):
        """order: list of (net, class). Raises RuntimeError naming what is unrouted if the caps are reached
        (strict), or leaves those nets out and lists them in self.failed (not strict: for looking at)."""
        names = names or {}
        nm = lambda n: names.get(n, n)
        t0 = time.time()
        queue = list(order)
        cls_of = dict(order)
        ripups = 0
        self.failed = []
        soft_nets = set()

        def fail(msg, rest):
            if strict:
                raise RuntimeError("router: " + msg)
            print("  router: " + msg)
            self.failed += rest

        while queue:
            if time.time() - t0 > TIME_LIMIT_S:
                fail(f"time limit reached; unrouted: {[nm(n) for n, _ in queue]}", [n for n, _ in queue])
                break
            net, cls = queue.pop(0)
            self.rip(net)
            ok, _ = self.route_net(net, cls)
            if ok:
                continue
            self.rip(net)
            ok, crossed = self.route_net(net, cls, soft=True)
            if not ok or ripups + len(crossed) > MAX_RIPUPS:
                self.rip(net)
                fail(f"cannot route {nm(net)}" + ("" if not ok else f" without ripping up {sorted(nm(c) for c in crossed)} (rip-up limit)"), [net])
                continue
            ripups += len(crossed)
            soft_nets.add(net)
            for n2 in crossed:
                self.rip(n2)
                queue.append((n2, cls_of[n2]))
            print(f"  router: {nm(net)} ripped up {sorted(nm(c) for c in crossed)}")
        # A net routed through others keeps its raw staircase path; now that the others have moved, route it again
        # the normal way (straightened), and keep the old path if that fails.
        for net in sorted(soft_nets):
            if net in self.failed:
                continue
            keep = (self.routed.get(net), self.vias.get(net), self.rmask.get(net))
            self.rip(net)
            ok, _ = self.route_net(net, cls_of[net])
            if not ok:
                self.rip(net)
                self.routed[net], self.vias[net], self.rmask[net] = keep
                if keep[1] is None:
                    self.vias.pop(net)
        nv = sum(len(v) for v in self.vias.values())
        print(f"  router: done in {time.time() - t0:.0f} s, {ripups} rip-ups, {nv} vias")
        return self.routed, self.vias
