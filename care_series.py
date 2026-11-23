"""Hospitals, care facilities and distance to care for the PR Data Observatory (Phase 3, item 9, data wave C), for the 78 municipalities and Puerto Rico.

    python care_series.py             # build site/data/care_series.json (downloads only what is missing from the cache)
    python care_series.py --refresh   # download the CMS lists and HRSA's site points again
    python care_series.py --check     # rebuild from the cache and exit 1 when site/data/care_series.json is not what it gives (no network, nothing written)

Two parts, one snapshot (the shape of health_series.json, which holds HRSA's health centers and shortage areas):
  CMS facility lists (Provider Data Catalog, US federal data, public domain): counts of Medicare-certified hospitals, hospitals with an emergency department, dialysis facilities,
      nursing homes, home health agencies and hospice providers in each municipality. Only the municipality (county or town), the ZIP code and, for hospitals, the type and the
      emergency flag reach the cache (cache/cms/); names, addresses, telephone numbers and certification numbers are never kept.
  Distance to the nearest health center site, along the roads, from where residents live (care_access.py): the average road distance, an estimated drive time and the share of
      residents within 10 km. The site points stay in the local cache only (owner decision, 2026-10-14) and are never published.
docs/health.md ("Item 9") has the method and the checks.
"""

import json
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import requests

import care_access
import health_series as hsr
import housing_series as hs

ROOT = Path(__file__).resolve().parent
OUT = hs.OUT / "care_series.json"
CMS_API = "https://data.cms.gov/provider-data/api/1/datastore/query/{id}/0"
CMS_CACHE = ROOT / "cache" / "cms"
CMS = {   # key: (dataset id, the column that names the municipality, the columns kept)
    "hospitals": ("xubh-q36u", "countyparish", ["countyparish", "zip_code", "hospital_type", "emergency_services"]),
    "dialysis": ("23ew-n7w9", "countyparish", ["countyparish", "zip_code"]),
    "nursing_homes": ("4pq5-n9py", "countyparish", ["countyparish", "zip_code"]),
    "home_health": ("6jpm-sxkc", "citytown", ["citytown", "zip_code"]),
    "hospice": ("yc9t-dgbk", "countyparish", ["countyparish", "zip_code"]),
}
CMS_FLOORS = {"hospitals": 40, "dialysis": 30, "nursing_homes": 5, "home_health": 25, "hospice": 25}   # the 2026-10 lists have 59, 50, 9, 39 and 42 in Puerto Rico
CMS_ZIP = {"00917": "San Juan", "00780": "Ponce", "00674": "Manatí", "00962": "Cataño"}   # the home health list names a few places by a barrio or sector (Hato Rey, Coto Laurel, Altos de Luchetti, Palmas): their ZIP code says the municipality
log = hs.log

SOURCES = {
    "cms_provider_data": {"name": "CMS — Provider Data Catalog (hospitals, dialysis facilities, nursing homes, home health agencies, hospice)", "url": "https://data.cms.gov/provider-data/",
                          "license": "US federal government data (public domain)",
                          "note": "Medicare-certified facilities. The observatory publishes counts for each municipality, never names, addresses or certification numbers."},
    "hrsa_sites": hsr.SOURCES["hrsa_sites"],
    "osm": {"name": "OpenStreetMap contributors (roads)", "url": "https://www.openstreetmap.org/copyright", "license": "Open Database License (ODbL) 1.0",
            "note": "The road graph the distance to a health center is measured on."},
    "census_tiger": {"name": "US Census Bureau — 2020 census blocks (residents and internal points)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Where residents live: each block's 2020 residents weigh the average distance."},
}


def cms_rows(key, refresh=False, offline=False):
    """The kept columns of the Puerto Rico rows of one CMS list, from the cache or the Provider Data API. Names, addresses, telephone numbers and certification numbers are never kept."""
    ds, _, keep = CMS[key]
    path = CMS_CACHE / f"{key}.pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"care_series --check: {path.name} is not in the cache (python care_series.py makes it; --check never downloads)")
    CMS_CACHE.mkdir(parents=True, exist_ok=True)
    (CMS_CACHE / "as_of.json").write_text(json.dumps({"date": date.today().isoformat()}), encoding="utf-8")   # the day the lists were read: the snapshot's date and year
    rows, off = [], 0
    while True:
        r = requests.get(CMS_API.format(id=ds), params={"conditions[0][property]": "state", "conditions[0][value]": "PR", "limit": 500, "offset": off}, headers=hsr.UA, timeout=(30, 120))
        r.raise_for_status()
        page = r.json().get("results") or []
        missing = [c for c in keep if page and c not in page[0]]
        if missing:
            raise SystemExit(f"care_series: the CMS list {ds} has no column {missing}: read its data dictionary before going on")
        rows += [{c: x.get(c) for c in keep} for x in page]
        if len(page) < 500:
            break
        off += 500
    CMS_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  CMS {key}: {len(rows)} rows")
    return rows


def norm(s):
    return unicodedata.normalize("NFD", (s or "")).encode("ascii", "ignore").decode().lower().replace(" municipio", "").strip()


def cms_counts(key, rows, names, ids):
    """{fips: count} of one CMS list (and, for hospitals, of those with emergency services), each row in the municipality its county (or, for home health, its town) names.
    A name that is not a municipality and has no ZIP rule stops the build."""
    by_name = {norm(n): f for n, f in zip(names, ids)}
    col = CMS[key][1]
    out, emerg = Counter(), Counter()
    for r in rows:
        f = by_name.get(norm(r[col])) or by_name.get(norm(CMS_ZIP.get((r.get("zip_code") or "")[:5], "")))
        if not f:
            raise SystemExit(f"care_series: the CMS {key} list names {r[col]!r} (ZIP {r.get('zip_code')}), which is not a municipality: add its ZIP code to CMS_ZIP after checking it")
        out[f] += 1
        if key == "hospitals" and r.get("emergency_services") == "Yes":
            emerg[f] += 1
    return out, emerg


CMS_TEXT = {
    "hospitals": ("cms_hospitals", "Hospitals (Medicare-certified)", "Hospitals in CMS's Hospital General Information list for the municipality of the hospital: acute care, psychiatric, children's and the VA hospital that Medicare certifies or rates. Hospitals that do not take part in Medicare are not listed."),
    "dialysis": ("cms_dialysis", "Dialysis facilities", "Dialysis facilities certified by Medicare (CMS's Dialysis Facility list), in the municipality CMS gives for the facility."),
    "nursing_homes": ("cms_nursing_homes", "Nursing homes (Medicare or Medicaid certified)", "Nursing homes certified by Medicare or Medicaid (CMS's Nursing Home list), in the municipality CMS gives. Long-term care homes that are not certified are not listed."),
    "home_health": ("cms_home_health", "Home health agencies", "Home health agencies certified by Medicare (CMS's Home Health Care Agencies list), in the municipality of the agency's office; an agency serves people in other municipalities too."),
    "hospice": ("cms_hospice", "Hospice providers", "Hospice providers certified by Medicare (CMS's Hospice list), in the municipality of the provider's office; hospice care is mostly given at home, in any municipality the provider serves."),
}


def compute(refresh=False, offline=False, floors=True, order_file=hs.OUT / "economy_series.json"):
    names, fips = hs.municipalities()
    ids = list(fips)
    if order_file and order_file.exists():
        g = json.loads(order_file.read_text(encoding="utf-8"))["geo"]
        if g["ids"][:len(ids)] != ids or g["names"][:len(ids)] != names:
            raise SystemExit("care_series: the municipalities are not in the order of economy_series.json")
    log("Hospitals and care facilities (CMS) and distance to a health center")
    stamp = CMS_CACHE / "as_of.json"
    as_of = json.loads(stamp.read_text(encoding="utf-8"))["date"] if stamp.exists() else date.today().isoformat()
    year = int(as_of[:4])   # the year the lists were read, not the year of the build: a rebuild from the cache keeps it
    column = lambda c: [c.get(f, 0) for f in ids] + [sum(c.get(f, 0) for f in ids)]
    vs, cms_n = [], {}
    G2, REF_CMS = "Hospitals and care facilities", "CMS Provider Data Catalog"
    for key in CMS:
        rows = cms_rows(key, refresh, offline)
        if floors and len(rows) < CMS_FLOORS[key]:
            raise SystemExit(f"care_series: the CMS {key} list has {len(rows)} Puerto Rico rows (the 2026-10 list has more than {CMS_FLOORS[key]}): read it before publishing")
        cms_n[key] = cms_counts(key, rows, names, ids)
        vk, label, definition = CMS_TEXT[key]
        vs.append(hsr.var(vk, G2, label, "", 0, "count", ["cms_provider_data"], REF_CMS, definition + " A municipality with none shows 0: CMS lists none there. Names and addresses are not kept.",
                          {str(year): column(cms_n[key][0])}, dPer=3, noPerHU=True, classes="jenks"))
        if key == "hospitals":
            vs.append(hsr.var("cms_hospitals_er", G2, "Hospitals with an emergency department", "", 0, "count", ["cms_provider_data"], REF_CMS,
                              "Hospitals of CMS's Hospital General Information list that say they provide emergency services, in the municipality of the hospital. A municipality with none shows 0. Names and addresses are not kept.",
                              {str(year): column(cms_n[key][1])}, dPer=3, noPerHU=True, classes="jenks"))
    acc, acc_notes = care_access.compute(refresh, offline)
    G3 = "Distance to a health center"
    REF_ACC = "Computed by the observatory from HRSA's sites, the 2020 census blocks and OpenStreetMap roads (care_access.py)"
    pick = lambda i: [acc[f][i] if f in acc else None for f in ids] + [acc["72"][i] if "72" in acc else None]
    ACC = ("Measured from where people live: each 2020 census block with residents, from its internal point to the nearest permanent health center site (HRSA's list), along the roads in either direction, "
           "and averaged over the municipality's residents. It is a distance to the nearest health center, not to a hospital, an emergency department or a doctor's office, and it says nothing about hours, services or whether the center takes a person's insurance. ")
    vs.append(hsr.var("hc_road_km", G3, "Road distance to the nearest health center (average per resident, km)", "km", 1, "ratio", ["hrsa_sites", "census_tiger", "osm"], REF_ACC,
                      ACC + "An estimate made by the observatory, not a figure HRSA publishes.", {str(year): pick(0)}, tag="estimate"))
    vs.append(hsr.var("hc_drive_min", G3, "Drive time to the nearest health center (estimate, minutes)", "min", 1, "ratio", ["hrsa_sites", "census_tiger", "osm"], REF_ACC,
                      ACC + "Drive time uses the observatory's planning speeds for each class of road (free flow: no traffic, no stops, no waiting): a rough estimate that is shorter than most real trips. The road distance is the firmer figure.",
                      {str(year): pick(1)}, tag="estimate"))
    vs.append(hsr.var("hc_within_10km_pct", G3, "Residents within 10 km of a health center by road (%)", "%", 1, "rate", ["hrsa_sites", "census_tiger", "osm"], REF_ACC,
                      ACC + "The share of the municipality's residents whose road distance to the nearest health center site is 10 km or less. An estimate made by the observatory.", {str(year): pick(2)}, tag="estimate"))
    notes = {"cms": {k: {"rows": sum(v[0].values()), "municipios": len(v[0]), **({"with_emergency": sum(v[1].values())} if k == "hospitals" else {})} for k, v in cms_n.items()},
             "access": acc_notes}
    return {"as_of": as_of, "years": [year], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    out = compute(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda d: {**d, "built": None, "as_of": None}
        if old is None or strip(old) != strip(json.loads(json.dumps(out, ensure_ascii=False))):
            print("care_series.json is not what the cache gives: run python care_series.py")
            return 1
        print("care_series.json matches the cache")
        return 0
    text = json.dumps({"built": date.today().isoformat(), **out}, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(out['vars'])} variables, {OUT.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
