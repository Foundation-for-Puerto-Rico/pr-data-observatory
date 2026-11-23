"""Single audit findings that repeat (audit_findings.json, audit_findings.py, HANDOFF decision 110, step 3): a finding is counted once per audit,
the flags hold when any of its lines sets them, the audits are asked for in chunks the service accepts, no body is named in the file, the sums
agree, and the page's figures are the file's. The rebuild from the cache is compared with the published file when the cache is complete."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import audit_findings as A  # noqa: E402

OUT = ROOT / "site" / "data" / "audit_findings.json"
PAGE = ROOT / "site" / "unused-funds.html"


def f(report, ref, line, repeat="N", material="N", questioned="N"):
    return {"report_id": report, "reference_number": ref, "award_reference": line, "is_repeat_finding": repeat, "is_material_weakness": material, "is_questioned_costs": questioned}


class Rules(unittest.TestCase):
    def test_what_is_read(self):
        self.assertEqual(A.FIRST_YEAR, 2019)
        self.assertEqual(A.DEADLINE_MONTHS, 9)
        for sel in (A.GENERAL, A.FINDINGS, A.AWARDS):
            for word in ("contact", "email", "phone", "address", "ein", "uei", "auditor"):
                self.assertNotIn(word, sel.lower())

    def test_a_finding_is_counted_once_however_many_award_lines_it_touches(self):
        seen = A.findings_of([f("r1", "2023-001", "AWARD-0001"), f("r1", "2023-001", "AWARD-0002", repeat="Y"), f("r1", "2023-002", "AWARD-0001", questioned="Y"),
                              f("r2", "2023-001", "AWARD-0001", material="Y")])
        self.assertEqual(len(seen), 3)
        self.assertTrue(seen[("r1", "2023-001")]["repeat"])   # any line sets the flag
        self.assertEqual(seen[("r1", "2023-001")]["lines"], {"AWARD-0001", "AWARD-0002"})
        self.assertEqual(A.tally(seen.values()), [3, 1, 1, 1])

    def test_chunks_keep_every_audit_and_stay_under_the_address_limit(self):
        ids = [f"2023-06-GSAFAC-{k:010d}" for k in range(2000)]
        ch = A.chunks(ids)
        self.assertEqual([i for c in ch for i in c], ids)
        self.assertGreater(len(ch), 1)
        for c in ch:
            self.assertLessEqual(sum(len(i) + 1 for i in c), A.MAX_ADDRESS + len(ids[0]) + 1)
        self.assertEqual(A.chunks([]), [])

    def test_months_to_acceptance(self):
        self.assertAlmostEqual(A.months_late({"fy_end_date": "2023-06-30", "fac_accepted_date": "2024-03-31"}), 9.0, delta=0.1)
        self.assertIsNone(A.months_late({"fy_end_date": None, "fac_accepted_date": "2024-03-31"}))
        self.assertIsNone(A.months_late({"fy_end_date": "2023-06-30", "fac_accepted_date": "not a date"}))

    def test_summarise_counts_a_finding_once_in_each_program_and_agency_it_touches(self):
        audits = [{"report_id": "r1", "audit_year": "2023", "auditee_name": "X", "entity_type": "local", "fy_end_date": "2023-06-30", "total_amount_expended": 1000, "fac_accepted_date": "2024-06-30"},
                  {"report_id": "r2", "audit_year": "2023", "auditee_name": "Y", "entity_type": "non-profit", "fy_end_date": "2023-12-31", "total_amount_expended": 500, "fac_accepted_date": "2024-05-31"}]
        found = [f("r1", "2023-001", "AWARD-0001", repeat="Y"), f("r1", "2023-001", "AWARD-0002"), f("r1", "2023-002", "AWARD-0003")]
        lines = [{"report_id": "r1", "award_reference": "AWARD-0001", "federal_agency_prefix": "14", "federal_award_extension": "871", "federal_program_name": "A", "amount_expended": 1, "findings_count": 1},
                 {"report_id": "r1", "award_reference": "AWARD-0002", "federal_agency_prefix": "14", "federal_award_extension": "872", "federal_program_name": "B", "amount_expended": 1, "findings_count": 1},
                 {"report_id": "r1", "award_reference": "AWARD-0003", "federal_agency_prefix": "93", "federal_award_extension": "600", "federal_program_name": "C", "amount_expended": 1, "findings_count": 1}]
        d = A.summarise({"read": "2026-11-18"}, audits, found, lines)
        self.assertEqual(d["totals"], {"audits": 2, "audits_with_findings": 1, "tally": [2, 1, 0, 0], "programs": 3})
        self.assertEqual(d["by_year"][0][:8], [2023, 2, 1, 2, 1, 0, 0, 1])   # one of the two audits was accepted after nine months
        self.assertEqual({r[0]: r[3] for r in d["listings"]}, {"14.871": 1, "14.872": 1, "93.600": 1})
        self.assertEqual({r[0]: r[1] for r in d["agencies"]}, {"Department of Housing and Urban Development": 1, "Department of Health and Human Services": 1})   # one finding, two lines of one agency: once
        self.assertEqual(d["kinds"]["local"], {"audits": 1, "tally": [2, 1, 0, 0]})
        self.assertNotIn("X", json.dumps(d["kinds"]) + json.dumps(d["by_year"]))

    def test_the_municipio_governments_are_matched_by_name_and_counted_over_three_years(self):
        def audit(rid, name, year, accepted="2024-03-01"):
            return {"report_id": rid, "audit_year": str(year), "auditee_name": name, "entity_type": "local", "fy_end_date": f"{year}-06-30", "total_amount_expended": 1, "fac_accepted_date": accepted}
        audits = [audit("a1", "MUNICIPALITY OF PONCE", 2023), audit("a2", "MUNICIPIO DE PONCE", 2024), audit("a3", "VALLE VERDE HOUSING - MUNICIPALITY OF ADJUNTAS", 2023),
                  audit("a4", "MUNICIPALITY OF PONCE", 2023, "2024-09-01"), audit("a5", "MUNICIPALITY OF PONCE", 2019), audit("a6", "MUNICIPALITY OF VIEQUES", 2025)]
        seen = A.findings_of([f("a1", "2023-001", "L1", repeat="Y"), f("a1", "2023-002", "L1"), f("a2", "2024-001", "L1"), f("a3", "2023-001", "L1"), f("a4", "2023-009", "L1"), f("a5", "2019-001", "L1")])
        years, out = A.municipio_governments(audits, seen, 2024)
        self.assertEqual(years, [2022, 2023, 2024])
        self.assertEqual(len(out), 78)
        ponce = out["72113"]
        self.assertEqual(ponce, [2, 3, 1, 2024])            # 2023 (first accepted: two findings, one repeated) and 2024; the second 2023 audit and 2019 are not counted
        self.assertEqual(out["72001"], [0, 0, 0, None])     # the housing project is not the municipio's government
        self.assertEqual(out["72147"], [0, 0, 0, 2025])     # filed, but outside the three years

    def test_an_agency_the_list_does_not_know_is_grouped(self):
        self.assertEqual(A.AGENCY.get("14"), "Department of Housing and Urban Development")
        self.assertNotIn("00", A.AGENCY)


@unittest.skipUnless(OUT.exists(), "audit_findings.json is not built")
class Published(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))

    def test_shape(self):
        d = self.d
        self.assertEqual(d["years"][0], 2019)
        self.assertEqual([r[0] for r in d["by_year"]], d["years"])
        for r in d["by_year"]:
            self.assertEqual(len(r), 10)
            self.assertGreaterEqual(r[1], r[2])
            self.assertGreaterEqual(r[3], r[4])
            self.assertGreaterEqual(r[1], r[7])
        for r in d["listings"]:
            self.assertEqual(len(r), 7)
            self.assertRegex(r[0], r"^\d\d\.")
            self.assertGreaterEqual(r[3], r[4])

    def test_the_years_and_the_kinds_add_up_to_the_totals(self):
        d, t = self.d, self.d["totals"]
        self.assertEqual(sum(r[1] for r in d["by_year"]), t["audits"])
        self.assertEqual(sum(r[2] for r in d["by_year"]), t["audits_with_findings"])
        self.assertEqual([sum(r[k] for r in d["by_year"]) for k in (3, 4, 5, 6)], t["tally"])
        done = [r for r in d["by_year"] if r[0] <= d["kinds_years"][1]]   # the kinds leave out the audit years still arriving
        self.assertEqual(d["kinds_years"][1], int(d["read"][:4]) - 2)
        self.assertEqual([sum(v["tally"][k] for v in d["kinds"].values()) for k in range(4)], [sum(r[k] for r in done) for k in (3, 4, 5, 6)])
        self.assertEqual(sum(v["audits"] for v in d["kinds"].values()), sum(r[1] for r in done))
        self.assertEqual(len(d["listings"]), t["programs"])

    def test_programs_add_up_to_at_least_the_findings_that_name_a_program(self):
        d = self.d
        self.assertGreaterEqual(sum(r[3] for r in d["listings"]), sum(r[1] for r in d["agencies"]))
        self.assertGreater(sum(r[3] for r in d["listings"]), 0.9 * d["totals"]["tally"][0], "most findings name a program: the award lines were read for every audit")

    def test_the_municipio_governments_are_the_78_and_are_keyed_by_code(self):
        m = self.d["municipio_governments"]
        self.assertEqual(m["years"], [int(self.d["read"][:4]) - 4, int(self.d["read"][:4]) - 3, int(self.d["read"][:4]) - 2])
        self.assertEqual(len(m["by_code"]), 78)
        for code, (filed, findings, repeated, last) in m["by_code"].items():
            self.assertRegex(code, r"^72\d{3}$")
            self.assertTrue(0 <= filed <= 3 and findings >= repeated >= 0, code)
            self.assertTrue(filed == 0 or last is not None, code)
        self.assertGreater(sum(1 for v in m["by_code"].values() if v[0]), 70, "most municipio governments are matched by name")
        import municipio_view   # the My municipio file carries the same figures
        mv = json.loads((ROOT / "site" / "data" / "spending_municipio.json").read_text(encoding="utf-8"))
        self.assertEqual(mv["years"]["audit"], [m["years"][0], m["years"][-1]])
        for row in mv["municipios"]:
            self.assertEqual(row["audit"], m["by_code"][str(row["id"])], row["name"])

    def test_no_body_is_named(self):
        text = OUT.read_text(encoding="utf-8")
        for word in ("auditee", "MUNICIP", "Municipality", "Municipio de", "Autoridad", "Departamento", "Universidad", "Inc.", "report_id", "GSAFAC"):
            self.assertNotIn(word, text)

    def test_about_half_of_the_findings_repeat(self):
        n, rep = self.d["totals"]["tally"][:2]
        self.assertGreater(n, 1000)
        self.assertTrue(0.3 < rep / n < 0.7)

    def test_the_file_is_what_the_cache_gives(self):
        idx = A.CACHE / "index.json"
        if not idx.exists() or not json.loads(idx.read_text(encoding="utf-8")).get("complete"):
            self.skipTest("no complete cache of the audits")
        self.assertEqual(A.build(check=True), 0)


@unittest.skipUnless(OUT.exists() and PAGE.exists(), "the page is not built")
class Page(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(OUT.read_text(encoding="utf-8"))
        self.html = PAGE.read_text(encoding="utf-8")
        self.section = re.search(r'<section class="block" id="findings">(.*?)</section>', self.html, re.S).group(1)

    def test_every_year_kind_agency_and_program_is_in_the_section(self):
        d = self.d
        self.assertEqual(len(re.findall(r'<tr class="af-y">', self.section)), sum(1 for r in d["by_year"] if r[1]))
        self.assertEqual(len(re.findall(r'<tr class="af-k">', self.section)), len(d["kinds"]))
        self.assertEqual(len(re.findall(r'<tr class="af-ag">', self.section)), len(d["agencies"]))
        self.assertEqual(re.findall(r'<td class="af-code" data-t="skip">([0-9A-Z.]+)</td>', self.section), [r[0] for r in d["listings"]])

    def test_the_headline_uses_only_years_that_have_mostly_arrived(self):
        done = [r for r in self.d["by_year"] if r[0] <= int(self.d["read"][:4]) - 2]
        n, rep = sum(r[3] for r in done), sum(r[4] for r in done)
        self.assertIn(f"Of the {n:,} findings, {rep:,} ({round(100 * rep / n)}%) were repeated.", self.section)

    def test_the_section_says_what_a_finding_is_not(self):
        self.assertIn("A finding is not a loss.", self.section)
        self.assertIn("No body is named.", self.section)
        self.assertIn("the source publishes no amount", self.section)


if __name__ == "__main__":
    unittest.main()
