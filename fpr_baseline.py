"""FPR's Eastern Region baseline layers for the PR Data Observatory: what FPR's own field work found and no public source publishes.

    python fpr_baseline.py     # build the two files below

Source: FPR's Eastern Region baseline dashboard (Power BI, "Baseline dashboard CIH", 2025), read 2026-10-23, and the routes FPR traced in ArcGIS Pro for
it. Each layer is a file kept by hand in this folder; edit it and run the script again. The dashboard's other topics are not here: its outage figures
(SAIDI, SAIFI) are the Energy Bureau's, which LUMA files every month (wanted.json, power-reliability).

    fpr_vertederos_clandestinos.csv  -> illegal_dumping.geojson   illegal dumping sites FPR found at or near natural and cultural assets, at the
                                                                  point the survey recorded; size and kinds of waste as the form names them
    fpr_rutas_municipales.geojson    -> fpr_routes.geojson        municipal routes FPR traced in ArcGIS Pro (Municipalroutes_ExportFeatures, exported to WGS 84);
                                                                  only the segments the observatory's routes (transit_routes.geojson, refreshed nightly)
                                                                  cover less than halfway within 75 m are published, so a route that gains a timetable
                                                                  feed leaves this layer at the next run. To update, export the layer again to this file
                                                                  (keep the properties tramo, nombre, operador, fuente, nota)

The dashboard's names were tidied (accents) and its "Rio Grande" and "Loiza" spelled as the municipios are. The survey's free-text comments are not published.
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import transform as stransform
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from municipalities import MUNICIPALITY_NAMES

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "data"
VINTAGE = "2025"   # the dashboard's survey; the form records no date for each visit
DUMP_CSV = ROOT / "fpr_vertederos_clandestinos.csv"
DUMP_COLS = ["punto", "activo_cercano", "municipio", "tamano", "residuos", "quema", "lat", "lng", "nota"]
ROUTES_SRC = ROOT / "fpr_rutas_municipales.geojson"
ROUTE_PROPS = ["tramo", "nombre", "operador", "fuente", "nota"]
NEAR_ROUTE, COVERED = 75, 0.5   # meters from an observatory route, and the share of a segment within it that counts as covered
TO_M = Transformer.from_crs(4326, 32161, always_xy=True)   # Puerto Rico State Plane, meters
SIZES = {"pequeño": "Small (about 13 gallons, a kitchen bag)", "mediano": "Medium (about 30 gallons, a yard bag)", "grande": "Large (more than 50 gallons)"}
WASTE = {"reciclables": "recyclables", "orgánicos": "organic", "generales": "general waste", "escombros": "construction debris", "enseres": "appliances", "peligrosos": "hazardous materials"}


def read(path, cols):
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and list(rows[0]) == cols, f"{path.name} must have the columns {cols}"
    for n, r in enumerate(rows, 2):   # a row with a comma too many or too few shifts its values into the wrong columns
        assert None not in r and None not in r.values(), f"{path.name}, line {n}: {len(cols)} columns expected"
        assert r["municipio"] in MUNICIPALITY_NAMES, f"{path.name}: unknown municipio {r['municipio']!r}"
    return rows


def metric(g):
    return stransform(g, lambda xy: np.column_stack(TO_M.transform(xy[:, 0], xy[:, 1])))


def routes(munis, geoid):
    """The traced segments that the observatory's routes do not cover: [(feature, km)], and how many were left out as covered."""
    src = json.loads(ROUTES_SRC.read_text(encoding="utf-8"))["features"]
    obs = [metric(shape(f["geometry"])) for f in json.loads((OUT / "transit_routes.geojson").read_text(encoding="utf-8"))["features"]]
    tree, mm = STRtree(obs), {m: metric(a) for m, a in munis.items()}
    out, covered = [], 0
    for f in src:
        p = f["properties"]
        assert set(p) == set(ROUTE_PROPS), f"{ROUTES_SRC.name}: segment {p.get('tramo')} must have the properties {ROUTE_PROPS}"
        g = shape(f["geometry"])
        gm = metric(g)
        near = [obs[i] for i in tree.query(gm.buffer(NEAR_ROUTE))]
        share = gm.intersection(unary_union(near).buffer(NEAR_ROUTE)).length / gm.length if near else 0
        if share >= COVERED:
            covered += 1
            continue
        m = max(mm, key=lambda k: mm[k].intersection(gm).length)
        assert mm[m].intersection(gm).length > 0, f"{ROUTES_SRC.name}: segment {p['tramo']} is outside Puerto Rico"
        geom = mapping(g)
        geom = {"type": geom["type"], "coordinates": json.loads(json.dumps(geom["coordinates"]), parse_float=lambda x: round(float(x), 5))}
        out.append(({"type": "Feature", "properties": {"name": p["nombre"] or None, "type": "Municipal route mapped by FPR", "municipio": m, "geoid": geoid[m],
                                                       "operator": p["operador"] or None, "km": round(gm.length / 1000, 1), "covered_pct": round(100 * share)},
                     "geometry": geom}, gm.length / 1000))
    return out, covered, len(src)


def feature(props, lat, lng):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [round(float(lng), 5), round(float(lat), 5)]}}


def write(name, feats, notes):
    doc = {"type": "FeatureCollection", "source": "fpr_baseline", "vintage": VINTAGE, "notes": notes, "features": feats}
    (OUT / name).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build():
    print("FPR Eastern Region baseline (fpr_*)")
    mdoc = json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]
    munis = {f["properties"]["municipality"]: shape(f["geometry"]) for f in mdoc}
    geoid = {f["properties"]["municipality"]: f["properties"]["GEOID"] for f in mdoc}

    dumps = read(DUMP_CSV, DUMP_COLS)
    feats = []
    for d in dumps:   # a typo in coordinates edited by hand: 0.001° (about 100 m) lets a shoreline point sit just off the coast
        assert munis[d["municipio"]].distance(Point(float(d["lng"]), float(d["lat"]))) < 0.001, f"dumping site {d['punto']} is not in {d['municipio']}"
        assert d["tamano"] in SIZES, f"dumping site {d['punto']}: size {d['tamano']!r} is not one of {list(SIZES)}"
        kinds = [k.strip() for k in d["residuos"].split(",")]
        assert all(k in WASTE for k in kinds), f"dumping site {d['punto']}: unknown kind of waste in {d['residuos']!r}"
        feats.append(feature({"name": d["activo_cercano"], "type": "Illegal dumping site", "municipio": d["municipio"], "geoid": geoid[d["municipio"]],
                              "size": SIZES[d["tamano"]], "waste": [WASTE[k] for k in kinds], "burning": d["quema"] == "sí"}, d["lat"], d["lng"]))
    write("illegal_dumping.geojson", feats, {"sites": len(feats), "municipios": len({d["municipio"] for d in dumps})})
    print(f"  illegal dumping: {len(feats)} sites in {len({d['municipio'] for d in dumps})} municipios")

    kept, covered, traced = routes(munis, geoid)
    km = {}
    for f, k in kept:
        km[f["properties"]["municipio"]] = round(km.get(f["properties"]["municipio"], 0) + k, 1)
    write("fpr_routes.geojson", [f for f, _ in kept], {"segments": len(kept), "traced": traced, "covered_left_out": covered, "km": round(sum(k for _, k in kept), 1),
                                                       "km_by_municipio": km, "near_m": NEAR_ROUTE, "covered_share": COVERED})
    print(f"  municipal routes: {len(kept)} of {traced} traced segments published ({sum(k for _, k in kept):.1f} km); {covered} left out (the observatory's routes cover them); km published by municipio: {km}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
