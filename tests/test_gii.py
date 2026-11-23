"""The Global Innovation Index area (gii.py, docs/analysis/gii-2021/, site/data/gii_profile.json, site/gii.html): the original stays as printed, the
updates never carry a rank, the GII 2026 comparison is computed as documented, and the page keeps its labels."""
import io
import json
import os
import re
import unittest
import zipfile
from pathlib import Path

import gii

ROOT = Path(__file__).resolve().parent.parent
ORIG = json.loads((ROOT / "docs" / "analysis" / "gii-2021" / "gii_original.json").read_text(encoding="utf-8"))
PUB = json.loads((ROOT / "site" / "data" / "gii_profile.json").read_text(encoding="utf-8"))
CHG = json.loads((ROOT / "site" / "data" / "gii_changes.json").read_text(encoding="utf-8"))
CW = json.loads((ROOT / "docs" / "analysis" / "gii-2021" / "gii_crosswalk.json").read_text(encoding="utf-8"))
BY = {r["code"]: r for r in ORIG["indicators"]}
PUB_BY = {r["code"]: r for r in PUB["indicators"]}

# Read off the printed profile (PR+Country+Profile.pdf, 2021-09-26): value as printed and rank
PRINTED = {"1.1.1": ("1.4", 29), "1.1.2": ("-0.2", 80), "1.2.3": ("8.0", 3), "1.3.2": ("83.3", 10), "2.1.4": ("397.0", 69), "2.1.5": ("17.2", 90),
           "2.2.1": ("92.1", 4), "2.2.2": ("17.7", 81), "3.1.1": ("5.6", 66), "3.2.1": ("4,920.0", 43), "3.2.3": ("14.3", 121), "4.3.1": ("1.6", 19),
           "4.3.3": ("126.9", 76), "5.3.3": ("0.01", 126), "5.3.5": ("32.5", 40), "6.1.3": ("0.8", 28), "6.2.1": ("-2.0", 126), "6.2.5": ("91.2", 1),
           "6.3.2": ("54.9", 1), "7.1.2": ("0.6", 80), "7.2.1": ("0.0", 92), "7.2.2": ("2.6", 62), "7.2.5": ("0.5", 60)}
STAR = {"1.1.1", "1.2.3", "2.1.5", "4.3.1"}
HOURGLASS = {"2.1.1", "2.1.2", "2.1.3", "2.1.4", "2.2.1", "2.3.1", "2.3.2", "4.3.2", "5.1.3", "5.1.4", "5.2.1", "5.2.2", "7.1.4", "7.2.2"}


class Original(unittest.TestCase):
    def test_the_profile_is_whole(self):
        codes = [r["code"] for r in ORIG["indicators"]]
        self.assertEqual(len(codes), 80)
        self.assertEqual(len(set(codes)), 80)
        self.assertEqual(sum(1 for r in ORIG["indicators"] if r["value"] is not None), 56)
        self.assertEqual(sum(1 for r in ORIG["indicators"] if r["rank"] is not None), 56)
        self.assertEqual([p["code"] for p in ORIG["pillars"]], list("1234567"))
        self.assertEqual(sum(len(p["subs"]) for p in ORIG["pillars"]), 21)

    def test_values_ranks_and_marks_as_printed(self):
        for code, (shown, rank) in PRINTED.items():
            self.assertEqual((BY[code]["shown"], BY[code]["rank"], BY[code]["rank_printed_of"]), (shown, rank, 132), code)
        self.assertEqual({c for c, r in BY.items() if r["star"]}, STAR)
        self.assertEqual({c for c, r in BY.items() if r["hourglass"]}, HOURGLASS)

    def test_corrections_are_notes_not_edits(self):
        for code in ("2.2.1", "2.2.2", "3.1.1", "5.3.5", "6.3.2", "7.2.2", "1.2.3", "2.1.5", "4.3.1", "6.2.1", "6.1.3"):
            self.assertTrue(BY[code]["note"] and BY[code]["note"]["en"] and BY[code]["note"]["es"], code)
        self.assertIn("84th of the 126", BY["2.1.5"]["note"]["en"])
        self.assertIn("1st of the 130", BY["1.2.3"]["note"]["en"])
        self.assertIn("18th of the 131", BY["4.3.1"]["note"]["en"])
        self.assertIn("114th of the 120", BY["6.2.1"]["note"]["en"])
        self.assertIn("-2.012) would rank 115th", BY["6.2.1"]["note"]["en"])
        self.assertIn("ICTs", BY["7.1.4"]["note"]["en"])
        self.assertEqual(BY["2.2.2"]["year"], "2016")   # the UIS year of the printed 17.7

    def test_every_indicator_is_explained_in_both_languages(self):
        for r in ORIG["indicators"]:
            for k in ("name", "definition", "method", "source_printed"):
                self.assertTrue(r[k]["en"] and r[k]["es"], (r["code"], k))
            # an update or the reason there is none (3.2.1 and 5.1.1 were updated after the original's reasons were written on 2026-10-23)
            self.assertTrue(r["code"] in gii.UPDATES or r["not_updated"], r["code"])

    def test_proprietary_values_are_not_updated(self):
        for code in ("1.1.1", "6.1.4", "7.1.2"):
            self.assertTrue(BY[code]["proprietary"])
            self.assertNotIn(code, gii.UPDATES)


class Published(unittest.TestCase):
    def test_the_original_reaches_the_file_unchanged(self):
        for r in ORIG["indicators"]:
            p = PUB_BY[r["code"]]
            for k in ("value", "shown", "rank", "rank_printed_of", "star", "hourglass", "year"):
                self.assertEqual(p[k], r[k], (r["code"], k))

    def test_updated_values_have_a_year_a_source_and_no_rank(self):
        upd = [r for r in PUB["indicators"] if "upd_value" in r]
        self.assertEqual(len(upd), PUB["about"]["updated_count"])
        self.assertGreaterEqual(len(upd), 12)
        for r in upd:
            self.assertTrue(r["upd_year"] and r["upd_source"] and r["upd_series"], r["code"])
            self.assertIn(r["upd_kind"], ("official", "fpr"))
            self.assertFalse(any(k.startswith("upd_") and "rank" in k for k in r), r["code"])
        self.assertEqual({r["code"] for r in upd if r["upd_kind"] == "fpr"}, {"3.2.1", "4.3.1", "5.1.1", "6.2.1"})

    def test_an_update_or_a_true_reason_in_both_languages(self):
        for code, t in PUB["texts"].items():
            self.assertEqual("upd_value" in PUB_BY[code], "not_updated" not in t, code)
            if "not_updated" in t:
                self.assertTrue(t["not_updated"]["en"] and t["not_updated"]["es"], code)
                # the observatory reads only keyless sources: no reason may still say a key is the only thing missing where a keyless file exists
                self.assertNotIn("needs a key the observatory does not hold", t["not_updated"]["en"], code)
                self.assertNotIn("too few series a day without a key", t["not_updated"]["en"], code)
        self.assertIn("no keyless open source", PUB["texts"]["6.1.1"]["not_updated"]["en"])
        self.assertIn("granted patents rather than applications", PUB["texts"]["6.1.1"]["not_updated"]["en"])
        self.assertNotIn("upd_value", PUB_BY["6.1.1"])

    def test_the_keyless_updates(self):
        e = PUB_BY["3.2.1"]
        self.assertEqual((e["upd_source"], e["upd_kind"]), ("eia_intl+census_pep", "fpr"))
        self.assertGreaterEqual(int(e["upd_year"]), 2024)
        self.assertTrue(4000 < e["upd_value"] < 9000, e["upd_value"])   # 4,920.0 in 2017 (the year of Hurricane María); about 6,000 before and after
        self.assertIn(e["chg"], ("better", "worse", "same"))   # same source family and definition as the original
        k = PUB_BY["5.1.1"]
        self.assertEqual((k["upd_source"], k["upd_kind"], k["chg"], k["chg_why"]), ("bls_oews", "fpr", "na", "method"))
        self.assertTrue(20 < k["upd_value"] < 40, k["upd_value"])   # 32.0 printed for 2019-2020
        for code in ("3.2.1", "5.1.1"):
            self.assertNotIn("c26_pos", PUB_BY[code])
            self.assertIn(code, gii.NO_POSITION)
        for s in ("eia_intl", "census_pep", "bls_oews"):
            self.assertIn(s, PUB["sources"])
        lc = next(x for x in CHG["new_2026"] if x["c26"] == "IN.3.3.2")
        self.assertEqual((lc["pr"], lc["pr_est"]["source"]), ("fpr", "eia_intl"))
        self.assertTrue(0 < lc["pr_est"]["value"] < 100)
        self.assertIn("FPR estimate", lc["pr_note"]["en"])
        self.assertTrue(lc["pr_note"]["es"])

    def test_no_overall_score_and_no_other_economy(self):
        text = json.dumps(PUB, ensure_ascii=False) + json.dumps(CHG, ensure_ascii=False)
        self.assertNotRegex(text, r'"(score|overall|gii_rank|subindex)[a-z_]*":')
        for name in ("United States\"", "Dominican Republic", "Costa Rica", "Switzerland", "\"USA\""):
            self.assertNotIn(name, text)
        self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]")   # no email address

    def test_gii2026_comparison_only_where_sources_match(self):
        cmp_ = {r["code"] for r in PUB["indicators"] if "c26_pos" in r}
        self.assertEqual(cmp_, set(gii.COMPARE))
        self.assertEqual(len(cmp_), PUB["about"]["compared_count"])
        for r in PUB["indicators"]:
            if "c26_pos" in r:
                self.assertTrue(1 <= r["c26_pos"] <= r["c26_of"] == r["c26_n"] + 1, r["code"])
                self.assertLessEqual(r["c26_q1"], r["c26_median"])
                self.assertLessEqual(r["c26_median"], r["c26_q3"])
        self.assertEqual(PUB["about"]["gii2026"]["sha256_wipo"], gii.G26_SHA256_WIPO)
        self.assertRegex(PUB["about"]["gii2026"]["sha256_file"], r"^[0-9a-f]{64}$")

    def test_sources_of_the_file_are_in_its_contract(self):
        ds = json.loads((ROOT / "dictionary_src" / "datasets.json").read_text(encoding="utf-8"))
        rec = next(r for r in ds["datasets"] if r["file"] == "gii_profile.json")
        for k in PUB["sources"]:
            self.assertIn(k, rec["sources"])

    @unittest.skipUnless((gii.CACHE / "wb_PRI_GOV_WGI_GE.EST.json").exists(), "needs the cache of gii.py (cache/gii/)")
    def test_the_file_is_what_the_cache_gives(self):
        self.assertEqual(gii.build(check=True), 0)


class Position(unittest.TestCase):
    def test_position_counts_strictly_better_economies(self):
        self.assertEqual(gii.position(5, [1, 2, 5, 7, 9], False), (3, 6))   # 7 and 9 are better; ties share the better place
        self.assertEqual(gii.position(5, [1, 2, 5, 7, 9], True), (3, 6))    # lower is better: 1 and 2
        self.assertEqual(gii.position(10, [1, 2], False), (1, 3))
        self.assertEqual(gii.position(0, [1, 2], False), (3, 3))

    def test_compare_uses_the_year_of_the_gii_or_a_three_year_average(self):
        g26 = {"indicators": {"IN.1.1.2": {"year": 2024, "values": [-1.0, 0.0, 1.0, 2.0]}, "IN.3.2.4": {"year": 2025, "values": [10.0, 20.0, 30.0]}}}
        c = gii.compare("1.1.2", {"value": 0.5, "year": "2025"}, {"2024": 0.4, "2025": 0.5}, g26)
        self.assertEqual((c["c26_pr_value"], c["c26_pr_year"], c["c26_pos"], c["c26_of"]), (0.4, "2024", 3, 5))
        c = gii.compare("3.2.3", {"value": 15.0, "year": "2025"}, {"2023": 12.0, "2024": 15.0, "2025": 18.0}, g26)
        self.assertEqual((c["c26_pr_value"], c["c26_pr_year"], c["c26_pos"]), (15.0, "2023-2025", 3))
        g26["indicators"]["IN.2.1.5"] = {"year": 2024, "values": [5.0, 10.0, 20.0, 30.0]}
        self.assertIsNone(gii.compare("2.1.5", {"value": 17.0, "year": "2024"}, {"2024": 17.0}, g26))   # UIS's 2024 teacher series changed: no position
        self.assertIn("2.1.5", gii.NO_POSITION)

    def test_no_position_beyond_the_winsorized_values(self):
        g26 = {"indicators": {"IN.2.2.3": {"year": 2024, "values": [0.0, 1.0, 2.0, 50.0], "linear": False, "free_lo": 0.5, "free_hi": 2.0}}}
        self.assertIsNone(gii.compare("2.2.3", {"value": 30.0, "year": "2024"}, {}, g26))
        self.assertEqual(gii.compare("2.2.3", {"value": 1.5, "year": "2024"}, {}, g26)["c26_pos"], 3)   # 2 and 50 are higher


class Change(unittest.TestCase):
    G = {"indicators": {"X": {"values": [0.0, 10.0, 20.0, 30.0, 40.0]}, "L": {"values": [1.0, 10.0, 100.0, 1000.0, 10000.0], "log": True}}}

    def test_better_worse_and_no_meaningful_change_follow_the_direction(self):
        # IQR of X (inclusive quartiles) = 30 - 10 = 20, so the threshold is 5% x 20 = 1.0
        def r(v, u, d=1, code="9.9.9"):
            return {"code": code, "value": v, "upd_value": u, "dir": d}
        self.assertEqual(gii.change(r(10, 12), self.G, "X")["chg"], "better")
        self.assertEqual(gii.change(r(10, 12, -1), self.G, "X")["chg"], "worse")   # higher is worse
        self.assertEqual(gii.change(r(10, 8, -1), self.G, "X")["chg"], "better")
        self.assertEqual(gii.change(r(10, 10.9), self.G, "X")["chg"], "same")
        self.assertEqual(gii.change(r(10, 12), self.G, "X")["chg_thr"], 1.0)
        self.assertEqual(gii.change(r(None, 12), self.G, "X"), {"chg": "na", "chg_why": "no_2021"})
        self.assertEqual(gii.change(r(10, 12, 1, "6.2.2"), self.G, "X"), {"chg": "na", "chg_why": "definition"})
        self.assertEqual(gii.change(r(-2.0, 0.0, 1, "6.2.1"), self.G, "X"), {"chg": "na", "chg_why": "definition"})
        self.assertEqual(gii.change(r(17.2, 17.1, -1, "2.1.5"), self.G, "X"), {"chg": "na", "chg_why": "series"})
        self.assertTrue(gii.change(r(100, 130), self.G, "L")["chg_log"])   # measured on the GII's log scale

    def test_the_wgi_is_compared_within_one_release(self):
        G = {"indicators": {"IN.1.1.2": {"values": [-2.0, -1.0, 0.0, 1.0, 2.0]}}}   # IQR 2, threshold 0.1
        r = {"code": "1.1.2", "value": -0.2, "upd_value": -0.42, "dir": 1}
        c = gii.change(r, G, "IN.1.1.2", {"2018": -0.39, "2025": -0.42})
        self.assertEqual((c["chg"], c["chg_base"], c["chg_base_year"], c["chg_delta"]), ("same", -0.39, "2018", -0.03))   # not -0.22 against the printed -0.2
        self.assertEqual(gii.change(r, G, "IN.1.1.2", {"2025": -0.42}), {"chg": "na", "chg_why": "no_base"})

    def test_the_published_markers(self):
        for r in PUB["indicators"]:
            self.assertEqual(r["dir"], -1 if r["code"] in STAR else 1, r["code"])
            if "upd_value" in r:
                self.assertIn(r["chg"], ("better", "worse", "same", "na"), r["code"])
                if r["chg"] in ("better", "worse"):
                    self.assertGreaterEqual(abs(r["chg_delta"]), r["chg_thr"] if not r.get("chg_log") else 0, r["code"])
                    self.assertEqual(r["chg"] == "better", (r["upd_value"] - r.get("chg_base", r["value"])) * r["dir"] > 0, r["code"])
            else:
                self.assertNotIn("chg", r)
        self.assertEqual(PUB_BY["2.2.3"]["chg"], "na")   # no 2021 value
        self.assertEqual(PUB_BY["6.2.2"]["chg"], "na")   # another source and definition
        self.assertEqual((PUB_BY["2.1.5"]["chg"], PUB_BY["6.2.1"]["chg"]), ("na", "na"))
        self.assertNotIn("c26_pos", PUB_BY["2.1.5"])
        for code in ("1.1.2", "1.2.1", "1.2.2"):
            self.assertEqual(PUB_BY[code]["chg_base_year"], "2018", code)   # the data year of the GII 2020 (Appendix III)
            self.assertEqual(PUB_BY[code]["value"], BY[code]["value"], code)   # the printed value is untouched
        self.assertEqual(PUB_BY["1.1.2"]["chg"], "same")
        self.assertEqual(PUB["about"]["status_count"], {"same": 49, "renamed": 8, "redefined": 7, "dropped": 16})
        self.assertEqual(PUB["about"]["change_share"], 0.05)


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def _xlsx(rows):
    """A minimal .xlsx with one sheet: the first row as shared strings, the rest inline (numbers as numbers), as BLS's files mix them."""
    shared = rows[0]
    def cell(ref, v, r):
        if r == 1:
            return f'<c r="{ref}" t="s"><v>{shared.index(v)}</v></c>'
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    body = "".join(f'<row r="{i}">' + "".join(cell(f"{chr(65 + j)}{i}", v, i) for j, v in enumerate(row)) + "</row>" for i, row in enumerate(rows, 1))
    sst = f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>"
    return _zip({"xl/sharedStrings.xml": sst, "xl/worksheets/sheet1.xml": f'<worksheet {ns}><sheetData>{body}</sheetData></worksheet>'})


class KeylessMethods(unittest.TestCase):
    """The FPR methods of the keyless updates, on small fixtures (no network)."""

    def test_electricity_per_million_reproduces_the_2017_value(self):
        # EIA's net generation for 2017 (16.3707 billion kWh) over the Census Bureau's 3,325,284 people: 4,923.1, against FPR's printed 4,920.0
        y, v = gii.per_million({"2016": 20.6427, "2017": 16.3707}, {"2017": 3325284, "2018": 3193344})
        self.assertEqual((y, round(v, 1)), ("2017", 4923.1))
        self.assertEqual(gii.per_million({"2024": 20.0, "2023": 19.0}, {"2023": 2_000_000, "2024": 2_500_000}), ("2024", 8000.0))   # the latest year both have
        self.assertIsNone(gii.per_million({"2024": 20.0}, {"2023": 3_000_000}))

    def test_parse_intl_keeps_the_puerto_rico_series(self):
        lines = [{"series_id": gii.EIA_GEN, "name": "Electricity net generation, Puerto Rico, Annual", "data": [["2024", 19.9], ["2023", "--"]], "last_updated": "2026-02-24"},
                 {"series_id": gii.EIA_ENERGY, "data": [["2024", 0.30]], "last_updated": "2026-03-11"},
                 {"series_id": gii.EIA_LOWC, "data": [["2024", 0.0042]], "last_updated": "2026-03-11"},
                 {"series_id": "INTL.2-12-USA-BKWH.A", "data": [["2024", 4300.0]]}]
        data = _zip({"INTL.txt": "\n".join(json.dumps(x) for x in lines)})
        out = gii.parse_intl(data)
        self.assertEqual(out["values"][gii.EIA_GEN], {"2024": 19.9})   # "--" left out
        self.assertEqual(sorted(out["values"]), sorted([gii.EIA_GEN, gii.EIA_ENERGY, gii.EIA_LOWC]))
        with self.assertRaises(KeyError):
            gii.parse_intl(_zip({"INTL.txt": json.dumps(lines[0])}))   # a missing series is an error, not a silent gap

    def test_low_carbon_share(self):
        y, v = gii.share_of({"2023": 0.0037, "2024": 0.0042, "2025": 0.005}, {"2023": 0.30, "2024": 0.30})   # the latest year both have
        self.assertEqual((y, round(v, 6)), ("2024", 1.4))
        y, v = gii.share_of({"2024": 0.00417622868065401}, {"2024": 0.30469201729206574})   # EIA's 2024 values for Puerto Rico
        self.assertEqual((y, round(v, 2)), ("2024", 1.37))

    def test_parse_pep_reads_puerto_rico(self):
        csv = "SUMLEV,REGION,DIVISION,STATE,NAME,ESTIMATESBASE2020,POPESTIMATE2020,POPESTIMATE2024,POPESTIMATE2025\n" \
              "040,3,5,12,Florida,1,2,3,4\n040,X,X,72,Puerto Rico,3285874,3281591,3202521,3184835\n"
        self.assertEqual(gii.parse_pep(csv.encode("latin-1")), {"values": {"2020": 3281591, "2024": 3202521, "2025": 3184835}, "vintage": "2025"})

    def test_knowledge_share_from_soc_major_groups(self):
        hdr = ["AREA", "AREA_TITLE", "OCC_CODE", "O_GROUP", "TOT_EMP"]
        rows = [hdr, ["72", "Puerto Rico", "00-0000", "total", 1000], ["72", "Puerto Rico", "11-0000", "major", 100],
                ["72", "Puerto Rico", "11-1011", "detailed", 10], ["72", "Puerto Rico", "31-0000", "major", 50], ["01", "Alabama", "11-0000", "major", 999]]
        rows += [["72", "Puerto Rico", f"{g}-0000", "major", 20] for g in gii.ISCO_1_3[1:]]
        o = gii.parse_oews(_zip({"oesm25st/state_M2025_dl.xlsx": _xlsx(rows)}))
        self.assertEqual((o["year"], o["total"], o["major"]["11"], o["major"]["31"]), ("2025", 1000.0, 100.0, 50.0))   # detailed rows and other states ignored
        self.assertAlmostEqual(gii.knowledge_share(o), 100 * (100 + 20 * 9) / 1000)   # groups 11-29; 31 (healthcare support) left out
        o["major"]["23"] = None   # a suppressed group ("**"): no value rather than a low one
        self.assertIsNone(gii.knowledge_share(o))
        self.assertEqual(gii.ISCO_1_3, ("11", "13", "15", "17", "19", "21", "23", "25", "27", "29"))

    def test_bls_gets_a_descriptive_user_agent(self):
        old = os.environ.pop("FRESHNESS_CONTACT", None)
        try:
            self.assertIn("Foundation for Puerto Rico", gii.bls_headers()["User-Agent"])
            os.environ["FRESHNESS_CONTACT"] = "role-mailbox"
            self.assertTrue(gii.bls_headers()["User-Agent"].endswith(" contact: role-mailbox"))
        finally:
            os.environ.pop("FRESHNESS_CONTACT", None)
            if old is not None:
                os.environ["FRESHNESS_CONTACT"] = old

    def test_no_api_key_anywhere(self):
        src = (ROOT / "gii.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"(?i)api_key|apikey|x-api-key|registrationkey")


class Crosswalk(unittest.TestCase):
    def test_every_indicator_has_a_status_and_the_counts_add_up(self):
        self.assertEqual(sorted(CW["crosswalk"]), sorted(BY))
        for code, x in CW["crosswalk"].items():
            self.assertIn(x["status"], ("same", "renamed", "redefined", "dropped"), code)
            self.assertEqual(x["c26"] is None, x["status"] == "dropped", code)
            if x["status"] != "same":
                self.assertTrue(x["note"]["en"] and x["note"]["es"], code)
        mapped = {x["c26"] for x in CW["crosswalk"].values() if x["c26"]}
        new = {e["c26"] for e in CW["new_2026"]}
        self.assertFalse(mapped & new)
        self.assertEqual(len(mapped) + len(new), 79)   # the GII 2026's 79 indicators
        self.assertEqual({r["code"]: r["c26_status"] for r in PUB["indicators"]}, {c: x["status"] for c, x in CW["crosswalk"].items()})
        for e in CW["new_2026"]:
            self.assertIn(e["pr"], ("yes", "no", "proxy", "proprietary", "check"))
            self.assertTrue(e["name"]["es"] and e["pr_note"]["es"])

    @unittest.skipUnless(gii.G26_EXTRACT.exists(), "needs the GII 2026 extract (cache/gii/2026/)")
    def test_the_crosswalk_covers_the_gii_2026_database(self):
        ext = json.loads(gii.G26_EXTRACT.read_text(encoding="utf-8"))["indicators"]
        mapped = {x["c26"] for x in CW["crosswalk"].values() if x["c26"]} | {e["c26"] for e in CW["new_2026"]}
        self.assertEqual(mapped, set(ext))
        self.assertEqual({c for c, v in ext.items() if v.get("dir") == -1}, {"IN.1.1.1", "IN.2.1.5", "IN.3.2.2", "IN.4.3.1", "IN.4.3.2"})
        self.assertEqual(sum(1 for v in ext.values() if v.get("log")), 9)   # WIPO's Appendix I: 9 log-transformed indicators
        for code, (c26, lower, _) in gii.COMPARE.items():
            self.assertEqual(lower, ext[c26]["dir"] == -1, code)   # the comparison uses the database's own direction
        for code in STAR:
            c26 = CW["crosswalk"][code]["c26"]
            if c26:
                self.assertEqual(ext[c26]["dir"], -1, code)


class Page(unittest.TestCase):
    HTML = (ROOT / "site" / "gii.html").read_text(encoding="utf-8")

    def test_marker_notice_noindex_and_labels(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', self.HTML)
        self.assertIn('class="note caution review-note"', self.HTML)
        self.assertIn('data-ka="gii"', self.HTML)
        self.assertIn("FPR's calculation, not an official ranking.", self.HTML)
        self.assertIn("Puerto Rico is not one of the economies of the official Global Innovation Index", self.HTML)
        self.assertIn("Cornell University, INSEAD and the World Intellectual Property Organization (WIPO)", self.HTML)
        self.assertIn("WIPO, Global Innovation Index 2026, CC BY 4.0", self.HTML)
        knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
        self.assertRegex(knowledge, r"id: 'gii',.*page: 'gii\.html', status: 'published', review: true")

    def test_the_data_loads_on_demand(self):
        js = (ROOT / "site" / "js" / "gii.js").read_text(encoding="utf-8")
        self.assertNotIn("gii_profile", self.HTML)   # not embedded: gii.js fetches it
        self.assertNotIn("gii_changes", self.HTML)
        self.assertIn("fetchJson('data/gii_profile.json')", js)
        self.assertIn("fetchJson('data/gii_changes.json')", js)   # only when "Changes in the index since 2020" is opened
        self.assertEqual(re.findall(r"<details[^>]*>", self.HTML), ['<details class="gp-changes" id="giiChanges">'])   # the rows are drawn from the data
        routes = json.loads((ROOT / "dictionary_src" / "routes.json").read_text(encoding="utf-8"))["routes"]
        self.assertIn("gii_changes.json", routes["gii"]["on_use"])

    def test_the_legend_and_labels_of_the_markers(self):
        self.assertIn("Indicative position calculated by FPR, not an official WIPO rank.", self.HTML)
        self.assertIn('"Better" follows the direction of the index, not a value judgement.', self.HTML)
        self.assertIn("only the arrow is coloured", self.HTML)
        js = (ROOT / "site" / "js" / "gii.js").read_text(encoding="utf-8")
        for k in ("better than 2021", "worse than 2021", "no meaningful change from 2021", "not comparable with 2021"):
            self.assertIn("T('" + k + "')", js)
        self.assertIn('role="img" aria-label=', js)
        self.assertIn("r.c26_pos + '/' + r.c26_of", js)   # X/N, like the profile
        es = json.loads((ROOT / "i18n_src" / "es" / "gii.json").read_text(encoding="utf-8"))
        self.assertEqual(es["better than 2021"], "mejor que 2021")
        self.assertEqual(es["worse than 2021"], "peor que 2021")
        css = (ROOT / "site" / "css" / "gii.css").read_text(encoding="utf-8")
        self.assertIn(".gp-chg.better { color: var(--tint-green-fg); }", css)
        self.assertIn(".gp-chg.worse { color: var(--color-danger); }", css)


if __name__ == "__main__":
    unittest.main()
