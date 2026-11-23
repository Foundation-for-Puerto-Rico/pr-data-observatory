"""Airport and ferry passengers for the PR Data Observatory, for the 78 municipalities and Puerto Rico: how many people board at each gateway, every year.

    python gateway_series.py             # build site/data/gateway_series.json (downloads only what is missing)
    python gateway_series.py --refresh   # download again
    python gateway_series.py --check     # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Three sources, no key, US federal data (public domain):
  BTS T-100 Segment Summary by Origin Airport (data.bts.gov r495-tyji): passengers and departures of commercial flights, by origin airport and month. Seven Puerto
      Rico airports report. A year is published once San Juan (SJU) has all twelve months; a smaller airport with fewer months had no commercial flights in the others.
  FAA Commercial Service Enplanements (one file a calendar year, each with that year and the one before): passengers boarding at each commercial service airport.
      It adds Ceiba (RVR), which is not in T-100, and counts a few more kinds of flight (on-demand air taxi).
  BTS National Census of Ferry Operators (operator segment, segment and terminal files of each census): passengers on each one-way segment, which are the
      passengers boarding at the segment's first terminal. Censuses since 2022 are named for the year of their data (the 2022 file says data_year 2022); the 2020
      census gives data_year 2019. The 2018 census is left out: it does not state its data year and its segments end at Fajardo, before the move to Ceiba.

An airport or a terminal counts in the municipality that holds it: an airport by its FAA code in transport.json (San Juan's SJU is in Carolina), a terminal by its point.
Only counts for each municipality are published: no terminal or airport names, no points.
"""

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import infrastructure_series as inf
import xlsx_lite

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "gateways"
OUT = hs.OUT / "gateway_series.json"
UA = {"User-Agent": "Mozilla/5.0 (pr-digital-twin open-data build; Foundation for Puerto Rico)"}
log = hs.log
SODA = "https://data.bts.gov/resource/{}.json"
T100 = "r495-tyji"
T100_AIRPORTS = ["SJU", "BQN", "PSE", "VQS", "CPX", "SIG", "MAZ"]   # every Puerto Rico airport in T-100 (checked 2026-10-14)
FAA = "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/arp-cy{y}-commercial-service-enplanements.xlsx"
FAA_FIRST = 2024   # the first file under this name; each file holds its year and the one before
NCFO = {2020: ("ggca-ddee", "gn77-pp24", "ca7h-i9yt"), 2022: ("as3z-m8rd", "iyde-f8k7", "ke6h-ga46"), 2024: ("7umd-qc2k", "2ygc-ds4z", "difu-6bgs")}   # census: (operator segments, segments, terminals)
FLOORS = {"sju_passengers": 3_000_000, "ferry_passengers": 800_000}   # SJU had 6.7 million in 2025 (2.4 million in 2020); ferries 1.15 to 1.62 million a census

SOURCES = {
    "bts_t100": {"name": "BTS — T-100 Segment Summary by Origin Airport", "url": "https://data.bts.gov/Aviation/AFF-T100-Segment-Summary-By-Origin-Airport/r495-tyji", "license": "Public Domain U.S. Government",
                 "note": "Passengers and departures of commercial flights from each airport, by month. The observatory adds the months of each full year."},
    "faa_enplanements": {"name": "FAA — Commercial Service Airports, passenger boardings (enplanements)", "url": "https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger", "license": "US federal government data (public domain)",
                         "note": "Passengers boarding at each commercial service airport, by calendar year."},
    "bts_ncfo": {"name": "BTS — National Census of Ferry Operators", "url": "https://www.bts.gov/ncfo", "license": "Public Domain U.S. Government",
                 "note": "Passengers on each ferry segment, every two years. The observatory counts the passengers boarding at each terminal."},
}


def soda(dataset, **params):
    for attempt in range(4):
        try:
            r = requests.get(SODA.format(dataset), params={"$limit": 5000, **params}, headers=UA, timeout=(30, 300))
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"gateway_series: data.bts.gov {dataset} failed: {e}")


def cached(name, fetch, refresh, offline):
    path = CACHE / name
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"gateway_series --check: {name} is not in the cache")
    d = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    return d


# ── Air ──────────────────────────────────────────────────────────────────────

def t100_rows(refresh=False, offline=False):
    """[{airport, year, months, passengers, departures}] for the Puerto Rico airports, every year in T-100."""
    def fetch():
        rows = soda(T100, **{"$select": "origin_airport_code as airport, year, count(*) as months, sum(total_passengers) as passengers, sum(total_departures) as departures",
                             "$where": "origin_airport_code in (" + ",".join(f"'{a}'" for a in T100_AIRPORTS) + ")", "$group": "origin_airport_code, year"})
        out = [{"airport": r["airport"], "year": int(r["year"]), "months": int(r["months"]), "passengers": round(float(r["passengers"])), "departures": round(float(r["departures"]))} for r in rows]
        log(f"  T-100: {len(out)} airport-years")
        return out
    return cached("t100_pr.json", fetch, refresh, offline)


def faa_rows(refresh=False, offline=False):
    """{year: {airport: enplanements}} from every FAA file under the current name; a newer file wins for the year two files share."""
    def fetch():
        out = {}
        for y in range(FAA_FIRST, date.today().year + 1):
            r = requests.get(FAA.format(y=y), headers=UA, timeout=(30, 300))
            if r.status_code == 404:
                continue
            r.raise_for_status()
            tmp = CACHE / "faa.xlsx"
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(r.content)
            rows = xlsx_lite.sheet_rows(tmp, xlsx_lite.sheet_names(tmp)[0])
            tmp.unlink()
            h = rows[0]
            cols = {yy: h.index(f"CY {str(yy)[2:]} Enplanements") for yy in (y, y - 1) if f"CY {str(yy)[2:]} Enplanements" in h}
            if y not in cols or "ST" not in h or "Locid" not in h:
                raise SystemExit(f"gateway_series: the FAA file of {y} has new columns ({h}): read it before going on")
            for x in rows[1:]:
                if len(x) > max(cols.values()) and x[h.index("ST")] == "PR":
                    for yy, c in sorted(cols.items()):   # y - 1 first, so the newer file's own year is set last
                        if yy == y or str(yy) not in out or x[h.index("Locid")] not in out[str(yy)]:
                            out.setdefault(str(yy), {})[x[h.index("Locid")]] = int(float(x[c]))
            log(f"  FAA CY{y}: {len(out[str(y)])} Puerto Rico airports")
        if not out:
            raise SystemExit("gateway_series: no FAA enplanement file answered")
        return out
    return cached("faa_enplanements_pr.json", fetch, refresh, offline)


def airport_municipality():
    """{FAA code: municipality name} from transport.json (the FAA airports, placed in their municipality by build.py)."""
    return {a["code"]: a["municipality"] for a in json.loads((hs.OUT / "transport.json").read_text(encoding="utf-8")) if a.get("source") == "faa_airports"}


# ── Ferries ──────────────────────────────────────────────────────────────────

def ncfo_rows(census, refresh=False, offline=False):
    """{data_year, terminals: {id: [lon, lat]}, segments: [{segment, from, passengers, trips}]} for the Puerto Rico terminals of one census."""
    op_seg, seg, term = NCFO[census]
    def fetch():
        terms = soda(term, **{"$where": "term_state='PR'"})
        tids = {t["terminal_id"] for t in terms}
        segs = {s["segment_id"]: s for s in soda(seg, **{"$where": "seg_terminal1_id in (" + ",".join(f"'{t}'" for t in tids) + ")"})}
        ops = soda(op_seg, **{"$where": "segment_id in (" + ",".join(f"'{s}'" for s in segs) + ")"})
        years = {t.get("data_year") for t in terms} | {o.get("data_year") for o in ops}
        years.discard(None)
        if len(years) > 1:
            raise SystemExit(f"gateway_series: the {census} ferry census gives more than one data year: {years}")
        out = {"data_year": int(years.pop()) if years else census,   # since 2022 BTS names a census for the year of its data; the 2024 files have no data_year column
               "terminals": {t["terminal_id"]: [float(t["longitude"]), float(t["latitude"])] for t in terms},
               "segments": [{"segment": o["segment_id"], "from": segs[o["segment_id"]]["seg_terminal1_id"], "passengers": int(float(o["passengers"])), "trips": int(float(o["trips_per_year"]))} for o in ops]}
        log(f"  NCFO {census} (data {out['data_year']}): {len(terms)} terminals, {len(ops)} segments")
        return out
    return cached(f"ncfo_{census}_pr.json", fetch, refresh, offline)


# ── Build ────────────────────────────────────────────────────────────────────

def compute(refresh=False, offline=False, floors=FLOORS):
    names, fips = hs.municipalities()
    by_name = dict(zip(names, fips))
    log("Gateways: airport passengers (BTS T-100, FAA) and ferry passengers (BTS NCFO)")
    column = lambda c: [c.get(f, 0) for f in fips] + [sum(c.get(f, 0) for f in fips)]
    muni = airport_municipality()

    def where(code):
        if muni.get(code) not in by_name:
            raise SystemExit(f"gateway_series: airport {code} is not an FAA airport of transport.json")
        return by_name[muni[code]]
    # T-100: full years only
    t = t100_rows(refresh, offline)
    full = sorted(r["year"] for r in t if r["airport"] == "SJU" and r["months"] == 12)
    pax, dep, months = {}, {}, {}
    for r in t:
        if r["year"] not in full:
            continue
        y, f = str(r["year"]), where(r["airport"])
        pax.setdefault(y, Counter())[f] += r["passengers"]
        dep.setdefault(y, Counter())[f] += r["departures"]
        months.setdefault(y, {})[r["airport"]] = r["months"]
    if floors and pax[str(full[-1])][where("SJU")] < floors["sju_passengers"]:
        raise SystemExit(f"gateway_series: San Juan had {pax[str(full[-1])][where('SJU')]:,} passengers in {full[-1]} (6.7 million in 2025)")
    # FAA
    fa = faa_rows(refresh, offline)
    enp = {y: Counter() for y in fa}
    for y, airports in fa.items():
        for code, n in airports.items():
            enp[y][where(code)] += n
    # ferries
    fpax, fnotes = {}, {}
    for census in sorted(NCFO):
        d = ncfo_rows(census, refresh, offline)
        tid = list(d["terminals"])
        at = {tid[i]: f for i, f in inf.locate([d["terminals"][k] for k in tid]).items()}
        c = Counter()
        for s in d["segments"]:
            c[at[s["from"]]] += s["passengers"]
        if floors and sum(c.values()) < floors["ferry_passengers"]:
            raise SystemExit(f"gateway_series: the {census} ferry census has {sum(c.values()):,} passengers")
        fpax[str(d["data_year"])] = c
        fnotes[str(d["data_year"])] = {"census": census, "terminals": len(tid), "segments": len(d["segments"]), "passengers": sum(c.values()), "trips": sum(s["trips"] for s in d["segments"])}
    G = "Airports and ferries"
    var = lambda key, label, sources, ref, definition, values: inf.var(key, G, label, "", 0, "count", sources, ref, definition, {y: column(c) for y, c in sorted(values.items())}, noPerHU=True, classes="jenks")
    vs = [
        var("air_passengers", "Air passengers boarding (commercial flights)", ["bts_t100"], "BTS T-100 Segment Summary by Origin Airport",
            "Passengers who boarded a commercial flight at an airport in the municipality during the year, to anywhere: the US mainland, another island or abroad. San Juan's airport (SJU) is in Carolina; Isla Grande (SIG) is in San Juan. A passenger is counted each time they board.", pax),
        var("air_departures", "Commercial flights departing", ["bts_t100"], "BTS T-100 Segment Summary by Origin Airport",
            "Commercial flights that departed from an airport in the municipality during the year, passenger and cargo.", dep),
        var("air_enplanements_faa", "Air passengers boarding (FAA enplanements)", ["faa_enplanements"], "FAA Commercial Service Airports, passenger boardings",
            "Passengers who boarded at a commercial service airport in the municipality during the calendar year, as FAA counts them for airport funding. It includes Ceiba's airport (RVR), which T-100 does not, and on-demand air taxi flights.", enp),
        var("ferry_passengers", "Ferry passengers boarding", ["bts_ncfo"], "BTS National Census of Ferry Operators",
            "Passengers who boarded a ferry at a terminal in the municipality during the year the census covers, as the operator reported them: Cataño and Old San Juan (the Cataño crossing), Ceiba, Vieques and Culebra. Passengers going and coming back are each counted where they board. The census is every two years.", fpax),
    ]
    notes = {"t100_full_years": [full[0], full[-1]], "t100_months_reported": months, "ferries": fnotes,
             "note": "A year of T-100 is published once San Juan has all twelve months. A smaller airport with fewer months had no commercial flights in the others (Ponce reported 3 months in 2020 and 9 in 2021)."}
    ys = sorted({int(y) for v in vs for y in v["years"]})
    return {"years": ys, "geo": {"ids": fips + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    d = compute(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
            print(f"{OUT.name} is not what the cache gives: run python gateway_series.py")
            return 1
        print(f"{OUT.name} matches the cache")
        return 0
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"wrote {OUT.name}: {len(d['vars'])} variables, {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
