"""Assemble REPORT.md from the JSON results of the other scripts (numbers are read from them, not retyped). Also writes report_numbers.json."""
from common import *
import ast
import re

R = lambda n: read_json(n)
q1, q1b, q1c, q1d, qx = R("q1_baseline.json"), R("q1b_stale_check.json"), R("q1c_location_sensitivity.json"), R("q1d_bruteforce_check.json"), R("q_extra.json")
q2, q2b, q2c, q2d = R("q2_walk.json"), R("q2b_osm_inventory.json"), R("q2c_osm_walk.json"), R("q2d_muni_graph_diff.json")
q3, q3b = R("q3_gateways.json"), R("q3b_east_and_osm.json")
q4, q4c = R("q4_journey.json"), R("q4c_check.json")
q5, q6 = R("q5_problems.json"), R("q6_design_numbers.json")
try:
    timings = R("timings.json")
except FileNotFoundError:
    timings = {}
try:
    hist = R("timing_history.json")
except FileNotFoundError:
    hist = []
nh = len(hist)


def rng(key, nd=1):
    vals = [h[key] for h in hist if h.get(key) is not None]
    return f"{min(vals):.{nd}f} to {max(vals):.{nd}f}"

tables = {}
txt = (HERE / "tables.md").read_text(encoding="utf-8")
for m_ in re.finditer(r"<!-- table:(\w+) -->\n(.*?)\n<!-- /table:\1 -->", txt, re.S):
    tables[m_.group(1)] = m_.group(2)


def md(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def n0(x):
    return f"{int(round(x)):,}"


def dist_txt(m):
    return f"{m:,.0f} m" if m < 1000 else f"{m / 1000:.1f} km"


mr = qx["municipality_rows_by_name"]
fe = {f["operator"]: f for f in q5["feeds_with_stops"]}
exp_ops = [f for f in q5["feeds_with_stops"] if f["status_today"] == "expired"]
n_exp = len(exp_ops)
isl = q1["island"]
A, A1, B = isl["A_any_stop_twin_today"], isl["A1_scheduled_any_feed"], isl["B_current_scheduled"]
C10, C20, C40 = isl["C10_current_trips>=10"], isl["C20_current_trips>=20"], isl["C40_current_trips>=40"]
DS, DU, DB, E = isl["D_sat_current"], isl["D_sun_current"], isl["D_sat_and_sun_current"], isl["E_rail_or_ferry_any_source"]
NDEF = q1["n_default"]
why = q1["why_served_island"]
near_any = A["w400"]
mt = q1["matching"]
ev = mt["events_by_day"]
st = q1["stale_check"]
b1 = q1b
sw = q2["sample"]
cur_ = q2["full_island"]["current_scheduled"]
oc = q2c
tm2 = q2
m4 = q4["main_weekday_10"]
da = q4["drive_all"]
ps = q6["places_json_added_size"]
hp = q6["hub_proximity_default"]
rg = q1["by_region"]
bt = q1["by_type"]
fr = {r["short_name"]: r for r in q3["ferry_routes_from_routes_file"]}
tt = q3["ferry_trips_in_timetable_files"]
sj = q3["sju_stops_within_500m"]
inv = q3["inventory_by_kind_source"]
ro = q4c["operators_reached_all_feeds"]
op_types = q5["operators_by_type_and_feed"]
cats_nice = {"ACCOMMODATIONS": "Accommodations", "ATTRACTIONS": "Attractions", "GASTRONOMY": "Gastronomy", "VISITOR_SERVICES": "Visitor services"}

snapped_near = cur_["sl_400_n"] - cur_["lost_400_of_which_unsnapped_n"]
lost_snapped = cur_["lost_400_n"] - cur_["lost_400_of_which_unsnapped_n"]
N = {
    "near_any_n": near_any,
    "cause_current_pct": pct(why["current"], near_any), "cause_expired_pct": pct(why["expired_only"], near_any), "cause_osm_pct": pct(why["osm_only"], near_any),
    "drop_any_to_current_pts": round(A["p400"] - B["p400"], 1), "drop_any_to_current_rel_pct": round(100 * (1 - B["w400"] / A["w400"]), 0),
    "ratio_any_over_current": round(A["p400"] / B["p400"], 1),
    "walk_lost_pct_snapped_current": pct(lost_snapped, snapped_near), "walk_lost_n_snapped_current": lost_snapped, "walk_lost_n_unsnapped_current": cur_["lost_400_of_which_unsnapped_n"],
    "walk_end_to_end_s": round(q2["graph_build_s"] + q2["stop_snap_s"] + q2["place_snap_s"] + q2["place_registry_s"] + q2["full_run_s"], 1),
    "events_matched_total": sum(ev.values()),
    "max_call_share_missing_pct": round(max(100 * (1 - v["calls_trips_json"] / v["calls_feed"]) for v in mt["by_operator_feed_vs_file"].values()), 0),
    "jayuya_far_km": round(q5["municipal_stops_more_than_3km_outside_own_municipality"]["max_m"] / 1000),
    "no_stop_800_pct": round(100 - B["p800"], 1),
    "osm_walk_minus_roads_pts": round(oc["island_current"]["osm_full_walk"]["net_400_pct"] - oc["island_current"]["roads_bin"]["net_400_pct"], 1),
    "recovered_share_pct": pct(oc["island_current_lost_on_roads_bin_400_recovered_on_osm_walk"], oc["island_current_lost_on_roads_bin_400"]),
}
slug_to_name = {slug(r["municipality"]): r["municipality"] for r in q1["municipality_rows"]}


def opname(x):
    return "ATI" if x == "ati" else slug_to_name.get(x, x.replace("_", " ").title())


N["keeps_text"] = ", ".join(f"{opname(o)} keeps {v['calls_trips_json']:,} of {v['calls_feed']:,}" for o, v in list(mt["by_operator_feed_vs_file"].items())[:5])
pairs = []
for k, v in q5["scheduled_stop_pairs_within_30m"]["different_operator_pairs_by_operators"].items():
    a_, b_ = ast.literal_eval(k)
    pairs.append(f"{opname(a_)} with {opname(b_)} {v}")
N["cross_pairs_text"] = ", ".join(pairs)
N["sat_ops_text"] = ", ".join(opname(o) for o in qx["saturday_operators"])
N["sun_ops_text"] = ", ".join(opname(o) for o in qx["sunday_operators"])
p_rows = [x for x in q1["municipality_rows"]]
paper = qx["paper_municipalities_n"]

out = []
w = out.append

# ================================================================================================================================
w("# Tourism assets and transport links: exploratory spike for the PR Digital Twin")
w("")
w("Read-only spike for Foundation for Puerto Rico (FPR). Analysis date 2026-10-05. Data: the published files in the repository's `site/data/` (places and stops built 2026-10-02; feed status recalculated for 2026-10-05). No network, no browser, no change to the repository. Every number below was read from the output of a script in this folder (list in section 9). Business names and addresses are not reproduced anywhere; the figures are aggregates.")
w("")
w("## 1. The answer")
w("")
w(f"**Today's \"near transit\" figure is about {N['ratio_any_over_current']} times what current scheduled service supports.** {A['p400']}% of the {NDEF:,} default-basis tourism places are within 400 m (straight line) of some mapped stop (the twin publishes {st['pub_pct400_default']}%; the gap is mostly the stale Jayuya fix). Require a scheduled stop whose operator feed is current and it is **{B['p400']}%** ({N['drop_any_to_current_pts']} points, {N['drop_any_to_current_rel_pct']:.0f}% fewer places). Require 20 or more weekday calls at that stop and it is **{C20['p400']}%**; require Saturday service, **{DS['p400']}%**; Sunday service, **{DU['p400']}%**; a Tren Urbano station or ferry terminal, **{E['p400']}%**.")
w("")
w("Decision-relevant numbers:")
w("")
w(f"1. Of the {near_any:,} places the twin calls \"near\", {why['current']:,} ({N['cause_current_pct']}%) have a current scheduled stop within 400 m; {why['expired_only']:,} ({N['cause_expired_pct']}%) rely only on stops from expired timetables and {why['osm_only']:,} ({N['cause_osm_pct']}%) only on volunteer-mapped OpenStreetMap stops (no timetable).")
ex_txt = "; ".join(f"{m} {mr[m]['pct400_any_stop']}% to {mr[m]['pct400_current_scheduled']}%" for m in ("Juncos", "San Lorenzo", "Fajardo", "Ponce"))
w(f"2. {qx['paper_municipalities_zero_current']} municipalities look partly served (above 0%) but have 0.0% once a current timetable is required. Examples (any stop, then current scheduled stop): {ex_txt}. Ponce's feed ended {fe['ponce']['end']}. {qx['municipalities_zero_near_current']} of 78 municipalities have no place within 400 m of a current scheduled stop; {qx['municipalities_zero_near_c20']} have none near a stop with 20 or more weekday calls.")
w(f"3. Walking changes the picture again: along mapped roads the network distance is a median {sw['ratio_net_best_over_sl_nearest']['median']} times the straight line (90th percentile {sw['ratio_net_best_over_sl_nearest']['p90']}). {N['walk_lost_pct_snapped_current']}% of the places within 400 m by straight line of a current scheduled stop are beyond 400 m on the road network, so {B['p400']}% becomes {cur_['net_400_pct']}%. `roads.bin` holds no footways, paths, steps, pedestrian streets or service roads; a full OSM walking network moves the result by only {N['osm_walk_minus_roads_pts']} point ({oc['island_current']['osm_full_walk']['net_400_pct']}%).")
w(f"4. The whole-island walking run ({q2['full_run_searches']:,} bounded searches from the scheduled stops to {q2['places']['all']:,} places) took {q2['full_run_s']} s in the final run ({rng('island_search_s')} s across {nh} runs on a shared machine); loading the graph, snapping and searching together took {N['walk_end_to_end_s']} s in the final run ({rng('island_end_to_end_s')} s across the {nh} runs). This is measured, not estimated.")
w(f"5. Gateways in the data: {q3['faa_airports']['public_use']} FAA public-use airports (SJU, BQN, PSE, MAZ and six more), {q3['rail_stations']['n']} Tren Urbano stations, {inv['ferry_terminal|ati_gtfs']} ATI ferry terminals on {len(fr)} ferry routes, {inv['bus_station|ati_gtfs'] + inv['bus_station|muni_gtfs'] + inv['bus_station|osm_transport']} bus stations and terminals ({inv['bus_station|ati_gtfs']} ATI, {inv['bus_station|muni_gtfs']} municipal, {inv['bus_station|osm_transport']} OpenStreetMap), and one cruise pier (mapped in OpenStreetMap as a ferry terminal). The Ceiba ferry terminal, the gateway to Vieques and Culebra, is {q3b['ceiba_ferry_terminal_to_nearest_ati_bus_stop_km']} km from the nearest ATI bus stop; no scheduled land link to it exists in the data.")
w(f"6. Scheduled transit from SJU (weekday 10:00, 3 boardings at most): {m4['all']['pct_within_60']}% of places within 60 minutes, {m4['all']['pct_within_90']}% within 90, {m4['all']['pct_within_120']}% within 120. A free-flow driving estimate on the road graph gives {da['pct_within_60']}%, {da['pct_within_90']}% and {da['pct_within_120']}%. Only the San Juan metro area is connected: {m4['by_region']['Porta Capital']['pct_within_120']}% of Porta Capital places are within 120 minutes by transit; Porta Caribe, Porta Cordillera and both Porta del Sol regions have none.")
w(f"7. Data problems that would distort a naive analysis: {n_exp} operators with expired timetables hold {q5['expired_stops']} of {q5['scheduled_stops_total']:,} scheduled stops ({q5['expired_stop_share_pct']}%); the trip files drop {q5['weekday_calls']['share_missing_pct']}% of weekday calls (up to {N['max_call_share_missing_pct']:.0f}% for one municipal feed); the published place fields are stale for Jayuya ({b1['flag_changes_default_jayuya']} default-basis places wrongly lack the 400 m flag); one Jayuya stop is still {N['jayuya_far_km']} km from its municipality; {q5['scheduled_stop_pairs_within_30m']['total']} pairs of scheduled stops lie within 30 m of each other.")
w(f"8. Added weight of the recommended core (three per-place fields): {ps['core3_ts_m_ts_calls_ts_we']['gzip6_added_kb']:.0f} KB gzip inside `places.json` (today {q6['places_json_gzip6_mb']} MB gzip), or {q6['binary_core3_columns']['gzip6_kb']:.0f} KB as a separate typed-column file; the per-area series add about {q6['municipalities_json_added']['gzip6_added_kb'] + q6['barrios_geojson_added']['gzip6_added_kb']:.0f} KB gzip. Build cost: seconds for Tier 1 ({rng('tier1_total_s')} s for the whole baseline script, which computes 15 stop sets), {rng('island_end_to_end_s')} s more for walking distances, and {q4['scan_seconds_one_origin']} s per gateway and departure for the journey scan in the final run; all measured on a shared machine over {nh} runs.")
w("")
w("**Recommended method in brief** (details in section 8):")
w("")
w("- Treat access as a **profile, not a score**. For each place publish: distance to the nearest *current scheduled* stop, the weekday calls and weekend flags at stops within 400 m, and (for walking) the network distance. Show the old \"any stop\" figure only as a labelled legacy field.")
w("- **Tier 1 (cheap, robust, no road graph):** `ts_m`, `ts_calls`, `ts_we` per place and shares at 400 m and 800 m per municipality, region and barrio. Checked two independent ways to within 0.1 point.")
w("- **Tier 2 (needs the road graph):** `tw_m`, the walking distance along mapped roads (bounded to 1,000 m). Use it for the 400 m flag; label it an estimate that ignores footpaths, sidewalks, fences and crossings.")
w("- **Tier 3 (prototype now, needs better timetable data to scale):** scheduled journey times and a driving comparator from named gateways. Only gateways inside the San Juan metro area (SJU, Old San Juan, the Cataño ferry, Tren Urbano and ATI terminals) have a current scheduled stop within 400 m; for every other airport and ferry terminal publish \"no scheduled link in the data\", not a time.")
w(f"- **Hubs:** for the {N['no_stop_800_pct']}% of places with no current scheduled stop within 800 m, compute distance to the nearest gateway (airport, ferry terminal, rail station, bus terminal) from a small `gateways.json` in the browser instead of adding a per-place field.")
w("- **Fix first:** rebuild the stale place fields, put feed status and Saturday/Sunday calls on every stop inside `parse_gtfs`, write untimed calls into the trip files, and fold duplicate OSM and cross-operator stops. These fixes change the numbers more than any new method does.")
w("- **Never claim:** that a place is \"accessible by public transport\" for a visitor, anything real-time, door-to-door times, or service quality from `trips_weekday` alone (section 8.9).")
w("")

# ================================================================================================================================
w("## 2. Definitions used throughout")
w("")
cat_counts = ", ".join(f"{cats_nice[c]} {q1['by_category'][c]['A_any_stop_twin_today']['n']:,}" for c in CATS)
w(f"- **Default basis:** places with confidence 0.50 or higher and no places of worship, the rule in `site/js/app.js` `visible(p)` with the initial state (`conf: 0.5`, `worship: false`). {NDEF:,} of {q1['n_places_all']:,} places: {cat_counts}.")
w(f"- **Stop sets** (all from `transport.json`): *any stop* = the twin's own set (kinds transit_stop, bus_stop, bus_station, rail_station, ferry_terminal from every source and feed: {q1['stop_sets']['A_any_stop_twin_today']:,} features); *scheduled* = ATI and municipal GTFS stops ({q1['stop_sets']['A1_scheduled_any_feed']:,}); *current* = scheduled stops whose operator feed has not ended on 2026-10-05 ({q1['stop_sets']['B_current_scheduled']:,}; includes {qx['current_only_excluding_expiring_feed']['expiring_feed_stops']} Canóvanas stops whose feed ends {fe['canovanas']['end']}); *expired* = {q5['expired_stops']} stops of {n_exp} operators; *OSM-only* = {q1['stop_sets']['F_osm_only_stops']} volunteer-mapped stops with no timetable.")
w("- **Weekday calls** = `trips_weekday` of a stop: scheduled calls on a typical Wednesday, both directions if the stop serves both. A one-direction stop shows about half of a two-way stop with the same headway.")
w("- **Distances** are straight-line metres in EPSG:32161 (Puerto Rico State Plane), computed with a spatial index. The twin's own flat-earth formula gives the same shares to within 0.1 point (checked by brute force, section 3.7).")
w("- **Eastern region** = the Puerto Rico Tourism Company region *Porta del Mar* (15 municipalities, including Vieques and Culebra); the app has no region called \"East\".")
w("")

# ================================================================================================================================
w("## 3. Question 1: baseline today, and what changes with real service")
w("")
w("### 3.1 Island, default basis")
w("")
w(tables["island"])
w("")
sun_routes = ", ".join(r for r in qx["sunday_routes_ati"] if r.isdigit())
w(f"Reading: the first row is what the twin shows now. Each further condition removes places. The {A['w400'] - B['w400']:,} places that drop out between rows (a) and (b) are the \"served on paper\" places. Sunday service exists only on {', '.join(o.upper() for o in qx['sunday_operators'])} ({mt['weekend_method_check']['sun_A']} stop locations: Tren Urbano, bus routes {sun_routes}, ferry routes {', '.join(qx['sunday_ferry_routes'])}).")
w("")
gi = lambda k: isl[k]["p400"]
w(f"If expired feeds are also counted (scheduled stops of any feed), the shares within 400 m are {gi('G10_any_feed_trips>=10')}% / {gi('G20_any_feed_trips>=20')}% / {gi('G40_any_feed_trips>=40')}% for 10 / 20 / 40 or more weekday calls and {gi('G_sat_any_feed')}% / {gi('G_sun_any_feed')}% for Saturday / Sunday service (Sunday is ATI only, so it does not change). Of the {q1['stop_sets']['E_rail_or_ferry_any_source']} rail and ferry features, {q1['stop_sets']['E1_rail_or_ferry_scheduled_current']} are scheduled in current feeds (the other seven are OpenStreetMap ferry nodes); counting only those gives {isl['E1_rail_or_ferry_scheduled_current']['p400']}% within 400 m.")
w("")
rs = q1["residents"]
w(f"Residents, same stop sets (Census block centres, {rs['population_total']:,} people): within 400 m of any stop {rs['A_any_stop_twin_today']['p400']}%, of a current scheduled stop {rs['B_current_scheduled']['p400']}%, with 20 or more weekday calls {rs['C20_current_trips>=20']['p400']}%, with Saturday service {rs['D_sat_current']['p400']}%, next to rail or ferry {rs['E_rail_or_ferry_any_source']['p400']}%. Places are better served than residents, probably because listings concentrate in town centres where stops are (not tested).")
w("")
w("### 3.2 By category, within 400 m (percent of places)")
w("")
w("Columns: A any stop, A1 scheduled stop of any feed, B current scheduled, C10 / C20 / C40 current with 10 / 20 / 40 or more weekday calls, D-Sat / D-Sun current with Saturday / Sunday service, E rail station or ferry terminal.")
w("")
w(tables["category400"])
w("")
w("### 3.3 By category, within 800 m (percent of places)")
w("")
w(tables["category800"])
w("")
w("### 3.4 By tourism region, within 400 m (percent of places)")
w("")
w(tables["region400"])
w("")
w(f"Porta Capital is the only region where a visitor without a car finds frequent scheduled service near most places ({rg['Porta Capital']['C20_current_trips>=20']['p400']}% within 400 m of a stop with 20 or more weekday calls). Porta Caribe shows {rg['Porta Caribe']['A_any_stop_twin_today']['p400']}% under today's measure but {rg['Porta Caribe']['B_current_scheduled']['p400']}% with a current timetable, because Ponce's feed ended {fe['ponce']['end']}. Porta del Sol Norte has {rg['Porta del Sol Norte']['C20_current_trips>=20']['p400']}% of places near a stop with 20 or more weekday calls and Porta del Sol Sur {rg['Porta del Sol Sur']['C20_current_trips>=20']['p400']}%; neither region has a place near Saturday service ({rg['Porta del Sol Norte']['D_sat_current']['p400']}% and {rg['Porta del Sol Sur']['D_sat_current']['p400']}%).")
w("")
w("### 3.5 By type (selected, within 400 m, percent of places)")
w("")
w(tables["types400"])
w("")
tb = lambda t_: bt[t_]["B_current_scheduled"]["p400"]
w(f"Against the all-places figure of {B['p400']}% near a current scheduled stop, museums ({tb('Museums')}%), restaurants ({tb('Restaurants')}%) and tourist attractions ({tb('Tourist Attractions')}%) sit above, while beaches ({tb('Beaches')}%), hotels ({tb('Hotels')}%), parks ({tb('Parks')}%) and scenic areas ({tb('Scenic Areas')}%) sit below. Only {bt['Beaches']['E_rail_or_ferry_any_source']['p400']}% of beaches and {bt['Hotels']['E_rail_or_ferry_any_source']['p400']}% of hotels are near a rail station or ferry terminal.")
w("")
w("### 3.6 Municipalities")
w("")
w(f"Full tables: `q1_by_municipality_full.csv` (every stop set at 400 m and 800 m) and `q1_by_municipality.csv` (with the cause split below). {qx['municipalities_zero_places_near_any_stop']} municipalities have no place near any stop of any kind; {qx['municipalities_zero_near_current']} have none near a current scheduled stop; {qx['municipalities_zero_near_c20']} none near a stop with 20 or more weekday calls; {qx['municipalities_zero_near_sat']} none near Saturday service; {qx['municipalities_zero_near_sun']} none near Sunday service. Only {qx['municipalities_ge50_current']} municipalities reach 50% near a current scheduled stop.")
w("")
pc_ = qx["paper_causes"]
w(f"**Municipalities that look \"served\" only because of expired or OSM-only stops** ({paper} municipalities where the current-service share is under one third of the any-stop share; {qx['paper_municipalities_zero_current']} of them at 0.0%). Cause counts: expired feed only {pc_.get('expired feed', 0)}, expired feed and OSM stops {pc_.get('expired feed and OSM stops', 0)}, OSM stops only {pc_.get('OSM stops only', 0)}. In the OSM-only cases the \"service\" is usually one volunteer-mapped bus terminal with no timetable (the twin's own dictionary says most such terminals are carros públicos terminals).")
w("")
w(tables["paper"])
w("")
w("Best-served municipalities (50 or more places):")
w("")
w(tables["best"])
w("")
w("### 3.7 Replication of the published figure")
w("")
w(f"- The published `transit_400m` gives {st['pub_pct400_default']}% for the default basis. Recomputing with the twin's own formula and the current `transport.json` gives {b1['twin_formula_pct400_default_current_stops']}%. The difference is {b1['flag_false_to_true_default']} places ({b1['flag_changes_default_jayuya']} in Jayuya) that should carry the flag; none lose it.")
w(f"- `places.json` was built before the Jayuya longitude fix reached `transport.json`. Jayuya: median distance {n0(b1['jayuya_published_median_transit_m'])} m published against {n0(b1['jayuya_recomputed_median_transit_m'])} m recomputed; share within 400 m {b1['jayuya_default_pct400_published']}% published against {b1['jayuya_default_pct400_recomputed']}%.")
dif = ", ".join(f"{x['municipality']} ({x['published']} against {x['recomputed']})" for x in qx["published_vs_recomputed_transit_pct_differences_over_half_point"])
w(f"- Municipal `transit_pct` matches the recomputed any-stop share to within 0.5 point everywhere except {dif}.")
w(f"- Independent check of sets B, C20, C40, D and E: brute-force nearest distance with the twin's flat-earth formula (no projection, no index) gives within 0.1 point of the indexed figures (for example B {q1d['B_current']['p400']}% against {B['p400']}%, C20 {q1d['C20']['p400']}% against {C20['p400']}%).")
w(f"- Counting the {qx['current_only_excluding_expiring_feed']['expiring_feed_stops']} Canóvanas stops (feed ends {fe['canovanas']['end']}) as not current changes B from {B['p400']}% to {qx['current_only_excluding_expiring_feed']['pct400']}%.")
w(f"- Frequency thresholds counted on stop locations (adding up co-located stop IDs) instead of single IDs change C10, C20, C40 from {q1c['10']['stop_level_pct400']}%, {q1c['20']['stop_level_pct400']}%, {q1c['40']['stop_level_pct400']}% to {q1c['10']['location_level_pct400']}%, {q1c['20']['location_level_pct400']}%, {q1c['40']['location_level_pct400']}%.")
w("")
w("### 3.8 How weekend service was derived, and its error")
w("")
w(f"The trip files hold `[lng, lat, seconds]` per stop call and no stop ID. `network.py` rounds every stop coordinate to five decimals (about 1.1 m) before writing both `transport.json` and the trip files, so equality is exact. **Rule:** a call at (lng, lat) on a trip of operator O counts for the scheduled stop(s) of operator O with those coordinates; stop IDs of one operator sharing a coordinate are merged into one stop location ({mt['scheduled_stops']:,} stops make {mt['stop_locations']:,} locations; {mt['locations_with_more_than_one_stop_id']} locations hold {mt['stops_in_those_locations']} stops).")
w("")
w("Error, in order of size:")
w("")
zc = qx["locations_with_feed_trips_but_zero_calls_in_trips_json"]
w(f"1. **Matching itself is exact:** all {N['events_matched_total']:,} calls ({ev['wk']:,} weekday, {ev['sa']:,} Saturday, {ev['su']:,} Sunday) matched a scheduled stop ({mt['stop_events_unmatched']} unmatched).")
w(f"2. **Calls missing from the trip files.** `parse_gtfs` writes only calls that have a time and leaves out routes with a non-geographic stop order ({q5['routes_with_order_note_non_geographic_stop_order']['n']} Patillas routes). The files hold {mt['weekday_calls_in_trips_json_total']:,} weekday calls against {mt['weekday_calls_feed_total']:,} in the feeds (-{q5['weekday_calls']['share_missing_pct']}%). At {mt['locations_where_trips_json_has_fewer_calls_than_feed']} of {mt['stop_locations']:,} locations the file has fewer calls than the feed, and {zc['n']} have none ({zc['current_feeds_n']} of them on current feeds). For this reason weekday frequency tiers use the feed's own `trips_weekday` per stop, not the trip files.")
w(f"3. **Weekend flags cross-checked.** I derived Saturday and Sunday service a second way, from the route calendars (`trips_saturday`, `trips_sunday` in `transit_routes.geojson`, matched to the routes listed at each stop). Current feeds agree exactly. The only difference is {mt['weekend_method_check']['sat_B_not_A'].get('juncos', 0)} Juncos locations with Saturday service in the calendar but no timed call in the file (Juncos' feed is expired). Sunday: {mt['weekend_method_check']['sun_A']} against {mt['weekend_method_check']['sun_B']}.")
w(f"4. **What a missing flag means.** No Saturday or Sunday service in the data is not proof of none: the operators whose feeds contain Saturday service are {N['sat_ops_text']} (Juncos is expired); the only one with Sunday service is {N['sun_ops_text']}. Most municipal feeds carry weekday calendars only.")
w("")

# ================================================================================================================================
w("## 4. Question 2: straight line against walking along the road network")
w("")
w("### 4.1 What the graph contains")
w("")
g = q2["graph"]
kmw = q2b["km_by_highway_walkable_ways_used"]
w(f"`roads.bin` (read with `roads.Roads`): {g['roads_bin_nodes']:,} nodes, {g['roads_bin_edges']:,} edges, {sum(g['km_by_class_in_file'].values()):,.0f} km. Classes present: {', '.join(g['classes_present'])}. **It has no footways, paths, steps, pedestrian streets, cycleways, tracks or service roads** (`roads.py` `CLASSES` lists none of them, `_usable()` drops every `highway=service`, and ways with `access=no/private` or `motor_vehicle=no` are dropped). {g['oneway_edges_pct']}% of edges are one-way; pedestrians ignore that, so the walking run treats every edge as two-way and drops motorways and motorway links ({g['km_by_class_in_file']['motorway'] + g['km_by_class_in_file']['motorway_link']:,.0f} km). The cached OpenStreetMap extract (`cache/roads/puerto-rico.osm.pbf`, read only) holds a further {q2b['classes_not_in_roads_bin_but_walkable_km']:,.0f} km of ways a pedestrian can use that `roads.bin` lacks: service {kmw.get('service', 0):,.0f} km, tracks {kmw.get('track', 0):,.0f} km, paths {kmw.get('path', 0):,.0f} km, footways {kmw.get('footway', 0):,.0f} km, pedestrian ways {kmw.get('pedestrian', 0):,.0f} km, steps {kmw.get('steps', 0):,.0f} km. Footways are {kmw.get('footway', 0) / q2b['walkable_km_total'] * 100:.1f}% of the {q2b['walkable_km_total']:,.0f} km of walkable ways in the extract, so even the full extract holds little sidewalk detail.")
w("")
w(f"Snapping (shapely nearest edge, 150 m limit): {q2['stops']['snapped_within_150m']:,} of {q2['stops']['scheduled']:,} scheduled stops snap (median connector {q2['stops']['median_connector_m']:.1f} m); {q2['places']['default_snapped_within_150m']:,} of {q2['places']['default']:,} default places snap (median connector {q2['places']['default_median_connector_m']:.1f} m, 90th percentile {q2['places']['default_p90_connector_m']:.0f} m); {q2['places']['default_not_snapped_150m']:,} places have no walkable road within 150 m ({q2['places']['default_not_snapped_300m']} not within 300 m). The snap distance matches `roads.Roads.snap` (median difference {q2['checks']['snap_distance_roads_py_vs_walknet']['median_abs_diff_m']} m on {q2['checks']['snap_distance_roads_py_vs_walknet']['n']} places). Network distance = connector to the road + path along edges + connector to the stop.")
w("")
w("### 4.2 Sample result")
w("")
w(f"Sample: {sw['sample_n']:,} places drawn at random (seed 20261005) from the {q2['sample_pool_default_within_800m_scheduled']:,} default places within 800 m straight line of a scheduled stop (any feed); place-side bounded Dijkstra, cut-off 1,000 m.")
w("")
w(tables["walk_sample"])
w("")
w("By straight-line band (median / 90th percentile ratio): " + "; ".join(f"{k} m: {v['median_ratio']} / {v['p90_ratio']} (n={v['n']})" for k, v in sw["by_sl_band"].items()) + ".")
w("")
w(f"**Flips across the 400 m line:** {sw['sl_le_400_and_net_gt_400_snapped_only']} of the {sw['places_sl_le_400'] - sw['sl_le_400_not_snapped']} sampled places within 400 m straight line that have a road within 150 m ({sw['flip_share_of_sl_le_400_pct']}%) are farther than 400 m on the network; {sw['sl_le_400_not_snapped']} more have no road within 150 m and cannot be tested. No place goes the other way (a walking route cannot beat a straight line). At 800 m, {sw['sl_le_800_and_net_gt_800_or_not_found_snapped']} of {sw['snapped']} snapped places are beyond 800 m on the network.")
w("")
w("### 4.3 Whole island")
w("")
w(tables["walk_island"])
w("")
w(f"On the default basis {cur_['lost_400_n']:,} places drop out at 400 m when walking is measured against current scheduled stops: {lost_snapped:,} are true detours ({N['walk_lost_pct_snapped_current']}% of the {snapped_near:,} near places that have a road within 150 m) and {cur_['lost_400_of_which_unsnapped_n']} have no road within 150 m. By category the share of straight-line-near places lost at 400 m is: " + "; ".join(f"{cats_nice[c]} {q2['full_by_category'][c]['current_scheduled']['lost_400_pct_of_sl']}%" for c in CATS) + ". Accommodations and visitor services lose most (the reason was not investigated).")
w("")
w("### 4.4 How reliable is a roads-only distance")
w("")
od = oc["osm_walk_over_roads_bin_distance_ratio_where_both_found"]
w(f"I built a second graph from the same OpenStreetMap extract with every pedestrian-usable way ({oc['osm_walk_graph']['nodes']:,} nodes, {oc['osm_walk_graph']['edges']:,} edges, {oc['osm_walk_graph']['km']:,.0f} km) and repeated the island run. Island share within 400 m of a current scheduled stop: roads-only {oc['island_current']['roads_bin']['net_400_pct']}%, full walking network {oc['island_current']['osm_full_walk']['net_400_pct']}%, straight line {oc['island_current']['roads_bin']['sl_400_pct']}%. {oc['island_current_lost_on_roads_bin_400_recovered_on_osm_walk']} of the {oc['island_current_lost_on_roads_bin_400']:,} places lost on the roads-only graph come back inside 400 m on the full network, and places with no walkable road within 150 m fall from {oc['places_default_unsnapped_roads_bin_vs_osm']['roads_bin']:,} to {oc['places_default_unsnapped_roads_bin_vs_osm']['osm_walk']}. Where both graphs find a path, the full-network distance has a median ratio {od['median']} to the roads-only one (10th to 90th percentile {od['p10']} to {od['p90']}).")
w("")
w(f"**Conclusion:** the roads-only graph is reliable enough for an *aggregate* walking-access share (about {abs(N['osm_walk_minus_roads_pts'])} point on the island; municipal shares differ from the full-network ones by a median {q2d['median_abs_diff_pts']} points, 90th percentile {q2d['p90_abs_diff_pts']}, largest {q2d['max_abs_diff_pts']} ({q2d['max_at']}), over {q2d['municipalities_with_100_or_more_places']} municipalities with 100 or more places) and for flagging places where a detour is likely. It is less reliable for one individual place: {N['recovered_share_pct']}% of the places lost on the roads-only graph come back within 400 m once footpaths, tracks, steps and service roads are added. Neither graph can see rivers without bridges, highways without crossings, fences, hills or missing sidewalks, so every walking figure must be labelled an estimate.")
w("")
w("### 4.5 Run time (measured on this machine, single-threaded Python)")
w("")
w(md(["Step", "Time"], [
    [f"Load `roads.bin` with `roads.Roads` and build the walking graph ({q2['graph']['walk_edges_used']:,} edges, spatial index)", f"{tm2['graph_build_s']} s (one-off per build; {tm2['roads_py_load_s']} s of it is `roads.Roads`)"],
    [f"Snap {tm2['stops']['scheduled']:,} stops / {q2['places']['all']:,} places", f"{tm2['stop_snap_s']} s / {tm2['place_snap_s']} s"],
    [f"Bounded Dijkstra (1,000 m) from each of {tm2['full_run_searches']:,} scheduled stops to all {q2['places']['all']:,} places", f"**{tm2['full_run_s']} s** ({tm2['full_run_per_stop_ms']} ms per stop; mean {n0(tm2['full_run_settled_nodes_per_stop_mean'])} nodes settled per search)"],
    ["Same search from the place side for the 1,000-place sample", f"{tm2['sample_search_s_per_place_ms']} ms per place"],
    ["Island run end to end (load graph, snap, search)", f"**{N['walk_end_to_end_s']} s**"],
    ["Whole script incl. sample, checks, tables", f"{tm2['total_script_s']} s"],
    ["Full OSM walking graph: read the 74 MB extract (one-off) / build graph / island run", f"{q2b['read_pbf_seconds']} s / {oc['osm_walk_graph']['build_total_s']} s / {oc['full_run_s']} s"],
]))
w("")
w(f"These are the timings of the final run. The machine was shared, and the same steps varied between the {nh} runs made here: island search {rng('island_search_s')} s, graph load {rng('graph_load_s')} s, end to end {rng('island_end_to_end_s')} s, reading the 74 MB extract {rng('pbf_read_s')} s (`timing_history.json`).")
w("")
w(f"Place-side and stop-side searches agree exactly ({q2['consistency_place_side_vs_stop_side']['mismatches_gt_0.5m']} mismatches over {q2['consistency_place_side_vs_stop_side']['checked']} places). As a plausibility check, on {q2['checks']['router_vs_walk']['pairs']} place-to-stop pairs the walking distance never exceeded the length of the `roads.Roads.route` path (median ratio router/walk {q2['checks']['router_vs_walk']['median_router_over_walk']}). A search settles only {n0(q2['full_run_settled_nodes_per_stop_mean'])} nodes on average because `roads.bin` edges are long (mean edge about {q2['graph']['km_by_class_in_file'] and round(sum(q2['graph']['km_by_class_in_file'].values()) * 1000 / q2['graph']['roads_bin_edges'])} m).")
w("")

# ================================================================================================================================
w("## 5. Question 3: gateways, ferry routes, the Eastern region, Vieques and Culebra")
w("")
w("### 5.1 What is in the data")
w("")
w(md(["Gateway kind", "ATI GTFS", "Municipal GTFS", "OpenStreetMap", "FAA", "Total"], [
    ["Airports", "-", "-", inv["airport|osm_transport"], f"{inv['airport|faa_airports']} ({q3['faa_airports']['public_use']} public use)", inv["airport|osm_transport"] + inv["airport|faa_airports"]],
    ["Rail stations (Tren Urbano)", inv["rail_station|ati_gtfs"], "-", inv.get("rail_station|osm_transport", 0), "-", inv["rail_station|ati_gtfs"] + inv.get("rail_station|osm_transport", 0)],
    ["Ferry terminals", inv["ferry_terminal|ati_gtfs"], "-", inv["ferry_terminal|osm_transport"], "-", inv["ferry_terminal|ati_gtfs"] + inv["ferry_terminal|osm_transport"]],
    ["Bus stations and terminals", inv["bus_station|ati_gtfs"], inv["bus_station|muni_gtfs"], inv["bus_station|osm_transport"], "-", inv["bus_station|ati_gtfs"] + inv["bus_station|muni_gtfs"] + inv["bus_station|osm_transport"]],
]))
w("")
w(f"- **Airports:** FAA public-use: {', '.join(q3['faa_airports']['codes_public'])}; {q3['faa_airports']['total'] - q3['faa_airports']['public_use']} private-use strips. OpenStreetMap adds Diego Jiménez Torres in Fajardo (FAJ), two seaplane bases (Fajardo, San Juan) and {inv['airport|osm_transport'] - 3} other airfields (historic, closed, military, on Mona Island or unnamed). FAJ is missing from the FAA list in the published file.")
rail_m = ", ".join(f"{k} {v}" for k, v in q3["rail_stations"]["municipalities"].items())
w(f"- **Rail:** {q3['rail_stations']['n']} Tren Urbano stations ({rail_m}), {', '.join(str(x) for x in q3['rail_weekday_trips_values'])} weekday trips per station; no other rail.")
w(f"- **Bus terminals:** {q3['bus_stations']['ati']} ATI (Covadonga in Old San Juan, Sagrado Corazón, Piñero, Cupey, Bayamón, Cataño, Carolina, Iturregui, Campanilla and others), {q3['bus_stations']['muni_gtfs']} in municipal feeds ({q3['bus_stations']['muni_gtfs_by_operator']['san_lorenzo']} in San Lorenzo's expired feed), and {q3['bus_stations']['osm']} volunteer-mapped OpenStreetMap stations with no timetable. {q3b['municipalities_without_any_bus_station']} of 78 municipalities have no bus station in any source.")
w(f"- **Taxi and ride-hailing:** {q3b['taxi_stands']['n']} mapped taxi stands in {q3b['taxi_stands']['municipalities']} municipalities; Uber's cities page lists {q3b['uber_listed_municipalities']} municipalities (a yes/no listing, not coverage).")
w("")
w("### 5.2 Ferry routes in the timetable and route files")
w("")
rows = []
for code in ("CSJ", "CC", "CI", "CM"):
    r = fr[code]
    rows.append([code, r["long_name"], "ATI GTFS feed", " - ".join(r["stops"]), r["trips_weekday"], r["trips_saturday"], r["trips_sunday"], f"{r['first_hhmm']}-{r['last_hhmm']}", f"{tt['wk'][code]['median_minutes_first_to_last_stop']:.0f} min"])
w(md(["Route", "Name", "Operator in the data", "Stops", "Trips weekday", "Sat", "Sun", "First to last departure (weekday)", "Crossing time"], rows))
w("")
w(f"Trips are one-way sailings (CSJ: {fr['CSJ']['trips_weekday'] // 2} each way). The data hold no ferry operator other than ATI: Fajardo's terminal, private passenger boats and any other lake or bay ferries have no timetable.")
w("")
w("### 5.3 Link from each gateway to land transit")
w("")
air = [x for x in q3["gateway_land_links"] if x["kind"] == "airport" and x["source"] == "faa_airports"]
w(md(["Public-use airport (FAA code)", "Municipality", "Nearest current bus stop", "Current bus stops within 400 m", "Weekday calls at the busiest of them"],
     [[x["code"], x["municipality"], dist_txt(x["nearest_current_bus_stop_m"]), x["current_bus_stops_within_400m"], x["max_weekday_trips_at_a_stop_within_400m"] or "-"] for x in air]))
w("")
srt = sorted(air, key=lambda x: x["nearest_current_bus_stop_m"])
w(f"Only SJU has a current scheduled stop within 400 m ({sj['n']} stops lie within 500 m of its reference point, at {', '.join(str(x) for x in sj['distances_m'])} m; ATI routes {', '.join(sj['routes'])} stop there). The next closest are {srt[1]['code']} at {dist_txt(srt[1]['nearest_current_bus_stop_m'])}, {srt[2]['code']} at {dist_txt(srt[2]['nearest_current_bus_stop_m'])} and {srt[3]['code']} at {dist_txt(srt[3]['nearest_current_bus_stop_m'])}; the rest are more than {int(srt[4]['nearest_current_bus_stop_m'] / 1000)} km from any current bus stop.")
w("")
fer = [x for x in q3["gateway_land_links"] if x["kind"] == "ferry_terminal"]
pier = next(x for x in fer if "Carnival" in x["name"])
fer_rows = [[(x["name"].split(" Ángel")[0] if x["name"] != "(no name)" else "(unnamed OSM node)"), "ATI feed" if x["source"] == "ati_gtfs" else "OpenStreetMap", dist_txt(x["nearest_current_bus_stop_m"]), x["current_bus_stops_within_400m"], x["max_weekday_trips_at_a_stop_within_400m"] or "-"] for x in fer if "Carnival" not in x["name"]]
fer_rows.append(["Cruise pier 4, Old San Juan (mapped as a ferry terminal)", "OpenStreetMap", dist_txt(pier["nearest_current_bus_stop_m"]), pier["current_bus_stops_within_400m"], pier["max_weekday_trips_at_a_stop_within_400m"]])
w(md(["Ferry terminal", "Source", "Nearest current bus stop", "Current bus stops within 400 m", "Weekday calls at the busiest"], fer_rows))
w("")
rail = [x for x in q3["gateway_land_links"] if x["kind"] == "rail_station"]
no_bus = [x for x in rail if x["current_bus_stops_within_400m"] == 0]
atib = [x for x in q3["gateway_land_links"] if x["kind"] == "bus_station" and x["source"] == "ati_gtfs"]
atib0 = [x for x in atib if x["current_bus_stops_within_400m"] == 0]
w(f"Tren Urbano: {len(rail) - len(no_bus)} of {len(rail)} stations have current bus stops within 400 m ({min(x['current_bus_stops_within_400m'] for x in rail if x['current_bus_stops_within_400m'])} to {max(x['current_bus_stops_within_400m'] for x in rail)} stops; up to {max(x['max_weekday_trips_at_a_stop_within_400m'] for x in rail)} weekday calls at the busiest); " + "; ".join(f"{x['name'].replace('Estación ', '')} has none within {x['nearest_current_bus_stop_m']:,.0f} m" for x in no_bus) + f". Of the {len(atib)} ATI bus terminals, {len(atib) - len(atib0)} have other current bus stops within 400 m; " + "; ".join(f"{x['name']}: nearest at {x['nearest_current_bus_stop_m']:,.0f} m" for x in atib0) + ".")
w("")
w("### 5.4 Cruise and port facilities, and what is missing")
w("")
w(f"- **Cruise:** one feature, a pier in Old San Juan mapped as `amenity=ferry_terminal`. No cruise or port facility is recorded elsewhere on the island. The build's OpenStreetMap query asks only for stops, stations, ferry terminals, taxi stands, bicycle rental, charging stations, aerodromes and helipads, so port, harbour and pier features are not captured. Old San Juan has good last-mile data: Terminal Covadonga is {q3['cruise_pier_to_terminal_covadonga_m']} m from the pier and has {pier['max_weekday_trips_at_a_stop_within_400m']} weekday calls on the busiest stop within 400 m of it.")
w("- **Passenger counts:** none in the data (no FAA enplanements, port statistics or ferry ridership), so gateways cannot be weighted by visitor volume.")
ceib = " and ".join(f"{x} m" for x in q3["osm_ferry_nodes_in_ceiba_m_from_ati_terminal"])
w(f"- **Ferries without a timetable:** none of the {inv['ferry_terminal|osm_transport']} OpenStreetMap ferry terminals carries a timetable: Fajardo's terminal ({q3b['fajardo_ferry_terminal_osm_to_nearest_scheduled_stop']['m']} m from a stop of Fajardo's municipal feed, which has expired), an unnamed San Juan node, an unnamed node on a reservoir in Arecibo, the AcuaExpreso node at Hato Rey (no service in the ATI feed), the cruise pier, and two nodes in Ceiba that are {ceib} from the ATI Ceiba terminal and probably the same facility.")
w(f"- **Públicos (carros públicos):** the main non-metro mode is not in any timetable. Only the {q3['bus_stations']['osm']} volunteer-mapped bus stations exist; {q3b['municipalities_without_any_bus_station']} municipalities have no bus station in any source.")
w(f"- **Rental cars, taxis, ride-hailing:** {q3b['taxi_stands']['n']} taxi stands, a yes/no Uber list and the Overture places of type Transportation ({q3['places_port_related_types']['Transportation']} listings, aggregate only). No fares or availability.")
w("- **Real time:** none (the twin's own table says ATI's GTFS-Realtime feed is \"en desarrollo\").")
w("")
w("### 5.5 Eastern region (Porta del Mar), Vieques and Culebra")
w("")
e1, em, vq, cu = q3["east_porta_del_mar"], q3["east_mainland"], q3["vieques"], q3["culebra"]
rows = []
for x in (e1, em, vq, cu):
    rows.append([x["label"], f"{x['places_default']:,}", " / ".join(f"{x['by_category'][c]:,}" for c in CATS), f"{x['pct400_any_stop']}%", f"{x['pct400_current_scheduled']}%", f"{x['pct400_current_trips20']}%", f"{x['pct400_rail_or_ferry']}%", f"{x['median_km_to_ferry_terminal_any']} km"])
w(md(["Area", "Default places", "Accomm. / Attr. / Gastr. / Visitor serv.", "Any stop 400 m", "Current scheduled 400 m", ">=20 calls 400 m", "Rail or ferry 400 m", "Median distance to a ferry terminal"], rows))
w("")
w("By municipality in Porta del Mar:")
w("")
w(md(["Municipality", "Default places", "Scheduled stops (current / expired)", "OSM stops", "Any stop 400 m", "Current scheduled 400 m", "Municipal feed today"],
     [[r["municipality"], r["places_default"], f"{r['scheduled_stops']} ({r['of_which_current']} / {r['of_which_expired']})", r["osm_stops"], f"{r['pct400_any_stop']}%", f"{r['pct400_current_scheduled']}%", r["feed_status_of_muni_operator"]] for r in q3["east_rows"]]))
w("")
w("Transport links in the data:")
w("")
cross_min = min(tt["wk"][c]["median_minutes_first_to_last_stop"] for c in ("CI", "CM", "CC"))
cross_max = max(tt["wk"][c]["median_minutes_first_to_last_stop"] for c in ("CI", "CM", "CC"))
w(f"- **Ferries (ATI):** Ceiba to Vieques (CI, {fr['CI']['trips_weekday']} trips weekdays, {fr['CI']['trips_saturday']} Saturday and Sunday), Ceiba to Vieques Mosquito (CM, {fr['CM']['trips_weekday']} weekdays only), Ceiba to Culebra (CC, {fr['CC']['trips_weekday']} weekdays, {fr['CC']['trips_saturday']} weekends); the median crossing is {cross_min:.0f} minutes{'' if cross_min == cross_max else f' to {cross_max:.0f} minutes'}. Four ATI ferry terminals serve the islands (Ceiba, Culebra, Vieques Isabel II, Vieques Mosquito); the two Vieques terminals carry no municipality in the file ({q5['stops_without_municipality']['n']} scheduled features, four of them ferry terminals, fall outside the shoreline-clipped boundaries).")
w("- **Airports:** Vieques VQS, Culebra CPX, Ceiba RVR, Humacao X63 (FAA public use); Fajardo FAJ and a seaplane base (OpenStreetMap). No scheduled bus serves any of them.")
w(f"- **Vieques municipal bus:** {q3['vieques_municipal_system']['routes']} route, {q3['vieques_municipal_system']['stops']} stops, {q3['vieques_municipal_system']['weekday_trips']} weekday trips, feed valid to {q3['vieques_municipal_system']['feed_end']}. {q3['vieques_pct400_municipal_bus_stops']}% of Vieques' {q3['vieques_places_default']} default places are within 400 m of one of its stops and {q3['vieques_pct400_ati_ferry_terminals']}% within 400 m of an ATI ferry terminal ({q3['vieques_pct400_either']}% either); none is near a stop with 20 or more calls.")
w(f"- **Culebra:** no municipal system, no bus stop of any source. The {cu['pct400_current_scheduled']}% of Culebra places near a \"scheduled stop\" are all near the ferry dock ({cu['pct_within_2km_ferry_terminal_any']}% are within 2 km of it).")
w(f"- **Land side:** the easternmost ATI bus stop is in {q3b['easternmost_ati_bus_stop']['municipality']}. The Ceiba ferry terminal is {q3b['ceiba_ferry_terminal_to_nearest_ati_bus_stop_km']} km from the nearest ATI bus stop and {q3b['ceiba_ferry_terminal_to_nearest_other_scheduled_stop']['km']} km from the nearest other scheduled stop, which belongs to Fajardo's municipal feed (expired {fe['fajardo']['end']}). In the scan from SJU the Ceiba, Vieques and Culebra terminals are never reached.")
w(f"- **Eastern mainland:** Canóvanas ({mr['Canóvanas']['pct400_current_scheduled']}% of places near a current scheduled stop; ATI plus a municipal feed that ends {fe['canovanas']['end']}), Loíza ({mr['Loíza']['pct400_current_scheduled']}%, ATI) and Humacao ({mr['Humacao']['pct400_current_scheduled']}%, a current municipal feed with {fe['humacao']['stops']} stops) are served; Fajardo, Juncos and San Lorenzo show high any-stop shares only because of expired feeds; Luquillo, Naguabo, Yabucoa, Maunabo, Las Piedras and Río Grande have no place near a current scheduled stop. Mona Island has {q3['mona_island_places_default']} default places and one OpenStreetMap airfield run by the Department of Natural and Environmental Resources; no scheduled service.")
w("")

# ================================================================================================================================
w("## 6. Question 4: journey times from SJU (prototype)")
w("")
w("### 6.1 Method and what the data allow")
w("")
w("- **Algorithm:** earliest-arrival scan in rounds (connection scan with RAPTOR-style rounds): at most 3 boardings (2 transfers), walking links up to 400 m straight line at 4.8 km/h between stops, 180 s buffer on every boarding after the first, no buffer for the first boarding. Start 10:00 on a typical weekday. Horizon 4 hours. Places are reached from stops within 400 m (arrival at the stop plus walking); a place needs at least one vehicle leg.")
w(f"- **Origin:** the {sj['n']} scheduled stops within 500 m of the FAA reference point of SJU ({', '.join(str(x) for x in q4['origin_sju']['walk_distances_m'])} m; walking {sj['walk_minutes_min_max'][0]} to {sj['walk_minutes_min_max'][1]:.0f} minutes). The reference point is the airfield centre, not the terminal door; I widened the radius from 400 m to 500 m so the curbside stops count.")
tc, ta = q4["timetable_weekday_current_feeds"], q4["timetable_weekday_all_feeds"]
w(f"- **Timetable used:** weekday file, current feeds only: {tc['trips']:,} trips, {tc['connections']:,} stop-to-stop connections, {tc['stops_with_calls']:,} stops with calls. The {n_exp} expired feeds are left out ({ta['trips'] - tc['trips']} trips); including them changes nothing because none of their stops is reachable.")
w("- **What the files do not support, exactly:** trips have no stop ID, trip ID or route-pattern ID (a stop is a coordinate, a trip a list position), calls without a time are absent (so on routes that publish only timepoints the intermediate stops are missing), five Patillas routes are removed, there are no calendar exceptions or holidays, no frequency-based trips and no fare or transfer rules. The best this data can do is what is shown here: a schedule-based, timepoint-level estimate. Cross-feed transfers rely on a 400 m walk between coordinates.")
w(f"- **Verification:** a brute-force computation of 1, 2 and 3 boardings gives the same earliest arrival at all {q4c['stops_reached_scan']:,} reached stops ({q4c['mismatching_stops']} mismatches).")
w("")
w("### 6.2 Results: share of default places reachable within 60, 90 and 120 minutes")
w("")
w("By category (transit = scheduled, weekday 10:00; drive = free-flow estimate, see 6.4):")
w("")
w(tables["sju_category"])
w("")
w("By tourism region:")
w("")
w(tables["sju_region"])
w("")
w(f"Of the {m4['all']['reachable_any_within_4h']:,} places reachable within 4 hours by transit, the median is {m4['all']['median_minutes_of_reachable']:.0f} minutes. {q4['municipalities_with_any_place_within_120']} of 78 municipalities have any place within 120 minutes and {q4['municipalities_with_ge50pct_within_120']} reach 50% (`q4_sju_by_municipality.csv`). The scan reaches {m4['stops_reached_by_vehicle_any_round']:,} stops by vehicle: {m4['stops_reached_by_round']['1']} with one boarding, {m4['stops_reached_by_round']['2']} with two, {m4['stops_reached_by_round']['3']} with three. Within 120 minutes, {m4['within_120_with_1_boardings_exactly']:,} places need one boarding, {m4['within_120_with_2_boardings_exactly']:,} two and {m4['within_120_with_3_boardings_exactly']:,} three.")
w("")
n_other = len(ro) - 4
w(f"Stops reached by operator (all feeds loaded): ATI {ro['ati']['reached']:,} of {ro['ati']['stops_with_calls']:,}, San Juan municipal {ro['san_juan']['reached']} of {ro['san_juan']['stops_with_calls']}, Guaynabo {ro['guaynabo']['reached']} of {ro['guaynabo']['stops_with_calls']}, Bayamón {ro['bayamon']['reached']} of {ro['bayamon']['stops_with_calls']}; **none of the other {n_other} municipal feeds is connected** (no stop within a 400 m walk of an ATI stop within 3 boardings).")
w("")
w("Sensitivity (share of default places within the stated time):")
w("")
w(tables["sju_sens"])
w("")
w(f"Time of day matters little; the day of week matters a lot (Sunday only {q4['sensitivity']['sunday_10_current']['pct_within_120']}% within 120 minutes). Fewer boardings sharply lower reach: with one boarding only {q4['sensitivity']['weekday_10_max1_boarding']['pct_within_120']}% of places are reachable at all.")
w("")
oo = q4["other_gateway_origins_weekday_10"]
w("Other origins, same rules (share within 60 / 90 / 120 minutes): " + "; ".join(f"{lbl} {v['pct_within_60']}% / {v['pct_within_90']}% / {v['pct_within_120']}%" for lbl, v in (("Terminal Covadonga (Old San Juan)", oo["terminal_covadonga_old_san_juan"]), ("the Old San Juan cruise pier", oo["old_san_juan_cruise_pier_osm_mapped"]), ("the Ceiba ferry terminal", oo["ceiba_ferry_terminal_ati"]))) +
  f". From the Ceiba terminal only the ferries connect: {oo['ceiba_ferry_terminal_ati']['reachable_any_within_4h']} places are reachable within 4 hours (" + ", ".join(f"{k} {v}" for k, v in oo["ceiba_ferry_terminal_ati"]["reachable_within_4h_by_municipality"].items()) + ").")
w("")
w("### 6.3 Plausibility checks (public facilities)")
w("")
pc = q4["pair_checks"]
w(md(["From SJU at 10:00 to", "Minutes (any means)", "Boardings if by vehicle"], [
    ["Terminal Covadonga, Old San Juan", f"{pc['Terminal Covadonga (Old San Juan)']['minutes_from_10:00']:.0f}", pc["Terminal Covadonga (Old San Juan)"]["boardings_if_by_vehicle"]],
    ["Tren Urbano Río Piedras", f"{pc['Estación Río Piedras']['minutes_from_10:00']:.0f}", pc["Estación Río Piedras"]["boardings_if_by_vehicle"]],
    ["Tren Urbano Bayamón terminus", f"{pc['Estación Bayamón (Tren Urbano)']['minutes_from_10:00']:.0f}", pc["Estación Bayamón (Tren Urbano)"]["boardings_if_by_vehicle"]],
    ["Terminal de Carolina", f"{pc['Terminal de Carolina']['minutes_from_10:00']:.0f}", pc["Terminal de Carolina"]["boardings_if_by_vehicle"]],
    ["Caguas public transport terminal", f"{pc['Terminal Transporte Publico de Caguas']['minutes_from_10:00']:.0f}", pc["Terminal Transporte Publico de Caguas"]["boardings_if_by_vehicle"]],
    ["Cataño ferry terminal", f"{pc['Terminal de Lancha Cataño (ferry)']['minutes_from_10:00']:.0f}", pc["Terminal de Lancha Cataño (ferry)"]["boardings_if_by_vehicle"]],
    ["Ceiba / Vieques / Culebra ferry terminals", "not reached" if all(pc[k]["minutes_from_10:00"] is None for k in ("Terminal de Lanchas de Ceiba (ferry)", "Terminal de Lanchas Vieques (Isabel II)", "Terminal de Lanchas Culebra")) else "see data", "-"],
]))
w("")
w("These times are internally consistent (a bus to Old San Juan needs one boarding; the Tren Urbano needs a bus plus a train) but were not checked against the operator's journey planner or rider experience.")
w("")
w("### 6.4 Driving comparison (estimate)")
w("")
w(f"**Estimate, not a measurement.** Dijkstra over `roads.bin` from the road nearest SJU ({q4['drive_origin_snap_connector_m']:.0f} m from the reference point, a {q4['drive_origin_edge_class']} road), one-way rules obeyed, the planning speeds of `roads.py` (motorway 90, trunk 75, primary 55, secondary 48, tertiary 40, residential 25 km/h; these are planning ratios, not speed limits), a 20 km/h connector from the road to the place, no traffic, signals, tolls, parking or waiting. It was not validated against measured drive times (median {q4['drive_by_region']['Porta Caribe']['median_minutes']:.0f} minutes to Porta Caribe places). Places with no road path from the main graph, mainly Vieques, Culebra, Mona and a few remote sites, count as unreachable: {q4['drive_all']['pct_no_road_path_or_no_road_within_300m']}% of default places.")
w("")
tr_ = q4["transit_over_drive_time_ratio_places_reachable_by_transit_le_120"]
w(f"Where transit reaches a place within 120 minutes, it takes a median {q4['median_transit_minutes_of_those_places']:.0f} minutes against {q4['median_drive_minutes_of_those_places']:.0f} by car (ratio {tr_['median']}, inter-quartile {tr_['p25']} to {tr_['p75']}). Of the places within 60 minutes of SJU by car, {q4['of_places_within_60_min_drive_share_also_within_60_min_transit_pct']}% are within 60 minutes by transit and {q4['of_places_within_60_min_drive_share_also_within_120_min_transit_pct']}% within 120.")
w("")

# ================================================================================================================================
w("## 7. Question 5: data problems that would distort the analysis")
w("")
sp = q5["scheduled_stop_pairs_within_30m"]
oq = q3b["osm_bus_stops_and_stations"]
exp_txt = ", ".join(f"{opname(k)} {fe[k]['end']}" for k in ("hatillo", "cidra", "caguas", "san_lorenzo", "fajardo", "juncos"))
w(md(["Problem", "Count", "Effect", "What to do"], [
    ["Expired timetables", f"{n_exp} operators, {q5['expired_stops']} stops ({q5['expired_stop_share_pct']}% of {q5['scheduled_stops_total']:,}); Ponce ended {fe['ponce']['end']} ({fe['ponce']['days_since_end']} days ago), {exp_txt}; one more ends {fe['canovanas']['end']} (Canóvanas, {fe['canovanas']['stops']} stops)", f"{why['expired_only']:,} default places count as near only because of them; the any-stop measure, `pop_served_pct` and the 800 m gaps layer all include them", "Evaluate feed status at build time and per stop; show both counts. Expiry means the published timetable does not cover today, not that service stopped. Ask the operators for new feeds (OUTREACH_TRANSIT_DATA.md)"],
    ["Stale place fields", f"{b1['flag_false_to_true_default']} default places lack a 400 m flag they should have ({b1['flag_changes_default_jayuya']} in Jayuya); {b1['places_where_transit_m_differs_by_more_than_2m_all']} places in the file ({b1['places_where_transit_m_differs_by_more_than_2m_default']} on the default basis) have a `transit_m` that differs by more than 2 m from today's stop list: {b1['jayuya_places_all']} in Jayuya and {b1['differs_gt2m_not_jayuya_all']} elsewhere; the published value is the longer one in {b1['differs_gt2m_new_closer_all']} of the {b1['places_where_transit_m_differs_by_more_than_2m_all']} cases", f"Jayuya shows {b1['jayuya_default_pct400_published']}% instead of {b1['jayuya_default_pct400_recomputed']}%; the nightly refresh rewrites stops but never `places.json`", "Compute place access fields in a function called by both `build.py` and `refresh_network.py`"],
    ["Wrong stop coordinates", f"{q5['jayuya']['stops_in_transport_json']} Jayuya stops had positive longitudes (fixed in `transport.json`); 1 Jayuya stop ({qx['jayuya_stop_in_caguas'][0]['trips_weekday']} weekday calls) is still {N['jayuya_far_km']} km from Jayuya (lng {qx['jayuya_stop_in_caguas'][0]['lng']}), the only municipal stop more than 3 km outside its own municipality; {q5['scheduled_stops_not_within_150m_of_road_graph']['n']} scheduled stops are over 150 m from any road ({q5['scheduled_stops_not_within_150m_of_road_graph']['not_within_500m']} over 500 m)", "A bad stop creates false \"served\" places (or false gaps) near its wrong position", "Add a sanity check to `parse_gtfs`: distance to the operator's municipality and to the nearest road; drop or flag outliers"],
    ["Duplicate stops", f"{sp['total']} pairs of scheduled stops within 30 m ({sp['same_operator']} same operator, {sp['different_operators']} across operators: {N['cross_pairs_text']}); {q5['scheduled_stops_sharing_exact_coordinates_with_another_stop_id']['locations']} locations hold {q5['scheduled_stops_sharing_exact_coordinates_with_another_stop_id']['stops']} stop IDs; {oq['n']} OSM bus stops and stations: {oq['operator_tag_ama']} tagged AMA (whose routes are already in the ATI feed), {oq['within_30m_of_scheduled'] + oq['30_to_100m']} within 100 m of a scheduled stop ({oq['within_30m_of_scheduled']} within 30 m, which the build should have folded)", "Inflates stop counts and \"stops per municipality\"; hardly changes distances", "Fold OSM stops within 100 m and flag cross-operator pairs as one physical stop"],
    ["Calls missing from the trip files", f"{q5['weekday_calls']['share_missing_pct']}% of weekday calls ({mt['weekday_calls_in_trips_json_total']:,} of {mt['weekday_calls_feed_total']:,}); {zc['n']} locations ({pct(zc['n'], mt['stop_locations'])}%) have none; {N['keeps_text']}", "Journey times and the timetable replay understate municipal service; weekend flags rely on the route calendar for these", "Interpolate untimed calls (GTFS rule) or write all calls with a flag; keep stop IDs in the trip files"],
    ["Route/stop mismatches", f"{q5['routes_with_order_note_non_geographic_stop_order']['n']} Patillas routes have a non-geographic stop order and 0 trips in the file; {q5['implausible_bus_hops_in_trip_files']['flagged']} of {q5['implausible_bus_hops_in_trip_files']['hops_checked']:,} bus hops are implausible (zero or negative time over 500 m, or over 100 km/h in a straight line); {q5['scheduled_stops_with_zero_weekday_trips']} stop with no route and no weekday trip", "Small; they affect individual connections, not shares", "Keep the `order_note` rule; reject hops above a speed limit in `parse_gtfs`"],
    ["Zero-trip stops", f"{q5['scheduled_stops_with_zero_weekday_trips']} scheduled stop. {q5['current_stops_with_saturday_service']:,} of {q5['current_stops_without_weekend_service']['current_stops']:,} current stops have Saturday service, {q5['current_stops_with_sunday_service']} have Sunday service", "Weekend access is almost entirely ATI, Guaynabo and Vega Alta", "Carry Saturday and Sunday calls per stop"],
    ["No timetable at all", f"{op_types['municipal']['none']} municipal systems in the NTD list and the públicos authority publish no feed; {op_types['municipal']['with feed']} municipal systems do; públicos are in no feed; {q3b['municipalities_without_scheduled_stop']} of 78 municipalities have no scheduled stop", "Absence of a stop is not absence of transport", "Say so in every label"],
    ["Municipality of stops and places", f"{q5['stops_without_municipality']['n']} scheduled features have no municipality (piers and shoreline stops, up to {q5['stops_without_municipality']['max_dist_to_polygon_m'] / 1000:.1f} km from a polygon); {q5['places_outside_every_municipality_polygon']['default']} default places ({pct(q5['places_outside_every_municipality_polygon']['default'], NDEF)}%) fall outside every polygon and take the nearest centre", "Municipal stop counts miss the Vieques, Cataño and San Juan ferry terminals; a few places may be assigned to the wrong municipality", "Use nearest-polygon assignment with a distance limit"],
    ["Resident file", f"`population_blocks.json` column 4 is metres to the nearest scheduled stop (capped at 9,999; {q5['population_blocks_fourth_value']['n_capped_9999']:,} of {q5['population_blocks_fourth_value']['n_blocks']:,} blocks capped), not housing units as the brief assumes; it includes expired feeds", "A reader taking it for housing units would get nonsense; the distance ignores feed status", "Document it; add a current-feeds distance"],
    ["Airports list", f"FAA public-use list has {q3['faa_airports']['public_use']}; FAJ (Fajardo) is only in OpenStreetMap; HANDOFF says the old {q3['faa_airports']['total']}-record airports file is still published", "Gateway tables are incomplete", "Next full build (already fixed in code)"],
    ["Personal data check", f"`places.json` carries business name for all {q5['places_with_name_address_website']['name']:,} places, address for {q5['places_with_name_address_website']['address']:,} and website for {q5['places_with_name_address_website']['website']:,}; some may identify individuals (sole traders). Stop names can embed business or organisation names. No email pattern in `transport.json` or `operators.json`; no personal cloud link in `operators.json`", "Not printed here. Anything published from this analysis must stay aggregate", "Keep access series aggregate; do not add names to new files"],
]))
w("")
sh = q5["default_places_sharing_a_point_with_another_default_place"]
w(f"A further caution on places: {sh['places_in_shared_points']:,} default places share a map point with another place (up to {sh['max_places_at_one_point']} at one point), so their distances are identical; counts of places near transit are counts of listings, not of businesses or visitors.")
w("")

# ================================================================================================================================
w("## 8. Question 6: recommended method")
w("")
w("### 8.1 Principle")
w("")
w(f"Link each tourism place to transport in three layers, from most to least certain: (1) the nearest *scheduled stop with a current timetable* and what it offers; (2) a walking-distance check on the road graph; (3) hub and gateway proximity and journey times. Publish the layers as separate, labelled fields. Do not merge them into one score: the weights would be a policy choice that FPR has not made, and a score would hide that {N['no_stop_800_pct']:.0f}% of places have no current scheduled stop within 800 m.")
w("")
w("Access classes for the default basis (computed from the Tier 1 distances; a candidate legend):")
w("")
w(tables["classes"])
w("")
hw = hp["places_without_current_scheduled_stop_within_800m"]
w(f"The {hw['n']:,} places in the last two rows are where a hub connection matters: {hw['pct_within_5000m_of_any_gateway']}% are within 5 km and {hw['pct_within_10000m_of_any_gateway']}% within 10 km of some gateway (airport, ferry terminal, rail station or bus terminal, counting the volunteer-mapped ones); for all default places the median distance to a bus terminal is {hp['bus_terminal_scheduled_or_osm']['median_km']} km, to an airport {hp['public_airport']['median_km']} km, to a ferry terminal {hp['ferry_terminal_any']['median_km']} km, to a rail station {hp['rail_station']['median_km']} km.")
w("")
w("### 8.2 Tiers")
w("")
t1 = q1["timing_s"]
w(md(["Tier", "What it adds", "Needs road graph", "Build cost (measured)", "Added first-load weight (gzip)", "Status"], [
    ["0. Fix and relabel", "Rebuild stale place fields; call the old field \"any mapped stop\"; show feed status", "No", "seconds", "0", "Do first"],
    ["1. Service-qualified stop (cheap, robust)", "`ts_m`, `ts_calls`, `ts_we`; shares at 400 and 800 m per area; access classes", "No", f"{t1['distances_for_15_stop_sets_35118_places']} s for 15 stop sets on 35,118 places (the three fields need three of them); {t1['total']} s for the whole script", f"{ps['core3_ts_m_ts_calls_ts_we']['gzip6_added_kb']:.0f} KB in `places.json`, or {q6['binary_core3_columns']['gzip6_kb']:.0f} KB as typed columns; areas about {q6['municipalities_json_added']['gzip6_added_kb']:.0f} KB (municipalities) and {q6['barrios_geojson_added']['gzip6_added_kb']:.0f} KB (barrios)", "Ready; checked two ways"],
    ["2. Walking distance", "`tw_m`; share within 400 m walking per area", "Yes (`roads.bin`; optional full OSM walking graph)", f"{N['walk_end_to_end_s']} s end to end with `roads.bin` ({q2['full_run_s']} s of searches); a full OSM graph adds a one-off read of the extract ({rng('pbf_read_s')} s over {nh} runs) and {oc['full_run_s']} s per run in the final run", f"{ps['tier1_plus_tw_m']['gzip6_added_kb'] - ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['gzip6_added_kb']:.0f} KB (JSON) or {q6['binary_columns_gzip_kb_each']['tw_m']:.0f} KB (typed column)", "Ready as an estimate"],
    ["3. Gateway journey times", "`gw` times by transit and by car from named gateways; area series", "Transit scan: no. Driving comparator: yes", f"timetable {tc['build_s']} s, scan {q4['scan_seconds_one_origin']} s per origin and departure, driving graph {q4['drive_dijkstra_s']} s once", f"{ps['tier1_plus_tw_m_plus_sju_t_sju_b_sju_d']['gzip6_added_kb'] - ps['tier1_plus_tw_m']['gzip6_added_kb']:.0f} KB per gateway (JSON, three fields) or {q6['binary_columns_gzip_kb_each']['sju_t'] + q6['binary_columns_gzip_kb_each']['sju_b'] + q6['binary_columns_gzip_kb_each']['sju_d']:.0f} KB as typed columns", "Prototype; not ready to publish beyond the San Juan metro"],
    ["4. Data to obtain, not compute", "Current municipal feeds; untimed calls; carros públicos routes and terminals; ATI GTFS-Realtime; cruise and port facilities; ferry operators other than ATI; sidewalks and footpaths", "-", "-", "-", "Open requests; see `OUTREACH_TRANSIT_DATA.md`"],
]))
w("")
w("### 8.3 Per-place fields (name, unit, definition)")
w("")
w(md(["Field", "Unit", "Definition", "Tier"], [
    ["`ts_m`", "metres (integer, 99,999 cap)", "Straight-line distance to the nearest scheduled stop whose operator feed has not ended on the build date. Scheduled = ATI or municipal GTFS. Excludes OpenStreetMap-only stops, airports, taxi stands and chargers. Replaces the use of `transit_m` for access statements.", "1"],
    ["`ts_calls`", "calls per weekday (integer; missing = none within 400 m)", "Largest `trips_weekday` among current scheduled stops within 400 m: scheduled stop events on a typical Wednesday, both directions if served. A frequency proxy, not a headway.", "1"],
    ["`ts_we`", "bit flags (1 = Saturday, 2 = Sunday; missing = none in the data)", "OR of the Saturday and Sunday flags of current scheduled stops within 400 m, taken from the feed calendar inside `parse_gtfs` (not by coordinate matching). Missing means no weekend service in the published feed.", "1"],
    ["`tw_m`", "metres (integer; missing = more than 1,000 m or no road within 150 m)", "Walking distance along mapped roads (`roads.bin`, motorways excluded, one-way rules ignored) from the place to the nearest current scheduled stop, including connectors. An estimate: no footways, sidewalks, stairs or crossings.", "2"],
    ["`transit_m`, `transit_400m`, `nearest_stop`", "unchanged", "Keep for continuity; relabel as \"nearest mapped stop of any kind, including expired timetables and volunteer-mapped stops\".", "0"],
    ["`gw_t_<id>`, `gw_b_<id>`, `gw_d_<id>`", "minutes; boardings (1 to 3); minutes", "Per gateway `<id>` from `gateways.json`: earliest scheduled-transit arrival minutes (weekday 10:00, at most 3 boardings, walking links up to 400 m at 4.8 km/h, 3-minute buffer; missing = not reached within 240 minutes), boardings, and free-flow driving minutes (planning speeds, no traffic; missing = no road path). Start with SJU and Old San Juan.", "3"],
]))
w("")
w(f"Nearest hub of each kind (rail station, ferry terminal, airport, bus terminal): compute in the browser from `gateways.json` (about {q6['gateways_json_estimate']['gzip6_kb']:.0f} KB gzip, {q6['gateways_json_estimate']['records']} records) rather than storing per-place fields; storing `hub_m` and `hub` for every place would add about {ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['gzip6_added_kb'] - ps['core3_ts_m_ts_calls_ts_we']['gzip6_added_kb']:.0f} KB gzip.")
w("")
w("### 8.4 Per-area series (municipality, tourism region, barrio)")
w("")
w("All are shares of default-basis tourism places in the area unless stated. Publish the denominator (`access_n`) and the date (`access_as_of`); suppress shares where `access_n` is below 10 (many barrios) and say so.")
w("")
w(md(["Field", "Unit", "Definition"], [
    ["`acc_any400_pct`, `acc_any800_pct`", "% of places", "A mapped stop of any kind within 400 / 800 m (the legacy measure; equals `transit_pct` at 400 m once the stale fields are rebuilt)."],
    ["`acc_cur400_pct`, `acc_cur800_pct`", "% of places", "A current scheduled stop within 400 / 800 m."],
    ["`acc_freq400_pct`", "% of places", "A current scheduled stop with 20 or more weekday calls within 400 m (state the threshold in the field's metadata; 10 and 40 can be added)."],
    ["`acc_sat400_pct`, `acc_sun400_pct`", "% of places", "A current scheduled stop with Saturday / Sunday service within 400 m."],
    ["`acc_hub400_pct`, `acc_hub800_pct`", "% of places", "A rail station or ferry terminal within 400 / 800 m."],
    ["`acc_walk400_pct`", "% of places", "Walking distance (Tier 2) of 400 m or less to a current scheduled stop. Estimate."],
    ["`acc_paper_pct`", "% of places", "Places whose only stop within 400 m comes from an expired timetable or from OpenStreetMap: the \"served on paper\" gap. Together with `acc_cur400_pct` it explains the difference from `acc_any400_pct`."],
    ["`stops_current`, `stops_expired`, `stops_osm`", "count", "Stops by feed state in the area, with `feed_end` (latest end date of the operators serving it)."],
    ["`pop_served_freq_pct`, `pop_served_sat_pct`", "% of residents", "Same tests for residents (Census block centres), next to the existing `pop_served_*` fields."],
    ["`gw_<id>_t60_pct`, `_t90_pct`, `_t120_pct`, `_d60_pct`, `_d90_pct`, `_d120_pct`", "% of places", "Share reachable within 60 / 90 / 120 minutes from a gateway by scheduled transit (`_t`) and by car estimate (`_d`). Publish only where the transit scan reaches the area; otherwise show \"no scheduled link in the data\"."],
    ["`access_n`, `access_as_of`", "count; date", "Denominator and the build or feed date."],
]))
w("")
w("### 8.5 Added file size and build time (all measured)")
w("")
w(md(["Addition", "Raw added", "Gzip added"], [
    ["places.json today (reference)", f"{q6['places_json_raw_mb']} MB", f"{q6['places_json_gzip6_mb']} MB"],
    ["Core three fields in `places.json` (`ts_m`, `ts_calls`, `ts_we`)", f"{ps['core3_ts_m_ts_calls_ts_we']['raw_added_kb']:,.0f} KB", f"{ps['core3_ts_m_ts_calls_ts_we']['gzip6_added_kb']:.0f} KB"],
    ["Two fields only (`ts_m`, `ts_calls`)", f"{ps['minimal_ts_m_and_ts_calls']['raw_added_kb']:,.0f} KB", f"{ps['minimal_ts_m_and_ts_calls']['gzip6_added_kb']:.0f} KB"],
    ["Five fields (core three plus `hub_m`, `hub`)", f"{ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['raw_added_kb']:,.0f} KB", f"{ps['tier1_ts_m_ts_calls_ts_we_hub_m_hub']['gzip6_added_kb']:.0f} KB"],
    ["Six fields (adds `tw_m`)", f"{ps['tier1_plus_tw_m']['raw_added_kb']:,.0f} KB", f"{ps['tier1_plus_tw_m']['gzip6_added_kb']:.0f} KB"],
    ["Nine fields (adds `sju_t`, `sju_b`, `sju_d` for one gateway)", f"{ps['tier1_plus_tw_m_plus_sju_t_sju_b_sju_d']['raw_added_kb']:,.0f} KB", f"{ps['tier1_plus_tw_m_plus_sju_t_sju_b_sju_d']['gzip6_added_kb']:.0f} KB"],
    ["Alternative: core three as typed columns in a separate file", f"{q6['binary_core3_columns']['raw_kb']:,.0f} KB", f"{q6['binary_core3_columns']['gzip6_kb']:.0f} KB"],
    ["Alternative: all nine as typed columns", f"{q6['binary_columns_alternative']['raw_kb']:,.0f} KB", f"{q6['binary_columns_alternative']['gzip6_kb']:.0f} KB"],
    ["`municipalities.json`: 26 new fields x 78", f"{q6['municipalities_json_added']['raw_added_kb']:,.0f} KB", f"{q6['municipalities_json_added']['gzip6_added_kb']:.0f} KB"],
    ["`barrios.geojson`: 4 new fields x 901", f"{q6['barrios_geojson_added']['raw_added_kb']:,.0f} KB", f"{q6['barrios_geojson_added']['gzip6_added_kb']:.0f} KB"],
    ["`transport.json`: `calls_sat`, `calls_sun`, `feed` on 3,847 stops", f"{q6['transport_json_added_for_scheduled_stops']['raw_added_kb']:,.0f} KB", f"{q6['transport_json_added_for_scheduled_stops']['gzip6_added_kb']:.0f} KB"],
    [f"`gateways.json` (new, {q6['gateways_json_estimate']['records']} records)", f"{q6['gateways_json_estimate']['raw_kb']:,.0f} KB", f"{q6['gateways_json_estimate']['gzip6_kb']:.0f} KB"],
]))
w("")
w("The figures come from re-serialising the real file in memory with the real values added (same JSON settings as `build.py`; the re-serialised baseline has exactly the same length in bytes as the published file) and gzip level 6. The values used for the per-area fields are random numbers with one decimal, which is why their gzip size is not trivially small. Load time on a throttled connection was not measured.")
w("")
w("Build time: each figure in the tier table is the measured time of the step on this machine, and timings vary two to three times between runs with machine load. None needs more than a minute, so adding Tiers 1 to 3 to `build.py` and Tier 1 plus Tier 3 to the nightly refresh is practical. The refresh currently never touches `places.json`; either call the access computation from `refresh_network.py` or compute Tier 1 in the browser from the nightly `transport.json` and `operators.json`.")
w("")
w("### 8.6 Which parts need the road graph")
w("")
w(f"- **Tier 2 (`tw_m`, `acc_walk400_pct`):** yes. `roads.bin` is enough for the aggregate; a full OSM walking graph (rebuilt from the extract: a one-off read of {rng('pbf_read_s')} s, then {oc['osm_walk_graph']['build_total_s']} s to build; {oc['osm_walk_graph']['roads_bin_layout_size_mb_estimate']} MB in the `roads.bin` layout if it were shipped) is only needed if individual-place accuracy matters. Do not ship either graph to the browser for this; compute at build time.")
w("- **Tier 3 driving comparator:** yes, same graph, one-way rules obeyed.")
w("- **Tier 1 and the transit scan:** no.")
w("")
w("### 8.7 Labels the app must show")
w("")
for line in [
    "**Schedule-based, not real-time.** Every transit figure comes from published timetables (a typical Wednesday, Saturday or Sunday); no live positions exist. Holidays and calendar exceptions are not modelled.",
    f"**Feed coverage and date.** \"{op_types['municipal']['with feed']} of {op_types['municipal']['with feed'] + op_types['municipal']['none']} municipal systems publish a feed; {n_exp} feeds have expired (list); {op_types['municipal']['none']} publish none; públicos are not included.\" Always show the feed end date next to a stop or area and the build or refresh date.",
    "**Straight line versus walking.** Say which one a number uses. Walking figures read \"estimated walking distance along mapped roads; excludes footpaths, sidewalks, stairs, crossings and barriers.\"",
    "**Estimates and proxies.** `ts_calls` is a frequency proxy, not a headway. Journey times read \"scheduled estimate, weekday 10:00, up to 3 boardings, walking up to 400 m at 4.8 km/h, 3-minute transfer buffer; not door to door.\" Driving times read \"free-flow estimate at planning speeds; no traffic, signals or parking.\"",
    "**What counts as a stop.** \"Current scheduled stop\" versus \"mapped stop (no timetable or expired)\". Show the old measure only with the second label.",
    "**Missing is not zero.** \"No Saturday service in the published data\" is not \"no Saturday service\"; \"no scheduled link in the data\" is not \"no link\".",
    "**Counts are listings.** Places are Overture listings (confidence 0.50 or higher, no places of worship), not businesses, rooms or visitors.",
    "**Small numbers.** Suppress or flag shares for areas with fewer than 10 places.",
]:
    w(f"- {line}")
w("")
w("### 8.8 Fix first (these change the numbers more than any new method)")
w("")
fixes = [
    f"Rebuild the place access fields from the current stops ({b1['flag_changes_default_jayuya']} Jayuya places wrong today) and call that code from the nightly refresh too.",
    "In `parse_gtfs`, store per stop: feed state, Saturday and Sunday calls, first and last weekday departure. This replaces the coordinate matching used in this spike.",
    f"Write untimed calls to the trip files (interpolate between timepoints) and keep stop IDs, so municipal feeds are not understated by up to {N['max_call_share_missing_pct']:.0f}%.",
    f"Fold OpenStreetMap stops within 100 m of scheduled stops, mark cross-operator duplicates, correct the 1 Jayuya stop {N['jayuya_far_km']} km off, and give every pier stop a municipality.",
    "Add port, harbour and cruise-pier features to the stop inventory (OpenStreetMap `harbour`, `landuse=port`, `amenity=ferry_terminal`) and take the FAJ airport from OpenStreetMap until the FAA file is refreshed.",
    f"Renew or replace the {n_exp} expired municipal feeds; a Ponce feed alone would move about {mr['Ponce']['near_expired_only_n']:,} places from \"on paper\" to \"served\" if the service still runs.",
]
for i, line in enumerate(fixes, 1):
    w(f"{i}. {line}")
w("")
w("### 8.9 What I would not claim")
w("")
for line in [
    "That a place is \"accessible by public transport\", \"car-free\" or \"reachable\" for visitors. The data show scheduled stops near a listing, not whether a visitor can use them (luggage, accessibility, safety, fares, language, real timetable adherence).",
    "Anything real-time, or that a timetable is running today; expired feeds mean \"not covered by a published timetable\".",
    "That no stop means no transport: públicos, taxis, ride-hailing, rental cars, tour shuttles and informal ferries are outside the data.",
    "A walking time or a door-to-door journey time. Only distances along mapped roads and stop-to-stop schedule times are available.",
    "Service quality from `trips_weekday` alone. It mixes directions and gives no headway, hours or reliability.",
    f"Comparisons across municipalities as if feeds were equally complete: Ponce's {mr['Ponce']['pct400_current_scheduled']}% reflects a lapsed feed, not an absence of buses.",
    "Visitor numbers, demand, equity or causality. Counts are listings; shares over 78 places show patterns, not causes.",
    "Journey times outside the San Juan metro area. Only ATI, San Juan, Guaynabo and Bayamón stops connect today.",
]:
    w(f"- {line}")
w("")
w("### 8.10 Decisions for FPR")
w("")
for line in [
    "Whether to rename the published \"within 400 m of transit\" measure now (recommended) or keep it as is until Tier 1 is live.",
    f"Whether Tier 1 fields live in `places.json` (+{ps['core3_ts_m_ts_calls_ts_we']['gzip6_added_kb']:.0f} KB gzip) or in a separate typed-column file (+{q6['binary_core3_columns']['gzip6_kb']:.0f} KB gzip, needs the lazy loading planned as Phase 3 item 3).",
    "Which gateways to publish first (only gateways inside the San Juan metro area connect to scheduled transit today) and which departure times.",
    f"Who contacts the {n_exp} operators with expired feeds, and ATI about GTFS-Realtime, untimed calls and stop IDs (a draft exists in `OUTREACH_TRANSIT_DATA.md`).",
    "Review path before anything new goes on a public page: the dictionary page is `noindex` until Compliance has reviewed pages that describe grant-funded data; new access entries should follow the same path. These transit series use no federal grant data.",
]:
    w(f"- {line}")
w("")

# ================================================================================================================================
w("## 9. Scripts, outputs and reproducibility")
w("")
w(f"All files are in this folder. Run `<repo>/venv/Scripts/python.exe run_all.py` to rebuild everything ({round(sum(v['seconds'] for v in timings.values()) / 60, 1) if timings else '?'} minutes in the last run, more when the machine is busy; reading the OpenStreetMap extract alone took {rng('pbf_read_s')} s over {nh} runs). Scripts write only here and read the repository without changing it (`sys.dont_write_bytecode` is set so no `.pyc` is written into it).")
w("")
w(md(["Script", "What it does"], [
    ["`common.py`, `service.py`, `walknet.py`, `csa.py`", "Loaders and shared code: projection, stop sets, feed status, stop locations, walking engine, scan"],
    ["`01_baseline.py`, `01b_stale_check.py`, `01c_bruteforce_check.py`, `07b_location_sensitivity.py`", "Q1: shares by stop set, category, region, municipality, type; stale-field check; brute-force and location-level checks. Outputs `q1_*.json`, `q1_by_municipality*.csv`, `q1_by_region.csv`"],
    ["`02_walk.py`, `02b_osm_walk_ways.py`, `02c_walk_osm_compare.py`, `02d_muni_graph_diff.py`", "Q2: walking distances on `roads.bin`, OSM inventory, full OSM walking graph comparison. Outputs `q2*.json`, `q2_walk_by_municipality.csv`, `q2_sample_ids.npy`"],
    ["`03_gateways.py`, `03b_east_and_osm.py`", "Q3: gateways, ferry routes, Eastern region, land links. Outputs `q3_gateways.json`, `q3b_east_and_osm.json`"],
    ["`04_journey.py`, `04c_check_csa.py`", "Q4: timetable scan, driving estimate, brute-force check. Outputs `q4_journey.json`, `q4c_check.json`, `q4_sju_by_municipality.csv`, `q4_sju_times.npz`"],
    ["`05_problems.py`", "Q5: data problems. Output `q5_problems.json`"],
    ["`06_design_numbers.py`, `07_extra_and_tables.py`, `make_report.py`", "Q6 sizes and classes, extra numbers, tables, this report. Outputs `q6_design_numbers.json`, `q_extra.json`, `tables.md`, `REPORT.md`"],
    ["`run_all.py`, `record_history.py`, `99_privacy_scan.py`, `timings.json`, `timing_history.json`, `logs/`", "Runner, wall-clock time per script and over runs, privacy scan of the outputs, console output"],
]))
w("")
if timings:
    w("Wall-clock time per script on this machine (12 cores, Python 3.12, numpy 2.5, shapely 2.1; the machine was shared, so figures vary): " + ", ".join(f"`{k}` {v['seconds']} s" for k, v in timings.items() if k != "make_report.py") + ".")
    w("")
w("### Limits of this spike")
w("")
for line in [
    "One snapshot (places and stops of 2026-10-02) and one day type per scan; no validation against real trips or counts.",
    "Walking and driving are estimates from OpenStreetMap-based graphs; no field check.",
    "SJU was located by the FAA reference point, not the terminal door.",
    "\"Eastern region\" is read as the PRTC region Porta del Mar; a different definition of the east would change the Q3 counts.",
    "The 1,000-place walking sample is random, but the island run covers every place, so the island figures do not depend on it.",
    "Not tested: the app's browser code; I did not open the site.",
]:
    w(f"- {line}")
w("")
w("### Process notes")
w("")
w("- Three files that were in this folder at first were not created by this analysis and were not used: `ati_gtfs.zip`, `ati_open.html`, `ati_urbana.html` (they appeared at 17:10 to 17:11 on 2026-10-05, after the folder was created, from some other process, and were gone again by the end of the work). The brief says no network use; the GTFS zip (2,234,433 bytes) has the same size as the repository's cached ATI feed.")
w("- While this analysis ran, other files in the repository changed: a check at the end found 42 files modified since 17:00 (the Spanish-interface work: `i18n.py`, `i18n_src/`, `site/index.html`, `site/js/app.js`, `README.md`, `docs/` and others) and a git commit had appeared. None is in `site/data`, `cache` or `__pycache__`. They come from another process; this analysis only read `site/data/*`, the cached OpenStreetMap extract and the repository's `roads.py` and `municipalities.py` (imported with bytecode writing off).")
w("- A privacy scan (`99_privacy_scan.py`) compared every text output in this folder with the business names, addresses and websites in `places.json` and with e-mail patterns. No website or e-mail matched; the only name and address matches are generic phrases and public place names (for example the neighbourhood names Old San Juan and Río Piedras, the Ceiba ferry terminal and the phrase \"rest stop\"). `q3_gateways.json` keeps names only for airports, ferry terminals and stations.")
w("- One `git status --short` was run early, to check that no stray files had been written. It is read-only in effect but can refresh the index's timestamps, so strictly it touched git state. It showed one untracked file (`site/js/i18n.js`) that is not from this analysis. No other git command was run, and these scripts wrote no file, cache or git state inside the repository.")

report = "\n".join(out) + "\n"
(HERE / "REPORT.md").write_text(report, encoding="utf-8")
write_json("report_numbers.json", {k: v for k, v in N.items()})
print("wrote REPORT.md", len(report), "characters,", report.count("\n"), "lines")
