"""Tests for the page-weight budget (budget.py, dictionary_src/routes.json; plan item 13, docs/performance.md). No network."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import budget  # noqa: E402

SITE = ROOT / "site"


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = budget.load_routes()

    def test_every_page_and_file_exists(self):
        for name, r in self.R["routes"].items():
            self.assertTrue((SITE / r["page"]).exists(), r["page"])
            for f in r.get("first", []) + r.get("later", []) + r.get("on_use", []):
                self.assertTrue((SITE / "data" / f).exists(), f"{name}: {f}")

    def test_every_library_from_another_host_has_a_size(self):
        for page in SITE.glob("*.html"):
            for s in re.findall(r'<script src="(https?://[^"]+)"', page.read_text(encoding="utf-8")):
                self.assertIn(s, self.R["external"], f"{page.name}: {s}")

    def test_the_map_reads_the_index_of_the_dictionary_on_first_use(self):
        """catalog.json is read first; its index (catalog_index.json) and the Spanish words (catalog_es.json) after ready, when the Catalog tab, the chat or the Economy tab needs
        them: budget.py counts them as 'on first use'."""
        m = self.R["routes"]["map"]
        self.assertIn("catalog.json", m["first"])
        self.assertEqual([f for f in m["on_use"] if f.startswith("catalog")], ["catalog_index.json", "catalog_es.json", "catalog_views.json"])   # and the glossary's definitions (docs/glossary.md); the views when a topic page opens
        js = {f: (SITE / "js" / f).read_text(encoding="utf-8") for f in ("app.js", "catalog.js", "chat.js", "economy.js", "common.js")}
        self.assertNotIn("catalog_index.json", js["app.js"])
        self.assertIn("fetchJson('data/catalog_index.json')", js["common.js"])
        for f in ("catalog.js", "chat.js", "economy.js"):
            self.assertIn("withIndex(S.catalog)", js[f], f)
        self.assertIn("fetchJson('data/catalog_views.json')", js["catalog.js"])   # navigation plan PR 6: only a topic page reads the ready-made views
        row = budget.measure("map", m, self.R["external"])
        self.assertGreater(row["on_use_kb"], 0)

    def test_the_maps_budget_is_the_plans(self):
        self.assertEqual(self.R["routes"]["map"]["budget"], {"script_kb": 250, "data_kb": 250})

    def test_every_page_is_within_its_budget(self):
        rows = [budget.measure(n, r, self.R["external"]) for n, r in self.R["routes"].items()]
        self.assertEqual([r["route"] for r in rows if r["over"]], [], [r["over"] for r in rows])

    def test_the_map_does_not_load_the_chat_or_the_chart_library_with_the_page(self):
        html = (SITE / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("js/chat.js", html)
        self.assertNotIn("chart.umd", html)
        self.assertIn("js/chatboot.js", html)
        boot = (SITE / "js" / "chatboot.js").read_text(encoding="utf-8")
        self.assertRegex(boot, r"SRC = 'js/chat\.js\?v=\d+'")
        eco = (SITE / "js" / "economy.js").read_text(encoding="utf-8")
        self.assertIn(re.search(r"<script src=\"(https://[^\"]*chart[^\"]*)\"", (SITE / "housing.html").read_text(encoding="utf-8")).group(1), eco, "the map loads the same Chart.js as the Housing page")

    def test_the_3d_view_has_the_chat_on_first_use_with_every_method_it_calls(self):
        html = (SITE / "3d.html").read_text(encoding="utf-8")
        self.assertNotIn("js/chat.js", html)
        for f in ("js/chatboot.js", "js/ask3d.js", "css/chat.css"):
            self.assertIn(f, html)
        for name in ("chat_bubble", "send", "close", "delete"):   # the chat's icons are in the page's icon font
            self.assertRegex(html, r"icon_names=[a-z_,]*\b" + name + r"\b")
        chat = (SITE / "js" / "chat.js").read_text(encoding="utf-8")
        called = set(re.findall(r"\bapi\.([a-zA-Z]+)\b", chat)) | set(re.findall(r"chApi\(\)\.([a-zA-Z]+)\b", chat))
        only_mapless = {"mapless", "page"}   # what a page without a map adds (askpage.js); chat.js reads both only when api.mapless is set
        for page, src, start, end, optional in (("3D", "ask3d.js", "const api = {", "\n  };", only_mapless), ("2D", "economy.js", "const ecApi = {", "\n};", only_mapless),
                                                ("without a map", "askpage.js", "const api = {", "\n  };", {"page"})):
            js = (SITE / "js" / src).read_text(encoding="utf-8")
            api = js[js.index(start):]
            api = api[:api.index(end)]
            missing = sorted(m for m in called - optional if not re.search(r"(?:^|,)[ \t]*(?:async[ \t]+)?" + m + r"[ \t]*(?:[:(,]|$)", api, re.M))   # a definition: a key at the start of a line or after a comma
            self.assertEqual(missing, [], f"the {page} page's ECON.api lacks what chat.js calls")
        self.assertIn("api.page = page;", (SITE / "js" / "askpage.js").read_text(encoding="utf-8"))

    def test_every_page_has_the_ask_button_and_loads_the_chat_on_first_use(self):
        """The Ask button on every page (the project lead, 2026-10-26): chatboot.js and the chat's style and icons; chat.js, ask.js and askpage.js are never in a page's first load."""
        boot = (SITE / "js" / "chatboot.js").read_text(encoding="utf-8")
        self.assertRegex(boot, r"PAGE = !MAP && 'js/askpage\.js\?v=\d+'")
        for r in budget.load_routes()["routes"].values():
            html = (SITE / r["page"]).read_text(encoding="utf-8")
            for f in ("js/chatboot.js", "css/chat.css"):
                self.assertIn(f, html, r["page"])
            for f in ("js/chat.js", "js/ask.js", "js/askpage.js"):
                self.assertNotIn(f, html, r["page"])
            for name in ("chat_bubble", "send", "close", "delete"):
                self.assertRegex(html, r"icon_names=[a-z0-9_,]*\b" + name + r"\b", r["page"])

    def test_the_3d_buildings_are_drawn_once_and_the_switch_hides_them(self):
        js = (SITE / "js" / "twin3d.js").read_text(encoding="utf-8")
        scene = js[js.index("function setupScene()"):js.index("function setTerrain(")]
        # at the start and after each switch of base map (baseExtras), and in the style a switch brings in (carryStyle)
        drop = "map.getStyle().layers.filter(l => l.type === 'fill-extrusion' && l.source === vs && l.id !== 'buildings-3d').forEach(l => map.removeLayer(l.id));"
        self.assertIn(drop, scene, "the base style's own buildings would stay up when the switch is off, and draw twice when on")
        self.assertLess(scene.index(drop), scene.index("id: 'buildings-3d'"))
        self.assertIn("baseExtras();", scene[:scene.index("function baseExtras()")])
        self.assertIn("const own = next.layers.filter(l => !(l.type === 'fill-extrusion' && l.source === vs));", scene)

    def test_the_3d_view_draws_before_the_places_arrive(self):
        js = (SITE / "js" / "twin3d.js").read_text(encoding="utf-8")
        start = js[js.index("setupScene();"):js.index("$('#loader').classList.add('hide');")]
        self.assertNotIn("places.json", start, "the places are not fetched before the loader hides")
        self.assertIn("if ($('#lyPlaces').checked) loadPlaces()", js[js.index("$('#loader').classList.add('hide');"):])
        self.assertRegex((SITE / "3d.html").read_text(encoding="utf-8"), r'<input type="checkbox" id="lyPlaces">', "the places start switched off")
        add = js[js.index("function addPlaces()"):js.index("function updatePlacesMode()")]
        self.assertNotIn("muni-hit", add, "the places go under the layers added after them (routes, hazards, plans), not next to the municipalities: the columns and labels stay under them")
        under = re.search(r"const PLACES_UNDER = /(.+)/;", js).group(1)
        for hazard in ("flood-fill", "prot-fill", "landuse-fill", "ce-fill", "ce-line", "slr"):   # added under the municipal lines, so under the places
            self.assertIsNone(re.search(under, hazard), hazard)
        for top in ("hubs-pts", "wcrp-pts", "plan-line"):   # added on top, so above the places
            self.assertIsNotNone(re.search(under, top), top)
        # the route lines go under every point, as on the 2D map (routes pane under the markers), so the point drawn on top of a click is the point (docs/layers.md, "Clicks")
        self.assertIsNone(re.search(under, "routes-line"), "the places' points are drawn over the route lines")
        heat = re.search(r"map\.addLayer\(\{ id: 'places-heat'.*?\}, (\w+)\);", add, re.S).group(1)
        pts = re.search(r"map\.addLayer\(\{ id: 'places-pts'.*?\}, (\w+)\);", add, re.S).group(1)
        self.assertEqual((heat, pts), ("heatBefore", "before"))
        self.assertIn("const heatBefore = map.getStyle().layers.map(l => l.id).find(id => /^routes-/.test(id)) || slotBefore('routes-');", add, "the heat map stays under the route lines (the review of PR #77: San Juan's network vanished under it)")
        tops = re.findall(r"'([\w-]+)'", re.search(r"const TOPS = \[([^\]]*)\]", js).group(1))
        self.assertEqual(tops, ["hubs-", "wcrp-", "plan-"], "the stations, the WCRP pins and the planned route in one order, whichever was switched on first")
        for layer, prefix in (("hubs-pts", "hubs-"), ("wcrp-pts", "wcrp-")):
            self.assertRegex(next(l for l in js.splitlines() if f"id: '{layer}'" in l), rf"topBefore\('{prefix}'\)\);$")
        slots = re.findall(r"'([\w-]+)'", re.search(r"const SLOTS = \[([^\]]*)\]", js).group(1))
        self.assertEqual(slots[0], "routes-", "the route lines are the bottom slot, under the gaps, stops, taxis, integration points and facilities")
        for layer in ("routes-line", "routes-inferred", "routes-approx", "routes-ferry"):
            self.assertRegex(next(l for l in js.splitlines() if f"id: '{layer}'" in l), r"slotBefore\('routes-'\)\);$")

    def test_the_3d_view_loads_the_layers_it_shares_with_the_map_on_use(self):
        """Phase B of the layer menus (docs/layers.md): the layers the 3D view gained from the 2D map start switched off and load the first time they are used."""
        r = self.R["routes"]["3d"]
        html = (SITE / "3d.html").read_text(encoding="utf-8")
        js = (SITE / "js" / "twin3d.js").read_text(encoding="utf-8")
        files = re.findall(r"file: '([\w.]+)'", (SITE / "js" / "core" / "facilities.js").read_text(encoding="utf-8")) + ["barrios.geojson", "population_blocks.json"]
        self.assertEqual(len(files), 28)   # public_schools.geojson added (decision 107, step 3); hex_grid.geojson (step 9)
        start = js[js.index("async function start()"):]
        for f in files:
            self.assertIn(f, r["on_use"])
            self.assertNotIn(f, r["first"] + r["later"])
            self.assertNotIn(f, start, f"{f} is not fetched when the view starts")
        for s in ("facilities3d.js", "core/facilities.js"):
            self.assertNotIn(s, html, "the facility layers' scripts load on first use")
            self.assertIn(f"addJs('js/{s}?v=", js)
        self.assertRegex(html, r'<input type="checkbox" id="lyMuni">', "Límites is off when the view opens, as on the 2D map (2026-11-13)")
        for i in ("lyBarrios", "lyStops", "lyTaxi", "walkRings", "lyOz", "lyPubHousing", "lyLihtc", "lyReservoirs", "lyBroadband", "lyRivers", "lyGroundwater", "lyRain", "lyFire", "lyPolice", "lyTownhalls", "lyLibraries", "lySchools", "lyHistoric", "lyDumping", "lyFprRoutes", "lyPublicos", "lyLinks", "lyTraffic", "lyBridges", "lyAirports", "lyFerries", "lyEvCharge", "lyGaps", "lyXfer"):
            self.assertRegex(html, rf'<input type="checkbox" id="{i}">', f"{i} starts switched off")
        for i in ("lyTerrain", "lyBuildings", "lyRoutes", "lyTrips"):
            self.assertRegex(html, rf'<input type="checkbox" id="{i}" checked>', f"{i} starts switched on")
        # one click, one answer (docs/layers.md, "Clicks"): a single handler decides, so the order in which the layers were switched on cannot (tests/browser/click_order.js
        # clicks it in a browser)
        fac, sup = ((SITE / "js" / f).read_text(encoding="utf-8") for f in ("facilities3d.js", "supply3d.js"))
        self.assertEqual(len(re.findall(r"map\.on\('click'", js)), 1, "one click handler in twin3d.js: no layer's own handler races it")
        self.assertNotIn("map.on('click'", fac)
        self.assertNotIn("onClick:", sup, "a deck.gl object's card goes through the same handler (Supply.card)")
        hand = js[js.index("map.on('click', async e => {"):]
        hand = hand[:hand.index("\n});")]
        steps = [hand.index(s) for s in ("Plan.mapPick(", "Plan.appendPoint(", "deckAt(e.point, deckCards())", "map.queryRenderedFeatures(e.point", "zoomCluster(top)", "areaCard(e.lngLat")]
        self.assertEqual(steps, sorted(steps), "the planner's pick, then deck.gl, then the MapLibre feature on top (a cluster zooms), then the areas")
        for layer, card in (("flood-fill", "floodPopup"), ("prot-fill", "protPopup"), ("landuse-fill", "landusePopup"), ("ce-fill", "comunidadPopup"), ("barrios-hit", "barrioPopup")):
            self.assertIn(f"clickable('{layer}', 'area', f => {card}(f.properties, false))", js, f"{layer}: the 2D map's section (access.js) in the one area card")
        self.assertIn("['stops-cluster', 'stops-count'].forEach(id => clickable(id, 'cluster'))", js)
        self.assertIn("clickable(id, L0.area ? 'area' : L0.line ? 'line' : 'point', f => F.popup(k, f.properties, d))", fac)   # an area layer (broadband hexagons) answers a click as an area
        # the areas a click answers are stacked as the 2D map's panes, whichever was switched on first, so the card lists them in one order
        app = (SITE / "js" / "app.js").read_text(encoding="utf-8")
        z = {k: int(v) for k, v in re.findall(r"(\w+): (\d{3})", re.search(r"const panes = \{([^}]*)\}", app).group(1))}
        z["landuse"] = int(re.search(r"getPane\('landuse'\)\.style\.zIndex = (\d+)", app).group(1))
        soil = (SITE / "js" / "soil.js").read_text(encoding="utf-8")   # the soils and landslide panes are made there, and drawn in 3D by soil3d.js
        z.update({k: int(v) for k, v in re.findall(r"getPane\('(\w+)'\)\.style\.zIndex = (\d+)", soil)})
        areas = re.findall(r"'([\w-]+)'", re.search(r"const AREAS = \[([^\]]*)\]", js).group(1))
        self.assertEqual([a for a in areas if a != "ce-line"], ["slide-img", "landuse-fill", "soil-fill", "prot-fill", "flood-fill", "ce-fill"])
        self.assertEqual(sorted(["comunidades", "flood", "prot", "landuse", "soil", "slide"], key=z.get), ["slide", "landuse", "soil", "prot", "flood", "comunidades"], "the 2D map's panes, from the bottom")
        drawn = js + (SITE / "js" / "soil3d.js").read_text(encoding="utf-8")
        for layer in areas:
            self.assertIn(f"areaBefore('{layer}')", drawn)
        self.assertIn("clickable('soil-fill', 'area', f => soilPopup(f.properties, false))", drawn, "the soil's section of the 2D map in the one area card")
        for s in ("soil.js", "soil3d.js"):
            self.assertNotIn(s, html, "the soils and landslide layers' scripts load on first use")
            self.assertIn(f"addJs('js/{s}?v=", js)

    def test_the_economy_tab_and_the_3d_animation_load_on_use(self):
        """Make room 4 (docs/performance.md): the map's Economy engine, and the 3D view's deck.gl, time series panel and transit supply, are not in the HTML."""
        html = (SITE / "index.html").read_text(encoding="utf-8")
        for f in ("js/economy.js", "js/core/engine.js", "js/core/adapters.js", "js/core/datasets.js", "js/core/reliability.js", "js/core/panel.js"):
            self.assertNotIn(f, html)
        self.assertIn("js/econ_shell.js", html)
        shell = (SITE / "js" / "econ_shell.js").read_text(encoding="utf-8")
        loads = re.findall(r"'(js/[^']+\.js)\?v=\d+'", shell)
        self.assertEqual(loads[-1], "js/economy.js", "the engine first, economy.js last")
        for f in loads:
            self.assertTrue((SITE / f).exists(), f)
        self.assertIn("I18N.load('economy')", shell)
        three = (SITE / "3d.html").read_text(encoding="utf-8")
        for f in ("deck.gl", "js/series3d.js", "js/supply3d.js"):
            self.assertNotIn(f, three)
        r3 = self.R["routes"]["3d"]
        tw = (SITE / "js" / "twin3d.js").read_text(encoding="utf-8")
        self.assertIn(f"src: '{r3['deferred'][0]}', integrity: 'sha384-", tw, "twin3d.js loads the deck.gl that routes.json counts, with its integrity")
        for f in ("series3d.js", "supply3d.js"):
            self.assertRegex(tw, r"addJs\('js/" + f + r"\?v=\d+'\)")
        for f in ("transport.json", "transit_supply.json", "operators.json"):
            self.assertNotIn(f, r3["first"])
            self.assertIn(f, r3["on_use"])

    def test_the_registry_says_who_loads_each_file(self):
        reg = json.loads((SITE / "data" / "registry.json").read_text(encoding="utf-8"))
        rows = {f["file"]: f for f in reg["files"]}
        self.assertIn({"route": "map", "when": "first"}, rows["catalog.json"]["loaded_by"])
        self.assertEqual(rows["places.json"]["loaded_by"], [], "the places load only when their layer is switched on, on the map and in the 3D view")
        self.assertIn({"route": "3d", "when": "later"}, rows["trips.json"]["loaded_by"])
        self.assertEqual(rows["catalog_index.json"]["loaded_by"], [{"route": "data", "when": "first"}], "the index of the dictionary loads on first use on the map and on the area profile (its chat); only the Data page (data.html), which is the catalog, reads it before it is ready")
        self.assertEqual(rows["catalog_domains.json"]["loaded_by"], [{"route": "profile", "when": "first"}], "the area profile groups its tables by the domain of each entry before they draw")
        self.assertEqual(rows["catalog_es.json"]["loaded_by"], [])
        self.assertTrue(all(f["gzip_bytes"] <= f["bytes"] or f["bytes"] < 200 for f in reg["files"]))


if __name__ == "__main__":
    unittest.main()


class Scenarios(unittest.TestCase):
    def test_the_scenario_workspace_loads_on_use(self):
        html = (SITE / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("scenarios.js", html)
        self.assertNotIn("core/scenario.js", html)
        self.assertIn("'js/core/scenario.js?v=", (SITE / "js" / "economy.js").read_text(encoding="utf-8"))
        self.assertTrue((SITE / "samples" / "model_output_sample.csv").exists())
