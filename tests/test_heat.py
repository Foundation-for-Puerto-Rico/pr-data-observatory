"""Tests for heat.py: daytime land surface temperature by barrio and municipio (Landsat 8 and 9; docs/heat.md).

  python -m unittest tests.test_heat

The scene reader is checked on small Landsat-like scenes written here (a ST_B10 and a QA_PIXEL GeoTIFF on a 60 m grid): only clear land pixels count, each flag of
QA_PIXEL removes a pixel, the scale and offset give degrees Celsius, cells outside the scene are skipped, and a scene in another UTM zone lands on the right cells.
The composite is checked for its median (odd, even and empty cells, and a cold outlier) and its minimum of three views. The published files are checked without the cache: the 901
barrios in the crosswalk's order, temperatures in a plausible range, the 90th percentile never below the median, shares between 0 and 100, residents never above
the area's, municipios' residents as the sums of their barrios', Puerto Rico's share of hot land close to 10% by construction, and the physics the build checks
(San Juan hotter, Jayuya and Adjuntas cooler than Puerto Rico).
"""
import json
import math
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import heat  # noqa: E402
import raster  # noqa: E402
from test_raster import write_tiff  # noqa: E402

DATA = ROOT / "site" / "data"
CLEAR = 1 << 6                 # QA_PIXEL bit 6: clear
K = lambda c: int(round((c + 273.15 - heat.ST_OFFSET) / heat.ST_SCALE))   # degrees C -> ST_B10 digital number


def scene(d, name, st, qa, x0=500000.0, y0=2050000.0, epsg=32620, extra=None):
    """A Landsat-like scene: ST and QA (and any `extra` bands, {suffix: array}) at 30 m with a 60 m overview (level 1), named as the USGS files are."""
    kw = dict(tiepoint=(0, 0, 0, x0, y0, 0), scale=(30.0, 30.0, 0), epsg=epsg, tile=16)
    name = name if name.startswith("LC0") else "LC09_" + name
    paths = {}
    for suffix, arr in {"ST_B10": st, "QA_PIXEL": qa, **(extra or {})}.items():
        arr = np.asarray(arr, np.uint16)
        paths[suffix] = write_tiff(Path(d) / f"{name}_{suffix}.TIF", [arr.repeat(2, 0).repeat(2, 1), arr], nodata=None if suffix == "QA_PIXEL" else 0, **kw)
    return {"id": name, "date": "2026-07-01", "epsg": epsg, "cloud": 10, "st": str(paths["ST_B10"]), "qa": str(paths["QA_PIXEL"])}


class SceneReader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = heat.CACHE
        heat.CACHE = Path(self.dir.name) / "cache"

    def tearDown(self):
        heat.CACHE = self.old
        self.dir.cleanup()

    def cells(self, n=4, x0=500000.0, y0=2050000.0):
        """The centres of the first n x n cells of a 60 m grid that starts at the scene's corner."""
        cc, rr = np.meshgrid(np.arange(n), np.arange(n))
        return (x0 + (cc.ravel() + 0.5) * 60, y0 - (rr.ravel() + 0.5) * 60)

    def test_only_clear_land_pixels_count_and_the_scale_gives_celsius(self):
        st = np.full((4, 4), K(35.0))
        qa = np.full((4, 4), CLEAR)
        qa[0, 1] = CLEAR | 1             # fill
        qa[0, 2] = CLEAR | (1 << 4)      # cloud shadow
        qa[0, 3] = CLEAR | (1 << 7)      # water
        qa[1, 0] = 1 << 3                # cloud (not clear)
        sc = scene(self.dir.name, "a", st, qa)
        X, Y = self.cells()
        idx, t, filled = heat.scene_values(sc, {32620: (X, Y)}, lambda: "", None, False)
        self.assertEqual(sorted(idx.tolist()), [0] + list(range(5, 16)))
        self.assertFalse(filled.any())
        np.testing.assert_allclose(t, 35.0, atol=0.01)

    def test_cells_outside_the_scene_are_skipped(self):
        sc = scene(self.dir.name, "b", np.full((4, 4), K(30.0)), np.full((4, 4), CLEAR))
        X, Y = self.cells(6)                 # a 6 x 6 grid over a 4 x 4 scene
        idx, _, _ = heat.scene_values(sc, {32620: (X, Y)}, lambda: "", None, False)
        self.assertEqual(len(idx), 16)
        self.assertTrue(all(i % 6 < 4 and i // 6 < 4 for i in idx))
        far = (X + 1e6, Y)
        self.assertIsNone(heat.scene_values(sc, {32620: far}, lambda: "", None, False))

    def test_a_scene_in_another_utm_zone_lands_on_the_right_cells(self):
        # a scene in zone 19 whose pixels hold 20 + their column: the grid's cells (zone 20) are mapped through pyproj
        X20, Y20 = np.array([200000.0, 200300.0]), np.array([2030000.0, 2030000.0])
        X19, Y19 = raster.transform_points(X20, Y20, 32620, 32619)
        x0, y0 = math.floor(min(X19) / 60) * 60 - 600, math.ceil(max(Y19) / 60) * 60 + 600
        st = np.array([[K(20.0 + c) for c in range(40)] for _ in range(30)])
        sc = scene(self.dir.name, "z19", st, np.full(st.shape, CLEAR), x0=x0, y0=y0, epsg=32619)
        idx, t, _ = heat.scene_values(sc, {32620: (X20, Y20), 32619: (X19, Y19)}, lambda: "", None, False)
        want = [20.0 + math.floor((x - x0) / 60) for x in X19]
        np.testing.assert_allclose(t, want, atol=0.01)

    def test_composite_median_and_minimum_views(self):
        X, Y = self.cells(2)
        temps = [[30, 32], [31, 33], [29, 31], [30, 32], [31, 32], [12, 32]]   # cell 0: five views near 30 and one cold (a cloud edge); cell 1: always ~32
        scs = []
        for k, (a, b) in enumerate(temps):
            st = np.array([[K(a), K(b)], [K(30), K(30)]])
            qa = np.array([[CLEAR, CLEAR], [CLEAR if k < 2 else 1 << 3, 1 << 3]])  # cell 2 has two clear views only; cell 3 none
            scs.append(scene(self.dir.name, f"s{k}", st, qa))
        lst, n, nfill, used, total, check = heat.composite(scs, {32620: (X, Y)}, 4, offline=False, tok=lambda: "", parallel=2, check_fill=False)
        self.assertEqual(list(nfill), [0, 0, 0, 0])
        self.assertEqual(list(n), [6, 6, 2, 0])
        self.assertAlmostEqual(lst[0], 30.0, places=2)                   # median of 12, 29, 30, 30, 31, 31: the cold view barely moves it (the mean would be 27.2)
        self.assertAlmostEqual(lst[1], 32.0, places=2)
        self.assertTrue(np.isnan(lst[2]))                                # fewer than three views: no value
        self.assertTrue(np.isnan(lst[3]))
        self.assertEqual((total, len(used)), (14, 6))

    def test_gap_fill_recovers_a_known_temperature_where_usgs_has_none(self):
        # forward model: TOA radiance from a known surface temperature, emissivity from NDVI on heat's table, and an atmosphere; ST_B10 empty (0)
        K1, K2 = heat.K_TIRS["LC09"]
        temps = np.array([[25.0, 38.0], [45.0, 31.0]])
        ndvi_red, ndvi_nir = np.array([[0.05, 0.10], [0.12, 0.03]]), np.array([[0.45, 0.20], [0.18, 0.40]])   # dense vegetation, soil, roof, forest
        ndvi = (ndvi_nir - ndvi_red) / (ndvi_nir + ndvi_red)
        eps = np.interp(ndvi, *heat.EMIS_NDVI)
        at, ur, dr = 0.82, 1.15, 1.95
        B = K1 / (np.exp(K2 / (temps + 273.15)) - 1)
        toa = at * (eps * B + (1 - eps) * dr) + ur
        DN = lambda x, sc, off=0.0: np.round((x - off) / sc)
        extra = {"ST_TRAD": DN(toa, 0.001), "ST_URAD": np.full((2, 2), DN(ur, 0.001)), "ST_DRAD": np.full((2, 2), DN(dr, 0.001)),
                 "ST_ATRAN": np.full((2, 2), DN(at, 0.0001)), "SR_B4": DN(ndvi_red, 0.0000275, -0.2), "SR_B5": DN(ndvi_nir, 0.0000275, -0.2)}
        st = np.array([[0, 0], [0, K(31.0)]])                   # USGS has a value for one cell only
        sc = scene(self.dir.name, "fill", st, np.full((2, 2), CLEAR), extra=extra)
        X, Y = self.cells(2)
        idx, t, filled = heat.scene_values(sc, {32620: (X, Y)}, lambda: "", None, False)
        order = np.argsort(idx)
        self.assertEqual(list(filled[order]), [True, True, True, False])
        np.testing.assert_allclose(t[order], temps.ravel(), atol=0.05)   # the rounding of the bands' integers, not the method

    def test_median_by_cell_odd_even_and_empty(self):
        idx = np.array([2, 0, 2, 0, 2, 0, 0], np.int32)
        t = np.array([5, 4, 1, 1, 3, 3, 2], np.float32)
        med, n = heat.median_by_cell(idx, t, 4)
        self.assertEqual(list(n), [4, 0, 3, 0])
        self.assertAlmostEqual(med[0], 2.5)                              # 1 2 3 4
        self.assertAlmostEqual(med[2], 3.0)                              # 1 3 5
        self.assertTrue(np.isnan(med[1]) and np.isnan(med[3]))

    def test_summers(self):
        self.assertEqual(heat.summers(date(2026, 11, 4)), [2024, 2025, 2026])
        self.assertEqual(heat.summers(date(2026, 9, 30)), [2023, 2024, 2025])


@unittest.skipUnless((DATA / "heat_series.json").exists(), "heat_series.json not built")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "heat_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "heat_barrio.json").read_text(encoding="utf-8"))
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
        self.assertEqual(set(self.sv), {"heat_lst_med", "heat_lst_p90", "heat_hot_land_pct", "heat_res_hot", "heat_res_hot_pct"})
        self.assertEqual(set(self.bv), set(self.sv))
        for v in self.b["vars"]:
            self.assertEqual(len(v["years"][self.Y]), 901, v["key"])
        for v in self.s["vars"]:
            self.assertEqual(v["barrioFile"], "heat_barrio.json")
            self.assertEqual(len(v["years"][self.Y]), 79)

    def test_ranges(self):
        for lvl in ("m", "b"):
            med, p90 = self.col("heat_lst_med", lvl), self.col("heat_lst_p90", lvl)
            for a, b in zip(med, p90):
                if a is None:
                    self.assertIsNone(b)
                    continue
                self.assertTrue(15 <= a <= 60 and 15 <= b <= 65, (a, b))
                self.assertLessEqual(a, b)
            for k in ("heat_hot_land_pct", "heat_res_hot_pct"):
                for x in self.col(k, lvl):
                    self.assertTrue(x is None or 0 <= x <= 100, (k, x))

    def test_residents_add_up_and_never_exceed_the_area(self):
        bres = self.col("heat_res_hot", "b")
        for bid, x in zip(self.bids, bres):
            self.assertTrue(x is None or x <= self.pop[bid], bid)
        mids = self.s["geo"]["ids"][:-1]
        for f, x in zip(mids, self.col("heat_res_hot")):
            parts = [y for bid, y in zip(self.bids, bres) if bid[:5] == f and y is not None]
            if x is not None:
                self.assertEqual(x, sum(parts), f)
        self.assertEqual(self.col("heat_res_hot")[-1], sum(x for x in bres if x is not None))

    def test_puerto_rico_hot_land_is_a_tenth_and_the_physics_hold(self):
        self.assertAlmostEqual(self.col("heat_hot_land_pct")[-1], 10.0, delta=0.5)
        ids = self.s["geo"]["ids"]
        med = dict(zip(ids, self.col("heat_lst_med")))
        self.assertGreater(med["72127"], med["72"])            # San Juan
        self.assertLess(med["72073"], med["72"])               # Jayuya
        self.assertLess(med["72001"], med["72"])               # Adjuntas
        n = self.s["notes"]
        self.assertGreaterEqual(n["grid"]["cells_with_value_pct"], heat.CHECK_COVER * 100)
        self.assertGreaterEqual(n["window"]["scenes_with_clear_cells"], heat.FLOOR_SCENES)


if __name__ == "__main__":
    unittest.main()
