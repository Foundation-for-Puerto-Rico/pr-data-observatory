"""Energy in Puerto Rico, for the Knowledge Area page "Energía en Puerto Rico" (site/energy.html). HANDOFF decision 104, step 3; docs/energy.md.

    python energy_series.py              # build site/data/energy.json (downloads only what cache/energy/ lacks)
    python energy_series.py --refresh    # look for newer filings and files, then build
    python energy_series.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Sources, none needs a key (decision 104 (d): LUMA's filings are read on the Energy Bureau's site, energia.pr.gov; LUMA's own site bars scripts):
  LUMA, Distributed generation data, Exhibit 2 (case NEPR-MI-2019-0016, quarterly; the newest file on the case page): every month since January 2010, the
      net metering customers registered, their capacity, the energy they exported to the grid, the system's net production by fuel (oil, natural gas, coal,
      hydro, solar, wind, landfill gas: the utility's and its contractors' plants) and the share LUMA counts toward the renewable portfolio standard.
      The file's second block of solar, wind and landfill-gas columns (production by fuel) holds other quantities before October 2017; the first block
      (contracted renewable production) is consistent every month and is the one read.
  LUMA, Monthly metrics workbook "Resumen Metricas Master" (case NEPR-MI-2019-0007, monthly; the newest), sheet T&D, from June 2021: electricity sales,
      battery installations and their kWh, and the share of customers with smart meters, by municipio (LUMA splits San Juan into San Juan, Río Piedras and
      Santurce: added back together); rooftop solar MW and installations by LUMA's 34 commercial districts; SAIDI by month for the system (transmission
      and distribution, and generation) and LUMA's 16 technical districts.
  EIA-861M, Sales to ultimate customers (US government data, public domain), every month since 2020: Puerto Rico's utility (number 15497) and the United
      States' residential revenue and sales, from which the average residential price in cents per kWh.
  The observatory's own files: power_plants.geojson (EIA-860M capacity by technology), power_lines.geojson (OpenStreetMap lines), flood.geojson (FEMA
      flood hazard areas) and municipios.geojson (2020 Census residents and housing units).

Output site/data/energy.json; every month is 'YYYY-MM'; energy in GWh, capacity in MW, prices in cents per kWh, SAIDI in minutes. No customer, address or
installation is in any source: the figures are LUMA's and EIA's totals by month, municipio or district.
"""

import datetime
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import facilities as fac
import housing_series as hs
import infrastructure_series as ins
import xlsx_lite

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "energy"
OUT = hs.OUT / "energy.json"
log = hs.log
BUREAU = "https://energia.pr.gov/en/dockets/?docket={case}"
DG_CASE, METRICS_CASE = "nepr-mi-2019-0016", "nepr-mi-2019-0007"
EIA861M = "https://www.eia.gov/electricity/data/eia861m/{dir}xls/sales_ult_cust_{y}.xlsx"
PRICE_FIRST = 2020
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
SJ_PARTS = {"Río Piedras": "San Juan", "Rio Piedras": "San Juan", "Santurce": "San Juan"}
# Exhibit 2, sheet "Monthly ": column of each quantity (checked by header text in dg_rows)
DG_COLS = {"exported": (3, "Energ"), "capacity_kw": (8, "Capacidad Clientes GD"), "customers": (9, "Clientes Registrados"), "solar": (15, "Fotovoltaica"),
           "wind": (16, "lica"), "landfill": (17, "Otras fuentes"), "rps_pct": (25, "Cumplimiento"), "oil": (26, "Petr"), "gas": (27, "Gas Natural"),
           "coal": (28, "Carb"), "hydro": (29, "Hidro"), "dg": (33, "DG")}
FUELS = ["oil", "gas", "coal", "hydro", "solar", "wind", "landfill", "dg"]


def month_of(serial):
    return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(serial)))).isoformat()[:7]


def num(v):
    try:
        x = float(str(v).replace(",", ""))
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def r(v, d=1):
    return None if v is None else round(v + 0, d)


def newest_on_case(case, pattern, key):
    """The newest file on an Energy Bureau case page whose URL matches pattern, by key(url) (None when the page does not answer)."""
    resp = ins.get(BUREAU.format(case=case))
    if resp is None:
        return None
    urls = sorted(set(re.findall(r'https?://energia\.pr\.gov/[^"\']*' + pattern, resp.text)), key=key)
    return urls[-1] if urls else None


def metrics_key(u):
    m = re.search(r"Master[_-]([A-Za-z]+)[-_]?(\d{4})", u)
    return (int(m.group(2)), MONTHS.index(m.group(1).lower()) + 1) if m and m.group(1).lower() in MONTHS else (0, 0)


def dg_key(u):
    m = re.search(r"/(\d{8})-MI20190016-Exhibit-2", u)
    return m.group(1) if m else ""


def cached(name, url, refresh):
    """A file in the cache: downloaded when missing (or when refresh found a newer name). Returns its path."""
    p = CACHE / name
    if not p.exists():
        resp = ins.get(url)
        if resp is None or resp.content[:2] != b"PK":
            raise SystemExit(f"energy_series: {url} did not give a spreadsheet")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(resp.content)
        log(f"  downloaded {name} ({len(resp.content) // 1024} KB)")
    return p


def sources(refresh=False, check=False):
    """The names of the files to read: kept in cache/energy/sources.json, renewed from the Bureau's case pages with --refresh."""
    p = CACHE / "sources.json"
    s = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    if check:
        if not s:
            raise SystemExit("energy_series --check: cache/energy/sources.json is missing")
        return s
    if refresh or not s:
        dg = newest_on_case(DG_CASE, r"Exhibit-2-Distributed-Generation-Data[^\"']*\.xlsx", dg_key)
        mt = newest_on_case(METRICS_CASE, r"Resumen-Metricas-Master[^\"']*\.xlsx", metrics_key)
        if dg:
            s["dg"] = dg
        if mt:
            s["metrics"] = mt
        if "dg" not in s or "metrics" not in s:
            raise SystemExit("energy_series: the Energy Bureau's case pages gave no Exhibit 2 or metrics workbook")
        s["checked"] = datetime.date.today().isoformat()
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(s, indent=1), encoding="utf-8")
    return s


def dg_rows(path):
    rows = xlsx_lite.sheet_rows(path, next(n for n in xlsx_lite.sheet_names(path) if n.strip() == "Monthly"))
    head = rows[2]
    for k, (c, word) in DG_COLS.items():
        if word not in str(head[c]):
            raise SystemExit(f"energy_series: Exhibit 2 column {c} is {head[c]!r}, expected {word!r} ({k}); the layout changed")
    out = []
    for x in rows:
        if len(x) > 33 and str(x[1]).replace(".", "").isdigit():
            out.append({"m": month_of(x[1]), **{k: num(x[c]) for k, (c, _) in DG_COLS.items()}})
    return out


def metrics(path):
    rows = xlsx_lite.sheet_rows(path, "T&D")
    hdr = rows[0]
    months = {i: month_of(hdr[i]) for i in range(5, len(hdr)) if str(hdr[i]).replace(".", "").isdigit()}
    by = {}
    for x in rows[1:]:
        if len(x) < 5:
            continue
        key = (x[2].strip(), x[3].strip())
        vals = {months[i]: num(x[i]) for i in months if i < len(x) and num(x[i]) is not None}
        by.setdefault(key, {}).update(vals)
    return by, sorted(set(months.values()))


def metric(by, name, area):
    return by.get((name, area), {})


def muni_series(by, name, M, add_parts):
    """{geoid: {month: value}} of a metric by municipio; San Juan's parts added when add_parts."""
    out = {}
    for (n, area), vals in by.items():
        if n != name or area in ("", "Total", "System"):
            continue
        target = SJ_PARTS.get(area, area) if add_parts else area
        g = M.by_name.get(fac.norm(target))
        if g is None:
            continue
        acc = out.setdefault(g, {})
        for m, v in vals.items():
            acc[m] = acc.get(m, 0) + v if add_parts else v
    return out


def price_rows(refresh=False, check=False):
    """{month: [pr revenue k$, pr sales MWh, us revenue k$, us sales MWh]} for residential customers, from EIA-861M."""
    out, this = {}, datetime.date.today().year
    for y in range(PRICE_FIRST, this + 1):
        p = CACHE / f"sales_ult_cust_{y}.xlsx"
        if not p.exists() or (refresh and y >= this - 1):
            if check:
                continue
            got = None
            for d in ("", "archive/"):
                resp = ins.get(EIA861M.format(dir=d, y=y))
                if resp is not None and resp.content[:2] == b"PK":
                    got = resp.content
                    break
            if got is None:
                continue
            CACHE.mkdir(parents=True, exist_ok=True)
            p.write_bytes(got)
        for sheet in xlsx_lite.sheet_names(p):
            rows = xlsx_lite.sheet_rows(p, sheet)
            hi = next((i for i, x in enumerate(rows) if "Utility Number" in x), None)
            if hi is None:
                continue
            h = rows[hi]
            iy, im, iu, ist, irev, isal = h.index("Year"), h.index("Month"), h.index("Utility Number"), h.index("State"), 7, 8
            terr = "Territ" in sheet
            for x in rows[hi + 1:]:
                if len(x) <= isal or not str(x[iy]).strip().isdigit():
                    continue
                m = f"{int(x[iy])}-{int(float(x[im])):02d}"
                rev, sal = num(x[irev]) or 0.0, num(x[isal]) or 0.0
                acc = out.setdefault(m, [0.0, 0.0, 0.0, 0.0])
                if terr:
                    if x[ist] == "PR" and str(x[iu]).strip() == "15497":
                        acc[0] += rev
                        acc[1] += sal
                else:
                    acc[2] += rev
                    acc[3] += sal
    return out


def exposure():
    """Transmission line km and plant MW inside FEMA's 1% flood hazard area (SFHA) and its coastal high-hazard V zones, from the published files."""
    from shapely.geometry import MultiLineString, Point, shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    fl = json.loads((hs.OUT / "flood.geojson").read_text(encoding="utf-8"))
    sfha = [shape(f["geometry"]).buffer(0) for f in fl["features"] if (f["properties"].get("SFHA_TF") == "T")]
    vz = [g for f, g in zip([f for f in fl["features"] if f["properties"].get("SFHA_TF") == "T"], sfha) if str(f["properties"].get("FLD_ZONE", "")).startswith("V")]
    S, V = unary_union(sfha), unary_union(vz) if vz else None
    km = lambda geom: sum(fac_km(list(ln.coords)) for ln in (geom.geoms if hasattr(geom, "geoms") else [geom]) if ln.geom_type == "LineString")
    L = json.loads((hs.OUT / "power_lines.geojson").read_text(encoding="utf-8"))
    lines = {}
    for f in L["features"]:
        g = MultiLineString(f["geometry"]["coordinates"])
        kv = str(f["properties"]["kv"])
        e = lines.setdefault(kv, {"km": 0.0, "sfha_km": 0.0, "v_km": 0.0})
        e["km"] += km(g)
        e["sfha_km"] += km(g.intersection(S))
        if V is not None:
            e["v_km"] += km(g.intersection(V))
    P = json.loads((hs.OUT / "power_plants.geojson").read_text(encoding="utf-8"))
    op = [f for f in P["features"] if f["properties"]["status"] == "op"]
    inside = [f["properties"] for f in op if S.contains(Point(f["geometry"]["coordinates"]))]
    return {"lines": {k: {x: round(y, 1) for x, y in v.items()} for k, v in lines.items()},
            "plants_sfha": len(inside), "plants_sfha_mw": round(sum(p["mw"] for p in inside), 1), "plants": len(op), "plants_mw": round(sum(f["properties"]["mw"] for f in op), 1),
            "plants_sfha_list": sorted(([p["name"], p["municipio"], p["mw"], p["tech"]] for p in inside if p["mw"] >= 20), key=lambda x: -x[2]),
            "flood_note": "FEMA National Flood Hazard Layer as published in flood.geojson (the observatory's 2D flood layer): zones with SFHA_TF = T; V zones are the coastal high-hazard areas."}


def fac_km(coords):
    t = 0.0
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        k = math.cos(math.radians((y0 + y1) / 2))
        t += 6371.0088 * math.hypot(math.radians(x1 - x0) * k, math.radians(y1 - y0))
    return t


def build(refresh=False, check=False):
    src = sources(refresh, check)
    dgp = cached("dg_" + src["dg"].rsplit("/", 1)[-1], src["dg"], refresh)
    mtp = cached("metrics_" + src["metrics"].rsplit("/", 1)[-1], src["metrics"], refresh)
    M = fac.Munis()
    munis = json.loads((hs.OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]
    hu = {str(f["properties"]["GEOID"])[:5]: f["properties"]["HU100"] for f in munis}
    pop = {str(f["properties"]["GEOID"])[:5]: f["properties"]["POP100"] for f in munis}

    # 1 · the monthly series since 2010 (Exhibit 2)
    D = dg_rows(dgp)
    gen = {k: [r((x[k] or 0) / 1e6, 2) for x in D] for k in FUELS}   # kWh -> GWh
    series = {"months": [x["m"] for x in D], "gen_gwh": gen, "rps_pct": [r(x["rps_pct"], 2) for x in D],
              "rooftop_customers": [int(x["customers"]) if x["customers"] is not None else None for x in D],
              "rooftop_mw": [r(x["capacity_kw"] / 1000, 1) if x["capacity_kw"] is not None else None for x in D],
              "exported_gwh": [r((x["exported"] or 0) / 1e6, 2) for x in D]}
    years = {}
    for x in D:
        y = years.setdefault(x["m"][:4], Counter())
        y["n"] += 1
        for k in FUELS:
            y[k] += (x[k] or 0) / 1e6
    annual = {y: {k: round(c[k], 1) for k in FUELS} for y, c in sorted(years.items()) if c["n"] == 12}

    # 2 · municipios and districts (metrics workbook)
    by, mmonths = metrics(mtp)
    sales = muni_series(by, "Monthly sales by Municipality", M, True)
    bess_n = muni_series(by, "Total number of BESS installations", M, True)
    bess_kwh = muni_series(by, "Total installed BESS capacity", M, True)
    ami = muni_series(by, "Percent of customers on AMI", M, False)
    last_m = max(m for g in bess_n.values() for m in g)
    ami_m = max((m for g in ami.values() for m, v in g.items() if v is not None), default=None)
    last12 = sorted({m for g in sales.values() for m in g})[-12:]
    ids = sorted(hu)
    muni = {"ids": ids, "names": [M.name_of[g] for g in ids], "hu": [hu[g] for g in ids], "pop": [pop[g] for g in ids],
            "bess": [int(bess_n.get(g, {}).get(last_m, 0)) for g in ids], "bess_kwh": [round(bess_kwh.get(g, {}).get(last_m, 0)) for g in ids],
            "sales_gwh_12m": [round(sum(sales.get(g, {}).get(m, 0) for m in last12), 1) for g in ids],
            "ami_pct": [r(ami[g][ami_m] * 100, 1) if ami.get(g, {}).get(ami_m) is not None else None for g in ids], "ami_as_of": ami_m,
            "ami_system_pct": r((metric(by, "Percent of customers on AMI", "System").get(ami_m) or 0) * 100, 1), "as_of": last_m, "sales_months": [last12[0], last12[-1]]}
    bess_months = sorted({m for g in bess_n.values() for m in g})
    muni["bess_series"] = {"months": bess_months, "total": [int(sum(bess_n.get(g, {}).get(m, 0) for g in ids)) for m in bess_months]}
    pv_mw = {a: v for (n, a), v in by.items() if n == "Total installed distributed generation capacity - Photovoltaic" and a != "Total"}
    pv_n = {a: v for (n, a), v in by.items() if n == "Total number of distributed generation installations - Photovoltaic" and a != "Total"}
    pv_last = max(m for v in pv_mw.values() for m in v)
    districts = sorted(([a, r(pv_mw[a].get(pv_last), 1), int(pv_n.get(a, {}).get(pv_last, 0))] for a in pv_mw), key=lambda x: -(x[1] or 0))
    saidi_names = [a for (n, a) in by if n == "Monthly SAIDI (T&D)" and a != "System"]
    smonths = [m for m in mmonths if any(m in metric(by, "Monthly SAIDI (T&D)", a) for a in ["System"])]
    saidi = {"months": smonths, "td": [r(metric(by, "Monthly SAIDI (T&D)", "System").get(m), 1) for m in smonths],
             "dist": [r(metric(by, "Monthly SAIDI Distribution", "System").get(m), 1) for m in smonths],
             "eia861_2025": {"saidi_all": 3547, "saifi_all": 17.17, "saidi_no_med": 2151, "saifi_no_med": 15.5, "note": "EIA-861 2025, Reliability, Puerto Rico's utility (15497): all events including major event days and generation shortfalls, and without major event days (IEEE 1366); read on 2026-11-13."},
             "districts": {a: [r(metric(by, "Monthly SAIDI (T&D)", a).get(m), 1) for m in smonths] for a in sorted(saidi_names)}}

    # 3 · price (EIA-861M)
    P = price_rows(refresh, check)
    pm = sorted(m for m, v in P.items() if v[1] > 0 and v[3] > 0)
    price = {"months": pm, "pr": [round(P[m][0] / P[m][1] * 100, 2) for m in pm], "us": [round(P[m][2] / P[m][3] * 100, 2) for m in pm]}

    # 4 · plants, lines and flood hazard (the observatory's files)
    plants = json.loads((hs.OUT / "power_plants.geojson").read_text(encoding="utf-8"))
    lines = json.loads((hs.OUT / "power_lines.geojson").read_text(encoding="utf-8"))
    pn = plants["notes"]
    cap = {"as_of": plants["vintage"], "by_tech": pn["by_tech"], "mw": pn["mw"], "renewable_mw": pn["renewable_mw"], "battery_mw": pn["battery_mw"], "plants": pn["plants"], "built_mw": pn.get("built_mw", 0), "built_plants": pn.get("built_plants", 0),
           "rooftop_mw": next((v for v in reversed(series["rooftop_mw"]) if v), None), "rooftop_month": next((m for m, v in zip(reversed(series["months"]), reversed(series["rooftop_mw"])) if v), None)}
    out = {"source": "luma_bureau", "built": src.get("checked") or datetime.date.today().isoformat(),
           "files": {"dg": src["dg"], "metrics": src["metrics"]},
           "series": series, "annual_gwh": annual, "capacity": cap, "municipios": muni,
           "districts": {"as_of": pv_last, "rows": districts, "fields": ["district", "rooftop_mw", "installations"]},
           "saidi": saidi, "price": price, "exposure": exposure(), "lines_km": lines["notes"]["km_by_kv"], "lines_as_of": lines["vintage"],
           "law": {"act_17_2019": {"rps": {"2025": 40, "2040": 60, "2050": 100}, "coal_end": "2028-01-01"},
                   "act_1_2025": {"rps": {"2050": 100}, "coal_end": "2032-12-31", "note": "removed the 40% (2025) and 60% (2040) interim targets"}}}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"energy.json {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name}: {series['months'][0]} to {series['months'][-1]}, rooftop {cap['rooftop_mw']} MW ({cap['rooftop_month']}), batteries {sum(muni['bess']):,} ({last_m}), "
        f"price {price['months'][0] if pm else '-'} to {price['months'][-1] if pm else '-'}, SAIDI {smonths[0]} to {smonths[-1]}, {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
