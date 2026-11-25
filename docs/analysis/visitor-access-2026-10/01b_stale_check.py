"""Q1/Q5: how stale is places.json (transit_m, transit_400m, nearest_stop) compared with the CURRENT transport.json?
Replicates the twin's own distance formula (transport.py _dist_m: 111,320 m per degree latitude, longitude shortened by cos(mean lat))
and its stop set (kinds transit_stop, bus_stop, bus_station, rail_station, ferry_terminal; any source, any feed status), by brute force
(true nearest in meters, not nearest in degrees).
"""
from common import *

d = Data()
m = np.nonzero(d.t_access)[0]
slat, slng = d.t_lat[m], d.t_lng[m]
T = d.transport

best = np.full(d.n_places, np.inf)
arg = np.zeros(d.n_places, int)
CH = 1500
for a in range(0, d.n_places, CH):
    la = d.p_lat[a:a + CH, None]
    lo = d.p_lng[a:a + CH, None]
    dlat = (slat[None, :] - la) * 111_320
    dlng = (slng[None, :] - lo) * 111_320 * np.cos(np.radians((la + slat[None, :]) / 2))
    D = np.sqrt(dlat * dlat + dlng * dlng)
    j = D.argmin(axis=1)
    arg[a:a + CH] = j
    best[a:a + CH] = D[np.arange(len(j)), j]

pub = d.p_transit_m
dm = d.default
new_i = np.floor(best)          # the twin cuts to whole meters for transit_m
res = {}
res["twin_formula_pct400_default_current_stops"] = pct(((best <= 400) & dm).sum(), dm.sum())
res["published_pct400_default"] = pct((d.p_t400 & dm).sum(), dm.sum())
res["places_where_transit_m_differs_by_more_than_2m_all"] = int((np.abs(new_i - pub) > 2).sum())
res["places_where_transit_m_differs_by_more_than_2m_default"] = int(((np.abs(new_i - pub) > 2) & dm).sum())
res["differs_gt2m_not_jayuya_all"] = int(((np.abs(new_i - pub) > 2) & (d.p_muni != "Jayuya")).sum())
chg = np.abs(new_i - pub) > 2
res["differs_gt2m_new_closer_all"] = int((chg & (new_i < pub)).sum())
res["differs_gt2m_new_farther_all"] = int((chg & (new_i > pub)).sum())
res["flag_changes_default"] = int(((d.p_t400 != (best <= 400)) & dm).sum())
res["flag_false_to_true_default"] = int((~d.p_t400 & (best <= 400) & dm).sum())
res["flag_true_to_false_default"] = int((d.p_t400 & ~(best <= 400) & dm).sum())
res["flag_changes_default_jayuya"] = int(((d.p_t400 != (best <= 400)) & dm & (d.p_muni == "Jayuya")).sum())
res["flag_changes_default_not_jayuya"] = int(((d.p_t400 != (best <= 400)) & dm & (d.p_muni != "Jayuya")).sum())
# of the non-Jayuya changes: why? distance within 2 m of the 400 line (rounding) vs a different nearest stop
nj = (d.p_t400 != (best <= 400)) & dm & (d.p_muni != "Jayuya")
res["flag_changes_not_jayuya_within_3m_of_line"] = int((nj & (np.abs(best - 400) <= 3)).sum())
# nearest stop name changed
chg_name = 0
for i in np.nonzero(np.abs(new_i - pub) > 2)[0]:
    f = T[m[arg[i]]]
    nm = f["name"] or f["kind"].replace("_", " ")
    chg_name += nm != d.places[i].get("nearest_stop")
res["differs_gt2m_and_nearest_stop_name_differs_all"] = int(chg_name)
# Jayuya
jay = d.p_muni == "Jayuya"
res["jayuya_places_all"] = int(jay.sum())
res["jayuya_published_median_transit_m"] = float(np.median(pub[jay]))
res["jayuya_recomputed_median_transit_m"] = float(np.median(best[jay]))
res["jayuya_default_pct400_published"] = pct((d.p_t400 & jay & dm).sum(), (jay & dm).sum())
res["jayuya_default_pct400_recomputed"] = pct(((best <= 400) & jay & dm).sum(), (jay & dm).sum())
# approx. difference due to formula alone: compare EPSG:32161 distance to formula distance for places within 1 km
dd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[m], d.t_y[m])
r = dd / np.maximum(best, 1)
sel = best < 2000
res["epsg32161_over_twin_formula_ratio_median_within_2km"] = float(np.median(r[sel]))
res["epsg32161_over_twin_formula_ratio_p5_p95_within_2km"] = [float(np.percentile(r[sel], 5)), float(np.percentile(r[sel], 95))]
res["share_default_within_400_epsg32161"] = pct(((dd <= 400) & dm).sum(), dm.sum())
res["share_default_within_400_twin_formula"] = pct(((best <= 400) & dm).sum(), dm.sum())
res["share_default_within_800_epsg32161"] = pct(((dd <= 800) & dm).sum(), dm.sum())
res["share_default_within_800_twin_formula"] = pct(((best <= 800) & dm).sum(), dm.sum())
write_json("q1b_stale_check.json", res)
for k, v in res.items():
    print(k, v)
