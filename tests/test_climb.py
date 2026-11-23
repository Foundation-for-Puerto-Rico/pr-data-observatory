"""Tests for climb.py and walknet.nearest_paths: the climb on the walk to a transit stop (docs/climb.md).

  python -m unittest tests.test_climb

The walk is checked on a small grid of roads: its pieces are joined end to start, from the place to the stop, and its length is the walking distance the
search of from_stops gives; the nearest stop wins; a place too far gets no walk. The climb is checked on made-up heights: flat is 0, a hill up and down
counts both ways, a steady 1 in 10 is steep and 1 in 20 is not, and a short piece gives its own grade. The weighted median and the elevation tile names are
checked. The published files, when present, are checked for shape, ranges, residents that add up and the build's checks.
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import shapely

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import climb  # noqa: E402
import walknet  # noqa: E402

DATA = ROOT / "site" / "data"


def grid_net():
    """A 3 x 3 grid of roads 100 m apart, in local metres: nodes 0..8 row by row, edges right and down."""
    xy = {n: (100.0 * (n % 3), -100.0 * (n // 3)) for n in range(9)}
    eu, ev, geoms = [], [], []
    for n in range(9):
        for m in ((n + 1) if n % 3 < 2 else None, n + 3 if n < 6 else None):
            if m is not None:
                eu.append(n); ev.append(m); geoms.append(shapely.linestrings([xy[n], xy[m]]))
    return walknet.WalkNet(eu, ev, geoms, 9)


def ll(x, y):
    """Local metres back to lon/lat."""
    return {"lng": x / (walknet.M_PER_DEG * walknet.COS0) + walknet.LON0, "lat": y / walknet.M_PER_DEG + walknet.LAT0}


class Walks(unittest.TestCase):
    def test_the_walk_is_joined_from_the_place_to_the_stop_and_has_the_searched_length(self):
        net = grid_net()
        places = [ll(5.0, -150.0), ll(150.0, -205.0), ll(190.0, 3.0)]          # beside roads, a few metres off
        stops = [ll(200.0, -60.0)]
        paths = walknet.nearest_paths(net, stops, places, 1000)
        dist = walknet.from_stops(net, stops, places, 1000)[0]
        for k, b in enumerate(paths):
            j, d, pieces = b
            self.assertEqual(j, 0)
            self.assertAlmostEqual(d, dist[k][0], places=6)
            self.assertAlmostEqual(sum(float(shapely.length(shapely.linestrings(p))) for p in pieces if len(p) > 1), d, places=4)
            px, py = walknet.to_xy(places[k]["lng"], places[k]["lat"])
            sx, sy = walknet.to_xy(stops[0]["lng"], stops[0]["lat"])
            np.testing.assert_allclose(pieces[0][0], [px, py], atol=1e-6)       # starts at the place
            np.testing.assert_allclose(pieces[-1][-1], [sx, sy], atol=1e-6)     # ends at the stop
            for a, b2 in zip(pieces, pieces[1:]):
                if len(a) and len(b2):
                    np.testing.assert_allclose(a[-1], b2[0], atol=1e-6)        # joined end to start

    def test_the_nearest_stop_wins_and_a_place_too_far_gets_none(self):
        net = grid_net()
        places = [ll(0.0, -195.0), ll(200.0, 0.0)]
        stops = [ll(100.0, -195.0), ll(0.0, -5.0)]                             # 110 m and 205 m from the first place
        paths = walknet.nearest_paths(net, stops, places, 150)
        self.assertEqual(paths[0][0], 0)
        self.assertIsNone(paths[1])                                             # 200 m from the nearest stop, beyond 150 m


class Measures(unittest.TestCase):
    def test_flat_hill_and_grades(self):
        self.assertEqual(climb.walk_measures([[5.0] * 20]), (0.0, 0.0))
        up_down = list(range(0, 11)) + list(range(9, -1, -1))                   # up 10 m and down 10 m, 1 m each 10 m
        c, s = climb.walk_measures([up_down])
        self.assertAlmostEqual(c, 20.0)
        self.assertAlmostEqual(s, 0.1)
        self.assertGreater(climb.walk_measures([[i * 1.0 for i in range(10)]])[1], climb.STEEP)       # 1 in 10
        self.assertLess(climb.walk_measures([[i * 0.5 for i in range(10)]])[1], climb.STEEP)          # 1 in 20
        self.assertAlmostEqual(climb.walk_measures([[0.0, 2.0]])[1], 0.2)                             # a piece shorter than the window
        self.assertEqual(climb.walk_measures([[0.0, float("nan"), 3.0]]), (0.0, 0.0))                  # no height: the piece is skipped

    def test_climb_adds_over_pieces(self):
        self.assertAlmostEqual(climb.walk_measures([[0, 3, 6], [6, 2]])[0], 10.0)

    def test_weighted_median(self):
        self.assertEqual(climb.weighted_median([1, 2, 3], [1, 1, 10]), 3.0)
        self.assertEqual(climb.weighted_median([1, 2, 3], [1, 1, 1]), 2.0)
        self.assertIsNone(climb.weighted_median([], []))

    def test_elevation_tile_of_a_point(self):
        cells = climb.Dem.cell_of(np.array([-66.6, -67.2, -65.5, -66.5]), np.array([18.17, 18.3, 18.1, 17.95]))
        self.assertEqual(cells.tolist(), ["n19w067", "n19w068", "n19w066", "n18w067"])


@unittest.skipUnless((DATA / "climb_series.json").exists(), "climb_series.json is built by climb.py")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "climb_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "climb_barrio.json").read_text(encoding="utf-8"))
        cls.Y = cls.s["as_of"]

    def col(self, key, level="m"):
        doc = self.s if level == "m" else self.b
        return next(v for v in doc["vars"] if v["key"] == key)["years"][self.Y]

    def test_shape_and_ranges(self):
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        for v in self.b["vars"]:
            self.assertEqual(len(v["years"][self.Y]), 901)
        for lvl in ("m", "b"):
            self.assertTrue(all(x is None or 0 <= x <= 400 for x in self.col("walk_climb_med", lvl)))
            self.assertTrue(all(x is None or 0 <= x <= 100 for x in self.col("walk_steep_pct", lvl)))

    def test_residents_add_up_to_the_published_walkers(self):
        n = self.s["notes"]
        self.assertEqual(n["residents_with_a_walk"], n["published_walk_cur"])
        bres, mres = self.col("walk_steep_res", "b"), self.col("walk_steep_res")
        self.assertEqual(mres[-1], sum(x for x in mres[:-1] if x is not None))
        self.assertEqual(mres[-1], sum(x for x in bres if x is not None))

    def test_the_checks_hold(self):
        med = dict(zip(self.s["geo"]["ids"], self.col("walk_climb_med")))
        for f in climb.HILLS:
            self.assertGreater(med[f], med["72"])
        for f in climb.FLAT:
            self.assertLess(med[f], med["72"])


if __name__ == "__main__":
    unittest.main()
