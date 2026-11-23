"""Q2: how much does the roads-only graph (roads.bin) distort walking distance? Compare with a full OSM walking network built from the same
OpenStreetMap extract (footways, paths, steps, pedestrian ways, tracks and service roads added; motorways left out).
Reads osm_walk_ways.pkl (made by 02b) and the saved sample ids / distances of 02_walk.py.
"""
from service import *
from walknet import *
import pickle

BOUND = 1000.0
SNAP_M = 150.0
t_all = timer()
d = Data()
res = {}
dm = d.default

# ---- build the OSM walking graph ---------------------------------------------------------------------------------
t = timer()
with open(HERE / "osm_walk_ways.pkl", "rb") as f:
    W = pickle.load(f)
ways, coord = W["ways"], W["coord"]
cnt = Counter()
for hw, refs, sw, sf in ways:
    cnt[refs[0]] += 2
    cnt[refs[-1]] += 2
    for r in refs[1:-1]:
        cnt[r] += 1
node_id = {}
eu, ev = [], []
verts_lon, verts_lat, vert_edge = [], [], []
edge_hw = []
ne = 0
for hw, refs, sw, sf in ways:
    start = 0
    for i in range(1, len(refs)):
        if cnt[refs[i]] >= 2 or i == len(refs) - 1:
            seg = refs[start:i + 1]
            a, b = seg[0], seg[-1]
            ua = node_id.setdefault(a, len(node_id))
            vb = node_id.setdefault(b, len(node_id))
            for r in seg:
                lo, la = coord[r]
                verts_lon.append(lo); verts_lat.append(la); vert_edge.append(ne)
            eu.append(ua); ev.append(vb); edge_hw.append(hw)
            ne += 1
            start = i
res["build_edges_s"] = round(t(), 1)
vx, vy = to_xy(np.array(verts_lon), np.array(verts_lat))
geoms = linestrings(np.column_stack([vx, vy]), indices=np.array(vert_edge))
net2 = WalkNet(eu, ev, geoms, len(node_id), label="OSM full walking network")
res["osm_walk_graph"] = {"nodes": len(node_id), "edges": int(net2.n_edges), "km": round(float(net2.len.sum()) / 1000, 0), "build_total_s": round(t(), 1)}
edge_hw = np.array(edge_hw)
res["osm_walk_graph"]["km_by_class"] = {k: round(float(net2.len[edge_hw == k].sum()) / 1000, 1) for k in sorted(set(edge_hw), key=lambda k: -net2.len[edge_hw == k].sum())[:14]}
print("OSM walk graph", res["osm_walk_graph"])

# ---- stops, places ---------------------------------------------------------------------------------------------------
sidx = np.nonzero(d.t_sched)[0]
sx, sy = d.t_x[sidx], d.t_y[sidx]
s_cur = d.t_current[sidx]
s_edge, s_along, s_conn = net2.snap(sx, sy, SNAP_M)
p_edge, p_along, p_conn = net2.snap(d.p_x, d.p_y, SNAP_M)
res["stops_snapped"] = int((s_edge >= 0).sum())
res["places_default_snapped_150m"] = int(((p_edge >= 0) & dm).sum())
res["places_default_not_snapped_150m"] = int(((p_edge < 0) & dm).sum())
res["places_default_median_connector_m"] = float(np.median(p_conn[(p_edge >= 0) & dm]))
sl_all, nn_all = nearest_dist(d.p_x, d.p_y, sx, sy)
cur_ids = np.nonzero(s_cur)[0]
sl_cur, _ = nearest_dist(d.p_x, d.p_y, sx[cur_ids], sy[cur_ids])

# full run
t = timer()
node_reg_p, edge_reg_p = net2.registry(p_edge, p_along, p_conn)
best_all = np.full(d.n_places, np.inf)
best_cur = np.full(d.n_places, np.inf)
settled = 0
for k in range(len(sidx)):
    if s_edge[k] < 0:
        continue
    best, ns = net2.search(int(s_edge[k]), float(s_along[k]), float(s_conn[k]), BOUND, node_reg_p, edge_reg_p, want_nodes=True)
    settled += ns
    iscur = bool(s_cur[k])
    for pid, dd in best.items():
        if dd < best_all[pid]:
            best_all[pid] = dd
        if iscur and dd < best_cur[pid]:
            best_cur[pid] = dd
res["full_run_s"] = round(t(), 1)
res["full_run_settled_nodes_per_stop_mean"] = round(settled / max(1, int((s_edge >= 0).sum())))
print("full run on OSM walk graph", res["full_run_s"], "s")

# roads.bin results (from 02_walk.py)
Z = np.load(HERE / "q2_walk_distances.npz")
rb_all, rb_cur = Z["net_all"].astype(float), Z["net_cur"].astype(float)

def blk(mask, sl, nd):
    n = int(mask.sum())
    o = {"n": n}
    for thr in (400, 800):
        o[f"sl_{thr}_pct"] = pct(int((sl[mask] <= thr).sum()), n)
        o[f"net_{thr}_pct"] = pct(int((nd[mask] <= thr).sum()), n)
        o[f"lost_{thr}_pct_of_sl"] = pct(int(((sl[mask] <= thr) & ~(nd[mask] <= thr)).sum()), int((sl[mask] <= thr).sum()))
    return o

res["island_current"] = {"straight_line": blk(dm, sl_cur, best_cur)["sl_400_pct"], "roads_bin": blk(dm, sl_cur, rb_cur), "osm_full_walk": blk(dm, sl_cur, best_cur)}
res["island_all_scheduled"] = {"roads_bin": blk(dm, sl_all, rb_all), "osm_full_walk": blk(dm, sl_all, best_all)}

# sample comparison
sample = np.load(HERE / "q2_sample_ids.npy")
def sample_stats(nd_all, sl, snapped):
    rows = [(i, sl[i], nd_all[i]) for i in sample if snapped[i]]
    found = [(i, s, n) for i, s, n in rows if np.isfinite(n)]
    ratios = np.array([n / max(s, 1.0) for i, s, n in found])
    sl400 = [(i, s, n) for i, s, n in [(i, sl[i], nd_all[i]) for i in sample if snapped[i]] if s <= 400]
    flips = sum(1 for i, s, n in sl400 if not (n <= 400))
    return {"sample": len(sample), "snapped": len(rows), "found": len(found), "median_ratio": round(float(np.median(ratios)), 2), "p90_ratio": round(float(np.percentile(ratios, 90)), 2),
            "p95_ratio": round(float(np.percentile(ratios, 95)), 2), "sl_le_400": len(sl400), "flips_over_400": flips, "flip_pct": pct(flips, len(sl400))}
res["sample_roads_bin"] = sample_stats(rb_all, sl_all, Z["p_edge"] >= 0)
res["sample_osm_full_walk"] = sample_stats(best_all, sl_all, p_edge >= 0)
# on the sample: how many places that are beyond 400 m by roads.bin come back within 400 m on the full walk graph
lost_rb = [i for i in sample if sl_all[i] <= 400 and not (rb_all[i] <= 400)]
res["sample_roads_bin_flips"] = len(lost_rb)
res["sample_of_those_recovered_le_400_on_osm_walk"] = int(sum(1 for i in lost_rb if best_all[i] <= 400))
res["sample_of_those_unsnapped_on_roads_bin"] = int(sum(1 for i in lost_rb if Z["p_edge"][i] < 0))

# island: places lost by roads.bin but within 400 on OSM graph
lost_cur = dm & (sl_cur <= 400) & ~(rb_cur <= 400)
res["island_current_lost_on_roads_bin_400"] = int(lost_cur.sum())
res["island_current_lost_on_roads_bin_400_recovered_on_osm_walk"] = int((lost_cur & (best_cur <= 400)).sum())
res["island_current_lost_on_roads_bin_400_still_lost_on_osm_walk"] = int((lost_cur & ~(best_cur <= 400)).sum())
# difference between the two graphs (places where both found)
both = dm & np.isfinite(rb_all) & np.isfinite(best_all) & (sl_all <= 800)
rr = best_all[both] / np.maximum(rb_all[both], 1)
res["osm_walk_over_roads_bin_distance_ratio_where_both_found"] = {"n": int(both.sum()), "median": round(float(np.median(rr)), 3), "p10": round(float(np.percentile(rr, 10)), 3), "p90": round(float(np.percentile(rr, 90)), 3),
                                                                   "share_osm_walk_shorter_by_more_than_10pct": pct(int((rr < 0.9).sum()), int(both.sum()))}
# unsnapped
res["places_default_unsnapped_roads_bin_vs_osm"] = {"roads_bin": int(((Z["p_edge"] < 0) & dm).sum()), "osm_walk": int(((p_edge < 0) & dm).sum())}
np.savez_compressed(HERE / "q2c_osm_walk_distances.npz", net_all=best_all.astype(np.float32), net_cur=best_cur.astype(np.float32), p_edge=p_edge)
# estimate of a binary file for the OSM walking graph in roads.bin's layout (12 bytes per edge, 8 per node, 4 per shape point)
n_shape = int(sum(len(g.coords) - 2 for g in net2.geoms))
res["osm_walk_graph"]["roads_bin_layout_size_mb_estimate"] = round((20 + 8 * len(node_id) + 12 * net2.n_edges + 4 * n_shape) / 1e6, 1)
res["total_s"] = round(t_all(), 1)
write_json("q2c_osm_walk.json", res)
print(json.dumps(res, indent=1, default=str))
