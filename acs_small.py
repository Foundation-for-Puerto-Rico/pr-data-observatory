"""Small-area American Community Survey reader for the PR Data Observatory (plan item 4).

Reads Puerto Rico's rows of one ACS 5-year table, for any of: the island, the 78 municipios, the barrios (Census county subdivisions),
the census tracts and the block groups, from the Census Bureau's table-based summary files. Each file holds the whole nation (about
18 MB a table), sorted by GEO_ID, and the server answers byte-range requests, so the rows of one level are found by binary search
and only they (0.05-0.4 MB) are downloaded.

    python acs_small.py B25077                              # latest vintage, every level; cached under cache/acs_small
    python acs_small.py B25077 --vintage 2023 --levels tract,barrio
    python acs_small.py --check                             # live check: the municipio rows must equal the ones housing_series.py holds

    import acs_small
    r = acs_small.read_table("B25077", levels=["tract", "barrio"])
    r["levels"]["tract"]["72001956400"]["B25077_001"]     # [estimate, margin of error at the 90% level]; None when the Census Bureau gives no value

Rules that every use of these numbers must keep (docs/geography.md, "Small-area estimates"):
  - A null is "not computable or not published", never zero. Estimates and margins come as the Census Bureau gives them.
  - Margins are 90% margins of error. Do not add or average margins; do not sum medians or rates.
  - Barrios are read from the Census Bureau's own barrio rows. They do not nest in tracts: do not rebuild them from tracts.
  - The five-year windows that share years are not independent.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "acs_small"
DATA = ROOT / "site" / "data"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)", "Accept-Encoding": "identity"}   # identity: byte ranges address the file as stored
BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/"

# level -> (GEO_ID prefix of Puerto Rico's rows, number of digits in the GEOID the observatory uses)
LEVELS = {
    "island": ("0400000US72", 2),
    "municipio": ("0500000US72", 5),
    "barrio": ("0600000US72", 10),
    "tract": ("1400000US72", 11),
    "block-group": ("1500000US72", 12),
}
PROBE = 4 * 1024           # bytes read at each step of the search: a row is far shorter, and the read doubles when it is not
SPAN = 32 * 1024           # the search stops when its window is this small and reads on from there
READ = 64 * 1024           # the largest block read when streaming rows (reads start at PROBE and double)
NULL_AT_OR_BELOW = -222222222        # the Census Bureau's codes for "not computable", "no sample", "open-ended median" and the like
CELL_RE = re.compile(r"^([A-Z0-9]+)_([EM])(\d+)$")
FIRST_VINTAGE = 2021               # the first 5-year vintage published as table-based files (2019 and 2020 answer 404); earlier windows are per-sequence files this reader does not read


def log(*a):
    print(*a, flush=True)


# ── A file read by byte ranges ───────────────────────────────────────────────

class RangeFile:
    """A file on a web server, read with HTTP byte ranges: .size and .read(start, n)."""

    def __init__(self, url, session=None):
        self.url, self.session, self._size, self.calls, self.downloaded = url, session or requests.Session(), None, 0, 0

    @property
    def size(self):
        if self._size is None:
            r = self.session.head(self.url, headers=UA, allow_redirects=True, timeout=60)
            r.raise_for_status()
            if r.headers.get("Accept-Ranges", "").lower() != "bytes":
                raise RuntimeError(f"{self.url}: the server does not accept byte ranges")
            self._size = int(r.headers["Content-Length"])
        return self._size

    def read(self, start, n):
        end = min(start + n, self.size) - 1
        if end < start:
            return b""
        for attempt in range(4):
            try:
                self.calls += 1
                r = self.session.get(self.url, headers={**UA, "Range": f"bytes={start}-{end}"}, timeout=120)
                if r.status_code != 206:
                    raise RuntimeError(f"{self.url}: byte range answered {r.status_code}, not 206")
                self.downloaded += len(r.content)
                return r.content
            except (requests.RequestException, RuntimeError):
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))


# ── Finding rows by GEO_ID in a sorted file ──────────────────────────────────

def _key(line):
    return line.split(b"|", 1)[0]


def _first_line_after(f, pos):
    """(offset, line) of the first complete line that starts after the first newline at or beyond pos; None when there is none."""
    n = PROBE
    while True:
        data = f.read(pos, n)
        i = data.find(b"\n")
        reached_end = pos + len(data) >= f.size
        if i < 0:
            if reached_end:
                return None
            n *= 2
            continue
        j = data.find(b"\n", i + 1)
        if j < 0:
            if reached_end:
                line = data[i + 1:]
                return (pos + i + 1, line.rstrip(b"\r")) if line else None
            n *= 2
            continue
        return pos + i + 1, data[i + 1:j].rstrip(b"\r")


def iter_lines(f, offset):
    """(offset, line) for every line from `offset` (the start of a line) to the end of the file, read in chunks as needed."""
    pos, buf, off, n = offset, b"", offset, PROBE
    while True:
        if pos < f.size:
            chunk = f.read(pos, n)
            if not chunk:
                raise OSError(f"empty answer at byte {pos}")
            pos += len(chunk)
            buf += chunk
            n = min(2 * n, READ)
        eof = pos >= f.size
        start = 0
        while True:
            j = buf.find(b"\n", start)
            if j < 0:
                break
            yield off + start, buf[start:j].rstrip(b"\r")
            start = j + 1
        buf, off = buf[start:], off + start
        if eof:
            if buf:
                yield off, buf.rstrip(b"\r")
            return


def header_of(f):
    """(column names, offset of the first data row)."""
    n = PROBE
    while True:
        data = f.read(0, n)
        i = data.find(b"\n")
        if i >= 0:
            return data[:i].rstrip(b"\r").decode("utf-8").split("|"), i + 1
        if len(data) >= f.size:
            raise ValueError("the file has no data rows")
        n *= 2


def lower_bound(f, prefix, data_start):
    """Offset of the first line whose GEO_ID is at or after `prefix` (bytes); the file size when there is none."""
    lo, hi = data_start, f.size         # invariant: every line that starts before lo has a GEO_ID below the prefix
    while hi - lo > SPAN:
        mid = (lo + hi) // 2
        got = _first_line_after(f, mid)
        if got is None:
            hi = mid
            continue
        start, line = got
        if _key(line) < prefix:
            lo = start
        else:
            hi = mid
    for off, line in iter_lines(f, lo):
        if _key(line) >= prefix:
            return off
    return f.size


def read_prefix(f, prefix, data_start):
    """The data lines whose GEO_ID starts with `prefix` (bytes). Stops at the first line beyond them; fails if the file is not sorted."""
    rows, last = [], None
    for _, line in iter_lines(f, lower_bound(f, prefix, data_start)):
        k = _key(line)
        if last is not None and k < last:
            raise ValueError(f"the file is not sorted by GEO_ID ({k!r} after {last!r}): the byte-range search cannot be used")
        last = k
        if not k.startswith(prefix):
            break
        rows.append(line)
    return rows


# ── Values ───────────────────────────────────────────────────────────────────

def estimate(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x <= NULL_AT_OR_BELOW:
        return None
    return int(x) if x == int(x) else x


def margin(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x < 0:
        return None
    return int(x) if x == int(x) else x


def parse_rows(columns, lines, level):
    """{geoid: {"B25077_001": [estimate, margin]}} from data lines."""
    digits = LEVELS[level][1]
    cells = []                          # (index of the estimate, index of its margin or None, cell id)
    idx = {}
    for i, c in enumerate(columns[1:], start=1):
        m = CELL_RE.match(c)
        if not m:
            raise ValueError(f"unexpected column {c!r}")
        idx[(m.group(1), m.group(2), m.group(3))] = i
    for (tbl, kind, n), i in idx.items():
        if kind == "E":
            cells.append((i, idx.get((tbl, "M", n)), f"{tbl}_{n}"))
    out = {}
    for line in lines:
        f = line.decode("utf-8").split("|")
        if len(f) != len(columns):
            raise ValueError(f"a row has {len(f)} values, the header {len(columns)}")
        out[f[0][-digits:]] = {cid: [estimate(f[e]), margin(f[m]) if m is not None else None] for e, m, cid in cells}
    return out


# ── Tables ───────────────────────────────────────────────────────────────────

def url_for(table, vintage):
    return f"{BASE}{vintage}/table-based-SF/data/5YRData/acsdt5y{vintage}-{table.lower()}.dat"


def latest_vintage(start=2024):
    """The last ACS 5-year vintage published as a table-based file, found with HEAD requests (the same rule housing_series.py uses)."""
    def exists(y):
        try:
            return requests.head(url_for("b01003", y), headers=UA, timeout=60, allow_redirects=True).status_code == 200
        except requests.RequestException:
            return False
    y = start
    while exists(y + 1):
        y += 1
    return y


def crosswalk_ids(path=None):
    """{level: set of ids} from site/data/geo/crosswalk.json, or None when it has not been built."""
    p = Path(path or DATA / "geo" / "crosswalk.json")
    if not p.exists():
        return None
    cw = json.loads(p.read_text(encoding="utf-8"))
    return {lv: {r[0] for r in rows} for lv, rows in cw["units"].items()}


def read_table(table, vintage=None, levels=None, refresh=False, known="crosswalk", f=None, cache_dir=None):
    """Puerto Rico's rows of one ACS 5-year table.

    Returns {"table", "vintage", "columns", "levels": {level: {geoid: {cell: [estimate, margin]}}}, "dropped": {level: n}, "match": {level: [found in the crosswalk, total]}}.
    Rows whose id is not a unit of the crosswalk are dropped and counted (the 38 offshore "not defined" barrios have no land and no residents).
    """
    table = table.upper()
    vintage = vintage or latest_vintage()
    if vintage < FIRST_VINTAGE:
        raise ValueError(f"ACS {vintage}: table-based files start with the {FIRST_VINTAGE} vintage; earlier five-year windows are per-sequence files (housing_series.py reads those for municipios)")
    levels = list(levels or LEVELS)
    for lv in levels:
        if lv not in LEVELS:
            raise ValueError(f"unknown level {lv!r}; choose from {list(LEVELS)}")
    known = crosswalk_ids() if known == "crosswalk" else known
    cdir = Path(cache_dir or CACHE) / str(vintage)
    out = {"table": table, "vintage": vintage, "columns": None, "levels": {}, "dropped": {}, "match": {}}
    file = f
    for lv in levels:
        path = cdir / f"{table}_{lv}.json"
        if path.exists() and not refresh:
            cached = json.loads(path.read_text(encoding="utf-8"))
            rows, out["columns"] = cached["rows"], cached["columns"]
        else:
            file = file or RangeFile(url_for(table, vintage))
            columns, start = header_of(file)
            lines = read_prefix(file, LEVELS[lv][0].encode(), start)
            rows, out["columns"] = parse_rows(columns, lines, lv), columns
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"vintage": vintage, "table": table, "level": lv, "columns": columns, "rows": rows}, separators=(",", ":")), encoding="utf-8")
        if known and known.get(lv):
            keep = {g: v for g, v in rows.items() if g in known[lv]}
            out["dropped"][lv] = len(rows) - len(keep)
            out["match"][lv] = [len(keep), len(rows)]
            rows = keep
        out["levels"][lv] = rows
    return out


# ── Live check ───────────────────────────────────────────────────────────────

def check(tables=("B01003", "B25001", "B25077", "B25064", "B19013"), vintage=2024):
    """The municipio and island rows read here must equal the ones housing_series.py read from the same files (it stops at the county rows)."""
    p = ROOT / "cache" / "housing" / f"acs5_{vintage}.json"
    if not p.exists():
        log(f"  {p} not found: run housing_series.py first (nothing to compare with)")
        return 0
    held = json.loads(p.read_text(encoding="utf-8"))
    bad = n = 0
    for t in tables:
        r = read_table(t, vintage, ["island", "municipio"], known=None)
        for lv in ("island", "municipio"):
            for gid, cells in r["levels"][lv].items():
                for cid, val in cells.items():
                    want = (held.get(gid) or {}).get(cid)
                    if want is None:
                        continue
                    n += 1
                    if [val[0], val[1]] != [want[0], want[1]]:
                        bad += 1
                        if bad <= 5:
                            log(f"    DIFFERENT {gid} {cid}: read here {val}, held {want}")
        log(f"  {t}: {len(r['levels']['municipio'])} municipios and {len(r['levels']['island'])} island row compared")
    log(f"acs_small check: {n} values compared, {bad} different")
    return 1 if bad else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        return check()
    args = [a for a in argv if not a.startswith("--")]
    opt = lambda name: argv[argv.index(name) + 1] if name in argv else None
    if not args:
        print(__doc__)
        return 2
    table = args[0]
    vintage = int(opt("--vintage")) if opt("--vintage") else latest_vintage()
    f = RangeFile(url_for(table.upper(), vintage))
    r = read_table(table, vintage, opt("--levels").split(",") if opt("--levels") else None, refresh="--refresh" in argv, f=f)
    log(f"{r['table']} {r['vintage']} 5-year: {len(r['columns']) - 1} columns" + (f"; {f.downloaded / 1024:.0f} KB downloaded in {f.calls} requests (the nationwide file is {f.size / 1048576:.1f} MB)" if f.calls else "; read from the cache"))
    for lv, rows in r["levels"].items():
        log(f"  {lv:12s} {len(rows):5d} rows" + (f" ({r['dropped'][lv]} not units of the crosswalk, dropped)" if r["dropped"].get(lv) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
