"""Tests for exposure.py (residents and housing units exposed to flood, sea level rise, storm surge and protected land, and near transit).

  python -m unittest discover -s tests -v

A small invented island checks every rule: seven census blocks, a flood layer with one polygon of each kind FEMA has (and two that must not count), protected areas
(with a proclamation boundary that must not count), sea level layers, storm surge depth bands, four stops with different timetables. The whole build runs on it without any download, and so
does the nightly step. The real published files are checked too (they must pass their own checks, tie out with the Transit tab, and match the figures the dictionary
quotes). One slow test rebuilds everything from the real inputs; run it with PRDT_SLOW=1.
"""
import copy
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

import numpy as np
from shapely.geometry import box, mapping

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import exposure  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
LAT, LNG = 18.2, -66.2
AS_OF = date(2026, 10, 6)


def at(north_m=0.0, east_m=0.0):
    """(lat, lng) a given number of meters north and east of the origin, on the scale the observatory uses (111,320 m per degree of latitude)."""
    lat = LAT + north_m / 111_320
    lng = LNG + east_m / (111_320 * math.cos(math.radians(LAT + north_m / 222_640)))
    return round(lat, 7), round(lng, 7)


def around(lat, lng, d=0.0005):
    return box(lng - d, lat - d, lng + d, lat + d)


# blocks: (geoid, residents, housing units, north m, east m, barrio)
SPEC = [
    ("720010001001001", 100, 40, 0, 0, "7200100001"),        # b1: tract 1, barrio A: in the 1% flood area; frequent current stop near
    ("720010001001002", 50, 20, 0, 3000, "7200100002"),      # b2: tract 1, barrio B: 0.2% flood area only; 2 ft sea level; stop with an expired timetable near
    ("720010002001001", 30, 10, 3000, 0, "7200100001"),      # b3: tract 2, barrio A: unshaded zone X (no flood); proclamation boundary (no protected); 1 ft sea level; only an OSM stop near
    ("720010002001002", 20, 8, 3000, 3000, "7200100002"),    # b4: tract 2, barrio B: open water (no flood); strict protected area; infrequent current stop with Sunday service near
    ("720010002001003", 10, 0, 6000, 6000, "7200100002"),    # b5: tract 2, barrio B: group quarters (no housing units); protected (GAP 3); low-lying area at 3 ft; no stop
    ("720010002001004", 0, 5, 6000, 0, "7200100001"),        # b6: no residents, housing units; in nothing
    ("720010002001005", 0, 0, 0, 6000, "7200199999"),        # b7: offshore county subdivision that is not a barrio (index -1)
]


def table():
    rows = []
    for geoid, pop, hu, n, e, _ in SPEC:
        lat, lng = at(n, e)
        rows.append([geoid, pop, hu, 1000, lng, lat])
    return {"fields": ["geoid", "pop", "hu", "land_m2", "lon", "lat"], "rows": rows}


def point(i):
    r = table()["rows"][i]
    return r[5], r[4]          # lat, lng


def feature(poly, **props):
    return {"type": "Feature", "properties": props, "geometry": mapping(poly)}


def flood_fc():
    return {"type": "FeatureCollection", "features": [
        feature(around(*point(0)), FLD_ZONE="AE", ZONE_SUBTY="FLOODWAY", SFHA_TF="T"),
        feature(around(*point(1)), FLD_ZONE="X", ZONE_SUBTY="0.2 PCT ANNUAL CHANCE FLOOD HAZARD", SFHA_TF="F"),
        feature(around(*point(2)), FLD_ZONE="X", ZONE_SUBTY="AREA OF MINIMAL FLOOD HAZARD", SFHA_TF="F"),
        feature(around(*point(3)), FLD_ZONE="OPEN WATER", ZONE_SUBTY=None, SFHA_TF="F"),
    ]}


def protected_fc():
    return {"type": "FeatureCollection", "features": [
        feature(around(*point(3)), Des_Tp="NP", GAP_Sts="1", Unit_Nm="strict"),
        feature(around(*point(2)), Des_Tp="PROC", GAP_Sts="1", Unit_Nm="a proclamation boundary"),
        feature(around(*point(4)), Des_Tp="LP", GAP_Sts="3", Unit_Nm="a local park"),
    ]}


def slr(kind, ft):
    """The connected area grows with the height (b3 from 1 ft, b2 from 2 ft); the low-lying area holds b5 at 3 ft only."""
    if kind == "slr":
        return [around(*point(2))] * (ft >= 1) + [around(*point(1))] * (ft >= 2)
    return [around(*point(4))] if ft == 3 else []


# storm surge band codes per block (b1 to b7) and category: 0 dry, 1 under 1 ft, 2 = 1 to 2 ft, ... 4 and up = 3 ft or more
SURGE = {1: [2, 0, 0, 0, 0, 0, 0], 2: [3, 0, 0, 0, 0, 0, 0], 3: [5, 1, 0, 0, 0, 0, 0], 4: [6, 2, 1, 0, 0, 0, 0], 5: [7, 4, 1, 0, 0, 0, 0]}


def surge(cat):
    return np.array(SURGE[cat])


def stops():
    def s(i, kind, source, operator, north, calls, sat=0, sun=0):
        lat, lng = at(*north)
        return {"id": f"s{i}", "kind": kind, "source": source, "operator": operator, "lat": lat, "lng": lng, "trips_weekday": calls, "calls_sat": sat, "calls_sun": sun}
    return [s(1, "transit_stop", "ati_gtfs", "ati", (150, 0), 25, sat=12),                 # 150 m from b1: current, frequent, Saturday
            s(2, "transit_stop", "muni_gtfs", "old", (150, 3000), 8),                      # 150 m from b2: timetable on file, expired
            s(3, "bus_stop", "osm_transport", "osm", (3150, 0), 0),                        # 150 m from b3: mapped by volunteers
            s(4, "transit_stop", "ati_gtfs", "ati", (3150, 3000), 5, sun=3)]               # 150 m from b4: current, not frequent, Sunday


OPERATORS = [{"id": "ati", "feed": {"status": "current", "end": "2027-01-01"}}, {"id": "old", "feed": {"status": "expired", "end": "2026-01-01"}}, {"id": "osm", "feed": {"status": "none"}}]


def crosswalk():
    """A crosswalk of the invented island, with each area's residents and housing units added up from the blocks."""
    def agg(key):
        out = {}
        for geoid, pop, hu, n, e, barrio in SPEC:
            k = key(geoid, barrio)
            a = out.setdefault(k, [0, 0])
            a[0] += pop
            a[1] += hu
        return out
    unit = lambda id_, parent, a: [id_, parent, id_, id_, id_.lower(), 1.0, a[0], a[1], LAT, LNG]   # noqa: E731
    mun, barrio, tract = agg(lambda g, b: g[:5]), agg(lambda g, b: b), agg(lambda g, b: g[:11])
    barrio.pop("7200199999")
    return {"units": {"island": [unit("72", None, [sum(a[0] for a in mun.values()), sum(a[1] for a in mun.values())])],
                      "region": [unit("reg-a", "72", [sum(a[0] for a in mun.values()), sum(a[1] for a in mun.values())])],
                      "municipio": [unit(k, "reg-a", a) for k, a in sorted(mun.items())],
                      "barrio": [unit(k, "72001", a) for k, a in sorted(barrio.items())],
                      "tract": [unit(k, "72001", a) for k, a in sorted(tract.items())], "block-group": []}}


def write_island(tmp):
    d = Path(tmp)
    (d / "geo").mkdir(exist_ok=True)
    (d / "geo" / "crosswalk.json").write_text(json.dumps(crosswalk()), encoding="utf-8")
    (d / "flood.geojson").write_text(json.dumps(flood_fc()), encoding="utf-8")
    (d / "protected.geojson").write_text(json.dumps(protected_fc()), encoding="utf-8")
    (d / "transport.json").write_text(json.dumps(stops()), encoding="utf-8")
    (d / "operators.json").write_text(json.dumps({"operators": OPERATORS}), encoding="utf-8")
    return d


def quiet(fn, *a, **k):
    with redirect_stdout(io.StringIO()):
        return fn(*a, **k)


BARRIO_OF = [s[5] for s in SPEC]


class Layout(unittest.TestCase):
    def test_thirty_families_with_labels_in_both_languages(self):
        self.assertEqual(len(exposure.FAMILIES), 42)   # 30, the two walking families (2026-10-16) and ten storm surge families (2026-11-17)
        self.assertEqual(len(set(exposure.KEYS)), 42)
        for f in exposure.FAMILIES:
            self.assertTrue(f["label"]["en"] and f["label"]["es"], f["key"])
            self.assertIn(f["group"], exposure.GROUPS)
        self.assertEqual(exposure.KEYS[:2], ["flood_sfha", "flood_any"])
        self.assertEqual(len(exposure.STATIC_KEYS) + len(exposure.TRANSIT_KEYS), 42)
        self.assertEqual(exposure.SURGE_KEYS, [f"surge_cat{n}" for n in range(1, 6)] + [f"surge_deep_cat{n}" for n in range(1, 6)])
        self.assertEqual(exposure.TRANSIT_KEYS, ["stop_any", "stop_sched", "stop_cur", "stop_freq", "stop_sat", "stop_sun", "walk_cur", "walk_freq"])   # the walking ones last, so the nightly refresh appends them in build order

    def test_spanish_says_one_foot_in_the_singular(self):
        labels = {f["key"]: f["label"] for f in exposure.FAMILIES}
        self.assertIn("1 pie ", labels["slr_1ft"]["es"])
        self.assertIn("2 pies ", labels["slr_2ft"]["es"])
        self.assertIn("1 ft ", labels["slr_1ft"]["en"])


class Polygons(unittest.TestCase):
    def test_points_inside_outside_on_the_edge_and_in_a_hole(self):
        shell = [(0, 0), (10, 0), (10, 10), (0, 10)]
        hole = [(4, 4), (6, 4), (6, 6), (4, 6)]
        from shapely.geometry import Polygon
        poly = Polygon(shell, [hole])
        x = np.array([2.0, 5.0, 12.0, 0.0, 10.0, 5.0])
        y = np.array([2.0, 5.0, 5.0, 5.0, 10.0, 1.0])
        self.assertEqual(exposure.points_in_polygons([poly], x, y).tolist(), [True, False, False, False, False, True])

    def test_several_polygons_and_nothing(self):
        a, b = box(0, 0, 1, 1), box(5, 5, 6, 6)
        x, y = np.array([0.5, 5.5, 3.0]), np.array([0.5, 5.5, 3.0])
        self.assertEqual(exposure.points_in_polygons([a, b], x, y).tolist(), [True, True, False])
        self.assertFalse(exposure.points_in_polygons([], x, y).any())
        self.assertEqual(len(exposure.points_in_polygons([a], np.array([]), np.array([]))), 0)

    def test_agrees_with_shapely_on_random_points(self):
        rng = np.random.default_rng(7)
        polys = [box(rng.uniform(0, 8), rng.uniform(0, 8), 0, 0).buffer(0) for _ in range(0)] + [box(x, y, x + 2, y + 1.5) for x, y in rng.uniform(0, 8, (40, 2))]
        x, y = rng.uniform(-1, 11, 3000), rng.uniform(-1, 11, 3000)
        import shapely
        want = np.zeros(len(x), dtype=bool)
        for p in polys:
            want |= shapely.contains_xy(p, x, y)
        self.assertEqual(exposure.points_in_polygons(polys, x, y).tolist(), want.tolist())

    def test_flood_rules_are_those_of_the_place_flags(self):
        sfha, any_ = exposure.flood_polygons(flood_fc())
        self.assertEqual((len(sfha), len(any_)), (1, 2))                 # the 1% area; that and the 0.2% area. Unshaded X and open water are left out
        self.assertEqual(exposure.flood_polygons({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"FLD_ZONE": "AE", "SFHA_TF": "T"}, "geometry": None}]}), ([], []))

    def test_protected_rules(self):
        real, strict = exposure.protected_polygons(protected_fc())
        self.assertEqual((len(real), len(strict)), (2, 1))              # the proclamation boundary does not count; GAP status 1 or 2 is strict


class Transit(unittest.TestCase):
    def test_every_class_on_the_invented_island(self):
        blocks = exposure.Blocks(table())
        f = exposure.transit_flags(blocks, stops(), OPERATORS, AS_OF)
        expect = {"stop_any": [1, 1, 1, 1, 0, 0, 0], "stop_sched": [1, 1, 0, 1, 0, 0, 0], "stop_cur": [1, 0, 0, 1, 0, 0, 0],
                  "stop_freq": [1, 0, 0, 0, 0, 0, 0], "stop_sat": [1, 0, 0, 0, 0, 0, 0], "stop_sun": [0, 0, 0, 1, 0, 0, 0]}
        for k, v in expect.items():
            self.assertEqual(f[k].astype(int).tolist(), v, k)
        self.assertEqual(exposure.check_subsets({**f}), [])

    def test_a_timetable_that_ends_stops_counting(self):
        blocks = exposure.Blocks(table())
        f = exposure.transit_flags(blocks, stops(), OPERATORS, date(2027, 6, 1))     # the ATI feed ended on 2027-01-01
        self.assertEqual(f["stop_cur"].sum(), 0)
        self.assertEqual(f["stop_freq"].sum(), 0)
        self.assertEqual(f["stop_sched"].astype(int).tolist(), [1, 1, 0, 1, 0, 0, 0])   # the timetable on file is still on file

    def test_the_distance_rule_is_400_m_with_the_points_rounded_to_four_decimals(self):
        rows = [["720010001001001", 10, 5, 0, *reversed(at(0, 0))], ["720010001001002", 10, 5, 0, *reversed(at(0, 700))]]
        blocks = exposure.Blocks({"rows": rows})
        near = {"id": "s", "kind": "transit_stop", "source": "ati_gtfs", "operator": "ati", "lat": at(390, 0)[0], "lng": at(390, 0)[1], "trips_weekday": 1, "calls_sat": 0, "calls_sun": 0}
        far = dict(near, lat=at(410, 0)[0], lng=at(410, 0)[1])
        self.assertTrue(exposure.transit_flags(blocks, [near], OPERATORS, AS_OF)["stop_cur"][0])
        self.assertFalse(exposure.transit_flags(blocks, [far], OPERATORS, AS_OF)["stop_cur"][0])
        self.assertEqual(blocks.lon4[0], round(rows[0][4], 4))
        self.assertEqual(blocks.lat4[1], round(rows[1][5], 4))


class Units(unittest.TestCase):
    def test_the_unit_of_each_block_at_each_level(self):
        blocks = exposure.Blocks(table())
        ids = {"municipio": ["72001"], "tract": ["72001000100", "72001000200"], "barrio": ["7200100001", "7200100002"]}
        self.assertEqual(exposure.unit_index(blocks, "municipio", ids["municipio"]).tolist(), [0] * 7)
        self.assertEqual(exposure.unit_index(blocks, "tract", ids["tract"]).tolist(), [0, 0, 1, 1, 1, 1, 1])
        self.assertEqual(exposure.unit_index(blocks, "barrio", ids["barrio"], BARRIO_OF).tolist(), [0, 1, 0, 1, 1, 0, -1])   # -1: an offshore subdivision that is not a barrio
        with self.assertRaises(ValueError):
            exposure.unit_index(blocks, "region", ["reg-a"])

    def test_roll_up_counts_residents_and_housing_units_and_skips_blocks_in_no_unit(self):
        blocks = exposure.Blocks(table())
        idx = exposure.unit_index(blocks, "barrio", ["7200100001", "7200100002"], BARRIO_OF)
        flags = {"a": np.array([1, 1, 0, 0, 0, 0, 1], dtype=bool), "b": np.zeros(7, dtype=bool)}
        rolled, total = exposure.roll_up(blocks, idx, 2, flags)
        self.assertEqual(rolled["a"][0].tolist(), [100, 50])
        self.assertEqual(rolled["a"][1].tolist(), [40, 20])
        self.assertEqual(rolled["b"][0].tolist(), [0, 0])
        self.assertEqual(total[0].tolist(), [130, 80])
        self.assertEqual(total[1].tolist(), [55, 28])

    def test_subsets(self):
        f = {"flood_sfha": np.array([1, 0], dtype=bool), "flood_any": np.array([0, 0], dtype=bool), "slr_1ft": np.array([1, 0], dtype=bool), "slr_2ft": np.array([1, 1], dtype=bool)}
        self.assertEqual(exposure.check_subsets(f), [("flood_sfha", "flood_any", 1)])
        self.assertEqual(exposure.check_subsets(f, tolerate=[("flood_sfha", "flood_any")]), [])


class Island(unittest.TestCase):
    """The whole build on the invented island."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = write_island(self.tmp.name)
        quiet(exposure.build, data_dir=self.dir, as_of=AS_OF, out=self.dir, slr=slr, surge=surge, table=table(), barrio_of=BARRIO_OF)
        self.doc = {lv: json.loads((self.dir / exposure.FILE[lv]).read_text(encoding="utf-8")) for lv in exposure.LEVELS}

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_numbers_of_every_family_and_level(self):
        m, b, t = (self.doc[lv] for lv in exposure.LEVELS)
        self.assertEqual(m["total"], {"pop": [210], "hu": [83]})
        v = lambda d, k, meas: d["vars"][k][meas]   # noqa: E731
        # municipio (one area)
        for k, pop, hu in (("flood_sfha", 100, 40), ("flood_any", 150, 60), ("slr_1ft", 30, 10), ("slr_2ft", 80, 30), ("slr_10ft", 80, 30), ("low_3ft", 10, 0), ("low_2ft", 0, 0),
                           ("protected", 30, 8), ("protected_strict", 20, 8), ("stop_any", 200, 78), ("stop_sched", 170, 68), ("stop_cur", 120, 48), ("stop_freq", 100, 40), ("stop_sat", 100, 40), ("stop_sun", 20, 8),
                           ("surge_cat1", 100, 40), ("surge_deep_cat1", 0, 0), ("surge_cat3", 150, 60), ("surge_deep_cat3", 100, 40), ("surge_cat5", 180, 70), ("surge_deep_cat5", 150, 60)):
            self.assertEqual((v(m, k, "pop"), v(m, k, "hu")), ([pop], [hu]), k)
        # barrios A (b1, b3, b6) and B (b2, b4, b5): residents
        self.assertEqual(b["geo"]["ids"], ["7200100001", "7200100002"])
        self.assertEqual(v(b, "flood_sfha", "pop"), [100, 0])
        self.assertEqual(v(b, "flood_any", "pop"), [100, 50])
        self.assertEqual(v(b, "slr_1ft", "pop"), [30, 0])
        self.assertEqual(v(b, "slr_2ft", "pop"), [30, 50])
        self.assertEqual(v(b, "protected", "pop"), [0, 30])
        self.assertEqual(v(b, "stop_cur", "pop"), [100, 20])
        self.assertEqual(v(b, "surge_cat5", "pop"), [130, 50])
        self.assertEqual(b["total"]["pop"], [130, 80])
        # tracts 1 (b1, b2) and 2 (b3 to b6)
        self.assertEqual(t["geo"]["ids"], ["72001000100", "72001000200"])
        self.assertEqual(v(t, "flood_any", "hu"), [60, 0])
        self.assertEqual(v(t, "protected", "hu"), [0, 8])
        self.assertEqual(v(t, "stop_sun", "pop"), [0, 20])
        self.assertEqual(t["total"]["hu"], [60, 23])

    def test_the_files_carry_what_a_consumer_needs(self):
        d = self.doc["municipio"]
        self.assertEqual((d["level"], d["geo"]["level"], d["as_of"]), ("municipio", "municipio", "2026-10-06"))
        self.assertEqual(list(d["vars"]), exposure.KEYS)
        self.assertEqual(set(d["vars"]["flood_sfha"]), {"label", "group", "kind", "pop", "hu"})
        self.assertEqual(d["vars"]["stop_cur"]["kind"], "stops")
        self.assertIn("Computed, not measured", d["basis"]["en"])
        self.assertTrue(d["basis"]["es"].startswith("Calculado"))
        self.assertEqual(set(d["measures"]), {"pop", "hu"})

    def test_the_files_pass_their_own_checks(self):
        self.assertEqual(exposure.check(self.dir), [])

    def test_the_checker_names_each_kind_of_damage(self):
        def damaged(fn):
            docs = copy.deepcopy(self.doc)
            fn(docs)
            for lv, d in docs.items():
                (self.dir / exposure.FILE[lv]).write_text(json.dumps(d), encoding="utf-8")
            text = " | ".join(exposure.check(self.dir))
            for lv in exposure.LEVELS:
                (self.dir / exposure.FILE[lv]).write_text(json.dumps(self.doc[lv]), encoding="utf-8")
            return text
        self.assertIn("ids are not the crosswalk's", damaged(lambda d: d["tract"]["geo"]["ids"].reverse()))
        self.assertIn("total pop is not the crosswalk's", damaged(lambda d: d["barrio"]["total"]["pop"].__setitem__(0, 999)))
        self.assertIn("is larger than flood_any.pop", damaged(lambda d: d["municipio"]["vars"]["flood_sfha"]["pop"].__setitem__(0, 200)))
        self.assertIn("between 0 and the area's total", damaged(lambda d: d["municipio"]["vars"]["protected"]["hu"].__setitem__(0, -1)))
        self.assertIn("between 0 and the area's total", damaged(lambda d: d["municipio"]["vars"]["protected"]["hu"].__setitem__(0, 1.5)))
        self.assertIn("values for", damaged(lambda d: d["tract"]["vars"]["stop_cur"]["pop"].append(0)))
        self.assertIn("do not add up to the municipio rows", damaged(lambda d: d["barrio"]["vars"]["slr_3ft"]["pop"].__setitem__(1, 5)))
        self.assertIn("families are not the expected", damaged(lambda d: d["municipio"]["vars"].pop("stop_sun")))

    def test_a_missing_file_is_reported(self):
        (self.dir / exposure.FILE["tract"]).unlink()
        self.assertIn("exposure_tract.json is missing", " ".join(exposure.check(self.dir)))

    def test_the_build_stops_when_the_blocks_do_not_add_up_to_the_crosswalk(self):
        bad = table()
        bad["rows"][0][1] += 1
        with self.assertRaises(SystemExit) as cm:
            quiet(exposure.build, data_dir=self.dir, as_of=AS_OF, out=self.dir, slr=slr, surge=surge, table=bad, barrio_of=BARRIO_OF)
        self.assertIn("do not add up to the crosswalk", str(cm.exception))

    def test_nothing_is_written_when_a_later_level_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_island(tmp)
            wrong = list(BARRIO_OF)
            wrong[0] = "7200100002"      # block 1 moves to the other barrio: the municipio and tract totals still add up, the barrio totals do not
            with self.assertRaises(SystemExit) as cm:
                quiet(exposure.build, data_dir=d, as_of=AS_OF, out=d, slr=slr, surge=surge, table=table(), barrio_of=wrong)
            self.assertIn("barrio level", str(cm.exception))
            self.assertEqual(sorted(p.name for p in d.glob("exposure_*.json")), [], "the municipio file must not be written when the barrio level fails")

    def test_the_build_stops_when_a_set_is_not_inside_its_superset(self):
        broken = lambda kind, ft: slr(kind, ft) if not (kind == "slr" and ft == 5) else []   # 5 ft loses what 4 ft flooded
        with self.assertRaises(SystemExit) as cm:
            quiet(exposure.build, data_dir=self.dir, as_of=AS_OF, out=self.dir, slr=broken, surge=surge, table=table(), barrio_of=BARRIO_OF)
        self.assertIn("slr_4ft not in slr_5ft", str(cm.exception))


class Nightly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = write_island(self.tmp.name)
        quiet(exposure.build, data_dir=self.dir, as_of=AS_OF, out=self.dir, slr=slr, surge=surge, table=table(), barrio_of=BARRIO_OF)

    def tearDown(self):
        self.tmp.cleanup()

    def run_nightly(self, as_of, **kw):
        lines = []
        written = exposure.apply_transit(self.dir, as_of, log=lines.append, table=kw.pop("table", table()), barrio_of=BARRIO_OF, **kw)
        return written, " ".join(lines)

    def load(self, lv):
        return json.loads((self.dir / exposure.FILE[lv]).read_text(encoding="utf-8"))

    def test_a_night_that_changes_nothing_writes_nothing(self):
        before = {lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}
        written, _ = self.run_nightly(date(2026, 10, 7))
        self.assertEqual(written, [])
        self.assertEqual({lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}, before, "not even the dates are rewritten")

    def test_an_expired_feed_changes_only_the_transit_families(self):
        before = {lv: self.load(lv) for lv in exposure.LEVELS}
        written, text = self.run_nightly(date(2027, 6, 1))
        self.assertEqual(sorted(written), sorted(exposure.FILE.values()))
        self.assertIn("within 400 m of a stop with a current timetable 0 (0.0%; walking 0, 0.0%)", text)
        for lv in exposure.LEVELS:
            after = self.load(lv)
            self.assertEqual(after["as_of"], "2027-06-01")
            self.assertEqual(after["vars"]["stop_cur"]["pop"], [0] * len(after["geo"]["ids"]))
            for k in exposure.STATIC_KEYS + ["stop_any", "stop_sched"]:
                self.assertEqual(after["vars"][k], before[lv]["vars"][k], f"{lv} {k} must not change")
            self.assertEqual(after["total"], before[lv]["total"])
        self.assertEqual(exposure.check(self.dir), [])

    def test_write_false_changes_nothing(self):
        before = (self.dir / exposure.FILE["municipio"]).read_bytes()
        written, text = self.run_nightly(date(2027, 6, 1), write=False)
        self.assertTrue(written)
        self.assertIn("would write", text)
        self.assertEqual((self.dir / exposure.FILE["municipio"]).read_bytes(), before)

    def test_new_census_blocks_stop_the_refresh_without_writing(self):
        other = table()
        other["rows"][1][1] += 7
        before = (self.dir / exposure.FILE["barrio"]).read_bytes()
        written, text = self.run_nightly(date(2027, 6, 1), table=other)
        self.assertEqual(written, [])
        self.assertIn("no longer match", text)
        self.assertEqual((self.dir / exposure.FILE["barrio"]).read_bytes(), before)

    def test_a_mismatch_at_a_later_level_writes_nothing(self):
        wrong = list(BARRIO_OF)
        wrong[0] = "7200100002"
        before = {lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}
        lines = []
        written = exposure.apply_transit(self.dir, date(2027, 6, 1), log=lines.append, table=table(), barrio_of=wrong)
        self.assertEqual(written, [])
        self.assertIn("no longer match", " ".join(lines))
        self.assertEqual({lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}, before, "the municipio file must not change when the barrio level fails")

    def test_unbuilt_files_are_reported(self):
        (self.dir / exposure.FILE["barrio"]).unlink()
        written, text = self.run_nightly(date(2027, 6, 1))
        self.assertEqual(written, [])
        self.assertIn("has not been built", text)


class Surge(unittest.TestCase):
    """python exposure.py --surge: only the ten storm surge families, on the invented island."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = write_island(self.tmp.name)
        quiet(exposure.build, data_dir=self.dir, as_of=AS_OF, out=self.dir, slr=slr, surge=surge, table=table(), barrio_of=BARRIO_OF)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, lv):
        return json.loads((self.dir / exposure.FILE[lv]).read_text(encoding="utf-8"))

    def run_surge(self, bins=surge, **kw):
        return exposure.apply_surge(self.dir, log=lambda *a: None, table=kw.pop("table", table()), barrio_of=BARRIO_OF, bins=bins, **kw)

    def test_band_codes_become_any_depth_and_three_feet_or_more(self):
        class B:
            lon = lat = np.zeros(4)
        f = exposure.surge_flags(B(), bins=lambda c: np.array([0, 1, 3, 4]))
        self.assertEqual(f["surge_cat2"].tolist(), [False, True, True, True])
        self.assertEqual(f["surge_deep_cat2"].tolist(), [False, False, False, True])

    def test_files_built_before_the_surge_maps_get_the_families_in_build_order_and_nothing_else_moves(self):
        before = {}
        for lv in exposure.LEVELS:   # the files as they were before 2026-11-17: no surge families
            d = self.load(lv)
            for k in exposure.SURGE_KEYS:
                del d["vars"][k]
            del d["groups"]["surge"], d["inputs"]["surge"]
            exposure.dump(self.dir / exposure.FILE[lv], d)
            before[lv] = d
        self.assertEqual(sorted(self.run_surge()), sorted(exposure.FILE.values()))
        for lv in exposure.LEVELS:
            after = self.load(lv)
            self.assertEqual(list(after["vars"]), exposure.KEYS)
            for k in before[lv]["vars"]:
                self.assertEqual(after["vars"][k], before[lv]["vars"][k], f"{lv} {k} must not change")
            self.assertEqual((after["built"], after["as_of"], after["total"]), (before[lv]["built"], before[lv]["as_of"], before[lv]["total"]))
        self.assertEqual(self.load("municipio")["vars"]["surge_deep_cat5"]["pop"], [150])
        self.assertEqual(exposure.check(self.dir), [])

    def test_a_second_run_writes_nothing(self):
        before = {lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}
        self.assertEqual(self.run_surge(), [])
        self.assertEqual({lv: (self.dir / exposure.FILE[lv]).read_bytes() for lv in exposure.LEVELS}, before)

    def test_categories_need_not_nest_but_deep_water_must_be_wet(self):
        dry5 = lambda c: np.array([7, 4, 0, 0, 0, 0, 0]) if c == 5 else surge(c)   # noqa: E731  b3 wet at category 4, dry at 5, as five San Juan blocks are
        self.assertEqual(sorted(self.run_surge(dry5)), sorted(exposure.FILE.values()))
        self.assertEqual(exposure.check(self.dir), [])
        for n in range(1, 6):
            self.assertIn((f"surge_deep_cat{n}", f"surge_cat{n}"), exposure.SUBSETS)
            if n < 5:
                self.assertNotIn((f"surge_cat{n}", f"surge_cat{n + 1}"), exposure.SUBSETS)

    def test_new_census_blocks_stop_it_without_writing(self):
        other = table()
        other["rows"][1][1] += 7
        before = (self.dir / exposure.FILE["barrio"]).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_surge(table=other)
        self.assertIn("no longer match", str(cm.exception))
        self.assertEqual((self.dir / exposure.FILE["barrio"]).read_bytes(), before)


class Published(unittest.TestCase):
    """The real files in site/data."""

    @classmethod
    def setUpClass(cls):
        if not all((DATA / exposure.FILE[lv]).exists() for lv in exposure.LEVELS):
            raise unittest.SkipTest("the exposure files have not been built (python exposure.py)")
        cls.doc = {lv: json.loads((DATA / exposure.FILE[lv]).read_text(encoding="utf-8")) for lv in exposure.LEVELS}
        cls.cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))

    def island(self, k, m, lv="municipio"):
        return sum(self.doc[lv]["vars"][k][m])

    def test_the_published_files_pass_their_own_checks(self):
        self.assertEqual(exposure.check(), [])

    def test_the_totals_are_the_crosswalks_and_the_island(self):
        for lv in exposure.LEVELS:
            self.assertEqual(sum(self.doc[lv]["total"]["pop"]), 3285874)
            self.assertEqual(sum(self.doc[lv]["total"]["hu"]), 1598159)
        self.assertEqual([len(self.doc[lv]["geo"]["ids"]) for lv in exposure.LEVELS], [78, 901, 981])

    def test_the_three_levels_give_the_same_island_figure_for_every_family(self):
        for k in exposure.KEYS:
            for m in ("pop", "hu"):
                self.assertEqual(len({self.island(k, m, lv) for lv in exposure.LEVELS}), 1, f"{k}.{m}")

    def test_sea_level_rise_grows_with_the_height(self):
        for m in ("pop", "hu"):
            vals = [self.island(f"slr_{n}ft", m) for n in exposure.FEET]
            self.assertEqual(vals, sorted(vals))
            self.assertGreater(vals[-1], vals[0])

    def test_storm_surge_is_inside_the_flood_and_deep_water_inside_any_water(self):
        for m in ("pop", "hu"):
            for n in range(1, 6):
                for lv in exposure.LEVELS:
                    d = self.doc[lv]["vars"]
                    self.assertTrue(all(a <= b for a, b in zip(d[f"surge_deep_cat{n}"][m], d[f"surge_cat{n}"][m])), f"{lv} {m} category {n}")
            self.assertLessEqual(self.island("surge_cat1", m), self.island("flood_sfha", m))
            self.assertLess(self.island("surge_cat1", m), self.island("surge_cat5", m))
        i = self.doc["municipio"]["geo"]["ids"].index("72033")   # Cataño: over half its residents in the category 5 surge area
        self.assertGreater(self.doc["municipio"]["vars"]["surge_cat5"]["pop"][i] / self.doc["municipio"]["total"]["pop"][i], 0.5)

    def test_the_transit_families_tie_out_with_the_transit_tab(self):
        muni = json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))
        mj = json.loads((DATA / "municipios.geojson").read_text(encoding="utf-8"))
        name = {str(f["properties"]["GEOID"]): f["properties"]["municipality"] for f in mj["features"]}
        d = self.doc["municipio"]
        for i, g in enumerate(d["geo"]["ids"]):
            m, pop = muni[name[g]], d["total"]["pop"][i]
            self.assertEqual(pop, m["population_2020"], name[g])
            if m.get("pop_served_active_pct") is not None:
                self.assertLessEqual(abs(d["vars"]["stop_cur"]["pop"][i] / pop * 100 - m["pop_served_active_pct"]), 0.051, f"{name[g]}: residents near a stop with a current timetable")
            if m.get("pop_served_400m") is not None:
                self.assertLessEqual(abs(d["vars"]["stop_sched"]["pop"][i] - m["pop_served_400m"]) / pop, 0.006, f"{name[g]}: residents near a scheduled stop")

    def test_florida_is_mapped_minimal_hazard_so_it_has_no_flood_or_sea_level_exposure(self):
        i = self.doc["municipio"]["geo"]["ids"].index("72054")
        for k in ("flood_sfha", "flood_any", "slr_10ft"):
            self.assertEqual(self.doc["municipio"]["vars"][k]["pop"][i], 0, k)

    def test_figures_quoted_in_the_dictionary_text_still_hold(self):
        """dictionary_src/entries/exposure.json quotes these; if a rebuild changes one, update the figures in the entries."""
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "exposure.json").read_text(encoding="utf-8"))}
        pairs = {"pop": ("pop", "residents"), "hu": ("hu", "housing units")}
        for m in ("pop", "hu"):
            checks = {f"exposure.{m}_flood": ["flood_sfha", "flood_any"], f"exposure.{m}_slr": ["slr_1ft", "slr_3ft", "slr_10ft"], f"exposure.{m}_protected": ["protected", "protected_strict"],
                      f"exposure.{m}_surge": ["surge_cat1", "surge_cat3", "surge_cat5", "surge_deep_cat3", "surge_deep_cat5"]}
            for eid, keys in checks.items():
                for k in keys:
                    self.assertIn(f"{self.island(k, m):,}", ents[eid]["definition"], f"{eid} quotes {k}; the file says {self.island(k, m):,}")
            best = max(exposure.FEET, key=lambda n: self.island(f"low_{n}ft", m))
            self.assertIn(f"{self.island(f'low_{best}ft', m):,}", ents[f"exposure.{m}_low"]["definition"])
        self.assertIn(f"{sum(self.doc['municipio']['total']['pop']):,}", ents["exposure.total"]["definition"])
        self.assertIn(f"{sum(self.doc['municipio']['total']['hu']):,}", ents["exposure.total"]["definition"])
        self.assertIn("316,309", ents["exposure.method"]["method"])

    def test_the_edge_analysis_was_run_on_these_files_and_the_dictionary_quotes_it(self):
        """docs/analysis/exposure-2026-10/block_edge_bounds.json must describe the published counts, and exposure.method must quote it correctly."""
        edge = json.loads((ROOT / "docs" / "analysis" / "exposure-2026-10" / "block_edge_bounds.json").read_text(encoding="utf-8"))
        fam = edge["families"]
        for k, v in fam.items():
            for m in ("pop", "hu"):
                i = v[m]["island"]
                self.assertEqual(i["point"], self.island(k, m), f"{k}.{m}: the analysis counted a different island total than the published file; run block_edge_bounds.py again")
                self.assertLessEqual(i["lower"], i["point"])
                self.assertLessEqual(i["point"], i["upper"])
                for lv in exposure.LEVELS:
                    self.assertEqual(v[m][lv]["point_outside_bounds"], 0, f"{k}.{m} {lv}")
        text = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "exposure.json").read_text(encoding="utf-8"))}["exposure.method"]["method"]
        self.assertIn(f"{edge['water_free_share']['pop'] * 100:.1f}%", text)
        for k in ("flood_sfha", "slr_3ft", "protected"):
            w = fam[k]["pop"]["island_water_free"]
            for v in (w["point"], w["area_weighted"]):
                self.assertIn(f"{v / w['total'] * 100:.1f}%", text, k)
        i = fam["flood_sfha"]["pop"]["island"]
        for v in (i["lower"], i["upper"], i["point"]):
            self.assertIn(f"{v / i['total'] * 100:.1f}%", text)

    def test_the_spanish_names_the_engine_builds_are_the_files_own(self):
        """The layer stack names a dataset "Residents: " + the family's label; i18n_src/es/labels_exposure.json holds the Spanish of those names and must not drift from the file's own."""
        es = json.loads((ROOT / "i18n_src" / "es" / "labels_exposure.json").read_text(encoding="utf-8"))
        self.assertEqual(es, exposure.spanish_labels(self.doc["municipio"]), "run python exposure.py --labels")
        self.assertEqual(len(es), 98)   # 72, the two walking families for residents and housing units (2026-10-16), and the ten storm surge families and their group (2026-11-17)

    def test_every_family_is_claimed_by_an_entry_at_every_level(self):
        claimed = set()
        for e in json.loads((ROOT / "dictionary_src" / "entries" / "exposure.json").read_text(encoding="utf-8")):
            claimed.update(e["where"]["files"])
        for lv in exposure.LEVELS:
            for k in exposure.KEYS + ["total"]:
                self.assertIn(f"exposure_{lv}.json:{k}", claimed)

    @unittest.skipUnless(os.environ.get("PRDT_SLOW"), "rebuilds everything from the real inputs (about 40 s); set PRDT_SLOW=1")
    def test_a_full_rebuild_gives_the_published_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "geo").mkdir()
            (Path(tmp) / "geo" / "crosswalk.json").write_bytes((DATA / "geo" / "crosswalk.json").read_bytes())
            for name in ("flood.geojson", "protected.geojson", "transport.json", "operators.json"):
                (Path(tmp) / name).write_bytes((DATA / name).read_bytes())
            quiet(exposure.build, data_dir=Path(tmp), as_of=date.fromisoformat(self.doc["municipio"]["as_of"]), out=Path(tmp))
            for lv in exposure.LEVELS:
                new = json.loads((Path(tmp) / exposure.FILE[lv]).read_text(encoding="utf-8"))
                self.assertEqual({k: v for k, v in new.items() if k != "built"}, {k: v for k, v in self.doc[lv].items() if k != "built"}, lv)


if __name__ == "__main__":
    unittest.main()
