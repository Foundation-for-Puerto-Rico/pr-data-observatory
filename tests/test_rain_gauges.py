"""Rainfall (rain_gauges.py): the gauge's name, the unit, the usual rain of a week, and what the published file holds.

    python -m unittest tests.test_rain_gauges
"""
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rain_gauges as rn  # noqa: E402

FILE = ROOT / "site" / "data" / "rain_gauges.geojson"


class Names(unittest.TestCase):
    def test_the_name_is_usgs_name_written_as_words_with_its_accents(self):
        for usgs, name in (("RIO DE LA PLATA AT COMERIO, PR", "Río de la Plata at Comerío"),
                           ("BO. ANONES RAINGAGE NEAR NARANJITO, PR", "Bo. Anones rain gauge near Naranjito"),
                           ("LA PLAZA RAINGAGE, CAGUAS PR", "La Plaza rain gauge, Caguas"),
                           ("RAINGAGE NEAR ALTAMIRA, GUAYNABO, PR", "Rain gauge near Altamira, Guaynabo"),
                           ("PRECIPITATION STATION AT FT ALLEN FD,JUANA DIAZ,PR", "Precipitation Station at Ft. Allen FD, Juana Díaz"),
                           ("BO. MONTONES RAINGAGE, LAS PIEDRAS PR", "Bo. Montones rain gauge, Las Piedras"),
                           ("LAGO COAMO NR LOS LLANOS, PR", "Lago Coamo near Los Llanos"),
                           ("BO GUAJATACA RAINGAGE ABV LAGO GUAJATACA AT PR 455", "Bo. Guajataca rain gauge above Lago Guajataca at PR 455"),
                           ("JUA 5 WELL, GUAYAMA, PR", "JUA 5 Well, Guayama")):
            self.assertEqual(rn.gauge_name(usgs), name)


class Rain(unittest.TestCase):
    def test_inches_become_millimetres(self):
        self.assertEqual(rn.mm("1"), 25.4)
        self.assertEqual(rn.mm(0.01), 0.3)

    def test_the_usual_rain_of_a_week_is_the_percentile_of_each_years_week(self):
        daily = {}
        for i, y in enumerate(range(2011, 2021)):   # ten years: every day of week 1 has 0.1, 0.2, ... 1.0 inches
            for d in range(7):
                daily[(date(y, 1, 1) + timedelta(days=d)).isoformat()] = str(round(0.1 * (i + 1), 1))
        norm, years = rn.normals(daily)
        self.assertEqual(years, 10)
        self.assertEqual(norm[50][0], round(0.55 * 7 * rn.MM, 1))   # a week of the median year: 7 days of 0.55 inches
        self.assertEqual(norm[10][0], round(0.19 * 7 * rn.MM, 1))
        self.assertEqual(norm[90][0], round(0.91 * 7 * rn.MM, 1))
        self.assertIsNone(norm[50][1], "a week with no value has no usual rain")

    def test_a_week_needs_six_of_its_days_and_eight_years(self):
        five = {(date(y, 1, 1) + timedelta(days=d)).isoformat(): "1" for y in range(2011, 2021) for d in range(5)}
        self.assertIsNone(rn.normals(five)[0][50][0], "five days of a week are not a week")
        six = {(date(y, 1, 1) + timedelta(days=d)).isoformat(): "1" for y in range(2011, 2021) for d in range(6)}
        self.assertEqual(rn.normals(six)[0][50][0], round(7 * rn.MM, 1), "six days stand for the week: their mean times seven")
        seven_years = {(date(y, 1, 1) + timedelta(days=d)).isoformat(): "1" for y in range(2011, 2018) for d in range(7)}
        self.assertIsNone(rn.normals(seven_years)[0][50][0])

    def test_the_last_week_of_a_year_has_one_or_two_days(self):
        self.assertEqual(rn.days_in_week(52, 2023), 1)
        self.assertEqual(rn.days_in_week(52, 2024), 2)
        self.assertEqual(rn.days_in_week(10, 2024), 7)
        last = {date(y, 12, 31).isoformat(): "1" for y in range(2011, 2023) if y % 4}   # the 365th day of a common year is the whole of week 52
        self.assertEqual(rn.normals(last)[0][50][52], round(7 * rn.MM, 1))

    def test_years_outside_the_window_and_empty_values_are_left_out(self):
        daily = {"2010-01-03": "9", "2026-01-03": "9", "2015-01-03": "", "2016-01-03": None}
        self.assertEqual(rn.normals(daily)[1], 0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))
        cls.props = [f["properties"] for f in cls.d["features"]]

    def test_every_gauge_has_a_municipio_and_a_station(self):
        self.assertGreaterEqual(len(self.props), 25)
        self.assertEqual(self.d["notes"]["gauges"], len(self.props))
        self.assertEqual(self.d["notes"]["municipios"], len({p["geoid"] for p in self.props}))
        for p in self.props:
            self.assertRegex(p["geoid"], r"^72\d{3}$")
            self.assertRegex(p["usgs"], r"^USGS-\d+$")
            self.assertTrue(p["name"] and p["station"] and p["municipio"])
            self.assertFalse(p["name"].endswith(","), p["name"])
            self.assertEqual(p["type"], "Rain gauge")
        self.assertEqual(len({p["usgs"] for p in self.props}), len(self.props), "one point a gauge")

    def test_the_history_has_120_days_and_53_weeks_and_no_negative_rain(self):
        for p in self.props:
            self.assertEqual(len(p["recent"]), rn.RECENT)
            self.assertTrue(all(v is None or 0 <= v < 1000 for v in p["recent"]), p["usgs"])   # mm in a day
            for q in ("p10", "p25", "p50", "p75", "p90"):
                self.assertEqual(len(p[q]), 53)
            for w in range(53):
                qs = [p[q][w] for q in ("p10", "p25", "p50", "p75", "p90")]
                if qs[0] is not None:
                    self.assertEqual(qs, sorted(qs), f"{p['usgs']} week {w}: the percentiles rise")
                    self.assertGreaterEqual(qs[0], 0)

    def test_no_field_beyond_the_documented_ones(self):
        allowed = {"name", "type", "municipio", "geoid", "usgs", "station", "recent_start", "recent", "p10", "p25", "p50", "p75", "p90"}
        for p in self.props:
            self.assertFalse(set(p) - allowed)

    def test_the_points_are_in_puerto_rico(self):
        for f in self.d["features"]:
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(-67.35 < lon < -65.2 and 17.85 < lat < 18.55, f["properties"]["usgs"])

    def test_the_file_is_what_the_cache_gives_when_the_cache_is_here(self):
        if not (rn.CACHE / "sites.json").exists():
            self.skipTest("no cache on this machine")
        self.assertEqual(rn.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
