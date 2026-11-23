"""Where each Commonwealth budget line takes its function (spending.ogp_basis, spending_state.json "basis", HANDOFF decision 109, step 4): the basis
follows ogp_function's order (a line by agency default has its agency's function), each column's bases add up to the column's total, and the
agencies listed add up to the latest approved budget."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import spending  # noqa: E402

OUT = ROOT / "site" / "data" / "spending_state.json"


class Basis(unittest.TestCase):
    def setUp(self):
        self.cw = spending.load_crosswalk()

    def test_a_program_row_wins_over_the_agency(self):
        self.assertEqual(spending.ogp_basis("045", "1224", cw=self.cw), "program")
        self.assertEqual(spending.ogp_function("045", "1224", cw=self.cw)[0], "health")

    def test_an_agency_default_line_has_its_agency_function(self):
        agencies = [k[1] for k in self.cw if k[0] == "ogp_agency"]
        for a in agencies[:40]:
            self.assertEqual(spending.ogp_basis(a, cw=self.cw), "agency", a)
            self.assertEqual(spending.ogp_function(a, cw=self.cw)[0], self.cw[("ogp_agency", a)]["function_category"], a)


@unittest.skipUnless(OUT.exists(), "spending_state.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_bases_add_up_to_each_column(self):
        d = self.d
        self.assertEqual(d["basis"]["kinds"], spending.BASES)
        for c, v in zip(d["columns"], d["basis"]["by_column"]):
            self.assertLessEqual(abs(sum(v) - c["total"]), 10, (c["year"], c["stage"]))

    def test_agencies_add_up_to_the_latest_approved_budget(self):
        d = self.d
        c = d["columns"][d["basis"]["column"]]
        self.assertEqual(c["stage"], "approved")
        self.assertEqual(c["year"], max(x["year"] for x in d["columns"] if x["stage"] == "approved"))
        self.assertLessEqual(abs(sum(a[1] for a in d["basis"]["agencies"]) - c["total"]), len(d["basis"]["agencies"]))
        for a in d["basis"]["agencies"]:
            self.assertLessEqual(a[2], a[1] + 1, a[0])


if __name__ == "__main__":
    unittest.main()
