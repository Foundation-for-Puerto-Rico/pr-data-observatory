"""Medicare enrollment for the PR Data Observatory (Phase 3, item 9, data wave C): people enrolled in Medicare in each of the 78 municipalities and Puerto Rico, every year since 2013.

    python medicare_series.py             # build site/data/medicare_series.json (downloads only when the cache is missing)
    python medicare_series.py --refresh   # download again
    python medicare_series.py --check     # rebuild from the cache and exit 1 when site/data/medicare_series.json is not what it gives (no network, nothing written)

Source, no key, US federal data (public domain): the Centers for Medicare & Medicaid Services (CMS) "Medicare Monthly Enrollment" dataset on data.cms.gov, the yearly rows
(MONTH = "Year") of every county-level row of Puerto Rico. A yearly row counts the average of the year's monthly enrollment. The file has no personal data: only counts by county.
CMS suppresses small counts with "*": they are read as no value, never as zero.

Variables:
  medicare_benes         people enrolled in Medicare (TOT_BENES)
  medicare_ma_pct        share enrolled in Medicare Advantage and other health plans (MA_AND_OTH_BENES / TOT_BENES)
  medicare_disabled_pct  share entitled to Medicare by a disability or end-stage renal disease rather than by age (DSBLD_TOT_BENES / TOT_BENES)
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "cms" / "medicare_enrollment.pr.json"
OUT = hs.OUT / "medicare_series.json"
API = "https://data.cms.gov/data-api/v1/dataset/d7fabe1e-d19b-4333-9eff-e80e0643f2fd/data"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
KEEP = ["YEAR", "MONTH", "BENE_GEO_LVL", "BENE_STATE_ABRVTN", "BENE_FIPS_CD", "TOT_BENES", "MA_AND_OTH_BENES", "DSBLD_TOT_BENES"]
FLOOR = 600_000   # fewer people in a year means CMS changed a column (Puerto Rico had about 712,000 in 2013 and more since)
log = hs.log

SOURCES = {"cms_medicare_enrollment": {"name": "CMS — Medicare Monthly Enrollment (data.cms.gov)", "url": "https://data.cms.gov/summary-statistics-on-beneficiary-enrollment/medicare-and-medicaid-reports/medicare-monthly-enrollment",
                                       "license": "US federal government data (public domain)",
                                       "note": "Yearly counts of people enrolled in Medicare by county (municipio). The observatory publishes the total, the share in Medicare Advantage and the share entitled by disability."}}


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def rows(refresh=False, offline=False):
    """The kept columns of the yearly county-level and state-level rows of Puerto Rico."""
    if CACHE.exists() and not refresh:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"medicare_series --check: {CACHE.name} is not in the cache (python medicare_series.py makes it; --check never downloads)")
    out = []
    for lvl in ("County", "State"):
        off = 0
        while True:
            for attempt in range(4):
                try:
                    r = requests.get(API, params={"filter[BENE_STATE_ABRVTN]": "PR", "filter[BENE_GEO_LVL]": lvl, "filter[MONTH]": "Year", "size": 5000, "offset": off}, headers=UA, timeout=(30, 180))
                    r.raise_for_status()
                    page = r.json()
                    break
                except (requests.RequestException, ValueError) as e:
                    if attempt == 3:
                        raise SystemExit(f"medicare_series: {API} failed: {e}")
                    time.sleep(5 * (attempt + 1))
            missing = [c for c in KEEP if page and c not in page[0]]
            if missing:
                raise SystemExit(f"medicare_series: the rows have no column {missing}: CMS changed the dataset; read its data dictionary before going on")
            out += [{c: x.get(c) for c in KEEP} for x in page]
            if len(page) < 5000:
                break
            off += 5000
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    log(f"  Medicare enrollment: {len(out)} rows")
    return out


def var(key, group, label, unit, d, typ, definition, values):
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["cms_medicare_enrollment"], "ref": "CMS Medicare Monthly Enrollment, yearly rows",
            "definition": definition, "family": "health", "counted": False, **({"noPerHU": True} if typ == "count" else {}), "years": values}


def compute(refresh=False, offline=False, order_file=hs.OUT / "economy_series.json"):
    names, fips = hs.municipalities()
    ids = list(fips)
    if order_file and order_file.exists():
        g = json.loads(order_file.read_text(encoding="utf-8"))["geo"]
        if g["ids"][:len(ids)] != ids or g["names"][:len(ids)] != names:
            raise SystemExit("medicare_series: the municipalities are not in the order of economy_series.json")
    log("Medicare enrollment (CMS)")
    rs = rows(refresh, offline)
    by = {}
    for r in rs:
        key = "72" if r["BENE_GEO_LVL"] == "State" else str(r["BENE_FIPS_CD"])
        by[(str(r["YEAR"]), key)] = r
    years = sorted({y for y, _ in by})
    other = sorted({k for _, k in by} - set(ids) - {"72"})
    tot, ma, dis = {}, {}, {}
    for y in years:
        isl = by.get((y, "72"))
        if not isl or (num(isl["TOT_BENES"]) or 0) < FLOOR:
            raise SystemExit(f"medicare_series: {y}: no state row or fewer than {FLOOR:,} people for Puerto Rico: read the dataset before publishing")
        t, m, d = [], [], []
        for f in ids + ["72"]:
            r = by.get((y, f))
            T = num(r["TOT_BENES"]) if r else None
            t.append(None if T is None else round(T))
            share = lambda col: None if T in (None, 0) or num(r[col]) is None else round(num(r[col]) / T * 100, 2)
            m.append(share("MA_AND_OTH_BENES"))
            d.append(share("DSBLD_TOT_BENES"))
        tot[y], ma[y], dis[y] = t, m, d
    G = "Medicare"
    YEAR = "A year's figure is the average of the monthly enrollment counts of that year (CMS's yearly rows). "
    vs = [
        var("medicare_benes", G, "People enrolled in Medicare", "", 0, "count",
            YEAR + "People with Medicare who live in the municipality: people 65 and older and younger people entitled by a disability or end-stage renal disease. CMS suppresses a very small count; it shows as no value.", tot),
        var("medicare_ma_pct", G, "Medicare Advantage and other plans, % of people with Medicare", "%", 1, "rate",
            YEAR + "Share of the people enrolled in Medicare who get their coverage through Medicare Advantage or another private health plan rather than Original Medicare. In Puerto Rico most do.", ma),
        var("medicare_disabled_pct", G, "Entitled by disability, % of people with Medicare", "%", 1, "rate",
            YEAR + "Share of the people enrolled in Medicare who are entitled by a disability (or end-stage renal disease) rather than by age.", dis),
    ]
    return {"years": [int(y) for y in years], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": [{**v, "years": {str(y): a for y, a in v["years"].items()}} for v in vs],
            "sources": SOURCES, "notes": {"rows": len(rs), "county_codes_not_a_municipio": other}}


def build(refresh=False, check=False):
    out = compute(refresh, offline=check)
    text = json.dumps({"built": date.today().isoformat(), **out}, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        if old is None or {**old, "built": None} != {**json.loads(text), "built": None}:
            print("medicare_series.json is not what the cache gives: run python medicare_series.py")
            return 1
        print("medicare_series.json matches the cache")
        return 0
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(out['vars'])} variables, years {out['years'][0]}-{out['years'][-1]}, {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
