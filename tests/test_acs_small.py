"""Tests for acs_small.py: the byte-range reader of the Census Bureau's ACS table files.

  python -m unittest discover -s tests -v

A small invented file, sorted by GEO_ID like the real ones, is served from memory with the same two calls the web reader has (.size and
.read(start, n)). The search must give the same answer as reading the whole file, for every prefix, with a tiny chunk (many search steps),
long rows, Windows line endings and no final newline. No network is used.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import acs_small  # noqa: E402

HEADER = "GEO_ID|B01003_E001|B01003_M001"


class MemFile:
    """What RangeFile offers, over bytes held in memory; counts the bytes it hands out."""

    def __init__(self, data):
        self.data, self.size, self.served, self.calls = data, len(data), 0, 0

    def read(self, start, n):
        out = self.data[start:start + n]
        self.served += len(out)
        self.calls += 1
        return out


def make_rows():
    """GEO_IDs in the order the Census Bureau sorts them (plain string order): nation, state, counties, subdivisions, tracts, block groups, places."""
    ids = ["0100000US", "0400000US01", "0400000US72"]
    ids += [f"0500000US72{c:03d}" for c in (1, 3, 5)]
    ids += [f"0500000US73{c:03d}" for c in range(1, 40)]
    ids += ["0600000US7200100000", "0600000US7200113645", "0600000US7200311111"]
    ids += [f"1400000US01{c:03d}{t:06d}" for c in range(1, 30) for t in range(1, 30)]
    ids += ["1400000US72001956400", "1400000US72001956500", "1400000US72003956600"]
    ids += ["1500000US720019564001", "1500000US720019564002", "1500000US720019565001", "1500000US720039566001"]
    ids += [f"1500000US73{c:03d}{t:06d}{b}" for c in range(1, 5) for t in range(1, 40) for b in (1, 2)]
    ids += [f"8600000US{z:05d}" for z in range(600, 640)]
    return sorted(ids)


def build(ids, eol="\n", final_newline=True, extra_columns=0):
    cols = HEADER + "".join(f"|B01003_E{i:03d}|B01003_M{i:03d}" for i in range(2, 2 + extra_columns))
    lines = [cols]
    for n, g in enumerate(ids):
        vals = [str(1000 + n), str(50 + n % 7)] + [str(n * i) for i in range(2, 2 + extra_columns) for _ in (0, 1)]
        lines.append("|".join([g] + vals))
    body = eol.join(lines)
    return (body + (eol if final_newline else "")).encode()


def brute(data, prefix):
    """The lines whose GEO_ID starts with prefix, by reading everything."""
    lines = data.decode().replace("\r\n", "\n").split("\n")[1:]
    return [l.encode() for l in lines if l and l.split("|")[0].startswith(prefix.decode())]


class Search(unittest.TestCase):
    def setUp(self):
        self.ids = make_rows()

    def check_all_prefixes(self, data, chunk):
        with mock.patch.object(acs_small, "PROBE", chunk), mock.patch.object(acs_small, "SPAN", 2 * chunk), mock.patch.object(acs_small, "READ", 4 * chunk):
            f = MemFile(data)
            cols, start = acs_small.header_of(f)
            self.assertEqual(cols[0], "GEO_ID")
            prefixes = {b"", b"0", b"0100000US", b"0400000US72", b"0500000US72", b"0500000US73", b"0600000US72", b"1400000US72", b"1400000US01", b"1500000US72", b"1500000US73001", b"8600000US", b"8600000US00610", b"9", b"~", b"0500000US72001", b"0500000US72002"}
            prefixes |= {g.encode()[:k] for g in self.ids[::17] for k in (3, 9, 11)}
            for p in sorted(prefixes):
                self.assertEqual(acs_small.read_prefix(f, p, start), brute(data, p), f"prefix {p!r}, chunk {chunk}")

    def test_finds_exactly_the_rows_with_the_prefix_for_every_prefix(self):
        for chunk in (8, 16, 64, 300, acs_small.PROBE):
            self.check_all_prefixes(build(self.ids), chunk)

    def test_windows_line_endings_and_no_final_newline(self):
        self.check_all_prefixes(build(self.ids, eol="\r\n"), 64)
        self.check_all_prefixes(build(self.ids, final_newline=False), 64)
        self.check_all_prefixes(build(self.ids, eol="\r\n", final_newline=False), 300)

    def test_rows_longer_than_the_chunk(self):
        self.check_all_prefixes(build(self.ids, extra_columns=40), 64)     # each row is several hundred bytes

    def test_reads_far_less_than_the_file(self):
        """On a file of a few MB (the real ones are 18 MB) the three rows cost a few dozen small reads."""
        data = build(make_rows() + [f"2500000US{n:05d}" for n in range(100000)] + [f"9700000US{n:05d}" for n in range(100000)])
        self.assertGreater(len(data), 4_000_000)
        f = MemFile(data)
        _, start = acs_small.header_of(f)
        rows = acs_small.read_prefix(f, b"1400000US72", start)
        self.assertEqual(len(rows), 3)
        self.assertLess(f.served, len(data) / 20, f"read {f.served} of {len(data)} bytes")
        self.assertLess(f.calls, 60)

    def test_a_file_that_is_not_sorted_is_refused(self):
        ids = ["0400000US72", "0500000US72003", "0500000US72001", "0500000US72005"]
        f = MemFile(build(ids))
        _, start = acs_small.header_of(f)
        with self.assertRaises(ValueError):
            acs_small.read_prefix(f, b"0500000US72", start)

    def test_a_file_with_no_data_rows_is_refused(self):
        with self.assertRaises(ValueError):
            acs_small.header_of(MemFile(HEADER.encode()))


class Values(unittest.TestCase):
    def test_null_codes_are_none_not_zero(self):
        for code in ("-666666666", "-555555555", "-333333333", "-222222222", "-999999999", "", "N", "(X)"):
            self.assertIsNone(acs_small.estimate(code), code)
        self.assertEqual(acs_small.estimate("0"), 0)
        self.assertEqual(acs_small.estimate("2.45"), 2.45)
        self.assertEqual(acs_small.estimate("3234309.0"), 3234309)
        self.assertIsNone(acs_small.margin("-555555555"))
        self.assertIsNone(acs_small.margin("-1"))
        self.assertEqual(acs_small.margin("0"), 0)
        self.assertEqual(acs_small.margin("1731"), 1731)

    def test_rows_are_keyed_by_the_geoid_the_twin_uses(self):
        cols = HEADER.split("|")
        cases = {"tract": ("1400000US72001956400", "72001956400"), "block-group": ("1500000US720019564001", "720019564001"),
                 "barrio": ("0600000US7200113645", "7200113645"), "municipio": ("0500000US72001", "72001"), "island": ("0400000US72", "72")}
        for level, (geo_id, geoid) in cases.items():
            out = acs_small.parse_rows(cols, [f"{geo_id}|1234|-555555555".encode()], level)
            self.assertEqual(out, {geoid: {"B01003_001": [1234, None]}}, level)

    def test_every_cell_gets_its_own_margin(self):
        cols = ["GEO_ID", "B25024_E001", "B25024_M001", "B25024_E002", "B25024_M002"]
        out = acs_small.parse_rows(cols, [b"1400000US72001956400|100|10|-666666666|-222222222"], "tract")
        self.assertEqual(out["72001956400"], {"B25024_001": [100, 10], "B25024_002": [None, None]})

    def test_a_row_of_the_wrong_width_or_an_unknown_column_is_refused(self):
        with self.assertRaises(ValueError):
            acs_small.parse_rows(HEADER.split("|"), [b"1400000US72001956400|1"], "tract")
        with self.assertRaises(ValueError):
            acs_small.parse_rows(["GEO_ID", "NAME"], [b"x|y"], "tract")


class ReadTable(unittest.TestCase):
    def test_reads_every_level_caches_it_and_drops_ids_that_are_not_units(self):
        ids = make_rows()
        data = build(ids)
        known = {"barrio": {"7200113645", "7200311111"}, "tract": {"72001956400", "72001956500", "72003956600"}}
        with tempfile.TemporaryDirectory() as tmp:
            f = MemFile(data)
            r = acs_small.read_table("b01003", 2024, ["island", "barrio", "tract", "block-group"], known=known, f=f, cache_dir=tmp)
            self.assertEqual((r["table"], r["vintage"]), ("B01003", 2024))
            self.assertEqual(sorted(r["levels"]["barrio"]), ["7200113645", "7200311111"])
            self.assertEqual(r["dropped"], {"barrio": 1, "tract": 0})
            self.assertEqual(r["match"]["barrio"], [2, 3])
            self.assertEqual(len(r["levels"]["block-group"]), 4)
            self.assertEqual(list(r["levels"]["island"]), ["72"])
            served = f.served
            again = acs_small.read_table("B01003", 2024, ["island", "barrio", "tract", "block-group"], known=known, f=MemFile(b"not used"), cache_dir=tmp)
            self.assertEqual(again["levels"], r["levels"])                  # the second time nothing is read
            self.assertGreater(served, 0)
            cached = json.loads((Path(tmp) / "2024" / "B01003_barrio.json").read_text(encoding="utf-8"))
            self.assertEqual(len(cached["rows"]), 3, "the cache keeps every row; the crosswalk filter is applied on reading")

    def test_a_vintage_before_the_table_based_files_is_refused_with_the_reason(self):
        with self.assertRaises(ValueError) as cm:
            acs_small.read_table("B01003", 2020, ["tract"], known=None, f=MemFile(build(make_rows())), cache_dir=tempfile.gettempdir())
        self.assertIn("table-based files start with the 2021 vintage", str(cm.exception))

    def test_unknown_level_is_refused(self):
        with self.assertRaises(ValueError):
            acs_small.read_table("B01003", 2024, ["county"], known=None, f=MemFile(build(make_rows())), cache_dir=tempfile.gettempdir())


class WebReader(unittest.TestCase):
    """RangeFile with an invented web session: it must insist on byte ranges and on a 206 answer."""

    class Resp:
        def __init__(self, status=200, headers=None, content=b""):
            self.status_code, self.headers, self.content = status, headers or {}, content

        def raise_for_status(self):
            if self.status_code >= 400:
                raise acs_small.requests.HTTPError(str(self.status_code))

    class Session:
        def __init__(self, head, get):
            self.head_r, self.get_r, self.requested = head, get, []

        def head(self, *a, **k):
            return self.head_r

        def get(self, url, headers=None, **k):
            self.requested.append(headers["Range"])
            return self.get_r

    def test_asks_for_the_range_and_accepts_206(self):
        s = self.Session(self.Resp(200, {"Accept-Ranges": "bytes", "Content-Length": "100"}), self.Resp(206, content=b"abc"))
        f = acs_small.RangeFile("http://x/file.dat", s)
        self.assertEqual(f.size, 100)
        self.assertEqual(f.read(10, 3), b"abc")
        self.assertEqual(s.requested, ["bytes=10-12"])
        self.assertEqual(f.read(98, 50), b"abc")
        self.assertEqual(s.requested[-1], "bytes=98-99")
        self.assertEqual(f.read(100, 5), b"")

    def test_refuses_a_server_without_byte_ranges(self):
        f = acs_small.RangeFile("http://x/file.dat", self.Session(self.Resp(200, {"Content-Length": "100"}), self.Resp(206)))
        with self.assertRaises(RuntimeError):
            f.size

    def test_a_full_file_answer_to_a_range_request_is_an_error(self):
        s = self.Session(self.Resp(200, {"Accept-Ranges": "bytes", "Content-Length": "100"}), self.Resp(200, content=b"x" * 100))
        f = acs_small.RangeFile("http://x/file.dat", s)
        with mock.patch.object(acs_small.time, "sleep"):
            with self.assertRaises(RuntimeError):
                f.read(0, 10)


class Crosswalk(unittest.TestCase):
    def test_ids_come_from_the_crosswalk_when_it_exists(self):
        p = Path(__file__).resolve().parent.parent / "site" / "data" / "geo" / "crosswalk.json"
        if not p.exists():
            self.skipTest("site/data/geo/crosswalk.json has not been built")
        ids = acs_small.crosswalk_ids(p)
        self.assertEqual({lv: len(v) for lv, v in ids.items()}, {"island": 1, "region": 7, "municipio": 78, "barrio": 901, "tract": 981, "block-group": 2555})
        self.assertIsNone(acs_small.crosswalk_ids(Path(tempfile.gettempdir()) / "no-such-crosswalk.json"))


if __name__ == "__main__":
    unittest.main()
