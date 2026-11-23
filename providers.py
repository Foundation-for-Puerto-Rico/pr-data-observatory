"""Health care providers registered in each municipio, by type, from the NPPES registry (decision 107, step 8; row nppes); docs/providers.md.

    python providers.py             # build site/data/providers_series.json from cache/nppes/providers_pr.csv (extracts it from the monthly ZIP if needed)
    python providers.py --refresh   # download the newest monthly NPPES file (about 1.1 GB) and extract Puerto Rico again
    python providers.py --check     # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

Source, no key: CMS's National Plan and Provider Enumeration System (NPPES), the monthly full replacement file (https://download.cms.gov/nppes/NPI_Files.html;
US Government work). Every health care provider who bills in the United States has a National Provider Identifier (NPI) with a practice address and up to
fifteen taxonomy codes (the NUCC Health Care Provider Taxonomy), one marked primary.

What is counted. Individual providers (entity type 1) whose NPI is active (no deactivation date, or reactivated since) and whose practice location is in
Puerto Rico, by their primary taxonomy code (TYPES). Registered nurses are not counted: only nurses who bill need an NPI, so the registry lists about
1,250 against tens of thousands working in Puerto Rico. The ZIP file is read as a stream; only NPI-free columns of Puerto Rico rows reach the cache
(cache/nppes/providers_pr.csv: taxonomy, city, ZIP, last update year): no name, NPI, address or telephone. Only counts by municipio are published.

Where a provider is counted: the practice location's city when it is a municipio's name; otherwise a known postal place (Hato Rey, Río Piedras, Santurce
are San Juan); otherwise the municipio holding most of the land of its ZIP code (Census ZCTA file) - the placement nonprofits.py uses.

Privacy (decision 107 d): the rows are about single people, so a municipio's count of 1 to 9 is not published (the value is empty and the definition says
so); 0 and counts of 10 or more are. The island's totals are exact.

It is a registry, not a head count: a provider who left Puerto Rico, retired or works part-time may still be listed at a Puerto Rico address, and one
person can practise in several municipios but is counted once, at the primary practice location. The notes give how many records were last updated more
than five years ago, and for each type the count of records updated within five years: the registered count is the top of a range and the
recently updated count its bottom (many providers never update a record that is still right).
"""

import csv
import io
import json
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "nppes"
SMALL = CACHE / "providers_pr.csv"
OUT = DATA / "providers_series.json"
PAGE = "https://download.cms.gov/nppes/NPI_Files.html"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
FLOOR = 10
STALE_YEARS = 5
G = "Health · Health care providers (NPPES registry)"

# key, label, Spanish, taxonomy prefixes (NUCC); the first match wins, in this order
TYPES = [
    ("prov_primary_care", "Primary care physicians", "Médicos de atención primaria",
     ("207Q", "208D", "207R00000X", "208000000X", "207V00000X")),   # family medicine, general practice, internal medicine (general), pediatrics (general), OB-GYN (general)
    ("prov_psychiatrists", "Psychiatrists", "Psiquiatras", ("2084P0800X", "2084P0804X", "2084P0805X", "2084P0802X")),
    ("prov_other_physicians", "Other physicians (specialists)", "Otros médicos (especialistas)", ("20",)),
    ("prov_dentists", "Dentists", "Dentistas", ("1223",)),
    ("prov_np_pa", "Nurse practitioners and physician assistants", "Enfermeros practicantes y asistentes médicos", ("363L", "363A")),
    ("prov_mental_other", "Psychologists, counselors and social workers", "Psicólogos, consejeros y trabajadores sociales", ("103T", "101Y", "1041")),
    ("prov_pharmacists", "Pharmacists", "Farmacéuticos", ("1835",)),
]
SOURCES = {
    "cms_nppes": {"name": "CMS — National Plan and Provider Enumeration System (NPPES), monthly full file", "url": PAGE,
                  "license": "US Government work (public domain)", "note": "Individual providers with an active NPI and a Puerto Rico practice location; only counts by municipio are published."},
    "census_zcta_county": {"name": "US Census Bureau — 2020 ZCTA to county relationship file", "url": "https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html",
                           "license": "US federal government data (public domain)", "note": "Places a provider in the municipio holding most of the land of its ZIP code when its city is not a municipio's name."},
}


def log(*a):
    print(*a, flush=True)


def type_of(code):
    code = (code or "").strip()
    for key, _, _, prefixes in TYPES:
        if any(code.startswith(p) for p in prefixes):
            return key
    return None


def newest_zip():
    import re
    import requests
    html = requests.get(PAGE, headers=UA, timeout=60).text
    names = re.findall(r"NPPES_Data_Dissemination_[A-Za-z]+_\d{4}_V2\.zip", html)
    if not names:
        raise SystemExit("providers: no monthly file named on the NPPES page")
    return names[0]


def extract(zip_path):
    """Stream the national CSV inside the ZIP and keep Puerto Rico's individual providers: primary taxonomy, practice city and ZIP, last update year, active flag."""
    z = zipfile.ZipFile(zip_path)
    name = next(n for n in z.namelist() if n.startswith("npidata_pfile_") and n.endswith(".csv") and "fileheader" not in n.lower())
    out, seen = [], 0
    with z.open(name) as f:
        r = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        head = next(r)
        ix = {h: i for i, h in enumerate(head)}
        st, ent = ix["Provider Business Practice Location Address State Name"], ix["Entity Type Code"]
        city, zp = ix["Provider Business Practice Location Address City Name"], ix["Provider Business Practice Location Address Postal Code"]
        deact, react, upd = ix["NPI Deactivation Date"], ix["NPI Reactivation Date"], ix["Last Update Date"]
        tax = [(ix[f"Healthcare Provider Taxonomy Code_{k}"], ix[f"Healthcare Provider Primary Taxonomy Switch_{k}"]) for k in range(1, 16)]
        for row in r:
            seen += 1
            if row[st] not in ("PR", "PUERTO RICO") or row[ent] != "1":
                continue
            prim = next((row[c] for c, s in tax if row[s] == "Y"), "") or row[tax[0][0]]
            active = not row[deact] or bool(row[react])
            out.append([prim, row[city], row[zp][:5], (row[upd] or "")[-4:], "1" if active else "0"])
    CACHE.mkdir(parents=True, exist_ok=True)
    with SMALL.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["taxonomy", "city", "zip", "last_update_year", "active"])
        w.writerows(sorted(out))
    (CACHE / "providers_pr.source.json").write_text(json.dumps({"zip": zip_path.name, "national_rows": seen}), encoding="utf-8")
    log(f"  kept {len(out):,} Puerto Rico individual providers of {seen:,} national records")


def rows(refresh=False, offline=False):
    if refresh and not offline:
        import requests
        name = newest_zip()
        p = CACHE / name
        if not p.exists():
            CACHE.mkdir(parents=True, exist_ok=True)
            log(f"  downloading {name}")
            with requests.get(PAGE.rsplit("/", 1)[0] + "/" + name, headers=UA, stream=True, timeout=1800) as r:
                r.raise_for_status()
                with open(p, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        extract(p)
    if not SMALL.exists():
        zips = sorted(CACHE.glob("NPPES_*.zip"))
        if offline or not zips:
            raise SystemExit("providers: cache/nppes/providers_pr.csv is missing (python providers.py --refresh)")
        extract(zips[-1])
    with SMALL.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f)), json.loads((CACHE / "providers_pr.source.json").read_text(encoding="utf-8"))


def assemble(refresh=False, offline=False):
    import nonprofits
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    ids, names = [r[0] for r in muni], [r[2] for r in muni]
    by_name = {nonprofits.norm(n): f for n, f in zip(names, ids)}
    zc = nonprofits.zcta(refresh=False, offline=offline)
    data, src = rows(refresh, offline)
    at = {m: i for i, m in enumerate(ids)}
    counts = {k: [0] * len(ids) for k, *_ in TYPES}
    island, recent = Counter(), Counter()
    how, other, stale, inactive = Counter(), 0, 0, 0
    this_year = date.today().year
    for r in data:
        if r["active"] != "1":
            inactive += 1
            continue
        k = type_of(r["taxonomy"])
        if not k:
            other += 1
            continue
        island[k] += 1
        if r["last_update_year"].isdigit() and this_year - int(r["last_update_year"]) > STALE_YEARS:
            stale += 1
        else:
            recent[k] += 1
        f, h = nonprofits.place({"CITY": r["city"], "ZIP": r["zip"]}, by_name, zc)
        how[h] += 1
        if f in at:
            counts[k][at[f]] += 1
    REF = f"CMS NPPES monthly full file ({src['zip']}): individual providers with an active NPI and a Puerto Rico practice location, by primary taxonomy, counted by municipio"
    TAIL = (f" Counted at the primary practice location in the NPPES registry, by the provider's primary taxonomy code. A registry, not a head count: a provider who left, retired "
            f"or works part-time may still be listed. To protect individuals, a municipio with 1 to {FLOOR - 1} is shown empty; the island total is exact.")
    vs = []
    for key, en, es, prefixes in TYPES:
        vals = [c if (c == 0 or c >= FLOOR) else None for c in counts[key]]
        vs.append({"key": key, "group": G, "label": en, "unit": "", "d": 0, "type": "count", "sources": ["cms_nppes", "census_zcta_county"], "ref": REF,
                   "definition": f"{en} registered in NPPES with a practice location in the municipio (taxonomy codes {', '.join(prefixes)})." + TAIL, "family": "providers",
                   "years": {str(this_year): [*vals, island[key]]}})
    placed = sum(how[h] for h in how if h != "not placed")
    notes = {"source_file": src["zip"], "national_records": src["national_rows"], "pr_individual_records": len(data), "inactive": inactive, "other_types": other,
             "counted": sum(island.values()), "placed_by": dict(how), "placed_pct": round(placed / max(1, sum(how.values())) * 100, 1),
             f"last_updated_over_{STALE_YEARS}_years_ago": stale, "floor": FLOOR,
             "suppressed_cells": sum(1 for key, *_ in TYPES for c in counts[key] if 0 < c < FLOOR),
             "range": {key: {"registered": island[key], f"updated_within_{STALE_YEARS}_years": recent[key]} for key, *_ in TYPES}}
    return {"as_of": date.today().isoformat(), "years": [this_year], "geo": {"ids": [*ids, "72"], "names": [*names, "Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    doc = assemble(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")
    y = str(doc["years"][0])
    for v in doc["vars"]:
        log(f"  {v['key']:24s} island {v['years'][y][-1]:,}")
    log("  " + json.dumps(doc["notes"]))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in sys.argv and not SMALL.exists():
        print(f"providers: {SMALL} is not in the cache; nothing to check")
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
