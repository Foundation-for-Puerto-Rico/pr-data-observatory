"""The Explore tab of the 2D map (navigation plan PR 3, decision 81): the Overview tab grown into ten topics with their pages and a search.

  python -m unittest tests.test_explore

Every published Knowledge Area page is listed under its home domain in catalog.json, once; the page has the Explore tab, its search box and the two places a
topic's page and the search results are drawn; catalog.js opens a topic and answers Ask's question "which topic is this dataset in"; Ask offers "Open its
topic" on the 2D map only.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


class Explore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((SITE / "data" / "catalog.json").read_text(encoding="utf-8"))
        cls.html = (SITE / "index.html").read_text(encoding="utf-8")
        cls.js = (SITE / "js" / "catalog.js").read_text(encoding="utf-8")

    def test_every_published_knowledge_area_is_under_its_domain(self):
        src = (SITE / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        areas = {m.group(2): m.group(3) for m in re.finditer(r"\{ id: '(\w+)',.*?page: '([\w.-]+)', status: 'published'.*?domain: '([\w.-]+)'", src)}
        self.assertGreaterEqual(len(areas), 7)
        top = {d["id"]: d for d in self.cat["domains"] if not d["parent"]}
        for page, dom in areas.items():
            home = dom.split(".")[0] if dom.split(".")[0] in top else dom
            self.assertIn(page, [a["page"] for a in top[home]["knowledge"]], page)
        listed = [a["page"] for d in top.values() for a in d["knowledge"]]
        self.assertEqual(sorted(listed), sorted(areas), "each page once among the top domains")

    def test_the_tab_its_search_and_its_places(self):
        self.assertRegex(self.html, r'data-tab="overview"><span class="ms-icon" aria-hidden="true">explore</span>Explore')
        for i in ('id="exQ"', 'id="exResults"', 'id="exDomain"', 'id="ovCards"'):
            self.assertIn(i, self.html)
        self.assertIn("explore", re.search(r"icon_names=([a-z0-9_,]+)", self.html).group(1).split(","))

    def test_every_icon_explore_draws_is_in_the_font(self):
        # Explore draws each topic's icon and the icons of its Knowledge pages (catalog.js); an icon missing from the font's icon_names shows as its name
        # in letters ("diversity_3" on the Communities card, found on 2026-11-10)
        font = set(re.search(r"icon_names=([a-z0-9_,]+)", self.html).group(1).split(","))
        need = {d["icon"] for d in self.cat["domains"] if d.get("icon")}
        need |= {a["icon"] for d in self.cat["domains"] for a in d.get("knowledge") or [] if a.get("icon")}
        src = (SITE / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        need |= set(re.findall(r"icon: '([a-z0-9_]+)'", src))
        self.assertTrue(need)
        self.assertEqual(sorted(need - font), [], "add these icons to the icon_names of index.html")

    def test_catalog_opens_a_topic_and_names_a_datasets_home(self):
        self.assertIn("function openDomain(", self.js)
        self.assertIn("function renderDomain(", self.js)
        self.assertRegex(self.js, r"return \{ init, shown, apply, canMap, browse, levelsOf, ensure, openDomain, homeOf:")
        self.assertIn("data-open-dom", self.js)

    def test_ask_opens_the_topic_on_the_map_only(self):
        chat = (SITE / "js" / "chat.js").read_text(encoding="utf-8")
        self.assertIn("function chTopic(", chat)
        self.assertRegex(chat, r"if \(chMapless\(\) \|\| typeof Catalog === 'undefined'")
        self.assertEqual(chat.count("const tp = chTopic("), 2)


if __name__ == "__main__":
    unittest.main()
