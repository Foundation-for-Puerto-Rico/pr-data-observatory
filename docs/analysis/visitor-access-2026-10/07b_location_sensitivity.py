"""Sensitivity: weekday-call thresholds on stop locations (sum of co-located stop IDs of one operator) instead of single stop IDs."""
from service import *
d = Data()
locs, s2l, loc_of = build_locations(d)
add_calls(d, locs, loc_of)
dm = d.default
loc_trips = np.zeros(d.n_tr, int)
for i, k in s2l.items():
    loc_trips[i] = locs[k]["trips_feed"]
out = {}
for thr in (10, 20, 40):
    stop_level = d.t_current & (d.t_trips >= thr)
    loc_level = d.t_current & (loc_trips >= thr)
    a, _ = nearest_dist(d.p_x, d.p_y, d.t_x[stop_level], d.t_y[stop_level])
    b, _ = nearest_dist(d.p_x, d.p_y, d.t_x[loc_level], d.t_y[loc_level])
    out[str(thr)] = {"stop_level_pct400": pct(int((a[dm] <= 400).sum()), int(dm.sum())), "location_level_pct400": pct(int((b[dm] <= 400).sum()), int(dm.sum())),
                     "stops_stop_level": int(stop_level.sum()), "stops_location_level": int(loc_level.sum())}
write_json("q1c_location_sensitivity.json", out)
print(json.dumps(out, indent=1))
