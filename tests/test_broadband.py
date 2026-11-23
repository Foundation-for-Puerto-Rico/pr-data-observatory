"""Tests for broadband.py: fixed broadband availability by municipio and barrio (FCC Broadband Data Collection; docs/broadband.md).

  python -m unittest tests.test_broadband

The tiers are checked on rows written here: a location takes its best low-latency service over a reliable technology (served at 100/20 Mbps or more,
underserved at 25/3 or more, unserved otherwise); satellite, unlicensed fixed wireless and high-latency service do not lift it; fiber at any speed counts as
fiber. Without the secrets the build downloads nothing. The published files are checked without the cache: 78 municipios and Puerto Rico, 901 barrios,
shares that follow from the counts, barrios that add up to the municipios and the municipios to Puerto Rico, and no location id. With the cache, the files
must be what it gives.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import broadband  # noqa: E402

DATA = ROOT / "site" / "data"


def row(loc, tech, dl, ul, low="1", block="720010001001000", h="884cee7951fffff"):
    return {"location_id": loc, "technology": tech, "max_advertised_download_speed": str(dl), "max_advertised_upload_speed": str(ul), "low_latency": low, "block_geoid": block,
            "h3_res8_id": h}


class Tiers(unittest.TestCase):
    def counts(self, rows):
        best, fiber, block = {}, set(), {}
        for r in rows:
            broadband.take(r, best, fiber, block)
        return broadband.by_block(best, fiber, block)

    def test_best_reliable_low_latency_service_decides(self):
        c = self.counts([
            row("1", "40", 300, 20),                       # cable 300/20: served
            row("2", "10", 50, 3), row("2", "61", 250, 30),  # copper 50/3 is underserved; low-orbit satellite does not lift it
            row("3", "70", 200, 50),                       # unlicensed fixed wireless only: unserved
            row("4", "71", 100, 20, low="0"),              # licensed fixed wireless, high latency: unserved
            row("5", "10", 10, 1), row("5", "50", 1000, 1000),  # fiber lifts the copper location to served, and counts as fiber
            row("6", "60", 100, 3),                        # geostationary satellite only: unserved
            row("7", "72", 25, 3),                         # licensed-by-rule fixed wireless at exactly 25/3: underserved
            row("8", "50", 10, 2),                         # slow fiber: unserved, but fiber is available
        ])
        self.assertEqual(c, {"720010001001000": [8, 2, 2, 4, 2]})

    def test_a_location_counts_once_in_its_first_block(self):
        c = self.counts([row("1", "40", 300, 20, block="720010001001000"), row("1", "61", 300, 20, block="720010001001000"), row("2", "61", 100, 20, block="720010001001001")])
        self.assertEqual(c, {"720010001001000": [1, 1, 0, 0, 0], "720010001001001": [1, 0, 0, 1, 0]})

    def test_without_secrets_nothing_is_downloaded(self):
        with mock.patch.dict(os.environ, {"FCC_BDC_USERNAME": "", "FCC_BDC_HASH": ""}), mock.patch.object(broadband, "get", side_effect=AssertionError("no request")):
            self.assertEqual(broadband.build(), 0)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "broadband_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "broadband_barrio.json").read_text(encoding="utf-8"))

    def test_shape(self):
        s, b = self.s, self.b
        self.assertEqual(len(s["geo"]["ids"]), 79)
        self.assertEqual(s["geo"]["ids"][-1], "72")
        self.assertEqual(len(b["geo"]["ids"]), 901)
        self.assertEqual([v["key"] for v in s["vars"]], [v["key"] for v in b["vars"]])
        self.assertEqual(s["years"], b["years"])
        self.assertGreaterEqual(min(s["years"]), broadband.FIRST_YEAR)
        for v in s["vars"]:
            self.assertEqual(v["barrioFile"], "broadband_barrio.json")
            self.assertEqual(v["sources"], ["fcc_bdc", "census_tiger"])

    def test_counts_add_up_and_shares_follow(self):
        S = {v["key"]: v["years"] for v in self.s["vars"]}
        B = {v["key"]: v["years"] for v in self.b["vars"]}
        for y in map(str, self.s["years"]):
            n = S["bb_locations"][y]
            self.assertEqual(sum(n[:-1]), n[-1], y)
            self.assertEqual(sum(B["bb_locations"][y]), n[-1], y)
            self.assertTrue(broadband.MIN_N <= n[-1] <= broadband.MAX_N, y)
            self.assertEqual(sum(S["bb_below100_n"][y][:-1]), S["bb_below100_n"][y][-1], y)
            self.assertEqual(sum(B["bb_below100_n"][y]), S["bb_below100_n"][y][-1], y)
            for i in range(79):
                tiers = [S[k][y][i] for k in ("bb_served_pct", "bb_underserved_pct", "bb_unserved_pct")]
                self.assertAlmostEqual(sum(tiers), 100, delta=0.15, msg=(y, i))
                below = (S["bb_underserved_pct"][y][i] + S["bb_unserved_pct"][y][i]) / 100 * n[i]
                self.assertAlmostEqual(below, S["bb_below100_n"][y][i], delta=n[i] * 0.001 + 1, msg=(y, i))
                self.assertTrue(0 <= S["bb_fiber_pct"][y][i] <= 100)
            for i, x in enumerate(B["bb_locations"][y]):
                if x == 0:
                    self.assertIsNone(B["bb_served_pct"][y][i])

    def test_no_location_or_provider_is_published(self):
        for doc in (self.s, self.b):
            txt = json.dumps(doc)
            self.assertNotIn("location_id", txt)
            self.assertNotIn("brand_name", txt)
            self.assertNotIn('"frn"', txt)
            self.assertNotIn("provider_id", txt)

    def test_matches_the_cache_when_there_is_one(self):
        if not list(broadband.CACHE.glob("blocks_*.json")) or not (ROOT / "cache" / "network" / "census_blocks_ids.json").exists():
            self.skipTest("no cached block summaries (they are built in GitHub Actions)")
        with mock.patch("builtins.print"):
            self.assertEqual(broadband.build(check=True), 0)


class Hexagons(unittest.TestCase):
    def test_cells_count_each_location_once_with_its_municipio(self):
        best, fiber, block, hexes = {}, set(), {}, {}
        rows = [row(str(i), "40", 300, 20) for i in range(12)] + [row("5", "50", 1000, 1000)]
        rows += [row("a", "61", 100, 20, h="884cee7953fffff", block="720030001001000"), row("b", "10", 50, 3, h="884cee7953fffff", block="720030001001000"),
                 row("c", "40", 300, 20, h="884cee7953fffff")]
        for r in rows:
            broadband.take(r, best, fiber, block, hexes)
        hx = broadband.by_hex(best, fiber, block, hexes)
        self.assertEqual(hx, {"884cee7951fffff": [12, 12, 0, 0, 1, "72001"], "884cee7953fffff": [3, 1, 1, 1, 0, "72003"]})

    def test_cells_under_the_floor_are_counted_not_drawn(self):
        hx = {"as_of": "2026-06-30", "cells": {"884cee7951fffff": [12, 9, 1, 2, 6, "72001"], "884cee7953fffff": [9, 0, 0, 9, 0, "72001"]}}
        d = broadband.hex_layer(hx)
        self.assertEqual([f["properties"]["h"] for f in d["features"]], ["884cee7951fffff"])
        p = d["features"][0]["properties"]
        self.assertEqual((p["n"], p["below_pct"], p["unserved_pct"], p["fiber_pct"]), (12, 25.0, 16.7, 50.0))
        self.assertEqual((d["notes"]["hexes_left_out"], d["notes"]["locations_left_out"], d["notes"]["locations"]), (1, 9, 21))
        ring = d["features"][0]["geometry"]["coordinates"][0]
        self.assertEqual(len(ring), 7)
        self.assertEqual(ring[0], ring[-1])


class PublishedHexagons(unittest.TestCase):
    def test_no_hexagon_under_the_floor_and_the_counts_add_up(self):
        d = json.loads((DATA / "broadband_hex.geojson").read_text(encoding="utf-8"))
        s = json.loads((DATA / "broadband_series.json").read_text(encoding="utf-8"))
        n = d["notes"]
        pr = next(v for v in s["vars"] if v["key"] == "bb_locations")["years"][n["as_of"][:4]][-1]
        self.assertEqual(n["as_of"][:7], s["as_of"])
        self.assertEqual(n["locations"], pr)
        drawn = sum(f["properties"]["n"] for f in d["features"])
        self.assertEqual(drawn, n["locations_drawn"])
        self.assertEqual(drawn + n["locations_left_out"], pr)
        self.assertEqual(len(d["features"]), n["hexes_drawn"])
        self.assertGreaterEqual(min(f["properties"]["n"] for f in d["features"]), broadband.HEX_MIN)
        for f in d["features"]:
            p = f["properties"]
            self.assertTrue(0 <= p["unserved_pct"] <= p["below_pct"] <= 100, p)
            self.assertEqual(set(p), {"h", "n", "below_pct", "unserved_pct", "fiber_pct", "mun"})


if __name__ == "__main__":
    unittest.main()
