"""crashes.py: road deaths by municipio and year from NHTSA's FARS, counts only. The person and crash rules are tested on made-up files; the published
file is checked for its totals, for the absence of any crash's place, date or time, and, where the downloads are cached, against a rebuild."""
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import crashes as cr   # noqa: E402

DATA = ROOT / "site" / "data"


def fake_zip(tmp, year, accident, person):
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as f:
        f.writestr(f"FARS{year}PuertoRicoCSV/accident.csv", accident)
        f.writestr(f"FARS{year}PuertoRicoCSV/person.csv", person)
    (tmp / f"FARS{year}PR.zip").write_bytes(z.getvalue())


class Rules(unittest.TestCase):
    def test_who_was_killed_and_where(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            acc = "ST_CASE,COUNTY,FATALS,LATITUDE,LONGITUD\n1,127,2,18.40,-66.05\n2,72,1,88.8888,888.8888\n3,54,1,77.7777,777.7777\n"
            per = ("ST_CASE,INJ_SEV,PER_TYP,BODY_TYP\n"
                   "1,4,5,0\n1,4,1,80\n1,3,2,80\n"   # a pedestrian and a motorcycle driver killed; an injured passenger
                   "2,4,6,0\n"                        # a bicyclist
                   "3,4,1,4\n")                       # a car driver
            fake_zip(tmp, 2024, acc, per)
            with mock.patch.object(cr, "CACHE", tmp):
                got = {c["case"]: c for c in cr.read_year(2024)}
        self.assertEqual((got["1"]["walk_bike"], got["1"]["moto"], got["1"]["fatals"], got["1"]["lat"]), (1, 1, 2, 18.40))
        self.assertEqual((got["2"]["walk_bike"], got["2"]["county"], got["2"]["lat"]), (1, 72, None), "88.8888: no location")
        self.assertEqual((got["3"]["walk_bike"], got["3"]["moto"], got["3"]["lng"]), (0, 0, None))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "crashes_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v for v in cls.d["vars"]}

    def test_municipios_add_up_to_puerto_rico_each_year(self):
        n = self.d["notes"]
        for y in self.d["years"]:
            for k, f in (("crash_deaths", "deaths"), ("crash_fatal", "crashes"), ("crash_walk_bike", "walk_bike"), ("crash_moto", "moto")):
                vals = self.v[k]["years"][str(y)]
                self.assertEqual(len(vals), 79)
                self.assertEqual(vals[-1], n["island"][str(y)][f], (k, y))
                unplaced = n["municipio_not_given"][str(y)] if k == "crash_deaths" else None
                if unplaced is not None:
                    self.assertEqual(sum(vals[:-1]) + unplaced, vals[-1], (k, y))
                self.assertTrue(all(isinstance(x, int) and x >= 0 for x in vals), (k, y))
            self.assertLessEqual(self.v["crash_walk_bike"]["years"][str(y)][-1] + self.v["crash_moto"]["years"][str(y)][-1], self.v["crash_deaths"]["years"][str(y)][-1])

    def test_the_file_publishes_no_crash(self):
        text = json.dumps(self.d).lower()
        for word in ("latitude", "longitud", "st_case", '"hour"', '"day"', '"month"'):
            self.assertNotIn(word, text)
        self.assertEqual(set(self.d["notes"]["island"]["2024"]), {"crashes", "deaths", "walk_bike", "moto"})

    def test_rates(self):
        last = str(self.d["years"][-1])
        r = self.v["crash_rate_5y"]["years"][last]
        self.assertTrue(all(x is None or 0 <= x < 100 for x in r))
        self.assertGreater(r[-1], 0)
        if "crash_per_vkm" in self.v:
            k = self.v["crash_per_vkm"]["years"][last]
            self.assertTrue(0.3 < k[-1] < 3, "Puerto Rico's deaths per 100 million vehicle-km are in the range of US states")

    def test_the_simulated_connections_count_deaths_near_them(self):
        d = json.loads((DATA / "transit_links.json").read_text(encoding="utf-8"))
        self.assertEqual(d["safety"]["years"], self.d["notes"]["rate_years"])
        pairs = [dict(zip(d["pair_fields"], r)) for r in d["pairs"]]
        sims = [p for p in pairs if p["sim"]]
        self.assertTrue(all(isinstance(p["deaths_5y"], int) and 0 <= p["walk_bike_5y"] <= p["deaths_5y"] for p in sims))
        self.assertTrue(all(p["deaths_5y"] is None for p in pairs if not p["sim"]))

    def test_the_file_is_what_the_cache_gives(self):
        if not cr.cached_years():
            self.skipTest("the FARS files are not cached here (cache/crashes/)")
        self.assertEqual(cr.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
