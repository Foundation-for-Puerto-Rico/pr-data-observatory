"""Local conditions for the PR Data Observatory, for the 901 barrios and the 78 municipios: EPA-regulated sites (Toxics Release Inventory, Risk Management Plan,
Superfund National Priorities List, municipal solid waste landfills), impaired waters and air quality non-attainment areas, households with severe housing problems,
street intersection density and the drive time to the nearest general hospital.

    python conditions.py                          # build site/data/conditions_series.json and site/data/conditions_barrio.json (downloads only what is missing from cache/conditions/)
    python conditions.py --refresh                # download every source again
    python conditions.py --refresh tri,frs        # download only these sources again (tri, frs, attains, greenbook, lmop, chas, tiger, hospitals); the others come from the cache
    python conditions.py --check                  # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources (no key; each read through its live service; each dataset carries its own vintage in its `ref` and in notes.vintages):
  tri        EPA Toxics Release Inventory, Basic Data File for Puerto Rico, the newest reporting year EPA has published (Envirofacts download service).
  frs        EPA Facility Registry Service, Facility Interests map service: Risk Management Plan facilities that FRS marks active, and Superfund National Priorities
             List sites (layer SEMS_NPL) currently on the final list.
  attains    EPA ATTAINS assessment units (the hosted feature service of EPA's Office of Water), the areas layer for Puerto Rico: the units on the 303(d) list.
  greenbook  EPA Green Book non-attainment areas (OAR/OAQPS map service): lead (2008 standard) and sulfur dioxide (1-hour, 2010 standard), areas in non-attainment now.
  lmop       EPA Landfill Methane Outreach Program, "All Landfills in LMOP Database with Coordinates" (EPA's hosted feature service): municipal solid waste landfills.
  chas       HUD Comprehensive Housing Affordability Strategy (CHAS) data by census tract, HUD's eGIS feature service: households with one or more of the four severe
             housing problems. HUD User's newer release (2018-2022) refuses scripted downloads; the eGIS service is the newest release a script may read (2016-2020).
  tiger      US Census Bureau TIGER/Line EDGES files, the newest year, the 78 municipios: street intersections.
  hospitals  CMS Hospital General Information (acute care hospitals with emergency services), each located by the OpenStreetMap hospital of its municipio whose name
             matches (the observatory's place index, gazetteer.json), else by an OpenStreetMap hospital within 1 km of HHS's geocoded address whose name shares a word,
             else by HHS's geocoded hospital address itself (healthdata.gov, COVID-19 Reported Patient Impact and Hospital Capacity by Facility, the last week each hospital
             reported; HHS's points sit up to several km from the building), else by a hand-checked point (HAND_POINTS).
All EPA data: the EPA Standard Open Data License (public domain, 17 U.S.C. 105). HUD eGIS: U.S. Public Domain. TIGER/Line: US Government work. CMS and HHS: public domain.

How each figure is made (docs/conditions.md has the full method):
  - Sites are counted in the barrio whose outline (site/data/barrios.geojson) holds the point, or the nearest outline within 2 km (a point on the coast); a municipio's
    count is the sum of its barrios; Puerto Rico's adds the sites no barrio holds.
  - Impaired waters and non-attainment: the share of the barrio's area (as drawn) inside the areas, measured on an equal-area projection. A barrio "touches" one when
    its share is above zero. A municipio's share is worked out from the areas of its barrios.
  - Severe housing problems: tract counts (households with one or more severe problems, and all households) are spread over barrios in proportion to the 2020
    housing units each barrio has in the tract (geo/crosswalk.json weights; docs/geography.md, section 4), then divided. The barrio values are ESTIMATES; the
    municipio values are exact sums of their tracts.
  - Intersection density: TIGER/Line topological nodes where three or more street edges meet (MTFCC S1200, S1400, S1730, S1740; limited-access highways, ramps, service
    drives, trails, walkways and parking lot roads are left out), per square mile of land (2020 Census land area). The observatory's roads.bin comes from OpenStreetMap,
    not TIGER, so it is not used here.
  - Drive time: from the barrio's population-weighted point (the mean of its 2020 census blocks' internal points weighted by residents; the barrio's internal point when
    no one lives there) to the nearest general hospital, along roads.bin (OpenStreetMap) at the observatory's planning speeds, as care_access.py measures the distance to a
    health center (both directions of a one-way road, free flow). A barrio that holds a hospital is 0. Vieques and Culebra (and Mona) have no road link to a hospital, and
    an uninhabited barrio may have no road within 2 km of its internal point: no value, and the dataset says why (noValue). A municipio's figure is the average of its
    barrios weighted by 2020 residents; Puerto Rico's leaves out the residents with no value (Vieques and Culebra, about 10,000).

What is kept. No personal data and no business contact details: only the columns in KEEP reach the cache. Facility names and points of EPA sites stay in the local cache
(the published files hold counts and shares only); hospital points are cached without names or certification numbers.
"""

import csv
import io
import json
import math
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "conditions"
OUT = hs.OUT
OUT_SERIES = OUT / "conditions_series.json"
OUT_BARRIO = OUT / "conditions_barrio.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
SOURCE_KEYS = ("tri", "frs", "attains", "greenbook", "lmop", "chas", "tiger", "hospitals")
log = hs.log

TRI_URL = "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/{y}_PR/csv"
FRS = "https://geodata.epa.gov/arcgis/rest/services/OEI/FRS_INTERESTS/MapServer"
ATTAINS = "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/ATTAINS_Assessment/FeatureServer/2"
GREENBOOK = "https://gispub.epa.gov/arcgis/rest/services/OAR_OAQPS/NonattainmentAreas/MapServer"
GREENBOOK_LAYERS = {3: "lead", 4: "so2"}   # Lead (2008 standard), SO2 1-hr (2010 standard)
LMOP = "https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/New_Landfills/FeatureServer/0"
CHAS = "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/ACS_5YR_ESTIMATES_CHAS_TRACT/FeatureServer/1"
CHAS_ITEM = "https://www.arcgis.com/sharing/rest/content/items/db5099395be44cbd8c6896136dbd5e7e"
TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER{y}/EDGES/tl_{y}_{fips}_edges.zip"
CMS_HOSPITALS = "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0"
HHS_POINTS = "https://healthdata.gov/resource/anag-cw7u.json"

KEEP = {   # the only columns that reach the cache (besides lon and lat); a test checks that none can hold a telephone, an e-mail, a person's name or a street address
    "tri": ["year", "trifd", "name", "sector"],
    "frs": ["registry_id", "name", "program", "status"],
    "attains": ["assessmentunitidentifier", "assessmentunitname", "ircategory", "isimpaired", "on303dlist", "reportingcycle"],
    "greenbook": ["composite_id", "area_name", "pollutant", "current_status"],
    "lmop": ["name", "status", "category", "opened", "closed"],
    "chas": ["GEOID", "T2_EST1", "T2_EST3", "T2_EST127"],
    "hospitals": ["located", "county"],
}
FLOORS = {"tri": 60, "rmp": 15, "npl": 10, "attains": 200, "greenbook": 2, "lmop": 20, "chas": 900, "tiger": 50000, "hospitals": 40}   # 2026-10-17: 104 TRI facilities, 33 RMP, 18 NPL, 336 units, 3 areas, 32 landfills, 942 tracts, 52 hospitals
NEAR_KM = 2.0   # a point within this distance of a barrio outline (a coastal site) is placed in the nearest one
STREET_MTFCC = {"S1200", "S1400", "S1730", "S1740"}   # secondary roads, local streets, alleys, private roads; not S1100 (limited access), S1630 (ramps), S1640 (service drives), trails, walkways, stairways, parking lots, bike and bridle paths
SNAP_M = 2000
LAEA = "+proj=laea +lat_0=18.2 +lon_0=-66.5 +datum=WGS84 +units=m +no_defs"   # equal-area plane for Puerto Rico
SQKM_PER_SQMI = 2.589988110336

# A hospital that neither OpenStreetMap (by name) nor HHS locates can be placed by hand here, after a person checks its building: CMS certification number (a public
# facility identifier; it is not cached or published) -> (how it was checked, longitude, latitude). Empty on 2026-10-17: every general hospital was located.
HAND_POINTS = {}
NAME_MATCH = 0.6   # the share of name words a CMS hospital and an OpenStreetMap hospital of the same municipio must share (Jaccard; generic words left out)
NEAR_HHS_KM = 1.0   # the second rule (near_hhs): an OpenStreetMap hospital this close to HHS's point whose name shares a word with CMS's (8 hospitals on 2026-10-17)
HOSPITAL_NAME = re.compile(r"\bhospital\b|\bmedical cent(?:er|re)\b|\bcentro medico\b")   # what an OpenStreetMap name must say for the second rule
NAME_STOP = {"hospital", "hosp", "de", "del", "la", "el", "los", "las", "y", "and", "inc", "corp", "llc", "the", "of", "center", "centre", "centro", "medical", "medico", "pr", "puerto",
             "rico", "dr", "san", "general", "community", "regional", "health", "system", "i", "ii"}
GENERAL_HOSPITAL_TYPES = {"Acute Care Hospitals", "Critical Access Hospitals"}   # not the VA, Department of Defense, psychiatric or children's hospitals

SOURCES = {
    "epa_tri": {"name": "EPA — Toxics Release Inventory (TRI), Basic Data File for Puerto Rico", "url": "https://www.epa.gov/toxics-release-inventory-tri-program/tri-basic-data-files-calendar-years-1987-present",
                "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105)",
                "note": "Facilities that filed a TRI report for the reporting year. The observatory counts them in each barrio and municipio; it publishes no name, address or point."},
    "epa_frs": {"name": "EPA — Facility Registry Service (FRS), Facility Interests (Risk Management Plan facilities, Superfund National Priorities List sites)", "url": "https://www.epa.gov/frs",
                "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105)",
                "note": "RMP facilities FRS marks active, and NPL sites currently on the final list. The observatory counts them; it publishes no name, address or point."},
    "epa_attains": {"name": "EPA — ATTAINS assessment units (Clean Water Act 303(d) list), Puerto Rico", "url": "https://www.epa.gov/waterdata/attains",
                    "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105)",
                    "note": "Puerto Rico maps its river and stream assessment units as the land that drains to them, so a listed unit covers its watershed, not only the water."},
    "epa_greenbook": {"name": "EPA — Green Book non-attainment areas (lead 2008, sulfur dioxide 2010)", "url": "https://www.epa.gov/green-book",
                      "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105); the service states no access or use constraints",
                      "note": "Areas EPA designates as not meeting the national air quality standard for lead or sulfur dioxide."},
    "epa_lmop": {"name": "EPA — Landfill Methane Outreach Program (LMOP), landfills with coordinates", "url": "https://www.epa.gov/lmop/lmop-landfill-and-project-database",
                 "license": "EPA Standard Open Data License: public domain (17 U.S.C. 105)",
                 "note": "Municipal solid waste landfills, open or closed. LMOP does not list every landfill, nor open dumps, transfer stations, industrial or hazardous waste landfills."},
    "hud_chas": {"name": "HUD — Comprehensive Housing Affordability Strategy (CHAS) data by census tract (eGIS)", "url": "https://hudgis-hud.opendata.arcgis.com/datasets/HUD::acs-5yr-chas-estimate-data-by-tract",
                 "license": "U.S. Public Domain (HUD's open data catalog); HUD adds a disclaimer of warranty and liability",
                 "note": "A custom tabulation of the American Community Survey that the Census Bureau makes for HUD. The barrio values are the observatory's estimates from the tracts."},
    "census_tiger_lines": {"name": "US Census Bureau — TIGER/Line Shapefiles, all lines (EDGES)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                           "license": "US Government work (no US copyright)",
                           "note": "The street network the intersections are counted on."},
    "cms_provider_data": {"name": "CMS — Provider Data Catalog (Hospital General Information)", "url": "https://data.cms.gov/provider-data/dataset/xubh-q36u",
                          "license": "US federal government data (public domain)",
                          "note": "Acute care hospitals that provide emergency services. Names, addresses and certification numbers are not kept."},
    "hhs_hospital_capacity": {"name": "HHS — COVID-19 Reported Patient Impact and Hospital Capacity by Facility (geocoded hospital addresses)", "url": "https://healthdata.gov/Hospital/COVID-19-Reported-Patient-Impact-and-Hospital-Capa/anag-cw7u",
                              "license": "Public Domain U.S. Government (as healthdata.gov states)",
                              "note": "Used only for the geocoded point of the hospitals OpenStreetMap does not place by name; HHS stopped updating it in May 2024."},
    "osm": {"name": "OpenStreetMap contributors (roads; hospital buildings)", "url": "https://www.openstreetmap.org/copyright", "license": "Open Database License (ODbL) 1.0",
            "note": "The road graph the drive time is measured on (roads.bin), and the building of each hospital whose name OpenStreetMap maps in the same municipio (the observatory's place index, gazetteer.json)."},
    "census_tiger": {"name": "US Census Bureau — 2020 census blocks, county subdivisions and land area", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)",
                     "note": "Barrio outlines, land areas, the 2020 housing units that spread tract counts over barrios, and the residents that weigh each barrio's point."},
}


# ── Download ─────────────────────────────────────────────────────────────────

TRIES = 6
BUSY = {429, 500, 502, 503, 504}   # "too many requests" and a busy or failing server: wait and ask again


def backoff(attempt, retry_after=None):
    """Seconds to wait before asking again: the server's Retry-After when it gives one (at most 120), else 4, 8, 16, 32, 60, as build.py waits on ArcGIS servers."""
    try:
        s = float(retry_after)
    except (TypeError, ValueError):
        s = 0
    return min(120.0, s) if s > 0 else min(60, 4 * 2 ** attempt)


def get(url, tries=TRIES, **kw):
    """A GET with a polite retry: a 429 or a 5xx answer, a timeout or a dropped connection waits (backoff) and asks again; a 404 is returned to the caller."""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 300), **kw)
            if r.status_code == 404:
                return r
            if r.status_code in BUSY and attempt < tries - 1:
                wait = backoff(attempt, r.headers.get("Retry-After"))
                log(f"  {url}: HTTP {r.status_code}; waiting {wait:.0f} s before try {attempt + 2} of {tries}")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise SystemExit(f"conditions: {url} failed: {e}")
            time.sleep(backoff(attempt))


def arcgis(url, where, fields, geometry=True, page=2000, tries=TRIES):
    """Every feature of an ArcGIS REST query, page by page, as GeoJSON features (WGS 84). ArcGIS Online can also answer a busy server inside the JSON (HTTP 200 with
    {"error": {"code": 429}}): that page is asked for again after the same backoff."""
    out, off = [], 0
    while True:
        for attempt in range(tries):
            d = get(url + "/query", params={"where": where, "outFields": ",".join(fields), "returnGeometry": "true" if geometry else "false", "outSR": 4326, "f": "geojson" if geometry else "json",
                                            "resultOffset": off, "resultRecordCount": page, "geometryPrecision": 6}).json()
            code = (d.get("error") or {}).get("code") if isinstance(d.get("error"), dict) else None
            if code in BUSY and attempt < tries - 1:
                wait = backoff(attempt)
                log(f"  {url}: answered {code} at offset {off}; waiting {wait:.0f} s before try {attempt + 2} of {tries}")
                time.sleep(wait)
                continue
            break
        if "error" in d:
            raise SystemExit(f"conditions: {url} answered {str(d['error'])[:300]}")
        feats = d.get("features") or []
        out += feats
        more = d.get("exceededTransferLimit") or (d.get("properties") or {}).get("exceededTransferLimit")
        if not feats or not more:
            return out
        off += len(feats)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat() if ms else None


def fetch_tri():
    """The newest reporting year EPA has published for Puerto Rico: one row per facility (the file has one row per chemical)."""
    this = date.today().year
    for y in range(this, this - 4, -1):
        r = get(TRI_URL.format(y=y))
        if r.status_code == 404 or not r.text.startswith("1. YEAR"):
            continue
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig", errors="replace"))))
        h = rows[0]
        col = lambda name: h.index(name)
        i = {k: col(n) for k, n in (("year", "1. YEAR"), ("trifd", "2. TRIFD"), ("name", "4. FACILITY NAME"), ("lat", "12. LATITUDE"), ("lon", "13. LONGITUDE"), ("sector", "23. INDUSTRY SECTOR"), ("st", "8. ST"))}
        fac = {}
        for x in rows[1:]:
            if len(x) < len(h):
                continue
            if x[i["st"]] != "PR":
                raise SystemExit("conditions: the TRI file for Puerto Rico holds a facility in another state")
            fac.setdefault(x[i["trifd"]], {"year": int(x[i["year"]]), "trifd": x[i["trifd"]], "name": x[i["name"]], "sector": x[i["sector"]],
                                            "lon": float(x[i["lon"]]) if x[i["lon"]] else None, "lat": float(x[i["lat"]]) if x[i["lat"]] else None})
        return {"vintage": str(y), "rows": sorted(fac.values(), key=lambda r: r["trifd"])}
    raise SystemExit("conditions: no TRI Basic Data File for Puerto Rico in the last four years")


def fetch_frs():
    rows = []
    for layer, where, prog in ((8, "STATE_CODE='PR' AND PGM_SYS_ACRNM='RMP'", "rmp"), (22, "STATE_CODE='PR'", "npl")):
        for f in arcgis(f"{FRS}/{layer}", where, ["REGISTRY_ID", "PRIMARY_NAME", "ACTIVE_STATUS"]):
            p, g = f["properties"], f.get("geometry") or {}
            c = g.get("coordinates") or [None, None]
            rows.append({"registry_id": p["REGISTRY_ID"], "name": p["PRIMARY_NAME"], "program": prog, "status": p["ACTIVE_STATUS"], "lon": c[0], "lat": c[1]})
    meta = get(FRS, params={"f": "json"}).json()
    return {"vintage": date.today().isoformat(), "service": (meta.get("documentInfo") or {}).get("Title"), "rows": sorted(rows, key=lambda r: (r["program"], r["registry_id"]))}


def fetch_attains():
    meta = get(ATTAINS, params={"f": "json"}).json()
    feats = arcgis(ATTAINS, "state='PR'", KEEP["attains"], page=500)
    rows = [{**{k: f["properties"].get(k) for k in KEEP["attains"]}, "geometry": f["geometry"]} for f in feats if f.get("geometry")]
    cycles = sorted({r["reportingcycle"] for r in rows if r["reportingcycle"]})
    return {"vintage": str(cycles[-1]) if cycles else None, "edited": iso((meta.get("editingInfo") or {}).get("dataLastEditDate")), "rows": rows}


def fetch_greenbook():
    rows = []
    for layer, pol in GREENBOOK_LAYERS.items():
        for f in arcgis(f"{GREENBOOK}/{layer}", "state_abbreviation='PR'", ["composite_id", "area_name", "pollutant_name", "current_status"]):
            p = f["properties"]
            rows.append({"composite_id": p["composite_id"], "area_name": p["area_name"], "pollutant": pol, "current_status": p["current_status"], "geometry": f["geometry"]})
    return {"vintage": date.today().isoformat(), "rows": rows}


def fetch_lmop():
    meta = get(LMOP, params={"f": "json"}).json()
    rows = []
    for f in arcgis(LMOP, "county_state LIKE '%, PR'", ["landfill_name", "current_landfill_status", "category", "year_landfill_opened", "landfill_closure_year", "latitude", "longitude"], geometry=False):
        a = f["attributes"]
        rows.append({"name": a["landfill_name"], "status": a["current_landfill_status"], "category": a["category"], "opened": a["year_landfill_opened"], "closed": a["landfill_closure_year"],
                     "lon": a["longitude"], "lat": a["latitude"]})
    return {"vintage": iso((meta.get("editingInfo") or {}).get("dataLastEditDate")), "rows": sorted(rows, key=lambda r: r["name"] or "")}


def fetch_chas():
    item = get(CHAS_ITEM, params={"f": "json"}).json()
    text = re.sub(r"<[^>]+>", " ", item.get("description") or "")
    m = re.search(r"Date of Coverage:?\W*(\d{4})\s*-\s*(\d{4})", text) or re.search(r"(\d{4})\s*-\s*(\d{4})\s+American Community Survey", text)
    if not m:
        raise SystemExit("conditions: the CHAS item no longer states its date of coverage; read it before going on")
    feats = arcgis(CHAS, "STATE='72'", KEEP["chas"], geometry=False)
    rows = [{k: f["attributes"].get(k) for k in KEEP["chas"]} for f in feats]
    meta = get(CHAS, params={"f": "json"}).json()
    return {"vintage": f"{m.group(1)}-{m.group(2)}", "edited": iso((meta.get("editingInfo") or {}).get("dataLastEditDate")), "rows": sorted(rows, key=lambda r: r["GEOID"])}


def fetch_tiger():
    """The street edges of the 78 municipios from the newest TIGER/Line year: [tlid, mtfcc, from node, to node] and each node's point."""
    import shapefile
    names, fips = hs.municipalities()
    year = None
    for y in range(date.today().year, date.today().year - 3, -1):
        r = requests.head(TIGER_URL.format(y=y, fips=fips[0]), headers=UA, timeout=60)
        if r.status_code == 200:
            year = y
            break
    if year is None:
        raise SystemExit("conditions: no TIGER/Line EDGES file for Puerto Rico in the last three years")
    edges, nodes = {}, {}
    for f in fips:
        z = zipfile.ZipFile(io.BytesIO(get(TIGER_URL.format(y=year, fips=f)).content))
        base = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        sf = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), shx=io.BytesIO(z.read(base + ".shx")), dbf=io.BytesIO(z.read(base + ".dbf")))
        fields = [x[0] for x in sf.fields[1:]]
        ix = {k: fields.index(k) for k in ("TLID", "TNIDF", "TNIDT", "MTFCC", "ROADFLG")}
        for sr in sf.iterShapeRecords():
            rec = sr.record
            if rec[ix["ROADFLG"]] != "Y":
                continue
            pts = sr.shape.points
            if not pts:
                continue
            a, b = int(rec[ix["TNIDF"]]), int(rec[ix["TNIDT"]])
            edges[int(rec[ix["TLID"]])] = [rec[ix["MTFCC"]], a, b]
            nodes.setdefault(a, [round(pts[0][0], 6), round(pts[0][1], 6)])
            nodes.setdefault(b, [round(pts[-1][0], 6), round(pts[-1][1], 6)])
        log(f"  TIGER {year} {f}: {len(edges)} road edges so far")
    return {"vintage": str(year), "rows": [[t, *e] for t, e in sorted(edges.items())], "nodes": {str(k): v for k, v in sorted(nodes.items())}}


def name_words(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return {w for w in re.findall(r"[a-z0-9]+", s) if w not in NAME_STOP and len(w) > 1}


def stem(w):
    """A name word without a final o, a or s, so Spanish and English forms meet ("metropolitano", "metropolitan"; "doctors", "doctor"). Used only by the second rule."""
    return w[:-1] if len(w) > 4 and w[-1] in "oas" else w


def named_hospital(name):
    """True when an OpenStreetMap name says hospital or medical center ("Hospital del Maestro", "Manatí Medical Center"), not a clinic, a plaza or a laboratory."""
    import unicodedata
    return bool(HOSPITAL_NAME.search(unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()))


def km_apart(a, b):
    return math.hypot((a[0] - b[0]) * 105.6, (a[1] - b[1]) * 110.8)


def osm_hospitals():
    """The hospitals and clinics of the observatory's OpenStreetMap place index (site/data/gazetteer.json, ODbL): [(name words, municipio, lon, lat, named a hospital)]."""
    g = json.loads((OUT / "gazetteer.json").read_text(encoding="utf-8"))
    k = g["kinds"].index("hospital")
    return [(name_words(x[0]), g["munis"][x[4]], x[2], x[1], named_hospital(x[0])) for x in g["items"] if x[3] == k]


def near_hhs(words, point, osm):
    """The second rule: the OpenStreetMap hospital (named a hospital or medical center) within NEAR_HHS_KM of HHS's point whose name shares the most words with
    CMS's (after stem(), at least one), when no other one there shares as many. Two independent signs (the name and HHS's address) must agree. (lon, lat) or None."""
    st = {stem(w) for w in words}
    near = sorted(((len(st & s) / len(st | s), lon, lat) for w, m, lon, lat, named in osm for s in [{stem(x) for x in w}]
                   if named and st & s and km_apart((lon, lat), point) <= NEAR_HHS_KM), reverse=True)
    if near and (len(near) == 1 or near[1][0] < near[0][0]):
        return near[0][1], near[0][2]
    return None


def fetch_hospitals():
    """The points of the general acute care hospitals with emergency services (CMS), cached without names or certification numbers. Each is located, in this order, by
    the OpenStreetMap hospital of the same municipio whose name shares at least NAME_MATCH of its words (a mapped building, "osm"), by the OpenStreetMap hospital near HHS's
    point that near_hhs() finds ("osm_near"), by HHS's geocoded address ("hhs"), or by HAND_POINTS. A hospital placed by name alone that HHS also places keeps HHS's point
    too (hhs_lon, hhs_lat), so the build can say how often the two fall in different barrios."""
    rows, off = [], 0
    while True:
        r = get(CMS_HOSPITALS, params={"conditions[0][property]": "state", "conditions[0][value]": "PR", "limit": 500, "offset": off}).json()
        page = r.get("results") or []
        rows += page
        if len(page) < 500:
            break
        off += 500
    general = [x for x in rows if x.get("hospital_type") in GENERAL_HOSPITAL_TYPES and x.get("emergency_services") == "Yes"]
    hhs = {}
    for x in get(HHS_POINTS, params={"$select": "ccn,geocoded_hospital_address,collection_week", "$where": "state='PR'", "$order": "collection_week", "$limit": 50000}).json():
        g = x.get("geocoded_hospital_address")
        if x.get("ccn") and g and g.get("coordinates"):
            hhs[x["ccn"]] = g["coordinates"]   # ordered by week: the last week a hospital reported wins
    osm = osm_hospitals()
    plain = lambda s: name_words(s) and " ".join(sorted(name_words(s)))
    out, missing, apart = [], [], []
    for x in general:
        ccn, words, muni = x["facility_id"], name_words(x.get("facility_name")), x.get("countyparish") or ""
        cands = sorted(((len(words & w) / len(words | w), lon, lat) for w, m, lon, lat, _ in osm if words and w and plain(m) == plain(muni)), reverse=True)
        near = near_hhs(words, hhs[ccn], osm) if ccn in hhs and words else None
        if cands and cands[0][0] >= NAME_MATCH and (len(cands) == 1 or cands[1][0] < cands[0][0]):
            how, lon, lat = "osm", cands[0][1], cands[0][2]
        elif near:
            how, (lon, lat) = "osm_near", near
        elif ccn in hhs:
            how, (lon, lat) = "hhs", hhs[ccn]
        elif ccn in HAND_POINTS:
            how, lon, lat = HAND_POINTS[ccn]
        else:
            missing.append(f"{x.get('facility_name')} ({x.get('citytown')})")
            continue
        row = {"located": how.split(" ")[0], "county": muni, "lon": round(float(lon), 5), "lat": round(float(lat), 5)}
        if how == "osm" and ccn in hhs:   # a hospital placed by its name alone that HHS also places: how far apart the two points are and (in the build) whether they fall in one barrio,
            apart.append(km_apart((lon, lat), hhs[ccn]))   # which says how far the HHS points of the other hospitals can be trusted (the second rule picks close ones, so it is left out)
            row["hhs_lon"], row["hhs_lat"] = round(float(hhs[ccn][0]), 5), round(float(hhs[ccn][1]), 5)
        out.append(row)
    if missing:
        raise SystemExit("conditions: CMS lists general hospitals that neither OpenStreetMap, HHS nor HAND_POINTS locates: " + "; ".join(missing)
                         + ". Find each one's building, check it, and add it to HAND_POINTS (or fix its name in OpenStreetMap).")
    return {"vintage": date.today().isoformat(), "listed": len(general), "osm_to_hhs_km": {"median": round(sorted(apart)[len(apart) // 2], 2), "max": round(max(apart), 2)} if apart else None,
            "rows": sorted(out, key=lambda r: (r["lon"], r["lat"]))}


FETCH = {"tri": fetch_tri, "frs": fetch_frs, "attains": fetch_attains, "greenbook": fetch_greenbook, "lmop": fetch_lmop, "chas": fetch_chas, "tiger": fetch_tiger, "hospitals": fetch_hospitals}


def floors(key, d):
    rows = d["rows"]
    if key == "frs":
        checks = {"rmp": sum(r["program"] == "rmp" and r["status"] == "ACTIVE" for r in rows), "npl": sum(r["program"] == "npl" and r["status"] == "CURRENTLY ON THE FINAL NPL" for r in rows)}
    elif key == "greenbook":
        checks = {"greenbook": len(rows)}
    else:
        checks = {key: len(rows)}
    for k, n in checks.items():
        if n < FLOORS[k]:
            raise SystemExit(f"conditions: {k} gave {n} rows (fewer than {FLOORS[k]}): the source changed; read it before going on")


def source(key, refresh=False, offline=False):
    path = CACHE / f"{key}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"conditions --check: {path.name} is not in the cache (python conditions.py makes it; --check never downloads)")
    log(f"  downloading {key}")
    d = FETCH[key]()
    floors(key, d)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  {key}: {len(d['rows'])} rows, vintage {d['vintage']}")
    return d


# ── Geography ────────────────────────────────────────────────────────────────

class Barrios:
    """The 901 barrios (site/data/barrios.geojson, in the crosswalk's order of ids), their land and residents (geo/crosswalk.json), point lookup and an equal-area plane."""

    def __init__(self):
        import numpy as np
        import shapely
        from pyproj import Transformer
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        self.np, self.shapely = np, shapely
        self.T = Transformer.from_crs("EPSG:4326", LAEA, always_xy=True)
        cw = json.loads((OUT / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
        F = {f: i for i, f in enumerate(cw["fields"])}
        self.cw = cw
        self.unit = {r[F["id"]]: {"km2": r[F["km2"]], "pop": r[F["pop"]], "hu": r[F["hu"]], "lat": r[F["lat"]], "lng": r[F["lng"]], "parent": r[F["parent"]]} for lv in ("barrio", "municipio") for r in cw["units"][lv]}
        self.ids = [r[F["id"]] for r in cw["units"]["barrio"]]
        fc = json.loads((OUT / "barrios.geojson").read_text(encoding="utf-8"))
        geo = {f["properties"]["geoid"]: shape(f["geometry"]) for f in fc["features"]}
        missing = [i for i in self.ids if i not in geo]
        if missing or len(geo) != len(self.ids):
            raise SystemExit(f"conditions: barrios.geojson and the crosswalk disagree ({len(geo)} outlines, {len(self.ids)} barrios; {missing[:3]} have no outline)")
        self.geoms = [geo[i] for i in self.ids]
        self.tree = STRtree(self.geoms)
        self.plane = [self.project(g) for g in self.geoms]
        self.area = [g.area for g in self.plane]
        self.names, self.mids = hs.municipalities()
        self.idx = {b: i for i, b in enumerate(self.ids)}

    def project(self, g):
        np = self.np
        return self.shapely.transform(g, lambda xy: np.column_stack(self.T.transform(xy[:, 0], xy[:, 1])))

    def at(self, lon, lat, tol_km=NEAR_KM):
        """The index of the barrio that holds the point, or of the nearest one within tol_km; None when farther."""
        from shapely.geometry import Point
        if lon is None or lat is None:
            return None
        p = Point(lon, lat)
        hit = [int(j) for j in self.tree.query(p, predicate="intersects")]
        if hit:
            return min(hit)
        j = int(self.tree.nearest(p))
        x, y = self.T.transform(lon, lat)
        return j if self.plane[j].distance(self.shapely.geometry.Point(x, y)) <= tol_km * 1000 else None

    def muni_of(self, i):
        return self.ids[i][:5]


def counts_by_area(B, points):
    """[count per barrio], {fips: count}, island total and how many points no barrio holds. points: [(lon, lat)]."""
    nb, unplaced = [0] * len(B.ids), 0
    for lon, lat in points:
        i = B.at(lon, lat)
        if i is None:
            unplaced += 1
        else:
            nb[i] += 1
    nm = Counter()
    for i, n in enumerate(nb):
        nm[B.muni_of(i)] += n
    return nb, nm, sum(nb) + unplaced, unplaced


def shares_by_area(B, geoms):
    """The share of each barrio's area (as drawn), of each municipio's and of the island's, inside the union of the geometries (WGS 84 GeoJSON)."""
    from shapely.geometry import shape
    from shapely.validation import make_valid
    if not geoms:
        z = [0.0] * len(B.ids)
        return z, {f: 0.0 for f in B.mids}, 0.0, [False] * len(B.ids)
    u = B.shapely.union_all([make_valid(B.project(shape(g))) for g in geoms])
    inter = []
    for g in B.plane:
        inter.append(g.intersection(u).area if g.intersects(u) else 0.0)
    pct = [round(100 * a / t, 2) if t else None for a, t in zip(inter, B.area)]
    num, den = Counter(), Counter()
    for i, (a, t) in enumerate(zip(inter, B.area)):
        num[B.muni_of(i)] += a
        den[B.muni_of(i)] += t
    mpct = {f: round(100 * num[f] / den[f], 2) if den[f] else None for f in B.mids}
    return pct, mpct, round(100 * sum(inter) / sum(B.area), 2), [a > 0 for a in inter]


# ── Severe housing problems: tracts to barrios ───────────────────────────────

def chas_by_area(B, rows):
    """Barrio estimates (spread from tracts by 2020 housing units) and exact municipio sums of households with one or more severe problems and of all households."""
    tract = {r["GEOID"]: (int(r["T2_EST3"] or 0) + int(r["T2_EST127"] or 0), int(r["T2_EST1"] or 0)) for r in rows}
    w = B.cw["weights"]["barrio_tract"]["rows"]   # [barrio, tract, residents, housing units, blocks]
    hu_t = Counter()
    for b, t, pop, hu, blocks in w:
        hu_t[t] += hu
    bn, bd = Counter(), Counter()
    no_weight = 0
    for b, t, pop, hu, blocks in w:
        if t not in tract or not hu_t[t]:
            continue
        s = hu / hu_t[t]
        bn[b] += tract[t][0] * s
        bd[b] += tract[t][1] * s
    for t, (n, d) in tract.items():
        if d and not hu_t[t]:
            no_weight += d   # households in a tract with no 2020 housing units: none in 2016-2020 (checked by the floor below)
    mn, md = Counter(), Counter()
    for t, (n, d) in tract.items():
        mn[t[:5]] += n
        md[t[:5]] += d
    missing_hu = sum(hu for t, hu in hu_t.items() if t not in tract)
    notes = {"tracts": len(tract), "tracts_with_households": sum(1 for v in tract.values() if v[1]), "households_in_tracts_without_2020_housing_units": no_weight,
             "housing_units_2020_in_tracts_chas_does_not_list": missing_hu}
    return bn, bd, mn, md, notes


# ── Street intersections ─────────────────────────────────────────────────────

def intersections(d):
    """Nodes where three or more street edges meet: [(lon, lat)]."""
    deg = Counter()
    for tlid, mtfcc, a, b in d["rows"]:
        if mtfcc in STREET_MTFCC:
            deg[a] += 1
            deg[b] += 1   # a loop (a == b) adds two legs
    return [tuple(d["nodes"][str(n)]) for n, k in sorted(deg.items()) if k >= 3]


# ── Drive time to a general hospital ─────────────────────────────────────────

def barrio_points(B):
    """Each barrio's population-weighted point (2020 census blocks with residents, site/data/population_blocks.json), or its internal point when no block with
    residents falls in it; and the residents counted."""
    blocks = json.loads((OUT / "population_blocks.json").read_text(encoding="utf-8"))
    sx, sy, sp = Counter(), Counter(), Counter()
    for r in blocks:
        lon, lat, pop = r[0], r[1], r[2]
        i = B.at(lon, lat)
        if i is None or not pop:
            continue
        sx[i] += lon * pop
        sy[i] += lat * pop
        sp[i] += pop
    pts, how = [], Counter()
    for i, b in enumerate(B.ids):
        if sp[i]:
            pts.append((sx[i] / sp[i], sy[i] / sp[i]))
            how["residents"] += 1
        else:
            pts.append((B.unit[b]["lng"], B.unit[b]["lat"]))
            how["internal_point"] += 1
    return pts, dict(how)


def drive(B, hospitals):
    """[(minutes, km) or None per barrio] from each barrio's point to the nearest general hospital, with notes."""
    import care_access
    import roads
    R = roads.Roads(OUT / "roads.bin")
    for i in range(len(R.eu)):   # both directions of a one-way road: a distance to care, not a driving route (care_access.py)
        if R.oneway[i]:
            R.adj[int(R.ev[i])].append((int(R.eu[i]), i, False))
    hp = [(r["lon"], r["lat"]) for r in hospitals]
    snapped = [R.snap(lon, lat, SNAP_M) for lon, lat in hp]
    src = [(s, s["dist"]) for s in snapped if s]
    km = care_access.search(R, src, lambda e, m: m)
    sec = care_access.search(R, [(s, d / roads.SPEED_MS[R.cls[s["edge"]]]) for s, d in src], lambda e, m: m / roads.SPEED_MS[R.cls[e]])
    holds = Counter(B.at(lon, lat, tol_km=0.5) for lon, lat in hp)
    pts, how = barrio_points(B)
    out, notes = [], {"hospitals": len(hp), "hospitals_snapped": len(src), "barrio_points": how, "barrios_with_a_hospital": sum(1 for k in holds if k is not None),
                      "no_road_link": []}
    for i, (lon, lat) in enumerate(pts):
        if holds.get(i):
            out.append((0.0, 0.0))
            continue
        s = care_access.snap_reachable(R, lon, lat, km)
        if not s:
            out.append(None)
            notes["no_road_link"].append(B.ids[i])
            continue
        e, L = s["edge"], R.cum[s["edge"]][-1]
        u, v = int(R.eu[e]), int(R.ev[e])
        dk = s["dist"] + min(km.get(u, 1e18) + s["along"], km.get(v, 1e18) + L - s["along"])
        sp = roads.SPEED_MS[R.cls[e]]
        ds = s["dist"] / sp + min(sec.get(u, 1e18) + s["along"] / sp, sec.get(v, 1e18) + (L - s["along"]) / sp)
        if dk >= 1e17:
            out.append(None)
            notes["no_road_link"].append(B.ids[i])
            continue
        out.append((round(ds / 60, 1), round(dk / 1000, 1)))
    return out, notes


# ── Build ────────────────────────────────────────────────────────────────────

def var(key, group, label, unit, d, typ, definition, sources, ref, year, muni, island, **extra):
    return {"key": key, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": ref, "definition": definition, "family": "conditions",
            "barrioFile": OUT_BARRIO.name, **extra, "years": {str(year): [*muni, island]}}


def compute(refresh=(), offline=False):
    B = Barrios()
    S = {k: source(k, k in refresh, offline) for k in SOURCE_KEYS}
    V = {k: s.get("vintage") for k, s in S.items()}
    mcol = lambda m: [m.get(f) for f in B.mids]
    vs, bvals, notes = [], {}, {}

    def add(v, barrio):
        vs.append(v)
        bvals[v["key"]] = (int(next(iter(v["years"]))), barrio)

    # sites
    tri_year = int(V["tri"])
    G1 = "Environment · Regulated sites (EPA)"
    sets = {
        "epa_tri": ([(r["lon"], r["lat"]) for r in S["tri"]["rows"]], tri_year, "Toxics Release Inventory facilities (EPA)",
                    f"Facilities that filed a Toxics Release Inventory (TRI) report with EPA for {tri_year}: plants of covered industries that make, process or otherwise use more than a threshold amount of a listed toxic chemical. A count of facilities, not of releases or of their amounts.",
                    ["epa_tri"], f"EPA TRI Basic Data File, Puerto Rico, reporting year {tri_year}"),
        "epa_rmp": ([(r["lon"], r["lat"]) for r in S["frs"]["rows"] if r["program"] == "rmp" and r["status"] == "ACTIVE"], int(S["frs"]["vintage"][:4]), "Risk Management Plan facilities (EPA)",
                    "Facilities with an active Risk Management Plan (RMP) registration in EPA's Facility Registry Service: places that hold more than a threshold quantity of a listed toxic or flammable substance (water and wastewater plants, chemical, energy and food plants, among others).",
                    ["epa_frs"], f"EPA Facility Registry Service, RMP interests marked active, read {S['frs']['vintage']}"),
        "epa_npl": ([(r["lon"], r["lat"]) for r in S["frs"]["rows"] if r["program"] == "npl" and r["status"] == "CURRENTLY ON THE FINAL NPL"], int(S["frs"]["vintage"][:4]), "Superfund National Priorities List sites (EPA)",
                    "Superfund sites currently on EPA's final National Priorities List, as EPA's Facility Registry Service places them: hazardous waste sites EPA ranks for long-term cleanup. Sites deleted from the list are not counted.",
                    ["epa_frs"], f"EPA Facility Registry Service, SEMS_NPL layer, currently on the final NPL, read {S['frs']['vintage']}"),
        "epa_landfills": ([(r["lon"], r["lat"]) for r in S["lmop"]["rows"]], int((V["lmop"] or "0")[:4]), "Municipal solid waste landfills, open or closed (EPA LMOP)",
                          "Municipal solid waste landfills in EPA's Landfill Methane Outreach Program database, open or closed. LMOP does not list every landfill, and lists no open dumps, transfer stations, industrial or hazardous waste landfills.",
                          ["epa_lmop"], f"EPA LMOP landfills with coordinates, data edited {V['lmop']}"),
        "epa_landfills_open": ([(r["lon"], r["lat"]) for r in S["lmop"]["rows"] if r["status"] == "Open"], int((V["lmop"] or "0")[:4]), "Municipal solid waste landfills still open (EPA LMOP)",
                               "Municipal solid waste landfills that EPA's Landfill Methane Outreach Program lists as open (accepting waste). The status is LMOP's as of its last update, which can lag a closure.",
                               ["epa_lmop"], f"EPA LMOP landfills with coordinates, data edited {V['lmop']}"),
    }
    notes["sites"] = {}
    for key, (pts, year, label, definition, srcs, ref) in sets.items():
        nb, nm, total, unplaced = counts_by_area(B, pts)
        notes["sites"][key] = {"sites": len(pts), "placed": len(pts) - unplaced, "outside_every_barrio": unplaced}
        add(var(key, G1, label, "", 0, "count", definition + " Counted in the barrio whose outline holds the site's point (a coastal site within 2 km of one counts there); a municipio is the sum of its barrios.",
                srcs, ref, year, mcol(nm), total, counted=False, classes="jenks", noPerHU=True), nb)

    # impaired waters and non-attainment
    G2 = "Environment · Water and air quality (EPA)"
    listed = [r["geometry"] for r in S["attains"]["rows"] if r["on303dlist"] == "Y"]
    pct, mpct, ipct, touch = shares_by_area(B, listed)
    notes["attains"] = {"units": len(S["attains"]["rows"]), "units_on_303d_list": len(listed), "barrios_touching": sum(touch), "cycle": V["attains"]}
    add(var("epa_303d_pct", G2, "Area draining to or in a 303(d)-listed impaired water (EPA ATTAINS, %)", "%", 1, "rate",
            "The share of the area inside an assessment unit that Puerto Rico's water quality report puts on the Clean Water Act 303(d) list (impaired, and a cleanup plan still needed). Puerto Rico maps its rivers and streams as the land that drains to each assessed reach, so a listed unit covers that watershed; lakes, estuaries and coastal waters are their own areas. A barrio touches a listed water when its share is above 0.",
            ["epa_attains"], f"EPA ATTAINS assessment units, Puerto Rico, {V['attains']} reporting cycle", int(V["attains"]), mcol(mpct), ipct, counted=False), pct)
    for pol, label, std in (("so2", "Area in a sulfur dioxide non-attainment area (EPA Green Book, %)", "the 1-hour sulfur dioxide standard of 2010"),
                            ("lead", "Area in a lead non-attainment area (EPA Green Book, %)", "the lead standard of 2008")):
        geoms = [r["geometry"] for r in S["greenbook"]["rows"] if r["pollutant"] == pol and r["current_status"] == "Nonattainment"]
        pct, mpct, ipct, touch = shares_by_area(B, geoms)
        notes[f"naa_{pol}"] = {"areas": [r["area_name"] for r in S["greenbook"]["rows"] if r["pollutant"] == pol and r["current_status"] == "Nonattainment"], "barrios_touching": sum(touch)}
        add(var(f"epa_naa_{pol}_pct", G2, label, "%", 1, "rate",
                f"The share of the area inside an area that EPA designates as not meeting {std} (non-attainment), as EPA's Green Book maps it. A barrio is in a non-attainment area when its share is above 0. It says where the designation applies, not what anyone breathes.",
                ["epa_greenbook"], f"EPA Green Book non-attainment areas, current status read {V['greenbook']}", int(V["greenbook"][:4]), mcol(mpct), ipct, counted=False), pct)

    # severe housing problems
    G3 = "Housing · Severe housing problems"
    bn, bd, mn, md, chas_notes = chas_by_area(B, S["chas"]["rows"])
    notes["chas"] = {**chas_notes, "window": V["chas"]}
    chas_year = int(V["chas"][-4:])
    est = "The barrio values are estimates: each tract's counts are spread over its barrios in proportion to the 2020 housing units each barrio has in the tract (docs/geography.md, section 4), so a barrio that lies in several tracts gets a blend of them. The municipio values are exact sums of their tracts."
    add(var("chas_severe_hh", G3, "Households with one or more severe housing problems (HUD CHAS)", "", 0, "count",
            f"Households with at least one of the four severe housing problems in HUD's CHAS data ({V['chas']}): a home without complete kitchen facilities, without complete plumbing, with more than 1.5 people per room, or a household paying more than half of its income for housing. " + est,
            ["hud_chas", "census_tiger"], f"HUD CHAS {V['chas']}, census tracts (Table 2), from HUD eGIS", chas_year, mcol({f: round(mn[f]) for f in B.mids}), sum(mn.values()), counted=False, tag="estimate"),
        [round(bn[b]) if bd[b] else (0 if b in bd else None) for b in B.ids])
    add(var("chas_severe_pct", G3, "Households with one or more severe housing problems (HUD CHAS, %)", "%", 1, "rate",
            f"The share of households with at least one of the four severe housing problems in HUD's CHAS data ({V['chas']}): no complete kitchen, no complete plumbing, more than 1.5 people per room, or housing costs above half of income. " + est,
            ["hud_chas", "census_tiger"], f"HUD CHAS {V['chas']}, census tracts (Table 2), from HUD eGIS", chas_year,
            mcol({f: round(100 * mn[f] / md[f], 1) if md[f] else None for f in B.mids}), round(100 * sum(mn.values()) / sum(md.values()), 1), counted=False, tag="estimate"),
        [round(100 * bn[b] / bd[b], 1) if bd[b] >= 0.5 else None for b in B.ids])

    # street intersections
    G4 = "Infrastructure · Street connectivity"
    nodes = intersections(S["tiger"])
    nb, nm, total, unplaced = counts_by_area(B, nodes)
    notes["tiger"] = {"year": V["tiger"], "street_edges": sum(1 for r in S["tiger"]["rows"] if r[1] in STREET_MTFCC), "intersections": len(nodes), "outside_every_barrio": unplaced}
    sqmi = lambda km2: km2 / SQKM_PER_SQMI
    bsq = [sqmi(B.unit[b]["km2"]) for b in B.ids]
    msq = {f: sqmi(B.unit[f]["km2"]) for f in B.mids}
    isq = sum(msq.values())
    tiger_year = int(V["tiger"])
    TIG = f"Street intersections: points where three or more street segments of the Census Bureau's TIGER/Line {tiger_year} files meet (secondary roads, local streets, alleys and private roads; limited-access highways, ramps, service drives, trails, walkways and parking lot roads are left out). A dead end or a bend is not an intersection."
    add(var("street_intersections", G4, "Street intersections (TIGER/Line)", "", 0, "count", TIG + " Counted in the barrio that holds each point.",
            ["census_tiger_lines"], f"US Census Bureau TIGER/Line {tiger_year} EDGES, 78 municipios", tiger_year, mcol(nm), total, counted=False, noPerHU=True), nb)
    add(var("street_intersection_density", G4, "Street intersections per square mile (TIGER/Line)", "", 1, "ratio", TIG + " Divided by the land area in square miles (2020 Census). Higher means a finer street grid, usually easier to walk.",
            ["census_tiger_lines", "census_tiger"], f"US Census Bureau TIGER/Line {tiger_year} EDGES; 2020 Census land area", tiger_year,
            mcol({f: round(nm[f] / msq[f], 1) if msq[f] else None for f in B.mids}), round(total / isq, 1)), [round(n / s, 1) if s else None for n, s in zip(nb, bsq)])

    # drive time to a general hospital
    G5 = "Health care · Distance to a general hospital"
    res, dnotes = drive(B, S["hospitals"]["rows"])
    hrows = S["hospitals"]["rows"]
    located = Counter(r["located"] for r in hrows)
    both = [r for r in hrows if "hhs_lon" in r]
    other = sum(1 for r in both if B.at(r["lon"], r["lat"], tol_km=0.5) != B.at(r["hhs_lon"], r["hhs_lat"], tol_km=0.5))
    notes["hospitals"] = {**dnotes, "listed_by_cms": S["hospitals"].get("listed"), "located": dict(located), "osm_to_hhs_km": S["hospitals"].get("osm_to_hhs_km"),
                          "placed_by_name_and_by_hhs": len(both), "hhs_point_in_another_barrio": other}
    pop = [B.unit[b]["pop"] for b in B.ids]

    def mean(vals, idx):
        w = [(vals[i], pop[i]) for i in idx if vals[i] is not None and pop[i]]
        tw = sum(p for _, p in w)
        return round(sum(v * p for v, p in w) / tw, 1) if tw else None
    mins = [r[0] if r else None for r in res]
    kms = [r[1] if r else None for r in res]
    by_m = defaultdict(list)
    for i in range(len(B.ids)):
        by_m[B.muni_of(i)].append(i)
    left = sum(pop[i] for i in range(len(B.ids)) if res[i] is None)
    notes["hospitals"]["residents_with_no_road_link"] = left
    hosp_year = int(S["hospitals"]["vintage"][:4])
    F = {f: i for i, f in enumerate(B.cw["fields"])}
    bname = {r[F["id"]]: r[F["name_en"]] for r in B.cw["units"]["barrio"]}
    mname = dict(zip(B.mids, B.names))
    others = [f"{bname[b]} ({mname[b[:5]]}, {B.unit[b]['pop']:,} residents)" for b in dnotes["no_road_link"] if b[:5] not in ("72049", "72147")]
    others_text = (" Other barrios with no value: " + "; ".join(others) + ".") if others else ""
    n_osm = located["osm"] + located["osm_near"]
    HOSP = ("From each barrio's population-weighted point (the 2020 census blocks of the barrio, weighted by their residents) to the nearest general acute care hospital with an emergency department in CMS's Hospital General Information list "
            f"({n_osm} of the {len(hrows)} placed at their OpenStreetMap building, found by name or near HHS's geocoded address; {located['hhs']} at HHS's geocoded address), "
            "along the observatory's OpenStreetMap road graph in either direction. A barrio that holds a hospital is 0. "
            f"Which barrios are 0 is uncertain near the {located['hhs']} hospitals placed at HHS's address: of the {len(both)} hospitals found by name that HHS also places, HHS's point falls in another barrio for {other}. "
            "A municipio's figure is the average of its barrios weighted by their 2020 residents. "
            "Vieques and Culebra have no road link to a hospital (a trip needs a ferry or a flight), so they have no value, and Puerto Rico's figure leaves out their residents." + others_text + " VA, psychiatric and children's hospitals are not counted.")
    NOROAD = "No road path to a general hospital (an island the roads do not reach, or no road within 2 km)"
    CAUTION = "Which barrios show 0 is uncertain where a hospital is placed at HHS's geocoded address, not at its OpenStreetMap building: HHS's point can fall in another barrio."
    add(var("hosp_drive_min", G5, "Drive time to the nearest general hospital (estimate, minutes)", "min", 1, "ratio",
            HOSP + " Drive time uses the observatory's planning speeds for each class of road (free flow: no traffic, no stops): a rough estimate, shorter than most real trips. The road distance is the firmer figure.",
            ["cms_provider_data", "hhs_hospital_capacity", "osm", "census_tiger"], "Computed by the observatory from CMS's hospital list (each hospital placed at its OpenStreetMap building or HHS's geocoded address), the 2020 census blocks and OpenStreetMap roads (conditions.py)",
            hosp_year, [mean(mins, by_m[f]) for f in B.mids], mean(mins, range(len(B.ids))), tag="estimate", noValue=NOROAD, caution=CAUTION), mins)
    add(var("hosp_road_km", G5, "Road distance to the nearest general hospital (km)", "km", 1, "ratio",
            HOSP + " An estimate made by the observatory, not a figure CMS publishes.",
            ["cms_provider_data", "hhs_hospital_capacity", "osm", "census_tiger"], "Computed by the observatory from CMS's hospital list (each hospital placed at its OpenStreetMap building or HHS's geocoded address), the 2020 census blocks and OpenStreetMap roads (conditions.py)",
            hosp_year, [mean(kms, by_m[f]) for f in B.mids], mean(kms, range(len(B.ids))), tag="estimate", noValue=NOROAD, caution=CAUTION), kms)

    notes["vintages"] = {"epa_tri": V["tri"], "epa_frs": V["frs"], "epa_attains": V["attains"], "epa_greenbook": V["greenbook"], "epa_lmop": V["lmop"], "hud_chas": V["chas"],
                         "census_tiger_lines": V["tiger"], "cms_provider_data": V["hospitals"]}
    years = sorted({int(y) for v in vs for y in v["years"]})
    series = {"as_of": max(V["frs"], V["greenbook"], V["hospitals"])[:7], "years": years, "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs,
              "sources": {k: SOURCES[k] for k in ("epa_tri", "epa_frs", "epa_attains", "epa_greenbook", "epa_lmop", "hud_chas", "census_tiger_lines", "cms_provider_data", "hhs_hospital_capacity", "osm", "census_tiger")},
              "notes": notes}
    barrio = {"level": "barrio", "geo": {"ids": B.ids}, "vars": [{"key": k, "years": {str(y): vals}} for k, (y, vals) in bvals.items()],
              "notes": {"areas": len(B.ids), "source": "conditions.py; the municipio values and the method are in conditions_series.json", "estimates": ["chas_severe_hh", "chas_severe_pct", "hosp_drive_min", "hosp_road_km"]}}
    return series, barrio


def build(refresh=(), check=False):
    series, barrio = compute(refresh, offline=check)
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python conditions.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {len(d['vars'])} variables, {path.stat().st_size / 1024:.1f} KB")
    return status


def parse_refresh(argv):
    if "--refresh" not in argv:
        return ()
    i = argv.index("--refresh")
    nxt = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
    keys = tuple(x for x in nxt.split(",") if x) or SOURCE_KEYS
    bad = [k for k in keys if k not in SOURCE_KEYS]
    if bad:
        raise SystemExit(f"conditions: unknown source {bad}; use {', '.join(SOURCE_KEYS)}")
    return keys


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build(parse_refresh(sys.argv), "--check" in sys.argv))
