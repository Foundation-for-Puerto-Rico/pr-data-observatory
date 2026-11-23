"""Test for the proposal docs/unused-federal-funds-proposal-2026-11.md: grants whose end date has passed and that still show an unpaid balance.

Same awards as federal_outlays.py (grants, award types 02 to 05, place of performance Puerto Rico, signed in federal fiscal years 2020 to 2025,
FEMA Public Assistance left out), read again with the end date of each award. "Ended" means the end date is more than a year before the day of
the run: by then the 120 days a recipient has to draw down (2 CFR 200.344) and the agency's own year to close the award have both passed.
The unpaid balance is the amount obligated minus the outlays, never below zero. It is money at risk, not money lost: an award can be extended,
and an agency can still pay a late claim.

Run from the repository root:  python docs/analysis/unused-funds-2026-11/expired.py [--refresh]
"""
import collections
import datetime
import json
import os
import pathlib
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
CACHE = pathlib.Path(os.environ.get("TWIN_CACHE", "C:/t/cache")) / "spending" / "expired"
URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; pr-digital-twin research dashboard; +https://github.com/Foundation-for-Puerto-Rico/pr-digital-twin)"}
FIELDS = ["Award ID", "Award Amount", "Total Outlays", "CFDA Number", "End Date", "Awarding Agency", "Recipient Name"]
YEARS = range(2020, 2026)
EXCLUDE = {"97.036"}


def year_rows(fy, refresh=False):
    p = CACHE / f"{fy}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    seen, out, page = set(), [], 1
    while True:
        body = {"filters": {"award_type_codes": ["02", "03", "04", "05"], "place_of_performance_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30", "date_type": "date_signed"}]},
                "fields": FIELDS, "limit": 100, "page": page, "sort": "Award ID", "order": "asc"}
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
        j = r.json()
        for x in j.get("results", []):
            k = x.get("generated_internal_id") or x.get("Award ID")
            if k not in seen:
                seen.add(k)
                out.append(x)
        if not j.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def main():
    refresh = "--refresh" in sys.argv
    today = datetime.date.today()
    cut = today.replace(year=today.year - 1).isoformat()
    rows = []
    for fy in YEARS:
        for x in year_rows(fy, refresh):
            if (x.get("CFDA Number") or "") in EXCLUDE:
                continue
            rows.append({"fy": fy, "amount": x.get("Award Amount") or 0.0, "outlays": x.get("Total Outlays"), "end": x.get("End Date") or "",
                         "listing": x.get("CFDA Number") or "?", "agency": x.get("Awarding Agency") or "", "recipient": (x.get("Recipient Name") or "").strip()})
    ended = [r for r in rows if r["end"] and r["end"] < cut and r["amount"] > 0]
    known = [r for r in ended if r["outlays"] is not None]
    for r in known:
        r["unpaid"] = max(0.0, r["amount"] - max(0.0, r["outlays"]))
    open_ = [r for r in known if r["unpaid"] >= 0.05 * r["amount"] and r["unpaid"] >= 1000]

    def top(key, n):
        c, k = collections.Counter(), collections.Counter()
        for r in open_:
            c[r[key]] += r["unpaid"]
            k[r[key]] += 1
        return [{"name": a, "unpaid": round(v), "awards": k[a]} for a, v in c.most_common(n)]

    summary = {
        "read": today.isoformat(), "ended_before": cut,
        "basis": "grants (award types 02-05), place of performance Puerto Rico, signed FY2020-2025, FEMA Public Assistance (97.036) left out",
        "awards": len(rows), "obligated": round(sum(r["amount"] for r in rows)),
        "ended": len(ended), "ended_obligated": round(sum(r["amount"] for r in ended)), "ended_no_outlay_reported": len(ended) - len(known),
        "ended_no_outlay_reported_obligated": round(sum(r["amount"] for r in ended if r["outlays"] is None)),
        "ended_paid": round(sum(min(r["amount"], max(0.0, r["outlays"])) for r in known)), "ended_unpaid": round(sum(r["unpaid"] for r in known)),
        "ended_with_balance": len(open_), "ended_with_balance_unpaid": round(sum(r["unpaid"] for r in open_)),
        "balance_rule": "unpaid balance of at least 5% of the award and at least $1,000",
        "listings": len({r["listing"] for r in open_}), "agencies": len({r["agency"] for r in open_}),
        "by_agency": top("agency", 12), "by_listing": top("listing", 20),
        "by_end_year": [{"year": y, "awards": sum(1 for r in open_ if r["end"][:4] == y), "unpaid": round(sum(r["unpaid"] for r in open_ if r["end"][:4] == y))}
                        for y in sorted({r["end"][:4] for r in open_})],
    }
    (HERE / "expired_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
