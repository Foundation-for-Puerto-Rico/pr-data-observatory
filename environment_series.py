"""Environment for the PR Data Observatory (Phase 3, item 11, data wave E), for the 78 municipalities and Puerto Rico.

    python environment_series.py             # build site/data/environment_series.json and site/data/hazard_series.json (downloads only what is missing)
    python environment_series.py --refresh   # download again
    python environment_series.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Five sources, no key, US federal data (public domain):
  FEMA National Risk Index (county table, FEMA's own ArcGIS Online service): expected annual loss in dollars, in all and for six hazards. The composite risk score,
      social vulnerability and community resilience are empty for Puerto Rico; the file says so and publishes none of them.
  Census Bureau Community Resilience Estimates for Puerto Rico (2019, 2021-2024): the share of residents with no, one or two, or three or more risk factors, with
      the margin of error, for each municipality and the island.
  USGS data release "Map of slope-failure locations in Puerto Rico after Hurricane Maria" (Hughes and others, 2019), read from the copy its first author keeps at
      UPRM (the USGS catalogue refuses scripts): 71,431 points, each placed in the municipality whose boundary holds it. The barrio names of the copy are not used.
  US Fish and Wildlife Service National Wetlands Inventory (its map service): the wetland polygons of Puerto Rico, split among the municipal boundaries.
  USGS ComCat earthquake catalogue: earthquakes of magnitude 2.5 or more around Puerto Rico each year, each placed in the municipality that holds its epicenter or,
      offshore, the nearest municipality within 25 km of the coast.

Outputs:
  environment_series.json   one snapshot (the shape of health_series.json): hazard loss, landslides, wetlands. Each dataset's year is its source's.
  hazard_series.json        one value a year (the shape of economy_series.json): community resilience (with margins) and earthquakes
"""

import csv
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "environment"
OUT = hs.OUT / "environment_series.json"
OUT_HZ = hs.OUT / "hazard_series.json"
UA = {"User-Agent": "Mozilla/5.0 (pr-digital-twin open-data build; Foundation for Puerto Rico)"}
log = hs.log
NRI = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0/query"
NRI_HAZ = [("hurricane", "HRCN", "hurricane (wind)"), ("earthquake", "ERQK", "earthquake"), ("inland_flood", "IFLD", "inland (river and rain) flooding"),
           ("landslide", "LNDS", "landslide"), ("coastal_flood", "CFLD", "coastal flooding"), ("tsunami", "TSUN", "tsunami")]
NRI_EMPTY = ["RISK_SCORE", "SOVI_SCORE", "RESL_SCORE"]   # empty for Puerto Rico in FEMA's table: checked on every build
CRE = "https://www2.census.gov/programs-surveys/demo/datasets/community-resilience/{y}/pr/CRE{yy}_PR{part}.csv"
CRE_YEARS = [2019, 2021, 2022, 2023, 2024]
CRE_KEYS = [("cre_risk0_pct", "PRED0"), ("cre_risk12_pct", "PRED12"), ("cre_risk3_pct", "PRED3")]
SLIDES = "https://services5.arcgis.com/TQ9qkk0dURXSP7LQ/arcgis/rest/services/DERRUMBES_HURACAN_MARIA/FeatureServer/0/query"
NWI = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query"
NWI_BOX = "-67.95,17.85,-65.2,18.55"   # Puerto Rico with Mona, Desecheo, Vieques and Culebra; the US Virgin Islands start east of -65.1
WETLAND = {"Estuarine and Marine Wetland", "Freshwater Emergent Wetland", "Freshwater Forested/Shrub Wetland"}   # NWI's wetland types (deepwater, lakes, ponds and rivers left out)
NWI_PHOTO_YEAR = 1983   # almost all of the wetland area lies in the inventory's projects mapped from colour-infrared photographs of February 1983 (the coasts); most of the interior is its scalable product (Data_Source service); see docs/environment.md
MANGROVE = ("E2FO3", "E2SS3")   # estuarine intertidal forested or scrub-shrub, broad-leaved evergreen: Puerto Rico's mangroves
QUAKES = "https://earthquake.usgs.gov/fdsnws/event/1/query"
QUAKE_BOX = {"minlatitude": 17.4, "maxlatitude": 19.0, "minlongitude": -68.4, "maxlongitude": -64.9}   # wide enough for 25 km around every coast
QUAKE_FIRST, QUAKE_KM = 2000, 25
PR_CRS = "EPSG:32161"   # NAD83 / Puerto Rico and Virgin Islands, metres: areas and distances
FLOORS = {"nri": 78, "slides": 70000, "wetlands": 12000}   # the 2026-10 sources have 78 municipios, 71,431 slope failures and about 16,000 polygons of all types

SOURCES = {
    "fema_nri": {"name": "FEMA — National Risk Index, county table", "url": "https://hazards.fema.gov/nri/", "license": "US federal government data (public domain)",
                 "note": "Expected annual loss for each municipality, in all and by hazard. FEMA leaves the composite risk score, social vulnerability and community resilience empty for Puerto Rico."},
    "census_cre": {"name": "Census Bureau — Community Resilience Estimates for Puerto Rico", "url": "https://www.census.gov/programs-surveys/community-resilience-estimates.html", "license": "US federal government data (public domain); cite the Census Bureau",
                   "note": "Share of residents with no, one or two, or three or more risk factors, with margins of error at 90% confidence."},
    "usgs_slope_failures": {"name": "USGS — Map of slope-failure locations in Puerto Rico after Hurricane María (Hughes and others, 2019)", "url": "https://doi.org/10.5066/P9BVMD74", "license": "US federal government data (public domain)",
                            "note": "Read from the copy the data release's first author keeps at the University of Puerto Rico at Mayagüez (the USGS catalogue refuses scripts). Counted by point in the municipal boundary."},
    "usfws_nwi": {"name": "US Fish and Wildlife Service — National Wetlands Inventory", "url": "https://www.fws.gov/program/national-wetlands-inventory", "license": "US federal government data (public domain)",
                  "note": "Wetland polygons of Puerto Rico from the inventory's map service, split among the municipal boundaries."},
    "usgs_comcat": {"name": "USGS — ComCat earthquake catalogue", "url": "https://earthquake.usgs.gov/fdsnws/event/1/", "license": "US federal government data (public domain)",
                    "note": "Earthquakes of magnitude 2.5 or more around Puerto Rico, by year."},
}


def get(url, **kw):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 300), **kw)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"environment_series: {url} failed: {e}")


def cached(name, fetch, refresh, offline):
    path = CACHE / name
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"environment_series --check: {name} is not in the cache")
    d = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    return d


# ── Sources ──────────────────────────────────────────────────────────────────

def nri_rows():
    fields = ["STCOFIPS", "NRI_VER", "EAL_VALT"] + [c + "_EALT" for _, c, _ in NRI_HAZ] + NRI_EMPTY
    j = get(NRI, params={"where": "STATEFIPS='72'", "outFields": ",".join(fields), "returnGeometry": "false", "f": "json"}).json()
    if "features" not in j:
        raise SystemExit(f"environment_series: the National Risk Index service answered {str(j)[:200]}")
    rows = [f["attributes"] for f in j["features"]]
    log(f"  National Risk Index: {len(rows)} municipios, version {rows[0].get('NRI_VER') if rows else '?'}")
    return rows


def cre_rows():
    out = {}
    for y in CRE_YEARS:
        yy = str(y)[2:]
        keep = ["GEO_ID", "POPUNI"] + [f"{p}_{s}" for _, p in CRE_KEYS for s in ("PE", "PM")]
        rows = []
        for part in ("_MUNICIPIO", ""):
            r = get(CRE.format(y=y, yy=yy, part=part))
            if r is None:
                raise SystemExit(f"environment_series: the Community Resilience Estimates of {y} ({part or 'tract'} file) are not where they were")
            rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
            missing = [c for c in keep if c not in (rd.fieldnames or [])]
            if missing:
                raise SystemExit(f"environment_series: CRE {y}{part} has no column {missing}")
            for x in rd:
                g = x["GEO_ID"]
                if (part and g.startswith("0500000US72")) or (not part and g == "0400000US72"):
                    rows.append({c: x[c] for c in keep})
        out[str(y)] = rows
        log(f"  Community Resilience Estimates {y}: {len(rows)} rows")
    return out


def arcgis_points(url, extra=None):
    """Every point of a hosted layer as [lon, lat] (paged; attributes not kept)."""
    pts, off = [], 0
    while True:
        j = get(url, params={"where": "1=1", "outFields": "", "returnGeometry": "true", "outSR": "4326", "f": "json", "resultOffset": off, "resultRecordCount": 2000, "orderByFields": "FID", **(extra or {})}).json()
        fs = j.get("features")
        if fs is None:
            raise SystemExit(f"environment_series: {url} answered {str(j)[:200]}")
        pts += [[round(f["geometry"]["x"], 6), round(f["geometry"]["y"], 6)] for f in fs if f.get("geometry")]
        if not fs or not j.get("exceededTransferLimit"):
            return pts
        off += len(fs)


def slide_points():
    pts = arcgis_points(SLIDES)
    log(f"  slope failures after Hurricane María: {len(pts)}")
    return pts


def wetland_polys():
    """The wetland polygons of Puerto Rico: [{a: NWI code, t: type, g: rings}], wetland types only."""
    geo = {"geometry": NWI_BOX, "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects"}
    ids = get(NWI, params={"where": "1=1", "returnIdsOnly": "true", "f": "json", **geo}).json().get("objectIds") or []
    ids.sort()
    out = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        r = requests.post(NWI, data={"objectIds": ",".join(map(str, chunk)), "outFields": "ATTRIBUTE,WETLAND_TYPE", "returnGeometry": "true", "outSR": "4326", "geometryPrecision": 6, "f": "json"}, headers=UA, timeout=(30, 300))
        r.raise_for_status()
        j = r.json()
        if "features" not in j:
            raise SystemExit(f"environment_series: the wetlands service answered {str(j)[:200]}")
        for f in j["features"]:
            a = f["attributes"]
            if a.get("WETLAND_TYPE") in WETLAND and f.get("geometry"):
                out.append({"a": a.get("ATTRIBUTE") or "", "t": a["WETLAND_TYPE"], "g": f["geometry"]["rings"]})
    log(f"  National Wetlands Inventory: {len(ids)} polygons in the box, {len(out)} wetlands")
    return {"retrieved": date.today().isoformat(), "in_box": len(ids), "polys": out}


def quake_rows(y):
    r = get(QUAKES, params={"format": "csv", "starttime": f"{y}-01-01", "endtime": f"{y + 1}-01-01", "minmagnitude": 2.5, "orderby": "time-asc", "limit": 20000, **QUAKE_BOX})
    rd = csv.DictReader(io.StringIO(r.text))
    rows = [[round(float(x["longitude"]), 4), round(float(x["latitude"]), 4), float(x["mag"])] for x in rd if x.get("mag")]
    if len(rows) >= 20000:
        raise SystemExit(f"environment_series: ComCat {y} reached its 20,000-event limit: split the year")
    log(f"  ComCat {y}: {len(rows)} earthquakes of magnitude 2.5 or more")
    return rows


# ── Geometry ─────────────────────────────────────────────────────────────────

class Munis:
    """The municipal boundaries (site/data/municipios.geojson), projected to metres, with land areas from the Census."""

    def __init__(self, ids):
        import shapely
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        self.shapely = shapely
        self.tf = Transformer.from_crs("EPSG:4326", PR_CRS, always_xy=True)
        fc = json.loads((hs.OUT / "municipios.geojson").read_text(encoding="utf-8"))
        names, fips = hs.municipalities()
        by_name = dict(zip(names, fips))
        geoms, keys, land = [], [], {}
        for f in fc["features"]:
            k = by_name[f["properties"]["municipality"]]
            geoms.append(self.proj(shape(f["geometry"])))
            keys.append(k)
            land[k] = int(f["properties"]["AREALAND"]) / 1e6
        assert sorted(keys) == sorted(ids)
        self.geoms, self.keys, self.land = geoms, keys, land
        self.tree = STRtree(geoms)

    def proj(self, g):
        return self.shapely.transform(g, lambda xy: __import__("numpy").column_stack(self.tf.transform(xy[:, 0], xy[:, 1])))

    def points(self, lonlat, km):
        """[fips or None] for each (lon, lat): the boundary that holds it, else the nearest within `km`."""
        import numpy as np
        if not lonlat:
            return []
        a = np.array(lonlat, dtype=float)
        x, y = self.tf.transform(a[:, 0], a[:, 1])
        pts = self.shapely.points(x, y)
        out = [None] * len(pts)
        pi, gi = self.tree.query(pts, predicate="within")
        for p, g in zip(pi, gi):
            out[p] = self.keys[g]
        rest = [i for i, k in enumerate(out) if k is None]
        if rest:
            pi, gi = self.tree.query_nearest(pts[rest], max_distance=km * 1000)
            for p, g in zip(pi, gi):   # equally near two municipios: the lower FIPS code, so the counts do not depend on the tree's order
                k = self.keys[g]
                if out[rest[p]] is None or k < out[rest[p]]:
                    out[rest[p]] = k
        return out


def rings_polygon(rings):
    """An Esri polygon (outer rings clockwise, holes counter-clockwise) as a shapely geometry."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid
    outer, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        p = Polygon(r)
        (holes if p.exterior.is_ccw else outer).append(p)
    shell = unary_union([make_valid(p) for p in outer]) if outer else None
    if shell is None:
        return None
    if holes:
        shell = shell.difference(unary_union([make_valid(h) for h in holes]))
    return shell


# ── Build ────────────────────────────────────────────────────────────────────

def var(key, group, label, unit, d, typ, sources, ref, definition, values, family="environment", **extra):
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": ref, "definition": definition, "family": family, "counted": False, **extra, "years": values}


def compute(refresh=False, offline=False, floors=FLOORS):
    names, fips = hs.municipalities()
    ids = list(fips)
    g = json.loads((hs.OUT / "economy_series.json").read_text(encoding="utf-8"))["geo"]
    if g["ids"][:len(ids)] != ids or g["names"][:len(ids)] != names:
        raise SystemExit("environment_series: the municipalities are not in the order of economy_series.json")
    log("Environment: hazard loss (FEMA NRI), resilience (Census CRE), landslides (USGS), wetlands (USFWS NWI), earthquakes (USGS ComCat)")
    M = Munis(ids)
    column = lambda c, r=None: [(round(c.get(f, 0), r) if r is not None else c.get(f, 0)) for f in ids] + [round(sum(c.get(f, 0) for f in ids), r) if r is not None else sum(c.get(f, 0) for f in ids)]
    notes, vs = {}, []

    # hazard loss
    nri = cached("nri_counties.pr.json", nri_rows, refresh, offline)
    if floors and len(nri) < floors["nri"]:
        raise SystemExit(f"environment_series: the National Risk Index has {len(nri)} municipios of Puerto Rico")
    by = {r["STCOFIPS"]: r for r in nri}
    if sorted(by) != sorted(ids):
        raise SystemExit("environment_series: the National Risk Index's municipios are not the 78")
    filled = [c for c in NRI_EMPTY if any(r.get(c) is not None for r in nri)]
    ver = sorted({r["NRI_VER"] for r in nri})
    if len(ver) != 1:
        raise SystemExit(f"environment_series: the National Risk Index rows mix versions {ver}")
    vy = str(int(ver[0][-4:]))
    notes["nri"] = {"version": ver[0], "empty_for_puerto_rico": [c for c in NRI_EMPTY if c not in filled], "filled_now": filled,
                    "note": "FEMA leaves the composite risk score, social vulnerability and community resilience empty for Puerto Rico; the Community Resilience Estimates (hazard_series.json) fill part of the gap."}
    G1, NR = "Natural hazard risk", f"FEMA National Risk Index ({ver[0]}), expected annual loss"
    lossdef = "FEMA's estimate of the average loss each year, in dollars, to buildings, agriculture and lives (lives valued in dollars by FEMA's rule)"
    vs.append(var("nri_eal_total", G1, "Expected annual loss from natural hazards, $ a year", "$", 0, "total$", ["fema_nri"], NR,
                  lossdef + ", from the 18 hazards of the National Risk Index. Puerto Rico's value is the sum of the municipios. A model estimate, not a record of losses.",
                  {vy: column({f: by[f]["EAL_VALT"] or 0 for f in ids}, 0)}, noPerHU=True, tag="estimate", classes="jenks"))
    for key, code, word in NRI_HAZ:
        vals = {f: by[f][code + "_EALT"] for f in ids}
        if all(v is None for v in vals.values()):
            raise SystemExit(f"environment_series: the National Risk Index has no {word} loss for Puerto Rico")
        vs.append(var(f"nri_eal_{key}", G1, f"Expected annual loss from {word}, $ a year", "$", 0, "total$", ["fema_nri"], NR,
                      f"{lossdef}, from {word} alone. Blank where FEMA does not model the hazard for the municipio. A model estimate, not a record of losses.",
                      {vy: [None if vals[f] is None else round(vals[f]) for f in ids] + [round(sum(v or 0 for v in vals.values()))]}, noPerHU=True, tag="estimate", classes="jenks"))

    # landslides
    sp = cached("slope_failures_maria.json", slide_points, refresh, offline)
    if floors and len(sp) < floors["slides"]:
        raise SystemExit(f"environment_series: {len(sp)} slope failures (the data release has 71,431)")
    where = M.points(sp, 1)
    lost = sum(w is None for w in where)
    slides = Counter(w for w in where if w)
    notes["landslides"] = {"points": len(sp), "placed": len(sp) - lost, "more_than_1_km_from_a_boundary": lost}
    G2, SL = "Landslides", "USGS slope-failure locations after Hurricane María (Hughes and others, 2019)"
    vs.append(var("landslides_maria", G2, "Landslides mapped after Hurricane María (2017)", "", 0, "count", ["usgs_slope_failures"], SL,
                  "Slope failures (landslides, debris flows and rock falls) that USGS and UPRM geologists mapped from aerial images taken after Hurricane María, by the municipal boundary that holds each one's point. It shows where the 2017 rains set off slides, a record of one storm, not a forecast.",
                  {"2017": column(slides)}, noPerHU=True, classes="jenks"))
    vs.append(var("landslides_maria_km2", G2, "Landslides mapped after Hurricane María, per km² of land", "", 1, "ratio", ["usgs_slope_failures", "census_tiger"], SL,
                  "The same slope failures divided by the municipio's land area in square kilometres (Census).",
                  {"2017": [round(slides.get(f, 0) / M.land[f], 1) for f in ids] + [round(sum(slides.values()) / sum(M.land.values()), 1)]}, noPerHU=True))

    # wetlands
    wd = cached("nwi_wetlands.pr.json", wetland_polys, refresh, offline)
    if floors and wd["in_box"] < floors["wetlands"]:
        raise SystemExit(f"environment_series: {wd['in_box']} wetland inventory polygons (2026-10 has about 16,000)")
    wet, mang, outside, skipped = Counter(), Counter(), 0.0, 0
    for p in wd["polys"]:
        geom = rings_polygon(p["g"])
        if geom is None or geom.is_empty:
            skipped += 1
            continue
        geom = M.proj(geom)
        total = geom.area
        parts = [(M.keys[j], geom.intersection(M.geoms[j]).area) for j in M.tree.query(geom, predicate="intersects")]
        parts = [(k, a) for k, a in parts if a > 0]
        if parts:
            rest = total - sum(a for _, a in parts)
            big = max(parts, key=lambda x: x[1])[0]
            parts = [(k, a + (rest if k == big and rest > 0 else 0)) for k, a in parts]   # the part beyond the drawn coast goes to the municipio with the largest share
        else:
            j = M.tree.query_nearest(geom, max_distance=2000)
            if len(j) == 0:
                outside += total
                continue
            parts = [(M.keys[j[0]], total)]
        mg = p["a"].startswith(MANGROVE)
        for k, a in parts:
            wet[k] += a / 1e6
            if mg:
                mang[k] += a / 1e6
    notes["wetlands"] = {"polygons_in_box": wd["in_box"], "wetland_polygons": len(wd["polys"]), "unreadable": skipped, "km2_more_than_2_km_offshore": round(outside / 1e6, 2),
                         "retrieved": wd["retrieved"], "mapped_from": "colour-infrared aerial photographs of February 1983 for the coasts (about a third of the island, holding almost all of the wetland area); most of the interior is the inventory's interim scalable product, and a few small areas come from later photographs", "wetland_types": sorted(WETLAND), "mangrove_codes": list(MANGROVE)}
    G3, NW = "Wetlands", "USFWS National Wetlands Inventory"
    ny = str(NWI_PHOTO_YEAR)
    vs.append(var("wetland_km2", G3, "Wetlands, km²", "km²", 1, "count", ["usfws_nwi"], NW,
                  "The area of the wetlands the National Wetlands Inventory maps in the municipio, almost all of it from aerial photographs of 1983 (estuarine and marine wetlands, among them mangroves, beaches and tidal flats; freshwater marshes; freshwater swamps and shrub wetlands), in square kilometres. Lakes, ponds, rivers and open water are left out. A wetland across a boundary is split; the part beyond the drawn coast goes to the municipio with the largest share.",
                  {ny: column(wet, 2)}, noPerHU=True, classes="jenks"))
    vs.append(var("wetland_pct", G3, "Wetlands, % of land area", "%", 1, "rate", ["usfws_nwi", "census_tiger"], NW,
                  "Wetland area divided by the municipio's land area (Census), in percent. Coastal wetlands can lie partly on what the Census counts as water.",
                  {ny: [round(wet.get(f, 0) / M.land[f] * 100, 2) for f in ids] + [round(sum(wet.values()) / sum(M.land.values()) * 100, 2)]}))
    vs.append(var("mangrove_km2", G3, "Mangroves, km²", "km²", 1, "count", ["usfws_nwi"], NW,
                  "The area of the inventory's estuarine intertidal forested and scrub-shrub wetlands with broad-leaved evergreen plants (codes E2FO3 and E2SS3), which in Puerto Rico are mangroves, in square kilometres, as mapped from photographs of 1983.",
                  {ny: column(mang, 2)}, noPerHU=True, classes="jenks"))

    # yearly: resilience and earthquakes
    cre = cached("cre_pr.json", cre_rows, refresh, offline)
    hv, hm, cnotes = {k: {} for k, _ in CRE_KEYS}, {k: {} for k, _ in CRE_KEYS}, {}
    num = lambda s: None if s in ("", None) or float(s) < 0 else float(s)
    for y, rows in sorted(cre.items()):
        rb = {r["GEO_ID"][-5:] if r["GEO_ID"].startswith("0500000US") else "72": r for r in rows}
        if sorted(k for k in rb if k != "72") != sorted(ids) or "72" not in rb:
            raise SystemExit(f"environment_series: CRE {y} does not have the 78 municipios and Puerto Rico")
        for key, p in CRE_KEYS:
            hv[key][y] = [num(rb[f][p + "_PE"]) for f in ids + ["72"]]
            hm[key][y] = [num(rb[f][p + "_PM"]) for f in ids + ["72"]]
        tot = [sum(hv[k][y][i] or 0 for k, _ in CRE_KEYS) for i in range(79)]
        if any(abs(t - 100) > 0.5 for t in tot):
            raise SystemExit(f"environment_series: CRE {y}: the three shares do not add up to 100 for some place")
        cnotes[y] = {"population_covered": int(float(rb["72"]["POPUNI"]))}
    G4, CR = "Community resilience", "Census Bureau Community Resilience Estimates for Puerto Rico"
    crdef = "The Census Bureau counts, for each resident, ten risk factors that make it harder to withstand and recover from a disaster: household income below 130% of the poverty line, only one or no adults aged 18 to 64 in the household, more than 0.75 people per room, limited English or no one with a high-school diploma in the household, no one employed full-time year-round, a disability, no health insurance, age 65 or over, no vehicle and no broadband. Modelled from the Puerto Rico Community Survey and other records. The ten factors are the same in every release, but from 2023 the Census Bureau computes municipio margins a new way (smaller), so compare margins across 2022 and 2023 with care."
    hz = [var("cre_risk0_pct", G4, "Residents with no risk factors, % (Community Resilience Estimates)", "%", 1, "rate", ["census_cre"], CR, "Residents with none of the risk factors, in percent of the residents the estimates cover. " + crdef, hv["cre_risk0_pct"], moe=hm["cre_risk0_pct"], tag="estimate"),
          var("cre_risk12_pct", G4, "Residents with one or two risk factors, %", "%", 1, "rate", ["census_cre"], CR, "Residents with one or two of the risk factors, in percent. " + crdef, hv["cre_risk12_pct"], moe=hm["cre_risk12_pct"], tag="estimate"),
          var("cre_risk3_pct", G4, "Residents with three or more risk factors, %", "%", 1, "rate", ["census_cre"], CR, "Residents with three or more of the risk factors, in percent: the Census Bureau's measure of the population least able to recover from a disaster. " + crdef, hv["cre_risk3_pct"], moe=hm["cre_risk3_pct"], tag="estimate")]
    last = date.today().year - 1   # whole years only
    q25, q4, qnotes = {}, {}, {}
    for y in range(QUAKE_FIRST, last + 1):
        rows = cached(f"comcat_{y}.json", lambda y=y: quake_rows(y), refresh and y >= last - 1, offline)
        where = M.points([r[:2] for r in rows], QUAKE_KM)
        a, b = Counter(), Counter()
        for w, r in zip(where, rows):
            if w:
                a[w] += 1
                b[w] += r[2] >= 4
        q25[str(y)], q4[str(y)] = column(a), column(b)
        qnotes[str(y)] = {"in_box": len(rows), "placed": sum(a.values()), "strongest": max((r[2] for r, w in zip(rows, where) if w), default=None)}
    G5, QC = "Earthquakes", "USGS ComCat earthquake catalogue"
    qdef = f"Earthquakes in USGS's catalogue whose epicenter is in the municipio or, offshore, closer to it than to any other municipio and within {QUAKE_KM} km of its coast. Each earthquake counts once, so the municipal values add up to Puerto Rico's. A count of events, not of damage: most are felt little or not at all."
    hz += [var("quakes_m25", G5, "Earthquakes of magnitude 2.5 or more", "", 0, "count", ["usgs_comcat"], QC, qdef, q25, noPerHU=True),
           var("quakes_m4", G5, "Earthquakes of magnitude 4.0 or more", "", 0, "count", ["usgs_comcat"], QC, qdef.replace("Earthquakes in", "Earthquakes of magnitude 4.0 or more in"), q4, noPerHU=True)]
    geo = {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}
    src = lambda ks: {k: SOURCES[k] for k in ks}
    snap = {"as_of": wd["retrieved"][:7],
            "years": sorted({int(y) for v in vs for y in v["years"]}), "geo": geo, "vars": vs, "sources": src(["fema_nri", "usgs_slope_failures", "usfws_nwi"]), "notes": notes}
    yrs = sorted({int(y) for v in hz for y in v["years"]})
    hzd = {"years": yrs, "geo": geo, "vars": hz, "sources": src(["census_cre", "usgs_comcat"]), "notes": {"cre": cnotes, "earthquakes": qnotes}}
    return snap, hzd


def build(refresh=False, check=False):
    snap, hz = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT, snap), (OUT_HZ, hz)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python environment_series.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {len(d['vars'])} variables, {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
