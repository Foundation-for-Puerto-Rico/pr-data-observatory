"""Night-time land surface temperature for the PR Data Observatory, for the 901 barrios and the 78 municipios: how warm the ground, roofs and pavement stay after
dark on clear summer nights, from NASA's ECOSTRESS, and how many residents live on the land that stays warmest. Step 2 of the terrain and climate plan
(docs/terrain-climate-proposal-2026-11.md, HANDOFF decision 80; method in docs/ecostress.md). Night heat matters most for health: bodies recover when nights cool.

    python ecostress.py --diagnose   # what the LP DAAC answers for one night granule, and the layout and values of its layers (never prints the token)
    python ecostress.py              # build site/data/night_heat_series.json and night_heat_barrio.json (reads only the granules missing from cache/ecostress/; needs EARTHDATA_TOKEN)
    python ecostress.py --refresh    # search the catalog again
    python ecostress.py --from-cache # write the files again from the cache (no network, no token): after a change of wording
    python ecostress.py --check      # rebuild from the cache and exit 1 when a published file is not what it gives (no network, no token, nothing written)

The login. The LP DAAC's files need a NASA Earthdata login. The build reads FPR's Earthdata user token from the EARTHDATA_TOKEN environment variable (in GitHub
Actions, the repository secret of that name; the one night lights uses, decision 75) and sends it only to NASA's hosts (NASA_HOSTS), in the Authorization header.
The LP DAAC answers with a short-lived signed address of the file in its cloud store, which is read by HTTP range requests without the token. The token is never
printed, written to the cache, the repository or a published file, and the site never calls NASA.

The source. ECOSTRESS Tiled Land Surface Temperature and Emissivity Instantaneous L2 Global 70 m, version 2 (ECO_L2T_LSTE.002), Hook, S., Hulley, G. (2022),
NASA EOSDIS Land Processes DAAC, https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002. ECOSTRESS flies on the International Space Station, whose orbit is not
sun-synchronous, so it passes at different hours: the build keeps the night passes. NASA Earth science data: no restrictions on use, with credit.
"""

import json
import math
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

import surface_image

import heat
import housing_series as hs
import raster

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "ecostress"
OUT = hs.OUT
OUT_SERIES = OUT / "night_heat_series.json"
OUT_BARRIO = OUT / "night_heat_barrio.json"
OUT_SURFACE = OUT / "night_heat_surface.json"     # the night surface on the maps: its corners and scale (decision 88)
OUT_SURFACE_PNG = OUT / "night_heat_surface.png"
UA = heat.UA
log = hs.log

CMR = "https://cmr.earthdata.nasa.gov/search"
COLLECTION = "C2076090826-LPCLOUD"               # ECO_L2T_LSTE version 002 at the LP DAAC (cloud)
SEARCH_BOX = heat.SEARCH_BOX
TOKEN_VAR = "EARTHDATA_TOKEN"
NASA_HOSTS = {"data.lpdaac.earthdatacloud.nasa.gov", "urs.earthdata.nasa.gov"}   # the only hosts the token is sent to
LAYERS = ("LST", "QC", "cloud", "water", "LST_err")
NIGHT_HOURS = set(range(21, 24)) | set(range(0, 6))   # 21:00 to 05:59 Atlantic Standard Time (UTC-4), and the granule's own NIGHT flag


def token():
    t = os.environ.get(TOKEN_VAR, "").strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t or None


NO_TOKEN = (f"ecostress: {TOKEN_VAR} is not set, so nothing was downloaded and no file was changed. The NASA Earthdata token is FPR's "
            "(docs/nightlights-setup.md) and is kept only as a GitHub Actions secret or a local environment variable.")


def tile_epsg(tile):
    """The UTM zone of an MGRS tile (19QHA -> EPSG:32619): ECOSTRESS tiles carry their CRS as text, not as an EPSG code."""
    return 32600 + int(tile[:2])


def local_hour(iso):
    return (int(iso[11:13]) - 4) % 24


def granules(start, end):
    """The ECO_L2T_LSTE granules over Puerto Rico between two dates, from NASA's open catalog (CMR): [{id, time, tile, night, files {layer: url}}]."""
    out, page = [], 1
    while True:
        for attempt in range(6):
            try:
                r = requests.get(f"{CMR}/granules.json", headers=UA, timeout=(30, 120),
                                 params={"collection_concept_id": COLLECTION, "bounding_box": ",".join(map(str, SEARCH_BOX)),
                                         "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z", "page_size": 2000, "page_num": page})
                r.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 5:
                    raise SystemExit(f"ecostress: the CMR search failed: {e}")
                time.sleep(min(60, 4 * 2 ** attempt))
        e = r.json()["feed"]["entry"]
        for g in e:
            files = {}
            for l in g.get("links", []):
                h = l.get("href", "")
                if h.startswith("https://") and h.endswith(".tif"):
                    for name in LAYERS:
                        if h.endswith(f"_{name}.tif"):
                            files[name] = h
            out.append({"id": g["title"], "time": g["time_start"], "tile": g["title"].split("_")[5], "night": g.get("day_night_flag") == "NIGHT", "files": files})
        if len(e) < 2000:
            break
        page += 1
    out.sort(key=lambda g: (g["time"], g["id"]))
    return out


def signed(url, tok, session):
    """(the address to read the file from, hops). The LP DAAC answers a request with the token by a redirect to a signed address in its cloud store; the
    redirects are followed by hand so that the token goes to NASA_HOSTS only. hops lists host and path, never a query string."""
    from urllib.parse import urljoin, urlsplit
    hops = []
    if not str(url).startswith(("https://", "http://")):
        return url, hops                         # a local file (the tests)
    for _ in range(8):
        u = urlsplit(url)
        if u.scheme != "https":
            raise SystemExit(f"ecostress: the LP DAAC sent the file to an address that is not https ({u.netloc}{u.path})")
        if u.hostname not in NASA_HOSTS:
            return url, hops                     # the signed address: read it without the token
        for attempt in range(6):                 # NASA answers 429 or 5xx now and then: wait and ask again
            try:
                r = session.get(url, headers={**UA, "Authorization": f"Bearer {tok}", "Range": "bytes=0-0"}, allow_redirects=False, timeout=(30, 120))
            except requests.RequestException as e:
                if attempt == 5:
                    raise SystemExit(f"ecostress: {u.netloc}{u.path} failed: {e}")
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            break
        hops.append(f"{r.status_code} {u.netloc}{u.path}")
        if 300 <= r.status_code < 400:
            url = urljoin(url, r.headers.get("Location", ""))
            continue
        if r.status_code in (200, 206):
            return url, hops                     # served directly: reads need the token (not expected)
        if r.status_code in (401, 403):
            raise SystemExit(f"ecostress: the LP DAAC refused the file (HTTP {r.status_code}; pages: {' -> '.join(hops)}). The token in {TOKEN_VAR} is missing "
                             "or expired, or the Earthdata account has not accepted the LP DAAC's terms.")
        raise SystemExit(f"ecostress: the LP DAAC answered HTTP {r.status_code} six times (pages: {' -> '.join(hops)}); run again later")
    raise SystemExit("ecostress: too many redirects: " + " -> ".join(hops))


def diagnose(tok):
    """For one summer night granule over San Juan: what the LP DAAC answers, and for each layer its layout (size, tiles, overviews, type, nodata, GDAL metadata)
    and its values over Puerto Rico. Prints no token and no account."""
    import numpy as np
    gs = granules("2025-06-01", "2025-09-30")
    night = [g for g in gs if g["night"] and local_hour(g["time"]) in NIGHT_HOURS and g["tile"] == "19QHA"]
    print(f"catalogue: {len(gs)} granules over Puerto Rico in summer 2025; {sum(g['night'] for g in gs)} flagged NIGHT; "
          f"{len(night)} night ones on tile 19QHA (San Juan) between 21:00 and 05:59")
    s = requests.Session()
    for g in night[:2]:
        print(f"\ngranule {g['id']} ({g['time']}, {local_hour(g['time']):02d}h local); layers: {sorted(g['files'])}")
        for name in LAYERS:
            if name not in g["files"]:
                print(f"  {name}: not listed")
                continue
            url, hops = signed(g["files"][name], tok, s)
            from urllib.parse import urlsplit
            u = urlsplit(url)
            print(f"  {name}: pages {' -> '.join(hops)}; read from {u.netloc}")
            c = raster.COG(url, session=s, workers=8, epsg=tile_epsg(g["tile"]))
            h = raster._Header(c.source)
            gk = raster._geokeys(h.ifds[0].get(raster.TAG["geokeys"]))
            print(f"    geokeys {gk}; citation {str(h.ifds[0].get(34737, ''))[:160]!r}")
            meta = str(h.ifds[0].get(42112, ""))[:300].replace("\n", " ")
            print(f"    epsg {c.epsg}, {c.width}x{c.height}, transform {tuple(round(x, 3) for x in c.transform)}, dtype {c.dtype}, nodata {c.nodata}, "
                  f"levels {[(l.width, l.tw, l.compression) for l in c.levels]}; gdal metadata: {meta}")
            a = c.read_window(0, 0, c.width, c.height, 0).astype(np.float64)
            fin = np.isfinite(a)
            if name in ("LST", "LST_err"):
                v = a[fin & (a != (c.nodata if c.nodata is not None else -1e30))]
                print(f"    finite {fin.mean():.1%}; values: n {v.size}, min {np.nanmin(v) if v.size else None}, p5 {np.percentile(v, 5) if v.size else None}, "
                      f"median {np.median(v) if v.size else None}, p95 {np.percentile(v, 95) if v.size else None}, max {np.nanmax(v) if v.size else None}")
            elif name == "QC":
                q = a[fin].astype(np.int64)
                print("    bits 0-1: " + ", ".join(f"{k}: {(q & 3 == k).mean():.1%}" for k in range(4)) + "; bits 2-3: " +
                      ", ".join(f"{k}: {((q >> 2) & 3 == k).mean():.1%}" for k in range(4)) + f"; most common values {np.unique(q, return_counts=True)[0][:12].tolist()}")
            else:
                vals, cnt = np.unique(a[fin], return_counts=True)
                print(f"    values: {dict(zip(vals.tolist()[:10], (cnt / cnt.sum()).round(3).tolist()[:10]))}")
    return 0


MONTHS = heat.MONTHS                             # June to September, the summers of heat.py
RULE = "v1-qc01-cloud0-water0"                   # the per-granule cache's rule: change it when the reading of a granule changes
MIN_OBS = 3
BLOCKS = 4
MIN_CELLS = heat.MIN_CELLS
HOT_PCT = 90
CHECK_MEDIAN = (15.0, 35.0)
CHECK_COVER = 0.90
SAN_JUAN, COOL = heat.SAN_JUAN, heat.COOL
FLOOR_GRANULES = 150                             # 2026-11-04: about 300 night tiles in three summers
NO_VIEWS = "Too few cloud-free ECOSTRESS night views"

SOURCES = {
    "nasa_ecostress_lste": {
        "name": "NASA ECOSTRESS — Tiled Land Surface Temperature and Emissivity, Instantaneous L2, 70 m, version 2 (ECO_L2T_LSTE.002)",
        "url": "https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002",
        "license": "NASA Earth science data: no restrictions on use, with credit (cite the DOI)",
        "note": "Read from the LP DAAC's cloud store with FPR's NASA Earthdata login, used only by the build; night passes only; summaries, no images. Surface temperature, not air temperature."},
    "census_tiger": heat.SOURCES["census_tiger"],
}


def night_granules(years, refresh=False, offline=False):
    """The night granules of the summers (NIGHT flag and 21:00-05:59 local time, June to September), from the cache or the catalog."""
    p = CACHE / f"granules_{years[0]}_{years[-1]}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"ecostress --check: {p.name} is missing in cache/ecostress (python ecostress.py makes it)")
    out = []
    for y in years:
        out += [g for g in granules(f"{y}-{MONTHS[0]:02d}-01", f"{y}-{MONTHS[1]:02d}-30")
                if g["night"] and local_hour(g["time"]) in NIGHT_HOURS and all(k in g["files"] for k in ("LST", "QC", "cloud", "water"))]
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


def clear_values(lst, qc, cloud, water):
    """The positions and temperatures (C) of the clear land observations: LST set, QC bits 0-1 best (0) or nominal (1), the cloud mask 0, the water mask 0."""
    import numpy as np
    ok = np.isfinite(lst) & ((qc.astype(np.int64) & 3) <= 1) & (cloud == 0) & (water == 0) & (lst > 250) & (lst < 350)
    k = np.flatnonzero(ok)
    return k, lst[k].astype(np.float64) - 273.15


def read_granule(g, xy, tok, session):
    """(cell indexes, temperatures in C x 100) of one granule's clear land cells. Each layer is read only where the grid's cells fall in the tile."""
    import numpy as np
    epsg = tile_epsg(g["tile"])
    cogs = {}
    for name in ("cloud", "water", "QC", "LST"):
        url, _ = signed(g["files"][name], tok, session)
        cogs[name] = raster.COG(url, session=session, workers=8, epsg=epsg)
    X, Y = xy[epsg]
    a, _, c, _, e, f = cogs["LST"].level_transform(0)
    for name, cg in cogs.items():
        if cg.level_transform(0) != (a, 0.0, c, 0.0, e, f) or (cg.width, cg.height) != (cogs["LST"].width, cogs["LST"].height):
            raise SystemExit(f"ecostress: {g['id']}: the {name} layer is not on the LST layer's grid")
    col = np.floor((X - c) / a).astype(np.int64); row = np.floor((Y - f) / e).astype(np.int64)
    cl, inside = cogs["cloud"].values_at(col, row, 0)
    idx = np.flatnonzero(inside & (cl == 0))           # read the other layers only where the cloud mask is clear
    if not idx.size:
        return idx.astype(np.int32), np.zeros(0, np.int16)
    w, _ = cogs["water"].values_at(col[idx], row[idx], 0)
    q, _ = cogs["QC"].values_at(col[idx], row[idx], 0)
    t, _ = cogs["LST"].values_at(col[idx], row[idx], 0)
    k, tc = clear_values(t.astype(np.float64), q, np.zeros(len(idx)), w)
    return idx[k].astype(np.int32), np.round(tc * 100).astype(np.int16)


def granule_values(g, xy, tok=None, session=None, offline=False):
    """(cell indexes, temperatures in C x 100) of one granule, from cache/ecostress/values/ or read and cached."""
    import numpy as np
    p = CACHE / "values" / RULE / f"{g['id']}.npz"
    if p.exists():
        z = np.load(p)
        return np.cumsum(z["d"]).astype(np.int32), z["v"]
    if offline:
        raise SystemExit(f"ecostress --check: the cached values of {g['id']} are missing (python ecostress.py reads them)")
    idx, v = read_granule(g, xy, tok, session)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.stem + ".part.npz")
    np.savez_compressed(tmp, d=np.diff(idx, prepend=0).astype(np.int32), v=v)
    tmp.replace(p)
    return idx, v


def orbit_key(g):
    """The ISS orbit of a granule (ECOv002_L2T_LSTE_<orbit>_<scene>_<tile>_...): the tiles of one orbit overlap where MGRS tiles meet."""
    return g["id"].split("_")[3]


def composite(gs, xy, n_cells, tok=None, offline=False, parallel=4):
    """Per cell: the median night temperature of its clear views (nan below MIN_OBS), the views, the orbits with a clear cell, the orbits, the observations."""
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    import vegetation
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=48))
    clear = {}
    with ThreadPoolExecutor(parallel) as ex:
        for k, (g, n) in enumerate(zip(gs, ex.map(lambda g: len(granule_values(g, xy, tok, session, offline)[0]), gs))):
            clear[g["id"]] = n
            if (k + 1) % 25 == 0:
                log(f"    {k + 1} of {len(gs)} granules read")
    groups = {}
    for g in gs:
        groups.setdefault(orbit_key(g), []).append(g)
    passes = [sorted(v, key=lambda g: g["id"]) for _, v in sorted(groups.items())]
    used = sum(any(clear[g["id"]] for g in p) for p in passes)
    med = np.full(n_cells, np.nan); nobs = np.zeros(n_cells, np.int64); total = 0
    edges = np.linspace(0, n_cells, BLOCKS + 1).astype(np.int64)
    for b in range(BLOCKS):
        lo, hi = edges[b], edges[b + 1]
        ii, vv = [], []
        for p in passes:
            parts = []
            for g in p:
                i, v = granule_values(g, xy, offline=True)
                k = (i >= lo) & (i < hi)
                parts.append((i[k], v[k]))
            i, v = vegetation.one_view_per_pass(parts)
            ii.append(i - lo); vv.append(v)
        i = np.concatenate(ii); v = np.concatenate(vv).astype(np.float64) / 100
        total += i.size
        m, n = heat.median_by_cell(i, v, hi - lo)
        med[lo:hi], nobs[lo:hi] = m, n
    return np.where(nobs >= MIN_OBS, med, np.nan), nobs, used, len(passes), total


def compute(refresh=False, offline=False, today=None):
    import numpy as np
    import conditions
    tok = None if offline else token()
    if not offline and tok is None:
        raise SystemExit(NO_TOKEN)
    B = conditions.Barrios()
    nb = len(B.ids)
    years = heat.summers(today)
    gs = night_granules(years, refresh, offline)
    if len(gs) < FLOOR_GRANULES:
        raise SystemExit(f"ecostress: only {len(gs)} night granules for the summers {years[0]}-{years[-1]} (2026-11-04: about 300)")
    lab, X, Y, shape, gtr, labgrid = heat.grid(B)
    xy = {heat.EPSG: (X, Y)}
    for epsg in sorted({tile_epsg(g["tile"]) for g in gs} - {heat.EPSG}):
        xy[epsg] = tuple(np.asarray(a) for a in raster.transform_points(X, Y, heat.EPSG, epsg))
    hours = {}
    for g in gs:
        hours[local_hour(g["time"])] = hours.get(local_hour(g["time"]), 0) + 1
    per_year = ", ".join(f"{y}: {sum(g['time'][:4] == str(y) for g in gs)}" for y in years)
    log(f"  {len(gs)} night granules ({per_year}); {len(lab):,} cells of {heat.RES:.0f} m in {nb} barrios")
    lst, nobs, used, npass, total = composite(gs, xy, len(lab), tok, offline)
    have = np.isfinite(lst)
    cover = float(have.mean())
    thr = float(np.percentile(lst[have], HOT_PCT))
    hot = have & (lst > thr)
    pop_hot, pop_unknown = heat.residents_on(hot, have, *heat.block_cells(B, shape, gtr, labgrid, len(lab)), nb)
    res = [B.unit[b]["pop"] for b in B.ids]

    def stats(cells, residents_idx):
        v = lst[cells][have[cells]]
        if v.size < MIN_CELLS:
            return None
        p = float(sum(pop_hot[j] for j in residents_idx)); r = sum(res[j] for j in residents_idx)
        return {"med": round(float(np.median(v)), 1), "p90": round(float(np.percentile(v, 90)), 1),
                "hot": round(float((v > thr).mean() * 100), 1), "res": int(p), "res_pct": round(p / r * 100, 1) if r else None,
                "cells": int(v.size), "obs": int(np.median(nobs[cells][have[cells]])),
                "cover": round(float(have[cells].mean() * 100), 1)}
    by_b = [np.flatnonzero(lab == i) for i in range(nb)]
    brow = [stats(by_b[i], [i]) for i in range(nb)]
    mrows = {}
    for f in B.mids:
        ii = [i for i in range(nb) if B.muni_of(i) == f]
        mrows[f] = stats(np.concatenate([by_b[i] for i in ii]) if ii else np.array([], dtype=np.int64), ii)
    isl = stats(np.arange(len(lab)), range(nb))
    day = None
    hp = OUT / heat.OUT_SERIES.name
    if hp.exists():
        hd = json.loads(hp.read_text(encoding="utf-8"))
        day = next(v for v in hd["vars"] if v["key"] == "heat_lst_med")["years"][hd["as_of"]][-1]
    bad = []
    if not (CHECK_MEDIAN[0] <= isl["med"] <= CHECK_MEDIAN[1]):
        bad.append(f"Puerto Rico's median night surface temperature is {isl['med']} C, outside {CHECK_MEDIAN}")
    if mrows[SAN_JUAN] is None or mrows[SAN_JUAN]["med"] <= isl["med"]:
        bad.append(f"San Juan's night median ({mrows[SAN_JUAN] and mrows[SAN_JUAN]['med']} C) is not above Puerto Rico's ({isl['med']} C)")
    for f in COOL:
        if mrows[f] is None or mrows[f]["med"] >= isl["med"]:
            bad.append(f"{f}'s night median ({mrows[f] and mrows[f]['med']} C) is not below Puerto Rico's ({isl['med']} C)")
    if day is not None and isl["med"] >= day:
        bad.append(f"Puerto Rico's night median ({isl['med']} C) is not below its morning median in heat_series.json ({day} C)")
    if cover < CHECK_COVER:
        bad.append(f"only {cover:.1%} of the cells have {MIN_OBS} or more clear night views")
    if bad:
        raise SystemExit("ecostress: the composite fails its checks:\n  " + "\n  ".join(bad))
    log(f"  composite: {cover:.1%} of cells with a value; night median {isl['med']} C, 90th percentile {thr:.1f} C; San Juan {mrows[SAN_JUAN]['med']} C, "
        f"Jayuya {mrows['72073'] and mrows['72073']['med']} C, Adjuntas {mrows['72001'] and mrows['72001']['med']} C; morning median {day} C; "
        f"{total:,} clear observations from {used} of {npass} orbits; typical cell {isl['obs']} views")
    Y_ = str(years[-1])
    G = "Environment · Night surface heat (ECOSTRESS)"
    win = f"June to September {years[0]}-{years[-1]}"
    REF = (f"NASA ECOSTRESS ECO_L2T_LSTE version 2 (70 m), {len(gs)} night granules of {win} between 21:00 and 06:00, read from the LP DAAC; "
           f"the median of each 60 m cell's clear views (https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002)")
    LST = ("Land surface temperature is the radiative temperature of the ground, roofs, pavement and tree canopy, measured by the satellite's thermal sensor; it is not "
           "the air temperature. At night, pavement, roofs and walls give back the heat they stored during the day, so built land stays warmer than fields and forest: "
           "this is what keeps a city from cooling down. ECOSTRESS flies on the International Space Station, which passes at a different hour each time; these are the "
           f"passes between 21:00 and 06:00 on clear nights of {win}. Each 60 m cell's value is the median of its cloud-free night views (at least {MIN_OBS}; the "
           f"typical cell has {isl['obs']}), whatever the hour, so a place seen mostly before midnight reads a little warmer than one seen mostly before dawn. "
           "A cell belongs to the barrio that holds its center; a municipio's and Puerto Rico's figures pool the cells of their barrios. Water is left out. The sea "
           "stays warm at night, so land near the coast stays warmer too, and elevation cools the land: compare coastal places with each other and the Cordillera with itself.")
    HOT = f" Warm land at night is the land above Puerto Rico's {HOT_PCT}th percentile of the cells ({thr:.1f} °C), so Puerto Rico's share is 10% by construction."
    RES_ = (" Each 2020 census block with residents counts whole on the cell under its internal point, in the barrio the crosswalk gives it; the share is over all "
            "the 2020 residents of the area. An estimate, rough for a barrio.")

    def var(key, label, unit, d, typ, definition, field, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["nasa_ecostress_lste", "census_tiger"], "ref": REF,
                "definition": definition, "family": "environment", "counted": False, "barrioFile": OUT_BARRIO.name, "noValue": NO_VIEWS, "noPerHU": True, **extra,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("night_lst_med", "Median land surface temperature, summer nights (ECOSTRESS, °C)", "°C", 1, "ratio",
              "The median of the land's surface temperature at night over the area: half the land is warmer. " + LST, "med"),
          var("night_lst_p90", "Warmest tenth of the land, surface temperature, summer nights (ECOSTRESS, °C)", "°C", 1, "ratio",
              "The 90th percentile of the land's surface temperature at night over the area: a tenth of its land is warmer. " + LST, "p90"),
          var("night_hot_land_pct", "Land among Puerto Rico's warmest tenth at night, summer (ECOSTRESS, %)", "%", 1, "rate",
              "The share of the area's land whose night surface temperature is among the warmest 10% of Puerto Rico's land." + HOT + " " + LST, "hot"),
          var("night_res_hot", "Residents on Puerto Rico's warmest tenth of land at night (estimate)", "", 0, "count",
              "The 2020 census residents living on land whose night surface temperature is among the warmest 10% of Puerto Rico's land." + HOT + RES_ + " " + LST, "res",
              tag="estimate", classes="jenks"),
          var("night_res_hot_pct", "Residents on Puerto Rico's warmest tenth of land at night (estimate, %)", "%", 1, "rate",
              "The share of the 2020 census residents living on land whose night surface temperature is among the warmest 10% of Puerto Rico's land." + HOT + RES_ + " " + LST,
              "res_pct", tag="estimate")]
    out_b = {"night_lst_med": "med", "night_lst_p90": "p90", "night_hot_land_pct": "hot", "night_res_hot": "res", "night_res_hot_pct": "res_pct"}
    no_res = [B.ids[i] for i in range(nb) if brow[i] is not None and not res[i]]
    why = {"night_res_hot_pct": [{"why": "No residents in 2020", "ids": no_res}]} if no_res else {}
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, **({"noValueWhy": why[k]} if k in why else {}), "years": {Y_: [None if r is None else r[fld] for r in brow]}} for k, fld in out_b.items()],
              "notes": {"areas": nb, "source": "ecostress.py; the municipio values and the method are in night_heat_series.json", "estimates": ["night_res_hot", "night_res_hot_pct"]}}
    notes = {"window": {"summers": years, "months": list(MONTHS), "local_hours": "21:00-05:59 (UTC-4)", "granules": len(gs), "orbits": npass, "orbits_with_clear_cells": used,
                        "granules_by_local_hour": {f"{h:02d}": hours[h] for h in sorted(hours, key=lambda h: (h < 12, h))}, "first": gs[0]["time"][:10], "last": gs[-1]["time"][:10]},
             "grid": {"epsg": heat.EPSG, "cell_m": heat.RES, "read_at_m": 70, "cells": int(len(lab)), "cells_with_value_pct": round(cover * 100, 1), "median_views": isl["obs"]},
             "composite": {"clear_observations": total, "statistic": "median of the clear views, one per orbit", "min_views": MIN_OBS,
                           "clear": "LST set, QC bits 0-1 best or nominal, cloud mask 0, water mask 0"},
             "hot_threshold_c": round(thr, 1),
             "checks": {"pr_median_c": isl["med"], "san_juan_median_c": mrows[SAN_JUAN]["med"], "jayuya_median_c": mrows["72073"] and mrows["72073"]["med"],
                        "adjuntas_median_c": mrows["72001"] and mrows["72001"]["med"], "pr_morning_median_c": day},
             "municipios_cover_pct": {B.names[k]: mrows[f]["cover"] for k, f in enumerate(B.mids) if mrows[f] and mrows[f]["cover"] < 95},
             "residents_on_cells_without_value": int(pop_unknown),
             "no_value": {"barrios": [B.ids[i] for i in range(nb) if brow[i] is None], "municipios": [f for f in B.mids if mrows[f] is None]}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    # the night surface on the maps (surface_image.py; HANDOFF decision 88, the day and night switch): every cell, as heat.py draws the mornings
    v = lst[have]
    half = float(math.ceil(max(isl["med"] - np.percentile(v, 2), np.percentile(v, 98) - isl["med"])))
    png, meta = surface_image.mercator_png(lst, X, Y, heat.EPSG, heat.RES, isl["med"], half, min_lon=heat.SURFACE_MIN_LON)
    surface = {"png": png, "meta": {"what": "Median land surface temperature of summer nights, by 60 m cell (ECOSTRESS, read at 70 m)", "image": OUT_SURFACE_PNG.name,
                                     "window": win, "summers": [years[0], years[-1]], "unit": "°C", "time": "night", **meta, "source": REF}}
    log(f"  surface: {meta['size'][0]} x {meta['size'][1]} px, scale {meta['scale']['low']} to {meta['scale']['high']} °C, {len(png) / 1024:.0f} KB")
    return series, barrio, surface


def build(refresh=False, check=False, from_cache=False):
    series, barrio, surface = compute(refresh, offline=check or from_cache)
    status = 0
    if check:
        same = OUT_SURFACE_PNG.exists() and OUT_SURFACE_PNG.read_bytes() == surface["png"] and OUT_SURFACE.exists()             and {**json.loads(OUT_SURFACE.read_text(encoding="utf-8")), "built": None} == {**json.loads(json.dumps(surface["meta"], ensure_ascii=False)), "built": None}
        print(f"{OUT_SURFACE_PNG.name} and {OUT_SURFACE.name} " + ("match the cache" if same else "are not what the cache gives: run python ecostress.py --from-cache"))
        status = 0 if same else 1
    else:
        OUT_SURFACE_PNG.write_bytes(surface["png"])
        OUT_SURFACE.write_text(json.dumps({"built": date.today().isoformat(), **surface["meta"]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {OUT_SURFACE_PNG.name} ({OUT_SURFACE_PNG.stat().st_size / 1024:.0f} KB) and {OUT_SURFACE.name}")
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python ecostress.py")
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
    if "--diagnose" in sys.argv:
        t = token()
        if not t:
            raise SystemExit(NO_TOKEN)
        raise SystemExit(diagnose(t))
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv, "--from-cache" in sys.argv))
