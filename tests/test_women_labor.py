"""Tests for women_labor.py (women in the labor force: labor_sex_series.json and women_labor.json). No network.

  python -m unittest tests.test_women_labor
"""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import women_labor as wl  # noqa: E402

DATA = ROOT / "site" / "data"


class Arithmetic(unittest.TestCase):
    def test_esum(self):
        self.assertEqual(wl.esum([[100, 30], [50, 40]]), [150, 50.0])
        self.assertEqual(wl.esum([[100, None], [50, 0]]), [150, 0.0], "a controlled total has no margin and adds none")
        self.assertIsNone(wl.esum([[100, 30], None]))
        self.assertIsNone(wl.esum([[100, 30], [None, 5]]))

    def test_prop(self):
        # p = 40/100; root = 10^2 - 0.16 * 20^2 = 100 - 64 = 36 -> margin 6/100 = 6 points
        v, m = wl.prop([40, 10], [100, 20])
        self.assertAlmostEqual(v, 40.0)
        self.assertAlmostEqual(m, 6.0)
        # a negative root falls back to the ratio formula: 1 + 0.25 * 100 = 26 -> sqrt(26)/10 * 100
        v, m = wl.prop([5, 1], [10, 10])
        self.assertAlmostEqual(v, 50.0)
        self.assertAlmostEqual(m, 100 * math.sqrt(26) / 10)
        self.assertIsNone(wl.prop(None, [10, 1]))
        self.assertIsNone(wl.prop([1, 1], [0, 1]))

    def test_diff(self):
        d = wl.diff([50, 3], [40, 4])
        self.assertEqual((d["v"], d["m"], d["sig"]), (10, 5.0, True))
        d = wl.diff([41, 3], [40, 4])
        self.assertFalse(d["sig"], "a difference smaller than its margin is not significant")
        self.assertIsNone(wl.diff(None, [1, 1]))

    def test_age_adjust(self):
        n = len(wl.AGES)
        def rec(pops, rates):
            return {"f": [[[p, 0], [p * r, 0], [p * r, 0], [0, 0]] for p, r in zip(pops, rates)]}
        std = rec([100] * n, [0.5] * n)
        # the same rates as the standard but a different age mix: the adjusted rate is the standard's, the whole gap is age mix
        reg = rec([300] + [100] * (n - 1), [0.2] + [0.5] * (n - 1))
        std2 = rec([100] * n, [0.2] + [0.5] * (n - 1))
        a = wl.age_adjust(reg, std2)
        crude_r = (300 * 0.2 + 100 * 0.5 * (n - 1)) / (300 + 100 * (n - 1))
        crude_s = (100 * 0.2 + 100 * 0.5 * (n - 1)) / (100 * n)
        self.assertAlmostEqual(a["crude"], 100 * crude_r)
        self.assertAlmostEqual(a["standard"], 100 * crude_s)
        self.assertAlmostEqual(a["adjusted"], 100 * crude_s)
        self.assertAlmostEqual(a["from_rates"], 0)
        self.assertAlmostEqual(a["from_age_mix"], a["gap"])
        # the same age mix, rates 10 points lower in every group: the gap is all rates
        b = wl.age_adjust(rec([100] * n, [0.4] * n), std)
        self.assertAlmostEqual(b["adjusted"], 40)
        self.assertAlmostEqual(b["from_age_mix"], 0)
        self.assertAlmostEqual(b["from_rates"], -10)
        self.assertAlmostEqual(b["from_age_mix"] + b["from_rates"], b["gap"])


@unittest.skipUnless((DATA / "women_labor.json").exists() and (DATA / "labor_sex_series.json").exists(), "women_labor.json is not built")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "women_labor.json").read_text(encoding="utf-8"))
        cls.ser = json.loads((DATA / "labor_sex_series.json").read_text(encoding="utf-8"))
        cls.cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))

    def test_analysis_file_shape(self):
        d = self.doc
        self.assertEqual(d["window_ends"], [2014, 2019, 2024])
        self.assertEqual(d["windows"], ["2010-2014", "2015-2019", "2020-2024"])
        self.assertEqual(d["ages"], [a for a, _ in wl.AGES])
        self.assertEqual(d["cells"], ["pop", "lf", "clf", "une"])
        for w in map(str, d["window_ends"]):
            areas = d["areas"][w]
            self.assertEqual(len(areas), 79, w)
            self.assertIn("72", areas)
            for g, r in areas.items():
                for sex in ("m", "f"):
                    self.assertEqual(len(r[sex]), len(wl.AGES), (w, g))
                    self.assertTrue(all(len(grp) == 4 for grp in r[sex]), (w, g))
        self.assertIn("sample", d["areas"]["2024"]["72"])
        self.assertEqual(set(d["analysis"]), {"ersv"})
        self.assertEqual(set(d["analysis"]["ersv"]), {"2014", "2019", "2024", "change"})

    def test_series_file_shape(self):
        s = self.ser
        self.assertEqual(s["years"], [2014, 2019, 2024])
        self.assertEqual(s["geo"]["ids"][-1], "72")
        self.assertEqual(len(s["geo"]["ids"]), 79)
        econ = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))
        self.assertEqual(s["geo"]["ids"], econ["geo"]["ids"], "the order of economy_series.json")
        self.assertEqual([v["key"] for v in s["vars"]], [k for k, *_ in wl.SERIES_VARS])
        for v in s["vars"]:
            self.assertEqual(v["sources"], ["acs"])
            self.assertEqual(v["family"], "labor_sex")
            for y in ("2014", "2019", "2024"):
                self.assertEqual(len(v["years"][y]), 79, (v["key"], y))
                self.assertEqual(len(v["moe"][y]), 79, (v["key"], y))
        lf = next(v for v in s["vars"] if v["key"] == "lfpr_women")
        self.assertAlmostEqual(lf["years"]["2024"][-1], round(self.doc["analysis"]["ersv"]["2024"]["island"]["lfpr_f"][0], 1))

    def test_ersv_list(self):
        names = {u[0]: u[2] for u in self.cw["units"]["municipio"]}
        self.assertEqual(len(wl.ERSV), 15)
        self.assertEqual(len(self.doc["groups"]["ersv"]["ids"]), 15)
        self.assertEqual(sorted(self.doc["groups"]["ersv"]["ids"]), sorted(wl.ERSV))
        for g, n in wl.ERSV.items():
            self.assertEqual(names.get(g), n, g)

    def test_pooled_ersv_rate(self):
        """The region's rate is summed labor force over summed population, as published in the analysis."""
        a = self.doc["areas"]["2024"]
        ids = self.doc["groups"]["ersv"]["ids"]
        pop = sum(a[g]["f"][k][0][0] for g in ids for k in range(len(wl.AGES)))
        lf = sum(a[g]["f"][k][1][0] for g in ids for k in range(len(wl.AGES)))
        got = self.doc["analysis"]["ersv"]["2024"]["region"]["lfpr_f"][0]
        self.assertAlmostEqual(100 * lf / pop, got, places=1)
        self.assertEqual(round(pop), round(self.doc["analysis"]["ersv"]["2024"]["region"]["women16"][0]))
        mean = sum(100 * sum(a[g]["f"][k][1][0] for k in range(len(wl.AGES))) / sum(a[g]["f"][k][0][0] for k in range(len(wl.AGES))) for g in ids) / len(ids)
        self.assertAlmostEqual(mean, self.doc["analysis"]["ersv"]["2024"]["unweighted_mean_lfpr_f"], places=1)

    def test_counts_are_consistent(self):
        """In every area, window, sex and age group: population >= labor force >= civilian labor force >= unemployed >= 0; the series counts are the sums over ages."""
        for w, areas in self.doc["areas"].items():
            for g, r in areas.items():
                for sex in ("m", "f"):
                    for k, (pop, lf, clf, une) in enumerate(r[sex]):
                        if pop is None:
                            continue
                        self.assertTrue(pop[0] >= lf[0] >= clf[0] >= une[0] >= 0, (w, g, sex, k))
        ids = self.ser["geo"]["ids"]
        w16 = next(v for v in self.ser["vars"] if v["key"] == "women_16plus")
        wlf = next(v for v in self.ser["vars"] if v["key"] == "women_in_lf")
        for w in ("2014", "2019", "2024"):
            areas = self.doc["areas"][w]
            for i, g in enumerate(ids):
                pop = sum(grp[0][0] for grp in areas[g]["f"])
                lf = sum(grp[1][0] for grp in areas[g]["f"])
                self.assertEqual(w16["years"][w][i], pop, (w, g))
                self.assertEqual(wlf["years"][w][i], lf, (w, g))
                self.assertGreaterEqual(pop, lf)
            # the 78 municipios add up to about the island row (independent estimates, so within the island's margin of the sum)
            isl = sum(grp[0][0] for grp in areas["72"]["f"])
            munis = sum(sum(grp[0][0] for grp in areas[g]["f"]) for g in ids if g != "72")
            self.assertLess(abs(isl - munis) / isl, 0.01, w)


if __name__ == "__main__":
    unittest.main()
