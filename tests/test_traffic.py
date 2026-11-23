"""traffic.py: the traffic layer and the municipio figures from FHWA's HPMS. The joining and classing rules are tested on made-up sections; the published
files are checked against each other and, where the downloads are cached, against a rebuild."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import traffic as tr   # noqa: E402

DATA = ROOT / "site" / "data"


def section(oid, b, e, aadt, route="PR-1", name="PR-1", x0=-66.0, **kw):
    a = {"objectid": oid, "route_id": route, "route_name": name, "begin_point": b, "end_point": e, "section_length": e - b, "f_system": 3, "county_id": 127,
         "aadt": aadt, "aadt_vd": "2024-01-01", "aadt_single_unit": None, "aadt_combination": None, "through_lanes": 2, "speed_limit": 35, "nhs": None, **kw}
    return {"attributes": a, "geometry": {"paths": [[[x0 + b / 100, 18.4], [x0 + e / 100, 18.4]]]}}


class Rules(unittest.TestCase):
    def test_colour_classes(self):
        self.assertEqual([tr.colour_class(v) for v in (1, 1999, 2000, 4999, 5000, 10000, 19999, 20000, 39999, 40000, 266200)], [1, 1, 2, 2, 3, 4, 4, 5, 5, 6, 6])

    def test_consecutive_sections_with_one_count_are_one_stretch(self):
        secs = [section(1, 0.0, 0.5, 9000), section(2, 0.5, 1.0, 9000), section(3, 1.0, 1.5, 12000), section(4, 2.0, 2.5, 12000),   # a gap before 4
                section(5, 0.0, 0.5, 9000, route="PR-2", name="PR-2")]
        out = tr.stretches(secs, {i: 2 for i in range(1, 6)})
        got = sorted((s["route"], s["aadt"], round(s["km"], 3)) for s in out)
        self.assertEqual(got, [("PR-1", 9000, round(1.0 * tr.MILE_KM, 3)), ("PR-1", 12000, round(0.5 * tr.MILE_KM, 3)), ("PR-1", 12000, round(0.5 * tr.MILE_KM, 3)), ("PR-2", 9000, round(0.5 * tr.MILE_KM, 3))])

    def test_truck_share_is_weighted_by_length_and_left_out_when_not_reported(self):
        secs = [section(1, 0.0, 0.5, 10000, aadt_single_unit=400, aadt_combination=100), section(2, 0.5, 1.5, 10000, aadt_single_unit=1000, aadt_combination=500)]
        s = tr.stretches(secs, {1: 2, 2: 2})[0]
        self.assertEqual(s["trucks_pct"], round(100 * (500 * 0.5 + 1500 * 1.0) / 1.5 / 10000, 1))
        self.assertIsNone(tr.stretches([section(3, 0, 1, 5000)], {3: 1})[0]["trucks_pct"])
        self.assertTrue(tr.stretches([section(3, 0, 1, 5000)], {3: 1})[0]["oneway"])


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "traffic_series.json").read_text(encoding="utf-8"))
        cls.l = json.loads((DATA / "traffic_roads.geojson").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v["years"][str(cls.s["years"][0])] for v in cls.s["vars"]}

    def test_the_series_has_every_municipio_and_puerto_rico(self):
        g = self.s["geo"]
        self.assertEqual(len(g["ids"]), 79)
        self.assertEqual(g["ids"][-1], "72")
        self.assertEqual(g["names"][-1], "Puerto Rico")
        self.assertEqual([v[0] for v in tr.V], [v["key"] for v in self.s["vars"]])
        for k, vals in self.v.items():
            self.assertEqual(len(vals), 79, k)

    def test_municipios_add_up_to_puerto_rico(self):
        for k in ("traffic_vkt", "traffic_main_km"):
            vals = self.v[k]
            self.assertAlmostEqual(sum(vals[:-1]), vals[-1], delta=0.2 * 79 if k == "traffic_main_km" else 79, msg=k)
        self.assertEqual(self.v["traffic_max_aadt"][-1], max(x for x in self.v["traffic_max_aadt"][:-1] if x))
        for k in ("traffic_truck_pct", "traffic_poor_pct"):
            self.assertTrue(all(x is None or 0 <= x <= 100 for x in self.v[k]), k)

    def test_the_layer_matches_its_notes_and_its_classes(self):
        f, n = self.l["features"], self.l["notes"]
        self.assertEqual(n["stretches"], len(f))
        self.assertAlmostEqual(n["km"], sum(x["properties"]["km"] for x in f), delta=1)
        for x in f:
            p = x["properties"]
            self.assertEqual(p["c"], tr.colour_class(p["a"]))
            self.assertIn(p["f"], (1, 2, 3, 4, 5))
            self.assertGreater(p["a"], 0)
            self.assertTrue(set(p) <= {"c", "a", "r", "f", "y", "l", "km", "t", "s", "o"}, p)
        self.assertEqual([x["properties"]["a"] for x in f], sorted(x["properties"]["a"] for x in f), "the busiest roads are drawn last")
        self.assertLessEqual(max(x["properties"]["a"] for x in f), self.v["traffic_max_aadt"][-1])

    def test_the_maps_name_the_layer_file(self):
        src = (ROOT / "site" / "js" / "core" / "facilities.js").read_text(encoding="utf-8")
        self.assertIn("file: 'traffic_roads.geojson'", src)
        for lab in tr.CLASS_NAMES[1:]:
            self.assertIn(f"TK('{lab}')", src)

    def test_the_simulated_connections_carry_the_traffic_of_their_roads(self):
        d = json.loads((DATA / "transit_links.json").read_text(encoding="utf-8"))
        self.assertEqual(d["traffic"]["data_year"], self.s["years"][0])
        pairs = [dict(zip(d["pair_fields"], r)) for r in d["pairs"]]
        sims = [p for p in pairs if p["sim"]]
        self.assertTrue(all(p["aadt_max"] and p["aadt_med"] <= p["aadt_max"] and 0 < p["counted_pct"] <= 100 for p in sims))
        self.assertTrue(all(p["aadt_max"] is None for p in pairs if not p["sim"]))

    def test_the_files_are_what_the_cache_gives(self):
        if not (tr.CACHE / "year.json").exists():
            self.skipTest("the HPMS pages are not cached here (cache/traffic/)")
        self.assertEqual(tr.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
