"""Append the key timings of the current run to timing_history.json (the report quotes the range over all runs).
The first three entries were read from the console output of earlier runs of the same scripts (seeded by hand, marked as such).
"""
from common import *
import datetime

SEED = [
    {"run": "earlier run 1 (scripts run one by one)", "seeded": True, "island_search_s": 3.6, "graph_load_s": 12.1, "island_end_to_end_s": 17.7, "pbf_read_s": 45.6, "tier1_total_s": 5.3, "drive_graph_s": 12.1},
    {"run": "earlier run 2 (run_all.py)", "seeded": True, "island_search_s": 1.6, "graph_load_s": 6.0, "island_end_to_end_s": 8.5, "pbf_read_s": 17.9, "tier1_total_s": None, "drive_graph_s": 7.3},
    {"run": "earlier run 3 (run_all.py, busy machine)", "seeded": True, "island_search_s": 4.5, "graph_load_s": 18.5, "island_end_to_end_s": 25.6, "pbf_read_s": 60.9, "tier1_total_s": 14.5, "drive_graph_s": 22.6},
]
p = HERE / "timing_history.json"
hist = json.loads(p.read_text(encoding="utf-8")) if p.exists() else list(SEED)
q2, q2b, q1, q4 = read_json("q2_walk.json"), read_json("q2b_osm_inventory.json"), read_json("q1_baseline.json"), read_json("q4_journey.json")
rec = {"run": datetime.datetime.now().strftime("run_all.py %Y-%m-%d %H:%M"), "seeded": False,
       "island_search_s": q2["full_run_s"], "graph_load_s": q2["graph_build_s"],
       "island_end_to_end_s": round(q2["graph_build_s"] + q2["stop_snap_s"] + q2["place_snap_s"] + q2["place_registry_s"] + q2["full_run_s"], 1),
       "pbf_read_s": q2b["read_pbf_seconds"], "tier1_total_s": q1["timing_s"]["total"], "drive_graph_s": q4["drive_dijkstra_s"]}
same = [h for h in hist if not h.get("seeded") and all(h[k] == rec[k] for k in rec if k != "run")]
if not same:
    hist.append(rec)
p.write_text(json.dumps(hist, indent=1), encoding="utf-8")
print(len(hist), "runs recorded")
