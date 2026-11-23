"""Tests for environment_series.py (Phase 3, item 11): what is kept, how earthquakes and wetlands are placed, and the published files. No network."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import environment_series as env  # noqa: E402

DATA = ROOT / "site" / "data"


class Kept(unittest.TestCase):
    def test_the_caches_hold_no_names(self):
        p = env.CACHE / "slope_failures_maria.json"
        if p.exists():
            pts = json.loads(p.read_text(encoding="utf-8"))
            self.assertTrue(all(isinstance(x, list) and len(x) == 2 for x in pts[:500]), "points only: the copy's municipio and barrio fields are not kept")
        p = env.CACHE / "nwi_wetlands.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["polys"][:500]:
                self.assertEqual(set(r), {"a", "t", "g"})
                self.assertIn(r["t"], env.WETLAND)

    def test_no_published_file_holds_a_point(self):
        for f in ("environment_series.json", "hazard_series.json"):
            p = DATA / f
            if p.exists():
                self.assertNotRegex(p.read_text(encoding="utf-8"), r"-6[5-8]\.\d{4,}", f"{f}: a longitude")


class Placing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import housing_series as hs
        if not (DATA / "municipios.geojson").exists():
            raise unittest.SkipTest("no boundaries")
        cls.M = env.Munis(hs.municipalities()[1])
        cls.by_name = dict(zip(*hs.municipalities()))

    def test_a_point_on_land_goes_to_its_municipio(self):
        self.assertEqual(self.M.points([[-66.06, 18.43]], 25), [self.by_name["San Juan"]])   # Hato Rey
        self.assertEqual(self.M.points([[-66.72, 18.25]], 25), [self.by_name["Utuado"]])

    def test_offshore_goes_to_the_nearest_within_the_limit(self):
        self.assertEqual(self.M.points([[-66.92, 17.92]], 25), [self.by_name["Guánica"]])   # just off Guánica, the 2020 sequence
        self.assertEqual(self.M.points([[-66.5, 17.3]], 25), [None])                          # about 60 km south: left out
        self.assertEqual(self.M.points([[-66.5, 17.3]], 80)[0] is not None, True)

    def test_esri_rings_with_a_hole(self):
        outer = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]   # clockwise: an outer ring
        hole = [[2, 2], [4, 2], [4, 4], [2, 4], [2, 2]]        # counter-clockwise: a hole
        self.assertAlmostEqual(env.rings_polygon([outer, hole]).area, 96)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "environment_series.json").exists():
            raise unittest.SkipTest("not built")
        cls.e = json.loads((DATA / "environment_series.json").read_text(encoding="utf-8"))
        cls.h = json.loads((DATA / "hazard_series.json").read_text(encoding="utf-8"))
        cls.E = {v["key"]: list(v["years"].values())[0] for v in cls.e["vars"]}
        cls.H = {v["key"]: v for v in cls.h["vars"]}

    def test_shape(self):
        for d in (self.e, self.h):
            self.assertEqual(len(d["geo"]["ids"]), 79)
            for v in d["vars"]:
                for a in v["years"].values():
                    self.assertEqual(len(a), 79, v["key"])
                for a in (v.get("moe") or {}).values():
                    self.assertEqual(len(a), 79, v["key"])

    def test_nri(self):
        n = self.e["notes"]["nri"]
        self.assertEqual(n["filled_now"], [], "FEMA filled a Puerto Rico score: publish it and update docs/environment.md")
        total = self.E["nri_eal_total"]
        self.assertAlmostEqual(total[-1], sum(total[:78]), delta=1)
        parts = sum(self.E[f"nri_eal_{k}"][-1] for k, _, _ in env.NRI_HAZ)
        self.assertLess(parts, total[-1], "six of the 18 hazards add up to less than the total")
        self.assertAlmostEqual(total[-1] / 1e9, 3.19, delta=0.3)   # the plan's figure for the December 2025 version

    def test_counts_add_up(self):
        for k in ("landslides_maria", "wetland_km2", "mangrove_km2"):
            self.assertAlmostEqual(self.E[k][-1], sum(self.E[k][:78]), delta=0.05, msg=k)
        for i in range(79):
            self.assertLessEqual(self.E["mangrove_km2"][i], self.E["wetland_km2"][i] + 0.01)
        self.assertEqual(self.E["landslides_maria"][-1], self.e["notes"]["landslides"]["placed"])
        for k in ("quakes_m25", "quakes_m4"):
            for y, a in self.H[k]["years"].items():
                self.assertEqual(a[-1], sum(a[:78]), f"{k} {y}: each earthquake counts once")
        for y in self.H["quakes_m4"]["years"]:
            for i in range(79):
                self.assertLessEqual(self.H["quakes_m4"]["years"][y][i], self.H["quakes_m25"]["years"][y][i])

    def test_resilience_shares(self):
        keys = [k for k, _ in env.CRE_KEYS]
        for y in self.H[keys[0]]["years"]:
            for i in range(79):
                self.assertAlmostEqual(sum(self.H[k]["years"][y][i] for k in keys), 100, delta=0.5)
        self.assertNotIn("2020", self.H[keys[0]]["years"], "no 2020 release")

    def test_known_figures(self):
        self.assertEqual(self.E["landslides_maria"][-1], 71431)
        self.assertGreater(self.H["quakes_m25"]["years"]["2020"][-1], 5000)   # the southwest sequence

    def test_every_variable_has_an_entry_and_spanish(self):
        ids = {e["id"] for e in json.loads((ROOT / "dictionary_src" / "entries" / "environment.json").read_text(encoding="utf-8"))}
        es = json.loads((ROOT / "i18n_src" / "es" / "labels_environment.json").read_text(encoding="utf-8"))
        for d in (self.e, self.h):
            for v in d["vars"]:
                self.assertIn("environment." + v["key"], ids)
                self.assertIn(v["label"], es)
                self.assertIn("Environment · " + v["group"], es)


if __name__ == "__main__":
    unittest.main()
