"""Q2: how far apart are the roads-only and the full-OSM walking shares for individual municipalities (400 m, current scheduled stops)?"""
from common import *
d = Data()
dm = d.default
rb = np.load(HERE / "q2_walk_distances.npz")["net_cur"].astype(float)
osm = np.load(HERE / "q2c_osm_walk_distances.npz")["net_cur"].astype(float)
rows = []
for m in sorted(set(d.p_muni)):
    mk = dm & (d.p_muni == m)
    if mk.sum() >= 100:
        rows.append((m, 100 * float((rb[mk] <= 400).mean()), 100 * float((osm[mk] <= 400).mean())))
diff = np.array([abs(a - b) for _, a, b in rows])
res = {"municipalities_with_100_or_more_places": len(rows), "median_abs_diff_pts": round(float(np.median(diff)), 2), "p90_abs_diff_pts": round(float(np.percentile(diff, 90)), 2),
       "max_abs_diff_pts": round(float(diff.max()), 1), "max_at": rows[int(diff.argmax())][0], "share_with_diff_under_1pt_pct": pct(int((diff < 1).sum()), len(diff))}
write_json("q2d_muni_graph_diff.json", res)
print(res)
