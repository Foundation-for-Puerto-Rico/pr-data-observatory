"""Q3: gateways (airports, ferry terminals, rail stations, bus terminals, cruise/port facilities), ferry routes, Eastern region, Vieques, Culebra.
Names are printed only for public facilities (airports, terminals, stations); never for businesses.
"""
from service import *
import csv
import re

d = Data()
T = d.transport
locs, s2l, loc_of = build_locations(d)
add_calls(d, locs, loc_of)
res = {}
dm = d.default

# ---- inventory of gateways -----------------------------------------------------------------------------------------
inv = Counter()
for i, f in enumerate(T):
    if f["kind"] in ("airport", "ferry_terminal", "rail_station", "bus_station"):
        inv[(f["kind"], f["source"])] += 1
res["inventory_by_kind_source"] = {f"{k}|{s}": v for (k, s), v in sorted(inv.items())}
res["faa_airports"] = {"total": sum(1 for f in T if f["source"] == "faa_airports"), "public_use": sum(1 for f in T if f["source"] == "faa_airports" and f.get("public_use")),
                       "codes_public": sorted(f["code"] for f in T if f["source"] == "faa_airports" and f.get("public_use"))}
res["osm_airports"] = [{"name": f["name"] or "(no name)", "municipality": f["municipality"], "iata": f.get("iata")} for f in T if f["source"] == "osm_transport" and f["kind"] == "airport"]
res["bus_stations"] = {
    "ati": sum(1 for f in T if f["kind"] == "bus_station" and f["source"] == "ati_gtfs"),
    "muni_gtfs": sum(1 for f in T if f["kind"] == "bus_station" and f["source"] == "muni_gtfs"),
    "osm": sum(1 for f in T if f["kind"] == "bus_station" and f["source"] == "osm_transport"),
    "osm_by_municipality": dict(Counter(f["municipality"] for f in T if f["kind"] == "bus_station" and f["source"] == "osm_transport").most_common()),
    "muni_gtfs_by_operator": dict(Counter(f["operator"] for f in T if f["kind"] == "bus_station" and f["source"] == "muni_gtfs").most_common()),
}
res["ferry_terminals"] = [{"source": f["source"], "name": f["name"] or "(no name)", "municipality": f["municipality"], "operator": f.get("operator"),
                           "routes": f.get("routes"), "trips_weekday": f.get("trips_weekday"), "lat": f["lat"], "lng": f["lng"]} for f in T if f["kind"] == "ferry_terminal"]
res["rail_stations"] = {"n": sum(1 for f in T if f["kind"] == "rail_station"), "sources": dict(Counter(f["source"] for f in T if f["kind"] == "rail_station")),
                        "municipalities": dict(Counter(f["municipality"] for f in T if f["kind"] == "rail_station"))}

# cruise / port facilities in the stop data (public facility names only)
kw = re.compile(r"crucero|cruise|muelle|pier|puerto|port\b|marina|harbor|harbour|terminal mar|seaplane", re.I) if (re := __import__("re")) else None
# names are kept only for public facilities (airports, ferry terminals, stations); ordinary stop names can embed business names and are not stored
res["port_like_features_in_transport_json"] = [{"name": f["name"] if f["kind"] in ("airport", "ferry_terminal", "rail_station", "bus_station") else None, "kind": f["kind"], "source": f["source"], "municipality": f["municipality"]} for f in T if f["name"] and kw.search(f["name"])]
# places of types that relate to ports (aggregate only, no names)
res["places_port_related_types"] = {ty: int(((d.p_type == ty)).sum()) for ty in ("Marinas", "Transportation")}
oc = Counter()
for p in d.places:
    c = (p.get("overture_category") or "")
    if re.search(r"port|harbor|harbour|dock|ferry|cruise|marina|airport|bus_station|transit|train|railway|taxi|car_rental", c):
        oc[c] += 1
res["places_overture_categories_transport_related"] = dict(oc.most_common())

# ---- ferry routes ----------------------------------------------------------------------------------------------------
rt = jload("transit_routes.geojson")["features"]
fer = []
for f in rt:
    p = f["properties"]
    if p["mode"] == "ferry":
        fer.append({"operator": p["operator"], "route_id": p["route_id"], "short_name": p["short_name"], "long_name": p["long_name"],
                    "trips_weekday": p["trips_weekday"], "trips_saturday": p["trips_saturday"], "trips_sunday": p["trips_sunday"], "first": p["first"], "last": p["last"], "geometry_source": p["geometry_source"]})
def hhmm(s):
    return None if s is None else f"{int(s // 3600) % 24:02d}:{int(s % 3600 // 60):02d}"
for r in fer:
    r["first_hhmm"], r["last_hhmm"] = hhmm(r["first"]), hhmm(r["last"])
    # stops from the timetable
    stops = []
    for L in locs:
        if r["short_name"] in L["routes"] and L["op"] == r["operator"] and "ferry" in L["modes"]:
            stops.append(T[L["stops"][0]]["name"])
    r["stops"] = sorted(set(stops))
res["ferry_routes_from_routes_file"] = fer
# timetable events per ferry route and day
tt = {}
for day, fn in DAY_FILES.items():
    trips = jload(fn)["trips"]
    by = defaultdict(list)
    for t_ in trips:
        if t_["m"] == "ferry":
            by[t_["r"]].append(t_)
    tt[day] = {r: {"trips": len(v), "first": hhmm(min(x["p"][0][2] for x in v)), "last_departure": hhmm(max(x["p"][0][2] for x in v)),
                   "median_minutes_first_to_last_stop": round(float(np.median([(x["p"][-1][2] - x["p"][0][2]) / 60 for x in v])), 0),
                   "stops_per_trip_max": max(len(x["p"]) for x in v)} for r, v in sorted(by.items())}
res["ferry_trips_in_timetable_files"] = tt
# distinct ferry-timetable stop coordinates
res["ferry_stop_names_in_timetables"] = sorted({T[L["stops"][0]]["name"] for L in locs if "ferry" in L["modes"]})

# ---- link between gateways and land transit ----------------------------------------------------------------------------
gw = []
cur_idx = np.nonzero(d.t_current)[0]
bus_cur_idx = np.array([i for i in cur_idx if d.t_kind[i] in ("transit_stop", "bus_station")])
for i, f in enumerate(T):
    if f["kind"] in ("airport", "ferry_terminal", "rail_station", "bus_station") and (f["source"] != "faa_airports" or f.get("public_use")):
        if f["source"] == "osm_transport" and f["kind"] == "bus_station":
            continue   # many OSM bus stations; summarized separately
        # nearest OTHER current scheduled bus-type stop (not itself, not another ferry/rail record at this hub)
        mask = bus_cur_idx != i
        xx, yy = d.t_x[bus_cur_idx[mask]], d.t_y[bus_cur_idx[mask]]
        dd = np.hypot(xx - d.t_x[i], yy - d.t_y[i])
        n400 = int((dd <= 400).sum())
        # best weekday trips among bus stops within 400 m
        tr = d.t_trips[bus_cur_idx[mask]][dd <= 400]
        near_any_sched, _ = nearest_dist(np.array([d.t_x[i]]), np.array([d.t_y[i]]), d.t_x[d.t_sched & (np.arange(d.n_tr) != i)], d.t_y[d.t_sched & (np.arange(d.n_tr) != i)])
        gw.append({"kind": f["kind"], "source": f["source"], "name": f["name"] or "(no name)", "municipality": f["municipality"], "code": f.get("code") or f.get("iata"),
                   "nearest_current_bus_stop_m": round(float(dd.min()), 0) if len(dd) else None, "current_bus_stops_within_400m": n400, "max_weekday_trips_at_a_stop_within_400m": int(tr.max()) if len(tr) else 0,
                   "nearest_any_scheduled_stop_m": round(float(near_any_sched[0]), 0)})
res["gateway_land_links"] = gw

# ---- Eastern region, Vieques, Culebra --------------------------------------------------------------------------------
sl = np.load(HERE / "q1_distances.npz")
def reg_block(mask, label):
    n = int(mask.sum())
    out = {"label": label, "places_default": n, "by_category": {c: int((mask & (d.p_cat == c)).sum()) for c in CATS}}
    for nm, key in (("any_stop", "A_any_stop_twin_today"), ("current_scheduled", "B_current_scheduled"), ("current_trips20", "C20_current_trips>=20"), ("rail_or_ferry", "E_rail_or_ferry_any_source")):
        dd = sl[key][mask]
        out[f"pct400_{nm}"] = pct(int((dd <= 400).sum()), n)
        out[f"pct800_{nm}"] = pct(int((dd <= 800).sum()), n)
    # distance to ferry terminal, airports (public use), at wider radii
    fm = d.t_kind == "ferry_terminal"
    am = np.array([f["source"] == "faa_airports" and bool(f.get("public_use")) for f in T])
    for nm, m in (("ferry_terminal_any", fm), ("public_airport_faa", am)):
        dd, _ = nearest_dist(d.p_x[mask], d.p_y[mask], d.t_x[m], d.t_y[m])
        out[f"median_km_to_{nm}"] = round(float(np.median(dd)) / 1000, 1)
        out[f"pct_within_2km_{nm}"] = pct(int((dd <= 2000).sum()), n)
        out[f"pct_within_5km_{nm}"] = pct(int((dd <= 5000).sum()), n)
    return out
east = d.p_region == "Porta del Mar"
res["east_porta_del_mar"] = reg_block(dm & east, "Porta del Mar (PRTC Eastern region, 15 municipalities incl. Vieques and Culebra)")
res["east_mainland"] = reg_block(dm & east & ~np.isin(d.p_muni, ["Vieques", "Culebra"]), "Porta del Mar without Vieques and Culebra")
res["vieques"] = reg_block(dm & (d.p_muni == "Vieques"), "Vieques")
res["culebra"] = reg_block(dm & (d.p_muni == "Culebra"), "Culebra")
res["mona_island_places_default"] = int((dm & (d.p_lat < 18.2) & (d.p_lng < -67.8)).sum())
# all places (any confidence) for context
res["vieques"]["places_all_confidence_no_worship"] = int(((d.p_muni == "Vieques") & (d.p_type != "Places of Worship")).sum())
res["culebra"]["places_all_confidence_no_worship"] = int(((d.p_muni == "Culebra") & (d.p_type != "Places of Worship")).sum())

# stops and operators per municipality of the east
rows = []
for m in sorted([m for m, r in d.region_of.items() if r == "Porta del Mar"]):
    n_sched = sum(1 for i in range(d.n_tr) if d.t_sched[i] and T[i].get("municipality") == m)
    n_cur = sum(1 for i in range(d.n_tr) if d.t_current[i] and T[i].get("municipality") == m)
    n_exp = sum(1 for i in range(d.n_tr) if d.t_expired[i] and T[i].get("municipality") == m)
    n_osm = sum(1 for i in range(d.n_tr) if d.t_access[i] and d.t_src[i] == "osm_transport" and T[i].get("municipality") == m)
    mk = dm & (d.p_muni == m)
    dd = sl["B_current_scheduled"][mk]
    rows.append({"municipality": m, "places_default": int(mk.sum()), "scheduled_stops": n_sched, "of_which_current": n_cur, "of_which_expired": n_exp, "osm_stops": n_osm,
                 "pct400_any_stop": pct(int((sl["A_any_stop_twin_today"][mk] <= 400).sum()), int(mk.sum())), "pct400_current_scheduled": pct(int((dd <= 400).sum()), int(mk.sum())),
                 "feed_status_of_muni_operator": d.op_status.get(slug(m), "no municipal system"),
                 "airports_faa": sum(1 for f in T if f["source"] == "faa_airports" and f["municipality"] == m), "ferry_terminals": sum(1 for f in T if f["kind"] == "ferry_terminal" and f["municipality"] == m)})
res["east_rows"] = rows
# Vieques municipal system: stops, routes, trips
vq = d.op_by_id.get("vieques")
res["vieques_municipal_system"] = {"status_today": d.op_status.get("vieques"), "routes": vq["routes"], "stops": vq["stops"], "weekday_trips": vq["trips_weekday"], "feed_end": vq["feed"].get("end")}
res["culebra_municipal_system"] = {"operator_row": "culebra" in d.op_by_id, "scheduled_stops_in_municipality": sum(1 for i in range(d.n_tr) if d.t_sched[i] and T[i].get("municipality") == "Culebra"),
                                   "osm_bus_stops_in_municipality": sum(1 for f in T if f["kind"] == "bus_stop" and f["municipality"] == "Culebra")}
# all east operators
res["east_operators_status"] = {o["id"]: {"status": d.op_status[o["id"]], "end": o["feed"].get("end")} for o in d.ops["operators"] if o.get("municipality") in {m for m, r in d.region_of.items() if r == "Porta del Mar"}}

# SJU: scheduled stops within 500 m of the reference point
sju_i = next(i for i, f in enumerate(T) if f.get("code") == "SJU")
dd_ = np.hypot(d.t_x - d.t_x[sju_i], d.t_y - d.t_y[sju_i])
near_ = [int(i) for i in np.nonzero((dd_ <= 500) & d.t_current)[0]]
res["sju_stops_within_500m"] = {"n": len(near_), "distances_m": sorted(int(round(float(dd_[i]))) for i in near_), "routes": sorted({r for i in near_ for r in (T[i].get("routes") or [])}),
                                "max_weekday_calls": max(T[i]["trips_weekday"] for i in near_), "walk_minutes_min_max": [round(float(dd_[near_].min()) / (4800 / 60), 1), round(float(dd_[near_].max()) / (4800 / 60), 1)]}
# cruise pier to Terminal Covadonga
pier_ = next(i for i, f in enumerate(T) if f["kind"] == "ferry_terminal" and "cruise" in (f["name"] or "").lower())
cov_ = next(i for i, f in enumerate(T) if f["source"] == "ati_gtfs" and f["kind"] == "bus_station" and "covadonga" in f["name"].lower())
res["cruise_pier_to_terminal_covadonga_m"] = int(round(float(np.hypot(d.t_x[pier_] - d.t_x[cov_], d.t_y[pier_] - d.t_y[cov_]))))
# Vieques: places near the municipal bus stops, near the ATI ferry terminals, near either
mk_ = dm & (d.p_muni == "Vieques")
bus_ = d.t_current & (d.t_op == "vieques")
fer_ = d.t_current & (d.t_kind == "ferry_terminal") & (np.abs(d.t_lng + 65.47) < 0.1) & (d.t_lat < 18.2)
db_, _ = nearest_dist(d.p_x[mk_], d.p_y[mk_], d.t_x[bus_], d.t_y[bus_])
df_, _ = nearest_dist(d.p_x[mk_], d.p_y[mk_], d.t_x[fer_], d.t_y[fer_])
res["vieques_places_default"] = int(mk_.sum())
res["vieques_pct400_municipal_bus_stops"] = pct(int((db_ <= 400).sum()), int(mk_.sum()))
res["vieques_pct400_ati_ferry_terminals"] = pct(int((df_ <= 400).sum()), int(mk_.sum()))
res["vieques_pct400_either"] = pct(int(((db_ <= 400) | (df_ <= 400)).sum()), int(mk_.sum()))
res["vieques_ati_ferry_terminals_counted"] = int(fer_.sum())
res["rail_weekday_trips_values"] = sorted({int(T[i]["trips_weekday"]) for i in range(d.n_tr) if T[i]["kind"] == "rail_station"})
# Ceiba: OSM ferry nodes near the ATI Ceiba terminal
ceiba_ati = next(i for i, f in enumerate(T) if f["source"] == "ati_gtfs" and f["kind"] == "ferry_terminal" and "Ceiba" in f["name"])
res["osm_ferry_nodes_in_ceiba_m_from_ati_terminal"] = sorted(int(round(float(np.hypot(d.t_x[i] - d.t_x[ceiba_ati], d.t_y[i] - d.t_y[ceiba_ati])))) for i, f in enumerate(T) if f["source"] == "osm_transport" and f["kind"] == "ferry_terminal" and f["municipality"] == "Ceiba")
write_json("q3_gateways.json", res)
print(json.dumps({k: v for k, v in res.items() if k not in ("gateway_land_links", "ferry_terminals", "osm_airports", "east_rows")}, indent=1, default=str)[:9000])
print("GATEWAY LINKS")
for g in res["gateway_land_links"]:
    print(g)
print("EAST ROWS")
for r in res["east_rows"]:
    print(r)
