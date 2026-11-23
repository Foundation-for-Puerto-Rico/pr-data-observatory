"""Tests for inflation.py and the Inflation page (inflation.html; HANDOFF decision 95, docs/inflation-plan-2026-11.md).

  python -m unittest tests.test_inflation
"""
import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import inflation as I  # noqa: E402

DATA = ROOT / "site" / "data"
PAGE = ROOT / "site" / "inflation.html"

# Social Security's announced cost-of-living adjustments, effective in December of each year (SSA, "Cost-of-Living Adjustments",
# https://www.ssa.gov/oact/cola/colaseries.html). inflation.py computes them from the CPI-W; they must agree.
SSA_COLA = {2007: 2.3, 2008: 5.8, 2009: 0.0, 2010: 0.0, 2011: 3.6, 2012: 1.7, 2013: 1.5, 2014: 1.7, 2015: 0.0, 2016: 0.3, 2017: 2.0, 2018: 2.8,
            2019: 1.6, 2020: 1.3, 2021: 5.9, 2022: 8.7, 2023: 3.2, 2024: 2.5, 2025: 2.8}


class Arithmetic(unittest.TestCase):
    def test_months(self):
        self.assertEqual(I.add((2025, 11), 3), (2026, 2))
        self.assertEqual(I.add((2026, 1), -1), (2025, 12))
        self.assertEqual(list(I.months((2025, 11), (2026, 2))), [(2025, 11), (2025, 12), (2026, 1), (2026, 2)])

    def test_forward_rates_compound_back_to_the_average(self):
        E = [3.0, 2.8, 2.7, 2.65, 2.6]
        f = I.forwards(E)
        self.assertAlmostEqual(f[0], 3.0)
        for k in range(1, 6):
            prod = math.prod(1 + x / 100 for x in f[:k])
            self.assertAlmostEqual(prod, (1 + E[k - 1] / 100) ** k, places=10)

    def test_a_flat_projection_rises_at_the_rate_over_a_year(self):
        S = {(y, m): 100.0 for y in range(2010, 2021) for m in range(1, 13)}   # no seasonal pattern
        P = I.project(S, (2020, 12), [3.0, 3.0], 24)
        self.assertAlmostEqual(P[(2021, 12)] / 100, 1.03, places=10)
        self.assertAlmostEqual(P[(2022, 12)] / 100, 1.03 ** 2, places=10)

    def test_the_seasonal_pattern_sums_to_zero_over_a_year(self):
        S, v = {}, 100.0
        for y in range(2010, 2021):
            for m in range(1, 13):
                v *= 1.002 + (0.004 if m == 8 else 0) - (0.004 / 11 if m != 8 else 0)
                S[(y, m)] = v
        s = I.seasonal(S, (2020, 12))
        self.assertAlmostEqual(sum(s.values()), 0.0, places=9)
        self.assertGreater(s[8], 0.3, "August carries the bump")

    def test_cola_follows_the_rule(self):
        # CPI-W flat, then +2% in the third quarter of 2002: a 2.0% adjustment in 2002, none in 2001 and 2003; the base stays at the last raise
        W = {}
        for y in range(1999, 2005):
            for m in range(1, 13):
                W[(y, m)] = 100.0 if (y, m) < (2002, 7) else 102.0
        c = I.cola(W)
        self.assertEqual((c[2001], c[2002], c[2003]), (0.0, 2.0, 0.0))


class DataFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "inflation.json").read_text(encoding="utf-8"))

    def test_cola_matches_what_social_security_announced(self):
        got = {r["year"]: r["pct"] for r in self.d["cola"]["rows"]}
        for y, v in SSA_COLA.items():
            self.assertEqual(got.get(y), v, f"COLA effective December {y}")

    def test_headline_rates_recompute_from_the_monthly_indexes(self):
        m, h = self.d["monthly"], self.d["headline"]
        s0 = I.idx(tuple(map(int, m["start"].split("-"))))
        pr = {I.mkey(((s0 + i) // 12, (s0 + i) % 12 + 1)): v for i, v in enumerate(m["pr_index"])}
        last = self.d["latest"]["pr"]
        y, mo = map(int, last.split("-"))
        self.assertAlmostEqual(100 * (pr[last] / pr[f"{y - 1}-{mo:02d}"] - 1), h["pr_yoy"], delta=0.051)
        self.assertAlmostEqual(100 * (pr[last] / pr["2000-01"] - 1), h["cum2000"]["pr"], delta=0.051)

    def test_the_series_start_in_2000_and_reach_the_latest_months(self):
        m = self.d["monthly"]
        self.assertEqual(m["start"], "2000-01")
        self.assertEqual(len(m["pr_yoy"]), len(m["us_yoy"]))
        n = I.idx(tuple(map(int, self.d["latest"]["us"].split("-")))) - I.idx((2000, 1)) + 1
        self.assertEqual(len(m["us_index"]), n)
        self.assertNotIn(None, m["pr_yoy"][: I.idx(tuple(map(int, self.d["latest"]["pr"].split("-")))) - I.idx((2000, 1)) + 1])

    def test_the_missing_us_month_is_left_empty_in_the_rates(self):
        miss = self.d["checks"]["us_missing"]
        s0 = I.idx((2000, 1))
        for k in miss:
            i = I.idx(tuple(map(int, k.split("-")))) - s0
            self.assertIsNone(self.d["monthly"]["us_yoy"][i], k)
            if i + 12 < len(self.d["monthly"]["us_yoy"]):
                self.assertIsNone(self.d["monthly"]["us_yoy"][i + 12], f"12 months after {k}")

    def test_bands_contain_the_central_path_and_nest(self):
        for key in ("pr_path", "us_path"):
            for k, c, l8, h8, l9, h9 in self.d["projection"][key]:
                self.assertTrue(l9 <= l8 <= c <= h8 <= h9, (key, k))
        for key in ("pr_years", "us_years"):
            for r in self.d["projection"][key]:
                self.assertTrue(r["lo95"] <= r["lo80"] <= r["c"] <= r["hi80"] <= r["hi95"], (key, r["year"]))

    def test_the_projection_runs_five_years_past_the_latest_year(self):
        p = self.d["projection"]
        self.assertEqual(int(p["end"][:4]), int(self.d["latest"]["pr"][:4]) + 5)
        self.assertEqual(p["pr_path"][-1][0], p["end"])
        self.assertEqual(p["us_path"][-1][0], p["end"])

    def test_the_method_used_is_the_one_the_backtest_supports(self):
        """The page says the US expectation had the smallest error at every horizon; if a refresh changes that, the page must change too."""
        b = self.d["backtest"]
        for h in b["count"]:
            self.assertEqual(min(b["order"], key=lambda n: b["rmse"][n][h]), "us_expected", f"horizon {h}")

    def test_group_weights_are_the_basket(self):
        self.assertAlmostEqual(sum(g["weight"] for g in self.d["groups"]), 100.0, delta=0.1)
        self.assertEqual([g["key"] for g in self.d["groups"]], [g[0] for g in I.GROUPS])

    def test_no_personal_data(self):
        text = (DATA / "inflation.json").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"@[A-Za-z0-9-]+\.[a-z]{2,}", "no e-mail addresses")

    @unittest.skipUnless((ROOT / "cache" / "inflation" / "dtrh_serie_historica.xls").exists(), "needs cache/inflation (python inflation.py)")
    def test_the_file_is_current(self):
        I.OFFLINE = True
        try:
            D = I.build(False)
        finally:
            I.OFFLINE = False
        D["built"] = self.d["built"]
        self.assertEqual(D, self.d, "site/data/inflation.json is out of date: run python inflation.py")


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.d = json.loads((DATA / "inflation.json").read_text(encoding="utf-8"))

    def test_the_page_quotes_the_file(self):
        h = self.d["headline"]
        self.assertIn(f"{h['pr_yoy']:.1f}%", self.html)
        self.assertIn(f"{h['cum2000']['pr']:.1f}%", self.html)
        self.assertIn(f"{h['cum2000']['us']:.1f}%", self.html)

    def test_registry_marks_it_published_in_review_with_ai_under_economy(self):
        knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        self.assertRegex(knowledge, r"id: 'inflation',.*page: 'inflation\.html', status: 'published', review: true, ai: true.*domain: 'economy'")

    def test_noindex_notice_and_header(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("data-ka-note", self.html)
        self.assertIn('data-ka="inflation"', self.html)

    def test_shared_scripts_match_the_other_area_pages(self):
        other = (ROOT / "site" / "urban-heat.html").read_text(encoding="utf-8")
        for name in ("js/core/knowledge.js", "js/common.js", "css/twin.css", "css/housing.css"):
            v = re.search(re.escape(name) + r"\?v=(\d+)", self.html).group(1)
            self.assertEqual(v, re.search(re.escape(name) + r"\?v=(\d+)", other).group(1), name)

    def test_bls_terms(self):
        self.assertIn("BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov.", self.html)

    def test_every_js_string_has_spanish(self):
        js = (ROOT / "site" / "js" / "inflation.js").read_text(encoding="utf-8")
        es = json.loads((ROOT / "i18n_src" / "es" / "inflation.json").read_text(encoding="utf-8"))
        for s in re.findall(r"T\('((?:[^'\\]|\\.)+)'", js):
            s = s.replace("\\'", "'")
            self.assertIn(s, es, s)
        for s in re.findall(r"T\(\"([^\"]+)\"", js):
            self.assertIn(s, es, s)


if __name__ == "__main__":
    unittest.main()
