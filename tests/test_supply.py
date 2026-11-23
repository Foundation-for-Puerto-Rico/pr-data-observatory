"""Transit supply (supply.py): trips per hour, waits per period, departures by stop (the last stop is an arrival), the longest gap,
route totals, the island counts by hour, and the current / expired flag."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import supply  # noqa: E402

H = 3600


def doc():
    # one route "A" (operator "op") with two stop patterns: k=0 three stops, k=1 the reverse; one route "B" of an expired operator
    paths = [[[-66.1, 18.4, 0], [-66.09, 18.4, 1000], [-66.08, 18.4, 2000]],
             [[-66.08, 18.4, 0], [-66.09, 18.4, 1000], [-66.1, 18.4, 2000]],
             [[-66.2, 18.3, 0], [-66.19, 18.3, 3000]]]
    trips = [
        {"r": "A", "m": "bus", "o": "op", "k": 0, "s": [0, 1, 2], "t": [6 * H, 6 * H + 300, 6 * H + 600]},
        {"r": "A", "m": "bus", "o": "op", "k": 0, "s": [0, 1, 2], "t": [6 * H + 1800, 6 * H + 2100, 6 * H + 2400]},
        {"r": "A", "m": "bus", "o": "op", "k": 0, "s": [0, 1, 2], "t": [12 * H, 12 * H + 300, 12 * H + 600]},
        {"r": "A", "m": "bus", "o": "op", "k": 1, "s": [0, 1, 2], "t": [7 * H, 7 * H + 300, 7 * H + 600]},
        {"r": "B", "m": "bus", "o": "old", "k": 2, "s": [0, 1], "t": [8 * H, 8 * H + 900]},
    ]
    return {"format": 2, "paths": paths, "path_kind": ["line", "line", "stops"], "trips": trips,
            "path_stops": [["gtfs:op:1", "gtfs:op:2", "gtfs:op:3"], ["gtfs:op:3", "gtfs:op:2", "gtfs:op:1"], ["gtfs:old:9", "gtfs:old:8"]]}


class Supply(unittest.TestCase):
    def setUp(self):
        self.d = supply.day_supply(doc(), {"op": "current", "old": "expired"})

    def test_patterns(self):
        p0 = next(p for p in self.d["patterns"] if p["k"] == 0)
        self.assertEqual(p0["trips"], 3)
        self.assertEqual(p0["hours"][6], 2); self.assertEqual(p0["hours"][12], 1)
        self.assertEqual((p0["first"], p0["last"]), (6 * H, 12 * H))
        self.assertEqual(p0["periods"]["am"], {"n": 2, "hw": 90})       # 06:00-09:00: 180 minutes / 2 trips
        self.assertEqual(p0["periods"]["mid"], {"n": 1, "hw": 360})
        self.assertEqual(p0["periods"]["eve"], {"n": 0, "hw": None})
        self.assertEqual(p0["km"], 2.0); self.assertEqual(p0["run_min"], 10.0); self.assertEqual(p0["kmh"], 12.0)
        self.assertTrue(p0["cur"] and p0["line"])

    def test_routes_sum_both_directions(self):
        a = next(r for r in self.d["routes"] if r["r"] == "A")
        self.assertEqual(a["trips"], 4)
        self.assertEqual(sorted(a["patterns"]), [0, 1])
        self.assertEqual(a["hours"][6] + a["hours"][7] + a["hours"][12], 4)
        self.assertEqual(a["peak_hw"], 90)                               # the busier direction at the morning peak
        self.assertFalse(next(r for r in self.d["routes"] if r["r"] == "B")["cur"])

    def test_stops_count_departures_not_last_arrivals(self):
        st = self.d["stops"]
        self.assertEqual(st["gtfs:op:1"]["n"], 3)                        # departs on k=0 three times; is the last stop of k=1
        self.assertEqual(st["gtfs:op:3"]["n"], 1)                        # the last stop of k=0, the first of k=1
        self.assertEqual(st["gtfs:op:2"]["n"], 4)
        self.assertNotIn("gtfs:old:8", st)                               # only ever an arrival
        self.assertEqual(st["gtfs:op:1"]["routes"], ["A"])

    def test_longest_gap(self):
        # stop 1 departs at 06:00, 06:30 and 12:00: the longest wait between 06:00 and 22:00 is 12:00 -> 22:00
        self.assertEqual(self.d["stops"]["gtfs:op:1"]["gap"], 600)
        self.assertIsNone(supply._longest_gap([5 * H]))

    def test_island_counts_only_current(self):
        isl = self.d["island"]
        self.assertEqual(isl["vehicles"][6], 2)
        self.assertEqual(isl["vehicles"][8], 0)                          # route B is expired
        self.assertEqual(isl["routes"][7], 1)

    def test_published_file(self):
        p = ROOT / "site" / "data" / "transit_supply.json"
        if not p.exists():
            self.skipTest("no transit_supply.json")
        d = json.loads(p.read_text(encoding="utf-8"))
        trips = json.loads((ROOT / "site" / "data" / "trips.json").read_text(encoding="utf-8"))
        wk = d["days"]["wk"]
        self.assertEqual(len(wk["patterns"]), len({t["k"] for t in trips["trips"]}))
        self.assertEqual(sum(p["trips"] for p in wk["patterns"]), len(trips["trips"]))
        self.assertEqual(wk["trips_without_stop_ids"], 0)
        for r in wk["routes"]:
            self.assertEqual(len(r["hours"]), 24)


if __name__ == "__main__":
    unittest.main()
