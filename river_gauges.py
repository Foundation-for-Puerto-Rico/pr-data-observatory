"""River flow for the PR Data Observatory: one point per river or stream with a live USGS gauge, its last 120 days and the usual flow for each week of the year,
for the "River flow" layer of the 2D map and the 3D view (core/facilities.js draws it; the page asks USGS for the latest reading when the layer is switched on).

    python river_gauges.py              # build site/data/river_gauges.geojson (downloads only what is missing from cache/river_gauges/)
    python river_gauges.py --refresh    # download every gauge again
    python river_gauges.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the USGS Water Data API (https://api.waterdata.usgs.gov/ogcapi/v1/; US government work, public domain), the source of reservoirs.py.
  monitoring-locations  the streams of Puerto Rico (site_type_code ST) and their points
  latest-continuous     parameter 00060, discharge (the volume of water passing the gauge each second), cubic feet per second: the latest reading, every 15 minutes or so
  daily                 parameter 00060, statistic 00003 (the mean of the day), one value a day: the history
Both are converted to cubic metres per second (x 0.0283168).
  latest-continuous     parameter 00065, gauge height (how high the water stands on the gauge's own scale, in feet; kept in metres), and parameter 00010, water
                        temperature (degrees Celsius), for the gauges that report them: the latest reading at build time, which the page replaces with a live one
Also, from USGS Real-Time Flood Impacts (https://api.waterdata.usgs.gov/rtfi-api/, the same agency, public domain): the flood reference levels USGS has surveyed
at a gauge (the top of the riverbank, the lowest beam and the deck of a bridge, a past flood's high-water mark), each a gauge height. On 2026-11-12 Puerto Rico
has four, all at one gauge (Río de la Plata at Comerío).
Also, from the National Weather Service's National Water Prediction Service (https://api.water.noaa.gov/nwps/v1/, no key; NWS information is in the public
domain): the flood stages NWS has set at a gauge (action, minor, moderate, major), each a gauge height in feet on the scale of the USGS gauge NWS names for it.
A gauge keeps them only when NWS gives them in feet, and, where NWS's own latest reading and USGS's were taken within an hour of each other, when the two are
within half a foot (the check that both read the same scale).

Which gauges. Every stream gauge whose discharge reading is less than 30 days old and that has at least 8 years of daily values in 2011-2025.

The usual flow. As reservoirs.py: for each gauge and each week of the year, the mean of the daily values of that week in each year 2011-2025, then the 10th, 25th,
50th, 75th and 90th percentile of those yearly means (at least 8 years; otherwise null). The page says where today's reading falls: below the 10th percentile is
"lower than usual for this time of year", above the 90th "higher", between them "usual".

What this is not. A flow higher than usual is not a flood warning: the layer has no flood stage (the National Weather Service sets those, for a few gauges), and
a river can leave its banks between gauges. USGS marks recent readings provisional. Some gauges sit below a dam or a water intake, so their flow is what the
operator releases, not what the rain brings.

Output: site/data/river_gauges.geojson. Each point: name (the river, with its accents), type, municipio, geoid, usgs (the monitoring location id), station (the
name USGS gives the gauge, as written), flow and flow_time (the latest reading at build time; the page replaces them with a live one), recent (daily flows in
m³/s from recent_start, 120 values, null where missing), and p10, p25, p50, p75, p90 (53 weekly values each, m³/s). Where the gauge reports them: stage and
stage_time (gauge height, metres), temp and temp_time (water temperature, °C), and refs (the flood reference levels: kind, label as USGS writes it, level in
metres of gauge height, lowest first), and nws (the National Weather Service's flood stages: lid, the id NWS gives the gauge, and action, minor, moderate,
major, each in metres of gauge height, only the ones NWS has set).
"""

import json
import statistics
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

import facilities as fac
import housing_series as hs
import reservoirs as rv

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "river_gauges"
OUT = hs.OUT / "river_gauges.geojson"
CFS = 0.0283168        # cubic feet per second to cubic metres per second
FT = 0.3048            # feet to metres
MORE = {"00065": ("stage", FT, 2), "00010": ("temp", 1.0, 1)}   # the other readings a gauge may report: its key in the file, what turns the unit into the file's, decimals
RTFI = "https://api.waterdata.usgs.gov/rtfi-api/referencepoints/state/46"   # USGS Real-Time Flood Impacts; 46 is Puerto Rico in the service's own list of states
REF_KIND = {"BANK": "bank", "CHORD": "chord", "DECK": "deck", "HWM": "hwm"}   # the service's names of a reference point; any other is kept as "other"
NWPS = "https://api.water.noaa.gov/nwps/v1/gauges"   # the National Weather Service's gauges; one of them names its USGS gauge and gives its flood stages
PR_BOX = {"bbox.xmin": -68.0, "bbox.ymin": 17.6, "bbox.xmax": -65.1, "bbox.ymax": 18.6, "srid": "EPSG_4326"}
STAGES = ("action", "minor", "moderate", "major")   # NWS's flood categories, lowest first
SAME_SCALE_FT = 0.5    # NWS's reading and USGS's, taken within an hour, may differ by this much and still be the same scale
YEARS = rv.YEARS       # the years the usual flow is taken from (those of the reservoirs)
MIN_YEARS = rv.MIN_YEARS
RECENT = rv.RECENT
STALE_DAYS = rv.STALE_DAYS
log = hs.log
MAX_WAIT = 20 * 60     # the longest the build waits when USGS says it has had too many requests

# USGS writes station names in capitals without accents; the words of Puerto Rico's river names that carry one
ACCENTS = {"Rio": "Río", "Canovanas": "Canóvanas", "Loiza": "Loíza", "Bayamon": "Bayamón", "Manati": "Manatí", "Anasco": "Añasco", "Guanajibo": "Guanajibo",
           "Mameyes": "Mameyes", "Espiritu": "Espíritu", "Culebrinas": "Culebrinas", "Gurabo": "Gurabo", "Cibuco": "Cibuco", "Tanama": "Tanamá", "Yaguez": "Yagüez",
           "Jacaguas": "Jacaguas", "Portugues": "Portugués", "Canas": "Cañas", "Bucana": "Bucaná", "Inabon": "Inabón", "Guayanes": "Guayanés", "Humacao": "Humacao",
           "Icacos": "Icacos", "Sabana": "Sabana", "Fajardo": "Fajardo", "Maunabo": "Maunabo", "Guamani": "Guamaní", "Majada": "Majada", "Lapa": "Lapa",
           "Coamo": "Coamo", "Descalabrado": "Descalabrado", "Toa": "Toa", "Vaca": "Vaca", "Guayanilla": "Guayanilla", "Yauco": "Yauco", "Loco": "Loco",
           "Rosario": "Rosario", "Camuy": "Camuy", "Guajataca": "Guajataca", "Arecibo": "Arecibo", "Caonillas": "Caonillas", "Limon": "Limón", "Yunes": "Yunes",
           "Saliente": "Saliente", "Orocovis": "Orocovis", "Bauta": "Bauta", "Cialitos": "Cialitos", "Unibon": "Unibón", "Morovis": "Morovis", "Mavilla": "Mavilla",
           "Guadiana": "Guadiana", "Caguitas": "Cagüitas", "Bairoa": "Bairoa", "Valenciano": "Valenciano", "Turabo": "Turabo", "Cayaguas": "Cayaguás",
           "Piedras": "Piedras", "Guaynabo": "Guaynabo", "Hondo": "Hondo", "Minillas": "Minillas", "Piñones": "Piñones", "Canal": "Canal", "Quebrada": "Quebrada",
           "Cano": "Caño", "Rincon": "Rincón", "Maricao": "Maricao", "Jayuya": "Jayuya", "Viví": "Viví", "Vivi": "Viví", "Pellejas": "Pellejas", "Grande": "Grande",
           "Mayaguez": "Mayagüez", "Gaudiana": "Guadiana", "Nigua": "Nigua", "Cerrillos": "Cerrillos", "Marin": "Marín", "Santiago": "Santiago", "Tallaboa": "Tallaboa",
           "Penuelas": "Peñuelas", "Jueyes": "Jueyes", "Salinas": "Salinas", "Patillas": "Patillas", "Chico": "Chico", "Blanco": "Blanco", "Seco": "Seco",
           "Matrullas": "Matrullas", "Toro": "Toro", "Negro": "Negro", "Guaba": "Guabá", "Sonadora": "Sonadora", "Prieto": "Prieto", "Duey": "Duey", "Qda.": "Quebrada", "Usabon": "Usabón"}
LOWER = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y"}
# where the river's name ends and the place of the gauge starts in a USGS station name
CUTS = (" AT ", " NEAR ", " NR ", " ABOVE ", " ABV ", " AB ", " BELOW ", " BLW ", " BL ", " BLO ", " ABOVE", " BELOW")


def get(path, **params):
    """A page of the API. Without a key USGS allows a limited number of requests an hour and answers 429 with the seconds to wait: the build waits and asks again."""
    for attempt in range(5):
        try:
            r = requests.get(f"{rv.API}/{path}/items", params={"f": "json", **params}, headers=rv.UA, timeout=(30, 180))
            if r.status_code == 429:
                wait = min(int(r.headers.get("Retry-After") or 60) + 5, MAX_WAIT)
                log(f"USGS asks to wait {wait} s (too many requests); waiting")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == 4:
                raise SystemExit(f"river_gauges: {path} failed: {e}")
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f"river_gauges: {path} failed: USGS still answers 429 (too many requests); run it again later, the cache keeps what was downloaded")


def river_name(usgs_name):
    """'RIO GRANDE DE LOIZA AT CAGUAS, PR' -> 'Río Grande de Loíza'."""
    s = usgs_name.split(",")[0]
    for cut in CUTS:
        s = s.split(cut)[0]
    words = [w.lower() if w in LOWER and i else w.capitalize() for i, w in enumerate(s.split())]
    return " ".join(ACCENTS.get(w, w) for w in words)


def fetch(refresh=False):
    """The cache: sites.json (the gauges, their points and latest readings) and one daily file per gauge that has a recent reading."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sites_p = CACHE / "sites.json"
    if refresh or not sites_p.exists():
        locs = get("monitoring-locations", state_code="72", site_type_code="ST", limit=10000)["features"]
        ids = [f["id"] for f in locs]
        latest = []
        for k in range(0, len(ids), 40):
            latest += get("latest-continuous", monitoring_location_id=",".join(ids[k:k + 40]), parameter_code="00060", limit=1000,
                             properties="monitoring_location_id,time,value", skipGeometry="true")["features"]
        last = {f["properties"]["monitoring_location_id"]: f["properties"] for f in latest if f["properties"].get("value") not in (None, "")}
        today = date.today()
        sites = [{"id": f["id"], "name": f["properties"].get("monitoring_location_name"), "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                  "flow": float(last[f["id"]]["value"]), "time": last[f["id"]]["time"]} for f in locs if f["id"] in last and f.get("geometry")]
        stale = [s for s in sites if (today - date.fromisoformat(s["time"][:10])).days > STALE_DAYS]
        sites = [s for s in sites if s not in stale]   # a gauge that stopped reporting years ago has no daily file to fetch
        sites_p.write_text(json.dumps({"fetched": today.isoformat(), "stream_sites": len(locs), "with_discharge": len(last), "stale": len(stale), "sites": sites},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    S = json.loads(sites_p.read_text(encoding="utf-8"))
    for s in S["sites"]:
        p = CACHE / f"{s['id']}.json"
        if refresh or not p.exists():
            d = get("daily", monitoring_location_id=s["id"], parameter_code="00060", statistic_id="00003", datetime=f"{YEARS[0]}-01-01/{date.today().isoformat()}",
                       limit=10000, properties="time,value", skipGeometry="true")["features"]
            p.write_text(json.dumps({r["properties"]["time"]: r["properties"]["value"] for r in d}, separators=(",", ":")), encoding="utf-8")
    return S


def extras(S, refresh=False, check=False):
    """The cache's extras.json: for the gauges of sites.json, the latest gauge height and water temperature, and USGS's flood reference levels."""
    p = CACHE / "extras.json"
    if check or (p.exists() and not refresh):
        return json.loads(p.read_text(encoding="utf-8"))
    ids, today = [s["id"] for s in S["sites"]], date.today()
    out = {"fetched": today.isoformat(), "stage": {}, "temp": {}, "refs": {}}
    for code, (key, _, _) in MORE.items():
        for k in range(0, len(ids), 40):
            for f in get("latest-continuous", monitoring_location_id=",".join(ids[k:k + 40]), parameter_code=code, limit=1000,
                         properties="monitoring_location_id,time,value", skipGeometry="true")["features"]:
                q = f["properties"]
                if q.get("value") not in (None, "") and (today - date.fromisoformat(q["time"][:10])).days <= STALE_DAYS:
                    out[key][q["monitoring_location_id"]] = {"value": float(q["value"]), "time": q["time"]}
    r = requests.get(RTFI, headers=rv.UA, timeout=(30, 120))
    r.raise_for_status()
    for x in r.json():
        if x.get("active") and x.get("unit") == "ft" and x.get("rp_elevation") is not None and "USGS-" + str(x.get("nwis_id")) in ids:
            out["refs"].setdefault("USGS-" + str(x["nwis_id"]), []).append({"kind": REF_KIND.get((x.get("rp_name") or "").upper(), "other"), "label": (x.get("description") or "").strip(),
                                                                          "level_ft": float(x["rp_elevation"])})
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def nws_get(url, **params):
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=rv.UA, timeout=(30, 120))
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == 3:
                raise SystemExit(f"river_gauges: {url} failed: {e}")
            time.sleep(3 * (attempt + 1))


def nws(S, refresh=False, check=False):
    """The cache's nws.json: for the gauges of sites.json that the National Weather Service lists with flood stages, its id, the stages (feet) and its latest reading."""
    p = CACHE / "nws.json"
    if check or (p.exists() and not refresh):
        return json.loads(p.read_text(encoding="utf-8"))
    ids = {s["id"] for s in S["sites"]}
    listed = [g["lid"] for g in nws_get(NWPS, **PR_BOX)["gauges"] if (g.get("state") or {}).get("abbreviation") == "PR"]
    out = {"fetched": date.today().isoformat(), "listed": len(listed), "gauges": {}}
    for lid in listed:   # the list has no USGS id and no stages: each gauge's own record does
        g = nws_get(f"{NWPS}/{lid}")
        usgs, flood = "USGS-" + str(g.get("usgsId") or ""), g.get("flood") or {}
        stages = {k: float(v["stage"]) for k, v in (flood.get("categories") or {}).items() if k in STAGES and v and v.get("stage") is not None and float(v["stage"]) > -900}
        if usgs in ids and stages:
            obs = (g.get("status") or {}).get("observed") or {}
            out["gauges"][usgs] = {"lid": lid, "name": g.get("name"), "units": flood.get("stageUnits"), "stages": stages,
                                   "observed": obs.get("primary") if obs.get("primaryUnit") == "ft" else None, "observed_time": obs.get("validTime")}
        time.sleep(0.15)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def nws_field(usgs, X, W):
    """A gauge's nws field, or (None, why) when NWS's stages cannot be set beside USGS's gauge height."""
    g, s = W["gauges"].get(usgs), X["stage"].get(usgs)
    if not g:
        return None, None
    if not s:
        return None, "the gauge reports no gauge height"
    if g["units"] != "ft":
        return None, f"NWS gives the stages in {g['units']!r}, not feet"
    levels = [g["stages"][k] for k in STAGES if k in g["stages"]]
    if levels != sorted(levels):
        return None, "NWS's stages do not rise from action to major"
    if g.get("observed") is not None and g.get("observed_time"):
        apart = abs((datetime.fromisoformat(g["observed_time"].replace("Z", "+00:00")) - datetime.fromisoformat(s["time"])).total_seconds())
        if apart <= 3600 and abs(float(g["observed"]) - s["value"]) > SAME_SCALE_FT:
            return None, f"NWS reads {g['observed']} ft where USGS reads {s['value']} ft: not the same scale"
    return {"lid": g["lid"], **{k: round(g["stages"][k] * FT, 2) for k in STAGES if k in g["stages"]}}, None


def more_fields(usgs, X):
    """The fields of a gauge beyond its flow: stage, temp (with their times) and refs, each only where the gauge has it."""
    out = {}
    for key, k, dec in MORE.values():
        v = X[key].get(usgs)
        if v:
            out[key], out[key + "_time"] = round(v["value"] * k, dec), v["time"]
    refs = X["refs"].get(usgs)
    if refs and "stage" in out:   # a reference level means something only beside the water's own level
        out["refs"] = sorted(({"kind": r["kind"], "label": r["label"], "level": round(r["level_ft"] * FT, 2)} for r in refs), key=lambda r: (r["level"], r["kind"]))
    return out


def flow(v):
    """Cubic feet per second to cubic metres per second, three decimals (a small stream runs at a few hundredths)."""
    return round(float(v) * CFS, 3)


def normals(daily):
    """p10..p90 of the yearly mean of each week, m³/s, or None where fewer than MIN_YEARS years have a value; and the years with any value."""
    by = {}
    for t, v in daily.items():
        d = date.fromisoformat(t)
        if YEARS[0] <= d.year <= YEARS[1] and v not in (None, ""):
            by.setdefault((rv.week(d), d.year), []).append(float(v) * CFS)
    out = {q: [None] * 53 for q in (10, 25, 50, 75, 90)}
    for w in range(53):
        yearly = [statistics.fmean(by[(w, y)]) for y in range(YEARS[0], YEARS[1] + 1) if (w, y) in by]
        if len(yearly) >= MIN_YEARS:
            for q in out:
                out[q][w] = round(rv.quantile(yearly, q / 100), 3)
    return out, len({y for (_, y) in by})


def build(refresh=False, check=False):
    S = fetch(refresh) if not check else json.loads((CACHE / "sites.json").read_text(encoding="utf-8"))
    built = date.fromisoformat(S["fetched"])
    X = extras(S, refresh, check)
    W = nws(S, refresh, check)
    nws_out = []
    M = fac.Munis()
    feats, left_out = [], []
    for s in S["sites"]:
        daily = json.loads((CACHE / f"{s['id']}.json").read_text(encoding="utf-8"))
        norm, years = normals(daily)
        geoid = M.at(s["lon"], s["lat"])
        if years < MIN_YEARS or geoid is None:
            left_out.append({"usgs": s["id"], "name": river_name(s["name"]),
                             "why": f"{years} years of daily values in {YEARS[0]}-{YEARS[1]}" if years < MIN_YEARS else "the point is outside every municipio"})
            continue
        start = built - timedelta(days=RECENT - 1)
        recent = [daily.get((start + timedelta(days=i)).isoformat()) for i in range(RECENT)]
        feats.append(fac.feature(s["lon"], s["lat"], river_name(s["name"]), "River gauge", geoid, M, usgs=s["id"], station=s["name"],
                                 flow=flow(s["flow"]), flow_time=s["time"], recent_start=start.isoformat(),
                                 recent=[flow(v) if v not in (None, "") else None for v in recent],
                                 **{f"p{q}": norm[q] for q in (10, 25, 50, 75, 90)}, **more_fields(s["id"], X)))
        stages, why = nws_field(s["id"], X, W)
        if stages:
            feats[-1]["properties"]["nws"] = stages
        elif why:
            nws_out.append({"usgs": s["id"], "why": why})
    feats.sort(key=lambda f: (f["properties"]["name"], f["properties"]["usgs"]))
    if len(feats) < 40:   # 70 or so on 2026-11-11: fewer than 40 means the API answered with part of the network
        raise SystemExit(f"river_gauges: only {len(feats)} gauges with a recent reading and a usual flow; not written")
    out = {"type": "FeatureCollection", "source": "usgs_water", "vintage": S["fetched"], "built": S["fetched"],
           "notes": {"gauges": len(feats), "rivers": len({f["properties"]["name"] for f in feats}), "municipios": len({f["properties"]["geoid"] for f in feats}),
                     "stream_sites": S["stream_sites"], "stopped_reporting": S["stale"] + S["stream_sites"] - S["with_discharge"],
                     "usual_years": f"{YEARS[0]}-{YEARS[1]}", "min_years": MIN_YEARS, "left_out": left_out,
                     "more_fetched": X["fetched"], "with_gauge_height": sum("stage" in f["properties"] for f in feats), "with_water_temperature": sum("temp" in f["properties"] for f in feats),
                     "with_flood_reference_levels": sum("refs" in f["properties"] for f in feats),
                     "nws_fetched": W["fetched"], "nws_gauges_listed": W["listed"], "with_nws_flood_stages": sum("nws" in f["properties"] for f in feats), "nws_left_out": nws_out},
           "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"river_gauges.geojson {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(feats)} gauges on {out['notes']['rivers']} rivers and streams in {out['notes']['municipios']} municipios, {len(left_out)} left out, {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
