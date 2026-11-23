"""The slope of the land (slope.py; docs/slope.md): Horn's method on known surfaces, the block counts, and the published files.

    python -m unittest tests.test_slope
"""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "site" / "data"

try:
    import numpy as np
except ImportError:   # the system Python of some machines
    np = None


@unittest.skipIf(np is None, "numpy is not installed")
class Method(unittest.TestCase):
    def test_horn_gives_the_slope_of_a_plane(self):
        import slope
        dx, dy = 9.78, 10.29
        r, c = np.mgrid[0:14, 0:14].astype(float)
        for gx, gy in ((0.10, 0.0), (0.0, -0.25), (0.3, 0.4)):          # rise per metre east and north
            z = gx * c * dx - gy * r * dy                                # rows run south
            s = slope.horn(z, dx, dy)
            self.assertEqual(s.shape, (12, 12))
            self.assertTrue(np.allclose(s, math.hypot(gx, gy) * 100), (gx, gy, float(s.mean())))
        z = np.full((5, 5), 40.0); z[0, 0] = np.nan
        s = slope.horn(z, dx, dy)
        self.assertTrue(np.isnan(s[0, 0]) and np.allclose(s[1:, 1:], 0), "a cell next to one with no height has no slope; flat ground is 0")

    def test_blocks_count_the_cells_over_each_threshold(self):
        import slope
        s = np.full((6, 12), 10.0)
        s[:, 6:] = 40.0
        s[0, 0] = np.nan; s[0, 6] = 20.0
        n, (s15, s30), tot = slope.blocks(s)
        self.assertEqual(n.tolist(), [[35, 36]])
        self.assertEqual(s15.tolist(), [[0, 36]])
        self.assertEqual(s30.tolist(), [[0, 35]])
        self.assertAlmostEqual(float(tot[0, 0]), 350.0)
        self.assertAlmostEqual(float(tot[0, 1]), 35 * 40 + 20)

    def test_metres_per_degree(self):
        import slope
        mx, my = slope.deg_m(18.2)
        self.assertAlmostEqual(mx, 105_800, delta=200)
        self.assertAlmostEqual(my, 110_700, delta=100)


@unittest.skipUnless((DATA / "slope_series.json").exists(), "slope_series.json is built by slope.py")
class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "slope_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "slope_barrio.json").read_text(encoding="utf-8"))
        cls.m = json.loads((DATA / "slope_surface.json").read_text(encoding="utf-8"))

    def vals(self, key, f=None):
        f = f or self.s
        v = next(x for x in f["vars"] if x["key"] == key)
        return v["years"][next(iter(v["years"]))]

    def test_shapes_and_keys(self):
        self.assertEqual(self.s["geo"]["ids"][-1], "72")
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual([v["key"] for v in self.s["vars"]], ["slope_steep15_pct", "slope_steep30_pct", "slope_mean"])
        self.assertEqual([v["key"] for v in self.b["vars"]], ["slope_steep15_pct", "slope_steep30_pct", "slope_mean"])
        for k in ("slope_steep15_pct", "slope_steep30_pct", "slope_mean"):
            self.assertEqual(len(self.vals(k)), 79)
            self.assertEqual(len(self.vals(k, self.b)), len(self.b["geo"]["ids"]))

    def test_shares_are_ordered_and_in_range(self):
        for f in (self.s, self.b):
            for a, c in zip(self.vals("slope_steep15_pct", f), self.vals("slope_steep30_pct", f)):
                if a is None:
                    self.assertIsNone(c)
                    continue
                self.assertTrue(0 <= c <= a <= 100, (a, c))

    def test_the_mountains_are_steeper_than_the_coast(self):
        ids = self.s["geo"]["ids"]
        s30 = dict(zip(ids, self.vals("slope_steep30_pct")))
        for hill in ("72073", "72107", "72019"):                 # Jayuya, Orocovis, Barranquitas
            self.assertGreater(s30[hill], s30["72"])
        self.assertLess(s30["72033"], 1)                         # Cataño

    def test_image_metadata(self):
        self.assertEqual(self.m["image"], "slope_surface.png")
        self.assertEqual(self.m["scale"]["low"], 0.0)
        self.assertEqual(self.m["scale"]["high"], 60.0)
        self.assertLessEqual(self.m["size"][0], 4096)
        w, s, e, n = self.m["bounds"]
        self.assertTrue(-67.4 < w < -67.2 and 17.8 < s < 17.95 and -65.3 < e < -65.1 and 18.5 < n < 18.6, self.m["bounds"])
        png = (DATA / "slope_surface.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
