"""Domain tags on dictionary entries: dictionary.validate must reject tags that are not in the registry."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dictionary  # noqa: E402

SOURCES = {"census_tiger": {}}
IDS = {"housing", "economy", "economy.visitor-economy", "system.docs"}
ENTRY = {"id": "x.rent", "name": "Rent", "domain": "housing", "domains": ["housing", "economy"], "group": "G", "kind": "variable",
         "plain": "Rent.", "definition": "Rent paid.", "unit": "$", "value_type": "level", "geography": "78 municipalities",
         "coverage": {"timeline": "annual", "first": 2010, "last": 2020}, "method": "m", "sources": ["census_tiger"],
         "where": {"files": ["municipalities.json:*"]}, "added": "2026-10-05", "_file": "t.json"}
INV = {"municipalities.json": {"*"}}


def run(**changes):
    e = copy.deepcopy(ENTRY)
    e.update(changes)
    return dictionary.validate([e], SOURCES, {}, INV, None, IDS)


def msgs(ps):
    return " | ".join(p[3] for p in ps if p[0] == "error")


class DomainTagTests(unittest.TestCase):
    def test_clean_entry_passes(self):
        self.assertEqual(msgs(run()), "")

    def test_primary_domain_must_be_in_registry(self):
        self.assertIn("not in the registry", msgs(run(domain="Housing", domains=["Housing"])))

    def test_secondary_domain_must_be_in_registry(self):
        self.assertIn("lists 'nowhere'", msgs(run(domains=["housing", "nowhere"])))

    def test_domains_must_start_with_primary(self):
        self.assertIn("must start with the primary domain", msgs(run(domains=["economy", "housing"])))

    def test_domains_cannot_repeat(self):
        self.assertIn("twice", msgs(run(domains=["housing", "housing"])))

    def test_domains_is_required(self):
        e = copy.deepcopy(ENTRY)
        del e["domains"]
        self.assertIn("missing required field 'domains'", msgs(dictionary.validate([e], SOURCES, {}, INV, None, IDS)))

    def test_in_domain_includes_sub_domains_and_secondary_tags(self):
        e = {"domain": "economy.visitor-economy", "domains": ["economy.visitor-economy", "environment.land"]}
        self.assertTrue(dictionary.in_domain(e, "economy"))
        self.assertTrue(dictionary.in_domain(e, "environment.land"))
        self.assertTrue(dictionary.in_domain(e, "environment"))       # a parent domain includes entries tagged with its sub-domains
        self.assertFalse(dictionary.in_domain(e, "hazards"))          # hazards is a domain of its own since decision 81, not under environment
        self.assertFalse(dictionary.in_domain({"domain": "hazards", "domains": ["hazards"]}, "environment"))
        self.assertFalse(dictionary.in_domain(e, "housing"))
        self.assertFalse(dictionary.in_domain({"domain": "economy", "domains": ["economy"]}, "economy.visitor-economy"))   # but not the other way round


class NewDomainTests(unittest.TestCase):
    """Acceptance test from the brief: a new domain is one object in the registry; nothing else lists domains."""

    def test_adding_a_domain_needs_only_a_registry_object(self):
        import contract
        reg = contract.load_registry()
        before = dictionary.domain_order(reg)
        toy = {"id": "toy-domain", "parent": None, "order": 65, "name": {"es": "Dominio de prueba", "en": "Toy domain"},
               "description": {"es": "Solo para la prueba.", "en": "For the test only."}, "icon": "science", "accent": "--fpr-blue", "headline": None,
               "examples": {"es": ["¿Qué hay?"], "en": ["What is there?"]}, "status": "planned", "system": False}
        reg2 = {**reg, "domains": reg["domains"] + [toy]}
        self.assertEqual([p for p in contract.validate_registry(reg2, None, contract.accent_tokens()) if p[0] == "error"], [])
        after = dictionary.domain_order(reg2)
        self.assertEqual(len(after), len(before) + 1)
        self.assertLess(after.index("health"), after.index("toy-domain"))                 # ordered by the registry's order field
        self.assertLess(after.index("toy-domain"), after.index("environment"))
        ids = set(contract.domains_by_id(reg2))
        e = dict(ENTRY, domain="toy-domain", domains=["toy-domain", "housing"])
        self.assertEqual(msgs(dictionary.validate([e], SOURCES, {}, INV, None, ids)), "")
        self.assertTrue(dictionary.in_domain(e, "toy-domain") and dictionary.in_domain(e, "housing"))


if __name__ == "__main__":
    unittest.main()
