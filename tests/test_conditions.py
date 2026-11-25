"""Tests for conditions.py: the rules (sites in barrios, shares of area, tracts spread over barrios, intersections, hospital names), what is kept (no contact fields),
and the published files: every one of the 901 barrios, no names or points, drive times that make sense (0 where a hospital is, finite elsewhere, none for the
islands no road reaches). No network.

  python -m unittest tests.test_conditions
"""
import json
import math
import re
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import conditions as C  # noqa: E402

DATA = ROOT / "site" / "data"
CONTACT_COL = re.compile(r"(?i)phone|phn|fax|e-?mail|contact|director|exec|admin|addr|street|website|url|zip|mailing|owner|parent|^name$")
PHONE_TEXT = re.compile(r"(?<![\d-])(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]\d{4}(?!\d)")
EMAIL_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ISLANDS = ("72049", "72147")   # Culebra, Vieques: no road link to the main island
KEYS = ["epa_tri", "epa_rmp", "epa_npl", "epa_landfills", "epa_landfills_open", "epa_303d_pct", "epa_naa_so2_pct", "epa_naa_lead_pct", "chas_severe_hh", "chas_severe_pct",
        "street_intersections", "street_intersection_density", "hosp_drive_min", "hosp_road_km"]


def load(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


class StubBarrios:
    """Three square barrios in two municipios, on a plane where a degree is a kilometer (enough for the rules)."""
    ids = ["7200100001", "7200100002", "7200300003"]
    mids, names = ["72001", "72003"], ["Uno", "Tres"]

    def __init__(self, weights=()):
        self.cw = {"weights": {"barrio_tract": {"fields": ["barrio", "tract", "pop"], "rows": list(weights)}}}

    def at(self, lon, lat, tol_km=2.0):
        if lon is None or lat is None or not (0 <= lat < 1):
            return None
        return 0 if 0 <= lon < 1 else 1 if 1 <= lon < 2 else 2 if 2 <= lon < 3 else None

    def muni_of(self, i):
        return self.ids[i][:5]


class Rules(unittest.TestCase):
    def test_sites_are_counted_in_the_barrio_that_holds_them_and_add_up(self):
        B = StubBarrios()
        nb, nm, total, unplaced = C.counts_by_area(B, [(0.5, 0.5), (0.2, 0.1), (1.5, 0.5), (2.5, 0.5), (9, 9), (None, None)])
        self.assertEqual(nb, [2, 1, 1])
        self.assertEqual(dict(nm), {"72001": 3, "72003": 1})
        self.assertEqual((total, unplaced), (6, 2), "Puerto Rico counts every site, the unplaced ones too")

    def test_intersections_need_three_street_legs(self):
        d = {"rows": [[1, "S1400", 10, 11], [2, "S1400", 10, 12], [3, "S1200", 10, 13],   # node 10: three legs
                      [4, "S1400", 20, 21], [5, "S1400", 20, 22], [6, "S1100", 20, 23],   # node 20: the third leg is a highway, not a street
                      [7, "S1730", 30, 30], [8, "S1400", 30, 31]],                       # node 30: a loop counts twice
             "nodes": {str(n): [n, 0] for n in (10, 11, 12, 13, 20, 21, 22, 23, 30, 31)}}
        self.assertEqual(C.intersections(d), [(10, 0), (30, 0)])
        self.assertNotIn("S1100", C.STREET_MTFCC)
        self.assertNotIn("S1630", C.STREET_MTFCC)

    def test_tract_counts_are_spread_over_barrios_by_housing_units_and_municipios_are_exact(self):
        # tract A (72001): 30 of 100 households with a severe problem; barrio 1 has 75 of its 100 housing units, barrio 2 has 25. Tract B (72003): all in barrio 3.
        w = [["7200100001", "72001000100", 200, 75, 3], ["7200100002", "72001000100", 60, 25, 1], ["7200300003", "72003000200", 90, 40, 2]]
        rows = [{"GEOID": "72001000100", "T2_EST1": 100, "T2_EST3": 10, "T2_EST127": 20}, {"GEOID": "72003000200", "T2_EST1": 40, "T2_EST3": 5, "T2_EST127": 5}]
        bn, bd, mn, md, notes = C.chas_by_area(StubBarrios(w), rows)
        self.assertAlmostEqual(bn["7200100001"], 22.5)
        self.assertAlmostEqual(bd["7200100001"], 75)
        self.assertAlmostEqual(bn["7200100002"], 7.5)
        self.assertEqual((mn["72001"], md["72001"], mn["72003"], md["72003"]), (30, 100, 10, 40))
        self.assertEqual(notes["households_in_tracts_without_2020_housing_units"], 0)

    def test_hospital_names_match_on_their_own_words(self):
        self.assertEqual(C.name_words("HOSPITAL PAVIA HATO REY, INC"), {"pavia", "hato", "rey"})
        self.assertEqual(C.name_words("Hospital Pavía de Hato Rey"), {"pavia", "hato", "rey"})
        self.assertEqual(C.name_words("CENTRO MEDICO DEL NORESTE"), {"noreste"})
        self.assertGreater(C.NAME_MATCH, 0.5, "a half match took the wrong building in the 2026-10-17 test (Bayamón Medical Center)")

    def test_a_partial_name_needs_hhs_point_nearby_and_a_hospital_name(self):
        # (name words, municipio, lon, lat, named a hospital): a degree here is about 105 km east-west, so 0.005 is about half a km
        osm = [(C.name_words("Hospital Metropolitano de San Juan"), "San Juan", -66.0986, 18.3897, True),
               (C.name_words("Pavía Medical Plaza"), "San Juan", -66.0700, 18.4450, False),
               (C.name_words("Doctors' Center Hospital Bayamón"), "Bayamón", -66.1650, 18.3960, True)]
        self.assertEqual(C.near_hhs(C.name_words("METROPOLITAN HOSPITAL"), (-66.0990, 18.3897), osm), (-66.0986, 18.3897), "metropolitan and metropolitano meet")
        self.assertIsNone(C.near_hhs(C.name_words("METROPOLITAN HOSPITAL"), (-66.0800, 18.3897), osm), "more than 1 km from HHS's point")
        self.assertIsNone(C.near_hhs(C.name_words("HOSPITAL PAVIA SANTURCE"), (-66.0701, 18.4451), osm), "a plaza is not a hospital building")
        self.assertIsNone(C.near_hhs(C.name_words("BAYAMON MEDICAL CENTER"), (-66.1498, 18.3957), osm), "the 2026-10-17 trap: a hospital of the same town 1.8 km away")
        two = osm + [(C.name_words("Hospital Metropolitano Dr. Pila"), "San Juan", -66.0980, 18.3895, True)]
        self.assertIsNone(C.near_hhs(C.name_words("METROPOLITAN HOSPITAL"), (-66.0990, 18.3897), two), "two buildings share as many words: no choice is made")
        self.assertTrue(C.named_hospital("Manatí Medical Center") and C.named_hospital("Centro Médico de Puerto Rico") and not C.named_hospital("CDT Dorado Medical Complex"))

    def test_a_busy_server_is_asked_again_after_a_wait(self):
        class Answer:
            def __init__(self, status, body=None, headers=None):
                self.status_code, self._body, self.headers = status, body or {}, headers or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise C.requests.HTTPError(f"HTTP {self.status_code}")

            def json(self):
                return self._body
        waits = []
        answers = [Answer(429, headers={"Retry-After": "7"}), Answer(503), Answer(200, {"features": [{"attributes": {"GEOID": "1"}}]})]
        with mock.patch.object(C.requests, "get", side_effect=lambda *a, **k: answers.pop(0)), mock.patch.object(C.time, "sleep", waits.append), mock.patch.object(C, "log"):
            self.assertEqual(C.arcgis("https://x/FeatureServer/1", "STATE='72'", ["GEOID"], geometry=False), [{"attributes": {"GEOID": "1"}}])
        self.assertEqual(waits, [7.0, 8], "Retry-After first, then the backoff (4, 8, 16 ...)")
        waits.clear()
        answers = [Answer(200, {"error": {"code": 429, "message": "Too many requests"}}), Answer(200, {"features": [{"attributes": {"GEOID": "2"}}]})]
        with mock.patch.object(C.requests, "get", side_effect=lambda *a, **k: answers.pop(0)), mock.patch.object(C.time, "sleep", waits.append), mock.patch.object(C, "log"):
            self.assertEqual(len(C.arcgis("https://x/FeatureServer/1", "STATE='72'", ["GEOID"], geometry=False)), 1, "a 429 inside the JSON is asked again too")
        self.assertEqual(waits, [4])
        answers = [Answer(429) for _ in range(C.TRIES)]
        with mock.patch.object(C.requests, "get", side_effect=lambda *a, **k: answers.pop(0)), mock.patch.object(C.time, "sleep", lambda s: None), mock.patch.object(C, "log"):
            with self.assertRaises(SystemExit):
                C.get("https://x/FeatureServer/1/query")
        self.assertEqual(answers, [], f"it gives up after {C.TRIES} tries")
        self.assertEqual(C.backoff(10), 60)
        self.assertEqual(C.backoff(0, "600"), 120, "a long Retry-After is capped")

    def test_refresh_keys(self):
        self.assertEqual(C.parse_refresh(["x"]), ())
        self.assertEqual(C.parse_refresh(["x", "--refresh"]), C.SOURCE_KEYS)
        self.assertEqual(C.parse_refresh(["x", "--refresh", "tri,chas"]), ("tri", "chas"))
        with self.assertRaises(SystemExit):
            C.parse_refresh(["x", "--refresh", "tri,nope"])


class Kept(unittest.TestCase):
    def test_no_kept_column_can_hold_contact_details(self):
        allowed = {"name", "assessmentunitname", "area_name"}   # site, water and air-area names: kept in the local cache only, never published
        for src, cols in C.KEEP.items():
            self.assertEqual([c for c in cols if CONTACT_COL.search(c) and c not in allowed], [], src)

    def test_the_caches_hold_only_the_kept_columns(self):
        extra = {"tri": {"lon", "lat"}, "frs": {"lon", "lat"}, "attains": {"geometry"}, "greenbook": {"geometry"}, "lmop": {"lon", "lat"}, "chas": set(), "hospitals": {"lon", "lat", "hhs_lon", "hhs_lat"}}
        found = False
        for k, cols in C.KEEP.items():
            p = C.CACHE / f"{k}.json"
            if not p.exists():
                continue
            found = True
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertLessEqual(set(r), set(cols) | extra[k], k)
        p = C.CACHE / "hospitals.json"
        if p.exists():
            self.assertNotRegex(p.read_text(encoding="utf-8"), r'"(facility_id|facility_name|address|telephone_number|ccn)"', "hospital names, addresses and certification numbers are never cached")
        if not found:
            self.skipTest("no cache on this machine (python conditions.py makes it)")

    def test_the_queries_ask_for_puerto_rico_only(self):
        consts = " ".join(str(c) for f in (C.fetch_frs, C.fetch_attains, C.fetch_greenbook, C.fetch_lmop, C.fetch_chas) for c in f.__code__.co_consts)
        for w in ("STATE_CODE='PR'", "state='PR'", "state_abbreviation='PR'", "county_state LIKE '%, PR'", "STATE='72'"):
            self.assertIn(w, consts)
        self.assertIn("_PR/", C.TRI_URL)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s, cls.b = load("conditions_series.json"), load("conditions_barrio.json")
        if cls.s is None or cls.b is None:
            raise unittest.SkipTest("not built")
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.barrios = [r[F["id"]] for r in cw["units"]["barrio"]]
        cls.pop = {r[F["id"]]: r[F["pop"]] for r in cw["units"]["barrio"]}
        cls.bv = {v["key"]: list(v["years"].values())[0] for v in cls.b["vars"]}
        cls.mv = {v["key"]: list(v["years"].values())[0] for v in cls.s["vars"]}
        cls.meta = {v["key"]: v for v in cls.s["vars"]}

    def test_every_barrio_and_every_municipio(self):
        self.assertEqual(len(self.barrios), 901)
        self.assertEqual(self.b["geo"]["ids"], self.barrios, "the barrio file covers the 901 barrios, in the crosswalk's order")
        fc = json.loads((DATA / "barrios.geojson").read_text(encoding="utf-8"))
        self.assertEqual(sorted(f["properties"]["geoid"] for f in fc["features"]), sorted(self.barrios))
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual(self.s["geo"]["ids"][-1], "72")
        self.assertEqual(sorted(self.bv), sorted(KEYS))
        self.assertEqual(sorted(self.mv), sorted(KEYS))
        for k in KEYS:
            self.assertEqual(len(self.bv[k]), 901, k)
            self.assertEqual(len(self.mv[k]), 79, k)
            self.assertEqual(self.meta[k]["barrioFile"], "conditions_barrio.json", k)
            self.assertEqual(list(self.meta[k]["years"]), [str(y) for y in [int(list(next(v for v in self.b["vars"] if v["key"] == k)["years"])[0])]], f"{k}: the barrio and municipio values are of one vintage")

    def test_counts_add_up_from_barrios_to_municipios(self):
        for k in ("epa_tri", "epa_rmp", "epa_npl", "epa_landfills", "epa_landfills_open", "street_intersections"):
            b, m = self.bv[k], self.mv[k]
            self.assertTrue(all(isinstance(x, int) and x >= 0 for x in b + m), k)
            by = Counter()
            for g, x in zip(self.barrios, b):
                by[g[:5]] += x
            self.assertEqual(m[:-1], [by[f] for f in self.s["geo"]["ids"][:-1]], k)
            self.assertGreaterEqual(m[-1], sum(m[:-1]), k)
        self.assertLessEqual(self.mv["epa_landfills_open"][-1], self.mv["epa_landfills"][-1])

    def test_shares_are_shares(self):
        for k in ("epa_303d_pct", "epa_naa_so2_pct", "epa_naa_lead_pct", "chas_severe_pct"):
            for x in self.bv[k] + self.mv[k]:
                self.assertTrue(x is None or 0 <= x <= 100, (k, x))
        self.assertGreater(sum(1 for x in self.bv["epa_naa_lead_pct"] if x), 0, "Arecibo's lead area touches some barrios")
        self.assertTrue(all(x is not None for x in self.bv["epa_303d_pct"]))

    def test_barrio_estimates_of_severe_housing_problems_add_up_to_the_tracts(self):
        tot = sum(x for x in self.bv["chas_severe_hh"] if x)
        self.assertLess(abs(tot - self.mv["chas_severe_hh"][-1]) / self.mv["chas_severe_hh"][-1], 0.005, "spreading tracts over barrios keeps the total (up to rounding)")
        self.assertEqual(self.meta["chas_severe_hh"].get("tag"), "estimate")
        self.assertIn("estimate", self.meta["chas_severe_pct"]["definition"])

    def test_drive_times_are_plausible(self):
        mins, kms = self.bv["hosp_drive_min"], self.bv["hosp_road_km"]
        self.assertEqual([x is None for x in mins], [x is None for x in kms])
        islands = [i for i, g in enumerate(self.barrios) if g[:5] in ISLANDS]
        self.assertTrue(islands and all(mins[i] is None for i in islands), "Vieques and Culebra have no road to a hospital: no value, not a number")
        for i, g in enumerate(self.barrios):
            if mins[i] is None and g[:5] not in ISLANDS:
                self.assertEqual(self.pop[g], 0, f"{g}: only an uninhabited barrio may lack a road to a hospital")
            if mins[i] is not None:
                self.assertTrue(math.isfinite(mins[i]) and 0 <= mins[i] < 90, (g, mins[i]))
                self.assertTrue(0 <= kms[i] < 80, (g, kms[i]))
                self.assertTrue((mins[i] == 0) == (kms[i] == 0), g)
                if kms[i] > 2:
                    self.assertLess(kms[i] / (mins[i] / 60), 95, f"{g}: faster than any planning speed")
        ids = self.s["geo"]["ids"]
        for f in ISLANDS:
            self.assertIsNone(self.mv["hosp_drive_min"][ids.index(f)])
        self.assertTrue(all(x is not None for f, x in zip(ids, self.mv["hosp_drive_min"]) if f not in ISLANDS))
        self.assertTrue(self.meta["hosp_drive_min"].get("noValue"), "an empty place says why")
        zero = sum(1 for x in mins if x == 0)
        self.assertGreaterEqual(zero, 30, "a barrio that holds a general hospital is 0")
        self.assertLessEqual(zero, self.s["notes"]["hospitals"]["hospitals"])

    def test_a_barrio_that_holds_a_hospital_is_zero(self):
        p = C.CACHE / "hospitals.json"
        if not p.exists():
            self.skipTest("no hospital cache on this machine")
        B = C.Barrios()
        held = {B.at(r["lon"], r["lat"], tol_km=0.5) for r in json.loads(p.read_text(encoding="utf-8"))["rows"]} - {None}
        for i in held:
            self.assertEqual(self.bv["hosp_drive_min"][i], 0.0, B.ids[i])
        for i, x in enumerate(self.bv["hosp_drive_min"]):
            if i not in held and x is not None:
                self.assertGreater(x, 0, B.ids[i])

    def test_no_names_points_or_contact_text_are_published(self):
        for name in ("conditions_series.json", "conditions_barrio.json"):
            t = (DATA / name).read_text(encoding="utf-8")
            self.assertNotRegex(t, r"-6[5-7]\.\d{4,}", f"{name}: a longitude")
            self.assertNotRegex(t, PHONE_TEXT, name)
            self.assertNotRegex(t, EMAIL_TEXT, name)
            d = json.loads(t)
            self.assertNotRegex(json.dumps([d["vars"], d.get("notes")]), r'"(lon|lat|lng|address|name|names)"\s*:', f"{name}: a site's name or point")
        tri = C.CACHE / "tri.json"
        if tri.exists():
            names = [r["name"] for r in json.loads(tri.read_text(encoding="utf-8"))["rows"] if r.get("name") and len(r["name"]) > 12]
            t = (DATA / "conditions_series.json").read_text(encoding="utf-8")
            self.assertEqual([n for n in names if n in t], [], "no TRI facility name is published")

    def test_every_source_is_named_in_the_contract(self):
        listed = json.loads((ROOT / "dictionary_src" / "sources.json").read_text(encoding="utf-8"))
        for v in self.s["vars"]:
            for sid in v["sources"]:
                self.assertIn(sid, listed, v["key"])
                self.assertIn(sid, self.s["sources"], v["key"])

    def test_the_skipped_sources_say_why(self):
        w = {x["id"]: x for x in json.loads((DATA / "wanted.json").read_text(encoding="utf-8"))["items"]}
        for k in ("open-dumps", "chas-latest"):
            self.assertEqual(w[k]["status"], "blocked", k)
            self.assertTrue(w[k].get("question") and w[k].get("who_to_ask"), k)
        self.assertEqual(w["landfills"]["status"], "live")


if __name__ == "__main__":
    unittest.main()
