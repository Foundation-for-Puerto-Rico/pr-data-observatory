"""Q3/Q5 support: land links to the eastern ferry terminals, municipalities without terminals or stops, OSM stops by operator tag."""
from service import *

d = Data()
T = d.transport
res = {}

# ---- eastern links -------------------------------------------------------------------------------------------------------
ati_bus = [i for i, f in enumerate(T) if f.get("operator") == "ati" and "bus" in (f.get("modes") or [])]
ceiba = next(i for i, f in enumerate(T) if f["source"] == "ati_gtfs" and f["kind"] == "ferry_terminal" and "Ceiba" in f["name"])
dd = np.hypot(d.t_x[ati_bus] - d.t_x[ceiba], d.t_y[ati_bus] - d.t_y[ceiba])
res["ceiba_ferry_terminal_to_nearest_ati_bus_stop_km"] = round(float(dd.min()) / 1000, 1)
res["easternmost_ati_bus_stop"] = {"lng": max(T[i]["lng"] for i in ati_bus), "municipality": next(T[i]["municipality"] for i in ati_bus if T[i]["lng"] == max(T[j]["lng"] for j in ati_bus))}
others = [i for i, f in enumerate(T) if f["source"] in SCHEDULED_SOURCES and f["kind"] != "ferry_terminal"]
dd2 = np.hypot(d.t_x[others] - d.t_x[ceiba], d.t_y[others] - d.t_y[ceiba])
j = others[int(dd2.argmin())]
res["ceiba_ferry_terminal_to_nearest_other_scheduled_stop"] = {"km": round(float(dd2.min()) / 1000, 1), "operator": T[j]["operator"], "feed_status_today": str(d.t_status[j])}
faj = next(i for i, f in enumerate(T) if f["source"] == "osm_transport" and f["kind"] == "ferry_terminal" and "Fajardo" in f["name"])
sc = np.nonzero(d.t_sched)[0]
dd3 = np.hypot(d.t_x[sc] - d.t_x[faj], d.t_y[sc] - d.t_y[faj])
j = sc[int(dd3.argmin())]
res["fajardo_ferry_terminal_osm_to_nearest_scheduled_stop"] = {"m": round(float(dd3.min())), "operator": T[j]["operator"], "feed_status_today": str(d.t_status[j])}
ati_by_muni = Counter(f["municipality"] for f in T if f.get("operator") == "ati")
east = {m for m, r in d.region_of.items() if r == "Porta del Mar"}
res["ati_stops_in_porta_del_mar_by_municipality"] = {m: ati_by_muni[m] for m in sorted(east) if ati_by_muni[m]}

# ---- municipalities without terminals / stops ----------------------------------------------------------------------------------
munis = sorted(d.muni.keys())
has_bs, has_any, has_sched = Counter(), Counter(), Counter()
for f in T:
    m = f.get("municipality")
    if f["kind"] == "bus_station":
        has_bs[m] += 1
    if f["kind"] in ACCESS_KINDS:
        has_any[m] += 1
    if f["source"] in SCHEDULED_SOURCES:
        has_sched[m] += 1
res["municipalities_total"] = len(munis)
res["municipalities_without_any_bus_station"] = sum(1 for m in munis if has_bs[m] == 0)
res["municipalities_without_any_stop_station_or_terminal"] = sum(1 for m in munis if has_any[m] == 0)
res["municipalities_without_scheduled_stop"] = sum(1 for m in munis if has_sched[m] == 0)
res["taxi_stands"] = {"n": sum(1 for f in T if f["kind"] == "taxi"), "municipalities": len({f["municipality"] for f in T if f["kind"] == "taxi"})}
res["ev_charging_points"] = sum(1 for f in T if f["kind"] == "ev_charging")
res["uber_listed_municipalities"] = sum(1 for m in munis if d.muni[m].get("uber_listed"))

# ---- OSM bus stops by operator tag, and proximity to scheduled stops --------------------------------------------------------------
osm = [(i, f) for i, f in enumerate(T) if f["source"] == "osm_transport" and f["kind"] in ("bus_stop", "bus_station")]
oi = [i for i, _ in osm]
dd, _ = nearest_dist(d.t_x[oi], d.t_y[oi], d.t_x[d.t_sched], d.t_y[d.t_sched])
res["osm_bus_stops_and_stations"] = {"n": len(osm), "operator_tag_ama": sum(1 for _, f in osm if "Metropolitana" in (f.get("operator") or "")),
                                     "no_operator_tag": sum(1 for _, f in osm if not f.get("operator")),
                                     "within_30m_of_scheduled": int((dd < 30).sum()), "30_to_100m": int(((dd >= 30) & (dd < 100)).sum()), "100_to_250m": int(((dd >= 100) & (dd < 250)).sum()),
                                     "250_to_1000m": int(((dd >= 250) & (dd < 1000)).sum()), "over_1000m": int((dd >= 1000).sum())}
ama = [k for k, (_, f) in enumerate(osm) if "Metropolitana" in (f.get("operator") or "")]
res["osm_bus_stops_and_stations"]["ama_tagged_within_100m_of_scheduled"] = int((dd[ama] <= 100).sum())
dm = d.default
m = (d.t_kind == "bus_station") & (d.t_src == "osm_transport")
bd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[m], d.t_y[m])
res["default_places_within_400_800m_of_an_osm_bus_station_pct"] = [pct(int((bd[dm] <= 400).sum()), int(dm.sum())), pct(int((bd[dm] <= 800).sum()), int(dm.sum()))]
mona = dm & (d.p_lat < 18.2) & (d.p_lng < -67.8)
mx, my = d.p_x[mona], d.p_y[mona]
near = [(T[i]["kind"], T[i]["source"]) for i in range(d.n_tr) if np.hypot(d.t_x[i] - mx.mean(), d.t_y[i] - my.mean()) < 15000]
res["mona_island"] = {"default_places": int(mona.sum()), "transport_features_within_15km": [f"{k}|{s}" for k, s in near]}
write_json("q3b_east_and_osm.json", res)
print(json.dumps(res, indent=1, default=str))
