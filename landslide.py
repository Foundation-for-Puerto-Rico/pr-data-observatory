"""Landslide susceptibility for the PR Data Observatory, for the 901 barrios and the 78 municipios: how much of the land, and how many of the residents, lie in the
high, very high and extremely high classes of the USGS map of susceptibility to landslides triggered by intense rainfall (Hughes and Schulz, 2020).

    python landslide.py             # build site/data/landslide_series.json and site/data/landslide_barrio.json (downloads only the map tiles missing from cache/landslide/)
    python landslide.py --refresh   # download the map tiles and the service's description again
    python landslide.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

The source. Hughes, K.S., and Schulz, W.H., 2020, Map depicting susceptibility to landslides triggered by intense rainfall, Puerto Rico: USGS Open-File Report
2020-1022 (https://doi.org/10.3133/ofr20201022), and its GIS layer, Schulz and Hughes, 2021, USGS data release (https://doi.org/10.5066/P990ZP4C): a 5 m raster of the
main island in five classes (Low, Moderate, High, Very High, Extremely High), set by area: the lowest 40% of the island is Low, then 30% Moderate, 20% High, 9% Very
High and the top 1% Extremely High (the report's table 5). USGS data are public domain; the data release states CC0 1.0. Vieques, Culebra, Mona and the other small
islands are not in the model.

How it is read. The data release lives on ScienceBase, which refuses scripted downloads behind a bot check, and the observatory does not get around it (the same
rule as environment_series.py, which reads the landslide inventory from the first author's copy). Looked for again on 2026-10-18 with plain requests: the DOI
resolves to the ScienceBase item, and the item's JSON (?format=json) and its file links answer with the bot check; the report's own folder on pubs.usgs.gov
(https://pubs.usgs.gov/of/2020/1022/) is open to scripts but holds no classified raster (map sheets as PDF and georeferenced TIFF pictures, KMZ pictures, and
SI_raster_for_SMAP.zip, the susceptibility index before its soil-moisture term, not the published classes). The freshness check watches the copy and the release's
DOI record at DataCite (refresh/sources.json, usgs_landslide_map). So the build reads the map the way the repository reads that
inventory: from the copy the first author (K. S. Hughes, University of Puerto Rico at Mayaguez) publishes on ArcGIS Online, a tile service of the 5 m raster
("Susceptibilidad_Derrumbe_PR", item ae6770d5b81e4a0e918d58b001948cb3): 256-pixel PNG tiles with one flat colour per class (grey Low, yellow Moderate, orange High,
red Very High, blue-violet Extremely High; transparent where there is no data). The tiles of zoom level 15 (4.8 m a pixel in Web Mercator, about 4.5 m on the
ground at Puerto Rico's latitude, finer than the 5 m cells) are decoded with zlib and numpy (no raster library: rasterio is not in the project's environment), each
pixel's colour is turned back into its class, and the build stops if a tile holds any other colour. Two checks against the report prove that the tiles are the
published map: the area of each class must be the report's share of the island (40, 30, 20, 9 and 1%, within 1 point) and its total about 8,700 km2; and the
71,431 slope failures of the Hurricane Maria inventory (cache/environment, environment_series.py) must fall in the classes as the report's table 5 says (1.2, 10.0,
29.4, 44.6 and 14.9%, within 2 points).

How each figure is made (docs/landslide.md):
  - Land: each classified pixel is counted, with its ground area (Web Mercator pixels shrink by the square of the cosine of the latitude), in the barrio whose
    outline (site/data/barrios.geojson) holds its centre, or the nearest outline within about 1 km (the generalised coast). A barrio's share of land in a class is the
    classified area of the class over all the classified area of the barrio. A municipio's and Puerto Rico's shares come from the areas of their barrios.
  - Residents: each 2020 census block with residents (site/data/population_blocks.json) counts whole in the class of the pixel under its internal point, in the
    barrio whose outline holds the point. A share is over all the 2020 residents of the barrio (geo/crosswalk.json). Rough below the municipio: a block that a class
    edge cuts is counted on one side (the same rule as exposure.py).
  - Barrios and municipios the map does not cover (Vieques, Culebra, Isla de Mona e Islote Monito) have no value, and the datasets say why (noValue).
No personal data: the files hold areas, shares and counts of residents.
"""

import json
import math
import struct
import sys
import time
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "landslide"
OUT = hs.OUT
OUT_SERIES = OUT / "landslide_series.json"
OUT_BARRIO = OUT / "landslide_barrio.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
log = hs.log

SERVICE = "https://tiles.arcgis.com/tiles/TQ9qkk0dURXSP7LQ/arcgis/rest/services/Susceptibilidad_Derrumbe_PR/MapServer"
ITEM = "https://www.arcgis.com/sharing/rest/content/items/ae6770d5b81e4a0e918d58b001948cb3"
Z = 15                                   # zoom level read: 4.78 m a pixel in Web Mercator, about 4.5 m on the ground at 18 degrees north
BOX = (-67.30, 17.86, -65.56, 18.54)     # the main island (lon, lat); Vieques, Culebra and Mona are not in the model
NEAR_DEG = 0.01                          # a classified pixel outside every barrio outline (the generalised coast) goes to the nearest outline within this distance (about 1 km)
EARTH = 6378137.0
CLASSES = ["low", "moderate", "high", "very_high", "extremely_high"]
CLASS_VARS = [   # the share of the land in each class, one dataset each (added 2026-10-18, when the catalog had room): key, label, what the class is
    ("ls_cls_low_pct", "Land in the Low landslide susceptibility class (USGS, %)", "Low: the least susceptible 40% of the main island"),
    ("ls_cls_moderate_pct", "Land in the Moderate landslide susceptibility class (USGS, %)", "Moderate: the next 30%"),
    ("ls_cls_high_pct", "Land in the High landslide susceptibility class (USGS, %)", "High: the next 20%"),
    ("ls_cls_very_high_pct", "Land in the Very High landslide susceptibility class (USGS, %)", "Very High: the next 9%"),
    ("ls_cls_extremely_high_pct", "Land in the Extremely High landslide susceptibility class (USGS, %)", "Extremely High: the most susceptible 1%"),
]
COLOURS = {(204, 204, 204): 1, (255, 255, 0): 2, (255, 170, 0): 3, (255, 0, 0): 4, (0, 92, 230): 5}   # the service's legend: grey, yellow, orange, red, blue-violet
REPORT_AREA_PCT = [40, 30, 20, 9, 1]                 # Hughes and Schulz (2020), table 5: share of the island in each class
REPORT_AREA_KM2 = 8700.2                             # table 5, total
REPORT_SLIDES_PCT = [1.2, 10.0, 29.4, 44.6, 14.9]    # table 5: share of the 71,431 Hurricane Maria slope failures in each class
TOL_AREA, TOL_SLIDES, TOL_KM2 = 1.0, 2.0, 0.02       # points, points, share of the total
MAP_YEAR = 2020                                      # the year the map was published (Open-File Report 2020-1022); its GIS layer followed in 2021 (DataCite: issued 2021, registered 2021-08-18)
FLOOR_TILES = 6000                                   # 2026-10-18: 7,294 tiles over the main island, every one with data
NOT_MAPPED = "Not mapped: the USGS susceptibility map covers the main island only"
NO_RESIDENTS = "No residents in 2020"                 # why a barrio of the main island has no share of residents (Cedro, Emajagual and Santa Rosa had none in the 2020 census)

SOURCES = {
    "usgs_landslide_map": {
        "name": "USGS — Landslide susceptibility map of Puerto Rico (Hughes and Schulz, 2020; GIS layer, 2021)",
        "url": "https://doi.org/10.5066/P990ZP4C",
        "license": "US Government work, public domain (the data release states CC0 1.0)",
        "note": "Read from the first author's tile copy of the 5 m raster on ArcGIS Online (University of Puerto Rico at Mayaguez), because ScienceBase refuses scripted downloads; checked against the report's class areas and table 5. Not a substitute for a site-specific slope-stability study."},
    "census_tiger": {"name": "US Census Bureau — 2020 census blocks and county subdivisions", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)",
                     "note": "Barrio outlines, and the 2020 residents of each block and barrio."},
}


# ── Download ─────────────────────────────────────────────────────────────────

BUSY = {429, 500, 502, 503, 504}


def get(url, tries=6):
    """A GET with a polite retry (a 429 or a 5xx answer, a timeout or a dropped connection waits 4, 8, 16, 32, 60 s); a 404 is returned to the caller."""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 120))
            if r.status_code == 404:
                return r
            if r.status_code in BUSY and attempt < tries - 1:
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise SystemExit(f"landslide: {url} failed: {e}")
            time.sleep(min(60, 4 * 2 ** attempt))


def tile_range():
    """The (x, y) of every zoom-15 tile over the main island's box."""
    n = 2 ** Z
    tx = lambda lon: int((lon + 180) / 360 * n)
    ty = lambda lat: int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return [(x, y) for x in range(tx(BOX[0]), tx(BOX[2]) + 1) for y in range(ty(BOX[3]), ty(BOX[1]) + 1)]


def tile_box(x, y):
    n = 2 ** Z
    lon = lambda X: X / n * 360 - 180
    lat = lambda Y: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y / n))))
    return lon(x), lat(y + 1), lon(x + 1), lat(y)


def wanted_tiles(B):
    """The tiles that touch a barrio of the main island (within NEAR_DEG): the others are sea."""
    import shapely
    from shapely.geometry import box
    land = shapely.union_all([g for g in B.geoms if g.intersects(box(*BOX))]).buffer(NEAR_DEG)
    shapely.prepare(land)
    return [(x, y) for x, y in tile_range() if land.intersects(box(*tile_box(x, y)))]


def fetch_tiles(tiles, refresh=False, offline=False):
    """{(x, y): png bytes} for the tiles with data; the tiles the service does not have (404: no data there) are listed in the cache and skipped."""
    d = CACHE / f"z{Z}"
    gone_p = d / "_404.json"
    gone = set(map(tuple, json.loads(gone_p.read_text(encoding="utf-8")))) if gone_p.exists() and not refresh else set()
    todo = [t for t in tiles if t not in gone and (refresh or not (d / f"{t[0]}_{t[1]}.png").exists())]
    if todo and offline:
        raise SystemExit(f"landslide --check: {len(todo)} map tiles are not in the cache (python landslide.py downloads them; --check never does)")
    if todo:
        d.mkdir(parents=True, exist_ok=True)
        log(f"  downloading {len(todo)} map tiles of zoom {Z}")

        def one(t):
            r = get(f"{SERVICE}/tile/{Z}/{t[1]}/{t[0]}")
            if r.status_code == 404:
                return t, None
            if r.content[:8] != b"\x89PNG\r\n\x1a\n":
                raise SystemExit(f"landslide: tile {t} is not a PNG ({r.headers.get('content-type')})")
            (d / f"{t[0]}_{t[1]}.png").write_bytes(r.content)
            return t, True
        with ThreadPoolExecutor(6) as ex:
            for k, (t, ok) in enumerate(ex.map(one, todo)):
                if ok is None:
                    gone.add(t)
                if (k + 1) % 1000 == 0:
                    log(f"    {k + 1} of {len(todo)}")
        gone_p.write_text(json.dumps(sorted(gone)), encoding="utf-8")
    out = {}
    for t in tiles:
        p = d / f"{t[0]}_{t[1]}.png"
        if t not in gone and p.exists():
            out[t] = p.read_bytes()
    return out


def item_info(refresh=False, offline=False):
    """The service's description on ArcGIS Online (title, owner, dates): the freshness check reads the same 'modified' date."""
    p = CACHE / "item.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit("landslide --check: cache/landslide/item.json is missing")
    j = get(ITEM + "?f=json").json()
    keep = {k: j.get(k) for k in ("id", "title", "owner", "created", "modified", "snippet", "url")}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    return keep


# ── PNG tiles to classes ─────────────────────────────────────────────────────

def png_indexed(b):
    """(palette indexes as a 2-D uint8 array, palette [(r, g, b)], alpha of each palette entry or None) of a palette PNG (colour type 3, not interlaced)."""
    import numpy as np
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    i, idat, plte, trns, hdr = 8, [], None, None, None
    while i < len(b):
        n, = struct.unpack(">I", b[i:i + 4])
        t, d = b[i + 4:i + 8], b[i + 8:i + 8 + n]
        i += 12 + n
        if t == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", d)
        elif t == b"PLTE":
            plte = [tuple(d[j:j + 3]) for j in range(0, len(d), 3)]
        elif t == b"tRNS":
            trns = list(d)
        elif t == b"IDAT":
            idat.append(d)
        elif t == b"IEND":
            break
    w, h, depth, ctype, _, _, inter = hdr
    if ctype != 3 or inter != 0 or depth not in (1, 2, 4, 8):
        raise ValueError(f"PNG colour type {ctype}, depth {depth}, interlace {inter}: only non-interlaced palette images are read")
    raw = zlib.decompress(b"".join(idat))
    stride = (w * depth + 7) // 8
    rows = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int32)
    pos = 0
    for yy in range(h):   # undo the row filters (the filter unit is one byte for a palette image)
        f = raw[pos]
        line = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=pos + 1).astype(np.int32)
        pos += 1 + stride
        if f == 0:
            cur = line
        elif f == 1:
            cur = np.cumsum(line) & 255
        elif f == 2:
            cur = (line + prev) & 255
        elif f in (3, 4):
            cur = np.empty(stride, dtype=np.int32)
            a = c = 0
            for xx in range(stride):
                up = int(prev[xx])
                if f == 3:
                    a = (int(line[xx]) + ((a + up) >> 1)) & 255
                else:
                    p = a + up - c
                    pa, pb, pc = abs(p - a), abs(p - up), abs(p - c)
                    a = (int(line[xx]) + (a if pa <= pb and pa <= pc else up if pb <= pc else c)) & 255
                    c = up
                cur[xx] = a
        else:
            raise ValueError(f"PNG row filter {f}")
        rows[yy] = cur
        prev = cur
    if depth == 8:
        return rows[:, :w], plte, trns
    bits = np.unpackbits(rows, axis=1)[:, :w * depth].reshape(h, w, depth)
    return (bits * (1 << np.arange(depth - 1, -1, -1))).sum(axis=2).astype(np.uint8), plte, trns


def tile_classes(b):
    """The class of each pixel of a tile (0 no data, 1 Low ... 5 Extremely High); a colour outside the legend stops the build."""
    import numpy as np
    idx, plte, trns = png_indexed(b)
    lut = np.zeros(256, dtype=np.uint8)
    for k, rgb in enumerate(plte or []):
        alpha = trns[k] if trns and k < len(trns) else 255
        if alpha == 0:
            continue
        if alpha != 255 or rgb not in COLOURS:
            raise SystemExit(f"landslide: a tile holds the colour {rgb} (alpha {alpha}), which is not in the map's legend: the service changed; read it again by hand")
        lut[k] = COLOURS[rgb]
    return lut[idx]


def pixel_grid(x, y):
    """Longitude and latitude of the centre of every pixel of a tile (256 x 256), and each pixel's ground area in m2."""
    import numpy as np
    n = 256 * 2 ** Z
    c = (np.arange(256) + 0.5)
    lon = (x * 256 + c) / n * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * (y * 256 + c) / n))))
    res = 2 * math.pi * EARTH / n
    area = (res * np.cos(np.radians(lat))) ** 2
    LON, LAT = np.meshgrid(lon, lat)
    return LON, LAT, np.broadcast_to(area[:, None], (256, 256))


# ── Build ────────────────────────────────────────────────────────────────────

def compute(refresh=False, offline=False):
    import numpy as np
    import shapely
    from shapely.geometry import box
    import conditions
    import environment_series as envs
    B = conditions.Barrios()
    for g in B.geoms:
        shapely.prepare(g)
    nb = len(B.ids)
    tiles = wanted_tiles(B)
    png = fetch_tiles(tiles, refresh, offline)
    info = item_info(refresh, offline)
    if len(png) < FLOOR_TILES:
        raise SystemExit(f"landslide: only {len(png)} map tiles with data (2026-10-18: 7,294, every tile over the main island)")
    log(f"  {len(png)} map tiles with data, of {len(tiles)} over the main island")

    # blocks with residents, by the tile and pixel under their internal point
    blocks = json.loads((OUT / "population_blocks.json").read_text(encoding="utf-8"))
    n = 256 * 2 ** Z
    by_tile = {}
    for k, r in enumerate(blocks):
        lon, lat = r[0], r[1]
        X = (lon + 180) / 360 * n
        Y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        by_tile.setdefault((int(X) // 256, int(Y) // 256), []).append((k, int(Y) % 256, int(X) % 256))
    block_class = [0] * len(blocks)

    # inventory points of Hurricane Maria, for the check against table 5
    slides = envs.cached("slope_failures_maria.json", envs.slide_points, False, offline)
    s_tile = {}
    for lon, lat in slides:
        X = (lon + 180) / 360 * n
        Y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        s_tile.setdefault((int(X) // 256, int(Y) // 256), []).append((int(Y) % 256, int(X) % 256))
    slide_cls = Counter()

    acc = np.zeros(nb * 6)
    outside = np.zeros(6)
    near = 0
    for (x, y), b in png.items():
        cls = tile_classes(b)
        for (row, col) in s_tile.get((x, y), ()):
            slide_cls[int(cls[row, col])] += 1
        for (k, row, col) in by_tile.get((x, y), ()):
            block_class[k] = int(cls[row, col])
        have = cls > 0
        if not have.any():
            continue
        LON, LAT, AREA = pixel_grid(x, y)
        owner = np.full((256, 256), -1, dtype=np.int64)
        tb = box(*tile_box(x, y))
        cand = sorted(int(j) for j in B.tree.query(tb, predicate="intersects"))
        whole = [j for j in cand if B.geoms[j].contains(tb)]
        if whole:
            owner[:] = whole[0]
        else:
            for j in cand:
                m = (owner < 0) & have
                if not m.any():
                    break
                inside = shapely.contains_xy(B.geoms[j], LON[m], LAT[m])
                owner[np.where(m)[0][inside], np.where(m)[1][inside]] = j
            rest = (owner < 0) & have
            if rest.any():
                pts = shapely.points(LON[rest], LAT[rest])
                pi, gi = B.tree.query_nearest(pts, max_distance=NEAR_DEG)
                got = np.full(len(pts), -1, dtype=np.int64)
                for p, g in zip(pi, gi):   # equally near two outlines: the lower index (the crosswalk's order), so the result does not depend on the tree
                    if got[p] < 0 or g < got[p]:
                        got[p] = g
                near += int((got >= 0).sum())
                owner[np.where(rest)[0], np.where(rest)[1]] = got
        sel = have & (owner >= 0)
        np.add.at(acc, owner[sel] * 6 + cls[sel], AREA[sel])
        lost = have & (owner < 0)
        if lost.any():
            np.add.at(outside, cls[lost], AREA[lost])
    area = acc.reshape(nb, 6)[:, 1:] / 1e6   # km2 by barrio and class
    lost_km2 = outside[1:] / 1e6

    # the checks against the report
    tot = area.sum(axis=0) + lost_km2
    island_km2 = float(tot.sum())
    pct = [float(v / island_km2 * 100) for v in tot]
    bad = [f"{c}: {p:.2f}% of the classified area, the report says {r}%" for c, p, r in zip(CLASSES, pct, REPORT_AREA_PCT) if abs(p - r) > TOL_AREA]
    if abs(island_km2 - REPORT_AREA_KM2) > TOL_KM2 * REPORT_AREA_KM2:
        bad.append(f"the classified area is {island_km2:,.1f} km2, the report says {REPORT_AREA_KM2:,.1f}")
    placed = sum(slide_cls[c] for c in range(1, 6))
    spct = [slide_cls[c] / placed * 100 if placed else 0 for c in range(1, 6)]
    bad += [f"{c}: {p:.1f}% of the Maria slope failures, the report's table 5 says {r}%" for c, p, r in zip(CLASSES, spct, REPORT_SLIDES_PCT) if abs(p - r) > TOL_SLIDES]
    if bad:
        raise SystemExit("landslide: the tiles are not the published map:\n  " + "\n  ".join(bad))
    log("  classes (km2): " + ", ".join(f"{c} {v:,.1f} ({p:.1f}%)" for c, v, p in zip(CLASSES, tot, pct)) + f"; Maria slope failures by class: " + ", ".join(f"{p:.1f}%" for p in spct))

    # residents
    pop_b = np.zeros(nb)
    nodata_pop = 0
    for k, r in enumerate(blocks):
        if not r[2]:
            continue
        c = block_class[k]
        i = B.at(r[0], r[1])
        if i is None:
            continue
        if c >= 3:
            pop_b[i] += r[2]
        elif c == 0 and B.ids[i][:5] not in NOT_IN_MODEL:   # a block whose internal point falls on a pixel with no class (the coast): counted as not in the high classes
            nodata_pop += r[2]
    res = [B.unit[b]["pop"] for b in B.ids]

    mapped = area.sum(axis=1) > 0
    out_b = {"ls_land_high_pct": [], "ls_land_vhigh_pct": [], "ls_res_high": [], "ls_res_high_pct": []}
    cls_b = {c: [] for c in CLASSES}
    for i in range(nb):
        t = area[i].sum()
        ok = bool(mapped[i])   # a barrio with no classified pixel is not in the map (Vieques, Culebra, Isla de Mona)
        for k, c in enumerate(CLASSES):
            cls_b[c].append(round(float(area[i, k] / t * 100), 2) if ok else None)
        out_b["ls_land_high_pct"].append(round(float(area[i, 2:].sum() / t * 100), 2) if ok else None)
        out_b["ls_land_vhigh_pct"].append(round(float(area[i, 3:].sum() / t * 100), 2) if ok else None)
        out_b["ls_res_high"].append(int(pop_b[i]) if ok else None)
        out_b["ls_res_high_pct"].append((round(float(pop_b[i] / res[i] * 100), 2) if res[i] else None) if ok else None)

    def roll(idx):
        idx = [i for i in idx if out_b["ls_land_high_pct"][i] is not None]
        if not idx:
            return None
        a = area[idx].sum(axis=0)
        p = float(sum(pop_b[i] for i in idx))
        r = sum(res[i] for i in idx)
        return {"cls": [round(float(v / a.sum() * 100), 2) for v in a], "high": round(float(a[2:].sum() / a.sum() * 100), 2), "vhigh": round(float(a[3:].sum() / a.sum() * 100), 2),
                "res": int(p), "res_pct": round(p / r * 100, 2) if r else None, "residents": r}
    mrows = {f: roll([i for i in range(nb) if B.muni_of(i) == f]) for f in B.mids}
    isl = roll(range(nb))
    col = lambda key: [None if mrows[f] is None else mrows[f][key] for f in B.mids] + [isl[key]]

    G = "Environment · Landslide susceptibility (USGS)"
    REF = f"USGS landslide susceptibility map of Puerto Rico (Hughes and Schulz, 2020; Open-File Report 2020-1022; GIS layer, data release 10.5066/P990ZP4C), read from the first author's 5 m tile copy at zoom {Z}"
    CLS = ("The USGS map ranks every 5 m cell of the main island by how likely it is to slide during or soon after intense rainfall, such as a hurricane's, and sorts the island into five classes by area: "
           "the 40% least susceptible is Low, then Moderate (30%), High (20%), Very High (9%) and Extremely High (the top 1%). The classes are relative to Puerto Rico, not a probability. "
           "It does not show where a slide travels downhill, and it is not a substitute for a site-specific slope-stability study.")
    LAND = (" A barrio's share is the classified area of those classes over all its classified land, from the map read at about 4.5 m a pixel; a municipio's and Puerto Rico's shares come from the areas of their barrios. "
            "Vieques, Culebra and Isla de Mona are not in the map and have no value; Puerto Rico's figure is the main island's.")
    RES = (" Each 2020 census block with residents counts whole in the class under its internal point (a block that a class edge crosses counts on one side), in the barrio that holds the point; "
           "the share is over all the 2020 residents of the area. An estimate, rough for a barrio. Vieques, Culebra and Isla de Mona have no value; Puerto Rico's figure is the main island's "
           f"(the share is over the main island's {isl['residents']:,} residents; the Economy tab's 'per 1,000 residents' view divides Puerto Rico's count by all {sum(res):,} residents, Vieques and Culebra included, "
           f"as it does for every dataset, so it reads {isl['res'] / sum(res) * 1000:.1f} where the share reads {isl['res_pct']:.1f}%). A barrio with no residents in 2020 has no share.")

    def var(key, label, unit, d, typ, definition, muni_vals, island, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["usgs_landslide_map", "census_tiger"], "ref": REF, "definition": definition,
                "family": "environment", "counted": False, "barrioFile": OUT_BARRIO.name, "noValue": NOT_MAPPED, "noPerHU": True, **extra, "years": {str(MAP_YEAR): [*muni_vals, island]}}
    vs = [var("ls_land_high_pct", "Land highly susceptible to landslides (USGS, %)", "%", 1, "rate",
              "The share of the land in the three highest classes of the USGS map of susceptibility to landslides triggered by intense rainfall (High, Very High and Extremely High: the most susceptible 30% of the main island). " + CLS + LAND,
              col("high")[:-1], isl["high"]),
          var("ls_land_vhigh_pct", "Land very highly susceptible to landslides (USGS, %)", "%", 1, "rate",
              "The share of the land in the two highest classes of the USGS map (Very High and Extremely High: the most susceptible 10% of the main island). " + CLS + LAND,
              col("vhigh")[:-1], isl["vhigh"]),
          var("ls_res_high", "Residents on land highly susceptible to landslides (estimate)", "", 0, "count",
              "The 2020 census residents living in the three highest classes of the USGS landslide susceptibility map (High, Very High and Extremely High)." + RES,
              col("res")[:-1], isl["res"], tag="estimate", classes="jenks"),
          var("ls_res_high_pct", "Residents on land highly susceptible to landslides (estimate, %)", "%", 1, "rate",
              "The share of the 2020 census residents living in the three highest classes of the USGS landslide susceptibility map (High, Very High and Extremely High)." + RES,
              col("res_pct")[:-1], isl["res_pct"], tag="estimate")]
    for k, (key, label, what) in enumerate(CLASS_VARS):
        vs.append(var(key, label, "%", 1, "rate", f"The share of the land in one class of the USGS map of susceptibility to landslides triggered by intense rainfall ({what}). The five classes add up to 100%. " + CLS + LAND,
                      [None if mrows[f] is None else mrows[f]["cls"][k] for f in B.mids], isl["cls"][k]))
        out_b[key] = cls_b[CLASSES[k]]
    notes = {"tiles": {"zoom": Z, "with_data": len(png), "over_the_island": len(tiles), "pixel_m_mercator": round(2 * math.pi * EARTH / (256 * 2 ** Z), 2)},
             "service": {k: info.get(k) for k in ("id", "title", "owner", "modified")},
             "checks": {"classified_km2": round(island_km2, 1), "report_km2": REPORT_AREA_KM2, "class_pct": [round(p, 2) for p in pct], "report_class_pct": REPORT_AREA_PCT,
                        "slope_failures": len(slides), "slope_failures_classified": placed, "slope_failures_pct": [round(p, 2) for p in spct], "report_slope_failures_pct": REPORT_SLIDES_PCT},
             "pixels_outside_every_outline_km2": round(float(lost_km2.sum()), 3), "pixels_placed_in_nearest_outline": near,
             "residents_on_unclassified_pixels": int(nodata_pop),
             "not_mapped": {"barrios": [b for b in B.ids if out_b["ls_land_high_pct"][B.idx[b]] is None], "municipios": [f for f in B.mids if mrows[f] is None]},
             "residents_of_the_main_island": isl["residents"]}
    series = {"as_of": str(MAP_YEAR), "years": [MAP_YEAR], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs,
              "sources": SOURCES, "notes": notes}
    no_res = [B.ids[i] for i in range(nb) if mapped[i] and not res[i]]   # on the map, but no 2020 residents: a share of nobody has no value, and it is not "not mapped"
    why = {"ls_res_high_pct": [{"why": NO_RESIDENTS, "ids": no_res}]} if no_res else {}
    barrio = {"level": "barrio", "geo": {"ids": B.ids}, "vars": [{"key": k, **({"noValueWhy": why[k]} if k in why else {}), "years": {str(MAP_YEAR): v}} for k, v in out_b.items()],
              "notes": {"areas": nb, "source": "landslide.py; the municipio values and the method are in landslide_series.json", "estimates": ["ls_res_high", "ls_res_high_pct"]}}
    return series, barrio


NOT_IN_MODEL = ("72147", "72049")                  # Vieques and Culebra: islands the model does not cover


def build(refresh=False, check=False):
    series, barrio = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python landslide.py")
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
