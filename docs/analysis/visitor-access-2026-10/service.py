"""Derive per-stop service from the published timetables (trips.json, trips_sa.json, trips_su.json).

Matching rule: the trip files carry only [lng, lat, seconds] per stop call (no stop ID). The timetable writer rounded each stop
coordinate to 5 decimals (network.py parse_gtfs, stop_xy) and transport.json holds the same rounded values, so a call is matched to
the scheduled stop whose (lng, lat) is IDENTICAL, restricted to the operator named on the trip (field o).
Several stop IDs of one operator can share one coordinate (same pole, two IDs); those are merged into one "stop location",
and a call counts for the location (it cannot be split between the IDs).
"""
from common import *

DAY_FILES = {"wk": "trips.json", "sa": "trips_sa.json", "su": "trips_su.json"}
KIND_RANK = {"rail_station": 4, "ferry_terminal": 3, "bus_station": 2, "transit_stop": 1}


def build_locations(d):
    """Returns (locs, stop_to_loc): locs is a list of dicts, one per (operator, lng, lat) of scheduled stops."""
    T = d.transport
    loc_of = {}
    locs = []
    stop_to_loc = {}
    for i, f in enumerate(T):
        if f["source"] not in SCHEDULED_SOURCES:
            continue
        key = (f["operator"], f["lng"], f["lat"])
        if key not in loc_of:
            loc_of[key] = len(locs)
            locs.append({"op": f["operator"], "lng": f["lng"], "lat": f["lat"], "stops": [], "kind": f["kind"], "trips_feed": 0,
                         "modes": set(), "routes": set(), "municipality": f.get("municipality"), "status": d.op_status.get(f["operator"], "")})
        k = loc_of[key]
        L = locs[k]
        L["stops"].append(i)
        L["trips_feed"] += f.get("trips_weekday", 0) or 0
        L["modes"].update(f.get("modes") or [])
        L["routes"].update(f.get("routes") or [])
        if KIND_RANK[f["kind"]] > KIND_RANK[L["kind"]]:
            L["kind"] = f["kind"]
        stop_to_loc[i] = k
    return locs, stop_to_loc, loc_of


def add_calls(d, locs, loc_of):
    """Adds wk/sa/su call counts, daytime calls (09:00-17:00 weekday) and the set of routes calling per day type."""
    unmatched = Counter()
    for day, fn in DAY_FILES.items():
        trips = jload(fn)["trips"]
        for L in locs:
            L[day] = 0
        if day == "wk":
            for L in locs:
                L["wk_day"] = 0          # departures 09:00-17:00
                L["wk_peak"] = 0         # departures 07:00-09:00 and 16:00-19:00
                L["wk_first"] = None
                L["wk_last"] = None
                L["wk_times"] = []
        for t in trips:
            o = t["o"]
            for lng, lat, s in t["p"]:
                k = loc_of.get((o, lng, lat))
                if k is None:
                    unmatched[(day, o)] += 1
                    continue
                L = locs[k]
                L[day] += 1
                if day == "wk":
                    if 9 * 3600 <= s < 17 * 3600:
                        L["wk_day"] += 1
                    if 7 * 3600 <= s < 9 * 3600 or 16 * 3600 <= s < 19 * 3600:
                        L["wk_peak"] += 1
                    L["wk_first"] = s if L["wk_first"] is None else min(L["wk_first"], s)
                    L["wk_last"] = s if L["wk_last"] is None else max(L["wk_last"], s)
                    L["wk_times"].append(s)
    return unmatched
