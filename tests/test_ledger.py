"""Tests for the counts and the ledger behind the Data management page (ledger.py, registry.py; docs/data-management.md).

  python -m unittest tests.test_ledger

The counters run on small documents made here; the ledger on made-up builds (a rebuild with the same content keeps its dates, a content change moves
last_updated, first_published never moves); and the published files are checked against an independent count of four of them.
"""
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import contract  # noqa: E402
import ledger  # noqa: E402
import registry  # noqa: E402

DATA = ROOT / "site" / "data"
SITE = ROOT / "site"


def raw(doc):
    return json.dumps(doc).encode("utf-8")


def counts(name, doc):
    return ledger.count(name, raw(doc) if not isinstance(doc, bytes) else doc)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


_CUR = {}


def current():
    """ledger.current() of the published files, read once for all the tests (about 7 seconds)."""
    if not _CUR:
        _CUR.update(ledger.current())
    return _CUR


class Values(unittest.TestCase):
    def test_missing_is_null_absent_or_empty_text(self):
        self.assertEqual([ledger.leaves(x) for x in (None, "", 0, False, "a", 1.5)], [0, 0, 1, 1, 1, 1])
        self.assertEqual(ledger.leaves(float("nan")), 0)
        self.assertEqual(ledger.leaves([1, None, "", [2, 3]]), 3, "a list cell counts its non-null elements")
        self.assertEqual(ledger.leaves({"a": 1, "b": None}), 1)

    def test_an_object_in_a_record_is_a_group_of_fields(self):
        self.assertEqual(dict(ledger.flatten({"a": 1, "b": {"x": 2, "y": None}, "c": [1, 2]})), {"a": 1, "b.x": 2, "b.y": None, "c": [1, 2]})


class Adapters(unittest.TestCase):
    def test_geojson_features_are_records_and_geometry_is_vertices(self):
        doc = {"type": "FeatureCollection", "source": "metadata, not a value", "features": [
            {"type": "Feature", "properties": {"name": "A", "n": 1, "note": ""}, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
            {"type": "Feature", "properties": {"name": "B", "n": None, "note": None}, "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [0, 0]]], [[[2, 2], [3, 2], [2, 2]]]]}},
            {"type": "Feature", "properties": {"name": "C"}, "geometry": {"type": "Point", "coordinates": [5, 5]}},
        ]}
        self.assertEqual(counts("x.geojson", doc), {"records": 3, "fields": 2, "values": 4, "vertices": 4 + 6 + 1})

    def test_series_record_is_an_area_in_a_period_with_a_value(self):
        doc = {"built": "2026-10-19", "years": [2020, 2021], "geo": {"ids": ["72001", "72003", "72"], "names": ["A", "B", "Puerto Rico"]},
               "vars": [{"key": "a", "label": "metadata", "years": {"2020": [1, None, 3], "2021": [None, None, None]}, "moe": {"2020": [0.1, None, None]}},
                        {"key": "b", "years": {"2021": [None, 2, None]}},
                        {"key": "c", "definition": "no values"}],
               "notes": {"x": 1}, "sources": {"s": {"name": "n"}}}
        # records: (72001, 2020), (72, 2020), (72003, 2021); fields: a, a (margin of error), b; values: 2 + 1 + 1
        self.assertEqual(counts("bridges_series.json", doc), {"records": 3, "fields": 3, "values": 4, "vertices": None})

    def test_island_tables_join_the_island_record_of_their_year(self):
        doc = {"geo": {"ids": ["72001", "72"]}, "vars": [{"key": "a", "years": {"2020": [1, 2]}}], "tables": {"grapi": {"2020": [1.0, 2.0, 3.0], "2021": [4.0, 5.0, 6.0]}}}
        # records: (72001, 2020), (72, 2020), (72, 2021); fields: a, tables.grapi; values: 2 + 6
        self.assertEqual(counts("housing_series.json", doc), {"records": 3, "fields": 2, "values": 8, "vertices": None})

    def test_columnar_files_count_positions_with_a_value(self):
        doc = {"geo": {"ids": ["1", "2", "3"]}, "total": {"pop": [10, 0, None]}, "vars": {"f": {"label": {"en": "x", "es": "y"}, "pop": [1, None, None], "hu": [None, None, None]}}}
        self.assertEqual(counts("exposure_municipio.json", doc), {"records": 2, "fields": 2, "values": 3, "vertices": None})
        pa = {"n": 3, "near_m": 400, "ts_m": [1, 2, None], "tw_straight": [2, 7]}
        self.assertEqual(counts("place_access.json", pa), {"records": 3, "fields": 2, "values": 3, "vertices": None}, "a flag stored as a list of record positions counts each listed record; 7 is out of range")

    def test_a_point_pair_is_a_vertex_not_two_values(self):
        doc = [{"name": "a", "lat": 18.4, "lng": -66.1, "kind": "stop"}, {"name": "b", "withheld": "address", "kind": ""}]
        self.assertEqual(counts("transport.json", doc), {"records": 2, "fields": 3, "values": 4, "vertices": 1})

    def test_a_hurricane_track_fix_is_a_vertex_and_three_values(self):
        doc = [{"id": "AL01", "name": "A", "year": 2000, "track": [[-60, 15, "200001010000", 40, "TS"], [-61, 16, "200001010600", 45, "TS"]]}]
        self.assertEqual(counts("hurricanes.json", doc), {"records": 1, "fields": 4, "values": 3 + 6, "vertices": 2})

    def test_roads_bin_is_read_from_its_header(self):
        head = b"PRRD" + struct.pack("<IIII", 1, 10, 7, 25)
        self.assertEqual(ledger.count("roads.bin", head + b"\0" * 64), {"records": 7, "fields": 3, "values": 21, "vertices": 35})
        with self.assertRaises(ValueError):
            ledger.count("roads.bin", b"XXXX" + b"\0" * 20)

    def test_documentation_and_unknown_files_are_not_counted(self):
        none = {"records": None, "fields": None, "values": None, "vertices": None}
        self.assertEqual(ledger.count("dictionary.json", raw({"entries": [{"a": 1}]}), "documentation"), none)
        self.assertEqual(ledger.count("gazetteer.json", raw({"items": [[1, 2]]}), "index"), none)
        self.assertEqual(ledger.count("new_file.json", raw({"a": [1, 2]})), none)

    def test_every_published_data_file_has_an_adapter(self):
        cur = current()
        for name, p in contract.published_files(DATA):
            if name in ledger.NOT_LISTED or cur[name]["kind"] != "data":
                continue
            self.assertIsNotNone(ledger.family(name), f"{name}: add a counting adapter to ledger.py (docs/data-management.md, section 1)")
            c = cur[name]
            self.assertGreater(c["records"], 0, name)
            self.assertGreater(c["values"], 0, name)
            self.assertLessEqual(c["fields"], c["values"], name)


class IndependentCount(unittest.TestCase):
    """Four files counted again here without ledger.py's helpers (the method of docs/data-management.md, section 2)."""

    def got(self, name):
        c = current()[name]
        return c["records"], c["fields"], c["values"], c["vertices"]

    @staticmethod
    def present(v):
        return v is not None and v != ""

    def test_municipalities(self):
        m = load(DATA / "municipalities.json")
        fields, vals = set(), 0
        for r in m.values():
            for k, v in r.items():
                for kk, vv in (v.items() if isinstance(v, dict) else [(None, v)]):
                    if self.present(vv):
                        fields.add((k, kk))
                        vals += 1
        self.assertEqual(self.got("municipalities.json"), (len(m), len(fields), vals, None))

    def test_barrios(self):
        b = load(DATA / "barrios.geojson")
        fields, vals, vtx = set(), 0, 0
        for f in b["features"]:
            for k, v in f["properties"].items():
                if self.present(v):
                    fields.add(k)
                    vals += 1
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            vtx += sum(len(ring) for poly in polys for ring in poly)
        self.assertEqual(self.got("barrios.geojson"), (len(b["features"]), len(fields), vals, vtx))

    def test_places(self):
        p = load(DATA / "places.json")
        fields, vals, vtx = set(), 0, 0
        for r in p:
            vtx += r.get("lat") is not None and r.get("lng") is not None
            for k, v in r.items():
                if k not in ("lat", "lng") and self.present(v):
                    fields.add(k)
                    vals += 1
        self.assertEqual(self.got("places.json"), (len(p), len(fields), vals, vtx))

    def test_acs_barrio(self):
        a = load(DATA / "acs_barrio.json")
        keys, fields, vals = set(), set(), 0
        for v in a["vars"]:
            for part in ("years", "moe"):
                for y, arr in (v.get(part) or {}).items():
                    for i, x in enumerate(arr):
                        if x is not None:
                            keys.add((i, y))
                            fields.add((v["key"], part))
                            vals += 1
        self.assertEqual(self.got("acs_barrio.json"), (len(keys), len(fields), vals, None))
        self.assertEqual(len(keys), len(a["geo"]["ids"]) * len(a["windows"]), "every barrio has a value in every window")


class ContentHash(unittest.TestCase):
    def test_a_new_build_date_is_not_new_content(self):
        a = {"built": "2026-10-01", "meta": {"built": "2026-10-01", "generated_at": "x"}, "vars": [1, 2]}
        b = {"built": "2026-10-19", "meta": {"built": "2026-10-19", "generated_at": "y"}, "vars": [1, 2]}
        self.assertEqual(ledger.content_hash("f.json", raw(a)), ledger.content_hash("f.json", raw(b)))

    def test_a_changed_value_is_new_content(self):
        self.assertNotEqual(ledger.content_hash("f.json", raw({"vars": [1, 2]})), ledger.content_hash("f.json", raw({"vars": [1, 3]})))

    def test_a_built_field_inside_a_record_is_data(self):
        self.assertNotEqual(ledger.content_hash("f.json", raw([{"built": 1990}])), ledger.content_hash("f.json", raw([{"built": 1991}])))

    def test_key_order_spacing_and_line_ends_do_not_matter(self):
        self.assertEqual(ledger.content_hash("f.json", b'{"a": 1,\r\n "b": [1, 2]}'), ledger.content_hash("f.json", b'{"b":[1,2],"a":1}'))
        self.assertEqual(ledger.lf(b"a\r\nb", "f.json"), b"a\nb")
        self.assertEqual(ledger.lf(b"a\r\nb", "roads.bin"), b"a\r\nb", "a binary file is hashed and sized as it is")


def described(**files):
    """A made-up build: {file: (hash, records, values, bytes)}."""
    return {n: {"kind": "data", "hash": h, "bytes": b, "records": r, "fields": 1, "values": v, "vertices": None} for n, (h, r, v, b) in files.items()}


class Ledger(unittest.TestCase):
    def setUp(self):
        self.led, _ = ledger.update(ledger.empty_ledger(), described(a=("h1", 10, 20, 100), b=("h2", 5, 5, 50)), 3, "2026-10-01")

    def test_a_new_file_gets_both_dates(self):
        a = self.led["files"]["a"]
        self.assertEqual((a["first_published"], a["last_updated"], a["versions"]), ("2026-10-01", "2026-10-01", 1))

    def test_a_rebuild_with_the_same_content_keeps_its_dates(self):
        again, changed = ledger.update(self.led, described(a=("h1", 10, 20, 100), b=("h2", 5, 5, 50)), 3, "2026-10-19")
        self.assertEqual(changed, [])
        self.assertEqual(again, self.led, "nothing moves: no date, no version, no history row")

    def test_a_content_change_moves_last_updated_and_never_first_published(self):
        led, changed = ledger.update(self.led, described(a=("h9", 11, 22, 110), b=("h2", 5, 5, 50)), 3, "2026-10-05")
        self.assertEqual(changed, ["a"])
        a, b = led["files"]["a"], led["files"]["b"]
        self.assertEqual((a["first_published"], a["last_updated"], a["versions"], a["records"]), ("2026-10-01", "2026-10-05", 2, 11))
        self.assertEqual((b["first_published"], b["last_updated"], b["versions"]), ("2026-10-01", "2026-10-01", 1))
        led2, _ = ledger.update(led, described(a=("h10", 11, 22, 110), b=("h2", 5, 5, 50)), 3, "2026-10-09")
        self.assertEqual(led2["files"]["a"]["first_published"], "2026-10-01")
        self.assertEqual(led2["files"]["a"]["versions"], 3)

    def test_a_size_change_without_new_content_moves_no_date(self):
        led, changed = ledger.update(self.led, described(a=("h1", 10, 20, 104), b=("h2", 5, 5, 50)), 3, "2026-10-05")
        self.assertEqual(changed, [])
        self.assertEqual(led["files"]["a"]["last_updated"], "2026-10-01")
        self.assertEqual(led["files"]["a"]["bytes"], 104, "the size follows the file")

    def test_a_removed_file_keeps_its_first_date_when_it_comes_back(self):
        gone, changed = ledger.update(self.led, described(a=("h1", 10, 20, 100)), 3, "2026-10-03")
        self.assertEqual(changed, ["b"])
        self.assertEqual(gone["removed"]["b"]["removed"], "2026-10-03")
        back, _ = ledger.update(gone, described(a=("h1", 10, 20, 100), b=("h7", 5, 5, 50)), 3, "2026-10-08")
        self.assertEqual((back["files"]["b"]["first_published"], back["files"]["b"]["last_updated"], back["files"]["b"]["versions"]), ("2026-10-01", "2026-10-08", 2))
        self.assertNotIn("b", back["removed"])

    def test_the_history_has_a_row_for_each_date_the_totals_changed(self):
        h = self.led["history"]
        self.assertEqual(h, [{"date": "2026-10-01", "files": 2, "bytes": 150, "records": 15, "fields": 2, "values": 25, "items": 3}])
        led, _ = ledger.update(self.led, described(a=("h9", 12, 30, 120), b=("h2", 5, 5, 50)), 3, "2026-10-05")
        led, _ = ledger.update(led, described(a=("h8", 13, 31, 121), b=("h2", 5, 5, 50)), 3, "2026-10-05")
        self.assertEqual([r["date"] for r in led["history"]], ["2026-10-01", "2026-10-05"], "a second build on a day replaces that day's row")
        self.assertEqual(led["history"][-1]["values"], 36)
        led, _ = ledger.update(led, described(a=("h8", 13, 31, 121), b=("h2", 5, 5, 50)), 4, "2026-10-06")
        self.assertEqual(led["history"][-1], {"date": "2026-10-06", "files": 2, "bytes": 171, "records": 18, "fields": 2, "values": 36, "items": 4}, "a new dictionary item is a change of the totals")

    def test_totals_count_data_files_and_size_every_file(self):
        cur = described(a=("h1", 10, 20, 100))
        cur["d.json"] = {"kind": "documentation", "hash": "x", "bytes": 7, "records": None, "fields": None, "values": None, "vertices": None, "items": 3}
        self.assertEqual(ledger.totals(cur, 9), {"files": 2, "bytes": 107, "records": 10, "fields": 1, "values": 20, "items": 9})

    def test_the_check_reports_stale_files_and_never_the_date(self):
        cur = described(a=("h1", 10, 20, 100), b=("h2", 5, 5, 50))
        self.assertEqual(ledger.problems(self.led, cur, 3), [])
        stale = ledger.problems(self.led, described(a=("h9", 10, 20, 100), b=("h2", 5, 5, 50)), 3)
        self.assertTrue(any("a: hash" in p for p in stale), stale)
        self.assertTrue(any(p.startswith("c is published") for p in ledger.problems(self.led, {**cur, **described(c=("h3", 1, 1, 1))}, 3)))


class PublishedLedger(unittest.TestCase):
    """The committed ledger and registry describe the committed files (the tests job also runs python registry.py --check)."""

    @classmethod
    def setUpClass(cls):
        cls.cur = current()
        cls.led = ledger.load()
        cls.reg = load(DATA / "registry.json")

    def test_the_ledger_is_current(self):
        self.assertEqual(ledger.problems(self.led, self.cur, ledger.documented_items()), [], "run python registry.py and commit dictionary_src/data_ledger.json")

    def test_the_registry_is_what_the_files_and_the_ledger_give(self):
        self.assertEqual(registry.comparable(self.reg), registry.comparable(registry.build(self.cur, self.led)), "run python registry.py and commit site/data/registry.json")

    def test_dates_are_in_order_and_backfilled_from_the_first_publication(self):
        for name, f in self.led["files"].items():
            self.assertRegex(f["first_published"], r"^\d{4}-\d{2}-\d{2}$", name)
            self.assertLessEqual(f["first_published"], f["last_updated"], name)
            self.assertGreaterEqual(f["versions"], 1, name)
        self.assertEqual(self.led["files"]["flood.geojson"]["first_published"], "2026-10-01")
        self.assertEqual(self.led["files"]["wcrp_social.json"]["first_published"], "2026-10-19")
        dates = [h["date"] for h in self.led["history"]]
        self.assertEqual(dates, sorted(set(dates)))
        self.assertEqual(dates[0], "2026-10-01")

    def test_the_totals_add_up(self):
        t, files = self.reg["totals"], self.reg["files"]
        data = [f for f in files if f["kind"] == "data"]
        self.assertEqual(t["files"], len(files))
        self.assertEqual(t["bytes"], sum(f["bytes"] for f in files))
        self.assertEqual(t["bytes"], self.reg["total_bytes"])
        for k in ("records", "fields", "values"):
            self.assertEqual(t[k], sum(f[k] for f in data), k)
        self.assertEqual(t["counted_files"], len(data))
        self.assertEqual({k: self.reg["history"][-1][k] for k in ledger.TOTAL_KEYS}, {k: t[k] for k in ledger.TOTAL_KEYS})
        self.assertNotIn("registry.json", {f["file"] for f in files})
        self.assertTrue(all(f["records"] is None for f in files if f["kind"] != "data"))

    def test_the_open_reviews_are_shown_with_their_reason(self):
        recs = {r["file"]: r for r in contract.load_datasets()["datasets"]}
        want = sum(1 for r in recs.values() for rv in r.get("review") or [] if rv.get("status") == "open")
        shown = [(f["file"], o) for f in self.reg["files"] for o in f["review"].get("open", [])]
        self.assertEqual(len(shown), want)
        for f, o in shown:
            self.assertTrue(o["summary"] and o["summary"]["en"] and o["summary"]["es"], f)
            self.assertNotRegex(o["summary"]["es"], r"CDBG|LIHTC|WCRP|\bHUD\b", f"{f}: Spanish about federal grant work waits for Finance and Compliance (held_for_review.json)")
        rows = {f["file"]: f["review"] for f in self.reg["files"]}
        self.assertEqual(rows["housing.json"]["status"], "open")
        self.assertIn("federal-grant", rows["economy_series.json"]["flags"])
        self.assertEqual(rows["wcrp_rvi_barrio.json"]["status"], "cleared")
        self.assertEqual(rows["wcrp_rvi_barrio.json"]["cleared"], "2026-10-19")
        self.assertIn("licence-unstated", rows["wcrp_rvi_barrio.json"]["flags"])
        self.assertIn("counts-only", rows["places.json"]["flags"])
        self.assertEqual(rows["flood.geojson"]["status"], "none")
        self.assertEqual(rows["transport.json"]["status"], "unstated")

    def test_a_restrictive_licence_class_names_the_sources_that_set_it(self):
        # a file takes the most restrictive class of its sources: "License not stated" must never read as "none of its sources has a license"
        srcs, aliases = registry.sources()
        for f in self.reg["files"]:
            if f.get("licence_class") in ("unstated", "licensed-not-open"):
                got = f["review"].get("licence_from")
                self.assertTrue(got, f"{f['file']}: no source with the class {f['licence_class']}")
                for x in got:
                    self.assertEqual(srcs[x["id"]]["licence_class"], f["licence_class"], f["file"])
                    self.assertTrue(x["en"] and x["es"], x["id"])
            else:
                self.assertNotIn("licence_from", f["review"], f["file"])
        rows = {f["file"]: f["review"] for f in self.reg["files"]}
        self.assertEqual([x["id"] for x in rows["barrios.geojson"]["licence_from"]], ["muni_gtfs"], "barrios.geojson: only the municipal GTFS feeds state no license")
        self.assertEqual(rows["barrios.geojson"]["licence_from"][0]["es"], "GTFS municipales")
        unstated = [f for f in self.reg["files"] if f.get("licence_class") == "unstated"]
        self.assertEqual(len(unstated), sum(1 for f in self.reg["files"] if f["review"]["status"] == "unstated" or "licence-unstated" in f["review"]["flags"]))

    def test_what_is_not_published_is_counts_only(self):
        w = {x["id"]: x for x in self.reg["withheld"]}
        self.assertEqual(set(w), {"places_not_drawn", "not_tourism", "hrsa_sites", "shelters", "nrhp_private_homes", "public_housing_approximate", "lihtc_not_drawn", "treatment_facilities", "nonprofits"})
        for x in w.values():
            self.assertIsInstance(x["count"], int, x["id"])
            self.assertTrue(set(x) <= {"id", "count", "of", "parts", "file", "doc", "wanted_status"}, x["id"])
            self.assertTrue((DATA / x["file"]).exists(), x["id"])
        places = load(DATA / "places.json")
        self.assertEqual(w["places_not_drawn"]["count"], sum(1 for p in places if p.get("withheld")))
        self.assertEqual(w["shelters"]["count"], 0)
        ids = {e["id"] for e in load(DATA / "dictionary.json")["entries"]}
        for x in w.values():
            self.assertIn(x["doc"], ids, x["id"])


class Registry(unittest.TestCase):
    def test_review_status_order(self):
        rv = lambda **k: {"type": "licence", "note": "n", **k}
        self.assertEqual(registry.review_of({"licence_class": "open", "review": []}), {"status": "none", "flags": []})
        self.assertEqual(registry.review_of({"licence_class": "unstated", "review": []})["status"], "unstated")
        c = registry.review_of({"licence_class": "unstated", "review": [rv(status="cleared", date="2026-10-18"), rv(status="cleared", date="2026-10-19")]})
        self.assertEqual((c["status"], c["cleared"], c["flags"]), ("cleared", "2026-10-19", ["licence-unstated"]))
        o = registry.review_of({"licence_class": "licensed-not-open", "flags": ["federal-grant"], "review": [rv(status="cleared", date="2026-10-18"), rv(status="open", summary={"en": "x", "es": "y"})]})
        self.assertEqual((o["status"], o["open"], o["flags"]), ("open", [{"type": "licence", "summary": {"en": "x", "es": "y"}}], ["federal-grant", "licensed-not-open"]))
        srcs = ({"a": {"licence_class": "open", "name": "A"}, "b": {"licence_class": "unstated", "name": "B long", "short": {"en": "B", "es": "Be"}}, "c": {"licence_class": "unstated", "name": "C"}}, {"old_b": "b"})
        u = registry.review_of({"licence_class": "unstated", "sources": ["a", "old_b", "c", "b"], "review": []}, srcs)
        self.assertEqual(u["licence_from"], [{"id": "b", "en": "B", "es": "Be"}, {"id": "c", "en": "C", "es": "C"}], "the sources of the file's class, once each, aliases resolved, the short name when there is one")

    def test_only_the_date_and_compressed_sizes_changed_is_no_change(self):
        a = {"built": "2026-10-01", "total_bytes": 5, "files": [{"file": "a", "bytes": 5, "gzip_bytes": 3}]}
        b = {"built": "2026-10-19", "total_bytes": 5, "files": [{"file": "a", "bytes": 5, "gzip_bytes": 4}]}
        self.assertEqual(registry.comparable(a), registry.comparable(b))
        self.assertNotEqual(registry.comparable(a), registry.comparable({**b, "total_bytes": 6}))


class Contract(unittest.TestCase):
    def test_flags_and_review_fields_are_checked(self):
        reg = {"version": 1, "domains": [{"id": "housing", "parent": None, "order": 1, "name": {"es": "Vivienda", "en": "Housing"}, "description": {"es": "d", "en": "d"}, "icon": "home", "accent": "--fpr-blue", "status": "active", "system": False, "examples": {"es": ["?"], "en": ["?"]}, "headline": None}]}
        src = {"s": {"licence_class": "open"}}

        def errors(**rec):
            r = {"id": "x", "file": "x.json", "title": {"en": "X", "es": "X"}, "domains": ["housing"], "geography": {"level": "none"}, "time": {"type": "static"}, "sources": ["s"],
                 "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": [], **rec}
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "x.json").write_text("{}", encoding="utf-8")
                P, _ = contract.validate_datasets({"version": 1, "datasets": [r]}, reg, src, {}, Path(d), scan=False)
            return [(p[0], p[3]) for p in P if p[1] == "datasets.json"]
        self.assertEqual(errors(), [])
        self.assertTrue(any(s == "error" and "federal-grant" in m for s, m in errors(flags=["federal-grant"])))
        self.assertTrue(any(s == "error" and "flags must be" in m for s, m in errors(flags=["secret"])))
        ok = errors(flags=["federal-grant"], review=[{"type": "compliance", "status": "open", "note": "n", "summary": {"en": "a", "es": "b"}}])
        self.assertEqual(ok, [])
        self.assertTrue(any(s == "warn" and "no summary" in m for s, m in errors(review=[{"type": "pii", "status": "open", "note": "n"}])))
        self.assertTrue(any(s == "warn" and "no date" in m for s, m in errors(review=[{"type": "pii", "status": "cleared", "note": "n"}])))
        self.assertTrue(any(s == "error" and "YYYY-MM-DD" in m for s, m in errors(review=[{"type": "pii", "status": "cleared", "note": "n", "date": "19/10/2026"}])))


class Page(unittest.TestCase):
    def test_the_page_is_public_read_only_routed_budgeted_and_translated(self):
        html = (SITE / "data-management.html").read_text(encoding="utf-8")
        # public and indexable (HANDOFF decision 56(a), 2026-10-20): no robots tag, and the canonical link and share tags of the other pages
        self.assertNotIn('name="robots"', html, "the Data management page is open to search engines (HANDOFF decision 56(a))")
        url = "https://observatory.foundationpr.org/data-management.html"
        self.assertIn(f'<link rel="canonical" href="{url}">', html)
        self.assertIn(f'<meta property="og:url" content="{url}">', html)
        self.assertIn('<meta name="twitter:card" content="summary">', html)
        # read-only, and it says so in both languages (the Spanish comes from the page's own scope, not common.js)
        ro = "This page is generated automatically from the observatory's repository; only the Foundation for Puerto Rico team can change the data, through reviewed changes."
        self.assertIn(f'<p class="lede" id="dmReadOnly">{ro}</p>', html)
        es = json.loads((ROOT / "i18n_src" / "es" / "datamgmt.json").read_text(encoding="utf-8"))
        self.assertIn("solo el equipo de Foundation for Puerto Rico puede modificar los datos", es[ro])
        self.assertNotIn(ro, json.loads((ROOT / "i18n_src" / "es" / "common.json").read_text(encoding="utf-8")))
        self.assertNotRegex(html, r"<(form|textarea)\b|contenteditable", "no editing control on the page")
        # the other pages stay as they are (decision 13; WCRP while its marker is on, decision 51)
        for page, tag in (("dictionary.html", "noindex, follow"), ("housing.html", "noindex, follow"), ("profile.html", "noindex, follow"), ("wcrp.html", "noindex, nofollow")):
            self.assertIn(f'<meta name="robots" content="{tag}">', (SITE / page).read_text(encoding="utf-8"), page)
        self.assertIn('data-page="datamgmt"', html)
        routes = json.loads((ROOT / "dictionary_src" / "routes.json").read_text(encoding="utf-8"))["routes"]
        self.assertEqual(routes["datamgmt"]["page"], "data-management.html")
        self.assertEqual(routes["datamgmt"]["first"], ["registry.json"])
        pages = json.loads((ROOT / "i18n_src" / "pages.json").read_text(encoding="utf-8"))["pages"]
        self.assertEqual(pages["datamgmt"]["file"], "data-management.html")
        self.assertTrue((SITE / "i18n" / "es.datamgmt.js").exists())
        self.assertIn("name: 'datamgmt'", (ROOT / "tests" / "browser" / "throttle.js").read_text(encoding="utf-8"))
        for sec in ("files", "growth", "withheld", "definitions"):
            self.assertIn(f'id="{sec}"', html)

    def test_the_dictionary_links_to_it_and_its_old_anchor_still_lands(self):
        d = (SITE / "dictionary.html").read_text(encoding="utf-8")
        self.assertIn('id="files"', d, "dictionary.html#files still lands on the files section")
        self.assertIn('href="data-management.html', d)
        self.assertNotIn('id="filesTbl"', d)
        for page in ("about.html", "3d.html"):   # the map's About text is about.html since 2026-11-25
            self.assertIn('href="data-management.html"', (SITE / page).read_text(encoding="utf-8"), f"the About text of {page} names the page")
        self.assertNotIn('href="data-management.html"', re.search(r'<nav class="views".*?</nav>', (SITE / "index.html").read_text(encoding="utf-8"), re.S).group(0), "no top-bar button")

    def test_the_glossary_defines_its_terms(self):
        g = {t["term"]: t for t in load(ROOT / "dictionary_src" / "glossary.json")}
        for term in ("Record", "Field", "Value (data point)", "Vertex", "First published", "Last updated", "Compliance review"):
            self.assertIn(term, g)
            self.assertTrue(g[term]["plain_es"] and g[term]["source"]["url"].startswith("https://"), term)


if __name__ == "__main__":
    unittest.main()
