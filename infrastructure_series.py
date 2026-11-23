"""Infrastructure for the PR Data Observatory (Phase 3, item 10, data wave D), for the 78 municipalities and Puerto Rico.

    python infrastructure_series.py             # build site/data/infrastructure_series.json and site/data/bridges_series.json (downloads only what is missing)
    python infrastructure_series.py --refresh   # download again
    python infrastructure_series.py --check     # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Eight sources, no key, US federal data (public domain):
  EPA ECHO, Safe Drinking Water Act search: the active community water systems of Puerto Rico, with the municipalities each one serves (FIPS codes), the population it
      serves, and two of ECHO's flags: a health-based violation (HealthFlag: a breach of a maximum contaminant level, a maximum residual disinfectant level or a treatment
      technique rule) and enforcement priority (SeriousViolator: unresolved serious, multiple or continuing violations, EPA's priority for formal enforcement).
      The systems outside PRASA (non-PRASA) are the ones SDWIS records as privately owned (owner type P), as EPA Region 2 defines non-PRASA systems; they are
      counted, and their residents served added up where a system serves one municipality only. The system's name is dropped as the file is read: many
      non-PRASA systems are named after a person, a family or a farm. No federal source gives their locations below the municipality (docs/infrastructure.md).
  EPA ECHO, Clean Water Act search: the facilities of Puerto Rico with an active individual permit to discharge wastewater into surface waters (an NPDES
      permit), each with its point, whether it is a publicly owned treatment works (a public sewage treatment plant), whether EPA classes it as a major
      discharger, and ECHO's current compliance status. A facility is placed in the municipality whose boundary holds its point. The facility's name is
      dropped as the file is read. Left out: the facilities covered by a general permit (construction sites, industrial and municipal stormwater), which
      come and go with each project, and the records ECHO attaches to another permit.
  EPA ECHO, Clean Air Act search: the active stationary sources of air pollution of Puerto Rico that the Clean Air Act regulates (power plants,
      factories, quarries, hospitals' boilers, fuel terminals and others), each with its point and EPA's class of its emissions (major, synthetic
      minor, minor). A source is placed in the municipality whose boundary holds its point. Its name is dropped as the file is read.
  EPA ECHO, hazardous waste search (the Resource Conservation and Recovery Act, RCRA): the active handlers of hazardous waste of Puerto Rico
      (the businesses and institutions that generate, transport, treat or store it), each with its point and its class by the amount of waste it
      generates. A handler is placed in the municipality whose boundary holds its point. Its name is dropped as the file is read.
  EPA ECHO, all-programs facility search: every active facility of Puerto Rico that EPA regulates under the air, water, hazardous waste or drinking
      water laws, each with its point, how many inspections it had in the last five years and how many formal enforcement actions. A facility is placed
      in the municipality whose boundary holds its point. Its name is dropped as the file is read.
  EPA Toxics Release Inventory (TRI), Basic Data File for Puerto Rico (Envirofacts): the pounds of listed toxic chemicals each reporting facility
      released in the newest reporting year, in total and to the air. The pounds are summed for the municipality whose boundary holds the facility's
      point. The facility's name is never read into the cache. conditions.py counts the same facilities by barrio (epa_tri).
  EIA-860M, the monthly generator inventory (Puerto Rico sheet "Operating_PR"): each operating generator's plant id, technology, nameplate capacity and point. A generator
      is placed in the municipality whose boundary holds its point (the file leaves the county blank for 78 of 228 generators). Owner names and plant names are dropped.
  FHWA National Bridge Inventory, the yearly delimited file of Puerto Rico: each bridge's county and its condition (good, fair or poor, from the lowest of the deck,
      superstructure, substructure and culvert ratings, FHWA's rule: 4 or below is poor, 7 or above is good). Locations and names are not kept.

Outputs:
  infrastructure_series.json   one snapshot (the shape of health_series.json): water systems, wastewater discharge permits, air pollution sources, hazardous waste handlers, inspections and enforcement actions, toxic chemical releases, and power plants
  bridges_series.json          one value a year (the shape of economy_series.json): bridges and their condition
A system that serves several municipalities counts in each of them; its population is not split (there is no honest way to), so population served is an island figure in notes only.
"""

import csv
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import xlsx_lite

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "infrastructure"
OUT = hs.OUT / "infrastructure_series.json"
OUT_BR = hs.OUT / "bridges_series.json"
OUT_BARRIO = hs.OUT / "infrastructure_barrio.json"   # the same counts for the 901 barrios, for the datasets of BARRIO_KEYS
# The counts also given by barrio: how many facilities of a kind a barrio holds. The counts of violations, inspections and enforcement actions and the pounds of
# toxic releases stay at the municipality: in a barrio they would nearly always be one facility's own record.
BARRIO_KEYS = ("wastewater_permits", "wastewater_plants", "wastewater_major", "air_sources", "air_major", "hazwaste_handlers", "hazwaste_large")
UA = {"User-Agent": "Mozilla/5.0 (pr-digital-twin open-data build; Foundation for Puerto Rico)"}
log = hs.log
ECHO = "https://echodata.epa.gov/echo/sdw_rest_services."
ECHO_COLS = {"2": "PWSId", "10": "PWSTypeCode", "14": "PopulationServedCount", "17": "OwnerTypeCode", "21": "SeriousViolator", "22": "HealthFlag", "48": "FIPSCodes"}   # ECHO column ids (sdw_rest_services.metadata)
ECHO_CWA = "https://echodata.epa.gov/echo/cwa_rest_services."
CWA_COLS = {"15": "FacFIPSCode", "26": "FacLat", "27": "FacLong", "30": "CWPFacilityTypeIndicator", "56": "CWPPermitTypeDesc", "62": "CWPMajorMinorStatusFlag", "99": "CWPStatus"}   # ECHO column ids (cwa_rest_services.metadata); SourceID, the permit number, comes with every download
CWA_KEEP = ["SourceID"] + list(CWA_COLS.values())
CWA_INDIVIDUAL = "NPDES Individual Permit"
CWA_VIOLATION = {"Violation Identified", "Significant/Category I Noncompliance"}   # ECHO's current status of a permit that is not in compliance
CWA_SNC = "Significant/Category I Noncompliance"
ECHO_AIR = "https://echodata.epa.gov/echo/air_rest_services."
AIR_COLS = {"14": "FacFIPSCode", "25": "FacLat", "26": "FacLong", "29": "AIRStatus", "31": "AIRClassification", "46": "AIRComplStatus"}   # ECHO column ids (air_rest_services.metadata); SourceID, the source's number, comes with every download
AIR_KEEP = ["SourceID"] + list(AIR_COLS.values())
AIR_MAJOR = "Major Emissions"
AIR_HPV = "High Priority Violation"
ECHO_RCRA = "https://echodata.epa.gov/echo/rcra_rest_services."
RCRA_COLS = {"14": "FacFIPSCode", "25": "FacLat", "26": "FacLong", "27": "RCRAUniverse", "38": "RCRAComplStatus"}   # ECHO column ids (rcra_rest_services.metadata); SourceID, the handler's number, comes with every download
RCRA_KEEP = ["SourceID"] + list(RCRA_COLS.values())
RCRA_LARGE = "LQG"   # a large quantity generator; a handler can be in several classes ("LQG, Transporter")
RCRA_CLEAR = "No Violation Identified"
ECHO_ALL = "https://echodata.epa.gov/echo/echo_rest_services."
ALL_COLS = {"19": "FacLat", "20": "FacLong", "43": "FacInspectionCount", "56": "FacFormalActionCount", "83": "FacFIPSCode"}   # ECHO column ids (echo_rest_services.metadata); RegistryID, EPA's number of the facility, comes with every download
ALL_KEEP = ["RegistryID"] + list(ALL_COLS.values())
TRI_URL = "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/{y}_PR/csv"   # the file conditions.py reads for its count of facilities
TRI_COLS = {"year": "1. YEAR", "trifd": "2. TRIFD", "st": "8. ST", "lat": "12. LATITUDE", "lon": "13. LONGITUDE", "unit": "50. UNIT OF MEASURE", "fugitive": "51. 5.1 - FUGITIVE AIR",
            "stack": "52. 5.2 - STACK AIR", "total": "107. TOTAL RELEASES"}
TRI_KEEP = ["trifd", "lon", "lat", "total_lb", "air_lb", "chemicals"]
LB_PER_GRAM = 0.00220462   # dioxins are reported in grams
EIA = "https://www.eia.gov/electricity/data/eia860m/xls/{month}_generator{year}.xlsx"
EIA_KEEP = ["Plant ID", "Technology", "Nameplate Capacity (MW)", "Latitude", "Longitude", "Status"]
RENEWABLE = {"Solar Photovoltaic", "Conventional Hydroelectric", "Onshore Wind Turbine", "Landfill Gas"}
NBI = "https://www.fhwa.dot.gov/bridge/nbi/{y}/delimited/PR{yy}.txt"
NBI_KEEP = ["COUNTY_CODE_003", "RECORD_TYPE_005A", "DECK_COND_058", "SUPERSTRUCTURE_COND_059", "SUBSTRUCTURE_COND_060", "CULVERT_COND_062", "BRIDGE_CONDITION"]
NBI_FIRST = 2016
FLOORS = {"water": 300, "wastewater": 120, "air": 300, "hazwaste": 1000, "regulated": 2500, "tri": 60, "generators": 150, "bridges": 2000}   # the 2026-10 sources have 404 systems, 228 generators and 2,434 bridges; ECHO of 2026-11-11 has 177 individual wastewater permits , 482 active air pollution sources , 1,740 active hazardous waste handlers and 3,925 active regulated facilities in all

SOURCES = {
    "epa_echo_sdwa": {"name": "EPA ECHO — Safe Drinking Water Act, community water systems", "url": "https://echo.epa.gov/facilities/facility-search?mediaSelected=sdwa", "license": "US federal government data (public domain)",
                      "note": "Active community water systems, the municipalities they serve and two of ECHO's compliance flags. The observatory publishes counts for each municipality, never a system's name."},
    "epa_echo_cwa": {"name": "EPA ECHO — Clean Water Act, wastewater discharge permits (NPDES)", "url": "https://echo.epa.gov/facilities/facility-search?mediaSelected=cwa", "license": "US federal government data (public domain)",
                     "note": "Facilities with an active individual permit to discharge wastewater, with ECHO's current compliance status. The observatory publishes counts for each municipality, never a facility's name or point."},
    "epa_echo_caa": {"name": "EPA ECHO — Clean Air Act, stationary sources of air pollution", "url": "https://echo.epa.gov/facilities/facility-search?mediaSelected=caa", "license": "US federal government data (public domain)",
                     "note": "Active facilities that the Clean Air Act regulates, with EPA's class of their emissions. The observatory publishes counts for each municipality, never a facility's name or point."},
    "epa_echo_rcra": {"name": "EPA ECHO — Hazardous waste handlers (RCRA)", "url": "https://echo.epa.gov/facilities/facility-search?mediaSelected=rcra", "license": "US federal government data (public domain)",
                      "note": "Active handlers of hazardous waste, with their class by the amount they generate. The observatory publishes counts for each municipality, never a handler's name or point."},
    "epa_echo_all": {"name": "EPA ECHO — Inspections and enforcement actions at regulated facilities", "url": "https://echo.epa.gov/facilities/facility-search", "license": "US federal government data (public domain)",
                     "note": "Active facilities regulated under the air, water, hazardous waste or drinking water laws, with their inspections and formal enforcement actions of the last five years. The observatory publishes counts for each municipality, never a facility's name or point."},
    "epa_tri": {"name": "EPA — Toxics Release Inventory (TRI), Basic Data File for Puerto Rico", "url": "https://www.epa.gov/toxics-release-inventory-tri-program/tri-basic-data-files-calendar-years-1987-present",
                "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105)",
                "note": "Pounds of listed toxic chemicals that the reporting facilities released in the reporting year. The observatory sums them for each municipality; it publishes no name, address or point."},
    "eia_860m": {"name": "EIA — Form EIA-860M, Monthly Update to the Annual Electric Generator Report", "url": "https://www.eia.gov/electricity/data/eia860m/", "license": "US federal government data (public domain)",
                 "note": "Operating generators of Puerto Rico. The observatory publishes plants and capacity for each municipality, never owner or plant names."},
    "fhwa_nbi": {"name": "FHWA — National Bridge Inventory", "url": "https://www.fhwa.dot.gov/bridge/nbi/ascii.cfm", "license": "US federal government data (public domain)",
                 "note": "Every highway bridge of Puerto Rico each year, with its condition. The observatory publishes counts for each municipality."},
}


def get(url, **kw):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 300), **kw)
            if r.status_code in (301, 302, 404):
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"infrastructure_series: {url} failed: {e}")


# ── Water ────────────────────────────────────────────────────────────────────

def water_rows(refresh=False, offline=False):
    path = CACHE / "echo_cws.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    q = get(ECHO + "get_systems", params={"output": "JSON", "p_st": "PR", "p_act": "Y", "p_systyp": "CWS"}).json()["Results"]["QueryID"]
    r = get(ECHO + "get_download", params={"qid": q, "output": "CSV", "qcolumns": ",".join(ECHO_COLS)})
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
    missing = [c for c in ECHO_COLS.values() if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"infrastructure_series: ECHO's download has no column {missing}: read its metadata before going on")
    rows = [{c: x[c] for c in ECHO_COLS.values()} for x in rd]   # the system's name (always in the download) is dropped here
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
    log(f"  ECHO community water systems: {len(rows)}")
    return rows


# ── Wastewater ───────────────────────────────────────────────────────────────

def wastewater_rows(refresh=False, offline=False):
    """{"rows": the facilities with an active individual NPDES permit, "types": how many active records ECHO has of each permit type}."""
    path = CACHE / "echo_npdes.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    q = get(ECHO_CWA + "get_facilities", params={"output": "JSON", "p_st": "PR", "p_act": "Y"}).json()["Results"]["QueryID"]
    r = get(ECHO_CWA + "get_download", params={"qid": q, "output": "CSV", "qcolumns": ",".join(CWA_COLS)})
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
    missing = [c for c in CWA_KEEP if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"infrastructure_series: ECHO's wastewater download has no column {missing}: read its metadata before going on")
    every = [{c: x[c] for c in CWA_KEEP} for x in rd]   # the facility's name (always in the download) is dropped here
    d = {"fetched": date.today().isoformat(), "types": dict(Counter(x["CWPPermitTypeDesc"] for x in every)), "rows": [x for x in every if x["CWPPermitTypeDesc"] == CWA_INDIVIDUAL]}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    log(f"  ECHO wastewater permits: {len(d['rows'])} individual permits of {len(every)} active records")
    return d


# ── Air ──────────────────────────────────────────────────────────────────────

def air_rows(refresh=False, offline=False):
    """{"rows": the active stationary sources of air pollution of Puerto Rico in ECHO (Clean Air Act)}."""
    path = CACHE / "echo_air.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    q = get(ECHO_AIR + "get_facilities", params={"output": "JSON", "p_st": "PR", "p_act": "Y"}).json()["Results"]["QueryID"]
    r = get(ECHO_AIR + "get_download", params={"qid": q, "output": "CSV", "qcolumns": ",".join(AIR_COLS)})
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
    missing = [c for c in AIR_KEEP if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"infrastructure_series: ECHO's air download has no column {missing}: read its metadata before going on")
    d = {"fetched": date.today().isoformat(), "rows": [{c: x[c] for c in AIR_KEEP} for x in rd]}   # the facility's name (always in the download) is dropped here
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    log(f"  ECHO air pollution sources: {len(d['rows'])} active")
    return d


# ── Hazardous waste ──────────────────────────────────────────────────────────

def hazwaste_rows(refresh=False, offline=False):
    """{"rows": the active handlers of hazardous waste of Puerto Rico in ECHO (RCRA)}."""
    path = CACHE / "echo_rcra.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    q = get(ECHO_RCRA + "get_facilities", params={"output": "JSON", "p_st": "PR", "p_act": "Y"}).json()["Results"]["QueryID"]
    r = get(ECHO_RCRA + "get_download", params={"qid": q, "output": "CSV", "qcolumns": ",".join(RCRA_COLS)})
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
    missing = [c for c in RCRA_KEEP if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"infrastructure_series: ECHO's hazardous waste download has no column {missing}: read its metadata before going on")
    d = {"fetched": date.today().isoformat(), "rows": [{c: x[c] for c in RCRA_KEEP} for x in rd]}   # the handler's name (always in the download) is dropped here
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    log(f"  ECHO hazardous waste handlers: {len(d['rows'])} active")
    return d


# ── Inspections and enforcement ──────────────────────────────────────────────

def count(v):
    """ECHO writes a count as digits, or leaves it empty."""
    v = (v or "").strip()
    return int(v) if v.isdigit() else 0


def regulated_rows(refresh=False, offline=False):
    """{"rows": the active facilities of Puerto Rico that EPA regulates, in ECHO's all-programs search}."""
    path = CACHE / "echo_all.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    q = get(ECHO_ALL + "get_facilities", params={"output": "JSON", "p_st": "PR", "p_act": "Y"}).json()["Results"]["QueryID"]
    r = get(ECHO_ALL + "get_download", params={"qid": q, "output": "CSV", "qcolumns": ",".join(ALL_COLS)})
    rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
    missing = [c for c in ALL_KEEP if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"infrastructure_series: ECHO's all-programs download has no column {missing}: read its metadata before going on")
    d = {"fetched": date.today().isoformat(), "rows": [{c: x[c] for c in ALL_KEEP} for x in rd]}   # the facility's name (always in the download) is dropped here
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    log(f"  ECHO regulated facilities: {len(d['rows'])} active")
    return d


# ── Toxic chemical releases ──────────────────────────────────────────────────

def tri_rows(refresh=False, offline=False):
    """{"year": the newest reporting year EPA has published for Puerto Rico, "rows": one row per facility with its pounds released in total and to the air}."""
    path = CACHE / "tri_releases.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    this = date.today().year
    for y in range(this, this - 4, -1):
        r = get(TRI_URL.format(y=y))
        if r is None or not r.text.startswith("1. YEAR"):
            continue
        rd = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig", errors="replace")))
        missing = [c for c in TRI_COLS.values() if c not in (rd.fieldnames or [])]
        if missing:
            raise SystemExit(f"infrastructure_series: the TRI file has no column {missing}")
        num = lambda v: float(v) if (v or "").strip() else 0.0
        fac = {}
        for x in rd:   # one row per facility and chemical; only the columns of TRI_COLS are read, so the facility's name never reaches the cache
            if x[TRI_COLS["st"]] != "PR":
                raise SystemExit("infrastructure_series: the TRI file for Puerto Rico holds a facility in another state")
            k = LB_PER_GRAM if x[TRI_COLS["unit"]] == "Grams" else 1.0
            if x[TRI_COLS["unit"]] not in ("Pounds", "Grams"):
                raise SystemExit(f"infrastructure_series: a TRI row is in {x[TRI_COLS['unit']]!r}, not pounds or grams")
            f = fac.setdefault(x[TRI_COLS["trifd"]], {"trifd": x[TRI_COLS["trifd"]], "lon": float(x[TRI_COLS["lon"]]), "lat": float(x[TRI_COLS["lat"]]), "total_lb": 0.0, "air_lb": 0.0, "chemicals": 0})
            f["total_lb"] += num(x[TRI_COLS["total"]]) * k
            f["air_lb"] += (num(x[TRI_COLS["fugitive"]]) + num(x[TRI_COLS["stack"]])) * k
            f["chemicals"] += 1
        d = {"fetched": date.today().isoformat(), "year": y, "rows": sorted(({**f, "total_lb": round(f["total_lb"], 3), "air_lb": round(f["air_lb"], 3)} for f in fac.values()), key=lambda f: f["trifd"])}
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
        log(f"  TRI releases, reporting year {y}: {len(d['rows'])} facilities")
        return d
    raise SystemExit("infrastructure_series: no TRI Basic Data File for Puerto Rico in the last four years")


# ── Power ────────────────────────────────────────────────────────────────────

def power_rows(refresh=False, offline=False):
    """The kept columns of EIA-860M's operating generators of Puerto Rico, from the newest monthly file that answers, and the month it is."""
    path = CACHE / "eia860m_operating.pr.json"
    if path.exists() and not refresh:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d["rows"], d["month"]
    if offline:
        raise SystemExit(f"infrastructure_series --check: {path.name} is not in the cache")
    months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    t = date.today()
    for back in range(0, 8):
        y, m = (t.year * 12 + t.month - 1 - back) // 12, (t.year * 12 + t.month - 1 - back) % 12
        r = get(EIA.format(month=months[m], year=y))
        if r is not None and r.content[:2] == b"PK":
            break
    else:
        raise SystemExit("infrastructure_series: no EIA-860M file of the last eight months answered")
    tmp = CACHE / "eia860m.xlsx"
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(r.content)
    rows = xlsx_lite.sheet_rows(tmp, "Operating_PR")
    tmp.unlink()
    hi = next(i for i, x in enumerate(rows) if "Plant ID" in x)
    h = rows[hi]
    missing = [c for c in EIA_KEEP if c not in h]
    if missing:
        raise SystemExit(f"infrastructure_series: EIA-860M's Operating_PR sheet has no column {missing}")
    out = [{c: x[h.index(c)] if h.index(c) < len(x) else "" for c in EIA_KEEP} for x in rows[hi + 1:] if len(x) > h.index("Plant ID") and x[h.index("Plant ID")].strip().isdigit()]
    month = f"{y}-{m + 1:02d}"
    path.write_text(json.dumps({"month": month, "rows": out}, separators=(",", ":")), encoding="utf-8")
    log(f"  EIA-860M {month}: {len(out)} operating generators")
    return out, month


def locate(points, strict=True):
    """{index: fips} for each (lon, lat), by the municipal boundary that holds it (site/data/municipios.geojson). A point more than 2 km from every
    municipality stops the build, or gives None when strict is False."""
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree
    fc = json.loads((hs.OUT / "municipios.geojson").read_text(encoding="utf-8"))
    names, fips = hs.municipalities()
    by_name = dict(zip(names, fips))
    geoms, keys = [], []
    for f in fc["features"]:
        geoms.append(shape(f["geometry"]))
        keys.append(by_name[f["properties"]["municipality"]])
    tree = STRtree(geoms)
    out = {}
    for i, (lon, lat) in enumerate(points):
        p = Point(lon, lat)
        hit = [j for j in tree.query(p) if geoms[j].contains(p)]
        if not hit:   # a point on the coast just outside the drawn boundary: the nearest municipality
            j = min(range(len(geoms)), key=lambda k: geoms[k].distance(p))
            if geoms[j].distance(p) > 0.02:
                if not strict:
                    out[i] = None
                    continue
                raise SystemExit(f"infrastructure_series: a point ({lon}, {lat}) is more than 2 km from every municipality")
            hit = [j]
        out[i] = keys[hit[0]]
    return out


# ── Bridges ──────────────────────────────────────────────────────────────────

def bridge_rows(year, refresh=False, offline=False):
    path = CACHE / f"nbi_{year}.pr.csv"
    if path.exists() and not refresh:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    if offline:
        return None
    r = get(NBI.format(y=year, yy=str(year)[2:]))
    if r is None:
        return None
    rd = csv.DictReader(io.StringIO(r.content.decode("latin-1")))
    rows = [{c: (x.get(c) or "").strip().strip("'") for c in NBI_KEEP} for x in rd]
    CACHE.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NBI_KEEP, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    log(f"  NBI {year}: {len(rows)} rows")
    return rows


def condition(r):
    """FHWA's rule: the lowest of the deck, superstructure, substructure and culvert ratings (0-9; "N" is not applicable); 4 or below is poor, 7 or above is good, else fair. None when no rating."""
    vals = [int(r[c]) for c in ("DECK_COND_058", "SUPERSTRUCTURE_COND_059", "SUBSTRUCTURE_COND_060", "CULVERT_COND_062") if r[c].isdigit()]
    if not vals:
        return None
    low = min(vals)
    return "P" if low <= 4 else "G" if low >= 7 else "F"


# ── Build ────────────────────────────────────────────────────────────────────

def var(key, group, label, unit, d, typ, sources, ref, definition, values, family="infrastructure", **extra):
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": ref, "definition": definition, "family": family, "counted": False, **extra, "years": values}


def compute(refresh=False, offline=False, floors=FLOORS):
    names, fips = hs.municipalities()
    ids = list(fips)
    g = json.loads((hs.OUT / "economy_series.json").read_text(encoding="utf-8"))["geo"]
    if g["ids"][:len(ids)] != ids or g["names"][:len(ids)] != names:
        raise SystemExit("infrastructure_series: the municipalities are not in the order of economy_series.json")
    log("Infrastructure: drinking water, wastewater permits, air pollution sources, hazardous waste handlers, inspections and enforcement (EPA ECHO), toxic chemical releases (EPA TRI), power plants (EIA-860M), bridges (FHWA NBI)")
    column = lambda c: [c.get(f, 0) for f in ids] + [sum(c.get(f, 0) for f in ids)]
    with_island = lambda c, isl: [c.get(f, 0) for f in ids] + [isl]   # the island figure counts each system once
    rcolumn = lambda c: [round(c.get(f, 0), 1) for f in ids] + [round(sum(c.get(f, 0) for f in ids), 1)]
    # water
    wr = water_rows(refresh, offline)
    if floors and len(wr) < floors["water"]:
        raise SystemExit(f"infrastructure_series: {len(wr)} community water systems (the 2026-10 search has 404)")
    sys_n, health, prio = Counter(), Counter(), Counter()
    np_n, np_pop = Counter(), Counter()   # systems outside PRASA (non-PRASA): the ones SDWIS records as privately owned (OwnerTypeCode P), as EPA Region 2 defines them
    multi, pop, island_only = 0, 0, 0
    np_all = np_pop_all = np_multi = np_multi_pop = np_health = 0
    for r in wr:
        fl = [x.strip() for x in (r["FIPSCodes"] or "").split(",") if x.strip()]
        p = int((r["PopulationServedCount"] or "0").replace(",", "") or 0)
        pop += p
        private = r["OwnerTypeCode"] == "P"
        if private:
            np_all += 1
            np_pop_all += p
            np_health += r["HealthFlag"] == "Yes"
        if fl == ["72"]:   # a few small systems give Puerto Rico's code and no municipality: they count in the island figures only
            island_only += 1
            continue
        bad = [x for x in fl if x not in ids]
        if bad or not fl:
            raise SystemExit(f"infrastructure_series: a water system ({r['PWSId']}) serves {fl}, not a list of the 78 municipalities")
        multi += len(fl) > 1
        for f in fl:
            sys_n[f] += 1
            health[f] += r["HealthFlag"] == "Yes"
            prio[f] += r["SeriousViolator"] == "Yes"
            np_n[f] += private
        if private and len(fl) == 1:   # residents served are given to a municipio only when the system serves that one alone (a population is never split)
            np_pop[fl[0]] += p
        elif private:
            np_multi += 1
            np_multi_pop += p
    # wastewater: the facilities with an individual NPDES permit, each in the municipality that holds its point
    wd = wastewater_rows(refresh, offline)
    ww = wd["rows"]
    if floors and len(ww) < floors["wastewater"]:
        raise SystemExit(f"infrastructure_series: {len(ww)} individual wastewater permits (ECHO of 2026-11-11 has 177)")
    if len({r["SourceID"] for r in ww}) != len(ww):
        raise SystemExit("infrastructure_series: ECHO lists a wastewater permit twice")
    ww_where = locate([(float(r["FacLong"]), float(r["FacLat"])) for r in ww])
    ww_n, ww_potw, ww_major, ww_vio = Counter(), Counter(), Counter(), Counter()
    ww_fips_differs = 0
    for i, r in enumerate(ww):
        f = ww_where[i]
        ww_fips_differs += bool(r["FacFIPSCode"]) and r["FacFIPSCode"] != f   # ECHO's own county code, from the address: the point decides
        ww_n[f] += 1
        ww_potw[f] += r["CWPFacilityTypeIndicator"] == "POTW"
        ww_major[f] += r["CWPMajorMinorStatusFlag"] == "M"
        ww_vio[f] += r["CWPStatus"] in CWA_VIOLATION
    # air: the active stationary sources the Clean Air Act regulates, each in the municipality that holds its point
    ad = air_rows(refresh, offline)
    air = ad["rows"]
    if floors and len(air) < floors["air"]:
        raise SystemExit(f"infrastructure_series: {len(air)} active air pollution sources (ECHO of 2026-11-11 has 482)")
    if len({r["SourceID"] for r in air}) != len(air):
        raise SystemExit("infrastructure_series: ECHO lists an air pollution source twice")
    air_where = locate([(float(r["FacLong"]), float(r["FacLat"])) for r in air])
    air_n, air_major = Counter(), Counter()
    air_fips_differs = 0
    for i, r in enumerate(air):
        f = air_where[i]
        air_fips_differs += bool(r["FacFIPSCode"]) and r["FacFIPSCode"] != f   # ECHO's own county code, from the address: the point decides
        air_n[f] += 1
        air_major[f] += r["AIRClassification"] == AIR_MAJOR
    # hazardous waste: the active handlers, each in the municipality that holds its point
    hd = hazwaste_rows(refresh, offline)
    hz = hd["rows"]
    if floors and len(hz) < floors["hazwaste"]:
        raise SystemExit(f"infrastructure_series: {len(hz)} active hazardous waste handlers (ECHO of 2026-11-11 has 1,740)")
    if len({r["SourceID"] for r in hz}) != len(hz):
        raise SystemExit("infrastructure_series: ECHO lists a hazardous waste handler twice")
    hz_where = locate([(float(r["FacLong"]), float(r["FacLat"])) for r in hz])
    hz_n, hz_large = Counter(), Counter()
    hz_fips_differs = 0
    hz_is_large = [RCRA_LARGE in [c.strip() for c in r["RCRAUniverse"].split(",")] for r in hz]
    for i, r in enumerate(hz):
        f = hz_where[i]
        hz_fips_differs += bool(r["FacFIPSCode"]) and r["FacFIPSCode"] != f   # ECHO's own county code, from the address: the point decides
        hz_n[f] += 1
        hz_large[f] += hz_is_large[i]
    # inspections and enforcement: every active regulated facility, in the municipality that holds its point
    gd = regulated_rows(refresh, offline)
    rg = gd["rows"]
    if floors and len(rg) < floors["regulated"]:
        raise SystemExit(f"infrastructure_series: {len(rg)} active regulated facilities (ECHO of 2026-11-12 has 3,925)")
    if len({r["RegistryID"] for r in rg}) != len(rg):
        raise SystemExit("infrastructure_series: ECHO lists a regulated facility twice")
    rg_where = locate([(float(r["FacLong"]), float(r["FacLat"])) for r in rg], strict=False)   # a few records carry a point on the mainland (a head office) or out at sea
    known = set(hs.municipalities()[1])
    rg_insp, rg_formal = Counter(), Counter()
    rg_by_code = rg_unplaced = 0
    for i, r in enumerate(rg):
        f = rg_where[i]
        if f is None:   # no point on the island: ECHO's county code, from the address, when it names a municipality
            f = r["FacFIPSCode"] if r["FacFIPSCode"] in known else None
            rg_by_code += f is not None
        if f is None:
            rg_unplaced += 1
            continue
        rg_insp[f] += count(r["FacInspectionCount"]) > 0
        rg_formal[f] += count(r["FacFormalActionCount"]) > 0
    # toxic chemical releases: the pounds each TRI facility reported, summed in the municipality that holds its point
    td = tri_rows(refresh, offline)
    tr = td["rows"]
    if floors and len(tr) < floors["tri"]:
        raise SystemExit(f"infrastructure_series: {len(tr)} TRI facilities (reporting year 2024 has 104)")
    tr_where = locate([(r["lon"], r["lat"]) for r in tr])
    tr_total, tr_air, tr_fac = Counter(), Counter(), Counter()
    for i, r in enumerate(tr):
        tr_total[tr_where[i]] += r["total_lb"]
        tr_air[tr_where[i]] += r["air_lb"]
        tr_fac[tr_where[i]] += 1
    # power
    pr, month = power_rows(refresh, offline)
    if floors and len(pr) < floors["generators"]:
        raise SystemExit(f"infrastructure_series: {len(pr)} operating generators (the 2026 file has 228)")
    where = locate([(float(r["Longitude"]), float(r["Latitude"])) for r in pr])
    plants, mw, ren, techs = defaultdict(set), Counter(), Counter(), Counter()
    for i, r in enumerate(pr):
        f = where[i]
        cap = float(r["Nameplate Capacity (MW)"] or 0)
        plants[f].add(r["Plant ID"])
        if r["Technology"] != "Batteries":   # storage is not generating capacity
            mw[f] += cap
        if r["Technology"] in RENEWABLE:
            ren[f] += cap
        techs[r["Technology"]] += cap
    plant_n = Counter({f: len(s) for f, s in plants.items()})
    year = int(month[:4])
    G1, G2, G4, G5, G6, G7 = "Drinking water", "Power plants", "Wastewater", "Air pollution sources", "Hazardous waste", "Environmental enforcement"
    G8 = "Toxic chemical releases"
    TRI = f"EPA Toxics Release Inventory, reporting year {td['year']}"
    wcolumn = lambda c: [round(c.get(f, 0)) for f in ids] + [round(sum(c.get(f, 0) for f in ids))]   # whole pounds
    ENF = "EPA ECHO, all programs: active regulated facilities, last five years"
    HZ = "EPA ECHO, RCRA: active handlers of hazardous waste"
    AIR = "EPA ECHO, Clean Air Act: active stationary sources of air pollution"
    WW = "EPA ECHO, Clean Water Act: facilities with an active individual NPDES permit"
    W = "EPA ECHO, Safe Drinking Water Act: active community water systems"
    vs = [
        var("water_systems", G1, "Community water systems serving the municipality", "", 0, "count", ["epa_echo_sdwa"], W,
            "Active community water systems (systems that serve the same people all year: PRASA's, the community-run systems known as non-PRASA, and one federal system) that list the municipality among those they serve. A system that serves several municipalities counts in each, so the municipal values add up to more than Puerto Rico's, which counts each system once (and also the few small systems that give no municipality).",
            {str(year): with_island(sys_n, len(wr))}, noPerHU=True, classes="jenks"),
        var("water_health_vio", G1, "Water systems with a health-based violation", "", 0, "count", ["epa_echo_sdwa"], W,
            "Of those systems, the ones ECHO flags with a health-based violation: a breach of a maximum contaminant level, a maximum residual disinfectant level or a treatment technique rule. It is a compliance record, not proof that the water is unsafe today.",
            {str(year): with_island(health, sum(r["HealthFlag"] == "Yes" for r in wr))}, noPerHU=True, classes="jenks"),
        var("water_priority", G1, "Water systems that are an enforcement priority", "", 0, "count", ["epa_echo_sdwa"], W,
            "Of those systems, the ones EPA designates as an enforcement priority: unresolved serious, multiple or continuing violations.",
            {str(year): with_island(prio, sum(r["SeriousViolator"] == "Yes" for r in wr))}, noPerHU=True, classes="jenks"),
        var("water_nonprasa", G1, "Community water systems outside PRASA (non-PRASA)", "", 0, "count", ["epa_echo_sdwa"], W,
            "Of those systems, the ones the Safe Drinking Water Information System (SDWIS) records as privately owned: the community-run systems known as non-PRASA, which EPA Region 2 defines as the privately owned systems, and a few private developments and institutions. SDWIS records some community-run systems as local government, so this count can miss a few. A system that serves several municipalities counts in each; Puerto Rico's value counts each system once. Names are never published: many systems are named after a person, a family or a farm.",
            {str(year): with_island(np_n, np_all)}, noPerHU=True, classes="jenks"),
        var("water_nonprasa_pop", G1, "Residents served by community water systems outside PRASA", "", 0, "count", ["epa_echo_sdwa"], W,
            "The population that the non-PRASA systems (privately owned in SDWIS) report serving, added up for the systems that serve only this municipality. A system that serves several municipalities is left out of every municipality's value, because its population cannot be split, and is counted in Puerto Rico's value. The population served is the system's own estimate.",
            {str(year): with_island(np_pop, np_pop_all)}, noPerHU=True, classes="jenks"),
        var("wastewater_permits", G4, "Facilities with a permit to discharge wastewater", "", 0, "count", ["epa_echo_cwa"], WW,
            "Facilities with an active individual permit to discharge wastewater into rivers, lakes or the sea (a permit of the National Pollutant Discharge Elimination System, NPDES, which EPA issues in Puerto Rico): sewage treatment plants, water filtration plants, power plants, factories and others, in the municipality that holds the facility's point. Not counted: the facilities covered by a general permit (construction sites and stormwater), which come and go with each project.",
            {str(year): column(ww_n)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("wastewater_plants", G4, "Public sewage treatment plants", "", 0, "count", ["epa_echo_cwa"], WW,
            "Of those facilities, the publicly owned treatment works (POTW): the plants that treat the sewage of homes and businesses before it is discharged. In Puerto Rico the Aqueduct and Sewer Authority (PRASA) runs nearly all of them. A plant counts in the municipality where it stands, which may not be the only one it serves.",
            {str(year): column(ww_potw)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("wastewater_major", G4, "Major wastewater dischargers", "", 0, "count", ["epa_echo_cwa"], WW,
            "Of those facilities, the ones EPA classes as major: sewage treatment plants built to treat 1 million gallons a day or more, and industrial facilities that EPA scores as major for the volume or the pollutants of their discharge.",
            {str(year): column(ww_major)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("wastewater_violation", G4, "Wastewater dischargers with a violation on record", "", 0, "count", ["epa_echo_cwa"], WW,
            "Of those facilities, the ones whose current status in ECHO is 'Violation Identified' or 'Significant/Category I Noncompliance': a discharge above a permit limit, a missed deadline of a compliance schedule, or a monitoring report that was late or never sent. It is a compliance record of the last reported quarter, not a measure of how clean the water is today, and a late report counts the same as a discharge above a limit.",
            {str(year): column(ww_vio)}, noPerHU=True, classes="jenks"),
        var("air_sources", G5, "Facilities regulated for air pollution", "", 0, "count", ["epa_echo_caa"], AIR,
            "Active stationary sources of air pollution that the Clean Air Act regulates and EPA's ECHO lists: power plants, factories, quarries and asphalt plants, fuel terminals, hospitals and others with boilers, generators or processes that emit into the air, in the municipality that holds the facility's point. Most are minor sources. Cars, trucks and other moving sources are not facilities and are not counted.",
            {str(year): column(air_n)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("air_major", G5, "Major sources of air pollution", "", 0, "count", ["epa_echo_caa"], AIR,
            "Of those facilities, the ones EPA classes as major emissions sources: they emit, or could emit, more than the Clean Air Act's thresholds (in most areas 100 tons a year of a regulated pollutant, or 10 tons a year of one hazardous air pollutant), and need a Title V operating permit. Major is a class of size, not a finding that the facility breaks its permit.",
            {str(year): column(air_major)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("hazwaste_handlers", G6, "Hazardous waste handlers", "", 0, "count", ["epa_echo_rcra"], HZ,
            "Active handlers of hazardous waste that EPA's ECHO lists under the Resource Conservation and Recovery Act (RCRA): the businesses and institutions that generate hazardous waste (factories, laboratories, hospitals, auto shops, dry cleaners and others), and those that transport, treat or store it, in the municipality that holds the handler's point. Most generate very small amounts.",
            {str(year): column(hz_n)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("hazwaste_large", G6, "Large generators of hazardous waste", "", 0, "count", ["epa_echo_rcra"], HZ,
            "Of those handlers, the large quantity generators: they generate 1,000 kilograms or more of hazardous waste in a month (or more than 1 kilogram of acutely hazardous waste), and must follow the strictest rules for storing, shipping and reporting it. Large is a class of amount, not a finding that the handler breaks the rules.",
            {str(year): column(hz_large)}, noPerHU=True, classes="jenks", barrioFile=OUT_BARRIO.name),
        var("epa_inspected", G7, "Facilities inspected for environmental compliance", "", 0, "count", ["epa_echo_all"], ENF,
            "Of the active facilities that EPA regulates under the air, water, hazardous waste or drinking water laws, the ones that EPA or the Puerto Rico government inspected at least once in the last five years, in the municipality that holds the facility's point. An inspection is a routine check, not a finding that something is wrong.",
            {str(year): column(rg_insp)}, noPerHU=True, classes="jenks"),
        var("epa_formal_action", G7, "Facilities with a formal environmental enforcement action", "", 0, "count", ["epa_echo_all"], ENF,
            "Of those facilities, the ones that received at least one formal enforcement action in the last five years: an order or a court case in which EPA or the Puerto Rico government requires the facility to correct a violation, with or without a penalty. A warning letter or notice of violation is an informal action and is not counted.",
            {str(year): column(rg_formal)}, noPerHU=True, classes="jenks"),
        var("tri_release_lb", G8, "Toxic chemicals released, pounds", "lb", 0, "count", ["epa_tri"], TRI,
            f"The pounds of listed toxic chemicals that the facilities reporting to EPA's Toxics Release Inventory released in {td['year']}, on site (to the air, to water, to land) and off site (sent elsewhere for disposal), summed for the municipality that holds each facility's point. Only larger facilities in certain industries report, and only for the chemicals on EPA's list. Pounds of different chemicals are added together, so the figure shows amount, not toxicity or risk.",
            {str(year): wcolumn(tr_total)}, noPerHU=True, classes="jenks"),
        var("tri_air_lb", G8, "Toxic chemicals released to the air, pounds", "lb", 0, "count", ["epa_tri"], TRI,
            f"Of those pounds, the ones released on site to the air in {td['year']}, from stacks and vents and as leaks and evaporation (fugitive emissions). Pounds of different chemicals are added together, so the figure shows amount, not toxicity or risk.",
            {str(year): wcolumn(tr_air)}, noPerHU=True, classes="jenks"),
        var("power_plants", G2, "Power plants (operating)", "", 0, "count", ["eia_860m"], "EIA-860M, operating generators",
            "Plants with at least one operating generator in EIA's monthly inventory, in the municipality that holds the plant's point. Plants whose generators add up to less than 1 MW, most rooftop solar among them, are not in the inventory.",
            {str(year): column(plant_n)}, noPerHU=True, classes="jenks"),
        var("power_mw", G2, "Generating capacity, MW (nameplate)", "MW", 1, "count", ["eia_860m"], "EIA-860M, operating generators",
            "The nameplate capacity of the operating generators in the municipality, in megawatts: how much the generators are built to produce, not what they produce. Batteries are left out (they store power).",
            {str(year): rcolumn(mw)}, noPerHU=True, classes="jenks"),
        var("power_renewable_mw", G2, "Renewable generating capacity, MW (solar, wind, hydro, landfill gas)", "MW", 1, "count", ["eia_860m"], "EIA-860M, operating generators",
            "The nameplate capacity of the operating solar, wind, hydroelectric and landfill gas generators in the municipality, in megawatts. Rooftop solar is not in EIA's inventory.",
            {str(year): rcolumn(ren)}, noPerHU=True, classes="jenks"),
    ]
    # bridges, every year
    bvals = {k: {} for k in ("bridges", "bridges_poor", "bridges_poor_pct")}
    bnotes = {}
    for y in range(NBI_FIRST, date.today().year + 1):
        rows = bridge_rows(y, refresh, offline)
        if not rows:
            continue
        if floors and len(rows) < floors["bridges"]:
            raise SystemExit(f"infrastructure_series: {y}: {len(rows)} bridges (2025 has 2,434)")
        n, poor, unrated, agree, given = Counter(), Counter(), 0, 0, 0
        for r in rows:
            f = "72" + r["COUNTY_CODE_003"].zfill(3)
            if f not in ids:
                raise SystemExit(f"infrastructure_series: NBI {y}: a bridge has the county code {r['COUNTY_CODE_003']!r}")
            c = condition(r)
            n[f] += 1
            if c is None:
                unrated += 1
            poor[f] += c == "P"
            if r.get("BRIDGE_CONDITION"):
                given += 1
                agree += r["BRIDGE_CONDITION"] == c
        bvals["bridges"][str(y)] = column(n)
        bvals["bridges_poor"][str(y)] = column(poor)
        pct = [round(poor.get(f, 0) / n[f] * 100, 2) if n.get(f) else None for f in ids]
        bvals["bridges_poor_pct"][str(y)] = pct + [round(sum(poor.values()) / sum(n.values()) * 100, 2)]
        bnotes[str(y)] = {"bridges": sum(n.values()), "poor": sum(poor.values()), "unrated": unrated, "fhwa_condition_given": given, "fhwa_condition_agrees": agree}
        if given and agree != given:
            raise SystemExit(f"infrastructure_series: NBI {y}: the condition worked out by FHWA's rule differs from the file's own for {given - agree} bridges")
    G3, NB = "Bridges", "FHWA National Bridge Inventory"
    bv = [
        var("bridges", G3, "Highway bridges", "", 0, "count", ["fhwa_nbi"], NB, "Bridges of the public road network in the National Bridge Inventory (spans longer than 20 feet), in the municipality the inventory gives. A year is the inventory submitted that year.", bvals["bridges"], noPerHU=True),
        var("bridges_poor", G3, "Bridges in poor condition", "", 0, "count", ["fhwa_nbi"], NB, "Bridges whose lowest rating of deck, superstructure, substructure or culvert is 4 or below (FHWA's definition of poor). Poor does not mean unsafe: an unsafe bridge is closed.", bvals["bridges_poor"], noPerHU=True),
        var("bridges_poor_pct", G3, "Bridges in poor condition, % of bridges", "%", 1, "rate", ["fhwa_nbi"], NB, "Bridges in poor condition (FHWA's definition) out of all the municipality's bridges, by count, in percent.", bvals["bridges_poor_pct"]),
    ]
    notes = {"water": {"systems": len(wr), "serving_several_municipalities": multi, "with_no_municipality": island_only, "population_served_island": pop, "note": "A system that serves several municipalities counts in each; its population is not split.",
                       "non_prasa": {"systems": np_all, "population_served": np_pop_all, "serving_several_municipalities": np_multi, "population_of_those_left_out_of_municipal_values": np_multi_pop,
                                     "with_a_health_based_violation": np_health, "rule": "SDWIS owner type P (privately owned)"}},
             "wastewater": {"fetched": wd["fetched"], "individual_permits": len(ww), "public_sewage_treatment_plants": sum(ww_potw.values()), "major": sum(ww_major.values()),
                            "with_a_violation_on_record": sum(ww_vio.values()), "in_significant_noncompliance": sum(r["CWPStatus"] == CWA_SNC for r in ww),
                            "active_records_by_permit_type": wd["types"], "county_code_differs_from_the_point": ww_fips_differs,
                            "note": "Only individual permits are counted. A facility is placed by its point; its name and point are not kept."},
             "air": {"fetched": ad["fetched"], "active_sources": len(air), "by_class": dict(Counter(r["AIRClassification"] for r in air)), "major": sum(air_major.values()),
                     "temporarily_closed": sum(r["AIRStatus"] != "Operating" for r in air), "with_a_high_priority_violation": sum(r["AIRComplStatus"] == AIR_HPV for r in air),
                     "county_code_differs_from_the_point": air_fips_differs,
                     "note": "A source is placed by its point; its name and point are not kept. The sources with a violation are too few to publish for each municipality: the count is given for Puerto Rico only."},
             "hazwaste": {"fetched": hd["fetched"], "active_handlers": len(hz), "by_class": dict(Counter(r["RCRAUniverse"] for r in hz)), "large_quantity_generators": sum(hz_large.values()),
                          "with_a_violation_on_record": sum(r["RCRAComplStatus"] != RCRA_CLEAR for r in hz), "county_code_differs_from_the_point": hz_fips_differs,
                          "note": "A handler is placed by its point; its name and point are not kept. The handlers with a violation are too few to publish for each municipality: the count is given for Puerto Rico only."},
             "enforcement": {"fetched": gd["fetched"], "active_regulated_facilities": len(rg), "inspected_in_five_years": sum(rg_insp.values()),
                             "with_a_formal_action_in_five_years": sum(rg_formal.values()), "inspections": sum(count(r["FacInspectionCount"]) for r in rg),
                             "formal_actions": sum(count(r["FacFormalActionCount"]) for r in rg),
                             "placed_by_county_code": rg_by_code, "not_placed": rg_unplaced,
                             "note": "A facility is placed by its point; its name and point are not kept. A drinking water system is placed at the point ECHO gives it, often its office."},
             "tri": {"fetched": td["fetched"], "reporting_year": td["year"], "facilities": len(tr), "facilities_reporting_no_release": sum(r["total_lb"] == 0 for r in tr),
                     "total_lb": round(sum(r["total_lb"] for r in tr)), "air_lb": round(sum(r["air_lb"] for r in tr)), "largest_facility_share_pct": round(100 * max(r["total_lb"] for r in tr) / sum(r["total_lb"] for r in tr), 1),
                     "municipalities_with_a_facility": len(tr_fac), "municipalities_with_one_facility": sum(n == 1 for n in tr_fac.values()),
                     "note": "Pounds are summed by municipality; no name or point is kept. In a municipality with one reporting facility the figure is that facility's own public report."},
             "power": {"month": month, "generators": len(pr), "plants": len({r["Plant ID"] for r in pr}), "capacity_mw_by_technology": {k: round(v, 1) for k, v in techs.most_common()}}}
    base = {"geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "sources": {k: SOURCES[k] for k in ("epa_echo_sdwa", "epa_echo_cwa", "epa_echo_caa", "epa_echo_rcra", "epa_echo_all", "epa_tri", "eia_860m")}}
    snap = {"as_of": month, "years": [year], **base, "vars": vs, "notes": notes}
    br = {"years": sorted(int(y) for y in bvals["bridges"]), "geo": base["geo"], "vars": bv, "sources": {"fhwa_nbi": SOURCES["fhwa_nbi"]}, "notes": bnotes}
    return snap, br


def barrio(snap, offline=False):
    """The datasets of BARRIO_KEYS for the 901 barrios: each facility counted in the barrio whose outline holds its point, or the nearest outline within 2 km
    (conditions.py's rule for EPA sites). Reads the rows compute() has just cached. The municipality's count stands as compute() made it, by the municipal
    boundary; the notes say how many facilities fall in a barrio of another municipality by the barrio outlines, and how many no barrio holds."""
    import conditions as cn
    B = cn.Barrios()
    ww, air, hz = wastewater_rows(False, offline)["rows"], air_rows(False, offline)["rows"], hazwaste_rows(False, offline)["rows"]
    large = lambda r: RCRA_LARGE in [c.strip() for c in r["RCRAUniverse"].split(",")]
    sets = {"wastewater_permits": ww, "wastewater_plants": [r for r in ww if r["CWPFacilityTypeIndicator"] == "POTW"], "wastewater_major": [r for r in ww if r["CWPMajorMinorStatusFlag"] == "M"],
            "air_sources": air, "air_major": [r for r in air if r["AIRClassification"] == AIR_MAJOR], "hazwaste_handlers": hz, "hazwaste_large": [r for r in hz if large(r)]}
    assert tuple(sets) == BARRIO_KEYS
    year, col = str(snap["years"][0]), {v["key"]: v["years"] for v in snap["vars"]}
    mids = snap["geo"]["ids"]
    vs, notes = [], {}
    for key, rows in sets.items():
        pts = [(float(r["FacLong"]), float(r["FacLat"])) for r in rows]
        nb, nm, total, unplaced = cn.counts_by_area(B, pts)
        muni = dict(zip(mids, col[key][year]))
        if total != muni["72"]:
            raise SystemExit(f"infrastructure_series: {key} has {total} facilities by barrio and {muni['72']} by municipality")
        notes[key] = {"facilities": len(pts), "placed": len(pts) - unplaced, "outside_every_barrio": unplaced, "barrios_with_one_or_more": sum(n > 0 for n in nb),
                      "municipalities_whose_barrios_add_up_to_another_count": sum(nm.get(f, 0) != muni[f] for f in mids if f != "72")}
        vs.append({"key": key, "years": {year: nb}})
    return {"level": "barrio", "geo": {"ids": B.ids}, "vars": vs,
            "notes": {"areas": len(B.ids), "source": "infrastructure_series.py; the municipality values and the method are in infrastructure_series.json",
                      "how": "A facility is counted in the barrio whose outline holds its point, or the nearest outline within 2 km. No name or point is kept.", "counts": notes}}


def build(refresh=False, check=False):
    snap, br = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT, snap), (OUT_BR, br), (OUT_BARRIO, barrio(snap, offline=check))):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python infrastructure_series.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {len(d['vars'])} variables, {path.stat().st_size / 1024:.1f} KB")
        if path == OUT_BARRIO:
            for k, n in d["notes"]["counts"].items():
                log(f"  {k}: {n['facilities']} facilities in {n['barrios_with_one_or_more']} barrios, {n['outside_every_barrio']} outside every barrio, {n['municipalities_whose_barrios_add_up_to_another_count']} municipalities differ")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
