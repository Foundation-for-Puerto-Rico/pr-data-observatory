"""Tests for the phase 5 analysis of the transit plan (docs/analysis/transit-needs-2026-11/transit_needs.py). No network."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("transit_needs", ROOT / "docs" / "analysis" / "transit-needs-2026-11" / "transit_needs.py")
tn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tn)

LAT = 18.4


def lon_at(m):   # a longitude m metres east of -66.0 at the test latitude
    return -66.0 + m / tn.KX


class Parts(unittest.TestCase):
    def test_percentiles_share_ties_and_keep_gaps(self):
        self.assertEqual(tn.pct_rank([10, 20, 20, None, 30]), [0.0, 50.0, 50.0, None, 100.0])
        self.assertEqual(tn.pct_rank([None, 5]), [None, 50.0])

    def test_a_point_in_a_hole_is_outside(self):
        outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
        hole = [(4, 4), (6, 4), (6, 6), (4, 6)]
        self.assertTrue(tn.in_polygon(2, 2, [outer, hole]))
        self.assertFalse(tn.in_polygon(5, 5, [outer, hole]))
        self.assertFalse(tn.in_polygon(12, 5, [outer, hole]))

    def test_the_grid_finds_what_is_within_the_distance(self):
        g = tn.Grid(400)
        g.add((0, 0), "a"); g.add((399, 0), "b"); g.add((401, 0), "c")
        self.assertEqual(sorted(i for _, i in g.near((0, 0), 400)), ["a", "b"])

    def test_a_line_is_sampled_at_most_the_step_apart(self):
        pts = tn.sample_line([(lon_at(0), LAT), (lon_at(1000), LAT)], 100)
        self.assertEqual(len(pts), 11)
        self.assertTrue(all(tn.dist(a, b) <= 100.5 for a, b in zip(pts, pts[1:])))

    def test_a_timetable_counts_until_the_day_it_ends(self):
        ops = {"operators": [{"id": "a", "type": "municipal", "municipality": "Cataño", "feed": {"end": "2026-10-31"}},
                             {"id": "b", "type": "municipal", "municipality": "Ponce", "feed": {"end": "2027-01-31"}},
                             {"id": "mayaguez", "type": "municipal", "municipality": "Mayagüez", "feed": None}]}
        self.assertEqual(tn.current_operators(ops, "2026-10-31"), {"a", "b"})
        self.assertEqual(tn.current_operators(ops, "2026-11-01"), {"b"})
        feeds = tn.municipal_feeds(ops, "2026-11-10")
        self.assertEqual(feeds["catano"], ("expired", "2026-10-31"))
        self.assertEqual(feeds["mayaguez"], ("none", None))

    def test_useful_is_a_bus_every_30_minutes_through_the_day(self):
        every30 = [0] * 7 + [2] * 12 + [0] * 5
        self.assertTrue(tn.useful_stop({"hours": every30}, True))
        self.assertFalse(tn.useful_stop({"hours": every30}, False))
        self.assertFalse(tn.useful_stop({"hours": [0] * 7 + [1] * 12 + [0] * 5}, True))

    def test_a_stop_without_timed_departures_takes_half_its_routes_trips(self):
        stops = {"s1": {"id": "s1", "operator": "x", "routes": ["1", "2"]}, "s2": {"id": "s2", "operator": "x", "routes": ["9"]}}
        wk = {"stops": {}, "routes": [{"o": "x", "r": "1", "hours": [4] * 24}, {"o": "x", "r": "2", "hours": [2] * 24}]}
        got = tn.stop_service(stops, wk)
        self.assertEqual(got["s1"]["hours"][10], 3)
        self.assertTrue(got["s1"]["estimated"])
        self.assertNotIn("s2", got, "a stop whose routes have no timetable has no service to estimate")


class Connections(unittest.TestCase):
    def line(self, op, route, north_m, stops=()):
        lat = LAT + north_m / tn.KY
        f = {"type": "Feature", "properties": {"operator": op, "operator_name": op, "route_id": route, "short_name": route, "long_name": "", "trips_weekday": 20},
             "geometry": {"type": "LineString", "coordinates": [[lon_at(0), lat], [lon_at(2000), lat]]}}
        st = {f"{op}{route}{k}": {"id": f"{op}{route}{k}", "operator": op, "routes": [route], "lng": lon_at(x), "lat": lat} for k, x in enumerate(stops)}
        return f, st

    def run_pairs(self, *lines):
        feats, stops = [], {}
        for f, st in lines:
            feats.append(f); stops.update(st)
        blocks = [[lon_at(0), LAT, 100], [lon_at(1900), LAT, 50]]   # the lines are parallel: the closest point is the first one found, at the west end
        pairs, places = tn.connections({"features": feats}, stops, blocks, {"a", "b"})
        return pairs, places

    def test_two_operators_500_m_apart_with_no_shared_stop_are_a_candidate(self):
        pairs, places = self.run_pairs(self.line("a", "1", 0, [0, 1000]), self.line("b", "7", 500, [2000]))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["gap_m"], 500)
        self.assertEqual(pairs[0]["residents_800m"], 100)
        self.assertEqual(len(places), 1)

    def test_routes_that_already_share_a_stop_are_left_out(self):
        pairs, _ = self.run_pairs(self.line("a", "1", 0, [0]), self.line("b", "7", 200, [0]))
        self.assertEqual(pairs, [])

    def test_routes_of_one_operator_and_routes_too_far_are_left_out(self):
        self.assertEqual(self.run_pairs(self.line("a", "1", 0), self.line("a", "2", 500))[0], [])
        self.assertEqual(self.run_pairs(self.line("a", "1", 0), self.line("b", "7", 900))[0], [])


class Published(unittest.TestCase):
    def test_the_files_are_what_site_data_gives(self):
        code = tn.main(["--check"])
        if code == 2:   # the nightly transit refresh changed site/data after the snapshot: not a failure (the refresh bot's PRs must keep merging)
            self.skipTest("site/data changed since the snapshot")
        self.assertEqual(code, 0, "run python docs/analysis/transit-needs-2026-11/transit_needs.py --as-of <the date in summary.json>")


if __name__ == "__main__":
    unittest.main()
