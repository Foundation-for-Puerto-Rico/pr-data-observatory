"""The Spanish of the data dictionary (dictionary_src/es/, its README): every record belongs to something real and has fingerprints, the summaries and the glossary
have one Spanish each (i18n_src/dictionary_plain.json, dictionary_src/glossary.json), stale Spanish is left out, and nothing held for Finance and Compliance review
(dictionary_src/es/held_for_review.json, i18n_src/held_for_review.json) reaches a published file."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ES = ROOT / "dictionary_src" / "es"
DATA = ROOT / "site" / "data"
HOLD = re.compile(r"(?i)\bLIHTC\b|\bCDBG")   # the WCRP Spanish is released (decision 51, 2026-10-19)
FP = re.compile(r"^[0-9a-f]{8}$")
sys.path.insert(0, str(ROOT))
import dictionary as d  # noqa: E402


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def page_files():
    return [DATA / "dictionary.json", DATA / "dictionary_list.json", DATA / "dictionary_list_es.json"] + sorted(DATA.glob("dictionary_detail_*.json")) + sorted(DATA.glob("glossary_*.json"))


@unittest.skipUnless(ES.exists(), "no Spanish dictionary yet")
class SpanishDictionary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = {e["id"]: e for f in (ROOT / "dictionary_src" / "entries").glob("*.json") for e in load(f)}
        cls.held = load(ES / "held_for_review.json")
        cls.held_plain = load(ROOT / "i18n_src" / "held_for_review.json")["dictionary_plain"]
        cls.full = load(DATA / "dictionary.json")

    def test_entries_belong_to_real_entries_and_have_fingerprints(self):
        for f in (ES / "entries").glob("*.json"):
            for k, rec in load(f).items():
                self.assertIn(k, self.entries, f"{f.name}: {k} is not an entry")
                fields = [x for x in rec if x != "_en"]
                self.assertTrue(fields, f"{f.name}: {k} has no Spanish")
                self.assertLessEqual(set(fields), set(d.ES_ENTRY_FIELDS), f"{f.name}: {k}: the summary's Spanish is in i18n_src/dictionary_plain.json, one system")
                for x in fields:
                    self.assertRegex(rec.get("_en", {}).get(x, ""), FP, f"{f.name}: {k}.{x} has no fingerprint")

    def test_one_spanish_glossary(self):
        self.assertFalse((ES / "glossary.json").exists(), "the glossary's Spanish is in dictionary_src/glossary.json (term_es, plain_es, hold_es)")

    def test_held_records_are_not_in_the_published_sources(self):
        released = {"fpr_wcrp"}   # the WCRP card names its CDBG-DR funds; its Spanish is released with the WCRP Spanish (decision 51)
        for f in list((ES / "entries").glob("*.json")) + [ES / n for n in ("labels.json", "sources.json", "groups.json")]:
            text = json.dumps({k: v for k, v in load(f).items() if k not in released}, ensure_ascii=False)
            for m in HOLD.finditer(text):
                self.fail(f"{f.relative_to(ROOT)} has federal grant text ({m.group(0)}); it belongs in held_for_review.json")
        es_entries = {k for f in (ES / "entries").glob("*.json") for k in load(f)}
        self.assertFalse(es_entries & (set(self.held["entries"]) | set(self.held_plain)), "a held entry's Spanish is in held_for_review.json only")
        self.assertFalse(set(load(ES / "sources.json")) & set(self.held["sources"]))
        self.assertFalse(set(load(ES / "groups.json")) & set(self.held["groups"]))
        self.assertFalse(set(load(ES / "labels.json")) & set(self.held["labels"]))
        for k in ("usaspending", "openfema"):
            self.assertIn(k, self.held["sources"], f"the {k} source card is held with Public money (2026-10-21)")
        self.assertIn("fpr_housing_2023", self.held["sources"], "the 2023 housing study card is held with Table 10")
        self.assertNotIn("fpr_wcrp", self.held["sources"], "the WCRP card's Spanish is released (decision 51)")
        self.assertIn("fpr_wcrp", load(ES / "sources.json"))
        self.assertFalse([k for k in self.held["entries"] if "wcrp" in k], "the WCRP entries' Spanish is released (decision 51)")
        self.assertIn("public-money", self.held["groups"])
        for k in self.held_plain:
            if k.startswith(("economy.fed_", "economy.fema_pa_", "housing.fema_ia_")):
                self.assertIn(k, self.held["entries"], f"{k}: its Spanish name and how to read it are held with its summary")

    def test_nothing_held_is_in_a_published_file(self):
        """Every held Spanish text (longer than a short label) is absent from the dictionary's published files, and every held entry is marked."""
        texts = [v for k in ("entries", "sources", "groups") for rec in self.held[k].values() for f, v in rec.items() if f != "_en" and isinstance(v, str)]
        texts += [g for rec in self.held["groups"].values() for g in (rec.get("groups") or {}).values()]
        texts += [r["es"] for r in self.held_plain.values()]
        texts = [t for t in texts if len(t) > 40]
        self.assertGreater(len(texts), 40)
        published = {p.name: p.read_text(encoding="utf-8") for p in page_files()}
        for t in texts:
            for name, s in published.items():
                self.assertNotIn(t, s, f"{name} publishes held Spanish: {t[:60]}…")
        by_id = {e["id"]: e for e in self.full["entries"]}
        for k in set(self.held["entries"]) | set(self.held_plain):
            e = by_id[k]
            self.assertTrue(e.get("hold_es"), k)
            self.assertNotIn("name_es", e, k)
            self.assertNotIn("how_to_read_es", e, k)
            if k in self.held_plain:
                self.assertNotIn("plain_es", e, k)
        for sid in ("usaspending", "openfema"):
            self.assertFalse([f for f in self.full["sources"][sid] if f.endswith("_es") and f != "name_es"], f"no Spanish on the {sid} card")
        es_list = load(DATA / "dictionary_list_es.json")
        self.assertFalse({"usaspending", "openfema", "fpr_housing_2023"} & set(es_list["sources"]))
        self.assertEqual(set(es_list["sources"]["fpr_wcrp"]), set(d.ES_SOURCE_FIELDS), "the WCRP card is published in Spanish, every field current")
        self.assertNotIn("public-money", es_list["domain_info"])
        for k in ("boundaries.wcrp_comunidades", "boundaries.wcrp_estado", "boundaries.wcrp_subrecipiente", "boundaries.wcrp_ubicacion"):
            self.assertTrue(es_list["names"].get(k) and by_id[k].get("how_to_read_es"), f"{k}: released, so its Spanish is published")
        self.assertNotIn("summary_es", self.full["domain_info"].get("public-money", {}))
        self.assertNotIn("groups_es", self.full["domain_info"].get("public-money", {}))
        self.assertFalse(set(self.held["labels"]) & set(self.full["labels_es"]), "no held label is published")

    def test_build_holds_by_what_the_text_belongs_to(self):
        """spanish() on a small dictionary: a held entry, source card, area and label stay English, whatever their words."""
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "entries").mkdir()
            merged = {"a.x": {"name": "Jobs", "how_to_read": "Read it.", "unit": "people", "group": "G"}, "a.y": {"name": "Grants", "how_to_read": "Read that.", "unit": "dollars", "group": "G"}}
            sources = {"s1": {"access": "API."}, "s2": {"access": "Other API."}}
            info = {"a": {"summary": "Area.", "groups": {"G": "Group."}}, "b": {"summary": "Other area."}}
            fp = d.fingerprint
            (tmp / "entries" / "x.json").write_text(json.dumps({k: {"name": "N", "how_to_read": "L", "_en": {"name": fp(v["name"]), "how_to_read": fp(v["how_to_read"])}} for k, v in merged.items()}), encoding="utf-8")
            (tmp / "labels.json").write_text(json.dumps({"people": "personas", "dollars": "dólares", "G": "Grupo"}), encoding="utf-8")
            (tmp / "sources.json").write_text(json.dumps({s: {"access": "A", "_en": {"access": fp(v["access"])}} for s, v in sources.items()}), encoding="utf-8")
            (tmp / "groups.json").write_text(json.dumps({k: {"summary": "R", "groups": {"G": "GG"} if k == "a" else {}, "_en": {"summary": fp(v["summary"]), **({"groups.G": fp("Group.")} if k == "a" else {})}} for k, v in info.items()}), encoding="utf-8")
            held = tmp / "held_for_review.json"
            held.write_text(json.dumps({"entries": {"a.y": {}}, "sources": {"s2": {}}, "groups": {"b": {}}, "labels": {}}), encoding="utf-8")
            old = (d.ES, d.HELD_ES, d.HELD_REVIEW)
            d.ES, d.HELD_ES, d.HELD_REVIEW = tmp, held, tmp / "none.json"
            try:
                es, stale = d.spanish(merged, sources, info, quiet=True)
            finally:
                d.ES, d.HELD_ES, d.HELD_REVIEW = old
            self.assertEqual(stale, [])
            self.assertEqual(set(es["entries"]), {"a.x"})
            self.assertEqual(es["held"], {"a.y"})
            self.assertEqual(set(es["sources"]), {"s1"})
            self.assertEqual(set(es["domain_info"]), {"a"})
            self.assertEqual(es["labels"], {"people": "personas", "G": "Grupo"}, "a label used only by held entries is not published")
            out = [{"id": k, **v} for k, v in merged.items()]
            dom = d.add_spanish(out, sources, info, es)
            self.assertEqual((out[0].get("name_es"), out[1].get("name_es"), out[1].get("hold_es")), ("N", None, True))
            self.assertEqual((sources["s1"].get("access_es"), sources["s2"].get("access_es")), ("A", None))
            self.assertEqual((dom["a"].get("summary_es"), dom["a"].get("groups_es"), dom["b"].get("summary_es")), ("R", {"G": "GG"}, None))
        finally:
            shutil.rmtree(tmp)

    def test_build_leaves_out_stale_spanish(self):
        rec = {"how_to_read": "Texto.", "_en": {"how_to_read": d.fingerprint("Old English.")}}
        stale = []
        self.assertEqual(d._es_take(rec, {"how_to_read": "New English."}, ["how_to_read"], "x", stale), {})
        self.assertEqual(stale, ["x.how_to_read"])
        rec["_en"]["how_to_read"] = d.fingerprint("New English.")
        self.assertEqual(d._es_take(rec, {"how_to_read": "New English."}, ["how_to_read"], "x", []), {"how_to_read": "Texto."})

    def test_published_spanish_is_what_the_sources_give(self):
        """The published Spanish is what dictionary_src/es/ gives for today's English (a stale field is left out; python dictionary.py --es lists it)."""
        info = {k: {kk: vv for kk, vv in v.items() if not kk.endswith("_es")} for k, v in self.full["domain_info"].items()}
        es, _ = d.spanish({e["id"]: e for e in self.full["entries"]}, self.full["sources"], info, quiet=True)
        for e in self.full["entries"]:
            for f in d.ES_ENTRY_FIELDS:
                self.assertEqual(e.get(f + "_es"), es["entries"].get(e["id"], {}).get(f), f"{e['id']}.{f}: rebuild with python dictionary.py")
        self.assertEqual(self.full["labels_es"], es["labels"])


if __name__ == "__main__":
    unittest.main()
