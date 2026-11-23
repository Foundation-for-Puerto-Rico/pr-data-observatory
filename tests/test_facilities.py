"""Tests for facilities.py and nonprofits.py: what is kept (no contact fields), Puerto Rico only, the rules that decide what is drawn and counted, the shelters that
must never be published, and the published files. No network."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import facilities as fa  # noqa: E402
import nonprofits as npo  # noqa: E402

DATA = ROOT / "site" / "data"
CONTACT_COL = re.compile(r"(?i)phone|phn|fax|e-?mail|contact|director|exec|admin|addr|street|website|url|zip|mailing|ein\b|sort_name|^name$")
PHONE_TEXT = re.compile(r"(?<![\d-])(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]\d{4}(?!\d)")
EMAIL_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
POINT_FILES = ("public_housing.geojson", "lihtc.geojson", "fire_stations.geojson", "police_stations.geojson", "libraries.geojson")
PROPS = {"public_housing.geojson": {"name", "type", "municipio", "geoid", "units"}, "lihtc.geojson": {"name", "type", "municipio", "geoid", "units", "li_units", "year"}, "fire_stations.geojson": {"name", "type", "municipio", "geoid"},
         "police_stations.geojson": {"name", "type", "municipio", "geoid", "osm"}, "libraries.geojson": {"name", "type", "municipio", "geoid"}}
# shelters for people at risk must never be published (owner rule): no layer of shelters is built, and no facility's name may describe one
PROTECTED_SHELTER = re.compile(r"(?i)violencia|dom[eé]stic|maltrat|albergue|hogar (?:de|para) (?:ni[nñ]|menor|mujer|v[ií]ctima)|refugio|shelter|safe ?house|casa protegida|menores")


class Kept(unittest.TestCase):
    def test_no_kept_column_can_hold_contact_details(self):
        allowed = {"PROJECT_NAME", "name", "entity_name", "project"}   # facility names: published, with any telephone taken out
        for src, cols in fa.KEEP.items():
            self.assertEqual([c for c in cols if CONTACT_COL.search(c) and c not in allowed], [], src)
        self.assertEqual([c for c in npo.KEEP if CONTACT_COL.search(c) and c != "ZIP"], [])
        self.assertNotIn("NAME", npo.KEEP)
        self.assertNotIn("EIN", npo.KEEP)
        self.assertNotIn("STREET", npo.KEEP)

    def test_the_caches_hold_only_the_kept_columns(self):
        extra = {"hud": {"lon", "lat"}, "lihtc": set(), "usgs": {"lon", "lat"}, "osm": {"osm", "lon", "lat"}, "usac": set()}
        found = False
        for k in fa.FILES:
            p = fa.CACHE / f"{k}.json"
            if p.exists():
                found = True
                for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                    self.assertLessEqual(set(r), set(fa.KEEP[k]) | extra[k], k)
        p = npo.CACHE / "eo_pr.json"
        if p.exists():
            found = True
            for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
                self.assertEqual(set(r), set(npo.KEEP))
        if not found:
            self.skipTest("no cache on this machine (python facilities.py and python nonprofits.py make it)")

    def test_queries_ask_only_for_the_kept_columns(self):
        self.assertIn("STATE2KX='72'", fa.fetch_hud.__code__.co_consts)
        self.assertIn("state='PR'", fa.fetch_usgs.__code__.co_consts)
        self.assertIn("physical_state='PR' AND entity_type='Library'", fa.fetch_usac.__code__.co_consts)

    def test_names_lose_telephones_and_web_addresses(self):
        self.assertEqual(fa.clean_name("Villa Valle Verde A Y B, 829-3343"), "Villa Valle Verde A Y B")
        self.assertEqual(fa.clean_name("Centro (787) 555-1234"), "Centro")
        self.assertEqual(fa.clean_name("Biblioteca info@example.org"), "Biblioteca")
        self.assertEqual(fa.clean_name("Centro www.example.org"), "Centro")
        self.assertEqual(fa.clean_name("Escuela 2020-2021"), "Escuela 2020-2021")   # years are not a telephone
        self.assertEqual(fa.clean_name("Biblioteca 2 Generaciones"), "Biblioteca 2 Generaciones")
        self.assertIsNone(fa.clean_name("  "))


class Munis:
    """A stand-in for facilities.Munis with two square municipios."""
    names, ids = ["Adjuntas", "Aguada"], ["72001", "72003"]
    name_of = dict(zip(ids, names))

    def at(self, lon, lat, tol_km=2.0):
        return "72001" if -67 < lon < -66 and 18 < lat < 19 else "72003" if -68 < lon < -67 and 18 < lat < 19 else None

    def near(self, geoid, lon, lat, km):
        return self.at(lon, lat) == geoid

    def named(self, *texts):
        for t in texts:
            if fa.norm(t) in ("adjuntas", "aguada"):
                return {"adjuntas": "72001", "aguada": "72003"}[fa.norm(t)]
        return None


def sources(hud=(), usgs=(), osm=(), usac=(), lihtc=None):
    return {"hud": {"rows": list(hud)}, "lihtc": None if lihtc is None else {"rows": list(lihtc)}, "usgs": {"rows": list(usgs)}, "osm": {"rows": list(osm)}, "usac": {"rows": list(usac)}}


def tc(name, cnty="1", city="ADJUNTAS", lat="18.2", lon="-66.5", fips="72001956700", hml="2", spc=None, units="40", li="40", yr="2005", st="PR", nonprog=None):
    return {"hud_id": name, "project": name, "proj_cty": city, "proj_st": st, "latitude": lat, "longitude": lon, "fips2020": fips, "cnty2020": cnty, "n_units": units,
            "li_units": li, "yr_pis": yr, "type": "1", "credit": "3", "nonprog": nonprog, "trgt_hml": hml, "trgt_spc": spc}


def hud(name, lvl="R", cnty="001", state="72", units=10, lon=-66.5, lat=18.2):
    return {"DEVELOPMENT_CODE": name, "PROJECT_NAME": name, "TOTAL_UNITS": units, "SCATTERED_SITE_IND": "N", "STATE2KX": state, "CNTY2KX": cnty, "LVL2KX": lvl, "lon": lon, "lat": lat}


def lib(n, status="Active", public="Yes", city="Adjuntas", state="PR", lon="-66.5", lat="18.2", typ="Library"):
    return {"entity_number": n, "entity_name": f"Biblioteca {n}", "entity_type": typ, "status": status, "physical_city": city, "physical_county": None, "physical_state": state,
            "public_library": public, "main_branch": "No", "bookmobile": "No", "kiosk": "No", "latitude": lat, "longitude": lon}


class Rules(unittest.TestCase):
    M = Munis()

    def test_hud_counts_every_development_and_draws_only_precise_points(self):
        out = fa.points(sources(hud=[hud("A", "R"), hud("B", "4"), hud("C", "B"), hud("D", "T"), hud("E", "R", lon=-67.5)]), self.M)
        feats, counts, notes = out["hud"]
        self.assertEqual(counts["ph_devs"]["72001"], 5)
        self.assertEqual(counts["ph_units"]["72001"], 50)
        self.assertEqual(sorted(f["properties"]["name"] for f in feats), ["A", "B"])
        self.assertEqual(notes["not_drawn_approximate_location"], 2)
        self.assertEqual(notes["not_drawn_point_outside_its_municipio"], 1)

    def test_lihtc_counts_every_project_and_draws_only_placed_points_that_serve_no_sensitive_group(self):
        rows = [tc("A"), tc("B", cnty=".", city="AGUADA", lat=None, lon=None, fips="72XXXXXXXXX"), tc("C", lat=None, lon=None, fips="72001XXXXXX"),
                tc("D", hml="1"), tc("E", spc="AIDS/HIV"), tc("F", lon="-67.5"), tc("G", cnty=".", city="NOWHERE", lat=None, lon=None, fips="72XXXXXXXXX"), tc("H", nonprog="1", units="10", li="8"),
                tc("Egida Ejemplo Elderly"), tc("Hogar Ficticio II"), tc("Ejemplo Elderly")]
        feats, counts, notes = fa.points(sources(lihtc=rows), self.M)["lihtc"]
        self.assertEqual(counts["lihtc_projects"]["72001"], 9)   # A, C, D, E, F (its point is in Aguada, its tract in Adjuntas), H and the three named; B in Aguada by its city; G not placed
        self.assertEqual(counts["lihtc_projects"]["72003"], 1)
        self.assertEqual(counts["lihtc_units"]["72001"], 330)
        self.assertEqual(counts["lihtc_li_units"]["72001"], 328)
        self.assertEqual(sorted(f["properties"]["name"] for f in feats), ["A", "Ejemplo Elderly", "H"])   # senior housing is drawn; an égida or a "Hogar" is not
        self.assertEqual(set(feats[0]["properties"]), {"name", "type", "municipio", "geoid", "units", "li_units", "year"})
        self.assertEqual((notes["not_drawn_sensitive"], notes["not_drawn_approximate_location"], notes["not_drawn_point_outside_its_municipio"]), (4, 2, 1))
        self.assertEqual((notes["placed_by_city"], notes["not_placed"], notes["no_longer_monitored"]), (1, 1, 1))
        with self.assertRaises(SystemExit):
            fa.points(sources(lihtc=[tc("X", st="VI")]), self.M)
        self.assertNotIn("lihtc", fa.points(sources(), self.M))   # not read (a clean runner): the published layer is kept

    def test_published_lihtc_layer_names_no_care_home(self):
        # lihtc.geojson is a public register for the places privacy test (its housing names are HUD's), so this test keeps its care homes out
        feats = json.loads((fa.OUT / "lihtc.geojson").read_text(encoding="utf-8"))["features"]
        self.assertGreater(len(feats), 50)
        self.assertEqual([f["properties"]["name"] for f in feats if fa.lihtc_care_name(f["properties"]["name"])], [])

    def test_lihtc_keeps_no_address(self):
        self.assertFalse({"proj_add", "proj_zip", "PROJ_ADD", "PROJ_ZIP"} & set(fa.KEEP["lihtc"]))
        self.assertNotIn("requests", fa.fetch_lihtc.__code__.co_names)   # the archive is saved by hand (HUD USER refuses scripts), never fetched

    def test_puerto_rico_only(self):
        with self.assertRaises(SystemExit):
            fa.points(sources(hud=[hud("A", state="12")]), self.M)
        with self.assertRaises(SystemExit):
            fa.points(sources(usgs=[{"permanent_identifier": "x", "name": "F", "fcode": 74026, "state": "FL", "loaddate": 0, "lon": -66.5, "lat": 18.2}]), self.M)
        with self.assertRaises(SystemExit):
            fa.points(sources(usac=[lib("1", state="VI")]), self.M)
        with self.assertRaises(SystemExit):
            fa.points(sources(usac=[lib("1", typ="School")]), self.M)
        with self.assertRaises(SystemExit):
            fa.points(sources(osm=[{"osm": "n1", "amenity": "social_facility", "name": "X", "operator": None, "police": None, "lon": -66.5, "lat": 18.2}]), self.M)

    def test_libraries_active_public_placed_by_address_drawn_where_the_point_agrees(self):
        out = fa.points(sources(usac=[lib("1"), lib("2", status="Closed"), lib("3", public="No"), lib("4", lon="-67.5"), lib("5", lon="", lat=""), lib("1")]), self.M)
        feats, counts, notes = out["usac"]
        self.assertEqual(counts["libraries"]["72001"], 3)   # 1, 4 (its point is in Aguada, its address in Adjuntas) and 5 (no point); 1 once
        self.assertEqual([f["properties"]["name"] for f in feats], ["Biblioteca 1"])
        self.assertEqual(notes["not_active_or_not_public"], 2)
        self.assertEqual(notes["not_drawn_point_in_another_municipio"], 1)
        self.assertEqual(notes["not_drawn_no_point"], 1)

    def test_police_twice_mapped_counts_once_and_types(self):
        osm = [{"osm": "n1", "amenity": "police", "name": "Policía Municipal de Adjuntas", "operator": None, "police": None, "lon": -66.5, "lat": 18.2},
               {"osm": "w2", "amenity": "police", "name": "Policía Municipal de Adjuntas", "operator": None, "police": None, "lon": -66.5001, "lat": 18.2001},
               {"osm": "n3", "amenity": "police", "name": "Cuartel", "operator": "Policía de Puerto Rico", "police": None, "lon": -66.6, "lat": 18.3},
               {"osm": "n4", "amenity": "police", "name": None, "operator": None, "police": None, "lon": -67.5, "lat": 18.3}]
        feats, counts, notes = fa.points(sources(osm=osm), self.M)["osm"]
        self.assertEqual(sum(counts["police_stations"].values()), 3)
        self.assertEqual(notes["same_station_twice"], 1)
        self.assertEqual(sorted(f["properties"]["type"] for f in feats), ["Municipal police", "Police (agency not stated)", "State police (Puerto Rico Police Bureau)"])

    def test_a_published_point_carries_only_name_type_municipio_and_geoid(self):
        f = fa.feature(-66.512345678, 18.2, "X", "Fire or EMS station", "72001", self.M)
        self.assertEqual(set(f["properties"]), {"name", "type", "municipio", "geoid"})
        self.assertEqual(f["geometry"]["coordinates"], [-66.51235, 18.2])


class Nonprofits(unittest.TestCase):
    def test_ntee_major_groups(self):
        self.assertEqual(npo.group_of("A23"), "npo_arts")
        self.assertEqual(npo.group_of("D20"), "npo_environment")
        self.assertEqual(npo.group_of("H01"), "npo_health")
        self.assertEqual(npo.group_of("P20"), "npo_human")
        self.assertEqual(npo.group_of("W30"), "npo_public")
        self.assertEqual(npo.group_of("Z99"), "npo_unclassified")
        self.assertEqual(npo.group_of(""), "npo_unclassified")
        self.assertEqual(len({g[0] for g in npo.GROUPS}), 10)
        self.assertEqual("".join(sorted("".join(g[2] for g in npo.GROUPS))), "ABCDEFGHIJKLMNOPQRSTUVWXYZ")   # every letter in exactly one group

    def test_placing_an_organization(self):
        by = {"san juan": "72127", "trujillo alto": "72139", "rio grande": "72119", "naguabo": "72103", "guaynabo": "72061", "toa baja": "72137"}
        self.assertEqual(npo.place({"CITY": "SAN JUAN", "ZIP": "00901"}, by, {}), ("72127", "city"))
        self.assertEqual(npo.place({"CITY": "SAINT JUST", "ZIP": "00978"}, by, {}), ("72139", "postal place"))
        self.assertEqual(npo.place({"CITY": "COTO LAUREL", "ZIP": "00780"}, by, {"00780": "72113"}), ("72113", "zip"))
        self.assertEqual(npo.place({"CITY": "NOWHERE", "ZIP": "00000"}, by, {}), (None, "not placed"))


class Published(unittest.TestCase):
    def test_point_files_hold_only_the_allowed_properties_and_no_contact_text(self):
        for f in POINT_FILES:
            p = DATA / f
            if not p.exists():
                self.skipTest("not built")
            d = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn(d.get("source"), ("hud_public_housing", "hud_lihtc", "usgs_structures", "osm", "usac_erate"), f)
            self.assertTrue(d.get("vintage"), f"{f}: no vintage")
            for x in d["features"]:
                self.assertLessEqual(set(x["properties"]), PROPS[f], f)
                self.assertTrue(x["properties"]["geoid"].startswith("72") and len(x["properties"]["geoid"]) == 5, f)
                lon, lat = x["geometry"]["coordinates"]
                self.assertTrue(-68 < lon < -65 and 17.8 < lat < 18.6, f"{f}: a point outside Puerto Rico")
                name = x["properties"]["name"] or ""
                self.assertNotRegex(name, PHONE_TEXT, f)
                self.assertNotRegex(name, EMAIL_TEXT, f)
                self.assertNotRegex(name, PROTECTED_SHELTER, f"{f}: {name!r} reads like a shelter for people at risk")

    def test_no_shelter_layer_is_published_and_the_wanted_row_says_why(self):
        self.assertEqual([p.name for p in DATA.glob("*shelter*")] + [p.name for p in DATA.glob("*refugio*")], [])
        w = {x["id"]: x for x in json.loads((DATA / "wanted.json").read_text(encoding="utf-8"))["items"]}
        self.assertEqual(w["shelters"]["status"], "blocked")
        self.assertTrue(w["shelters"].get("question") and w["shelters"].get("who_to_ask"))

    def test_series_files(self):
        for f, n in (("facility_series.json", 8), ("nonprofit_series.json", 12)):
            p = DATA / f
            if not p.exists():
                self.skipTest("not built")
            t = p.read_text(encoding="utf-8")
            d = json.loads(t)
            self.assertEqual(len(d["vars"]), n, f)
            self.assertEqual(d["geo"]["ids"][-1], "72")
            self.assertEqual(len(d["geo"]["ids"]), 79)
            for v in d["vars"]:
                vals = list(v["years"].values())[0]
                self.assertEqual(len(vals), 79, v["key"])
                self.assertTrue(all(isinstance(x, int) and x >= 0 for x in vals), v["key"])
                self.assertGreaterEqual(vals[-1], sum(vals[:-1]), v["key"])   # Puerto Rico counts every row, including the few no municipio could be given
            self.assertNotRegex(t, r"-6[5-7]\.\d{4,}", f"{f}: a longitude")
            self.assertNotRegex(t, PHONE_TEXT)
        n = json.loads((DATA / "nonprofit_series.json").read_text(encoding="utf-8"))
        parts = sum(list(v["years"].values())[0][-1] for v in n["vars"] if v["key"] not in ("npo_all", "npo_501c3"))
        self.assertEqual(parts, list(n["vars"][0]["years"].values())[0][-1], "the ten groups add up to all organizations")


if __name__ == "__main__":
    unittest.main()
