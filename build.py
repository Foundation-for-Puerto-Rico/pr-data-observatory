"""PR Data Observatory - Phase 1 data build.

    python build.py [--refresh] [--label "Snapshot 2026-10"]

Produces a static dataset under site/data/ from open sources only:

  places.json          tourism places from Overture Maps (CDLA-Permissive 2.0 / Apache 2.0),
                       classified into the VIEWPR taxonomy, de-duplicated, without the listings that are not
                       tourism (homes, housing, care services: places_privacy.not_tourism), attributed to a
                       municipality, flagged for flood zone and protected area
  municipios.geojson   78 municipality boundaries + 2020 Census population (US Census TIGERweb)
  flood.geojson        FEMA National Flood Hazard Layer zones (simplified for display)
  protected.geojson    USGS PAD-US protected areas (simplified for display)
  municipalities.json  per-municipality statistics (supply, risk exposure, density)
  place_access.json    per tourism place: distance to the nearest stop with a current timetable, its weekday departures, weekend service (access.py)
  meta.json            snapshot label/date, source credits and licences, counts
  catalog.json         what the map reads first: the domains with a headline figure each, an index of the dictionary, the weight of every file (catalog.py)

Everything downloaded is cached in cache/ so re-builds are fast; --refresh re-downloads.
No API keys (except the free api.data.gov key that economy_series.py --fac reads from FAC_API_KEY, HANDOFF decision 70), no stored proprietary data.
"""

import argparse
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import cos, radians, sqrt
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from municipalities import MUNICIPALITIES
import muni_locate
from network import LIVE_CHECKED, LIVE_SOURCES, SOURCES as NETWORK_SOURCES, build_network, coverage, load_blocks, load_roads, previous_routes, transfers
from transport import SOURCES as TRANSPORT_SOURCES, build_transport
from timeseries import SOURCES as TIME_SOURCES, load_hurricanes, load_population_2010
from housing import SOURCES as HOUSING_SOURCES, build_housing
import housing_series
import economy_series
import health_series
import education_series
import women_labor
import public_money_need
import inflation
import ogp_budget
import pica
import federal_awards
import cdbg_dr
import federal_outlays
import fema_pa_stage
import municipio_view
import cdbg_regular
import medicare_series
import care_series
import infrastructure_series
import power_plants
import power_lines
import energy_series
import energy_municipios
import environment_series
import gateway_series
import facilities
import facility_exposure
import reservoirs
import opportunity_zones
import traffic
import crashes
import transport_inventories
import transit_links
import river_gauges
import groundwater
import rain_gauges
import nonprofits
import conditions
import landslide
import heat
import vegetation
import buildings
import climb
import slope
import watersheds
import upstream
import ecostress
import community_assets
import commuting
import credit
import drought
import storm_recovery
import essentials
import cutoff
import jobs_reach
import degrees
import school_conditions
import proficiency
import providers
import small_area
import registry
import budget
import dictionary
import access
import audit_findings
import catalog
import contract
import places_privacy
import exposure
import geo
import i18n
import knowledge
import learn
import supply
import svi
import taken_back
import trip_paths
import unused_funds
from landuse import SOURCES as LANDUSE_SOURCES, build_barrios, build_landuse

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "site" / "data"
BBOX = (-67.97, 17.85, -65.20, 18.57)   # west, south, east, north - all of PR incl. Mona, Culebra, Vieques
MIN_CONF = 0.50   # the map's default confidence filter; every published statistic uses the same basis (no worship)
# Telephones, e-mails, social accounts, street addresses and websites are read for de-duplication only and never published (places_privacy.CONTACT_FIELDS):
# "never publish business contact details or any personal data" (owner rule).

SOURCES = {
    "overture": {
        "name": "Overture Maps Foundation - Places",
        "url": "https://overturemaps.org/",
        "license": "CDLA-Permissive 2.0 (Meta, Microsoft and others) / Apache 2.0 (Foursquare)",
        "credit": "Place data © Overture Maps Foundation contributors (Meta, Microsoft, Foursquare and others)",
    },
    "fema": {
        "name": "FEMA National Flood Hazard Layer (NFHL)",
        "url": "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28",
        "license": "US Government work; FEMA's metadata lists no access constraints",
        "credit": "Flood zones: FEMA National Flood Hazard Layer",
    },
    "padus": {
        "name": "USGS Protected Areas Database of the United States (PAD-US 4.1)",
        "url": "https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Protection_Mechanism_Category_PADUS/FeatureServer/0",
        "license": "US Government work - public domain",
        "credit": "Protected areas: USGS PAD-US",
    },
    "census": {
        "name": "US Census Bureau - TIGERweb, 2020 Census",
        "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/82",
        "license": "US Government work (no US copyright)",
        "credit": "Municipal boundaries and population: US Census Bureau (2020 Census, TIGERweb)",
    },
    "census_shore": {
        "name": "US Census Bureau — TIGERweb generalized county boundaries (500k, shoreline-clipped)",
        "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2023/State_County/MapServer/11",
        "license": "US Government work (no US copyright)",
        "credit": "Municipal boundaries: US Census Bureau (TIGERweb generalized)",
    },
    "noaa_slr": {
        "name": "NOAA Office for Coastal Management - Sea Level Rise Viewer",
        "url": "https://coast.noaa.gov/arcgis/rest/services/dc_slr",
        "license": "No license stated; NOAA's disclaimer applies",
        "credit": "Sea level rise scenarios: NOAA Office for Coastal Management",
    },
    "osm": {
        "name": "OpenStreetMap",
        "url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "credit": "Map data © OpenStreetMap contributors",
    },
}

# ── Taxonomy: Overture categories -> VIEWPR category / type ───────────────────

ROOTS = {
    "lodging": "ACCOMMODATIONS", "accommodation": "ACCOMMODATIONS",
    "food_and_drink": "GASTRONOMY", "eat_and_drink": "GASTRONOMY",
    "cultural_and_historic": "ATTRACTIONS", "attractions_and_activities": "ATTRACTIONS",
    "arts_and_entertainment": "ATTRACTIONS", "geographic_entities": "ATTRACTIONS",
}
RULES = [
    ("ATTRACTIONS", "Places of Worship", r"place_of_worship|church|cathedral|chapel|synagogue|mosque|temple|religious"),
    ("ATTRACTIONS", "Beaches", r"^beach"),
    ("ATTRACTIONS", "Parks", r"^park$|_park$|^park_|playground|national_park|state_park"),
    ("ATTRACTIONS", "Nature Reserves", r"nature|forest|wildlife|reserve|botanical"),
    ("ATTRACTIONS", "Museums", r"museum"),
    ("ATTRACTIONS", "Historic Sites", r"historic|monument|fort|castle|ruin"),
    ("ATTRACTIONS", "Cultural Attractions", r"art_gallery|theater|theatre|performing_arts|cultural_center|cinema|movie_theater"),
    ("ATTRACTIONS", "Scenic Areas", r"scenic|lookout|viewpoint|waterfall|cave|lake|river|island|mountain|hiking_trail|trail"),
    ("ATTRACTIONS", "Tourist Attractions", r"tourist|attraction|amusement|zoo|aquarium|water_park|theme_park|observatory|plaza|landmark"),
    ("GASTRONOMY", "Bakeries", r"bakery|pastry|patisserie|donut"),
    ("GASTRONOMY", "Cafes", r"cafe|coffee|tea_room|ice_cream|dessert|juice_bar|bubble_tea"),
    ("GASTRONOMY", "Nightlife", r"night_club|nightclub|karaoke|lounge|dance_club|live_music"),
    ("GASTRONOMY", "Bars", r"\bbar\b|_bar$|^bar_|pub$|brewery|brewpub|beer_garden|cocktail|sports_bar|wine_bar"),
    ("GASTRONOMY", "Food Markets", r"farmers_market|food_market|public_market|market$|grocery"),
    ("GASTRONOMY", "Food Experiences", r"winery|distillery|coffee_roaster|food_tour|cooking"),
    ("GASTRONOMY", "Restaurants", r"restaurant|food_truck|food_stand|diner|pizzeria|steakhouse|seafood|fast_food|cafeteria|eatery|taqueria|bistro|kiosk|chinchorro"),
    ("ACCOMMODATIONS", "Resorts", r"resort"),
    ("ACCOMMODATIONS", "Inns", r"\binn\b|bed_and_breakfast"),
    ("ACCOMMODATIONS", "Guest Houses", r"guest_house|guesthouse|hostel|boarding"),
    ("ACCOMMODATIONS", "Vacation Properties", r"vacation|villa|cottage|cabin|holiday|rental|apartment_hotel|condo"),
    ("ACCOMMODATIONS", "Hotels", r"hotel|motel"),
    ("ACCOMMODATIONS", "Lodging", r"lodging|accommodation|campground|camping|rv_park"),
    ("VISITOR_SERVICES", "Tour Operators", r"tour|travel_agen|excursion|sightseeing"),
    ("VISITOR_SERVICES", "Visitor Centers", r"visitor|tourist_information|information_center"),
    ("VISITOR_SERVICES", "Marinas", r"marina|boat|yacht|harbor|harbour|dock|ferry"),
    ("VISITOR_SERVICES", "Adventure Operators", r"surf|dive|scuba|snorkel|kayak|zipline|zip_line|rafting|horse|adventure|paddle|sailing|fishing_charter|climbing"),
    ("VISITOR_SERVICES", "Transportation", r"car_rental|airport|taxi|bus_station|transit|shuttle|limo|bike_rental|scooter_rental"),
    ("VISITOR_SERVICES", "Cultural Experience Providers", r"cooking_class|art_class|dance_studio|workshop|artisan"),
]
COMPILED = [(c, s, re.compile(p)) for c, s, p in RULES]
DEFAULT_TYPE = {"ACCOMMODATIONS": "Lodging", "GASTRONOMY": "Restaurants", "ATTRACTIONS": "Tourist Attractions", "VISITOR_SERVICES": "Tour Operators"}
STANDALONE_TYPES = {"Beaches", "Nature Reserves", "Scenic Areas", "Historic Sites", "Museums", "Parks", "Places of Worship"}


def classify(primary, hierarchy):
    if not primary:
        return None
    hit = None
    for text in (primary, " ".join(hierarchy or [])):
        for cat, sub, rx in COMPILED:
            if rx.search(text):
                hit = (cat, sub)
                break
        if hit:
            break
    root = next((ROOTS[h] for h in (hierarchy or []) if h in ROOTS), None)
    if root:
        return hit if hit and hit[0] == root else (root, DEFAULT_TYPE[root])
    if hit and (hit[0] == "VISITOR_SERVICES" or hit[1] in STANDALONE_TYPES):
        return hit
    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


MUNI_BY_NORM = {norm(m["name"]): m["name"] for m in MUNICIPALITIES}
REGION_BY_MUNI = {m["name"]: m["region"] for m in MUNICIPALITIES}


def nearest_muni(lat, lng):   # only a de-duplication key for places with no address locality (parse_places); every published municipality comes from make_muni_locator
    return min(MUNICIPALITIES, key=lambda m: (lat - m["lat"]) ** 2 + ((lng - m["lng"]) * cos(radians(lat))) ** 2)["name"]


def distance_m(a, b):
    dlat = (b[0] - a[0]) * 111_320
    dlng = (b[1] - a[1]) * 111_320 * cos(radians((a[0] + b[0]) / 2))
    return sqrt(dlat * dlat + dlng * dlng)


def arcgis_geojson(url, where="1=1", out_fields="*", bbox=None, page=500, label="", order="OBJECTID"):
    """Page through an ArcGIS REST layer and return a GeoJSON FeatureCollection.

    Each page is cached on disk (cache/pages/<label>/<offset>.json) so an interrupted download
    resumes where it stopped; FEMA's server in particular resets long-running connections.
    """
    pages_dir = CACHE / "pages" / re.sub(r"[^A-Za-z0-9_-]+", "_", label or "layer")
    pages_dir.mkdir(parents=True, exist_ok=True)
    features, offset = [], 0
    session = requests.Session()
    session.headers.update({"Accept-Encoding": "gzip", "User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"})
    while True:
        page_file = pages_dir / f"{offset}.json"
        if page_file.exists():
            data = json.loads(page_file.read_text(encoding="utf-8"))
        else:
            params = {
                "where": where, "outFields": out_fields, "f": "geojson", "outSR": 4326, "geometryPrecision": 6,
                "orderByFields": order, "resultOffset": offset, "resultRecordCount": page,
            }
            if bbox:
                params.update({"geometry": ",".join(map(str, bbox)), "geometryType": "esriGeometryEnvelope",
                               "inSR": 4326, "spatialRel": "esriSpatialRelIntersects"})
            for attempt in range(8):
                try:
                    r = session.get(f"{url}/query", params=params, timeout=300)
                    r.raise_for_status()
                    data = r.json()
                    if "error" in data:
                        raise RuntimeError(f"{label}: {data['error']}")
                    break
                except Exception as e:  # transient 5xx / resets are common on these servers
                    if attempt == 7:
                        raise
                    wait = min(60, 4 * 2 ** attempt)
                    print(f"  {label}: offset {offset} retry {attempt + 1} after {type(e).__name__}; waiting {wait}s", flush=True)
                    time.sleep(wait)
                    session = requests.Session()
                    session.headers.update({"Accept-Encoding": "gzip", "User-Agent": "pr-digital-twin/1.0"})
            page_file.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        batch = data.get("features", [])
        features.extend(batch)
        print(f"  {label}: {len(features):,} features", flush=True)
        if len(batch) < page:
            break
        offset += page
    return {"type": "FeatureCollection", "features": features}


def cached(path: Path, producer, refresh: bool):
    if path.exists() and not refresh:
        print(f"  using cache {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))
    data = producer()
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data


def simplify_fc(fc, tolerance, keep_props):
    out = []
    for ft in fc["features"]:
        try:
            g = shape(ft["geometry"]).simplify(tolerance, preserve_topology=True)
        except Exception:
            continue
        if g.is_empty:
            continue
        out.append({"type": "Feature", "properties": {k: ft["properties"].get(k) for k in keep_props},
                    "geometry": g.__geo_interface__})
    return {"type": "FeatureCollection", "features": out}


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1048576:.1f} MB)")


# ── Steps ────────────────────────────────────────────────────────────────────

def step_overture(refresh):
    path = CACHE / "overture_pr_places.geojson"
    if path.exists() and not refresh:
        print(f"  using cache {path.name}")
    else:
        exe = ROOT / "venv" / "Scripts" / "overturemaps.exe"
        cmd = [str(exe) if exe.exists() else "overturemaps", "download", f"--bbox={','.join(map(str, BBOX))}", "-f", "geojson", "--type=place", "-o", str(path)]
        print("  downloading Overture places:", " ".join(cmd[1:]))
        subprocess.run(cmd, check=True)
    return json.loads(path.read_text(encoding="utf-8"))


def parse_places(fc):
    places, dropped = [], Counter()
    for ft in fc["features"]:
        p = ft["properties"]
        lng, lat = ft["geometry"]["coordinates"][:2]
        tax = p.get("taxonomy") or {}
        primary = tax.get("primary") or p.get("basic_category")
        cls = classify(primary, tax.get("hierarchy") or [])
        if not cls:
            dropped[primary or "(none)"] += 1
            continue
        addrs = p.get("addresses") or []
        a0 = addrs[0] if addrs else {}
        muni = MUNI_BY_NORM.get(norm(a0.get("locality") or "")) or nearest_muni(lat, lng)
        src = (p.get("sources") or [{}])[0]
        places.append({
            "oid": ft.get("id") or p.get("id"),   # Overture record id (feature level in the GeoJSON export)
            "name": (p.get("names") or {}).get("primary") or "",
            "category": cls[0], "type": cls[1], "overture_category": primary,
            "municipality": muni, "region": REGION_BY_MUNI.get(muni, ""),
            "lat": round(lat, 6), "lng": round(lng, 6),
            "address": (a0.get("freeform") or "").strip() or None,
            "postcode": a0.get("postcode") or None,
            "website": (p.get("websites") or [None])[0],
            "phone": (p.get("phones") or [None])[0],
            "email": (p.get("emails") or [None])[0],
            "socials": p.get("socials") or [],
            "brand": ((p.get("brand") or {}).get("names") or {}).get("primary"),
            "confidence": round(p.get("confidence") or 0, 3),
            "source": src.get("dataset"), "source_license": src.get("license"),
            "updated": (src.get("update_time") or "")[:10] or None,
        })
    return places, dropped


GENERIC = set("""the el la los las de del y and a an of at in en por para con un una playa beach balneario parque park plaza
restaurante restaurant cafe cafeteria coffee bar pub bakery panaderia pizza pizzeria hotel hostal hostel inn posada guesthouse
guest house villa villas resort apartamentos apartments apartment apto studio suite suites casa home museo museum galeria gallery
teatro theater centro center cultural tour tours travel marina puerto pr puerto rico llc inc corp iglesia church capilla
universidad university escuela school""".split())
for _m in MUNICIPALITIES:
    GENERIC.update(norm(_m["name"]).replace("-", " ").split())


def name_tokens(name):
    return {t for t in re.sub(r"[^a-z0-9 ]+", " ", norm(name)).split() if len(t) >= 3 and t not in GENERIC}


def similarity(a, b):
    if not a or not b:
        return 0.0
    inter = a & b
    if not inter or not any(len(t) >= 4 for t in inter):
        return 0.0
    jacc = len(inter) / len(a | b)
    shorter, longer = min(len(a), len(b)), max(len(a), len(b))
    return max(jacc, len(inter) / shorter * 0.9) if (shorter >= 2 or longer <= 2) else jacc


def dedup(places):
    """Group listings of the same place (same municipality + category) and keep the best record."""
    NATURAL = {"Beaches", "Parks", "Nature Reserves", "Scenic Areas", "Historic Sites", "Tourist Attractions"}
    by_key = defaultdict(list)
    for i, p in enumerate(places):
        by_key[(p["municipality"], p["category"])].append(i)
    tokens = [name_tokens(p["name"]) for p in places]
    parent = list(range(len(places)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for idxs in by_key.values():
        cell = defaultdict(list)
        for i in idxs:
            cell[(int(places[i]["lat"] / 0.009), int(places[i]["lng"] / 0.009))].append(i)
        for (ci, cj), bucket in cell.items():
            neigh = [j for di in (-1, 0, 1) for dj in (-1, 0, 1) for j in cell.get((ci + di, cj + dj), [])]
            for i in bucket:
                pi = places[i]
                for j in neigh:
                    if j <= i:
                        continue
                    pj = places[j]
                    d = distance_m((pi["lat"], pi["lng"]), (pj["lat"], pj["lng"]))
                    natural = pi["type"] in NATURAL or pj["type"] in NATURAL
                    if d > (1000 if natural else 600):
                        continue
                    sim = similarity(tokens[i], tokens[j])
                    same_phone = pi["phone"] and pi["phone"] == pj["phone"]
                    if (sim >= 0.95) or (sim >= 0.8 and d <= (600 if natural else 150)) or (same_phone and sim >= 0.5 and d <= 500):
                        parent[find(j)] = find(i)

    groups = defaultdict(list)
    for i in range(len(places)):
        groups[find(i)].append(i)
    kept, dup_count = [], 0
    for members in groups.values():
        best = max(members, key=lambda i: (places[i]["confidence"],
                                            sum(1 for k in ("website", "phone", "email", "address") if places[i][k]),
                                            len(places[i]["socials"])))
        p = dict(places[best])
        p["duplicates"] = len(members) - 1
        dup_count += len(members) - 1
        kept.append(p)
    return kept, dup_count


def step_flood(refresh):
    print("FEMA flood zones")
    fc = cached(CACHE / "fema_nfhl_pr.geojson", lambda: arcgis_geojson(
        SOURCES["fema"]["url"], where="DFIRM_ID LIKE '72%'", out_fields="FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE", page=250, label="NFHL"), refresh)
    return fc


def step_protected(refresh):
    print("USGS PAD-US protected areas")
    return cached(CACHE / "padus_pr.geojson", lambda: arcgis_geojson(
        SOURCES["padus"]["url"], where="State_Nm='PR'", out_fields="Unit_Nm,Mang_Name,Des_Tp,GAP_Sts,Category,Pub_Access,GIS_Acres", page=500, label="PAD-US"), refresh)


def step_census(refresh):
    print("Census municipalities + 2020 population")
    return cached(CACHE / "tiger_pr_counties.geojson", lambda: arcgis_geojson(
        SOURCES["census"]["url"], where="STATE='72'", out_fields="NAME,GEOID,POP100,HU100,AREALAND,AREAWATER", label="TIGERweb"), refresh)


def step_census_shoreline(refresh):
    """Generalized (500k) county boundaries clipped to the shoreline, for display and point lookup.
    The legal boundaries in the 2020 layer extend 3 nautical miles into the sea."""
    print("Census shoreline-clipped boundaries")
    return cached(CACHE / "tiger_pr_counties_500k.geojson", lambda: arcgis_geojson(
        SOURCES["census_shore"]["url"], where="STATE='72'", out_fields="NAME,GEOID,BASENAME,AREALAND,AREAWATER", label="TIGERweb 500k"), refresh)


def point_flags(places, flood_fc, protected_fc):
    """Flag each place with the flood zone and protected area it falls in (point-in-polygon)."""
    print("Spatial flags (point-in-polygon)")
    flood_geoms, flood_props = [], []
    for ft in flood_fc["features"]:
        pr = ft["properties"]
        if pr.get("FLD_ZONE") in (None, "AREA NOT INCLUDED", "OPEN WATER"):
            continue
        try:
            flood_geoms.append(shape(ft["geometry"])); flood_props.append(pr)
        except Exception:
            pass
    prot_geoms, prot_props = [], []
    for ft in protected_fc["features"]:
        try:
            prot_geoms.append(shape(ft["geometry"])); prot_props.append(ft["properties"])
        except Exception:
            pass
    ftree, ptree = STRtree(flood_geoms), STRtree(prot_geoms)
    for p in places:
        pt = Point(p["lng"], p["lat"])
        p["flood_zone"], p["flood_subtype"], p["sfha"], p["protected_area"], p["protected_gap"] = None, None, False, None, None
        hits = ftree.query(pt, predicate="within")
        if len(hits):
            # prefer a Special Flood Hazard Area if the point sits in overlapping polygons
            best = max(hits, key=lambda i: (flood_props[i].get("SFHA_TF") == "T", "0.2" in (flood_props[i].get("ZONE_SUBTY") or "")))
            fp = flood_props[best]
            p["sfha"] = fp.get("SFHA_TF") == "T"
            # record only mapped hazard: the SFHA (1%) or the 0.2% annual chance zone; unshaded X = minimal risk
            if p["sfha"] or "0.2" in (fp.get("ZONE_SUBTY") or ""):
                p["flood_zone"] = fp.get("FLD_ZONE")
                p["flood_subtype"] = fp.get("ZONE_SUBTY") or None
        hits = ptree.query(pt, predicate="within")
        # Proclamation boundaries (Des_Tp PROC) outline whole islands or refuges but are not themselves managed land:
        # they are drawn on the map but do not count a place as "inside a protected area".
        real = [i for i in hits if prot_props[i].get("Des_Tp") != "PROC"]
        if real:
            best = min(real, key=lambda i: str(prot_props[i].get("GAP_Sts") or "9"))   # strictest GAP status wins
            p["protected_area"] = prot_props[best].get("Unit_Nm")
            p["protected_gap"] = prot_props[best].get("GAP_Sts")
    print(f"  in 1% or 0.2% flood zones: {sum(1 for p in places if p['flood_zone']):,} | in SFHA: {sum(1 for p in places if p['sfha']):,} | in protected areas: {sum(1 for p in places if p['protected_area']):,}")


def make_muni_locator(census_fc):
    """Point-in-polygon municipality lookup from the Census boundaries; a point outside every outline (a pier, a shore stop, an offshore pin) takes the nearest outline (muni_locate.py)."""
    geoms, names = [], []
    for ft in census_fc["features"]:
        name = MUNI_BY_NORM.get(norm(re.sub(r"\s+Municipio$", "", ft["properties"].get("NAME", ""))))
        if name:
            try:
                geoms.append(shape(ft["geometry"])); names.append(name)
            except Exception:
                pass
    return muni_locate.Locator(geoms, names)


def municipality_stats(places, census_fc):
    pop = {}
    for ft in census_fc["features"]:
        pr = ft["properties"]
        name = MUNI_BY_NORM.get(norm(re.sub(r"\s+Municipio$", "", pr.get("NAME", ""))))
        if name:
            pop[name] = {"population_2020": int(pr.get("POP100") or 0), "housing_units_2020": int(pr.get("HU100") or 0),
                         "land_km2": round((pr.get("AREALAND") or 0) / 1e6, 1)}
    stats = {}
    for m in MUNICIPALITIES:
        n = m["name"]
        mine = [p for p in places if p["municipality"] == n]
        by_cat = Counter(p["category"] for p in mine)
        core = [p for p in mine if p["type"] != "Places of Worship" and p["confidence"] >= MIN_CONF]
        s = {
            "municipality": n, "region": m["region"],
            "assets": len(core), "assets_all_confidence": sum(1 for p in mine if p["type"] != "Places of Worship"), "listings_all": len(mine),
            "by_category": {c: sum(1 for p in core if p["category"] == c) for c in ("ATTRACTIONS", "GASTRONOMY", "ACCOMMODATIONS", "VISITOR_SERVICES")},
            "in_sfha": sum(1 for p in core if p["sfha"]),
            "in_flood_zone": sum(1 for p in core if p["flood_zone"]),
            "in_protected": sum(1 for p in core if p["protected_area"]),
            "avg_confidence": round(sum(p["confidence"] for p in core) / len(core), 3) if core else None,
            "with_website": sum(1 for p in core if p["website"]),
        }
        s.update(pop.get(n, {}))
        if s.get("population_2020"):
            s["assets_per_1000_residents"] = round(s["assets"] / s["population_2020"] * 1000, 2)
        if s.get("land_km2"):
            s["assets_per_km2"] = round(s["assets"] / s["land_km2"], 2)
        s["sfha_pct"] = round(s["in_sfha"] / s["assets"] * 100, 1) if s["assets"] else None
        stats[n] = s
    return stats, pop


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download all sources")
    ap.add_argument("--label", default=None)
    ap.add_argument("--refresh-network", action="store_true", help="re-download only the transit feeds, the feed registry and OSM routes (used by the nightly refresh)")
    args = ap.parse_args()
    CACHE.mkdir(exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print("Overture places")
    raw = step_overture(args.refresh)
    places, dropped = parse_places(raw)
    print(f"  {len(raw['features']):,} places in bbox -> {len(places):,} tourism-relevant listings")
    places, dup_count = dedup(places)
    print(f"  de-duplicated: {dup_count:,} duplicate listings folded -> {len(places):,} unique places")
    rv = places_privacy.load_review()
    places_privacy.classify(places, rv)   # private homes, housing, addresses, care services and holiday rentals: never drawn (places_review.json)
    # what is not tourism supply (homes, housing, care services, numbered homes filed where homes are filed) is not counted either: dropped before
    # every count and never published (HANDOFF decision 47, 2026-10-18); holiday rentals stay counted, not drawn
    not_tourism = Counter(p["withheld"] for p in places if places_privacy.not_tourism(p, rv))
    places = [p for p in places if not places_privacy.not_tourism(p, rv)]
    withheld = Counter(p["withheld"] for p in places if p["withheld"])
    print(f"  not tourism, left out of every count: {sum(not_tourism.values()):,} ({', '.join(f'{k} {v:,}' for k, v in not_tourism.most_common())}) -> {len(places):,} places")
    print(f"  counted but not drawn: {sum(withheld.values()):,} ({', '.join(f'{k} {v:,}' for k, v in withheld.most_common())})")

    flood = step_flood(args.refresh)
    protected = step_protected(args.refresh)
    census = step_census(args.refresh)
    shore = step_census_shoreline(args.refresh)
    nearest_muni_or_locality = make_muni_locator(shore)
    # The municipality is where the pin sits (point-in-polygon), so counts agree with the polygons the map draws.
    # The address locality was only used above to block the de-duplication; offshore pins take the nearest outline.
    moved = 0
    for p in places:
        m = nearest_muni_or_locality(p["lat"], p["lng"])
        moved += m != p["municipality"]
        p["municipality"], p["region"] = m, REGION_BY_MUNI.get(m, "")
    print(f"  municipality set from the pin location; {moved:,} listings differ from their address locality")
    point_flags(places, flood, protected)
    stats, pop = municipality_stats(places, census)
    net = build_network(CACHE, args.refresh or args.refresh_network, MUNI_BY_NORM, roads=load_roads(OUT), previous=previous_routes(OUT))
    print("Transportation")
    transport, routes_fc, transport_meta, access_res = build_transport(CACHE, args.refresh, places, nearest_muni_or_locality, stats, net)
    for i, p in enumerate(places):   # a withheld place has no point in places.json: the nightly access refresh counts it from these (access.compute)
        if p["withheld"] and access_res.hub400[i]:
            p["hub_400m"] = True
    print("Time series")
    trips = trip_paths.trip_doc("weekday (typical Wednesday service)", net["trips"]["wk"], net["trip_paths"]["wk"])   # vehicles follow the route lines
    storms = load_hurricanes(CACHE, args.refresh)
    pop2010 = load_population_2010(CACHE, args.refresh)
    geoid_by_name = {}
    for ft in census["features"]:
        n = MUNI_BY_NORM.get(norm(re.sub(r"\s+Municipio$", "", ft["properties"].get("NAME", ""))))
        if n:
            geoid_by_name[n] = ft["properties"].get("GEOID")
    for n, st in stats.items():
        p10 = pop2010.get(geoid_by_name.get(n), {})
        st.update(p10)
        if p10.get("population_2010") and st.get("population_2020"):
            st["pop_change_pct"] = round((st["population_2020"] - p10["population_2010"]) / p10["population_2010"] * 100, 1)
    housing_paper, housing_meta = build_housing(CACHE, args.refresh, stats, geoid_by_name, pop)
    print("Service coverage and integration")
    muni_by_fips = {g[:5]: n for n, g in geoid_by_name.items()}
    inactive = {k for k, o in net["operators"].items() if o["feed"]["status"] == "expired"}
    import walknet
    blocks, cov = coverage(load_blocks(CACHE / "network", args.refresh), net["stops"], muni_by_fips, inactive, net=walknet.load())   # residents also by walking along mapped roads
    xfers, n_xfers = transfers(net["stops"])
    muni_op = {o["municipality"]: o for o in net["operators"].values() if o.get("municipality")}
    for n, st in stats.items():
        c = cov.get(n, {})
        st.update({"pop_served_400m": c.get("served"), "pop_served_pct": c.get("served_pct"), "pop_served_active_pct": c.get("served_active_pct"), "pop_served_ati": c.get("served_ati"), "pop_served_muni": c.get("served_muni"),
                   "pop_walk_400m": c.get("walk_served"), "pop_walk_pct": c.get("walk_served_pct"), "pop_walk_active_pct": c.get("walk_served_active_pct")})   # walking along mapped roads (network.coverage)
        o = muni_op.get(n)
        st["muni_system"] = o["feed"]["status"] if o else None   # NTD-reporting municipal system and the state of its public feed
        st["muni_system_routes"] = o["routes"] if o else 0
    print("Land use")
    landuse_summary = {}
    landuse_fc, landuse_meta = build_landuse(CACHE, args.refresh, places, stats, lambda n: MUNI_BY_NORM.get(norm(n)), summary_out=landuse_summary)
    # Barrios: CRIM's Catastro licence text restricts republishing; publish only after swapping the source to Census
    # TIGERweb County Subdivisions (public domain, same GEOIDs) or with CRIM's written authorization. See CATASTRO_ASSESSMENT_2026-10-01.md.
    PUBLISH_BARRIOS = True   # Census county subdivisions (public domain); the CRIM copy is no longer used
    fips_to_muni = {g[:5]: n for n, g in geoid_by_name.items()}
    barrios_fc, barrios_meta = (build_barrios(CACHE, args.refresh, places, fips_to_muni.get, access_res) if PUBLISH_BARRIOS else ({"type": "FeatureCollection", "features": []}, {"barrios": 0, "published": False}))

    print("Writing site/data")
    # keep the file small: drop the contact fields, the region (derived from the municipality in the browser) and empty values; a withheld place
    # also loses its name, Overture id, point and nearest stop (places_privacy.py)
    # the withheld rows go last, in an order of their own (places_privacy.publish_order): Overture's order follows location
    rows = [places_privacy.public_row(p) for p in places]
    order = places_privacy.publish_order(rows)
    dump(OUT / "places.json", [rows[i] for i in order])
    dump(OUT / "municipalities.json", stats)
    dump(OUT / "transport.json", transport)
    dump(OUT / "transit_routes.geojson", routes_fc)
    dump(OUT / "trips.json", trips)
    for d, label in (("sa", "Saturday"), ("su", "Sunday")):
        dump(OUT / f"trips_{d}.json", trip_paths.trip_doc(label, net["trips"][d], net["trip_paths"][d]))   # loaded by the 2D map on weekends
    dump(OUT / "operators.json", {"built": net["built"], "operators": sorted(net["operators"].values(), key=lambda o: (o["feed"]["status"] in ("none",), o["type"] != "regional", o["short"] or o["name"])),
                                  "live": {"checked": LIVE_CHECKED, "sources": LIVE_SOURCES},
                                  "coverage": cov, "transfers": xfers, "transfers_total": n_xfers})
    supply.apply(OUT)   # transit_supply.json: scheduled service by stop pattern, route and stop (reads the trips files and operators.json above)
    dump(OUT / "population_blocks.json", blocks)   # [lon, lat, residents, metres to the nearest scheduled stop]
    dump(OUT / "hurricanes.json", storms)
    dump(OUT / "housing.json", housing_paper)
    dump(OUT / "landuse.geojson", landuse_fc)
    dump(OUT / "landuse_summary.json", landuse_summary)   # km² of each land-use class by municipality and for Puerto Rico (the land-use analysis view)
    if PUBLISH_BARRIOS:
        dump(OUT / "barrios.geojson", barrios_fc)
    dump(OUT / "flood.geojson", simplify_fc(flood, 0.00005, ["FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"]))
    dump(OUT / "protected.geojson", simplify_fc(protected, 0.00005, ["Unit_Nm", "Mang_Name", "Des_Tp", "GAP_Sts", "Pub_Access", "GIS_Acres"]))
    pop_by_geoid = {ft["properties"].get("GEOID"): ft["properties"] for ft in census["features"]}
    muni_fc = simplify_fc(shore, 0.0002, ["NAME", "GEOID", "AREALAND"])
    for ft in muni_fc["features"]:
        src = pop_by_geoid.get(ft["properties"].get("GEOID"), {})
        ft["properties"]["POP100"], ft["properties"]["HU100"] = src.get("POP100"), src.get("HU100")
        name = MUNI_BY_NORM.get(norm(re.sub(r"\s+Municipio$", "", ft["properties"].get("NAME", ""))))
        ft["properties"]["municipality"] = name
        ft["properties"]["region"] = REGION_BY_MUNI.get(name, "")
    dump(OUT / "municipios.geojson", muni_fc)

    generated = datetime.now(timezone.utc)
    meta = {
        "label": args.label or f"Snapshot {generated:%Y-%m}",
        "generated_at": generated.isoformat(timespec="seconds"),
        "bbox": BBOX,
        "counts": {
            "overture_places_in_bbox": len(raw["features"]),
            "tourism_places": sum(1 for p in places if p["type"] != "Places of Worship" and p["confidence"] >= MIN_CONF),
            "tourism_places_all_confidence": sum(1 for p in places if p["type"] != "Places of Worship"),
            "listings_total": len(places), "min_confidence": MIN_CONF, "duplicates_folded": dup_count, "not_tourism_dropped": sum(not_tourism.values()),
            "worship_places": sum(1 for p in places if p["type"] == "Places of Worship"),
            "flood_polygons": len(flood["features"]), "protected_units": len(protected["features"]),
            "municipalities": len(stats), "population_2020": sum(v.get("population_2020", 0) for v in pop.values()),
        },
        "sources": {**SOURCES, **TRANSPORT_SOURCES, **NETWORK_SOURCES, **TIME_SOURCES, **HOUSING_SOURCES, **{f"housing_{k}": v for k, v in housing_series.SOURCES.items()}, **{f"economy_{k}": v for k, v in economy_series.SOURCES.items()}, **LANDUSE_SOURCES},
        "housing": housing_meta,
        "landuse": landuse_meta,
        "barrios": barrios_meta,
        "transport": transport_meta,
        "access": access.island_summary(places, access_res, net["operators"], access_res.as_of),
        "network": {"built": net["built"], "operators": len(net["operators"]), "by_status": {k: sum(1 for o in net["operators"].values() if o["feed"]["status"] == k) for k in sorted({o["feed"]["status"] for o in net["operators"].values()})},
                    "routes": len(net["routes"]), "scheduled_stops": len(net["stops"]), "weekday_trips": len(net["trips"]["wk"]),
                    "residents": sum(c["pop"] for c in cov.values()), "residents_within_400m": sum(c["served"] for c in cov.values()),
                    "residents_walk_400m": sum(c.get("walk_served", 0) for c in cov.values())},
        "time": {"trips": len(trips["trips"]), "trips_day": trips["day"], "storms_near_pr": len(storms),
                 "major_hurricanes_near_pr": sum(1 for s in storms if (s.get("cat_near_pr") or 0) >= 3),
                 "storm_years": [storms[0]["year"], storms[-1]["year"]] if storms else None},
        "taxonomy_dropped_top": dropped.most_common(25),
    }
    dump(OUT / "meta.json", meta)
    dump(OUT / "place_access.json", places_privacy.permute_columns(places_privacy.coarsen_columns(access.columns_doc(access_res, meta["generated_at"]), places), order))   # per-place columns, in the order of places.json; meta.generated_at ties the two files together
    geo.build(args.refresh)              # the geography crosswalk and the tract and block group outlines (needs municipios.geojson and barrios.geojson, written above; the contract checks join keys against it)
    opportunity_zones.build(args.refresh)   # Opportunity Zones 2.0: every tract's status, residents in zones by barrio and municipio, the map layer (US Treasury; needs the crosswalk and the tract outlines, written above; docs/opportunity-zones.md)
    traffic.build(args.refresh)   # traffic on the main roads and by municipio (FHWA HPMS; needs municipios.geojson, written above; docs/traffic.md)
    crashes.build(args.refresh)   # people killed in traffic crashes by municipio and year (NHTSA FARS; needs municipios.geojson, housing_series.json and traffic_series.json; docs/road-safety.md)
    transport_inventories.build(args.refresh)   # bridges and tunnels, airports, ferry routes and EV charging as map layers (FHWA, FAA, BTS, DOE; needs municipios.geojson; docs/transport-inventories.md)
    transit_links.build(args.refresh)   # workers who travel between municipios, the route listed for each pair, the simulated connections and the público routes of 2020 (needs trips*.json, transport.json, operators.json and municipios.geojson, written above, and roads.bin and gazetteer.json, which roads.py and gazetteer.py write; docs/transit-links.md)
    commuting.build(args.refresh)   # daytime population and commuting by municipio, calculated from the same flows table and the 2020 Census (docs/commuting.md)
    credit.build(args.refresh)   # insured bank offices and deposits (FDIC Summary of Deposits) and home loans (HMDA) by municipio and year (docs/credit.md)
    drought.build(args.refresh)   # drought by municipio and year from the weekly US Drought Monitor (docs/drought.md)
    storm_recovery.build()   # months for night-time light to come back after María and Fiona, from nightlights_monthly.json (docs/storm_recovery.md)
    essentials.build()   # road distance to essentials, from cache/essentials/points.json (python essentials.py --refresh makes it; docs/essentials.md)
    jobs_reach.build()   # jobs within 30 and 45 minutes by car, by municipio, from QCEW jobs, roads.bin and cache/jobs_reach (docs/jobs-reach.md)
    cutoff.build()   # residents cut off from every hospital when flooded roads or poor bridges close, from roads.bin, flood.geojson and bridges.geojson (docs/cutoff.md)
    degrees.build()   # degrees awarded by level and field, IPEDS (docs/degrees.md)
    school_conditions.build()   # school conditions from the Civil Rights Data Collection (docs/school_conditions.md)
    proficiency.build()   # META-PR results by municipio, EDFacts (docs/proficiency.md)
    providers.build()   # health care providers by type, NPPES (docs/providers.md)
    svi.build(args.refresh)   # CDC/ATSDR Social Vulnerability Index 2022 for the municipios and the census tracts (docs/svi.md)
    facility_exposure.build(args.refresh)   # public facilities, students and main roads inside FEMA's 1% flood area, by municipio (needs flood.geojson, the facility layers and traffic_roads.geojson; docs/facility-exposure.md)
    exposure.build(refresh=args.refresh)   # residents and housing units exposed to flood, sea level rise and protected land and near transit, by municipio, barrio and tract (needs flood.geojson, protected.geojson, transport.json, operators.json and the crosswalk, all written above)
    watersheds.build(args.refresh)   # subwatersheds, streams and the catchments of What drains here (USGS WBD and NHDPlus HR; docs/watersheds.md)
    upstream.build()   # what lies upstream of each reservoir and river gauge, from catchments.geojson and cache/upstream (python upstream.py --refresh fills it; docs/upstream.md)
    slope.build()   # the slope of the land by barrio and municipio, and the slope image of the maps (USGS 3DEP 10 m; docs/slope.md)
    climb.build()   # the climb on the walk to a current stop, by barrio and municipio (USGS 3DEP 10 m; the walkers of exposure.py; docs/climb.md)
    housing_series.build(args.refresh)   # every year of the housing variables (needs municipios.geojson, written above)
    economy_series.build(args.refresh)   # every year of the economy variables (jobs, labor force, income, commuting, federal money)
    health_series.build(args.refresh)    # health centers and shortage areas by municipio (HRSA; needs municipios.geojson; docs/health.md)
    infrastructure_series.build(args.refresh)    # drinking water, power plants and bridges by municipio (EPA ECHO, EIA-860M, FHWA NBI; docs/infrastructure.md)
    power_plants.build(args.refresh)   # the Power plants layer: one point per plant of 1 MW or more, MW by technology, no owner (EIA-860M; needs municipios.geojson; docs/energy.md)
    power_lines.build(args.refresh)   # the Transmission lines layer: OpenStreetMap 230/115/38 kV, simplified, substations counted (Overpass; needs municipios.geojson; docs/energy.md)
    energy_series.build(args.refresh)   # the Energy in Puerto Rico page: LUMA filings at the Energy Bureau, EIA-861M, plants, lines and floods (docs/energy.md)
    energy_municipios.build(args.refresh)   # energy by municipio and barrio for Explore and the profiles: batteries, sales, smart meters (LUMA) and electricity bills (ACS B25132) (docs/energy.md)
    environment_series.build(args.refresh)    # hazard loss, resilience, landslides, wetlands and earthquakes by municipio (FEMA NRI, Census CRE, USGS, USFWS NWI; docs/environment.md)
    gateway_series.build(args.refresh)   # air and ferry passengers by municipio (BTS T-100, FAA, BTS ferry census; needs transport.json, written above; docs/infrastructure.md)
    facilities.build(tuple(facilities.FILES) if args.refresh else ())   # public housing (HUD), fire stations (USGS), police stations (OpenStreetMap) and public libraries (USAC): points and counts by municipio (needs municipios.geojson; docs/facilities.md)
    river_gauges.build(args.refresh)   # river flow (USGS Water Data): the stream gauges reporting now, their last 120 days and the usual flow of each week; the page reads the latest live (needs municipios.geojson; docs/facilities.md)
    groundwater.build(args.refresh)   # groundwater levels (USGS Water Data): the wells reporting now, their last 120 days and the usual depth to water of each week; the page reads the latest live (needs municipios.geojson; docs/facilities.md)
    rain_gauges.build(args.refresh)   # rainfall (USGS Water Data): the rain gauges reporting now, their last 120 daily totals and the usual rain of each week; the page reads the last 24 hours and 7 days live (needs municipios.geojson; docs/facilities.md)
    reservoirs.build(args.refresh)   # reservoir levels (USGS Water Data): the reservoirs, their last 120 days and the usual level of each week; the page reads the latest live (needs municipios.geojson; docs/facilities.md)
    nonprofits.build(args.refresh)   # tax-exempt organizations by municipio and NTEE major group, counts only (IRS EO BMF; docs/facilities.md)
    landslide.build(args.refresh)   # landslide susceptibility (USGS, Hughes and Schulz 2020) by barrio and municipio: land and residents in the high classes (needs barrios.geojson, population_blocks.json and the environment cache; docs/landslide.md)
    heat.build(args.refresh)        # daytime land surface temperature by barrio and municipio, summer mornings (Landsat 8 and 9 via Planetary Computer, raster.py; docs/heat.md)
    buildings.build(args.refresh)   # buildings by barrio and municipio: counts, land under roofs, footprint size, flood hazard areas (Overture buildings theme; docs/buildings.md)
    vegetation.build(args.refresh)  # vegetation greenness (NDVI) by barrio and municipio, summer (Sentinel-2 L2A via Earth Search, raster.py; after heat.build, whose barrio file it checks against; docs/vegetation.md)
    if ecostress.token():
        ecostress.build(args.refresh)   # night-time land surface temperature by barrio and municipio, summer nights (NASA ECOSTRESS via the LP DAAC; needs EARTHDATA_TOKEN, without it the published files stay; docs/ecostress.md)
    community_assets.build(community_assets.SOURCE_KEYS if args.refresh else ())   # historic places (NPS) and city halls (OpenStreetMap) as points; historic places and treatment facilities (SAMHSA, counts only) by municipio (docs/community.md)
    conditions.build(conditions.SOURCE_KEYS if args.refresh else ())   # EPA sites, impaired waters, non-attainment, severe housing problems, street intersections and drive time to a hospital, by barrio and municipio (needs barrios.geojson, roads.bin, gazetteer.json; docs/conditions.md)
    care_series.build(args.refresh)    # hospitals and care facilities (CMS) and distance to a health center (care_access.py; docs/health.md)
    medicare_series.build(args.refresh)    # Medicare enrollment by municipio since 2013 (CMS; docs/health.md)
    education_series.build(args.refresh)    # public schools and colleges by municipio, every school year since 2010 (NCES via the Urban Institute; docs/education.md)
    ogp_budget.main(["--refresh"] if args.refresh else [])   # the Commonwealth budget by agency, fund, function and concept: spent, approved, proposed (OGP data sheets; spending_state.json, decision 77)
    pica.main(["--refresh"] if args.refresh else [])   # capital projects by municipio from the Planning Board's PICA (needs pdftotext; spending_pica.json, decision 79)
    federal_awards.main(["--refresh"] if args.refresh else [])   # federal money in Puerto Rico by function, program and award type (USAspending; spending_federal.json, decision 83)
    federal_outlays.main(["--refresh"] if args.refresh else [])   # federal grants and contracts obligated and paid out (USAspending; spending_outlays.json, decision 96)
    unused_funds.main(["--refresh"] if args.refresh else [])   # federal grants that ended with an unpaid balance (USAspending; unused_funds.json, decision 110); after federal_outlays, whose file names the programs
    taken_back.main(["--refresh"] if args.refresh else [])   # federal grant money taken back: the net reduction of each grant (USAspending transactions; taken_back.json, decision 110, step 2)
    audit_findings.main([])   # single audit findings and the findings that repeat (Federal Audit Clearinghouse; audit_findings.json, decision 110, step 3); refreshed by hand, because the public key allows ten calls an hour
    cdbg_dr.main(["--refresh"] if args.refresh else [])
    fema_pa_stage.main(["--refresh"] if args.refresh else [])
    municipio_view.main([])   # My municipio: one row per municipio from the files above and economy_series.json (spending_municipio.json, decision 109)   # FEMA Public Assistance by stage and age (OpenFEMA; spending_fema_pa.json, decision 109)   # disaster recovery grant subawards by municipio (USAspending; spending_cdbgdr.json, decision 89)
    cdbg_regular.main(["--refresh"] if args.refresh else [])   # HUD's yearly CDBG by municipio: entitlement grants and state program subawards (USAspending; spending_cdbg.json, decision 100)
    public_money_need.main([])   # FEMA money of 2017-2025, HUD CDBG money and two measures of need by municipio (reads economy, housing, environment and hazard series and the two CDBG files; public_money_need.json is the Knowledge Area page's file)
    women_labor.main(["--refresh"] if args.refresh else [])   # women's and men's labor force participation by municipio and region, three ACS windows that share no year (B23001; needs the crosswalk and economy_series.json; women_labor.json is the Knowledge Area page's file)
    inflation.write(args.refresh)   # consumer prices in Puerto Rico (DTRH) and the US (BLS), the five-year projection and its backtest, household income (ACS 1-year), Social Security adjustments (inflation.json, the Knowledge Area page's file; decision 95)
    small_area.build(args.refresh)       # the Population domain's municipal series and the survey estimates for barrios, census tracts and block groups (needs the crosswalk written by geo.build above; docs/small-area.md)
    _, dict_problems, _ = dictionary.build()   # data dictionary page; warns about published fields no entry documents
    catalog.main([])                     # the file the map reads first (domains, headline figures, index of the dictionary); needs dictionary.json
    registry.main()                      # inventory and size of everything published (after the dictionary and the catalog, so their sizes are current)
    # the domain registry and data contract: the build fails on any violation (rules and the placement guide: docs/adding-data.md)
    problems, reviews = contract.validate_all(entry_ids={e["id"] for e in json.loads((OUT / "dictionary.json").read_text(encoding="utf-8"))["entries"]})
    n_errors = contract.report(problems, reviews)
    knowledge_failed = knowledge.main([])   # the Knowledge registry: checks knowledge_src/items.json, writes the area list and the home page's items (docs/knowledge-plan-2026-11.md)
    learn_failed = learn.main([])   # the Learn registry: checks learn_src/lessons.json and writes the lessons' figures from the data files written above (docs/learn.md)
    i18n_failed = i18n.main([])          # Spanish bundles for every page, and a check that every label in the data and every string in the scripts has Spanish (docs/i18n.md)
    over_budget = budget.main([])        # the compressed size of what each page loads before it is ready, against its budget (dictionary_src/routes.json; docs/performance.md)
    if n_errors or knowledge_failed or learn_failed or i18n_failed or over_budget or any(p[0] == "error" for p in dict_problems):
        raise SystemExit("Build stopped: the dictionary, the data contract, the Knowledge or Learn registry, the Spanish layer or the page-weight budget has errors (listed above). The files in site/data were written but must not be published until this is fixed.")
    print(f"Done in {time.time() - t0:.0f}s - {meta['label']}: {len(places):,} places, {sum(1 for p in places if p['sfha']):,} in Special Flood Hazard Areas")


if __name__ == "__main__":
    main()
