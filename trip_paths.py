"""Make the timetable replay follow the route lines instead of jumping between stops in straight lines.

A GTFS trip is a list of stops with times. The replay (trips*.json: the 3D view and the 2D "vehicles now" layer) used to move a vehicle
in a straight line from one stop to the next, across buildings and hills, even though every route line already follows the roads (the
operator's own shape, or the road network that network.snap_routes snaps to). This module walks each trip along its route's line:

  1. place every stop of the trip on one line of its route (a route can have several: directions and variants), in travel order;
  2. keep the part of the line between the first and the last stop, simplified to about 5 m;
  3. spread the time between two stops along that part in proportion to distance (done by the page, from the stop times).

Trips that stop at the same places in the same order share one path (a stop pattern: one variant of a route), so the file stores each
path once. trips*.json, format 2:

  "paths":     [[[lng, lat, metres from the start], ...], ...]   one per stop pattern
  "path_kind": ["line" | "stops", ...]   "line" follows the route line; "stops" joins the stops in straight lines (no line fitted)
  "path_stops": [["gtfs:<operator>:<stop_id>", ...], ...]   the stop of each "s" position, per pattern (the ids of transport.json)
  "trips":     [{"r": route, "m": mode, "o": operator, "k": path index, "s": [path index of each stop], "t": [seconds after midnight at each stop]}]

common.js tripPoints() turns a trip back into [lng, lat, seconds] points. The stop indices and times keep the timetable intact for
analysis by stop and by pattern (frequency, span, transfers, and ridership when a source exists).

Pure Python, no dependencies: network.build_network calls follow_routes(); refresh_network.py and build.py write trip_doc();
`python trip_paths.py` rewrites the published files in site/data (it reads format 1 or 2).
"""
import json
import math
import sys
from pathlib import Path

LAT0 = 18.2                                        # Puerto Rico: a local flat projection is accurate to well under 1% here
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110540
TOL = 250                                          # metres: a stop farther than this from every part of a line is not on that line
SIMPLIFY = 5                                       # metres: Douglas-Peucker tolerance for the path between two stops
AHEAD = 0.05                                       # cost per metre of skipping ahead along the line, so a loop that passes the stop again later loses
MAX_SPEED = 35                                     # m/s (126 km/h): faster than any bus, train or ferry here
MIN_SPEED = 0.5                                    # m/s: slower than this over three minutes or more means the vehicle is not where we placed it
FORMAT = 2


def _xy(p):
    return ((p[0] + 66.5) * KX, (p[1] - LAT0) * KY)


def _dist(a, b):
    (ax, ay), (bx, by) = _xy(a), _xy(b)
    return math.hypot(bx - ax, by - ay)


class _Line:
    """One polyline of a route, in metres, with the distance along it at each vertex."""
    def __init__(self, coords):
        self.ll = [c[:2] for c in coords]
        self.xy = [_xy(c) for c in self.ll]
        self.cum = [0.0]
        for a, b in zip(self.xy, self.xy[1:]):
            self.cum.append(self.cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))

    def candidates(self, p):
        """(distance to the line, position along it) of the nearest point of every segment within TOL."""
        x, y = _xy(p); out = []
        for i, (a, b) in enumerate(zip(self.xy, self.xy[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
            f = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
            d = math.hypot(x - (a[0] + f * dx), y - (a[1] + f * dy))
            if d <= TOL:
                out.append((d, self.cum[i] + f * (self.cum[i + 1] - self.cum[i])))
        return out

    def point_at(self, pos):
        """[lng, lat] at a distance along the line, and the vertex before it."""
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.cum[mid] <= pos: lo = mid
            else: hi = mid
        seg = self.cum[hi] - self.cum[lo]; f = 0.0 if seg == 0 else (pos - self.cum[lo]) / seg
        a, b = self.ll[lo], self.ll[hi]
        return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])], lo

    def place(self, stops):
        """Positions along the line for each stop ([lng, lat, seconds]), in travel order, and the total cost; None when the stops do not fit.

        The time between stops decides between passes of a loop: a circulator that lists only its terminal at the start and at the end
        must go round the loop in that time, not stand still. A leg is refused only when the line is both far longer than the straight
        distance and would need an impossible speed (some feeds time a stop 1 second after the last one, so speed alone is not enough)."""
        pos, cost, prev = [], 0.0, None
        for k, s in enumerate(stops):
            dt = None if k == 0 else s[2] - stops[k - 1][2]
            straight = 0.0 if k == 0 else _dist(s, stops[k - 1])
            best = None
            for d, at in self.candidates(s):
                if k == 0:
                    c = d + 0.01 * at                              # the first stop: nearest, and early on the line
                else:
                    run = at - prev
                    if run < -1:                                   # going backwards along the line
                        continue
                    if run > 3 * straight + 1500 and dt is not None and run > MAX_SPEED * max(dt, 1):
                        continue                                   # a far longer trip than the stops make, at an impossible speed: wrong pass
                    c = d + AHEAD * max(run, 0)
                    if dt is not None and dt >= 180 and run < MIN_SPEED * dt:
                        c += 1000                                  # minutes on the timetable and nearly no distance: the vehicle goes round, take the later pass
                if best is None or c < best[0]:
                    best = (c, at, d)
            if best is None:
                return None
            pos.append(max(best[1], prev if prev is not None else best[1])); cost += best[2]; prev = pos[-1]
        return pos, cost

    def path(self, pos):
        """The line from the first to the last stop position: (points [lng, lat], index of each stop among them)."""
        pts, idx = [], []
        for k, (a, b) in enumerate(zip(pos, pos[1:])):
            pa, ia = self.point_at(a); pb, ib = self.point_at(b)
            leg = _simplify([pa] + [self.ll[i] for i in range(ia + 1, ib + 1) if a < self.cum[i] < b] + [pb])
            if k == 0:
                idx.append(0); pts.append(leg[0])
            pts += leg[1:]; idx.append(len(pts) - 1)
        if len(pos) == 1:
            pts, idx = [self.point_at(pos[0])[0]], [0]
        return pts, idx


def _simplify(pts):
    """Douglas-Peucker in metres; keeps the ends."""
    if len(pts) < 3:
        return pts
    xy = [_xy(p) for p in pts]
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = xy[i], xy[j]; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
        far, k = -1.0, None
        for m in range(i + 1, j):
            x, y = xy[m]
            d = math.hypot(x - ax, y - ay) if L == 0 else abs(dy * x - dx * y + bx * ay - by * ax) / L
            if d > far:
                far, k = d, m
        if k is not None and far > SIMPLIFY:
            keep[k] = True; stack += [(i, k), (k, j)]
    return [p for p, f in zip(pts, keep) if f]


def _route_key(props):
    return (props.get("operator"), props.get("short_name") or props.get("long_name") or "")


def _lines_by_route(routes):
    out = {}
    for f in routes:
        g = f.get("geometry") or {}
        lines = g.get("coordinates") if g.get("type") == "MultiLineString" else [g.get("coordinates")] if g.get("type") == "LineString" else []
        out.setdefault(_route_key(f.get("properties") or {}), []).extend(_Line(c) for c in lines if c and len(c) > 1)
    return out


def _with_metres(pts):
    out, run = [], 0.0
    for i, p in enumerate(pts):
        if i:
            run += _dist(pts[i - 1], p)
        out.append([round(p[0], 5), round(p[1], 5), round(run)])
    return out


def stops_of(trip, paths=None):
    """The stops of a trip as [lng, lat, seconds], from format 1 ("p") or format 2 ("k", "s", "t" with its file's paths)."""
    if "t" in trip and paths is not None:
        path = paths[trip["k"]]
        return [[path[i][0], path[i][1], sec] for i, sec in zip(trip["s"], trip["t"])]
    if "s" in trip:
        return [trip["p"][i] for i in trip["s"]]
    return trip["p"]


def follow_routes(routes, trips_by_day, paths_by_day=None, stops_by_day=None):
    """Turn each day's trips into format 2 along the route lines. trips_by_day: {"wk": [trip, ...], ...} with format 1 trips (or format 2,
    with paths_by_day and stops_by_day giving their paths and path_stops). A format 1 trip may carry "_sid", its stop ids (network.py).
    Rewrites the trips in place and returns {day: {"paths": [...], "path_kind": [...], "path_stops": [...]}}."""
    lines = _lines_by_route(routes)
    fitted = {}          # one placement per stop pattern: most trips of a route repeat a few patterns
    out, n = {}, {"trips": 0, "line": 0, "stops": 0, "patterns": 0, "points": 0}
    for day, trips in trips_by_day.items():
        paths, kinds, pstops, index = [], [], [], {}
        old_stops = (stops_by_day or {}).get(day)
        for t in trips:
            sids = t.pop("_sid", None) or (old_stops[t["k"]] if old_stops and "k" in t else None)
            stops = stops_of(t, (paths_by_day or {}).get(day))
            key = (t.get("o"), t.get("r"), tuple((round(s[0], 5), round(s[1], 5)) for s in stops))
            if key not in fitted:
                best = None
                for ln in lines.get((t.get("o"), t.get("r")), []):
                    r = ln.place(stops)
                    if r and (best is None or r[1] < best[2]):
                        best = (ln, r[0], r[1])
                fitted[key] = ("line", *best[0].path(best[1])) if best else ("stops", [s[:2] for s in stops], list(range(len(stops))))
            kind, pts, idx = fitted[key]
            if key not in index:
                index[key] = len(paths); paths.append(_with_metres(pts)); kinds.append(kind); pstops.append(sids if sids and len(sids) == len(stops) else None)
                n["patterns"] += 1; n["points"] += len(pts)
            for f in ("p", "k", "s", "t"):
                t.pop(f, None)
            t["k"], t["s"], t["t"] = index[key], idx, [int(round(s[2])) for s in stops]
            n["trips"] += 1; n[kind] += 1
        out[day] = {"paths": paths, "path_kind": kinds, "path_stops": pstops}
    print(f"  replay: {n['line']:,} of {n['trips']:,} trips follow their route line, {n['stops']:,} keep straight stop-to-stop legs; "
          f"{n['patterns']:,} stop patterns, {n['points']:,} path points")
    return out


def trip_doc(label, trips, paths):
    """The content of trips.json / trips_sa.json / trips_su.json."""
    doc = {"day": label, "format": FORMAT, "paths": paths["paths"], "path_kind": paths["path_kind"], "trips": trips}
    if any(paths.get("path_stops") or []):
        doc["path_stops"] = paths["path_stops"]
    return doc


def main(argv):
    """Rewrite the published files in site/data (the nightly refresh and build.py do this themselves)."""
    data = Path(__file__).resolve().parent / "site" / "data"
    routes = json.loads((data / "transit_routes.geojson").read_text(encoding="utf-8"))["features"]
    files = {"wk": "trips.json", "sa": "trips_sa.json", "su": "trips_su.json"}
    docs = {d: json.loads((data / f).read_text(encoding="utf-8")) for d, f in files.items() if (data / f).exists()}
    if all(doc.get("format") == FORMAT for doc in docs.values()) and "--force" not in argv:
        print("  the trips files are already format 2 (paths along the route lines); --force re-fits them from their stops")
        return 0
    paths = follow_routes(routes, {d: doc["trips"] for d, doc in docs.items()}, {d: doc.get("paths") for d, doc in docs.items()}, {d: doc.get("path_stops") for d, doc in docs.items()})
    if "--check" not in argv:
        for d, doc in docs.items():
            (data / files[d]).write_text(json.dumps(trip_doc(doc["day"], doc["trips"], paths[d]), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"  wrote {files[d]} {(data / files[d]).stat().st_size / 1048576:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
