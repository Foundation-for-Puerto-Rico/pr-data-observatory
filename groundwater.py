"""Groundwater levels for the PR Data Observatory: one point per well with a live USGS gauge, its last 120 days and the usual depth to water for each week of
the year, for the "Groundwater levels" layer of the 2D map and the 3D view (core/facilities.js draws it; the page asks USGS for the latest reading when the layer
is switched on).

    python groundwater.py              # build site/data/groundwater.geojson (downloads only what is missing from cache/groundwater/)
    python groundwater.py --refresh    # download every well again
    python groundwater.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the USGS Water Data API (https://api.waterdata.usgs.gov/ogcapi/v1/; US government work, public domain), the source of reservoirs.py and
river_gauges.py.
  monitoring-locations  the wells of Puerto Rico (site_type_code GW), their points and the depth of each well
  latest-continuous     parameter 72019, depth to water level (how far below the ground the water stands in the well), feet: the latest reading
  daily                 parameter 72019, one value a day: the history. USGS keeps one daily statistic per well (the mean of the day, or the reading at noon);
                        the build takes the mean where the well has it and otherwise the statistic with the most days.
Depths are converted to meters (x 0.3048).

Which wells. Every well whose reading is less than 30 days old. A well with fewer than 8 years of daily values in 2011-2025 is drawn too, without a usual range.

The usual depth. As reservoirs.py: for each well and each week of the year, the mean of the daily values of that week in each year 2011-2025, then the 10th, 25th,
50th, 75th and 90th percentile of those yearly means (at least 8 years; otherwise null). A larger depth is lower water: the page says "lower than usual for this
time of year" when the depth is above the 90th percentile, "higher" when it is below the 10th.

What this is not. A well shows the water at one point of one aquifer; pumping nearby can lower it within hours, and the next well can read differently. The
layer says nothing about the quality of the water or how much can be pumped. USGS marks recent readings provisional.

Output: site/data/groundwater.geojson. Each point: name, type, municipio, geoid, usgs (the monitoring location id), station (the name USGS gives the well, as
written), depth and depth_time (the latest reading at build time, meters below the ground; the page replaces them with a live one), well_depth (how deep the well
was built, meters, where USGS records it), recent (daily depths in meters from recent_start, 120 values, null where missing), and p10, p25, p50, p75, p90 (53
weekly values each, meters).
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
CACHE = ROOT / "cache" / "groundwater"
OUT = hs.OUT / "groundwater.geojson"
FT = 0.3048            # feet to meters
PARAM = "72019"        # depth to water level, feet below land surface
BBOX = "-68.0,17.6,-65.1,18.6"   # Puerto Rico with Mona, Vieques and Culebra; a well outside the list of Puerto Rico's wells is dropped
STATS = ("00003", "00008", "31200", "32400", "00001", "00002")   # the daily statistic taken, in this order: mean, median, the reading at noon, at midnight, maximum, minimum
YEARS = rv.YEARS       # the years the usual depth is taken from (those of the reservoirs)
MIN_YEARS = rv.MIN_YEARS
RECENT = rv.RECENT
STALE_DAYS = rv.STALE_DAYS
log = hs.log
get = rg.get           # a page of the API; waits when USGS says it has had too many requests

# USGS writes well names in capitals without accents. The words written as ordinary words (the others are the codes of a well and stay as USGS writes them)
SHORT = {"WELL", "WEST", "PARK", "NAVY", "CABO", "ROJO", "LAS", "LOS", "EAST", "RIO"}
CODES = {"JBNERR"}     # longer words that are a code or an acronym
ACCENTS = {**rg.ACCENTS, "Cofresi": "Cofresí", "Sanson": "Sansón", "Cemetary": "Cemetery", "Juncos": "Juncos"}


def well_name(usgs_name):
    """'PASEO LADIS WELL AT VILLA COFRESI, SALINAS, PR' -> 'Paseo Ladis Well at Villa Cofresí'. A code (JUA 5, MW 11, CE-RUM2) stays as USGS writes it."""
    out = []
    for i, w in enumerate(usgs_name.split(",")[0].split()):
        if w in ("AT", "DE", "DEL", "LA", "EL", "Y") and i:
            out.append(w.lower())
        elif w.isalpha() and w not in CODES and (len(w) > 4 or w in SHORT):
            out.append(ACCENTS.get(w.capitalize(), w.capitalize()))
        else:
            out.append(w)
    return " ".join(out)


def fetch(refresh=False):
    """The cache: sites.json (the wells with a recent reading, their points and latest readings) and one daily file per well."""
    CACHE.mkdir(parents=True, exist_ok=True)
    sites_p = CACHE / "sites.json"
    if refresh or not sites_p.exists():
        locs = get("monitoring-locations", state_code="72", site_type_code="GW", limit=10000,
                   properties="id,monitoring_location_name,well_constructed_depth")["features"]
        ids = {f["id"] for f in locs}
        # every latest depth inside Puerto Rico's box, in one request: asking for the 5,000 well sites by name, 40 at a time, meets USGS's limit on requests
        latest = get("latest-continuous", bbox=BBOX, parameter_code=PARAM, limit=10000, properties="monitoring_location_id,time,value,unit_of_measure")["features"]
        last = {f["properties"]["monitoring_location_id"]: f["properties"] for f in latest
                if f["properties"].get("value") not in (None, "") and f["properties"]["monitoring_location_id"] in ids}
        bad = sorted({q.get("unit_of_measure") for q in last.values()} - {"ft"})
        if bad:
            raise SystemExit(f"groundwater: a depth is in {bad}, not feet")
        today = date.today()
        sites = [{"id": f["id"], "name": f["properties"].get("monitoring_location_name"), "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                  "depth": float(last[f["id"]]["value"]), "time": last[f["id"]]["time"], "well_depth": f["properties"].get("well_constructed_depth")}
                 for f in locs if f["id"] in last and f.get("geometry")]
        stale = [s for s in sites if (today - date.fromisoformat(s["time"][:10])).days > STALE_DAYS]
        sites = [s for s in sites if s not in stale]
        sites_p.write_text(json.dumps({"fetched": today.isoformat(), "well_sites": len(locs), "with_depth": len(last), "stale": len(stale), "sites": sites},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    S = json.loads(sites_p.read_text(encoding="utf-8"))
    for s in S["sites"]:
        p = CACHE / f"{s['id']}.json"
        if refresh or not p.exists():
            d = get("daily", monitoring_location_id=s["id"], parameter_code=PARAM, datetime=f"{YEARS[0]}-01-01/{date.today().isoformat()}",
                    limit=10000, properties="time,value,statistic_id", skipGeometry="true")["features"]
            by = {}
            for r in d:
                by.setdefault(r["properties"]["statistic_id"], {})[r["properties"]["time"]] = r["properties"]["value"]
            stat = next((x for x in STATS if x in by), max(by, key=lambda x: len(by[x])) if by else None)
            p.write_text(json.dumps({"statistic": stat, "values": by.get(stat, {})}, separators=(",", ":")), encoding="utf-8")
    return S


def metres(v):
    """Feet to meters, two decimals."""
    return round(float(v) * FT, 2)


def normals(daily):
    """p10..p90 of the yearly mean of each week, meters below the ground, or None where fewer than MIN_YEARS years have a value; and the years with any value."""
    by = {}
    for t, v in daily.items():
        d = date.fromisoformat(t)
        if YEARS[0] <= d.year <= YEARS[1] and v not in (None, ""):
            by.setdefault((rv.week(d), d.year), []).append(float(v) * FT)
    out = {q: [None] * 53 for q in (10, 25, 50, 75, 90)}
    for w in range(53):
        yearly = [statistics.fmean(by[(w, y)]) for y in range(YEARS[0], YEARS[1] + 1) if (w, y) in by]
        if len(yearly) >= MIN_YEARS:
            for q in out:
                out[q][w] = round(rv.quantile(yearly, q / 100), 2)
    return out, len({y for (_, y) in by})


def build(refresh=False, check=False):
    S = fetch(refresh) if not check else json.loads((CACHE / "sites.json").read_text(encoding="utf-8"))
    built = date.fromisoformat(S["fetched"])
    M = fac.Munis()
    feats, left_out, short = [], [], 0
    for s in S["sites"]:
        daily = json.loads((CACHE / f"{s['id']}.json").read_text(encoding="utf-8"))["values"]
        norm, years = normals(daily)
        geoid = M.at(s["lon"], s["lat"])
        if geoid is None:
            left_out.append({"usgs": s["id"], "name": well_name(s["name"]), "why": "the point is outside every municipio"})
            continue
        short += years < MIN_YEARS
        start = built - timedelta(days=RECENT - 1)
        recent = [daily.get((start + timedelta(days=i)).isoformat()) for i in range(RECENT)]
        feats.append(fac.feature(s["lon"], s["lat"], well_name(s["name"]), "Groundwater well", geoid, M, usgs=s["id"], station=s["name"],
                                 depth=metres(s["depth"]), depth_time=s["time"], well_depth=round(float(s["well_depth"]) * FT, 1) if s.get("well_depth") else None,
                                 recent_start=start.isoformat(), recent=[metres(v) if v not in (None, "") else None for v in recent],
                                 **{f"p{q}": norm[q] for q in (10, 25, 50, 75, 90)}))
    feats.sort(key=lambda f: (f["properties"]["municipio"], f["properties"]["name"], f["properties"]["usgs"]))
    if len(feats) < 15:   # 34 on 2026-11-12: fewer than 15 means the API answered with part of the network
        raise SystemExit(f"groundwater: only {len(feats)} wells with a recent reading; not written")
    out = {"type": "FeatureCollection", "source": "usgs_water", "vintage": S["fetched"], "built": S["fetched"],
           "notes": {"wells": len(feats), "municipios": len({f["properties"]["geoid"] for f in feats}), "well_sites": S["well_sites"],
                     "stopped_reporting": S["stale"] + S["well_sites"] - S["with_depth"], "without_a_usual_range": short,
                     "usual_years": f"{YEARS[0]}-{YEARS[1]}", "min_years": MIN_YEARS, "left_out": left_out},
           "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"groundwater.geojson {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(feats)} wells in {out['notes']['municipios']} municipios, {short} without a usual range, {len(left_out)} left out, {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
