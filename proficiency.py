"""Reading (Spanish) and math proficiency in Puerto Rico's public schools, all tested grades, for the 78 municipalities and Puerto Rico, school years 2014-15
to 2017-18. HANDOFF decision 107, step 7, third part (row school-outcomes: "reading and math proficiency"); docs/proficiency.md.

    python proficiency.py             # build site/data/proficiency_series.json (downloads what is missing from cache/edfacts)
    python proficiency.py --refresh   # download again
    python proficiency.py --check     # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

Source, no key: the Urban Institute's Education Data Portal (ODC-By 1.0), which republishes the US Department of Education's EDFacts assessment files (public
domain): schools/edfacts/assessments/{year}/grade-99, all grades together, the all-students row only (every subgroup code 99). For each school: the students
with a valid score and the share who scored proficient or above, in reading (in Puerto Rico, Spanish language arts) and math.

Why it stops at 2018-19. The newest school-level files a script can read end there (checked 2026-11-18): the portal holds no Puerto Rico rows after 2018 (2018-19; 2019-20 was not tested),
ED Data Express answers a script with an empty page, and the Department of Education's school profile (perfilescolar.dde.pr) is a Power BI report with no
data file. The label of every dataset gives its school years.

To protect students, EDFacts gives a small school a range (for example 20% to 29%), not a number. The share used is the middle of the range, and the notes
keep the island's figure from the bottom and the top of every range: the band the truth must lie in.
A municipio's share is pooled: the sum over its schools of (share x students tested) over the sum of students tested, never an average of school shares.
Each school is placed in a municipio by its NCES id in the Common Core of Data directory of the same year (cache/education, from education_series.py).

Puerto Rico sets its own test (META-PR) and its own line for "proficient": do not compare these shares with a state's.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "edfacts"
CCD = ROOT / "cache" / "education"
OUT = DATA / "proficiency_series.json"
YEARS = (2014, 2015, 2016, 2017, 2018)
API = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{y}/grade-99/"
FILTER = "?fips=72&race=99&sex=99&lep=99&homeless=99&migrant=99&disability=99&econ_disadvantaged=99&foster_care=99&military_connected=99"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
G = "Education · Test results (META-PR, 2014-15 to 2018-19)"
SUBJ = {"read": ("reading (Spanish)", "lectura (español)"), "math": ("math", "matemáticas")}
SOURCES = {"urban_edfacts": {"name": "Urban Institute, Education Data Portal: EDFacts state assessments (US Department of Education)", "url": "https://educationdata.urban.org/documentation/schools.html#edfacts",
                             "license": "ODC-By 1.0 (the portal); the federal data are public domain", "note": "Students tested and share proficient by school; only municipio shares are published."},
           "urban_ccd": {"name": "Urban Institute, Education Data Portal: NCES Common Core of Data school directory", "url": "https://educationdata.urban.org/documentation/schools.html",
                         "license": "ODC-By 1.0 (the portal); the federal data are public domain", "note": "The municipio of each school (county code), by its NCES id."}}


def log(*a):
    print(*a, flush=True)


def fetch(year, refresh=False, offline=False):
    """Every all-students row of one year's assessment file (all pages), cached as cache/edfacts/assess_{year}.json in the portal's own layout."""
    p = CACHE / f"assess_{year}.json"
    if p.exists() and not refresh:
        d = json.loads(p.read_text(encoding="utf-8"))
        if not d.get("next"):
            return d["results"]
    if offline:
        raise SystemExit(f"proficiency: {p.name} is not complete in the cache (python proficiency.py downloads it; --check never does)")
    import requests
    url, out = API.format(y=year) + FILTER, []
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
            raise SystemExit(f"proficiency: {url} did not answer after six tries")
        j = r.json()
        out += j["results"]
        url = j.get("next")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"count": len(out), "next": None, "results": out}, separators=(",", ":")), encoding="utf-8")
    return out


def county_of(year):
    f = sorted(CCD.glob(f"schools_ccd_directory_{year}_*.json"))
    if not f:
        raise SystemExit(f"proficiency: no CCD directory for {year} in cache/education (python education_series.py makes it)")
    return {r["ncessch"]: str(r["county_code"]) for r in json.loads(f[-1].read_text(encoding="utf-8"))}


def val(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def year_values(year, ids, refresh=False, offline=False):
    where = county_of(year)
    at = {m: i for i, m in enumerate(ids)}
    n = len(ids) + 1
    acc = {s: {"mid": [0.0] * n, "lo": [0.0] * n, "hi": [0.0] * n, "w": [0.0] * n} for s in SUBJ}
    rows = [r for r in fetch(year, refresh, offline) if all(r.get(k, 99) == 99 for k in ("race", "sex", "lep", "homeless", "migrant", "disability", "econ_disadvantaged", "foster_care", "military_connected"))]
    unplaced, ranged = 0, {s: 0 for s in SUBJ}
    for r in rows:
        i = at.get(where.get(str(r.get("ncessch") or r.get("ncessch_num")).zfill(12)))
        if i is None:
            unplaced += 1
            continue
        for s in SUBJ:
            w, mid, lo, hi = (val(r.get(f"{s}_test_{k}")) for k in ("num_valid", "pct_prof_midpt", "pct_prof_low", "pct_prof_high"))
            if not w or mid is None:
                continue
            lo = mid if lo is None else lo
            hi = mid if hi is None else hi
            if hi > lo:
                ranged[s] += 1
            for j in (i, n - 1):
                a = acc[s]
                a["mid"][j] += w * mid
                a["lo"][j] += w * lo
                a["hi"][j] += w * hi
                a["w"][j] += w
    out, band = {}, {}
    for s in SUBJ:
        a = acc[s]
        out[f"prof_{s}_pct"] = [round(a["mid"][j] / a["w"][j], 1) if a["w"][j] else None for j in range(n)]
        out[f"tested_{s}"] = [int(a["w"][j]) for j in range(n)]
        band[s] = {"island_low": round(a["lo"][-1] / a["w"][-1], 1), "island_high": round(a["hi"][-1] / a["w"][-1], 1), "schools_with_a_range": ranged[s]}
    return out, {"school_rows": len(rows), "schools_unplaced": unplaced, "band": band}


def assemble(refresh=False, offline=False):
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    ids, names = [r[0] for r in muni], [r[2] for r in muni]
    per, notes = {}, {}
    for y in YEARS:
        per[y], notes[str(y)] = year_values(y, ids, refresh, offline)
    REF = "US Department of Education, EDFacts state assessment files, school years 2014-15 to 2018-19, via the Urban Institute's Education Data Portal; pooled by municipio"
    TAIL = (" Public schools, all tested grades together, pooled over the students with a valid score; a small school's share comes as a range and its middle is used. "
            "Puerto Rico sets its own test (META-PR) and its own line for proficient: do not compare with a state. The newest school-level results a script can read end in 2018-19. "
            "The year is the school year that starts in it (2018 = 2018-19, tested in spring 2019).")
    vs = []
    for s, (en, es) in SUBJ.items():
        vs.append({"key": f"prof_{s}_pct", "group": G, "label": f"Students proficient in {en} (%)", "unit": "%", "d": 1, "type": "rate", "sources": ["urban_edfacts", "urban_ccd"], "ref": REF,
                   "definition": f"The share of students tested in {en} who scored proficient or above on Puerto Rico's test." + TAIL, "family": "proficiency", "counted": False, "noPerHU": True,
                   "years": {str(y): per[y][f"prof_{s}_pct"] for y in YEARS}})
    notes["tested"] = {str(y): {s: per[y][f"tested_{s}"][-1] for s in SUBJ} for y in YEARS}
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
        log(f"  {v['key']:16s} " + "  ".join(f"{y}: {v['years'][str(y)][-1]}" for y in YEARS))
    log("  " + json.dumps({y: doc["notes"][y] for y in map(str, YEARS)}))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in sys.argv and not CACHE.exists():
        print(f"proficiency: {CACHE} is not in the cache; nothing to check")
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
