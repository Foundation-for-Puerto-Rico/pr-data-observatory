"""Tests for the domain registry and data contract validator (contract.py).

  python -m unittest discover -s tests -v

Each test builds a tiny registry, source list and data folder in a temporary directory and checks that a violation is caught
(or, for the 'clean' cases, that nothing is reported), so a change to the validator cannot silently weaken the contract.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import contract  # noqa: E402

TOKENS = {"--fpr-blue", "--fpr-red"}


def domain(id_, parent=None, order=10, system=False, **kw):
    d = {"id": id_, "parent": parent, "order": order,
         "name": {"es": f"{id_} es", "en": f"{id_} en"}, "description": {"es": "descripción", "en": "description"},
         "icon": "home", "accent": "--fpr-blue", "headline": None,
         "examples": {"es": [] if system else ["¿Qué?"], "en": [] if system else ["What?"]}, "status": "active", "system": system}
    d.update(kw)
    return d


def registry(*ds):
    return {"version": 1, "domains": list(ds) or [domain("housing"), domain("system", system=True, order=900)]}


def problems(fn, *a, **k):
    out = fn(*a, **k)
    return out[0] if isinstance(out, tuple) else out


def errors(ps):
    return [p for p in ps if p[0] == "error"]


def messages(ps, sev="error"):
    return " | ".join(p[3] for p in ps if p[0] == sev)


class RegistryTests(unittest.TestCase):
    def test_clean_registry_passes(self):
        self.assertEqual(errors(contract.validate_registry(registry(), None, TOKENS)), [])

    def test_duplicate_id(self):
        r = registry(domain("housing"), domain("housing", order=20))
        self.assertIn("duplicate id", messages(contract.validate_registry(r, None, TOKENS)))

    def test_missing_spanish_name(self):
        d = domain("housing")
        d["name"]["es"] = ""
        self.assertIn("name needs", messages(contract.validate_registry(registry(d), None, TOKENS)))

    def test_subdomain_parent_must_match_prefix(self):
        r = registry(domain("economy"), domain("economy.visitor", parent="housing"))
        self.assertIn("parent must be", messages(contract.validate_registry(r, None, TOKENS)))

    def test_parent_must_exist(self):
        r = registry(domain("economy.visitor", parent="economy"))
        self.assertIn("does not exist", messages(contract.validate_registry(r, None, TOKENS)))

    def test_top_level_cannot_have_parent(self):
        r = registry(domain("economy"), domain("health", parent="economy"))
        self.assertIn("parent null", messages(contract.validate_registry(r, None, TOKENS)))

    def test_unknown_accent_token(self):
        d = domain("housing", accent="--nope")
        self.assertIn("not defined in site/css/twin.css", messages(contract.validate_registry(registry(d), None, TOKENS)))

    def test_headline_variable_must_exist(self):
        d = domain("housing", headline={"variable": "housing.nothing", "norm": "value"})
        self.assertIn("not a dictionary entry", messages(contract.validate_registry(registry(d), {"housing.rent"}, TOKENS)))
        ok = domain("housing", headline={"variable": "housing.rent", "norm": "value"})
        self.assertEqual(errors(contract.validate_registry(registry(ok), {"housing.rent"}, TOKENS)), [])

    def test_data_domain_needs_examples_in_both_languages(self):
        d = domain("housing")
        d["examples"]["es"] = []
        self.assertIn("at least one example", messages(contract.validate_registry(registry(d), None, TOKENS)))

    def test_system_domain_needs_no_examples(self):
        self.assertEqual(errors(contract.validate_registry(registry(domain("system", system=True)), None, TOKENS)), [])

    def test_duplicate_names_rejected(self):
        a, b = domain("housing"), domain("health", order=20)
        b["name"]["en"] = "Housing EN".replace("EN", "en")          # same as housing's "housing en"
        self.assertIn("already used", messages(contract.validate_registry(registry(a, b), None, TOKENS)))

    def test_legacy_name_must_point_to_a_domain(self):
        r = registry()
        r["legacy_names"] = {"Old": "nowhere"}
        self.assertIn("not a domain", messages(contract.validate_registry(r, None, TOKENS)))

    def test_bad_status(self):
        d = domain("housing", status="empty")
        self.assertIn("status must be", messages(contract.validate_registry(registry(d), None, TOKENS)))


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.reg = registry(domain("housing"), domain("system", system=True, order=900), domain("system.docs", parent="system", system=True, order=920))
        self.sources = {"census": {"licence_class": "open"}, "osm": {"licence_class": "open-with-conditions"}, "jp": {"licence_class": "unstated"},
                        "study": {"licence_class": "licensed-not-open"}}
        self.aliases = {"acs": "census"}
        (self.dir / "municipios.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"GEOID": "72001", "municipality": "Adjuntas"}},
            {"type": "Feature", "properties": {"GEOID": "72003", "municipality": "Aguada"}}]}), encoding="utf-8")
        (self.dir / "rent.json").write_text(json.dumps({"years": [2010, 2011, 2012], "geo": {"ids": ["72001", "72003", "72"]}}), encoding="utf-8")
        self.rec = {"id": "rent", "file": "rent.json", "title": {"en": "Rent", "es": "Alquiler"}, "domains": ["housing"],
                    "geography": {"level": "municipio", "key": "geo.ids"}, "time": {"type": "period", "first": 2010, "last": 2012, "years_path": "years"},
                    "sources": ["census"], "licence_class": "open", "cadence": "annual", "tier": "small", "published": "2026-10", "review": []}
        self.geo_rec = {"id": "municipios", "file": "municipios.geojson", "title": {"en": "M", "es": "M"}, "domains": ["system.docs"],
                        "geography": {"level": "municipio", "key": "field:GEOID"}, "time": {"type": "static"}, "sources": ["census"],
                        "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": []}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, *recs):
        ds = {"version": 1, "datasets": [copy.deepcopy(r) for r in (recs or (self.rec, self.geo_rec))]}
        return contract.validate_datasets(ds, self.reg, self.sources, self.aliases, self.dir, True)

    def test_clean_dataset_passes(self):
        ps, reviews = self.check()
        self.assertEqual(errors(ps), [], ps)
        self.assertEqual(reviews, [])

    def test_unregistered_file_fails(self):
        (self.dir / "extra.json").write_text("{}", encoding="utf-8")
        self.assertIn("no contract record", messages(self.check()[0]))

    def test_missing_file_fails(self):
        r = dict(self.rec, file="gone.json")
        self.assertIn("not in site/data", messages(self.check(r, self.geo_rec)[0]))

    def test_unknown_domain_fails(self):
        r = dict(self.rec, domains=["housing", "nowhere"])
        self.assertIn("not in the registry", messages(self.check(r, self.geo_rec)[0]))

    def test_unknown_source_fails(self):
        r = dict(self.rec, sources=["census", "mystery"])
        self.assertIn("unknown source id 'mystery'", messages(self.check(r, self.geo_rec)[0]))

    def test_source_alias_resolves(self):
        r = dict(self.rec, sources=["acs"])
        self.assertEqual(errors(self.check(r, self.geo_rec)[0]), [])

    def test_licence_class_cannot_be_laxer_than_sources(self):
        r = dict(self.rec, sources=["census", "jp"], licence_class="open")
        self.assertIn("less restrictive", messages(self.check(r, self.geo_rec)[0]))
        r = dict(self.rec, sources=["census", "jp"], licence_class="unstated")
        self.assertEqual(errors(self.check(r, self.geo_rec)[0]), [])

    def test_licensed_not_open_needs_a_licence_review(self):
        r = dict(self.rec, sources=["study"], licence_class="licensed-not-open")
        self.assertIn("needs a 'licence' review", messages(self.check(r, self.geo_rec)[0]))
        r["review"] = [{"type": "licence", "status": "open", "note": "permission needed", "fields": ["x"]}]
        ps, reviews = self.check(r, self.geo_rec)
        self.assertEqual(errors(ps), [])
        self.assertEqual(len(reviews), 1)

    def test_invalid_enums(self):
        for field, bad in (("cadence", "whenever"), ("tier", "huge"), ("licence_class", "free")):
            r = dict(self.rec, **{field: bad})
            self.assertTrue(errors(self.check(r, self.geo_rec)[0]), field)
        r = dict(self.rec, time={"type": "sometimes"})
        self.assertIn("time.type", messages(self.check(r, self.geo_rec)[0]))
        r = dict(self.rec, geography={"level": "county", "key": "x"})
        self.assertIn("geography.level", messages(self.check(r, self.geo_rec)[0]))

    def test_keyed_level_needs_key(self):
        r = dict(self.rec, geography={"level": "tract"})
        self.assertIn("geography.key is required", messages(self.check(r, self.geo_rec)[0]))

    def test_unmatched_join_keys_fail_above_one_percent(self):
        (self.dir / "rent.json").write_text(json.dumps({"years": [2010], "geo": {"ids": ["72001", "99999"]}}), encoding="utf-8")
        r = dict(self.rec, time={"type": "period", "first": 2010, "last": 2010, "years_path": "years"})
        self.assertIn("do not resolve", messages(self.check(r, self.geo_rec)[0]))

    def test_few_unmatched_join_keys_only_warn(self):
        ids = ["72001"] * 199 + ["99999"]
        (self.dir / "rent.json").write_text(json.dumps({"years": [2010, 2011, 2012], "geo": {"ids": ids}}), encoding="utf-8")
        ps, _ = self.check()
        self.assertEqual(errors(ps), [])
        self.assertIn("do not resolve", messages(ps, "warn"))

    def test_year_range_must_match_file(self):
        r = dict(self.rec, time={"type": "period", "first": 2000, "last": 2012, "years_path": "years"})
        self.assertIn("time.first is 2000", messages(self.check(r, self.geo_rec)[0]))

    def test_size_tier_is_enforced(self):
        (self.dir / "rent.json").write_text(json.dumps({"years": [2010, 2011, 2012], "geo": {"ids": ["72001"]}, "pad": "x" * (contract.MB + 10)}), encoding="utf-8")
        self.assertIn("over the 'small' budget", messages(self.check()[0]))

    def test_personal_data_column_fails_unless_reviewed(self):
        (self.dir / "places.json").write_text(json.dumps([{"name": "Cafe", "municipality": "Adjuntas", "phone": "x"}]), encoding="utf-8")
        place = {"id": "places", "file": "places.json", "title": {"en": "P", "es": "P"}, "domains": ["housing"], "geography": {"level": "point", "key": "field:municipality", "joins_to": "municipio"},
                 "time": {"type": "snapshot"}, "sources": ["osm"], "licence_class": "open-with-conditions", "cadence": "snapshot", "tier": "small", "published": "2026-10", "review": []}
        self.assertIn("column 'phone'", messages(self.check(self.rec, self.geo_rec, place)[0]))
        place["review"] = [{"type": "pii", "status": "open", "fields": ["phone"], "note": "to be removed"}]
        ps, reviews = self.check(self.rec, self.geo_rec, place)
        self.assertEqual(errors(ps), [], ps)
        self.assertEqual(len(reviews), 1)

    def test_owner_columns_in_housing_variables_are_not_personal_data(self):
        (self.dir / "places.json").write_text(json.dumps([{"name": "Cafe", "municipality": "Adjuntas", "owner_cost_burden_pct": 3}]), encoding="utf-8")
        place = {"id": "places", "file": "places.json", "title": {"en": "P", "es": "P"}, "domains": ["housing"], "geography": {"level": "point", "key": "field:municipality", "joins_to": "municipio"},
                 "time": {"type": "snapshot"}, "sources": ["osm"], "licence_class": "open-with-conditions", "cadence": "snapshot", "tier": "small", "published": "2026-10", "review": []}
        self.assertEqual(errors(self.check(self.rec, self.geo_rec, place)[0]), [])

    def test_email_and_phone_values_are_detected(self):
        (self.dir / "notes.json").write_text(json.dumps([{"name": "Call 787-555-0123 or mail a.b@example.org"}]), encoding="utf-8")
        notes = {"id": "notes", "file": "notes.json", "title": {"en": "N", "es": "N"}, "domains": ["housing"], "geography": {"level": "none", "key": None},
                 "time": {"type": "snapshot"}, "sources": ["census"], "licence_class": "open", "cadence": "snapshot", "tier": "small", "published": "2026-10", "review": []}
        m = messages(self.check(self.rec, self.geo_rec, notes)[0])
        self.assertIn("email address", m)
        self.assertIn("phone number", m)

    # ── the geography crosswalk and the geo/ subfolder (plan item 4) ──

    def write_crosswalk(self, tracts=("72001956400", "72001956500", "72003430200")):
        (self.dir / "geo").mkdir(exist_ok=True)
        units = {"island": [["72", None, "Puerto Rico", "Puerto Rico"]], "region": [["reg-sol-norte", "72", "Porta del Sol Norte", "Porta del Sol Norte"]],
                 "municipio": [["72001", "reg-sol-norte", "Adjuntas", "Adjuntas"], ["72003", "reg-sol-norte", "Aguada", "Aguada"]], "barrio": [["7200113645", "72001", "Capáez", "Capáez"]],
                 "tract": [[t, t[:5], f"Sector censal {t[5:9]}", f"Census tract {t[5:9]}"] for t in tracts], "block-group": [["720019564001", "72001956400", "Grupo de bloques 1", "Block group 1"]]}
        (self.dir / "geo" / "crosswalk.json").write_text(json.dumps({"units": units}), encoding="utf-8")

    def tract_rec(self):
        return {"id": "tracts", "file": "geo/tracts.geojson", "title": {"en": "T", "es": "T"}, "domains": ["system.docs"], "geography": {"level": "tract", "key": "field:GEOID"},
                "time": {"type": "static"}, "sources": ["census"], "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": []}

    def write_tracts(self, ids):
        (self.dir / "geo" / "tracts.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"GEOID": i}, "geometry": None} for i in ids]}), encoding="utf-8")

    def test_files_in_the_geo_subfolder_are_published_files_named_with_their_folder(self):
        self.write_crosswalk()
        self.assertEqual([n for n, _ in contract.published_files(self.dir)], ["geo/crosswalk.json", "municipios.geojson", "rent.json"])
        self.assertIn("geo/crosswalk.json: ", " | ".join(f"{p[2]}: {p[3]}" for p in self.check()[0] if p[0] == "error"), "an unrecorded file in geo/ must fail")
        rec = {"id": "crosswalk", "file": "geo/crosswalk.json", "title": {"en": "C", "es": "C"}, "domains": ["system.docs"], "geography": {"level": "none"}, "time": {"type": "static"},
               "sources": ["census"], "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": []}
        self.assertEqual(errors(self.check(self.rec, self.geo_rec, rec)[0]), [])

    def test_other_subfolders_are_not_published(self):
        (self.dir / "scratch").mkdir()
        (self.dir / "scratch" / "x.json").write_text("{}", encoding="utf-8")
        self.assertEqual([n for n, _ in contract.published_files(self.dir)], ["municipios.geojson", "rent.json"])

    def test_tract_ids_resolve_against_the_crosswalk(self):
        self.write_crosswalk()
        self.write_tracts(["72001956400", "72001956500", "72003430200"])
        crosswalk_rec = {"id": "crosswalk", "file": "geo/crosswalk.json", "title": {"en": "C", "es": "C"}, "domains": ["system.docs"], "geography": {"level": "none"}, "time": {"type": "static"},
                         "sources": ["census"], "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": []}
        self.assertEqual(errors(self.check(self.rec, self.geo_rec, crosswalk_rec, self.tract_rec())[0]), [])
        self.write_tracts(["72001956400", "72001956500", "72003430200", "72001999999"])         # one of four is not a tract of the crosswalk: 25%
        self.assertIn("do not resolve", messages(self.check(self.rec, self.geo_rec, crosswalk_rec, self.tract_rec())[0]))

    def test_municipios_are_checked_against_the_crosswalk_by_id_and_by_name(self):
        self.write_crosswalk()
        (self.dir / "rent.json").write_text(json.dumps({"years": [2010, 2011, 2012], "geo": {"ids": ["72001", "Aguada", "aguada", "72"]}}), encoding="utf-8")
        cw = {"id": "crosswalk", "file": "geo/crosswalk.json", "title": {"en": "C", "es": "C"}, "domains": ["system.docs"], "geography": {"level": "none"}, "time": {"type": "static"},
              "sources": ["census"], "licence_class": "open", "cadence": "static", "tier": "small", "published": "2026-10", "review": []}
        self.assertEqual(errors(self.check(self.rec, self.geo_rec, cw)[0]), [])

    def test_a_block_level_file_needs_a_key_or_a_stated_reason(self):
        r = dict(self.rec, geography={"level": "block", "key": None}, time={"type": "static"})
        self.assertIn("geography.ids_not_published", messages(self.check(r, self.geo_rec)[0], "warn"))
        r = dict(self.rec, geography={"level": "block", "key": None, "ids_not_published": True}, time={"type": "static"})
        self.assertEqual(messages(self.check(r, self.geo_rec)[0], "warn"), "")

    def test_joins_to_accepts_the_crosswalk_levels_only(self):
        for level in ("region", "municipio", "barrio", "tract", "block-group"):
            r = dict(self.rec, geography={"level": "polygon", "key": "geo.ids", "joins_to": level})
            self.assertNotIn("joins_to", messages(self.check(r, self.geo_rec)[0]), level)
        r = dict(self.rec, geography={"level": "polygon", "key": "geo.ids", "joins_to": "county"})
        self.assertIn("joins_to must be one of", messages(self.check(r, self.geo_rec)[0]))

    def test_duplicate_ids_and_files(self):
        a, b = dict(self.rec), dict(self.rec)
        self.assertIn("duplicate id", messages(self.check(a, b, self.geo_rec)[0]))
        self.assertIn("already has a record", messages(self.check(a, dict(b, id="rent2"), self.geo_rec)[0]))


class RealRepositoryTests(unittest.TestCase):
    """The committed registry and contract must pass (this is what the build enforces)."""

    def test_committed_registry_and_contract_have_no_errors(self):
        ids = None
        dj = contract.DATA / "dictionary.json"
        if dj.exists():
            ids = {e["id"] for e in json.loads(dj.read_text(encoding="utf-8"))["entries"]}
        ps, _ = contract.validate_all(entry_ids=ids)
        self.assertEqual(errors(ps), [], "\n".join(f"{p[1]}:{p[2]} {p[3]}" for p in errors(ps)))


if __name__ == "__main__":
    unittest.main()
