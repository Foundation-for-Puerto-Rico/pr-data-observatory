"""Federal money obligated and paid out in Puerto Rico, by function, for the PR Data Observatory (Public spending, HANDOFF decision 96, step 2).

    python federal_outlays.py              # build site/data/spending_outlays.json (downloads only the signing years missing from cache/spending/outlays/)
    python federal_outlays.py --refresh    # download the two latest signing years again (their outlays still grow)
    python federal_outlays.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network)

Source, no key: USAspending.gov's award search (api.usaspending.gov/api/v2/search/spending_by_award/), place of performance Puerto Rico, awards
SIGNED in each federal fiscal year (date_type date_signed), every page. For each award it gives the amount obligated over the award's life
("Award Amount") and the total outlays to date ("Total Outlays": what the Treasury has paid to the recipient). USAspending has outlays from
fiscal year 2020 on, so only awards signed from FY2020 are read: both figures then cover the whole life of the award.

What is read. Grants (award types 02 to 05) and contracts (A to D). Direct payments (Social Security, Medicare and the like, 06 and 10) are paid when
they are recorded, so their outlays equal their obligations; loans and insurance (07, 08, 09, 11) report no outlays. FEMA Public Assistance (97.036)
is left out: USAspending reports it in a way that does not follow the projects (its largest Puerto Rico award shows $0.44 B against tens of billions
in OpenFEMA), and the page counts it by project stage from OpenFEMA (step 3). Its USAspending figures are kept in "excluded" so the gap is visible.

Paid out. Some awards report outlays above their obligated amount (an award amount that lags its amendments, or an outlay reported against the wrong
award). The share paid out caps each award's outlays at its obligated amount; the uncapped excess is counted in "over" so it is not hidden.

Function: as federal_awards.py (the crosswalk, dictionary_src/spending_crosswalk.csv; a contract takes its awarding agency's default).

output: site/data/spending_outlays.json. years (signing years); groups; functions; totals per group: obligated, paid (capped), awards, over (count and
excess dollars) and no_outlay (awards with no outlay reported); rows: [key, name, group, function, confidence, [obligated per year], [paid per year]]
for programs (or contract agencies) with at least $10 million obligated over the years read, the rest added into "Other programs" by agency, group
and function; excluded: obligated and paid of the programs left out.
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import spending
from federal_awards import last_year, UA

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "spending" / "outlays"
OUT = ROOT / "site" / "data" / "spending_outlays.json"
FED = ROOT / "site" / "data" / "spending_federal.json"
API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIRST_YEAR = 2020
KEEP = 10_000_000
GROUPS = {"grants": ["02", "03", "04", "05"], "contracts": ["A", "B", "C", "D"]}
FIELDS = {"grants": ["Award ID", "Award Amount", "Total Outlays", "CFDA Number"], "contracts": ["Award ID", "Award Amount", "Total Outlays", "Awarding Agency"]}
EXCLUDE = {"97.036": "FEMA Public Assistance: USAspending's awards do not follow the projects; counted by project stage from OpenFEMA"}
# a contract's awarding agency (USAspending's name) to the assistance listing prefix whose default function it takes (federal_awards.CONTRACT_AGENCY by name)
AGENCY = {"Department of Agriculture": "10", "Department of Commerce": "11", "Department of Defense": "12", "Department of Housing and Urban Development": "14",
          "Department of the Interior": "15", "Department of Justice": "16", "Department of Labor": "17", "Department of State": "19",
          "Department of Transportation": "20", "Department of the Treasury": "21", "Federal Communications Commission": "32",
          "General Services Administration": "39", "National Aeronautics and Space Administration": "43", "National Science Foundation": "47",
          "Small Business Administration": "59", "Department of Veterans Affairs": "64", "Environmental Protection Agency": "66",
          "Department of Energy": "81", "Department of Education": "84", "Department of Health and Human Services": "93",
          "Corporation for National and Community Service": "94", "Social Security Administration": "96", "Department of Homeland Security": "97"}
UNMAPPED = set()


def log(*a):
    print(*a, flush=True)


def fetch(fy, group, refresh=False):
    """Every award of one group signed in one federal fiscal year (cached): [id, obligated, outlays or None, listing or agency]."""
    p = CACHE / f"{fy}_{group}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    fields = FIELDS[group]
    seen, out, page = set(), [], 1
    while True:
        body = {"filters": {"award_type_codes": GROUPS[group], "place_of_performance_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30", "date_type": "date_signed"}]},
                "fields": fields, "limit": 100, "page": page, "sort": "Award ID", "order": "asc"}
        for attempt in range(5):
            try:
                r = requests.post(API, json=body, headers=UA, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                r = None
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending FY{fy} {group} page {page}: {getattr(r, 'status_code', r)}")
        d = r.json()
        for x in d["results"]:
            k = x.get("generated_internal_id") or x.get("internal_id")
            if k in seen:
                continue
            seen.add(k)
            out.append([x.get("Award ID") or "", x.get("Award Amount") or 0.0, x.get("Total Outlays"), (x.get(fields[3]) or "").strip()])
        if not d["page_metadata"].get("hasNext"):
            break
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
    return out


def classify(group, key, cw):
    """(function, confidence, listing prefix) of one award's listing (grants) or awarding agency (contracts)."""
    if group == "contracts":
        pre = AGENCY.get(key)
        if not pre or ("cfda_agency", pre) not in cw:
            UNMAPPED.add(key or "unknown")
            return "other", "low", ""
        return cw[("cfda_agency", pre)]["function_category"], "low", pre
    pre = key.split(".")[0]
    if ("cfda", key) not in cw and ("cfda_agency", pre) not in cw:
        UNMAPPED.add(pre or "unknown")
        return "other", "low", pre
    fn, conf = spending.cfda_function(key, cw=cw)
    return fn, conf, pre


def build(refresh=False, check=False, today=None):
    UNMAPPED.clear()
    years = list(range(FIRST_YEAR, last_year(today) + 1))
    cw = spending.load_crosswalk()
    names = {r[0]: r[1] for r in json.loads(FED.read_text(encoding="utf-8"))["rows"]} if FED.exists() else {}
    groups, functions, confs = list(GROUPS), spending.FUNCTIONS, spending.CONFIDENCE
    n = len(years)
    zero = lambda: [0.0] * n
    totals = {g: {"obligated": zero(), "paid": zero(), "awards": [0] * n, "over_n": [0] * n, "over_usd": zero(), "no_outlay": [0] * n} for g in groups}
    progs, excluded, agencies = {}, {}, {}
    for yi, fy in enumerate(years):
        for g in groups:
            if check and not (CACHE / f"{fy}_{g}.json").exists():
                raise FileNotFoundError(f"no cache for FY{fy} {g}: run python federal_outlays.py")
            res = fetch(fy, g, refresh=refresh and not check and fy >= years[-1] - 1)
            for aid, amount, outlays, key in res:
                if g == "grants" and key in EXCLUDE:
                    e = excluded.setdefault(key, {"obligated": zero(), "paid": zero()})
                    e["obligated"][yi] += amount
                    e["paid"][yi] += outlays or 0.0
                    continue
                if amount <= 0:      # de-obligated or zero awards carry no share to pay out
                    continue
                t = totals[g]
                paid = min(outlays or 0.0, amount)
                t["obligated"][yi] += amount
                t["paid"][yi] += max(paid, 0.0)
                t["awards"][yi] += 1
                if outlays is None:
                    t["no_outlay"][yi] += 1
                elif outlays > amount * 1.001 + 1:
                    t["over_n"][yi] += 1
                    t["over_usd"][yi] += outlays - amount
                fn, conf, pre = classify(g, key, cw)
                if pre and ("cfda_agency", pre) in cw:
                    agencies[pre] = cw[("cfda_agency", pre)]["name"]
                k = (key if g == "grants" else f"contracts:{key}", g)
                e = progs.setdefault(k, {"name": names.get(key, key) if g == "grants" else key, "fn": fn, "conf": conf, "pre": pre, "o": zero(), "p": zero()})
                e["o"][yi] += amount
                e["p"][yi] += max(paid, 0.0)
    rows, rest = [], {}
    for (key, g), e in progs.items():
        if sum(e["o"]) >= KEEP:
            rows.append([key, e["name"], groups.index(g), functions.index(e["fn"]), confs.index(e["conf"]), [round(v) for v in e["o"]], [round(v) for v in e["p"]]])
        else:
            rk = (e["pre"], g, e["fn"])
            r = rest.setdefault(rk, [zero(), zero()])
            r[0] = [a + b for a, b in zip(r[0], e["o"])]
            r[1] = [a + b for a, b in zip(r[1], e["p"])]
    for (pre, g, fn), (o, p) in rest.items():
        if any(round(x) for x in o):
            rows.append([f"{pre or 'contracts'}.*", "Other programs", groups.index(g), functions.index(fn), confs.index("low"), [round(x) for x in o], [round(x) for x in p]])
    rows.sort(key=lambda r: (r[2], -sum(r[5]), r[0]))
    tot = {g: {k: [round(x) for x in v] for k, v in t.items()} for g, t in totals.items()}
    for g in groups:   # the rows add up to the totals (rounding aside)
        for yi in range(n):
            so = sum(r[5][yi] for r in rows if r[2] == groups.index(g))
            sp = sum(r[6][yi] for r in rows if r[2] == groups.index(g))
            if abs(so - tot[g]["obligated"][yi]) > len(rows) or abs(sp - tot[g]["paid"][yi]) > len(rows):
                raise ValueError(f"{g} FY{years[yi]}: rows do not add up to the totals")
    doc = {"version": 1, "built": date.today().isoformat(), "source": "usaspending", "unit": "USD", "level": "federal_to_pr",
           "fiscal_year_basis": "federal_oct_sep", "year_is": "signed", "stage": ["obligated", "outlaid"],
           "crosswalk": "reviewed 2026-11-09 (dictionary_src/spending_crosswalk.csv, HANDOFF decisions 76 and 92)",
           "years": years, "groups": groups, "functions": functions, "confidence": confs, "agencies": dict(sorted(agencies.items())),
           "totals": tot, "rows": rows,
           "excluded": {k: {"why": EXCLUDE[k], "obligated": [round(x) for x in v["obligated"]], "paid": [round(x) for x in v["paid"]]} for k, v in sorted(excluded.items())},
           "unmapped": sorted(UNMAPPED)}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_outlays.json {'is current' if same else 'differs from the cache: run python federal_outlays.py'}")
        return same
    OUT.write_text(text, encoding="utf-8", newline="\n")
    for yi, fy in enumerate(years):
        o = sum(tot[g]["obligated"][yi] for g in groups)
        p = sum(tot[g]["paid"][yi] for g in groups)
        log(f"  signed FY{fy}: ${o / 1e9:6.2f} B obligated, ${p / 1e9:6.2f} B paid out ({100 * p / o:.0f}%), {sum(tot[g]['awards'][yi] for g in groups)} awards")
    log(f"  wrote spending_outlays.json: {len(rows)} rows, {OUT.stat().st_size / 1e3:.0f} KB; unmapped {sorted(UNMAPPED)}")
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
