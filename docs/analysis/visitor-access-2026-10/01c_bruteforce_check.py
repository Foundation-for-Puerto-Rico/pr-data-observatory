"""Independent check of Q1 numbers: brute-force nearest distance with the twin's own flat-earth formula (no projection, no spatial index)."""
from service import *
d = Data()
locs, s2l, loc_of = build_locations(d)
add_calls(d, locs, loc_of)
sat = np.zeros(d.n_tr, bool); sun = np.zeros(d.n_tr, bool)
for i, k in s2l.items():
    sat[i] = locs[k]["sa"] > 0; sun[i] = locs[k]["su"] > 0
sets = {"B_current": d.t_current, "C20": d.t_current & (d.t_trips >= 20), "C40": d.t_current & (d.t_trips >= 40), "D_sat": d.t_current & sat, "D_sun": d.t_current & sun,
        "E_rail_ferry": np.isin(d.t_kind, ["rail_station", "ferry_terminal"])}
dm = d.default
plat, plng = d.p_lat[dm], d.p_lng[dm]
out = {}
for nm, m in sets.items():
    idx = np.nonzero(m)[0]
    slat, slng = d.t_lat[idx], d.t_lng[idx]
    best = np.full(len(plat), np.inf)
    for a in range(0, len(plat), 1500):
        la = plat[a:a + 1500, None]; lo = plng[a:a + 1500, None]
        dlat = (slat[None, :] - la) * 111_320
        dlng = (slng[None, :] - lo) * 111_320 * np.cos(np.radians((la + slat[None, :]) / 2))
        best[a:a + 1500] = np.sqrt(dlat ** 2 + dlng ** 2).min(axis=1)
    out[nm] = {"p400": pct(int((best <= 400).sum()), len(plat)), "p800": pct(int((best <= 800).sum()), len(plat))}
q1 = read_json("q1_baseline.json")["island"]
keymap = {"B_current": "B_current_scheduled", "C20": "C20_current_trips>=20", "C40": "C40_current_trips>=40", "D_sat": "D_sat_current", "D_sun": "D_sun_current", "E_rail_ferry": "E_rail_or_ferry_any_source"}
for nm, v in out.items():
    print(nm, "brute force twin formula:", v, "  EPSG:32161 + STRtree:", {"p400": q1[keymap[nm]]["p400"], "p800": q1[keymap[nm]]["p800"]})
write_json("q1d_bruteforce_check.json", out)
