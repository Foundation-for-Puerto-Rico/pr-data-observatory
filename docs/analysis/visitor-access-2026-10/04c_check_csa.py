"""Q4 check: verify the connection scan against a brute-force computation for 1 and 2 boardings, and see which operators the scan reaches."""
from csa import *
from service import *

d = Data()
T = d.transport
expired_ops = {o for o, s in d.op_status.items() if s == "expired"}
trips = jload("trips.json")["trips"]
tt = Timetable(trips, expired_ops)
sju = next(f for f in T if f.get("code") == "SJU")
sx, sy = to_xy(sju["lng"], sju["lat"])
t0 = 10 * 3600
dd = np.hypot(tt.x - sx, tt.y - sy)
acc = {int(i): t0 + float(dd[i]) / WALK_MS for i in np.nonzero(dd <= 500)[0]}
vb, vr, av = tt.scan(acc, t0, max_boardings=3)

# brute force: trips as lists of (node, time)
cur_trips = [t for t in trips if t["o"] not in expired_ops]
tr = []
for t in cur_trips:
    seq = []
    for lng, lat, s in t["p"]:
        if (lng, lat) in tt.node:
            seq.append((tt.node[(lng, lat)], s))
    tr.append(seq)
# per node: list of (trip index, position)
by_node = defaultdict(list)
for ti, seq in enumerate(tr):
    for pos, (n, s) in enumerate(seq):
        by_node[n].append((ti, pos))

def ride_from(avail, buffer):
    """avail: dict node -> time available; returns dict node -> earliest vehicle arrival after boarding anywhere."""
    out = {}
    for n, tavail in avail.items():
        for ti, pos in by_node.get(n, ()):
            seq = tr[ti]
            if seq[pos][1] >= tavail + buffer:
                for q in range(pos + 1, len(seq)):
                    m, s = seq[q]
                    if m == n:
                        continue
                    if s < out.get(m, INF):
                        out[m] = s
    return out

def relax_walk(veh, base):
    av = dict(base)
    for s, v in veh.items():
        if v < av.get(s, INF):
            av[s] = v
        for s2, wt in tt.walk[s]:
            if v + wt < av.get(s2, INF):
                av[s2] = v + wt
    return av

# round 1
veh1 = ride_from(acc, 0)
av1 = relax_walk(veh1, acc)
veh2 = ride_from(av1, BUFFER_S)
av2 = relax_walk(veh2, av1)
veh3 = ride_from(av2, BUFFER_S)
best = {}
for v in (veh1, veh2, veh3):
    for s, t_ in v.items():
        if t_ < best.get(s, INF):
            best[s] = t_
mism = 0
for s in range(tt.n):
    a = vb[s] if vb[s] < INF else None
    b = best.get(s)
    if a != b:
        mism += 1
print("stops", tt.n, "reached (scan)", sum(1 for v in vb if v < INF), "reached (brute force)", len(best), "mismatching stops", mism)

# which operators' stops are reached (scan on all feeds)
tt_all = Timetable(trips)
dd2 = np.hypot(tt_all.x - sx, tt_all.y - sy)
acc2 = {int(i): t0 + float(dd2[i]) / WALK_MS for i in np.nonzero(dd2 <= 500)[0]}
vb2, vr2, av2_ = tt_all.scan(acc2, t0)
node_ops = defaultdict(set)
for dep, tid, seq, arr, a, b in tt_all.conns:
    op = tt_all.trip_op[tid]
    node_ops[a].add(op); node_ops[b].add(op)
reached_by_op = Counter()
for s in range(tt_all.n):
    if vb2[s] < INF:
        for op in node_ops[s]:
            reached_by_op[op] += 1
tot_by_op = Counter()
for s in range(tt_all.n):
    for op in node_ops[s]:
        tot_by_op[op] += 1
print("operators reached with all feeds (stops reached / stops with calls):")
for op, n in tot_by_op.most_common():
    print(f"  {op:14} {reached_by_op.get(op, 0):5} / {n:5}   status={d.op_status.get(op)}")
# node set equality between current and all
print("reached stops: current-only", sum(1 for v in vb if v < INF), "all feeds", sum(1 for v in vb2 if v < INF))

write_json("q4c_check.json", {"stops_with_calls_current_feeds": tt.n, "stops_reached_scan": int(sum(1 for v in vb if v < INF)), "stops_reached_brute_force": len(best), "mismatching_stops": mism,
                              "operators_reached_all_feeds": {op: {"reached": int(reached_by_op.get(op, 0)), "stops_with_calls": int(n), "feed_status": d.op_status.get(op)} for op, n in tot_by_op.most_common()},
                              "stops_reached_current_only": int(sum(1 for v in vb if v < INF)), "stops_reached_all_feeds": int(sum(1 for v in vb2 if v < INF))})
