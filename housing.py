"""Housing dimension for the PR Data Observatory, modeled on FPR's "The State of Housing in Puerto Rico:
An Analysis of the Factors That Impact Housing and Rent Prices" (2023, Advancing Equitable
Neighborhood Development grant).

The paper's tables are reproduced for all 78 municipalities from the same public source
(US Census Bureau, American Community Survey 5-year) without an API key, using the ACS summary files:

  latest  ACS 5-year table-based summary file (one .dat per table, nationwide, filtered to PR counties)
  2012    ACS 5-year sequence files for Puerto Rico (the paper's 2012-2021 change window starts here)

Variables (paper reference in brackets):
  median home value, median gross rent, median household income           [Table 9 change columns]
  share of adults 25+ with a bachelor's degree or higher                   [Table 9]
  residents per housing unit                                               [Table 9 ratio]
  renters paying 30%+ of income (cost-burdened)                            [Table 3 GRAPI]
  owners with a mortgage paying 30%+ of income                             [Table 4 SMOCAPI]
  home ownership affordability ratio: median value / max affordable loan   [Table 6 method]
  owner-occupied share                                                      [Table 7]
  vacant units and seasonal/recreational units (weekend homes proxy)       [Sec. 2 vacancy]
  poverty rate, median age, employment rate                                [Table 11]
Plus the paper's own published Table 10 (LIHTC projects, CDBG-DR), kept as published with citation.
"""

import csv
import io
import json
import zipfile
from pathlib import Path

import requests

UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
LATEST = 2024  # ACS 2020-2024 5-year
BASE = 2012    # ACS 2008-2012 5-year
TB_URL = "https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/data/5YRData/acsdt5y{y}-{t}.dat"
SEQ_ZIP = "https://www2.census.gov/programs-surveys/acs/summary_file/2012/data/5_year_by_state/PuertoRico_All_Geographies_Not_Tracts_Block_Groups.zip"
SEQ_LOOKUP = "https://www2.census.gov/programs-surveys/acs/summary_file/2012/documentation/5_year/user_tools/Sequence_Number_and_Table_Number_Lookup.txt"

TABLES_LATEST = ["b25077", "b25064", "b19013", "b25002", "b25004", "b25003", "b15003", "b25070", "b25091", "b01003", "b17001", "b01002", "b23025"]
TABLES_BASE = ["B25077", "B25064", "B19013", "B15002", "B01003"]

SOURCES = {
    "acs_latest": {
        "name": f"US Census Bureau — American Community Survey {LATEST - 4}–{LATEST} 5-year estimates (summary file)",
        "url": f"https://www2.census.gov/programs-surveys/acs/summary_file/{LATEST}/table-based-SF/",
        "license": "US Government work; cite the Census Bureau as the source",
        "credit": f"Housing and income: US Census Bureau ACS {LATEST} 5-year",
    },
    "acs_2012": {
        "name": "US Census Bureau — American Community Survey 2008–2012 5-year estimates (summary file)",
        "url": "https://www2.census.gov/programs-surveys/acs/summary_file/2012/",
        "license": "US Government work; cite the Census Bureau as the source",
        "credit": "2012 baseline: US Census Bureau ACS 2012 5-year",
    },
    "fpr_housing_2023": {
        "name": "Foundation for Puerto Rico — The State of Housing in Puerto Rico: An Analysis of the Factors That Impact Housing and Rent Prices in Puerto Rico and Proposed Strategies to Increase Housing Affordability (2023)",
        "url": "https://foundationforpuertorico.org/wp-content/uploads/2023/05/state_of_housing.pdf",
        "license": "© Foundation for Puerto Rico 2023. Advancing Equitable Neighborhood Development grant, funded in part by NALCAB. Tables reproduced as published",
        "credit": "Study figures: FPR, The State of Housing in Puerto Rico (2023), NALCAB Advancing Equitable Neighborhood Development grant",
        "home": "https://foundationforpuertorico.org/",
        "program": "https://foundationforpuertorico.org/en/housing-in-puerto-rico/"
    },
    "nalcab": {
        "name": "NALCAB — National Association for Latino Community Asset Builders, Advancing Equitable Neighborhood Development program",
        "url": "https://nalcab.org/",
        "license": "Grant funder of the 2023 study (planning grant to Foundation for Puerto Rico)",
        "credit": "The State of Housing study was funded in part by NALCAB"
    },
}

# Table 10: LIHTC projects, CDBG-DR (as published)
PAPER_LIHTC = [
    {"name": "Jose Gautier Benitez (JGB) Family", "municipality": "Caguas", "type": "Multifamily apartments", "units": 238, "beneficiaries": "Low-income families", "cost": 82341000, "cdbg_dr": 31715900},
    {"name": "De Diego Village", "municipality": "San Juan", "type": "Multifamily apartments", "units": 94, "beneficiaries": "One-parent families", "cost": 33811005, "cdbg_dr": 18127253},
    {"name": "JGB Elderly", "municipality": "Caguas", "type": "Nursing home", "units": 200, "beneficiaries": "Elderly", "cost": 53077000, "cdbg_dr": 14147390},
    {"name": "Sabana Village Apartments", "municipality": "San Juan", "type": "Multifamily apartments", "units": 160, "beneficiaries": "Low-income families, people with HIV, people experiencing homelessness", "cost": 26109567, "cdbg_dr": 9995987},
    {"name": "Hogar Manuel Mediavilla Negrón II", "municipality": "Humacao", "type": "Nursing home", "units": 90, "beneficiaries": "Elderly and handicapped people", "cost": 25622726, "cdbg_dr": 8576778},
    {"name": "San Blas Apartments", "municipality": "Coamo", "type": "Nursing home", "units": 69, "beneficiaries": "Elderly and handicapped people", "cost": 21128774, "cdbg_dr": 7969563},
]

# Affordability method from Table 6: 30% of income for housing, ~78% of that to principal and interest,
# 30-year loan. The paper's row for Puerto Rico ($21,967 -> $80,181) implies a ~5% rate.
MORTGAGE_RATE = 0.05
PI_SHARE = 430 / 549


def _get(url, path: Path, refresh=False, stream=False) -> Path:
    if path.exists() and not refresh:
        return path
    with requests.get(url, headers={"User-Agent": UA}, timeout=600, stream=True) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path


def _num(v):
    try:
        x = float(v)
        return None if x <= -666666666 else x
    except (TypeError, ValueError):
        return None


def load_latest(cache: Path, refresh: bool):
    """ACS table-based files -> {geoid: {column: value}} for PR counties."""
    out = {}
    d = cache / "acs"
    d.mkdir(exist_ok=True)
    for t in TABLES_LATEST:
        p = _get(TB_URL.format(y=LATEST, t=t), d / f"acsdt5y{LATEST}-{t}.dat", refresh)
        with open(p, encoding="utf-8", errors="replace") as f:
            header = f.readline().rstrip("\n").split("|")
            for line in f:
                if not line.startswith("0500000US72"):
                    continue
                row = line.rstrip("\n").split("|")
                geoid = row[0][-5:]
                rec = out.setdefault(geoid, {})
                for k, v in zip(header[1:], row[1:]):
                    if k.endswith(("E001",)) or "_E" in k:
                        rec[k.replace("_E", "_")] = _num(v)
        print(f"  ACS {LATEST} {t.upper()}: {len(out)} municipalities", flush=True)
    return out


def load_2012(cache: Path, refresh: bool):
    """ACS 2012 5-year sequence files for PR -> {geoid: {TABLE_cell: value}}."""
    d = cache / "acs"
    d.mkdir(exist_ok=True)
    zp = _get(SEQ_ZIP, d / "acs2012_pr_not_tracts.zip", refresh)
    lk = _get(SEQ_LOOKUP, d / "acs2012_lookup.txt", refresh)
    # lookup: table -> (sequence, start position, cells)
    meta = {}
    with open(lk, encoding="latin-1") as f:
        for row in csv.DictReader(f):
            tid = row["Table ID"].strip()
            if tid in TABLES_BASE and row["Line Number"].strip() == "" and row["Start Position"].strip():
                meta[tid] = (int(row["Sequence Number"]), int(row["Start Position"]), int(row["Total Cells in Table"].split()[0]))
    missing = [t for t in TABLES_BASE if t not in meta]
    if missing:
        raise RuntimeError(f"2012 lookup missing tables {missing}")
    z = zipfile.ZipFile(zp)
    names = z.namelist()
    geo_name = next(n for n in names if n.lower().startswith("g20125pr") and n.lower().endswith(".csv"))
    logrec = {}
    for row in csv.reader(io.TextIOWrapper(z.open(geo_name), encoding="latin-1")):
        # SUMLEVEL col 2, LOGRECNO col 4, GEOID col 48 (e.g. 05000US72001)
        if len(row) > 48 and row[2] == "050":
            logrec[row[4]] = row[48][-5:]
    out = {}
    for tid, (seq, start, cells) in meta.items():
        fname = next(n for n in names if n.lower() == f"e20125pr{seq:04d}000.txt")
        for row in csv.reader(io.TextIOWrapper(z.open(fname), encoding="latin-1")):
            geoid = logrec.get(row[5])
            if not geoid:
                continue
            rec = out.setdefault(geoid, {})
            for i in range(cells):
                rec[f"{tid}_{i + 1:03d}"] = _num(row[start - 1 + i])
        print(f"  ACS 2012 {tid}: seq {seq}, {len(out)} municipalities", flush=True)
    return out


def pct(a, b, d=1):
    return round(a / b * 100, d) if a is not None and b else None


def change_pct(new, old):
    return round((new - old) / old * 100, 1) if new is not None and old else None


def max_affordable_loan(income):
    if not income:
        return None
    pmt = income * 0.30 / 12 * PI_SHARE
    r = MORTGAGE_RATE / 12
    return round(pmt * (1 - (1 + r) ** -360) / r)


def build_housing(cache: Path, refresh: bool, stats: dict, geoid_by_name: dict, pop2020: dict):
    """Adds housing fields to `stats` (per municipality) and returns (paper_data, meta)."""
    print("Housing (ACS summary files, State of Housing 2023 method)")
    latest = load_latest(cache, refresh)
    base = load_2012(cache, refresh)
    n = 0
    for name, s in stats.items():
        g = geoid_by_name.get(name)
        L, B = latest.get(g, {}), base.get(g, {})
        if not L:
            continue
        n += 1
        income, value, rent = L.get("B19013_001"), L.get("B25077_001"), L.get("B25064_001")
        units, occupied, vacant = L.get("B25002_001"), L.get("B25002_002"), L.get("B25002_003")
        seasonal = L.get("B25004_006")
        owner_occ, occ_total = L.get("B25003_002"), L.get("B25003_001")
        pop25 = L.get("B15003_001")
        bach = sum(L.get(f"B15003_{k:03d}") or 0 for k in (22, 23, 24, 25)) if pop25 else None
        renters = L.get("B25070_001")
        rent_burden = sum(L.get(f"B25070_{k:03d}") or 0 for k in (7, 8, 9, 10)) if renters else None
        owners_mtg = L.get("B25091_002")
        own_burden = sum(L.get(f"B25091_{k:03d}") or 0 for k in (8, 9, 10, 11)) if owners_mtg else None
        pov_total, pov_below = L.get("B17001_001"), L.get("B17001_002")
        emp_pop, employed = L.get("B23025_001"), L.get("B23025_004")
        loan = max_affordable_loan(income)
        b_pop25 = B.get("B15002_001")
        b_bach = sum(B.get(f"B15002_{k:03d}") or 0 for k in (15, 16, 17, 18, 32, 33, 34, 35)) if b_pop25 else None
        hu2020 = pop2020.get(name, {}).get("housing_units_2020") or s.get("housing_units_2020")
        s.update({
            "acs_year": LATEST,
            "median_home_value": value, "median_gross_rent": rent, "median_hh_income": income,
            "housing_units_acs": units, "vacant_units": vacant, "vacancy_pct": pct(vacant, units),
            "seasonal_units": seasonal, "seasonal_pct": pct(seasonal, units),
            "owner_occupied_pct": pct(owner_occ, occ_total),
            "bachelors_pct": pct(bach, pop25),
            "renter_cost_burden_pct": pct(rent_burden, renters - (L.get("B25070_011") or 0) if renters else None),
            "owner_cost_burden_pct": pct(own_burden, owners_mtg - (L.get("B25091_012") or 0) if owners_mtg else None),
            "poverty_pct": pct(pov_below, pov_total),
            "median_age": L.get("B01002_001"),
            "employment_rate_pct": pct(employed, emp_pop),
            "max_affordable_loan": loan,
            "affordability_ratio": round(value / loan, 2) if value and loan else None,
            "residents_per_unit": round(s["population_2020"] / hu2020, 2) if s.get("population_2020") and hu2020 else None,
            "home_value_change_pct": change_pct(value, B.get("B25077_001")),
            "gross_rent_change_pct": change_pct(rent, B.get("B25064_001")),
            "income_change_pct": change_pct(income, B.get("B19013_001")),
            "bachelors_change_pts": round(pct(bach, pop25) - pct(b_bach, b_pop25), 1) if bach is not None and b_bach is not None and pct(b_bach, b_pop25) is not None else None,
            "population_change_2012_pct": change_pct(L.get("B01003_001"), B.get("B01003_001")),
        })
    # island-wide cost-burden distributions (Tables 3 and 4 method), summed from the municipality tables
    def dist(table, first, last):
        tot = sum((latest[g].get(f"{table}_{k:03d}") or 0) for g in latest for k in range(first, last + 1))
        return [round(sum((latest[g].get(f"{table}_{k:03d}") or 0) for g in latest) / tot * 100, 1) for k in range(first, last + 1)] if tot else None
    grapi = dist("B25070", 2, 10)
    smocapi = dist("B25091", 3, 11)
    paper = {
        "grapi": grapi, "smocapi": smocapi,
        "renters_burdened_pct": round(sum(grapi[5:]), 1) if grapi else None, "owners_burdened_pct": round(sum(smocapi[5:]), 1) if smocapi else None,
        "lihtc": PAPER_LIHTC,
        "headline": {"housing_units_2020": 1_600_000, "vacant_homes_2020": 370_000, "abandoned_estimate": 300_000, "annual_new_housing_deficit": 20_000},
        "citation": "Foundation for Puerto Rico (2023). The State of Housing in Puerto Rico: An Analysis of the Factors That Impact Housing and Rent Prices in Puerto Rico and Proposed Strategies to Increase Housing Affordability. Advancing Equitable Neighborhood Development grant, funded in part by NALCAB (National Association for Latino Community Asset Builders). Tables 2, 3, 4, 6, 7, 10, 11.",
        "links": {"study_pdf": "https://foundationforpuertorico.org/wp-content/uploads/2023/05/state_of_housing.pdf", "fpr_housing_page": "https://foundationforpuertorico.org/en/housing-in-puerto-rico/", "nalcab": "https://nalcab.org/", "fpr_home": "https://foundationforpuertorico.org/"},
    }
    pr = {k: v for k, v in latest.items()}
    meta = {"acs_latest": LATEST, "acs_base": BASE, "municipalities_with_acs": n, "method": "FPR State of Housing 2023, Table 6 affordability method (30% of income, 78% to principal and interest, 30-year loan at 5%)"}
    print(f"  housing fields added for {n} municipalities (ACS {LATEST} vs {BASE})")
    return paper, meta


if __name__ == "__main__":
    import sys
    cache = Path(__file__).resolve().parent / "cache"
    cache.mkdir(exist_ok=True)
    L = load_latest(cache, "--refresh" in sys.argv)
    B = load_2012(cache, False)
    print("latest sample 72127:", {k: L["72127"].get(k) for k in ("B25077_001", "B25064_001", "B19013_001", "B25002_001", "B25004_006")})
    print("2012 sample 72127:", {k: B["72127"].get(k) for k in ("B25077_001", "B25064_001", "B19013_001", "B01003_001", "B15002_001")})
