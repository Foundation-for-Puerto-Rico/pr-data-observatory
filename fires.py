"""Vegetation fire detections from satellite for the PR Data Observatory, by municipio: how many hot spots NASA's FIRMS records each year, per 100 km² of land,
and in the last 12 months. Step C of the GeoAI sources plan (docs/geoai-sources-proposal-2026-11.md, HANDOFF decision 91; method in docs/fires.md).

    python fires.py             # build site/data/fires_series.json from cache/fires/ (downloads missing yearly files; the last 12 months need FIRMS_MAP_KEY)
    python fires.py --refresh   # download the newest yearly file again and, with FIRMS_MAP_KEY, the last 12 months
    python fires.py --check     # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

The source. NASA FIRMS (Fire Information for Resource Management System), active fire detections from the VIIRS instrument (375 m) on NOAA-20, one satellite
for every year so the years compare (Suomi NPP stopped sending FIRMS data on 2026-11-02; NOAA-21 has no Puerto Rico yearly files yet). Two parts:
  - Complete years: FIRMS's yearly country files (data/country/viirs-jpss1/<year>/viirs-jpss1_<year>_Puerto_Rico.csv), standard processing, public, no key.
    They tag each detection with a type: 0 presumed vegetation fire, 1 volcano, 2 other static land source (industry, a power plant), 3 offshore.
  - The last 12 months: the FIRMS area API for the Puerto Rico box (-67.95,17.85,-65.2,18.55), standard processing (VIIRS_NOAA20_SP) where it reaches and near
    real time (VIIRS_NOAA20_NRT) after, in 5-day windows. It needs a free MAP_KEY, read only from the FIRMS_MAP_KEY environment variable (a GitHub Actions
    secret; .github/workflows/fires.yml). Near-real-time rows have no type, so a detection within 400 m of a place the yearly files tag as a static land
    source is left out.
Licence: NASA open data, no restriction; credit "NASA FIRMS" (LANCE).

How it is made (docs/fires.md):
  - A detection counts when its type is 0 (or, for the last 12 months, it is not near a static source) and its confidence is nominal or high (low is left out).
  - A detection belongs to the municipio of the barrio whose outline holds its point (the pixel's centre), or the nearest barrio within about 500 m; farther
    ones (at sea) are left out.
  - Per 100 km² of land uses the Census land area.
  - Checks that stop the build: each complete year between 50 and 2,000 detections in Puerto Rico, and more than half of all detections in the dry south and
    southwest (the municipios of SOUTH), where grass fires are known to burn most.
A detection is a hot pixel, not a fire: one fire seen on two passes counts twice, and a small fire under the satellite's threshold, or under clouds, is not seen.
Points are not published; the file holds counts by municipio.
"""

import csv
import io
import json
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "fires"
OUT = hs.OUT
OUT_SERIES = OUT / "fires_series.json"
log = hs.log

KEY_VAR = "FIRMS_MAP_KEY"
COUNTRY = "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-jpss1/{y}/viirs-jpss1_{y}_Puerto_Rico.csv"
API = "https://firms.modaps.eosdis.nasa.gov/api"
BBOX = "-67.95,17.85,-65.2,18.55"
FIRST_YEAR = 2019            # NOAA-20's first complete year (its files start 2018-04-01)
NEAR_DEG = 0.005             # about 500 m: a detection on the shore goes to the nearest barrio within this
STATIC_DEG = 0.004           # about 400 m: a near-real-time detection this close to a static land source is left out
WINDOW = 5                   # days per API request (FIRMS accepts 1 to 5)
KEEP_CONF = {"n", "h", "nominal", "high"}
SOUTH = ["72023", "72043", "72055", "72057", "72059", "72075", "72079", "72109", "72111", "72113", "72123", "72133", "72149", "72153", "72015", "72125", "72067", "72121", "72095"]   # Cabo Rojo, Coamo, Guánica, Guayama, Guayanilla, Juana Díaz, Lajas, Patillas, Peñuelas, Ponce, Salinas, Santa Isabel, Villalba, Yauco, Arroyo, San Germán, Hormigueros, Sabana Grande, Maunabo
MIN_YEAR_N, MAX_YEAR_N = 50, 2000
UA = {"User-Agent": "PR-Data-Observatory/1.0 (Foundation for Puerto Rico)"}


def get(url, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def year_file(y, refresh=False, offline=False):
    """The cached yearly country file for year y (downloaded when missing, or again with refresh); None when FIRMS has none."""
    p = CACHE / f"viirs-jpss1_{y}_Puerto_Rico.csv"
    if p.exists() and not refresh:
        return p
    if offline:
        return p if p.exists() else None
    r = get(COUNTRY.format(y=y))
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if not r.text.startswith("latitude,"):
        raise SystemExit(f"fires: the FIRMS file for {y} is not a detection table (starts {r.text[:60]!r})")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(r.text, encoding="utf-8", newline="")
    return p


def rows(p):
    return list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))))


def complete_years(today, refresh=False, offline=False):
    """{year: rows} for every complete year from FIRST_YEAR that FIRMS has a yearly file for. The newest is downloaded again with refresh."""
    out = {}
    for y in range(FIRST_YEAR, today.year):
        p = year_file(y, refresh=refresh and y == today.year - 1, offline=offline)
        if p is None:
            continue
        out[y] = rows(p)
    return out


def last12(today, refresh=False, offline=False):
    """(rows, (first, last) dates, sources) of the last 12 months from the API, cached as cache/fires/last12_<end>.csv; None without key and cache."""
    cached = sorted(CACHE.glob("last12_*.csv"))
    key = os.environ.get(KEY_VAR, "").strip()
    if offline or not key or (cached and not refresh):
        if not cached:
            if not key and not offline:
                log(f"  no {KEY_VAR} and no cached last 12 months: that dataset is left out of this build")
            return None
        p = cached[-1]
        meta = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
        return rows(p), (meta["first"], meta["last"]), meta["sources"]
    avail = get(f"{API}/data_availability/csv/{key}/ALL")
    if avail.status_code != 200 or "data_id" not in avail.text:
        raise SystemExit(f"fires: FIRMS did not answer the data availability request (HTTP {avail.status_code}); check the {KEY_VAR} secret")
    sp_max = None
    for r in csv.DictReader(io.StringIO(avail.text)):
        if r.get("data_id") == "VIIRS_NOAA20_SP":
            sp_max = date.fromisoformat(r["max_date"])
    end = today - timedelta(days=1)
    start = end - timedelta(days=364)
    got, used = {}, Counter()
    d = start
    while d <= end:
        span = min(WINDOW, (end - d).days + 1)
        last = d + timedelta(days=span - 1)
        srcs = (["VIIRS_NOAA20_SP"] if sp_max and last <= sp_max else []) + (["VIIRS_NOAA20_NRT"] if not sp_max or last > sp_max else [])
        if sp_max and d <= sp_max < last:
            srcs = ["VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"]
        for s in srcs:
            r = get(f"{API}/area/csv/{key}/{s}/{BBOX}/{span}/{d.isoformat()}")
            if r.status_code != 200 or not r.text.startswith("latitude,"):
                raise SystemExit(f"fires: FIRMS answered HTTP {r.status_code} for {s} from {d} ({r.text[:80]!r})")
            for x in csv.DictReader(io.StringIO(r.text)):
                k = (x["latitude"], x["longitude"], x["acq_date"], x["acq_time"])
                if k not in got:
                    x["source"] = s
                    got[k] = x
                    used[s] += 1
        d = last + timedelta(days=1)
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"last12_{end.isoformat()}.csv"
    cols = ["latitude", "longitude", "acq_date", "acq_time", "confidence", "frp", "daynight", "source"]
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(got.values(), key=lambda x: (x["acq_date"], x["acq_time"], x["latitude"], x["longitude"])))
    meta = {"first": start.isoformat(), "last": end.isoformat(), "sources": dict(used), "sp_max": sp_max.isoformat() if sp_max else None}
    p.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    for old in cached:
        if old != p:
            old.unlink(missing_ok=True)
            old.with_suffix(".json").unlink(missing_ok=True)
    log(f"  last 12 months {start} to {end}: {len(got)} detections ({dict(used)})")
    return rows(p), (meta["first"], meta["last"]), meta["sources"]


def place(B, lon, lat):
    """Barrio index of each point, or -1 (buildings.place with a wider reach for a 375 m pixel)."""
    import buildings
    old = buildings.NEAR_DEG
    buildings.NEAR_DEG = NEAR_DEG
    try:
        return buildings.place(B, lon, lat)
    finally:
        buildings.NEAR_DEG = old


def counts_by_muni(B, rs, mids):
    """(Counter of municipio ids, left out at sea) for detection rows."""
    import numpy as np
    if not rs:
        return Counter(), 0
    lon = np.array([float(r["longitude"]) for r in rs])
    lat = np.array([float(r["latitude"]) for r in rs])
    bi = place(B, lon, lat)
    c = Counter(B.ids[i][:5] for i in bi if i >= 0)
    return c, int((bi < 0).sum())


def keep_archive(r):
    return r.get("type") == "0" and (r.get("confidence") or "").lower() in KEEP_CONF


def compute(refresh=False, offline=False, today=None):
    import numpy as np
    import conditions
    today = today or date.today()
    B = conditions.Barrios()
    mids, names = B.mids, B.names
    land = {m: B.unit[m]["km2"] for m in mids}
    land_pr = sum(land.values())
    yrs = complete_years(today, refresh, offline)
    if not yrs:
        raise SystemExit("fires: no yearly FIRMS file for Puerto Rico (cache/fires/ is empty and FIRMS did not answer)")
    static = [(float(r["longitude"]), float(r["latitude"])) for rs in yrs.values() for r in rs if r.get("type") == "2"]
    per_year, sea, kept_all, month = {}, 0, Counter(), Counter()
    for y, rs in sorted(yrs.items()):
        k = [r for r in rs if keep_archive(r)]
        c, s = counts_by_muni(B, k, mids)
        per_year[y] = c
        sea += s
        kept_all.update(c)
        month.update(int(r["acq_date"][5:7]) for r in k)
    l12 = last12(today, refresh, offline)
    c12 = None
    if l12:
        rs, (f12, t12), src12 = l12
        sx = np.array([p[0] for p in static]) if static else np.zeros(0)
        sy = np.array([p[1] for p in static]) if static else np.zeros(0)

        def near_static(r):
            if not len(sx):
                return False
            return bool(((sx - float(r["longitude"])) ** 2 + (sy - float(r["latitude"])) ** 2 <= STATIC_DEG ** 2).any())
        k12 = [r for r in rs if (r.get("confidence") or "").lower() in KEEP_CONF and not near_static(r)]
        c12, _ = counts_by_muni(B, k12, mids)
    bad = []
    tot = {y: sum(c.values()) for y, c in per_year.items()}
    for y, n in tot.items():
        if not MIN_YEAR_N <= n <= MAX_YEAR_N:
            bad.append(f"{y}: {n} detections in Puerto Rico (expected {MIN_YEAR_N} to {MAX_YEAR_N})")
    south = sum(kept_all[m] for m in SOUTH) / max(1, sum(kept_all.values()))
    if south <= 0.5:
        bad.append(f"only {south:.0%} of the detections in the dry south and southwest (expected more than half)")
    if bad:
        raise SystemExit("fires: the counts fail their checks:\n  " + "\n  ".join(bad))
    top = sorted(((kept_all[m], names[i]) for i, m in enumerate(mids)), reverse=True)[:5]
    log(f"  {min(yrs)}-{max(yrs)}: {tot}; {south:.0%} in the south and southwest; most: {top}" + (f"; last 12 months {sum(c12.values())}" if c12 is not None else ""))

    G = "Environment · Fires (NASA FIRMS)"
    REF = (f"NASA FIRMS active fire detections, VIIRS 375 m on NOAA-20: yearly country files for Puerto Rico ({min(yrs)}-{max(yrs)}, standard processing, type 0, "
           "confidence nominal or high)" + (f"; the area API for {l12[1][0]} to {l12[1][1]} (VIIRS_NOAA20_SP and _NRT)" if l12 else "") + ". Credit: NASA FIRMS")
    WHAT = ("A detection is a 375 m pixel that held one or more fires when NOAA-20 passed (about 1:30 in the afternoon and at night), as NASA FIRMS records it; "
            "only those FIRMS tags as presumed vegetation fires, with nominal or high confidence. One fire seen on two passes counts twice; a small fire, or one "
            "under clouds, is not seen. A detection belongs to the municipio that holds its pixel's centre. Mostly grass and brush fires, most of them in the dry "
            "south in the first months of the year.")
    ys = sorted(yrs)
    Y = [str(y) for y in ys]

    def yearly(fn):
        return {str(y): [fn(per_year[y].get(m, 0), land[m]) for m in mids] + [fn(sum(per_year[y].values()), land_pr)] for y in ys}
    vs = [{"key": "fire_n", "group": G, "label": "Vegetation fire detections from satellite (NASA FIRMS)", "unit": "", "d": 0, "type": "count",
           "sources": ["nasa_firms", "census_tiger"], "ref": REF, "definition": "The number of satellite fire detections in the area in the year. " + WHAT,
           "family": "fires", "counted": False, "noPerHU": True, "classes": "jenks", "years": yearly(lambda n, a: n)},
          {"key": "fire_per100km2", "group": G, "label": "Vegetation fire detections per 100 km² of land (NASA FIRMS)", "unit": "", "d": 1, "type": "rate",
           "sources": ["nasa_firms", "census_tiger"], "ref": REF, "definition": "Satellite fire detections in the year per 100 km² of the area's land (Census land area); what a detection is: see the count.",
           "family": "fires", "counted": False, "noPerHU": True, "years": yearly(lambda n, a: round(n / a * 100, 1) if a else None)}]
    if c12 is not None:
        t12 = l12[1][1]
        vs.append({"key": "fire_n_12m", "group": G, "label": "Vegetation fire detections, last 12 months (NASA FIRMS)", "unit": "", "d": 0, "type": "count",
                   "sources": ["nasa_firms", "census_tiger"], "ref": REF,
                   "definition": (f"The number of satellite fire detections in the area from {l12[1][0]} to {t12}, from FIRMS's area service (standard processing where "
                                  "it reaches, near real time after). Near-real-time detections carry no type, so a detection within 400 m of a place the yearly files "
                                  "mark as a static land source (industry, a power plant) is left out; what a detection is: see the yearly count."),
                   "family": "fires", "counted": False, "noPerHU": True, "classes": "jenks", "tag": "near real time",
                   "years": {t12[:4]: [c12.get(m, 0) for m in mids] + [sum(c12.values())]}})
    SOURCES = {"nasa_firms": {"name": "NASA FIRMS — VIIRS 375 m active fire detections (NOAA-20)", "url": "https://firms.modaps.eosdis.nasa.gov/",
                              "license": "NASA open data, no restriction; credit NASA FIRMS (LANCE)",
                              "note": "Yearly country files (public, no key) and, for the last 12 months, the area API with FPR's MAP_KEY (a GitHub Actions secret)."},
               "census_tiger": {"name": "US Census Bureau — municipio and barrio outlines and land area (TIGER/Line)",
                                "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html", "license": "US Government work (no US copyright)",
                                "note": "Barrio outlines (to place each detection) and municipio land area, from the observatory's crosswalk."}}
    notes = {"satellite": "NOAA-20 (VIIRS)", "years": ys, "per_year_pr": {str(y): tot[y] for y in ys}, "by_month_pr_all_years": {str(m): month.get(m, 0) for m in range(1, 13)},
             "south_share": round(south, 3), "left_out_at_sea": sea, "static_sources_seen": len(static),
             "last_12_months": ({"first": l12[1][0], "last": l12[1][1], "sources": l12[2], "pr": sum(c12.values())} if l12 else None),
             "filters": {"type": "0 (presumed vegetation fire)", "confidence": "nominal or high", "near_static_deg": STATIC_DEG}}
    as_of = l12[1][1][:7] if l12 else str(max(ys))
    return {"as_of": as_of, "years": ys, "geo": {"ids": mids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    from datetime import date as _d
    series = compute(refresh, offline=check)
    if check:
        old = json.loads(OUT_SERIES.read_text(encoding="utf-8")) if OUT_SERIES.exists() else None
        if old is None or {**old, "built": None} != {**json.loads(json.dumps(series, ensure_ascii=False)), "built": None}:
            print(f"{OUT_SERIES.name} is not what the cache gives: run python fires.py")
            return 1
        print(f"{OUT_SERIES.name} matches the cache")
        return 0
    OUT_SERIES.write_text(json.dumps({"built": _d.today().isoformat(), **series}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"wrote {OUT_SERIES.name}: {len(series['vars'])} variables, {OUT_SERIES.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
