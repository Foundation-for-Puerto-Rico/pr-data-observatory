"""Tests for landslide.py: landslide susceptibility by barrio and municipio (USGS, Hughes and Schulz 2020; docs/landslide.md).

  python -m unittest tests.test_landslide

The PNG reader is checked on tiles made here with every row filter, the colour rule on the legend's colours and on one that is not in it, the pixel areas on the sphere. The published
files are checked without the cache: the 901 barrios in the crosswalk's order, shares between 0 and 100 and the five class datasets that add up to 100, residents never above the barrio's, no value
only where the map does not reach, the municipios as the sums of their barrios, and the two checks against the report. With the cache of tiles, a rebuild gives the files again.
"""
import json
import math
import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import landslide as ls  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"


def png(idx, palette, alpha=None, filters=None):
    """A palette PNG (colour type 3, depth 8) of the rows `idx`, each row written with filters[i] (0 to 4)."""
    h, w = len(idx), len(idx[0])
    raw, prev = b"", [0] * w
    for y, row in enumerate(idx):
        f = (filters or [0] * h)[y]
        out, a, c = [], 0, 0
        for x, v in enumerate(row):
            up = prev[x]
            left = row[x - 1] if x else 0
            ul = prev[x - 1] if x else 0
            if f == 0:
                out.append(v)
            elif f == 1:
                out.append((v - left) & 255)
            elif f == 2:
                out.append((v - up) & 255)
            elif f == 3:
                out.append((v - ((left + up) >> 1)) & 255)
            else:
                p = left + up - ul
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - ul)
                pr = left if pa <= pb and pa <= pc else up if pb <= pc else ul
                out.append((v - pr) & 255)
        raw += bytes([f] + out)
        prev = row

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    body = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) + chunk(b"PLTE", b"".join(bytes(c) for c in palette))
    if alpha:
        body += chunk(b"tRNS", bytes(alpha))
    return b"\x89PNG\r\n\x1a\n" + body + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class Reading(unittest.TestCase):
    def test_every_row_filter_is_undone(self):
        rows = [[(x * 7 + y * 13) % 5 for x in range(9)] for y in range(5)]
        got, plte, trns = ls.png_indexed(png(rows, [(0, 0, 0)] * 5, filters=[0, 1, 2, 3, 4]))
        self.assertEqual(got.tolist(), rows)
        self.assertIsNone(trns)

    def test_colours_become_classes_and_transparent_is_no_data(self):
        pal = [(253, 253, 253), (204, 204, 204), (255, 255, 0), (255, 170, 0), (255, 0, 0), (0, 92, 230)]
        rows = [[0, 1, 2, 3, 4, 5]]
        cls = ls.tile_classes(png(rows, pal, alpha=[0, 255, 255, 255, 255, 255]))
        self.assertEqual(cls.tolist(), [[0, 1, 2, 3, 4, 5]])

    def test_a_colour_outside_the_legend_stops_the_build(self):
        with self.assertRaises(SystemExit):
            ls.tile_classes(png([[0, 1]], [(204, 204, 204), (10, 20, 30)]))
        with self.assertRaises(SystemExit):   # a half-transparent pixel would be a blend of classes
            ls.tile_classes(png([[0]], [(204, 204, 204)], alpha=[128]))

    def test_pixel_areas_shrink_with_the_latitude(self):
        x, y = 10312, 14694   # a zoom-15 tile over Utuado
        lon, lat, area = ls.pixel_grid(x, y)
        w, s, e, n = ls.tile_box(x, y)
        self.assertTrue(w < lon.min() < lon.max() < e and s < lat.min() < lat.max() < n)
        res = 2 * math.pi * ls.EARTH / (256 * 2 ** ls.Z)
        self.assertAlmostEqual(float(area[128, 0]), (res * math.cos(math.radians(float(lat[128, 0])))) ** 2, places=6)
        self.assertTrue(4.4 < math.sqrt(float(area[0, 0])) < 4.6, "about 4.5 m on the ground at 18 degrees north")

    def test_the_tiles_cover_the_main_island_only(self):
        tiles = ls.tile_range()
        boxes = [ls.tile_box(x, y) for x, y in tiles]
        self.assertLessEqual(min(b[0] for b in boxes), -67.30)
        self.assertGreaterEqual(max(b[2] for b in boxes), -65.56)
        self.assertGreater(min(b[0] for b in boxes), -67.32, "Mona and Desecheo (west of -67.4) are not in the model")


@unittest.skipUnless((DATA / "landslide_series.json").exists() and (DATA / "landslide_barrio.json").exists(), "the landslide files are not built yet")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = json.loads((DATA / "landslide_series.json").read_text(encoding="utf-8"))
        cls.b = json.loads((DATA / "landslide_barrio.json").read_text(encoding="utf-8"))
        cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        cls.barrios = [r[F["id"]] for r in cw["units"]["barrio"]]
        cls.pop = {r[F["id"]]: r[F["pop"]] for r in cw["units"]["barrio"]}
        cls.y = str(ls.MAP_YEAR)

    def val(self, doc, key):
        return next(v for v in doc["vars"] if v["key"] == key)["years"][self.y]

    def test_901_barrios_in_the_crosswalks_order_and_the_municipios_then_puerto_rico(self):
        self.assertEqual(len(self.b["geo"]["ids"]), 901)
        self.assertEqual(self.b["geo"]["ids"], self.barrios)
        self.assertEqual(len(self.s["geo"]["ids"]), 79)
        self.assertEqual(self.s["geo"]["ids"][-1], "72")
        for doc, n in ((self.s, 79), (self.b, 901)):
            self.assertEqual([v["key"] for v in doc["vars"]], ["ls_land_high_pct", "ls_land_vhigh_pct", "ls_res_high", "ls_res_high_pct"] + [k for k, _, _ in ls.CLASS_VARS])
            for v in doc["vars"]:
                self.assertEqual(list(v["years"]), [self.y])
                self.assertEqual(len(v["years"][self.y]), n)
            self.assertNotIn("classes", doc, "the share of each class is a dataset (CLASS_VARS), not a second copy")

    def test_shares_are_between_0_and_100_and_the_classes_add_up(self):
        for doc in (self.s, self.b):
            hi, vh, rp = (self.val(doc, k) for k in ("ls_land_high_pct", "ls_land_vhigh_pct", "ls_res_high_pct"))
            cls = [self.val(doc, k) for k, _, _ in ls.CLASS_VARS]   # low ... extremely high, in the order of ls.CLASSES
            for i in range(len(hi)):
                if hi[i] is None:
                    self.assertTrue(all(c[i] is None for c in cls))
                    continue
                for x in (hi[i], vh[i], *(c[i] for c in cls)):
                    self.assertTrue(0 <= x <= 100, x)
                self.assertTrue(rp[i] is None or 0 <= rp[i] <= 100)
                self.assertLessEqual(vh[i], hi[i])
                self.assertAlmostEqual(sum(c[i] for c in cls), 100, delta=0.05)
                self.assertAlmostEqual(hi[i], sum(c[i] for c in cls[2:]), delta=0.03)
                self.assertAlmostEqual(vh[i], sum(c[i] for c in cls[3:]), delta=0.03)

    def test_residents_are_never_more_than_the_barrios_and_add_up_to_the_municipios(self):
        res = self.val(self.b, "ls_res_high")
        for b, r in zip(self.barrios, res):
            if r is not None:
                self.assertLessEqual(r, self.pop[b], b)
        mres = self.val(self.s, "ls_res_high")
        for j, f in enumerate(self.s["geo"]["ids"][:-1]):
            got = [r for b, r in zip(self.barrios, res) if b[:5] == f and r is not None]
            self.assertEqual(mres[j], sum(got) if got else None, f)
        self.assertEqual(mres[-1], sum(r for r in res if r is not None))

    def test_no_value_only_where_the_map_does_not_reach(self):
        hi = self.val(self.b, "ls_land_high_pct")
        empty = {b for b, x in zip(self.barrios, hi) if x is None}
        self.assertTrue(empty, "Vieques and Culebra are not in the model")
        self.assertTrue(all(b[:5] in ("72147", "72049") or b == "7209736650" or self.pop[b] == 0 for b in empty), sorted(empty))   # Vieques, Culebra, Isla de Mona e Islote Monito (Mayaguez)
        self.assertTrue(all(b in empty for b in self.barrios if b[:5] in ("72147", "72049")))
        m = dict(zip(self.s["geo"]["ids"], self.val(self.s, "ls_land_high_pct")))
        self.assertIsNone(m["72147"])
        self.assertIsNone(m["72049"])
        self.assertEqual(sum(1 for f, x in m.items() if x is None), 2)
        for v in self.s["vars"]:
            self.assertEqual(v["barrioFile"], "landslide_barrio.json")
            self.assertTrue(v["noValue"])

    def test_not_mapped_is_said_only_of_the_islands_the_model_leaves_out(self):
        # a barrio of the main island with no 2020 residents has no share of residents, for its own reason (noValueWhy), never "not mapped" (review of PR #61)
        ids, rp = self.b["geo"]["ids"], self.val(self.b, "ls_res_high_pct")
        not_mapped = set(self.s["notes"]["not_mapped"]["barrios"])
        self.assertEqual(len(not_mapped), 15)
        self.assertTrue(all(b[:5] in ("72147", "72049") or b == "7209736650" for b in not_mapped), sorted(not_mapped))
        v = next(x for x in self.b["vars"] if x["key"] == "ls_res_high_pct")
        own = {i for w in v.get("noValueWhy", []) for i in w["ids"]}
        self.assertEqual([w["why"] for w in v["noValueWhy"]], [ls.NO_RESIDENTS])
        self.assertEqual(own, {b for b in ids if b not in not_mapped and self.pop[b] == 0})
        self.assertEqual(own, {"7205915795", "7207526588", "7214179134"})   # Cedro, Emajagual, Santa Rosa (2020 census: no residents)
        self.assertEqual({b for b, x in zip(ids, rp) if x is None}, not_mapped | own)
        for b in own:
            self.assertIsNotNone(self.val(self.b, "ls_land_high_pct")[ids.index(b)], b)   # they are on the map: their land has values
        for x in self.b["vars"]:
            if x["key"] != "ls_res_high_pct":
                self.assertNotIn("noValueWhy", x, x["key"])

    def test_the_tiles_are_the_published_map(self):
        c = self.s["notes"]["checks"]
        for got, want in zip(c["class_pct"], ls.REPORT_AREA_PCT):
            self.assertLessEqual(abs(got - want), ls.TOL_AREA)
        for got, want in zip(c["slope_failures_pct"], ls.REPORT_SLIDES_PCT):
            self.assertLessEqual(abs(got - want), ls.TOL_SLIDES)
        self.assertLessEqual(abs(c["classified_km2"] - ls.REPORT_AREA_KM2), ls.TOL_KM2 * ls.REPORT_AREA_KM2)
        isl = [self.val(self.s, k)[-1] for k, _, _ in ls.CLASS_VARS]
        for got, want in zip(isl, ls.REPORT_AREA_PCT):   # Puerto Rico's datasets are the report's class areas
            self.assertLessEqual(abs(got - want), ls.TOL_AREA)
        self.assertAlmostEqual(self.val(self.s, "ls_land_high_pct")[-1], sum(isl[2:]), delta=0.03)

    def test_no_personal_data_and_no_raster(self):
        for name in ("landslide_series.json", "landslide_barrio.json"):
            self.assertLess((DATA / name).stat().st_size, 200_000, name)
        self.assertFalse([p for p in list(DATA.glob("*.tif")) + list(DATA.glob("*.png")) if p.name.startswith("landslide")])   # heat_surface.png (decision 88) is the one published picture, built by heat.py

    def test_the_cached_tiles_give_the_published_files_again(self):
        if not (ls.CACHE / f"z{ls.Z}" / "_404.json").exists():
            self.skipTest("the map tiles are not cached on this machine (python landslide.py downloads them)")
        self.assertEqual(ls.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
