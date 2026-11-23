"""Capital projects by municipio (spending_pica.json, pica.py, HANDOFF decision 79): the project lines are read with their municipio, lines that name
several municipios are split equally, regional lines stay unplaced, and the published file adds up: municipios plus unplaced equal the lines read, which
reach at least 99% of the program's stated total. The rebuild from the cached PDF is compared with the published file when the cache is present."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pica as P  # noqa: E402

DATA = ROOT / "site" / "data"

# A page of the program as pdftotext -raw writes it (rows can come before the table's header)
PAGE = """Programa de Inversiones de Cuatro Años 2025-2026 a 2028-2029
Las recomendaciones del Programa de Mejoras Capitales para el cuatrienio
2025-2026 a 2028-2029 asciende a $1,000 miles (Tabla 1).
\x0cREPARACIONES GENERALES CENTRO DE GOBIERNO
DE AIBONITO
Aibonito Rehabilitación 420 0 0 0 420
Tabla 3: Autoridad de Edificios Públicos
Miles de Dólares
Caguas Norte WTP Microgrid Caguas, PR (FEMA-406). Caguas Construcción 100 50 0 0 150
REHABILITACION DE PUENTES
Adjuntas, Utuado Rehabilitación 100 100 0 0 200
Mejoras regionales
Región Metro Construcción 100 0 0 0 100
LINEA QUE NO SUMA
Ponce Construcción 10 10 10 10 99
\x0cTabla 4: Autoridad de Carreteras y Transportación
Juana Díaz
Rehabilitación 30 0 0 0 30
APÉNDICE A
Autoridad de Edificios Públicos 1 0 0 0 0 0 0 1
"""


class Parse(unittest.TestCase):
    def setUp(self):
        self.rows, self.years, self.stated = P.parse(PAGE)

    def test_years_and_stated_total(self):
        self.assertEqual(self.years, [2026, 2027, 2028, 2029])
        self.assertEqual(self.stated, 1_000_000)

    def test_rows_their_municipios_and_dollars(self):
        got = [(a[:9], g, [round(x) for x in v]) for a, fn, g, v in self.rows]
        self.assertEqual(got, [
            ("Autoridad", "72009", [420000, 0, 0, 0]),             # the row on the table's first page, before its header
            ("Autoridad", "72025", [100000, 50000, 0, 0]),          # the municipio at the end of a description
            ("Autoridad", "72001", [50000, 50000, 0, 0]),           # two municipios: split equally
            ("Autoridad", "72141", [50000, 50000, 0, 0]),
            ("Autoridad", None, [100000, 0, 0, 0]),                 # a region: not placed
            ("Autoridad", "72075", [30000, 0, 0, 0]),               # the municipio alone on the line before
        ])
        self.assertEqual({fn for a, fn, g, v in self.rows}, {"general_government", "transportation"})

    def test_a_line_whose_years_do_not_add_up_and_the_appendix_are_left_out(self):
        self.assertEqual(len(self.rows), 6)

    def test_an_unknown_agency_stops_the_build(self):
        with self.assertRaises(ValueError):
            P.parse(PAGE.replace("Tabla 4: Autoridad de Carreteras y Transportación", "Tabla 4: Oficina Nueva"))

    def test_municipios_named(self):
        self.assertEqual(P.municipios_named("Cayey, Cidra y Aibonito"), ["72035", "72041", "72009"])
        self.assertEqual(P.municipios_named("(Varios)"), [])
        self.assertEqual(P.municipios_named("Toa Alta y Toa Baja"), ["72135", "72137"])


class PublishedFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "spending_pica.json").read_text(encoding="utf-8"))

    def test_shapes(self):
        n = len(self.d["geo"]["ids"])
        self.assertEqual(n, 78)
        self.assertEqual(len(self.d["by_muni"]), len(self.d["years"]))
        self.assertTrue(all(len(y) == n for y in self.d["by_muni"]))
        self.assertTrue(all(len(m) == n for a, m, u in self.d["by_agency"]))
        self.assertEqual(len(self.d["population"]), n)
        self.assertTrue(all(isinstance(p, int) and p > 0 for p in self.d["population"]))

    def test_placed_plus_unplaced_is_what_was_read(self):
        placed = sum(map(sum, self.d["by_muni"]))
        self.assertLessEqual(abs(placed - self.d["placed_usd"]), 100)
        self.assertLessEqual(abs(placed + sum(self.d["unplaced"]) - self.d["total_usd"]), 100)
        by_agency = sum(sum(m) + u for a, m, u in self.d["by_agency"])
        self.assertLessEqual(abs(by_agency - self.d["total_usd"]), 100)

    def test_the_lines_read_reach_the_programs_total(self):
        self.assertGreaterEqual(self.d["total_usd"], (1 - P.TOLERANCE) * self.d["stated_total_usd"])
        self.assertEqual(self.d["gap_usd"], self.d["stated_total_usd"] - self.d["total_usd"])

    def test_a_plan_on_the_puerto_rico_fiscal_year_with_no_project_names(self):
        self.assertEqual((self.d["stage"], self.d["fiscal_year_basis"], self.d["level"]), ("proposed", "pr_jul_jun", "state"))
        self.assertNotIn("projects", self.d)
        self.assertLess(len(json.dumps(self.d)), 40_000, "totals only")


@unittest.skipUnless(list(P.CACHE.glob("*.txt")), "the program is not cached here")
class RebuildFromCache(unittest.TestCase):
    def test_the_published_file_is_what_the_cache_gives(self):
        self.assertTrue(P.build(check=True), "run python pica.py")


if __name__ == "__main__":
    unittest.main()
