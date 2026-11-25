"""Road deaths in Puerto Rico for the PR Data Observatory: fatal crashes and the people killed in them, by municipio and year, from NHTSA's Fatality
Analysis Reporting System (FARS). Counts only: no crash is drawn, and no date, time or place of a death is published.

    python crashes.py            # download the yearly files missing from cache/crashes/ and build the file below
    python crashes.py --refresh  # download every year again (NHTSA revises a year when it publishes its final file)
    python crashes.py --check    # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

Writes site/data/crashes_series.json (the shape of economy_series.json): for the 78 municipios and Puerto Rico, every year with a municipio in the
files (2020 on), fatal crashes, people killed, pedestrians and bicyclists killed, motorcyclists killed, and the deaths per 100,000 residents over the last
five years and, when traffic_series.json is built (traffic.py), per 100 million vehicle-km. Puerto Rico's yearly totals since 2015 are in its notes, with the deaths of the few crashes whose municipio is not given (county code 72). transit_links.py reads the crash points from the same cache (points()) to count the
deaths along each simulated connection; those counts are published only as five-year totals per connection (docs/road-safety.md, HANDOFF decision 105,
step 3).

The source (no key): US Department of Transportation, National Highway Traffic Safety Administration, FARS, the Puerto Rico files of each year
(static.nhtsa.gov/nhtsa/downloads/FARS/<year>/Puerto Rico/FARS<year>PuertoRicoCSV.zip): accident.csv (one row per fatal crash: COUNTY, FATALS,
LATITUDE, LONGITUD) and person.csv (one row per person: INJ_SEV 4 is a fatal injury; PER_TYP 1 driver, 2 passenger, 5 pedestrian, 6 bicyclist,
7 other cyclist; BODY_TYP 80-89 a motorcycle). US Government work. NHTSA publishes a year first as an Annual Report File and then, about a year later,
as a final file; the newest year here is the first release (the notes say which). The files give the municipio (COUNTY, the county code) from 2020;
before 2020 every crash has the same code, so earlier years are Puerto Rico totals only.

FARS counts deaths within 30 days of a crash on a public road. The Puerto Rico Traffic Safety Commission keeps its own count, which can differ from
FARS's (NHTSA corrects FARS records that the Commission's database does not reflect).
"""
import csv
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "crashes"
OUT = hs.OUT
OUT_SERIES = OUT / "crashes_series.json"
log = hs.log

UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
URL = "https://static.nhtsa.gov/nhtsa/downloads/FARS/{year}/Puerto%20Rico/FARS{year}PuertoRicoCSV.zip"
FIRST = 2015
RATE_YEARS = 5           # the deaths per 100,000 residents are pooled over the last five years
MOTORCYCLE = range(80, 90)
WALK_BIKE = {"5", "6", "7"}
UNPLACED = 72            # COUNTY 72 ("PUERTO RICO"): the municipio is not given; the crash counts in Puerto Rico's total only


def fetch(url):
    for i in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            if i == 3:
                raise SystemExit(f"crashes: {url} failed ({e})")
            log(f"  retry {url} ({e})")


def years(refresh=False):
    """The cached yearly files, downloading the missing ones; a year is added while NHTSA has a file for it."""
    CACHE.mkdir(parents=True, exist_ok=True)
    y, out = FIRST, []
    while True:
        p = CACHE / f"FARS{y}PR.zip"
        if refresh or not p.exists():
            data = fetch(URL.format(year=y))
            if data is None or not data.startswith(b"PK"):   # no file for that year yet (NHTSA answers 404, or a page that is not a zip archive)
                break
            p.write_bytes(data)
            log(f"  downloaded FARS {y} ({len(data) / 1024:,.0f} KB)")
        out.append(y)
        y += 1
    if not out:
        raise SystemExit("crashes: no FARS file for Puerto Rico")
    return out


def cached_years():
    out, y = [], FIRST
    while (CACHE / f"FARS{y}PR.zip").exists() and zipfile.is_zipfile(CACHE / f"FARS{y}PR.zip"):
        out.append(y)
        y += 1
    return out


def table(y, name):
    z = zipfile.ZipFile(CACHE / f"FARS{y}PR.zip")
    member = next((n for n in z.namelist() if n.lower().endswith("/" + name) or n.lower() == name), None)
    if member is None:
        raise SystemExit(f"crashes: FARS {y} has no {name}")
    raw = z.read(member)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return list(csv.DictReader(io.StringIO(text)))


def read_year(y):
    """[{case, county, fatals, lat, lng, walk_bike, moto}] for the year's fatal crashes."""
    acc = table(y, "accident.csv")
    per = table(y, "person.csv")
    killed = {}
    for p in per:
        if p.get("INJ_SEV") != "4":
            continue
        k = killed.setdefault(p["ST_CASE"], {"walk_bike": 0, "moto": 0})
        if p.get("PER_TYP") in WALK_BIKE:
            k["walk_bike"] += 1
        elif p.get("PER_TYP") in ("1", "2") and p.get("BODY_TYP", "").isdigit() and int(p["BODY_TYP"]) in MOTORCYCLE:
            k["moto"] += 1
    out = []
    for a in acc:
        lat, lng = float(a.get("LATITUDE") or 99), float(a.get("LONGITUD") or 999)
        ok = 17.5 < lat < 18.8 and -68 < lng < -65   # 77.7777 not reported, 88.8888 not available, 99.9999 unknown
        k = killed.get(a["ST_CASE"], {"walk_bike": 0, "moto": 0})
        out.append({"case": a["ST_CASE"], "county": int(a["COUNTY"]), "fatals": int(a["FATALS"]), "lat": lat if ok else None, "lng": lng if ok else None, **k})
    return out


def points(refresh=False):
    """The located fatal crashes of the last RATE_YEARS years with a file, for transit_links.py: (first year, last year, [(lng, lat, deaths, walk/bike deaths)])."""
    ys = years(refresh) if refresh or not cached_years() else cached_years()
    last = ys[-1]
    span = [y for y in ys if y > last - RATE_YEARS]
    pts = [(c["lng"], c["lat"], c["fatals"], c["walk_bike"]) for y in span for c in read_year(y) if c["lat"] is not None]
    return span[0], last, pts


def assemble(ys):
    munis = {f["properties"]["GEOID"]: f["properties"] for f in json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]}
    ids = sorted(munis)
    order = ids + ["72"]
    hsj = json.loads((OUT / "housing_series.json").read_text(encoding="utf-8"))
    pop_var = next(v for v in hsj["vars"] if v["key"] == "population")
    pop_at = {g: i for i, g in enumerate(hsj["geo"]["ids"])}
    island, by_year, located, unplaced = {}, {}, {}, {}
    for y in ys:
        cs = read_year(y)
        island[str(y)] = {"crashes": len(cs), "deaths": sum(c["fatals"] for c in cs), "walk_bike": sum(c["walk_bike"] for c in cs), "moto": sum(c["moto"] for c in cs)}
        counties = {c["county"] for c in cs}
        located[y] = sum(1 for c in cs if c["lat"] is not None)
        if len(counties) == 1:
            continue   # before 2020: no municipio in the files
        bad = {c for c in counties if "72%03d" % c not in munis and c != UNPLACED}
        if bad:
            raise SystemExit(f"crashes: FARS {y} has county codes with no municipio: {sorted(bad)}")
        acc = {g: {"crashes": 0, "deaths": 0, "walk_bike": 0, "moto": 0} for g in order}
        unplaced[str(y)] = sum(c["fatals"] for c in cs if c["county"] == UNPLACED)
        for c in cs:
            for g in (("72%03d" % c["county"],) if c["county"] != UNPLACED else ()) + ("72",):
                a = acc[g]
                a["crashes"] += 1
                a["deaths"] += c["fatals"]
                a["walk_bike"] += c["walk_bike"]
                a["moto"] += c["moto"]
        if acc["72"]["deaths"] != island[str(y)]["deaths"] or sum(acc[g]["deaths"] for g in ids) + unplaced[str(y)] != island[str(y)]["deaths"]:
            raise SystemExit(f"crashes: FARS {y}: the municipios do not add up to Puerto Rico")
        by_year[y] = acc
    if not by_year:
        raise SystemExit("crashes: no year with a municipio")
    myears = sorted(by_year)
    last = myears[-1]
    span = [y for y in myears if y > last - RATE_YEARS]
    if len(span) < RATE_YEARS:
        raise SystemExit(f"crashes: {len(span)} years with a municipio for a {RATE_YEARS}-year rate")
    rate = []
    for g in order:
        deaths = sum(by_year[y][g]["deaths"] for y in span)
        people = sum(pop_var["years"][str(y)][pop_at[g]] for y in span)
        rate.append(round(100000 * deaths / people, 1) if people else None)
    tp = OUT / "traffic_series.json"   # deaths per 100 million vehicle-km: the five years of deaths over five years of the newest traffic (traffic.py), when it is built
    per_vkm, traffic_year = None, None
    if tp.exists():
        tj = json.loads(tp.read_text(encoding="utf-8"))
        tv = next(v for v in tj["vars"] if v["key"] == "traffic_vkt")
        traffic_year = str(tj["years"][0])
        t_at = {g: i for i, g in enumerate(tj["geo"]["ids"])}
        per_vkm = []
        for g in order:
            vkt = tv["years"][traffic_year][t_at[g]]
            deaths = sum(by_year[y][g]["deaths"] for y in span)
            per_vkm.append(round(1e8 * deaths / (vkt * 365 * len(span)), 2) if vkt else None)
    ref = f"NHTSA Fatality Analysis Reporting System (FARS), Puerto Rico files {myears[0]}-{last} ({last}: first release, the Annual Report File)"
    span_txt = f"{span[0]}-{span[-1]}"
    V = [
        ("crash_deaths", "People killed in traffic crashes (FARS)", "deaths", "deaths",
         "People who died within 30 days of a crash on a public road in the municipio, as NHTSA's Fatality Analysis Reporting System counts them."),
        ("crash_fatal", "Fatal traffic crashes (FARS)", "crashes", "crashes",
         "Crashes on a public road in the municipio in which at least one person died within 30 days."),
        ("crash_walk_bike", "Pedestrians and bicyclists killed (FARS)", "deaths", "walk_bike",
         "People on foot or on a bicycle (or other pedal cycle) who died in a traffic crash in the municipio."),
        ("crash_moto", "Motorcyclists killed (FARS)", "deaths", "moto",
         "Drivers and passengers of motorcycles who died in a traffic crash in the municipio."),
    ]
    variables = [{"key": k, "group": "Infrastructure · Road safety (NHTSA FARS)", "label": lab, "unit": u, "d": 0, "type": "count", "sources": ["nhtsa_fars"], "ref": ref,
                  "definition": dfn, "family": "crashes", "counted": False, "noPerHU": True,
                  "years": {str(y): [by_year[y][g][f] for g in order] for y in myears}} for k, lab, u, f, dfn in V]
    variables.append({"key": "crash_rate_5y", "group": "Infrastructure · Road safety (NHTSA FARS)", "label": f"Traffic deaths per 100,000 residents, {span_txt} (FARS)",
                      "unit": "per 100,000 residents a year", "d": 1, "type": "ratio", "sources": ["nhtsa_fars", "census_pep"], "ref": ref,
                      "definition": f"The people killed in traffic crashes in the municipio over {span_txt}, divided by the sum of its residents in those years (Census Bureau population estimates), times 100,000: a yearly rate. Five years are pooled because a municipio has few deaths a year.",
                      "family": "crashes", "counted": False, "noPerHU": True, "years": {str(last): rate}})
    if per_vkm:
        variables.append({"key": "crash_per_vkm", "group": "Infrastructure · Road safety (NHTSA FARS)", "label": f"Traffic deaths per 100 million vehicle-km, {span_txt} (FARS, HPMS)",
                          "unit": "deaths per 100 million vehicle-km", "d": 2, "type": "ratio", "sources": ["nhtsa_fars", "fhwa_hpms"], "ref": ref + f"; FHWA HPMS, data year {traffic_year}",
                          "definition": f"The people killed in traffic crashes in the municipio over {span_txt}, divided by the vehicle-kilometers driven on its roads in those years, times 100 million. The vehicle-kilometers are those of HPMS data year {traffic_year} (traffic_series.json), counted for each of the {len(span)} years: a measure of risk per kilometer driven, where the rate per resident is high because much traffic passes through.",
                          "family": "crashes", "counted": False, "noPerHU": True, "years": {str(last): per_vkm}})
    doc = {"years": myears, "geo": {"ids": order, "names": [munis[g]["municipality"] for g in ids] + ["Puerto Rico"]}, "vars": variables,
           "sources": {"nhtsa_fars": {"name": "NHTSA · Fatality Analysis Reporting System (FARS), Puerto Rico files", "url": "https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars",
                                      "license": "US Government work (no US copyright)",
                                      "note": "Every fatal crash on a public road; the observatory publishes counts by municipio and year, never a crash's place, date or time."},
                       **({"fhwa_hpms": {"name": "FHWA · Highway Performance Monitoring System (HPMS), Puerto Rico", "url": "https://www.fhwa.dot.gov/policyinformation/hpms.cfm",
                                         "license": "US Government work (no US copyright)", "note": f"Daily vehicle-kilometers of data year {traffic_year} (traffic_series.json), for the deaths per vehicle-km."}} if per_vkm else {}),
                       "census_pep": {"name": "US Census Bureau · Population Estimates Program", "url": "https://www.census.gov/programs-surveys/popest.html",
                                      "license": "US Government work (no US copyright)", "note": "Residents of each municipio each year, for the rate (housing_series.json)."}},
           "notes": {"first_release": last, "traffic_year": int(traffic_year) if traffic_year else None, "rate_years": [span[0], span[-1]], "island": island, "municipio_not_given": unplaced, "located_pct": {str(y): round(100 * located[y] / island[str(y)]["crashes"], 1) for y in ys},
                     "what": "Counts only. NHTSA's Puerto Rico files name the municipio from 2020; island totals since 2015 are in 'island'. The newest year is NHTSA's first release and can change when the final file comes out."}}
    return doc


def build(refresh=False, check=False):
    if check:
        ys = cached_years()
        if not ys:
            print("crashes: nothing cached in cache/crashes/: run python crashes.py first")
            return 1
    else:
        ys = years(refresh)
    doc = assemble(ys)
    n, last = doc["notes"], doc["years"][-1]
    log(f"crashes: FARS {ys[0]}-{ys[-1]} (municipios {doc['years'][0]}-{last}); {last}: {n['island'][str(last)]['deaths']} deaths in {n['island'][str(last)]['crashes']} crashes; "
        f"rate {n['rate_years'][0]}-{n['rate_years'][1]} Puerto Rico {doc['vars'][-1]['years'][str(last)][-1]} per 100,000")
    if check:
        old = json.loads(OUT_SERIES.read_text(encoding="utf-8")) if OUT_SERIES.exists() else None
        same = old is not None and {**old, "built": None} == {**json.loads(json.dumps(doc, ensure_ascii=False)), "built": None}
        print(f"{OUT_SERIES.name} {'matches the cache' if same else 'is not what the cache gives: run python crashes.py'}")
        return 0 if same else 1
    OUT_SERIES.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    log(f"wrote {OUT_SERIES.name}: {OUT_SERIES.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
