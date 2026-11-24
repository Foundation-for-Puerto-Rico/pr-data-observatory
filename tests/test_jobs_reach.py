"""Tests for jobs_reach.py (jobs within 30 and 45 minutes by car; decision 107, step 9, fifth part)."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import jobs_reach as J  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Spread(unittest.TestCase):
    def test_each_municipio_keeps_its_jobs(self):
        w = J.spread({"a": 100, "b": 30}, np.array(["a", "a", "b", "a"]))
        self.assertEqual(w.tolist(), [100 / 3, 100 / 3, 30, 100 / 3])
        w = J.spread({"a": 90}, np.array(["a", "a"]), [2, 1])
        self.assertEqual(w.tolist(), [60, 30])

    def test_by_node_sums_points_on_the_same_node(self):
        n, w = J.by_node(np.array([5, 3, 5]), [1.0, 2.0, 4.0])
        self.assertEqual((n.tolist(), w.tolist()), ([3, 5], [2.0, 5.0]))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not J.OUT.exists():
            raise unittest.SkipTest("jobs_reach_series.json not built")
        cls.d = json.loads(J.OUT.read_text(encoding="utf-8"))
        y = str(cls.d["years"][0])
        cls.V = {v["key"]: v["years"][y] for v in cls.d["vars"]}

    def test_shape(self):
        self.assertEqual(len(self.d["geo"]["ids"]), 79)
        self.assertEqual(self.d["geo"]["ids"][-1], "72")
        for v in self.d["vars"]:
            self.assertTrue(v["estimate"])
            self.assertIn("estimate", v["label"])

    def test_45_minutes_reach_at_least_as_far_as_30_and_shares_agree(self):
        tot = self.d["notes"]["jobs_total"]
        for i in range(79):
            a, b = self.V["jobs_reach_30"][i], self.V["jobs_reach_45"][i]
            self.assertLessEqual(a, b)
            self.assertLessEqual(b, tot)
            self.assertAlmostEqual(self.V["jobs_reach_30_pct"][i], round(a / tot * 100, 1), places=6)

    def test_the_islands_reach_their_own_jobs(self):
        e = json.loads((ROOT / "site" / "data" / "economy_series.json").read_text(encoding="utf-8"))
        q = next(v for v in e["vars"] if v["key"] == "qcew_jobs")
        jobs = dict(zip(e["geo"]["ids"], q["years"][str(self.d["notes"]["jobs_year"])]))
        ids = self.d["geo"]["ids"]
        for m in ("72147", "72049"):   # Vieques, Culebra: no road leaves them
            self.assertLessEqual(self.V["jobs_reach_45"][ids.index(m)], jobs[m] + 1)

    def test_the_check_against_the_commuting_flows(self):
        c = self.d["notes"]["check"]
        self.assertGreater(c["within_45_min_pct"], 90)
        self.assertGreater(c["between_within_45_min_pct"], 85)
        r = self.d["notes"]["range"]["30_min"]
        self.assertLess(abs(r["jobs_over_residents"] / r["central"] - 1), 0.15)


if __name__ == "__main__":
    unittest.main()
