"""Tests for degrees.py (degrees awarded by level and field, IPEDS; decision 107, step 7, first part).

The counting rules run on two small invented IPEDS files; the published file is checked against its own identities; with the local cache a rebuild must give it.
"""
import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import degrees as D  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def zipped(path, name, header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(name, "﻿" + buf.getvalue())


class Counting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        zipped(d / "HD2030.zip", "HD2030.csv", ["UNITID", "INSTNM", "STABBR", "COUNTYCD"],
               [["1", "College A", "PR", "72127"], ["2", "College B", "PR", "72021"], ["3", "Mainland", "NY", "36061"]])
        C = ["UNITID", "CIPCODE", "MAJORNUM", "AWLEVEL", "CTOTALT"]
        zipped(d / "C2030_A.zip", "C2030_a.csv", C, [
            ["1", "99", "1", "05", "10"], ["1", "51.3801", "1", "05", "6"], ["1", "52.0201", "1", "05", "4"],
            ["1", "99", "1", "7", "3"], ["1", "13.0101", "1", "7", "3"],
            ["1", "99", "2", "05", "5"], ["1", "51.3801", "2", "05", "5"],      # second majors: not counted
            ["2", "99", "1", "2", "8"], ["2", "12.0401", "1", "2", "8"],        # a certificate: in the total, not in a field
            ["2", "99", "1", "3", "2"], ["2", "51.0801", "1", "3", "2"],
            ["3", "99", "1", "5", "100"], ["3", "11.0101", "1", "5", "100"]])  # not Puerto Rico
        zipped(d / "C2029_A.zip", "C2029_a.csv", C, [["1", "99", "1", "5", "1"], ["1", "51.3801", "1", "5", "1"]])
        zipped(d / "C2029_A_RV.zip", "x.csv", C, [])
        self.cache = mock.patch.object(D, "CACHE", d)
        self.cache.start()

    def tearDown(self):
        self.cache.stop()
        self.tmp.cleanup()

    def test_levels_fields_first_majors_and_places(self):
        out, notes = D.year_counts(2030, ["72021", "72127"], offline=True)
        self.assertEqual(out["deg_total"], [10, 13])
        self.assertEqual(out["deg_bachelor"], [0, 10])
        self.assertEqual(out["deg_graduate"], [0, 3])
        self.assertEqual(out["deg_associate"], [2, 0])
        self.assertEqual((out["deg_field_health"], out["deg_field_business"], out["deg_field_education"]), ([0, 6], [0, 4], [0, 3]))
        self.assertEqual(notes["largest_reporter"]["name"], "College A")
        self.assertEqual(notes["awards_unplaced"], 0)

    def test_rows_that_do_not_add_up_stop_the_build(self):
        d = D.CACHE
        zipped(d / "C2030_A.zip", "C2030_a.csv", ["UNITID", "CIPCODE", "MAJORNUM", "AWLEVEL", "CTOTALT"],
               [["1", "99", "1", "5", "10"], ["1", "51.3801", "1", "5", "9"]])
        with self.assertRaises(SystemExit):
            D.year_counts(2030, ["72127"], offline=True)

    def test_the_revised_file_is_read_when_the_zip_has_one(self):
        p = D.CACHE / "C2028_A.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("C2028_a.csv", "UNITID,CIPCODE\n1,old\n")
            z.writestr("C2028_a_RV.csv", "UNITID,CIPCODE\n1,new\n")
        self.assertEqual([r["CIPCODE"] for r in D.rows(p)], ["new"])


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not D.OUT.exists():
            raise unittest.SkipTest("degrees_series.json not built")
        cls.d = json.loads(D.OUT.read_text(encoding="utf-8"))
        cls.V = {v["key"]: v for v in cls.d["vars"]}

    def test_island_is_the_sum_and_fields_add_up(self):
        fields = [k for k in self.V if k.startswith("deg_field_")]
        for y in map(str, self.d["years"]):
            for v in self.V.values():
                self.assertEqual(v["years"][y][-1], sum(v["years"][y][:-1]), v["key"])
            self.assertEqual(sum(self.V[k]["years"][y][-1] for k in fields), self.V["deg_bachelor"]["years"][y][-1] + self.V["deg_graduate"]["years"][y][-1], y)
            self.assertGreaterEqual(self.V["deg_total"]["years"][y][-1], self.V["deg_bachelor"]["years"][y][-1] + self.V["deg_graduate"]["years"][y][-1] + self.V["deg_associate"]["years"][y][-1])
            self.assertEqual(self.d["notes"][y]["awards_unplaced"], 0)

    def test_areas_are_the_crosswalks(self):
        cw = json.loads((ROOT / "site" / "data" / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        self.assertEqual(self.d["geo"]["ids"], [r[0] for r in cw["units"]["municipio"]] + ["72"])

    def test_the_dictionary_quotes_the_file(self):
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "degrees.json").read_text(encoding="utf-8"))}
        last = str(self.d["years"][-1])
        for k in ("deg_total", "deg_bachelor"):
            self.assertIn(f"{self.V[k]['years'][last][-1]:,}", ents["degrees." + k]["how_to_read"])
        big = self.d["notes"][last]["largest_reporter"]
        self.assertIn(f"{big['awards']:,}", ents["degrees.deg_total"]["caveats"][0])


@unittest.skipUnless((D.CACHE / f"C{D.LAST}_A.zip").exists(), "needs cache/degrees (python degrees.py)")
class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            self.assertEqual(D.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
