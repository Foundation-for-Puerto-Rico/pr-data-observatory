"""Tests for fpr_baseline.py and its published files: what each feature may carry (no survey comments, no contact fields), the Eastern Region only, the
counts the CSVs give, and only the traced routes the observatory lacks. No network."""
import csv
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fpr_baseline as fb  # noqa: E402

DATA = ROOT / "site" / "data"
PROPS = {"illegal_dumping.geojson": {"name", "type", "municipio", "geoid", "size", "waste", "burning"},
         "fpr_routes.geojson": {"name", "type", "municipio", "geoid", "operator", "km", "covered_pct"}}


def rows(path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class Csv(unittest.TestCase):
    def test_the_csvs_have_their_columns_and_known_values(self):
        for path, cols in ((fb.DUMP_CSV, fb.DUMP_COLS),):
            self.assertEqual(list(rows(path)[0]), cols, path.name)
        for d in rows(fb.DUMP_CSV):
            self.assertIn(d["tamano"], fb.SIZES)
            self.assertTrue(all(k.strip() in fb.WASTE for k in d["residuos"].split(",")), d["punto"])

    def test_the_traced_routes_keep_their_properties(self):
        for f in json.loads(fb.ROUTES_SRC.read_text(encoding="utf-8"))["features"]:
            self.assertEqual(set(f["properties"]), set(fb.ROUTE_PROPS))


class Published(unittest.TestCase):
    def setUp(self):
        self.docs = {f: json.loads((DATA / f).read_text(encoding="utf-8")) for f in PROPS if (DATA / f).exists()}
        if len(self.docs) < len(PROPS):
            self.skipTest("not built")

    def test_features_hold_only_the_allowed_properties_in_the_eastern_region(self):
        for f, d in self.docs.items():
            self.assertEqual((d["source"], d["vintage"]), ("fpr_baseline", fb.VINTAGE), f)
            for x in d["features"]:
                self.assertLessEqual(set(x["properties"]), PROPS[f], f)
                self.assertTrue(x["properties"]["geoid"].startswith("72") and len(x["properties"]["geoid"]) == 5, f)
                g = x["geometry"]
                pts = [g["coordinates"]] if g["type"] == "Point" else [c for line in g["coordinates"] for c in line]
                self.assertTrue(all(-66.1 < lon < -65.2 and 17.9 < lat < 18.5 for lon, lat in pts), f"{f}: a point outside the Eastern Region")

    def test_the_counts_are_those_of_the_csvs(self):
        self.assertEqual(len(self.docs["illegal_dumping.geojson"]["features"]), len(rows(fb.DUMP_CSV)))
        for gone in ("asset_transit.geojson", "microtransit.geojson"):   # layers taken off at the owner's request (2026-10-27)
            self.assertFalse((DATA / gone).exists(), gone)

    def test_only_the_routes_the_observatory_lacks_are_published(self):
        d, src = self.docs["fpr_routes.geojson"], json.loads(fb.ROUTES_SRC.read_text(encoding="utf-8"))["features"]
        self.assertEqual(d["notes"]["traced"], len(src))
        self.assertEqual(len(d["features"]) + d["notes"]["covered_left_out"], len(src))
        self.assertTrue(all(x["properties"]["covered_pct"] < 100 * fb.COVERED for x in d["features"]))
        self.assertTrue(all(x["geometry"]["type"] in ("LineString", "MultiLineString") for x in d["features"]))


if __name__ == "__main__":
    unittest.main()
