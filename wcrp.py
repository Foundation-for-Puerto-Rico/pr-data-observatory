"""WCRP communities layer for the PR Data Observatory: one point per community in FPR's Whole Community Resilience Planning program.

    python wcrp.py     # place the rows of wcrp_comunidades.csv that have no point yet, then build site/data/wcrp.geojson

Source: wcrp_comunidades.csv, one row per community (name, municipality, WCRP region, plan status, subrecipient). 69 rows are
the WCRP-RAG list_comunidades list of 2026-10-06 (72 less the three population plans). The other 7, led by UPR Mayagüez, come from FPR's Smartsheet tracker
(TRACKER_Planning Phases, 79 communities) because they are in phase 1 and the WCRP-RAG has no documents for them yet; no source
gives a WCRP region for 4 of them, so region stays empty. The plans define each community's area only in a PDF map, so the layer
is points, not outlines, and each point says where it comes from (column ubicacion):

    comunidad_especial  a point inside the Comunidad Especial with the same name in the same municipality (comunidades.geojson)
    osm                 the OpenStreetMap place or landmark with the same name, or one the plan names (gazetteer.json)
    barrio_censo        the Census barrio with the same name, or the one the plan names (gazetteer.json)
    pueblo              the town centre, for the Centro Urbano and Casco Urbano plans
    manual              coordinates the plan itself gives; nota cites the page

Plans for a population group rather than an area (people without a home in Ponce, immigrant and vulnerable populations in
Río Piedras) are not in the CSV: on 2026-11-23 FPR decided that groups of people are not points on a public map.

A row placed by hand keeps the ubicacion of the place its point comes from, and nota says why that place and cites the plan.

The script fills only rows whose ubicacion is empty and writes the CSV back, so edits made by hand are kept. A row it cannot
place stays empty and off the map. To add communities, append rows with the first five columns and run the script again.
"""

import csv
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

from shapely.geometry import Point, shape

from municipalities import MUNICIPALITY_NAMES

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "data"
CSV = ROOT / "wcrp_comunidades.csv"
COLS = ["comunidad", "municipio", "region", "estado", "subrecipiente", "ubicacion", "referencia", "lat", "lng", "nota"]
UBICACION = {"comunidad_especial", "osm", "barrio_censo", "pueblo", "manual"}
PUBLISH = ["comunidad", "municipio", "region", "estado", "subrecipiente", "ubicacion", "referencia"]
CE_MATCH = 0.8   # ponytail: difflib ratio on normalised names; every match is reviewed in the CSV, so a looser cut is fine
PREFIX = re.compile(r"^(barrio|barriada|parcelas|sector|comunidad|la|el|los|las) ")


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = " ".join(s.split())
    while PREFIX.match(s):
        s = PREFIX.sub("", s, count=1)
    return s


def candidates():
    """{municipio: {kind: [(normalised name, name, lat, lng)]}} from the Comunidades Especiales and the gazetteer."""
    idx = {}
    for f in json.loads((OUT / "comunidades.geojson").read_text(encoding="utf-8"))["features"]:
        p, pt = f["properties"], shape(f["geometry"]).representative_point()
        idx.setdefault(p["municipio"], {}).setdefault("comunidad_especial", []).append((norm(p["nombre"]), p["nombre"], pt.y, pt.x))
    g = json.loads((OUT / "gazetteer.json").read_text(encoding="utf-8"))
    kinds = {"town": "osm", "village": "osm", "neighborhood": "osm", "barrio": "barrio_censo", "municipio": "pueblo"}
    for name, lat, lng, k, mi, *_ in g["items"]:
        kind = kinds.get(g["kinds"][k])
        if kind:
            idx.setdefault(g["munis"][mi], {}).setdefault(kind, []).append((norm(name), name, lat, lng))
    return idx


def place(row, idx):
    """(ubicacion, referencia, lat, lng) for a row, or None when nothing in the municipality matches its name."""
    cands, name = idx.get(row["municipio"], {}), norm(row["comunidad"])
    if re.match(r"(centro|casco) urbano", name):
        _, ref, lat, lng = cands["pueblo"][0]
        return "pueblo", ref, lat, lng
    ce = cands.get("comunidad_especial", [])
    best = max(ce, key=lambda c: difflib.SequenceMatcher(None, name, c[0]).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, name, best[0]).ratio() >= CE_MATCH:
        return "comunidad_especial", best[1], best[2], best[3]
    for kind in ("osm", "barrio_censo"):
        hit = next((c for c in cands.get(kind, []) if c[0] == name), None)
        if hit:
            return kind, hit[1], hit[2], hit[3]
    return None


def build():
    print("WCRP communities (wcrp_comunidades.csv)")
    with CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and list(rows[0]) == COLS, f"{CSV.name} must have the columns {COLS}"
    idx, placed = candidates(), 0
    for r in rows:
        assert r["municipio"] in MUNICIPALITY_NAMES, f"unknown municipio {r['municipio']!r} for {r['comunidad']!r}"
        if r["ubicacion"]:
            assert r["ubicacion"] in UBICACION, f"unknown ubicacion {r['ubicacion']!r} for {r['comunidad']!r}"
            continue
        hit = place(r, idx)
        if hit:
            r["ubicacion"], r["referencia"], lat, lng = hit
            r["lat"], r["lng"], placed = f"{lat:.5f}", f"{lng:.5f}", placed + 1
    with CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        w.writerows(rows)

    munis = {f["properties"]["municipality"]: shape(f["geometry"]) for f in json.loads((OUT / "municipios.geojson").read_text(encoding="utf-8"))["features"]}
    for r in rows:   # catches a typo in coordinates edited by hand; 0.001° (about 100 m) lets a shoreline point sit just off the coast
        if r["lat"]:
            assert munis[r["municipio"]].distance(Point(float(r["lng"]), float(r["lat"]))) < 0.001, f"{r['comunidad']!r} is not in {r['municipio']}"
    feats = [{"type": "Feature", "properties": {k: r[k] or None for k in PUBLISH},
              "geometry": {"type": "Point", "coordinates": [round(float(r["lng"]), 5), round(float(r["lat"]), 5)]}}
             for r in rows if r["ubicacion"] and r["lat"]]
    (OUT / "wcrp.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    missing = [r["comunidad"] for r in rows if not (r["ubicacion"] and r["lat"])]
    by = {u: sum(1 for f in feats if f["properties"]["ubicacion"] == u) for u in sorted(UBICACION)}
    print(f"  {len(feats)} of {len(rows)} communities on the map ({placed} placed this run): {by}")
    if missing:
        print(f"  not placed, fill by hand in {CSV.name}: {', '.join(missing)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
