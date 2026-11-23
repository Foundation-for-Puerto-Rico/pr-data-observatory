"""freshness.py and refresh/sources.json: the schedule covers every source, the checks compare with their own past, rebuilds follow the review rules."""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import freshness as F  # noqa: E402

SCHED = F.load_schedule()
BY = {s["id"]: s for s in SCHED["sources"]}


class FakeResp:
    def __init__(self, status=200, headers=None, js=None, text=""):
        self.status_code, self.headers, self._js, self.text = status, headers or {}, js, text

    def json(self):
        if self._js is None:
            raise ValueError("not json")
        return self._js

    def close(self):
        pass


class FakeHttp:
    """Answers by URL: a dict {url: FakeResp}; anything else is a 404."""
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def request(self, method, url, contact=False, **kw):
        self.calls.append((method, url))
        a = self.answers.get(url)
        if isinstance(a, Exception):
            raise a
        return a or FakeResp(404)


class Schedule(unittest.TestCase):
    def test_every_source_is_scheduled_or_named_static_once(self):
        listed = json.loads((ROOT / "dictionary_src" / "sources.json").read_text(encoding="utf-8"))
        ids = [k for k in listed if not k.startswith("_")]
        sched = [s["id"] for s in SCHED["sources"]] + [s["id"] for s in SCHED["static"]]
        self.assertEqual(sorted(ids), sorted(sched), "each source of dictionary_src/sources.json is either checked or named static, once")

    def test_fields(self):
        kinds = {"head", "range-size", "walk", "json", "regex", "calendar", "follows"}
        for s in SCHED["sources"]:
            self.assertIn(s["probe"]["kind"], kinds, s["id"])
            self.assertIn(s["unit"], SCHED["units"], s["id"])
            self.assertIn(s["review"], ("auto", "human"), s["id"])
            self.assertTrue(all(1 <= m <= 12 for m in s["hot_months"]), s["id"])
            self.assertGreaterEqual(s["every_days"], 1, s["id"])
            if s["probe"]["kind"] == "follows":
                self.assertIn(s["probe"]["source"], BY)

    def test_public_money_and_licence_sensitive_sources_always_wait_for_a_person(self):
        for i in ("usaspending", "openfema", "hrsa_hpsa", "hrsa_sites", "ppr_type1", "acs5", "census_pep", "cms_medicare_enrollment", "usgs_comcat"):
            self.assertEqual(BY[i]["review"], "human", i)

    def test_a_rebuild_merges_itself_only_when_every_source_it_reads_is_routine(self):
        # a rebuild re-reads every source of its unit, so a new vintage of one would ride along with a routine change of another (review of PR #37)
        self.assertEqual(F.review_of(SCHED, "infrastructure", ["epa_echo_sdwa"]), "human", "the bridges (a new year) are read too")
        for u, x in SCHED["units"].items():
            if x["where"] == "ci":
                mine = [s for s in SCHED["sources"] if s["unit"] == u]
                self.assertEqual(F.review_of(SCHED, u), "auto" if all(s["review"] == "auto" for s in mine) else "human", u)
        with self.assertRaises(SystemExit):
            F.review_of(SCHED, "health", ["cms_medicare_enrollment"])   # a source of another unit cannot vouch for this one

    def test_units_a_runner_rebuilds_are_the_ones_rebuild_yml_offers(self):
        ci = sorted(k for k, u in SCHED["units"].items() if u["where"] == "ci")
        wf = (ROOT / ".github" / "workflows" / "rebuild.yml").read_text(encoding="utf-8")
        offered = sorted(x.strip() for x in wf.split("options: [", 1)[1].split("]", 1)[0].split(","))
        self.assertEqual(ci, offered)
        for k in ci:
            u = SCHED["units"][k]
            self.assertTrue(u["runs"] and u["files"], k)
            for f in u["files"]:
                self.assertTrue((ROOT / "site" / "data" / f).exists(), f)

    def test_the_documented_schedule_is_current(self):
        self.assertEqual(F.main(["--check-doc"]), 0, "run python freshness.py --doc and paste the table into docs/automation.md")


class Due(unittest.TestCase):
    def test_interval_and_hot_months(self):
        s = {"probe": {"kind": "head"}, "every_days": 30, "hot_months": [12]}
        self.assertTrue(F.due(s, {}, date(2026, 10, 15)), "never checked: due")
        self.assertFalse(F.due(s, {"checked": "2026-10-05"}, date(2026, 10, 15)))
        self.assertTrue(F.due(s, {"checked": "2026-09-15"}, date(2026, 10, 15)))
        self.assertTrue(F.due(s, {"checked": "2026-12-14"}, date(2026, 12, 15)), "a hot month: daily")
        self.assertFalse(F.due({"probe": {"kind": "follows"}, "every_days": 1, "hot_months": []}, {}, date(2026, 1, 1)))


class Probes(unittest.TestCase):
    T = date(2026, 10, 15)

    def test_periods(self):
        self.assertEqual([F.step("2026-11", "month"), F.step("2026-12", "month"), F.step("2025", "year")], ["2026-12", "2027-01", "2026"])
        self.assertEqual(F.fill("https://x/{month}_generator{y}.xlsx", "2026-09"), "https://x/september_generator2026.xlsx")
        self.assertEqual(F.fill("https://x/{y}/CRE{yy}.csv", "2025"), "https://x/2025/CRE25.csv")

    def test_walk_finds_the_newest_published_period(self):
        u = "https://x/{y}.dat"
        h = FakeHttp({"https://x/2024.dat": FakeResp(200), "https://x/2025.dat": FakeResp(200)})
        self.assertEqual(F.probe({"probe": {"kind": "walk", "url": u, "start": "2024", "step": "year"}}, h, self.T), "2025")
        with self.assertRaises(F.ProbeError):
            F.probe({"probe": {"kind": "walk", "url": u, "start": "2030", "step": "year"}}, h, self.T)

    def test_walk_starts_from_the_newest_period_seen_and_never_goes_blind(self):
        ok = {f"https://x/{y}.dat": FakeResp(200) for y in range(2024, 2041)}
        p = {"probe": {"kind": "walk", "url": "https://x/{y}.dat", "start": "2024", "step": "year"}}
        self.assertEqual(F.probe(p, FakeHttp(ok), self.T, last="2035"), "2040", "from the last answer, not the start written in 2026")
        self.assertEqual(F.probe(p, FakeHttp(ok), self.T, last="2026-08"), "2040", "a last answer of another shape is ignored")
        many = {f"https://m/{y}.dat": FakeResp(200) for y in range(2024, 2100)}
        with self.assertRaises(F.ProbeError):
            F.probe({"probe": {"kind": "walk", "url": "https://m/{y}.dat", "start": "2024", "step": "year"}}, FakeHttp(many), self.T)

    def test_a_server_error_is_a_failed_check_not_a_missing_period(self):
        h = FakeHttp({"https://x/2024.dat": FakeResp(200), "https://x/2025.dat": FakeResp(500)})
        with self.assertRaises(F.ProbeError):
            F.probe({"probe": {"kind": "walk", "url": "https://x/{y}.dat", "start": "2024", "step": "year"}}, h, self.T)

    def test_walk_spreadsheet_ignores_a_503_page(self):
        h = FakeHttp({"https://e/august_generator2026.xlsx": FakeResp(200, {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
                      "https://e/september_generator2026.xlsx": FakeResp(503, {"Content-Type": "text/html"})})
        p = {"probe": {"kind": "walk", "url": "https://e/{month}_generator{y}.xlsx", "start": "2026-08", "step": "month", "ok": "spreadsheet"}}
        self.assertEqual(F.probe(p, h, self.T), "2026-08")

    def test_json_head_range_regex_calendar(self):
        h = FakeHttp({"https://j": FakeResp(200, js={"a": [{"b": 7}]}), "https://h": FakeResp(200, {"ETag": "x1", "Content-Length": "9"}),
                      "https://r": FakeResp(206, {"Content-Range": "bytes 0-0/14139704"}), "https://p": FakeResp(200, text="DelitosTipoI-2024-12 DelitosTipoI-2025-12")})
        self.assertEqual(F.probe({"probe": {"kind": "json", "urls": ["https://j"], "paths": ["a.0.b"]}}, h, self.T), "7")
        h.answers["https://k"] = FakeResp(200, js={"data": {"attributes": {"updated": "2021-08-18"}}})   # per_url: one list of paths for each address (the landslide map's copy and its USGS release)
        self.assertEqual(F.probe({"probe": {"kind": "json", "urls": ["https://j", "https://k"], "paths": [["a.0.b"], ["data.attributes.updated"]], "per_url": True}}, h, self.T), "7 | 2021-08-18")
        self.assertEqual(F.probe({"probe": {"kind": "head", "url": "https://h", "headers": ["ETag", "Content-Length"]}}, h, self.T), "ETag=x1 | Content-Length=9")
        self.assertEqual(F.probe({"probe": {"kind": "range-size", "urls": ["https://r"]}}, h, self.T), "14139704")
        self.assertEqual(F.probe({"probe": {"kind": "regex", "url": "https://p", "pattern": r"DelitosTipoI-(\d{4})-12"}}, h, self.T), "2025")
        fy = {"probe": {"kind": "calendar", "rule": "fiscal-year-final"}}
        self.assertEqual([F.probe(fy, h, date(2026, 11, 14)), F.probe(fy, h, date(2026, 11, 15))], ["FY2025", "FY2026"])
        self.assertEqual(F.probe({"probe": {"kind": "calendar", "rule": "quarter"}}, h, self.T), "2026-Q4")
        su = {"probe": {"kind": "calendar", "rule": "summer"}}   # surface heat (heat.py): a summer is complete once October begins
        self.assertEqual([F.probe(su, h, date(2026, 9, 30)), F.probe(su, h, date(2026, 10, 1)), F.probe(su, h, date(2027, 3, 1))], ["summer-2025", "summer-2026", "summer-2026"])
        import heat
        self.assertEqual([heat.summers(date(2026, 9, 30)), heat.summers(date(2026, 10, 1))], [[2023, 2024, 2025], [2024, 2025, 2026]])

    def test_walk_get_asks_for_a_byte_and_never_uses_head(self):
        # EPA's Envirofacts downloads answer HEAD with 500 and a missing year with 404 (conditions.py, TRI)
        h = FakeHttp({"https://t/2024.csv": FakeResp(206), "https://t/2025.csv": FakeResp(404)})
        p = {"probe": {"kind": "walk", "url": "https://t/{y}.csv", "start": "2024", "step": "year", "ok": "get"}}
        self.assertEqual(F.probe(p, h, self.T), "2024")
        self.assertEqual({m for m, _ in h.calls}, {"GET"})
        with self.assertRaises(F.ProbeError):
            F.probe(p, FakeHttp({"https://t/2024.csv": FakeResp(206), "https://t/2025.csv": FakeResp(500)}), self.T)


class Runs(unittest.TestCase):
    def sched(self):
        return {"units": {"u": {"where": "ci", "how": "python u.py"}, "l": {"where": "local", "how": "python l.py"}},
                "sources": [{"id": "a", "name": "A", "probe": {"kind": "json", "urls": ["https://a"], "paths": ["v"]}, "every_days": 1, "hot_months": [], "unit": "u", "review": "auto"},
                            {"id": "b", "name": "B", "probe": {"kind": "json", "urls": ["https://b"], "paths": ["v"]}, "every_days": 1, "hot_months": [], "unit": "l", "review": "human"},
                            {"id": "c", "name": "C", "probe": {"kind": "json", "urls": ["https://c"], "paths": ["v"]}, "every_days": 1, "hot_months": [], "unit": "u", "review": "human", "code_edit": "X.YEARS"}]}

    def test_baseline_then_change_then_failure(self):
        s, state, t = self.sched(), {}, date(2026, 10, 15)
        h = FakeHttp({u: FakeResp(200, js={"v": 1}) for u in ("https://a", "https://b", "https://c")})
        ch, fail, checked = F.run(s, state, t, h)
        self.assertEqual((ch, fail, sorted(checked)), ([], [], ["a", "b", "c"]), "the first answer is a baseline, not a change")
        h = FakeHttp({"https://a": FakeResp(200, js={"v": 2}), "https://b": FakeResp(200, js={"v": 2}), "https://c": FakeResp(200, js={"v": 2})})
        ch, fail, _ = F.run(s, state, date(2026, 10, 16), h)
        self.assertEqual(sorted(c["id"] for c in ch), ["a", "b", "c"])
        self.assertEqual(F.rebuildable(ch), {"u": ["a"]}, "only a runner unit without a code edit is rebuilt by itself")
        self.assertEqual([F.review_of(s, "u", ["a"]), F.review_of(s, "l")], ["human", "human"], "unit u also reads c, which is reviewed")
        h = FakeHttp({"https://a": F.ProbeError("timeout")})
        ch, fail, _ = F.run(s, state, date(2026, 10, 17), h, only={"a"})
        self.assertEqual((ch, [f["id"] for f in fail], state["a"]["fingerprint"]), ([], ["a"], "2"), "a failed check keeps its last answer")
        self.assertTrue(fail[0]["new"])
        _, fail2, _ = F.run(s, state, date(2026, 10, 18), h, only={"a"})
        self.assertEqual((fail2[0]["since"], fail2[0]["new"]), ("2026-10-17", False), "a known failure is reported but notifies once")
        F.run(s, state, date(2026, 10, 19), FakeHttp({"https://a": FakeResp(200, js={"v": 2})}), only={"a"})
        self.assertNotIn("failing_since", state["a"], "a success clears the failure")
        rep = F.report(ch, fail, [], s, state, date(2026, 10, 17))
        self.assertIn("Checks that failed", rep)


class AfterARebuild(unittest.TestCase):
    def test_stamps_are_not_changes(self):
        self.assertEqual(F.strip_stamps({"built": "2026-10-15", "x": [{"retrieved": 1, "v": 2}]}), {"x": [{"v": 2}]})
        self.assertEqual(F.strip_stamps({"as_of": "2026-10", "v": 1}, ["as_of"]), {"v": 1}, "a unit can name its own download stamps")
        self.assertEqual(F.strip_stamps({"as_of": "2026-10", "v": 1}), {"as_of": "2026-10", "v": 1}, "as_of is data elsewhere (EIA month, HRSA file date)")
        self.assertEqual(SCHED["units"]["environment"].get("ignore"), ["as_of"])

    def test_sync_time_moves_only_the_end_forward(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "site" / "data").mkdir(parents=True); (tmp / "dictionary_src").mkdir()
            recs = [{"file": "a.json", "time": {"first": 2013, "last": 2024, "years_path": "years"}},
                    {"file": "b.json", "time": {"first": 2013, "last": 2025, "years_path": "years"}},
                    {"file": "c.json", "time": {"first": 2010, "last": 2024, "years_path": "years"}}]
            (tmp / "dictionary_src" / "datasets.json").write_text(json.dumps({"datasets": recs}, indent=1) + "\n", encoding="utf-8")
            yrs = lambda a, b: {"years": list(range(a, b + 1))}
            for f, d in (("a.json", yrs(2013, 2025)), ("b.json", yrs(2013, 2024)), ("c.json", yrs(2011, 2025))):
                (tmp / "site" / "data" / f).write_text(json.dumps(d), encoding="utf-8")
            moved = F.sync_time(tmp)
            out = {r["file"]: r["time"]["last"] for r in json.loads((tmp / "dictionary_src" / "datasets.json").read_text(encoding="utf-8"))["datasets"]}
            self.assertEqual(moved, ["a.json: 2024 -> 2025"])
            self.assertEqual(out, {"a.json": 2025, "b.json": 2025, "c.json": 2024}, "never backward, never when the start moved")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Workflows(unittest.TestCase):
    def test_freshness_keeps_its_answers_and_starts_rebuilds(self):
        t = (ROOT / ".github" / "workflows" / "freshness.yml").read_text(encoding="utf-8")
        for s in ("actions/cache/restore@", "actions/cache/save@", "python freshness.py", "\"workflow\", \"run\", \"rebuild.yml\"", "issues: write", "['notify']"):
            self.assertIn(s, t)
        self.assertNotIn("contents: write", t, "the daily checks never write to the repository")

    def test_rebuild_publishes_only_real_changes_and_merges_only_routine_ones(self):
        t = (ROOT / ".github" / "workflows" / "rebuild.yml").read_text(encoding="utf-8")
        self.assertIn('python freshness.py --changed-unit "${{ inputs.unit }}"', t)
        self.assertIn("python freshness.py --sync-time | tee .years_moved", t)
        self.assertIn('[ -z "$moved" ] || review=human', t, "a dataset that reaches a later year is a new vintage: always reviewed")
        self.assertIn('python freshness.py --review "$UNIT"', t)
        self.assertIn("python contract.py", t)
        self.assertIn('if [ "$review" = "auto" ]; then gh pr merge "$branch" --auto --merge; fi', t)
        self.assertIn("Superseded by a newer rebuild", t)
        order = [t.index(s) for s in ("bash .rebuild.sh", "--changed-unit", "python contract.py", "--review \"$UNIT\"", "git push -u origin")]
        self.assertEqual(order, sorted(order))


if __name__ == "__main__":
    unittest.main()
