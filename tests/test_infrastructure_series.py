"""Tests for infrastructure_series.py (Phase 3, item 10): what is kept, FHWA's bridge condition rule, how water systems are counted, and the published files. No network."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import infrastructure_series as inf  # noqa: E402

DATA = ROOT / "site" / "data"
BANNED = re.compile(r"(?i)\bname\b|plant name|entity|pwsname|address|phone|email|contact")   # "Nameplate Capacity" is a capacity, not a name


class Kept(unittest.TestCase):
    def test_no_name_or_contact_column_is_kept(self):
        for cols in (list(inf.ECHO_COLS.values()), inf.CWA_KEEP, inf.AIR_KEEP, inf.RCRA_KEEP, inf.ALL_KEEP, inf.EIA_KEEP, inf.NBI_KEEP):
            self.assertEqual([c for c in cols if BANNED.search(c)], [], cols)

    def test_the_caches_hold_only_those_columns(self):
        p = inf.CACHE / "echo_cws.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8")):
                self.assertEqual(set(r), set(inf.ECHO_COLS.values()))
        p = inf.CACHE / "echo_npdes.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.CWA_KEEP))
                self.assertEqual(r["CWPPermitTypeDesc"], inf.CWA_INDIVIDUAL, "only individual permits are kept")
        p = inf.CACHE / "echo_air.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.AIR_KEEP))
        p = inf.CACHE / "echo_rcra.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.RCRA_KEEP))
        p = inf.CACHE / "echo_all.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.ALL_KEEP))
        p = inf.CACHE / "tri_releases.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.TRI_KEEP), "no facility name in the cache")
        p = inf.CACHE / "eia860m_operating.pr.json"
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(inf.EIA_KEEP))

    def test_no_published_file_holds_a_point_or_a_name(self):
        for f in ("infrastructure_series.json", "bridges_series.json"):
            p = DATA / f
            if p.exists():
                t = p.read_text(encoding="utf-8")
                self.assertNotRegex(t, r"-6[5-7]\.\d{4,}", f"{f}: a longitude")
                self.assertNotIn("PWSId", t)
                self.assertNotIn("Plant ID", t)
                self.assertNotIn("SourceID", t)
                self.assertNotRegex(t, r"\bPR00\d{5}\b", f"{f}: a permit number")


class Rules(unittest.TestCase):
    def rec(self, deck="7", sup="7", sub="7", cul="N"):
        return {"DECK_COND_058": deck, "SUPERSTRUCTURE_COND_059": sup, "SUBSTRUCTURE_COND_060": sub, "CULVERT_COND_062": cul}

    def test_fhwa_condition_rule(self):
        self.assertEqual(inf.condition(self.rec()), "G")
        self.assertEqual(inf.condition(self.rec(sub="5")), "F")
        self.assertEqual(inf.condition(self.rec(deck="4")), "P")
        self.assertEqual(inf.condition(self.rec(deck="N", sup="N", sub="N", cul="3")), "P")   # a culvert is rated on its own
        self.assertIsNone(inf.condition(self.rec(deck="N", sup="N", sub="N", cul="N")))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "infrastructure_series.json").exists():
            raise unittest.SkipTest("not built")
        cls.i = json.loads((DATA / "infrastructure_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "bridges_series.json").read_text(encoding="utf-8"))
        cls.I = {v["key"]: list(v["years"].values())[0] for v in cls.i["vars"]}

    def test_shape(self):
        for d in (self.i, self.b):
            self.assertEqual(len(d["geo"]["ids"]), 79)
            for v in d["vars"]:
                for a in v["years"].values():
                    self.assertEqual(len(a), 79, v["key"])

    def test_the_island_counts_each_water_system_once(self):
        n = self.i["notes"]["water"]
        self.assertEqual(self.I["water_systems"][-1], n["systems"])
        self.assertGreater(sum(self.I["water_systems"][:78]), n["systems"] - n["with_no_municipality"], "a system serving several municipalities counts in each")
        self.assertLessEqual(self.I["water_health_vio"][-1], self.I["water_systems"][-1])
        self.assertLessEqual(self.I["water_priority"][-1], self.I["water_systems"][-1])

    def test_wastewater_permits_count_each_facility_once_in_one_municipality(self):
        n = self.i["notes"]["wastewater"]
        for k, note in (("wastewater_permits", "individual_permits"), ("wastewater_plants", "public_sewage_treatment_plants"), ("wastewater_major", "major"), ("wastewater_violation", "with_a_violation_on_record")):
            self.assertEqual(self.I[k][-1], sum(self.I[k][:78]), f"{k}: Puerto Rico is the sum of the municipalities")
            self.assertEqual(self.I[k][-1], n[note], k)
        for i in range(79):   # the plants, the major dischargers and those with a violation are among the permitted facilities of the municipality
            for k in ("wastewater_plants", "wastewater_major", "wastewater_violation"):
                self.assertLessEqual(self.I[k][i], self.I["wastewater_permits"][i], k)
        self.assertLessEqual(n["in_significant_noncompliance"], n["with_a_violation_on_record"])
        self.assertEqual(n["active_records_by_permit_type"][inf.CWA_INDIVIDUAL], n["individual_permits"])
        self.assertGreaterEqual(n["individual_permits"], inf.FLOORS["wastewater"])
        self.assertEqual(inf.CWA_VIOLATION, {"Violation Identified", "Significant/Category I Noncompliance"}, "a permit ECHO shows in compliance, or of unknown status, is not a violation")

    def test_air_sources_count_each_facility_once_in_one_municipality(self):
        n = self.i["notes"]["air"]
        for k, note in (("air_sources", "active_sources"), ("air_major", "major")):
            self.assertEqual(self.I[k][-1], sum(self.I[k][:78]), f"{k}: Puerto Rico is the sum of the municipalities")
            self.assertEqual(self.I[k][-1], n[note], k)
        for i in range(79):   # the major sources are among the regulated facilities of the municipality
            self.assertLessEqual(self.I["air_major"][i], self.I["air_sources"][i])
        self.assertEqual(sum(n["by_class"].values()), n["active_sources"])
        self.assertEqual(n["by_class"][inf.AIR_MAJOR], n["major"])
        self.assertGreaterEqual(n["active_sources"], inf.FLOORS["air"])
        self.assertNotIn("air_violation", self.I, "the sources with a violation are too few to publish for each municipality")

    def test_hazardous_waste_handlers_count_each_handler_once_in_one_municipality(self):
        n = self.i["notes"]["hazwaste"]
        for k, note in (("hazwaste_handlers", "active_handlers"), ("hazwaste_large", "large_quantity_generators")):
            self.assertEqual(self.I[k][-1], sum(self.I[k][:78]), f"{k}: Puerto Rico is the sum of the municipalities")
            self.assertEqual(self.I[k][-1], n[note], k)
        for i in range(79):   # the large generators are among the handlers of the municipality
            self.assertLessEqual(self.I["hazwaste_large"][i], self.I["hazwaste_handlers"][i])
        self.assertEqual(sum(n["by_class"].values()), n["active_handlers"])
        self.assertEqual(n["large_quantity_generators"], sum(c for k, c in n["by_class"].items() if inf.RCRA_LARGE in [x.strip() for x in k.split(",")]), "a handler in several classes counts once")
        self.assertGreaterEqual(n["active_handlers"], inf.FLOORS["hazwaste"])
        self.assertNotIn("hazwaste_violation", self.I, "the handlers with a violation are too few to publish for each municipality")

    def test_inspections_and_enforcement_count_each_facility_once(self):
        n = self.i["notes"]["enforcement"]
        for k, note in (("epa_inspected", "inspected_in_five_years"), ("epa_formal_action", "with_a_formal_action_in_five_years")):
            self.assertEqual(self.I[k][-1], sum(self.I[k][:78]), f"{k}: Puerto Rico is the sum of the municipalities")
            self.assertEqual(self.I[k][-1], n[note], k)
            self.assertLessEqual(self.I[k][-1], n["active_regulated_facilities"])
        self.assertLessEqual(n["inspected_in_five_years"], n["inspections"], "a facility inspected several times counts once")
        self.assertLessEqual(n["with_a_formal_action_in_five_years"], n["formal_actions"])
        self.assertGreaterEqual(n["active_regulated_facilities"], inf.FLOORS["regulated"])
        self.assertLess(n["not_placed"], 20, "nearly every facility has a point on the island or a county code")
        self.assertEqual((inf.count("3"), inf.count(""), inf.count(None), inf.count(" 12 ")), (3, 0, 0, 12))

    def test_a_point_far_from_every_municipality_stops_the_build_unless_asked(self):
        with self.assertRaises(SystemExit):
            inf.locate([(-77.0, 39.9)])
        self.assertEqual(inf.locate([(-77.0, 39.9), (-66.1, 18.4)], strict=False)[0], None)
        self.assertRegex(inf.locate([(-77.0, 39.9), (-66.1, 18.4)], strict=False)[1], r"^72\d{3}$")

    def test_toxic_releases_are_whole_pounds_that_add_up(self):
        n = self.i["notes"]["tri"]
        for k, note in (("tri_release_lb", "total_lb"), ("tri_air_lb", "air_lb")):
            self.assertEqual(self.I[k][-1], n[note], k)
            self.assertLessEqual(abs(self.I[k][-1] - sum(self.I[k][:78])), 78, f"{k}: Puerto Rico is the sum of the municipalities, to the rounding of each")
            self.assertTrue(all(isinstance(x, int) and x >= 0 for x in self.I[k]), k)
        for i in range(79):   # the pounds released to the air are among the pounds released
            self.assertLessEqual(self.I["tri_air_lb"][i], self.I["tri_release_lb"][i] + 1)
        self.assertGreaterEqual(n["facilities"], inf.FLOORS["tri"])
        self.assertLessEqual(sum(1 for x in self.I["tri_release_lb"][:78] if x), n["municipalities_with_a_facility"])
        self.assertNotIn("name", inf.TRI_COLS, "the facility's name is never read")
        self.assertAlmostEqual(inf.LB_PER_GRAM * 453.59237, 1, places=5)

    def test_power_sums_and_renewables(self):
        for k in ("power_plants", "power_mw", "power_renewable_mw"):
            self.assertAlmostEqual(self.I[k][-1], sum(self.I[k][:78]), delta=0.5, msg=k)
        for i in range(79):
            self.assertLessEqual(self.I["power_renewable_mw"][i], self.I["power_mw"][i] + 0.05)

    def test_bridges(self):
        V = {v["key"]: v["years"] for v in self.b["vars"]}
        for y in V["bridges"]:
            self.assertEqual(V["bridges"][y][-1], sum(V["bridges"][y][:78]))
            self.assertEqual(V["bridges_poor"][y][-1], sum(V["bridges_poor"][y][:78]))
            nb = self.b["notes"][y]
            self.assertEqual(nb["fhwa_condition_agrees"], nb["fhwa_condition_given"], y)
        self.assertEqual((V["bridges"]["2025"][-1], V["bridges_poor"]["2025"][-1]), (2434, 344))   # FHWA's 2025 file: 344 of 2,434 poor (14.1%), the figure the plan quoted

    def test_every_variable_has_an_entry_and_spanish(self):
        ids = {e["id"] for e in json.loads((ROOT / "dictionary_src" / "entries" / "infrastructure.json").read_text(encoding="utf-8"))}
        es = json.loads((ROOT / "i18n_src" / "es" / "labels_infrastructure.json").read_text(encoding="utf-8"))
        for d in (self.i, self.b):
            for v in d["vars"]:
                self.assertIn("infrastructure." + v["key"], ids)
                self.assertIn(v["label"], es)
                self.assertIn("Infrastructure · " + v["group"], es)


class ByBarrio(unittest.TestCase):
    """infrastructure_barrio.json: seven ECHO counts for the 901 barrios."""

    @classmethod
    def setUpClass(cls):
        data = ROOT / "site" / "data"
        cls.b = json.loads((data / "infrastructure_barrio.json").read_text(encoding="utf-8"))
        cls.s = json.loads((data / "infrastructure_series.json").read_text(encoding="utf-8"))
        cls.vars = {v["key"]: v for v in cls.s["vars"]}

    def test_the_seven_counts_and_only_they_are_given_by_barrio(self):
        self.assertEqual([v["key"] for v in self.b["vars"]], list(inf.BARRIO_KEYS))
        for k, v in self.vars.items():
            self.assertEqual(v.get("barrioFile"), "infrastructure_barrio.json" if k in inf.BARRIO_KEYS else None, k)
        for held in ("wastewater_violation", "epa_inspected", "epa_formal_action", "tri_release_lb", "tri_air_lb"):
            self.assertNotIn(held, inf.BARRIO_KEYS, "a barrio's figure would be one facility's own record")

    def test_901_barrios_whole_counts_and_the_island_total_of_the_municipality_file(self):
        ids = self.b["geo"]["ids"]
        self.assertEqual(len(ids), 901)
        self.assertEqual(self.b["level"], "barrio")
        for v in self.b["vars"]:
            (year, vals), = v["years"].items()
            self.assertEqual(list(self.vars[v["key"]]["years"]), [year])
            self.assertEqual(len(vals), 901)
            self.assertTrue(all(isinstance(n, int) and n >= 0 for n in vals), v["key"])
            n = self.b["notes"]["counts"][v["key"]]
            self.assertEqual(sum(vals) + n["outside_every_barrio"], self.vars[v["key"]]["years"][year][-1], v["key"])
            self.assertEqual(n["barrios_with_one_or_more"], sum(x > 0 for x in vals))

    def test_a_subset_never_exceeds_its_whole_in_any_barrio(self):
        col = {v["key"]: next(iter(v["years"].values())) for v in self.b["vars"]}
        for part, whole in (("wastewater_plants", "wastewater_permits"), ("wastewater_major", "wastewater_permits"), ("air_major", "air_sources"), ("hazwaste_large", "hazwaste_handlers")):
            self.assertTrue(all(a <= b for a, b in zip(col[part], col[whole])), part)

    def test_a_municipalitys_barrios_add_up_to_its_count_but_for_points_on_a_municipal_line(self):
        ids = self.b["geo"]["ids"]
        mids = self.s["geo"]["ids"]
        for v in self.b["vars"]:
            (year, vals), = v["years"].items()
            by = {}
            for i, n in zip(ids, vals):
                by[i[:5]] = by.get(i[:5], 0) + n
            muni = dict(zip(mids, self.vars[v["key"]]["years"][year]))
            differ = sum(by.get(f, 0) != muni[f] for f in mids if f != "72")
            self.assertEqual(differ, self.b["notes"]["counts"][v["key"]]["municipalities_whose_barrios_add_up_to_another_count"], v["key"])
            self.assertLessEqual(differ, 6, v["key"])

    def test_no_name_or_point_reaches_the_file(self):
        text = (ROOT / "site" / "data" / "infrastructure_barrio.json").read_text(encoding="utf-8")
        for word in ("FacName", "FacLat", "FacLong", "SourceID", "FacStreet"):
            self.assertNotIn(word, text)
        self.assertEqual(set(self.b), {"built", "level", "geo", "vars", "notes"})


if __name__ == "__main__":
    unittest.main()
