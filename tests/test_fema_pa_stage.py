"""FEMA Public Assistance by stage and age (spending_fema_pa.json, fema_pa_stage.py, HANDOFF decision 109, step 2): the stage of a process step, the
dollar-weighted median, and the published file adds up (municipios plus Statewide equal Puerto Rico; the age bins hold only open and pending money).
The rebuild from the cache is compared with the published file when the cache is present."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fema_pa_stage as F  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_fema_pa.json"


class Rules(unittest.TestCase):
    def test_stage(self):
        self.assertEqual(F.stage("Project Closed Out"), "closed")
        self.assertEqual(F.stage("Obligated"), "open")
        self.assertEqual(F.stage("Pending EHP Review"), "pending")

    def test_weighted_median(self):
        self.assertEqual(F.wmedian([(1, 10), (9, 1)]), 1)
        self.assertEqual(F.wmedian([(1, 1), (9, 10)]), 9)
        self.assertIsNone(F.wmedian([]))


@unittest.skipUnless(OUT.exists(), "spending_fema_pa.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_municipios_plus_statewide_equal_puerto_rico(self):
        d = self.d
        placed = sum(sum(v) for v in d["by_muni"]["usd"])
        self.assertLessEqual(abs(placed + sum(d["statewide"]["usd"]) - sum(d["island"]["usd"])), len(d["geo"]["ids"]) + 3)
        self.assertEqual(sum(sum(v) for v in d["by_muni"]["count"]) + sum(d["statewide"]["count"]), sum(d["island"]["count"]))

    def test_age_bins_hold_the_open_and_pending_money(self):
        d = self.d
        self.assertLessEqual(abs(sum(d["age_usd"]) - d["island"]["usd"][1] - d["island"]["usd"][2]), 1e6)

    def test_shape(self):
        d = self.d
        self.assertEqual(d["stages"], ["closed", "open", "pending"])
        cd = json.loads((ROOT / "site" / "data" / "spending_cdbgdr.json").read_text(encoding="utf-8"))
        self.assertEqual(d["geo"]["ids"], cd["geo"]["ids"])
        self.assertEqual(d["population"], cd["population"])

    @unittest.skipUnless(F.CACHE.exists(), "no OpenFEMA cache")
    def test_the_cache_rebuilds_the_published_file(self):
        self.assertTrue(F.build(check=True))


if __name__ == "__main__":
    unittest.main()
