"""Disaster recovery subawards by municipio (spending_cdbgdr.json, cdbg_dr.py, HANDOFF decision 89): only the Department of Housing's disaster grants
are read (never the yearly block grants or the COVID grant), and the published file adds up: for each year the municipios plus the subawards that
name no municipio equal the subawards for Puerto Rico, which never pass the prime grants over all the years. The rebuild from the cache is compared
with the published file when the cache is present."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cdbg_dr as C  # noqa: E402
import spending  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_cdbgdr.json"


class Awards(unittest.TestCase):
    def test_only_disaster_grants(self):
        codes = {a.split("-")[2] for a in C.DR_AWARDS}
        self.assertTrue(codes <= {"DM", "DP", "DE", "DF", "DZ", "DN", "DI"}, codes)
        self.assertFalse(any("-DC-" in a or "-DW-" in a for a in C.DR_AWARDS))
        self.assertTrue(all(a.endswith(("-72-0001", "-72-0002")) for a in C.DR_AWARDS), "Puerto Rico grants only")

    def test_dedup_group_exists(self):
        self.assertIn("cdbg_dr", spending.DEDUP_GROUPS)


@unittest.skipUnless(OUT.exists(), "spending_cdbgdr.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_municipios_plus_unplaced_equal_the_subawards(self):
        d = self.d
        for yi, y in enumerate(d["years"]):
            self.assertLessEqual(abs(sum(d["by_muni"][yi]) + d["unplaced"][yi] - d["subawards"][yi]), len(d["geo"]["ids"]) + 1, y)
            self.assertGreaterEqual(d["unplaced"][yi], -len(d["geo"]["ids"]), y)

    def test_grants_are_the_awards_and_paid_never_passes_obligated(self):
        d = self.d
        self.assertEqual([g[0] for g in d["grants"]], d["awards"])
        for a, o, p in d["grants"]:
            self.assertLessEqual(p, o + 1, a)
        self.assertEqual(len(d["grants_read"]), 10)

    def test_subawards_never_pass_the_prime_grants(self):
        self.assertLess(sum(self.d["subawards"]), sum(self.d["prime"]))

    def test_shape_and_one_population_basis(self):
        d = self.d
        pica = json.loads((ROOT / "site" / "data" / "spending_pica.json").read_text(encoding="utf-8"))
        self.assertEqual(d["geo"]["ids"], pica["geo"]["ids"])
        self.assertEqual(d["population"], pica["population"])
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        self.assertTrue(all(len(yr) == len(d["geo"]["ids"]) for yr in d["by_muni"]))
        self.assertEqual(d["awards"], C.DR_AWARDS)

    @unittest.skipUnless((C.CACHE / f"cdbgdr_{C.FIRST_YEAR}.json").exists(), "no USAspending cache")
    def test_the_cache_rebuilds_the_published_file(self):
        self.assertTrue(C.build(check=True, today=date(self.d["years"][-1] + 1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
