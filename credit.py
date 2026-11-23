"""Credit: insured bank branches and their deposits (FDIC), and home loans (HMDA), by municipio and year. HANDOFF decision 107, step 4; docs/credit.md.

    python credit.py              # build site/data/credit_series.json from the cache
    python credit.py --refresh    # download the FDIC and HMDA files again (the HMDA years already cached are kept: a year's file is final)
    python credit.py --check      # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources, no key:
- FDIC Summary of Deposits (api.fdic.gov/banks/sod): every office of an FDIC-insured bank on June 30 of each year since 2000, with the deposits the bank
  books at that office. Puerto Rico's cooperativas de ahorro y crédito are insured by COSSEC, not the FDIC, and are not in it; nor are credit unions or
  international banking entities. Deposits are where the bank books them, not where the depositors live: a main office books far more than its share.
- HMDA, the Home Mortgage Disclosure Act data (the FFIEC/CFPB Data Browser, ffiec.cfpb.gov), every year since 2018 (the year the current record
  layout began): one row for each application for a home loan that a reporting lender received. The rows carry the applicant's income, age, race and
  sex, so nothing below the municipio is published and a municipio's amount and denial share have no value under MIN_LOANS loans or decided
  applications. Loan purchases between lenders (action 6) are left out: they are not new lending and would count a loan twice.
  The public file gives each loan's amount as the midpoint of its $10,000 band, so a sum is within $5,000 a loan of the true amount.

Output: credit_series.json (the shape of nightlights_series.json: yearly values for the 78 municipios and Puerto Rico, which is the last value).

No points layer: since 2023 the FDIC places about half the offices at the centre of their ZIP code (geocode "M", the same point as the 2022 "US_Zipcode"
match), so only 113 of the 260 offices of June 2026 have a street-level location. A map of the other half would put banks where they are not.
The notes give the count; the offices' addresses could be geocoded later (step 6 of decision 107 needs bank points).
"""

import collections
import csv
import datetime
import io
import json
import sys
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "credit"
OUT = hs.OUT / "credit_series.json"
log = hs.log
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}

SOD_URL = "https://api.fdic.gov/banks/sod"
SOD_FIRST = 2000
SOD_FIELDS = "YEAR,UNINUMBR,CERT,NAMEFULL,NAMEBR,CITYBR,STCNTYBR,DEPSUMBR,BRSERTYP,SIMS_LATITUDE,SIMS_LONGITUDE,SIMS_PROJECTION"
# the FDIC's geocode codes that place an office at its address or street (the others place it at a ZIP code or town centre, or give a match score)
STREET_LEVEL = {"EXACT", "StreetAddress", "StreetAddressExt", "PointAddress", "POINTADDRESS", "StreetName", "STREETNAME", "StreetInt", "STREETINT",
                "DistanceMarker", "ROADKM", "POI", "US_Streets", "US_STREETS"}
HMDA_URL = "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv?states=PR&years={y}"
HMDA_FIRST = 2018
MIN_LOANS = 10   # a municipio-year's amount and denial share need at least this many loans or decided applications (decision 107: counts and sums only, with a floor)

# HMDA action_taken codes (the FFIEC filing instructions)
MADE, APPROVED_NOT_ACCEPTED, DENIED, PURCHASED = "1", "2", "3", "6"
HOME_PURCHASE = "1"

G_BANK = "Economy · Banks and deposits (FDIC)"
G_HMDA = "Housing · Home loans (HMDA)"
SOURCES = {
    "fdic_sod": {"name": "FDIC Summary of Deposits", "url": "https://banks.data.fdic.gov/bankfind-suite/SOD",
                 "license": "US Government work",
                 "note": "Offices of FDIC-insured banks and the deposits booked at each, on June 30 of each year. Cooperativas (COSSEC) are not in it."},
    "hmda": {"name": "Home Mortgage Disclosure Act data (FFIEC and CFPB)", "url": "https://ffiec.cfpb.gov/data-browser/",
             "license": "US Government work",
             "note": "Applications for home loans reported by lenders, one row for each; the observatory publishes municipio counts and sums only."},
}


def fetch_sod(refresh):
    """Every Puerto Rico office of every year since SOD_FIRST, paged (the API gives at most 10,000 rows a call)."""
    p = CACHE / "sod.json"
    if refresh or not p.exists():
        rows, offset = [], 0
        while True:
            r = requests.get(SOD_URL, params={"filters": f"STALPBR:PR AND YEAR:[{SOD_FIRST} TO 2100]", "fields": SOD_FIELDS, "limit": 10000,
                                              "offset": offset, "sort_by": "ID", "format": "json"}, headers=UA, timeout=180)
            r.raise_for_status()
            d = r.json()
            rows += [x["data"] for x in d["data"]]
            offset += len(d["data"])
            if not d["data"] or offset >= d["meta"]["total"]:
                break
        if len(rows) != d["meta"]["total"]:
            raise SystemExit(f"credit: FDIC gave {len(rows)} rows of {d['meta']['total']}")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
        log(f"  downloaded the Summary of Deposits: {len(rows):,} office-years")
    return json.loads(p.read_text(encoding="utf-8"))


def hmda_years(refresh, check):
    """{year: path} of the HMDA files in the cache; with refresh, also the years after the last one cached, until the Data Browser has none."""
    CACHE.mkdir(parents=True, exist_ok=True)
    y = HMDA_FIRST
    out = {}
    while True:
        p = CACHE / f"hmda{y}.csv"
        if not p.exists() and refresh and not check:
            r = requests.get(HMDA_URL.format(y=y), headers=UA, timeout=600)
            if r.status_code in (400, 404) or not r.content.startswith(b"activity_year"):
                break   # the year is not published yet
            r.raise_for_status()
            p.write_bytes(r.content)
            log(f"  downloaded HMDA {y} ({len(r.content) / 1e6:.1f} MB)")
        if not p.exists():
            break
        out[y] = p
        y += 1
    if not out:
        raise SystemExit("credit: no HMDA year in the cache; run with --refresh")
    return out


def sod_figures(rows, ids):
    """{year: {geoid: [offices, deposits in $]}} and the offices whose municipio is not one of the 78 (none expected)."""
    by = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    stray = 0
    for x in rows:
        g = str(x["STCNTYBR"]).zfill(5)
        if g not in ids:
            stray += 1
            continue
        c = by[int(x["YEAR"])][g]
        c[0] += 1
        c[1] += (x["DEPSUMBR"] or 0) * 1000   # the FDIC gives thousands of dollars
    if stray:
        raise SystemExit(f"credit: {stray} FDIC offices name no Puerto Rico municipio")
    return by


def hmda_figures(path, ids):
    """{geoid or '72': {loans, purchase, amount, denied, decided}} for one year; '72' is Puerto Rico, rows with no municipio included."""
    f = collections.defaultdict(collections.Counter)
    no_muni = 0
    with open(path, encoding="utf-8", newline="") as fh:
        for x in csv.DictReader(fh):
            a = x["action_taken"]
            if a == PURCHASED:
                continue
            g = x["county_code"]
            keys = ["72"]
            if g in ids:
                keys.append(g)
            else:
                no_muni += 1
            for k in keys:
                c = f[k]
                if a == MADE:
                    c["loans"] += 1
                    c["amount"] += float(x["loan_amount"])
                    if x["loan_purpose"] == HOME_PURCHASE:
                        c["purchase"] += 1
                if a in (MADE, APPROVED_NOT_ACCEPTED, DENIED):
                    c["decided"] += 1
                if a == DENIED:
                    c["denied"] += 1
    return f, no_muni


def documents(sod_rows, hmda_paths):
    names, fips = hs.municipalities()
    ids = list(fips)
    sod = sod_figures(sod_rows, set(ids))
    sod_years = sorted(sod)
    hm = {}
    no_muni = {}
    for y, p in sorted(hmda_paths.items()):
        hm[y], no_muni[y] = hmda_figures(p, set(ids))
    hm_years = sorted(hm)

    def series(years, get):
        return {str(y): [get(y, g) for g in ids] + [get(y, "72")] for y in years}

    def sod_get(i):
        def get(y, g):
            if g == "72":
                return round(sum(v[i] for v in sod[y].values()))
            return round(sod[y][g][i]) if g in sod[y] else 0
        return get

    def hm_count(k):
        return lambda y, g: hm[y][g][k] if g in hm[y] else 0

    def hm_amount(y, g):
        c = hm[y].get(g)
        return round(c["amount"]) if c and c["loans"] >= MIN_LOANS else None

    def hm_denial(y, g):
        c = hm[y].get(g)
        return round(100 * c["denied"] / c["decided"], 1) if c and c["decided"] >= MIN_LOANS else None

    floor = f" A municipio with fewer than {MIN_LOANS} {{}} in a year has no value: the observatory does not publish a figure that could describe a few borrowers."
    coop = " Cooperativas de ahorro y crédito are insured by COSSEC, not the FDIC, and are not counted: a municipio with no bank office may still have a cooperativa."
    hmda_ref = f"Home Mortgage Disclosure Act data, Puerto Rico, {hm_years[0]}-{hm_years[-1]} (FFIEC and CFPB Data Browser)"
    sod_ref = f"FDIC Summary of Deposits, June 30 of each year, {sod_years[0]}-{sod_years[-1]}"
    vs = [
        {"key": "bank_branches", "group": G_BANK, "label": "Bank offices (FDIC-insured banks)", "unit": "offices", "d": 0, "type": "count",
         "sources": ["fdic_sod"], "ref": sod_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "The offices of FDIC-insured banks in the municipio on June 30: main offices, branches and limited-service offices, as the banks report them to the FDIC each year." + coop,
         "years": series(sod_years, sod_get(0))},
        {"key": "bank_deposits", "group": G_BANK, "label": "Deposits in bank offices (FDIC-insured banks)", "unit": "$", "d": 0, "type": "total$",
         "sources": ["fdic_sod"], "ref": sod_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "The deposits that FDIC-insured banks book at their offices in the municipio on June 30, in dollars of each year (not adjusted for inflation). Deposits are counted where the bank books them, not where the depositors live: a bank's main office books far more than its share, so San Juan holds most of the island's total." + coop,
         "years": series(sod_years, sod_get(1))},
        {"key": "hmda_loans", "group": G_HMDA, "label": "Home loans made (HMDA)", "unit": "loans", "d": 0, "type": "count",
         "sources": ["hmda"], "ref": hmda_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "Home loans that reporting lenders made for homes in the municipio during the year: to buy, refinance, improve or borrow against a home of 1 to 4 units or an apartment building. Loans bought from another lender are not counted again. Small lenders that do not have to report are missing, so this is less than all home lending.",
         "years": series(hm_years, hm_count("loans"))},
        {"key": "hmda_purchase_loans", "group": G_HMDA, "label": "Home purchase loans made (HMDA)", "unit": "loans", "d": 0, "type": "count",
         "sources": ["hmda"], "ref": hmda_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "The home loans made to buy a home in the municipio during the year (loan purpose: home purchase), without refinancing, home improvement and other purposes.",
         "years": series(hm_years, hm_count("purchase"))},
        {"key": "hmda_loan_amount", "group": G_HMDA, "label": "Amount of home loans made (HMDA)", "unit": "$", "d": 0, "type": "total$",
         "sources": ["hmda"], "ref": hmda_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "The sum of the home loans made in the municipio during the year, in dollars of each year. The public file gives each loan as the midpoint of its $10,000 band, so the sum is within $5,000 a loan of the true amount." + floor.format("loans"),
         "years": series(hm_years, hm_amount)},
        {"key": "hmda_denial_pct", "group": G_HMDA, "label": "Home loan applications denied (HMDA, %)", "unit": "%", "d": 1, "type": "rate",
         "sources": ["hmda"], "ref": hmda_ref, "family": "credit", "counted": False, "noPerHU": True,
         "definition": "Of the applications for a home loan in the municipio that a lender decided during the year (made, approved but not taken, or denied), the share denied. Applications withdrawn or closed as incomplete are left out. A denial depends on the applicant's income, debts and credit and on the home, which this share does not separate." + floor.format("decided applications"),
         "years": series(hm_years, hm_denial)},
    ]
    last = sod_years[-1]
    pr_hm = {y: hm[y]["72"] for y in hm_years}
    notes = {"fdic_years": f"{sod_years[0]}-{last}, June 30", "hmda_years": f"{hm_years[0]}-{hm_years[-1]}",
             "offices": {str(y): sum(v[0] for v in sod[y].values()) for y in sod_years},
             "hmda_island": {str(y): {"loans_made": pr_hm[y]["loans"], "amount": round(pr_hm[y]["amount"]), "denied": pr_hm[y]["denied"], "decided": pr_hm[y]["decided"]} for y in hm_years},
             "hmda_no_municipio": {str(y): no_muni[y] for y in hm_years},
             "floor": f"A municipio's HMDA amount and denial share need {MIN_LOANS} or more loans or decided applications in the year",
             "purchased_left_out": "HMDA action 6 (a loan bought from another lender) is not counted",
             "not_counted": "Cooperativas de ahorro y crédito (COSSEC), credit unions and international banking entities are not in the FDIC file",
             "check": "The HMDA loans made and their amount for Puerto Rico equal the Data Browser's own totals (2023: 13,550 loans, $2.24 billion)"}
    today = datetime.date.today().isoformat()
    years = sorted(set(sod_years) | set(hm_years))
    doc = {"built": today, "as_of": str(max(years)), "years": years, "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]},
           "vars": vs, "sources": SOURCES, "notes": notes}
    last_rows = [x for x in sod_rows if int(x["YEAR"]) == last]
    notes["located_at_street"] = {"year": last, "offices": len(last_rows), "street_level": sum(1 for x in last_rows if x.get("SIMS_PROJECTION") in STREET_LEVEL),
                                  "why_no_points": "The FDIC places the other offices at the centre of their ZIP code or town, so the observatory draws no office points"}
    return doc


def build(refresh=False, check=False):
    go = refresh and not check
    doc = documents(fetch_sod(go), hmda_years(refresh, check))
    stale = 0
    for p, d in ((OUT, doc),):
        text = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        if check:
            old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            same = old is not None and {**old, "built": None} == {**json.loads(text), "built": None}
            print(f"  {p.name}: {'matches' if same else 'DIFFERS'}")
            stale += not same
            continue
        p.write_text(text, encoding="utf-8", newline="\n")
        log(f"wrote {p.name} ({p.stat().st_size / 1024:.1f} KB)")
    if not check:
        n = doc["notes"]
        log(f"  offices: {n['offices']}")
        log(f"  HMDA Puerto Rico: {n['hmda_island']}")
    return 1 if stale else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
