"""Connection-scan / RAPTOR-style earliest-arrival prototype on the twin's published weekday timetable (trips.json).

The trip file has no stop IDs, trip IDs or route patterns: each trip is {r, m, o, p=[[lng, lat, seconds], ...]}. A stop is therefore a coordinate
(lng, lat, rounded to 5 decimals as written by network.py); two stops with identical coordinates are one stop. A call without a time in the
feed is not in the file, so intermediate stops of routes that publish only timepoints are missing.

Rules (from the brief): departure at t0, at most 3 boardings (2 transfers), walking links up to 400 m straight line at 4.8 km/h,
transfer buffer 180 s on every boarding after the first.
"""
from common import *
import heapq

WALK_MS = 4800 / 3600.0
BUFFER_S = 180
WALK_LINK_M = 400.0
INF = 10 ** 9


class Timetable:
    def __init__(self, trips, exclude_ops=frozenset()):
        self.node = {}
        self.conns = []
        self.bad = 0
        self.n_trips = 0
        self.trip_op = []
        used = 0
        for ti, t in enumerate(trips):
            if t["o"] in exclude_ops:
                continue
            used += 1
            self.trip_op.append(t["o"])
            tid = used - 1
            p = t["p"]
            for i in range(len(p) - 1):
                a, b = p[i], p[i + 1]
                if (a[0], a[1]) == (b[0], b[1]):
                    continue
                if b[2] < a[2]:
                    self.bad += 1
                    continue
                ia = self.node.setdefault((a[0], a[1]), len(self.node))
                ib = self.node.setdefault((b[0], b[1]), len(self.node))
                self.conns.append((a[2], tid, i, b[2], ia, ib))
        self.n_trips = used
        self.conns.sort()          # (dep, trip, seq) keeps the order inside a trip
        self.n = len(self.node)
        lng = np.empty(self.n)
        lat = np.empty(self.n)
        for (lo, la), k in self.node.items():
            lng[k], lat[k] = lo, la
        self.lng, self.lat = lng, lat
        self.x, self.y = to_xy(lng, lat)
        # walking links between stops within 400 m
        tree = STRtree(points(self.x, self.y))
        i, j = tree.query(points(self.x, self.y), predicate="dwithin", distance=WALK_LINK_M)
        self.walk = [[] for _ in range(self.n)]
        for a, b in zip(i.tolist(), j.tolist()):
            if a != b:
                self.walk[a].append((b, math.hypot(self.x[a] - self.x[b], self.y[a] - self.y[b]) / WALK_MS))

    def scan(self, access, t0, max_boardings=3, horizon_s=4 * 3600, buffer_s=BUFFER_S):
        """access: {stop index: arrival time at that stop (seconds after midnight)}.
        Returns (veh, avail_by_round): veh[k][s] earliest arrival at s BY VEHICLE using exactly <=k boardings (k = 1..max);
        avail[s] earliest time at s by any means (vehicle, walking transfer) with <= max boardings."""
        avail = [INF] * self.n
        for s, t in access.items():
            avail[s] = t
        horizon = t0 + horizon_s
        veh_best = [INF] * self.n        # earliest vehicle arrival over all rounds
        veh_round = [0] * self.n         # round (boardings) at which veh_best was first achieved
        veh_by_round = []
        for k in range(1, max_boardings + 1):
            veh = [INF] * self.n
            boarded = set()
            extra = buffer_s if k > 1 else 0
            for dep, tid, seq, arr, a, b in self.conns:
                if dep > horizon:
                    break
                if tid in boarded:
                    if arr < veh[b]:
                        veh[b] = arr
                    continue
                if avail[a] + extra <= dep:
                    boarded.add(tid)
                    if arr < veh[b]:
                        veh[b] = arr
            new_avail = avail[:]
            for s in range(self.n):
                v = veh[s]
                if v < INF:
                    if v < veh_best[s]:
                        veh_best[s] = v
                        veh_round[s] = k
                    if v < new_avail[s]:
                        new_avail[s] = v
                    for s2, wt in self.walk[s]:
                        if v + wt < new_avail[s2]:
                            new_avail[s2] = v + wt
            avail = new_avail
            veh_by_round.append(veh)
        return veh_best, veh_round, avail


def trips_for(day_file, exclude_status, d):
    trips = jload(day_file)["trips"]
    return trips
