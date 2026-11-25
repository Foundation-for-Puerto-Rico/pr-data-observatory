"""How much can counting a census block whole change an exposure count? (plan item 5, 2026-10-06)

    python block_edge_bounds.py           # downloads the 2020 block outlines once (about 40 MB) into cache/network/blocks_geom, then prints and writes block_edge_bounds.json next to this file
    python block_edge_bounds.py --pages 3 # a quick trial on the first 3,000 blocks (prints only)

exposure.py gives a block to a layer by its one internal point. A block that the edge of a layer cuts is counted whole in or out: all of its residents are counted as exposed, or none are.
Two checks on what that does, for the polygon families of the exposure series (FEMA flood areas, NOAA sea level rise at 1, 3 and 10 ft, USGS protected areas):

1. Bounds. The true count lies between two counts that need no assumption about where people live inside a block: the residents of blocks that lie wholly inside the layer (lower bound)
   and of every block the layer touches (upper bound). The script says how far apart they are for the island and, typically, for a municipio, a barrio and a census tract.
2. Area weighting. On blocks with no water (outline area within 3% of the Census land area), it spreads each block's residents evenly over its area, counts the share inside the layer, and compares
   that with the internal-point count: for the island, and area by area.

How it decides "wholly inside", "touched" and the area share: each block outline is sampled with a grid of points about 60 m apart (5 to 40 points on a side, only those inside the block) plus the
block's internal point, and every sample is tested against the layer with exposure.points_in_polygons. A block is wholly inside when all its samples are, touched when any is; its area share is the
share of its samples that are inside. A sliver thinner than the grid can be missed, so the bounds are close, not exact. Blocks with no residents and no housing units are skipped (they add nothing
to a count).

Water: Census block outlines run out into coastal water, and NOAA's sea level rise areas are land that would flood, so a coastal block can never be "wholly inside" a sea level rise area. That makes
the lower bound lower than the truth for sea level rise (the range is wider than it needs to be); the upper bound is not affected. Protected-area outlines can include sea, which can make the upper
bound for those higher than the truth. The ranges are therefore safe: the true count is inside them. Area weighting is done only where there is no water, for the same reason.

Reads public Census Bureau and NOAA data only (the files exposure.py already downloaded, plus the block outlines from TIGERweb). Aggregates only; nothing here is published on the site.
"""
import argparse
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import exposure  # noqa: E402
import geo  # noqa: E402
import network  # noqa: E402

PAGE = 1000
GRID_M, MIN_N, MAX_N = 60, 5, 40
CHUNK = 400_000
WATER_FREE = 0.03                 # outline area within 3% of the Census land area
FAMILIES = ("flood_sfha", "flood_any", "slr_1ft", "slr_3ft", "slr_10ft", "protected", "protected_strict")
M_PER_DEG = 111_320


def log(*a):
    print(*a, flush=True)


def block_outlines(pages=None):
    """GeoJSON features of the 2020 census blocks of Puerto Rico, downloaded page by page and kept in cache/network/blocks_geom."""
    d = exposure.CACHE / "network" / "blocks_geom"
    d.mkdir(parents=True, exist_ok=True)
    feats, offset, n = [], 0, 0
    while pages is None or n < pages:
        p = d / f"page_{offset:06d}.json"
        if not p.exists():
            r = requests.get(f"{network.CENSUS_BLOCKS}/query", headers=exposure.UA, timeout=300, params={
                "where": "STATE='72'", "outFields": "GEOID", "returnGeometry": "true", "outSR": 4326, "geometryPrecision": 6, "maxAllowableOffset": 0.00002,
                "f": "geojson", "resultOffset": offset, "resultRecordCount": PAGE, "orderByFields": "OBJECTID"})
            r.raise_for_status()
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.replace(p)
            log(f"  block outlines from {offset:,}")
        j = json.loads(p.read_text(encoding="utf-8"))
        fs = j["features"]
        feats += fs
        n += 1
        if not fs or not j.get("exceededTransferLimit"):
            break
        offset += len(fs)
    return feats


def sample_points(feats, blocks):
    """(x, y, block index, used, outline area in m2) of sample points inside each block that has residents or housing units: a grid of about GRID_M meters plus the block's internal point."""
    where = {g: i for i, g in enumerate(blocks.ids)}
    xs, ys, bi = [], [], []
    used = np.zeros(len(blocks), dtype=bool)
    area = np.full(len(blocks), np.nan)
    for ft in feats:
        i = where.get(ft["properties"]["GEOID"])
        if i is None or (blocks.pop[i] == 0 and blocks.hu[i] == 0):
            continue
        if ft.get("geometry"):
            g = shape(ft["geometry"])
            minx, miny, maxx, maxy = g.bounds
            w = (maxx - minx) * M_PER_DEG * math.cos(math.radians(blocks.lat[i]))
            h = (maxy - miny) * M_PER_DEG
            nx, ny = (int(min(MAX_N, max(MIN_N, math.ceil(v / GRID_M)))) for v in (w, h))
            gx = minx + (np.arange(nx) + 0.5) * (maxx - minx) / nx
            gy = miny + (np.arange(ny) + 0.5) * (maxy - miny) / ny
            X, Y = (a.ravel() for a in np.meshgrid(gx, gy))
            ok = shapely.contains_xy(g, X, Y)
            area[i] = g.area * M_PER_DEG ** 2 * math.cos(math.radians(blocks.lat[i]))
        else:                                  # no outline: the internal point alone
            X = Y = np.zeros(0)
            ok = np.zeros(0, dtype=bool)
        xs += [X[ok], [blocks.lon[i]]]
        ys += [Y[ok], [blocks.lat[i]]]
        bi += [np.full(int(ok.sum()) + 1, i)]
        used[i] = True
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(bi), used, area


def layer_polygons(data_dir=exposure.DATA):
    """{family: polygons} for the FAMILIES, as exposure.hazard_flags reads them."""
    sfha, any_ = exposure.flood_polygons(exposure.load_json(Path(data_dir) / "flood.geojson"))
    real, strict = exposure.protected_polygons(exposure.load_json(Path(data_dir) / "protected.geojson"))
    out = {"flood_sfha": sfha, "flood_any": any_, "protected": real, "protected_strict": strict}
    gdb = exposure.slr_gdb(exposure.CACHE / "slr")
    for n in (1, 3, 10):
        out[f"slr_{n}ft"] = exposure.slr_layer(gdb, "slr", n)
    return {k: out[k] for k in FAMILIES}


def spread(values, round_to=2):
    """Median, 90th percentile and maximum of absolute values, and how many are 5 or more."""
    a = np.abs(np.asarray(values, dtype=float))
    return {"median": round(float(np.median(a)), round_to), "p90": round(float(np.percentile(a, 90)), round_to), "max": round(float(a.max()), round_to), "units_5_or_more": int((a >= 5).sum())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", type=int, help="only the first N pages of 1,000 blocks (a trial; nothing is written)")
    args = ap.parse_args(argv)
    t0 = time.time()
    table = network.load_block_table(exposure.CACHE / "network", False)
    blocks = exposure.Blocks(table)
    land = np.array([r[3] for r in table["rows"]], dtype=float)
    ids, cw = exposure.crosswalk_ids()
    barrio_of = geo.block_barrios(table, False, exposure.CACHE / "geo")
    log("block outlines")
    feats = block_outlines(args.pages)
    log(f"  {len(feats):,} outlines, {time.time() - t0:.0f} s")
    x, y, bi, used, area = sample_points(feats, blocks)
    n_all = np.bincount(bi, minlength=len(blocks))
    log(f"  {len(x):,} sample points in {int(used.sum()):,} blocks with residents or housing units, {time.time() - t0:.0f} s")
    polys = layer_polygons()
    ip = exposure.hazard_flags(blocks, exposure.DATA, exposure.CACHE / "slr", False)
    n_in = {k: np.zeros(len(blocks)) for k in FAMILIES}
    for a in range(0, len(x), CHUNK):
        sl = slice(a, a + CHUNK)
        tree = STRtree(shapely.points(x[sl], y[sl]))
        for k in FAMILIES:
            hit = exposure.points_in_polygons(polys[k], x[sl], y[sl], tree)
            n_in[k] += np.bincount(bi[sl], weights=hit, minlength=len(blocks))
        log(f"  tested points {min(a + CHUNK, len(x)):,} of {len(x):,}, {time.time() - t0:.0f} s")
    frac = {k: np.divide(n_in[k], n_all, out=np.zeros(len(blocks)), where=n_all > 0) for k in FAMILIES}
    wf = used & (land > 0) & (np.abs(area - land) <= WATER_FREE * land)       # NaN areas (no outline) compare False
    flags = {}
    for k in FAMILIES:
        flags[f"{k}.lo"] = used & (n_in[k] == n_all)
        flags[f"{k}.pt"] = ip[k] & used
        flags[f"{k}.hi"] = used & (n_in[k] > 0)
        # the internal point is among the samples, so lo <= pt <= hi block by block; a violation means the layers or the outlines disagree
        assert not (flags[f"{k}.lo"] & ~flags[f"{k}.pt"]).any(), (k, "a block wholly inside has its internal point outside")
        assert not (flags[f"{k}.pt"] & ~flags[f"{k}.hi"]).any(), (k, "an internal point in the layer but no sample inside")
    weight = {"pop": blocks.pop.astype(float), "hu": blocks.hu.astype(float)}
    out = {"method": "block outlines sampled on a grid of about 60 m plus the internal point; wholly inside = all samples inside, touched = any sample inside; area share = share of samples inside",
           "blocks": int(used.sum()), "samples": int(len(x)), "water_free_blocks": int(wf.sum()),
           "water_free_share": {m: round(float(w[wf].sum() / w[used].sum()), 4) for m, w in weight.items()}, "families": {k: {m: {} for m in weight} for k in FAMILIES}}
    for level in exposure.LEVELS:
        idx = exposure.unit_index(blocks, level, ids[level], barrio_of)
        n = len(ids[level])
        rolled, total = exposure.roll_up(blocks, idx, n, flags)
        ok_blk = idx >= 0
        for mi, m in enumerate(("pop", "hu")):
            w = weight[m]
            tot = total[mi].astype(float)
            ok = tot > 0
            for k in FAMILIES:
                f = out["families"][k][m]
                lo, pt, hi = (rolled[f"{k}.{s}"][mi].astype(float) for s in ("lo", "pt", "hi"))
                if level == "municipio":
                    f["island"] = {"total": int(tot.sum()), "lower": int(lo.sum()), "point": int(pt.sum()), "upper": int(hi.sum())}
                    ipw, awv = (w * ip[k])[wf].sum(), (w * frac[k])[wf].sum()
                    f["island_water_free"] = {"total": int(w[wf].sum()), "point": int(round(ipw)), "area_weighted": int(round(awv))}
                f[level] = {"units": int(ok.sum()), "bounds_width_points": spread((hi - lo)[ok] / tot[ok] * 100),
                            "point_outside_bounds": int(((pt < lo) | (pt > hi))[ok].sum())}
                m_ok = ok_blk & wf
                ip_c = np.bincount(idx[m_ok], weights=(w * ip[k])[m_ok], minlength=n)
                aw_c = np.bincount(idx[m_ok], weights=(w * frac[k])[m_ok], minlength=n)
                f[level]["area_weighted_minus_point_points"] = spread((aw_c - ip_c)[ok] / tot[ok] * 100)
    for k in FAMILIES:
        for m in ("pop", "hu"):
            f = out["families"][k][m]
            i, wfi = f["island"], f["island_water_free"]
            t = i["total"]
            log(f"  {k:17s} {m}: lower {i['lower']:>9,} ({i['lower'] / t * 100:5.1f}%)  counted {i['point']:>9,} ({i['point'] / t * 100:5.1f}%)  upper {i['upper']:>9,} ({i['upper'] / t * 100:5.1f}%) | "
                f"water-free blocks: point {wfi['point']:>9,} area {wfi['area_weighted']:>9,} of {wfi['total']:,} | width median pts: municipio {f['municipio']['bounds_width_points']['median']:.1f}, "
                f"barrio {f['barrio']['bounds_width_points']['median']:.1f}, tract {f['tract']['bounds_width_points']['median']:.1f}")
    if not args.pages:
        (HERE / "block_edge_bounds.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        log(f"wrote block_edge_bounds.json, {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
