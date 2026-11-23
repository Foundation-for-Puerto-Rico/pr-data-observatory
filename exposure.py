"""Exposure series for the PR Data Observatory (plan item 5): how many residents and housing units are inside a hazard or protected land, or near transit,
for every municipio, barrio and census tract.

    python exposure.py                  # build site/data/exposure_municipio.json, exposure_barrio.json and exposure_tract.json
    python exposure.py --transit        # recompute only the transit families from the published stops (what the nightly refresh does)
    python exposure.py --surge          # add or recompute only the storm surge families (NOAA NHC SLOSH maps, read once into cache/surge)
    python exposure.py --check          # check the published files (no network)
    python exposure.py --labels         # write the Spanish of the dataset names the engine builds from them (i18n_src/es/labels_exposure.json)
    python exposure.py --as-of 2027-02-02   # the date "a current timetable" is judged on (default: today)

Method, in one paragraph. The unit of count is the 2020 Census block (41,987 in Puerto Rico; geo.py and network.py keep them with their ids). A block is counted
whole, by its internal point (the Census Bureau's point guaranteed to lie inside it): in a layer if the point is inside a polygon, near transit if the point is within
400 m of a stop. Its 2020 residents and housing units are then added up to the municipio, the barrio and the tract that hold it (counts add up exactly between levels).
Nothing here is measured: it is computed from open layers and labelled so (see docs/exposure.md).

Families (each has residents, "pop", and housing units, "hu", per area):
  flood_sfha, flood_any          FEMA flood hazard areas (site/data/flood.geojson): the 1% annual chance area, and that or the 0.2% annual chance area
  slr_1ft ... slr_10ft           NOAA sea level rise, 1 to 10 ft above high tide, ocean-connected inundation
  low_1ft ... low_10ft           NOAA low-lying areas at the same heights that are not connected to the ocean and "may flood"
  surge_cat1 ... surge_cat5     NOAA National Hurricane Center storm surge (SLOSH Maximum of MEOWs, high tide, 2018 maps): the block point is flooded by the near worst
                                 case surge of a category 1 to 5 hurricane, at any depth
  surge_deep_cat1 ... _cat5      the same, under 3 ft of water or more (the maps give the depth in 1 ft bands; NHC's own map starts a colour at 3 ft)
  protected, protected_strict    USGS PAD-US protected areas (not proclamation boundaries), and those with GAP status 1 or 2
  stop_any ... stop_sun          within 400 m of a stop: any mapped stop; a stop with a timetable on file; a stop with a current timetable; a frequent stop (20 or more
                                 weekday departures); a current stop with Saturday service; with Sunday service (the classes access.py gives places, on the block points
                                 the transit coverage uses, rounded to 4 decimals, so the municipal totals equal the Transit tab's)
  walk_cur, walk_freq            within a 400 m walk along mapped roads (walknet.py, site/data/roads.bin) of a stop with a current timetable, and of a frequent
                                 one: access.py's walking rule (tw_m, tw_calls) on the same block points. A block with no walkable road within 150 m keeps its
                                 straight-line test. Without roads.bin the two copy stop_cur and stop_freq, and the log says so.
"""
import argparse
import json
import os
import sys
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

import access
import geo
import network

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache"
LEVELS = ("municipio", "barrio", "tract")
FILE = {lv: f"exposure_{lv}.json" for lv in LEVELS}
FEET = tuple(range(1, 11))
SLR_ZIP = "https://chs.coast.noaa.gov/htdata/Inundation/SLR/BulkDownload/Sea_Level_Rise_Vectors/PR/PR_slr_data_dist.zip"
SLR_GDB = "PR_slr_final_dist.gdb"
SURGE_ZIP = "https://www.nhc.noaa.gov/gis/hazardmaps/PR_SLOSH_MOM_Inundation.zip"
SURGE_TIF = "PR_SLOSH_MOM_Inundation_11_2018/PR_Category{c}_MOM_Inundation_HighTide.tif"
CATS = (1, 2, 3, 4, 5)
SURGE_DEEP_BIN = 4   # the band codes: 1 = under 1 ft above ground, 2 = 1 to 2 ft, ..., so 4 and up = 3 ft or more
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}
VERSION = 1

MEASURES = {"pop": {"en": "Residents (2020 Census)", "es": "Residentes (Censo 2020)"},
            "hu": {"en": "Housing units (2020 Census)", "es": "Unidades de vivienda (Censo 2020)"}}
GROUPS = {"flood": {"en": "Flood hazard · FEMA", "es": "Riesgo de inundación · FEMA"},
          "slr": {"en": "Sea level rise · NOAA (connected to the ocean)", "es": "Aumento del nivel del mar · NOAA (conectado al océano)"},
          "low": {"en": "Sea level rise · NOAA (low-lying areas, not connected to the ocean)", "es": "Aumento del nivel del mar · NOAA (áreas bajas, sin conexión con el océano)"},
          "surge": {"en": "Storm surge · NOAA NHC (near worst case, high tide)", "es": "Marejada ciclónica · NOAA NHC (casi el peor caso, marea alta)"},
          "protected": {"en": "Protected areas · USGS PAD-US", "es": "Áreas protegidas · USGS PAD-US"},
          "transit": {"en": "Transit stops within 400 m", "es": "Paradas de transporte a 400 m o menos"}}
BASIS = {"en": "Computed, not measured: each 2020 Census block is counted whole by its internal point (inside a polygon or a flooded raster cell, or within 400 m of a stop), with the block's 2020 residents and housing units.",
         "es": "Calculado, no medido: cada bloque censal de 2020 se cuenta completo según su punto interno (dentro de un polígono o de una celda inundada de un ráster, o a 400 m o menos de una parada), con los residentes y las unidades de vivienda del bloque en 2020."}
INPUTS = {"blocks": "2020 Census blocks (TIGERweb layer 10): residents, housing units, internal point",
          "flood": "FEMA National Flood Hazard Layer, as published in flood.geojson (outlines simplified by about 5 m)",
          "slr": "NOAA Office for Coastal Management, Sea Level Rise Viewer data for Puerto Rico, 1 to 10 ft above mean higher high water (2017 data, file dated 2023-09-27)",
          "surge": "NOAA National Hurricane Center, SLOSH Maximum of MEOWs storm surge maps for Puerto Rico, category 1 to 5 at high tide (maps dated November 2018)",
          "protected": "USGS PAD-US, as published in protected.geojson",
          "transit": "stops (transport.json) and the end date of each operator's timetable (operators.json)"}


MEASURE_WORDS = {"pop": ("Residents", "Residentes"), "hu": ("Housing units", "Unidades de vivienda")}   # the name of the count in a dataset's label and group (site/js/core/adapters.js)
SHARE_LABELS = {"pop": ("% of the area's residents", "% de los residentes del área"), "hu": ("% of the area's housing units", "% de las unidades de vivienda del área")}   # the share an exposure layer is shaded by


def spanish_labels(doc):
    """{English text: Spanish text} for every dataset label, group and share the engine composes from an exposure file ("Residents: Inside a protected area"): the pages translate them with T()."""
    out = {}
    for meas, (en, es) in MEASURE_WORDS.items():
        for v in doc["vars"].values():
            out[f"{en}: {v['label']['en']}"] = f"{es}: {v['label']['es']}"
        for g in doc["groups"].values():
            out[f"{en} · {g['en']}"] = f"{es} · {g['es']}"
        out[SHARE_LABELS[meas][0]] = SHARE_LABELS[meas][1]
    return out


def write_labels(doc, path=None):
    """Write the Spanish of those names where the language tool reads it. Returns the path."""
    p = Path(path or ROOT / "i18n_src" / "es" / "labels_exposure.json")
    p.write_text(json.dumps(spanish_labels(doc), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def _ft(n, lang):
    return f"{n} ft" if lang == "en" else (f"{n} pie" if n == 1 else f"{n} pies")


def _families():
    f = [
        ("flood_sfha", "flood", "polygon", "Inside a Special Flood Hazard Area (1% annual chance)", "Dentro de un Área Especial de Riesgo de Inundación (1% de probabilidad anual)", ["fema_nfhl"]),
        ("flood_any", "flood", "polygon", "Inside a flood hazard area (1% or 0.2% annual chance)", "Dentro de una zona de riesgo de inundación (1% o 0.2% de probabilidad anual)", ["fema_nfhl"]),
    ]
    for n in FEET:
        f.append((f"slr_{n}ft", "slr", "polygon", f"Inundated by {_ft(n, 'en')} of sea level rise (connected to the ocean)", f"En zonas inundadas con {_ft(n, 'es')} de aumento del nivel del mar (conectadas al océano)", ["noaa_slr"]))
    for n in FEET:
        f.append((f"low_{n}ft", "low", "polygon", f"In a low-lying area that may flood at {_ft(n, 'en')} of sea level rise (not connected to the ocean)",
                  f"En un área baja que podría inundarse con {_ft(n, 'es')} de aumento del nivel del mar (sin conexión con el océano)", ["noaa_slr"]))
    for n in CATS:
        f.append((f"surge_cat{n}", "surge", "raster", f"Flooded by storm surge in a category {n} hurricane (near worst case, high tide)",
                  f"Inundado por marejada ciclónica en un huracán categoría {n} (casi el peor caso, marea alta)", ["nhc_slosh"]))
    for n in CATS:
        f.append((f"surge_deep_cat{n}", "surge", "raster", f"Under 3 ft or more of storm surge in a category {n} hurricane (near worst case, high tide)",
                  f"Bajo 3 pies o más de marejada ciclónica en un huracán categoría {n} (casi el peor caso, marea alta)", ["nhc_slosh"]))
    f += [
        ("protected", "protected", "polygon", "Inside a protected area", "Dentro de un área protegida", ["padus"]),
        ("protected_strict", "protected", "polygon", "Inside a strictly protected area (GAP status 1 or 2)", "Dentro de un área de protección estricta (estado GAP 1 o 2)", ["padus"]),
    ]
    stops = ["ati_gtfs", "muni_gtfs", "osm"]
    f += [
        ("stop_any", "transit", "stops", "Within 400 m of any mapped stop", "A 400 m o menos de cualquier parada cartografiada", stops),
        ("stop_sched", "transit", "stops", "Within 400 m of a stop with a timetable on file (expired timetables included)", "A 400 m o menos de una parada con horario registrado (incluye horarios vencidos)", ["ati_gtfs", "muni_gtfs"]),
        ("stop_cur", "transit", "stops", "Within 400 m of a stop with a current timetable", "A 400 m o menos de una parada con horario vigente", ["ati_gtfs", "muni_gtfs"]),
        ("stop_freq", "transit", "stops", "Within 400 m of a frequent stop (20 or more weekday departures)", "A 400 m o menos de una parada frecuente (20 o más salidas en día laborable)", ["ati_gtfs", "muni_gtfs"]),
        ("stop_sat", "transit", "stops", "Within 400 m of a stop with Saturday service", "A 400 m o menos de una parada con servicio los sábados", ["ati_gtfs", "muni_gtfs"]),
        ("stop_sun", "transit", "stops", "Within 400 m of a stop with Sunday service", "A 400 m o menos de una parada con servicio los domingos", ["ati_gtfs", "muni_gtfs"]),
        ("walk_cur", "transit", "stops", "Within a 400 m walk (along mapped roads) of a stop with a current timetable", "A 400 m o menos a pie (por calles mapeadas) de una parada con horario vigente", ["ati_gtfs", "muni_gtfs", "osm"]),
        ("walk_freq", "transit", "stops", "Within a 400 m walk (along mapped roads) of a frequent stop (20 or more weekday departures)", "A 400 m o menos a pie (por calles mapeadas) de una parada frecuente (20 o más salidas en día laborable)", ["ati_gtfs", "muni_gtfs", "osm"]),
    ]
    return [{"key": k, "group": g, "kind": kind, "label": {"en": en, "es": es}, "sources": src} for k, g, kind, en, es, src in f]


FAMILIES = _families()
KEYS = [f["key"] for f in FAMILIES]
STATIC_KEYS = [f["key"] for f in FAMILIES if f["kind"] in ("polygon", "raster")]
SURGE_KEYS = [f["key"] for f in FAMILIES if f["group"] == "surge"]
TRANSIT_KEYS = [f["key"] for f in FAMILIES if f["kind"] == "stops"]
# every block in a set is also in its superset (checked in the build and in the published files)
SUBSETS = [("flood_sfha", "flood_any"), ("protected_strict", "protected"), ("stop_cur", "stop_sched"), ("stop_sched", "stop_any"), ("stop_freq", "stop_cur"), ("stop_sat", "stop_cur"), ("stop_sun", "stop_cur"),
           ("walk_cur", "stop_cur"), ("walk_freq", "walk_cur"), ("walk_freq", "stop_freq")] \
    + [(f"slr_{n}ft", f"slr_{n + 1}ft") for n in FEET[:-1]] \
    + [(f"surge_deep_cat{n}", f"surge_cat{n}") for n in CATS]
# NOAA's maps for the five categories are not strictly nested: each is the highest surge of its own set of model storms. On 2026-11-17 five block points in
# San Juan (247 residents, 124 housing units) were flooded at category 4 and not at category 5. So no subset rule joins two categories (docs/exposure.md, section 9).


def log(*a):
    print(*a, flush=True)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ── Blocks ───────────────────────────────────────────────────────────────────

class Blocks:
    """The census blocks of Puerto Rico as arrays, in the order of the block table (network.load_block_table)."""

    def __init__(self, table):
        rows = table["rows"]
        self.table = table
        self.ids = [r[0] for r in rows]
        self.pop = np.array([r[1] for r in rows], dtype=np.int64)
        self.hu = np.array([r[2] for r in rows], dtype=np.int64)
        self.lon = np.array([r[4] for r in rows], dtype=float)
        self.lat = np.array([r[5] for r in rows], dtype=float)
        # the transit coverage has always used block points rounded to 4 decimals (about 11 m); the transit families use the same points, so the totals agree
        self.lon4 = np.array([round(float(v), 4) for v in self.lon])
        self.lat4 = np.array([round(float(v), 4) for v in self.lat])

    def __len__(self):
        return len(self.ids)


# ── Polygon layers ───────────────────────────────────────────────────────────

def points_in_polygons(polys, x, y, ptree=None):
    """Boolean array: which of the points (x, y) lie inside any of `polys` (a point on an edge counts as outside).

    Candidates come from a point index queried with each polygon's bounding box, and each polygon is tested once against all its candidates (vectorised, prepared
    geometry): about 0.4 s for NOAA's 5,000 polygons against 42,000 points, where testing point by point took minutes."""
    inside = np.zeros(len(x), dtype=bool)
    if len(polys) == 0 or len(x) == 0:
        return inside
    arr = np.empty(len(polys), dtype=object)
    for i, g in enumerate(polys):
        arr[i] = g
    ptree = ptree or STRtree(shapely.points(x, y))
    pi, qi = ptree.query(arr)
    if not len(pi):
        return inside
    order = np.argsort(pi, kind="stable")
    pi, qi = pi[order], qi[order]
    cuts = np.flatnonzero(np.diff(pi)) + 1
    for p, cand in zip(pi[np.concatenate(([0], cuts))], np.split(qi, cuts)):
        cand = cand[~inside[cand]]                 # a point already found in another polygon needs no second test
        if len(cand):
            inside[cand] = shapely.contains_xy(arr[p], x[cand], y[cand])
    return inside


def flood_polygons(fc):
    """(1% annual chance areas, those and the 0.2% annual chance areas) as shapely geometries. The same rules as build.py's point_flags: a polygon counts as the 1%
    area when SFHA_TF is 'T', as the 0.2% area when its subtype says so; unshaded zone X (minimal hazard), open water and unmapped areas are left out."""
    sfha, any_ = [], []
    for ft in fc["features"]:
        pr = ft.get("properties") or {}
        if pr.get("FLD_ZONE") in (None, "AREA NOT INCLUDED", "OPEN WATER") or not ft.get("geometry"):
            continue
        if pr.get("SFHA_TF") == "T":
            g = shape(ft["geometry"])
            sfha.append(g)
            any_.append(g)
        elif "0.2" in (pr.get("ZONE_SUBTY") or ""):
            any_.append(shape(ft["geometry"]))
    return sfha, any_


def protected_polygons(fc):
    """(protected areas, strictly protected areas). As for places: a proclamation boundary (Des_Tp PROC) outlines whole islands or refuges and is not managed land,
    so it does not count; strict is GAP status 1 or 2 (managed for biodiversity)."""
    real, strict = [], []
    for ft in fc["features"]:
        pr = ft.get("properties") or {}
        if pr.get("Des_Tp") == "PROC" or not ft.get("geometry"):
            continue
        g = shape(ft["geometry"])
        real.append(g)
        if str(pr.get("GAP_Sts")) in ("1", "2"):
            strict.append(g)
    return real, strict


def slr_gdb(cache=None, refresh=False):
    """NOAA's File Geodatabase of Puerto Rico sea level rise extents (1 to 10 ft, 23 MB), downloaded once into cache/slr."""
    import requests
    d = Path(cache or CACHE / "slr")
    gdb = d / "gdb" / SLR_GDB
    if gdb.exists() and not refresh:
        return gdb
    d.mkdir(parents=True, exist_ok=True)
    zp = d / "PR_slr_data_dist.zip"
    if not zp.exists() or refresh:
        log("  NOAA sea level rise extents for Puerto Rico (23 MB)")
        with requests.get(SLR_ZIP, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(zp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    zipfile.ZipFile(zp).extractall(d / "gdb")
    return gdb


def slr_layer(gdb, kind, ft):
    """The polygons of one NOAA layer: kind 'slr' (ocean-connected inundation) or 'low' (low-lying areas), ft whole feet above mean higher high water."""
    os.environ["OGR_ORGANIZE_POLYGONS"] = "ONLY_CCW"   # the Esri convention (outer rings clockwise, holes counter-clockwise); GDAL's default takes minutes on these layers
    try:
        import pyogrio
    except ImportError as e:   # only the full build needs it
        raise SystemExit("exposure.py reads NOAA's File Geodatabase of sea level rise with pyogrio: pip install pyogrio (it is in requirements.txt)") from e
    _, _, geom, _ = pyogrio.raw.read(str(gdb), layer=f"PR_{kind}_{ft}ft", columns=[], read_geometry=True)
    return shapely.from_wkb(geom)


def surge_dir(cache=None, refresh=False):
    """NOAA NHC's Puerto Rico storm surge maps (five GeoTIFFs, 7.3 MB zipped, dated November 2018), downloaded once into cache/surge."""
    import requests
    d = Path(cache or CACHE / "surge")
    if (d / "x" / SURGE_TIF.format(c=5)).exists() and not refresh:
        return d / "x"
    d.mkdir(parents=True, exist_ok=True)
    zp = d / "PR_SLOSH_MOM_Inundation.zip"
    if not zp.exists() or refresh:
        log("  NOAA NHC storm surge maps for Puerto Rico (7.3 MB)")
        with requests.get(SURGE_ZIP, headers=UA, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(zp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    with zipfile.ZipFile(zp) as z:
        z.extractall(d / "x", [n for n in z.namelist() if n.endswith(".tif")])
    return d / "x"


def surge_bins(cat, x, y, cache=None, refresh=False):
    """The storm surge band code (0 = dry or outside the map, 1 = under 1 ft, 2 = 1 to 2 ft, ...) of a category `cat` hurricane at lon/lat points.
    Read with the project's own GeoTIFF reader (raster.py): the files are tiled, LZW, 8-bit, 255 = no data, about 10 m cells in NAD83 (EPSG 4269)."""
    import raster
    cog = raster.COG(str(surge_dir(cache, refresh) / SURGE_TIF.format(c=cat)))
    v = np.asarray(cog.sample(list(map(float, x)), list(map(float, y))), dtype=float)
    v = np.where(np.isnan(v) | (v == cog.nodata), 0, v)
    return v.astype(np.int64)


def surge_flags(blocks, cache=None, refresh=False, bins=None):
    """{family: boolean array over the blocks} for the storm surge families. `bins` (a function cat -> band code per block) can be given to test."""
    bins = bins or (lambda c: surge_bins(c, blocks.lon, blocks.lat, cache, refresh))   # noqa: E731
    out = {}
    for n in CATS:
        b = np.asarray(bins(n))
        out[f"surge_cat{n}"] = b >= 1
        out[f"surge_deep_cat{n}"] = b >= SURGE_DEEP_BIN
    return out


def hazard_flags(blocks, data_dir=DATA, slr_cache=None, refresh=False, flood=None, protected=None, slr=None, surge=None):
    """{family: boolean array over the blocks} for the polygon and raster families. `flood`, `protected`, `slr` (a function (kind, ft) -> polygons) and `surge`
    (a function cat -> band code per block) can be given to test."""
    x, y = blocks.lon, blocks.lat
    ptree = STRtree(shapely.points(x, y))
    out = {}
    sfha, any_ = flood_polygons(flood or load_json(Path(data_dir) / "flood.geojson"))
    out["flood_sfha"] = points_in_polygons(sfha, x, y, ptree)
    out["flood_any"] = points_in_polygons(any_, x, y, ptree)
    real, strict = protected_polygons(protected or load_json(Path(data_dir) / "protected.geojson"))
    out["protected"] = points_in_polygons(real, x, y, ptree)
    out["protected_strict"] = points_in_polygons(strict, x, y, ptree)
    if slr is None:
        gdb = slr_gdb(slr_cache, refresh)
        slr = lambda kind, ft: slr_layer(gdb, kind, ft)   # noqa: E731
    for n in FEET:
        out[f"slr_{n}ft"] = points_in_polygons(slr("slr", n), x, y, ptree)
        out[f"low_{n}ft"] = points_in_polygons(slr("low", n), x, y, ptree)
    out.update(surge_flags(blocks, Path(slr_cache).parent / "surge" if slr_cache else None, refresh, bins=surge))
    return {k: out[k] for k in STATIC_KEYS}


# ── Transit ──────────────────────────────────────────────────────────────────

def transit_flags(blocks, stops, operators, as_of, net=None):
    """{family: boolean array over the blocks} for the transit families, with the rules access.py gives places (400 m, straight line, the same distance formula),
    and the walking families with access.py's walking rule when `net` (walknet.load()) is given."""
    pts = [{"lat": float(a), "lng": float(b)} for a, b in zip(blocks.lat4, blocks.lon4)]
    res = access.compute(pts, stops, operators, as_of, net=net)
    scheduled = [s for s in stops if s.get("source") in access.SCHEDULED_SOURCES]
    sched = access.compute(pts, scheduled, operators, as_of).any_m <= access.NEAR_M if scheduled else np.zeros(len(pts), dtype=bool)
    cur = res.ts_m <= access.NEAR_M
    freq = cur & (res.ts_calls >= access.FREQUENT_CALLS)
    if res.tw_m is not None:
        walk = res.tw_m <= access.NEAR_M
        wfreq = walk & (res.tw_calls >= access.FREQUENT_CALLS)
    else:
        log("  no walking network (site/data/roads.bin): walk_cur and walk_freq copy the straight-line stop_cur and stop_freq")
        walk, wfreq = cur.copy(), freq.copy()
    return {"stop_any": res.any_m <= access.NEAR_M, "stop_sched": sched, "stop_cur": cur, "stop_freq": freq,
            "stop_sat": (res.ts_we & access.SATURDAY) > 0, "stop_sun": (res.ts_we & access.SUNDAY) > 0, "walk_cur": walk, "walk_freq": wfreq}


# ── Units and roll-up ────────────────────────────────────────────────────────

def crosswalk_ids(data_dir=DATA):
    cw = load_json(Path(data_dir) / "geo" / "crosswalk.json")
    return {lv: [r[0] for r in cw["units"][lv]] for lv in LEVELS}, cw


def unit_index(blocks, level, ids, barrio_of=None):
    """For each block, the position in `ids` of the unit of `level` that holds it (-1 for a block in no unit: the offshore county subdivisions that are not barrios)."""
    where = {u: i for i, u in enumerate(ids)}
    if level == "municipio":
        keys = (b[:5] for b in blocks.ids)
    elif level == "tract":
        keys = (b[:11] for b in blocks.ids)
    elif level == "barrio":
        keys = iter(barrio_of)
    else:
        raise ValueError(level)
    return np.array([where.get(k, -1) for k in keys], dtype=np.int64)


def roll_up(blocks, index, n, flags):
    """({family: (residents per unit, housing units per unit)}, (total residents per unit, total housing units per unit)); a block counts in the unit `index` names."""
    ok = index >= 0
    count = lambda w, m: np.bincount(index[m], weights=w[m], minlength=n).astype(np.int64)   # noqa: E731
    total = (count(blocks.pop, ok), count(blocks.hu, ok))
    return {k: (count(blocks.pop, ok & f), count(blocks.hu, ok & f)) for k, f in flags.items()}, total


def check_subsets(flags, tolerate=()):
    """Every block in a set must be in its superset (a 2 ft flood is also a 3 ft flood; a current stop is also a stop). Returns the violations."""
    bad = []
    for small, big in SUBSETS:
        if small in flags and big in flags and (small, big) not in tolerate:
            n = int((flags[small] & ~flags[big]).sum())
            if n:
                bad.append((small, big, n))
    return bad


def document(level, ids, rolled, total, as_of, built):
    fam = {f["key"]: f for f in FAMILIES}
    vars_ = {}
    for k in KEYS:
        if k in rolled:
            pop, hu = rolled[k]
            vars_[k] = {"label": fam[k]["label"], "group": fam[k]["group"], "kind": fam[k]["kind"], "pop": pop.tolist(), "hu": hu.tolist()}
    return {"version": VERSION, "built": built, "as_of": as_of, "level": level, "basis": BASIS, "inputs": INPUTS, "measures": MEASURES, "groups": GROUPS,
            "geo": {"level": level, "ids": ids}, "total": {"pop": total[0].tolist(), "hu": total[1].tolist()}, "vars": vars_}


def dump(path, doc):
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# ── Build ────────────────────────────────────────────────────────────────────

def build(data_dir=DATA, as_of=None, refresh=False, cache=None, out=None, slr=None, table=None, barrio_of=None, surge=None):
    """Compute every family for every block and write the three files. Returns {level: file name}.

    `slr` (a function (kind, ft) -> polygons), `table` (the block table) and `barrio_of` (the barrio of each block) can be given instead of read, to test on a small island."""
    as_of = as_of or date.today()
    data_dir = Path(data_dir)
    out = Path(out or data_dir)
    log("Exposure series")
    table = table or network.load_block_table(Path(cache or CACHE) / "network", refresh)
    blocks = Blocks(table)
    barrio_of = barrio_of or geo.block_barrios(table, refresh, Path(cache or CACHE) / "geo")
    ids, cw = crosswalk_ids(data_dir)
    log("  polygon and raster layers (flood, sea level rise, storm surge, protected areas)")
    flags = hazard_flags(blocks, data_dir, Path(cache or CACHE) / "slr", refresh, slr=slr, surge=surge)
    log("  transit stops")
    import walknet
    flags.update(transit_flags(blocks, load_json(data_dir / "transport.json"), load_json(data_dir / "operators.json")["operators"], as_of, net=walknet.load(data_dir / "roads.bin")))
    bad = check_subsets(flags)
    if bad:
        raise SystemExit("exposure: a set is not inside its superset for some blocks (" + ", ".join(f"{a} not in {b}: {n}" for a, b, n in bad) + "); the layers or the rules disagree")
    built = date.today().isoformat()
    docs = {}
    for level in LEVELS:   # all three levels are worked out and checked before any file is written
        idx = unit_index(blocks, level, ids[level], barrio_of)
        rolled, total = roll_up(blocks, idx, len(ids[level]), flags)
        rows = {r[0]: r for r in cw["units"][level]}
        want = (np.array([rows[u][6] for u in ids[level]]), np.array([rows[u][7] for u in ids[level]]))
        if (total[0] != want[0]).any() or (total[1] != want[1]).any():
            raise SystemExit(f"exposure: the blocks do not add up to the crosswalk's residents and housing units for the {level} level; run python geo.py")
        docs[level] = document(level, ids[level], rolled, total, as_of.isoformat(), built)
    written = {}
    if out == DATA:   # a build into another folder (the tests) leaves the language sources alone
        write_labels(docs["municipio"])
    for level in LEVELS:
        dump(out / FILE[level], docs[level])
        written[level] = FILE[level]
        log(f"  {FILE[level]}: {len(ids[level]):,} areas x {len(KEYS)} families, {(out / FILE[level]).stat().st_size / 1024:.0f} KB")
    pop = int(blocks.pop.sum())
    for k in ("flood_sfha", "flood_any", "slr_3ft", "slr_10ft", "surge_cat1", "surge_cat5", "protected", "stop_any", "stop_cur"):
        log(f"    residents {k:12s} {int(blocks.pop[flags[k]].sum()):>9,} ({blocks.pop[flags[k]].sum() / pop * 100:5.1f}%)   housing units {int(blocks.hu[flags[k]].sum()):>9,} ({blocks.hu[flags[k]].sum() / blocks.hu.sum() * 100:5.1f}%)")
    return written


def _same(a, b):
    """Equal apart from the dates, so a night that changes nothing writes nothing."""
    skip = ("as_of", "built")
    return {k: v for k, v in a.items() if k not in skip} == {k: v for k, v in b.items() if k not in skip}


def _ordered(vars_):
    """The families in the order of KEYS (the order check() expects), whatever order they were added in."""
    return {k: vars_[k] for k in KEYS if k in vars_} | {k: v for k, v in vars_.items() if k not in KEYS}


def apply_surge(data_dir=DATA, write=True, cache=None, log=log, table=None, barrio_of=None, refresh=False, bins=None):
    """Add or recompute only the storm surge families of the published files, and leave every other family as it is (the surge maps were added on 2026-11-17,
    after the last full build). Returns the names of the files written."""
    data_dir = Path(data_dir)
    old = {}
    for lv in LEVELS:
        p = data_dir / FILE[lv]
        if not p.exists():
            raise SystemExit(f"exposure: {FILE[lv]} has not been built (python exposure.py)")
        old[lv] = load_json(p)
    cache = Path(cache or CACHE)
    table = table or network.load_block_table(cache / "network", False)
    blocks = Blocks(table)
    barrio_of = barrio_of or geo.block_barrios(table, False, cache / "geo")
    ids, _ = crosswalk_ids(data_dir)
    flags = surge_flags(blocks, cache / "surge", refresh, bins=bins)
    bad = check_subsets(flags)
    if bad:
        raise SystemExit("exposure: storm surge sets disagree: " + ", ".join(f"{a} not in {b}: {n}" for a, b, n in bad))
    fam = {f["key"]: f for f in FAMILIES}
    new = {}
    for lv in LEVELS:
        idx = unit_index(blocks, lv, ids[lv], barrio_of)
        rolled, total = roll_up(blocks, idx, len(ids[lv]), flags)
        if (np.array(old[lv]["total"]["pop"]) != total[0]).any() or (np.array(old[lv]["total"]["hu"]) != total[1]).any() or old[lv]["geo"]["ids"] != ids[lv]:
            raise SystemExit(f"exposure: the blocks no longer match {FILE[lv]} (a new census table or crosswalk); run python exposure.py")
        d = json.loads(json.dumps(old[lv]))
        for k in SURGE_KEYS:
            d["vars"][k] = {"label": fam[k]["label"], "group": fam[k]["group"], "kind": fam[k]["kind"], "pop": rolled[k][0].tolist(), "hu": rolled[k][1].tolist()}
        d["vars"] = _ordered(d["vars"])
        d["groups"], d["inputs"] = GROUPS, INPUTS
        new[lv] = d
    written = []
    for lv, d in new.items():
        if not _same(old[lv], d):
            if write:
                dump(data_dir / FILE[lv], d)
            written.append(FILE[lv])
    if write and written and data_dir == DATA:
        write_labels(new["municipio"])
    pop, hu = int(blocks.pop.sum()), int(blocks.hu.sum())
    for k in SURGE_KEYS:
        log(f"    residents {k:16s} {int(blocks.pop[flags[k]].sum()):>9,} ({blocks.pop[flags[k]].sum() / pop * 100:5.1f}%)   housing units {int(blocks.hu[flags[k]].sum()):>9,} ({blocks.hu[flags[k]].sum() / hu * 100:5.1f}%)")
    log("exposure: " + ((("wrote " if write else "would write ") + ", ".join(written)) if written else "storm surge families unchanged"))
    return written


def apply_transit(data_dir=DATA, as_of=None, write=True, cache=None, log=log, table=None, barrio_of=None):
    """Recompute only the transit families of the published files from the published stops and timetables, and write what changed (the nightly refresh calls this).

    The polygon families do not change between full builds and are kept as they are. Returns the names of the files written."""
    as_of = as_of or date.today()
    data_dir = Path(data_dir)
    old = {}
    for lv in LEVELS:
        p = data_dir / FILE[lv]
        if not p.exists():
            log(f"exposure: {FILE[lv]} has not been built (python exposure.py); transit families not refreshed")
            return []
        old[lv] = load_json(p)
    cache = Path(cache or CACHE)
    table = table or network.load_block_table(cache / "network", False)
    blocks = Blocks(table)
    barrio_of = barrio_of or geo.block_barrios(table, False, cache / "geo")
    ids, _ = crosswalk_ids(data_dir)
    import walknet
    flags = transit_flags(blocks, load_json(data_dir / "transport.json"), load_json(data_dir / "operators.json")["operators"], as_of, net=walknet.load(data_dir / "roads.bin"))
    bad = check_subsets(flags)
    if bad:
        raise SystemExit("exposure: transit sets disagree: " + ", ".join(f"{a} not in {b}: {n}" for a, b, n in bad))
    changed = {}
    for lv in LEVELS:   # all three levels are checked before any file is written
        idx = unit_index(blocks, lv, ids[lv], barrio_of)
        rolled, total = roll_up(blocks, idx, len(ids[lv]), flags)
        if (np.array(old[lv]["total"]["pop"]) != total[0]).any() or (np.array(old[lv]["total"]["hu"]) != total[1]).any() or old[lv]["geo"]["ids"] != ids[lv]:
            log(f"exposure: the blocks no longer match {FILE[lv]} (a new census table or crosswalk); run python exposure.py. Transit families not refreshed")
            return []
        new = json.loads(json.dumps(old[lv]))
        fam = {f["key"]: f for f in FAMILIES}
        for k in TRANSIT_KEYS:   # a family added since the full build (the walking ones, 2026-10-16) is created with its label, as build() writes it
            v = new["vars"].setdefault(k, {"label": fam[k]["label"], "group": fam[k]["group"], "kind": fam[k]["kind"]})
            v["pop"], v["hu"] = rolled[k][0].tolist(), rolled[k][1].tolist()
        new["vars"] = _ordered(new["vars"])
        new["as_of"] = as_of.isoformat()
        if not _same(old[lv], new):
            changed[lv] = new
    written = []
    for lv, new in changed.items():
        if write:
            dump(data_dir / FILE[lv], new)
        written.append(FILE[lv])
    pop = int(blocks.pop.sum())
    log(f"exposure: residents within 400 m of a stop with a current timetable {int(blocks.pop[flags['stop_cur']].sum()):,} ({blocks.pop[flags['stop_cur']].sum() / pop * 100:.1f}%; "
        f"walking {int(blocks.pop[flags['walk_cur']].sum()):,}, {blocks.pop[flags['walk_cur']].sum() / pop * 100:.1f}%), "
        f"any mapped stop {int(blocks.pop[flags['stop_any']].sum()):,}; " + ((("wrote " if write else "would write ") + ", ".join(written)) if written else "nothing to write"))
    return written


# ── Checks on the published files ────────────────────────────────────────────

def check(data_dir=DATA):
    """Problems found in the published exposure files (an empty list when they are sound)."""
    data_dir = Path(data_dir)
    P = []
    try:
        ids, cw = crosswalk_ids(data_dir)
    except FileNotFoundError:
        return ["site/data/geo/crosswalk.json is missing: run python geo.py"]
    docs = {}
    for lv in LEVELS:
        p = data_dir / FILE[lv]
        if not p.exists():
            P.append(f"{FILE[lv]} is missing: run python exposure.py")
            continue
        d = docs[lv] = load_json(p)
        if d.get("geo", {}).get("ids") != ids[lv]:
            P.append(f"{FILE[lv]}: the ids are not the crosswalk's {lv} ids, in the crosswalk's order")
        n = len(ids[lv])
        rows = {r[0]: r for r in cw["units"][lv]}
        for m, i in (("pop", 6), ("hu", 7)):
            if d.get("total", {}).get(m) != [rows[u][i] for u in ids[lv]]:
                P.append(f"{FILE[lv]}: total {m} is not the crosswalk's")
        vars_ = d.get("vars", {})
        if list(vars_) != KEYS:
            P.append(f"{FILE[lv]}: the families are not the expected {len(KEYS)} in order")
        for k, v in vars_.items():
            for m in ("pop", "hu"):
                a, tot = v.get(m), d.get("total", {}).get(m)
                if not isinstance(a, list) or not isinstance(tot, list):
                    P.append(f"{FILE[lv]} {k}.{m}: missing")
                elif len(a) != n:
                    P.append(f"{FILE[lv]} {k}.{m}: {len(a)} values for {n} areas")
                elif any((not isinstance(x, int)) or x < 0 or x > t for x, t in zip(a, tot)):
                    P.append(f"{FILE[lv]} {k}.{m}: a value is not a whole number between 0 and the area's total")
        for small, big in SUBSETS:
            if small in vars_ and big in vars_:
                for m in ("pop", "hu"):
                    if any(a > b for a, b in zip(vars_[small].get(m, []), vars_[big].get(m, []))):
                        P.append(f"{FILE[lv]}: {small}.{m} is larger than {big}.{m} in some area")
    # the three levels hold the same blocks: they must agree on every municipio and on the island
    if len(docs) == len(LEVELS):
        parent = {lv: [r[1] for r in cw["units"][lv]] for lv in ("barrio", "tract")}
        mun = {u: i for i, u in enumerate(ids["municipio"])}
        for k in KEYS:
            if any(not isinstance(d.get("vars", {}).get(k, {}).get(m), list) for d in docs.values() for m in ("pop", "hu")):
                continue   # a family a file lacks is reported above
            for m in ("pop", "hu"):
                base = docs["municipio"]["vars"][k][m]
                for lv in ("barrio", "tract"):
                    sums = [0] * len(base)
                    for par, x in zip(parent[lv], docs[lv]["vars"][k][m]):
                        sums[mun[par]] += x
                    if sums != base:
                        P.append(f"{k}.{m}: the {lv} rows do not add up to the municipio rows")
    return P


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transit", action="store_true", help="recompute only the transit families of the published files")
    ap.add_argument("--surge", action="store_true", help="add or recompute only the storm surge families of the published files")
    ap.add_argument("--check", action="store_true", help="check the published files and write nothing")
    ap.add_argument("--refresh", action="store_true", help="download the source layers again")
    ap.add_argument("--labels", action="store_true", help="write i18n_src/es/labels_exposure.json from the published municipio file and stop")
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: today)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    if args.labels:
        print("wrote", write_labels(load_json(DATA / FILE["municipio"])))
        return 0
    if args.check:
        problems = check()
        for p in problems:
            print("  ERROR", p)
        print(f"exposure: {len(problems)} problems")
        return 1 if problems else 0
    if args.transit:
        apply_transit(as_of=as_of)
        return 0
    if args.surge:
        apply_surge(refresh=args.refresh)
        problems = check()
        for p in problems:
            print("  ERROR", p)
        return 1 if problems else 0
    build(as_of=as_of, refresh=args.refresh)
    problems = check()
    for p in problems:
        print("  ERROR", p)
    if problems:
        raise SystemExit(f"exposure: the files just written fail their own checks ({len(problems)} problems)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
