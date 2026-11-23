"""Time dimensions for the PR Data Observatory 3D view.

  hurricanes.json   every Atlantic tropical cyclone since 1851 that passed within 250 km of Puerto
                    Rico, from NOAA NHC HURDAT2 (public domain), with 6-hourly track points
  population_2010   per-municipality 2010 Census population (TIGERweb) for 2010 -> 2020 change
"""

import json
import re
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import requests

HURDAT2_INDEX = "https://www.nhc.noaa.gov/data/hurdat/"
HURDAT2_FALLBACK = "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt"
CENSUS2010_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2010/MapServer/100"
PR_CENTER = (18.22, -66.45)
NEAR_KM = 250
UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"

SOURCES = {
    "hurdat2": {
        "name": "NOAA National Hurricane Center — HURDAT2 Atlantic best-track database (1851–{last_year})",
        "url": "https://www.nhc.noaa.gov/data/#hurdat",
        "license": "US Government work — public domain",
        "credit": "Hurricane tracks: NOAA NHC HURDAT2",
    },
    "census2010": {
        "name": "US Census Bureau — TIGERweb, 2010 Census counties",
        "url": CENSUS2010_URL,
        "license": "US Government work (no US copyright)",
        "credit": "2010 population: US Census Bureau",
    },
}

def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    d = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * atan2(sqrt(d), sqrt(1 - d))


def latest_hurdat2_url():
    """NHC publishes a new file name every year (hurdat2-1851-YYYY-MMDDYY.txt); find the newest."""
    try:
        r = requests.get(HURDAT2_INDEX, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        names = re.findall(r'href="(hurdat2-1851-(\d{4})-(\d{6})\.txt)"', r.text)
        if names:
            # newest by last year, then by the MMDDYY stamp read as YYMMDD
            best = max(names, key=lambda n: (int(n[1]), n[2][4:] + n[2][:4]))
            return HURDAT2_INDEX + best[0]
    except requests.RequestException as e:
        print(f"  could not list {HURDAT2_INDEX} ({e}); using the last known file")
    return HURDAT2_FALLBACK


def load_hurricanes(cache: Path, refresh: bool):
    """HURDAT2 storms passing within NEAR_KM of Puerto Rico."""
    print("Hurricane tracks (NOAA HURDAT2)")
    path = cache / "hurdat2.txt"
    if not path.exists() or refresh:
        url = latest_hurdat2_url()
        print(f"  downloading {url}")
        r = requests.get(url, headers={"User-Agent": UA}, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    storms, cur = [], None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if line[:2] == "AL" and len(parts) >= 3 and parts[2].isdigit():
            cur = {"id": parts[0], "name": parts[1].title(), "year": int(parts[0][4:8]), "track": []}
            storms.append(cur)
            continue
        if cur is None or len(parts) < 7:
            continue
        try:
            lat = float(parts[4][:-1]) * (-1 if parts[4].endswith("S") else 1)
            lon = float(parts[5][:-1]) * (-1 if parts[5].endswith("W") else 1)
            wind = int(parts[6]) if parts[6] not in ("", "-999") else None
        except ValueError:
            continue
        cur["track"].append([round(lon, 2), round(lat, 2), parts[0] + parts[1].zfill(4), wind, parts[3]])
    near = []
    for s in storms:
        if not s["track"]:
            continue
        dmin = min(haversine_km((p[1], p[0]), PR_CENTER) for p in s["track"])
        if dmin > NEAR_KM:
            continue
        winds = [p[3] for p in s["track"] if p[3]]
        wmax = max(winds) if winds else None
        # Saffir-Simpson category from peak wind (kt) while near PR
        near_pts = [p for p in s["track"] if haversine_km((p[1], p[0]), PR_CENTER) <= NEAR_KM and p[3]]
        wnear = max((p[3] for p in near_pts), default=None)
        cat = None if wnear is None else 5 if wnear >= 137 else 4 if wnear >= 113 else 3 if wnear >= 96 else 2 if wnear >= 83 else 1 if wnear >= 64 else 0
        near.append({**s, "max_wind": wmax, "wind_near_pr": wnear, "cat_near_pr": cat, "min_dist_km": round(dmin)})
    near.sort(key=lambda s: s["track"][0][2])
    print(f"  {len(storms):,} Atlantic storms, {len(near):,} within {NEAR_KM} km of PR; "
          f"{sum(1 for s in near if (s['cat_near_pr'] or 0) >= 3)} major hurricanes near PR")
    last = max((s["year"] for s in storms), default=None)
    SOURCES["hurdat2"]["name"] = SOURCES["hurdat2"]["name"].format(last_year=last)
    return near


def load_population_2010(cache: Path, refresh: bool):
    print("Census 2010 population")
    path = cache / "tiger_pr_counties_2010.json"
    if not path.exists() or refresh:
        r = requests.get(f"{CENSUS2010_URL}/query", params={"where": "STATE='72'", "outFields": "NAME,GEOID,POP100,HU100", "returnGeometry": "false", "f": "json"}, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_text(r.text, encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {f["attributes"]["GEOID"]: {"population_2010": int(f["attributes"].get("POP100") or 0), "housing_units_2010": int(f["attributes"].get("HU100") or 0)} for f in data.get("features", [])}
    print(f"  {len(out)} municipalities")
    return out
