"""Test for the proposal docs/unused-federal-funds-proposal-2026-11.md: can open data show federal money taken back from Puerto Rico grantees?

Reads USAspending's transaction search for grants (award types 02 to 05) whose recipient is in Puerto Rico, one federal fiscal year at a time,
sorted from the most negative transaction up, and stops at the first one that is not negative. A negative transaction lowers the amount obligated
to an award (a deobligation). It can be a recapture, a balance left unused when the award closed, or a correction, so the totals here are an
upper bound of money taken back and not a count of losses.

Run from the repository root:  python docs/analysis/unused-funds-2026-11/measure.py [--refresh]
The cache goes to C:/t/cache/spending/deobligations (or $TWIN_CACHE/spending/deobligations); nothing is written to the repository but summary.json.
"""
import collections
import json
import os
import pathlib
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
CACHE = pathlib.Path(os.environ.get("TWIN_CACHE", "C:/t/cache")) / "spending" / "deobligations"
URL = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; pr-digital-twin research dashboard; +https://github.com/Foundation-for-Puerto-Rico/pr-digital-twin)"}
FIELDS = ["Award ID", "Mod", "Recipient Name", "Action Date", "Transaction Amount", "Awarding Agency", "Awarding Sub Agency", "Award Type",
          "Assistance Listing", "Action Type", "generated_internal_id"]
YEARS = range(2019, 2027)          # federal fiscal years, October to September, named by the year they end
DISASTER = {"97.036", "14.228", "97.039", "97.050"}   # FEMA Public Assistance, CDBG (State program: carries CDBG-DR), Hazard Mitigation, Individuals and Households


def year_rows(fy, refresh=False):
    p = CACHE / f"{fy}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    out, page = [], 1
    while True:
        body = {"filters": {"award_type_codes": ["02", "03", "04", "05"], "recipient_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}]},
                "fields": FIELDS, "sort": "Transaction Amount", "order": "asc", "limit": 100, "page": page}
        for attempt in range(5):
            try:
                r = requests.post(URL, json=body, headers=UA, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending FY{fy} page {page}: no answer")
        res = r.json().get("results", [])
        neg = [x for x in res if (x.get("Transaction Amount") or 0) < 0]
        out += neg
        if len(neg) < len(res) or not res:
            break
        if page == 100:
            raise RuntimeError(f"FY{fy}: more than 10,000 negative transactions; split the query")
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def listing(x):
    a = x.get("Assistance Listing")
    if isinstance(a, dict):
        return (a.get("cfda_number") or "?", a.get("cfda_program_title") or a.get("cfda_title") or "")
    if isinstance(a, list) and a:
        return listing({"Assistance Listing": a[0]})
    return (str(a or "?"), "")


def main():
    refresh = "--refresh" in sys.argv
    rows = []
    for fy in YEARS:
        for x in year_rows(fy, refresh):
            n, t = listing(x)
            rows.append({"fy": fy, "amount": -x["Transaction Amount"], "award": x.get("Award ID") or "", "recipient": (x.get("Recipient Name") or "").strip(),
                         "agency": x.get("Awarding Agency") or "", "sub": x.get("Awarding Sub Agency") or "", "listing": n, "title": t,
                         "date": x.get("Action Date") or "", "action": x.get("Action Type") or ""})
    total = sum(r["amount"] for r in rows)
    rest = [r for r in rows if r["listing"] not in DISASTER]

    def top(rs, key, n):
        c, k = collections.Counter(), collections.Counter()
        for r in rs:
            c[r[key]] += r["amount"]
            k[r[key]] += 1
        return [{"name": a, "amount": round(v), "transactions": k[a]} for a, v in c.most_common(n)]

    titles = {}
    for r in rows:
        titles.setdefault(r["listing"], r["title"])
    by_listing = top(rest, "listing", 25)
    for b in by_listing:
        b["title"] = titles.get(b["name"], "")
    summary = {
        "read": time.strftime("%Y-%m-%d"), "basis": "grants (award types 02-05), recipient in Puerto Rico, negative transactions, federal fiscal years 2019-2026",
        "transactions": len(rows), "awards": len({r["award"] for r in rows}), "total": round(total),
        "disaster_listings": sorted(DISASTER), "disaster_total": round(total - sum(r["amount"] for r in rest)),
        "other_total": round(sum(r["amount"] for r in rest)), "other_transactions": len(rest), "other_awards": len({r["award"] for r in rest}),
        "other_listings": len({r["listing"] for r in rest}), "other_recipients": len({r["recipient"] for r in rest}),
        "by_year": [{"fy": fy, "all": round(sum(r["amount"] for r in rows if r["fy"] == fy)), "other": round(sum(r["amount"] for r in rest if r["fy"] == fy))} for fy in YEARS],
        "by_agency_other": top(rest, "agency", 12), "by_listing_other": by_listing,   # recipients are counted, not named (choice (d) of the proposal)
        "by_listing_all": [dict(b, title=titles.get(b["name"], "")) for b in top(rows, "listing", 8)],
        "action_types": top(rows, "action", 8),
        "largest_other": sorted(({k: r[k] for k in ("date", "award", "amount", "listing", "title")} for r in rest), key=lambda r: -r["amount"])[:15],
    }
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
