"""Tests for vegetation.py: vegetation greenness (NDVI) by barrio and municipio (Sentinel-2; docs/vegetation.md).

  python -m unittest tests.test_vegetation

The scene reader is checked on small Sentinel-2-like scenes written here (red and near-infrared at 10 m with overviews to 40 m, SCL at 20 m with an overview
to 40 m): only the SCL classes vegetation and not vegetated count, the scale and offset give reflectance, NDVI is right, a pixel with no reflectance is skipped,
cells outside the scene are skipped, and a scene whose overviews are not one grid stops the build. The per-scene cache is checked to give back what was read and to
be used offline. Two tiles of one pass give each cell once. The composite's median, its minimum of three views and its blocks are checked. The rank correlation is
checked with ties. The published files are checked without the cache: the 901 barrios in the crosswalk's order, NDVI between -1 and 1, shares between 0 and 100,
residents never above the area's and adding up, and the checks the build makes (San Juan less green, Jayuya and Adjuntas greener than Puerto Rico; greener is
cooler across the barrios).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import vegetation as veg  # noqa: E402
from test_raster import write_tiff  # noqa: E402

DATA = ROOT / "site" / "data"
DN = lambda refl: int(round((refl + 0.1) * 10000))     # reflectance -> Sentinel-2 Collection 1 digital number (scale 0.0001, offset -0.1)


def scene(d, name, red, nir, scl, x0=500000.0, y0=2050000.0, epsg=32620, date="2026-07-01", break_grid=False):
    """A Sentinel-2-like scene: arrays at 40 m, written as red/nir at 10 m with overviews 20 m and 40 m, and SCL at 20 m with an overview at 40 m."""
    kw = dict(tiepoint=(0, 0, 0, x0, y0, 0), epsg=epsg, tile=16)
    paths = {}
    for band, arr in (("red", red), ("nir", nir)):
        a = np.asarray(arr, np.uint16)
        paths[band] = write_tiff(Path(d) / f"{name}_{band}.tif", [a.repeat(4, 0).repeat(4, 1), a.repeat(2, 0).repeat(2, 1), a], nodata=0, scale=(10.0, 10.0, 0), **kw)
    s = np.asarray(scl, np.uint8)
    lv = [s.repeat(2, 0).repeat(2, 1), s] if not break_grid else [s.repeat(2, 0).repeat(2, 1)]
    paths["scl"] = write_tiff(Path(d) / f"{name}_scl.tif", lv, nodata=0, scale=(20.0, 20.0, 0), **kw)
    return {"id": name, "date": date, "epsg": epsg, "cloud": 10, **{k: str(v) for k, v in paths.items()}, "scale": 0.0001, "offset": -0.1}


def cells(n=4, x0=500000.0, y0=2050000.0):
    """The centres of the 40 m pixels of an n x n scene (one grid cell on each)."""
    cc, rr = np.meshgrid(np.arange(n), np.arange(n))
    return x0 + (cc.ravel() + 0.5) * 40, y0 - (rr.ravel() + 0.5) * 40


class SceneReader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = veg.CACHE
        veg.CACHE = Path(self.dir.name) / "cache"

    def tearDown(self):
        veg.CACHE = self.old
        self.dir.cleanup()

    def test_only_vegetation_and_bare_land_count_and_ndvi_is_right(self):
        red = np.full((4, 4), DN(0.05)); nir = np.full((4, 4), DN(0.45))      # NDVI 0.8
        scl = np.full((4, 4), 4)
        scl[0, 1] = 5                    # not vegetated: counts
        scl[0, 2] = 3                    # cloud shadow
        scl[0, 3] = 6                    # water
        scl[1, 0] = 8                    # cloud, medium probability
        scl[1, 1] = 10                   # thin cirrus
        scl[1, 2] = 2                    # dark area or terrain shadow
        scl[1, 3] = 7                    # unclassified
        red[2, 0] = DN(0.2); nir[2, 0] = DN(0.2)    # NDVI 0
        red[2, 1] = 0                    # no data
        sc = scene(self.dir.name, "S2A_T20QKF_20260701_L2A", red, nir, scl)
        X, Y = cells()
        idx, v = veg.read_scene(sc, {32620: (X, Y)})
        self.assertEqual(idx.tolist(), [0, 1, 8] + list(range(10, 16)))
        nd = dict(zip(idx.tolist(), (v / 10000).tolist()))
        self.assertAlmostEqual(nd[0], 0.8, places=3)
        self.assertAlmostEqual(nd[8], 0.0, places=3)

    def test_cells_outside_the_scene_are_skipped(self):
        sc = scene(self.dir.name, "S2A_T20QKF_20260702_L2A", np.full((4, 4), DN(0.05)), np.full((4, 4), DN(0.3)), np.full((4, 4), 4))
        cc, rr = np.meshgrid(np.arange(6), np.arange(6))
        X, Y = 500000.0 + (cc.ravel() + 0.5) * 40, 2050000.0 - (rr.ravel() + 0.5) * 40
        idx, _ = veg.read_scene(sc, {32620: (X, Y)})
        self.assertEqual(len(idx), 16)
        self.assertTrue(all(i % 6 < 4 and i // 6 < 4 for i in idx.tolist()))

    def test_overviews_that_are_not_one_grid_stop_the_build(self):
        sc = scene(self.dir.name, "S2A_T20QKF_20260703_L2A", np.full((4, 4), DN(0.05)), np.full((4, 4), DN(0.3)), np.full((4, 4), 4), break_grid=True)
        with self.assertRaises(SystemExit):
            veg.read_scene(sc, {32620: cells()})

    def test_the_cache_gives_back_what_was_read_and_works_offline(self):
        red = np.arange(16).reshape(4, 4) * 50 + DN(0.03); nir = np.full((4, 4), DN(0.4))
        scl = np.full((4, 4), 4); scl[3, 3] = 9
        sc = scene(self.dir.name, "S2B_T20QKF_20260704_L2A", red, nir, scl)
        xy = {32620: cells()}
        a = veg.scene_values(sc, xy)
        Path(sc["red"]).unlink()                      # the files are gone: the cache must answer, offline
        b = veg.scene_values(sc, xy, offline=True)
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_array_equal(a[1], b[1])
        self.assertEqual(len(b[0]), 15)
        with self.assertRaises(SystemExit):
            veg.scene_values({**sc, "id": "S2B_T20QKF_20260705_L2A"}, xy, offline=True)

    def test_one_view_per_pass(self):
        i, v = veg.one_view_per_pass([(np.array([3, 1, 2], np.int32), np.array([30, 10, 20], np.int16)),
                                      (np.array([2, 4], np.int32), np.array([99, 40], np.int16))])
        self.assertEqual(dict(zip(i.tolist(), v.tolist())), {1: 10, 2: 20, 3: 30, 4: 40})
        g = veg.by_pass([{"id": "S2A_T20QKE_x", "date": "2026-07-01"}, {"id": "S2A_T19QHA_x", "date": "2026-07-01"},
                         {"id": "S2B_T19QHA_x", "date": "2026-07-01"}, {"id": "S2A_T19QHA_y", "date": "2026-07-11"}])
        self.assertEqual([[s["id"] for s in p] for p in g], [["S2A_T19QHA_x", "S2A_T20QKE_x"], ["S2A_T19QHA_y"], ["S2B_T19QHA_x"]])

    def test_composite_median_minimum_views_and_blocks(self):
        xy = {32620: cells()}
        vals = [0.2, 0.5, 0.6, 0.9]
        scs = []
        for k, ndvi in enumerate(vals):
            r = 0.05
            n = r * (1 + ndvi) / (1 - ndvi)
            scl = np.full((4, 4), 4)
            if k >= 2:
                scl[0, 0] = 9                         # cell 0 has two clear views only
            scs.append(scene(self.dir.name, f"S2A_T20QKF_2026070{k + 1}_L2A", np.full((4, 4), DN(r)), np.full((4, 4), DN(n)), scl, date=f"2026-07-0{k + 1}"))
        # a second tile of the first pass, overlapping: it must not add a view
        scs.append(scene(self.dir.name, "S2A_T20QKG_20260701_L2A", np.full((4, 4), DN(0.05)), np.full((4, 4), DN(0.5)), np.full((4, 4), 4), date="2026-07-01"))
        old = veg.BLOCKS
        try:
            for blocks in (1, 3):
                veg.BLOCKS = blocks
                ndvi, nobs, used, npass, total = veg.composite(scs, xy, 16, parallel=2)
                self.assertTrue(np.isnan(ndvi[0]))
                self.assertEqual(nobs[0], 2)
                self.assertTrue((nobs[1:] == 4).all())
                np.testing.assert_allclose(ndvi[1:], 0.55, atol=1e-3)
                self.assertEqual((used, npass, total), (4, 4, 62))
        finally:
            veg.BLOCKS = old

    def test_ranks_and_spearman(self):
        np.testing.assert_allclose(veg.ranks([10, 20, 20, 5]), [2, 3.5, 3.5, 1])
        self.assertAlmostEqual(veg.spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)


class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "vegetation_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "vegetation_barrio.json").read_text(encoding="utf-8"))
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.bids = [r[F["id"]] for r in cw["units"]["barrio"]]
        cls.pop = {r[F["id"]]: r[F["pop"]] for lv in ("barrio", "municipio") for r in cw["units"][lv]}
        cls.sv = {v["key"]: v for v in cls.s["vars"]}
        cls.bv = {v["key"]: v for v in cls.b["vars"]}
        cls.Y = cls.s["as_of"]

    def col(self, key, level="m"):
        return (self.sv if level == "m" else self.bv)[key]["years"][self.Y]

    def test_shape(self):
        self.assertEqual(self.b["geo"]["ids"], self.bids)
        self.assertEqual(self.s["geo"]["ids"][-1], "72")
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual(set(self.sv), {"veg_ndvi_med", "veg_dense_pct", "veg_sparse_pct", "veg_res_sparse", "veg_res_sparse_pct"})
        self.assertEqual(set(self.bv), set(self.sv))
        for v in self.b["vars"]:
            self.assertEqual(len(v["years"][self.Y]), 901, v["key"])
        for v in self.s["vars"]:
            self.assertEqual(v["barrioFile"], "vegetation_barrio.json")
            self.assertEqual(len(v["years"][self.Y]), 79)

    def test_ranges(self):
        for lvl in ("m", "b"):
            for x in self.col("veg_ndvi_med", lvl):
                self.assertTrue(x is None or -1 <= x <= 1, x)
            for d, s in zip(self.col("veg_dense_pct", lvl), self.col("veg_sparse_pct", lvl)):
                if d is None:
                    self.assertIsNone(s)
                    continue
                self.assertTrue(0 <= d <= 100 and 0 <= s <= 100 and d + s <= 100.05, (d, s))
            for x in self.col("veg_res_sparse_pct", lvl):
                self.assertTrue(x is None or 0 <= x <= 100, x)

    def test_residents_add_up_and_never_exceed_the_area(self):
        bres = self.col("veg_res_sparse", "b")
        for bid, x in zip(self.bids, bres):
            self.assertTrue(x is None or x <= self.pop[bid], bid)
        for f, x in zip(self.s["geo"]["ids"][:-1], self.col("veg_res_sparse")):
            if x is not None:
                self.assertEqual(x, sum(y for bid, y in zip(self.bids, bres) if bid[:5] == f and y is not None), f)
        self.assertEqual(self.col("veg_res_sparse")[-1], sum(x for x in bres if x is not None))

    def test_the_checks_hold(self):
        med = dict(zip(self.s["geo"]["ids"], self.col("veg_ndvi_med")))
        self.assertLess(med["72127"], med["72"])            # San Juan
        self.assertGreater(med["72073"], med["72"])         # Jayuya
        self.assertGreater(med["72001"], med["72"])         # Adjuntas
        n = self.s["notes"]
        self.assertGreaterEqual(n["grid"]["cells_with_value_pct"], veg.CHECK_COVER * 100)
        link = n["checks"]["greener_is_cooler"]
        self.assertIsNotNone(link)
        self.assertLessEqual(link["spearman"], veg.CHECK_HEAT_RHO)


if __name__ == "__main__":
    unittest.main()
