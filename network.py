"""Transit network for the PR Data Observatory: every operator, every public schedule feed.

Sources (all public, all cached under cache/network/):
  ATI GTFS          Autoridad de Transporte Integrado: Tren Urbano, AMA / Metrobús / Metro Urbano buses, AcuaExpreso
                    ferries. https://docs.pr.gov/files/ATI/DATOS_ABIERTOS/GTFS/PRITA_GTFS.zip
  Municipal GTFS    Municipal bus and trolley systems that publish a GTFS feed, discovered from the open Transitland
                    Atlas registry of the National RTAP portal (rapid.nationalrtap.org). The registry is re-read on
                    every build, so a municipality that uploads a new feed appears on the next build.
  FTA NTD list      Every Puerto Rico agency that reports to the National Transit Database (via the Atlas copy of the
                    NTD GTFS-weblinks table): the checklist of systems that exist, whether or not they publish data.
  OpenStreetMap     Route relations (públicos, trolleys) that no agency publishes as GTFS. ODbL.
  Census 2020       Population by block (centroids) for service-coverage analysis. US Government work (no US copyright).

Real-time vehicle positions are NOT available: ATI lists its GTFS-RT feed as "en desarrollo". LIVE_SOURCES records
what was checked, so the site can say so plainly.
"""

import csv
import io
import json
import math
import re
import time
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

import trip_paths

UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
ATI_URL = "https://docs.pr.gov/files/ATI/DATOS_ABIERTOS/GTFS/PRITA_GTFS.zip"
ATLAS = "https://raw.githubusercontent.com/transitland/transitland-atlas/main"
RAPID_REGISTRY = f"{ATLAS}/feeds/nationalrtap.org.dmfr.json"
NTD_LIST = f"{ATLAS}/external-data-for-reference/ntd-gtfs-weblinks/2023-gtfs-weblinks.csv"
CENSUS_BLOCKS = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
WALK_M = 400
WALK_BOUND_M = 1_000   # a walking search goes this far from each stop (access.WALK_BOUND_M): past the 800 m of the far-from-service view
TRANSFER_M = 250

ROUTE_TYPES = {"0": "tram", "1": "rail", "2": "rail", "3": "bus", "4": "ferry", "5": "cable", "6": "gondola", "7": "funicular", "11": "bus", "12": "rail"}
ROUTE_LABEL = {"rail": "Tren Urbano", "bus": "Bus", "ferry": "Ferry", "tram": "Tram"}

SOURCES = {
    "ati_gtfs": {
        "name": "Autoridad de Transporte Integrado (ATI) — GTFS open data",
        "url": "https://www.ati.pr.gov/relaciones-comunidad?tab=DatosAbiertos",
        "license": "Open data published by ATI (Gobierno de Puerto Rico); provided without warranty",
        "credit": "Transit routes and stops: ATI GTFS (Tren Urbano, AMA/Metrobús, AcuaExpreso)",
    },
    "muni_gtfs": {
        "name": "Municipal transit GTFS feeds (National RTAP portal, rapid.nationalrtap.org)",
        "url": "https://rapid.nationalrtap.org/",
        "license": "Public GTFS feeds published by each municipality; no license stated in the feeds",
        "credit": "Municipal routes and stops: each municipality's public GTFS feed (National RTAP portal)",
    },
    "ntd": {
        "name": "FTA National Transit Database — Puerto Rico reporters (via Transitland Atlas)",
        "url": "https://github.com/transitland/transitland-atlas/tree/main/external-data-for-reference/ntd-gtfs-weblinks",
        "license": "US Government works (FTA); Transitland Atlas registry: CC BY 4.0",
        "credit": "Operator checklist: FTA National Transit Database",
    },
    "osm_routes": {
        "name": "OpenStreetMap — public transport route relations",
        "url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL",
        "credit": "Públicos and other routes © OpenStreetMap contributors",
    },
    "osm_roads": {
        "name": "OpenStreetMap — road network and place names (Geofabrik Puerto Rico extract)",
        "url": "https://download.geofabrik.de/north-america/us/puerto-rico.html",
        "license": "ODbL",
        "credit": "Roads, route snapping and place search © OpenStreetMap contributors",
    },
    "census_blocks": {
        "name": "US Census Bureau — 2020 Census blocks (population), TIGERweb",
        "url": CENSUS_BLOCKS,
        "license": "US Government work (no US copyright)",
        "credit": "Population by block: US Census Bureau (2020 Census)",
    },
}

# What was checked about real-time data, and what came back (the site shows this table).
LIVE_CHECKED = "2026-10-02"
LIVE_SOURCES = [
    {"id": "ati_gtfs_rt", "name": "ATI GTFS-Realtime (vehicle positions and arrival forecasts)", "status": "not published",
     "detail": "ATI's open data page lists GTFS-RT as \"en desarrollo\" (in development). No feed URL exists yet.",
     "url": "https://www.ati.pr.gov/relaciones-comunidad?tab=DatosAbiertos"},
    {"id": "ama_movil", "name": "AMA Móvil app (AMATrack)", "status": "app only",
     "detail": "The official AMA app shows bus positions, but there is no public data feed behind it.",
     "url": "https://play.google.com/store/apps/details?id=com.e3ama.amatrack_rider"},
    {"id": "ati_express", "name": "ATI express buses (T3, E10, E20, E30, E40, C22, C35, C36)", "status": "private feed",
     "detail": "The independent app transPRte says it shows live positions for these routes \"using the positions the operator publishes\". The feed is not public; access has to be requested from ATI.",
     "url": "https://apps.apple.com/us/app/transprte/id6776652469"},
    {"id": "municipal_rt", "name": "Municipal bus and trolley systems", "status": "none found",
     "detail": "No municipal GTFS-RT feed exists in the public registries. Schedules are public for the systems listed under Operators."},
    {"id": "ferry", "name": "AcuaExpreso ferries (Hornblower)", "status": "app only",
     "detail": "ATI points riders to the City Experiences app for ferry tracking and service alerts. No public feed.",
     "url": "https://www.ati.pr.gov/transportacion-urbana"},
    {"id": "adsb", "name": "Aircraft near Puerto Rico (ADS-B)", "status": "available, needs a relay",
     "detail": "Community ADS-B networks publish free live positions, but their servers do not allow calls from a web page, so a small relay (a Cloudflare Worker or Azure Function) is needed."},
]



PERSONAL_LINK = re.compile(r"-my\.sharepoint\.com/.*/personal/|onedrive\.live\.com|1drv\.ms|drive\.google\.com/.*/d/", re.I)



SIMPLIFY_DEG = 0.00003   # about 3 m: every route line is simplified to this before it is published (transit_routes.geojson stays under its 1 MB budget)


def simplify_line(pts):
    """A route line as published: Douglas-Peucker to about 3 m, coordinates to 5 decimals (about 1 m). Feed shapes, OpenStreetMap routes and lines
    snapped to the roads all go through it (until 2026-11-18 only the snapped ones did, and the file passed 1 MB)."""
    pts = [(float(x), float(y)) for x, y in pts]
    if len(pts) < 3:
        return [[round(x, 5), round(y, 5)] for x, y in pts]
    return [[round(x, 5), round(y, 5)] for x, y in LineString(pts).simplify(SIMPLIFY_DEG, preserve_topology=False).coords]

def public_url(u):
    """A feed link is published in operators.json. A link into a person's own cloud storage names that person in its address,
    so it is kept out of the published file (the build still downloads from it)."""
    return None if u and PERSONAL_LINK.search(u) else u

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower().strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", norm(s)).strip("_")


def _secs(hms):
    try:
        h, m, s = (hms or "").strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return None


def _dist_m(a, b):
    from math import cos, radians, sqrt
    dlat = (b[0] - a[0]) * 111_320
    dlng = (b[1] - a[1]) * 111_320 * cos(radians((a[0] + b[0]) / 2))
    return sqrt(dlat * dlat + dlng * dlng)


# ── Registry: which operators exist, which publish a feed ────────────────────

def _get(url, **kw):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=120, **kw)
    r.raise_for_status()
    return r


def muni_key(agency_name, muni_names):
    """Map an agency name such as 'Municipality of Cabo Rojo' or 'Autonomous Municipality of Ponce' to a municipality."""
    n = norm(re.sub(r"^(autonomous\s+)?(municipality|municipio|city|town)\s+(autonomo\s+)?(of|de)\s+", "", norm(agency_name)))
    return muni_names.get(n)


def discover(cache: Path, refresh: bool, muni_names: dict):
    """Returns (operators, feeds): operators from the NTD checklist, feed URLs from the Atlas registry."""
    reg = cache / "registry.json"
    if reg.exists() and not refresh:
        d = json.loads(reg.read_text(encoding="utf-8"))
        return d["operators"], d["feeds"]
    print("  reading the NTD checklist and the Atlas registry")
    try:
        rows = list(csv.DictReader(io.StringIO(_get(NTD_LIST).text)))
        registry_json = _get(RAPID_REGISTRY).json()
    except Exception as ex:
        if reg.exists():
            print(f"    registry unavailable ({type(ex).__name__}); using the cached copy")
            d = json.loads(reg.read_text(encoding="utf-8"))
            return d["operators"], d["feeds"]
        raise
    operators = {}
    for r in rows:
        name = r["Agency Name"].strip()
        m = muni_key(name, muni_names)
        if m == "San Juan" and r["NTD ID"] != "40112":
            continue   # another "City of San Juan" (Texas) shares the name
        low = name.lower()
        if m:
            kind = "municipal"
        elif "metropolitan bus authority" in low:
            kind = "ama"
        elif "highway and transportation authority" in low or "público" in low or "publico" in low:
            kind = "publico"
        elif "maritime transport" in low:
            kind = "ferry"
        else:
            continue
        key = slug(m or name)
        operators.setdefault(key, {"id": key, "name": name, "type": kind, "municipality": m, "ntd_id": int(r["NTD ID"]) if r["NTD ID"].isdigit() else None,
                                   "ntd_weblink": r.get("Weblink") or None})
    feeds = {}
    for f in registry_json.get("feeds", []):
        ops = [o.get("name", "") for o in f.get("operators", [])]
        name = next((o for o in ops if o), "")
        m = muni_key(name, muni_names) if re.search(r"municipal|municipio|city of san juan", name, re.I) else None
        url = (f.get("urls") or {}).get("static_current")
        if m and url and ("~pr~us" in f["id"] or f["id"] in ("f-municipality~of~bayamon", "f-municipality~of~vega~baja")):
            feeds[slug(m)] = {"url": url.replace("http://", "https://"), "agency": name}
    reg.write_text(json.dumps({"operators": operators, "feeds": feeds}, ensure_ascii=False, indent=1), encoding="utf-8")
    return operators, feeds


# ── GTFS parsing ─────────────────────────────────────────────────────────────

def parse_gtfs(raw: bytes, op_id: str, op_name: str, mode_default="bus"):
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = {n.lower().split("/")[-1]: n for n in z.namelist()}

    def rd(name):
        n = names.get(name)
        if not n:
            return []
        return list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding="utf-8-sig", errors="replace")))

    feed = (rd("feed_info.txt") or [{}])[0]
    agencies = rd("agency.txt")
    routes = {r["route_id"]: r for r in rd("routes.txt") if r.get("route_id")}
    trips = {t["trip_id"]: t for t in rd("trips.txt") if t.get("trip_id")}
    cal = {c["service_id"]: c for c in rd("calendar.txt") if c.get("service_id")}
    starts = [c["start_date"] for c in cal.values() if c.get("start_date")]
    ends = [c["end_date"] for c in cal.values() if c.get("end_date")]
    if not cal:   # calendar_dates only: every listed service counts as running
        for c in rd("calendar_dates.txt"):
            if c.get("service_id"):
                cal.setdefault(c["service_id"], {"wednesday": "1", "saturday": "1", "sunday": "1"})

    # a "typical weekday" is Wednesday (or the first weekday the feed actually serves), so services split by day are not double counted
    ref = next((d for d in ("wednesday", "tuesday", "thursday", "monday", "friday") if any(c.get(d) == "1" for c in cal.values())), "wednesday")

    def days(sid):
        c = cal.get(sid)
        if c is None:
            return {"wk"}   # trip names a service that is not defined: assume weekday
        out = set()
        if c.get(ref) == "1":
            out.add("wk")
        if c.get("saturday") == "1":
            out.add("sa")
        if c.get("sunday") == "1":
            out.add("su")
        return out

    stops_raw = {}
    for s in rd("stops.txt"):
        try:
            stops_raw[s["stop_id"]] = s
        except KeyError:
            continue
    stop_xy = {}
    flipped = 0
    for sid, s in stops_raw.items():
        try:
            lng, lat = float(s["stop_lon"]), float(s["stop_lat"])
        except (TypeError, ValueError, KeyError):
            continue
        if 65.0 <= lng <= 68.0 and 17.5 <= lat <= 18.8:   # Puerto Rico is west of Greenwich: the minus sign was dropped (Jayuya's feed)
            lng, flipped = -lng, flipped + 1
        if not (-68.0 <= lng <= -65.0 and 17.5 <= lat <= 18.8):   # not in Puerto Rico at all (blank-ish or garbage rows)
            continue
        stop_xy[sid] = (round(lng, 5), round(lat, 5))
    if flipped:
        print(f"    {flipped} stop longitudes had no minus sign; corrected")

    seq = defaultdict(list)   # trip -> [(sequence, seconds, stop_id)]
    stop_routes, stop_trips = defaultdict(set), Counter()
    stop_sat, stop_sun = Counter(), Counter()   # calls on a Saturday and on a Sunday, from the calendar flags (as the route counts below)
    trip_days = {tid: days(t.get("service_id")) for tid, t in trips.items()}
    for st in rd("stop_times.txt"):
        t = trips.get(st.get("trip_id"))
        sid = st.get("stop_id")
        if not t or sid not in stop_xy:
            continue
        sec = _secs(st.get("departure_time") or st.get("arrival_time"))
        try:
            n = int(st.get("stop_sequence") or 0)
        except ValueError:
            n = 0
        seq[st["trip_id"]].append((n, sec, sid))
        stop_routes[sid].add(t.get("route_id"))
        d = trip_days[st["trip_id"]]
        if "wk" in d:
            stop_trips[sid] += 1
        if "sa" in d:
            stop_sat[sid] += 1
        if "su" in d:
            stop_sun[sid] += 1
    for pts in seq.values():
        pts.sort(key=lambda p: p[0])

    # routes
    route_trips = defaultdict(lambda: Counter())   # route -> day -> n
    first_last = defaultdict(list)
    route_shapes = defaultdict(Counter)
    route_stopseqs = defaultdict(lambda: defaultdict(list))   # route -> direction -> [(n_stops, trip_id)]
    for tid, t in trips.items():
        for d in days(t.get("service_id")):
            route_trips[t.get("route_id")][d] += 1
        if t.get("shape_id"):
            route_shapes[t.get("route_id")][t["shape_id"]] += 1
        pts = seq.get(tid)
        if pts:
            route_stopseqs[t.get("route_id")][t.get("direction_id") or "0"].append((len(pts), tid))
            if "wk" in days(t.get("service_id")) and pts[0][1] is not None:
                first_last[t.get("route_id")].append(pts[0][1])
    shape_pts = defaultdict(list)
    for p in rd("shapes.txt"):
        try:
            shape_pts[p["shape_id"]].append((int(p.get("shape_pt_sequence") or 0), float(p["shape_pt_lon"]), float(p["shape_pt_lat"])))
        except (TypeError, ValueError, KeyError):
            pass

    features = []
    for rid, r in routes.items():
        mode = ROUTE_TYPES.get(r.get("route_type"), mode_default)
        lines, geom_kind, seqs = [], None, None
        for sid, _ in route_shapes.get(rid, Counter()).most_common(2):
            pts = sorted(shape_pts.get(sid, []))
            if len(pts) > 1:
                lines.append(simplify_line([(x, y) for _, x, y in pts]))
        if lines:
            geom_kind = "shape"
        else:   # no shape in the feed: join the stops of the longest trip in each direction (an approximate alignment)
            seqs = []
            for direction, cands in sorted(route_stopseqs.get(rid, {}).items())[:2]:
                _, tid = max(cands)
                line = [list(stop_xy[sid]) for _, _, sid in seq[tid]]
                names_ = [(stops_raw[sid].get("stop_name") or "").strip() for _, _, sid in seq[tid]]
                keep = [i for i in range(len(line)) if i == 0 or line[i] != line[i - 1]]
                dedup = [line[i] for i in keep]
                if len(dedup) > 1:
                    lines.append(dedup)
                    seqs.append([(names_[i], line[i][0], line[i][1]) for i in keep])
            if lines:
                geom_kind = "stops"
        if not lines:
            continue
        rt = route_trips.get(rid, Counter())
        starts_t = sorted(first_last.get(rid, []))
        features.append({
            "type": "Feature",
            "properties": {
                "operator": op_id, "operator_name": op_name, "route_id": rid,
                "short_name": r.get("route_short_name") or "", "long_name": r.get("route_long_name") or "",
                "mode": mode, "label": ROUTE_LABEL.get(mode, mode), "color": ("#" + r["route_color"]) if r.get("route_color") and re.fullmatch(r"[0-9A-Fa-f]{6}", r["route_color"]) else None,
                "trips_weekday": rt.get("wk", 0), "trips_saturday": rt.get("sa", 0), "trips_sunday": rt.get("su", 0),
                "first": starts_t[0] if starts_t else None, "last": starts_t[-1] if starts_t else None,
                "geometry_source": geom_kind,
            },
            "geometry": {"type": "MultiLineString", "coordinates": lines},
            "_seq": seqs if geom_kind == "stops" else None,
        })

    # stops (boarding points only)
    route_mode = {rid: ROUTE_TYPES.get(r.get("route_type"), mode_default) for rid, r in routes.items()}
    stops = []
    for sid, s in stops_raw.items():
        if s.get("location_type") not in ("", "0", None) or sid not in stop_xy:
            continue
        rids = sorted(r for r in stop_routes.get(sid, []) if r in routes)
        modes = sorted({route_mode[r] for r in rids})
        nm = (s.get("stop_name") or "").strip()
        kind = "rail_station" if "rail" in modes else "ferry_terminal" if "ferry" in modes else "bus_station" if re.match(r"^(terminal|estaci[oó]n)\b", nm, re.I) else "transit_stop"
        lng, lat = stop_xy[sid]
        stops.append({
            "id": f"gtfs:{op_id}:{sid}", "kind": kind, "name": nm, "lat": lat, "lng": lng, "source": "ati_gtfs" if op_id == "ati" else "muni_gtfs",
            "operator": op_id, "operator_name": op_name, "modes": modes,
            "routes": [routes[r].get("route_short_name") or routes[r].get("route_long_name") or r for r in rids],
            "trips_weekday": stop_trips.get(sid, 0), "wheelchair": s.get("wheelchair_boarding") == "1",
        })
        # weekend calls, left out when there are none: a missing field means no such service in the feed
        for key, value in (("calls_sat", stop_sat.get(sid, 0)), ("calls_sun", stop_sun.get(sid, 0))):
            if value:
                stops[-1][key] = value

    # timed paths for the weekday replay
    out_trips = {"wk": [], "sa": [], "su": []}
    for tid, pts in seq.items():
        t = trips[tid]
        timed = [[*stop_xy[sid], sec] for _, sec, sid in pts if sec is not None]
        if len(timed) < 2:
            continue
        r = routes.get(t.get("route_id"), {})
        rec = {"r": r.get("route_short_name") or r.get("route_long_name") or "", "m": route_mode.get(t.get("route_id"), mode_default), "o": op_id, "p": timed,
               "_sid": [f"gtfs:{op_id}:{sid}" for _, sec, sid in pts if sec is not None]}   # the stop ids, same order as p: trip_paths keeps them per stop pattern
        for d in days(t.get("service_id")):
            out_trips[d].append(dict(rec))   # a copy per day: trip_paths.follow_routes rewrites each trip in place, once per day

    meta = {
        "agency": (agencies[0].get("agency_name") if agencies else None) or op_name,
        "version": feed.get("feed_version") or None,
        "start": _iso(min(starts)) if starts else _iso(feed.get("feed_start_date")),
        "end": _iso(max(ends)) if ends else _iso(feed.get("feed_end_date")),
        "routes": len(features), "stops": len(stops), "trips_weekday": len(out_trips["wk"]),
        "has_shapes": any(f["properties"]["geometry_source"] == "shape" for f in features),
        "weekend_service": any(f["properties"]["trips_saturday"] or f["properties"]["trips_sunday"] for f in features),
    }
    return stops, features, out_trips, meta


def _iso(d):
    d = (d or "").strip()
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if re.fullmatch(r"\d{8}", d) else None


def feed_status(meta, today: date):
    if not meta:
        return "none"
    end = meta.get("end")
    if not end:
        return "unknown"
    try:
        e = date.fromisoformat(end)
    except ValueError:
        return "unknown"
    if e < today:
        return "expired"
    return "expiring" if (e - today).days <= 60 else "current"


# ── OpenStreetMap routes (públicos, trolleys) ────────────────────────────────

def load_osm_routes(cache: Path, refresh: bool):
    print("  OpenStreetMap route relations (públicos, trolleys and other routes not in any GTFS)")
    path = cache / "osm_routes.json"
    if path.exists() and not refresh:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        q = """[out:json][timeout:180];
area["ISO3166-1"="PR"]->.pr;
relation["type"="route"]["route"~"^(bus|trolleybus|share_taxi|minibus)$"](area.pr);
out geom;"""
        data = None
        for ep in OVERPASS:
            try:
                r = requests.post(ep, data={"data": q}, headers={"User-Agent": UA}, timeout=300)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as ex:
                print(f"    {ep}: {type(ex).__name__}; trying next mirror")
                time.sleep(5)
        if data is None:
            if not path.exists():
                return []
            print("    Overpass unavailable; using the cached copy")
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    feats = []
    for el in data.get("elements", []):
        t = el.get("tags") or {}
        net = (t.get("network") or t.get("operator") or "").strip()
        # AMA / ATI routes come from the official GTFS; Bayamón from its own feed
        if re.search(r"\bAMA\b|^ATI$|autoridad de transporte|bayam", net, re.I):
            continue
        lines = []
        for m in el.get("members", []):
            g = m.get("geometry")
            if m.get("type") == "way" and g and len(g) > 1 and m.get("role", "") in ("", "route", "forward", "backward"):
                lines.append(simplify_line([(p["lon"], p["lat"]) for p in g]))
        if not lines:
            continue
        feats.append({
            "type": "Feature",
            "properties": {
                "operator": "osm", "operator_name": "Públicos and other routes (OpenStreetMap)", "route_id": f"r{el['id']}",
                "short_name": t.get("ref") or "", "long_name": t.get("name") or t.get("description") or net or "Unnamed route",
                "mode": "bus", "label": "Público" if t.get("route") == "share_taxi" or "público" in net.lower() else "Bus", "color": None,
                "trips_weekday": 0, "trips_saturday": 0, "trips_sunday": 0, "first": None, "last": None, "geometry_source": "osm",
                "network": net or None,
            },
            "geometry": {"type": "MultiLineString", "coordinates": lines},
        })
    print(f"    {len(feats)} routes")
    return feats


# ── Population blocks ────────────────────────────────────────────────────────

BLOCK_FIELDS = ["geoid", "pop", "hu", "land_m2", "lon", "lat"]


def load_block_table(cache: Path, refresh: bool):
    """Every 2020 census block of Puerto Rico (41,987, 36,570 with residents), with its 15-digit id.

    {"fields": BLOCK_FIELDS, "rows": [[geoid, residents, housing units, land area in m2, internal-point lon, lat], ...]}, in the order
    the Census service lists them. Housing units are exact (the Census Bureau holds them invariant); residents are noise-injected
    at this size. The transit coverage (load_blocks) and the geography crosswalk (geo.py) both read this one table."""
    print("  Census 2020 blocks (id, residents, housing units)")
    path = cache / "census_blocks_ids.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    rows, offset = [], 0
    while True:
        for attempt in range(4):
            try:
                r = requests.get(f"{CENSUS_BLOCKS}/query", params={"where": "STATE='72'", "outFields": "GEOID,POP100,HU100,AREALAND,INTPTLAT,INTPTLON", "returnGeometry": "false", "f": "json", "resultOffset": offset, "resultRecordCount": 20000, "orderByFields": "OBJECTID"}, headers={"User-Agent": UA}, timeout=300)
                r.raise_for_status()
                feats = r.json()["features"]
                break
            except (requests.RequestException, KeyError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        for f in feats:
            a = f["attributes"]
            rows.append([str(a["GEOID"]), int(a.get("POP100") or 0), int(a.get("HU100") or 0), int(a.get("AREALAND") or 0), float(a["INTPTLON"]), float(a["INTPTLAT"])])
        if len(feats) < 20000:
            break
        offset += 20000
    table = {"fields": BLOCK_FIELDS, "rows": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table, separators=(",", ":")), encoding="utf-8")
    print(f"    {len(rows):,} blocks, {sum(1 for r in rows if r[1] > 0):,} with residents, {sum(r[1] for r in rows):,} people, {sum(r[2] for r in rows):,} housing units")
    return table


def load_blocks(cache: Path, refresh: bool):
    """[(lon, lat, population, county_fips)] for every 2020 census block with residents (read from load_block_table)."""
    out = [[round(lon, 4), round(lat, 4), pop, geoid[:5]] for geoid, pop, hu, land, lon, lat in load_block_table(cache, refresh)["rows"] if pop > 0]
    print(f"    {len(out):,} blocks with residents, {sum(b[2] for b in out):,} people")
    return out


# ── Snapping routes to roads ─────────────────────────────────────────────────

def load_roads(data_dir: Path):
    """The road graph from site/data/roads.bin, or None when it has not been built (routes then keep their stop-to-stop lines)."""
    try:
        import roads
        return roads.Roads(data_dir / "roads.bin")
    except FileNotFoundError:
        print("  site/data/roads.bin not found: run `python roads.py` to snap routes to roads")
        return None


def previous_routes(data_dir: Path):
    """{(operator, route_id): feature} from the published routes, so unchanged routes keep their snapped geometry."""
    try:
        fc = json.loads((data_dir / "transit_routes.geojson").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return {(f["properties"].get("operator"), f["properties"].get("route_id")): f for f in fc.get("features", [])}


def _straight_m(a, b):
    return _dist_m((a[1], a[0]), (b[1], b[0]))


def order_quality(seq):
    """Is the stop order geographic? Returns (ok, ratio, alphabetical).

    ratio = length of the path through the stops in the listed order / length of a nearest-neighbor tour. Real routes sit
    near 1-2; a feed that lists stops alphabetically (Patillas) sits at 3-5."""
    pts = [(lng, lat) for _, lng, lat in seq]
    if len(pts) < 4:
        return True, 1.0, False
    listed = sum(_straight_m(a, b) for a, b in zip(pts, pts[1:]))
    left, cur, tour = pts[1:], pts[0], 0.0
    while left:
        j = min(range(len(left)), key=lambda i: _straight_m(cur, left[i]))
        tour += _straight_m(cur, left[j])
        cur = left.pop(j)
    ratio = listed / max(tour, 1.0)
    names = [n.lower() for n, _, _ in seq]
    alpha = len(names) >= 5 and all(names[i] <= names[i + 1] for i in range(len(names) - 1))
    return not (ratio > 2.5 or alpha), round(ratio, 2), alpha


class RoadSnapper:
    """Routes between consecutive stops along the road graph, with a cache so rebuilds are quick."""

    def __init__(self, roads, cache_path=None):
        self.roads = roads
        self.cache_path = cache_path
        self.cache = {}
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                self.cache = {}
        self.dirty = False

    def save(self):
        if self.cache_path and self.dirty:
            self.cache_path.write_text(json.dumps(self.cache, separators=(",", ":")), encoding="utf-8")

    def pair(self, a, b):
        """Road path between two [lng, lat] points, or None when no sensible path exists."""
        key = f"{a[0]:.5f},{a[1]:.5f}|{b[0]:.5f},{b[1]:.5f}"
        if key in self.cache:
            return self.cache[key]
        straight = _straight_m(a, b)
        res = None
        if straight < 25:
            res = [list(a), list(b)]
        else:
            sa, sb = self.roads.snap(a[0], a[1], 500), self.roads.snap(b[0], b[1], 500)   # a stop on a lane OpenStreetMap has not mapped can sit 400 m from the nearest road
            if sa and sb:
                r = self.roads.route(sa, sb)
                if r and r[2] <= 3 * straight + 400:
                    res = [[round(x, 5), round(y, 5)] for x, y in r[1]]
        self.cache[key] = res
        self.dirty = True
        return res

    def path(self, pts):
        """Snap an ordered list of [lng, lat]; returns (line, share of legs that follow a road)."""
        out, ok = [], 0
        for a, b in zip(pts, pts[1:]):
            seg = self.pair(a, b)
            if seg:
                ok += 1
            else:
                seg = [list(a), list(b)]
            out += seg if not out else (seg[1:] if seg[0] == out[-1] else seg)
        return out, ok / max(1, len(pts) - 1)

    def infer_order(self, seq):
        """For feeds whose stop order is not geographic: a plausible loop from the first stop, by road travel distance."""
        uniq, seen = [], set()
        for n, lng, lat in seq:
            k = (round(lng, 4), round(lat, 4))
            if k not in seen:
                seen.add(k)
                uniq.append((n, [lng, lat]))
        if len(uniq) > 45:
            return None
        start = next((i for i, (n, _) in enumerate(uniq) if re.match(r"(terminal|estaci|plaza|pueblo|casco|alcald)", n, re.I)), 0)
        n = len(uniq)
        T = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    r = self.pair(uniq[i][1], uniq[j][1])
                    T[i][j] = sum(_straight_m(a, b) for a, b in zip(r, r[1:])) if r else 3 * _straight_m(uniq[i][1], uniq[j][1]) + 500
        order, left = [start], set(range(n)) - {start}
        while left:
            cur = order[-1]
            j = min(left, key=lambda k: T[cur][k])
            order.append(j)
            left.remove(j)
        improved = True
        while improved:   # 2-opt on the open path
            improved = False
            for i in range(1, n - 1):
                for j in range(i + 1, n):
                    a, b, c = order[i - 1], order[i], order[j]
                    d = order[j + 1] if j + 1 < n else None
                    old = T[a][b] + (T[c][d] if d is not None else 0)
                    new = T[a][c] + (T[b][d] if d is not None else 0)
                    if new + 1e-6 < old:
                        order[i:j + 1] = reversed(order[i:j + 1])
                        improved = True
        order.append(start)   # back to the terminal
        return [uniq[i][1] for i in order]


def snap_routes(routes, roads, previous=None, cache_path=None):
    """Replace stop-to-stop straight lines by road-following lines. Routes with a published shape are left alone.

    previous: {(operator, route_id): feature} from the last published build; a route whose stops did not change keeps its geometry.
    Returns the set of (operator, route label) whose stop order is not geographic, so the timetable replay can leave them out."""
    import hashlib

    from shapely.geometry import LineString
    previous = previous or {}
    snapper = RoadSnapper(roads, cache_path)
    unreliable, done, reused = set(), 0, 0
    for f in routes:
        seqs = f.pop("_seq", None)
        p = f["properties"]
        if not seqs:
            continue
        label = (p["operator"], p["short_name"] or p["long_name"])
        sig = hashlib.md5((json.dumps(seqs, separators=(",", ":")) + "|snap2").encode()).hexdigest()[:12]   # snap2 = the method version: bump it to re-snap every route
        old = previous.get((p["operator"], p["route_id"]))
        if old and old["properties"].get("sig") == sig and old["properties"].get("geometry_source") in ("roads", "roads_inferred"):
            f["geometry"], p["geometry_source"], p["sig"] = old["geometry"], old["properties"]["geometry_source"], sig
            if old["properties"].get("order_note"):
                p["order_note"] = old["properties"]["order_note"]
                unreliable.add(label)
            reused += 1
            continue
        lines, kinds, shares = [], set(), []
        for seq in seqs:
            ok, ratio, alpha = order_quality(seq)
            if ok:
                line, share = snapper.path([[lng, lat] for _, lng, lat in seq])
                kinds.add("roads")
            else:
                order = snapper.infer_order(seq)
                p["order_note"] = "The feed lists this route's stops " + ("alphabetically" if alpha else "out of travel order") + f" (zig-zag ratio {ratio}), so the order of visit is inferred and its times are not usable."
                unreliable.add(label)
                if not order:
                    line, share = [[lng, lat] for _, lng, lat in seq], 0.0
                    kinds.add("stops")
                else:
                    line, share = snapper.path(order)
                    kinds.add("roads_inferred")
            lines.append(line)
            shares.append(share)
        done += 1
        if kinds == {"stops"} or (shares and min(shares) < 0.6):
            p["geometry_source"] = "stops"   # too little of the line could be snapped: keep the straight stop-to-stop line
            continue
        simple = [simplify_line(ln) for ln in lines]
        f["geometry"] = {"type": "MultiLineString", "coordinates": simple}
        p["geometry_source"] = "roads_inferred" if "roads_inferred" in kinds else "roads"
        p["sig"] = sig
    snapper.save()
    print(f"  snapped {done} routes to the road network ({reused} reused from the last build); {len({k[0] for k in unreliable})} operators have a feed with a non-geographic stop order")
    return unreliable


# ── Assembly ─────────────────────────────────────────────────────────────────

def build_network(cache: Path, refresh: bool, muni_names: dict, today: date = None, roads=None, previous=None):
    """Download and normalize every feed. Returns a dict with operators, stops, routes_fc, trips, blocks."""
    today = today or date.today()
    gcache = cache / "network"
    gcache.mkdir(exist_ok=True)
    print("Transit network")
    registry_ops, feeds = discover(gcache, refresh, muni_names)

    feed_defs = {"ati": {"url": ATI_URL, "agency": "Autoridad de Transporte Integrado"}}
    feed_defs.update(feeds)
    operators, all_stops, all_routes = {}, [], []
    all_trips = {"wk": [], "sa": [], "su": []}
    for key, fd in feed_defs.items():
        path = gcache / f"{key}.zip"
        status_http = None
        if refresh or not path.exists():
            try:
                r = _get(fd["url"])
                path.write_bytes(r.content)
                status_http = r.status_code
            except Exception as ex:
                print(f"  {key}: download failed ({type(ex).__name__}); {'using the cached copy' if path.exists() else 'skipped'}")
        if not path.exists():
            continue
        base = registry_ops.get(key, {})
        name = "Autoridad de Transporte Integrado (ATI)" if key == "ati" else (base.get("name") or fd["agency"])
        try:
            stops, feats, trips, meta = parse_gtfs(path.read_bytes(), key, name)
        except Exception as ex:
            print(f"  {key}: could not parse the feed ({type(ex).__name__}: {ex})")
            operators[key] = {"id": key, "name": name, "type": base.get("type", "municipal"), "municipality": base.get("municipality"), "ntd_id": base.get("ntd_id"),
                              "feed": {"status": "broken", "url": public_url(fd["url"])}}
            continue
        modes = sorted({f["properties"]["mode"] for f in feats})
        operators[key] = {
            "id": key, "name": name, "short": ("ATI" if key == "ati" else (base.get("municipality") or name)),
            "type": "regional" if key == "ati" else base.get("type", "municipal"), "municipality": base.get("municipality"), "ntd_id": base.get("ntd_id"),
            "modes": modes, "routes": meta["routes"], "stops": meta["stops"], "trips_weekday": meta["trips_weekday"],
            "feed": {"status": feed_status(meta, today), "url": public_url(fd["url"]), "agency": meta["agency"], "version": meta["version"], "start": meta["start"], "end": meta["end"],
                     "has_shapes": meta["has_shapes"], "weekend_service": meta["weekend_service"]},
        }
        if meta["end"]:   # the stop carries its feed's end date: a popup can say whether the timetable still covers today
            for st in stops:
                st["feed_end"] = meta["end"]
        all_stops += stops
        all_routes += feats
        for d in all_trips:
            all_trips[d] += trips[d]
        print(f"  {key:22} {meta['routes']:3} routes {meta['stops']:4} stops {meta['trips_weekday']:4} weekday trips  feed {meta['start']}..{meta['end']}  [{operators[key]['feed']['status']}]")

    if roads is not None:
        unreliable = snap_routes(all_routes, roads, previous, gcache / "road_pairs_v2.json")   # v2: snap radius 500 m
        for key, o in operators.items():
            n_bad = sum(1 for f in all_routes if f["properties"]["operator"] == key and f["properties"].get("order_note"))
            if n_bad:
                o["feed"]["order_issue"] = n_bad
        if unreliable:   # the times of these routes are not usable, so they stay out of the timetable replay
            for d in all_trips:
                all_trips[d] = [t for t in all_trips[d] if (t["o"], t["r"]) not in unreliable]
    else:
        for f in all_routes:
            f.pop("_seq", None)
    # the replay moves each vehicle along its route's line (the shape, or the roads snapped above), not in straight lines between stops
    trip_paths_by_day = trip_paths.follow_routes(all_routes, all_trips)

    osm_feats = load_osm_routes(gcache, refresh)
    if osm_feats:
        all_routes += osm_feats
        operators["osm"] = {"id": "osm", "name": "Públicos and other routes (OpenStreetMap)", "short": "OpenStreetMap", "type": "community", "municipality": None, "ntd_id": None,
                            "modes": ["bus"], "routes": len(osm_feats), "stops": 0, "trips_weekday": 0, "feed": {"status": "community", "url": "https://www.openstreetmap.org/", "has_shapes": True}}

    # operators that exist (NTD) but publish no feed of their own
    for key, base in registry_ops.items():
        if key in operators:
            continue
        in_ati = base["type"] in ("ama", "ferry")   # AMA buses and the AcuaExpreso ferries are inside the ATI feed
        operators[key] = {"id": key, "name": base["name"], "short": base.get("municipality") or ("AMA" if base["type"] == "ama" else base["name"]), "type": base["type"], "municipality": base.get("municipality"), "ntd_id": base.get("ntd_id"),
                          "modes": [], "routes": 0, "stops": 0, "trips_weekday": 0, "feed": {"status": "in_ati" if in_ati else "none", "url": public_url(base.get("ntd_weblink"))}}

    status = Counter(o["feed"]["status"] for o in operators.values())
    print(f"  {len(operators)} operators: {dict(status)}; {len(all_routes)} routes, {len(all_stops):,} stops, {len(all_trips["wk"]):,} weekday trips, {len(all_trips["sa"]):,} Saturday, {len(all_trips["su"]):,} Sunday")
    return {"operators": operators, "stops": all_stops, "routes": all_routes, "trips": all_trips, "trip_paths": trip_paths_by_day, "built": today.isoformat()}


def coverage(blocks, stops, muni_by_fips, inactive_ops=frozenset(), net=None):
    """Residents within WALK_M of a scheduled stop, overall and per operator group, per municipality.

    Each block becomes [lon, lat, residents, meters to the nearest scheduled stop (straight line, capped at 9,999)]. With a walking network
    (walknet.load()), a 5th value is the meters walked along mapped roads to the nearest scheduled stop (9,999 past WALK_BOUND_M), and each
    municipality gets walk_served (any scheduled stop) and walk_served_active (a stop of a feed that has not expired) within a 400 m walk.
    A block with no walkable road within 150 m keeps its straight-line values; a stop on no walkable road counts at its straight line
    (walknet.walk_to_stops); a walk is never shorter than the straight line. A walk is rounded up to whole meters, as access.py rounds tw_m, so the
    residents within a 400 m walk of an active stop here equal exposure.py's walk_cur (the straight-line distance stays cut, as it always was).
    """
    print("  service coverage (residents within 400 m of a scheduled stop)")
    pts = [Point(s["lng"], s["lat"]) for s in stops]
    tree = STRtree(pts)
    ati_idx = {i for i, s in enumerate(stops) if s["operator"] == "ati"}
    active_idx = {i for i, s in enumerate(stops) if s["operator"] not in inactive_ops}
    per = defaultdict(lambda: {"pop": 0, "served": 0, "served_active": 0, "served_ati": 0, "served_muni": 0, "served_both": 0})
    walks = ok = None
    if net is not None and stops:
        import walknet
        walks, ok, _ = walknet.walk_to_stops(net, stops, [{"lat": lat, "lng": lon} for lon, lat, pop, fips in blocks], WALK_BOUND_M)
    out_blocks = []
    for k, (lon, lat, pop, fips) in enumerate(blocks):
        p = Point(lon, lat)
        i = tree.nearest(p)
        d = int(_dist_m((lat, lon), (stops[i]["lat"], stops[i]["lng"])))
        w = w_active = None
        if walks is not None:
            if ok[k]:
                near = walks[k]
                w = max(math.ceil(min(near.values())), d) if near else 9999
                act = [v for j, v in near.items() if j in active_idx]
                w_active = max(math.ceil(min(act)), d) if act else 9999
        out_blocks.append([lon, lat, pop, min(d, 9999)] + ([] if walks is None else [min(w if w is not None else d, 9999)]))
        m = muni_by_fips.get(fips)
        if not m:
            continue
        a = per[m]
        a["pop"] += pop
        if d <= WALK_M:
            a["served"] += pop
        # per group: query stops within WALK_M
        near = tree.query(p.buffer(WALK_M / 111_320 * 1.05))
        has_ati = has_muni = has_active = False
        for j in near:
            if _dist_m((lat, lon), (stops[j]["lat"], stops[j]["lng"])) <= WALK_M:
                if stops[j]["operator"] not in inactive_ops:
                    has_active = True
                if j in ati_idx:
                    has_ati = True
                else:
                    has_muni = True
        if has_active:
            a["served_active"] += pop
        if has_ati:
            a["served_ati"] += pop
        if has_muni:
            a["served_muni"] += pop
        if has_ati and has_muni:
            a["served_both"] += pop
        if walks is not None:
            if w is None:   # no walkable road near the block: the straight-line tests stand
                w_hit, wa_hit = d <= WALK_M, has_active
            else:
                w_hit, wa_hit = w <= WALK_M, w_active <= WALK_M
            a["walk_served"] = a.get("walk_served", 0) + (pop if w_hit else 0)
            a["walk_served_active"] = a.get("walk_served_active", 0) + (pop if wa_hit else 0)
    for m, a in per.items():
        a["served_pct"] = round(a["served"] / a["pop"] * 100, 1) if a["pop"] else None
        a["served_active_pct"] = round(a["served_active"] / a["pop"] * 100, 1) if a["pop"] else None
        if "walk_served" in a:
            a["walk_served_pct"] = round(a["walk_served"] / a["pop"] * 100, 1) if a["pop"] else None
            a["walk_served_active_pct"] = round(a["walk_served_active"] / a["pop"] * 100, 1) if a["pop"] else None
    total = sum(a["pop"] for a in per.values())
    served = sum(a["served"] for a in per.values())
    print(f"    {served:,} of {total:,} residents ({served / total * 100:.1f}%) within {WALK_M} m of a scheduled stop"
          + ("" if walks is None else f"; within a {WALK_M} m walk along mapped roads {sum(a.get('walk_served', 0) for a in per.values()):,}"))
    return out_blocks, dict(per)


def transfers(stops, limit=600):
    """Places where two different operators stop within TRANSFER_M of each other: candidate integration points."""
    pts = [Point(s["lng"], s["lat"]) for s in stops]
    tree = STRtree(pts)
    seen, out = set(), []
    for i, s in enumerate(stops):
        for j in sorted(tree.query(pts[i].buffer(TRANSFER_M / 111_320 * 1.1))):   # sorted: the same output on every platform
            t = stops[j]
            if j <= i or t["operator"] == s["operator"]:
                continue
            d = _dist_m((s["lat"], s["lng"]), (t["lat"], t["lng"]))
            if d > TRANSFER_M:
                continue
            key = (s["operator"], t["operator"], round(s["lat"], 3), round(s["lng"], 3))
            if key in seen:
                continue
            seen.add(key)
            out.append({"a": s["operator"], "an": s["name"], "b": t["operator"], "bn": t["name"], "lat": round((s["lat"] + t["lat"]) / 2, 5), "lng": round((s["lng"] + t["lng"]) / 2, 5), "d": int(d)})
    out.sort(key=lambda x: (x["d"], x["a"], x["b"], x["an"], x["bn"], x["lat"], x["lng"]))
    print(f"    {len(out)} stop pairs of different operators within {TRANSFER_M} m")
    return out[:limit], len(out)
