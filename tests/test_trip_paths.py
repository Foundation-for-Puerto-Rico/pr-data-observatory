"""The timetable replay follows the route lines (trip_paths.py): stops land on the line in travel order, stop times are kept, a loop is
traveled rather than skipped, and a trip that fits no line keeps its straight stop-to-stop path."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import trip_paths as tp  # noqa: E402

# an L-shaped road: 0.01° east (about 1.06 km), then 0.01° north (about 1.1 km)
L_LINE = [[-66.10, 18.40], [-66.09, 18.40], [-66.09, 18.41]]
LOOP = [[-66.10, 18.40], [-66.09, 18.40], [-66.09, 18.41], [-66.10, 18.41], [-66.10, 18.40]]


def route(name, lines):
    return {"properties": {"operator": "op", "short_name": name}, "geometry": {"type": "MultiLineString", "coordinates": lines}}


def trip(name, stops):
    return {"r": name, "m": "bus", "o": "op", "p": [[lng, lat, t] for lng, lat, t in stops]}


def expand(doc, t):   # the same rule as tripPoints() in site/js/common.js
    path, out = doc["paths"][t["k"]], []
    for j in range(len(t["s"]) - 1):
        a, b, t0, t1 = t["s"][j], t["s"][j + 1], t["t"][j], t["t"][j + 1]; m0, m1 = path[a][2], path[b][2]
        if j == 0:
            out.append([path[a][0], path[a][1], t0])
        if a == b:
            out.append([path[b][0], path[b][1], t1]); continue
        for i in range(a + 1, b + 1):
            out.append([path[i][0], path[i][1], t1 if i == b else t0 if m1 == m0 else t0 + (t1 - t0) * (path[i][2] - m0) / (m1 - m0)])
    return out


class TripPaths(unittest.TestCase):
    def run_one(self, routes, trips):
        days = {"wk": trips}
        paths = tp.follow_routes(routes, days)
        return tp.trip_doc("weekday", trips, paths["wk"])

    def test_two_stops_follow_the_corner(self):
        doc = self.run_one([route("A", [L_LINE])], [trip("A", [(-66.10, 18.40, 100), (-66.09, 18.41, 400)])])
        t = doc["trips"][0]
        self.assertEqual(doc["path_kind"][t["k"]], "line")
        pts = expand(doc, t)
        self.assertTrue(any(abs(p[0] + 66.09) < 1e-4 and abs(p[1] - 18.40) < 1e-4 for p in pts), "the path turns at the corner")
        self.assertEqual((pts[0][2], pts[-1][2]), (100, 400))
        corner = next(p for p in pts if abs(p[0] + 66.09) < 1e-4 and abs(p[1] - 18.40) < 1e-4)
        self.assertAlmostEqual(corner[2], 100 + 300 * 1057 / (1057 + 1105), delta=5, msg="time spread by distance along the road")

    def test_stop_times_are_kept_and_in_order(self):
        stops = [(-66.10, 18.40, 0), (-66.095, 18.4001, 60), (-66.09, 18.405, 180), (-66.0901, 18.41, 300)]
        doc = self.run_one([route("A", [L_LINE])], [trip("A", stops)])
        t = doc["trips"][0]
        self.assertEqual(t["t"], [0, 60, 180, 300])
        pts = expand(doc, t)
        self.assertEqual([pts[i][2] for i in [0] + [len(pts) - 1]], [0, 300])
        self.assertTrue(all(b[2] >= a[2] for a, b in zip(pts, pts[1:])))
        self.assertEqual(len(t["s"]), 4)
        for (lng, lat, _), i in zip(stops, t["s"]):   # each stop sits on the line next to where it is
            self.assertLess(tp._dist([lng, lat], doc["paths"][t["k"]][i]), 20)

    def test_a_loop_is_travelled_not_skipped(self):
        # a circulator that lists only its terminal, at the start and 30 minutes later
        doc = self.run_one([route("C", [LOOP])], [trip("C", [(-66.10, 18.40, 0), (-66.10, 18.40, 1800)])])
        t = doc["trips"][0]
        path = doc["paths"][t["k"]]
        self.assertGreater(path[t["s"][-1]][2], 4000, "the vehicle goes round the 4.3 km loop")

    def test_no_fitting_line_keeps_straight_legs(self):
        far = [(-66.30, 18.20, 0), (-66.31, 18.21, 600)]   # 20 km from the route's line
        doc = self.run_one([route("A", [L_LINE])], [trip("A", far)])
        t = doc["trips"][0]
        self.assertEqual(doc["path_kind"][t["k"]], "stops")
        self.assertEqual([p[:2] for p in doc["paths"][t["k"]]], [[-66.3, 18.2], [-66.31, 18.21]])
        self.assertEqual(t["t"], [0, 600])

    def test_trips_with_the_same_stops_share_a_path(self):
        a = trip("A", [(-66.10, 18.40, 100), (-66.09, 18.41, 400)]); b = trip("A", [(-66.10, 18.40, 1000), (-66.09, 18.41, 1300)])
        doc = self.run_one([route("A", [L_LINE])], [a, b])
        self.assertEqual(len(doc["paths"]), 1)
        self.assertEqual(doc["trips"][0]["k"], doc["trips"][1]["k"])
        self.assertEqual(doc["trips"][1]["t"], [1000, 1300])

    def test_published_files_are_format_2(self):
        data = ROOT / "site" / "data"
        for f in ("trips.json", "trips_sa.json", "trips_su.json"):
            doc = json.loads((data / f).read_text(encoding="utf-8"))
            self.assertEqual(doc.get("format"), 2, f)
            self.assertEqual(len(doc["paths"]), len(doc["path_kind"]), f)
            for t in doc["trips"]:
                self.assertEqual(len(t["s"]), len(t["t"]))
                self.assertTrue(0 <= t["k"] < len(doc["paths"]))
                self.assertTrue(all(0 <= i < len(doc["paths"][t["k"]]) for i in t["s"]))


if __name__ == "__main__":
    unittest.main()
