"""River flow (river_gauges.py): the river's name, the unit, the usual flow of a week, and what the published file holds.

    python -m unittest tests.test_river_gauges
"""
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import river_gauges as rg  # noqa: E402

FILE = ROOT / "site" / "data" / "river_gauges.geojson"


class Names(unittest.TestCase):
    def test_the_river_is_the_start_of_the_station_name_with_its_accents(self):
        for usgs, name in (("RIO GRANDE DE LOIZA AT CAGUAS, PR", "Río Grande de Loíza"),
                           ("RIO DE LA PLATA AT HWY 2 NEAR TOA ALTA, PR", "Río de la Plata"),
                           ("RIO GRANDE DE MANATI NR MOROVIS, PR", "Río Grande de Manatí"),
                           ("QUEBRADA BLANCA AT EL JAGUAL, PR", "Quebrada Blanca"),
                           ("RIO ESPIRITU SANTO NR RIO GRANDE, PR", "Río Espíritu Santo"),
                           ("RIO BAYAMON BLW LAGO DE CIDRA DAM, PR", "Río Bayamón")):
            self.assertEqual(rg.river_name(usgs), name)

    def test_a_name_never_keeps_the_place_of_the_gauge(self):
        for cut in ("AT", "NEAR", "NR", "ABOVE", "ABV", "BELOW", "BLW"):
            self.assertEqual(rg.river_name(f"RIO TURABO {cut} BORINQUEN, PR"), "Río Turabo", cut)


class Flow(unittest.TestCase):
    def test_cubic_feet_per_second_become_cubic_metres_per_second(self):
        self.assertEqual(rg.flow("100"), 2.832)
        self.assertEqual(rg.flow(0.5), 0.014)   # a small stream keeps its thousandths

    def test_the_usual_flow_is_the_percentile_of_each_years_weekly_mean(self):
        daily = {}
        for i, y in enumerate(range(2011, 2021)):   # ten years: week 1 flows at 10, 20, ... 100 cubic feet per second
            for d in range(7):
                daily[(date(y, 1, 1) + timedelta(days=d)).isoformat()] = str(10 * (i + 1))
        norm, years = rg.normals(daily)
        self.assertEqual(years, 10)
        self.assertEqual(norm[50][0], round(55 * rg.CFS, 3))
        self.assertEqual(norm[10][0], round(19 * rg.CFS, 3))
        self.assertEqual(norm[90][0], round(91 * rg.CFS, 3))
        self.assertIsNone(norm[50][1], "a week with no value has no usual flow")

    def test_fewer_than_eight_years_give_no_usual_flow(self):
        daily = {date(y, 1, 3).isoformat(): "10" for y in range(2011, 2018)}   # seven years
        norm, years = rg.normals(daily)
        self.assertEqual(years, 7)
        self.assertIsNone(norm[50][0])

    def test_years_outside_the_window_and_empty_values_are_left_out(self):
        daily = {"2010-01-03": "999", "2026-01-03": "999", "2015-01-03": "", "2016-01-03": None}
        self.assertEqual(rg.normals(daily)[1], 0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))
        cls.props = [f["properties"] for f in cls.d["features"]]

    def test_every_gauge_has_a_municipio_a_station_and_a_flow(self):
        self.assertGreaterEqual(len(self.props), 40)
        self.assertEqual(self.d["notes"]["gauges"], len(self.props))
        for p in self.props:
            self.assertRegex(p["geoid"], r"^72\d{3}$")
            self.assertRegex(p["usgs"], r"^USGS-\d+$")
            self.assertTrue(p["name"] and p["station"] and p["municipio"])
            self.assertEqual(p["type"], "River gauge")
            self.assertGreaterEqual(p["flow"], 0)
        self.assertEqual(len({p["usgs"] for p in self.props}), len(self.props), "one point a gauge")

    def test_the_history_has_120_days_and_53_weeks(self):
        for p in self.props:
            self.assertEqual(len(p["recent"]), rg.RECENT)
            for q in ("p10", "p25", "p50", "p75", "p90"):
                self.assertEqual(len(p[q]), 53)
            for w in range(53):
                qs = [p[q][w] for q in ("p10", "p25", "p50", "p75", "p90")]
                if qs[0] is not None:
                    self.assertEqual(qs, sorted(qs), f"{p['usgs']} week {w}: the percentiles rise")

    def test_no_field_beyond_the_documented_ones(self):
        allowed = {"name", "type", "municipio", "geoid", "usgs", "station", "flow", "flow_time", "recent_start", "recent", "p10", "p25", "p50", "p75", "p90", "stage", "stage_time", "temp", "temp_time", "refs", "nws"}
        for p in self.props:
            self.assertFalse(set(p) - allowed)

    def test_gauge_height_and_flood_reference_levels(self):
        n = self.d["notes"]
        self.assertEqual(n["with_gauge_height"], sum("stage" in p for p in self.props))
        self.assertEqual(n["with_flood_reference_levels"], sum("refs" in p for p in self.props))
        self.assertGreaterEqual(n["with_gauge_height"], 40)
        for p in self.props:
            if "stage" in p:
                self.assertTrue(-5 < p["stage"] < 40 and p["stage_time"], p["usgs"])   # metres on the gauge's own scale
            for r in p.get("refs", []):
                self.assertEqual(set(r), {"kind", "label", "level"})
                self.assertIn(r["kind"], {"bank", "chord", "deck", "hwm", "other"})
            if "refs" in p:
                self.assertIn("stage", p, "a reference level is only given beside the water's own level")
                self.assertEqual([r["level"] for r in p["refs"]], sorted(r["level"] for r in p["refs"]), "lowest first")

    def test_the_points_are_in_puerto_rico(self):
        for f in self.d["features"]:
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(-67.35 < lon < -65.2 and 17.85 < lat < 18.55, f["properties"]["usgs"])




class NwsStages(unittest.TestCase):
    X = {"stage": {"USGS-1": {"value": 5.0, "time": "2026-11-12T20:00:00+00:00"}}}

    def W(self, **g):
        return {"gauges": {"USGS-1": {"lid": "AAAP4", "units": "ft", "stages": {"minor": 13.0, "action": 10.0, "major": 18.0}, "observed": None, "observed_time": None, **g}}}

    def test_feet_become_metres_in_the_order_of_the_stages(self):
        f, why = rg.nws_field("USGS-1", self.X, self.W())
        self.assertIsNone(why)
        self.assertEqual(f, {"lid": "AAAP4", "action": 3.05, "minor": 3.96, "major": 5.49})
        self.assertEqual(list(f), ["lid", "action", "minor", "major"], "only the stages NWS has set, lowest first")

    def test_a_gauge_nws_does_not_list_has_no_field_and_no_reason(self):
        self.assertEqual(rg.nws_field("USGS-9", self.X, self.W()), (None, None))

    def test_stages_are_left_out_when_they_cannot_stand_beside_the_usgs_level(self):
        self.assertIn("no gauge height", rg.nws_field("USGS-1", {"stage": {}}, self.W())[1])
        self.assertIn("not feet", rg.nws_field("USGS-1", self.X, self.W(units="m"))[1])
        self.assertIn("do not rise", rg.nws_field("USGS-1", self.X, self.W(stages={"action": 12.0, "minor": 10.0}))[1])

    def test_the_two_agencies_must_read_the_same_scale_when_their_readings_are_of_the_same_hour(self):
        near = self.W(observed=5.3, observed_time="2026-11-12T20:30:00Z")
        self.assertIsNotNone(rg.nws_field("USGS-1", self.X, near)[0])
        off = self.W(observed=105.0, observed_time="2026-11-12T20:30:00Z")
        self.assertIn("not the same scale", rg.nws_field("USGS-1", self.X, off)[1])
        later = self.W(observed=9.0, observed_time="2026-11-13T09:00:00Z")   # hours apart: the river may have risen, so the readings prove nothing
        self.assertIsNotNone(rg.nws_field("USGS-1", self.X, later)[0])

    def test_the_published_stages(self):
        d = json.loads(FILE.read_text(encoding="utf-8"))
        with_nws = [f["properties"] for f in d["features"] if "nws" in f["properties"]]
        self.assertEqual(d["notes"]["with_nws_flood_stages"], len(with_nws))
        self.assertGreaterEqual(len(with_nws), 40)
        for p in with_nws:
            self.assertIn("stage", p, "a stage is only given beside the water's own level")
            self.assertRegex(p["nws"]["lid"], r"^[A-Z0-9]{5}$")
            levels = [p["nws"][k] for k in rg.STAGES if k in p["nws"]]
            self.assertTrue(levels and levels == sorted(levels) and 0 < levels[0] and levels[-1] < 20, p["usgs"])   # metres on the gauge
            self.assertFalse(set(p["nws"]) - {"lid", *rg.STAGES})


class MoreFields(unittest.TestCase):
    X = {"stage": {"USGS-1": {"value": 10.0, "time": "2026-11-12T10:00:00+00:00"}, "USGS-2": {"value": 3.0, "time": "2026-11-12T10:00:00+00:00"}}, "temp": {"USGS-2": {"value": 25.44, "time": "t"}},
         "refs": {"USGS-1": [{"kind": "deck", "label": "Bridge Deck", "level_ft": 30.0}, {"kind": "bank", "label": "", "level_ft": 20.0}], "USGS-3": [{"kind": "bank", "label": "", "level_ft": 20.0}]}}

    def test_feet_become_metres_and_the_levels_are_sorted(self):
        f = rg.more_fields("USGS-1", self.X)
        self.assertEqual(f["stage"], 3.05)
        self.assertEqual(f["refs"], [{"kind": "bank", "label": "", "level": 6.1}, {"kind": "deck", "label": "Bridge Deck", "level": 9.14}])
        self.assertNotIn("temp", f)

    def test_a_gauge_has_only_the_fields_it_reports(self):
        self.assertEqual(rg.more_fields("USGS-2", self.X), {"stage": 0.91, "stage_time": "2026-11-12T10:00:00+00:00", "temp": 25.4, "temp_time": "t"})
        self.assertEqual(rg.more_fields("USGS-3", self.X), {}, "a reference level without the water's level is left out")
        self.assertEqual(rg.more_fields("USGS-9", self.X), {})


if __name__ == "__main__":
    unittest.main()
