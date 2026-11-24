"""Jobs within reach for the PR Data Observatory: how many jobs the residents of each municipio can reach within 30 and 45 minutes by road. HANDOFF decision 107,
step 9, fifth part (row derived-jobs-reach); docs/jobs-reach.md. An estimate (decision 107 b): a road-network model, labelled so, with a check and a range.

    python jobs_reach.py --refresh   # read the Census Bureau's commuting flows into cache/jobs_reach/, then build
    python jobs_reach.py             # build site/data/jobs_reach_series.json from the cache and the published files (no network)
    python jobs_reach.py --check     # rebuild and exit 1 when the published file is not what it gives (nothing written)

What it is made of:
  jobs       QCEW's jobs (all employers) by municipio, the newest year in economy_series.json. QCEW says how many jobs a municipio has, not where in it.
  where      each municipio's jobs are spread over its business places (the Overture places of cache/essentials, confidence 0.5 or more, each in the municipio
             whose outline holds it), so the jobs of San Juan sit in Hato Rey, Santurce and Río Piedras, not at one point. The range spreads them instead over
             where the municipio's residents live (2020 Census blocks). Nothing below the municipio is published: the places only tell the model where to start.
  time       the road graph the map uses (roads.bin, OpenStreetMap), one-way streets one way, at the observatory's planning speeds for each road class (roads.py
             SPEED_KMH): free flow, no traffic, no stops, no parking. A drive time, not a commute: a car is assumed.
  residents  each 2020 Census block with residents starts from its nearest road node joined to the network (within 2 km).
A municipio's figure is the average over its residents (each block weighted by its residents) of the jobs whose place is within 30 (and 45) minutes.
The check: the Census Bureau's commuting flows 2016-2020 (County-to-County, Table 1), the same as the commuting series: the share of workers whose
municipio of work is, in the model, within 45 minutes of their municipio of home, and how flows fall with drive time.
"""

import argparse
import collections
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "jobs_reach"
FLOWS = CACHE / "commuting_flows_2016_2020.xlsx"
FLOWS_URL = "https://www2.census.gov/programs-surveys/demo/tables/metro-micro/2020/commuting-flows-2020/table1.xlsx"
PLACES = ROOT / "cache" / "essentials" / "overture_pr_places.geojson"
PLACES_NPZ = CACHE / "business_points.npz"
OUT = DATA / "jobs_reach_series.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
MIN_CONF = 0.5
SNAP_M = 2000
LIMIT_S = 3600          # the search stops at an hour (the check needs times past 45 minutes)
THRESHOLDS = (30, 45)   # minutes
BATCH = 120
G = "Economy · Jobs within reach (estimate)"


def log(*a):
    print(*a, flush=True)


# ── inputs ───────────────────────────────────────────────────────────────────

def fetch_flows():
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    r = requests.get(FLOWS_URL, headers=UA, timeout=180)
    r.raise_for_status()
    FLOWS.write_bytes(r.content)
    log(f"  commuting flows: {len(r.content) / 1024:,.0f} KB")


def business_points():
    """(lon, lat) arrays of the Overture places with confidence MIN_CONF or more, cached as an npz the first time (the GeoJSON is about 120 MB)."""
    if PLACES_NPZ.exists():
        z = np.load(PLACES_NPZ)
        return z["lon"], z["lat"], str(z["release"])
    if not PLACES.exists():
        raise SystemExit(f"jobs_reach: {PLACES} is missing (python essentials.py --refresh downloads it)")
    lon, lat = [], []
    d = json.loads(PLACES.read_text(encoding="utf-8"))
    for f in d["features"]:
        p = f.get("properties") or {}
        if (p.get("confidence") or 0) < MIN_CONF or not f.get("geometry"):
            continue
        x, y = f["geometry"]["coordinates"][:2]
        lon.append(x)
        lat.append(y)
    state = PLACES.with_suffix(PLACES.suffix + ".state")
    release = json.loads(state.read_text(encoding="utf-8")).get("last_release", "") if state.exists() else ""
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(PLACES_NPZ, lon=np.array(lon), lat=np.array(lat), release=np.array(release))
    return np.array(lon), np.array(lat), release


def jobs_by_municipio():
    e = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))
    v = next(x for x in e["vars"] if x["key"] == "qcew_jobs")
    year = max(v["years"], key=int)
    ids = e["geo"]["ids"]
    return {ids[i]: int(n) for i, n in enumerate(v["years"][year]) if ids[i] != "72" and n is not None}, int(year)


def read_flows():
    import xlsx_read
    out = {}
    for r in xlsx_read.rows(FLOWS.read_bytes()):
        if r.get(8) is None or not str(r.get(0) or "").isdigit():
            continue
        if r[0] == "72" and r.get(4) == "072":
            n = r[8]
            out[("72" + r[1], "72" + r[5])] = int(float(n)) if n not in (None, "") else 0
    if len(out) < 1000:
        raise SystemExit(f"jobs_reach: {len(out)} flows inside Puerto Rico (about 2,300 in 2016-2020)")
    return out


# ── the graph ────────────────────────────────────────────────────────────────

def graph(R):
    """A directed CSR graph of drive time in seconds (one-way streets one way), and the node coordinates."""
    from scipy.sparse import csr_matrix
    import roads
    L = np.array([c[-1] for c in R.cum])
    t = L / np.array(roads.SPEED_MS)[R.cls]
    u, v = R.eu, R.ev
    two = ~R.oneway
    rows = np.concatenate([u, v[two]])
    cols = np.concatenate([v, u[two]])
    w = np.maximum(np.concatenate([t, t[two]]), 0.01)
    best = {}   # parallel roads between two nodes: the fastest (a sparse matrix would add them up)
    for a, b, c in zip(rows.tolist(), cols.tolist(), w.tolist()):
        k = (a, b)
        if k not in best or c < best[k]:
            best[k] = c
    a = np.array([k[0] for k in best])
    b = np.array([k[1] for k in best])
    c = np.array(list(best.values()))
    return csr_matrix((c, (a, b)), shape=(R.n_nodes, R.n_nodes))


def main_nodes(R):
    """The nodes of the network's large pieces (the main island, Vieques, Culebra), so a point is never placed on a road the network does not join."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    g = csr_matrix((np.ones(len(R.eu)), (R.eu, R.ev)), shape=(R.n_nodes, R.n_nodes))
    n, lab = connected_components(g, directed=False)
    size = np.bincount(lab)
    return np.isin(lab, np.flatnonzero(size >= 300)), lab


def snap(R, ok, lon, lat):
    """The nearest node of the joined network to each point, and its distance in metres (np.inf beyond SNAP_M)."""
    from scipy.spatial import cKDTree
    k = math.cos(math.radians(18.2)) * 111320
    idx = np.flatnonzero(ok)
    tree = cKDTree(np.c_[R.lon[idx] * k, R.lat[idx] * 110574])
    d, j = tree.query(np.c_[np.asarray(lon) * k, np.asarray(lat) * 110574])
    node = idx[j]
    d = np.where(d <= SNAP_M, d, np.inf)
    return node, d


# ── the model ────────────────────────────────────────────────────────────────

def reach(g, origins, dest_nodes, dest_w, muni_of_dest, munis):
    """For each origin node: the jobs within each threshold, and the job-weighted mean time to each municipio's jobs (capped at LIMIT_S)."""
    from scipy.sparse.csgraph import dijkstra
    dn = np.asarray(dest_nodes)
    dw = np.asarray(dest_w, dtype=float)
    mi = {m: i for i, m in enumerate(munis)}
    dm = np.array([mi[m] for m in muni_of_dest])
    mw = np.bincount(dm, weights=dw, minlength=len(munis))
    within = {t: np.zeros(len(origins)) for t in THRESHOLDS}
    tmun = np.zeros((len(origins), len(munis)))
    for s in range(0, len(origins), BATCH):
        o = origins[s:s + BATCH]
        D = dijkstra(g, directed=True, indices=o, limit=LIMIT_S)[:, dn]
        for t in THRESHOLDS:
            within[t][s:s + len(o)] = (D <= t * 60) @ dw
        Dc = np.where(np.isfinite(D), D, LIMIT_S)
        for i in range(len(munis)):
            sel = dm == i
            if mw[i] > 0:
                tmun[s:s + len(o), i] = (Dc[:, sel] @ dw[sel]) / mw[i]
        if s // BATCH % 20 == 0:
            log(f"    {s + len(o):,} of {len(origins):,} origins")
    return within, tmun


def spread(jobs, munis_of_pts, weights=None):
    """Each municipio's jobs shared over its points in proportion to weights (1 each by default): one weight per point."""
    w = np.ones(len(munis_of_pts)) if weights is None else np.asarray(weights, dtype=float)
    tot = collections.Counter()
    for m, x in zip(munis_of_pts, w):
        tot[m] += x
    return np.array([jobs.get(m, 0) * x / tot[m] if tot[m] else 0.0 for m, x in zip(munis_of_pts, w)])


def by_node(nodes, w):
    """Weights summed per node: (nodes, weights)."""
    acc = collections.defaultdict(float)
    for n, x in zip(nodes.tolist(), np.asarray(w).tolist()):
        acc[n] += x
    k = sorted(acc)
    return np.array(k), np.array([acc[n] for n in k])


def muni_of(lon, lat):
    import shapely
    from shapely.geometry import shape
    fc = json.loads((DATA / "municipios.geojson").read_text(encoding="utf-8"))
    polys = [shape(f["geometry"]) for f in fc["features"]]
    ids = [f["properties"].get("geoid") or f["properties"].get("GEOID") for f in fc["features"]]
    tree = shapely.STRtree(polys)
    pi, gi = tree.query(shapely.points(lon, lat), predicate="intersects")
    out = np.array([None] * len(lon), dtype=object)
    for p, g in zip(pi.tolist(), gi.tolist()):
        if out[p] is None:
            out[p] = ids[g]
    return out


def assemble():
    import network
    import roads
    jobs, year = jobs_by_municipio()
    munis = sorted(jobs)
    R = roads.Roads(DATA / "roads.bin")
    g = graph(R)
    ok, _ = main_nodes(R)
    table = network.load_block_table(ROOT / "cache" / "network", False)
    rows = [r for r in table["rows"] if r[1] > 0]
    b_lon = np.array([r[4] for r in rows])
    b_lat = np.array([r[5] for r in rows])
    b_pop = np.array([r[1] for r in rows], dtype=float)
    b_mun = np.array([r[0][:5] for r in rows])
    b_node, b_d = snap(R, ok, b_lon, b_lat)
    placed = np.isfinite(b_d)
    # destinations: jobs over business places (central) and over residents (range)
    p_lon, p_lat, release = business_points()
    p_mun = muni_of(p_lon, p_lat)
    keep = np.array([m in jobs for m in p_mun])
    p_lon, p_lat, p_mun = p_lon[keep], p_lat[keep], p_mun[keep]
    p_node, p_d = snap(R, ok, p_lon, p_lat)
    pk = np.isfinite(p_d)
    w_c = spread(jobs, p_mun[pk])
    dn_c, dw_c = by_node(p_node[pk], w_c)
    dm_c = node_muni(p_node[pk], p_mun[pk], dn_c)
    in_m = np.isin(b_mun, munis) & placed
    w_r = spread(jobs, b_mun[in_m], b_pop[in_m])
    dn_r, dw_r = by_node(b_node[in_m], w_r)
    dm_r = node_muni(b_node[in_m], b_mun[in_m], dn_r)
    # origins: the distinct nodes of the blocks with residents
    origins, inv = np.unique(b_node[placed], return_inverse=True)
    log(f"  {len(origins):,} origin nodes for {int(b_pop[placed].sum()):,} residents; {len(dn_c):,} job nodes from {int(pk.sum()):,} business places")
    wc, tm = reach(g, origins, dn_c, dw_c, dm_c, munis)
    wr, _ = reach(g, origins, dn_r, dw_r, dm_r, munis)
    pop = b_pop[placed]
    mun = b_mun[placed]
    res = {}
    for name, W in (("central", wc), ("residents", wr)):
        res[name] = {t: W[t][inv] for t in THRESHOLDS}
    return dict(jobs=jobs, year=year, munis=munis, pop=pop, mun=mun, res=res, tm=tm[inv], release=release,
                left_out=int(b_pop[~placed].sum()), places=int(pk.sum()), places_off=int((~pk).sum()), total=sum(jobs.values()))


def node_muni(nodes, munis_of_pts, uniq):
    """The municipio of each destination node: the one most of its weight comes from (a node on a border can hold two)."""
    c = collections.defaultdict(collections.Counter)
    for n, m in zip(nodes.tolist(), munis_of_pts.tolist()):
        c[n][m] += 1
    return [c[n].most_common(1)[0][0] for n in uniq.tolist()]


def weighted(vals, pop, groups, ids):
    out = []
    for m in ids:
        sel = groups == m
        w = pop[sel]
        out.append(float((vals[sel] * w).sum() / w.sum()) if w.sum() else None)
    return out


def check(A, flows):
    """The share of workers (between and within municipios) whose municipio of work is within 45 minutes of their home municipio in the model: the
    residents-weighted mean drive time from the home municipio's blocks to the work municipio's jobs."""
    munis, pop, mun, tm = A["munis"], A["pop"], A["mun"], A["tm"]
    mi = {m: i for i, m in enumerate(munis)}
    T = np.zeros((len(munis), len(munis)))
    for m in munis:
        sel = mun == m
        if sel.any():
            T[mi[m]] = (tm[sel] * pop[sel, None]).sum(0) / pop[sel].sum()
    bands = collections.Counter()
    tot = between = between_45 = all_45 = 0
    for (h, w), n in flows.items():
        if h not in mi or w not in mi or not n:
            continue
        t = T[mi[h], mi[w]] / 60
        tot += n
        all_45 += n if t <= 45 else 0
        if h != w:
            between += n
            between_45 += n if t <= 45 else 0
            bands["0-15" if t <= 15 else "15-30" if t <= 30 else "30-45" if t <= 45 else "45-60" if t < 60 else "60+"] += n
    return {"flows": "US Census Bureau, County-to-County Commuting Flows, ACS 2016-2020, Table 1", "workers_inside_pr": tot,
            "within_45_min_pct": round(all_45 / tot * 100, 1) if tot else None,
            "between_municipios": between, "between_within_45_min_pct": round(between_45 / between * 100, 1) if between else None,
            "between_by_drive_time_min": {k: bands[k] for k in ("0-15", "15-30", "30-45", "45-60", "60+")}}


def build(refresh=False, check_only=False):
    if refresh:
        fetch_flows()
    if not FLOWS.exists() or not (ROOT / "cache" / "network" / "census_blocks_ids.json").exists():
        log("jobs_reach: cache/jobs_reach or the census block table is missing (python jobs_reach.py --refresh); nothing built")
        return 1 if check_only else 0
    A = assemble()
    ids = A["munis"]
    pop, mun = A["pop"], A["mun"]
    isl = np.array(["72"] * len(pop))
    vals, notes_range = {}, {}
    for t in THRESHOLDS:
        c = A["res"]["central"][t]
        r = A["res"]["residents"][t]
        vals[t] = [None if v is None else int(round(v)) for v in weighted(c, pop, mun, ids)] + [int(round(weighted(c, pop, isl, ["72"])[0]))]
        notes_range[f"{t}_min"] = {"central": vals[t][-1], "jobs_over_residents": int(round(weighted(r, pop, isl, ["72"])[0]))}
    total = A["total"]
    year = date.today().year
    common = (f" An estimate: QCEW's {A['year']} jobs of each municipio, spread over its business places (Overture), reached over the mapped roads at free-flow "
              "planning speeds with a car, from where residents live (2020 Census blocks, each weighted by its residents). No traffic, parking or transit is assumed. "
              "QCEW counts jobs where they are, not who holds them, and leaves out the self-employed.")
    vars_ = []
    for t in THRESHOLDS:
        vars_.append({"key": f"jobs_reach_{t}", "group": G, "label": f"Jobs within {t} minutes by car (estimate)", "unit": "jobs", "d": 0, "type": "rate",
                      "sources": ["bls_qcew", "overture", "osm", "census_tiger"], "ref": REF,
                      "definition": f"The average number of jobs that the municipio's residents can reach within {t} minutes by car." + common,
                      "family": "jobs_reach", "counted": False, "noPerHU": True, "estimate": True, "years": {str(year): vals[t]}})
        vars_.append({"key": f"jobs_reach_{t}_pct", "group": G, "label": f"Share of Puerto Rico's jobs within {t} minutes by car (estimate, %)", "unit": "%", "d": 1, "type": "rate",
                      "sources": ["bls_qcew", "overture", "osm", "census_tiger"], "ref": REF,
                      "definition": f"The jobs the municipio's residents can reach within {t} minutes by car, on average, as a share of all of Puerto Rico's {total:,} jobs." + common,
                      "family": "jobs_reach", "counted": False, "noPerHU": True, "estimate": True,
                      "years": {str(year): [None if v is None else round(v / total * 100, 1) for v in vals[t]]}})
    flows = read_flows()
    notes = {"jobs_year": A["year"], "jobs_total": total, "overture_release": A["release"], "business_places": A["places"], "business_places_off_the_network": A["places_off"],
             "residents_not_placed": A["left_out"], "speeds_kmh": __import__("roads").SPEED_KMH, "range": notes_range,
             "range_rule": "the same model with each municipio's jobs spread over where its residents live instead of its business places",
             "check": check(A, flows)}
    doc = {"as_of": date.today().isoformat(), "years": [year], "geo": {"ids": [*ids, "72"], "names": names(ids) + ["Puerto Rico"]}, "vars": vars_, "sources": SOURCES, "notes": notes}
    if check_only:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    c = notes["check"]
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB): Puerto Rico {vals[30][-1]:,} jobs within 30 min, {vals[45][-1]:,} within 45 (range {notes_range})")
    log(f"  check: {c['within_45_min_pct']}% of workers inside Puerto Rico, {c['between_within_45_min_pct']}% of those between municipios, work within 45 min in the model; {c['between_by_drive_time_min']}")
    return 0


def names(ids):
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    nm = {r[0]: r[2] for r in cw["units"]["municipio"]}
    return [nm[i] for i in ids]


REF = ("Estimated by the observatory: QCEW jobs by municipio spread over Overture business places, reached by car over the OpenStreetMap road graph (roads.bin) "
       "at planning speeds from each 2020 Census block with residents (jobs_reach.py)")
SOURCES = {
    "bls_qcew": {"name": "BLS Quarterly Census of Employment and Wages (QCEW)", "url": "https://www.bls.gov/cew/", "license": "US Government work (no US copyright)",
             "note": "Jobs (all employers) by municipio, from economy_series.json."},
    "overture": {"name": "Overture Maps Foundation, Places theme", "url": "https://docs.overturemaps.org/guides/places/", "license": "CDLA Permissive 2.0 (some records ODbL); attribution",
                 "note": "Business places, used only to spread each municipio's jobs; no place is published."},
    "osm": {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "license": "ODbL 1.0", "note": "The road graph (roads.bin)."},
    "census_tiger": {"name": "US Census Bureau, 2020 Census blocks", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Where residents live: each block's 2020 residents and internal point."},
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read the commuting flows first")
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the published file")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return build(a.refresh, a.check)


if __name__ == "__main__":
    raise SystemExit(main())
