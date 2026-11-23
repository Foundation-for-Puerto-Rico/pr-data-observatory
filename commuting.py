"""Daytime population and commuting by municipio, calculated from the Census Bureau's commuting flows. HANDOFF decision 107, step 1; docs/commuting.md.

    python commuting.py              # build site/data/commuting_series.json from the cache (transit_links.py's copy of the flows table)
    python commuting.py --refresh    # download the flows table again
    python commuting.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

A calculated layer (decision 107 names three kinds: calculated, overlaid, estimate): arithmetic on published figures, with nothing assumed.

  daytime_population   residents + workers who come in - workers who leave. The Census Bureau calls it the commuter-adjusted population: the residents, plus
                       the workers who work in the area, minus the workers who live in it (census.gov, Calculating Commuter-Adjusted Population Estimates).
  daytime_change_pct   (workers who come in - workers who leave) / residents x 100: how much a working day adds to, or takes from, the municipio.
  work_elsewhere_pct   of the workers who live in a municipio and work in Puerto Rico, the share who work in another municipio: the figure of
                       transit_links.json (the Connections between municipios page), here with its margin of error.

Sources, no key:
  US Census Bureau, County-to-County Commuting Flows, ACS 2016-2020, Table 1 (the file transit_links.py reads): workers 16 and over by the municipio where
      they live and the one where they work, each flow with a 90 percent margin of error. Workers who come in include the few who live outside Puerto Rico;
      workers who leave include those who work outside Puerto Rico.
  US Census Bureau, 2020 Census: residents of each municipio (site/data/geo/crosswalk.json).

Margins of error (90 percent): the margin of a sum is the square root of the sum of the squares of its flows' margins; the 2020 Census count has none; a share
uses the Census Bureau's proportion formula (housing_series.pct). A sum of many small flows has a wide margin: it is published as it comes out.

Output: commuting_series.json (78 municipios and Puerto Rico, in the shape of economy_series.json; one period, labelled 2020, the last year of the window).
"""

import datetime
import json
import math
import sys
from pathlib import Path

import housing_series as hs
import transit_links as tl
import xlsx_read

ROOT = Path(__file__).resolve().parent
OUT = hs.OUT / "commuting_series.json"
log = hs.log
GROUP = "Population · Daytime population"
YEAR = int(tl.FLOWS_PERIOD.split("-")[1])   # the window is labelled by its last year, as the survey's five-year windows are
FLOWS_REF = "US Census Bureau, County-to-County Commuting Flows, American Community Survey " + tl.FLOWS_PERIOD + " (5-year), Table 1"
WINDOW = {"type": "window", "windowYears": 5}


def num(v):
    return int(str(v).replace(",", ""))


def read_flows(data):
    """(inside, away, from_out) from the flows table: inside {(home geoid, work geoid): (workers, margin)} for homes and workplaces in Puerto Rico (the same
    municipio included); away {home geoid: [(workers, margin)]} for workplaces outside Puerto Rico; from_out {work geoid: [(workers, margin)]} for workers
    who live outside Puerto Rico. Stops when the table is not the release the texts name."""
    title, inside, away, from_out = "", {}, {}, {}
    for r in xlsx_read.rows(data):
        if r.get(0) and "Commuting Flows" in str(r[0]) and not title:
            title = str(r[0])
        if r.get(8) is None or not str(r.get(0) or "").isdigit():
            continue
        flow = (num(r[8]), num(r[9]))
        if r[0] == "72":
            home = "72" + r[1]
            if r.get(4) == "072":
                inside[(home, "72" + r[5])] = flow
            else:
                away.setdefault(home, []).append(flow)
        elif r.get(4) == "072":
            from_out.setdefault("72" + r[5], []).append(flow)
    if tl.FLOWS_PERIOD not in title:
        raise SystemExit(f"commuting: the flows table is not the {tl.FLOWS_PERIOD} release ({title[:120]!r})")
    return inside, away, from_out


def total(flows):
    """(workers, margin) of a list of flows: the margin of a sum is the root of the sum of the squares."""
    return sum(n for n, _ in flows), math.sqrt(sum(m * m for _, m in flows))


def residents():
    """({geoid: residents counted in the 2020 Census}, the crosswalk's basis text) for the 78 municipios."""
    cw = json.loads((hs.OUT / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    f = cw["fields"]
    return {r[f.index("id")]: r[f.index("pop")] for r in cw["units"]["municipio"]}, cw["basis"]


def figures(inside, away, from_out, pop, ids):
    """{key: ([values], [margins])} in the order of ids (the 78 municipios), with Puerto Rico last."""
    out = {k: ([], []) for k in ("daytime_population", "daytime_change_pct", "work_elsewhere_pct")}

    def put(k, v, m):
        out[k][0].append(v)
        out[k][1].append(m)

    def one(res, come, leave, other, in_pr):
        net, net_m = come[0] - leave[0], math.sqrt(come[1] ** 2 + leave[1] ** 2)
        put("daytime_population", res + net, round(net_m))
        put("daytime_change_pct", round(net / res * 100, 2), round(net_m / res * 100, 2))
        put("work_elsewhere_pct", *hs.pct(other, in_pr))

    for g in ids:
        to_other = [v for (h, w), v in inside.items() if h == g and w != g]
        in_pr = [v for (h, w), v in inside.items() if h == g]
        come = [v for (h, w), v in inside.items() if w == g and h != g] + from_out.get(g, [])
        one(pop[g], total(come), total(to_other + away.get(g, [])), total(to_other), total(in_pr))
    # Puerto Rico: only the workers who cross its edge change its daytime population
    one(sum(pop[g] for g in ids), total([v for fl in from_out.values() for v in fl]), total([v for fl in away.values() for v in fl]),
        total([v for (h, w), v in inside.items() if h != w]), total(list(inside.values())))
    return out


def document(inside, away, from_out):
    names, fips = hs.municipalities()
    ids = list(fips)
    pop, basis = residents()
    if set(ids) != set(pop) or {h for h, _ in inside} != set(ids):
        raise SystemExit("commuting: the flows table, the crosswalk and the municipal list do not name the same 78 municipios")
    fig = figures(inside, away, from_out, pop, ids)
    y = str(YEAR)

    def var(key, label, unit, d, typ, definition, sources, **more):
        vals, moes = fig[key]
        return {"key": key, "group": GROUP, "label": label, "unit": unit, "d": d, "type": typ, "sources": sources, "ref": FLOWS_REF, "definition": definition, "family": "commuting",
                "time": WINDOW, "counted": False, **more, "years": {y: vals}, "moe": {y: moes}}

    vs = [
        var("daytime_population", "Daytime population (commuter-adjusted)", "", 0, "count",
            "The people in the municipio on a working day: its residents, plus the workers who come in to work, minus the workers who leave to work elsewhere. Calculated, not surveyed: the Census Bureau's formula for the commuter-adjusted population, with the residents of the 2020 Census and the workers of the 2016-2020 commuting flows. It counts workers only, not students, shoppers or visitors.",
            ["commuting_flows", "census_2020"], noPerHU=True),
        var("daytime_change_pct", "Daytime change in population from commuting, % of residents", "%", 1, "rate",
            "Workers who come in to work minus workers who leave to work elsewhere, as a percent of the municipio's residents. Above zero the municipio fills up on a working day; below zero it empties.",
            ["commuting_flows", "census_2020"], diverging=True, noPerHU=True),
        var("work_elsewhere_pct", "Resident workers who work in another municipio, % of resident workers", "%", 1, "rate",
            "Of the workers who live in the municipio and work in Puerto Rico, the share whose workplace is in another municipio.",
            ["commuting_flows"], noPerHU=True),
    ]
    come_out, leave_out = total([v for fl in from_out.values() for v in fl])[0], total([v for fl in away.values() for v in fl])[0]
    return {"built": datetime.date.today().isoformat(), "years": [YEAR], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs,
            "sources": {"commuting_flows": {"name": FLOWS_REF, "url": "https://www.census.gov/topics/employment/commuting/guidance/flows.html", "license": "US Government work; cite the Census Bureau as the source",
                                            "note": "Workers 16 years and over by the municipio where they live and the one where they work, with a 90 percent margin of error for each flow."},
                        "census_2020": {"name": "US Census Bureau, 2020 Census: residents by municipio", "url": "https://www.census.gov/programs-surveys/decennial-census/decade/2020/2020-census-main.html",
                                        "license": "US Government work; cite the Census Bureau as the source", "note": basis}},
            "notes": {"kind": "calculated: arithmetic on published figures, nothing assumed (HANDOFF decision 107)",
                      "formula": "daytime population = residents + workers who come in - workers who leave (US Census Bureau, Calculating Commuter-Adjusted Population Estimates)",
                      "period": f"flows of {tl.FLOWS_PERIOD}, labelled {YEAR}; residents of the 2020 Census",
                      "outside_puerto_rico": f"{leave_out:,} workers who live in Puerto Rico work outside it and {come_out:,} who work in it live outside it; both are counted",
                      "work_elsewhere": "the workers who work outside Puerto Rico are left out of both sides of the share, as on the Connections between municipios page (transit_links.json)",
                      "margins": "90 percent; the root of the sum of the squares of the flows' margins; the census count has none"}}


def build(refresh=False, check=False):
    doc = document(*read_flows(tl.cached("commuting_flows_2016_2020.xlsx", tl.FLOWS_URL, refresh and not check)))
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        same = old is not None and {**old, "built": None} == {**json.loads(text), "built": None}
        print(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB, {len(doc['vars'])} variables)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
