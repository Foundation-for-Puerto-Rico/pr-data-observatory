"""Place-name index for the PR Data Observatory: what the search boxes and the route planner look names up in.

    python gazetteer.py        # rebuild site/data/gazetteer.json from the OpenStreetMap extract (reads the file roads.py downloads)

One compact file with everything that has a name and a place on the map, apart from the tourism listings (the pages already
hold those): the 78 municipalities, barrios, towns, villages and neighborhoods, named roads and PR route numbers (one entry
per road per municipality), and civic landmarks (hospitals, schools, town halls, terminals, parks, beaches, peaks, ...).
The browser searches it locally; nothing a visitor types leaves the page.

Layout: {"munis": [names], "kinds": [labels], "items": [[name, lat, lng, kind, muni, extra], ...]} where extra is a road's
local name for a route number, or the place's own subtype note. Source data: OpenStreetMap (ODbL), US Census 2020 boundaries.
"""

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

import roads

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "data"

KINDS = ["municipio", "town", "village", "barrio", "neighborhood", "road", "route", "hospital", "school", "university", "civic", "transport",
         "park", "beach", "peak", "water", "landmark", "airport", "mall"]
KIND = {k: i for i, k in enumerate(KINDS)}

PLACE_KIND = {"city": "town", "town": "town", "village": "village", "hamlet": "village", "suburb": "neighborhood", "neighbourhood": "neighborhood",
              "quarter": "neighborhood", "locality": "neighborhood", "island": "water", "islet": "water"}
ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "pedestrian"}
AMENITY = {"hospital": "hospital", "clinic": "hospital", "school": "school", "college": "university", "university": "university",
           "townhall": "civic", "courthouse": "civic", "police": "civic", "fire_station": "civic", "library": "civic", "community_centre": "civic",
           "post_office": "civic", "bus_station": "transport", "ferry_terminal": "transport", "marketplace": "mall", "theatre": "landmark", "arts_centre": "landmark"}
LEISURE = {"park": "park", "stadium": "park", "marina": "water", "nature_reserve": "park", "sports_centre": "park", "golf_course": "park"}
NATURAL = {"beach": "beach", "peak": "peak", "bay": "water", "cape": "water", "cave_entrance": "landmark", "volcano": "peak"}
HISTORIC = {"castle", "fort", "monument", "memorial", "ruins", "lighthouse", "archaeological_site", "building", "church"}


def norm(s):
    return re.sub(r"[̀-ͯ]", "", unicodedata.normalize("NFD", s or "")).lower().strip()


def clean_name(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def route_ref(tags):
    """'PR-52' from ref tags such as 'PR 52', 'PR-52;PR-1'; the first PR route number only."""
    ref = tags.get("ref") or ""
    m = re.search(r"\bPR[\s-]*(\d{1,4})(?:[\s-]*([A-Z]))?\b", ref.upper())
    return f"PR-{m.group(1)}{m.group(2) or ''}" if m else None


def centre(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def read(pbf: Path):
    import osmium
    here = os.getcwd()
    os.chdir(pbf.parent)   # libosmium cannot open an accented path on Windows, so open it by its bare name
    try:
        keys = ("place", "highway", "amenity", "leisure", "natural", "historic", "aeroway", "shop")
        fp = osmium.FileProcessor(pbf.name, osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(osmium.filter.KeyFilter(*keys))
        points, ways = [], []   # points: (name, lon, lat, kind, note); ways: (name, ref, class, lon, lat, meters)
        for o in fp:
            t = o.tags
            name = clean_name(t.get("name"))
            if o.is_node():
                if not o.location.valid():
                    continue
                lon, lat = o.location.lon, o.location.lat
                if "place" in t and name and t["place"] in PLACE_KIND:
                    points.append((name, lon, lat, PLACE_KIND[t["place"]], t["place"]))
                elif name and t.get("amenity") in AMENITY:
                    points.append((name, lon, lat, AMENITY[t["amenity"]], ""))
                elif name and t.get("natural") in NATURAL:
                    points.append((name, lon, lat, NATURAL[t["natural"]], ""))
                elif name and t.get("historic") in HISTORIC:
                    points.append((name, lon, lat, "landmark", ""))
                elif name and t.get("aeroway") in ("aerodrome", "terminal"):
                    points.append((name, lon, lat, "airport", ""))
                elif name and t.get("leisure") in LEISURE:
                    points.append((name, lon, lat, LEISURE[t["leisure"]], ""))
                elif name and t.get("shop") == "mall":
                    points.append((name, lon, lat, "mall", ""))
            elif o.is_way():
                pts = [(n.lon, n.lat) for n in o.nodes if n.location.valid()]
                if len(pts) < 2:
                    continue
                hw = t.get("highway")
                if hw in ROAD_CLASSES:
                    ref = route_ref(t)
                    if not name and not ref:
                        continue
                    m = len(pts) // 2
                    metres = sum(roads.hav(a[1], a[0], b[1], b[0]) for a, b in zip(pts, pts[1:]))
                    ways.append((name, ref, hw, pts[m][0], pts[m][1], metres))
                    continue
                if not name:
                    continue
                c = centre(pts)   # areas: hospitals, schools, parks, beaches, terminals, airports
                kind = AMENITY.get(t.get("amenity")) or LEISURE.get(t.get("leisure")) or NATURAL.get(t.get("natural")) or ("airport" if t.get("aeroway") in ("aerodrome", "terminal") else None) or ("mall" if t.get("shop") == "mall" else None) or ("landmark" if t.get("historic") in HISTORIC else None)
                if kind:
                    points.append((name, c[0], c[1], kind, ""))
    finally:
        os.chdir(here)
    return points, ways


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not roads.PBF.exists():
        sys.exit("Run `python roads.py` first: it downloads the OpenStreetMap extract this reads.")
    print("  reading the OpenStreetMap extract")
    points, ways = read(roads.PBF)
    print(f"    {len(points):,} named points, {len(ways):,} road ways")

    muni_fc = json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))
    names, geoms = [], []
    for f in muni_fc["features"]:
        n = f["properties"].get("municipality")
        if n:
            names.append(n)
            geoms.append(shape(f["geometry"]))
    tree = STRtree(geoms)
    muni_index = {n: i for i, n in enumerate(sorted(names, key=norm))}
    sorted_names = sorted(names, key=norm)

    def muni_of(lon, lat):
        hit = tree.query(Point(lon, lat), predicate="within")
        if len(hit):
            return muni_index[names[hit[0]]]
        d = [(g.distance(Point(lon, lat)), i) for i, g in enumerate(geoms)]
        d.sort()
        return muni_index[names[d[0][1]]] if d and d[0][0] < 0.02 else -1   # up to about 2 km offshore (piers, cays), else not in a municipality

    items, seen = [], set()

    def add(name, lat, lng, kind, m, extra=""):
        key = (norm(name), kind, round(lat, 3), round(lng, 3))
        if key in seen or m < 0:
            return
        seen.add(key)
        items.append([name, round(lat, 5), round(lng, 5), KIND[kind], m, extra] if extra else [name, round(lat, 5), round(lng, 5), KIND[kind], m])

    # municipalities: the town of the same name when OpenStreetMap has one (its center is where people mean), else a point inside the polygon
    town_at = {}
    for name, lon, lat, kind, note in points:
        if kind == "town":
            town_at.setdefault(norm(name), []).append((lon, lat))
    for n, g in zip(names, geoms):
        mi = muni_index[n]
        cand = [c for c in town_at.get(norm(n), []) if g.contains(Point(*c))]
        lon, lat = cand[0] if cand else (g.representative_point().x, g.representative_point().y)
        add(n, lat, lon, "municipio", mi)
    # barrios
    barrios = json.loads((OUT / "barrios.geojson").read_text(encoding="utf-8"))
    for f in barrios["features"]:
        p = f["properties"]
        pt = shape(f["geometry"]).representative_point()
        mi = muni_index.get(p.get("municipality"), -1)
        add(f"Barrio {p['barrio']}", pt.y, pt.x, "barrio", mi, p["barrio"])
    # named places and landmarks
    municipality_names = {norm(n) for n in names}
    for name, lon, lat, kind, note in points:
        if kind == "town" and norm(name) in municipality_names:
            continue   # already the municipality entry
        add(name, lat, lon, kind, muni_of(lon, lat), note if kind in ("town", "village", "neighborhood") else "")
    # roads: one entry per road name per municipality at the middle of its longest piece; route numbers likewise
    best = {}
    for name, ref, hw, lon, lat, metres in ways:
        mi = muni_of(lon, lat)
        if mi < 0:
            continue
        for label, kind in ((name, "road"), (ref, "route")):
            if not label:
                continue
            k = (norm(label), mi, kind)
            cur = best.get(k)
            if cur is None:
                best[k] = [label, lon, lat, metres, metres, name if kind == "route" else "", hw]
            else:
                cur[4] += metres
                if metres > cur[3]:
                    cur[0], cur[1], cur[2], cur[3] = label, lon, lat, metres
    long_enough = 0
    for (nk, mi, kind), (label, lon, lat, longest, total, local, hw) in best.items():
        if kind == "road" and total < 60:
            continue   # stubs
        long_enough += 1
        add(label, lat, lon, kind, mi, local if kind == "route" and local and norm(local) != norm(label) else "")
    items.sort(key=lambda r: (r[3], norm(r[0])))
    doc = {"munis": sorted_names, "kinds": KINDS, "items": items}
    out = OUT / "gazetteer.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    by = {}
    for r in items:
        by[KINDS[r[3]]] = by.get(KINDS[r[3]], 0) + 1
    print(f"  wrote gazetteer.json: {len(items):,} names, {out.stat().st_size / 1e6:.2f} MB  {by}")


if __name__ == "__main__":
    main()
