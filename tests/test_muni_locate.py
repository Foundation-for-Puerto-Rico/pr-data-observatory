"""Tests for muni_locate.py: the municipality of a stop or a place is the outline that holds it, else the nearest outline.

  python -m unittest discover -s tests -v

An invented shore checks the rule: a stop 50 m off a shore counts in the municipality whose outline is nearest, even when another municipality's
town center is nearer. Two tests read the published files in site/data: the scheduled stops on Cataño's waterfront are in Cataño, and both scripts
that place stops (build.py and refresh_network.py) use this rule.
"""
import json
import math
import sys
import unittest
from pathlib import Path

from shapely.geometry import Point, box, shape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import muni_locate  # noqa: E402

DATA = ROOT / "site" / "data"
LAT0 = 18.4
M_LAT = 111_320
M_LNG = 111_320 * math.cos(math.radians(LAT0))


def deg(north_m, east_m):
    """(lat, lng) a given number of meters north and east of (18.4, -66.0)."""
    return LAT0 + north_m / M_LAT, -66.0 + east_m / M_LNG


def square(south_m, west_m, north_m, east_m):
    s, w = deg(south_m, west_m)
    n, e = deg(north_m, east_m)
    return box(w, s, e, n)


class NearestOutline(unittest.TestCase):
    def setUp(self):
        # "Shore" is a long strip (35 km east to west) whose north edge is the shoreline; "Big" lies along the coast to the east, behind a 1 km gap of water.
        # Big's center is nearer than Shore's to a stop just off Shore's east end; the outline rule must still give Shore.
        self.geoms = [square(-3_000, -30_000, 0, 5_000), square(-3_000, 6_000, 2_000, 12_000)]
        self.names = ["Shore", "Big"]
        self.locate = muni_locate.Locator(self.geoms, self.names)

    def test_inside_an_outline(self):
        self.assertEqual(self.locate(*deg(-500, 2_500)), "Shore")
        self.assertEqual(self.locate(*deg(-500, 10_000)), "Big")

    def test_stop_50m_off_a_shore_takes_the_nearest_outline(self):
        lat, lng = deg(50, 4_900)                                     # 50 m off Shore's coast, 1,100 m from Big's outline
        self.assertFalse(any(g.contains(Point(lng, lat)) for g in self.geoms))
        self.assertEqual(self.locate(lat, lng), "Shore")
        i, m = self.locate.nearest(lat, lng)
        self.assertEqual(self.names[i], "Shore")
        self.assertAlmostEqual(m, 50, delta=1)                        # meters, with longitude scaled by cos(latitude)
        # Big's centroid is nearer than Shore's: the old nearest-center rule would have said "Big"
        cs, cb = (g.centroid for g in self.geoms)
        k = math.cos(math.radians(lat))
        self.assertLess(math.hypot((cb.x - lng) * k, cb.y - lat), math.hypot((cs.x - lng) * k, cs.y - lat))

    def test_far_offshore_still_finds_the_nearest_outline(self):
        self.assertEqual(self.locate(*deg(9_000, -10_000)), "Shore")   # 9 km out, beyond the 5 km search box
        self.assertEqual(self.locate(*deg(9_000, 10_000)), "Big")


class PublishedStops(unittest.TestCase):
    def test_catano_waterfront_stops_are_in_catano(self):
        stops = {f["name"]: f["municipality"] for f in json.loads((DATA / "transport.json").read_text(encoding="utf-8")) if f.get("source") == "ati_gtfs"}
        for name in ("Terminal de Cataño", "Terminal de Lancha Cataño"):
            self.assertEqual(stops.get(name), "Cataño", name)

    def test_published_scheduled_stops_follow_the_rule(self):
        geoms, names = [], []
        for ft in json.loads((DATA / "municipios.geojson").read_text(encoding="utf-8"))["features"]:
            if ft["properties"].get("municipality"):
                geoms.append(shape(ft["geometry"])); names.append(ft["properties"]["municipality"])
        locate = muni_locate.Locator(geoms, names)
        stops = [f for f in json.loads((DATA / "transport.json").read_text(encoding="utf-8")) if f.get("source") in ("ati_gtfs", "muni_gtfs")]
        wrong = [(f["name"], f["municipality"], locate(f["lat"], f["lng"])) for f in stops if locate(f["lat"], f["lng"]) != f["municipality"]]
        self.assertEqual(wrong, [])

    def test_both_scripts_use_the_rule(self):
        for f in ("build.py", "refresh_network.py"):
            src = (ROOT / f).read_text(encoding="utf-8")
            self.assertIn("muni_locate.Locator(", src, f)
        self.assertNotIn("nearest_muni", (ROOT / "refresh_network.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
