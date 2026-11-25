"""Daytime land surface temperature for the PR Data Observatory, for the 901 barrios and the 78 municipios: how hot the ground, roofs and pavement get on clear
summer mornings, from Landsat 8 and 9, and how many residents live on the hottest land. Step 1 of the terrain and climate plan (docs/terrain-climate-proposal-2026-11.md,
HANDOFF decision 80; method in docs/heat.md).

    python heat.py             # build site/data/heat_series.json and site/data/heat_barrio.json (downloads only the Landsat tiles missing from cache/heat/)
    python heat.py --refresh   # search the scene catalog again (new scenes are downloaded; cached tiles are kept)
    python heat.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

The source. USGS Landsat Collection 2 Level-2 surface temperature (band ST_B10, from the thermal infrared sensor TIRS, about 100 m, delivered on a 30 m grid) and its
pixel quality band (QA_PIXEL), read from Microsoft Planetary Computer's copy with its anonymous token (the AWS copy is requester-pays). US Government work, public domain.
Surface temperature is the radiative temperature of the ground, roofs, pavement and canopy, not the air temperature people breathe: on a sunny morning a dark roof can be
20 C or more above the air. Landsat passes Puerto Rico at about 10:30 local time, so these are mid-morning values, not the afternoon peak or the night.

How it is made (docs/heat.md):
  - Scenes: every Landsat 8 and 9 Level-2 scene over Puerto Rico from June to September of the last three complete summers, with less than 70% cloud cover (six path/rows,
    004-006 by 047-048, about 90 scenes a summer; UTM zones 19 and 20).
  - Grid: one 60 m grid in UTM zone 20 (EPSG:32620) over the barrios; scenes are read at their first overview (60 m; the thermal band is natively about 100 m) with
    raster.py, by HTTP range requests, and each grid cell takes the value of the scene pixel under its center (scenes in zone 19 are mapped through pyproj).
  - Clear pixels: an observation counts when QA_PIXEL says clear (bit 6), not cloud shadow (bit 4), not water (bit 7), not fill (bit 0), and the surface temperature is set.
  - Composite: each cell's value is the median of its clear observations, so a thin cloud edge the flags miss (it reads cold) or a hot outlier moves it little; the
    median is exact (all clear observations are kept in memory, about 60 million). Cells with fewer than 3 clear observations have no value. (A mean clipped at 2.5
    standard deviations was tried first and dropped on 2026-11-04: with fewer than 8 views one outlier inflates the spread so much that it can never be clipped.)
  - Gap fill: USGS leaves the surface temperature empty where ASTER GED, the emissivity it needs, has no value: parts of the northwest (Aguada, Aguadilla, Rincón,
    Moca, Isabela) and the east, in every scene. There the build computes it from the same scene's thermal radiance and atmosphere bands with an emissivity from NDVI,
    fitted on USGS's own emissivity; every build checks the method against USGS where both exist and stops if the bias passes 0.5 K or the spread 1.2 K (see
    EMIS_NDVI and fill_check). The files say how much of each municipio was filled (notes.gap_fill).
  - Areas: a cell belongs to the barrio whose outline (site/data/barrios.geojson) holds its center (the rule of landslide.py). Municipios and Puerto Rico pool the cells of
    their barrios (not an average of barrio figures).
  - Hot land: the cells above Puerto Rico's 90th percentile of the composite (all barrios). A barrio's share of hot land is its cells above that threshold over its cells
    with a value; Puerto Rico's is 10% by construction.
  - Residents: each 2020 census block with residents counts whole on the cell under its internal point, in the barrio the geography crosswalk gives it
    (network.load_block_table and geo.block_barrios, the rule of exposure.py), so the barrios' residents add up to the crosswalk's; an estimate, rough for a barrio.
  - Checks that stop the build: Puerto Rico's median between 25 and 45 C; San Juan's median above Puerto Rico's (urban heat); Jayuya's and Adjuntas's below it (the
    Cordillera is cooler); at least 95% of the cells with a value.
No personal data: the files hold temperatures, shares and counts of residents.
"""

import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import raster
import surface_image

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "heat"
OUT = hs.OUT
OUT_SERIES = OUT / "heat_series.json"
OUT_SURFACE = OUT / "heat_surface.json"   # the surface on the maps: its corners and scale
OUT_SURFACE_PNG = OUT / "heat_surface.png"
SURFACE_MIN_LON = -67.35                         # Mona, Monito and Desecheo are left out of the image (open sea would widen it past 4,096 px)
OUT_BARRIO = OUT / "heat_barrio.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
log = hs.log

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"
COLLECTION = "landsat-c2-l2"
PLATFORMS = ["landsat-8", "landsat-9"]
SEARCH_BOX = [-67.95, 17.85, -65.2, 18.55]       # Puerto Rico with Vieques, Culebra and Mona
MONTHS = (6, 9)                                  # June to September
SUMMERS = 3                                      # the last three complete summers
MAX_CLOUD = 70                                   # scene cloud cover, %
EPSG = 32620                                     # the grid: UTM zone 20 north
RES = 60.0                                       # m
LEVEL = 1                                        # the first overview of the 30 m scenes: 60 m
ST_SCALE, ST_OFFSET = 0.00341802, 149.0          # USGS Collection 2 Level-2: ST in kelvin = DN x scale + offset
MIN_OBS = 3
# Gap fill (decided 2026-11-04, docs/heat.md "Where USGS has no surface temperature"): USGS leaves ST_B10 empty where ASTER GED, the emissivity it needs, has no
# value (parts of the northwest and the east, in every scene). There the build computes the surface temperature itself from the scene's own thermal radiance and
# atmosphere bands (ST_TRAD, ST_URAD, ST_DRAD, ST_ATRAN), with an emissivity read from NDVI (SR_B4, SR_B5) on the table below: the median of USGS's own
# emissivity (ST_EMIS) by NDVI, fitted on six summer scenes of 2024-2026 (2.69 million clear pixels, paths 004 and 005). Leaving each scene out in turn, the
# method gives USGS's surface temperature with a bias of -0.12 to +0.18 K and a spread of 0.60 to 0.85 K per pixel and view. Every build checks it again (fill_check).
EMIS_NDVI = ([-0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
             [0.988, 0.988, 0.988, 0.988, 0.9696, 0.9652, 0.965, 0.9648, 0.9644, 0.965, 0.9665, 0.9686, 0.9714, 0.975, 0.9776, 0.9795, 0.981, 0.9824, 0.9836,
              0.9849, 0.9861, 0.9869, 0.9862, 0.9816])
K_TIRS = {"LC08": (774.8853, 1321.0789), "LC09": (799.0284, 1329.2405)}   # band 10 thermal constants K1, K2 (the scenes' MTL files; USGS Landsat 8-9 handbooks)
FILL_BANDS = ("ST_TRAD", "ST_URAD", "ST_DRAD", "ST_ATRAN", "SR_B4", "SR_B5")
FILL_CHECK_SCENES, FILL_MAX_BIAS, FILL_MAX_SD = 3, 0.5, 1.2
MIN_CELLS = 5                                    # a barrio needs at least this many cells with a value (0.018 km2)
HOT_PCT = 90                                     # hot land: above Puerto Rico's 90th percentile
CHECK_MEDIAN = (25.0, 45.0)
CHECK_COVER = 0.95
SAN_JUAN, COOL = "72127", ("72073", "72001")     # San Juan; Jayuya and Adjuntas
FLOOR_SCENES = 150                               # 2026-11-04: about 270 scenes in three summers
NO_VIEWS = "Too few cloud-free Landsat views"

SOURCES = {
    "usgs_landsat_c2_st": {
        "name": "USGS — Landsat 8 and 9 Collection 2 Level-2 surface temperature (ST_B10) and pixel quality (QA_PIXEL)",
        "url": "https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature",
        "license": "US Government work, public domain (cite USGS)",
        "note": "Read from Microsoft Planetary Computer's copy (collection landsat-c2-l2) with its anonymous token, at 60 m, by HTTP range requests (raster.py). Surface temperature, not air temperature."},
    "census_tiger": {"name": "US Census Bureau — 2020 census blocks and county subdivisions", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)",
                     "note": "Barrio outlines, and the 2020 residents of each block and barrio."},
}


def summers(today=None):
    """The last SUMMERS complete summers (June to September): a summer is complete once October has begun."""
    today = today or date.today()
    last = today.year if today.month >= 10 else today.year - 1
    return list(range(last - SUMMERS + 1, last + 1))


# ── Scene catalog ──────────────────────────────────────────────────────────

def post(url, body, tries=6):
    for attempt in range(tries):
        try:
            r = requests.post(url, json=body, headers=UA, timeout=(30, 120))
            if r.status_code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise SystemExit(f"heat: {url} failed: {e}")
            time.sleep(min(60, 4 * 2 ** attempt))


def scenes(years, refresh=False, offline=False):
    """[{id, date, epsg, cloud, st, qa}] for the summers, from the cache or the STAC search (hrefs without the token)."""
    p = CACHE / f"scenes_{years[0]}_{years[-1]}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"heat --check: {p.relative_to(ROOT)} is missing (python heat.py makes it)")
    out = []
    for y in years:
        body = {"collections": [COLLECTION], "bbox": SEARCH_BOX, "limit": 250,
                "datetime": f"{y}-{MONTHS[0]:02d}-01T00:00:00Z/{y}-{MONTHS[1]:02d}-30T23:59:59Z",
                "query": {"platform": {"in": PLATFORMS}, "eo:cloud_cover": {"lt": MAX_CLOUD}}}
        page = post(f"{STAC}/search", body)
        feats = list(page["features"])
        while any(l.get("rel") == "next" for l in page.get("links", [])):
            nxt = next(l for l in page["links"] if l.get("rel") == "next")
            page = post(nxt["href"], nxt.get("body", body))
            feats += page["features"]
        for f in feats:
            pr = f["properties"]
            epsg = pr.get("proj:epsg") or int(str(pr.get("proj:code", "")).split(":")[-1] or 0)
            out.append({"id": f["id"], "date": pr["datetime"][:10], "epsg": int(epsg), "cloud": pr["eo:cloud_cover"],
                        "st": f["assets"]["lwir11"]["href"], "qa": f["assets"]["qa_pixel"]["href"]})
    out.sort(key=lambda s: (s["date"], s["id"]))
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


class Token:
    """Planetary Computer's anonymous SAS token for the Landsat container, renewed every 20 minutes."""

    def __init__(self, session):
        self.s, self.tok, self.at = session, None, 0

    def __call__(self):
        if self.tok is None or time.time() - self.at > 1200:
            for attempt in range(6):
                try:
                    r = self.s.get(TOKEN, headers=UA, timeout=60)
                    r.raise_for_status()
                    self.tok, self.at = r.json()["token"], time.time()
                    break
                except requests.RequestException as e:
                    if attempt == 5:
                        raise SystemExit(f"heat: the Planetary Computer token failed: {e}")
                    time.sleep(4 * 2 ** attempt)
        return self.tok


# ── Grid ─────────────────────────────────────────────────────────────────────

def grid(B):
    """The cells of the 60 m grid whose center is in a barrio: (barrio index of each cell, x, y in EPSG:32620, shape, transform)."""
    import numpy as np
    import shapely
    from shapely.ops import transform as shp_transform
    tr = raster._transformer(4326, EPSG)
    geoms = [shp_transform(tr.transform, g) for g in B.geoms]
    minx = min(g.bounds[0] for g in geoms); miny = min(g.bounds[1] for g in geoms)
    maxx = max(g.bounds[2] for g in geoms); maxy = max(g.bounds[3] for g in geoms)
    x0, y0 = math.floor(minx / RES) * RES, math.ceil(maxy / RES) * RES
    W, H = int(math.ceil((maxx - x0) / RES)), int(math.ceil((y0 - miny) / RES))
    lab = np.full((H, W), -1, dtype=np.int32)
    for i, g in enumerate(geoms):
        gx0, gy0, gx1, gy1 = g.bounds
        c0, c1 = max(int((gx0 - x0) / RES), 0), min(int(math.ceil((gx1 - x0) / RES)), W)
        r0, r1 = max(int((y0 - gy1) / RES), 0), min(int(math.ceil((y0 - gy0) / RES)), H)
        if c0 >= c1 or r0 >= r1:
            continue
        cc, rr = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
        inside = shapely.contains_xy(g, x0 + (cc + 0.5) * RES, y0 - (rr + 0.5) * RES)
        sub = lab[r0:r1, c0:c1]
        sub[inside & (sub < 0)] = i            # a center on a shared edge goes to the lower index (the crosswalk's order)
    rows, cols = np.nonzero(lab >= 0)
    return lab[rows, cols], x0 + (cols + 0.5) * RES, y0 - (rows + 0.5) * RES, (H, W), (RES, 0.0, x0, 0.0, -RES, y0), lab


# ── Cells for the hexagon grid ───────────────────────────────────────────────

def cells_file(cache, scs):
    """cache/<name>/cells_<hash of the scene ids>.npz: one summer composite's value of every 60 m cell (never published; a new scene set gives a new file)."""
    import hashlib
    return cache / f"cells_{hashlib.sha1(chr(10).join(sorted(s['id'] for s in scs)).encode()).hexdigest()[:12]}.npz"


def save_cells(f, X, Y, v):
    import numpy as np
    f.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f, x=X, y=Y, v=np.asarray(v, dtype=np.float32))


def load_cells(f):
    import numpy as np
    z = np.load(f)
    return z["x"], z["y"], z["v"]


def cells(module, offline=True, today=None):
    """(x, y in EPSG:32620, value) of every 60 m cell of heat.py's or vegetation.py's composite (`module`), as float32 values, for hexgrid.py: from the file each
    build leaves in its cache, or the composite again from the module's cache (no network when offline; about 6 minutes for heat, 5 for vegetation)."""
    import numpy as np
    import conditions
    scs = module.scenes(summers(today), False, offline)
    f = cells_file(module.CACHE, scs)
    if not f.exists():
        lab, X, Y = grid(conditions.Barrios())[:3]
        xy = {EPSG: (X, Y)}
        for epsg in sorted({s["epsg"] for s in scs} - {EPSG}):
            xy[epsg] = tuple(np.asarray(a) for a in raster.transform_points(X, Y, EPSG, epsg))
        save_cells(f, X, Y, module.composite(scs, xy, len(lab), offline)[0])
    return load_cells(f)


# ── Composite ────────────────────────────────────────────────────────────────

def band(sc, name):
    """The address of another band of the scene (they share the name up to the band)."""
    return sc["st"].replace("_ST_B10.TIF", f"_{name}.TIF")


def clear_cells(qa, col, row):
    """The positions of the clear land observations: QA_PIXEL clear (bit 6), not cloud shadow (bit 4), not water (bit 7), not fill (bit 0)."""
    import numpy as np
    qv, inside = qa.values_at(col, row, LEVEL)
    qv = qv.astype(np.int64)
    return np.flatnonzero(inside & ((qv & 1) == 0) & ((qv >> 6) & 1 == 1) & ((qv >> 4) & 1 == 0) & ((qv >> 7) & 1 == 0))


def computed_st(sc, cols, rows, session, tok, offline):
    """Surface temperature in C at pixels of overview LEVEL, computed from the scene's radiance and atmosphere bands and an emissivity from NDVI
    (the gap fill); nan where a band is missing."""
    import numpy as np
    q = "?" + tok() if sc["st"].startswith("http") and not offline else ""
    v = {}
    for name in FILL_BANDS:
        c = raster.COG(band(sc, name) + q, cache=CACHE / "tiles", session=session, offline=offline, workers=12)
        x, _ = c.values_at(cols, rows, LEVEL)
        v[name] = x.astype(np.float64)
    ok = (v["ST_TRAD"] > 0) & (v["ST_ATRAN"] > 0) & (v["SR_B4"] > 0) & (v["SR_B5"] > 0)
    red, nir = v["SR_B4"] * 0.0000275 - 0.2, v["SR_B5"] * 0.0000275 - 0.2             # Collection 2 surface reflectance scale and offset
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = np.clip((nir - red) / (nir + red), -1, 1)
        eps = np.interp(ndvi, *EMIS_NDVI)
        tr, ur, dr, at = v["ST_TRAD"] * 0.001, v["ST_URAD"] * 0.001, v["ST_DRAD"] * 0.001, v["ST_ATRAN"] * 0.0001
        surf = ((tr - ur) / at - (1 - eps) * dr) / eps                                  # surface-leaving blackbody radiance
        K1, K2 = K_TIRS[sc["id"][:4]]
        t = K2 / np.log(K1 / surf + 1) - 273.15
    return np.where(ok & np.isfinite(t), t, np.nan)


def open_pair(sc, session, tok, offline):
    q = "?" + tok() if sc["st"].startswith("http") and not offline else ""   # the token only for a remote copy; the cache key leaves it out
    st = raster.COG(sc["st"] + q, cache=CACHE / "tiles", session=session, offline=offline, workers=12)
    qa = raster.COG(sc["qa"] + q, cache=CACHE / "tiles", session=session, offline=offline, workers=12)
    if len(st.levels) <= LEVEL or (st.levels[LEVEL].width, st.levels[LEVEL].height) != (qa.levels[LEVEL].width, qa.levels[LEVEL].height):
        raise SystemExit(f"heat: {sc['id']}: ST and QA_PIXEL do not share overview {LEVEL}")
    return st, qa


def pixels(cog, xy):
    import numpy as np
    X, Y = xy[cog.epsg]
    a, _, c, _, e, f = cog.level_transform(LEVEL)
    return np.floor((X - c) / a).astype(np.int64), np.floor((Y - f) / e).astype(np.int64)


def scene_values(sc, xy, tok, session, offline):
    """(cell indexes, surface temperatures in C, filled) of the clear observations of one scene, or None when the scene has no clear cell. `filled` marks the
    observations the build computed itself because USGS has no surface temperature there (the gap fill). Only the tiles under the grid's cells are read
    (raster.COG.values_at), not the sea around them."""
    import numpy as np
    st, qa = open_pair(sc, session, tok, offline)
    col, row = pixels(st, xy)
    idx = clear_cells(qa, col, row)
    if not idx.size:
        return None
    s, _ = st.values_at(col[idx], row[idx], LEVEL)      # the temperature band only where QA_PIXEL says clear land
    t = np.where(s > 0, s.astype(np.float64) * ST_SCALE + ST_OFFSET - 273.15, np.nan)
    gap = s == 0
    filled = np.zeros(len(idx), bool)
    if gap.any():                                       # USGS has no surface temperature here (no ASTER GED emissivity): compute it
        t[gap] = computed_st(sc, col[idx][gap], row[idx][gap], session, tok, offline)
        filled[gap] = True
    ok = np.isfinite(t)
    if not ok.any():
        return None
    return idx[ok], t[ok], filled[ok]


def fill_check(scs, xy, session, tok, offline):
    """The gap fill against USGS where both exist: on the FILL_CHECK_SCENES clearest scenes, the method's surface temperature minus USGS's at every 7th clear
    cell that has USGS's value. The build stops when the bias or the spread is above FILL_MAX_BIAS or FILL_MAX_SD (kelvin)."""
    import numpy as np
    out = []
    for sc in sorted(scs, key=lambda x: (x["cloud"], x["id"]))[:FILL_CHECK_SCENES]:
        st, qa = open_pair(sc, session, tok, offline)
        col, row = pixels(st, xy)
        col, row = col[::7], row[::7]
        k = clear_cells(qa, col, row)
        s, _ = st.values_at(col[k], row[k], LEVEL)
        k, s = k[s > 0], s[s > 0]
        usgs = s.astype(np.float64) * ST_SCALE + ST_OFFSET - 273.15
        mine = computed_st(sc, col[k], row[k], session, tok, offline)
        d = (mine - usgs)[np.isfinite(mine)]
        out.append({"scene": sc["id"], "pixels": int(d.size), "bias_k": round(float(d.mean()), 3), "sd_k": round(float(d.std()), 3)})
    bad = [r for r in out if abs(r["bias_k"]) > FILL_MAX_BIAS or r["sd_k"] > FILL_MAX_SD or r["pixels"] < 1000]
    if bad:
        raise SystemExit(f"heat: the gap fill does not reproduce USGS's surface temperature: {bad}")
    return out


def median_by_cell(idx, t, n_cells):
    """The median of the values of each cell (nan where a cell has none) and the number of values, from flat arrays of cell indexes and values."""
    import numpy as np
    n = np.bincount(idx, minlength=n_cells)
    order = np.lexsort((t, idx))
    ts = t[order]
    start = np.concatenate([[0], np.cumsum(n)[:-1]])
    med = np.full(n_cells, np.nan)
    has = n > 0
    lo = start[has] + (n[has] - 1) // 2
    hi = start[has] + n[has] // 2
    med[has] = (ts[lo].astype(np.float64) + ts[hi]) / 2
    return med, n


def composite(scs, xy, n_cells, offline, tok=None, parallel=3, check_fill=True):
    """Per cell: the median of its clear observations (nan below MIN_OBS views), the number of views, how many of them the gap fill computed, the scenes that
    gave a clear cell, the number of observations, and the gap fill's check against USGS."""
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=48))
    tok = tok or Token(session)
    parts, used = [], []
    with ThreadPoolExecutor(parallel) as ex:          # a few scenes at once; each reads its tiles in parallel too
        for k, (sc, v) in enumerate(zip(scs, ex.map(lambda sc: scene_values(sc, xy, tok, session, offline), scs))):
            if v is not None:
                parts.append((v[0].astype(np.int32), v[1].astype(np.float32), v[2]))
                used.append(sc["id"])
            if (k + 1) % 25 == 0:
                log(f"    {k + 1} of {len(scs)} scenes read")
    if not parts:
        raise SystemExit("heat: no scene has a clear cell")
    idx = np.concatenate([p[0] for p in parts])
    t = np.concatenate([p[1] for p in parts])
    nfill = np.bincount(idx[np.concatenate([p[2] for p in parts])], minlength=n_cells)
    med, n = median_by_cell(idx, t, n_cells)
    lst = np.where(n >= MIN_OBS, med, np.nan)
    check = fill_check(scs, xy, session, tok, offline) if check_fill else []
    return lst, n, nfill, used, int(idx.size), check


# ── Residents ────────────────────────────────────────────────────────────────

def block_cells(B, shape, gtr, labgrid, n_cells):
    """Each 2020 census block with residents: (its cell, -1 when its internal point is on no cell; its residents; its barrio's index). A block counts in the barrio the
    crosswalk gives it (geo.block_barrios, the rule that makes the crosswalk's residents), on the cell under its internal point; so a barrio's residents on some
    kind of land never exceed its residents, and the barrios add up to the municipios. Shared with vegetation.py."""
    import numpy as np
    import geo
    import network
    table = network.load_block_table(ROOT / "cache" / "network", False)
    barrio_of = geo.block_barrios(table, False, ROOT / "cache" / "geo")
    rows_ = [(r, bo) for r, bo in zip(table["rows"], barrio_of) if r[1] and bo in B.idx]
    bx, by = raster.transform_points([r[4] for r, _ in rows_], [r[5] for r, _ in rows_], 4326, EPSG)
    H, W = shape
    a, _, x0, _, e, y0 = gtr
    bc = np.floor((np.asarray(bx) - x0) / a).astype(np.int64)
    br = np.floor((np.asarray(by) - y0) / e).astype(np.int64)
    cell_of = np.full(H * W, -1, dtype=np.int64)
    rows, cols = np.nonzero(labgrid >= 0)
    cell_of[rows * W + cols] = np.arange(n_cells)
    inside = (br >= 0) & (br < H) & (bc >= 0) & (bc < W)
    ci = np.where(inside, cell_of[np.where(inside, br * W + bc, 0)], -1)
    return ci, np.array([r[1] for r, _ in rows_], dtype=np.int64), np.array([B.idx[bo] for _, bo in rows_], dtype=np.int64)


def residents_on(sel, have, ci, pop, bi, nb):
    """(residents per barrio on the cells `sel` marks, residents whose point is on no cell with a value). A point on water or off the generalized outlines counts
    as not on the selected land."""
    import numpy as np
    known = (ci >= 0) & have[np.maximum(ci, 0)]
    on = known & sel[np.maximum(ci, 0)]
    return np.bincount(bi[on], weights=pop[on], minlength=nb), int(pop[~known].sum())


# ── Build ────────────────────────────────────────────────────────────────────

def compute(refresh=False, offline=False, today=None):
    import numpy as np
    import conditions
    B = conditions.Barrios()
    nb = len(B.ids)
    years = summers(today)
    scs = scenes(years, refresh, offline)
    if len(scs) < FLOOR_SCENES:
        raise SystemExit(f"heat: only {len(scs)} Landsat scenes for the summers {years[0]}-{years[-1]} (2026-11-04: about 270)")
    lab, X, Y, shape, gtr, labgrid = grid(B)
    xy = {EPSG: (X, Y)}
    for epsg in sorted({s["epsg"] for s in scs} - {EPSG}):
        xy[epsg] = raster.transform_points(X, Y, EPSG, epsg)
    per_year = ", ".join(f"{y}: {sum(s['date'][:4] == str(y) for s in scs)}" for y in years)
    log(f"  {len(scs)} scenes ({per_year}); {len(lab):,} cells of {RES:.0f} m in {nb} barrios")
    lst, nobs, nfill, used, total, fcheck = composite(scs, xy, len(lab), offline)
    save_cells(cells_file(CACHE, scs), X, Y, lst)   # every cell's value, for hexgrid.py (cache only)
    have = np.isfinite(lst)
    cover = float(have.mean())
    thr = float(np.percentile(lst[have], HOT_PCT))
    hot = have & (lst > thr)
    pop_hot, pop_unknown = residents_on(hot, have, *block_cells(B, shape, gtr, labgrid, len(lab)), nb)
    res = [B.unit[b]["pop"] for b in B.ids]

    def stats(cells, residents_idx):
        v = lst[cells][have[cells]]
        if v.size < MIN_CELLS:
            return None
        p = float(sum(pop_hot[j] for j in residents_idx)); r = sum(res[j] for j in residents_idx)
        return {"med": round(float(np.median(v)), 1), "p90": round(float(np.percentile(v, 90)), 1),
                "hot": round(float((v > thr).mean() * 100), 1), "res": int(p), "res_pct": round(p / r * 100, 1) if r else None,
                "cells": int(v.size), "obs": int(np.median(nobs[cells][have[cells]])),
                "filled_pct": round(float((nfill[cells][have[cells]] * 2 > nobs[cells][have[cells]]).mean() * 100), 1)}
    by_b = [np.flatnonzero(lab == i) for i in range(nb)]
    brow = [stats(by_b[i], [i]) for i in range(nb)]
    mrows = {}
    for f in B.mids:
        ii = [i for i in range(nb) if B.muni_of(i) == f]
        mrows[f] = stats(np.concatenate([by_b[i] for i in ii]) if ii else np.array([], dtype=np.int64), ii)
    isl = stats(np.arange(len(lab)), range(nb))
    # the checks
    bad = []
    if not (CHECK_MEDIAN[0] <= isl["med"] <= CHECK_MEDIAN[1]):
        bad.append(f"Puerto Rico's median surface temperature is {isl['med']} C, outside {CHECK_MEDIAN}")
    if mrows[SAN_JUAN] is None or mrows[SAN_JUAN]["med"] <= isl["med"]:
        bad.append(f"San Juan's median ({mrows[SAN_JUAN] and mrows[SAN_JUAN]['med']} C) is not above Puerto Rico's ({isl['med']} C)")
    for f in COOL:
        if mrows[f] is None or mrows[f]["med"] >= isl["med"]:
            bad.append(f"{f}'s median ({mrows[f] and mrows[f]['med']} C) is not below Puerto Rico's ({isl['med']} C)")
    if cover < CHECK_COVER:
        bad.append(f"only {cover:.1%} of the cells have {MIN_OBS} or more clear views")
    if bad:
        raise SystemExit("heat: the composite fails its checks:\n  " + "\n  ".join(bad))
    log(f"  composite: {cover:.1%} of cells with a value; median {isl['med']} C, 90th percentile {thr:.1f} C; San Juan {mrows[SAN_JUAN]['med']} C, "
        f"Jayuya {mrows['72073']['med']} C, Adjuntas {mrows['72001']['med']} C; {total:,} clear observations from {len(used)} scenes")
    Y_ = str(years[-1])
    G = "Environment · Surface heat (Landsat)"
    win = f"June to September {years[0]}-{years[-1]}"
    REF = (f"USGS Landsat 8 and 9 Collection 2 Level-2 surface temperature (ST_B10) and QA_PIXEL, {len(used)} scenes of {win} with less than {MAX_CLOUD}% cloud cover, "
           f"read from Microsoft Planetary Computer at {RES:.0f} m; the median of each cell's clear views")
    LST = ("Land surface temperature is the radiative temperature of the ground, roofs, pavement and tree canopy, measured by the satellite's thermal infrared sensor; "
           "it is not the air temperature, and on a sunny morning a dark roof or a parking lot can be 20 °C or more above the air. Landsat passes at about 10:30 local time, "
           f"so these are mid-morning values on clear days of {win}, not the afternoon peak or the night. Each 60 m cell's value is the median of its cloud-free views "
           f"(at least {MIN_OBS}; the typical cell has {isl['obs']}), so a cloud edge the quality flags miss moves it little. "
           "A cell belongs to the barrio that holds its center; a municipio's and Puerto Rico's figures pool the cells of their barrios. Water is left out. "
           "Elevation matters: the Cordillera is cooler than the coast, so compare places at similar heights.")
    HOT = (f" Hot land is the land above Puerto Rico's {HOT_PCT}th percentile of the cells ({thr:.1f} °C), so Puerto Rico's share is 10% by construction.")
    RES_ = (" Each 2020 census block with residents counts whole on the cell under its internal point, in the barrio that holds the point (a block that the edge of hot land "
            "crosses counts on one side); the share is over all the 2020 residents of the area. An estimate, rough for a barrio.")

    def var(key, label, unit, d, typ, definition, field, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["usgs_landsat_c2_st", "census_tiger"], "ref": REF,
                "definition": definition, "family": "environment", "counted": False, "barrioFile": OUT_BARRIO.name, "noValue": NO_VIEWS, "noPerHU": True, **extra,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("heat_lst_med", "Median land surface temperature, summer mornings (Landsat, °C)", "°C", 1, "ratio",
              "The median of the land's surface temperature over the area: half the land is hotter. " + LST, "med"),
          var("heat_lst_p90", "Hottest tenth of the land, surface temperature, summer mornings (Landsat, °C)", "°C", 1, "ratio",
              "The 90th percentile of the land's surface temperature over the area: a tenth of its land is hotter. It shows the hot spots a median hides. " + LST, "p90"),
          var("heat_hot_land_pct", "Land among Puerto Rico's hottest tenth, summer mornings (Landsat, %)", "%", 1, "rate",
              "The share of the area's land whose surface temperature is among the hottest 10% of Puerto Rico's land." + HOT + " " + LST, "hot"),
          var("heat_res_hot", "Residents on Puerto Rico's hottest tenth of land (estimate)", "", 0, "count",
              "The 2020 census residents living on land whose surface temperature is among the hottest 10% of Puerto Rico's land." + HOT + RES_ + " " + LST, "res",
              tag="estimate", classes="jenks"),
          var("heat_res_hot_pct", "Residents on Puerto Rico's hottest tenth of land (estimate, %)", "%", 1, "rate",
              "The share of the 2020 census residents living on land whose surface temperature is among the hottest 10% of Puerto Rico's land." + HOT + RES_ + " " + LST, "res_pct",
              tag="estimate")]
    out_b = {"heat_lst_med": "med", "heat_lst_p90": "p90", "heat_hot_land_pct": "hot", "heat_res_hot": "res", "heat_res_hot_pct": "res_pct"}
    no_res = [B.ids[i] for i in range(nb) if brow[i] is not None and not res[i]]
    why = {"heat_res_hot_pct": [{"why": "No residents in 2020", "ids": no_res}]} if no_res else {}
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, **({"noValueWhy": why[k]} if k in why else {}), "years": {Y_: [None if r is None else r[fld] for r in brow]}} for k, fld in out_b.items()],
              "notes": {"areas": nb, "source": "heat.py; the municipio values and the method are in heat_series.json", "estimates": ["heat_res_hot", "heat_res_hot_pct"]}}
    notes = {"window": {"summers": years, "months": list(MONTHS), "max_scene_cloud_pct": MAX_CLOUD, "scenes_found": len(scs), "scenes_with_clear_cells": len(used),
                        "first": scs[0]["date"], "last": scs[-1]["date"]},
             "grid": {"epsg": EPSG, "cell_m": RES, "cells": int(len(lab)), "cells_with_value_pct": round(cover * 100, 1), "median_views": isl["obs"]},
             "composite": {"clear_observations": total, "statistic": "median of the clear views", "min_views": MIN_OBS},
             "gap_fill": {"why": "USGS leaves surface temperature empty where ASTER GED has no emissivity (parts of the northwest and the east); there heat.py computes it from the scene's radiance and atmosphere bands with an emissivity from NDVI",
                          "cells_mostly_filled_pct": isl["filled_pct"],
                          "municipios_mostly_filled_pct": {B.names[k]: mrows[f]["filled_pct"] for k, f in enumerate(B.mids) if mrows[f] and mrows[f]["filled_pct"] >= 1},
                          "check_against_usgs": fcheck, "max_bias_k": FILL_MAX_BIAS, "max_sd_k": FILL_MAX_SD},
             "hot_threshold_c": round(thr, 1),
             "checks": {"pr_median_c": isl["med"], "san_juan_median_c": mrows[SAN_JUAN]["med"], "jayuya_median_c": mrows["72073"]["med"], "adjuntas_median_c": mrows["72001"]["med"]},
             "residents_on_cells_without_value": int(pop_unknown),
             "no_value": {"barrios": [B.ids[i] for i in range(nb) if brow[i] is None], "municipios": [f for f in B.mids if mrows[f] is None]}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    # the surface on the maps (surface_image.py): every cell, colored around Puerto Rico's median; the ends of the scale hold 2% of the land each side
    v = lst[have]
    half = float(math.ceil(max(isl["med"] - np.percentile(v, 2), np.percentile(v, 98) - isl["med"])))
    png, meta = surface_image.mercator_png(lst, X, Y, EPSG, RES, isl["med"], half, min_lon=SURFACE_MIN_LON)
    surface = {"png": png, "meta": {"what": "Median land surface temperature of summer mornings, by 60 m cell (Landsat 8 and 9)", "image": OUT_SURFACE_PNG.name,
                                     "window": win, "summers": [years[0], years[-1]], "unit": "°C", **meta, "source": REF}}
    log(f"  surface: {meta['size'][0]} x {meta['size'][1]} px of {meta['pixel_m']} m, scale {meta['scale']['low']} to {meta['scale']['high']} °C, {len(png) / 1024:.0f} KB")
    return series, barrio, surface


def build(refresh=False, check=False):
    series, barrio, surface = compute(refresh, offline=check)
    status = 0
    if check:
        same = OUT_SURFACE_PNG.exists() and OUT_SURFACE_PNG.read_bytes() == surface["png"] and OUT_SURFACE.exists()             and {**json.loads(OUT_SURFACE.read_text(encoding="utf-8")), "built": None} == {**json.loads(json.dumps(surface["meta"], ensure_ascii=False)), "built": None}
        print(f"{OUT_SURFACE_PNG.name} and {OUT_SURFACE.name} " + ("match the cache" if same else "are not what the cache gives: run python heat.py"))
        status = 0 if same else 1
    else:
        OUT_SURFACE_PNG.write_bytes(surface["png"])
        OUT_SURFACE.write_text(json.dumps({"built": date.today().isoformat(), **surface["meta"]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {OUT_SURFACE_PNG.name} ({OUT_SURFACE_PNG.stat().st_size / 1024:.0f} KB) and {OUT_SURFACE.name}")
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python heat.py")
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
