"""Land use and zoning layers for the PR Data Observatory.

  PUT 2015   Plan de Uso de Terrenos de Puerto Rico (Junta de Planificación, adopted 30 Nov 2015):
             land classification into Suelo Urbano, Urbanizable (programado / no programado),
             Rústico Común and Rústico Especialmente Protegido (ecológico, agrícola, hídrico ...).
             Read from the public hosted copy of the official shapefile on ArcGIS Online; FPR also
             keeps the original shapefile (plan_uso_terrenos_30nov2015.zip) as a fallback.
  Calificación  Zoning districts (Reglamento Conjunto) from the Junta de Planificación MIPR service.
             Fetched when the service answers; skipped with a note when it does not (it was
             returning 502 on the first build date).
"""

import json
import math
from collections import defaultdict
from pathlib import Path

import requests
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
PUT_URL = "https://services6.arcgis.com/a523XM128lX5Nsff/arcgis/rest/services/Puerto_Rico_Land_Use_Plan/FeatureServer/0"
CALIF_URL = "https://sige.pr.gov/server/rest/services/MIPR/Calificacion/MapServer"

# Barrios = Census county subdivisions (public domain). CRIM's Catastro layer is not used: its licence text restricts republishing.
BARRIOS_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2023/Places_CouSub_ConCity_SubMCD/MapServer/7"   # layer 7 answers at every scale (layer 1 returns no geometry)

SOURCES = {
    "census_barrios": {
        "name": "US Census Bureau — TIGERweb generalized county subdivisions (barrios), 500k, shoreline-clipped",
        "url": BARRIOS_URL,
        "license": "US Government work (no US copyright)",
        "credit": "Barrio boundaries: US Census Bureau (TIGERweb county subdivisions)",
    },
    "put2015": {
        "name": "Junta de Planificación de Puerto Rico — Plan de Uso de Terrenos (PUT 2015)",
        "url": "https://jp.pr.gov/plan-de-uso-de-terrenos/",
        "license": "Public Government of Puerto Rico data (official shapefile, 30 Nov 2015 version); hosted copy on ArcGIS Online",
        "credit": "Land use classification: Junta de Planificación, PUT 2015",
    },
    "calificacion": {
        "name": "Junta de Planificación — Mapa Interactivo de Puerto Rico (MIPR), Calificación de suelos (zoning)",
        "url": CALIF_URL,
        "license": "Public Government of Puerto Rico data",
        "credit": "Zoning districts: Junta de Planificación, MIPR",
    },
}

# Class groups for display and statistics (CLASIPUT prefixes)
GROUPS = {
    "SU": ("Suelo Urbano", "urban", "#8C8E8E"),
    "SURP": ("Suelo Urbanizable Programado", "urbanizable", "#FFA600"),
    "SURNP": ("Suelo Urbanizable No Programado", "urbanizable", "#FFC83C"),
    "SRC": ("Suelo Rústico Común", "rustic", "#C2D85E"),
    "SREP": ("Suelo Rústico Especialmente Protegido", "protected", "#79901E"),
    "SREP-E": ("SREP Ecológico", "protected", "#47560F"),
    "SREP-A": ("SREP Agrícola", "protected", "#A6BF33"),
    "SREP-H": ("SREP Hídrico", "protected", "#338CB3"),
    "SREP-EH": ("SREP Ecológico e Hídrico", "protected", "#205D7B"),
    "SREP-AH": ("SREP Agrícola e Hídrico", "protected", "#5FAFDA"),
    "AGUA": ("Agua", "water", "#BDE0F2"),
    "VIAL": ("Vial", "road", "#E6E6E6"),
}


SHARE_EXCLUDED = ("water", "road")   # shares of land leave out water bodies and road rights-of-way, as the *_pct fields of municipalities.json do


def class_key(cls):
    """The display class of a CLASIPUT code: the code itself when it has its own colour (GROUPS), else its prefix (SREP-AE, SREP-EP ... draw as SREP), else OTRO."""
    cls = (cls or "").upper()
    return cls if cls in GROUPS else cls.split("-")[0] if cls.split("-")[0] in GROUPS else "OTRO"


def class_summary(props, muni_norm, version):
    """landuse_summary.json: km² of each display class by municipality and for Puerto Rico, from the full-resolution polygons' Shape_Area
    (square metres in the projected CRS), the areas behind landuse_km2 and the *_pct fields. Polygons with no municipality are kept apart."""
    areas, unassigned = defaultdict(lambda: defaultdict(float)), defaultdict(float)
    for p in props:
        k, m, a = class_key(p.get("CLASIPUT")), muni_norm(p.get("Municipio") or ""), (p.get("Shape_Area") or 0) / 1e6
        (areas[m] if m else unassigned)[k] += a
    keys = list(GROUPS) + (["OTRO"] if any("OTRO" in v for v in areas.values()) or "OTRO" in unassigned else [])
    total = defaultdict(float)
    for v in areas.values():
        for k, a in v.items():
            total[k] += a
    r = lambda v: {k: round(v.get(k, 0.0), 3) for k in keys}
    return {"version": 1, "put_version": version, "unit": "km2",
            "source": "Junta de Planificación, Plan de Uso de Terrenos de Puerto Rico 2015 (PUT-2014, adopted 30 November 2015)",
            "basis": "Areas of the full-resolution polygons (Shape_Area). Shares of land leave out water and road rights-of-way.",
            "classes": [{"key": k, "label": GROUPS.get(k, ("Otro", "other", "#B3B3B3"))[0], "group": GROUPS.get(k, ("Otro", "other", "#B3B3B3"))[1],
                         "color": GROUPS.get(k, ("Otro", "other", "#B3B3B3"))[2], "in_share": GROUPS.get(k, ("", "other", ""))[1] not in SHARE_EXCLUDED} for k in keys],
            "names": sorted(areas), "municipios": {m: r(v) for m, v in sorted(areas.items())}, "puerto_rico": r(total), "unassigned": r(unassigned)}


PUT_ZIP = "plan_uso_terrenos_30nov2015.zip"   # official JP shapefile kept by FPR (copied into cache/)


def fetch_put(cache: Path, refresh: bool):
    """PUT 2015 polygons as WGS84 GeoJSON: from FPR's copy of the official shapefile when present
    (reprojected from NAD83(2011) State Plane Puerto Rico), otherwise from the hosted ArcGIS copy."""
    print("Plan de Uso de Terrenos 2015 (Junta de Planificación)")
    path = cache / "put2015.geojson"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    zp = cache / PUT_ZIP
    if zp.exists():
        import io
        import zipfile

        import shapefile
        from pyproj import Transformer
        from shapely.ops import transform

        z = zipfile.ZipFile(zp)
        base = next(n for n in z.namelist() if n.lower().endswith(".shp"))[:-4]
        r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")))
        prj = z.read(base + ".prj").decode("latin-1")
        tr = Transformer.from_crs(prj, "EPSG:4326", always_xy=True)
        feats = []
        for sr in r.iterShapeRecords():
            try:
                g = transform(tr.transform, shape(sr.shape.__geo_interface__))
            except Exception:
                continue
            rec = sr.record.as_dict()
            feats.append({"type": "Feature", "properties": {"OBJECTID": rec.get("OBJECTID"), "TIPO": rec.get("TIPO"), "Municipio": rec.get("Municipio"), "CLASIPUT": rec.get("CLASIPUT"), "DESCRIPPUT": rec.get("DESCRIPPUT"), "Shape_Area": rec.get("Shape_Area")}, "geometry": g.__geo_interface__})
        print(f"  PUT: {len(feats)} polygons from the official shapefile ({PUT_ZIP})", flush=True)
    else:
        feats, offset = [], 0
        while True:
            for attempt in range(5):
                try:
                    r = requests.get(f"{PUT_URL}/query", params={"where": "1=1", "outFields": "OBJECTID,TIPO,Municipio,CLASIPUT,DESCRIPPUT,Shape_Area", "f": "geojson", "outSR": 4326, "geometryPrecision": 5, "resultOffset": offset, "resultRecordCount": 50, "orderByFields": "OBJECTID"}, headers={"User-Agent": UA}, timeout=300)
                    r.raise_for_status()
                    batch = r.json().get("features", [])
                    break
                except Exception as e:
                    if attempt == 4:
                        raise
                    print(f"  PUT offset {offset}: retry after {type(e).__name__}", flush=True)
            feats.extend(batch)
            print(f"  PUT: {len(feats)} polygons", flush=True)
            if len(batch) < 50:
                break
            offset += 50
    fc = {"type": "FeatureCollection", "features": feats}
    path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    return fc


def fetch_barrios(cache: Path, refresh: bool):
    """Barrio polygons (Census county subdivisions of Puerto Rico), paged and cached."""
    print("Census barrios (county subdivisions)")
    path = cache / "census_barrios.geojson"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    feats, offset = [], 0
    while True:
        r = requests.get(f"{BARRIOS_URL}/query", params={"where": "STATE='72'", "outFields": "GEOID,BASENAME", "f": "geojson", "outSR": 4326, "geometryPrecision": 5, "resultOffset": offset, "resultRecordCount": 500, "orderByFields": "OBJECTID"}, headers={"User-Agent": UA}, timeout=300)
        r.raise_for_status()
        batch = r.json().get("features", [])
        feats.extend(batch)
        print(f"  barrios: {len(feats)}", flush=True)
        if len(batch) < 500:
            break
        offset += 500
    fc = {"type": "FeatureCollection", "features": feats}
    path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    return fc


def build_barrios(cache: Path, refresh: bool, places: list, muni_of_fips, access=None):
    """Barrio polygons with tourism counts (places, in SFHA, near transit) for the sub-municipal view.

    `access` (access.py's per-place result, in the order of `places`) adds acc_cur400 and acc_freq400 (straight line) and, when it was computed with a
    walking network, acc_walk400 and acc_wfreq400 (walking along mapped roads); `transit` stays the count near any mapped stop
    (transit minus acc_cur400 is the places near only a stop with an expired timetable or none)."""
    fc = fetch_barrios(cache, refresh)
    geoms, props = [], []
    for ft in fc["features"]:
        try:
            geoms.append(shape(ft["geometry"])); props.append(ft["properties"])
        except Exception:
            pass
    tree = STRtree(geoms)
    counts = [dict(assets=0, sfha=0, transit=0, lodging=0) for _ in geoms]
    if access is not None:
        walk = access.tw_m is not None
        for c in counts:
            c.update(acc_cur400=0, acc_freq400=0, **({"acc_walk400": 0, "acc_wfreq400": 0} if walk else {}))
    for i, pl in enumerate(places):
        if pl.get("confidence", 0) < 0.5 or pl.get("type") == "Places of Worship":
            continue
        hits = tree.query(Point(pl["lng"], pl["lat"]), predicate="within")
        if not len(hits):
            continue
        c = counts[hits[0]]
        c["assets"] += 1
        c["sfha"] += 1 if pl.get("sfha") else 0
        c["transit"] += 1 if pl.get("transit_400m") else 0
        c["lodging"] += 1 if pl.get("category") == "ACCOMMODATIONS" else 0
        if access is not None:
            f = access.flags(i)
            c["acc_cur400"] += f["cur400"]
            c["acc_freq400"] += f["freq400"]
            if walk:
                c["acc_walk400"] += f["walk400"]
                c["acc_wfreq400"] += f["wfreq400"]
        pl["barrio"] = props[hits[0]].get("BASENAME")
    out = []
    for g, p, c in zip(geoms, props, counts):
        gs = g.simplify(0.0003, preserve_topology=True)
        if gs.is_empty:
            continue
        # area from the (shoreline-clipped) polygon, equal-area approximation at the polygon's latitude
        lat = g.centroid.y
        km2 = g.area * (111.32 * math.cos(math.radians(lat))) * 110.57
        geoid = p.get("GEOID") or ""
        out.append({"type": "Feature", "properties": {"barrio": p.get("BASENAME"), "municipality": muni_of_fips(geoid[:5]), "geoid": geoid, "km2": round(km2, 2), **c, "assets_per_km2": round(c["assets"] / km2, 2) if km2 else None}, "geometry": _round_geom(gs.__geo_interface__, 5)})
    print(f"  {len(out)} barrios; {sum(c['assets'] for c in counts):,} places attributed to a barrio")
    return {"type": "FeatureCollection", "features": out}, {"barrios": len(out)}


def try_fetch_calificacion(cache: Path, refresh: bool):
    path = cache / "calificacion_meta.json"
    try:
        r = requests.get(f"{CALIF_URL}?f=pjson", headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        d = r.json()
        if "layers" not in d:
            raise RuntimeError("no layers")
        path.write_text(json.dumps(d), encoding="utf-8")
        print(f"  Calificación service reachable: {len(d['layers'])} layers (download not yet wired)")
        return {"available": True, "layers": [(layer["id"], layer["name"]) for layer in d["layers"]]}
    except Exception as e:
        print(f"  Calificación (zoning) service unavailable on build: {type(e).__name__}; layer skipped")
        return {"available": False, "reason": type(e).__name__}


def _round_geom(g, nd=4):
    def rc(c):
        return [round(c[0], nd), round(c[1], nd)] if isinstance(c[0], (int, float)) else [rc(x) for x in c]
    return {"type": g["type"], "coordinates": rc(g["coordinates"])}


def build_landuse(cache: Path, refresh: bool, places: list, stats: dict, muni_norm, summary_out=None):
    """Returns (landuse_fc_for_site, meta); adds land-use fields to places and stats. `summary_out` (a dict) receives landuse_summary.json."""
    fc = fetch_put(cache, refresh)
    geoms, props = [], []
    for ft in fc["features"]:
        try:
            g = shape(ft["geometry"])
        except Exception:
            continue
        p = ft["properties"]
        cls = (p.get("CLASIPUT") or "").upper()
        grp = GROUPS.get(cls) or GROUPS.get(cls.split("-")[0]) or ("Otro", "other", "#B3B3B3")
        p["label"], p["group"], p["color"] = grp
        geoms.append(g)
        props.append(p)
    tree = STRtree(geoms)
    # places -> land class
    counts = defaultdict(lambda: defaultdict(int))
    for pl in places:
        hits = tree.query(Point(pl["lng"], pl["lat"]), predicate="within")
        if len(hits):
            p = props[hits[0]]
            pl["land_use"], pl["land_group"] = p["CLASIPUT"], p["group"]
            counts[pl["municipality"]][p["group"]] += 1
        else:
            pl["land_use"], pl["land_group"] = None, None
    # municipality area shares (Shape_Area is in the projected CRS, square metres)
    area = defaultdict(lambda: defaultdict(float))
    for p in props:
        m = muni_norm(p.get("Municipio") or "")
        if m and p["group"] not in ("water", "road"):
            area[m][p["group"]] += (p.get("Shape_Area") or 0) / 1e6
    for name, s in stats.items():
        a = area.get(name, {})
        tot = sum(a.values())
        s["landuse_km2"] = {k: round(v, 1) for k, v in a.items()}
        if tot:
            s["urban_pct"] = round(a.get("urban", 0) / tot * 100, 1)
            s["urbanizable_pct"] = round(a.get("urbanizable", 0) / tot * 100, 1)
            s["protected_land_pct"] = round(a.get("protected", 0) / tot * 100, 1)
            s["rustic_common_pct"] = round(a.get("rustic", 0) / tot * 100, 1)
        c = counts.get(name, {})
        core = sum(c.values())
        s["places_on_protected_land"] = c.get("protected", 0)
        s["places_on_protected_land_pct"] = round(c.get("protected", 0) / core * 100, 1) if core else None
        s["places_urban_pct"] = round(c.get("urban", 0) / core * 100, 1) if core else None
    if summary_out is not None:
        summary_out.update(class_summary(props, muni_norm, "PUT-2014, 30-NOV-2015"))
    calif = try_fetch_calificacion(cache, refresh)
    # display copy: simplified
    out = []
    for g, p in zip(geoms, props):
        gs = g.simplify(0.001, preserve_topology=True)   # ~100 m: display copy, analytics above used full geometry
        if gs.is_empty:
            continue
        out.append({"type": "Feature", "properties": {"cls": p["CLASIPUT"], "label": p["label"], "group": p["group"], "color": p["color"], "municipio": p.get("Municipio")}, "geometry": _round_geom(gs.__geo_interface__)})
    meta = {"put_polygons": len(out), "put_version": "PUT-2014, 30-NOV-2015", "groups": {k: v[0] for k, v in GROUPS.items()}, "calificacion": calif,
            "places_on_protected_land": sum(1 for pl in places if pl.get("land_group") == "protected")}
    print(f"  {len(out)} PUT polygons; {meta['places_on_protected_land']:,} tourism places on Suelo Rústico Especialmente Protegido")
    return {"type": "FeatureCollection", "features": out}, meta
