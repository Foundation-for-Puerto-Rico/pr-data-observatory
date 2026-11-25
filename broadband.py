"""Fixed broadband availability for the PR Data Observatory, by municipio and barrio: how many of the places where the FCC says a home or business could get
internet service (broadband serviceable locations) are served, underserved or unserved, and how many can get fiber, as of June 30 of each year since 2023.

    python broadband.py              # download the June releases missing from cache/broadband/ (needs FCC_BDC_USERNAME and FCC_BDC_HASH) and build the two files below
    python broadband.py --refresh    # list the FCC's releases again and download every June release again
    python broadband.py --check      # rebuild from the cached summaries and exit 1 when a published file is not what they give (no network, no secret, nothing written)
    python broadband.py --diagnose   # what the FCC API answers with the account: the release dates and Puerto Rico's files (prints no secret)

Writes site/data/broadband_series.json (78 municipios and Puerto Rico) and site/data/broadband_barrio.json (901 barrios), the same keys at both levels.
And the map layer site/data/broadband_hex.geojson: the newest June release by H3 resolution-8 cell (the hexagons of about 0.74 km² the FCC gives each location),
only the cells with at least 10 locations (HEX_MIN); the others are counted in its notes. 2D map, 3D view and any map that reads Core.facilities (layer broadband).

The login. The FCC Broadband Data Collection (BDC) public data API answers 401 without an account. The build reads the account's username (the CORES email) from
FCC_BDC_USERNAME and its API token from FCC_BDC_HASH (in GitHub Actions, the repository secrets of those names; .github/workflows/broadband.yml) and sends them
only to broadbandmap.fcc.gov, in the username and hash_value headers the API asks for. Neither is printed, written to the cache, the repository or a published
file, and the site never calls the FCC (docs/broadband.md says how the account and the token are made).

The source. FCC, Broadband Data Collection, fixed broadband availability, the state files for Puerto Rico (category State, subcategory Location Coverage): one
row for each location, provider and technology, with the maximum advertised download and upload speeds and whether the service is low latency (100 ms or less).
Providers report them twice a year (as of June 30 and December 31); this build uses the June release of each year, so the years compare. Works of the US
Government, public domain.

How each figure is made (docs/broadband.md):
  - Locations: every location that appears in a fixed broadband file of the release (satellite service is reported for almost all of them). The FCC's list of
    locations (the Fabric) changes between releases, so a change in the count is partly a change of the list.
  - The NTIA BEAD tiers, by the best service a location can get over a reliable technology (copper, cable, fiber, licensed or licensed-by-rule fixed wireless)
    that is low latency: served at 100/20 Mbps or more (download/upload), underserved at 25/3 or more but less than 100/20, unserved below 25/3 or with no
    reliable technology (only satellite or unlicensed fixed wireless). Shares are of all the area's locations.
  - Fiber: the locations where any provider reports fiber to the premises, at any speed.
  - Places: a location belongs to its 2020 census block (block_geoid in the file); the block to its municipio by its id and to its barrio by the Census Bureau's
    internal point (geo.block_barrios). Counts add up exactly from barrios to municipios to Puerto Rico.
  - Checks that stop the build: every release between 900,000 and 1,500,000 locations, every municipio with locations, and nearly every block id known.
Availability is what providers report they can install within ten business days, not what anyone subscribes to (the survey's household internet share says
that) or the speed anyone gets. No personal data: the files hold counts and shares for areas; no location, address or provider list is published.
"""

import csv
import io
import json
import os
import sys
import time
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "broadband"
OUT = hs.OUT
OUT_SERIES = OUT / "broadband_series.json"
OUT_BARRIO = OUT / "broadband_barrio.json"
OUT_HEX = OUT / "broadband_hex.geojson"
log = hs.log

API = "https://broadbandmap.fcc.gov/api/public/map"
UA = "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"
FIRST_YEAR = 2023                     # the first June release of the BDC is June 30, 2022, but its Puerto Rico files are checked from 2023 on (the FCC's first rounds of challenges changed the list a lot)
RELIABLE = {"10", "40", "50", "71", "72"}   # copper, cable, fiber to the premises, licensed fixed wireless, licensed-by-rule fixed wireless (NTIA BEAD's reliable broadband)
FIBER = "50"
MIN_N, MAX_N = 900_000, 1_500_000
HEX_MIN = 10                          # a hexagon with fewer locations is counted in the file's notes, never drawn (a few homes would be shown one by one)
NO_SECRET = ("broadband: FCC_BDC_USERNAME and FCC_BDC_HASH are not both set, so nothing was downloaded. They are the FCC account's username and API token "
             "(repository secrets in GitHub Actions; docs/broadband.md).")


def secrets():
    u, h = os.environ.get("FCC_BDC_USERNAME", "").strip(), os.environ.get("FCC_BDC_HASH", "").strip()
    return (u, h) if u and h else None


def get(path, sec, stream=False, tries=4, timeout=600):
    hdr = {"username": sec[0], "hash_value": sec[1], "user-agent": UA}
    for i in range(tries):
        try:
            r = requests.get(f"{API}/{path}", headers=hdr, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(str(r.status_code))
            if r.status_code == 401:
                raise SystemExit("broadband: the FCC answered 401 (unauthorized): check the FCC_BDC_USERNAME and FCC_BDC_HASH secrets (docs/broadband.md)")
            r.raise_for_status()
            return r
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def june_releases(sec):
    """The as-of dates (YYYY-MM-DD) of the June availability releases from FIRST_YEAR on."""
    data = get("listAsOfDates", sec, timeout=120).json().get("data", [])
    ds = sorted({d["as_of_date"][:10] for d in data if d.get("data_type") == "availability"})
    return [d for d in ds if d[5:7] == "06" and int(d[:4]) >= FIRST_YEAR]


def state_files(sec, as_of):
    """Puerto Rico's fixed broadband location files of a release: [{file_id, technology_code, file_name}]."""
    files = get(f"downloads/listAvailabilityData/{as_of}", sec, timeout=300).json().get("data", [])
    out = [f for f in files if str(f.get("state_fips")) == "72" and f.get("category") == "State" and f.get("subcategory") == "Location Coverage"
           and f.get("technology_type") == "Fixed Broadband"]
    if not out:
        raise SystemExit(f"broadband: the FCC lists no Puerto Rico fixed broadband state files for {as_of}")
    return out


def summary_path(as_of):
    return CACHE / f"blocks_{as_of}.json"


def take(row, best, fiber, block, hexes=None):
    """Add one row of a location file: the location's block (and, when hexes is a dict, its H3 resolution-8 cell), its best tier so far (2 served,
    1 underserved, 0 unserved) and whether it has fiber."""
    loc, tech = row["location_id"], row["technology"]
    block.setdefault(loc, row["block_geoid"])
    if hexes is not None:
        hexes.setdefault(loc, row["h3_res8_id"])
    t = best.get(loc, 0)
    if tech in RELIABLE and row["low_latency"] == "1" and t < 2:
        dl, ul = float(row["max_advertised_download_speed"] or 0), float(row["max_advertised_upload_speed"] or 0)
        t = max(t, 2 if dl >= 100 and ul >= 20 else 1 if dl >= 25 and ul >= 3 else 0)
    best[loc] = t
    if tech == FIBER:
        fiber.add(loc)


def by_block(best, fiber, block):
    """{block geoid: [locations, served, underserved, unserved, fiber]}, sorted by block."""
    by = {}
    for loc, b in block.items():
        c = by.setdefault(b, [0, 0, 0, 0, 0])
        c[0] += 1
        c[1 + (2 - best[loc])] += 1
        c[4] += loc in fiber
    return dict(sorted(by.items()))


def by_hex(best, fiber, block, hexes):
    """{H3 cell: [locations, served, underserved, unserved, fiber, municipio]}, sorted by cell; the municipio is the one that holds most of the cell's
    locations (by their census blocks)."""
    by, mun = {}, {}
    for loc, h in hexes.items():
        c = by.setdefault(h, [0, 0, 0, 0, 0])
        c[0] += 1
        c[1 + (2 - best[loc])] += 1
        c[4] += loc in fiber
        mun.setdefault(h, Counter())[block[loc][:5]] += 1
    return {h: c + [mun[h].most_common(1)[0][0]] for h, c in sorted(by.items())}


def hex_path(as_of):
    return CACHE / f"hex_{as_of}.json"


def summarise(sec, as_of, with_hex=False):
    """Download a release's Puerto Rico files, give each location its tier and fiber flag, and keep the counts by census block in cache/broadband/
    (and, with with_hex, by H3 resolution-8 cell: the newest release only, for the map layer)."""
    files = state_files(sec, as_of)
    best, fiber, block = {}, set(), {}
    hexes = {} if with_hex else None
    rows = Counter()
    for f in sorted(files, key=lambda x: x["file_name"]):
        before = sum(rows.values())
        r = get(f"downloads/downloadFile/availability/{f['file_id']}", sec)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for name in z.namelist():
            with z.open(name) as fh:
                for row in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig")):
                    take(row, best, fiber, block, hexes)
                    rows[row["technology"]] += 1
        log(f"    {f['file_name']}: {sum(rows.values()) - before:,} rows")
    by = by_block(best, fiber, block)
    out = {"as_of": as_of, "files": sorted(f["file_name"] for f in files), "rows_by_technology": dict(sorted(rows.items())), "locations": len(block),
           "fields": ["locations", "served", "underserved", "unserved", "fiber"], "blocks": by}
    CACHE.mkdir(parents=True, exist_ok=True)
    summary_path(as_of).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    log(f"  {as_of}: {len(block):,} locations in {len(by):,} blocks")
    if with_hex:
        hx = by_hex(best, fiber, block, hexes)
        hex_path(as_of).write_text(json.dumps({"as_of": as_of, "resolution": 8, "fields": ["locations", "served", "underserved", "unserved", "fiber", "municipio"],
                                               "cells": hx}, separators=(",", ":")), encoding="utf-8")
        log(f"  {as_of}: {len(hx):,} H3 cells")
    return out


def summaries():
    out = {}
    for p in sorted(CACHE.glob("blocks_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["as_of"]] = d
    return out


def hex_layer(hx):
    """The map layer: a GeoJSON FeatureCollection of the H3 cells with at least HEX_MIN locations, each a hexagon with its counts as shares; the cells with
    fewer are counted in the notes only."""
    import h3
    feats, left_cells, left_locs = [], 0, 0
    for h, (n, s, u, x, f, m) in hx["cells"].items():
        if n < HEX_MIN:
            left_cells += 1
            left_locs += n
            continue
        ring = [[round(lng, 4), round(lat, 4)] for lat, lng in h3.cell_to_boundary(h)]   # 4 decimals: about 11 m, for hexagons about 460 m across
        ring.append(ring[0])
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h": h, "n": n, "below_pct": round((u + x) / n * 100, 1), "unserved_pct": round(x / n * 100, 1), "fiber_pct": round(f / n * 100, 1), "mun": m}})
    total = sum(c[0] for c in hx["cells"].values())
    notes = {"as_of": hx["as_of"], "resolution": 8, "min_locations": HEX_MIN, "hexes_drawn": len(feats), "locations_drawn": total - left_locs,
             "hexes_left_out": left_cells, "locations_left_out": left_locs, "locations": total,
             "source": "broadband.py: FCC Broadband Data Collection, Puerto Rico state location files of the newest June release; each location in the H3 cell the FCC gives it (h3_res8_id); tiers as NTIA's BEAD program defines them (docs/broadband.md)"}
    return {"type": "FeatureCollection", "notes": notes, "features": feats}


def places():
    """(municipio ids, names, barrio ids, {block geoid: barrio geoid}) from the observatory's crosswalk and the 2020 census blocks."""
    import geo
    import network
    names, mids = hs.municipalities()
    cw = json.loads((OUT / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    F = {f: i for i, f in enumerate(cw["fields"])}
    bids = [r[F["id"]] for r in cw["units"]["barrio"]]
    table = network.load_block_table(ROOT / "cache" / "network", False)
    barrio = geo.block_barrios(table)
    return mids, names, bids, dict(zip((r[0] for r in table["rows"]), barrio))


def assemble(S, mids, names, bids, barrio_of):
    years = sorted(int(a[:4]) for a in S)
    mi, bi = {m: i for i, m in enumerate(mids)}, {b: i for i, b in enumerate(bids)}
    M, Bv, bad, unknown = {}, {}, [], {}
    for as_of, d in sorted(S.items()):
        m = [[0] * 5 for _ in mids]
        b = [[0] * 5 for _ in bids]
        miss = 0
        for blk, c in d["blocks"].items():
            k = mi.get(blk[:5])
            if k is None:
                miss += c[0]
                continue
            for j in range(5):
                m[k][j] += c[j]
            br = barrio_of.get(blk)
            if br in bi:
                for j in range(5):
                    b[bi[br]][j] += c[j]
            else:
                unknown[as_of] = unknown.get(as_of, 0) + c[0]
        tot = [sum(r[j] for r in m) for j in range(5)]
        if not MIN_N <= tot[0] <= MAX_N:
            bad.append(f"{as_of}: {tot[0]:,} locations (expected {MIN_N:,} to {MAX_N:,})")
        if any(r[0] == 0 for r in m):
            bad.append(f"{as_of}: municipios with no location: {[names[i] for i, r in enumerate(m) if r[0] == 0]}")
        if miss or unknown.get(as_of, 0) > tot[0] * 0.001:
            bad.append(f"{as_of}: {miss:,} locations outside the 78 municipios and {unknown.get(as_of, 0):,} in a block with no barrio")
        M[as_of[:4]] = m + [tot]
        Bv[as_of[:4]] = b
    if bad:
        raise SystemExit("broadband: the counts fail their checks:\n  " + "\n  ".join(bad))

    def pct(c, j):
        return round(c[j] / c[0] * 100, 1) if c[0] else None
    G = "Infrastructure · Broadband (FCC)"
    newest = max(S)
    REF = (f"FCC Broadband Data Collection, fixed broadband availability, Puerto Rico state location files, releases as of June 30 of {years[0]}-{years[-1]} "
           f"(newest as of {newest}); tiers as NTIA's BEAD program defines them")
    WHAT = (" A broadband serviceable location is a place where the FCC's list (the Fabric) says a home or business is or could be served: a house, an apartment "
            "building, a business. Availability is what providers report they can install within ten business days, not what anyone subscribes to or the speed "
            "anyone gets. Each year's value is the release as of June 30 of that year. Each location belongs to its 2020 census block.")
    TIER = (" Reliable technologies are copper, cable, fiber to the premises and licensed or licensed-by-rule fixed wireless, with low latency (100 ms or less); "
            "satellite and unlicensed fixed wireless do not count (NTIA's BEAD rules).")

    def var(key, label, unit, d, typ, definition, fn, **extra):
        return ({"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["fcc_bdc", "census_tiger"], "ref": REF,
                 "definition": definition + WHAT, "family": "broadband", "counted": False, "noPerHU": True, "barrioFile": OUT_BARRIO.name, **extra,
                 "years": {y: [fn(c) for c in M[y]] for y in M}},
                {"key": key, "years": {y: [fn(c) for c in Bv[y]] for y in Bv}})
    pairs = [
        var("bb_locations", "Broadband serviceable locations (FCC)", "", 0, "count", "The number of broadband serviceable locations in the area.", lambda c: c[0], classes="jenks"),
        var("bb_served_pct", "Locations served at 100/20 Mbps or more (FCC, %)", "%", 1, "rate",
            "The share of the area's locations that can get 100 Mbps download and 20 Mbps upload or more over a reliable technology: 'served' in NTIA's BEAD terms." + TIER, lambda c: pct(c, 1)),
        var("bb_underserved_pct", "Locations underserved, 25/3 to 100/20 Mbps (FCC, %)", "%", 1, "rate",
            "The share of the area's locations whose best service over a reliable technology is at least 25/3 Mbps but less than 100/20: 'underserved' in NTIA's BEAD terms." + TIER, lambda c: pct(c, 2)),
        var("bb_unserved_pct", "Locations unserved, below 25/3 Mbps (FCC, %)", "%", 1, "rate",
            "The share of the area's locations with no service of 25/3 Mbps or more over a reliable technology (they may still have satellite or unlicensed fixed wireless): 'unserved' in NTIA's BEAD terms." + TIER, lambda c: pct(c, 3)),
        var("bb_below100_n", "Locations below 100/20 Mbps, underserved or unserved (FCC)", "", 0, "count",
            "The number of the area's locations that are underserved or unserved: those that cannot get 100/20 Mbps over a reliable technology (the locations NTIA's BEAD program can fund)." + TIER, lambda c: c[2] + c[3], classes="jenks"),
        var("bb_fiber_pct", "Locations where fiber is available (FCC, %)", "%", 1, "rate",
            "The share of the area's locations where at least one provider reports fiber to the premises, at any speed.", lambda c: pct(c, 4)),
    ]
    SOURCES = {"fcc_bdc": {"name": "FCC — Broadband Data Collection, fixed broadband availability (National Broadband Map)", "url": "https://broadbandmap.fcc.gov/data-download",
                           "license": "US Government work (no US copyright)",
                           "note": "Puerto Rico's state location files of each June release, read with FPR's FCC account (GitHub Actions secrets); only counts by area are published."},
               "census_tiger": {"name": "US Census Bureau — 2020 census blocks and barrio outlines (TIGER/Line)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                                "license": "US Government work (no US copyright)", "note": "Each location's census block, placed in its barrio by the block's internal point."}}
    notes = {"releases": sorted(S), "locations_pr": {a[:4]: S[a]["locations"] for a in sorted(S)}, "files_newest": S[newest]["files"],
             "rows_by_technology_newest": S[newest]["rows_by_technology"], "in_a_block_with_no_barrio": unknown,
             "tiers": {"served": "100/20 Mbps or more", "underserved": "25/3 or more, below 100/20", "unserved": "below 25/3, or no reliable technology",
                       "reliable_technology_codes": sorted(RELIABLE), "low_latency": "required"}}
    series = {"as_of": newest[:7], "years": years, "geo": {"ids": mids + ["72"], "names": names + ["Puerto Rico"]}, "vars": [p[0] for p in pairs], "sources": SOURCES, "notes": notes}
    barrio = {"level": "barrio", "years": years, "geo": {"ids": bids}, "vars": [p[1] for p in pairs],
              "notes": {"areas": len(bids), "source": "broadband.py; the municipio values and the method are in broadband_series.json"}}
    pr = M[str(years[-1])][-1]
    log(f"  {newest}: Puerto Rico {pr[0]:,} locations; served {pct(pr, 1)}%, underserved {pct(pr, 2)}%, unserved {pct(pr, 3)}%, fiber {pct(pr, 4)}%")
    return series, barrio


def build(refresh=False, check=False):
    if not check:
        sec = secrets()
        if not sec:
            print(NO_SECRET)
            return 0
        rel = june_releases(sec)
        have = summaries()
        newest = rel[-1] if rel else None
        todo = [a for a in rel if refresh or a not in have or (a == newest and not hex_path(a).exists())]   # the newest release is read again when its H3 cells are missing
        log(f"broadband: June releases {rel}; {len(todo)} to download")
        for a in todo:
            summarise(sec, a, with_hex=a == newest)
    S = summaries()
    if not S:
        print("broadband: no release is summarized in cache/broadband/: nothing to build")
        return 1 if check else 0
    docs = list(assemble(S, *places()))
    paths = [OUT_SERIES, OUT_BARRIO]
    hp = hex_path(max(S))
    if hp.exists():
        docs.append(hex_layer(json.loads(hp.read_text(encoding="utf-8"))))
        paths.append(OUT_HEX)
    else:
        log(f"  no H3 cells for {max(S)} in cache/broadband/: {OUT_HEX.name} is left as it is")
    status = 0
    for path, d in zip(paths, docs):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python broadband.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: " + (f"{len(d['features'])} hexagons" if "features" in d else f"{len(d['vars'])} variables") + f", {path.stat().st_size / 1024:.1f} KB")
    return status


def diagnose():
    sec = secrets()
    if not sec:
        sys.exit(NO_SECRET)
    rel = june_releases(sec)
    print("June releases:", rel)
    for a in rel:
        fs = state_files(sec, a)
        print(f"  {a}: {len(fs)} files: " + ", ".join(f"{f['file_name']} ({f.get('record_count')})" for f in fs))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--diagnose" in sys.argv:
        diagnose()
    else:
        raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
