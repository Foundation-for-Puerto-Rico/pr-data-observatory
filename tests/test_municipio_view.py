"""Public money in each municipio's territory (spending_municipio.json, municipio_view.py, HANDOFF decision 109, step 5): the file only repeats
published figures (each row equals its source files), it has the 78 municipios, and the ABRE Tu Municipio slugs follow the site's rule."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import municipio_view as V  # noqa: E402

D = ROOT / "site" / "data"
OUT = D / "spending_municipio.json"


class Slugs(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(V.slug("San Juan"), "san-juan")
        self.assertEqual(V.slug("Mayagüez"), "mayaguez")
        self.assertEqual(V.slug("Juana Díaz"), "juana-diaz")
        self.assertEqual(V.slug("Las Marías"), "las-marias")


@unittest.skipUnless(OUT.exists(), "spending_municipio.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_rows_repeat_the_published_files(self):
        cd = json.loads((D / "spending_cdbgdr.json").read_text(encoding="utf-8"))
        fe = json.loads((D / "spending_fema_pa.json").read_text(encoding="utf-8"))
        pica = json.loads((D / "spending_pica.json").read_text(encoding="utf-8"))
        self.assertEqual([m["id"] for m in self.d["municipios"]], cd["geo"]["ids"])
        for i, m in enumerate(self.d["municipios"]):
            self.assertEqual(m["cdbgdr"], round(sum(yr[i] for yr in cd["by_muni"])))
            self.assertEqual(m["fema_usd"], fe["by_muni"]["usd"][i])
            self.assertEqual(m["plan"], round(sum(yr[i] for yr in pica["by_muni"])))
            self.assertLessEqual(sum(v for _, v in m["plan_top"]), m["plan"] + 3)

    def test_the_file_is_current(self):
        self.assertTrue(V.build(check=True))


if __name__ == "__main__":
    unittest.main()
