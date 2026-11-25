"""Daytime population and commuting by municipio (commuting.py, HANDOFF decision 107 step 1): the arithmetic on invented flows, and the published file.

    python -m unittest tests.test_commuting

The published file is checked WITHOUT the cache: its areas are the 78 municipios and Puerto Rico in the order of the other series; the municipios' daytime
populations add up to the island's; the daytime population is the 2020 residents plus the published change; the share who work in another municipio is the
figure of transit_links.json; no margin is negative. One test needs the cached flows table (a rebuild gives the file again) and skips without it.
"""
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import commuting  # noqa: E402
import housing_series as hs  # noqa: E402
import transit_links as tl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"


class Arithmetic(unittest.TestCase):
    """Three municipios A, B and C. A: 100 work at home, 50 go to B, 10 leave Puerto Rico. B: 200 at home, 20 go to A. C: 30 at home, 5 go to A. 4 people from outside work in A."""
    INSIDE = {("A", "A"): (100, 10), ("A", "B"): (50, 6), ("B", "B"): (200, 12), ("B", "A"): (20, 8), ("C", "C"): (30, 5), ("C", "A"): (5, 3)}
    AWAY = {"A": [(10, 4)]}
    FROM_OUT = {"A": [(4, 3)]}
    POP = {"A": 1000, "B": 2000, "C": 400}

    def setUp(self):
        self.fig = commuting.figures(self.INSIDE, self.AWAY, self.FROM_OUT, self.POP, ["A", "B", "C"])

    def test_daytime_population_is_residents_plus_workers_in_minus_workers_out(self):
        vals, moes = self.fig["daytime_population"]
        self.assertEqual(vals[0], 1000 + (20 + 5 + 4) - (50 + 10), "A: three flows come in (one from outside Puerto Rico), two leave (one to outside)")
        self.assertEqual(vals[1], 2000 + 50 - 20)
        self.assertEqual(vals[2], 400 + 0 - 5)
        self.assertEqual(moes[0], round(math.sqrt(8 ** 2 + 3 ** 2 + 3 ** 2 + 6 ** 2 + 4 ** 2)), "the margin of a sum is the root of the sum of the squares; the census count adds none")

    def test_the_census_bureaus_formula_gives_the_same_number(self):
        """Residents + workers working in the area - workers living in the area (census.gov, Calculating Commuter-Adjusted Population Estimates)."""
        working_in_a = 100 + 20 + 5 + 4
        living_in_a = 100 + 50 + 10
        self.assertEqual(self.fig["daytime_population"][0][0], 1000 + working_in_a - living_in_a)

    def test_the_municipios_add_up_to_puerto_rico_which_changes_only_at_its_edge(self):
        vals = self.fig["daytime_population"][0]
        self.assertEqual(sum(vals[:3]), vals[3])
        self.assertEqual(vals[3], 3400 + 4 - 10, "inside Puerto Rico every worker who leaves one municipio comes in to another")

    def test_the_change_is_a_percent_of_residents_and_can_be_negative(self):
        vals, moes = self.fig["daytime_change_pct"]
        self.assertEqual(vals[0], round((29 - 60) / 1000 * 100, 2))
        self.assertEqual(vals[1], 1.5)
        self.assertLess(vals[2], 0)
        self.assertEqual(moes[1], round(math.sqrt(6 ** 2 + 8 ** 2) / 2000 * 100, 2))

    def test_work_elsewhere_leaves_out_the_workers_who_work_outside_puerto_rico(self):
        vals, moes = self.fig["work_elsewhere_pct"]
        self.assertEqual((vals[0], moes[0]), hs.pct((50, 6.0), (150, math.sqrt(10 ** 2 + 6 ** 2))), "A: 50 of the 150 who work in Puerto Rico, not of 160")
        self.assertAlmostEqual(vals[3], (50 + 20 + 5) / (100 + 50 + 200 + 20 + 30 + 5) * 100, places=2)

    def test_a_table_of_another_release_stops_the_build(self):
        real = commuting.xlsx_read.rows
        commuting.xlsx_read.rows = lambda data: iter([{0: "Table 1. Residence County to Workplace County Commuting Flows: 5-Year ACS, 2011-2015"}])
        try:
            with self.assertRaises(SystemExit):
                commuting.read_flows(b"")
        finally:
            commuting.xlsx_read.rows = real


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "commuting_series.json").read_text(encoding="utf-8"))
        cls.v = {v["key"]: v for v in cls.doc["vars"]}
        cls.y = str(commuting.YEAR)

    def test_the_areas_are_the_78_municipios_and_puerto_rico_in_the_order_of_the_other_series(self):
        pop = json.loads((DATA / "population_series.json").read_text(encoding="utf-8"))
        self.assertEqual(self.doc["geo"], pop["geo"])
        self.assertEqual([v["key"] for v in self.doc["vars"]], ["daytime_population", "daytime_change_pct", "work_elsewhere_pct"])
        for v in self.doc["vars"]:
            self.assertEqual(list(v["years"]), [self.y])
            self.assertEqual((len(v["years"][self.y]), len(v["moe"][self.y])), (79, 79), v["key"])
            self.assertEqual(v["time"], {"type": "window", "windowYears": 5}, "the flows are a five-year window, labeled by its last year")
            self.assertTrue(all(m is not None and m >= 0 for m in v["moe"][self.y]), v["key"])

    def test_the_municipios_add_up_to_the_island(self):
        vals = self.v["daytime_population"]["years"][self.y]
        self.assertEqual(sum(vals[:78]), vals[78])

    def test_the_daytime_population_is_the_residents_plus_the_change(self):
        pop, _ = commuting.residents()
        ids = self.doc["geo"]["ids"]
        day, ch = self.v["daytime_population"]["years"][self.y], self.v["daytime_change_pct"]["years"][self.y]
        for i, g in enumerate(ids[:78]):
            self.assertEqual(ch[i], round((day[i] - pop[g]) / pop[g] * 100, 2), g)
        self.assertEqual(ch[78], round((day[78] - sum(pop.values())) / sum(pop.values()) * 100, 2))
        self.assertGreater(day[ids.index("72127")], pop["72127"], "San Juan has more people on a working day than residents")

    def test_the_share_who_work_elsewhere_is_the_connections_pages_figure(self):
        t = json.loads((DATA / "transit_links.json").read_text(encoding="utf-8"))
        f = t["muni_fields"]
        page = {m[f.index("geoid")]: m[f.index("work_elsewhere_pct")] for m in t["municipios"]}
        mine = dict(zip(self.doc["geo"]["ids"], self.v["work_elsewhere_pct"]["years"][self.y]))
        for g, p in page.items():
            self.assertAlmostEqual(mine[g], p, delta=0.051, msg=g)   # the page keeps one decimal

    def test_the_sources_are_named_and_the_period_is_the_flows(self):
        self.assertEqual(set(self.doc["sources"]), {"commuting_flows", "census_2020"})
        self.assertIn(tl.FLOWS_PERIOD, self.doc["notes"]["period"])
        self.assertTrue(self.doc["notes"]["kind"].startswith("calculated"))

    @unittest.skipUnless((commuting.tl.CACHE / "commuting_flows_2016_2020.xlsx").exists(), "needs the cached flows table")
    def test_the_cached_table_gives_the_published_file_again(self):
        self.assertEqual(commuting.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
