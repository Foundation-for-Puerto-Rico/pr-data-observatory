"""Access of tourism places to transport, computed in one place from the stops the observatory publishes.

build.py (full build) and refresh_network.py (nightly) both call this module, so a place's access fields cannot drift away from the stops
(before 2026-10 the nightly refresh rewrote the stops but never touched places.json, and the fields went stale). Method and reasons:
docs/visitor-transport-access-2026-10.md.

Three stop sets, all schedule-based, measured by straight line (and the current stops also by walking, below):

  any mapped stop   a stop, station or terminal of kind transit_stop, bus_stop, bus_station, rail_station or ferry_terminal from any source:
                    scheduled feeds (expired timetables included) and volunteer-mapped OpenStreetMap stops. This is the measure the observatory
                    published until 2026-10 as "within 400 m of transit". It is kept (places.json: transit_m, transit_400m, nearest_stop;
                    municipalities.json: places_near_transit, transit_pct) and labeled as what it is.
  current stop      a scheduled stop (ATI or a municipal GTFS feed) whose operator's feed has not ended on the as-of date.
  frequent stop     a current stop with 20 or more calls on a typical weekday.

Fields written (place_access.json holds the per-place columns; the rest update published files):

  ts_m      meters to the nearest current stop, rounded up (so ts_m <= 400 is exactly the test used for the shares), 99,999 at most
  ts_calls  most weekday calls at any current stop within 400 m (0 when there is none): a frequency proxy, not a headway
  ts_we     1 = a current stop within 400 m has Saturday service, 2 = Sunday service (0 = neither in the published feeds)
  tw_m, tw_calls, tw_we   the same three by walking along mapped roads (walknet.py), searched up to 1,000 m (99,999 beyond). The map's
            access classes and the walking shares use them. A place with no walkable road within 150 m keeps its straight-line values and is
            listed in tw_straight; a stop with no walkable road nearby counts at its straight-line distance. Not footpaths: see walknet.py.

Usage:  python access.py            recompute the published files from site/data and write what changed
        python access.py --check    say whether the published files are up to date (exit 1 when not), writing nothing
"""
import argparse
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"

NEAR_M = 400
FAR_M = 800
FREQUENT_CALLS = 20
CAP_M = 99_999
MIN_CONF = 0.5
ANY_KINDS = ("transit_stop", "bus_stop", "bus_station", "rail_station", "ferry_terminal")   # as transport.py has always counted stops
SCHEDULED_SOURCES = ("ati_gtfs", "muni_gtfs")
HUB_KINDS = ("rail_station", "ferry_terminal")
SATURDAY, SUNDAY = 1, 2
WALK_BOUND_M = 1_000   # a walking search goes this far from each stop: past FAR_M, so a distance shown up to 1 km is measured, not capped

# Distances use the flat-earth formula the observatory has always used (network.py _dist_m): 111,320 m per degree of latitude, longitude shortened by the
# cosine of the mean latitude of the two points. Against a projected-meter computation (EPSG:32161) it is about 0.6% long north to south, so a share
# reads up to 0.1 point lower (32.0% instead of 32.1% of places near a current stop). Using the same formula keeps places, residents and the
# route planner on one scale.
M_PER_DEG = 111_320.0
CHUNK = 500   # places per block of the distance matrix (500 x 4,400 stops is about 17 MB per array)

BASIS_NOTE = "confidence 0.50 or higher, places of worship left out"


def in_basis(p):
    """The tourism places every count and share uses (the observatory's default basis)."""
    return p.get("type") != "Places of Worship" and (p.get("confidence") or 0) >= MIN_CONF


def operator_list(operators):
    return list(operators.values()) if isinstance(operators, dict) else list(operators or [])


def feed_current(op, as_of):
    """True when the operator's feed has an end date that is not before `as_of`. A feed with no end date cannot be shown to cover today."""
    end = (op.get("feed") or {}).get("end")
    try:
        return end is not None and date.fromisoformat(end) >= as_of
    except (TypeError, ValueError):
        return False


def current_operators(operators, as_of):
    return {o["id"] for o in operator_list(operators) if feed_current(o, as_of)}


class Access:
    """One value per place, in the order of the places list that was passed to compute()."""

    def __init__(self, as_of, stops, current_ids):
        self.as_of = as_of
        self.stops = stops              # the "any mapped stop" records, in the order any_idx points into
        self.current_ids = current_ids  # operators whose feed has not ended on as_of
        self.any_m = self.any_idx = None
        self.ts_m = self.ts_calls = self.ts_we = self.hub400 = None
        self.tw_m = self.tw_calls = self.tw_we = self.tw_straight = None   # walking (None without a walking network)
        self.n_current = self.n_expired = self.n_osm = self.n_stops_off_road = 0

    def stop_state(self, s):
        """current (scheduled, feed not ended), expired (scheduled, feed ended or undated) or osm (mapped by volunteers, no timetable)."""
        if s.get("source") in SCHEDULED_SOURCES:
            return "current" if s.get("operator") in self.current_ids else "expired"
        return "osm" if s.get("source") == "osm_transport" else "other"

    def flags(self, i):
        """Booleans for place i that the shares and classes are built from."""
        return {"any400": bool(self.any_m[i] <= NEAR_M), "any800": bool(self.any_m[i] <= FAR_M), "cur400": bool(self.ts_m[i] <= NEAR_M),
                "cur800": bool(self.ts_m[i] <= FAR_M), "freq400": bool(self.ts_m[i] <= NEAR_M and self.ts_calls[i] >= FREQUENT_CALLS),
                "sat400": bool(self.ts_we[i] & SATURDAY), "sun400": bool(self.ts_we[i] & SUNDAY), "hub400": bool(self.hub400[i]),
                **({} if self.tw_m is None else {"walk400": bool(self.tw_m[i] <= NEAR_M), "walk800": bool(self.tw_m[i] <= FAR_M),
                                                 "wfreq400": bool(self.tw_m[i] <= NEAR_M and self.tw_calls[i] >= FREQUENT_CALLS)})}


def compute(places, stops, operators, as_of, net=None, prev=None):
    """Access fields for every place. Exact (every place against every stop, in blocks); about 3 s for 35,000 places.
    With a walking network (walknet.load()), also the walking fields tw_m, tw_calls and tw_we (see walking()).

    A place withheld from the map (places_privacy.py: no lat and lng in places.json) cannot be measured again: it keeps the values the last full
    build gave it, from `prev` (the previous place_access.json) and from its own transit_m, transit_400m and hub_400m, so the counts and shares
    that include it do not move. Without `prev` its timetable columns are empty (99,999 m, no calls)."""
    located = [i for i, p in enumerate(places) if p.get("lat") is not None and p.get("lng") is not None]
    if len(located) == len(places):
        return _compute(places, stops, operators, as_of, net)
    sub = _compute([places[i] for i in located], stops, operators, as_of, net)
    return _carry(sub, places, located, prev)


def _carry(sub, places, located, prev):
    """Spread the result for the located places back over all of them and fill the withheld ones from `prev` (see compute())."""
    n = len(places)
    res = Access(sub.as_of, sub.stops, sub.current_ids)
    res.n_current, res.n_expired, res.n_osm, res.n_stops_off_road = sub.n_current, sub.n_expired, sub.n_osm, sub.n_stops_off_road
    idx = np.array(located, dtype=np.int64)
    ok = isinstance(prev, dict) and prev.get("n") == n
    walk = sub.tw_m is not None

    def col(key, fill, dtype):
        a = np.array(prev[key], dtype=dtype) if ok and key in prev and len(prev[key]) == n else np.full(n, fill, dtype=dtype)
        return a
    res.ts_m, res.ts_calls, res.ts_we = col("ts_m", CAP_M, np.int64), col("ts_calls", 0, np.int64), col("ts_we", 0, np.int64)
    res.any_m = np.array([float(p.get("transit_m", np.inf)) for p in places])
    for i, p in enumerate(places):   # transit_m is cut to whole meters; transit_400m says on which side of 400 m the exact distance fell
        if not p.get("transit_400m") and res.any_m[i] <= NEAR_M:
            res.any_m[i] = NEAR_M + 0.5
    res.any_idx = np.full(n, -1, dtype=np.int64)
    res.hub400 = np.array([bool(p.get("hub_400m")) for p in places], dtype=bool)
    for name in ("any_m", "any_idx", "ts_m", "ts_calls", "ts_we", "hub400"):
        getattr(res, name)[idx] = getattr(sub, name)
    if walk:
        res.tw_m, res.tw_calls, res.tw_we = col("tw_m", CAP_M, np.int64), col("tw_calls", 0, np.int64), col("tw_we", 0, np.int64)
        for name in ("tw_m", "tw_calls", "tw_we"):
            getattr(res, name)[idx] = getattr(sub, name)
        located_set = set(located)
        kept = [i for i in (prev.get("tw_straight", []) if ok else []) if i not in located_set]
        res.tw_straight = np.array(sorted(kept + idx[sub.tw_straight].tolist()), dtype=np.int64)
    return res


def _compute(places, stops, operators, as_of, net=None):
    cur = current_operators(operators, as_of)
    any_stops = [s for s in stops if s.get("kind") in ANY_KINDS]
    res = Access(as_of, any_stops, cur)
    n = len(places)
    res.any_m = np.full(n, np.inf)
    res.any_idx = np.zeros(n, dtype=np.int64)
    res.ts_m = np.full(n, CAP_M, dtype=np.int64)
    res.ts_calls = np.zeros(n, dtype=np.int64)
    res.ts_we = np.zeros(n, dtype=np.int64)
    res.hub400 = np.zeros(n, dtype=bool)
    sched = [s.get("source") in SCHEDULED_SOURCES for s in any_stops]
    is_cur = np.array([sched[i] and s.get("operator") in cur for i, s in enumerate(any_stops)], dtype=bool)
    res.n_current = int(is_cur.sum())
    res.n_expired = int(np.array(sched, dtype=bool).sum()) - res.n_current
    res.n_osm = sum(1 for s in any_stops if s.get("source") == "osm_transport")
    if not any_stops or not n:
        return res
    slat = np.array([s["lat"] for s in any_stops], dtype=float)
    slng = np.array([s["lng"] for s in any_stops], dtype=float)
    plat = np.array([p["lat"] for p in places], dtype=float)
    plng = np.array([p["lng"] for p in places], dtype=float)
    cur_cols = np.flatnonzero(is_cur)
    cur_calls = np.array([any_stops[j].get("trips_weekday") or 0 for j in cur_cols], dtype=np.int64)
    cur_sat = np.array([(any_stops[j].get("calls_sat") or 0) > 0 for j in cur_cols], dtype=bool)
    cur_sun = np.array([(any_stops[j].get("calls_sun") or 0) > 0 for j in cur_cols], dtype=bool)
    hub_cols = np.array([j for j, s in enumerate(any_stops) if s["kind"] in HUB_KINDS], dtype=np.int64)
    near2 = float(NEAR_M) ** 2
    for a in range(0, n, CHUNK):
        b = min(n, a + CHUNK)
        r = np.arange(b - a)
        dy = (slat[None, :] - plat[a:b, None]) * M_PER_DEG
        dx = (slng[None, :] - plng[a:b, None]) * M_PER_DEG * np.cos(np.radians((plat[a:b, None] + slat[None, :]) / 2))
        d2 = dx * dx + dy * dy
        j = d2.argmin(axis=1)
        res.any_idx[a:b] = j
        res.any_m[a:b] = np.sqrt(d2[r, j])
        if len(hub_cols):
            res.hub400[a:b] = (d2[:, hub_cols] <= near2).any(axis=1)
        if len(cur_cols):
            dc = d2[:, cur_cols]
            jc = dc.argmin(axis=1)
            res.ts_m[a:b] = np.minimum(np.ceil(np.sqrt(dc[r, jc])), CAP_M).astype(np.int64)
            near = dc <= near2
            res.ts_calls[a:b] = np.where(near, cur_calls[None, :], 0).max(axis=1)
            res.ts_we[a:b] = (near & cur_sat[None, :]).any(axis=1) * SATURDAY + (near & cur_sun[None, :]).any(axis=1) * SUNDAY
    if net is not None:
        walking(res, places, [any_stops[j] for j in cur_cols], cur_calls, cur_sat, cur_sun, net)
    return res


def walking(res, places, cur_stops, cur_calls, cur_sat, cur_sun, net):
    """tw_m, tw_calls, tw_we: the ts_* fields measured by walking along mapped roads (walknet.py) instead of a straight line.

    A bounded search runs from each stop with a current timetable, up to WALK_BOUND_M. Two cases fall back to the straight line, so no place
    or stop is silently dropped: a place with no walkable road within walknet.SNAP_M keeps its ts_* values (and is listed in tw_straight),
    and a stop with no walkable road nearby counts at its straight-line distance. A walking distance is never shorter than the straight
    line (tw_m >= ts_m): a walk cannot beat a straight line, and the two metrics differ by under 0.3% (walknet.py)."""
    import walknet
    n = len(places)
    res.tw_m = np.full(n, CAP_M, dtype=np.int64)
    res.tw_calls = np.zeros(n, dtype=np.int64)
    res.tw_we = np.zeros(n, dtype=np.int64)
    if not n:
        res.tw_straight = np.zeros(0, dtype=np.int64)
        return
    per_place, place_ok, stop_ok = walknet.walk_to_stops(net, cur_stops, places, WALK_BOUND_M)   # stops on no walkable road count at the straight line
    lost = np.flatnonzero(~stop_ok)
    for i, near in enumerate(per_place):
        if not place_ok[i]:
            res.tw_m[i], res.tw_calls[i], res.tw_we[i] = res.ts_m[i], res.ts_calls[i], res.ts_we[i]
            continue
        if not near:
            continue
        res.tw_m[i] = min(max(math.ceil(min(near.values())), int(res.ts_m[i])), CAP_M)
        close = [j for j, d in near.items() if d <= NEAR_M]
        if close and res.tw_m[i] <= NEAR_M:
            res.tw_calls[i] = max(int(cur_calls[j]) for j in close)
            res.tw_we[i] = any(cur_sat[j] for j in close) * SATURDAY + any(cur_sun[j] for j in close) * SUNDAY
    res.tw_straight = np.flatnonzero(~place_ok)
    res.n_stops_off_road = int(len(lost))


# ── Fields on the published files ────────────────────────────────────────────

def legacy_fields(places, res):
    """Set transit_m, transit_400m and nearest_stop on each place as build_transport always did. Returns how many places changed.

    As in places_privacy.public_row(), a false flag is left out of the record, and a distance is cut (not rounded) to whole meters."""
    changed = 0
    for i, p in enumerate(places):
        if p.get("lat") is None:   # withheld from the map (places_privacy.py): keeps the transit_m and transit_400m of the last full build, and has no nearest_stop
            continue
        s = res.stops[int(res.any_idx[i])] if res.stops else None
        before = (p.get("transit_m"), p.get("transit_400m"), p.get("nearest_stop"))
        if s is None:
            for k in ("transit_m", "transit_400m", "nearest_stop"):
                p.pop(k, None)
        else:
            p["transit_m"] = int(res.any_m[i])
            if res.any_m[i] <= NEAR_M:
                p["transit_400m"] = True
            else:
                p.pop("transit_400m", None)
            p["nearest_stop"] = s.get("name") or s["kind"].replace("_", " ")
        changed += before != (p.get("transit_m"), p.get("transit_400m"), p.get("nearest_stop"))
    return changed


def _pct(k, n):
    return round(k / n * 100, 1) if n else None


def area_fields(places, res, area_of):
    """{area: counts} over the default basis. `area_of(place)` names the area or returns None."""
    out = {}
    for i, p in enumerate(places):
        if not in_basis(p):
            continue
        a = area_of(p)
        if a is None:
            continue
        c = out.setdefault(a, Counter())
        c["n"] += 1
        for k, v in res.flags(i).items():
            c[k] += v
        c["paper"] += bool(res.any_m[i] <= NEAR_M and res.ts_m[i] > NEAR_M)   # near only a stop with an expired timetable or no timetable
    return out


def stop_fields(stats, stops, res):
    """Per-municipality counts of stops by kind and by timetable state. Rebuilt from the stops on every run, so a nightly feed change cannot leave them behind."""
    by = {}
    for s in stops:
        by.setdefault(s.get("municipality"), []).append(s)
    for name, st in stats.items():
        mine = by.get(name, [])
        kinds = Counter(f["kind"] for f in mine)
        states = Counter(res.stop_state(f) for f in mine if f["kind"] in ANY_KINDS)
        st.update({
            "transit_stops": sum(kinds[k] for k in ANY_KINDS),
            "gtfs_stops": sum(1 for f in mine if f.get("source") in SCHEDULED_SOURCES),
            "bus_stations": kinds["bus_station"], "rail_stations": kinds["rail_station"], "ferry_terminals": kinds["ferry_terminal"],
            "airports": kinds["airport"], "public_airports": sum(1 for f in mine if f["kind"] == "airport" and f.get("public_use")),
            "taxi_stands": kinds["taxi"], "ev_charging": kinds["ev_charging"],
            "stops_current": states["current"], "stops_expired": states["expired"], "stops_osm": states["osm"],
        })


def municipality_fields(stats, places, res, stops, as_of):
    """Update each municipality's stop counts and access fields in place (the dict that becomes municipalities.json)."""
    stop_fields(stats, stops, res)
    counts = area_fields(places, res, lambda p: p.get("municipality"))
    for name, st in stats.items():
        c = counts.get(name, Counter())
        n = c["n"]
        st.update({
            "places_near_transit": int(c["any400"]), "transit_pct": _pct(c["any400"], n),
            "access_n": n, "access_as_of": as_of.isoformat(),
            "acc_cur400_pct": _pct(c["cur400"], n), "acc_cur800_pct": _pct(c["cur800"], n), "acc_freq400_pct": _pct(c["freq400"], n),
            "acc_sat400_pct": _pct(c["sat400"], n), "acc_sun400_pct": _pct(c["sun400"], n), "acc_hub400_pct": _pct(c["hub400"], n),
            "acc_paper_pct": _pct(c["paper"], n),
        })
        if res.tw_m is not None:
            st.update({"acc_walk400_pct": _pct(c["walk400"], n), "acc_walk800_pct": _pct(c["walk800"], n), "acc_wfreq400_pct": _pct(c["wfreq400"], n)})


def island_summary(places, res, operators, as_of):
    """The island-wide figures (meta.json: access), on the default basis."""
    c = area_fields(places, res, lambda p: "PR").get("PR", Counter())
    n = c["n"]
    ops = [o for o in operator_list(operators) if (o.get("feed") or {}).get("end")]
    walk = {} if res.tw_m is None else {
        "walk400_pct": _pct(c["walk400"], n), "walk800_pct": _pct(c["walk800"], n), "wfreq400_pct": _pct(c["wfreq400"], n),
        "walk": {"bound_m": WALK_BOUND_M, "network": "roads.bin without motorways (no footpaths)",
                 "places_straight": int(sum(1 for i in res.tw_straight.tolist() if in_basis(places[i]))), "stops_off_road": res.n_stops_off_road}}
    return {
        "as_of": as_of.isoformat(), "basis": BASIS_NOTE, "places": n, "near_m": NEAR_M, "far_m": FAR_M, "frequent_calls": FREQUENT_CALLS,
        "any400_pct": _pct(c["any400"], n), "cur400_pct": _pct(c["cur400"], n), "cur800_pct": _pct(c["cur800"], n), "freq400_pct": _pct(c["freq400"], n),
        "sat400_pct": _pct(c["sat400"], n), "sun400_pct": _pct(c["sun400"], n), "hub400_pct": _pct(c["hub400"], n), "paper_pct": _pct(c["paper"], n),
        "stops": {"current": res.n_current, "expired": res.n_expired, "osm": res.n_osm},
        "feeds": {"current": sum(feed_current(o, as_of) for o in ops), "expired": sum(not feed_current(o, as_of) for o in ops)},
        **walk,
    }


def columns_doc(res, built):
    """The per-place columns, in the order of places.json. `built` is meta.generated_at: the browser uses it to check that both files belong together."""
    doc = {"as_of": res.as_of.isoformat(), "built": built, "n": len(res.ts_m), "near_m": NEAR_M, "cap_m": CAP_M, "frequent_calls": FREQUENT_CALLS,
           "ts_m": res.ts_m.tolist(), "ts_calls": res.ts_calls.tolist(), "ts_we": res.ts_we.tolist()}
    if res.tw_m is not None:
        doc.update({"walk_bound_m": WALK_BOUND_M, "tw_m": res.tw_m.tolist(), "tw_calls": res.tw_calls.tolist(), "tw_we": res.tw_we.tolist(),
                    "tw_straight": res.tw_straight.tolist()})
    return doc


# ── The class a place falls in (the legend the map uses) ─────────────────────

def access_class(ts_m, ts_calls, transit_m, straight_m=None):
    """frequent / basic / near / detour / paper / none. The same rule is in js/access.js (accessClass), and takes the same published fields: a distance to the
    nearest current stop and its calls (the map passes the walking pair tw_m, tw_calls when place_access.json has them, else ts_m, ts_calls; both
    rounded up), and transit_m (the nearest mapped stop of any kind, straight line, cut to whole meters, so 800.x m reads 800 and is outside 800 m).
    With the walking pair, straight_m is ts_m: a current stop within 800 m in a straight line but more than 800 m on foot is a 'detour', not a place
    near only expired or unscheduled stops."""
    if ts_m <= NEAR_M:
        return "frequent" if ts_calls >= FREQUENT_CALLS else "basic"
    if ts_m <= FAR_M:
        return "near"
    if straight_m is not None and straight_m <= FAR_M:
        return "detour"
    return "paper" if transit_m < FAR_M else "none"


# ── Run against the published files ──────────────────────────────────────────

def _load(data_dir, name):
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def _dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _same(a, b):
    """Equal apart from the as-of dates, so a day that changes nothing writes nothing (the nightly job commits only real changes)."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("as_of", "access_as_of")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(a) == strip(b)


def apply_files(data_dir=DATA, as_of=None, write=True, log=print):
    """Recompute the access fields from the published places, stops and operators and write what changed. Returns the names of the files written."""
    as_of = as_of or date.today()
    places = _load(data_dir, "places.json")
    stops = _load(data_dir, "transport.json")
    operators = _load(data_dir, "operators.json")["operators"]
    stats = _load(data_dir, "municipalities.json")
    meta = _load(data_dir, "meta.json")
    import walknet
    try:
        prev_cols = _load(data_dir, "place_access.json")   # the withheld places keep their columns (compute())
    except FileNotFoundError:
        prev_cols = None
    res = compute(places, stops, operators, as_of, net=walknet.load(data_dir / "roads.bin"), prev=prev_cols)
    changed_legacy = legacy_fields(places, res)
    old_stats = json.loads(json.dumps(stats))
    municipality_fields(stats, places, res, stops, as_of)
    summary = island_summary(places, res, operators, as_of)
    if isinstance(meta.get("transport"), dict):   # the legacy island count the full build wrote
        meta["transport"]["places_near_transit"] = int(sum(1 for i, p in enumerate(places) if in_basis(p) and res.any_m[i] <= NEAR_M))
    import places_privacy
    cols = places_privacy.coarsen_columns(columns_doc(res, meta.get("generated_at")), places)   # the withheld places' distances stay coarse (decision 49)
    try:
        old_cols = _load(data_dir, "place_access.json")
    except FileNotFoundError:
        old_cols = {}
    written = []
    if changed_legacy:
        if write:
            _dump(data_dir / "places.json", places)
        written.append("places.json")
    if not (_same(old_stats, stats) and _same(meta.get("access"), summary) and _same(old_cols, cols)):
        if write:
            _dump(data_dir / "municipalities.json", stats)
            meta["access"] = summary
            _dump(data_dir / "meta.json", meta)
            _dump(data_dir / "place_access.json", cols)
        written += ["municipalities.json", "meta.json", "place_access.json"]
    log(f"access: {summary['places']:,} places on the default basis; within 400 m of a stop with a current timetable {summary['cur400_pct']}% "
        f"(walking along mapped roads {summary.get('walk400_pct', 'not measured: no roads.bin')}%), "
        f"frequent {summary['freq400_pct']}%, any mapped stop {summary['any400_pct']}%; {changed_legacy:,} places had a stale transit field; "
        + (("wrote " + ", ".join(written)) if written else "nothing to write"))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 when the published files are out of date")
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: today)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    written = apply_files(as_of=date.fromisoformat(args.as_of) if args.as_of else None, write=not args.check)
    return 1 if (args.check and written) else 0


if __name__ == "__main__":
    sys.exit(main())
