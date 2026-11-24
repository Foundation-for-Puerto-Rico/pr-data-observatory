"""The glossary (dictionary_src/glossary.json; dictionary_src/README.md, "Glossary"; docs/glossary.md): every term in both languages and with a source,
match forms the highlighter can use, and Spanish held for review left out of what the site publishes. Part 2: the highlighter's files are current and hold no
held Spanish, every page loads the highlighter after it is ready (never with its first load), and a priority-1 term shown in the interface is underlined.

  python -m unittest tests.test_glossary
"""
import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dictionary  # noqa: E402

SRC = ROOT / "dictionary_src" / "glossary.json"
DATA = ROOT / "site" / "data"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class Glossary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = load(SRC)
        full = load(DATA / "dictionary.json") if (DATA / "dictionary.json").exists() else {"entries": [], "id_alias": {}}
        cls.known = {e["id"] for e in full["entries"]} | set(full.get("id_alias", {}))

    def errors(self, terms):
        return [p for p in dictionary.check_glossary(terms, self.known) if p[0] == "error"]

    def test_the_glossary_passes_its_checks(self):
        self.assertEqual(self.errors(self.g), [])

    def test_a_term_without_a_source_or_a_language_fails(self):
        base = next(t for t in self.g if t["id"] == "data-file")
        for change, why in ((lambda t: t.pop("source"), "no source"), (lambda t: t["source"].update(url=""), "no source url"),
                            (lambda t: t["source"].update(url="http://example.org/"), "not https"), (lambda t: t["source"].pop("checked"), "no date checked"),
                            (lambda t: t.pop("plain_es"), "no Spanish"), (lambda t: t.update(plain_es="  "), "blank Spanish"), (lambda t: t.update(plain=""), "no English"),
                            (lambda t: t["match"].pop("es"), "no Spanish match forms"), (lambda t: t.pop("highlight"), "no highlight flag"),
                            (lambda t: t.update(id="Data file"), "id is not the anchor"), (lambda t: t["source"].update(url="https://observatory.foundationpr.org/dictionary.html#no.such_entry"), "dead anchor")):
            t = copy.deepcopy(base)
            change(t)
            self.assertTrue(self.errors([t]), f"a term with {why} must fail the check")

    def test_a_highlighted_form_names_one_term(self):
        a = copy.deepcopy(next(t for t in self.g if t["id"] == "data-file"))
        b = copy.deepcopy(a)
        b.update(term="Data files (copy)", id=dictionary.glossary_slug("Data files (copy)"))
        self.assertTrue(any("also a form of" in p[3] for p in self.errors([a, b])))

    def test_ids_are_the_anchors_of_the_page(self):
        for t in self.g:
            self.assertRegex(t["id"], r"^[a-z0-9]+(-[a-z0-9]+)*$", t["term"])
        self.assertEqual(dictionary.glossary_slug("Calificación"), "calificacion")
        self.assertEqual(dictionary.glossary_slug("1% annual chance flood"), "1-annual-chance-flood")

    def test_the_terms_francis_asked_about_are_defined(self):
        ids = {t["id"]: t for t in self.g}
        for i in ("data-file", "domain-in-the-dictionary", "dataset", "snapshot", "geojson", "csv", "moe", "census-tract", "block-group", "sfha", "gtfs"):
            self.assertIn(i, ids)
            self.assertTrue(ids[i]["highlight"], i)
        self.assertIn("archivo de datos", ids["data-file"]["match"]["es"])
        self.assertIn("dominio", ids["domain-in-the-dictionary"]["match"]["es"])

    def test_acronyms_that_are_also_words_match_only_in_capitals(self):
        ids = {t["id"]: t for t in self.g}
        for i in ("put", "ama", "str", "pep", "ati", "crim", "ems", "sfha", "moe"):
            caps = [f for f in ids[i]["match"]["en"] if f.isupper()]
            self.assertTrue(caps and all(dictionary.glossary_form_cs(ids[i], f) for f in caps), i)
        self.assertFalse(dictionary.glossary_form_cs(ids["str"], "short-term rental"))
        self.assertTrue(dictionary.glossary_form_cs(ids["str"], "STR"))

    def test_spanish_held_for_review_is_not_published(self):
        held = [t for t in self.g if t.get("hold_es")]
        self.assertTrue(held)
        for f in ("dictionary.json", "dictionary_list.json"):
            pub = {t["id"]: t for t in load(DATA / f)["glossary"]}
            self.assertEqual(len(pub), len(self.g), f)
            for t in held:
                self.assertNotIn("plain_es", pub[t["id"]], f"{f}: the Spanish of {t['term']} is held for review")
                self.assertNotIn("expansion_es", pub[t["id"]], f"{f}: {t['term']}")
                self.assertNotIn("name_es", pub[t["id"]]["source"], f"{f}: {t['term']}")
            self.assertTrue(all(pub[t["id"]].get("plain_es") for t in self.g if not t.get("hold_es")), f)

    def test_federal_grant_terms_are_held(self):
        # a safety net like tests/test_held_for_review.py: Spanish that names CDBG-DR or LIHTC waits for Finance and Compliance
        # Released on purpose: the project lead approved the WCRP wording, its CDBG-DR and HUD funding line included, on 2026-10-19 (HANDOFF decision 51)
        released_decision_51 = {"cdbg-dr", "hud", "wcrp"}
        pat = re.compile(r"CDBG|LIHTC")
        for t in self.g:
            if t["id"] in released_decision_51:
                self.assertNotIn("hold_es", t, f"{t['term']} was released under decision 51")
                self.assertNotRegex(t["plain_es"], r"LIHTC|Tabla 10|estudio de vivienda", f"{t['term']}: the released text is the WCRP framing only")
                continue
            if pat.search(t["plain_es"]) or pat.search(t["term"]):
                self.assertEqual(t.get("hold_es"), "compliance", t["term"])
        self.assertEqual({t["id"] for t in self.g if t.get("hold_es")}, {"lihtc", "openfema", "usaspending", "ihp", "individual-assistance-fema", "public-assistance-fema", "obligation",
                         "de-obligation", "federal-award-types", "place-of-performance", "disaster-declaration", "loan-subsidy-cost", "recorded-as-statewide",
                         "damage-category-fema", "section-406-mitigation", "hazard-mitigation-assistance-fema", "hmgp", "subapplication-fema-grants", "federal-share",   # Public money v2, step 1 (2026-10-30)
                         "assistance-listing", "pell-grant", "head-start", "project-based-rental-assistance", "social-security-disability-benefits", "veterans-disability-compensation",   # step 2 (2026-10-31)
                         "single-audit", "federal-audit-clearinghouse", "pass-through-entity", "federal-awards-expended",   # step 3 (2026-10-31)
                         "new-markets-tax-credit", "qualified-low-income-community-investment", "community-development-entity", "placed-in-service",   # step 4 (2026-10-31)
                         "subaward", "subrecipient",   # Public spending stage lines (decision 96, step 1, 2026-11-11)
                         "outlay", "period-of-performance", "audit-finding", "repeated-finding", "questioned-costs",   # Public spending, obligated and paid out (decision 96, step 2, 2026-11-13)
                         "project-closeout",   # Public spending, FEMA by stage and age (decision 109, step 2, 2026-11-17)
                         "cdbg", "cdbg-mit", "entitlement-grant-cdbg", "cdbg-state-program"})   # Disaster funding and need, HUD CDBG (decision 100, 2026-11-12)

    def test_observatory_sources_have_spanish_names_and_real_dates(self):
        from datetime import date
        for t in self.g:
            s = t["source"]
            self.assertEqual(date.fromisoformat(s["checked"]).isoformat(), s["checked"], t["term"])
            if s["url"].startswith(dictionary.OBS_URL):
                self.assertTrue(s.get("name_es"), t["term"])
        bad = copy.deepcopy(next(t for t in self.g if t["id"] == "data-file"))
        bad["source"]["checked"] = "2026-02-30"
        self.assertTrue(self.errors([bad]), "an impossible date must fail")
        bad["source"]["checked"] = "2026-10-19"
        bad["source"].pop("name_es")
        self.assertTrue(self.errors([bad]), "an observatory source without its Spanish name must fail")

    def test_the_published_glossary_is_sorted_and_current(self):
        pub = load(DATA / "dictionary_list.json")["glossary"]
        self.assertEqual(pub, dictionary.published_glossary(self.g), "run python dictionary.py and commit what it writes")



SITE = ROOT / "site"
ROUTES = ROOT / "dictionary_src" / "routes.json"
PAGES = ("index.html", "3d.html", "profile.html", "housing.html", "wcrp.html", "dictionary.html", "data-management.html")


class Highlighter(unittest.TestCase):
    """Part 2 (site/js/core/glossary.js): its data files, how the pages load it, and the standing rule."""
    @classmethod
    def setUpClass(cls):
        cls.g = load(SRC)
        cls.pub = dictionary.published_glossary(cls.g)

    def test_the_four_files_are_current(self):
        files = dictionary.glossary_page_files(self.pub)
        self.assertEqual(sorted(files), sorted(dictionary.GLOSSARY_FILES))
        for name, want in files.items():
            self.assertEqual(load(DATA / name), want, f"{name} is stale: run python dictionary.py and commit what it writes")

    def test_forms_hold_the_highlighted_terms_and_defs_every_term(self):
        for lang in dictionary.GLOSSARY_LANGS:
            forms = load(DATA / f"glossary_forms_{lang}.json")["terms"]
            self.assertEqual([t[0] for t in forms], [g["id"] for g in self.pub if g["highlight"]], lang)
            for tid, fs, cs in forms:
                g = next(x for x in self.g if x["id"] == tid)
                nm = (g.get("not_match") or {}).get(lang, [])
                self.assertEqual(fs, g["match"][lang] + ["!" + f for f in nm], "the forms, then the not_match phrases with '!' in front")
                self.assertEqual(cs, [1 if dictionary.glossary_form_cs(g, f) else 0 for f in g["match"][lang] + nm], tid)
            defs = load(DATA / f"glossary_defs_{lang}.json")["terms"]
            self.assertEqual(set(defs), {g["id"] for g in self.g}, "a page can mark a term that is not highlighted on purpose (data-gloss), so every term has its text")

    def test_no_held_spanish_reaches_the_highlighter(self):
        blob = "".join((DATA / f).read_text(encoding="utf-8") for f in dictionary.GLOSSARY_FILES)
        defs = load(DATA / "glossary_defs_es.json")["terms"]
        for g in self.g:
            if not g.get("hold_es"):
                continue
            for k in ("plain_es", "expansion_es"):
                if g.get(k):
                    self.assertNotIn(g[k], blob, f"{g['term']}: {k} is held for review")
            if g["source"].get("name_es"):
                self.assertNotIn(g["source"]["name_es"], blob, g["term"])
            self.assertEqual(defs[g["id"]][2], g["plain"], f"{g['term']}: Spanish pages show the English definition")
            self.assertTrue(defs[g["id"]][6] & 1, f"{g['term']}: and mark it lang=en")

    def test_the_pages_fetch_the_forms_after_they_are_ready_and_the_definitions_on_first_use(self):
        routes = load(ROUTES)["routes"]
        for name, r in routes.items():
            if name == "dictionary":   # it reads both from its own copy of the glossary (dictionary_list.json)
                self.assertFalse([f for f in r.get("first", []) + r.get("later", []) + r.get("on_use", []) if f.startswith("glossary_")])
                continue
            self.assertIn("glossary_forms_es.json", r["later"], name)
            self.assertIn("glossary_defs_es.json", r["on_use"], name)
            self.assertFalse([f for f in r["first"] if f.startswith("glossary_")], name)

    def test_the_highlighter_is_never_part_of_a_first_load(self):
        common = (SITE / "js" / "common.js").read_text(encoding="utf-8")
        self.assertRegex(common, r"s\.src = 'js/core/glossary\.js\?v=\d+'", "common.js loads it when the page is ready")
        at = common.index("s.src = 'js/core/glossary.js")
        loader = common[common.index("window.addEventListener('load', function glossary()"):at]
        self.assertIn("requestIdleCallback", loader)
        self.assertIn("if (netBusy", loader, "it waits until the page has fetched its data")
        # netBusy does not count what a page's libraries fetch (the 3D view's style, tiles and terrain): a page that marks the moment it is ready waits for the mark too
        self.assertIn("performance.getEntriesByName('ready')", loader)
        ready = set(re.findall(r"'(\w+)'", re.search(r"const READY_PAGES = \[([^\]]*)\]", common).group(1)))
        marks = set()
        for name, spec in load(ROOT / "i18n_src" / "pages.json")["pages"].items():
            scripts = spec.get("scripts", []) + [s for m in spec.get("modules", {}).values() for s in m["scripts"]]
            if any("performance.mark('ready')" in (SITE / "js" / s).read_text(encoding="utf-8") for s in scripts if s != "common.js"):
                marks.add(name)
                self.assertIn(f'data-page="{name}"', (SITE / spec["file"]).read_text(encoding="utf-8"), "the loader reads the page's name from i18n.js's data-page")
        self.assertEqual(ready, marks, "READY_PAGES lists exactly the pages whose scripts mark 'ready': another page would wait two minutes for a mark that never comes")
        for page in PAGES:
            html = (SITE / page).read_text(encoding="utf-8")
            self.assertNotIn("glossary.js", html, f"{page} lists no glossary script: it is off the budgeted first load")
            self.assertIn("js/common.js", html, page)
        pages = load(ROOT / "i18n_src" / "pages.json")["pages"]
        for name, spec in pages.items():
            self.assertEqual(spec.get("modules", {}).get("glossary"), {"scopes": ["glossary"], "scripts": ["core/glossary.js"]}, f"{name}: the module's Spanish loads with it (es.{name}.glossary.js), not with the page")
            self.assertTrue((SITE / "i18n" / f"es.{name}.glossary.js").exists(), name)

    def test_the_words_francis_asked_about_are_marked_on_purpose_on_the_dictionary_page(self):
        html = (SITE / "dictionary.html").read_text(encoding="utf-8")
        self.assertIn('<h2 id="fTitle" data-gloss="data-file">Published data files</h2>', html)
        self.assertIn('<h2 class="side-h" data-gloss="domain-in-the-dictionary">', (SITE / "js" / "dictionary.js").read_text(encoding="utf-8"))
        ids = {g["id"] for g in self.g}
        for page in PAGES:
            for i in re.findall(r'data-gloss="([^"]+)"', (SITE / page).read_text(encoding="utf-8")):
                self.assertTrue(i == "off" or i in ids, f"{page}: data-gloss={i} is not a glossary id")

    def test_a_priority_1_term_shown_in_the_interface_is_underlined_unless_its_record_says_why(self):
        self.assertEqual(dictionary.check_glossary_ui(self.g), [], "every priority-1 term that appears in the interface is highlighted, or says why not (highlight_why)")
        texts = {"en": "Each estimate comes with its margin of error.", "es": "Cada estimado tiene su margen de error."}
        base = copy.deepcopy(next(t for t in self.g if t["id"] == "estimate"))
        base["highlight"] = False
        self.assertTrue(dictionary.check_glossary_ui([base], texts), "a priority-1 term shown in the interface, not underlined and with no reason, must fail")
        base["highlight_why"] = "Too common in the tables of one page; its column headings link to the Glossary instead."
        self.assertEqual(dictionary.check_glossary_ui([base], texts), [])
        base["priority"] = 2
        del base["highlight_why"]
        self.assertEqual(dictionary.check_glossary_ui([base], texts), [], "the rule is for priority 1")
        hidden = copy.deepcopy(next(t for t in self.g if t["id"] == "estimate"))
        hidden["highlight"] = False
        self.assertEqual(dictionary.check_glossary_ui([hidden], {"en": "nothing here", "es": "nada"}), [], "a term that the interface does not show needs no reason")
        self.assertTrue(dictionary.check_glossary_ui([hidden], {"en": "nothing", "es": "los estimados"}), "Spanish counts too")
        self.assertTrue(dictionary.check_glossary_ui([hidden], {"en": "underestimated", "es": "subestimado"}) == [], "whole words only")
        self.assertTrue(dictionary.check_glossary_ui([hidden]), "and the real interface shows 'estimate'")

    def test_not_match_phrases_hold_a_form_and_reach_the_forms_file(self):
        pc = next(x for x in self.g if x["id"] == "per-capita")
        self.assertEqual(pc["not_match"], {"es": ["por residente empleado"]}, "jobs per employed resident is not a per-capita figure")
        forms = {t[0]: t for t in load(DATA / "glossary_forms_es.json")["terms"]}
        self.assertIn("!por residente empleado", forms["per-capita"][1])
        self.assertIn("GTFS-Realtime", next(x for x in self.g if x["id"] == "gtfs-rt")["match"]["es"])
        bad = lambda t: [p for p in dictionary.check_glossary([t], set()) if p[0] == "error" and ("not_match" in p[3] or "'!'" in p[3])]
        t = copy.deepcopy(pc)
        self.assertEqual(bad(t), [])
        t["not_match"] = {"es": ["empleo total"]}
        self.assertTrue(bad(t), "a phrase that holds none of the term's forms would never stop a mark")
        t["not_match"] = {"fr": ["par résident"]}
        self.assertTrue(bad(t), "only en and es")
        t = copy.deepcopy(pc)
        t["match"]["es"].append("!por")
        self.assertTrue(bad(t), "a form may not start with '!', which marks a phrase in the files")

    def test_highlight_why_is_only_a_reason_for_a_term_that_is_not_underlined(self):
        t = copy.deepcopy(next(x for x in self.g if x["id"] == "data-file"))
        t["highlight_why"] = "a reason"
        why = lambda: [p for p in dictionary.check_glossary([t], set()) if p[0] == "error" and "highlight_why" in p[3]]
        self.assertTrue(why(), "highlight_why with highlight true")
        t["highlight"] = False
        self.assertFalse(why())
        t["highlight_why"] = "  "
        self.assertTrue(why(), "a blank reason")


if __name__ == "__main__":
    unittest.main()
