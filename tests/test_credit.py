"""Credit (credit.py, HANDOFF decision 107 step 4): the reading of HMDA rows and FDIC offices on invented rows, and the published file.

    python -m unittest tests.test_credit

The published file is checked WITHOUT the cache. Two tests need the cached files (the 2023 totals and a rebuild) and skip without them.
"""
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import credit  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
FIELDS = ["action_taken", "county_code", "loan_amount", "loan_purpose"]


def hmda_file(rows):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    w = csv.writer(f)
    w.writerow(FIELDS)
    w.writerows(rows)
    f.close()
    return Path(f.name)


class Reading(unittest.TestCase):
    def test_hmda_counts_made_purchase_denied_and_leaves_out_purchased_loans(self):
        p = hmda_file([["1", "72001", "105000", "1"], ["1", "72001", "55000", "31"], ["3", "72001", "75000", "1"], ["2", "72001", "65000", "1"],
                       ["4", "72001", "95000", "1"], ["6", "72001", "205000", "1"], ["1", "NA", "15000", "1"]])
        try:
            f, no_muni = credit.hmda_figures(p, {"72001", "72003"})
        finally:
            p.unlink()
        a = f["72001"]
        self.assertEqual(a["loans"], 2, "two loans made; the purchased loan (action 6) is not new lending")
        self.assertEqual(a["purchase"], 1)
        self.assertEqual(a["amount"], 160000)
        self.assertEqual((a["denied"], a["decided"]), (1, 4), "decided: made, approved but not taken, denied; a withdrawn application is not a decision")
        self.assertEqual(f["72"]["loans"], 3, "a row with no municipio counts in Puerto Rico's figure")
        self.assertEqual(no_muni, 1)
        self.assertNotIn("72003", f)

    def test_fdic_offices_add_up_by_municipio_and_deposits_are_in_dollars(self):
        rows = [{"YEAR": 2025, "STCNTYBR": 72001, "DEPSUMBR": 1500}, {"YEAR": 2025, "STCNTYBR": 72001, "DEPSUMBR": None}, {"YEAR": 2024, "STCNTYBR": "72003", "DEPSUMBR": 7}]
        by = credit.sod_figures(rows, {"72001", "72003"})
        self.assertEqual(by[2025]["72001"], [2, 1500000])
        self.assertEqual(by[2024]["72003"], [1, 7000])

    def test_an_office_outside_the_78_municipios_stops_the_build(self):
        with self.assertRaises(SystemExit):
            credit.sod_figures([{"YEAR": 2025, "STCNTYBR": 78010, "DEPSUMBR": 1}], {"72001"})


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "credit_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v for v in cls.doc["vars"]}

    def test_the_areas_are_the_78_municipios_then_puerto_rico(self):
        ids = self.doc["geo"]["ids"]
        self.assertEqual(len(ids), 79)
        self.assertEqual(ids[-1], "72")
        for v in self.doc["vars"]:
            for y, a in v["years"].items():
                self.assertEqual(len(a), 79, (v["key"], y))

    def test_offices_and_deposits_add_up_to_puerto_rico(self):
        for key in ("bank_branches", "bank_deposits"):
            for y, a in self.v[key]["years"].items():
                self.assertEqual(sum(a[:-1]), a[-1], (key, y))

    def test_loans_add_up_to_no_more_than_puerto_rico(self):
        for key in ("hmda_loans", "hmda_purchase_loans"):
            for y, a in self.v[key]["years"].items():
                self.assertLessEqual(sum(a[:-1]), a[-1], (key, y))
                self.assertGreater(sum(a[:-1]), 0.98 * a[-1], (key, y))

    def test_amount_and_denial_share_are_empty_under_the_floor(self):
        for y in self.v["hmda_loans"]["years"]:
            n = self.v["hmda_loans"]["years"][y]
            amt = self.v["hmda_loan_amount"]["years"][y]
            for i in range(78):
                if n[i] < credit.MIN_LOANS:
                    self.assertIsNone(amt[i], (y, i))
                if amt[i] is None:
                    self.assertLess(n[i], credit.MIN_LOANS, (y, i))
            for x in self.v["hmda_denial_pct"]["years"][y]:
                self.assertTrue(x is None or 0 <= x <= 100)

    def test_no_licence_line_claims_more_than_a_us_government_work(self):
        for s in self.doc["sources"].values():
            self.assertNotIn("public domain", s["license"].lower())

    def test_2023_equals_the_data_browsers_own_totals(self):
        h = self.doc["notes"]["hmda_island"]["2023"]
        self.assertEqual(h["loans_made"], 13550)
        self.assertEqual(round(h["amount"] / 1e7), 224, "$2.24 billion")


class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        if not (credit.CACHE / "sod.json").exists() or not (credit.CACHE / f"hmda{credit.HMDA_FIRST}.csv").exists():
            self.skipTest("no cache (python credit.py --refresh)")
        doc = credit.documents(credit.fetch_sod(False), credit.hmda_years(False, True))
        old = json.loads((DATA / "credit_series.json").read_text(encoding="utf-8"))
        self.assertEqual({**doc, "built": None}, {**old, "built": None})


if __name__ == "__main__":
    unittest.main()
