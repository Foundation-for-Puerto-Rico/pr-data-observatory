"""Federal money in Puerto Rico by function (spending_federal.json, federal_awards.py, HANDOFF decision 83): each program takes its crosswalk function
or its agency's, a contract its awarding agency's, a prefix with no crosswalk row is counted as "other" and named, only final fiscal years are read,
and the published file adds up: for each year and award type the rows equal USAspending's total. The rebuild from the cache is compared with the
published file when the cache is present."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import federal_awards as F  # noqa: E402
import spending  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_federal.json"


class Classify(unittest.TestCase):
    def setUp(self):
        self.cw = spending.load_crosswalk()
        F.UNMAPPED.clear()

    def test_a_listing_with_its_own_row(self):
        fn, conf = spending.cfda_function("96.002", self.cw)
        self.assertEqual(F.classify("direct_payments", "96.002", self.cw), (fn, conf, "96"))

    def test_a_listing_without_a_row_takes_its_agency_default_with_low_confidence(self):
        self.assertEqual(F.classify("grants", "84.999", self.cw), (self.cw[("cfda_agency", "84")]["function_category"], "low", "84"))

    def test_a_contract_takes_its_awarding_agency_default(self):
        self.assertEqual(F.classify("contracts", "DOD", self.cw), (self.cw[("cfda_agency", "12")]["function_category"], "low", "12"))
        self.assertEqual(F.classify("contracts", "XYZ", self.cw), ("other", "low", ""))

    def test_a_prefix_with_no_crosswalk_row_is_other_and_named(self):
        self.assertEqual(F.classify("grants", "00.001", self.cw), ("other", "low", "00"))
        self.assertEqual(F.UNMAPPED, {"00"})

    def test_every_contract_agency_has_a_crosswalk_default(self):
        self.assertEqual([a for a, p in F.CONTRACT_AGENCY.items() if ("cfda_agency", p) not in self.cw], [])


class FinalYears(unittest.TestCase):
    def test_a_fiscal_year_is_final_from_november_15(self):
        self.assertEqual(F.last_year(date(2026, 11, 14)), 2025)
        self.assertEqual(F.last_year(date(2026, 11, 15)), 2026)
        self.assertEqual(F.last_year(date(2027, 3, 1)), 2026)


@unittest.skipUnless(OUT.exists(), "spending_federal.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_rows_add_up_to_usaspending_totals(self):
        d = self.d
        for gi, g in enumerate(d["groups"]):
            for yi, y in enumerate(d["years"]):
                s = sum(r[5][yi] for r in d["rows"] if r[2] == gi)
                self.assertLessEqual(abs(s - d["totals"][g][yi]), len(d["rows"]), f"{g} FY{y}")

    def test_indexes_and_shapes(self):
        d = self.d
        self.assertEqual(d["functions"], spending.FUNCTIONS)
        self.assertEqual(d["fiscal_year_basis"], "federal_oct_sep")
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        for r in d["rows"]:
            self.assertTrue(0 <= r[2] < len(d["groups"]) and 0 <= r[3] < len(d["functions"]) and 0 <= r[4] < len(d["confidence"]), r[:5])
            self.assertEqual(len(r[5]), len(d["years"]), r[0])

    def test_no_prefix_is_left_out_of_the_crosswalk(self):
        self.assertEqual(self.d["unmapped"], [])

    def test_fema_programs_carry_their_dedup_groups(self):
        self.assertEqual(self.d["dedup"], {"97.036": "fema_pa", "97.039": "fema_hma"})
        self.assertTrue(set(self.d["dedup"].values()) <= set(spending.DEDUP_GROUPS))

    @unittest.skipUnless((F.CACHE / f"{F.FIRST_YEAR}_grants.json").exists(), "no USAspending cache")
    def test_the_cache_rebuilds_the_published_file(self):
        years = self.d["years"]
        self.assertTrue(F.build(check=True, today=date(years[-1] + 1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
