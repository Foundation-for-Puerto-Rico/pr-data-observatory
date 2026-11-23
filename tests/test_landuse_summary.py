"""Tests for landuse.py class_summary and the published landuse_summary.json (the land-use analysis of the 2D map).

  python -m unittest discover -s tests -v
"""
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import landuse  # noqa: E402

DATA = ROOT / "site" / "data"


class Summary(unittest.TestCase):
    def test_classes_areas_and_the_codes_without_their_own_colour(self):
        props = [{"CLASIPUT": "SU", "Municipio": "Uno", "Shape_Area": 2_000_000}, {"CLASIPUT": "SREP-AE", "Municipio": "Uno", "Shape_Area": 500_000},
                 {"CLASIPUT": "agua", "Municipio": "Uno", "Shape_Area": 1_000_000}, {"CLASIPUT": "SRC", "Municipio": "Dos", "Shape_Area": 3_000_000},
                 {"CLASIPUT": "SU", "Municipio": "", "Shape_Area": 9_000_000}]
        d = landuse.class_summary(props, lambda n: n or None, "v")
        self.assertEqual(d["names"], ["Dos", "Uno"])
        self.assertEqual((d["municipios"]["Uno"]["SU"], d["municipios"]["Uno"]["SREP"], d["municipios"]["Uno"]["AGUA"]), (2.0, 0.5, 1.0), "SREP-AE draws, and counts, as SREP; codes are case-blind")
        self.assertEqual(d["puerto_rico"]["SU"], 2.0, "Puerto Rico is the sum of the municipios")
        self.assertEqual(d["unassigned"]["SU"], 9.0, "a polygon with no municipio is kept apart")
        share = {c["key"]: c["in_share"] for c in d["classes"]}
        self.assertEqual((share["AGUA"], share["VIAL"], share["SU"]), (False, False, True))
        self.assertEqual(landuse.class_key("SREP-XX"), "SREP")
        self.assertEqual(landuse.class_key("ZZ"), "OTRO")

    def test_the_browser_uses_the_same_classes(self):
        js = (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
        keys = [k for k in landuse.GROUPS if landuse.GROUPS[k][1] not in landuse.SHARE_EXCLUDED]
        self.assertIn("const LU_KEYS = [" + ", ".join(f"'{k}'" for k in keys) + "]", js)
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        for k in keys:
            self.assertIn(f'data-lu="{k}" checked', html, f"{k}: a tick box, ticked when the page opens")
        self.assertIn('id="luAnalyze"', html)


@unittest.skipUnless((DATA / "landuse_summary.json").exists(), "published file not present")
class Published(unittest.TestCase):
    def test_the_classes_add_up_to_the_published_groups(self):
        d = json.loads((DATA / "landuse_summary.json").read_text(encoding="utf-8"))
        stats = json.loads((DATA / "municipalities.json").read_text(encoding="utf-8"))
        grp = {c["key"]: c["group"] for c in d["classes"]}
        self.assertEqual(sorted(d["names"]), sorted(stats))
        for m, s in stats.items():
            g = defaultdict(float)
            for k, a in d["municipios"][m].items():
                if grp[k] not in landuse.SHARE_EXCLUDED:
                    g[grp[k]] += a
            for k, v in s["landuse_km2"].items():
                self.assertAlmostEqual(g[k], v, delta=0.06, msg=f"{m} {k}")
        for k in grp:
            self.assertAlmostEqual(d["puerto_rico"][k], sum(v[k] for v in d["municipios"].values()), delta=0.01, msg=k)


if __name__ == "__main__":
    unittest.main()
