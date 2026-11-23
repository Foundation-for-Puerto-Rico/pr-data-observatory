"""Federal money in Puerto Rico by function for the PR Data Observatory: what federal agencies obligated for work or benefits in Puerto Rico in each
federal fiscal year, by program (assistance listing), award type and function (Public spending PR 6, HANDOFF decision 83).

    python federal_awards.py              # build site/data/spending_federal.json (downloads only the fiscal years missing from cache/spending/usaspending/)
    python federal_awards.py --refresh    # download every fiscal year again
    python federal_awards.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: USAspending.gov's API (api.usaspending.gov/api/v2/search/spending_by_category/), place of performance Puerto Rico, one call per
federal fiscal year (October to September, named by the year it ends) and award type. Assistance (grants, direct payments, loans, insurance and other)
is read by assistance listing (CFDA); contracts have no listing and are read by awarding agency. Only finished fiscal years are read.

Function. Each listing takes its row of the function crosswalk (dictionary_src/spending_crosswalk.csv, reviewed on 2026-11-09, HANDOFF decision 92;
spending.cfda_function), else its agency's default (low confidence). A contract takes the default of its awarding agency (CONTRACT_AGENCY).

Loans are the estimated subsidy cost to the government, not the amount lent, as USAspending reports them; they can be negative when an estimate is revised.

Never add these figures to the Commonwealth budget (spending_state.json): its federal funds are federal grants here too (dedup group ogp_federal).
FEMA Public Assistance (97.036) and Hazard Mitigation (97.039) are counted from OpenFEMA elsewhere, so their records carry the dedup groups fema_pa and
fema_hma. Nothing here is placed in a municipio; the municipio figures stay in economy_series.json (fed_awards_total and its parts).

output: site/data/spending_federal.json. years; groups (award types); functions; agencies: listing prefix to agency name; totals: USAspending's sum per
year and group; rows: [program code, name, group, function, confidence, [whole dollars per year]] for every program with at least $1 million in some year;
the rest are added into one row per agency, group and function, named "Other programs" (code "<prefix>.*").
"""

import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import spending

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "spending" / "usaspending"
OUT = ROOT / "site" / "data" / "spending_federal.json"
RECORDS = ROOT / "cache" / "spending" / "records" / "usaspending.csv"
API = "https://api.usaspending.gov/api/v2/search/spending_by_category/"
SITE = "https://www.usaspending.gov/search"
TERMS = "No license stated for the data (the API's source code is CC0-1.0)"
FIRST_YEAR = 2008   # USAspending's search API answers from federal fiscal year 2008; earlier years exist only in its bulk archives (2026-11-17)
KEEP = 1_000_000          # programs below this in every year are added into their agency's "Other programs"
UA = {"User-Agent": "PR Data Observatory (pr-digital-twin)"}

# award type groups (USAspending award_type_codes) and the category each is read by
GROUPS = {
    "grants": (["02", "03", "04", "05"], "cfda"),
    "direct_payments": (["06", "10"], "cfda"),
    "contracts": (["A", "B", "C", "D"], "awarding_agency"),
    "loans": (["07", "08"], "cfda"),
    "other": (["09", "11", "-1"], "cfda"),
}
RECIPIENT = {"grants": "mixed", "direct_payments": "individual_aggregate", "contracts": "private", "loans": "mixed", "other": "mixed"}
# a contract's awarding agency (USAspending's abbreviation) to the assistance listing prefix whose default function it takes
CONTRACT_AGENCY = {"USDA": "10", "DOC": "11", "DOD": "12", "HUD": "14", "DOI": "15", "DOJ": "16", "DOL": "17", "DOS": "19", "DOT": "20", "TREAS": "21",
                   "FCC": "32", "GSA": "39", "NASA": "43", "NSF": "47", "SBA": "59", "VA": "64", "EPA": "66", "DOE": "81", "ED": "84", "HHS": "93",
                   "CNCS": "94", "SSA": "96", "DHS": "97"}
DEDUP = {"97.036": "fema_pa", "97.039": "fema_hma"}
UNMAPPED = set()          # listing prefixes with no crosswalk row: counted as "other" and named in the file


def log(*a):
    print(*a, flush=True)


def last_year(today=None):
    """The last final federal fiscal year: a year ends on September 30 and, as for economy_series.py, counts as final from November 15."""
    t = today or date.today()
    return t.year if (t.month, t.day) >= (11, 15) else t.year - 1


def fetch_one(fy, group, refresh=False):
    """USAspending's results for one fiscal year and award group (cached; every page)."""
    p = CACHE / f"{fy}_{group}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    codes, cat = GROUPS[group]
    out, page = [], 1
    while True:
        body = {"category": cat, "limit": 100, "page": page,
                "filters": {"time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}],
                            "place_of_performance_locations": [{"country": "USA", "state": "PR"}], "award_type_codes": codes}}
        for attempt in range(4):
            try:
                r = requests.post(API + cat + "/", json=body, headers=UA, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                r = None
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending FY{fy} {group}: {getattr(r, 'status_code', r)}")
        d = r.json()
        out += [{"code": x.get("code") or "", "name": (x.get("name") or "").strip(), "amount": x.get("amount") or 0.0} for x in d["results"]]
        if not d["page_metadata"].get("hasNext"):
            break
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    return out


def classify(group, code, cw):
    """(function, confidence, listing prefix) of one result."""
    if group == "contracts":
        pre = CONTRACT_AGENCY.get(code)
        if not pre:
            return "other", "low", ""
        return cw[("cfda_agency", pre)]["function_category"], "low", pre
    if code == "none":   # assistance with no listing (older years): no function can be read
        return "other", "low", ""
    pre = code.split(".")[0]
    if ("cfda", code) not in cw and ("cfda_agency", pre) not in cw:
        UNMAPPED.add(pre)
        return "other", "low", pre
    fn, conf = spending.cfda_function(code, cw=cw)
    return fn, conf, pre


def build(refresh=False, check=False, today=None):
    UNMAPPED.clear()
    years = list(range(FIRST_YEAR, last_year(today) + 1))
    cw = spending.load_crosswalk()
    groups, functions, confs = list(GROUPS), spending.FUNCTIONS, spending.CONFIDENCE
    progs, totals, records, agencies = {}, {}, [], {}
    retrieved = date.today().isoformat()
    for yi, fy in enumerate(years):
        for g in groups:
            if check and not (CACHE / f"{fy}_{g}.json").exists():
                raise FileNotFoundError(f"no cache for FY{fy} {g}: run python federal_awards.py")
            res = fetch_one(fy, g, refresh=refresh and not check and fy >= years[-1] - 1)
            totals.setdefault(g, [0.0] * len(years))[yi] += sum(x["amount"] for x in res)
            for x in res:
                if not x["amount"]:
                    continue
                if g != "contracts" and not x["code"]:   # older years have assistance with no listing (FY2008 on): one row, function "other"
                    x = {**x, "code": "none", "name": x["name"] or "No assistance listing"}
                fn, conf, pre = classify(g, x["code"], cw)
                if pre and ("cfda_agency", pre) in cw:
                    agencies[pre] = cw[("cfda_agency", pre)]["name"]
                code = x["code"] if g != "contracts" else f"contracts:{x['code']}"
                k = (code, g)
                e = progs.setdefault(k, {"name": x["name"], "fn": fn, "conf": conf, "pre": pre, "v": [0.0] * len(years)})
                e["v"][yi] += x["amount"]
                records.append({"municipio_fips": "", "fiscal_year": fy, "fiscal_year_basis": "federal_oct_sep", "level": "federal_to_pr",
                                "source_system": "usaspending", "stage": "obligated", "fund_origin": "federal",
                                "agency_or_entity": x["name"] if g == "contracts" else agencies.get(pre, pre or "unknown"),
                                "program": "" if g == "contracts" else f"{x['code']} {x['name']}", "function_category": fn,
                                "concept_of_expense": "other", "recipient_type": RECIPIENT[g], "allocation_tier": "island_wide", "allocation_driver": "",
                                "allocation_confidence": conf, "amount_usd": round(x["amount"]), "population_basis": "", "per_capita_usd": "",
                                "dedup_group": DEDUP.get(x["code"], "") if g != "contracts" else "", "retrieved_at": retrieved, "source_url": SITE,
                                "terms_of_use": TERMS})
    bad = [p for r in records for p in spending.validate({k: str(v) for k, v in r.items()})]
    if bad:
        raise ValueError(f"records fail the schema: {bad[:5]}")
    rows, rest = [], {}
    for (code, g), e in progs.items():
        if max(abs(v) for v in e["v"]) >= KEEP:
            rows.append([code, e["name"], groups.index(g), functions.index(e["fn"]), confs.index(e["conf"]), [round(v) for v in e["v"]]])
        else:
            k = (e["pre"], g, e["fn"])
            rest.setdefault(k, [0.0] * len(years))
            rest[k] = [a + b for a, b in zip(rest[k], e["v"])]
    for (pre, g, fn), v in rest.items():
        if any(round(x) for x in v):
            rows.append([f"{pre or 'contracts'}.*", "Other programs", groups.index(g), functions.index(fn), confs.index("low"), [round(x) for x in v]])
    rows.sort(key=lambda r: (r[2], -sum(r[5]), r[0]))
    doc = {"version": 1, "built": retrieved, "source": "usaspending", "unit": "USD", "level": "federal_to_pr", "fiscal_year_basis": "federal_oct_sep",
           "stage": "obligated", "crosswalk": "reviewed 2026-11-09 (dictionary_src/spending_crosswalk.csv, HANDOFF decisions 76 and 92)", "years": years,
           "groups": groups, "functions": functions, "confidence": confs, "agencies": dict(sorted(agencies.items())),
           "totals": {g: [round(v) for v in totals[g]] for g in groups}, "rows": rows,
           "dedup": dict(DEDUP), "unmapped": sorted(UNMAPPED)}
    for g in groups:
        for yi in range(len(years)):
            s = sum(r[5][yi] for r in rows if r[2] == groups.index(g))
            if abs(s - doc["totals"][g][yi]) > len(rows):
                raise ValueError(f"{g} FY{years[yi]}: rows add up to {s}, USAspending's total is {doc['totals'][g][yi]}")
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_federal.json {'is current' if same else 'differs from the cache: run python federal_awards.py'}")
        return same
    OUT.write_text(text, encoding="utf-8")
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORDS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spending.FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    for yi, fy in enumerate(years):
        log(f"  FY{fy}: ${sum(doc['totals'][g][yi] for g in groups) / 1e9:6.2f} B")
    log(f"  wrote spending_federal.json: {len(rows)} rows, {OUT.stat().st_size / 1e3:.0f} KB; {len(records)} records in {RECORDS.name}")
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
