"""Tests for fires.py: vegetation fire detections by municipio (NASA FIRMS, NOAA-20; docs/fires.md).

  python -m unittest tests.test_fires

The filters are checked on rows written here: only type 0 with nominal or high confidence counts from the yearly files. Detections are placed in the municipio
of the barrio that holds them, or the nearest within about 500 m; farther ones are left out. The last 12 months are read from the cache offline and are skipped
without a key or a cache; the key is never written to the cache. The published file is checked without the cache: 78 municipios and Puerto Rico, counts that
add up, the per-100 km² rate that follows from the counts, and the checks the build makes. No point is published.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fires  # noqa: E402

DATA = ROOT / "site" / "data"


class FakeBarrios:
    def __init__(self):
        from shapely.geometry import box
        from shapely.strtree import STRtree
        self.geoms = [box(0, 0, 1, 1), box(1, 0, 2, 1)]
        self.tree = STRtree(self.geoms)
        self.ids = ["72001000001", "72003000001"]


class Filters(unittest.TestCase):
    def test_only_vegetation_fires_with_nominal_or_high_confidence(self):
        self.assertTrue(fires.keep_archive({"type": "0", "confidence": "n"}))
        self.assertTrue(fires.keep_archive({"type": "0", "confidence": "h"}))
        self.assertFalse(fires.keep_archive({"type": "0", "confidence": "l"}))
        self.assertFalse(fires.keep_archive({"type": "2", "confidence": "h"}))
        self.assertFalse(fires.keep_archive({"type": "3", "confidence": "n"}))

    def test_placement_by_barrio_and_the_sea_left_out(self):
        rs = [{"longitude": "0.5", "latitude": "0.5"}, {"longitude": "1.5", "latitude": "0.5"}, {"longitude": "2.003", "latitude": "0.5"},
              {"longitude": "2.5", "latitude": "0.5"}]
        c, sea = fires.counts_by_muni(FakeBarrios(), rs, ["72001", "72003"])
        self.assertEqual(dict(c), {"72001": 1, "72003": 2})
        self.assertEqual(sea, 1)


class Last12(unittest.TestCase):
    def test_without_key_or_cache_it_is_skipped(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fires, "CACHE", Path(d)), mock.patch.dict(os.environ, {fires.KEY_VAR: ""}):
            self.assertIsNone(fires.last12(date(2026, 11, 10)))
            self.assertIsNone(fires.last12(date(2026, 11, 10), offline=True))

    def test_offline_reads_the_newest_cache(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fires, "CACHE", Path(d)):
            for end in ("2026-10-01", "2026-11-09"):
                (Path(d) / f"last12_{end}.csv").write_text("latitude,longitude,acq_date,acq_time,confidence,frp,daynight,source\n18.0,-66.5,2026-03-01,1730,n,3.1,D,VIIRS_NOAA20_NRT\n", encoding="utf-8")
                (Path(d) / f"last12_{end}.json").write_text(json.dumps({"first": "2025-11-10", "last": end, "sources": {"VIIRS_NOAA20_NRT": 1}}), encoding="utf-8")
            rs, span, src = fires.last12(date(2026, 11, 10), offline=True)
        self.assertEqual(span[1], "2026-11-09")
        self.assertEqual(len(rs), 1)

    def test_the_key_never_reaches_the_cache_or_the_file(self):
        key = os.environ.get(fires.KEY_VAR, "")
        if not key:
            self.skipTest("no key here")
        for p in list(fires.CACHE.glob("*")) + [fires.OUT_SERIES]:
            self.assertNotIn(key, p.read_text(encoding="utf-8", errors="replace"))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads(fires.OUT_SERIES.read_text(encoding="utf-8"))
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.land = {r[F["id"]]: r[F["km2"]] for r in cw["units"]["municipio"]}
        cls.V = {v["key"]: v for v in cls.s["vars"]}

    def test_shape(self):
        ids = self.s["geo"]["ids"]
        self.assertEqual(len(ids), 79)
        self.assertEqual(ids[-1], "72")
        self.assertTrue({"fire_n", "fire_per100km2"} <= set(self.V))
        self.assertEqual(self.s["years"][0], fires.FIRST_YEAR)
        for v in self.s["vars"]:
            self.assertEqual(v["sources"], ["nasa_firms", "census_tiger"])
            self.assertNotIn("barrioFile", v)

    def test_counts_add_up_and_rates_follow(self):
        ids = self.s["geo"]["ids"][:-1]
        for y, row in self.V["fire_n"]["years"].items():
            self.assertEqual(sum(row[:-1]), row[-1], y)
            self.assertTrue(fires.MIN_YEAR_N <= row[-1] <= fires.MAX_YEAR_N, (y, row[-1]))
            rate = self.V["fire_per100km2"]["years"][y]
            for m, n, r in zip(ids, row, rate):
                self.assertAlmostEqual(r, round(n / self.land[m] * 100, 1), places=6)
        if "fire_n_12m" in self.V:
            row = next(iter(self.V["fire_n_12m"]["years"].values()))
            self.assertEqual(sum(row[:-1]), row[-1])
            self.assertIsNotNone(self.s["notes"]["last_12_months"])

    def test_the_south_check_holds(self):
        self.assertGreater(self.s["notes"]["south_share"], 0.5)

    def test_no_point_is_published(self):
        text = json.dumps(self.s)
        for word in ('"latitude"', '"longitude"', '"acq_time"'):
            self.assertNotIn(word, text)

    def test_the_cache_rebuilds_the_file_when_it_is_here(self):
        if not list(fires.CACHE.glob("viirs-jpss1_*.csv")):
            self.skipTest("no cache/fires/ here (python fires.py builds it)")
        if "fire_n_12m" in self.V and not list(fires.CACHE.glob("last12_*.csv")):
            self.skipTest("the last 12 months come from the Actions run's artifact")
        self.assertEqual(fires.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
