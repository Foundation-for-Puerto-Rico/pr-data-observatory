"""Tests for community_assets.py (historic places, city halls, treatment facilities) and the non-PRASA water counts of infrastructure_series.py: Puerto Rico only,
no contact fields, no names or points for treatment facilities or water systems, the rules that decide what is drawn and counted, and the published files. No network."""
import io
import json
import re
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import community_assets as ca  # noqa: E402
import facilities as fa  # noqa: E402

DATA = ROOT / "site" / "data"
CONTACT_COL = re.compile(r"(?i)phone|phn|fax|e-?mail|contact|director|exec|admin|addr|street|website|url|zip|mailing|intake|hotline|^name\d?$|owner")
PHONE_TEXT = re.compile(r"(?<![\d-])(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]\d{4}(?!\d)")
EMAIL_TEXT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PROPS = {"historic_places.geojson": {"name", "type", "municipio", "geoid", "listed"}, "town_halls.geojson": {"name", "type", "municipio", "geoid", "osm"}}


class Munis:
    """A stand-in for facilities.Munis with two square municipios (Adjuntas west of -66 is Aguada here, for the test only)."""
    names, ids = ["Adjuntas", "Aguada"], ["72001", "72003"]
    name_of = dict(zip(ids, names))

    def at(self, lon, lat, tol_km=2.0):
        return "72001" if -67 < lon < -66 and 18 < lat < 19 else "72003" if -68 < lon < -67 and 18 < lat < 19 else None

    def near(self, geoid, lon, lat, km):
        return (geoid == "72001" and -67 < lon < -66 and 17.9 < lat < 19) or (geoid == "72003" and -68 < lon < -67 and 17.9 < lat < 19)

    def named(self, *texts):
        for t in texts:
            k = fa.norm(t)
            if k in ("adjuntas", "aguada"):
                return {"adjuntas": "72001", "aguada": "72003"}[k]
        return None


def nrhp(ref, name="Iglesia X", lon=-66.5, lat=18.2, state="PUERTO RICO", status="Listed", city="Adjuntas", typ="building", cert="1984-12-", layer="point"):
    return {"NRIS_Refnum": ref, "RESNAME": name, "ResType": typ, "City": city, "CertDate": cert, "STATUS": status, "State": state, "layer": layer, "lon": lon, "lat": lat}


def hall(osm, name="Casa Alcaldía de Adjuntas", lon=-66.5, lat=18.2, amenity="townhall"):
    return {"osm": osm, "amenity": amenity, "name": name, "townhall:type": None, "lon": lon, "lat": lat}


def xlsx(rows):
    """A minimal .xlsx (inline strings) that xlsx_lite reads, with one sheet named 'Facilities List'."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    col = lambda i: chr(65 + i)
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;")
    body = "".join(f'<row r="{r + 1}">' + "".join(f'<c r="{col(i)}{r + 1}" t="inlineStr"><is><t>{esc(v)}</t></is></c>' for i, v in enumerate(row)) + "</row>" for r, row in enumerate(rows))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook {ns} {rel}><sheets><sheet name="Facilities List" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{body}</sheetData></worksheet>")
    return b.getvalue()


HEAD = ["name1", "name2", "street1", "street2", "city", "state", "zip", "phone", "intake1", "intake2", "intake1a", "intake2a", "service_code_info"]


def dir_row(name, street, city, state, codes, phone="787-555-0100"):
    return [name, "", street, "", city, state, "00601", phone, phone, "", "", "", codes + " * OP * CASH"]


class Kept(unittest.TestCase):
    def test_no_kept_column_can_hold_contact_details(self):
        allowed = {"RESNAME", "name"}   # the names of historic places and city halls: published
        for src, cols in ca.KEEP.items():
            self.assertEqual([c for c in cols if CONTACT_COL.search(c) and c not in allowed], [], src)
        self.assertEqual(set(ca.KEEP["samhsa"]), {"dir", "key", "city", "state", "care"}, "a treatment facility keeps no name, address, telephone or point")
        self.assertNotIn("Address", ca.KEEP["nps"])

    def test_the_caches_hold_only_the_kept_columns(self):
        extra = {"nps": {"layer", "lon", "lat"}, "townhall": {"osm", "lon", "lat"}, "samhsa": set()}
        found = False
        for k in ca.SOURCE_KEYS:
            p = ca.CACHE / f"{k}.json"
            if p.exists():
                found = True
                d = json.loads(p.read_text(encoding="utf-8"))
                for r in d["rows"]:
                    self.assertLessEqual(set(r), set(ca.KEEP[k]) | extra[k], k)
                if k == "samhsa":
                    t = p.read_text(encoding="utf-8")
                    self.assertNotRegex(t, PHONE_TEXT, "a telephone number in the SAMHSA cache")
                    self.assertNotIn("lat", t.replace("latest", ""))
                    self.assertEqual({r["state"] for r in d["rows"]}, {"PR"})
        if not found:
            self.skipTest("no cache on this machine (python community_assets.py makes it)")

    def test_queries_ask_for_puerto_rico_only(self):
        self.assertEqual(ca.NPS_WHERE, "State='PUERTO RICO'")
        self.assertIn('"amenity"="townhall"', ca.TOWNHALL_QUERY)
        self.assertEqual(fa.BBOX, (17.85, -67.97, 18.57, -65.20))

    def test_listing_dates(self):
        self.assertEqual(ca.listed("1984-12-"), "1984-12")
        self.assertEqual(ca.listed("8/31/2022"), "2022-08-31")
        self.assertEqual(ca.listed("2026-01-"), "2026-01")
        self.assertIsNone(ca.listed(""))
        self.assertIsNone(ca.listed(None))


class Samhsa(unittest.TestCase):
    M = Munis()

    def test_a_directory_keeps_puerto_rico_rows_without_names_addresses_or_telephones(self):
        content = xlsx([HEAD, dir_row("Centro Uno", "1 Calle Sol", "Adjuntas", "PR", "SA MH SUMH"), dir_row("Florida Rehab", "2 Main St", "Miami", "FL", "SA"),
                        dir_row("Centro Dos", "3 Calle Luna", "Aguada", "PR", "MH")])
        rows = ca.samhsa_rows("mh", content)
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(set(r), set(ca.KEEP["samhsa"]))
            self.assertEqual(r["state"], "PR")
        t = json.dumps(rows)
        for secret in ("Centro", "Calle", "787", "555", "00601", "Florida"):
            self.assertNotIn(secret, t)
        self.assertEqual(rows[0]["care"], ["MH", "SA", "SUMH"])

    def test_a_directory_without_the_expected_columns_stops_the_build(self):
        with self.assertRaises(SystemExit):
            ca.samhsa_rows("su", xlsx([["name", "city", "state"], ["X", "Adjuntas", "PR"]]))

    def test_a_facility_in_both_directories_counts_once_and_types_are_exclusive(self):
        k = lambda n: ca.fac_key({"name1": n, "name2": "", "street1": "1 Calle", "city": "Adjuntas"})
        rows = [{"dir": "su", "key": k("A"), "city": "Adjuntas", "state": "PR", "care": ["SA", "SUMH"]},
                {"dir": "mh", "key": k("A"), "city": "Adjuntas", "state": "PR", "care": ["MH"]},          # A: in both directories, both types of care
                {"dir": "su", "key": k("B"), "city": "Adjuntas", "state": "PR", "care": ["SA"]},          # B: substance use only
                {"dir": "mh", "key": k("C"), "city": "Aguada", "state": "PR", "care": ["MH", "SUMH"]},    # C: mental health only
                {"dir": "mh", "key": k("D"), "city": "Nowhere", "state": "PR", "care": ["MH"]}]          # D: a city no municipio has: Puerto Rico only
        counts, island, notes = ca.treatment(rows, self.M)
        self.assertEqual((counts["bh_both"]["72001"], counts["bh_su"]["72001"], counts["bh_mh"]["72003"]), (1, 1, 1))
        self.assertEqual(counts["bh_all"]["72001"], 2)
        self.assertEqual((island["bh_all"], island["bh_mh"]), (4, 2))
        self.assertEqual((notes["facilities"], notes["in_both_directories"], notes["not_placed_city_unknown"]), (4, 1, 1))
        with self.assertRaises(SystemExit):
            ca.treatment([{**rows[0], "state": "FL"}], self.M)

    def test_the_key_is_one_way_and_stable(self):
        r = {"name1": "Centro Uno", "name2": "", "street1": "1 Calle Sol", "city": "Adjuntas"}
        self.assertEqual(ca.fac_key(r), ca.fac_key({**r, "name1": "CENTRO  UNO"}))
        self.assertNotIn("centro", ca.fac_key(r))
        self.assertEqual(len(ca.fac_key(r)), 16)


class Historic(unittest.TestCase):
    M = Munis()

    def test_one_point_per_listing_and_municipio_and_the_island_counts_each_listing_once(self):
        rows = [nrhp("1"), nrhp("1", lon=-66.6), nrhp("2", typ="district", lon=-66.5), nrhp("2", typ="district", lon=-67.5, city="Aguada"),
                nrhp("3", status="Removed"), nrhp("4", layer="polygon", typ="site", cert="8/31/2022")]
        feats, n, island, notes = ca.historic(rows, self.M)
        self.assertEqual((n["72001"], n["72003"], island), (3, 1, 3))   # listing 2 counts in both municipios and once in Puerto Rico; 3 is not listed
        self.assertEqual(len(feats), 4)
        self.assertEqual((notes["more_points_in_the_same_municipio"], notes["not_listed"], notes["placed_from_polygon"]), (1, 1, 1))
        for f in feats:
            self.assertLessEqual(set(f["properties"]), PROPS["historic_places.geojson"])
        self.assertEqual({f["properties"]["type"] for f in feats}, {"Historic building", "Historic district", "Historic site"})
        self.assertIn("2022-08-31", {f["properties"].get("listed") for f in feats})

    def test_a_point_at_sea_goes_to_the_municipio_its_city_names_when_it_is_near(self):
        feats, n, island, notes = ca.historic([nrhp("5", lon=-66.5, lat=17.95), nrhp("6", lon=-66.5, lat=17.5)], self.M)
        self.assertEqual((n["72001"], island, notes["offshore_placed_by_its_city"], notes["outside_every_municipio"]), (1, 2, 1, 1))

    def test_puerto_rico_only(self):
        with self.assertRaises(SystemExit):
            ca.historic([nrhp("1", state="FLORIDA")], self.M)


class Residences(unittest.TestCase):
    """Decision 44 (2026-10-18): private residences, and listings whose name holds a street address or house number, are counted in their municipio but not
    drawn, and their names are published nowhere."""
    M = Munis()
    RV = {"public": {"10": {"name": "Casa Alcaldía de Adjuntas", "reason": "a city hall"}, "15": {"name": "Puente No. 6", "reason": "a bridge number"}},
          "residence": {"11": {"reason": "a family house"}}}
    STREET = re.compile(r"(?i)\bhouse at\b|\b(calle|street|avenida|avenue)\b|\bc\.\s|^\s*\d+\s+\w")   # a street word, 'House at', 'C. ' or a leading house number; other numbers need a reviewed reason (test_the_reviewed_list)

    def test_reviewed_residences_unreviewed_names_and_addresses_are_counted_not_drawn(self):
        rows = [nrhp("10", "Casa Alcaldía de Adjuntas"), nrhp("11", "Iglesia Y", lon=-66.4), nrhp("12", "Casa Fulano", lon=-66.3), nrhp("13", "House at 12 Luna Street", lon=-66.2),
                nrhp("14", "Puente Z", typ="structure", lon=-66.1), nrhp("15", "Puente No. 6", typ="structure", lon=-66.05), nrhp("16", "Calle Sol No. 3", lon=-67.5, city="Aguada")]
        feats, n, island, notes = ca.historic(rows, self.M, self.RV)
        self.assertEqual(sorted(f["properties"]["name"] for f in feats), ["Casa Alcaldía de Adjuntas", "Puente No. 6", "Puente Z"])
        self.assertEqual((n["72001"], n["72003"], island), (6, 1, 7))   # the counts include every listing
        self.assertEqual((notes["counted_not_drawn"], notes["counted_not_drawn_residences"], notes["counted_not_drawn_unreviewed"]), (4, 1, 3))
        self.assertEqual(notes["counted_not_drawn_by_municipio"], {"72001": 3, "72003": 1})
        self.assertEqual(notes["listings_drawn"], 3)
        self.assertNotIn("Fulano", json.dumps([feats, notes]))

    def test_the_patterns(self):
        for name in ("Casa Vives", "Acevedo, Rafael, House", "Residencia Heygler", "Brunet--Calaf Residence", "Villa Julita", "Chalet Amill", "Quinta Vendrell", "Casona Cesari"):
            self.assertRegex(name, ca.RESIDENCE_NAME, name)
        for name in ("House at 659 Concordia Street", "Calle Gonzalo Marin No. 61", "Gonzalo Marin 101", "Casa Delerme--Anduze No. 2"):
            self.assertRegex(name, ca.ADDRESS_NAME, name)
        for name in ("Villaran Bridge", "Casino de Ponce", "Faro de Arecibo", "Iglesia de la Santisma Trinidad", "Villalba"):
            self.assertIsNone(ca.RESIDENCE_NAME.search(name) or ca.ADDRESS_NAME.search(name), name)

    def test_the_reviewed_list(self):
        rv = ca.review()
        self.assertFalse(set(rv["public"]) & set(rv["residence"]))
        for ref, x in rv["public"].items():
            self.assertTrue(x.get("name") and x.get("reason"), ref)
        for ref, x in rv["residence"].items():
            self.assertEqual(set(x), {"reason"}, f"{ref}: a residence is listed by reference number and reason only (no name)")
            self.assertTrue(x["reason"], ref)
        for ref, x in rv["public"].items():   # a name with a number or a street word is drawn only when the number is not a street address
            if ca.ADDRESS_NAME.search(x["name"]):
                self.assertNotRegex(x["name"], self.STREET, ref)
                self.assertRegex(x["reason"], r"not a street address|a year", ref)
        p = ca.CACHE / "nps.json"
        if not p.exists():
            self.skipTest("no NPS cache on this machine")
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        unreviewed = sorted({r["NRIS_Refnum"] for r in rows if ca.residence(r, rv) == "unreviewed"})
        self.assertEqual(unreviewed, [], "listings whose name matches a residence or address pattern and are in neither list of nrhp_review.json: review them")
        refs = {r["NRIS_Refnum"] for r in rows}
        self.assertLessEqual(set(rv["public"]) | set(rv["residence"]), refs, "nrhp_review.json names a listing NPS no longer has")

    @staticmethod
    def public_names(rv):
        """The names a drawn, reviewed listing can carry: the one in nrhp_review.json, and the names NPS gives its other points (Hacienda La Esperanza's mill)."""
        names = {x["name"] for x in rv["public"].values()} | {n for x in rv["public"].values() for n in x.get("other_points", [])}   # other points are listed in the review so the check needs no cache (CI)
        p = ca.CACHE / "nps.json"
        if p.exists():
            names |= {fa.clean_name(r["RESNAME"]) for r in json.loads(p.read_text(encoding="utf-8"))["rows"] if r["NRIS_Refnum"] in rv["public"] and r.get("RESNAME")}
        return names

    def test_every_hacienda_is_reviewed(self):
        """A plantation's house can still be a home: every listing named Hacienda, Finca or Estancia (first word or not) is decided by hand in nrhp_review.json."""
        for name in ("Hacienda Buena Vista", "Santa Fulana Hacienda", "HACIENDA X"):
            self.assertRegex(name, ca.RESIDENCE_NAME, name)
        p = ca.CACHE / "nps.json"
        if not p.exists():
            self.skipTest("no NPS cache on this machine")
        rv = ca.review()
        reviewed = set(rv["public"]) | set(rv["residence"])
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        estates = {r["NRIS_Refnum"] for r in rows if re.search(r"(?i)\b(hacienda|finca|estancia)\b", r.get("RESNAME") or "")}
        self.assertGreaterEqual(len(estates), 12)
        self.assertEqual(sorted(estates - reviewed), [], "listings named Hacienda, Finca or Estancia that are not in nrhp_review.json: review them")
        public = self.public_names(rv)
        for f in json.loads((DATA / "historic_places.geojson").read_text(encoding="utf-8"))["features"]:
            name = f["properties"]["name"] or ""
            if re.search(r"(?i)\b(hacienda|finca|estancia)\b", name):
                self.assertIn(name, public, f"{name}: a hacienda is drawn without a public review")

    def test_no_drawn_point_is_a_residence(self):
        d = json.loads((DATA / "historic_places.geojson").read_text(encoding="utf-8"))
        rv = ca.review()
        public = self.public_names(rv)
        for f in d["features"]:
            name = f["properties"]["name"] or ""
            if ca.RESIDENCE_NAME.search(name) or ca.ADDRESS_NAME.search(name):
                self.assertIn(name, public, f"{name}: a residence or address-like name is drawn without a review")
        n = d["notes"]
        self.assertEqual(n["counted_not_drawn_unreviewed"], 0)
        self.assertEqual(n["listings_drawn"] + n["counted_not_drawn"], n["listings"])
        self.assertEqual(sum(n["counted_not_drawn_by_municipio"].values()), n["counted_not_drawn"])   # a residence has one point
        s = json.loads((DATA / "community_series.json").read_text(encoding="utf-8"))
        v = next(x for x in s["vars"] if x["key"] == "nrhp_places")
        self.assertEqual(list(v["years"].values())[0][-1], n["listings"], "the count includes the residences")

    def test_no_published_name_holds_a_street_address_or_house_number(self):
        d = json.loads((DATA / "historic_places.geojson").read_text(encoding="utf-8"))
        for f in d["features"]:
            self.assertNotRegex(f["properties"]["name"] or "", self.STREET)

    def test_residence_names_are_in_no_generated_file(self):
        p = ca.CACHE / "nps.json"
        if not p.exists():
            self.skipTest("no NPS cache on this machine")
        rv = ca.review()
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        names = {fa.clean_name(r["RESNAME"]) for r in rows if ca.residence(r, rv)}
        self.assertEqual(len({r["NRIS_Refnum"] for r in rows if ca.residence(r, rv)}), len(rv["residence"]))
        files = [DATA / f for f in ("historic_places.geojson", "community_series.json", "catalog.json", "dictionary.json", "dictionary_summary.json", "registry.json")]
        files += [ROOT / "site" / "js" / f for f in ("chat.js", "chatboot.js", "facilities.js", "facilities3d.js", "core/facilities.js", "twin3d.js", "access.js")] + sorted((ROOT / "site" / "i18n").glob("*.js"))
        for f in files:
            t = f.read_text(encoding="utf-8")
            for nm in names:
                for v in {nm, json.dumps(nm)[1:-1]}:
                    self.assertNotIn(v, t, f"{f.name} holds the name of a residence ({nm})")


class Townhalls(unittest.TestCase):
    M = Munis()

    def test_annexes_twice_mapped_halls_and_gaps(self):
        rows = [hall("w1"), hall("n2", lon=-66.5001, lat=18.2001), hall("w3", "Casa Alcaldía de Adjuntas - Anexo", lon=-66.6), hall("n4", None, lon=-66.7)]
        feats, notes = ca.townhalls(rows, self.M)
        self.assertEqual(notes["same_building_twice"], 1)
        self.assertEqual(sorted(f["properties"]["type"] for f in feats), ["City hall", "City hall", "City hall annex"])
        self.assertEqual(notes["municipios_without_a_city_hall_mapped"], ["Aguada"])   # gaps are reported, never filled
        self.assertEqual(notes["unnamed"], 1)
        for f in feats:
            self.assertLessEqual(set(f["properties"]), PROPS["town_halls.geojson"])

    def test_only_amenity_townhall(self):
        with self.assertRaises(SystemExit):
            ca.townhalls([hall("n1", amenity="police")], self.M)


class Published(unittest.TestCase):
    def test_point_files_hold_only_the_allowed_properties_and_no_contact_text(self):
        for f, src in (("historic_places.geojson", "nps_nrhp"), ("town_halls.geojson", "osm")):
            p = DATA / f
            if not p.exists():
                self.skipTest("not built")
            d = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(d.get("source"), src)
            self.assertTrue(d.get("vintage"), f)
            for x in d["features"]:
                self.assertLessEqual(set(x["properties"]), PROPS[f], f)
                self.assertTrue(re.fullmatch(r"72\d{3}", x["properties"]["geoid"]), f)
                lon, lat = x["geometry"]["coordinates"]
                self.assertTrue(-68 < lon < -65 and 17.8 < lat < 18.6, f"{f}: a point outside Puerto Rico")
                name = x["properties"]["name"] or ""
                self.assertNotRegex(name, PHONE_TEXT, f)
                self.assertNotRegex(name, EMAIL_TEXT, f)

    def test_the_town_hall_gaps_are_listed(self):
        d = json.loads((DATA / "town_halls.geojson").read_text(encoding="utf-8"))
        n = d["notes"]
        halls = {x["properties"]["geoid"] for x in d["features"] if x["properties"]["type"] == "City hall"}
        self.assertEqual(n["municipios_with_a_city_hall"], len(halls))
        self.assertEqual(len(n["municipios_without_a_city_hall_mapped"]) + len(halls), 78)

    def test_the_series_holds_counts_only(self):
        t = (DATA / "community_series.json").read_text(encoding="utf-8")
        d = json.loads(t)
        self.assertEqual([v["key"] for v in d["vars"]], ["nrhp_places", "ce_n", "ce_viviendas", "bh_all", "bh_su", "bh_mh", "bh_both"])
        self.assertEqual(d["geo"]["ids"][-1], "72")
        self.assertEqual(len(d["geo"]["ids"]), 79)
        V = {v["key"]: list(v["years"].values())[0] for v in d["vars"]}
        for k, vals in V.items():
            self.assertEqual(len(vals), 79, k)
            self.assertTrue(all(isinstance(x, int) and x >= 0 for x in vals), k)
        for i in range(79):
            self.assertEqual(V["bh_all"][i], V["bh_su"][i] + V["bh_mh"][i] + V["bh_both"][i], d["geo"]["names"][i])
        ce = json.loads((DATA / "comunidades.geojson").read_text(encoding="utf-8"))["features"]   # the Comunidades Especiales (2006): Puerto Rico = every community, the municipios add up to it
        self.assertEqual(V["ce_n"][-1], len(ce))
        self.assertEqual(sum(V["ce_n"][:-1]), len(ce))
        self.assertEqual(V["ce_viviendas"][-1], sum(f["properties"].get("viviendas") or 0 for f in ce))
        self.assertEqual(sum(V["ce_viviendas"][:-1]), V["ce_viviendas"][-1])
        self.assertGreaterEqual(V["bh_all"][-1], sum(V["bh_all"][:-1]))
        self.assertGreaterEqual(sum(V["nrhp_places"][:-1]), V["nrhp_places"][-1] - 1)   # a listing counts in each municipio it touches
        self.assertNotRegex(t, r"-6[5-7]\.\d{4,}", "a longitude")
        self.assertNotRegex(t, PHONE_TEXT)
        self.assertNotRegex(t, EMAIL_TEXT)
        self.assertEqual(sorted(d["sources"]), ["jp_comunidades_especiales", "nps_nrhp", "samhsa_nsumhss"])

    def test_non_prasa_water_counts_have_no_names(self):
        d = json.loads((DATA / "infrastructure_series.json").read_text(encoding="utf-8"))
        V = {v["key"]: list(v["years"].values())[0] for v in d["vars"]}
        for i in range(78):
            self.assertLessEqual(V["water_nonprasa"][i], V["water_systems"][i])
        n = d["notes"]["water"]["non_prasa"]
        self.assertEqual((V["water_nonprasa"][-1], V["water_nonprasa_pop"][-1]), (n["systems"], n["population_served"]))
        self.assertLessEqual(sum(V["water_nonprasa_pop"][:-1]), V["water_nonprasa_pop"][-1])   # a population is never split, so the municipios add up to less
        t = json.dumps(d, ensure_ascii=False)
        self.assertNotRegex(t, r"(?i)acued|comunidad|asoc\.|hacienda|finca")   # no system name
        cache = ROOT / "cache" / "infrastructure" / "echo_cws.pr.json"
        if cache.exists():
            self.assertNotIn("PWSName", cache.read_text(encoding="utf-8"))

    def test_skipped_sources_have_a_wanted_row_with_the_question(self):
        w = {x["id"]: x for x in json.loads((DATA / "wanted.json").read_text(encoding="utf-8"))["items"]}
        for k in ("non-prasa-locations", "samhsa-locator"):
            self.assertEqual(w[k]["status"], "blocked", k)
            self.assertTrue(w[k].get("question") and w[k].get("who_to_ask"), k)
        self.assertEqual(w["nrhp"]["status"], "live")


if __name__ == "__main__":
    unittest.main()
