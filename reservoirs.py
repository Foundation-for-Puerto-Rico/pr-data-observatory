"""Reservoir water levels for the PR Data Observatory: one point per reservoir with a live USGS gauge, its last 120 days and the usual level for each week of
the year, for the "Reservoir levels" layer of the 2D map and the 3D view (core/facilities.js draws it; the page asks USGS for the latest reading when the layer
is switched on).

    python reservoirs.py              # build site/data/reservoirs.geojson (downloads only what is missing from cache/reservoirs/)
    python reservoirs.py --refresh    # download every gauge again
    python reservoirs.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the USGS Water Data API (https://api.waterdata.usgs.gov/ogcapi/v1/; US government work, public domain).
  monitoring-locations  the lakes and reservoirs of Puerto Rico (site_type_code LK) and their points
  latest-continuous     parameter 72376, lake or reservoir water-surface elevation above local mean sea level, meters: the latest reading, every 15 minutes or so
  daily                 parameter 72375, the same elevation in feet, one value a day since 1987: the history (converted to meters, x 0.3048)

Which reservoirs. Every lake or reservoir whose 72376 reading is less than 30 days old and that has at least 8 years of daily values in 2011-2025. On 2026-11-02:
the 19 that the Puerto Rico Aqueduct and Sewer Authority (AAA) reports every morning, and a few others (irrigation and flood-control reservoirs). `aaa` marks the 19.
On that day the 72376 reading matched the level of AAA's 05:00 chart to within 0.08 m for 18 of the 19 (docs/facilities.md, Reservoir levels).

The usual level. For each reservoir and each week of the year (week 1 = 1-7 January, week 53 = 31 December and, in leap years, 30 December), the mean of the daily
values of that week in each year 2011-2025, then the 10th, 25th, 50th, 75th and 90th percentile of those yearly means (at least 8 years; otherwise null). The page
says where today's reading falls: below the 10th percentile is "lower than usual for this time of year", above the 90th "higher", between them "usual". A level is not a volume: sediment has
filled part of several reservoirs, and an operator can draw a reservoir down on purpose.

What is not here. AAA's alert levels (desborde, seguridad, observación, ajustes, control) are not published: AAA states no license, and FPR asked it in writing
(HANDOFF). The pop-up links to AAA's page for them.

Output: site/data/reservoirs.geojson. Each point: name, type, municipio, geoid, usgs (the monitoring location id), aaa (true for the 19), level and level_time
(the latest reading at build time; the page replaces them with a live one), recent (daily levels in meters from recent_start, 120 values, null where missing),
and p10, p25, p50, p75, p90 (53 weekly values each, meters).
"""

import json
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

import facilities as fac
import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "reservoirs"
OUT = hs.OUT / "reservoirs.geojson"
OUT_HIST = hs.OUT / "reservoir_history.json"   # the Reservoirs page of the Knowledge Area (reservoirs.html)
API = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
FT = 0.3048
YEARS = (2011, 2025)   # the years the usual level is taken from
MIN_YEARS = 8          # a week needs this many years with a value
RECENT = 120           # days of daily values published in the map layer
HIST_DAYS = 400        # days of daily values in the history file
FIRST = "1985-01-01"   # the history file reaches back to the first daily value USGS has (1987 or later)
STALE_DAYS = 30        # a reservoir whose latest reading is older is left out
log = hs.log

# The 19 reservoirs of AAA's daily report, by USGS monitoring location, with the name AAA and the press use (matched by level on 2026-11-02)
AAA = {
    "USGS-50059000": "Carraízo (Lago Loíza)", "USGS-50045000": "La Plata", "USGS-50047550": "Cidra", "USGS-50111210": "Toa Vaca",
    "USGS-50076800": "Río Blanco (Lago Blanco)", "USGS-50071225": "Fajardo", "USGS-50039995": "Carite", "USGS-50093045": "Patillas",
    "USGS-50032290": "Guineo", "USGS-50032590": "Matrullas", "USGS-50111300": "Guayabal", "USGS-50020100": "Garzas", "USGS-50141500": "Guayo",
    "USGS-50125780": "Lucchetti", "USGS-50128900": "Loco", "USGS-50027100": "Dos Bocas", "USGS-50026140": "Caonillas", "USGS-50010800": "Guajataca",
    "USGS-50113950": "Cerrillos",
}
# the other reservoirs' names as USGS writes them in capitals, with their accents
ACCENTS = {"Daguey": "Dagüey", "Portugues": "Portugués"}


def get(path, **params):
    for attempt in range(4):
        try:
            r = requests.get(f"{API}/{path}/items", params={"f": "json", **params}, headers=UA, timeout=(30, 180))
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"reservoirs: {path} failed: {e}")
            time.sleep(3 * (attempt + 1))


DAILY_LIMIT = 10000   # daily values a page; fetch_daily follows the next links (1985-2010 alone is about 9,500 days)


def fetch_daily(site_id, span):
    """The daily values (72375) of one gauge in span ('first/last'), as {time: value}. The API returns at most DAILY_LIMIT a page and a 'next' link for
    the rest, which is followed, so a long record is never cut off."""
    page = get("daily", monitoring_location_id=site_id, parameter_code="72375", datetime=span, limit=DAILY_LIMIT, properties="time,value", skipGeometry="true")
    feats = list(page["features"])
    while page["features"]:
        nxt = next((l["href"] for l in page.get("links", []) if l.get("rel") == "next"), None)
        if not nxt:
            break
        for attempt in range(4):
            try:
                r = requests.get(nxt, headers=UA, timeout=(30, 180))
                r.raise_for_status()
                page = r.json()
                break
            except requests.RequestException as e:
                if attempt == 3:
                    raise SystemExit(f"reservoirs: {site_id} {span} (next page) failed: {e}")
                time.sleep(3 * (attempt + 1))
        feats += page["features"]
    return {r["properties"]["time"]: r["properties"]["value"] for r in feats}


def short_name(usgs_name):
    """'LAGO DE MATRULLAS AT DAMSITE NEAR OROCOVIS, PR' -> 'Lago de Matrullas'."""
    s = usgs_name.split(",")[0]
    for cut in (" AT ", " NEAR ", " NR ", " ABOVE "):
        s = s.split(cut)[0]
    words = [w.capitalize() if w not in ("DE", "DEL", "LA", "LAS") else w.lower() for w in s.split()]
    return " ".join(ACCENTS.get(w, w) for w in words)


def fetch(refresh=False):
    """The cache: sites.json (the reservoirs, their points and latest readings) and one daily file per reservoir."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sites_p = CACHE / "sites.json"
    if refresh or not sites_p.exists():
        locs = get("monitoring-locations", state_code="72", site_type_code="LK", limit=500)["features"]
        ids = [f["id"] for f in locs]
        latest = []
        for k in range(0, len(ids), 40):
            latest += get("latest-continuous", monitoring_location_id=",".join(ids[k:k + 40]), parameter_code="72376", limit=1000,
                          properties="monitoring_location_id,time,value", skipGeometry="true")["features"]
        last = {f["properties"]["monitoring_location_id"]: f["properties"] for f in latest}
        sites = [{"id": f["id"], "name": f["properties"].get("monitoring_location_name"), "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                  "level": float(last[f["id"]]["value"]), "time": last[f["id"]]["time"]} for f in locs if f["id"] in last and f.get("geometry")]
        sites_p.write_text(json.dumps({"fetched": date.today().isoformat(), "lake_sites": len(locs), "sites": sites}, ensure_ascii=False, indent=1), encoding="utf-8")
    S = json.loads(sites_p.read_text(encoding="utf-8"))
    for s in S["sites"]:
        p = CACHE / f"{s['id']}.json"
        if refresh or not p.exists():
            p.write_text(json.dumps(fetch_daily(s["id"], f"{YEARS[0]}-01-01/{date.today().isoformat()}"), separators=(",", ":")), encoding="utf-8")
        old = CACHE / f"{s['id']}_old.json"   # the years before YEARS[0]: they do not change, so they are read once, even with --refresh
        if not old.exists():
            old.write_text(json.dumps(fetch_daily(s["id"], f"{FIRST}/{YEARS[0] - 1}-12-31"), separators=(",", ":")), encoding="utf-8")
    return S


def week(d):
    return min((d.timetuple().tm_yday - 1) // 7, 52)


def quantile(xs, q):
    """Linear interpolation between order statistics (the same as statistics.quantiles' 'inclusive' method)."""
    xs = sorted(xs)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    return xs[lo] if lo + 1 >= len(xs) else xs[lo] + (xs[lo + 1] - xs[lo]) * (pos - lo)


def normals(daily):
    """p10..p90 of the yearly mean of each week, meters, or None where fewer than MIN_YEARS years have a value."""
    by = {}
    for t, v in daily.items():
        d = date.fromisoformat(t)
        if YEARS[0] <= d.year <= YEARS[1] and v not in (None, ""):
            by.setdefault((week(d), d.year), []).append(float(v) * FT)
    out = {q: [None] * 53 for q in (10, 25, 50, 75, 90)}
    for w in range(53):
        yearly = [statistics.fmean(by[(w, y)]) for y in range(YEARS[0], YEARS[1] + 1) if (w, y) in by]
        if len(yearly) >= MIN_YEARS:
            for q in out:
                out[q][w] = round(quantile(yearly, q / 100), 2)
    return out, len({y for (_, y) in by})


def history(daily, built):
    """One reservoir's history for the Reservoirs page, meters: its range in YEARS (lowest and highest daily value), its record low, the mean of each week
    of the year in each year of YEARS (for the percentile of today's level among the same week's years), its monthly means since its first daily value
    (a month needs 15 days with a value) and its last HIST_DAYS daily values."""
    m = {t: round(float(v) * FT, 3) for t, v in daily.items() if v not in (None, "")}
    ref = [(t, v) for t, v in m.items() if YEARS[0] <= int(t[:4]) <= YEARS[1]]
    lo, hi = min(ref, key=lambda x: x[1]), max(ref, key=lambda x: x[1])
    # The older years can be on another reference (Toa Vaca reported about 30 m, a depth, until 2005) or catch a reservoir still filling (Cerrillos 1991-92):
    # the history starts the year after the last year before YEARS whose median is more than one YEARS range below its low or above its high. After that,
    # a single value more than three ranges below the low or one above the high is a gauge error. Droughts stay (Guineo and Garzas in 1994).
    span = hi[1] - lo[1]
    yearly = {}
    for t, v in m.items():
        yearly.setdefault(int(t[:4]), []).append(v)
    off = [y for y, xs in yearly.items() if y < YEARS[0] and not lo[1] - span <= statistics.median(xs) <= hi[1] + span]
    since = max(off) + 1 if off else min(yearly)
    keep = {t: v for t, v in m.items() if int(t[:4]) >= since and lo[1] - 3 * span <= v <= hi[1] + span}
    dropped = len(m) - len(keep)
    m = keep
    rec = min(m.items(), key=lambda x: (x[1], x[0]))
    by = {}
    for t, v in ref:
        d = date.fromisoformat(t)
        by.setdefault((week(d), d.year), []).append(v)
    wk = [[round(statistics.fmean(by[(w, y)]), 2) if (w, y) in by else None for y in range(YEARS[0], YEARS[1] + 1)] for w in range(53)]
    months = {}
    for t, v in m.items():
        months.setdefault(t[:7], []).append(v)
    first = min(months)
    y, mo = int(first[:4]), int(first[5:7])
    mon = []
    while f"{y}-{mo:02d}" <= built.isoformat()[:7]:
        xs = months.get(f"{y}-{mo:02d}", [])
        mon.append(round(statistics.fmean(xs), 2) if len(xs) >= 15 else None)
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    start = built - timedelta(days=HIST_DAYS - 1)
    day = [m.get((start + timedelta(days=i)).isoformat()) for i in range(HIST_DAYS)]
    return {"lo": round(lo[1], 2), "lo_date": lo[0], "hi": round(hi[1], 2), "hi_date": hi[0], "rec_lo": round(rec[1], 2), "rec_lo_date": rec[0], "dropped": dropped,
            "wk": wk, "m0": first, "mon": mon, "d0": start.isoformat(), "day": [None if v is None else round(v, 2) for v in day]}


def build(refresh=False, check=False):
    S = fetch(refresh) if not check else json.loads((CACHE / "sites.json").read_text(encoding="utf-8"))
    built = date.fromisoformat(S["fetched"])
    M = fac.Munis()
    feats, left_out, hist = [], [], []
    for s in S["sites"]:
        daily = json.loads((CACHE / f"{s['id']}.json").read_text(encoding="utf-8"))
        old_p = CACHE / f"{s['id']}_old.json"
        older = json.loads(old_p.read_text(encoding="utf-8")) if old_p.exists() else {}
        age = (built - date.fromisoformat(s["time"][:10])).days
        norm, years = normals(daily)
        if age > STALE_DAYS or years < MIN_YEARS:
            left_out.append({"usgs": s["id"], "name": short_name(s["name"]), "why": f"latest reading {s['time'][:10]}" if age > STALE_DAYS else f"{years} years of daily values in {YEARS[0]}-{YEARS[1]}"})
            continue
        geoid = M.at(s["lon"], s["lat"])
        start = built - timedelta(days=RECENT - 1)
        recent = [daily.get((start + timedelta(days=i)).isoformat()) for i in range(RECENT)]
        name = AAA.get(s["id"]) or short_name(s["name"])
        feats.append(fac.feature(s["lon"], s["lat"], name, "Reservoir", geoid, M, usgs=s["id"], aaa=s["id"] in AAA,
                                 level=round(s["level"], 2), level_time=s["time"], recent_start=start.isoformat(),
                                 recent=[round(float(v) * FT, 2) if v not in (None, "") else None for v in recent],
                                 **{f"p{q}": norm[q] for q in (10, 25, 50, 75, 90)}))
        hist.append({"usgs": s["id"], "name": name, "aaa": s["id"] in AAA, "municipio": M.name_of[geoid], "geoid": geoid,
                     "level": round(s["level"], 2), "level_time": s["time"], **history({**older, **daily}, built)})
    feats.sort(key=lambda f: (not f["properties"]["aaa"], f["properties"]["name"]))
    missing = sorted(set(AAA) - {f["properties"]["usgs"] for f in feats})
    if missing:
        raise SystemExit(f"reservoirs: AAA reservoirs with no usable gauge: {missing}")
    out = {"type": "FeatureCollection", "source": "usgs_water", "vintage": S["fetched"], "built": S["fetched"],
           "notes": {"reservoirs": len(feats), "aaa_monitored": sum(f["properties"]["aaa"] for f in feats), "lake_sites": S["lake_sites"],
                     "usual_years": f"{YEARS[0]}-{YEARS[1]}", "min_years": MIN_YEARS, "left_out": left_out},
           "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    hist.sort(key=lambda r: (not r["aaa"], r["name"]))
    htext = json.dumps({"source": "usgs_water", "vintage": S["fetched"], "built": S["fetched"], "years": list(YEARS), "unit": "m above local mean sea level", "geo": {"ids": [r["geoid"] for r in hist]},
                        "notes": {"reservoirs": len(hist), "aaa_monitored": sum(r["aaa"] for r in hist), "hist_days": HIST_DAYS,
                                  "wk": f"the mean of each week of the year (week 1 = 1-7 January, week 53 = the last 1 or 2 days) in each year {YEARS[0]}-{YEARS[1]}, null where no value",
                                  "mon": "monthly means from m0, null where a month has fewer than 15 daily values", "dropped": "daily values left out: the years before the last year (before 2011) whose median is more than one 2011-2025 range outside it (another reference, or a reservoir still filling), and single values more than three ranges below the low or one above the high", "day": "daily values from d0, null where missing"},
                        "reservoirs": hist}, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text and OUT_HIST.exists() and OUT_HIST.read_text(encoding="utf-8") == htext
        log(f"reservoirs.geojson and reservoir_history.json {'are' if same else 'are NOT'} what the cache gives")
        return 0 if same else 1
    OUT_HIST.write_text(htext, encoding="utf-8")
    log(f"wrote {OUT_HIST.name}: {len(hist)} reservoirs, {len(htext) // 1024} KB")
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(feats)} reservoirs ({out['notes']['aaa_monitored']} in AAA's report), {len(left_out)} left out, {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
