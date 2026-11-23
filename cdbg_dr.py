"""Disaster recovery grants by municipio for the PR Data Observatory: where the HUD Community Development Block Grant disaster recovery and mitigation
money (CDBG-DR and CDBG-MIT) that the Puerto Rico Department of Housing (Vivienda) passed on as subawards was placed, by federal fiscal year
(Public spending PR 9, step 6 of the Phase 0 build order, HANDOFF decision 89).

    python cdbg_dr.py              # build site/data/spending_cdbgdr.json (downloads only the fiscal years missing from cache/spending/usaspending/)
    python cdbg_dr.py --refresh    # download the last two fiscal years again
    python cdbg_dr.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: USAspending.gov's API (spending_by_geography), filtered to Vivienda's disaster grants (DR_AWARDS, assistance listing 14.228: the HUD
grant codes DM, DP, DE, DF, DZ, DN and DI; the yearly block grants, DC, and the COVID grant, DW, are left out). For each final federal fiscal year
(October to September, final from November 15, as in federal_awards.py) four requests: subawards by municipio (place of performance), subawards for
Puerto Rico as a whole, and the prime grants for Puerto Rico as a whole.

Why subawards. USAspending places the prime grants where Vivienda is, in San Juan. The first-tier subawards that Vivienda reports under the federal
transparency law (FFATA: to municipalities, contractors and nonprofits, usually $30,000 or more) carry the place where the work is done. They are part
of the prime grants, never added to them, and cover only part of the money: what Vivienda spends through its own programs is not placed. Subawards
for Puerto Rico that name no municipio are kept as "not placed", so nothing disappears.

Records (spending.FIELDS) go to cache/spending/records/usaspending_cdbgdr.csv and are checked with spending.validate: level federal_to_pr, stage
obligated, dedup group cdbg_dr (the prime grants are also in spending_federal.json and the subawards are a part of them).

output: site/data/spending_cdbgdr.json. years; awards: the grant numbers read; geo: ids and names of the 78 municipios; by_muni: dollars per year in
geo order; unplaced: subawards for Puerto Rico with no municipio, per year; subawards: their total per year; prime: the prime grants' obligations per
year; population and population_basis: as in spending_pica.json (one basis for per-resident figures, decision 73 (3)); grants: [grant number,
obligated over the grant's life, outlays to date] for each prime grant, from USAspending's award search (HANDOFF decision 109, step 3), read on
grants_read. Outlays are what the Treasury has paid to the Department of Housing (its draws). HUD's monthly CDBG-DR expenditure and CDBG-MIT financial
reports are used only as a check (docs/spending.md), never published.
"""

import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import federal_awards
import spending

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "spending" / "usaspending"
OUT = ROOT / "site" / "data" / "spending_cdbgdr.json"
PICA = ROOT / "site" / "data" / "spending_pica.json"
RECORDS = ROOT / "cache" / "spending" / "records" / "usaspending_cdbgdr.csv"
API = "https://api.usaspending.gov/api/v2/search/spending_by_geography/"
AWARDS_API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
SITE = "https://www.usaspending.gov/search"
FIRST_YEAR = 2019
# Vivienda's disaster grants (HUD grant numbers): 2017 hurricanes (DM, DP), mitigation (DP-0002), the electrical grid (DE), later disasters (DF, DZ,
# DN) and the 2008 floods (DI). A new grant number for Puerto Rico appears in federal_awards' 14.228 rows; add it here when it is a disaster grant.
DR_AWARDS = ["B-17-DM-72-0001", "B-18-DP-72-0001", "B-18-DP-72-0002", "B-18-DE-72-0001", "B-19-DP-72-0001", "B-19-DF-72-0001", "B-21-DZ-72-0001",
             "B-23-DN-72-0001", "B-23-DN-72-0002", "B-08-DI-72-0001"]


def log(*a):
    print(*a, flush=True)


def query(fy, sub, layer):
    body = {"scope": "place_of_performance", "geo_layer": layer, "subawards": sub,
            "filters": {"time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}],
                        "place_of_performance_locations": [{"country": "USA", "state": "PR"}], "award_ids": DR_AWARDS}}
    if layer == "state":
        body["geo_layer_filters"] = ["PR"]
    for attempt in range(4):
        try:
            r = requests.post(API, json=body, headers=federal_awards.UA, timeout=240)
            if r.status_code == 200:
                return [{"code": x.get("shape_code") or "", "name": x.get("display_name") or "", "amount": x.get("aggregated_amount") or 0.0}
                        for x in r.json().get("results", [])]
        except requests.RequestException:
            r = None
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"USAspending CDBG-DR FY{fy} {layer} {'sub' if sub else 'prime'}: {getattr(r, 'status_code', r)}")


def fetch(fy, refresh=False):
    p = CACHE / f"cdbgdr_{fy}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    d = {"awards": DR_AWARDS, "sub_county": query(fy, True, "county"), "sub_state": query(fy, True, "state"), "prime_state": query(fy, False, "state")}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    return d


def fetch_grants(refresh=False):
    """Each prime grant's obligation over its life and its outlays to date (cached with the date read; decision 109, step 3)."""
    p = CACHE / "cdbgdr_grants.json"
    if p.exists() and not refresh:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("awards") == DR_AWARDS:
            return d
    body = {"filters": {"award_type_codes": ["02", "03", "04", "05"], "award_ids": DR_AWARDS, "time_period": [{"start_date": "2007-10-01", "end_date": f"{date.today().year + 1}-09-30"}]},
            "fields": ["Award ID", "Award Amount", "Total Outlays"], "limit": 100, "page": 1, "sort": "Award Amount", "order": "desc"}
    for attempt in range(4):
        try:
            r = requests.post(AWARDS_API, json=body, headers=federal_awards.UA, timeout=240)
            if r.status_code == 200:
                break
        except requests.RequestException:
            r = None
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"USAspending CDBG-DR grants: {getattr(r, 'status_code', r)}")
    got = {x["Award ID"]: [x.get("Award Amount") or 0.0, x.get("Total Outlays") or 0.0] for x in r.json()["results"]}
    d = {"awards": DR_AWARDS, "read": date.today().isoformat(), "rows": [[a, *got.get(a, [0.0, 0.0])] for a in DR_AWARDS]}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8", newline="\n")
    return d


def build(refresh=False, check=False, today=None):
    years = list(range(FIRST_YEAR, federal_awards.last_year(today) + 1))
    pica = json.loads(PICA.read_text(encoding="utf-8"))
    ids, names = pica["geo"]["ids"], pica["geo"]["names"]
    at = {g: i for i, g in enumerate(ids)}
    by_muni = [[0.0] * len(ids) for _ in years]
    unplaced, subs, prime, records = [0.0] * len(years), [0.0] * len(years), [0.0] * len(years), []
    retrieved = date.today().isoformat()
    for yi, fy in enumerate(years):
        if check and not (CACHE / f"cdbgdr_{fy}.json").exists():
            raise FileNotFoundError(f"no cache for FY{fy}: run python cdbg_dr.py")
        d = fetch(fy, refresh=refresh and not check and fy >= years[-1] - 1)
        if d.get("awards") != DR_AWARDS:
            if check:
                raise ValueError(f"the cache for FY{fy} was read with other grant numbers: run python cdbg_dr.py --refresh")
            d = fetch(fy, refresh=True)
        for x in d["sub_county"]:
            if x["code"] not in at:
                raise ValueError(f"FY{fy}: '{x['code']}' ({x['name']}) is not a municipio id")
            by_muni[yi][at[x["code"]]] += x["amount"]
        subs[yi] = sum(x["amount"] for x in d["sub_state"])
        prime[yi] = sum(x["amount"] for x in d["prime_state"])
        unplaced[yi] = subs[yi] - sum(by_muni[yi])
        rec = {"fiscal_year": fy, "fiscal_year_basis": "federal_oct_sep", "level": "federal_to_pr", "source_system": "usaspending", "stage": "obligated",
               "fund_origin": "federal", "agency_or_entity": "Puerto Rico Department of Housing (subawards)", "program": "14.228 CDBG-DR and CDBG-MIT",
               "function_category": "housing", "concept_of_expense": "transfers", "recipient_type": "mixed", "allocation_driver": "",
               "allocation_confidence": "high", "population_basis": "", "per_capita_usd": "", "dedup_group": "cdbg_dr", "retrieved_at": retrieved,
               "source_url": SITE, "terms_of_use": federal_awards.TERMS}
        for i, v in enumerate(by_muni[yi]):
            if v:
                records.append({**rec, "municipio_fips": ids[i], "allocation_tier": "direct", "amount_usd": round(v)})
        if round(unplaced[yi]):
            records.append({**rec, "municipio_fips": "", "allocation_tier": "island_wide", "amount_usd": round(unplaced[yi])})
    bad = [p for r in records for p in spending.validate({k: str(v) for k, v in r.items()})]
    if bad:
        raise ValueError(f"records fail the schema: {bad[:5]}")
    doc = {"version": 1, "built": retrieved, "source": "usaspending", "unit": "USD", "level": "federal_to_pr", "fiscal_year_basis": "federal_oct_sep",
           "stage": "obligated", "program": "14.228 CDBG-DR and CDBG-MIT (Puerto Rico Department of Housing)", "awards": DR_AWARDS, "years": years,
           "geo": {"ids": ids, "names": names}, "by_muni": [[round(v) for v in yr] for yr in by_muni], "unplaced": [round(v) for v in unplaced],
           "subawards": [round(v) for v in subs], "prime": [round(v) for v in prime], "population": pica["population"],
           "population_basis": pica["population_basis"], "dedup_group": "cdbg_dr"}
    if check and not (CACHE / "cdbgdr_grants.json").exists():
        raise FileNotFoundError("no cache for the grants: run python cdbg_dr.py")
    g = fetch_grants(refresh=refresh and not check)
    doc["grants"] = [[a, round(o), round(p)] for a, o, p in g["rows"]]
    doc["grants_read"] = g["read"]
    for yi, fy in enumerate(years):
        if doc["unplaced"][yi] < -len(ids):
            raise ValueError(f"FY{fy}: the municipios add up to more than the subawards for Puerto Rico")
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_cdbgdr.json {'is current' if same else 'differs from the cache: run python cdbg_dr.py'}")
        return same
    OUT.write_text(text, encoding="utf-8")
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORDS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spending.FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    for yi, fy in enumerate(years):
        log(f"  FY{fy}: prime ${prime[yi] / 1e9:6.2f} B, subawards ${subs[yi] / 1e9:5.2f} B, in municipios ${sum(by_muni[yi]) / 1e9:5.2f} B")
    log(f"  wrote spending_cdbgdr.json: {OUT.stat().st_size / 1e3:.0f} KB; {len(records)} records in {RECORDS.name}")
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
