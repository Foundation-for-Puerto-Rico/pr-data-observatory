"""Runs the JavaScript tests of the shared engine (site/js/core), of the layer menus (site/js/core/layers.js), of the in-page glossary (site/js/core/glossary.js) and of the Knowledge Area registry with Node, when Node is installed: python -m unittest discover -s tests"""
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("node"), "Node is not installed")
class CoreEngineTests(unittest.TestCase):
    def test_engine_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "core.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_layer_menu_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "layers_menu.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_glossary_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "glossary.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_knowledge_area_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "knowledge.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_profile_region_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "profile_region.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_women_labor_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "women_labor.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_osm_inspector_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "osminspect.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)

    def test_basemap_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(HERE / "basemap.test.js")], capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-3000:])
        self.assertIn("fail 0", r.stdout)


if __name__ == "__main__":
    unittest.main()
