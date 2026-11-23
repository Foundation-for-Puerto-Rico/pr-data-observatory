"""Transmission lines for the PR Data Observatory: OpenStreetMap's 230, 115 and 38 kV lines and cables, simplified to about 100 m, for the "Transmission lines"
layer of the 2D map and the 3D view (core/facilities.js draws it, coloured and sized by voltage). HANDOFF decision 104, step 2; docs/energy.md.

    python power_lines.py              # build site/data/power_lines.geojson (asks Overpass only when cache/energy/osm_power.json is missing)
    python power_lines.py --refresh    # ask Overpass again
    python power_lines.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source, no key: OpenStreetMap through the Overpass API (ODbL 1.0; facilities.OVERPASS servers, which refuse GitHub's runners, so this is renewed by hand with
the other OpenStreetMap files, unit 'osm' of refresh/sources.json). Asked: ways tagged power=line or power=cable, and power=substation (ways and nodes).

Decision 104 (c). LUMA asks the Energy Bureau to treat the location of its lines as Critical Energy Infrastructure Information, and EIA does not publish
substation locations. The lines are mapped in OpenStreetMap and visible on the ground, so the layer draws them, but only their shape: each way is simplified
to about 100 m (Douglas-Peucker, 0.0009 degrees), ways of the same voltage are joined, and no name, operator, circuit number or tower is kept. Substations are
never drawn: they are counted by municipio (the point inside the outline that holds it) in the file's notes.

Voltage. A way's voltage is the highest of its 'voltage' tag (several circuits are separated by ';'). Only 230, 115 and 38 kV are drawn; ways with another
voltage or none are left out and their length is given in the notes. Lengths are measured on the ways as mapped, before simplifying.

Output: site/data/power_lines.geojson, one MultiLineString per voltage and kind ({kv: 230 | 115 | 38, cable: true for underground or submarine cable}), with
notes: km by voltage, km left out, the substations by voltage class and by municipio, and the OpenStreetMap date.
"""

import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import requests

import facilities as fac
import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "energy"
RAW = CACHE / "osm_power.json"
OUT = hs.OUT / "power_lines.geojson"
log = hs.log
BBOX = (17.6, -67.95, 18.65, -65.2)   # south, west, north, east: Mona to Culebra
QUERY = """[out:json][timeout:240];
(way["power"~"^(line|cable)$"]({s},{w},{n},{e});way["power"="substation"]({s},{w},{n},{e});node["power"="substation"]({s},{w},{n},{e}););
out tags geom;"""
KV = (230, 115, 38)
TOL = 0.0009          # degrees, about 100 m at 18 degrees north
FLOOR_KM = {230: 600, 115: 700}   # 752 and 900 km on 2026-11-13: less means Overpass answered with part of the island


def fetch(refresh=False):
    if RAW.exists() and not refresh:
        return json.loads(RAW.read_text(encoding="utf-8"))
    s, w, n, e = BBOX
    q = QUERY.format(s=s, w=w, n=n, e=e)
    d = None
    for attempt in range(4):
        for ep in fac.OVERPASS:
            try:
                r = requests.post(ep, data={"data": q}, headers=fac.UA, timeout=300)
                r.raise_for_status()
                d = r.json()
                break
            except (requests.RequestException, ValueError) as ex:
                log(f"  {ep}: {type(ex).__name__}; trying the next server")
                time.sleep(5)
        if d is not None:
            break
        time.sleep(30 * (attempt + 1))
    if d is None:
        raise SystemExit("power_lines: no Overpass server answered; try again later")
    CACHE.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  Overpass: {len(d.get('elements', []))} power features, OpenStreetMap of {d.get('osm3s', {}).get('timestamp_osm_base', '?')}")
    return d


def kv_of(tag):
    """The highest voltage of a 'voltage' tag, in kV, or None ('230000;115000' -> 230; '' -> None)."""
    vs = [int(x) for x in str(tag or "").replace(" ", "").split(";") if x.isdigit()]
    return round(max(vs) / 1000) if vs else None


def km_of(coords):
    """Length of a lon/lat line in km (equirectangular at each segment's latitude; within 0.1% over Puerto Rico)."""
    t = 0.0
    for (x0, y0), (x1, y1) in zip(coords, coords[1:]):
        k = math.cos(math.radians((y0 + y1) / 2))
        t += 6371.0088 * math.hypot(math.radians(x1 - x0) * k, math.radians(y1 - y0))
    return t


def r5(c):
    return [round(c[0], 5), round(c[1], 5)]


def build(refresh=False, check=False):
    from shapely.geometry import LineString, MultiLineString
    from shapely.ops import linemerge
    if check and not RAW.exists():
        log(f"power_lines --check: {RAW.name} is not in the cache")
        return 1
    d = fetch(refresh) if not check else json.loads(RAW.read_text(encoding="utf-8"))
    M = fac.Munis()
    parts, km, left, subs, sub_muni = {}, Counter(), Counter(), Counter(), {}
    for el in d.get("elements", []):
        t = el.get("tags", {})
        if t.get("power") == "substation":
            if el["type"] == "node":
                lon, lat = el["lon"], el["lat"]
            else:
                g = [p for p in el.get("geometry", []) if p]
                if not g:
                    continue
                lon, lat = sum(p["lon"] for p in g) / len(g), sum(p["lat"] for p in g) / len(g)
            v = kv_of(t.get("voltage"))
            cls = "115_230" if v and v >= 115 else "38" if v == 38 else "other_or_untagged"
            subs[cls] += 1
            geoid = M.at(lon, lat)
            if geoid:
                sub_muni[geoid] = sub_muni.get(geoid, 0) + 1
            continue
        if el["type"] != "way" or t.get("power") not in ("line", "cable"):
            continue
        coords = [(p["lon"], p["lat"]) for p in el.get("geometry", []) if p]
        if len(coords) < 2:
            continue
        v, length = kv_of(t.get("voltage")), km_of(coords)
        if v not in KV:
            left["untagged" if v is None else "other"] += length
            continue
        cable = t.get("power") == "cable"
        km[(v, cable)] += length
        parts.setdefault((v, cable), []).append(LineString(coords))
    feats = []
    for (v, cable) in sorted(parts, key=lambda k: (-k[0], k[1])):
        merged = linemerge(parts[(v, cable)])
        lines = list(merged.geoms) if isinstance(merged, MultiLineString) else [merged]
        simple = [ln.simplify(TOL, preserve_topology=False) for ln in lines]
        geom = [[r5(c) for c in ln.coords] for ln in simple if ln.length > 0]
        props = {"kv": v, "km": round(km[(v, cable)], 1)}
        if cable:
            props["cable"] = True
        feats.append({"type": "Feature", "properties": props, "geometry": {"type": "MultiLineString", "coordinates": geom}})
    by_kv = {v: round(km[(v, False)] + km[(v, True)], 1) for v in KV}
    for v, floor in FLOOR_KM.items():
        if by_kv[v] < floor:
            raise SystemExit(f"power_lines: only {by_kv[v]} km of {v} kV lines (752 and 900 km in November 2026); not written")
    base = d.get("osm3s", {}).get("timestamp_osm_base", "")[:10]
    notes = {"km_by_kv": {str(v): by_kv[v] for v in KV}, "cable_km": round(sum(x for (v, c), x in km.items() if c), 1),
             "km_left_out": {"untagged": round(left["untagged"], 1), "other_voltage": round(left["other"], 1)},
             "simplified_deg": TOL, "points": sum(len(ln) for f in feats for ln in f["geometry"]["coordinates"]),
             "substations": sum(subs.values()), "substations_by_class": dict(sorted(subs.items())),
             "substations_by_municipio": {g: sub_muni[g] for g in sorted(sub_muni)},
             "irp_2019_circuit_km": {"230": 665, "115": 1130, "38": 2214}}
    out = {"type": "FeatureCollection", "source": "osm", "vintage": base, "built": base, "notes": notes, "features": feats}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        log(f"power_lines.geojson {'is' if same else 'is NOT'} what the cache gives")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name}: {by_kv} km, {notes['cable_km']} km of cable, {notes['points']} points after simplifying, {notes['substations']} substations counted "
        f"(not drawn) in {len(sub_muni)} municipios; left out {notes['km_left_out']} km; {len(text) // 1024} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
