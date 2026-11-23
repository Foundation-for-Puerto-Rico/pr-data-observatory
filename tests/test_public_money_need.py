"""The Disaster funding and need page (Knowledge Area, Public money v2 step 5; HUD CDBG, decision 100): its data file is current and adds up, and the page keeps the Compliance hold.

public_money_need.json is built only from the published series (public_money_need.py); the page (public-money.html, written by
docs/analysis/public-money-v2-2026-10/make_page.py) states facts, carries no headline figure and keeps the In review marker and noindex
while the Compliance review of the federal-money series is open (HANDOFF decisions 21 and 72).
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import public_money_need as P  # noqa: E402

DATA = ROOT / "site" / "data"
PAGE = ROOT / "site" / "public-money.html"


class DataFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "public_money_need.json").read_text(encoding="utf-8"))

    def test_the_file_matches_a_rebuild_from_the_series(self):
        new = json.loads(json.dumps(P.build()))
        self.assertEqual({k: v for k, v in self.d.items() if k != "built"}, {k: v for k, v in new.items() if k != "built"}, "run python public_money_need.py")

    def test_78_municipios_in_every_column(self):
        d = self.d
        self.assertEqual(len(d["geo"]["ids"]), 78)
        self.assertNotIn("72", d["geo"]["ids"])
        for part in ("money", "need", "hma"):
            for k, col in d[part].items():
                self.assertEqual(len(col), 78, f"{part}.{k}")
        self.assertTrue(all(p > 0 for p in d["population"]))

    def test_placed_money_is_the_sum_of_the_municipios_and_never_more_than_the_island(self):
        d = self.d
        for k, v in d["island"].items():
            self.assertEqual(v["placed"], sum(d["money"][k]), k)
            self.assertLessEqual(v["placed"], v["total"], k)
        h = d["hma_island"]
        self.assertLessEqual(sum(d["hma"]["approved"]), h["approved"])
        self.assertEqual(d["hma"]["approved"], d["money"]["hma"], "the Hazard Mitigation money and its approved column are the same series")

    def test_the_years_are_the_ones_the_page_names(self):
        self.assertEqual((self.d["years"]["first"], self.d["years"]["last"]), (P.FIRST, P.LAST))
        self.assertEqual(self.d["population_year"], 2020)

    def test_no_recipient_is_named(self):
        text = json.dumps(self.d)
        for word in ("applicant", "recipient", "subrecipient", "name\":", "address", "contact"):
            self.assertNotIn(word, text.replace('"names"', ""), word)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding="utf-8")
        cls.d = json.loads((DATA / "public_money_need.json").read_text(encoding="utf-8"))

    def test_the_compliance_hold_is_kept(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("data-ka-note", self.html, "the In review notice box")
        self.assertNotIn("kpi", self.html, "no headline figure (decision 21)")
        knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        self.assertRegex(knowledge, r"id: 'publicmoney',.*page: 'public-money\.html', status: 'published', review: true, ai: true")

    def test_the_figures_in_the_text_come_from_the_data(self):
        i, h = self.d["island"]["pa"], self.d["hma_island"]
        self.assertIn(f"{100 * i['placed'] / i['total']:.0f}% of it is on this map", self.html)
        self.assertIn(f"${h['approved'] / 1e9:.2f} billion", self.html)
        self.assertIn(f"${h['obligated'] / 1e9:.2f} billion", self.html)

    def test_every_string_the_script_asks_for_has_its_spanish(self):
        js = (ROOT / "site" / "js" / "public_money.js").read_text(encoding="utf-8")
        es = json.loads((ROOT / "i18n_src" / "es" / "public_money.json").read_text(encoding="utf-8"))
        asked = set(re.findall(r"\bT\('((?:[^'\\]|\\.)+)'", js)) | {m for pair in re.findall(r"\[\s*'[a-z0-9_]+',\s*'([^']+)'\]", js) for m in [pair]}
        missing = sorted(s for s in asked if s.replace("\\'", "'") not in es)
        self.assertEqual(missing, [])


class Hud(unittest.TestCase):
    """HUD's CDBG money (decision 100): read from the two published CDBG files, placed money never more than the prime grants, never added to FEMA's,
    and every Spanish string that names CDBG or HUD held for Finance and Compliance (decision 21)."""
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "public_money_need.json").read_text(encoding="utf-8"))
        cls.dr = json.loads((DATA / "spending_cdbgdr.json").read_text(encoding="utf-8"))
        cls.cd = json.loads((DATA / "spending_cdbg.json").read_text(encoding="utf-8"))

    def test_the_money_is_the_sum_of_the_cdbg_files(self):
        d, dr, cd = self.d, self.dr, self.cd
        self.assertEqual(d["money"]["cdbg_dr"], [sum(yr[i] for yr in dr["by_muni"]) for i in range(78)])
        self.assertEqual(d["money"]["cdbg"], [sum(yr[i] for yr in cd["entitlement"]) + sum(yr[i] for yr in cd["state_by_muni"]) for i in range(78)])
        self.assertEqual([a + b for a, b in zip(d["cdbg_parts"]["entitlement"], d["cdbg_parts"]["state"])], d["money"]["cdbg"])
        self.assertEqual(d["island"]["cdbg_dr"]["total"], sum(dr["prime"]))
        self.assertEqual(d["island"]["cdbg"]["total"], sum(cd["entitlement_total"]) + sum(cd["state_prime"]))
        self.assertEqual(d["money_years"]["cdbg"], [cd["years"][0], cd["years"][-1]])
        self.assertEqual(d["money_years"]["cdbg_dr"], [dr["years"][0], dr["years"][-1]])

    def test_every_municipio_gets_yearly_cdbg_one_way_or_the_other(self):
        self.assertTrue(all(x > 0 for x in self.d["money"]["cdbg"]))

    def test_hud_money_is_never_added_to_fema(self):
        js = (ROOT / "site" / "js" / "public_money.js").read_text(encoding="utf-8")
        line = re.search(r"function moneyTotal\(k, i\) \{(.*)\}", js).group(1)
        self.assertNotIn("cdbg", line)
        self.assertIn("'The three FEMA programs together'", js)

    def test_spanish_naming_cdbg_or_hud_is_held(self):
        es = json.loads((ROOT / "i18n_src" / "es" / "public_money.json").read_text(encoding="utf-8"))
        held = json.loads((ROOT / "i18n_src" / "held_for_review.json").read_text(encoding="utf-8"))["spanish"].get("public_money", {})
        for k, v in es.items():
            if k != "_about" and re.search(r"CDBG|\bHUD\b", k + " " + v):
                self.assertEqual(v, k, f"{k[:60]!r} names CDBG or HUD: its Spanish waits in held_for_review.json")
                self.assertIn(k, held)
        self.assertGreaterEqual(len(held), 10)

    def test_the_hud_figures_in_the_text_come_from_the_data(self):
        html = PAGE.read_text(encoding="utf-8")
        i, u = self.d["island"], self.d["cdbg_parts"]
        self.assertIn(f"HUD obligated ${i['cdbg_dr']['total'] / 1e9:.2f} billion", html)
        self.assertIn(f"entitlement grants, ${u['entitlement_total'] / 1e6:.0f} million", html)
        self.assertIn('id="hud"', html)


if __name__ == "__main__":
    unittest.main()
