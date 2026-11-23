"""Tests for walking distance along mapped roads (walknet.py and access.walking()).

  python -m unittest discover -s tests -v

An invented street plan with known answers: a place at a corner, a stop 300 m up the same street, and a stop 350 m away in a straight line that the
streets reach only by a 950 m detour. Then the fallbacks (a place or a stop with no road nearby), the 1,000 m bound, the published fields, and the
published files (walking is never shorter than the straight line, and the islands shares match the visitor-access study).
"""
import json
import sys
import unittest
from datetime import date
from pathlib import Path

import numpy as np
from shapely import linestrings

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import access  # noqa: E402
import walknet  # noqa: E402
from test_access import AS_OF, LAT, LNG, at, operators, place, stop  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


def street_plan(points, edges):
    """A WalkNet from named points {name: (north_m, east_m)} and edges [(a, b)]: straight streets between the points."""
    names = list(points)
    idx = {n: i for i, n in enumerate(names)}
    lat, lng = zip(*(at(*points[n]) for n in names))
    x, y = walknet.to_xy(lng, lat)
    coords = np.array([[x[idx[a]], y[idx[a]], x[idx[b]], y[idx[b]]] for a, b in edges]).reshape(-1, 2)
    geoms = linestrings(coords, indices=np.repeat(np.arange(len(edges)), 2))
    return walknet.WalkNet([idx[a] for a, _ in edges], [idx[b] for _, b in edges], geoms, len(names))


# a street north from the corner (0, 0) to (300, 0), then east to (300, 350), then south to (0, 350): no street along the bottom
CORNER = {"o": (0, 0), "n": (300, 0), "ne": (300, 350), "e": (0, 350)}
STREETS = [("o", "n"), ("n", "ne"), ("ne", "e")]


class Detour(unittest.TestCase):
    def setUp(self):
        self.net = street_plan(CORNER, STREETS)
        self.stops = [stop("A", north=300, calls=25, sat=3),                                   # up the street: a 300 m walk
                      stop("B", east=350, operator="muni", source="muni_gtfs", calls=40, sun=2)]  # 350 m straight, 950 m on foot
        self.places = [place()]
        self.res = access.compute(self.places, self.stops, operators(muni_end="2027-01-01"), AS_OF, net=self.net)

    def test_walking_follows_the_streets(self):
        self.assertEqual(int(self.res.ts_m[0]), 300)
        self.assertLessEqual(abs(int(self.res.tw_m[0]) - 300), 2, "300 m up the street (the two metrics differ by under 0.3%)")

    def test_calls_and_weekend_come_from_the_stops_within_a_400_m_walk(self):
        self.assertEqual((int(self.res.ts_calls[0]), int(self.res.ts_we[0])), (40, access.SATURDAY | access.SUNDAY), "in a straight line both stops are within 400 m")
        self.assertEqual((int(self.res.tw_calls[0]), int(self.res.tw_we[0])), (25, access.SATURDAY), "on foot only A is: B is a 950 m detour")

    def test_a_detour_moves_a_place_out_of_400_m(self):
        res = access.compute(self.places, self.stops[1:], operators(muni_end="2027-01-01"), AS_OF, net=self.net)
        self.assertIn(int(res.ts_m[0]), (350, 351), "350 m, rounded up (at() keeps 7 decimals: about 1 cm)")
        self.assertGreater(int(res.tw_m[0]), 940)
        self.assertLess(int(res.tw_m[0]), 960)
        f = res.flags(0)
        self.assertTrue(f["cur400"])
        self.assertFalse(f["walk400"])
        self.assertFalse(f["walk800"])
        self.assertEqual((int(res.tw_calls[0]), int(res.tw_we[0])), (0, 0))

    def test_beyond_the_bound_reads_the_cap(self):
        far = {"o": (0, 0), "n": (1200, 0)}
        res = access.compute([place()], [stop("A", north=1200, calls=5)], operators(), AS_OF, net=street_plan(far, [("o", "n")]))
        self.assertEqual(int(res.tw_m[0]), access.CAP_M)
        self.assertEqual(int(res.ts_m[0]), 1200)

    def test_walking_is_never_shorter_than_the_straight_line(self):
        self.assertTrue((self.res.tw_m >= self.res.ts_m).all())

    def test_the_published_fields(self):
        doc = access.columns_doc(self.res, "b")
        self.assertEqual(doc["walk_bound_m"], 1000)
        self.assertEqual((doc["tw_calls"], doc["tw_we"], doc["tw_straight"]), ([25], [1], []))
        s = access.island_summary(self.places, self.res, operators(muni_end="2027-01-01"), AS_OF)
        self.assertEqual((s["walk400_pct"], s["wfreq400_pct"], s["walk"]["places_straight"], s["walk"]["stops_off_road"]), (100.0, 100.0, 0, 0))
        stats = {"A": {"municipality": "A"}}
        access.municipality_fields(stats, self.places, self.res, self.stops, AS_OF)
        self.assertEqual((stats["A"]["acc_walk400_pct"], stats["A"]["acc_wfreq400_pct"], stats["A"]["acc_walk800_pct"]), (100.0, 100.0, 100.0))

    def test_the_class_uses_the_walking_pair(self):
        res = access.compute(self.places, self.stops[1:], operators(muni_end="2027-01-01"), AS_OF, net=self.net)
        self.assertEqual(access.access_class(int(res.ts_m[0]), int(res.ts_calls[0]), 350), "frequent", "straight line")
        self.assertEqual(access.access_class(int(res.tw_m[0]), int(res.tw_calls[0]), 350, int(res.ts_m[0])), "detour",
                         "on foot beyond 800 m, but the stop has a current timetable: not 'only expired or unscheduled stops'")
        self.assertEqual(access.access_class(900, 0, 350, 900), "paper", "no current stop within 800 m either way, a mapped one is")
        self.assertEqual(access.access_class(900, 0, 900, 900), "none")

    def test_the_browser_has_the_detour_class(self):
        js = (Path(__file__).resolve().parent.parent / "site" / "js" / "access.js").read_text(encoding="utf-8")
        self.assertIn("if (p.tw_m != null && p.ts_m <= ACCESS.far) return 'detour';", js)
        self.assertLess(js.index("return 'detour'"), js.index("? 'paper' : 'none'"))


class Fallbacks(unittest.TestCase):
    def test_a_place_with_no_road_nearby_keeps_the_straight_line(self):
        net = street_plan({"a": (1000, 0), "b": (1000, 500)}, [("a", "b")])          # the only street is 1 km north
        res = access.compute([place(), place(north=1000)], [stop("A", north=200, calls=30), stop("B", north=1000, east=100, calls=2)], operators(), AS_OF, net=net)
        self.assertEqual(res.tw_straight.tolist(), [0])
        self.assertEqual((int(res.tw_m[0]), int(res.tw_calls[0])), (int(res.ts_m[0]), int(res.ts_calls[0])))
        self.assertLessEqual(abs(int(res.tw_m[1]) - 100), 2, "the second place is on the street, 100 m from B")
        s = access.island_summary([place(), place(north=1000)], res, operators(), AS_OF)
        self.assertEqual(s["walk"]["places_straight"], 1)

    def test_a_stop_with_no_road_nearby_counts_in_a_straight_line(self):
        net = street_plan({"o": (0, 0), "n": (900, 0)}, [("o", "n")])
        res = access.compute([place()], [stop("X", east=-300, calls=30)], operators(), AS_OF, net=net)   # 300 m west, no street within 150 m
        self.assertEqual(res.n_stops_off_road, 1)
        self.assertEqual((int(res.tw_m[0]), int(res.tw_calls[0])), (int(res.ts_m[0]), 30), "the same metres as the straight line to that stop")
        self.assertIn(int(res.ts_m[0]), (300, 301))

    def test_without_a_road_file_no_walking_fields_are_written(self):
        self.assertIsNone(walknet.load(Path("no such file")))
        res = access.compute([place()], [stop("A", north=300, calls=25)], operators(), AS_OF)
        self.assertIsNone(res.tw_m)
        self.assertNotIn("walk400", res.flags(0))
        self.assertNotIn("tw_m", access.columns_doc(res, "b"))
        self.assertNotIn("walk400_pct", access.island_summary([place()], res, operators(), AS_OF))


class Engine(unittest.TestCase):
    def test_search_from_either_end_gives_the_same_distance(self):
        net = street_plan(CORNER, STREETS)
        p = [{"lat": at(150, 0)[0], "lng": at(150, 0)[1]}]                # halfway up the first street
        s = [{"lat": at(300, 200)[0], "lng": at(300, 200)[1]}]            # 200 m along the second
        per, ok_p, ok_s = walknet.from_stops(net, s, p, 1000)
        pe, pa, pc = net.snap([p[0]["lng"]], [p[0]["lat"]])
        se, sa, sc = net.snap([s[0]["lng"]], [s[0]["lat"]])
        back = net.search(int(pe[0]), float(pa[0]), float(pc[0]), 1000, *net.targets(se, sa, sc))
        self.assertTrue(ok_p[0] and ok_s[0])
        self.assertAlmostEqual(per[0][0], back[0], places=6)
        self.assertAlmostEqual(per[0][0], 350, delta=1.5)

    def test_two_points_on_one_street(self):
        net = street_plan({"o": (0, 0), "n": (500, 0)}, [("o", "n")])
        per, _, _ = walknet.from_stops(net, [{"lat": at(400, 0)[0], "lng": at(400, 0)[1]}], [{"lat": at(100, 20)[0], "lng": at(100, 20)[1]}], 1000)
        self.assertAlmostEqual(per[0][0], 320, delta=1.5, msg="20 m to the street, then 300 m along it")

    def test_motorways_are_not_walkable(self):
        import roads
        self.assertEqual(walknet.NO_WALK, ("motorway", "motorway_link"))
        self.assertTrue(all(c in roads.CLS for c in walknet.NO_WALK))


@unittest.skipUnless((DATA / "place_access.json").exists() and (DATA / "roads.bin").exists(), "published files not present")
class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cols = json.loads((DATA / "place_access.json").read_text(encoding="utf-8"))
        cls.places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))
        cls.meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    def test_the_walking_columns_belong_to_the_places_file(self):
        c = self.cols
        self.assertTrue(all(len(c[k]) == c["n"] for k in ("tw_m", "tw_calls", "tw_we")))
        self.assertTrue(all(w >= s for w, s in zip(c["tw_m"], c["ts_m"])), "a walk is never shorter than the straight line")
        self.assertTrue(all(c["tw_m"][i] == c["ts_m"][i] and c["tw_calls"][i] == c["ts_calls"][i] for i in c["tw_straight"]))
        straight = set(c["tw_straight"])
        self.assertTrue(all(w <= c["walk_bound_m"] or w == access.CAP_M for i, w in enumerate(c["tw_m"]) if i not in straight),
                        "a measured walk is within the bound, else the cap (a place measured in a straight line keeps its ts_m, which can be farther)")
        self.assertTrue(all((k > 0) <= (w <= access.NEAR_M) for k, w in zip(c["tw_calls"], c["tw_m"])))

    def test_the_island_share_is_the_recount(self):
        basis = [i for i, p in enumerate(self.places) if access.in_basis(p)]
        n = sum(1 for i in basis if self.cols["tw_m"][i] <= access.NEAR_M)
        self.assertEqual(self.meta["access"]["walk400_pct"], round(n / len(basis) * 100, 1))

    def test_the_share_matches_the_visitor_access_study(self):
        # REPORT.md section 4.3: 26.6% within a 400 m walk when the places with no road within 150 m count as out. The build counts them at their
        # straight-line distance instead, so adding back those of them within 400 m in a straight line must give the published share.
        if self.meta["network"]["built"] != "2026-10-02":
            self.skipTest("the transit data have been refreshed since the study")
        basis = [i for i, p in enumerate(self.places) if access.in_basis(p)]
        straight = set(self.cols["tw_straight"])
        walked = sum(1 for i in basis if i not in straight and self.cols["tw_m"][i] <= access.NEAR_M)
        self.assertAlmostEqual(walked / len(basis) * 100, 26.6, delta=0.3)

    def test_the_browser_reads_the_walking_columns(self):
        js = (Path(__file__).resolve().parent.parent / "site" / "js" / "access.js").read_text(encoding="utf-8")
        for s in ("p.tw_m = access.tw_m[i]", "const walkM = p => p.tw_m ?? p.ts_m;", "access.tw_straight", "ACCESS.bound = access.walk_bound_m"):
            self.assertIn(s, js)
        # the 3D page's place pins carry the walking fields, so a click shows the same class as a search (review of PR #41)
        js3d = (Path(__file__).resolve().parent.parent / "site" / "js" / "twin3d.js").read_text(encoding="utf-8")
        self.assertIn("tw_m: p.tw_m, tw_calls: p.tw_calls, tw_we: p.tw_we, tw_straight: p.tw_straight", js3d)


class Residents(unittest.TestCase):
    """network.coverage with a walking network: the detour street plan, with census blocks instead of places."""

    def test_a_block_near_in_a_straight_line_can_be_far_on_foot(self):
        import network
        net = street_plan(CORNER, STREETS)
        ati = stop("A", north=300, calls=25); muni = stop("B", east=350, operator="muni", source="muni_gtfs", calls=40)
        blk = lambda north, east, pop: [at(north, east)[1], at(north, east)[0], pop, "72001"]
        blocks = [blk(0, 0, 100), blk(1000, 1000, 7)]        # the corner, and a block with no street within 150 m
        out, cov = network.coverage(blocks, [ati, muni], {"72001": "A"}, inactive_ops={"ati"}, net=net)
        c = cov["A"]
        self.assertIn(out[0][3], (299, 300), "straight line to A, cut to whole metres (at() keeps 7 decimals: about 1 cm)")
        self.assertLessEqual(abs(out[0][4] - 300), 2, "walked up the street to A")
        self.assertEqual(out[1][4], out[1][3], "no street nearby: the walk repeats the straight line")
        self.assertEqual((c["served"], c["walk_served"]), (100, 100))
        self.assertEqual((c["served_active"], c["walk_served_active"]), (100, 0), "B (active) is 350 m in a straight line but a 950 m walk; A is expired")
        self.assertEqual(c["walk_served_active_pct"], 0.0)

    def test_without_a_network_nothing_changes(self):
        import network
        out, cov = network.coverage([[LNG, LAT, 5, "72001"]], [stop("A", north=300)], {"72001": "A"})
        self.assertEqual(len(out[0]), 4)
        self.assertNotIn("walk_served", cov["A"])


@unittest.skipUnless((DATA / "population_blocks.json").exists() and (DATA / "exposure_municipio.json").exists(), "published files not present")
class PublishedResidents(unittest.TestCase):
    def test_the_blocks_and_the_shares_agree(self):
        blocks = json.loads((DATA / "population_blocks.json").read_text(encoding="utf-8"))
        self.assertTrue(all(len(b) == 5 and b[4] >= b[3] for b in blocks), "a walk is never shorter than the straight line")
        ops = json.loads((DATA / "operators.json").read_text(encoding="utf-8"))["coverage"]
        stats = json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(c["walk_served"] for c in ops.values()), sum(b[2] for b in blocks if b[4] <= 400), "the counts are the blocks within a 400 m walk")
        for name, c in ops.items():
            self.assertEqual((stats[name]["pop_walk_400m"], stats[name]["pop_walk_active_pct"]), (c["walk_served"], c["walk_served_active_pct"]), name)
        meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))["network"]
        self.assertEqual(meta["residents_walk_400m"], sum(c["walk_served"] for c in ops.values()))

    def test_the_two_resident_measures_by_walking_are_one(self):
        # network.coverage (the Transit tab, municipalities.json) and exposure.py (the engine's series) walk the same blocks to the same stops
        ops = json.loads((DATA / "operators.json").read_text(encoding="utf-8"))["coverage"]
        exp = json.loads((DATA / "exposure_municipio.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(c["walk_served_active"] for c in ops.values()), sum(exp["vars"]["walk_cur"]["pop"]))
        self.assertTrue(all(w <= s for w, s in zip(exp["vars"]["walk_cur"]["pop"], exp["vars"]["stop_cur"]["pop"])))

    def test_the_mobility_headline_is_by_walking(self):
        doms = json.loads((Path(__file__).resolve().parent.parent / "dictionary_src" / "domains.json").read_text(encoding="utf-8"))
        text = json.dumps(doms)
        self.assertIn('"variable": "municipalities.pop_walk_active_pct"', text)


if __name__ == "__main__":
    unittest.main()
