"""Capital projects by municipio for the PR Data Observatory: the Junta de Planificación's Four-Year Investment Program (Programa de Inversiones de Cuatro
Años, PICA), the recommended capital improvements of the agencies and public corporations, project by project, with the municipio of each (Public
spending PR 5, HANDOFF decision 79).

    python pica.py              # build site/data/spending_pica.json (downloads only what is missing from cache/spending/pica/)
    python pica.py --refresh    # read the Planning Board's home page again and download the newest adopted program
    python pica.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the adopted PICA (PDF) linked from jp.pr.gov ("...PICA-<years>-Adoptado....pdf"). A draft for public hearing (Borrador para vista pública) is
not used. The text is read with pdftotext -raw (poppler), so this script runs where poppler is installed, not on the clean CI runner (refresh unit "spending-pica",
where: local).

How a project line is read. Each agency's table (Tabla 3 onward, until Apéndice A) has one line per project: description, municipio, type of project (Construcción,
Rehabilitación...) and the four fiscal years and their total, in thousands of dollars. A line counts only when its four years add up to its total. The municipio is
the name right before the type (muni_names.municipio_id); "Varios", "Región Metro" and similar are not placed in a municipio, and kept as such. Tables are
assigned by page, because pdftotext can print a page's rows before its "Tabla" header. The program's stated total ("asciende a $X miles") checks the sum: the
build stops if the lines found add up to less than 99% of it, and the gap is published (gap_usd).

Output: site/data/spending_pica.json. years: the program's fiscal years (July to June, named by the year they end); agencies: [name, function]; geo.ids: the 78
municipios; by_muni: dollars per municipio for each year (arrays in geo.ids order); by_agency: for each agency, its dollars per municipio over the whole program
and its unplaced dollars; unplaced: dollars per year not placed in a municipio (several municipios, a region, the whole island, or not defined); population:
the Census Bureau's 2025 estimate per municipio (per resident); lines and placed_lines: project rows read and placed (a line split among several
municipios counts once for each); stated_total_usd and gap_usd. Project names are not published.
"""

import csv
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import muni_names
import spending

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "spending" / "pica"
RECORDS = ROOT / "cache" / "spending" / "records" / "pica.csv"
OUT = hs.OUT / "spending_pica.json"
HOME = "https://jp.pr.gov/"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
LINK = re.compile(r"href=\"(https://docs\.pr\.gov/files/[^\"]*PICA[^\"]*Adoptado[^\"]*\.pdf)\"", re.I)
NUM = r"-?\d{1,3}(?:,\d{3})*"
TIPO = (r"(Nueva construcci.n|Construcci.n|Rehabilitaci.n|Reconstrucci.n|Remodelaci.n|Restauraci.n|Mejoras?|Dise.o|Reparaci.n|Adquisici.n|"
        r"Mitigaci.n|Demolici.n|Ampliaci.n|Desarrollo de solares)")
ROW = re.compile(rf"^(.*?)\s*{TIPO}\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s*$", re.I)
UNPLACED = re.compile(r"(\(?varios\)?|todos|toda la isla|isla|regi.n( (metro|norte|sur|este|oeste|central))?|no definido|puerto rico|m.ltiples?|islas)\s*$", re.I)
# Each table's agency and its function (dictionary_src/spending_crosswalk.csv for those with an OGP code; the public corporations have none)
AGENCY = [
    (r"Edificios P.blicos", "Autoridad de Edificios Públicos", "general_government", "162"),
    (r"Ciencias Forenses", "Instituto de Ciencias Forenses", "public_safety", "189"),
    (r"Universidad de Puerto Rico", "Universidad de Puerto Rico", "education", "176"),
    (r"Departamento de Educaci.n", "Departamento de Educación", "education", "081"),
    (r"Departamento de Salud", "Departamento de Salud", "health", "071"),
    (r"Servicios M.dicos", "Administración de Servicios Médicos de Puerto Rico", "health", "090"),
    (r"Acueductos y Alcantarillados", "Autoridad de Acueductos y Alcantarillados", "utilities_energy", ""),
    (r"Vivienda P.blica", "Administración de Vivienda Pública", "housing", "106"),
    (r"Pen.nsula de Cantera", "Compañía para el Desarrollo Integral de la Península de Cantera", "housing", "167"),
    (r"ENLACE", "Corporación del Proyecto ENLACE del Caño Martín Peña", "housing", "264"),
    (r"Carreteras y Transportaci.n", "Autoridad de Carreteras y Transportación", "transportation", ""),
    (r"Metropolitana de Autobuses", "Autoridad Metropolitana de Autobuses", "transportation", ""),
    (r"Comercio y Exportaci.n", "Compañía de Comercio y Exportación de Puerto Rico", "economic_development", ""),
]
TOLERANCE = 0.01
log = hs.log


def agency_of(header):
    for pat, name, fn, code in AGENCY:
        if re.search(pat, header, re.I):
            return name, fn
    raise ValueError(f"PICA: a table for an agency the script does not know: {header!r} (add it to AGENCY with its function)")


def fetch(refresh=False):
    """The adopted program's PDF and its text (pdftotext -raw) in cache/spending/pica/; returns (pdf path, url)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = CACHE / "source.json"
    if refresh or not meta.exists():
        found = LINK.findall(requests.get(HOME, headers=UA, timeout=60).text)
        if not found:
            raise RuntimeError("PICA: the Planning Board's home page links no adopted program (…PICA…Adoptado….pdf); look at jp.pr.gov")
        url = sorted(set(found))[-1]
        meta.write_text(json.dumps({"url": url, "checked": date.today().isoformat()}, indent=1), encoding="utf-8")
    url = json.loads(meta.read_text(encoding="utf-8"))["url"]
    pdf = CACHE / re.sub(r"[^A-Za-z0-9._-]+", "_", requests.utils.unquote(url.rsplit("/", 1)[1]))
    if refresh or not pdf.exists():
        r = requests.get(url, headers=UA, timeout=300)
        r.raise_for_status()
        pdf.write_bytes(r.content)
        log(f"  PICA: {pdf.name} ({len(r.content) / 1e6:.1f} MB)")
    txt = pdf.with_suffix(".txt")
    if not txt.exists() or txt.stat().st_mtime < pdf.stat().st_mtime:
        exe = shutil.which("pdftotext")
        if not exe:
            raise RuntimeError("PICA: pdftotext (poppler) is needed to read the program")
        subprocess.run([exe, "-raw", str(pdf), str(txt)], check=True)
    return txt, url


def municipios_named(pre):
    """The municipios a project line names right before its type: the last words of the description ("... Microgrid Caguas, PR (FEMA-406). Caguas"),
    and any municipios listed before them, separated by commas or "y" ("Adjuntas, Utuado")."""
    segs = [x for x in re.split(r",\s*|\s+y\s+", pre) if x.strip()]
    found = []
    for i, seg in enumerate(reversed(segs)):
        g = muni_names.municipio_id(seg)
        if not g and i == 0:
            toks = seg.split()
            g = next((muni_names.municipio_id(" ".join(toks[-k:])) for k in range(min(4, len(toks)), 0, -1) if muni_names.municipio_id(" ".join(toks[-k:]))), None)
            if g:
                found.append(g)
                break   # the description ends in one municipio: what comes before is the description
        if not g:
            break
        found.append(g)
    return list(dict.fromkeys(reversed(found)))


def parse(text):
    """(rows, fiscal years, stated total in dollars) from the program's text: rows are (agency, function, geoid or None, [dollars per year]); a line for several municipios gives one row for each, split equally."""
    head = re.search(r"Programa de Inversiones de Cuatro A.os (\d{4})-(\d{4}) a (\d{4})-(\d{4})", text)
    first = int(head.group(2))
    years = list(range(first, first + 4))
    stated = re.search(r"cuatrienio\s+(?:de\s+)?\d{4}-\d{4}\s+a\s+\d{4}-\d{4}\s+asciende\s+a\s+\$?\s*(" + NUM + r")\s+miles", text)
    stated = int(stated.group(1).replace(",", "")) * 1000 if stated else None
    body = re.split(r"AP.NDICE A\s*\n", text)[0]
    rows, agency, prev = [], None, ""
    for page in body.split("\x0c"):
        t = re.search(r"Tabla\s*(\d+)\s*:\s*(.+)", page)
        if t:
            agency = agency_of(t.group(2)) if int(t.group(1)) >= 3 else None
        if not agency:
            continue
        for ln in page.split("\n"):
            ln = ln.strip()
            m = ROW.match(ln)
            if not m:
                prev = ln
                continue
            pre = m.group(1).strip()
            v = [int(x.replace(",", "")) * 1000 for x in m.groups()[2:]]
            if sum(v[:4]) != v[4]:
                prev = ln
                continue
            places = municipios_named(pre) or ([muni_names.municipio_id(prev)] if not pre and muni_names.municipio_id(prev) else [])
            # a line that names several municipios ("Adjuntas, Utuado") is split equally among them, as Hazard Mitigation is (decision 66)
            for g in places or [None]:
                rows.append((agency[0], agency[1], g, [x / len(places or [None]) for x in v[:4]]))
            prev = ln
    return rows, years, stated


def build(refresh=False, check=False):
    txt, url = fetch(refresh and not check)
    rows, years, stated = parse(txt.read_text(encoding="latin-1"))
    total = round(sum(sum(r[3]) for r in rows))
    if stated and total < (1 - TOLERANCE) * stated:
        raise ValueError(f"PICA: the project lines add up to ${total / 1e9:.3f} B, less than 99% of the program's ${stated / 1e9:.3f} B")
    names, ids = hs.municipalities()
    at = {g: i for i, g in enumerate(ids)}
    by_muni = [[0] * len(ids) for _ in years]
    unplaced = [0] * len(years)
    agencies, by_agency = [], {}
    for name, fn, g, v in rows:
        if name not in by_agency:
            agencies.append([name, fn])
            by_agency[name] = {"muni": [0] * len(ids), "unplaced": 0}
        for yi, x in enumerate(v):
            if g in at:
                by_muni[yi][at[g]] += x
                by_agency[name]["muni"][at[g]] += x
            else:
                unplaced[yi] += x
                by_agency[name]["unplaced"] += x
    pop = population(ids)
    placed = round(sum(map(sum, by_muni)))
    doc = {"version": 1, "built": date.today().isoformat(), "source": "jp_pica", "unit": "USD", "level": "state", "fiscal_year_basis": "pr_jul_jun",
           "stage": "proposed", "program": f"{years[0] - 1}-{years[0]} a {years[-1] - 1}-{years[-1]}", "years": years, "source_url": url,
           "geo": {"ids": ids, "names": names}, "agencies": agencies,
           "by_muni": [[round(x) for x in yr] for yr in by_muni], "unplaced": [round(x) for x in unplaced],
           "by_agency": [[a, [round(x) for x in by_agency[a]["muni"]], round(by_agency[a]["unplaced"])] for a, _ in agencies],
           "population": pop, "population_basis": "Census Bureau Population Estimates, July 1 2025",
           "lines": len(rows), "placed_lines": sum(1 for r in rows if r[2] in at),
           "total_usd": total, "placed_usd": placed, "stated_total_usd": stated, "gap_usd": (stated - total) if stated else None}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(text).items() if k != "built"}
        log(f"  spending_pica.json {'is current' if same else 'differs from the cache: run python pica.py'}")
        return same
    OUT.write_text(text, encoding="utf-8")
    write_records(rows, years, url, at)
    log(f"  PICA {doc['program']}: {len(rows)} project lines, ${total / 1e9:.2f} B of ${(stated or 0) / 1e9:.2f} B stated; "
        f"{doc['placed_lines']} lines (${placed / 1e9:.2f} B) placed in {sum(1 for i in range(len(ids)) if any(by_muni[y][i] for y in range(len(years))))} municipios")
    log(f"  wrote spending_pica.json, {OUT.stat().st_size / 1e3:.0f} KB")
    return doc


def population(ids):
    """The Census Bureau's 2025 estimate per municipio, from the Housing page's population series (the per-resident basis of docs/spending.md)."""
    d = json.loads((hs.OUT / "housing_series.json").read_text(encoding="utf-8"))
    v = next(x for x in d["vars"] if x["key"] == "population")
    order = d["geo"]["ids"]
    vals = v["years"]["2025"]
    by = dict(zip(order, vals))
    return [by.get(g) for g in ids]


def write_records(rows, years, url, at):
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    with open(RECORDS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spending.FIELDS), lineterminator="\n")
        w.writeheader()
        for name, fn, g, v in rows:
            for yi, x in enumerate(v):
                if not x:
                    continue
                placed = g in at
                w.writerow({"municipio_fips": g if placed else "", "fiscal_year": years[yi], "fiscal_year_basis": "pr_jul_jun", "level": "state",
                            "source_system": "jp_pica", "stage": "proposed", "fund_origin": "bond_other", "agency_or_entity": name, "program": "",
                            "function_category": fn, "concept_of_expense": "capex", "recipient_type": "agency",
                            "allocation_tier": "direct" if placed else "island_wide", "allocation_driver": "", "allocation_confidence": "high",
                            "amount_usd": round(x), "population_basis": "", "per_capita_usd": "", "dedup_group": "", "retrieved_at": today, "source_url": url,
                            "terms_of_use": "Public record of the Government of Puerto Rico (Junta de Planificación); no licence stated"})


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        sys.exit(0 if build(check=True) else 1)
    build(refresh="--refresh" in argv)


if __name__ == "__main__":
    main()
