"""Federal grant money taken back (taken_back.json, taken_back.py, HANDOFF decision 110, step 2): the net-reduction rule, money moved between
grants, the programs kept apart, sums that agree with each other, no recipient in the file, and a page whose figures are the file's.
The rebuild from the cache is compared with the published file when the cache is present."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import taken_back as B  # noqa: E402

OUT = ROOT / "site" / "data" / "taken_back.json"
PAGE = ROOT / "site" / "unused-funds.html"


def tx(award, day, amount, listing="10.001", agency="A"):
    return [award, day, amount, listing, "Program " + listing, agency]


class Rules(unittest.TestCase):
    def test_what_is_read(self):
        self.assertEqual(B.FIRST_YEAR, 2019)
        self.assertNotIn("Recipient Name", B.FIELDS)
        self.assertEqual(len(B.quarters(2024)), 4)
        self.assertEqual(B.quarters(2024)[0], ("2023-10-01", "2023-12-31"))
        self.assertEqual(B.quarters(2024)[3], ("2024-07-01", "2024-09-30"))

    def test_fiscal_year(self):
        self.assertEqual(B.fiscal_year("2023-09-30"), 2023)
        self.assertEqual(B.fiscal_year("2023-10-01"), 2024)

    def test_net_reduction(self):
        self.assertEqual(B.net_reduction([100, -30]), 30)            # lowered for good
        self.assertEqual(B.net_reduction([100, -30, 30]), 0)         # lowered and raised back
        self.assertEqual(B.net_reduction([100, -30, 50]), 0)         # ends above its earlier peak
        self.assertEqual(B.net_reduction([-40]), 40)                 # an award that began before the period
        self.assertEqual(B.net_reduction([-40, 100]), 0)
        self.assertEqual(B.net_reduction([100, -60, 20, -10]), 50)   # peak 100, ends at 50
        self.assertEqual(B.net_reduction([100, 50]), 0)

    def test_same_day_transactions_count_as_one_change(self):
        # a swap between two lines of one award on one day is not a reduction, whatever order the source lists them in
        for order in ([tx("a", "2021-01-05", -5000), tx("a", "2021-01-05", 5000)], [tx("a", "2021-01-05", 5000), tx("a", "2021-01-05", -5000)]):
            self.assertEqual(B.awards(order)[1], [])
        n, recs = B.awards([tx("a", "2021-01-05", 9000), tx("a", "2022-03-01", -5000), tx("a", "2022-03-01", 1000)])
        self.assertEqual((n, recs[0][3], recs[0][4]), (1, 4000, 2022))

    def test_small_reductions_are_left_out(self):
        self.assertEqual(B.awards([tx("a", "2021-01-05", 9000), tx("a", "2022-03-01", -999)])[1], [])

    def test_an_award_takes_the_listing_with_most_money_and_is_marked_combined(self):
        _, recs = B.awards([tx("a", "2020-01-05", 100000, "17.259"), tx("a", "2020-02-05", 300000, "17.278"), tx("a", "2023-09-13", -50000, "17.259")])
        self.assertEqual((recs[0][0], recs[0][3], recs[0][5]), ("17.278", 50000, True))

    def test_money_moved_to_another_grant_of_the_same_program_is_not_a_reduction(self):
        rows = [tx("a", "2020-01-05", 100000), tx("a", "2021-06-01", -40000), tx("b", "2021-06-20", 40000)]
        kept, n, usd = B.drop_moves(rows)
        self.assertEqual((n, usd), (1, 40000))
        self.assertEqual(B.awards(kept)[1], [])
        self.assertEqual(len(kept), 2)   # the increase stays with the grant that received the money
        # another program, another agency, another amount, the same grant or more than MOVE_DAYS apart: a reduction
        for other in (tx("b", "2021-06-20", 40000, "10.002"), tx("b", "2021-06-20", 40000, agency="B"), tx("b", "2021-06-20", 39000), tx("a", "2021-06-20", 40000), tx("b", "2021-08-20", 40000)):
            self.assertEqual(B.drop_moves([rows[0], rows[1], other])[1], 0)

    def test_one_increase_covers_one_reduction(self):
        rows = [tx("a", "2021-06-01", -40000), tx("c", "2021-06-02", -40000), tx("b", "2021-06-20", 40000)]
        self.assertEqual(B.drop_moves(rows)[1], 1)

    def test_the_programs_apart_have_a_reason_and_are_listed_once(self):
        codes = [c for v in B.APART.values() for c in v["listings"]]
        self.assertEqual(len(codes), len(set(codes)))
        for v in B.APART.values():
            self.assertGreater(len(v["why"]), 40)
        self.assertNotIn("17.278", codes)   # the workforce programs are in the main figures, like any other
        self.assertEqual(B.APART["federal"]["listings"], ["81.254", "66.959", "66.616"])   # money withdrawn by a federal decision in 2025


@unittest.skipUnless(OUT.exists(), "taken_back.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_shape(self):
        d = self.d
        self.assertEqual(d["years"][0], 2019)
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        self.assertEqual([r[0] for r in d["by_year"]], d["years"])
        self.assertEqual(set(d["apart"]), set(B.APART))
        for r in d["listings"]:
            self.assertEqual(len(r), 6)
            self.assertTrue(r[1], f"{r[0]} has no name")
            self.assertGreaterEqual(r[4], B.MIN_USD)

    def test_no_recipient_and_no_award_is_in_the_file(self):
        text = OUT.read_text(encoding="utf-8").lower()
        for word in ("recipient", "award id", "asst_non", "uei", "duns"):
            self.assertNotIn(word, text)

    def test_the_three_breakdowns_add_up_to_the_totals(self):
        d, t = self.d, self.d["totals"]
        for name, n, usd in (("agencies", 1, 2), ("listings", 3, 4), ("by_year", 1, 2)):
            self.assertEqual(sum(r[n] for r in d[name]), t["awards"], name)
            self.assertLessEqual(abs(sum(r[usd] for r in d[name]) - t["net"]), len(d[name]), name)
        self.assertEqual(len({r[0] for r in d["listings"]}), t["listings"])
        self.assertEqual(len(d["agencies"]), t["agencies"])
        self.assertEqual(sum(r[5] for r in d["listings"]), t["combined_awards"])

    def test_the_programs_apart_are_in_no_breakdown(self):
        apart = {c for v in B.APART.values() for c in v["listings"]}
        self.assertFalse({r[0] for r in self.d["listings"]} & apart)
        for g, v in self.d["apart"].items():
            self.assertTrue({l[0] for l in v["listings"]} <= set(B.APART[g]["listings"]), g)
            self.assertEqual(sum(l[2] for l in v["listings"]), v["awards"], g)

    def test_net_is_far_below_gross(self):
        d = self.d
        everything = d["totals"]["net"] + sum(v["net"] for v in d["apart"].values())
        self.assertLess(everything, d["read_counts"]["gross_negative"])
        self.assertGreater(d["read_counts"]["transactions"], d["read_counts"]["negative"])

    def test_every_program_is_read(self):
        self.assertGreater(self.d["totals"]["listings"], 200)
        self.assertGreater(self.d["totals"]["agencies"], 15)

    def test_the_file_is_what_the_cache_gives(self):
        if not (B.CACHE / "index.json").exists():
            self.skipTest("no cache of the transactions")
        self.assertEqual(B.build(check=True), 0)


@unittest.skipUnless(OUT.exists() and PAGE.exists(), "the page is not built")
class Page(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))
        self.html = PAGE.read_text(encoding="utf-8")
        self.section = re.search(r'<section class="block" id="taken">(.*?)</section>', self.html, re.S).group(1)

    def test_the_section_quotes_the_file(self):
        t = self.d["totals"]
        for v in (f"{t['awards']:,} grants", f"${t['net'] / 1e9:.2f} billion", f"{t['listings']} programs of {t['agencies']} federal agencies"):
            self.assertIn(v, self.section)

    def test_every_program_line_and_agency_is_in_the_section(self):
        self.assertEqual(re.findall(r'<td class="tb-code" data-t="skip">([0-9.?]+)</td>', self.section), [r[0] for r in self.d["listings"]])
        self.assertEqual(len(re.findall(r'<tr class="tb-ag">', self.section)), len(self.d["agencies"]))
        self.assertEqual(len(re.findall(r'<tr class="tb-apart">', self.section)), len(self.d["apart"]))

    def test_the_section_says_what_it_cannot_say(self):
        intro = re.search(r'<p class="pm-p">(.*?)</p>', self.section, re.S).group(1)
        self.assertLess(intro.index("The data do not say why an amount was lowered"), intro.index("a net reduction of"), "the limit comes before the figure")
        self.assertIn("Never add the two measures.", self.section)
        self.assertIn("Net, not gross.", self.section)
        text = re.sub(r"<[^>]+>", " ", self.html)
        self.assertNotRegex(text, r"(?i)\bfunds? (was|were) lost\b|\blost (funds|money)\b")

    def test_the_programs_apart_are_not_in_the_program_table(self):
        for v in B.APART.values():
            for c in v["listings"]:
                self.assertNotIn(f'data-t="skip">{c}</td>', self.section)


if __name__ == "__main__":
    unittest.main()
