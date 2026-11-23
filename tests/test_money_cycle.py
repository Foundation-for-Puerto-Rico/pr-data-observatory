"""The How public money moves page (money-cycle.html, docs/analysis/money-cycle-2026-11/make_page.py, HANDOFF decision 112, step 1): the stages in
their order, a public source for what the page says, links to the three public money pages and back, complete Spanish, and the review marker."""
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "site" / "money-cycle.html"
spec = importlib.util.spec_from_file_location("money_cycle_page", ROOT / "docs" / "analysis" / "money-cycle-2026-11" / "make_page.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class Content(unittest.TestCase):
    def test_the_stages_are_the_eight_in_their_order(self):
        self.assertEqual([s[1][0] for s in G.STAGES], ["Design", "Request", "Approval", "Assignment", "Obligation", "Execution", "Spending", "In service"])
        self.assertEqual([s[1][1] for s in G.STAGES], ["Diseño", "Solicitud", "Aprobación", "Asignación", "Obligación", "Ejecución", "Gasto", "En servicio"])
        for _icon, name, what, who in G.STAGES:
            self.assertTrue(all(name) and all(what) and all(who))

    def test_the_federal_side_ends_with_closeout(self):
        self.assertEqual([f[0][0] for f in G.FEDERAL][0], "Appropriation")
        self.assertEqual([f[0][0] for f in G.FEDERAL][-1], "Closeout")
        self.assertIn("Outlay", [f[0][0] for f in G.FEDERAL])

    def test_every_source_has_a_name_what_it_supports_and_a_secure_address(self):
        self.assertGreaterEqual(len(G.SOURCES), 6)
        for name, what, url in G.SOURCES:
            self.assertTrue(all(name) and all(what))
            self.assertRegex(url, r"^https://[a-z0-9.-]+\.(gov|org)/")
        text = " ".join(n[0] for n, _w, _u in G.SOURCES)
        for law in ("PROMESA", "Act 147 of 1980", "Act 230 of 1974", "Act 73 of 2019", "2 CFR 200"):
            self.assertIn(law, text)

    def test_the_three_public_money_pages_are_named_with_their_stage(self):
        self.assertEqual([p[1] for p in G.PAGES], ["public-spending.html", "unused-funds.html", "public-money.html"])
        for _name, href, _what, _stage in G.PAGES:
            self.assertTrue((ROOT / "site" / href).exists(), href)


@unittest.skipUnless(PAGE.exists(), "the page is not built")
class Teaching(unittest.TestCase):
    """The parts that teach (decision 112, step 1b): an example, the pairs often confused, the questions, the links into the figures, the self-check."""

    def test_every_link_into_the_figures_points_to_a_section_that_exists(self):
        links = [h for _w, _wh, h in G.EXAMPLE if h] + [h for _w, _s, _n, h in G.SEE]
        self.assertGreaterEqual(len(links), 10)
        for href in links:
            page, anchor = href.split("#")
            self.assertIn(page, [p[1] for p in G.PAGES], href)
            self.assertRegex((ROOT / "site" / page).read_text(encoding="utf-8"), r'<section[^>]*\bid="%s"' % anchor, href)

    def test_the_example_is_made_up_and_carries_no_amount(self):
        self.assertIn("This grant does not exist.", PAGE.read_text(encoding="utf-8"))
        for what, where, href in G.EXAMPLE:
            if not href:
                self.assertNotRegex(what[0] + where[0] + what[1] + where[1], r"[$\d]")
            self.assertNotIn("$", what[0] + what[1])
        self.assertEqual(sum(1 for _w, _wh, h in G.EXAMPLE if not h), 5)   # half of the steps show nowhere: the point of the example

    def test_the_wording_rule_of_the_grants_page_holds_here(self):
        """Decision 111: never say money was returned, unused or at risk as a finding. The page may name a confusion only to deny it."""
        text = " ".join(a[0] + " " + b[0] for a, b in G.CONFUSED + G.QUESTIONS + G.CHECK)
        self.assertNotRegex(text, r"(?i)\b(at risk|was returned|were returned|wasted|fraud)\b")
        self.assertIn("A balance is not money lost", [a[0] for a, _b in G.CONFUSED])

    def test_the_self_check_needs_no_script(self):
        html_ = PAGE.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'<details class="card mc-check"><summary>', html_)), len(G.CHECK))
        self.assertEqual(len(G.QUESTIONS), 5)
        self.assertEqual(len(re.findall(r'<div class="card mc-kind mc-not">', html_)), len(G.CONFUSED))


@unittest.skipUnless(PAGE.exists(), "the page is not built")
class Page(unittest.TestCase):
    def setUp(self):
        self.html = PAGE.read_text(encoding="utf-8")
        self.text = re.sub(r"<[^>]+>", " ", self.html)

    def test_the_page_is_in_review_and_not_indexed(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.html)
        self.assertIn("data-ka-note", self.html)
        self.assertIn('data-ka="moneycycle"', self.html)
        item = next(i for i in json.loads((ROOT / "knowledge_src" / "items.json").read_text(encoding="utf-8"))["items"] if i["id"] == "moneycycle")
        self.assertEqual((item["status"], item.get("review"), item.get("ai"), item["datasets"]), ("published", True, True, []))
        self.assertEqual(item["related"], ["publicspending", "unusedfunds", "publicmoney"])

    def test_the_path_and_the_sources_are_on_the_page(self):
        self.assertEqual(len(re.findall(r'<li class="mc-step', self.html)), len(G.STAGES))
        self.assertEqual(len(re.findall(r'<li class="mc-fstep">', self.html)), len(G.FEDERAL))
        self.assertEqual(re.findall(r'<p class="pm-small mc-src" data-t="skip"><a href="([^"]+)"', self.html), [u for _n, _w, u in G.SOURCES])
        self.assertEqual(len(re.findall(r'<li class="mc-step mc-gap">', self.html)), 1)   # the last stage is marked as the one with no data

    def test_the_page_has_no_figures_and_no_script_of_its_own(self):
        self.assertNotRegex(self.text, r"\$\s?\d")                       # no dollar figure: the page explains, the other pages count
        self.assertNotIn("data/", re.sub(r'href="https?://[^"]+"', "", self.html))
        scripts = re.findall(r'<script src="js/([a-z0-9_/]+)\.js', self.html)
        self.assertEqual(scripts, ["i18n", "core/knowledge", "common", "chatboot"])

    def test_the_page_says_what_the_data_do_not_show_and_gives_no_opinion(self):
        self.assertIn("The last stage has no data.", self.html)
        self.assertIn("gives no opinion on how the process should work", self.html)
        self.assertNotRegex(self.text, r"(?i)\b(should be reformed|must change|wasteful|corrupt|mismanag)")

    def test_the_other_pages_link_to_the_cycle(self):
        for f in ("public-spending.html", "unused-funds.html"):
            self.assertIn('href="money-cycle.html"', (ROOT / "site" / f).read_text(encoding="utf-8"), f)
        items = {i["id"]: i for i in json.loads((ROOT / "knowledge_src" / "items.json").read_text(encoding="utf-8"))["items"]}
        for other in ("publicspending", "unusedfunds", "publicmoney"):
            self.assertIn("moneycycle", items[other]["related"], other)

    def test_spanish(self):
        es = json.loads((ROOT / "i18n_src" / "es" / "money_cycle.json").read_text(encoding="utf-8"))
        self.assertEqual(es["How public money moves"], "Cómo se mueve el dinero público")
        same = [k for k, v in es.items() if k != "_about" and v == k]
        self.assertEqual(same, [], "every string has Spanish")


if __name__ == "__main__":
    unittest.main()
