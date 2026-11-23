"""Tests for school_conditions.py (public school conditions from the Civil Rights Data Collection; decision 107, step 7, second part).

The pooling runs on invented schools; the published file is checked for its ranges and the dictionary's quoted figures; with the local cache a rebuild must give it.
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import school_conditions as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Pooling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "crdc").mkdir()
        (d / "edu").mkdir()
        (d / "edu" / "schools_ccd_directory_2030_x.json").write_text(json.dumps([
            {"ncessch": "a", "county_code": "72001"}, {"ncessch": "b", "county_code": "72001"}, {"ncessch": "c", "county_code": "72003"}]))
        rows = {"enroll": [{"ncessch": "a", "enrollment_crdc": 100}, {"ncessch": "b", "enrollment_crdc": 300}, {"ncessch": "c", "enrollment_crdc": 50}, {"ncessch": "z", "enrollment_crdc": 9}],
                "absent": [{"ncessch": "a", "students_chronically_absent": 10}, {"ncessch": "b", "students_chronically_absent": 90}, {"ncessch": "c", "students_chronically_absent": -3}],
                "staff": [{"ncessch": "a", "counselors_fte": "1.000", "nurses_fte": "0.000"}, {"ncessch": "b", "counselors_fte": "0.000", "nurses_fte": "1.000"},
                          {"ncessch": "c", "counselors_fte": "-1.000", "nurses_fte": "-1.000"}]}
        for k, r in rows.items():
            (d / "crdc" / f"{k}_2030_total.json").write_text(json.dumps(r))
        self.p = [mock.patch.object(S, "CACHE", d / "crdc"), mock.patch.object(S, "CCD", d / "edu")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_shares_are_pooled_and_missing_codes_are_no_value(self):
        out, notes = S.year_values(2030, ["72001", "72003"], offline=True)
        self.assertEqual(out["crdc_absent_pct"], [25.0, None, 25.0])          # (10 + 90) / (100 + 300), not the mean of 10% and 30%; c is suppressed
        self.assertEqual(out["crdc_students_counselor"], [400.0, None, 400.0])  # 400 students, 1 counselor
        self.assertEqual(out["crdc_no_counselor_pct"], [50.0, None, 50.0])
        self.assertEqual(out["crdc_nurse_pct"], [50.0, None, 50.0])
        self.assertEqual(notes["schools_unplaced"], 1)                           # z is not in the directory


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not S.OUT.exists():
            raise unittest.SkipTest("school_conditions_series.json not built")
        cls.d = json.loads(S.OUT.read_text(encoding="utf-8"))

    def test_ranges_and_the_gaps_of_the_source(self):
        for v in self.d["vars"]:
            for y, vals in v["years"].items():
                for x in vals:
                    if x is not None:
                        self.assertGreaterEqual(x, 0, v["key"])
                        if v["unit"] == "%":
                            self.assertLessEqual(x, 100, v["key"])
            if v["key"] != "crdc_absent_pct":
                self.assertTrue(all(x is None for x in v["years"]["2017"]), f"{v['key']}: Puerto Rico's staff items are missing in 2017-18")
        self.assertLessEqual(self.d["notes"]["2021"]["schools_unplaced"], 5)

    def test_the_dictionary_quotes_the_file(self):
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "school_conditions.json").read_text(encoding="utf-8"))}
        for v in self.d["vars"]:
            self.assertIn(f"{v['years']['2021'][-1]:g}", ents["school_conditions." + v["key"]]["how_to_read"], v["key"])


@unittest.skipUnless((S.CACHE / "staff_2021_total.json").exists() and S.CCD.exists(), "needs cache/crdc and cache/education")
class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(S.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
