"""Community Development Block Grants by municipio for the PR Data Observatory: where HUD's yearly CDBG money (not the disaster grants, which are in
cdbg_dr.py) went in Puerto Rico, by federal fiscal year (Disaster funding and need page, HANDOFF decision 100).

    python cdbg_regular.py              # build site/data/spending_cdbg.json (downloads only what is missing from cache/spending/usaspending/)
    python cdbg_regular.py --refresh    # download the grant list and the last two fiscal years again
    python cdbg_regular.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: USAspending.gov's API, as in cdbg_dr.py. HUD pays the yearly CDBG in Puerto Rico two ways, which together reach the 78 municipios:
  entitlement   assistance listing 14.218, HUD grant code MC: HUD pays the larger municipios directly (27 in fiscal years 2024 and 2025). The prime grant
                is placed in the municipio that receives it. The grant list is read from USAspending's award search (spending_by_award) and cached; the
                COVID grants of the same listing (code MW, CDBG-CV) are left out.
  state         assistance listing 14.228, HUD grant code DC: the state program. HUD pays the Puerto Rico Department of Housing (until 2018, the Office
                of the Commissioner for Municipal Affairs), which passes the money to the other municipios as subawards. The first-tier subawards
                reported under the federal transparency law (FFATA) carry the municipio; the prime grant is placed in San Juan, where the agency is.
                Subawards for Puerto Rico that name no municipio are kept as "not placed".
For each final federal fiscal year (October to September, final from November 15, as in federal_awards.py) five requests to spending_by_geography:
entitlement grants by municipio and for Puerto Rico, state subawards by municipio and for Puerto Rico, and the state prime grant for Puerto Rico.
Subawards often arrive a year or more after the prime grant, so the latest year can have none yet.

Records (spending.FIELDS) go to cache/spending/records/usaspending_cdbg.csv and are checked with spending.validate: level federal_to_pr, stage
obligated, dedup group cdbg (the prime grants are also in spending_federal.json, rows 14.218 and 14.228, and the subawards are a part of them).

output: site/data/spending_cdbg.json. years; awards: {entitlement: grant numbers, state: grant numbers}; geo: ids and names of the 78 municipios;
entitlement: dollars per year in geo order (prime grants); entitlement_total: for Puerto Rico per year; state_by_muni: subawards per year in geo order;
state_unplaced: state subawards that name no municipio, per year; state_subawards: their total per year; state_prime: the state grant's obligations
per year; population and population_basis: as in spending_pica.json.
"""

import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import cdbg_dr
import federal_awards
import spending

ROOT = Path(__file__).parent
CACHE = ROOT / "cache" / "spending" / "usaspending"
OUT = ROOT / "site" / "data" / "spending_cdbg.json"
PICA = ROOT / "site" / "data" / "spending_pica.json"
RECORDS = ROOT / "cache" / "spending" / "records" / "usaspending_cdbg.csv"
AWARDS_API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIRST_YEAR = cdbg_dr.FIRST_YEAR
GRANTS = ["02", "03", "04", "05"]   # USAspending's grant award types


def log(*a):
    print(*a, flush=True)


def state_awards(last):
    """The state program's grant numbers: one a year, B-yy-DC-72-0001, from 2015 to the year after the last fiscal year read."""
    return [f"B-{y % 100:02d}-DC-72-0001" for y in range(2015, last + 2)]


def entitlement_awards(refresh=False, check=False):
    """The entitlement grants (code MC) to Puerto Rico recipients, read from USAspending's award search (every page) and cached."""
    p = CACHE / "cdbg_entitlement_awards.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if check:
        raise FileNotFoundError("no cache of the entitlement grants: run python cdbg_regular.py")
    ids, page = set(), 1
    while True:
        body = {"filters": {"award_type_codes": GRANTS, "program_numbers": ["14.218"], "recipient_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": "2007-10-01", "end_date": date.today().isoformat()}]},
                "fields": ["Award ID"], "limit": 100, "page": page, "sort": "Award ID", "order": "asc"}
        for attempt in range(4):
            try:
                r = requests.post(AWARDS_API, json=body, headers=federal_awards.UA, timeout=240)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                r = None
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending award search, page {page}: {getattr(r, 'status_code', r)}")
        d = r.json()
        ids |= {x["Award ID"] for x in d.get("results", []) if "-MC-72-" in (x.get("Award ID") or "")}
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
    out = sorted(ids)
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def query(fy, sub, layer, awards):
    body = {"scope": "place_of_performance", "geo_layer": layer, "subawards": sub,
            "filters": {"time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}],
                        "place_of_performance_locations": [{"country": "USA", "state": "PR"}], "award_ids": awards}}
    if layer == "state":
        body["geo_layer_filters"] = ["PR"]
    for attempt in range(4):
        try:
            r = requests.post(cdbg_dr.API, json=body, headers=federal_awards.UA, timeout=240)
            if r.status_code == 200:
                return [{"code": x.get("shape_code") or "", "name": x.get("display_name") or "", "amount": x.get("aggregated_amount") or 0.0}
                        for x in r.json().get("results", [])]
        except requests.RequestException:
            r = None
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"USAspending CDBG FY{fy} {layer} {'sub' if sub else 'prime'}: {getattr(r, 'status_code', r)}")


def fetch(fy, awards, refresh=False):
    p = CACHE / f"cdbg_{fy}.json"
    if p.exists() and not refresh:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("awards") == awards:
            return d
    ent, st = awards["entitlement"], awards["state"]
    d = {"awards": awards, "ent_county": query(fy, False, "county", ent), "ent_state": query(fy, False, "state", ent),
         "sub_county": query(fy, True, "county", st), "sub_state": query(fy, True, "state", st), "prime_state": query(fy, False, "state", st)}
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    return d


def build(refresh=False, check=False, today=None):
    years = list(range(FIRST_YEAR, federal_awards.last_year(today) + 1))
    awards = {"entitlement": entitlement_awards(refresh=refresh and not check, check=check), "state": state_awards(years[-1])}
    pica = json.loads(PICA.read_text(encoding="utf-8"))
    ids, names = pica["geo"]["ids"], pica["geo"]["names"]
    at = {g: i for i, g in enumerate(ids)}
    ent = [[0.0] * len(ids) for _ in years]
    sub = [[0.0] * len(ids) for _ in years]
    ent_total, unplaced, subs, prime, records = [0.0] * len(years), [0.0] * len(years), [0.0] * len(years), [0.0] * len(years), []
    retrieved = date.today().isoformat()

    def place(rows, out, fy):
        for x in rows:
            if x["code"] not in at:
                raise ValueError(f"FY{fy}: '{x['code']}' ({x['name']}) is not a municipio id")
            out[at[x["code"]]] += x["amount"]

    for yi, fy in enumerate(years):
        p = CACHE / f"cdbg_{fy}.json"
        if check:
            if not p.exists():
                raise FileNotFoundError(f"no cache for FY{fy}: run python cdbg_regular.py")
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("awards") != awards:
                raise ValueError(f"the cache for FY{fy} was read with other grant numbers: run python cdbg_regular.py --refresh")
        else:
            d = fetch(fy, awards, refresh=refresh and fy >= years[-1] - 1)
        place(d["ent_county"], ent[yi], fy)
        place(d["sub_county"], sub[yi], fy)
        ent_total[yi] = sum(x["amount"] for x in d["ent_state"])
        subs[yi] = sum(x["amount"] for x in d["sub_state"])
        prime[yi] = sum(x["amount"] for x in d["prime_state"])
        unplaced[yi] = subs[yi] - sum(sub[yi])
        base = {"fiscal_year": fy, "fiscal_year_basis": "federal_oct_sep", "level": "federal_to_pr", "source_system": "usaspending", "stage": "obligated",
                "fund_origin": "federal", "function_category": "housing", "concept_of_expense": "transfers", "allocation_driver": "",
                "allocation_confidence": "high", "population_basis": "", "per_capita_usd": "", "dedup_group": "cdbg", "retrieved_at": retrieved,
                "source_url": cdbg_dr.SITE, "terms_of_use": federal_awards.TERMS}
        rec_e = {**base, "agency_or_entity": "Department of Housing and Urban Development", "program": "14.218 CDBG entitlement grants", "recipient_type": "municipality"}
        rec_s = {**base, "agency_or_entity": "Puerto Rico Department of Housing (subawards)", "program": "14.228 CDBG state program", "recipient_type": "mixed"}
        for rec, col in ((rec_e, ent[yi]), (rec_s, sub[yi])):
            for i, v in enumerate(col):
                if v:
                    records.append({**rec, "municipio_fips": ids[i], "allocation_tier": "direct", "amount_usd": round(v)})
        if round(unplaced[yi]):
            records.append({**rec_s, "municipio_fips": "", "allocation_tier": "island_wide", "amount_usd": round(unplaced[yi])})
    bad = [p for r in records for p in spending.validate({k: str(v) for k, v in r.items()})]
    if bad:
        raise ValueError(f"records fail the schema: {bad[:5]}")
    doc = {"version": 1, "built": retrieved, "source": "usaspending", "unit": "USD", "level": "federal_to_pr", "fiscal_year_basis": "federal_oct_sep",
           "stage": "obligated", "program": "14.218 CDBG entitlement grants and 14.228 CDBG state program (yearly grants; disaster and COVID grants left out)",
           "awards": awards, "years": years, "geo": {"ids": ids, "names": names},
           "entitlement": [[round(v) for v in yr] for yr in ent], "entitlement_total": [round(v) for v in ent_total],
           "state_by_muni": [[round(v) for v in yr] for yr in sub], "state_unplaced": [round(v) for v in unplaced],
           "state_subawards": [round(v) for v in subs], "state_prime": [round(v) for v in prime],
           "population": pica["population"], "population_basis": pica["population_basis"], "dedup_group": "cdbg"}
    for yi, fy in enumerate(years):
        if doc["state_unplaced"][yi] < -len(ids):
            raise ValueError(f"FY{fy}: the municipios add up to more than the state subawards for Puerto Rico")
        if sum(doc["entitlement"][yi]) > doc["entitlement_total"][yi] + len(ids):
            raise ValueError(f"FY{fy}: the entitlement municipios add up to more than Puerto Rico")
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_cdbg.json {'is current' if same else 'differs from the cache: run python cdbg_regular.py'}")
        return same
    OUT.write_text(text, encoding="utf-8")
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORDS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spending.FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    for yi, fy in enumerate(years):
        log(f"  FY{fy}: entitlement ${ent_total[yi] / 1e6:6.1f} M ({sum(1 for v in ent[yi] if v)} municipios), state prime ${prime[yi] / 1e6:5.1f} M, "
            f"state subawards ${subs[yi] / 1e6:5.1f} M ({sum(1 for v in sub[yi] if v)} municipios, ${unplaced[yi] / 1e6:4.1f} M not placed)")
    log(f"  wrote spending_cdbg.json: {OUT.stat().st_size / 1e3:.0f} KB; {len(records)} records in {RECORDS.name}")
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
