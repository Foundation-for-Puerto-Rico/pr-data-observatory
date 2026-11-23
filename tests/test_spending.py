"""Public spending schema (spending.py, docs/spending.md, HANDOFF decision 73): the record checks, the rules for adding up, and the tags on the
public-money series of economy_series.json (each breakdown adds up to its whole; a part keeps its whole's fiscal-year basis and stage)."""
import collections
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import spending as S  # noqa: E402

DATA = ROOT / "site" / "data"


def rec(**kw):
    r = {"municipio_fips": "72001", "fiscal_year": "2025", "fiscal_year_basis": "pr_jul_jun", "level": "state", "source_system": "ogp", "stage": "approved",
         "fund_origin": "general", "agency_or_entity": "081 Departamento de Educación", "function_category": "education", "concept_of_expense": "payroll",
         "recipient_type": "agency", "allocation_tier": "direct", "allocation_confidence": "high", "amount_usd": "1000", "retrieved_at": "2026-11-01",
         "source_url": "https://www.presupuestos.pr.gov/", "terms_of_use": "Public record"}
    r.update(kw)
    return {k: v for k, v in r.items() if v is not None}


class Records(unittest.TestCase):
    def test_a_good_record_passes(self):
        self.assertEqual(S.validate(rec()), [])

    def test_values_outside_the_schema_fail(self):
        for kw in ({"stage": "spent"}, {"fiscal_year_basis": "fy"}, {"municipio_fips": "72000x"}, {"amount_usd": "n/a"}, {"amount_usd": "nan"},
                   {"function_category": "roads"}, {"retrieved_at": "11/01/2026"}, {"source_url": "presupuestos.pr.gov"}, {"vendor_owner": "x"}):
            self.assertTrue(S.validate(rec(**kw)), kw)

    def test_required_fields(self):
        for k, (req, _) in S.FIELDS.items():
            if req:
                self.assertTrue(S.validate(rec(**{k: None})), k)

    def test_tier_rules(self):
        self.assertTrue(S.validate(rec(municipio_fips=None)), "direct needs a municipio")
        self.assertEqual(S.validate(rec(municipio_fips=None, allocation_tier="island_wide")), [])
        self.assertTrue(S.validate(rec(allocation_tier="island_wide")), "island-wide has no municipio")
        self.assertTrue(S.validate(rec(allocation_tier="apportioned")), "apportioned names a driver")
        self.assertEqual(S.validate(rec(allocation_tier="apportioned", allocation_driver="school enrollment FY2025", allocation_confidence="medium")), [])
        self.assertTrue(S.validate(rec(allocation_driver="school enrollment FY2025")), "only apportioned has a driver")
        for kw in ({"concept_of_expense": "capex"}, {"level": "federal_to_pr"}):
            self.assertTrue(S.validate(rec(allocation_tier="apportioned", allocation_driver="d", **kw)), f"never apportion {kw}")

    def test_per_capita_names_its_population(self):
        self.assertTrue(S.validate(rec(per_capita_usd="0.05")))
        self.assertEqual(S.validate(rec(per_capita_usd="0.05", population_basis="Census PEP V2025, 2025")), [])

    def test_dedup_group_must_exist(self):
        self.assertTrue(S.validate(rec(dedup_group="nope")))
        self.assertEqual(S.validate(rec(dedup_group="ogp_federal", fund_origin="federal")), [])


class AddingUp(unittest.TestCase):
    def test_never_mixes_fiscal_year_bases_or_stages(self):
        with self.assertRaises(ValueError):
            S.add_up([rec(), rec(fiscal_year_basis="federal_oct_sep")])
        with self.assertRaises(ValueError):
            S.add_up([rec(), rec(stage="actual")])

    def test_copies_are_left_out(self):
        a = rec(source_system="openfema", dedup_group="fema_pa", level="federal_to_pr", fund_origin="federal", stage="obligated")
        b = dict(a, source_system="cor3")
        c = dict(a, source_system="usaspending")
        self.assertEqual(S.add_up([a, b, c]), {("72001",): 1000.0})

    def test_island_wide_kept_and_apportioned_left_out_unless_asked(self):
        rs = [rec(), rec(municipio_fips=None, allocation_tier="island_wide", amount_usd="500"),
              rec(allocation_tier="apportioned", allocation_driver="d", amount_usd="7")]
        self.assertEqual(S.add_up(rs), {("72001",): 1000.0, ("",): 500.0})
        self.assertEqual(S.add_up(rs, tiers=("apportioned",)), {("72001",): 7.0})

    def test_every_dedup_group_has_an_authoritative_source_not_in_also_in(self):
        for g, d in S.DEDUP_GROUPS.items():
            self.assertNotIn(d["authoritative"], d["also_in"], g)


class SeriesTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))
        cls.vars = {v["key"]: v for v in cls.doc["vars"]}

    def test_tags_are_valid(self):
        self.assertEqual(S.check_tags(), [])

    def test_every_public_money_series_is_tagged_and_published_with_its_tags(self):
        pm = {k for k, v in self.vars.items() if v["group"] == "Public money" and not v.get("from")}
        self.assertEqual(pm, set(S.SERIES_TAGS))
        for k in pm:
            self.assertEqual(self.vars[k].get("spend"), S.SERIES_TAGS[k], f"{k}: run python spending.py --tag")

    def test_every_split_adds_up_to_its_whole_every_year(self):
        splits = collections.defaultdict(list)
        for k, t in S.SERIES_TAGS.items():
            if t.get("split"):
                splits[(t["part_of"], t["split"])].append(k)
        self.assertEqual(set(splits), {("fed_awards_total", "award_type"), ("fema_pa_obligated", "damage_category"), ("fac_expended", "channel"), ("fac_expended", "agency")})
        for (whole, split), parts in splits.items():
            W = self.vars[whole]["years"]
            for y, arr in W.items():
                for i, w in enumerate(arr):
                    if w is None:
                        continue
                    got = sum((self.vars[p]["years"].get(y) or [0] * len(arr))[i] or 0 for p in parts)
                    self.assertAlmostEqual(got, w, delta=max(2.0, abs(w) * 1e-6), msg=f"{whole} {split} {y} place {i}")

    def test_a_subset_never_exceeds_its_whole(self):
        for k, t in S.SERIES_TAGS.items():
            if t.get("part_of") and not t.get("split") and t.get("in_totals", True):
                W, P = self.vars[t["part_of"]]["years"], self.vars[k]["years"]
                for y, arr in P.items():
                    w = W.get(y)
                    if w and arr[-1] is not None and w[-1] is not None:
                        self.assertLessEqual(arr[-1], w[-1] * 1.0001, f"{k} {y} island")




class SourceManifest(unittest.TestCase):
    def test_authority_and_lineage_checks(self):
        import contract as C
        self.assertEqual(C.validate_sources({"a": {"authority": "authoritative", "lineage": {"en": "x"}}, "b": {}}), [])
        self.assertTrue(C.validate_sources({"a": {"authority": "primary"}}))
        self.assertTrue(C.validate_sources({"a": {"authority": "secondary"}}), "a secondary source says what it repeats")
        self.assertTrue(C.validate_sources({"a": {"lineage": "x"}}))

    def test_every_source_a_public_money_series_uses_has_a_manifest_entry(self):
        src = json.loads((ROOT / "dictionary_src" / "sources.json").read_text(encoding="utf-8"))
        for sid in {t["source_system"] for t in S.SERIES_TAGS.values()}:
            self.assertIn(src[sid].get("authority"), ("authoritative", "secondary"), sid)
            self.assertTrue(src[sid].get("lineage", {}).get("en"), sid)


if __name__ == "__main__":
    unittest.main()
