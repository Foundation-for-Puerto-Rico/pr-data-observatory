"""Transit links between municipios for the PR Data Observatory: how many workers travel between each pair of municipios, whether a timetabled route or a
listed público route joins the pair, and a simulated connection along the roads for the pairs with many workers and no timetabled route.

    python transit_links.py            # download the files missing from cache/transit_links/ and build the three files below
    python transit_links.py --refresh  # download the sources again
    python transit_links.py --check    # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)

Writes
  site/data/publicos.geojson       the público routes of the 2020 list, as lines (map layer publicos)
  site/data/transit_links.json     every pair of municipios with workers travelling between them, the municipios and Puerto Rico's totals
  site/data/simulated_links.geojson  the simulated connections, as lines along the roads (map layer links)
  site/data/timetabled_links.geojson the pairs joined by a current timetable, each as the stretch of its busiest route between the two town centres
The Knowledge Area page transit-links.html reads the last three (docs/transit-links.md, HANDOFF decision 105).

The sources (no key):
  - US Census Bureau, County-to-County Commuting Flows, American Community Survey 2016-2020 (5-year), Table 1: workers 16 and over by the municipio where
    they live and the municipio where they work, each with a margin of error (90 percent). The newest release; the Bureau publishes it every five years.
    US Government work.
  - Instituto de Estadísticas de Puerto Rico, open data portal, "Mapa de rutas de porteadores públicos" (data of the Autoridad de Carreteras y
    Transportación): the público routes that were active, each with a code, a name and its line. Published 2020-03-19, Creative Commons Attribution.
    The list has no timetable, no fares and no date of each route; a route on it may no longer run.
  - The observatory's own files, already built: trips.json, trips_sa.json and trips_su.json (the timetabled trips of the ATI and the municipal systems, from
    their GTFS feeds), transport.json (each stop's municipio), operators.json (whether each timetable is still current), roads.bin (OpenStreetMap roads,
    ODbL), gazetteer.json (each town centre) and municipios.geojson.

How each figure is made (docs/transit-links.md):
  - Workers between two municipios: the two directions added (A to B and B to A). The margin of error of the sum is the root of the sum of the squares.
    A pair is "low reliability" when its margin is as large as the estimate or larger.
  - Timetabled link: a route of a published timetable with stops in both municipios (each stop in the municipio whose outline holds it), on a weekday, Saturday or Sunday. Direct routes only: a trip with a
    transfer is not counted. "Current" when the operator's timetable still runs on the day operators.json was built. Some municipal systems time only
    the first and last stop of each trip: for them, the operator's stops within 35 m of the route's line are the route's stops.
  - Público link (2020 list): a route of the list joins the municipios where its line ends and those whose town centre it passes within 1 km. A long
    route on an expressway does not join the municipios it only crosses.
  - Reachable with a transfer: no direct route, but the two municipios are joined by a chain of current timetabled links through other municipios. No
    journey time is computed, so the chain can be long.
  - Status of a pair, the first that applies: current timetable; expired timetable only; público route on the 2020 list only; none listed.
  - Line of a timetabled pair (the page's map): the stretch of the pair's route with the most weekday trips, as the transit routes layer draws it (the
    ferries' crossings included), from its point in one municipio nearest that town centre to its point in the other nearest the other centre. When no
    route of the pair has a line inside both, the fastest path along the roads between the two centres. Never a straight line.
  - Simulated connection: for the pairs with 500 workers or more, not low reliability, and no timetabled route (current or expired), the fastest path along
    the roads between the two town centres, with its length and driving time without traffic. It is a line drawn by a program to show where a connection
    is missing; it is not a proposed route, a service plan or a demand forecast.
"""
import csv
import heapq
import io
import json
import math
import sys
from datetime import date
from pathlib import Path

import requests
from shapely.geometry import LineString, Point, shape
from shapely.ops import linemerge, nearest_points, substring, unary_union
from shapely import wkt as shapely_wkt
from shapely.prepared import prep

import housing_series as hs
import roads
import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "transit_links"
OUT = hs.OUT
OUT_PUBLICOS = OUT / "publicos.geojson"
OUT_JSON = OUT / "transit_links.json"
OUT_LINKS = OUT / "simulated_links.geojson"
OUT_TT = OUT / "timetabled_links.geojson"
log = hs.log

UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
FLOWS_URL = "https://www2.census.gov/programs-surveys/demo/tables/metro-micro/2020/commuting-flows-2020/table1.xlsx"
FLOWS_PERIOD = "2016-2020"
PUBLICOS_URL = "https://datos.estadisticas.pr/dataset/01e93527-86bc-42c1-a85f-380cc1c4d0d8/resource/ca2b6343-7ad8-43eb-b8c8-cc95e3b14092/download/rutas_publicos.csv"
PUBLICOS_PAGE = "https://datos.estadisticas.pr/dataset/mapa-de-rutas-de-porteadores-publicos"
PUBLICOS_AS_OF = "2020-03-19"   # the day the Instituto published the file (its only date)
NEAR_LINE_M = 35        # a stop of an operator that times only the ends of its trips is on a route when it is this close to its line
NEAR_CENTRE_M = 1000    # a público route joins a municipio when it ends there or passes this close to its town centre
SIM_MIN_WORKERS = 500   # a simulated connection is drawn for a pair with this many workers or more (both directions)
SAFETY_NEAR_M = 100     # a fatal crash counts for a simulated connection when it is this close to its line (FARS coordinates are approximate)
# the second pass of the gap analysis (step 5): journey time by timetable between town centres, and what lies along each simulated connection
TT_FROM, TT_TO, TT_STEP = 6 * 3600, 9 * 3600, 900   # leaving a town centre every 15 minutes from 6:00 to 9:00 on a weekday (13 departures)
TT_MAX = 3 * 3600       # a journey longer than three hours is not counted
TT_WALK_M = 1000        # from a town centre to a stop, and from a stop to a town centre: up to 1 km in a straight line
TT_XFER_M = 400         # a transfer walks up to 400 m between stops, plus TT_XFER_S to make the connection
TT_XFER_S = 120
WALK_MS, DETOUR = 1.2, 1.3   # walking speed (m/s) and the factor from a straight line to the streets
ALONG_M = 1000          # the residents along a simulated connection: 2020 Census blocks within 1 km of its line
ALONG_STOP_M = 400      # of them, those beyond 400 m (straight line) of a scheduled stop
BRIDGE_NEAR_M = 50      # a bridge of the National Bridge Inventory is on a simulated connection when its point is this close to the line
TRAFFIC_STEP_M, TRAFFIC_NEAR_M = 100, 25   # the traffic along a simulated connection: a point every 100 m takes the count of the counted road within 25 m
SIMPLIFY_M = 12        # público lines and simulated connections are simplified to this tolerance
TT_EDGE_M, TT_MIN_M = 150, 300   # the page's line of a timetabled pair: a route's line counts inside a municipio up to 150 m beyond its outline (a terminal on the shore); a stretch is at least 300 m
STATUSES = ["timetable", "expired", "publico", "none"]
SIM_TYPES = {"none": "Simulated connection, no route listed", "publico": "Simulated connection, público route on the 2020 list"}   # the layers' types, as core/facilities.js names them
PUBLICO_TYPES = {True: "Público route between municipios", False: "Público route within a municipio"}
LAT0 = 18.2
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110574   # metres per degree at Puerto Rico's latitude


def fetch(url, timeout=300):
    for i in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == 3:
                raise SystemExit(f"transit links: {url} failed ({e})")
            log(f"  retry {url} ({e})")


def cached(name, url, refresh):
    """The bytes of a cached download, fetched when missing or on --refresh."""
    p = CACHE / name
    if refresh or not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(fetch(url).content)
        log(f"  downloaded {name} ({p.stat().st_size / 1024:,.0f} KB)")
    return p.read_bytes()


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def to_m(geom):
    """A shapely geometry in degrees, in local metres (equirectangular at 18.2° N: good to about 0.1% across Puerto Rico)."""
    from shapely import transform
    return transform(geom, lambda a: a * [KX, KY])


def to_deg(geom):
    from shapely import transform
    return transform(geom, lambda a: a / [KX, KY])


def line_coords(geom):
    """The coordinates of a line or multi-line, rounded to 5 decimals (about 1 m), as GeoJSON geometry."""
    r = lambda c: [[round(x, 5), round(y, 5)] for x, y in c]
    if isinstance(geom, LineString):
        return {"type": "LineString", "coordinates": r(geom.coords)}
    parts = [r(g.coords) for g in geom.geoms if len(g.coords) > 1]
    return {"type": "LineString", "coordinates": parts[0]} if len(parts) == 1 else {"type": "MultiLineString", "coordinates": parts}


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# municipios
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def municipios():
    """[{geoid, name, lat, lng (town centre), geom_m (outline in metres)}] in GEOID order."""
    fc = read("municipios.geojson")
    gz = read("gazetteer.json")
    centre = {gz["munis"][i[4]]: (i[1], i[2]) for i in gz["items"] if gz["kinds"][i[3]] == "municipio"}
    out = []
    for f in fc["features"]:
        p = f["properties"]
        name = p["municipality"]
        if name not in centre:
            raise SystemExit(f"transit links: {name} has no town centre in gazetteer.json")
        out.append({"geoid": p["GEOID"], "name": name, "lat": centre[name][0], "lng": centre[name][1], "geom_m": to_m(shape(f["geometry"]))})
    out.sort(key=lambda m: m["geoid"])
    if len(out) != 78:
        raise SystemExit(f"transit links: {len(out)} municipios, expected 78")
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# workers between municipios (Census commuting flows)
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def flows(data, munis):
    """({(home geoid, work geoid): (workers, margin)} for every pair inside Puerto Rico, home and work the same included; workers who work outside Puerto
    Rico). Stops when the table is not the one expected."""
    known = {m["geoid"] for m in munis}
    num = lambda v: int(str(v).replace(",", ""))
    title, out, away = "", {}, 0
    for r in xlsx_read.rows(data):
        if r.get(0) and "Commuting Flows" in str(r[0]) and not title:
            title = str(r[0])
        if r.get(0) != "72" or r.get(8) is None:
            continue
        home = "72" + r[1]
        if home not in known:
            raise SystemExit(f"transit links: the flows table names a municipio the observatory does not have ({home})")
        if r.get(4) != "072":
            away += num(r[8])
            continue
        work = "72" + r[5]
        if work not in known:
            raise SystemExit(f"transit links: the flows table names a workplace municipio the observatory does not have ({work})")
        out[(home, work)] = (num(r[8]), num(r[9]))
    if FLOWS_PERIOD not in title:
        raise SystemExit(f"transit links: the flows table is not the {FLOWS_PERIOD} release ({title[:120]!r}): update FLOWS_PERIOD and the texts that name it")
    if len({h for h, _ in out}) != 78:
        raise SystemExit("transit links: the flows table does not cover the 78 municipios")
    return out, away


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# timetabled routes that join two municipios
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def place_stops(stops, munis):
    """{stop id: geoid}: the municipio whose outline holds the stop, or whose outline is nearest when the point is just outside every outline (a pier).
    transport.json's municipality follows the same rule since the 2026-11 fix (muni_locate.py); before it, the nearest town centre put five stops of
    Cataño's waterfront in San Juan. This page still places every stop by its point, so it never depends on when transport.json was last rebuilt."""
    shapes = [(m["geoid"], prep(m["geom_m"]), m["geom_m"]) for m in munis]
    out = {}
    for t in stops:
        p = to_m(Point(t["lng"], t["lat"]))
        out[t["id"]] = next((g for g, pp, _ in shapes if pp.contains(p)), None) or min(shapes, key=lambda x: x[2].distance(p))[0]
    return out


def timetabled(munis):
    """{(geoid a, geoid b) with a < b: {"routes": {(operator, route): weekday trips}, "current": bool, "days": set}} and the operators' names and status.
    A route joins the municipios where it has stops. The stops of a trip are those of its pattern (path_stops). Some municipal feeds time only the first and
    last stop of each trip, so the patterns of those routes hold two stops: for a municipal route with no longer pattern, the operator's stops within NEAR_LINE_M
    of the route's line count too (those lines are drawn through the route's stops, in order). The ATI's two-stop routes are express routes and are left as they are."""
    geoid = {m["name"]: m["geoid"] for m in munis}
    stops = [t for t in read("transport.json") if t.get("source") in ("ati_gtfs", "muni_gtfs")]
    stop_muni = place_stops(stops, munis)
    ops = read("operators.json")
    status = {o["id"]: o["feed"].get("status") for o in ops["operators"]}
    names = {o["id"]: o.get("short") or o["name"] for o in ops["operators"]}
    municipal = {o["id"] for o in ops["operators"] if o.get("type") == "municipal"}
    pairs, full, seen = {}, set(), set()

    def join(ms, key, day, trips):
        ms = sorted(ms)
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                p = pairs.setdefault((a, b), {"routes": {}, "days": set()})
                p["days"].add(day)
                p["routes"][key] = max(p["routes"].get(key, 0), trips) if day == "wk" else p["routes"].get(key, 0)

    for day, name in (("wk", "trips.json"), ("sa", "trips_sa.json"), ("su", "trips_su.json")):
        doc = read(name)
        path_munis = [{stop_muni.get(s) for s in ps} - {None} for ps in doc["path_stops"]]   # path_stops[k] holds the stop of each position of the pattern ("s" indexes the path's points, not this list)
        count = {}
        for t in doc["trips"]:
            seen.add((t["o"], str(t["r"])))
            if len(doc["path_stops"][t["k"]]) > 2:
                full.add((t["o"], str(t["r"])))
            key = (t["o"], str(t["r"]), t["k"])
            count[key] = count.get(key, 0) + 1
        by_route = {}
        for (o, r, k), n in count.items():   # a route's weekday trips between two municipios: those of its patterns that stop in both
            for i, a in enumerate(sorted(path_munis[k])):
                for b in sorted(path_munis[k])[i + 1:]:
                    by_route[(a, b, o, r)] = by_route.get((a, b, o, r), 0) + n
        for (a, b, o, r), n in by_route.items():
            join([a, b], (o, r), day, n)
    ends_only = {k for k in seen - full if k[0] in municipal}   # the routes whose trips time only their two ends
    ends_ops = {o for o, _ in ends_only}
    near = {}
    for t in stops:
        if t.get("operator") in ends_ops and stop_muni[t["id"]]:
            near.setdefault(t["operator"], []).append((to_m(Point(t["lng"], t["lat"])), stop_muni[t["id"]]))
    for f in read("transit_routes.geojson")["features"]:
        q = f["properties"]
        key = (q["operator"], str(q.get("short_name") or q.get("long_name") or q["route_id"]))   # a trip's "r" is the route's short name, or its long name
        if key not in ends_only:
            continue
        line = to_m(shape(f["geometry"]))
        ms = {g for pt, g in near.get(q["operator"], []) if line.distance(pt) <= NEAR_LINE_M}
        for day, k in (("wk", "trips_weekday"), ("sa", "trips_saturday"), ("su", "trips_sunday")):
            if q.get(k):
                join(ms, key, day, q[k])
    for p in pairs.values():
        p["current"] = any(status.get(o) in ("current", "expiring") for o, _ in p["routes"])
    return pairs, names, status, ops.get("built"), sorted(names.get(o, o) for o in ends_ops)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# público routes of the 2020 list
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def publicos(data, munis):
    """The routes of the list, one per code (the list gives some routes as several rows: each direction, or pieces): [{code, name, rows, munis: [geoid],
    geom (degrees, simplified)}]. A route joins the municipios where it ends (the two ends of its line that are farthest apart) and those whose town centre
    it passes within NEAR_CENTRE_M: a long route on an expressway does not join the municipios it only crosses."""
    csv.field_size_limit(10 ** 9)
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    if not rows or set(rows[0]) != {"the_geom", "Nombre", "Codigo", "Rumbo"}:
        raise SystemExit("transit links: the público file does not have the columns the_geom, Nombre, Codigo, Rumbo")
    groups = {}
    for i, r in enumerate(rows):
        g = shapely_wkt.loads(r["the_geom"])
        if g.is_empty:
            continue
        code = r["Codigo"].split(" (")[0].strip()   # some codes carry a truncated note, "L-42-08 (4"
        k = code or f"row {i}"
        groups.setdefault(k, {"code": code, "name": " ".join(r["Nombre"].split()), "parts": []})["parts"].append(to_m(g))
    prepared = [(m["geoid"], m["geom_m"], prep(m["geom_m"]), to_m(Point(m["lng"], m["lat"]))) for m in munis]
    out = []
    for k in sorted(groups):
        r = groups[k]
        gm = unary_union(r["parts"])
        lines = [gm] if isinstance(gm, LineString) else list(gm.geoms)
        ends = [Point(c) for ln in lines for c in (ln.coords[0], ln.coords[-1])]
        far = max(((p.distance(q), i, j) for i, p in enumerate(ends) for j, q in enumerate(ends) if i < j), default=(0, 0, 0))
        termini = [ends[far[1]], ends[far[2]]]
        inside = [geoid for geoid, poly, pp, centre in prepared if any(pp.contains(t) for t in termini) or gm.distance(centre) <= NEAR_CENTRE_M]
        if not inside:   # a short route that ends outside every outline (a pier) and passes no centre: the municipio that holds most of it
            inside = [max(prepared, key=lambda m: gm.intersection(m[1]).length)[0]]
        out.append({"code": r["code"], "name": r["name"], "rows": len(r["parts"]), "munis": sorted(inside), "geom": to_deg(gm.simplify(SIMPLIFY_M))})
    return out


def publico_pairs(routes):
    pairs = {}
    for r in routes:
        ms = sorted(r["munis"])
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                pairs.setdefault((a, b), []).append(r["code"])
    return pairs


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# roads: the fastest path between two town centres
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def tree(R, source):
    """Fastest driving time from one node to every node it reaches: ({node: seconds}, {node: (previous node, edge)})."""
    dist, prev, heap = {source: 0.0}, {}, [(0.0, source)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist[n]:
            continue
        for m, e, _ in R.adj[n]:
            nd = d + R.cum[e][-1] / roads.SPEED_MS[R.cls[e]]
            if nd < dist.get(m, 1e18):
                dist[m] = nd
                prev[m] = (n, e)
                heapq.heappush(heap, (nd, m))
    return dist, prev


def centre_node(R, m):
    """The road node nearest a town centre: an end of the nearest road within 1 km."""
    s = R.snap(m["lng"], m["lat"], 1000)
    if s is None:
        raise SystemExit(f"transit links: no road within 1 km of the centre of {m['name']}")
    e = s["edge"]
    return int(R.eu[e]) if s["along"] <= R.cum[e][-1] / 2 else int(R.ev[e])


def road_path(R, prev, a, b):
    """The path from node a (the tree's source) to node b as (metres, [(lon, lat)...]), from the tree's previous-node table."""
    seq, n = [], b
    while n != a:
        p, e = prev[n]
        seq.append((e, int(R.eu[e]) == p))
        n = p
    pts, metres = [], 0.0
    for e, fwd in reversed(seq):
        seg = R.poly[e] if fwd else R.poly[e][::-1]
        metres += R.cum[e][-1]
        pts += seg if not pts else seg[1:]
    return metres, pts


def route_lines():
    """{(operator, route): (line in metres, mode, label)} for the timetabled routes, from the transit routes layer (transit_routes.geojson), keyed as a
    trip's route is (its short name, or its long name)."""
    out = {}
    for f in read("transit_routes.geojson")["features"]:
        q = f["properties"]
        key = (q["operator"], str(q.get("short_name") or q.get("long_name") or q["route_id"]))
        g = to_m(shape(f["geometry"]))
        if g.geom_type == "MultiLineString":
            g = linemerge(g)
        out[key] = (g, q.get("mode"), q.get("label") or q.get("short_name") or q.get("long_name"))
    return out


def stretch(line, ma, mb):
    """The part of a route's line between the two municipios it joins: from the point of the line inside municipio A (its outline widened by TT_EDGE_M)
    nearest A's town centre to the point inside B nearest B's centre. None when the line does not enter one of the two, or the stretch is shorter than
    TT_MIN_M. A route that serves San Juan in Río Piedras is drawn to Río Piedras, not to the centre of Old San Juan."""
    parts = list(line.geoms) if line.geom_type == "MultiLineString" else [line]
    best = None
    for part in parts:
        ends = []
        for m in (ma, mb):
            inside = part.intersection(m["geom_m"].buffer(TT_EDGE_M))
            if inside.is_empty:
                break
            ends.append(part.project(nearest_points(inside, m["centre_m"])[0]))
        if len(ends) < 2:
            continue
        seg = substring(part, min(ends), max(ends))
        if seg.length >= TT_MIN_M and (best is None or seg.length > best.length):
            best = seg
    return best


def timetabled_lines(pairs, tt, centre, R, trees, node):
    """One line for each pair joined by a current timetable: the stretch of its busiest route with a line, else the road path. [(pair, line in degrees, how, route)]."""
    lines = route_lines()
    out = []
    for p in pairs:
        if p["status"] != "timetable":
            continue
        a, b = p["a"], p["b"]
        got = None
        for key, trips in sorted(tt[(a, b)]["routes"].items(), key=lambda kv: (-kv[1], kv[0])):
            if key in lines:
                seg = stretch(lines[key][0], centre[a], centre[b])
                if seg is not None:
                    got = (seg, lines[key][1] or "bus", lines[key][2])
                    break
        if got is None:
            if a not in trees:
                trees[a] = tree(R, node[a])
            dist, prev = trees[a]
            if node[b] not in dist:
                raise SystemExit(f"transit links: no route line and no road joins {a} and {b}")
            got = (to_m(LineString(road_path(R, prev, node[a], node[b])[1])), "road", None)
        out.append((p, to_deg(got[0].simplify(SIMPLIFY_M)), got[1], got[2]))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------------------------------------------------------------------------------------

def road_traffic(links):
    """The traffic on the roads each simulated connection follows, from the published traffic layer (traffic.py): points every TRAFFIC_STEP_M along the
    line take the count of the counted road within TRAFFIC_NEAR_M. Sets aadt_med, aadt_max and counted_pct on each pair; returns the traffic data year, or
    None when the layer has not been built (the fields stay empty)."""
    p = OUT / "traffic_roads.geojson"
    if not p.exists():
        return None
    from statistics import median
    from shapely import STRtree
    doc = json.loads(p.read_text(encoding="utf-8"))
    geoms = [to_m(shape(f["geometry"])) for f in doc["features"]]
    aadt = [f["properties"]["a"] for f in doc["features"]]
    tree = STRtree(geoms)
    for pair, g in links:
        line = to_m(g)
        n = max(2, int(line.length // TRAFFIC_STEP_M) + 1)
        pts = [line.interpolate(i * line.length / (n - 1)) for i in range(n)]
        got = []
        for pt in pts:
            hit = tree.query_nearest(pt, max_distance=TRAFFIC_NEAR_M, all_matches=False)
            if len(hit):
                got.append(aadt[int(hit[0])])
        pair["aadt_med"] = round(median(got)) if got else None
        pair["aadt_max"] = max(got) if got else None
        pair["counted_pct"] = round(100 * len(got) / n, 1)
    return int(doc.get("vintage") or doc["notes"]["data_year"])


def transit_times(pairs, munis):
    """The fastest journey by the published weekday timetables between the town centres of each pair (both ways), with transfers: a connection scan over
    trips.json for departures every TT_STEP from TT_FROM to TT_TO. Walks TT_WALK_M at most to and from the stops, TT_XFER_M between stops (plus TT_XFER_S).
    Sets tt_best (the fastest journey, minutes), tt_typ (the median over the departures, waiting included) and tt_xfers (transfers on the fastest) on each
    pair that has a journey within TT_MAX, and tt_why on the others: 1 when a town centre has no stop of the weekday timetables within TT_WALK_M, 2 when
    both have one but no journey within TT_MAX joins them. Returns the rule, the counts and {geoid: km from the town centre to the nearest stop with
    weekday service}."""
    from bisect import bisect_left
    from shapely import STRtree
    doc = read("trips.json")
    stop_pt = {t["id"]: to_m(Point(t["lng"], t["lat"])) for t in read("transport.json") if t.get("source") in ("ati_gtfs", "muni_gtfs")}
    ids = sorted(stop_pt)
    ix = {sid: i for i, sid in enumerate(ids)}
    pts = [stop_pt[sid] for sid in ids]
    conns = []
    for j, t in enumerate(doc["trips"]):
        ps, tt = doc["path_stops"][t["k"]], t["t"]
        for i in range(len(tt) - 1):
            a, b = ix.get(ps[i]), ix.get(ps[i + 1])
            if a is not None and b is not None and tt[i + 1] >= tt[i]:
                conns.append((tt[i], tt[i + 1], a, b, j))
    conns.sort()
    dep_times = [c[0] for c in conns]
    tree = STRtree(pts)
    timed = sorted({c[2] for c in conns} | {c[3] for c in conns})   # stops with weekday service
    ttree = STRtree([pts[i] for i in timed])
    foot = [[] for _ in pts]
    for i, p in enumerate(pts):
        for j in tree.query(p, predicate="dwithin", distance=TT_XFER_M):
            j = int(j)
            if j != i:
                foot[i].append((j, p.distance(pts[j]) * DETOUR / WALK_MS + TT_XFER_S))
    access, stop_km = {}, {}
    for m in munis:
        c = to_m(Point(m["lng"], m["lat"]))
        access[m["geoid"]] = [(timed[int(j)], c.distance(pts[timed[int(j)]]) * DETOUR / WALK_MS) for j in ttree.query(c, predicate="dwithin", distance=TT_WALK_M)]
        stop_km[m["geoid"]] = round(c.distance(pts[timed[int(ttree.nearest(c))]]) / 1000, 1)
    wanted = {}
    for p in pairs:
        wanted.setdefault(p["a"], set()).add(p["b"])
        wanted.setdefault(p["b"], set()).add(p["a"])
    deps = list(range(TT_FROM, TT_TO + 1, TT_STEP))
    INF = float("inf")
    got = {}   # (origin, destination): [(journey seconds, boardings) per departure]
    for a in sorted(wanted):
        if not access[a]:
            continue
        for d in deps:
            S, B = [INF] * len(pts), [0] * len(pts)
            for j, w in access[a]:
                S[j] = min(S[j], d + w)
            reached, end = {}, d + TT_MAX
            for k in range(bisect_left(dep_times, d), len(conns)):
                dt, at, u, v, trip = conns[k]
                if dt > end:
                    break
                bt = reached.get(trip)
                if bt is None:
                    if S[u] > dt:
                        continue
                    bt = reached[trip] = B[u] + 1
                if at < S[v]:
                    S[v], B[v] = at, bt
                    for w2, ws in foot[v]:
                        if at + ws < S[w2]:
                            S[w2], B[w2] = at + ws, bt
            for b in wanted[a]:
                best = min(((S[j] + w, B[j]) for j, w in access[b] if S[j] < INF and B[j] > 0), default=None)
                got.setdefault((a, b), []).append((best[0] - d, best[1]) if best and best[0] - d <= TT_MAX else None)
    done = 0
    for p in pairs:
        runs = [r for key in ((p["a"], p["b"]), (p["b"], p["a"])) for r in got.get(key, []) if r]
        if not runs:
            p["tt_why"] = 1 if not access[p["a"]] or not access[p["b"]] else 2
            continue
        fast = min(runs)
        js = sorted(r[0] for r in runs)
        p["tt_best"], p["tt_typ"], p["tt_xfers"] = round(fast[0] / 60), round(js[len(js) // 2] / 60), fast[1] - 1
        done += 1
    return {"source": "The published weekday timetables (trips.json), as the observatory reads them on " + str(doc.get("day")),
            "rule": "The fastest journey by timetable between the two town centres, in either direction, leaving every 15 minutes from 6:00 to 9:00 on a weekday: "
                    "walking up to 1 km to and from a stop and up to 400 m between stops (straight line times 1.3, at 1.2 m/s, plus 2 minutes to transfer); "
                    "tt_best is the fastest, tt_typ the median over the departures (waiting included), tt_xfers the transfers on the fastest. No journey over 3 hours.",
            "day": doc.get("day"), "departures": [TT_FROM, TT_TO, TT_STEP], "walk_m": TT_WALK_M, "transfer_m": TT_XFER_M, "max_min": TT_MAX // 60,
            "pairs_with_a_journey": done, "connections": len(conns), "centres_without_a_stop": sum(1 for g in access if not access[g]),
            "why": {"1": "a town centre has no stop of the weekday timetables within 1 km", "2": "no journey within 3 hours joins the two centres"}}, stop_km


def along_links(links):
    """What lies along each simulated connection: the 2020 Census residents of the blocks within ALONG_M of its line (along_res) and, of them, those beyond
    ALONG_STOP_M of a scheduled stop (along_far; population_blocks.json gives each block's straight-line distance to the nearest scheduled stop); and the
    bridges of the National Bridge Inventory within BRIDGE_NEAR_M of the line in poor condition (bridges_poor) or closed (bridges_closed), from
    bridges.geojson (transport_inventories.py). Returns the rules, or None for the bridges when that file is missing."""
    from shapely import STRtree
    blocks = read("population_blocks.json")
    bt = STRtree([to_m(Point(b[0], b[1])) for b in blocks])
    for pair, g in links:
        gm = to_m(g)
        near = [blocks[int(i)] for i in bt.query(gm, predicate="dwithin", distance=ALONG_M)]
        pair["along_res"] = sum(b[2] for b in near)
        pair["along_far"] = sum(b[2] for b in near if b[3] > ALONG_STOP_M)
    out = {"residents": {"source": "2020 Census blocks (population_blocks.json)", "near_m": ALONG_M, "far_m": ALONG_STOP_M,
                         "rule": "Residents of the 2020 Census blocks whose point is within 1 km of the connection's line; along_far, those of them beyond 400 m in a straight line of a scheduled stop. Connections share roads, so the counts must not be added up."}}
    path = OUT / "bridges.geojson"
    if path.exists():
        bg = [f for f in json.loads(path.read_text(encoding="utf-8"))["features"] if f["properties"].get("type") == "Bridge"]
        tree = STRtree([to_m(Point(*f["geometry"]["coordinates"])) for f in bg])
        for pair, g in links:
            near = [bg[int(i)]["properties"] for i in tree.query(to_m(g), predicate="dwithin", distance=BRIDGE_NEAR_M)]
            pair["bridges_poor"] = sum(1 for q in near if q.get("c") == "P")
            pair["bridges_closed"] = sum(1 for q in near if q.get("o") == "K")
        out["bridges"] = {"source": "FHWA National Bridge Inventory (bridges.geojson, transport_inventories.py)", "near_m": BRIDGE_NEAR_M, "bridges": len(bg),
                          "rule": "Bridges whose point is within 50 m of the connection's line: bridges_poor in poor condition, bridges_closed closed. A bridge under the road the line follows can count too."}
    return out


def need_by_municipio():
    """{geoid: (households with no vehicle %, residents below the poverty level %)} for the newest ACS 5-year estimates the site publishes, and that period."""
    eco, hou = read("economy_series.json"), read("housing_series.json")
    nv = next(v for v in eco["vars"] if v["key"] == "no_vehicle_hh_pct")
    pv = next(v for v in hou["vars"] if v["key"] == "poverty_pct")
    y = max(set(nv["years"]) & set(pv["years"]), key=int)
    a, b = nv["years"][y], pv["years"][y]
    out = {g: (a[i], b[i]) for i, g in enumerate(eco["geo"]["ids"]) if i < len(a)}
    return out, f"{int(y) - 4}-{y}"


def road_safety(links):
    """The people killed in traffic crashes within SAFETY_NEAR_M of each simulated connection over the last five years of NHTSA's FARS (crashes.points(),
    from cache/crashes/): deaths_5y and walk_bike_5y (pedestrians and bicyclists) on each pair. Only these five-year totals are published, never a crash's
    place, date or time. Returns the rule and the years, or None when there is no FARS file (the fields stay empty)."""
    import crashes
    from shapely import STRtree
    from shapely.geometry import Point
    try:
        y0, y1, pts = crashes.points()
    except SystemExit:
        return None
    if not pts:
        return None
    geoms = [to_m(Point(lng, lat)) for lng, lat, _, _ in pts]
    tree = STRtree(geoms)
    for pair, g in links:
        near = tree.query(to_m(g), predicate="dwithin", distance=SAFETY_NEAR_M)
        pair["deaths_5y"] = sum(pts[int(i)][2] for i in near)
        pair["walk_bike_5y"] = sum(pts[int(i)][3] for i in near)
    return {"source": "NHTSA Fatality Analysis Reporting System (FARS), Puerto Rico files (crashes.py)", "years": [y0, y1], "near_m": SAFETY_NEAR_M, "located_crashes": len(pts),
            "rule": "People killed in fatal crashes within 100 m of the simulated connection's line over the five years; walk_bike_5y counts the pedestrians and bicyclists among them. A crash at a crossing road within 100 m counts too."}


def assemble(flows_doc, pub_data):
    munis = municipios()
    name = {m["geoid"]: m["name"] for m in munis}
    fl, away = flows(flows_doc, munis)
    tt, op_names, op_status, tt_as_of, ends_only = timetabled(munis)
    routes = publicos(pub_data, munis)
    pp = publico_pairs(routes)

    # pairs of different municipios with workers in either direction
    keys = sorted({tuple(sorted(k)) for k in fl if k[0] != k[1]})
    R = roads.Roads()
    node = {m["geoid"]: centre_node(R, m) for m in munis}
    trees = {}
    pairs, links = [], []
    for a, b in keys:
        ab, ba = fl.get((a, b), (0, 0)), fl.get((b, a), (0, 0))
        workers = ab[0] + ba[0]
        moe = round(math.sqrt(ab[1] ** 2 + ba[1] ** 2))
        t = tt.get((a, b))
        pubs = sorted(set(pp.get((a, b), [])))
        status = "timetable" if t and t["current"] else "expired" if t else "publico" if pubs else "none"
        pairs.append({"a": a, "b": b, "ab": ab[0], "ba": ba[0], "workers": workers, "moe": moe, "low": moe >= workers, "status": status,
                      "tt_routes": len(t["routes"]) if t else 0, "tt_trips": sum(t["routes"].values()) if t else 0,
                      "tt_ops": sorted({op_names.get(o, o) for o, _ in t["routes"]}) if t else [], "publicos": len(pubs), "km": None, "min": None})
    # reachable with a transfer: the two municipios are in the same group of the graph of current timetabled links
    group = {m["geoid"]: m["geoid"] for m in munis}

    def find(x):
        while group[x] != x:
            group[x] = group[group[x]]
            x = group[x]
        return x
    for p in pairs:
        if p["status"] == "timetable":
            group[find(p["a"])] = find(p["b"])
    for p in pairs:
        p["via"] = p["status"] != "timetable" and find(p["a"]) == find(p["b"])
    # road distance and time for every pair on the same island of the road network, and the simulated connections
    for p in pairs:
        a, b = p["a"], p["b"]
        if a not in trees:
            trees[a] = tree(R, node[a])
        dist, prev = trees[a]
        if node[b] not in dist:
            continue   # Vieques and Culebra: no road to the main island
        metres, pts = road_path(R, prev, node[a], node[b])
        p["km"], p["min"] = round(metres / 1000, 1), round(dist[node[b]] / 60)
        if p["workers"] >= SIM_MIN_WORKERS and not p["low"] and p["status"] in ("publico", "none"):
            g = to_deg(to_m(LineString(pts)).simplify(SIMPLIFY_M))
            links.append((p, g))
    links.sort(key=lambda x: (-x[0]["workers"], x[0]["a"], x[0]["b"]))
    for i, (p, _) in enumerate(links):
        p["sim"] = i + 1
    centre = {m["geoid"]: {**m, "centre_m": to_m(Point(m["lng"], m["lat"]))} for m in munis}
    tt_lines = timetabled_lines(pairs, tt, centre, R, trees, node)
    traffic_year = road_traffic(links)
    safety = road_safety(links)
    times, stop_km = transit_times(pairs, munis)
    along = along_links(links)
    need, need_period = need_by_municipio()

    # totals
    cross = sum(p["workers"] for p in pairs)
    same = sum(v[0] for k, v in fl.items() if k[0] == k[1])
    by_status = {s: {"pairs": 0, "workers": 0} for s in STATUSES}
    for p in pairs:
        by_status[p["status"]]["pairs"] += 1
        by_status[p["status"]]["workers"] += p["workers"]
    pct = lambda n, d: round(100 * n / d, 1) if d else None
    pr = {"workers": cross + same + away, "same_municipio": same, "other_municipio": cross, "outside_pr": away, "other_municipio_pct": pct(cross, cross + same + away),
          "pairs": len(pairs), "by_status": {s: {**v, "pct": pct(v["workers"], cross)} for s, v in by_status.items()},
          "simulated": len(links), "simulated_workers": sum(p["workers"] for p, _ in links),
          "simulated_none": sum(1 for p, _ in links if p["status"] == "none"), "simulated_via": sum(1 for p, _ in links if p["via"]),
          "via_pairs": sum(1 for p in pairs if p["via"]), "via_workers": sum(p["workers"] for p in pairs if p["via"]), "simulated_km": round(sum(p["km"] for p, _ in links), 1)}

    # municipios: residents who work elsewhere, workers who come in, and how much of both has a timetabled link
    mrows = []
    own = {}   # the municipio's own system and the state of its timetable: current, expiring, expired, or none (it reports service but publishes no timetable)
    for o in read("operators.json")["operators"]:
        if o.get("type") != "municipal":
            continue
        where = o.get("municipality") or next((m["name"] for m in munis if hs.norm(m["name"]) == hs.norm(o["id"].replace("_", " "))), None)   # three operators carry no municipality: their id names it
        if where:
            own[where] = o["feed"].get("status") or "none"
    for m in munis:
        g = m["geoid"]
        out_w = sum(v[0] for k, v in fl.items() if k[0] == g and k[1] != g)
        in_w = sum(v[0] for k, v in fl.items() if k[1] == g and k[0] != g)
        stay = fl.get((g, g), (0, 0))[0]
        mine = [p for p in pairs if g in (p["a"], p["b"])]
        two_way = sum(p["workers"] for p in mine)
        linked = sum(p["workers"] for p in mine if p["status"] == "timetable")
        top = max(((v[0], k[1]) for k, v in fl.items() if k[0] == g and k[1] != g), default=(0, None))
        mrows.append([g, m["name"], round(m["lat"], 5), round(m["lng"], 5), stay + out_w, out_w, pct(out_w, stay + out_w), in_w, top[1], top[0],
                      pct(linked, two_way), sum(1 for p in mine if p["status"] == "timetable"), sum(1 for p in mine if p.get("sim")),
                      own.get(m["name"]), *need.get(g, (None, None)), stop_km.get(g)])

    fields = ["a", "b", "ab", "ba", "workers", "moe", "low", "status", "via", "tt_routes", "tt_trips", "tt_ops", "publicos", "km", "min", "sim", "aadt_med", "aadt_max", "counted_pct", "deaths_5y", "walk_bike_5y", "tt_best", "tt_typ", "tt_xfers", "tt_why", "along_res", "along_far", "bridges_poor", "bridges_closed"]
    doc = {
        "about": "Workers who travel between each pair of municipios of Puerto Rico, whether a timetabled route or a público route of the 2020 list joins the "
                 "pair, and the simulated connections drawn for the pairs with many workers and no timetabled route. A simulated connection is not a proposed "
                 "route or a demand forecast (transit_links.py, docs/transit-links.md).",
        "flows": {"source": "US Census Bureau, County-to-County Commuting Flows, American Community Survey " + FLOWS_PERIOD + " (5-year), Table 1", "url": FLOWS_URL,
                  "period": FLOWS_PERIOD, "universe": "Workers 16 years and over", "moe": "90 percent margin of error; for a pair, the root of the sum of the squares of the two directions"},
        "timetables": {"source": "GTFS timetables of the ATI and the municipal systems, as the observatory publishes them (trips.json, operators.json)", "as_of": tt_as_of,
                       "rule": "A route with stops in both municipios on a weekday, Saturday or Sunday; direct routes only",
                       "ends_only": ends_only, "near_line_m": NEAR_LINE_M},
        "publicos": {"source": "Instituto de Estadísticas de Puerto Rico, Mapa de rutas de porteadores públicos (Autoridad de Carreteras y Transportación)", "url": PUBLICOS_PAGE,
                     "as_of": PUBLICOS_AS_OF, "routes": len(routes), "between_municipios": sum(1 for r in routes if len(r["munis"]) > 1),
                     "rows": sum(r["rows"] for r in routes), "near_centre_m": NEAR_CENTRE_M},
        "rules": {"sim_min_workers": SIM_MIN_WORKERS, "statuses": STATUSES, "low": "margin of error as large as the estimate or larger"},
        "traffic": {"source": "FHWA Highway Performance Monitoring System (traffic_roads.geojson, traffic.py)", "data_year": traffic_year, "sample_m": TRAFFIC_STEP_M, "near_m": TRAFFIC_NEAR_M,
                    "rule": "Points every 100 m along each simulated connection; a point takes the count of the counted road within 25 m. aadt_med is the median of those counts, aadt_max the highest, counted_pct the share of points on a counted road."} if traffic_year else None,
        "safety": safety,
        "transit_time": times,
        "along": along,
        "need": {"source": "US Census Bureau, American Community Survey " + need_period + " (5-year): households with no vehicle (B25044, economy_series.json) and residents below the poverty level (B17001, housing_series.json)",
                 "period": need_period},
        "pr": pr,
        "muni_fields": ["geoid", "name", "lat", "lng", "resident_workers", "work_elsewhere", "work_elsewhere_pct", "come_in", "top_dest", "top_dest_workers",
                        "linked_pct", "linked_pairs", "sim_links", "own_system", "no_vehicle_pct", "poverty_pct", "stop_km"],
        "municipios": mrows,
        "pair_fields": fields,
        "pairs": [[p.get(f) for f in fields] for p in sorted(pairs, key=lambda p: (-p["workers"], p["a"], p["b"]))],
    }
    layer = {
        "type": "FeatureCollection", "vintage": FLOWS_PERIOD,
        "notes": {"source": "Simulated by Foundation for Puerto Rico from the Census Bureau's commuting flows " + FLOWS_PERIOD + ", the published timetables and OpenStreetMap roads",
                  "what": "The fastest path along the roads between two town centres, for each pair of municipios with " + str(SIM_MIN_WORKERS)
                          + " workers or more travelling between them and no timetabled route. Not a proposed route or a demand forecast.",
                  "flows_period": FLOWS_PERIOD, "timetables_as_of": tt_as_of, "publicos_as_of": PUBLICOS_AS_OF, "min_workers": SIM_MIN_WORKERS,
                  "links": len(links), "with_publico_2020": sum(1 for p, _ in links if p["status"] == "publico"), "none_listed": pr["simulated_none"],
                  "workers": pr["simulated_workers"]},
        "features": [{"type": "Feature", "geometry": line_coords(g),
                      "properties": {"type": SIM_TYPES[p["status"]], "c": 2 if p["status"] == "publico" else 1, "rank": p["sim"], "a": name[p["a"]], "b": name[p["b"]],
                                     "name": name[p["a"]] + " – " + name[p["b"]], "workers": p["workers"], "moe": p["moe"], "km": p["km"], "min": p["min"],
                                     "publicos": p["publicos"], "via": p["via"], "geoid_a": p["a"], "geoid_b": p["b"],
                                     **({"aadt_med": p["aadt_med"], "aadt_max": p["aadt_max"], "counted_pct": p["counted_pct"]} if p.get("aadt_max") else {}),
                                     **({"deaths_5y": p["deaths_5y"], "walk_bike_5y": p["walk_bike_5y"]} if safety else {}),
                                     **{k: p[k] for k in ("along_res", "along_far", "bridges_poor", "tt_best", "tt_why") if p.get(k) is not None}}} for p, g in links],
    }
    tt_layer = {
        "type": "FeatureCollection", "vintage": tt_as_of,
        "notes": {"what": "Each pair of municipios joined by a current timetabled route, as the stretch of its route with the most weekday trips between its point "
                          "in each municipio nearest that town centre (transit routes layer); the fastest road path when no route has a line inside both.",
                  "timetables_as_of": tt_as_of, "pairs": len(tt_lines), "by": {k: sum(1 for x in tt_lines if x[2] == k) for k in sorted({x[2] for x in tt_lines})},
                  "edge_m": TT_EDGE_M, "min_m": TT_MIN_M},
        "features": [{"type": "Feature", "geometry": line_coords(g),
                      "properties": {"name": name[p["a"]] + " – " + name[p["b"]], "geoid_a": p["a"], "geoid_b": p["b"], "workers": p["workers"],
                                     "trips": p["tt_trips"], "mode": how, **({"route": route} if route else {})}} for p, g, how, route in tt_lines],
    }
    pub_layer = {
        "type": "FeatureCollection", "vintage": PUBLICOS_AS_OF,
        "notes": {"source": doc["publicos"]["source"], "url": PUBLICOS_PAGE, "as_of": PUBLICOS_AS_OF, "licence": "Creative Commons Attribution",
                  "routes": len(routes), "between_municipios": doc["publicos"]["between_municipios"],
                  "what": "The público routes listed as active when the file was published. No timetable, fares or later updates: a route may no longer run."},
        "features": [{"type": "Feature", "geometry": line_coords(r["geom"]),
                      "properties": {"type": PUBLICO_TYPES[len(r["munis"]) > 1], "code": r["code"], "name": r["name"],
                                     "municipio": ", ".join(name[g] for g in r["munis"])}} for r in routes],
    }
    return doc, layer, pub_layer, tt_layer


def build(refresh=False, check=False):
    if check and not (CACHE / "rutas_publicos.csv").exists():
        print("transit links: nothing cached in cache/transit_links/: run python transit_links.py first")
        return 1
    go = refresh and not check
    doc, layer, pub_layer, tt_layer = assemble(cached("commuting_flows_2016_2020.xlsx", FLOWS_URL, go), cached("rutas_publicos.csv", PUBLICOS_URL, go))
    p = doc["pr"]
    log(f"transit links: {p['other_municipio']:,} workers travel between municipios ({p['other_municipio_pct']}% of {p['workers']:,}); {p['pairs']} pairs: "
        + ", ".join(f"{s} {v['pairs']} pairs {v['pct']}%" for s, v in p["by_status"].items())
        + f"; {p['simulated']} simulated connections ({p['simulated_workers']:,} workers, {p['simulated_km']:,} km); públicos {doc['publicos']['routes']} routes")
    status = 0
    for path, d in ((OUT_JSON, doc), (OUT_LINKS, layer), (OUT_PUBLICOS, pub_layer), (OUT_TT, tt_layer)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python transit_links.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
