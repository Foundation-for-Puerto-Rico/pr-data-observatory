"""School conditions from the Civil Rights Data Collection (CRDC), public schools, for the 78 municipalities and Puerto Rico, school years 2017-18 and 2021-22.
HANDOFF decision 107, step 7, second part (row school-outcomes: "civil-rights data"); docs/school_conditions.md.

    python school_conditions.py             # build site/data/school_conditions_series.json (downloads what is missing from cache/crdc)
    python school_conditions.py --refresh   # download again
    python school_conditions.py --check     # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

Source, no key: the Urban Institute's Education Data Portal (ODC-By 1.0), which republishes the US Department of Education's Civil Rights Data Collection
(public domain). Only all-students rows are asked for (race, sex, disability, English learner and homeless all 99 = total):
  schools/crdc/enrollment/{year}/race/sex          students enrolled at the school (enrollment_crdc)
  schools/crdc/chronic-absenteeism/{year}/race/sex students absent 15 or more school days in the year (students_chronically_absent)
  schools/crdc/teachers-staff/{year}               full-time equivalents of teachers, first-year teachers, counselors and nurses
The CRDC runs every two years; 2019-20 was skipped (the pandemic), so 2017-18 and 2021-22 are the two newest with these items. A year is the school year
that starts in it (2021 = 2021-22). Each school is placed in a municipio by its NCES id in the Common Core of Data directory of the same year (the cache of
education_series.py); a school the directory lacks is counted in the notes, never guessed. Negative codes (missing, not applicable, suppressed) are no value.

Ratios are pooled, never averaged: a municipio's share is the sum of its schools' numerators over the sum of their denominators, over the schools that
report both.
  crdc_absent_pct          chronically absent students, % of enrolled students
  crdc_students_counselor  enrolled students per full-time school counselor
  crdc_nurse_pct           schools with a nurse (any nurse FTE), % of schools that report staff
  crdc_no_counselor_pct    schools with no school counselor (0 FTE), % of schools that report staff
Puerto Rico's staff items are all missing (-1) in 2017-18 and its first-year teacher item in 2021-22, so the staff measures have 2021-22 only and there is
no first-year teacher measure. Check: the Annie E. Casey Foundation's KIDS COUNT release for Puerto Rico (2024, with the Instituto del Desarrollo de la
Juventud) reports 48% of public school students chronically absent around 2022-23, beside the 45.7% this file gives for 2021-22.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "crdc"
CCD = ROOT / "cache" / "education"
OUT = DATA / "school_conditions_series.json"
YEARS = (2017, 2021)
API = "https://educationdata.urban.org/api/v1/schools/crdc/"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
G = "Education · School conditions (Civil Rights Data Collection)"
TOTALS = {"race": 99, "sex": 99, "disability": 99, "lep": 99, "homeless": 99}
PATHS = {"enroll": "enrollment/{y}/race/sex/", "absent": "chronic-absenteeism/{y}/race/sex/", "staff": "teachers-staff/{y}/"}
SOURCES = {"urban_crdc": {"name": "Urban Institute, Education Data Portal: Civil Rights Data Collection (US Department of Education, Office for Civil Rights)",
                         "url": "https://educationdata.urban.org/documentation/schools.html#crdc", "license": "ODC-By 1.0 (the portal); the federal data are public domain",
                         "note": "School-level counts of students, chronic absence and staff; only municipio totals are published."},
           "urban_ccd": {"name": "Urban Institute, Education Data Portal: NCES Common Core of Data school directory", "url": "https://educationdata.urban.org/documentation/schools.html",
                         "license": "ODC-By 1.0 (the portal); the federal data are public domain", "note": "The municipio of each school (county code), by its NCES id."}}


def log(*a):
    print(*a, flush=True)


def fetch(kind, year, refresh=False, offline=False):
    """Every all-students row of one CRDC file for Puerto Rico (all pages), cached as cache/crdc/{kind}_{year}_total.json."""
    p = CACHE / f"{kind}_{year}_total.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"school_conditions: {p.name} is not in the cache (python school_conditions.py downloads it; --check never does)")
    import requests
    filt = "" if kind == "staff" else "&" + "&".join(f"{k}=99" for k in (TOTALS if kind == "absent" else ("race", "sex", "disability", "lep")))
    url, out = API + PATHS[kind].format(y=year) + "?fips=72" + filt, []
    while url:
        for attempt in range(6):   # the portal times out often (2026-11-18)
            try:
                r = requests.get(url, headers=UA, timeout=300)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(10 * (attempt + 1))
        else:
            raise SystemExit(f"school_conditions: {url} did not answer after six tries")
        j = r.json()
        out += j["results"]
        url = j.get("next")
    rows = [x for x in out if all(x.get(k, 99) == 99 for k in TOTALS)]
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    return rows


def county_of(year):
    f = sorted(CCD.glob(f"schools_ccd_directory_{year}_*.json"))
    if not f:
        raise SystemExit(f"school_conditions: no CCD directory for {year} in cache/education (python education_series.py makes it)")
    return {r["ncessch"]: str(r["county_code"]) for r in json.loads(f[-1].read_text(encoding="utf-8"))}


def val(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def year_values(year, ids, refresh=False, offline=False):
    where = county_of(year)
    enroll = {r["ncessch"]: val(r.get("enrollment_crdc")) for r in fetch("enroll", year, refresh, offline)}
    absent = {r["ncessch"]: val(r.get("students_chronically_absent")) for r in fetch("absent", year, refresh, offline)}
    staff = {r["ncessch"]: r for r in fetch("staff", year, refresh, offline)}
    at = {m: i for i, m in enumerate(ids)}
    n = len(ids) + 1   # the last is the island
    acc = {k: [[0.0, 0.0] for _ in range(n)] for k in ("absent", "counsel", "nurse", "nocounsel")}
    schools = set(enroll) | set(staff)
    unplaced = [s for s in schools if where.get(s) not in at]

    def add(k, i, num, den):
        for j in (i, n - 1):
            acc[k][j][0] += num
            acc[k][j][1] += den
    for s in schools:
        if s in unplaced:
            continue
        i = at[where[s]]
        e, a, st = enroll.get(s), absent.get(s), staff.get(s)
        if e and a is not None:
            add("absent", i, a, e)
        if st:
            c, nu = val(st.get("counselors_fte")), val(st.get("nurses_fte"))
            if e and c is not None:
                add("counsel", i, e, c)   # students over counselors: pooled
            if c is not None:
                add("nocounsel", i, 1 if c == 0 else 0, 1)
            if nu is not None:
                add("nurse", i, 1 if nu > 0 else 0, 1)
    r = lambda num, den, scale=100, d=1: round(num / den * scale, d) if den else None   # noqa: E731
    out = {"crdc_absent_pct": [r(*x) for x in acc["absent"]],
           "crdc_students_counselor": [r(x[0], x[1], 1, 0) for x in acc["counsel"]],
           "crdc_nurse_pct": [r(*x) for x in acc["nurse"]],
           "crdc_no_counselor_pct": [r(*x) for x in acc["nocounsel"]]}
    notes = {"schools": len(schools), "schools_unplaced": len(unplaced), "enrolled": int(acc["absent"][-1][1]),
             "chronically_absent": int(acc["absent"][-1][0]), "counselors_fte": round(acc["counsel"][-1][1], 1), "schools_with_staff": int(acc["nurse"][-1][1])}
    return out, notes


def assemble(refresh=False, offline=False):
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    ids, names = [r[0] for r in muni], [r[2] for r in muni]
    per, notes = {}, {}
    for y in YEARS:
        per[y], notes[str(y)] = year_values(y, ids, refresh, offline)
    REF = "US Department of Education, Civil Rights Data Collection 2017-18 and 2021-22, public schools, via the Urban Institute's Education Data Portal; pooled by municipio"
    TAIL = (" Public schools that answered the Civil Rights Data Collection, placed in a municipio by the NCES school directory; the share is pooled over the schools that report both "
            "figures, never an average of school shares. The year is the school year that starts in it (2021 = 2021-22); 2019-20 was not collected.")

    def var(key, label, unit, d, definition):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": "rate", "sources": ["urban_crdc", "urban_ccd"], "ref": REF,
                "definition": definition + TAIL, "family": "school_conditions", "counted": False, "noPerHU": True, "years": {str(y): per[y][key] for y in YEARS}}
    vs = [var("crdc_absent_pct", "Students chronically absent (%)", "%", 1,
              "Students absent 15 or more school days in the year, for any reason (excused or not), as a share of the students enrolled."),
          var("crdc_students_counselor", "Students per school counselor", "", 0,
              "Students enrolled for each full-time school counselor (full-time equivalents). Puerto Rico's staff items are missing in 2017-18."),
          var("crdc_nurse_pct", "Schools with a nurse (%)", "%", 1,
              "Schools that report any nurse (full- or part-time), as a share of the schools that report their staff. Puerto Rico's staff items are missing in 2017-18."),
          var("crdc_no_counselor_pct", "Schools with no school counselor (%)", "%", 1,
              "Schools that report no school counselor (zero full-time equivalents), as a share of the schools that report their staff. Puerto Rico's staff items are missing in 2017-18.")]
    return {"as_of": date.today().isoformat(), "years": list(YEARS), "geo": {"ids": [*ids, "72"], "names": [*names, "Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    doc = assemble(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")
    for v in doc["vars"]:
        log(f"  {v['key']:24s} " + "  ".join(f"{y}: {v['years'][str(y)][-1]}" for y in YEARS))
    log("  " + json.dumps(doc["notes"]))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in sys.argv and not CACHE.exists():
        print(f"school_conditions: {CACHE} is not in the cache; nothing to check")
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
