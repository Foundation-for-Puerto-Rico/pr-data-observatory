"""Run every analysis script in order and record wall-clock time per script (timings.json). Logs go to logs/.
Usage (from this folder):  <repo>/venv/Scripts/python.exe run_all.py
Reads the repository (read only); writes only into this folder.
"""
import subprocess
import sys
import time
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
(HERE / "logs").mkdir(exist_ok=True)
ORDER = [
    "01_baseline.py", "01b_stale_check.py", "01c_bruteforce_check.py", "07b_location_sensitivity.py",
    "02_walk.py", "02b_osm_walk_ways.py", "02c_walk_osm_compare.py", "02d_muni_graph_diff.py",
    "03_gateways.py", "03b_east_and_osm.py",
    "04_journey.py", "04c_check_csa.py",
    "05_problems.py", "06_design_numbers.py", "07_extra_and_tables.py", "record_history.py", "make_report.py", "99_privacy_scan.py",
]
timings = {}
for s in ORDER:
    if not (HERE / s).exists():
        continue
    t = time.time()
    with open(HERE / "logs" / (s + ".txt"), "w", encoding="utf-8", errors="replace") as log:
        p = subprocess.run([sys.executable, str(HERE / s)], cwd=str(HERE), stdout=log, stderr=subprocess.STDOUT)
    timings[s] = {"seconds": round(time.time() - t, 1), "exit_code": p.returncode}
    print(s, timings[s], flush=True)
with open(HERE / "timings.json", "w", encoding="utf-8") as f:
    json.dump(timings, f, indent=1)
