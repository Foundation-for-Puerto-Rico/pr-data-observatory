"""Tests for transit_reach.py: the class of each barrio by the transit inside it (transit-reach.html).

  python -m unittest tests.test_transit_reach

The published file must be what the files in site/data give for its date; the classes cover the 901 barrios once; the residents add up to the 2020
Census total of the exposure series and the municipios to Puerto Rico; and the `passes` flag is only set on barrios without a current stop.
"""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import transit_reach  # noqa: E402

DATA = ROOT / "site" / "data"


class Classify(unittest.TestCase):
    def test_current_stop_wins(self):
        self.assertEqual(transit_reach.classify(1, 3, 2, 1), 3)

    def test_other_service_without_current_stop(self):
        for args in ((0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)):
            self.assertEqual(transit_reach.classify(*args), 2)

    def test_nothing(self):
        self.assertEqual(transit_reach.classify(0, 0, 0, 0), 1)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads((DATA / transit_reach.OUT).read_text(encoding="utf-8"))
        cls.doc = transit_reach.build(as_of=date.fromisoformat(cls.old["as_of"]))

    def test_file_is_what_the_inputs_give(self):
        self.assertEqual(transit_reach.dump(self.doc), (DATA / transit_reach.OUT).read_text(encoding="utf-8"))

    def test_classes_cover_every_barrio_once(self):
        p, rows = self.doc["pr"], self.doc["barrios"]
        self.assertEqual(len(rows), 901)
        self.assertEqual(len({r[0] for r in rows}), 901)
        self.assertEqual(p["b3"] + p["b2"] + p["b1"], 901)

    def test_residents_add_up(self):
        p = self.doc["pr"]
        exp = json.loads((DATA / "exposure_barrio.json").read_text(encoding="utf-8"))
        self.assertEqual(p["p3"] + p["p2"] + p["p1"], sum(exp["total"]["pop"]))
        f = self.doc["muni_fields"]
        munis = [dict(zip(f, m)) for m in self.doc["municipios"]]
        self.assertEqual(len(munis), 78)
        self.assertEqual(sum(m["pop"] for m in munis), p["pop"])
        self.assertEqual(sum(m["b3"] for m in munis), p["b3"])

    def test_passes_only_without_a_current_stop(self):
        f = self.doc["barrio_fields"]
        for r in self.doc["barrios"]:
            b = dict(zip(f, r))
            if b["passes"]:
                self.assertLess(b["cls"], 3, b["geoid"])
            self.assertEqual(b["cls"] == 3, b["cur"] > 0, b["geoid"])


if __name__ == "__main__":
    unittest.main()
