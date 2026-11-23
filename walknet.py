"""Walking distance along mapped roads, from the road file the site already publishes (site/data/roads.bin).

Promoted from the visitor-access study's prototype (docs/analysis/visitor-access-2026-10/walknet.py; method and checks in its REPORT.md,
section 4). A pedestrian may use every road in roads.bin except motorways and motorway links, in both directions (one-way rules are for
vehicles). Points (places, stops) are snapped to the nearest walkable road within SNAP_M, and

    walking distance = connector (point to road) + path along the roads + connector (road to point)

found with a bounded Dijkstra search from each stop. roads.bin holds no footways, paths, steps, sidewalks or crossings, so the result is
"along mapped roads": an estimate that cannot see shortcuts, fences or a road a pedestrian cannot cross. The study found the island share
within 400 m 0.4 point away from the one on a full OpenStreetMap walking network (26.6% against 27.0%).

Distances use the flat-earth metric of access.py (111,320 m per degree, longitude shortened by the cosine of the latitude), on a local
plane centred on Puerto Rico, so a walking distance and a straight-line distance from access.py are on one scale. Across the island the
plane differs from access.py's per-pair formula by under 0.3%; the caller keeps a walking distance from falling below the straight line.
"""
import heapq
import math
from pathlib import Path

import numpy as np
import shapely
from shapely import STRtree, linestrings, points

ROOT = Path(__file__).resolve().parent
ROADS_BIN = ROOT / "site" / "data" / "roads.bin"

M_PER_DEG = 111_320.0
LAT0, LON0 = 18.2, -66.5
COS0 = math.cos(math.radians(LAT0))
SNAP_M = 150.0               # a point farther than this from every walkable road is not on the network (the study: 1,095 of 26,579 places)
NO_WALK = ("motorway", "motorway_link")


def to_xy(lon, lat):
    """Metres on the local plane."""
    lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    return (lon - LON0) * M_PER_DEG * COS0, (lat - LAT0) * M_PER_DEG


class WalkNet:
    """An undirected graph of edges (u, v, polyline in local metres) with a spatial index for snapping."""

    def __init__(self, eu, ev, geoms, n_nodes):
        self.eu = np.asarray(eu, dtype=np.int64)
        self.ev = np.asarray(ev, dtype=np.int64)
        self.geoms = np.asarray(geoms, dtype=object)
        self.n_nodes = int(n_nodes)
        self.len = shapely.length(self.geoms)
        src = np.concatenate([self.eu, self.ev])
        dst = np.concatenate([self.ev, self.eu])
        w = np.concatenate([self.len, self.len])
        order = np.argsort(src, kind="stable")
        src, dst, w = src[order], dst[order], w[order]
        self.indptr = np.searchsorted(src, np.arange(self.n_nodes + 1)).tolist()
        self.nbr = dst.tolist()
        self.w = w.tolist()
        self.tree = STRtree(self.geoms)

    def snap(self, lon, lat, max_m=SNAP_M):
        """Arrays (edge, metres along it, connector metres); edge -1 when no walkable road is within max_m."""
        x, y = to_xy(lon, lat)
        pts = points(x, y)
        edge = np.full(len(x), -1, dtype=np.int64)
        along = np.zeros(len(x))
        conn = np.full(len(x), np.inf)
        if len(x):
            idx, d = self.tree.query_nearest(pts, max_distance=max_m, return_distance=True, all_matches=False)
            edge[idx[0]] = idx[1]
            conn[idx[0]] = d
            along[idx[0]] = shapely.line_locate_point(self.geoms[idx[1]], pts[idx[0]])
        return edge, along, conn

    def targets(self, edge, along, conn):
        """The snapped targets indexed for search: node -> [(target, metres to that node incl. connector)], edge -> [(target, along, connector)]."""
        node_reg, edge_reg = {}, {}
        for k, (e, a, c) in enumerate(zip(edge.tolist(), along.tolist(), conn.tolist())):
            if e < 0:
                continue
            u, v = int(self.eu[e]), int(self.ev[e])
            node_reg.setdefault(u, []).append((k, a + c))
            node_reg.setdefault(v, []).append((k, self.len[e] - a + c))
            edge_reg.setdefault(e, []).append((k, a, c))
        return node_reg, edge_reg

    def search(self, e, a, c, bound, node_reg, edge_reg):
        """Bounded Dijkstra from a point on edge e, `a` metres along it, `c` metres off it. Returns {target: metres} within bound."""
        best = {}
        for k, a2, c2 in edge_reg.get(e, ()):   # a target on the same edge: straight along it
            dd = abs(a - a2) + c + c2
            if dd <= bound and dd < best.get(k, math.inf):
                best[k] = dd
        u, v = int(self.eu[e]), int(self.ev[e])
        dist, heap = {}, []
        for n, d in ((u, a + c), (v, self.len[e] - a + c)):
            if d <= bound and d < dist.get(n, math.inf):
                dist[n] = d
                heap.append((d, n))
        heapq.heapify(heap)
        indptr, nbr, w = self.indptr, self.nbr, self.w
        settled = set()
        while heap:
            d, n = heapq.heappop(heap)
            if n in settled:
                continue
            settled.add(n)
            for k, off in node_reg.get(n, ()):
                dd = d + off
                if dd <= bound and dd < best.get(k, math.inf):
                    best[k] = dd
            for j in range(indptr[n], indptr[n + 1]):
                m, nd = nbr[j], d + w[j]
                if nd <= bound and nd < dist.get(m, math.inf):
                    dist[m] = nd
                    heapq.heappush(heap, (nd, m))
        return best


def from_roads(R):
    """A WalkNet from a roads.Roads, without motorways and motorway links."""
    import roads
    drop = [roads.CLS[c] for c in NO_WALK]
    ids = np.flatnonzero(~np.isin(R.cls, drop))
    lens = np.array([len(R.poly[i]) for i in ids])
    flat = np.array([pt for i in ids for pt in R.poly[i]])
    x, y = to_xy(flat[:, 0], flat[:, 1])
    geoms = linestrings(np.column_stack([x, y]), indices=np.repeat(np.arange(len(ids)), lens))
    return WalkNet(R.eu[ids], R.ev[ids], geoms, R.n_nodes)


def load(path=ROADS_BIN):
    """The walking network of the published road file, or None when the file is missing (the caller then publishes no walking fields)."""
    if not Path(path).exists():
        return None
    import roads
    return from_roads(roads.Roads(Path(path)))


def from_stops(net, stops, places, bound):
    """For each place, {stop index: walking metres} for the stops within `bound`, searching once from each snapped stop.

    Returns (per_place, place_snapped, stop_snapped): per_place[i] is a dict, place_snapped and stop_snapped are boolean arrays."""
    pe, pa, pc = net.snap([p["lng"] for p in places], [p["lat"] for p in places])
    se, sa, sc = net.snap([s["lng"] for s in stops], [s["lat"] for s in stops])
    node_reg, edge_reg = net.targets(pe, pa, pc)
    per_place = [dict() for _ in places]
    for j in range(len(stops)):
        if se[j] < 0:
            continue
        for i, d in net.search(int(se[j]), float(sa[j]), float(sc[j]), bound, node_reg, edge_reg).items():
            per_place[i][j] = d
    return per_place, pe >= 0, se >= 0


def walk_to_stops(net, stops, places, bound):
    """from_stops, plus the stops on no walkable road counted at their straight-line distance (access.py's formula, so the same stop gives the
    same metres as the straight line). Points are dicts with lat and lng. Returns (per_place, place_snapped, stop_snapped)."""
    per_place, place_ok, stop_ok = from_stops(net, stops, places, bound)
    lost = np.flatnonzero(~stop_ok)
    if len(lost) and len(places):
        plat = np.array([p["lat"] for p in places], dtype=float)
        plng = np.array([p["lng"] for p in places], dtype=float)
        for j in lost.tolist():
            s = stops[j]
            dy = (s["lat"] - plat) * M_PER_DEG
            dx = (s["lng"] - plng) * M_PER_DEG * np.cos(np.radians((plat + s["lat"]) / 2))
            d = np.sqrt(dx * dx + dy * dy)
            for i in np.flatnonzero(d <= bound).tolist():
                per_place[i][j] = min(per_place[i].get(j, math.inf), float(d[i]))
    return per_place, place_ok, stop_ok


def _piece(line, d0, d1):
    """The part of a line between d0 and d1 metres along it (in either order), as an (n, 2) array of local metres."""
    from shapely.ops import substring
    a, b = (d0, d1) if d0 <= d1 else (d1, d0)
    g = substring(line, a, b)
    xy = np.asarray(g.coords, dtype=float) if not g.is_empty else np.zeros((0, 2))
    return xy if d0 <= d1 else xy[::-1]


def nearest_paths(net, stops, places, bound):
    """For each place, the walk to its nearest stop along mapped roads within `bound`: (stop index, metres, [pieces]) or None.

    The same search as from_stops (a bounded Dijkstra from each snapped stop), keeping each node's parent, so the walk can be drawn: the pieces are (n, 2) arrays
    of local metres in walking order from the place to the stop, made of the place's connector, the part of its road, the whole roads between, the part of the
    stop's road and the stop's connector. Added for climb.py, which reads the ground's height along them. Places or stops on no walkable road get no walk here."""
    pe, pa, pc = net.snap([p["lng"] for p in places], [p["lat"] for p in places])
    se, sa, sc = net.snap([s["lng"] for s in stops], [s["lat"] for s in stops])
    px, py = to_xy([p["lng"] for p in places], [p["lat"] for p in places])
    sx, sy = to_xy([s["lng"] for s in stops], [s["lat"] for s in stops])
    node_reg, edge_reg = net.targets(pe, pa, pc)
    best = [None] * len(places)
    geoms, eu, ev, L = net.geoms, net.eu, net.ev, net.len
    indptr, nbr, w = net.indptr, net.nbr, net.w
    # the edge of each neighbour entry, to rebuild the walk: the entries are the edges sorted by their start (src), first as u->v then as v->u
    src = np.concatenate([eu, ev]); eid = np.concatenate([np.arange(len(eu)), np.arange(len(eu))])
    nbr_edge = eid[np.argsort(src, kind="stable")].tolist()

    def connector(x0, y0, line, along):
        p = shapely.line_interpolate_point(line, along)
        return np.array([[x0, y0], [p.x, p.y]])

    for j in range(len(stops)):
        e = int(se[j])
        if e < 0:
            continue
        a, c = float(sa[j]), float(sc[j])
        stop_conn = connector(sx[j], sy[j], geoms[e], a)[::-1]          # snapped point -> stop
        # targets on the stop's own edge
        for k, a2, c2 in edge_reg.get(e, ()):
            dd = abs(a - a2) + c + c2
            if dd <= bound and (best[k] is None or dd < best[k][1]):
                best[k] = (j, dd, [connector(px[k], py[k], geoms[e], a2), _piece(geoms[e], a2, a), stop_conn])
        u, v = int(eu[e]), int(ev[e])
        dist, par, heap, won = {}, {}, [], set()
        for n, d, start in ((u, a + c, 0.0), (v, L[e] - a + c, float(L[e]))):
            if d <= bound and d < dist.get(n, math.inf):
                dist[n], par[n] = d, (None, e, start)                     # reached from the stop along its own edge, from `start` metres to the stop's point
                heap.append((d, n))
        heapq.heapify(heap)
        settled = set()
        while heap:
            d, n = heapq.heappop(heap)
            if n in settled:
                continue
            settled.add(n)
            for k, off in node_reg.get(n, ()):
                dd = d + off
                if dd <= bound and (best[k] is None or dd < best[k][1]):
                    best[k] = (j, dd, n)                                 # rebuilt below, once the search of this stop is over
                    won.add(k)
            for t in range(indptr[n], indptr[n + 1]):
                m, nd = nbr[t], d + w[t]
                if nd <= bound and nd < dist.get(m, math.inf):
                    dist[m], par[m] = nd, (n, nbr_edge[t], None)
                    heapq.heappush(heap, (nd, m))
        # rebuild the walks this stop won: place -> its road -> node chain -> the stop's road -> stop
        for k in won:
            b = best[k]
            if b[0] != j or not isinstance(b[2], int):
                continue
            n = b[2]
            ke, ka = int(pe[k]), float(pa[k])
            pieces = [connector(px[k], py[k], geoms[ke], ka), _piece(geoms[ke], ka, 0.0 if int(eu[ke]) == n else float(L[ke]))]
            while True:
                prev, edge, start = par[n]
                if prev is None:                                          # the stop's own edge: from the node to the stop's point
                    pieces.append(_piece(geoms[edge], start, a))
                    break
                pieces.append(_piece(geoms[edge], 0.0, float(L[edge])) if int(eu[edge]) == n else _piece(geoms[edge], float(L[edge]), 0.0))
                n = prev
            pieces.append(stop_conn)
            best[k] = (j, b[1], pieces)
    return best
