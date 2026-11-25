"""One grid of equal hexagons for the PR Data Observatory: residents, housing units, buildings, residents in the flood area, surface heat, greenness and slope,
by hexagon of 1 km². HANDOFF decision 107, step 9, parts 1 and 2 (row derived-hex-grid); docs/hexgrid.md.

    python hexgrid.py           # build site/data/hex_grid.geojson from the census blocks, the building footprints, flood.geojson and the caches of heat.py,
                                # vegetation.py and slope.py (no network; run those first when a new summer or elevation release arrives)
    python hexgrid.py --check   # rebuild and exit 1 when the published file is not what it gives (nothing written)

Why these hexagons and not H3. The grid is the one the map already uses to count places (site/js/core/hexbin.js): a Lambert azimuthal equal-area projection
centered on Puerto Rico (18.2 N, 66.45 W) with pointy-topped hexagons laid on the plane, so every cell holds the same ground area (to about 0.3%). H3 cells,
which the FCC's broadband hexagons use, differ in area across the island. With cells of exactly 1 km², a count per cell is also a density per km². This module
ports hexbin.js's project, cell and corner functions; a test checks that both give the same cell ids. Cell ids are "q,r" (axial coordinates).

What each cell holds (only cells with at least one resident, housing unit or building):
  p    residents, 2020 Census: each census block is counted whole in the cell of its internal point, so the cells add up to Puerto Rico's 3,285,874 exactly.
       A block larger than a cell puts all its residents in one cell: rural cells read lumpy (a calculated count, not an estimate spread over buildings).
  h    housing units, 2020 Census, the same way
  b    buildings: the footprints of the observatory's building layer (Overture, buildings.py), each counted in the cell of its point
  bf   footprint area, % of the cell's 1 km²: how built up it is
  pf   residents in FEMA's 1% annual chance flood area (the Special Flood Hazard Area of flood.geojson), as % of the cell's residents; empty where p is 0.
       A block is in the area when its internal point is (exposure.py's rule).
  t    surface temperature of summer mornings, °C: the median of the 60 m cells of heat.py's composite whose center is in the hexagon (Landsat, the last three
       summers; land surface, not air)
  g    greenness (NDVI): the median of the 60 m cells of vegetation.py's composite (Sentinel-2, the same summers)
  s    slope of the ground, %: the mean of the 10 m cells of slope.py's blocks of about 60 m whose center is in the hexagon (USGS 3DEP)
       Each of t, g and s is empty when less than a tenth of the hexagon has a value (the sea, a coast); a hexagon with only land and none of the counts is
       kept for them, so the three cover the whole island.
Nothing about a single home is published: census blocks are public counts, and a building is counted, never drawn or named.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

MIN_CELLS60 = 28        # a hexagon of 1 km² holds about 278 cells of 60 m: t and g need a tenth of them with a value
MIN_CELLS10 = 1000      # and about 10,000 cells of 10 m: s needs a tenth of them

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT = DATA / "hex_grid.geojson"
KM2 = 1.0
R = 6371.0088
LAT0, LON0 = math.radians(18.2), math.radians(-66.45)
S0, C0 = math.sin(LAT0), math.cos(LAT0)


def size(km2=KM2):
    return math.sqrt(2 * km2 / (3 * math.sqrt(3)))


def project(lat, lng):
    """km east and north of the center (numpy arrays or floats), as hexbin.js project()."""
    f, lam = np.radians(lat), np.radians(lng) - LON0
    k = np.sqrt(2 / (1 + S0 * np.sin(f) + C0 * np.cos(f) * np.cos(lam)))
    return R * k * np.cos(f) * np.sin(lam), R * k * (C0 * np.sin(f) - S0 * np.cos(f) * np.cos(lam))


def unproject(x, y):
    rho = math.hypot(x, y)
    if not rho:
        return math.degrees(LAT0), math.degrees(LON0)
    c = 2 * math.asin(rho / (2 * R))
    sc, cc = math.sin(c), math.cos(c)
    return math.degrees(math.asin(cc * S0 + y * sc * C0 / rho)), math.degrees(LON0 + math.atan2(x * sc, rho * C0 * cc - y * S0 * sc))


def cell_at(x, y, s):
    """Axial (q, r) of the hexagon that holds each point, as hexbin.js cellAt() (cube rounding)."""
    q = (math.sqrt(3) / 3 * x - y / 3) / s
    r = (2 / 3 * y) / s
    t = -q - r
    rq, rr, rt = np.round(q), np.round(r), np.round(t)
    dq, dr, dt = np.abs(rq - q), np.abs(rr - r), np.abs(rt - t)
    a = (dq > dr) & (dq > dt)
    b = ~a & (dr > dt)
    rq = np.where(a, -rr - rt, rq)
    rr = np.where(b, -rq - rt, rr)
    return rq.astype(np.int64) + 0, rr.astype(np.int64) + 0


def corners(q, r, s):
    cx, cy = s * math.sqrt(3) * (q + r / 2), s * 1.5 * r
    out = []
    for i in range(6):
        a = math.radians(60 * i - 30)
        la, lo = unproject(cx + s * math.cos(a), cy + s * math.sin(a))
        out.append([round(lo, 5), round(la, 5)])
    return out + [out[0]]


def ids_of(lat, lng, s):
    x, y = project(np.asarray(lat, float), np.asarray(lng, float))
    q, r = cell_at(x, y, s)
    return q, r


def by_cell(q, r, v, w=None):
    """{(q, r): (median of v, count)}, or with weights w, {(q, r): (sum of v / sum of w, sum of w)}: the per-hexagon summary of a surface."""
    ok = np.isfinite(v)
    q, r, v = q[ok], r[ok], v[ok]
    w = None if w is None else w[ok]
    key = (q.astype(np.int64) + 50000) * 100000 + (r.astype(np.int64) + 50000)   # q and r are within ±50,000 (cells of 1 km)
    order = np.lexsort((v, key)) if w is None else np.argsort(key, kind="stable")
    key, v = key[order], v[order]
    w = None if w is None else w[order]
    cut = np.flatnonzero(np.diff(key)) + 1
    out = {}
    for ks, vs, ws in zip(np.split(key, cut), np.split(v, cut), np.split(w, cut) if w is not None else [None] * (len(cut) + 1)):
        if not len(ks):
            continue
        k = (int(ks[0] // 100000) - 50000, int(ks[0] % 100000) - 50000)
        out[k] = (float(np.median(vs)), len(vs)) if ws is None else (float(vs.sum() / ws.sum()), float(ws.sum()))
    return out


def surfaces(s):
    """The three surfaces by hexagon: {"t": {(q, r): °C}, "g": {(q, r): NDVI}, "s": {(q, r): % slope}} and their notes."""
    import climb
    import conditions
    import heat
    import raster
    import slope
    import vegetation
    out, notes = {}, {}
    for key, mod, nd in (("t", heat, 1), ("g", vegetation, 2)):
        X, Y, v = heat.cells(mod)
        lon, lat = raster.transform_points(X, Y, heat.EPSG, 4326)
        q, r = ids_of(np.asarray(lat), np.asarray(lon), s)
        out[key] = {k: round(m, nd) for k, (m, n) in by_cell(q, r, v.astype(np.float64)).items() if n >= MIN_CELLS60}
    tiles = climb.dem_tiles(True)
    version = max(u.rsplit("_", 1)[-1][:8] for u in tiles.values())
    G = slope.grids(conditions.Barrios(), climb.Dem(tiles, offline=True), version)
    ii, jj = np.nonzero((G["owner"] >= 0) & (G["cnt"] > 0))
    side = slope.BLK * slope.CELL
    q, r = ids_of(slope.BOX[3] - (ii + 0.5) * side, slope.BOX[0] + (jj + 0.5) * side, s)
    out["s"] = {k: round(m, 1) for k, (m, n) in by_cell(q, r, G["tot"][ii, jj].astype(np.float64), G["cnt"][ii, jj].astype(np.float64)).items() if n >= MIN_CELLS10}
    win = heat.summers()
    notes = {"summers": f"{win[0]}-{win[-1]}", "elevation_version": version}
    return out, notes


def assemble():
    import buildings
    import exposure
    import network
    table = network.load_block_table(ROOT / "cache" / "network", False)
    rows = table["rows"]
    pop = np.array([r[1] for r in rows], dtype=np.int64)
    hu = np.array([r[2] for r in rows], dtype=np.int64)
    lon = np.array([r[4] for r in rows], dtype=float)
    lat = np.array([r[5] for r in rows], dtype=float)
    s = size()
    bq, br = ids_of(lat, lon, s)
    sfha, _ = exposure.flood_polygons(exposure.load_json(DATA / "flood.geojson"))
    wet = exposure.points_in_polygons(sfha, lon, lat)
    release, B = buildings.load(offline=True)
    gq, gr = ids_of(B["lat"], B["lon"], s)
    cells = {}

    def cell(q, r):
        k = (int(q), int(r))
        c = cells.get(k)
        if c is None:
            c = cells[k] = [0, 0, 0, 0.0, 0]   # residents, housing units, buildings, footprint m², residents in the flood area
        return c
    for q, r, p, h, w in zip(bq, br, pop, hu, wet):
        if p or h:
            c = cell(q, r)
            c[0] += int(p)
            c[1] += int(h)
            c[4] += int(p) if w else 0
    for q, r, a in zip(gq, gr, B["area"]):
        c = cell(q, r)
        c[2] += 1
        c[3] += float(a)
    surf, snotes = surfaces(s)
    for k in set().union(*surf.values()):
        cell(*k)                               # a hexagon of land with no one and no building still has heat, greenness and slope
    feats = []
    for (q, r), (p, h, b, fa, pw) in sorted(cells.items()):
        props = {"id": f"{q},{r}", "p": p, "h": h, "b": b, "bf": round(min(100.0, fa / 1e4), 1), "pf": round(pw / p * 100, 1) if p else None,
                 "t": surf["t"].get((q, r)), "g": surf["g"].get((q, r)), "s": surf["s"].get((q, r))}
        feats.append({"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [corners(q, r, s)]}})
    tot = {"residents": int(pop.sum()), "housing_units": int(hu.sum()), "buildings": int(len(B["area"]))}
    got = {"residents": sum(f["properties"]["p"] for f in feats), "housing_units": sum(f["properties"]["h"] for f in feats), "buildings": sum(f["properties"]["b"] for f in feats)}
    if got != tot:
        raise SystemExit(f"hexgrid: the cells do not add up to the inputs: {got} against {tot}")
    notes = {"km2": KM2, "projection": "Lambert azimuthal equal-area centered on 18.2 N, 66.45 W (site/js/core/hexbin.js)", "cells": len(feats),
             "cells_with_residents": sum(1 for f in feats if f["properties"]["p"]), "totals": tot, "buildings_release": release,
             "residents_in_flood_area": int(pop[wet].sum()), "surfaces": {**snotes, "cells_with": {k: sum(1 for f in feats if f["properties"][k] is not None) for k in "tgs"}}}
    return {"type": "FeatureCollection", "as_of": date.today().isoformat(), "notes": notes, "features": feats}


def build(check=False):
    doc = assemble()
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        same = old is not None and {**old, "as_of": None} == {**json.loads(text), "as_of": None}
        print(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    n = doc["notes"]
    print(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.0f} KB): {n['cells']:,} cells, {n['cells_with_residents']:,} with residents; totals {n['totals']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--check" in sys.argv))
