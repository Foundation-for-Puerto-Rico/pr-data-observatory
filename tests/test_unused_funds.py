"""Federal grants that ended with an unpaid balance (unused_funds.json, unused_funds.py, HANDOFF decision 110, step 1): the rule for "ended" and for
"keeps a balance", the programs kept apart, no recipient in the file, sums that agree with each other, and a page whose figures are the file's.
The rebuild from the cache is compared with the published file when the cache is present."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import unused_funds as U  # noqa: E402

OUT = ROOT / "site" / "data" / "unused_funds.json"
PAGE = ROOT / "site" / "unused-funds.html"


class Rules(unittest.TestCase):
    def test_the_awards_read(self):
        self.assertEqual(U.FIRST_YEAR, 2020)   # USAspending has outlays from fiscal year 2020
        self.assertIn("97.036", U.EXCLUDE)
        apart = [c for v in U.APART.values() for c in v["listings"]]
        self.assertEqual(len(apart), len(set(apart)))
        for c in ("93.778", "93.558", "66.959", "66.616"):   # Medicaid, TANF (no deadline), and two programs the federal government ended in 2025
            self.assertIn(c, apart)
        for v in U.APART.values():
            self.assertGreater(len(v["why"]), 40)
        self.assertIn("84.010", U.NOTES)                      # Title I stays in the figures, with a note
        self.assertIn("Start Date", U.FIELDS)

    def test_only_awards_that_began_in_the_years_read_are_counted(self):
        # the search also returns older awards that were only amended in those years (the review of 2026-11-19 found one that ended in 2018)
        self.assertTrue(U.in_universe(["10.001", 1.0, 1.0, "2022-09-30", "A", "2019-10-01"]))
        self.assertFalse(U.in_universe(["10.001", 1.0, 1.0, "2022-09-30", "A", "2019-09-30"]))
        self.assertFalse(U.in_universe(["10.001", 1.0, 1.0, "2018-09-30", "A", "2015-01-01"]))
        self.assertFalse(U.in_universe(["10.001", 1.0, 1.0, "2022-09-30", "A", ""]))
        self.assertNotIn("Recipient Name", U.FIELDS)
        self.assertIn("End Date", U.FIELDS)

    def test_cutoff_is_one_year_before_the_read_date(self):
        self.assertEqual(U.cutoff("2026-11-17"), "2025-11-17")
        self.assertEqual(U.cutoff("2028-02-29"), "2027-02-28")

    def test_unpaid_is_never_negative(self):
        self.assertEqual(U.unpaid(100.0, 40.0), 60.0)
        self.assertEqual(U.unpaid(100.0, 140.0), 0.0)
        self.assertEqual(U.unpaid(100.0, -5.0), 100.0)   # a negative outlay is not a payment

    def test_keeps_balance(self):
        self.assertTrue(U.keeps_balance(100_000.0, 90_000.0))      # 10%, $10,000
        self.assertFalse(U.keeps_balance(100_000.0, 96_000.0))     # 4%
        self.assertFalse(U.keeps_balance(10_000.0, 9_100.0))       # 9% but $900
        self.assertFalse(U.keeps_balance(100_000.0, None))         # no outlay reported is not an unpaid balance
        self.assertFalse(U.keeps_balance(0.0, 0.0))

    def test_summarise(self):
        awards = [["10.001", 100_000.0, 20_000.0, "2024-01-31", "A", "2021-01-01"],   # ended, keeps a balance
                  ["10.001", 100_000.0, 99_000.0, "2024-01-31", "A", "2021-01-01"],   # ended, paid
                  ["10.002", 50_000.0, None, "2023-06-30", "B", "2021-01-01"],        # ended, no outlay reported
                  ["10.003", 70_000.0, 0.0, "2026-06-30", "B", "2021-01-01"],         # not ended
                  ["10.004", 70_000.0, 0.0, "", "B", "2021-01-01"]]                   # no end date
        s, kept = U.summarise(awards, "2025-11-17")
        self.assertEqual((s["awards"], s["ended"], s["no_outlay"], s["with_balance"]), (5, 3, 1, 1))
        self.assertEqual((s["ended_paid"], s["ended_unpaid"], s["with_balance_unpaid"], s["no_outlay_obligated"]), (119_000, 81_000, 80_000, 50_000))
        self.assertEqual([a[0] for a in kept], ["10.001"])

    def test_the_last_final_year(self):
        from datetime import date
        self.assertEqual(U.last_final_year(date(2026, 11, 14)), 2025)
        self.assertEqual(U.last_final_year(date(2026, 11, 15)), 2026)


@unittest.skipUnless(OUT.exists(), "unused_funds.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_shape(self):
        d = self.d
        self.assertEqual(d["years"][0], 2020)
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        self.assertEqual(d["ended_before"], U.cutoff(d["read"]))
        self.assertEqual(set(d["apart"]), set(U.APART))
        self.assertGreater(d["totals"]["older_left_out"], 0)
        self.assertTrue(all(y >= d["years"][0] - 1 for y, _n, _u in d["end_years"]), "no grant of the years read ended before they began")
        self.assertEqual(sum(r[1] for r in d["no_outlay"]), d["totals"]["no_outlay"])
        self.assertLessEqual(abs(sum(r[2] for r in d["no_outlay"]) - d["totals"]["no_outlay_obligated"]), len(d["no_outlay"]))
        for r in d["listings"]:
            self.assertEqual(len(r), 6)
            self.assertTrue(r[1], f"{r[0]} has no name")

    def test_no_recipient_and_no_award_is_in_the_file(self):
        text = OUT.read_text(encoding="utf-8").lower()
        for word in ("recipient", "award id", "uei", "duns"):
            self.assertNotIn(word, text.replace("no recipient", ""))

    def test_the_three_breakdowns_add_up_to_the_totals(self):
        d, t = self.d, self.d["totals"]
        for name, n, usd in (("agencies", 1, 3), ("listings", 3, 5), ("end_years", 1, 2)):
            self.assertEqual(sum(r[n] for r in d[name]), t["with_balance"], name)
            self.assertLessEqual(abs(sum(r[usd] for r in d[name]) - t["with_balance_unpaid"]), len(d[name]), name)
        self.assertLessEqual(abs(sum(r[2] for r in d["agencies"]) - t["with_balance_obligated"]), len(d["agencies"]))

    def test_the_programs_kept_apart_and_left_out_are_in_no_breakdown(self):
        codes = {r[0] for r in self.d["listings"]}
        self.assertFalse(codes & ({c for v in U.APART.values() for c in v["listings"]} | set(U.EXCLUDE)))

    def test_orders_of_magnitude(self):
        t = self.d["totals"]
        self.assertGreaterEqual(t["awards"], t["ended"])
        self.assertGreaterEqual(t["ended"], t["with_balance"] + t["no_outlay"])
        self.assertGreaterEqual(t["ended_obligated"], t["ended_paid"])
        self.assertGreaterEqual(t["ended_unpaid"], t["with_balance_unpaid"])
        self.assertGreater(t["with_balance_obligated"], t["with_balance_unpaid"])
        for r in self.d["listings"]:
            self.assertGreaterEqual(r[4] + 1, r[5], r[0])
            self.assertGreaterEqual(r[5], U.MIN_USD, r[0])

    def test_every_program_is_read(self):
        # no program is singled out: the workforce listings are lines like any other, and many agencies and programs are present
        self.assertGreater(len({r[0] for r in self.d["listings"]}), 100)
        self.assertGreater(len(self.d["agencies"]), 8)

    def test_the_file_is_what_the_cache_gives(self):
        if not (U.CACHE / "index.json").exists():
            self.skipTest("no cache of the awards")
        self.assertEqual(U.build(check=True), 0)


@unittest.skipUnless(OUT.exists() and PAGE.exists(), "the page is not built")
class Page(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))
        self.html = PAGE.read_text(encoding="utf-8")

    def test_the_page_is_in_review_and_not_indexed(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("data-ka-note", self.html)
        self.assertIn('data-ka="unusedfunds"', self.html)
        item = next(i for i in json.loads((ROOT / "knowledge_src" / "items.json").read_text(encoding="utf-8"))["items"] if i["id"] == "unusedfunds")
        self.assertEqual((item["status"], item.get("review"), item.get("ai"), item["reviewer"]), ("published", True, True, ["compliance"]))

    def test_the_page_quotes_the_file(self):
        t = self.d["totals"]
        lede = re.search(r'<p class="lede">(.*?)</p>', self.html, re.S).group(1)
        for v in (f"{t['awards']:,}", f"{t['ended']:,}", f"{t['with_balance']:,}", f"${t['with_balance_unpaid'] / 1e9:.2f} billion", f"${t['with_balance_obligated'] / 1e9:.2f} billion"):
            self.assertIn(v, lede)
        self.assertIn("is not money lost", lede)
        self.assertNotIn("money at risk of not being used", self.html)   # the review of 2026-11-19: a balance not paid out is not money at risk
        self.assertNotIn("clearest sign", self.html)
        self.assertNotIn("returned and unused", self.html.lower())

    def test_every_program_line_and_agency_is_on_the_page(self):
        rows = re.findall(r'<td class="uf-code" data-t="skip">([0-9.?]+)</td>', self.html)
        self.assertEqual(rows, [r[0] for r in self.d["listings"]])
        self.assertEqual(len(re.findall(r"<tr><th scope=\"row\">", self.html)), len(self.d["agencies"]))

    def test_the_page_names_no_recipient_and_calls_nothing_lost(self):
        text = re.sub(r"<[^>]+>", " ", self.html)
        self.assertNotRegex(text, r"(?i)\bfunds? (was|were) lost\b|\blost (funds|money)\b")
        for name in ("Departamento de", "Department of Education of Puerto Rico", "Municipality of", "Municipio de"):
            self.assertNotIn(name, text)   # federal agencies are named in English in the page source; no Puerto Rico body is named

    def test_the_method_gives_the_read_date_and_the_cutoff_each_by_name(self):
        d = self.d
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        fmt = lambda s: f"{months[int(s[5:7]) - 1]} {int(s[8:10])}, {s[:4]}"
        self.assertIn(f"The data were read on {fmt(d['read'])}, and a grant counts as ended when its end date is before {fmt(d['ended_before'])}", self.html)
        self.assertIn("90 days for grants made before November 12, 2020", self.html)
        for c in d["notes"]:
            self.assertRegex(self.html, rf'<td class="uf-code" data-t="skip">{re.escape(c)}</td><th scope="row" data-t="skip" lang="en">[^<]* †</th>')

    def test_medicaid_is_apart(self):
        self.assertEqual(len(re.findall(r'<tr class="uf-apart">', self.html)), len(self.d["apart"]))
        self.assertEqual(len(re.findall(r'<tr class="uf-blank">', self.html)), len(self.d["no_outlay"]))
        m = self.d["apart"]["medicaid"]
        self.assertIn(f">{m['with_balance_unpaid'] / 1e6:,.1f}<", self.html)
        for sec in ("agencies", "programs", "years"):   # it is in none of the unpaid-balance tables (the audit findings section lists every program)
            self.assertNotIn(">93.778<", re.search(rf'<section class="block" id="{sec}">(.*?)</section>', self.html, re.S).group(1))

    def test_spanish(self):
        es = json.loads((ROOT / "i18n_src" / "es" / "unused_funds.json").read_text(encoding="utf-8"))
        self.assertEqual(es["Federal grants: balances, reductions and audit findings"], "Subvenciones federales: saldos, reducciones y hallazgos de auditoría")
        for k, v in es.items():
            if k != "_about":
                self.assertTrue(v and v != k or k in ("Medicaid",), k[:60])


REBUILT = ROOT / "docs" / "analysis" / "unused-funds-2026-11" / "awards_rebuilt.json"


@unittest.skipUnless(REBUILT.exists() and PAGE.exists(), "the rebuilt grants are not built")
class Rebuilt(unittest.TestCase):
    """Five grants rebuilt from the first commitment to the last payment on record (decision 112, step 4; rebuild_awards.py)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("rebuild_awards", REBUILT.with_name("rebuild_awards.py"))
        cls.R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.R)
        cls.doc = json.loads(REBUILT.read_text(encoding="utf-8"))
        cls.page = PAGE.read_text(encoding="utf-8")

    def test_payments_by_year_are_the_last_month_of_each_year_summed_over_account_lines(self):
        f = lambda y, m, line, v: {"reporting_fiscal_year": y, "reporting_fiscal_month": m, "federal_account": line, "gross_outlay_amount": v}
        rows = [f(2022, 6, "a", 10.0), f(2022, 12, "a", 30.0), f(2022, 12, "b", 5.0), f(2023, 3, "a", 7.0), f(2023, 9, "a", 4.0), f(2021, 9, "a", None)]
        self.assertEqual(self.R.by_year(rows), [[2021, 9, 0.0], [2022, 12, 35.0], [2023, 9, 4.0]])
        self.assertEqual(self.R.fiscal_year("2023-09-30"), 2023)
        self.assertEqual(self.R.fiscal_year("2023-10-01"), 2024)

    def test_five_grants_of_five_programs_outside_the_programs_kept_apart(self):
        g = self.doc["grants"]
        self.assertEqual(len(g), 5)
        self.assertEqual(len({"/".join(x["listings"]) for x in g}), 5)
        for x in g:
            self.assertFalse(set(x["listings"]) & self.R.LEFT_OUT)
            self.assertLess(x["end"], self.doc["ended_before"])
        balances = [x["obligated"] - x["paid"] for x in g]
        self.assertEqual(balances, sorted(balances, reverse=True))

    def test_each_grant_adds_up(self):
        for x in self.doc["grants"]:
            self.assertAlmostEqual(sum(y[2] for y in x["paid_by_year"]), x["paid"], delta=1)
            self.assertAlmostEqual(sum(c[2] for c in x["changes"]), x["obligated"], delta=1)
            self.assertAlmostEqual(sum(y[2] for y in x["paid_by_year"] if y[0] > x["end_fiscal_year"]), x["paid_after_end_year"], delta=1)
            self.assertGreaterEqual(x["highest"], x["obligated"])

    def test_no_recipient_and_no_grant_number(self):
        text = REBUILT.read_text(encoding="utf-8").lower().replace("no recipient", "").replace("the recipient is not read", "")
        for word in ("recipient", "award id", "uei", "duns", "fain", "asst_", "generated"):
            self.assertNotIn(word, text)

    def test_the_file_is_what_the_cache_gives(self):
        if not (self.R.CACHE / "index.json").exists():
            self.skipTest("no cache of the rebuilt grants")
        self.assertEqual(self.R.build(check=True), 0)

    def test_the_page_quotes_the_file_and_draws_no_indicator(self):
        sec = self.page[self.page.index('id="rebuilt"'):self.page.index('id="limits"')]
        self.assertEqual(sec.count('class="card uf-rb"'), 5)
        for x in self.doc["grants"]:
            self.assertIn(f"Committed: ${x['obligated'] / 1e6:,.1f} million. Paid out on record: ${x['paid'] / 1e6:,.1f} million", sec)
            for y in x["paid_by_year"]:
                if y[2]:
                    self.assertIn(f">{y[2] / 1e6:,.1f}<", sec)
        self.assertIn("the page builds no indicator from these balances", sec)
        self.assertIn('href="#rebuilt"', self.page[:self.page.index('id="rebuilt"')])
        low = re.sub(r"<[^>]+>", " ", sec).lower()
        for word in ("returned", "lost", "at risk", "wasted", "failed", "unused"):
            self.assertNotIn(word, low)
        es = json.loads((ROOT / "i18n_src" / "es" / "unused_funds.json").read_text(encoding="utf-8"))
        for k, v in es.items():
            if "rebuilt" in k or "on record:" in k or "The record shows payments" in k:
                self.assertNotEqual(k, v)


if __name__ == "__main__":
    unittest.main()
