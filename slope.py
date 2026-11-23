"""The slope of the land for the PR Data Observatory, for the 901 barrios and the 78 municipios: how steep the ground is, and how much of it is steeper than 15% and
than 30%, from the USGS 10 m elevation model; and the slope as an image on the maps. Step 2 of the GIS tools plan (docs/gis-tools-proposal-2026-11.md, HANDOFF
decision 93; method in docs/slope.md).

    python slope.py             # build site/data/slope_series.json, slope_barrio.json, slope_surface.json and slope_surface.png (reads the elevation tiles missing from cache/dem/)
    python slope.py --check     # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)

The ground. USGS 3D Elevation Program, 1/3 arc-second (about 10 m) seamless elevation model, the newest version of each one-degree tile over Puerto Rico (the tiles
climb.py reads, listed in cache/dem/tiles.json), read with raster.py in windows of 0.1 degree. Public domain.

How it is made (docs/slope.md):
  - Slope: at every 10 m cell, by Horn's method (the 3 x 3 neighbourhood, as GDAL, QGIS and ArcGIS compute it), with the cell's size in metres at its latitude,
    as a percent (rise over run x 100: 100% is 45 degrees). A cell next to one with no height (the sea) has no slope.
  - Blocks: the 10 m cells are counted in blocks of 6 x 6 (2 arc-seconds, about 60 m): how many have a slope, how many are steeper than 15% and than 30%, and their
    mean slope. A block belongs to the barrio that holds its centre (the nearest within 100 m off the coast); a block across a barrio's edge counts whole on one side.
    Blocks in no barrio (the sea, which the elevation model also covers) are left out of the figures and of the image. The block grids are kept in
    cache/slope/blocks_<tile version>.npz, so --check and a rebuild read no elevation again.
  - Areas: the share of the area's cells with a slope that are steeper than 15% and than 30%, and their mean slope; municipios and Puerto Rico pool their barrios.
  - The image: each block's mean slope on a fixed scale from 0% to 60% (steeper is drawn as 60%), one block per pixel, in Web Mercator like the heat image
    (surface_image.py); Mona, Monito and Desecheo are left out of the image (not of the figures), as in the heat image.
  - Thresholds: 15% is where building and farming begin to need terracing or special design in most planning guides; 30% is where most building codes and Puerto
    Rico's planning rules treat ground as too steep to build on without engineering, and where the USGS map of landslide susceptibility rises steeply.
  - Checks that stop the build: Puerto Rico's share steeper than 30% between 15% and 55%; Jayuya, Orocovis and Barranquitas steeper than Puerto Rico; Cataño with
    less than 5% of its land steeper than 15%; the cells counted cover 97% to 110% of the barrios' Census land area.
No personal data: the files hold shares and means by area, and an image of the ground.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

import climb
import housing_series as hs
import raster
import surface_image

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = hs.OUT
OUT_SERIES = OUT / "slope_series.json"
OUT_BARRIO = OUT / "slope_barrio.json"
OUT_SURFACE = OUT / "slope_surface.json"
OUT_SURFACE_PNG = OUT / "slope_surface.png"
log = hs.log

CELL = 1 / 10800                 # 1/3 arc-second, in degrees
WIN = 0.1                        # a window of 1,080 x 1,080 cells
BLK = 6                          # cells per block side: 2 arc-seconds, about 60 m
BOX = (-68.0, 17.8, -65.2, 18.6)  # the windows looked at: Mona to Culebra (windows with no barrio are skipped)
STEEP = (15, 30)                 # percent
NODATA = -1000                   # heights at or below this are no data (USGS uses -999999 over the sea)
NEAR_DEG = 0.001                 # about 100 m: a block centre just off the coast goes to the nearest barrio within this
SCALE = (0.0, 60.0)              # the image's scale, percent
STOPS = ["#F7F4EA", "#E9D7A5", "#C9A05A", "#8C5A2B", "#3E2410"]   # pale to dark earth: no blue (FEMA), no red or yellow-orange (landslides, heat)
SURFACE_MIN_LON = -67.35         # as heat.py: the image leaves out Mona, Monito and Desecheo
HILLS, FLAT = ("72073", "72107", "72019"), ("72033",)   # Jayuya, Orocovis, Barranquitas; Cataño
PR_STEEP30 = (15.0, 55.0)
FLAT_STEEP15_MAX = 5.0
COVER = (0.97, 1.10)            # the cells with a slope over the barrios' land area (Census): inland water and the coast's edge make it differ a little


def deg_m(lat):
    """Metres per degree of longitude and of latitude at a latitude (WGS 84, series to the second order)."""
    p = math.radians(lat)
    return 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p), 111132.954 - 559.822 * math.cos(2 * p) + 1.175 * math.cos(4 * p)


def horn(z, dx, dy):
    """Slope in percent of the inner cells of a padded height array z (one cell of padding on every side), by Horn's method; NaN where a neighbour has no height."""
    import numpy as np
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    gx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    gy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    return np.hypot(gx, gy) * 100


def blocks(s):
    """Per 6 x 6 block of a slope array (sides a multiple of 6): cells with a slope, cells steeper than each threshold, and the sum of their slopes."""
    import numpy as np
    H, W = s.shape
    r = s.reshape(H // BLK, BLK, W // BLK, BLK)
    ok = np.isfinite(r)
    n = ok.sum(axis=(1, 3))
    tot = np.where(ok, r, 0).sum(axis=(1, 3))
    steep = [(ok & (r > t)).sum(axis=(1, 3)) for t in STEEP]
    return n, steep, tot


def windows(B):
    """The 0.1-degree windows of BOX that touch a barrio: (west, north)."""
    from shapely.geometry import box
    out = []
    nx, ny = round((BOX[2] - BOX[0]) / WIN), round((BOX[3] - BOX[1]) / WIN)
    for j in range(ny):
        for i in range(nx):
            w, n = round(BOX[0] + i * WIN, 6), round(BOX[3] - j * WIN, 6)
            if len(B.tree.query(box(w, n - WIN, w + WIN, n), predicate="intersects")):
                out.append((w, n))
    return out


def read_window(dem, w, n):
    """Heights of the window whose north-west corner is (w, n), with one cell of padding on every side, from the one-degree tile that holds it (its 6-cell margins
    hold the padding); NaN for no data. None when no tile covers the window."""
    import numpy as np
    cell = f"n{math.floor(n - 1e-9) + 1}w{math.ceil(-w - 1e-9):03d}"
    cog = dem.cogs.get(cell)
    if cog is None:
        return None
    a, _, c, _, e, f = cog.level_transform(0)
    col0, row0 = round((w - c) / a), round((n - f) / e)
    side = round(WIN / CELL)
    z = cog.read_window(col0 - 1, row0 - 1, side + 2, side + 2, 0).astype("float64")
    z[z <= NODATA] = np.nan
    return z


def owners(B, lon, lat):
    """The barrio index of each block centre (-1 when none within NEAR_DEG): inside an outline first (the lowest index on a shared edge), then the nearest."""
    import numpy as np
    import buildings
    return buildings.place(B, lon, lat) if len(lon) else np.zeros(0, dtype="int32")


def grids(B, dem, version):
    """The block grids over BOX (about 60 m): cells with a slope, steeper than 15% and 30%, the sum of their slopes, their area (km2) and the barrio of each block
    (-1: none, the sea). Computed once per version of the elevation tiles and kept in cache/slope/ (a few tens of MB, never published)."""
    import numpy as np
    f = CACHE / "slope" / f"blocks_{version}.npz"
    if f.exists():
        z = np.load(f)
        return {k: z[k] for k in z.files}
    side = round(WIN / CELL) // BLK                       # 180 blocks a side
    gw, gh = round((BOX[2] - BOX[0]) / WIN) * side, round((BOX[3] - BOX[1]) / WIN) * side
    G = {"cnt": np.zeros((gh, gw), "uint16"), "s15": np.zeros((gh, gw), "uint16"), "s30": np.zeros((gh, gw), "uint16"),
         "tot": np.zeros((gh, gw), "float32"), "km2": np.zeros((gh, gw), "float32"), "owner": np.full((gh, gw), -1, "int16")}
    wins = windows(B)
    log(f"  {len(wins)} windows of 0.1 degree over Puerto Rico")
    for k, (w, n) in enumerate(wins):
        z = read_window(dem, w, n)
        if z is None:
            continue
        mx, my = deg_m(n - WIN / 2)
        cnt, (s15, s30), tot = blocks(horn(z, CELL * mx, CELL * my))
        gi, gj = round((BOX[3] - n) / WIN) * side, round((w - BOX[0]) / WIN) * side
        sl = (slice(gi, gi + side), slice(gj, gj + side))
        G["cnt"][sl], G["s15"][sl], G["s30"][sl], G["tot"][sl] = cnt, s15, s30, tot
        G["km2"][sl] = cnt * (CELL * mx) * (CELL * my) / 1e6
        rr, cc = np.nonzero(cnt > 0)
        if len(rr):
            G["owner"][gi + rr, gj + cc] = owners(B, w + (cc + 0.5) * BLK * CELL, n - (rr + 0.5) * BLK * CELL)
        if k % 25 == 0:
            log(f"  window {k + 1} of {len(wins)}")
    f.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f, **G)
    return G


def compute(offline=False):
    import numpy as np
    import conditions
    B = conditions.Barrios()
    nb = len(B.ids)
    tiles = climb.dem_tiles(offline)
    version = max(u.rsplit("_", 1)[-1][:8] for u in tiles.values())          # 20260722
    G = grids(B, climb.Dem(tiles, offline=offline), version)
    land = (G["owner"] >= 0) & (G["cnt"] > 0)                                # blocks in a barrio: the sea and the cays outside the outlines are left out
    o = G["owner"][land].astype(np.int64)
    acc = np.zeros((nb, 5))                                                   # per barrio: cells, steeper than 15%, steeper than 30%, sum of slopes, km2
    np.add.at(acc, o, np.stack([G["cnt"][land], G["s15"][land], G["s30"][land], G["tot"][land], G["km2"][land]], axis=1).astype("float64"))
    mean = np.where(land, G["tot"] / np.maximum(G["cnt"], 1), np.nan).astype("float32")
    land_km2 = sum(B.unit[b]["km2"] for b in B.ids)
    covered = acc[:, 4].sum() / land_km2

    def row(v):
        if not v[0]:
            return None
        return {"s15": round(v[1] / v[0] * 100, 1), "s30": round(v[2] / v[0] * 100, 1), "mean": round(v[3] / v[0], 1)}
    brow = [row(acc[i]) for i in range(nb)]
    mid = [B.mids.index(B.ids[i][:5]) for i in range(nb)]
    macc = np.zeros((len(B.mids), 5))
    np.add.at(macc, mid, acc)
    mrows = {m: row(macc[j]) for j, m in enumerate(B.mids)}
    isl = row(acc.sum(axis=0))
    name = lambda m: B.names[B.mids.index(m)]

    bad = []
    if not PR_STEEP30[0] <= isl["s30"] <= PR_STEEP30[1]:
        bad.append(f"{isl['s30']}% of Puerto Rico steeper than 30% (expected {PR_STEEP30[0]} to {PR_STEEP30[1]})")
    for m in HILLS:
        if not mrows[m]["s30"] > isl["s30"]:
            bad.append(f"{name(m)} ({mrows[m]['s30']}% steeper than 30%) is not steeper than Puerto Rico ({isl['s30']}%)")
    for m in FLAT:
        if not mrows[m]["s15"] < FLAT_STEEP15_MAX:
            bad.append(f"{name(m)} has {mrows[m]['s15']}% of its land steeper than 15% (expected under {FLAT_STEEP15_MAX}%)")
    if not COVER[0] <= covered <= COVER[1]:
        bad.append(f"the cells with a slope in the barrios cover {covered:.1%} of the barrios' land area (expected {COVER[0]:.0%} to {COVER[1]:.0%})")
    log(f"  Puerto Rico: mean slope {isl['mean']}%, {isl['s15']}% of the land steeper than 15%, {isl['s30']}% steeper than 30%; "
        + ", ".join(f"{name(m)} {mrows[m]['s15']}/{mrows[m]['s30']}%" for m in HILLS + FLAT) + f"; cover {covered:.2%} of the land")
    if bad:
        raise SystemExit("slope: the figures fail their checks:\n  " + "\n  ".join(bad))

    Y_ = version[:4]
    G = "Environment · Slope of the land (USGS 3DEP)"
    REF = (f"USGS 3D Elevation Program (3DEP), 1/3 arc-second (about 10 m) seamless elevation model, tiles of {version[:4]}-{version[4:6]}-{version[6:]}; slope of "
           "every 10 m cell by Horn's method, counted by barrio; municipios and Puerto Rico pool their barrios")
    WHAT = ("Slope is the rise over the run, as a percent: 10% climbs 10 m in 100 m, and 100% is 45 degrees. It is computed for every 10 m cell of the USGS "
            "elevation model (bare ground, not buildings or trees) from its eight neighbours (Horn's method). A cell counts in the barrio that holds the centre of "
            "its 60 m block; municipios and Puerto Rico pool their barrios. Coastal cells next to the sea have no slope.")
    LIM = {"15": "15% is where building and farming begin to need terraces or special design.",
           "30": "30% is where ground is generally treated as too steep to build on without engineering, and where landslide susceptibility rises."}

    def var(key, label, unit, d, typ, definition, field):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["usgs_3dep_13", "census_tiger"], "ref": REF,
                "definition": definition, "family": "slope", "counted": False, "barrioFile": OUT_BARRIO.name,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("slope_steep15_pct", "Land steeper than 15% (%)", "%", 1, "rate", "The share of the area's land steeper than 15%. " + LIM["15"] + " " + WHAT, "s15"),
          var("slope_steep30_pct", "Land steeper than 30% (%)", "%", 1, "rate", "The share of the area's land steeper than 30%. " + LIM["30"] + " " + WHAT, "s30"),
          var("slope_mean", "Mean slope of the land (%)", "%", 1, "level", "The mean slope of the area's 10 m cells. " + WHAT, "mean")]
    keys = {"slope_steep15_pct": "s15", "slope_steep30_pct": "s30", "slope_mean": "mean"}
    none = [B.ids[i] for i in range(nb) if brow[i] is None]
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, **({"noValueWhy": [{"why": "No land in the elevation model", "ids": none}]} if none else {}),
                        "years": {Y_: [None if r is None else r[f] for r in brow]}} for k, f in keys.items()],
              "notes": {"areas": nb, "source": "slope.py; the municipio values and the method are in slope_series.json"}}
    notes = {"tiles": sorted(tiles), "version": version, "cells_with_slope": int(acc[:, 0].sum()), "km2_with_slope": round(float(acc[:, 4].sum()), 1), "cover_of_land_area": round(covered, 4),
             "thresholds_pct": list(STEEP), "checks": {"pr_steep30_pct": isl["s30"], **{f"steep30_{m}": mrows[m]["s30"] for m in HILLS}, **{f"steep15_{m}": mrows[m]["s15"] for m in FLAT}},
             "no_value": {"barrios": none, "municipios": [f for f in B.mids if mrows[f] is None]}}
    SOURCES = {"usgs_3dep_13": climb.SOURCES["usgs_3dep_13"], "census_tiger": {"name": "US Census Bureau — 2020 barrio outlines (TIGER/Line)",
               "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html", "license": "US Government work (no US copyright)",
               "note": "Barrio outlines from the observatory's crosswalk."}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    surface = surface_png(mean, version, REF)
    return series, barrio, surface


def surface_png(mean, version, ref):
    """The blocks' mean slope as an indexed Web Mercator PNG on the fixed scale (one block per pixel), with its corners and scale."""
    import numpy as np
    gh, gw = mean.shape
    step = BLK * CELL
    lons = BOX[0] + (np.arange(gw) + 0.5) * step
    lats = BOX[3] - (np.arange(gh) + 0.5) * step
    keep_c = lons >= SURFACE_MIN_LON
    have = np.isfinite(mean) & keep_c[None, :]
    rows_, cols_ = np.nonzero(have)
    pad = 0.01
    w, e = float(lons[cols_].min()) - pad, float(lons[cols_].max()) + pad
    s, n = float(lats[rows_].min()) - pad, float(lats[rows_].max()) + pad
    mercY = lambda la: math.log(math.tan(math.pi / 4 + math.radians(la) / 2))
    W = int(math.ceil((e - w) / step))
    if W > surface_image.MAX_PX:
        raise SystemExit(f"slope: the image would be {W} px wide (more than {surface_image.MAX_PX})")
    px = math.radians(e - w) / W                                         # a pixel's width in Web Mercator units (radians of longitude)
    H = int(math.ceil((mercY(n) - mercY(s)) / px))
    # each pixel centre, back into the block grid; the block under it gives its value (nearest: nothing is invented between blocks)
    pc_lon = w + (np.arange(W) + 0.5) * (e - w) / W
    pc_lat = np.degrees(2 * np.arctan(np.exp(mercY(n) - (np.arange(H) + 0.5) * px)) - math.pi / 2)
    ci = np.floor((pc_lon - BOX[0]) / step).astype(np.int64)
    ri = np.floor((BOX[3] - pc_lat) / step).astype(np.int64)
    okc, okr = (ci >= 0) & (ci < gw) & keep_c[np.clip(ci, 0, gw - 1)], (ri >= 0) & (ri < gh)
    v = np.full((H, W), np.nan, dtype="float32")
    sub = mean[np.clip(ri, 0, gh - 1)][:, np.clip(ci, 0, gw - 1)]
    v[np.ix_(okr, okc)] = sub[np.ix_(okr, okc)]
    t = np.clip((v - SCALE[0]) / (SCALE[1] - SCALE[0]), 0, 1)
    idx = np.where(np.isfinite(v), 1 + np.rint(t * (surface_image.STEPS - 1)), 0).astype(np.uint8)
    png = surface_image.png_indexed(idx, surface_image.ramp(surface_image.STEPS, STOPS))
    s_edge = math.degrees(2 * math.atan(math.exp(mercY(n) - H * px)) - math.pi / 2)
    lat_mid = (s + n) / 2
    meta = {"what": "Slope of the ground, mean of the 10 m cells of each block of about 60 m (USGS 3DEP)", "image": OUT_SURFACE_PNG.name, "unit": "%",
            "version": version, "bounds": [round(w, 6), round(s_edge, 6), round(e, 6), round(n, 6)], "size": [W, H],
            "pixel_m": round((e - w) / W * deg_m(lat_mid)[0], 1),
            "scale": {"low": SCALE[0], "centre": (SCALE[0] + SCALE[1]) / 2, "high": SCALE[1], "steps": surface_image.STEPS, "stops": STOPS},
            "cells_drawn": int(np.isfinite(v).sum()), "left_out_west_of": SURFACE_MIN_LON, "source": ref}
    log(f"  surface: {W} x {H} px of {meta['pixel_m']} m, {len(png) / 1024:.0f} KB")
    return {"png": png, "meta": meta}


def build(check=False):
    series, barrio, surface = compute(offline=check)
    status = 0
    files = ((OUT_SERIES, series), (OUT_BARRIO, barrio), (OUT_SURFACE, surface["meta"]))
    for path, d in files:
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python slope.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:.1f} KB")
    if check:
        same = OUT_SURFACE_PNG.exists() and OUT_SURFACE_PNG.read_bytes() == surface["png"]
        print(f"{OUT_SURFACE_PNG.name} {'matches the cache' if same else 'is not what the cache gives: run python slope.py'}")
        status = status or (0 if same else 1)
    else:
        OUT_SURFACE_PNG.write_bytes(surface["png"])
        log(f"wrote {OUT_SURFACE_PNG.name}: {len(surface['png']) / 1024:.0f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--check" in sys.argv))
