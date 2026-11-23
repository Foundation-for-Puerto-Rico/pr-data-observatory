"""Tests for proficiency.py (META-PR results by municipio; decision 107, step 7, third part).

The pooling and the band run on invented schools; the published file is checked against the Department of Education's own 2018-19 figures and the dictionary;
with the local cache a rebuild must give it.
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
import proficiency as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALL = {"race": 99, "sex": 99, "lep": 99, "homeless": 99, "migrant": 99, "disability": 99, "econ_disadvantaged": 99, "foster_care": 99, "military_connected": 99}


class Pooling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "edf").mkdir()
        (d / "edu").mkdir()
        (d / "edu" / "schools_ccd_directory_2030_x.json").write_text(json.dumps([{"ncessch": "720000000001", "county_code": "72001"}, {"ncessch": "720000000002", "county_code": "72001"}]))
        rows = [{**ALL, "ncessch": "720000000001", "read_test_num_valid": 100, "read_test_pct_prof_midpt": 50, "read_test_pct_prof_low": 50, "read_test_pct_prof_high": 50,
                 "math_test_num_valid": 100, "math_test_pct_prof_midpt": 20, "math_test_pct_prof_low": 20, "math_test_pct_prof_high": 20},
                {**ALL, "ncessch": "720000000002", "read_test_num_valid": 300, "read_test_pct_prof_midpt": 25, "read_test_pct_prof_low": 20, "read_test_pct_prof_high": 30,
                 "math_test_num_valid": 300, "math_test_pct_prof_midpt": -3, "math_test_pct_prof_low": -3, "math_test_pct_prof_high": -3},
                {**ALL, "sex": 1, "ncessch": "720000000001", "read_test_num_valid": 50, "read_test_pct_prof_midpt": 99}]   # a subgroup row: not counted
        (d / "edf" / "assess_2030.json").write_text(json.dumps({"count": 3, "next": None, "results": rows}))
        self.p = [mock.patch.object(P, "CACHE", d / "edf"), mock.patch.object(P, "CCD", d / "edu")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        self.tmp.cleanup()

    def test_pooled_by_students_tested_with_the_band_and_suppressed_values_left_out(self):
        out, notes = P.year_values(2030, ["72001"], offline=True)
        self.assertEqual(out["prof_read_pct"], [31.2, 31.2])      # (100 x 50 + 300 x 25) / 400 = 31.25, not the mean of 50 and 25
        self.assertEqual(out["prof_math_pct"], [20.0, 20.0])      # the suppressed school is left out
        self.assertEqual(notes["band"]["read"], {"island_low": 27.5, "island_high": 35.0, "schools_with_a_range": 1})
        self.assertEqual(notes["schools_unplaced"], 0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not P.OUT.exists():
            raise unittest.SkipTest("proficiency_series.json not built")
        cls.d = json.loads(P.OUT.read_text(encoding="utf-8"))
        cls.V = {v["key"]: v for v in cls.d["vars"]}

    def test_the_departments_own_2018_19_figures(self):
        """The Department of Education's META-PR results for 2018-19: 45.1% proficient in Spanish, 30.1% in math."""
        self.assertAlmostEqual(self.V["prof_read_pct"]["years"]["2018"][-1], 45.1, delta=0.5)
        self.assertAlmostEqual(self.V["prof_math_pct"]["years"]["2018"][-1], 30.1, delta=0.5)

    def test_the_midpoint_lies_inside_its_band_and_every_school_is_placed(self):
        for y in map(str, self.d["years"]):
            for s in ("read", "math"):
                b = self.d["notes"][y]["band"][s]
                self.assertLessEqual(b["island_low"], self.V[f"prof_{s}_pct"]["years"][y][-1])
                self.assertLessEqual(self.V[f"prof_{s}_pct"]["years"][y][-1], b["island_high"])
            self.assertEqual(self.d["notes"][y]["schools_unplaced"], 0, y)

    def test_the_dictionary_quotes_the_file(self):
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "proficiency.json").read_text(encoding="utf-8"))}
        for k, v in self.V.items():
            self.assertIn(f"{v['years']['2018'][-1]}%", ents["proficiency." + k]["how_to_read"], k)


@unittest.skipUnless((P.CACHE / "assess_2018.json").exists() and P.CCD.exists(), "needs cache/edfacts and cache/education")
class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(P.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
