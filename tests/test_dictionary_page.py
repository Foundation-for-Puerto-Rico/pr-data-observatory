"""The files the dictionary page reads (dictionary.py page_files; docs/performance.md): dictionary_list.json first, dictionary_detail_<domain>.json on first use.
tests/dictionary_page.test.js checks that the page's list and search see what they saw in dictionary.json; this checks that the published files are current and counted."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import budget  # noqa: E402
import contract  # noqa: E402
import dictionary  # noqa: E402

DATA = ROOT / "site" / "data"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@unittest.skipUnless((DATA / "dictionary.json").exists(), "run python dictionary.py first")
class PageFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = load(DATA / "dictionary.json")
        cls.files = dictionary.page_files(cls.full)

    def test_the_published_files_are_made_from_the_published_dictionary(self):
        on_disk = sorted(n for n, _ in contract.published_files(DATA) if dictionary.is_page_file(n))
        self.assertEqual(on_disk, sorted(self.files), "run python dictionary.py and commit what it writes")
        for name, content in self.files.items():
            self.assertEqual(load(DATA / name), content, f"{name} is out of date: run python dictionary.py and commit what it writes")

    def test_one_detail_file_for_each_top_level_domain_with_entries(self):
        tops = {e["domain"].split(".")[0] for e in self.full["entries"]}
        self.assertEqual(self.files[dictionary.PAGE_LIST]["detail_files"], sorted(f"dictionary_detail_{t}.json" for t in tops))

    def test_the_budget_counts_them(self):
        r = budget.load_routes()["routes"]["dictionary"]
        self.assertEqual(r["first"], [dictionary.PAGE_LIST], "registry.json loads after the first paint (decision 104, step 4: room for new entries)")
        details = self.files[dictionary.PAGE_LIST]["detail_files"]
        self.assertEqual(r["later"], [dictionary.PAGE_WORDS, dictionary.PAGE_LIST_ES, "registry.json"], "the search words, the Spanish page's own file and the registry, read right after it is ready")
        self.assertEqual(r["on_use"], details + [dictionary.es_detail_file(f) for f in details])
        row = budget.measure("dictionary", r, budget.load_routes()["external"])
        self.assertGreater(row["on_use_kb"], row["data_kb"] / 2, "the detail files hold most of the dictionary")

    def test_the_search_words_hold_no_space_and_no_capital(self):
        words = self.files[dictionary.PAGE_WORDS]["w"]
        for e in self.files[dictionary.PAGE_LIST]["entries"]:
            self.assertNotIn("w", e, e["id"] + ": the long texts' words are in dictionary_words.json")
            for v in (e["wp"], words.get(e["id"], "")):
                self.assertEqual(v, dictionary.js_norm(v), e["id"])
                self.assertEqual(v.split(" "), sorted(set(v.split(" "))) if v else [""], e["id"])

    def test_the_inventory_of_documented_fields_leaves_them_out(self):
        for name in self.files:
            self.assertTrue(dictionary.is_page_file(name), name)
        self.assertFalse(dictionary.is_page_file("dictionary.json"))
        self.assertFalse(dictionary.is_page_file("dictionary_summary.json"))


class SearchWords(unittest.TestCase):
    def test_a_word_inside_a_longer_one_is_left_out_and_accents_go(self):
        self.assertEqual(dictionary.search_words(["Flood floods FLOODING", "Población"]), "flooding floods poblacion")
        self.assertEqual(dictionary.search_words(["the theory"], ["theory"]), "")

    def test_the_first_sentence_ends_at_a_space_after_a_stop(self):
        self.assertEqual(dictionary.first_sentence("Jobs by place. More text."), "Jobs by place.")
        self.assertEqual(dictionary.first_sentence("U.S. jobs. More text."), "U.S.", "as the page always cut it")
        self.assertEqual(dictionary.first_sentence("No stop at all"), "No stop at all")
        self.assertEqual(dictionary.first_sentence(""), "")


if __name__ == "__main__":
    unittest.main()
