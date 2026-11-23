"""Urban heat beside the people it reaches, by barrio: the data of the Knowledge Area page urban-heat.html (terrain and climate plan, step 3; HANDOFF decision 80).

The page sets the surface heat of the land (morning and night) and its greenness next to measures of the residents who live there, barrio by barrio, and
states the facts without drawing conclusions: the measures are never combined into one score (the rule of the FEMA funding page, decision 72). It adds no
source: every figure is read from files the site already publishes.

    python urban_heat.py            # reads site/data/*_barrio.json and the crosswalk, writes site/data/urban_heat.json and prints the island figures
    python urban_heat.py --check    # rebuilds in memory and compares with the published file (no write)

Land (summer, June to September of the last three complete summers; satellite figures over the barrio's 60 m cells):
  day     median land surface temperature, summer mornings (Landsat, about 10:30)   heat_barrio.json        heat_lst_med
  night   median land surface temperature, summer nights (ECOSTRESS, 21:00-06:00)  night_heat_barrio.json  night_lst_med
  ndvi    median vegetation greenness (Sentinel-2 NDVI)                             vegetation_barrio.json  veg_ndvi_med
People (American Community Survey, the latest 5-year window, with the published margins of error at 90%; and a drive time):
  age65   residents 65 and older, %                    acs_barrio.json acs_age65plus_pct
  pov     residents below the poverty level, %         acs_barrio.json poverty_pct
  noveh   households without a vehicle, %              acs_barrio.json no_vehicle_hh_pct
  alone   households of one person living alone, %     acs_barrio.json acs_living_alone_pct
  hosp    drive time to a general hospital, minutes    conditions_barrio.json hosp_drive_min (the observatory's estimate)
Residents: the crosswalk's 2020 Census residents of each barrio. The Census Bureau's Community Resilience Estimates have no barrio values, so they are not here.
No personal data: the file holds shares, medians and counts by barrio.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT = DATA / "urban_heat.json"
LAND = {"day": ("heat_barrio.json", "heat_lst_med"), "night": ("night_heat_barrio.json", "night_lst_med"), "ndvi": ("vegetation_barrio.json", "veg_ndvi_med")}
PEOPLE = {"age65": "acs_age65plus_pct", "pov": "poverty_pct", "noveh": "no_vehicle_hh_pct", "alone": "acs_living_alone_pct"}
HOSP = ("conditions_barrio.json", "hosp_drive_min")
SERIES = {"day": "heat_series.json", "night": "night_heat_series.json", "ndvi": "vegetation_series.json"}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def var(doc, key):
    for v in doc["vars"]:
        if v["key"] == key:
            return v
    raise SystemExit(f"urban_heat: no {key}")


def only_year(v, key):
    ys = list(v["years"])
    if len(ys) != 1:
        raise SystemExit(f"urban_heat: {key} has {len(ys)} years, expected one snapshot")
    return ys[0], v["years"][ys[0]]


def ranks(x):
    """Average ranks; ties share their mean rank."""
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    k = 0
    while k < len(o):
        j = k
        while j + 1 < len(o) and x[o[j + 1]] == x[o[k]]:
            j += 1
        for t in range(k, j + 1):
            r[o[t]] = (k + j) / 2 + 1
        k = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    sab = sum((p - ma) * (q - mb) for p, q in zip(ra, rb))
    sa = sum((p - ma) ** 2 for p in ra) ** 0.5
    sb = sum((q - mb) ** 2 for q in rb) ** 0.5
    return sab / (sa * sb)


def build():
    cw = load("geo/crosswalk.json")
    F = {f: i for i, f in enumerate(cw["fields"])}
    rows = cw["units"]["barrio"]
    ids = [r[F["id"]] for r in rows]
    munis = {r[F["id"]]: r[F["name_es"]] for r in cw["units"]["municipio"]}
    n = len(ids)
    land, land_window = {}, {}
    for k, (f, key) in LAND.items():
        d = load(f)
        if d["geo"]["ids"] != ids:
            raise SystemExit(f"urban_heat: {f} lists its barrios in another order than the crosswalk")
        y, col = only_year(var(d, key), key)
        land[k] = col
        land_window[k] = load(SERIES[k])["notes"]["window"]["summers"]
    acs = load("acs_barrio.json")
    if acs["geo"]["ids"] != ids:
        raise SystemExit("urban_heat: acs_barrio.json lists its barrios in another order than the crosswalk")
    wy = str(max(int(y) for y in acs["windows"]))
    people, moe = {}, {}
    for k, key in PEOPLE.items():
        v = var(acs, key)
        people[k] = v["years"][wy]
        moe[k] = v["moe"][wy]
    hd = load(HOSP[0])
    if hd["geo"]["ids"] != ids:
        raise SystemExit("urban_heat: conditions_barrio.json lists its barrios in another order")
    _, people["hosp"] = only_year(var(hd, HOSP[1]), HOSP[1])
    for k, col in {**land, **people}.items():
        if len(col) != n:
            raise SystemExit(f"urban_heat: {k} has {len(col)} values, not {n}")
    # rank correlations across the barrios that have both values (facts for the page's grid; the page says what a rank correlation is and is not)
    rho = {}
    for a, ca in land.items():
        for b, cb in people.items():
            pairs = [(x, y) for x, y in zip(ca, cb) if x is not None and y is not None]
            rho[f"{a}:{b}"] = {"rho": round(spearman([p for p, _ in pairs], [q for _, q in pairs]), 2) + 0.0, "n": len(pairs)}
    for a in land:
        for b in land:
            if a < b:
                pairs = [(x, y) for x, y in zip(land[a], land[b]) if x is not None and y is not None]
                rho[f"{a}:{b}"] = {"rho": round(spearman([p for p, _ in pairs], [q for _, q in pairs]), 2) + 0.0, "n": len(pairs)}
    return {
        "version": 1,
        "built": date.today().isoformat(),
        "level": "barrio",
        "geo": {"ids": ids, "names": [r[F["name_es"]] for r in rows], "muni": [r[F["parent"]] for r in rows], "muni_names": munis},
        "population": [r[F["pop"]] for r in rows],
        "population_year": 2020,
        "land": land,
        "land_summers": land_window,
        "people": people,
        "moe": moe,
        "acs_window": f"{int(wy) - 4}-{wy}",
        "rho": rho,
        "inputs": {**{k: f"{f} {key}" for k, (f, key) in LAND.items()}, **{k: f"acs_barrio.json {key} ({int(wy) - 4}-{wy})" for k, key in PEOPLE.items()},
                   "hosp": f"{HOSP[0]} {HOSP[1]}", "population": "geo/crosswalk.json pop (2020 Census)"},
    }


def summary(d):
    out = [f"{len(d['geo']['ids'])} barrios; ACS window {d['acs_window']}; summers {d['land_summers']['day']}"]
    for k, v in d["rho"].items():
        out.append(f"  rank correlation {k}: {v['rho']} ({v['n']} barrios)")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="rebuild in memory and compare with the published file")
    a = ap.parse_args(argv)
    new = build()
    if a.check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(json.dumps(new)).items() if k != "built"}
        print("urban_heat.json is current" if same else "urban_heat.json differs from its sources: run python urban_heat.py")
        return 0 if same else 1
    OUT.write_text(json.dumps(new, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(summary(new))
    print(f"wrote {OUT.name}: {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
