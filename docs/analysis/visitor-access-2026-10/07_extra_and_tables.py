"""Extra numbers for the report and the markdown tables (generated from the JSON results, so the report copies, not retypes, the numbers)."""
from service import *
import csv

d = Data()
T = d.transport
dm = d.default
res = {}
locs, s2l, loc_of = build_locations(d)
add_calls(d, locs, loc_of)
Q1 = np.load(HERE / "q1_distances.npz")
q1 = read_json("q1_baseline.json")

# sensitivity: 'expiring' feeds (Canovanas, ends 2026-10-31) counted as not current
exp_m = d.t_sched & (d.t_status == "current")
dd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[exp_m], d.t_y[exp_m])
res["current_only_excluding_expiring_feed"] = {"pct400": pct(int((dd[dm] <= 400).sum()), int(dm.sum())), "pct800": pct(int((dd[dm] <= 800).sum()), int(dm.sum())), "expiring_feed_stops": int((d.t_sched & (d.t_status == "expiring")).sum())}
# locations whose feed lists weekday trips but whose calls are all missing from the trip files
miss = [L for L in locs if L["trips_feed"] > 0 and L["wk"] == 0]
res["locations_with_feed_trips_but_zero_calls_in_trips_json"] = {"n": len(miss), "of_total_locations": len(locs), "current_feeds_n": sum(1 for L in miss if L["status"] in ("current", "expiring")), "by_operator": dict(Counter(L["op"] for L in miss).most_common())}
# the one Jayuya stop far from Jayuya: attributes only
jay_far = [(i, f) for i, f in enumerate(T) if f.get("operator") == "jayuya" and f["municipality"] == "Caguas"]
res["jayuya_stop_in_caguas"] = [{"kind": f["kind"], "lng": f["lng"], "lat": f["lat"], "trips_weekday": f["trips_weekday"], "routes": f["routes"]} for i, f in jay_far]
# current stops by feed
res["scheduled_stops_by_operator_status"] = {o: {"stops": int(((d.t_op == o) & d.t_sched).sum()), "status": d.op_status.get(o)} for o in sorted(set(d.t_op[d.t_sched]))}

# full municipality table with every set at 400 and 800 m
names = ["A_any_stop_twin_today", "A1_scheduled_any_feed", "B_current_scheduled", "C10_current_trips>=10", "C20_current_trips>=20", "C40_current_trips>=40", "D_sat_current", "D_sun_current", "D_sat_and_sun_current",
         "E_rail_or_ferry_any_source", "E1_rail_or_ferry_scheduled_current", "F_osm_only_stops", "F1_expired_scheduled"]
rows = []
for m in sorted(set(d.p_muni)):
    mk = dm & (d.p_muni == m)
    n = int(mk.sum())
    row = {"municipality": m, "region": d.region_of.get(m, ""), "places_default": n}
    for nm in names:
        row[f"{nm}_pct400"] = pct(int((Q1[nm][mk] <= 400).sum()), n)
        row[f"{nm}_pct800"] = pct(int((Q1[nm][mk] <= 800).sum()), n)
    rows.append(row)
with open(HERE / "q1_by_municipality_full.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
res["municipality_full_rows"] = len(rows)

# published municipal transit_pct against the recomputed any-stop share
diffs = []
for r_ in q1["municipality_rows"]:
    p_ = r_["published_transit_pct"]
    if p_ is not None and abs(r_["pct400_any_stop"] - p_) > 0.5:
        diffs.append({"municipality": r_["municipality"], "published": p_, "recomputed": r_["pct400_any_stop"]})
res["published_vs_recomputed_transit_pct_differences_over_half_point"] = diffs
res["municipality_rows_by_name"] = {r_["municipality"]: {k: r_[k] for k in ("places", "pct400_any_stop", "pct400_current_scheduled", "near_expired_only_n", "near_osm_only_n")} for r_ in q1["municipality_rows"]}

# ---- markdown tables ---------------------------------------------------------------------------------------------------------
def md(headers, rows_):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows_:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)

SETS = [("A", "A_any_stop_twin_today", "(a) any stop, as the twin does today"), ("A1", "A1_scheduled_any_feed", "scheduled stop, any feed (expired included)"), ("B", "B_current_scheduled", "(b) scheduled stop, feed current"),
        ("C10", "C10_current_trips>=10", "(c) current, 10 or more weekday calls"), ("C20", "C20_current_trips>=20", "(c) current, 20 or more weekday calls"), ("C40", "C40_current_trips>=40", "(c) current, 40 or more weekday calls"),
        ("D-Sat", "D_sat_current", "(d) current, Saturday service"), ("D-Sun", "D_sun_current", "(d) current, Sunday service"), ("E", "E_rail_or_ferry_any_source", "(e) rail station or ferry terminal")]
CATNAME = {"ACCOMMODATIONS": "Accommodations", "ATTRACTIONS": "Attractions", "GASTRONOMY": "Gastronomy", "VISITOR_SERVICES": "Visitor services"}
tabs = {}
isl = q1["island"]
tabs["island"] = md(["Stop set (default basis, 26,579 places)", "Stops in set", "Within 400 m", "Within 800 m", "Places within 400 m"],
                    [[lbl, f"{q1['stop_sets'][key]:,}", f"{isl[key]['p400']}%", f"{isl[key]['p800']}%", f"{isl[key]['w400']:,}"] for _, key, lbl in SETS])
rows_c = []
for c in CATS:
    v = q1["by_category"][c]
    rows_c.append([CATNAME[c], f"{v['A_any_stop_twin_today']['n']:,}"] + [f"{v[key]['p400']}" for _, key, _l in SETS])
rows_c.append(["All default", f"{q1['n_default']:,}"] + [f"{isl[key]['p400']}" for _, key, _l in SETS])
tabs["category400"] = md(["Category", "Places"] + [s[0] for s in SETS], rows_c)
rows_c = []
for c in CATS:
    v = q1["by_category"][c]
    rows_c.append([CATNAME[c], f"{v['A_any_stop_twin_today']['n']:,}"] + [f"{v[key]['p800']}" for _, key, _l in SETS])
rows_c.append(["All default", f"{q1['n_default']:,}"] + [f"{isl[key]['p800']}" for _, key, _l in SETS])
tabs["category800"] = md(["Category", "Places"] + [s[0] for s in SETS], rows_c)
rows_r = []
for r_, v in q1["by_region"].items():
    rows_r.append([r_, f"{v['A_any_stop_twin_today']['n']:,}"] + [f"{v[key]['p400']}" for _, key, _l in SETS])
tabs["region400"] = md(["PRTC region", "Places"] + [s[0] for s in SETS], rows_r)
# types
rows_t = []
for ty, v in q1["by_type"].items():
    rows_t.append([ty, f"{v['A_any_stop_twin_today']['n']:,}", v["A_any_stop_twin_today"]["p400"], v["B_current_scheduled"]["p400"], v["C20_current_trips>=20"]["p400"], v["D_sat_current"]["p400"], v["E_rail_or_ferry_any_source"]["p400"]])
tabs["types400"] = md(["Type", "Places", "A any", "B current", "C20", "D-Sat", "E rail/ferry"], rows_t)
# municipalities "served on paper"
mrows = q1["municipality_rows"]
paper = [r for r in mrows if (r["pct400_any_stop"] or 0) > 0 and (r["pct400_current_scheduled"] or 0) < (r["pct400_any_stop"] or 0) / 3 and r["places"] >= 1]
paper.sort(key=lambda r: -(r["pct400_any_stop"] - r["pct400_current_scheduled"]))
def cause(r):
    ex, os_ = r["near_expired_only_n"], r["near_osm_only_n"]
    if ex and os_:
        return "expired feed and OSM stops"
    return "expired feed" if ex else "OSM stops only"
tabs["paper"] = md(["Municipality", "Region", "Places", "Any stop %", "Current scheduled %", "Near places on expired feed only", "Near places on OSM stops only", "Cause"],
                   [[r["municipality"], r["region"], f"{r['places']:,}", r["pct400_any_stop"], r["pct400_current_scheduled"], r["near_expired_only_n"], r["near_osm_only_n"], cause(r)] for r in paper])
res["paper_municipalities_n"] = len(paper)
res["paper_municipalities_zero_current"] = sum(1 for r in paper if (r["pct400_current_scheduled"] or 0) == 0)
res["paper_causes"] = dict(Counter(cause(r) for r in paper))
# top: current scheduled well served municipalities
best = sorted([r for r in mrows if r["places"] >= 50], key=lambda r: -(r["pct400_current_scheduled"] or 0))[:12]
tabs["best"] = md(["Municipality", "Places", "Any stop %", "Current %", ">=20 calls %", "Sat %", "Sun %"], [[r["municipality"], f"{r['places']:,}", r["pct400_any_stop"], r["pct400_current_scheduled"], r["pct400_current_trips20"], r["pct400_current_sat"], r["pct400_current_sun"]] for r in best])
res["municipalities_zero_places_near_any_stop"] = sum(1 for r in mrows if r["pct400_any_stop"] == 0)
res["municipalities_zero_near_current"] = sum(1 for r in mrows if r["pct400_current_scheduled"] == 0)
res["municipalities_zero_near_c20"] = sum(1 for r in mrows if r["pct400_current_trips20"] == 0)
res["municipalities_zero_near_sat"] = sum(1 for r in mrows if r["pct400_current_sat"] == 0)
res["municipalities_zero_near_sun"] = sum(1 for r in mrows if r["pct400_current_sun"] == 0)
res["municipalities_ge50_current"] = sum(1 for r in mrows if (r["pct400_current_scheduled"] or 0) >= 50)

# Q2 tables
q2 = read_json("q2_walk.json")
S = q2["sample"]
tabs["walk_sample"] = md(["Measure (sample of 1,000 default places within 800 m straight line of a scheduled stop)", "Value"], [
    ["Places with a road within 150 m (could be snapped)", f"{S['snapped']} of {S['sample_n']}"],
    ["Network distance found within the 1,000 m cut-off", f"{S['found_within_1000m']} of {S['snapped']}"],
    ["Ratio network / straight line to the nearest stop: median", S["ratio_net_best_over_sl_nearest"]["median"]],
    ["Ratio: 25th to 75th percentile", f"{S['ratio_net_best_over_sl_nearest']['p25']} to {S['ratio_net_best_over_sl_nearest']['p75']}"],
    ["Ratio: 90th percentile", S["ratio_net_best_over_sl_nearest"]["p90"]],
    ["Ratio: 95th percentile", S["ratio_net_best_over_sl_nearest"]["p95"]],
    ["Detour factor to the same (straight-line nearest) stop: median / 90th", f"{S['detour_factor_to_same_stop']['median']} / {S['detour_factor_to_same_stop']['p90']}"],
    ["Extra meters (network minus straight line): median / 90th percentile", f"{S['extra_metres_net_minus_sl_median']} / {S['extra_metres_p90']}"],
    ["Share of places with ratio above 1.5 / above 2", f"{S['share_ratio_gt_1_5']}% / {S['share_ratio_gt_2']}%"],
    ["Places within 400 m straight line", S["places_sl_le_400"]],
    ["of which beyond 400 m on the network (road within 150 m)", f"{S['sl_le_400_and_net_gt_400_snapped_only']} ({S['flip_share_of_sl_le_400_pct']}%)"],
    ["of which no road within 150 m (cannot be tested)", S["sl_le_400_not_snapped"]],
    ["Places beyond 400 m straight line but within 400 m on the network", S["sl_gt_400_and_net_le_400"]],
])
fi = q2["full_island"]
tabs["walk_island"] = md(["Island, default basis (26,579 places)", "Straight line", "Walking, roads.bin", "Walking, full OSM network"], [
    ["Within 400 m of a current scheduled stop", f"{fi['current_scheduled']['sl_400_pct']}%", f"{fi['current_scheduled']['net_400_pct']}%", f"{read_json('q2c_osm_walk.json')['island_current']['osm_full_walk']['net_400_pct']}%"],
    ["Within 800 m of a current scheduled stop", f"{fi['current_scheduled']['sl_800_pct']}%", f"{fi['current_scheduled']['net_800_pct']}%", f"{read_json('q2c_osm_walk.json')['island_current']['osm_full_walk']['net_800_pct']}%"],
    ["Within 400 m of any scheduled stop (expired included)", f"{fi['all_scheduled']['sl_400_pct']}%", f"{fi['all_scheduled']['net_400_pct']}%", f"{read_json('q2c_osm_walk.json')['island_all_scheduled']['osm_full_walk']['net_400_pct']}%"],
    ["Places lost at 400 m (share of those near by straight line), current stops", "-", f"{fi['current_scheduled']['lost_400_pct_of_sl']}% ({fi['current_scheduled']['lost_400_n']:,} places)", f"{read_json('q2c_osm_walk.json')['island_current']['osm_full_walk']['lost_400_pct_of_sl']}%"],
])
# Q4 tables
q4 = read_json("q4_journey.json")
m = q4["main_weekday_10"]
rows_q = [["All default places", f"{m['all']['n']:,}", f"{m['all']['pct_within_60']}%", f"{m['all']['pct_within_90']}%", f"{m['all']['pct_within_120']}%", f"{q4['drive_all']['pct_within_60']}%", f"{q4['drive_all']['pct_within_90']}%", f"{q4['drive_all']['pct_within_120']}%"]]
for c in CATS:
    rows_q.append([CATNAME[c], f"{m['by_category'][c]['n']:,}", f"{m['by_category'][c]['pct_within_60']}%", f"{m['by_category'][c]['pct_within_90']}%", f"{m['by_category'][c]['pct_within_120']}%",
                   f"{q4['drive_by_category'][c]['pct_within_60']}%", f"{q4['drive_by_category'][c]['pct_within_90']}%", f"{q4['drive_by_category'][c]['pct_within_120']}%"])
tabs["sju_category"] = md(["Group", "Places", "Transit 60 min", "Transit 90 min", "Transit 120 min", "Drive 60 min", "Drive 90 min", "Drive 120 min"], rows_q)
rows_q = []
for r_ in m["by_region"]:
    rows_q.append([r_, f"{m['by_region'][r_]['n']:,}", f"{m['by_region'][r_]['pct_within_60']}%", f"{m['by_region'][r_]['pct_within_90']}%", f"{m['by_region'][r_]['pct_within_120']}%",
                   f"{q4['drive_by_region'][r_]['pct_within_60']}%", f"{q4['drive_by_region'][r_]['pct_within_90']}%", f"{q4['drive_by_region'][r_]['pct_within_120']}%"])
tabs["sju_region"] = md(["PRTC region", "Places", "Transit 60", "Transit 90", "Transit 120", "Drive 60", "Drive 90", "Drive 120"], rows_q)
sens = q4["sensitivity"]
tabs["sju_sens"] = md(["Variant (all other rules unchanged)", "Within 60 min", "Within 90 min", "Within 120 min"],
                      [["Main run: weekday 10:00, current feeds, 3 boardings, 3 min buffer", f"{m['all']['pct_within_60']}%", f"{m['all']['pct_within_90']}%", f"{m['all']['pct_within_120']}%"]] +
                      [[lbl, f"{sens[k]['pct_within_60']}%", f"{sens[k]['pct_within_90']}%", f"{sens[k]['pct_within_120']}%"] for lbl, k in (
                          ("Including expired feeds", "weekday_10_including_expired_feeds"), ("Weekday 07:00", "weekday_07_current"), ("Weekday 14:00", "weekday_14_current"), ("Weekday 18:00", "weekday_18_current"),
                          ("Saturday 10:00", "saturday_10_current"), ("Sunday 10:00", "sunday_10_current"), ("At most 2 boardings", "weekday_10_max2_boardings"), ("At most 1 boarding", "weekday_10_max1_boarding"), ("No transfer buffer", "weekday_10_buffer_0s"))])
# Q6 sizes table
q6 = read_json("q6_design_numbers.json")
ps = q6["places_json_added_size"]
tabs["sizes"] = md(["Addition", "Raw added", "Gzip added"], [
    ["places.json today (reference)", f"{q6['places_json_raw_mb']} MB", f"{q6['places_json_gzip6_mb']} MB"],
    ["Tier 1 minimal: ts_m, ts_calls", f"{ps['minimal_ts_m_and_ts_calls']['raw_added_kb']:.0f} KB", f"{ps['minimal_ts_m_and_ts_calls']['gzip6_added_kb']:.0f} KB"],
    ["Tier 1: ts_m, ts_calls, ts_we, hub_m, hub", f"{ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['raw_added_kb']:.0f} KB", f"{ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['gzip6_added_kb']:.0f} KB"],
    ["Tier 1 + Tier 2 (adds tw_m)", f"{ps['tier1_plus_tw_m']['raw_added_kb']:.0f} KB", f"{ps['tier1_plus_tw_m']['gzip6_added_kb']:.0f} KB"],
    ["Tier 1 + 2 + 3 (adds sju_t, sju_b, sju_d)", f"{ps['tier1_plus_tw_m_plus_sju_t_sju_b_sju_d']['raw_added_kb']:.0f} KB", f"{ps['tier1_plus_tw_m_plus_sju_t_sju_b_sju_d']['gzip6_added_kb']:.0f} KB"],
    ["Alternative: all 9 fields as typed columns in one binary file", f"{q6['binary_columns_alternative']['raw_kb']:.0f} KB", f"{q6['binary_columns_alternative']['gzip6_kb']:.0f} KB"],
    ["municipalities.json: 26 new fields x 78 municipalities", f"{q6['municipalities_json_added']['raw_added_kb']:.0f} KB", f"{q6['municipalities_json_added']['gzip6_added_kb']:.0f} KB"],
    ["barrios.geojson: 4 new fields x 901 barrios", f"{q6['barrios_geojson_added']['raw_added_kb']:.0f} KB", f"{q6['barrios_geojson_added']['gzip6_added_kb']:.0f} KB"],
    ["transport.json: calls_sat, calls_sun, feed on 3,847 scheduled stops", f"{q6['transport_json_added_for_scheduled_stops']['raw_added_kb']:.0f} KB", f"{q6['transport_json_added_for_scheduled_stops']['gzip6_added_kb']:.0f} KB"],
    ["gateways.json (new file, 141 records)", f"{q6['gateways_json_estimate']['raw_kb']:.0f} KB", f"{q6['gateways_json_estimate']['gzip6_kb']:.0f} KB"],
])
ac = q6["access_classes_island"]
tabs["classes"] = md(["Access class (default basis)", "Places", "Share"], [[k, f"{v['n']:,}", f"{v['pct']}%"] for k, v in ac.items()])
rtf = jload("transit_routes.geojson")["features"]
res["saturday_operators"] = sorted({f["properties"]["operator"] for f in rtf if f["properties"]["trips_saturday"] > 0})
res["sunday_operators"] = sorted({f["properties"]["operator"] for f in rtf if f["properties"]["trips_sunday"] > 0})
res["sunday_routes_ati"] = sorted(f["properties"]["short_name"] for f in rtf if f["properties"]["operator"] == "ati" and f["properties"]["trips_sunday"] > 0)
res["sunday_ferry_routes"] = sorted(f["properties"]["short_name"] for f in rtf if f["properties"]["mode"] == "ferry" and f["properties"]["trips_sunday"] > 0)
write_json("q_extra.json", res)
with open(HERE / "tables.md", "w", encoding="utf-8") as f:
    for k, v in tabs.items():
        f.write(f"<!-- table:{k} -->\n{v}\n<!-- /table:{k} -->\n\n")
print(json.dumps(res, indent=1, default=str)[:6000])
for k in ("island", "paper", "best"):
    print(k); print(tabs[k]); print()
