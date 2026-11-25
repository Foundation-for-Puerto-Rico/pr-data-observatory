"""The WCRP Social Capital map (wcrp_social.py; docs/wcrp.md): the cleaned list keeps only its keys and flags, the match, the published counts, the hold.

  python -m unittest tests.test_wcrp_social
"""
import csv
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import wcrp_social as S  # noqa: E402

DATA = ROOT / "site" / "data"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class CleanedList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with S.CSV_PATH.open(encoding="utf-8", newline="") as fh:
            cls.rows = list(csv.DictReader(fh))

    def test_only_the_match_keys_and_the_nine_flags(self):
        self.assertEqual(list(self.rows[0].keys()), S.COLUMNS)
        self.assertEqual(len(self.rows), 711)
        for r in self.rows:
            for _, k in S.FLAGS:
                self.assertIn(r[k], ("si", "no", "nd"), r["nombre_lista"])
            self.assertIn(r["enlace"], ("exacto", "barrio", "parecido", "sin_enlace"))
            self.assertEqual(bool(r["nombre_jp"]), r["enlace"] != "sin_enlace")

    def test_no_contact_details(self):
        text = S.CSV_PATH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"@|https?://|\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b", text), "an e-mail, a web address or a telephone number")
        self.assertNotIn(S.LOST, text, "a lost letter is written '?'")

    def test_the_rule_on_a_small_example(self):
        self.assertTrue(S.same(S.fold("Tanam� (Sector El Valle)"), S.fold("Tanamá (Sector el Valle)")))
        self.assertFalse(S.same(S.fold("Playa"), S.fold("Playita")))
        self.assertEqual(S.restore("Barriada Rull�n", "Rullán", {}), "Barriada Rullán")
        self.assertEqual(S.restore("Ri�to I y II", "Rito I y II", {}), "Ri?to I y II")   # the matching name has no letter there: unknown


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load(DATA / "wcrp_social.json")

    def test_current(self):
        self.assertEqual(S.main(["--check"]), 0)

    def test_counts_add_up(self):
        A, pr = self.doc["assets"], len(self.doc["geo"]["names"]) - 1
        self.assertEqual(A["listed"][pr], 711)
        self.assertEqual(sum(A["listed"][:pr]), 711)
        self.assertEqual(A["match"]["matched_rows"], len(A["poly"]))
        self.assertEqual(self.doc["comunidades"]["polygons"][pr], 713)
        for f in A["flags"]:
            self.assertEqual(sum(A["yes"][f][:pr]), A["yes"][f][pr], f)
            self.assertLessEqual(A["yes"][f][pr] + A["unknown"][f][pr], A["listed"][pr], f)
        self.assertEqual(A["yes"]["pdi"][pr], 593)   # 593 Sí / 118 No in the list (inventory of 2026-10-17)
        self.assertGreaterEqual(A["match"]["matched_rows"] / A["match"]["rows"], 0.98)

    def test_every_polygon_key_is_a_polygon(self):
        keys = {f"{p['municipio']}|{p['nombre']}|{p.get('barrio') or ''}" for p in (f["properties"] for f in load(DATA / "comunidades.geojson")["features"])}
        self.assertLessEqual(set(self.doc["assets"]["poly"]), keys)

    def test_published_in_review_and_released(self):
        # FPR's approval of 2026-10-19 (HANDOFF decision 51): published with the "In review" marker; the compliance review records the approval, and the license
        # review is cleared: the approval covers republishing the list (decision 54). The list states no open license, so the class stays 'unstated' and the
        # dictionary tells others to ask PRDOH and FPR before re-use; no license is invented and no staff member is named
        rec = next(r for r in load(ROOT / "dictionary_src" / "datasets.json")["datasets"] if r["file"] == "wcrp_social.json")
        kinds = {(r["type"], r["status"]) for r in rec["review"]}
        self.assertIn(("compliance", "cleared"), kinds)
        self.assertIn(("licence", "cleared"), kinds)
        self.assertNotIn(("licence", "open"), kinds)
        self.assertEqual(rec["licence_class"], "unstated")
        lic = next(r for r in rec["review"] if r["type"] == "licence")
        self.assertIn("FPR confirmed on 2026-10-19 that its approval covers republishing these sources on the observatory (HANDOFF decision 54).", lic["note"])
        src = load(ROOT / "dictionary_src" / "sources.json")["wcrp_scm"]
        self.assertEqual(src["licence_class"], "unstated")
        for text in (src["licence"], src["terms_note"], lic["note"]):
            self.assertIn("no open license", text.lower())
            self.assertIn("ask PRDOH and FPR", text)
            self.assertNotRegex(text, r"CC[- ]?BY|CC0|Creative Commons|public domain|ODbL|Open Data Commons")
            self.assertNotIn("Francis", text)
        self.assertNotEqual(rec["title"]["es"], rec["title"]["en"])
        held = load(ROOT / "i18n_src" / "held_for_review.json")
        release = {"spanish": {"wcrp_social": [k for r in held["released"] if r["date"] == "2026-10-19" for k in r["spanish"].get("wcrp_social", [])]},
                   "dictionary_plain": [e for r in held["released"] if r["date"] == "2026-10-19" for e in r["dictionary_plain"]]}   # the page's release and its rework, the same day
        self.assertNotIn("wcrp_social", held["spanish"])
        scope = load(ROOT / "i18n_src" / "es" / "wcrp_social.json")
        for k, v in scope.items():
            if re.search(r"WCRP|CDBG|PRDOH|\bHUD\b|Social Capital", k):
                self.assertIn(k, release["spanish"]["wcrp_social"], k)
                self.assertNotEqual(v, k)
        for k in ("Community center", "Sports court", "Residents' association"):   # the list's flags are WCRP-derived
            self.assertIn(k, release["spanish"]["wcrp_social"])
        self.assertIn("wcrp.ce_assets", release["dictionary_plain"])


class NewThemes(unittest.TestCase):
    """The themes the original tool had that the observatory now holds (docs/wcrp.md, "The Social Capital map"): historic places and city halls drawn from
    the main map's own files; treatment facilities and water systems outside PRASA counted only, from the Economy tab's count files."""

    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "site" / "js" / "wcrp_social.js").read_text(encoding="utf-8")

    def test_reuses_main_s_files(self):
        for f in ("historic_places.geojson", "town_halls.geojson", "community_series.json", "infrastructure_series.json"):
            self.assertIn(f"'{f}'", self.js, f)
            self.assertTrue((DATA / f).exists(), f)
        for key in ("'nrhp_places'", "'bh_all'", "'water_nonprasa'", "'water_nonprasa_pop'"):
            self.assertIn(key, self.js)

    def test_sensitive_places_are_counted_not_drawn(self):
        files = set(re.findall(r"file: '([\w.]+\.geojson)'", self.js))
        self.assertEqual(files, {"libraries.geojson", "fire_stations.geojson", "police_stations.geojson", "public_housing.geojson", "historic_places.geojson", "town_halls.geojson"})
        hist = load(DATA / "historic_places.geojson")
        self.assertGreater(hist["notes"]["counted_not_drawn"], 0, "private homes are counted only")
        self.assertLessEqual(set().union(*(f["properties"].keys() for f in hist["features"])), {"name", "type", "municipio", "geoid", "listed"})


if __name__ == "__main__":
    unittest.main()
