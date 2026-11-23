"""The WCRP vulnerability index (wcrp_rvi.py; docs/wcrp.md): the method on a small worked example, the original's ranks, the barrios, the hold.

  python -m unittest tests.test_wcrp_rvi
"""
import json
import math
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import wcrp_rvi as W  # noqa: E402

DATA = ROOT / "site" / "data"
load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
AREAS = ["overall", "econ", "edu", "envir", "health", "housing", "infra"]


class Method(unittest.TestCase):
    """A fixture small enough to work out by hand."""

    def test_percentile_is_the_share_of_places_strictly_lower(self):
        self.assertEqual(W.percentile([10, 20, 20, 40, None]), [0.0, 0.25, 0.25, 0.75, None])   # n = 4 values; ties share the lower rank
        self.assertEqual(W.percentile([None, None]), [None, None])

    def test_rank_is_the_fifth_of_the_index(self):
        cases = {0.0: 1, 0.05: 1, 0.2: 1, 0.2001: 2, 0.4: 2, 0.6: 3, 0.8: 4, 0.8001: 5, 0.999: 5, None: None}
        for p, r in cases.items():
            self.assertEqual(W.rank(p), r, p)
        self.assertEqual(W.rank(177 / 885), 1, "float noise at a limit does not push a barrio up a rank")

    def test_an_area_ranks_the_sum_of_its_percentiles(self):
        a = [1, 2, 3, 4, 5]          # percentiles 0, .2, .4, .6, .8
        b = [5, 4, 3, 1, 2]          # percentiles .8, .6, .4, 0, .2
        # sums .8, .8, .8, .6, 1.0 -> share strictly lower among 5: .2, .2, .2, 0, .8
        self.assertEqual(W.combine([W.percentile(a), W.percentile(b)]), [0.2, 0.2, 0.2, 0.0, 0.8])

    def test_a_missing_input_is_made_up_by_the_others_the_white_papers_education_rule(self):
        enrol = [None, 10, 20, 30]   # the first place has nobody aged 3 to 24
        nodip = [40, 10, 20, 30]
        # percentiles: enrol (among 3) -, 0, 1/3, 2/3; no diploma (among 4) .75, 0, .25, .5
        pe, pn = W.percentile(enrol), W.percentile(nodip)
        self.assertEqual(pn, [0.75, 0.0, 0.25, 0.5])
        sums = [2 * 0.75, 0 + 0, 1 / 3 + 0.25, 2 / 3 + 0.5]   # the first doubled
        self.assertEqual(W.combine([pe, pn]), W.percentile([round(s, 9) for s in sums]))
        self.assertEqual(W.combine([pe, pn]), [0.75, 0.0, 0.25, 0.5])

    def test_sub_indicators_then_areas_then_overall(self):
        n = 5
        col = lambda *v: list(v)
        cols = {
            "econ": {None: [col(1, 2, 3, 4, 5)]},
            "edu": {None: [col(5, 4, 3, 2, 1)]},
            "envir": {None: [col(1, 1, 1, 1, 2)]},
            "health": {None: [col(1, 2, 3, 4, 5), col(1, 2, 3, 4, 5)]},
            "housing": {None: [col(2, 1, 4, 3, 5)]},
            "infra": {"telecom": [col(1, 2, 3, 4, 5)], "transport": [col(5, 4, 3, 2, 1)]},
        }
        out = W.build_index(cols, active=[True, True, True, True, False])
        self.assertEqual(out["econ"], [0.0, 0.25, 0.5, 0.75, None], "an inactive place (no residents) is left out of every ranking")
        self.assertEqual(out["envir"], [0.0, 0.0, 0.0, 0.0, None])
        self.assertEqual(out["infra"], [0.0, 0.0, 0.0, 0.0, None], "two opposite sub-indicators cancel")
        # overall = percentile of the sum of the six areas
        areas = ["econ", "edu", "envir", "health", "housing", "infra"]
        sums = [round(sum(out[a][i] for a in areas), 9) for i in range(4)] + [None]
        self.assertEqual(out["overall"], W.percentile(sums))
        self.assertEqual(len(out["overall"]), n)

    def test_the_method_gives_back_the_original_from_its_own_inputs(self):
        """Measured by wcrp_rvi.py on the harvest and kept in the published file: the page states it."""
        r = load(DATA / "wcrp_rvi_barrio.json")["checks"]["reproduced"]
        for a in ("overall", "edu", "health", "housing", "infra"):
            self.assertEqual(r[a]["spearman"], 1.0, a)
            self.assertGreater(r[a]["same_rank_pct"], 98, a)
        self.assertLess(r["econ"]["spearman"], 0.9, "economy does not reproduce, and the page says so")


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load(DATA / "wcrp_rvi_barrio.json")
        cls.inputs = load(DATA / "wcrp_rvi_inputs.json")
        cls.vals = {v["key"]: list(v["years"].values())[0] for v in cls.doc["vars"]}
        cls.barrios = [f["properties"]["geoid"] for f in load(DATA / "barrios.geojson")["features"]]

    def rank_of(self, x):   # as the pages compute it from the stored value (index times 100, two decimals)
        return None if x is None else min(5, max(1, math.ceil(x / 20 - 1e-7)))

    def test_every_one_of_the_901_barrios_matches_barrios_geojson(self):
        self.assertEqual(len(self.barrios), 901)
        self.assertEqual(sorted(self.barrios), self.doc["geo"]["ids"])
        self.assertEqual(self.inputs["geo"]["ids"], self.doc["geo"]["ids"])
        for k, arr in self.vals.items():
            self.assertEqual(len(arr), 901, k)
        for ver in ("orig", "rebuild"):
            for k, arr in self.inputs[ver]["values"].items():
                self.assertEqual(len(arr), 901, k)

    def test_the_originals_ranks_are_fifths(self):
        for a in AREAS:
            arr = self.vals[f"rvi_{a}_orig"]
            have = [x for x in arr if x is not None]
            self.assertEqual(len(have), 887, f"{a}: the 14 barrios with no residents have no value")
            self.assertTrue(all(0 <= x <= 100 for x in have), a)
            n = Counter(self.rank_of(x) for x in have)
            self.assertEqual(sorted(n), [1, 2, 3, 4, 5], a)
            for r, c in n.items():
                self.assertLessEqual(abs(c - len(have) / 5), len(have) / 100, f"{a}: rank {r} holds {c} of {len(have)} barrios, not a fifth")   # ties (the doubled education percentiles) move a few

    def test_the_originals_published_ranks_are_the_fifths_of_its_index(self):
        cache = W.CACHE / "harvest.json"
        if not cache.exists():
            self.skipTest("no harvest in cache/wcrp_rvi (python wcrp_rvi.py)")
        h = load(cache)
        by = {r["GEOID"]: r for r in h["all"]}
        for i, g in enumerate(self.doc["geo"]["ids"]):
            for a in AREAS:
                idx, rk = W.FIELD[a]
                self.assertEqual(self.rank_of(self.vals[f"rvi_{a}_orig"][i]), by[g][rk] or None, f"{g} {a}")
                self.assertEqual(W.rank(by[g][idx]), by[g][rk] or None, f"{g} {a}")

    def test_the_rebuilds_ranks_are_fifths(self):
        for a in AREAS:
            have = [x for x in self.vals[f"rvi_{a}_rebuild"] if x is not None]
            n = Counter(self.rank_of(x) for x in have)
            for r, c in n.items():
                self.assertLessEqual(abs(c - len(have) / 5), len(have) / 100, f"{a}: rank {r} holds {c} of {len(have)}")

    def test_every_dataset_is_barrio_only_and_documented(self):
        entries = {e["id"]: e for e in load(ROOT / "dictionary_src" / "entries" / "wcrp.json")}
        for v in self.doc["vars"]:
            self.assertEqual(v["level"], "barrio")
            self.assertTrue(v["noIsland"])
            e = entries["wcrp." + v["key"]]
            self.assertIn(f"wcrp_rvi_barrio.json:{v['key']}", e["where"]["files"])
            self.assertEqual(e["domain"], "communities")   # WCRP's home domain since decision 81 (c); population stays among its domains
            self.assertIn("population", e["domains"])
        self.assertEqual({m["area"] for m in self.doc["method"]["missing"]}, {"envir"}, "the one input the rebuild leaves out (solid waste facilities) is listed")
        inputs_entry = entries["wcrp.rvi_inputs_rebuild"]
        for k, *_ in W.REBUILD_INPUTS:
            self.assertIn(f"wcrp_rvi_inputs.json:{k}", inputs_entry["where"]["files"], f"{k} has a dictionary entry")

    def test_the_rebuild_uses_the_local_conditions_as_the_original_used_its_inputs(self):
        """decision 41: every input of the original but solid waste facilities has a current source; each maps to the original's column"""
        orig_keys = {k for k, *_ in W.ORIGINAL_INPUTS}
        for k, *_ in W.REBUILD_INPUTS:
            self.assertIn(W.SAME_INPUT[k], orig_keys, k)
        self.assertEqual(set(W.ORIGINAL_INPUTS[i][0] for i in range(len(W.ORIGINAL_INPUTS))) - set(W.SAME_INPUT.values()), {"o_per_capita_income", "o_solid_waste"})
        reb = self.inputs["rebuild"]["values"]
        cond = load(DATA / "conditions_barrio.json")
        at = {g: i for i, g in enumerate(cond["geo"]["ids"])}
        C = {v["key"]: next(iter(v["years"].values())) for v in cond["vars"]}
        for i, g in enumerate(self.doc["geo"]["ids"]):
            j = at[g]
            self.assertEqual(reb["impaired_water_flag"][i], int(C["epa_303d_pct"][j] > 0), g)
            self.assertEqual(reb["nonattainment_flag"][i], int(C["epa_naa_so2_pct"][j] > 0 or C["epa_naa_lead_pct"][j] > 0), g)
            self.assertEqual(reb["landfill_flag"][i], int(C["epa_landfills"][j] > 0), g)
            self.assertEqual(reb["hospital_drive_min"][i], C["hosp_drive_min"][j], g)
        no_road = {g[2:5] for g, v in zip(self.doc["geo"]["ids"], reb["hospital_drive_min"]) if v is None}
        self.assertLessEqual(no_road, {"049", "147", "097", "141"}, "no drive time only in Culebra, Vieques, Isla de Mona (Mayagüez) and an uninhabited barrio of Utuado")
        d = self.doc["checks"]["definitions"]["health_without_hospital"]
        self.assertTrue(set(d["municipios"]) >= {"049", "147"}, "Vieques and Culebra are ranked in health from the other two inputs")
        health = self.vals["rvi_health_rebuild"]
        for i, g in enumerate(self.doc["geo"]["ids"]):
            if g[2:5] in ("049", "147") and self.inputs["rebuild"]["population"][i]:
                self.assertIsNotNone(health[i], f"{g}: ranked in health without the hospital input")

    def test_fewer_intersections_are_more_vulnerable(self):
        """the original's infrastructure reproduces only with the intersection percentile taken on the negated density; the rebuild does the same"""
        self.assertEqual(W.FEWER_IS_WORSE, {"intersection_density"})
        vals = {k: [None] * 4 for k, *_ in W.REBUILD_INPUTS}
        vals["intersection_density"] = [10, 20, 30, 40]
        vals["no_vehicle_hh_pct"] = [5, 5, 5, 5]
        out = W.rebuild(vals, [1, 1, 1, 1])
        self.assertEqual(out["infra"], [0.75, 0.5, 0.25, 0.0], "the barrio with the fewest intersections ranks highest")

    def test_the_economy_hypothesis_is_measured(self):
        r = self.doc["checks"]["reproduced"]
        h = r["econ_income_as_higher_no_unemployment"]
        self.assertGreater(h["spearman"], r["econ"]["spearman"] + 0.2, "a reviewer's hypothesis, stated on the page as one to confirm with Hunter College")


class RefreshCoupling(unittest.TestCase):
    """The rebuild reads conditions_barrio.json, so the refresh that rewrites it must rebuild the WCRP files in the same run (docs/wcrp.md,
    "Refresh"); otherwise this file's tests and wcrp_rvi.py --check fail on main until someone runs wcrp_rvi.py by hand."""

    def setUp(self):
        sys.path.insert(0, str(ROOT))
        import freshness as F
        self.F, self.sched = F, F.load_schedule()
        self.outs = [W.OUT.name, W.OUT_INPUTS.name]

    def test_every_runner_unit_that_rewrites_an_input_reruns_the_index_after_it(self):
        reads = {W.CONDITIONS.name, "acs_barrio.json"}
        units = {k: u for k, u in self.sched["units"].items() if u["where"] == "ci" and reads & set(u.get("files", []))}
        self.assertIn("conditions", units, "the conditions refresh rewrites conditions_barrio.json on a runner")
        for k, u in units.items():
            runs = u["runs"]
            self.assertIn("python wcrp_rvi.py", runs, f"{k}: rebuild the WCRP files in the same run")
            self.assertEqual(runs[-1], "python wcrp_rvi.py", f"{k}: after the script that rewrites its input")
            for f in self.outs:
                self.assertIn(f, u["files"], f"{k}: {f} is published by the run")
                self.assertIn(f, u.get("human_if_changed", []), f"{k}: {f} is WCRP content, reviewed by a person")
            self.assertIn("harvested", u.get("ignore", []), f"{k}: a fresh harvest on a clean runner is not a change of the data")
        self.assertIn("wcrp_rvi.py", self.sched["units"]["housing"]["how"], "the survey's barrio file is rebuilt by hand, and the how says to rerun the index")

    def test_a_run_that_changes_the_index_waits_for_a_person(self):
        F = self.F
        self.assertEqual(F.review_of(self.sched, "conditions", changed=[self.outs[0]]), "human")
        s = {"units": {"u": {"where": "ci", "human_if_changed": ["x.json"]}}, "sources": [{"id": "a", "unit": "u", "review": "auto"}]}
        self.assertEqual(F.review_of(s, "u"), "auto", "routine sources, nothing held changed")
        self.assertEqual(F.review_of(s, "u", changed=["y.json"]), "auto")
        self.assertEqual(F.review_of(s, "u", changed=["x.json"]), "human", "a file of human_if_changed changed")
        self.assertEqual(F.strip_stamps({"versions": {"orig": {"harvested": "2026-10-17", "published": "2022-03"}}}, ["harvested"]),
                         {"versions": {"orig": {"published": "2022-03"}}})

    def test_the_published_files_follow_the_published_conditions(self):
        """what a refresh that skipped wcrp_rvi.py would break: every conditions input of the rebuild equals today's conditions_barrio.json"""
        cond = load(DATA / W.CONDITIONS.name)
        at = {g: i for i, g in enumerate(cond["geo"]["ids"])}
        C = {v["key"]: next(iter(v["years"].values())) for v in cond["vars"]}
        reb = load(W.OUT_INPUTS)["rebuild"]["values"]
        ids = load(W.OUT)["geo"]["ids"]
        direct = {k: how.split(":", 1)[1] for k, _, _, _, how in W.REBUILD_INPUTS if how.startswith("conditions_barrio:") and not how.startswith("conditions_barrio: ")}
        self.assertTrue(direct)
        for k, src in direct.items():
            for i, g in enumerate(ids):
                v = C[src][at[g]]
                self.assertEqual(reb[k][i], None if v is None else round(v, 1), f"{k} {g}: run python wcrp_rvi.py after conditions.py")


class Context(unittest.TestCase):
    """The age groups and the landslide susceptibility are shown beside the index, never as inputs: the white paper's method has neither
    (docs/wcrp.md, "Beside the index")."""

    @classmethod
    def setUpClass(cls):
        cls.doc, cls.inputs = load(W.OUT), load(W.OUT_INPUTS)

    def test_neither_is_an_input(self):
        keys = {k for k, *_ in W.REBUILD_INPUTS}
        self.assertFalse(keys & {k for k, *_ in W.CONTEXT}, "an age group is not an input")
        self.assertFalse(any("acs_age" in how or "under18" in how or "landslide" in how for *_, how in W.REBUILD_INPUTS))
        self.assertEqual({x["key"] for x in self.doc["method"]["rebuild"]}, keys)

    def test_the_age_groups_are_the_survey_s_for_the_rebuild_window(self):
        acs = load(DATA / "acs_barrio.json")
        window = int(self.doc["versions"]["rebuild"]["window"][-4:])
        at = {g: i for i, g in enumerate(acs["geo"]["ids"])}
        V = {v["key"]: v for v in acs["vars"]}
        ctx, moe, ids = self.inputs["rebuild"]["context"], self.inputs["rebuild"]["context_moe"], self.inputs["geo"]["ids"]
        self.assertEqual(set(ctx), {k for k, *_ in W.CONTEXT})
        for key, _, var in W.CONTEXT:
            for i, g in enumerate(ids):
                v, m = V[var]["years"][str(window)][at[g]], V[var]["moe"][str(window)][at[g]]
                self.assertEqual(ctx[key][i], None if v is None else round(v, 1), f"{key} {g}: run python wcrp_rvi.py after small_area.py")
                self.assertEqual(moe[key][i], None if m is None else round(m, 1), f"{key} {g}")
        self.assertTrue(all(x["estimate"] for x in self.doc["method"]["context"]), "labelled as estimates")

    def test_the_landslide_context_is_read_from_main_s_file_not_copied(self):
        ls = load(DATA / "landslide_barrio.json")
        have = {v["key"] for v in ls["vars"]}
        for x in self.doc["method"]["hazards"]:
            self.assertEqual(x["file"], "landslide_barrio.json")
            self.assertIn(x["key"], have)
            self.assertNotIn(x["key"], self.inputs["rebuild"]["values"])
            self.assertNotIn(x["key"], self.inputs["rebuild"]["context"])
        self.assertIn("data/landslide_barrio.json", (ROOT / "site" / "js" / "wcrp_vuln.js").read_text(encoding="utf-8"))


class Held(unittest.TestCase):
    """WCRP is a HUD CDBG-DR program: FPR approved publication on 2026-10-19 (decision 51), the licences included (decision 54). The original states no open
    license, so its class stays 'unstated' and the texts tell others to ask PRDOH and FPR before re-use; no licence is invented."""

    def test_the_originals_license_is_unstated_and_its_review_cleared(self):
        s = load(ROOT / "dictionary_src" / "sources.json")["wcrp_rvi"]
        self.assertEqual(s["licence_class"], "unstated")
        for text in (s["licence"], s["terms_note"]):
            self.assertIn("no open license", text.lower())
            self.assertIn("ask PRDOH and FPR", text)
            self.assertNotRegex(text, r"CC[- ]?BY|CC0|Creative Commons|public domain|ODbL|Open Data Commons", "no licence is invented")
            self.assertNotIn("Francis", text, "no staff names in the dictionary")
        self.assertIn("program's approval", s["licence"])
        self.assertIn("confirmed the same day that its approval covers republishing this source on the observatory", s["terms_note"])
        recs = {r["file"]: r for r in load(ROOT / "dictionary_src" / "datasets.json")["datasets"]}
        for f in ("wcrp_rvi_barrio.json", "wcrp_rvi_inputs.json"):
            self.assertEqual(recs[f]["licence_class"], "unstated", f)
            kinds = {(r["type"], r["status"]) for r in recs[f]["review"]}
            self.assertNotIn(("licence", "open"), kinds, f)
            self.assertIn(("licence", "cleared"), kinds, f)      # decision 54
            self.assertIn(("compliance", "cleared"), kinds, f)   # FPR's approval of 2026-10-19 (decision 51)
            lic = next(r for r in recs[f]["review"] if r["type"] == "licence")
            self.assertIn("FPR confirmed on 2026-10-19 that its approval covers republishing these sources on the observatory (HANDOFF decision 54).", lic["note"], f)
            self.assertIn("ask PRDOH and FPR", lic["note"], f)
            self.assertNotIn("Francis", json.dumps(recs[f], ensure_ascii=False), f)
        # what readers see: the Economy tab's source line (from the file) and the page's "Read with care" item
        self.assertEqual(load(DATA / "wcrp_rvi_barrio.json")["sources"]["wcrp_rvi"]["license"], W.SOURCES["wcrp_rvi"]["license"])
        self.assertNotIn("under review", W.SOURCES["wcrp_rvi"]["license"])
        js = (ROOT / "site" / "js" / "wcrp_vuln.js").read_text(encoding="utf-8")
        self.assertIn("That is not an open license: to re-use them, ask the Puerto Rico Department of Housing and FPR.", js)
        self.assertNotIn("until the Puerto Rico Department of Housing confirms", js)

    def test_the_page_is_published_with_its_in_review_marker_and_the_spanish_is_released(self):
        # Francis, 2026-10-19 (HANDOFF decision 51): the page is published and keeps its "In review" marker; while the marker is on, it is not indexed
        html = (ROOT / "site" / "wcrp.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="robots" content="noindex, nofollow">', html)
        self.assertEqual(html.count('<div class="note caution review-note" role="note" data-ka-note></div>'), 1, "one In review notice, written by core/knowledge.js")
        self.assertIn("<b>In review:</b> the content of this page is under review and may change.", (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8"))
        self.assertNotIn("Draft for review", html)
        knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        self.assertRegex(knowledge, r"id: 'wcrp',.*page: 'wcrp\.html', status: 'published', review: true", "the Knowledge Area's tabs link to WCRP, marked In review (core/knowledge.js)")
        self.assertIn('data-ka="housing"', (ROOT / "site" / "housing.html").read_text(encoding="utf-8"))
        self.assertIn('data-ka="wcrp"', html)
        held = load(ROOT / "i18n_src" / "held_for_review.json")
        self.assertNotIn("wcrp", held["spanish"], "the WCRP page's Spanish is released")
        self.assertNotIn("wcrp_vuln", held["spanish"])
        # the records of the page's release (2026-10-19: the page, decision 51; its plain-language rework and the "Updated 2020–2024" name, the same day)
        releases = [r for r in held["released"] if r["date"] == "2026-10-19"]
        self.assertGreaterEqual(len(releases), 2)
        released = lambda scope: {k for r in releases for k in r["spanish"].get(scope, [])}
        # what was held is what the page says about WCRP, the index, its results and its errors: every such sentence, on the page or in its vulnerability map's module, is released on record and shows Spanish
        spanish = []
        for name in ("wcrp", "wcrp_vuln"):
            scope = {k: v for k, v in load(ROOT / "i18n_src" / "es" / f"{name}.json").items() if not k.startswith("_")}
            spanish += [v if isinstance(v, str) else " ".join(v) for v in scope.values()]
            for k, v in scope.items():
                if (re.search(r"WCRP|RVI|Hunter|CDBG|\bHUD\b|PRDOH|white paper|Social Capital", k) or len(k) > 160) and k != "WCRP":   # the acronym alone is a name, the same in both languages
                    self.assertIn(k, released(name), f"{name}: released on record: {k[:60]!r}")
                    self.assertNotEqual(v, k, f"a released string shows Spanish: {k[:60]!r}")
        for eid in ("wcrp.rvi_overall_orig", "wcrp.rvi_overall_rebuild", "methods.wcrp_rvi"):
            self.assertIn(eid, {e for r in releases for e in r["dictionary_plain"]})
            self.assertNotIn(eid, held["dictionary_plain"])
        # the program description in Francis's wording; never "oversees" or "supervises"
        spanish = " ".join(spanish)
        self.assertIn("Foundation for Puerto Rico administra el programa en colaboración con el Departamento de la Vivienda de Puerto Rico (PRDOH)", spanish)
        for text in (html, spanish):
            self.assertNotRegex(text.lower(), r"overse|supervis")


class Page(unittest.TestCase):
    """wcrp.html after the plain-language rework (Francis, 2026-10-19; docs/wcrp.md, "What it is"): the Social Capital map first, the vulnerability map second with
    one legend of the five levels, Original 2022 and Updated 2020–2024 as the only versions to choose, every other explanation in a closed <details>."""

    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "site" / "wcrp.html").read_text(encoding="utf-8")
        cls.vuln = (ROOT / "site" / "js" / "wcrp_vuln.js").read_text(encoding="utf-8")
        cls.doc = load(DATA / "wcrp_rvi_barrio.json")

    def test_the_social_capital_map_comes_first(self):
        order = re.findall(r'<(?:section|details) class="(?:block|hero)[^"]*" id="(\w+)"', self.html)
        self.assertEqual(order, ["about", "social", "vulnerability", "method", "compare", "sources"])
        self.assertIn("1 · Social Capital map</h2>", self.html)
        self.assertIn("2 · Vulnerability map</h2>", self.html)
        toc = re.search(r'<nav class="toc".*?</nav>', self.html, re.S).group(0)
        self.assertEqual(re.findall(r'<a href="#(\w+)">', toc), ["about", "social", "vulnerability", "method", "sources"])
        for i in re.findall(r'href="#(\w+)"', self.html):
            self.assertRegex(self.html, rf'\sid="{i}"', f"#{i} links to nothing")

    def test_the_version_is_a_slider_from_the_original_through_each_survey_window(self):
        self.assertRegex(self.html, r'<input type="range" id="wmVer" min="0"', "Francis, 2026-11-04: a slider, the original 2022 first")
        self.assertIn('<label for="wmVer">Version</label>', self.html)
        self.assertIn('class="wm-vernote"', self.html, "the slider says that neighbouring windows share years")
        self.assertIn('id="cmpShow"', self.html, "Change opens from the comparison section, not from the slider")
        self.assertIn('id="wmBack"', self.html)
        doc = json.loads((ROOT / "site" / "data" / "wcrp_rvi_barrio.json").read_text(encoding="utf-8"))
        s = doc["series"]
        self.assertEqual(s["windows"][-1], doc["versions"]["rebuild"]["window"], "the slider's last stop is the updated version")
        self.assertEqual(len(s["windows"]), len(s["ends"]))
        for a, lists in s["levels"].items():
            self.assertEqual(len(lists), len(s["ends"]))
            for L in lists:
                self.assertEqual(len(L), len(doc["geo"]["ids"])); self.assertTrue(set(L) <= set("012345"))
        rebuild = next(v for v in doc["vars"] if v["key"] == "rvi_overall_rebuild")["years"]
        idx = next(iter(rebuild.values()))
        last = s["levels"]["overall"][-1]
        rank = lambda x: 0 if x is None else min(5, max(1, math.ceil(x / 20 - 1e-7)))
        self.assertEqual(last, "".join(str(rank(x)) for x in idx), "the last window's levels are the updated version's")

    def test_every_explanation_is_a_closed_details_with_a_heading(self):
        for m in re.finditer(r"<details\b([^>]*)>\s*<summary>(.*?)</summary>", self.html, re.S):
            self.assertNotIn(" open", m.group(1), "closed by default")
            self.assertRegex(m.group(2), r"^<h[2-4]>.*</h[2-4]>$", "a summary is a heading")
            self.assertRegex(m.group(1), r'id="\w+"', "a link can open it")
        ids = re.findall(r'<details\b[^>]*id="(\w+)"', self.html)
        self.assertEqual(sorted(ids), sorted(["socialAbout", "socialNotes", "ceAbout", "care", "method", "compare", "sources"]))

    def test_one_legend_for_the_levels_in_the_maps_colours(self):
        key = re.search(r'<div class="wm-key".*?</div>\s*</div>', self.html, re.S).group(0)
        self.assertEqual(re.findall(r'data-r="(\d)"', key), ["1", "2", "3", "4", "5", "0"])
        self.assertIn("among the 20% least vulnerable barrios", key)
        self.assertIn("among the 20% most vulnerable barrios", key)
        self.assertNotIn('id="wmLegend"', self.html, "the map's own legend is merged into it")
        # the words match the cut points: a level is a fifth of the index (0–20 is 1, above 80 is 5), as wcrp_rvi.py ranks it
        for x, r in ((0, 1), (20, 1), (20.01, 2), (80, 4), (80.01, 5), (100, 5)):
            self.assertEqual(W.rank(x / 100), r)

    def test_every_input_has_its_plain_name_for_the_legend(self):
        plain = set(re.findall(r"(\w+): TK\(", re.search(r"const PLAIN = \{(.*?)\};", self.vuln, re.S).group(1)))
        keys = {x["key"] for x in self.doc["method"]["orig"] + self.doc["method"]["rebuild"]} - {"o_per_capita_income"}   # shown in the original's table, not an input
        self.assertEqual(keys - plain, set(), "inputs without a plain name")
        self.assertIn("NOT_INPUT = new Set(['o_per_capita_income'])", self.vuln)

    def test_the_updated_version_is_never_called_rebuild_on_the_page(self):
        import sys as _s
        _s.path.insert(0, str(ROOT))
        import i18n as I
        keys = [k for f in ("wcrp.js", "wcrp_social.js", "wcrp_vuln.js") for k, _ in I.js_keys(ROOT / "site" / "js" / f)[0]]
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>|<!--.*?-->", " ", self.html, flags=re.S))
        for t in keys + [text] + [v["label"] + " " + v["group"] for v in self.doc["vars"]]:
            self.assertNotRegex(t, r"(?i)\brebuil", t[:80])

    def test_a_reader_reads_level_not_rank(self):
        # review of PR #69: the 1-5 value is a "level" (the Spanish says "nivel"); "rank correlation" (the statistic) and "ranked" (the verb) stay
        import sys as _s
        _s.path.insert(0, str(ROOT))
        import i18n as I
        rank = re.compile(r"(?i)(?<![{\w])ranks?\b(?!\s+(?:correlation|barrios))(?!\})")   # "the index ranks barrios" is the verb
        keys = [k for f in ("wcrp.js", "wcrp_social.js", "wcrp_vuln.js") for k, _ in I.js_keys(ROOT / "site" / "js" / f)[0]]
        text = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>|<!--.*?-->", " ", self.html, flags=re.S))
        M = self.doc["method"]
        data = [x.get("note", "") for x in M["rebuild"]] + [M["context_note"], M["hazards_note"]] + [v["label"] + " " + v["group"] for v in self.doc["vars"]]
        entries = load(ROOT / "dictionary_src" / "entries" / "wcrp.json")
        names = [e["name"] + " " + (e.get("plain") or "") for e in entries if e["id"].startswith("wcrp.rvi_") or e["id"] == "methods.wcrp_rvi"]
        for t in keys + [text] + data + names:
            self.assertIsNone(rank.search(t), t[:100])
        self.assertRegex(self.vuln, r"T\('level \(1-5\)'\)", "the CSV's level columns")


if __name__ == "__main__":
    unittest.main()
