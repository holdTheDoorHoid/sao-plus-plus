"""A small two-layer grid router with rip-up and reroute, for build_board.py (KiCad 10's Python: needs numpy, not pcbnew).

Why this exists: the maker's 144-LED matrix is routed on both copper layers with 167 vias, and the new parts (the XIAO,
the SAO connector, the switch and the LiPo connector) land on top of some of his back-side tracks. Those tracks are
taken out, and the broken connections plus every new connection are routed here. Everything else of the maker's
routing is kept exactly as drawn and is never moved by this router.

How it works
  - The board is a grid of 0.05 mm cells on two layers (0 = front copper, 1 = back copper).
  - FIXED copper (pads, the maker's kept tracks and vias, edges, keep-outs) is drawn into the grid once, grown by the
    clearance a new track of each width class needs, and labelled with its net: a cell is usable by net N if no fixed
    copper of another net is too close.
  - ROUTED copper (what this router adds) is kept per net as "claims", so a net can be ripped up again.
  - A* finds a path from a net's connected group to the nearest other group of the same net, changing layer through a
    via where that is cheaper. If no path exists, it searches again treating other nets' routed copper as passable at
    a high cost; the nets that path crosses are ripped up and queued to be routed again (classic rip-up and reroute).
  - Paths are straightened (any angle) where the straight line stays in usable cells.

Safety margin: a straight line between cell centres can pass up to 0.048 mm closer to an obstacle than the cell
centres do. Every obstacle is grown by MARGIN = 0.05 mm extra, so routed copper always keeps at least the stated
clearance; KiCad's rule check confirms it afterwards.
"""
import heapq
import math

import numpy as np

G = 0.05
MARGIN = 0.05


class Grid:
    def __init__(self, x0, y0, x1, y1, classes, n_layers=2, layer_cost=None):
        """classes: {name: (half width of the copper this class places, clearance it keeps from other nets)}."""
        self.x0, self.y0 = x0, y0
        self.nx = int(math.ceil((x1 - x0) / G)) + 1
        self.ny = int(math.ceil((y1 - y0) / G)) + 1
        self.classes = dict(classes)
        self.nl = n_layers
        self.layer_cost = layer_cost or [1.0] * n_layers
        shp = (n_layers, self.ny, self.nx)
        # fixed copper, per class and layer: how many different nets are too close (0, 1, 2 = more / everyone) and which
        self.cnt = {c: np.zeros(shp, np.uint8) for c in classes}
        self.who = {c: np.full(shp, -1, np.int32) for c in classes}
        # routed copper: how many routed shapes claim each cell, per class (all nets together), and each net's own claims
        self.claim = {c: np.zeros(shp, np.int16) for c in classes}
        self.claims_of = {}                                # net -> [(cls, layer, (i0, i1, j0, j1), mask)]
        self.drill = np.zeros((self.ny, self.nx), np.int16)  # how many holes are too close for a new via's hole
        self.drills_of = {}                                # net -> [((i0, i1, j0, j1), mask)]
        self.hist = np.zeros(shp, np.float32)             # congestion history: cells fought over cost more each time
        self.xs = x0 + np.arange(self.nx) * G
        self.ys = y0 + np.arange(self.ny) * G

    # ---- coordinates ------------------------------------------------------------------------------
    def cell(self, x, y):
        return int(round((y - self.y0) / G)), int(round((x - self.x0) / G))

    def xy(self, i, j):
        return float(self.x0 + j * G), float(self.y0 + i * G)

    def window(self, xmin, ymin, xmax, ymax):
        i0 = max(0, int(math.floor((ymin - self.y0) / G)))
        i1 = min(self.ny, int(math.ceil((ymax - self.y0) / G)) + 1)
        j0 = max(0, int(math.floor((xmin - self.x0) / G)))
        j1 = min(self.nx, int(math.ceil((xmax - self.x0) / G)) + 1)
        return i0, i1, j0, j1

    # ---- shapes ---------------------------------------------------------------------------------------
    @staticmethod
    def d_segment(X, Y, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return np.hypot(X - ax, Y - ay)
        t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
        return np.hypot(X - (ax + t * dx), Y - (ay + t * dy))

    @staticmethod
    def d_rect(X, Y, cx, cy, hw, hh, ang_deg):
        """Distance to a rectangle whose own x axis points along (cos a, sin a) in board coordinates (y down)."""
        a = math.radians(ang_deg)
        c, s = math.cos(a), math.sin(a)
        u = (X - cx) * c + (Y - cy) * s
        v = -(X - cx) * s + (Y - cy) * c
        return np.hypot(np.maximum(np.abs(u) - hw, 0), np.maximum(np.abs(v) - hh, 0))

    def _mask(self, shape, grow):
        kind = shape[0]
        if kind == "seg":
            _, ax, ay, bx, by, hw = shape
            ext = hw + max(grow, 0)
            i0, i1, j0, j1 = self.window(min(ax, bx) - ext, min(ay, by) - ext, max(ax, bx) + ext, max(ay, by) + ext)
            X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
            return (i0, i1, j0, j1), self.d_segment(X, Y, ax, ay, bx, by) <= hw + grow
        if kind == "circle":
            _, cx, cy, r = shape
            ext = r + max(grow, 0)
            i0, i1, j0, j1 = self.window(cx - ext, cy - ext, cx + ext, cy + ext)
            X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
            return (i0, i1, j0, j1), np.hypot(X - cx, Y - cy) <= r + grow
        if kind == "rect":                    # ("rect", cx, cy, half w, half h, axis angle)
            _, cx, cy, hw, hh, ang = shape
            ext = math.hypot(hw, hh) + max(grow, 0)
            i0, i1, j0, j1 = self.window(cx - ext, cy - ext, cx + ext, cy + ext)
            X, Y = np.meshgrid(self.xs[j0:j1], self.ys[i0:i1])
            if grow < 0:
                return (i0, i1, j0, j1), self.d_rect(X, Y, cx, cy, max(hw + grow, 0.01), max(hh + grow, 0.01), ang) <= 1e-9
            return (i0, i1, j0, j1), self.d_rect(X, Y, cx, cy, hw, hh, ang) <= grow + 1e-9
        raise ValueError(kind)

    def grow_for(self, cls):
        half, clear = self.classes[cls]
        return half + clear + MARGIN

    # ---- fixed copper -------------------------------------------------------------------------------
    def add_fixed(self, shape, layers, net):
        """Fixed copper of `net` (an int >= 0, or -1 for 'blocks everyone') on the given layers."""
        for c in self.classes:
            (i0, i1, j0, j1), m = self._mask(shape, self.grow_for(c))
            for L in layers:
                cnt = self.cnt[c][L, i0:i1, j0:j1]
                who = self.who[c][L, i0:i1, j0:j1]
                if net < 0:
                    cnt[m] = 2
                    continue
                sub_c, sub_w = cnt[m], who[m]
                cnt[m] = np.where(sub_c == 0, 1, np.where(sub_w == net, sub_c, 2))
                who[m] = np.where(sub_c == 0, net, sub_w)

    def add_fixed_drill(self, cx, cy, r, hole_clear, new_drill_r):
        (i0, i1, j0, j1), m = self._mask(("circle", cx, cy, r), hole_clear + new_drill_r + MARGIN)
        self.drill[i0:i1, j0:j1] += m

    def base_free(self, cls, net):
        c, w = self.cnt[cls], self.who[cls]
        return (c == 0) | ((c == 1) & (w == net))

    # ---- routed copper (removable) --------------------------------------------------------------------
    def claim_shape(self, net, shape, layers):
        lst = self.claims_of.setdefault(net, [])
        for c in self.classes:
            (i0, i1, j0, j1), m = self._mask(shape, self.grow_for(c))
            for L in layers:
                self.claim[c][L, i0:i1, j0:j1] += m
                lst.append((c, L, (i0, i1, j0, j1), m))

    def claim_drill(self, net, cx, cy, r, hole_clear, new_drill_r):
        (i0, i1, j0, j1), m = self._mask(("circle", cx, cy, r), hole_clear + new_drill_r + MARGIN)
        self.drill[i0:i1, j0:j1] += m
        self.drills_of.setdefault(net, []).append(((i0, i1, j0, j1), m))

    def unclaim(self, net):
        for c, L, (i0, i1, j0, j1), m in self.claims_of.pop(net, []):
            self.claim[c][L, i0:i1, j0:j1] -= m
        for (i0, i1, j0, j1), m in self.drills_of.pop(net, []):
            self.drill[i0:i1, j0:j1] -= m

    def own_claim(self, cls, net):
        own = np.zeros((self.nl, self.ny, self.nx), np.int16)
        for c, L, (i0, i1, j0, j1), m in self.claims_of.get(net, []):
            if c == cls:
                own[L, i0:i1, j0:j1] += m
        return own

    def own_drill(self, net):
        own = np.zeros((self.ny, self.nx), np.int16)
        for (i0, i1, j0, j1), m in self.drills_of.get(net, []):
            own[i0:i1, j0:j1] += m
        return own

    def add_history(self, cls, cells, exclude, amount=float(__import__('os').environ.get('DONUT_HIST', '3'))):
        """Raise the cost of the path cells that other routed nets also wanted (and a little around them)."""
        others = (self.claim[cls] - self.own_claim(cls, exclude)) > 0
        for (L, i, j) in cells:
            if others[L, i, j]:
                h = self.hist[L, max(0, i - 3):i + 4, max(0, j - 3):j + 4]
                np.minimum(h + amount, 30.0, out=h)          # capped, so searches do not flood the whole board

    def nets_claiming(self, cls, cells, exclude):
        """Which routed nets claim any of the given (layer, i, j) cells, in class cls."""
        hit = set()
        for net, lst in self.claims_of.items():
            if net == exclude:
                continue
            for c, L, (i0, i1, j0, j1), m in lst:
                if c != cls:
                    continue
                for (l2, i, j) in cells:
                    if l2 == L and i0 <= i < i1 and j0 <= j < j1 and m[i - i0, j - j0]:
                        hit.add(net)
                        break
                if net in hit:
                    break
        return hit

    def cells_of(self, shape, layers, shrink=0.0):
        """Boolean array of the cells inside a shape (its own copper, optionally shrunk), per layer."""
        out = np.zeros((self.nl, self.ny, self.nx), bool)
        (i0, i1, j0, j1), m = self._mask(shape, -shrink)
        for L in layers:
            out[L, i0:i1, j0:j1] |= m
        return out

    # ---- search -----------------------------------------------------------------------------------
    def usable(self, cls, net, soft=False):
        """(free cells [2, ny, nx], free via cells [ny, nx], soft cells or None)."""
        base = self.base_free(cls, net)
        others = (self.claim[cls] - self.own_claim(cls, net)) > 0
        vbase = self.base_free("via", net)
        vothers = (self.claim["via"] - self.own_claim("via", net)) > 0
        drill_other = (self.drill - self.own_drill(net)) > 0
        own_drill = self.own_drill(net) > 0
        vfree = vbase.all(axis=0) & ~(drill_other | own_drill)       # vias go through every layer
        vo = vothers.any(axis=0)
        if soft:
            return base, vfree, others | vo[None, :, :]
        return base & ~others, vfree & ~vo, None

    def route(self, free, vfree, src, dst, soft=None, soft_cost=60.0, front_cost=1.4, via_cost=20.0,
              max_expand=4_000_000, h_weight=1.15, use_hist=True):
        """A* from any cell of src (bool [2, ny, nx]) to any cell of dst. Returns [(layer, i, j), ...] or None."""
        src = src & free
        dst = dst & free
        if not src.any() or not dst.any():
            return None
        tl, ti, tj = np.nonzero(dst)
        k = np.linspace(0, len(ti) - 1, min(len(ti), 96)).astype(int)
        I = np.arange(self.ny, dtype=np.float32)[:, None]
        J = np.arange(self.nx, dtype=np.float32)[None, :]
        h = np.full((self.ny, self.nx), np.inf, np.float32)
        for a in k:
            np.minimum(h, np.hypot(I - ti[a], J - tj[a]), out=h)
        h = (h.ravel() * h_weight).tolist()
        nx = self.nx
        N = nx * self.ny
        # bytes index far faster than numpy arrays in the inner loop. The grid's outer ring of cells is always
        # blocked (it lies outside the board), so neighbours never need a bounds check.
        nl = self.nl
        fb = tuple(free[k].tobytes() for k in range(nl))
        db = tuple(dst[k].tobytes() for k in range(nl))
        vb = vfree.tobytes() if vfree is not None else None
        sb = tuple(soft[k].tobytes() for k in range(nl)) if soft is not None else None
        hl = tuple(self.hist[k].ravel().tolist() for k in range(nl)) if use_hist and self.hist.any() else None
        cost_mul = tuple(self.layer_cost) if nl > 2 else (front_cost, 1.0)
        gbest = {}
        prev = {}
        heap = []
        for L, i, j in zip(*np.nonzero(src)):
            s = int(L) * N + int(i) * nx + int(j)
            gbest[s] = 0.0
            prev[s] = -1
            heap.append((h[s % N], 0.0, s))
        heapq.heapify(heap)
        D = 1.4142
        nbr = ((-nx, 1.0, 0, 0), (nx, 1.0, 0, 0), (-1, 1.0, 0, 0), (1, 1.0, 0, 0),
               (-nx - 1, D, -nx, -1), (-nx + 1, D, -nx, 1), (nx - 1, D, nx, -1), (nx + 1, D, nx, 1))
        n_exp = 0
        goal = None
        pop, push = heapq.heappop, heapq.heappush
        while heap:
            f, g, s = pop(heap)
            if g > gbest[s]:
                continue
            L, p = divmod(s, N)
            if db[L][p]:
                goal = s
                break
            n_exp += 1
            if n_exp > max_expand:
                break
            m = cost_mul[L]
            fl = fb[L]
            sl = sb[L] if sb is not None else None
            hh = hl[L] if hl is not None else None
            base = L * N
            for dq, c, a1, a2 in nbr:
                q = p + dq
                if not fl[q]:
                    continue
                if a1 and not (fl[p + a1] and fl[p + a2]):
                    continue                         # no corner cutting
                t = base + q
                ng = g + c * m
                if sl is not None and sl[q]:
                    ng += soft_cost
                if hh is not None:
                    ng += hh[q]
                if ng < gbest.get(t, 1e18):
                    gbest[t] = ng
                    prev[t] = s
                    push(heap, (ng + h[q], ng, t))
            if vb is not None and vb[p]:
                for L2 in range(nl):
                    if L2 == L or not fb[L2][p]:
                        continue
                    t = L2 * N + p
                    ng = g + via_cost
                    if ng < gbest.get(t, 1e18):
                        gbest[t] = ng
                        prev[t] = s
                        push(heap, (ng + h[p], ng, t))
        self.last_expanded = n_exp
        if goal is None:
            return None
        path = []
        s = goal
        while s != -1:
            L, p = divmod(s, N)
            path.append((L, p // nx, p % nx))
            s = prev[s]
        return path[::-1]

    # ---- turning a cell path into tracks ------------------------------------------------------------
    @staticmethod
    def clear_line(free_layer, a, b):
        (ia, ja), (ib, jb) = a, b
        n = int(max(abs(ib - ia), abs(jb - ja)) * 2) + 1
        for t in range(n + 1):
            if not free_layer[int(round(ia + (ib - ia) * t / n)), int(round(ja + (jb - ja) * t / n))]:
                return False
        return True

    def simplify(self, path, free):
        """Split at layer changes and straighten each run. Returns ([(layer, [(x, y), ...]), ...], [(x, y) vias])."""
        runs, vias = [], []
        cur = [path[0]]
        for st in path[1:]:
            if st[0] != cur[-1][0]:
                runs.append(cur)
                vias.append(self.xy(st[1], st[2]))
                cur = [st]
            else:
                cur.append(st)
        runs.append(cur)
        out = []
        for run in runs:
            L = run[0][0]
            pts = [(i, j) for _, i, j in run]
            keep = [0]
            a = 0
            while a < len(pts) - 1:
                b = a + 1
                while b + 1 < len(pts) and self.clear_line(free[L], pts[a], pts[b + 1]):
                    b += 1
                keep.append(b)
                a = b
            out.append((L, [self.xy(*pts[k]) for k in keep]))
        return out, vias
