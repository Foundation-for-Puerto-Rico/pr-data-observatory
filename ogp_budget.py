"""The Commonwealth budget for the PR Data Observatory: what the Government of Puerto Rico's agencies spent, were approved and were proposed to spend, by
agency, fund, function and concept of expense, from the Oficina de Gerencia y Presupuesto's data sheets (Public spending PR 3, HANDOFF decision 77).

    python ogp_budget.py              # build site/data/spending_state.json (downloads only the data sheets missing from cache/spending/ogp/)
    python ogp_budget.py --refresh    # read the budget site again and download every data sheet
    python ogp_budget.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: OGP's "Sábana" data sheets (one XLSX per approved and per proposed budget, under docs.pr.gov/files/OGP/), found through the links of
www.presupuestos.pr.gov and its pages for each budget, because the folder names change every year. An earlier budget has its own site, linked from
the home page, and that site holds its sheets itself (presupuesto2025.pr.gov/Sabana_Files/: what was spent in 2023 and approved for 2024). Each sheet has one line per agency, fund, program,
concept and object of expense, in thousands of dollars, and columns such as "Gastado 2024", "Aprobado FY25", "Propuesto 2027". The sheets cover the
agencies in the fiscal plan (agencias integrantes del Plan Fiscal), not the public corporations that run their own budgets (AEE, AAA and others).

Which column is used. Each fiscal year and stage (actual = "Gastado", approved = "Aprobado", proposed = the last "Propuesto" column) comes from the newest
sheet whose lines add up to its own stated total within 0.5%: a newer sheet restates earlier years, but the FY27 approved sheet leaves out lines that
have no FY27 money, so its FY25 and FY26 columns fall short of its totals and are not used. "Solicitado" (what agencies asked for) and "Baseline" columns
are not read. A sheet marked "Privileged & Confidential" is skipped even when it is posted publicly (the draft FY27 proposal of 2026-03-17).

Every line goes through the function crosswalk (dictionary_src/spending_crosswalk.csv, reviewed on 2026-11-09, HANDOFF decision 92; spending.ogp_function), and its
normalized records (spending.FIELDS: level state, fiscal-year basis July to June, island-wide, no municipio) are written to
cache/spending/records/ogp.csv and checked with spending.validate. A new agency or concept code stops the build instead of landing in "other".

output: site/data/spending_state.json. years: the fiscal years present; columns: one per fiscal year and stage, with the sheet it came from and OGP's stated total; agencies: code to name;
funds, concepts, functions: the lists the rows index; rows: [agency code, fund, concept, function, [whole dollars per column]], one row per combination
that has money. Nothing is placed in a municipio: the budget names none.
"""

import csv
import json
import re
import ssl
import sys
import urllib.request
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

import housing_series as hs
import spending
import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "spending" / "ogp"
RECORDS = ROOT / "cache" / "spending" / "records" / "ogp.csv"
OUT = hs.OUT / "spending_state.json"
SITE = "https://www.presupuestos.pr.gov"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
SHEET = re.compile(r"https://docs\.pr\.gov/files/OGP/[^\"'\s?]*Sab[a-z]+[^\"'\s?]*\.xlsx", re.I)
PAGE = re.compile(r"href=\"(/(?:aprobado|presupuestos)-\d\d-\d\d/[a-z0-9-]+)\"", re.I)
OTHER_SITE = re.compile(r"href=\"(https://(?:www\.)?presupuesto[a-z0-9-]*\.pr\.gov/?)\"", re.I)   # earlier budgets have their own sites
LOCAL_SHEET = re.compile(r"href=\"((?!https?:)[^\"?#]*Sab[a-z]+[^\"?#]*\.xlsx)\"", re.I)   # an earlier budget's site links its sheets by a relative address
STAGE = {"gastado": "actual", "aprobado": "approved", "propuesto": "proposed"}
FUNDS = {"fondo general": "general", "fondos especiales": "special", "fondos federales": "federal"}
TOLERANCE = 0.005
TERMS = "Public record of the Government of Puerto Rico (OGP); no license stated"
log = hs.log


def num(v):
    return float(v) if re.match(r"^\s*-?\d[\d.]*(E[+-]?\d+)?\s*$", str(v or ""), re.I) else 0.0


def get(url, timeout=60):
    """(content, Last-Modified) of an address. The 2025 budget's site does not send its intermediate certificate, so the certificate list requests ships
    cannot check it; the operating system's own certificates can, and the second try uses them. Verification is never turned off."""
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        r.raise_for_status()
        return r.content, r.headers.get("Last-Modified", "")
    except requests.exceptions.SSLError:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=ssl.create_default_context()) as r:
            return r.read(), r.headers.get("Last-Modified", "")


def find_sheets():
    """The data-sheet addresses linked from the budget site's home page and its budget pages."""
    home = get(SITE + "/")[0].decode("utf-8", "replace")
    urls = set(SHEET.findall(home))
    pages = [SITE + p for p in sorted(set(PAGE.findall(home)))] + sorted(set(OTHER_SITE.findall(home)))
    for page in pages:
        try:
            text = get(page)[0].decode("utf-8", "replace")
            urls |= set(SHEET.findall(text))
            if not page.startswith(SITE):
                urls |= {urljoin(page, u) for u in LOCAL_SHEET.findall(text)}
        except (requests.RequestException, OSError) as e:
            log(f"  OGP: {page} did not answer ({e.__class__.__name__}); its sheets are skipped this run")
    return sorted(urls)


def sheet_name(url):
    """The cache name of a data sheet: its folder and file under docs.pr.gov/files/OGP/, or its site and path when an earlier budget's site holds it."""
    if "/files/OGP/" in url:
        return url.split("/files/OGP/", 1)[1].replace("/", "__")
    return re.sub(r"^https?://(?:www\.)?", "", url).replace("/", "__")


def fetch(refresh=False):
    """Download the data sheets into cache/spending/ogp/ (named after their folder and file); returns {cache file: (url, Last-Modified)}."""
    CACHE.mkdir(parents=True, exist_ok=True)
    index_p = CACHE / "index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    if refresh or not index:
        for url in find_sheets():
            name = sheet_name(url)
            p = CACHE / name
            if refresh or not p.exists():
                content, modified = get(url, 300)
                p.write_bytes(content)
                log(f"  OGP: {name} ({len(content) / 1e6:.1f} MB)")
                index[name] = [url, modified]
            index.setdefault(name, [url, ""])
        index_p.write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return index


def column_labels(rows, h):
    """For each value column of the sheet whose header is row h: (year, stage or None, OGP's stated total or None)."""
    width = max(i for r in rows[h:h + 3] for i, c in enumerate(r) if c not in (None, "")) + 1
    total_row = next((r for r in rows[h + 1:h + 6] if str(r[0] or "").strip().lower().startswith("total")), None)
    out = {}
    for j in range(5, width):
        words = " ".join(str(rows[k][j] or "") for k in range(max(0, h - 1), h + 3))
        fy = re.search(r"\bFY ?(\d\d)\b", words)   # "Aprobado FY25"; otherwise the latest year named ("Propuesto March 3, 2025 2026": the 2026 budget)
        years = [int(x) for x in re.findall(r"(?<!\d)(20\d\d)(?!\d)", words)]
        year = 2000 + int(fy.group(1)) if fy else max(years) if years else None
        st = next((s for w, s in STAGE.items() if w in words.lower()), None)
        stated = num(total_row[j]) if total_row else next((num(rows[k][j]) for k in range(max(0, h - 1), h) if num(rows[k][j]) > 1e6), None)
        out[j] = (year, st, stated or None)
    return out


def read_sheet(path):
    """(lines, columns, note) of one data sheet: lines are dicts of codes and names with the values of every column; columns maps the column index to
    (year, stage, stated total). A sheet marked privileged gives no lines."""
    rows = [[r.get(j) for j in range(16)] for r in xlsx_read.rows(path.read_bytes())]
    if any("privileged" in str(c).lower() for r in rows[:12] for c in r if c):
        return [], {}, "marked Privileged & Confidential: not read"
    h = next(i for i, r in enumerate(rows) if str(r[0] or "").strip().lower().startswith("agencia"))
    cols = column_labels(rows, h)
    lines = []
    for r in rows[h + 1:]:
        obj = re.search(r"E\d{4}", str(r[4] or ""))
        if not obj:
            continue
        ag = re.match(r"\s*[A-Z]?(\d{3})(?:-\d{3})?[:\s]\s*(.*)", str(r[0]))   # "B045-021:" is a bureau of agency 045
        pr = re.match(r"\s*P(\d{4})\d*[:\-]\s*(.*)", str(r[2]))
        co = re.match(r"\s*[AC](\d{3})[:\-]\s*(.*)", str(r[3]))
        fund = next((v for k, v in FUNDS.items() if k in str(r[1]).lower()), None)
        if not (ag and pr and co and fund):
            raise ValueError(f"{path.name}: a line the reader cannot parse: {r[:5]}")
        lines.append({"agency": ag.group(1), "agency_name": ag.group(2).strip(), "program": pr.group(1),
                      "program_name": re.sub(r"\s+\d{4}\s+-\s+Otros Serv.*$", "", pr.group(2)).strip(), "concept": co.group(1), "object": obj.group(),
                      "fund": fund, "values": {j: num(r[j]) * 1000 for j in cols}})
    return lines, cols, ""


def order(name, modified):
    """Newest first: the budget's fiscal year from the folder, an approved budget after the proposal of the same year, then the server's date."""
    y = re.search(r"(\d{4})-(\d{4})", name)
    site = re.match(r"presupuesto(\d{4})\.", name)   # "presupuesto2025.pr.gov__Sabana_Files__...": the 2025 budget's own site
    when = parsedate_to_datetime(modified).timestamp() if modified else 0
    return (int(y.group(2)) if y else int(site.group(1)) if site else 0, name.lower().startswith(("aprobado", "presupuestoaprobado")), when)


def select(index):
    """{(year, stage): (cache name, column index, stated total, the lines)} from the newest sheet whose lines add up to its total; and the log of choices."""
    chosen, notes = {}, []
    for name in sorted(index, key=lambda n: order(n, index[n][1]), reverse=True):
        lines, cols, note = read_sheet(CACHE / name)
        if note:
            notes.append(f"{name}: {note}")
            continue
        last_proposed = max((j for j, (y, s, _) in cols.items() if s == "proposed"), default=None)
        for j, (year, stage, stated) in cols.items():
            if not (year and stage) or (stage == "proposed" and j != last_proposed):
                continue
            got = sum(l["values"][j] for l in lines)
            if not stated or abs(got - stated * 1000) > TOLERANCE * stated * 1000:
                notes.append(f"{name}: {stage} {year} not used (lines add up to {got / 1e9:.3f} B, the sheet says {stated * 1000 / 1e9 if stated else float('nan'):.3f} B)")
                continue
            if (year, stage) in chosen:
                notes.append(f"{name}: {stage} {year} also here ({got / 1e9:.3f} B); the newer sheet's column is used")
                continue
            chosen[(year, stage)] = (name, j, stated * 1000, lines)
    return chosen, notes


def build(refresh=False, check=False):
    index = fetch(refresh and not check)
    chosen, notes = select(index)
    cw = spending.load_crosswalk()
    agencies, agg, records = {}, {}, []
    keys = sorted(chosen)
    basis = [[0.0] * len(spending.BASES) for _ in keys]   # decision 109, step 4: where each column's money takes its function from
    last = max((k for k in keys if k[1] == "approved"), default=None)
    by_agency = {}
    retrieved = date.today().isoformat()
    for ci, key in enumerate(keys):
        name, j, stated, lines = chosen[key]
        url = index[name][0]
        for l in lines:
            v = l["values"][j]
            if not v:
                continue
            fn, concept, alloc, conf = spending.ogp_function(l["agency"], l["program"], l["concept"], l["object"], cw=cw, fund=l["fund"], year=key[0])
            agencies.setdefault(l["agency"], l["agency_name"])
            b = spending.ogp_basis(l["agency"], l["program"], l["concept"], l["object"], cw=cw, fund=l["fund"], year=key[0])
            basis[ci][spending.BASES.index(b)] += v
            if key == last:
                e = by_agency.setdefault(l["agency"], {"total": 0.0, "agency": 0.0, "fns": set()})
                e["total"] += v
                if b == "agency":
                    e["agency"] += v
                if b != "concept":
                    e["fns"].add(fn)
            k = (l["agency"], l["fund"], concept, fn)
            agg.setdefault(k, [0.0] * len(keys))[ci] += v
            records.append({"municipio_fips": "", "fiscal_year": key[0], "fiscal_year_basis": "pr_jul_jun", "level": "state", "source_system": "ogp",
                            "stage": key[1], "fund_origin": l["fund"], "agency_or_entity": f"{l['agency']} {l['agency_name']}",
                            "program": f"{l['program']} {l['program_name']}", "function_category": fn, "concept_of_expense": concept,
                            "recipient_type": "agency", "allocation_tier": "island_wide", "allocation_driver": "", "allocation_confidence": "high",
                            "amount_usd": round(v), "population_basis": "", "per_capita_usd": "", "dedup_group": "ogp_federal" if l["fund"] == "federal" else "",
                            "retrieved_at": retrieved, "source_url": url, "terms_of_use": TERMS})
    bad = [p for r in records[:2000] for p in spending.validate({k: str(v) for k, v in r.items()})]
    if bad:
        raise ValueError(f"records fail the schema: {bad[:5]}")
    funds, concepts, functions = list(FUNDS.values()), spending.CONCEPTS, spending.FUNCTIONS
    rows = sorted([[a, funds.index(f), concepts.index(c), functions.index(fn), [round(x) for x in vals]] for (a, f, c, fn), vals in agg.items()],
                  key=lambda r: (r[0], r[1], r[2], r[3]))
    doc = {"version": 1, "built": retrieved, "source": "ogp", "unit": "USD", "level": "state", "fiscal_year_basis": "pr_jul_jun",
           "crosswalk": "reviewed 2026-11-09 (dictionary_src/spending_crosswalk.csv, HANDOFF decisions 76 and 92)", "years": sorted({y for y, _ in keys}),
           "columns": [{"year": y, "stage": s, "sheet": chosen[(y, s)][0].replace("__", "/"), "stated_total": round(chosen[(y, s)][2]),
                        "total": round(sum(r[4][i] for r in rows))} for i, (y, s) in enumerate(keys)],
           "agencies": dict(sorted(agencies.items())), "funds": funds, "concepts": concepts, "functions": functions, "rows": rows,
           "notes": notes,
           "basis": {"kinds": spending.BASES, "by_column": [[round(x) for x in c] for c in basis], "column": keys.index(last) if last else None,
                     "agencies": sorted([[a, round(e["total"]), round(e["agency"]), len(e["fns"]), functions.index(cw[("ogp_agency", a)]["function_category"])]
                                         for a, e in by_agency.items() if round(e["total"])], key=lambda r: -r[1])}}
    for c in doc["columns"]:
        if abs(c["total"] - c["stated_total"]) > TOLERANCE * c["stated_total"]:
            raise ValueError(f"{c['stage']} {c['year']}: published total {c['total']} is not OGP's {c['stated_total']}")
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_state.json {'is current' if same else 'differs from the cache: run python ogp_budget.py'}")
        return same
    OUT.write_text(text, encoding="utf-8")
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORDS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spending.FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(records)
    for c in doc["columns"]:
        log(f"  {c['stage']:8s} FY{c['year']}: ${c['total'] / 1e9:6.2f} B (OGP {c['stated_total'] / 1e9:.2f} B) from {c['sheet']}")
    log(f"  wrote spending_state.json: {len(rows)} rows, {len(agencies)} agencies, {OUT.stat().st_size / 1e3:.0f} KB; {len(records)} records in {RECORDS.name}")
    return doc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        sys.exit(0 if build(check=True) else 1)
    build(refresh="--refresh" in argv)


if __name__ == "__main__":
    main()
