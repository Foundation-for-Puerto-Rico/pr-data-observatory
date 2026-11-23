"""Drought (drought.py, HANDOFF decision 107 step 5): the yearly figures on invented weeks, and the published file.

    python -m unittest tests.test_drought

The published file is checked WITHOUT the cache. Two tests need the cached weeks (the area check and a rebuild) and skip without them.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import drought  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


def week(date, d1, d2=0.0, d3=0.0):
    return {"mapDate": date + "T00:00:00", "d1": d1, "d2": d2, "d3": d3}


class Figures(unittest.TestCase):
    def test_average_share_and_weeks_over_half_the_area(self):
        rows = [week("2015-01-06", 100, 60), week("2015-01-13", 50, 49.9), week("2015-01-20", 49.9), week("2015-01-27", 0)]
        f = drought.figures(drought.by_year(rows)[2015])
        self.assertEqual(f["area"], 50.0)
        self.assertEqual(f["weeks"], 2, "a week counts at exactly half the area, not just under it")
        self.assertEqual(f["severe"], 1)

    def test_weeks_go_to_the_year_of_their_map_date_in_order(self):
        by = drought.by_year([week("2016-01-05", 10), week("2015-12-29", 20), week("2015-12-22", 30)])
        self.assertEqual([w[0] for w in by[2015]], ["2015-12-22", "2015-12-29"])
        self.assertEqual(len(by[2016]), 1)


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "drought_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v for v in cls.doc["vars"]}

    def test_the_areas_are_the_78_municipios_then_puerto_rico(self):
        ids = self.doc["geo"]["ids"]
        self.assertEqual(len(ids), 79)
        self.assertEqual(ids[-1], "72")
        for v in self.doc["vars"]:
            for y, a in v["years"].items():
                self.assertEqual(len(a), 79, (v["key"], y))

    def test_whole_years_have_52_or_53_weeks(self):
        weeks = self.doc["notes"]["weeks"]
        last = str(self.doc["years"][-1])
        for y, n in weeks.items():
            if y != last:
                self.assertIn(n, (52, 53), y)
            self.assertLessEqual(n, 53)

    def test_shares_and_weeks_are_in_range(self):
        for y in self.v["drought_weeks"]["years"]:
            n = self.doc["notes"]["weeks"][y]
            for a, w, s in zip(self.v["drought_area_pct"]["years"][y], self.v["drought_weeks"]["years"][y], self.v["drought_severe_weeks"]["years"][y]):
                self.assertTrue(0 <= a <= 100)
                self.assertTrue(0 <= s <= w <= n, (y, w, s, n))

    def test_the_credit_line_the_drought_monitor_asks_for(self):
        self.assertIn("Data courtesy of NDMC, via https://droughtmonitor.unl.edu", self.doc["sources"]["usdm"]["license"])
        for v in self.doc["vars"]:
            self.assertIn("Data courtesy of NDMC", v["ref"])


class WithCache(unittest.TestCase):
    def setUp(self):
        if not (drought.CACHE / "72.json").exists():
            self.skipTest("no cache (python drought.py --refresh)")

    def test_municipios_weighted_by_land_area_give_puerto_ricos_share(self):
        doc = json.loads((DATA / "drought_series.json").read_text(encoding="utf-8"))
        towns = json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))
        area = {g: towns[n]["land_km2"] for g, n in zip(doc["geo"]["ids"][:78], doc["geo"]["names"][:78])}
        total = sum(area.values())
        acc = {}
        for g, a in area.items():
            for r in json.loads((drought.CACHE / f"{g}.json").read_text(encoding="utf-8")):
                acc[r["mapDate"]] = acc.get(r["mapDate"], 0) + r["d1"] * a / total
        for r in json.loads((drought.CACHE / "72.json").read_text(encoding="utf-8")):
            self.assertAlmostEqual(acc[r["mapDate"]], r["d1"], delta=0.5, msg=r["mapDate"])

    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        _, fips = drought.hs.municipalities()
        doc = drought.documents({g: drought.fetch(g, False) for g in list(fips) + ["72"]})
        old = json.loads((DATA / "drought_series.json").read_text(encoding="utf-8"))
        self.assertEqual({**doc, "built": None}, {**old, "built": None})


if __name__ == "__main__":
    unittest.main()
