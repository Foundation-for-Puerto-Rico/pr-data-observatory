"""Tests for ecostress.py: night-time land surface temperature by barrio and municipio (NASA ECOSTRESS; docs/ecostress.md).

  python -m unittest tests.test_ecostress

The granule reader is checked on small ECOSTRESS-like tiles written here (LST in kelvin with NaN fill, QC, cloud and water layers at 70 m): only clear land
observations count (each mask and each QC grade), kelvin becomes degrees Celsius, cells outside the tile are skipped, and layers on different grids stop the build.
The per-granule cache gives back what was read and answers offline. The token goes only to NASA's hosts. The night window and the zone of a tile are checked.
The composite keeps one view per orbit. The published files, when present, are checked for shape, ranges, residents that add up and the build's checks.
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
import ecostress as eco  # noqa: E402
from test_raster import write_tiff  # noqa: E402

DATA = ROOT / "site" / "data"


def granule(d, gid, lst, qc, cloud, water, x0=500000.0, y0=2050000.0, tile="20QKF", time="2025-07-01T06:00:00.000Z", shift=0.0):
    kw = dict(tiepoint=(0, 0, 0, x0, y0, 0), scale=(70.0, 70.0, 0), epsg=32620, tile=16)
    files = {}
    for name, arr, nd in (("LST", np.asarray(lst, np.float32), "nan"), ("QC", np.asarray(qc, np.uint16), None),
                          ("cloud", np.asarray(cloud, np.uint8), None), ("water", np.asarray(water, np.uint8), None)):
        k = dict(kw)
        if name == "water" and shift:
            k["tiepoint"] = (0, 0, 0, x0 + shift, y0, 0)
        files[name] = str(write_tiff(Path(d) / f"{gid}_{name}.tif", [arr], nodata=nd, **k))
    return {"id": gid, "time": time, "tile": tile, "night": True, "files": files}


def cells(n=4, x0=500000.0, y0=2050000.0):
    cc, rr = np.meshgrid(np.arange(n), np.arange(n))
    return x0 + (cc.ravel() + 0.5) * 70, y0 - (rr.ravel() + 0.5) * 70


GID = "ECOv002_L2T_LSTE_{orbit}_005_{tile}_20250701T060000_0713_01"


class GranuleReader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.old = eco.CACHE
        eco.CACHE = Path(self.dir.name) / "cache"

    def tearDown(self):
        eco.CACHE = self.old
        self.dir.cleanup()

    def test_only_clear_land_counts_and_kelvin_becomes_celsius(self):
        lst = np.full((4, 4), 300.15, np.float32)
        qc = np.zeros((4, 4)); cloud = np.zeros((4, 4)); water = np.zeros((4, 4))
        lst[0, 1] = np.nan          # not produced
        qc[0, 2] = 1                # nominal: counts
        qc[0, 3] = 3                # not produced
        qc[1, 0] = 2                # cloud detected by the QC
        cloud[1, 1] = 1             # cloud mask
        water[1, 2] = 1             # water
        lst[1, 3] = 150.0           # impossible value
        g = granule(self.dir.name, GID.format(orbit=1, tile="20QKF"), lst, qc, cloud, water)
        idx, v = eco.read_granule(g, {32620: cells()}, None, None)
        self.assertEqual(idx.tolist(), [0, 2] + list(range(8, 16)))
        np.testing.assert_allclose(v / 100, 27.0, atol=0.01)

    def test_cells_outside_the_tile_are_skipped(self):
        g = granule(self.dir.name, GID.format(orbit=2, tile="20QKF"), np.full((4, 4), 295.0), np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4)))
        cc, rr = np.meshgrid(np.arange(6), np.arange(6))
        X, Y = 500000.0 + (cc.ravel() + 0.5) * 70, 2050000.0 - (rr.ravel() + 0.5) * 70
        idx, _ = eco.read_granule(g, {32620: (X, Y)}, None, None)
        self.assertEqual(len(idx), 16)

    def test_layers_on_different_grids_stop_the_build(self):
        g = granule(self.dir.name, GID.format(orbit=3, tile="20QKF"), np.full((4, 4), 295.0), np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4)), shift=70.0)
        with self.assertRaises(SystemExit):
            eco.read_granule(g, {32620: cells()}, None, None)

    def test_the_cache_gives_back_what_was_read_and_works_offline(self):
        g = granule(self.dir.name, GID.format(orbit=4, tile="20QKF"), np.full((4, 4), 299.0), np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4)))
        a = eco.granule_values(g, {32620: cells()})
        Path(g["files"]["LST"]).unlink()
        b = eco.granule_values(g, {32620: cells()}, offline=True)
        np.testing.assert_array_equal(a[0], b[0]); np.testing.assert_array_equal(a[1], b[1])
        with self.assertRaises(SystemExit):
            eco.granule_values({**g, "id": GID.format(orbit=5, tile="20QKF")}, {32620: cells()}, offline=True)

    def test_composite_one_view_per_orbit_and_the_median(self):
        xy = {32620: cells()}
        gs = []
        for k, t in enumerate((20.0, 24.0, 30.0)):
            gs.append(granule(self.dir.name, GID.format(orbit=10 + k, tile="20QKF"), np.full((4, 4), t + 273.15), np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4))))
        gs.append(granule(self.dir.name, GID.format(orbit=10, tile="20QKG"), np.full((4, 4), 40 + 273.15), np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 4))))
        lst, nobs, used, npass, total = eco.composite(gs, xy, 16, parallel=2)
        self.assertTrue((nobs == 3).all())
        np.testing.assert_allclose(lst, 24.0, atol=0.01)
        self.assertEqual((used, npass, total), (3, 3, 48))


class Rules(unittest.TestCase):
    def test_tile_zone_and_night_hours(self):
        self.assertEqual(eco.tile_epsg("19QHA"), 32619)
        self.assertEqual(eco.tile_epsg("20QKF"), 32620)
        self.assertEqual(eco.local_hour("2025-06-21T06:19:33Z"), 2)
        self.assertEqual(eco.local_hour("2025-06-21T01:00:00Z"), 21)
        self.assertIn(2, eco.NIGHT_HOURS); self.assertIn(21, eco.NIGHT_HOURS)
        self.assertNotIn(19, eco.NIGHT_HOURS); self.assertNotIn(6, eco.NIGHT_HOURS)

    def test_the_token_goes_to_nasa_hosts_only(self):
        sent = []

        class R:
            def __init__(self, code, loc=None):
                self.status_code, self.headers = code, ({"Location": loc} if loc else {})

        class S:
            def get(self, url, headers=None, **kw):
                sent.append((url.split("/")[2], "Authorization" in (headers or {})))
                return R(303, "https://d1nklfio7vscoe.cloudfront.net/x.tif?sig=1")
        url, hops = eco.signed("https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/x.tif", "tok", S())
        self.assertEqual(url, "https://d1nklfio7vscoe.cloudfront.net/x.tif?sig=1")
        self.assertEqual(sent, [("data.lpdaac.earthdatacloud.nasa.gov", True)])
        self.assertTrue(all("sig" not in h for h in hops))


@unittest.skipUnless((DATA / "night_heat_series.json").exists(), "night_heat_series.json is built by the ecostress workflow")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "night_heat_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "night_heat_barrio.json").read_text(encoding="utf-8"))
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
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual(set(self.sv), {"night_lst_med", "night_lst_p90", "night_hot_land_pct", "night_res_hot", "night_res_hot_pct"})
        self.assertEqual(set(self.bv), set(self.sv))
        for v in self.b["vars"]:
            self.assertEqual(len(v["years"][self.Y]), 901)

    def test_ranges(self):
        for lvl in ("m", "b"):
            for a, b in zip(self.col("night_lst_med", lvl), self.col("night_lst_p90", lvl)):
                if a is None:
                    self.assertIsNone(b)
                    continue
                self.assertTrue(5 <= a <= 40 and a <= b <= 45, (a, b))
            for k in ("night_hot_land_pct", "night_res_hot_pct"):
                for x in self.col(k, lvl):
                    self.assertTrue(x is None or 0 <= x <= 100, (k, x))

    def test_residents_add_up_and_never_exceed_the_area(self):
        bres = self.col("night_res_hot", "b")
        for bid, x in zip(self.bids, bres):
            self.assertTrue(x is None or x <= self.pop[bid], bid)
        for f, x in zip(self.s["geo"]["ids"][:-1], self.col("night_res_hot")):
            if x is not None:
                self.assertEqual(x, sum(y for bid, y in zip(self.bids, bres) if bid[:5] == f and y is not None), f)

    def test_the_checks_hold(self):
        med = dict(zip(self.s["geo"]["ids"], self.col("night_lst_med")))
        self.assertGreater(med["72127"], med["72"])
        self.assertLess(med["72073"], med["72"])
        self.assertLess(med["72001"], med["72"])
        self.assertAlmostEqual(self.col("night_hot_land_pct")[-1], 10.0, delta=0.5)
        day = self.s["notes"]["checks"]["pr_morning_median_c"]
        self.assertTrue(day is None or med["72"] < day)


if __name__ == "__main__":
    unittest.main()
