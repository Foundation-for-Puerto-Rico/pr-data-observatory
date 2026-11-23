"""Rainfall for the PR Data Observatory: one point per USGS rain gauge that is reporting now, its last 120 daily totals and the usual rain of each week of the
year, for the "Rainfall" layer of the 2D map and the 3D view (core/facilities.js draws it; the page asks USGS for the last 24 hours and the last 7 days when the
layer is switched on).

    python rain_gauges.py              # build site/data/rain_gauges.geojson (downloads only what is missing from cache/rain_gauges/)
    python rain_gauges.py --refresh    # download every gauge again
    python rain_gauges.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the USGS Water Data API (https://api.waterdata.usgs.gov/ogcapi/v1/; US government work, public domain), the source of reservoirs.py,
river_gauges.py and groundwater.py.
  latest-continuous     parameter 00045, precipitation, inches: every gauge inside Puerto Rico's box that has a reading, and its point
  monitoring-locations  the name USGS gives each of those sites. Some are rain gauges of their own; many are the rain gauge of a river or reservoir station.
  daily                 parameter 00045, statistic 00006 (the sum of the day), one value a day: the history
Rain is converted to millimetres (x 25.4).

Which gauges. Every site whose precipitation reading is less than 30 days old. A gauge with fewer than 8 years of daily totals in 2011-2025 is drawn too,
without a usual range.

The usual rain of a week. For each gauge and each week of the year, the rain of that week in each year 2011-2025 (the mean of its daily totals times seven; a
week needs six of its days), then the 10th, 25th, 50th, 75th and 90th percentile of those yearly weeks (at least 8 years; otherwise null). The page compares the
rain of the last seven days with them.

What this is not. A gauge measures the rain at one spot: a shower can miss it and flood the next valley. It is not a flood warning or a forecast; the National
Weather Service issues those. USGS marks recent readings provisional, and a gauge can clog or stop reporting in a storm.

Output: site/data/rain_gauges.geojson. Each point: name, type, municipio, geoid, usgs (the monitoring location id), station (the name USGS gives the site, as
written), recent (daily totals in mm from recent_start, 120 values, null where missing), and p10, p25, p50, p75, p90 (53 weekly values each, mm in a week).
"""

import json
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

import facilities as fac
import housing_series as hs
import reservoirs as rv
import river_gauges as rg

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "rain_gauges"
OUT = hs.OUT / "rain_gauges.geojson"
MM = 25.4              # inches to millimetres
PARAM = "00045"        # precipitation, inches
STAT = "00006"         # the sum of the day
BBOX = "-68.0,17.6,-65.1,18.6"   # Puerto Rico with Mona, Vieques and Culebra; a site outside Puerto Rico's municipios is left out
YEARS = rv.YEARS
MIN_YEARS = rv.MIN_YEARS
RECENT = rv.RECENT
STALE_DAYS = rv.STALE_DAYS
log = hs.log
get = rg.get           # a page of the API; waits when USGS says it has had too many requests

# USGS writes site names in capitals without accents and with its own abbreviations
WORDS = {"RAINGAGE": "rain gauge", "AT": "at", "NEAR": "near", "NR": "near", "ABV": "above", "ABOVE": "above", "BLW": "below", "BELOW": "below", "DE": "de", "DEL": "del", "LA": "la",
         "LAS": "las", "LOS": "los", "EL": "el", "Y": "y", "BO.": "Bo.", "BO": "Bo.", "QDA.": "Quebrada", "HWY": "Hwy", "FT": "Ft.", "INTER.": "Interchange", "PR": "PR", "FD": "FD"}
ACCENTS = {**rg.ACCENTS, "Diaz": "Díaz", "Comerio": "Comerío", "Jagueyes": "Jagüeyes", "Canaboncito": "Cañaboncito", "Vaqueria": "Vaquería", "Tibes": "Tibes", "Cayey": "Cayey",
           "Guanica": "Guánica", "Sebastian": "Sebastián"}
ARTICLES = {"LA", "LAS", "LOS", "EL"}
KEEP = {"NSRR", "JUA", "FD", "PR"}   # codes and acronyms, as USGS writes them


def gauge_name(usgs_name):
    """'RIO DE LA PLATA AT COMERIO, PR' -> 'Río de la Plata at Comerío'; 'BO. ANONES RAINGAGE NEAR NARANJITO, PR' -> 'Bo. Anones rain gauge near Naranjito'."""
    s = " ".join(usgs_name.replace(",", ", ").split())
    for end in (", PR", " PR"):
        if s.endswith(end):
            s = s[:-len(end)]
    out, prev = [], ""
    for i, w in enumerate(s.strip(" ,").split()):
        comma = "," if w.endswith(",") else ""
        w = w.rstrip(",")
        if w in KEEP:
            x = w
        elif w in ARTICLES and prev != "DE":   # La Plata, Las Piedras, El Mimo; but Río de la Plata
            x = w.capitalize()
        elif w in WORDS:
            x = WORDS[w]
            x = x[0].upper() + x[1:] if not i else x
        elif w.replace(".", "").isalpha():
            x = ACCENTS.get(w.capitalize(), w.capitalize())
        else:
            x = w
        out.append(x + comma)
        prev = w
    return " ".join(out)


def fetch(refresh=False):
    """The cache: sites.json (the gauges with a recent reading, their points and names) and one file of daily totals per gauge."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sites_p = CACHE / "sites.json"
    if refresh or not sites_p.exists():
        latest = get("latest-continuous", bbox=BBOX, parameter_code=PARAM, limit=10000, properties="monitoring_location_id,time,value,unit_of_measure")["features"]
        last = {f["properties"]["monitoring_location_id"]: f for f in latest if f["properties"].get("value") not in (None, "") and f.get("geometry")}
        bad = sorted({f["properties"].get("unit_of_measure") for f in last.values()} - {"in"})
        if bad:
            raise SystemExit(f"rain_gauges: a rain reading is in {bad}, not inches")
        today = date.today()
        fresh = sorted(k for k, f in last.items() if (today - date.fromisoformat(f["properties"]["time"][:10])).days <= STALE_DAYS)
        names = {}
        for k in range(0, len(fresh), 40):
            for f in get("monitoring-locations", id=",".join(fresh[k:k + 40]), limit=1000, properties="id,monitoring_location_name,site_type_code,state_code", skipGeometry="true")["features"]:
                names[f["id"]] = f["properties"]
        sites = [{"id": k, "name": names[k]["monitoring_location_name"], "site_type": names[k].get("site_type_code"), "lon": last[k]["geometry"]["coordinates"][0],
                  "lat": last[k]["geometry"]["coordinates"][1], "time": last[k]["properties"]["time"]} for k in fresh if k in names and names[k].get("state_code") == "72"]
        sites_p.write_text(json.dumps({"fetched": today.isoformat(), "with_rain": len(last), "stale": len(last) - len(fresh), "sites": sites}, ensure_ascii=False, indent=1), encoding="utf-8")
    S = json.loads(sites_p.read_text(encoding="utf-8"))
    for s in S["sites"]:
        p = CACHE / f"{s['id']}.json"
        if refresh or not p.exists():
            d = get("daily", monitoring_location_id=s["id"], parameter_code=PARAM, statistic_id=STAT, datetime=f"{YEARS[0]}-01-01/{date.today().isoformat()}",
                    limit=10000, properties="time,value", skipGeometry="true")["features"]
            p.write_text(json.dumps({r["properties"]["time"]: r["properties"]["value"] for r in d}, separators=(",", ":")), encoding="utf-8")
    return S


def mm(v):
    """Inches to millimetres, one decimal."""
    return round(float(v) * MM, 1)


def days_in_week(w, year):
    """How many days of the year fall in week w (reservoirs.week): seven, and one or two in the last."""
    n = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    return 7 if w < 52 else n - 364


def normals(daily):
    """p10..p90 of the rain of each week across the years, mm in a week, or None where fewer than MIN_YEARS years have that week; and the years with any value."""
    by = {}
    for t, v in daily.items():
        d = date.fromisoformat(t)
        if YEARS[0] <= d.year <= YEARS[1] and v not in (None, ""):
            by.setdefault((rv.week(d), d.year), []).append(float(v) * MM)
    out = {q: [None] * 53 for q in (10, 25, 50, 75, 90)}
    for w in range(53):
        yearly = [statistics.fmean(by[(w, y)]) * 7 for y in range(YEARS[0], YEARS[1] + 1) if len(by.get((w, y), [])) >= min(6, days_in_week(w, y))]
        if len(yearly) >= MIN_YEARS:
            for q in out:
                out[q][w] = round(rv.quantile(yearly, q / 100), 1)
    return out, len({y for (_, y) in by})


def build(refresh=False, check=False):
    S = fetch(refresh) if not check else json.loads((CACHE / "sites.json").read_text(encoding="utf-8"))
    built = date.fromisoformat(S["fetched"])
    M = fac.Munis()
    feats, left_out, short = [], [], 0
    for s in S["sites"]:
        daily = json.loads((CACHE / f"{s['id']}.json").read_text(encoding="utf-8"))
        norm, years = normals(daily)
        geoid = M.at(s["lon"], s["lat"])
        if geoid is None:
            left_out.append({"usgs": s["id"], "name": gauge_name(s["name"]), "why": "the point is outside every municipio"})
            continue
        short += years < MIN_YEARS
        start = built - timedelta(days=RECENT - 1)
        recent = [daily.get((start + timedelta(days=i)).isoformat()) for i in range(RECENT)]
        feats.append(fac.feature(s["lon"], s["lat"], gauge_name(s["name"]), "Rain gauge", geoid, M, usgs=s["id"], station=s["name"], recent_start=start.isoformat(),
                                 recent=[mm(v) if v not in (None, "") else None for v in recent], **{f"p{q}": norm[q] for q in (10, 25, 50, 75, 90)}))
    feats.sort(key=lambda f: (f["properties"]["municipio"], f["properties"]["name"], f["properties"]["usgs"]))
    if len(feats) < 25:   # 54 on 2026-11-12: fewer than 25 means the API answered with part of the network
        raise SystemExit(f"rain_gauges: only {len(feats)} gauges with a recent reading; not written")
    out = {"type": "FeatureCollection", "source": "usgs_water", "vintage": S["fetched"], "built": S["fetched"],
           "notes": {"gauges": len(feats), "municipios": len({f["properties"]["geoid"] for f in feats}), "sites_with_rain_readings": S["with_rain"], "stopped_reporting": S["stale"],
                     "without_a_usual_range": short, "usual_years": f"{YEARS[0]}-{YEARS[1]}", "min_years": MIN_YEARS, "left_out": left_out},
           "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"rain_gauges.geojson {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(feats)} gauges in {out['notes']['municipios']} municipios, {short} without a usual range, {len(left_out)} left out, {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
