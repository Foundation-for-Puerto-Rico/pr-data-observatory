"""Power plants (power_plants.py, HANDOFF decision 104 step 1): what the published file holds, and the rules that make it.

    python -m unittest tests.test_power_plants
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import power_plants as pp  # noqa: E402

FILE = ROOT / "site" / "data" / "power_plants.geojson"
KEYS = {"name", "type", "municipio", "geoid", "eia", "tech", "mw", "bat_mw", "bat_mwh", "by", "sb", "out", "units", "y0", "y1", "plan", "plan_ym", "status",
        "stage", "as_of", "src", "url", "osm"}   # the last five: a built plant added from energy_src/plants_added.json


class Rules(unittest.TestCase):
    def test_every_eia_technology_has_a_group_and_an_unknown_one_stops_the_build(self):
        self.assertEqual(pp.tech_of("Solar Photovoltaic"), "solar")
        self.assertEqual(pp.tech_of("Natural Gas Fired Combined Cycle"), "gas")
        self.assertEqual(pp.tech_of("Batteries"), "battery")
        with self.assertRaises(SystemExit):
            pp.tech_of("Fusion")

    def test_the_owner_column_is_never_read(self):
        self.assertNotIn("Entity Name", pp.OP_COLS + pp.PL_COLS)
        self.assertNotIn("Entity ID", pp.OP_COLS + pp.PL_COLS)


class File(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))
        cls.p = [f["properties"] for f in cls.d["features"]]

    def test_only_the_published_fields_and_no_owner(self):
        for p in self.p:
            self.assertLessEqual(set(p), KEYS, p["name"])
            self.assertEqual(p["type"], "Power plant")
            self.assertIn(p["status"], ("op", "planned", "built"))
            self.assertIn(p["tech"], set(pp.TECH.values()))

    def test_points_are_in_puerto_rico_and_in_a_municipio(self):
        names = json.loads((ROOT / "site" / "data" / "municipios.geojson").read_text(encoding="utf-8"))
        munis = {f["properties"]["municipality"] for f in names["features"]}
        for f in self.d["features"]:
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(-68.0 < lon < -65.2 and 17.8 < lat < 18.6, f["properties"]["name"])
            self.assertIn(f["properties"]["municipio"], munis)

    def test_the_notes_add_up(self):
        op = [p for p in self.p if p["status"] == "op"]
        n = self.d["notes"]
        self.assertGreaterEqual(n["plants"], pp.FLOOR)
        self.assertEqual(n["plants"], len(op))
        self.assertAlmostEqual(n["mw"], sum(p["mw"] for p in op), delta=0.1 * len(op))
        self.assertAlmostEqual(n["battery_mw"], sum(p.get("bat_mw", 0) for p in op), delta=0.1 * len(op))
        by = {}
        for p in op:
            for k, v in p["by"].items():
                by[k] = by.get(k, 0) + v
        self.assertAlmostEqual(n["renewable_mw"], sum(v for k, v in by.items() if k in pp.RENEWABLE), delta=0.1 * len(op))
        for p in op:   # the main technology is the one with the most MW without batteries
            gen = {k: v for k, v in p["by"].items() if k != "battery"}
            if gen:
                self.assertEqual(gen[p["tech"]], max(gen.values()), p["name"])
                self.assertAlmostEqual(p["mw"], sum(gen.values()), delta=0.1 * len(gen))

    def test_built_plants_are_added_apart_from_eias_totals(self):
        built = [p for p in self.p if p["status"] == "built"]
        added = json.loads(pp.ADDED.read_text(encoding="utf-8"))["plants"]
        n = self.d["notes"]
        self.assertEqual(len(built) + len(n["built_absorbed"]), len(added), "every added plant is in the file, or EIA lists it now")
        self.assertEqual(n["built_plants"], len(built))
        self.assertAlmostEqual(n["built_mw"], sum(p["mw"] for p in built), delta=0.1 * max(1, len(built)))
        for p in built:
            self.assertNotIn("eia", p)
            self.assertIn(p["stage"], ("connected", "complete"))
            self.assertRegex(p["as_of"], r"^20\d\d-\d\d$")
            self.assertTrue(p["url"].startswith("https://") and p["src"] and p["osm"], p["name"])
            self.assertEqual(p["tech"], "solar")

    def test_an_added_plant_leaves_the_file_once_eia_lists_it(self):
        M = pp.fac.Munis()
        none_yet, _ = pp.added({}, M)
        listed, absorbed = pp.added({"1": {"name": "CIRO One Salinas LLC"}}, M)
        self.assertEqual(len(listed), len(none_yet) - 1)
        self.assertEqual(absorbed, ["CIRO One Salinas"])

    def test_sorted_largest_first(self):
        mw = [p["mw"] or p.get("bat_mw", 0) for p in self.p]
        self.assertEqual(mw, sorted(mw, reverse=True))


if __name__ == "__main__":
    unittest.main()
