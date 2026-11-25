"""Facilities, students and main roads in the flood, sea level rise and landslide areas (facility_exposure.py, HANDOFF decision 107 step 3): the overlay on
invented shapes, and the published file.

    python -m unittest tests.test_facility_exposure

The published file is checked WITHOUT the cache. One test needs the caches (school directory, NOAA's sea level rise extents, landslide tiles) and skips without them.
"""
import json
import sys
import unittest
from pathlib import Path

from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import facility_exposure as fx  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
FLOOD = [box(-66.10, 18.00, -66.00, 18.10)]   # one square flood area


def square(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


class Overlay(unittest.TestCase):
    """Two municipios: A west of -66.05 and B east of it. The flood square covers part of each."""

    def setUp(self):
        pts = [{"kind": "Police stations", "geoid": "A", "x": -66.08, "y": 18.05},    # inside
               {"kind": "Police stations", "geoid": "A", "x": -66.20, "y": 18.05},    # outside
               {"kind": "City halls", "geoid": "B", "x": -66.02, "y": 18.20}]         # outside
        schools = [{"geoid": "A", "x": -66.07, "y": 18.02, "students": 300},           # inside
                   {"geoid": "A", "x": -66.30, "y": 18.02, "students": 100},           # outside
                   {"geoid": "B", "x": -66.01, "y": 18.01, "students": None}]          # inside, enrollment not given
        self.fig, self.counts = fx.figures(pts, schools, {"A": [10.0, 2.5], "B": [0.0, 0.0]}, FLOOD, ["A", "B"])

    def test_a_point_inside_counts_and_one_outside_does_not(self):
        self.assertEqual(self.fig["fx_flood_n"], [2, 1, 3], "A: a station and a school; B: a school; then Puerto Rico")
        self.assertEqual(self.fig["fx_flood_pct"], [50.0, 50.0, 50.0])
        self.assertEqual(self.counts["Police stations"], [2, 1])

    def test_students_follow_their_school_and_a_missing_enrolment_adds_none(self):
        self.assertEqual(self.fig["fx_schools_flood_n"], [1, 1, 2])
        self.assertEqual(self.fig["fx_students_flood_n"], [300, 0, 300])
        self.assertEqual(self.fig["fx_students_flood_pct"][0], 75.0)
        self.assertIsNone(self.fig["fx_students_flood_pct"][1], "no enrollment is known in B: no share, never a zero")

    def test_road_shares_are_of_the_municipios_own_roads_and_none_without_roads(self):
        self.assertEqual(self.fig["fx_road_flood_km"], [2.5, 0.0, 2.5])
        self.assertEqual(self.fig["fx_road_flood_pct"], [25.0, None, 25.0])

    def test_a_facility_in_an_unknown_municipio_stops_the_build(self):
        with self.assertRaises(SystemExit):
            fx.figures([{"kind": "City halls", "geoid": "Z", "x": 0, "y": 0}], [], {}, FLOOD, ["A"])

    def test_a_road_is_cut_at_the_municipio_line_and_at_the_flood_edge(self):
        munis = {"features": [{"properties": {"GEOID": "A"}, "geometry": square(-66.30, 17.90, -66.05, 18.30)},
                              {"properties": {"GEOID": "B"}, "geometry": square(-66.05, 17.90, -65.90, 18.30)}]}
        road = {"features": [{"geometry": {"type": "LineString", "coordinates": [[-66.20, 18.05], [-65.95, 18.05]]}}]}   # west to east through both and through the flood square
        km = fx.road_km(road, munis, FLOOD)
        deg = fx.KX / 1000
        self.assertAlmostEqual(km["A"][0], 0.15 * deg, places=2)
        self.assertAlmostEqual(km["A"][1], 0.05 * deg, places=2, msg="-66.10 to -66.05 is inside the flood square")
        self.assertAlmostEqual(km["B"][0], 0.10 * deg, places=2)
        self.assertAlmostEqual(km["B"][1], 0.05 * deg, places=2)

    def test_a_hazard_the_map_does_not_cover_gives_no_value_and_is_left_out_of_puerto_rico(self):
        every = [{"kind": "Police stations", "geoid": "A", "students": None}, {"kind": "Public schools", "geoid": "A", "students": 200},
                 {"kind": "Public schools", "geoid": "A", "students": 600}, {"kind": "City halls", "geoid": "B", "students": None}]
        fig, counts = fx.hazard_figures(every, [True, True, False, True], {"A": [10.0, 4.0], "B": [5.0, 5.0]}, ["A", "B"], "ls", {"B"})
        self.assertEqual(fig["fx_ls_n"], [2, None, 2])
        self.assertEqual(fig["fx_ls_pct"], [66.7, None, 66.7])
        self.assertEqual(fig["fx_students_ls_pct"], [25.0, None, 25.0])
        self.assertEqual(fig["fx_road_ls_km"], [4.0, None, 4.0], "B's roads are not in Puerto Rico's figure: the map does not cover B")
        self.assertEqual(fig["fx_road_ls_pct"], [40.0, None, 40.0])
        self.assertNotIn("City halls", counts)

    def test_a_road_is_read_every_20_m_on_the_landslide_map(self):
        from shapely.geometry import LineString
        line = LineString([(0, 0), (1000, 0)])   # 1 km, in meters; the west half is on high ground
        km = fx.road_ls_km([("A", line)], lambda lon, lat: (lon * fx.KX < 500).astype(int) * 4)
        self.assertAlmostEqual(km["A"], 0.5, places=3)

    def test_points_stacked_at_one_address_are_not_tested(self):
        import tempfile
        real = fx.hs.OUT
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name in fx.LAYERS:
                pts = [(-66.1, 18.1), (-66.1, 18.1), (-66.2, 18.2)] if name == "libraries.geojson" else []
                (d / name).write_text(json.dumps({"features": [{"geometry": {"coordinates": list(c)}, "properties": {"geoid": "A"}} for c in pts]}), encoding="utf-8")
            fx.hs.OUT = d
            try:
                pts = fx.facility_points()
            finally:
                fx.hs.OUT = real
        self.assertEqual([(q["x"], q["y"]) for q in pts], [(-66.2, 18.2)], "two libraries at one point are left out; the one on its own is kept")
        self.assertEqual(fx.STACKED, {"Libraries": 2})

    def test_flags_and_grades(self):
        self.assertEqual(fx.flag_codes(True, False, True), "fl")
        self.assertEqual(fx.grades(-1, 12), "PK-12")
        self.assertEqual(fx.grades(0, 5), "K-5")
        self.assertEqual(fx.grades(9, 9), "9")
        self.assertIsNone(fx.grades(-9, 12))
        self.assertEqual(fx.point_key(-66.1, 18.12345), "-66.10000,18.12345")

    def test_the_newest_school_year_is_one_with_students(self):
        real = fx.school_rows
        rows = [{"ncessch": str(i), "county_code": "72001", "latitude": 18.1, "longitude": -66.1, "school_status": 1, "enrollment": 100} for i in range(700)]
        fx.school_rows = lambda year, refresh=False, offline=False: [] if year > 2024 else [{**r, "enrollment": None} for r in rows] if year == 2024 else rows
        try:
            import datetime
            year, schools, no_point = fx.newest_schools(today=datetime.date(2026, 11, 16))
        finally:
            fx.school_rows = real
        self.assertEqual((year, len(schools), no_point), (2023, 700, 0), "a year without its students yet is passed over")


class PublishedLayers(unittest.TestCase):
    """public_schools.geojson and facility_hazards.json agree with the figures."""

    @classmethod
    def setUpClass(cls):
        cls.schools = json.loads((DATA / "public_schools.geojson").read_text(encoding="utf-8"))
        cls.hz = json.loads((DATA / "facility_hazards.json").read_text(encoding="utf-8"))
        doc = json.loads((DATA / "facility_exposure_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v["years"][str(doc["years"][0])][-1] for v in doc["vars"]}

    def test_the_school_layer_holds_the_schools_tested_with_their_flags(self):
        f = self.schools["features"]
        self.assertEqual(len(f), self.schools["notes"]["schools"])
        self.assertEqual(sum(1 for x in f if "f" in x["properties"].get("hz", "")), self.v["fx_schools_flood_n"])
        self.assertEqual(sum(x["properties"]["students"] or 0 for x in f if "f" in x["properties"].get("hz", "")), self.v["fx_students_flood_n"])
        self.assertTrue(all(set(x["properties"]) <= {"name", "type", "municipio", "geoid", "students", "grades", "nces", "hz"} for x in f), "no address, no contact fields")

    def test_the_flags_add_up_to_the_counts(self):
        for code, key in (("f", "fx_flood_n"), ("s", "fx_slr_n"), ("l", "fx_ls_n")):
            n = sum(1 for x in self.schools["features"] if code in x["properties"].get("hz", "")) + sum(1 for m in self.hz["layers"].values() for c in m.values() if code in c)
            self.assertEqual(n, self.v[key], key)

    def test_every_flagged_point_is_a_point_of_its_layer(self):
        files = {v: k for k, v in fx.LAYER_KEY.items()}
        for layer, m in self.hz["layers"].items():
            keys = {fx.point_key(*g["geometry"]["coordinates"][:2]) for g in json.loads((DATA / files[layer]).read_text(encoding="utf-8"))["features"]}
            self.assertLessEqual(set(m), keys, layer)
            self.assertTrue(all(c and set(c) <= set("fsl") for c in m.values()), layer)


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "facility_exposure_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v["years"][str(cls.doc["years"][0])] for v in cls.doc["vars"]}

    def test_the_areas_are_those_of_the_other_series(self):
        pop = json.loads((DATA / "population_series.json").read_text(encoding="utf-8"))
        self.assertEqual(self.doc["geo"], pop["geo"])
        self.assertEqual(len(self.doc["vars"]), 17)
        for k, vals in self.v.items():
            self.assertEqual(len(vals), 79, k)

    def test_puerto_rico_is_the_sum_of_the_municipios(self):
        for k in ("fx_flood_n", "fx_schools_flood_n", "fx_students_flood_n"):
            self.assertEqual(sum(self.v[k][:78]), self.v[k][78], k)
        self.assertAlmostEqual(sum(self.v["fx_road_flood_km"][:78]), self.v["fx_road_flood_km"][78], delta=4.0)   # 78 values rounded to 0.1 km

    def test_the_landslide_map_leaves_out_vieques_and_culebra_only(self):
        ids = self.doc["geo"]["ids"]
        for k in ("fx_ls_n", "fx_ls_pct", "fx_road_ls_km"):
            none = {ids[i] for i, x in enumerate(self.v[k]) if x is None}
            self.assertEqual(none, {"72049", "72147"}, k)
        self.assertEqual(sum(x for x in self.v["fx_ls_n"][:78] if x is not None), self.v["fx_ls_n"][78])
        self.assertEqual(sum(self.v["fx_slr_n"][:78]), self.v["fx_slr_n"][78])
        self.assertEqual(self.v["fx_slr_n"][78], sum(x["in_the_area"] for x in self.doc["notes"]["tested_slr"].values()))
        self.assertEqual(self.v["fx_ls_n"][78], sum(x["on_high_or_above"] for x in self.doc["notes"]["tested_landslide"].values()))

    def test_the_sea_reaches_no_more_than_the_3_ft_area_of_inland_municipios(self):
        names = dict(zip(self.doc["geo"]["ids"], self.doc["geo"]["names"]))
        inland = [g for g, n in names.items() if n in ("Aibonito", "Barranquitas", "Orocovis", "Utuado", "Jayuya", "Cidra", "Comerío", "Lares")]
        self.assertEqual(len(inland), 8)
        for g in inland:
            i = self.doc["geo"]["ids"].index(g)
            self.assertEqual(self.v["fx_slr_n"][i], 0, names[g])
            self.assertEqual(self.v["fx_road_slr_km"][i], 0.0, names[g])

    def test_counts_fit_what_was_tested_and_shares_are_percents(self):
        t = self.doc["notes"]["tested"]
        self.assertEqual(self.v["fx_flood_n"][78], sum(x["in_the_flood_area"] for x in t.values()))
        self.assertEqual(self.v["fx_schools_flood_n"][78], t["Public schools"]["in_the_flood_area"])
        self.assertTrue(all(a >= b for a, b in zip(self.v["fx_flood_n"], self.v["fx_schools_flood_n"])), "schools are among the facilities")
        for k in ("fx_flood_pct", "fx_students_flood_pct", "fx_road_flood_pct", "fx_slr_pct", "fx_students_slr_pct", "fx_road_slr_pct", "fx_ls_pct", "fx_students_ls_pct", "fx_road_ls_pct"):
            self.assertTrue(all(x is None or 0 <= x <= 100 for x in self.v[k]), k)
        self.assertNotIn("Bridges", t, "bridges stand over water by design and are not tested")

    def test_the_notes_say_what_kind_of_figure_it_is(self):
        n = self.doc["notes"]
        self.assertTrue(n["kind"].startswith("overlaid"))
        self.assertIn("public_schools.geojson", n["drawn"])
        self.assertGreater(n["left_out_stacked"]["Libraries"], 0)
        for v in self.doc["vars"]:
            self.assertIn("(overlaid)", v["label"])
            self.assertTrue(any(w in v["definition"] for w in ("not that it floods", "may be raised", "not when or whether", "not that a slide will happen")), v["key"])

    @unittest.skipUnless(fx.CACHE.exists() and any(fx.CACHE.glob("schools_*.json")) and (fx.exposure.CACHE / "slr" / "gdb").exists()
                         and (fx.ROOT / "cache" / "landslide" / "z15").exists(), "needs the cached school directory, sea level rise extents and landslide tiles")
    def test_the_cache_gives_the_published_file_again(self):
        self.assertEqual(fx.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
