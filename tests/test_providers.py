"""Tests for providers.py (health care providers by type, NPPES; decision 107, step 8).

The type rules, the stream extract and the privacy floor run on an invented NPPES file; the published file is checked for the floor and the dictionary;
with the local cache a rebuild must give it.
"""
import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import providers as P  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Types(unittest.TestCase):
    def test_primary_codes_map_to_their_type_in_order(self):
        for code, want in [("207Q00000X", "prov_primary_care"), ("207R00000X", "prov_primary_care"), ("207RC0000X", "prov_other_physicians"),
                           ("2084P0800X", "prov_psychiatrists"), ("2084N0400X", "prov_other_physicians"), ("1223G0001X", "prov_dentists"),
                           ("363LF0000X", "prov_np_pa"), ("363A00000X", "prov_np_pa"), ("163W00000X", None), ("103T00000X", "prov_mental_other"),
                           ("1041C0700X", "prov_mental_other"), ("183500000X", "prov_pharmacists"), ("", None)]:
            self.assertEqual(P.type_of(code), want, code)


class Extract(unittest.TestCase):
    def test_only_puerto_rico_individuals_and_no_names_reach_the_cache(self):
        head = ["NPI", "Entity Type Code", "Provider Last Name (Legal Name)", "NPI Deactivation Date", "NPI Reactivation Date", "Last Update Date",
                "Provider Business Practice Location Address City Name", "Provider Business Practice Location Address State Name", "Provider Business Practice Location Address Postal Code"]
        for k in range(1, 16):
            head += [f"Healthcare Provider Taxonomy Code_{k}", f"Healthcare Provider Primary Taxonomy Switch_{k}"]
        def row(npi, ent, name, state, city, zp, codes, prim):
            r = [npi, ent, name, "", "", "05/01/2024", city, state, zp]
            for k in range(15):
                r += [codes[k] if k < len(codes) else "", "Y" if k == prim else ("N" if k < len(codes) else "")]
            return r
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        w.writerow(row("1", "1", "SECRET ONE", "PR", "PONCE", "007161234", ["163W00000X", "207Q00000X"], 1))
        w.writerow(row("2", "2", "A HOSPITAL", "PR", "PONCE", "00716", ["282N00000X"], 0))
        w.writerow(row("3", "1", "SECRET TWO", "NY", "NEW YORK", "10001", ["207Q00000X"], 0))
        with tempfile.TemporaryDirectory() as tmp:
            zp = Path(tmp) / "NPPES_x.zip"
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr("npidata_pfile_1-2.csv", buf.getvalue())
            with mock.patch.object(P, "CACHE", Path(tmp)), mock.patch.object(P, "SMALL", Path(tmp) / "providers_pr.csv"), redirect_stdout(io.StringIO()):
                P.extract(zp)
                text = (Path(tmp) / "providers_pr.csv").read_text(encoding="utf-8")
        self.assertEqual(text.splitlines(), ["taxonomy,city,zip,last_update_year,active", "207Q00000X,PONCE,00716,2024,1"])
        self.assertNotIn("SECRET", text)


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not P.OUT.exists():
            raise unittest.SkipTest("providers_series.json not built")
        cls.d = json.loads(P.OUT.read_text(encoding="utf-8"))

    def test_no_count_from_1_to_9_and_the_island_is_at_least_the_sum(self):
        y = str(self.d["years"][0])
        for v in self.d["vars"]:
            vals = v["years"][y]
            self.assertTrue(all(x is None or x == 0 or x >= P.FLOOR for x in vals[:-1]), v["key"])
            self.assertGreaterEqual(vals[-1], sum(x for x in vals[:-1] if x))
        self.assertGreaterEqual(self.d["notes"]["placed_pct"], 99.0)
        self.assertNotIn("prov_nurses", [v["key"] for v in self.d["vars"]])

    def test_the_dictionary_quotes_the_range(self):
        ents = {e["id"]: e for e in json.loads((ROOT / "dictionary_src" / "entries" / "providers.json").read_text(encoding="utf-8"))}
        for k, r in self.d["notes"]["range"].items():
            self.assertIn(f"{r['registered']:,} registered", ents["providers." + k]["how_to_read"], k)


@unittest.skipUnless(P.SMALL.exists() and (ROOT / "cache" / "nonprofits" / "zcta_county_pr.json").exists(), "needs cache/nppes and cache/nonprofits")
class Rebuild(unittest.TestCase):
    def test_a_rebuild_from_the_cache_gives_the_published_file(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(P.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
