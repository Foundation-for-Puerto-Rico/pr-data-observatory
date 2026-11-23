"""Public facilities, public school students and main roads inside three hazard areas, by municipio: FEMA's 1% flood area, NOAA's 3 ft sea level rise area and the
USGS map's High, Very High and Extremely High landslide susceptibility classes. HANDOFF decision 107, step 3; docs/facility-exposure.md.

    python facility_exposure.py              # build site/data/facility_exposure_series.json (downloads the school directory, NOAA's sea level rise extents and the
                                             # landslide map tiles under the points and roads when they are not cached)
    python facility_exposure.py --refresh    # read the newest school directory again
    python facility_exposure.py --check      # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

An overlaid layer (decision 107 names three kinds: calculated, overlaid, estimate): one published layer laid on another. It says where a building or a road
stands, not what a flood would do to it: the floor height of a building and the height of a road are not known.

What is laid on what:
  the flood area    site/data/flood.geojson: FEMA's 1% annual chance flood area (the Special Flood Hazard Area), by the rule of exposure.flood_polygons
  sea level rise    NOAA's extent of 3 ft of sea level rise above mean higher high water, connected to the ocean (exposure.slr_layer; the height the observatory's
                    exposure series headline). Low-lying areas not connected to the ocean are left out. Roads are read every 20 m along their length.
  landslides        the USGS map of susceptibility to landslides triggered by intense rainfall (Hughes and Schulz, 2020), read from the same tiles as landslide.py:
                    a point counts when the 5 m cell under it is High, Very High or Extremely High (the top 30% of the main island). The map covers the main
                    island only, so Vieques and Culebra have no landslide value. A road is read every 20 m along its length.
  facilities        the point layers the map already draws: fire and EMS stations, police stations, city halls, libraries, public housing developments,
                    power plants and airports; and the public schools open in the newest year of the NCES school directory (Urban Institute Education Data API, no key),
                    each with its students
  main roads        site/data/traffic_roads.geojson: the arterials and major collectors with a traffic count, cut by municipio

Left out on purpose: bridges (a bridge over a river stands in the flood area by design). Public housing developments whose location is approximate are not
drawn and are not tested. 74 of the 1,099 library points lie within 150 m of an open public school and may be the same building: both are counted.

Output: facility_exposure_series.json (78 municipios and Puerto Rico, in the shape of health_series.json: one snapshot).
"""

import datetime
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import requests
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

import exposure
import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "facility_exposure"
OUT = hs.OUT / "facility_exposure_series.json"
OUT_SCHOOLS = hs.OUT / "public_schools.geojson"      # the open public schools as a map layer, each with its students, grades and hazard flags
OUT_HAZARDS = hs.OUT / "facility_hazards.json"       # the hazard flags of the points of the other facility layers, by layer and point, for their pop-ups
LAYER_KEY = {"fire_stations.geojson": "fire", "police_stations.geojson": "police", "town_halls.geojson": "townhalls", "libraries.geojson": "libraries",
             "public_housing.geojson": "pubhousing", "power_plants.geojson": "plants", "airports.geojson": "airports"}   # the layer keys of site/js/core/facilities.js
HZ_CODES = {"f": "FEMA's 1% annual chance flood area", "s": "NOAA's 3 ft sea level rise area (connected to the ocean)", "l": "High, Very High or Extremely High landslide susceptibility (USGS), under the point"}
log = hs.log
API = "https://educationdata.urban.org/api/v1/schools/ccd/directory/{year}/?fips=72"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
OPEN = {1, 3, 4, 5, 8}   # CCD school status, as education_series.OPEN: open, new, added, changed agency, reopened
KEEP = ["ncessch", "county_code", "latitude", "longitude", "school_status", "enrollment", "school_name", "lowest_grade_offered", "highest_grade_offered"]
LAYERS = {"fire_stations.geojson": "Fire and EMS stations", "police_stations.geojson": "Police stations", "town_halls.geojson": "City halls", "libraries.geojson": "Libraries",
          "public_housing.geojson": "Public housing developments", "power_plants.geojson": "Power plants", "airports.geojson": "Airports and heliports"}
GROUP = "Hazards · Facilities and roads in hazard areas"
SLR_FT = 3                                    # feet of sea level rise: the height the exposure series headline (exp_slr_3ft_pop)
LS_HIGH = 3                                   # landslide classes: High (3), Very High (4) and Extremely High (5) count
LS_STEP_M = 20                                # metres between the points read along a road on the landslide map
LS_NOT_MAPPED = {"72049", "72147"}            # Culebra and Vieques: the USGS landslide map covers the main island only
LAT0 = 18.2
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574   # metres per degree at Puerto Rico's latitude
REF = "FEMA National Flood Hazard Layer (the observatory's flood layer) laid on the observatory's facility layers, the NCES school directory and the FHWA main roads"
REF_SLR = "NOAA Office for Coastal Management sea level rise extents (3 ft, connected to the ocean) laid on the observatory's facility layers, the NCES school directory and the FHWA main roads"
REF_LS = "USGS landslide susceptibility map of Puerto Rico (Hughes and Schulz, 2020) laid on the observatory's facility layers, the NCES school directory and the FHWA main roads"


def school_rows(year, refresh=False, offline=False):
    """The kept columns of the Puerto Rico rows of the school directory of one year ([] when the API has none), cached."""
    f = CACHE / f"schools_{year}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    if offline:
        return None
    url, rows = API.format(year=year), []
    while url:
        for attempt in range(4):
            try:
                r = requests.get(url, headers=UA, timeout=(30, 180))
                if r.status_code == 404:
                    return []
                r.raise_for_status()
                d = r.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise SystemExit(f"facility_exposure: {url} failed: {e}")
                time.sleep(5 * (attempt + 1))
        rows += [{c: row.get(c) for c in KEEP} for row in d.get("results") or [] if str(row.get("fips")) == "72"]
        url = d.get("next")
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    log(f"  school directory {year}: {len(rows)} rows")
    return rows


def newest_schools(refresh=False, offline=False, today=None):
    """(year, open schools with a point) of the newest school year the directory has for Puerto Rico with students in it: [{geoid, x, y, students}]."""
    y = (today or datetime.date.today()).year
    for year in range(y, y - 6, -1):
        rows = school_rows(year, refresh, offline)
        if not rows:
            continue
        if any("school_name" not in r for r in rows[:5]):   # a cache from before the layer kept the names: read the year again (a --check stops here instead)
            if offline:
                raise SystemExit(f"facility_exposure --check: the cached school directory of {year} has no school names (python facility_exposure.py --refresh reads it again)")
            rows = school_rows(year, True, False)
        out = [{"geoid": str(r["county_code"]), "x": r["longitude"], "y": r["latitude"], "students": r["enrollment"] if isinstance(r["enrollment"], (int, float)) and r["enrollment"] >= 0 else None,
                "name": (r.get("school_name") or "").strip(), "grades": grades(r.get("lowest_grade_offered"), r.get("highest_grade_offered")), "nces": str(r["ncessch"])}
               for r in rows if r["school_status"] in OPEN and r["latitude"] and r["longitude"]]
        if sum(1 for s in out if s["students"]) >= 0.8 * len(out) and len(out) >= 600:   # a year the directory holds without its students yet is not the newest usable one
            return year, out, sum(1 for r in rows if r["school_status"] in OPEN) - len(out)
    raise SystemExit("facility_exposure: no school directory year in the cache or at the API (python facility_exposure.py makes the cache; --check never downloads)")


def grades(lo, hi):
    """'PK-12', 'K-5', '9-12' from the directory's codes (-1 pre-kindergarten, 0 kindergarten, 1 to 12); None when a code is missing or outside them."""
    name = lambda g: "PK" if g == -1 else "K" if g == 0 else str(g)   # noqa: E731
    if not isinstance(lo, int) or not isinstance(hi, int) or not -1 <= lo <= hi <= 12:
        return None
    return name(lo) if lo == hi else f"{name(lo)}-{name(hi)}"


STACKED = {}   # {kind: points left out because two or more points of the layer share their coordinates}, filled by facility_points()


def facility_points():
    """[{kind, layer, geoid, x, y}] of the point layers the map draws. Points that share their coordinates with another point of the same layer are left out
    (STACKED): several facilities listed at one address (for example a municipio's technology centres at its main library, as E-Rate lists them) are not where
    the buildings stand, and counting each would multiply one spot's hazard by the size of the stack."""
    from collections import Counter
    out = []
    STACKED.clear()
    for name, kind in LAYERS.items():
        feats = json.loads((hs.OUT / name).read_text(encoding="utf-8"))["features"]
        at = Counter(point_key(*f["geometry"]["coordinates"][:2]) for f in feats)
        for f in feats:
            x, y = f["geometry"]["coordinates"][:2]
            if at[point_key(x, y)] > 1:
                STACKED[kind] = STACKED.get(kind, 0) + 1
                continue
            out.append({"kind": kind, "layer": LAYER_KEY[name], "geoid": str(f["properties"]["geoid"]), "x": x, "y": y})
    return out


def point_key(x, y):
    """The key of a point in facility_hazards.json: its longitude and latitude to 5 decimals, as the layer files write them (core/facilities.js hzKey)."""
    return f"{x:.5f},{y:.5f}"


def flag_codes(wet, slr, ls):
    return ("f" if wet else "") + ("s" if slr else "") + ("l" if ls else "")


def side_files(every, wet, slr, ls, names_by_geoid, year):
    """(public_schools.geojson, facility_hazards.json): the schools as a layer with their flags, and the flags of the other layers' points (only the flagged ones)."""
    feats, layers = [], {}
    for p, a, b, c in zip(every, wet, slr, ls):
        hz = flag_codes(a, b, c)
        if p["kind"] == "Public schools":
            props = {"name": p["name"] or None, "type": "Public school", "municipio": names_by_geoid[p["geoid"]], "geoid": p["geoid"], "students": p["students"], "grades": p["grades"], "nces": p["nces"]}
            if hz:
                props["hz"] = hz
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(p["x"], 5), round(p["y"], 5)]}, "properties": props})
        elif hz:
            layers.setdefault(p["layer"], {})[point_key(p["x"], p["y"])] = hz
    feats.sort(key=lambda f: (f["properties"]["municipio"], f["properties"]["name"] or ""))
    flagged = sum(1 for f in feats if f["properties"].get("hz"))
    schools = {"type": "FeatureCollection", "vintage": f"{year}-{(year + 1) % 100:02d}", "school_year": year,
               "notes": {"schools": len(feats), "students": sum(f["properties"]["students"] or 0 for f in feats), "flagged": flagged,
                         "hz": HZ_CODES, "source": "NCES Common Core of Data school directory, through the Urban Institute's Education Data API (no key)",
                         "drawn": "every open public school with a point; the hazard flags say where the school stands (facility_exposure.py), not that harm will come to it"},
               "features": feats}
    hazards = {"version": 1, "codes": HZ_CODES, "key": "longitude,latitude to 5 decimals, as the layer files write them",
               "note": "Only the points with a flag are listed: a point of a layer that is not listed stands in none of the three areas, shares its coordinates with another point of its layer (not tested), or was added after the last build.",
               "layers": {k: dict(sorted(v.items())) for k, v in sorted(layers.items())}}
    return schools, hazards


def to_m(geom):
    return shapely.transform(geom, lambda c: np.column_stack([c[:, 0] * KX, c[:, 1] * KY]))


def road_pieces(roads_fc, muni_fc):
    """[(geoid, line in metres)]: each road line cut by the municipio outlines."""
    munis = [(f["properties"]["GEOID"], to_m(shape(f["geometry"]))) for f in muni_fc["features"]]
    mtree = STRtree([g for _, g in munis])
    out = []
    for f in roads_fc["features"]:
        line = to_m(shape(f["geometry"]))
        for i in mtree.query(line):
            piece = line.intersection(munis[i][1])
            if not piece.is_empty:
                out.append((munis[i][0], piece))
    return out


def road_samples(pieces):
    """(geoids, km of each step, lon, lat): each piece read every LS_STEP_M metres, at the middle of each step."""
    geo, step, xs, ys = [], [], [], []
    for g, piece in pieces:
        for line in shapely.get_parts(piece):
            if line.geom_type != "LineString" or line.length == 0:
                continue
            n = max(1, math.ceil(line.length / LS_STEP_M))
            d = (np.arange(n) + 0.5) * line.length / n
            c = shapely.get_coordinates(shapely.line_interpolate_point(line, d))
            xs.append(c[:, 0] / KX)
            ys.append(c[:, 1] / KY)
            geo += [g] * n
            step.append(np.full(n, line.length / n / 1000))
    if not geo:
        return [], np.zeros(0), np.zeros(0), np.zeros(0)
    return geo, np.concatenate(step), np.concatenate(xs), np.concatenate(ys)


def road_sampled_km(samples, flag):
    """{geoid: km of main road whose steps are flagged}: `flag(lon, lat)` says, for each step's middle point, whether it is in the hazard area."""
    geo, step, x, y = samples
    out = {}
    if not geo:
        return out
    for g, km, f in zip(geo, step, flag(x, y)):
        out[g] = out.get(g, 0.0) + (float(km) if f else 0.0)
    return out


def road_ls_km(pieces, classify):
    """{geoid: km of main road on High or higher landslide susceptibility}, read every LS_STEP_M metres. `classify(lon, lat)` gives the class of each point (0 where the map has none)."""
    return road_sampled_km(road_samples(pieces), lambda x, y: classify(x, y) >= LS_HIGH)


def ls_classifier(refresh=False, offline=False):
    """A function (lon, lat) -> landslide class of each point (0 where the map has no data), reading only the zoom-15 tiles of landslide.py under the points."""
    import landslide as ls
    island = set(ls.tile_range())

    def classify(lon, lat):
        lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
        n = 256 * 2 ** ls.Z
        X = (lon + 180) / 360 * n
        Y = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n
        tx, ty = (X // 256).astype(int), (Y // 256).astype(int)
        col, row = (X % 256).astype(int), (Y % 256).astype(int)
        out = np.zeros(len(lon), dtype=np.uint8)
        groups = {}
        for k, t in enumerate(zip(tx.tolist(), ty.tolist())):
            if t in island:
                groups.setdefault(t, []).append(k)
        png = ls.fetch_tiles(sorted(groups), refresh, offline)
        for t, idx in groups.items():
            if t in png:
                idx = np.array(idx)
                out[idx] = ls.tile_classes(png[t])[row[idx], col[idx]]
        return out
    return classify


def road_km(roads_fc, muni_fc, sfha, pieces=None):
    """{geoid: [km of main road, km of it inside the polygons]}: each road line is cut by the municipio outlines, and each piece by the polygons it meets."""
    flood = [to_m(g) for g in sfha]
    tree = STRtree(flood)
    out = {f["properties"]["GEOID"]: [0.0, 0.0] for f in muni_fc["features"]}
    for g, piece in (pieces if pieces is not None else road_pieces(roads_fc, muni_fc)):
        near = [flood[j] for j in tree.query(piece)]
        wet = piece.intersection(shapely.union_all(near)).length if near else 0.0
        a = out[g]
        a[0] += piece.length / 1000
        a[1] += wet / 1000
    return out


def figures(points, schools, roads, sfha, ids):
    """{key: [values for ids, then Puerto Rico]} from the facility points (schools included as a kind), the schools with their students and the road lengths."""
    def inside(items):
        if not items:
            return np.zeros(0, dtype=bool)
        return exposure.points_in_polygons(sfha, np.array([p["x"] for p in items], dtype=float), np.array([p["y"] for p in items], dtype=float))

    every = points + [{"kind": "Public schools", **s} for s in schools]
    for p, w in zip(every, inside(every)):
        p["wet"] = bool(w)
    unknown = {p["geoid"] for p in every} - set(ids)
    if unknown:
        raise SystemExit(f"facility_exposure: a facility names a municipio the observatory does not have: {sorted(unknown)[:5]}")
    out = {k: [] for k in ("fx_flood_n", "fx_flood_pct", "fx_schools_flood_n", "fx_students_flood_n", "fx_students_flood_pct", "fx_road_flood_km", "fx_road_flood_pct")}

    def one(sel, road):
        fac = [p for p in every if sel(p)]
        sch = [p for p in fac if p["kind"] == "Public schools"]
        wet = [p for p in fac if p["wet"]]
        stu = sum(p["students"] or 0 for p in sch)
        stu_wet = sum(p["students"] or 0 for p in sch if p["wet"])
        out["fx_flood_n"].append(len(wet))
        out["fx_flood_pct"].append(round(len(wet) / len(fac) * 100, 1) if fac else None)
        out["fx_schools_flood_n"].append(sum(1 for p in sch if p["wet"]))
        out["fx_students_flood_n"].append(stu_wet)
        out["fx_students_flood_pct"].append(round(stu_wet / stu * 100, 1) if stu else None)
        out["fx_road_flood_km"].append(round(road[1], 1))
        out["fx_road_flood_pct"].append(round(road[1] / road[0] * 100, 1) if road[0] else None)

    for g in ids:
        one(lambda p, g=g: p["geoid"] == g, roads.get(g, [0.0, 0.0]))
    one(lambda p: True, [sum(r[0] for r in roads.values()), sum(r[1] for r in roads.values())])
    counts = {}
    for p in every:
        c = counts.setdefault(p["kind"], [0, 0])
        c[0] += 1
        c[1] += p["wet"]
    return out, counts


def hazard_figures(every, flag, roads, ids, tag, not_mapped=frozenset()):
    """{key: [values for ids, then Puerto Rico]} for one more hazard: `every` the facilities (schools included, with their students), `flag` whether each stands
    in the hazard area, `roads` {geoid: [km of main road, km of it in the area]}. A municipio the hazard map does not cover gets no value; Puerto Rico's figures
    are those of the municipios it covers."""
    keys = [f"fx_{tag}_n", f"fx_{tag}_pct", f"fx_students_{tag}_pct", f"fx_road_{tag}_km", f"fx_road_{tag}_pct"]
    out = {k: [] for k in keys}

    def one(sel, road):
        fac = [(p, f) for p, f in zip(every, flag) if sel(p) and p["geoid"] not in not_mapped]
        stu = sum(p["students"] or 0 for p, _ in fac if p["kind"] == "Public schools")
        stu_in = sum(p["students"] or 0 for p, f in fac if p["kind"] == "Public schools" and f)
        n_in = sum(1 for _, f in fac if f)
        out[keys[0]].append(n_in)
        out[keys[1]].append(round(n_in / len(fac) * 100, 1) if fac else None)
        out[keys[2]].append(round(stu_in / stu * 100, 1) if stu else None)
        out[keys[3]].append(round(road[1], 1))
        out[keys[4]].append(round(road[1] / road[0] * 100, 1) if road[0] else None)

    for g in ids:
        if g in not_mapped:
            for k in keys:
                out[k].append(None)
            continue
        one(lambda p, g=g: p["geoid"] == g, roads.get(g, [0.0, 0.0]))
    kept = [r for g, r in roads.items() if g not in not_mapped]
    one(lambda p: True, [sum(r[0] for r in kept), sum(r[1] for r in kept)])
    counts = {}
    for p, f in zip(every, flag):
        if p["geoid"] in not_mapped:
            continue
        c = counts.setdefault(p["kind"], [0, 0])
        c[0] += 1
        c[1] += bool(f)
    return out, counts


def document(refresh=False, offline=False):
    names, fips = hs.municipalities()
    ids = list(fips)
    flood_fc = json.loads((hs.OUT / "flood.geojson").read_text(encoding="utf-8"))
    sfha, _ = exposure.flood_polygons(flood_fc)
    year, schools, no_point = newest_schools(refresh, offline)
    roads_fc, muni_fc = json.loads((hs.OUT / "traffic_roads.geojson").read_text(encoding="utf-8")), json.loads((hs.OUT / "municipios.geojson").read_text(encoding="utf-8"))
    pieces = road_pieces(roads_fc, muni_fc)
    roads = road_km(roads_fc, muni_fc, sfha, pieces)
    points = facility_points()
    fig, counts = figures(points, schools, roads, sfha, ids)
    every = points + [{"kind": "Public schools", **s} for s in schools]
    ex, ey = np.array([p["x"] for p in every], dtype=float), np.array([p["y"] for p in every], dtype=float)

    if offline and not (exposure.CACHE / "slr" / "gdb" / exposure.SLR_GDB).exists():
        raise SystemExit("facility_exposure --check: NOAA's sea level rise extents are not in cache/slr (python facility_exposure.py downloads them; --check never does)")
    slr_polys = list(exposure.slr_layer(exposure.slr_gdb(refresh=refresh and not offline), "slr", SLR_FT))
    samples = road_samples(pieces)   # NOAA's coastline is too detailed to cut every road piece by it; roads are read every 20 m for sea level rise and landslides
    slr_km = road_sampled_km(samples, lambda x, y: exposure.points_in_polygons(slr_polys, x, y))
    roads_slr = {g: [r[0], slr_km.get(g, 0.0)] for g, r in roads.items()}
    f_slr, c_slr = hazard_figures(every, exposure.points_in_polygons(slr_polys, ex, ey), roads_slr, ids, "slr")

    classify = ls_classifier(refresh, offline)
    ls_cls = classify(ex, ey)
    ls_km = road_sampled_km(samples, lambda x, y: classify(x, y) >= LS_HIGH)
    roads_ls = {g: [r[0], ls_km.get(g, 0.0)] for g, r in roads.items()}
    f_ls, c_ls = hazard_figures(every, ls_cls >= LS_HIGH, roads_ls, ids, "ls", LS_NOT_MAPPED)
    no_class = int(sum(1 for p, c in zip(every, ls_cls) if c == 0 and p["geoid"] not in LS_NOT_MAPPED))
    fig.update(f_slr)
    fig.update(f_ls)
    wet = [p.get("wet", False) for p in every]
    if not all("wet" in p for p in every):   # figures() marks each point it tested
        wet = list(exposure.points_in_polygons(sfha, ex, ey))
    side = side_files(every, wet, exposure.points_in_polygons(slr_polys, ex, ey), [c >= LS_HIGH and p["geoid"] not in LS_NOT_MAPPED for p, c in zip(every, ls_cls)],
                      dict(zip(ids, names)), year)
    y = str(datetime.date.today().year)
    kinds = "fire and EMS stations, police stations, city halls, libraries, public housing developments, power plants, airports and public schools"
    place = " It says where the building stands, not that it floods: floor heights are not known."
    slr_area = "NOAA's area flooded by 3 ft of sea level rise above today's high tide (connected to the ocean)"
    slr_place = " It says where the building stands today, not when or whether the sea reaches it."
    ls_area = "land the USGS map rates High, Very High or Extremely High for landslides triggered by intense rainfall (the most susceptible 30% of the main island)"
    ls_place = " It says what the ground under it is rated, not that a slide will happen there; Vieques and Culebra are not in the map."

    def var(key, label, unit, d, typ, definition, srcs=("fema_nfhl", "fx_layers"), ref=REF, **more):
        return {"key": key, "group": GROUP, "label": label, "unit": unit, "d": d, "type": typ, "sources": list(srcs), "ref": ref, "definition": definition, "family": "facility_exposure",
                "counted": False, "noPerHU": True, **more, "years": {y: fig[key]}}

    def slr(key, label, unit, d, typ, definition, **more):
        return var(key, label, unit, d, typ, definition, ("noaa_slr", "fx_layers"), REF_SLR, **more)

    def ls(key, label, unit, d, typ, definition, **more):
        return var(key, label, unit, d, typ, definition, ("usgs_landslide_map", "fx_layers"), REF_LS, noValue="Not mapped: the USGS susceptibility map covers the main island only", **more)

    vs = [
        var("fx_flood_n", "Public facilities in the 1% flood area (overlaid)", "", 0, "count", f"How many of the municipio's {kinds} stand inside FEMA's 1% annual chance flood area." + place, classes="jenks"),
        var("fx_flood_pct", "Public facilities in the 1% flood area, % of facilities (overlaid)", "%", 1, "rate", f"The share of the municipio's {kinds} that stand inside FEMA's 1% annual chance flood area." + place),
        var("fx_schools_flood_n", "Public schools in the 1% flood area (overlaid)", "", 0, "count", "How many of the municipio's open public schools stand inside FEMA's 1% annual chance flood area." + place, classes="jenks"),
        var("fx_students_flood_n", "Students of public schools in the 1% flood area (overlaid)", "", 0, "count", "The students enrolled in the public schools that stand inside FEMA's 1% annual chance flood area." + place, classes="jenks"),
        var("fx_students_flood_pct", "Students of public schools in the 1% flood area, % of students (overlaid)", "%", 1, "rate", "The share of the municipio's public school students who are enrolled in a school that stands inside FEMA's 1% annual chance flood area." + place),
        var("fx_road_flood_km", "Main roads in the 1% flood area, km (overlaid)", "km", 1, "count", "The kilometres of the municipio's main roads (arterials and major collectors with a traffic count) that run inside FEMA's 1% annual chance flood area. It says where the road runs, not that it floods: a road may be raised.", classes="jenks", noShare=True),
        var("fx_road_flood_pct", "Main roads in the 1% flood area, % of main road km (overlaid)", "%", 1, "rate", "The share of the kilometres of the municipio's main roads that run inside FEMA's 1% annual chance flood area. A road may be raised above it."),
        slr("fx_slr_n", "Public facilities in the 3 ft sea level rise area (overlaid)", "", 0, "count", f"How many of the municipio's {kinds} stand inside {slr_area}." + slr_place, classes="jenks"),
        slr("fx_slr_pct", "Public facilities in the 3 ft sea level rise area, % of facilities (overlaid)", "%", 1, "rate", f"The share of the municipio's {kinds} that stand inside {slr_area}." + slr_place),
        slr("fx_students_slr_pct", "Students of public schools in the 3 ft sea level rise area, % of students (overlaid)", "%", 1, "rate", f"The share of the municipio's public school students who are enrolled in a school that stands inside {slr_area}." + slr_place),
        slr("fx_road_slr_km", "Main roads in the 3 ft sea level rise area, km (overlaid)", "km", 1, "count", f"The kilometres of the municipio's main roads (arterials and major collectors with a traffic count) that run inside {slr_area}, read every 20 m. It says where the road runs today, not that it will be under water: a road may be raised.", classes="jenks", noShare=True),
        slr("fx_road_slr_pct", "Main roads in the 3 ft sea level rise area, % of main road km (overlaid)", "%", 1, "rate", f"The share of the kilometres of the municipio's main roads that run inside {slr_area}, read every 20 m. A road may be raised above it."),
        ls("fx_ls_n", "Public facilities on high landslide susceptibility land (overlaid)", "", 0, "count", f"How many of the municipio's {kinds} stand on {ls_area}." + ls_place, classes="jenks"),
        ls("fx_ls_pct", "Public facilities on high landslide susceptibility land, % of facilities (overlaid)", "%", 1, "rate", f"The share of the municipio's {kinds} that stand on {ls_area}." + ls_place),
        ls("fx_students_ls_pct", "Students of public schools on high landslide susceptibility land, % of students (overlaid)", "%", 1, "rate", f"The share of the municipio's public school students who are enrolled in a school that stands on {ls_area}." + ls_place),
        ls("fx_road_ls_km", "Main roads on high landslide susceptibility land, km (overlaid)", "km", 1, "count", f"The kilometres of the municipio's main roads (arterials and major collectors with a traffic count) that run on {ls_area}, read every 20 m." + ls_place, classes="jenks", noShare=True),
        ls("fx_road_ls_pct", "Main roads on high landslide susceptibility land, % of main road km (overlaid)", "%", 1, "rate", f"The share of the kilometres of the municipio's main roads that run on {ls_area}, read every 20 m." + ls_place),
    ]
    total_km = sum(r[0] for r in roads.values())
    return side, {"built": datetime.date.today().isoformat(), "as_of": datetime.date.today().isoformat(), "years": [int(y)], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs,
            "sources": {"fema_nfhl": {"name": "FEMA National Flood Hazard Layer, as the observatory's flood layer (flood.geojson)", "url": "https://www.fema.gov/flood-maps/national-flood-hazard-layer", "license": "US Government work; FEMA's metadata lists no access constraints"},
                        "noaa_slr": {"name": "NOAA Office for Coastal Management, Sea Level Rise Viewer data for Puerto Rico (3 ft above mean higher high water, connected to the ocean)", "url": "https://coast.noaa.gov/slrdata/", "license": "No license stated; NOAA's disclaimer applies"},
                        "usgs_landslide_map": {"name": "USGS landslide susceptibility map of Puerto Rico (Hughes and Schulz, 2020; GIS layer, 2021), read from the first author's tile copy as landslide.py does", "url": "https://doi.org/10.5066/P990ZP4C", "license": "US federal government data (public domain); the data release states CC0 1.0"},
                        "fx_layers": {"name": "PR Data Observatory facility layers (USGS, OpenStreetMap, HUD, EIA, FAA), the NCES school directory through the Urban Institute's Education Data API, and FHWA HPMS main roads",
                                      "url": "https://observatory.foundationpr.org/dictionary.html", "license": "Each layer keeps its source's terms: US federal sources (USGS, HUD, EIA, FAA, NCES, FHWA); police stations and city halls are OpenStreetMap (ODbL); the Education Data API asks for credit (ODC-By)"}},
            "notes": {"kind": "overlaid: one published layer laid on another (HANDOFF decision 107)", "flood_area": "FEMA's 1% annual chance flood area (Special Flood Hazard Area), from the observatory's simplified flood layer",
                      "sea_level_rise": f"NOAA's extent of {SLR_FT} ft of sea level rise above mean higher high water, connected to the ocean; low-lying areas not connected are left out",
                      "landslide": "the USGS susceptibility classes High, Very High and Extremely High under each point (zoom-15 tiles, about 4.5 m); roads read every 20 m; Vieques and Culebra are not in the map",
                      "tested_slr": {k: {"facilities": v[0], "in_the_area": int(v[1])} for k, v in sorted(c_slr.items())},
                      "tested_landslide": {k: {"facilities": v[0], "on_high_or_above": int(v[1])} for k, v in sorted(c_ls.items())},
                      "landslide_points_without_a_class": no_class,
                      "school_year": year, "schools_without_a_point": no_point,
                      "tested": {k: {"facilities": v[0], "in_the_flood_area": int(v[1])} for k, v in sorted(counts.items())},
                      "main_road_km": round(total_km, 1), "left_out": "bridges (over water by design), public housing developments whose location is approximate, and points that share their coordinates with another point of the same layer (several facilities listed at one address)",
                      "left_out_stacked": dict(sorted(STACKED.items())), "overlap": "library points within 150 m of an open public school may be the same building; both are counted",
                      "drawn": "the public schools as a map layer (public_schools.geojson) and the hazard flags of every facility point in its pop-up (facility_hazards.json)"}}


def build(refresh=False, check=False):
    (schools, hazards), doc = document(refresh and not check, offline=check)
    files = [(OUT, doc), (OUT_SCHOOLS, schools), (OUT_HAZARDS, hazards)]
    if check:
        drop = lambda d: {**d, "built": None, "as_of": None}   # noqa: E731
        bad = 0
        for path, d in files:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            same = old is not None and drop(old) == drop(json.loads(json.dumps(d, ensure_ascii=False)))
            print(f"  {path.name}: {'matches' if same else 'DIFFERS'}")
            bad += not same
        return 1 if bad else 0
    for path, d in files:
        path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB, {len(doc['vars'])} variables), {OUT_SCHOOLS.name} ({len(schools['features'])} schools, "
        f"{OUT_SCHOOLS.stat().st_size / 1024:.1f} KB) and {OUT_HAZARDS.name} ({sum(map(len, hazards['layers'].values()))} flagged points)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
