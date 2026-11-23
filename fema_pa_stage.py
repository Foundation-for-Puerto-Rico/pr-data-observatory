"""FEMA Public Assistance in Puerto Rico by project stage and age, for the PR Data Observatory (Public spending, HANDOFF decision 109, step 2;
decision 96, step 3).

    python fema_pa_stage.py              # build site/data/spending_fema_pa.json from the cache (downloads when there is none)
    python fema_pa_stage.py --refresh    # download OpenFEMA again
    python fema_pa_stage.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network)

Source, no key: OpenFEMA's Public Assistance Funded Projects Details (www.fema.gov/api/open/v2/PublicAssistanceFundedProjectsDetails), every
Puerto Rico project. Amounts are the federal share obligated: OpenFEMA publishes obligations, not payments.

Stage, from each project's process step: "closed" is Project Closed Out; "open" is Obligated (the money is committed and the work or its
documentation is under way); "pending" is any "Pending ..." step (a review, an award or the closeout itself waits). Age counts the years from a
project's first obligation to the day the data were read; the median is weighted by dollars, so a large old project weighs more than many small ones.

Place: the county code of each project gives its municipio (FIPS 72 + code). Projects recorded as "Statewide" (about three quarters of the dollars)
name no municipio and are kept apart, never spread over the map.

output: site/data/spending_fema_pa.json. stages; island and statewide: count and dollars by stage; age_bins and age_usd (open and pending dollars by
age); median_age; disasters: [number, incident type, declaration year, count by stage, dollars by stage, median age]; categories: [damage category,
dollars by stage]; geo (the 78 municipios in the order of spending_cdbgdr.json); by_muni: dollars and counts by stage, median age and dollars open
more than five years; population (the same estimate as the other Public spending files).
"""

import json
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "spending" / "openfema_pa.json"
OUT = ROOT / "site" / "data" / "spending_fema_pa.json"
GEO = ROOT / "site" / "data" / "spending_cdbgdr.json"
API = "https://www.fema.gov/api/open/v2/PublicAssistanceFundedProjectsDetails"
UA = {"User-Agent": "PR Data Observatory (pr-digital-twin)"}
FIELDS = "disasterNumber,declarationDate,incidentType,county,countyCode,damageCategoryCode,projectProcessStep,federalShareObligated,firstObligationDate"
STAGES = ["closed", "open", "pending"]
BINS = [("under_2", 0, 2), ("2_to_5", 2, 5), ("5_to_8", 5, 8), ("8_plus", 8, 99)]


def log(*a):
    print(*a, flush=True)


def stage(step):
    s = step or ""
    return "closed" if "Closed" in s else ("open" if s == "Obligated" else "pending")


def fetch(refresh=False):
    """Every Puerto Rico project (cached with the date it was read)."""
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    rows, skip = [], 0
    while True:
        for attempt in range(5):
            try:
                r = requests.get(API, params={"$filter": "stateNumberCode eq '72'", "$select": FIELDS, "$top": 10000, "$skip": skip}, headers=UA, timeout=300)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                r = None
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"OpenFEMA skip {skip}: {getattr(r, 'status_code', r)}")
        b = r.json()["PublicAssistanceFundedProjectsDetails"]
        rows += [[x.get("disasterNumber"), (x.get("declarationDate") or "")[:10], x.get("incidentType") or "", x.get("county") or "", x.get("countyCode"),
                  x.get("damageCategoryCode") or "", x.get("projectProcessStep") or "", x.get("federalShareObligated") or 0.0, (x.get("firstObligationDate") or "")[:10]]
                 for x in b]
        if len(b) < 10000:
            break
        skip += 10000
    doc = {"read": date.today().isoformat(), "rows": rows}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8", newline="\n")
    return doc


def wmedian(pairs):
    """Dollar-weighted median of (years, dollars) pairs; None when there are none."""
    pairs = sorted(p for p in pairs if p[1] > 0)
    tot = sum(w for _, w in pairs)
    if not tot:
        return None
    c = 0.0
    for y, w in pairs:
        c += w
        if c >= tot / 2:
            return round(y, 1)


def build(refresh=False, check=False):
    if check and not CACHE.exists():
        raise FileNotFoundError("no OpenFEMA cache: run python fema_pa_stage.py")
    src = fetch(refresh and not check)
    asof = date.fromisoformat(src["read"])
    g = json.loads(GEO.read_text(encoding="utf-8"))
    ids, names, pop = g["geo"]["ids"], g["geo"]["names"], g["population"]
    at = {str(f): i for i, f in enumerate(ids)}
    z = lambda: [0, 0, 0]
    island = {"count": z(), "usd": [0.0] * 3}
    statewide = {"count": z(), "usd": [0.0] * 3}
    muni = [{"count": z(), "usd": [0.0] * 3, "ages": [], "over5": 0.0} for _ in ids]
    dis = defaultdict(lambda: {"type": "", "year": "", "count": z(), "usd": [0.0] * 3, "ages": []})
    cats = defaultdict(lambda: [0.0] * 3)
    age_usd, ages, unplaced_codes = [0.0] * len(BINS), [], 0
    for num, decl, itype, county, code, cat, step, usd, first in src["rows"]:
        k = STAGES.index(stage(step))
        island["count"][k] += 1
        island["usd"][k] += usd
        d = dis[num]
        d["type"], d["year"] = itype, decl[:4]
        d["count"][k] += 1
        d["usd"][k] += usd
        cats[cat][k] += usd
        age = (asof - date.fromisoformat(first)).days / 365.25 if first and k else None
        if age is not None:
            ages.append((age, usd))
            d["ages"].append((age, usd))
            for b, (_n, lo, hi) in enumerate(BINS):
                if lo <= age < hi:
                    age_usd[b] += usd
        fips = f"72{int(code):03d}" if code not in (None, "", 0) and county != "Statewide" else None
        if fips is None or fips not in at:
            if county != "Statewide":
                unplaced_codes += 1
            statewide["count"][k] += 1
            statewide["usd"][k] += usd
            continue
        m = muni[at[fips]]
        m["count"][k] += 1
        m["usd"][k] += usd
        if age is not None:
            m["ages"].append((age, usd))
            if age > 5:
                m["over5"] += usd
    r3 = lambda v: [round(x) for x in v]
    doc = {"version": 1, "built": asof.isoformat(), "read": src["read"], "source": "openfema", "unit": "USD", "level": "municipio",
           "stage_of": "federal share obligated, by project process step", "stages": STAGES,
           "island": {"count": island["count"], "usd": r3(island["usd"])}, "statewide": {"count": statewide["count"], "usd": r3(statewide["usd"])},
           "unplaced_not_statewide": unplaced_codes,
           "age_bins": [b[0] for b in BINS], "age_usd": r3(age_usd), "median_age": wmedian(ages),
           "disasters": sorted([[n, d["type"], d["year"], d["count"], r3(d["usd"]), wmedian(d["ages"])] for n, d in dis.items()], key=lambda x: -sum(x[4])),
           "categories": sorted([[c, r3(v)] for c, v in cats.items()], key=lambda x: x[0]),
           "geo": {"ids": ids, "names": names},
           "by_muni": {"usd": [r3(m["usd"]) for m in muni], "count": [m["count"] for m in muni], "median_age": [wmedian(m["ages"]) for m in muni],
                       "over5_usd": [round(m["over5"]) for m in muni]},
           "population": pop, "population_basis": g.get("population_basis", "")}
    tot = sum(doc["island"]["usd"])
    placed = sum(sum(v) for v in doc["by_muni"]["usd"])
    if abs(placed + sum(doc["statewide"]["usd"]) - tot) > len(ids) + 3:
        raise ValueError("municipios plus statewide do not add up to Puerto Rico")
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = old == json.loads(text)
        log(f"  spending_fema_pa.json {'is current' if same else 'differs from the cache: run python fema_pa_stage.py'}")
        return same
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"  read {src['read']}: {sum(island['count'])} projects, ${tot / 1e9:.2f} B; statewide ${sum(statewide['usd']) / 1e9:.2f} B "
        f"({100 * sum(statewide['usd']) / tot:.0f}%); by stage {[round(x / 1e9, 2) for x in island['usd']]} B; median age {doc['median_age']} years")
    log(f"  wrote spending_fema_pa.json, {OUT.stat().st_size / 1e3:.0f} KB")
    return doc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        sys.exit(0 if build(check=True) else 1)
    build(refresh="--refresh" in argv)


if __name__ == "__main__":
    main()
