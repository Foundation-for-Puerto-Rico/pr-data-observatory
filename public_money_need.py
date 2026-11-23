"""Public money compared with need, by municipio: the data of the Knowledge Area page public-money.html (Public money v2, step 5; 2026-10-31;
HUD's CDBG money added under HANDOFF decision 100, 2026-11-12).

The page asks where FEMA's disaster money and the need for it line up and where they do not, and states the facts without drawing conclusions.
It adds no source: every figure is read from data files the site already publishes.

    python public_money_need.py            # reads site/data/*_series.json, writes site/data/public_money_need.json and prints the island figures
    python public_money_need.py --check    # rebuilds in memory and compares with the published file (no write)

Money (FEMA, disasters declared or grants of fiscal years 2017 to 2025: hurricanes Irma and María, the 2020 earthquakes, Fiona and later):
  pa    Public Assistance obligated, federal share, by applicant municipio and declaration year     economy_series.json fema_pa_obligated
  ia    Individual Assistance approved for owners and renters, by declaration year                   housing_series.json fema_ia_amount
  hma   Hazard Mitigation Assistance, federal share approved, by benefiting municipio and fiscal year economy_series.json hma_approved_federal
Each is summed over the years and divided by the municipio's 2020 Census residents. The island total keeps the money that cannot be placed in a
municipio ("statewide"), so the page can say how much of each program the map shows.

Money (HUD Community Development Block Grants, federal fiscal years 2019 to the last final one, obligations; read from USAspending):
  cdbg_dr  CDBG-DR and CDBG-MIT subawards of the Puerto Rico Department of Housing, by municipio of the work       spending_cdbgdr.json (cdbg_dr.py)
  cdbg     yearly CDBG: entitlement grants HUD pays to 27 municipios, plus the subawards of the state program      spending_cdbg.json (cdbg_regular.py)
           that the Department of Housing passes to the other municipios
The island total of each is the prime grants' obligations over the same years; what is not placed is what the Department of Housing keeps for its
own programs, has not passed on yet, or reports with no municipio. The FEMA and HUD money are on different time bases (year a disaster was declared
or a FEMA grant's fiscal year; year HUD obligated the money) and are never added together.

Need (two measures, never combined):
  eal   FEMA National Risk Index, expected annual loss from natural hazards, $ a year (a model estimate)   environment_series.json nri_eal_total
  cre3  Census Community Resilience Estimates: residents with three or more risk factors, %, latest year  hazard_series.json cre_risk3_pct

Hazard Mitigation by status, the same years: federal share approved, federal money obligated, federal share awaiting a FEMA decision and the
number of approved subapplications (economy_series.json hma_*). FEMA reports a payment for few subapplications (notes.hma_payment_reported),
so money paid is not shown.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT = DATA / "public_money_need.json"
FIRST, LAST = 2017, 2025
POP_YEAR = "2020"
MONEY = {"pa": ("economy_series.json", "fema_pa_obligated"), "ia": ("housing_series.json", "fema_ia_amount"), "hma": ("economy_series.json", "hma_approved_federal")}
NEED = {"eal": ("environment_series.json", "nri_eal_total"), "cre3": ("hazard_series.json", "cre_risk3_pct")}
HUD = {"cdbg_dr": "spending_cdbgdr.json", "cdbg": "spending_cdbg.json"}
HMA = {"approved": "hma_approved_federal", "obligated": "hma_obligated", "pending": "hma_pending_federal", "projects": "hma_projects"}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def series(doc, key):
    for v in doc["vars"]:
        if v["key"] == key:
            if not isinstance(v.get("years"), dict):
                raise SystemExit(f"public_money_need: {key} has no values in this file")
            return v
    raise SystemExit(f"public_money_need: no {key}")


def summed(doc, key, n):
    """The years FIRST to LAST added up, for the n municipios and the island (last); a blank year adds nothing."""
    out = [0.0] * (n + 1)
    for y, col in series(doc, key)["years"].items():
        if FIRST <= int(y) <= LAST:
            if len(col) != n + 1:
                raise SystemExit(f"public_money_need: {key} {y} has {len(col)} values, not {n + 1}")
            for i, x in enumerate(col):
                out[i] += x or 0
    return [round(x) for x in out]


def hud_money(ids):
    """HUD's CDBG money by municipio, summed over the fiscal years of its file: {key: {placed: [dollars in geo order], total: prime grants}}, the
    parts of the yearly CDBG (entitlement grants and state subawards, each by municipio, and their island totals), the years and the build dates."""
    out, years, built = {}, {}, {}
    for k, f in HUD.items():
        d = load(f)
        if d["geo"]["ids"] != ids:
            raise SystemExit(f"public_money_need: {f} lists its places in another order")
        years[k], built[f"usaspending_{k}"] = [d["years"][0], d["years"][-1]], d["built"]
        col = lambda rows: [round(sum(yr[i] for yr in rows)) for i in range(len(ids))]
        if k == "cdbg_dr":
            out[k] = {"placed": col(d["by_muni"]), "total": round(sum(d["prime"]))}
        else:
            ent, st = col(d["entitlement"]), col(d["state_by_muni"])
            out[k] = {"placed": [a + b for a, b in zip(ent, st)], "total": round(sum(d["entitlement_total"]) + sum(d["state_prime"]))}
            parts = {"entitlement": ent, "state": st, "entitlement_total": round(sum(d["entitlement_total"])), "state_prime": round(sum(d["state_prime"])),
                     "state_subawards": round(sum(d["state_subawards"])), "entitlement_municipios": sum(1 for x in ent if x)}
    dr = load(HUD["cdbg_dr"])
    parts["dr_subawards"] = round(sum(dr["subawards"]))
    return out, parts, years, built


def build():
    docs = {f: load(f) for f in {f for f, _ in [*MONEY.values(), *NEED.values()]} | {"housing_series.json"}}
    econ = docs["economy_series.json"]
    ids, names = econ["geo"]["ids"][:-1], econ["geo"]["names"][:-1]
    n = len(ids)
    if n != 78 or econ["geo"]["ids"][-1] != "72":
        raise SystemExit("public_money_need: economy_series.json does not list the 78 municipios and Puerto Rico")
    for f, d in docs.items():
        if d["geo"]["ids"] != econ["geo"]["ids"]:
            raise SystemExit(f"public_money_need: {f} lists its places in another order")
    pop = series(docs["housing_series.json"], "population")["years"][POP_YEAR]
    if any(not p for p in pop[:n]):
        raise SystemExit("public_money_need: a municipio has no 2020 population")

    money, island = {}, {}
    for k, (f, key) in MONEY.items():
        s = summed(docs[f], key, n)
        money[k] = s[:n]
        island[k] = {"total": s[n], "placed": sum(s[:n])}
        if island[k]["placed"] > island[k]["total"] * 1.0001:   # placed money never exceeds the island's, which also holds the statewide money
            raise SystemExit(f"public_money_need: the municipios of {k} add up to more than Puerto Rico")

    need, need_year = {}, {}
    eal = series(docs["environment_series.json"], NEED["eal"][1])
    (y_eal, col), = eal["years"].items()
    need["eal"] = [round(x) for x in col[:n]]
    need_year["eal"] = docs["environment_series.json"]["notes"]["nri"]["version"]
    cre = series(docs["hazard_series.json"], NEED["cre3"][1])
    y_cre = max(cre["years"], key=int)
    need["cre3"] = cre["years"][y_cre][:n]
    need_year["cre3"] = int(y_cre)
    for k, v in need.items():
        if any(x is None for x in v):
            raise SystemExit(f"public_money_need: {k} has a blank municipio")

    hma, hma_island = {}, {}
    for k, key in HMA.items():
        s = summed(econ, key, n)
        hma[k], hma_island[k] = s[:n], s[n]
    hud, hud_parts, hud_years, hud_built = hud_money(ids)
    for k, v in hud.items():
        money[k] = v["placed"]
        island[k] = {"total": v["total"], "placed": sum(v["placed"])}
        if island[k]["placed"] > island[k]["total"] * 1.0001:
            raise SystemExit(f"public_money_need: the municipios of {k} add up to more than the prime grants")
    notes = econ["notes"]
    return {
        "version": 1,
        "built": date.today().isoformat(),
        "level": "municipio",
        "years": {"first": FIRST, "last": LAST},
        "geo": {"level": "municipio", "ids": ids, "names": names},
        "population": pop[:n],
        "population_year": int(POP_YEAR),
        "money": money,
        "island": island,
        "need": need,
        "need_year": need_year,
        "hma": hma,
        "hma_island": hma_island,
        "money_years": {**{k: [FIRST, LAST] for k in MONEY}, **hud_years},
        "cdbg_parts": hud_parts,
        "inputs": {k: f"{f} {key}" for k, (f, key) in {**MONEY, **NEED}.items()} | {f"hma_{k}": f"economy_series.json {v}" for k, v in HMA.items()} | HUD,
        "retrieved": {"openfema_pa": notes.get("fema_pa_retrieved"), "openfema_hma": notes.get("hma_retrieved"), "nri": need_year["eal"], "cre": need_year["cre3"], **hud_built},
        "notes": {"hma_subapplications": notes.get("hma_subapplications"), "hma_payment_reported": notes.get("hma_payment_reported")},
    }


def summary(d):
    out = []
    for k, v in d["island"].items():
        if not v["total"]:
            continue
        out.append(f"{k}: Puerto Rico ${v['total'] / 1e9:.2f} B, placed in municipios ${v['placed'] / 1e9:.2f} B ({100 * v['placed'] / v['total']:.1f}%)")
    h = d["hma_island"]
    out.append(f"hma: approved ${h['approved'] / 1e9:.2f} B, obligated ${h['obligated'] / 1e9:.2f} B, awaiting a decision ${h['pending'] / 1e9:.2f} B, {h['projects']} approved subapplications")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="rebuild in memory and compare with the published file")
    a = ap.parse_args(argv)
    new = build()
    if a.check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(json.dumps(new)).items() if k != "built"}
        print("public_money_need.json is current" if same else "public_money_need.json differs from its sources: run python public_money_need.py")
        return 0 if same else 1
    OUT.write_text(json.dumps(new, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(summary(new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
