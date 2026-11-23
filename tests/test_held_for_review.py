"""What waits for Finance and Compliance stays held until it is taken out of i18n_src/held_for_review.json (HANDOFF decisions 20 and 21; docs/i18n.md, "Strings held for review").

  python -m unittest tests.test_held_for_review
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "i18n_src"


class HeldForReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.held = json.loads((SRC / "held_for_review.json").read_text(encoding="utf-8"))
        cls.bundles = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "site" / "i18n").glob("es.*.js")))

    def test_a_held_string_shows_its_english_text_on_the_spanish_pages(self):
        for scope, strings in self.held["spanish"].items():
            es = json.loads((SRC / "es" / f"{scope}.json").read_text(encoding="utf-8"))
            for key, spanish in strings.items():
                self.assertNotEqual(spanish, key, f"{scope}: the held translation of {key[:50]!r} is the English text")
                self.assertEqual(es.get(key), key, f"{scope}: {key[:50]!r} is held for review but its Spanish text is back in the scope file")

    def test_no_page_bundle_carries_a_held_translation(self):
        for scope, strings in self.held["spanish"].items():
            for key, spanish in strings.items():
                self.assertNotIn(":" + json.dumps(spanish, ensure_ascii=False), self.bundles, f"{scope}: the held translation of {key[:50]!r} is in a bundle: run python i18n.py")

    def test_the_held_strings_are_the_ones_about_federal_grant_work(self):
        # a safety net, not the definition of what is held (the held file lists that, by what a string belongs to): a Spanish string that mentions HUD, CDBG-DR, LIHTC or WCRP is held or equals its English key
        import re
        pat = re.compile(r"CDBG|LIHTC|WCRP|\bHUD\b", re.I)
        held = {(scope, key) for scope, strings in self.held["spanish"].items() for key in strings}
        held |= {(scope, key) for r in self.held.get("released", []) for scope, keys in r["spanish"].items() for key in keys}   # released on purpose, with who, when and why
        for p in sorted((SRC / "es").glob("*.json")):
            for key, value in json.loads(p.read_text(encoding="utf-8")).items():
                text = " ".join(value) if isinstance(value, list) else value
                if (pat.search(key) or pat.search(text)) and (p.stem, key) not in held:
                    self.assertEqual(text, key, f"{p.stem}: {key[:60]!r} mentions federal grant work and has Spanish text that is not in held_for_review.json: hold it (docs/i18n.md) or record the review")

    def test_a_held_dictionary_summary_shows_english(self):
        import re
        pat = re.compile(r"CDBG|LIHTC|WCRP|\bHUD\b", re.I)
        held = self.held.get("dictionary_plain", {})
        src = json.loads((SRC / "dictionary_plain.json").read_text(encoding="utf-8"))
        built = {e["id"]: e for e in json.loads((ROOT / "site" / "data" / "dictionary.json").read_text(encoding="utf-8"))["entries"]}
        for eid, s in held.items():
            self.assertNotEqual(s["es"], s["en"])
            self.assertNotIn(eid, src, f"{eid}: its Spanish summary is held for review but is back in dictionary_plain.json")
            self.assertNotIn("plain_es", built[eid], f"{eid}: the built dictionary shows a held Spanish summary: run python dictionary.py")
        released = {eid for r in self.held.get("released", []) for eid in r.get("dictionary_plain", [])}
        for eid, s in src.items():   # the same safety net as for the scopes
            if not eid.startswith("_") and eid not in released and (pat.search(s["en"]) or pat.search(s["es"]) or eid.startswith(("economy.fed_", "economy.fema_pa_", "housing.fema_ia_"))):   # the federal money and FEMA summaries wait for Finance and Compliance too (decision 21)
                self.fail(f"{eid}: the Spanish summary mentions federal grant work and is not held: hold it (docs/i18n.md) or record the review")

    def test_a_held_dataset_title_shows_english(self):
        records = {r["id"]: r for r in json.loads((ROOT / "dictionary_src" / "datasets.json").read_text(encoding="utf-8"))["datasets"]}
        for rid, titles in self.held["titles"].items():
            self.assertEqual(records[rid]["title"]["es"], records[rid]["title"]["en"], f"{rid}: the Spanish title is back in datasets.json: release it on purpose (docs/i18n.md) and delete it from held_for_review.json")
            self.assertNotEqual(titles["es"], titles["en"])

    def test_a_held_headline_is_not_in_the_registry(self):
        domains = {d["id"]: d for d in json.loads((ROOT / "dictionary_src" / "domains.json").read_text(encoding="utf-8"))["domains"]}
        for dom, headline in self.held["headlines"].items():
            self.assertIsNone(domains[dom].get("headline"), f"{dom} has a headline again: release it on purpose (docs/i18n.md) and delete it from held_for_review.json")
            self.assertIn("variable", headline)


if __name__ == "__main__":
    unittest.main()
