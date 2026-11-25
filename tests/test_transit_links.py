"""transit_links.py: the workers who travel between municipios, the route listed for each pair, the simulated connections and the público routes of 2020.
The rules are tested on small made-up inputs; the published files are checked against each other and, where the downloads are cached, against a rebuild."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shapely.geometry import box   # noqa: E402

import transit_links as tl   # noqa: E402

DATA = ROOT / "site" / "data"


def muni(geoid, name, x0, x1):
    """A made-up municipio: a 10 km square, its center in the middle."""
    k = 10000
    lng, lat = (x0 + x1) / 2 * k / tl.KX, 0.5 * k / tl.KY
    return {"geoid": geoid, "name": name, "lat": lat, "lng": lng, "geom_m": box(x0 * k, 0, x1 * k, k)}


def wkt(points):
    return "MULTILINESTRING ((" + ", ".join(f"{x / tl.KX} {y / tl.KY}" for x, y in points) + "))"


def csv_bytes(rows):
    out = "the_geom,Nombre,Codigo,Rumbo\n" + "".join(f'"{g}","{n}","{c}","{n}"\n' for g, n, c in rows)
    return out.encode("utf-8-sig")


class Rules(unittest.TestCase):
    MUNIS = [muni("72001", "A", 0, 1), muni("72003", "B", 1, 2), muni("72005", "C", 2, 3)]

    def test_a_route_joins_where_it_ends_and_the_centres_it_passes(self):
        through = wkt([(5000, 5000), (15000, 5000), (25000, 5000)])   # ends in A and C, passes B's center
        bypass = wkt([(5000, 9500), (15000, 9500), (25000, 9500)])    # ends in A and C, crosses B 4.5 km from its center
        local = wkt([(5000, 5000), (5000, 8000)])
        r = {x["code"]: x for x in tl.publicos(csv_bytes([(through, "A - C via B", "I-1"), (bypass, "A - C", "I-2"), (local, "A - Bo. X", "L-1")]), self.MUNIS)}
        self.assertEqual(r["I-1"]["munis"], ["72001", "72003", "72005"])
        self.assertEqual(r["I-2"]["munis"], ["72001", "72005"], "a route that only crosses a municipio far from its center does not join it")
        self.assertEqual(r["L-1"]["munis"], ["72001"])
        self.assertEqual(tl.publico_pairs(list(r.values())), {("72001", "72003"): ["I-1"], ("72001", "72005"): ["I-1", "I-2"], ("72003", "72005"): ["I-1"]})

    def test_rows_of_one_code_are_one_route(self):
        there, back = wkt([(5000, 5000), (15000, 5000)]), wkt([(15000, 5100), (5000, 5100)])
        r = tl.publicos(csv_bytes([(there, "A - B", "I-9 (1"), (back, "B - A", "I-9")]), self.MUNIS)
        self.assertEqual([(x["code"], x["rows"], x["munis"]) for x in r], [("I-9", 2, ["72001", "72003"])], "the truncated note of a code is dropped and its rows joined")

    def test_a_file_with_other_columns_stops_the_build(self):
        with self.assertRaises(SystemExit):
            tl.publicos(b"geom,name\nx,y\n", self.MUNIS)


class TransitTimes(unittest.TestCase):
    def test_a_direct_trip_and_one_with_a_transfer(self):
        """Two municipios 10 km apart: a bus from A's center to a stop on the way (7:00 to 7:10), a second bus from a stop 100 m away to B's center
        (7:20 to 7:40). Leaving A at 7:00 arrives at 7:40: 40 minutes, one transfer. A third municipio with no stop near its center has no trip."""
        from unittest import mock
        k = 10000
        a, b, c = muni("72001", "A", 0, 1), muni("72003", "B", 1, 2), muni("72005", "C", 2, 3)
        to_deg = lambda x, y: (x / tl.KX, y / tl.KY)
        sa, sm, sm2, sb = to_deg(0.5 * k, 0.5 * k), to_deg(1.0 * k, 0.5 * k), to_deg(1.0 * k + 100, 0.5 * k), to_deg(1.5 * k, 0.5 * k)
        files = {"transport.json": [{"id": i, "lng": p[0], "lat": p[1], "source": "ati_gtfs"} for i, p in (("sa", sa), ("sm", sm), ("sm2", sm2), ("sb", sb))],
                 "trips.json": {"day": "test", "path_stops": [["sa", "sm"], ["sm2", "sb"]],
                                "trips": [{"o": "x", "r": "1", "k": 0, "s": [0, 1], "t": [7 * 3600, 7 * 3600 + 600]},
                                          {"o": "x", "r": "2", "k": 1, "s": [0, 1], "t": [7 * 3600 + 1200, 7 * 3600 + 2400]}]}}
        pairs = [{"a": "72001", "b": "72003"}, {"a": "72001", "b": "72005"}]
        with mock.patch.object(tl, "read", lambda name: files[name]):
            info, stop_km = tl.transit_times(pairs, [a, b, c])
        self.assertEqual((pairs[0]["tt_best"], pairs[0]["tt_xfers"]), (40, 1))
        self.assertGreater(pairs[0]["tt_typ"], 40, "the median over the departures counts the wait")
        self.assertEqual((pairs[1].get("tt_best"), pairs[1]["tt_why"]), (None, 1))
        self.assertEqual((info["pairs_with_a_journey"], info["centres_without_a_stop"]), (1, 1))
        self.assertEqual(stop_km["72001"], 0.0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((DATA / "transit_links.json").read_text(encoding="utf-8"))
        cls.links = json.loads((DATA / "simulated_links.geojson").read_text(encoding="utf-8"))
        cls.pub = json.loads((DATA / "publicos.geojson").read_text(encoding="utf-8"))
        cls.pairs = [dict(zip(cls.d["pair_fields"], r)) for r in cls.d["pairs"]]
        cls.munis = [dict(zip(cls.d["muni_fields"], r)) for r in cls.d["municipios"]]

    def test_totals_add_up(self):
        pr = self.d["pr"]
        self.assertEqual(len(self.munis), 78)
        self.assertEqual(pr["pairs"], len(self.pairs))
        self.assertEqual(pr["other_municipio"], sum(p["workers"] for p in self.pairs))
        self.assertEqual(pr["workers"], pr["same_municipio"] + pr["other_municipio"] + pr["outside_pr"])
        self.assertEqual(sum(v["pairs"] for v in pr["by_status"].values()), len(self.pairs))
        self.assertEqual(sum(v["workers"] for v in pr["by_status"].values()), pr["other_municipio"])
        for s, v in pr["by_status"].items():
            self.assertEqual(v["workers"], sum(p["workers"] for p in self.pairs if p["status"] == s), s)
        self.assertEqual(sum(m["work_elsewhere"] for m in self.munis), pr["other_municipio"], "everyone who leaves a municipio to work is in a pair")
        self.assertEqual(sum(m["come_in"] for m in self.munis), pr["other_municipio"])
        self.assertEqual(sum(m["resident_workers"] for m in self.munis), pr["workers"] - pr["outside_pr"])

    def test_every_pair_is_sound(self):
        ids = {m["geoid"] for m in self.munis}
        seen = set()
        for p in self.pairs:
            self.assertLess(p["a"], p["b"])
            self.assertTrue({p["a"], p["b"]} <= ids)
            self.assertNotIn((p["a"], p["b"]), seen)
            seen.add((p["a"], p["b"]))
            self.assertEqual(p["workers"], p["ab"] + p["ba"])
            self.assertEqual(p["low"], p["moe"] >= p["workers"])
            self.assertIn(p["status"], tl.STATUSES)
            self.assertEqual(p["status"] in ("timetable", "expired"), p["tt_routes"] > 0)
            if p["status"] == "publico":
                self.assertGreater(p["publicos"], 0)
            if p["status"] == "none":
                self.assertEqual(p["publicos"], 0)
            if p["via"]:
                self.assertNotEqual(p["status"], "timetable")

    def test_a_simulated_connection_is_only_drawn_where_the_rule_says(self):
        rule = [p for p in self.pairs if p["workers"] >= tl.SIM_MIN_WORKERS and not p["low"] and p["status"] in ("publico", "none") and p["km"] is not None]
        sims = [p for p in self.pairs if p["sim"]]
        self.assertEqual({(p["a"], p["b"]) for p in sims}, {(p["a"], p["b"]) for p in rule})
        self.assertEqual(sorted(p["sim"] for p in sims), list(range(1, len(sims) + 1)))
        by_rank = sorted(sims, key=lambda p: p["sim"])
        self.assertEqual([p["workers"] for p in by_rank], sorted((p["workers"] for p in sims), reverse=True), "rank 1 is the pair with the most workers")
        pr, feats = self.d["pr"], self.links["features"]
        self.assertEqual(pr["simulated"], len(sims))
        self.assertEqual(len(feats), len(sims))
        by_pair = {(p["a"], p["b"]): p for p in sims}
        for f in feats:
            q = f["properties"]
            p = by_pair[(q["geoid_a"], q["geoid_b"])]
            self.assertEqual((q["rank"], q["workers"], q["moe"], q["km"], q["min"], q["publicos"], q["via"]), (p["sim"], p["workers"], p["moe"], p["km"], p["min"], p["publicos"], p["via"]))
            self.assertEqual(q["c"], 2 if p["status"] == "publico" else 1)
            self.assertEqual(q["type"], tl.SIM_TYPES[p["status"]])
            self.assertIn(f["geometry"]["type"], ("LineString", "MultiLineString"))
        n = self.links["notes"]
        self.assertEqual((n["links"], n["none_listed"], n["with_publico_2020"]), (len(feats), sum(1 for f in feats if f["properties"]["c"] == 1), sum(1 for f in feats if f["properties"]["c"] == 2)))

    def test_the_islands_have_no_road_to_the_main_island(self):
        name = {m["geoid"]: m["name"] for m in self.munis}
        for p in self.pairs:
            island = {name[p["a"]], name[p["b"]]} & {"Vieques", "Culebra"}
            self.assertEqual(p["km"] is None, bool(island), f"{name[p['a']]} - {name[p['b']]}")

    def test_the_publico_layer_matches_its_notes_and_the_pairs(self):
        feats, n = self.pub["features"], self.pub["notes"]
        self.assertEqual(n["routes"], len(feats))
        self.assertEqual(n["between_municipios"], sum(1 for f in feats if f["properties"]["type"] == tl.PUBLICO_TYPES[True]))
        self.assertEqual(self.d["publicos"]["routes"], len(feats))
        names = {m["name"] for m in self.munis}
        for f in feats:
            q = f["properties"]
            self.assertEqual(set(q), {"type", "code", "name", "municipio"}, "the layer keeps the route's code, name and municipios, nothing else")
            ms = q["municipio"].split(", ")
            self.assertTrue(set(ms) <= names and ms, q)
            self.assertEqual(q["type"], tl.PUBLICO_TYPES[len(ms) > 1])

    def test_the_layers_types_are_the_ones_the_maps_name(self):
        src = (ROOT / "site" / "js" / "core" / "facilities.js").read_text(encoding="utf-8")
        for t in list(tl.SIM_TYPES.values()) + list(tl.PUBLICO_TYPES.values()):
            self.assertIn(f"TK('{t}')", src)

    def test_every_timetabled_pair_follows_its_route_not_a_straight_line(self):
        tt = json.loads((DATA / "timetabled_links.geojson").read_text(encoding="utf-8"))
        have = {(f["properties"]["geoid_a"], f["properties"]["geoid_b"]): f for f in tt["features"]}
        want = {(p["a"], p["b"]) for p in self.pairs if p["status"] == "timetable"}
        self.assertEqual(set(have), want)
        for k, f in have.items():
            self.assertGreater(len(f["geometry"]["coordinates"]), 2, f"{f['properties']['name']} is drawn as a straight line")
            self.assertIn(f["properties"]["mode"], ("bus", "rail", "ferry", "road"))
        islands = {("72037", "72147"), ("72037", "72049")}   # Ceiba–Vieques, Ceiba–Culebra: the ferry, never a road or a straight line
        for k in islands & set(have):
            self.assertEqual(have[k]["properties"]["mode"], "ferry")

    def test_a_stop_counts_where_its_point_is(self):
        """transport.json puts the Cataño terminal in San Juan (nearest town center); place_stops puts it in Cataño, whose outline is nearest."""
        munis = [muni("72033", "Cataño", 0, 1), muni("72127", "San Juan", 1.05, 2)]
        stops = [{"id": "pier", "lng": 0.5 * 10000 / tl.KX, "lat": -50 / tl.KY, "municipality": "San Juan"},   # 50 m off Cataño's shore
                 {"id": "in", "lng": 1.5 * 10000 / tl.KX, "lat": 0.5 * 10000 / tl.KY}]
        self.assertEqual(tl.place_stops(stops, munis), {"pier": "72033", "in": "72127"})

    def test_the_second_pass_figures_are_consistent(self):
        m = {r["geoid"]: r for r in self.munis}
        for p in self.pairs:
            if p["tt_best"] is not None:
                self.assertIsNone(p["tt_why"])
                self.assertTrue(0 < p["tt_best"] <= p["tt_typ"] <= 180 and p["tt_xfers"] >= 0, p)
            else:
                self.assertIn(p["tt_why"], (1, 2), p)
                near = max(m[p["a"]]["stop_km"], m[p["b"]]["stop_km"])
                self.assertTrue(near >= 0.95 if p["tt_why"] == 1 else near <= 1.05, (p["a"], p["b"], near))
            if p["sim"]:
                self.assertTrue(0 <= p["along_far"] <= p["along_res"], p)
                self.assertIsInstance(p["bridges_poor"], int)
            else:
                self.assertIsNone(p["along_res"])
        self.assertTrue(all(0 <= r["no_vehicle_pct"] < 100 and 0 <= r["poverty_pct"] < 100 for r in self.munis))
        self.assertEqual(self.d["transit_time"]["pairs_with_a_journey"], sum(1 for p in self.pairs if p["tt_best"] is not None))

    def test_the_files_are_what_the_cache_gives(self):
        if not (tl.CACHE / "rutas_publicos.csv").exists() or not (tl.CACHE / "commuting_flows_2016_2020.xlsx").exists():
            self.skipTest("the downloads are not cached here (cache/transit_links/)")
        self.assertEqual(tl.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
