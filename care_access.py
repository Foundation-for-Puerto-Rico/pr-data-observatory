"""Distance to care for the PR Data Observatory (Phase 3, item 9): how far residents live from the nearest health center site, along the roads, for the 78 municipalities and Puerto Rico.

    python care_access.py           # print the municipal figures (health_series.py publishes them; this is for checking)

Inputs:
  the permanent health center sites of HRSA's Health Center Service Delivery and Look-Alike Sites file (active, delivering care), as points. HRSA geocodes each site; the
      points are kept in the local cache only (cache/hrsa/site_points.pr.csv: longitude and latitude, nothing else) and are never published (owner decision, 2026-10-14):
      the observatory publishes figures for each municipality only.
  the census blocks with residents (cache/network/census_blocks_ids.json, written by network.py: id, 2020 residents, housing units, internal point).
  the road graph (site/data/roads.bin, roads.py).

Method. A multi-source shortest-path search from every site over the road graph, in both directions of every road (one-way streets are read as two-way: the figure is a
distance to care, not a driving route). Each block's internal point is snapped to the nearest road within 2 km; its distance is the road distance from that point to the
nearest site, plus the straight line from the block point to the road and from the site to the road. A block with no road within 2 km is left out and counted.
Drive time is the same search with the observatory's planning speeds for each road class (roads.py SPEED_KMH, free-flow speeds, no traffic, no stops): an estimate.
A municipality's figure is the average over its residents (each block weighted by its 2020 residents), so it describes where people live, not the area.
"""

import csv
import heapq
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "hrsa"
POINTS = CACHE / "site_points.pr.csv"
BLOCKS = ROOT / "cache" / "network" / "census_blocks_ids.json"
ROADS = ROOT / "site" / "data" / "roads.bin"
SNAP_M = 2000
NEAR_KM = 10   # the share of residents within this road distance of a site
SITES_URL = "https://data.hrsa.gov/DataDownload/DD_Files/Health_Center_Service_Delivery_and_LookAlike_Sites.csv"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
X, Y = "Geocoding Artifact Address Primary X Coordinate", "Geocoding Artifact Address Primary Y Coordinate"


def site_points(refresh=False, offline=False):
    """[(lon, lat)] of the permanent health center sites that deliver care in Puerto Rico. Only the two coordinates are cached: no name, address or other column."""
    if POINTS.exists() and not refresh:
        with POINTS.open(encoding="utf-8", newline="") as f:
            return [(float(r["lon"]), float(r["lat"])) for r in csv.DictReader(f)]
    if offline:
        raise SystemExit(f"care_access: {POINTS.name} is not in the cache (python care_series.py makes it; --check never downloads)")
    import requests
    pts = []
    with requests.get(SITES_URL, headers=UA, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        for row in csv.DictReader(io.TextIOWrapper(r.raw, encoding="utf-8-sig", errors="replace", newline="")):
            if (row["Site State Abbreviation"] == "PR" and row["Site Status Description"] == "Active" and "Service Delivery" in row["Health Center Type Description"]
                    and row["Health Center Location Type Description"] == "Permanent"):
                try:
                    lon, lat = float(row[X]), float(row[Y])
                except ValueError:
                    continue
                if -67.95 < lon < -65.2 and 17.85 < lat < 18.55:   # inside Puerto Rico
                    pts.append((round(lon, 5), round(lat, 5)))
    if len(pts) < 50:
        raise SystemExit(f"care_access: {len(pts)} permanent sites with a point (the 2026-10 file has about 127): read HRSA's file before publishing")
    CACHE.mkdir(parents=True, exist_ok=True)
    with POINTS.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["lon", "lat"])
        w.writerows(sorted(pts))
    return sorted(pts)


def blocks():
    """[(geoid, residents, lon, lat)] of the census blocks with residents."""
    d = json.loads(BLOCKS.read_text(encoding="utf-8"))
    i = {k: n for n, k in enumerate(d["fields"])}
    return [(r[i["geoid"]], r[i["pop"]], r[i["lon"]], r[i["lat"]]) for r in d["rows"] if r[i["pop"]] > 0]


def search(R, sources, weight):
    """Multi-source shortest paths over the road graph in both directions: {node: cost}. sources: [(snapped point, extra cost)]."""
    dist = {}
    heap = []
    for s, extra in sources:
        e = s["edge"]
        L = R.cum[e][-1]
        for node, along in ((int(R.eu[e]), s["along"]), (int(R.ev[e]), L - s["along"])):
            c = extra + weight(e, along)
            if c < dist.get(node, 1e18):
                dist[node] = c
                heapq.heappush(heap, (c, node))
    radj = {}
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, 1e18):
            continue
        for m, e, _ in R.adj[n] + radj.get(n, []):
            nd = d + weight(e, R.cum[e][-1])
            if nd < dist.get(m, 1e18):
                dist[m] = nd
                heapq.heappush(heap, (nd, m))
    return dist


def snap_reachable(R, lon, lat, reach, max_m=SNAP_M):
    """The nearest road within max_m whose ends have a path to a site: a block next to a small piece of road that the graph does not join to the network (a gated street, a gap in the
    map) is measured from the nearest road that is joined. None when there is none within max_m."""
    s = R.snap(lon, lat, max_m)   # the usual case: the nearest road is joined to the network
    if s and (int(R.eu[s["edge"]]) in reach or int(R.ev[s["edge"]]) in reach):
        return s
    cx, cy = int(lon / R.cell), int(lat / R.cell)
    r = 1 if max_m <= 220 else 2 if max_m <= 450 else 3 if max_m <= 700 else int(max_m / 220) + 1
    cand = set()
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            cand.update(R.grid.get((cx + dx, cy + dy), ()))
    best = None
    for i in cand:
        if int(R.eu[i]) not in reach and int(R.ev[i]) not in reach:
            continue
        p = R._project(lon, lat, i)
        if p["dist"] <= max_m and (best is None or p["dist"] < best["dist"]):
            best = p
    return best


def compute(refresh=False, offline=False):
    """{fips: (mean km, mean minutes, share within NEAR_KM km)} for each municipality and "72" for Puerto Rico, with notes."""
    import roads
    R = roads.Roads(ROADS)
    for i in range(len(R.eu)):   # both directions of a one-way road: a distance to care, not a driving route
        if R.oneway[i]:
            R.adj[int(R.ev[i])].append((int(R.eu[i]), i, False))
    pts = site_points(refresh, offline)
    snapped = [(R.snap(lon, lat, SNAP_M), lon, lat) for lon, lat in pts]
    src = [(s, s["dist"]) for s, _, _ in snapped if s]
    km = search(R, src, lambda e, m: m)
    sec = search(R, [(s, d / roads.SPEED_MS[R.cls[s["edge"]]]) for s, d in src], lambda e, m: m / roads.SPEED_MS[R.cls[e]])
    agg, notes = {}, {"sites": len(pts), "sites_snapped": len(src), "blocks": 0, "blocks_left_out": 0, "residents_left_out": 0}
    for geoid, pop, lon, lat in blocks():
        notes["blocks"] += 1
        s = snap_reachable(R, lon, lat, km)
        if not s:
            notes["blocks_left_out"] += 1
            notes["residents_left_out"] += pop
            lo = notes.setdefault("left_out_by_municipio", {})
            lo[geoid[:5]] = lo.get(geoid[:5], 0) + pop
            continue
        e, L = s["edge"], R.cum[s["edge"]][-1]
        u, v = int(R.eu[e]), int(R.ev[e])
        dk = s["dist"] + min(km.get(u, 1e18) + s["along"], km.get(v, 1e18) + L - s["along"])
        sp = roads.SPEED_MS[R.cls[e]]
        ds = s["dist"] / sp + min(sec.get(u, 1e18) + s["along"] / sp, sec.get(v, 1e18) + (L - s["along"]) / sp)
        if dk >= 1e17:   # no road path to a site: an island with no site of its own
            notes["blocks_left_out"] += 1
            notes["residents_left_out"] += pop
            lo = notes.setdefault("no_road_to_a_site_by_municipio", {})
            lo[geoid[:5]] = lo.get(geoid[:5], 0) + pop
            continue
        for f in (geoid[:5], "72"):
            a = agg.setdefault(f, [0, 0.0, 0.0, 0])
            a[0] += pop
            a[1] += pop * dk / 1000
            a[2] += pop * ds / 60
            a[3] += pop if dk / 1000 <= NEAR_KM else 0
    out = {f: (round(a[1] / a[0], 2), round(a[2] / a[0], 1), round(a[3] / a[0] * 100, 1)) for f, a in agg.items() if a[0]}
    return out, notes


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res, n = compute()
    print(n)
    for f in sorted(res):
        print(f, res[f])
