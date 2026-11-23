"""Tests for urban_heat.py and the Urban heat page (urban-heat.html; terrain and climate plan, step 3).

  python -m unittest tests.test_urban_heat

The data file matches a rebuild from the published barrio files; it has the 901 barrios in the crosswalk's order in every column; its land values are the
barrio files' values and its people values are the survey's latest window; its rank correlations are what the values give; no person is named. The page keeps
the In review marker, its notice box and noindex, carries no headline figure and combines no measures; the figures in its text come from the data; every
string the page's script asks for has its Spanish.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import urban_heat as U  # noqa: E402

DATA = ROOT / "site" / "data"
PAGE = ROOT / "site" / "urban-heat.html"


class DataFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "urban_heat.json").read_text(encoding="utf-8"))
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.ids = [r[F["id"]] for r in cw["units"]["barrio"]]

    def test_the_file_matches_a_rebuild_from_the_barrio_files(self):
        self.assertEqual(U.main(["--check"]), 0)

    def test_901_barrios_in_every_column(self):
        self.assertEqual(self.d["geo"]["ids"], self.ids)
        for group in ("land", "people", "moe"):
            for k, col in self.d[group].items():
                self.assertEqual(len(col), 901, (group, k))
        self.assertEqual(len(self.d["population"]), 901)
        self.assertEqual(set(self.d["land"]), {"day", "night", "ndvi"})
        self.assertEqual(set(self.d["people"]), {"age65", "pov", "noveh", "alone", "hosp"})

    def test_land_values_are_the_barrio_files_values(self):
        for k, (f, key) in U.LAND.items():
            doc = json.loads((DATA / f).read_text(encoding="utf-8"))
            v = next(x for x in doc["vars"] if x["key"] == key)
            self.assertEqual(self.d["land"][k], next(iter(v["years"].values())), k)

    def test_ranges(self):
        for k, lo, hi in (("day", 15, 60), ("night", 5, 40), ("ndvi", -1, 1)):
            self.assertTrue(all(x is None or lo <= x <= hi for x in self.d["land"][k]), k)
        for k in ("age65", "pov", "noveh", "alone"):
            self.assertTrue(all(x is None or 0 <= x <= 100 for x in self.d["people"][k]), k)

    def test_the_rank_correlations_are_what_the_values_give(self):
        a, b = self.d["land"]["night"], self.d["people"]["age65"]
        pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
        self.assertAlmostEqual(self.d["rho"]["night:age65"]["rho"], U.spearman([p for p, _ in pairs], [q for _, q in pairs]), places=2)
        self.assertEqual(self.d["rho"]["night:age65"]["n"], len(pairs))
        self.assertAlmostEqual(U.spearman([1, 2, 2, 3], [1, 2, 3, 4]), 0.9486832980505138, places=12)   # tied ranks are averaged
        self.assertTrue(all(str(v["rho"]) != "-0.0" for v in self.d["rho"].values()))

    def test_no_person_is_named(self):
        self.assertEqual(set(self.d), {"version", "built", "level", "geo", "population", "population_year", "land", "land_summers", "people", "moe", "acs_window", "rho", "inputs"})


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.d = json.loads((DATA / "urban_heat.json").read_text(encoding="utf-8"))

    def test_the_marker_notice_and_noindex_are_kept(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("data-ka-note", self.html)
        self.assertNotIn("kpi", self.html, "no headline figure")
        knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        self.assertRegex(knowledge, r"id: 'urbanheat',.*page: 'urban-heat\.html', status: 'published', review: true, ai: true")

    def test_no_measure_is_combined_into_a_score(self):
        js = (ROOT / "site" / "js" / "urban_heat.js").read_text(encoding="utf-8")
        code = js.split("*/", 1)[1].lower()
        for word in ("score", "weight", "composite"):
            self.assertNotIn(word, code, word)
        self.assertIn("never combined into one score", self.html)

    def test_the_figures_in_the_text_come_from_the_data(self):
        r = self.d["rho"]
        self.assertIn(f"rank correlation of {r['day:night']['rho']:.2f}", self.html)
        self.assertIn(f"the morning temperature {r['day:ndvi']['rho']:.2f}", self.html)
        self.assertIn(f"5-year estimates {self.d['acs_window']}", self.html)

    def test_the_cooling_section_cites_its_sources_and_names_no_barrio(self):
        sec = self.html.split('id="cooling"', 1)[1].split("</section>", 1)[0]
        r = self.d["rho"]
        self.assertIn(f"have a rank correlation of {r['day:ndvi']['rho']:.2f}", sec)
        for url in ("epa.gov/heatislands/learn-about-heat-islands", "ntrs.nasa.gov/citations/20050215322", "doi.org/10.1016/j.uclim.2026.103086",
                    "epa.gov/heatislands/using-cool-roofs-reduce-heat-islands", "wedocs.unep.org/handle/20.500.11822/37313"):
            self.assertIn(url, sec)
        names = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(names["fields"])}
        barrios = {r[F["name_es"]] for r in names["units"]["barrio"]} - {"San Juan"}
        text = re.sub(r"<[^>]+>", " ", sec)
        self.assertEqual([b for b in barrios if re.search(r"" + re.escape(b) + r"", text)], [])

    def test_every_string_the_script_asks_for_has_its_spanish(self):
        js = (ROOT / "site" / "js" / "urban_heat.js").read_text(encoding="utf-8")
        es = json.loads((ROOT / "i18n_src" / "es" / "urban_heat.json").read_text(encoding="utf-8"))
        asked = set(re.findall(r"\bT\('((?:[^'\\]|\\.)+)'", js)) | set(re.findall(r"\[\s*'[a-z0-9]+',\s*'([A-Z][^']*)'(?:,|\])", js))
        missing = sorted(s for s in asked if s.replace("\\'", "'") not in es)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
