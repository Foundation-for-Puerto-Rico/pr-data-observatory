"""The buildings the 3D view was missing: building footprints that Google and Microsoft traced by machine learning and OpenStreetMap does not have, as one
vector tile file the 3D view draws next to the base map's buildings. Step A2 of the GeoAI sources plan (docs/geoai-sources-proposal-2026-11.md, HANDOFF
decision 91; docs/buildings3d.md).

    python buildings3d.py             # build site/data/buildings_gap.pmtiles from cache/buildings3d/ (downloads the release's tiles when missing)
    python buildings3d.py --refresh   # use the newest Overture release
    python buildings3d.py --check     # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Why. The 3D view draws the base map's buildings (OpenFreeMap, from OpenStreetMap): about 1.5 million in Puerto Rico. Overture's buildings theme has 2.16 million;
the 656,964 others (release 2026-10-21.0) come from Google Open Buildings and Microsoft ML Buildings, mostly in the countryside and the west.

How (HANDOFF decision 91 (c): hosting measured first; docs/buildings3d.md):
  - Overture publishes its buildings as vector tiles (PMTiles, zooms 0 to 14, about 180 GB for the world). The build reads the tiles of zooms 13 and 14 over
    Puerto Rico by HTTP range requests (about 2,300 tiles, 150 MB, six minutes) into cache/buildings3d/, never published.
  - From each tile it keeps the buildings whose geometry source is not OpenStreetMap, with their height and base height when Overture has them, and nothing
    else (no id, name, class or source record), and writes them into one PMTiles file, layer "b", zooms 13 and 14. Measured on 2026-11-10: every building slimmed
    this way is 29.0 MB; the missing ones alone 7.3 MB; Overture's own tiles for Puerto Rico 153.5 MB (over GitHub Pages' 100 MB a file).
  - The 3D view reads the file with the PMTiles library and draws it under the same "3D buildings" switch; a building without a height gets the same 6 m as the
    base map's.
  - Checks that stop the build: the file has between 550,000 and 800,000 features at zoom 14 (a building on a tile edge counts in each tile; 704,061 on
    2026-11-10), it is under 20 MB, and no feature comes from OpenStreetMap.
License: ODbL 1.0 (Overture's buildings theme), credit "© OpenStreetMap contributors, Overture Maps Foundation"; the file is offered under ODbL 1.0.
Private homes: the file holds outlines and heights, as any base map does; no name, address, use or value is attached to a building.
"""

import gzip
import hashlib
import json
import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "buildings3d"
OUT = hs.OUT / "buildings_gap.pmtiles"
log = hs.log

TILES = "https://overturemaps-extras-us-west-2.s3.us-west-2.amazonaws.com/tiles/{release}/buildings.pmtiles"
BBOX = (-67.97, 17.85, -65.20, 18.57)   # as buildings.py
ZOOMS = (13, 14)
LAYER = "b"
MIN_N, MAX_N = 550_000, 800_000
MAX_MB = 20


def release(refresh=False, offline=False):
    have = sorted(p.stem.split("_")[1] for p in CACHE.glob("pr_*.pmtiles"))
    if offline or (have and not refresh):
        if not have:
            raise SystemExit("buildings3d: no cache in cache/buildings3d/ (run python buildings3d.py first)")
        return have[-1]
    from overturemaps import core
    return core.get_latest_release()


def tile_xy(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def download(rel):
    """Overture's tiles of ZOOMS over BBOX into cache/buildings3d/pr_<release>.pmtiles, as they are (gzip-compressed vector tiles)."""
    import requests
    from pmtiles.reader import Reader
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer
    url = TILES.format(release=rel)
    local = threading.local()

    def get(offset, length):
        s = getattr(local, "s", None) or requests.Session()
        local.s = s
        for i in range(5):
            try:
                r = s.get(url, headers={"Range": f"bytes={offset}-{offset + length - 1}"}, timeout=60)
                if r.status_code == 206:
                    return r.content
                r.raise_for_status()
                raise SystemExit(f"buildings3d: {url} does not answer range requests (HTTP {r.status_code})")
            except requests.RequestException:
                if i == 4:
                    raise
                time.sleep(3 * (i + 1))
    R = Reader(get)
    jobs = []
    for z in ZOOMS:
        x0, y0 = tile_xy(BBOX[0], BBOX[3], z)
        x1, y1 = tile_xy(BBOX[2], BBOX[1], z)
        jobs += [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    log(f"  reading {len(jobs):,} tiles of Overture release {rel} (zooms {ZOOMS[0]}-{ZOOMS[-1]})")
    with ThreadPoolExecutor(16) as ex:
        got = {j: d for j, d in zip(jobs, ex.map(lambda j: R.get(*j), jobs)) if d}
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"pr_{rel}.pmtiles"
    with open(path, "wb") as f:
        w = Writer(f)
        for k in sorted(got, key=lambda k: zxy_to_tileid(*k)):
            w.write_tile(zxy_to_tileid(*k), got[k])
        w.finalize(header(TileType, Compression), {"name": f"Overture buildings, Puerto Rico, release {rel}", "release": rel})
    for old in CACHE.glob("pr_*.pmtiles"):
        if old != path:
            old.unlink()
    log(f"  wrote {path.relative_to(ROOT)}: {len(got):,} tiles, {path.stat().st_size / 1e6:.1f} MB")
    return path


def header(TileType, Compression):
    return {"tile_type": TileType.MVT, "tile_compression": Compression.GZIP, "min_zoom": ZOOMS[0], "max_zoom": ZOOMS[-1],
            "min_lon_e7": int(BBOX[0] * 1e7), "min_lat_e7": int(BBOX[1] * 1e7), "max_lon_e7": int(BBOX[2] * 1e7), "max_lat_e7": int(BBOX[3] * 1e7),
            "center_zoom": 14, "center_lon_e7": int(-66.45 * 1e7), "center_lat_e7": int(18.22 * 1e7)}


def slim(data):
    """(new tile bytes or None, features kept, OpenStreetMap features seen, height values kept) for one gzip-compressed Overture tile."""
    import mapbox_vector_tile as mvt
    d = mvt.decode(gzip.decompress(data), default_options={"y_coord_down": True})
    lay = d.get("building", {})
    keep, osm = [], 0
    for f in lay.get("features", []):
        p = f["properties"]
        if str(p.get("@geometry_source", "")).lower().startswith("openstreetmap"):
            osm += 1
            continue
        q = {k: round(float(p[k]), 1) for k in ("height", "min_height") if p.get(k) is not None}
        keep.append({"geometry": f["geometry"], "properties": q})
    if not keep:
        return None, 0, osm, 0
    raw = mvt.encode([{"name": LAYER, "features": keep}], default_options={"extents": lay.get("extent", 4096), "y_coord_down": True})
    return gzip.compress(raw, 9, mtime=0), len(keep), osm, sum(len(f["properties"]) for f in keep)


def compute(refresh=False, offline=False):
    from pmtiles.reader import MmapSource, Reader, all_tiles
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    rel = release(refresh, offline)
    path = CACHE / f"pr_{rel}.pmtiles"
    if not path.exists():
        if offline:
            raise SystemExit(f"buildings3d: no cached tiles for release {rel}")
        download(rel)
    tiles, n14, osm, v14 = {}, 0, 0, 0
    with open(path, "rb") as f:
        R = Reader(MmapSource(f))
        for (z, x, y), data in all_tiles(R.get_bytes):
            t, n, o, v = slim(data)
            osm += o
            if z == 14:
                n14 += n
                v14 += v
            if t:
                tiles[zxy_to_tileid(z, x, y)] = t
    return rel, tiles, n14, osm, v14


def write(rel, tiles, dest, n14=None, v14=None):
    from pmtiles.tile import Compression, TileType
    from pmtiles.writer import Writer
    meta = {"name": "Buildings missing from the base map (Overture, not OpenStreetMap)", "release": rel,
            "attribution": "© OpenStreetMap contributors, © Overture Maps Foundation (ODbL 1.0)",
            "vector_layers": [{"id": LAYER, "fields": {"height": "Number", "min_height": "Number"}, "minzoom": ZOOMS[0], "maxzoom": ZOOMS[-1]}],
            "features_z14": n14, "values_z14": v14}   # for ledger.py, which reads the metadata, not the tiles (a building on a tile edge counts in each tile)
    with open(dest, "wb") as f:
        w = Writer(f)
        for tid in sorted(tiles):
            w.write_tile(tid, tiles[tid])
        w.finalize(header(TileType, Compression), meta)


def build(refresh=False, check=False):
    rel, tiles, n14, osm, v14 = compute(refresh, offline=check)
    bad = []
    if not MIN_N <= n14 <= MAX_N:
        bad.append(f"{n14:,} features at zoom 14 (expected {MIN_N:,} to {MAX_N:,}; 2026-11-10: 704,061)")
    log(f"  release {rel}: {len(tiles):,} tiles, {n14:,} features at zoom 14 kept, {osm:,} OpenStreetMap features left out")
    tmp = OUT.with_suffix(".tmp")
    write(rel, tiles, tmp, n14, v14)
    mb = tmp.stat().st_size / 1e6
    if mb > MAX_MB:
        bad.append(f"the file is {mb:.1f} MB (expected under {MAX_MB} MB)")
    if bad:
        tmp.unlink()
        raise SystemExit("buildings3d: the file fails its checks:\n  " + "\n  ".join(bad))
    if check:
        same = OUT.exists() and hashlib.sha256(OUT.read_bytes()).digest() == hashlib.sha256(tmp.read_bytes()).digest()
        tmp.unlink()
        print(f"{OUT.name} {'matches' if same else 'is not what'} the cache{'' if same else ' gives: run python buildings3d.py'}")
        return 0 if same else 1
    tmp.replace(OUT)
    (CACHE / "last_build.json").write_text(json.dumps({"release": rel, "tiles": len(tiles), "features_z14": n14, "mb": round(mb, 1)}), encoding="utf-8")
    log(f"wrote {OUT.name}: {mb:.1f} MB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
