"""Storm recovery from night-time light (storm_recovery.py, HANDOFF decision 107 step 5, second part): the rule on invented months, and the published files.

    python -m unittest tests.test_storm_recovery
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import storm_recovery as sr  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


def months(before, after):
    """Twelve months before the storm (index 12 is the storm month), then the months after."""
    return list(before) + list(after)


class Rule(unittest.TestCase):
    def test_back_needs_two_months_in_a_row_at_80_percent_of_the_same_month(self):
        base = [10.0] * 12
        s = months(base, [2, 9, 5, 8, 8.5, 9])   # October at 90% alone, then December and January both at 80% or more
        self.assertEqual(sr.recovery(s, 12)[:2], (3, 20), "back in December, 3 months from September; lowest 20%")

    def test_exactly_80_percent_counts(self):
        s = months([10.0] * 12, [3, 8, 8])
        self.assertEqual(sr.recovery(s, 12)[0], 1, "1 means back by October")

    def test_each_month_is_compared_with_its_own_month_the_year_before(self):
        base = [10.0] * 12
        base[1] = 5.0   # a dark October the year before
        s = months(base, [1, 4.5, 8.0])
        self.assertEqual(sr.recovery(s, 12)[0], 1, "October at 4.5 is 90% of last October's 5 (but under half the year's mean), November at 8 is 80% of 10")
        s = months(base, [1, 4.5, 4.0])
        self.assertEqual(sr.recovery(s, 12)[2], "not_back", "November at 4 is 40% of last November's 10")

    def test_too_dim_to_read(self):
        s = months([0.4] * 12, [0.1, 0.4, 0.4])
        self.assertEqual(sr.recovery(s, 12), (None, None, "dim"))

    def test_not_back_by_the_last_month(self):
        s = months([10.0] * 12, [1, 5, 6, 7])
        self.assertEqual(sr.recovery(s, 12), (None, 10, "not_back"))

    def test_the_lowest_month_looks_seven_months_from_september(self):
        s = months([10.0] * 12, [9, 9, 9, 9, 9, 9, 9, 1, 9, 9])
        self.assertEqual(sr.recovery(s, 12)[1], 90, "the eighth month (April) is outside the window")


class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "storm_recovery_series.json").read_text(encoding="utf-8"))
        cls.bar = json.loads((DATA / "storm_recovery_barrio.json").read_text(encoding="utf-8"))
        cls.mon = json.loads((DATA / "nightlights_monthly.json").read_text(encoding="utf-8"))

    def test_the_years_are_the_two_storms(self):
        self.assertEqual(self.doc["years"], [2017, 2022])
        self.assertEqual([self.doc["notes"]["storms"][y]["name"] for y in ("2017", "2022")], ["María", "Fiona"])

    def test_areas_follow_the_monthly_file(self):
        self.assertEqual(self.doc["geo"]["ids"], self.mon["municipio"]["ids"])
        self.assertEqual(self.doc["geo"]["ids"][-1], "72")
        self.assertEqual(self.bar["geo"]["ids"], self.mon["barrio"]["ids"])
        for d in (self.doc, self.bar):
            for v in d["vars"]:
                for y, a in v["years"].items():
                    self.assertEqual(len(a), len(d["geo"]["ids"]), (v["key"], y))

    def test_values_are_in_range_and_dim_barrios_have_none(self):
        notes = self.doc["notes"]
        for d in (self.doc, self.bar):
            v = {x["key"]: x for x in d["vars"]}
            for y in ("2017", "2022"):
                for m, low in zip(v["storm_months_back"]["years"][y], v["storm_low_light_pct"]["years"][y]):
                    self.assertEqual(m is None, low is None, "a dim area has neither figure")
                    if m is not None:
                        self.assertGreaterEqual(m, 1)
                        self.assertTrue(0 <= low <= 200, low)
        for y in ("2017", "2022"):
            self.assertEqual(sum(m is None for m in {x["key"]: x for x in self.bar["vars"]}["storm_months_back"]["years"][y]), notes["barrio"][y]["dim"] + notes["barrio"][y]["not_back"])

    def test_the_island_agrees_with_the_restoration_record(self):
        st = self.doc["notes"]["storms"]
        self.assertLessEqual(st["2017"]["island_back"], 9, "98.4% of customers were restored by mid-May 2018 (8 months)")
        self.assertGreaterEqual(st["2017"]["island_back"], 6)
        self.assertEqual(st["2022"]["island_back"], 1, "90% of customers were restored on 2022-10-01")
        self.assertLess(st["2017"]["island_lowest_pct"], 40, "the island lost most of its light after María")

    def test_the_file_is_what_the_monthly_file_gives(self):
        self.assertEqual(sr.build(check=True), 0)

    def test_every_variable_names_its_barrio_file(self):
        for v in self.doc["vars"]:
            self.assertEqual(v["barrioFile"], "storm_recovery_barrio.json")
            self.assertIn("proxy", v["definition"])


if __name__ == "__main__":
    unittest.main()
