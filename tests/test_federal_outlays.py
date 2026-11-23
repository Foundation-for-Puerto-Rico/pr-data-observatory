"""Federal grants and contracts obligated and paid out (spending_outlays.json, federal_outlays.py, HANDOFF decision 96, step 2): only awards signed from
fiscal year 2020 are read (USAspending's outlays start then), FEMA Public Assistance is left out and kept apart, paid out never passes obligated in any
row (each award is capped; the excess is counted), and the rows add up to the totals. The rebuild from the cache is compared with the published file
when the cache is present."""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import federal_outlays as O  # noqa: E402
import spending  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_outlays.json"


class Rules(unittest.TestCase):
    def test_outlays_era_and_groups(self):
        self.assertEqual(O.FIRST_YEAR, 2020)
        self.assertEqual(set(O.GROUPS), {"grants", "contracts"})
        self.assertIn("97.036", O.EXCLUDE)

    def test_contract_agencies_have_a_crosswalk_default(self):
        cw = spending.load_crosswalk()
        for name, pre in O.AGENCY.items():
            self.assertIn(("cfda_agency", pre), cw, name)

    def test_classify(self):
        cw = spending.load_crosswalk()
        self.assertEqual(O.classify("grants", "84.010", cw)[0], "education")
        self.assertEqual(O.classify("contracts", "Department of Defense", cw)[2], "12")
        self.assertEqual(O.classify("contracts", "No Such Agency", cw)[:2], ("other", "low"))


@unittest.skipUnless(OUT.exists(), "spending_outlays.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_shape(self):
        d = self.d
        self.assertEqual(d["years"][0], 2020)
        self.assertEqual(d["years"], list(range(d["years"][0], d["years"][-1] + 1)))
        self.assertEqual(d["year_is"], "signed")
        for r in d["rows"]:
            self.assertEqual(len(r[5]), len(d["years"]))
            self.assertEqual(len(r[6]), len(d["years"]))

    def test_paid_never_passes_obligated(self):
        for r in self.d["rows"]:
            for o, p in zip(r[5], r[6]):
                self.assertLessEqual(p, o + 1, r[0])
                self.assertGreaterEqual(p, 0, r[0])

    def test_rows_add_up_to_the_totals(self):
        d = self.d
        for gi, g in enumerate(d["groups"]):
            for yi in range(len(d["years"])):
                for k, col in (("obligated", 5), ("paid", 6)):
                    s = sum(r[col][yi] for r in d["rows"] if r[2] == gi)
                    self.assertLessEqual(abs(s - d["totals"][g][k][yi]), len(d["rows"]), (g, k, d["years"][yi]))

    def test_fema_public_assistance_is_kept_apart(self):
        self.assertFalse(any(r[0] == "97.036" for r in self.d["rows"]))
        self.assertIn("97.036", self.d["excluded"])

    @unittest.skipUnless((O.CACHE / f"{O.FIRST_YEAR}_grants.json").exists(), "no USAspending cache")
    def test_the_cache_rebuilds_the_published_file(self):
        self.assertTrue(O.build(check=True, today=date(self.d["years"][-1] + 1, 1, 1)))


if __name__ == "__main__":
    unittest.main()
