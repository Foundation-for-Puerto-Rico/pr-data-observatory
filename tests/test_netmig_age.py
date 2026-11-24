"""Tests for netmig_age.py (net migration by age, 2010-2020, by the residual method; decision 107, step 9, sixth part)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import netmig_age as M  # noqa: E402


class Residual(unittest.TestCase):
    def setUp(self):
        self.S = {s: [0.9] * 15 + [0.5] for s in ("m", "f")}   # 90% of each group survives ten years; half of the open group

    def test_no_migration_gives_zero(self):
        p10 = {s: [100] * 18 for s in ("m", "f")}
        p20 = {s: [0, 0] + [90] * 15 + [0] for s in ("m", "f")}
        p20 = {s: p20[s][:17] + [0.5 * 300] for s in ("m", "f")}   # 75-79, 80-84 and 85+ of 2010 (300 people) reach 85+: half survive
        nm, ex = M.residual(p10, p20, self.S)
        self.assertTrue(all(abs(x) < 1e-9 for x in nm[2:]))
        self.assertAlmostEqual(ex[2], 180.0)   # 90 survivors of each sex

    def test_departures_show_as_a_loss_in_the_right_group(self):
        p10 = {s: [100] * 18 for s in ("m", "f")}
        p20 = {s: [0, 0] + [90] * 15 + [150] for s in ("m", "f")}
        p20["f"][6] -= 30   # 30 women aged 30-34 in 2020 (20-24 in 2010) left
        nm, _ = M.residual(p10, p20, self.S)
        self.assertAlmostEqual(nm[6], -30)
        b = M.broad(nm, [1] * 18)
        self.assertAlmostEqual(b["30_44"][0], -30)
        self.assertAlmostEqual(b["10_plus"][0], -30)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not M.OUT.exists():
            raise unittest.SkipTest("netmig_age_series.json not built")
        cls.d = json.loads(M.OUT.read_text(encoding="utf-8"))
        cls.V = {v["key"]: v["years"]["2020"] for v in cls.d["vars"]}

    def test_shape(self):
        self.assertEqual(len(self.d["geo"]["ids"]), 79)
        self.assertEqual(len(self.d["vars"]), 7)
        for v in self.d["vars"]:
            self.assertTrue(v["estimate"])

    def test_the_municipios_add_up_to_the_island(self):
        self.assertAlmostEqual(sum(self.V["netmig_10_plus"][:78]), self.V["netmig_10_plus"][-1], delta=78)

    def test_the_check_against_the_demographic_balance(self):
        c = self.d["notes"]["check"]
        self.assertLess(abs(c["residual_vs_balance_pct"]), 10)
        self.assertEqual(c["census_2010"], 3725789)
        r = self.d["notes"]["range"]["10_plus_net_migration"]
        self.assertTrue(r["life_table_2019"] <= r["published"] <= r["life_table_2010"])

    def test_the_young_left_most(self):
        i = self.d["notes"]["island"]
        self.assertLess(i["20_29"]["pct"], i["45_64"]["pct"])
        self.assertLess(i["20_29"]["pct"], i["65_plus"]["pct"])


if __name__ == "__main__":
    unittest.main()
