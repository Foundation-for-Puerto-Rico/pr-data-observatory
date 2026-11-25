"""Watersheds, streams and the drainage network for the PR Data Observatory: the USGS Watershed Boundary Dataset's subwatersheds (HUC-12) with their residents,
the main streams, and the catchments of NHDPlus High Resolution linked downstream, so the map can show the land that drains to any point ("What drains here").
Step 3 of the GIS tools plan (docs/gis-tools-proposal-2026-11.md, HANDOFF decision 93; method in docs/watersheds.md).

    python watersheds.py             # build site/data/watersheds.geojson, streams.geojson and catchments.geojson (downloads into cache/watersheds/ what is missing)
    python watersheds.py --refresh   # download again
    python watersheds.py --check     # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)

The sources (public domain, USGS; read from The National Map's ArcGIS services, no key):
  - Watershed Boundary Dataset (WBD), subwatersheds (HUC-12) and subbasins (HUC-8) of subregion 2101 (Puerto Rico): wbd/MapServer layers 6 and 4.
  - NHDPlus High Resolution, VPU 2101: the network flowlines (NetworkNHDFlowline, layer 3: hydrologic sequence, the downstream one, stream order, drainage
    area, name) and the catchments (NHDPlusCatchment, layer 10), the land that drains directly to each flowline. A catchment and its flowline share an NHDPlusID.

How it is made (docs/watersheds.md):
  - Catchments: outlines simplified by the service to about 20 m (maxAllowableOffset 0.0002 degree), coordinates to 5 decimals. Each gets `dn`, the index of the
    catchment of its flowline's downstream main-path flowline (DnHydroSeq), or -1 at the sea, a sink or the network's edge. Minor branches of a divergence are
    not followed: water is routed down the main path, as NHDPlus's own drainage areas are.
  - Minor branches: where a river splits, NHDPlus routes the water down the main path, so the minor branch (Divergence 2) has nothing upstream through DnHydroSeq.
    Its catchment gets `via`, the catchment of the reach it splits from (the flowline whose DnMinorHyd is it), so the land upstream of the split drains to it too.
  - Upstream: the land that drains to a catchment is it and every catchment whose chain of dn (and via) reaches it. The browser walks the chain backward
    (Core.study.upstream).
  - Subwatersheds: WBD HUC-12 outlines simplified to about 20 m, with their HUC-8 subbasin's name, their area (WBD) and their residents (2020 census blocks whose
    point is inside, as the study areas count them).
  - Streams: the flowlines that drain at least 5 km2, simplified to about 20 m, with name, stream order and drainage area.
  - Checks that stop the build: 12,000 to 16,000 catchments and flowlines; every dn is a valid index and the network has no cycle; the catchments add up to
    8,500 to 10,500 km2; the drainage area the network gives at the mouths of the five largest rivers, and at the largest minor branch, is within 3% of
    NHDPlus's own TotDASqKm; 200 to 260 HUC-12s;
    and the HUC-12 residents add up to at least 99% of Puerto Rico's 2020 census residents.
No personal data: outlines of land and water, and residents counted by area.
"""

import json
import sys
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "watersheds"
OUT = hs.OUT
OUT_SHEDS = OUT / "watersheds.geojson"
OUT_STREAMS = OUT / "streams.geojson"
OUT_CATCH = OUT / "catchments.geojson"
log = hs.log

SVC = "https://hydro.nationalmap.gov/arcgis/rest/services"
WBD = SVC + "/wbd/MapServer"
NHD = SVC + "/NHDPlus_HR/MapServer"
VPU = "2101"
SIMPLIFY = 0.0002                 # degrees, about 20 m
STREAM_MIN_KM2 = 5.0
N_RANGE = (12_000, 16_000)
AREA_RANGE = (8_500, 10_500)
HUC12_RANGE = (200, 260)
MOUTH_TOL = 0.03
MIN_RESIDENTS = 0.99
UA = {"User-Agent": "PR-Data-Observatory/1.0 (Foundation for Puerto Rico; open-data build)"}


def query(url, where, fields, geometry=False, page=1000, simplify=None):
    """Every feature of a layer that matches `where`, page by page (GeoJSON when geometry, else attributes only), in OBJECTID order."""
    out, offset = [], 0
    while True:
        p = {"where": where, "outFields": fields, "returnGeometry": "true" if geometry else "false", "outSR": "4326", "orderByFields": "OBJECTID",
             "resultOffset": str(offset), "resultRecordCount": str(page), "f": "geojson" if geometry else "json"}
        if geometry and simplify:
            p.update({"maxAllowableOffset": str(simplify), "geometryPrecision": "5"})
        for attempt in range(6):
            try:
                r = requests.get(url + "/query", params=p, headers=UA, timeout=300)
                r.raise_for_status()
                d = r.json()
                if "error" in d:
                    raise RuntimeError(d["error"])
                break
            except Exception as e:   # the service times out now and then: wait and ask again
                if attempt == 5:
                    raise
                log(f"  {url.rsplit('/', 2)[-2]} offset {offset}: {e}; again")
                import time
                time.sleep(5 * (attempt + 1))
        feats = d["features"]
        out += feats if geometry else [f["attributes"] for f in feats]
        if len(feats) < page:
            return out
        offset += len(feats)


def cached(name, fn, refresh=False, offline=False):
    p = CACHE / name
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"watersheds --check: {p} is missing (python watersheds.py downloads it)")
    d = fn()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    return d


def download(refresh=False, offline=False):
    log("  NHDPlus HR flowlines (attributes)…")
    flow = cached("flowlines.json", lambda: query(NHD + "/3", f"vpuid='{VPU}'", "nhdplusid,hydroseq,dnhydroseq,dnminorhyd,streamorde,totdasqkm,areasqkm,gnis_name,terminalfl,divergence", page=2000), refresh, offline)
    log("  NHDPlus HR streams (geometry)…")
    streams = cached("streams.json", lambda: query(NHD + "/3", f"vpuid='{VPU}' AND totdasqkm>={STREAM_MIN_KM2}", "nhdplusid,gnis_name,streamorde,totdasqkm", geometry=True, simplify=SIMPLIFY), refresh, offline)
    log("  NHDPlus HR catchments (geometry)…")
    catch = cached("catchments.json", lambda: query(NHD + "/10", f"vpuid='{VPU}'", "nhdplusid,areasqkm", geometry=True, simplify=SIMPLIFY, page=1000), refresh, offline)
    log("  WBD subwatersheds and subbasins…")
    h12 = cached("huc12.json", lambda: query(WBD + "/6", f"huc12 LIKE '{VPU}%'", "huc12,name,areasqkm", geometry=True, simplify=SIMPLIFY), refresh, offline)
    h8 = cached("huc8.json", lambda: query(WBD + "/4", f"huc8 LIKE '{VPU}%'", "huc8,name"), refresh, offline)
    return flow, streams, catch, h12, h8


def round_geom(g):
    def r(c):
        return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    return {"type": g["type"], "coordinates": r(g["coordinates"])}


def compute(refresh=False, offline=False):
    import numpy as np
    import shapely
    from shapely.geometry import shape
    flow, streams, catch, h12, h8 = download(refresh, offline)
    by_seq = {f["hydroseq"]: f for f in flow if f.get("hydroseq")}
    fl_by_id = {int(f["nhdplusid"]): f for f in flow}
    catch = [c for c in catch if c.get("geometry")]
    catch.sort(key=lambda c: int(c["properties"]["nhdplusid"]))
    idx = {int(c["properties"]["nhdplusid"]): i for i, c in enumerate(catch)}
    n = len(catch)
    dn = np.full(n, -1, dtype=np.int64)
    names = [""] * n
    for i, c in enumerate(catch):
        f = fl_by_id.get(int(c["properties"]["nhdplusid"]))
        if not f:
            continue
        names[i] = f.get("gnis_name") or ""
        if f.get("terminalfl") == 1:   # a river's last reach: NHDPlus links mouths to each other along the coast, which is not water draining downstream
            continue
        d = by_seq.get(f.get("dnhydroseq"))
        while d is not None and int(d["nhdplusid"]) not in idx:   # a downstream flowline with no catchment of its own (a short connector): go on down
            d = by_seq.get(d.get("dnhydroseq"))
        if d is not None:
            dn[i] = idx[int(d["nhdplusid"])]
    area = np.array([float(c["properties"].get("areasqkm") or 0) for c in catch])
    via = [[] for _ in range(n)]   # a minor branch's catchment -> the catchments of the reaches it splits from
    ups = {}
    for f in flow:
        ups.setdefault(f.get("dnhydroseq"), []).append(f)
    for f in flow:
        m = by_seq.get(f.get("dnminorhyd")) if f.get("dnminorhyd") else None
        if m is None:
            continue
        hops = 0
        while f is not None and int(f["nhdplusid"]) not in idx and hops < 50:   # the reach it splits from has no catchment: up its largest tributary to one that does
            f = max(ups.get(f["hydroseq"], []), key=lambda g: g.get("totdasqkm") or 0, default=None); hops += 1
        if f is None or int(f["nhdplusid"]) not in idx:
            continue
        hops = 0
        while m is not None and int(m["nhdplusid"]) not in idx and hops < 50:   # the branch's first reach has no catchment (a short connector): its first one that does
            m = by_seq.get(m.get("dnhydroseq")); hops += 1
        if m is not None and int(m["nhdplusid"]) in idx:
            via[idx[int(m["nhdplusid"])]].append(idx[int(f["nhdplusid"])])

    def drains_to(i):   # the land upstream of catchment i, through dn and via (a set, so land reached twice counts once)
        kids = drains_to.kids
        seen, stack = {i}, [i]
        while stack:
            k = stack.pop()
            for c in kids.get(k, ()):
                if c not in seen:
                    seen.add(c); stack.append(c)
            for v in via[k]:
                if v not in seen:
                    seen.add(v); stack.append(v)
        return float(area[list(seen)].sum())
    drains_to.kids = {}
    for k in range(n):
        if dn[k] >= 0:
            drains_to.kids.setdefault(int(dn[k]), []).append(k)

    # the network: no cycle, and the upstream area at each catchment (summed in topological order)
    indeg = np.zeros(n, dtype=np.int64)
    for i in range(n):
        if dn[i] >= 0:
            indeg[dn[i]] += 1
    up = area.copy()
    order, stack = [], [i for i in range(n) if indeg[i] == 0]
    deg = indeg.copy()
    while stack:
        i = stack.pop(); order.append(i)
        j = dn[i]
        if j >= 0:
            up[j] += up[i]; deg[j] -= 1
            if deg[j] == 0:
                stack.append(j)
    bad = []
    if len(order) != n:
        bad.append(f"the downstream links have a cycle ({n - len(order)} catchments in it)")
    if not N_RANGE[0] <= n <= N_RANGE[1] or not N_RANGE[0] <= len(flow) <= N_RANGE[1]:
        bad.append(f"{n:,} catchments and {len(flow):,} flowlines (expected {N_RANGE[0]:,} to {N_RANGE[1]:,})")
    total = float(area.sum())
    if not AREA_RANGE[0] <= total <= AREA_RANGE[1]:
        bad.append(f"the catchments add up to {total:,.0f} km2 (expected {AREA_RANGE[0]:,} to {AREA_RANGE[1]:,})")
    # the five largest named rivers at their largest reach (near the mouth), and the largest minor branch: the network's upstream area against NHDPlus's own
    mouths = []
    for f in sorted(flow, key=lambda f: -(f.get("totdasqkm") or 0)):
        i = idx.get(int(f["nhdplusid"]))
        if i is None or f.get("divergence") == 2 or not f.get("gnis_name") or f["gnis_name"] in [m[0] for m in mouths]:
            continue
        mouths.append((f.get("gnis_name") or "(no name)", float(f["totdasqkm"]), drains_to(i)))
        if len(mouths) == 5:
            break
    minor = next((f for f in sorted(flow, key=lambda f: -(f.get("totdasqkm") or 0)) if f.get("divergence") == 2 and int(f["nhdplusid"]) in idx), None)
    if minor is not None:
        mouths.append(((minor.get("gnis_name") or "(no name)") + " (minor branch)", float(minor["totdasqkm"]), drains_to(idx[int(minor["nhdplusid"])])))
    for name, nhd, ours in mouths:
        if abs(ours / nhd - 1) > MOUTH_TOL:
            bad.append(f"{name}: the network drains {ours:,.1f} km2 to its mouth, NHDPlus says {nhd:,.1f}")
    biggest = max(float(f.get("totdasqkm") or 0) for f in flow)   # no catchment drains more land than the largest river: mouths are not chained along the coast
    tops = [i for i in range(n) if dn[i] < 0]
    widest = max((drains_to(i) for i in tops), default=0)
    if widest > biggest * (1 + MOUTH_TOL):
        bad.append(f"an outlet drains {widest:,.1f} km2, more than the largest river ({biggest:,.1f} km2): river mouths are chained")
    if not HUC12_RANGE[0] <= len(h12) <= HUC12_RANGE[1]:
        bad.append(f"{len(h12)} HUC-12 subwatersheds (expected {HUC12_RANGE[0]} to {HUC12_RANGE[1]})")

    # residents of each HUC-12 (2020 census blocks by their point, as the study areas count them)
    blocks = json.loads((OUT / "population_blocks.json").read_text(encoding="utf-8"))
    bl = np.array([[b[0], b[1], b[2]] for b in blocks], dtype=float)
    geoms = [shape(h["geometry"]) for h in h12]
    tree = shapely.STRtree(geoms)
    pts = shapely.points(bl[:, 0], bl[:, 1])
    pi, gi = tree.query(pts, predicate="intersects")
    first = {}
    for p, g in sorted(zip(pi.tolist(), gi.tolist())):
        first.setdefault(p, g)
    res = np.zeros(len(h12))
    for p, g in first.items():
        res[g] += bl[p, 2]
    pr_res = float(bl[:, 2].sum())
    if res.sum() < MIN_RESIDENTS * pr_res:
        bad.append(f"the HUC-12s hold {res.sum():,.0f} of {pr_res:,.0f} residents (expected {MIN_RESIDENTS:.0%} or more)")
    if bad:
        raise SystemExit("watersheds: the network fails its checks:\n  " + "\n  ".join(bad))
    log(f"  {n:,} catchments ({total:,.0f} km2), {len(flow):,} flowlines, {len(h12)} HUC-12s, {len(streams)} streams of {STREAM_MIN_KM2:g} km2 or more; "
        + "; ".join(f"{m[0]} {m[2]:,.0f} km2 (NHDPlus {m[1]:,.0f})" for m in mouths))

    h8n = {h["huc8"]: h["name"] for h in h8}
    sheds = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"huc12": h["properties"]["huc12"], "name": h["properties"]["name"], "huc8": h["properties"]["huc12"][:8],
                                           "basin": h8n.get(h["properties"]["huc12"][:8], ""), "km2": round(float(h["properties"]["areasqkm"] or 0), 2), "residents": int(round(res[k]))},
         "geometry": round_geom(h["geometry"])} for k, h in enumerate(sorted(h12, key=lambda h: h["properties"]["huc12"]))]}
    # the residents were counted in the order of h12 as downloaded: recount in the sorted order
    order12 = sorted(range(len(h12)), key=lambda k: h12[k]["properties"]["huc12"])
    for f, k in zip(sheds["features"], order12):
        f["properties"]["residents"] = int(round(res[k]))
    strm = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": s["properties"].get("gnis_name") or "", "order": s["properties"].get("streamorde"),
                                           "km2": round(float(s["properties"].get("totdasqkm") or 0), 1)}, "geometry": round_geom(s["geometry"])}
        for s in sorted(streams, key=lambda s: int(s["properties"]["nhdplusid"])) if s.get("geometry")]}
    cat = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"dn": int(dn[i]), **({"via": sorted(via[i])} if via[i] else {}), "km2": round(float(area[i]), 4), **({"name": names[i]} if names[i] else {})}, "geometry": round_geom(c["geometry"])}
        for i, c in enumerate(catch)]}
    notes = {"vpu": VPU, "catchments": n, "minor_branches_linked": sum(1 for v in via if v), "catchments_km2": round(total, 1), "flowlines": len(flow), "huc12": len(h12), "streams": len(strm["features"]),
             "mouths": [{"name": m[0], "nhdplus_km2": round(m[1], 1), "network_km2": round(m[2], 1)} for m in mouths],
             "residents_in_huc12": int(res.sum()), "residents_pr": int(pr_res)}
    for d in (sheds, strm, cat):
        d["notes"] = notes
    return sheds, strm, cat


def build(refresh=False, check=False):
    files = dict(zip((OUT_SHEDS, OUT_STREAMS, OUT_CATCH), compute(refresh, offline=check)))
    status = 0
    for path, d in files.items():
        text = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        if check:
            same = path.exists() and path.read_text(encoding="utf-8") == text
            print(f"{path.name} {'matches the cache' if same else 'is not what the cache gives: run python watersheds.py'}")
            status = status or (0 if same else 1)
            continue
        path.write_text(text, encoding="utf-8")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:,.0f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
