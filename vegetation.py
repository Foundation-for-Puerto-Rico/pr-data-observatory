"""Vegetation greenness for the PR Data Observatory, for the 901 barrios and the 78 municipios: how green the land is on clear summer days, from Sentinel-2,
how much of it is densely vegetated and how much has little or no vegetation, and how many residents live on that bare or built land. Shown next to the surface
heat of heat.py, from the same months and on the same grid. Step 1 of the terrain and climate plan (docs/terrain-climate-proposal-2026-11.md, HANDOFF decision 80;
method in docs/vegetation.md).

    python vegetation.py             # build site/data/vegetation_series.json and site/data/vegetation_barrio.json (reads only the scenes missing from cache/vegetation/)
    python vegetation.py --refresh   # search the scene catalog again (new scenes are read; cached scenes are kept)
    python vegetation.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

The source. Copernicus Sentinel-2 Level-2A surface reflectance, Collection 1 (reprocessed by ESA with one processing baseline, so older and newer scenes compare),
read from the Earth Search catalog on AWS (Element 84), whose files are public and need no key: the red band (B04), the near-infrared band (B08), both 10 m, and the
scene classification (SCL, 20 m). License: the Copernicus Sentinel data terms (free, full and open use; credit "Contains modified Copernicus Sentinel data").
NDVI, the normalized difference vegetation index, is (near-infrared - red) / (near-infrared + red): green leaves reflect near-infrared and absorb red, so it is near 0
on bare ground, pavement and roofs, and 0.6 to 0.9 under dense forest. It measures how green the land looks from above, not tree cover or species.

How it is made (docs/vegetation.md):
  - Scenes: every Sentinel-2 L2A scene over Puerto Rico from June to September of the last three complete summers (the window of heat.py), with less than 70% cloud
    cover (eight 110 km MGRS tiles, UTM zones 19 and 20; about 330 scenes a summer).
  - Grid: heat.py's 60 m grid in UTM zone 20 over the barrios. Each scene is read at 40 m (the second overview of the 10 m bands, which the files average from the
    10 m pixels; the first overview of SCL, which keeps the most common class: the files' OVR_RESAMPLING_ALG is AVERAGE and MODE), by HTTP range requests with raster.py, and each cell takes the pixel
    under its center (zone 19 scenes are mapped through pyproj).
  - Clear pixels: an observation counts when SCL says vegetation (4) or not vegetated (5), and both reflectances are above zero. Clouds, cirrus, cloud shadow, dark
    or terrain shadow, water, unclassified and saturated pixels are left out.
  - One view per pass: where two MGRS tiles of the same pass overlap, the cell keeps one value (the first tile in name order), so a pass is not counted twice.
  - Composite: each cell's value is the median of its clear views, exact (computed in eight blocks of cells to bound memory). Cells with fewer than 3 views have
    no value.
  - The cache keeps, for each scene, the cells it saw clear and their NDVI (cache/vegetation/values/, about 1 MB a scene), not the image tiles: a rebuild reads
    the cache, and the nightly rebuild's cache stays small.
  - Areas: a cell belongs to the barrio whose outline holds its center (heat.grid). Municipios and Puerto Rico pool the cells of their barrios.
  - Classes (USGS's reading of NDVI): dense vegetation at 0.6 and above (forest, crops at their peak); little or no vegetation below 0.2 (rock, sand, pavement,
    roofs). The pixel size matters: a 40 m pixel mixes a roof, a yard and a tree, so a city street lined with trees reads in between.
  - Residents: each 2020 census block with residents counts whole on the cell under its internal point, in the barrio the crosswalk gives it (heat.block_cells).
  - Checks that stop the build: Puerto Rico's median NDVI between 0.4 and 0.9; San Juan's median below Puerto Rico's; Jayuya's and Adjuntas's above it; at least
    95% of the cells with a value; and, across the barrios, greener means cooler in heat_barrio.json (a Spearman rank correlation of -0.3 or less) when that file
    is there.
No personal data: the files hold indexes, shares and counts of residents.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import heat
import housing_series as hs
import raster

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "vegetation"
OUT = hs.OUT
OUT_SERIES = OUT / "vegetation_series.json"
OUT_BARRIO = OUT / "vegetation_barrio.json"
UA = heat.UA
log = hs.log

STAC = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"
SEARCH_BOX = heat.SEARCH_BOX
MONTHS = heat.MONTHS
MAX_CLOUD = 70
EPSG = heat.EPSG
LEVEL_BAND, LEVEL_SCL = 2, 1                     # 40 m: the second overview of the 10 m bands, the first of the 20 m SCL
CLEAR_SCL = (4, 5)                               # vegetation, not vegetated
RULE = "v1-scl45-l40m"                           # the per-scene cache's rule: change it when the reading of a scene changes
MIN_OBS = 3
BLOCKS = 8
MIN_CELLS = heat.MIN_CELLS
DENSE, SPARSE = 0.6, 0.2                         # USGS: 0.6-0.9 dense vegetation; 0.1 or less barren, 0.2-0.5 sparse
CHECK_MEDIAN = (0.4, 0.9)
CHECK_COVER = 0.95
CHECK_HEAT_RHO = -0.3
SAN_JUAN, GREEN = heat.SAN_JUAN, heat.COOL       # San Juan; Jayuya and Adjuntas
FLOOR_SCENES = 600                               # 2026-11-04: 984 scenes in three summers
NO_VIEWS = "Too few cloud-free Sentinel-2 views"

SOURCES = {
    "copernicus_sentinel2_l2a": {
        "name": "Copernicus Sentinel-2 Level-2A surface reflectance, Collection 1 — red (B04), near-infrared (B08) and scene classification (SCL)",
        "url": "https://element84.com/earth-search/",
        "license": "Copernicus Sentinel data terms: free, full and open use; credit \"Contains modified Copernicus Sentinel data\"",
        "note": "Read from the Earth Search catalog on AWS (collection sentinel-2-c1-l2a, public files, no key) at 40 m, by HTTP range requests (raster.py). Contains modified Copernicus Sentinel data."},
    "census_tiger": heat.SOURCES["census_tiger"],
}


# ── Scene catalog ──────────────────────────────────────────────────────────

def search(body, tries=6):
    """All the features of a STAC search, following its next links (Earth Search pages by POST with a body, or by GET)."""
    url, method, out = f"{STAC}/search", "POST", []
    while True:
        for attempt in range(tries):
            try:
                r = (requests.post(url, json=body, headers=UA, timeout=(30, 120)) if method == "POST"
                     else requests.get(url, headers=UA, timeout=(30, 120)))
                if r.status_code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                    time.sleep(min(60, 4 * 2 ** attempt))
                    continue
                r.raise_for_status()
                page = r.json()
                if "features" not in page:
                    raise requests.RequestException(f"no features in the reply: {str(page)[:200]}")
                break
            except requests.RequestException as e:
                if attempt == tries - 1:
                    raise SystemExit(f"vegetation: {url} failed: {e}")
                time.sleep(min(60, 4 * 2 ** attempt))
        out += page["features"]
        nxt = [l for l in page.get("links", []) if l.get("rel") == "next"]
        if not nxt:
            return out
        url, method, body = nxt[0]["href"], nxt[0].get("method", "GET"), nxt[0].get("body", body)


def scale_offset(asset):
    b = (asset.get("raster:bands") or [{}])[0]
    return float(b.get("scale", 0.0001)), float(b.get("offset", -0.1))


def scenes(years, refresh=False, offline=False):
    """[{id, date, epsg, cloud, red, nir, scl, scale, offset}] for the summers, from the cache or the STAC search."""
    p = CACHE / f"scenes_{years[0]}_{years[-1]}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"vegetation --check: {p.relative_to(ROOT)} is missing (python vegetation.py makes it)")
    out = []
    for y in years:
        body = {"collections": [COLLECTION], "bbox": SEARCH_BOX, "limit": 100,
                "datetime": f"{y}-{MONTHS[0]:02d}-01T00:00:00Z/{y}-{MONTHS[1]:02d}-30T23:59:59Z",
                "query": {"eo:cloud_cover": {"lt": MAX_CLOUD}}}
        for f in search(body):
            pr, a = f["properties"], f["assets"]
            s_r, o_r = scale_offset(a["red"])
            s_n, o_n = scale_offset(a["nir"])
            if (s_r, o_r) != (s_n, o_n):
                raise SystemExit(f"vegetation: {f['id']}: red and near-infrared have different scales")
            out.append({"id": f["id"], "date": pr["datetime"][:10], "epsg": int(pr.get("proj:epsg") or str(pr.get("proj:code", "0")).split(":")[-1]),
                        "cloud": pr["eo:cloud_cover"], "red": a["red"]["href"], "nir": a["nir"]["href"], "scl": a["scl"]["href"], "scale": s_r, "offset": o_r})
    seen = {}
    for s in out:
        seen.setdefault(s["id"], s)                   # a scene listed twice (paging) counts once
    out = sorted(seen.values(), key=lambda s: (s["date"], s["id"]))
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


# ── One scene ────────────────────────────────────────────────────────────────

def pixels(cog, xy, level):
    import numpy as np
    X, Y = xy[cog.epsg]
    a, _, c, _, e, f = cog.level_transform(level)
    return np.floor((X - c) / a).astype(np.int64), np.floor((Y - f) / e).astype(np.int64)


def read_scene(sc, xy, session=None):
    """(cell indexes, NDVI) of the clear land observations of one scene, read from its files. Only the tiles under the grid's cells are read."""
    import numpy as np
    scl = raster.COG(sc["scl"], session=session, workers=12)
    red = raster.COG(sc["red"], session=session, workers=12)
    nir = raster.COG(sc["nir"], session=session, workers=12)
    if len(scl.levels) <= LEVEL_SCL or len(red.levels) <= LEVEL_BAND or scl.level_transform(LEVEL_SCL) != red.level_transform(LEVEL_BAND) \
            or red.level_transform(LEVEL_BAND) != nir.level_transform(LEVEL_BAND):
        raise SystemExit(f"vegetation: {sc['id']}: SCL overview {LEVEL_SCL} and the bands' overview {LEVEL_BAND} are not one grid")
    col, row = pixels(scl, xy, LEVEL_SCL)
    s, inside = scl.values_at(col, row, LEVEL_SCL)
    idx = np.flatnonzero(inside & np.isin(s, CLEAR_SCL))
    if not idx.size:
        return idx.astype(np.int32), np.zeros(0, np.int16)
    r, _ = red.values_at(col[idx], row[idx], LEVEL_BAND)
    n, _ = nir.values_at(col[idx], row[idx], LEVEL_BAND)
    r = r.astype(np.float64) * sc["scale"] + sc["offset"]
    n = n.astype(np.float64) * sc["scale"] + sc["offset"]
    ok = (r > 0) & (n > 0)
    v = (n[ok] - r[ok]) / (n[ok] + r[ok])
    return idx[ok].astype(np.int32), np.round(v * 10000).astype(np.int16)


def scene_values(sc, xy, session=None, offline=False):
    """(cell indexes, NDVI x 10000) of one scene, from cache/vegetation/values/ or read and cached."""
    import numpy as np
    p = CACHE / "values" / RULE / f"{sc['id']}.npz"
    if p.exists():
        z = np.load(p)
        return np.cumsum(z["d"]).astype(np.int32), z["v"]
    if offline:
        raise SystemExit(f"vegetation --check: the cached values of {sc['id']} are missing (python vegetation.py reads them)")
    idx, v = read_scene(sc, xy, session)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".part.npz")
    np.savez_compressed(tmp, d=np.diff(idx, prepend=0).astype(np.int32), v=v)   # indexes as differences: they compress to almost nothing
    tmp.replace(p)
    return idx, v


def by_pass(scs):
    """The scenes grouped by pass (platform and date): the tiles of one pass overlap where MGRS tiles meet."""
    groups = {}
    for s in scs:
        groups.setdefault((s["id"].split("_")[0], s["date"]), []).append(s)
    return [sorted(g, key=lambda s: s["id"]) for _, g in sorted(groups.items())]


def one_view_per_pass(parts):
    """The (indexes, values) of the tiles of one pass, with each cell once (the first tile in the list keeps it)."""
    import numpy as np
    idx = np.concatenate([p[0] for p in parts])
    v = np.concatenate([p[1] for p in parts])
    _, first = np.unique(idx, return_index=True)
    return idx[first], v[first]


def composite(scs, xy, n_cells, offline=False, parallel=4):
    """Per cell: the median NDVI of its clear views (nan below MIN_OBS), the number of views, the passes that gave a clear cell, the number of observations."""
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=64))
    clear = {}
    with ThreadPoolExecutor(parallel) as ex:          # read (or load) every scene once, a few at a time; only the number of clear cells is kept in memory
        for k, (sc, n) in enumerate(zip(scs, ex.map(lambda sc: len(scene_values(sc, xy, session, offline)[0]), scs))):
            clear[sc["id"]] = n
            if (k + 1) % 50 == 0:
                log(f"    {k + 1} of {len(scs)} scenes read")
    passes = by_pass(scs)
    used = sum(any(clear[sc["id"]] for sc in g) for g in passes)
    med = np.full(n_cells, np.nan)
    nobs = np.zeros(n_cells, np.int64)
    total = 0
    edges = np.linspace(0, n_cells, BLOCKS + 1).astype(np.int64)
    for b in range(BLOCKS):                            # the exact median, a block of cells at a time
        lo, hi = edges[b], edges[b + 1]
        ii, vv = [], []
        for g in passes:
            parts = []
            for sc in g:
                i, v = scene_values(sc, xy, None, True)
                k = (i >= lo) & (i < hi)
                parts.append((i[k], v[k]))
            i, v = one_view_per_pass(parts)
            ii.append(i - lo); vv.append(v)
        i = np.concatenate(ii); v = np.concatenate(vv).astype(np.float64) / 10000
        total += i.size
        m, n = heat.median_by_cell(i, v, hi - lo)
        med[lo:hi], nobs[lo:hi] = m, n
    ndvi = np.where(nobs >= MIN_OBS, med, np.nan)
    return ndvi, nobs, used, len(passes), total


# ── Build ────────────────────────────────────────────────────────────────────

def ranks(x):
    """Average ranks (ties share their mean rank)."""
    import numpy as np
    x = np.asarray(x, float)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x)); r[order] = np.arange(1, len(x) + 1)
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=r)
    return (sums / cnt)[inv]


def spearman(a, b):
    import numpy as np
    ra, rb = ranks(a), ranks(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def heat_link(B, brow):
    """The rank correlation, across the barrios that have both, of their median NDVI and their median surface temperature in heat_barrio.json (None without it)."""
    p = OUT / heat.OUT_BARRIO.name
    if not p.exists():
        return None
    hb = json.loads(p.read_text(encoding="utf-8"))
    if hb["geo"]["ids"] != B.ids:
        return None
    v = next(x for x in hb["vars"] if x["key"] == "heat_lst_med")
    t = next(iter(v["years"].values()))
    pairs = [(r["med"], t[i]) for i, r in enumerate(brow) if r is not None and t[i] is not None]
    hs_ = OUT / heat.OUT_SERIES.name
    summers_ = json.loads(hs_.read_text(encoding="utf-8"))["notes"]["window"]["summers"] if hs_.exists() else None
    return {"barrios": len(pairs), "spearman": round(spearman([a for a, _ in pairs], [b for _, b in pairs]), 3), "heat_summers": summers_}


def compute(refresh=False, offline=False, today=None):
    import numpy as np
    import conditions
    B = conditions.Barrios()
    nb = len(B.ids)
    years = heat.summers(today)
    scs = scenes(years, refresh, offline)
    if len(scs) < FLOOR_SCENES:
        raise SystemExit(f"vegetation: only {len(scs)} Sentinel-2 scenes for the summers {years[0]}-{years[-1]} (2026-11-04: 984)")
    lab, X, Y, shape, gtr, labgrid = heat.grid(B)
    xy = {EPSG: (X, Y)}
    for epsg in sorted({s["epsg"] for s in scs} - {EPSG}):
        xy[epsg] = tuple(np.asarray(a) for a in raster.transform_points(X, Y, EPSG, epsg))
    per_year = ", ".join(f"{y}: {sum(s['date'][:4] == str(y) for s in scs)}" for y in years)
    log(f"  {len(scs)} scenes ({per_year}); {len(lab):,} cells of {heat.RES:.0f} m in {nb} barrios")
    ndvi, nobs, used, npass, total = composite(scs, xy, len(lab), offline)
    heat.save_cells(heat.cells_file(CACHE, scs), X, Y, ndvi)   # every cell's value, for hexgrid.py (cache only)
    have = np.isfinite(ndvi)
    cover = float(have.mean())
    dense = have & (ndvi >= DENSE)
    sparse = have & (ndvi < SPARSE)
    pop_sparse, pop_unknown = heat.residents_on(sparse, have, *heat.block_cells(B, shape, gtr, labgrid, len(lab)), nb)
    res = [B.unit[b]["pop"] for b in B.ids]

    def stats(cells, residents_idx):
        v = ndvi[cells][have[cells]]
        if v.size < MIN_CELLS:
            return None
        p = float(sum(pop_sparse[j] for j in residents_idx)); r = sum(res[j] for j in residents_idx)
        return {"med": round(float(np.median(v)), 2), "dense": round(float((v >= DENSE).mean() * 100), 1), "sparse": round(float((v < SPARSE).mean() * 100), 1),
                "res": int(p), "res_pct": round(p / r * 100, 1) if r else None, "cells": int(v.size), "obs": int(np.median(nobs[cells][have[cells]]))}
    by_b = [np.flatnonzero(lab == i) for i in range(nb)]
    brow = [stats(by_b[i], [i]) for i in range(nb)]
    mrows = {}
    for f in B.mids:
        ii = [i for i in range(nb) if B.muni_of(i) == f]
        mrows[f] = stats(np.concatenate([by_b[i] for i in ii]) if ii else np.array([], dtype=np.int64), ii)
    isl = stats(np.arange(len(lab)), range(nb))
    link = heat_link(B, brow)
    bad = []
    if not (CHECK_MEDIAN[0] <= isl["med"] <= CHECK_MEDIAN[1]):
        bad.append(f"Puerto Rico's median NDVI is {isl['med']}, outside {CHECK_MEDIAN}")
    if mrows[SAN_JUAN] is None or mrows[SAN_JUAN]["med"] >= isl["med"]:
        bad.append(f"San Juan's median NDVI ({mrows[SAN_JUAN] and mrows[SAN_JUAN]['med']}) is not below Puerto Rico's ({isl['med']})")
    for f in GREEN:
        if mrows[f] is None or mrows[f]["med"] <= isl["med"]:
            bad.append(f"{f}'s median NDVI ({mrows[f] and mrows[f]['med']}) is not above Puerto Rico's ({isl['med']})")
    if cover < CHECK_COVER:
        bad.append(f"only {cover:.1%} of the cells have {MIN_OBS} or more clear views")
    if link is not None and link["spearman"] > CHECK_HEAT_RHO:
        bad.append(f"across {link['barrios']} barrios, greener is not cooler: Spearman {link['spearman']} (expected {CHECK_HEAT_RHO} or less)")
    if bad:
        raise SystemExit("vegetation: the composite fails its checks:\n  " + "\n  ".join(bad))
    log(f"  composite: {cover:.1%} of cells with a value; median NDVI {isl['med']}, dense {isl['dense']}%, little or none {isl['sparse']}%; San Juan "
        f"{mrows[SAN_JUAN]['med']}, Jayuya {mrows['72073']['med']}, Adjuntas {mrows['72001']['med']}; {total:,} clear observations from {used} passes; "
        f"heat link {link}")
    Y_ = str(years[-1])
    G = "Environment · Vegetation (Sentinel-2)"
    win = f"June to September {years[0]}-{years[-1]}"
    REF = (f"Copernicus Sentinel-2 Level-2A surface reflectance (Collection 1), red B04, near-infrared B08 and scene classification SCL, {len(scs)} scenes of {win} with "
           f"less than {MAX_CLOUD}% cloud cover, read from the Earth Search catalog on AWS at 40 m; the median of each 60 m cell's clear views. Contains modified "
           f"Copernicus Sentinel data {years[0]}-{years[-1]}")
    NDVI = ("NDVI, the normalized difference vegetation index, is (near-infrared − red) / (near-infrared + red): green leaves reflect near-infrared light and absorb red, "
            "so it is near 0 on pavement, roofs and bare ground and 0.6 to 0.9 under dense forest. It shows how green the land looks from above, not tree cover. "
            f"Sentinel-2 passes at about 11:00 local time; each 60 m cell's value is the median of its cloud-free views of {win} (at least {MIN_OBS}; the typical cell "
            f"has {isl['obs']}), read at 40 m, so a pixel mixes roofs, yards and trees. A cell belongs to the barrio that holds its center; a municipio's and Puerto "
            "Rico's figures pool the cells of their barrios. Water is left out. The same months and grid as the surface heat figures (Landsat), so the two compare.")
    DENSE_ = f" Dense vegetation is NDVI {DENSE} or more, the range USGS gives for forests and crops at their peak."
    SPARSE_ = f" Little or no vegetation is NDVI below {SPARSE}: USGS reads 0.1 or less as rock, sand or bare ground and 0.2 to 0.5 as sparse cover; here that is mostly pavement, roofs and bare soil."
    RES_ = (" Each 2020 census block with residents counts whole on the cell under its internal point, in the barrio the crosswalk gives it; the share is over all the "
            "2020 residents of the area. An estimate, rough for a barrio.")

    def var(key, label, unit, d, typ, definition, field, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["copernicus_sentinel2_l2a", "census_tiger"], "ref": REF,
                "definition": definition, "family": "environment", "counted": False, "barrioFile": OUT_BARRIO.name, "noValue": NO_VIEWS, "noPerHU": True, **extra,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("veg_ndvi_med", "Median vegetation greenness, summer (Sentinel-2 NDVI)", "", 2, "ratio",
              "The median NDVI of the area's land: half the land is greener. " + NDVI, "med"),
          var("veg_dense_pct", "Land with dense vegetation, summer (Sentinel-2, %)", "%", 1, "rate",
              "The share of the area's land with NDVI 0.6 or more." + DENSE_ + " " + NDVI, "dense"),
          var("veg_sparse_pct", "Land with little or no vegetation, summer (Sentinel-2, %)", "%", 1, "rate",
              "The share of the area's land with NDVI below 0.2." + SPARSE_ + " " + NDVI, "sparse"),
          var("veg_res_sparse", "Residents on land with little or no vegetation (estimate)", "", 0, "count",
              "The 2020 census residents living on land with NDVI below 0.2." + SPARSE_ + RES_ + " " + NDVI, "res", tag="estimate", classes="jenks"),
          var("veg_res_sparse_pct", "Residents on land with little or no vegetation (estimate, %)", "%", 1, "rate",
              "The share of the 2020 census residents living on land with NDVI below 0.2." + SPARSE_ + RES_ + " " + NDVI, "res_pct", tag="estimate")]
    out_b = {"veg_ndvi_med": "med", "veg_dense_pct": "dense", "veg_sparse_pct": "sparse", "veg_res_sparse": "res", "veg_res_sparse_pct": "res_pct"}
    no_res = [B.ids[i] for i in range(nb) if brow[i] is not None and not res[i]]
    why = {"veg_res_sparse_pct": [{"why": "No residents in 2020", "ids": no_res}]} if no_res else {}
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, **({"noValueWhy": why[k]} if k in why else {}), "years": {Y_: [None if r is None else r[fld] for r in brow]}} for k, fld in out_b.items()],
              "notes": {"areas": nb, "source": "vegetation.py; the municipio values and the method are in vegetation_series.json", "estimates": ["veg_res_sparse", "veg_res_sparse_pct"]}}
    notes = {"window": {"summers": years, "months": list(MONTHS), "max_scene_cloud_pct": MAX_CLOUD, "scenes_found": len(scs), "passes": npass, "passes_with_clear_cells": used,
                        "first": scs[0]["date"], "last": scs[-1]["date"]},
             "grid": {"epsg": EPSG, "cell_m": heat.RES, "read_at_m": 40, "cells": int(len(lab)), "cells_with_value_pct": round(cover * 100, 1), "median_views": isl["obs"]},
             "composite": {"clear_observations": total, "statistic": "median of the clear views, one per pass", "min_views": MIN_OBS, "clear_classes_scl": list(CLEAR_SCL)},
             "classes": {"dense_ndvi_at_least": DENSE, "little_or_none_ndvi_below": SPARSE},
             "checks": {"pr_median": isl["med"], "san_juan_median": mrows[SAN_JUAN]["med"], "jayuya_median": mrows["72073"]["med"], "adjuntas_median": mrows["72001"]["med"],
                        "greener_is_cooler": link},
             "residents_on_cells_without_value": int(pop_unknown),
             "no_value": {"barrios": [B.ids[i] for i in range(nb) if brow[i] is None], "municipios": [f for f in B.mids if mrows[f] is None]}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    return series, barrio


def build(refresh=False, check=False):
    series, barrio = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python vegetation.py")
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
