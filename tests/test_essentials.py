"""Tests for essentials.py (road distance to a supermarket, food store, pharmacy, bank, library and fire station; decision 107, step 6).

The rules that pick the shops, the roll-up over residents and the check are tested without data; the published files are checked against the crosswalk and the
dictionary's quoted figures; with the local cache (cache/essentials/points.json) a rebuild must give the published files.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import essentials as E  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"


class Rules(unittest.TestCase):
    def test_supermarkets_by_name_and_colmados_left_out(self):
        for cat, name, want in [("grocery_store", "Supermercado Econo Cayey", "supermarket"), ("grocery_store", "Econo", "supermarket"), ("grocery_store", "Pueblo Ponce", "supermarket"),
                                ("grocery_store", "Colmado El Pueblo", None), ("grocery_store", "Mr Donuts Aguada Pueblo", None), ("grocery_store", "El Amigo Nutrition", None),
                                ("grocery_store", "Doña Elena Mini Market", None), ("grocery_store", "Superdescuentos Morales Market", "supermarket"),
                                ("convenience_store", "Supermercado Isla Nena", "supermarket"), ("convenience_store", "Colmado el Mambo", None),
                                ("department_store", "Walmart Supercenter", "supermarket"), ("pharmacy", "Walmart Pharmacy", "pharmacy"), ("money_transfer_service", "Walmart MoneyCenter", None),
                                ("drugstore", "Walgreens", "pharmacy"), ("credit_union", "Cooperativa Caguas", "bank"), ("atm", "ATH Popular", None)]:
            self.assertEqual(E.classify(cat, name), want, f"{cat} {name}")

    def test_roll_up_weights_by_residents_and_skips_what_cannot_be_measured(self):
        blocks = [("b1", 100, 0, 0), ("b2", 300, 0, 0), ("b3", 50, 0, 0), ("b4", 0, 0, 0)]
        mean, w = E.roll_up(blocks, [0, 0, 1, 0], 2, [1.0, 3.0, None, 9.0])
        self.assertEqual(mean, [2.5, None])
        self.assertEqual(w, [400, 0])
        self.assertEqual(E.share_far(blocks, [0, 0, 1, 0], 2, [1.0, 6.0, None, 9.0]), [75.0, None])

    def test_the_check_matches_within_300_m(self):
        ours = [[-66.0, 18.0]]
        self.assertEqual(E.matched_share([[-66.0, 18.002], [-66.0, 18.01]], ours), 50.0)   # about 220 m and 1.1 km
        self.assertIsNone(E.matched_share([], ours))

    def test_openstreetmap_fills_only_the_gaps(self):
        doc = {"points": [["supermarket", -66.0, 18.0], ["grocery", -66.0, 18.0]], "osm": [["supermarket", -66.0, 18.001], ["supermarket", -66.1, 18.1], ["pharmacy", -66.2, 18.2]]}
        c = E.combined(doc)
        self.assertEqual(c["supermarket"], [[-66.0, 18.0], [-66.1, 18.1]])
        self.assertEqual(c["grocery"], [[-66.0, 18.0], [-66.1, 18.1]], "an OpenStreetMap supermarket is also a food store")
        self.assertEqual(c["pharmacy"], [[-66.2, 18.2]])


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (E.OUT_SERIES.exists() and E.OUT_BARRIO.exists()):
            raise unittest.SkipTest("essentials files not built")
        cls.s = json.loads(E.OUT_SERIES.read_text(encoding="utf-8"))
        cls.b = json.loads(E.OUT_BARRIO.read_text(encoding="utf-8"))
        cls.cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        cls.y = str(cls.s["years"][0])

    def test_areas_are_the_crosswalks(self):
        self.assertEqual(self.s["geo"]["ids"], [r[0] for r in self.cw["units"]["municipio"]] + ["72"])
        self.assertEqual(self.b["geo"]["ids"], [r[0] for r in self.cw["units"]["barrio"]])
        self.assertEqual([v["key"] for v in self.s["vars"]], [v["key"] for v in self.b["vars"]])

    def test_values_are_plausible_and_labelled_estimates(self):
        for v in self.s["vars"]:
            self.assertIn("(estimate,", v["label"])
            self.assertEqual(v["type"], "rate", "a distance or share must not be shaded per 1,000 residents")
            vals = [x for x in v["years"][self.y] if x is not None]
            self.assertGreater(len(vals), 70)
            hi = 100 if v["unit"] == "%" else 30
            self.assertTrue(all(0 <= x <= hi for x in vals), v["key"])
        isl = {v["key"]: v["years"][self.y][-1] for v in self.s["vars"]}
        self.assertLess(isl["ess_grocery_km"], isl["ess_supermarket_km"])

    def test_a_barrio_with_no_residents_has_no_value(self):
        pop = {r[0]: r[6] for r in self.cw["units"]["barrio"]}
        for v in self.b["vars"]:
            for i, x in zip(self.b["geo"]["ids"], v["years"][self.y]):
                if pop[i] == 0:
                    self.assertIsNone(x, f"{v['key']} {i}")

    def test_figures_quoted_in_the_dictionary_still_hold(self):
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "essentials.json").read_text(encoding="utf-8"))}
        for v in self.s["vars"]:
            self.assertIn(f"{v['years'][self.y][-1]}", ents["essentials." + v["key"]]["how_to_read"], v["key"])


@unittest.skipUnless(E.POINTS.exists() and (ROOT / "cache" / "network").exists(), "needs cache/essentials/points.json and the block table (python essentials.py --refresh)")
class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_files(self):
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            self.assertEqual(E.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
