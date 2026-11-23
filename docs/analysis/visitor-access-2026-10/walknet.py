"""A small walking-network engine used by the access spike.

A WalkNet is an undirected graph of edges (u, v, polyline in EPSG:32161 metres). Points (places, stops) are snapped to the nearest edge
(vectorised with shapely), and bounded Dijkstra gives network walking distance in metres:

    distance(place, stop) = connector(place -> edge) + path along the network + connector(edge -> stop)

Pedestrians ignore one-way rules; the caller decides which edges are walkable (e.g. drop motorways).
"""
from common import *
import heapq
import shapely
from shapely import STRtree, points, linestrings


class WalkNet:
    def __init__(self, eu, ev, geoms, n_nodes, label=""):
        self.label = label
        self.eu = np.asarray(eu, dtype=np.int64)
        self.ev = np.asarray(ev, dtype=np.int64)
        self.geoms = np.asarray(geoms, dtype=object)
        self.n_nodes = int(n_nodes)
        self.len = shapely.length(self.geoms)
        self.n_edges = len(self.eu)
        # CSR adjacency, both directions
        src = np.concatenate([self.eu, self.ev])
        dst = np.concatenate([self.ev, self.eu])
        w = np.concatenate([self.len, self.len])
        order = np.argsort(src, kind="stable")
        src, dst, w = src[order], dst[order], w[order]
        indptr = np.searchsorted(src, np.arange(self.n_nodes + 1))
        self.indptr = indptr.tolist()
        self.nbr = dst.tolist()
        self.w = w.tolist()
        self.tree = STRtree(self.geoms)

    # ---- snapping ---------------------------------------------------------------------------------------------
    def snap(self, x, y, max_m=150.0):
        """Returns arrays (edge, along_m, connector_m); edge = -1 when no edge within max_m."""
        pts = points(x, y)
        idx, d = self.tree.query_nearest(pts, max_distance=max_m, return_distance=True, all_matches=False)
        edge = np.full(len(x), -1, dtype=np.int64)
        along = np.zeros(len(x))
        conn = np.full(len(x), np.inf)
        edge[idx[0]] = idx[1]
        conn[idx[0]] = d
        sel = idx[0]
        along[sel] = shapely.line_locate_point(self.geoms[idx[1]], pts[sel])
        return edge, along, conn

    def registry(self, edge, along, conn, ids=None):
        """node -> list of (target id, offset to that node incl. connector); edge -> list of (id, along, connector)."""
        node_reg = defaultdict(list)
        edge_reg = defaultdict(list)
        ids = range(len(edge)) if ids is None else ids
        for k, e, a, c in zip(ids, edge.tolist(), along.tolist(), conn.tolist()):
            if e < 0:
                continue
            L = self.len[e]
            u, v = int(self.eu[e]), int(self.ev[e])
            node_reg[u].append((k, a + c))
            node_reg[v].append((k, L - a + c))
            edge_reg[e].append((k, a, c))
        return node_reg, edge_reg

    # ---- search ------------------------------------------------------------------------------------------------
    def search(self, e, a, c, bound, node_reg, edge_reg, want_nodes=False):
        """Bounded Dijkstra from a point on edge e at offset a (connector c). Returns {target id: metres} for targets within bound."""
        L = self.len[e]
        u, v = int(self.eu[e]), int(self.ev[e])
        dist = {}
        heap = []
        if a + c <= bound:
            dist[u] = a + c
            heap.append((a + c, u))
        if L - a + c <= bound:
            if v not in dist or L - a + c < dist[v]:
                dist[v] = L - a + c
            heap.append((L - a + c, v))
        heapq.heapify(heap)
        indptr, nbr, w = self.indptr, self.nbr, self.w
        best = {}
        # same edge
        for k, a2, c2 in edge_reg.get(e, ()):
            dd = abs(a - a2) + c + c2
            if dd <= bound and dd < best.get(k, 1e18):
                best[k] = dd
        settled = set()
        while heap:
            d, n = heapq.heappop(heap)
            if n in settled:
                continue
            settled.add(n)
            for k, off in node_reg.get(n, ()):
                dd = d + off
                if dd <= bound and dd < best.get(k, 1e18):
                    best[k] = dd
            for j in range(indptr[n], indptr[n + 1]):
                m = nbr[j]
                nd = d + w[j]
                if nd <= bound and nd < dist.get(m, 1e18):
                    dist[m] = nd
                    heapq.heappush(heap, (nd, m))
        if want_nodes:
            return best, len(settled)
        return best


def from_roads_bin(exclude_classes=(0, 1), keep_all=False):
    """WalkNet from site/data/roads.bin using the repository's roads.Roads loader. Motorways and motorway links are dropped for pedestrians."""
    sys.path.insert(0, str(REPO))
    import roads
    R = roads.Roads(DATA / "roads.bin")
    keep = np.ones(R.n_edges, bool) if keep_all else ~np.isin(R.cls, list(exclude_classes))
    ids = np.nonzero(keep)[0]
    # project every polyline vertex at once
    lens = np.array([len(R.poly[i]) for i in ids])
    flat = np.array([pt for i in ids for pt in R.poly[i]])
    x, y = to_xy(flat[:, 0], flat[:, 1])
    idx = np.repeat(np.arange(len(ids)), lens)
    geoms = linestrings(np.column_stack([x, y]), indices=idx)
    net = WalkNet(R.eu[ids], R.ev[ids], geoms, R.n_nodes, label="roads.bin" + ("" if keep_all else " (no motorways)"))
    net.cls = R.cls[ids]
    net.src_edge_ids = ids
    net.R = R
    return net
