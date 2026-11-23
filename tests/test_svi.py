"""CDC/ATSDR Social Vulnerability Index (svi.py, HANDOFF decision 107 step 2): the reading of CDC's files on invented rows, and the published files.

    python -m unittest tests.test_svi

The published files are checked WITHOUT the cache. One test needs the cached CDC files (a rebuild gives the files again) and skips without them.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import svi  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


class Reading(unittest.TestCase):
    def test_cdcs_no_value_code_is_empty_never_zero(self):
        self.assertIsNone(svi.rank({"FIPS": "x", "RPL_THEMES": "-999"}, "RPL_THEMES"))
        self.assertIsNone(svi.rank(None, "RPL_THEMES"), "a tract CDC's file does not hold")
        self.assertEqual(svi.rank({"FIPS": "x", "RPL_THEMES": "0"}, "RPL_THEMES"), 0.0, "a rank of zero is the least vulnerable area, a real value")
        self.assertEqual(svi.rank({"FIPS": "x", "RPL_THEMES": "0.63184"}, "RPL_THEMES"), 0.6318)

    def test_a_value_that_is_not_a_rank_stops_the_build(self):
        with self.assertRaises(SystemExit):
            svi.rank({"FIPS": "x", "RPL_THEMES": "63.2"}, "RPL_THEMES")

    def test_a_file_without_a_column_the_build_reads_stops_it(self):
        with self.assertRaises(SystemExit):
            svi.rows("FIPS,E_TOTPOP,RPL_THEMES\n72001,10,0.5\n".encode("utf-8"))

    def test_the_minority_theme_is_not_among_the_published_variables(self):
        self.assertNotIn(svi.MINORITY, [c for c, _, _ in svi.VARS.values()])
        self.assertEqual(list(svi.VARS), ["svi_overall", "svi_socioeconomic", "svi_household", "svi_housing_transport"])


class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.muni = json.loads((DATA / "svi_series.json").read_text(encoding="utf-8"))
        cls.tract = json.loads((DATA / "svi_tract.json").read_text(encoding="utf-8"))
        cls.y = str(svi.EDITION)

    def test_the_municipios_are_those_of_the_other_series_and_puerto_rico_has_no_rank(self):
        pop = json.loads((DATA / "population_series.json").read_text(encoding="utf-8"))
        self.assertEqual(self.muni["geo"], pop["geo"])
        self.assertEqual([v["key"] for v in self.muni["vars"]], list(svi.VARS))
        for v in self.muni["vars"]:
            vals = v["years"][self.y]
            self.assertEqual(len(vals), 79)
            self.assertIsNone(vals[78], "a rank among municipios has no value for the island")
            self.assertTrue(v["noIsland"])
            self.assertTrue(all(x is not None and 0 <= x <= 1 for x in vals[:78]), v["key"])

    def test_the_overall_rank_orders_the_78_municipios_from_0_to_1(self):
        vals = sorted(self.muni["vars"][0]["years"][self.y][:78])
        self.assertEqual((vals[0], vals[-1]), (0.0, 1.0))
        self.assertGreater(len(set(vals)), 70, "a percentile rank among 78 areas has few ties")

    def test_the_tracts_are_the_crosswalks_in_its_order(self):
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        self.assertEqual(self.tract["geo"]["ids"], [r[0] for r in cw["units"]["tract"]])
        self.assertEqual([v["key"] for v in self.tract["vars"]], list(svi.VARS))
        for v in self.tract["vars"]:
            vals = v["years"][self.y]
            self.assertEqual(len(vals), 981)
            self.assertTrue(all(x is None or 0 <= x <= 1 for x in vals))
        with_rank = sum(x is not None for x in self.tract["vars"][0]["years"][self.y])
        self.assertEqual(with_rank, self.tract["notes"]["with_overall_rank"])
        self.assertGreater(with_rank, 900)

    def test_a_tract_without_residents_has_no_rank(self):
        res = self.tract["notes"]["residents"][self.y]
        overall = self.tract["vars"][0]["years"][self.y]
        for r, x in zip(res, overall):
            if r in (None, 0):
                self.assertIsNone(x)

    def test_the_notes_say_what_a_reader_must_know(self):
        n = self.muni["notes"]
        self.assertIn("Puerto Rico only", n["ranked_within"])
        self.assertIn("not published", n["theme_3"])
        self.assertEqual(set(self.muni["sources"]), {"cdc_svi"})

    @unittest.skipUnless(all((svi.CACHE / name).exists() for name, _ in svi.FILES.values()), "needs the cached CDC files")
    def test_the_cached_files_give_the_published_files_again(self):
        self.assertEqual(svi.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
