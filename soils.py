"""Soils layer of the PR Data Observatory's 2D map (site/js/soil.js).

  SSURGO     USDA NRCS Soil Survey Geographic Database, read keyless from Soil Data Access (SDA, SQL over REST).
             Puerto Rico's seven survey areas (PR682, PR684, PR686, PR688, PR689, PR700, PR787), which cover Vieques, Culebra and Mona too.

The layer answers four plain questions about every map unit, from NRCS's own interpretations (planning scale, not a site study):

  farm     is it good land to farm? the unit's farmland class: prime, prime if irrigated or drained, of statewide importance, not prime
                                                                                                              mapunit.farmlndcl
  build    how suited is it to build houses? NRCS's rating for dwellings without basements, by dominant condition (the rating that
           covers the largest share of the unit's rated components): not, somewhat or very limited          cointerp 'ENG - Dwellings W/O Basements'
  flood    does it flood or stay wet? flooding frequency, and drainage where it does not flood               muaggatt.flodfreqdcd, drclassdcd
  slope    the representative slope in percent, and its low-high range, of the main soil                    component.slope_r, _l, _h

the chemistry of the top 30 cm of the soil it describes (thickness-weighted over the horizons in that depth): pH in water (1:1), organic
matter (%), electrical conductivity or salinity (dS/m) and calcium carbonate equivalent or lime (%), chorizon ph1to1h2o_r, om_r, ec_r, caco3_r;

and, as technical detail, its main soil (the component with the largest share of the unit):

  order    the soil order of US Soil Taxonomy, its most general class (Ultisols, Oxisols, Inceptisols ...)   component.taxorder
  origin   the kind of material the soil formed in (alluvium, residuum, colluvium, marine deposits ...)       copm.pmkind, pmorigin

A map unit is a survey generalization: it names the typical soil of the polygon, and other soils (`share` says how much of the unit is the
main one) sit inside it. Miscellaneous areas (rock outcrop, urban land, water) have no order. A complex led by one of them (most of the San
Juan metro area is mapped as Urban land-<soil> complexes) is described by its largest classified soil when that soil is at least MIN_SHARE
of the unit, and `cover` names the miscellaneous area on top (Urban land) with its share. A unit that is Urban land alone has no soil
described: its flooding answer comes from the USGS geologic map of Puerto Rico at 1:100,000 (Bawiec, 1998, Open-File Report 98-38):
"geo_wet" where it stands on young river, swamp or beach deposits (Qa, Qs, Qb), "geo_dry" elsewhere on the main island. The map's
three ArcInfo export files (west.e00, central.e00, east.e00, from https://pubs.usgs.gov/of/1998/of98-038/export/) are downloaded by
hand into cache/geology/ and read with pyogrio and pyproj; without them that part stays unrated. Vieques and Culebra are not on them.

Each unit's name is also given in Spanish (`name_es`, spanish()): the series stays, the texture and the phases are translated.

  python soils.py             build site/data/soils.geojson (reads the cache when present)
  python soils.py --refresh   query SDA again
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import requests
from shapely import set_precision, wkt
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "soils"
OUT = ROOT / "site" / "data" / "soils.geojson"
SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico)"
REDUCE = 0.00008    # degrees (about 9 m): SDA simplifies each polygon before sending it
SIMPLIFY = 0.0001   # degrees (about 11 m): after the polygons of one map unit are merged
MIN_SHARE = 15      # %: below this a classified soil in a unit led by urban land or rock is an inclusion, not the unit's soil

# Kinds of parent material, grouped for the map (the pop-up keeps the survey's own words)
ORIGIN = {
    "Alluvium": "alluvial", "Slope alluvium": "alluvial", "Flow deposits": "alluvial",
    "Residuum": "residual", "Saprolite": "residual",
    "Colluvium": "colluvial",
    "Marine deposits": "coastal", "Fluviomarine deposits": "coastal", "Estuarine deposits": "coastal", "Beach sand": "coastal", "Lagoonal deposits": "coastal",
    "Organic material": "organic", "Herbaceous organic material": "organic",
    "Human-transported material": "fill",
}
# The four questions, each answer as a short code (the page holds the words)
FARM = {"All areas are prime farmland": "prime", "Prime farmland if irrigated": "prime_if", "Prime farmland if drained": "prime_if",
        "Prime farmland if irrigated and reclaimed of excess salts and sodium": "prime_if",
        "Farmland of statewide importance": "state", "Farmland of statewide importance, if irrigated": "state", "Not prime farmland": "not"}
BUILD = {"Not limited": "not", "Somewhat limited": "somewhat", "Very limited": "very"}
FLOODS = {"Frequent": "frequent", "Very frequent": "frequent", "Occasional": "sometimes", "Rare": "sometimes"}
WET = {"Poorly drained", "Very poorly drained", "Somewhat poorly drained"}
DWELLINGS = "ENG - Dwellings W/O Basements"


def flood_class(freq, drainage):
    if freq in FLOODS:
        return FLOODS[freq]
    if drainage in WET:
        return "wet"
    return "no" if freq == "None" else None


def practical(refresh):
    """Farmland class, flooding and drainage of each map unit, and the dominant rating for houses."""
    units = cached("units.json", lambda: sda("""
        SELECT mu.mukey, mu.farmlndcl, a.flodfreqdcd, a.drclassdcd
        FROM legend l JOIN mapunit mu ON mu.lkey = l.lkey LEFT JOIN muaggatt a ON a.mukey = mu.mukey
        WHERE l.areasymbol LIKE 'PR%'"""), refresh)
    ratings = cached("dwellings.json", lambda: sda(f"""
        SELECT c.mukey, c.cokey, c.comppct_r, i.interphrc
        FROM legend l JOIN mapunit mu ON mu.lkey = l.lkey JOIN component c ON c.mukey = mu.mukey
        JOIN cointerp i ON i.cokey = c.cokey AND i.ruledepth = 0 AND i.mrulename = '{DWELLINGS}'
        WHERE l.areasymbol LIKE 'PR%'"""), refresh)
    share = defaultdict(Counter)
    for r in ratings:
        if r["interphrc"] in BUILD:
            share[r["mukey"]][BUILD[r["interphrc"]]] += num(r["comppct_r"]) or 0
    return {u["mukey"]: {"farm": FARM.get(u["farmlndcl"]), "build": share[u["mukey"]].most_common(1)[0][0] if share[u["mukey"]] else None,
                         "flood": flood_class(u["flodfreqdcd"], u["drclassdcd"])} for u in units}


FREQ_RANK = ["None", "Very rare", "Rare", "Occasional", "Frequent", "Very frequent"]


def water(refresh):
    """Flooding (the most frequent class of any month) and drainage of every component. The unit's own figures (muaggatt) follow its
    dominant component, which in an Urban land-<soil> complex is Urban land, rated as never flooding: Urban land-Reilly, frequently
    flooded complex came out "does not flood". The map reads the soil it describes instead."""
    rows = cached("water.json", lambda: sda("""
        SELECT c.cokey, c.drainagecl, m.flodfreqcl
        FROM legend l JOIN mapunit mu ON mu.lkey = l.lkey JOIN component c ON c.mukey = mu.mukey
        LEFT JOIN comonth m ON m.cokey = c.cokey
        WHERE l.areasymbol LIKE 'PR%'"""), refresh)
    out = {}
    for r in rows:
        freq, drain = out.get(r["cokey"], (None, r["drainagecl"]))
        f = r["flodfreqcl"]
        if f in FREQ_RANK and (freq is None or FREQ_RANK.index(f) > FREQ_RANK.index(freq)):
            freq = f
        out[r["cokey"]] = (freq, drain)
    return {k: flood_class(*v) for k, v in out.items()}

SOURCES = {
    "ssurgo": {
        "name": "USDA NRCS Soil Survey Geographic Database (SSURGO), Soil Data Access",
        "url": "https://sdmdataaccess.sc.egov.usda.gov/",
        "license": "US Government work (no US copyright)",
        "credit": "Soils: USDA NRCS, SSURGO",
    },
}


def sda(sql):
    r = requests.post(SDA, data={"query": sql, "format": "JSON+COLUMNNAME"}, headers={"User-Agent": UA}, timeout=600)
    r.raise_for_status()
    rows = r.json().get("Table", [])
    return [dict(zip(rows[0], row)) for row in rows[1:]] if rows else []


def cached(name, fetch, refresh):
    p = CACHE / name
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    data = fetch()
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")
    return data


def num(v):
    return None if v is None or v == "" else float(v)


def classify(refresh):
    """The main soil of every map unit in Puerto Rico: its order, parent material and slope."""
    rows = cached("components.json", lambda: sda("""
        SELECT mu.mukey, mu.musym, mu.muname, c.cokey, c.compname, c.compkind, c.comppct_r, c.taxorder,
               c.slope_l, c.slope_r, c.slope_h, pm.pmkind, pm.pmorigin, pm.pmorder
        FROM legend l JOIN mapunit mu ON mu.lkey = l.lkey JOIN component c ON c.mukey = mu.mukey
        LEFT JOIN copmgrp g ON g.cokey = c.cokey AND g.rvindicator = 'Yes'
        LEFT JOIN copm pm ON pm.copmgrpkey = g.copmgrpkey
        WHERE l.areasymbol LIKE 'PR%'"""), refresh)
    print(f"  {len(rows):,} component rows")

    comps = defaultdict(dict)   # mukey -> cokey -> component, with its parent materials (top layer first)
    names = {}
    for r in rows:
        names[r["mukey"]] = (r["musym"], r["muname"])
        c = comps[r["mukey"]].setdefault(r["cokey"], {**r, "pms": []})
        if r["pmkind"]:
            c["pms"].append((num(r["pmorder"]) or 0, r["pmkind"], r["pmorigin"]))

    out = {}
    for mukey, cs in comps.items():
        pct = lambda c: num(c["comppct_r"]) or 0
        top = max(cs.values(), key=lambda c: (pct(c), c["taxorder"] is not None))
        main = top
        if not top["taxorder"]:
            # a complex led by a miscellaneous area (Urban land-Bayamón complex, Rock outcrop-Tanama complex): describe its largest
            # classified soil instead, when that soil is a real part of the unit and not a small inclusion
            named = [c for c in cs.values() if c["taxorder"] and pct(c) >= MIN_SHARE]
            if named:
                main = max(named, key=pct)
        pms = sorted(main["pms"])
        kind, rock = (pms[0][1], pms[0][2]) if pms else (None, None)
        out[mukey] = {
            "musym": names[mukey][0], "name": names[mukey][1], "comp": main["compname"], "cokey": main["cokey"],
            "share": round(pct(main)),
            "cover": top["compname"] if main is not top else None, "cover_share": round(pct(top)) if main is not top else None,
            "order": main["taxorder"],
            "origin": ORIGIN.get(kind, "other" if kind else None), "pm": kind, "pm_rock": rock,
            "slope": num(main["slope_r"]), "slope_l": num(main["slope_l"]), "slope_h": num(main["slope_h"]),
        }
    return out


def polygons(refresh):
    """One merged, simplified geometry per map unit."""
    areas = [r["areasymbol"] for r in sda("SELECT areasymbol FROM sacatalog WHERE areasymbol LIKE 'PR%' ORDER BY areasymbol")]
    parts = defaultdict(list)
    for a in areas:
        rows = cached(f"polygons_{a}.json", lambda a=a: sda(
            f"SELECT mukey, mupolygongeo.Reduce({REDUCE}).STAsText() wkt FROM mupolygon WHERE areasymbol = '{a}'"), refresh)
        for r in rows:
            parts[r["mukey"]].append(wkt.loads(r["wkt"]))
        print(f"  {a}: {len(rows):,} polygons")
    return {k: _polygonal(set_precision(unary_union(v).simplify(SIMPLIFY, preserve_topology=True), 1e-5)) for k, v in parts.items()}


def _polygonal(g):
    """Polygons only: snapping to 1e-5 degrees can leave a slivered polygon as lines or points inside a collection."""
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    polys = [p for p in getattr(g, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(polys) if polys else g.__class__()


# USGS geologic map of Puerto Rico (Bawiec, ed., 1998, Open-File Report 98-038, 1:100,000; US Government work, public domain): read only under
# map units the soil survey leaves as Urban land alone, to say what the city stands on. The ArcInfo export files are downloaded by hand to
# cache/geology (west, central, east: https://pubs.usgs.gov/of/1998/of98-038/export/); their polygons are rebuilt from the arcs and the
# label points, because GDAL's own polygon reader takes many minutes on them. Projection: polyconic, NAD27, origin 18N 67W (the .met files)
GEOLOGY = ROOT / "cache" / "geology"
GEO_SHEETS = ("west", "central", "east")
GEO_WET = {"Qa": "alluvium", "Qs": "swamp deposits", "Qb": "beach deposits"}   # young deposits of rivers, swamps and beaches: land that floods


def geology():
    """The young river, swamp and beach deposits (GEO_WET) of the geologic map, in degrees, merged per symbol."""
    out = GEOLOGY / "young_deposits.geojson"
    if out.exists():
        return {f["properties"]["unit"]: shape(f["geometry"]) for f in json.loads(out.read_text(encoding="utf-8"))["features"]}
    if not all((GEOLOGY / f"{s}.e00").exists() for s in GEO_SHEETS):
        print("  geologic map not in cache/geology: Urban land alone stays unrated")
        return {}
    import pyogrio
    import shapely
    from pyproj import Transformer
    to_deg = Transformer.from_crs("+proj=poly +lat_0=18 +lon_0=-67 +x_0=0 +y_0=0 +ellps=clrk66 +datum=NAD27 +units=m +no_defs", "EPSG:4326", always_xy=True)
    parts, hulls = defaultdict(list), []
    for sheet in GEO_SHEETS:
        path = GEOLOGY / f"{sheet}.e00"
        _, _, arcs, _ = pyogrio.raw.read(path, layer="ARC", columns=[])
        polys = list(shapely.polygonize(shapely.from_wkb(arcs)).geoms)
        meta, _, labels, cols = pyogrio.raw.read(path, layer="LAB", columns=["FMATN"])
        units = dict(zip(meta["fields"], cols))["FMATN"]
        hull = shapely.concave_hull(shapely.MultiPolygon(polys), ratio=0.05)   # what the sheet covers: the main island, not Vieques or Culebra
        hulls.append(shapely.transform(hull, lambda xy: np.column_stack(to_deg.transform(xy[:, 0], xy[:, 1]))))
        for li, pi in zip(*shapely.STRtree(polys).query(shapely.from_wkb(labels), predicate="within")):
            u = str(units[li]).strip()
            if u in GEO_WET:
                parts[u].append(shapely.transform(polys[pi], lambda xy: np.column_stack(to_deg.transform(xy[:, 0], xy[:, 1]))))
    merged = {u: unary_union(g).buffer(0) for u, g in parts.items()}
    merged["coverage"] = unary_union(hulls).buffer(0)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"unit": u}, "geometry": mapping(g)} for u, g in merged.items()]}), encoding="utf-8")
    print("  geologic map: " + ", ".join(f"{u} {len(parts[u])} polygons" for u in parts))
    return merged


# Chemical properties of the soil the map describes, its top 30 cm (where roots, runoff and most uses meet it)
DEPTH = 30
CHEM = {"ph": "ph1to1h2o_r", "om": "om_r", "ec": "ec_r", "caco3": "caco3_r"}


def profile(refresh):
    """For every component, the thickness-weighted value of each CHEM property over its horizons between 0 and DEPTH cm."""
    cols = ", ".join(f"h.{c}" for c in CHEM.values())
    rows = cached("chemistry.json", lambda: sda(f"""
        SELECT c.cokey, h.hzdept_r, h.hzdepb_r, {cols}
        FROM legend l JOIN mapunit mu ON mu.lkey = l.lkey JOIN component c ON c.mukey = mu.mukey
        JOIN chorizon h ON h.cokey = c.cokey AND h.hzdept_r < {DEPTH}
        WHERE l.areasymbol LIKE 'PR%'"""), refresh)
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    for r in rows:
        t0, t1 = num(r["hzdept_r"]), num(r["hzdepb_r"])
        if t0 is None or t1 is None or min(t1, DEPTH) <= max(t0, 0):
            continue
        th = min(t1, DEPTH) - max(t0, 0)
        for k, col in CHEM.items():
            v = num(r[col])
            if v is not None:
                acc[r["cokey"]][k][0] += v * th
                acc[r["cokey"]][k][1] += th
    return {c: {k: round(a[k][0] / a[k][1], 2) for k in CHEM if a[k][1] > 0} for c, a in acc.items()}


# A soil map unit's name in Spanish (USDA texture classes and NRCS phase terms): the series stay as they are, they are names; the texture of the
# surface layer and the phases (slope, erosion, flooding) are translated. "Mucara clay, 40 to 60 percent slopes" -> "Mucara: arcilla, pendientes de 40 a 60 %"
ES_LAND = {   # miscellaneous areas and the land types inside complexes
    "Urban land": "terreno urbano", "Rock outcrop": "afloramiento rocoso", "Limestone outcrop": "afloramiento de caliza", "Serpentinite outcrop": "afloramiento de serpentinita",
    "Limestone rockland": "terreno de roca caliza", "Limestone rock land": "terreno de roca caliza", "Rock land": "terreno rocoso", "Stony land": "terreno pedregoso",
    "Stony rock land": "terreno de roca pedregoso", "Stony rockland": "terreno de roca pedregoso", "Rubble land": "terreno de rocas sueltas",
    "Alluvial land": "terreno aluvial", "Cobbly alluvial land": "terreno aluvial con guijarros", "Wet alluvial land": "terreno aluvial húmedo",
    "Anthroportic Ustorthents": "Ustorthents alterados por el ser humano", "Beaches": "playas", "Coastal beach": "playas", "Coastal beaches": "playas",
    "Canteras and Graveros": "canteras y graveras", "Gravel": "grava", "Gravel pits": "graveras", "Landfill": "vertedero", "Leveled land": "terreno nivelado",
    "Made land": "terreno de relleno", "Not Public Information": "información no pública", "Pits": "excavaciones", "Pits and Quarries": "excavaciones y canteras",
    "Riverwash": "arenas y gravas de río", "Salt flats": "salinas", "Salt pits": "estanques de sal", "Salt water marsh": "marisma de agua salada",
    "Tidal flats": "llanos de marea", "Leveled clayey land": "terreno nivelado arcilloso", "Leveled sandy land": "terreno nivelado arenoso", "Rough stony land": "terreno pedregoso escarpado", "Tidal swamp": "ciénaga de marea", "Water": "agua", "Water > 40 acres": "agua (más de 40 acres)", "Water >40 acres": "agua (más de 40 acres)",
}
ES_TEXTURE = {
    "silty clay loam": "franco arcillo limoso", "sandy clay loam": "franco arcillo arenoso", "fine sandy loam": "franco arenoso fino", "coarse sandy loam": "franco arenoso grueso",
    "very fine sandy loam": "franco arenoso muy fino", "loamy fine sand": "arena franca fina", "loamy coarse sand": "arena franca gruesa", "silty clay": "arcilla limosa",
    "sandy clay": "arcilla arenosa", "clay loam": "franco arcilloso", "silt loam": "franco limoso", "sandy loam": "franco arenoso", "loamy sand": "arena franca",
    "fine sand": "arena fina", "coarse sand": "arena gruesa", "clay": "arcilla", "loam": "franco", "sand": "arena", "silt": "limo", "muck": "lodo orgánico", "peat": "turba",
}
ES_MODIFIER = {
    "extremely gravelly": "con muchísima grava", "very gravelly": "con mucha grava", "gravelly": "con grava", "extremely cobbly": "con muchísimos guijarros",
    "very cobbly": "con muchos guijarros", "cobbly": "con guijarros", "extremely stony": "con muchísimas piedras", "very stony": "con muchas piedras", "stony": "con piedras",
    "mucky": "con lodo orgánico", "parashelly": "con conchas", "clayey": "arcilloso",
}
ES_PHASE = {
    "eroded": "erosionado", "severely eroded": "muy erosionado", "frequently flooded": "se inunda con frecuencia", "very frequently flooded": "se inunda muy a menudo",
    "occasionally flooded": "se inunda a veces", "rarely flooded": "rara vez se inunda", "ponded": "con agua estancada", "occasionally ponded": "con agua estancada a veces",
    "rarely ponded": "rara vez con agua estancada", "saline": "salino", "steep": "empinado", "very steep": "muy empinado", "windswept": "expuesto al viento",
    "moderately wet": "algo húmedo", "deep variant": "variante profunda", "moderately deep variant": "variante moderadamente profunda", "shallow": "poco profundo",
    "high bottom": "vega alta", "gravelly substratum": "subsuelo con grava", "human altered": "alterado por el ser humano", "overwash": "con sedimento encima",
    "extremely stony": "con muchísimas piedras", "extremelly stony": "con muchísimas piedras", "extremely cobbly": "con muchísimos guijarros", "very stony": "con muchas piedras",
    "limestone": "caliza", "sandstone": "arenisca", "sand": "arena", "gravel": "grava", "quarry": "cantera", "pits and quarries": "excavaciones y canteras",
    "Humid Coastal Plains": "llanos costeros húmedos", "Semiarid Coastal Plains": "llanos costeros semiáridos", "Semiarid Mountains and Valleys": "montañas y valles semiáridos",
}
_NUM = r"(\d+(?:\.\d+)?)"


def _land(series):   # "Urban land-Bayamon" -> "terreno urbano-Bayamon"
    return "-".join(ES_LAND.get(s, s) for s in re.split(r"-(?=[A-Z])", series))


def _phase(t):
    t = t.strip()
    if m := re.fullmatch(_NUM + r" to " + _NUM + r" ?(?:percent|perecent|perecnt)? ?(?:slopes)?", t):
        return f"pendientes de {m[1]} a {m[2]} %"
    if m := re.fullmatch(_NUM + r" to " + _NUM + r" (?:meter )?water depth( complex)?", t):
        return f"bajo {m[1]} a {m[2]} m de agua"
    if m := re.fullmatch(r"(.*flooded)( complex)?(-.+)?", t):
        return ES_PHASE.get(m[1], m[1]) + (", " + _land(m[3][1:]) if m[3] else "")
    return ES_PHASE.get(t, ES_LAND.get(t, t))


def spanish(name):
    name = re.sub(r"\s+", " ", name.strip()).replace("Rock Outcrop", "Rock outcrop").replace("percent, slopes", "percent slopes")
    if name in ES_LAND:
        return ES_LAND[name][0].upper() + ES_LAND[name][1:]
    if m := re.match(r"(.+?) and (\S+) soils(.*)", name):   # "Manglillo, Boqueron and Serrano soils, ..." -> "Suelos Manglillo, Boqueron y Serrano, ..."
        head, rest = f"Suelos {m[1]} y {m[2]}", m[3]
    elif m := re.match(r"(\S+) soils(.*)", name):
        head, rest = f"Suelos {m[1]}", m[2]
    else:
        head, _, rest = name.partition(",")
        rest = "," + rest if rest else ""
        if m := re.fullmatch(r"(.+) (complex|association)( steep)?", head):
            head = ("Complejo " if m[2] == "complex" else "Asociación ") + _land(m[1]) + (", empinada" if m[3] else "")
        else:
            words, tex = head.split(" "), ""
            for k in range(1, len(words)):   # the longest tail of the name that is a texture, with its modifiers
                tail = " ".join(words[k:]).lower()
                mods = ""
                for mod in sorted(ES_MODIFIER, key=len, reverse=True):
                    if tail.startswith(mod + " "):
                        mods, tail = ES_MODIFIER[mod], tail[len(mod) + 1:]
                        break
                if tail in ES_TEXTURE:
                    tex = ES_TEXTURE[tail] + (" " + mods if mods else "")
                    head = " ".join(words[:k])
                    break
            head = _land(head) + (": " + tex if tex else "")
    phases = [_phase(t) for t in rest.split(",") if t.strip()]
    out = ", ".join([head] + phases)
    return out[0].upper() + out[1:]


def build(refresh=False):
    print("USDA NRCS SSURGO soil types")
    soil = classify(refresh)
    geoms = polygons(refresh)
    use = practical(refresh)
    wet = water(refresh)
    cokeys = defaultdict(set)
    for r in cached("components.json", lambda: [], False):
        cokeys[r["mukey"]].add((r["cokey"], r["compname"]))
    props = profile(refresh)
    young = geology()
    covered = young.pop("coverage", None)
    young_all = unary_union(list(young.values())) if young else None
    feats = []
    for mukey, g in geoms.items():
        if g.is_empty or mukey not in soil:
            continue
        answers = dict(use.get(mukey, {}))
        if soil[mukey]["order"] and wet.get(soil[mukey]["cokey"]):
            answers["flood"] = wet[soil[mukey]["cokey"]]   # the flooding of the soil described, not of Urban land on top of it
        if soil[mukey]["order"] is None:
            # No classified soil (rock, urban land, water, salt flats, tidal swamps). Farming and building are left unrated: NRCS calls the sea
            # "not prime farmland". Flooding is a property of the place, so it keeps the worst class NRCS gives any component (a tidal swamp
            # floods often, a limestone outcrop never), except for water, and leaving out Urban land components, whose "none" is a convention, not a finding
            answers = dict.fromkeys(answers)
            if not soil[mukey]["name"].startswith("Water"):
                classes = [wet.get(c) for c, name in cokeys[mukey] if name != "Urban land"]
                answers["flood"] = next((k for k in ("frequent", "sometimes", "wet", "no") if k in classes), None)
        p = {"mukey": mukey, **soil[mukey], **answers}
        p["name_es"] = spanish(p["name"])
        chem = props.get(soil[mukey]["cokey"], {}) if soil[mukey]["order"] else {}   # Urban land, rock and water have no horizons to read
        p.update({k: chem.get(k) for k in CHEM})
        if p["comp"] == "Urban land" and p["order"] is None and young:
            # Urban land alone: the soil survey says nothing of the ground under it. Split it by the geologic map: on young river, swamp or beach
            # deposits it is land that can flood ("geo_wet"); elsewhere (rock, older terraces) the map has no sign of it ("geo_dry")
            wet_part = _polygonal(set_precision(g.intersection(young_all), 1e-5))
            dry_part = _polygonal(set_precision(g.intersection(covered).difference(young_all), 1e-5))
            off_part = _polygonal(set_precision(g.difference(covered), 1e-5))   # outside the sheets (Vieques): no answer
            if not off_part.is_empty and off_part.area > 1e-8:
                feats.append({"type": "Feature", "properties": p, "geometry": mapping(off_part)})
            for part, k in ((wet_part, "geo_wet"), (dry_part, "geo_dry")):
                if not part.is_empty and part.area > 1e-8:
                    unit = max(young, key=lambda u: young[u].intersection(part).area) if k == "geo_wet" else None
                    feats.append({"type": "Feature", "properties": {**p, "flood": k, "geo": unit}, "geometry": mapping(part)})
            continue
        feats.append({"type": "Feature", "properties": p, "geometry": mapping(g)})
    fc = {"type": "FeatureCollection", "source": SOURCES["ssurgo"], "features": feats}
    OUT.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    count = lambda k: dict(sorted(((v, sum(1 for f in feats if f["properties"][k] == v)) for v in {f["properties"][k] for f in feats}), key=lambda x: -x[1]))
    print(f"  {len(feats):,} map units -> {OUT.name} ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(f"  orders: {count('order')}")
    print(f"  origins: {count('origin')}")
    print(f"  with a slope: {sum(1 for f in feats if f['properties']['slope'] is not None)}")
    for k in ("farm", "build", "flood"):
        print(f"  {k}: {count(k)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="query Soil Data Access again")
    build(ap.parse_args().refresh)
