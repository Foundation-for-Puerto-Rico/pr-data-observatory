"""Five federal grants rebuilt from the first commitment to the last payment on record (HANDOFF decision 112, step 4; decision 111 (d)).

  python docs/analysis/unused-funds-2026-11/rebuild_awards.py            read USAspending (cached) and write awards_rebuilt.json beside this file
  python docs/analysis/unused-funds-2026-11/rebuild_awards.py --check    rebuild from the cache and exit 1 when the file differs (no network)

The reviewer of the Federal grants page asked for this before any new indicator: take a few large grants and follow each one through everything the
open record gives, to see how much the data can support. This is a study of the source, done once, not a series: the file is an input of the page
(docs/analysis/unused-funds-2026-11/make_page.py), not a data file of the site.

The rule that picks the grants: grants with place of performance Puerto Rico signed in federal fiscal years 2020 to 2024, whose end date is more than
one year before the day of the read, outside the programs the page keeps apart or leaves out (unused_funds.APART and EXCLUDE); ordered by the balance
not paid out on record; the first grant of each of the first five programs. No program is chosen by hand.

What is read for each grant, from USAspending.gov (no key): the award (dates, amount, total outlays), its transactions (each change of the amount
committed) and its funding by reporting period (the payments the federal agency reported, year to date, by account line). The recipient is not read
into the file and no award key is published: the grants are told apart by program, agency and dates. Cache: cache/spending/awards (or AWARDS_CACHE).
"""
import datetime
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import unused_funds as U   # noqa: E402  the programs kept apart, the user agent

CACHE = Path(os.environ.get("AWARDS_CACHE") or ROOT / "cache" / "spending" / "awards")
OUT = HERE / "awards_rebuilt.json"
API = "https://api.usaspending.gov/api/v2/"
YEARS = range(2020, 2025)
PAGES = 3      # the 300 largest grants of each signing year are enough to find the largest balances
N = 5
LEFT_OUT = set(U.EXCLUDE) | {c for v in U.APART.values() for c in v["listings"]}


def call(path, body, name, offline):
    """One call to USAspending, kept in the cache under a name that carries no award key."""
    p = CACHE / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise FileNotFoundError(name)
    for attempt in range(5):
        try:
            r = requests.post(API + path, json=body, headers=U.UA, timeout=180) if body is not None else requests.get(API + path, headers=U.UA, timeout=180)
            if r.status_code == 200:
                CACHE.mkdir(parents=True, exist_ok=True)
                p.write_text(r.text, encoding="utf-8")
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"USAspending {path}: no answer")


def paged(path, body, name, offline):
    out, page = [], 1
    while True:
        j = call(path, dict(body, limit=100, page=page), f"{name}_{page}.json", offline)
        out += j["results"]
        if not j["page_metadata"].get("hasNext"):
            return out
        page += 1


def pick(read, offline):
    """The grants of the rule: [key, listing, obligated, outlays, end date], largest balance on record first, one per program."""
    cut = (read - datetime.timedelta(days=365)).isoformat()
    seen, rows = set(), []
    for fy in YEARS:
        for page in range(1, PAGES + 1):
            j = call("search/spending_by_award/", {"filters": {"award_type_codes": ["02", "03", "04", "05"], "place_of_performance_locations": [{"country": "USA", "state": "PR"}],
                     "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30", "date_type": "date_signed"}]},
                     "fields": ["Award ID", "Award Amount", "Total Outlays", "CFDA Number", "End Date"], "limit": 100, "page": page, "sort": "Award Amount", "order": "desc"},
                     f"top_{fy}_{page}.json", offline)
            for x in j["results"]:
                k = x["generated_internal_id"]
                if k not in seen:
                    seen.add(k)
                    rows.append([k, (x.get("CFDA Number") or "").strip(), x.get("Award Amount") or 0.0, x.get("Total Outlays") or 0.0, x.get("End Date") or ""])
    ended = [r for r in rows if r[4] and r[4] < cut and r[1] not in LEFT_OUT]
    ended.sort(key=lambda r: (-(r[2] - r[3]), r[1]))
    out, programs = [], set()
    for r in ended:
        if r[1] not in programs:
            programs.add(r[1])
            out.append(r)
        if len(out) == N:
            break
    return out


def by_year(funding):
    """The payments reported for each federal fiscal year: [year, last month reported, dollars]. The source gives them year to date for each
    account line, so a year's payments are the sum over lines at the last month reported that year."""
    per = defaultdict(lambda: defaultdict(float))
    for f in funding:
        line = (f.get("federal_account"), f.get("disaster_emergency_fund_code"), f.get("object_class"), f.get("program_activity_code"))
        per[(f["reporting_fiscal_year"], f["reporting_fiscal_month"])][line] += f.get("gross_outlay_amount") or 0.0
    last = {}
    for (y, m) in sorted(per):
        last[y] = [y, m, round(sum(per[(y, m)].values()), 2)]
    return [last[y] for y in sorted(last)]


def fiscal_year(date):
    y, m = int(date[:4]), int(date[5:7])
    return y + 1 if m >= 10 else y


def rebuild(n, key, offline):
    d = call(f"awards/{key}/", None, f"g{n}_award.json", offline)
    tx = paged("transactions/", {"award_id": key, "sort": "action_date", "order": "asc"}, f"g{n}_tx", offline)
    fu = paged("awards/funding/", {"award_id": key, "sort": "reporting_fiscal_date", "order": "asc"}, f"g{n}_funding", offline)
    pop = d["period_of_performance"]
    days = defaultdict(float)
    kinds = {}
    for t in tx:   # one day, one change (the rule of the reductions, docs/unused-funds.md)
        days[t["action_date"]] += t.get("federal_action_obligation") or 0.0
        kinds.setdefault(t["action_date"], t.get("action_type_description") or "")
    years = by_year(fu)
    paid = round(sum(y[2] for y in years), 2)
    end_fy = fiscal_year(pop["end_date"])
    return {
        "listings": sorted(c["cfda_number"] for c in d["cfda_info"]),
        "programs": [c["cfda_title"] for c in sorted(d["cfda_info"], key=lambda c: c["cfda_number"])],
        "agency": d["awarding_agency"]["toptier_agency"]["name"],
        "signed": d["date_signed"], "start": pop["start_date"], "end": pop["end_date"], "end_fiscal_year": end_fy, "record_changed": pop["last_modified_date"][:10],
        "obligated": round(d["total_obligation"], 2), "paid": round(d["total_outlay"] or 0.0, 2), "paid_from_periods": paid,
        "changes": [[day, kinds[day], round(v, 2)] for day, v in sorted(days.items())],
        "highest": round(max(_running(days)), 2),
        "paid_by_year": years,
        "paid_after_end_year": round(sum(y[2] for y in years if y[0] > end_fy), 2),
        "first_year_paid": next((y[0] for y in years if y[2]), None),
        "last_period": [years[-1][0], years[-1][1]] if years else None,
    }


def _running(days):
    total, out = 0.0, []
    for day in sorted(days):
        total += days[day]
        out.append(total)
    return out or [0.0]


def build(check=False, read=None):
    index = CACHE / "index.json"
    if check and not index.exists():
        U.log("  rebuild_awards: no cache, nothing to check")
        return 0
    read = read or (datetime.date.fromisoformat(json.loads(index.read_text(encoding="utf-8"))["read"]) if index.exists() else datetime.date.today())
    grants = [rebuild(n, r[0], check) for n, r in enumerate(pick(read, check))]
    if not index.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({"read": read.isoformat()}), encoding="utf-8")
    for g in grants:   # the payments by period must rebuild the award's own total, or the reading of the periods is wrong
        if abs(g["paid"] - g["paid_from_periods"]) > 1:
            raise SystemExit(f"payments by period ({g['paid_from_periods']}) do not rebuild the total ({g['paid']}) for {g['listings']}")
    doc = {"version": 1, "read": read.isoformat(), "ended_before": (read - datetime.timedelta(days=365)).isoformat(),
           "source": "USAspending.gov: award, transactions and funding by reporting period of each grant; grants (award types 02 to 05), place of performance Puerto Rico",
           "terms": U.TERMS,
           "rule": f"signed in federal fiscal years {YEARS[0]} to {YEARS[-1]}; end date more than one year before the read; outside the programs kept apart or left out; "
                   f"largest balance on record first; the first grant of each of the first {N} programs",
           "no recipient": "the recipient is not read into this file and no award key is published",
           "grants": grants}
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    if check:
        if OUT.read_text(encoding="utf-8") != text:
            U.log("  awards_rebuilt.json is NOT what the cache gives: run python docs/analysis/unused-funds-2026-11/rebuild_awards.py")
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    for g in grants:
        U.log(f"  {'/'.join(g['listings'])} {g['agency']}: {g['obligated'] / 1e6:,.1f} M obligated, {g['paid'] / 1e6:,.1f} M paid, {g['paid_after_end_year'] / 1e6:,.1f} M after FY{g['end_fiscal_year']}")
    return 0


if __name__ == "__main__":
    sys.exit(build(check="--check" in sys.argv))
