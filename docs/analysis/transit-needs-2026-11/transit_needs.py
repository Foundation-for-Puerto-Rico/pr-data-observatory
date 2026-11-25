"""Where a new route or connection is most needed: phase 5 of docs/transit-network-analysis-plan-2026-10.md, from open data only.

  python docs/analysis/transit-needs-2026-11/transit_needs.py            read site/data; write barrios.csv, connections.csv, summary.json,
                                                                           findings.md and findings_es.md in this folder
  python docs/analysis/transit-needs-2026-11/transit_needs.py --check    recompute for the date in summary.json and compare (exit 1 if
                                                                           the files are not what site/data gives)
  --as-of YYYY-MM-DD   the day a timetable must still run on to count as current (default: today; --check uses summary.json's)

No download, no key. A planning aid for FPR's review, not a demand forecast or an engineering study; a public recommendation of new
routes is a policy position that needs FPR leadership's approval before it is published (the plan's decision 4). README.md explains the
method and its limits. It brings together:

  need        (phase 4, proxies)  ACS 2020-2024 by barrio: households with no vehicle (counted twice), poverty, residents 65 and over,
                                  residents with a disability, and residents per km2 (2020 Census blocks over the barrio's land): each a
                                  percentile among the barrios with 500 residents or more, averaged into a need index of 0 to 100
  useful      (phase 2)           a stop whose operator's timetable runs on the as-of day, with 2 or more weekday departures an hour on
                                  average 7:00-19:00 (a bus every 30 minutes or better through the day; transit_supply.json); a block
                                  counts as served when its point is within 400 m in a straight line of one
  gap                             the share of a barrio's residents (2020 Census blocks) beyond 400 m of a useful stop, and the car-free
                                  households that share gives (households x no-vehicle share x unserved share: an even spread is assumed)
  priority                        half the percentile of need x gap, half the percentile of car-free households without useful service
  connections (phase 3)           pairs of current routes of different operators whose lines come within 250 to 800 m of each other with
                                  no pair of their stops within 250 m: a short link or a new stop could join them. Ranked by the
                                  residents within 800 m of the closest point, then by the weekday trips of the less frequent route
"""
import csv
import io
import json
import math
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "site" / "data"

ACS_YEAR = "2024"            # the 2020-2024 window, the newest in acs_barrio.json
MIN_RES = 500                # barrios with fewer residents are listed but not ranked (their percentages swing on a few households)
SERVED_M = 400               # straight line, as exposure.py's stop_* measures
USEFUL_PER_HOUR = 2          # weekday departures an hour on average 7:00-19:00
DAY = (7, 19)
NEAR_M = 1500                # a useful stop this close counts as reachable by a short extension or feeder
LINK = (250, 800)            # a connection candidate: lines this close, no stops within 250 m of each other
STOP_PAIR_M = 250
CATCH_M = 800
SAMPLE_M = 100               # points along each route line
NEED_WEIGHTS = {"no_vehicle_hh_pct": 2, "poverty_pct": 1, "acs_age65plus_pct": 1, "acs_disability_pct": 1, "density": 1}
TOP = 25


# ── geometry (meters on a local plane: Puerto Rico spans 1.3 degrees of latitude) ───────────────────────────────────────────────
KX, KY = 111320 * math.cos(math.radians(18.2)), 110574


def xy(lon, lat):
    return lon * KX, lat * KY


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Grid:
    """Points in square cells, for the points within a distance of another."""
    def __init__(self, cell):
        self.cell, self.cells = cell, {}

    def add(self, p, item):
        self.cells.setdefault((int(p[0] // self.cell), int(p[1] // self.cell)), []).append((p, item))

    def near(self, p, r):
        n, cx, cy = int(math.ceil(r / self.cell)), int(p[0] // self.cell), int(p[1] // self.cell)
        for i in range(cx - n, cx + n + 1):
            for j in range(cy - n, cy + n + 1):
                for q, item in self.cells.get((i, j), ()):
                    d = dist(p, q)
                    if d <= r:
                        yield d, item


def in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def in_polygon(x, y, rings):   # the first ring is the outline, the others holes
    return in_ring(x, y, rings[0]) and not any(in_ring(x, y, h) for h in rings[1:])


def polygons(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def sample_line(coords, step):
    """Points every `step` meters along a line of lon, lat pairs, both ends included."""
    pts = [xy(*coords[0])]
    for a, b in zip(coords, coords[1:]):
        pa, pb = xy(*a), xy(*b)
        n = max(1, int(dist(pa, pb) // step))
        pts += [(pa[0] + (pb[0] - pa[0]) * k / n, pa[1] + (pb[1] - pa[1]) * k / n) for k in range(1, n + 1)]
    return pts


def pct_rank(values):
    """Each value's percentile (0-100) among the values: ties share their mean rank; None stays None."""
    have = sorted(v for v in values if v is not None)
    if len(have) < 2:
        return [None if v is None else 50.0 for v in values]
    first, last = {}, {}
    for i, v in enumerate(have):
        first.setdefault(v, i); last[v] = i
    return [None if v is None else 100 * (first[v] + last[v]) / 2 / (len(have) - 1) for v in values]


# ── inputs ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
INPUTS = ("acs_barrio.json", "barrios.geojson", "operators.json", "transport.json", "transit_supply.json", "population_blocks.json", "transit_routes.geojson")


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def fingerprints():
    """sha256 (first 16 hex) of each input in site/data, so --check can tell 'the inputs moved on' (the nightly transit refresh) from 'the outputs are wrong'."""
    import hashlib
    return {n: hashlib.sha256((DATA / n).read_bytes()).hexdigest()[:16] for n in INPUTS}


def current_operators(operators, as_of):
    """Operator ids whose timetable runs on the as-of day (the feed's end date, as the site reads it)."""
    return {o["id"] for o in operators["operators"] if (o.get("feed") or {}).get("end") and o["feed"]["end"] >= as_of}


def slug(name):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn").lower().replace(" ", "_")


def municipal_feeds(operators, as_of):
    """Each municipality's own transit system, as operators.json lists it: 'current', 'expired' (with its end date) or 'none' (a system
    is known, with no published timetable). A municipality not in the list has no system listed ('unlisted')."""
    out = {}
    for o in operators["operators"]:
        if o.get("type") != "municipal":
            continue
        end = (o.get("feed") or {}).get("end")
        out[slug(o.get("municipality") or o["id"].replace("_", " "))] = ("current", end) if end and end >= as_of else ("expired", end) if end else ("none", None)
    return out


def useful_stop(sup, operator_ok):
    hours = sup["hours"][DAY[0]:DAY[1]]
    return operator_ok and sum(hours) / len(hours) >= USEFUL_PER_HOUR


def stop_service(stops, supply_wk):
    """Weekday departures by hour at each stop: transit_supply.json's, or, for a stop it has none for (the systems that time only the
    first and last stop of a trip: Bayamón, Caguas, Jayuya, Juncos, Patillas, San Lorenzo, San Sebastián, Vega Baja), an estimate from
    its routes: their trips by hour, halved for the two directions (estimated true)."""
    route_hours = {(r["o"], str(r["r"])): r["hours"] for r in supply_wk["routes"]}
    out = {}
    for sid, st in stops.items():
        got = supply_wk["stops"].get(sid)
        if got:
            out[sid] = {"hours": got["hours"], "routes": [str(r) for r in got["routes"]], "estimated": False}
            continue
        rs = [str(r) for r in st.get("routes") or [] if (st["operator"], str(r)) in route_hours]
        if rs:
            out[sid] = {"hours": [sum(route_hours[(st["operator"], r)][h] for r in rs) / 2 for h in range(24)], "routes": rs, "estimated": True}
    return out


def inputs(as_of):
    acs, bar, ops = load("acs_barrio.json"), load("barrios.geojson"), load("operators.json")
    stops = {s["id"]: s for s in load("transport.json") if s.get("kind") == "transit_stop"}
    sup = stop_service(stops, load("transit_supply.json")["days"]["wk"])
    return acs, bar, ops, stops, sup, load("population_blocks.json"), load("transit_routes.geojson"), current_operators(ops, as_of)


# ── barrios: need, service and gap ──────────────────────────────────────────────────────────────────────────────────────────────
def barrios(acs, bar, stops, sup, blocks, cur_ops):
    ids = acs["geo"]["ids"]
    var = {v["key"]: v for v in acs["vars"]}
    col = lambda k: var[k]["years"][ACS_YEAR]
    moe = lambda k: var[k]["moe"][ACS_YEAR]
    feats = {f["properties"]["geoid"]: f for f in bar["features"]}

    # the stops: useful ones (in a grid), and any stop whose timetable runs today
    useful, anycur = Grid(SERVED_M), Grid(SERVED_M)
    farstops = Grid(NEAR_M)
    for sid, s in sup.items():
        st = stops[sid]
        op = st["operator"]
        p = xy(st["lng"], st["lat"])
        if op in cur_ops:
            anycur.add(p, sid)
            if useful_stop(s, True):
                useful.add(p, sid); farstops.add(p, sid)

    # the blocks into their barrio (point in polygon, boxes first)
    boxes = []
    for g, f in feats.items():
        polys = [[[xy(*c) for c in ring] for ring in poly] for poly in polygons(f["geometry"])]
        xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
        boxes.append((min(xs), min(ys), max(xs), max(ys), g, polys))
    bgrid = Grid(5000)
    for b in boxes:
        for i in range(int(b[0] // 5000), int(b[2] // 5000) + 1):
            for j in range(int(b[1] // 5000), int(b[3] // 5000) + 1):
                bgrid.cells.setdefault((i, j), []).append(((0, 0), b))
    agg = {g: {"pop": 0, "served": 0, "served_any": 0, "unserved_pts": []} for g in feats}
    for blk in blocks:
        lon, lat, pop = blk[0], blk[1], blk[2]
        if not pop:
            continue
        p = xy(lon, lat)
        home = next((b[4] for _, b in bgrid.cells.get((int(p[0] // 5000), int(p[1] // 5000)), ())
                     if b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3] and any(in_polygon(p[0], p[1], poly) for poly in b[5])), None)
        if home is None:
            continue
        a = agg[home]; a["pop"] += pop
        if next(useful.near(p, SERVED_M), None):
            a["served"] += pop
        else:
            a["unserved_pts"].append((p, pop))
        if next(anycur.near(p, SERVED_M), None):
            a["served_any"] += pop

    rows = []
    for i, g in enumerate(ids):
        f = feats.get(g)
        if not f:
            continue
        pr, a = f["properties"], agg[g]
        res, hh, nv = col("acs_population")[i], col("households")[i], col("no_vehicle_hh_pct")[i]
        km2 = pr.get("km2") or None
        unserved = 1 - a["served"] / a["pop"] if a["pop"] else None
        carfree = hh * nv / 100 if hh is not None and nv is not None else None
        nv_moe = moe("no_vehicle_hh_pct")[i]
        # where the unserved live (residents' center) and the nearest useful stop from there
        near = None
        if a["unserved_pts"]:
            w = sum(pp for _, pp in a["unserved_pts"])
            c = (sum(p[0] * pp for p, pp in a["unserved_pts"]) / w, sum(p[1] * pp for p, pp in a["unserved_pts"]) / w)
            near = min(farstops.near(c, NEAR_M), default=None, key=lambda t: t[0])
        rows.append({
            "geoid": g, "barrio": pr["barrio"], "municipality": pr["municipality"], "km2": km2,
            "residents_acs": res, "residents_2020": a["pop"], "households": hh,
            "no_vehicle_hh_pct": nv, "no_vehicle_moe": nv_moe,
            "poverty_pct": col("poverty_pct")[i], "acs_age65plus_pct": col("acs_age65plus_pct")[i], "acs_disability_pct": col("acs_disability_pct")[i],
            "density": round(a["pop"] / km2, 1) if km2 else None,
            "served_useful_pct": round(100 * a["served"] / a["pop"], 1) if a["pop"] else None,
            "served_current_pct": round(100 * a["served_any"] / a["pop"], 1) if a["pop"] else None,
            "unserved_share": unserved,
            "carfree_hh": round(carfree) if carfree is not None else None,
            "carfree_unserved": round(carfree * unserved) if carfree is not None and unserved is not None else None,
            "nearest_useful_m": round(near[0]) if near else None, "nearest_useful_stop": near[1] if near else None,
            "reliability": "low" if nv is None or nv == 0 or (nv_moe is not None and nv_moe > nv) else "ok",
        })

    ranked = [r for r in rows if (r["residents_acs"] or 0) >= MIN_RES and r["residents_2020"] >= MIN_RES]
    parts = {k: pct_rank([r[k] for r in ranked]) for k in NEED_WEIGHTS}
    for n, r in enumerate(ranked):
        ok = [(NEED_WEIGHTS[k], parts[k][n]) for k in NEED_WEIGHTS if parts[k][n] is not None]
        r["need"] = round(sum(w * v for w, v in ok) / sum(w for w, _ in ok), 1) if ok else None
    gapneed = pct_rank([r["need"] * r["unserved_share"] if r["need"] is not None and r["unserved_share"] is not None else None for r in ranked])
    count = pct_rank([r["carfree_unserved"] for r in ranked])
    for n, r in enumerate(ranked):
        r["priority"] = round((gapneed[n] + count[n]) / 2, 1) if gapneed[n] is not None and count[n] is not None else None
    ranked.sort(key=lambda r: (-(r["priority"] or -1), r["geoid"]))
    for k, r in enumerate(ranked, 1):
        r["rank"] = k
    return rows


def action(r, stops, sup):
    """What kind of change the barrio's gap points to, from where its unserved residents live (a reading aid, not a design)."""
    if r["served_useful_pct"] is None:
        return "empty", None   # no 2020 Census block with residents in the barrio
    if r["served_useful_pct"] >= 80:
        return "served", None
    if r["served_current_pct"] - r["served_useful_pct"] >= 20:
        return "frequency", None   # stops with a current timetable are near, but with less than a bus every 30 minutes
    if r["nearest_useful_stop"]:
        st = stops[r["nearest_useful_stop"]]
        return "extension", {"stop": st["name"], "operator": st.get("operator_name") or st["operator"], "routes": sup[st["id"]]["routes"], "m": r["nearest_useful_m"]}
    return "new", None


# ── connections between operators ──────────────────────────────────────────────────────────────────────────────────────────────
def connections(routes, stops, blocks, cur_ops):
    lines = []
    for f in routes["features"]:
        p = f["properties"]
        if p["operator"] not in cur_ops or not p.get("trips_weekday"):
            continue
        parts = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiLineString" else [f["geometry"]["coordinates"]]
        pts = [q for part in parts if len(part) > 1 for q in sample_line(part, SAMPLE_M)]
        rid = {str(p.get("route_id")), str(p.get("short_name"))}
        own = [xy(s["lng"], s["lat"]) for s in stops.values() if s["operator"] == p["operator"] and rid & set(map(str, s.get("routes") or []))]
        lines.append({"op": p["operator"], "opname": p.get("operator_name") or p["operator"], "route": p.get("short_name") or p.get("route_id"),
                      "name": p.get("long_name") or "", "trips": p["trips_weekday"], "pts": pts, "stops": own})
    grid = Grid(LINK[1])
    for k, ln in enumerate(lines):
        for q in ln["pts"]:
            grid.add(q, k)
    sgrid = Grid(STOP_PAIR_M)
    for k, ln in enumerate(lines):
        for q in ln["stops"]:
            sgrid.add(q, k)
    best = {}
    for a, ln in enumerate(lines):
        for q in ln["pts"]:
            for d, b in grid.near(q, LINK[1]):
                if b <= a or lines[b]["op"] == ln["op"]:
                    continue
                if (a, b) not in best or d < best[(a, b)][0]:
                    best[(a, b)] = (d, q)
    linked = set()
    for a, ln in enumerate(lines):
        for q in ln["stops"]:
            for _, b in sgrid.near(q, STOP_PAIR_M):
                if lines[b]["op"] != ln["op"]:
                    linked.add((min(a, b), max(a, b)))
    pgrid = Grid(CATCH_M)
    for blk in blocks:
        if blk[2]:
            pgrid.add(xy(blk[0], blk[1]), blk[2])
    pairs = []
    for (a, b), (d, q) in best.items():
        if d < LINK[0] or (a, b) in linked:
            continue
        A, B = lines[a], lines[b]
        pairs.append({"operator_a": A["opname"], "route_a": A["route"], "name_a": A["name"], "trips_a": A["trips"],
                      "operator_b": B["opname"], "route_b": B["route"], "name_b": B["name"], "trips_b": B["trips"],
                      "gap_m": round(d), "lat": round(q[1] / KY, 5), "lng": round(q[0] / KX, 5), "_p": q,
                      "residents_800m": sum(pop for _, pop in pgrid.near(q, CATCH_M))})
    pairs.sort(key=lambda c: (-c["residents_800m"], -min(c["trips_a"], c["trips_b"]), c["gap_m"], c["route_a"], c["route_b"]))
    # one place for the pairs whose closest points are within 400 m of a pair already placed: several routes of one corridor meet there
    places = []
    for c in pairs:
        home = next((pl for pl in places if dist(pl["_p"], c["_p"]) <= 400), None)
        if home is None:
            home = {"_p": c["_p"], "lat": c["lat"], "lng": c["lng"], "residents_800m": c["residents_800m"], "gap_m": c["gap_m"], "pairs": []}
            places.append(home)
        home["pairs"].append(c); home["gap_m"] = min(home["gap_m"], c["gap_m"])
    for k, pl in enumerate(places, 1):
        pl["rank"] = k
        for c in pl["pairs"]:
            c["place"] = k
    return pairs, places


# ── outputs ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
BAR_COLS = ["rank", "priority", "need", "geoid", "barrio", "municipality", "residents_acs", "residents_2020", "households", "no_vehicle_hh_pct",
            "no_vehicle_moe", "reliability", "carfree_hh", "carfree_unserved", "poverty_pct", "acs_age65plus_pct", "acs_disability_pct", "density",
            "served_useful_pct", "served_current_pct", "nearest_useful_m", "municipal_timetable", "municipal_timetable_end", "timetable_known", "action", "action_detail"]
CON_COLS = ["place", "operator_a", "route_a", "name_a", "trips_a", "operator_b", "route_b", "name_b", "trips_b", "gap_m", "residents_800m", "lat", "lng"]

ACTION = {
    "en": {"empty": "no residents in the 2020 Census blocks", "served": "already served", "frequency": "more frequent service on the current stops", "new": "new service (no stop with a bus every 30 minutes within 1.5 km)",
           "extension": "extend or feed {routes} ({operator}): the nearest stop with a bus every 30 minutes, {stop}, is {m} m from where the unserved residents live"},
    "es": {"empty": "sin residentes en los bloques del Censo 2020", "served": "ya tiene servicio", "frequency": "más frecuencia en las paradas que ya tiene", "new": "servicio nuevo (ninguna parada con guagua cada 30 minutos a 1.5 km o menos)",
           "extension": "extender o alimentar {routes} ({operator}): la parada más cercana con guagua cada 30 minutos, {stop}, está a {m} m de donde vive la población sin servicio"},
}


def action_text(lang, kind, det):
    if kind != "extension":
        return ACTION[lang][kind]
    rs = ", ".join(det["routes"][:3])
    routes = ("route " if lang == "en" else "la ruta ") + rs if len(det["routes"]) == 1 else ("routes " if lang == "en" else "las rutas ") + rs
    return ACTION[lang]["extension"].format(routes=routes, operator=det["operator"], stop=det["stop"], m=f"{det['m']:,}")


FEED = {"en": {"current": "current", "expired": "expired {end}", "none": "none published", "unlisted": "no system listed"},
        "es": {"current": "vigente", "expired": "vencido {end}", "none": "no publica", "unlisted": "sin sistema en la lista"}}


def feed_text(lang, r):
    return FEED[lang][r["municipal_timetable"]].format(end=r["municipal_timetable_end"])


def short_op(name):   # "Autoridad de Transporte Integrado (ATI)" -> "ATI"; "City of San Juan" -> "San Juan"
    if "(" in name:
        return name[name.index("(") + 1:name.index(")")]
    for p in ("City of ", "Municipality of ", "Municipio de ", "Municipio Autónomo de "):
        if name.startswith(p):
            return name[len(p):]
    return name


def to_csv(rows, cols):
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r[k]) for k in cols})
    return buf.getvalue()


def fmt(v, d=0):
    return "" if v is None else f"{v:,.{d}f}"


def findings(lang, as_of, top, solid, cons, summary):
    en = lang == "en"
    L = []
    L.append("# " + ("Where a new route or connection is most needed: findings" if en else "Dónde hace más falta una ruta o una conexión nueva: hallazgos"))
    L.append("")
    L.append(("Written by `transit_needs.py` for timetables running on " if en else "Escrito por `transit_needs.py` con los horarios vigentes el ") + f"{as_of}. " +
             ("A planning aid for FPR's review, not a demand forecast or an engineering study. Read `README.md` for the method and its limits; "
              "públicos are in no timetable, so a barrio without timetabled service may still have públicos." if en else
              "Es una ayuda de planificación para que FPR la revise, no un pronóstico de demanda ni un estudio de ingeniería. El método y sus límites están en `README.md`; "
              "los públicos no tienen horario publicado, así que un barrio sin servicio con horario puede tener públicos."))
    L.append("")
    s = summary
    L.append("## " + ("Island summary" if en else "Resumen de la isla"))
    L.append("")
    if en:
        L.append(f"- {fmt(s['residents_2020'])} residents (2020 Census blocks); {fmt(s['served_useful_pct'], 1)}% live within 400 m of a stop with a bus every 30 minutes or better through the weekday, "
                 f"{fmt(s['served_current_pct'], 1)}% within 400 m of any stop with a current timetable.")
        L.append(f"- About {fmt(s['carfree_hh'])} households have no vehicle (ACS 2020-2024); about {fmt(s['carfree_unserved'])} of them live in the unserved share of their barrio.")
        L.append(f"- {s['ranked']} barrios with {MIN_RES} residents or more are ranked; {s['current_operators']} operators have a timetable running on {as_of}.")
    else:
        L.append(f"- {fmt(s['residents_2020'])} residentes (bloques del Censo 2020); el {fmt(s['served_useful_pct'], 1)}% vive a 400 m o menos de una parada con guagua cada 30 minutos o mejor durante el día laborable, "
                 f"y el {fmt(s['served_current_pct'], 1)}% a 400 m o menos de cualquier parada con horario vigente.")
        L.append(f"- Unos {fmt(s['carfree_hh'])} hogares no tienen vehículo (ACS 2020-2024); unos {fmt(s['carfree_unserved'])} viven en la parte sin servicio de su barrio.")
        L.append(f"- Se ordenan {s['ranked']} barrios con {MIN_RES} residentes o más; {s['current_operators']} operadores tienen horario vigente el {as_of}.")
    L.append("")
    L.append("## " + (f"The {TOP} barrios to look at first" if en else f"Los {TOP} barrios para mirar primero"))
    L.append("")
    head = (["#", "Barrio", "Municipio", "Priority", "Need", "Car-free households", "without useful service", "Useful service", "Municipal timetable", "What the gap points to"] if en else
            ["#", "Barrio", "Municipio", "Prioridad", "Necesidad", "Hogares sin vehículo", "sin servicio útil", "Servicio útil", "Horario municipal", "Qué sugiere la brecha"])
    L.append("| " + " | ".join(head) + " |"); L.append("|" + "---|" * len(head))
    for r in top:
        flag = "" if r["reliability"] == "ok" else (" (low reliability)" if en else " (poca confiabilidad)")
        L.append(f"| {r['rank']} | {r['barrio']} | {r['municipality']} | {fmt(r['priority'], 1)} | {fmt(r['need'], 1)} | {fmt(r['carfree_hh'])} ({fmt(r['no_vehicle_hh_pct'], 1)}%){flag} | "
                 f"{fmt(r['carfree_unserved'])} | {fmt(r['served_useful_pct'], 1)}% | {feed_text(lang, r)} | {action_text(lang, r['action'], r['_det'])} |")
    L.append("")
    L.append(("Useful service: residents within 400 m (straight line) of a stop with a bus every 30 minutes or better, 7:00-19:00 on a weekday. "
              "Low reliability: the margin of error of the no-vehicle share is larger than the share itself. "
              f"Municipal timetable: the municipality's own system in `operators.json`. **{s['top_with_timetable_gap']} of these {TOP} barrios are in a municipality whose system "
              "publishes no timetable or whose timetable has expired**: there the gap may be in the data, not in the service, and the first step is to confirm with the "
              "municipality what runs (and to obtain its timetable)." if en else
              "Servicio útil: residentes a 400 m o menos (en línea recta) de una parada con guagua cada 30 minutos o mejor, de 7:00 a 19:00 en día laborable. "
              "Poca confiabilidad: el margen de error del porcentaje sin vehículo es mayor que el porcentaje. "
              f"Horario municipal: el sistema propio del municipio en `operators.json`. **{s['top_with_timetable_gap']} de estos {TOP} barrios están en un municipio cuyo sistema "
              "no publica horario o lo tiene vencido**: ahí la brecha puede estar en los datos y no en el servicio, y el primer paso es confirmar con el municipio "
              "qué servicio opera (y conseguir su horario)."))
    L.append("")
    L.append("## " + ("Where the timetables are current: the gaps the data can show" if en else "Donde los horarios están vigentes: las brechas que los datos sí muestran"))
    L.append("")
    L.append(("The same ranking, only the barrios of municipalities whose own system has a current timetable, or that list no system of their own and have ATI stops "
              "(the ATI's timetable is current). Here a gap is a gap in the published service." if en else
              "La misma lista, solo con los barrios de municipios cuyo sistema propio tiene horario vigente, o que no tienen sistema propio en la lista y tienen paradas de la ATI "
              "(el horario de la ATI está vigente). Aquí una brecha es una brecha en el servicio publicado."))
    L.append("")
    head = (["#", "Barrio", "Municipio", "Priority", "Car-free households without useful service", "Useful service", "Any current stop", "What the gap points to"] if en else
            ["#", "Barrio", "Municipio", "Prioridad", "Hogares sin vehículo sin servicio útil", "Servicio útil", "Alguna parada vigente", "Qué sugiere la brecha"])
    L.append("| " + " | ".join(head) + " |"); L.append("|" + "---|" * len(head))
    for r in solid[:15]:
        L.append(f"| {r['rank']} | {r['barrio']} | {r['municipality']} | {fmt(r['priority'], 1)} | {fmt(r['carfree_unserved'])} | {fmt(r['served_useful_pct'], 1)}% | "
                 f"{fmt(r['served_current_pct'], 1)}% | {action_text(lang, r['action'], r['_det'])} |")
    L.append("")
    L.append("## " + ("Connections between operators to look at first" if en else "Conexiones entre operadores para mirar primero"))
    L.append("")
    head = (["#", "Where", "Routes that come close", "Closest gap", "Residents within 800 m"] if en else ["#", "Dónde", "Rutas que se acercan", "Distancia mínima", "Residentes a 800 m"])
    L.append("| " + " | ".join(head) + " |"); L.append("|" + "---|" * len(head))
    trips = "trips" if en else "viajes"
    for pl in cons[:15]:
        seen, names = set(), []
        for c in pl["pairs"]:
            for o, r, t in ((c["operator_a"], c["route_a"], c["trips_a"]), (c["operator_b"], c["route_b"], c["trips_b"])):
                if (o, r) not in seen:
                    seen.add((o, r)); names.append(f"{short_op(o)} {r} ({fmt(t)} {trips})")
        L.append(f"| {pl['rank']} | {pl['lat']}, {pl['lng']} | {'; '.join(names)} | {fmt(pl['gap_m'])} m | {fmt(pl['residents_800m'])} |")
    L.append("")
    npairs = sum(len(pl["pairs"]) for pl in cons)
    L.append((f"{npairs} pairs of current routes of different operators come within {LINK[0]} to {LINK[1]} m of each other with no stops within {STOP_PAIR_M} m, at "
              f"{len(cons)} places (pairs whose closest points are within 400 m count as one place): a short link, a new stop or a timed transfer could join them. "
              "Trips are weekday trips in both directions. Every pair is in `connections.csv`." if en else
              f"{npairs} pares de rutas vigentes de operadores distintos pasan a {LINK[0]}-{LINK[1]} m una de otra sin paradas a {STOP_PAIR_M} m o menos, en "
              f"{len(cons)} lugares (los pares cuyos puntos más cercanos están a 400 m o menos cuentan como un lugar): un enlace corto, una parada nueva o un trasbordo "
              "coordinado podría unirlas. Los viajes son de día laborable, en ambas direcciones. Todos los pares están en `connections.csv`."))
    L.append("")
    return "\n".join(L)


def build(as_of):
    acs, bar, ops, stops, sup, blocks, routes, cur_ops = inputs(as_of)
    feeds = municipal_feeds(ops, as_of)
    rows = barrios(acs, bar, stops, sup, blocks, cur_ops)
    for r in rows:
        kind, det = action(r, stops, sup)
        r["action"], r["_det"] = kind, det
        r["action_detail"] = action_text("en", kind, det) if kind == "extension" else ""
        r["municipal_timetable"], r["municipal_timetable_end"] = feeds.get(slug(r["municipality"]), ("unlisted", None))
        if r.get("unserved_share") is not None:
            r["unserved_share"] = round(r["unserved_share"], 4)
    ranked = sorted((r for r in rows if r.get("rank")), key=lambda r: r["rank"])
    pairs, cons = connections(routes, stops, blocks, cur_ops)
    ati_munis = {st.get("municipality") for st in stops.values() if st["operator"] == "ati"}
    for r in rows:   # the gap is one of published service: the municipality's own timetable is current, or it lists no system of its own and the ATI serves it
        r["timetable_known"] = r["municipal_timetable"] == "current" or (r["municipal_timetable"] == "unlisted" and r["municipality"] in ati_munis)
    solid = [r for r in ranked if r["timetable_known"]]
    pop = sum(r["residents_2020"] for r in rows)
    served = sum(r["residents_2020"] * r["served_useful_pct"] / 100 for r in rows if r["served_useful_pct"] is not None)
    served_any = sum(r["residents_2020"] * r["served_current_pct"] / 100 for r in rows if r["served_current_pct"] is not None)
    summary = {"as_of": as_of, "acs_window": f"{int(ACS_YEAR) - 4}-{ACS_YEAR}", "residents_2020": pop,
               "served_useful_pct": round(100 * served / pop, 1), "served_current_pct": round(100 * served_any / pop, 1),
               "carfree_hh": sum(r["carfree_hh"] or 0 for r in rows), "carfree_unserved": sum(r["carfree_unserved"] or 0 for r in rows),
               "barrios": len(rows), "ranked": len(ranked), "connection_pairs": len(pairs), "connection_places": len(cons), "current_operators": len(cur_ops),
               "stops_with_service": len(sup), "stops_estimated": sum(1 for x in sup.values() if x["estimated"]),
               "top_with_timetable_gap": sum(1 for r in ranked[:TOP] if r["municipal_timetable"] in ("expired", "none")),
               "inputs": fingerprints(),
               "rules": {"useful_per_hour": USEFUL_PER_HOUR, "day": list(DAY), "served_m": SERVED_M, "min_residents": MIN_RES, "near_m": NEAR_M,
                         "link_m": list(LINK), "stop_pair_m": STOP_PAIR_M, "catch_m": CATCH_M, "need_weights": NEED_WEIGHTS}}
    out = {
        "barrios.csv": to_csv(ranked + sorted((r for r in rows if not r.get("rank")), key=lambda r: r["geoid"]), BAR_COLS),
        "connections.csv": to_csv(pairs, CON_COLS),
        "summary.json": json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
        "findings.md": findings("en", as_of, ranked[:TOP], solid, cons, summary) + "\n",
        "findings_es.md": findings("es", as_of, ranked[:TOP], solid, cons, summary) + "\n",
    }
    return out


def main(argv):
    as_of = argv[argv.index("--as-of") + 1] if "--as-of" in argv else date.today().isoformat()
    if "--check" in argv:
        snap = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
        as_of = snap["as_of"]
        moved = [n for n, h in fingerprints().items() if snap.get("inputs", {}).get(n) != h]
        if moved:   # a snapshot: site/data changed after it was made (the nightly refresh), which is not an error
            print("transit_needs: the inputs changed since " + as_of + " (" + ", ".join(moved) + "); rerun with --as-of to refresh the snapshot")
            return 2
        bad = [n for n, t in build(as_of).items() if not (HERE / n).exists() or (HERE / n).read_text(encoding="utf-8") != t]
        print("transit_needs: " + ("current" if not bad else "out of date: " + ", ".join(bad)))
        return 1 if bad else 0
    for n, t in build(as_of).items():
        (HERE / n).write_text(t, encoding="utf-8", newline="\n")
    s = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    print(f"transit_needs ({as_of}): {s['ranked']} barrios ranked of {s['barrios']}, {s['connection_pairs']} route pairs at {s['connection_places']} places; "
          f"useful service {s['served_useful_pct']}% of residents, any current stop {s['served_current_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
