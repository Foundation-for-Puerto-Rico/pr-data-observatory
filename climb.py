"""The climb on the walk to a transit stop, for the PR Data Observatory, by barrio and municipio: for the residents who live within a 400 m walk of a stop with
a current timetable (the published figure walk_cur of the exposure files), how much their walk climbs and whether it has a stretch steeper than a ramp may be.
A flat 400 m and a 400 m up a hill in Barranquitas are not the same walk, especially for older adults. Step 4 of the terrain and climate plan
(docs/terrain-climate-proposal-2026-11.md, HANDOFF decision 80; method in docs/climb.md).

    python climb.py             # build site/data/climb_series.json and site/data/climb_barrio.json (reads the elevation tiles missing from cache/dem/)
    python climb.py --check     # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)
The nightly transit refresh (refresh_network.py) runs it after the exposure files, since the stops with a current timetable change; it writes only on a change.

How it is made (docs/climb.md):
  - The walkers: each 2020 census block whose point is within a 400 m walk along mapped roads of a stop with a current timetable, by the rule of access.py and
    exposure.py (the same blocks as walk_cur), on the date of the published exposure files (their as_of), so the residents here are those residents.
  - The walk: the shortest walk along mapped roads from the block's point to its nearest current stop (walknet.nearest_paths). The climb is read along the
    roads only, from the point of the road nearest the block's point to the point nearest the stop: the block's point is a geometric centre, not a door, and the
    straight line from it to the road can cross ground nobody walks. A block whose point or stop is on no walkable road, which access.py measures in a straight
    line, walks the straight line here too.
  - The ground: USGS 3D Elevation Program, 1/3 arc-second (about 10 m) seamless elevation, the newest version of each one-degree tile over Puerto Rico, read with
    raster.py. The height is read every 10 m along the walk, interpolated between the four nearest cells.
  - Round-trip climb: the sum of the rises and the falls along the walk, which is the climb of going to the stop and back. The same in either direction.
  - Steep stretch: a 30 m stretch of the walk whose rise or fall is more than 1 in 12 (8.33%), the steepest running slope the 2010 ADA Standards allow for a
    ramp (405.2); a walk with such a stretch counts as steep.
  - Areas: a block counts in the barrio the crosswalk gives it (geo.block_barrios) and in its municipio; Puerto Rico pools the blocks. The median climb is
    weighted by residents.
  - Checks that stop the build: the residents with a walk add up to the published walk_cur residents of Puerto Rico; Puerto Rico's median climb between 0 and
    30 m; the Cordillera (Barranquitas, Jayuya, Orocovis) climbs more than Puerto Rico and the coastal plain (Cataño, Toa Baja) less.
No personal data: the files hold counts of residents, shares and medians.
"""

import json
import math
import sys
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import raster

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = hs.OUT
OUT_SERIES = OUT / "climb_series.json"
OUT_BARRIO = OUT / "climb_barrio.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
log = hs.log

TNM = "https://tnmaccess.nationalmap.gov/api/v1/products"
DEM_DATASET = "National Elevation Dataset (NED) 1/3 arc-second"
DEM_BOX = "-67.95,17.85,-65.2,18.55"
STEP_M = 10.0                 # the height is read every 10 m along a walk
WINDOW_M = 30.0               # a stretch for the grade
STEEP = 1 / 12                # 8.33%: ADA 2010 Standards 405.2, the steepest running slope of a ramp
MIN_CELLS = 1
CHECK_MEDIAN = (0.0, 30.0)
HILLS, FLAT = ("72021", "72073", "72107"), ("72033", "72137")   # Barranquitas, Jayuya, Orocovis; Cataño, Toa Baja (Aibonito has no current stop within a walk)
NO_WALK = "No residents within a 400 m walk of a current stop"

SOURCES = {
    "usgs_3dep_13": {
        "name": "USGS — 3D Elevation Program (3DEP), 1/3 arc-second (about 10 m) seamless digital elevation model",
        "url": "https://www.usgs.gov/3d-elevation-program",
        "license": "US Government work, public domain (cite USGS)",
        "note": "The newest version of each one-degree tile over Puerto Rico, read by HTTP range requests with raster.py. Heights of the ground, not of bridges or buildings."},
    "census_tiger": {"name": "US Census Bureau — 2020 census blocks and county subdivisions", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Barrio outlines, and the 2020 residents of each block and barrio."},
}


# ── Elevation ────────────────────────────────────────────────────────────────

def dem_tiles(offline=False):
    """{tile name: url} of the newest 3DEP 1/3 arc-second tile of each one-degree cell over Puerto Rico (from USGS's catalogue, kept in cache/dem/tiles.json)."""
    p = CACHE / "dem" / "tiles.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit("climb --check: cache/dem/tiles.json is missing (python climb.py makes it)")
    r = requests.get(TNM, headers=UA, timeout=120, params={"datasets": DEM_DATASET, "bbox": DEM_BOX, "max": 100, "outputFormat": "JSON"})
    r.raise_for_status()
    newest = {}
    for it in r.json()["items"]:
        u = it.get("downloadURL", "")
        if not u.endswith(".tif"):
            continue
        name = u.rsplit("/", 1)[-1]                      # USGS_13_n19w067_20260722.tif
        cell = name.split("_")[2]
        if cell not in newest or name > newest[cell].rsplit("/", 1)[-1]:
            newest[cell] = u
    if len(newest) < 3:
        raise SystemExit(f"climb: USGS lists only {len(newest)} elevation tiles over Puerto Rico")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(newest, indent=1, sort_keys=True), encoding="utf-8")
    return newest


class Dem:
    """Heights (m) at points, bilinear between the four nearest cells of the tile that holds each point."""

    def __init__(self, tiles, session=None, offline=False):
        self.cogs = {cell: raster.COG(u, cache=CACHE / "dem" / "tiles", session=session, offline=offline, workers=16) for cell, u in tiles.items()}

    @staticmethod
    def cell_of(lon, lat):
        import numpy as np
        return np.char.add(np.char.add("n", (np.floor(lat).astype(int) + 1).astype(str)), np.char.add("w", np.char.zfill((np.ceil(-lon)).astype(int).astype(str), 3)))

    def heights(self, lon, lat):
        import numpy as np
        lon, lat = np.asarray(lon, float), np.asarray(lat, float)
        out = np.full(len(lon), np.nan)
        cells = self.cell_of(lon, lat)
        for cell in np.unique(cells):
            k = np.flatnonzero(cells == cell)
            cog = self.cogs.get(str(cell))
            if cog is None:
                continue
            a, _, c, _, e, f = cog.level_transform(0)
            fx, fy = (lon[k] - c) / a - 0.5, (lat[k] - f) / e - 0.5        # pixel centres
            x0, y0 = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
            tx, ty = fx - x0, fy - y0
            vals = {}
            for dx in (0, 1):
                for dy in (0, 1):
                    v, inside = cog.values_at(x0 + dx, y0 + dy, 0)
                    v = v.astype(float)
                    v[~inside | (v <= -1000)] = np.nan
                    vals[dx, dy] = v
            out[k] = (vals[0, 0] * (1 - tx) * (1 - ty) + vals[1, 0] * tx * (1 - ty) + vals[0, 1] * (1 - tx) * ty + vals[1, 1] * tx * ty)
        return out


# ── Walks ────────────────────────────────────────────────────────────────────

def samples(pieces):
    """Points every STEP_M along each piece of a walk (both ends kept), in local metres: [(n, 2) array per piece]."""
    import numpy as np
    import shapely
    out = []
    for xy in pieces:
        if len(xy) < 2:
            continue
        line = shapely.linestrings(xy)
        L = float(shapely.length(line))
        if L <= 0:
            continue
        d = np.append(np.arange(0.0, L, STEP_M), L)
        pts = shapely.line_interpolate_point(line, d)
        out.append(np.column_stack([shapely.get_x(pts), shapely.get_y(pts)]))
    return out


def walk_measures(z_pieces, step=STEP_M, window=WINDOW_M):
    """(round-trip climb in m, steepest grade over a window) of one walk from its heights per piece (each sampled every `step` m, the last step shorter).
    Pieces join end to start, so the climb is the sum over pieces; a piece shorter than the window gives its own grade."""
    import numpy as np
    climb, steep = 0.0, 0.0
    for z in z_pieces:
        z = np.asarray(z, float)
        if len(z) < 2 or np.isnan(z).any():
            continue
        climb += float(np.abs(np.diff(z)).sum())
        k = max(1, int(round(window / step)))
        if len(z) > k:
            steep = max(steep, float(np.abs(z[k:] - z[:-k]).max() / (k * step)))
        elif len(z) >= 2:
            span = (len(z) - 1) * step
            if span >= step:
                steep = max(steep, float(abs(z[-1] - z[0]) / span))
    return climb, steep


def weighted_median(v, w):
    import numpy as np
    v, w = np.asarray(v, float), np.asarray(w, float)
    if not len(v) or w.sum() <= 0:
        return None
    o = np.argsort(v, kind="stable")
    c = np.cumsum(w[o])
    return float(v[o][np.searchsorted(c, c[-1] / 2)])


def compute(offline=False):
    import numpy as np
    import access
    import exposure
    import geo
    import network
    import walknet
    import conditions
    data = OUT
    expo = json.loads((data / "exposure_municipio.json").read_text(encoding="utf-8"))
    as_of = date.fromisoformat(expo["as_of"])
    table = network.load_block_table(CACHE / "network", False)
    blocks = exposure.Blocks(table)
    barrio_of = geo.block_barrios(table, False, CACHE / "geo")
    stops = json.loads((data / "transport.json").read_text(encoding="utf-8"))
    operators = json.loads((data / "operators.json").read_text(encoding="utf-8"))["operators"]
    net = walknet.load(data / "roads.bin")
    pts = [{"lat": float(a), "lng": float(b)} for a, b in zip(blocks.lat4, blocks.lon4)]
    log(f"  {len(pts):,} blocks; the walking rule of access.py on {as_of}")
    res = access.compute(pts, stops, operators, as_of, net=net)
    walk = res.tw_m <= access.NEAR_M
    walkers = np.flatnonzero(walk & (blocks.pop > 0))
    # the current stops, in access.py's order
    cur = access.current_operators(operators, as_of)
    any_stops = [s for s in stops if s.get("kind") in access.ANY_KINDS]
    cur_stops = [s for s in any_stops if s.get("source") in access.SCHEDULED_SOURCES and s.get("operator") in cur]
    log(f"  {len(walkers):,} blocks with residents within a 400 m walk of one of {len(cur_stops):,} current stops; tracing the walks")
    places = [pts[i] for i in walkers]
    paths = walknet.nearest_paths(net, cur_stops, places, access.NEAR_M + 1)
    sx, sy = walknet.to_xy([s["lng"] for s in cur_stops], [s["lat"] for s in cur_stops])
    px, py = walknet.to_xy([p["lng"] for p in places], [p["lat"] for p in places])
    straight = 0
    walk_pieces = []
    for k, b in enumerate(paths):
        if b is None or b[1] > access.NEAR_M + 1:
            # access.py measured this block in a straight line (its point or its stop is on no walkable road): walk the straight line to the nearest current stop
            d2 = (sx - px[k]) ** 2 + (sy - py[k]) ** 2
            j = int(np.argmin(d2))
            walk_pieces.append([np.array([[px[k], py[k]], [sx[j], sy[j]]])])
            straight += 1
        else:
            walk_pieces.append(b[2][1:-1])                               # along the roads: the connectors from the block's point and to the stop are left out
    sampled = [samples(p) for p in walk_pieces]
    flat = np.concatenate([np.concatenate(s) for s in sampled if s]) if sampled else np.zeros((0, 2))
    lon = flat[:, 0] / (walknet.M_PER_DEG * walknet.COS0) + walknet.LON0
    lat = flat[:, 1] / walknet.M_PER_DEG + walknet.LAT0
    log(f"  {len(flat):,} points along the walks ({straight:,} walks in a straight line); reading the ground's height (USGS 3DEP)")
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=32))
    z = Dem(dem_tiles(offline), session=session, offline=offline).heights(lon, lat)
    if np.isnan(z).mean() > 0.01:
        raise SystemExit(f"climb: {np.isnan(z).mean():.1%} of the points along the walks have no height")
    climb = np.zeros(len(walkers)); steep = np.zeros(len(walkers))
    at = 0
    for k, s in enumerate(sampled):
        zp = []
        for piece in s:
            zp.append(z[at:at + len(piece)]); at += len(piece)
        climb[k], steep[k] = walk_measures(zp)
    is_steep = steep > STEEP
    pop = blocks.pop[walkers].astype(float)
    # areas
    B = conditions.Barrios()
    nb = len(B.ids)
    bidx = np.array([B.idx.get(barrio_of[i], -1) for i in walkers])
    midx = np.array([blocks.ids[i][:5] for i in walkers])

    def stats(sel):
        p = pop[sel]
        if p.sum() <= 0:
            return None
        return {"med": round(weighted_median(climb[sel], p), 1), "steep_pct": round(float(p[is_steep[sel]].sum() / p.sum() * 100), 1),
                "steep": int(p[is_steep[sel]].sum()), "walkers": int(p.sum())}
    brow = [stats(bidx == i) for i in range(nb)]
    mrows = {f: stats(midx == f) for f in B.mids}
    isl = stats(np.ones(len(walkers), bool))
    # checks
    bad = []
    want = int(sum(expo["vars"]["walk_cur"]["pop"]))                 # the published residents within a 400 m walk of a current stop, summed over the municipios
    if want is not None and want != isl["walkers"]:
        bad.append(f"the residents with a walk ({isl['walkers']:,}) are not the published walk_cur residents ({want:,})")
    if not (CHECK_MEDIAN[0] <= isl["med"] <= CHECK_MEDIAN[1]):
        bad.append(f"Puerto Rico's median round-trip climb is {isl['med']} m, outside {CHECK_MEDIAN}")
    for f in HILLS:
        if mrows[f] is None or mrows[f]["med"] <= isl["med"]:
            bad.append(f"{f}'s median climb ({mrows[f] and mrows[f]['med']} m) is not above Puerto Rico's ({isl['med']} m)")
    for f in FLAT:
        if mrows[f] is None or mrows[f]["med"] >= isl["med"]:
            bad.append(f"{f}'s median climb ({mrows[f] and mrows[f]['med']} m) is not below Puerto Rico's ({isl['med']} m)")
    if bad:
        raise SystemExit("climb: the figures fail their checks:\n  " + "\n  ".join(bad))
    log(f"  Puerto Rico: {isl['walkers']:,} residents with a walk (published walk_cur {want}); median round-trip climb {isl['med']} m; steep {isl['steep_pct']}% "
        f"({isl['steep']:,}); Barranquitas {mrows['72021']['med']} m, Cataño {mrows['72033']['med']} m")
    Y_ = str(as_of.year)
    G = "Infrastructure · Climb on the walk to a stop (USGS 3DEP)"
    REF = (f"Walks along mapped roads (site/data/roads.bin) from each 2020 census block within a 400 m walk of a stop with a current timetable on {as_of} "
           "(transport.json, operators.json) to its nearest one; heights from USGS 3DEP 1/3 arc-second (about 10 m), read every 10 m along the walk")
    WALK = ("The walkers are the residents of the 2020 census blocks whose point is within a 400 m walk along mapped roads of a transit stop with a current timetable "
            f"(the observatory's measure 'within a 400 m walk', on {as_of}). Each block's walk is the shortest one along the mapped roads to its nearest current stop; "
            "the ground's height (USGS 3DEP, about 10 m) is read every 10 m along the roads, from the road nearest the block to the stop. Where few residents live "
            "within a walk, one block moves the figure a lot. Heights are of the bare ground: a walk over a bridge or an embankment reads the "
            "valley or the slope below, and steps, sidewalks and footpaths are not on the map. A block counts whole, in the barrio the crosswalk gives it.")
    CLIMB = " The round-trip climb is the sum of the rises and falls along the walk: the metres climbed going to the stop and coming back."
    STEEP_ = (" A steep stretch is a 30 m stretch that rises or falls more than 1 in 12 (8.33%), the steepest running slope a ramp may have under the 2010 ADA "
              "Standards for Accessible Design (405.2).")

    def var(key, label, unit, d, typ, definition, field, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["usgs_3dep_13", "census_tiger"], "ref": REF,
                "definition": definition, "family": "infrastructure", "counted": False, "barrioFile": OUT_BARRIO.name, "noValue": NO_WALK, "noPerHU": True, **extra,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("walk_climb_med", "Round-trip climb of the walk to a current stop, median (m)", "m", 1, "ratio",
              "The median, over the residents within a 400 m walk of a current stop, of the round-trip climb of their walk." + CLIMB + " " + WALK, "med"),
          var("walk_steep_pct", "Walks to a current stop with a stretch steeper than a ramp may be (%)", "%", 1, "rate",
              "The share of the residents within a 400 m walk of a current stop whose walk has a steep stretch." + STEEP_ + " " + WALK, "steep_pct", tag="estimate"),
          var("walk_steep_res", "Residents whose walk to a current stop has a stretch steeper than a ramp may be (estimate)", "", 0, "count",
              "The residents within a 400 m walk of a current stop whose walk has a steep stretch." + STEEP_ + " " + WALK, "steep", tag="estimate", classes="jenks")]
    out_b = {"walk_climb_med": "med", "walk_steep_pct": "steep_pct", "walk_steep_res": "steep"}
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, "years": {Y_: [None if r is None else r[fld] for r in brow]}} for k, fld in out_b.items()],
              "notes": {"areas": nb, "source": "climb.py; the municipio values and the method are in climb_series.json", "estimates": ["walk_steep_pct", "walk_steep_res"]}}
    notes = {"as_of": as_of.isoformat(), "blocks_with_a_walk": int(len(walkers)), "residents_with_a_walk": isl["walkers"], "published_walk_cur": want,
             "walks_in_a_straight_line": straight, "points_read": int(len(flat)), "step_m": STEP_M, "window_m": WINDOW_M, "steep_grade": round(STEEP, 4),
             "dem_tiles": sorted(u.rsplit("/", 1)[-1] for u in dem_tiles(offline).values()),
             "checks": {"pr_median_m": isl["med"], **{f"{f}_median_m": mrows[f]["med"] for f in HILLS + FLAT}},
             "no_value": {"barrios": [B.ids[i] for i in range(nb) if brow[i] is None], "municipios": [f for f in B.mids if mrows[f] is None]}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    return series, barrio


def build(check=False):
    """Writes the two files, only when a value changed (the nightly transit refresh runs it after the exposure files: refresh_network.py)."""
    series, barrio = compute(offline=check)
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        same = old is not None and {**old, "built": None} == {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}
        if check:
            print(f"{path.name} matches the cache" if same else f"{path.name} is not what the cache gives: run python climb.py")
            status |= 0 if same else 1
            continue
        if same:
            log(f"{path.name} unchanged")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {len(d['vars'])} variables, {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--check" in sys.argv))
