"""The shared municipio name helper (muni_names.py): every one of the 78 municipios resolves to its FIPS id in every spelling sources use, and
names that are not a municipio resolve to nothing (HANDOFF decision 73)."""
import json
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import muni_names as M  # noqa: E402

CW = json.loads((ROOT / "site" / "data" / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
UNITS = [dict(zip(CW["fields"], u)) for u in CW["units"]["municipio"]]


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def lost(s, mark):
    """The name as a source that lost its accents and ñ shows it."""
    return "".join(mark if plain(c) != c else c for c in s)


class EveryMunicipio(unittest.TestCase):
    def test_78_municipios_with_distinct_keys(self):
        self.assertEqual(len(UNITS), 78)
        self.assertEqual(len(set(M.municipios().values())), 78)
        self.assertEqual(sorted(u["id"] for u in UNITS), sorted(set(M.municipios().values())))

    def test_every_spelling_resolves(self):
        for u in UNITS:
            n, g = u["name_es"], u["id"]
            forms = [n, n.upper(), n.lower(), plain(n), plain(n).upper(), f"Municipio de {n}", f"MUNICIPIO AUTONOMO DE {plain(n).upper()}",
                     f"Municipio Autónomo de {n}", f"Gobierno Municipal de {n}", f"MUNICIPALITY OF {plain(n).upper()}",
                     f"AUTONOMOUS MUNICIPALITY OF {plain(n).upper()}", f"{plain(n).upper()}, MUNICIPALITY OF", f"{n} Municipio",
                     f"{n} Municipio, Puerto Rico", f"{n}, PR", f"  {n}  ", lost(n, "?"), lost(n, chr(0xFFFD)), g, g[2:], str(int(g[2:]))]
            for f in forms:
                self.assertEqual(M.municipio_id(f), g, f"{f!r} should be {g}")

    def test_agrees_with_the_crosswalk_normalised_name(self):
        for u in UNITS:
            self.assertEqual(M.municipio_id(u["norm"]), u["id"])


class NotAMunicipio(unittest.TestCase):
    def test_island_wide_and_unknown_names(self):
        for f in (None, "", "Puerto Rico", "Statewide", "STATEWIDE", "Multiple", "Island-wide", "72", "72000", "72154", "154",
                  "Valle Verde Housing", "San", "Las", "Sabana"):
            self.assertIsNone(M.municipio_id(f), repr(f))

    def test_known_typos(self):
        self.assertEqual(M.municipio_id("MUNICIPIO DE MANAT1"), "72091")
        self.assertEqual(M.municipio_id("Loiza Aldea"), "72087")

    def test_an_ambiguous_wildcard_matches_nothing(self):
        # 'San ?uan' fits only San Juan; '?' alone would fit many names of one letter: none exist, so nothing
        self.assertEqual(M.municipio_id("San ?uan"), "72127")
        self.assertIsNone(M.municipio_id("?"))
        self.assertIsNone(M.municipio_id("Sa????"))


if __name__ == "__main__":
    unittest.main()
