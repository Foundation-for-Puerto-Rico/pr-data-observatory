"""Tests for education_series.py (Phase 3, item 8): what is kept from the API, how a missing count is read, the aggregation by municipality and the published file. No network."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import education_series as es  # noqa: E402

PII = {"school_name", "inst_name", "street_location", "street_mailing", "address", "phone", "phone_number", "chief_admin_name", "chief_admin_title", "latitude", "longitude", "url_school", "lea_name", "zip", "zip_location", "zip_mailing"}


def school(sid, county, status=1, enroll=100, teachers=10.0):
    return {"ncessch": sid, "year": 2024, "county_code": county, "school_status": status, "school_type": 1, "school_level": 1, "enrollment": enroll, "teachers_fte": teachers, "charter": 0, "virtual": 0}


class Kept(unittest.TestCase):
    def test_no_name_address_phone_or_coordinates_is_kept(self):
        for kind, cols in es.KEEP.items():
            self.assertFalse(PII & set(cols), kind)

    def test_cache_has_only_the_kept_columns(self):
        allowed = set().union(*es.KEEP.values())
        for f in (ROOT / "cache" / "education").glob("*.json"):
            for r in json.loads(f.read_text(encoding="utf-8"))[:50]:
                self.assertLessEqual(set(r), allowed, f.name)

    def test_cache_names_fit_a_windows_path(self):
        p = es.cache_file("college-university/ipeds/fall-enrollment/2010/undergraduate/race/sex/?fips=72&race=99&sex=99&ftpt=99&degree_seeking=99&class_level=99")
        self.assertLess(len(p.name), 60)
        self.assertNotIn("?", p.name)


class Read(unittest.TestCase):
    def test_negative_codes_are_no_value(self):
        for v in (-1, -2, -3, "-1", None, "x"):
            self.assertIsNone(es.num(v))
        self.assertEqual(es.num(0), 0)
        self.assertEqual(es.num("12"), 12)

    def test_schools_count_only_open_statuses(self):
        rows = [school("a", "72001"), school("b", "72001", status=2), school("c", "72001", status=6), school("d", "72003", status=8, enroll=-1, teachers=-1)]
        by, seen, notes = es.schools(rows, {"72001", "72003"})
        self.assertEqual(by["72001"][0], 1)
        self.assertEqual(by["72003"][0], 1)
        self.assertEqual(seen, {"a", "d"})
        self.assertIsNone(by["72003"][1])   # an open school with no count: no value, not zero
        self.assertEqual(by["72001"][1], 100)

    def test_ratio_uses_schools_that_report_both(self):
        rows = [school("a", "72001", enroll=200, teachers=10), school("b", "72001", enroll=300, teachers=-1)]
        by, _, _ = es.schools(rows, {"72001"})
        self.assertEqual(by["72001"][3] / by["72001"][4], 20)

    def test_unknown_county_stops_the_build(self):
        with self.assertRaises(SystemExit):
            es.schools([school("a", "99999")], {"72001"})

    def test_colleges_go_to_the_directory_municipality(self):
        d = [{"unitid": 1, "year": 2024, "county_fips": "72001", "sector": 1}, {"unitid": 2, "year": 2024, "county_fips": "72003", "sector": 9}]
        f = [{"unitid": 1, "year": 2024, "level_of_study": 1, "enrollment_fall": 50}, {"unitid": 1, "year": 2024, "level_of_study": 2, "enrollment_fall": 5}, {"unitid": 2, "year": 2024, "level_of_study": 1, "enrollment_fall": -3}]
        inst, enr, _ = es.colleges(d, f, {"72001", "72003"})
        self.assertEqual(inst, {"72001": 1, "72003": 1})
        self.assertEqual(enr["72001"], 55)
        self.assertIsNone(enr["72003"])

    def test_system_offices_and_not_applicable_records_are_not_institutions(self):   # review of PR #17: sector 0 (a university system's office) and -1 ("not applicable") made a false rise in 2020
        d = [{"unitid": 1, "county_fips": "72127", "sector": 0}, {"unitid": 2, "county_fips": "72127", "sector": -1}, {"unitid": 3, "county_fips": "72127", "sector": 2}]
        inst, _, notes = es.colleges(d, [], {"72127"})
        self.assertEqual(inst, {"72127": 1})
        self.assertEqual(notes["not an institution (sector 0)"] + notes["not an institution (sector -1)"], 2)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = ROOT / "site" / "data" / "education_series.json"
        if not p.exists():
            raise unittest.SkipTest("education_series.json is not built")
        cls.d = json.loads(p.read_text(encoding="utf-8"))
        cls.V = {v["key"]: v for v in cls.d["vars"]}

    def test_shape(self):
        self.assertEqual(len(self.d["geo"]["ids"]), 79)
        self.assertEqual(self.d["geo"]["ids"][-1], "72")
        for v in self.d["vars"]:
            for y, a in v["years"].items():
                self.assertEqual(len(a), 79, (v["key"], y))

    def test_island_is_the_sum_of_municipios(self):
        for k in ("sch_open", "sch_enroll", "sch_closed", "he_inst", "he_enroll"):
            for y, a in self.V[k]["years"].items():
                if a[-1] is None:
                    continue
                self.assertAlmostEqual(a[-1], sum(x for x in a[:-1] if x is not None), delta=0.5, msg=(k, y))

    def test_known_totals(self):   # published NCES counts that the plan quoted (docs/proposal-2026-10.md, D2)
        self.assertEqual(self.V["sch_enroll"]["years"]["2017"][-1], 346096)
        self.assertEqual(self.V["sch_enroll"]["years"]["2024"][-1], 235819)

    def test_no_closure_value_for_the_first_year(self):
        first = str(self.d["years"][0])
        self.assertTrue(all(x is None for x in self.V["sch_closed"]["years"][first]))

    def test_every_variable_has_a_dictionary_entry(self):
        ids = {e["id"] for e in json.loads((ROOT / "dictionary_src" / "entries" / "education.json").read_text(encoding="utf-8"))}
        self.assertEqual(ids, {f"education.{k}" for k in self.V})

    def test_every_label_has_spanish(self):
        es_ = json.loads((ROOT / "i18n_src" / "es" / "labels_education.json").read_text(encoding="utf-8"))
        for v in self.d["vars"]:
            self.assertIn(v["label"], es_)
            self.assertIn("Education · " + v["group"], es_)


if __name__ == "__main__":
    unittest.main()
