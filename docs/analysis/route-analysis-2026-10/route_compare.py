"""Compares every bus route of the ATI and of the municipal systems that connect with it on six measures.

Municipal systems included: those with a stop within 250 m of an ATI stop (San Juan, Bayamón, Guaynabo, Caguas, Canóvanas).
The eastern municipal systems (Fajardo, Humacao, Juncos, San Lorenzo, Patillas, Vieques) are included too, flagged as not meeting
the ATI network (region "este"); km_to_ati is the straight-line distance from the route's nearest stop to the nearest ATI stop.

  python route_compare.py      read site/data (trips.json, transit_routes.geojson, transport.json, population_blocks.json) and this
                               folder's road_features.geojson, road_flow.csv, transit_exposure.csv and transit_runtime.csv (from the
                               road-features analysis, README.md); write route_compare.csv and route_compare.json

Weekday timetables (typical Wednesday). For each route:

  1 service       weekday trips (both directions), first and last departure, and the peak headway: 180 minutes divided by
                  the trips that leave 6:00-9:00 on the route's busiest stop pattern (one direction)
  2 length/speed  length of the route's main stop pattern (the one with most trips) and its scheduled average speed
                  (length / median scheduled time from first to last stop)
  3 congestion    junctions with a design-hour volume of 2,000 vehicles an hour or more on its path, per 10 km, and how often its trips
                  pass them 6:00-9:00 and 16:00-19:00 (transit_exposure.csv). The flow is an estimate of the design-hour volume: HPMS
                  2024 AADT times the K factor of the busiest road within 30 m (road_flow.csv). K is the design-hour volume (the
                  30th-busiest hour of the year) as a percentage of AADT (HPMS Field Manual, item 26), required only on Sample Panel
                  sections; where a road has none (k_imputed, 764 of 1,582 junctions) the class median K is the observatory's own
                  estimate, which HPMS guidance does not endorse. So the 2,000 vehicles an hour apply to a design hour, not a typical
                  weekday peak
  4 timetable     scheduled time of the main pattern for trips leaving 6:00-9:00 against 10:00-14:00 (transit_runtime.py)
  5 connections   whether a stop is within 300 m of a Tren Urbano station, and the other operators with a stop within 250 m
  supplementary   footbridges (OpenStreetMap) within 30 m of the route's path
  6 residents     residents (2020 Census blocks, block centroid) within 400 m in a straight line of any of its stops, each
                  block counted once per route

A route whose operator's timetable had expired on TODAY is flagged (timetable_expired): its schedule may not be today's service. The
page computes the same flag again from feed_end and the date it is read, so a timetable that expires later (Canóvanas: 2026-10-31)
is flagged from that day on.

Timetable only (timepoints_only). Bayamón's, Caguas's, Juncos's and San Lorenzo's timetables give a time at two stops of each trip
(start and end), and so does ATI's express route 20 (two stops). For such a route (main pattern with two timed stops) the operator's
route line in transit_routes.geojson gives the length and the junctions on its path, and the rush-hour passes are estimated as trips
leaving 6:00-9:00 times busy junctions (passes_estimated true). Stops come from transport.json (every stop listed for the route), not
only the timed ones. The line can hold both directions or a loop: Bayamón BR-1's line is 32.1 km, its timed path 16.0 km (one way),
so length_km is then the length of the line drawn, not of one trip. Speed is the timed path over the median timed run, and is left
blank when the timed path is under half the line (the timed stretch is not the whole trip: Bayamón BR-1, BR-2, BR-3, BT-1; Caguas
Green, Orange, Purple; Juncos Bo. Juncos Pueblo, Bo. Ceiba Norte y Bo. Ceiba Sur).
"""
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
DATA = ROOT / "site" / "data"
OPERATORS = {"ati": "ATI (AMA)", "san_juan": "San Juan", "bayamon": "Bayamón", "guaynabo": "Guaynabo", "caguas": "Caguas", "canovanas": "Canóvanas",
             "fajardo": "Fajardo", "humacao": "Humacao", "juncos": "Juncos", "san_lorenzo": "San Lorenzo", "patillas": "Patillas", "vieques": "Vieques"}
EAST = {"fajardo", "humacao", "juncos", "san_lorenzo", "patillas", "vieques"}
AM = (6 * 3600, 9 * 3600)
KX = 111320 * math.cos(math.radians(18.2))
KY = 110574
TODAY = "2026-10-19"


def xy(lng, lat):
    return (lng * KX, lat * KY)


def hhmm(s):
    return f"{s // 3600}:{s % 3600 // 60:02d}"


def main():
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    trips = json.loads((DATA / "trips.json").read_text(encoding="utf-8"))
    stops = {f["id"]: f for f in json.loads((DATA / "transport.json").read_text(encoding="utf-8"))}
    routes_geo = json.loads((DATA / "transit_routes.geojson").read_text(encoding="utf-8"))
    names = {}
    for f in routes_geo["features"]:
        p = f["properties"]
        for key in {str(p["route_id"]), str(p.get("short_name") or ""), str(p.get("long_name") or "")} - {""}:
            names.setdefault((p["operator"], key), p)
    expo = {(r["operator"], r["route"]): r for r in csv.DictReader(open(HERE / "transit_exposure.csv", encoding="utf-8"))}
    runtime = defaultdict(list)
    for r in csv.DictReader(open(HERE / "transit_runtime.csv", encoding="utf-8")):
        runtime[(r["operator"], r["route"], int(r["pattern"]))].append(r)
    feed_end = {}
    for s in stops.values():
        if s.get("operator") and s.get("feed_end"):
            feed_end[s["operator"]] = s["feed_end"]

    rail = [Point(*xy(s["lng"], s["lat"])) for s in stops.values() if s["kind"] == "rail_station"]
    rail_tree = STRtree(rail)
    other = [(Point(*xy(s["lng"], s["lat"])), s.get("operator_name") or s.get("operator")) for s in stops.values()
             if s["kind"] in ("transit_stop", "bus_stop", "bus_station", "ferry_terminal") and s.get("operator")]
    other_tree = STRtree([p for p, _ in other])
    ati_pts = [Point(*xy(s["lng"], s["lat"])) for s in stops.values() if s.get("operator") == "ati" and s["kind"] == "transit_stop"]
    ati_tree = STRtree(ati_pts)
    op_of_other = [s.get("operator") for s in stops.values() if s["kind"] in ("transit_stop", "bus_stop", "bus_station", "ferry_terminal") and s.get("operator")]
    blocks = json.loads((DATA / "population_blocks.json").read_text(encoding="utf-8"))
    bpts = [Point(*xy(b[0], b[1])) for b in blocks]
    btree = STRtree(bpts)

    from shapely.geometry import LineString, MultiLineString, shape
    lines = {}
    for f in routes_geo["features"]:
        p = f["properties"]
        geom = shape(f["geometry"]) if f.get("geometry") else None
        if geom is None:
            continue
        parts = list(geom.geoms) if geom.geom_type == "MultiLineString" else [geom]
        parts = [LineString([xy(*c[:2]) for c in g.coords]) for g in parts if len(g.coords) >= 2]
        if parts:
            longest = max(parts, key=lambda g: g.length)
            for key in {str(p["route_id"]), str(p.get("short_name") or ""), str(p.get("long_name") or "")} - {""}:
                lines.setdefault((p["operator"], key), longest)
    rf = json.loads((HERE / "road_features.geojson").read_text(encoding="utf-8"))
    flow = {r["osm_ids"]: r for r in csv.DictReader(open(HERE / "road_flow.csv", encoding="utf-8"))}
    busy_pts = [Point(*xy(*f["geometry"]["coordinates"])) for f in rf["features"]
                if f["properties"]["kind"] in ("traffic_signals", "roundabout")
                and flow.get(f["properties"]["osm_ids"], {}).get("peak_main") and int(flow[f["properties"]["osm_ids"]]["peak_main"]) >= 2000]
    busy_tree = STRtree(busy_pts)
    foot_pts = [Point(*xy(*f["geometry"]["coordinates"])) for f in rf["features"] if f["properties"]["kind"] == "footbridge"]
    foot_tree = STRtree(foot_pts)
    route_stops = defaultdict(set)
    for sid, st in stops.items():
        for rr in st.get("routes") or []:
            route_stops[(st.get("operator"), str(rr))].add(sid)

    by_route = defaultdict(list)
    for t in trips["trips"]:
        if t["o"] in OPERATORS and t["m"] == "bus":
            by_route[(t["o"], t["r"])].append(t)

    rows = []
    for (op, r), T in sorted(by_route.items(), key=lambda kv: (list(OPERATORS).index(kv[0][0]), len(kv[0][1]), kv[0][1])):
        pat = Counter(t["k"] for t in T)
        main_k = pat.most_common(1)[0][0]
        path = trips["paths"][main_k]
        length_km = path[-1][2] / 1000 if path else None
        timepoints_only = len(trips["path_stops"][main_k]) <= 2
        line = lines.get((op, r))
        path_km = length_km
        if timepoints_only and line is not None:
            length_km = line.length / 1000
        runs = [t["t"][-1] - t["t"][0] for t in T if t["k"] == main_k and len(t["t"]) >= 2]
        speed = path_km / (statistics.median(runs) / 3600) if path_km and runs and statistics.median(runs) > 0 else None
        # the timed stretch is only part of the route (two timed stops close together): no speed. An express with two stops
        # (ATI 20, Bayamón - Campanilla) has a full path between them and keeps its speed.
        if timepoints_only and line is not None and path_km and path_km < 0.5 * length_km:
            speed = None
        express = timepoints_only and speed is not None
        am_by_k = Counter(t["k"] for t in T if AM[0] <= t["t"][0] < AM[1])
        am_max = max(am_by_k.values()) if am_by_k else 0
        starts = [t["t"][0] for t in T]
        e = expo.get((op, r), {})
        busy = int(e.get("busy_junctions_on_path") or 0)
        passes_am, passes_pm, estimated = int(e.get("busy_passes_6_9") or 0), int(e.get("busy_passes_16_19") or 0), False
        if timepoints_only and line is not None:
            busy = sum(1 for j in busy_tree.query(line.buffer(20)) if busy_pts[j].distance(line) <= 20)
            n_am = sum(1 for t in T if AM[0] <= t["t"][0] < AM[1])
            n_pm = sum(1 for t in T if 16 * 3600 <= t["t"][0] < 19 * 3600)
            passes_am, passes_pm, estimated = n_am * busy, n_pm * busy, True
        # supplementary: footbridges (OpenStreetMap) within 30 m of the route's path, every pattern (or its line)
        geoms = [LineString([xy(c[0], c[1]) for c in trips["paths"][k]]) for k in pat if len(trips["paths"][k]) >= 2]
        if timepoints_only and line is not None:
            geoms = [line]
        feet = {j for g_ in geoms for j in foot_tree.query(g_.buffer(30)) if foot_pts[j].distance(g_) <= 30}
        rt = runtime.get((op, r, main_k)) or []
        rt = max(rt, key=lambda x: int(x["trips_peak"]) + int(x["trips_midday"])) if rt else None
        # stops of every pattern the route uses
        sids = {sid for k in pat for sid in trips["path_stops"][k]} | route_stops.get((op, r), set())
        spts = [Point(*xy(stops[s]["lng"], stops[s]["lat"])) for s in sids if s in stops]
        tren = any(rail[j].distance(p) <= 300 for p in spts for j in rail_tree.query(p.buffer(300)))
        ops = set()
        for p in spts:
            for j in other_tree.query(p.buffer(250)):
                if op_of_other[j] != op and other[j][0].distance(p) <= 250:
                    ops.add(other[j][1])
        km_ati = min(ati_pts[ati_tree.nearest(p_)].distance(p_) for p_ in spts) / 1000 if spts else None
        near = set()
        for p in spts:
            near.update(j for j in btree.query(p.buffer(400)) if bpts[j].distance(p) <= 400)
        residents = sum(blocks[j][2] for j in near)
        g = names.get((op, r), {})
        rows.append({
            "operator": op, "operator_name": OPERATORS[op], "region": "este" if op in EAST else "metro", "route": r, "name": g.get("long_name") or g.get("short_name") or r,
            "timetable_expired": bool(feed_end.get(op) and feed_end[op] < TODAY),
            "weekday_trips": len(T), "first": hhmm(min(starts)), "last": hhmm(max(starts)),
            "peak_trips_one_direction": am_max, "peak_headway_min": round(180 / am_max) if am_max else "",
            "length_km": round(length_km, 1) if length_km else "", "speed_kmh": round(speed, 1) if speed else "",
            "busy_junctions": busy, "busy_per_10km": round(10 * busy / length_km, 1) if length_km else "",
            "busy_passes_6_9": passes_am, "busy_passes_16_19": passes_pm, "passes_estimated": estimated, "timepoints_only": timepoints_only, "express_two_stops": express,
            "minutes_peak": rt["minutes_peak"] if rt else "", "minutes_midday": rt["minutes_midday"] if rt else "",
            "peak_extra_pct": rt["peak_extra_pct"] if rt else "",
            "reaches_tren_urbano": tren, "other_operators": len(ops), "other_operator_names": "; ".join(sorted(ops)),
            "stops": len(spts), "residents_400m": residents, "footbridges_30m": len(feet),
            "km_to_ati": round(km_ati, 1) if km_ati is not None else "",
        })
    cols = list(rows[0].keys())
    with open(HERE / "route_compare.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    out = {"day": trips["day"], "as_of": TODAY, "operators": OPERATORS, "feed_end": {k: feed_end.get(k) for k in OPERATORS},
           "routes": rows, "by_operator": {op: {"routes": sum(1 for x in rows if x["operator"] == op),
                                                "weekday_trips": sum(x["weekday_trips"] for x in rows if x["operator"] == op),
                                                "with_busy_junctions": sum(1 for x in rows if x["operator"] == op and x["busy_junctions"])}
                                           for op in OPERATORS}}
    (HERE / "route_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["by_operator"], ensure_ascii=False))
    print("routes", len(rows))
    for x in sorted(rows, key=lambda x: -x["busy_passes_6_9"])[:6]:
        print(" ", {k: x[k] for k in ("operator", "route", "weekday_trips", "peak_headway_min", "length_km", "speed_kmh", "busy_junctions", "busy_passes_6_9", "peak_extra_pct", "reaches_tren_urbano", "other_operators", "residents_400m")})


if __name__ == "__main__":
    main()
