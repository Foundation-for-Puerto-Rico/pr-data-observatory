"""What lies upstream of each reservoir and river gauge for the PR Data Observatory: the land that drains to it, and the residents, housing units, buildings,
wastewater treatment plants and protected land on that land. HANDOFF decision 107, step 9, fourth part (row derived-upstream); docs/upstream.md.

    python upstream.py --refresh   # read EPA's wastewater plants and USGS's drainage areas into cache/upstream/, then build
    python upstream.py             # build site/data/upstream.json from the cache and the published layers (no network)
    python upstream.py --check     # rebuild and exit 1 when the published file is not what it gives (nothing written)

How (an overlay of published layers along the stream network, docs/upstream.md):
  - The land: the NHDPlus HR catchments of "What drains here" (catchments.geojson, watersheds.py), each linked to the next one downstream (dn) and, at a split,
    to the reach it splits from (via). A site's land is the catchment that holds its point and every catchment upstream of it, walked as the map's
    Core.study.upstream walks it. A point that falls outside every catchment (on a dam's edge or at sea) takes the nearest catchment within 500 m.
  - Residents and housing units: the 2020 Census blocks whose internal point is on that land. Buildings: the footprints of the map's building layer (Overture,
    buildings.py) whose point is on it. Protected land: the area of the protected areas of protected.geojson (PAD-US, the same rules as the exposure series:
    proclamation boundaries left out) inside it, as a share.
  - Wastewater plants: the publicly owned treatment works (interest type POTW) of EPA's Facility Registry Service in Puerto Rico whose permit is in force
    (status effective or administratively continued), on that land. They are public facilities and are named.
The check: USGS's own drainage area for each site (NWIS site service, drain_area_va), against the area of the land found here. In the northern karst
water also moves underground, and some reservoirs receive water piped or channelled from another basin: the land that drains to a site on the surface is
not all the water that reaches it. Both are said wherever the figures appear.
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
CACHE = ROOT / "cache" / "upstream"
POTW_CACHE = CACHE / "potw_pr.json"
NWIS_CACHE = CACHE / "nwis_sites.json"
OUT = DATA / "upstream.json"
FRS_NPDES = "https://geodata.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer/11/query"
NWIS_SITE = "https://waterservices.usgs.gov/nwis/site/"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
IN_FORCE = ("EFFECTIVE", "ADMIN CONTINUED")
NEAR_M = 500
SQMI_KM2 = 2.589988
AGREE = 0.25
NAME_M = 300     # a site snaps to a stream of its own name within 300 m
STREAM_M = 150   # else to the largest stream within 150 m   # a site agrees with USGS when the land found here is within 25% of USGS's drainage area


def log(*a):
    print(*a, flush=True)


# ── downloads (cache only) ───────────────────────────────────────────────────

def fetch_potw():
    import requests
    rows, off = [], 0
    while True:
        r = requests.get(FRS_NPDES, params={"where": "STATE_CODE='PR' AND INTEREST_TYPE='POTW'", "outFields": "REGISTRY_ID,PRIMARY_NAME,ACTIVE_STATUS,PGM_SYS_ID,LATITUDE83,LONGITUDE83,CITY_NAME",
                                            "returnGeometry": "false", "f": "json", "resultOffset": off, "resultRecordCount": 1000, "orderByFields": "OBJECTID"}, headers=UA, timeout=120).json()
        if "error" in r:
            raise SystemExit(f"upstream: EPA FRS answered {r['error']}")
        page = [f["attributes"] for f in r.get("features", [])]
        rows += page
        if len(page) < 1000:
            break
        off += 1000
    if not 30 <= len(rows) <= 200:
        raise SystemExit(f"upstream: {len(rows)} POTW records for Puerto Rico (63 on 2026-11-23): read EPA's layer before publishing")
    keep = [{"id": x["PGM_SYS_ID"], "name": x["PRIMARY_NAME"], "status": x["ACTIVE_STATUS"], "lon": x["LONGITUDE83"], "lat": x["LATITUDE83"]} for x in rows]
    CACHE.mkdir(parents=True, exist_ok=True)
    POTW_CACHE.write_text(json.dumps({"read": date.today().isoformat(), "rows": sorted(keep, key=lambda x: x["id"] or "")}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    log(f"  EPA FRS: {len(keep)} POTW records, {sum(1 for x in keep if x['status'] in IN_FORCE)} in force")


def fetch_nwis(ids):
    import requests
    out = {}
    for i in range(0, len(ids), 80):
        r = requests.get(NWIS_SITE, params={"format": "rdb", "sites": ",".join(ids[i:i + 80]), "siteOutput": "expanded"}, headers=UA, timeout=120)
        r.raise_for_status()
        lines = [ln for ln in r.text.splitlines() if ln and not ln.startswith("#")]
        head = lines[0].split("\t")
        for ln in lines[2:]:
            v = dict(zip(head, ln.split("\t")))
            out[v["site_no"]] = {"name": v["station_nm"], "drain_sqmi": float(v["drain_area_va"]) if v.get("drain_area_va", "").strip() else None,
                                 "contrib_sqmi": float(v["contrib_drain_area_va"]) if v.get("contrib_drain_area_va", "").strip() else None}
    CACHE.mkdir(parents=True, exist_ok=True)
    NWIS_CACHE.write_text(json.dumps({"read": date.today().isoformat(), "sites": out}, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    log(f"  USGS NWIS: {len(out)} sites, {sum(1 for v in out.values() if v['drain_sqmi'])} with a drainage area")


# ── the network ──────────────────────────────────────────────────────────────

def upstream(dn, i, via, kids):
    """The catchments that drain to i: i and every k whose chain of dn (and via) reaches it (Core.study.upstream)."""
    out, seen, stack = [], {i}, [i]
    while stack:
        k = stack.pop()
        out.append(k)
        v = via[k]
        for c in list(kids.get(k, ())) + (list(v) if isinstance(v, list) else [] if v is None else [v]):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return out


def outlets(dn):
    """The catchment where each catchment's chain of dn ends (at the sea, a sink or the network's edge)."""
    out = [-1] * len(dn)
    for k in range(len(dn)):
        path, j = [], k
        while out[j] < 0 and dn[j] >= 0 and len(path) < 100000:
            path.append(j)
            j = dn[j]
        end = out[j] if out[j] >= 0 else j
        for q in path + [j]:
            out[q] = end
    return out


def locate(tree, polys, lon, lat):
    """The catchment index of each point (-1 when none): inside an outline (the lowest index on a shared edge)."""
    import shapely
    hit, idx = tree.query(shapely.points(lon, lat), predicate="intersects")
    out = np.full(len(lon), -1, dtype=np.int64)
    order = np.lexsort((idx, hit))
    hit, idx = hit[order], idx[order]
    first = np.r_[True, hit[1:] != hit[:-1]] if len(hit) else np.zeros(0, bool)
    out[hit[first]] = idx[first]
    return out


def norm(name):
    """A stream or site name without accents, case, 'Río', 'Lago', 'Quebrada' and parentheses: 'Río Grande de Loíza' -> 'grande de loiza'."""
    import re
    import unicodedata
    if not name:
        return ""
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\b(rio|lago|quebrada|embalse|represa|lake|reservoir)\b", " ", t)
    return " ".join(t.split())


def km_per_deg(lat):
    return 111.32 * math.cos(math.radians(lat)), 110.57


def assemble(cat, sites, blocks, bld, potw, protected_fc, nwis):
    import shapely
    from shapely import STRtree
    from shapely.geometry import shape
    import exposure
    feats = cat["features"]
    polys = [shapely.make_valid(shape(f["geometry"])) for f in feats]
    dn = [f["properties"]["dn"] for f in feats]
    via = [f["properties"].get("via") for f in feats]
    km2 = np.array([f["properties"]["km2"] for f in feats])
    kids = collections.defaultdict(list)
    for k, d in enumerate(dn):
        if d >= 0:
            kids[d].append(k)
    outlet = outlets(dn)
    crossing = 0
    for k, v in enumerate(via):   # a split followed only within one river: a link between two rivers is a canal or a transfer, not land upstream
        if v:
            keep = [m for m in (v if isinstance(v, list) else [v]) if outlet[m] == outlet[k]]
            crossing += len(v if isinstance(v, list) else [v]) - len(keep)
            via[k] = keep or None
    tree = STRtree(polys)

    def per_catchment(lon, lat, w=None):
        at = locate(tree, polys, np.asarray(lon), np.asarray(lat))
        ok = at >= 0
        return np.bincount(at[ok], weights=None if w is None else np.asarray(w)[ok], minlength=len(polys)), int((~ok).sum())

    b_pop, out_pop = per_catchment([b[2] for b in blocks], [b[3] for b in blocks], [b[1] for b in blocks])
    b_hu, _ = per_catchment([b[2] for b in blocks], [b[3] for b in blocks], [b[4] for b in blocks])
    b_bld, out_bld = per_catchment(bld["lon"], bld["lat"])
    live = [p for p in potw if p["status"] in IN_FORCE and p["lon"] is not None]
    p_at = locate(tree, polys, np.array([p["lon"] for p in live]), np.array([p["lat"] for p in live]))
    prot, _strict = exposure.protected_polygons(protected_fc)
    pu = shapely.union_all(shapely.make_valid(np.array(prot, dtype=object))) if prot else None
    shapely.prepare(pu)
    b_prot = np.zeros(len(polys))
    for k in tree.query(pu, predicate="intersects") if pu is not None else ():
        g = polys[k]
        if shapely.contains(pu, g):
            b_prot[k] = km2[k]
        else:
            a = shapely.area(shapely.intersection(g, pu))
            b_prot[k] = km2[k] * a / shapely.area(g) if shapely.area(g) else 0
    names = [norm(f["properties"].get("name")) for f in feats]
    up_km2 = {}

    def total(k):
        if k not in up_km2:
            up_km2[k] = float(km2[upstream(dn, k, via, kids)].sum())
        return up_km2[k]

    def snap(s, lon, lat):
        """The catchment of the stream a site measures: within NAME_M, the one whose flowline bears the site's river name and drains the most land; else, within
        STREAM_M, the one that drains the most land (the river's own reach, not a small catchment on its bank); else the catchment that holds the point."""
        kx, ky = km_per_deg(lat)
        pt = shapely.points(lon, lat)
        river = norm(s["name"])
        named = [k for k in tree.query(shapely.buffer(pt, NAME_M / 1000 / ky)) if names[k] and river and (river in names[k] or names[k] in river)]
        if named:
            return max(named, key=total), "named stream"
        near = list(tree.query(shapely.buffer(pt, STREAM_M / 1000 / ky)))
        if near:
            return max(near, key=total), "largest stream nearby"
        i = int(locate(tree, polys, np.array([lon]), np.array([lat]))[0])
        if i >= 0:
            return i, "inside"
        nb = tree.query_nearest(pt, max_distance=NEAR_M / 1000 / ky, return_distance=False)
        return (int(nb[0]), "nearest") if len(nb) else (-1, "none")

    rows, notes_place = [], collections.Counter()
    for s in sites:
        lon, lat = s["lon"], s["lat"]
        i, how = snap(s, lon, lat)
        if i < 0:
            notes_place["none"] += 1
            continue
        notes_place[how] += 1
        up = upstream(dn, i, via, kids)
        a = float(km2[up].sum())
        ref = nwis.get(s["usgs"].replace("USGS-", ""), {})
        usgs_km2 = round(ref["drain_sqmi"] * SQMI_KM2, 1) if ref.get("drain_sqmi") else None
        pl = [live[j]["name"].title().replace("Wwtp", "WWTP").replace("Stp", "STP").replace("Prasa", "PRASA") for j in np.flatnonzero(np.isin(p_at, up))]
        if s["kind"] == "reservoir" and usgs_km2 is None:   # off the stream, fed by a canal or pumps: USGS publishes no drainage area and the network cannot say what feeds it
            rows.append({"usgs": s["usgs"], "name": s["name"], "kind": s["kind"], "municipio": s["municipio"], "geoid": s["geoid"], "aaa": s.get("aaa"),
                         "km2": None, "usgs_km2": None, "placed": how, "agrees": None, "withheld": "off-stream",
                         "residents": None, "housing_units": None, "buildings": None, "residents_per_km2": None, "wastewater_plants": None, "plant_names": [],
                         "protected_pct": None, "catchments": None})
            continue
        rows.append({"usgs": s["usgs"], "name": s["name"], "kind": s["kind"], "municipio": s["municipio"], "geoid": s["geoid"], "aaa": s.get("aaa"),
                     "agrees": None if usgs_km2 is None else bool(abs(a / usgs_km2 - 1) <= AGREE), "withheld": None,
                     "km2": round(a, 1), "usgs_km2": usgs_km2, "placed": how,
                     "residents": int(b_pop[up].sum()), "housing_units": int(b_hu[up].sum()), "buildings": int(b_bld[up].sum()),
                     "residents_per_km2": round(float(b_pop[up].sum()) / a, 1) if a else None,
                     "wastewater_plants": len(pl), "plant_names": sorted(pl),
                     "protected_pct": round(float(b_prot[up].sum()) / a * 100, 1) if a else None,
                     "catchments": len(up)})
    agree = [r for r in rows if r["usgs_km2"] and r["km2"] is not None]
    within = [r for r in agree if abs(r["km2"] / r["usgs_km2"] - 1) <= AGREE]
    notes = {"sites": len(rows), "reservoirs": sum(1 for r in rows if r["kind"] == "reservoir"), "gauges": sum(1 for r in rows if r["kind"] == "gauge"),
             "withheld_off_stream": sorted(r["name"] for r in rows if r["withheld"]),
             "not_checked": sorted(r["name"] for r in rows if r["usgs_km2"] is None and not r["withheld"]),
             "placed": dict(notes_place), "catchments": len(polys), "splits_between_rivers_not_followed": crossing,
             "points_outside_every_catchment": {"residents": int(out_pop), "buildings": int(out_bld)},
             "wastewater_plants": {"records": len(potw), "in_force": len(live), "on_a_catchment": int((p_at >= 0).sum())},
             "check": {"rule": f"the land found here within {int(AGREE * 100)}% of USGS's drainage area (NWIS drain_area_va)",
                       "with_a_usgs_area": len(agree), "within": len(within),
                       "median_ratio": round(float(np.median([r["km2"] / r["usgs_km2"] for r in agree])), 3) if agree else None,
                       "outside": sorted(([r["name"], r["kind"], r["km2"], r["usgs_km2"]] for r in agree if r not in within), key=lambda x: x[0])}}
    return rows, notes


SOURCES = {
    "usgs_nhdplus_hr": {"name": "USGS NHDPlus High Resolution (VPU 2101): catchments and network flowlines", "url": "https://www.usgs.gov/national-hydrography/nhdplus-high-resolution",
                        "license": "US Government work (no US copyright)", "note": "The land that drains to each site (catchments.geojson, watersheds.py)."},
    "usgs_water": {"name": "USGS National Water Information System, site service", "url": "https://waterservices.usgs.gov/docs/site-service/",
                  "license": "US Government work (no US copyright)", "note": "The reservoirs and gauges, and each site's published drainage area (the check)."},
    "epa_frs": {"name": "EPA Facility Registry Service, NPDES interests (publicly owned treatment works)", "url": "https://www.epa.gov/frs",
                "license": "US Government work (no US copyright)", "note": "The wastewater treatment plants whose permit is in force."},
    "padus": {"name": "USGS Protected Areas Database of the United States (PAD-US)", "url": "https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview",
              "license": "US Government work (no US copyright)", "note": "The protected land (protected.geojson)."},
    "census_tiger": {"name": "US Census Bureau, 2020 Census blocks", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Residents and housing units by block internal point."},
    "overture_buildings": {"name": "Overture Maps Foundation, Buildings theme", "url": "https://docs.overturemaps.org/guides/buildings/", "license": "ODbL 1.0 (some CDLA Permissive 2.0)",
                 "note": "The building footprints of the map's building layer (buildings.py)."},
}


def inputs():
    import buildings
    import network
    load = lambda n: json.loads((DATA / n).read_text(encoding="utf-8"))   # noqa: E731
    sites = []
    for fname, kind in (("reservoirs.geojson", "reservoir"), ("river_gauges.geojson", "gauge")):
        for f in load(fname)["features"]:
            p = f["properties"]
            lon, lat = f["geometry"]["coordinates"][:2]
            sites.append({"usgs": p["usgs"], "name": p["name"], "kind": kind, "municipio": p.get("municipio"), "geoid": p.get("geoid"), "aaa": p.get("aaa") if kind == "reservoir" else None,
                          "lon": lon, "lat": lat})
    table = network.load_block_table(ROOT / "cache" / "network", False)
    blocks = [(r[0], r[1], r[4], r[5], r[2]) for r in table["rows"]]
    release, bld = buildings.load(offline=True)
    potw = json.loads(POTW_CACHE.read_text(encoding="utf-8"))
    nwis = json.loads(NWIS_CACHE.read_text(encoding="utf-8"))
    return load("catchments.geojson"), sites, blocks, bld, potw, load("protected.geojson"), nwis, release


def build(refresh=False, check=False):
    if refresh:
        fetch_potw()
        fetch_nwis([f["properties"]["usgs"].replace("USGS-", "") for n in ("reservoirs.geojson", "river_gauges.geojson")
                    for f in json.loads((DATA / n).read_text(encoding="utf-8"))["features"]])
    if not (POTW_CACHE.exists() and NWIS_CACHE.exists() and (ROOT / "cache" / "network" / "census_blocks_ids.json").exists()):
        log("upstream: cache/upstream or the census block table is missing (python upstream.py --refresh); nothing built")
        return 1 if check else 0
    cat, sites, blocks, bld, potw, prot, nwis, release = inputs()
    rows, notes = assemble(cat, sites, blocks, bld, potw["rows"], prot, nwis["sites"])
    notes.update({"buildings_release": release, "potw_read": potw["read"], "nwis_read": nwis["read"],
                  "limits": ["In the northern karst, water also moves underground: the land that drains to a site on the surface is not all the water that reaches it.",
                             "Some reservoirs receive water piped or channelled from another basin, which the land upstream does not show.",
                             "A count on the land upstream is not a load: it says what is there, not what reaches the water."]})
    doc = {"as_of": date.today().isoformat(), "sources": SOURCES, "notes": notes, "sites": rows}
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    c = notes["check"]
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB): {notes['reservoirs']} reservoirs, {notes['gauges']} gauges; placed {notes['placed']}")
    log(f"  check: {c['within']} of {c['with_a_usgs_area']} within {int(AGREE * 100)}% of USGS's drainage area (median ratio {c['median_ratio']})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read EPA's wastewater plants and USGS's drainage areas first")
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the published file")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return build(a.refresh, a.check)


if __name__ == "__main__":
    raise SystemExit(main())
