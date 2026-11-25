"""Housing time series for the PR Data Observatory: every year the public sources allow, for all 78 municipalities and Puerto Rico.

    python housing_series.py              # build site/data/housing_series.json (downloads only what is missing; seconds when cached)
    python housing_series.py --refresh    # re-download everything

Sources, none needing an API key:
  Population      Census Bureau decennial counts (2010, 2020) and Population Estimates for municipios: Vintage 2020 (2011-2019,
                  based on the 2010 census) and Vintage 2025 (2021-2025, based on the 2020 census), plus the 65+ share.
  Census housing  2010 and 2020 PL 94-171 redistricting files, table H1: housing units, occupied, vacant.
  ACS 5-year      Every vintage 2010-2024 (2006-2010 ... 2020-2024) from the Census summary files: per-sequence files for
                  2010-2020, table-based files for 2021-2024. About 40 variables, each with its margin of error where the
                  Census Bureau publishes one. Labeled by the last year of the five-year window.
  FEMA            OpenFEMA Housing Assistance (owners and renters): households approved for Individual Assistance and dollars,
                  by municipality and year of the disaster declaration.

Output layout (arrays are indexed like geo.names; the last entry is Puerto Rico as a whole):
  {"built", "latest", "years", "geo": {"ids", "names"}, "vars": {key: {meta..., "years": {"2012": [...]}, "moe": {"2012": [...]}}},
   "tables": {...Puerto Rico-level tables for the study's Tables 3, 4, 6 and 7, by year}, "sources": {...}}
"""

import csv
import io
import json
import re
import sys
import unicodedata
import zipfile
from math import sqrt
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "housing"
OUT = ROOT / "site" / "data"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}

BASE = "https://www2.census.gov/programs-surveys/acs/summary_file/"
POPEST = "https://www2.census.gov/programs-surveys/popest/datasets/"
SEQ_YEARS = range(2010, 2021)                # per-sequence summary files (older vintages)


def _exists(url):
    try:
        return requests.head(url, headers=UA, timeout=60, allow_redirects=True).status_code == 200
    except requests.RequestException:
        return False


def latest_acs():
    """Last ACS 5-year vintage published as a table-based file: starts from 2024 and looks for the next ones."""
    y = 2024
    while _exists(BASE + f"{y + 1}/table-based-SF/data/5YRData/acsdt5y{y + 1}-b25077.dat"):
        y += 1
    return y


def latest_vintage():
    """Last Population Estimates vintage with a Puerto Rico age-and-sex file (2025 at the time of writing)."""
    y = 2025
    while _exists(POPEST + f"2020-{y + 1}/puerto-rico/asrh/cc-est{y + 1}-agesex-72.csv"):
        y += 1
    return y


ACS_LAST = latest_acs()
VINTAGE = latest_vintage()
ACS_YEARS = list(range(2010, ACS_LAST + 1))          # 5-year vintages, by last year of the window
POP_YEARS = list(range(2010, VINTAGE + 1))
TB_YEARS = range(2021, ACS_LAST + 1)                 # table-based summary files
MORTGAGE_RATE = 0.05                         # the study's Table 6 assumption, held fixed so years differ only in prices and incomes
PI_SHARE = 430 / 549

# tables that did not exist yet in the earliest vintages: table -> last year without it
NOT_BEFORE = {"B23025": 2010, "B28002": 2013}
OPTIONAL = {"B28002"}                       # skipped, not an error, when a vintage lacks it or lays it out differently

# tables read from every vintage, with the number of cells each must have (a mismatch means the layout changed)
TABLES = {"B01002": 3, "B01003": 1, "B15002": 35, "B17001": 59, "B19013": 1, "B19049": 5, "B19301": 1, "B23025": 7, "B25001": 1,
          "B25002": 3, "B25003": 3, "B25004": 8, "B25007": 21, "B25010": 3, "B25014": 13, "B25024": 11, "B25035": 1, "B25064": 1,
          "B25070": 11, "B25071": 1, "B25077": 1, "B25088": 3, "B25091": 23, "B25119": 3}


def norm(s):
    return re.sub(r"[̀-ͯ]", "", unicodedata.normalize("NFD", s or "")).lower().strip()


def log(*a):
    print(*a, flush=True)


def fetch(url, path: Path, refresh=False, binary=True):
    if path.exists() and not refresh:
        return path.read_bytes() if binary else path.read_text(encoding="utf-8", errors="replace")
    r = requests.get(url, headers=UA, timeout=300)
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return r.content if binary else r.text


# ── Geography ────────────────────────────────────────────────────────────────

def municipalities():
    fc = json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))
    rows = sorted(((f["properties"]["municipality"], str(f["properties"]["GEOID"])[:5]) for f in fc["features"] if f["properties"].get("municipality")), key=lambda r: norm(r[0]))
    return [r[0] for r in rows], [r[1] for r in rows]


# ── ACS ──────────────────────────────────────────────────────────────────────

def _est(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x <= -222222222 else x


def _moe(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x < 0 else x


def acs_sequence(year, refresh=False, tables=None):
    """{geoid: {'B25077_001': [estimate, moe]}} for Puerto Rico ('72') and its 78 municipios, from the per-sequence files."""
    tables = tables or TABLES
    d = CACHE / "raw" / f"acs{year}"
    lookup_url = BASE + (f"{year}/documentation/5_year/user_tools/Sequence_Number_and_Table_Number_Lookup.txt" if year <= 2012 else f"{year}/documentation/user_tools/ACS_5yr_Seq_Table_Number_Lookup.txt")
    lk = fetch(lookup_url, d / "lookup.txt", refresh, binary=False)
    meta = {}

    def pick(row, *names):
        for n in names:
            if n in row and row[n] is not None:
                return str(row[n]).strip()
        return ""

    for row in csv.DictReader(io.StringIO(lk)):
        tid = pick(row, "Table ID")
        line, start = pick(row, "Line Number", "Line Number Decimal M Lines"), pick(row, "Start Position", "position")
        if tid in tables and line in ("", ".") and start.isdigit():
            meta[tid] = (int(pick(row, "Sequence Number", "seq")), int(start), int(pick(row, "Total Cells in Table", "cells").split()[0]))
    for t, n in tables.items():
        if t not in meta:
            if year <= NOT_BEFORE.get(t, 0) or t in OPTIONAL:
                continue
            raise RuntimeError(f"ACS {year}: table {t} not in the lookup")
        if meta[t][2] != n:
            if t in OPTIONAL:
                del meta[t]
                continue
            raise RuntimeError(f"ACS {year}: {t} has {meta[t][2]} cells, expected {n}; check the layout")
    seqdir = BASE + f"{year}/data/5_year_seq_by_state/PuertoRico/All_Geographies_Not_Tracts_Block_Groups/"
    g = fetch(seqdir + f"g{year}5pr.csv", d / "geo.csv", refresh, binary=False)
    logrec = {}
    for row in csv.reader(io.StringIO(g)):
        m = re.search(r"0[45]000US(72\d{0,3})", ",".join(row))
        if m and (m.group(1) == "72" or len(m.group(1)) == 5):
            logrec[row[4]] = m.group(1)
    out = {}
    for seq in sorted({s for s, _, _ in meta.values()}):
        zp = fetch(seqdir + f"{year}5pr{seq:04d}000.zip", d / f"seq{seq:04d}.zip", refresh)
        z = zipfile.ZipFile(io.BytesIO(zp))
        names = {n.lower(): n for n in z.namelist()}
        est = list(csv.reader(io.TextIOWrapper(z.open(names[f"e{year}5pr{seq:04d}000.txt"]), encoding="latin-1")))
        mo = {r[5]: r for r in csv.reader(io.TextIOWrapper(z.open(names[f"m{year}5pr{seq:04d}000.txt"]), encoding="latin-1"))}
        for tid, (s, start, cells) in meta.items():
            if s != seq:
                continue
            for row in est:
                gid = logrec.get(row[5])
                if not gid:
                    continue
                mrow = mo.get(row[5])
                rec = out.setdefault(gid, {})
                for i in range(cells):
                    rec[f"{tid}_{i + 1:03d}"] = [_est(row[start - 1 + i]), _moe(mrow[start - 1 + i]) if mrow else None]
    return out


def acs_table_based(year, refresh=False, tables=None):
    """The same, from the table-based files (one nationwide file per table; Puerto Rico's rows come early, so reading stops there)."""
    tables = tables or TABLES
    d = CACHE / "raw" / f"acs{year}"
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in tables:
        p = d / f"{t}.json"
        if p.exists() and not refresh:
            rows = json.loads(p.read_text(encoding="utf-8"))
        else:
            url = BASE + f"{year}/table-based-SF/data/5YRData/acsdt5y{year}-{t.lower()}.dat"
            rows, header, seen = {}, None, 0
            with requests.get(url, headers=UA, stream=True, timeout=300) as r:
                if r.status_code == 404 and t in OPTIONAL:
                    continue
                r.raise_for_status()
                for raw in r.iter_lines(chunk_size=1 << 16):
                    line = raw.decode("utf-8", "replace")
                    if header is None:
                        header = line.split("|")
                        continue
                    if line.startswith("0400000US72") or line.startswith("0500000US72"):
                        f = line.split("|")
                        gid = f[0][-2:] if f[0].startswith("0400000US") else f[0][-5:]
                        rows[gid] = {header[i].replace("_E", "_").replace("_M", "_m"): f[i] for i in range(1, len(header))}
                        seen += 1
                    elif seen and line[:9] > "0500000US" and not line.startswith("0500000US72"):
                        break
            p.write_text(json.dumps(rows), encoding="utf-8")
        for gid, rec in rows.items():
            tgt = out.setdefault(gid, {})
            for k, v in rec.items():
                if "_m" in k:
                    continue
                m = rec.get(k.replace("_", "_m", 1))
                tgt[k] = [_est(v), _moe(m)]
        log(f"    ACS {year} {t}: {len(rows)} geographies")
    for t, n in tables.items():
        got = sum(1 for k in next(iter(out.values())) if k.startswith(t + "_"))
        if got != n:
            if t in OPTIONAL:
                for rec in out.values():
                    for k in [k for k in rec if k.startswith(t + "_")]:
                        del rec[k]
                continue
            raise RuntimeError(f"ACS {year}: {t} has {got} cells, expected {n}")
    return out


def acs_vintage(year, refresh=False, tables=None, tag="acs5"):
    cache = CACHE / f"{tag}_{year}.json"
    if cache.exists() and not refresh:
        return json.loads(cache.read_text(encoding="utf-8"))
    log(f"  ACS {year - 4}-{year} 5-year ...")
    data = acs_sequence(year, refresh, tables) if year in SEQ_YEARS else acs_table_based(year, refresh, tables)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


# ── Derived variables (value and margin of error) ────────────────────────────

class Cells:
    """Estimate-and-margin arithmetic for one geography: sums add margins in quadrature, ratios follow the Census Bureau's formulas."""

    def __init__(self, rec):
        self.rec = rec

    def cell(self, table, n):
        v = self.rec.get(f"{table}_{n:03d}")
        return (v[0], v[1]) if v else (None, None)

    def sum(self, table, ns):
        e, m = 0.0, 0.0
        for n in ns:
            v, mm = self.cell(table, n)
            if v is None:
                return None, None
            e += v
            m += (mm or 0) ** 2
        return e, sqrt(m)


def pct(num, den, subset=True):
    """Share in percent with its margin of error; num/den are (estimate, moe)."""
    (a, ma), (b, mb) = num, den
    if a is None or not b:
        return None, None
    p = a / b
    if ma is None or mb is None:
        return round(p * 100, 2), None
    rad = ma ** 2 - (p ** 2) * mb ** 2 if subset else ma ** 2 + (p ** 2) * mb ** 2
    if rad < 0:
        rad = ma ** 2 + (p ** 2) * mb ** 2
    return round(p * 100, 2), round(sqrt(rad) / b * 100, 2)


def max_loan(income):
    if not income:
        return None
    pmt = income * 0.30 / 12 * PI_SHARE
    r = MORTGAGE_RATE / 12
    return round(pmt * (1 - (1 + r) ** -360) / r)


def derive(rec, year):
    """All ACS-based variables for one geography and vintage: {key: (value, moe)}."""
    c = Cells(rec)
    one = c.cell
    out = {}

    def put(k, v, m=None):
        if v is not None:
            out[k] = (round(v, 2) if isinstance(v, float) else v, None if m is None else round(m, 2))

    hu, occ, vac = one("B25001", 1), one("B25002", 2), one("B25002", 3)
    put("housing_units", *hu); put("vacant_units", *vac)
    put("vacancy_pct", *pct(vac, hu))
    seas, other = one("B25004", 6), one("B25004", 8)
    put("seasonal_units", *seas); put("seasonal_pct", *pct(seas, hu))
    put("other_vacant_units", *other); put("other_vacant_pct", *pct(other, hu))
    for_rent, rented, for_sale, sold = one("B25004", 2), one("B25004", 3), one("B25004", 4), one("B25004", 5)
    owner, renter, hh = one("B25003", 2), one("B25003", 3), one("B25003", 1)
    put("households", *hh)
    put("owner_occupied_pct", *pct(owner, hh))
    if None not in (for_rent[0], rented[0], renter[0]):
        den = c.sum("B25004", [2, 3]); den = (den[0] + renter[0], sqrt(den[1] ** 2 + (renter[1] or 0) ** 2))
        put("rental_vacancy_pct", *pct(for_rent, den))
    if None not in (for_sale[0], sold[0], owner[0]):
        den = c.sum("B25004", [4, 5]); den = (den[0] + owner[0], sqrt(den[1] ** 2 + (owner[1] or 0) ** 2))
        put("homeowner_vacancy_pct", *pct(for_sale, den))
    put("avg_household_size", *one("B25010", 1))
    value, rent, income = one("B25077", 1), one("B25064", 1), one("B19013", 1)
    put("median_home_value", *value); put("median_gross_rent", *rent); put("median_hh_income", *income)
    put("per_capita_income", *one("B19301", 1))
    put("median_owner_income", *one("B25119", 2)); put("median_renter_income", *one("B25119", 3))
    put("median_rent_pct_income", *one("B25071", 1))
    put("median_owner_costs_mortgage", *one("B25088", 2)); put("median_owner_costs_no_mortgage", *one("B25088", 3))
    put("median_year_built", *one("B25035", 1))
    loan = max_loan(income[0])
    put("max_affordable_loan", loan)
    if value[0] and loan:
        put("affordability_ratio", value[0] / loan)
    # cost burden (Tables 3 and 4 method): households where the ratio can be computed
    rt = one("B25070", 1)
    rt_not = one("B25070", 11)
    if rt[0] is not None and rt_not[0] is not None:
        den = (rt[0] - rt_not[0], sqrt((rt[1] or 0) ** 2 + (rt_not[1] or 0) ** 2))
        put("renter_cost_burden_pct", *pct(c.sum("B25070", [7, 8, 9, 10]), den))
        put("renter_severe_burden_pct", *pct(one("B25070", 10), den))
    om, om_not = one("B25091", 2), one("B25091", 12)
    if om[0] is not None and om_not[0] is not None:
        den = (om[0] - om_not[0], sqrt((om[1] or 0) ** 2 + (om_not[1] or 0) ** 2))
        put("owner_cost_burden_pct", *pct(c.sum("B25091", [8, 9, 10, 11]), den))
    pov = one("B17001", 2)
    put("poverty_pct", *pct(pov, one("B17001", 1)))
    put("median_age", *one("B01002", 1))
    emp_pop = one("B23025", 1)
    put("employment_rate_pct", *pct(one("B23025", 4), emp_pop))
    put("unemployment_rate_pct", *pct(one("B23025", 5), one("B23025", 3)))
    adults = one("B15002", 1)
    put("bachelors_pct", *pct(c.sum("B15002", [15, 16, 17, 18, 32, 33, 34, 35]), adults))
    put("overcrowded_pct", *pct(c.sum("B25014", [5, 6, 7, 11, 12, 13]), one("B25014", 1)))
    units = one("B25024", 1)
    put("detached_house_pct", *pct(one("B25024", 2), units))
    put("apartments_5plus_pct", *pct(c.sum("B25024", [6, 7, 8, 9]), units))
    put("mobile_home_pct", *pct(one("B25024", 10), units))
    return out


def island_tables(rec):
    """Puerto Rico-level tables for the study's Tables 3, 4, 6, 7 from one vintage."""
    c = Cells(rec)
    g = [c.cell("B25070", n)[0] for n in range(2, 11)]
    s = [c.cell("B25091", n)[0] for n in range(3, 12)]
    gt, st = sum(x or 0 for x in g), sum(x or 0 for x in s)
    owner = c.cell("B25007", 2)[0]
    age_bins = [[3, 4], [5], [6], [7, 8], [9], [10], [11]]
    t7 = [round(sum(c.cell("B25007", n)[0] or 0 for n in b) / owner * 100, 1) if owner else None for b in age_bins]
    inc = [c.cell("B19049", n)[0] for n in range(1, 6)]   # all, 15-24, 25-44, 45-64, 65+
    return {"grapi": [round(x / gt * 100, 1) for x in g] if gt else None, "smocapi": [round(x / st * 100, 1) for x in s] if st else None,
            "t7_owner_age": t7, "t6_income_by_age": inc}


# ── Population ───────────────────────────────────────────────────────────────

def population(names, geoids, refresh=False):
    """{year: {geoid: population}}, basis per year, and the 65+ share, from the decennial counts and the two estimate vintages."""
    v20 = fetch(POPEST + "2010-2020/municipios/totals/PRM-EST2020.csv", CACHE / "PRM-EST2020.csv", refresh, binary=False)
    a20 = fetch(POPEST + "2010-2020/municipios/asrh/PRM-EST2020-AGESEX.csv", CACHE / "PRM-EST2020-AGESEX.csv", refresh, binary=False)
    a25 = fetch(POPEST + f"2020-{VINTAGE}/puerto-rico/asrh/cc-est{VINTAGE}-agesex-72.csv", CACHE / f"cc-est{VINTAGE}-agesex-72.csv", refresh, binary=False)
    pop, old, basis = {}, {}, {}
    for row in csv.DictReader(io.StringIO(v20)):
        if row["SUMLEV"] == "040":
            gid = "72"
        elif row["SUMLEV"] == "050":
            gid = "72" + row["COUNTY"].zfill(3)
        else:
            continue
        pop.setdefault(2010, {})[gid] = int(row["CENSUS2010POP"])
        for y in range(2011, 2020):
            pop.setdefault(y, {})[gid] = int(row[f"POPESTIMATE{y}"])
    for row in csv.DictReader(io.StringIO(a20)):
        if row["SUMLEV"] != "050":
            continue
        gid = "72" + row["MUNICIPIO"].zfill(3)
        yr = int(row["YEAR"])
        # YEAR 1 = 2010 census, 2 = estimates base, 3 = July 2010, 4 = July 2011 ... 12 = July 2019
        y = 2010 if yr == 1 else yr + 2007 if 4 <= yr <= 12 else None
        if y:
            old.setdefault(y, {})[gid] = (int(row["AGE65PLUS_TOT"]), int(row["POPESTIMATE"]), float(row["MEDIAN_AGE_TOT"]))
    new = {}
    for row in csv.DictReader(io.StringIO(a25)):
        gid = "72" + row["MUNICIPIO"].zfill(3)
        yr = int(row["YEAR"])   # 1 = 2020 census, 2 = July 2020, 3 = July 2021 ... 7 = July 2025
        if yr == 1:
            pop.setdefault(2020, {})[gid] = int(row["POPESTIMATE"])
            new.setdefault(2020, {})[gid] = (int(row["AGE65PLUS_TOT"]), int(row["POPESTIMATE"]), float(row["MEDIAN_AGE_TOT"]))
        elif yr >= 3:
            y = 2018 + yr
            pop.setdefault(y, {})[gid] = int(row["POPESTIMATE"])
            new.setdefault(y, {})[gid] = (int(row["AGE65PLUS_TOT"]), int(row["POPESTIMATE"]), float(row["MEDIAN_AGE_TOT"]))
    age = {}
    for src in (old, new):
        for y, d in src.items():
            a = age.setdefault(y, {})
            for gid, (a65, tot, med) in d.items():
                a[gid] = round(a65 / tot * 100, 2)
            a["72"] = round(sum(v[0] for v in d.values()) / sum(v[1] for v in d.values()) * 100, 2)
    for y in range(2010, VINTAGE + 1):
        basis[y] = "2010 census count" if y == 2010 else "2020 census count" if y == 2020 else "estimate, July 1 (Vintage 2020, 2010 census base)" if y < 2020 else f"estimate, July 1 (Vintage {VINTAGE}, 2020 census base)"
    if 2020 in pop:
        pop[2020]["72"] = sum(v for k, v in pop[2020].items() if k != "72")
    for y in range(2021, VINTAGE + 1):
        pop[y]["72"] = sum(v for k, v in pop[y].items() if k != "72")
    return pop, basis, age


def census_housing(refresh=False):
    """Census-day housing units, occupied and vacant for 2010 and 2020 from the PL 94-171 files: {year: {geoid: (units, occupied, vacant)}}."""
    out = {}
    for year, url, geo, h in ((2010, "https://www2.census.gov/census_2010/01-Redistricting_File--PL_94-171/Puerto_Rico/pr2010.pl.zip", "prgeo2010.pl", "pr000022010.pl"),
                              (2020, "https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Puerto_Rico/pr2020.pl.zip", "prgeo2020.pl", "pr000022020.pl")):
        p = CACHE / f"housing_census_{year}.json"
        if p.exists() and not refresh:
            out[year] = {k: tuple(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
            continue
        log(f"  Census {year} PL 94-171 (housing occupancy) ...")
        z = zipfile.ZipFile(io.BytesIO(fetch(url, CACHE / "raw" / f"pr{year}.pl.zip", refresh)))
        logrec = {}
        for raw in z.open(geo):
            line = raw.decode("latin-1")
            if year == 2020:
                f = line.split("|")
                if f[2] in ("040", "050"):
                    logrec[f[7]] = "72" if f[2] == "040" else f[8][-5:]
            elif line[8:11] in ("040", "050"):
                logrec[line[18:25]] = "72" if line[8:11] == "040" else "72" + line[29:32]
        res = {}
        for raw in z.open(h):
            f = raw.decode("latin-1").rstrip("\n").split("|" if year == 2020 else ",")
            gid = logrec.get(f[4])
            if gid:
                tail = [x for x in f if x != ""][-3:]
                res[gid] = tuple(int(x) for x in tail)
        p.write_text(json.dumps(res), encoding="utf-8")
        out[year] = res
    return out


def fema(names, geoids, refresh=False):
    """Households approved for FEMA Individual Assistance (owners + renters) and dollars, by municipality and declaration year."""
    p = CACHE / "fema_housing.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    log("  OpenFEMA housing assistance ...")
    api = "https://www.fema.gov/api/open/v2/"

    def pages(entity, flt, select=None):
        rows, skip = [], 0
        while True:
            params = {"$filter": flt, "$top": 1000, "$skip": skip}
            if select:
                params["$select"] = select
            r = requests.get(api + entity, params=params, headers=UA, timeout=300)
            r.raise_for_status()
            part = r.json().get(entity, [])
            rows += part
            if len(part) < 1000:
                return rows
            skip += 1000
    decl = {}
    for x in pages("DisasterDeclarationsSummaries", "state eq 'PR'", "disasterNumber,declarationDate,declarationTitle"):
        decl.setdefault(x["disasterNumber"], (x["declarationDate"][:4], x["declarationTitle"]))
    by = {}
    for ent in ("HousingAssistanceOwners", "HousingAssistanceRenters"):
        for x in pages(ent, "state eq 'PR'"):
            n = norm(re.sub(r"\s*\(.*\)", "", x["county"]))
            year, title = decl.get(x["disasterNumber"], (None, None))
            if not year:
                continue
            rec = by.setdefault(n, {}).setdefault(year, {"households": 0, "amount": 0.0, "disasters": {}})
            rec["households"] += x.get("approvedForFemaAssistance") or 0
            rec["amount"] += x.get("totalApprovedIhpAmount") or 0.0
            rec["disasters"][str(x["disasterNumber"])] = title
    p.write_text(json.dumps(by), encoding="utf-8")
    return by


# ── Catalog ──────────────────────────────────────────────────────────────────

ACS = "acs"
CATALOG = [
    # key, group, label, unit, decimals, source kind, tables, definition, extra
    ("population", "Population", "Resident population", "", 0, "pop", "Census counts (2010, 2020); Population Estimates", "People living in the municipality: the 2010 and 2020 census counts (April 1) and the Census Bureau's July 1 estimates for the other years. Estimates for 2011-2019 were built on the 2010 census and were never revised after the 2020 count, so the series steps up in 2020; later years are built on the 2020 census. The 2020 figure is the April 2020 base of the latest estimates, which includes the Census Bureau's post-census count corrections, so a few municipalities differ from the original count by a handful of people.", {}),
    ("pop_change_since_2010_pct", "Population", "Population change since the 2010 census", "%", 1, "pop", "Census counts; Population Estimates", "Percent change from the 2010 census count to the selected year.", {"diverging": True}),
    ("pop_change_since_2020_pct", "Population", "Population change since the 2020 census", "%", 1, "pop", "Census 2020; Population Estimates Vintage 2025", "Percent change from the 2020 census base to the selected year (2021 onward).", {"diverging": True}),
    ("age65_pct", "Population", "Residents aged 65 and over", "%", 1, "pop", "Population Estimates (age and sex)", "Share of residents 65 or older, from the Census Bureau's population estimates by age and sex.", {}),
    ("census_housing_units", "Housing stock", "Housing units, census count (number)", "", 0, "census", "PL 94-171 table H1", "Housing units counted on census day (April 1), 2010 and 2020.", {}),
    ("census_vacant_units", "Housing stock", "Vacant units, census count (number)", "", 0, "census", "PL 94-171 table H1", "Housing units vacant on census day.", {}),
    ("census_vacancy_pct", "Housing stock", "Vacancy rate, census count", "%", 1, "census", "PL 94-171 table H1", "Vacant units as a share of all housing units on census day. The American Community Survey puts vacancy higher (it is a five-year survey with its own vacancy test): neither is wrong, so compare each source only with itself.", {}),
    ("residents_per_unit", "Housing stock", "Residents per housing unit", "", 2, "census", "PL 94-171 tables P1 and H1", "Census population divided by census housing units (2010 and 2020). Below about 2 points to a surplus of homes over households.", {}),
    ("housing_units", "Housing stock", "Housing units (number)", "", 0, ACS, "ACS B25001", "All housing units, occupied or vacant, from the American Community Survey five-year estimates.", {}),
    ("vacant_units", "Housing stock", "Vacant housing units (number)", "", 0, ACS, "ACS B25002", "Housing units with no one living in them, including homes for sale or rent, seasonal homes and abandoned units.", {}),
    ("vacancy_pct", "Housing stock", "Vacant housing units, % of all units", "%", 1, ACS, "ACS B25002", "Share of all housing units that are vacant. Includes seasonal homes, units for sale or rent, and abandoned units.", {}),
    ("seasonal_units", "Housing stock", "Seasonal, recreational or occasional-use units (number)", "", 0, ACS, "ACS B25004", "Units held for seasonal, recreational or occasional use: the closest public proxy for weekend homes and short-term rentals.", {}),
    ("seasonal_pct", "Housing stock", "Seasonal, recreational or occasional-use units, % of all units", "%", 1, ACS, "ACS B25004", "Share of all units the Census classes as held for seasonal, recreational or occasional use. The best public proxy for weekend homes and short-term rentals.", {}),
    ("other_vacant_units", "Housing stock", "Other vacant units (number)", "", 0, ACS, "ACS B25004", "Vacant units that are not for sale, for rent, sold or rented, or seasonal. The usual public proxy for abandoned or dilapidated housing.", {}),
    ("other_vacant_pct", "Housing stock", "Other vacant units, % of all units (abandoned-housing proxy)", "%", 1, ACS, "ACS B25004", "Share of all units that are vacant for 'other' reasons: not for sale or rent, not seasonal. The usual public proxy for abandoned or dilapidated housing.", {}),
    ("rental_vacancy_pct", "Housing stock", "Rental vacancy rate", "%", 1, ACS, "ACS B25004, B25003", "Units for rent as a share of rental units (for rent, rented not yet occupied, and renter-occupied).", {}),
    ("homeowner_vacancy_pct", "Housing stock", "Homeowner vacancy rate", "%", 1, ACS, "ACS B25004, B25003", "Units for sale as a share of owner units (for sale, sold not yet occupied, and owner-occupied).", {}),
    ("detached_house_pct", "Housing stock", "Single-family detached homes", "%", 1, ACS, "ACS B25024", "Share of housing units that are detached single-family houses.", {}),
    ("apartments_5plus_pct", "Housing stock", "Units in buildings of 5 or more", "%", 1, ACS, "ACS B25024", "Share of housing units in buildings with five or more units.", {}),
    ("mobile_home_pct", "Housing stock", "Mobile homes", "%", 1, ACS, "ACS B25024", "Share of housing units that are mobile homes.", {}),
    ("median_year_built", "Housing stock", "Median year the home was built", "", 0, ACS, "ACS B25035", "Median year the structure was built, for all housing units.", {"plain": True}),
    ("overcrowded_pct", "Housing stock", "Overcrowded homes (more than 1 person per room)", "%", 1, ACS, "ACS B25014", "Occupied homes with more than one occupant per room.", {}),
    ("households", "Households", "Households (occupied housing units)", "", 0, ACS, "ACS B25003", "Occupied housing units.", {}),
    ("avg_household_size", "Households", "Average household size", "", 2, ACS, "ACS B25010", "People per occupied home.", {}),
    ("owner_occupied_pct", "Households", "Owner-occupied share of occupied units", "%", 1, ACS, "ACS B25003", "Owner-occupied units as a share of all occupied units.", {}),
    ("median_age", "Households", "Median age", "", 1, ACS, "ACS B01002", "Median age of residents, in years.", {}),
    ("poverty_pct", "Households", "Population below the poverty level", "%", 1, ACS, "ACS B17001", "Share of people whose income in the past 12 months was below the poverty level.", {}),
    ("employment_rate_pct", "Households", "Employment rate (16 and over)", "%", 1, ACS, "ACS B23025", "Employed civilians as a share of all residents 16 and over.", {}),
    ("unemployment_rate_pct", "Households", "Unemployment rate", "%", 1, ACS, "ACS B23025", "Unemployed as a share of the civilian labor force.", {}),
    ("bachelors_pct", "Households", "Adults 25+ with a bachelor's degree or higher", "%", 1, ACS, "ACS B15002", "Share of adults 25 and over holding a bachelor's, master's, professional or doctoral degree.", {}),
    ("median_home_value", "Prices and incomes", "Median home value", "$", 0, ACS, "ACS B25077", "Median value of owner-occupied homes, as estimated by their owners.", {}),
    ("median_gross_rent", "Prices and incomes", "Median gross rent", "$", 0, ACS, "ACS B25064", "Median monthly gross rent, including utilities.", {}),
    ("median_hh_income", "Prices and incomes", "Median household income", "$", 0, ACS, "ACS B19013", "Median household income in the past 12 months, in that survey period's dollars (not adjusted for inflation).", {}),
    ("per_capita_income", "Prices and incomes", "Per capita income", "$", 0, ACS, "ACS B19301", "Income per person in the past 12 months, not adjusted for inflation.", {}),
    ("median_owner_income", "Prices and incomes", "Median income of owner households", "$", 0, ACS, "ACS B25119", "Median household income of owner-occupied households.", {}),
    ("median_renter_income", "Prices and incomes", "Median income of renter households", "$", 0, ACS, "ACS B25119", "Median household income of renter-occupied households.", {}),
    ("median_owner_costs_mortgage", "Prices and incomes", "Median monthly owner costs, with a mortgage", "$", 0, ACS, "ACS B25088", "Median selected monthly owner costs for homes with a mortgage (mortgage, taxes, insurance, utilities).", {}),
    ("median_owner_costs_no_mortgage", "Prices and incomes", "Median monthly owner costs, no mortgage", "$", 0, ACS, "ACS B25088", "Median selected monthly owner costs for homes without a mortgage.", {}),
    ("median_rent_pct_income", "Cost burden", "Median gross rent as a share of household income", "%", 1, ACS, "ACS B25071", "Median of rent divided by income across renter households.", {}),
    ("renter_cost_burden_pct", "Cost burden", "Cost-burdened renters (30%+ of income on rent)", "%", 1, ACS, "ACS B25070", "Renter households paying 30% or more of income in gross rent, excluding those where the ratio cannot be computed.", {}),
    ("renter_severe_burden_pct", "Cost burden", "Severely cost-burdened renters (50%+ of income)", "%", 1, ACS, "ACS B25070", "Renter households paying half or more of income in gross rent.", {}),
    ("owner_cost_burden_pct", "Cost burden", "Cost-burdened owners with a mortgage (30%+ of income)", "%", 1, ACS, "ACS B25091", "Owner households with a mortgage paying 30% or more of income in selected monthly owner costs.", {}),
    ("max_affordable_loan", "Affordability", "Maximum affordable 30-year loan", "$", 0, "derived", "ACS B19013; study method", "The largest 30-year mortgage the median household can carry spending 30% of income on housing, 78% of that on principal and interest (the study's Table 6 method), at a fixed 5% rate so that years differ only through incomes.", {}),
    ("affordability_ratio", "Affordability", "Home ownership affordability ratio", "×", 2, "derived", "ACS B25077, B19013; study method", "Median home value divided by the largest 30-year loan the median household can carry (study method, fixed 5% rate). Above 1.0, the typical home is out of reach for the typical household.", {}),
    ("fema_ia_households", "Disaster recovery", "Households approved for FEMA housing assistance", "", 0, "fema", "OpenFEMA Housing Assistance", "Owner and renter households approved for FEMA Individual Assistance after a disaster declared that year, by municipality. Years with no declaration have no value.", {}),
    ("fema_ia_amount", "Disaster recovery", "FEMA Individual Assistance approved", "$", 0, "fema", "OpenFEMA Housing Assistance", "Dollars approved for owners and renters under FEMA Individual Assistance for disasters declared that year.", {}),
]

SOURCES = {
    "pep": {"name": "US Census Bureau — Population Estimates, municipios of Puerto Rico (Vintage 2020 for 2010-2019, Vintage 2025 for 2020-2025)", "url": "https://www.census.gov/programs-surveys/popest.html", "license": "US Government work; cite the Census Bureau as the source"},
    "census": {"name": "US Census Bureau — 2010 and 2020 Census, PL 94-171 Redistricting Data (table H1 housing occupancy)", "url": "https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html", "license": "US Government work; cite the Census Bureau as the source"},
    "acs": {"name": "US Census Bureau — American Community Survey 5-year estimates, 2006-2010 through 2020-2024 (summary files)", "url": "https://www2.census.gov/programs-surveys/acs/summary_file/", "license": "US Government work; cite the Census Bureau as the source"},
    "fema": {"name": "FEMA — OpenFEMA Housing Assistance Data (Owners and Renters)", "url": "https://www.fema.gov/about/openfema/data-sets", "license": "US Government work; OpenFEMA terms apply"},
    "derived": {"name": "FPR calculation on ACS 5-year estimates (State of Housing 2023, Table 6 method)", "url": "https://foundationforpuertorico.org/wp-content/uploads/2023/05/state_of_housing.pdf", "license": "Method © Foundation for Puerto Rico 2023; inputs are US Census Bureau ACS estimates"},
}


def build(refresh=False):
    names, geoids = municipalities()
    ids = geoids + ["72"]
    idx = {g: i for i, g in enumerate(ids)}
    log("Housing time series")
    pop, basis, age = population(names, geoids, refresh)
    cens = census_housing(refresh)
    fm = fema(names, geoids, refresh)
    values, moes, notes = {}, {}, {}

    def setv(key, year, gid, v, m=None):
        if gid not in idx or v is None:
            return
        a = values.setdefault(key, {}).setdefault(year, [None] * len(ids))
        a[idx[gid]] = v
        if m is not None:
            moes.setdefault(key, {}).setdefault(year, [None] * len(ids))[idx[gid]] = m

    for y, d in pop.items():
        for g, v in d.items():
            setv("population", y, g, v)
            if y > 2010 and 2010 in pop and pop[2010].get(g):
                setv("pop_change_since_2010_pct", y, g, round((v - pop[2010][g]) / pop[2010][g] * 100, 2))
            if y > 2020 and pop[2020].get(g):
                setv("pop_change_since_2020_pct", y, g, round((v - pop[2020][g]) / pop[2020][g] * 100, 2))
    for y, d in age.items():
        for g, v in d.items():
            setv("age65_pct", y, g, v)
    for y, d in cens.items():
        for g, (units, occ, vac) in d.items():
            setv("census_housing_units", y, g, units); setv("census_vacant_units", y, g, vac)
            setv("census_vacancy_pct", y, g, round(vac / units * 100, 2) if units else None)
            if pop.get(y, {}).get(g) and units:
                setv("residents_per_unit", y, g, round(pop[y][g] / units, 2))
    tables = {"grapi": {}, "smocapi": {}, "t7_owner_age": {}, "t6_income_by_age": {}}
    for y in ACS_YEARS:
        raw = acs_vintage(y, refresh)
        for gid, rec in raw.items():
            for k, (v, m) in derive(rec, y).items():
                setv(k, y, gid, v, m)
            if gid == "72":
                for tk, tv in island_tables(rec).items():
                    tables[tk][str(y)] = tv
    for n, byyear in fm.items():
        gid = next((g for nm, g in zip(names, geoids) if norm(nm) == n), None)
        for y, rec in byyear.items():
            setv("fema_ia_households", int(y), gid, rec["households"]); setv("fema_ia_amount", int(y), gid, round(rec["amount"]))
            notes.setdefault("fema", {}).setdefault(y, {}).update(rec["disasters"])
    # Puerto Rico totals for FEMA are the sums
    for key in ("fema_ia_households", "fema_ia_amount"):
        for y, arr in values.get(key, {}).items():
            arr[-1] = round(sum(v or 0 for v in arr[:-1]))
    # Puerto Rico's own medians are the Census Bureau's island-level estimates (set above from the '72' row), counts are summed there too
    catalog = []
    for key, group, label, unit, d, kind, ref, definition, extra in CATALOG:
        if key not in values:
            log(f"  (no data for {key})")
            continue
        yrs = sorted(values[key])
        entry = {"key": key, "group": group, "label": label, "unit": unit, "d": d, "kind": kind, "ref": ref, "definition": definition, **extra,
                 "years": {str(y): values[key][y] for y in yrs}}
        if key in moes:
            entry["moe"] = {str(y): moes[key][y] for y in sorted(moes[key])}
        if kind == "pop":
            entry["basis"] = {str(y): basis[y] for y in yrs if y in basis}
        catalog.append(entry)
    doc = {"built": str(__import__("datetime").date.today()), "latest": {"acs": max(ACS_YEARS), "pop": max(POP_YEARS)}, "years": sorted({y for v in values.values() for y in v}),
           "geo": {"ids": ids, "names": names + ["Puerto Rico"]}, "vars": catalog, "tables": tables, "sources": SOURCES,
           "notes": {"fema": notes.get("fema", {}),
                     "acs_windows": {str(y): f"{y - 4}-{y}" for y in ACS_YEARS},
                     "pop_break": "Estimates for 2011-2019 were made before the 2020 census and were not revised to match it; 2020 and later are on the 2020 census base."}}
    path = OUT / "housing_series.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  wrote housing_series.json: {len(catalog)} variables, {len(doc['years'])} years, {path.stat().st_size / 1e6:.2f} MB")
    return doc


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build("--refresh" in sys.argv)
