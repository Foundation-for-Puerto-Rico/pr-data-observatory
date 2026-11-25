"""Groundwater levels (groundwater.py): the well's name, the unit, the usual depth of a week, and what the published file holds.

    python -m unittest tests.test_groundwater
"""
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import groundwater as gw  # noqa: E402

FILE = ROOT / "site" / "data" / "groundwater.geojson"


class Names(unittest.TestCase):
    def test_words_are_written_as_words_and_a_wells_code_stays_as_usgs_writes_it(self):
        for usgs, name in (("PASEO LADIS WELL AT VILLA COFRESI, SALINAS, PR", "Paseo Ladis Well at Villa Cofresí"),
                           ("ALOMAR OESTE WELL, SANTA ISABEL, PR", "Alomar Oeste Well"),
                           ("JUA 5 WELL, GUAYAMA, PR", "JUA 5 Well"),
                           ("PIEZOMETER JBNERR WEST 1 SALINAS, PR", "Piezometer JBNERR West 1 Salinas"),
                           ("CE-RUM2 OBSERVATION WELL, MAYAGUEZ CAMPUS, PR", "CE-RUM2 Observation Well"),
                           ("MW 11 WELL, LUQUILLO, PR", "MW 11 Well"),
                           ("RINCON 4 WELL, RINCON, PR", "Rincón 4 Well"),
                           ("CABO ROJO P1 WELL, CABO ROJO, PR", "Cabo Rojo P1 Well")):
            self.assertEqual(gw.well_name(usgs), name)


class Depth(unittest.TestCase):
    def test_feet_become_metres(self):
        self.assertEqual(gw.metres("100"), 30.48)
        self.assertEqual(gw.metres(3.15), 0.96)

    def test_the_usual_depth_is_the_percentile_of_each_years_weekly_mean(self):
        daily = {}
        for i, y in enumerate(range(2011, 2021)):   # ten years: week 1 stands at 10, 20, ... 100 feet below the ground
            for d in range(7):
                daily[(date(y, 1, 1) + timedelta(days=d)).isoformat()] = str(10 * (i + 1))
        norm, years = gw.normals(daily)
        self.assertEqual(years, 10)
        self.assertEqual(norm[50][0], round(55 * gw.FT, 2))
        self.assertEqual(norm[10][0], round(19 * gw.FT, 2))
        self.assertEqual(norm[90][0], round(91 * gw.FT, 2))
        self.assertIsNone(norm[50][1], "a week with no value has no usual depth")

    def test_fewer_than_eight_years_give_no_usual_depth(self):
        daily = {date(y, 1, 3).isoformat(): "10" for y in range(2011, 2018)}   # seven years
        norm, years = gw.normals(daily)
        self.assertEqual(years, 7)
        self.assertIsNone(norm[50][0])

    def test_years_outside_the_window_and_empty_values_are_left_out(self):
        daily = {"2010-01-03": "999", "2026-01-03": "999", "2015-01-03": "", "2016-01-03": None}
        self.assertEqual(gw.normals(daily)[1], 0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))
        cls.props = [f["properties"] for f in cls.d["features"]]

    def test_every_well_has_a_municipio_a_station_and_a_depth(self):
        self.assertGreaterEqual(len(self.props), 15)
        self.assertEqual(self.d["notes"]["wells"], len(self.props))
        self.assertEqual(self.d["notes"]["municipios"], len({p["geoid"] for p in self.props}))
        for p in self.props:
            self.assertRegex(p["geoid"], r"^72\d{3}$")
            self.assertRegex(p["usgs"], r"^USGS-\d+$")
            self.assertTrue(p["name"] and p["station"] and p["municipio"])
            self.assertEqual(p["type"], "Groundwater well")
            self.assertTrue(-5 < p["depth"] < 300 and p["depth_time"], p["usgs"])   # meters below the ground; a flowing well reads a little above it
            if "well_depth" in p:
                self.assertTrue(0 < p["well_depth"] < 1500, p["usgs"])
        self.assertEqual(len({p["usgs"] for p in self.props}), len(self.props), "one point a well")

    def test_the_history_has_120_days_and_53_weeks(self):
        without = 0
        for p in self.props:
            self.assertEqual(len(p["recent"]), gw.RECENT)
            for q in ("p10", "p25", "p50", "p75", "p90"):
                self.assertEqual(len(p[q]), 53)
            without += all(v is None for v in p["p50"])
            for w in range(53):
                qs = [p[q][w] for q in ("p10", "p25", "p50", "p75", "p90")]
                if qs[0] is not None:
                    self.assertEqual(qs, sorted(qs), f"{p['usgs']} week {w}: the percentiles rise")
        self.assertLessEqual(without, self.d["notes"]["without_a_usual_range"] + 0, "a well short of 8 years is counted in the notes")

    def test_no_field_beyond_the_documented_ones(self):
        allowed = {"name", "type", "municipio", "geoid", "usgs", "station", "depth", "depth_time", "well_depth", "recent_start", "recent", "p10", "p25", "p50", "p75", "p90"}
        for p in self.props:
            self.assertFalse(set(p) - allowed)

    def test_the_points_are_in_puerto_rico(self):
        for f in self.d["features"]:
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(-67.35 < lon < -65.2 and 17.85 < lat < 18.55, f["properties"]["usgs"])

    def test_the_file_is_what_the_cache_gives_when_the_cache_is_here(self):
        if not (gw.CACHE / "sites.json").exists():
            self.skipTest("no cache on this machine")
        self.assertEqual(gw.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
