"""Tests for access.py: how close each tourism place is to a stop with a current timetable.

  python -m unittest discover -s tests -v

A small invented island (a few stops at known distances from a place) checks every rule: which stops count as current, the distances and their rounding,
the call and weekend fields, the access classes, the area shares, and that a day which changes nothing writes nothing. Two tests read the published files in
site/data to check that they agree with the code and with the exploratory figures in docs/visitor-transport-access-2026-10.md.
"""
import json
import math
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import access  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
AS_OF = date(2026, 10, 5)
LAT, LNG = 18.2, -66.2


def at(north_m=0.0, east_m=0.0):
    """(lat, lng) a given number of meters north and east of the origin, on the scale the observatory uses (111,320 m per degree of latitude)."""
    lat = LAT + north_m / 111_320
    lng = LNG + east_m / (111_320 * math.cos(math.radians(LAT + north_m / 222_640)))
    return round(lat, 7), round(lng, 7)


def stop(sid, north=0, east=0, kind="transit_stop", source="ati_gtfs", operator="ati", calls=0, sat=0, sun=0, name=None, municipality="A"):
    lat, lng = at(north, east)
    s = {"id": sid, "kind": kind, "name": name if name is not None else sid, "lat": lat, "lng": lng, "source": source, "operator": operator,
         "municipality": municipality}
    if source != "osm_transport":
        s["trips_weekday"] = calls
        if sat:
            s["calls_sat"] = sat
        if sun:
            s["calls_sun"] = sun
    return s


def place(north=0, east=0, municipality="A", conf=0.9, type_="Restaurants"):
    lat, lng = at(north, east)
    return {"lat": lat, "lng": lng, "municipality": municipality, "confidence": conf, "type": type_, "category": "GASTRONOMY"}


def operators(ati_end="2027-07-19", old_end="2024-12-31", muni_end=AS_OF.isoformat()):
    return [{"id": "ati", "feed": {"status": "current", "end": ati_end}}, {"id": "old", "feed": {"status": "expired", "end": old_end}},
            {"id": "muni", "feed": {"status": "expiring", "end": muni_end}}, {"id": "none", "feed": {"status": "none"}}]


class World(unittest.TestCase):
    """One place with stops around it, and one place far from everything."""

    def setUp(self):
        self.stops = [
            stop("A", north=300, calls=25, sat=3),                                       # current, frequent, Saturday service
            stop("B", east=350, operator="muni", source="muni_gtfs", calls=5, sun=2),    # current (its feed ends today), Sunday service
            stop("C", north=-100, operator="old", source="muni_gtfs", calls=40, name=""),  # expired timetable, the closest stop of all, no name
            stop("D", east=-600, kind="bus_stop", source="osm_transport", operator=None),  # volunteer-mapped
            stop("E", north=1500, kind="rail_station", calls=80, sat=40, sun=20),         # current rail station
            stop("F", north=10, kind="airport"),                                          # not a stop for access
            stop("G", east=700, kind="taxi", source="osm_transport", operator=None),      # not a stop for access
        ]
        self.places = [place(), place(north=60000, east=60000)]
        self.res = access.compute(self.places, self.stops, operators(), AS_OF)

    def test_closest_mapped_stop_is_the_expired_one(self):
        self.assertAlmostEqual(self.res.any_m[0], 100, delta=1)
        self.assertEqual(self.res.stops[int(self.res.any_idx[0])]["id"], "C")
        self.assertTrue(self.res.flags(0)["any400"])

    def test_airports_and_taxi_stands_are_not_stops(self):
        self.assertEqual({s["kind"] for s in self.res.stops}, {"transit_stop", "bus_stop", "rail_station"})

    def test_nearest_current_stop_ignores_expired_and_unscheduled_ones(self):
        self.assertEqual(int(self.res.ts_m[0]), 300 + 0)   # rounded up from a hair over 299.99.. or exactly 300
        self.assertLessEqual(self.res.ts_m[0], 301)
        self.assertGreaterEqual(self.res.ts_m[0], 300)

    def test_calls_and_weekend_flags_come_from_current_stops_within_400_m(self):
        self.assertEqual(int(self.res.ts_calls[0]), 25)       # A (25) and B (5): the larger; C is expired, E is 1.5 km away
        self.assertEqual(int(self.res.ts_we[0]), access.SATURDAY | access.SUNDAY)   # A has Saturday, B has Sunday

    def test_a_feed_that_ends_today_is_current_and_one_that_ended_yesterday_is_not(self):
        self.assertTrue(access.feed_current(operators()[2], AS_OF))
        self.assertFalse(access.feed_current(operators(muni_end="2026-10-04")[2], AS_OF))
        self.assertFalse(access.feed_current({"id": "x", "feed": {"status": "unknown"}}, AS_OF))   # no end date: cannot be shown to cover today
        self.assertFalse(access.feed_current({"id": "x", "feed": {"end": "not a date"}}, AS_OF))
        later = access.compute(self.places, self.stops, operators(), date(2026, 10, 6))
        self.assertEqual(int(later.ts_calls[0]), 25)           # B's feed has ended, A still reaches the place
        self.assertEqual(int(later.ts_we[0]), access.SATURDAY)

    def test_hub_within_400_m_means_a_rail_station_or_ferry_terminal(self):
        self.assertFalse(self.res.flags(0)["hub400"])           # the station is 1.5 km away
        near = access.compute([place()], self.stops + [stop("H", north=200, kind="ferry_terminal")], operators(), AS_OF)
        self.assertTrue(near.flags(0)["hub400"])

    def test_a_place_far_from_every_stop(self):
        self.assertEqual(int(self.res.ts_calls[1]), 0)
        self.assertEqual(int(self.res.ts_we[1]), 0)
        self.assertGreater(self.res.ts_m[1], 40000)
        self.assertEqual(access.access_class(int(self.res.ts_m[1]), 0, int(self.res.any_m[1])), "none")

    def test_distance_is_capped_and_a_world_without_current_stops_is_handled(self):
        res = access.compute([place()], [stop("C", operator="old", source="muni_gtfs")], operators(), AS_OF)
        self.assertEqual(int(res.ts_m[0]), access.CAP_M)
        self.assertEqual(res.n_current, 0)
        self.assertEqual(res.n_expired, 1)
        empty = access.compute([place()], [], operators(), AS_OF)
        self.assertEqual(int(empty.ts_m[0]), access.CAP_M)

    def test_stop_states(self):
        states = [self.res.stop_state(s) for s in self.res.stops]
        self.assertEqual(sorted(states), ["current", "current", "current", "expired", "osm"])   # A, B, E, C, D
        self.assertEqual((self.res.n_current, self.res.n_expired, self.res.n_osm), (3, 1, 1))


class Rounding(unittest.TestCase):
    def test_ts_m_is_rounded_up_so_the_integer_test_matches_the_exact_one(self):
        for north, near in ((399.4, True), (400.6, False)):
            res = access.compute([place()], [stop("A", north=north, calls=3)], operators(), AS_OF)
            self.assertEqual(bool(res.ts_m[0] <= access.NEAR_M), near, north)
            self.assertEqual(res.flags(0)["cur400"], near, north)

    def test_the_legacy_distance_is_cut_not_rounded_and_the_flag_is_dropped_when_false(self):
        places = [place(), place(north=900)]
        stops = [stop("A", north=399.6)]
        res = access.compute(places, stops, operators(), AS_OF)
        self.assertEqual(access.legacy_fields(places, res), 2)
        self.assertEqual(places[0]["transit_m"], 399)
        self.assertTrue(places[0]["transit_400m"])
        self.assertEqual(places[1]["transit_m"], 500)
        self.assertNotIn("transit_400m", places[1])      # a false flag is left out of the record, as in places.json
        self.assertEqual(places[0]["nearest_stop"], "A")
        self.assertEqual(access.legacy_fields(places, res), 0)   # nothing left to change


class Classes(unittest.TestCase):
    def test_rule(self):
        c = access.access_class
        self.assertEqual(c(400, 20, 400), "frequent")
        self.assertEqual(c(400, 19, 400), "basic")
        self.assertEqual(c(401, 80, 10), "near")
        self.assertEqual(c(800, 0, 10), "near")
        self.assertEqual(c(801, 0, 799), "paper")
        self.assertEqual(c(801, 0, 800), "none")      # transit_m is cut: 800 stands for 800.0 to 800.99 m, outside 800 m
        self.assertEqual(c(801, 0, 801), "none")
        self.assertEqual(c(access.CAP_M, 0, 5), "paper")   # no current stop at all, but a mapped one next door

    def test_the_browser_rule_is_the_same_on_the_800_m_edge(self):
        js = (Path(__file__).resolve().parent.parent / "site" / "js" / "access.js").read_text(encoding="utf-8")
        self.assertIn("p.transit_m < ACCESS.far ? 'paper' : 'none'", js)

    def test_the_browser_uses_the_same_rule(self):
        js = (Path(__file__).resolve().parent.parent / "site" / "js" / "access.js").read_text(encoding="utf-8")
        self.assertIn("const ACCESS = { near: 400, far: 800, frequent: 20, bound: 1000 };", js)
        self.assertEqual((access.NEAR_M, access.FAR_M, access.FREQUENT_CALLS, access.WALK_BOUND_M), (400, 800, 20, 1000))


class Areas(unittest.TestCase):
    def test_shares_stop_counts_and_the_default_basis(self):
        stops = [stop("A", north=100, calls=30, sat=1), stop("C", north=-700, operator="old", source="muni_gtfs", calls=4), stop("D", east=5000, kind="bus_stop", source="osm_transport", operator=None, municipality="B")]
        places = [place(north=105), place(north=-695), place(north=3000, east=3000), place(conf=0.3), place(type_="Places of Worship"), place(municipality="B", east=4990)]
        res = access.compute(places, stops, operators(), AS_OF)
        stats = {"A": {}, "B": {}, "C": {}}
        access.municipality_fields(stats, places, res, stops, AS_OF)
        a = stats["A"]
        self.assertEqual(a["access_n"], 3)                       # the low-confidence listing and the place of worship are left out
        self.assertEqual(a["places_near_transit"], 2)            # the first two have a mapped stop within 400 m
        self.assertEqual(a["transit_pct"], 66.7)
        self.assertEqual(a["acc_cur400_pct"], 33.3)              # only the first has a current stop within 400 m
        self.assertEqual(a["acc_freq400_pct"], 33.3)
        self.assertEqual(a["acc_sat400_pct"], 33.3)
        self.assertEqual(a["acc_sun400_pct"], 0.0)
        self.assertEqual(a["acc_paper_pct"], 33.3)               # the second is near only the expired stop
        self.assertEqual((a["stops_current"], a["stops_expired"], a["stops_osm"]), (1, 1, 0))
        self.assertEqual(a["transit_stops"], 2)
        self.assertEqual(stats["B"]["stops_osm"], 1)
        self.assertIsNone(stats["C"]["acc_cur400_pct"])           # a municipality with no places has no share
        self.assertEqual(stats["C"]["access_n"], 0)
        for s in stats.values():
            self.assertEqual(s["stops_current"] + s["stops_expired"] + s["stops_osm"], s["transit_stops"])

    def test_island_summary(self):
        stops = [stop("A", north=100, calls=30)]
        places = [place(north=105), place(north=5000)]
        res = access.compute(places, stops, operators(), AS_OF)
        s = access.island_summary(places, res, operators(), AS_OF)
        self.assertEqual((s["places"], s["cur400_pct"], s["freq400_pct"], s["any400_pct"]), (2, 50.0, 50.0, 50.0))
        self.assertEqual(s["stops"], {"current": 1, "expired": 0, "osm": 0})
        self.assertEqual(s["feeds"], {"current": 2, "expired": 1})   # the operator with no end date is not counted either way


class Files(unittest.TestCase):
    """apply_files on a small data folder: it writes when something changed, and writes nothing on a day that changes nothing."""

    def make(self, folder):
        stops = [stop("A", north=300, calls=25, sat=3, municipality="A"), stop("B", east=350, operator="muni", source="muni_gtfs", calls=5, municipality="A")]
        files = {"places.json": [place(), place(north=900)], "transport.json": stops, "operators.json": {"operators": operators()},
                 "municipalities.json": {"A": {"municipality": "A", "assets": 2}}, "meta.json": {"generated_at": "2026-10-02T02:31:31+00:00", "transport": {"places_near_transit": 0}}}
        for name, doc in files.items():
            (folder / name).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    def test_write_then_nothing_then_a_feed_expires(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            self.make(folder)
            first = access.apply_files(folder, date(2026, 10, 5), log=lambda *_: None)
            self.assertEqual(sorted(first), ["meta.json", "municipalities.json", "place_access.json", "places.json"])
            cols = json.loads((folder / "place_access.json").read_text(encoding="utf-8"))
            self.assertEqual((cols["n"], cols["built"], cols["as_of"]), (2, "2026-10-02T02:31:31+00:00", "2026-10-05"))
            self.assertEqual(cols["ts_calls"], [25, 0])
            meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["access"]["cur400_pct"], 50.0)
            self.assertEqual(meta["transport"]["places_near_transit"], 1)
            # the next day nothing is different, so nothing is written (the nightly job commits only real changes)
            self.assertEqual(access.apply_files(folder, date(2026, 10, 5), log=lambda *_: None), [])
            self.assertEqual(access.apply_files(folder, date(2026, 10, 5), write=False, log=lambda *_: None), [])
            self.assertEqual(json.loads((folder / "place_access.json").read_text(encoding="utf-8"))["as_of"], "2026-10-05")
            # the municipal feed ends on 2026-10-05: on the 6th it is no longer current and the files change
            changed = access.apply_files(folder, date(2026, 10, 6), log=lambda *_: None)
            self.assertIn("place_access.json", changed)
            self.assertEqual(json.loads((folder / "place_access.json").read_text(encoding="utf-8"))["as_of"], "2026-10-06")

    def test_check_mode_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            folder = Path(t)
            self.make(folder)
            self.assertTrue(access.apply_files(folder, AS_OF, write=False, log=lambda *_: None))
            self.assertFalse((folder / "place_access.json").exists())


@unittest.skipUnless((DATA / "place_access.json").exists() and (DATA / "meta.json").exists(), "published files not present")
class Published(unittest.TestCase):
    """The files in site/data agree with the code, and with the exploratory run that justified this work."""

    @classmethod
    def setUpClass(cls):
        cls.meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
        cls.as_of = date.fromisoformat(cls.meta["access"]["as_of"])

    def test_published_files_are_what_the_code_gives_for_their_date(self):
        # not today's date: a feed that expires tomorrow would make this fail without anything being wrong (the nightly refresh is what keeps up with time)
        self.assertEqual(access.apply_files(DATA, self.as_of, write=False, log=lambda *_: None), [])

    def test_the_columns_belong_to_the_places_file(self):
        cols = json.loads((DATA / "place_access.json").read_text(encoding="utf-8"))
        places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))
        self.assertEqual(cols["n"], len(places))
        self.assertEqual(cols["built"], self.meta["generated_at"])
        self.assertTrue(all(len(cols[k]) == cols["n"] for k in ("ts_m", "ts_calls", "ts_we")))
        self.assertTrue(all(0 <= w <= 3 for w in cols["ts_we"]))

    def test_island_shares_match_the_exploratory_run_within_a_fifth_of_a_point(self):
        # docs/visitor-transport-access-2026-10.md (projected meters, EPSG:32161): any 47.0, current 32.1, frequent 21.3, Saturday 22.5, Sunday 6.1, rail or ferry 2.8.
        # The observatory's own flat-earth distance is about 0.6% long north to south, so the shares read up to 0.1 point lower.
        # Pinned to the stops of the exploratory run and to its date: once the nightly job brings new feeds (meta.network.built moves) the figures legitimately change and the test steps aside.
        if self.meta["network"]["built"] != "2026-10-02":
            self.skipTest("the transit data have been refreshed since the exploratory run")
        places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))
        stops = json.loads((DATA / "transport.json").read_text(encoding="utf-8"))
        ops = json.loads((DATA / "operators.json").read_text(encoding="utf-8"))["operators"]
        as_of = date(2026, 10, 5)
        a = access.island_summary(places, access.compute(places, stops, ops, as_of), ops, as_of)
        for key, expected in (("any400_pct", 47.0), ("cur400_pct", 32.1), ("freq400_pct", 21.3), ("sat400_pct", 22.5), ("sun400_pct", 6.1), ("hub400_pct", 2.8)):
            self.assertAlmostEqual(a[key], expected, delta=0.2, msg=key)
        self.assertEqual(a["places"], sum(1 for p in places if access.in_basis(p)))   # the run counted 26,579 places; the basis left out homes, housing and care services on 2026-10-18 (decision 47)

    def test_municipality_stop_counts_add_up(self):
        stats = json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))
        for name, s in stats.items():
            self.assertEqual(s["stops_current"] + s["stops_expired"] + s["stops_osm"], s["transit_stops"], name)
            self.assertEqual(s["access_n"], s["assets"], name)
        transport = json.loads((DATA / "transport.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(s["transit_stops"] for s in stats.values()), sum(1 for f in transport if f["kind"] in access.ANY_KINDS))


if __name__ == "__main__":
    unittest.main()
