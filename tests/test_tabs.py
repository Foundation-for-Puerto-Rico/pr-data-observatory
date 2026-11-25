"""The 2D map's main tabs (navigation plan PR 4, decision 81 (a) and (g); since 2026-11-25 three: Home, Place and Tools, with About a page of its own), each main tab holding sub-tabs for the old panes.

  python -m unittest tests.test_tabs

Every old pane keeps its id (tab-<name>) and its name for showTab, so links, Ask and the code that opens a tab by name keep working; each pane sits under one
main tab and is labeled by its sub-tab; the 3D view keeps its own tabs; the About tab's first steps name the new tabs, not the old ones.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
GROUPS = {"explore": ["overview", "layers", "catalog"], "place": ["muni", "region", "rank"], "tools": ["maptools", "transit", "economy"]}   # decision 97: Tools opens on Map tools, Rankings under Place


class Tabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (SITE / "index.html").read_text(encoding="utf-8")
        cls.common = (SITE / "js" / "common.js").read_text(encoding="utf-8")

    def test_four_main_tabs_in_order(self):
        bar = re.search(r'<div class="tabs" role="tablist"[^>]*>(.*?)</div>', self.html, re.S).group(1)
        mains = re.findall(r'id="t-(\w+)"', bar)
        self.assertEqual(mains, ["explore", "place", "tools"])   # About is about.html since 2026-11-25
        for g, subs in GROUPS.items():
            self.assertRegex(bar, rf'data-main="{g}" data-tab="{subs[0]}"', g)

    def test_each_old_pane_has_one_sub_tab_under_its_main_tab(self):
        for g, subs in GROUPS.items():
            row = re.search(rf'<div class="subtabs" role="tablist" aria-label="\w+" data-group="{g}"[^>]*>(.*?)</div>', self.html, re.S)
            self.assertIsNotNone(row, g)
            self.assertEqual(re.findall(r'data-tab="(\w+)"', row.group(1)), subs, g)
            for t in subs:
                self.assertIn(f'id="tab-{t}" role="tabpanel" aria-labelledby="s-{t}"', self.html, t)
        self.assertNotIn('id="tab-about"', self.html)

    def test_show_tab_takes_old_names_and_main_names(self):
        self.assertIn("const m = document.querySelector(`.tabs [data-main=\"${name}\"]`); if (m) name = tabLast[name] || m.dataset.tab;", self.common)
        self.assertIn("showTab(b.dataset.main || b.dataset.tab)", self.common)
        # the names the site's scripts open a tab by: each a pane of the 2D map or of the 3D view
        panes = set(re.findall(r'id="tab-(\w+)" role="tabpanel"', self.html)) | set(re.findall(r'id="tab-(\w+)" role="tabpanel"', (SITE / "3d.html").read_text(encoding="utf-8")))
        called = set()
        for f in (SITE / "js").rglob("*.js"):
            called |= set(re.findall(r"showTab\('(\w+)'", f.read_text(encoding="utf-8")))
        self.assertTrue(called and called <= panes, called - panes)

    def test_the_3d_view_keeps_its_tabs(self):
        h = (SITE / "3d.html").read_text(encoding="utf-8")
        self.assertNotIn('class="subtabs"', h)
        self.assertRegex(h, r'data-tab="layers"')

    def test_help_names_the_new_tabs(self):
        about = (SITE / "about.html").read_text(encoding="utf-8")
        tour = about[about.index('<ol class="tour-steps"'):]
        tour = tour[:tour.index("</ol>")]
        self.assertEqual(tour.count('<li class="tour-step">'), 8)
        for old in ("Overview tab", "Explore tab", "Widgets", "3D + Time"):
            self.assertNotIn(old, tour)
        for new in ("Home tab", "On the map", "Place tab", "Tools tab", "Insights", "2D / 3D switch", "Map Gallery"):
            self.assertIn(new, tour)


class MapTools(unittest.TestCase):
    """Tools › Map tools (decision 97, js/maptools.js): every button opens a tool that exists, where it works."""
    @classmethod
    def setUpClass(cls):
        cls.html = (SITE / "index.html").read_text(encoding="utf-8")
        cls.pane = re.search(r'<section class="tab-page" id="tab-maptools".*?</section>', cls.html, re.S).group(0)
        cls.specs = re.findall(r'data-mt="([^"]+)"', cls.pane)

    def test_each_button_names_a_tool_that_exists(self):
        self.assertGreaterEqual(len(self.specs), 21)
        self.assertEqual(len(self.specs), len(set(self.specs)))
        study = (SITE / "js" / "studyareas.js").read_text(encoding="utf-8")
        economy = (SITE / "js" / "economy.js").read_text(encoding="utf-8") + (SITE / "js" / "workbench.js").read_text(encoding="utf-8")
        for spec in self.specs:
            k, *rest = spec.split(":")
            self.assertIn(k, "lsbhfcmi", spec)
            if k == "l":
                self.assertRegex(self.html, rf'<input type="checkbox" id="{rest[0]}"', spec)
            elif k == "s":
                self.assertIn(f'id="{rest[0]}"', self.html, spec)
            elif k == "b":
                self.assertIn(f"'{rest[0]}'", economy, spec)
                if len(rest) > 1:
                    self.assertIn(f'id="{rest[1]}"', study, spec)
            elif k == "m":
                self.assertIn(rest[0], ("line", "area"), spec)
            elif k == "h":
                self.assertIn(f'<option value="{rest[0]}">', self.html, spec)

    def test_the_pane_loads_on_use_and_waits_for_its_spanish(self):
        app = (SITE / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("if (name === 'maptools') mtP = mtP || addJs('js/maptools.js?v=", app)
        self.assertIn('id="tab-maptools" role="tabpanel" aria-labelledby="s-maptools" data-t-wait', self.html)
        import json
        pages = json.loads((ROOT / "i18n_src" / "pages.json").read_text(encoding="utf-8"))
        self.assertEqual(pages["pages"]["map"]["modules"]["maptools"], {"scopes": [], "scripts": ["maptools.js"], "html": ["tab-maptools"]})

    def test_rankings_sit_under_place_and_its_button_has_spanish(self):
        import json
        es = json.loads((ROOT / "i18n_src" / "es" / "map.json").read_text(encoding="utf-8"))
        self.assertEqual(es.get("Show on the map"), "Mostrar en el mapa")
        self.assertNotIn("data-ecbench=\"study\"", self.html[self.html.index('id="tab-economy"'):self.html.index('id="econRoot"')])


if __name__ == "__main__":
    unittest.main()
