"""Months for night-time light to come back after Hurricanes María (2017) and Fiona (2022), by barrio and municipio. HANDOFF decision 107, step 5
(second part, row derived-storm-recovery); docs/storm_recovery.md.

    python storm_recovery.py           # build site/data/storm_recovery_series.json and storm_recovery_barrio.json from nightlights_monthly.json
    python storm_recovery.py --check   # rebuild and exit 1 when a published file is not what nightlights_monthly.json gives (nothing written)

No network and no key: the input is the observatory's own monthly night-time light (nightlights.py, NASA Black Marble VNP46A3), one value per area and
month since January 2012. The rule, stated once here and in the notes of the file:

- The year before. Each storm month (September) is compared with the twelve months before it (September to August), month by month: October after the
  storm with the October before it, and so on, so that the seasons (cloudier, darker months) cancel out.
- Back. Light counts as back in the first month after the storm month when it and the next month are both at least BACK (80%) of the same calendar
  month in the year before. Two months in a row, so that one clear month does not count. The figure is the number of months from September:
  1 means back by October.
- Lowest. The lowest month from September to March as a share of the same month the year before.
- Too dim to read. An area whose mean in the year before is under DIM (0.5 nW/cm²/sr) has no figure: its light moves 20% to 70% from one month to the
  next without any storm, more than the 20% the rule allows, so a return could not be told from noise.

The rule is the observatory's, not NASA's or the utility's. Light is a proxy for power and activity; it can stay lower after a storm because homes were
left empty, businesses closed or streetlights were changed to LED (whiter light, which the sensor sees less of). The check is the island's restoration
record: the utility's customers restored (docs/storm_recovery.md).
"""

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
IN = DATA / "nightlights_monthly.json"
OUT_SERIES = DATA / "storm_recovery_series.json"
OUT_BARRIO = DATA / "storm_recovery_barrio.json"

BACK = 0.80   # share of the same month the year before that counts as back
RUN = 2       # months in a row
DIM = 0.5     # nW/cm²/sr: under this mean in the year before, an area has no figure
LOW_MONTHS = 7   # September to March for the lowest month
SENSITIVITY = (0.70, 0.80, 0.90)

STORMS = [
    {"year": 2017, "month": "2017-09", "name": "María", "landfall": "2017-09-20",
     "note": "Hurricane Irma passed north of Puerto Rico on 2017-09-06, in the same month; the September composite holds both."},
    {"year": 2022, "month": "2022-09", "name": "Fiona", "landfall": "2022-09-18", "note": ""},
]
G = "Hazards · Storm recovery (night-time light)"
SOURCES = {
    "nasa_black_marble": {"name": "NASA Black Marble VNP46A3 (Román et al., 2018)", "url": "https://doi.org/10.5067/VIIRS/VNP46A3.002",
                          "license": "NASA data: no restrictions (CC0); cite the product",
                          "note": "Monthly night-time light, read by nightlights.py; this file is calculated from it with a stated rule."},
    "census_tiger": {"name": "US Census Bureau, TIGER/Line (barrio and municipio outlines)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "The outlines that assign each pixel to a barrio."},
}


def recovery(series, s, back=BACK, run=RUN, dim=DIM):
    """(months to come back or None, lowest share in %, why) for one area's monthly values and the storm month's index s."""
    base = series[s - 12:s]   # September of the year before to August; base[(k - s) % 12] is the same calendar month as k
    if any(v is None for v in base) or sum(base) / 12 < dim:
        return None, None, "dim"
    if min(base) <= 0:
        return None, None, "dim"

    def ratio(k):
        v = series[k]
        return None if v is None else v / base[(k - s) % 12]
    lows = [ratio(k) for k in range(s, min(s + LOW_MONTHS, len(series)))]
    low = round(100 * min(r for r in lows if r is not None)) if any(r is not None for r in lows) else None
    for k in range(s + 1, len(series) - run + 1):
        if all((ratio(j) or 0) >= back for j in range(k, k + run)):
            return k - s, low, "back"
    return None, low, "not_back"


def assemble(mon):
    months = mon["months"]
    M, B = mon["municipio"], mon["barrio"]
    idx = {st["year"]: months.index(st["month"]) for st in STORMS}
    for st in STORMS:
        if idx[st["year"]] < 12:
            raise SystemExit(f"storm_recovery: fewer than twelve months before {st['month']}")
    years = [st["year"] for st in STORMS]

    def level(L):
        out, low, why = {}, {}, {}
        for y in years:
            r = [recovery(row, idx[y]) for row in L["ntl_radiance"]]
            out[str(y)], low[str(y)], why[str(y)] = [x[0] for x in r], [x[1] for x in r], [x[2] for x in r]
        return out, low, why
    m_back, m_low, m_why = level(M)
    b_back, b_low, b_why = level(B)

    def tally(why):
        return {y: {k: w.count(k) for k in ("back", "dim", "not_back")} for y, w in why.items()}

    def quart(vals):
        v = sorted(x for x in vals if x is not None)
        return {"p10": v[int(0.1 * (len(v) - 1))], "median": v[int(0.5 * (len(v) - 1))], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1]} if v else None
    isl = M["ntl_radiance"][-1]
    sens = {str(st["year"]): {f"{int(100 * t)}%": recovery(isl, idx[st["year"]], back=t)[0] for t in SENSITIVITY} for st in STORMS}
    sens_b = {str(st["year"]): {f"{int(100 * t)}%": quart([recovery(r, idx[st["year"]], back=t)[0] for r in B["ntl_radiance"]]) for t in SENSITIVITY} for st in STORMS}
    last = months[-1]
    storms = {str(st["year"]): {"name": st["name"], "landfall": st["landfall"], "storm_month": st["month"],
                                "year_before": f"{months[idx[st['year']] - 12]} to {months[idx[st['year']] - 1]}",
                                "island_back": m_back[str(st["year"])][-1], "island_lowest_pct": m_low[str(st["year"])][-1],
                                "island_back_month": months[idx[st["year"]] + m_back[str(st["year"])][-1]] if m_back[str(st["year"])][-1] is not None else None,
                                **({"note": st["note"]} if st["note"] else {})} for st in STORMS}
    RULE = (f"Each month after the storm is compared with the same month in the twelve months before the storm month (September to August). "
            f"Light counts as back in the first month after September when it and the next month are both at least {int(100 * BACK)}% of the same month the year before; "
            f"the figure counts months from September (1 means back by October). Areas with a mean under {DIM} nW/cm²/sr in the year before are too dim to read and have no figure.")
    CAV = (" Light is a proxy for power and activity, not a count of homes with power. It can stay lower after a storm because homes were left empty, businesses closed "
           "or streetlights were changed to LED (whiter light, which the sensor sees less of), and a month is a composite of its clear nights, so an outage shorter than "
           "a few weeks barely shows. The rule is the observatory's; the island's figures agree with the utility's record of customers restored (docs/storm_recovery.md).")
    REF = ("Calculated by the observatory from NASA Black Marble VNP46A3 (collection 2) monthly night-time light, as read by nightlights.py (pixels of about 460 m, "
           "pooled by barrio, municipio and Puerto Rico); Román et al. (2018)")

    def var(key, label, unit, d, typ, definition, vals):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["nasa_black_marble", "census_tiger"], "ref": REF,
                "definition": definition, "family": "storm_recovery", "counted": False, "noPerHU": True, "barrioFile": OUT_BARRIO.name, "years": vals}
    YEARS = " The year 2017 is Hurricane María (with Irma earlier that month); 2022 is Hurricane Fiona."
    vs = [var("storm_months_back", "Months until night-time light came back after the hurricane", "months", 0, "rate",
              "The months from the hurricane's month (September) until the area's night-time light was back to at least 80% of the same month the year before, "
              "two months in a row. 1 means back by October." + YEARS + " " + RULE + CAV, {y: m_back[y] for y in m_back}),
          var("storm_low_light_pct", "Night-time light at its lowest after the hurricane (% of the year before)", "%", 0, "rate",
              "The area's darkest month from September to March after the hurricane, as a share of the same month the year before. 100 means no drop; "
              "a low share means a deep blackout that lasted most of a month." + YEARS + " " + RULE + CAV, {y: m_low[y] for y in m_low})]
    notes = {"rule": RULE, "back": BACK, "months_in_a_row": RUN, "dim": DIM, "input": IN.name, "input_last_month": last, "storms": storms,
             "municipio": tally(m_why), "barrio": tally(b_why),
             "barrio_months_back": {y: quart(v) for y, v in b_back.items()},
             "sensitivity": {"island": sens, "barrio": sens_b},
             "check": {"2017": "Army Corps of Engineers: 98.4% of the utility's customers restored in mid-May 2018; EIA: 95% by mid-April 2018 (eia.gov/todayinenergy/detail.php?id=36832)",
                       "2022": "LUMA: 90% of customers restored on 2022-10-01 (publicpower.org, 'Power restored to more than 1.3 million customers in Puerto Rico'). "
                               "EAGLE-I (Oak Ridge National Laboratory, CC BY 4.0, figshare 24237376): customers out fell to 10% of the peak or fewer between 2022-09-29 and 2022-10-10 in each of the seven LUMA regions, Mayagüez last"}}
    series = {"as_of": last, "years": years, "geo": {"ids": M["ids"], "names": None}, "vars": vs, "sources": SOURCES, "notes": notes}
    barrio = {"level": "barrio", "years": years, "geo": {"ids": B["ids"]},
              "vars": [{"key": "storm_months_back", "years": b_back}, {"key": "storm_low_light_pct", "years": b_low}],
              "notes": {"areas": len(B["ids"]), "source": "storm_recovery.py; the municipio values and the rule are in storm_recovery_series.json"}}
    return series, barrio


def build(check=False):
    if not IN.exists():
        print(f"storm_recovery: {IN.name} is missing (python nightlights.py builds it)")
        return 1 if check else 0
    mon = json.loads(IN.read_text(encoding="utf-8"))
    series, barrio = assemble(mon)
    names = json.loads((DATA / "nightlights_series.json").read_text(encoding="utf-8"))["geo"]
    if names["ids"] != series["geo"]["ids"]:
        raise SystemExit("storm_recovery: the monthly file's municipios are not those of nightlights_series.json")
    series["geo"]["names"] = names["names"]
    status = 0
    for path, d in ((OUT_SERIES, series), (OUT_BARRIO, barrio)):
        text = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            same = old is not None and {**old, "built": None} == {**json.loads(text), "built": None}
            print(f"  {path.name}: {'matches' if same else 'DIFFERS'}")
            status |= 0 if same else 1
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        print(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--check" in sys.argv))
