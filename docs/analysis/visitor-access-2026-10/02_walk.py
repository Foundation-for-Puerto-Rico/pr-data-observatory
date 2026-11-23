"""Q2: straight line versus walking distance on the repository's road graph (roads.bin, loaded with roads.Roads).

1. Sample of default-basis places within 800 m straight line of a scheduled stop: place-side bounded Dijkstra (1,000 m cut-off).
2. Full run from every scheduled stop (stop-side bounded Dijkstra) to every place: gives the island figures and the run time.
3. Consistency checks: place-side vs stop-side agree; snapping vs roads.Roads.snap; sanity check against roads.Roads.route.

Walking graph = roads.bin without motorways and motorway links, undirected (pedestrians ignore one-way signs).
roads.bin has no footways, paths, steps, pedestrian streets, tracks or service roads, so every distance here is a road-only estimate.
"""
from service import *
from walknet import *
import csv

BOUND = 1000.0
SNAP_M = 150.0
rng = np.random.default_rng(20261005)

t_all = timer()
d = Data()
res = {}

# ---- graph ---------------------------------------------------------------------------------------------------------
t = timer()
net = from_roads_bin()
res["graph_build_s"] = round(t(), 1)
_t = timer()
import roads as _roads_probe
_roads_probe.Roads(DATA / "roads.bin")
res["roads_py_load_s"] = round(_t(), 1)
R = net.R
res["graph"] = {
    "roads_bin_nodes": int(R.n_nodes), "roads_bin_edges": int(R.n_edges),
    "walk_edges_used": int(net.n_edges), "walk_km_used": round(float(net.len.sum()) / 1000, 0),
}
import roads as roads_mod   # already on sys.path through walknet
cls_names = roads_mod.CLASSES
allkm = np.array([c[-1] for c in R.cum])
res["graph"]["km_by_class_in_file"] = {cls_names[i]: round(float(allkm[R.cls == i].sum()) / 1000, 1) for i in range(len(cls_names))}
res["graph"]["classes_present"] = [cls_names[i] for i in range(len(cls_names)) if (R.cls == i).any()]
res["graph"]["footway_path_pedestrian_steps_cycleway_track_service_in_file"] = False
res["graph"]["oneway_edges_pct"] = round(100 * float(R.oneway.mean()), 1)
print("graph built", res["graph_build_s"], "s", res["graph"]["walk_edges_used"], "edges")

# ---- stops and places ----------------------------------------------------------------------------------------------
sidx = np.nonzero(d.t_sched)[0]                      # scheduled stops (all feeds)
sx, sy = d.t_x[sidx], d.t_y[sidx]
s_cur = d.t_current[sidx]
t = timer()
s_edge, s_along, s_conn = net.snap(sx, sy, SNAP_M)
res["stop_snap_s"] = round(t(), 2)
res["stops"] = {"scheduled": int(len(sidx)), "snapped_within_150m": int((s_edge >= 0).sum()),
                "not_snapped": int((s_edge < 0).sum()),
                "median_connector_m": float(np.median(s_conn[s_edge >= 0])),
                "p90_connector_m": float(np.percentile(s_conn[s_edge >= 0], 90))}
# 300 m radius for context
e300, _, c300 = net.snap(sx, sy, 300.0)
res["stops"]["not_snapped_within_300m"] = int((e300 < 0).sum())

t = timer()
p_edge, p_along, p_conn = net.snap(d.p_x, d.p_y, SNAP_M)
res["place_snap_s"] = round(t(), 2)
dm = d.default
res["places"] = {"all": int(d.n_places), "default": int(dm.sum()),
                 "default_snapped_within_150m": int(((p_edge >= 0) & dm).sum()),
                 "default_not_snapped_150m": int(((p_edge < 0) & dm).sum()),
                 "default_median_connector_m": float(np.median(p_conn[(p_edge >= 0) & dm])),
                 "default_p90_connector_m": float(np.percentile(p_conn[(p_edge >= 0) & dm], 90))}
e300, _, _ = net.snap(d.p_x[dm], d.p_y[dm], 300.0)
res["places"]["default_not_snapped_300m"] = int((e300 < 0).sum())
print("snapped", res["place_snap_s"], "s")

# straight-line nearest scheduled stop (all feeds / current) for every place
sl_all, nn_all = nearest_dist(d.p_x, d.p_y, sx, sy)
cur_ids = np.nonzero(s_cur)[0]
sl_cur, nn_cur = nearest_dist(d.p_x, d.p_y, sx[cur_ids], sy[cur_ids])
nn_cur = cur_ids[nn_cur]

# ---- 1. sample (place-side) --------------------------------------------------------------------------------------
t = timer()
node_reg_s, edge_reg_s = net.registry(s_edge, s_along, s_conn)                  # stops registry (ids = position in sidx)
res["stop_registry_s"] = round(t(), 2)
cand = np.nonzero(dm & (sl_all <= 800))[0]
res["sample_pool_default_within_800m_scheduled"] = int(len(cand))
N = 1000
sample = np.sort(rng.choice(cand, size=N, replace=False))
np.save(HERE / "q2_sample_ids.npy", sample)
rows = []
t = timer()
settled_counts = []
for pi in sample:
    r = {"place": int(pi), "sl_all": float(sl_all[pi]), "sl_cur": float(sl_cur[pi]), "snapped": bool(p_edge[pi] >= 0), "conn": float(p_conn[pi]) if p_edge[pi] >= 0 else None}
    if p_edge[pi] >= 0:
        best, ns = net.search(int(p_edge[pi]), float(p_along[pi]), float(p_conn[pi]), BOUND, node_reg_s, edge_reg_s, want_nodes=True)
        settled_counts.append(ns)
        r["net_all"] = min(best.values()) if best else None
        cb = [v for k, v in best.items() if s_cur[k]]
        r["net_cur"] = min(cb) if cb else None
        # network distance to the straight-line nearest stop (same stop)
        r["net_to_sl_nearest"] = best.get(int(nn_all[pi]))
        r["n_stops_found"] = len(best)
    rows.append(r)
res["sample_search_s_per_place_ms"] = round(1000 * t() / N, 1)
res["sample_settled_nodes_median"] = float(np.median(settled_counts))
res["sample_settled_nodes_p90"] = float(np.percentile(settled_counts, 90))

def ratio_stats(vals):
    v = np.array(vals)
    return {"n": int(len(v)), "median": round(float(np.median(v)), 2), "p25": round(float(np.percentile(v, 25)), 2), "p75": round(float(np.percentile(v, 75)), 2),
            "p90": round(float(np.percentile(v, 90)), 2), "p95": round(float(np.percentile(v, 95)), 2), "mean": round(float(v.mean()), 2)}

snapped_rows = [r for r in rows if r["snapped"]]
found = [r for r in snapped_rows if r["net_all"] is not None]
S = {"sample_n": N, "snapped": len(snapped_rows), "not_snapped_150m": N - len(snapped_rows), "found_within_1000m": len(found),
     "not_found_within_1000m_but_snapped": len(snapped_rows) - len(found)}
S["ratio_net_best_over_sl_nearest"] = ratio_stats([r["net_all"] / max(r["sl_all"], 1.0) for r in found])
f2 = [r for r in found if r["net_to_sl_nearest"] is not None]
S["detour_factor_to_same_stop"] = ratio_stats([r["net_to_sl_nearest"] / max(r["sl_all"], 1.0) for r in f2])
S["extra_metres_net_minus_sl_median"] = round(float(np.median([r["net_all"] - r["sl_all"] for r in found])), 1)
S["extra_metres_p90"] = round(float(np.percentile([r["net_all"] - r["sl_all"] for r in found], 90)), 1)
S["share_ratio_gt_1_5"] = pct(sum(1 for r in found if r["net_all"] / max(r["sl_all"], 1.0) > 1.5), len(found))
S["share_ratio_gt_2"] = pct(sum(1 for r in found if r["net_all"] / max(r["sl_all"], 1.0) > 2.0), len(found))
# by straight-line band
bands = [(0, 200), (200, 400), (400, 600), (600, 800)]
S["by_sl_band"] = {}
for lo, hi in bands:
    sel = [r for r in found if lo <= r["sl_all"] < hi]
    if sel:
        S["by_sl_band"][f"{lo}-{hi}"] = {"n": len(sel), "median_ratio": round(float(np.median([r["net_all"] / max(r["sl_all"], 1) for r in sel])), 2),
                                         "p90_ratio": round(float(np.percentile([r["net_all"] / max(r["sl_all"], 1) for r in sel], 90)), 2),
                                         "median_net_m": round(float(np.median([r["net_all"] for r in sel])), 0)}
# flips across 400 m (all scheduled stops)
sl400 = [r for r in rows if r["sl_all"] <= 400]
S["places_sl_le_400"] = len(sl400)
S["sl_le_400_and_net_gt_400_or_not_found"] = sum(1 for r in sl400 if (not r["snapped"]) or r["net_all"] is None or r["net_all"] > 400)
S["sl_le_400_and_net_gt_400_snapped_only"] = sum(1 for r in sl400 if r["snapped"] and (r["net_all"] is None or r["net_all"] > 400))
S["sl_le_400_not_snapped"] = sum(1 for r in sl400 if not r["snapped"])
S["flip_share_of_sl_le_400_pct"] = pct(S["sl_le_400_and_net_gt_400_snapped_only"], sum(1 for r in sl400 if r["snapped"]))
S["sample_share_within_400_sl_pct"] = pct(len(sl400), N)
S["sample_share_within_400_net_pct"] = pct(sum(1 for r in snapped_rows if r["net_all"] is not None and r["net_all"] <= 400), N)
S["sample_share_within_400_net_pct_of_snapped"] = pct(sum(1 for r in snapped_rows if r["net_all"] is not None and r["net_all"] <= 400), len(snapped_rows))
# 400 < sl <= 800 places that stay beyond 400 (as expected) and any that fall under 400 (impossible by geometry)
S["sl_gt_400_and_net_le_400"] = sum(1 for r in rows if r["sl_all"] > 400 and r["snapped"] and r["net_all"] is not None and r["net_all"] <= 400)
# at 800 m
sl800 = rows
S["sl_le_800_and_net_gt_800_or_not_found_snapped"] = sum(1 for r in rows if r["snapped"] and (r["net_all"] is None or r["net_all"] > 800))
S["share_sl_le_800_that_have_net_le_800_pct_of_snapped"] = pct(sum(1 for r in snapped_rows if r["net_all"] is not None and r["net_all"] <= 800), len(snapped_rows))
# current-only version
cur_pool = [r for r in rows if r["sl_cur"] <= 800]
S["current_only_sample_n"] = len(cur_pool)
S["current_only_sl_le_400"] = sum(1 for r in cur_pool if r["sl_cur"] <= 400)
S["current_only_sl_le_400_and_net_gt_400_snapped"] = sum(1 for r in cur_pool if r["sl_cur"] <= 400 and r["snapped"] and (r["net_cur"] is None or r["net_cur"] > 400))
S["current_only_ratio"] = ratio_stats([r["net_cur"] / max(r["sl_cur"], 1.0) for r in cur_pool if r["snapped"] and r["net_cur"] is not None]) if cur_pool else None
res["sample"] = S
print("sample done", round(t(), 1), "s")

# ---- 2. full run (stop-side) --------------------------------------------------------------------------------------
t = timer()
node_reg_p, edge_reg_p = net.registry(p_edge, p_along, p_conn)                  # places registry (ids = place index)
res["place_registry_s"] = round(t(), 2)
best_all = np.full(d.n_places, np.inf)
best_cur = np.full(d.n_places, np.inf)
t = timer()
settled_tot = 0
searched = 0
for k in range(len(sidx)):
    if s_edge[k] < 0:
        continue
    best, ns = net.search(int(s_edge[k]), float(s_along[k]), float(s_conn[k]), BOUND, node_reg_p, edge_reg_p, want_nodes=True)
    settled_tot += ns
    searched += 1
    iscur = bool(s_cur[k])
    for pid, dd in best.items():
        if dd < best_all[pid]:
            best_all[pid] = dd
        if iscur and dd < best_cur[pid]:
            best_cur[pid] = dd
res["full_run_s"] = round(t(), 1)
res["full_run_searches"] = searched
res["full_run_per_stop_ms"] = round(1000 * res["full_run_s"] / searched, 1)
res["full_run_settled_nodes_total"] = settled_tot
res["full_run_settled_nodes_per_stop_mean"] = round(settled_tot / searched, 0)
print("full run", res["full_run_s"], "s")

# consistency: sample (place-side) vs full run (stop-side)
mism = 0
checked = 0
maxdiff = 0.0
for r in rows:
    if r["snapped"]:
        a = r["net_all"] if r["net_all"] is not None else np.inf
        b = best_all[r["place"]]
        checked += 1
        if np.isinf(a) and np.isinf(b):
            continue
        dd = abs(a - b) if not (np.isinf(a) or np.isinf(b)) else np.inf
        maxdiff = max(maxdiff, dd) if np.isfinite(dd) else maxdiff
        if not np.isfinite(dd) or dd > 0.5:
            mism += 1
res["consistency_place_side_vs_stop_side"] = {"checked": checked, "mismatches_gt_0.5m": mism, "max_abs_diff_m_where_both_found": round(maxdiff, 3)}

# island figures on the default basis
def share_block(mask, sl, net_d):
    n = int(mask.sum())
    out = {"n": n}
    for thr in (400, 800):
        sl_n = int((sl[mask] <= thr).sum())
        net_n = int((net_d[mask] <= thr).sum())
        both = int(((sl[mask] <= thr) & (net_d[mask] <= thr)).sum())
        out[f"sl_{thr}_n"] = sl_n
        out[f"net_{thr}_n"] = net_n
        out[f"sl_{thr}_pct"] = pct(sl_n, n)
        out[f"net_{thr}_pct"] = pct(net_n, n)
        out[f"lost_{thr}_n"] = sl_n - both
        out[f"lost_{thr}_pct_of_sl"] = pct(sl_n - both, sl_n)
    return out
# the 1,000 m cut-off means "net_d <= 800" is exact; places unsnapped (no road within 150 m) count as not within
res["full_island"] = {
    "all_scheduled": share_block(dm, sl_all, best_all),
    "current_scheduled": share_block(dm, sl_cur, best_cur),
}
res["full_by_category"] = {c: {"all_scheduled": share_block(dm & (d.p_cat == c), sl_all, best_all), "current_scheduled": share_block(dm & (d.p_cat == c), sl_cur, best_cur)} for c in CATS}
# unsnapped contribution to the loss
uns = dm & (p_edge < 0)
res["full_island"]["current_scheduled"]["lost_400_of_which_unsnapped_n"] = int((uns & (sl_cur <= 400)).sum())
res["full_island"]["all_scheduled"]["lost_400_of_which_unsnapped_n"] = int((uns & (sl_all <= 400)).sum())
# ratio over all default places with both defined and sl<=800 (full-run version of the sample statistic)
sel = dm & (sl_all <= 800) & np.isfinite(best_all)
rr = best_all[sel] / np.maximum(sl_all[sel], 1.0)
res["full_ratio_all_default_sl_le_800"] = {"n": int(sel.sum()), "median": round(float(np.median(rr)), 2), "p90": round(float(np.percentile(rr, 90)), 2), "p95": round(float(np.percentile(rr, 95)), 2)}
sel = dm & (sl_cur <= 800) & np.isfinite(best_cur)
rr = best_cur[sel] / np.maximum(sl_cur[sel], 1.0)
res["full_ratio_current_default_sl_le_800"] = {"n": int(sel.sum()), "median": round(float(np.median(rr)), 2), "p90": round(float(np.percentile(rr, 90)), 2)}

# municipality table
muni_rows = []
for m in sorted(set(d.p_muni)):
    msk = dm & (d.p_muni == m)
    a = share_block(msk, sl_cur, best_cur)
    b = share_block(msk, sl_all, best_all)
    muni_rows.append({"municipality": m, "places": a["n"], "current_sl400_pct": a["sl_400_pct"], "current_net400_pct": a["net_400_pct"], "current_sl800_pct": a["sl_800_pct"], "current_net800_pct": a["net_800_pct"],
                      "all_sched_sl400_pct": b["sl_400_pct"], "all_sched_net400_pct": b["net_400_pct"]})
with open(HERE / "q2_walk_by_municipality.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(muni_rows[0].keys()))
    w.writeheader(); w.writerows(muni_rows)

# per-place result for later scripts (floats)
np.savez_compressed(HERE / "q2_walk_distances.npz", sl_all=sl_all.astype(np.float32), sl_cur=sl_cur.astype(np.float32), net_all=best_all.astype(np.float32), net_cur=best_cur.astype(np.float32),
                    p_edge=p_edge, p_conn=p_conn.astype(np.float32), default=dm)

# ---- sanity checks: snapping versus roads.Roads.snap, and walking vs roads.Roads.route on pairs ------------------
chk = {}
ex = rng.choice(np.nonzero(dm & (p_edge >= 0))[0], 60, replace=False)
dd_ = []
for pi in ex:
    sn = R.snap(float(d.p_lng[pi]), float(d.p_lat[pi]), 150)
    if sn:
        dd_.append((sn["dist"], float(p_conn[pi])))
a = np.array(dd_)
chk["snap_distance_roads_py_vs_walknet"] = {"n": len(a), "median_abs_diff_m": round(float(np.median(np.abs(a[:, 0] - a[:, 1]))), 2), "share_within_2m": pct(int((np.abs(a[:, 0] - a[:, 1]) <= 2).sum()), len(a))}
# router pairs: place -> its walking-nearest scheduled stop; compare router length (fastest drive path, one-way rules) with walking metres
pairs = [r for r in found if r["net_all"] is not None and r["net_all"] > 150][:200]
sel_pairs = rng.choice(len(pairs), 40, replace=False)
comp = []
for j in sel_pairs:
    r = pairs[j]
    pi = r["place"]
    # find the stop that gave net_all: re-run search to get its id
    best = net.search(int(p_edge[pi]), float(p_along[pi]), float(p_conn[pi]), BOUND, node_reg_s, edge_reg_s)
    k = min(best, key=best.get)
    sa = R.snap(float(d.p_lng[pi]), float(d.p_lat[pi]), 150)
    sb = R.snap(float(d.t_lng[sidx[k]]), float(d.t_lat[sidx[k]]), 150)
    if not (sa and sb):
        continue
    rt = R.route(sa, sb)
    if rt:
        comp.append((best[k], rt[2] + sa["dist"] + sb["dist"]))
c = np.array(comp)
chk["router_vs_walk"] = {"pairs": len(c), "walk_le_router_pct": pct(int((c[:, 0] <= c[:, 1] + 1).sum()), len(c)),
                         "median_router_over_walk": round(float(np.median(c[:, 1] / c[:, 0])), 3)}
res["checks"] = chk

res["total_script_s"] = round(t_all(), 1)
write_json("q2_walk.json", res)
print(json.dumps({k: v for k, v in res.items() if k not in ("full_by_category",)}, indent=1, default=str)[:12000])
