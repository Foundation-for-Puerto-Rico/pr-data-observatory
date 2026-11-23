"""Transit supply: how much scheduled service each stop pattern, route and stop has, hour by hour (site/data/transit_supply.json).

Reads the published timetable files (trips.json, trips_sa.json, trips_su.json, format 2 with path_stops: trip_paths.py) and the feed
status of each operator (operators.json). Writes, for a weekday, Saturday and Sunday:

  patterns  one row per stop pattern (a variant of a route: the trips that stop at the same places in the same order), indexed like the
            "paths" of that day's trips file: trips per hour (by the departure from its first stop), first and last departure, trips and
            average wait between departures in four periods, median run time, length along the route line and scheduled speed
  routes    one row per operator and route label, summing its patterns (both directions)
  stops     one row per stop id (the ids of transport.json): departures per hour, routes, first and last departure, longest gap
  island    for each hour: vehicles in service, routes running, stops with a departure, stops with frequent service

Every row says whether its operator's timetable is current on the day of the build ("cur"): an expired feed may still run, or not.
Departures count every stop time except a trip's last stop (where it arrives and does not leave). Times are the published timetable,
not observed service, and públicos are in no timetable.

    python supply.py           write site/data/transit_supply.json when its content changed
    python supply.py --check   print the summary and write nothing

refresh_network.py (nightly) and build.py call apply(). Pure Python, no dependencies.
"""
import json
import sys
from datetime import date
from pathlib import Path
from statistics import median

DATA = Path(__file__).resolve().parent / "site" / "data"
DAYS = {"wk": ("trips.json", "weekday (typical Wednesday service)"), "sa": ("trips_sa.json", "Saturday"), "su": ("trips_su.json", "Sunday")}
PERIODS = {"am": (6, 9), "mid": (9, 15), "pm": (15, 19), "eve": (19, 23)}   # morning peak, midday, afternoon peak, evening (hours, end excluded)
FREQUENT = 4            # departures in an hour: a bus every 15 minutes or better
GAP_WINDOW = (6, 22)    # the longest gap at a stop is measured between 06:00 and 22:00
CURRENT = ("current", "expiring")


def _hour(sec):
    return min(23, max(0, int(sec // 3600)))


def _periods(deps):
    """Trips and average minutes between departures in each period, from departure times in seconds."""
    out = {}
    for name, (a, b) in PERIODS.items():
        n = sum(1 for s in deps if a * 3600 <= s < b * 3600)
        out[name] = {"n": n, "hw": round((b - a) * 60 / n) if n else None}
    return out


def _longest_gap(deps):
    """Minutes of the longest wait between departures inside GAP_WINDOW, counting from its start and to its end (None: no service in it)."""
    a, b = GAP_WINDOW[0] * 3600, GAP_WINDOW[1] * 3600
    inside = sorted(s for s in deps if a <= s <= b)
    if not inside:
        return None
    edges = [a] + inside + [b]
    return round(max(y - x for x, y in zip(edges, edges[1:])) / 60)


def day_supply(doc, status):
    """The supply of one day's trips file. status: {operator id: feed status}."""
    paths, pstops = doc["paths"], doc.get("path_stops") or [None] * len(doc["paths"])
    by_k = {}
    for t in doc["trips"]:
        by_k.setdefault(t["k"], []).append(t)
    cur = lambda o: status.get(o) in CURRENT

    patterns = []
    for k, trips in sorted(by_k.items()):
        t0 = trips[0]; s = t0["s"]; path = paths[k]
        deps = sorted(t["t"][0] for t in trips)
        hours = [0] * 24
        for d in deps:
            hours[_hour(d)] += 1
        run = median((t["t"][-1] - t["t"][0]) for t in trips) / 60
        km = (path[s[-1]][2] - path[s[0]][2]) / 1000
        patterns.append({"k": k, "o": t0["o"], "r": t0["r"], "m": t0["m"], "cur": cur(t0["o"]), "stops": len(s), "km": round(km, 2),
                         "trips": len(trips), "hours": hours, "first": deps[0], "last": deps[-1], "periods": _periods(deps),
                         "run_min": round(run, 1), "kmh": round(km / (run / 60), 1) if run > 0 else None,
                         "line": doc["path_kind"][k] == "line"})

    routes = {}
    for p in patterns:
        r = routes.setdefault((p["o"], p["r"]), {"o": p["o"], "r": p["r"], "m": p["m"], "cur": p["cur"], "patterns": [], "trips": 0, "hours": [0] * 24, "first": p["first"], "last": p["last"]})
        r["patterns"].append(p["k"]); r["trips"] += p["trips"]; r["hours"] = [a + b for a, b in zip(r["hours"], p["hours"])]
        r["first"] = min(r["first"], p["first"]); r["last"] = max(r["last"], p["last"])
    for r in routes.values():   # the busiest variant at the morning peak sets the route's peak wait (one direction)
        best = max((p for p in patterns if p["k"] in r["patterns"]), key=lambda p: (p["periods"]["am"]["n"], p["trips"]))
        r["peak_hw"] = best["periods"]["am"]["hw"]

    stops, missing = {}, 0
    for t in doc["trips"]:
        ids = pstops[t["k"]]
        if not ids:
            missing += 1; continue
        for sid, sec in list(zip(ids, t["t"]))[:-1]:    # the last stop is an arrival
            st = stops.setdefault(sid, {"deps": [], "routes": set(), "o": t["o"]})
            st["deps"].append(sec); st["routes"].add(t["r"])
    stop_rows = {}
    for sid, st in sorted(stops.items()):
        deps = sorted(st["deps"]); hours = [0] * 24
        for d in deps:
            hours[_hour(d)] += 1
        stop_rows[sid] = {"cur": cur(st["o"]), "n": len(deps), "hours": hours, "routes": sorted(st["routes"]), "first": deps[0], "last": deps[-1], "gap": _longest_gap(deps)}

    island = {"vehicles": [0] * 24, "routes": [0] * 24, "stops": [0] * 24, "frequent_stops": [0] * 24}
    for h in range(24):
        a, b = h * 3600, (h + 1) * 3600
        island["vehicles"][h] = sum(1 for t in doc["trips"] if t["t"][0] < b and t["t"][-1] >= a and cur(t["o"]))
        island["routes"][h] = sum(1 for r in routes.values() if r["cur"] and r["hours"][h])
        island["stops"][h] = sum(1 for s in stop_rows.values() if s["cur"] and s["hours"][h])
        island["frequent_stops"][h] = sum(1 for s in stop_rows.values() if s["cur"] and s["hours"][h] >= FREQUENT)
    return {"patterns": patterns, "routes": sorted(routes.values(), key=lambda r: (r["o"], r["r"])), "stops": stop_rows, "island": island,
            "trips_without_stop_ids": missing}


def build(data=DATA, today=None):
    ops = json.loads((data / "operators.json").read_text(encoding="utf-8"))["operators"]
    status = {o["id"]: (o.get("feed") or {}).get("status") for o in ops}
    out = {"about": "Scheduled transit service by stop pattern, route and stop, for a weekday, Saturday and Sunday (supply.py). The timetable, not observed service; públicos are in no timetable.",
           "built": (today or date.today()).isoformat(), "periods": PERIODS, "frequent_per_hour": FREQUENT, "gap_window": GAP_WINDOW, "days": {}}
    for d, (f, label) in DAYS.items():
        p = data / f
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("format") != 2:
            raise SystemExit(f"{f} is not format 2 (paths along the route lines): run python trip_paths.py first")
        out["days"][d] = {"label": label, **day_supply(doc, status)}
    return out


def apply(data=DATA, today=None, write=True):
    """Write transit_supply.json when its content (all but the build date) changed. Returns the document."""
    doc = build(data, today)
    p = data / "transit_supply.json"
    try:
        old = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        old = None
    same = old is not None and {k: v for k, v in old.items() if k != "built"} == json.loads(json.dumps({k: v for k, v in doc.items() if k != "built"}))
    wk = doc["days"].get("wk", {})
    print(f"  supply: {len(wk.get('patterns', []))} weekday stop patterns, {len(wk.get('routes', []))} routes, {len(wk.get('stops', {}))} stops with departures"
          f"{'' if not wk.get('trips_without_stop_ids') else f'; {wk['trips_without_stop_ids']} trips without stop ids'}"
          f"{'; unchanged' if same else ''}")
    if write and not same:
        p.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  wrote transit_supply.json {p.stat().st_size / 1024:.0f} KB")
    return doc


if __name__ == "__main__":
    apply(write="--check" not in sys.argv[1:])
