"""Tests for Phase 3 item 9: care_series.py (CMS facility counts, distance to a health center via care_access.py) and medicare_series.py. No network."""
import csv
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import care_access  # noqa: E402
import care_series as cs  # noqa: E402
import medicare_series as ms  # noqa: E402

DATA = ROOT / "site" / "data"
BANNED = re.compile(r"(?i)name|address|phone|telephone|web|url|email|ccn|certification|lat|lon|coord")


class Kept(unittest.TestCase):
    def test_cms_keeps_no_name_address_phone_or_certification_number(self):
        for key, (_, col, keep) in cs.CMS.items():
            self.assertEqual([c for c in keep if BANNED.search(c)], [], key)
            self.assertIn(col, keep, key)

    def test_the_cms_cache_holds_only_those_columns(self):
        for key, (_, _, keep) in cs.CMS.items():
            p = cs.CMS_CACHE / f"{key}.pr.json"
            if p.exists():
                for r in json.loads(p.read_text(encoding="utf-8")):
                    self.assertLessEqual(set(r), set(keep), key)

    def test_the_site_points_cache_holds_two_coordinates_and_nothing_else(self):   # owner decision 2026-10-14: the points stay in the local cache, never published
        if not care_access.POINTS.exists():
            self.skipTest("no site points in the cache")
        with care_access.POINTS.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["lon", "lat"])
        self.assertTrue(all(len(r) == 2 for r in rows))

    def test_medicare_keeps_counts_only(self):
        self.assertEqual([c for c in ms.KEEP if BANNED.search(c) and c not in ("BENE_STATE_ABRVTN",)], [])

    def test_no_published_file_holds_a_point_or_a_facility(self):
        for f in ("care_series.json", "medicare_series.json"):
            p = DATA / f
            if p.exists():
                t = p.read_text(encoding="utf-8")
                self.assertNotRegex(t, r"-6[5-7]\.\d{4,}", f"{f}: a longitude")   # Puerto Rico's longitudes
                self.assertNotIn("countyparish", t)
                self.assertNotIn("zip_code", t)


class Counts(unittest.TestCase):
    NAMES, IDS = ["San Juan", "Ponce", "Mayagüez"], ["72127", "72113", "72097"]

    def test_a_county_or_a_town_names_the_municipality_with_or_without_accents(self):
        rows = [{"countyparish": "SAN JUAN", "zip_code": "00901"}, {"countyparish": "Mayaguez", "zip_code": "00680"}, {"countyparish": "San Juan Municipio", "zip_code": "00909"}]
        out, _ = cs.cms_counts("dialysis", rows, self.NAMES, self.IDS)
        self.assertEqual(out, {"72127": 2, "72097": 1})

    def test_a_barrio_name_is_placed_by_its_zip_code(self):
        rows = [{"citytown": "HATO REY", "zip_code": "00917"}, {"citytown": "COTO LAUREL", "zip_code": "00780"}]
        out, _ = cs.cms_counts("home_health", rows, self.NAMES, self.IDS)
        self.assertEqual(out, {"72127": 1, "72113": 1})

    def test_an_unknown_name_stops_the_build(self):
        with self.assertRaises(SystemExit):
            cs.cms_counts("home_health", [{"citytown": "SOMEWHERE", "zip_code": "00000"}], self.NAMES, self.IDS)

    def test_hospitals_with_emergency_services(self):
        rows = [{"countyparish": "PONCE", "zip_code": "00716", "hospital_type": "Acute Care Hospitals", "emergency_services": "Yes"},
                {"countyparish": "PONCE", "zip_code": "00716", "hospital_type": "Psychiatric", "emergency_services": "No"}]
        out, er = cs.cms_counts("hospitals", rows, self.NAMES, self.IDS)
        self.assertEqual((out["72113"], er["72113"]), (2, 1))


class Published(unittest.TestCase):
    def test_care_series(self):
        p = DATA / "care_series.json"
        if not p.exists():
            self.skipTest("care_series.json is not built")
        d = json.loads(p.read_text(encoding="utf-8"))
        V = {v["key"]: list(v["years"].values())[0] for v in d["vars"]}
        self.assertEqual(len(d["geo"]["ids"]), 79)
        for k in ("cms_hospitals", "cms_hospitals_er", "cms_dialysis", "cms_nursing_homes", "cms_home_health", "cms_hospice"):
            self.assertEqual(V[k][-1], sum(V[k][:-1]), k)
        self.assertLessEqual(V["cms_hospitals_er"][-1], V["cms_hospitals"][-1])
        for k in ("hc_road_km", "hc_drive_min", "hc_within_10km_pct"):
            self.assertEqual(sum(x is None for x in V[k]), 0, k)
        self.assertTrue(all(0 <= x <= 100 for x in V["hc_within_10km_pct"]))
        self.assertLess(d["notes"]["access"]["residents_left_out"], 1000, "almost every resident is measured")

    def test_medicare_series(self):
        p = DATA / "medicare_series.json"
        if not p.exists():
            self.skipTest("medicare_series.json is not built")
        d = json.loads(p.read_text(encoding="utf-8"))
        V = {v["key"]: v["years"] for v in d["vars"]}
        for y, a in V["medicare_benes"].items():
            munis = sum(x for x in a[:78] if x is not None)
            self.assertLess(abs(a[-1] - munis), 100, y)   # the state row also counts the few people of an unknown municipality
        self.assertEqual(V["medicare_benes"]["2013"][-1], 711896)

    def test_suppressed_counts_are_no_value(self):
        self.assertIsNone(ms.num("*"))
        self.assertEqual(ms.num("1,234"), 1234)

    def test_every_variable_has_a_dictionary_entry_and_spanish(self):
        ids = {e["id"] for f in ("care.json", "medicare.json") for e in json.loads((ROOT / "dictionary_src" / "entries" / f).read_text(encoding="utf-8"))}
        es = json.loads((ROOT / "i18n_src" / "es" / "labels_health.json").read_text(encoding="utf-8"))
        for f in ("care_series.json", "medicare_series.json"):
            p = DATA / f
            if not p.exists():
                continue
            for v in json.loads(p.read_text(encoding="utf-8"))["vars"]:
                self.assertIn("health." + v["key"], ids)
                self.assertIn(v["label"], es)
                self.assertIn("Health care · " + v["group"], es)


if __name__ == "__main__":
    unittest.main()
