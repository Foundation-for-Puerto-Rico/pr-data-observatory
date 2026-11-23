"""The ten domains of the navigation plan (docs/navigation-plan-2026-11.md, HANDOFF decision 81), in the registry and in every list that names a home domain.

  python -m unittest tests.test_domains_registry

The registry has the ten data domains in the plan's order, with economy.public-money and environment.hazards kept as aliases; every row of the layer menu
(js/core/layers.js) and every Knowledge Area page (js/core/knowledge.js) names a home domain that exists; the plan's moves hold (heat in Environment and climate,
also in Health and Hazards; WCRP and historic places in Communities; residents in a flood zone in Hazards); no stored reference uses an old id.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dictionary_src"
TEN = ["population", "economy", "public-money", "housing", "health", "education", "environment", "hazards", "infrastructure", "communities"]


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class Registry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load(SRC / "domains.json")
        cls.ids = {d["id"] for d in cls.reg["domains"]}
        cls.entries = {e["id"]: e for f in (SRC / "entries").glob("*.json") for e in load(f)}

    def test_the_ten_data_domains_in_order(self):
        top = [d["id"] for d in sorted(self.reg["domains"], key=lambda d: d["order"]) if d["parent"] is None and not d["system"]]
        self.assertEqual(top, TEN)

    def test_old_ids_are_aliases(self):
        self.assertEqual(self.reg["legacy_names"]["economy.public-money"], "public-money")
        self.assertEqual(self.reg["legacy_names"]["environment.hazards"], "hazards")
        self.assertFalse({"economy.public-money", "environment.hazards"} & self.ids)

    def test_every_layer_row_has_a_home_domain(self):
        src = (ROOT / "site" / "js" / "core" / "layers.js").read_text(encoding="utf-8")
        rows = re.findall(r"\{ id: '(\w+)', (?:domain: (null|'[\w.-]+'), )?(?:also: \[([^\]]*)\], )?", src)
        rows = [r for r in rows if r[0].startswith("ly") or r[0] in ("choro", "walkRings")]
        self.assertGreater(len(rows), 20)
        for rid, dom, also in rows:
            self.assertTrue(dom, f"{rid} has no domain field")
            if dom != "null":
                self.assertIn(dom.strip("'"), self.ids, rid)
            for a in re.findall(r"'([\w.-]+)'", also):
                self.assertIn(a, self.ids, rid)

    def test_every_knowledge_area_has_a_home_domain(self):
        src = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        areas = re.findall(r"^    \{ id: '(\w+)',.*?domain: '([\w.-]+)' \}", src, flags=re.M)
        listed = re.findall(r"^    \{ id: '(\w+)', label:", src, flags=re.M)
        self.assertEqual([a for a, _ in areas], listed)
        for a, d in areas:
            self.assertIn(d, self.ids, a)

    def test_the_plans_moves(self):
        self.assertEqual(self.entries["night_heat.night_lst_med"]["domains"], ["environment", "health", "hazards"])
        self.assertEqual(self.entries["heat.heat_lst_med"]["domain"], "environment")
        self.assertEqual(self.entries["wcrp.rvi_overall_rebuild"]["domain"], "communities")
        self.assertEqual(self.entries["layers.historic_places"]["domain"], "communities")
        self.assertEqual(self.entries["exposure.pop_flood"]["domains"], ["hazards", "population"])
        self.assertIn("health", self.entries["climb.walk_steep_pct"]["domains"])

    def test_no_stored_reference_uses_an_old_id(self):
        old = re.compile(r"(?<![\w.-])(economy\.public-money|environment\.hazards)(?![\w-])")
        for f in [*(SRC / "entries").glob("*.json"), SRC / "datasets.json", SRC / "groups.json", ROOT / "site" / "data" / "wanted.json"]:
            self.assertIsNone(old.search(f.read_text(encoding="utf-8")), f.name)
        for e in self.entries.values():
            for d in e.get("domains", []):
                self.assertIn(d, self.ids, e["id"])


if __name__ == "__main__":
    unittest.main()
