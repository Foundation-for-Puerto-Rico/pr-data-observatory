"""Power plants for the PR Data Observatory: one point per plant in EIA's monthly generator inventory, for the "Power plants" layer of the 2D map and the 3D
view (core/facilities.js draws it: circle area by capacity, color by main technology). HANDOFF decision 104, step 1; docs/energy.md.

    python power_plants.py              # build site/data/power_plants.geojson (downloads EIA-860M only when cache/energy/ has no copy)
    python power_plants.py --refresh    # download the newest EIA-860M file again
    python power_plants.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: EIA-860M, the Monthly Update to the Annual Electric Generator Report (https://www.eia.gov/electricity/data/eia860m/; US government data,
public domain), the newest monthly file that answers. Puerto Rico has its own sheets: Operating_PR (generators operating, on standby or out of service) and
Planned_PR (generators under construction or planned). infrastructure_series.py reads the same file for its counts by municipio.

Kept, per generator: plant id, plant name, technology, nameplate capacity (MW), battery energy (MWh), status, operating year (planned month and year), point.
The owner (EIA's "Entity Name") is never kept (decision 104 (b)). Every plant in the inventory has generators adding up to 1 MW or more, so no home is in it;
rooftop solar is not.

One point per plant (EIA's point; all of a plant's generators share it), placed in the municipio whose outline holds it (facilities.Munis). Properties:
  name, type, municipio, geoid   as the other facility layers (facilities.feature)
  eia      EIA's plant id
  tech     the main technology: the one with the most operating nameplate MW without batteries; batteries when the plant has nothing else
  mw       operating nameplate MW without batteries (generators on standby and out of service included, as EIA lists them)
  bat_mw, bat_mwh   operating battery capacity (MW) and energy (MWh), when the plant has batteries
  by       {technology: MW} of the operating generators, batteries included
  sb, out  MW on standby, and MW out of service (EIA's OA and OS), when any
  units    operating generators; y0, y1: the first and last operating year among them
  plan     {technology: MW} planned or under construction; plan_ym: the earliest planned month (YYYY-MM)
  status   "op" (at least one operating generator), "planned", or "built" (an added plant, below)

Added plants (energy_src/plants_added.json, kept by hand with a source for each): solar plants of 1 MW or more that are built but not yet in EIA-860M,
because they are not yet in commercial operation (CIRO One, the two Marahú farms, Yabucoa Solar in November 2026). Each gets status "built", no eia id, and
  stage    "connected" (connected to the grid, commercial operation not yet declared) or "complete" (construction complete, not yet connected)
  as_of    the month of that status (YYYY-MM); src, url: the source; osm: the OpenStreetMap ways whose outlines place the point
An added plant leaves the file by itself, with a line in the log, once EIA lists a plant whose name matches its eia_match. The notes' totals (plants, mw,
renewable_mw, battery_mw) stay EIA's operating plants; built_plants, built_mw and built_battery_mw count the added ones.
"""

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import facilities as fac
import housing_series as hs
import infrastructure_series as ins
import xlsx_lite

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "energy"
RAW = CACHE / "eia860m_plants.pr.json"
OUT = hs.OUT / "power_plants.geojson"
ADDED = ROOT / "energy_src" / "plants_added.json"
log = hs.log
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
OP_COLS = ["Plant ID", "Plant Name", "Technology", "Nameplate Capacity (MW)", "Nameplate Energy Capacity (MWh)", "Status", "Operating Year", "Latitude", "Longitude"]
PL_COLS = ["Plant ID", "Plant Name", "Technology", "Nameplate Capacity (MW)", "Status", "Planned Operation Month", "Planned Operation Year", "Latitude", "Longitude"]
FLOOR = 40   # 67 plants with operating generators in the September 2026 file: fewer than 40 means a sheet was cut short

# EIA's technologies, in the eight groups the layer colors (the same groups as docs/energy-proposal-2026-11.md); a technology not listed stops the build
TECH = {"Petroleum Liquids": "oil", "Petroleum Coke": "oil",
        "Natural Gas Steam Turbine": "gas", "Natural Gas Fired Combined Cycle": "gas", "Natural Gas Internal Combustion Engine": "gas",
        "Natural Gas Fired Combustion Turbine": "gas", "Other Natural Gas": "gas",
        "Conventional Steam Coal": "coal", "Solar Photovoltaic": "solar", "Onshore Wind Turbine": "wind", "Conventional Hydroelectric": "hydro",
        "Batteries": "battery", "Landfill Gas": "landfill", "Other Waste Biomass": "landfill", "Wood/Wood Waste Biomass": "landfill"}
RENEWABLE = {"solar", "wind", "hydro", "landfill"}
STANDBY = "(SB)"
OUT_OF_SERVICE = ("(OA)", "(OS)")


def sheet(path, name, cols):
    rows = xlsx_lite.sheet_rows(path, name)
    hi = next(i for i, x in enumerate(rows) if "Plant ID" in x)
    h = rows[hi]
    missing = [c for c in cols if c not in h]
    if missing:
        raise SystemExit(f"power_plants: EIA-860M's {name} sheet has no column {missing}")
    ix = [h.index(c) for c in cols]
    return [{c: (x[i] if i < len(x) else "") for c, i in zip(cols, ix)} for x in rows[hi + 1:] if len(x) > ix[0] and str(x[ix[0]]).strip().isdigit()]


def fetch(refresh=False):
    """The kept columns of the newest EIA-860M file's Puerto Rico sheets, cached as JSON (the 14 MB workbook is not kept)."""
    if RAW.exists() and not refresh:
        return json.loads(RAW.read_text(encoding="utf-8"))
    t = date.today()
    for back in range(0, 8):
        y, m = divmod(t.year * 12 + t.month - 1 - back, 12)
        r = ins.get(ins.EIA.format(month=MONTHS[m], year=y))
        if r is not None and r.content[:2] == b"PK":
            break
    else:
        raise SystemExit("power_plants: no EIA-860M file of the last eight months answered")
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = CACHE / "eia860m.xlsx"
    tmp.write_bytes(r.content)
    try:
        d = {"month": f"{y}-{m + 1:02d}", "fetched": t.isoformat(), "operating": sheet(tmp, "Operating_PR", OP_COLS), "planned": sheet(tmp, "Planned_PR", PL_COLS)}
    finally:
        tmp.unlink()
    RAW.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  EIA-860M {d['month']}: {len(d['operating'])} operating and {len(d['planned'])} planned generators of Puerto Rico")
    return d


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return 0.0


def tech_of(t):
    if t not in TECH:
        raise SystemExit(f"power_plants: EIA technology {t!r} has no group in TECH; add it")
    return TECH[t]


def r1(v):
    return round(v + 1e-9, 1)


def build(refresh=False, check=False):
    if check and not RAW.exists():
        log(f"power_plants --check: {RAW.name} is not in the cache")
        return 1
    d = fetch(refresh) if not check else json.loads(RAW.read_text(encoding="utf-8"))
    M = fac.Munis()
    plants = {}
    for g in d["operating"]:
        p = plants.setdefault(g["Plant ID"].strip(), {"name": g["Plant Name"].strip(), "lon": num(g["Longitude"]), "lat": num(g["Latitude"]), "by": Counter(), "plan": Counter(),
                                                      "bat_mwh": 0.0, "sb": 0.0, "out": 0.0, "years": [], "units": 0, "plan_ym": []})
        k, mw = tech_of(g["Technology"].strip()), num(g["Nameplate Capacity (MW)"])
        p["by"][k] += mw
        p["units"] += 1
        if k == "battery":
            p["bat_mwh"] += num(g["Nameplate Energy Capacity (MWh)"])
        st = g["Status"].strip()
        if st.startswith(STANDBY):
            p["sb"] += mw
        elif st.startswith(OUT_OF_SERVICE):
            p["out"] += mw
        if str(g["Operating Year"]).strip().isdigit():
            p["years"].append(int(g["Operating Year"]))
    for g in d["planned"]:
        p = plants.setdefault(g["Plant ID"].strip(), {"name": g["Plant Name"].strip(), "lon": num(g["Longitude"]), "lat": num(g["Latitude"]), "by": Counter(), "plan": Counter(),
                                                      "bat_mwh": 0.0, "sb": 0.0, "out": 0.0, "years": [], "units": 0, "plan_ym": []})
        p["plan"][tech_of(g["Technology"].strip())] += num(g["Nameplate Capacity (MW)"])
        if str(g["Planned Operation Year"]).strip().isdigit() and str(g["Planned Operation Month"]).strip().isdigit():
            p["plan_ym"].append(f"{int(g['Planned Operation Year'])}-{int(g['Planned Operation Month']):02d}")
    feats, left_out = [], []
    for pid, p in plants.items():
        geoid = M.at(p["lon"], p["lat"])
        if geoid is None:
            left_out.append({"eia": pid, "name": p["name"], "why": "the point is outside every municipio"})
            continue
        gen = {k: v for k, v in p["by"].items() if k != "battery"}
        op = bool(p["by"])
        tech = max(sorted(gen), key=lambda k: gen[k]) if gen else "battery" if p["by"] else max(sorted(p["plan"]), key=lambda k: p["plan"][k])
        extra = {"eia": pid, "tech": tech, "mw": r1(sum(gen.values())), "status": "op" if op else "planned"}
        if p["by"].get("battery"):
            extra.update(bat_mw=r1(p["by"]["battery"]), bat_mwh=r1(p["bat_mwh"]))
        if op:
            extra["by"] = {k: r1(v) for k, v in sorted(p["by"].items(), key=lambda kv: (-kv[1], kv[0]))}
            extra.update(units=p["units"], y0=min(p["years"]) if p["years"] else None, y1=max(p["years"]) if p["years"] else None)
        if p["sb"]:
            extra["sb"] = r1(p["sb"])
        if p["out"]:
            extra["out"] = r1(p["out"])
        if p["plan"]:
            extra["plan"] = {k: r1(v) for k, v in sorted(p["plan"].items(), key=lambda kv: (-kv[1], kv[0]))}
            if p["plan_ym"]:
                extra["plan_ym"] = min(p["plan_ym"])
        feats.append(fac.feature(p["lon"], p["lat"], p["name"], "Power plant", geoid, M, **extra))
    built, absorbed = added(plants, M)
    feats += built
    feats.sort(key=lambda f: (-(f["properties"]["mw"] or f["properties"].get("bat_mw", 0)), f["properties"].get("eia") or "", f["properties"]["name"]))
    opf = [f["properties"] for f in feats if f["properties"]["status"] == "op"]
    if len(opf) < FLOOR:
        raise SystemExit(f"power_plants: only {len(opf)} plants with an operating generator (67 in September 2026); not written")
    by_tech = Counter()
    for q in opf:
        by_tech.update(q["by"])
    notes = {"plants": len(opf), "planned_plants": sum(1 for f in feats if f["properties"]["status"] == "planned"), "generators": len(d["operating"]),
             "mw": r1(sum(q["mw"] for q in opf)), "battery_mw": r1(by_tech["battery"]), "battery_mwh": r1(sum(q.get("bat_mwh", 0) for q in opf)),
             "renewable_mw": r1(sum(v for k, v in by_tech.items() if k in RENEWABLE)), "standby_mw": r1(sum(q.get("sb", 0) for q in opf)),
             "out_of_service_mw": r1(sum(q.get("out", 0) for q in opf)), "planned_mw": r1(sum(sum(f["properties"].get("plan", {}).values()) for f in feats)),
             "by_tech": {k: r1(v) for k, v in sorted(by_tech.items(), key=lambda kv: -kv[1])}, "municipios": len({q["geoid"] for q in opf}), "left_out": left_out,
             "built_plants": len(built), "built_mw": r1(sum(f["properties"]["mw"] for f in built)), "built_battery_mw": r1(sum(f["properties"].get("bat_mw", 0) for f in built)),
             "built_absorbed": absorbed}
    out = {"type": "FeatureCollection", "source": "eia_860m", "vintage": d["month"], "built": d["fetched"], "notes": notes, "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"power_plants.geojson {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name}: {notes['plants']} plants in {notes['municipios']} municipios, {notes['mw']:,} MW without batteries, {notes['battery_mw']} MW of batteries, "
        f"{notes['renewable_mw']} MW renewable; {notes['planned_plants']} planned plants ({notes['planned_mw']} MW planned in all); "
        f"{len(built)} built plants added ({notes['built_mw']} MW){'; now in EIA, no longer added: ' + ', '.join(absorbed) if absorbed else ''}; {len(left_out)} left out; {len(text) // 1024} KB")
    return 0


def added(plants, M):
    """The built plants of energy_src/plants_added.json that EIA does not list yet, as features; and the names of those EIA now lists (eia_match)."""
    names = [p["name"].lower() for p in plants.values()]
    feats, absorbed = [], []
    for a in json.loads(ADDED.read_text(encoding="utf-8"))["plants"]:
        if a["stage"] not in ("connected", "complete") or a["tech"] not in set(TECH.values()):
            raise SystemExit(f"power_plants: {ADDED.name}: {a['key']} has stage {a['stage']!r} or technology {a['tech']!r}")
        if any(re.search(a["eia_match"], n) for n in names):
            absorbed.append(a["name"])
            continue
        geoid = M.at(a["lon"], a["lat"])
        if geoid is None:
            raise SystemExit(f"power_plants: {ADDED.name}: {a['key']} is outside every municipio")
        by = {a["tech"]: r1(a["mw"])}
        extra = {"tech": a["tech"], "mw": r1(a["mw"]), "status": "built", "stage": a["stage"], "as_of": a["as_of"]}
        if a.get("bat_mw"):
            by["battery"] = r1(a["bat_mw"])
            extra["bat_mw"] = r1(a["bat_mw"])
            if a.get("bat_mwh"):
                extra["bat_mwh"] = r1(a["bat_mwh"])
        extra.update(by=dict(sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))), src=a["source"]["name"], url=a["source"]["url"], osm=a["osm"])
        feats.append(fac.feature(a["lon"], a["lat"], a["name"], "Power plant", geoid, M, **extra))
    return feats, absorbed


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
