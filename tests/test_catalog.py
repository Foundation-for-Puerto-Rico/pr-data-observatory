"""Tests for catalog.py: the file the map reads first (the registry's domains, a headline figure for each, the weight of every file) and the two it reads on first use
(catalog_index.json, the index of the dictionary; catalog_es.json, the words of the Spanish summaries for the Catalog search).

  python -m unittest discover -s tests -v

The island rules (sum, ratio, weighted mean) are checked on a small invented table. The published catalog is checked against its sources: the headline figures
against the series files and the municipal values, the index against the dictionary, the ways onto the map against the files and the layers the page knows,
and the sizes against their budgets: the first read against that of the neutral landing view (docs/proposal-2026-10.md, A3), the files read on first use against their own.
"""
import copy
import gzip
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import catalog  # noqa: E402
import contract  # noqa: E402

DATA = ROOT / "site" / "data"
SRC = ROOT / "dictionary_src"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class IslandRules(unittest.TestCase):
    MUNI = {"A": {"n": 10, "d": 40, "w": 100, "x": 50.0}, "B": {"n": 5, "d": 60, "w": 300, "x": 10.0}, "C": {"n": None, "d": 0, "w": 0, "x": None}}

    def test_sum_ignores_missing(self):
        self.assertEqual(catalog.island_value({"sum": "n"}, self.MUNI), 15)

    def test_ratio_is_a_ratio_of_sums_not_a_mean_of_ratios(self):
        self.assertAlmostEqual(catalog.island_value({"ratio": {"num": "n", "den": "d", "scale": 100}}, self.MUNI), 15.0)   # (10+5)/(40+60) = 15%, not (25%+8.3%)/2

    def test_weighted_mean_skips_municipalities_without_a_value_or_weight(self):
        self.assertAlmostEqual(catalog.island_value({"wmean": {"field": "x", "weight": "w"}}, self.MUNI), (50 * 100 + 10 * 300) / 400)

    def test_zero_denominator_gives_none(self):
        self.assertIsNone(catalog.island_value({"ratio": {"num": "n", "den": "zero"}}, self.MUNI))
        self.assertIsNone(catalog.island_value({"wmean": {"field": "x", "weight": "zero"}}, self.MUNI))
        self.assertIsNone(catalog.island_value({}, self.MUNI))


class IslandRuleChecks(unittest.TestCase):
    MUNI = {"A": {"assets": 3, "in_sfha": 1, "pop": 10, "x": 5.0}, "B": {"assets": 7, "in_sfha": 2, "pop": 30, "x": 1.0}}

    def test_a_mistyped_field_stops_the_build_instead_of_reading_zero(self):
        with self.assertRaises(SystemExit):
            catalog.check_island({"sum": "assetz"}, self.MUNI, "x.y")
        with self.assertRaises(SystemExit):
            catalog.check_island({"ratio": {"num": "in_sfha", "den": "nothing"}}, self.MUNI, "x.y")
        with self.assertRaises(SystemExit):
            catalog.check_island({"wmean": {"field": "x", "weight": "nope"}}, self.MUNI, "x.y")
        with self.assertRaises(SystemExit):
            catalog.check_island({}, self.MUNI, "x.y")

    def test_good_rules_and_units_pass(self):
        catalog.check_island({"ratio": {"num": "in_sfha", "den": "assets", "scale": 100}, "unit": "%", "d": 1}, self.MUNI, "x.y")
        catalog.check_island({"sum": "assets"}, self.MUNI, "x.y")

    def test_unit_and_decimals_are_checked(self):
        with self.assertRaises(SystemExit):
            catalog.check_island({"sum": "assets", "unit": "dollars"}, self.MUNI, "x.y")
        with self.assertRaises(SystemExit):
            catalog.check_island({"sum": "assets", "d": -1}, self.MUNI, "x.y")
        with self.assertRaises(SystemExit):
            catalog.check_island({"sum": "assets", "d": 1.5}, self.MUNI, "x.y")


class NightlyApply(unittest.TestCase):
    """catalog.apply() is what the nightly transit refresh calls: it must not rewrite the file for a change of file sizes, and must rewrite it for a changed figure."""

    def setUp(self):
        self._build, self._out, self._parts = catalog.build, catalog.OUT, catalog.PARTS
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        catalog.OUT = d / "catalog.json"
        catalog.PARTS = {d / "catalog_index.json": ("index", "sources"), d / "catalog_es.json": ("words_es",)}
        self.base = {"version": 1, "built": "2026-10-02T00:00:00+00:00", "snapshot": "S", "domains": [{"id": "a", "headline": {"value": 22.0}}], "index": {"fields": [], "rows": []},
                     "words_es": {"a.b": "pobreza"}, "sources": {}, "weights": {"x.json": {"raw": 10, "gz": 5}}}
        catalog.write(self.base)

    def tearDown(self):
        catalog.build, catalog.OUT, catalog.PARTS = self._build, self._out, self._parts
        self.tmp.cleanup()

    def files(self):
        return [p.read_bytes() for p in (catalog.OUT, *catalog.PARTS)]

    def test_only_weights_changed_writes_nothing(self):
        new = copy.deepcopy(self.base)
        new["weights"]["x.json"]["gz"] = 99
        new["built"] = "2026-10-07T00:00:00+00:00"
        catalog.build = lambda with_weights=True: new
        before = self.files()
        self.assertFalse(catalog.apply(log=lambda *_: None))
        self.assertEqual(self.files(), before)

    def test_a_changed_headline_rewrites_the_file(self):
        new = copy.deepcopy(self.base)
        new["domains"][0]["headline"]["value"] = 21.0
        catalog.build = lambda with_weights=True: new
        self.assertTrue(catalog.apply(log=lambda *_: None))
        self.assertEqual(json.loads(catalog.OUT.read_text(encoding="utf-8"))["domains"][0]["headline"]["value"], 21.0)

    def test_a_changed_index_or_spanish_summary_rewrites_its_file(self):
        for part, change in (("index", lambda n: n["index"]["rows"].append(["x"])), ("words_es", lambda n: n["words_es"].update({"a.b": "vivienda"}))):
            new = copy.deepcopy(self.base)
            change(new)
            catalog.build = lambda with_weights=True: new
            self.assertTrue(catalog.apply(log=lambda *_: None), part)
            self.assertEqual(catalog.published()[part], new[part], part)
            self.base = new

    def test_the_first_read_holds_no_index_and_each_file_its_own_part(self):
        files = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in (catalog.OUT, *catalog.PARTS)}
        self.assertEqual(sorted(files["catalog.json"]), ["built", "domains", "snapshot", "version", "weights"])
        self.assertEqual(sorted(files["catalog_index.json"]), ["built", "index", "sources", "version"])
        self.assertEqual(sorted(files["catalog_es.json"]), ["built", "version", "words_es"])
        self.assertEqual(catalog.published(), self.base, "the files put together are what build() gave")


class SpanishWords(unittest.TestCase):
    def test_words_are_normalised_as_the_page_does_each_once(self):
        self.assertEqual(catalog.es_words("Porcentaje de la población bajo el nivel de pobreza. La pobreza se mide por año."), "porcentaje poblacion bajo nivel pobreza mide ano")
        self.assertIsNone(catalog.es_words(None))
        self.assertIsNone(catalog.es_words("de la y"))


class Periods(unittest.TestCase):
    def test_periods_follow_the_timeline_of_the_entry(self):
        self.assertEqual(catalog.period_of({"coverage": {"timeline": "five-year window"}}, 2024), {"type": "window", "first": 2020, "last": 2024})
        self.assertEqual(catalog.period_of({"coverage": {"timeline": "annual"}}, 2025), {"type": "year", "year": 2025})
        self.assertEqual(catalog.period_of({"coverage": {"timeline": "event-based"}}, 2024), {"type": "event", "year": 2024})
        self.assertEqual(catalog.period_of({"coverage": {"timeline": "snapshot"}}, None), {"type": "snapshot"})


class Licences(unittest.TestCase):
    def test_strictest_class_wins_and_unknowns_are_ignored(self):
        self.assertEqual(catalog.strictest(["open", "unstated", "own"]), "unstated")
        self.assertEqual(catalog.strictest(["open", "licensed-not-open"]), "licensed-not-open")
        self.assertEqual(catalog.strictest([None, "open-with-conditions"]), "open-with-conditions")
        self.assertIsNone(catalog.strictest([None]))


@unittest.skipUnless(all((DATA / f).exists() for f in ("catalog.json", "catalog_index.json", "catalog_es.json", "dictionary.json")), "run python dictionary.py and python catalog.py first")
class PublishedCatalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = load(DATA / "catalog.json")
        cls.cat.update({k: v for k, v in load(DATA / "catalog_index.json").items() if k in ("index", "sources")})   # the index is a file of its own, read on first use
        cls.reg = load(SRC / "domains.json")
        cls.dict = load(DATA / "dictionary.json")
        cls.muni = load(DATA / "municipalities.json")

    def test_is_what_the_sources_give(self):
        self.assertEqual(catalog.comparable(catalog.published()), catalog.comparable(catalog.build(with_weights=False)), "catalog.json, catalog_index.json or catalog_es.json is stale: run python catalog.py")

    def test_the_spanish_words_are_those_of_the_spanish_summaries(self):
        words = load(DATA / "catalog_es.json")["words_es"]
        have = {e["id"]: e["plain_es"] for e in self.dict["entries"] if e.get("plain_es")}
        self.assertEqual(set(words), {i for i, t in have.items() if catalog.es_words(t)})
        self.assertIn("pobreza", words["housing.poverty_pct"].split(), "a Spanish page finds the poverty rate by its Spanish summary")

    def test_every_registry_domain_is_in_the_catalog_in_the_registry_order(self):
        self.assertEqual([d["id"] for d in self.cat["domains"]], [d["id"] for d in self.reg["domains"]])
        for d in self.cat["domains"]:
            self.assertTrue(d["name"]["es"] and d["name"]["en"] and d["description"]["es"] and d["description"]["en"], d["id"])

    def test_headline_series_figures_equal_the_last_puerto_rico_value_of_the_file(self):
        files = {f: load(DATA / f) for f in ("housing_series.json", "economy_series.json", "health_series.json", "community_series.json", "broadband_series.json", "infrastructure_series.json")}
        n = 0
        for d in self.cat["domains"]:
            h = d["headline"]
            if not h or h["kind"] != "series":
                continue
            fname, key = None, None
            entry = next(e for e in self.dict["entries"] if e["id"] == h["variable"])
            for f in entry["where"]["files"]:
                name, _, k = f.partition(":")
                if name in files:
                    fname, key = name, k
            v = next(x for x in files[fname]["vars"] if x["key"] == key)
            if v.get("from") == "housing":
                v = next(x for x in files["housing_series.json"]["vars"] if x["key"] == key)
            ys = sorted(int(y) for y in v["years"] if v["years"][y][-1] is not None)
            self.assertEqual(h["year"], ys[-1], d["id"])
            self.assertEqual(h["value"], v["years"][str(ys[-1])][-1], d["id"])
            if len(ys) == 1:   # a snapshot has no trend to draw
                self.assertIsNone(h["series"], d["id"])
            else:
                self.assertEqual([p[0] for p in h["series"]], ys, d["id"])
            n += 1
        self.assertGreaterEqual(n, 4)

    def test_headline_snapshot_figures_are_recomputed_independently(self):
        rows = list(self.muni.values())
        by_id = {d["id"]: d for d in self.cat["domains"]}
        hz = by_id["hazards"]["headline"]
        self.assertAlmostEqual(hz["value"], round(sum(r["in_sfha"] for r in rows) / sum(r["assets"] for r in rows) * 100, 1))
        self.assertEqual(by_id["environment.land"]["headline"]["value"], sum(r["in_protected"] for r in rows))
        self.assertEqual(by_id["economy.visitor-economy"]["headline"]["value"], sum(r["assets"] for r in rows))
        mb = by_id["infrastructure.mobility"]["headline"]
        w = sum(r["population_2020"] for r in rows)
        self.assertEqual(mb["value"], round(sum(r["pop_walk_active_pct"] * r["population_2020"] for r in rows) / w))   # the Mobility headline is by walking since 2026-10-16
        # the island share found from the blocks is the same figure to a point (meta.network counts every scheduled stop, the field only those with a current timetable)
        self.assertTrue(0 < mb["value"] < 100)

    def test_a_snapshot_headline_without_an_island_rule_stops_the_build(self):
        dom = {"id": "x", "headline": {"variable": "municipalities.sfha_pct", "norm": "value"}}
        entries = {e["id"]: e for e in self.dict["entries"]}
        with self.assertRaises(SystemExit):
            catalog.headline(dom, entries, self.muni, {}, "Snapshot")

    def test_index_rows_are_the_dictionary_entries(self):
        fields, rows = self.cat["index"]["fields"], self.cat["index"]["rows"]
        self.assertEqual(len(rows), len(self.dict["entries"]))
        ids = [r[fields.index("id")] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {e["id"] for e in self.dict["entries"]})
        self.assertTrue(all(len(r) == len(fields) for r in rows))

    def test_ways_onto_the_map_point_at_things_that_exist(self):
        app = (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
        adapters = (ROOT / "site" / "js" / "core" / "adapters.js").read_text(encoding="utf-8")
        layer_keys = set(re.findall(r"(\w+): '(?:ly\w+|walkRings)'", app))
        series = set()
        for f in ("housing_series.json", "economy_series.json", "health_series.json", "population_series.json", "commuting_series.json", "svi_series.json", "facility_exposure_series.json", "credit_series.json", "drought_series.json", "storm_recovery_series.json", "essentials_series.json", "cutoff_series.json", "jobs_reach_series.json", "netmig_age_series.json", "degrees_series.json", "school_conditions_series.json", "proficiency_series.json", "providers_series.json", "education_series.json", "labor_sex_series.json", "nightlights_series.json", "broadband_series.json", "energy_series.json", "traffic_series.json", "crashes_series.json", "heat_series.json", "vegetation_series.json", "buildings_series.json", "fires_series.json", "night_heat_series.json", "climb_series.json", "slope_series.json", "medicare_series.json", "care_series.json", "bridges_series.json", "infrastructure_series.json", "environment_series.json", "hazard_series.json", "gateway_series.json", "facility_series.json", "community_series.json", "nonprofit_series.json", "conditions_series.json", "landslide_series.json", "wcrp_rvi_barrio.json"):
            series |= {v["key"] for v in load(DATA / f)["vars"]}
        series |= {f"exp_{k}_{m}" for k in load(DATA / "exposure_municipio.json")["vars"] for m in ("pop", "hu")}   # the exposure series: datasets the layer engine builds from exposure_municipio.json (site/js/core/adapters.js)
        snap = set(re.findall(r"^    \{ key: '(\w+)'", adapters[adapters.index("const SNAPSHOT_FIELDS"):adapters.index("const SNAPSHOT_SOURCES")], re.M))   # one-period datasets from municipalities.json
        series |= snap | {"tourism_places"}
        fields = self.cat["index"]["fields"]
        kinds = {"econ": 0, "layers": 0}
        for r in self.cat["index"]["rows"]:
            a = r[fields.index("map")]
            if not a:
                continue
            kinds[a[0]] += 1   # no "choro" action is left: the shading menu was retired (decision 81 (d))
            if a[0] == "econ":
                self.assertIn(a[1], series, r[0])
            else:
                for k in a[1].split(","):
                    self.assertIn(k, layer_keys, r[0])
        self.assertTrue(all(kinds.values()), kinds)
        for d in self.cat["domains"]:   # a headline's "Show on map" opens a dataset
            h = d["headline"]
            if h and h["map"]:
                self.assertEqual(h["map"][0], "econ", h["variable"])
                self.assertIn(h["map"][1], series, h["variable"])

    def test_every_old_shading_measure_opens_a_dataset(self):
        """s= links of the retired "Shade municipalities by" menu (app.js SHADE_DS): every measure is mapped, to a dataset the engine has, with a normalisation it allows."""
        app = (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
        adapters = (ROOT / "site" / "js" / "core" / "adapters.js").read_text(encoding="utf-8")
        shade = catalog.shade_datasets()
        self.assertEqual(len(shade), 35)
        snap = set(re.findall(r"^    \{ key: '(\w+)'", adapters[adapters.index("const SNAPSHOT_FIELDS"):adapters.index("const SNAPSHOT_SOURCES")], re.M))
        known = snap | {"tourism_places"} | {v["key"] for v in load(DATA / "housing_series.json")["vars"]} | {v["key"] for v in load(DATA / "population_series.json")["vars"]}
        for k, v in shade.items():
            self.assertIn(v[0], known, k)
            if len(v) > 1:
                self.assertIn(v[1], ("per1000", "perkm2"), k)
        self.assertNotIn('id="choro"', (ROOT / "site" / "index.html").read_text(encoding="utf-8"))
        self.assertIn("const SHADE_DS = {", app)
        self.assertIn("Core.viewstate.has(SHADE_DS, EC.pending.s)", (ROOT / "site" / "js" / "economy.js").read_text(encoding="utf-8"))   # economy.js opens an old link's s= as its dataset

    def test_layers_come_from_the_list_and_nothing_else(self):
        listed = load(SRC / "map_layers.json")["layers"]
        by_id = {e["id"] for e in self.dict["entries"]}
        self.assertTrue(set(listed) <= by_id, "map_layers.json names an id that is not a dictionary entry")
        fields = self.cat["index"]["fields"]
        offered = {r[0]: r[fields.index("map")][1] for r in self.cat["index"]["rows"] if r[fields.index("map")] and r[fields.index("map")][0] == "layers"}
        self.assertEqual(offered, listed)

    def test_levels_and_licence_classes_are_the_contract_vocabulary(self):
        fields = self.cat["index"]["fields"]
        for r in self.cat["index"]["rows"]:
            for lv in r[fields.index("levels")]:
                self.assertIn(lv, contract.LEVELS, r[0])
            lc = r[fields.index("licence")]
            self.assertTrue(lc is None or lc in contract.LICENCE_CLASSES, r[0])

    def test_weights_cover_every_file_but_the_catalog(self):
        names = {n for n, _ in contract.published_files(DATA) if n not in ("catalog.json", "catalog_index.json", "catalog_es.json", "catalog_views.json", "catalog_domains.json")}
        self.assertEqual(set(self.cat["weights"]), names)
        for name, w in self.cat["weights"].items():
            self.assertGreater(w["raw"], 0, name)
            self.assertGreater(w["gz"], 0, name)

    def test_the_catalog_stays_inside_the_landing_budget(self):
        """What the map reads first: the registry, the headline figures and the weights (18 KB, 6 KB compressed on 2026-10-18). Docs/proposal-2026-10.md A3 gives the
        whole catalog 100-200 KB; since the index left it, the first read has a budget of its own, so that growing past it is a decision (docs/performance.md)."""
        raw = (DATA / "catalog.json").read_bytes()
        self.assertNotIn(b'"index"', raw, "the index of the dictionary is read on first use, from catalog_index.json")
        self.assertLessEqual(len(raw), 32 * 1024)
        self.assertLessEqual(len(gzip.compress(raw, 6)), 10 * 1024)

    def test_the_files_read_on_first_use_stay_inside_their_budget(self):
        """The index (182 KB, 28 KB compressed on 2026-10-18; it grows by about 225 bytes, 35 compressed, for each dictionary entry) and the Spanish words (117 KB, 30 KB
        compressed). On 2026-11-13 the index reached 40.0 KB compressed with the road deaths entries (decision 105, step 3), so its compressed budget is 48 KB:
        room for about two hundred more entries. On 2026-11-16 the index reached 256 KB raw (42.7 KB compressed) with the public schools layer (decision 107,
        step 3), so its raw budget is 288 KB; what a visitor downloads is the compressed size. On 2026-11-18 the Spanish words reached 40.1 KB compressed with the
        degrees entries (decision 107, step 7), so their compressed budget is 44 KB. Both load on first use of the catalog's search, not with the map."""
        for name, raw_kb, gz_kb in (("catalog_index.json", 288, 48), ("catalog_es.json", 160, 44)):
            raw = (DATA / name).read_bytes()
            self.assertLessEqual(len(raw), raw_kb * 1024, name)
            self.assertLessEqual(len(gzip.compress(raw, 6)), gz_kb * 1024, name)


class ReadyMadeViews(unittest.TestCase):
    """The ready-made views of each topic (navigation plan PR 6, decision 81): in dictionary_src/domains.json, built into catalog_views.json with their sources.
    The page checks the datasets and scales against the engine in tests/presets.test.js."""

    @classmethod
    def setUpClass(cls):
        cls.reg = {d["id"]: d for d in load(SRC / "domains.json")["domains"]}
        cls.built = load(DATA / "catalog_views.json")["presets"]
        cls.sources = load(DATA / "catalog_index.json")["sources"]

    def test_built_as_the_registry_has_them_each_with_sources(self):
        want = {k: d["presets"] for k, d in self.reg.items() if d.get("presets")}
        self.assertEqual(set(self.built), set(want))
        for k, vs in want.items():
            self.assertEqual([{x: v[x] for x in ("id", "name", "note", "show", "on")} for v in self.built[k]], vs, k)
            for v in self.built[k]:
                self.assertTrue(v["sources"] and all(x in self.sources for x in v["sources"]), f"{k}.{v['id']}: its sources are named in the index")

    def test_every_topic_has_two_to_four(self):
        """Public money's three views were released on 2026-11-05 (HANDOFF decision 86: Francis, with the Finance/Compliance approval of their wording). The visitor
        economy's view is shown after the economy's (catalog.js viewsOf: a sub-topic after its topic), so tourism stays last."""
        for k, d in self.reg.items():
            if d["parent"] or d["system"]:
                continue
            n = sum(len(x.get("presets", [])) for x in self.reg.values() if x["id"] == k or x["parent"] == k)
            self.assertTrue(2 <= n <= 4, f"{k}: {n} views")

    def test_a_view_that_breaks_the_rules_stops_the_build(self):
        d = copy.deepcopy(self.reg["hazards"])
        srcs = {("econ", "exp_flood_sfha_pop"): ["fema_nfhl"]}
        for bad in ({"show": [["exp_flood_sfha_pop", "fill", {"ramp": "rainbow"}]]}, {"show": [["exp_flood_sfha_pop", "fill", "shareArea"]]}, {"show": [["no_such_dataset", "fill"]]}, {"on": ["no_such_layer"]}, {"show": [["exp_flood_sfha_pop", "fill"]] * 3},
                    {"show": [], "on": []}, {"note": {"en": "x"}}):
            d["presets"] = [{**self.reg["hazards"]["presets"][1], **bad}]
            with self.assertRaises(SystemExit, msg=str(bad)):
                catalog.presets(d, srcs, {"fema_nfhl": {"name": "FEMA", "kind": "data"}})


class RegistryRules(unittest.TestCase):
    def reg(self, headline):
        r = load(SRC / "domains.json")
        next(d for d in r["domains"] if d["id"] == "housing")["headline"] = headline
        return r

    def problems(self, headline):
        return [p for p in contract.validate_registry(self.reg(headline), entry_ids=None, tokens=None) if p[2] == "housing"]

    def test_island_rule_needs_exactly_one_rule(self):
        base = {"variable": "x.y", "norm": "value", "label": {"es": "a", "en": "b"}}
        self.assertEqual(self.problems({**base, "island": {"sum": "assets"}}), [])
        self.assertTrue(self.problems({**base, "island": {"sum": "assets", "ratio": {"num": "a", "den": "b"}}}))
        self.assertTrue(self.problems({**base, "island": {"ratio": {"num": "a"}}}))
        self.assertTrue(self.problems({**base, "island": {"wmean": {"field": "a"}}}))

    def test_a_headline_without_a_label_is_flagged(self):
        p = self.problems({"variable": "x.y", "norm": "value"})
        self.assertTrue(any("label" in m[3] for m in p))


if __name__ == "__main__":
    unittest.main()
