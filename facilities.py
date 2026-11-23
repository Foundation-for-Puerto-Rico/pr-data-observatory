"""Public facilities for the PR Data Observatory: public housing developments, Low-Income Housing Tax Credit projects, fire stations, police stations and public
libraries, as points on the 2D map and the 3D view and as counts for the 78 municipalities and Puerto Rico.

    python facilities.py                       # build the four point files and site/data/facility_series.json (downloads only what is missing from cache/facilities/)
    python facilities.py --refresh             # download every source again
    python facilities.py --refresh hud,usac    # download only these sources again (hud, lihtc, usgs, osm, usac); the others come from the cache
    python facilities.py --only lihtc          # after saving a new cache/facilities/lihtcpub.zip by hand (see "lihtc" below): rebuild only the LIHTC layer and counts
    python facilities.py --check               # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources, no key, each read through its live service (never a static copy) except HUD's LIHTC database, each layer labelled with its own vintage:
  hud   HUD eGIS, "Public Housing Developments" (ArcGIS REST feature service, updated quarterly; licence: U.S. Public Domain, as HUD's open data catalog states).
        One point per development: the building with the most units. HUD says to map only points geocoded to the rooftop or the ZIP+4 centroid (LVL2KX R or 4):
        the others sit at the centre of their block group or tract, so they are counted in their municipio but not drawn.
  lihtc HUD USER, National Low-Income Housing Tax Credit (LIHTC) Database (LIHTCPUB.ZIP, released once a year in the spring; US government work). HUD USER
        answers scripts with a bot check, so the archive is saved by hand from https://www.huduser.gov/lihtc/lihtcpub.zip to cache/facilities/lihtcpub.zip and
        never fetched here (HANDOFF decision 71; HUD's eGIS layer of the same name stops at projects placed in service in 2020). The build reads LIHTCPUB.xlsx
        inside it and keeps the Puerto Rico rows and only the columns in KEEP (the database also holds each project's street address and ZIP code; they are not
        kept). Every project counts in its municipio: the county of its 2020 census tract when HUD has one, else the municipio of the city HUD lists. A project
        is drawn only where HUD placed it at a point and in a 2020 census tract, the point lies within 1 km of that municipio, and the project does not serve
        people who are homeless or living with HIV (TRGT_HML, TRGT_SPC), or whose name says it is a care home (an égida, a "Hogar ...": the sensitive-place words
        of places_privacy.py): those are counted, never drawn or named (owner rule on sensitive places).
        On a clean runner with neither the archive nor the cache, the published layer and its three counts are kept as they are.
  usgs  USGS The National Map, National Structures Dataset (ArcGIS REST, layer "Fire Stations/EMS Stations"; US federal data, public domain).
  osm   OpenStreetMap through the Overpass API (amenity=police; Open Database License 1.0, credit "© OpenStreetMap contributors").
  usac  USAC open data, "E-Rate Supplemental Entity Information" (Socrata, updated daily; licence: Public Domain, as the dataset states): active entities of
        type Library that USAC marks as a public library. Each library is placed in the municipio of its address; its pin is drawn only where USAC's
        coordinates fall within 1 km of that municipio, because some coordinates point to another town.

Why these sources (2026-10-17): for fire stations USGS has 94 points and OpenStreetMap 77, of which 74 lie within 500 m of a USGS point; for police stations
USGS has 8 and OpenStreetMap 144. So each layer takes the more complete source. IMLS's Public Libraries Survey has no Puerto Rico rows, so libraries come from USAC.

What is kept. Only the columns in KEEP reach the cache, and a published point carries only its name, its type, its municipio (name and GEOID) and, for public
housing, its number of units; for an LIHTC project, its units, low-income units and year placed in service. Telephone numbers, e-mail addresses, contact and director names, street addresses and web addresses are never requested or
are dropped as each row is read (HUD's layer has the housing authority's telephone and e-mail and its director's; USAC's has contacts; OSM has addresses).

Outputs:
  public_housing.geojson, lihtc.geojson, fire_stations.geojson, police_stations.geojson, libraries.geojson   the points (loaded by the map on first use)
  facility_series.json   one snapshot in the shape of health_series.json: counts for each municipio and Puerto Rico (the engine offers them per 1,000 residents)
"""

import json
import re
import sys
import time
import unicodedata
import zipfile
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import housing_series as hs
import places_privacy as pp
import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "facilities"
OUT = hs.OUT
OUT_SERIES = OUT / "facility_series.json"
FILES = {"hud": "public_housing.geojson", "lihtc": "lihtc.geojson", "usgs": "fire_stations.geojson", "osm": "police_stations.geojson", "usac": "libraries.geojson"}
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
log = hs.log

HUD = "https://services.arcgis.com/VTyQ9soqVukalItT/arcgis/rest/services/Public_Housing_Developments/FeatureServer/0"
LIHTC_URL = "https://www.huduser.gov/lihtc/lihtcpub.zip"   # saved by hand (see the docstring); never requested by this file
LIHTC_ZIP = CACHE / "lihtcpub.zip"
USGS = "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/51"   # Fire Stations/EMS Stations (FCODE 74026)
USAC = "https://opendata.usac.org/resource/7i5i-83qf.json"
USAC_META = "https://opendata.usac.org/api/views/metadata/v1/7i5i-83qf"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
BBOX = (17.85, -67.97, 18.57, -65.20)   # south, west, north, east: Puerto Rico with Mona, Vieques and Culebra (transport.BBOX)
OSM_QUERY = '[out:json][timeout:90];nwr["amenity"="police"]({s},{w},{n},{e});out center tags;'

KEEP = {   # the only columns that reach the cache; a test checks that none of them can hold a telephone, an e-mail, a person's name or a street address
    "hud": ["DEVELOPMENT_CODE", "PROJECT_NAME", "TOTAL_UNITS", "SCATTERED_SITE_IND", "STATE2KX", "CNTY2KX", "LVL2KX"],
    "lihtc": ["hud_id", "project", "proj_cty", "proj_st", "latitude", "longitude", "fips2020", "cnty2020", "n_units", "li_units", "yr_pis", "type", "credit",
              "nonprog", "trgt_hml", "trgt_spc"],
    "usgs": ["permanent_identifier", "name", "fcode", "state", "loaddate"],
    "osm": ["amenity", "name", "operator", "police"],
    "usac": ["entity_number", "entity_name", "entity_type", "status", "physical_city", "physical_county", "physical_state", "public_library", "main_branch", "bookmobile", "kiosk", "latitude", "longitude"],
}
HUD_PRECISE = {"R", "4"}   # LVL2KX: interpolated rooftop or ZIP+4 centroid, the only codes HUD says to map
NEAR_KM = 1.0   # a library's pin is drawn when its coordinates fall within this distance of the municipio of its address
FLOORS = {"hud": 250, "lihtc": 200, "usgs": 70, "osm": 100, "usac": 900}   # 2026-10-17: 304 developments, 94 fire stations, 144 police features, 1,231 public libraries; 2026-10-31: 245 LIHTC projects
LIHTC_SENSITIVE = re.compile(r"(?i)aids|hiv|vih|sida")   # TRGT_SPC: housing for people living with HIV is counted, never drawn or named


def lihtc_care_name(project):
    """True when a project's name says it is a care or shelter home (an "égida", a "Hogar ...", "Golden Living"): the sensitive-place words of
    places_privacy.py, which withhold the same names among the tourism places. Counted, never drawn or named (2026-11-05: three égidas and two senior
    housing names of this layer were withheld places there)."""
    n = pp.norm(project or "")
    return bool(pp.SENSITIVE.search(n) or pp.CARE_HOME_FIRST.search(n))

# Postal place names in addresses that are not municipio names (USAC's physical_city), and the municipio each lies in
PLACE_ALIAS = {"rio piedras": "San Juan", "santurce": "San Juan", "hato rey": "San Juan", "old san juan": "San Juan", "viejo san juan": "San Juan", "cupey": "San Juan",
               "cupey bajo": "San Juan", "caparra": "Guaynabo", "sj": "San Juan", "quebradilla": "Quebradillas", "levittown": "Toa Baja", "sabana seca": "Toa Baja",
               "mercedita": "Ponce", "coto laurel": "Ponce", "bajadero": "Arecibo", "sabana hoyos": "Arecibo", "boqueron": "Cabo Rojo", "saint just": "Trujillo Alto",
               "st just": "Trujillo Alto", "palmer": "Río Grande", "fort buchanan": "Guaynabo", "ramey": "Aguadilla", "castaner": "Lares", "ensenada": "Guánica", "puerto real": "Fajardo",
               "rio blanco": "Naguabo", "garrochales": "Arecibo", "angeles": "Utuado", "punta santiago": "Humacao", "punta stgo": "Humacao"}

SOURCES = {
    "hud_public_housing": {"name": "HUD — Public Housing Developments (eGIS open data)", "url": "https://hudgis-hud.opendata.arcgis.com/datasets/HUD::public-housing-developments", "license": "U.S. Public Domain (HUD open data catalog)",
                           "note": "One point per public housing development. The observatory publishes the development's name, type, units, municipio and point, never the housing authority's telephone, e-mail or director, nor the tenants' figures."},
    "hud_lihtc": {"name": "HUD — National Low-Income Housing Tax Credit (LIHTC) Database", "url": "https://www.huduser.gov/portal/datasets/lihtc/property.html", "license": "US Government work (17 U.S.C. 105: no copyright in the United States); HUD USER states no other licence for the database",
                  "note": "Every LIHTC project placed in service in Puerto Rico that the Puerto Rico Housing Finance Authority reported to HUD. The observatory publishes each drawn project's name, municipio, units, low-income units, year placed in service and point, never its street address; projects for people who are homeless or living with HIV, and care homes for older adults, are counted, not drawn or named."},
    "usgs_structures": {"name": "USGS — The National Map, National Structures Dataset", "url": "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer", "license": "US federal government data (public domain)",
                        "note": "Fire and EMS stations of Puerto Rico. The observatory publishes each station's name, type, municipio and point, not its address."},
    "osm": {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "license": "Open Database License (ODbL) 1.0; © OpenStreetMap contributors",
            "note": "Police stations as volunteers mapped them (amenity=police), read through the Overpass API. The observatory publishes each one's name, type, municipio and point, not its address, telephone or website."},
    "usac_erate": {"name": "USAC — E-Rate Supplemental Entity Information (open data)", "url": "https://opendata.usac.org/E-rate/E-Rate-Supplemental-Entity-Information/7i5i-83qf", "license": "Public Domain (as the dataset states)",
                   "note": "Libraries registered for the E-Rate program that USAC marks as public libraries. The observatory publishes each library's name, type, municipio and point, never its contacts, telephone, e-mail or address."},
}


def get(url, **kw):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 180), **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"facilities: {url} failed: {e}")
            time.sleep(3 * (attempt + 1))


def norm(s):
    return " ".join(unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower().replace(",", " ").replace(".", " ").split())


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat() if ms else None


def keep(row, cols):
    return {c: row.get(c) for c in cols}


# ── Download (each source to its cache, kept columns only) ───────────────────

def fetch_hud():
    meta = get(HUD, params={"f": "json"}).json()
    item = get("https://www.arcgis.com/sharing/rest/content/items/5c96143f79c940a0a8cedae99a1ac562", params={"f": "json"}).json()
    m = re.search(r"Date of Coverage:\s*(\d{1,2})/(\d{4})", re.sub("<[^>]+>", " ", item.get("description") or ""))
    d = get(HUD + "/query", params={"where": "STATE2KX='72'", "outFields": ",".join(KEEP["hud"]), "returnGeometry": "true", "outSR": 4326, "f": "json", "resultRecordCount": 5000}).json()
    if "error" in d or d.get("exceededTransferLimit"):
        raise SystemExit(f"facilities: HUD's query did not return every Puerto Rico development: {str(d)[:300]}")
    rows = [{**keep(f["attributes"], KEEP["hud"]), "lon": (f.get("geometry") or {}).get("x"), "lat": (f.get("geometry") or {}).get("y")} for f in d["features"]]
    return {"vintage": f"{m.group(2)}-{int(m.group(1)):02d}" if m else None, "edited": iso((meta.get("editingInfo") or {}).get("dataLastEditDate")), "rows": rows}


def fetch_lihtc():
    """The Puerto Rico rows of HUD's LIHTC database, from the archive saved by hand (HUD USER refuses scripts; this function never goes to the network)."""
    if not LIHTC_ZIP.exists():
        raise SystemExit(f"facilities: {LIHTC_ZIP} is missing. Open {LIHTC_URL} in a browser, save it there, and run again")
    z = zipfile.ZipFile(LIHTC_ZIP)
    m = next(i for i in z.infolist() if i.filename.upper() == "LIHTCPUB.XLSX")
    covers = re.search(r"Dictionary (\d{4})", " ".join(z.namelist()))
    it = xlsx_read.rows(z.read(m))
    head = next(it)
    head = [head.get(i) for i in range(max(head) + 1)]
    st = head.index("proj_st")
    rows = [{c: r.get(head.index(c)) for c in KEEP["lihtc"]} for r in it if r.get(st) == "PR"]
    return {"vintage": "%04d-%02d-%02d" % m.date_time[:3], "placed_in_service_through": int(covers.group(1)) if covers else None, "rows": rows}


def fetch_usgs():
    meta = get(USGS.rsplit("/", 1)[0], params={"f": "json"}).json()
    d = get(USGS + "/query", params={"where": "state='PR'", "outFields": ",".join(KEEP["usgs"]), "returnGeometry": "true", "outSR": 4326, "f": "json"}).json()
    if "error" in d or d.get("exceededTransferLimit"):
        raise SystemExit(f"facilities: the USGS query did not return every station: {str(d)[:300]}")
    rows = [{**keep(f["attributes"], KEEP["usgs"]), "lon": f["geometry"]["x"], "lat": f["geometry"]["y"]} for f in d["features"]]
    refreshed = re.search(r"Data Refreshed ([A-Za-z]+,? \d{4})", meta.get("copyrightText") or "")
    return {"vintage": max(iso(r["loaddate"]) for r in rows) if rows else None, "refreshed": refreshed.group(1) if refreshed else None, "rows": rows}


def fetch_osm():
    s, w, n, e = BBOX
    q = OSM_QUERY.format(s=s, w=w, n=n, e=e)
    d = None
    for attempt in range(4):   # the public servers are often busy (HTTP 504): go round them a few times before giving up
        for ep in OVERPASS:
            try:
                r = requests.post(ep, data={"data": q}, headers=UA, timeout=150)
                r.raise_for_status()
                d = r.json()
                break
            except (requests.RequestException, ValueError) as ex:
                log(f"  {ep}: {type(ex).__name__}; trying the next server")
                time.sleep(5)
        if d is not None:
            break
        time.sleep(30 * (attempt + 1))
    if d is None:
        raise SystemExit("facilities: no Overpass server answered; try again later")
    rows = []
    for el in d.get("elements", []):
        c = el if el["type"] == "node" else el.get("center") or {}
        if c.get("lat") is None:
            continue
        rows.append({"osm": f"{el['type'][0]}{el['id']}", **keep(el.get("tags") or {}, KEEP["osm"]), "lon": c["lon"], "lat": c["lat"]})
    return {"vintage": (d.get("osm3s") or {}).get("timestamp_osm_base", "")[:10] or None, "rows": rows}


def fetch_usac():
    meta = get(USAC_META).json()
    rows = get(USAC, params={"$select": ",".join(KEEP["usac"]), "$where": "physical_state='PR' AND entity_type='Library'", "$order": "entity_number", "$limit": 50000}).json()
    if not isinstance(rows, list):
        raise SystemExit(f"facilities: USAC's query failed: {str(rows)[:300]}")
    return {"vintage": (meta.get("dataUpdatedAt") or "")[:10] or None, "rows": [keep(r, KEEP["usac"]) for r in rows]}


FETCH = {"hud": fetch_hud, "lihtc": fetch_lihtc, "usgs": fetch_usgs, "osm": fetch_osm, "usac": fetch_usac}


def from_published(key):
    """The police points as last published, when there is no cache and Overpass is not asked (a clean runner cannot reach Overpass): the published file holds the kept fields."""
    p = OUT / FILES[key]
    if not p.exists():
        return None
    fc = json.loads(p.read_text(encoding="utf-8"))
    return {"vintage": fc.get("vintage"), "from_published": True, "notes": fc.get("notes"),   # the notes of the build that read Overpass (how many were joined) stay as they were
            "rows": [{"osm": f["properties"].get("osm"), "amenity": "police", "name": f["properties"].get("name"), "operator": None, "police": None, "type_published": f["properties"]["type"],
                      "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]} for f in fc["features"]]}


def source(key, refresh=False, offline=False):
    path = CACHE / f"{key}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"facilities --check: {path.name} is not in the cache (python facilities.py makes it; --check never downloads)")
    log(f"  {'reading the saved archive for' if key == 'lihtc' else 'downloading'} {key}")
    d = FETCH[key]()
    if len(d["rows"]) < FLOORS[key]:
        raise SystemExit(f"facilities: {key} returned {len(d['rows'])} rows (fewer than {FLOORS[key]}): the source changed; read it before going on")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  {key}: {len(d['rows'])} rows, vintage {d['vintage']}")
    return d


# ── Places ───────────────────────────────────────────────────────────────────

class Munis:
    """The 78 municipios: names, GEOIDs and outlines (site/data/municipios.geojson), for point-in-polygon and name lookups."""

    def __init__(self):
        from shapely.geometry import shape
        from shapely.strtree import STRtree
        self.names, self.ids = hs.municipalities()
        self.by_name = {norm(n): f for n, f in zip(self.names, self.ids)}
        self.name_of = dict(zip(self.ids, self.names))
        fc = json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))
        self.geoms, self.keys = [], []
        for f in fc["features"]:
            self.geoms.append(shape(f["geometry"]))
            self.keys.append(str(f["properties"]["GEOID"])[:5])
        self.tree = STRtree(self.geoms)
        self.geom_of = dict(zip(self.keys, self.geoms))

    def at(self, lon, lat, tol_km=2.0):
        """The GEOID of the municipio that holds the point, or the nearest one within tol_km (a coastal point just outside the drawn line); None when farther."""
        from shapely.geometry import Point
        p = Point(lon, lat)
        hit = [j for j in self.tree.query(p) if self.geoms[j].contains(p)]
        if hit:
            return self.keys[hit[0]]
        j = min(range(len(self.geoms)), key=lambda k: self.geoms[k].distance(p))
        return self.keys[j] if self.geoms[j].distance(p) * 105 <= tol_km else None   # degrees to km at 18° N, roughly

    def near(self, geoid, lon, lat, km):
        from shapely.geometry import Point
        return self.geom_of[geoid].distance(Point(lon, lat)) * 105 <= km

    def named(self, *texts):
        """The GEOID of the first text that is a municipio's name or a known postal place in one."""
        for t in texts:
            k = norm(t)
            if not k:
                continue
            if k in self.by_name:
                return self.by_name[k]
            if k in PLACE_ALIAS:
                return self.by_name[norm(PLACE_ALIAS[k])]
        return None


PHONE = re.compile(r"[,;:\s]*(?<![\d-])(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]\d{4}(?!\d)")   # a telephone number written into a name ("..., 829-3343")
CONTACT = re.compile(r"[,;:\s]*(?:\S+@\S+|https?://\S+|www\.\S+)", re.I)


def clean_name(s):
    """The name with spaces tidied and any telephone number, e-mail or web address taken out (a few USAC library names carry the library's telephone)."""
    s = CONTACT.sub("", PHONE.sub("", " ".join(str(s or "").split()))).strip(" ,;:-")
    return s or None


def police_type(r):
    if r.get("type_published"):
        return r["type_published"]
    t = norm(f"{r.get('name') or ''} {r.get('operator') or ''}")
    if "municipal" in t:
        return "Municipal police"
    if re.search(r"policia de puerto rico|policia estatal|estatal|state police|negociado de la policia", t):
        return "State police (Puerto Rico Police Bureau)"
    return "Police (agency not stated)"


def library_type(r):
    if r.get("main_branch") == "Yes":
        return "Main library"
    if r.get("bookmobile") == "Yes":
        return "Bookmobile"
    if r.get("kiosk") == "Yes":
        return "Library kiosk"
    return "Library or branch"


# ── Build ────────────────────────────────────────────────────────────────────

def whole(v):
    """A count from the LIHTC sheet ('150', '150.0' or empty) as an integer."""
    return int(float(v)) if v not in (None, "", ".") else 0


def points(srcs, M):
    """{key: (features, counts {geoid: n}, notes)} for the layers, by the rules in the module's docstring (LIHTC only when its source is read: srcs["lihtc"] not None)."""
    out = {}
    # public housing: every development counts in the county HUD gives; only precise points are drawn
    feats, n, units, notes = [], Counter(), Counter(), Counter()
    for r in srcs["hud"]["rows"]:
        if r["STATE2KX"] != "72":
            raise SystemExit(f"facilities: HUD returned a development outside Puerto Rico ({r['STATE2KX']})")
        f = "72" + str(r["CNTY2KX"] or "").zfill(3)
        if f not in M.name_of:
            raise SystemExit(f"facilities: a HUD development has the county code {r['CNTY2KX']!r}")
        n[f] += 1
        units[f] += int(r["TOTAL_UNITS"] or 0)
        typ = "Scattered-site public housing" if r["SCATTERED_SITE_IND"] == "Y" else "Public housing development"
        if r["LVL2KX"] not in HUD_PRECISE or r["lon"] is None:
            notes["not_drawn_approximate_location"] += 1
            continue
        if not M.near(f, r["lon"], r["lat"], NEAR_KM):
            notes["not_drawn_point_outside_its_municipio"] += 1
            continue
        feats.append(feature(r["lon"], r["lat"], clean_name(r["PROJECT_NAME"]), typ, f, M, units=int(r["TOTAL_UNITS"] or 0)))
    notes = {**notes, "developments": sum(n.values()), "units": sum(units.values()), "drawn": len(feats)}
    out["hud"] = (feats, {"ph_devs": n, "ph_units": units}, dict(notes))
    # LIHTC projects: every one counts in its municipio (its 2020 tract's county, else the city HUD lists); drawn only where HUD placed it at a point in a 2020 tract
    # near that municipio, and never when it serves people who are homeless or living with HIV or its name says it is a care home (lihtc_care_name)
    if srcs.get("lihtc") is not None:
        feats, n, units, li, notes = [], Counter(), Counter(), Counter(), Counter()
        for r in srcs["lihtc"]["rows"]:
            if r["proj_st"] != "PR":
                raise SystemExit(f"facilities: the LIHTC rows hold a project outside Puerto Rico ({r['proj_st']})")
            c = str(r.get("cnty2020") or "").strip()
            f = "72" + c.zfill(3) if c.isdigit() else None
            if f not in M.name_of:
                f = M.named(r.get("proj_cty"))
                notes["placed_by_city"] += f is not None
            if f is None:
                notes["not_placed"] += 1
                continue
            n[f] += 1
            units[f] += whole(r["n_units"])
            li[f] += whole(r["li_units"])
            notes["no_longer_monitored"] += r.get("nonprog") == "1"
            if r.get("trgt_hml") == "1" or LIHTC_SENSITIVE.search(r.get("trgt_spc") or "") or LIHTC_SENSITIVE.search(r.get("project") or "") or lihtc_care_name(r.get("project")):
                notes["not_drawn_sensitive"] += 1
                continue
            if r.get("latitude") in (None, "") or "X" in str(r.get("fips2020") or "X"):
                notes["not_drawn_approximate_location"] += 1
                continue
            lon, lat = float(r["longitude"]), float(r["latitude"])
            if not M.near(f, lon, lat, NEAR_KM):
                notes["not_drawn_point_outside_its_municipio"] += 1
                continue
            yr = whole(r.get("yr_pis"))
            feats.append(feature(lon, lat, clean_name(r["project"]), "Low-Income Housing Tax Credit project", f, M,
                                 units=whole(r["n_units"]) or None, li_units=whole(r["li_units"]) or None, year=yr if 1987 <= yr <= 2100 else None))
        notes = {**notes, "projects": sum(n.values()), "units": sum(units.values()), "low_income_units": sum(li.values()), "drawn": len(feats)}
        out["lihtc"] = (feats, {"lihtc_projects": n, "lihtc_units": units, "lihtc_li_units": li}, dict(notes))
    # fire and EMS stations: the municipio that holds the point
    feats, n, notes = [], Counter(), Counter()
    for r in srcs["usgs"]["rows"]:
        if r["state"] != "PR" or r["fcode"] != 74026:
            raise SystemExit(f"facilities: USGS returned a feature that is not a Puerto Rico fire or EMS station ({r['state']}, {r['fcode']})")
        f = M.at(r["lon"], r["lat"])
        if f is None:
            notes["outside_every_municipio"] += 1
            continue
        n[f] += 1
        feats.append(feature(r["lon"], r["lat"], clean_name(r["name"]), "Fire or EMS station", f, M))
    notes = {**notes, "stations": sum(n.values()), "drawn": len(feats)}
    out["usgs"] = (feats, {"fire_stations": n}, dict(notes))
    # police: the municipio that holds the point; a node and a building outline of the same station (same name, within 30 m) count once
    feats, n, notes, seen = [], Counter(), Counter(), []
    for r in sorted(srcs["osm"]["rows"], key=lambda r: (r.get("name") is None, r.get("osm") or "")):
        if r.get("amenity") != "police":
            raise SystemExit("facilities: the Overpass answer holds a feature that is not amenity=police")
        f = M.at(r["lon"], r["lat"])
        if f is None:
            notes["outside_every_municipio"] += 1
            continue
        nm = clean_name(r.get("name"))
        if any(abs(r["lat"] - a) * 111 < 0.03 and abs(r["lon"] - b) * 105 < 0.03 and (nm is None or nn is None or norm(nm) == norm(nn)) for a, b, nn in seen):
            notes["same_station_twice"] += 1
            continue
        seen.append((r["lat"], r["lon"], nm))
        n[f] += 1
        feats.append(feature(r["lon"], r["lat"], nm, police_type(r), f, M, osm=r.get("osm")))
    notes = {**notes, "stations": sum(n.values()), "drawn": len(feats), "types": dict(Counter(x["properties"]["type"] for x in feats))}
    out["osm"] = (feats, {"police_stations": n}, srcs["osm"]["notes"] if srcs["osm"].get("from_published") else dict(notes))
    # libraries: active E-Rate libraries marked public; placed by the address's municipio, drawn when the point agrees within 1 km
    feats, n, notes, ids = [], Counter(), Counter(), set()
    for r in srcs["usac"]["rows"]:
        if r.get("physical_state") != "PR" or r.get("entity_type") != "Library":
            raise SystemExit("facilities: USAC returned a row that is not a Puerto Rico library")
        if r.get("status") != "Active" or r.get("public_library") != "Yes":
            notes["not_active_or_not_public"] += 1
            continue
        if r["entity_number"] in ids:
            continue
        ids.add(r["entity_number"])
        lon, lat = (float(r["longitude"]), float(r["latitude"])) if r.get("latitude") and r.get("longitude") else (None, None)
        f = M.named(r.get("physical_city"), r.get("physical_county"))
        if f is None and lon is not None:
            f = M.at(lon, lat, tol_km=0.5)
            notes["placed_by_point"] += f is not None
        if f is None:
            notes["not_placed"] += 1
            continue
        n[f] += 1
        if lon is None:
            notes["not_drawn_no_point"] += 1
        elif not M.near(f, lon, lat, NEAR_KM):
            notes["not_drawn_point_in_another_municipio"] += 1
        else:
            feats.append(feature(lon, lat, clean_name(r["entity_name"]), library_type(r), f, M))
    notes = {**notes, "libraries": sum(n.values()), "drawn": len(feats)}
    out["usac"] = (feats, {"libraries": n}, dict(notes))
    return out


def feature(lon, lat, name, typ, geoid, M, **extra):
    props = {"name": name, "type": typ, "municipio": M.name_of[geoid], "geoid": geoid, **{k: v for k, v in extra.items() if v is not None}}
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]}}


def var(key, group, label, definition, values, sources, ref, **extra):
    return {"key": key, "group": group, "label": label, "unit": "", "d": 0, "type": "count", "sources": sources, "ref": ref, "definition": definition, "family": "facilities",
            "counted": False, "classes": "jenks", **extra, "years": values}


def compute(refresh=(), offline=False):
    M = Munis()
    srcs = {}
    for k in FILES:
        path = CACHE / f"{k}.json"
        if k == "lihtc" and not path.exists() and not LIHTC_ZIP.exists() and not offline and (OUT / FILES[k]).exists() and OUT_SERIES.exists():
            srcs[k] = None   # a clean runner: keep the LIHTC layer and its counts as published (the archive is saved by hand)
            log("  lihtc: no archive and no cache, the published layer and counts are kept")
            continue
        if k == "osm" and not path.exists() and k not in refresh and not offline and from_published(k):
            srcs[k] = from_published(k)   # a clean runner: keep the police layer as published (Overpass is refreshed by hand)
            log("  osm: no cache, the published police points are kept")
            continue
        srcs[k] = source(k, k in refresh, offline)
    built = points(srcs, M)
    V = {k: s.get("vintage") for k, s in srcs.items() if s is not None}
    kept = {}   # the LIHTC values as published, when its source was not read
    if srcs["lihtc"] is None:
        pub = json.loads((OUT / FILES["lihtc"]).read_text(encoding="utf-8"))
        old = {v["key"]: v for v in json.loads(OUT_SERIES.read_text(encoding="utf-8"))["vars"]}
        built["lihtc"] = (pub["features"], None, pub["notes"])
        V["lihtc"] = pub["vintage"]
        srcs["lihtc"] = {"vintage": pub["vintage"], "placed_in_service_through": pub.get("placed_in_service_through")}
        kept = {k: next(iter(old[k]["years"].values())) for k in ("lihtc_projects", "lihtc_units", "lihtc_li_units")}
    year = max(int(v[:4]) for v in V.values() if v)
    col = lambda c: [c.get(f, 0) for f in M.ids] + [sum(c.get(f, 0) for f in M.ids)]
    hud_ref = f"HUD Public Housing Developments, coverage {V['hud']}"
    thru = srcs["lihtc"].get("placed_in_service_through")
    vs = [
        var("ph_devs", "Housing · Public housing", "Public housing developments (HUD)",
            "Public housing developments in HUD's list, in the municipio HUD gives for each (the county of the development's main building). A development can be one building or several scattered across a community.",
            {str(year): col(built["hud"][1]["ph_devs"])}, ["hud_public_housing"], hud_ref, noPerHU=True),
        var("ph_units", "Housing · Public housing", "Public housing units (HUD)",
            "Dwelling units in those developments, as HUD reports them (TOTAL_UNITS). Occupied and vacant units are both counted.",
            {str(year): col(built["hud"][1]["ph_units"])}, ["hud_public_housing"], hud_ref),
        *lihtc_vars(year, kept or {k: col(c) for k, c in built["lihtc"][1].items()}, thru, V["lihtc"]),
        var("fire_stations", "Infrastructure · Emergency services", "Fire and EMS stations (USGS)",
            "Fire stations and emergency medical service stations in the USGS National Structures Dataset, in the municipio that holds each point.",
            {str(year): col(built["usgs"][1]["fire_stations"])}, ["usgs_structures"], f"USGS National Structures Dataset, loaded up to {V['usgs']}", noPerHU=True),
        var("police_stations", "Infrastructure · Emergency services", "Police stations (OpenStreetMap)",
            "Police stations and other police facilities mapped in OpenStreetMap (amenity=police), in the municipio that holds each point. A station mapped twice (a point and its building, same name, within 30 m) counts once. Volunteers map them, so a missing station is possible.",
            {str(year): col(built["osm"][1]["police_stations"])}, ["osm"], f"OpenStreetMap, data of {V['osm']}", noPerHU=True),
        var("libraries", "Education · Libraries", "Public libraries (USAC E-Rate)",
            "Active libraries registered for the federal E-Rate program that USAC marks as public libraries, in the municipio of their address. In Puerto Rico the list includes community technology centres and other community libraries registered as public libraries, not only municipal libraries.",
            {str(year): col(built["usac"][1]["libraries"])}, ["usac_erate"], f"USAC E-Rate Supplemental Entity Information, updated {V['usac']}", noPerHU=True),
    ]
    notes = {"public_housing": built["hud"][2], "lihtc": built["lihtc"][2], "fire_stations": built["usgs"][2], "police_stations": built["osm"][2], "libraries": built["usac"][2],
             "vintages": {"hud_public_housing": V["hud"], "hud_lihtc": V["lihtc"], "usgs_structures": V["usgs"], "osm": V["osm"], "usac_erate": V["usac"]}}
    series = {"as_of": max(v for v in V.values() if v)[:7], "years": [year], "geo": {"ids": M.ids + ["72"], "names": M.names + ["Puerto Rico"]}, "vars": vs,
              "sources": {k: SOURCES[k] for k in ("hud_public_housing", "hud_lihtc", "usgs_structures", "osm", "usac_erate")}, "notes": notes}
    layers = {FILES[k]: layer(k, feats, nt, V[k], thru) for k, (feats, _, nt) in built.items()}
    return layers, series


def lihtc_vars(year, vals, thru, vintage):
    """The three LIHTC counts ({key: [78 municipios + Puerto Rico]}) as datasets of facility_series.json."""
    ref = f"HUD National LIHTC Database, projects placed in service 1987 to {thru} (release of {vintage})"
    g = "Housing · Tax credit housing"
    return [
        var("lihtc_projects", g, "LIHTC projects (HUD)",
            "Projects placed in service with Low-Income Housing Tax Credits, as the Puerto Rico Housing Finance Authority reported them to HUD, in the municipio of each project (the county of its 2020 census tract, or the city HUD lists). A project counts from the year it was placed in service, including the few no longer monitored for the credit's rules.",
            {str(year): vals["lihtc_projects"]}, ["hud_lihtc"], ref, noPerHU=True),
        var("lihtc_units", g, "LIHTC housing units (HUD)",
            "Housing units in those projects, as HUD reports them (N_UNITS), low-income and market-rate together.",
            {str(year): vals["lihtc_units"]}, ["hud_lihtc"], ref),
        var("lihtc_li_units", g, "LIHTC low-income units (HUD)",
            "The units in those projects that are rent- and income-restricted under the credit (LI_UNITS), as the allocating agency reported them.",
            {str(year): vals["lihtc_li_units"]}, ["hud_lihtc"], ref),
    ]


def layer(k, feats, notes, vintage, thru=None):
    sid = {"hud": "hud_public_housing", "lihtc": "hud_lihtc", "usgs": "usgs_structures", "osm": "osm", "usac": "usac_erate"}[k]
    extra = {"placed_in_service_through": thru} if k == "lihtc" else {}
    return {"type": "FeatureCollection", "source": sid, "vintage": vintage, **extra, "notes": notes,
            "features": sorted(feats, key=lambda x: (x["properties"]["geoid"], x["properties"]["name"] or "", x["geometry"]["coordinates"]))}


def build_lihtc():
    """Rebuild only the LIHTC layer and its three counts in the published files, from the archive saved by hand (cache/facilities/lihtcpub.zip): run it after
    saving a new release. The other layers and counts keep their own data and vintages."""
    M = Munis()
    src = source("lihtc", refresh=True)
    feats, counts, notes = points({"hud": {"rows": []}, "lihtc": src, "usgs": {"rows": []}, "osm": {"rows": []}, "usac": {"rows": []}}, M)["lihtc"]
    path = OUT / FILES["lihtc"]
    path.write_text(json.dumps({**layer("lihtc", feats, notes, src["vintage"], src["placed_in_service_through"]), "built": date.today().isoformat()}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"wrote {path.name}: {len(feats)} points, {path.stat().st_size / 1024:.1f} KB")
    d = json.loads(OUT_SERIES.read_text(encoding="utf-8"))
    year = d["years"][0]
    col = lambda c: [c.get(f, 0) for f in M.ids] + [sum(c.get(f, 0) for f in M.ids)]
    new = lihtc_vars(year, {k: col(c) for k, c in counts.items()}, src["placed_in_service_through"], src["vintage"])
    vs = [v for v in d["vars"] if not v["key"].startswith("lihtc_")]
    at = next(i for i, v in enumerate(vs) if v["key"] == "ph_units") + 1
    d["vars"] = vs[:at] + new + vs[at:]
    d["notes"]["lihtc"] = notes
    d["notes"]["vintages"]["hud_lihtc"] = src["vintage"]
    d["sources"]["hud_lihtc"] = SOURCES["hud_lihtc"]
    OUT_SERIES.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"updated {OUT_SERIES.name}: the three LIHTC counts ({notes['projects']} projects, {notes['drawn']} drawn)")
    return 0


def build(refresh=(), check=False):
    layers, series = compute(refresh, offline=check)
    status = 0
    for name, d in [*layers.items(), (OUT_SERIES.name, series)]:
        path = OUT / name
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{name} is not what the cache gives: run python facilities.py")
                status = 1
            else:
                print(f"{name} matches the cache")
            continue
        out = {"built": date.today().isoformat(), **d} if name == OUT_SERIES.name else {**d, "built": date.today().isoformat()}
        path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {name}: {len(d['features']) if 'features' in d else len(d['vars'])} {'points' if 'features' in d else 'variables'}, {path.stat().st_size / 1024:.1f} KB")
    return status


def parse_refresh(argv):
    if "--refresh" not in argv:
        return ()
    i = argv.index("--refresh")
    nxt = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
    keys = tuple(x for x in nxt.split(",") if x) or tuple(FILES)
    bad = [k for k in keys if k not in FILES]
    if bad:
        raise SystemExit(f"facilities: unknown source {bad}; use {', '.join(FILES)}")
    return keys


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--only" in sys.argv:
        if sys.argv[sys.argv.index("--only") + 1:][:1] != ["lihtc"]:
            raise SystemExit("facilities.py: --only takes lihtc (the layer built from the archive saved by hand)")
        raise SystemExit(build_lihtc())
    raise SystemExit(build(parse_refresh(sys.argv), "--check" in sys.argv))
