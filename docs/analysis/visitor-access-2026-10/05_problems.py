"""Q5: data problems that would distort the analysis, with counts. Nothing printed here names an individual business or address."""
from service import *
from walknet import *
import shapely
from shapely.geometry import shape
import re

d = Data()
T = d.transport
dm = d.default
res = {}
locs, s2l, loc_of = build_locations(d)
um = add_calls(d, locs, loc_of)

# ---- feeds -------------------------------------------------------------------------------------------------------------
feeds = []
for o in d.ops["operators"]:
    f = o["feed"]
    if o["stops"]:
        end = f.get("end")
        feeds.append({"operator": o["id"], "status_today": d.op_status[o["id"]], "end": end, "stops": o["stops"], "routes": o["routes"], "weekday_trips": o["trips_weekday"],
                      "days_since_end": (AS_OF - date.fromisoformat(end)).days if end else None, "weekend_service": f.get("weekend_service"), "has_shapes": f.get("has_shapes"), "order_issue_routes": f.get("order_issue")})
res["feeds_with_stops"] = feeds
res["operators_total"] = len(d.ops["operators"])
res["operators_by_type_and_feed"] = {t_: dict(Counter(("with feed" if o["stops"] else o["feed"]["status"]) for o in d.ops["operators"] if o["type"] == t_)) for t_ in sorted({o["type"] for o in d.ops["operators"]})}
res["operators_by_status_today"] = dict(Counter(d.op_status.values()))
res["scheduled_stops_by_status"] = dict(Counter(str(s) for s in d.t_status[d.t_sched]))
res["scheduled_stops_total"] = int(d.t_sched.sum())
res["expired_stops"] = int(d.t_expired.sum())
res["expired_stop_share_pct"] = pct(int(d.t_expired.sum()), int(d.t_sched.sum()))
res["expiring_within_60_days_stops"] = int((d.t_sched & (d.t_status == "expiring")).sum())
res["muni_operators_with_no_public_feed"] = sum(1 for o in d.ops["operators"] if o["feed"]["status"] == "none")
res["muni_systems_with_feed"] = sum(1 for o in d.ops["operators"] if o["type"] == "municipal" and o["stops"] > 0)
# places depending on expired feeds
q1 = read_json("q1_baseline.json")
res["default_places_near_only_expired_or_osm"] = q1["why_served_island"]

# ---- stale places fields ------------------------------------------------------------------------------------------------
res["stale"] = read_json("q1b_stale_check.json")

# ---- Jayuya ------------------------------------------------------------------------------------------------------------
jay = [f for f in T if f.get("operator") == "jayuya"]
res["jayuya"] = {"stops_in_transport_json": len(jay), "lng_min": min(f["lng"] for f in jay), "lng_max": max(f["lng"] for f in jay), "all_negative_longitude": all(f["lng"] < 0 for f in jay),
                 "municipality_values": dict(Counter(f["municipality"] for f in jay))}

# ---- municipality of stops ------------------------------------------------------------------------------------------------
mg = jload("municipios.geojson")
geoms, names = [], []
for ft in mg["features"]:
    n = ft["properties"].get("municipality")
    if n:
        geoms.append(shape(ft["geometry"])); names.append(n)
# project polygons to metres for distances
import pyproj
from shapely.ops import transform
tr_ = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32161", always_xy=True).transform
pgeoms = [transform(tr_, g) for g in geoms]
ptree = STRtree(pgeoms)
nomuni = [i for i, f in enumerate(T) if not f.get("municipality")]
rows = []
for i in nomuni:
    pt = shapely.Point(d.t_x[i], d.t_y[i])
    j = ptree.nearest(pt)
    rows.append({"kind": T[i]["kind"], "source": T[i]["source"], "operator": T[i].get("operator"), "dist_to_nearest_municipality_polygon_m": round(float(pgeoms[j].distance(pt)), 0), "nearest_municipality": names[j]})
res["stops_without_municipality"] = {"n": len(nomuni), "by_kind": dict(Counter((r["kind"], r["source"]) for r in rows)) if False else dict(Counter(f"{r['kind']}|{r['source']}" for r in rows)),
                                     "max_dist_to_polygon_m": max(r["dist_to_nearest_municipality_polygon_m"] for r in rows), "rows": rows}
# municipal operators: stops far outside their own municipality
op_muni = {o["id"]: next((n_ for n_ in names if slug(n_) == o["id"]), None) for o in d.ops["operators"] if o["type"] == "municipal" and o["stops"]}
op_muni = {k: v for k, v in op_muni.items() if v}
far = []
for i, f in enumerate(T):
    if f["source"] == "muni_gtfs" and f["operator"] in op_muni and op_muni[f["operator"]] in names:
        j = names.index(op_muni[f["operator"]])
        dist = float(pgeoms[j].distance(shapely.Point(d.t_x[i], d.t_y[i])))
        if dist > 3000:
            far.append({"operator": f["operator"], "dist_to_own_municipality_m": round(dist), "kind": f["kind"]})
res["municipal_stops_more_than_3km_outside_own_municipality"] = {"n": len(far), "by_operator": dict(Counter(r["operator"] for r in far)), "max_m": max([r["dist_to_own_municipality_m"] for r in far], default=None)}
far5 = [r for r in far if r["dist_to_own_municipality_m"] > 10000]
res["municipal_stops_more_than_10km_outside_own_municipality"] = {"n": len(far5), "by_operator": dict(Counter(r["operator"] for r in far5))}

# ---- stops far from any road -----------------------------------------------------------------------------------------------
net = from_roads_bin()
sidx = np.nonzero(d.t_sched)[0]
e150, _, c150 = net.snap(d.t_x[sidx], d.t_y[sidx], 150.0)
e500, _, c500 = net.snap(d.t_x[sidx], d.t_y[sidx], 500.0)
res["scheduled_stops_not_within_150m_of_road_graph"] = {"n": int((e150 < 0).sum()), "by_kind": dict(Counter(str(d.t_kind[sidx][e150 < 0][k]) for k in range(int((e150 < 0).sum())))),
                                                        "by_operator": dict(Counter(str(d.t_op[sidx][e150 < 0][k]) for k in range(int((e150 < 0).sum())))),
                                                        "not_within_500m": int((e500 < 0).sum())}

# ---- duplicates ---------------------------------------------------------------------------------------------------------------
osm_m = d.t_access & (d.t_src == "osm_transport")
sch_m = d.t_sched
# scheduled stop within 30 m of an OSM stop (should be zero after the build's fold)
def pairs_within(mask_a, mask_b, r, same_set=False):
    ia, ib = np.nonzero(mask_a)[0], np.nonzero(mask_b)[0]
    tree = STRtree(points(d.t_x[ib], d.t_y[ib]))
    i, j = tree.query(points(d.t_x[ia], d.t_y[ia]), predicate="dwithin", distance=r)
    pa, pb = ia[i], ib[j]
    if same_set:
        keep = pa < pb
        return pa[keep], pb[keep]
    return pa, pb
a, b = pairs_within(osm_m, sch_m, 30)
res["osm_stops_within_30m_of_scheduled"] = int(len(set(a.tolist())))
a, b = pairs_within(osm_m, sch_m, 100)
res["osm_stops_within_100m_of_scheduled"] = int(len(set(a.tolist())))
res["osm_access_stops_total"] = int(osm_m.sum())
a, b = pairs_within(sch_m, sch_m, 30, same_set=True)
cross = [(x, y) for x, y in zip(a, b) if d.t_op[x] != d.t_op[y]]
same = [(x, y) for x, y in zip(a, b) if d.t_op[x] == d.t_op[y]]
res["scheduled_stop_pairs_within_30m"] = {"total": int(len(a)), "same_operator": len(same), "different_operators": len(cross),
                                          "different_operator_pairs_by_operators": dict(Counter(tuple(sorted((str(d.t_op[x]), str(d.t_op[y])))).__repr__() for x, y in cross).most_common(8))}
res["scheduled_stops_sharing_exact_coordinates_with_another_stop_id"] = {"locations": int(sum(1 for L in locs if len(L["stops"]) > 1)), "stops": int(sum(len(L["stops"]) for L in locs if len(L["stops"]) > 1))}
a, b = pairs_within(osm_m, osm_m, 10, same_set=True)
res["osm_stop_pairs_within_10m"] = int(len(a))
# hubs: OSM station/terminal near a scheduled one of the same kind
hub_osm = np.nonzero(osm_m & np.isin(d.t_kind, ["bus_station", "ferry_terminal", "rail_station"]))[0]
hub_sch = np.nonzero(sch_m & np.isin(d.t_kind, ["bus_station", "ferry_terminal", "rail_station"]))[0]
cnt = 0
for i in hub_osm:
    dd = np.hypot(d.t_x[hub_sch] - d.t_x[i], d.t_y[hub_sch] - d.t_y[i])
    if len(dd) and dd.min() <= 500:
        cnt += 1
res["osm_station_or_terminal_within_500m_of_scheduled_hub"] = {"osm_hubs": int(len(hub_osm)), "within_500m_of_a_scheduled_hub": cnt}

# ---- stops/routes/trips mismatches ------------------------------------------------------------------------------------------
res["scheduled_stops_with_no_route"] = int(sum(1 for f in T if f["source"] in SCHEDULED_SOURCES and not f.get("routes")))
res["scheduled_stops_with_zero_weekday_trips"] = int(sum(1 for f in T if f["source"] in SCHEDULED_SOURCES and f.get("trips_weekday", 0) == 0))
res["scheduled_stops_with_zero_weekday_trips_but_with_routes"] = int(sum(1 for f in T if f["source"] in SCHEDULED_SOURCES and f.get("trips_weekday", 0) == 0 and f.get("routes")))
res["locations_with_zero_calls_in_all_three_trip_files"] = int(sum(1 for L in locs if L["wk"] == 0 and L["sa"] == 0 and L["su"] == 0))
res["current_locations_with_zero_calls_in_all_three_trip_files"] = int(sum(1 for L in locs if L["wk"] == 0 and L["sa"] == 0 and L["su"] == 0 and L["status"] in ("current", "expiring")))
res["current_stops_without_weekend_service"] = {"current_stops": int(d.t_current.sum())}
sat = np.zeros(d.n_tr, bool); sun = np.zeros(d.n_tr, bool)
for i, k in s2l.items():
    sat[i] = locs[k]["sa"] > 0; sun[i] = locs[k]["su"] > 0
res["current_stops_with_saturday_service"] = int((d.t_current & sat).sum())
res["current_stops_with_sunday_service"] = int((d.t_current & sun).sum())
# feed vs file
rt = jload("transit_routes.geojson")["features"]
file_by_route = Counter()
for t_ in jload("trips.json")["trips"]:
    file_by_route[(t_["o"], t_["r"])] += 1
mism = []
for f in rt:
    p = f["properties"]
    if p["operator"] == "osm":
        continue
    lab = p["short_name"] or p["long_name"] or p["route_id"]
    n_file = file_by_route.get((p["operator"], lab), 0)
    if n_file != p["trips_weekday"]:
        mism.append((p["operator"], lab, p["trips_weekday"], n_file, bool(p.get("order_note"))))
res["routes_where_trips_json_count_differs_from_routes_file"] = {"routes_checked": sum(1 for f in rt if f["properties"]["operator"] != "osm"), "differing": len(mism), "by_operator": dict(Counter(m[0] for m in mism)),
                                                                  "routes_with_zero_trips_in_file_but_trips_in_feed": sum(1 for m in mism if m[3] == 0 and m[2] > 0), "of_which_order_issue": sum(1 for m in mism if m[3] == 0 and m[4])}
res["routes_with_order_note_non_geographic_stop_order"] = {"n": sum(1 for f in rt if f["properties"].get("order_note")), "by_operator": dict(Counter(f["properties"]["operator"] for f in rt if f["properties"].get("order_note")))}
res["osm_routes_without_timetable"] = sum(1 for f in rt if f["properties"]["operator"] == "osm")
# calls dropped from the trip files
q1m = q1["matching"]
res["weekday_calls"] = {"feed_total": q1m["weekday_calls_feed_total"], "in_trips_json": q1m["weekday_calls_in_trips_json_total"],
                        "share_missing_pct": pct(q1m["weekday_calls_feed_total"] - q1m["weekday_calls_in_trips_json_total"], q1m["weekday_calls_feed_total"]),
                        "by_operator": q1m["by_operator_feed_vs_file"]}
# implausible hops in the timetable files
bad = Counter(); tot = Counter()
bad_hops = []
for fn in ("trips.json", "trips_sa.json", "trips_su.json"):
    for t_ in jload(fn)["trips"]:
        if t_["m"] != "bus":
            continue
        p = t_["p"]
        px, py = to_xy([e[0] for e in p], [e[1] for e in p])
        for k in range(len(p) - 1):
            dist = math.hypot(px[k + 1] - px[k], py[k + 1] - py[k])
            dt = p[k + 1][2] - p[k][2]
            tot[t_["o"]] += 1
            if dist > 500:
                if dt <= 0:
                    bad[(t_["o"], "zero_or_negative_time_over_500m")] += 1
                elif dist / dt > 100 / 3.6:    # straight-line speed above 100 km/h
                    bad[(t_["o"], "straight_line_speed_over_100kmh")] += 1
                elif dist > 20000:
                    bad[(t_["o"], "hop_over_20km")] += 1
res["implausible_bus_hops_in_trip_files"] = {"hops_checked": int(sum(tot.values())), "flagged": int(sum(bad.values())), "by_operator_and_type": {f"{k[0]}|{k[1]}": v for k, v in bad.most_common(12)}}

# ---- places file -----------------------------------------------------------------------------------------------------------
keys = Counter()
for p in d.places:
    keys.update(p.keys())
res["places_fields"] = sorted(keys)
res["places_with_name_address_website"] = {"name": keys["name"], "address": keys["address"], "website": keys["website"]}
cc = Counter((round(p["lat"], 5), round(p["lng"], 5)) for i, p in enumerate(d.places) if d.default[i])
res["default_places_sharing_a_point_with_another_default_place"] = {"distinct_points": len(cc), "places_in_shared_points": int(sum(v for v in cc.values() if v > 1)), "max_places_at_one_point": max(cc.values())}
# offshore / outside any municipality polygon
ptree_wgs = STRtree(geoms)
inside = np.zeros(d.n_places, bool)
pts_ll = points(d.p_lng, d.p_lat)
i, j = ptree_wgs.query(pts_ll, predicate="within")
inside[np.unique(i)] = True
res["places_outside_every_municipality_polygon"] = {"all": int((~inside).sum()), "default": int((~inside & dm).sum())}
# personal data screen of the published stop and operator files (existence only)
raw_t = (DATA / "transport.json").read_text(encoding="utf-8")
raw_o = (DATA / "operators.json").read_text(encoding="utf-8")
res["pii_screen"] = {"transport_json_has_email_pattern": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw_t)), "operators_json_has_email_pattern": bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw_o)),
                     "operators_json_has_personal_cloud_link": bool(re.search(r"-my\.sharepoint\.com|onedrive\.live\.com|1drv\.ms", raw_o)),
                     "places_json_carries_business_name_address_website_fields": True,
                     "stop_names_that_embed_a_business_or_organisation_name": "yes (not counted, not printed)"}
# population blocks: 4th value
blocks = jload("population_blocks.json")
res["population_blocks_fourth_value"] = {"meaning": "metres to the nearest scheduled stop, capped at 9,999 (network.py coverage), NOT housing units", "n_blocks": len(blocks), "n_capped_9999": int(sum(1 for b in blocks if b[3] >= 9999)),
                                         "includes_expired_feeds": True}
# airports
res["faa_airports_in_file"] = 14
res["faa_airports_note"] = "HANDOFF: published transport.json still has the old 14 until the next full build (the source host changed)"
write_json("q5_problems.json", res)
print(json.dumps({k: v for k, v in res.items() if k not in ("places_fields", "feeds_with_stops", "stale")}, indent=1, default=str)[:14000])
