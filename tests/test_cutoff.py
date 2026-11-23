"""Tests for cutoff.py (residents cut off from every hospital when flooded roads or bridges in poor condition close; decision 107, step 9, third part).

The reachability rules run on a small made-up road graph; the published files are checked for their shape, their identities and the WCRP check.
"""
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cutoff as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Line:
    """A road graph of three edges in a row, 0-1-2-3, each 100 m, with the parts of roads.Roads that cutoff.py reads."""

    def __init__(self):
        self.n_nodes, self.n_edges = 4, 3
        self.eu, self.ev = np.array([0, 1, 2]), np.array([1, 2, 3])
        self.cum = [[0.0, 100.0]] * 3


def at(edge, along):
    return {"edge": edge, "along": along}


class Reach(unittest.TestCase):
    def setUp(self):
        self.R = Line()
        self.hosp = [at(2, 90.0)]   # a hospital near node 3

    def test_nothing_closed_everyone_reaches_the_hospital(self):
        cut, wet = C.cut_off(self.R, [at(0, 10.0), at(1, 50.0)], self.hosp, {})
        self.assertEqual(cut.tolist(), [False, False])
        self.assertEqual(wet.tolist(), [False, False])

    def test_a_flooded_stretch_cuts_off_the_far_side_only(self):
        closed = {1: [50.0]}   # the middle edge floods at its middle
        cut, wet = C.cut_off(self.R, [at(0, 10.0), at(1, 20.0), at(1, 80.0)], self.hosp, closed)
        self.assertEqual(cut.tolist(), [True, True, False])   # 20 m along: before the water, on the far side; 80 m: past it, on the hospital's side
        self.assertEqual(wet.tolist(), [False, False, False])

    def test_a_home_on_the_flooded_stretch_is_cut_off_and_wet(self):
        cut, wet = C.cut_off(self.R, [at(1, 55.0)], self.hosp, {1: [50.0]})
        self.assertEqual((bool(cut[0]), bool(wet[0])), (True, True))

    def test_a_block_with_no_road_is_never_counted(self):
        cut, wet = C.cut_off(self.R, [None], self.hosp, {1: [50.0]})
        self.assertEqual((bool(cut[0]), bool(wet[0])), (False, False))

    def test_a_hospital_on_a_flooded_stretch_is_reached_from_its_dry_side(self):
        cut, _ = C.cut_off(self.R, [at(0, 10.0)], [at(1, 30.0)], {1: [60.0]})
        self.assertFalse(cut[0])
        cut, _ = C.cut_off(self.R, [at(0, 10.0)], [at(1, 70.0)], {1: [60.0]})
        self.assertTrue(cut[0])


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not C.OUT_SERIES.exists():
            raise unittest.SkipTest("cutoff_series.json not built")
        cls.d = json.loads(C.OUT_SERIES.read_text(encoding="utf-8"))
        cls.b = json.loads(C.OUT_BARRIO.read_text(encoding="utf-8"))
        cls.V = {v["key"]: v["years"][str(cls.d["years"][0])] for v in cls.d["vars"]}

    def test_shape(self):
        self.assertEqual(len(self.d["geo"]["ids"]), 79)
        self.assertEqual(self.d["geo"]["ids"][-1], "72")
        for v in self.d["vars"]:
            self.assertTrue(v["estimate"])
            self.assertIn("estimate", v["label"])
        for v in self.b["vars"]:
            self.assertEqual(len(next(iter(v["years"].values()))), len(self.b["geo"]["ids"]))

    def test_shares_add_up(self):
        V = self.V
        for i in range(79):
            a = V["cut_flood_pct"][i]
            if a is None:
                continue
            self.assertTrue(0 <= V["cut_flood_dry_pct"][i] <= a + 1e-9)
            self.assertGreaterEqual(V["cut_both_pct"][i], max(a, V["cut_bridge_pct"][i]) - 1e-9)
        n = self.d["notes"]
        self.assertEqual(V["cut_flood_res"][-1], n["island"]["flood"]["residents"])
        self.assertEqual(n["island"]["flood"]["residents"], n["island"]["flood_own_street_closed"]["residents"] + n["island"]["flood_dry_street"]["residents"])

    def test_the_range_holds_the_published_figure(self):
        n = self.d["notes"]
        self.assertLessEqual(n["range"]["flood_low"]["pct"], n["island"]["flood"]["pct"])
        self.assertLessEqual(n["island"]["flood"]["pct"], n["range"]["flood_high"]["pct"])

    def test_vieques_and_culebra_are_left_out(self):
        names = self.d["geo"]["names"]
        for m in ("Vieques", "Culebra"):
            self.assertIsNone(self.V["cut_flood_pct"][names.index(m)])
        self.assertEqual(set(self.d["notes"]["left_out"]["by_municipio"]), {"72147", "72049"})

    def test_the_wcrp_check_separates_the_communities_whose_plans_say_cut_off(self):
        c = self.d["notes"]["check"]
        self.assertEqual(len(c["plans_say_cut_off"]), len(C.WCRP_SAY_CUT_OFF))
        self.assertGreater(c["plans_say_cut_off_mean_pct"], 1.5 * c["other_communities_mean_pct"])
        self.assertGreaterEqual(c["plans_say_cut_off_at_least_half"], 5)

    def test_the_flooded_streets_are_about_the_flood_area(self):
        """The residents whose own street floods are fewer than those in the flood area (some live off it, some on raised roads), and not far fewer."""
        hx = json.loads((ROOT / "site" / "data" / "hex_grid.geojson").read_text(encoding="utf-8"))["notes"]["residents_in_flood_area"]
        wet = self.d["notes"]["island"]["flood_own_street_closed"]["residents"]
        self.assertTrue(0.6 * hx < wet < hx, (wet, hx))


if __name__ == "__main__":
    unittest.main()
