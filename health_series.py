"""Health-care access for the PR Data Observatory: the federally funded health centers and the federal shortage-area designations, for the 78 municipalities and Puerto Rico.

    python health_series.py             # build site/data/health_series.json (downloads only what is missing)
    python health_series.py --refresh   # download the HRSA files again
    python health_series.py --check     # rebuild from the cached rows and exit 1 when site/data/health_series.json is not what they give (no network, nothing written; no cache, nothing to check)

Source, no key, US federal data: the HRSA Data Warehouse downloads (https://data.hrsa.gov/data/download). The download page lists "Usage limitations: None" for each
file used here, and Data.gov lists the sites file and the three shortage-area files as CC0 1.0 (docs/health.md). Four files are read:
  Health_Center_Service_Delivery_and_LookAlike_Sites   the sites of health centers that hold a federal grant (FQHC) or look-alike status, with the county that holds each one
  BCD_HPSA_FCT_DET_PC / _DH / _MH                      Health Professional Shortage Area (HPSA) designations for primary care, dental health and mental health: a priority
                                                       score, the practitioners in place (FTE) and the practitioners still needed to end the designation ("shortage")
The Area Health Resources File (AHRF) is NOT used: its documentation does not authorize re-use without the Bureau's permission (docs/health.md).

What is kept. Each file is read as a stream and only the Puerto Rico rows, and only the columns listed in FILES below, are written to cache/hrsa/<key>.pr.csv. Names, addresses,
telephone numbers, web addresses and coordinates are dropped as each row is read: they never reach the cache or the output, which holds counts and figures for each municipality only.

How a municipality's figures are made (docs/health.md has the reasons and the checks):
  hc_sites, hc_vans   active sites that deliver care (a "Service Delivery Site", or an "Administrative/Service Delivery Site"), split into permanent sites and mobile vans;
                      administrative-only buildings are left out. A municipality with none has a true zero.
  hpsa_*_score        the highest HPSA score among the municipality's designated area-level HPSAs (a geographic area, a population group or a high-needs area)
  hpsa_*_short        practitioners (FTE) still needed to end that designation; HRSA's own total for Puerto Rico is within 1.1% of the sum of these (with the correctional facility it includes)
  hpsa_*_met          "percent of need met" = FTE in place / (FTE in place + shortage), HRSA's definition (it reproduces HRSA's published Puerto Rico figures to 0.1 point)
  The build stops, and publishes nothing, when a value HRSA could rename ("Active", "Designated") is missing or a count is implausibly small, and when the four files were not made on one day.
  A municipality with no area-level designation has no value (None), never a zero. The facility designations (health centers, which are designated by law, and the correctional
  facility) are left out of the municipal figures. Every designation holds one row in Puerto Rico today; if one ever spans two rows of a municipality the build keeps the
  highest score and the designation with the largest shortage (the groups overlap, so they are not added) and says so in notes.hpsa_overlaps. One that spans two municipalities stops
  the build: there is no honest way to split it.

Output: {"built", "as_of", "years": [year], "geo": {"ids", "names"}, "vars": [...], "sources": {...}, "notes": {...}}, arrays indexed like geo.names (the last entry is Puerto Rico),
the shape of economy_series.json, with one snapshot year.
"""

import csv
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "hrsa"
OUT = hs.OUT / "health_series.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
BASE = "https://data.hrsa.gov/DataDownload/DD_Files/"
log = hs.log

# The columns kept from each file (everything else, names and addresses included, is dropped as the file streams in) and the test for a Puerto Rico row.
CREATED = "Data Warehouse Record Create Date"
FILES = {
    "sites": {
        "file": "Health_Center_Service_Delivery_and_LookAlike_Sites.csv",
        "keep": ["Site State Abbreviation", "Site Status Description", "Health Center Type", "Health Center Type Description", "Health Center Location Type Description",
                 "State and County Federal Information Processing Standard Code", CREATED],
        "is_pr": lambda r: r["Site State Abbreviation"] == "PR",
    },
    **{k: {
        "file": f"BCD_HPSA_FCT_DET_{k[-2:].upper()}.csv",
        "keep": ["HPSA ID", "HPSA Discipline Class", "HPSA Status", "Designation Type", "HPSA Score", "HPSA FTE", "HPSA Shortage", "HPSA Designation Population", "Provider Type",
                 "HPSA Population Type", "HPSA Designation Date", "HPSA Designation Last Update Date", "Primary State Abbreviation", "Common State Abbreviation", "Common State County FIPS Code", CREATED],
        "is_pr": lambda r: r["Primary State Abbreviation"] == "PR" or r["Common State Abbreviation"] == "PR",
    } for k in ("hpsa_pc", "hpsa_dh", "hpsa_mh")},
}
COUNTY = "State and County Federal Information Processing Standard Code"
HPSA_COUNTY = "Common State County FIPS Code"
# key, HRSA discipline class, group name, who is counted, the three labels, and the top of HRSA's score range (primary care 0 to 25, dental 0 to 26, mental health 0 to 25)
DISCIPLINES = [("pc", "Primary Care", "Primary care", "primary care physicians", "Primary care physicians still needed, full-time equivalents (shortage areas)", "Primary care physicians in place (% of the need)", "Primary care shortage priority score", 25),
               ("dh", "Dental Health", "Dental", "dentists", "Dentists still needed, full-time equivalents (shortage areas)", "Dentists in place (% of the need)", "Dental shortage priority score", 26),
               ("mh", "Mental Health", "Mental health", "psychiatrists (every mental health designation of Puerto Rico counts psychiatrists only)", "Psychiatrists still needed, full-time equivalents (shortage areas)", "Psychiatrists in place (% of the need)", "Mental health shortage priority score", 25)]
RATIO = {"pc": "That is 3,000 people for each physician, the goal that HRSA's file states for these designations, so reaching it would end the designation.",
         "dh": "That is 4,000 people for each dentist, the goal that HRSA's file states for these designations, so reaching it would end the designation.",
         "mh": "That is about 15,000 people for each psychiatrist, although HRSA's file states a goal of 20,000 for these designations: HRSA's figure is more than it would take to reach that goal, and the observatory publishes it as HRSA gives it."}
FLOORS = {"permanent": 50, "municipios_with_a_site": 30, "vans": 5, "pc": 8, "dh": 30, "mh": 20}   # fewer than these in the real files means HRSA renamed a value (the 2026-10 files give 127, 70, 33 vans, 20, 77 and 52)
JENKS = {k: {"classes": "jenks"} for k in ("hpsa_pc_met", "hpsa_mh_met", "hpsa_dh_score", "hpsa_mh_score")}   # the legends that quantiles leave with empty or repeated classes (6 of the 20 primary care and 44 of the 52 mental health figures are 0; the dental and mental health scores take few values)
AREA_TYPES = {"Geographic HPSA", "HPSA Population", "High Needs Geographic HPSA"}   # the other types are facilities: health centers (designated by law) and correctional facilities
DESIGNATED = {"Designated", "Proposed For Withdrawal"}   # HRSA counts a designation proposed for withdrawal until the Federal Register notice is published
KNOWN_LOCATIONS = {"Permanent", "Mobile Van", "Seasonal", "Unknown"}   # the location types of a site that the build has seen or HRSA documents: another one may be a renamed "Mobile Van"
SERVICE_SITE = "Service Delivery"   # in "Service Delivery Site" and "Administrative/Service Delivery Site"; "Administrative" alone delivers no care

SOURCES = {
    "hrsa_sites": {"name": "HRSA — Health Center Service Delivery and Look-Alike Sites (Data Warehouse download)", "url": "https://data.hrsa.gov/data/download",
                   "license": "CC0 1.0 (public domain) as Data.gov lists the file (its Excel version); HRSA's download page lists no usage limitations. Treated as open; HRSA has not confirmed the terms",
                   "note": "Sites of health centers that hold a federal grant (FQHC) or look-alike status, with the county of each site. The observatory publishes counts for each municipality, never the names, addresses or coordinates."},
    "hrsa_hpsa": {"name": "HRSA — Health Professional Shortage Area (HPSA) designations (Data Warehouse download)", "url": "https://data.hrsa.gov/data/download",
                  "license": "CC0 1.0 (public domain) as Data.gov lists these files, with an access level \"restricted public\" that contradicts it; HRSA's download page lists no usage limitations. Treated as open; HRSA has not confirmed the terms",
                  "note": "Primary care, dental health and mental health designations. The observatory publishes the area-level designations of each municipality: the priority score, the practitioners still needed and the share of need met."},
}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def day(s):
    """A date from the HRSA files, which write it as 10/06/2026 or as 2026-10-06 01:21:58.100."""
    s = (s or "").strip()
    for fmt, n in (("%m/%d/%Y", 10), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:n], fmt).date()
        except ValueError:
            pass
    return None


# ── Download and cache ───────────────────────────────────────────────────────

def pr_rows(key, refresh=False, offline=False):
    """The kept columns of the Puerto Rico rows of one HRSA file, from the cache or, when it is missing or refresh is set, streamed from data.hrsa.gov."""
    spec, path = FILES[key], CACHE / f"{key}.pr.csv"
    if offline and not path.exists():
        raise SystemExit(f"health_series --check: {path.name} is not in the cache, so there is nothing to check (python health_series.py makes it; --check never downloads)")
    if path.exists() and not refresh:
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if scrub(key, rows) and not offline:   # a cache made before the facility IDs were blanked
            write_cache(path, spec, rows)
        return rows
    url = BASE + spec["file"]
    log(f"  downloading {url}")
    with requests.get(url, headers=UA, stream=True, timeout=(30, 300)) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        rd = csv.DictReader(io.TextIOWrapper(r.raw, encoding="utf-8-sig", errors="replace", newline=""))
        need = set(spec["keep"]) | {"Primary State Abbreviation", "Common State Abbreviation"} if key != "sites" else set(spec["keep"])
        missing = sorted(need - set(rd.fieldnames or []))
        if missing:
            raise SystemExit(f"health_series: {spec['file']} has no column {missing}: HRSA changed the layout of the file; read its metadata before going on")
        total, rows = 0, []
        for row in rd:
            total += 1
            if spec["is_pr"](row):
                rows.append({c: row[c] for c in spec["keep"]})
    if not rows:
        raise SystemExit(f"health_series: no Puerto Rico row in {spec['file']} ({total} rows read)")
    scrub(key, rows)
    write_cache(path, spec, rows)
    log(f"  kept {len(rows)} of {total} rows")
    return rows


def scrub(key, rows):
    """The HPSA ID of a facility designation (a health center, a correctional facility) names one facility, so it is blanked before the row is stored. The ID of an area designation is kept (one for each designation, used to check
    that none covers two municipalities). True when a row had to be changed."""
    changed = False
    if key.startswith("hpsa_"):
        for r in rows:
            if r["Designation Type"] not in AREA_TYPES and r["HPSA ID"]:
                r["HPSA ID"] = ""
                changed = True
    return changed


def write_cache(path, spec, rows):
    CACHE.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=spec["keep"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ── Aggregation ──────────────────────────────────────────────────────────────

def sites(rows, ids):
    """Permanent sites and mobile vans for each municipality: active sites that deliver care."""
    perm, van, skipped = Counter(), Counter(), Counter()
    for r in rows:
        if r["Site Status Description"] != "Active" or SERVICE_SITE not in r["Health Center Type Description"]:
            skipped["not an active site that delivers care"] += 1
            continue
        fips = r[COUNTY]
        if fips not in ids:
            raise SystemExit(f"health_series: a health center site has the county code {fips!r}, which is not one of the 78 municipalities")
        kind = r["Health Center Location Type Description"]
        if kind == "Permanent":
            perm[fips] += 1
        elif kind == "Mobile Van":
            van[fips] += 1
        else:
            skipped[f"location type {kind}"] += 1
    return perm, van, skipped


def hpsa(rows, ids, discipline):
    """{fips: (score, fte, shortage)} for the designated area-level HPSAs of one discipline, with how many rows each municipality had and what was left out."""
    seen = Counter(r["HPSA Status"] for r in rows)
    area, facility, other = [], 0, 0
    for r in rows:
        if r["HPSA Discipline Class"] != discipline:
            raise SystemExit(f"health_series: a row of the {discipline} file says {r['HPSA Discipline Class']!r}")
        if r["HPSA Status"] not in DESIGNATED:
            other += 1
        elif r["Designation Type"] in AREA_TYPES:
            area.append(r)
        else:
            facility += 1
    if len({r["HPSA ID"] for r in area}) != len(area):
        raise SystemExit("health_series: one HPSA appears in more than one row of its file, so it covers more than one municipality; the build does not split a designation")
    by = defaultdict(list)
    for r in area:
        fips = r[HPSA_COUNTY]
        if fips not in ids:
            raise SystemExit(f"health_series: an HPSA has the county code {fips!r}, which is not one of the 78 municipalities")
        if not r["HPSA Score"].strip().isdigit() or num(r["HPSA Shortage"]) is None or num(r["HPSA FTE"]) is None:
            raise SystemExit(f"health_series: the HPSA {r['HPSA ID']} has no score, FTE or shortage: look at the row before publishing it")
        by[fips].append(r)
    out, overlaps = {}, 0
    for fips, rs in by.items():
        lead = max(rs, key=lambda r: num(r["HPSA Shortage"]))
        overlaps += len(rs) > 1
        out[fips] = (max(int(r["HPSA Score"]) for r in rs), num(lead["HPSA FTE"]), num(lead["HPSA Shortage"]))
    types = Counter(r["Provider Type"] for r in area)
    facility_rows = [r for r in rows if r["HPSA Status"] in DESIGNATED and r["Designation Type"] not in AREA_TYPES]
    facility_set = {r[HPSA_COUNTY] for r in facility_rows} - set(by)
    facility_only = len(facility_set)
    facility_only_correctional = len({f for f in facility_set if all(r["Designation Type"] == "Correctional Facility" for r in facility_rows if r[HPSA_COUNTY] == f)})
    withdrawn_area = {r[HPSA_COUNTY] for r in rows if r["HPSA Status"] not in DESIGNATED and r["Designation Type"] in AREA_TYPES}
    no_value = set(ids) - set(by)
    corr = [r for r in rows if r["HPSA Status"] in DESIGNATED and r["Designation Type"] == "Correctional Facility"]   # HRSA's own totals include these facilities: kept apart so the check against them can be repeated
    tot = lambda rs, col: round(sum(num(r[col]) or 0 for r in rs), 2)
    years = lambda col: [d.year for d in (day(r[col]) for r in area) if d]
    span = lambda ys: [min(ys), max(ys)] if ys else None
    return out, {"status": dict(seen), "area": len(area), "facility": facility, "not_in_force": other, "overlaps": overlaps, "provider_type": dict(types), "municipios_with_only_a_facility_designation": facility_only, "municipios_with_only_a_correctional_facility": facility_only_correctional,
                 "municipios_without_an_area_designation": len(no_value), "municipios_without_one_that_had_one_withdrawn": len(no_value & withdrawn_area),
                 "area_types": {f"{a} / {b}": n for (a, b), n in Counter((r["Designation Type"], r["HPSA Population Type"]) for r in area).most_common()},
                 "designated_years": span(years("HPSA Designation Date")), "last_updated_years": span(years("HPSA Designation Last Update Date")),
                 "area_population": tot(area, "HPSA Designation Population"), "correctional": {"designations": len(corr), "fte": tot(corr, "HPSA FTE"), "shortage": tot(corr, "HPSA Shortage"), "population": tot(corr, "HPSA Designation Population")}}


def met_pct(fte, short):
    return None if fte is None or short is None or fte + short <= 0 else fte / (fte + short) * 100


# ── Output ───────────────────────────────────────────────────────────────────

def var(key, group, label, unit, d, typ, sources, ref, definition, values, **extra):
    """`counted: False`: these are administrative counts and figures from a federal formula, not estimates from a few cases, so the engine does not flag a small count as less reliable.
    `classes: "jenks"` (in extra): the legend starts with natural breaks, for counts with many zeros and for scores with few distinct values.
    `dPer`: decimals of the per-resident views and of the short numbers of a legend (practitioners needed per 1,000 residents run from 0.01 to 0.1: 3). `noPerHU`: a count that does not sit on housing offers no "per 1,000 housing units".
    `tag`: the word the dataset window shows for the kind of figure instead of its type ("score")."""
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": ref, "definition": definition, "family": "health", "counted": False, **extra, "years": values}


def compute(refresh=False, order_file=hs.OUT / "economy_series.json", floors=FLOORS, offline=False):
    names, fips = hs.municipalities()
    ids = list(fips)
    pos = {f: i for i, f in enumerate(ids)}
    n = len(ids)
    if order_file and order_file.exists():   # the arrays must line up with the other series files
        g = json.loads(order_file.read_text(encoding="utf-8"))["geo"]
        if g["ids"][:n] != ids or g["names"][:n] != names:
            raise SystemExit("health_series: the municipalities are not in the order of economy_series.json")
    log("HRSA health centers and shortage areas")
    kw = {"offline": True} if offline else {}   # --check: the cache or nothing
    site_rows = pr_rows("sites", refresh, **kw)
    perm, van, skipped = sites(site_rows, pos)
    hp, hnotes = {}, {}
    rows_by = {}
    for k, disc, *_ in DISCIPLINES:
        rows_by[k] = pr_rows(f"hpsa_{k}", refresh, **kw)
        hp[k], hnotes[k] = hpsa(rows_by[k], pos, disc)
    # HRSA could rename a value ("Active", "Designated") and leave every column where it is: every count would be 0 and the build would publish a false "no site" and "no shortage area" for every municipality
    new_kinds = sorted(k[len("location type "):] for k in skipped if k.startswith("location type ") and k[len("location type "):] not in KNOWN_LOCATIONS)
    if new_kinds:
        raise SystemExit(f"health_series: the sites file has a location type the build does not know ({', '.join(new_kinds)}): HRSA may have renamed \"Permanent\" or \"Mobile Van\"; read its metadata before publishing")
    if floors and (sum(perm.values()) < floors["permanent"] or len(perm) < floors["municipios_with_a_site"]):
        raise SystemExit(f"health_series: {sum(perm.values())} permanent sites in {len(perm)} municipalities (the 2026-10 file has 127 in 70); HRSA may have renamed a status or a type in the sites file: read the file before publishing")
    if floors and sum(van.values()) < floors["vans"]:
        raise SystemExit(f"health_series: {sum(van.values())} mobile vans (the 2026-10 file has 33): HRSA may have renamed the location type \"Mobile Van\": read the file before publishing")
    for k in ("pc", "dh", "mh"):
        if floors and (len(hp[k]) < floors[k] or "Designated" not in hnotes[k]["status"]):
            raise SystemExit(f"health_series: {len(hp[k])} area designations in force in the {k} file with the statuses {sorted(hnotes[k]['status'])} (the 2026-10 file has 20, 77 and 52): HRSA may have renamed a status or a designation type: read the file before publishing")
        if set(hnotes[k]["status"]) - {"Designated", "Withdrawn", "Proposed For Withdrawal"}:
            raise SystemExit(f"health_series: the {k} file has a status the build does not know ({sorted(hnotes[k]['status'])}): read HRSA's metadata before publishing")
    made = {key: max((d for d in (day(r[CREATED]) for r in rs) if d), default=None) for key, rs in {"sites": site_rows, **{f"hpsa_{k}": rs for k, rs in rows_by.items()}}.items()}
    if not all(made.values()):
        raise SystemExit("health_series: a file has no record-create date, so the date of the files is unknown")
    if (max(made.values()) - min(made.values())).days > 1:
        raise SystemExit(f"health_series: the four HRSA files were made on different days ({', '.join(f'{k} {v}' for k, v in made.items())}): run python health_series.py --refresh so all four come from one day")
    as_of = max(made.values())
    year = as_of.year

    def column(c):   # a count for each municipality (a true zero where HRSA lists none) and the island sum last
        a = [c.get(f, 0) for f in ids]
        return a + [sum(a)]

    def by_muni(k, pick):   # a figure for each municipality that has an area-level designation, None for the others
        a = [pick(hp[k][f]) if f in hp[k] else None for f in ids]
        return a

    vs = []
    G0 = "Health centers"   # the engine puts "Health care · " in front of every group of this file (adapters.snapshotFile)
    vs.append(var("hc_sites", G0, "Health center sites (permanent)", "", 0, "count", ["hrsa_sites"], "HRSA Data Warehouse: Health Center Service Delivery and Look-Alike Sites",
                  "Permanent sites where a health center that holds a federal grant (a Federally Qualified Health Center, FQHC) or a look-alike designation delivers care, in the municipality HRSA gives for the site. "
                  "HRSA lists a site only while its organization holds the grant or the look-alike status and the site is open. Administrative-only buildings, mobile vans and seasonal sites are not counted here. "
                  "A site is a place, not an organization (one organization can run many) and says nothing about hours, services or how many people it serves. A municipality with none shows 0: HRSA lists no site there.",
                  {str(year): column(perm)}, dPer=3, noPerHU=True, classes="jenks"))
    vs.append(var("hc_vans", G0, "Health center mobile vans", "", 0, "count", ["hrsa_sites"], "HRSA Data Warehouse: Health Center Service Delivery and Look-Alike Sites",
                  "Mobile vans that HRSA lists as service delivery sites of a health center, in the municipality HRSA gives for the van. A van can serve other municipalities, so this shows where it is listed, "
                  "not everywhere it works. A municipality with none shows 0: HRSA lists no van there.", {str(year): column(van)}, dPer=3, noPerHU=True, classes="jenks"))
    for k, disc, short_name, who, l_short, l_met, l_score, score_max in DISCIPLINES:
        g = f"{short_name} shortage areas"
        ref = f"HRSA Data Warehouse: Health Professional Shortage Area designations, {short_name.lower()}"
        scope = ("Shown for a municipality that has a designated shortage area for its low-income residents or for the whole municipality (area-level designations). "
                 "No value means HRSA's file has no such designation for the municipality: it is not rated as a shortage area, which is not the same as missing data. "
                 "Designations of facilities (health centers, which HRSA designates by law, and a correctional facility) are left out.")
        counted = ("HRSA counts a practitioner by the time spent serving the designated population: for a low-income population, the time spent on Medicaid and sliding-fee patients "
                   "(HRSA's Shortage Designation Management System manual, August 2026), so a practitioner who serves few such patients adds little or nothing.")
        fte = {f: v[1] for f, v in hp[k].items()}
        short = {f: v[2] for f, v in hp[k].items()}
        isl_short = sum(short.values()) if short else None
        isl_fte = sum(fte.values()) if fte else None
        NV = {"noValue": "No area shortage designation"}   # the legend, the pop-up and the table say what an empty place means: it is not rated as a shortage area (a facility designation does not count), which is not missing data
        vs.append(var(f"hpsa_{k}_short", g, l_short, "", 1, "count", ["hrsa_hpsa"], ref,
                      f"The number of additional {who}, in full-time equivalents, that HRSA says the designated shortage area still needs to bring its ratio of people to practitioners down to the ratio HRSA works the figure out against. "
                      f"{RATIO[k]} {counted} {scope} The Puerto Rico figure adds the municipal figures and leaves out the facilities, so it is a little below HRSA's own total.",
                      {str(year): by_muni(k, lambda v: round(v[2], 2)) + [None if isl_short is None else round(isl_short, 2)]}, dPer=3, noPerHU=True, **NV))
        vs.append(var(f"hpsa_{k}_met", g, l_met, "%", 1, "rate", ["hrsa_hpsa"], ref,
                      f"Of the {who} that HRSA's formula says the designated shortage area needs, the share that are in place: practitioners available (full-time equivalents) divided by practitioners available plus "
                      f"practitioners still needed. This is HRSA's \"percent of need met\", worked out here for each municipality. It is not the share of people who get care. 0 means HRSA counts none serving the designated population; 100 means HRSA's formula needs no more. {counted} {scope}",
                      {str(year): by_muni(k, lambda v: None if met_pct(v[1], v[2]) is None else round(met_pct(v[1], v[2]), 3)) + [None if isl_fte is None else round(met_pct(isl_fte, isl_short), 3)]}, dPer=1, **NV, **JENKS.get(f"hpsa_{k}_met", {})))
        vs.append(var(f"hpsa_{k}_score", g, l_score, "", 0, "ratio", ["hrsa_hpsa"], ref,
                      f"HRSA's priority score for a designated {short_name.lower()} shortage area (HRSA scores {short_name.lower()} designations from 0 to {score_max}): the higher the score, the greater the priority for placing National Health Service Corps clinicians. "
                      f"It is an index that HRSA builds by its own rules, not a measurement, and a municipality's score is that of its area-level designation (the highest, if it has more than one). {scope} "
                      "Scores are not added or averaged, so there is no value for Puerto Rico as a whole.",
                      {str(year): by_muni(k, lambda v: v[0]) + [None]}, noIsland=True, tag="score", dPer=0, **NV, **JENKS.get(f"hpsa_{k}_score", {})))
    notes = {
        "sites": {"rows": len(site_rows), "service_sites": sum(perm.values()) + sum(van.values()), "permanent": sum(perm.values()), "mobile_vans": sum(van.values()),
                  "left_out": dict(skipped), "municipios_with_a_site": len(perm), "municipios_with_a_van": len(van)},
        "hpsa": {k: {"municipios": len(hp[k]), **hnotes[k], "shortage_total": round(sum(v[2] for v in hp[k].values()), 2), "fte_total": round(sum(v[1] for v in hp[k].values()), 2)} for k in hp},
        "files": {k: FILES[k]["file"] for k in FILES},
        "left_unread": "The Area Health Resources File (re-use needs the Bureau's permission) and the MUA/P file (a status that is the same for 72 of 78 municipios): see docs/health.md",
    }
    return {"as_of": as_of.isoformat(), "years": [year], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    out = compute(refresh, offline=check)
    new = {"built": date.today().isoformat(), **out}
    text = json.dumps(new, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        if old is None or {**old, "built": None} != {**json.loads(text), "built": None}:
            print("health_series.json is not what the cached HRSA rows give: run python health_series.py")
            return 1
        print("health_series.json matches the cached HRSA rows")
        return 0
    OUT.write_text(text, encoding="utf-8")
    nb = len(vs := out["vars"])
    log(f"wrote {OUT.name}: {nb} variables, as of {out['as_of']}, {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
