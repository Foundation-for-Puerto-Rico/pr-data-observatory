"""Community assets for the PR Data Observatory: historic places and city halls as points on the 2D map, and counts for the 78 municipalities and Puerto Rico of
historic places and of substance use and mental health treatment facilities (counts only).

    python community_assets.py                          # build the two point files and site/data/community_series.json (downloads only what is missing from cache/community/)
    python community_assets.py --refresh                # download every source again
    python community_assets.py --refresh nps,samhsa     # download only these sources again (nps, townhall, samhsa); the others come from the cache
    python community_assets.py --check                  # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources, no key, each labelled with its own vintage:
  nps       National Park Service, National Register of Historic Places, the public (non-restricted) locations map service: layer 0 (points) and layer 1 (polygons, used
            only for the listings that have no point; each is placed at a point inside its outline). The service's licence field says "For general public
            distribution"; a US Government work, public domain (decided by FPR on 2026-10-18). Restricted and sensitive listings (such as archaeological sites) are not in the service.
  townhall  OpenStreetMap through the Overpass API (amenity=townhall; Open Database License 1.0, credit "(c) OpenStreetMap contributors"). Refreshed by hand, as the
            police stations are: a runner cannot reach Overpass, so a clean runner keeps the published file.
  samhsa    SAMHSA, the National Directories of the National Substance Use and Mental Health Services Survey (N-SUMHSS): the substance use and the mental health
            directory, Excel files of the newest edition (found on SAMHSA's National Directories page). The directories carry SAMHSA's Public Domain Notice.
            FindTreatment.gov's locator API states no licence, so it is not used.

What is kept. Only the columns in KEEP reach the cache.
  - Historic places: the listing's reference number, name, resource type, city, listing date and status, and one point. The street address is never requested.
  - City halls: the OpenStreetMap element id, name and townhall:type, and one point. Addresses, telephones, websites and e-mail are never kept.
  - Treatment facilities: no name, street address, telephone or point. Each row keeps only which directory it came from, the city, the state, its type-of-care codes
    (SA substance use, MH mental health, SUMH co-occurring) and a key made from a one-way hash of its name and address, so that a facility listed in both
    directories counts once. The Excel files are read in memory and never written to disk.

A published point carries only its name, type, municipio (name and GEOID) and, for historic places, the listing date; for city halls, the OpenStreetMap id.
Private residences on the National Register, and any listing whose name holds a street address or house number, are counted in their municipio but not drawn,
and their names are not published (decision 44, 2026-10-18): see residence() and the reviewed list nrhp_review.json.
Treatment facilities are counted by municipio and type only (substance use only, mental health only, both): no points and no names, because these are sensitive services.

Outputs:
  historic_places.geojson, town_halls.geojson   the points (loaded by the map on first use)
  community_series.json   one snapshot in the shape of facility_series.json: counts for each municipio and Puerto Rico (the engine offers them per 1,000 residents)
"""

import hashlib
import io
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import facilities as fa
import housing_series as hs
import xlsx_lite

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "community"
OUT = hs.OUT
OUT_SERIES = OUT / "community_series.json"
SOURCE_KEYS = ("nps", "townhall", "samhsa")
FILES = {"nps": "historic_places.geojson", "townhall": "town_halls.geojson"}   # the point files; samhsa gives counts only
log = hs.log

NPS = "https://mapservices.nps.gov/arcgis/rest/services/cultural_resources/nrhp_locations/MapServer"
NPS_WHERE = "State='PUERTO RICO'"
TOWNHALL_QUERY = '[out:json][timeout:90];nwr["amenity"="townhall"]({s},{w},{n},{e});out center tags;'
SAMHSA_DIRS = "https://www.samhsa.gov/data/data-we-collect/n-sumhss-national-substance-use-and-mental-health-services-survey/national-directories"
SAMHSA_BASE = "https://www.samhsa.gov"
SAMHSA_CARE = {"SA", "MH", "SUMH"}   # the type-of-care codes kept (Service Code Reference sheet: TC)

KEEP = {   # the only columns that reach the cache; a test checks that none of them can hold a telephone, an e-mail, a person's name or a street address
    "nps": ["NRIS_Refnum", "RESNAME", "ResType", "City", "CertDate", "STATUS", "State"],
    "townhall": ["amenity", "name", "townhall:type"],
    "samhsa": ["dir", "key", "city", "state", "care"],
}
FLOORS = {"nps": 300, "townhall": 50, "samhsa": 70}   # 2026-10-18: 360 points and 15 polygons, 65 city hall features, 111 directory rows (59 mental health, 52 substance use)
OFFSHORE_KM = 5.0   # a historic place outside every municipio's outline goes to the municipio its city names when it lies within this distance of it
REVIEW = ROOT / "nrhp_review.json"   # the reviewed list: listings drawn although their name matches a pattern below ('public'), and residences counted only ('residence')
RESIDENCE_NAME = re.compile(r"(?i)\b(casa|casona|house|residencia|residence|home|villa|chalet|quinta|manor|dwelling|apartments?|retreat|mansion|hacienda)\b")   # hacienda: a plantation's house can still be a home (no listing names a Finca or Estancia)
ADDRESS_NAME = re.compile(r"(?i)\d|#|\b(calle|street|avenida|avenue)\b")   # any number (a house number, 'No. 61'), a street word
RES_TYPE = {"building": "Historic building", "structure": "Historic structure", "district": "Historic district", "site": "Historic site", "object": "Historic object"}

SOURCES = {
    "nps_nrhp": {"name": "National Park Service — National Register of Historic Places, public locations (map service)", "url": "https://www.nps.gov/subjects/nationalregister/data-downloads.htm",
                 "license": "Public domain (US Government work; the service's licence field says 'For general public distribution')",
                 "note": "Listed historic places of Puerto Rico. The observatory publishes each listing's name, type, municipio, listing date and point, not its address; private residences, and listings named by a street address, are counted but not drawn. Restricted and sensitive listings are not in the service."},
    "osm": {"name": "OpenStreetMap", "url": "https://www.openstreetmap.org/copyright", "license": "Open Database License (ODbL) 1.0; © OpenStreetMap contributors",
            "note": "City halls as volunteers mapped them (amenity=townhall), read through the Overpass API. The observatory publishes each one's name, type, municipio and point, not its address, telephone or website."},
    "samhsa_nsumhss": {"name": "SAMHSA — National Directories of substance use and mental health treatment facilities (N-SUMHSS)", "url": SAMHSA_DIRS,
                       "license": "Public domain (SAMHSA's Public Domain Notice in the directories; they may not be reproduced or distributed for a fee)",
                       "note": "Treatment facilities counted by municipio and type of care. The observatory publishes counts only: no facility name, address, telephone or point."},
}


def keep(row, cols):
    return {c: row.get(c) for c in cols}


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat() if ms else None


def listed(s):
    """The listing date as NPS gives it ('1984-12-' or '8/31/2022') as 'YYYY-MM' or 'YYYY-MM-DD'; None when there is none."""
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-?(\d{1,2})?", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None


# ── Download (each source to its cache, kept columns only) ───────────────────

def arcgis(url, params):
    d = fa.get(url, params={**params, "f": "json"}).json()
    if "error" in d or d.get("exceededTransferLimit"):
        raise SystemExit(f"community_assets: {url} did not return every Puerto Rico feature: {str(d)[:300]}")
    return d["features"]


def fetch_nps():
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    pts = arcgis(f"{NPS}/0/query", {"where": NPS_WHERE, "outFields": ",".join(KEEP["nps"]) + ",EDIT_DATE", "returnGeometry": "true", "outSR": 4326})
    rows, edited = [], []
    for f in pts:
        a = f["attributes"]
        edited.append(a.get("EDIT_DATE") or 0)
        rows.append({**keep(a, KEEP["nps"]), "layer": "point", "lon": f["geometry"]["x"], "lat": f["geometry"]["y"]})
    have = {r["NRIS_Refnum"] for r in rows}
    polys = arcgis(f"{NPS}/1/query", {"where": NPS_WHERE, "outFields": ",".join(KEEP["nps"]) + ",EDIT_DATE", "returnGeometry": "true", "outSR": 4326})
    for f in polys:
        a = f["attributes"]
        edited.append(a.get("EDIT_DATE") or 0)
        if a["NRIS_Refnum"] in have:
            continue
        shp = unary_union([Polygon(r) for r in (f.get("geometry") or {}).get("rings", []) if len(r) >= 4])
        if shp.is_empty:
            continue
        p = shp.representative_point()   # a point inside the outline, not its centroid (which can fall outside)
        rows.append({**keep(a, KEEP["nps"]), "layer": "polygon", "lon": p.x, "lat": p.y})
    return {"vintage": iso(max(edited)) if edited else None, "rows": rows}


def overpass(query):
    s, w, n, e = fa.BBOX
    q = query.format(s=s, w=w, n=n, e=e)
    for attempt in range(4):   # the public servers are often busy (HTTP 504): go round them a few times before giving up
        for ep in fa.OVERPASS:
            try:
                r = requests.post(ep, data={"data": q}, headers=fa.UA, timeout=150)
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as ex:
                log(f"  {ep}: {type(ex).__name__}; trying the next server")
                time.sleep(5)
        time.sleep(30 * (attempt + 1))
    raise SystemExit("community_assets: no Overpass server answered; try again later")


def fetch_townhall():
    d = overpass(TOWNHALL_QUERY)
    rows = []
    for el in d.get("elements", []):
        c = el if el["type"] == "node" else el.get("center") or {}
        if c.get("lat") is None:
            continue
        rows.append({"osm": f"{el['type'][0]}{el['id']}", **keep(el.get("tags") or {}, KEEP["townhall"]), "lon": c["lon"], "lat": c["lat"]})
    return {"vintage": (d.get("osm3s") or {}).get("timestamp_osm_base", "")[:10] or None, "rows": rows}


def samhsa_files():
    """The newest edition that has both directories: {year, mh: xlsx url, su: xlsx url}."""
    page = fa.get(SAMHSA_DIRS).text
    reports = set(re.findall(r'href="(/data/report/(\d{4})-national-directory-(?:drug|mental)[^"]*)"', page))
    years = sorted({int(y) for _, y in reports}, reverse=True)
    for y in years:
        found = {}
        for path, yy in reports:
            if int(yy) != y:
                continue
            kind = "mh" if "mental" in path else "su"
            xl = re.findall(r'href="([^"]+\.xlsx)"', fa.get(SAMHSA_BASE + path).text)
            if xl:
                found[kind] = xl[0] if xl[0].startswith("http") else SAMHSA_BASE + xl[0]
        if {"mh", "su"} <= set(found):
            return {"year": y, **found}
    raise SystemExit("community_assets: SAMHSA's National Directories page lists no edition with both directories in Excel; read the page before going on")


def fac_key(r):
    """A one-way key for a directory row (its name and address), so a facility in both directories counts once; the name and address are not kept."""
    return hashlib.sha1("|".join(fa.norm(r.get(c)) for c in ("name1", "name2", "street1", "city")).encode()).hexdigest()[:16]


def samhsa_rows(kind, content):
    """The kept columns of the Puerto Rico rows of one directory (an .xlsx file read in memory)."""
    rows = xlsx_lite.sheet_rows(io.BytesIO(content), "Facilities List")
    head = rows[0]
    need = ["name1", "name2", "street1", "city", "state", "service_code_info"]
    if [c for c in need if c not in head]:
        raise SystemExit(f"community_assets: the {kind} directory has no column {[c for c in need if c not in head]}: read it before going on")
    out = []
    for cells in rows[1:]:
        r = dict(zip(head, cells))
        if r.get("state") != "PR":
            continue
        care = sorted(SAMHSA_CARE & set((r.get("service_code_info") or "").split()))
        out.append({"dir": kind, "key": fac_key(r), "city": r.get("city"), "state": r["state"], "care": care})
    return out


def fetch_samhsa():
    f = samhsa_files()
    rows, released = [], []
    for kind in ("su", "mh"):
        r = fa.get(f[kind])
        released.append(r.headers.get("Last-Modified") or "")
        rows += samhsa_rows(kind, r.content)   # the file stays in memory
    rel = max((datetime.strptime(x, "%a, %d %b %Y %H:%M:%S GMT").date().isoformat() for x in released if x), default=None)
    return {"vintage": str(f["year"]), "survey_year": f["year"] - 1, "released": rel, "files": {k: f[k] for k in ("su", "mh")}, "rows": rows}


FETCH = {"nps": fetch_nps, "townhall": fetch_townhall, "samhsa": fetch_samhsa}


def from_published(key):
    """The city halls as last published, when there is no cache and Overpass is not asked (a clean runner cannot reach Overpass)."""
    p = OUT / FILES[key]
    if not p.exists():
        return None
    fc = json.loads(p.read_text(encoding="utf-8"))
    return {"vintage": fc.get("vintage"), "from_published": True, "notes": fc.get("notes"),
            "rows": [{"osm": f["properties"].get("osm"), "amenity": "townhall", "name": f["properties"].get("name"), "townhall:type": None, "type_published": f["properties"]["type"],
                      "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]} for f in fc["features"]]}


def source(key, refresh=False, offline=False):
    path = CACHE / f"{key}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"community_assets --check: {path.name} is not in the cache (python community_assets.py makes it; --check never downloads)")
    log(f"  downloading {key}")
    d = FETCH[key]()
    if len(d["rows"]) < FLOORS[key]:
        raise SystemExit(f"community_assets: {key} returned {len(d['rows'])} rows (fewer than {FLOORS[key]}): the source changed; read it before going on")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  {key}: {len(d['rows'])} rows, vintage {d['vintage']}")
    return d


# ── Build ────────────────────────────────────────────────────────────────────

def townhall_type(r):
    if r.get("type_published"):
        return r["type_published"]
    return "City hall annex" if re.search(r"(?i)\banexo\b|\bannex\b", r.get("name") or "") else "City hall"


def review():
    d = json.loads(REVIEW.read_text(encoding="utf-8"))
    both = set(d["public"]) & set(d["residence"])
    if both:
        raise SystemExit(f"community_assets: {REVIEW.name} lists {sorted(both)} as both public and residence")
    return d


def residence(r, rv):
    """'residence' (counted, not drawn) for a listing reviewed as a private residence or whose name holds a street address or house number; 'unreviewed' (also
    counted, not drawn, until a person reviews it) for a name that matches a pattern and is in neither list; None (drawn) otherwise. NPS gives no ownership
    or use field, so the name patterns pick the listings to review and nrhp_review.json holds each decision with its reason."""
    ref, name = r["NRIS_Refnum"], r.get("RESNAME") or ""
    if ref in rv["residence"]:
        return "residence"
    if RESIDENCE_NAME.search(name) or ADDRESS_NAME.search(name):
        return None if ref in rv["public"] else "unreviewed"
    return None


def historic(rows, M, rv=None):
    """(features, counts {geoid: n}, island count, notes). One point per listing and municipio; a listing with points in several municipios (a road, an irrigation
    district) counts in each, and once in Puerto Rico's figure."""
    rv = rv if rv is not None else review()
    feats, n, notes, seen, listings, hidden, hidden_n = [], Counter(), Counter(), set(), set(), {}, Counter()
    for r in sorted(rows, key=lambda r: (r["NRIS_Refnum"], r["layer"] != "point", r["lon"], r["lat"])):
        if r.get("State") != "PUERTO RICO":
            raise SystemExit(f"community_assets: NPS returned a listing outside Puerto Rico ({r.get('State')})")
        if r.get("STATUS") not in (None, "", "Listed"):
            notes["not_listed"] += 1
            continue
        f, named = M.at(r["lon"], r["lat"]), M.named(r.get("City"))
        if f is None and named and M.near(named, r["lon"], r["lat"], OFFSHORE_KM):   # a lighthouse on a cay, a crash site at sea: the municipio its city names, when that is near
            f = named
            notes["offshore_placed_by_its_city"] += 1
        listings.add(r["NRIS_Refnum"])
        if f is None:
            notes["outside_every_municipio"] += 1
            continue
        if (r["NRIS_Refnum"], f) in seen:
            notes["more_points_in_the_same_municipio"] += 1
            continue
        seen.add((r["NRIS_Refnum"], f))
        if named and named != f:
            notes["point_in_another_municipio_than_its_city"] += 1
        notes["placed_from_polygon"] += r["layer"] == "polygon"
        n[f] += 1
        why = residence(r, rv)
        if why:   # counted in its municipio, never drawn: no name or point leaves the cache
            hidden[r["NRIS_Refnum"]] = why
            hidden_n[f] += 1
            continue
        feats.append(fa.feature(r["lon"], r["lat"], fa.clean_name(r.get("RESNAME")), RES_TYPE.get((r.get("ResType") or "").lower(), "Listed place"), f, M, listed=listed(r.get("CertDate"))))
    k = Counter(hidden.values())
    notes = {**notes, "listings": len(listings), "points_drawn": len(feats), "listings_drawn": len(listings) - len(hidden), "types": dict(Counter(x["properties"]["type"] for x in feats)),
             "counted_not_drawn": len(hidden), "counted_not_drawn_residences": k["residence"], "counted_not_drawn_unreviewed": k["unreviewed"],
             "counted_not_drawn_by_municipio": {g: hidden_n[g] for g in sorted(hidden_n)}}
    if k["unreviewed"]:
        log(f"  historic places: {k['unreviewed']} listing(s) whose name matches the residence or address patterns are not in {REVIEW.name}: counted, not drawn, until reviewed")
    return feats, n, len(listings), notes


def townhalls(rows, M, from_pub=None):
    feats, notes, seen = [], Counter(), []
    for r in sorted(rows, key=lambda r: (r.get("name") is None, r.get("osm") or "")):
        if r.get("amenity") != "townhall":
            raise SystemExit("community_assets: the Overpass answer holds a feature that is not amenity=townhall")
        f = M.at(r["lon"], r["lat"])
        if f is None:
            notes["outside_every_municipio"] += 1
            continue
        nm = fa.clean_name(r.get("name"))
        if any(abs(r["lat"] - a) * 111 < 0.03 and abs(r["lon"] - b) * 105 < 0.03 and (nm is None or nn is None or fa.norm(nm) == fa.norm(nn)) for a, b, nn in seen):
            notes["same_building_twice"] += 1
            continue
        seen.append((r["lat"], r["lon"], nm))
        feats.append(fa.feature(r["lon"], r["lat"], nm, townhall_type(r), f, M, osm=r.get("osm")))
    if from_pub:
        return feats, from_pub
    halls = {x["properties"]["geoid"] for x in feats if x["properties"]["type"] == "City hall"}
    gaps = [M.name_of[g] for g in M.ids if g not in halls]
    notes = {**notes, "features": len(feats), "types": dict(Counter(x["properties"]["type"] for x in feats)), "municipios_with_a_city_hall": len(halls),
             "municipios_without_a_city_hall_mapped": gaps, "unnamed": sum(1 for x in feats if not x["properties"]["name"])}
    return feats, notes


def treatment(rows, M):
    """Counts by municipio of facilities offering substance use treatment only, mental health treatment only, or both; a facility listed in both directories counts once."""
    fac = {}
    for r in rows:
        if r.get("state") != "PR":
            raise SystemExit("community_assets: a SAMHSA row outside Puerto Rico reached the build")
        x = fac.setdefault(r["key"], {"city": r["city"], "care": set(), "dirs": set()})
        x["care"] |= set(r["care"])
        x["dirs"].add(r["dir"])
    counts = {k: Counter() for k in ("bh_su", "bh_mh", "bh_both", "bh_all")}
    island, notes = Counter(), Counter()
    for x in fac.values():
        sa, mh = "SA" in x["care"], "MH" in x["care"]
        kind = "bh_both" if sa and mh else "bh_su" if sa else "bh_mh" if mh else None
        if kind is None:   # a row with no type of care given: listed in its directory, so counted by the directory's own field
            kind = "bh_su" if x["dirs"] == {"su"} else "bh_mh" if x["dirs"] == {"mh"} else "bh_both"
            notes["type_from_the_directory"] += 1
        island[kind] += 1
        island["bh_all"] += 1
        f = M.named(x["city"])
        if f is None:
            notes["not_placed_city_unknown"] += 1
            continue
        counts[kind][f] += 1
        counts["bh_all"][f] += 1
    notes = {**notes, "facilities": len(fac), "rows": len(rows), "in_both_directories": sum(1 for x in fac.values() if len(x["dirs"]) == 2),
             "by_type": {k: island[k] for k in ("bh_su", "bh_mh", "bh_both")}}
    return counts, island, notes


def var(key, group, label, definition, values, sources, ref, **extra):
    return {"key": key, "group": group, "label": label, "unit": "", "d": 0, "type": "count", "sources": sources, "ref": ref, "definition": definition, "family": "community",
            "counted": False, "classes": "jenks", "noPerHU": True, **extra, "years": values}


def compute(refresh=(), offline=False):
    M = fa.Munis()
    srcs = {}
    for k in SOURCE_KEYS:
        path = CACHE / f"{k}.json"
        if k == "townhall" and not path.exists() and k not in refresh and not offline and from_published(k):
            srcs[k] = from_published(k)   # a clean runner: keep the city halls as published (Overpass is refreshed by hand)
            log("  townhall: no cache, the published city halls are kept")
            continue
        srcs[k] = source(k, k in refresh, offline)
    V = {k: s.get("vintage") for k, s in srcs.items()}
    hfeats, hn, hisland, hnotes = historic(srcs["nps"]["rows"], M)
    tfeats, tnotes = townhalls(srcs["townhall"]["rows"], M, srcs["townhall"].get("notes") if srcs["townhall"].get("from_published") else None)
    bh, bh_island, bh_notes = treatment(srcs["samhsa"]["rows"], M)
    col = lambda c, isl: [c.get(f, 0) for f in M.ids] + [isl]
    nps_year, sy = V["nps"][:4], str(srcs["samhsa"]["survey_year"])
    S = srcs["samhsa"]
    s_ref = f"SAMHSA National Directories {S['vintage']} (N-SUMHSS {sy}, released {S['released']})"
    G = "Health · Treatment facilities (SAMHSA)"
    bh_def = (" Facilities that answered SAMHSA's National Substance Use and Mental Health Services Survey of {y} and are listed in its National Directories, in the municipio of their"
              " address. A facility listed in both directories counts once. The directories leave out facilities that did not answer or asked not to be listed, and most"
              " individual practitioners.").format(y=sy)
    vs = [
        var("nrhp_places", "Education · Historic places", "Places on the National Register of Historic Places (NPS)",
            "Buildings, structures, sites, objects and historic districts of Puerto Rico listed on the National Register of Historic Places, in the municipio that holds each listing's point. A listing with points in several municipios (a historic road or an irrigation system) counts in each, so the municipal values add up to more than Puerto Rico's, which counts each listing once. Every listing counts, private residences too, although the map does not draw those. Restricted and sensitive listings, such as archaeological sites, are not in the public data.",
            {nps_year: col(hn, hisland)}, ["nps_nrhp"], f"NPS National Register of Historic Places, public locations, edited up to {V['nps']}"),
        var("bh_all", G, "Substance use and mental health treatment facilities (SAMHSA)", "All the facilities below: substance use treatment, mental health treatment or both." + bh_def,
            {sy: col(bh["bh_all"], bh_island["bh_all"])}, ["samhsa_nsumhss"], s_ref),
        var("bh_su", G, "Treatment facilities: substance use only (SAMHSA)", "Facilities that offer substance use treatment and not mental health treatment." + bh_def,
            {sy: col(bh["bh_su"], bh_island["bh_su"])}, ["samhsa_nsumhss"], s_ref),
        var("bh_mh", G, "Treatment facilities: mental health only (SAMHSA)", "Facilities that offer mental health treatment and not substance use treatment." + bh_def,
            {sy: col(bh["bh_mh"], bh_island["bh_mh"])}, ["samhsa_nsumhss"], s_ref),
        var("bh_both", G, "Treatment facilities: both substance use and mental health (SAMHSA)", "Facilities that offer both substance use treatment and mental health treatment." + bh_def,
            {sy: col(bh["bh_both"], bh_island["bh_both"])}, ["samhsa_nsumhss"], s_ref),
    ]
    notes = {"historic_places": hnotes, "town_halls": tnotes, "treatment_facilities": bh_notes,
             "vintages": {"nps_nrhp": V["nps"], "osm": V["townhall"], "samhsa_nsumhss": {"directory": S["vintage"], "survey_year": S["survey_year"], "released": S["released"]}}}
    series = {"as_of": max(V["nps"], V["townhall"] or "")[:7], "years": sorted({int(nps_year), int(sy)}), "geo": {"ids": M.ids + ["72"], "names": M.names + ["Puerto Rico"]}, "vars": vs,
              "sources": {k: SOURCES[k] for k in ("nps_nrhp", "samhsa_nsumhss")}, "notes": notes}
    srt = lambda fs: sorted(fs, key=lambda x: (x["properties"]["geoid"], x["properties"]["name"] or "", x["geometry"]["coordinates"]))
    layers = {FILES["nps"]: {"type": "FeatureCollection", "source": "nps_nrhp", "vintage": V["nps"], "notes": hnotes, "features": srt(hfeats)},
              FILES["townhall"]: {"type": "FeatureCollection", "source": "osm", "vintage": V["townhall"], "notes": tnotes, "features": srt(tfeats)}}
    return layers, series


def build(refresh=(), check=False):
    layers, series = compute(refresh, offline=check)
    status = 0
    for name, d in [*layers.items(), (OUT_SERIES.name, series)]:
        path = OUT / name
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{name} is not what the cache gives: run python community_assets.py")
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
    keys = tuple(x for x in nxt.split(",") if x) or SOURCE_KEYS
    bad = [k for k in keys if k not in SOURCE_KEYS]
    if bad:
        raise SystemExit(f"community_assets: unknown source {bad}; use {', '.join(SOURCE_KEYS)}")
    return keys


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build(parse_refresh(sys.argv), "--check" in sys.argv))
