"""Federal grant money taken back, for the Knowledge Area page "Federal funds returned and unused" (HANDOFF decision 110, step 2).

    python taken_back.py              # build site/data/taken_back.json (downloads only the quarters missing from cache/spending/taken_back/)
    python taken_back.py --refresh    # read every quarter again from USAspending
    python taken_back.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: USAspending.gov's transaction search. Every transaction (each change to the amount obligated to an award) on grants (award types
02 to 05) with place of performance Puerto Rico, by action date, from federal fiscal year FIRST_YEAR. No recipient is read.

The rule. A negative transaction lowers the amount obligated to an award. Alone it is not money taken back: it can be the correction of an
estimate that a later transaction raises again. So the measure is each award's NET REDUCTION over the period read: the highest level its obligation
reached (counted from where it stood when the period began) minus the level where it ended. An award that was lowered and raised back counts
nothing; an award lowered for good counts what it lost. The year of a reduction is the fiscal year of the award's last negative transaction.

Shown apart (APART): programs whose awards are estimates or project agreements that are adjusted as a routine, and disaster programs whose
projects are re-versioned. Their net reductions are published in their own lines and are never added to the other programs.

output: site/data/taken_back.json. See docs/unused-funds.md.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import unused_funds

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "spending" / "taken_back"
OUT = ROOT / "site" / "data" / "taken_back.json"
API = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
UA = hs.UA
FIRST_YEAR = 2019
FIELDS = ["Award ID", "Action Date", "Transaction Amount", "Awarding Agency", "Assistance Listing", "generated_internal_id"]   # no recipient field
MIN_USD = 1000
MOVE_DAYS = 31
# Programs whose reductions are routine and are published in their own lines, never added to the others. A program is here only for a reason
# that holds for the program as a whole, stated in "why".
APART = {
    "estimates": {"why": "Programs that pay a share of whatever the costs turn out to be: each grant is an estimate that is lowered or raised to the actual costs",
                  "listings": ["93.778", "93.767", "93.658", "93.659", "93.563", "10.553", "10.555", "10.558", "10.559", "10.542"]},
    "highways": {"why": "Highway project agreements: money released when a project closes goes back to the highway balance of Puerto Rico and can be used on another project",
                 "listings": ["20.205"]},
    "disaster": {"why": "Disaster programs, whose projects are re-versioned many times; FEMA Public Assistance is counted by project on the Public spending page",
                 "listings": ["97.036", "97.039", "97.050", "14.228"]},
    "federal": {"why": "Money the federal government withdrew by its own decision in 2025: the Department of Energy redirected the solar funds of the Puerto Rico Energy Resilience Fund, and the Environmental Protection Agency terminated Solar for All and cancelled the Community Change Grants",
                "listings": ["81.254", "66.959", "66.616"]},
}
log = hs.log


def quarters(fy):
    """The four quarters of a federal fiscal year, as (start, end) dates."""
    return [(f"{fy - 1}-10-01", f"{fy - 1}-12-31"), (f"{fy}-01-01", f"{fy}-03-31"), (f"{fy}-04-01", f"{fy}-06-30"), (f"{fy}-07-01", f"{fy}-09-30")]


def listing(x):
    a = x.get("Assistance Listing")
    if isinstance(a, list):
        a = a[0] if a else None
    if isinstance(a, dict):
        return (a.get("cfda_number") or "").strip(), (a.get("cfda_program_title") or a.get("cfda_title") or "").strip()
    return (str(a or "").strip(), "")


def fetch(fy, q, refresh=False):
    """Every transaction of one quarter (cached): [award key, action date, amount, listing, listing name, awarding agency]."""
    p = CACHE / f"{fy}_q{q + 1}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    start, end = quarters(fy)[q]
    out, page = [], 1
    while True:
        body = {"filters": {"award_type_codes": ["02", "03", "04", "05"], "place_of_performance_locations": [{"country": "USA", "state": "PR"}],
                            "time_period": [{"start_date": start, "end_date": end}]},
                "fields": FIELDS, "sort": "Transaction Amount", "order": "asc", "limit": 100, "page": page}
        for attempt in range(6):
            try:
                r = requests.post(API, json=body, headers=UA, timeout=180)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"USAspending FY{fy} Q{q + 1} page {page}: no answer")
        j = r.json()
        for x in j.get("results", []):
            code, name = listing(x)
            out.append([x.get("generated_internal_id") or x.get("Award ID") or "", x.get("Action Date") or "", x.get("Transaction Amount") or 0.0, code, name, (x.get("Awarding Agency") or "").strip()])
        if not j.get("page_metadata", {}).get("hasNext"):
            break
        if page == 100:
            raise RuntimeError(f"FY{fy} Q{q + 1}: more than 10,000 transactions; split the quarter")
        page += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    log(f"  USAspending: {len(out)} transactions in FY{fy} Q{q + 1}")
    return out


def fiscal_year(day):
    y, m = int(day[:4]), int(day[5:7])
    return y + 1 if m >= 10 else y


def net_reduction(amounts):
    """The highest level reached (from 0, where the award stood when the period began) minus the final level, for amounts in date order."""
    level = peak = 0.0
    for a in amounts:
        level += a
        peak = max(peak, level)
    return max(0.0, peak - level)


def load(refresh=False, check=False):
    index_p = CACHE / "index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    if refresh or not index:
        if check:
            return None, None
        index = {"read": date.today().isoformat(), "last_year": unused_funds.last_final_year()}
    rows = []
    for fy in range(FIRST_YEAR, index["last_year"] + 1):
        for q in range(4):
            rows += fetch(fy, q, refresh and not check)
    if not check:
        CACHE.mkdir(parents=True, exist_ok=True)
        index_p.write_text(json.dumps(index), encoding="utf-8")
    return index, rows


def drop_moves(rows):
    """Leave out money moved between two grants of the same program: a negative transaction matched by a positive one of the same amount, on
    another award of the same listing and agency, within MOVE_DAYS days. Returns (the other rows, the pairs dropped, their dollars)."""
    pos = {}
    for k, r in enumerate(rows):
        if r[2] >= MIN_USD:
            pos.setdefault((r[3], r[5], round(r[2])), []).append(k)
    gone, used, usd = set(), set(), 0.0   # only the negative is left out: the increase stays with the award that received the money
    for k, r in sorted(enumerate(rows), key=lambda kr: (kr[1][1], kr[1][0], kr[1][2])):
        if r[2] > -MIN_USD:
            continue
        day = date.fromisoformat(r[1])
        for j in pos.get((r[3], r[5], round(-r[2])), []):
            q = rows[j]
            if j not in used and q[0] != r[0] and abs((date.fromisoformat(q[1]) - day).days) <= MOVE_DAYS:
                used.add(j)
                gone.add(k)
                usd += -r[2]
                break
    return [r for k, r in enumerate(rows) if k not in gone], len(gone), usd


def awards(rows):
    """(awards read, one record for each award with a net reduction of at least MIN_USD): [listing, listing name, agency, net reduction, fiscal
    year of its last negative transaction, whether the award carries more than one listing]. An award's listing is the one with most money
    obligated to it."""
    by = {}
    for r in rows:
        by.setdefault(r[0], []).append(r)
    out = []
    for tx in by.values():
        tx.sort(key=lambda r: r[1])
        days = {}
        for r in tx:   # the transactions of one day count as one change: a same-day swap between lines of an award is not a reduction
            days[r[1]] = days.get(r[1], 0.0) + r[2]
        net = net_reduction([days[d] for d in sorted(days)])
        if net < MIN_USD:
            continue
        up = {}
        for r in tx:
            up[r[3]] = up.get(r[3], 0.0) + max(0.0, r[2])
        code = max(sorted(up), key=lambda c: (up[c], sum(1 for r in tx if r[3] == c)))
        name = next((r[4] for r in tx if r[3] == code and r[4]), "")
        last = max(r[1] for r in tx if r[2] < 0)
        out.append([code, name, tx[0][5] or "Not stated", net, fiscal_year(last), len(up) > 1])
    return len(by), out


def group(recs, key):
    g = {}
    for r in recs:
        e = g.setdefault(key(r), [0, 0.0, 0])
        e[0] += 1
        e[1] += r[3]
        e[2] += 1 if r[5] else 0
    return g


def build(refresh=False, check=False):
    index, rows = load(refresh, check)
    if index is None:
        log("  taken_back: no cache, nothing to check")
        return 0
    kept, pairs, moved = drop_moves(rows)
    n_awards, recs = awards(kept)
    apart_of = {c: g for g, v in APART.items() for c in v["listings"]}
    main = [r for r in recs if r[0] not in apart_of]
    nm = unused_funds.lookup_names({r[0] for r in recs if r[0]}, unused_funds.names(), offline=check)
    names_of = {}
    for r in recs:
        names_of.setdefault(r[0], nm.get(r[0]) or r[1].title())
    li = group(main, lambda r: (r[0] or "?", r[2]))
    ag = group(main, lambda r: r[2])
    ys = group(main, lambda r: r[4])
    years = list(range(FIRST_YEAR, index["last_year"] + 1))
    apart = {}
    for g, v in APART.items():
        rs = [r for r in recs if apart_of.get(r[0]) == g]
        gl = group(rs, lambda r: r[0])
        apart[g] = {"why": v["why"], "awards": len(rs), "net": round(sum(r[3] for r in rs)),
                    "listings": sorted(([c, names_of.get(c, ""), e[0], round(e[1])] for c, e in gl.items()), key=lambda x: (-x[3], x[0]))}
    doc = {"version": 1, "built": index["read"], "read": index["read"], "years": years,
           "source": "USAspending.gov transaction search: grants (award types 02 to 05), place of performance Puerto Rico, by action date",
           "terms": unused_funds.TERMS,
           "rule": {"measure": "net reduction of each award over the period: the highest level its obligation reached minus its final level", "min_usd": MIN_USD,
                    "moves": f"a reduction matched by an equal increase on another award of the same listing and agency within {MOVE_DAYS} days is a move, not a reduction",
                    "year": "federal fiscal year of the award's last negative transaction"},
           "read_counts": {"transactions": len(rows), "negative": sum(1 for r in rows if r[2] < 0), "gross_negative": round(-sum(r[2] for r in rows if r[2] < 0)),
                           "awards": n_awards, "moves": pairs, "moved": round(moved)},
           "totals": {"awards": len(main), "net": round(sum(r[3] for r in main)), "listings": len({r[0] for r in main}), "agencies": len(ag),
                      "combined_awards": sum(1 for r in main if r[5])},
           "apart": apart,
           "agencies": sorted(([k, e[0], round(e[1])] for k, e in ag.items()), key=lambda r: (-r[2], r[0])),
           "listings": sorted(([k[0], names_of.get(k[0], ""), k[1], e[0], round(e[1]), e[2]] for k, e in li.items()), key=lambda r: (-r[4], r[0], r[2])),
           "by_year": [[y, ys.get(y, [0, 0.0])[0], round(ys.get(y, [0, 0.0])[1])] for y in years]}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    if check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            log("  taken_back.json is NOT what the cache gives: run python taken_back.py")
            return 1
        log("  taken_back.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    t = doc["totals"]
    log(f"  wrote taken_back.json: {len(rows)} transactions on {n_awards} awards; {t['awards']} awards with a net reduction, ${t['net'] / 1e9:.2f} B in {t['listings']} programs; "
        + "apart: " + ", ".join(f"{g} ${v['net'] / 1e9:.2f} B" for g, v in apart.items()) + f"; {pairs} moves (${moved / 1e6:.1f} M) left out")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    return build(refresh="--refresh" in argv, check="--check" in argv)


if __name__ == "__main__":
    sys.exit(main())
