"""Tests for buildings.py: buildings by barrio and municipio (Overture buildings theme; docs/buildings.md).

  python -m unittest tests.test_buildings

The barrio assignment is checked on small squares written here: a point inside goes to its barrio, a point on a shared edge to the lower index (as
conditions.Barrios.at), a point just off the coast to the nearest barrio within 100 m and a farther one to none. The flood rule is checked on a small FEMA-like
collection: only Special Flood Hazard Areas count. The rank correlation is checked with ties. The cache is checked to be read offline, the newest release first.
The published files are checked without the cache: the 901 barrios in the crosswalk's order, counts that add up from barrios to municipios to Puerto Rico,
shares between 0 and 100, the flood count never above the count, and the checks the build makes. Nothing per building is published.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import buildings as bld  # noqa: E402

DATA = ROOT / "site" / "data"


class FakeBarrios:
    """Two unit squares side by side, (0,0)-(1,1) and (1,0)-(2,1), in degrees, like conditions.Barrios's tree."""

    def __init__(self):
        from shapely.geometry import box
        from shapely.strtree import STRtree
        self.geoms = [box(0, 0, 1, 1), box(1, 0, 2, 1)]
        self.tree = STRtree(self.geoms)


class Place(unittest.TestCase):
    def test_inside_edge_coast_and_far(self):
        B = FakeBarrios()
        lon = np.array([0.5, 1.5, 1.0, 2.0005, 2.01])
        lat = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
        self.assertEqual(bld.place(B, lon, lat).tolist(), [0, 1, 0, 1, -1])

    def test_no_point_left(self):
        B = FakeBarrios()
        self.assertEqual(bld.place(B, np.array([0.2]), np.array([0.2])).tolist(), [0])


class Flood(unittest.TestCase):
    def test_only_special_flood_hazard_areas_count(self):
        sq = lambda x0: {"type": "Polygon", "coordinates": [[[x0, 0], [x0 + 1, 0], [x0 + 1, 1], [x0, 1], [x0, 0]]]}
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"FLD_ZONE": "AE", "SFHA_TF": "T"}, "geometry": sq(0)},
            {"type": "Feature", "properties": {"FLD_ZONE": "X", "SFHA_TF": "F", "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD"}, "geometry": sq(1)},
            {"type": "Feature", "properties": {"FLD_ZONE": "OPEN WATER", "SFHA_TF": "T"}, "geometry": sq(2)}]}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "flood.geojson").write_text(json.dumps(fc), encoding="utf-8")
            with mock.patch.object(bld, "OUT", Path(d)):
                m = bld.in_flood(np.array([0.5, 1.5, 2.5, 5.0]), np.array([0.5, 0.5, 0.5, 0.5]))
        self.assertEqual(m.tolist(), [True, False, False, False])


class Spearman(unittest.TestCase):
    def test_monotone_and_reversed(self):
        self.assertAlmostEqual(bld.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(bld.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)

    def test_ties_do_not_break_it(self):
        r = bld.spearman([1, 1, 2, 3], [1, 2, 3, 4])
        self.assertTrue(0.8 < r <= 1.0, r)


class Cache(unittest.TestCase):
    def test_offline_reads_the_newest_cached_release(self):
        with tempfile.TemporaryDirectory() as d:
            for rel, n in (("2026-09-23.0", 1), ("2026-10-21.0", 2)):
                np.savez_compressed(Path(d) / f"{rel}.npz", lon=np.zeros(n), lat=np.zeros(n), area=np.ones(n, "float32"), src=np.zeros(n, "uint8"),
                                    height=np.full(n, np.nan, "float32"), other=np.array("{}"))
            with mock.patch.object(bld, "CACHE", Path(d)):
                rel, z = bld.load(offline=True)
        self.assertEqual(rel, "2026-10-21.0")
        self.assertEqual(len(z["lon"]), 2)

    def test_offline_without_a_cache_stops(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(bld, "CACHE", Path(d)):
            with self.assertRaises(SystemExit):
                bld.load(offline=True)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "buildings_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "buildings_barrio.json").read_text(encoding="utf-8"))
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.barrios = [r[F["id"]] for r in cw["units"]["barrio"]]
        cls.V = {v["key"]: next(iter(v["years"].values())) for v in cls.s["vars"]}
        cls.BV = {v["key"]: next(iter(v["years"].values())) for v in cls.b["vars"]}

    def test_shape(self):
        self.assertEqual(self.b["geo"]["ids"], self.barrios)
        self.assertEqual(self.s["geo"]["ids"][-1], "72")
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual(set(self.V), {"bld_n", "bld_per_km2", "bld_roof_pct", "bld_area_med", "bld_sfha_n", "bld_sfha_pct", "bld_ml_pct"})
        self.assertEqual(set(self.BV), set(self.V))
        for v in self.s["vars"]:
            self.assertEqual(v["barrioFile"], "buildings_barrio.json")
            self.assertEqual(v["sources"], ["overture_buildings", "census_tiger"])

    def test_counts_add_up(self):
        n_b, n_m = self.BV["bld_n"], self.V["bld_n"]
        self.assertEqual(sum(x or 0 for x in n_b), n_m[-1])
        self.assertEqual(sum(n_m[:-1]), n_m[-1])
        for i, m in enumerate(self.s["geo"]["ids"][:-1]):
            self.assertEqual(sum(x or 0 for b, x in zip(self.barrios, n_b) if b[:5] == m), n_m[i], m)
        self.assertEqual(sum(x or 0 for x in self.BV["bld_sfha_n"]), self.V["bld_sfha_n"][-1])

    def test_ranges(self):
        for k in ("bld_roof_pct", "bld_sfha_pct", "bld_ml_pct"):
            for x in self.V[k] + self.BV[k]:
                self.assertTrue(x is None or 0 <= x <= 100, (k, x))
        for n, f in zip(self.V["bld_n"] + self.BV["bld_n"], self.V["bld_sfha_n"] + self.BV["bld_sfha_n"]):
            self.assertTrue(n is None or 0 <= f <= n)
        for x in self.V["bld_area_med"]:
            self.assertTrue(20 <= x <= 1000, x)

    def test_the_checks_hold(self):
        n = self.s["notes"]
        self.assertTrue(bld.FLOOR_N <= n["buildings_in_box"] <= bld.CEIL_N)
        self.assertGreaterEqual(n["placed_in_a_barrio"] / n["buildings_in_box"], bld.MIN_PLACED)
        self.assertGreater(n["checks"]["san_juan_per_km2"], n["checks"]["pr_per_km2"])
        self.assertTrue(1 <= n["checks"]["pr_sfha_pct"] <= 30)
        self.assertGreaterEqual(n["checks"]["spearman_buildings_housing_units"], bld.MIN_RHO_HU)
        self.assertEqual(sum(n["by_source"].values()), n["buildings_in_box"])

    def test_nothing_per_building_is_published(self):
        for d in (self.s, self.b):
            text = json.dumps(d)
            for word in ('"lon"', '"lat"', '"geometry"', '"coordinates"', '"height"'):
                self.assertNotIn(word, text)
        self.assertLessEqual(len(json.dumps(self.b)), 60_000)

    def test_the_cache_rebuilds_the_files_when_it_is_here(self):
        if not list(bld.CACHE.glob("*.npz")):
            self.skipTest("no cache/buildings/ here (python buildings.py builds it)")
        self.assertEqual(bld.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
