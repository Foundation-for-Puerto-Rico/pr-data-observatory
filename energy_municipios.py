"""Energy datasets by municipio and barrio for the Explore and Analysis tabs and the area profiles. HANDOFF decision 104, step 4; docs/energy.md.

    python energy_municipios.py              # build site/data/energy_series.json and site/data/energy_barrio.json from the cache (energy_series.py fills it)
    python energy_municipios.py --refresh    # read the newest LUMA metrics workbook and the ACS files again
    python energy_municipios.py --check      # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Sources, no key:
  LUMA's monthly metrics workbook (case NEPR-MI-2019-0007, read by energy_series.py from the Energy Bureau's site): battery installations and their kWh, electricity
      sales and the share of customers with smart meters, by municipio (LUMA splits San Juan into San Juan, Río Piedras and Santurce: added together; the smart-meter
      share of San Juan is LUMA's for its San Juan area). A year's batteries and smart-meter share are December's; the current year's are the latest month's.
      Sales are calendar years with twelve months.
  ACS 5-year table B25132, Monthly electricity costs (acs_small.py, the table-based summary files): households that pay for electricity separately and those that
      pay $250 or more a month, by municipio, barrio and Puerto Rico, for the windows 2017-2021 to the newest. The share's margin of error follows the Census
      Bureau's formula for a proportion.

Output: energy_series.json (78 municipios and Puerto Rico, in the shape of economy_series.json) and energy_barrio.json (901 barrios; the ACS datasets only).
"""

import datetime
import json
import math
import sys
from pathlib import Path

import acs_small
import facilities as fac
import housing_series as hs
import energy_series as es

ROOT = Path(__file__).resolve().parent
OUT = hs.OUT / "energy_series.json"
OUT_B = hs.OUT / "energy_barrio.json"
log = hs.log
GROUP = "Infrastructure · Energy (LUMA)"
GROUP_ACS = "Infrastructure · Energy (ACS)"
LUMA_REF = "LUMA Energy, monthly metrics workbook filed with the Puerto Rico Energy Bureau (case NEPR-MI-2019-0007), sheet T&D"
ACS_REF = "ACS 5-year B25132, Monthly electricity costs"
ACS_FIRST = 2021


def r(v, d=1):
    return None if v is None else int(round(v)) if d == 0 else round(v, d)


def year_end(series, years, today_year):
    """{year: value}: December's value, or for the current year the latest month's."""
    out = {}
    for y in years:
        ms = sorted(m for m in series if m.startswith(f"{y}-"))
        if not ms:
            continue
        if f"{y}-12" in series:
            out[y] = series[f"{y}-12"]
        elif y == today_year or y == max(years):
            out[y] = series[ms[-1]]
    return out


def ratio_moe(x, mx, y, my):
    """Margin of error of x / y (a proportion, the Census Bureau's formula; the ratio formula when the radicand is negative)."""
    if not y:
        return None
    p = x / y
    rad = mx * mx - p * p * my * my
    if rad < 0:
        rad = mx * mx + p * p * my * my
    return math.sqrt(rad) / y


def acs_vars(M, refresh=False, check=False):
    """The B25132 datasets for every window from ACS_FIRST: {window: {level: {geoid: (pct, pct_moe, n, n_moe, base)}}}."""
    out = {}
    newest = acs_small.latest_vintage() if not check else None
    cache = ROOT / "cache" / "acs_small"
    vintages = sorted(int(p.name) for p in cache.iterdir() if p.is_dir() and p.name.isdigit() and (p / "B25132_municipio.json").exists()) if check else range(ACS_FIRST, newest + 1)
    for v in vintages:
        t = acs_small.read_table("B25132", vintage=v, levels=["island", "municipio", "barrio"], refresh=refresh)
        w = {}
        for lv, rows in t["levels"].items():
            w[lv] = {}
            for g, c in rows.items():
                base, bm = c.get("B25132_003", [None, None])
                n, nm = c.get("B25132_009", [None, None])
                if base is None or n is None:
                    continue
                pct = n / base * 100 if base else None
                moe = ratio_moe(n, nm or 0, base, bm or 0) if base else None
                w[lv][g] = (r(pct, 1), r(moe * 100 if moe is not None else None, 1), n, nm, base)
        out[str(v)] = w
    return out


def build(refresh=False, check=False):
    src = es.sources(refresh=False, check=True) if (check or not refresh) else es.sources(refresh=True)
    mtp = es.cached("metrics_" + src["metrics"].rsplit("/", 1)[-1], src["metrics"], False)
    M = fac.Munis()
    munis = json.loads((hs.OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]
    ids = sorted(str(f["properties"]["GEOID"])[:5] for f in munis)
    by, months = es.metrics(mtp)
    bess = es.muni_series(by, "Total number of BESS installations", M, True)
    kwh = es.muni_series(by, "Total installed BESS capacity", M, True)
    sales = es.muni_series(by, "Monthly sales by Municipality", M, True)
    ami = es.muni_series(by, "Percent of customers on AMI", M, False)
    ami_pr = es.metric(by, "Percent of customers on AMI", "System")
    sales_pr = es.metric(by, "Monthly sales by Municipality", "Total")
    years = sorted({int(m[:4]) for m in months})
    this = max(years)

    def yearly(series_by, pr_series, fn, d):
        out = {}
        for y in years:
            row = []
            for g in ids:
                ye = fn(series_by.get(g, {}), y)
                row.append(r(ye, d))
            pv = fn(pr_series, y) if pr_series is not None else (sum(v for v in row if v is not None) if any(v is not None for v in row) else None)
            if all(v is None for v in row):
                continue
            out[str(y)] = row + [r(pv, d)]
        return out

    end = lambda s, y: year_end(s, [y], this).get(y)
    full = lambda s, y: sum(s[f"{y}-{k:02d}"] for k in range(1, 13)) if all(f"{y}-{k:02d}" in s for k in range(1, 13)) else None
    pct = lambda s, y: (end(s, y) * 100 if end(s, y) is not None else None)
    V_bess = yearly(bess, None, end, 0)
    V_kwh = yearly({g: {m: v / 1000 for m, v in s.items()} for g, s in kwh.items()}, None, end, 1)
    V_sales = yearly(sales, sales_pr, full, 1)
    V_ami = yearly(ami, ami_pr, pct, 1)
    last_m = max(m for s in bess.values() for m in s)
    note_end = f"December of each year; {this} is {datetime.date(int(last_m[:4]), int(last_m[5:]), 1).strftime('%B %Y')}"
    A = acs_vars(M, refresh, check)
    wins = sorted(A)
    bill = {"years": {}, "moe": {}}
    billn = {"years": {}, "moe": {}}
    for w in wins:
        mu, isl = A[w]["municipio"], A[w]["island"]
        prk = next(iter(isl))
        bill["years"][w] = [mu.get(g, (None,) * 5)[0] for g in ids] + [isl[prk][0]]
        bill["moe"][w] = [mu.get(g, (None,) * 5)[1] for g in ids] + [isl[prk][1]]
        billn["years"][w] = [mu.get(g, (None,) * 5)[2] for g in ids] + [isl[prk][2]]
        billn["moe"][w] = [mu.get(g, (None,) * 5)[3] for g in ids] + [isl[prk][3]]
    common = {"family": "energy", "counted": False, "classes": "jenks"}
    vars_ = [
        {"key": "en_batteries", "group": GROUP, "label": "Home and business batteries (installations)", "unit": "", "d": 0, "type": "count", "sources": ["luma_bureau"], "ref": LUMA_REF,
         "definition": f"Battery energy storage systems installed at homes and businesses connected to LUMA's grid, as LUMA counts them in its monthly metrics ({note_end}). Most are paired with rooftop solar.",
         **common, "years": V_bess},
        {"key": "en_battery_mwh", "group": GROUP, "label": "Battery storage, MWh (homes and businesses)", "unit": "MWh", "d": 1, "type": "count", "sources": ["luma_bureau"], "ref": LUMA_REF,
         "definition": f"The energy those batteries can store, in megawatt-hours (LUMA reports kWh; {note_end}).", **common, "noPerHU": False, "years": V_kwh},
        {"key": "en_sales_gwh", "group": GROUP, "label": "Electricity sales, GWh a year", "unit": "GWh", "d": 1, "type": "count", "sources": ["luma_bureau"], "ref": LUMA_REF,
         "definition": "The electricity LUMA sold to customers in the municipio in the calendar year, in gigawatt-hours: homes, businesses, industry and government together. Years with twelve months only.",
         **common, "noPerHU": True, "years": V_sales},
        {"key": "en_ami_pct", "group": GROUP, "label": "Customers with smart meters (%)", "unit": "%", "d": 1, "type": "rate", "sources": ["luma_bureau"], "ref": LUMA_REF,
         "definition": f"The share of LUMA's customers whose meter is a smart (AMI) meter ({note_end}). Empty where LUMA reports no share yet: the meters are being installed.",
         **common, "noPerHU": True, "island": "value", "years": V_ami},
        {"key": "en_bill250_pct", "group": GROUP_ACS, "label": "Households paying $250 or more a month for electricity (%)", "unit": "%", "d": 1, "type": "rate", "sources": ["acs"], "ref": ACS_REF,
         "definition": "Of the occupied housing units that pay for electricity separately, the share whose monthly electricity cost is $250 or more, from the five-year American Community Survey (table B25132); each year is the last year of its window.",
         **common, "noPerHU": True, "barrioFile": "energy_barrio.json", "years": bill["years"], "moe": bill["moe"]},
        {"key": "en_bill250_n", "group": GROUP_ACS, "label": "Households paying $250 or more a month for electricity", "unit": "", "d": 0, "type": "count", "sources": ["acs"], "ref": ACS_REF,
         "definition": "The number of occupied housing units that pay $250 or more a month for electricity (ACS 5-year B25132).", **common, "barrioFile": "energy_barrio.json", "years": billn["years"], "moe": billn["moe"]},
    ]
    for v in vars_:
        if v.get("noPerHU") is False:
            v.pop("noPerHU")
    names = [M.name_of[g] for g in ids] + ["Puerto Rico"]
    out = {"built": src.get("checked") or datetime.date.today().isoformat(), "as_of": last_m, "years": sorted({int(y) for v in vars_ for y in v["years"]}),
           "geo": {"ids": ids + ["72"], "names": names}, "vars": vars_,
           "sources": {"luma_bureau": {"name": "LUMA Energy, filings with the Puerto Rico Energy Bureau (monthly metrics workbook)", "url": "https://energia.pr.gov/en/dockets/?docket=nepr-mi-2019-0007",
                                       "license": "No license stated (public filings)", "note": "Batteries, electricity sales and smart meters by municipio; totals only."},
                       "acs": {"name": "US Census Bureau, American Community Survey 5-year estimates, table B25132", "url": "https://www2.census.gov/programs-surveys/acs/summary_file/",
                               "license": "No license stated by the product page", "note": "Monthly electricity costs of occupied housing units."}},
           "notes": {"san_juan": "LUMA's San Juan, Río Piedras and Santurce areas are added together for batteries and sales; the smart-meter share is LUMA's San Juan area's.",
                     "acs_windows": {w: f"{int(w) - 4}-{w}" for w in wins}, "metrics_file": src["metrics"]}}
    bids = sorted(A[wins[-1]]["barrio"])
    bout = {"built": out["built"], "level": "barrio", "windows": {w: f"{int(w) - 4}-{w}" for w in wins}, "years": [int(w) for w in wins], "geo": {"ids": bids},
            "vars": [{"key": "en_bill250_pct", "years": {w: [A[w]["barrio"].get(b, (None,) * 5)[0] for b in bids] for w in wins}, "moe": {w: [A[w]["barrio"].get(b, (None,) * 5)[1] for b in bids] for w in wins}},
                     {"key": "en_bill250_n", "years": {w: [A[w]["barrio"].get(b, (None,) * 5)[2] for b in bids] for w in wins}, "moe": {w: [A[w]["barrio"].get(b, (None,) * 5)[3] for b in bids] for w in wins}}],
            "notes": {"base": "Occupied housing units that pay for electricity separately (B25132_003); the share is B25132_009 over it."}}
    texts = {OUT: json.dumps(out, ensure_ascii=False, separators=(",", ":")), OUT_B: json.dumps(bout, ensure_ascii=False, separators=(",", ":"))}
    if check:
        bad = [p.name for p, t in texts.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        log(f"energy_series.json and energy_barrio.json {'are' if not bad else 'are NOT'} what the cache gives {bad or ''}")
        return 1 if bad else 0
    for p, t in texts.items():
        p.write_text(t, encoding="utf-8", newline="\n")
    pr = len(ids)
    log(f"wrote {OUT.name}: batteries {V_bess[str(this)][pr]:,} ({last_m}), sales {V_sales.get(str(this - 1), [None] * (pr + 1))[pr]} GWh in {this - 1}, smart meters {V_ami[str(this)][pr]}%, "
        f"bills of $250+ {bill['years'][wins[-1]][pr]}% (ACS {int(wins[-1]) - 4}-{wins[-1]}); {OUT_B.name}: {len(bids)} barrios, windows {wins[0]}-{wins[-1]}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
