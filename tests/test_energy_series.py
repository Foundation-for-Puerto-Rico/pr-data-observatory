"""Energy in Puerto Rico (energy_series.py, HANDOFF decision 104 step 3): the published file's shape and the checks on LUMA's columns.

    python -m unittest tests.test_energy_series
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import energy_series as es  # noqa: E402

FILE = ROOT / "site" / "data" / "energy.json"


class Rules(unittest.TestCase):
    def test_excel_months(self):
        self.assertEqual(es.month_of("40179"), "2010-01")
        self.assertEqual(es.month_of(46266), "2026-09")

    def test_newest_filing_by_name(self):
        self.assertGreater(es.metrics_key("https://energia.pr.gov/x/Resumen-Metricas-Master_October2026.xlsx"),
                           es.metrics_key("https://energia.pr.gov/x/20260821-MI20190007-Exhibit-1-Resumen-Metricas-Master-August-2026.xlsx"))
        self.assertGreater(es.dg_key("/20260814-MI20190016-Exhibit-2-Distributed-Generation-Data-April-to-June-2026.xlsx"),
                           es.dg_key("/20260521-MI20190016-Exhibit-2-Distributed-Generation-Data-January-to-March-2026.xlsx"))


class File(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(FILE.read_text(encoding="utf-8"))

    def test_series_line_up(self):
        s = self.d["series"]
        n = len(s["months"])
        self.assertEqual(s["months"][0], "2010-01")
        for k in ("rps_pct", "rooftop_customers", "rooftop_mw", "exported_gwh"):
            self.assertEqual(len(s[k]), n, k)
        for k in es.FUELS:
            self.assertEqual(len(s["gen_gwh"][k]), n, k)

    def test_no_customer_or_address(self):
        text = FILE.read_text(encoding="utf-8").lower()
        for word in ("address", "direcci", "account", "cuenta"):
            self.assertNotIn(word, text)

    def test_municipios_and_districts(self):
        m = self.d["municipios"]
        self.assertEqual(len(m["ids"]), 78)
        for k in ("names", "hu", "pop", "bess", "bess_kwh", "sales_gwh_12m", "ami_pct"):
            self.assertEqual(len(m[k]), 78, k)
        self.assertEqual(len(self.d["districts"]["rows"]), 34)
        self.assertEqual(len(self.d["saidi"]["districts"]), 16)

    def test_exposure_is_part_of_the_whole(self):
        for kv, r in self.d["exposure"]["lines"].items():
            self.assertLessEqual(r["sfha_km"], r["km"], kv)
            self.assertLessEqual(r["v_km"], r["sfha_km"] + 0.1, kv)
        x = self.d["exposure"]
        self.assertLessEqual(x["plants_sfha_mw"], x["plants_mw"])


if __name__ == "__main__":
    unittest.main()
