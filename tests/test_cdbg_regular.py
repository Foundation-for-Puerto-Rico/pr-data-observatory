"""HUD's yearly CDBG by municipio (spending_cdbg.json, cdbg_regular.py, HANDOFF decision 100): only the yearly grants are read (entitlement grants,
code MC, and the state program, code DC; never the disaster grants or the COVID grants), and the published file adds up: for each year the municipios
plus the state subawards that name no municipio equal the state subawards for Puerto Rico, and the entitlement municipios equal Puerto Rico's
entitlement total. The rebuild from the cache is compared with the published file when the cache is present."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cdbg_regular as C  # noqa: E402
import spending  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_cdbg.json"


class Awards(unittest.TestCase):
    def test_state_grants_are_the_yearly_ones(self):
        a = C.state_awards(2025)
        self.assertEqual(a[0], "B-15-DC-72-0001")
        self.assertEqual(a[-1], "B-26-DC-72-0001")
        self.assertTrue(all("-DC-72-" in x for x in a))

    def test_dedup_group_exists(self):
        self.assertIn("cdbg", spending.DEDUP_GROUPS)


@unittest.skipUnless(OUT.exists(), "spending_cdbg.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_only_yearly_grants(self):
        ent, st = self.d["awards"]["entitlement"], self.d["awards"]["state"]
        self.assertTrue(ent and all("-MC-72-" in a for a in ent), "entitlement grants only (no CDBG-CV, code MW)")
        self.assertTrue(all("-DC-72-" in a for a in st), "state program only (no disaster or COVID grants)")

    def test_municipios_add_up(self):
        d, n = self.d, len(self.d["geo"]["ids"])
        for yi, y in enumerate(d["years"]):
            self.assertLessEqual(abs(sum(d["state_by_muni"][yi]) + d["state_unplaced"][yi] - d["state_subawards"][yi]), n + 1, y)
            self.assertGreaterEqual(d["state_unplaced"][yi], -n, y)
            self.assertLessEqual(abs(sum(d["entitlement"][yi]) - d["entitlement_total"][yi]), n, y)

    def test_shape_and_one_population_basis(self):
        d = self.d
        pica = json.loads((ROOT / "site" / "data" / "spending_pica.json").read_text(encoding="utf-8"))
        self.assertEqual(d["geo"]["ids"], pica["geo"]["ids"])
        self.assertEqual(d["population"], pica["population"])
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        for part in ("entitlement", "state_by_muni"):
            self.assertEqual(len(d[part]), len(d["years"]))
            self.assertTrue(all(len(yr) == len(d["geo"]["ids"]) for yr in d[part]))

    @unittest.skipUnless((C.CACHE / f"cdbg_{C.FIRST_YEAR}.json").exists() and (C.CACHE / "cdbg_entitlement_awards.json").exists(), "no USAspending cache")
    def test_the_cache_rebuilds_the_published_file(self):
        self.assertTrue(C.build(check=True, today=date(self.d["years"][-1] + 1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
