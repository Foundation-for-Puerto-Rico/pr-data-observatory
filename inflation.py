"""Inflation in Puerto Rico and the United States: the data of the Knowledge Area page inflation.html (HANDOFF decision 95, docs/inflation-plan-2026-11.md).

    python inflation.py             # downloads what is missing into cache/inflation/, writes site/data/inflation.json and prints the headline figures
    python inflation.py --refresh   # downloads every source again (a new month)
    python inflation.py --check     # rebuilds from the cache in memory and compares with the published file (no write, no download)

Sources (none needs a key):
  dtrh_xls   Puerto Rico Department of Labor and Human Resources (DTRH), "Serie Histórica Índice de Precios al Consumidor": the official consumer price index
             of Puerto Rico, all items and the 8 major groups, monthly from January 2007 (base December 2006 = 100, 2010 revision).
  dtrh_csv   DTRH on indicadores.pr (CKAN): the same index concatenated back to 1984 (read for 1999-2006), and the 2000-01 basket weights of the groups.
  bls        US Bureau of Labor Statistics, public API v1: CPI-U (US city average), CPI-W and the 8 major groups, not seasonally adjusted.
  cleveland  Federal Reserve Bank of Cleveland, inflation expectations model: expected US CPI inflation over 1 to 30 years, every month since 1982.
  spf        Federal Reserve Bank of Philadelphia, Survey of Professional Forecasters: median 1-year and 10-year CPI forecasts (a cross-check on the page).
  acs        US Census Bureau, American Community Survey 1-year: median household income (B19013), Puerto Rico and the US, 2010 onward.

The projection (docs/inflation-plan-2026-11.md, section 4): the central path of both places is the Cleveland Fed's expected US inflation, turned into
one-year forward rates, because that method had the smallest errors for Puerto Rico in a backtest of five candidates over 44 forecast origins (each
quarter of 2011 to 2021), each candidate seeing only what was known at its origin. The bands are the method's own past errors at each horizon: against
Puerto Rico's actual inflation for the Puerto Rico band, and against US inflation for the US band (origins each quarter of 1999 to 2021) (80% and 95%, normal, from the root mean
square error). The file holds index values, rates and medians only: no personal data.
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import unicodedata
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import requests

import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "inflation"
OUT = ROOT / "site" / "data" / "inflation.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; pr-digital-twin research dashboard; +https://github.com/Foundation-for-Puerto-Rico/pr-digital-twin)"}
UA_CENSUS = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}   # the agent housing_series.py uses on www2.census.gov

URL = {
    "dtrh_xls": "https://www.mercadolaboral.pr.gov/lmi/Excel/IPC/Serie%20Historica%20a%20Publicar.xls",
    "dtrh_page": "https://www.mercadolaboral.pr.gov/Tablas_Estadisticas/Otras_Tablas/T_Indice_Precio.aspx",
    "ckan": "https://indicadores.pr/api/3/action/package_show?id=indice-de-precios-al-consumidor",
    "ckan_page": "https://indicadores.pr/dataset/indice-de-precios-al-consumidor",
    "bls": "https://api.bls.gov/publicAPI/v1/timeseries/data/",
    "cleveland": "https://www.clevelandfed.org/-/media/files/webcharts/inflationexpectations/inflation-expectations.xlsx?sc_lang=en",
    "cleveland_page": "https://www.clevelandfed.org/indicators-and-data/inflation-expectations",
    "spf": "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/historical-data/Inflation.xlsx?sc_lang=en",
    "spf_page": "https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/inflation-forecasts",
    "acs": "https://www2.census.gov/programs-surveys/acs/summary_file/",
}

# The 8 major groups: key, DTRH name in the workbook, CSV column of DTRH, basket code (2000-01 weights), BLS series of the US counterpart
GROUPS = [
    ("food", "Alimentos y Bebidas", "F", "CUUR0000SAF"),
    ("housing", "Alojamiento", "H", "CUUR0000SAH"),
    ("apparel", "Ropa", "A", "CUUR0000SAA"),
    ("transport", "Transportación", "T", "CUUR0000SAT"),
    ("medical", "Cuidado Médico", "M", "CUUR0000SAM"),
    ("recreation", "Entretenimiento", "R", "CUUR0000SAR"),
    ("educom", "Educación y Comunicación", "E", "CUUR0000SAE"),
    ("other", "Otros Artículos y Servicios", "G", "CUUR0000SAG"),
]
BLS_SERIES = ["CUUR0000SA0", "CWUR0000SA0"] + [g[3] for g in GROUPS]
MES = {m: i + 1 for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
START = (2000, 1)            # the page's history starts here
EST_START = (2008, 1)        # the ARDL is estimated from here (the 2010 revision covers 2007 on; one year of lags)
ORIGINS = [(y, m) for y in range(2011, 2022) for m in (1, 4, 7, 10)]   # backtest origins (44)
H_YEARS = [1, 2, 3, 4, 5]
END_YEAR_OFFSET = 5          # the projection runs to December of (latest year + 5)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fold(s):
    return unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().strip().lower()


# ── months ───────────────────────────────────────────────────────────────────
def add(k, n):
    t = k[0] * 12 + (k[1] - 1) + n
    return (t // 12, t % 12 + 1)


def idx(k):
    return k[0] * 12 + k[1] - 1


def mkey(k):
    return f"{k[0]}-{k[1]:02d}"


def months(a, b):
    k = a
    while idx(k) <= idx(b):
        yield k
        k = add(k, 1)


# ── downloads ────────────────────────────────────────────────────────────────
def fetch(url, name, refresh=False, headers=UA, post=None, check=None):
    p = CACHE / name
    if p.exists() and not refresh:
        return p.read_bytes()
    if OFFLINE:
        raise SystemExit(f"inflation: {name} is not in cache/inflation (run python inflation.py first)")
    log(f"  downloading {name}")
    r = requests.post(url, json=post, headers=headers, timeout=180) if post is not None else requests.get(url, headers=headers, timeout=180)
    r.raise_for_status()
    if b"Request Rejected" in r.content[:400]:
        raise SystemExit(f"inflation: {url} rejected the request")
    if check and not check(r.content):
        raise SystemExit(f"inflation: {url} did not return the expected file")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return r.content


OFFLINE = False


# ── Puerto Rico: DTRH ────────────────────────────────────────────────────────
def dtrh_workbook(refresh):
    """{group key or 'all': {(y, m): index}} from the DTRH workbook, every sheet 'enero a diciembre YYYY' (the month columns are found by name: the 2010
    sheet has an extra blank column and every sheet starts with the base month, December 2006 = 100)."""
    import xlrd
    data = fetch(URL["dtrh_xls"], "dtrh_serie_historica.xls", refresh, check=lambda b: b[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    book = xlrd.open_workbook(file_contents=data)
    names = {fold(n): k for k, n, _, _ in GROUPS}
    names["todos los grupos"] = "all"
    out = {k: {} for k in names.values()}
    title = None
    for s in book.sheets():
        m = re.match(r"enero a diciembre (\d{4})", s.name.strip())
        if not m:
            continue
        y = int(m.group(1))
        hdr = next(r for r in range(s.nrows) if "enero" in [fold(s.cell_value(r, c)) for c in range(s.ncols)])
        head = [fold(s.cell_value(hdr, c)) for c in range(s.ncols)]
        cols = {}
        for c in range(head.index("enero"), s.ncols):
            if head[c] in MES and MES[head[c]] not in cols:
                cols[MES[head[c]]] = c
            if head[c].startswith("promedio"):
                break
        if len(cols) != 12:
            raise SystemExit(f"inflation: DTRH sheet {s.name!r} has {len(cols)} month columns")
        seen = set()
        for r in range(hdr + 1, s.nrows):
            key = names.get(fold(s.cell_value(r, 0)))
            if not key or key in seen:
                continue
            seen.add(key)   # the first block of the sheet is the index; the second block (percent changes) repeats the names
            for mo, c in cols.items():
                v = s.cell_value(r, c)
                if isinstance(v, float) and v > 0:
                    out[key][(y, mo)] = v
        if len(seen) != 9:
            raise SystemExit(f"inflation: DTRH sheet {s.name!r} has {len(seen)} of the 9 rows")
        if title is None:
            title = str(s.cell_value(2, 0)).strip()
    return out, title


def dtrh_ckan(refresh):
    """The CSV of the index (all items, 1984 on) and the 2000-01 basket weights of the 8 groups, from the CKAN dataset on indicadores.pr."""
    meta = json.loads(fetch(URL["ckan"], "dtrh_ckan.json", refresh))
    res = meta["result"]["resources"]
    ipc = next(r for r in res if fold(r["name"]).startswith("indice de precios al consumidor ipc"))
    basket = next(r for r in res if fold(r["name"]).startswith("canasta de bienes y servicios"))
    text = fetch(ipc["url"], "dtrh_ipc.csv", refresh).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    head = [fold(h) for h in rows[0]]
    col = head.index("todos los articulos y servicios")
    allitems = {}
    for r in rows[1:]:
        m = re.match(r"\s*([a-z]+)-(\d\d)\s*$", fold(r[0]))
        if not m or m.group(1) not in MES or len(r) <= col or not r[col].strip():
            continue
        y = int(m.group(2))
        y += 1900 if y > 50 else 2000
        allitems[(y, MES[m.group(1)])] = float(r[col])
    wtext = fetch(basket["url"], "dtrh_basket.csv", refresh).decode("latin-1")
    weights = {}
    codes = {g[2]: g[0] for g in GROUPS}
    for r in csv.reader(io.StringIO(wtext)):
        if r and r[0].strip() in codes and len(r) > 3:
            weights[codes[r[0].strip()]] = float(r[3])
    if set(weights) != set(codes.values()):
        raise SystemExit(f"inflation: the basket file has weights for {sorted(weights)}")
    return allitems, weights, {"csv": ipc["url"], "csv_modified": ipc.get("last_modified", "")[:10], "license": meta["result"].get("license_title", "")}


# ── United States: BLS ───────────────────────────────────────────────────────
def bls(refresh, last_year):
    """{series: {(y, m): value}} from 1999 to last_year, in windows of up to 10 years (the API's v1 limit). Missing months (BLS has no October 2025:
    the 2025 lapse in appropriations) are left out; `gaps` lists them."""
    out, gaps = {s: {} for s in BLS_SERIES}, []
    a = 1999
    while a <= last_year:
        b = min(a + 9, last_year)
        name = f"bls_{a}_{b}.json"
        data = json.loads(fetch(URL["bls"], name, refresh, post={"seriesid": BLS_SERIES, "startyear": str(a), "endyear": str(b)},
                                check=lambda c: b"REQUEST_SUCCEEDED" in c[:200]))
        for s in data["Results"]["series"]:
            if s["seriesID"] not in out:
                continue
            for x in s["data"]:
                p = x["period"]
                if not p.startswith("M") or p == "M13":
                    continue
                k = (int(x["year"]), int(p[1:]))
                try:
                    out[s["seriesID"]][k] = float(x["value"])
                except ValueError:
                    if s["seriesID"] == "CUUR0000SA0":
                        gaps.append(mkey(k))
        a = b + 1
    return out, sorted(set(gaps))


# ── Expectations ─────────────────────────────────────────────────────────────
def excel_month(serial):
    d = date(1899, 12, 30) + timedelta(days=int(float(serial)))
    return (d.year, d.month)


def cleveland(refresh):
    """{(y, m): [expected annual CPI inflation over 1..30 years, %]}."""
    data = fetch(URL["cleveland"], "cleveland_expectations.xlsx", refresh, check=lambda b: b[:2] == b"PK")
    out = {}
    for i, r in enumerate(xlsx_read.rows(data, "Expected Inflation")):
        if i == 0:
            if "expected inflation" not in fold(r.get(1, "")):
                raise SystemExit("inflation: the Cleveland Fed file changed its layout")
            continue
        try:
            out[excel_month(r[0])] = [round(float(r[j]) * 100, 4) for j in range(1, 31)]
        except (KeyError, TypeError, ValueError):
            continue
    return out


def spf(refresh):
    """The latest survey's median CPI forecasts: {'quarter': 'YYYY Qn', 'cpi1': %, 'cpi10': %}."""
    data = fetch(URL["spf"], "spf_inflation.xlsx", refresh, check=lambda b: b[:2] == b"PK")
    rows = list(xlsx_read.rows(data))
    head = [fold(rows[0].get(i, "")) for i in range(len(rows[0]))]
    c1, c10 = head.index("infcpi1yr"), head.index("infcpi10yr")
    last = None
    for r in rows[1:]:
        try:
            last = {"quarter": f"{int(float(r[0]))} Q{int(float(r[1]))}", "cpi1": round(float(r[c1]), 2), "cpi10": round(float(r[c10]), 2)}
        except (KeyError, TypeError, ValueError):
            continue
    return last


# ── Household income: ACS 1-year B19013 ──────────────────────────────────────
def acs_income(refresh):
    """{year: {'pr': [median, moe], 'us': [median, moe]}}: the per-sequence files 2010-2019 and the table-based files from 2021 (2020 had no standard
    1-year release)."""
    out = {}
    for y in range(2010, 2020):
        out[y] = {"pr": _acs_seq(y, "PuertoRico", "pr", r"04000US72\b", refresh), "us": _acs_seq(y, "UnitedStates", "us", r"01000US\b", refresh)}
    y = 2021
    while True:
        url = URL["acs"] + f"{y}/table-based-SF/data/1YRData/acsdt1y{y}-b19013.dat"
        name = f"acs/b19013_{y}.dat"
        if not (CACHE / name).exists():
            if OFFLINE:
                break
            if requests.head(url, headers=UA_CENSUS, timeout=60).status_code != 200:
                break
        rec = {}
        for line in fetch(url, name, False, headers=UA_CENSUS).decode("latin-1").splitlines():
            f = line.split("|")
            if f[0] in ("0100000US", "0400000US72"):
                rec["us" if f[0] == "0100000US" else "pr"] = [float(f[1]), float(f[2])]
        if len(rec) != 2:
            raise SystemExit(f"inflation: ACS {y} B19013 lacks Puerto Rico or the US")
        out[y] = rec
        y += 1
    return out


def _acs_seq(y, folder, ab, geo, refresh):
    base = URL["acs"] + f"{y}/"
    text = None
    for path in ("documentation/user_tools/ACS_1yr_Seq_Table_Number_Lookup.txt", "documentation/1_year/user_tools/Sequence_Number_and_Table_Number_Lookup.txt"):
        try:
            text = fetch(base + path, f"acs/lookup{y}.txt", refresh, headers=UA_CENSUS).decode("latin-1")
            break
        except requests.HTTPError:
            continue
    seq = start = None
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        st = row.get("Start Position") or row.get("position") or ""
        if row.get("Table ID") == "B19013" and st.isdigit():
            seq, start = int(row.get("Sequence Number") or row.get("seq")), int(st)
            break
    if seq is None:
        raise SystemExit(f"inflation: ACS {y}: B19013 not in the lookup file")
    d = base + f"data/1_year_seq_by_state/{folder}/"
    g = fetch(d + f"g{y}1{ab}.csv", f"acs/g{y}{ab}.csv", refresh, headers=UA_CENSUS).decode("latin-1")
    rec = next((row[4] for row in csv.reader(io.StringIO(g)) if re.search(geo, ",".join(row))), None)
    z = zipfile.ZipFile(io.BytesIO(fetch(d + f"{y}1{ab}{seq:04d}000.zip", f"acs/{y}{ab}{seq:04d}.zip", refresh, headers=UA_CENSUS)))
    names = {n.lower(): n for n in z.namelist()}
    vals = []
    for kind in "em":
        for row in csv.reader(io.TextIOWrapper(z.open(names[f"{kind}{y}1{ab}{seq:04d}000.txt"]), encoding="latin-1")):
            if row[5] == rec:
                vals.append(float(row[start - 1]))
                break
    if len(vals) != 2:
        raise SystemExit(f"inflation: ACS {y} {folder}: no B19013 row")
    return vals


# ── rates ────────────────────────────────────────────────────────────────────
def yoy(S, k):
    k0 = add(k, -12)
    return 100 * (S[k] / S[k0] - 1) if k in S and k0 in S else None


def dl(S, k):
    k0 = add(k, -1)
    return 100 * math.log(S[k] / S[k0]) if k in S and k0 in S else None


def year_avg(S, y):
    v = [S.get((y, m)) for m in range(1, 13)]
    return sum(v) / 12 if None not in v else None


def r1(x, d=1):
    return None if x is None else round(x, d)


# ── the forecast methods ─────────────────────────────────────────────────────
def forwards(E):
    """One-year forward expected inflation for years 1..len(E): E[k-1] is the expected annual average over k years (compounded)."""
    f = [E[0]]
    for k in range(2, len(E) + 1):
        f.append(100 * ((1 + E[k - 1] / 100) ** k / (1 + E[k - 2] / 100) ** (k - 1) - 1))
    return f


def seasonal(S, origin, years=10):
    """The index's own seasonal pattern: the mean log change of each calendar month over the `years` before `origin`, less the mean of all months
    (both indexes are not seasonally adjusted, so an even spread of a year's rate would make false base effects in the 12-month rate)."""
    by = {m: [] for m in range(1, 13)}
    for k in months(add(origin, -12 * years + 1), origin):
        v = dl(S, k)
        if v is not None:
            by[k[1]].append(v)
    if any(not v for v in by.values()):
        return {m: 0.0 for m in range(1, 13)}
    mean = float(np.mean([np.mean(v) for v in by.values()]))
    return {m: float(np.mean(v)) - mean for m, v in by.items()}


def project(S, origin, f, H):
    """The index path after `origin` at the forward rates `f` (% a year) with the index's seasonal pattern: {(y, m): index}."""
    seas = seasonal(S, origin)
    out, v = {}, S[origin]
    for h in range(1, H + 1):
        k = add(origin, h)
        v *= (1 + f[min((h - 1) // 12, len(f) - 1)] / 100) ** (1 / 12) * math.exp(seas[k[1]] / 100)
        out[k] = v
    return out


def avg_rate(S, k0, h):
    """Average annual inflation from month k0 to k0+h, %."""
    return 100 * ((S[add(k0, h)] / S[k0]) ** (12 / h) - 1)


def fit_ardl(P, U, origin, p=1, q=1):
    """OLS of Puerto Rico's monthly log change on its own lags, US changes (current and lagged) and month dummies, EST_START to origin."""
    X, Y = [], []
    for k in months(EST_START, origin):
        y = dl(P, k)
        ys = [dl(P, add(k, -i)) for i in range(1, p + 1)]
        xs = [dl(U, add(k, -j)) for j in range(q + 1)]
        if y is None or None in ys or None in xs:
            continue
        d = [0.0] * 11
        if k[1] > 1:
            d[k[1] - 2] = 1.0
        X.append([1.0] + d + ys + xs)
        Y.append(y)
    b, *_ = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)
    return b, len(Y)


def us_seasonal(U, origin):
    by = {m: [] for m in range(1, 13)}
    for k in months((2010, 1), origin):
        v = dl(U, k)
        if v is not None:
            by[k[1]].append(v)
    mean = float(np.mean([np.mean(v) for v in by.values()]))
    return {m: float(np.mean(v)) - mean for m, v in by.items()}


def ardl_path(P, U, origin, b, f, H, p=1, q=1):
    """Puerto Rico's index path from the ARDL, fed a US path at the forward rates `f` plus the US seasonal pattern."""
    seas = us_seasonal(U, origin)
    ly = {add(origin, -i): dl(P, add(origin, -i)) for i in range(p + 1)}
    lx = {add(origin, -j): dl(U, add(origin, -j)) for j in range(q + 1)}
    out, v = {}, P[origin]
    for h in range(1, H + 1):
        k = add(origin, h)
        lx[k] = 100 * math.log(1 + f[min((h - 1) // 12, len(f) - 1)] / 100) / 12 + seas[k[1]]
        d = [0.0] * 11
        if k[1] > 1:
            d[k[1] - 2] = 1.0
        y = float(np.dot(b, [1.0] + d + [ly[add(k, -i)] for i in range(1, p + 1)] + [lx[add(k, -j)] for j in range(q + 1)]))
        ly[k] = y
        v *= math.exp(y / 100)
        out[k] = v
    return out


def backtest(P, U, CL, last_pr):
    """Each candidate's errors (forecast minus actual average annual inflation over h months), over ORIGINS, h = 12..60 months."""
    names = ["us_expected", "ardl", "last12", "own_mean", "us_plus_gap"]
    err = {n: {h: [] for h in H_YEARS} for n in names}
    for o in ORIGINS:
        E = CL[o]
        f = forwards(E[:10])
        b, _ = fit_ardl(P, U, o)
        A = ardl_path(P, U, o, b, f, 60)
        A[o] = P[o]
        last12 = yoy(P, o)
        own = 100 * ((P[o] / P[(2007, 12)]) ** (12 / (idx(o) - idx((2007, 12)))) - 1)
        gap = 100 * ((P[o] / P[add(o, -120)]) ** 0.1 - 1) - 100 * ((U[o] / U[add(o, -120)]) ** 0.1 - 1)
        for hy in H_YEARS:
            h = 12 * hy
            if idx(add(o, h)) > idx(last_pr):
                continue
            act = avg_rate(P, o, h)
            fc = {"us_expected": E[hy - 1], "ardl": avg_rate(A, o, h), "last12": last12, "own_mean": own, "us_plus_gap": E[hy - 1] + gap}
            for n, v in fc.items():
                err[n][hy].append(v - act)
    rmse = {n: {str(h): r1(math.sqrt(np.mean(np.square(e))), 2) for h, e in d.items()} for n, d in err.items()}
    bias = {n: {str(h): r1(float(np.mean(e)), 2) for h, e in d.items()} for n, d in err.items()}
    count = {str(h): len(err["us_expected"][h]) for h in H_YEARS}
    return {"origins": [mkey(ORIGINS[0]), mkey(ORIGINS[-1])], "n_origins": len(ORIGINS), "count": count, "rmse": rmse, "bias": bias, "order": names}


def path_errors(S, CL, origins, last):
    """RMSE of the method's 12-month rate h months ahead (h = 1..72) and of the rate over the k-th year ahead (k = 1..6), from the given origins."""
    e_m = {h: [] for h in range(1, 73)}
    e_y = {k: [] for k in range(1, 7)}
    for o in origins:
        if o not in CL or o not in S:
            continue
        f = forwards(CL[o][:10])
        Q = dict(S)
        Q.update(project(S, o, f, 72))
        for h in range(1, 73):
            k = add(o, h)
            if idx(k) > idx(last) or k not in S or add(k, -12) not in S:
                continue
            e_m[h].append(100 * (Q[k] / Q[add(k, -12)] - 1) - yoy(S, k))
        for y in range(1, 7):
            if idx(add(o, 12 * y)) <= idx(last) and add(o, 12 * y) in S:
                e_y[y].append(f[y - 1] - 100 * (S[add(o, 12 * y)] / S[add(o, 12 * (y - 1))] - 1))
    rm = lambda e: math.sqrt(float(np.mean(np.square(e)))) if e else None
    sm = [rm(e_m[h]) for h in range(1, 73)]
    # carry the last horizon with enough origins forward (fewer than 8 origins is too few to read)
    for h in range(1, 73):
        if len(e_m[h]) < 8:
            sm[h - 1] = sm[h - 2]
    sy = []
    for y in range(1, 7):
        sy.append(rm(e_y[y]) if len(e_y[y]) >= 8 else sy[-1])
    return sm, sy, {"monthly_n": [len(e_m[h]) for h in (12, 24, 36, 48, 60)], "yearly_n": [len(e_y[y]) for y in range(1, 7)]}


def cola(W):
    """Social Security's cost-of-living adjustments from CPI-W: the July-September average over the same quarter of the last year with an adjustment,
    rounded to 0.1%, effective each December (paid from January). {effective year: %}."""
    q3 = {y: sum(W[(y, m)] for m in (7, 8, 9)) / 3 for y in range(1999, 2100) if all((y, m) in W for m in (7, 8, 9))}
    out, base = {}, q3[1999]
    for y in sorted(q3):
        if y == 1999:
            continue
        c = math.floor((q3[y] / base - 1) * 1000 + 0.5) / 10
        c = max(c, 0.0)
        out[y] = c
        if c > 0:
            base = q3[y]
    return out


# ── build ────────────────────────────────────────────────────────────────────
def build(refresh=False):
    W, wb_title = dtrh_workbook(refresh)
    csv_all, weights, ckan = dtrh_ckan(refresh)
    pr_all = W["all"]
    last_pr = max(pr_all)
    over = [k for k in pr_all if k in csv_all]
    disagree = [(mkey(k), csv_all[k], pr_all[k]) for k in over if abs(csv_all[k] - pr_all[k]) > 0.0015]
    if len(disagree) > 3:
        raise SystemExit(f"inflation: the DTRH workbook and CSV disagree in {len(disagree)} months: {disagree[:5]}")
    P = {k: v for k, v in csv_all.items() if (1999, 1) <= k <= (2006, 12)}
    P.update(pr_all)
    missing = [mkey(k) for k in months((1999, 1), last_pr) if k not in P]
    if missing:
        raise SystemExit(f"inflation: Puerto Rico months missing: {missing}")
    B, gaps = bls(refresh, date.today().year)
    U = dict(B["CUUR0000SA0"])
    Wc = B["CWUR0000SA0"]
    last_us = max(U)
    filled = []
    for k in months((1999, 1), last_us):
        if k not in U:
            U[k] = math.sqrt(U[add(k, -1)] * U[add(k, 1)])   # the model reads a missing month as the geometric mean of its neighbours
            filled.append(mkey(k))
    CL = cleveland(refresh)
    last_cl = max(CL)
    SP = spf(refresh)
    INC = acs_income(refresh)

    # history
    hist_months = list(months(START, last_us))
    gapset = set(gaps)
    us_yoy = [None if (mkey(k) in gapset or mkey(add(k, -12)) in gapset) else r1(yoy(U, k), 2) for k in hist_months]
    pr_yoy = [r1(yoy(P, k), 2) if k in P else None for k in hist_months]
    annual = []
    for y in range(START[0] + 1, last_us[0] + 1):
        pa, pb, ua, ub = year_avg(P, y), year_avg(P, y - 1), year_avg(U, y), year_avg(U, y - 1)
        if pa and pb and ua and ub:
            annual.append({"year": y, "pr": r1(100 * (pa / pb - 1), 2), "us": r1(100 * (ua / ub - 1), 2)})

    # projection: both from the latest Cleveland curve; each place from its own latest month
    E = CL[last_cl]
    f = forwards(E[:10])
    end = (last_pr[0] + END_YEAR_OFFSET, 12)
    Hp, Hu = idx(end) - idx(last_pr), idx(end) - idx(last_us)
    PP = dict(P)
    PP.update(project(P, last_pr, f, Hp))
    UP = dict(U)
    UP.update(project(U, last_us, f, Hu))
    sm_pr, sy_pr, n_pr = path_errors(P, CL, ORIGINS, last_pr)
    us_origins = [(y, m) for y in range(2000, 2022) for m in (1, 4, 7, 10)]   # BLS is read from 1999; the seasonal pattern needs a year
    sm_us, sy_us, n_us = path_errors(U, CL, us_origins, last_us)
    Z80, Z95 = 1.2816, 1.96

    def path(S, Q, last, sm):
        rows = []
        for k in months(add(last, 1), end):
            h = idx(k) - idx(last)
            c = 100 * (Q[k] / Q[add(k, -12)] - 1)
            s = sm[min(h, 72) - 1]
            rows.append([mkey(k), r1(c, 2), r1(c - Z80 * s, 2), r1(c + Z80 * s, 2), r1(c - Z95 * s, 2), r1(c + Z95 * s, 2)])
        return rows

    def years(S, Q, last, sy, sm):
        rows = []
        for y in range(last[0], end[0] + 1):
            c = 100 * (year_avg(Q, y) / year_avg(Q, y - 1) - 1)
            k = max(0, y - last[0])   # 0: the current year, part observed
            if k == 0:
                # the current year's average: only its remaining months are projected; their errors are added as if fully correlated (cautious)
                s = sum(sm[h - 1] for h in range(1, 13 - last[1])) / 12
            else:
                s = sy[min(k, 6) - 1]
            rows.append({"year": y, "c": r1(c, 2), "lo80": r1(c - Z80 * s, 2), "hi80": r1(c + Z80 * s, 2), "lo95": r1(c - Z95 * s, 2), "hi95": r1(c + Z95 * s, 2), "observed_months": min(12, last[1]) if k == 0 else 0})
        return rows

    bt = backtest(P, U, CL, last_pr)
    b, n_ardl = fit_ardl(P, U, last_pr)
    a_sum, b_sum = float(b[12]), float(b[13] + b[14])
    ardl = {"n": n_ardl, "pass_through": r1(b_sum / (1 - a_sum), 2), "const_pp_year": r1((12 * float(b[0]) + float(np.sum(b[1:12]))) / (1 - a_sum), 2), "own_lag": r1(a_sum, 3), "us_now": r1(float(b[13]), 3), "us_lag": r1(float(b[14]), 3)}

    # groups
    groups = []
    k20 = (2020, 1)
    for key, name, code, sid in GROUPS:
        g, ug = W[key], B[sid]
        lu = max(ug)
        groups.append({"key": key, "dtrh": name, "bls": sid, "weight": weights[key],
                       "pr_yoy": r1(yoy(g, last_pr), 1), "us_yoy": r1(yoy(ug, last_us), 1) if mkey(add(last_us, -12)) not in gapset else r1(yoy(ug, add(last_us, -1)), 1),
                       "us_yoy_month": mkey(last_us) if mkey(add(last_us, -12)) not in gapset else mkey(add(last_us, -1)),
                       "pr_since2020": r1(100 * (g[last_pr] / g[k20] - 1), 1), "us_since2020": r1(100 * (ug[lu] / ug[k20] - 1), 1),
                       "pr_index": [r1(g.get(k), 3) for k in months((2007, 1), last_pr)]})

    # people and families
    def pp(S, a, b):
        return r1(100 * S[a] / S[b], 1)   # cost in month a of what $100 bought in month b
    power = {"from": {}, "pr": {}, "us": {}}
    for lab, k in (("2000", (2000, 1)), ("2007", (2006, 12)), ("2020", (2020, 1))):
        power["from"][lab] = mkey(k)
        power["pr"][lab] = {"cost": pp(P, last_pr, k), "worth": r1(100 * P[k] / P[last_pr], 1)}
        power["us"][lab] = {"cost": pp(U, last_us, k), "worth": r1(100 * U[k] / U[last_us], 1)}
    power["pr"]["proj"] = {"cost": r1(100 * PP[end] / P[last_pr], 1), "worth": r1(100 * P[last_pr] / PP[end], 1)}
    power["us"]["proj"] = {"cost": r1(100 * UP[end] / U[last_us], 1), "worth": r1(100 * U[last_us] / UP[end], 1)}
    # Puerto Rico's price level at the end of the projection, with the 80% band from the method's error on 5-year average inflation (backtest)
    yrs = Hp / 12
    r_c = (PP[end] / P[last_pr]) ** (1 / yrs) - 1
    s5 = bt["rmse"]["us_expected"]["5"] / 100
    power["pr"]["proj"].update({"months": Hp, "lo80": r1(100 * (1 + r_c - Z80 * s5) ** yrs, 1), "hi80": r1(100 * (1 + r_c + Z80 * s5) ** yrs, 1)})

    full = [y for y in range(2000, last_pr[0] + 1) if year_avg(P, y) and year_avg(U, y)]
    ref_year = max(full)
    income = []
    for y in sorted(INC):
        pr, us = INC[y]["pr"], INC[y]["us"]
        income.append({"year": y, "pr": pr[0], "pr_moe": pr[1], "us": us[0], "us_moe": us[1],
                       "pr_real": round(pr[0] * year_avg(P, ref_year) / year_avg(P, y)), "us_real": round(us[0] * year_avg(U, ref_year) / year_avg(U, y))})
    co = cola(Wc)
    # a benefit of $1,000 in January 2007: with each December's adjustment, against prices in Puerto Rico and in the US
    ben, k = 1000.0, (2007, 1)
    for y in range(2007, last_pr[0] + 1):
        if y in co and (y, 12) <= last_pr:
            ben *= 1 + co[y] / 100
    real_pr = ben * P[(2007, 1)] / P[last_pr]
    real_us = ben * U[(2007, 1)] / U[last_pr]

    D = {
        "built": date.today().isoformat(),
        "latest": {"pr": mkey(last_pr), "us": mkey(last_us), "cleveland": mkey(last_cl), "spf": SP["quarter"] if SP else None, "acs": max(INC)},
        "headline": {"pr_yoy": r1(yoy(P, last_pr), 1), "us_yoy": r1(yoy(U, last_pr), 1) if mkey(add(last_pr, -12)) not in gapset else None,
                     "us_yoy_latest": us_yoy[-1] if us_yoy[-1] is not None else us_yoy[-2], "us_yoy_latest_month": mkey(last_us) if us_yoy[-1] is not None else mkey(add(last_us, -1)),
                     "pr_index": r1(P[last_pr], 3), "pr_index_year_ago": r1(P[add(last_pr, -12)], 3), "us_index": r1(U[last_us], 3),
                     "cum2000": {"pr": r1(100 * (P[last_pr] / P[(2000, 1)] - 1), 1), "us": r1(100 * (U[last_pr] / U[(2000, 1)] - 1), 1)},
                     "cum2020": {"pr": r1(100 * (P[last_pr] / P[(2020, 1)] - 1), 1), "us": r1(100 * (U[last_pr] / U[(2020, 1)] - 1), 1)},
                     "cum2007": {"pr": r1(100 * (P[last_pr] / P[(2006, 12)] - 1), 1), "us": r1(100 * (U[last_pr] / U[(2006, 12)] - 1), 1)},
                     "avg2007": {"pr": r1(100 * ((P[last_pr] / P[(2006, 12)]) ** (12 / (idx(last_pr) - idx((2006, 12)))) - 1), 2),
                                 "us": r1(100 * ((U[last_pr] / U[(2006, 12)]) ** (12 / (idx(last_pr) - idx((2006, 12)))) - 1), 2)},
                     "proj_avg5": r1(100 * ((1 + E[4] / 100)) - 100, 2), "pr_months_above": sum(1 for a, c in zip(pr_yoy[-12:], us_yoy[-12:]) if a is not None and c is not None and a > c)},
        "monthly": {"start": mkey(START), "pr_yoy": pr_yoy, "us_yoy": us_yoy, "pr_index": [r1(P.get(k), 3) for k in hist_months], "us_index": [r1(U[k], 3) for k in hist_months]},
        "annual": annual,
        "projection": {"origin": {"pr": mkey(last_pr), "us": mkey(last_us), "cleveland": mkey(last_cl)}, "end": mkey(end),
                       "expected": [r1(x, 2) for x in E[:10]], "forwards": [r1(x, 2) for x in f[:6]], "spf": SP,
                       "pr_path": path(P, PP, last_pr, sm_pr), "us_path": path(U, UP, last_us, sm_us),
                       "pr_years": years(P, PP, last_pr, sy_pr, sm_pr), "us_years": years(U, UP, last_us, sy_us, sm_us),
                       "rmse_year": {"pr": [r1(x, 2) for x in sy_pr], "us": [r1(x, 2) for x in sy_us]}, "counts": {"pr": n_pr, "us": n_us}},
        "backtest": bt,
        "ardl": ardl,
        "groups": groups,
        "power": power,
        "income": {"ref_year": ref_year, "rows": income},
        "cola": {"rows": [{"year": y, "pct": co[y]} for y in sorted(co) if y >= 2007], "benefit": {"start": 1000, "start_month": "2007-01", "now": round(ben, 2),
                 "real_pr": round(real_pr, 2), "real_us": round(real_us, 2), "month": mkey(last_pr)}},
        "checks": {"dtrh_overlap_months": len(over), "dtrh_disagree": [[a, b2, c] for a, b2, c in disagree], "us_missing": gaps, "us_filled_for_model": filled,
                   "dtrh_csv_last": mkey(max(csv_all)), "dtrh_workbook_title": wb_title},
        "sources": {
            "dtrh": {"name": "Departamento del Trabajo y Recursos Humanos de Puerto Rico, Negociado de Estadísticas del Trabajo: Índice de Precios al Consumidor (Serie Histórica)", "url": URL["dtrh_page"], "file": URL["dtrh_xls"], "license": "Government of Puerto Rico public information"},
            "dtrh_csv": {"name": "Departamento del Trabajo y Recursos Humanos, on indicadores.pr: Índice de Precios al Consumidor (IPC) and the 2000-01 basket", "url": URL["ckan_page"], "file": ckan["csv"], "license": ckan["license"] or "Creative Commons Attribution"},
            "bls": {"name": "US Bureau of Labor Statistics: Consumer Price Index (CPI-U and CPI-W, US city average), public data API", "url": "https://www.bls.gov/cpi/", "license": "US Government work (public domain)"},
            "cleveland": {"name": "Federal Reserve Bank of Cleveland: inflation expectations (doi 10.26509/frbc-infexp)", "url": URL["cleveland_page"], "license": "Free to use with citation"},
            "spf": {"name": "Federal Reserve Bank of Philadelphia: Survey of Professional Forecasters, inflation forecasts", "url": URL["spf_page"], "license": "Free to use with citation"},
            "acs": {"name": "US Census Bureau: American Community Survey 1-year estimates, table B19013 (median household income)", "url": "https://www.census.gov/programs-surveys/acs", "license": "US Government work; cite the Census Bureau as the source"},
        },
    }
    return D


def summary(D):
    h, p = D["headline"], D["projection"]
    print(f"Puerto Rico {D['latest']['pr']}: {h['pr_yoy']}% over 12 months; US {h['us_yoy_latest_month']}: {h['us_yoy_latest']}%")
    print(f"since Jan 2000: PR +{h['cum2000']['pr']}%, US +{h['cum2000']['us']}%; since Jan 2020: PR +{h['cum2020']['pr']}%, US +{h['cum2020']['us']}%")
    print("projected annual averages (PR central [80%]):", ", ".join(f"{r['year']} {r['c']} [{r['lo80']}, {r['hi80']}]" for r in p["pr_years"]))
    print("backtest RMSE:", json.dumps(D["backtest"]["rmse"]))
    print("ARDL:", D["ardl"])


def main():
    global OFFLINE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        OFFLINE = True
        D = build(False)
        old = json.loads(OUT.read_text(encoding="utf-8"))
        D["built"] = old.get("built")
        if D != old:
            diff = [k for k in D if D[k] != old.get(k)]
            raise SystemExit(f"inflation: site/data/inflation.json is out of date ({', '.join(diff)}); run python inflation.py")
        print("inflation: site/data/inflation.json is up to date")
        return
    summary(write(a.refresh))


def write(refresh=False):
    """Builds and writes site/data/inflation.json (build.py calls it); returns the data."""
    D = build(refresh)
    OUT.write_text(json.dumps(D, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
    return D


if __name__ == "__main__":
    main()
