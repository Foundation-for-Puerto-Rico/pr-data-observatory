"""Federal grants that have ended with an unpaid balance, for the Knowledge Area page "Federal funds returned and unused" (HANDOFF decision 110, step 1).

    python unused_funds.py              # build site/data/unused_funds.json (downloads only the signing years missing from cache/spending/ended/)
    python unused_funds.py --refresh    # read every signing year again from USAspending
    python unused_funds.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: USAspending.gov's award search. The awards are the grants of federal_outlays.py (award types 02 to 05, place of performance Puerto
Rico, signed in each federal fiscal year from 2020, because USAspending has outlays from then; FEMA Public Assistance, 97.036, is left out and read
by project from OpenFEMA), read here with each award's end date.

The rule. An award has "ended" when its end date is more than a year before the day the data were read: by then the 120 days a recipient has to
draw down (2 CFR 200.344) and the agency's own year to close the award have both passed. Its unpaid balance is the amount obligated minus the outlays,
never below zero. An award "keeps a balance" when that balance is at least 5% of the award and at least $1,000. This is money at risk, not money
lost: an award can be extended, an agency can still pay a late claim, and USAspending can be behind on what was paid.

Shown apart (APART), each for a reason that holds for the whole program, and never added to the other programs: Medicaid (93.778), whose ended
awards show billions unpaid, more likely a gap in what USAspending reports as paid; TANF (93.558), whose money can be carried forward without a
deadline; and the programs the federal government ended in 2025 (Solar for All, 66.959, and the Community Change Grants, 66.616). Title I (84.010)
stays in the figures with a note (NOTES). The awards read are the ones that BEGAN in the years read (in_universe): the search also returns older
awards amended in those years.

Every assistance listing is a federal program, and all of them are read: no program is singled out. Recipients are not read into the file.

output: site/data/unused_funds.json. read: the day USAspending was read; ended_before: read minus one year; years: the signing years; totals: every
award read, the ended ones and the ones that keep a balance (without the programs shown apart); apart: the same sums for each program shown apart;
agencies: [federal agency, awards that keep a balance, their obligated dollars, their unpaid dollars]; listings: [assistance listing, its name,
federal agency, awards, obligated, unpaid]; end_years: [calendar year the award ended, awards, unpaid]. Whole dollars.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "spending" / "ended"
OUT = ROOT / "site" / "data" / "unused_funds.json"
NAMES = [ROOT / "site" / "data" / "spending_federal.json", ROOT / "site" / "data" / "spending_outlays.json"]
API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
LISTING_API = "https://api.usaspending.gov/api/v2/autocomplete/cfda/"
UA = hs.UA
FIRST_YEAR = 2020
FIELDS = ["Award ID", "Award Amount", "Total Outlays", "CFDA Number", "End Date", "Awarding Agency", "Start Date"]   # no recipient field: recipients are not read
EXCLUDE = {"97.036": "FEMA Public Assistance: USAspending's awards do not follow the projects; counted by project stage from OpenFEMA"}
# Programs shown in their own lines and never added to the others, each for a reason that holds for the whole program (review of 2026-11-19).
APART = {
    "medicaid": {"why": "Medicaid: its ended awards show billions unpaid, more likely a gap in what USAspending reports as paid than money not paid",
                 "listings": ["93.778"]},
    "carryover": {"why": "A program whose money stays available without a deadline: a State or territory may carry unspent TANF funds forward to later years (42 U.S.C. 604(e)), so a balance after the end date is not money left behind",
                  "listings": ["93.558"]},
    "federal": {"why": "Programs the federal government ended: the Environmental Protection Agency terminated Solar for All on 2025-08-07 and canceled the Community Change Grants in 2025, so their balances are a federal decision, not unspent money",
                "listings": ["66.959", "66.616"]},
}
# Programs that stay in the main figures with a note on the page: their money has a longer life than the end date suggests.
NOTES = {"84.010": "Title I: under the Tydings Amendment (20 U.S.C. 1225(b)) the money stays available for 27 months, and the Department of Education can extend the time to pay it out"}
MIN_SHARE, MIN_USD = 0.05, 1000
TERMS = "US Government work, public domain (USAspending.gov)"
log = hs.log


def last_final_year(today=None):
    """The latest federal fiscal year that counts as final: a year ends on September 30 and is read from November 15 (as federal_outlays.py)."""
    today = today or date.today()
    return today.year if (today.month, today.day) >= (11, 15) else today.year - 1


def fetch(fy, refresh=False):
    """Every grant with an action signed in one federal fiscal year (cached): [listing, obligated, outlays or None, end date, awarding agency, start date]."""
    p = CACHE / f"{fy}.json"
    if p.exists() and not refresh:
        got = json.loads(p.read_text(encoding="utf-8"))
        if not got or len(got[0]) >= 6:   # a cache from before the start date was read is read again
            return got
    seen, out, page = set(), [], 1
    while True:
        body = {"filters": {"award_type_codes": ["02", "03", "04", "05"], "place_of_performance_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30", "date_type": "date_signed"}]},
                "fields": FIELDS, "limit": 100, "page": page, "sort": "Award ID", "order": "asc"}
        for attempt in range(5):
            try:
                r = requests.post(API, json=body, headers=UA, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending FY{fy} page {page}: no answer")
        j = r.json()
        for x in j.get("results", []):
            k = x.get("generated_internal_id") or x.get("Award ID")
            if k in seen:
                continue
            seen.add(k)
            out.append([(x.get("CFDA Number") or "").strip(), x.get("Award Amount") or 0.0, x.get("Total Outlays"), x.get("End Date") or "", (x.get("Awarding Agency") or "").strip(), x.get("Start Date") or ""])
        if not j.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    log(f"  USAspending: {len(out)} grants signed in FY{fy}")
    return out


def cutoff(read):
    """One year before the day the data were read (29 February becomes 28)."""
    d = date.fromisoformat(read)
    try:
        return d.replace(year=d.year - 1).isoformat()
    except ValueError:
        return d.replace(year=d.year - 1, day=28).isoformat()


def unpaid(amount, outlays):
    return max(0.0, amount - max(0.0, outlays))


def keeps_balance(amount, outlays):
    """Whether an ended award keeps a balance: outlays reported, and at least 5% of the award and $1,000 unpaid."""
    if outlays is None or amount <= 0:
        return False
    u = unpaid(amount, outlays)
    return u >= MIN_SHARE * amount and u >= MIN_USD


def in_universe(a, first_year=FIRST_YEAR):
    """Whether an award began in the years read. The search returns every award with an action signed in a year, so it also returns older awards
    that were only amended then; those have no outlays on record before fiscal year 2020 and are left out."""
    return bool(a[5]) and a[5] >= f"{first_year - 1}-10-01"


def summarise(awards, before):
    """The sums of one set of awards [listing, obligated, outlays, end, agency, start]: all, ended, and ended with a balance."""
    ended = [a for a in awards if a[3] and a[3] < before and a[1] > 0]
    known = [a for a in ended if a[2] is not None]
    kept = [a for a in known if keeps_balance(a[1], a[2])]
    return {"awards": len(awards), "obligated": round(sum(a[1] for a in awards)),
            "ended": len(ended), "ended_obligated": round(sum(a[1] for a in ended)),
            "ended_paid": round(sum(min(a[1], max(0.0, a[2])) for a in known)), "ended_unpaid": round(sum(unpaid(a[1], a[2]) for a in known)),
            "no_outlay": len(ended) - len(known), "no_outlay_obligated": round(sum(a[1] for a in ended if a[2] is None)),
            "with_balance": len(kept), "with_balance_obligated": round(sum(a[1] for a in kept)), "with_balance_unpaid": round(sum(unpaid(a[1], a[2]) for a in kept))}, kept


def names():
    """{assistance listing: its name}, from the published federal files, which read the same programs by name."""
    out = {}
    for f in NAMES:
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")).get("rows", []):
                if r[2] == 0 and r[1] and r[1] != r[0]:   # group 0 is grants; a row named by its own code has no name
                    out.setdefault(r[0], r[1])
    return out


def lookup_names(codes, known, offline=False):
    """Names of the listings the published files do not name, from USAspending's listing search (cached in names.json; one small call per listing)."""
    p = CACHE / "names.json"
    got = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for code in sorted(c for c in codes if c not in known and c not in got and not offline):
        try:
            r = requests.post(LISTING_API, json={"search_text": code, "limit": 5}, headers=UA, timeout=60)
            got[code] = next((x.get("program_title") or "" for x in r.json().get("results", []) if x.get("program_number") == code), "").strip()
        except (requests.RequestException, ValueError):
            pass
    if not offline:
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(got, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {**got, **known}


def build(refresh=False, check=False):
    index_p = CACHE / "index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    if check and not index:
        log("  unused_funds: no cache, nothing to check")
        return 0
    if refresh or not index:
        index = {"read": date.today().isoformat(), "last_year": last_final_year()}
    years = list(range(FIRST_YEAR, index["last_year"] + 1))
    read = []
    for fy in years:
        read += [a for a in fetch(fy, refresh and not check) if a[0] not in EXCLUDE]
    awards = [a for a in read if in_universe(a)]
    older = len(read) - len(awards)
    if not check:
        CACHE.mkdir(parents=True, exist_ok=True)
        index_p.write_text(json.dumps(index), encoding="utf-8")
    before = cutoff(index["read"])
    apart_of = {c: g for g, v in APART.items() for c in v["listings"]}
    main = [a for a in awards if a[0] not in apart_of]
    totals, kept = summarise(main, before)
    totals["older_left_out"] = older
    apart, apart_kept = {}, []
    for g, v in APART.items():
        s, k = summarise([a for a in awards if apart_of.get(a[0]) == g], before)
        apart[g] = {**s, "why": v["why"], "listings": v["listings"]}
        apart_kept += k
    nm = lookup_names({a[0] for a in kept + apart_kept if a[0]}, names(), offline=check)
    apart_names = {c: nm.get(c, "") for c in apart_of}
    blank = [a for a in main if a[3] and a[3] < before and a[1] > 0 and a[2] is None]   # ended, and no outlay on record: shown apart, never counted as unpaid
    nb = {}
    for a in blank:
        e = nb.setdefault(a[4] or "Not stated", [0, 0.0])
        e[0] += 1
        e[1] += a[1]

    def group(key):
        g = {}
        for a in kept:
            r = g.setdefault(key(a), [0, 0.0, 0.0])
            r[0] += 1
            r[1] += a[1]
            r[2] += unpaid(a[1], a[2])
        return g

    ag = group(lambda a: a[4] or "Not stated")
    li = group(lambda a: (a[0] or "?", a[4] or "Not stated"))
    ey = group(lambda a: a[3][:4])
    doc = {"version": 1, "built": index["read"], "read": index["read"], "ended_before": before, "years": years,
           "source": "USAspending.gov award search: grants (award types 02 to 05), place of performance Puerto Rico, by the federal fiscal year they were signed",
           "terms": TERMS, "rule": {"universe": f"awards that began on or after {FIRST_YEAR - 1}-10-01", "ended": "end date more than one year before the day the data were read", "balance_share": MIN_SHARE, "balance_usd": MIN_USD},
           "excluded": EXCLUDE, "totals": totals, "apart": apart, "apart_names": apart_names, "notes": {c: t for c, t in NOTES.items() if any(a[0] == c for a in kept)},
           "no_outlay": sorted(([k, v[0], round(v[1])] for k, v in nb.items()), key=lambda r: (-r[2], r[0])),
           "agencies": sorted(([k, v[0], round(v[1]), round(v[2])] for k, v in ag.items()), key=lambda r: (-r[3], r[0])),
           "listings": sorted(([k[0], nm.get(k[0], ""), k[1], v[0], round(v[1]), round(v[2])] for k, v in li.items()), key=lambda r: (-r[5], r[0], r[2])),
           "end_years": sorted([int(k), v[0], round(v[2])] for k, v in ey.items())}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    if check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            log("  unused_funds.json is NOT what the cache gives: run python unused_funds.py")
            return 1
        log("  unused_funds.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    t = totals
    log(f"  wrote unused_funds.json: {t['awards']} grants, {t['ended']} ended, {t['with_balance']} keep a balance of ${t['with_balance_unpaid'] / 1e9:.2f} B "
        f"in {len(doc['listings'])} program lines; {older} older awards left out; apart: " + ", ".join(f"{c} ${v['with_balance_unpaid'] / 1e9:.2f} B" for c, v in apart.items()))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    return build(refresh="--refresh" in argv, check="--check" in argv)


if __name__ == "__main__":
    sys.exit(main())
