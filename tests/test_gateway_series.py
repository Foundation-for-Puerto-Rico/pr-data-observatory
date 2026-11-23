"""Tests for gateway_series.py: where each gateway is counted, what is kept, and the published file. No network."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import gateway_series as gw  # noqa: E402

DATA = ROOT / "site" / "data"


class Places(unittest.TestCase):
    def test_every_airport_is_in_transport_json(self):
        m = gw.airport_municipality()
        for code in gw.T100_AIRPORTS + ["RVR"]:
            self.assertIn(code, m)
        self.assertEqual(m["SJU"], "Carolina")   # San Juan's airport is in Carolina, not San Juan
        self.assertEqual(m["SIG"], "San Juan")


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DATA / "gateway_series.json").exists():
            raise unittest.SkipTest("not built")
        cls.d = json.loads((DATA / "gateway_series.json").read_text(encoding="utf-8"))
        cls.V = {v["key"]: v["years"] for v in cls.d["vars"]}
        cls.at = {n: i for i, n in enumerate(cls.d["geo"]["names"])}

    def test_shape_and_island_sums(self):
        self.assertEqual(len(self.d["geo"]["ids"]), 79)
        for k, ys in self.V.items():
            for y, a in ys.items():
                self.assertEqual(len(a), 79, k)
                self.assertEqual(a[-1], sum(a[:78]), f"{k} {y}")

    def test_no_point_or_name(self):
        t = (DATA / "gateway_series.json").read_text(encoding="utf-8")
        self.assertNotRegex(t, r"-6[5-7]\.\d{4,}")
        self.assertNotIn("Terminal", t)

    def test_known_figures(self):
        a = self.V["air_passengers"]["2025"]
        self.assertEqual(a[self.at["Carolina"]], 6687309)   # T-100, SJU, 2025 (checked 2026-10-05)
        self.assertEqual(self.V["air_enplanements_faa"]["2025"][self.at["Carolina"]], 6658037)   # FAA CY2025
        self.assertEqual(self.V["air_enplanements_faa"]["2025"][self.at["Ceiba"]], 23214)   # only FAA has Ceiba
        self.assertEqual(a[self.at["Ceiba"]], 0)
        f = self.V["ferry_passengers"]["2024"]
        self.assertEqual(f[self.at["Cataño"]] + f[self.at["San Juan"]], 428604)   # the Cataño crossing, both ways
        self.assertEqual(sorted(self.V["ferry_passengers"]), ["2019", "2022", "2024"])

    def test_faa_and_t100_agree(self):
        for y in set(self.V["air_passengers"]) & set(self.V["air_enplanements_faa"]):
            t, f = self.V["air_passengers"][y][-1], self.V["air_enplanements_faa"][y][-1]
            self.assertLess(abs(t - f) / f, 0.02, y)

    def test_every_variable_has_an_entry_and_spanish(self):
        ids = {e["id"] for e in json.loads((ROOT / "dictionary_src" / "entries" / "infrastructure.json").read_text(encoding="utf-8"))}
        es = json.loads((ROOT / "i18n_src" / "es" / "labels_infrastructure.json").read_text(encoding="utf-8"))
        for v in self.d["vars"]:
            self.assertIn("infrastructure." + v["key"], ids)
            self.assertIn(v["label"], es)
            self.assertIn("Infrastructure · " + v["group"], es)


if __name__ == "__main__":
    unittest.main()
