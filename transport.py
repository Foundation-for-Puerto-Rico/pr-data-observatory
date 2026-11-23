"""Transportation layer for the PR Data Observatory.

Sources (all open, all cached under cache/):
  GTFS feeds    ATI and the municipal systems: parsed by network.py, which hands the scheduled stops and routes in here.
  OpenStreetMap bus stops, bus stations, rail stations, ferry terminals, taxi stands, EV charging,
                aerodromes island-wide (municipal systems, públicos terminals). Overpass API. ODbL.
  FAA / NTAD    Airports (public and private use) in Puerto Rico. US Government work (not copyrighted; unrestricted public use).
  Uber          List of Puerto Rico municipalities on Uber's "cities" page (a service listing, not a
                coverage polygon). Recorded as a per-municipality flag with the date checked.
"""

import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import requests
from shapely.geometry import Point
from shapely.strtree import STRtree

import access

BBOX = (-67.97, 17.85, -65.20, 18.57)
GTFS_URL = "https://docs.pr.gov/files/ATI/DATOS_ABIERTOS/GTFS/PRITA_GTFS.zip"
# BTS NTAD Aviation Facilities (the old geo.dot.gov host stopped answering in 2026; FAA data, refreshed about every 28 days, effective date in EFF_DATE)
FAA_URL = "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Aviation_Facilities/FeatureServer/0"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
WALK_M = 400  # quarter mile: the standard walk-access distance to a transit stop

# Municipalities Uber lists on https://www.uber.com/global/en/r/united-states/puerto-rico/cities/ (checked 2026-10-01).
UBER_CHECKED = "2026-10-01"
UBER_LISTED = [
    "Aguada", "Aguadilla", "Aguas Buenas", "Añasco", "Arecibo", "Arroyo", "Barceloneta", "Bayamón", "Cabo Rojo", "Caguas",
    "Camuy", "Canóvanas", "Carolina", "Cataño", "Cayey", "Ceiba", "Cidra", "Coamo", "Corozal", "Dorado", "Fajardo",
    "Guánica", "Guayama", "Guayanilla", "Guaynabo", "Gurabo", "Hatillo", "Hormigueros", "Humacao", "Isabela", "Juana Díaz",
    "Juncos", "Lajas", "Lares", "Las Piedras", "Loíza", "Luquillo", "Manatí", "Mayagüez", "Naguabo", "Peñuelas", "Ponce",
    "Quebradillas", "Rincón", "Río Grande", "Salinas", "San Germán", "San Juan", "San Lorenzo", "Santa Isabel", "Toa Alta",
    "Toa Baja", "Trujillo Alto", "Vega Alta", "Vega Baja", "Yabucoa", "Yauco",
]

SOURCES = {
    "ati_gtfs": {
        "name": "Autoridad de Transporte Integrado (ATI) — GTFS open data",
        "url": "https://www.ati.pr.gov/relaciones-comunidad?tab=DatosAbiertos",
        "license": "Open data published by ATI (Gobierno de Puerto Rico)",
        "credit": "Transit routes and stops: ATI GTFS (Tren Urbano, AMA/Metrobús, AcuaExpreso)",
    },
    "osm_transport": {
        "name": "OpenStreetMap — stops, stations, terminals, taxi stands, EV charging",
        "url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "credit": "Stops and stations © OpenStreetMap contributors",
    },
    "faa_airports": {
        "name": "FAA airports via BTS National Transportation Atlas Database",
        "url": FAA_URL,
        "license": "US Government work (not copyrighted; unrestricted public use)",
        "credit": "Airports: FAA / BTS NTAD",
    },
    "uber": {
        "name": "Uber — cities served in Puerto Rico (service listing)",
        "url": "https://www.uber.com/global/en/r/united-states/puerto-rico/cities/",
        "license": "Public web page; recorded as a yes/no listing per municipality only",
        "credit": f"Ride-hailing availability: Uber cities page, checked {UBER_CHECKED}",
    },
}

ROUTE_TYPES = {"0": "tram", "1": "rail", "2": "rail", "3": "bus", "4": "ferry", "5": "cable", "6": "gondola", "7": "funicular"}
ROUTE_LABEL = {"rail": "Tren Urbano", "bus": "Bus", "ferry": "Ferry"}


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def cached_bytes(path: Path, url: str, refresh: bool, **kw) -> bytes:
    if path.exists() and not refresh:
        return path.read_bytes()
    r = requests.get(url, headers={"User-Agent": UA}, timeout=300, **kw)
    r.raise_for_status()
    path.write_bytes(r.content)
    return r.content


# ── OpenStreetMap ────────────────────────────────────────────────────────────

OSM_QUERY = """[out:json][timeout:180];
(
  node["highway"="bus_stop"]({s},{w},{n},{e});
  node["amenity"="bus_station"]({s},{w},{n},{e}); way["amenity"="bus_station"]({s},{w},{n},{e});
  node["railway"="station"]({s},{w},{n},{e}); node["public_transport"="station"]({s},{w},{n},{e});
  node["amenity"="ferry_terminal"]({s},{w},{n},{e}); way["amenity"="ferry_terminal"]({s},{w},{n},{e});
  node["amenity"="taxi"]({s},{w},{n},{e});
  node["amenity"="bicycle_rental"]({s},{w},{n},{e});
  node["amenity"="charging_station"]({s},{w},{n},{e});
  node["aeroway"="aerodrome"]({s},{w},{n},{e}); way["aeroway"="aerodrome"]({s},{w},{n},{e});
  node["aeroway"="helipad"]({s},{w},{n},{e});
);
out center tags;"""


def osm_kind(t):
    if t.get("railway") == "station" or (t.get("public_transport") == "station" and t.get("railway")):
        return "rail_station"
    if t.get("amenity") == "ferry_terminal":
        return "ferry_terminal"
    if t.get("amenity") == "bus_station" or t.get("public_transport") == "station":
        return "bus_station"
    if t.get("highway") == "bus_stop":
        return "bus_stop"
    if t.get("aeroway") == "aerodrome":
        return "airport"
    if t.get("aeroway") == "helipad":
        return "helipad"
    if t.get("amenity") == "taxi":
        return "taxi"
    if t.get("amenity") == "bicycle_rental":
        return "bike_rental"
    if t.get("amenity") == "charging_station":
        return "ev_charging"
    return None


def load_osm(cache: Path, refresh: bool):
    print("OpenStreetMap stops, stations and terminals")
    path = cache / "osm_transport.json"
    if path.exists() and not refresh:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        w, s, e, n = BBOX
        q = OSM_QUERY.format(s=s, w=w, n=n, e=e)
        data = None
        for ep in OVERPASS:
            try:
                r = requests.post(ep, data={"data": q}, headers={"User-Agent": UA}, timeout=300)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as ex:
                print(f"  {ep}: {type(ex).__name__}; trying next mirror")
                time.sleep(5)
        if data is None:
            raise RuntimeError("Overpass unavailable")
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    out = []
    for el in data.get("elements", []):
        t = el.get("tags") or {}
        kind = osm_kind(t)
        if not kind:
            continue
        lat, lng = (el.get("lat"), el.get("lon")) if el["type"] == "node" else ((el.get("center") or {}).get("lat"), (el.get("center") or {}).get("lon"))
        if lat is None:
            continue
        out.append({
            "id": f"osm:{el['type'][0]}{el['id']}", "kind": kind, "name": t.get("name") or t.get("ref") or "", "lat": round(lat, 6), "lng": round(lng, 6),
            "source": "osm_transport", "operator": t.get("operator") or t.get("network") or None,
            "shelter": t.get("shelter") == "yes", "wheelchair": t.get("wheelchair") == "yes",
            "iata": t.get("iata") or None, "icao": t.get("icao") or None,
        })
    print(f"  {len(out):,} features: " + ", ".join(f"{k} {v}" for k, v in Counter(o['kind'] for o in out).most_common()))
    return out


# ── FAA airports ─────────────────────────────────────────────────────────────

def load_airports(cache: Path, refresh: bool):
    print("FAA airports (NTAD)")
    path = cache / "ntad_airports_pr.json"
    if path.exists() and not refresh:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        r = requests.get(f"{FAA_URL}/query", params={"where": "STATE_CODE='PR' AND SITE_TYPE_CODE='A'", "outFields": "ARPT_NAME,CITY,SITE_TYPE_CODE,FACILITY_USE_CODE,OWNERSHIP_TYPE_CODE,ARPT_ID,ARPT_STATUS,EFF_DATE", "f": "geojson", "outSR": 4326}, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data), encoding="utf-8")
    out = []
    for ft in data.get("features", []):
        p = ft["properties"]
        lng, lat = ft["geometry"]["coordinates"][:2]
        out.append({"id": f"faa:{p.get('ARPT_ID')}", "kind": "airport", "name": (p.get("ARPT_NAME") or "").title(), "lat": round(lat, 6), "lng": round(lng, 6),
                    "source": "faa_airports", "public_use": p.get("FACILITY_USE_CODE") == "PU", "city": (p.get("CITY") or "").title(), "code": p.get("ARPT_ID")})
    print(f"  {len(out)} airports ({sum(1 for a in out if a['public_use'])} public use)")
    return out


# ── Assembly and analytics ───────────────────────────────────────────────────

def _dist_m(a, b):
    from math import cos, radians, sqrt
    dlat = (b[0] - a[0]) * 111_320
    dlng = (b[1] - a[1]) * 111_320 * cos(radians((a[0] + b[0]) / 2))
    return sqrt(dlat * dlat + dlng * dlng)


def build_transport(cache: Path, refresh: bool, places: list, muni_of, stats: dict, net: dict):
    """Collect every transport feature, attribute municipalities, and compute access metrics.

    Mutates `places` (the legacy transit_m, transit_400m, nearest_stop) and `stats` (per-municipality transport and access fields), both through
    access.py, which the nightly refresh also runs. Returns (features, routes_fc, meta, res): `res` holds the per-place columns of access.py.
    """
    # scheduled stops and routes of every operator come from network.py (ATI, municipal feeds, OpenStreetMap routes)
    gtfs_stops = net["stops"]
    routes_fc = {"type": "FeatureCollection", "features": net["routes"]}
    gtfs_meta = {"operators_with_feed": sum(1 for o in net["operators"].values() if o["feed"]["status"] in ("current", "expiring", "expired")),
                 "routes": len(net["routes"]), "stops": len(gtfs_stops)}
    osm = load_osm(cache, refresh)
    faa = load_airports(cache, refresh)

    # FAA is the authoritative airport list; drop OSM aerodromes within 2 km of an FAA airport
    faa_pts = [(a["lat"], a["lng"]) for a in faa]
    osm = [o for o in osm if not (o["kind"] == "airport" and any(_dist_m((o["lat"], o["lng"]), f) < 2000 for f in faa_pts))]
    # OSM bus stops within 30 m of an official GTFS stop are the same stop: keep the GTFS record
    gtree = STRtree([Point(s["lng"], s["lat"]) for s in gtfs_stops]) if gtfs_stops else None
    kept = []
    # stations and terminals are mapped as several nodes (building, platform, entrance): fold those within 200 m of a
    # same-kind official or already-kept feature; ordinary stops use the 30 m rule
    HUB_FOLD_M = {"rail_station": 200, "ferry_terminal": 200, "bus_station": 100}
    for o in osm:
        if o["kind"] in ("bus_stop", "bus_station", "rail_station", "ferry_terminal") and gtree is not None:
            i = gtree.nearest(Point(o["lng"], o["lat"]))
            if i is not None and _dist_m((o["lat"], o["lng"]), (gtfs_stops[i]["lat"], gtfs_stops[i]["lng"])) < 30:
                continue
        if o["kind"] in HUB_FOLD_M:
            same = [f for f in gtfs_stops + kept if f["kind"] == o["kind"]]
            if any(_dist_m((o["lat"], o["lng"]), (f["lat"], f["lng"])) < HUB_FOLD_M[o["kind"]] for f in same):
                continue
        kept.append(o)
    features = gtfs_stops + kept + faa
    for f in features:
        f["municipality"] = muni_of(f["lat"], f["lng"])

    # transit access for tourism places (access.py): the legacy "any mapped stop" fields, the nearest stop with a current timetable, and the area shares
    as_of = date.fromisoformat(net["built"])
    import walknet
    res = access.compute(places, features, net["operators"], as_of, net=walknet.load())   # walking along mapped roads too (site/data/roads.bin)
    access.legacy_fields(places, res)

    # per-municipality: stop counts and access fields come from access.py (the nightly refresh recomputes them too); Uber is a listing, not computed
    uber = {n for n in UBER_LISTED}
    for name, s in stats.items():
        s["uber_listed"] = name in uber
    access.municipality_fields(stats, places, res, features, as_of)
    meta = {"gtfs": gtfs_meta, "osm_features": len(kept), "faa_airports": len(faa), "features": len(features),
            "kinds": dict(Counter(f["kind"] for f in features)), "walk_access_m": WALK_M,
            "places_near_transit": sum(1 for p in places if p.get("transit_400m") and p["type"] != "Places of Worship" and p["confidence"] >= 0.5), "uber_listed_municipalities": len(uber), "uber_checked": UBER_CHECKED,
            "sources": SOURCES}
    print(f"  transport features {len(features):,}; {meta['places_near_transit']:,} tourism places within {WALK_M} m of a stop")
    return features, routes_fc, meta, res
