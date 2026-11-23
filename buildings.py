"""Buildings for the PR Data Observatory, for the 901 barrios and the 78 municipios: how many buildings there are, how much of the land is under roofs, the size of
a typical building, how many stand in a FEMA Special Flood Hazard Area, and how many were traced by machine learning rather than by OpenStreetMap volunteers.
Step A1 of the GeoAI sources plan (docs/geoai-sources-proposal-2026-11.md, HANDOFF decision 91; method in docs/buildings.md).

    python buildings.py             # build site/data/buildings_series.json and site/data/buildings_barrio.json (downloads the newest Overture release once into cache/buildings/)
    python buildings.py --refresh   # look for a newer Overture release and download it when there is one
    python buildings.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

The source. The Overture Maps Foundation's buildings theme, which joins building footprints from OpenStreetMap (first, so volunteers' edits win), Google Open
Buildings, Microsoft's ML building footprints, Esri Community Maps and others into one set, released every month as GeoParquet on public cloud storage (no key).
Licence: ODbL 1.0, because it holds OpenStreetMap data; credit "© OpenStreetMap contributors, Overture Maps Foundation". The overturemaps package (already used for
places) reads the files for a box around Puerto Rico.

How it is made (docs/buildings.md):
  - The download keeps, for each building, one point inside its outline (shapely's point on surface), its footprint area in square metres (on the same Lambert
    equal-area plane as conditions.Barrios), the dataset of its first source, and its height when Overture has one. Not the outlines, and not the ids. The cache is
    cache/buildings/<release>.npz, a few tens of MB, never published.
  - Areas: a building belongs to the barrio whose outline holds its point; a point just off the coast (a pier, a building on a reef) goes to the nearest barrio
    within 100 m; farther ones (Saint Thomas is outside the box) are left out and counted in the notes. Municipios and Puerto Rico pool their barrios.
  - Flood: a building counts as in a Special Flood Hazard Area (the 1% annual chance flood) when its point is inside one of the FEMA areas of flood.geojson,
    by exposure.flood_polygons (the rule of the flood exposure figures).
  - Land under roofs: the footprints' area over the area's land area (Census, the crosswalk's km2). A footprint is traced from above, so it is the roof's outline.
  - Machine learning: a building whose first source is not OpenStreetMap (Google, Microsoft, Esri and others are traced by machine learning or by companies). In
    barrios where most buildings come from machine learning, counts are less certain: small sheds may be counted and buildings under trees missed.
  - Checks that stop the build: between 1.9 and 2.5 million buildings in Puerto Rico; at least 99.5% placed in a barrio; San Juan denser than Puerto Rico; the
    flood share between 1% and 30%; and, across the barrios, more housing units means more buildings (a Spearman rank correlation of 0.6 or more).
Private homes: most buildings are homes, so nothing is published per building. The files hold counts, areas and shares by barrio and larger areas only.
"""

import json
import sys
from datetime import date
from pathlib import Path

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "buildings"
OUT = hs.OUT
OUT_SERIES = OUT / "buildings_series.json"
OUT_BARRIO = OUT / "buildings_barrio.json"
log = hs.log

BBOX = (-67.97, 17.85, -65.20, 18.57)   # the places box (build.py): Mona to Culebra; Saint Thomas begins at about -65.09
NEAR_DEG = 0.001                        # about 100 m: a point off the coast goes to the nearest barrio within this
SAN_JUAN = "72127"
SOURCE_CODES = {"OpenStreetMap": 0, "Google Open Buildings": 1, "Microsoft ML Buildings": 2, "Esri Community Maps": 3}   # anything else: 9
FLOOR_N, CEIL_N = 1_900_000, 2_500_000
MIN_PLACED = 0.995
MIN_RHO_HU = 0.6


def latest_release():
    from overturemaps import core
    return core.get_latest_release()


def cached_release():
    files = sorted(CACHE.glob("*.npz"))
    return files[-1].stem if files else None


def download(release):
    """Read the buildings theme for BBOX and keep the point, area, source and height of each building in cache/buildings/<release>.npz."""
    import numpy as np
    import shapely
    from overturemaps import core
    from pyproj import Transformer
    import conditions
    T = Transformer.from_crs("EPSG:4326", conditions.LAEA, always_xy=True)
    lon, lat, area, src, height, other = [], [], [], [], [], {}
    n = 0
    reader = core.record_batch_reader("building", bbox=BBOX, release=release)
    if reader is None:
        raise SystemExit(f"buildings: Overture release {release} has no buildings for the box")
    for batch in reader:
        cols = batch.schema.names
        g = shapely.from_wkb(batch.column(cols.index("geometry")).to_numpy(zero_copy_only=False))
        p = shapely.point_on_surface(g)
        lon.append(shapely.get_x(p))
        lat.append(shapely.get_y(p))
        area.append(shapely.area(shapely.transform(g, lambda xy: np.column_stack(T.transform(xy[:, 0], xy[:, 1])))).astype("float32"))
        srcs = batch.column(cols.index("sources")).to_pylist()
        codes = []
        for s in srcs:
            ds = (s or [{}])[0].get("dataset") or ""
            c = SOURCE_CODES.get(ds, 9)
            if c == 9:
                other[ds] = other.get(ds, 0) + 1
            codes.append(c)
        src.append(np.array(codes, dtype="uint8"))
        h = batch.column(cols.index("height")).to_numpy(zero_copy_only=False)
        height.append(np.array([np.nan if v is None else v for v in h], dtype="float32"))
        n += len(g)
        if n % 500_000 < len(g):
            log(f"  {n:,} buildings read")
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{release}.npz"
    np.savez_compressed(path, lon=np.concatenate(lon), lat=np.concatenate(lat), area=np.concatenate(area), src=np.concatenate(src),
                        height=np.concatenate(height), other=np.array(json.dumps(other)))
    log(f"  wrote {path.relative_to(ROOT)}: {n:,} buildings, {path.stat().st_size / 1048576:.1f} MB; other sources {other}")
    return path


def load(refresh=False, offline=False):
    import numpy as np
    have = cached_release()
    if offline:
        if not have:
            raise SystemExit("buildings: no cache in cache/buildings/ (run python buildings.py first)")
        release = have
    else:
        release = latest_release() if (refresh or not have) else have
        if release != have:
            download(release)
    z = np.load(CACHE / f"{release}.npz")
    return release, {k: z[k] for k in z.files}


def place(B, lon, lat):
    """The barrio index of each point (-1 when none within NEAR_DEG): inside an outline first (the lowest index on a shared edge, as Barrios.at), then the nearest."""
    import numpy as np
    import shapely
    pts = shapely.points(lon, lat)
    hit, tree_i = B.tree.query(pts, predicate="intersects")
    out = np.full(len(lon), -1, dtype="int32")
    order = np.lexsort((tree_i, hit))   # by point, then lowest barrio first
    hit, tree_i = hit[order], tree_i[order]
    first = np.r_[True, hit[1:] != hit[:-1]]
    out[hit[first]] = tree_i[first]
    left = np.flatnonzero(out < 0)
    if len(left):
        q, t = B.tree.query_nearest(pts[left], max_distance=NEAR_DEG)
        o = np.lexsort((t, q))
        q, t = q[o], t[o]
        f = np.r_[True, q[1:] != q[:-1]] if len(q) else np.array([], dtype=bool)
        out[left[q[f]]] = t[f]
    return out


def in_flood(lon, lat):
    """True for the points inside a FEMA Special Flood Hazard Area of flood.geojson (exposure.flood_polygons)."""
    import numpy as np
    import shapely
    from shapely.strtree import STRtree
    import exposure
    sfha, _ = exposure.flood_polygons(json.loads((OUT / "flood.geojson").read_text(encoding="utf-8")))
    tree = STRtree(sfha)
    p, _ = tree.query(shapely.points(lon, lat), predicate="intersects")
    m = np.zeros(len(lon), dtype=bool)
    m[p] = True
    return m


def spearman(a, b):
    import numpy as np
    ra, rb = (np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float) for x in (a, b))
    return float(np.corrcoef(ra, rb)[0, 1])


def compute(refresh=False, offline=False):
    import numpy as np
    import conditions
    B = conditions.Barrios()
    nb = len(B.ids)
    release, z = load(refresh, offline)
    lon, lat, area, src = z["lon"], z["lat"], z["area"].astype("float64"), z["src"]
    n_all = len(lon)
    bi = place(B, lon, lat)
    ok = bi >= 0
    placed = float(ok.mean())
    flood = in_flood(lon, lat)
    log(f"  release {release}: {n_all:,} buildings, {placed:.2%} placed in a barrio, {int(flood[ok].sum()):,} in a Special Flood Hazard Area")
    bi, area, src, flood = bi[ok], area[ok], src[ok], flood[ok]
    mi = np.array([B.mids.index(B.ids[i][:5]) for i in range(nb)])[bi]
    nm = len(B.mids)

    def rows(idx, k, land_km2):
        n = np.bincount(idx, minlength=k)
        roof = np.bincount(idx, weights=area, minlength=k)
        fl = np.bincount(idx, weights=flood, minlength=k)
        ml = np.bincount(idx, weights=(src != 0), minlength=k)
        order = np.argsort(idx, kind="stable")
        cuts = np.cumsum(n)[:-1]
        meds = [float(np.median(a)) if len(a) else None for a in np.split(area[order], cuts)]
        out = []
        for j in range(k):
            if not n[j]:
                out.append(None)
                continue
            land = land_km2[j]
            out.append({"n": int(n[j]), "per_km2": round(n[j] / land, 1) if land else None, "roof_pct": round(roof[j] / (land * 1e6) * 100, 1) if land else None,
                        "area_med": round(meds[j]), "sfha_n": int(fl[j]), "sfha_pct": round(fl[j] / n[j] * 100, 1), "ml_pct": round(ml[j] / n[j] * 100, 1)})
        return out

    land_b = [B.unit[b]["km2"] for b in B.ids]
    land_m = [B.unit[m]["km2"] for m in B.mids]
    brow = rows(bi, nb, land_b)
    mrows_ = rows(mi, nm, land_m)
    mrows = dict(zip(B.mids, mrows_))
    isl = rows(np.zeros(len(bi), dtype=int), 1, [sum(land_m)])[0]
    hu = np.array([B.unit[b]["hu"] for b in B.ids], dtype=float)
    nbld = np.array([0 if r is None else r["n"] for r in brow], dtype=float)
    rho = spearman(nbld, hu)
    bad = []
    if not FLOOR_N <= n_all <= CEIL_N:
        bad.append(f"{n_all:,} buildings in the box (expected {FLOOR_N:,} to {CEIL_N:,}; 2026-11-09: 2,157,363)")
    if placed < MIN_PLACED:
        bad.append(f"only {placed:.2%} of the buildings placed in a barrio (expected {MIN_PLACED:.1%} or more)")
    if not mrows[SAN_JUAN]["per_km2"] > isl["per_km2"]:
        bad.append(f"San Juan ({mrows[SAN_JUAN]['per_km2']}/km²) is not denser than Puerto Rico ({isl['per_km2']}/km²)")
    if not 1 <= isl["sfha_pct"] <= 30:
        bad.append(f"{isl['sfha_pct']}% of the buildings in a Special Flood Hazard Area (expected 1% to 30%)")
    if rho < MIN_RHO_HU:
        bad.append(f"across the barrios, buildings and 2020 housing units have a Spearman correlation of {rho:.2f} (expected {MIN_RHO_HU} or more)")
    if bad:
        raise SystemExit("buildings: the counts fail their checks:\n  " + "\n  ".join(bad))
    log(f"  Puerto Rico: {isl['n']:,} buildings, {isl['per_km2']}/km², {isl['roof_pct']}% of the land under roofs, median {isl['area_med']} m², "
        f"{isl['sfha_pct']}% in a SFHA, {isl['ml_pct']}% by machine learning; San Juan {mrows[SAN_JUAN]['per_km2']}/km²; Spearman with housing units {rho:.3f}")

    Y_ = release[:4]
    G = "Housing · Buildings (Overture)"
    REF = (f"Overture Maps Foundation, buildings theme, release {release} (OpenStreetMap, Google Open Buildings and Microsoft ML Buildings footprints, joined by "
           "Overture), read for a box around Puerto Rico; one point inside each outline and its footprint area on an equal-area plane. © OpenStreetMap contributors, "
           "Overture Maps Foundation (ODbL 1.0)")
    WHAT = (f"A building is one footprint in Overture's buildings theme (release {release}): the outline of a roofed structure as traced from above, by OpenStreetMap "
            "volunteers or, where they have not mapped, by Google's or Microsoft's machine learning. A building belongs to the barrio that holds a point inside its "
            "outline; a municipio's and Puerto Rico's figures pool their barrios. Sheds, carports and ruins can be counted, and buildings hidden by trees can be missed, "
            "more often where machine learning traced them.")
    FLOOD = (" A building counts as in a Special Flood Hazard Area (the area FEMA maps with a 1% chance of flooding each year) when a point inside its outline falls "
             "in one in flood.geojson.")

    def var(key, label, unit, d, typ, definition, field, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["overture_buildings", "census_tiger"], "ref": REF,
                "definition": definition, "family": "buildings", "counted": False, "barrioFile": OUT_BARRIO.name, **extra,
                "years": {Y_: [None if mrows[f] is None else mrows[f][field] for f in B.mids] + [isl[field]]}}
    vs = [var("bld_n", "Buildings (Overture footprints)", "", 0, "count", "The number of buildings in the area. " + WHAT, "n", classes="jenks"),
          var("bld_per_km2", "Buildings per km² of land", "", 1, "rate", "Buildings per square kilometre of the area's land (Census land area). " + WHAT, "per_km2"),
          var("bld_roof_pct", "Land under roofs (%)", "%", 1, "rate",
              "The footprints' area as a share of the area's land area (Census). A footprint traced from above is the roof's outline, so eaves count. " + WHAT, "roof_pct"),
          var("bld_area_med", "Median building footprint (m²)", "m²", 0, "ratio",
              "The middle footprint area of the area's buildings, in square metres on an equal-area plane: half are smaller. " + WHAT, "area_med"),
          var("bld_sfha_n", "Buildings in a FEMA Special Flood Hazard Area", "", 0, "count", "The number of buildings in a Special Flood Hazard Area." + FLOOD + " " + WHAT,
              "sfha_n", classes="jenks"),
          var("bld_sfha_pct", "Buildings in a FEMA Special Flood Hazard Area (%)", "%", 1, "rate",
              "The share of the area's buildings in a Special Flood Hazard Area." + FLOOD + " " + WHAT, "sfha_pct"),
          var("bld_ml_pct", "Buildings traced by machine learning (%)", "%", 1, "rate",
              "The share of the area's buildings whose footprint comes from Google Open Buildings or Microsoft ML Buildings rather than OpenStreetMap: a measure of "
              "how the data were made, not of the buildings. Where it is high, counts and sizes are less certain. " + WHAT, "ml_pct")]
    keys = {"bld_n": "n", "bld_per_km2": "per_km2", "bld_roof_pct": "roof_pct", "bld_area_med": "area_med", "bld_sfha_n": "sfha_n", "bld_sfha_pct": "sfha_pct", "bld_ml_pct": "ml_pct"}
    none = [B.ids[i] for i in range(nb) if brow[i] is None]
    barrio = {"level": "barrio", "geo": {"ids": B.ids},
              "vars": [{"key": k, **({"noValueWhy": [{"why": "No buildings in Overture", "ids": none}]} if none else {}),
                        "years": {Y_: [None if r is None else r[f] for r in brow]}} for k, f in keys.items()],
              "notes": {"areas": nb, "source": "buildings.py; the municipio values and the method are in buildings_series.json"}}
    by_src = np.bincount(z["src"], minlength=10)
    notes = {"release": release, "box": list(BBOX), "buildings_in_box": n_all, "placed_in_a_barrio": int(ok.sum()), "left_out": int(n_all - ok.sum()),
             "by_source": {"OpenStreetMap": int(by_src[0]), "Google Open Buildings": int(by_src[1]), "Microsoft ML Buildings": int(by_src[2]),
                           "Esri Community Maps": int(by_src[3]), "other": int(by_src[9])},
             "with_height": int(np.isfinite(z["height"]).sum()),
             "checks": {"san_juan_per_km2": mrows[SAN_JUAN]["per_km2"], "pr_per_km2": isl["per_km2"], "pr_sfha_pct": isl["sfha_pct"],
                        "spearman_buildings_housing_units": round(rho, 3), "buildings_per_housing_unit_pr": round(isl["n"] / float(hu.sum()), 3)},
             "no_value": {"barrios": none, "municipios": [f for f in B.mids if mrows[f] is None]}}
    SOURCES = {"overture_buildings": {"name": "Overture Maps Foundation — Buildings theme", "url": "https://docs.overturemaps.org/guides/buildings/",
                                      "license": "ODbL 1.0; credit © OpenStreetMap contributors, Overture Maps Foundation",
                                      "note": f"Release {release}, read with the overturemaps package for a box around Puerto Rico (public files, no key)."},
               "census_tiger": {"name": "US Census Bureau — 2020 barrio outlines and land area (TIGER/Line)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                                "license": "US Government work (no US copyright)", "note": "Barrio outlines, land area and 2020 housing units from the observatory's crosswalk."}}
    series = {"as_of": Y_, "years": [int(Y_)], "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}
    return series, barrio


def build(refresh=False, check=False):
    series, barrio = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python buildings.py")
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
