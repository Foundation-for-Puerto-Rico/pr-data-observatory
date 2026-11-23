"""Road network for the PR Data Observatory: routing that follows roads.

One artifact, two users:
  site/data/roads.bin   a compact directed graph of Puerto Rico's drivable roads, built here from the OpenStreetMap
                        extract (ODbL). The build uses it to snap every transit route to the roads, and the browser
                        route planner (site/js/roads.js) loads the same file to route between named places.
  python roads.py       rebuild roads.bin from the Geofabrik extract (needs `osmium`; a few minutes, local only).

The nightly refresh does not need the OpenStreetMap extract: it reads roads.bin.

File layout (little endian), coordinates in 1e-5 degree units (about 1.1 m):
  header   magic "PRRD", u32 version, u32 n_nodes, u32 n_edges, u32 n_shape
  nodes    n_nodes x (u32 x, u32 y)            x = (lon + 68) * 1e5, y = (lat - 17) * 1e5
  edges    n_edges x (u32 u, u32 v, u16 length_2m, u8 flags, u8 n_interior)   flags: bits 0-3 class, bit 4 one-way (u -> v only)
  shape    n_shape x (i16 dx, i16 dy)          interior points of every edge in order, each relative to the previous point
"""

import heapq
import math
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PBF_URL = "https://download.geofabrik.de/north-america/us/puerto-rico-latest.osm.pbf"
PBF = ROOT / "cache" / "roads" / "puerto-rico.osm.pbf"
BIN = ROOT / "site" / "data" / "roads.bin"
Q = 1e5
MAGIC = b"PRRD"

CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
           "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service", "busway"]
CLS = {c: i for i, c in enumerate(CLASSES)}
SPEED_KMH = [90, 55, 75, 45, 55, 40, 48, 35, 40, 30, 35, 25, 12, 12, 40]   # planning speeds: only the ratios between classes matter
SPEED_MS = [s / 3.6 for s in SPEED_KMH]
MAX_MS = max(SPEED_MS)
SKIP_SERVICE = {"driveway", "parking_aisle", "drive-through", "emergency_access"}


def hav(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(a))


# ── Build from OpenStreetMap ─────────────────────────────────────────────────

def _usable(tags):
    hw = tags.get("highway")
    if hw not in CLS:
        return None
    if hw == "service":
        return None   # driveways, parking lots and alleys: not bus routes, and they would add 40,000 edges
    if tags.get("access") in ("no", "private") and tags.get("bus") not in ("yes", "designated"):
        return None
    if tags.get("motor_vehicle") == "no" and tags.get("bus") not in ("yes", "designated"):
        return None
    if tags.get("vehicle") == "no" and tags.get("bus") not in ("yes", "designated"):
        return None
    return hw


def build_graph(pbf: Path):
    import osmium

    print("  reading the OpenStreetMap extract")
    import os
    here = os.getcwd()
    os.chdir(pbf.parent)   # libosmium cannot open paths with accented characters on Windows (this folder is under 'Pérez'), so open it by its bare name
    try:
        return _read_ways(osmium, pbf.name)
    finally:
        os.chdir(here)


def _read_ways(osmium, pbf_name):
    coord, cnt, ways = {}, {}, []
    fp = osmium.FileProcessor(pbf_name, osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(osmium.filter.KeyFilter("highway"))
    for w in fp:
        if not w.is_way():
            continue
        hw = _usable(w.tags)
        if not hw:
            continue
        refs = []
        for n in w.nodes:
            if not n.location.valid():
                continue
            refs.append(n.ref)
            coord[n.ref] = (n.lon, n.lat)
        if len(refs) < 2:
            continue
        ow = w.tags.get("oneway")
        if ow in ("yes", "true", "1"):
            d = 1
        elif ow in ("-1", "reverse"):
            d = -1
        elif ow == "no":
            d = 0
        else:
            d = 1 if (hw in ("motorway", "motorway_link") or w.tags.get("junction") in ("roundabout", "circular")) else 0
        for r in (refs[0], refs[-1]):
            cnt[r] = cnt.get(r, 0) + 2   # way ends are always graph nodes
        for r in refs[1:-1]:
            cnt[r] = cnt.get(r, 0) + 1
        ways.append((CLS[hw], d, refs))
    print(f"    {len(ways):,} road ways, {len(coord):,} nodes")

    # a node is a graph node when two or more ways meet there, or a way starts or ends there; the previous count already
    # added 2 for ends and 1 per use, so cnt >= 2 covers both cases
    node_id, nodes_xy = {}, []

    def nid(ref):
        i = node_id.get(ref)
        if i is None:
            i = node_id[ref] = len(nodes_xy)
            lon, lat = coord[ref]
            nodes_xy.append((round((lon + 68) * Q), round((lat - 17) * Q)))
        return i

    edges = []   # (u, v, cls, oneway, [(x, y) interior points])
    for cls, d, refs in ways:
        if d == -1:
            refs = refs[::-1]
        start = 0
        for i in range(1, len(refs)):
            if cnt[refs[i]] >= 2 or i == len(refs) - 1:
                seg = refs[start:i + 1]
                u, v = nid(seg[0]), nid(seg[-1])
                interior = [(round((coord[r][0] + 68) * Q), round((coord[r][1] - 17) * Q)) for r in seg[1:-1]]
                if u != v or interior:
                    edges.append((u, v, cls, 1 if d != 0 else 0, interior))
                start = i
    print(f"    {len(edges):,} edges between {len(nodes_xy):,} junctions")
    return _finish(nodes_xy, edges)


def _finish(nodes_xy, edges):
    """Drop consecutive duplicate points, simplify slightly, enforce the shape limits (int16 steps, 255 interior points)."""
    out = []
    nodes_xy = list(nodes_xy)
    for u, v, cls, ow, interior in edges:
        pts = [nodes_xy[u]] + interior + [nodes_xy[v]]
        # simplify: drop points closer than 2 units to the chord of their neighbours (about 2 m)
        keep = [pts[0]]
        for p in pts[1:-1]:
            a, b = keep[-1], pts[-1]
            dx, dy = b[0] - a[0], b[1] - a[1]
            l2 = dx * dx + dy * dy
            t = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
            if math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy)) > 2 and (p != keep[-1]):
                keep.append(p)
        keep.append(pts[-1])
        # break long steps and long edges
        full = [keep[0]]
        for p in keep[1:]:
            a = full[-1]
            n = max(1, math.ceil(max(abs(p[0] - a[0]), abs(p[1] - a[1])) / 30000))
            for k in range(1, n + 1):
                full.append((round(a[0] + (p[0] - a[0]) * k / n), round(a[1] + (p[1] - a[1]) * k / n)))
        chunks, cur_u = [], u
        while len(full) - 2 > 250:
            cut = full[251]
            nodes_xy.append(cut)
            w = len(nodes_xy) - 1
            out.append((cur_u, w, cls, ow, full[1:251]))
            full = full[251:]
            cur_u = w
        out.append((cur_u, v, cls, ow, full[1:-1]))
    return nodes_xy, out


def write_bin(nodes_xy, edges, path: Path):
    shape = bytearray()
    ebuf = bytearray()
    n_shape = 0
    for u, v, cls, ow, interior in edges:
        px, py = nodes_xy[u]
        for x, y in interior:
            shape += struct.pack("<hh", x - px, y - py)
            px, py = x, y
            n_shape += 1
        length = 0.0
        pts = [nodes_xy[u]] + interior + [nodes_xy[v]]
        for a, b in zip(pts, pts[1:]):
            length += hav(17 + a[1] / Q, a[0] / Q - 68, 17 + b[1] / Q, b[0] / Q - 68)
        ebuf += struct.pack("<IIHBB", u, v, min(65535, round(length / 2)), cls | (16 if ow else 0), len(interior))
    nbuf = b"".join(struct.pack("<II", x, y) for x, y in nodes_xy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MAGIC + struct.pack("<IIII", 1, len(nodes_xy), len(edges), n_shape) + nbuf + bytes(ebuf) + bytes(shape))
    print(f"  wrote {path.name}: {len(nodes_xy):,} nodes, {len(edges):,} edges, {n_shape:,} shape points, {path.stat().st_size / 1e6:.1f} MB")


# ── Load and route ───────────────────────────────────────────────────────────

class Roads:
    def __init__(self, path: Path = BIN):
        b = path.read_bytes()
        assert b[:4] == MAGIC, "not a roads.bin file"
        _, n_nodes, n_edges, n_shape = struct.unpack_from("<IIII", b, 4)
        off = 20
        nodes = np.frombuffer(b, dtype="<u4", count=n_nodes * 2, offset=off).reshape(-1, 2)
        off += n_nodes * 8
        edt = np.dtype([("u", "<u4"), ("v", "<u4"), ("len", "<u2"), ("flags", "u1"), ("n", "u1")])
        ed = np.frombuffer(b, dtype=edt, count=n_edges, offset=off)
        off += n_edges * 12
        sh = np.frombuffer(b, dtype="<i2", count=n_shape * 2, offset=off).reshape(-1, 2)
        self.lon = nodes[:, 0] / Q - 68
        self.lat = nodes[:, 1] / Q + 17
        self.n_nodes, self.n_edges = n_nodes, n_edges
        self.eu, self.ev = ed["u"].astype(np.int64), ed["v"].astype(np.int64)
        self.cls = (ed["flags"] & 15).astype(np.int64)
        self.oneway = (ed["flags"] & 16) != 0
        starts = np.concatenate([[0], np.cumsum(ed["n"].astype(np.int64))])
        # polylines as lists of (lon, lat), and cumulative metres
        self.poly, self.cum = [], []
        for i in range(n_edges):
            x, y = int(nodes[ed["u"][i], 0]), int(nodes[ed["u"][i], 1])
            pts = [(x, y)]
            for dx, dy in sh[starts[i]:starts[i + 1]]:
                x += int(dx)
                y += int(dy)
                pts.append((x, y))
            pts.append((int(nodes[ed["v"][i], 0]), int(nodes[ed["v"][i], 1])))
            ll = [(px / Q - 68, py / Q + 17) for px, py in pts]
            c = [0.0]
            for a, bb in zip(ll, ll[1:]):
                c.append(c[-1] + hav(a[1], a[0], bb[1], bb[0]))
            self.poly.append(ll)
            self.cum.append(c)
        self.adj = [[] for _ in range(n_nodes)]   # node -> [(neighbour, edge, forward?)]
        for i in range(n_edges):
            u, v = int(self.eu[i]), int(self.ev[i])
            self.adj[u].append((v, i, True))
            if not self.oneway[i]:
                self.adj[v].append((u, i, False))
        # grid index of shape points for snapping
        self.cell = 0.002
        self.grid = {}
        for i, ll in enumerate(self.poly):
            seen = set()
            for lon, lat in ll:
                k = (int(lon / self.cell), int(lat / self.cell))
                if k not in seen:
                    seen.add(k)
                    self.grid.setdefault(k, []).append(i)

    def _project(self, lon, lat, i):
        ll, c = self.poly[i], self.cum[i]
        kx = math.cos(math.radians(lat)) * 111320
        best = (1e18, 0, 0.0, ll[0])
        for j in range(len(ll) - 1):
            ax, ay = (ll[j][0] - lon) * kx, (ll[j][1] - lat) * 110574
            bx, by = (ll[j + 1][0] - lon) * kx, (ll[j + 1][1] - lat) * 110574
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = 0 if l2 == 0 else max(0, min(1, -(ax * dx + ay * dy) / l2))
            d = math.hypot(ax + t * dx, ay + t * dy)
            if d < best[0]:
                best = (d, j, t, (ll[j][0] + t * (ll[j + 1][0] - ll[j][0]), ll[j][1] + t * (ll[j + 1][1] - ll[j][1])))
        d, j, t, pt = best
        along = c[j] + t * (c[j + 1] - c[j])
        return {"edge": i, "dist": d, "along": along, "pt": pt, "seg": j}

    def snap(self, lon, lat, max_m=250):
        cx, cy = int(lon / self.cell), int(lat / self.cell)
        r = 1 if max_m <= 220 else 2 if max_m <= 450 else 3
        cand = set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                cand.update(self.grid.get((cx + dx, cy + dy), ()))
        best = None
        for i in cand:
            p = self._project(lon, lat, i)
            if best is None or p["dist"] < best["dist"]:
                best = p
        return best if best and best["dist"] <= max_m else None

    def route(self, a, b, limit_s=None):
        """Fastest path between two snapped points. Returns (seconds, [(lon, lat)...], metres) or None."""
        def spd(e):
            return SPEED_MS[self.cls[e]]
        total = lambda e: self.cum[e][-1]
        # same edge
        if a["edge"] == b["edge"]:
            e = a["edge"]
            fwd = b["along"] >= a["along"]
            if (fwd or not self.oneway[e]):
                lo, hi = sorted((a["along"], b["along"]))
                geo = self._slice(e, lo, hi, reverse=not fwd)
                return ((hi - lo) / spd(e), geo, hi - lo)
        starts = {}
        e = a["edge"]
        L = total(e)
        v, u = int(self.ev[e]), int(self.eu[e])
        starts[v] = ((L - a["along"]) / spd(e), ("start_f", e))
        if not self.oneway[e]:
            starts[u] = min(starts.get(u, (1e18, None)), (a["along"] / spd(e), ("start_b", e)))
        e2 = b["edge"]
        L2 = total(e2)
        tails = {int(self.eu[e2]): (b["along"] / spd(e2), "end_f")}
        if not self.oneway[e2]:
            tv = int(self.ev[e2])
            c = ((L2 - b["along"]) / spd(e2), "end_b")
            if tv not in tails or c[0] < tails[tv][0]:
                tails[tv] = c
        blat, blon = b["pt"][1], b["pt"][0]
        heap, dist, prev = [], {}, {}
        for n, (c, how) in starts.items():
            dist[n] = c
            prev[n] = (None, how)
            heapq.heappush(heap, (c + hav(self.lat[n], self.lon[n], blat, blon) / MAX_MS, c, n))
        best, best_node = 1e18, None
        while heap:
            f, d, n = heapq.heappop(heap)
            if d > dist.get(n, 1e18):
                continue
            if f >= best:
                break
            if n in tails and d + tails[n][0] < best:
                best, best_node = d + tails[n][0], n
            if limit_s and d > limit_s:
                continue
            for m, e, fwd in self.adj[n]:
                nd = d + self.cum[e][-1] / SPEED_MS[self.cls[e]]
                if nd < dist.get(m, 1e18):
                    dist[m] = nd
                    prev[m] = (n, (e, fwd))
                    heapq.heappush(heap, (nd + hav(self.lat[m], self.lon[m], blat, blon) / MAX_MS, nd, m))
        if best_node is None:
            return None
        # rebuild geometry
        edges_seq = []
        n = best_node
        while True:
            p, how = prev[n]
            if p is None:
                first = how
                break
            edges_seq.append(how)
            n = p
        edges_seq.reverse()
        geo = []
        kind, e0 = first
        if kind == "start_f":
            geo += self._slice(e0, a["along"], total(e0))
        else:
            geo += self._slice(e0, 0, a["along"], reverse=True)
        for e, fwd in edges_seq:
            seg = self.poly[e] if fwd else self.poly[e][::-1]
            geo += seg
        how = tails[best_node][1]
        if how == "end_f":
            geo += self._slice(e2, 0, b["along"])
        else:
            geo += self._slice(e2, b["along"], total(e2), reverse=True)
        out = [geo[0]]
        for p in geo[1:]:
            if p != out[-1]:
                out.append(p)
        length = sum(hav(p[1], p[0], q[1], q[0]) for p, q in zip(out, out[1:]))
        return best, out, length

    def _slice(self, e, lo, hi, reverse=False):
        ll, c = self.poly[e], self.cum[e]
        pts = []

        def at(s):
            for j in range(len(c) - 1):
                if c[j + 1] >= s:
                    t = 0 if c[j + 1] == c[j] else (s - c[j]) / (c[j + 1] - c[j])
                    return j, (ll[j][0] + t * (ll[j + 1][0] - ll[j][0]), ll[j][1] + t * (ll[j + 1][1] - ll[j][1]))
            return len(ll) - 2, ll[-1]
        j0, p0 = at(lo)
        j1, p1 = at(hi)
        pts.append(p0)
        for j in range(j0 + 1, j1 + 1):
            pts.append(ll[j])
        pts.append(p1)
        return pts[::-1] if reverse else pts


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PBF.exists():
        import requests
        PBF.parent.mkdir(parents=True, exist_ok=True)
        print("downloading the OpenStreetMap extract (about 74 MB)")
        r = requests.get(PBF_URL, headers={"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}, timeout=600)
        r.raise_for_status()
        PBF.write_bytes(r.content)
    nodes, edges = build_graph(PBF)
    write_bin(nodes, edges, BIN)


if __name__ == "__main__":
    main()
