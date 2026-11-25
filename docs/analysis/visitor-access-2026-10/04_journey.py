"""Q4: earliest-arrival prototype from SJU to every stop and every default-basis place by scheduled transit (weekday 10:00),
plus a free-flow driving-time estimate over the road graph for comparison.
"""
from csa import *
from service import *
import csv

d = Data()
T = d.transport
dm = d.default
res = {}
t_all = timer()

expired_ops = {o for o, s in d.op_status.items() if s == "expired"}
res["expired_operators_excluded"] = sorted(expired_ops)

# ---- timetables ----------------------------------------------------------------------------------------------------
t = timer()
trips_wk = jload("trips.json")["trips"]
tt_cur = Timetable(trips_wk, expired_ops)
tt_all = Timetable(trips_wk)
res["timetable_weekday_current_feeds"] = {"trips": tt_cur.n_trips, "connections": len(tt_cur.conns), "stops_with_calls": tt_cur.n, "bad_connections_negative_duration": tt_cur.bad, "build_s": round(t(), 1)}
res["timetable_weekday_all_feeds"] = {"trips": tt_all.n_trips, "connections": len(tt_all.conns), "stops_with_calls": tt_all.n}
tt_sa = Timetable(jload("trips_sa.json")["trips"], expired_ops)
tt_su = Timetable(jload("trips_su.json")["trips"], expired_ops)
res["timetable_sat_current"] = {"trips": tt_sa.n_trips, "connections": len(tt_sa.conns), "stops": tt_sa.n}
res["timetable_sun_current"] = {"trips": tt_su.n_trips, "connections": len(tt_su.conns), "stops": tt_su.n}

# ---- origin: SJU ------------------------------------------------------------------------------------------------------
sju = next(f for f in T if f.get("code") == "SJU")
sx, sy = to_xy(sju["lng"], sju["lat"])
ORIGIN_RADIUS = 500.0

def origin_access(tt, t0):
    dd = np.hypot(tt.x - sx, tt.y - sy)
    idx = np.nonzero(dd <= ORIGIN_RADIUS)[0]
    return {int(i): t0 + float(dd[i]) / WALK_MS for i in idx}, [round(float(dd[i])) for i in idx]

acc, acc_d = origin_access(tt_cur, 10 * 3600)
res["origin_sju"] = {"reference_point": "FAA airport reference point of SJU (transport.json, faa:SJU)", "origin_radius_m": ORIGIN_RADIUS, "stops_used": len(acc), "walk_distances_m": sorted(acc_d)}

# ---- places: candidate stops within 400 m ---------------------------------------------------------------------------------
def place_links(tt):
    tree = STRtree(points(tt.x, tt.y))
    i, j = tree.query(points(d.p_x, d.p_y), predicate="dwithin", distance=WALK_LINK_M)
    dist = np.hypot(d.p_x[i] - tt.x[j], d.p_y[i] - tt.y[j])
    order = np.argsort(i, kind="stable")
    return i[order], j[order], dist[order]

def place_times(tt, veh_best, veh_round, links):
    pi, sj, dist = links
    arr = np.full(d.n_places, np.inf)
    rnd = np.zeros(d.n_places, dtype=int)
    vb = np.array(veh_best, dtype=float)
    vb[vb >= INF] = np.inf
    cand = vb[sj] + dist / WALK_MS
    best = np.full(d.n_places, np.inf)
    np.minimum.at(best, pi, cand)
    # round of the best candidate
    vr = np.array(veh_round)
    sel = np.isclose(cand, best[pi]) & np.isfinite(cand)
    rnd[pi[sel]] = vr[sj[sel]]
    return best, rnd

links_cur = place_links(tt_cur)
links_all = place_links(tt_all)
res["places_with_a_stop_within_400m_in_timetable_current"] = int((np.bincount(links_cur[0], minlength=d.n_places) > 0)[dm].sum())

def summarize(arr, t0, mask=None, label=""):
    m = dm if mask is None else (dm & mask)
    mins = (arr - t0) / 60.0
    n = int(m.sum())
    out = {"n": n}
    for T_ in (60, 90, 120):
        out[f"within_{T_}"] = int((mins[m] <= T_).sum())
        out[f"pct_within_{T_}"] = pct(int((mins[m] <= T_).sum()), n)
    fin = mins[m][np.isfinite(mins[m])]
    out["reachable_any_within_4h"] = int(len(fin))
    out["median_minutes_of_reachable"] = round(float(np.median(fin)), 0) if len(fin) else None
    return out

def run(tt, links, t0, label):
    acc, _ = origin_access(tt, t0)
    t = timer()
    vb, vr, av = tt.scan(acc, t0)
    secs = t()
    arr, rnd = place_times(tt, vb, vr, links)
    return {"vb": vb, "vr": vr, "avail": av, "arr": arr, "rnd": rnd, "scan_s": secs, "n_acc": len(acc)}

main = run(tt_cur, links_cur, 10 * 3600, "weekday current 10:00")
t0 = 10 * 3600
res["scan_seconds_one_origin"] = round(main["scan_s"], 2)
res["main_weekday_10"] = {"all": summarize(main["arr"], t0)}
res["main_weekday_10"]["by_category"] = {c: summarize(main["arr"], t0, d.p_cat == c) for c in CATS}
res["main_weekday_10"]["by_region"] = {r: summarize(main["arr"], t0, d.p_region == r) for r in sorted(set(d.p_region) - {""})}
# boardings
mins = (main["arr"] - t0) / 60
for K in (1, 2, 3):
    res["main_weekday_10"][f"within_120_with_{K}_boardings_exactly"] = int(((mins <= 120) & (main["rnd"] == K) & dm).sum())
res["main_weekday_10"]["stops_reached_by_vehicle_any_round"] = int(sum(1 for v in main["vb"] if v < INF))
res["main_weekday_10"]["stops_reached_within_60_90_120"] = {str(T_): int(sum(1 for v in main["vb"] if v < INF and (v - t0) / 60 <= T_)) for T_ in (60, 90, 120)}
res["main_weekday_10"]["stops_reached_by_round"] = {str(K): int(sum(1 for v, r_ in zip(main["vb"], main["vr"]) if v < INF and r_ == K)) for K in (1, 2, 3)}
# municipalities
muni_rows = []
for m in sorted(set(d.p_muni)):
    s = summarize(main["arr"], t0, d.p_muni == m)
    muni_rows.append({"municipality": m, "region": d.region_of.get(m, ""), "places": s["n"], "pct_within_60": s["pct_within_60"], "pct_within_90": s["pct_within_90"], "pct_within_120": s["pct_within_120"],
                      "median_minutes_reachable": s["median_minutes_of_reachable"]})
with open(HERE / "q4_sju_by_municipality.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(muni_rows[0].keys()))
    w.writeheader(); w.writerows(muni_rows)
res["municipalities_with_any_place_within_120"] = int(sum(1 for r in muni_rows if (r["pct_within_120"] or 0) > 0))
res["municipalities_with_ge50pct_within_120"] = int(sum(1 for r in muni_rows if (r["pct_within_120"] or 0) >= 50))

# sensitivity: expired feeds included, other departure times, weekend days
sens = {}
r_ = run(tt_all, links_all, 10 * 3600, "weekday all feeds 10:00")
sens["weekday_10_including_expired_feeds"] = summarize(r_["arr"], 10 * 3600)
for hh in (7, 14, 18):
    r_ = run(tt_cur, links_cur, hh * 3600, f"weekday {hh}")
    sens[f"weekday_{hh:02d}_current"] = summarize(r_["arr"], hh * 3600)
links_sa = place_links(tt_sa)
links_su = place_links(tt_su)
r_ = run(tt_sa, links_sa, 10 * 3600, "sat")
sens["saturday_10_current"] = summarize(r_["arr"], 10 * 3600)
r_ = run(tt_su, links_su, 10 * 3600, "sun")
sens["sunday_10_current"] = summarize(r_["arr"], 10 * 3600)
# no transfer buffer / 2 boardings only
acc, _ = origin_access(tt_cur, 10 * 3600)
vb, vr, av = tt_cur.scan(acc, 10 * 3600, max_boardings=2)
arr, _ = place_times(tt_cur, vb, vr, links_cur)
sens["weekday_10_max2_boardings"] = summarize(arr, 10 * 3600)
vb, vr, av = tt_cur.scan(acc, 10 * 3600, max_boardings=1)
arr, _ = place_times(tt_cur, vb, vr, links_cur)
sens["weekday_10_max1_boarding"] = summarize(arr, 10 * 3600)
vb, vr, av = tt_cur.scan(acc, 10 * 3600, max_boardings=3, buffer_s=0)
arr, _ = place_times(tt_cur, vb, vr, links_cur)
sens["weekday_10_buffer_0s"] = summarize(arr, 10 * 3600)
res["sensitivity"] = sens

# ---- other gateways as origins -----------------------------------------------------------------------------------------------------
def origin_from_point(tt, px, py, radius, t0):
    dd = np.hypot(tt.x - px, tt.y - py)
    idx = np.nonzero(dd <= radius)[0]
    return {int(i): t0 + float(dd[i]) / WALK_MS for i in idx}, [round(float(dd[i])) for i in idx]
others = {}
for key, pred in (("old_san_juan_cruise_pier_osm_mapped", lambda f: f["source"] == "osm_transport" and f["kind"] == "ferry_terminal" and "cruise" in (f["name"] or "").lower()),
                  ("ceiba_ferry_terminal_ati", lambda f: f["source"] == "ati_gtfs" and f["kind"] == "ferry_terminal" and "ceiba" in (f["name"] or "").lower()),
                  ("terminal_covadonga_old_san_juan", lambda f: f["source"] == "ati_gtfs" and f["kind"] == "bus_station" and "covadonga" in (f["name"] or "").lower())):
    f = next(f for f in T if pred(f))
    ox, oy = to_xy(f["lng"], f["lat"])
    acc_o, dist_o = origin_from_point(tt_cur, ox, oy, 500.0, 10 * 3600)
    vb_o, vr_o, av_o = tt_cur.scan(acc_o, 10 * 3600)
    arr_o, _ = place_times(tt_cur, vb_o, vr_o, links_cur)
    sm = summarize(arr_o, 10 * 3600)
    sm["origin_stops_within_500m"] = len(acc_o)
    reach = dm & np.isfinite(arr_o)
    sm["reachable_within_4h_by_municipality"] = dict(Counter(d.p_muni[reach]).most_common(6))
    sm["by_region_pct_within_120"] = {r: summarize(arr_o, 10 * 3600, d.p_region == r)["pct_within_120"] for r in sorted(set(d.p_region) - {""})}
    others[key] = sm
res["other_gateway_origins_weekday_10"] = others

# ---- plausibility: well-known pairs (public facilities) ------------------------------------------------------------------
def node_of(name_part, kinds=("bus_station", "rail_station", "ferry_terminal")):
    for i, f in enumerate(T):
        if f["source"] in SCHEDULED_SOURCES and f["kind"] in kinds and name_part.lower() in (f["name"] or "").lower():
            k = tt_cur.node.get((f["lng"], f["lat"]))
            if k is not None:
                return k, f["name"]
    return None, None

pairs = {}
for key, part in (("Terminal Covadonga (Old San Juan)", "Covadonga"), ("Estación Bayamón (Tren Urbano)", "Estación Bayamón"), ("Terminal de Cataño (bus)", "Terminal de Cataño"),
                  ("Terminal de Lancha Cataño (ferry)", "Terminal de Lancha Cataño"), ("Terminal de Lancha San Juan (ferry)", "Terminal de Lancha San Juan"),
                  ("Estación Río Piedras", "Rio Piedras"), ("Terminal de Carolina", "Terminal de Carolina"), ("Terminal Transporte Publico de Caguas", "Transporte Publico de Caguas"),
                  ("Terminal de Lanchas de Ceiba (ferry)", "Terminal de Lanchas de Ceiba"), ("Terminal de Lanchas Vieques (Isabel II)", "Isabel II"), ("Terminal de Lanchas Culebra", "Lanchas Culebra"),
                  ("Terminal Multimodal Bayamón", "Multimodal")):
    k, nm = node_of(part)
    if k is None:
        pairs[key] = "not in current-feed weekday timetable"
    else:
        v = min(main["vb"][k], main["avail"][k])
        pairs[key] = {"minutes_from_10:00": None if v >= INF else round((v - t0) / 60, 0), "boardings_if_by_vehicle": None if main["vb"][k] >= INF else main["vr"][k],
                      "arrives_by_vehicle_min": None if main["vb"][k] >= INF else round((main["vb"][k] - t0) / 60, 0)}
res["pair_checks"] = pairs

# ---- driving (free-flow, planning speeds) ---------------------------------------------------------------------------------
from walknet import from_roads_bin, WalkNet
import roads as roads_mod

t = timer()
net = from_roads_bin(exclude_classes=(), keep_all=True)     # all classes
R = net.R
SPD = np.array(roads_mod.SPEED_MS)
length = net.len                       # projected meters of every edge (all classes)
n_nodes = R.n_nodes
eu, ev = R.eu, R.ev
ow = R.oneway
# main connected component of the road graph (islands and isolated airfield pieces are not reachable by road from SJU)
parent = np.arange(n_nodes)
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
for u_, v_ in zip(eu.tolist(), ev.tolist()):
    ru, rv = find(u_), find(v_)
    if ru != rv:
        parent[ru] = rv
roots = np.array([find(i) for i in range(n_nodes)])
main_root = Counter(roots.tolist()).most_common(1)[0][0]
main_nodes = roots == main_root
main_edge = main_nodes[eu]
res["road_graph_components"] = {"nodes_in_main_component_pct": pct(int(main_nodes.sum()), n_nodes), "edges_in_main_component_pct": pct(int(main_edge.sum()), len(eu))}
cost = length / SPD[R.cls]
src = np.concatenate([eu, ev[~ow]])
dst = np.concatenate([ev, eu[~ow]])
w = np.concatenate([cost, cost[~ow]])
order = np.argsort(src, kind="stable")
src, dst, w = src[order], dst[order], w[order]
indptr = np.searchsorted(src, np.arange(n_nodes + 1)).tolist()
nbr, wl = dst.tolist(), w.tolist()
# origin: nearest edge of the main component within 3 km
ids_main = np.nonzero(main_edge)[0]
snap_main = WalkNet(eu[ids_main], ev[ids_main], net.geoms[ids_main], n_nodes)
e0, a0, c0 = snap_main.snap(np.array([sx]), np.array([sy]), 3000.0)
res["drive_origin_snap_connector_m"] = round(float(c0[0]), 0)
e = int(ids_main[int(e0[0])])
res["drive_origin_edge_class"] = roads_mod.CLASSES[R.cls[e]]
L0 = float(length[e])
a0 = float(a0[0])
dist = {}
heap = []
u, v = int(eu[e]), int(ev[e])
dist[v] = (L0 - a0) / SPD[R.cls[e]] + float(c0[0]) / (20 / 3.6)
heapq.heappush(heap, (dist[v], v))
if not ow[e]:
    dist[u] = a0 / SPD[R.cls[e]] + float(c0[0]) / (20 / 3.6)
    heapq.heappush(heap, (dist[u], u))
done = set()
while heap:
    dd, n = heapq.heappop(heap)
    if n in done:
        continue
    done.add(n)
    for j in range(indptr[n], indptr[n + 1]):
        m = nbr[j]
        nd = dd + wl[j]
        if nd < dist.get(m, 1e18):
            dist[m] = nd
            heapq.heappush(heap, (nd, m))
res["drive_dijkstra_s"] = round(t(), 1)
res["drive_nodes_reached"] = len(done)
res["drive_nodes_total"] = int(n_nodes)
Tn = np.full(n_nodes, np.inf)
for k, v_ in dist.items():
    Tn[k] = v_
# places: nearest main-component edge that is not a motorway or motorway link, within 300 m
ids_pl = np.nonzero(main_edge & ~np.isin(R.cls, [0, 1]))[0]
snap_pl = WalkNet(eu[ids_pl], ev[ids_pl], net.geoms[ids_pl], n_nodes)
pe, pa, pc = snap_pl.snap(d.p_x, d.p_y, 300.0)
drive = np.full(d.n_places, np.inf)
ok = pe >= 0
re_ = ids_pl[pe[ok]]
a_ = pa[ok]
L_ = length[re_]
spd_ = SPD[R.cls[re_]]
a_ = np.clip(a_, 0, L_)
tu = Tn[eu[re_]] + a_ / spd_
tv = np.where(~ow[re_], Tn[ev[re_]] + (L_ - a_) / spd_, np.inf)
tt_place = np.minimum(tu, tv) + pc[ok] / (20 / 3.6)       # connector at 20 km/h
drive[ok] = tt_place
mins_d = drive / 60.0
res["places_default_with_no_main_road_within_300m"] = int((dm & ~(pe >= 0)).sum()) if False else int((dm & ~np.isin(np.arange(d.n_places), np.nonzero(ok)[0])).sum())
def dsum(mask=None):
    m = dm if mask is None else (dm & mask)
    n = int(m.sum())
    o = {"n": n}
    for T_ in (60, 90, 120):
        o[f"pct_within_{T_}"] = pct(int((mins_d[m] <= T_).sum()), n)
    o["pct_no_road_path_or_no_road_within_300m"] = pct(int((~np.isfinite(mins_d[m])).sum()), n)
    fin = mins_d[m][np.isfinite(mins_d[m])]
    o["median_minutes"] = round(float(np.median(fin)), 0) if len(fin) else None
    o["p90_minutes"] = round(float(np.percentile(fin, 90)), 0) if len(fin) else None
    return o
res["drive_all"] = dsum()
res["drive_by_category"] = {c: dsum(d.p_cat == c) for c in CATS}
res["drive_by_region"] = {r: dsum(d.p_region == r) for r in sorted(set(d.p_region) - {""})}
res["drive_assumptions"] = "planning speeds by road class from roads.py SPEED_KMH (motorway 90, trunk 75, primary 55, secondary 48, tertiary 40, residential 25 km/h), one-way rules obeyed, no traffic, no signals, no parking, connector to the road at 20 km/h; islands without a road link are unreachable"
# transit vs drive for places reachable by both within 120 min of transit
both = dm & np.isfinite(mins) & (mins <= 120) & np.isfinite(mins_d) & (mins_d > 0)
ratio = mins[both] / mins_d[both]
res["transit_over_drive_time_ratio_places_reachable_by_transit_le_120"] = {"n": int(both.sum()), "median": round(float(np.median(ratio)), 1), "p25": round(float(np.percentile(ratio, 25)), 1), "p75": round(float(np.percentile(ratio, 75)), 1)}
res["median_drive_minutes_of_those_places"] = round(float(np.median(mins_d[both])), 0)
res["median_transit_minutes_of_those_places"] = round(float(np.median(mins[both])), 0)
# places within 60 min by car but not within 120 by transit
res["places_le60_drive_but_not_le120_transit"] = int((dm & (mins_d <= 60) & ~(mins <= 120)).sum())
res["share_of_le60_drive_places_not_le120_transit_pct"] = pct(int((dm & (mins_d <= 60) & ~(mins <= 120)).sum()), int((dm & (mins_d <= 60)).sum()))
both60 = dm & (mins_d <= 60)
res["of_places_within_60_min_drive_share_also_within_60_min_transit_pct"] = pct(int((both60 & (mins <= 60)).sum()), int(both60.sum()))
res["of_places_within_60_min_drive_share_also_within_120_min_transit_pct"] = pct(int((both60 & (mins <= 120)).sum()), int(both60.sum()))
res["by_region_of_le60_drive_places_share_le120_transit_pct"] = {r: pct(int((both60 & (d.p_region == r) & (mins <= 120)).sum()), int((both60 & (d.p_region == r)).sum())) for r in sorted(set(d.p_region) - {""})}
np.savez_compressed(HERE / "q4_sju_times.npz", transit_min=mins.astype(np.float32), drive_min=mins_d.astype(np.float32), rounds=main["rnd"].astype(np.int8), default=dm)
res["total_s"] = round(t_all(), 1)
write_json("q4_journey.json", res)
print(json.dumps(res, indent=1, default=str)[:15000])
