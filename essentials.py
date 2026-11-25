"""Road distance to essentials for the PR Data Observatory: how far residents live, along the roads, from the nearest supermarket, pharmacy, bank or
cooperativa, public library and fire or EMS station, by barrio and municipio. HANDOFF decision 107, step 6 (row derived-access-essentials);
docs/essentials.md. An estimate (decision 107 b): a road-network model, labeled so, with a check and a range.

    python essentials.py --refresh   # read the newest Overture places and OpenStreetMap extract into cache/essentials/points.json, then build
    python essentials.py             # build site/data/essentials_series.json and essentials_barrio.json from the cached points (no network)
    python essentials.py --check     # rebuild from the cache and exit 1 when a published file is not what it gives (nothing written)

What is measured from what:
  supermarket   Overture places (newest release, confidence 0.5 or more) of a grocery or warehouse-club category whose name is a supermarket's: "supermercado"
                or "supermarket", or one of the island's supermarket chains (SUPERMARKET_NAMES; "Pueblo" and "Amigo" only at the start of the name). A place
                called "colmado", "mini market" or "to go" is a corner store and is left out. Walmart, Costco and Sam's Club count in a store category
                (department store, superstore), not their pharmacy, optician or money-transfer listings.
  pharmacy      Overture places of the categories pharmacy and drugstore (confidence 0.5 or more).
  bank          Overture places of the categories bank, credit union and bank or credit union (confidence 0.5 or more): banks and cooperativas. ATMs are not.
  library       the libraries the map draws (libraries.geojson: USAC's E-Rate list of public libraries, facilities.py). In Puerto Rico the list also holds
                community, church and university libraries and municipal technology centers (centros tecnológicos), so it counts more places than the
                municipal public libraries alone; the label says "a library", not "a public library".
  grocery       any food store: every Overture place of a grocery category (colmados included) and the supermarkets above. Small towns often have no
                supermarket by the rule, only colmados and "super colmados"; this measure shows the difference.
  fire          the fire and EMS stations the map draws (fire_stations.geojson: USGS, facilities.py), and OpenStreetMap's fire stations with no USGS point
                within 300 m (USGS lacks Jayuya's).
OpenStreetMap (Geofabrik's Puerto Rico extract) is the check and fills the gaps: its supermarkets, pharmacies and banks with no Overture point of the same kind
within 300 m are added (combined()). The notes keep the island figures from Overture alone as the other end of the range.

Method, as care_access.py and conditions.py measure distance to care: one multi-source shortest-path search over the road graph (site/data/roads.bin) from every
point of a kind, in both directions of every road (one-way streets read as two-way: a distance, not a driving route). Each 2020 Census block with residents is
snapped to the nearest road joined to the network within 2 km; its distance is the road distance to the nearest point of the kind, plus the straight lines from
the block point and from the place to their roads. A barrio's and a municipio's figure is the average over their residents (each block weighted by its 2020
residents), so it describes where people live, not the area. Blocks with no road within 2 km, or no road path to any point of the kind (Vieques and Culebra
when they have none), are left out and counted in the notes.

The points of shops are a directory, not an inspection: a place that closed may still be listed, and one that opened may be missing. A missing place makes a
distance longer; a closed one makes it shorter. The check and the range in the notes say how much that moves the figures.
"""

import argparse
import ast
import json
import math
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "essentials"
POINTS = CACHE / "points.json"
OVERTURE = CACHE / "overture_pr_places.geojson"
OSM_PBF = CACHE / "osm" / "puerto-rico-latest.osm.pbf"
OUT_SERIES = DATA / "essentials_series.json"
OUT_BARRIO = DATA / "essentials_barrio.json"
BBOX = (-67.97, 17.85, -65.2, 18.57)
PBF_URL = "https://download.geofabrik.de/north-america/us/puerto-rico-latest.osm.pbf"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
MIN_CONF = 0.5
FAR_KM = 5.0          # the share of residents farther than this by road from a supermarket
MATCH_M = 300         # an OpenStreetMap place "has an Overture point near" within this distance (the check)
KINDS = ("supermarket", "grocery", "pharmacy", "bank", "library", "fire")
G = "Communities · Road distance to essentials (estimate)"

GROCERY = {"grocery_store", "warehouse_club_store", "organic_grocery_store", "supermarket", "hypermarket"}
PHARMACY = {"pharmacy", "drugstore"}
BANK = {"bank", "credit_union", "bank_or_credit_union"}
SUPERMARKET_NAMES = re.compile(
    r"\bsuper ?mercados?\b|\bsupermarket|\bsuper ?max\b|\becono\b|\bselectos\b|^(supermercados? )?pueblo\b|^(supermercados? )?amigo\b|\bmr\.? ?special\b|\bralph|\bfamcoop\b|\bagranel\b|"
    r"\bcentro ahorros\b|\bplaza loiza\b|\bmi gente\b|\bmega fresh\b|\bfresh ?mart\b|\bhatillo kash\b|\bnapo\b|\bpitusa\b|\bsuper ahorros\b|"
    r"\bp ?& ?g\b|\bcada dia\b|\bsuper ?descuentos\b|\bwalmart\b|\bcostco\b|\bsam'?s club\b")
ANY_CATEGORY = re.compile(r"\bwalmart\b|\bcostco\b|\bsam'?s club\b")
STORE = GROCERY | {"department_store", "superstore", "discount_store", "wholesale_grocer", "shopping"}   # Walmart, Costco and Sam's Club count in these (not their pharmacy, optician or money-transfer listings)
CORNER = re.compile(r"\bcolmado|\bmini ?market|\bto go\b|\bgasolinera|\bcafetin\b")

SOURCES = {
    "overture": {"name": "Overture Maps Foundation, Places theme", "url": "https://docs.overturemaps.org/guides/places/",
                 "license": "CDLA Permissive 2.0 (some records ODbL); attribution", "note": "Supermarkets, pharmacies and banks or cooperativas, as points; only the distances are published."},
    "usac_erate": {"name": "USAC E-Rate open data: public libraries", "url": "https://opendata.usac.org/",
                   "license": "Open data (USAC terms of use)", "note": "The public libraries the map draws (libraries.geojson)."},
    "usgs_structures": {"name": "USGS National Structures Dataset: fire stations and EMS", "url": "https://www.usgs.gov/programs/national-geospatial-program/national-map",
                        "license": "US Government work (no US copyright)", "note": "The fire and EMS stations the map draws (fire_stations.geojson)."},
    "osm": {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "license": "ODbL 1.0",
            "note": "The road graph (roads.bin) the distances follow, and the check of the shop points."},
    "census_tiger": {"name": "US Census Bureau, 2020 Census blocks and barrio outlines", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Where residents live: each block's 2020 residents and internal point."},
}


def log(*a):
    print(*a, flush=True)


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def _lit(v):
    if isinstance(v, (dict, list)) or v is None:
        return v or {}
    try:
        return ast.literal_eval(v)
    except (ValueError, SyntaxError):
        try:
            return json.loads(v)
        except ValueError:
            return {}


def classify(category, name):
    """The essential an Overture place counts as ('supermarket', 'pharmacy', 'bank') or None, by its category and name."""
    n = norm(name)
    if ANY_CATEGORY.search(n) and category in STORE:
        return "supermarket"
    if category in GROCERY or (category == "convenience_store" and re.search(r"\bsuper ?mercados?\b", n)):   # Overture files a few supermarkets as convenience stores
        return "supermarket" if SUPERMARKET_NAMES.search(n) and not CORNER.search(n) else None
    if category in PHARMACY:
        return "pharmacy"
    if category in BANK:
        return "bank"
    return None


def overture_points(path=OVERTURE):
    """[[kind, lon, lat]] from an Overture places GeoJSON (the 2026-10 layout: taxonomy.primary; older files: categories.primary)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out, seen = [], set()
    for f in d["features"]:
        p = f["properties"]
        if float(p.get("confidence") or 0) < MIN_CONF:
            continue
        cat = (_lit(p.get("taxonomy")) or {}).get("primary") or (_lit(p.get("categories")) or {}).get("primary")
        kind = classify(cat, (_lit(p.get("names")) or {}).get("primary") or "")
        kinds = ([kind] if kind else []) + (["grocery"] if kind == "supermarket" or cat in GROCERY else [])   # any food store: supermarkets and colmados
        lon, lat = f["geometry"]["coordinates"][:2]
        for k in kinds:
            key = (k, round(lon, 4), round(lat, 4))   # the same place listed twice (about 10 m apart or less)
            if key in seen:
                continue
            seen.add(key)
            out.append([k, round(lon, 5), round(lat, 5)])
    return out, d


def osm_points():
    """[[kind, lon, lat]] of OpenStreetMap supermarkets, pharmacies and banks, for the check (needs `osmium`)."""
    import osmium
    want = {("shop", "supermarket"): "supermarket", ("shop", "wholesale"): "supermarket", ("amenity", "pharmacy"): "pharmacy", ("shop", "chemist"): "pharmacy", ("amenity", "bank"): "bank",
            ("amenity", "fire_station"): "fire"}
    out = []

    class H(osmium.SimpleHandler):
        def take(self, tags, lon, lat):
            for (k, v), kind in want.items():
                if tags.get(k) == v:
                    out.append([kind, round(lon, 5), round(lat, 5)])
                    return

        def node(self, n):
            if n.location.valid():
                self.take(n.tags, n.location.lon, n.location.lat)

        def area(self, a):
            try:
                xs = [(nr.lon, nr.lat) for ring in a.outer_rings() for nr in ring]
            except Exception:   # noqa: BLE001  an area osmium cannot assemble
                return
            if xs:
                self.take(a.tags, sum(x for x, _ in xs) / len(xs), sum(y for _, y in xs) / len(xs))
    import os
    here = os.getcwd()
    os.chdir(OSM_PBF.parent)   # libosmium cannot open paths with accented characters on Windows (roads.py does the same)
    try:
        H().apply_file(OSM_PBF.name, locations=True)
    finally:
        os.chdir(here)
    return out


def refresh():
    """Download the newest Overture places and OpenStreetMap extract and write cache/essentials/points.json (the points and the release they came from)."""
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable).parent / "overturemaps.exe"
    cmd = [str(exe) if exe.exists() else "overturemaps", "download", f"--bbox={','.join(map(str, BBOX))}", "-f", "geojson", "--type=place", "-o", str(OVERTURE)]
    log("  Overture places (about 130 MB)")
    subprocess.run(cmd, check=True)
    (CACHE / "osm").mkdir(exist_ok=True)
    log("  OpenStreetMap extract (about 75 MB)")
    with requests.get(PBF_URL, headers=UA, stream=True, timeout=600) as r:
        r.raise_for_status()
        osm_file = r.url.rsplit("/", 1)[-1]
        with open(OSM_PBF, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    write_points(osm_file=osm_file)


def write_points(osm_file=None):
    pts, raw = overture_points()
    state = json.loads((OVERTURE.parent / (OVERTURE.name + ".state")).read_text(encoding="utf-8")) if (OVERTURE.parent / (OVERTURE.name + ".state")).exists() else {}
    try:
        osm = osm_points()
    except ImportError:   # the build's environment has no osmium: keep the check points of the last run
        old = json.loads(POINTS.read_text(encoding="utf-8")) if POINTS.exists() else {}
        osm, osm_file = old.get("osm", []), osm_file or old.get("osm_file")
        log(f"  no osmium: the OpenStreetMap check keeps the {len(osm)} points of the last run (pip install osmium to read the extract again)")
    doc = {"overture_release": state.get("last_release"), "overture_places": len(raw["features"]), "osm_file": osm_file, "points": pts, "osm": osm}
    POINTS.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  wrote {POINTS.name}: " + ", ".join(f"{k} {sum(1 for p in pts if p[0] == k)}" for k in ("supermarket", "pharmacy", "bank")) + f"; OpenStreetMap {len(osm)}")


def facility_points(name):
    return [[round(f["geometry"]["coordinates"][0], 5), round(f["geometry"]["coordinates"][1], 5)] for f in json.loads((DATA / name).read_text(encoding="utf-8"))["features"]]


def haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def matched_share(osm, ours, m=MATCH_M):
    """The share of `osm` points ([lon, lat]) with a point of `ours` within m meters."""
    if not osm:
        return None
    cell = 0.01
    grid = {}
    for x, y in ours:
        grid.setdefault((int(x / cell), int(y / cell)), []).append((x, y))
    hit = 0
    for x, y in osm:
        cx, cy = int(x / cell), int(y / cell)
        if any(haversine_m(x, y, a, b) <= m for dx in (-1, 0, 1) for dy in (-1, 0, 1) for a, b in grid.get((cx + dx, cy + dy), ())):
            hit += 1
    return round(hit / len(osm) * 100, 1)


# ── distances ────────────────────────────────────────────────────────────────

def distances(kinds_points, blocks, R=None):
    """{kind: [road km per block, None where it cannot be measured]} for `blocks` [(geoid, residents, lon, lat)], and notes."""
    import care_access
    import roads
    if R is None:
        R = roads.Roads(DATA / "roads.bin")
        for i in range(len(R.eu)):   # both directions of a one-way road: a distance, not a driving route (care_access.py)
            if R.oneway[i]:
                R.adj[int(R.ev[i])].append((int(R.eu[i]), i, False))
    out, notes = {}, {}
    base = [R.snap(lon, lat, care_access.SNAP_M) for _, _, lon, lat in blocks]   # each block's nearest road, worked out once
    for kind, pts in kinds_points.items():
        snapped = [R.snap(lon, lat, care_access.SNAP_M) for lon, lat in pts]
        src = [(s, s["dist"]) for s in snapped if s]
        km = care_access.search(R, src, lambda e, m: m)
        # the nearest road when it reaches a place of this kind, else the nearest road that does (per kind: Vieques has a fire station and no supermarket)
        snaps = [b if b and (int(R.eu[b["edge"]]) in km or int(R.ev[b["edge"]]) in km) else care_access.snap_reachable(R, lon, lat, km)
                 for b, (_, _, lon, lat) in zip(base, blocks)]
        vals = []
        for s in snaps:
            if not s:
                vals.append(None)
                continue
            e, L = s["edge"], R.cum[s["edge"]][-1]
            u, v = int(R.eu[e]), int(R.ev[e])
            dk = s["dist"] + min(km.get(u, 1e18) + s["along"], km.get(v, 1e18) + L - s["along"])
            vals.append(None if dk >= 1e17 else dk / 1000)
        out[kind] = vals
        notes[kind] = {"points": len(pts), "points_on_a_road": len(src)}
    return out, notes


def roll_up(blocks, unit_of, n, vals):
    """(residents-weighted mean km per unit, residents measured per unit) for one kind; unit_of: the unit index of each block (-1: none)."""
    s, w = [0.0] * n, [0] * n
    for (_, pop, _, _), u, v in zip(blocks, unit_of, vals):
        if u >= 0 and v is not None and pop > 0:
            s[u] += pop * v
            w[u] += pop
    return [round(s[i] / w[i], 2) if w[i] else None for i in range(n)], w


def share_far(blocks, unit_of, n, vals, far=FAR_KM):
    s, w = [0] * n, [0] * n
    for (_, pop, _, _), u, v in zip(blocks, unit_of, vals):
        if u >= 0 and v is not None and pop > 0:
            w[u] += pop
            s[u] += pop if v > far else 0
    return [round(s[i] / w[i] * 100, 1) if w[i] else None for i in range(n)]


LABEL = {"supermarket": "a supermarket", "grocery": "a food store (supermarket or colmado)", "pharmacy": "a pharmacy", "bank": "a bank or cooperativa", "library": "a library", "fire": "a fire or EMS station"}
SRC = {"supermarket": ["overture"], "grocery": ["overture"], "pharmacy": ["overture"], "bank": ["overture"], "library": ["usac_erate"], "fire": ["usgs_structures"]}
KEY = {"supermarket": "ess_supermarket_km", "grocery": "ess_grocery_km", "pharmacy": "ess_pharmacy_km", "bank": "ess_bank_km", "library": "ess_library_km", "fire": "ess_fire_km"}


def assemble(kinds_points, blocks, block_muni, block_barrio, muni_ids, muni_names, barrio_ids, pts_doc, R=None):
    year = date.today().year
    dist, dn = distances(kinds_points, blocks, R)
    mi = {m: i for i, m in enumerate(muni_ids)}
    bi = {b: i for i, b in enumerate(barrio_ids)}
    um = [mi.get(m, -1) for m in block_muni]
    ub = [bi.get(b, -1) for b in block_barrio]
    isl = [0] * len(blocks)
    vars_, bvars, notes = [], [], {"kinds": {}}
    total = sum(p for _, p, _, _ in blocks)
    for kind in KINDS:
        v = dist[kind]
        m, mw = roll_up(blocks, um, len(muni_ids), v)
        pr, pw = roll_up(blocks, isl, 1, v)
        b, _ = roll_up(blocks, ub, len(barrio_ids), v)
        left = total - pw[0]
        km_sorted = sorted((x, p) for x, (_, p, _, _) in zip(v, blocks) if x is not None)
        half = sum(p for _, p in km_sorted) / 2
        acc, median = 0, None
        for x, p in km_sorted:
            acc += p
            if acc >= half:
                median = round(x, 2)
                break
        notes["kinds"][kind] = {**dn[kind], "island_mean_km": pr[0], "island_median_km": median, "residents_not_measured": left,
                                "not_measured_by_municipio": {muni_ids[i]: sum(p for (_, p, _, _), u, x in zip(blocks, um, v) if u == i and x is None) for i in range(len(muni_ids))
                                                              if any(u == i and x is None and p > 0 for (_, p, _, _), u, x in zip(blocks, um, v))}}
        defin = (f"The average road distance from where the area's residents live to the nearest {LABEL[kind][2:] if LABEL[kind].startswith('a ') else LABEL[kind]}, "
                 f"in kilometers, each 2020 Census block weighted by its residents. " + DEF_TAIL[kind] + COMMON)
        vars_.append({"key": KEY[kind], "group": G, "label": f"Road distance to {LABEL[kind]} (estimate, km)", "unit": "km", "d": 1, "type": "rate",
                      "sources": SRC[kind] + ["osm", "census_tiger"], "ref": REF, "definition": defin, "family": "essentials", "counted": False, "noPerHU": True,
                      "barrioFile": OUT_BARRIO.name, "estimate": True, "years": {str(year): [*m, pr[0]]}})
        bvars.append({"key": KEY[kind], "years": {str(year): b}})
    v = dist["supermarket"]
    far_m = share_far(blocks, um, len(muni_ids), v)
    far_pr = share_far(blocks, isl, 1, v)
    far_b = share_far(blocks, ub, len(barrio_ids), v)
    vars_.append({"key": "ess_supermarket_far_pct", "group": G, "label": f"Residents more than {FAR_KM:g} km by road from a supermarket (estimate, %)", "unit": "%", "d": 1,
                  "type": "rate", "sources": ["overture", "osm", "census_tiger"], "ref": REF,
                  "definition": (f"The share of the area's residents (2020 Census) who live more than {FAR_KM:g} km by road from the nearest supermarket. " + DEF_TAIL["supermarket"] + COMMON),
                  "family": "essentials", "counted": False, "noPerHU": True, "barrioFile": OUT_BARRIO.name, "estimate": True, "years": {str(year): [*far_m, far_pr[0]]}})
    bvars.append({"key": "ess_supermarket_far_pct", "years": {str(year): far_b}})
    osm = pts_doc.get("osm") or []
    notes["check"] = {k: {"osm_points": sum(1 for p in osm if p[0] == k), "osm_with_an_overture_point_within_m": MATCH_M,
                          "share_pct": matched_share([p[1:] for p in osm if p[0] == k], [p[1:] for p in pts_doc["points"] if p[0] == k])}
                      for k in ("supermarket", "pharmacy", "bank")}
    if pts_doc.get("osm"):   # the range: the same distances from Overture's points alone (fewer places, so longer distances)
        alone = {k: [p[1:] for p in pts_doc["points"] if p[0] == k] for k in ("supermarket", "grocery", "pharmacy", "bank")}
        ad, _ = distances(alone, blocks, R)
        for k, v in ad.items():
            pr, _ = roll_up(blocks, isl, 1, v)
            notes["kinds"][k]["overture_alone"] = {"points": len(alone[k]), "island_mean_km": pr[0], "far_pct": share_far(blocks, isl, 1, v)[0] if k == "supermarket" else None}
            notes["kinds"][k]["osm_added"] = len(kinds_points[k]) - len(alone[k])
    notes.update({"overture_release": pts_doc.get("overture_release"), "osm_file": pts_doc.get("osm_file"), "min_confidence": MIN_CONF, "far_km": FAR_KM,
                  "blocks_with_residents": sum(1 for _, p, _, _ in blocks if p > 0), "residents": total})
    series = {"as_of": date.today().isoformat(), "years": [year], "geo": {"ids": [*muni_ids, "72"], "names": [*muni_names, "Puerto Rico"]}, "vars": vars_, "sources": SOURCES, "notes": notes}
    barrio = {"level": "barrio", "years": [year], "geo": {"ids": barrio_ids}, "vars": bvars,
              "notes": {"areas": len(barrio_ids), "source": "essentials.py; the municipio values, the method and the check are in essentials_series.json"}}
    return series, barrio, dist


REF = ("Estimated by the observatory: road distance over the OpenStreetMap road graph (roads.bin) from each 2020 Census block with residents to the nearest point "
       "of the kind, averaged over residents (essentials.py)")
COMMON = (" An estimate: distance along the mapped roads in either direction, not a driving route or a time. The places come from a directory, so a shop that "
          "closed may still be counted and one that opened may be missing. Blocks with no road within 2 km, or no road to any place of the kind, are left out.")
DEF_TAIL = {
    "supermarket": ("Supermarkets are Overture's grocery and warehouse-club places whose name is a supermarket's (\"supermercado\", \"supermarket\" or a supermarket "
                    "chain), plus Walmart, Costco and Sam's Club, and OpenStreetMap's supermarkets that Overture lacks; corner stores (colmados) are left out."),
    "pharmacy": "Pharmacies are Overture's places in the pharmacy and drugstore categories, and OpenStreetMap's pharmacies that Overture lacks.",
    "bank": "Banks and cooperativas are Overture's places in the bank and credit union categories, and OpenStreetMap's banks that Overture lacks; ATMs are not counted.",
    "library": ("Libraries are the ones the map draws: USAC's E-Rate list of public libraries, which in Puerto Rico also holds community, church and university "
                "libraries and municipal technology centers, so it counts more places than the municipal libraries alone."),
    "fire": "Stations are the fire and EMS stations the map draws (USGS), and OpenStreetMap's fire stations that USGS lacks (Jayuya's, on 2026-11-18).",
    "grocery": ("Food stores are every place in Overture's grocery categories, colmados (corner stores) included, and the supermarkets above. In small towns "
                "the nearest food store is often a colmado or a 'super colmado' that the supermarket rule leaves out."),
}


def combined(pts_doc, m=MATCH_M):
    """{kind: [[lon, lat]]} for the shops: every Overture point, and each OpenStreetMap point with no Overture point of its kind within m meters (the places
    Overture misses: 13% to 24% of OpenStreetMap's on 2026-11-18, and the only pharmacy of Vieques and supermarkets of Culebra)."""
    out = {}
    for k in ("supermarket", "pharmacy", "bank"):
        ours = [p[1:] for p in pts_doc["points"] if p[0] == k]
        extra = [p[1:] for p in (pts_doc.get("osm") or []) if p[0] == k and matched_share([p[1:]], ours, m) == 0]
        out[k] = ours + extra
    grocery = [p[1:] for p in pts_doc["points"] if p[0] == "grocery"]
    have = {tuple(x) for x in grocery}
    out["grocery"] = grocery + [x for x in out["supermarket"] if tuple(x) not in have]   # every supermarket is a food store, OpenStreetMap's included
    return out


def inputs():
    import geo
    import network
    pts_doc = json.loads(POINTS.read_text(encoding="utf-8"))
    kp = combined(pts_doc)
    kp["library"] = facility_points("libraries.geojson")
    usgs = facility_points("fire_stations.geojson")
    kp["fire"] = usgs + [p[1:] for p in (pts_doc.get("osm") or []) if p[0] == "fire" and matched_share([p[1:]], usgs) == 0]   # stations USGS lacks
    cache = ROOT / "cache"
    table = network.load_block_table(cache / "network", False)
    barrio_of = geo.block_barrios(table, False, cache / "geo")
    blocks = [(r[0], r[1], r[4], r[5]) for r in table["rows"]]
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    return kp, blocks, [b[0][:5] for b in blocks], barrio_of, [r[0] for r in muni], [r[2] for r in muni], [r[0] for r in cw["units"]["barrio"]], pts_doc


def build(check=False):
    if not POINTS.exists():
        log(f"essentials: {POINTS} is not in the cache (python essentials.py --refresh makes it)")
        return 1 if check else 0
    series, barrio, _ = assemble(*inputs())
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
            same = old is not None and strip(old) == strip(json.loads(json.dumps(d)))
            log(f"  {path.name}: {'matches' if same else 'DIFFERS'}")
            status |= 0 if same else 1
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        log(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")
    if not check:
        for k, n in series["notes"]["kinds"].items():
            log(f"  {k:12s} points {n['points']:5d}  island mean {n['island_mean_km']} km, median {n['island_median_km']} km, not measured {n['residents_not_measured']:,}")
        log("  check: " + ", ".join(f"{k} {v['share_pct']}% of {v['osm_points']} OpenStreetMap points have an Overture point within {MATCH_M} m" for k, v in series["notes"]["check"].items()))
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="download the newest Overture places and OpenStreetMap extract first")
    ap.add_argument("--points", action="store_true", help="rewrite cache/essentials/points.json from the files already in the cache")
    ap.add_argument("--check", action="store_true", help="rebuild from the cache and compare with the published files")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if a.refresh:
        refresh()
    elif a.points:
        write_points()
    return build(a.check)


if __name__ == "__main__":
    raise SystemExit(main())
