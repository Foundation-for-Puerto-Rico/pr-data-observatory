"""Q6 support: access classes, hub proximity and the size of the proposed per-place fields and per-area series (measured, not guessed).
Nothing here modifies the repository: places are re-serialised in memory to measure the added bytes.
"""
from service import *
import gzip
import csv

d = Data()
T = d.transport
dm = d.default
res = {}
Q1 = np.load(HERE / "q1_distances.npz")
Z2 = np.load(HERE / "q2_walk_distances.npz")
Z4 = np.load(HERE / "q4_sju_times.npz")
locs, s2l, loc_of = build_locations(d)
add_calls(d, locs, loc_of)
sat = np.zeros(d.n_tr, bool); sun = np.zeros(d.n_tr, bool)
for i, k in s2l.items():
    sat[i] = locs[k]["sa"] > 0; sun[i] = locs[k]["su"] > 0

# ---- access classes (default basis) -----------------------------------------------------------------------------------------
cur = Q1["B_current_scheduled"].astype(float)
c20 = Q1["C20_current_trips>=20"].astype(float)
anyd = Q1["A_any_stop_twin_today"].astype(float)
cls = np.full(d.n_places, 5)
cls[anyd <= 800] = 4                    # a stop of any kind, but not a current scheduled one within 800 m
cls[cur <= 800] = 3
cls[cur <= 400] = 2
cls[(cur <= 400) & (c20 <= 400)] = 1
labels = {1: "frequent: current scheduled stop within 400 m with at least 20 weekday calls", 2: "basic: current scheduled stop within 400 m (fewer than 20 calls at every such stop)",
          3: "near: current scheduled stop 400-800 m away", 4: "paper only: no current scheduled stop within 800 m, but an expired-feed or volunteer-mapped stop within 800 m", 5: "none: no stop of any kind within 800 m"}
res["access_classes_island"] = {labels[k]: {"n": int(((cls == k) & dm).sum()), "pct": pct(int(((cls == k) & dm).sum()), int(dm.sum()))} for k in (1, 2, 3, 4, 5)}
res["access_classes_by_category"] = {c: {str(k): pct(int(((cls == k) & dm & (d.p_cat == c)).sum()), int((dm & (d.p_cat == c)).sum())) for k in (1, 2, 3, 4, 5)} for c in CATS}
res["access_classes_by_region"] = {r: {str(k): pct(int(((cls == k) & dm & (d.p_region == r)).sum()), int((dm & (d.p_region == r)).sum())) for k in (1, 2, 3, 4, 5)} for r in sorted(set(d.p_region) - {""})}

# ---- hub proximity ---------------------------------------------------------------------------------------------------------
air_public = np.array([f["source"] == "faa_airports" and bool(f.get("public_use")) or (f["source"] == "osm_transport" and f["kind"] == "airport" and bool(f.get("iata"))) for f in T])
hubs = {"public_airport": air_public, "ferry_terminal_any": d.t_kind == "ferry_terminal", "rail_station": d.t_kind == "rail_station", "bus_terminal_scheduled_or_osm": (d.t_kind == "bus_station")}
hub_tab = {"counts": {k: int(v.sum()) for k, v in hubs.items()}}
for k, m in hubs.items():
    dd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[m], d.t_y[m])
    hub_tab[k] = {f"pct_within_{r}m": pct(int((dd[dm] <= r).sum()), int(dm.sum())) for r in (1000, 2000, 5000, 10000, 25000)}
    hub_tab[k]["median_km"] = round(float(np.median(dd[dm])) / 1000, 1)
anyhub = hubs["public_airport"] | hubs["ferry_terminal_any"] | hubs["rail_station"] | hubs["bus_terminal_scheduled_or_osm"]
dd, _ = nearest_dist(d.p_x, d.p_y, d.t_x[anyhub], d.t_y[anyhub])
hub_tab["any_gateway"] = {f"pct_within_{r}m": pct(int((dd[dm] <= r).sum()), int(dm.sum())) for r in (1000, 2000, 5000, 10000, 25000)}
# the places with no stop within 800 m (class 4 and 5): how far from a gateway?
far = dm & (cls >= 4)
hub_tab["places_without_current_scheduled_stop_within_800m"] = {"n": int(far.sum()), **{f"pct_within_{r}m_of_any_gateway": pct(int((dd[far] <= r).sum()), int(far.sum())) for r in (2000, 5000, 10000, 25000)}}
res["hub_proximity_default"] = hub_tab

# ---- per-place fields (Tier 1-3) ------------------------------------------------------------------------------------------
cur_idx = np.nonzero(d.t_current)[0]
tree = STRtree(points(d.t_x[cur_idx], d.t_y[cur_idx]))
i, j = tree.query(points(d.p_x, d.p_y), predicate="dwithin", distance=400)
calls = np.zeros(d.n_places, int)
np.maximum.at(calls, i, d.t_trips[cur_idx][j])
we = np.zeros(d.n_places, int)
np.bitwise_or.at(we, i, (sat[cur_idx][j].astype(int) * 1) | (sun[cur_idx][j].astype(int) * 2))
# nearest rail station / ferry terminal (any source) and its index in a hub list
hub_idx = np.nonzero(np.isin(d.t_kind, ["rail_station", "ferry_terminal"]))[0]
hd, hn = nearest_dist(d.p_x, d.p_y, d.t_x[hub_idx], d.t_y[hub_idx])
net_cur = Z2["net_cur"].astype(float)
sju_t = Z4["transit_min"].astype(float)
sju_b = Z4["rounds"]
sju_d = Z4["drive_min"].astype(float)

def fields_for(k, tier):
    p = {}
    ts = cur[k]
    p["ts_m"] = int(min(ts, 99999))
    if calls[k]:
        p["ts_calls"] = int(calls[k])
    if we[k]:
        p["ts_we"] = int(we[k])
    p["hub_m"] = int(min(hd[k], 99999))
    p["hub"] = int(hn[k])
    if tier >= 2 and np.isfinite(net_cur[k]):
        p["tw_m"] = int(net_cur[k])
    if tier >= 3:
        if np.isfinite(sju_t[k]) and sju_t[k] <= 240:
            p["sju_t"] = int(round(sju_t[k]))
            p["sju_b"] = int(sju_b[k])
        if np.isfinite(sju_d[k]):
            p["sju_d"] = int(round(sju_d[k]))
    return p

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

base_bytes = dumps(d.places)
orig = (DATA / "places.json").stat().st_size
res["size_check"] = {"places_json_on_disk_bytes": orig, "re_serialised_bytes": len(base_bytes), "identical_length": orig == len(base_bytes)}
def gz(b, lvl=6):
    return len(gzip.compress(b, compresslevel=lvl, mtime=0))
res["places_json_raw_mb"] = round(len(base_bytes) / 1e6, 2)
res["places_json_gzip6_mb"] = round(gz(base_bytes) / 1e6, 3)
sizes = {}
for tier, label in ((1, "tier1_ts_m_ts_calls_ts_we_hub_m_hub"), (2, "tier1_plus_tw_m"), (3, "tier1_plus_tw_m_plus_sju_t_sju_b_sju_d")):
    enriched = []
    for k, p in enumerate(d.places):
        q = dict(p)
        q.update(fields_for(k, tier))
        enriched.append(q)
    b = dumps(enriched)
    sizes[label] = {"raw_added_kb": round((len(b) - len(base_bytes)) / 1024, 0), "gzip6_added_kb": round((gz(b) - gz(base_bytes)) / 1024, 0), "raw_total_mb": round(len(b) / 1e6, 2), "gzip6_total_mb": round(gz(b) / 1e6, 3)}
res["places_json_added_size"] = sizes
# tier-1 minimal variant: only ts_m and ts_calls
enriched = []
for k, p in enumerate(d.places):
    q = dict(p)
    q["ts_m"] = int(min(cur[k], 99999))
    if calls[k]:
        q["ts_calls"] = int(calls[k])
    enriched.append(q)
b = dumps(enriched)
sizes["minimal_ts_m_and_ts_calls"] = {"raw_added_kb": round((len(b) - len(base_bytes)) / 1024, 0), "gzip6_added_kb": round((gz(b) - gz(base_bytes)) / 1024, 0)}
# core three fields as JSON (ts_m, ts_calls, ts_we) - the recommended per-place minimum
enriched = []
for k, p in enumerate(d.places):
    q = dict(p)
    q["ts_m"] = int(min(cur[k], 99999))
    if calls[k]:
        q["ts_calls"] = int(calls[k])
    if we[k]:
        q["ts_we"] = int(we[k])
    enriched.append(q)
b = dumps(enriched)
sizes["core3_ts_m_ts_calls_ts_we"] = {"raw_added_kb": round((len(b) - len(base_bytes)) / 1024, 0), "gzip6_added_kb": round((gz(b) - gz(base_bytes)) / 1024, 0)}
# binary columnar alternative (typed arrays, same order as places.json)
cols = {
    "ts_m": np.minimum(cur, 65534).astype("<u2"), "ts_calls": calls.astype("<u2"), "ts_we": we.astype("u1"), "hub_m": np.minimum(hd, 65534).astype("<u2"), "hub": hn.astype("u1"),
    "tw_m": np.where(np.isfinite(net_cur), np.minimum(net_cur, 65534), 65535).astype("<u2"),
    "sju_t": np.where(np.isfinite(sju_t) & (sju_t <= 240), np.round(sju_t), 65535).astype("<u2"), "sju_b": sju_b.astype("u1"),
    "sju_d": np.where(np.isfinite(sju_d), np.round(sju_d), 65535).astype("<u2"),
}
core3 = b"".join(cols[k].tobytes() for k in ("ts_m", "ts_calls", "ts_we"))
res["binary_core3_columns"] = {"raw_kb": round(len(core3) / 1024, 0), "gzip6_kb": round(gz(core3) / 1024, 0)}
raw = b"".join(v.tobytes() for v in cols.values())
res["binary_columns_alternative"] = {"columns": list(cols), "raw_kb": round(len(raw) / 1024, 0), "gzip6_kb": round(gz(raw) / 1024, 0), "n_places": d.n_places}
# per-column gz
res["binary_columns_gzip_kb_each"] = {k: round(gz(v.tobytes()) / 1024, 1) for k, v in cols.items()}

# ---- per-area series size ---------------------------------------------------------------------------------------------------
fields_muni = ["acc_any400_pct", "acc_any800_pct", "acc_cur400_pct", "acc_cur800_pct", "acc_freq400_pct", "acc_freq800_pct", "acc_sat400_pct", "acc_sun400_pct", "acc_hub400_pct", "acc_hub800_pct",
               "acc_walk400_pct", "acc_only_expired_pct", "acc_only_osm_pct", "stops_current", "stops_expired", "stops_osm", "sju_transit60_pct", "sju_transit90_pct", "sju_transit120_pct",
               "sju_drive60_pct", "sju_drive90_pct", "sju_drive120_pct", "sju_median_transit_min", "sju_median_drive_min", "access_n", "access_as_of"]
muni_json = jload("municipalities.json")
base_m = dumps(muni_json)
rng_ = np.random.default_rng(7)
mm = {}
for n_, v in muni_json.items():
    mm[n_] = dict(v)
    for f_ in fields_muni:
        mm[n_][f_] = round(float(rng_.uniform(0, 100)), 1) if f_ != "access_as_of" else "2026-10-05"
b = dumps(mm)
res["municipalities_json_added"] = {"fields": len(fields_muni), "raw_added_kb": round((len(b) - len(base_m)) / 1024, 1), "gzip6_added_kb": round((gz(b) - gz(base_m)) / 1024, 1)}
bg = jload("barrios.geojson")
base_b = dumps(bg)
for ft in bg["features"]:
    ft["properties"].update({"acc_cur400_pct": round(float(rng_.uniform(0, 100)), 1), "acc_freq400_pct": round(float(rng_.uniform(0, 100)), 1), "acc_sat400_pct": round(float(rng_.uniform(0, 100)), 1), "acc_n": int(rng_.integers(5, 400))})
b = dumps(bg)
res["barrios_geojson_added"] = {"features": len(bg["features"]), "fields": 4, "raw_added_kb": round((len(b) - len(base_b)) / 1024, 1), "gzip6_added_kb": round((gz(b) - gz(base_b)) / 1024, 1)}
# transport.json: weekend and daytime fields on scheduled stops
tj = jload("transport.json")
base_t = dumps(tj)
for k, f in enumerate(tj):
    if f["source"] in SCHEDULED_SOURCES:
        L = locs[s2l[k]]
        f["calls_sat"], f["calls_sun"] = int(L["sa"]), int(L["su"])
        f["feed"] = "c"
b = dumps(tj)
res["transport_json_added_for_scheduled_stops"] = {"fields": "calls_sat, calls_sun, feed", "raw_added_kb": round((len(b) - len(base_t)) / 1024, 1), "gzip6_added_kb": round((gz(b) - gz(base_t)) / 1024, 1)}
# gateways table (aggregate estimate by serialising the real records with the proposed fields)
gws = []
for i_, f in enumerate(T):
    if f["kind"] in ("airport", "ferry_terminal", "rail_station", "bus_station") and (f["source"] != "faa_airports" or f.get("public_use")):
        gws.append({"id": f["id"], "kind": f["kind"], "name": f["name"], "lat": f["lat"], "lng": f["lng"], "municipality": f["municipality"], "d_bus_m": 120, "calls_400m": 150, "routes": f.get("routes") or [], "src": f["source"]})
res["gateways_json_estimate"] = {"records": len(gws), "raw_kb": round(len(dumps(gws)) / 1024, 1), "gzip6_kb": round(gz(dumps(gws)) / 1024, 1)}
write_json("q6_design_numbers.json", res)
print(json.dumps(res, indent=1, default=str))
