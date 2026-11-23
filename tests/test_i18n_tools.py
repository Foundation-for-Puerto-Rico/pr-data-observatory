"""Tests for i18n.py (the Spanish bundle builder and checker) and, when Node is installed, for site/js/i18n.js."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import i18n  # noqa: E402


def msgs(ps, sev="error"):
    return " | ".join(p[3] for p in ps if p[0] == sev)


class ValidateTests(unittest.TestCase):
    def v(self, scopes, keep=()):
        return i18n.validate(scopes, set(keep))

    def test_clean_scope_passes(self):
        self.assertEqual(msgs(self.v({"a": {"Map": "Mapa", "{n} of {m} places": "{n} de {m} lugares", "{n} place": ["{n} lugar", "{n} lugares"]}})), "")

    def test_spanish_must_keep_every_placeholder(self):
        self.assertIn("drops placeholder", msgs(self.v({"a": {"{n} of {m} places": "{n} lugares"}})))

    def test_spanish_cannot_invent_a_placeholder(self):
        self.assertIn("uses a placeholder the key lacks", msgs(self.v({"a": {"Places": "{n} lugares"}})))

    def test_plural_array_needs_two_non_empty_strings(self):
        self.assertIn("value must be", msgs(self.v({"a": {"{n} place": ["{n} lugar"]}})))
        self.assertIn("value must be", msgs(self.v({"a": {"Map": ""}})))

    def test_html_tags_must_match_the_key(self):
        self.assertEqual(msgs(self.v({"a": {"<b>Hi</b> there": "<b>Hola</b> aquí"}})), "")
        self.assertIn("HTML tags", msgs(self.v({"a": {"<b>Hi</b> there": "Hola aquí"}})))
        self.assertIn("HTML tags", msgs(self.v({"a": {'See <a href="x">this</a>': 'Vea <a href="y">esto</a>'}})))

    def test_two_scopes_must_agree(self):
        self.assertIn("different Spanish", msgs(self.v({"a": {"Map": "Mapa"}, "b": {"Map": "Plano"}})))
        self.assertEqual(msgs(self.v({"a": {"Map": "Mapa"}, "b": {"Map": "Mapa"}})), "")

    def test_questions_open_with_inverted_mark_and_untranslated_text_is_flagged(self):
        self.assertIn("¿", msgs(self.v({"a": {"What is this?": "Qué es esto?"}}), "warn"))
        self.assertIn("equals the English key", msgs(self.v({"a": {"Variable": "Variable"}}), "warn"))
        self.assertEqual(msgs(self.v({"a": {"Variable": "Variable"}}, keep=["Variable"]), "warn"), "")


class KeyExtractionTests(unittest.TestCase):
    def keys(self, src):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.js"
            p.write_text(src, encoding="utf-8")
            return i18n.js_keys(p)

    def test_finds_t_th_and_tn_calls_in_all_quote_styles(self):
        ks, bad = self.keys("""const a = T('One'), b = T("Two"), c = T(`Three`), d = Th('<b>Four</b>', {}), e = Tn(rows.length, '{n} five', '{n} fives'), f = Tn(fmt(n), '{n} six', '{n} sixes');""")
        self.assertEqual([k for k, _ in ks], ["One", "Two", "Three", "<b>Four</b>", "{n} five", "{n} six"])
        self.assertEqual(bad, [])

    def test_handles_escapes_and_placeholders(self):
        ks, _ = self.keys(r"""T('It\'s {n} o\'clock'); T("Say \"hi\""); T('Line\nbreak');""")
        self.assertEqual([k for k, _ in ks], ["It's {n} o'clock", 'Say "hi"', "Line\nbreak"])

    def test_ignores_look_alike_names_and_member_calls(self):
        ks, _ = self.keys("""INPUT('x'); const MYT = 1; obj.T('no'); someT('no'); fmtT('no'); T ('yes');""")
        self.assertEqual([k for k, _ in ks], ["yes"])

    def test_template_keys_with_expressions_are_rejected(self):
        ks, bad = self.keys("const x = T(`Hello ${name}`);")
        self.assertEqual(ks, [])
        self.assertEqual(len(bad), 1)

    def test_reports_line_numbers(self):
        ks, _ = self.keys("// line 1\n\nT('Third line');")
        self.assertEqual(ks, [("Third line", 3)])


class CheckTests(unittest.TestCase):
    """check() on a tiny fake site: a script asking for a key with no Spanish fails; a data label without Spanish fails."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "js").mkdir()
        (self.tmp / "data").mkdir()
        (self.tmp / "js" / "app.js").write_text("T('Layers'); T('Missing one');", encoding="utf-8")
        (self.tmp / "data" / "series.json").write_text(json.dumps({"vars": [{"label": "Median rent"}, {"label": "Poverty rate"}]}), encoding="utf-8")
        self.saved = i18n.SITE
        i18n.SITE = self.tmp
        self.pages = {"pages": {"map": {"scopes": ["a"], "scripts": ["app.js"]}},
                      "data_labels": [{"file": "series.json", "paths": ["vars[].label"], "pages": ["map"]}]}

    def tearDown(self):
        i18n.SITE = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_keys_and_labels_are_errors(self):
        ps = i18n.check(self.pages, {"a": {"Layers": "Capas", "Median rent": "Alquiler mediano"}}, set())
        e = msgs(ps)
        self.assertIn("no Spanish for: 'Missing one'", e)
        self.assertIn("no Spanish for the label 'Poverty rate'", e)
        self.assertNotIn("'Layers'", e)

    def test_complete_page_has_no_errors_and_stale_keys_warn(self):
        scopes = {"a": {"Layers": "Capas", "Missing one": "Falta uno", "Median rent": "Alquiler mediano", "Poverty rate": "Tasa de pobreza", "Never used": "Nunca usado"}}
        ps = i18n.check(self.pages, scopes, set())
        self.assertEqual(msgs(ps), "")
        self.assertIn("stale key", msgs(ps, "warn"))

    def test_build_writes_one_bundle_per_page(self):
        saved_out = i18n.OUT
        i18n.OUT = self.tmp / "i18n"
        try:
            sizes = i18n.build(self.pages, {"a": {"Layers": "Capas"}})
            text = (self.tmp / "i18n" / "es.map.js").read_text(encoding="utf-8")
        finally:
            i18n.OUT = saved_out
        self.assertIn('I18N.add({"Layers":"Capas"});', text)
        self.assertEqual(sizes["map"][0], 1)


class ModuleTests(unittest.TestCase):
    """A module that loads on first use has its own bundle; its scripts are checked against the page bundle plus that bundle alone."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "js").mkdir()
        (self.tmp / "js" / "app.js").write_text("T('Layers'); I18N.load('views').then(() => 0); I18N.load(\"other\");", encoding="utf-8")
        (self.tmp / "js" / "core.js").write_text("T('Shared core');", encoding="utf-8")
        (self.tmp / "js" / "views.js").write_text("T('Layers'); T('Views');", encoding="utf-8")
        (self.tmp / "js" / "other.js").write_text("T('Other'); T('Views');", encoding="utf-8")
        self.saved = i18n.SITE, i18n.OUT
        i18n.SITE, i18n.OUT = self.tmp, self.tmp / "i18n"
        self.pages = {"pages": {"map": {"scopes": ["a"], "scripts": ["app.js"], "modules": {
            "views": {"scopes": ["v"], "scripts": ["core.js", "views.js"]},
            "other": {"scopes": ["o"], "scripts": ["core.js", "other.js"]}}}}}
        self.scopes = {"a": {"Layers": "Capas"}, "v": {"Views": "Vistas", "Shared core": "Núcleo", "Layers": "Capas"}, "o": {"Other": "Otra"}}

    def tearDown(self):
        i18n.SITE, i18n.OUT = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bundle_is_its_scopes_and_its_scripts_keys_less_the_page(self):
        self.assertEqual(i18n.module_bundle(self.pages, self.scopes, "map", "views"), {"Views": "Vistas", "Shared core": "Núcleo"})
        # 'other' takes from the other module's scope only the keys its own scripts ask for (a shared core file)
        self.assertEqual(i18n.module_bundle(self.pages, self.scopes, "map", "other"), {"Other": "Otra", "Shared core": "Núcleo", "Views": "Vistas"})
        self.assertEqual(msgs(i18n.check(self.pages, self.scopes, set())), "")

    def test_page_scripts_cannot_lean_on_a_module_bundle(self):
        (self.tmp / "js" / "app.js").write_text("T('Views'); I18N.load('views'); I18N.load('other');", encoding="utf-8")
        self.assertIn("page 'map' has no Spanish for: 'Views'", msgs(i18n.check(self.pages, self.scopes, set())))

    def test_a_module_without_spanish_and_a_module_nobody_loads_are_errors(self):
        (self.tmp / "js" / "app.js").write_text("I18N.load('views'); I18N.load('nope');", encoding="utf-8")
        (self.tmp / "js" / "other.js").write_text("T('Not translated');", encoding="utf-8")
        e = msgs(i18n.check(self.pages, self.scopes, set()))
        self.assertIn("module 'other', with its bundle) has no Spanish for: 'Not translated'", e)
        self.assertIn("no script of the page calls I18N.load('other')", e)
        self.assertIn("calls I18N.load('nope') but the page has no module 'nope'", e)

    def test_a_script_in_both_lists_is_an_error(self):
        self.pages["pages"]["map"]["scripts"].append("views.js")
        self.assertIn("listed in 'scripts' and in module 'views'", msgs(i18n.check(self.pages, self.scopes, set())))

    def test_build_writes_module_bundles_and_drops_stale_ones(self):
        self.tmp.joinpath("i18n").mkdir()
        (self.tmp / "i18n" / "es.map.gone.js").write_text("old", encoding="utf-8")
        sizes = i18n.build(self.pages, self.scopes)
        self.assertEqual(sorted(sizes), ["map", "map.other", "map.views"])
        self.assertIn('I18N.add({"Shared core":"Núcleo","Views":"Vistas"});', (self.tmp / "i18n" / "es.map.views.js").read_text(encoding="utf-8"))
        self.assertFalse((self.tmp / "i18n" / "es.map.gone.js").exists())
        self.assertNotIn("Vistas", (self.tmp / "i18n" / "es.map.js").read_text(encoding="utf-8"))


class HeldBackTests(unittest.TestCase):
    """Text that only a module shows stays out of the page bundle: data labels given to a module, the static text of an element a module translates ("html"),
    and the unused keys of a page's "pick" scopes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "js").mkdir()
        (self.tmp / "data").mkdir()
        (self.tmp / "js" / "app.js").write_text("T('Layers'); TK('Shared used'); I18N.load('vuln'); I18N.load('about');", encoding="utf-8")
        (self.tmp / "js" / "vuln.js").write_text("T('Vuln');", encoding="utf-8")
        (self.tmp / "data" / "rvi.json").write_text(json.dumps({"inputs": [{"label": "Poverty rate"}, {"label": "Layers"}]}), encoding="utf-8")
        (self.tmp / "page.html").write_text('<p>Shown at first</p><section id="about"><p>About only</p><div><p>Shown at first</p></div></section><p>Shared shown</p>', encoding="utf-8")
        self.saved = i18n.SITE, i18n.OUT
        i18n.SITE, i18n.OUT = self.tmp, self.tmp / "i18n"
        self.pages = {"pages": {"map": {"file": "page.html", "scopes": ["a", "shared"], "scripts": ["app.js"], "pick": ["shared"], "modules": {
            "vuln": {"scopes": ["v"], "scripts": ["vuln.js"]}, "about": {"scopes": [], "scripts": [], "html": ["about"]}}}},
            "data_labels": [{"file": "rvi.json", "paths": ["inputs[].label"], "pages": ["map"], "modules": {"map": "vuln"}}]}
        self.scopes = {"a": {"Layers": "Capas", "Poverty rate": "Tasa de pobreza", "Shown at first": "Visto al inicio", "About only": "Solo en Acerca de"},
                       "shared": {"Shared used": "Compartida usada", "Shared shown": "Compartida vista", "Shared unused": "Compartida sin uso"}, "v": {"Vuln": "Vuln"}}

    def tearDown(self):
        i18n.SITE, i18n.OUT = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_page_bundle_leaves_module_text_out(self):
        self.assertEqual(sorted(i18n.merged(self.pages, self.scopes, "map")), ["Layers", "Shared shown", "Shared used", "Shown at first"])
        # a label the page's own script asks for stays in the page bundle; the other goes with the module
        self.assertEqual(i18n.module_bundle(self.pages, self.scopes, "map", "vuln"), {"Vuln": "Vuln", "Poverty rate": "Tasa de pobreza"})
        # text shown only inside the element goes with the module; text also shown outside it stays
        self.assertEqual(i18n.module_bundle(self.pages, self.scopes, "map", "about"), {"About only": "Solo en Acerca de"})
        self.assertEqual(msgs(i18n.check(self.pages, self.scopes, set())), "")

    def test_a_label_without_spanish_in_its_module_is_an_error(self):
        del self.scopes["a"]["Poverty rate"]
        self.assertIn("page 'map' (module 'vuln') has no Spanish for the label 'Poverty rate'", msgs(i18n.check(self.pages, self.scopes, set())))

    def test_a_label_module_or_an_element_the_page_lacks_is_an_error(self):
        self.pages["data_labels"][0]["modules"] = {"map": "nope"}
        self.pages["pages"]["map"]["modules"]["about"]["html"] = ["gone"]
        e = msgs(i18n.check(self.pages, self.scopes, set()))
        self.assertIn("'map' has no module 'nope'", e)
        self.assertIn("translates the element #gone, which the page does not have", e)

    def test_without_the_options_the_page_bundle_is_its_scopes(self):
        del self.pages["pages"]["map"]["pick"]
        del self.pages["pages"]["map"]["modules"]["about"]["html"]
        del self.pages["data_labels"][0]["modules"]
        self.assertEqual(i18n.merged(self.pages, self.scopes, "map"), {**self.scopes["a"], **self.scopes["shared"]})

    def test_element_html_counts_nested_elements_of_its_kind(self):
        src = '<div id="x"><div>a</div><div>b<br/></div></div><div>after</div>'
        self.assertEqual(i18n.element_html(src, "x"), '<div id="x"><div>a</div><div>b<br/></div></div>')
        self.assertIsNone(i18n.element_html(src, "y"))


class RepositoryTests(unittest.TestCase):
    def test_committed_sources_have_no_errors(self):
        pages = i18n.load_pages()
        scopes, problems = i18n.load_scopes(pages)
        keep = set(i18n.load_json(i18n.SRC / "keep.json"))
        problems += i18n.check(pages, scopes, keep)
        errs = [p for p in problems if p[0] == "error"]
        self.assertEqual(errs, [], "\n".join(f"{p[1]}:{p[2]} {p[3]}" for p in errs[:20]))

    def test_dictionary_summaries_in_spanish_translate_the_current_english(self):
        # site/data/dictionary.json carries plain_es only where i18n_src/dictionary_plain.json translates the entry's current plain (else the page shows English)
        src = i18n.load_json(i18n.SRC / "dictionary_plain.json")
        for e in i18n.load_json(i18n.SITE / "data" / "dictionary.json")["entries"]:
            if "plain_es" in e:
                self.assertEqual(src[e["id"]], {"en": e["plain"], "es": e["plain_es"]}, e["id"])
        self.assertEqual([p for p in i18n.dictionary_plain() if p[0] == "error"], [])

    @unittest.skipUnless(shutil.which("node"), "Node is not installed")
    def test_language_layer_tests_pass_in_node(self):
        r = subprocess.run(["node", "--test", str(Path(__file__).with_name("i18n_core.test.js"))], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
