"""The Learn registry, the figures the lessons quote and the Learn link of every page (learn_src/lessons.json, learn.py; docs/learn.md, HANDOFF decision 106)."""
import copy
import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import learn  # noqa: E402

SITE = ROOT / "site"
REG = learn.load_json(learn.SRC)
GLOSSARY = {t["id"] for t in learn.load_json(ROOT / "dictionary_src" / "glossary.json")}
TOOLS, LAYERS, ES = learn.map_tools(), learn.layer_keys(), learn.spanish()
PAGE = learn.PAGE.read_text(encoding="utf-8")


def probs(reg, page=PAGE):
    return learn.problems(reg, GLOSSARY, TOOLS, LAYERS, ES, page)


def written():
    js = learn.ITEMS_JS.read_text(encoding="utf-8")
    return json.loads(js[js.index("{"):js.rindex("}") + 1])


class Registry(unittest.TestCase):
    def test_sound_and_written(self):
        self.assertEqual(probs(REG), [])
        self.assertEqual(learn.main(["--check"]), 0, "run python learn.py: site/js/learn_items.js is out of date")

    def test_only_built_lessons_reach_the_site(self):
        data = written()
        built = [l["id"] for l in REG["lessons"] if l["status"] == "built"]
        self.assertEqual(sorted(l["id"] for l in data["lessons"]), sorted(built))
        self.assertEqual(data["planned"], len(REG["lessons"]) - len(built))
        text = learn.ITEMS_JS.read_text(encoding="utf-8")
        for l in REG["lessons"]:
            if l["status"] == "planned":
                self.assertNotIn(f'"id":"{l["id"]}"', text, "a planned lesson is not published")
                self.assertNotIn(f'id="lesson-{l["id"]}"', PAGE)

    def test_the_map_has_the_tools_and_layers_the_lessons_name(self):
        self.assertGreaterEqual(len(TOOLS), 25)
        for l in written()["lessons"]:
            for t in l["tools"]:
                self.assertEqual(TOOLS[t["mt"]], t["en"], "the tool's name is the map's own")
                self.assertTrue(t["es"])
            for k in l["layers"]:
                self.assertIn(k, LAYERS)

    def test_the_rules_catch_a_broken_registry(self):
        def broken(change):
            reg = copy.deepcopy(REG)
            change(reg)
            return probs(reg)
        first = next(i for i, l in enumerate(REG["lessons"]) if l["status"] == "built")
        self.assertTrue(any("no tool" in p for p in broken(lambda r: r["lessons"][first]["tools"].append("b:nothing"))))
        self.assertTrue(any("no layer key" in p for p in broken(lambda r: r["lessons"][first]["layers"].append("nolayer"))))
        self.assertTrue(any("no glossary term" in p for p in broken(lambda r: r["lessons"][first]["glossary"].append("no-such-term"))))
        self.assertTrue(any("used twice" in p for p in broken(lambda r: r["lessons"].append(copy.deepcopy(r["lessons"][first])))))
        self.assertTrue(any("English and Spanish" in p for p in broken(lambda r: r["lessons"][first]["title"].pop("es"))))
        self.assertTrue(any("does not start with its part's letter" in p for p in broken(lambda r: r["lessons"][first].update(code="Z9"))))
        # the page and the registry must agree: a lesson marked built with no section, and a section the registry does not call built
        extra = lambda r: r["lessons"].append(dict(copy.deepcopy(r["lessons"][first]), id="nosuch", code="A9", status="built"))   # every lesson is built: a made-up one stands in
        self.assertTrue(any("has no section" in p for p in broken(extra)))
        self.assertTrue(any("does not say it is built" in p for p in broken(lambda r: r["lessons"][first].update(status="planned"))))

    def test_a_figure_never_reads_a_file_an_automated_rebuild_writes(self):
        units = learn.load_json(ROOT / "refresh" / "sources.json")["units"]
        by_bot = {f for u in units.values() if u.get("where") == "ci" for f in (u.get("files") or [])}
        inputs = REG["figures"]["inputs"]
        self.assertEqual(sorted(set(inputs) & by_bot), [], "a rebuild on a runner commits site/data only: a figure read from its files would go stale (docs/learn.md)")
        src = (ROOT / "learn.py").read_text(encoding="utf-8")
        read = set(re.findall(r'data / "([a-z_]+\.(?:json|geojson|bin))"', src))
        self.assertEqual(read, set(inputs), "the registry lists exactly the files learn.py reads")
        helper = (ROOT / "learn_src" / "figures.js").read_text(encoding="utf-8")
        self.assertLessEqual(set(re.findall(r"'data', '([a-z_]+\.(?:json|geojson|bin))'", helper)), set(inputs), "and the files its Node helper reads")


class Figures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = written()["figures"]

    def test_distance_is_the_map_tools_own(self):
        # the flat projection of Core.study.ring: 110,574 m to a degree of latitude, 111,320 m x cos(latitude) to a degree of longitude
        self.assertAlmostEqual(learn.metres(18.0, -66.0, 18.01, -66.0), 1105.74, places=2)
        self.assertAlmostEqual(learn.metres(18.0, -66.0, 18.0, -66.01), 1113.2 * math.cos(math.radians(18.0)), places=2)
        js = (SITE / "js" / "core" / "study.js").read_text(encoding="utf-8")
        self.assertIn("kx = 111320 * Math.cos(lat * Math.PI / 180), ky = 110574", js, "learn.py measures as the Area around a point tool draws")

    def test_rings_grow_and_cover_a_circles_area(self):
        n = self.F["near"]
        self.assertEqual([r["m"] for r in n["rings"]], REG["figures"]["near"]["metres"])
        for a, b in zip(n["rings"], n["rings"][1:]):
            self.assertLessEqual(a["places"], b["places"])
            self.assertLessEqual(a["residents"], b["residents"])
        for r in n["rings"]:
            self.assertAlmostEqual(r["km2"], math.pi * r["m"] ** 2 / 1e6, places=2)
        self.assertGreaterEqual(n["rings"][0]["places"], 1, "the plaza itself is a listed place")
        self.assertEqual(n["place"], REG["figures"]["near"]["place"])

    def test_rings_count_what_the_tool_counts(self):
        # every listing with a point and not withheld, as site/js/studyareas.js loads "Tourism places" for a study area
        js = (SITE / "js" / "studyareas.js").read_text(encoding="utf-8")
        self.assertIn("filter(p => !p.withheld && isFinite(p.lng) && isFinite(p.lat))", js)
        places = learn.load_json(SITE / "data" / "places.json")
        self.assertTrue(all("lat" in p and not p.get("withheld") for p in learn.listed(places)))
        self.assertGreater(len(learn.listed(places)), len(learn.drawn(places)))

    def test_counts_and_rates_agree_with_the_municipio_file(self):
        r, s = self.F["rates"], self.F["shapes"]
        muni = learn.load_json(SITE / "data" / "municipalities.json")
        self.assertEqual(len(r["rows"]), 78)
        self.assertEqual(r["total"], s["counted"], "the municipios' places add to the places the map counts")
        self.assertLess(s["points"], s["counted"], "some counted places are not drawn (docs/places-privacy.md)")
        for name, count, pop, rate in r["rows"]:
            self.assertEqual((count, pop, rate), (muni[name]["assets"], muni[name]["population_2020"], muni[name]["assets_per_1000_residents"]))
        by_count = sorted(r["rows"], key=lambda x: (-x[1], x[0]))
        by_rate = sorted(r["rows"], key=lambda x: (-x[3], x[0]))
        self.assertEqual(r["top_count"]["name"], by_count[0][0])
        self.assertEqual(r["top_rate"]["name"], by_rate[0][0])
        self.assertEqual(r["top_count"]["rank_by_rate"], [x[0] for x in by_rate].index(r["top_count"]["name"]) + 1)
        self.assertEqual(r["top_rate"]["rank_by_count"], [x[0] for x in by_count].index(r["top_rate"]["name"]) + 1)

    def test_shapes_count_the_published_layers(self):
        s = self.F["shapes"]
        self.assertEqual(s["barrios"], 901)
        self.assertEqual(s["municipios"], 78)
        self.assertEqual(s["lines"], len(learn.load_json(SITE / "data" / "streams.geojson")["features"]))
        heat = learn.load_json(SITE / "data" / "heat_surface.json")
        self.assertEqual((s["cell_m"], s["cells_across"], s["cells_down"]), (round(heat["pixel_m"]), heat["size"][0], heat["size"][1]))


class StepTwoFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = written()["figures"]

    def test_count_describes_the_barrios(self):
        import statistics
        c = self.F["count"]
        n = [f["properties"]["assets"] for f in learn.load_json(SITE / "data" / "barrios.geojson")["features"]]
        self.assertEqual((c["barrios"], c["total"], c["max"], c["none"]), (len(n), sum(n), max(n), n.count(0)))
        self.assertEqual((c["mean"], c["median"]), (round(statistics.mean(n), 1), statistics.median(n)))
        self.assertEqual(sum(c["hist"]), len(n), "every barrio is in one class of the chart")
        self.assertEqual(len(c["hist"]), len(c["bins"]))
        self.assertGreater(c["mean"], c["median"], "the lesson's point: a few large barrios pull the mean up")

    def test_overlay_adds_the_municipios(self):
        o = self.F["overlay"]
        muni = learn.load_json(SITE / "data" / "municipalities.json")
        self.assertEqual(o["flood"]["inside"], sum(m["in_sfha"] for m in muni.values()))
        self.assertEqual(o["protected"]["inside"], sum(m["in_protected"] for m in muni.values()))
        for k in ("flood", "protected"):
            self.assertEqual(len(o[k]["top"]), 5)
            self.assertEqual(o[k]["top"], sorted(o[k]["top"], key=lambda r: (-r[3], r[0])))
            self.assertAlmostEqual(o[k]["pct"], o[k]["inside"] / o["places"] * 100, places=1)

    def test_a_walk_is_never_more_than_its_ring(self):
        w = self.F["walk"]
        self.assertEqual([s["min"] for s in w["steps"]], REG["figures"]["walk_minutes"])
        for s in w["steps"]:
            self.assertEqual(s["m"], s["min"] * 80, "4.8 km an hour, the tool's pace")
            self.assertLessEqual(s["residents"], s["ring_residents"])
            self.assertLess(s["km2"], s["ring_km2"])
        for a, b in zip(w["steps"], w["steps"][1:]):
            self.assertLess(a["residents"], b["residents"])
        ring800 = next(r for r in self.F["near"]["rings"] if r["m"] == 800)
        self.assertEqual(next(s for s in w["steps"] if s["m"] == 800)["ring_residents"], ring800["residents"], "the ring beside the walk is lesson B3's ring")
        js = (SITE / "js" / "studyareas.js").read_text(encoding="utf-8")
        self.assertIn("const WALK_MPM = 80, WALK_MIN = [5, 10, 15, 20];", js, "the helper walks at the tool's pace and the lesson offers the tool's minutes")

    def test_hexagons_hold_the_places_the_map_draws(self):
        h = self.F["hex"]
        self.assertEqual(h["places"], self.F["shapes"]["points"])
        self.assertEqual(h["km2"], 10)
        self.assertLess(h["half_cells"], h["cells"] / 2, "half of the places are in far fewer than half of the hexagons")
        self.assertLessEqual(h["max"], h["top10"])
        self.assertEqual(self.F["land_km2"], round(sum(m["land_km2"] for m in learn.load_json(SITE / "data" / "municipalities.json").values())))


class StepThreeFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = written()["figures"]

    def test_attributes_read_one_barrio_and_its_join(self):
        a = self.F["attributes"]
        feats = learn.load_json(SITE / "data" / "barrios.geojson")["features"]
        top = max(feats, key=lambda f: f["properties"]["assets"])["properties"]
        self.assertEqual((a["barrio"], a["assets"], a["geoid"], a["fields"]), (top["barrio"], top["assets"], top["geoid"], len(top)))
        self.assertEqual(a["joined"], a["barrios"], "every barrio of the map has a row in the survey file")
        names = [f["properties"]["barrio"] for f in feats]
        self.assertEqual(a["top_name"]["n"], max(names.count(n) for n in set(names)))
        self.assertGreater(a["shared_names"], 0, "the lesson's point: a name is a poor key")

    def test_relations_add_up(self):
        r = self.F["relations"]
        places = learn.basis(learn.load_json(SITE / "data" / "places.json"))
        with_point = [p for p in places if "lat" in p]
        self.assertEqual(r["loose"], sum(1 for p in with_point if not p.get("barrio")))
        self.assertEqual(r["in_barrio"] + r["loose"] + r["no_point_no_barrio"], r["places"], "every counted place is in a barrio, a point in none, or neither")
        self.assertLessEqual(r["off_island"], r["loose"])
        self.assertEqual(r["barrios"], self.F["shapes"]["barrios"])

    def test_classes_are_the_maps_own(self):
        c = self.F["classes"]
        self.assertEqual(c["n"], 78)
        for m, o in c["methods"].items():
            self.assertEqual(sum(o["counts"]), c["n"], f"{m}: every municipio is in one class")
            self.assertEqual(len(o["edges"]), 6)
            self.assertEqual(o["edges"], sorted(o["edges"]))
            self.assertEqual([o["cls"].count(k) for k in range(5)], o["counts"])
        self.assertEqual(c["methods"]["quantile"]["edges"][0], min(v for v in c["values"] if v is not None))
        self.assertEqual(c["moved"], sum(1 for a, b in zip(c["methods"]["quantile"]["cls"], c["methods"]["equal"]["cls"]) if a != b))
        html = (SITE / "learn.html").read_text(encoding="utf-8")
        for m in "qej":   # the links cut the classes from the newest year alone, as the figure does ("Same classes in every year" off)
            self.assertIn(f'index.html#e=poverty_pct.f.value.blue.{m}.1.0"', html)

    def test_sure_counts_the_maps_flags(self):
        s = self.F["sure"]
        self.assertLess(s["muni"]["pct"], s["barrio"]["pct"], "the lesson's point: smaller areas, wider margins")
        self.assertGreater(s["big"]["residents"], s["small"]["residents"])
        self.assertLess(s["big"]["moe"], s["small"]["moe"])
        self.assertTrue(learn.unreliable(0, 1) and learn.unreliable(10, 3.1) and not learn.unreliable(10, 3) and not learn.unreliable(10, 0))
        js = (SITE / "js" / "core" / "reliability.js").read_text(encoding="utf-8")
        self.assertIn(f"const MOE_SHARE = {learn.MOE_SHARE}, ", js, "the lesson flags what the map flags")


class StepFourFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = written()["figures"]

    def test_areasize_compares_two_sizes_of_the_same_figure(self):
        a = self.F["areasize"]
        self.assertEqual(a["muni"]["n"], 78)
        self.assertLessEqual(a["barrio"]["lo"], a["muni"]["lo"], "smaller areas spread wider")
        self.assertGreaterEqual(a["barrio"]["hi"], a["muni"]["hi"])
        self.assertLessEqual(a["barrio"]["n"], self.F["sure"]["barrio"]["n"] - self.F["sure"]["barrio"]["flagged"], "only the estimates the map does not flag")
        s = a["spread"]
        self.assertLessEqual(s["low"]["rate"], s["high"]["rate"])
        js = (SITE / "js" / "learn_page.js").read_text(encoding="utf-8")
        self.assertNotIn("low.barrio", js, "the barrios of the widest spread are not named on the page")
        self.assertNotIn("high.barrio", js)

    def test_cause_correlations_are_the_maps_own(self):
        import statistics
        c = self.F["cause"]
        pts = [p for p in c["muni"]["points"] if None not in p]
        self.assertEqual(len(pts), c["muni"]["n"])
        self.assertAlmostEqual(statistics.correlation([p[0] for p in pts], [p[1] for p in pts]), c["muni"]["r"], places=2)
        self.assertLess(c["muni"]["r"], 0)
        self.assertLess(abs(c["barrio"]["r"]), abs(c["muni"]["r"]), "the lesson's point: the same relation, weaker by barrio")
        html = (SITE / "learn.html").read_text(encoding="utf-8")
        self.assertIn('index.html#e=bachelors_pct.f,poverty_pct.f"', html)

    def test_leftout_counts_the_privacy_rule(self):
        o = self.F["leftout"]
        places = learn.load_json(SITE / "data" / "places.json")
        w = [p for p in places if p.get("withheld")]
        self.assertEqual(o["withheld"], len(w))
        self.assertEqual(sum(o["reasons"].values()), o["withheld"])
        self.assertFalse(any("lat" in p or "name" in p for p in w), "a withheld listing has no point and no name")
        self.assertEqual(o["counted_not_drawn"], self.F["shapes"]["counted"] - self.F["shapes"]["points"])
        self.assertEqual(o["no_income"], self.F["sure"]["income_barrio"]["none"])


class StepFiveFigures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = written()["figures"]

    def test_owndata_quotes_the_tools_own_limits(self):
        o = self.F["owndata"]
        sa = (SITE / "js" / "studyareas.js").read_text(encoding="utf-8")
        self.assertIn(f"MAX_PTS = {o['max_points']}", sa.replace("200000", str(o["max_points"])))
        self.assertIn(f"up to {o['max_points']:,} points, {o['max_mb']} MB", sa, "the tool's own note says the same limits")
        st = (SITE / "js" / "core" / "study.js").read_text(encoding="utf-8")
        self.assertIn(f"MAX_AREAS = {o['max_areas']}", st)

    def test_qgis_reads_the_published_layers(self):
        q = self.F["qgis"]
        self.assertEqual(q["barrios"]["features"], self.F["shapes"]["barrios"])
        self.assertEqual(q["municipios"]["features"], self.F["shapes"]["municipios"])
        g = q["geoid"]
        self.assertEqual(g["state"] + g["county"] + g["subdivision"], g["full"])
        self.assertEqual(g["state"], "72", "Puerto Rico's code")

    def test_every_lesson_is_built_and_the_guide_prints_alone(self):
        self.assertEqual({l["status"] for l in REG["lessons"]}, {"built"})
        self.assertEqual(written()["planned"], 0)
        html = (SITE / "learn.html").read_text(encoding="utf-8")
        self.assertIn('id="guide"', html)
        self.assertIn('id="lnPrintGuide"', html)
        self.assertIn('id="lnHandout"', html)
        css = (SITE / "css" / "learn.css").read_text(encoding="utf-8")
        self.assertIn("body.ln-print-guide main > :not(#guide)", css)


class Links(unittest.TestCase):
    def test_the_link_map_names_built_lessons_and_real_tools_layers_and_terms(self):
        js = learn.LINKS_JS.read_text(encoding="utf-8")
        L = json.loads(js[js.index("{"):js.rindex("}") + 1])
        built = {l["id"]: l for l in REG["lessons"] if l["status"] == "built"}
        helps = set()   # the help buttons of the 2D map and the 3D view
        for page in ("index.html", "3d.html"):
            helps |= set(re.findall(r'data-help="([a-z0-9_]+)"', (SITE / page).read_text(encoding="utf-8")))
        for mt, (lesson, title) in L["tools"].items():
            self.assertIn(mt, TOOLS); self.assertIn(lesson, built); self.assertEqual(title, built[lesson]["title"])
        for key, (lesson, _) in L["layers"].items():
            self.assertIn(key, helps, "a layer link is keyed by a help button of the map or the 3D view"); self.assertIn(lesson, built)
        for term, (lesson, _) in L["terms"].items():
            self.assertIn(term, GLOSSARY); self.assertIn(lesson, built)
        self.assertEqual(L["tools"]["b:study:saAroundH"][0], "near")
        self.assertEqual(L["terms"]["buffer"][0], "near")
        self.assertIn("walk", L["layers"], "the 400 m rings' help button is 'walk', not the layer key 'rings'")
        for l in built.values():   # a lesson's own tools point back to a lesson (its own, or an earlier one that names the tool first)
            for t in l["tools"]:
                self.assertIn(t, L["tools"])

    def test_the_map_and_the_glossary_use_the_link_map(self):
        app = (SITE / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("addJs('js/learn_links.js?v=5')", app)
        self.assertIn('id="helpLearn"', (SITE / "index.html").read_text(encoding="utf-8"))
        self.assertIn("learnLinks().then((L) => {", (SITE / "js" / "maptools.js").read_text(encoding="utf-8"))
        g = (SITE / "js" / "core" / "glossary.js").read_text(encoding="utf-8")
        self.assertIn("lesson: lessonOf(id)", g)
        self.assertIn("s.onload = s.onerror = () => ok()", g, "a pop-up opens without the lesson link when the file does not come")
        index = (SITE / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("learn_links.js", index, "the link map is never part of the map's first load")

    def test_the_3d_view_links_a_layers_help_to_its_lesson(self):
        three = (SITE / "3d.html").read_text(encoding="utf-8")
        self.assertIn('id="helpLearn"', three)
        self.assertNotIn("learn_links.js", three, "never part of the 3D view's first load")
        js = (SITE / "js" / "twin3d.js").read_text(encoding="utf-8")
        app = (SITE / "js" / "app.js").read_text(encoding="utf-8")
        v = re.search(r"learn_links\.js\?v=(\d+)", app).group(1)
        self.assertIn(f"addJs('js/learn_links.js?v={v}')", js, "the 2D map and the 3D view load the same version")
        links = learn.links(REG)
        helps3d = set(re.findall(r'data-help="([a-z0-9_]+)"', three))
        self.assertIn("places3d", links["layers"], "the 3D view's tourism places have their own help key")
        self.assertTrue({k for k in links["layers"] if k in helps3d} >= {"barrios", "flood", "places3d"})

    def test_the_section_is_called_aprende(self):
        import glob
        for f in glob.glob(str(ROOT / "i18n_src" / "es" / "*.json")):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            if "Learn" in d:
                self.assertEqual(d["Learn"], "Aprende", f"{Path(f).name}: Francis 2026-11-16")


class Page(unittest.TestCase):
    def test_every_lesson_has_its_parts(self):
        for l in written()["lessons"]:
            m = re.search(rf'<section class="block lesson" id="lesson-{l["id"]}".*?</section>', PAGE, re.S)
            self.assertTrue(m, l["id"])
            sec = m.group(0)
            self.assertIn("<h3>In the observatory</h3>", sec)
            self.assertIn("<h3>Try it on the map</h3>", sec)
            self.assertIn('href="index.html#', sec, "a lesson opens the live map")
            self.assertIn("<b>Watch out.</b>", sec)
            self.assertGreaterEqual(sec.count('<details class="ln-check">'), 2, "two questions, answered on the page")
            self.assertIn("<b>Go further.</b>", sec)
            real = re.search(r'<div class="ln-real" id="\w+" aria-live="polite" data-t="skip"></div>', sec)
            self.assertTrue(real, "the figures are drawn from js/learn_items.js: none is typed into the page")

    def test_the_page_is_marked_as_decision_106_asks(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', PAGE)
        self.assertIn("<b>In review.</b>", PAGE)
        self.assertIn("Draft prepared with the help of Claude (artificial intelligence).", PAGE)
        self.assertNotIn("localStorage", (SITE / "js" / "learn_page.js").read_text(encoding="utf-8"), "nothing is stored")
        js = (SITE / "js" / "learn_page.js").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"fetchJson\(([^)]*)\)", js), ["'data/rain_gauges.geojson'"], "the page reads one published file and sends nothing")
        for word in (" fetch(", "sendBeacon", "XMLHttpRequest", "method:", "cookie"):
            self.assertNotIn(word, js)

    def test_every_page_has_the_learn_link_and_its_icon(self):
        pages = sorted(SITE.glob("*.html"))
        self.assertGreaterEqual(len(pages), 22)
        for p in pages:
            html = p.read_text(encoding="utf-8")
            nav = re.search(r'<nav class="views"[^>]*>(.*?)</nav>', html, re.S)
            self.assertTrue(nav, p.name)
            links = re.findall(r'<a class="btn" href="learn\.html"[^>]*>', nav.group(1))
            self.assertEqual(len(links), 1, f"{p.name}: one Learn link in the top bar")
            self.assertEqual("aria-current" in links[0], p.name == "learn.html", p.name)
            self.assertLess(nav.group(1).index('href="dictionary.html"'), nav.group(1).index('href="learn.html"'), f"{p.name}: Learn comes last")
            for names in re.findall(r"icon_names=([a-z0-9_,]+)", html):
                self.assertIn("school", names.split(","), f"{p.name}: the icon font holds the Learn icon")

    def test_the_generators_write_the_learn_link(self):
        gens = sorted((ROOT / "docs" / "analysis").glob("*/make_page.py"))
        made = [g for g in gens if 'href="dictionary.html"' in g.read_text(encoding="utf-8")]
        self.assertGreaterEqual(len(made), 11)
        for g in made:
            src = g.read_text(encoding="utf-8")
            self.assertEqual(src.count('<a class="btn" href="learn.html"'), 1, f"{g.parent.name}: a page made again keeps the Learn link")
            self.assertIn("school", src, g.parent.name)


if __name__ == "__main__":
    unittest.main()
