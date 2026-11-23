"""The numbers that dictionary entries quote about site/data/wanted.json (how many rows, and how many per status) are the file's.

The wanted-data list is edited by hand and its status counts move whenever a dataset is built or blocked; the dictionary entries that describe it quote the counts of a given date.
Without this test they went stale twice in the review of pull request 3 (84 rows quoted for a file of 101).

  python -m unittest tests.test_dictionary_numbers
"""
import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
STATUSES = ["candidate", "checked", "building", "live", "blocked"]


def entries():
    out = {}
    for f in (ROOT / "dictionary_src" / "entries").glob("*.json"):
        for e in json.loads(f.read_text(encoding="utf-8")):
            out[e["id"]] = e
    return out


class WantedNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        w = json.loads((DATA / "wanted.json").read_text(encoding="utf-8"))
        cls.rows = len(w["items"])
        cls.counts = Counter(i["status"] for i in w["items"])
        cls.entries = entries()

    def test_the_status_entry_quotes_the_count_of_each_status(self):
        e = self.entries["data.wanted_status"]
        for s in STATUSES:
            m = re.search(rf"(\d+)(?: rows are| are| is)? '{s}'", e["plain"])
            self.assertIsNotNone(m, f"plain does not give the count of '{s}'")
            self.assertEqual(int(m.group(1)), self.counts[s], f"plain: '{s}'")
            m = re.search(rf"\b{s} (\d+)\b", e["how_to_read"])
            self.assertIsNotNone(m, f"how_to_read does not give the count of '{s}'")
            self.assertEqual(int(m.group(1)), self.counts[s], f"how_to_read: '{s}'")
            m = re.search(r"(\d+) rows?\b", e["values"][s])
            self.assertIsNotNone(m, f"values['{s}'] does not give a count")
            self.assertEqual(int(m.group(1)), self.counts[s], f"values: '{s}'")

    def test_the_entries_that_say_how_many_rows_the_list_has_say_the_files_number(self):
        quoted = []
        for k, e in self.entries.items():
            text = json.dumps(e, ensure_ascii=False)
            for m in re.finditer(r"wanted\.json (\d+)\b|(\d+) rows in the file of 2026-\d\d-\d\d", text):
                quoted.append((k, int(m.group(1) or m.group(2))))
        self.assertTrue(quoted, "no entry says how many rows the wanted-data list has: this test looks for the sentence")
        for k, n in quoted:
            self.assertEqual(n, self.rows, f"{k} quotes {n} rows; wanted.json has {self.rows}")


if __name__ == "__main__":
    unittest.main()
