"""How reliable are small-area survey estimates in Puerto Rico? (plan item 4, 2026-10-06)

    python small_area_reliability.py          # prints the tables and writes small_area_reliability.json next to this file

For three ACS 5-year tables (median gross rent B25064, median household income B19013, median home value B25077) it counts, at each level, how many units
have no estimate and how wide the 90% margin of error is relative to the estimate. For one share (renter households paying 30% or more of income, from
B25070) it works out the margin of the share with the Census Bureau's approximate formula. Needs the repository's venv, network access (acs_small.py reads
Puerto Rico's rows by byte range, 0.5 to 1.5 MB per table) and, for the crosswalk filter, site/data/geo/crosswalk.json.

Reads only public Census Bureau tables. Aggregates only; nothing here is published on the site.
"""
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import acs_small  # noqa: E402

VINTAGE = 2024                   # the 2020-2024 window
LEVELS = ("municipio", "barrio", "tract", "block-group")
TABLES = (("B25064", "B25064_001", "median gross rent"), ("B19013", "B19013_001", "median household income"), ("B25077", "B25077_001", "median home value"))


def medians(rows, cell):
    vals = [v[cell] for v in rows.values()]
    no_est = sum(1 for e, m in vals if e is None)
    rel = [m / e for e, m in vals if e and m is not None]
    return {"units": len(rows), "no_estimate": no_est, "no_estimate_pct": round(no_est / len(rows) * 100, 1),
            "median_margin_over_estimate_pct": round(statistics.median(rel) * 100, 1), "margin_over_30pct_of_estimate_pct": round(sum(1 for x in rel if x > .30) / len(rel) * 100, 1)}


def share_margin(c):
    """Share of renter households paying 30% or more of income (B25070 cells 007-010 over 001 minus 011) and its 90% margin in points; None below 20 households."""
    tot, nc = c["B25070_001"], c["B25070_011"]
    den = (tot[0] or 0) - (nc[0] or 0)
    cells = [c[f"B25070_{i:03d}"] for i in (7, 8, 9, 10)]
    if den < 20 or any(x[0] is None for x in cells):
        return None
    num = sum(x[0] for x in cells)
    moe_num = math.sqrt(sum((x[1] or 0) ** 2 for x in cells))
    moe_den = math.sqrt((tot[1] or 0) ** 2 + (nc[1] or 0) ** 2)
    p = num / den
    under = moe_num ** 2 - p ** 2 * moe_den ** 2
    return (math.sqrt(under) if under > 0 else math.sqrt(moe_num ** 2 + p ** 2 * moe_den ** 2)) / den * 100


def main():
    out = {"vintage": f"{VINTAGE - 4}-{VINTAGE}", "tables": {}, "rent_burden_share": {}}
    for table, cell, label in TABLES:
        r = acs_small.read_table(table, VINTAGE)
        out["tables"][label] = {lv: medians(r["levels"][lv], cell) for lv in LEVELS}
        print(f"== {label} ({table}), {out['vintage']}")
        for lv in LEVELS:
            m = out["tables"][label][lv]
            print(f"  {lv:12s} {m['units']:5d} units | no estimate {m['no_estimate']:4d} ({m['no_estimate_pct']:4.1f}%) | median margin {m['median_margin_over_estimate_pct']:5.1f}% of the estimate | margin over 30% of the estimate in {m['margin_over_30pct_of_estimate_pct']:4.1f}% of units")
    r = acs_small.read_table("B25070", VINTAGE)
    print("== renter households paying 30% or more of income (B25070), units with 20 or more renter households")
    for lv in ("municipio", "tract", "block-group"):
        w = [x for x in (share_margin(c) for c in r["levels"][lv].values()) if x is not None]
        out["rent_burden_share"][lv] = {"units": len(w), "median_margin_points": round(statistics.median(w), 1)}
        print(f"  {lv:12s} {len(w):5d} units | median margin of the share: plus or minus {out['rent_burden_share'][lv]['median_margin_points']} points")
    (HERE / "small_area_reliability.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
