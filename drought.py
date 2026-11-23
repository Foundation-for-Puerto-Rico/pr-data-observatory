"""Drought by municipio and year, from the weekly US Drought Monitor. HANDOFF decision 107, step 5 (first part); docs/drought.md.

    python drought.py              # build site/data/drought_series.json from the cache
    python drought.py --refresh    # download every week again for the 78 municipios and Puerto Rico (79 requests)
    python drought.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: the US Drought Monitor's data service (usdmdataservices.unl.edu), one request a municipio. Every Tuesday map since January 4, 2000
gives the share of each municipio's area in each drought class, cumulative: d0 is the share in D0 (abnormally dry) or worse, d1 in D1 (moderate
drought) or worse, d2 in D2 (severe) or worse, d3 in D3 (extreme) or worse, d4 in D4 (exceptional). The map is drawn by the authors each week from
rainfall, soil moisture, stream flow, reservoirs and reports; it is an expert judgement, not a measurement.
Credit as the Drought Monitor asks (droughtmonitor.unl.edu/About/Permission.aspx): "Data courtesy of NDMC, via https://droughtmonitor.unl.edu".

Output: drought_series.json (the shape of nightlights_series.json: yearly values for the 78 municipios and Puerto Rico, which is the last value).
The current year holds the weeks published so far; notes.latest gives the newest week's shares.
"""

import collections
import datetime
import json
import sys
import time
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "drought"
OUT = hs.OUT / "drought_series.json"
log = hs.log
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)", "Accept": "application/json"}

BASE = "https://usdmdataservices.unl.edu/api/{kind}/GetDroughtSeverityStatisticsByAreaPercent"
FIRST = 2000
HALF = 50.0   # a week counts when drought covers at least half the municipio's area

G = "Hazards · Drought (US Drought Monitor)"
CREDIT = "Data courtesy of NDMC, via https://droughtmonitor.unl.edu"
SOURCES = {
    "usdm": {"name": "US Drought Monitor (National Drought Mitigation Center, USDA, NOAA)", "url": "https://droughtmonitor.unl.edu/",
             "license": "Free to use with credit: " + CREDIT,
             "note": "A weekly map of drought drawn by experts from rainfall, soil moisture, stream flow and reports; the share of each municipio in each class."},
}


def fetch(geoid, refresh):
    """Every week since FIRST for one municipio (geoid) or for Puerto Rico ('72'), newest first as the service gives them."""
    p = CACHE / f"{geoid}.json"
    if refresh or not p.exists():
        kind, aoi = ("StateStatistics", "72") if geoid == "72" else ("CountyStatistics", geoid)
        end = datetime.date.today()
        r = requests.get(BASE.format(kind=kind), params={"aoi": aoi, "startdate": f"1/1/{FIRST}", "enddate": f"{end.month}/{end.day}/{end.year}",
                                                         "statisticsType": 1}, headers=UA, timeout=180)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            raise SystemExit(f"drought: the Drought Monitor gave no weeks for {geoid}")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
        time.sleep(1)
    return json.loads(p.read_text(encoding="utf-8"))


def by_year(rows):
    """{year: [(map date, d1, d2, d3), ...]} in date order."""
    out = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r["mapDate"]):
        out[int(r["mapDate"][:4])].append((r["mapDate"][:10], r["d1"], r["d2"], r["d3"]))
    return out


def figures(weeks):
    """Yearly figures from one year's weeks: average share in D1 or worse, weeks with D1 or worse on half the area, the same for D2."""
    n = len(weeks)
    return {"area": round(sum(w[1] for w in weeks) / n, 1),
            "weeks": sum(1 for w in weeks if w[1] >= HALF),
            "severe": sum(1 for w in weeks if w[2] >= HALF)}


def documents(rows_by_geo):
    names, fips = hs.municipalities()
    ids = list(fips)
    yr = {g: by_year(rows_by_geo[g]) for g in ids + ["72"]}
    weeks_pr = yr["72"]
    years = sorted(y for y in weeks_pr if y >= FIRST)
    dates = {y: [w[0] for w in weeks_pr[y]] for y in years}
    for g in ids:
        for y in years:
            if [w[0] for w in yr[g].get(y, [])] != dates[y]:
                raise SystemExit(f"drought: {g} {y} has other weeks than Puerto Rico's")
    fig = {g: {y: figures(yr[g][y]) for y in years} for g in ids + ["72"]}

    def series(k):
        return {str(y): [fig[g][y][k] for g in ids] + [fig["72"][y][k]] for y in years}

    last_date = dates[years[-1]][-1]
    partial = f" {years[-1]} holds the weeks published so far (up to the map of {last_date})."
    ref = f"US Drought Monitor, weekly maps {dates[years[0]][0]} to {last_date}. {CREDIT}"
    judge = " The Drought Monitor is drawn each week by experts from rainfall, soil moisture, stream flow, reservoir levels and reports; it is a judgement, not a measurement, and its lines follow no municipio."
    vs = [
        {"key": "drought_area_pct", "group": G, "label": "Area in drought, average of the year (%)", "unit": "%", "d": 1, "type": "rate",
         "sources": ["usdm"], "ref": ref, "family": "drought", "counted": False, "noPerHU": True,
         "definition": "The share of the municipio's area in drought (moderate, D1, or worse) on the US Drought Monitor, averaged over the weeks of the year. 100 means the whole municipio was in drought every week." + judge + partial,
         "years": series("area")},
        {"key": "drought_weeks", "group": G, "label": "Weeks with drought over half the area", "unit": "weeks", "d": 0, "type": "rate",
         "sources": ["usdm"], "ref": ref, "family": "drought", "counted": False, "noPerHU": True,
         "definition": "The weeks of the year in which drought (moderate, D1, or worse) covered at least half of the municipio's area on the US Drought Monitor. A year has 52 or 53 weekly maps." + judge + partial,
         "years": series("weeks")},
        {"key": "drought_severe_weeks", "group": G, "label": "Weeks with severe drought over half the area", "unit": "weeks", "d": 0, "type": "rate",
         "sources": ["usdm"], "ref": ref, "family": "drought", "counted": False, "noPerHU": True,
         "definition": "The weeks of the year in which severe drought (D2) or worse covered at least half of the municipio's area on the US Drought Monitor." + judge + partial,
         "years": series("severe")},
    ]
    newest = {g: next(r for r in rows_by_geo[g] if r["mapDate"][:10] == last_date) for g in ids + ["72"]}
    notes = {"weeks": {str(y): len(dates[y]) for y in years}, "first_week": dates[years[0]][0], "last_week": last_date,
             "half": f"A week counts when the class covers at least {HALF:.0f}% of the municipio's area",
             "classes": "D0 abnormally dry, D1 moderate, D2 severe, D3 extreme, D4 exceptional; the shares are cumulative (D1 or worse)",
             "latest": {"date": last_date, "d1": [newest[g]["d1"] for g in ids] + [newest["72"]["d1"]], "d2": [newest[g]["d2"] for g in ids] + [newest["72"]["d2"]],
                        "d3": [newest[g]["d3"] for g in ids] + [newest["72"]["d3"]]},
             "island_extreme_max": {str(y): max(w[3] for w in weeks_pr[y]) for y in years},
             "credit": CREDIT}
    today = datetime.date.today().isoformat()
    return {"built": today, "as_of": last_date, "years": years, "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]},
            "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    go = refresh and not check
    _, fips = hs.municipalities()
    rows = {g: fetch(g, go) for g in list(fips) + ["72"]}
    if go:
        log(f"  downloaded the Drought Monitor weeks for {len(rows)} areas")
    doc = documents(rows)
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        same = old is not None and {**old, "built": None} == {**json.loads(text), "built": None}
        print(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB), weeks {doc['notes']['first_week']} to {doc['notes']['last_week']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
