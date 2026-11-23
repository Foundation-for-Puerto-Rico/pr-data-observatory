"""The function crosswalk (dictionary_src/spending_crosswalk.csv, HANDOFF decision 76, reviewed on 2026-11-09 in decision 92): every code the sources use is
covered, its values are in the schema, and the lookups follow the allocation rules (debt service and pensions island-wide, capital spending never
apportioned, a program with another function does not take its agency's driver). The code lists are the evidence in docs/analysis/public-spending-2026-11/
(OGP data sheets FY26-FY27, USAspending FY2023-2025 in Puerto Rico)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import spending as S  # noqa: E402

EV = ROOT / "docs" / "analysis" / "public-spending-2026-11"


class Crosswalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cw = S.load_crosswalk()
        cls.ogp = json.loads((EV / "ogp_codes.json").read_text(encoding="utf-8"))
        cls.cfda = json.loads((EV / "cfda_listings.json").read_text(encoding="utf-8"))["listings"]

    def test_values_are_in_the_schema(self):
        self.assertEqual(S.check_crosswalk(self.cw), [])

    def test_columns(self):
        import csv
        with open(S.CROSSWALK, encoding="utf-8", newline="") as f:
            self.assertEqual(csv.DictReader(f).fieldnames, S.CROSSWALK_FIELDS)

    def test_every_ogp_agency_and_concept_is_covered(self):
        for c in self.ogp["agencies"]:
            self.assertIn(("ogp_agency", c), self.cw, f"agency {c} {self.ogp['agencies'][c]}")
        for c in self.ogp["concepts"]:
            self.assertIn(("ogp_concept", c), self.cw, f"concept {c}")

    def test_every_ogp_budget_line_resolves(self):
        for key in self.ogp["programs"]:
            a, p = key.split("-")
            for c in self.ogp["concepts"]:
                fn, concept, alloc, conf = S.ogp_function(a, p, c, cw=self.cw)
                self.assertIn(fn, S.FUNCTIONS, key)
                self.assertIn(concept, S.CONCEPTS, key)

    def test_program_and_object_rows_name_real_codes(self):
        for kind, code in self.cw:
            if kind == "ogp_program":
                self.assertIn(code, self.ogp["programs"], code)
            if kind in ("ogp_program", "ogp_object"):
                self.assertIn(("ogp_agency", code.split("-")[0]), self.cw, code)

    def test_debt_service_and_pensions_are_island_wide_whatever_the_agency(self):
        for a in self.ogp["agencies"]:
            for c in ("009", "030"):
                fn, _, alloc, _ = S.ogp_function(a, concept=c, cw=self.cw)
                self.assertEqual((fn, alloc), ("debt_pensions", "island_wide"), f"{a} concept {c}")

    def test_capital_spending_is_never_apportioned(self):
        for (kind, code), r in self.cw.items():
            if kind == "ogp_agency" and r["allocation"].startswith("apportion:"):
                for c in self.ogp["concepts"]:
                    if self.cw[("ogp_concept", c)]["concept_of_expense"] == "capex":
                        self.assertEqual(S.ogp_function(code, concept=c, cw=self.cw)[2], "", f"{code} concept {c}")

    def test_only_education_is_apportioned_for_now(self):
        # decision 73 (5): Education by enrollment; Health, Transportation and Environment wait for their drivers
        self.assertEqual({c for (k, c), r in self.cw.items() if r["allocation"].startswith("apportion:")}, {"081"})

    def test_a_program_with_another_function_does_not_take_the_agency_driver(self):
        self.assertEqual(S.ogp_function("050", "1159", "001", cw=self.cw)[:3], ("parks_recreation", "payroll", "no_driver"))
        self.assertEqual(S.ogp_function("081", "1010", "001", cw=self.cw)[2], "apportion:school_enrollment")

    def test_an_unknown_agency_or_concept_stops_the_lookup(self):
        with self.assertRaises(KeyError):
            S.ogp_function("999", concept="001", cw=self.cw)
        with self.assertRaises(KeyError):
            S.ogp_function("081", concept="777", cw=self.cw)

    def test_every_federal_listing_in_puerto_rico_resolves(self):
        for k in self.cfda:
            fn, conf = S.cfda_function(k, cw=self.cw)
            self.assertIn(fn, S.FUNCTIONS, k)

    def test_named_listings_cover_most_of_the_money(self):
        tot = sum(v for _, v in self.cfda.values())
        named = sum(v for k, (_, v) in self.cfda.items() if ("cfda", k) in self.cw)
        self.assertGreaterEqual(named / tot, 0.95)

    def test_fema_and_contralor_lists_are_complete(self):
        self.assertEqual({c for k, c in self.cw if k == "fema_category"}, set("ABCDEFGZ"))
        self.assertEqual({int(c) for k, c in self.cw if k == "contralor_group"}, set(range(1, 24)))

    def test_flagged_rows_say_why(self):
        for (kind, code), r in self.cw.items():
            if r["flag"]:
                self.assertTrue(r["reason"].strip(), f"{kind} {code}")

    def test_the_tags_on_the_published_series_agree(self):
        for cat in "ABCDEFGZ":
            self.assertEqual(S.SERIES_TAGS[f"fema_pa_cat_{cat.lower()}"]["function_category"], self.cw[("fema_category", cat)]["function_category"], cat)
        for key, listing in (("fed_prog_ss_retirement", "96.002"), ("fed_prog_ss_disability", "96.001"), ("fed_prog_ss_survivors", "96.004"),
                             ("fed_prog_va_compensation", "64.109"), ("fed_prog_pell", "84.063"), ("fed_prog_head_start", "93.600"), ("fed_prog_pbra", "14.195")):
            self.assertEqual(S.SERIES_TAGS[key]["function_category"], S.cfda_function(listing, cw=self.cw)[0], key)

    def test_custodial_rows_hold_only_in_the_years_a_budget_resolution_confirms(self):
        cw = self.cw
        f = lambda obj, fund, year, concept="014": S.ogp_function("025", "1640", concept, obj, cw=cw, fund=fund, year=year)[0]
        self.assertEqual(f("E6390", "general", 2027), "debt_pensions", "FY27: the Pension Reserve Trust")
        self.assertEqual(f("E6390", "general", 2025), "debt_pensions", "FY25: the Pension Reserve Trust")
        self.assertEqual(f("E6390", "general", 2024), "other", "FY24 uses other codes")
        self.assertEqual(f("E6390", "special", 2027), "economic_development")
        self.assertEqual(f("E6390", "special", 2025), "other", "FY25 special funds are not matched")
        self.assertEqual(f("E9760", "general", 2026, "013"), "transportation")
        self.assertEqual(f("E9760", "general", 2025, "013"), "other", "FY25 mixes highway transfers and rum cover-over")
        self.assertEqual(f("E9760", "general", None, "013"), "other", "a row limited to some years needs the year")

    def test_years_are_checked(self):
        bad = {("ogp_object", "025-E1111"): dict(self.cw[("ogp_agency", "025")], kind="ogp_object", code="025-E1111", years="2025"),
               ("ogp_agency", "999"): dict(self.cw[("ogp_agency", "025")], code="999", years="2025-2027"),
               ("ogp_object", "025-611088"): dict(self.cw[("ogp_agency", "025")], kind="ogp_object", code="025-611088", years="")}
        self.assertEqual(len(S.check_crosswalk(bad)), 3)

    def test_the_review_list_matches_the_csv(self):
        text = (EV / "crosswalk_review.md").read_text(encoding="utf-8")
        flagged = [r for r in self.cw.values() if r["flag"] == "review"]
        self.assertEqual(text.count("\n| ") - 1, len(flagged), "run docs/analysis/public-spending-2026-11/make_crosswalk.py")


if __name__ == "__main__":
    unittest.main()
