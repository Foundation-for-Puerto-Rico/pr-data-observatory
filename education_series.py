"""Education for the PR Data Observatory (Phase 3, item 8, data wave B): public schools and colleges, every school year since 2010, for the 78 municipalities and Puerto Rico.

    python education_series.py             # build site/data/education_series.json (downloads only the years that are missing from the cache)
    python education_series.py --refresh   # download every year again
    python education_series.py --check     # rebuild from the cache and exit 1 when site/data/education_series.json is not what it gives (no network, nothing written)

Source, no key: the Urban Institute's Education Data Portal API (https://educationdata.urban.org), which republishes two US federal collections of the National Center for
Education Statistics (NCES) under the Open Data Commons Attribution license (ODC-By 1.0): credit "Urban Institute, Education Data Portal" and NCES.
  schools/ccd/directory/{year}                        the Common Core of Data (CCD) school directory: one row for each public school, with its county, status, students and teachers
  college-university/ipeds/directory/{year}           IPEDS, the directory of colleges, universities and other postsecondary institutions, with the county of each
  college-university/ipeds/fall-enrollment/{year}/... IPEDS fall enrollment (undergraduate and graduate totals of each institution)
A year is the school year that starts in it (2023 = 2023-24 for schools, fall 2023 for colleges).

What is kept. Only the columns listed in KEEP reach the cache (cache/education/) and only counts for each municipality reach the output: school and college names,
addresses, telephone numbers, web addresses, officers' names and coordinates are dropped as each row is read. Urban codes a missing value as a negative number
(-1 missing, -2 not applicable, -3 suppressed): those are read as no value, never as zero.

Variables (docs/education.md has the reasons and the checks):
  sch_open      public schools open in the year (CCD status open, new, added, changed agency or reopened)
  sch_enroll    students in those schools (a municipality whose open schools all lack a count has no value)
  sch_teachers  their classroom teachers, full-time equivalents
  sch_ptr       students per teacher: only schools that report both are counted
  sch_closed    schools open the year before that are not open this year (a school that changes its id is counted as a closure and an opening, which the notes measure)
  he_inst       postsecondary institutions in the IPEDS directory of the year (sector above 0: not the office of a university system, not a "not applicable" record)
  he_enroll     their students in the fall, undergraduate and graduate
Output: {"built", "years", "geo": {"ids", "names"}, "vars", "sources", "notes"}, arrays indexed like geo.names (the last entry is Puerto Rico), the shape of economy_series.json.
"""

import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "education"
OUT = hs.OUT / "education_series.json"
API = "https://educationdata.urban.org/api/v1/"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
FIRST = 2010
log = hs.log

KEEP = {
    "ccd": ["ncessch", "year", "county_code", "school_status", "school_type", "school_level", "enrollment", "teachers_fte", "charter", "virtual"],
    "ipeds": ["unitid", "year", "county_fips", "sector", "inst_control", "institution_level", "degree_granting", "currently_active_ipeds"],
    "fall": ["unitid", "year", "level_of_study", "enrollment_fall"],
}
OPEN = {1, 3, 4, 5, 8}   # CCD school status: 1 open, 3 new, 4 added, 5 changed agency, 8 reopened (2 closed, 6 inactive, 7 future are not open)
FLOORS = {"schools": 600, "enroll": 150_000, "inst": 60}   # fewer than these in a year means Urban changed a code or a column (2023: 858 open schools, 240,910 students, 128 institutions)

SOURCES = {
    "urban_ccd": {"name": "Urban Institute, Education Data Portal: NCES Common Core of Data school directory", "url": "https://educationdata.urban.org/documentation/schools.html",
                  "license": "Open Data Commons Attribution License (ODC-By 1.0) for the portal; the underlying NCES data are US federal (public domain)",
                  "note": "One row for each public school each school year. The observatory publishes counts for each municipality (schools, students, teachers, closures), never a school's name, address or location."},
    "urban_ipeds": {"name": "Urban Institute, Education Data Portal: NCES IPEDS directory and fall enrollment", "url": "https://educationdata.urban.org/documentation/colleges.html",
                    "license": "Open Data Commons Attribution License (ODC-By 1.0) for the portal; the underlying NCES data are US federal (public domain)",
                    "note": "Colleges, universities and other postsecondary institutions that report to IPEDS, with their fall enrollment. The observatory publishes counts for each municipality, never an institution's name, address or officers."},
}


def num(v):
    """A count from Urban: None for a missing, suppressed or not applicable value (negative codes) and for anything that is not a number."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x < 0 else x


# ── Download and cache ───────────────────────────────────────────────────────

def cache_file(path):
    """A short name for the cache file of one request (the full request is too long for a Windows path): what and which year, and a hash of the request."""
    parts = [x for x in re.split(r"[/?&]", path) if x]
    head = "_".join(x for x in parts[:6] if not x.startswith(("fips", "race", "sex", "ftpt", "degree", "class")))
    return CACHE / f"{head.replace('college-university_', '')}_{hashlib.sha1(path.encode()).hexdigest()[:8]}.json"


def fetch(path, kind, year, refresh=False, offline=False, missing_ok=False):
    """The kept columns of every Puerto Rico row of one endpoint and year, from the cache or the API (all pages). [] when the API has no row for the year."""
    f = cache_file(path)
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    if offline and missing_ok:
        return []
    if offline:
        raise SystemExit(f"education_series --check: {f.name} is not in the cache, so there is nothing to check (python education_series.py makes it; --check never downloads)")
    url, rows = API + path, []
    while url:
        for attempt in range(4):
            try:
                r = requests.get(url, headers=UA, timeout=(30, 180))
                if r.status_code == 404:
                    return []
                r.raise_for_status()
                d = r.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 3:
                    raise SystemExit(f"education_series: {url} failed: {e}")
                time.sleep(5 * (attempt + 1))
        for row in d.get("results") or []:
            if str(row.get("fips")) != "72":
                continue
            rows.append({c: row.get(c) for c in KEEP[kind]})
        url = d.get("next")
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    log(f"  {path}: {len(rows)} rows")
    return rows


def years_available(refresh=False, offline=False):
    """The school years from FIRST on that the CCD directory has for Puerto Rico: the first year with no row ends the run."""
    ys, y = [], FIRST
    while True:
        rows = fetch(f"schools/ccd/directory/{y}/?fips=72", "ccd", y, refresh, offline, missing_ok=True)
        if not rows:
            break
        ys.append(y)
        y += 1
    return ys


# ── Aggregation ──────────────────────────────────────────────────────────────

def schools(rows, ids):
    """For one year: {fips: [open, enrollment or None, teachers or None, students counted for the ratio, teachers counted for the ratio]} and the open school ids, with notes."""
    by, seen, notes = defaultdict(lambda: [0, None, None, 0.0, 0.0]), set(), Counter()
    for r in rows:
        st = r["school_status"]
        if st not in OPEN:
            notes[f"status {st}"] += 1
            continue
        fips = str(r["county_code"] or "")
        if fips not in ids:
            raise SystemExit(f"education_series: an open school ({r['ncessch']}, {r['year']}) has the county code {fips!r}, which is not one of the 78 municipalities")
        a = by[fips]
        a[0] += 1
        seen.add(r["ncessch"])
        e, t = num(r["enrollment"]), num(r["teachers_fte"])
        if e is not None:
            a[1] = (a[1] or 0) + e
        else:
            notes["open, no enrollment"] += 1
        if t is not None:
            a[2] = (a[2] or 0) + t
        else:
            notes["open, no teachers"] += 1
        if e is not None and t is not None and t > 0:
            a[3] += e
            a[4] += t
    return by, seen, notes


def colleges(dir_rows, fall_rows, ids):
    """For one year: {fips: institutions} and {fips: fall enrollment or None}, with notes. An institution's enrollment goes to the municipality of its directory row."""
    where, inst, notes = {}, Counter(), Counter()
    for r in dir_rows:
        if (num(r["sector"]) or 0) <= 0:   # sector 0: the administrative office of a university system (3 in San Juan every year); -1: "not applicable" records (13 in 2020); neither is an institution and neither has fall enrollment
            notes[f"not an institution (sector {r['sector']})"] += 1
            continue
        fips = str(r["county_fips"] or "")
        if fips not in ids:
            notes["no municipality"] += 1
            continue
        where[r["unitid"]] = fips
        inst[fips] += 1
    enr = defaultdict(lambda: None)
    for r in fall_rows:
        e = num(r["enrollment_fall"])
        fips = where.get(r["unitid"])
        if fips is None:
            notes["fall rows of an institution not in the directory"] += 1
            continue
        if e is not None:
            enr[fips] = (enr[fips] or 0) + e
    return inst, enr, notes


# ── Output ───────────────────────────────────────────────────────────────────

def var(key, group, label, unit, d, typ, sources, ref, definition, values, **extra):
    """`counted: False`: administrative counts, not estimates from a few cases, so the engine does not flag a small count as less reliable."""
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": ref, "definition": definition, "family": "education", "counted": False, **extra, "years": values}


def compute(refresh=False, offline=False, floors=FLOORS, order_file=hs.OUT / "economy_series.json"):
    names, fips = hs.municipalities()
    ids = list(fips)
    n = len(ids)
    if order_file and order_file.exists():   # the arrays must line up with the other series files
        g = json.loads(order_file.read_text(encoding="utf-8"))["geo"]
        if g["ids"][:n] != ids or g["names"][:n] != names:
            raise SystemExit("education_series: the municipalities are not in the order of economy_series.json")
    log("Education: NCES Common Core of Data and IPEDS (Urban Institute Education Data Portal)")
    ys = years_available(refresh, offline)
    if not ys:
        raise SystemExit("education_series: the CCD directory has no year for Puerto Rico")
    vals = {k: {} for k in ("sch_open", "sch_enroll", "sch_teachers", "sch_ptr", "sch_closed", "he_inst", "he_enroll")}
    notes = {"schools": {}, "colleges": {}, "closures_reopened_next_year": {}}
    prev_open, opened_by_year = None, {}
    for y in ys:
        rows = fetch(f"schools/ccd/directory/{y}/?fips=72", "ccd", y, refresh, offline)
        by, open_ids, sn = schools(rows, set(ids))
        tot_open = sum(a[0] for a in by.values())
        tot_enroll = sum(a[1] or 0 for a in by.values())
        if floors and (tot_open < floors["schools"] or tot_enroll < floors["enroll"]):
            raise SystemExit(f"education_series: {y}: {tot_open} open schools and {tot_enroll:,.0f} students (2023 has 858 and over 235,000): Urban may have changed a status code or a column; read its documentation before publishing")
        col = lambda i: [by[f][i] if f in by else (0 if i == 0 else None) for f in ids]
        isl = lambda arr: None if all(x is None for x in arr) else sum(x for x in arr if x is not None)
        o = col(0)
        e = [round(x) if x is not None else None for x in col(1)]
        t = [round(x, 1) if x is not None else None for x in col(2)]
        vals["sch_open"][str(y)] = o + [sum(o)]
        vals["sch_enroll"][str(y)] = e + [isl(e)]
        vals["sch_teachers"][str(y)] = t + [None if isl(t) is None else round(isl(t), 1)]
        ptr = [round(by[f][3] / by[f][4], 2) if f in by and by[f][4] > 0 else None for f in ids]
        s3, s4 = sum(by[f][3] for f in by), sum(by[f][4] for f in by)
        vals["sch_ptr"][str(y)] = ptr + [round(s3 / s4, 2) if s4 > 0 else None]
        if prev_open is not None:
            gone = {}
            for f in ids:
                gone[f] = 0
            prev_rows = fetch(f"schools/ccd/directory/{y - 1}/?fips=72", "ccd", y - 1, refresh, offline)
            prev_where = {r["ncessch"]: str(r["county_code"]) for r in prev_rows if r["school_status"] in OPEN}
            closed = prev_open - open_ids
            for sid in closed:
                gone[prev_where[sid]] += 1
            c = [gone[f] for f in ids]
            vals["sch_closed"][str(y)] = c + [sum(c)]
            opened_by_year[y] = open_ids - prev_open
        else:
            vals["sch_closed"][str(y)] = [None] * (n + 1)
        prev_open = open_ids
        notes["schools"][str(y)] = {"rows": len(rows), "open": tot_open, "students": round(tot_enroll), **dict(sn)}
        d_rows = fetch(f"college-university/ipeds/directory/{y}/?fips=72", "ipeds", y, refresh, offline)
        f_rows = []
        for lvl in ("undergraduate", "graduate"):
            f_rows += fetch(f"college-university/ipeds/fall-enrollment/{y}/{lvl}/race/sex/?fips=72&race=99&sex=99&ftpt=99&degree_seeking=99&class_level=99", "fall", y, refresh, offline)
        if not d_rows:
            vals["he_inst"][str(y)] = [None] * (n + 1)
            vals["he_enroll"][str(y)] = [None] * (n + 1)
            continue
        inst, enr, cn = colleges(d_rows, f_rows, set(ids))
        if floors and sum(inst.values()) < floors["inst"]:
            raise SystemExit(f"education_series: {y}: {sum(inst.values())} postsecondary institutions (2023 has 128): read Urban's IPEDS documentation before publishing")
        ic = [inst.get(f, 0) for f in ids]
        vals["he_inst"][str(y)] = ic + [sum(ic)]
        if f_rows:
            ec = [round(enr[f]) if enr[f] is not None else (0 if inst.get(f, 0) == 0 else None) for f in ids]
            vals["he_enroll"][str(y)] = ec + [isl(ec)]
        else:
            vals["he_enroll"][str(y)] = [None] * (n + 1)
        notes["colleges"][str(y)] = {"institutions": sum(ic), "fall_rows": len(f_rows), "students": None if not f_rows else isl(vals["he_enroll"][str(y)][:-1]), **dict(cn)}
    # A school whose id changes in a year counts as a closure and an opening: measure how many closures come back under the same id the next year (a reopening the build cannot tell from a recode)
    for y in ys[1:-1]:
        prev = fetch(f"schools/ccd/directory/{y - 1}/?fips=72", "ccd", y - 1, refresh, offline)
        cur = {r["ncessch"] for r in fetch(f"schools/ccd/directory/{y}/?fips=72", "ccd", y, refresh, offline) if r["school_status"] in OPEN}
        nxt = {r["ncessch"] for r in fetch(f"schools/ccd/directory/{y + 1}/?fips=72", "ccd", y + 1, refresh, offline) if r["school_status"] in OPEN}
        prev_ids = {r["ncessch"] for r in prev if r["school_status"] in OPEN}
        notes["closures_reopened_next_year"][str(y)] = len((prev_ids - cur) & nxt)
    G1, G2 = "Public schools", "Colleges and universities"
    REF_CCD, REF_IPEDS = "NCES Common Core of Data, via the Urban Institute Education Data Portal", "NCES IPEDS, via the Urban Institute Education Data Portal"
    YEAR = "A year is the school year that starts in it (2023 = the 2023-24 school year). "
    vs = [
        var("sch_open", G1, "Public schools open", "", 0, "count", ["urban_ccd"], REF_CCD,
            YEAR + "Public schools that the Common Core of Data lists as open in the municipality that year (open, new, added, changed agency or reopened), including the few charter-like and virtual schools it lists. "
            "Private schools are not in this collection. A municipality with none shows 0.", vals["sch_open"], noPerHU=True),
        var("sch_enroll", G1, "Students in public schools", "", 0, "count", ["urban_ccd"], REF_CCD,
            YEAR + "Students enrolled in the open public schools of the municipality, as the schools report them in the fall. A school that reports no count is left out of the total, "
            "and a municipality whose open schools all lack a count has no value.", vals["sch_enroll"], noPerHU=True),
        var("sch_teachers", G1, "Public school teachers (full-time equivalents)", "", 1, "count", ["urban_ccd"], REF_CCD,
            YEAR + "Classroom teachers of the open public schools of the municipality, in full-time equivalents (two half-time teachers count as one). A school that reports no count is left out.",
            vals["sch_teachers"], noPerHU=True),
        var("sch_ptr", G1, "Students per teacher, public schools", "", 1, "ratio", ["urban_ccd"], REF_CCD,
            YEAR + "Students divided by full-time-equivalent teachers, counting only the schools that report both. It is not class size: teachers who do not lead a class of their own are counted.",
            vals["sch_ptr"]),
        var("sch_closed", G1, "Public schools closed since the year before", "", 0, "count", ["urban_ccd"], REF_CCD,
            YEAR + "Public schools that were open in the municipality the year before and are not open this year. A school that NCES gives a new identifier counts as a closure (and an opening), so a few may be "
            "changes of record rather than closures; no value for the first year.", vals["sch_closed"], noPerHU=True),
        var("he_inst", G2, "Colleges, universities and other postsecondary institutions", "", 0, "count", ["urban_ipeds"], REF_IPEDS,
            "Institutions in the IPEDS directory for the year, in the municipality of their main address: universities, colleges and technical and vocational schools (beauty, nursing and trade schools among them). "
            "The central offices of university systems and the directory's records marked \"not applicable\" are not counted. "
            "A university with campuses in several municipalities that report separately counts once for each campus; one that reports as a whole counts once where its main office is.", vals["he_inst"], noPerHU=True),
        var("he_enroll", G2, "Students in colleges and universities (fall)", "", 0, "count", ["urban_ipeds"], REF_IPEDS,
            "Undergraduate and graduate students enrolled in the fall at the institutions of the municipality, full-time and part-time. Students are counted where the institution reports, which for a university "
            "that reports as a whole is its main office, not the campus they attend.", vals["he_enroll"], noPerHU=True),
    ]
    return {"years": ys, "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    out = compute(refresh, offline=check)
    new = {"built": date.today().isoformat(), **out}
    text = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        if old is None or {**old, "built": None} != {**json.loads(text), "built": None}:
            print("education_series.json is not what the cache gives: run python education_series.py")
            return 1
        print("education_series.json matches the cache")
        return 0
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(out['vars'])} variables, years {out['years'][0]}-{out['years'][-1]}, {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
