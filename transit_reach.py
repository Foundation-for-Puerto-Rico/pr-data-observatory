"""Transit by barrio: which of the 901 barrios have a stop with a current timetable, which have only service without one, and which have none on file.

  python transit_reach.py            write site/data/transit_reach.json from files already in site/data (no network)
  python transit_reach.py --check    rebuild for the published file's date and exit 1 when it differs (nothing written)
  python transit_reach.py --as-of 2026-11-21

The data of the Knowledge Area page transit-reach.html (docs/analysis/transit-reach-2026-11/make_page.py). Each barrio gets one class, by what lies inside it:
  3 timetable  a stop of ATI or a municipal system whose timetable (GTFS feed) has not ended on as_of (access.feed_current, the rule of exposure.py)
  2 other      no such stop, but a stop whose timetable has ended, a stop mapped in OpenStreetMap, or a route of the 2020 list of públicos
  1 none       nothing in these lists
and a flag `passes`: a route with a current timetable crosses the barrio but has no stop in it. A barrio with no 2020 residents keeps its class but is
drawn apart. The page describes what the published lists hold; it is not a measure of service and recommends nothing (the plan's decision 4 keeps
recommendations for FPR leadership). Inputs, all in site/data: barrios.geojson, transport.json, operators.json, transit_routes.geojson, publicos.geojson,
exposure_barrio.json (2020 residents and residents within 400 m of a current stop) and acs_barrio.json (households, households with no vehicle: ACS B25044).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

import access

DATA = Path(__file__).resolve().parent / "site" / "data"
OUT = "transit_reach.json"
SCHEDULED = ("ati_gtfs", "muni_gtfs")
OSM_STOPS = ("bus_stop", "bus_station", "rail_station", "ferry_terminal")
MIN_POP = 500   # fewer residents than this, or a margin as large as the estimate: the vehicle share is marked unreliable (the rule of transit_needs.py)
ACS_WINDOW = "2024"
BARRIO_FIELDS = ["geoid", "name", "mun", "cls", "passes", "cur", "expired", "osm", "publicos", "pop", "pop_400m", "hh", "noveh_pct", "noveh_moe", "low"]
MUNI_FIELDS = ["geoid", "name", "barrios", "b3", "b2", "b1", "pop", "p3", "p2", "p1", "passes", "system", "ntd_no_feed"]


def load(name, data_dir):
    return json.loads((data_dir / name).read_text(encoding="utf-8"))


def by_id(doc_ids, values):
    return dict(zip(doc_ids, values))


def contained(tree, polys, geoms):
    """For each geometry, the indexes of the polygons it falls in (a point) or crosses (a line)."""
    out = []
    for g in geoms:
        out.append([i for i in tree.query(g) if polys[i].intersects(g)])
    return out


def classify(cur, expired, osm, publicos):
    return 3 if cur else 2 if (expired or osm or publicos) else 1


def build(data_dir=DATA, as_of=None):
    as_of = as_of or date.today()
    B = load("barrios.geojson", data_dir)["features"]
    polys = [shape(f["geometry"]) for f in B]
    tree = STRtree(polys)
    ops = load("operators.json", data_dir)
    current = access.current_operators(ops["operators"], as_of)
    n = len(B)
    cur, expired, osm, publicos, passes = [0] * n, [0] * n, [0] * n, [0] * n, [0] * n

    stops = [s for s in load("transport.json", data_dir) if s.get("source") in SCHEDULED or (s.get("source") == "osm_transport" and s.get("kind") in OSM_STOPS)]
    for s, hits in zip(stops, contained(tree, polys, [Point(s["lng"], s["lat"]) for s in stops])):
        for i in hits[:1]:   # a point on a shared edge counts once
            if s["source"] in SCHEDULED:
                (cur if s.get("operator") in current else expired)[i] += 1
            else:
                osm[i] += 1

    for hits in contained(tree, polys, [shape(f["geometry"]) for f in load("publicos.geojson", data_dir)["features"]]):
        for i in hits:
            publicos[i] += 1

    routes = [f for f in load("transit_routes.geojson", data_dir)["features"] if f["properties"]["operator"] in current]
    for hits in contained(tree, polys, [shape(f["geometry"]) for f in routes]):
        for i in hits:
            passes[i] = 1

    E = load("exposure_barrio.json", data_dir)
    pop = by_id(E["geo"]["ids"], E["total"]["pop"])
    near = by_id(E["geo"]["ids"], E["vars"]["stop_cur"]["pop"])
    A = load("acs_barrio.json", data_dir)
    acs = {v["key"]: v for v in A["vars"]}

    def acs_of(key):
        return by_id(A["geo"]["ids"], acs[key]["years"][ACS_WINDOW]), by_id(A["geo"]["ids"], (acs[key].get("moe") or {}).get(ACS_WINDOW) or [None] * len(A["geo"]["ids"]))

    hh, _ = acs_of("households")
    nv, nv_moe = acs_of("no_vehicle_hh_pct")

    rows = []
    for i, f in enumerate(B):
        p = f["properties"]
        g, c = p["geoid"], classify(cur[i], expired[i], osm[i], publicos[i])
        v, m, people = nv.get(g), nv_moe.get(g), pop.get(g, 0)
        low = int(v is None or people < MIN_POP or (m is not None and m >= v and v > 0))
        rows.append([g, p["barrio"], g[:5], c, int(passes[i] and c < 3), cur[i], expired[i], osm[i], publicos[i], people, near.get(g, 0),
                     hh.get(g), v, m, low])
    rows.sort(key=lambda r: r[0])

    names = {f["properties"]["geoid"][:5]: f["properties"]["municipality"] for f in B}
    system = {}
    for o in ops["operators"]:
        if o.get("type") == "municipal" and o.get("municipality"):
            system[o["municipality"]] = "none" if (o.get("feed") or {}).get("status") == "none" else ("current" if access.feed_current(o, as_of) else "expired")
    munis = []
    for mg in sorted(names):
        rs = [r for r in rows if r[2] == mg]
        cnt = {k: sum(1 for r in rs if r[3] == k) for k in (3, 2, 1)}
        pp = {k: sum(r[9] for r in rs if r[3] == k) for k in (3, 2, 1)}
        sysn = system.get(names[mg])
        munis.append([mg, names[mg], len(rs), cnt[3], cnt[2], cnt[1], sum(r[9] for r in rs), pp[3], pp[2], pp[1], sum(r[4] for r in rs), sysn, int(sysn == "none")])

    tot_pop = sum(r[9] for r in rows)
    pr = {
        "barrios": n, "with_residents": sum(1 for r in rows if r[9] > 0),
        "b3": sum(1 for r in rows if r[3] == 3), "b2": sum(1 for r in rows if r[3] == 2), "b1": sum(1 for r in rows if r[3] == 1),
        "passes": sum(r[4] for r in rows), "pop": tot_pop,
        "p3": sum(r[9] for r in rows if r[3] == 3), "p2": sum(r[9] for r in rows if r[3] == 2), "p1": sum(r[9] for r in rows if r[3] == 1),
        "pop_passes": sum(r[9] for r in rows if r[4]),
        "pop_400m": sum(near.values()), "pop_400m_as_of": E["as_of"],
        "munis_no_timetable": sum(1 for m in munis if m[3] == 0), "munis_ntd_no_feed": sum(m[12] for m in munis),
        "hh_no_vehicle_outside": round(sum((r[11] or 0) * (r[12] or 0) / 100 for r in rows if r[3] < 3)),
        "hh_no_vehicle": round(sum((r[11] or 0) * (r[12] or 0) / 100 for r in rows)),
    }
    pr["p_out"] = pr["p2"] + pr["p1"]
    for k in ("p3", "p2", "p1", "p_out", "pop_400m", "pop_passes"):
        pr[k + "_share"] = round(pr[k] / tot_pop * 100, 1)

    lines = []   # the red lines of the map: Tren Urbano and the ferries, coordinates rounded to about 10 m
    for f in routes:
        if f["properties"]["mode"] in ("rail", "ferry"):
            g = f["geometry"]
            parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
            lines.append({"mode": f["properties"]["mode"], "name": f["properties"]["long_name"], "c": [[[round(x, 4), round(y, 4)] for x, y in part] for part in parts]})

    return {
        "as_of": as_of.isoformat(), "rules": {"current": "the operator's GTFS feed ends on or after as_of", "contains": "point in polygon; a route counts where it crosses the barrio",
                                               "min_pop": MIN_POP, "acs": f"ACS 5-year {int(ACS_WINDOW) - 4}-{ACS_WINDOW}, table B25044"},
        "inputs": {"operators": ops.get("built"), "exposure": E.get("as_of"), "acs": A.get("built"), "publicos": "2020-03-19"},
        "pr": pr, "barrio_fields": BARRIO_FIELDS, "barrios": rows, "muni_fields": MUNI_FIELDS, "municipios": munis, "lines": lines,
    }


def dump(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--as-of")
    a = ap.parse_args(argv)
    path = DATA / OUT
    if a.check:
        old = path.read_text(encoding="utf-8")
        new = dump(build(as_of=date.fromisoformat(json.loads(old)["as_of"])))
        if new != old:
            print(f"{OUT} is not what the files in site/data give; run python transit_reach.py")
            return 1
        print(f"{OUT} matches")
        return 0
    doc = build(as_of=date.fromisoformat(a.as_of) if a.as_of else None)
    text = dump(doc)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        print(f"{OUT} unchanged")
        return 0
    path.write_text(text, encoding="utf-8", newline="\n")
    p = doc["pr"]
    print(f"wrote {OUT}: {p['b3']} barrios with a current timetable, {p['b2']} with other service only, {p['b1']} with none; {p['passes']} where a route passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
