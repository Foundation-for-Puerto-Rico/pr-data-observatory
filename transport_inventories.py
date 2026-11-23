"""The federal transportation inventories as map layers (HANDOFF decision 105, step 4; docs/transport-inventories.md): bridges and tunnels with their condition,
airports and heliports, the ferry routes with their passengers, and the electric vehicle charging stations. core/facilities.js draws them on the 2D map and in
the 3D view.

    python transport_inventories.py            # build the four layers (downloads only what cache/inventories/ does not have)
    python transport_inventories.py --refresh  # download every source again
    python transport_inventories.py --check    # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources, no key, all US Government work:
  FHWA National Bridge Inventory, the newest yearly Puerto Rico file (https://www.fhwa.dot.gov/bridge/nbi/<year>/delimited/PR<yy>.txt; the same files
      infrastructure_series.py counts by municipio): one row per bridge of 20 feet or more on a public road.
  FHWA National Tunnel Inventory, through the Bureau of Transportation Statistics' National Transportation Atlas Database (NTAD).
  FAA aviation facilities (NTAD copy of the FAA's 28-day airport data).
  BTS National Census of Ferry Operators, the newest census on data.bts.gov (passengers, vehicles, trips), with the line of each crossing from the NTAD
      ferry routes.
  US DOE Alternative Fuels Data Center stations (NTAD copy, refreshed daily); the telephone field is never read.

Output (site/data/), each a FeatureCollection with "source", "vintage", "built" and "notes":
  bridges.geojson      bridges and tunnels: name (the road carried), type (Bridge, Tunnel), municipio, geoid, and
                       x feature crossed; c condition (G good, F fair, P poor; T a tunnel); lr lowest rating (0-9); y year built; yr year rebuilt;
                       a daily traffic and ay its year; t trucks %; d detour km; l length m; o status (A open, P posted for load, B should be posted,
                       E/D open with temporary support, K closed); s 1 when scour critical (NBI item 113 codes 0-3); i last inspection (YYYY-MM);
                       w owner class (state, toll, municipal, federal, other); sn structure number
  airports.geojson     airports, heliports and seaplane bases open to the public or owned by a public body; a private facility owned privately is
                       counted, never drawn or named (a private heliport can be at a home; docs/transport-inventories.md)
  ferry_routes.geojson one line per pair of terminals, both directions added: passengers and vehicles in the census's data year, trips a year, minutes
  ev_stations.geojson  public electric vehicle charging stations: network, DC fast and Level 2 ports, connectors, status
"""

import csv
import io
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import facilities as fac
import housing_series as hs
import gateway_series as gw
import infrastructure_series as ins

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "inventories"
OUTDIR = hs.OUT
log = hs.log
NTAD = "https://services.arcgis.com/xOi1kZaI0eWDREZv/ArcGIS/rest/services/{svc}/FeatureServer/0/query"
NBI_COLS = ["STRUCTURE_NUMBER_008", "RECORD_TYPE_005A", "FEATURES_DESC_006A", "FACILITY_CARRIED_007", "LAT_016", "LONG_017", "DETOUR_KILOS_019", "OWNER_022",
            "YEAR_BUILT_027", "ADT_029", "YEAR_ADT_030", "OPEN_CLOSED_POSTED_041", "STRUCTURE_LEN_MT_049", "DATE_OF_INSPECT_090", "YEAR_RECONSTRUCTED_106",
            "PERCENT_ADT_TRUCK_109", "SCOUR_CRITICAL_113", "BRIDGE_CONDITION", "LOWEST_RATING"]
OWNER = {"01": "state", "31": "toll", "04": "municipal", "02": "municipal", "03": "municipal"}   # NBI item 22; codes 60-80 are federal agencies
FLOORS = {"bridges": 2000, "airports": 10, "ferry": 2, "ev": 10}   # 2,434 bridges in 2025, 17 drawn facilities, 3 routes, 26 stations in 2026-11


def get_json(svc, where, fields, geometry=True):
    r = fac.get(NTAD.format(svc=svc), params={"where": where, "outFields": fields, "returnGeometry": str(geometry).lower(), "outSR": 4326,
                                               "f": "geojson" if geometry else "json", "resultRecordCount": 2000})
    d = r.json()
    if "error" in d:
        raise SystemExit(f"transport_inventories: {svc} answered {d['error']}")
    return d


def cached(name, fetch, refresh, check):
    path = CACHE / name
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if check:
        raise FileNotFoundError(name)
    d = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


# ── Bridges and tunnels ──────────────────────────────────────────────────────

def fetch_nbi():
    """The kept columns of the newest NBI Puerto Rico file (FHWA publishes a year's file the next spring)."""
    for y in range(date.today().year, date.today().year - 4, -1):
        r = ins.get(ins.NBI.format(y=y, yy=str(y)[2:]))
        if r is not None and r.content[:14] == b"STATE_CODE_001":
            rows = list(csv.DictReader(io.StringIO(r.content.decode("latin-1"))))
            missing = [c for c in NBI_COLS if c not in rows[0]]
            if missing:
                raise SystemExit(f"transport_inventories: the NBI {y} file has no column {missing}")
            log(f"  NBI {y}: {len(rows)} rows")
            return {"year": y, "fetched": date.today().isoformat(), "rows": [{c: (x[c] or "").strip().strip("'").strip() for c in NBI_COLS} for x in rows]}
    raise SystemExit("transport_inventories: no NBI Puerto Rico file of the last four years answered")


def fetch_nti():
    d = get_json("NTAD_National_Tunnel_Inventory", "state_code_i3=72", "tunnel_number_i1,tunnel_name_i2,year,facility_carried_i10,portal_latitude_i13,"
                 "portal_longitude_i14,year_built_a1,year_rehabilitated_a2,adt_a4,year_of_average_daily_traffic_a,detour_length_a7,tunnel_length_g1,owner_c1",
                 geometry=False)
    return {"fetched": date.today().isoformat(), "rows": [x["attributes"] for x in d["features"]]}


def dms(v, deg_digits):
    """NBI items 16 and 17: degrees, minutes, seconds and hundredths, as digits (DDMMSSss, DDDMMSSss)."""
    v = v.strip()
    if not v.isdigit() or len(v) < deg_digits + 6:
        return None
    v = v.zfill(deg_digits + 6)
    d, m, s = int(v[:deg_digits]), int(v[deg_digits:deg_digits + 2]), int(v[deg_digits + 2:]) / 100
    return d + m / 60 + s / 3600 if m < 60 and s < 60 else None


def whole(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


FIX = {"Catano": "Cataño", "Ii": "II", "Iii": "III"}


def tidy(s):
    """FHWA, FAA and BTS write names in capitals: 'PR 873 0.7 KM' stays, 'FRAILES CREEK' becomes 'Frailes Creek', 'ISABEL II' 'Isabel II'."""
    out = []
    for w in " ".join(str(s or "").replace("@", " ").split()).split(" "):   # "PR 750@KM0.4": an @ reads as an e-mail address to the contract's PII check
        pre = w[:1] if w[:1] in "(\"'" else ""
        core = w[len(pre):]
        if any(ch.isdigit() for ch in core) or core in ("PR", "US", "KM"):
            out.append(w)
            continue
        c = core.capitalize()
        out.append(pre + FIX.get(c, c))
    return " ".join(out)


def owner(code):
    c = code.strip().zfill(2)
    return OWNER.get(c) or ("federal" if c.isdigit() and 60 <= int(c) <= 80 else "other")


def bridges(nbi, nti, M):
    feats, left_out = [], []
    for r in nbi["rows"]:
        if r["RECORD_TYPE_005A"] != "1":
            continue
        lat, lon = dms(r["LAT_016"], 2), dms(r["LONG_017"], 3)
        lon = -lon if lon else None
        geoid = M.at(lon, lat) if lat and lon else None
        if geoid is None:
            left_out.append(r["STRUCTURE_NUMBER_008"])
            continue
        insp = r["DATE_OF_INSPECT_090"].zfill(4)
        sc = r["SCOUR_CRITICAL_113"]
        feats.append(fac.feature(lon, lat, tidy(r["FACILITY_CARRIED_007"]), "Bridge", geoid, M, sn=r["STRUCTURE_NUMBER_008"], x=tidy(r["FEATURES_DESC_006A"]),
                                 c=r["BRIDGE_CONDITION"] or None, lr=whole(r["LOWEST_RATING"]), y=whole(r["YEAR_BUILT_027"]),
                                 yr=whole(r["YEAR_RECONSTRUCTED_106"]) or None, a=whole(r["ADT_029"]), ay=whole(r["YEAR_ADT_030"]),
                                 t=whole(r["PERCENT_ADT_TRUCK_109"]) or None, d=whole(r["DETOUR_KILOS_019"]) or None,
                                 l=round(float(r["STRUCTURE_LEN_MT_049"] or 0), 1) or None, o=r["OPEN_CLOSED_POSTED_041"] or None,
                                 s=1 if sc in ("0", "1", "2", "3") else None, i=f"20{insp[2:]}-{insp[:2]}" if insp.isdigit() and 1 <= int(insp[:2]) <= 12 else None,
                                 w=owner(r["OWNER_022"])))
    for r in nti["rows"]:
        lat, lon = r.get("portal_latitude_i13"), r.get("portal_longitude_i14")
        geoid = M.at(lon, lat) if lat and lon else None
        if geoid is None:
            left_out.append(r.get("tunnel_number_i1"))
            continue
        feats.append(fac.feature(lon, lat, tidy(r["tunnel_name_i2"]), "Tunnel", geoid, M, sn=r.get("tunnel_number_i1"), x=tidy(r.get("facility_carried_i10")),
                                 c="T", y=whole(r.get("year_built_a1")), yr=whole(r.get("year_rehabilitated_a2")) or None, a=whole(r.get("adt_a4")),
                                 ay=whole(r.get("year_of_average_daily_traffic_a")), d=whole(r.get("detour_length_a7")) or None,
                                 l=whole(r.get("tunnel_length_g1"))))
    feats.sort(key=lambda f: (-(f["properties"].get("a") or 0), f["properties"].get("sn") or ""))   # busiest first: the 2D map draws later (quieter, smaller) circles on top
    b = [f["properties"] for f in feats if f["properties"]["type"] == "Bridge"]
    cond = Counter(p.get("c") for p in b)
    notes = {"bridges": len(b), "tunnels": sum(1 for f in feats if f["properties"]["type"] == "Tunnel"), "good": cond["G"], "fair": cond["F"], "poor": cond["P"],
             "closed": sum(1 for p in b if p.get("o") == "K"), "posted": sum(1 for p in b if p.get("o") in ("P", "B")),
             "scour_critical": sum(1 for p in b if p.get("s")),
             "adt_years": [min(p["ay"] for p in b if p.get("ay")), max(p["ay"] for p in b if p.get("ay"))], "nbi_year": nbi["year"],
             "nti_year": max((whole(r.get("year")) or 0 for r in nti["rows"]), default=None), "left_out": left_out}
    return feats, notes, str(nbi["year"]), nbi["fetched"]


# ── Airports, heliports and seaplane bases ──────────────────────────────────

SITE = {"A": "Airport", "H": "Heliport", "C": "Seaplane base", "U": "Ultralight park", "G": "Gliderport", "B": "Balloonport"}


def fetch_faa():
    d = get_json("NTAD_Aviation_Facilities", "STATE_CODE='PR'", "EFF_DATE,SITE_NO,SITE_TYPE_CODE,ARPT_ID,CITY,ARPT_NAME,OWNERSHIP_TYPE_CODE,"
                 "FACILITY_USE_CODE,LAT_DECIMAL,LONG_DECIMAL,ELEV,ARPT_STATUS,FAR_139_TYPE_CODE,TWR_TYPE_CODE", geometry=False)
    return {"fetched": date.today().isoformat(), "rows": [x["attributes"] for x in d["features"]]}


def airports(faa, M):
    feats, hidden, left_out = [], Counter(), []
    for r in faa["rows"]:
        if (r.get("ARPT_STATUS") or "O") != "O":
            continue
        kind = SITE.get(r.get("SITE_TYPE_CODE"), "Other")
        public_use, owned = r.get("FACILITY_USE_CODE") == "PU", r.get("OWNERSHIP_TYPE_CODE")
        if not public_use and owned == "PR":
            hidden[kind] += 1   # privately owned, private use: counted only (a private heliport can be at a home)
            continue
        lon, lat = r.get("LONG_DECIMAL"), r.get("LAT_DECIMAL")
        geoid = M.at(lon, lat) if lon and lat else None
        if geoid is None:
            left_out.append(r.get("ARPT_ID"))
            continue
        cat = "commercial" if (r.get("FAR_139_TYPE_CODE") or "").strip() else ("airport" if kind == "Airport" else "heliport" if kind == "Heliport" else "seaplane")
        feats.append(fac.feature(lon, lat, tidy(r.get("ARPT_NAME")), kind, geoid, M, faa=r.get("ARPT_ID"), cat=cat, use="public" if public_use else "private",
                                 own={"PU": "public", "PR": "private", "MA": "military", "MN": "military", "MR": "military", "CG": "military"}.get(owned, "other"),
                                 elev=whole(r.get("ELEV")), tower=1 if (r.get("TWR_TYPE_CODE") or "").startswith("ATCT") else None))
    order = {"commercial": 0, "airport": 1, "seaplane": 2, "heliport": 3}
    feats.sort(key=lambda f: (order.get(f["properties"]["cat"], 9), f["properties"]["faa"] or ""))
    eff = max(r.get("EFF_DATE") or "" for r in faa["rows"]).replace("/", "-")
    notes = {"drawn": len(feats), "by_cat": dict(Counter(f["properties"]["cat"] for f in feats)), "private_not_drawn": sum(hidden.values()),
             "private_by_kind": dict(hidden), "in_faa_file": len(faa["rows"]), "left_out": left_out}
    return feats, notes, eff, faa["fetched"]


# ── Ferry routes ─────────────────────────────────────────────────────────────

def simplify(pts, tol=0.0002):
    """Douglas-Peucker in degrees (0.0002 is about 20 m here): the census draws each crossing with hundreds of points."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    n = (dx * dx + dy * dy) ** .5 or 1e-12
    dist = [abs(dy * x - dx * y + x2 * y1 - y2 * x1) / n for x, y in pts[1:-1]]
    i = max(range(len(dist)), key=dist.__getitem__)
    if dist[i] <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:i + 2], tol)[:-1] + simplify(pts[i + 1:], tol)


def fetch_ferry():
    """The newest National Census of Ferry Operators on data.bts.gov (the figures; gateway_series.py reads the same files for its counts by municipio) and
    the NTAD ferry routes (only the line each crossing follows: NTAD holds the 2020 census, with the same terminal ids)."""
    census = max(gw.NCFO)
    op_seg, seg, term = gw.NCFO[census]
    terms = gw.soda(term, **{"$where": "term_state='PR'"})
    tids = sorted(t["terminal_id"] for t in terms)
    inn = ",".join(f"'{i}'" for i in tids)
    segs = gw.soda(seg, **{"$where": f"seg_terminal1_id in ({inn})"})
    ops = gw.soda(op_seg, **{"$where": "segment_id in (" + ",".join(f"'{x['segment_id']}'" for x in segs) + ")"})
    lines = get_json("NTAD_Ferry_Routes", f"seg_terminal1_id IN ({inn}) OR seg_terminal2_id IN ({inn})", "seg_terminal1_id,seg_terminal2_id")
    keep = ("passengers", "vehicles", "trips_per_year", "average_trip_time", "segment_id")
    return {"fetched": date.today().isoformat(), "census": census,
            "terminals": [{k: t.get(k) for k in ("terminal_id", "terminal_name", "longitude", "latitude", "data_year")} for t in terms],
            "segments": [{k: x.get(k) for k in ("segment_id", "seg_terminal1_id", "seg_terminal2_id")} for x in segs],
            "operations": [{k: o.get(k) for k in keep} for o in ops], "lines": lines}


def ferries(d):
    names = {str(t["terminal_id"]): tidy(t["terminal_name"]) for t in d["terminals"]}
    ends = {str(x["segment_id"]): (str(x["seg_terminal1_id"]), str(x["seg_terminal2_id"])) for x in d["segments"]}
    shape = {}
    for f in d["lines"]["features"]:
        p = f["properties"]
        shape.setdefault(tuple(sorted((str(p["seg_terminal1_id"]), str(p["seg_terminal2_id"])))), f["geometry"])
    pairs, no_line = {}, Counter()
    for o in d["operations"]:
        key = tuple(sorted(ends[str(o["segment_id"])]))
        q = pairs.setdefault(key, {"pax": 0, "veh": 0, "trips": 0, "min": []})
        q["pax"] += whole(o["passengers"]) or 0
        q["veh"] += whole(o["vehicles"]) or 0
        q["trips"] += whole(o["trips_per_year"]) or 0
        q["min"].append(whole(o["average_trip_time"]) or 0)
    feats = []
    for (a, b), q in sorted(pairs.items(), key=lambda kv: -kv[1]["pax"]):
        g = shape.get((a, b))
        if g is None or g["type"] != "LineString":
            no_line[f"{names.get(a, a)} – {names.get(b, b)}"] += q["pax"]   # a crossing with no line in NTAD (Culebra–Vieques: one trip a year each way in 2024)
            continue
        feats.append({"type": "Feature", "properties": {"name": f"{names.get(a, a)} – {names.get(b, b)}", "type": "Ferry route", "pax": q["pax"], "veh": q["veh"] or None,
                                                        "trips": q["trips"], "min": round(sum(q["min"]) / len(q["min"]))},
                      "geometry": {"type": "LineString", "coordinates": [[round(x, 5), round(y, 5)] for x, y in simplify(g["coordinates"])]}})
    years = {whole(t.get("data_year")) for t in d["terminals"]} - {None}
    year = years.pop() if len(years) == 1 else d["census"]   # since 2022 BTS names a census for the year of its data (gateway_series.py)
    notes = {"routes": len(feats), "terminals": len(d["terminals"]), "passengers": sum(f["properties"]["pax"] for f in feats), "data_year": year,
             "census_year": d["census"], "not_drawn": [{"pair": k, "passengers": v} for k, v in sorted(no_line.items())]}
    return feats, notes, str(year), d["fetched"]


# ── Electric vehicle charging ───────────────────────────────────────────────

def fetch_afdc():
    d = get_json("Alternative_Fueling_Stations", "state='PR' AND fuel_type_code='ELEC'", "id,station_name,city,latitude,longitude,status_code,access_code,"
                 "ev_network,ev_dc_fast_num,ev_level2_evse_num,ev_level1_evse_num,ev_connector_types,facility_type,open_date,date_last_confirmed,updated_at",
                 geometry=False)
    return {"fetched": date.today().isoformat(), "rows": [x["attributes"] for x in d["features"]]}


def ev(d, M):
    feats, left_out = [], []
    for r in d["rows"]:
        if r.get("access_code") != "public" or r.get("status_code") not in ("E", "T"):
            continue
        geoid = M.at(r["longitude"], r["latitude"])
        if geoid is None:
            left_out.append(r.get("id"))
            continue
        dc, l2, l1 = whole(r.get("ev_dc_fast_num")) or 0, whole(r.get("ev_level2_evse_num")) or 0, whole(r.get("ev_level1_evse_num")) or 0
        conn = [c for c in str(r.get("ev_connector_types") or "").replace(";", ",").split(",") if c.strip()]
        feats.append(fac.feature(r["longitude"], r["latitude"], " ".join(str(r.get("station_name") or "").split()), "EV charging station", geoid, M,
                                 afdc=r.get("id"), kind="dc" if dc else "l2", ports=dc + l2 + l1, dc=dc or None, l2=l2 or None, l1=l1 or None,
                                 net=" ".join(str(r.get("ev_network") or "").split()) or None, conn=[c.strip() for c in conn] or None,
                                 status="open" if r["status_code"] == "E" else "unavailable", confirmed=r.get("date_last_confirmed") or None))
    feats.sort(key=lambda f: (-f["properties"]["ports"], f["properties"]["afdc"] or 0))
    p = [f["properties"] for f in feats]
    updated = max((fac.iso(r.get("updated_at")) or "" for r in d["rows"]), default="")
    notes = {"stations": len(p), "dc_fast_stations": sum(1 for x in p if x["kind"] == "dc"), "ports": sum(x["ports"] for x in p), "dc_ports": sum(x.get("dc") or 0 for x in p),
             "unavailable": sum(1 for x in p if x["status"] == "unavailable"), "municipios": len({x["geoid"] for x in p}), "left_out": left_out}
    return feats, notes, updated or d["fetched"], d["fetched"]


# ── Build ────────────────────────────────────────────────────────────────────

LAYERS = {   # key: (output file, source key, floor key)
    "bridges": ("bridges.geojson", "fhwa_nbi"), "airports": ("airports.geojson", "faa_airports"),
    "ferry": ("ferry_routes.geojson", "bts_ferry"), "ev": ("ev_stations.geojson", "afdc_stations")}


def build(refresh=False, check=False):
    try:
        nbi = cached("nbi.pr.json", fetch_nbi, refresh, check)
        nti = cached("nti.pr.json", fetch_nti, refresh, check)
        faa = cached("faa.pr.json", fetch_faa, refresh, check)
        fer = cached("ferry_ncfo.pr.json", fetch_ferry, refresh, check)
        afd = cached("afdc.pr.json", fetch_afdc, refresh, check)
    except FileNotFoundError as e:
        log(f"transport_inventories --check: {e} is not in the cache")
        return 1
    M = fac.Munis()
    made = {"bridges": bridges(nbi, nti, M), "airports": airports(faa, M), "ferry": ferries(fer), "ev": ev(afd, M)}
    bad = 0
    for k, (feats, notes, vintage, built) in made.items():
        name, src = LAYERS[k]
        n = notes.get("bridges") or notes.get("drawn") or notes.get("routes") or notes.get("stations") or 0
        if n < FLOORS[k]:
            raise SystemExit(f"transport_inventories: {name} would hold only {n} features (at least {FLOORS[k]} expected); not written")
        text = json.dumps({"type": "FeatureCollection", "source": src, "vintage": vintage, "built": built, "notes": notes, "features": feats},
                          ensure_ascii=False, separators=(",", ":"))
        out = OUTDIR / name
        if check:
            same = out.exists() and out.read_text(encoding="utf-8") == text
            log(f"{name} {'is' if same else 'is NOT'} what the cache gives")
            bad += not same
            continue
        out.write_text(text, encoding="utf-8", newline="\n")
        log(f"wrote {name}: {len(feats)} features, {len(text) // 1024} KB; " + ", ".join(f"{a}={b}" for a, b in notes.items() if not isinstance(b, (list, dict))))
    return 1 if bad else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
