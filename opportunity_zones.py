"""Opportunity Zones 2.0 in Puerto Rico for the PR Data Observatory: the census tracts the US Treasury designated as Qualified Opportunity Zones for ten years
from January 1, 2027, the tracts that were eligible, and the zones of the first round (2018), which end on December 31, 2027.

    python opportunity_zones.py            # download the files missing from cache/oz/ and build the two files below
    python opportunity_zones.py --refresh  # read Treasury's Data Transparency page again, take its newest files and download everything again
    python opportunity_zones.py --check    # rebuild from the cache and exit 1 when a published file is not what it gives (no network, nothing written)

Writes site/data/opportunity_zones.json (every 2020 census tract of Puerto Rico with its status, the barrios and municipios with their residents in a zone,
Puerto Rico's totals and the first round's) and the map layer site/data/oz_tracts.geojson (the designated tracts only, rural or not; 2D map, 3D view and any
map that reads Core.facilities, layer oz). The Knowledge Area page opportunity-zones.html reads both (docs/opportunity-zones.md, HANDOFF decision 103).

What the program is. A Qualified Opportunity Zone is a low-income census tract in which an investment made through a Qualified Opportunity Fund earns federal
tax benefits on capital gains (26 U.S.C. 1400Z-1 and 1400Z-2). The One Big Beautiful Bill Act (P.L. 119-21, section 70421, July 4, 2025) made the incentive
permanent, with a new round of designations every ten years: a governor may nominate up to 25 percent of the state's eligible low-income communities (rounded
up), and the Treasury certifies them. It ended the 2018 rule that deemed every low-income tract of Puerto Rico a zone, narrowed the definition of a low-income
community (median family income at most 70 percent of the area's, or a poverty rate of 20 percent or more with a median family income at most 125 percent),
dropped contiguous tracts, and added larger benefits for zones made entirely of rural area. The Treasury designated the 2027 zones on November 5, 2026.

The sources (US Government works, public domain; no key):
  - Treasury, Office of Tax Policy, Data Transparency page for Qualified Opportunity Zones: "2027 QOZ Designations" (one row per designated tract, with its
    rural status) and "Eligible LICs for Nomination as 2027 QOZs" (every tract, with the poverty rate and median family income of the 2020-2024 American
    Community Survey that Treasury used, the comparison area's median family income, eligibility and rural status). The build reads the page and takes the
    files it names, so a corrected file is picked up by --refresh.
  - CDFI Fund, "Full list of designated QOZs" (2027): checked against Treasury's file; the build stops if Puerto Rico's tracts or their rural status differ.
  - CDFI Fund, designated QOZs of 2018 (updated 2018-12-14, with the two Puerto Rico tracts Notice 2019-42 added): the first round, 2010 tracts.
  - Census Bureau, TIGERweb, Census 2010 tracts (POP100): the residents of the first round's tracts, on the census of their own geography.
  - The observatory's crosswalk (site/data/geo/crosswalk.json, geo.py): 2020 tracts, barrios and municipios with their 2020 Census residents and housing
    units, and the residents of each barrio in each tract (blocks counted whole, so barrios add up exactly to tracts and municipios); and the tract outlines
    (site/data/geo/tracts.geojson, Census cartographic boundary file, for drawing only).

How each figure is made (docs/opportunity-zones.md):
  - A tract's status: designated (rural or not, as Treasury lists it), eligible but not designated, or not eligible.
  - Residents in a zone: the 2020 Census residents of the designated tracts, by tract, barrio (its blocks in designated tracts), municipio and Puerto Rico.
    A barrio can be split between tracts with different statuses, so its share in a zone can be anywhere from 0 to 100 percent.
  - Poverty rate and median family income: as Treasury published them for eligibility (ACS 2020-2024), never recomputed; income is given as a percent of
    the comparison area's median family income (the metropolitan or micropolitan area, or Puerto Rico outside one).
  - The first round: the 863 tracts of the 2018 list (2010 geography), and the share of 2010 Census residents in them; the two rounds' tracts are of
    different censuses, so the page compares counts and shares, never tract by tract.
Checks that stop the build: Puerto Rico's designated tracts must all be eligible, no more than the 25 percent limit, the same in Treasury's and the CDFI
Fund's lists, rural status the same in both, and every designated tract must have an outline and residents in the crosswalk.
The files describe the federal designation only; they recommend nothing about it (HANDOFF decision 103).
"""
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

import requests

import housing_series as hs
import xlsx_read

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "oz"
OUT = hs.OUT
OUT_JSON = OUT / "opportunity_zones.json"
OUT_LAYER = OUT / "oz_tracts.geojson"
log = hs.log

UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
TREASURY_PAGE = "https://home.treasury.gov/policy-issues/tax-policy/data-transparency/qualified-opportunity-zones"
TREASURY_FILES = {   # the newest file of each kind named on the page (its name carries its date)
    "designations": re.compile(r"""href=["']?([^"' >]*OZ2-Designations-[^"' >]*\.xlsx)"""),   # the page's HTML is minified: the href may be unquoted
    "eligible": re.compile(r"""href=["']?([^"' >]*OZ2-Eligible-Tracts-[^"' >]*\.xlsx)"""),
}
CDFI_2027 = "https://www.cdfifund.gov/media/8018881/download?inline"   # "Full list of designated QOZs" on https://www.cdfifund.gov/opportunity-zones (2026-11-05)
CDFI_2018 = "https://www.cdfifund.gov/system/files/documents/designated-qozs.12.14.18.xlsx"
TIGER_2010 = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2010/MapServer/14/query"
DESIGNATED_ON = "2026-11-05"   # Treasury's announcement of the 2027 designations (press release sb0682)
STARTS, ENDS = "2027-01-01", "2036-12-31"   # ten years from January 1, 2027 (Rev. Proc. 2026-14; Treasury, 2026-11-05)
OZ1_ENDS = "2027-12-31"   # the 2018 zones of Puerto Rico (deemed under prior 1400Z-1(b)(3)) end then (Rev. Proc. 2026-14, section 2.02(3)(d))


def fetch(url, params=None, timeout=300):
    for i in range(4):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == 3:
                raise SystemExit(f"opportunity zones: {url} failed ({e})")
            log(f"  retry {url} ({e})")


def cached(name, url, refresh):
    """The bytes of a cached download, fetched when missing or on --refresh."""
    p = CACHE / name
    if refresh or not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(fetch(url).content)
        log(f"  downloaded {name} ({p.stat().st_size / 1024:,.0f} KB)")
    return p.read_bytes()


def treasury_files(refresh):
    """{kind: (file name, URL)} of the newest designation and eligibility files named on Treasury's page (remembered in cache/oz/treasury.json)."""
    memo = CACHE / "treasury.json"
    if memo.exists() and not refresh:
        return {k: tuple(v) for k, v in json.loads(memo.read_text(encoding="utf-8")).items()}
    page = fetch(TREASURY_PAGE, timeout=60).text
    got = {}
    for kind, rx in TREASURY_FILES.items():
        def when(h):   # MMDDYYYY in the file name, as YYYYMMDD
            d = re.findall(r"(\d{8})", h)
            return d[-1][4:] + d[-1][:4] if d else ""
        links = sorted(set(rx.findall(page)), key=when)
        if not links:
            raise SystemExit(f"opportunity zones: no {kind} file on {TREASURY_PAGE}; the page changed")
        href = links[-1]   # the newest by the MMDDYYYY date in its name
        url = href if href.startswith("http") else "https://home.treasury.gov" + href
        got[kind] = (url.rsplit("/", 1)[-1], url)
    CACHE.mkdir(parents=True, exist_ok=True)
    memo.write_text(json.dumps(got, indent=1) + "\n", encoding="utf-8")
    return got


def sheet(data, must):
    """(header {column index: name}, data rows) of the first sheet, the header being the first row that holds the column `must`."""
    it = xlsx_read.rows(data)
    for r in it:
        if must in {(v or "").strip() for v in r.values()}:
            head = {i: (v or "").strip() for i, v in r.items()}
            return head, list(it)
    raise SystemExit(f"opportunity zones: no column {must!r} in a sheet")


def col(head, name):
    return next(i for i, h in head.items() if h == name)


def num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def designations(data):
    """{tract: rural?} of Puerto Rico in a 2027 designation list (Treasury's or the CDFI Fund's: the same columns)."""
    head, rows = sheet(data, "Census Tract Number")
    g, q, r = col(head, "Census Tract Number"), col(head, "QOZID"), col(head, "Rural QOZ")
    out = {}
    for row in rows:
        t = (row.get(g) or "").strip()
        if not t.startswith("72"):
            continue
        rural = (row.get(r) or "").strip() == "Rural"
        if rural != (row.get(q) or "").startswith("R"):
            raise SystemExit(f"opportunity zones: {t}: the QOZID {row.get(q)!r} and the rural status {row.get(r)!r} disagree")
        out[t] = rural
    return out


def eligibility(data):
    """{tract: {...}} of Puerto Rico from Treasury's eligibility file: poverty rate, median family income, the comparison area and its income, eligible, rural."""
    head, rows = sheet(data, "census_tract_number")
    c = {k: col(head, k) for k in ("census_tract_number", "cbsa", "poverty_rate", "mfi", "area_mfi", "mfi_ratio", "eligible_lic", "rural_status")}
    out = {}
    for row in rows:
        t = (row.get(c["census_tract_number"]) or "").strip()
        if not t.startswith("72"):
            continue
        out[t] = {"area": (row.get(c["cbsa"]) or "").strip() or "Puerto Rico", "pov": num(row.get(c["poverty_rate"])), "mfi": num(row.get(c["mfi"])),
                  "area_mfi": num(row.get(c["area_mfi"])), "ratio": num(row.get(c["mfi_ratio"])),
                  "eligible": num(row.get(c["eligible_lic"])) == 1, "rural": num(row.get(c["rural_status"])) == 1}
    return out


def first_round(data, refresh):
    """The 2018 zones of Puerto Rico (2010 tracts) and the 2010 Census residents of every 2010 tract."""
    head, rows = sheet(data, "Census Tract Number")
    s = next(i for i, h in head.items() if h.endswith("State"))   # its header is "Click arrow to filter state" and "State" on two lines
    g, k = col(head, "Census Tract Number"), col(head, "Tract Type")
    zones = {(r.get(g) or "").strip(): (r.get(k) or "").strip() for r in rows if (r.get(s) or "").strip() == "Puerto Rico"}
    p = CACHE / "tracts2010.json"
    if refresh or not p.exists():
        d = fetch(TIGER_2010, params={"where": "STATE='72'", "outFields": "GEOID,POP100", "returnGeometry": "false", "f": "json"}, timeout=120).json()
        pops = {f["attributes"]["GEOID"]: int(f["attributes"]["POP100"] or 0) for f in d.get("features", [])}
        if len(pops) < 900 or d.get("exceededTransferLimit"):
            raise SystemExit(f"opportunity zones: TIGERweb gave {len(pops)} tracts of 2010")
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(pops, sort_keys=True) + "\n", encoding="utf-8")
    pops = json.loads(p.read_text(encoding="utf-8"))
    missing = [t for t in zones if t not in pops]
    if missing:
        raise SystemExit(f"opportunity zones: {len(missing)} tracts of the 2018 list are not 2010 tracts of Puerto Rico ({missing[:3]})")
    return {"tracts": len(zones), "low_income": sum(1 for v in zones.values() if v == "Low-Income Community"),
            "contiguous": sum(1 for v in zones.values() if v.startswith("Non-LIC")), "tracts_2010": len(pops),
            "pop_2010": sum(pops.values()), "pop_in_zones_2010": sum(pops[t] for t in zones), "ends": OZ1_ENDS,
            "pop_share": round(sum(pops[t] for t in zones) / sum(pops.values()) * 100, 1)}


def r1(v):
    return None if v is None else round(v, 1)


def assemble(files, des, cdfi, elig, oz1):
    """The two published documents, from the parsed sources and the crosswalk."""
    cw = json.loads((OUT / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    F = {f: i for i, f in enumerate(cw["fields"])}
    names, mids = hs.municipalities()
    mname = dict(zip(mids, names))
    tr = {r[F["id"]]: r for r in cw["units"]["tract"]}
    br = {r[F["id"]]: r for r in cw["units"]["barrio"]}
    W = cw["weights"]["barrio_tract"]
    wf = {f: i for i, f in enumerate(W["fields"])}

    # ── checks ──
    n_elig = sum(1 for v in elig.values() if v["eligible"])
    cap = math.ceil(n_elig / 4) if n_elig >= 100 else 25
    if set(des) != set(cdfi):
        raise SystemExit(f"opportunity zones: Treasury lists {len(des)} tracts of Puerto Rico and the CDFI Fund {len(cdfi)}; {sorted(set(des) ^ set(cdfi))[:5]} differ")
    if any(des[t] != cdfi[t] for t in des):
        raise SystemExit("opportunity zones: the rural status of a tract differs between Treasury's and the CDFI Fund's lists")
    bad = [t for t in des if not (elig.get(t) or {}).get("eligible")]
    if bad:
        raise SystemExit(f"opportunity zones: {len(bad)} designated tracts are not eligible in Treasury's file ({bad[:3]})")
    if len(des) > cap:
        raise SystemExit(f"opportunity zones: {len(des)} designated tracts, more than the limit of {cap}")
    if any(des[t] != elig[t]["rural"] for t in des):
        raise SystemExit("opportunity zones: a designated tract's rural status differs from the eligibility file's")
    if set(elig) != set(tr):
        raise SystemExit(f"opportunity zones: Treasury's file has {len(elig)} tracts and the crosswalk {len(tr)}")

    # ── tracts ──
    status = {t: ("designated" if t in des else "eligible" if elig[t]["eligible"] else "not_eligible") for t in tr}
    areas = sorted({v["area"] for v in elig.values()}, key=lambda a: (a != "Puerto Rico", a))
    area_mfi = {}
    for v in elig.values():
        area_mfi.setdefault(v["area"], v["area_mfi"])
    pairs = {}
    for row in W["rows"]:
        pairs.setdefault(row[wf["tract"]], []).append((row[wf["pop"]], row[wf["barrio"]]))
    tract_rows = []
    for t in sorted(tr):
        e, x = elig[t], tr[t]
        bs = [b for p, b in sorted(pairs.get(t, []), key=lambda q: (-q[0], q[1])) if p > 0]
        tract_rows.append([t, x[F["parent"]], x[F["name_en"]].replace("Census tract ", ""), {"designated": 2 if des.get(t) else 1, "eligible": 0, "not_eligible": -1}[status[t]],
                           1 if e["rural"] else 0, r1(e["pov"]), None if e["mfi"] is None else round(e["mfi"]), r1(e["ratio"]), areas.index(e["area"]),
                           x[F["pop"]], x[F["hu"]], round(x[F["km2"]], 2), bs])
    if any(tr[t][F["pop"]] <= 0 for t in des):
        raise SystemExit("opportunity zones: a designated tract has no residents in the crosswalk")

    # ── barrios: residents in designated and in eligible tracts (blocks counted whole) ──
    in_des, in_elig = {}, {}
    for row in W["rows"]:
        b, t, p = row[wf["barrio"]], row[wf["tract"]], row[wf["pop"]]
        if status[t] == "designated":
            in_des[b] = in_des.get(b, 0) + p
        if status[t] in ("designated", "eligible"):
            in_elig[b] = in_elig.get(b, 0) + p
    barrio_rows = [[b, x[F["parent"]], x[F["name_es"]], x[F["pop"]], in_des.get(b, 0), in_elig.get(b, 0)] for b, x in sorted(br.items()) if x[F["pop"]] > 0]
    for b, m, n, p, d, e in barrio_rows:
        if not (0 <= d <= e <= p):
            raise SystemExit(f"opportunity zones: barrio {b} ({n}): residents in zones {d}, eligible {e}, of {p}")

    # ── municipios and Puerto Rico ──
    def summary(ts):
        d = [t for t in ts if status[t] == "designated"]
        return {"tracts": len(ts), "tracts_with_residents": sum(1 for t in ts if tr[t][F["pop"]] > 0),
                "eligible": sum(1 for t in ts if status[t] != "not_eligible"), "designated": len(d), "rural": sum(1 for t in d if des[t]),
                "pop": sum(tr[t][F["pop"]] for t in ts), "pop_designated": sum(tr[t][F["pop"]] for t in d),
                "pop_eligible": sum(tr[t][F["pop"]] for t in ts if status[t] != "not_eligible"),
                "hu_designated": sum(tr[t][F["hu"]] for t in d), "km2": round(sum(tr[t][F["km2"]] for t in ts), 1), "km2_designated": round(sum(tr[t][F["km2"]] for t in d), 1)}
    by_m = {}
    for t in tr:
        by_m.setdefault(tr[t][F["parent"]], []).append(t)
    if set(by_m) != set(mids):
        raise SystemExit("opportunity zones: the crosswalk's municipios are not the 78 of municipios.geojson")
    MF = ["id", "name", "tracts", "tracts_with_residents", "eligible", "designated", "rural", "pop", "pop_designated", "pop_eligible", "hu_designated", "km2", "km2_designated"]
    muni_rows = [[m, mname[m], *[summary(by_m[m])[k] for k in MF[2:]]] for m in mids]
    pr = summary(list(tr))
    pr.update({"limit": cap, "at_limit": len(des) == cap, "non_rural": len(des) - pr["rural"], "municipios_with_zone": sum(1 for r in muni_rows if r[MF.index("designated")]),
               "eligible_rural": sum(1 for t in tr if status[t] != "not_eligible" and elig[t]["rural"]),
               "pop_share": round(pr["pop_designated"] / pr["pop"] * 100, 1), "pop_eligible_share": round(pr["pop_eligible"] / pr["pop"] * 100, 1)})
    if sum(r[MF.index("pop_designated")] for r in muni_rows) != pr["pop_designated"] or sum(r[4] for r in barrio_rows) != pr["pop_designated"]:
        raise SystemExit("opportunity zones: the municipios or the barrios do not add up to Puerto Rico's residents in zones")

    def med(vals):
        v = sorted(x for x in vals if x is not None)
        return None if not v else r1(v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)
    groups = {}
    for k, test in (("designated_rural", lambda t: status[t] == "designated" and des[t]), ("designated_non_rural", lambda t: status[t] == "designated" and not des[t]),
                    ("eligible", lambda t: status[t] == "eligible"), ("not_eligible", lambda t: status[t] == "not_eligible" and tr[t][F["pop"]] > 0)):
        ts = [t for t in tr if test(t)]
        groups[k] = {"tracts": len(ts), "pop": sum(tr[t][F["pop"]] for t in ts), "median_pov": med(elig[t]["pov"] for t in ts), "median_ratio": med(elig[t]["ratio"] for t in ts)}

    vintage = {"designations": files["designations"][0], "eligible": files["eligible"][0], "designated_on": DESIGNATED_ON, "starts": STARTS, "ends": ENDS,
               "acs": "2020-2024", "census": 2020}
    doc = {"vintage": vintage,
           "notes": {"source": "opportunity_zones.py: US Treasury, Office of Tax Policy, Data Transparency for Qualified Opportunity Zones (2027 designations and eligible tracts, "
                               "checked against the CDFI Fund's list); CDFI Fund, 2018 designations; 2020 Census residents from the observatory's crosswalk (docs/opportunity-zones.md)",
                     "status_codes": {"2": "designated, rural", "1": "designated, not rural", "0": "eligible, not designated", "-1": "not eligible"},
                     "files": {k: v[1] for k, v in files.items()}},
           "sources": {
               "treasury_oz": {"name": "US Treasury: Qualified Opportunity Zones, 2027 designations and eligible tracts (Office of Tax Policy, Data Transparency); designated lists of 2027 and 2018 (CDFI Fund)",
                               "url": TREASURY_PAGE, "license": "US Government work (no US copyright)",
                               "note": "Designation, rural status, poverty rate and median family income (ACS 2020-2024) of every tract, as Treasury published them; the CDFI Fund's 2027 list is checked against Treasury's."},
               "census_tiger": {"name": "US Census Bureau: 2020 Census tracts, barrios and residents (the observatory's crosswalk); 2010 Census tract residents (TIGERweb)",
                                "url": "https://tigerweb.geo.census.gov/", "license": "US Government work; cite the Census Bureau as the source",
                                "note": "Residents and housing units of the 2020 tracts and of each barrio in each tract (blocks counted whole); the 2010 residents of the first round's tracts."},
               "census_cartographic": {"name": "US Census Bureau: cartographic boundary file, 2020 census tracts (1:500,000)",
                                       "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html",
                                       "license": "No license stated on the product pages; US Government work", "note": "The outlines of the map layer, for drawing only."},
           },
           "areas": [{"name": a, "mfi": None if area_mfi[a] is None else round(area_mfi[a])} for a in areas],
           "tract_fields": ["id", "mun", "tract", "status", "rural", "pov", "mfi", "mfi_pct", "area", "pop", "hu", "km2", "barrios"],
           "tracts": tract_rows,
           "barrio_fields": ["id", "mun", "name", "pop", "pop_designated", "pop_eligible"],
           "barrios": barrio_rows,
           "muni_fields": MF,
           "municipios": muni_rows,
           "pr": pr, "groups": groups, "first_round": oz1}

    # ── the map layer: the designated tracts only ──
    outl = {f["properties"]["GEOID"]: f["geometry"] for f in json.loads((OUT / "geo" / "tracts.geojson").read_text(encoding="utf-8"))["features"]}
    nobar = [t for t in des if t not in outl]
    if nobar:
        raise SystemExit(f"opportunity zones: no outline for designated tracts {nobar[:3]}")
    bname = {b: br[b][F["name_es"]] for b in br}

    def ring(r):
        out = []
        for x, y in r:
            q = [round(x, 4), round(y, 4)]
            if not out or q != out[-1]:
                out.append(q)
        if out[0] != out[-1]:
            out.append(out[0])
        return out

    def geom(g):
        if g["type"] == "Polygon":
            return {"type": "Polygon", "coordinates": [ring(r) for r in g["coordinates"]]}
        return {"type": "MultiPolygon", "coordinates": [[ring(r) for r in p] for p in g["coordinates"]]}
    feats = []
    for row in tract_rows:
        t, m, num_, st, rur, pov, mfi, ratio, ai, pop, hu, km2, bs = row
        if st < 1:
            continue
        feats.append({"type": "Feature", "geometry": geom(outl[t]),
                      "properties": {"g": t, "c": st, "m": mname[m], "t": num_, "p": pop, "pv": pov, "mr": ratio, "b": ", ".join(bname[b] for b in bs[:3]), "nb": len(bs)}})
    layer = {"type": "FeatureCollection",
             "notes": {"designated": len(feats), "rural": pr["rural"], "non_rural": pr["non_rural"], "eligible": pr["eligible"], "limit": cap,
                       "designated_on": DESIGNATED_ON, "starts": STARTS, "ends": ENDS, "acs": "2020-2024",
                       "source": "opportunity_zones.py: US Treasury, 2027 Qualified Opportunity Zone designations (Data Transparency, " + files["designations"][0]
                                 + "); outlines of the 2020 census tracts (Census cartographic boundary file); residents: 2020 Census"},
             "features": feats}
    return doc, layer


def build(refresh=False, check=False):
    if check and not (CACHE / "treasury.json").exists():
        print("opportunity zones: nothing cached in cache/oz/: run python opportunity_zones.py first")
        return 1
    files = treasury_files(refresh and not check)
    des = designations(cached(files["designations"][0], files["designations"][1], refresh and not check))
    elig = eligibility(cached(files["eligible"][0], files["eligible"][1], refresh and not check))
    cdfi = designations(cached("cdfi_designated_2027.xlsx", CDFI_2027, refresh and not check))
    oz1 = first_round(cached("cdfi_designated_2018.xlsx", CDFI_2018, refresh and not check), refresh and not check)
    doc, layer = assemble(files, des, cdfi, elig, oz1)
    p = doc["pr"]
    log(f"opportunity zones: {p['designated']} designated ({p['rural']} rural, {p['non_rural']} not) of {p['eligible']} eligible (limit {p['limit']}); "
        f"{p['pop_designated']:,} residents ({p['pop_share']}%), in {p['municipios_with_zone']} municipios; first round {oz1['tracts']} tracts, {oz1['pop_share']}% of 2010 residents")
    status = 0
    for path, d in ((OUT_JSON, doc), (OUT_LAYER, layer)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python opportunity_zones.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
