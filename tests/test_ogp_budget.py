"""The Commonwealth budget file (spending_state.json, ogp_budget.py, HANDOFF decision 77): each column adds up to OGP's own stated total, the rows index
the schema's lists, nothing is placed in a municipio, and the sheet reader picks the right year and stage from OGP's headers. The rebuild from the cached
data sheets is compared with the published file when the cache is present (it is not on the CI runner)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ogp_budget as O  # noqa: E402
import spending as S  # noqa: E402

DATA = ROOT / "site" / "data"


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "spending_state.json").read_text(encoding="utf-8"))

    def test_every_column_adds_up_to_ogp_total(self):
        for i, c in enumerate(self.d["columns"]):
            got = sum(r[4][i] for r in self.d["rows"])
            self.assertEqual(got, c["total"], c)
            self.assertLessEqual(abs(got - c["stated_total"]), O.TOLERANCE * c["stated_total"], c)

    def test_one_column_per_year_and_stage_and_only_schema_stages(self):
        keys = [(c["year"], c["stage"]) for c in self.d["columns"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue({s for _, s in keys} <= {"actual", "approved", "proposed"})
        self.assertEqual(sorted({y for y, _ in keys}), self.d["years"])

    def test_rows_index_the_lists(self):
        self.assertEqual(self.d["concepts"], S.CONCEPTS)
        self.assertEqual(self.d["functions"], S.FUNCTIONS)
        n = len(self.d["columns"])
        for a, f, c, fn, v in self.d["rows"]:
            self.assertIn(a, self.d["agencies"])
            self.assertTrue(0 <= f < len(self.d["funds"]) and 0 <= c < len(S.CONCEPTS) and 0 <= fn < len(S.FUNCTIONS))
            self.assertEqual(len(v), n)
            self.assertTrue(all(isinstance(x, int) for x in v))

    def test_no_row_repeats_a_combination(self):
        keys = [tuple(r[:4]) for r in self.d["rows"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_state_level_and_pr_fiscal_year(self):
        self.assertEqual((self.d["level"], self.d["fiscal_year_basis"], self.d["unit"]), ("state", "pr_jul_jun", "USD"))
        self.assertNotIn("municipio", json.dumps(self.d["rows"]))

    def test_debt_and_pensions_are_never_another_function(self):
        di = S.CONCEPTS.index("debt_service")
        for r in self.d["rows"]:
            if r[2] == di:
                self.assertEqual(S.FUNCTIONS[r[3]], "debt_pensions", r)

    def test_no_privileged_sheet_is_used(self):
        self.assertFalse(any("rev-3-17" in c["sheet"] for c in self.d["columns"]))


class SheetHeaders(unittest.TestCase):
    """OGP's headers, as the five sheets of 2025-2026 write them."""
    def labels(self, head, total=None):
        rows = [[None] * 16 for _ in range(6)]
        for k, line in enumerate(head):
            for j, v in enumerate(line):
                rows[k][5 + j] = v
        rows[1][0] = "Agencia"
        if total:
            rows[2 + len(head) - 1][0] = "TOTAL:"
            for j, v in enumerate(total):
                rows[2 + len(head) - 1][5 + j] = v
        return {j - 5: v for j, v in O.column_labels(rows, 1).items()}

    def test_year_from_fy_or_the_latest_year_named(self):
        got = self.labels([[None, None, None], ["Gastado", "Aprobado", "Propuesto"], ["2024", "FY25", "March 3, 2025 2026 Versión 1"]])
        self.assertEqual([(y, s) for y, s, _ in got.values()], [(2024, "actual"), (2025, "approved"), (2026, "proposed")])

    def test_requests_and_baselines_have_no_stage(self):
        got = self.labels([[None, None], ["Solicitado", "Baseline"], ["FY26", "2026 2.4.2025"]])
        self.assertEqual([s for _, s, _ in got.values()], [None, None])


@unittest.skipUnless((O.CACHE / "index.json").exists(), "the OGP data sheets are not cached here")
class RebuildFromCache(unittest.TestCase):
    def test_the_published_file_is_what_the_cache_gives(self):
        self.assertTrue(O.build(check=True), "run python ogp_budget.py")


if __name__ == "__main__":
    unittest.main()
