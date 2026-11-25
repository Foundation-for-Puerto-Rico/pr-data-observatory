"""The numbers that the health entries of the dictionary, the sources and docs/health.md quote are the published file's, not remembered ones.

The entries are written by hand from the file. Without this test a rebuild (HRSA refreshes its files daily) or a correction leaves a sentence that says "1 municipalities" or a wrong top four
(the review of pull request 5 found several). A sentence this test does not look for can still go stale: read the entry when a rebuild changes the file.

  python -m unittest tests.test_health_dictionary
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import health_series as hs  # noqa: E402

WORDS = {7: "seven", 16: "sixteen"}


def one(x, d=1):
    """A figure as the entries print it: d decimals."""
    return f"{x:.{d}f}"


class HealthDictionary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        j = json.loads((ROOT / "site" / "data" / "health_series.json").read_text(encoding="utf-8"))
        cls.names = j["geo"]["names"]
        cls.v = {x["key"]: list(x["years"].values())[0] for x in j["vars"]}
        cls.notes = j["notes"]
        cls.as_of = j["as_of"]   # the snapshot the sites and vans text names (2026-11 since the 2026-11-04 rebuild)
        cls.e = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "health.json").read_text(encoding="utf-8"))}
        cls.sources = json.loads((ROOT / "dictionary_src" / "sources.json").read_text(encoding="utf-8"))
        cls.guide = (ROOT / "docs" / "health.md").read_text(encoding="utf-8")
        cls.snapshot = j["as_of"] == "2026-10-06"

    def text(self, eid):
        return json.dumps(self.e[eid], ensure_ascii=False)

    def top(self, key, n):
        a = sorted(((x, self.names[i]) for i, x in enumerate(self.v[key][:78]) if x is not None), key=lambda t: (-t[0], t[1]))
        return a[:n]

    def test_no_value_counts(self):
        """'No value (N municipalities for X)' and 'N municipalities show no value' equal the municipalities with no value."""
        for d, disc in (("pc", "primary care"), ("dh", "dental"), ("mh", "mental health")):
            none = sum(1 for x in self.v[f"hpsa_{d}_short"][:78] if x is None)
            for kind in ("short", "met", "score"):
                t = self.text(f"health.hpsa_{d}_{kind}")
                m = re.search(r"No value \((\d+) municipalit(?:y|ies) for ([a-z ]+)\)", t)
                self.assertIsNotNone(m, f"{d} {kind}")
                self.assertEqual(int(m.group(1)), none, f"{d} {kind}")
                self.assertEqual(m.group(0).split(" municipalit")[1].startswith("y"), none == 1, f"{d} {kind}: singular for one municipality")
                self.assertNotRegex(t, r"(?<![\d,.])1 municipalities")
            m = re.search(r"(\d+) municipalit(?:y|ies) shows? no value", self.e[f"health.hpsa_{d}_short"]["how_to_read"])
            self.assertEqual(int(m.group(1)), none, d)

    def test_largest_gaps_and_the_smallest(self):
        for d in ("pc", "dh", "mh"):
            t = self.e[f"health.hpsa_{d}_short"]["how_to_read"]
            m = re.search(r"the largest gaps are in (.+?)\); the smallest is (\d+(?:\.\d+)?)", t)
            self.assertIsNotNone(m, d)
            quoted = re.findall(r"([^,()]+?) \(([\d.]+)", m.group(1) + ")")
            want = [(n, one(x)) for x, n in self.top(f"hpsa_{d}_short", 4)]
            self.assertEqual([(n.replace(" and ", "").strip(), x) for n, x in quoted], [(n, x) for n, x in want], d)
            smallest = min(x for x in self.v[f"hpsa_{d}_short"][:78] if x is not None)
            self.assertAlmostEqual(float(m.group(2)), smallest, places=2, msg=d)

    def test_sites_and_vans(self):
        sites, vans = self.v["hc_sites"], self.v["hc_vans"]
        t = self.e["health.hc_sites"]["how_to_read"]
        san = self.names.index("San Juan")
        self.assertIn(f"San Juan has {sites[san]} permanent sites", t)
        top = self.top("hc_sites", 4)
        self.assertIn(f"Bayamón {top[1][0]}", t)
        zero = [self.names[i] for i in range(78) if sites[i] == 0]
        self.assertIn(f"{len(zero)} municipalities have none", t)
        listed = ", ".join(zero[:-1]) + " and " + zero[-1]
        self.assertIn(f"({listed})", t)
        self.assertIn(f"HRSA lists {sum(vans[:78])} vans in {sum(1 for x in vans[:78] if x)} municipalities", self.e["health.hc_vans"]["how_to_read"])
        n = self.notes["sites"]
        m = self.text("health.hc_sites")
        self.assertIn(f"Of the {n['rows']} Puerto Rico rows in the {self.as_of[:7]} snapshot, {n['permanent']} are permanent sites that deliver care, {n['mobile_vans']} are mobile vans", m)
        self.assertEqual(sites[78], n["permanent"])

    def test_need_met(self):
        met = self.v["hpsa_pc_met"]
        zero = [self.names[i] for i in range(78) if met[i] == 0]
        t = self.e["health.hpsa_pc_met"]["how_to_read"]
        self.assertIn(f"{len(zero)} of the {sum(1 for x in met[:78] if x is not None)} designated municipalities are at 0% ({', '.join(zero[:-1])} and {zero[-1]})", t)
        island = self.v["hpsa_pc_met"][78]
        self.assertIn(f"it reads {one(island)}% where HRSA's figure is 28.90%", self.e["health.hpsa_pc_met"]["definition"])
        want = "(" + ", ".join(f"{one(self.v[f'hpsa_{d}_met'][78])}%" for d in ("pc", "dh")) + f" and {one(self.v['hpsa_mh_met'][78])}% of need met)"
        self.assertTrue(want in self.guide, f"docs/health.md should say {want}")
        sj = self.names.index("San Juan")
        short = self.v["hpsa_pc_short"]
        cav = " ".join(self.e["health.hpsa_pc_short"]["caveats"])
        self.assertEqual(met[sj], 0)
        self.assertIn(f"its {one(short[sj])} practitioners still needed are {round(short[sj] / short[78] * 100)}% of the island's {one(short[78])}", cav)

    def test_columns_kept_and_score_ranges(self):
        for key, n in (("sites", len(hs.FILES["sites"]["keep"])), ("hpsa_pc", len(hs.FILES["hpsa_pc"]["keep"]))):
            self.assertIn(n, WORDS, key)
        self.assertIn(f"{WORDS[len(hs.FILES['sites']['keep'])]} of its columns", self.e["health.hc_sites"]["method"])
        for eid in ("health.hpsa_pc_short", "health.hpsa_dh_short", "health.hpsa_mh_short", "health.shortage_method"):
            self.assertIn(f"{WORDS[len(hs.FILES['hpsa_pc']['keep'])]} columns", self.e[eid]["method"], eid)
        self.assertIn(f"{WORDS[len(hs.FILES['hpsa_pc']['keep'])]} columns", self.sources["hrsa_hpsa"]["access"])
        for d, disc in (("pc", "primary care"), ("dh", "dental"), ("mh", "mental health")):
            top = {x[0]: x[7] for x in hs.DISCIPLINES}[d]
            self.assertIn(f"HRSA scores {disc} designations from 0 to {top}", self.e[f"health.hpsa_{d}_score"]["definition"])
            high = max(x for x in self.v[f"hpsa_{d}_score"][:78] if x is not None)
            self.assertLessEqual(high, top)

    def test_the_limits_the_formula_implies(self):
        """HRSA's shortage for a designation is worked out with a limit of people for each practitioner. The entries say which: 3,000, 4,000 and 15,000 for a low-income population group (the rows
        of the cache give population / (FTE + shortage) for every designation)."""
        import csv
        stated = {"pc": "3,000", "dh": "4,000", "mh": "15,000"}
        for d, limit in {"pc": 3000, "dh": 4000, "mh": 15000}.items():
            p = hs.CACHE / f"hpsa_{d}.pr.csv"
            if not p.exists():
                self.skipTest("the HRSA cache is not on this machine")
            with p.open(encoding="utf-8", newline="") as f:
                rows = [r for r in csv.DictReader(f) if r["HPSA Status"] in hs.DESIGNATED and r["Designation Type"] in hs.AREA_TYPES and float(r["HPSA FTE"]) + float(r["HPSA Shortage"]) > 0]
            for r in rows:
                implied = float(r["HPSA Designation Population"]) / (float(r["HPSA FTE"]) + float(r["HPSA Shortage"]))
                self.assertAlmostEqual(implied / limit, 1, delta=0.02, msg=f"{d}: a designation is worked out with another limit than {limit}")
            self.assertIn(stated[d], self.text("health.shortage_method") + self.text(f"health.hpsa_{d}_short"))
        self.assertIn("15,000", self.e["health.hpsa_mh_short"]["definition"])
        self.assertNotIn("20,000 for a low-income population group or an area of unusually high need.", self.e["health.hpsa_mh_short"]["definition"])

    def test_the_sources_say_what_the_pages_say(self):
        for k in ("hrsa_sites", "hrsa_hpsa"):
            self.assertNotIn("403", json.dumps(self.sources[k]), "a sentence about a page that refused a request is not a license statement")
            self.assertIn("no usage limitations", self.sources[k]["licence"])
        self.assertIn("CC0", self.sources["hrsa_sites"]["licence"])
        self.assertFalse("HTTP 403" in self.guide, "docs/health.md still has the sentence about a page that refused a request")


class HealthDictionaryRound2(unittest.TestCase):
    """What the second review found: figures rounded twice, lists that were not checked, the license, the names and the plain wording."""

    @classmethod
    def setUpClass(cls):
        HealthDictionary.setUpClass.__func__(cls)
        cls.glossary = {g["term"]: g for g in json.loads((ROOT / "dictionary_src" / "glossary.json").read_text(encoding="utf-8"))}
        cls.j = json.loads((ROOT / "site" / "data" / "health_series.json").read_text(encoding="utf-8"))
        cls.es = json.loads((ROOT / "i18n_src" / "es" / "labels_health.json").read_text(encoding="utf-8"))
        cls.top = HealthDictionary.top

    def listed(self, names, n=6):
        """How the entries write a list of municipalities: all of them up to six, else the first four and 'and others'."""
        return ", ".join(names[:-1]) + " and " + names[-1] if len(names) <= n else ", ".join(names[:3]) + " and " + names[3] + " and others"

    def test_need_met_closest_three_and_the_zeros_are_the_files(self):
        for d in ("pc", "dh", "mh"):
            col = self.v[f"hpsa_{d}_met"]
            t = self.e[f"health.hpsa_{d}_met"]["how_to_read"]
            best = self.top(f"hpsa_{d}_met", 3)
            want = ", ".join(f"{n} ({one(x)}%)" for x, n in best[:2]) + f" and {best[2][1]} ({one(best[2][0])}%)"
            self.assertIn(want, t, f"{d}: the three closest to ending their designation, each rounded once from the stored value")
            zero = [self.names[i] for i in range(78) if col[i] == 0]
            designated = sum(1 for x in col[:78] if x is not None)
            self.assertIn(f"{len(zero)} of the {designated} designated municipalities are at 0% ({self.listed(zero)})", t, d)

    def test_score_ranges_and_the_highest(self):
        for d, disc in (("pc", "primary care"), ("dh", "dental"), ("mh", "mental health")):
            col = self.v[f"hpsa_{d}_score"]
            vals = [x for x in col[:78] if x is not None]
            hi = max(vals)
            names = [self.names[i] for i in range(78) if col[i] == hi]
            who = (", ".join(names[:2]) + " and " + names[2] if len(names) >= 3 else " and ".join(names)) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
            self.assertIn(f"the {disc} scores of the {len(vals)} designated municipalities run from {min(vals)} to {hi}; {who} {'have' if len(names) > 1 else 'has'} the highest ({hi})", self.e[f"health.hpsa_{d}_score"]["how_to_read"], d)

    def test_the_years_and_the_totals_quoted(self):
        for d, disc in (("pc", "primary care"), ("dh", "dental"), ("mh", "mental health")):
            n = self.notes["hpsa"][d]
            lo, hi = n["designated_years"]
            lu = n["last_updated_years"]
            want = f"were set between {lo} and {hi} and last updated " + (f"in {lu[0]}" if lu[0] == lu[1] else f"between {lu[0]} and {lu[1]}")
            self.assertIn(want, " ".join(self.e[f"health.hpsa_{d}_short"]["caveats"]), d)
            c = n["correctional"]
            self.assertIn(f"the sum of the municipal values is {round(n['shortage_total'], 1)} and, with the correctional facility designation that HRSA includes, {round(n['shortage_total'] + c['shortage'], 1)}", self.e[f"health.hpsa_{d}_short"]["method"], d)

    def test_no_value_says_why_and_the_facility_only_municipalities_are_counted(self):
        for d, who in (("pc", "doctors"), ("dh", "dentists"), ("mh", "psychiatrists or mental health care")):
            n = self.notes["hpsa"][d]
            no, wd = n["municipios_without_an_area_designation"], n["municipios_without_one_that_had_one_withdrawn"]
            self.assertEqual(no, 78 - n["municipios"], d)
            for kind in ("short", "met", "score"):
                t = " ".join(self.e[f"health.hpsa_{d}_{kind}"]["caveats"])
                self.assertIn(f"not proof that the municipality has enough {who}", t, f"{d} {kind}: no value is not proof that there are enough practitioners")
                self.assertIn((f"for {wd} of the {no}" if wd < no else "for all " + str(no)) if d != "dh" else "HRSA withdrew the area designation it once had", t, f"{d} {kind}")
                fo = n["municipios_with_only_a_facility_designation"]
                if fo:
                    c = n["municipios_with_only_a_correctional_facility"]
                    self.assertIn(f"{fo} have only a facility designation (a health center or, in {c}, a correctional facility)", t, f"{d} {kind}")
            island = " ".join(self.e[f"health.hpsa_{d}_short"]["caveats"])
            self.assertIn(f"including those of {'the ' + str(no) + ' municipalities' if no > 1 else 'the 1 municipality'} with no designation", island, d)

    def test_the_mental_health_ratio_and_the_goal_are_what_the_cached_rows_give(self):
        p = hs.CACHE / "hpsa_mh.pr.csv"
        if not p.exists():
            self.skipTest("the HRSA cache is not on this machine")
        rows = [r for r in hs.pr_rows("hpsa_mh") if r["HPSA Status"] in hs.DESIGNATED and r["Designation Type"] in hs.AREA_TYPES]
        pop = lambda r: float(r["HPSA Designation Population"])
        ratios = [pop(r) / (float(r["HPSA FTE"]) + float(r["HPSA Shortage"])) for r in rows if float(r["HPSA FTE"]) + float(r["HPSA Shortage"]) > 0]
        need20 = sum(max(0.0, pop(r) / 20000 - float(r["HPSA FTE"])) for r in rows)
        total = sum(float(r["HPSA Shortage"]) for r in rows)
        d = self.e["health.hpsa_mh_short"]["definition"]
        self.assertIn(f"between {round(min(ratios)):,} and {round(max(ratios)):,} in every one", d)
        self.assertIn(f"the 52 designations would need about {round(need20, 1)} psychiatrists, not {round(total, 1)}", d)
        self.assertIn("goal of 20,000 to 1 for all 52 designations", d)
        self.assertIn("inferred from the figures", d)
        for k, n in (("pc", 3000), ("dh", 4000)):
            self.assertIn(f"goal of {n:,} to 1", self.e[f"health.hpsa_{k}_short"]["definition"])
        self.assertIn("20,000 to 1 for all 52 mental health ones", self.guide)

    def test_the_cache_file_sizes_in_the_guide(self):
        sizes = [(hs.CACHE / f"{k}.pr.csv").stat().st_size for k in hs.FILES if (hs.CACHE / f"{k}.pr.csv").exists()]
        if len(sizes) < len(hs.FILES):
            self.skipTest("the HRSA cache is not on this machine")
        self.assertIn(f"{round(min(sizes) / 1000)} to {round(max(sizes) / 1000)} KB each", self.guide)

    def test_the_names_the_plain_sentences_and_the_glossary(self):
        for eid, e in self.e.items():
            self.assertIn("Health Resources and Services Administration (HRSA)", e["plain"], f"{eid}: HRSA is spelled out where a reader first meets it")
            self.assertLessEqual(max(len(s.split()) for s in re.split(r"(?<=[.!?]) ", e["plain"])), 40, f"{eid}: a plain sentence of more than 40 words")
        labels = {v["key"]: v["label"] for v in self.j["vars"]}
        for d in ("pc", "dh", "mh"):
            self.assertEqual(self.e[f"health.hpsa_{d}_met"]["name"], labels[f"hpsa_{d}_met"], "the entry carries the name of the dataset")
            self.assertIn("(% of the need)", labels[f"hpsa_{d}_met"])
            self.assertIn("not the share of people who get care", " ".join(self.e[f"health.hpsa_{d}_met"]["caveats"]))
        self.assertNotIn("40 hours", json.dumps(self.glossary["FTE"]) + json.dumps(self.e, ensure_ascii=False), "HRSA's FTE is not simply 40 hours")
        self.assertIn("four of its public data files", self.glossary["HRSA"]["plain"])
        self.assertIn("NHSC", self.glossary)
        dom ={d["id"]: d for d in json.loads((ROOT / "dictionary_src" / "domains.json").read_text(encoding="utf-8"))["domains"]}
        self.assertNotIn("look-alike", json.dumps(dom["health"]["headline"], ensure_ascii=False).lower(), "the headline names no term the reader does not know")

    def test_every_label_and_group_has_its_spanish(self):
        eco = json.loads((ROOT / "i18n_src" / "es" / "economy.json").read_text(encoding="utf-8"))
        for v in self.j["vars"]:
            self.assertIn(v["label"], self.es, v["key"])
            self.assertIn("Health care · " + v["group"], self.es, v["key"])
            if v.get("noValue"):
                self.assertIn(v["noValue"], self.es)
            if v.get("tag"):
                self.assertIn(v["tag"], eco, "the word for the kind of figure")
        self.assertEqual({self.es[k].split(" · ")[0] for k in self.es if k.startswith("Health care · ")}, {"Cuidado de la salud"}, "one Spanish term for health care, the one the jobs series uses")

    def test_both_sources_and_the_dataset_carry_the_licence_doubt(self):
        ds = json.loads((ROOT / "dictionary_src" / "datasets.json").read_text(encoding="utf-8"))["datasets"]
        rec = next(x for x in ds if x["id"] == "health_series")
        self.assertEqual([r["type"] for r in rec["review"]], ["licence"], "contract.py --reviews shows decision 38")
        self.assertEqual(rec["review"][0]["status"], "open")
        self.assertEqual(rec["review"][0]["fields"], [v["key"] for v in self.j["vars"]])
        for k in ("hrsa_sites", "hrsa_hpsa"):
            s = self.sources[k]
            self.assertEqual(s["verified"]["status"], "link-works-licence-unclear", k)
            self.assertEqual(s["licence_class"], "open", k)
            self.assertIn("Treated as open", s["licence"], k)
            self.assertIn("Open Database License 1.0", s["terms_note"], k)
            self.assertIn("downloadable data files", s["terms_note"], f"{k}: the Data Warehouse record says the portal offers the files")
        self.assertIn("Excel", self.sources["hrsa_sites"]["terms_note"], "the sites record lists the Excel file; the build reads the CSV")
        for k, text in self.j["sources"].items():
            self.assertIn("Treated as open", text["license"], f"the dataset window says {k} is treated as open")
        self.assertIn("contradicts itself", self.sources["hrsa_hpsa"]["terms_note"])
        self.assertIn("available under certain use restrictions", self.sources["hrsa_hpsa"]["terms_note"])

    def test_the_licence_evidence(self):
        s = self.sources["hrsa_hpsa"]
        self.assertIn("CC0", s["licence"])
        self.assertEqual(s["licence_class"], "open")
        self.assertIn("catalog.data.gov/dataset/shortage-designation-management-system-sdms", s["licence_url"])
        self.assertEqual(s["verified"]["status"], "link-works-licence-unclear", "until HRSA confirms the terms (HANDOFF decision 38)")
        for word in ("Shortage Designation Management System", "restricted public", "share-alike", "Usage limitations: None", "Open Database License 1.0"):
            self.assertIn(word, s["terms_note"], word)
        self.assertIn("Four files", self.guide)
        self.assertNotIn("Three files, no key", self.guide)
        self.assertNotIn("HRSA states no formal license", self.guide + json.dumps(self.sources))
        self.assertIn("share-alike", self.guide)


if __name__ == "__main__":
    unittest.main()
