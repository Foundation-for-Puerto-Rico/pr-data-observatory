"""Tests for upstream.py (what lies upstream of each reservoir and river gauge; decision 107, step 9, fourth part) and for the coast rule of watersheds.py.

The walk and the outlets run on a small made-up network; the published files are checked for the coast rule, their identities and the check against USGS.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import upstream as U  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"


class Network(unittest.TestCase):
    """0 <- 1 <- 2 and 0 <- 3 (two tributaries); 4 is a minor branch that splits from 2 (via) and reaches the sea on its own at 5: it takes 2's land, not 1's,
    which is downstream of the split."""
    dn = [-1, 0, 1, 0, 5, -1]

    def kids(self):
        k = {}
        for i, d in enumerate(self.dn):
            if d >= 0:
                k.setdefault(d, []).append(i)
        return k

    def test_the_walk_climbs_every_tributary(self):
        self.assertEqual(sorted(U.upstream(self.dn, 0, [None] * 6, self.kids())), [0, 1, 2, 3])
        self.assertEqual(sorted(U.upstream(self.dn, 1, [None] * 6, self.kids())), [1, 2])

    def test_a_minor_branch_takes_the_land_above_its_split(self):
        via = [None, None, None, None, [2], None]
        self.assertEqual(sorted(U.upstream(self.dn, 5, via, self.kids())), [2, 4, 5])

    def test_outlets(self):
        self.assertEqual(U.outlets(self.dn), [0, 0, 0, 0, 5, 5])

    def test_names(self):
        self.assertEqual(U.norm("Río Grande de Loíza"), "grande de loiza")
        self.assertEqual(U.norm("Río Blanco (Lago Blanco)"), "blanco")
        self.assertEqual(U.norm(None), "")


class Coast(unittest.TestCase):
    """watersheds.py stops each river at its last reach: no outlet drains more land than the island's largest river (NHDPlus: Río Grande de Loíza, 749.5 km²)."""

    def test_no_outlet_drains_more_than_the_largest_river(self):
        fc = json.loads((DATA / "catchments.geojson").read_text(encoding="utf-8"))
        dn = [f["properties"]["dn"] for f in fc["features"]]
        km2 = [f["properties"]["km2"] for f in fc["features"]]
        out = U.outlets(dn)
        tot = {}
        for k, o in enumerate(out):
            tot[o] = tot.get(o, 0) + km2[k]
        self.assertLess(max(tot.values()), 760)
        self.assertGreater(len(tot), 500, "each river reaches the sea on its own")


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not U.OUT.exists():
            raise unittest.SkipTest("upstream.json not built")
        cls.d = json.loads(U.OUT.read_text(encoding="utf-8"))
        cls.S = {(r["name"], r["kind"]): r for r in cls.d["sites"]}

    def test_every_site_of_the_two_layers(self):
        n = {k: len(json.loads((DATA / f).read_text(encoding="utf-8"))["features"]) for k, f in (("reservoir", "reservoirs.geojson"), ("gauge", "river_gauges.geojson"))}
        self.assertEqual(sum(1 for r in self.d["sites"] if r["kind"] == "reservoir"), n["reservoir"])
        self.assertEqual(sum(1 for r in self.d["sites"] if r["kind"] == "gauge"), n["gauge"])

    def test_the_land_agrees_with_usgs_for_most_sites(self):
        c = self.d["notes"]["check"]
        self.assertGreaterEqual(c["within"] / c["with_a_usgs_area"], 0.8)
        self.assertTrue(0.9 <= c["median_ratio"] <= 1.1)
        for r in self.d["sites"]:
            if r["agrees"] is not None:
                self.assertEqual(r["agrees"], abs(r["km2"] / r["usgs_km2"] - 1) <= U.AGREE)

    def test_the_big_reservoirs(self):
        """Carraízo holds the Río Grande de Loíza above the dam, with Caguas's plant; La Plata the Río de la Plata (USGS: 538.7 and 468.8 km²)."""
        car, pla = self.S[("Carraízo (Lago Loíza)", "reservoir")], self.S[("La Plata", "reservoir")]
        self.assertAlmostEqual(car["km2"] / car["usgs_km2"], 1, delta=0.05)
        self.assertAlmostEqual(pla["km2"] / pla["usgs_km2"], 1, delta=0.05)
        self.assertIn("Caguas Wastewater Treatment Plant", car["plant_names"])
        self.assertGreater(car["residents"], pla["residents"])

    def test_off_stream_reservoirs_have_no_figures(self):
        off = [r for r in self.d["sites"] if r["withheld"]]
        self.assertTrue(off)
        for r in off:
            self.assertEqual(r["kind"], "reservoir")
            self.assertIsNone(r["usgs_km2"])
            self.assertIsNone(r["residents"])
        self.assertIn("Lago Regulador de Isabela", [r["name"] for r in off])

    def test_shapes_of_the_figures(self):
        for r in self.d["sites"]:
            if r["withheld"]:
                continue
            self.assertGreater(r["km2"], 0)
            self.assertTrue(0 <= r["protected_pct"] <= 100)
            self.assertEqual(r["wastewater_plants"], len(r["plant_names"]))
            self.assertLessEqual(r["housing_units"], r["residents"] + 2000)


if __name__ == "__main__":
    unittest.main()
