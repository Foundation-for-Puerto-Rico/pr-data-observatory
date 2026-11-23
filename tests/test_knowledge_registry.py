"""The Knowledge registry (knowledge_src/items.json, knowledge.py; docs/knowledge-plan-2026-11.md, HANDOFF decision 90)."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import knowledge  # noqa: E402

REG = knowledge.load_json(knowledge.SRC)
DOMAINS = knowledge.load_json(ROOT / "dictionary_src" / "domains.json")
DOMAINS = DOMAINS.get("domains", DOMAINS)
DATASETS = knowledge.load_json(ROOT / "dictionary_src" / "datasets.json")["datasets"]
DOM_IDS, DS_IDS = {d["id"] for d in DOMAINS}, {d["id"] for d in DATASETS}


def probs(reg):
    return knowledge.problems(reg, DOM_IDS, DS_IDS)


class Registry(unittest.TestCase):
    def test_sound_and_written(self):
        self.assertEqual(probs(REG), [])
        self.assertEqual(knowledge.main(["--check"]), 0, "run python knowledge.py: a file made from the registry is out of date")

    def test_core_list_matches_registry(self):
        txt = knowledge.CORE.read_text(encoding="utf-8")
        for it in REG["items"]:
            needle = f"id: '{it['id']}'"
            self.assertEqual(needle in txt, it["audience"] == "public", it["id"])

    def test_home_page_items(self):
        js = knowledge.ITEMS_JS.read_text(encoding="utf-8")
        data = json.loads(js[js.index("{"):js.rindex("}") + 1])
        want = [it["id"] for it in REG["items"] if it["audience"] == "public" and it["status"] == "published"]
        self.assertEqual([it["id"] for it in data["items"]], want)
        self.assertNotIn("audience", json.dumps(data["items"]))
        for it in data["items"]:
            self.assertIn(it["domains"][0].split(".")[0], {d["id"] for d in data["domains"]}, it["id"])
            for d in it["datasets"]:
                self.assertIn(d, data["datasets"], f"{it['id']}: {d} has a title for the search")

    def test_rules_catch_mistakes(self):
        cases = {
            "domain": lambda it: it["domains"].append("nowhere"),
            "dataset": lambda it: it["datasets"].append("no_such_file"),
            "related": lambda it: it["related"].append(it["id"]),
            "kind": lambda it: it.__setitem__("kind", "essay"),
            "audience": lambda it: it.__setitem__("audience", "friends"),
            "updated": lambda it: it.__setitem__("updated", "2026-13"),
            "cite": lambda it: it.__setitem__("cite", "sources"),
            "summary": lambda it: it["summary"].pop("es"),
            "reviewer": lambda it: it.__setitem__("reviewer", ["auditors"]),
            "review": lambda it: (it.__setitem__("status", "in_review"), it.__setitem__("review", True)),
        }
        for name, change in cases.items():
            reg = copy.deepcopy(REG)
            change(reg["items"][0])
            self.assertTrue(probs(reg), f"a broken {name} must be reported")

    def test_internal_item_never_reaches_site(self):
        reg = copy.deepcopy(REG)
        secret = copy.deepcopy(reg["items"][0])
        secret.update(id="secretdraft", audience="internal", page="secret-draft.html")
        reg["items"].append(secret)
        self.assertEqual(probs(reg), [], "an internal item needs no page in site/")
        core = knowledge.core_text(knowledge.CORE.read_text(encoding="utf-8"), reg["items"], reg, DOMAINS, DATASETS)
        items = knowledge.items_text(reg, DOMAINS, DATASETS)
        for txt in (core, items):
            self.assertNotIn("secretdraft", txt)
            self.assertNotIn("secret-draft.html", txt)
        reg["items"][1]["related"] = ["secretdraft"]
        self.assertTrue(any("internal" in p for p in probs(reg)), "a public item cannot link to an internal one")

    def test_no_internal_item_in_site_files(self):
        internal = [it for it in REG["items"] if it["audience"] == "internal"]
        site_text = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "site").rglob("*") if p.suffix in (".html", ".js", ".json"))
        for it in internal:
            self.assertNotIn(it["page"], site_text, it["id"])


if __name__ == "__main__":
    unittest.main()
