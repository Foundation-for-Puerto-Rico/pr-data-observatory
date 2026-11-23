"""Residents who can be cut off from every hospital for the PR Data Observatory: when the roads in FEMA's 1% annual chance flood area close, when the bridges in
poor condition (and those already closed) close, and both. By barrio and municipio. HANDOFF decision 107, step 9, third part (row derived-cut-off-communities);
docs/cutoff.md. An estimate (decision 107 b): a road-network model, labelled so, with a check and a range.

    python cutoff.py           # build site/data/cutoff_series.json and cutoff_barrio.json (no network: every input is in the repository or the block cache)
    python cutoff.py --check   # rebuild and exit 1 when a published file is not what it gives (nothing written)

What is closed:
  flood    every stretch of road whose points (one each 25 m along the road) fall in FEMA's 1% annual chance flood area (flood.geojson, SFHA), except
           - motorways and trunk roads and their ramps (OpenStreetMap classes): expressways stand on raised embankments built above the floods, so they stay open;
           - the span of a bridge in good or fair condition (the National Bridge Inventory's point, half the bridge's length and 15 m either side): a sound bridge
             carries the road over the water.
  bridges  the road under the point of every bridge the National Bridge Inventory rates in poor condition, or lists as closed (status K), within 60 m.
  both     the two together.
Who is cut off: each 2020 Census block with residents is placed on its nearest road (within 2 km, on a road joined to the island's network) and is cut off when,
with those stretches closed, no open road leads from it to a hospital. A block whose own stretch of road is closed is cut off too: its street is under water. The
hospitals are the ones in the observatory's place index from OpenStreetMap (gazetteer.json) whose name says hospital or medical centre (conditions.py's rule): 73 on
2026-11-20. Vieques and Culebra have no road to a hospital with nothing closed (their health centres are not hospitals by that rule), so they are left out and
counted in the notes; the barrios with no residents have no value.

The range: low, the same model with primary roads also kept open; high, the 0.2% annual chance area closed too and every road class closed. The check: the
communities of the Whole Community Resilience Planning program (WCRP) whose plans say floods or a failing bridge leave them cut off (incomunicada), against the
others (notes.check).

It is a worst case: the 1% flood everywhere at once, every road in the flood area closed for its whole length. In a real storm only some rivers rise, the water
stays a few hours and some flooded roads can still be crossed. It says which communities depend on roads that can flood, not how many will be cut off in any one
storm. Landslides, fallen trees and power lines are not in the model.
"""

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT_SERIES = DATA / "cutoff_series.json"
OUT_BARRIO = DATA / "cutoff_barrio.json"
STEP_M = 25.0          # one test point every 25 m along each road
HALF_STEP = STEP_M / 2
BRIDGE_SNAP_M = 60     # a bridge's point to the road it carries
BRIDGE_PAD_M = 15      # added on each side of a sound bridge's half length
NETWORK_MIN_M = 20000  # a piece of the road graph this long is a network (the main island, Vieques, Culebra); smaller pieces are gaps in the map
RAISED = (0, 1, 2, 3)  # roads.CLASSES: motorway, motorway_link, trunk, trunk_link
PRIMARY = (4, 5)       # primary, primary_link: also kept open at the low end of the range
G = "Hazards · Cut off from hospitals (estimate)"
REF = ("Estimated by the observatory: the OpenStreetMap road graph (roads.bin) with the roads in FEMA's flood area or under bridges in poor condition closed, "
       "and each 2020 Census block tested for an open road to a hospital (cutoff.py)")
COMMON = (" An estimate and a worst case: the 1% flood everywhere at once and every flooded stretch closed, where a real storm raises only some rivers for a few "
          "hours. Expressways and sound bridges stay open. Landslides and fallen trees are not in the model. Vieques and Culebra, with no road to a hospital at all, "
          "are left out.")
SOURCES = {
    "osm": {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "license": "ODbL 1.0",
            "note": "The road graph (roads.bin) and the hospitals of the place index (gazetteer.json)."},
    "fema_nfhl": {"name": "FEMA National Flood Hazard Layer", "url": "https://www.fema.gov/flood-maps/national-flood-hazard-layer", "license": "US Government work (no US copyright)",
                  "note": "The 1% and 0.2% annual chance flood areas (flood.geojson)."},
    "fhwa_nbi": {"name": "FHWA National Bridge Inventory", "url": "https://www.fhwa.dot.gov/bridge/nbi.cfm", "license": "US Government work (no US copyright)",
                 "note": "Each bridge's point, condition, operating status and length (bridges.geojson)."},
    "census_tiger": {"name": "US Census Bureau, 2020 Census blocks and barrio outlines", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Where residents live: each block's 2020 residents and internal point."},
}
# the WCRP communities whose plans (searched 2026-11-20) say floods or a failing bridge leave them cut off; Buena Vista (Humacao) is left out: its plan names landslides
WCRP_SAY_CUT_OFF = ("La Vega", "Mariana", "Punta Santiago", "Punta Tuna", "Río Blanco", "Tropical Beach", "Tumbao", "Verde Mar")
WCRP_RADIUS_M = 800


def log(*a):
    print(*a, flush=True)


# ── the closures ─────────────────────────────────────────────────────────────

def samples(R):
    """Points every STEP_M along every edge: (lon, lat, edge, metres along the edge), as arrays."""
    ex, ey, ee, ea = [], [], [], []
    for i, (ll, c) in enumerate(zip(R.poly, R.cum)):
        L = c[-1]
        n = max(1, int(L // STEP_M))
        for k in range(n):
            s = (k + 0.5) * L / n
            j = min(int(np.searchsorted(c, s, side="right")) - 1, len(ll) - 2)
            t = 0.0 if c[j + 1] == c[j] else (s - c[j]) / (c[j + 1] - c[j])
            ex.append(ll[j][0] + t * (ll[j + 1][0] - ll[j][0]))
            ey.append(ll[j][1] + t * (ll[j + 1][1] - ll[j][1]))
            ee.append(i)
            ea.append(s)
    return np.array(ex), np.array(ey), np.array(ee, dtype=np.int64), np.array(ea)


def bridge_sets(R, fc):
    """({edge: [(from m, to m)]} spans of the sound bridges, {edge: [m]} points of the bridges in poor condition or closed, counts)."""
    spans, bad = collections.defaultdict(list), collections.defaultdict(list)
    n = collections.Counter()
    for f in fc["features"]:
        p = f["properties"]
        if p.get("type") == "Tunnel" or not f.get("geometry"):
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        poor = p.get("c") == "P" or p.get("o") == "K"
        sound = p.get("c") in ("G", "F") and p.get("o") != "K"
        if not (poor or sound):
            continue
        s = R.snap(lon, lat, BRIDGE_SNAP_M)
        kind = "poor_or_closed" if poor else "sound"
        n[kind] += 1
        if not s:
            n[kind + "_no_road"] += 1
            continue
        if poor:
            bad[s["edge"]].append(s["along"])
        else:
            h = (p.get("l") or 20) / 2 + BRIDGE_PAD_M
            spans[s["edge"]].append((s["along"] - h, s["along"] + h))
    return spans, bad, dict(n)


def flood_closures(R, smp, inside, spans, keep=RAISED):
    """{edge: [metres along it of each closed test point]}: the test points inside the flood area, except on the kept road classes and on sound bridges."""
    _, _, ee, ea = smp
    out = collections.defaultdict(list)
    for e, a in zip(ee[inside].tolist(), ea[inside].tolist()):
        if R.cls[e] in keep or any(lo <= a <= hi for lo, hi in spans.get(e, ())):
            continue
        out[e].append(a)
    return out


def merge(*ds):
    out = collections.defaultdict(list)
    for d in ds:
        for k, v in d.items():
            out[k] += v
    return out


# ── reachability ─────────────────────────────────────────────────────────────

def pieces(R, closed):
    """The connected piece of every node with the edges in `closed` removed (union-find, roads read in both directions)."""
    p = np.arange(R.n_nodes)

    def find(x):
        r = x
        while p[r] != r:
            r = p[r]
        while p[x] != r:
            p[x], x = r, p[x]
        return r
    for i in range(R.n_edges):
        if i in closed:
            continue
        a, b = find(int(R.eu[i])), find(int(R.ev[i]))
        if a != b:
            p[a] = b
    return np.array([find(i) for i in range(R.n_nodes)])


def ends_open(s, closed):
    """(the u end, the v end) of a point's edge that it can reach along its own edge: no closed test point between it and that end."""
    pos = closed.get(s["edge"])
    if not pos:
        return True, True
    a = s["along"]
    return all(q > a + HALF_STEP for q in pos), all(q < a - HALF_STEP for q in pos)


def reached(R, s, root, good, closed):
    """Whether the snapped point s has an open road to a node whose piece is in `good`."""
    u_ok, v_ok = ends_open(s, closed)
    return (u_ok and root[int(R.eu[s["edge"]])] in good) or (v_ok and root[int(R.ev[s["edge"]])] in good)


def cut_off(R, block_snaps, hosp_snaps, closed):
    """Boolean per block: no open road to any hospital (False for a block that could not be placed on a road), and per block whether its own stretch is closed."""
    root = pieces(R, closed)
    good = set()
    for h in hosp_snaps:
        u_ok, v_ok = ends_open(h, closed)
        if u_ok:
            good.add(root[int(R.eu[h["edge"]])])
        if v_ok:
            good.add(root[int(R.ev[h["edge"]])])
    cut = np.zeros(len(block_snaps), dtype=bool)
    wet = np.zeros(len(block_snaps), dtype=bool)
    for k, s in enumerate(block_snaps):
        if s is None:
            continue
        cut[k] = not reached(R, s, root, good, closed)
        u_ok, v_ok = ends_open(s, closed)
        wet[k] = not u_ok and not v_ok
    return cut, wet


def network_snaps(R, pts):
    """Each point's nearest road joined to a network piece (care_access.snap_reachable), or None."""
    import care_access
    root = pieces(R, set())
    length = collections.Counter()
    for i in range(R.n_edges):
        length[root[int(R.eu[i])]] += R.cum[i][-1]
    reach = {n for n in range(R.n_nodes) if length[root[n]] >= NETWORK_MIN_M}
    out = []
    for lon, lat in pts:
        s = R.snap(lon, lat, care_access.SNAP_M)
        if not s or int(R.eu[s["edge"]]) not in reach:
            s = care_access.snap_reachable(R, lon, lat, reach)
        out.append(s)
    return out


# ── the model ────────────────────────────────────────────────────────────────

def model(R, blocks, hospitals, flood_fc, bridges_fc):
    """{scenario: (cut, wet)} per block for the central model, the range and the bridges, and notes on the closures."""
    import exposure
    from shapely import STRtree, points
    smp = samples(R)
    sfha, any_ = exposure.flood_polygons(flood_fc)
    tree = STRtree(points(smp[0], smp[1]))
    in1 = exposure.points_in_polygons(sfha, smp[0], smp[1], tree)
    in2 = exposure.points_in_polygons(any_, smp[0], smp[1], tree)
    spans, bad, bn = bridge_sets(R, bridges_fc)
    flood = flood_closures(R, smp, in1, spans)
    scen = {"flood": flood, "flood_low": flood_closures(R, smp, in1, spans, RAISED + PRIMARY), "flood_high": flood_closures(R, smp, in2, {}, ()),
            "bridges": dict(bad), "both": merge(flood, bad), "none": {}}
    bs = network_snaps(R, [(lon, lat) for _, _, lon, lat in blocks])
    hs = [s for s in network_snaps(R, hospitals) if s]
    out = {k: cut_off(R, bs, hs, v) for k, v in scen.items()}
    km = lambda d: round(sum(R.cum[e][-1] for e in d) / 1000)   # noqa: E731  length of the edges touched
    notes = {"test_points": int(len(smp[0])), "test_points_in_1pct_area": int(in1.sum()), "test_points_in_1pct_or_02pct_area": int(in2.sum()),
             "edges_closed": {k: len(v) for k, v in scen.items() if k != "none"}, "km_of_road_on_closed_edges": {k: km(v) for k, v in scen.items() if k != "none"},
             "bridges": bn, "hospitals": len(hospitals), "hospitals_on_a_road": len(hs), "blocks_not_placed": sum(1 for s in bs if s is None)}
    return out, bs, notes


def inputs():
    import conditions
    import geo
    import network
    import roads
    cache = ROOT / "cache"
    table = network.load_block_table(cache / "network", False)
    barrio_of = geo.block_barrios(table, False, cache / "geo")
    keep = [k for k, r in enumerate(table["rows"]) if r[1] > 0]
    blocks = [(table["rows"][k][0], table["rows"][k][1], table["rows"][k][4], table["rows"][k][5]) for k in keep]
    block_barrio = [barrio_of[k] for k in keep] if isinstance(barrio_of, list) else [barrio_of.get(b[0]) for b in blocks]
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    hospitals = [(lon, lat) for _, _, lon, lat, named in conditions.osm_hospitals() if named]
    load = lambda n: json.loads((DATA / n).read_text(encoding="utf-8"))   # noqa: E731
    return (roads.Roads(DATA / "roads.bin"), blocks, block_barrio, [r[0] for r in muni], [r[2] for r in muni], [r[0] for r in cw["units"]["barrio"]],
            hospitals, load("flood.geojson"), load("bridges.geojson"), load("wcrp.geojson"))


def shares(blocks, unit_of, n, flag, measured):
    """(share of measured residents flagged per unit, rounded to 0.1 %, None where no one is measured; residents flagged per unit)."""
    s, w = [0] * n, [0] * n
    for (_, pop, _, _), u, f, m in zip(blocks, unit_of, flag, measured):
        if u >= 0 and m:
            w[u] += pop
            s[u] += pop if f else 0
    return [round(s[i] / w[i] * 100, 1) if w[i] else None for i in range(n)], [s[i] if w[i] else None for i in range(n)]


def wcrp_check(blocks, cut, measured, fc):
    """The share of residents within WCRP_RADIUS_M of each WCRP community's point who are cut off (central model), for the communities whose plans say they are cut
    off and for the others."""
    lon = np.array([b[2] for b in blocks])
    lat = np.array([b[3] for b in blocks])
    pop = np.array([b[1] for b in blocks]) * np.array(measured)
    said, other = {}, []
    for f in fc["features"]:
        x, y = f["geometry"]["coordinates"][:2]
        near = np.hypot((lon - x) * 105600, (lat - y) * 110600) < WCRP_RADIUS_M
        tot = int(pop[near].sum())
        if not tot:
            continue
        sh = round(float(pop[near & cut].sum()) / tot * 100, 1)
        name = f["properties"]["comunidad"]
        if name in WCRP_SAY_CUT_OFF:
            said[f"{name} ({f['properties']['municipio']})"] = sh
        else:
            other.append(sh)
    return {"radius_m": WCRP_RADIUS_M, "plans_say_cut_off": said, "plans_say_cut_off_mean_pct": round(sum(said.values()) / len(said), 1) if said else None,
            "plans_say_cut_off_at_least_half": sum(1 for v in said.values() if v >= 50), "other_communities": len(other),
            "other_communities_mean_pct": round(sum(other) / len(other), 1) if other else None,
            "other_communities_at_least_half": sum(1 for v in other if v >= 50),
            "searched": "the WCRP community plans, 2026-11-20: 'incomunicada', a single road in, a bridge at risk"}


def var(key, label, unit, defin, years, kind="rate", d=1):
    return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": kind, "sources": list(SOURCES), "ref": REF, "definition": defin + COMMON,
            "family": "cutoff", "counted": kind == "count", "noPerHU": True, "barrioFile": OUT_BARRIO.name, "estimate": True, "years": years}


def assemble(R, blocks, block_barrio, muni_ids, muni_names, barrio_ids, hospitals, flood_fc, bridges_fc, wcrp_fc):
    year = date.today().year
    res, snaps, mnotes = model(R, blocks, hospitals, flood_fc, bridges_fc)
    none_cut = res["none"][0]
    measured = [s is not None and not c for s, c in zip(snaps, none_cut)]   # placed on a road that reaches a hospital with nothing closed
    mi = {m: i for i, m in enumerate(muni_ids)}
    bi = {b: i for i, b in enumerate(barrio_ids)}
    um = [mi.get(b[0][:5], -1) for b in blocks]
    ub = [bi.get(b, -1) for b in block_barrio]
    isl = [0] * len(blocks)
    pop = np.array([b[1] for b in blocks])
    meas = np.array(measured)

    def three(flag):
        m, mc = shares(blocks, um, len(muni_ids), flag, measured)
        p, pc = shares(blocks, isl, 1, flag, measured)
        b, bc = shares(blocks, ub, len(barrio_ids), flag, measured)
        return (m, p, b), (mc, pc, bc)

    cut, wet = res["flood"]
    dry = cut & ~wet
    spec = [
        ("cut_flood_pct", "Residents with no flood-free road to a hospital (estimate, %)", cut,
         "The share of the area's residents (2020 Census) who would have no open road to any hospital if every road in FEMA's 1% annual chance flood area closed, "
         "those whose own street floods included."),
        ("cut_flood_dry_pct", "Residents on dry streets cut off from hospitals by floods (estimate, %)", dry,
         "The share of the area's residents (2020 Census) whose own street stays out of FEMA's 1% annual chance flood area but every road from it to a hospital "
         "crosses the flood area: they are dry and still cut off."),
        ("cut_bridge_pct", "Residents cut off from hospitals by bridges in poor condition (estimate, %)", res["bridges"][0],
         "The share of the area's residents (2020 Census) who would have no road to any hospital if every bridge the National Bridge Inventory rates in poor "
         "condition, or lists as closed, were closed."),
        ("cut_both_pct", "Residents cut off from hospitals by floods or poor bridges (estimate, %)", res["both"][0],
         "The share of the area's residents (2020 Census) who would have no open road to any hospital if both the roads in FEMA's 1% flood area and the bridges in "
         "poor condition or closed were closed."),
    ]
    vars_, bvars = [], []
    for key, label, flag, defin in spec:
        (m, p, b), _ = three(flag)
        vars_.append(var(key, label, "%", defin, {str(year): [*m, p[0]]}))
        bvars.append({"key": key, "years": {str(year): b}})
    _, (mc, pc, bc) = three(cut)
    vars_.append(var("cut_flood_res", "Residents with no flood-free road to a hospital (estimate)", "", spec[0][3], {str(year): [*mc, pc[0]]}, kind="count", d=0))
    bvars.append({"key": "cut_flood_res", "years": {str(year): bc}})

    def island(flag):
        n = int(pop[meas & flag].sum())
        return {"residents": n, "pct": round(n / int(pop[meas].sum()) * 100, 1)}
    notes = {**mnotes,
             "residents": int(pop.sum()), "residents_measured": int(pop[meas].sum()),
             "left_out": {"no_road_to_a_hospital_with_nothing_closed": int(pop[np.array([s is not None for s in snaps]) & none_cut].sum()),
                          "by_municipio": {muni_ids[i]: int(sum(p for (_, p, _, _), u, c, s in zip(blocks, um, none_cut, snaps) if u == i and c and s is not None))
                                           for i in sorted({u for u, c, s in zip(um, none_cut, snaps) if c and s is not None and u >= 0})},
                          "no_road_within_2_km": int(sum(b[1] for b, s in zip(blocks, snaps) if s is None))},
             "island": {"flood": island(cut), "flood_own_street_closed": island(wet & cut), "flood_dry_street": island(dry),
                        "bridges": island(res["bridges"][0]), "both": island(res["both"][0])},
             "range": {"flood_low": {**island(res["flood_low"][0]), "rule": "primary roads also kept open"},
                       "flood_high": {**island(res["flood_high"][0]), "rule": "the 0.2% annual chance area closed too, and every road class, sound bridges included"}},
             "rules": {"test_point_every_m": STEP_M, "kept_open": "motorways and trunk roads and their ramps; the span of each bridge in good or fair condition plus 15 m",
                       "bridge_to_road_m": BRIDGE_SNAP_M, "hospitals": "OpenStreetMap hospitals and medical centres of gazetteer.json (conditions.osm_hospitals, named)"},
             "check": wcrp_check(blocks, cut, measured, wcrp_fc)}
    series = {"as_of": date.today().isoformat(), "years": [year], "geo": {"ids": [*muni_ids, "72"], "names": [*muni_names, "Puerto Rico"]}, "vars": vars_,
              "sources": SOURCES, "notes": notes}
    barrio = {"level": "barrio", "years": [year], "geo": {"ids": barrio_ids}, "vars": bvars,
              "notes": {"areas": len(barrio_ids), "source": "cutoff.py; the municipio values, the method, the range and the check are in cutoff_series.json"}}
    return series, barrio


def build(check=False):
    if not (ROOT / "cache" / "network" / "census_blocks_ids.json").exists():
        log("cutoff: the census block table is not in the cache (network.py writes it); nothing built")
        return 1 if check else 0
    series, barrio = assemble(*inputs())
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
            same = old is not None and strip(old) == strip(json.loads(json.dumps(d)))
            log(f"  {path.name}: {'matches' if same else 'DIFFERS'}")
            status |= 0 if same else 1
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        log(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")
    if not check:
        n = series["notes"]
        for k, v in {**n["island"], **n["range"]}.items():
            log(f"  {k:24s} {v['residents']:9,d} residents ({v['pct']}%)")
        c = n["check"]
        log(f"  check: plans that say cut off {c['plans_say_cut_off_mean_pct']}% on average ({c['plans_say_cut_off_at_least_half']} of {len(c['plans_say_cut_off'])} at least half); "
            f"other WCRP communities {c['other_communities_mean_pct']}% ({c['other_communities_at_least_half']} of {c['other_communities']})")
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the published files")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return build(a.check)


if __name__ == "__main__":
    raise SystemExit(main())
