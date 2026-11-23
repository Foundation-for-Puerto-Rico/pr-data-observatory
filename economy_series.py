"""Economy time series for the PR Data Observatory: jobs, wages, industries, unemployment, income, commuting and public money,
for the 78 municipalities and Puerto Rico, every year the public sources allow.

    python economy_series.py             # build site/data/economy_series.json (downloads only what is missing)
    python economy_series.py --refresh   # re-download everything
    python economy_series.py --police    # update only the Police crime series in the published file (add --refresh after a new December report)
    python economy_series.py --fema      # update only the FEMA series (Public Assistance, Hazard Mitigation) in the published file (add --refresh for a new download)
    python economy_series.py --fac       # update only the Federal Audit Clearinghouse series in the published file (add --refresh to look for new audits)
    python economy_series.py --nmtc      # update only the New Markets Tax Credit series in the published file (add --refresh to look for a newer release)

Sources, none needing a key except the Federal Audit Clearinghouse (a free api.data.gov key in FAC_API_KEY):
  QCEW        BLS Quarterly Census of Employment and Wages (open-data API): establishments, jobs, wages by municipality, sector and
              ownership, 2014 onward. Counts jobs where the work is done, covers about 95% of wage-and-salary jobs, and hides cells
              that would identify an employer (small municipalities miss many sectors).
  LAUS        BLS Local Area Unemployment Statistics (public API): unemployment rate and labor force, annual averages (model-based).
  ACS         Census Bureau American Community Survey 5-year, every window 2006-2010 to 2020-2024: income distribution, inequality
              (Gini), class of worker, commuting, vehicles, internet.
  USAspending Federal awards by place of performance, by federal fiscal year and type (contracts, grants, direct payments, loans, other).
  OpenFEMA    Public Assistance obligations by municipality and the year of the disaster declaration, in total and by damage category; Hazard Mitigation
              Assistance subapplications (federal share approved, obligated and awaiting decision) by benefiting municipality and fiscal year.
  FAC         Federal Audit Clearinghouse (GSA): the single audit of each municipio government, federal money it spent in its fiscal year (July to June),
              in total, direct or through a pass-through entity, and by federal agency.
  NMTC        CDFI Fund (US Treasury), New Markets Tax Credit public data release: qualified low-income community investments (QLICIs) by the census tract
              of the project and the year the investment was made.
  CPI-U       BLS consumer price index (US city average): puts dollars of different years on one footing. It is the US index, not a Puerto Rico index.
  Police      Type I crimes by municipality, from the December report of each year (2017 onward) that the Instituto de Estadísticas publishes.
              Reports to 2022 are .xls (needs xlrd); later ones are PDFs read with pdftotext (Poppler).
Housing-page series (population, income, poverty, employment, FEMA household assistance) and the tourism-place counts are read
by the page directly from housing_series.json and municipalities.json, so nothing is duplicated here.

Output: {"built", "years", "geo": {"ids", "names"}, "vars": [...], "deflator": {"cpi": {year: index}}, "sources": {...}, "extras": {...}}
with arrays indexed like geo.names (the last entry is Puerto Rico).
"""

import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date
from math import sqrt
from pathlib import Path

import requests

import housing_series as hs
import spending
import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "economy"
OUT = hs.OUT
UA = {"User-Agent": "Mozilla/5.0 (compatible; pr-digital-twin research dashboard; +https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory)"}
log = hs.log

SECTORS = [("11", "Agriculture, forestry, fishing and hunting"), ("21", "Mining and quarrying"), ("22", "Utilities"), ("23", "Construction"), ("31-33", "Manufacturing"),
           ("42", "Wholesale trade"), ("44-45", "Retail trade"), ("48-49", "Transportation and warehousing"), ("51", "Information"), ("52", "Finance and insurance"),
           ("53", "Real estate and rental and leasing"), ("54", "Professional, scientific and technical services"), ("55", "Management of companies"),
           ("56", "Administrative, support and waste services"), ("61", "Educational services"), ("62", "Health care and social assistance"),
           ("71", "Arts, entertainment and recreation"), ("72", "Accommodation and food services"), ("81", "Other services (except public administration)")]
SECTOR_CODES = {c for c, _ in SECTORS}
slug = lambda c: "naics_" + c.replace("-", "_")

ECON_TABLES = {"B19083": 1, "B19001": 17, "B08301": 21, "B08303": 13, "B25044": 15, "B28002": 13, "B24080": 21}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── QCEW ─────────────────────────────────────────────────────────────────────

def qcew_years():
    y = 2024
    while requests.head(f"https://data.bls.gov/cew/data/api/{y + 1}/a/area/72127.csv", headers=UA, timeout=60).status_code == 200:
        y += 1
    return list(range(2014, y + 1))


def qcew_area(sess, area, year, refresh=False):
    """The rows this page uses for one area and year: totals by ownership, the 19 private NAICS sectors and 721 / 722."""
    p = CACHE / "qcew" / f"{area}_{year}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    for attempt in range(4):
        r = sess.get(f"https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv", timeout=90)
        if r.status_code == 200:
            break
        if r.status_code == 404:
            return {}
        time.sleep(2 * (attempt + 1))
    else:
        raise RuntimeError(f"QCEW {area} {year}: HTTP {r.status_code}")
    out = {}
    for x in csv.DictReader(io.StringIO(r.text)):
        own, ind = x["own_code"], x["industry_code"]
        if ind == "10" and own in ("0", "1", "2", "3", "5"):
            key = f"o{own}"
        elif own == "5" and ind in SECTOR_CODES | {"721", "722"}:
            key = ind
        else:
            continue
        hidden = x["disclosure_code"].strip() == "N"
        out[key] = [None if hidden else num(x["annual_avg_estabs"]), None if hidden else num(x["annual_avg_emplvl"]), None if hidden else num(x["total_annual_wages"]), None if hidden else num(x["avg_annual_pay"])]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    time.sleep(0.15)
    return out


# ── BLS public API (LAUS and CPI) ────────────────────────────────────────────

def bls_batch(series, y0, y1, refresh=False):
    """Annual averages for up to 25 series over at most 10 years from the keyless BLS API; cached so a rerun costs no queries."""
    tag = re.sub(r"\W", "", f"{series[0]}_{len(series)}_{y0}_{y1}")
    p = CACHE / "bls" / f"{tag}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    r = requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/", json={"seriesid": series, "startyear": str(y0), "endyear": str(y1), "annualaverage": True}, headers=UA, timeout=120)
    j = r.json()
    if j.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API: {j.get('status')} {j.get('message')}. The keyless API allows 25 queries a day; rerun tomorrow, the batches already fetched are cached.")
    res = {}
    for s in j["Results"]["series"]:
        months, ann = {}, {}
        for d in s["data"]:
            if d["period"] == "M13":
                ann[int(d["year"])] = num(d["value"])
            elif d["period"].startswith("M"):
                months.setdefault(int(d["year"]), []).append(num(d["value"]))
        for y, v in months.items():
            if y not in ann and len(v) == 12 and None not in v:
                ann[y] = sum(v) / 12
        res[s["seriesID"]] = ann
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(res), encoding="utf-8")
    return res


def bls_all(series, y0, y1, refresh=False):
    out = {}
    for lo in range(y0, y1 + 1, 10):
        hi = min(y1, lo + 9)
        for i in range(0, len(series), 25):
            out_b = bls_batch(series[i:i + 25], lo, hi, refresh)
            for k, v in out_b.items():
                out.setdefault(k, {}).update({int(a): b for a, b in v.items()})
    return out


# ── USAspending ──────────────────────────────────────────────────────────────

AWARD_TYPES = {"contracts": ["A", "B", "C", "D"], "grants": ["02", "03", "04", "05"], "direct_payments": ["06", "10"], "loans": ["07", "08"], "other": ["09", "11", "-1"]}


def last_fy():
    t = date.today()
    return t.year - 1 if (t.month, t.day) < (11, 15) else t.year   # a fiscal year is final about six weeks after it ends


def usaspending(geoids, refresh=False):
    """{category: {fy: {geoid: dollars}}}; 'total' sums the five categories. Place of performance as reported by the awarding agency."""
    out = {c: {} for c in AWARD_TYPES}
    for fy in range(2008, last_fy() + 1):
        for cat, codes in AWARD_TYPES.items():
            p = CACHE / "usaspending" / f"{fy}_{cat}.json"
            res = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not refresh else {}
            if not res or "PR" not in res:   # a cache file from before the state layer was fixed gets the island total added
                for layer, filt in (("county", geoids), ("state", ["PR"])):
                    if layer == "county" and any(k.startswith("72") for k in res):
                        continue
                    body = {"scope": "place_of_performance", "geo_layer": layer, "geo_layer_filters": filt, "subawards": False,
                            "filters": {"time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}], "award_type_codes": codes}}
                    for attempt in range(4):
                        r = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_geography/", json=body, headers=UA, timeout=180)
                        if r.status_code == 200:
                            break
                        time.sleep(3 * (attempt + 1))
                    else:
                        raise RuntimeError(f"USAspending {fy} {cat} {layer}: HTTP {r.status_code} {r.text[:200]}")
                    for x in r.json().get("results", []):
                        res[x["shape_code"]] = x["aggregated_amount"]
                    time.sleep(0.3)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(res), encoding="utf-8")
                time.sleep(0.3)
            out[cat][fy] = res
        log(f"  USAspending FY{fy}")
    return out


# Assistance listings (CFDA) whose money USAspending places across the municipalities: in FY2019 and FY2024 each reached 20 or more of them and less than
# 40% of what was placed was in San Juan. Programs paid to the Commonwealth government (Medicaid, nutrition assistance, Title I, public housing, highways,
# FEMA, CDBG-DR) are placed in San Juan or in no municipality, and agency totals mix the two, so neither is mapped (HANDOFF decision 69).
PROGRAMS = {"96.002": "ss_retirement", "96.001": "ss_disability", "96.004": "ss_survivors", "64.109": "va_compensation",
            "84.063": "pell", "93.600": "head_start", "14.195": "pbra"}


def usa_programs(geoids, refresh=False):
    """{program: {fy: {geoid or 'PR': dollars}}}: obligations of each assistance listing by place of performance; 'PR' is the territory total."""
    out = {p: {} for p in PROGRAMS}
    for fy in range(2008, last_fy() + 1):
        for prog in PROGRAMS:
            p = CACHE / "usaspending" / "programs" / f"{fy}_{prog}.json"
            if p.exists() and not refresh:
                out[prog][fy] = json.loads(p.read_text(encoding="utf-8"))
                continue
            res = {}
            for layer, filt in (("county", geoids), ("state", ["PR"])):
                body = {"scope": "place_of_performance", "geo_layer": layer, "geo_layer_filters": filt, "subawards": False,
                        "filters": {"time_period": [{"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}], "program_numbers": [prog]}}
                for attempt in range(5):
                    try:
                        r = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_geography/", json=body, headers=UA, timeout=180)
                    except requests.RequestException as e:   # the service drops connections now and then
                        r = e
                    if getattr(r, "status_code", None) == 200:
                        break
                    time.sleep(5 * (attempt + 1))
                else:
                    raise RuntimeError(f"USAspending {fy} {prog} {layer}: {getattr(r, 'status_code', r)}")
                for x in r.json().get("results", []):
                    if x["shape_code"] in filt:
                        res[x["shape_code"]] = x["aggregated_amount"]
                time.sleep(0.3)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(res), encoding="utf-8")
            out[prog][fy] = res
        log(f"  USAspending programs FY{fy}")
    return out


MIN_PLACES, MAX_SAN_JUAN, MAX_UNPLACED = 20, 40, 50   # the placement rule of decision 69, the same for choosing a listing and for its years


def placement(res):
    """(municipalities with money, San Juan's % of the placed money, % that names no municipality) for one listing and year; the rule's three tests."""
    pos = {g: v for g, v in res.items() if g != "PR" and v and v > 0}
    placed, pr = sum(pos.values()), res.get("PR") or 0
    return (len(pos), round(pos.get("72127", 0) / placed * 100, 1) if placed else None,
            round(max(pr - sum(v for g, v in res.items() if g != "PR" and v), 0) / pr * 100, 1) if pr > 0 else None)


def passes(n, sj, unplaced):
    return n >= MIN_PLACES and sj is not None and sj < MAX_SAN_JUAN and (unplaced is None or unplaced <= MAX_UNPLACED)


def kept_years(data):
    """The latest unbroken run of fiscal years that pass the rule. Earlier years fail where an agency recorded the money centrally (Social Security
    FY2008-2011 in San Juan, Head Start FY2009-2013 nowhere), so a series starts after its last break, and a newest year that fails is left out, not
    allowed to cut the series."""
    ok = [fy for fy in sorted(data) if passes(*placement(data[fy]))]
    if not ok:
        return []
    run = [ok[-1]]
    for fy in reversed(sorted(data)[:sorted(data).index(ok[-1])]):
        if fy not in ok:
            break
        run.insert(0, fy)
    return run


def program_values(geoids, refresh=False):
    """({key: {fy: {geoid: dollars}}}, {'statewide_share': {key: {fy: %}}}) for the program series. '72' is the territory total, which also counts
    obligations that name no municipality; the share is that unplaced part of it. Only the years kept_years() keeps are returned."""
    vals, share = {}, {}
    for prog, data in usa_programs(geoids, refresh).items():
        key = f"fed_prog_{PROGRAMS[prog]}"
        keep = kept_years(data)
        for fy in sorted(data):
            if fy not in keep and fy > keep[-1]:
                print(f"  {key} FY{fy} fails the placement rule {placement(data[fy])} and is left out; check the source")
        for fy in keep:
            res = data[fy]
            byg = {g: round(v) for g, v in res.items() if g != "PR" and v}
            if res.get("PR") is not None:
                byg["72"] = round(res["PR"])
                u = placement(res)[2]
                if u is not None:
                    share.setdefault(key, {})[str(fy)] = u
            vals.setdefault(key, {})[fy] = byg
    return vals, {"statewide_share": share}


# ── New Markets Tax Credit: investments in low-income communities (CDFI Fund) ──

# The CDFI Fund publishes every NMTC investment once a year (an Excel file on its data releases page): one row per qualified low-income community investment
# (QLICI), with the project's 2020 census tract, the year the investment was made and its amount. The build takes the newest file listed on that page.
NMTC_PAGE = "https://www.cdfifund.gov/documents/data-releases"
NMTC_FILE = re.compile(r'href="(/system/files\?file=[^"]*NMTC_Public_Data_Release_includes[^"]*\.xlsx)"')
NMTC_KEYS = ["nmtc_qlici", "nmtc_projects"]
NMTC_SHEET = "Financial Notes 1 - Data Set PU"   # one row per QLICI; the file's other sheets are its projects and the data point descriptions


def nmtc_release(refresh=False):
    """(path of the newest NMTC data file in the cache, its URL): read from the data releases page when --refresh is given or nothing is cached."""
    d = CACHE / "nmtc"
    have = sorted(d.glob("*.xlsx")) if d.exists() else []
    if have and not refresh:
        return have[-1], (d / "url.txt").read_text(encoding="utf-8").strip()
    m = NMTC_FILE.search(requests.get(NMTC_PAGE, headers=UA, timeout=60).text)
    if not m:
        raise SystemExit(f"NMTC: no data file found on {NMTC_PAGE}; the page changed")
    url = "https://www.cdfifund.gov" + m.group(1)
    p = d / re.sub(r"[^\w.-]", "_", url.rsplit("=", 1)[-1].rsplit("/", 1)[-1])
    if not p.exists():
        d.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, headers=UA, timeout=300)
        r.raise_for_status()
        p.write_bytes(r.content)
        log(f"  NMTC: downloaded {p.name}")
    (d / "url.txt").write_text(url + "\n", encoding="utf-8")
    return p, url


def nmtc_values(names, geoids, refresh=False):
    """({key: {year: {geoid: value}}}, notes) for the NMTC series: QLICI dollars by the municipio of the project's census tract and the year the investment was
    made, and projects by the year of their first QLICI. Every year of the release is filled: a municipio with no investment that year is 0, not blank."""
    p, url = nmtc_release(refresh)
    it = xlsx_read.rows(p.read_bytes(), NMTC_SHEET)
    head = next(it)
    ix = {c: next(i for i, h in head.items() if h == c) for c in ("Project ID", "2020 Census Tract", "Origination Year", "QLICI Amount", "State")}
    years, notes_pr = set(), []
    for r in it:
        if r.get(ix["Origination Year"]):
            years.add(int(float(r[ix["Origination Year"]])))
        if r.get(ix["State"]) == "PR":
            notes_pr.append(r)
    known = set(geoids)
    vals = {k: {y: dict.fromkeys(geoids, 0) for y in range(min(years), max(years) + 1)} for k in NMTC_KEYS}
    first, placed = {}, {}
    for r in notes_pr:
        g = str(r[ix["2020 Census Tract"]]).split(".")[0][:5]
        if g not in known:
            raise SystemExit(f"NMTC: a Puerto Rico investment has the tract {r[ix['2020 Census Tract']]!r}")
        y = int(float(r[ix["Origination Year"]]))
        vals["nmtc_qlici"][y][g] += float(r.get(ix["QLICI Amount"]) or 0)
        pid = r[ix["Project ID"]]
        first[pid] = min(first.get(pid, y), y)
        placed.setdefault(pid, g)
    for pid, y in first.items():
        vals["nmtc_projects"][y][placed[pid]] += 1
    for k in NMTC_KEYS:
        for y, byg in vals[k].items():
            for g in byg:
                byg[g] = round(byg[g])
            byg["72"] = sum(byg.values())
    return vals, {"nmtc_release": url.rsplit("=", 1)[-1].rsplit("/", 1)[-1], "nmtc_years": f"{min(years)}-{max(years)}", "nmtc_investments_pr": len(notes_pr), "nmtc_projects_pr": len(first)}


# ── Federal Audit Clearinghouse: federal money spent by each municipio government ──

# The single audit each municipio government files when it spends $750,000 or more of federal money in its fiscal year (July to June). The FAC API needs
# a free api.data.gov key in FAC_API_KEY (HANDOFF decision 70): the only key the repository uses, read by this build and never published. Without it the
# public DEMO_KEY is tried, which allows only about ten calls an hour.
FAC_URL = "https://api.fac.gov"
FAC_AGENCIES = {"93": "hhs", "14": "hud", "97": "dhs", "21": "treasury"}   # the four agencies with 92% of the money, FY2016-2025; the rest is "other"
FAC_KEYS = ["fac_expended", "fac_direct", "fac_passthrough"] + [f"fac_{a}" for a in FAC_AGENCIES.values()] + ["fac_other"]
FAC_GENERAL = "report_id,audit_year,auditee_name,auditee_ein,entity_type,fy_end_date,total_amount_expended,resubmission_status,fac_accepted_date"   # no contact fields
FAC_AWARDS = "report_id,federal_agency_prefix,federal_award_extension,amount_expended,is_direct,is_loan"
# audits of other bodies whose names contain the municipio's: its housing projects, a community it runs, a program filed apart, consortia and agencies
FAC_NOT_GOVERNMENT = re.compile(r"HOUSING|JARDINES|HUCARES|SOIGAL|COLINAS|RETIRO|RYAN WHITE|ALIANZA|ALLIANCE|COOPERATIVA|COLLECTION|COMMIS|MARITIME")


def fac_get(path, params):
    key = os.environ.get("FAC_API_KEY") or "DEMO_KEY"
    for attempt in range(5):
        try:
            r = requests.get(f"{FAC_URL}/{path}", params=params, headers={**UA, "X-Api-Key": key}, timeout=180)
        except requests.RequestException as e:
            r = e
        if getattr(r, "status_code", None) == 200:
            return r.json()
        if getattr(r, "status_code", None) == 429:
            raise RuntimeError("FAC API: rate limit reached" + ("" if key != "DEMO_KEY" else "; set FAC_API_KEY to an api.data.gov key"))
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"FAC API {path}: {getattr(r, 'status_code', r)}")


def fac_name_key(s):
    s = unicodedata.normalize("NFKD", s.upper().replace("?", "N").replace("MANAT1", "MANATI")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z ]", " ", s)).strip()


def fac_municipio(name, by_name):
    """The geoid of the municipio whose government filed an audit under this name, or None ('MUNICIPALITY OF SAN JUAN', 'MUNICIPIO DE MANATI',
    'AUTONOMOUS MUNICIPALITY OF PONCE', 'VIEQUES, MUNICIPALITY OF'; not 'VALLE VERDE HOUSING - MUNICIPALITY OF ADJUNTAS')."""
    u = name.upper()
    if FAC_NOT_GOVERNMENT.search(u):
        return None
    m = re.search(r"MUNICIPAL(?:ITY)?\s*(?:OF|DE)\s+(.+)$|MUNICIPIO\s+(?:AUTONOMO\s+)?DE\s+(.+)$|^(.+?),\s*MUNICIPALITY OF$|^(.+) MUNICIPALITY$", u)
    if not m:
        return None
    t = re.sub(r" (PUERTO RICO|EIN NOTED)$", "", fac_name_key(next(g for g in m.groups() if g)))
    return by_name.get(t)


def fac_audits(names, geoids, refresh=False):
    """{(geoid, fiscal year): audit header} for the municipio governments. Names are matched first; an audit whose name has a typo ('MUNCIPALITY OF
    JUNCOS') is taken by its EIN when that EIN belongs to one municipio only. Two audits of one municipio and year keep the last one accepted."""
    p = CACHE / "fac" / "general_pr.json"
    if refresh or not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(fac_get("general", {"auditee_state": "eq.PR", "limit": 20000, "select": FAC_GENERAL})), encoding="utf-8")
    rows = [r for r in json.loads(p.read_text(encoding="utf-8")) if r.get("resubmission_status") in ("most_recent", "", None)]
    by_name = {fac_name_key(n): g for n, g in zip(names, geoids)}
    found = {r["report_id"]: fac_municipio(r["auditee_name"], by_name) for r in rows}
    eins = {}
    for r in rows:
        if found[r["report_id"]]:
            eins.setdefault(r["auditee_ein"], set()).add(found[r["report_id"]])
    out = {}
    for r in sorted(rows, key=lambda r: r["fac_accepted_date"]):
        g = found[r["report_id"]]
        if not g and not FAC_NOT_GOVERNMENT.search(r["auditee_name"].upper()) and len(eins.get(r["auditee_ein"], ())) == 1:
            g = next(iter(eins[r["auditee_ein"]]))
        if g:
            k = (g, int(r["audit_year"]))
            if k in out and out[k]["total_amount_expended"] != r["total_amount_expended"]:
                print(f"  FAC: two audits of {g} for FY{k[1]} with different totals; keeping {r['report_id']}")
            out[k] = r
    return out


def fac_awards(audits, refresh=False):
    """{report_id: [award lines]} for the audits, cached by fiscal year; a year is downloaded again only when it has audits not in its cache."""
    out = {}
    for fy in sorted({y for _, y in audits}):
        ids = sorted(a["report_id"] for (g, y), a in audits.items() if y == fy)
        p = CACHE / "fac" / f"awards_{fy}.json"
        have = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not refresh else {}
        if set(ids) - set(have):
            have = {i: [] for i in ids}
            for x in fac_get("federal_awards", {"report_id": f"in.({','.join(ids)})", "limit": 20000, "select": FAC_AWARDS}):
                have[x["report_id"]].append(x)
            p.write_text(json.dumps(have), encoding="utf-8")
            log(f"  FAC awards FY{fy}: {len(ids)} audits")
        out.update({i: have[i] for i in ids})
    return out


def fac_values(names, geoids, refresh=False):
    """({key: {fy: {geoid: dollars}}}, notes) for the FAC series, by the municipio's fiscal year (July to June, named by the year it ends). The Puerto
    Rico value ('72') sums the municipios that filed; notes.fac_filed counts them."""
    audits = fac_audits(names, geoids, refresh)
    lines = fac_awards(audits, refresh)
    vals, filed = {k: {} for k in FAC_KEYS}, {}
    for (g, fy), a in audits.items():
        s = dict.fromkeys(FAC_KEYS, 0.0)
        for x in lines[a["report_id"]]:
            v = x["amount_expended"] or 0
            s["fac_expended"] += v
            s["fac_direct" if x["is_direct"] == "Y" else "fac_passthrough"] += v
            s[f"fac_{FAC_AGENCIES.get(x['federal_agency_prefix'], 'other')}"] += v
        if abs(s["fac_expended"] - float(a["total_amount_expended"])) > 1:
            print(f"  FAC: {a['report_id']} award lines add up to {s['fac_expended']:.0f}, the audit says {a['total_amount_expended']}")
        for k, v in s.items():
            vals[k].setdefault(fy, {})[g] = round(v)
        filed[str(fy)] = filed.get(str(fy), 0) + 1
    for k in FAC_KEYS:
        for fy, byg in vals[k].items():
            byg["72"] = sum(byg.values())
    return vals, {"fac_filed": dict(sorted(filed.items())), "fac_retrieved": date.fromtimestamp((CACHE / "fac" / "general_pr.json").stat().st_mtime).isoformat()}


# ── FEMA Public Assistance ───────────────────────────────────────────────────

PA_CATS = {"A": "debris", "B": "emergency", "C": "roads", "D": "water_control", "E": "buildings", "F": "utilities", "G": "parks_other", "Z": "management"}   # FEMA damage categories


def fema_pa(names, geoids, refresh=False):
    """Federal share obligated for Public Assistance projects by municipality and the year of the disaster declaration, in total and by damage category,
    and the proposed Section 406 mitigation; 'Statewide' (and any county that is not a municipality) is kept apart."""
    p = CACHE / "fema_pa_v2.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    log("  OpenFEMA Public Assistance ...")
    rows, skip = [], 0
    while True:
        r = requests.get("https://www.fema.gov/api/open/v2/PublicAssistanceFundedProjectsDetails", params={"$filter": "stateNumberCode eq '72'", "$top": 1000, "$skip": skip, "$select": "disasterNumber,declarationDate,county,damageCategoryCode,federalShareObligated,mitigationAmount"}, headers=UA, timeout=300)
        r.raise_for_status()
        part = r.json()["PublicAssistanceFundedProjectsDetails"]
        rows += part
        if len(part) < 1000:
            break
        skip += 1000
    by_name = {hs.norm(n): g for n, g in zip(names, geoids)}
    out = {"by_year": {}, "statewide": {}, "projects": len(rows), "retrieved": str(date.today()), "cat": {}, "cat_statewide": {}, "mit": {}, "mit_statewide": {}, "uncategorised": 0}

    def add(tree, y, g, v):
        tree.setdefault(y, {})[g] = tree.setdefault(y, {}).get(g, 0) + v

    for x in rows:
        y = x["declarationDate"][:4]
        amt = x.get("federalShareObligated") or 0
        mit = x.get("mitigationAmount") or 0
        cat = PA_CATS.get((x.get("damageCategoryCode") or "").strip()[:1])
        c = hs.norm(re.sub(r"\s*\(.*\)", "", x["county"] or ""))
        g = by_name.get(c)
        if g:
            add(out["by_year"], y, g, amt); add(out["mit"], y, g, mit)
        else:
            out["statewide"][y] = out["statewide"].get(y, 0) + amt
            out["mit_statewide"][y] = out["mit_statewide"].get(y, 0) + mit
        if cat is None:
            out["uncategorised"] += 1
            continue
        if g:
            add(out["cat"].setdefault(cat, {}), y, g, amt)
        else:
            out["cat_statewide"].setdefault(cat, {})[y] = out["cat_statewide"].setdefault(cat, {}).get(y, 0) + amt
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


# ── FEMA Hazard Mitigation Assistance ────────────────────────────────────────

HMA_APPROVED = {"Approved", "Closed", "Completed", "Subaward Accepted"}   # statuses after FEMA approved the subapplication
HMA_PENDING = {"Pending", "Submitted to FEMA"}                           # sent to FEMA, no decision yet


def hma_place(text, by_name):
    """Municipality GEOIDs named in OpenFEMA's benefitingCounties (semicolon-separated), or [] when the text is empty, 'Statewide' or names a place that is not a municipality."""
    out = []
    for part in (text or "").split(";"):
        c = hs.norm(re.sub(r"(?i)\s*municipio\s*$", "", part.replace("'", ""))).strip()
        if not c:
            continue
        if c not in by_name:
            return []   # 'statewide' or an unknown place: the whole subapplication is left unplaced
        out.append(by_name[c])
    return sorted(set(out))


def fema_hma(names, geoids, refresh=False):
    """FEMA Hazard Mitigation Assistance (HMGP, BRIC, FMA, PDM) subapplications in Puerto Rico, by benefiting municipality and federal fiscal year:
    federal share approved, federal money obligated, federal share pending and approved subapplications. A subapplication that benefits several
    municipalities is split equally among them (its count goes to each); 'Statewide' or a blank is kept apart."""
    p = CACHE / "fema_hma.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    log("  OpenFEMA Hazard Mitigation Assistance ...")
    rows, skip = [], 0
    while True:
        r = requests.get("https://www.fema.gov/api/open/v2/HmaSubapplications", params={"$filter": "subapplicantStateAbbreviation eq 'PR'", "$top": 1000, "$skip": skip, "$select": "program,fiscalYear,status,benefitingCounties,federalShareAmount,totalObligatedAmount,totalPaymentAmount"}, headers=UA, timeout=300)
        r.raise_for_status()
        part = r.json()["HmaSubapplications"]
        rows += part
        if len(part) < 1000:
            break
        skip += 1000
    by_name = {hs.norm(n): g for n, g in zip(names, geoids)}
    keys = ("hma_approved_federal", "hma_obligated", "hma_pending_federal", "hma_projects")
    out = {k: {} for k in keys}
    out.update({"statewide": {k: {} for k in keys}, "placed_projects": {}, "rows": len(rows), "retrieved": str(date.today()), "before_2000": 0, "other_status": 0,
                "payment_reported": sum(1 for x in rows if x.get("totalPaymentAmount") is not None)})
    for x in rows:
        fy = int(x["fiscalYear"])
        if fy < 2000:   # the CPI series in the file starts in 2000
            out["before_2000"] += 1
            continue
        st = x.get("status") or ""
        vals = {"hma_obligated": x.get("totalObligatedAmount") or 0}
        if st in HMA_APPROVED:
            vals.update(hma_approved_federal=x.get("federalShareAmount") or 0, hma_projects=1)
        elif st in HMA_PENDING:
            vals["hma_pending_federal"] = x.get("federalShareAmount") or 0
        else:
            out["other_status"] += 1
        places = hma_place(x.get("benefitingCounties"), by_name)
        y = str(fy)
        if places and vals.get("hma_projects"):
            out["placed_projects"][y] = out["placed_projects"].get(y, 0) + 1
        for k, v in vals.items():
            if not places:
                out["statewide"][k][y] = out["statewide"][k].get(y, 0) + v
                continue
            for g in places:
                share = v if k == "hma_projects" else v / len(places)
                out[k].setdefault(y, {})[g] = out[k].setdefault(y, {}).get(g, 0) + share
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


FEMA_KEYS = ["fema_pa_obligated"] + [f"fema_pa_cat_{c.lower()}" for c in PA_CATS] + ["fema_pa_406_mitigation", "hma_approved_federal", "hma_obligated", "hma_pending_federal", "hma_projects"]


def fema_values(names, geoids, refresh=False):
    """({key: {year: {geoid: value}}}, extras, notes) for the FEMA series. Each Puerto Rico value ('72') is the 78 municipalities plus what cannot be placed
    in one; extras give that unplaced part as a share of Puerto Rico for each year."""
    pa, hma = fema_pa(names, geoids, refresh), fema_hma(names, geoids, refresh)
    parts = [("fema_pa_obligated", pa["by_year"], pa["statewide"])]
    parts += [(f"fema_pa_cat_{c.lower()}", pa["cat"].get(cat, {}), pa["cat_statewide"].get(cat, {})) for c, cat in PA_CATS.items()]
    parts.append(("fema_pa_406_mitigation", pa["mit"], pa["mit_statewide"]))
    parts += [(k, hma[k], hma["statewide"][k]) for k in ("hma_approved_federal", "hma_obligated", "hma_pending_federal", "hma_projects")]
    vals, share = {}, {}
    for key, byy, sw in parts:
        cnt = key == "hma_projects"
        out = vals.setdefault(key, {})
        for y, byg in byy.items():
            out.setdefault(int(y), {}).update({g: round(v) for g, v in byg.items()})
        for y in set(byy) | set(sw):
            # each approved subapplication counts once for Puerto Rico, though it counts in every municipality it benefits
            tot = sw.get(y, 0) + (hma["placed_projects"].get(y, 0) if cnt else sum(byy.get(y, {}).values()))
            out.setdefault(int(y), {})["72"] = round(tot)
            if not cnt and tot:
                share.setdefault(key, {})[y] = round(sw.get(y, 0) / tot * 100, 1)
    extras = {"fema_pa_statewide_share": share.pop("fema_pa_obligated", {}), "statewide_share": share}
    notes = {"fema_pa_projects": pa["projects"], "fema_pa_retrieved": pa.get("retrieved"), "fema_pa_uncategorised": pa.get("uncategorised"), "hma_subapplications": hma["rows"],
             "hma_retrieved": hma["retrieved"], "hma_before_2000": hma["before_2000"], "hma_other_status": hma["other_status"], "hma_payment_reported": hma["payment_reported"]}
    return vals, extras, notes


# ── Police: Type I crimes by municipality ────────────────────────────────────

# The December report of each year counts January to December. The Instituto de Estadísticas keeps the reports up to 2024 on its old site
# (frozen); later ones are found on the product page of the new site.
POLICE_OLD = "https://estadisticas.pr/files/inventario/delitos_tipo_i/"
POLICE_DEC = {2017: "2018-01-09/Diciembre%202017.xls", 2018: "2019-01-14/Policia_DelitosTipoI_201812.xls", 2019: "2020-01-22/Policia_DelitosTipoI_201912.xls",
              2020: "2021-01-19/Policia_DelitosTipoI_202012.xls", 2021: "2022-01-12/Policia_DelitosTipoI_202112.xls", 2022: "2023-01-10/Policia-DelitosTipoI-2022-12.xls",
              2023: "2024-01-17/Policia-DelitosTipoI-2023-12.zip", 2024: "2025-01-13/Policia-DelitosTipoI-2024-12.zip"}
POLICE_PAGE = "https://www.estadisticas.pr.gov/en-us/productos/delitos-tipo-i"
CRIMES = ["murder", "rape", "trafficking", "robbery", "assault", "burglary", "larceny", "vehicle"]   # the column order of the PDF tables


def fetch(url):
    """Bytes of a URL. estadisticas.pr serves an incomplete certificate chain that Python rejects, so fall back to curl, which completes it."""
    try:
        r = requests.get(url, headers=UA, timeout=300)
        r.raise_for_status()
        return r.content
    except requests.exceptions.SSLError:   # ponytail: curl only fills the chain where the system store has the intermediate (macOS does); get the files once there
        import subprocess
        return subprocess.run(["curl", "-fsSL", "-m", "300", url], check=True, capture_output=True).stdout


def police_table(raw, name):
    """{municipality name: [total] + CRIMES} from one December report (.xls for 2017-2022, a .zip of PDFs from 2023)."""
    rows = {}
    if name.endswith(".xls"):   # sheet MUNICIPIO(S): name, total, then the crimes in CRIMES order
        import xlrd
        book = xlrd.open_workbook(file_contents=raw)
        sh = next(s for s in book.sheets() if s.name.strip().upper().startswith("MUNICIPIO"))
        for r in range(1, sh.nrows):
            v = sh.row_values(r)
            if isinstance(v[0], str) and v[0].strip() and all(isinstance(x, float) for x in v[1:10]):
                rows[v[0].strip()] = [int(x) for x in v[1:10]]
        return rows
    import subprocess, tempfile, zipfile
    z = zipfile.ZipFile(io.BytesIO(raw))
    pdf = next(n for n in z.namelist() if re.search(r"(?i)municipio", n) and n.lower().endswith(".pdf"))
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(z.read(pdf)); f.flush()
        text = subprocess.run(["pdftotext", "-layout", f.name, "-"], check=True, capture_output=True, text=True).stdout   # pdftotext comes with Poppler
    for line in text.splitlines():   # name, then the crimes in CRIMES order with the total first (2023) or last (2024 on); the page footers carry a staff e-mail and are skipped
        m = re.match(r"^\s*([^\d@]+?)\s{2,}((?:[\d.,]+\s+){8}[\d.,]+)\s*$", line)
        if m:   # counts only, so a comma or a dot is a thousands separator (2025 uses dots)
            n = [int(re.sub(r"[.,]", "", x)) for x in m.group(2).split()]
            rows[m.group(1).strip()] = n if n[0] == sum(n[1:]) else [n[8]] + n[:8]
    return rows


def police(names, geoids, refresh=False):
    """Type I crimes reported to the Police by municipality and calendar year: {year: {geoid or '72': [total] + CRIMES}}."""
    p = CACHE / "police_type1.json"
    if p.exists() and not refresh:
        return {int(y): v for y, v in json.loads(p.read_text(encoding="utf-8")).items()}
    log("  Police Type I crimes (Instituto de Estadísticas) ...")
    urls = {y: POLICE_OLD + f for y, f in POLICE_DEC.items()}
    page = requests.get(POLICE_PAGE, headers=UA, timeout=120).text
    for u in re.findall(r'href="([^"]+Policia-DelitosTipoI-(\d{4})-12[^"]*\.zip)"', page):
        urls.setdefault(int(u[1]), u[0])
    by_name = {hs.norm(n): g for n, g in zip(names, geoids)}
    by_name["sabana"] = by_name["sabana grande"]   # the 2024 table cuts the name short
    out = {}
    for y, u in sorted(urls.items()):
        rows = police_table(fetch(u), u)
        tot = next(v for k, v in rows.items() if hs.norm(k) in ("total", "totales"))
        res = {by_name[hs.norm(k)]: v for k, v in rows.items() if hs.norm(k) in by_name}
        if len(res) != 78 or [sum(c) for c in zip(*res.values())] != tot:
            raise SystemExit(f"Police {y}: {len(res)} municipalities matched; the columns must add up to the TOTAL row ({u})")
        if any(v[0] != sum(v[1:]) for v in res.values()):
            raise SystemExit(f"Police {y}: a municipality's total is not the sum of its crimes ({u})")
        res["72"] = tot
        out[y] = res
        log(f"    {y}: {tot[0]:,} Type I crimes, {tot[1]} murders")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out), encoding="utf-8")
    return out


def police_values(names, geoids, refresh=False):
    """The crime_* series of the catalog, {key: {year: {geoid: value}}}: violent crimes are the first five of CRIMES, property crimes the last three."""
    out = {}
    for y, res in police(names, geoids, refresh).items():
        for g, v in res.items():
            for key, x in (("crime_type1", v[0]), ("crime_violent", sum(v[1:6])), ("crime_property", sum(v[6:9])), ("crime_murders", v[1])):
                out.setdefault(key, {}).setdefault(y, {})[g] = x
    return out


# ── ACS: income distribution, class of worker, commuting ─────────────────────

def derive_econ(rec):
    c = hs.Cells(rec)
    one = c.cell
    out = {}

    def put(k, v, m=None):
        if v is not None:
            out[k] = (round(v, 3 if k == "gini" else 2), None if m is None else round(m, 3 if k == "gini" else 2))

    put("gini", *one("B19083", 1))
    hh = one("B19001", 1)
    put("hh_income_under_25k_pct", *hs.pct(c.sum("B19001", [2, 3, 4, 5]), hh))
    put("hh_income_75k_plus_pct", *hs.pct(c.sum("B19001", [13, 14, 15, 16, 17]), hh))
    w = one("B24080", 1)
    put("workers_16plus", *w)
    put("gov_worker_pct", *hs.pct(c.sum("B24080", [7, 8, 9, 17, 18, 19]), w))
    put("self_employed_pct", *hs.pct(c.sum("B24080", [5, 10, 15, 20]), w))
    put("nonprofit_worker_pct", *hs.pct(c.sum("B24080", [6, 16]), w))
    cm = one("B08301", 1)
    put("commute_drive_alone_pct", *hs.pct(one("B08301", 3), cm))
    put("commute_transit_pct", *hs.pct(one("B08301", 10), cm))
    put("commute_walk_pct", *hs.pct(one("B08301", 19), cm))
    put("work_from_home_pct", *hs.pct(one("B08301", 21), cm))
    put("commute_45plus_pct", *hs.pct(c.sum("B08303", [11, 12, 13]), one("B08303", 1)))
    put("no_vehicle_hh_pct", *hs.pct(c.sum("B25044", [3, 10]), one("B25044", 1)))
    put("internet_subscription_pct", *hs.pct(one("B28002", 2), one("B28002", 1)))
    put("no_internet_pct", *hs.pct(one("B28002", 13), one("B28002", 1)))
    return out


# ── Catalog ──────────────────────────────────────────────────────────────────
# key, group, label, unit, decimals, type, sources, reference, definition, extra
#   type: count | total$ (extensive: can be shown per resident, per km², as a share of Puerto Rico) · rate | level$ | ratio (intensive)

CATALOG = [
    ("qcew_jobs", "Jobs and employers", "Jobs (all employers)", "", 0, "count", ["qcew"], "BLS QCEW, all industries and ownerships", "Average number of jobs in the year at employers located in the municipality (wage-and-salary jobs covered by unemployment insurance, which the Bureau says is about 95% of jobs in the United States; self-employed and informal work are not counted). Jobs are counted where the work is done, not where workers live.", {"family": "jobs"}),
    ("qcew_private_jobs", "Jobs and employers", "Private-sector jobs", "", 0, "count", ["qcew"], "BLS QCEW, private ownership", "Average jobs at private employers located in the municipality.", {"family": "jobs"}),
    ("qcew_gov_jobs", "Jobs and employers", "Government jobs (federal, state, local)", "", 0, "count", ["qcew"], "BLS QCEW, government ownerships", "Total jobs minus private-sector jobs: federal, Commonwealth and municipal government employment (including municipal agencies and public schools).", {"family": "jobs"}),
    ("gov_job_share_pct", "Jobs and employers", "Government share of jobs", "%", 1, "rate", ["qcew"], "BLS QCEW", "Government jobs as a share of all jobs in the municipality.", {}),
    ("qcew_estabs", "Jobs and employers", "Establishments", "", 0, "count", ["qcew"], "BLS QCEW, all industries", "Average number of establishments (work sites of employers with employees) located in the municipality.", {}),
    ("qcew_wages", "Jobs and employers", "Total wages paid", "$", 0, "total$", ["qcew"], "BLS QCEW, all industries", "Total wages paid in the year by employers located in the municipality, in that year's dollars.", {}),
    ("qcew_avg_pay", "Jobs and employers", "Average annual pay per job", "$", 0, "level$", ["qcew"], "BLS QCEW, all industries", "Total wages divided by average jobs: what the average job at an employer in the municipality pays, in that year's dollars. It describes the jobs located there, not the residents' incomes.", {}),
    ("jobs_per_employed_resident", "Jobs and employers", "Jobs per employed resident", "", 2, "ratio", ["qcew", "acs"], "BLS QCEW jobs ÷ ACS employed residents", "Jobs located in the municipality divided by employed residents (ACS). Above 1 the municipality is a job centre that draws commuters; well below 1 it is a bedroom community. Informal and self-employed work is in the denominator but not the numerator.", {}),
    ("laus_unemp_rate", "Labor force", "Unemployment rate (BLS)", "%", 1, "rate", ["laus"], "BLS LAUS, annual average", "Unemployed people as a share of the labor force, annual average. A Bureau estimate built from local administrative and survey data and controlled to state totals (not a direct count), so it is smoother than a survey of a small municipality could be. The file has no annual average for 2020, and the latest year is preliminary: small municipalities can swing from one year to the next (and be revised).", {}),
    ("laus_labor_force", "Labor force", "Labor force", "", 0, "count", ["laus"], "BLS LAUS, annual average", "Residents 16 and over who are working or looking for work, annual average.", {"family": "labor"}),
    ("laus_employed", "Labor force", "Employed residents (BLS)", "", 0, "count", ["laus"], "BLS LAUS (derived)", "Labor force minus unemployed, from the BLS labor force and unemployment rate.", {"family": "labor"}),
    ("laus_unemployed", "Labor force", "Unemployed residents (BLS)", "", 0, "count", ["laus"], "BLS LAUS (derived)", "Labor force times the unemployment rate.", {"family": "labor"}),
    ("tourism_jobs", "Industries", "Tourism-related jobs (arts, entertainment, recreation, accommodation, food)", "", 0, "count", ["qcew"], "BLS QCEW, NAICS 71 and 72", "Private jobs in arts, entertainment and recreation (NAICS 71) and accommodation and food services (72): the usual statistical stand-in for the visitor economy. Includes restaurants that serve residents as much as visitors. Where the Bureau withholds arts, entertainment and recreation for a small municipality, only accommodation and food are counted, so the figure is slightly low there.", {"family": "jobs"}),
    ("accommodation_jobs", "Industries", "Accommodation jobs (hotels, inns, rentals)", "", 0, "count", ["qcew"], "BLS QCEW, NAICS 721", "Private jobs in accommodation (NAICS 721).", {"family": "jobs"}),
    ("food_service_jobs", "Industries", "Food service jobs (restaurants, bars)", "", 0, "count", ["qcew"], "BLS QCEW, NAICS 722", "Private jobs in food services and drinking places (NAICS 722).", {"family": "jobs"}),
    ("industry_hhi", "Industries", "Industry concentration (Herfindahl index)", "", 0, "ratio", ["qcew"], "BLS QCEW, sector jobs", "Sum of squared shares of jobs across the private NAICS sectors and government, times 10,000. Lower means a more diversified local economy; 10,000 means all jobs in one sector. Computed only where the published sectors cover at least 80% of jobs.", {}),
] + [(f"jobs_{slug(c)}", "Industries", f"Jobs: {label}", "", 0, "count", ["qcew"], f"BLS QCEW, private NAICS {c}", f"Average jobs in private-sector NAICS {c}, {label.lower()}, at employers located in the municipality. Blank where the Bureau withholds the figure to protect an employer's confidentiality (common in small municipalities).", {"family": "jobs"}) for c, label in SECTORS] + [
    ("median_hh_income", "Income and poverty", "Median household income", "$", 0, "level$", ["acs"], "ACS B19013 (Housing page series)", "Median household income of the residents, in the dollars of the last year of each five-year window.", {"from": "housing"}),
    ("per_capita_income", "Income and poverty", "Per capita income", "$", 0, "level$", ["acs"], "ACS B19301 (Housing page series)", "Income per resident, in the dollars of the last year of each five-year window.", {"from": "housing"}),
    ("median_owner_income", "Income and poverty", "Median income of owner households", "$", 0, "level$", ["acs"], "ACS B25119 (Housing page series)", "Median household income of owner-occupied households.", {"from": "housing"}),
    ("median_renter_income", "Income and poverty", "Median income of renter households", "$", 0, "level$", ["acs"], "ACS B25119 (Housing page series)", "Median household income of renter-occupied households.", {"from": "housing"}),
    ("poverty_pct", "Income and poverty", "Population below the poverty level", "%", 1, "rate", ["acs"], "ACS B17001 (Housing page series)", "Share of people whose income in the past 12 months was below the federal poverty level.", {"from": "housing"}),
    ("gini", "Income and poverty", "Income inequality (Gini index)", "", 3, "ratio", ["acs"], "ACS B19083", "Gini index of household income: 0 is perfect equality, 1 is one household holding all income.", {}),
    ("hh_income_under_25k_pct", "Income and poverty", "Households earning under $25,000", "%", 1, "rate", ["acs"], "ACS B19001", "Share of households with income below $25,000 in the past 12 months (dollars of the window's last year).", {}),
    ("hh_income_75k_plus_pct", "Income and poverty", "Households earning $75,000 or more", "%", 1, "rate", ["acs"], "ACS B19001", "Share of households with income of $75,000 or more in the past 12 months (dollars of the window's last year).", {}),
    ("employment_rate_pct", "Labor force", "Employment rate, residents 16+ (ACS)", "%", 1, "rate", ["acs"], "ACS B23025 (Housing page series)", "Employed civilians as a share of all residents 16 and over, from the survey. Low in Puerto Rico partly because many adults are retired or outside the formal labor force.", {"from": "housing"}),
    ("unemployment_rate_pct", "Labor force", "Unemployment rate (ACS survey)", "%", 1, "rate", ["acs"], "ACS B23025 (Housing page series)", "Unemployed as a share of the civilian labor force, from the five-year survey (noisier than the BLS series for small municipalities).", {"from": "housing"}),
    ("bachelors_pct", "Income and poverty", "Adults 25+ with a bachelor's degree or higher", "%", 1, "rate", ["acs"], "ACS B15002 (Housing page series)", "Share of adults 25 and over holding a bachelor's, master's, professional or doctoral degree.", {"from": "housing"}),
    ("workers_16plus", "Workers and commuting", "Employed residents 16+ (ACS)", "", 0, "count", ["acs"], "ACS B24080", "Civilian employed residents 16 and over, from the survey.", {"family": "labor"}),
    ("gov_worker_pct", "Workers and commuting", "Residents working for government", "%", 1, "rate", ["acs"], "ACS B24080", "Employed residents who work for local, Commonwealth or federal government, wherever the job is.", {}),
    ("self_employed_pct", "Workers and commuting", "Self-employed residents", "%", 1, "rate", ["acs"], "ACS B24080", "Employed residents working for themselves (own business, incorporated or not). A rough window on the informal economy, which the jobs data do not see.", {}),
    ("nonprofit_worker_pct", "Workers and commuting", "Residents working for nonprofits", "%", 1, "rate", ["acs"], "ACS B24080", "Employed residents who work for private not-for-profit organisations.", {}),
    ("commute_drive_alone_pct", "Workers and commuting", "Workers who drive alone to work", "%", 1, "rate", ["acs"], "ACS B08301", "Share of all workers 16 and over (including those who work at home) who usually drive alone to work.", {}),
    ("commute_transit_pct", "Workers and commuting", "Workers who take public transportation to work", "%", 1, "rate", ["acs"], "ACS B08301", "Share of all workers 16 and over (including those who work at home) who usually take public transportation (excluding taxis).", {}),
    ("commute_walk_pct", "Workers and commuting", "Workers who walk to work", "%", 1, "rate", ["acs"], "ACS B08301", "Share of all workers 16 and over (including those who work at home) who usually walk to work.", {}),
    ("work_from_home_pct", "Workers and commuting", "Workers who work from home", "%", 1, "rate", ["acs"], "ACS B08301", "Share of workers 16+ who worked at home.", {}),
    ("commute_45plus_pct", "Workers and commuting", "Commutes of 45 minutes or more", "%", 1, "rate", ["acs"], "ACS B08303", "Share of commuters (excluding those working at home) whose usual trip to work takes 45 minutes or longer.", {}),
    ("no_vehicle_hh_pct", "Workers and commuting", "Households with no vehicle", "%", 1, "rate", ["acs"], "ACS B25044", "Share of occupied homes with no vehicle available.", {}),
    ("internet_subscription_pct", "Workers and commuting", "Households with an internet subscription", "%", 1, "rate", ["acs"], "ACS B28002", "Share of households with any internet subscription. First available in the 2013-2017 window.", {}),
    ("no_internet_pct", "Workers and commuting", "Households with no internet access", "%", 1, "rate", ["acs"], "ACS B28002", "Share of households with no internet access at all. First available in the 2013-2017 window.", {}),
    ("fed_awards_total", "Public money", "Federal awards, all types", "$", 0, "total$", ["usaspending"], "USAspending, place of performance", "Dollars of federal contracts, grants, direct payments, loans and other assistance obligated in the federal fiscal year (October to September) for work or benefits in the municipality. Awards to the Commonwealth government for statewide programs are often attributed to the capital, so San Juan is overstated and other municipalities understated. The Puerto Rico figure is USAspending's total for the territory, which also counts awards that name no municipality, so the 78 municipalities add up to less than the island.", {"family": "fed"}),
    ("fed_contracts", "Public money", "Federal contracts", "$", 0, "total$", ["usaspending"], "USAspending, contracts", "Federal contract obligations by place of performance, fiscal year.", {"family": "fed"}),
    ("fed_grants", "Public money", "Federal grants", "$", 0, "total$", ["usaspending"], "USAspending, grants", "Federal grant obligations by place of performance, fiscal year. Includes disaster-recovery and block grants.", {"family": "fed"}),
    ("fed_direct_payments", "Public money", "Federal direct payments", "$", 0, "total$", ["usaspending"], "USAspending, direct payments", "Federal direct payments to individuals (for example benefit programs) by place of performance, fiscal year.", {"family": "fed"}),
    ("fed_loans", "Public money", "Federal loans (estimated cost to the government)", "$", 0, "total$", ["usaspending"], "USAspending, loans", "Estimated subsidy cost to the government of federal loans and loan guarantees (the cost, not the amount lent), by place of performance, fiscal year. It can be negative when earlier estimates are revised.", {"family": "fed"}),
    ("fed_other", "Public money", "Federal other assistance", "$", 0, "total$", ["usaspending"], "USAspending, other", "Federal insurance and other assistance not in the categories above.", {"family": "fed"}),
    ("fed_prog_ss_retirement", "Public money", "Social Security retirement benefits", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 96.002", "Federal obligations for Social Security Retirement Insurance (assistance listing 96.002) by place of performance, federal fiscal year (October to September). Benefits paid to retired workers and their families, placed where the beneficiaries live (the shares match the Social Security Administration's own county tables). The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_ss_disability", "Public money", "Social Security disability benefits", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 96.001", "Federal obligations for Social Security Disability Insurance (assistance listing 96.001) by place of performance, federal fiscal year. Benefits paid to workers who cannot work because of a disability, and their families. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_ss_survivors", "Public money", "Social Security survivors benefits", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 96.004", "Federal obligations for Social Security Survivors Insurance (assistance listing 96.004) by place of performance, federal fiscal year. Benefits paid to the families of workers who have died. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_va_compensation", "Public money", "Veterans disability compensation", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 64.109", "Federal obligations for Veterans Compensation for Service-Connected Disability (assistance listing 64.109) by place of performance, federal fiscal year. Monthly payments to veterans with a disability caused or made worse by military service. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_pell", "Public money", "Pell Grants", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 84.063", "Federal obligations for Federal Pell Grants (assistance listing 84.063) by place of performance, federal fiscal year. Grants to low-income undergraduate students, placed at the college or university that receives them, not where the students live, so municipalities with a campus show money and the others show none. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_head_start", "Public money", "Head Start grants", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 93.600", "Federal obligations for Head Start (assistance listing 93.600) by place of performance, federal fiscal year. Grants for early childhood education, placed where the grant recipient (a municipality, a consortium or a nonprofit) reports the work, which can serve children of nearby municipalities too. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fed_prog_pbra", "Public money", "Project-Based Rental Assistance", "$", 0, "total$", ["usaspending"], "USAspending, assistance listing 14.195", "Federal obligations for Section 8 Project-Based Rental Assistance (assistance listing 14.195) by place of performance, federal fiscal year. HUD rent payments to owners of privately owned buildings for units rented to low-income households, placed where the building is. The Puerto Rico value is USAspending's total for the territory, which also counts obligations that name no municipality.", {"family": "fed_prog"}),
    ("fema_pa_obligated", "Public money", "FEMA Public Assistance obligated (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects", "Federal share of FEMA Public Assistance projects (repair of roads, schools, power, water and other public facilities after disasters) by applicant municipality and the year of the disaster declaration. A large part is recorded as statewide and cannot be placed in a municipality; the Puerto Rico value includes it.", {}),
    ("fema_pa_cat_a", "Public money", "FEMA Public Assistance: debris removal (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category A", 'Federal share obligated for FEMA Public Assistance projects in damage category A (clearing debris from public property and roads), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_b", "Public money", "FEMA Public Assistance: emergency protective measures (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category B", 'Federal share obligated for FEMA Public Assistance projects in damage category B (actions to save lives and protect property during and right after the disaster, such as shelters, generators and emergency repairs), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_c", "Public money", "FEMA Public Assistance: roads and bridges (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category C", 'Federal share obligated for FEMA Public Assistance projects in damage category C (repair of public roads, bridges and their drainage), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_d", "Public money", "FEMA Public Assistance: water control facilities (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category D", 'Federal share obligated for FEMA Public Assistance projects in damage category D (repair of dams, levees, channels and other works that control water), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_e", "Public money", "FEMA Public Assistance: buildings and equipment (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category E", 'Federal share obligated for FEMA Public Assistance projects in damage category E (repair or replacement of public buildings, their contents and vehicles), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_f", "Public money", "FEMA Public Assistance: utilities (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category F", 'Federal share obligated for FEMA Public Assistance projects in damage category F (repair of power, water, sewer and communication systems), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_g", "Public money", "FEMA Public Assistance: parks, recreation and other (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category G", 'Federal share obligated for FEMA Public Assistance projects in damage category G (repair of parks, beaches, recreation sites and other public facilities), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_cat_z", "Public money", "FEMA Public Assistance: management and administrative costs (federal share)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, damage category Z", 'Federal share obligated for FEMA Public Assistance projects in damage category Z (the costs of managing the grant), by applicant municipality and the year of the disaster declaration. Part of fema_pa_obligated: the eight categories add up to it. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.', {"family": "fema_pa"}),
    ("fema_pa_406_mitigation", "Public money", "FEMA Public Assistance: Section 406 mitigation proposed (project cost)", "$", 0, "total$", ["openfema"], "OpenFEMA Public Assistance Funded Projects, mitigationAmount", "Cost proposed for Section 406 hazard mitigation inside Public Assistance projects (making a repaired facility stronger than before), by applicant municipality and the year of the disaster declaration. It is a project cost, not the federal share, and FEMA warns that some proposals are missing and some values are negative after adjustments. Projects recorded as statewide cannot be placed in a municipality; the Puerto Rico value includes them.", {"family": "fema_pa"}),
    ("hma_approved_federal", "Public money", "FEMA Hazard Mitigation: federal share approved", "$", 0, "total$", ["openfema"], "OpenFEMA Hazard Mitigation Assistance subapplications", "Federal share of the Hazard Mitigation Assistance subapplications that FEMA approved (HMGP, BRIC, FMA and PDM: projects and plans that reduce future disaster losses), by benefiting municipality and federal fiscal year (for disaster grants, the fiscal year the disaster was declared). A subapplication that benefits several municipalities is split equally among them. Subapplications for the whole island cannot be placed in a municipality; the Puerto Rico value includes them. Approved is not obligated or paid.", {"family": "hma"}),
    ("hma_obligated", "Public money", "FEMA Hazard Mitigation: federal money obligated", "$", 0, "total$", ["openfema"], "OpenFEMA Hazard Mitigation Assistance subapplications", "Federal money FEMA has obligated (made available, in steps as project milestones are met) for Hazard Mitigation Assistance subapplications, by benefiting municipality and federal fiscal year of the grant. Split and placed as for the federal share approved. Money obligated is not money paid.", {"family": "hma"}),
    ("hma_pending_federal", "Public money", "FEMA Hazard Mitigation: federal share awaiting decision", "$", 0, "total$", ["openfema"], "OpenFEMA Hazard Mitigation Assistance subapplications", "Federal share requested in Hazard Mitigation Assistance subapplications that were sent to FEMA and have no decision yet (status Pending or Submitted to FEMA), by benefiting municipality and federal fiscal year of the grant. Split and placed as for the federal share approved.", {"family": "hma"}),
    ("hma_projects", "Public money", "FEMA Hazard Mitigation: approved subapplications", "", 0, "count", ["openfema"], "OpenFEMA Hazard Mitigation Assistance subapplications", "Number of Hazard Mitigation Assistance subapplications (projects, plans and their management) that FEMA approved, by benefiting municipality and federal fiscal year of the grant. A subapplication that benefits several municipalities counts once in each, so the municipalities add up to more than Puerto Rico; the Puerto Rico value counts each subapplication once.", {"family": "hma", "noShare": True}),
    ("fac_expended", "Public money", "Federal money spent by the municipio government", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, schedule of expenditures of federal awards", "Federal awards expended by the municipio government in its fiscal year, from all federal agencies, received directly or through a pass-through entity such as a Commonwealth agency. Loans count the amount used in the year. Money spent, not obligated or awarded. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_direct", "Public money", "Federal money spent by the municipio government: received directly", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, awards marked direct", "Part of fac_expended: federal awards the municipio government received straight from a federal agency. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_passthrough", "Public money", "Federal money spent by the municipio government: through a pass-through entity", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, awards not marked direct", "Part of fac_expended: federal awards the municipio government received through a pass-through entity (mostly Commonwealth agencies, such as Vivienda for CDBG-DR). With fac_direct it adds up to fac_expended. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_hhs", "Public money", "Federal money spent by the municipio government: Health and Human Services", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, agency prefix 93", "Part of fac_expended: awards of the US Department of Health and Human Services (mostly Head Start, child care and HIV programs). From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_hud", "Public money", "Federal money spent by the municipio government: Housing and Urban Development", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, agency prefix 14", "Part of fac_expended: awards of the US Department of Housing and Urban Development (mostly housing choice vouchers and community development block grants, CDBG-DR included). From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_dhs", "Public money", "Federal money spent by the municipio government: Homeland Security (FEMA)", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, agency prefix 97", "Part of fac_expended: awards of the US Department of Homeland Security, almost all FEMA Public Assistance and Community Disaster Loans. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_treasury", "Public money", "Federal money spent by the municipio government: Treasury", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, agency prefix 21", "Part of fac_expended: awards of the US Department of the Treasury, mostly the COVID-19 Coronavirus Relief Fund and State and Local Fiscal Recovery Funds. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("fac_other", "Public money", "Federal money spent by the municipio government: other agencies", "$", 0, "total$", ["fac"], "Federal Audit Clearinghouse, other agency prefixes", "Part of fac_expended: awards of every other federal agency (Agriculture, Labor, Transportation, Education, Justice and others). The five agency series add up to fac_expended. From the single audit the municipio government files with the Federal Audit Clearinghouse, municipal fiscal year (July to June, named by the year it ends). Only the government of the municipio: federal money spent there by Commonwealth agencies, nonprofits, universities or the municipio's own housing projects (which file apart) is not counted. A government that spent less than $750,000 of federal money files no audit ($1,000,000 from FY2026), and a year whose audit is not filed yet is blank. The Puerto Rico value adds up the municipios that filed.", {"family": "fac"}),
    ("nmtc_qlici", "Public money", "Investment in low-income communities: New Markets Tax Credit (QLICI)", "$", 0, "total$", ["nmtc"], "CDFI Fund NMTC public data release, QLICI amount", "Dollars of qualified low-income community investments (loans to and equity in businesses and real estate projects in low-income census tracts) that Community Development Entities made with New Markets Tax Credit allocations, in the year each investment was made. From the CDFI Fund's NMTC public data release: each qualified low-income community investment (QLICI) placed in the municipio of its own 2020 census tract (a project with investments in several municipios is counted once, in the municipio of the first one the file lists; none in Puerto Rico does in the 2026 release), in the calendar year the investment was made. A year with no investment in a municipio is 0. The tax credit is 39% of the investment, claimed by the investors over seven years; these are the investments, not the credit.", {"family": "nmtc"}),
    ("nmtc_projects", "Public money", "Investment in low-income communities: New Markets Tax Credit projects", "", 0, "count", ["nmtc"], "CDFI Fund NMTC public data release, projects", "Number of projects that received their first New Markets Tax Credit investment that year, counted in the municipio of the project's tract. From the CDFI Fund's NMTC public data release: each qualified low-income community investment (QLICI) placed in the municipio of its own 2020 census tract (a project with investments in several municipios is counted once, in the municipio of the first one the file lists; none in Puerto Rico does in the 2026 release), in the calendar year the investment was made. A year with no investment in a municipio is 0. The tax credit is 39% of the investment, claimed by the investors over seven years; these are the investments, not the credit.", {"family": "nmtc"}),
    ("fema_ia_amount", "Public money", "FEMA Individual Assistance approved", "$", 0, "total$", ["openfema"], "OpenFEMA Housing Assistance (Housing page series)", "Dollars approved for owners and renters under FEMA Individual Assistance for disasters declared that year.", {"from": "housing"}),
    ("fema_ia_households", "Public money", "Households approved for FEMA housing assistance", "", 0, "count", ["openfema"], "OpenFEMA Housing Assistance (Housing page series)", "Owner and renter households approved for FEMA Individual Assistance after a disaster declared that year.", {"from": "housing"}),
    ("population", "People", "Resident population", "", 0, "count", ["pep"], "Census counts and Population Estimates (Housing page series)", "Residents: the 2010 and 2020 census counts and the Census Bureau's July 1 estimates for other years. The series steps up in 2020 because 2011-2019 estimates were never revised to the 2020 count.", {"from": "housing", "family": "people"}),
    ("age65_pct", "People", "Residents aged 65 and over", "%", 1, "rate", ["pep"], "Population Estimates, age and sex (Housing page series)", "Share of residents 65 or older.", {"from": "housing"}),
    ("median_age", "People", "Median age", "", 1, "rate", ["acs"], "ACS B01002 (Housing page series)", "Median age of residents, in years.", {"from": "housing"}),
    ("crime_type1", "Public safety", "Type I crimes reported to the Police", "", 0, "count", ["ppr"], "Policía de Puerto Rico, Type I crimes by municipality (December report)", "Complaints of the eight Type I crimes (murder, rape, human trafficking, robbery, aggravated assault, burglary, larceny and vehicle theft) that the Police recorded in the municipality from January to December. Crimes reported, not all crimes committed.", {"family": "crime"}),
    ("crime_violent", "Public safety", "Violent Type I crimes (murder, rape, human trafficking, robbery, aggravated assault)", "", 0, "count", ["ppr"], "Policía de Puerto Rico, Type I crimes by municipality (December report)", "Reported murders, rapes, human trafficking, robberies and aggravated assaults in the calendar year.", {"family": "crime"}),
    ("crime_property", "Public safety", "Property Type I crimes (burglary, larceny, vehicle theft)", "", 0, "count", ["ppr"], "Policía de Puerto Rico, Type I crimes by municipality (December report)", "Reported burglaries, larcenies and vehicle thefts in the calendar year.", {"family": "crime"}),
    ("crime_murders", "Public safety", "Murders (asesinatos)", "", 0, "count", ["ppr"], "Policía de Puerto Rico, Type I crimes by municipality (December report)", "Murders and non-negligent homicides the Police recorded in the municipality in the calendar year.", {"family": "crime"}),
]

SOURCES = {
    "qcew": {"name": "US Bureau of Labor Statistics — Quarterly Census of Employment and Wages (QCEW), open-data API", "url": "https://www.bls.gov/cew/", "extra": [["API and file layout", "https://www.bls.gov/cew/additional-resources/open-data/"], ["San Juan, 2024 (raw file)", "https://data.bls.gov/cew/data/api/2024/a/area/72127.csv"], ["Which employers are covered", "https://www.bls.gov/cew/overview.htm"]], "license": "US Government work — public domain", "note": "Annual averages 2014 onward for Puerto Rico's municipalities. Cells that would identify one employer are withheld."},
    "laus": {"name": "US Bureau of Labor Statistics — Local Area Unemployment Statistics (LAUS)", "url": "https://www.bls.gov/lau/", "extra": [["Estimation method", "https://www.bls.gov/lau/laumthd.htm"], ["Public data API", "https://www.bls.gov/developers/"]], "license": "US Government work — public domain", "note": "Municipio series LAUCN72xxx; annual averages."},
    "acs": {"name": "US Census Bureau — American Community Survey 5-year estimates (summary files)", "url": "https://www.census.gov/programs-surveys/acs", "extra": [["Summary files", "https://www2.census.gov/programs-surveys/acs/summary_file/"], ["Find a table (data.census.gov)", "https://data.census.gov/"]], "license": "US Government work; cite the Census Bureau as the source", "note": "Five-year windows labelled by their last year. Dollar values are in the dollars of that last year."},
    "usaspending": {"name": "USAspending.gov — federal awards by place of performance", "url": "https://www.usaspending.gov/", "extra": [["API documentation", "https://api.usaspending.gov/docs/endpoints"], ["Data dictionary", "https://www.usaspending.gov/data-dictionary"]], "license": "No license stated for the data (the API's source code is CC0-1.0)", "note": "Obligations by federal fiscal year; place of performance as reported by the awarding agency."},
    "openfema": {"name": "FEMA — OpenFEMA data sets (Public Assistance Funded Projects, HMA Subapplications, Housing Assistance)", "url": "https://www.fema.gov/about/openfema/data-sets", "extra": [["Public Assistance Funded Projects Details", "https://www.fema.gov/openfema-data-page/public-assistance-funded-projects-details-v2"], ["HMA Subapplications", "https://www.fema.gov/openfema-data-page/hma-subapplications-v2"], ["Housing Assistance Data (owners)", "https://www.fema.gov/openfema-data-page/housing-assistance-data-owners-v2"]], "license": "US Government work; OpenFEMA terms apply", "note": "FEMA series rebuilt from one download; the date is in notes.fema_pa_retrieved and notes.hma_retrieved."},
    "fac": {"name": "US General Services Administration — Federal Audit Clearinghouse (FAC), single audits", "url": "https://www.fac.gov/", "extra": [["API documentation", "https://www.fac.gov/developers/"], ["Data dictionary", "https://www.fac.gov/data/"], ["Single audit rules (2 CFR 200 subpart F)", "https://www.ecfr.gov/current/title-2/subtitle-A/chapter-II/part-200/subpart-F"]], "license": "Public domain (the FAC states that its data are free to use and in the public domain)", "note": "Audits of the municipio governments of Puerto Rico, fiscal years ending June 2016 onward (earlier audits stayed with the Census Bureau's clearinghouse). Read through the FAC API with an api.data.gov key; the date of the download is in notes.fac_retrieved and the number of municipios that filed each year in notes.fac_filed."},
    "nmtc": {"name": "US Department of the Treasury, CDFI Fund — New Markets Tax Credit (NMTC) public data release", "url": "https://www.cdfifund.gov/documents/data-releases", "extra": [["The NMTC program", "https://www.cdfifund.gov/programs-training/programs/new-markets-tax-credit"], ["Data point descriptions (in the file)", "https://www.cdfifund.gov/documents/data-releases"]], "license": "US Government work (17 U.S.C. 105: no copyright in the United States); the CDFI Fund states no other licence for the file", "note": "Investments reported by Community Development Entities in the CDFI Fund's Transaction Level Report, released once a year. The file named in notes.nmtc_release; the years it covers in notes.nmtc_years."},
    "pep": {"name": "US Census Bureau — Population Estimates, municipios of Puerto Rico", "url": "https://www.census.gov/programs-surveys/popest.html", "extra": [], "license": "US Government work; cite the Census Bureau as the source", "note": ""},
    "cpi": {"name": "US Bureau of Labor Statistics — Consumer Price Index for All Urban Consumers (CPI-U), US city average", "url": "https://www.bls.gov/cpi/", "extra": [], "license": "US Government work — public domain", "note": "This is the US index, not a Puerto Rico index, so it is an approximation of the island's inflation."},
    "ppr": {"name": "Policía de Puerto Rico — Delitos Tipo I (published by the Instituto de Estadísticas de Puerto Rico)", "url": POLICE_PAGE, "extra": [["Earlier reports (2017-2025)", "https://estadisticas.pr/en/inventario-de-estadisticas/delitos_tipo_i"], ["Police NIBRS manual", "https://estadisticas.pr/files/inventario/documentos-metodologicos/PPR_Manual_NIBRS.pdf"]], "license": "No license stated (official statistics of the Government of Puerto Rico)", "note": "The municipality table of each December report, January to December. Counts of complaints (querellas) by municipality and year of occurrence."},
    "overture": {"name": "Overture Maps Foundation — places (tourism supply)", "url": "https://overturemaps.org/", "extra": [], "license": "CDLA-Permissive 2.0 / Apache 2.0", "note": "Snapshot of listings, de-duplicated and classified by FPR."},
}


def build(refresh=False):
    names, geoids = hs.municipalities()
    ids = geoids + ["72"]
    idx = {g: i for i, g in enumerate(ids)}
    areas = geoids + ["72000"]
    n = len(ids)
    log("Economy time series")
    values, moes, extras = {}, {}, {}

    def setv(key, year, gid, v, m=None):
        if gid not in idx or v is None:
            return
        values.setdefault(key, {}).setdefault(year, [None] * n)[idx[gid]] = v
        if m is not None:
            moes.setdefault(key, {}).setdefault(year, [None] * n)[idx[gid]] = m

    # QCEW
    years = qcew_years()
    log(f"  QCEW {years[0]}-{years[-1]}: {len(areas)} areas ...")
    sess = requests.Session(); sess.headers.update(UA)
    top = {}
    for y in years:
        for a in areas:
            d = qcew_area(sess, a, y, refresh)
            if not d:
                continue
            gid = "72" if a == "72000" else a
            tot, prv = d.get("o0"), d.get("o5")
            if tot:
                setv("qcew_estabs", y, gid, tot[0]); setv("qcew_jobs", y, gid, tot[1]); setv("qcew_wages", y, gid, tot[2]); setv("qcew_avg_pay", y, gid, tot[3])
            if prv:
                setv("qcew_private_jobs", y, gid, prv[1])
            if tot and prv and tot[1] is not None and prv[1] is not None:
                gov = tot[1] - prv[1]
                setv("qcew_gov_jobs", y, gid, gov); setv("gov_job_share_pct", y, gid, round(gov / tot[1] * 100, 2) if tot[1] else None)
            jobs_total = tot[1] if tot else None
            shares = {}
            for c, label in SECTORS:
                r = d.get(c)
                if r and r[1] is not None:
                    setv(f"jobs_{slug(c)}", y, gid, r[1])
                    shares[label] = r[1]
            for code, key in (("721", "accommodation_jobs"), ("722", "food_service_jobs")):
                if d.get(code) and d[code][1] is not None:
                    setv(key, y, gid, d[code][1])
            food = (d.get("72") or [None, None])[1]
            if food is not None:   # where arts and recreation (71) is withheld, only accommodation and food are counted
                setv("tourism_jobs", y, gid, food + ((d.get("71") or [None, None])[1] or 0))
            if jobs_total and tot and prv and prv[1] is not None:
                gov = jobs_total - prv[1]
                covered = sum(shares.values()) + gov
                if covered / jobs_total >= 0.8:
                    parts = list(shares.values()) + [gov]
                    setv("industry_hhi", y, gid, round(sum((p / jobs_total) ** 2 for p in parts) * 10000))
                allp = dict(shares); allp["Government"] = gov
                if allp:
                    k, v = max(allp.items(), key=lambda kv: kv[1])
                    top.setdefault(str(y), [None] * n)[idx[gid]] = [k, round(v / jobs_total * 100, 1), round(sum(shares.values()) / max(prv[1], 1) * 100)]
    extras["top_sector"] = top

    # LAUS and CPI
    ys = list(range(2010, date.today().year))
    series = []
    for g in geoids:
        series += [f"LAUCN72{g[2:]}0000000003", f"LAUCN72{g[2:]}0000000006"]
    series += ["LASST72" + "0" * 11 + "03", "LASST72" + "0" * 11 + "06"]
    log(f"  LAUS {ys[0]}-{ys[-1]}: {len(series)} series ...")
    laus = bls_all(series, ys[0], ys[-1], refresh)
    cpi = bls_all(["CUUR0000SA0"], 2000, ys[-1], refresh).get("CUUR0000SA0", {})   # back to 2000 so the FEMA declaration years 2001-2009 can be adjusted too
    for g in ids:
        code = "LASST72" + "0" * 11 if g == "72" else f"LAUCN72{g[2:]}00000000"
        for y, rate in laus.get(code + "03", {}).items():
            lf = laus.get(code + "06", {}).get(y)
            setv("laus_unemp_rate", y, g, rate)
            if lf:
                setv("laus_labor_force", y, g, round(lf)); un = round(lf * rate / 100)
                setv("laus_unemployed", y, g, un); setv("laus_employed", y, g, round(lf) - un)

    # ACS
    for y in hs.ACS_YEARS:
        raw = hs.acs_vintage(y, refresh, ECON_TABLES, "acs5econ")
        for gid, rec in raw.items():
            for k, (v, m) in derive_econ(rec).items():
                setv(k, y, gid, v, m)

    # USAspending
    fed = usaspending(geoids, refresh)
    for cat, byfy in fed.items():
        for fy, res in byfy.items():
            for g, v in res.items():
                setv(f"fed_{cat}", fy, "72" if g == "PR" else g, v)   # the territory total includes awards that name no municipality
    for fy in range(2008, last_fy() + 1):
        a = [0.0] * n
        for cat in AWARD_TYPES:
            for g, i in idx.items():
                v = (values.get(f"fed_{cat}", {}).get(fy) or [None] * n)[i]
                if v is not None:
                    a[i] += v
        values.setdefault("fed_awards_total", {})[fy] = [round(x) if x else None for x in a]
    # share of each fiscal year's federal awards that name no municipality (Puerto Rico's total minus the 78 municipalities)
    extras["fed_unplaced_share"] = {}
    for fy, arr in values.get("fed_awards_total", {}).items():
        pr, placed = arr[-1], sum(x for x in arr[:-1] if x is not None)
        if pr and pr > 0:
            extras["fed_unplaced_share"][str(fy)] = round((pr - placed) / pr * 100, 1)
    # FEMA Public Assistance (in total and by damage category) and Hazard Mitigation Assistance
    fema, fx, fnotes = fema_values(names, geoids, refresh)
    for key, byy in fema.items():
        for y, byg in byy.items():
            for g, v in byg.items():
                setv(key, y, g, v)
    # Assistance listings that USAspending places across the municipalities
    prog, px = program_values(geoids, refresh)
    for key, byy in prog.items():
        for y, byg in byy.items():
            for g, v in byg.items():
                setv(key, y, g, v)
    merge_extras(extras, fx)
    merge_extras(extras, px)
    # federal money spent by each municipio government (Federal Audit Clearinghouse)
    fac, facn = fac_values(names, geoids, refresh)
    for key, byy in fac.items():
        for y, byg in byy.items():
            for g, v in byg.items():
                setv(key, y, g, v)
    fnotes.update(facn)
    # investments in low-income communities with New Markets Tax Credits (CDFI Fund)
    nm, nmn = nmtc_values(names, geoids, refresh)
    for key, byy in nm.items():
        for y, byg in byy.items():
            for g, v in byg.items():
                setv(key, y, g, v)
    fnotes.update(nmn)

    # Police Type I crimes
    for key, byy in police_values(names, geoids, refresh).items():
        for y, byg in byy.items():
            for g, v in byg.items():
                setv(key, y, g, v)

    # jobs per employed resident: QCEW jobs at the workplace over ACS employed residents of the same year's window
    for y, a in values.get("qcew_jobs", {}).items():
        w = values.get("workers_16plus", {}).get(y)
        if not w:
            continue
        r = [round(a[i] / w[i], 3) if a[i] and w[i] else None for i in range(n)]
        values.setdefault("jobs_per_employed_resident", {})[y] = r

    # Variables that come from the Housing page series are listed in the catalog so the page can label them, but their values are not copied
    catalog = []
    for key, group, label, unit, d, vtype, srcs, ref, definition, extra in CATALOG:
        if extra.get("from") == "housing":
            catalog.append({"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": vtype, "sources": srcs, "ref": ref, "definition": definition, **extra})
            continue
        if key not in values:
            log(f"  (no data for {key})")
            continue
        yrs = sorted(values[key])
        e = {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": vtype, "sources": srcs, "ref": ref, "definition": definition, **extra, "years": {str(y): values[key][y] for y in yrs}}
        if key in moes:
            e["moe"] = {str(y): moes[key][y] for y in sorted(moes[key])}
        catalog.append(e)
    doc = {"built": str(date.today()), "years": sorted({y for v in values.values() for y in v}), "geo": {"ids": ids, "names": names + ["Puerto Rico"]}, "vars": catalog,
           "deflator": {"cpi": {str(y): v for y, v in sorted(cpi.items())}, "note": "CPI-U, US city average, annual average (1982-84 = 100). It is the US index, not a Puerto Rico index."},
           "sources": SOURCES, "extras": extras,
           "notes": {"qcew_years": f"{years[0]}-{years[-1]}", "fed_last_fy": last_fy(), **fnotes}}
    spending.tag_vars(doc["vars"])   # which money each public-money series measures (spending.py, HANDOFF decision 73)
    path = OUT / "economy_series.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  wrote economy_series.json: {len(catalog)} datasets, {len(doc['years'])} years, {path.stat().st_size / 1e6:.2f} MB")
    return doc


def build_police(refresh=False):
    """Replace only the crime_* series in the published economy_series.json, so a new Police report needs no rebuild of everything else."""
    path = OUT / "economy_series.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    names, geoids = hs.municipalities()
    ids = doc["geo"]["ids"]
    vals = police_values(names, geoids, refresh)
    new = [{"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": vtype, "sources": srcs, "ref": ref, "definition": definition, **extra,
            "years": {str(y): [byg.get(g) for g in ids] for y, byg in sorted(vals[key].items())}}
           for key, group, label, unit, d, vtype, srcs, ref, definition, extra in CATALOG if key in vals]
    keys = {e["key"] for e in new}
    doc["vars"] = [v for v in doc["vars"] if v["key"] not in keys] + new
    doc["years"] = sorted(set(doc["years"]) | {y for k in vals.values() for y in k})
    doc["sources"]["ppr"] = SOURCES["ppr"]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  updated economy_series.json: {len(new)} crime datasets, {path.stat().st_size / 1e6:.2f} MB")


def build_fema(refresh=False):
    """Replace only the FEMA series (Public Assistance and Hazard Mitigation) in the published economy_series.json, from one OpenFEMA download."""
    path = OUT / "economy_series.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    names, geoids = hs.municipalities()
    vals, extras, notes = fema_values(names, geoids, refresh)
    new = replace_series(doc, vals, extras, notes)
    doc["sources"]["openfema"] = SOURCES["openfema"]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  updated economy_series.json: {len(new)} FEMA datasets, {path.stat().st_size / 1e6:.2f} MB")


def build_programs(refresh=False):
    """Replace only the USAspending program series in the published economy_series.json (finished fiscal years are cached; --refresh downloads them again)."""
    path = OUT / "economy_series.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    names, geoids = hs.municipalities()
    vals, extras = program_values(geoids, refresh)
    new = replace_series(doc, vals, extras, {})
    doc["sources"]["usaspending"] = SOURCES["usaspending"]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  updated economy_series.json: {len(new)} program datasets, {path.stat().st_size / 1e6:.2f} MB")


def build_fac(refresh=False):
    """Replace only the Federal Audit Clearinghouse series in the published economy_series.json; --refresh reads the list of audits again and downloads
    the award lines of the fiscal years that have new ones."""
    path = OUT / "economy_series.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    names, geoids = hs.municipalities()
    vals, notes = fac_values(names, geoids, refresh)
    new = replace_series(doc, vals, {}, notes)
    doc["sources"]["fac"] = SOURCES["fac"]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  updated economy_series.json: {len(new)} FAC datasets, {path.stat().st_size / 1e6:.2f} MB")


def build_nmtc(refresh=False):
    """Replace only the New Markets Tax Credit series in the published economy_series.json; --refresh looks for a newer release on the CDFI Fund's page."""
    path = OUT / "economy_series.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    names, geoids = hs.municipalities()
    vals, notes = nmtc_values(names, geoids, refresh)
    new = replace_series(doc, vals, {}, notes)
    doc["sources"]["nmtc"] = SOURCES["nmtc"]
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  updated economy_series.json: {len(new)} NMTC datasets, {path.stat().st_size / 1e6:.2f} MB")


def merge_extras(extras, more):
    """extras.update(more), except that the per-dataset 'statewide_share' maps of the FEMA and program builders are merged, not replaced."""
    for k, v in more.items():
        if k == "statewide_share":
            extras.setdefault(k, {}).update(v)
        else:
            extras[k] = v


def replace_series(doc, vals, extras, notes):
    """Put the CATALOG datasets found in vals into doc (replacing them if present), keeping the order of the catalog; returns the new entries."""
    ids = doc["geo"]["ids"]
    new = [{"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": vtype, "sources": srcs, "ref": ref, "definition": definition, **extra,
            "years": {str(y): [byg.get(g) for g in ids] for y, byg in sorted(vals[key].items())}}
           for key, group, label, unit, d, vtype, srcs, ref, definition, extra in CATALOG if key in vals]
    keys = {e["key"] for e in new}
    order = {c[0]: i for i, c in enumerate(CATALOG)}
    doc["vars"] = sorted([v for v in doc["vars"] if v["key"] not in keys] + new, key=lambda v: order.get(v["key"], len(order)))
    doc["years"] = sorted(set(doc["years"]) | {y for k in vals.values() for y in k})
    merge_extras(doc["extras"], extras)
    doc["notes"].update(notes)
    spending.tag_vars(doc["vars"])
    return new


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    (build_police if "--police" in sys.argv else build_fema if "--fema" in sys.argv else build_programs if "--programs" in sys.argv else build_fac if "--fac" in sys.argv else build_nmtc if "--nmtc" in sys.argv else build)("--refresh" in sys.argv)
