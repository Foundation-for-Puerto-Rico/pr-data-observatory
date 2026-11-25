"""Transmission lines (power_lines.py, HANDOFF decision 104 step 2): only the voltages drawn, only the shape, and the substations counted, never drawn.

    python -m unittest tests.test_power_lines
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import power_lines as pl  # noqa: E402

FILE = ROOT / "site" / "data" / "power_lines.geojson"


class Rules(unittest.TestCase):
    def test_the_voltage_is_the_highest_of_the_tag_in_kv(self):
        self.assertEqual(pl.kv_of("230000;115000"), 230)
        self.assertEqual(pl.kv_of("38000"), 38)
        self.assertIsNone(pl.kv_of(""))
        self.assertIsNone(pl.kv_of("unknown"))

    def test_length_in_km(self):
        self.assertAlmostEqual(pl.km_of([(-66.0, 18.0), (-66.0, 18.1)]), 11.12, places=1)


class File(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))

    def test_only_voltage_and_length_no_name_operator_or_circuit(self):
        for f in self.d["features"]:
            self.assertLessEqual(set(f["properties"]), {"kv", "km", "cable"})
            self.assertIn(f["properties"]["kv"], pl.KV)
            self.assertEqual(f["geometry"]["type"], "MultiLineString")

    def test_no_substation_or_tower_is_drawn(self):
        self.assertTrue(all(f["geometry"]["type"] == "MultiLineString" for f in self.d["features"]))
        n = self.d["notes"]
        self.assertEqual(n["substations"], sum(n["substations_by_class"].values()))
        self.assertLessEqual(sum(n["substations_by_municipio"].values()), n["substations"])

    def test_simplified_and_inside_puerto_rico(self):
        n = self.d["notes"]
        self.assertEqual(n["simplified_deg"], pl.TOL)
        km = sum(n["km_by_kv"].values())
        self.assertLess(n["points"] / km, 5, "about 100 m simplification leaves a point every few hundred meters")
        s, w, nn, e = pl.BBOX
        for f in self.d["features"]:
            for line in f["geometry"]["coordinates"]:
                for lon, lat in line:
                    self.assertTrue(w <= lon <= e and s <= lat <= nn)

    def test_the_backbone_is_there(self):
        for kv, floor in pl.FLOOR_KM.items():
            self.assertGreaterEqual(self.d["notes"]["km_by_kv"][str(kv)], floor)


if __name__ == "__main__":
    unittest.main()
