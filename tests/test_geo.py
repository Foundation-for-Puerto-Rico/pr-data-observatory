"""Tests for geo.py (the geography crosswalk) and the census block table in network.py.

  python -m unittest discover -s tests -v

A small invented island (one municipio, two barrios, two tracts that cut across them, two block groups) checks the checker: a good set of files passes and each
kind of damage is reported. The real published files are checked too (they must pass their own checks, and the figures the dictionary text quotes must still hold,
so a rebuild that changes them cannot leave stale text behind). No network is used.
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import geo  # noqa: E402
import network  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
SQUARE_A = {"type": "Polygon", "coordinates": [[[-66.0, 18.0], [-65.9, 18.0], [-65.9, 18.1], [-66.0, 18.1], [-66.0, 18.0]]]}
SQUARE_B = {"type": "Polygon", "coordinates": [[[-65.9, 18.0], [-65.8, 18.0], [-65.8, 18.1], [-65.9, 18.1], [-65.9, 18.0]]]}


def unit(id_, parent, name, km2, pop, hu, lat=18.05, lng=-65.9):
    return [id_, parent, name, name, geo.norm(name), km2, pop, hu, lat, lng]


def tiny_crosswalk():
    """Residents 100, housing units 50, 10 km2. Barrio 1 (60 residents) lies in tracts 1 and 2; barrio 2 (40) likewise."""
    units = {
        "island": [unit("72", None, "Puerto Rico", 10.0, 100, 50)],
        "region": [unit("reg-a", "72", "Porta A", 10.0, 100, 50)],
        "municipio": [unit("72001", "reg-a", "Adjuntas", 10.0, 100, 50)],
        "barrio": [unit("7200100001", "72001", "Barrio Uno", 6.0, 60, 30), unit("7200100002", "72001", "Barrio Dos", 4.0, 40, 20)],
        "tract": [unit("72001000100", "72001", "Sector censal 1", 7.0, 70, 35), unit("72001000200", "72001", "Sector censal 2", 3.0, 30, 15)],
        "block-group": [unit("720010001001", "72001000100", "Grupo de bloques 1, sector censal 1", 7.0, 70, 35), unit("720010002001", "72001000200", "Grupo de bloques 1, sector censal 2", 3.0, 30, 15)],
    }
    levels = [{"id": lv, "parent": p, "count": len(units[lv])} for lv, p in (("island", None), ("region", "island"), ("municipio", "region"), ("barrio", "municipio"), ("tract", "municipio"), ("block-group", "tract"))]
    weights = [["7200100001", "72001000100", 50, 25, 2], ["7200100001", "72001000200", 10, 5, 1], ["7200100002", "72001000100", 20, 10, 1], ["7200100002", "72001000200", 20, 10, 2]]
    return {"version": 1, "fields": geo.UNIT_FIELDS, "levels": levels, "units": units, "weights": {"barrio_tract": {"fields": geo.WEIGHT_FIELDS, "rows": weights}}}


def outlines(ids):
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"GEOID": i}, "geometry": SQUARE_A} for i in ids]}


class CacheFolders(unittest.TestCase):
    """The nightly job starts on a clean runner with no cache/geo: a function that caches must make the folder it writes to."""

    def test_barrio_polygons_makes_the_cache_folder(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache" / "geo"   # does not exist
            reply = mock.Mock()
            reply.json.return_value = {"features": [{"properties": {"GEOID": "7200100001"}, "geometry": SQUARE_A}]}
            with mock.patch.object(geo, "CACHE", cache), mock.patch.object(geo, "get", return_value=reply), mock.patch.object(geo, "log"):
                out = geo.barrio_polygons(False)
            self.assertEqual(list(out), ["7200100001"])
            self.assertTrue((cache / "tiger_barrio_geometry.json").exists())
            with mock.patch.object(geo, "CACHE", cache), mock.patch.object(geo, "get", side_effect=AssertionError("it must read the cache")):
                self.assertEqual(list(geo.barrio_polygons(False)), ["7200100001"])


class Names(unittest.TestCase):
    def test_region_ids_are_short_stable_and_unique(self):
        names = ["Porta Capital", "Porta Atlántico", "Porta del Mar", "Porta Caribe", "Porta Cordillera", "Porta del Sol Norte", "Porta del Sol Sur"]
        ids = [geo.region_id(n) for n in names]
        self.assertEqual(ids, ["reg-capital", "reg-atlantico", "reg-mar", "reg-caribe", "reg-cordillera", "reg-sol-norte", "reg-sol-sur"])
        self.assertEqual(len(set(ids)), 7)

    def test_names_of_tracts_and_block_groups(self):
        self.assertEqual(geo.tract_names("9564"), ("Sector censal 9564", "Census tract 9564"))
        self.assertEqual(geo.blockgroup_names("2", "9563.01"), ("Grupo de bloques 2, sector censal 9563.01", "Block group 2, census tract 9563.01"))

    def test_norm_drops_accents_and_case(self):
        self.assertEqual(geo.norm("  Capáez "), "capaez")
        self.assertEqual(geo.norm("Porta Atlántico"), "porta atlantico")


class Placing(unittest.TestCase):
    def test_each_block_goes_to_the_barrio_that_holds_its_internal_point(self):
        blocks = [["b1", 5, 2, 100, -65.95, 18.05], ["b2", 7, 3, 100, -65.85, 18.05]]
        owner, loose = geo.assign_blocks_to_barrios(blocks, {"A": SQUARE_A, "B": SQUARE_B})
        self.assertEqual(owner, {"b1": "A", "b2": "B"})
        self.assertEqual(loose, 0)

    def test_a_point_on_an_edge_or_just_outside_still_gets_the_nearest_barrio(self):
        blocks = [["edge", 1, 1, 1, -65.9, 18.05], ["outside", 1, 1, 1, -66.0005, 18.05]]
        owner, loose = geo.assign_blocks_to_barrios(blocks, {"A": SQUARE_A, "B": SQUARE_B})
        self.assertIn(owner["edge"], ("A", "B"))
        self.assertEqual(owner["outside"], "A")
        self.assertEqual(loose, 2)

    def test_the_blocks_must_add_up_to_the_census_totals(self):
        got = {"x": {"pop": 10, "hu": 4, "blocks": 2}}
        geo.compare("tract", got, {"x": {"pop": 10, "hu": 4}})
        with self.assertRaises(SystemExit) as cm:
            geo.compare("tract", got, {"x": {"pop": 11, "hu": 4}})
        self.assertIn("x", str(cm.exception))
        with self.assertRaises(SystemExit):
            geo.compare("tract", got, {"y": {"pop": 0, "hu": 0}})               # an id the Census Bureau does not know
        geo.compare("tract", {}, {"water": {"pop": 0, "hu": 0}})                # a unit with no blocks and no residents is fine


class Checker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.cw = tiny_crosswalk()
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, cw=None, tracts=("72001000100", "72001000200"), groups=("720010001001", "720010002001")):
        (self.dir / "crosswalk.json").write_text(json.dumps(cw or self.cw), encoding="utf-8")
        (self.dir / "tracts.geojson").write_text(json.dumps(outlines(tracts)), encoding="utf-8")
        (self.dir / "blockgroups.geojson").write_text(json.dumps(outlines(groups)), encoding="utf-8")

    def problems(self, cw=None, **kw):
        self.write(cw, **kw)
        return " | ".join(geo.check(self.dir))

    def test_good_files_pass(self):
        self.assertEqual(geo.check(self.dir), [])

    def test_missing_files_are_reported(self):
        shutil.rmtree(self.dir)
        self.assertIn("missing", " ".join(geo.check(self.dir)))
        self.dir.mkdir()                                                          # so tearDown has something to remove

    def test_repeated_id(self):
        cw = copy.deepcopy(self.cw)
        cw["units"]["barrio"][1][0] = "7200100001"
        self.assertIn("duplicate id 7200100001", self.problems(cw))

    def test_a_parent_of_the_wrong_kind(self):
        cw = copy.deepcopy(self.cw)
        cw["units"]["block-group"][0][1] = "72001"                                 # a municipio, not a tract
        self.assertIn("720010001001: parent 72001 is not a tract", self.problems(cw))

    def test_children_must_add_up_to_the_parent(self):
        for index, label in ((6, "residents"), (7, "housing units")):
            cw = copy.deepcopy(self.cw)
            cw["units"]["tract"][0][index] += 1
            self.assertIn("differ from the sum of its tracts", self.problems(cw), label)
        cw = copy.deepcopy(self.cw)
        cw["units"]["barrio"][0][5] += 0.5
        self.assertIn("land area", self.problems(cw))

    def test_rounding_of_areas_is_tolerated(self):
        cw = copy.deepcopy(self.cw)
        cw["units"]["barrio"][0][5] += 0.0001
        self.assertEqual(self.problems(cw), "")

    def test_weights_must_add_up_to_each_barrio_and_tract(self):
        cw = copy.deepcopy(self.cw)
        cw["weights"]["barrio_tract"]["rows"][0][2] += 5
        text = self.problems(cw)
        self.assertIn("barrio 7200100001: its weights do not add up", text)
        self.assertIn("tract 72001000100: its weights do not add up", text)

    def test_a_weight_between_things_that_are_not_a_barrio_and_a_tract(self):
        cw = copy.deepcopy(self.cw)
        cw["weights"]["barrio_tract"]["rows"][0][1] = "72001"
        self.assertIn("not a barrio and a tract", self.problems(cw))

    def test_names_must_be_there_and_norm_must_follow_them(self):
        cw = copy.deepcopy(self.cw)
        cw["units"]["barrio"][0][4] = "something else"
        self.assertIn("names or normalized name", self.problems(cw))

    def test_outlines_must_belong_to_the_crosswalk(self):
        self.assertIn("are not tracts of the crosswalk", self.problems(tracts=("72001000100", "72001999999")))
        self.assertIn("are not block-groups of the crosswalk", self.problems(groups=("72001000100",)))
        self.assertIn("repeated ids", self.problems(tracts=("72001000100", "72001000100")))

    def test_a_row_with_the_wrong_number_of_values(self):
        cw = copy.deepcopy(self.cw)
        cw["units"]["island"][0].pop()
        self.assertIn("expected 10", self.problems(cw))


class BlockTable(unittest.TestCase):
    ROWS = [["721455603001001", 226, 107, 1041751, -66.3906534, 18.4728836], ["721455602041002", 0, 12, 27711, -66.4089779, 18.4589251], ["720015601001000", 93, 45, 500, -66.7, 18.2]]

    def test_load_blocks_keeps_the_blocks_with_residents_in_the_old_row_format(self):
        with mock.patch.object(network, "load_block_table", return_value={"fields": network.BLOCK_FIELDS, "rows": self.ROWS}):
            rows = network.load_blocks(Path("."), False)
        self.assertEqual(rows, [[-66.3907, 18.4729, 226, "72145"], [-66.7, 18.2, 93, "72001"]])

    def test_the_fields_are_the_documented_ones(self):
        self.assertEqual(network.BLOCK_FIELDS, ["geoid", "pop", "hu", "land_m2", "lon", "lat"])


class PublishedFiles(unittest.TestCase):
    """The real crosswalk and outlines in site/data/geo."""

    @classmethod
    def setUpClass(cls):
        if not (DATA / "geo" / "crosswalk.json").exists():
            raise unittest.SkipTest("site/data/geo has not been built (python geo.py)")
        cls.cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))

    def test_the_published_files_pass_their_own_checks(self):
        self.assertEqual(geo.check(), [])

    def test_levels_and_counts(self):
        self.assertEqual({lv: len(rows) for lv, rows in self.cw["units"].items()}, {"island": 1, "region": 7, "municipio": 78, "barrio": 901, "tract": 981, "block-group": 2555})
        self.assertEqual(sum(len(r) for r in self.cw["units"].values()), 4523)

    def test_the_municipios_and_barrios_are_the_ones_the_twin_already_publishes(self):
        muni = json.loads((DATA / "municipios.geojson").read_text(encoding="utf-8"))
        self.assertEqual({r[0]: r[2] for r in self.cw["units"]["municipio"]}, {str(f["properties"]["GEOID"]): f["properties"]["municipality"] for f in muni["features"]})
        barrios = json.loads((DATA / "barrios.geojson").read_text(encoding="utf-8"))
        self.assertEqual({r[0]: r[2] for r in self.cw["units"]["barrio"]}, {f["properties"]["geoid"]: f["properties"]["barrio"] for f in barrios["features"]})

    def test_the_regions_are_the_municipios_regions(self):
        muni = json.loads((DATA / "municipios.geojson").read_text(encoding="utf-8"))
        want = {str(f["properties"]["GEOID"]): geo.region_id(f["properties"]["region"]) for f in muni["features"]}
        self.assertEqual({r[0]: r[1] for r in self.cw["units"]["municipio"]}, want)

    def test_every_unit_with_land_has_an_outline_and_the_ones_without_are_water(self):
        for level, name in (("tract", "tracts.geojson"), ("block-group", "blockgroups.geojson")):
            have = {f["properties"]["GEOID"] for f in json.loads((DATA / "geo" / name).read_text(encoding="utf-8"))["features"]}
            lacking = [r for r in self.cw["units"][level] if r[0] not in have]
            self.assertEqual(len(lacking), 42, level)
            for r in lacking:
                self.assertEqual((r[5], r[6], r[7]), (0, 0, 0), f"{level} {r[0]} has no outline but has land, residents or housing units")

    def test_figures_quoted_in_the_dictionary_text_still_hold(self):
        """dictionary_src/entries/geography.json and docs/geography.md quote these; if a rebuild changes one, update the text."""
        cw = self.cw
        self.assertEqual((cw["totals"]["pop"], cw["totals"]["hu"], cw["totals"]["blocks"], cw["totals"]["blocks_with_residents"]), (3285874, 1598159, 41987, 36570))
        self.assertEqual(cw["totals"]["barrio_offshore_not_defined"], 38)
        self.assertEqual((cw["nesting"]["barrios_with_residents"], cw["nesting"]["barrios_in_two_or_more_tracts"], round(cw["nesting"]["share_of_residents"], 2)), (896, 489, 0.81))
        self.assertEqual(len(cw["weights"]["barrio_tract"]["rows"]), 2057)
        by = {r[0]: r for lv in cw["units"] for r in cw["units"][lv]}
        self.assertEqual(by["72001956400"][2:4] + by["72001956400"][6:8], ["Sector censal 9564", "Census tract 9564", 2645, 1150])
        self.assertEqual(by["7200113645"][2], "Capáez")
        self.assertEqual(len({r[2] for r in cw["units"]["barrio"]}), 694)
        weights = {(b, t): (hu, n) for b, t, pop, hu, n in cw["weights"]["barrio_tract"]["rows"]}
        self.assertEqual((weights[("7200331318", "72003430200")][0], weights[("7200331318", "72003430300")][0]), (748, 421))
        self.assertEqual(round(by["7207531920"][5], 2), 15.31)

    def test_the_block_ids_line_up_with_population_blocks_json_when_the_build_cache_is_there(self):
        cache = Path(__file__).resolve().parent.parent / "cache" / "network" / "census_blocks_ids.json"
        if not cache.exists():
            self.skipTest("no block table in cache/network")
        table = json.loads(cache.read_text(encoding="utf-8"))
        populated = [r for r in table["rows"] if r[1] > 0]
        published = json.loads((DATA / "population_blocks.json").read_text(encoding="utf-8"))
        self.assertEqual(len(populated), len(published))
        for r, p in zip(populated, published):
            self.assertEqual((round(r[4], 4), round(r[5], 4), r[1]), (p[0], p[1], p[2]))


if __name__ == "__main__":
    unittest.main()
