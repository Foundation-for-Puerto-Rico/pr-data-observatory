"""Geography crosswalk for the PR Data Observatory (plan item 4).

    python geo.py              # build site/data/geo/ (downloads once, then reads cache/geo and cache/network)
    python geo.py --refresh    # download again
    python geo.py --check      # check the published files against each other (no network)

Every dataset the observatory holds is reduced to numbers for a list of areas. This file builds that list, once, from Census Bureau data:

  island        1      "72"
  region        7      "reg-capital" ... (the Puerto Rico Tourism Company's tourism regions; the only region scheme the observatory holds)
  municipio     78     5-digit GEOID
  barrio        901    10-digit GEOID (Census county subdivisions with land; the 38 offshore "not defined" ones have no land and no residents)
  tract         981    11-digit GEOID
  block-group   2,555  12-digit GEOID
  block         41,987 15-digit GEOID: used only as weights, never published

Written to site/data/geo/:
  crosswalk.json      one row per unit (id, parent, names in Spanish and English, normalised name, land area, 2020 residents and housing units, internal point),
                      and the weights that carry numbers between areas that do not nest (barrio to tract), counted from blocks
  tracts.geojson      display outlines (Census cartographic boundary file 1:500,000, shoreline-clipped): for drawing only, never for area or distance
  blockgroups.geojson the same for block groups

Everything is checked against the Census Bureau's own totals before anything is written: the blocks must add up to every tract, block group,
county subdivision and county, and to the island. Rules for using the units and the weights: docs/geography.md.
"""
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT = DATA / "geo"
CACHE = ROOT / "cache" / "geo"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}

TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer"
LAYER = {"municipio": 82, "tract": 6, "block-group": 8, "barrio": 20}                      # TIGERweb 2020 layers
CB = "https://www2.census.gov/geo/tiger/GENZ2020/shp/"
CB_FILE = {"tract": "cb_2020_72_tract_500k.zip", "block-group": "cb_2020_72_bg_500k.zip"}
ATTRS = "GEOID,NAME,BASENAME,AREALAND,POP100,HU100,INTPTLAT,INTPTLON"

LEVEL_ORDER = ["island", "region", "municipio", "barrio", "tract", "block-group"]
UNIT_FIELDS = ["id", "parent", "name_es", "name_en", "norm", "km2", "pop", "hu", "lat", "lng"]
WEIGHT_FIELDS = ["barrio", "tract", "pop", "hu", "blocks"]
VERSION = 1


def norm(s):
    """Lower case, accents removed: how names are compared (user input only; data joins use ids)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn").strip()


def log(*a):
    print(*a, flush=True)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ── Downloads (cached under cache/geo) ───────────────────────────────────────

def get(url, params=None, tries=4):
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers={**UA, "Accept-Encoding": "gzip"}, timeout=300)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def tiger_attributes(level, refresh):
    """{geoid: attributes} for one TIGERweb layer (Puerto Rico), without geometry."""
    path = CACHE / f"tiger_{level}.json"
    if path.exists() and not refresh:
        return load_json(path)
    log(f"  TIGERweb layer {LAYER[level]} ({level})")
    r = get(f"{TIGER}/{LAYER[level]}/query", {"where": "STATE='72'", "outFields": ATTRS, "returnGeometry": "false", "f": "json", "resultRecordCount": 5000, "orderByFields": "OBJECTID"})
    rows = {f["attributes"]["GEOID"]: f["attributes"] for f in r.json()["features"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return rows


def barrio_polygons(refresh):
    """Full-resolution county subdivision polygons (the legal extent, water included): the only way to say which barrio a block is in."""
    path = CACHE / "tiger_barrio_geometry.json"
    if path.exists() and not refresh:
        return load_json(path)
    log("  TIGERweb layer 20 (county subdivision outlines, full resolution)")
    feats, offset = [], 0
    while True:
        r = get(f"{TIGER}/{LAYER['barrio']}/query", {"where": "STATE='72'", "outFields": "GEOID", "f": "geojson", "outSR": 4326, "geometryPrecision": 6, "resultOffset": offset, "resultRecordCount": 250, "orderByFields": "OBJECTID"})
        batch = r.json().get("features", [])
        feats.extend(batch)
        if len(batch) < 250:
            break
        offset += 250
    out = {f["properties"]["GEOID"]: f["geometry"] for f in feats}
    path.parent.mkdir(parents=True, exist_ok=True)   # a clean runner (the nightly job) has no cache/geo yet
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def cartographic(level, refresh):
    """GeoJSON features of a Census cartographic boundary file (500k, clipped to the shoreline): {GEOID: geometry}."""
    import shapefile   # pyshp, only the full build needs it
    path = CACHE / CB_FILE[level]
    if not path.exists() or refresh:
        log(f"  cartographic boundary file {CB_FILE[level]}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(get(CB + CB_FILE[level]).content)
    z = zipfile.ZipFile(path)
    base = next(n for n in z.namelist() if n.endswith(".shp"))[:-4]
    sf = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")), dbf=io.BytesIO(z.read(base + ".dbf")))
    names = [f[0] for f in sf.fields[1:]]
    out = {}
    for sr in sf.shapeRecords():
        rec = dict(zip(names, sr.record))
        out[str(rec["GEOID"])] = sr.shape.__geo_interface__
    return out


# ── Names ────────────────────────────────────────────────────────────────────

def region_id(name):
    """'Porta del Sol Norte' -> 'reg-sol-norte'; 'Porta Atlántico' -> 'reg-atlantico'."""
    s = norm(name)
    s = re.sub(r"^porta\s+(del\s+)?", "", s)
    return "reg-" + re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def tract_names(base):
    return f"Sector censal {base}", f"Census tract {base}"


def blockgroup_names(base, tract_base):
    return f"Grupo de bloques {base}, sector censal {tract_base}", f"Block group {base}, census tract {tract_base}"


# ── Build ────────────────────────────────────────────────────────────────────

def assign_blocks_to_barrios(blocks, polygons):
    """{block geoid: barrio geoid} by the block's internal point; the Census Bureau guarantees a block sits inside one county subdivision."""
    geoids = list(polygons)
    shapes = [shape(polygons[g]) for g in geoids]
    tree = STRtree(shapes)
    pts = [Point(r[4], r[5]) for r in blocks]
    hit_i, hit_t = tree.query(pts, predicate="within")
    owner = {}
    for i, t in zip(hit_i.tolist(), hit_t.tolist()):
        owner.setdefault(i, []).append(t)
    out, loose = {}, []
    for i, r in enumerate(blocks):
        cand = owner.get(i, [])
        if len(cand) == 1:
            out[r[0]] = geoids[cand[0]]
        else:
            loose.append((i, cand))
    # a point on a shared edge or just off a polygon: take the nearest polygon (the checks below show whether it mattered)
    for i, cand in loose:
        p = pts[i]
        pool = cand or [int(j) for j in tree.query(p.buffer(0.001))] or list(range(len(shapes)))
        best = min(pool, key=lambda j: shapes[j].distance(p))
        out[blocks[i][0]] = geoids[best]
    return out, len(loose)


def block_barrios(table, refresh=False, cache=None):
    """The barrio of every census block of `table` (a list aligned with table["rows"]), by the block's internal point.

    Worked out once from the Census Bureau's county subdivision outlines (about 8 MB, downloaded the first time) and kept in cache/geo/block_barrio.json with a
    digest of the block ids, so anything that needs it later (the exposure series, the nightly refresh) neither downloads nor places the blocks again. A different
    block list (another digest) is placed again."""
    rows = table["rows"]
    ids = [r[0] for r in rows]
    digest = hashlib.sha1("\n".join(ids).encode()).hexdigest()
    path = Path(cache or CACHE) / "block_barrio.json"
    if path.exists() and not refresh:
        c = load_json(path)
        if c.get("digest") == digest:
            return [c["barrios"][i] for i in c["index"]]
    owner, loose = assign_blocks_to_barrios(rows, barrio_polygons(refresh))
    barrio = [owner[i] for i in ids]
    names = sorted(set(barrio))
    where = {b: k for k, b in enumerate(names)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"digest": digest, "n": len(ids), "loose": loose, "barrios": names, "index": [where[b] for b in barrio]}, separators=(",", ":")), encoding="utf-8")
    log(f"  {len(ids):,} blocks placed in a barrio ({loose} needed the nearest-polygon rule)")
    return barrio


def compare(label, got, want, fields=("pop", "hu")):
    """The blocks must add up to the Census Bureau's own figure for every unit."""
    bad = []
    for gid, w in want.items():
        g = got.get(gid, {"pop": 0, "hu": 0})
        if any(g[f] != w[f] for f in fields):
            bad.append((gid, {f: g[f] for f in fields}, {f: w[f] for f in fields}))
    extra = set(got) - set(want)
    if bad or extra:
        raise SystemExit(f"geo: the blocks do not add up to the Census totals for {label}: {len(bad)} units differ (first: {bad[:3]}), {len(extra)} unknown ids ({sorted(extra)[:3]})")
    log(f"    {label}: {len(want):,} units, blocks add up exactly")


def build(refresh=False):
    import network   # the shared table of census blocks (also read by the transit coverage)
    log("Geography crosswalk")
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    table = network.load_block_table(ROOT / "cache" / "network", refresh)
    blocks = table["rows"]                                          # [geoid, pop, hu, land_m2, lon, lat]
    attrs = {lv: tiger_attributes(lv, refresh) for lv in ("municipio", "tract", "block-group", "barrio")}
    muni_fc = load_json(DATA / "municipios.geojson")
    muni_name = {str(f["properties"]["GEOID"]): f["properties"]["municipality"] for f in muni_fc["features"]}
    muni_region = {str(f["properties"]["GEOID"]): f["properties"]["region"] for f in muni_fc["features"]}
    if not all(muni_region.values()) or len(set(muni_region.values())) != 7:
        raise SystemExit(f"geo: municipios.geojson should give every municipio one of 7 regions; got {sorted(set(muni_region.values()))}")
    barrios_fc = load_json(DATA / "barrios.geojson")
    barrio_name = {f["properties"]["geoid"]: f["properties"]["barrio"] for f in barrios_fc["features"]}

    # ── blocks into every level ──
    owner = dict(zip((r[0] for r in blocks), block_barrios(table, refresh)))
    tot = {lv: defaultdict(lambda: {"pop": 0, "hu": 0, "blocks": 0}) for lv in ("municipio", "tract", "block-group", "barrio")}
    weights = defaultdict(lambda: {"pop": 0, "hu": 0, "blocks": 0})
    for geoid, pop, hu, land, lon, lat in blocks:
        b = owner[geoid]
        for lv, key in (("municipio", geoid[:5]), ("tract", geoid[:11]), ("block-group", geoid[:12]), ("barrio", b)):
            t = tot[lv][key]
            t["pop"] += pop
            t["hu"] += hu
            t["blocks"] += 1
        w = weights[(b, geoid[:11])]
        w["pop"] += pop
        w["hu"] += hu
        w["blocks"] += 1
    want = {lv: {g: {"pop": int(a["POP100"] or 0), "hu": int(a["HU100"] or 0)} for g, a in attrs[lv].items()} for lv in attrs}
    for lv in ("municipio", "tract", "block-group", "barrio"):
        compare(lv, tot[lv], want[lv])
    island_pop, island_hu = sum(r[1] for r in blocks), sum(r[2] for r in blocks)

    # ── units ──
    units = {lv: [] for lv in LEVEL_ORDER}
    km2 = lambda a: round(int(a["AREALAND"] or 0) / 1e6, 4)
    ll = lambda a: (round(float(a["INTPTLAT"]), 5), round(float(a["INTPTLON"]), 5))
    muni_geom = {str(f["properties"]["GEOID"]): shape(f["geometry"]) for f in muni_fc["features"]}
    rp = lambda g: (round(g.representative_point().y, 5), round(g.representative_point().x, 5))
    island_lat, island_lng = rp(unary_union(list(muni_geom.values())))
    units["island"].append(["72", None, "Puerto Rico", "Puerto Rico", norm("Puerto Rico"), round(sum(r[3] for r in blocks) / 1e6, 4), island_pop, island_hu, island_lat, island_lng])
    by_region = defaultdict(list)
    for g, r in muni_region.items():
        by_region[r].append(g)
    for r in sorted(by_region, key=lambda x: region_id(x)):
        members = by_region[r]
        lat, lng = rp(unary_union([muni_geom[g] for g in members]))
        units["region"].append([region_id(r), "72", r, r, norm(r), round(sum(int(attrs["municipio"][g]["AREALAND"] or 0) for g in members) / 1e6, 4), sum(tot["municipio"][g]["pop"] for g in members), sum(tot["municipio"][g]["hu"] for g in members), lat, lng])
    for g in sorted(attrs["municipio"]):
        a = attrs["municipio"][g]
        name = muni_name[g]
        units["municipio"].append([g, region_id(muni_region[g]), name, name, norm(name), km2(a), tot["municipio"][g]["pop"], tot["municipio"][g]["hu"], *ll(a)])
    for g in sorted(barrio_name):
        a = attrs["barrio"][g]
        if a["BASENAME"] != barrio_name[g]:
            raise SystemExit(f"geo: barrio {g} is '{barrio_name[g]}' in barrios.geojson and '{a['BASENAME']}' at the Census Bureau")
        units["barrio"].append([g, g[:5], barrio_name[g], barrio_name[g], norm(barrio_name[g]), km2(a), tot["barrio"][g]["pop"], tot["barrio"][g]["hu"], *ll(a)])
    land_barrios = {g for g, a in attrs["barrio"].items() if int(a["AREALAND"] or 0) > 0}
    if land_barrios != set(barrio_name):
        raise SystemExit(f"geo: the barrios of barrios.geojson ({len(barrio_name)}) are not the county subdivisions with land ({len(land_barrios)}): {sorted(land_barrios ^ set(barrio_name))[:5]}")
    for g in sorted(attrs["tract"]):
        a = attrs["tract"][g]
        es, en = tract_names(a["BASENAME"])
        units["tract"].append([g, g[:5], es, en, norm(es), km2(a), tot["tract"][g]["pop"], tot["tract"][g]["hu"], *ll(a)])
    for g in sorted(attrs["block-group"]):
        a = attrs["block-group"][g]
        tb = attrs["tract"][g[:11]]["BASENAME"]
        es, en = blockgroup_names(a["BASENAME"], tb)
        units["block-group"].append([g, g[:11], es, en, norm(es), km2(a), tot["block-group"][g]["pop"], tot["block-group"][g]["hu"], *ll(a)])

    # ── nesting: how many barrios cross a tract line ──
    per_barrio = defaultdict(list)
    for (b, t), w in weights.items():
        if w["pop"] or w["hu"]:
            per_barrio[b].append((t, w))
    span = {b: v for b, v in per_barrio.items() if len(v) > 1}
    stats = {"barrios_with_residents": len(per_barrio), "barrios_in_two_or_more_tracts": len(span),
             "share_of_barrios": round(len(span) / len(per_barrio), 3), "share_of_residents": round(sum(w["pop"] for v in span.values() for _, w in v) / island_pop, 3)}
    wrows = sorted([b, t, w["pop"], w["hu"], w["blocks"]] for (b, t), w in weights.items() if w["pop"] or w["hu"])
    levels = [
        {"id": "island", "digits": 2, "parent": None, "count": 1, "key": "state FIPS code", "name": {"es": "Isla", "en": "Island"}},
        {"id": "region", "digits": None, "parent": "island", "count": len(units["region"]), "key": "reg-<slug> (the Puerto Rico Tourism Company's tourism regions)", "name": {"es": "Región turística", "en": "Tourism region"},
         "note": "The only region scheme the observatory holds. It is a tourism scheme: replace or supplement it if a general planning region is adopted."},
        {"id": "municipio", "digits": 5, "parent": "region", "count": len(units["municipio"]), "key": "GEOID (state + county)", "name": {"es": "Municipio", "en": "Municipality"}},
        {"id": "barrio", "digits": 10, "parent": "municipio", "count": len(units["barrio"]), "key": "GEOID (state + county + county subdivision)", "name": {"es": "Barrio", "en": "Barrio"},
         "note": "Census county subdivisions with land. They do not nest in tracts: use weights.barrio_tract (or the Census Bureau's own barrio rows) to move numbers between the two."},
        {"id": "tract", "digits": 11, "parent": "municipio", "count": len(units["tract"]), "key": "GEOID (state + county + tract)", "name": {"es": "Sector censal", "en": "Census tract"}},
        {"id": "block-group", "digits": 12, "parent": "tract", "count": len(units["block-group"]), "key": "GEOID (tract + block group)", "name": {"es": "Grupo de bloques", "en": "Block group"}},
    ]
    crosswalk = {
        "version": VERSION, "built": date.today().isoformat(),
        "basis": "2020 Census geography and counts (TIGERweb 2020 layers and the 2020 block table). Land area is the Census Bureau's AREALAND. Residents are noise-injected below the island; housing units are exact at block level.",
        "levels": levels, "fields": UNIT_FIELDS,
        "units": units,
        "weights": {"barrio_tract": {"note": "Residents and housing units of the blocks in each barrio-and-tract pair (pairs with neither are left out). Share of a barrio's housing units in a tract = hu / sum of hu for that barrio.", "fields": WEIGHT_FIELDS, "rows": wrows}},
        "totals": {"pop": island_pop, "hu": island_hu, "blocks": len(blocks), "blocks_with_residents": sum(1 for r in blocks if r[1] > 0), "barrio_offshore_not_defined": len(attrs["barrio"]) - len(land_barrios)},
        "nesting": stats,
    }
    (OUT / "crosswalk.json").write_text(json.dumps(crosswalk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  crosswalk.json: {sum(len(v) for v in units.values()):,} units, {len(wrows):,} barrio-tract weights, {(OUT / 'crosswalk.json').stat().st_size / 1024:.0f} KB")
    log(f"  barrios in two or more tracts: {stats['barrios_in_two_or_more_tracts']} of {stats['barrios_with_residents']} ({stats['share_of_barrios'] * 100:.0f}%), holding {stats['share_of_residents'] * 100:.0f}% of residents")

    # ── display outlines ──
    for level, name in (("tract", "tracts.geojson"), ("block-group", "blockgroups.geojson")):
        geoms = cartographic(level, refresh)
        ids = {u[0] for u in units[level]}
        feats = []
        for g in sorted(geoms):
            if g not in ids:
                raise SystemExit(f"geo: {CB_FILE[level]} has {g}, which is not a {level} of the 2020 geography")
            feats.append({"type": "Feature", "properties": {"GEOID": g}, "geometry": round_geometry(geoms[g])})
        (OUT / name).write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")), encoding="utf-8")
        log(f"  {name}: {len(feats):,} of {len(ids):,} {level}s have an outline ({(OUT / name).stat().st_size / 1024:.0f} KB)")
    return crosswalk


def round_geometry(g, nd=5):
    def r(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": g["type"], "coordinates": r(g["coordinates"])}


# ── Checks on the published files (no network) ───────────────────────────────

def check(out=OUT):
    """Returns a list of problems in the published crosswalk and outlines."""
    P = []
    p = out / "crosswalk.json"
    if not p.exists():
        return [f"{p} is missing: run python geo.py"]
    cw = load_json(p)
    if cw.get("fields") != UNIT_FIELDS:
        P.append("crosswalk fields changed")
    units, ids = cw["units"], {}
    for lv in LEVEL_ORDER:
        rows = units.get(lv) or []
        if len(rows) != next(l["count"] for l in cw["levels"] if l["id"] == lv):
            P.append(f"{lv}: row count differs from the level's count")
        for r in rows:
            if len(r) != len(UNIT_FIELDS):
                P.append(f"{lv} {r[0]}: {len(r)} values, expected {len(UNIT_FIELDS)}")
            if r[0] in ids:
                P.append(f"duplicate id {r[0]}")
            ids[r[0]] = lv
    parent_level = {l["id"]: l["parent"] for l in cw["levels"]}
    for lv in LEVEL_ORDER[1:]:
        for r in units[lv]:
            if ids.get(r[1]) != parent_level[lv]:
                P.append(f"{lv} {r[0]}: parent {r[1]} is not a {parent_level[lv]}")
    # a parent's numbers are the sum of its children's (barrios and tracts both add up to a municipio; block groups to a tract)
    def sums(child, parent):
        s = defaultdict(lambda: [0, 0, 0.0, 0])
        for r in units[child]:
            s[r[1]][0] += r[6]
            s[r[1]][1] += r[7]
            s[r[1]][2] += r[5]
            s[r[1]][3] += 1
        for r in units[parent]:
            n_pop, n_hu, n_km2, n = s.get(r[0], [0, 0, 0.0, 0])
            if [r[6], r[7]] != [n_pop, n_hu]:
                P.append(f"{parent} {r[0]}: residents or housing units differ from the sum of its {child}s")
            if abs(r[5] - n_km2) > 0.00006 * n + 0.0001:     # areas are rounded to 0.0001 km2 (100 m2) each
                P.append(f"{parent} {r[0]}: land area {r[5]} km2 differs from the sum of its {child}s ({n_km2:.4f})")
        for r in units[child]:
            if not (r[2] and r[3] and r[4] == norm(r[2])):
                P.append(f"{child} {r[0]}: names or normalised name missing or inconsistent")
    for child, parent in (("region", "island"), ("municipio", "region"), ("barrio", "municipio"), ("tract", "municipio"), ("block-group", "tract")):
        sums(child, parent)
    w = cw["weights"]["barrio_tract"]["rows"]
    sb, st = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for b, t, pp, hh, n in w:
        if ids.get(b) != "barrio" or ids.get(t) != "tract":
            P.append(f"weight {b}/{t}: not a barrio and a tract")
        sb[b][0] += pp
        sb[b][1] += hh
        st[t][0] += pp
        st[t][1] += hh
    for r in units["barrio"]:
        if sb.get(r[0], [0, 0]) != [r[6], r[7]]:
            P.append(f"barrio {r[0]}: its weights do not add up to its residents and housing units")
    for r in units["tract"]:
        if st.get(r[0], [0, 0]) != [r[6], r[7]]:
            P.append(f"tract {r[0]}: its weights do not add up to its residents and housing units")
    for name, lv in (("tracts.geojson", "tract"), ("blockgroups.geojson", "block-group")):
        q = out / name
        if not q.exists():
            P.append(f"{name} is missing")
            continue
        got = [f["properties"]["GEOID"] for f in load_json(q)["features"]]
        bad = [g for g in got if ids.get(g) != lv]
        if bad:
            P.append(f"{name}: {len(bad)} outlines are not {lv}s of the crosswalk (first {bad[:3]})")
        if len(set(got)) != len(got):
            P.append(f"{name}: repeated ids")
    return P


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        problems = check()
        for p in problems:
            print("  ERROR", p)
        print(f"geo: {len(problems)} problems")
        return 1 if problems else 0
    build("--refresh" in argv)
    problems = check()
    for p in problems:
        print("  ERROR", p)
    if problems:
        raise SystemExit(f"geo: the files just written fail their own checks ({len(problems)} problems)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
