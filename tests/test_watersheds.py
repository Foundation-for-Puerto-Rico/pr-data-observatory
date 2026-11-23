"""Watersheds, streams and the catchments of What drains here (watersheds.py; docs/watersheds.md): the published files hold a valid network.

    python -m unittest tests.test_watersheds
"""
import json
import unittest
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


@unittest.skipUnless((DATA / "catchments.geojson").exists(), "catchments.geojson is built by watersheds.py")
class Network(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = json.loads((DATA / "catchments.geojson").read_text(encoding="utf-8"))
        cls.w = json.loads((DATA / "watersheds.geojson").read_text(encoding="utf-8"))
        cls.s = json.loads((DATA / "streams.geojson").read_text(encoding="utf-8"))

    def test_links_are_valid_and_acyclic(self):
        f = self.c["features"]
        n = len(f)
        self.assertTrue(12_000 <= n <= 16_000, n)
        dn = [x["properties"]["dn"] for x in f]
        for k, d in enumerate(dn):
            self.assertTrue(d == -1 or (0 <= d < n and d != k), (k, d))
            for v in x_via(f[k]):
                self.assertTrue(0 <= v < n and v != k, (k, v))
        # following dn from every catchment ends at an outlet within n steps (no cycle)
        state = [0] * n
        for start in range(n):
            path, k = [], start
            while k != -1 and state[k] == 0:
                state[k] = 1; path.append(k); k = dn[k]
            self.assertNotEqual(k != -1 and state[k] == 1, True, f"a cycle through {k}")
            for p in path:
                state[p] = 2

    def test_area_and_notes(self):
        km2 = sum(x["properties"]["km2"] for x in self.c["features"])
        self.assertTrue(8_500 <= km2 <= 10_500, km2)
        for m in self.c["notes"]["mouths"]:
            self.assertLess(abs(m["network_km2"] / m["nhdplus_km2"] - 1), 0.03, m)
        names = {m["name"] for m in self.c["notes"]["mouths"]}
        self.assertIn("Río Grande De Loiza", names)

    def test_subwatersheds_and_streams(self):
        h = self.w["features"]
        self.assertTrue(200 <= len(h) <= 260, len(h))
        self.assertTrue(all(x["properties"]["huc12"].startswith("2101") and len(x["properties"]["huc12"]) == 12 for x in h))
        self.assertEqual(len({x["properties"]["huc12"] for x in h}), len(h))
        res = sum(x["properties"]["residents"] for x in h)
        self.assertGreaterEqual(res, 0.99 * self.w["notes"]["residents_pr"])
        self.assertTrue(all(x["properties"]["km2"] >= 5 for x in self.s["features"]))


def x_via(feat):
    return feat["properties"].get("via") or []


if __name__ == "__main__":
    unittest.main()
