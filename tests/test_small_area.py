"""Tests for small_area.py (plan item 7: ACS 5-year series for barrios, census tracts and block groups, and the Population domain's municipal series).

  python -m unittest discover -s tests -v

Invented cells check the arithmetic of the Population variables (every share is worked out from its numerator and denominator, with the Census Bureau's margin formulas, and an
empty cell gives no value, never a zero), the two things that would read as estimates and are not (the edge of an open-ended interval; a margin of zero, which a share of exactly 100% gets from the formula) and that
no variable is published that the plan says must not be. The published files are checked too, WITHOUT the cache: their ids are the crosswalk's, the variables of each file are the
planned ones, every value is plausible (shares between 0 and 100, no median of 0 or without a margin, no margin on an empty value, no share with a margin of zero), the areas
without a margin for their population are the controlled totals and no other, counts add up from block groups, tracts and barrios to municipios, a municipal value worked out here
equals the one housing_series.json publishes. The cell labels are committed (tests/fixtures/acs_labels), so the label check runs everywhere and the build is shown to stop on a wrong
one. Only two tests need the cache of Census rows (a rebuild gives the files again; the municipal parity) and skip without it.
"""
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import acs_small  # noqa: E402
import housing_series as hs  # noqa: E402
import small_area as sa  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"


def cells(table, values, moe=0.0):
    """{ 'B01001_003': [estimate, moe] } for {cell number: estimate}."""
    return {f"{table}_{n:03d}": [v, moe] for n, v in values.items()}


class PopulationArithmetic(unittest.TestCase):
    def rec(self):
        r = {}
        r.update(cells("B01003", {1: 1000}, 10))
        b = {1: 1000, 26: 520}
        b.update({n: 50 for n in sa.UNDER18})       # 8 cells of 50 = 400 under 18
        b.update({n: 25 for n in sa.AGE65})          # 12 cells of 25 = 300 aged 65 and over
        b.update({n: 0 for n in [*range(7, 20), *range(31, 44)]})   # the ages 18 to 64: real zeros (2026-10-18: the age groups need every age cell)
        r.update(cells("B01001", b, 8))
        r.update(cells("B11001", {1: 400, 2: 300, 8: 80}, 6))
        r.update(cells("B18101", {1: 990, **{n: 10 for n in sa.DISABILITY}}, 4))   # 12 cells of 10 = 120 with a disability
        r.update(cells("B21001", {1: 800, 2: 40}, 5))
        r.update(cells("B27010", {1: 980, **{n: 15 for n in sa.NO_COVERAGE}}, 4))   # 4 cells of 15 = 60 without health insurance
        r.update(cells("B15002", {1: 700, **{n: 7 for n in sa.NO_DIPLOMA}}, 3))   # 16 cells of 7 = 112 adults 25+ without a diploma
        r.update(cells("B09001", {3: 30, 4: 20}, 5))   # children under 3 and aged 3 and 4, in households
        lang = {n: 0 for n in range(2, 68)}
        lang.update({1: 900, **{n: 15 for n in sa.ENGLISH_WELL}})   # 15 cells of 15 = 225 of 900 people speak only English or speak English "very well"
        r.update(cells("B16004", lang, 3))
        r.update(cells("B22010", {1: 400, 2: 180}, 6))   # 180 of 400 households received nutrition assistance
        pov = {n: 0 for n in range(1, 60)}
        pov.update({**{n: 10 for n in sa.CHILD_POOR}, **{n: 5 for n in sa.CHILD_NOT_POOR}})     # 120 children below the poverty level and 60 at or above it
        pov.update({**{n: 6 for n in sa.SENIOR_POOR}, **{n: 9 for n in sa.SENIOR_NOT_POOR}})   # 24 people 65 and older below it and 36 at or above it
        r.update(cells("B17001", pov, 2))
        return r

    def test_each_variable_is_a_share_of_its_own_denominator(self):
        out = sa.derive_pop(self.rec())
        self.assertEqual(out["acs_population"], (1000, 10))
        self.assertAlmostEqual(out["acs_under18_pct"][0], 40.0)
        self.assertAlmostEqual(out["acs_age65plus_pct"][0], 30.0)
        self.assertAlmostEqual(out["acs_female_pct"][0], 52.0)
        self.assertAlmostEqual(out["acs_family_households_pct"][0], 75.0)
        self.assertAlmostEqual(out["acs_living_alone_pct"][0], 20.0)
        self.assertAlmostEqual(out["acs_veteran_pct"][0], 5.0)
        self.assertAlmostEqual(out["acs_disability_pct"][0], 120 / 990 * 100, places=1)
        self.assertAlmostEqual(out["acs_uninsured_pct"][0], 60 / 980 * 100, places=1)
        self.assertAlmostEqual(out["acs_no_hs_pct"][0], 112 / 700 * 100, places=1)
        self.assertAlmostEqual(out["acs_english_lt_very_well_pct"][0], 75.0)   # 100 minus 225 of 900
        self.assertAlmostEqual(out["acs_pan_hh_pct"][0], 45.0)
        self.assertAlmostEqual(out["acs_child_poverty_pct"][0], 120 / 180 * 100, places=1)
        self.assertAlmostEqual(out["acs_senior_poverty_pct"][0], 40.0)
        self.assertEqual(set(out), set(sa.POP_VARS), "every Population variable is made, and nothing else")

    def test_language_and_poverty_by_age_keep_the_census_bureaus_rules(self):
        r = self.rec()
        out = sa.derive_pop(r)
        well = hs.pct((225.0, (3 ** 2 * 15) ** 0.5), (900.0, 3.0))
        self.assertEqual(out["acs_english_lt_very_well_pct"], (round(100 - well[0], 2), well[1]), "the complement of a share has the share's margin")
        kids = hs.pct((120.0, (2 ** 2 * 12) ** 0.5), (180.0, (2 ** 2 * 24) ** 0.5))
        self.assertEqual(out["acs_child_poverty_pct"], kids, "the denominator is the same age group below and at or above the poverty level, not everyone")
        old = hs.pct((24.0, (2 ** 2 * 4) ** 0.5), (60.0, (2 ** 2 * 8) ** 0.5))
        self.assertEqual(out["acs_senior_poverty_pct"], old)
        r["B16004_001"] = [900, None]   # a total the Census Bureau controls has no margin: it counts as zero and the share keeps the margin of its numerator
        self.assertEqual(sa.derive_pop(r)["acs_english_lt_very_well_pct"], (75.0, round((3 ** 2 * 15) ** 0.5 / 900 * 100, 2)))
        del r["B17001_004"]   # an empty cell: no value, never a share of the cells that are left
        again = sa.derive_pop(r)
        self.assertNotIn("acs_child_poverty_pct", again)
        self.assertIn("acs_senior_poverty_pct", again)

    def test_poverty_by_age_is_not_published_below_the_municipio(self):
        for k in ("acs_child_poverty_pct", "acs_senior_poverty_pct"):
            self.assertIn(k, sa.EXCLUDED, "flagged less reliable for more than half of the barrios (docs/small-area.md)")
            self.assertIn(k, sa.POP_VARS)
        for k in ("acs_english_lt_very_well_pct", "acs_pan_hh_pct"):
            self.assertIn(k, sa.SELECTION["barrio"])
            self.assertIn(k, sa.SELECTION["tract"])
            self.assertNotIn(k, sa.SELECTION["block-group"])

    def test_a_margin_follows_the_census_bureaus_formula_and_is_not_zero_for_a_share(self):
        out = sa.derive_pop(self.rec())
        for k in ("acs_under18_pct", "acs_age65plus_pct", "acs_living_alone_pct", "acs_disability_pct"):
            self.assertGreater(out[k][1], 0, k)
        # the share of 400 of 1000 with the margin of the numerator sqrt(8 cells x 8^2) and of the denominator 8 (hs.pct, the formula the municipal series use)
        e, m = hs.pct((400.0, (8 ** 2 * 8) ** 0.5), (1000.0, 8.0))
        self.assertEqual(out["acs_under18_pct"], (e, m))

    def test_a_controlled_total_has_a_margin_of_zero_and_the_share_keeps_the_margin_of_its_numerator(self):
        r = self.rec()
        r["B01001_001"] = [1000, None]            # the Census Bureau controls the total (no margin) for the island and for 76 municipios
        out = sa.derive_pop(r)
        for k in ("acs_under18_pct", "acs_age65plus_pct", "acs_female_pct"):
            self.assertIsNotNone(out[k][1], f"{k}: a share of a controlled total still has a margin")
        self.assertAlmostEqual(out["acs_under18_pct"][1], (8 ** 2 * 8) ** 0.5 / 1000 * 100, places=2)   # the numerator's margin over the total, in percent
        self.assertEqual(out["acs_population"][1], 10, "the total population itself is read as the Census Bureau gives it")
        r["B01003_001"] = [1000, None]
        self.assertIsNone(sa.derive_pop(r)["acs_population"][1], "no margin is made up for a controlled total")

    def test_an_empty_cell_gives_no_value_never_a_zero(self):
        r = self.rec()
        r["B18101_001"] = [None, None]            # the Census Bureau gives no estimate for the area
        r["B21001_002"] = [None, None]
        out = sa.derive_pop(r)
        self.assertNotIn("acs_disability_pct", out)
        self.assertNotIn("acs_veteran_pct", out)
        self.assertIn("acs_under18_pct", out)     # the others are untouched
        r2 = self.rec()
        del r2["B01001_003"]                      # a missing cell in a sum: no share, not a share of what is left
        self.assertNotIn("acs_under18_pct", sa.derive_pop(r2))
        self.assertIn("acs_age65plus_pct", sa.derive_pop(r2))

    def test_a_real_zero_stays_a_zero(self):
        r = self.rec()
        r.update(cells("B21001", {1: 800, 2: 0}, 5))
        self.assertEqual(sa.derive_pop(r)["acs_veteran_pct"][0], 0.0, "no veterans among 800 adults is a result")


class WhatIsNotAnEstimate(unittest.TestCase):
    """The Census Bureau prints boundary values and all-or-nothing shares that read like estimates (found by the review of pull request 4 in the published tracts and barrios)."""

    def test_a_median_at_the_edge_of_an_open_interval_or_of_zero_is_no_value(self):
        rec = {}
        rec["B25071_001"] = [51, None]                    # 'rent is 50% or more of income': the boundary, no margin (code -333333333)
        rec["B19013_001"] = [2499, None]                  # 'under $2,500'
        rec["B25035_001"] = [0, 2]                        # 2017-2021 prints a median year built of 0 for two tracts and two barrios
        rec["B25077_001"] = [180000, 12000]               # a real median keeps its value and its margin
        out = sa.variables(rec, 2024)
        for k in ("median_rent_pct_income", "median_hh_income", "median_year_built"):
            self.assertNotIn(k, out, k)
        self.assertEqual(out["median_home_value"], (180000, 12000))

    def test_a_share_whose_margin_works_out_to_zero_has_no_margin(self):
        """Found by the second review of pull request 4: the proportion formula gives zero when the numerator's margin is the share times the denominator's margin, not only for 100%."""
        cells = [("acs_female_pct", (192.0, 120.0), (440.0, 275.0), 43.64),             # a barrio of Orocovis, 2018-2022
                 ("acs_female_pct", (4.0, 7.0), (8.0, 14.0), 50.0),                       # a barrio of Ceiba, 2020-2024
                 ("internet_subscription_pct", (1472.0, 253.0), (1664.0, 286.0), 88.46)]   # a tract of Carolina, 2019-2023
        for key, num, den, share in cells:
            self.assertEqual(hs.pct(num, den), (share, 0.0), f"{key}: the premise, the formula gives a margin of zero")
            self.assertEqual(sa.clean({key: hs.pct(num, den)})[key], (share, None), key)
        self.assertEqual(sa.clean({"acs_under18_pct": (43.64, 0.01)})["acs_under18_pct"], (43.64, 0.01), "a small margin that is not zero is kept")

    def test_a_share_of_one_hundred_has_no_margin_and_a_share_of_zero_keeps_its_margin(self):
        self.assertEqual(hs.pct((141.0, 58.0), (141.0, 58.0)), (100.0, 0.0), "the premise: the proportion formula gives a margin of zero when the numerator is the denominator")
        zero = hs.pct((0.0, 15.0), (800.0, 90.0))   # no veterans among 800 adults: a zero cell carries a modelled margin, so the share keeps one
        self.assertGreater(zero[1], 0, "the premise: the formula gives a share of 0% the margin of its numerator, not zero")
        out = sa.clean({"owner_occupied_pct": (100.0, 0.0), "poverty_pct": (0.0, 0.0), "acs_veteran_pct": (100, 3.2), "vacancy_pct": (4.0, 1.1), "housing_units": (0, 0), "acs_disability_pct": zero})
        self.assertEqual(out["owner_occupied_pct"], (100.0, None))
        self.assertEqual(out["acs_disability_pct"], zero, "a share of 0% keeps the margin the formula gives it (a real zero is a result, and the CSV by area marks it less reliable)")
        self.assertEqual(out["poverty_pct"], (0.0, None), "an invented cell: a margin of zero would read as exact, whatever the share")
        self.assertEqual(out["acs_veteran_pct"], (100, 3.2), "a margin that is not zero is kept")
        self.assertEqual(out["vacancy_pct"], (4.0, 1.1))
        self.assertEqual(out["housing_units"], (0, 0), "a count of zero is not a share")

    def test_every_median_is_in_the_list_the_rule_uses(self):
        self.assertEqual(sa.MEDIANS, {k for k in set(sa.WAVE1 + sa.WAVE2 + sa.AGE) if k.startswith("median_")})


class WhatIsPublished(unittest.TestCase):
    def test_nothing_the_plan_leaves_out_is_published_below_the_municipio(self):
        for level, keys in sa.SELECTION.items():
            self.assertFalse(set(keys) & set(sa.EXCLUDED), level)
            self.assertEqual(len(keys), len(set(keys)), level)
        for k in ("renter_cost_burden_pct", "renter_severe_burden_pct", "owner_cost_burden_pct"):
            self.assertIn(k, sa.EXCLUDED, "cost burden is not usable below municipio: the margin of the share is 36 points for a tract and 55 for a block group")

    def test_every_variable_comes_from_a_formula_that_exists(self):
        known = set(sa.POP_VARS)
        rec = {}
        for table in sa.TABLES:
            for n in range(1, 60):
                rec[f"{table}_{n:03d}"] = [10.0, 1.0]
        known |= set(sa.hs.derive(rec, 2024)) | set(sa.es.derive_econ(rec))
        for level, keys in sa.SELECTION.items():
            self.assertFalse(set(keys) - known, f"{level}: no formula for {sorted(set(keys) - known)}")

    def test_block_groups_get_the_first_wave_and_the_age_variables_only(self):
        bg = set(sa.SELECTION["block-group"])
        self.assertEqual(bg, set(sa.WAVE1 + sa.AGE))
        self.assertTrue(bg < set(sa.SELECTION["tract"]) and set(sa.SELECTION["tract"]) == set(sa.SELECTION["barrio"]))

    def test_the_cells_are_the_ones_the_census_bureau_says_they_are_in_every_vintage(self):
        for y in sa.VINTAGES:   # the labels are committed (tests/fixtures/acs_labels): no cache and no network needed
            self.assertEqual(sa.check_labels(y), [], y)

    def test_a_wrong_cell_is_noticed_and_the_build_stops_before_it_reads_anything(self):
        real = sa.group_labels

        def swapped(group, year):
            L = dict(real(group, year))
            if group == "B01001":
                L["B01001_002"], L["B01001_026"] = L["B01001_026"], L["B01001_002"]   # men and women swapped
            return L
        sa.group_labels = swapped
        try:
            self.assertTrue(sa.check_labels(2024))
            with self.assertRaises(SystemExit) as stop:
                sa.build(check=True)
            self.assertIn("cell labels are not what the formulas expect", str(stop.exception))
        finally:
            sa.group_labels = real


@unittest.skipUnless(all((DATA / f).exists() for f in (sa.POP_FILE, *sa.FILES.values())), "the series files are not built yet")
class PublishedFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: json.loads((DATA / name).read_text(encoding="utf-8")) for name in sa.FILES.values()}
        cls.pop = json.loads((DATA / sa.POP_FILE).read_text(encoding="utf-8"))
        cls.cw = sa.crosswalk()

    def test_each_file_names_its_areas_by_the_crosswalks_ids_in_its_order(self):
        for level, name in sa.FILES.items():
            self.assertEqual(self.docs[name]["geo"]["ids"], self.cw[level], name)
            self.assertEqual(self.docs[name]["level"], level)
            n = len(self.cw[level])
            for v in self.docs[name]["vars"]:
                for y, arr in v["years"].items():
                    self.assertEqual(len(arr), n, f"{name} {v['key']} {y}")
                    self.assertEqual(len(v["moe"][y]), n)

    def test_the_municipal_file_ends_with_puerto_rico_in_the_order_of_the_other_series(self):
        econ = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))["geo"]
        self.assertEqual(self.pop["geo"], {"ids": econ["ids"], "names": econ["names"]})
        for v in self.pop["vars"]:
            for arr in v["years"].values():
                self.assertEqual(len(arr), 79)
            self.assertTrue(v["sources"] == ["acs"] and v["family"] == "population" and v["type"] in ("count", "rate"))

    def test_counts_add_up_from_block_groups_tracts_and_barrios_to_municipios(self):
        for level, name in sa.FILES.items():
            doc = self.docs[name]
            by = {v["key"]: v for v in doc["vars"]}
            for key in ("acs_population", "housing_units", "households"):
                for y, arr in by[key]["years"].items():
                    sums = defaultdict(float)
                    for g, x in zip(doc["geo"]["ids"], arr):
                        if x is not None:
                            sums[g[:5]] += x
                    if key == "acs_population":
                        ref = next(v for v in self.pop["vars"] if v["key"] == "acs_population")["years"][y]
                    else:
                        ref = next(v for v in json.loads((DATA / "housing_series.json").read_text(encoding="utf-8"))["vars"] if v["key"] == key)["years"][y]
                    ids = self.pop["geo"]["ids"]
                    off = [(ids[i], sums[ids[i]], ref[i]) for i in range(78) if abs(sums[ids[i]] - (ref[i] or 0)) > 0.5]
                    self.assertEqual(off, [], f"{level} {key} {y}: municipios where the pieces do not add up")

    def test_block_groups_add_up_to_their_tract(self):
        bg, tr = self.docs["acs_blockgroup.json"], self.docs["acs_tract.json"]
        for key in ("acs_population", "housing_units", "households"):
            vb = next(v for v in bg["vars"] if v["key"] == key)
            vt = next(v for v in tr["vars"] if v["key"] == key)
            for y in vb["years"]:
                sums = defaultdict(float)
                for g, x in zip(bg["geo"]["ids"], vb["years"][y]):
                    if x is not None:
                        sums[g[:11]] += x
                off = [g for g, x in zip(tr["geo"]["ids"], vt["years"][y]) if x is not None and abs(sums[g] - x) > 0.5]
                self.assertEqual(off, [], f"{key} {y}: tracts that are not the sum of their block groups")

    def test_the_measurement_agrees_with_the_files_it_reads(self):
        m = sa.measure()
        self.assertEqual(set(m), {v["key"] for d in self.docs.values() for v in d["vars"]})
        self.assertEqual(m["acs_population"]["tract"]["areas"], len(self.cw["tract"]))
        self.assertEqual(m["acs_population"]["municipio"]["with_margin"], 2, "only Culebra and Maricao have a margin for the total population: the Census Bureau controls the other totals")
        self.assertTrue(sa.unreliable(0, 1) and sa.unreliable(10, 3.1) and not sa.unreliable(10, 3) and not sa.unreliable(None, 3) and not sa.unreliable(10, None) and not sa.unreliable(0, 0))
        self.assertIn("| Median gross rent (`median_gross_rent`) |", sa.measure_table())

    def test_the_variables_of_each_file_are_the_planned_ones(self):
        for level, name in sa.FILES.items():
            doc = self.docs[name]
            self.assertEqual([v["key"] for v in doc["vars"]], [k for k in sa.SELECTION[level] if k not in doc["notes"]["left_out"]], level)
            self.assertEqual(doc["notes"]["left_out"], [], f"{level}: a planned variable whose table has no rows at this level would be listed here")
        self.assertEqual([v["key"] for v in self.pop["vars"]], list(sa.POP_VARS))

    def test_every_published_value_is_plausible(self):
        bad = []
        for name, doc in {**self.docs, sa.POP_FILE: self.pop}.items():
            for v in doc["vars"]:
                key = v["key"]
                for y, arr in v["years"].items():
                    for i, (x, m) in enumerate(zip(arr, v["moe"][y])):
                        if x is None:
                            if m is not None:
                                bad.append((name, key, y, i, "a margin with no estimate"))
                            continue
                        if m is not None and m < 0:
                            bad.append((name, key, y, i, "a negative margin"))
                        if key.endswith("_pct") and not 0 <= x <= 100:
                            bad.append((name, key, y, i, f"a share of {x}"))
                        if key.endswith("_pct") and m == 0:
                            bad.append((name, key, y, i, "a share with a margin of zero reads as exact"))
                        if key in sa.MEDIANS and (x == 0 or m is None):
                            bad.append((name, key, y, i, "a median that is 0 or has no margin is the edge of an open interval, not an estimate"))
        self.assertEqual(bad[:6], [], f"{len(bad)} implausible values")

    def test_the_areas_with_no_margin_for_their_population_are_the_controlled_totals_and_no_other(self):
        """The Census Bureau controls the total population of the island and of 76 of the 78 municipios to its own estimate (raw margin code -555555555) and prints no margin: that is 77 values of the
        municipal file in every window, plus one barrio (Florida Adentro, which is its own municipio). No tract and no block group is controlled."""
        def missing(doc):
            v = next(x for x in doc["vars"] if x["key"] == "acs_population")
            return {y: sum(1 for e, m in zip(v["years"][y], v["moe"][y]) if e is not None and m is None) for y in v["years"]}
        self.assertEqual(missing(self.pop), {str(y): 77 for y in sa.VINTAGES})
        self.assertEqual(missing(self.docs["acs_barrio.json"]), {str(y): 1 for y in sa.VINTAGES})
        self.assertEqual(missing(self.docs["acs_tract.json"]), {str(y): 0 for y in sa.VINTAGES})
        self.assertEqual(missing(self.docs["acs_blockgroup.json"]), {str(y): 0 for y in sa.VINTAGES})

    def test_what_the_documents_say_about_missing_estimates_is_what_the_files_hold(self):
        rent = {lv: sum(1 for x in next(v for v in self.docs[name]["vars"] if v["key"] == "median_gross_rent")["years"][str(sa.VINTAGES[-1])] if x is None) for lv, name in sa.FILES.items() if lv != "block-group"}
        self.assertEqual(rent, {"barrio": 372, "tract": 124}, "median gross rent has no estimate for 41% of barrios and 13% of tracts (docs/small-area.md, methods.small_area_estimates)")

    def test_the_figures_of_the_guide_and_of_the_dictionary_are_the_measured_ones(self):
        guide = (ROOT / "docs" / "small-area.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        self.assertIn(sa.measure_table(), guide, "docs/small-area.md section 4 is the output of `python small_area.py --measure`: paste it again after a new window")
        import re
        m = sa.measure()
        quoted = 0
        for path in sorted((ROOT / "dictionary_src" / "entries").glob("*.json")):
            for e in json.loads(path.read_text(encoding="utf-8")):
                text = " ".join([e.get("how_to_read", "")] + list(e.get("caveats", [])))
                for hit in re.finditer(r"above 30% of the estimate.*? for (.+?) that have a value", text):
                    key = e["id"].split(".", 1)[1]
                    if key not in m:
                        continue
                    for share, where in re.findall(r"(\d+%|less than 1%|more than 99%) of (municipalities|barrios|census tracts|block groups)", hit.group(1)):
                        lv = {"municipalities": "municipio", "barrios": "barrio", "census tracts": "tract", "block groups": "block-group"}[where]
                        r = m[key][lv]
                        self.assertEqual(share, sa.share_text(r["flagged"], r["value"]), f"{e['id']}: {where}")
                        quoted += 1
        self.assertGreater(quoted, 80, "the entries quote the share flagged at each level: this test reads them (a sentence that changed shape is not tested)")

    def test_a_table_the_census_bureau_does_not_publish_for_block_groups_is_not_in_that_file(self):
        keys = {v["key"] for v in self.docs["acs_blockgroup.json"]["vars"]}
        for banned in ("poverty_pct", "gini", "acs_disability_pct", "median_owner_income"):
            self.assertNotIn(banned, keys)
        self.assertIn("poverty_pct", {v["key"] for v in self.docs["acs_tract.json"]["vars"]})

    def test_empty_is_null_and_the_values_are_not_made_up(self):
        for name, doc in self.docs.items():
            for v in doc["vars"]:
                for y, arr in v["years"].items():
                    for x, m in zip(arr, v["moe"][y]):
                        if x is None:
                            self.assertIsNone(m, f"{name} {v['key']}: a margin with no estimate")
        rent = next(v for v in self.docs["acs_blockgroup.json"]["vars"] if v["key"] == "median_gross_rent") if any(v["key"] == "median_gross_rent" for v in self.docs["acs_blockgroup.json"]["vars"]) else None
        self.assertIsNone(rent, "median rent is a second-wave variable: block groups do not get it")
        tr = next(v for v in self.docs["acs_tract.json"]["vars"] if v["key"] == "median_gross_rent")["years"][str(sa.VINTAGES[-1])]
        self.assertGreater(sum(1 for x in tr if x is None), 50, "the Census Bureau gives no rent estimate for some tracts: they stay empty")

    def test_the_municipal_values_worked_out_here_equal_the_published_series(self):
        v = sa.VINTAGES[-1]
        if not (acs_small.CACHE / str(v) / "B25077_municipio.json").exists():
            self.skipTest("the cache of Census rows is not on this machine")
        mun = {g: sa.variables(r, v) for g, r in sa.records("municipio", v).items()}
        hsj = json.loads((DATA / "housing_series.json").read_text(encoding="utf-8"))
        ids = self.pop["geo"]["ids"]
        n = bad = 0
        for var in hsj["vars"]:
            arr = (var.get("years") or {}).get(str(v))
            if not arr or var["key"] not in sa.WAVE1 + sa.WAVE2 + sa.AGE:
                continue
            for i, g in enumerate(ids[:78]):
                got = mun.get(g, {}).get(var["key"])
                if got is None or arr[i] is None:
                    continue
                n += 1
                bad += abs(arr[i] - got[0]) > 0.011
        self.assertGreater(n, 800)
        self.assertEqual(bad, 0, "the same formulas make the municipal and the sub-municipal values")

    def test_the_cached_census_rows_give_the_published_files_again(self):
        if not all((acs_small.CACHE / str(v) / f"B25077_{lv}.json").exists() for v in sa.VINTAGES for lv in ("tract", "barrio", "block-group", "municipio")):
            self.skipTest("the cache of Census rows is not on this machine (python small_area.py makes it)")
        self.assertEqual(sa.build(check=True), 0)

    def test_the_files_are_small_enough_for_a_lazy_load(self):
        for name in sa.FILES.values():
            self.assertLess((DATA / name).stat().st_size, 2.5e6, name)


class AgeArithmetic(unittest.TestCase):
    """The age bands and groups (2026-10-18): the cells come from the labels, add up to the total, and the share keeps the margin of its count."""

    def test_the_bands_and_groups_are_made_of_the_age_cells_inside_them(self):
        self.assertEqual(sa.age_cells(0, 4), [3, 27])
        self.assertEqual(sa.age_cells(15, 19), [6, 7, 30, 31], "15 to 19 is 15-17 plus 18-19")
        self.assertEqual(sa.age_cells(20, 24), [8, 9, 10, 32, 33, 34], "20 to 24 is 20, 21 and 22-24")
        self.assertEqual(sa.age_cells(60, 64), [18, 19, 42, 43])
        self.assertEqual(sa.age_cells(85, None), [25, 49])
        self.assertEqual(set(sa.age_cells(0, 17)), set(sa.UNDER18))
        self.assertEqual(set(sa.age_cells(65, None)), set(sa.AGE65))
        covered = sorted(c for _, r in sa.AGE_BANDS for c in sa.age_cells(*r))
        self.assertEqual(covered, list(range(3, 26)) + list(range(27, 50)), "the 18 five-year bands cover every age cell once")
        self.assertEqual(len(sa.AGE_BANDS), 18)

    def test_the_counts_add_up_to_the_total_and_the_shares_to_100(self):
        rec = cells("B01001", {1: 2300, **{n: 50 for n in range(3, 26)}, **{n: 50 for n in range(27, 50)}}, 9)
        rec.update(cells("B09001", {3: 60, 4: 35}, 12))
        out = sa.age_values(rec, sa.AGE_MUNI)
        bands = [k for k, _ in sa.AGE_BANDS]
        self.assertEqual(sum(out[k][0] for k in bands), 2300)
        self.assertAlmostEqual(sum(out[k + "_pct"][0] for k in bands), 100, delta=0.1)
        self.assertEqual(out["acs_age0to4"][0] + sum(out[k][0] for k in ("acs_age5to17", "acs_age18to24", "acs_age25to44", "acs_age45to64", "acs_age65plus")), 2300)
        self.assertEqual(sum(out[k][0] for k in ("acs_under18", "acs_age18to44", "acs_age45to64", "acs_age65plus")), 2300)
        self.assertEqual(out["acs_age_under3"], (60, 12))
        self.assertAlmostEqual(out["acs_age15to19"][1], (4 * 81) ** 0.5, places=2, msg="the margin of a sum is the square root of the sum of the squares")
        self.assertEqual(out["acs_age_under3_pct"][0], round(60 / 2300 * 100, 2))

    def test_a_controlled_count_has_no_margin_and_its_share_keeps_none(self):
        rec = {"B01001_001": [1000, None], "B01001_003": [100, None], "B01001_027": [90, None]}
        out = sa.age_values(rec, ["acs_age0to4"])
        self.assertEqual(out["acs_age0to4"], (190, None), "a count made only of controlled cells has no margin: it is not exact")
        self.assertEqual(out["acs_age0to4_pct"], (19.0, None), "and its share has none either, never a zero")

    def test_the_new_age_shares_of_the_series_are_the_counts_over_the_total(self):
        out = sa.derive_pop(PopulationArithmetic().rec())
        self.assertAlmostEqual(out["acs_age_under3_pct"][0], 3.0)
        self.assertAlmostEqual(out["acs_age5to17_pct"][0], 300 / 1000 * 100, msg="5-17 is the 6 cells of 50 from 5 to 17")

    def test_age_groups_too_rough_below_the_municipio_are_not_published_there(self):
        for k in ("acs_age_under3_pct", "acs_age3to4_pct", "acs_age5to17_pct", "acs_age18to24_pct", "acs_age25to44_pct"):
            self.assertIn(k, sa.EXCLUDED)
            self.assertNotIn(k, sa.SELECTION["barrio"])
        for k in ("acs_age18to44_pct", "acs_age45to64_pct"):
            self.assertIn(k, sa.SELECTION["barrio"])
            self.assertIn(k, sa.SELECTION["tract"])
            self.assertNotIn(k, sa.SELECTION["block-group"])
        self.assertEqual(sa.AGE_SMALL, ["acs_under18", "acs_age18to44", "acs_age45to64", "acs_age65plus"])
        for k in sa.AGE_COUNTS:   # the counts are municipio only: below it each is flagged for more than half of the barrios (2026-10-18)
            self.assertIn(k, sa.POP_VARS)
            self.assertIn(k, sa.EXCLUDED)
            for level in ("barrio", "tract", "block-group"):
                self.assertNotIn(k, sa.SELECTION[level])

    def test_the_b09001_labels_are_committed_for_every_vintage(self):
        for y in sa.VINTAGES:
            self.assertTrue((sa.LABEL_FIXTURES / f"B09001_{y}.json").exists(), y)


@unittest.skipUnless((DATA / sa.AGE_FILE).exists(), "population_age.json is not built yet")
class PublishedAgeFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / sa.AGE_FILE).read_text(encoding="utf-8"))
        cls.pop = json.loads((DATA / sa.POP_FILE).read_text(encoding="utf-8"))
        cls.cw = sa.crosswalk()

    @staticmethod
    def V(block):
        return {v["key"]: v for v in block["vars"]}

    def test_the_areas_are_the_municipios_and_the_901_barrios_and_981_tracts_in_the_crosswalks_order(self):
        self.assertEqual(self.doc["geo"]["ids"], self.pop["geo"]["ids"])
        self.assertEqual(self.doc["geo"]["ids"][-1], "72")
        self.assertEqual(len(self.doc["levels"]["barrio"]["ids"]), 901)
        self.assertEqual(self.doc["levels"]["barrio"]["ids"], self.cw["barrio"])
        self.assertEqual(self.doc["levels"]["tract"]["ids"], self.cw["tract"])
        for lv, block, n in (("municipio", self.doc, 79), ("barrio", self.doc["levels"]["barrio"], 901), ("tract", self.doc["levels"]["tract"], 981)):
            for v in block["vars"]:
                self.assertEqual(sorted(v["years"]), [str(y) for y in sa.VINTAGES], v["key"])
                for y, arr in v["years"].items():
                    self.assertEqual(len(arr), n, f"{lv} {v['key']} {y}")
                    self.assertEqual(len(v["moe"][y]), n)
        self.assertEqual([v["key"] for v in self.doc["levels"]["barrio"]["vars"]], [k + s for k in sa.AGE_SMALL for s in ("", "_pct")])

    def test_shares_are_between_0_and_100_and_no_margin_is_zero(self):
        for lv, block in (("municipio", self.doc), ("barrio", self.doc["levels"]["barrio"]), ("tract", self.doc["levels"]["tract"])):
            for v in block["vars"]:
                for y, arr in v["years"].items():
                    for x, m in zip(arr, v["moe"][y]):
                        if x is None:
                            self.assertIsNone(m)
                            continue
                        self.assertTrue(m is None or m > 0, f"{lv} {v['key']}: a margin of zero reads as exact")
                        if v["key"].endswith("_pct"):
                            self.assertTrue(0 <= x <= 100, f"{lv} {v['key']} {y}: {x}")
                        else:
                            self.assertIsInstance(x, int)

    def test_the_age_bands_add_up_to_the_total_within_rounding(self):
        V, P = self.V(self.doc), {v["key"]: v for v in self.pop["vars"]}
        bands = [k for k, _ in sa.AGE_BANDS]
        for y in [str(w) for w in self.doc["windows"]]:
            for i, g in enumerate(self.doc["geo"]["ids"]):
                tot = P["acs_population"]["years"][y][i]
                self.assertEqual(sum(V[k]["years"][y][i] for k in bands), tot, f"{g} {y}: the five-year bands are not all people")
                self.assertAlmostEqual(sum(V[k + "_pct"]["years"][y][i] for k in bands), 100, delta=0.1, msg=f"{g} {y}")
                self.assertEqual(V["acs_age0to4"]["years"][y][i] + sum(V[k]["years"][y][i] for k in ("acs_age5to17", "acs_age18to24", "acs_age25to44", "acs_age45to64", "acs_age65plus")), tot)
                self.assertLessEqual(V["acs_age_under3"]["years"][y][i] + V["acs_age3to4"]["years"][y][i], V["acs_age0to4"]["years"][y][i], f"{g} {y}: children in households under 5 above all children under 5")
        for lv in ("barrio", "tract"):
            B = self.V(self.doc["levels"][lv])
            for y in [str(w) for w in self.doc["windows"]]:
                for i in range(len(self.doc["levels"][lv]["ids"])):
                    shares = [B[k + "_pct"]["years"][y][i] for k in sa.AGE_SMALL]
                    if None not in shares:
                        self.assertAlmostEqual(sum(shares), 100, delta=0.05, msg=f"{lv} {i} {y}")

    def test_the_shares_are_the_ones_the_map_shows(self):
        V, P = self.V(self.doc), {v["key"]: v for v in self.pop["vars"]}
        for k in ("acs_age_under3_pct", "acs_age3to4_pct", "acs_age5to17_pct", "acs_age18to24_pct", "acs_age25to44_pct", "acs_age45to64_pct", "acs_age18to44_pct", "acs_under18_pct", "acs_age65plus_pct"):
            self.assertEqual(V[k]["years"], P[k]["years"], k)
            self.assertEqual(V[k]["moe"], P[k]["moe"], k)
        bar = {v["key"]: v for v in json.loads((DATA / "acs_barrio.json").read_text(encoding="utf-8"))["vars"]}
        B = self.V(self.doc["levels"]["barrio"])
        for k in ("acs_under18_pct", "acs_age18to44_pct", "acs_age45to64_pct", "acs_age65plus_pct"):
            self.assertEqual(B[k]["years"], bar[k]["years"], k)


if __name__ == "__main__":
    unittest.main()
