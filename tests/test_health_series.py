"""Tests for health_series.py (HRSA health center sites and shortage-area designations, by municipality).

  python -m unittest discover -s tests -v

Invented rows check every rule without any download: which sites count, which designations are read, what stops the build, what a municipality with no designation gets (no
value, never a zero), and how overlaps are kept. The published file is checked too: its shape, its island rules, that it holds no name, address, telephone number, web address
or coordinate, that the cached HRSA rows give it again, and (for the 2026-10 snapshot) that it reproduces the totals HRSA itself published for Puerto Rico.
"""
import csv
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import health_series as hs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "site" / "data"
IDS = {"72001": 0, "72003": 1, "72005": 2}   # three invented municipalities

# The columns the build is allowed to keep, written out in full. A column that could hold a name, an address, a telephone number, a web address or a place (a coordinate) is never on this list;
# adding any column to FILES in health_series.py fails the test below until a person has read the new column's definition and added it here.
ALLOWED = {
    "sites": ["Site State Abbreviation", "Site Status Description", "Health Center Type", "Health Center Type Description", "Health Center Location Type Description",
              "State and County Federal Information Processing Standard Code", "Data Warehouse Record Create Date"],
    **{f"hpsa_{k}": ["HPSA ID", "HPSA Discipline Class", "HPSA Status", "Designation Type", "HPSA Score", "HPSA FTE", "HPSA Shortage", "HPSA Designation Population", "Provider Type",
                     "HPSA Population Type", "HPSA Designation Date", "HPSA Designation Last Update Date", "Primary State Abbreviation", "Common State Abbreviation", "Common State County FIPS Code",
                     "Data Warehouse Record Create Date"] for k in ("pc", "dh", "mh")},
}


def site(county, status="Active", kind="Service Delivery Site", location="Permanent", ftype="Federally Qualified Health Center (FQHC)"):
    return {"Site State Abbreviation": "PR", "Site Status Description": status, "Health Center Type": ftype, "Health Center Type Description": kind,
            "Health Center Location Type Description": location, hs.COUNTY: county, hs.CREATED: "10/06/2026"}


def row(county, hid, score="15", fte="1.0", short="2.5", dtype="HPSA Population", status="Designated", disc="Primary Care", pop_type="Low Income Population HPSA", provider="Not Applicable", pop="1000"):
    return {"HPSA ID": hid, "HPSA Discipline Class": disc, "HPSA Status": status, "Designation Type": dtype, "HPSA Score": score, "HPSA FTE": fte, "HPSA Shortage": short,
            "HPSA Designation Population": pop, "Provider Type": provider, "HPSA Population Type": pop_type, "HPSA Designation Date": "05/04/2018", "HPSA Designation Last Update Date": "01/02/2023",
            "Primary State Abbreviation": "PR", "Common State Abbreviation": "PR", hs.HPSA_COUNTY: county, hs.CREATED: "10/06/2026"}


class Sites(unittest.TestCase):
    def test_only_active_sites_that_deliver_care_count_and_vans_are_counted_apart(self):
        rows = [site("72001"), site("72001"), site("72001", location="Mobile Van"), site("72003", kind="Administrative/Service Delivery Site"),
                site("72003", kind="Administrative"), site("72005", status="Terminated"), site("72005", status="Pending Verification")]
        perm, van, skipped = hs.sites(rows, IDS)
        self.assertEqual(dict(perm), {"72001": 2, "72003": 1})
        self.assertEqual(dict(van), {"72001": 1})
        self.assertEqual(skipped["not an active site that delivers care"], 3, "administrative-only, terminated and pending sites are left out")

    def test_a_seasonal_or_unknown_site_is_left_out_and_said_so(self):
        _, _, skipped = hs.sites([site("72001", location="Seasonal"), site("72001", location="Unknown")], IDS)
        self.assertEqual(skipped["location type Seasonal"], 1)
        self.assertEqual(skipped["location type Unknown"], 1)

    def test_a_county_that_is_not_a_municipality_stops_the_build(self):
        with self.assertRaises(SystemExit):
            hs.sites([site("78010")], IDS)


class Designations(unittest.TestCase):
    def test_only_area_level_designations_count_and_a_municipality_without_one_has_none(self):
        rows = [row("72001", "A", score="20", fte="2", short="6"),
                row("72003", "B", dtype="Federally Qualified Health Center", score="12", fte="", short=""),   # a facility, designated by law: left out
                row("72003", "C", dtype="Correctional Facility", score="25", fte="0", short="1.5"),
                row("72005", "D", status="Withdrawn", score="22")]
        out, notes = hs.hpsa(rows, IDS, "Primary Care")
        self.assertEqual(out, {"72001": (20, 2.0, 6.0)})
        self.assertEqual((notes["area"], notes["facility"], notes["not_in_force"]), (1, 2, 1))
        self.assertEqual(notes["municipios_with_only_a_facility_designation"], 1, "72003 has only facility designations")
        self.assertEqual(notes["correctional"], {"designations": 1, "fte": 0.0, "shortage": 1.5, "population": 1000.0}, "kept apart so HRSA's own totals can be checked")

    def test_a_designation_proposed_for_withdrawal_still_counts_as_hrsa_counts_it(self):
        out, _ = hs.hpsa([row("72001", "A", status="Proposed For Withdrawal")], IDS, "Primary Care")
        self.assertIn("72001", out)

    def test_two_area_designations_in_one_municipality_keep_the_highest_score_and_the_largest_shortage(self):
        rows = [row("72001", "A", score="14", fte="1", short="2"), row("72001", "B", score="19", fte="3", short="7", dtype="High Needs Geographic HPSA")]
        out, notes = hs.hpsa(rows, IDS, "Primary Care")
        self.assertEqual(out["72001"], (19, 3.0, 7.0), "the groups overlap, so the shortages are not added")
        self.assertEqual(notes["overlaps"], 1)

    def test_what_stops_the_build(self):
        with self.assertRaises(SystemExit, msg="one designation in two rows covers two municipalities"):
            hs.hpsa([row("72001", "A"), row("72003", "A")], IDS, "Primary Care")
        with self.assertRaises(SystemExit, msg="a county that is not a municipality"):
            hs.hpsa([row("78010", "A")], IDS, "Primary Care")
        with self.assertRaises(SystemExit, msg="a designation without a shortage figure"):
            hs.hpsa([row("72001", "A", short="")], IDS, "Primary Care")
        with self.assertRaises(SystemExit, msg="a designation without a score"):
            hs.hpsa([row("72001", "A", score="")], IDS, "Primary Care")
        with self.assertRaises(SystemExit, msg="a row of another discipline in the file"):
            hs.hpsa([row("72001", "A", disc="Dental Health")], IDS, "Primary Care")

    def test_need_met_is_the_share_of_the_practitioners_needed_that_are_in_place(self):
        self.assertAlmostEqual(hs.met_pct(3.1456, 3.3944), 48.1, delta=0.1)
        self.assertEqual(hs.met_pct(0.0, 11.51), 0.0, "HRSA counts none: a real zero")
        self.assertIsNone(hs.met_pct(0.0, 0.0), "nothing needed and nothing in place: no share")
        self.assertIsNone(hs.met_pct(None, 2.0))

    def test_dates_in_both_of_the_formats_hrsa_uses(self):
        self.assertEqual(str(hs.day("10/06/2026")), "2026-10-06")
        self.assertEqual(str(hs.day("2026-10-06 01:21:58.100")), "2026-10-06")
        self.assertIsNone(hs.day(""))


class Build(unittest.TestCase):
    """The whole computation on invented rows, without a download: the three municipalities of IDS stand for the island."""

    def run_compute(self, floors=None, sites_rows=None, **replace):
        sites_rows = sites_rows if sites_rows is not None else [site("72001"), site("72001", location="Mobile Van"), site("72003")]
        pc = [row("72001", "A", score="20", fte="2", short="6"), row("72003", "B", score="10", fte="0", short="4")]
        dh = [row("72001", "C", score="26", fte="1", short="1", disc="Dental Health")]
        mh = [row("72003", "D", score="18", fte="0", short="2", disc="Mental Health", provider="Psychiatrist")]
        files = {"sites": sites_rows, "hpsa_pc": pc, "hpsa_dh": dh, "hpsa_mh": mh, **replace}
        names = ["Uno", "Dos", "Tres"]
        with mock.patch.object(hs, "pr_rows", side_effect=lambda key, refresh=False: files[key]), mock.patch.object(hs.hs, "municipalities", return_value=(names, list(IDS))):
            return hs.compute(order_file=None, floors=floors)

    def test_arrays_end_with_puerto_rico_and_a_municipality_without_a_designation_has_no_value(self):
        d = self.run_compute()
        v = {x["key"]: list(x["years"].values())[0] for x in d["vars"]}
        self.assertEqual(d["geo"]["ids"], ["72001", "72003", "72005", "72"])
        self.assertEqual(v["hc_sites"], [1, 1, 0, 2], "a true zero where HRSA lists none; the island is the sum")
        self.assertEqual(v["hc_vans"], [1, 0, 0, 1])
        self.assertEqual(v["hpsa_pc_short"], [6.0, 4.0, None, 10.0])
        self.assertEqual(v["hpsa_pc_met"], [25.0, 0.0, None, round(2 / 12 * 100, 3)], "the island is the summed practitioners in place over the summed need, not a mean of shares; three decimals, so a figure printed with one is the one the sums give")
        self.assertEqual(v["hpsa_pc_score"], [20, 10, None, None], "scores are not added or averaged")
        self.assertEqual(v["hpsa_dh_short"], [1.0, None, None, 1.0])
        self.assertEqual(v["hpsa_mh_met"], [None, 0.0, None, 0.0])
        self.assertEqual(d["as_of"], "2026-10-06")
        self.assertEqual(d["years"], [2026])

    def test_every_variable_has_the_fields_the_engine_and_the_dictionary_read(self):
        d = self.run_compute()
        self.assertEqual(len(d["vars"]), 11)
        for x in d["vars"]:
            for k in ("key", "group", "label", "unit", "d", "type", "sources", "ref", "definition", "family", "years"):
                self.assertIn(k, x, x["key"])
            self.assertEqual(x["family"], "health")
            self.assertTrue(all(s in d["sources"] for s in x["sources"]), x["key"])
            self.assertIs(x["counted"], False, f"{x['key']}: administrative counts, not estimates from a few cases: no 'fewer than 10 counted' flag")
        self.assertEqual({x["key"] for x in d["vars"] if x.get("noIsland")}, {"hpsa_pc_score", "hpsa_dh_score", "hpsa_mh_score"}, "only the scores have no island value")
        self.assertEqual({x["group"] for x in d["vars"]}, {"Health centers", "Primary care shortage areas", "Dental shortage areas", "Mental health shortage areas"})
        self.assertEqual({x["noValue"] for x in d["vars"] if "noValue" in x}, {"No area shortage designation"})
        self.assertEqual({x["key"] for x in d["vars"] if x.get("classes") == "jenks"}, {"hc_sites", "hc_vans", "hpsa_pc_met", "hpsa_mh_met", "hpsa_dh_score", "hpsa_mh_score"}, "the legends that quantiles leave with empty or repeated classes")
        self.assertEqual({x["label"] for x in d["vars"] if "full-time equivalents" in x["label"]}, {"Primary care physicians still needed, full-time equivalents (shortage areas)", "Dentists still needed, full-time equivalents (shortage areas)", "Psychiatrists still needed, full-time equivalents (shortage areas)"})


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j = json.loads((DATA / "health_series.json").read_text(encoding="utf-8"))
        cls.v = {x["key"]: list(x["years"].values())[0] for x in cls.j["vars"]}
        cls.econ = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))

    def test_the_places_are_those_of_the_economy_series_in_the_same_order(self):
        self.assertEqual(self.j["geo"], {"ids": self.econ["geo"]["ids"], "names": self.econ["geo"]["names"]})
        self.assertEqual(self.j["geo"]["ids"][-1], "72")
        self.assertTrue(all(len(a) == 79 for a in self.v.values()))

    def test_island_rules(self):
        for k in ("hc_sites", "hc_vans"):
            self.assertEqual(self.v[k][78], sum(self.v[k][:78]), k)
            self.assertTrue(all(isinstance(x, int) and x >= 0 for x in self.v[k]), f"{k}: a count, with a true zero where HRSA lists none")
        for d in ("pc", "dh", "mh"):
            s = self.v[f"hpsa_{d}_short"]
            self.assertAlmostEqual(s[78], sum(x for x in s[:78] if x is not None), delta=0.011, msg=d)
            self.assertIsNone(self.v[f"hpsa_{d}_score"][78], "a score has no island value")
            for i in range(78):   # a municipality has all three figures or none
                trio = [self.v[f"hpsa_{d}_{m}"][i] for m in ("short", "met", "score")]
                self.assertTrue(all(x is None for x in trio) or all(x is not None for x in trio) or (trio[0] is not None and trio[2] is not None and trio[1] is None), (d, i, trio))
            met = [x for x in self.v[f"hpsa_{d}_met"] if x is not None]
            self.assertTrue(met and all(0 <= x <= 100 for x in met), d)
            top = {disc[0]: disc[7] for disc in hs.DISCIPLINES}[d]   # HRSA scores primary care and mental health from 0 to 25 and dental from 0 to 26
            self.assertEqual(top, {"pc": 25, "dh": 26, "mh": 25}[d])
            sc = [x for x in self.v[f"hpsa_{d}_score"] if x is not None]
            self.assertTrue(all(0 <= x <= top for x in sc), d)
            self.assertTrue(all(abs(x * 1000 - round(x * 1000)) < 1e-6 for x in met), f"{d}: need met is stored with three decimals at most")

    def test_it_holds_no_name_address_telephone_web_address_or_coordinate(self):
        allowed = {"built", "as_of", "years", "geo", "vars", "sources", "notes"}
        self.assertEqual(set(self.j), allowed)
        for x in self.j["vars"]:
            self.assertEqual(set(x) - {"noIsland", "noValue", "noPerHU", "dPer", "counted", "classes", "tag"}, {"key", "group", "label", "unit", "d", "type", "sources", "ref", "definition", "family", "years"}, x["key"])
        text = json.dumps({"vars": self.j["vars"], "notes": self.j["notes"]}, ensure_ascii=False)
        self.assertIsNone(re.search(r"https?://|www\.", text), "a web address")
        self.assertIsNone(re.search(r"\b\d{3}[-. )]\s?\d{3}[-. ]\d{4}\b", text), "a telephone number")
        self.assertIsNone(re.search(r"[\w.]+@[\w.]+\.\w+", text), "an e-mail address")
        for s in self.j["sources"].values():
            self.assertEqual(set(s), {"name", "url", "license", "note"})

    def test_the_build_keeps_only_the_columns_on_the_allowed_list(self):
        """No cache needed: the list in health_series.py is the list written above, and none of its columns could hold a name, an address, a telephone number, a web address or a place."""
        self.assertEqual(set(hs.FILES), set(ALLOWED))
        banned = re.compile(r"(?i)name|address|phone|web|url|latitude|longitude|geocod|contact|zip|street|email|\bcity\b|\blat\b|\blon\b|\bx\b|\by\b|location (?!type)|coordinate")
        for key, spec in hs.FILES.items():
            self.assertEqual(spec["keep"], ALLOWED[key], f"{key}: a column was added or removed: read its definition in HRSA's data dictionary, then change ALLOWED")
            self.assertEqual([c for c in spec["keep"] if banned.search(c)], [], f"{key}: a column that could hold a name or a place")
        self.assertEqual((len(hs.FILES["sites"]["keep"]), len(hs.FILES["hpsa_pc"]["keep"])), (7, 16), "the dictionary and the sources say how many columns are kept: tests/test_health_dictionary.py")

    def test_the_cache_holds_only_those_columns(self):
        for key, spec in hs.FILES.items():
            p = hs.CACHE / f"{key}.pr.csv"
            if not p.exists():
                self.skipTest("the HRSA cache is not on this machine (python health_series.py makes it)")
            with p.open(encoding="utf-8", newline="") as f:
                self.assertEqual(next(csv.reader(f)), spec["keep"], key)

    def test_the_cached_rows_give_the_published_file_again(self):
        if not all((hs.CACHE / f"{k}.pr.csv").exists() for k in hs.FILES):
            self.skipTest("the HRSA cache is not on this machine")
        self.assertEqual(hs.build(check=True), 0)

    def test_it_reproduces_the_totals_hrsa_published_for_puerto_rico(self):
        """HRSA's Designated HPSA Quarterly Summary (as of 30 September 2026): practitioners needed, population of designated HPSAs and percent of need met for Puerto Rico.
        HRSA's totals include the correctional facility, which the municipal values leave out, so the check adds it (notes.hpsa.<discipline>.correctional)."""
        if self.j["as_of"] != "2026-10-06":
            self.skipTest("the figures HRSA published belong to the 2026-10 snapshot")
        official = {"pc": (138, 574059, 28.90), "dh": (297, 2292005, 48.02), "mh": (70, 1140925, 8.31)}
        for d, (needed, pop, met) in official.items():
            n = self.j["notes"]["hpsa"][d]
            c = n["correctional"]
            self.assertEqual(n["area_population"] + c["population"], pop, f"{d}: the population of designated areas agrees exactly")
            short, fte = n["shortage_total"] + c["shortage"], n["fte_total"] + c["fte"]
            self.assertLess(abs(short - needed) / needed, 0.011, f"{d}: practitioners needed within 1.1% of HRSA's {needed} (HRSA rounds each designation)")
            self.assertAlmostEqual(fte / (fte + short) * 100, met, delta=0.02, msg=f"{d}: percent of need met reproduces HRSA's {met}")

    def test_the_designations_counted_are_those_hrsa_counted(self):
        if self.j["as_of"] != "2026-10-06":
            self.skipTest("the figures HRSA published belong to the 2026-10 snapshot")
        for d, total in {"pc": 43, "dh": 100, "mh": 75}.items():
            n = self.j["notes"]["hpsa"][d]
            self.assertEqual(n["area"] + n["facility"], total, f"{d}: designations (HRSA counts {total} for Puerto Rico)")
            self.assertEqual(n["overlaps"], 0)


class Safety(unittest.TestCase):
    """The build stops, and writes nothing, instead of publishing a false "no site", "no van" and "no shortage area" for every municipality when HRSA renames a value or the files do not belong together.
    The checks run on rows made for the test (so they run on any machine) and, where the cache of HRSA rows is on the machine, on the real rows too."""

    def sources(self):
        names, fips = hs.hs.municipalities()
        ids = list(fips)

        def designations(prefix, n, disc, provider="Not Applicable"):
            return [row(f, f"{prefix}{i}", disc=disc, provider=provider) for i, f in enumerate(ids[:n])] + [row(ids[50], f"{prefix}w", status="Withdrawn", disc=disc, provider=provider),
                                                                                                          row(ids[51], f"{prefix}f", dtype="Federally Qualified Health Center", disc=disc, provider=provider)]
        made = {"sites": [site(f) for f in ids[:40] for _ in range(2)] + [site(f, location="Mobile Van") for f in ids[:8]],
                "hpsa_pc": designations("pc", 12, "Primary Care"), "hpsa_dh": designations("dh", 34, "Dental Health"), "hpsa_mh": designations("mh", 24, "Mental Health", "Psychiatrist")}
        out = [("rows made for the test", made)]
        if all((hs.CACHE / f"{k}.pr.csv").exists() for k in hs.FILES):
            out.append(("the cached rows", {k: [dict(r) for r in hs.pr_rows(k)] for k in hs.FILES}))
        return out

    @staticmethod
    def copy(files):
        return {k: [dict(r) for r in v] for k, v in files.items()}

    def run_with(self, files):
        with mock.patch.object(hs, "pr_rows", side_effect=lambda key, refresh=False, **kw: files[key]):
            return hs.compute(order_file=None)

    def stops(self, label, files, text):
        with self.assertRaises(SystemExit, msg=label) as cm:
            self.run_with(files)
        self.assertIn(text, str(cm.exception), label)

    def test_the_rows_pass_every_stop(self):
        for label, files in self.sources():
            self.assertEqual(len(self.run_with(files)["vars"]), 11, label)

    def test_a_renamed_status_of_a_site_stops_the_build(self):
        for label, files in self.sources():
            f = self.copy(files)
            for r in f["sites"]:
                r["Site Status Description"] = "Activo"
            self.stops(label, f, "permanent sites")

    def test_a_renamed_or_unknown_location_type_stops_the_build(self):
        for label, files in self.sources():
            for old, new in (("Permanent", "Fixed"), ("Mobile Van", "Mobile Clinic")):
                f = self.copy(files)
                for r in f["sites"]:
                    if r["Health Center Location Type Description"] == old:
                        r["Health Center Location Type Description"] = new
                self.stops(f"{label}: {old} renamed {new}", f, "location type the build does not know")

    def test_no_van_at_all_stops_the_build(self):
        for label, files in self.sources():
            f = self.copy(files)
            for r in f["sites"]:
                if r["Health Center Location Type Description"] == "Mobile Van":
                    r["Health Center Location Type Description"] = "Seasonal"   # a type the build knows: the vans are simply gone
            self.stops(label, f, "mobile vans")

    def test_a_renamed_status_of_a_designation_stops_the_build(self):
        for label, files in self.sources():
            for k in ("hpsa_pc", "hpsa_dh", "hpsa_mh"):
                f = self.copy(files)
                for r in f[k]:
                    if r["HPSA Status"] == "Designated":
                        r["HPSA Status"] = "Designado"
                self.stops(f"{label}: {k}", f, "area designations in force")

    def test_a_status_the_build_does_not_know_stops_the_build(self):
        for label, files in self.sources():
            f = self.copy(files)
            f["hpsa_dh"][0]["HPSA Status"] = "Pending"
            self.stops(label, f, "a status the build does not know")

    def test_files_made_on_different_days_stop_the_build(self):
        for label, files in self.sources():
            f = self.copy(files)
            for r in f["sites"]:
                r[hs.CREATED] = "09/28/2026"
            self.stops(label, f, "different days")
            g = self.copy(files)
            for r in g["hpsa_mh"]:
                r[hs.CREATED] = "10/07/2026"
            self.run_with(g)   # a day apart is a refresh that crossed midnight: allowed

    def test_the_invented_rows_are_not_held_to_the_floors_of_the_real_files(self):
        with self.assertRaises(SystemExit):
            Build("test_every_variable_has_the_fields_the_engine_and_the_dictionary_read").run_compute(floors=hs.FLOORS)

    def test_a_facility_id_is_blanked_and_an_area_id_is_kept(self):
        rows = [row("72001", "111"), row("72003", "222", dtype="Federally Qualified Health Center"), row("72005", "333", dtype="Correctional Facility", status="Withdrawn")]
        self.assertTrue(hs.scrub("hpsa_pc", rows))
        self.assertEqual([r["HPSA ID"] for r in rows], ["111", "", ""], "the ID of a facility names one facility")
        self.assertFalse(hs.scrub("hpsa_pc", rows), "nothing left to change")
        self.assertFalse(hs.scrub("sites", [site("72001")]))

    def test_the_cache_holds_no_facility_id(self):
        if not all((hs.CACHE / f"{k}.pr.csv").exists() for k in hs.FILES):
            self.skipTest("the HRSA cache is not on this machine (python health_series.py makes it)")
        files = {k: [dict(r) for r in hs.pr_rows(k)] for k in hs.FILES}
        for k in ("hpsa_pc", "hpsa_dh", "hpsa_mh"):
            self.assertEqual([r for r in files[k] if r["Designation Type"] not in hs.AREA_TYPES and r["HPSA ID"]], [], k)
            self.assertTrue(all(r["HPSA ID"] for r in files[k] if r["Designation Type"] in hs.AREA_TYPES), f"{k}: the ID of an area designation is kept")

    def test_check_never_downloads_and_writes_nothing(self):
        import tempfile
        label, files = self.sources()[0]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(hs, "CACHE", Path(d)), mock.patch.object(hs.requests, "get", side_effect=AssertionError("--check went to the network")):
            with self.assertRaises(SystemExit) as cm:
                hs.build(check=True)   # no cache: nothing to check, and nothing is downloaded or written
            self.assertIn("nothing to check", str(cm.exception))
            self.assertEqual(list(Path(d).iterdir()), [], "and no file is made")
            for key, spec in hs.FILES.items():   # a cache that still holds a facility ID is not rewritten by --check
                rows = [dict(r) for r in files[key]]
                if key.startswith("hpsa_"):
                    for r in rows:
                        r["HPSA ID"] = r["HPSA ID"] or "999"
                with (Path(d) / f"{key}.pr.csv").open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=spec["keep"], lineterminator="\n")
                    w.writeheader()
                    w.writerows(rows)
            before = {p.name: p.read_bytes() for p in Path(d).iterdir()}
            hs.build(check=True)
            self.assertEqual({p.name: p.read_bytes() for p in Path(d).iterdir()}, before, "the cache is as it was")


class Notes(unittest.TestCase):
    """The notes of the published file that the dictionary quotes, and HRSA's own totals worked out the way HRSA works them out."""

    @classmethod
    def setUpClass(cls):
        cls.j = json.loads((DATA / "health_series.json").read_text(encoding="utf-8"))

    def test_the_municipalities_with_no_value_add_up(self):
        for d in ("pc", "dh", "mh"):
            n = self.j["notes"]["hpsa"][d]
            self.assertEqual(n["municipios"] + n["municipios_without_an_area_designation"], 78, d)
            self.assertLessEqual(n["municipios_without_one_that_had_one_withdrawn"], n["municipios_without_an_area_designation"], d)
            self.assertLessEqual(n["municipios_with_only_a_correctional_facility"], n["municipios_with_only_a_facility_designation"], d)
            self.assertLessEqual(n["municipios_with_only_a_facility_designation"], n["municipios_without_an_area_designation"], d)

    def test_the_guide_quotes_the_notes(self):
        """The table of docs/health.md (the file against HRSA's quarterly summary) and the no-value counts of the guide are the file's own notes, worked out here."""
        guide = (ROOT / "docs" / "health.md").read_text(encoding="utf-8")
        needed = {"pc": 138, "dh": 297, "mh": 70}
        worst = 0
        for d, disc in (("pc", "Primary care"), ("dh", "Dental"), ("mh", "Mental health")):
            n = self.j["notes"]["hpsa"][d]
            c = n["correctional"]
            short, fte = n["shortage_total"] + c["shortage"], n["fte_total"] + c["fte"]
            worst = max(worst, abs(short - needed[d]) / needed[d])
            row = next(l for l in guide.splitlines() if l.startswith(f"| {disc}, this file |"))
            self.assertIn(f"{n['area']} area + {n['facility']} facility", row, d)
            self.assertIn(f"{n['area_population']:,.0f} + {c['population']:,.0f} = **{n['area_population'] + c['population']:,.0f}**", row, d)
            self.assertIn(f"{n['shortage_total']:.1f} + {c['shortage']:.1f} = {short:.1f}", row, d)
            self.assertIn(f"{fte / (fte + short) * 100:.2f}%", row, d)
        self.assertIn(f"each within {worst * 100:.1f}%", guide, "the worst gap against HRSA's totals, as the guide says it")
        no = {d: self.j["notes"]["hpsa"][d]["municipios_without_an_area_designation"] for d in ("pc", "dh", "mh")}
        self.assertIn(f"({no['pc']} municipalities for primary care, {no['dh']} for dental care, {no['mh']} for mental health)", guide)

    def test_hrsas_totals_are_the_sum_of_its_designations_each_rounded_to_a_whole_number(self):
        """HRSA's metadata does not define HPSA Shortage; that the rounded figures add up to the totals of its Quarterly Summary (as of 30 September 2026) is the evidence that the column is what the summary adds."""
        if self.j["as_of"] != "2026-10-06" or not all((hs.CACHE / f"hpsa_{k}.pr.csv").exists() for k in ("pc", "dh", "mh")):
            self.skipTest("the 2026-10 snapshot and its cache are needed")
        for d, want in (("pc", 138), ("dh", 297), ("mh", 70)):
            rows = [r for r in hs.pr_rows(f"hpsa_{d}") if r["HPSA Status"] in hs.DESIGNATED]
            self.assertEqual(sum(int(float(r["HPSA Shortage"] or 0) + 0.5) for r in rows), want, d)


if __name__ == "__main__":
    unittest.main()
