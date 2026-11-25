"""Comunidades Especiales layer for the PR Data Observatory.

    python comunidades.py              # build site/data/comunidades.geojson (downloads once, then reads cache/)
    python comunidades.py --refresh    # download again

Source: the Junta de Planificación delimitation of the Comunidades Especiales designated under Ley 1-2001 (2006 version,
713 polygons), read from the public hosted copy on ArcGIS Online that sits next to the PUT 2015 copy landuse.py uses.
The JP's own MIPR service (gis.jp.pr.gov / sige.pr.gov) was not answering on 2026-10-06. The attributes come from the
community inventory taken with the delimitation; the observatory keeps name, place, housing units, community type and the two
hazards residents reported (flooding, landslides).

Each community also gets the share of its area inside a FEMA Special Flood Hazard Area (SFHA_TF = 'T', the 1% annual
chance flood), measured on the full-detail shapes of both layers. The NFHL comes from build.py's step_flood, so it shares
build.py's cache (cache/fema_nfhl_pr.geojson); build.py --refresh downloads it again.
"""

import json
import sys
from pathlib import Path

import requests
from shapely import make_valid
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from municipalities import MUNICIPALITY_NAMES

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "site" / "data"
UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
CE_URL = "https://services6.arcgis.com/a523XM128lX5Nsff/arcgis/rest/services/Comunidades_Especiales/FeatureServer/0"
FIELDS = "ObjectId,Nombre,Municipio,Barrio,u_vivienda,Tipo_com,Inundable,Deslizamie,Shape_Area"


def fetch(refresh: bool):
    path = CACHE / "comunidades_especiales.geojson"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    feats, offset = [], 0
    while True:
        r = requests.get(f"{CE_URL}/query", params={"where": "1=1", "outFields": FIELDS, "f": "geojson", "outSR": 4326, "geometryPrecision": 6, "resultOffset": offset, "resultRecordCount": 500, "orderByFields": "ObjectId"}, headers={"User-Agent": UA}, timeout=300)
        r.raise_for_status()
        batch = r.json().get("features", [])
        feats.extend(batch)
        print(f"  comunidades: {len(feats)}", flush=True)
        if len(batch) < 500:
            break
        offset += 500
    fc = {"type": "FeatureCollection", "features": feats}
    CACHE.mkdir(exist_ok=True)
    path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    return fc


def yes_no(v):
    v = (v or "").strip().lower()
    return True if v == "si" else False if v == "no" else None


def _round(c, nd=5):
    return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [_round(x, nd) for x in c]


def sfha_index():
    from build import step_flood   # imported here: build.py is large and only this step needs it
    flood = step_flood(False)
    geoms = [make_valid(shape(f["geometry"])) for f in flood["features"] if f["properties"].get("SFHA_TF") == "T" and f.get("geometry")]
    print(f"  {len(geoms):,} FEMA SFHA polygons")
    return geoms, STRtree(geoms)


def sfha_pct(g, sfha, tree):
    """Percent of polygon g inside the SFHA. Both areas are in degrees²; over one community the cos(latitude) scale is
    constant to well under 0.1%, so the ratio equals the ratio of true areas."""
    hits = tree.query(g, predicate="intersects")
    if not len(hits):
        return 0.0
    inside = unary_union([sfha[i].intersection(g) for i in hits])   # union: NFHL polygons can overlap where panels meet
    return min(100.0, inside.area / g.area * 100)


def build(refresh: bool):
    print("Comunidades Especiales (Junta de Planificación, 2006 delimitation)")
    fc = fetch(refresh)
    sfha, tree = sfha_index()
    out = []
    for ft in fc["features"]:
        p = ft["properties"]
        muni = p.get("Municipio")
        assert muni in MUNICIPALITY_NAMES, f"unknown municipio {muni!r}"
        full = make_valid(shape(ft["geometry"]))
        pct = sfha_pct(full, sfha, tree)
        km2 = round((p.get("Shape_Area") or 0) / 1e6, 3)   # Shape_Area is in the JP's State Plane meters, not Web Mercator
        g = shape(ft["geometry"]).simplify(0.00005, preserve_topology=True)   # ~5 m; display copy (make_valid can return a GeometryCollection)
        if g.is_empty:
            continue
        gj = g.__geo_interface__
        out.append({"type": "Feature", "properties": {
            "nombre": (p.get("Nombre") or "").strip(), "municipio": muni, "barrio": (p.get("Barrio") or "").strip().title() or None,
            "viviendas": p.get("u_vivienda") or None, "tipo": (p.get("Tipo_com") or "").strip() or None,
            "inundable": yes_no(p.get("Inundable")), "deslizamiento": yes_no(p.get("Deslizamie")),
            "km2": km2, "sfha_pct": round(pct, 1), "sfha_km2": round(km2 * pct / 100, 3),
        }, "geometry": {"type": gj["type"], "coordinates": _round(gj["coordinates"])}})
    assert len(out) >= 700, f"only {len(out)} communities; the source may have changed"
    (OUT / "comunidades.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  {len(out)} communities in {len({f['properties']['municipio'] for f in out})} municipalities; "
          f"{sum(f['properties']['viviendas'] or 0 for f in out):,} housing units in the inventory; "
          f"{sum(1 for f in out if f['properties']['sfha_pct'] > 0)} touch the SFHA, {sum(f['properties']['sfha_km2'] for f in out):.2f} km² inside it")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build("--refresh" in sys.argv)
