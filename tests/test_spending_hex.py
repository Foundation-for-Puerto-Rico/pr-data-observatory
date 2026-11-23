"""The hex grid of the Public spending page (HANDOFF decision 85): the layout written into site/js/public_spending_charts.js is what
docs/analysis/public-spending-2026-11/make_hex.py makes from the municipio outlines now, so a change to either shows up here, and the layout keeps
the island's shape: west municipios left of east ones, north ones above south ones, Vieques and Culebra at the east end."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "analysis" / "public-spending-2026-11"))
import make_hex as H  # noqa: E402

JS = ROOT / "site" / "js" / "public_spending_charts.js"


def published():
    text = re.search(r"const HEX = '([^']*)';", JS.read_text(encoding="utf-8")).group(1)
    return {"72" + i: (int(qr.split(".")[0]), int(qr.split(".")[1])) for i, qr, _ in (c.split(":") for c in text.split(","))}


class Hex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lay = H.layout()
        cls.pub = published()

    def test_the_script_has_the_layout_make_hex_writes(self):
        self.assertEqual(self.pub, self.lay)

    def test_the_island_keeps_its_shape(self):
        q = lambda m: self.pub[m][0] + (0.5 if self.pub[m][1] % 2 else 0)
        r = lambda m: self.pub[m][1]
        self.assertLess(q("72097"), q("72127"))      # Mayagüez west of San Juan
        self.assertLess(q("72003"), q("72053"))      # Aguada west of Fajardo
        self.assertLess(r("72127"), r("72113"))      # San Juan north of Ponce
        self.assertLess(r("72013"), r("72113"))      # Arecibo north of Ponce
        main_east = max(q(m) for m in self.pub if m not in H.ISLANDS)
        self.assertTrue(all(q(m) > main_east for m in H.ISLANDS))   # Vieques and Culebra east of the main island


if __name__ == "__main__":
    unittest.main()
