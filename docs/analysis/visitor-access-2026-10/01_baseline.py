"""Q1: baseline access of default-basis tourism places to transport, straight line, by stop quality.
Run: python 01_baseline.py   (about 1 minute)
Writes q1_baseline.json, q1_by_municipality.csv, q1_by_region.csv, q1_tables.md, stop_sets.json
"""
from service import *
import csv

t = timer()
d = Data()
locs, s2l, loc_of = build_locations(d)
unmatched = add_calls(d, locs, loc_of)
events_by_day = {day: int(sum(len(t_["p"]) for t_ in jload(fn)["trips"])) for day, fn in DAY_FILES.items()}
T = d.transport

t0_load = t()
# ---- stop-level flags --------------------------------------------------------------------------------------------
n = d.n_tr
sat = np.zeros(n, bool)
sun = np.zeros(n, bool)
for i, k in s2l.items():
    L = locs[k]
    sat[i] = L["sa"] > 0
    sun[i] = L["su"] > 0
trips = d.t_trips

sets = {
    "A_any_stop_twin_today": d.t_access,                                            # what the twin does now
    "A1_scheduled_any_feed": d.t_sched,                                             # scheduled, expired feeds included
    "B_current_scheduled": d.t_current,                                             # scheduled, feed not expired
    "B1_current_scheduled_trips>=1": d.t_current & (trips >= 1),
    "C10_current_trips>=10": d.t_current & (trips >= 10),
    "C20_current_trips>=20": d.t_current & (trips >= 20),
    "C40_current_trips>=40": d.t_current & (trips >= 40),
    "D_sat_current": d.t_current & sat,
    "D_sun_current": d.t_current & sun,
    "D_sat_and_sun_current": d.t_current & sat & sun,
    "D_weekday_and_sat_current_trips>=20": d.t_current & sat & (trips >= 20),
    "E_rail_or_ferry_any_source": np.isin(d.t_kind, ["rail_station", "ferry_terminal"]),
    "E1_rail_or_ferry_scheduled_current": d.t_current & np.isin(d.t_kind, ["rail_station", "ferry_terminal"]),
    "G10_any_feed_trips>=10": d.t_sched & (trips >= 10),                            # same thresholds, expired feeds included
    "G20_any_feed_trips>=20": d.t_sched & (trips >= 20),
    "G40_any_feed_trips>=40": d.t_sched & (trips >= 40),
    "G_sat_any_feed": d.t_sched & sat,
    "G_sun_any_feed": d.t_sched & sun,
    "F_osm_only_stops": d.t_access & (d.t_src == "osm_transport"),
    "F1_expired_scheduled": d.t_expired,
}
write_json("stop_sets.json", {k: int(v.sum()) for k, v in sets.items()})

# ---- distances for every place (all 35,118; the default mask is applied for the statistics) -----------------------
dist = {}
for name, m in sets.items():
    dd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[m], d.t_y[m])
    dist[name] = dd
dist_s = round(t(), 1)
print("distances done", dist_s, "s")

dm = d.default
res = {"as_of": str(AS_OF), "n_places_all": int(d.n_places), "n_default": int(dm.sum()), "stop_sets": {k: int(v.sum()) for k, v in sets.items()}}

def share(mask, name, r):
    sel = mask
    n = int(sel.sum())
    return {"n": n, "w400": int((dist[name][sel] <= 400).sum()), "w800": int((dist[name][sel] <= 800).sum()),
            "p400": pct((dist[name][sel] <= 400).sum(), n), "p800": pct((dist[name][sel] <= 800).sum(), n)}

# island, default basis
res["island"] = {name: share(dm, name, 0) for name in sets}
res["by_category"] = {c: {name: share(dm & (d.p_cat == c), name, 0) for name in sets} for c in CATS}
res["by_region"] = {r: {name: share(dm & (d.p_region == r), name, 0) for name in sets} for r in sorted(set(d.p_region) - {""})}
munis = sorted(set(d.p_muni))
res["by_municipality"] = {m: {name: share(dm & (d.p_muni == m), name, 0) for name in sets} for m in munis}

# hubs at longer reach
for name in ("E_rail_or_ferry_any_source", "E1_rail_or_ferry_scheduled_current"):
    res["island"][name]["w1600"] = int((dist[name][dm] <= 1600).sum())
    res["island"][name]["p1600"] = pct((dist[name][dm] <= 1600).sum(), dm.sum())

# types of interest (beaches, hotels, ...)
TYPES = ["Beaches", "Hotels", "Resorts", "Vacation Properties", "Lodging", "Historic Sites", "Museums", "Parks", "Restaurants", "Marinas", "Scenic Areas", "Tourist Attractions", "Nature Reserves", "Tour Operators", "Adventure Operators"]
res["by_type"] = {ty: {name: share(dm & (d.p_type == ty), name, 0) for name in ("A_any_stop_twin_today", "B_current_scheduled", "C20_current_trips>=20", "D_sat_current", "E_rail_or_ferry_any_source")} for ty in TYPES}

# ---- why a place counts as "served" today: current / expired only / OSM only -----------------------------------------
a400 = dist["A_any_stop_twin_today"] <= 400
cur400 = dist["B_current_scheduled"] <= 400
exp400 = dist["F1_expired_scheduled"] <= 400
osm400 = dist["F_osm_only_stops"] <= 400
cls = np.full(d.n_places, "far", dtype=object)
cls[a400 & cur400] = "current"
cls[a400 & ~cur400 & exp400] = "expired_only"
cls[a400 & ~cur400 & ~exp400 & osm400] = "osm_only"
res["why_served_island"] = {k: int(((cls == k) & dm).sum()) for k in ("current", "expired_only", "osm_only", "far")}

# per municipality classification
rows = []
for m in munis:
    sel = dm & (d.p_muni == m)
    nm = int(sel.sum())
    near = int((sel & a400).sum())
    cu = int((sel & (cls == "current")).sum())
    ex = int((sel & (cls == "expired_only")).sum())
    os_ = int((sel & (cls == "osm_only")).sum())
    r = res["by_municipality"][m]
    ms = d.muni.get(m, {})
    row = {"municipality": m, "region": d.region_of.get(m, ""), "places": nm,
           "pct400_any_stop": r["A_any_stop_twin_today"]["p400"], "pct400_scheduled_any_feed": r["A1_scheduled_any_feed"]["p400"],
           "pct400_current_scheduled": r["B_current_scheduled"]["p400"], "pct400_current_trips20": r["C20_current_trips>=20"]["p400"],
           "pct400_current_sat": r["D_sat_current"]["p400"], "pct400_current_sun": r["D_sun_current"]["p400"],
           "pct400_rail_ferry": r["E_rail_or_ferry_any_source"]["p400"],
           "pct800_any_stop": r["A_any_stop_twin_today"]["p800"], "pct800_current_scheduled": r["B_current_scheduled"]["p800"], "pct800_current_trips20": r["C20_current_trips>=20"]["p800"],
           "near_any_n": near, "near_current_n": cu, "near_expired_only_n": ex, "near_osm_only_n": os_,
           "share_of_near_that_is_expired_or_osm_only_pct": pct(ex + os_, near),
           "published_transit_pct": ms.get("transit_pct"),
           "muni_feed_status_today": d.op_status.get(slug(m)),
           "n_scheduled_stops_in_muni": int(sum(1 for i in range(n) if d.t_sched[i] and T[i].get("municipality") == m)),
           "n_current_stops_in_muni": int(sum(1 for i in range(n) if d.t_current[i] and T[i].get("municipality") == m)),
           "n_osm_stops_in_muni": int(sum(1 for i in range(n) if d.t_access[i] and d.t_src[i] == "osm_transport" and T[i].get("municipality") == m)),
           }
    rows.append(row)
with open(HERE / "q1_by_municipality.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
res["municipality_rows"] = rows

# regions csv
rr = []
for r_, v in res["by_region"].items():
    rr.append({"region": r_, "places": v["A_any_stop_twin_today"]["n"], **{f"{k}_p400": v[k]["p400"] for k in sets}, **{f"{k}_p800": v[k]["p800"] for k in sets}})
with open(HERE / "q1_by_region.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rr[0].keys()))
    w.writeheader()
    w.writerows(rr)

# ---- stale published fields: places.json transit_m vs recomputation from the current transport.json ---------------
dm_any = dist["A_any_stop_twin_today"]
pub = d.p_transit_m
diff = dm_any - pub
res["stale_check"] = {
    "places_all": int(d.n_places),
    "median_abs_diff_m": float(np.nanmedian(np.abs(diff))),
    "places_diff_gt_25m": int((np.abs(diff) > 25).sum()),
    "places_diff_gt_25m_default": int(((np.abs(diff) > 25) & dm).sum()),
    "flag_changes_all": int((d.p_t400 != (dm_any <= 400)).sum()),
    "flag_changes_default": int(((d.p_t400 != (dm_any <= 400)) & dm).sum()),
    "flag_published_true_now_false_default": int((d.p_t400 & ~(dm_any <= 400) & dm).sum()),
    "flag_published_false_now_true_default": int((~d.p_t400 & (dm_any <= 400) & dm).sum()),
    "jayuya_places_all": int((d.p_muni == "Jayuya").sum()),
    "jayuya_places_default": int(((d.p_muni == "Jayuya") & dm).sum()),
    "jayuya_flag_changes_default": int(((d.p_muni == "Jayuya") & dm & (d.p_t400 != (dm_any <= 400))).sum()),
    "pub_pct400_default": pct((d.p_t400 & dm).sum(), dm.sum()),
    "recomputed_pct400_default": pct(((dm_any <= 400) & dm).sum(), dm.sum()),
    "pub_pct400_default_excl_jayuya": pct((d.p_t400 & dm & (d.p_muni != "Jayuya")).sum(), (dm & (d.p_muni != "Jayuya")).sum()),
    "recomputed_pct400_default_excl_jayuya": pct(((dm_any <= 400) & dm & (d.p_muni != "Jayuya")).sum(), (dm & (d.p_muni != "Jayuya")).sum()),
}
# differences not caused by Jayuya
oth = (np.abs(diff) > 25) & (d.p_muni != "Jayuya")
res["stale_check"]["places_diff_gt_25m_excl_jayuya"] = int(oth.sum())
res["stale_check"]["flag_changes_excl_jayuya"] = int(((d.p_t400 != (dm_any <= 400)) & (d.p_muni != "Jayuya")).sum())

# ---- residents: same stop sets, block centroids ------------------------------------------------------------------
blocks = jload("population_blocks.json")
bx, by = to_xy(np.array([b[0] for b in blocks]), np.array([b[1] for b in blocks]))
bpop = np.array([b[2] for b in blocks])
tot = bpop.sum()
rres = {"population_total": int(tot)}
for name in ("A_any_stop_twin_today", "A1_scheduled_any_feed", "B_current_scheduled", "C20_current_trips>=20", "C40_current_trips>=40", "D_sat_current", "D_sat_and_sun_current", "E_rail_or_ferry_any_source"):
    m = sets[name]
    dd, _ = nearest_dist(bx, by, d.t_x[m], d.t_y[m])
    rres[name] = {"p400": pct(bpop[dd <= 400].sum(), tot), "p800": pct(bpop[dd <= 800].sum(), tot)}
res["residents"] = rres

# ---- unmatched / matching error --------------------------------------------------------------------------------------
tot_feed = sum(L["trips_feed"] for L in locs)
tot_der = sum(L["wk"] for L in locs)
by_op = defaultdict(lambda: [0, 0, 0, 0])
for L in locs:
    b = by_op[L["op"]]
    b[0] += L["trips_feed"]; b[1] += L["wk"]; b[2] += 1; b[3] += (L["wk"] < L["trips_feed"])
res["matching"] = {
    "stop_events_unmatched": sum(unmatched.values()), "events_by_day": events_by_day,
    "scheduled_stops": len(s2l), "stop_locations": len(locs),
    "locations_with_more_than_one_stop_id": int(sum(1 for L in locs if len(L["stops"]) > 1)),
    "stops_in_those_locations": int(sum(len(L["stops"]) for L in locs if len(L["stops"]) > 1)),
    "weekday_calls_feed_total": tot_feed, "weekday_calls_in_trips_json_total": tot_der,
    "locations_where_trips_json_has_fewer_calls_than_feed": int(sum(1 for L in locs if L["wk"] < L["trips_feed"])),
    "by_operator_feed_vs_file": {o: {"calls_feed": v[0], "calls_trips_json": v[1], "locations": v[2], "locations_short": v[3]} for o, v in sorted(by_op.items(), key=lambda kv: -kv[1][3]) if v[3]},
}
# weekend method check: route-calendar method B
rt = jload("transit_routes.geojson")["features"]
rflag = defaultdict(lambda: {"sa": 0, "su": 0})
for f in rt:
    p = f["properties"]
    lab = p["short_name"] or p["long_name"] or p["route_id"]
    rflag[(p["operator"], lab)]["sa"] += p["trips_saturday"]
    rflag[(p["operator"], lab)]["su"] += p["trips_sunday"]
chk = {"sat_A": 0, "sat_B": 0, "sat_B_not_A": Counter(), "sun_A": 0, "sun_B": 0, "sun_B_not_A": Counter()}
for L in locs:
    sa_b = any(rflag.get((L["op"], lab), {"sa": 0})["sa"] > 0 for lab in L["routes"])
    su_b = any(rflag.get((L["op"], lab), {"su": 0})["su"] > 0 for lab in L["routes"])
    chk["sat_A"] += L["sa"] > 0; chk["sat_B"] += sa_b
    chk["sun_A"] += L["su"] > 0; chk["sun_B"] += su_b
    if sa_b and not L["sa"] > 0: chk["sat_B_not_A"][L["op"]] += 1
    if su_b and not L["su"] > 0: chk["sun_B_not_A"][L["op"]] += 1
chk["sat_B_not_A"] = dict(chk["sat_B_not_A"]); chk["sun_B_not_A"] = dict(chk["sun_B_not_A"])
res["matching"]["weekend_method_check"] = chk

# stop-level trips distribution (current stops)
cur_tr = trips[d.t_current]
res["current_stop_trips"] = {"n": int(d.t_current.sum()), "p10": float(np.percentile(cur_tr, 10)), "median": float(np.median(cur_tr)), "p90": float(np.percentile(cur_tr, 90)),
                             "ge1": int((cur_tr >= 1).sum()), "ge10": int((cur_tr >= 10).sum()), "ge20": int((cur_tr >= 20).sum()), "ge40": int((cur_tr >= 40).sum())}

# save per-place distances for later scripts
np.savez_compressed(HERE / "q1_distances.npz", **{k: v.astype(np.float32) for k, v in dist.items()}, default=dm)
res["timing_s"] = {"loading_data_and_stop_service": round(t0_load, 1), "distances_for_15_stop_sets_35118_places": dist_s, "total": round(t(), 1)}
write_json("q1_baseline.json", res)
print("done", round(t(), 1), "s")
