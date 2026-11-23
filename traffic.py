"""Traffic on the roads of Puerto Rico for the PR Data Observatory: how many vehicles a day pass each stretch of the main roads, and the vehicle-kilometres,
truck traffic, road length and pavement condition of each municipio, from the Highway Performance Monitoring System (HPMS).

    python traffic.py            # download the pages missing from cache/traffic/ and build the two files below
    python traffic.py --refresh  # download everything again (the newest year FHWA publishes)
    python traffic.py --check    # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)

Writes
  site/data/traffic_roads.geojson  the map layer traffic: the arterials and major collectors with a traffic count, one line per stretch of a route with one
                                   count, wider and darker where more vehicles pass (2D map, 3D view and any map that reads Core.facilities)
  site/data/traffic_series.json    one value per municipio (the shape of economy_series.json): daily vehicle-kilometres, per resident, km of arterials and
                                   major collectors, truck share, pavement in poor condition, the busiest count
The Connections between municipios page and layer read traffic_roads.geojson for the traffic on the road each simulated connection follows
(transit_links.py; docs/traffic.md, HANDOFF decision 105, step 2).

The source (no key): US Department of Transportation, Federal Highway Administration, Highway Performance Monitoring System, "HPMS Full Join" of
Puerto Rico for the data year 2025 (collected by the Puerto Rico Department of Transportation and Public Works in 2025, submitted in 2026), published by
FHWA as an ArcGIS feature service on geo.dot.gov. US Government work. The build looks for the newest HPMS_FULL_PR_<year> service.

What the fields mean (HPMS Field Manual): aadt, the annual average daily traffic (vehicles a day, both directions on a two-way road); aadt_vd, the date
of the count or estimate; aadt_single_unit and aadt_combination, the trucks among them; f_system, the functional class (1 interstate, 2 other freeway or
expressway, 3 other principal arterial, 4 minor arterial, 5 major collector, 6 minor collector, 7 local); facility_type (1 one-way, 2 two-way, 4 ramp,
6 the non-inventory direction of a divided road, which repeats its line); section_length in miles; iri, the International Roughness Index in inches per
mile (FHWA: good under 95, fair 95 to 170, poor over 170); county_id, the municipio's county code.

How each figure is made (docs/traffic.md):
  - The layer: facility types 1 and 2 (each road drawn once), classes 1 to 5 with a count. Consecutive sections of one route with the same count are
    joined, and lines are simplified to 12 m. Local roads are left out: their counts are a handful of repeated low values, estimates, not counts.
  - Daily vehicle-km of a municipio: the sum of aadt x length over its sections of facility types 1 and 2, every class (local roads included, with the
    estimates the state reports). Per resident: over the 2020 Census residents.
  - Truck share: trucks over all vehicles, in vehicle-km, over the arterials and collectors (classes 1 to 5) whose sections report trucks.
  - Pavement in poor condition: the share of km of classes 1 to 5 with a roughness measurement whose IRI is over 170 inches per mile.
"""
import json
import math
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "traffic"
OUT = hs.OUT
OUT_LAYER = OUT / "traffic_roads.geojson"
OUT_SERIES = OUT / "traffic_series.json"
log = hs.log

UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
SERVICES = "https://geo.dot.gov/server/rest/services/Hosted?f=json"
SERVICE = "https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_PR_{year}/FeatureServer/0"
PAGE = 2000
LAYER_FIELDS = "objectid,route_id,route_name,begin_point,end_point,section_length,f_system,county_id,aadt,aadt_vd,aadt_single_unit,aadt_combination,through_lanes,speed_limit,nhs"
ALL_FIELDS = "objectid,f_system,facility_type,county_id,aadt,section_length,aadt_single_unit,aadt_combination,iri,iri_vd"
LAYER_WHERE = "f_system<=5 AND aadt>0 AND facility_type IN (1,2)"
MILE_KM = 1.609344
IRI_POOR = 170          # inches per mile (FHWA, 23 CFR 490.313)
SIMPLIFY_M = 12
CLASSES = [2000, 5000, 10000, 20000, 40000]   # vehicles a day: the layer's six colour classes start at 0 and at each of these
CLASS_NAMES = ["Fewer than 2,000 vehicles a day", "2,000 to 5,000", "5,000 to 10,000", "10,000 to 20,000", "20,000 to 40,000", "40,000 or more"]
FSYS = {1: "Interstate", 2: "Other freeway or expressway", 3: "Other principal arterial", 4: "Minor arterial", 5: "Major collector"}
LAT0 = 18.2
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574


def get(url, params=None, timeout=180):
    for i in range(5):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise requests.RequestException(str(d["error"])[:200])
            return d
        except (requests.RequestException, ValueError) as e:
            if i == 4:
                raise SystemExit(f"traffic: {url} failed ({e})")
            log(f"  retry {url} ({e})")
            time.sleep(3 * (i + 1))


def newest_year(refresh):
    """The newest data year of a Puerto Rico HPMS full join on geo.dot.gov (cached in cache/traffic/year.json)."""
    p = CACHE / "year.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))["year"]
    names = [s["name"] for s in get(SERVICES)["services"]]
    years = sorted(int(m.group(1)) for n in names if (m := re.fullmatch(r"Hosted/HPMS_FULL_PR_(\d{4})", n, re.I)))
    if not years:
        raise SystemExit("traffic: no HPMS_FULL_PR_<year> service on geo.dot.gov")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"year": years[-1], "checked": date.today().isoformat()}), encoding="utf-8")
    return years[-1]


def pages(year, kind, where, fields, geometry, refresh):
    """Every record of a query, from cached pages (cache/traffic/<year>-<kind>-<n>.json), downloading the missing ones."""
    url = SERVICE.format(year=year) + "/query"
    n = get(url, {"where": where, "returnCountOnly": "true", "f": "json"})["count"] if refresh or not (CACHE / f"{year}-{kind}-count.json").exists() \
        else json.loads((CACHE / f"{year}-{kind}-count.json").read_text())["count"]
    (CACHE / f"{year}-{kind}-count.json").write_text(json.dumps({"count": n}))
    out = []
    for k in range(math.ceil(n / PAGE)):
        p = CACHE / f"{year}-{kind}-{k}.json"
        if refresh or not p.exists():
            params = {"where": where, "outFields": fields, "orderByFields": "objectid", "resultOffset": k * PAGE, "resultRecordCount": PAGE, "f": "json",
                      "returnGeometry": "true" if geometry else "false"}
            if geometry:
                params.update({"outSR": 4326, "geometryPrecision": 6})
            d = get(url, params)
            p.write_text(json.dumps(d["features"], separators=(",", ":")), encoding="utf-8")
            log(f"  {kind} page {k + 1} of {math.ceil(n / PAGE)}")
        out += json.loads(p.read_text(encoding="utf-8"))
    if len(out) != n:
        raise SystemExit(f"traffic: {kind}: {len(out)} records for a count of {n}")
    return out


def download(refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    year = newest_year(refresh)
    layer = pages(year, "layer", LAYER_WHERE, LAYER_FIELDS, True, refresh)
    every = pages(year, "all", "1=1", ALL_FIELDS, False, refresh)
    return year, layer, every


def to_m(geom):
    from shapely import transform
    return transform(geom, lambda a: a * [KX, KY])


def to_deg(geom):
    from shapely import transform
    return transform(geom, lambda a: a / [KX, KY])


def colour_class(aadt):
    """1 to 6: the layer's colour class of a count (1 under 2,000 vehicles a day ... 6 at 40,000 or more)."""
    return 1 + sum(1 for c in CLASSES if aadt >= c)


def r1(v):
    return None if v is None else round(v, 1)


def stretches(layer, ftype):
    """The layer's features: consecutive sections of one route and direction with the same count, lanes, speed limit and count date, joined into one line."""
    from shapely.geometry import LineString, MultiLineString
    from shapely.ops import linemerge
    groups = {}
    for f in layer:
        a = f["attributes"]
        if not f.get("geometry") or not f["geometry"].get("paths"):
            continue
        groups.setdefault((a["route_id"], a["route_name"] or ""), []).append({**a, "paths": f["geometry"]["paths"], "ft": ftype.get(a["objectid"])})
    out = []
    for (rid, rname), secs in sorted(groups.items()):
        secs.sort(key=lambda a: (a["begin_point"], a["end_point"]))
        run = []

        def flush():
            if not run:
                return
            a0 = run[0]
            lines = [LineString(p) for s_ in run for p in s_["paths"] if len(p) > 1]
            if not lines:
                run.clear()
                return
            g = linemerge(MultiLineString(lines)) if len(lines) > 1 else lines[0]
            miles = sum(s_["section_length"] or 0 for s_ in run)
            trucks = [((s_["aadt_single_unit"] or 0) + (s_["aadt_combination"] or 0), s_["section_length"] or 0) for s_ in run if s_["aadt_single_unit"] or s_["aadt_combination"]]
            tl = sum(w for _, w in trucks)
            out.append({"geom": g, "route": rid, "name": rname, "aadt": a0["aadt"],
                        "trucks_pct": r1(100 * sum(t * w for t, w in trucks) / tl / a0["aadt"]) if trucks and tl and a0["aadt"] else None,
                        "lanes": a0["through_lanes"], "speed": a0["speed_limit"], "year": int(str(a0["aadt_vd"])[:4]) if a0.get("aadt_vd") else None,
                        "fsys": a0["f_system"], "oneway": a0["ft"] == 1, "km": miles * MILE_KM})
            run.clear()
        for a in secs:
            same = run and abs(a["begin_point"] - run[-1]["end_point"]) < 0.002 and all(a[k] == run[-1][k] for k in ("aadt", "through_lanes", "speed_limit", "f_system", "aadt_vd"))
            if not same:
                flush()
            run.append(a)
        flush()
    return out


V = [   # the series' variables: key, label, unit, decimals, type, definition
    ("traffic_vkt", "Vehicle-kilometres a day (HPMS)", "vehicle-km a day", 0, "count",
     "The vehicle-kilometres driven on an average day on the municipio's public roads: each road section's annual average daily traffic times its length, added up. "
     "Local streets are included with the traffic the Department of Transportation and Public Works estimates for them; ramps are left out."),
    ("traffic_vkt_pc", "Vehicle-kilometres a day per resident (HPMS)", "vehicle-km a day per resident", 1, "ratio",
     "The daily vehicle-kilometres on the municipio's roads over its residents in the 2020 Census. It counts every vehicle on those roads, also those of people who "
     "live elsewhere, so it is high where through traffic is heavy."),
    ("traffic_main_km", "Arterials and major collectors, km (HPMS)", "km", 1, "count",
     "The length of the municipio's main roads: freeways and expressways, principal and minor arterials and major collectors (functional classes 1 to 5), each road counted once."),
    ("traffic_max_aadt", "Busiest road, vehicles a day (HPMS)", "vehicles a day", 0, "count",
     "The highest annual average daily traffic on any section of the municipio's arterials and major collectors."),
    ("traffic_truck_pct", "Trucks, % of traffic on the main roads (HPMS)", "%", 1, "rate",
     "Single-unit and combination trucks as a share of all vehicles, in vehicle-kilometres, on the arterials and major collectors whose sections report trucks."),
    ("traffic_poor_pct", "Main roads with rough pavement, % of km measured (HPMS)", "% of km", 1, "rate",
     f"The share of the measured kilometres of arterials and major collectors whose International Roughness Index is over {IRI_POOR} inches per mile, FHWA's threshold for poor pavement."),
]


def assemble(year, layer, every):
    munis = {f["properties"]["GEOID"]: f["properties"] for f in json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]}
    ids = sorted(munis)
    ftype = {f["attributes"]["objectid"]: f["attributes"]["facility_type"] for f in every}
    rows = [f["attributes"] for f in every]
    unknown = {r["county_id"] for r in rows} - {int(g[2:]) for g in ids} - {None}
    if unknown:
        raise SystemExit(f"traffic: county codes with no municipio: {sorted(unknown)}")
    if len(munis) != 78:
        raise SystemExit(f"traffic: {len(munis)} municipios, expected 78")

    # the municipio figures
    acc = {g: {"vkt": 0.0, "main_km": 0.0, "truck_vkt": 0.0, "truck_base": 0.0, "iri_km": 0.0, "poor_km": 0.0, "max": 0} for g in ids + ["72"]}
    for r in rows:
        if r["facility_type"] not in (1, 2) or not r["section_length"] or r["county_id"] is None:
            continue
        km = r["section_length"] * MILE_KM
        for g in ("72%03d" % r["county_id"], "72"):
            a = acc[g]
            a["vkt"] += (r["aadt"] or 0) * km
            if r["f_system"] and r["f_system"] <= 5:
                a["main_km"] += km
                if r["aadt"]:
                    a["max"] = max(a["max"], r["aadt"])
                    if r["aadt_single_unit"] or r["aadt_combination"]:
                        a["truck_vkt"] += ((r["aadt_single_unit"] or 0) + (r["aadt_combination"] or 0)) * km
                        a["truck_base"] += r["aadt"] * km
                if r["iri"] and r["iri"] > 0:
                    a["iri_km"] += km
                    a["poor_km"] += km if r["iri"] > IRI_POOR else 0
    pop = {g: munis[g]["POP100"] for g in ids}
    pop["72"] = sum(pop.values())
    order = ids + ["72"]
    pct = lambda n, d: round(100 * n / d, 1) if d else None
    val = {
        "traffic_vkt": [round(acc[g]["vkt"]) for g in order],
        "traffic_vkt_pc": [round(acc[g]["vkt"] / pop[g], 1) if pop[g] else None for g in order],
        "traffic_main_km": [round(acc[g]["main_km"], 1) for g in order],
        "traffic_max_aadt": [acc[g]["max"] or None for g in order],
        "traffic_truck_pct": [pct(acc[g]["truck_vkt"], acc[g]["truck_base"]) for g in order],
        "traffic_poor_pct": [pct(acc[g]["poor_km"], acc[g]["iri_km"]) for g in order],
    }
    ref = f"FHWA Highway Performance Monitoring System, Puerto Rico full join, data year {year} (geo.dot.gov, HPMS_FULL_PR_{year})"
    variables = [{"key": k, "group": "Infrastructure · Traffic (FHWA HPMS)", "label": lab, "unit": u, "d": d, "type": t, "sources": ["fhwa_hpms"], "ref": ref,
                  "definition": dfn, "family": "traffic", "counted": False, "noPerHU": True, "years": {str(year): val[k]}} for k, lab, u, d, t, dfn in V]
    series = {"years": [year], "geo": {"ids": order, "names": [munis[g]["municipality"] for g in ids] + ["Puerto Rico"]}, "vars": variables,
              "sources": {"fhwa_hpms": {"name": "FHWA · Highway Performance Monitoring System (HPMS), Puerto Rico full join", "url": SERVICE.format(year=year),
                                        "license": "US Government work (no US copyright)",
                                        "note": f"Every road section Puerto Rico reported for {year}, with its traffic, lanes and pavement; the observatory publishes municipio figures and the main roads."}},
              "notes": {"data_year": year, "sections": len(rows), "sections_with_traffic": sum(1 for r in rows if r["aadt"]), "pr_vkt": val["traffic_vkt"][-1],
                        "pr_main_km": val["traffic_main_km"][-1], "iri_poor": IRI_POOR,
                        "what": "Annual average daily traffic as Puerto Rico reports it to FHWA: counts on the main roads (of different years: each section's aadt_vd), estimates on local streets."}}

    # the layer
    feats = []
    for s_ in stretches(layer, ftype):
        g = to_deg(to_m(s_["geom"]).simplify(SIMPLIFY_M))
        coords = [[[round(x, 5), round(y, 5)] for x, y in ln.coords] for ln in (g.geoms if g.geom_type == "MultiLineString" else [g])]
        coords = [c for c in coords if len(c) > 1]
        if not coords:
            continue
        p = {"c": colour_class(s_["aadt"]), "a": s_["aadt"], "r": s_["route"], "f": s_["fsys"], "y": s_["year"], "l": s_["lanes"], "km": round(s_["km"], 2)}
        if s_["trucks_pct"] is not None:
            p["t"] = s_["trucks_pct"]
        if s_["speed"]:
            p["s"] = s_["speed"]
        if s_["oneway"]:
            p["o"] = 1
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords[0]} if len(coords) == 1 else {"type": "MultiLineString", "coordinates": coords},
                      "properties": p})
    feats.sort(key=lambda f: (f["properties"]["a"], f["properties"]["r"]))   # the busiest roads drawn last, on top
    years = sorted({f["properties"]["y"] for f in feats if f["properties"]["y"]})
    layer_doc = {"type": "FeatureCollection", "vintage": str(year),
                 "notes": {"source": "FHWA Highway Performance Monitoring System, Puerto Rico", "data_year": year, "stretches": len(feats),
                           "km": round(sum(f["properties"]["km"] for f in feats), 1), "count_years": [years[0], years[-1]] if years else None,
                           "classes": CLASSES, "what": "Arterials and major collectors with a traffic count, each road drawn once (one-way roads in each direction)."},
                 "features": feats}
    return series, layer_doc


def build(refresh=False, check=False):
    if check:
        if not (CACHE / "year.json").exists():
            print("traffic: nothing cached in cache/traffic/: run python traffic.py first")
            return 1
        year = json.loads((CACHE / "year.json").read_text())["year"]
        layer, every = pages(year, "layer", LAYER_WHERE, LAYER_FIELDS, True, False), pages(year, "all", "1=1", ALL_FIELDS, False, False)
    else:
        year, layer, every = download(refresh)
    series, layer_doc = assemble(year, layer, every)
    n = series["notes"]
    log(f"traffic: {year}: {n['sections']:,} sections ({n['sections_with_traffic']:,} with traffic); Puerto Rico {n['pr_vkt']:,} vehicle-km a day, {n['pr_main_km']:,} km of main roads; "
        f"layer {layer_doc['notes']['stretches']:,} stretches, {layer_doc['notes']['km']:,} km")
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_LAYER, layer_doc)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python traffic.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--download" in sys.argv:
        y, a, b = download("--refresh" in sys.argv)
        print(y, len(a), len(b))
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
