"""Tests for hexgrid.py (the hexagon grid of 1 km²; decision 107, step 9, parts 1 and 2).

The Python port must give the same cell ids as the map's own core/hexbin.js (run in Node), every cell must be 1 km², and the published file must add up to
the island's residents, housing units and buildings.
"""
import json
import math
import random
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hexgrid as H  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Port(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_same_cells_as_hexbin_js(self):
        rnd = random.Random(20261119)
        pts = [(rnd.uniform(17.88, 18.52), rnd.uniform(-67.3, -65.2)) for _ in range(2000)]
        js = ("const hb = require(%s); let raw = ''; process.stdin.on('data', c => raw += c); process.stdin.on('end', () => {"
              "const out = JSON.parse(raw).map(([la, lo]) => hb.bin([{ lat: la, lng: lo }], { area: 1 }).cells[0].id); process.stdout.write(JSON.stringify(out)); });"
              % json.dumps(str(ROOT / "site" / "js" / "core" / "hexbin.js")))
        got_js = json.loads(subprocess.run(["node", "-e", js], input=json.dumps(pts), capture_output=True, text=True, check=True).stdout)
        q, r = H.ids_of([p[0] for p in pts], [p[1] for p in pts], H.size())
        self.assertEqual([f"{a},{b}" for a, b in zip(q.tolist(), r.tolist())], got_js)

    def test_a_cell_is_one_square_kilometre_and_holds_its_centre(self):
        s = H.size()
        self.assertAlmostEqual(3 * math.sqrt(3) / 2 * s * s, 1.0, places=9)
        for q, r in ((0, 0), (40, -12), (-80, 30)):
            ring = H.corners(q, r, s)[:-1]
            la = sum(p[1] for p in ring) / 6
            lo = sum(p[0] for p in ring) / 6
            cq, cr = H.ids_of([la], [lo], s)
            self.assertEqual((int(cq[0]), int(cr[0])), (q, r))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not H.OUT.exists():
            raise unittest.SkipTest("hex_grid.geojson not built")
        cls.d = json.loads(H.OUT.read_text(encoding="utf-8"))

    def test_the_cells_add_up_to_the_island(self):
        f = [x["properties"] for x in self.d["features"]]
        t = self.d["notes"]["totals"]
        self.assertEqual(sum(p["p"] for p in f), t["residents"])
        self.assertEqual(sum(p["h"] for p in f), t["housing_units"])
        self.assertEqual(sum(p["b"] for p in f), t["buildings"])
        self.assertEqual(t["residents"], 3285874)
        self.assertEqual(len({p["id"] for p in f}), len(f))

    def test_shares_are_shares_and_empty_where_no_one_lives(self):
        for p in (x["properties"] for x in self.d["features"]):
            self.assertTrue(0 <= p["bf"] <= 100)
            if p["p"]:
                self.assertTrue(0 <= p["pf"] <= 100)
            else:
                self.assertIsNone(p["pf"])

    def test_the_surfaces_are_in_range_and_cover_the_island(self):
        """Step 9, second part: heat (°C), greenness (NDVI) and slope (%) per hexagon, empty only where a hexagon is mostly sea."""
        f = [x["properties"] for x in self.d["features"]]
        for k, lo, hi in (("t", 15, 60), ("g", -1, 1), ("s", 0, 200)):
            v = [p[k] for p in f if p[k] is not None]
            self.assertTrue(all(lo <= x <= hi for x in v), k)
            self.assertGreater(len(v), 0.97 * len(f), f"{k} covers the land")
        lived = [p for p in f if p["p"]]
        self.assertGreater(sum(p["t"] is not None for p in lived), 0.98 * len(lived))
        self.assertEqual(self.d["notes"]["surfaces"]["cells_with"], {k: sum(p[k] is not None for p in f) for k in "tgs"})

    def test_the_surfaces_follow_the_barrio_files_physics(self):
        """San Juan hotter and less green than the mountains (heat.py's and vegetation.py's own checks), and the mountains steeper."""
        P = {x["properties"]["id"]: x["properties"] for x in self.d["features"]}
        s = H.size()

        def at(lat, lng):
            q, r = H.ids_of([lat], [lng], s)
            return P[f"{int(q[0])},{int(r[0])}"]
        hato_rey, jayuya, yunque = at(18.42, -66.06), at(18.22, -66.59), at(18.30, -65.79)
        self.assertGreater(hato_rey["t"], jayuya["t"])
        self.assertGreater(jayuya["t"], yunque["t"])
        self.assertLess(hato_rey["g"], jayuya["g"])
        self.assertLess(jayuya["g"], yunque["g"])
        self.assertLess(hato_rey["s"], jayuya["s"])

    def test_the_flood_count_matches_the_exposure_series(self):
        e = json.loads((ROOT / "site" / "data" / "exposure_municipio.json").read_text(encoding="utf-8"))
        self.assertEqual(self.d["notes"]["residents_in_flood_area"], sum(e["vars"]["flood_sfha"]["pop"]))


class ByCell(unittest.TestCase):
    def test_medians_and_weighted_means_per_hexagon(self):
        q, r = np.array([0, 0, 0, -3, -3]), np.array([1, 1, 1, -2, -2])
        self.assertEqual(H.by_cell(q, r, np.array([1.0, 5.0, 2.0, np.nan, 7.0])), {(0, 1): (2.0, 3), (-3, -2): (7.0, 1)})
        self.assertEqual(H.by_cell(q, r, np.array([10.0, 30.0, 0.0, 4.0, 6.0]), np.array([1.0, 1.0, 2.0, 1.0, 1.0])), {(0, 1): (10.0, 4.0), (-3, -2): (5.0, 2.0)})


if __name__ == "__main__":
    unittest.main()
