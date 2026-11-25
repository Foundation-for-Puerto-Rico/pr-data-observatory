"""Nonprofit organizations for the PR Data Observatory: tax-exempt organizations registered with the IRS, counted for the 78 municipalities and Puerto Rico,
in all, the 501(c)(3) charities among them, and by NTEE major group. Counts only: no organization's name, EIN or address is published.

    python nonprofits.py             # build site/data/nonprofit_series.json (downloads only what is missing from cache/nonprofits/)
    python nonprofits.py --refresh   # download again
    python nonprofits.py --check     # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Sources, no key:
  IRS, Exempt Organizations Business Master File Extract (EO BMF), the Puerto Rico file (https://www.irs.gov/pub/irs-soi/eo_pr.csv), renewed by the IRS about
      monthly (its Last-Modified date is the vintage). US federal government work, public domain (17 U.S.C. 105); the IRS page states no license.
  US Census Bureau, 2020 ZCTA to county relationship file: the municipio of a ZIP code whose city is not a municipio's name (public domain).

What is kept. Only CITY, the first five digits of ZIP, SUBSECTION and NTEE_CD reach the cache (cache/nonprofits/): names, EINs, street addresses and financial
fields are dropped as the file is read.

Where an organization is counted. The IRS file holds the address of each organization's headquarters, not where it works. The municipio is the CITY when it is
a municipio's name; otherwise a known postal place (Saint Just is in Trujillo Alto); otherwise the municipio that holds most of the land of its ZIP code (the
Census ZCTA file); otherwise only Puerto Rico's total counts it.

NTEE major groups (the ten groups the National Center for Charitable Statistics uses, from the first letter of NTEE_CD):
  A arts; B education; C D environment and animals; E F G H health; I-P human services; Q international; R-W public and societal benefit; X religion;
  Y mutual and membership benefit; Z or no code: unclassified.
"""

import csv
import io
import json
import sys
import unicodedata
from collections import Counter
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "nonprofits"
OUT = hs.OUT / "nonprofit_series.json"
BMF = "https://www.irs.gov/pub/irs-soi/eo_pr.csv"
ZCTA = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"
UA = {"User-Agent": "Mozilla/5.0 (pr-digital-twin open-data build; Foundation for Puerto Rico)"}   # irs.gov refuses some plain script agents
KEEP = ["CITY", "ZIP", "SUBSECTION", "NTEE_CD"]
FLOOR = 2000   # the Puerto Rico file held 2,572 organizations on 2026-10-13
log = hs.log

GROUPS = [   # (key, label, NTEE first letters)
    ("npo_arts", "Arts, culture and humanities", "A"),
    ("npo_education", "Education", "B"),
    ("npo_environment", "Environment and animals", "CD"),
    ("npo_health", "Health", "EFGH"),
    ("npo_human", "Human services", "IJKLMNOP"),
    ("npo_international", "International and foreign affairs", "Q"),
    ("npo_public", "Public and societal benefit", "RSTUVW"),
    ("npo_religion", "Religion-related", "X"),
    ("npo_mutual", "Mutual and membership benefit", "Y"),
    ("npo_unclassified", "Unclassified or no NTEE code", "Z"),
]
POSTAL = {"saint just": "Trujillo Alto", "palmer": "Río Grande", "santurce": "San Juan", "old san juan": "San Juan", "viejo san juan": "San Juan",
          "rio piedras": "San Juan", "hato rey": "San Juan", "rio blanco": "Naguabo", "fort buchanan": "Guaynabo", "levittown": "Toa Baja"}   # PO-box ZIP codes that are no ZCTA

SOURCES = {
    "irs_eo_bmf": {"name": "IRS — Exempt Organizations Business Master File Extract (EO BMF), Puerto Rico", "url": "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf",
                   "license": "US federal government work (public domain, 17 U.S.C. 105); the IRS page states no license",
                   "note": "Every organization the IRS recognizes as tax-exempt with a Puerto Rico address. The observatory publishes counts for each municipio, never a name, EIN or address."},
    "census_zcta_county": {"name": "US Census Bureau — 2020 ZCTA to county relationship file", "url": "https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html", "license": "US federal government data (public domain)",
                           "note": "Places an organization in the municipio holding most of the land of its ZIP code when its city is not a municipio's name."},
}


def get(url):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=(30, 300))
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == 3:
                raise SystemExit(f"nonprofits: {url} failed: {e}")


def bmf(refresh=False, offline=False):
    path = CACHE / "eo_pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"nonprofits --check: {path.name} is not in the cache (python nonprofits.py makes it)")
    r = get(BMF)
    rd = csv.DictReader(io.StringIO(r.content.decode("latin-1")))
    missing = [c for c in KEEP + ["STATE"] if c not in (rd.fieldnames or [])]
    if missing:
        raise SystemExit(f"nonprofits: the IRS file has no column {missing}: read its layout before going on")
    rows = []
    for x in rd:
        if x["STATE"] != "PR":
            raise SystemExit(f"nonprofits: the Puerto Rico file holds a row of {x['STATE']!r}")
        rows.append({"CITY": x["CITY"], "ZIP": (x["ZIP"] or "")[:5], "SUBSECTION": x["SUBSECTION"], "NTEE_CD": x["NTEE_CD"]})   # name, EIN, street and money dropped here
    if len(rows) < FLOOR:
        raise SystemExit(f"nonprofits: {len(rows)} organizations (fewer than {FLOOR}): the file changed; read it before going on")
    lm = r.headers.get("Last-Modified")
    d = {"vintage": parsedate_to_datetime(lm).date().isoformat() if lm else None, "rows": rows}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, separators=(",", ":")), encoding="utf-8")
    log(f"  IRS EO BMF Puerto Rico: {len(rows)} organizations, file of {d['vintage']}")
    return d


def zcta(refresh=False, offline=False):
    """{ZCTA: GEOID of the municipio that holds most of its land}, for Puerto Rico."""
    path = CACHE / "zcta_county_pr.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(f"nonprofits --check: {path.name} is not in the cache")
    best = {}
    for x in csv.DictReader(io.StringIO(get(ZCTA).content.decode("utf-8-sig")), delimiter="|"):
        c, z = x["GEOID_COUNTY_20"] or "", x["GEOID_ZCTA5_20"] or ""
        if c.startswith("72") and z:
            a = int(x["AREALAND_PART"] or 0)
            if z not in best or a > best[z][1]:
                best[z] = (c, a)
    out = {z: v[0] for z, v in sorted(best.items())}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def norm(s):
    return " ".join(unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace(",", " ").split())


def group_of(ntee):
    c = (ntee or "").strip()[:1].upper()
    for key, _, letters in GROUPS:
        if c and c in letters:
            return key
    return "npo_unclassified"


def place(row, by_name, zc):
    """(GEOID or None, how) for one organization."""
    k = norm(row["CITY"])
    if k in by_name:
        return by_name[k], "city"
    if k in POSTAL:
        return by_name[norm(POSTAL[k])], "postal place"
    if row["ZIP"] in zc:
        return zc[row["ZIP"]], "zip"
    return None, "not placed"


def compute(refresh=False, offline=False):
    names, ids = hs.municipalities()
    by_name = {norm(n): f for n, f in zip(names, ids)}
    b, zc = bmf(refresh, offline), zcta(refresh, offline)
    counts = {k: Counter() for k in ["npo_all", "npo_501c3"] + [g[0] for g in GROUPS]}
    island = Counter()
    how = Counter()
    for r in b["rows"]:
        f, h = place(r, by_name, zc)
        how[h] += 1
        keys = ["npo_all", group_of(r["NTEE_CD"])] + (["npo_501c3"] if r["SUBSECTION"] == "03" else [])
        for k in keys:
            island[k] += 1
            if f:
                counts[k][f] += 1
    year = int(b["vintage"][:4])
    col = lambda k: [counts[k].get(f, 0) for f in ids] + [island[k]]   # Puerto Rico's value also counts the few organizations no municipio could be given
    ref = f"IRS EO BMF, Puerto Rico file of {b['vintage']}"
    G = "Economy · Nonprofit organizations"

    def v(key, label, definition):
        return {"key": key, "group": G, "label": label, "unit": "", "d": 0, "type": "count", "sources": ["irs_eo_bmf"], "ref": ref, "definition": definition, "family": "nonprofits",
                "counted": False, "classes": "jenks", "noPerHU": True, "years": {str(year): col(key)}}
    vs = [v("npo_all", "Tax-exempt organizations (IRS)", "Organizations the IRS recognizes as exempt from federal income tax whose headquarters address is in the municipio: charities, social welfare groups, unions, business leagues, clubs and the like. Many Puerto Rico nonprofits are registered only under Puerto Rico law and are not in this list."),
          v("npo_501c3", "501(c)(3) charities (IRS)", "Of those, the organizations exempt under section 501(c)(3): charities, schools, churches that applied, and other public-benefit groups to which gifts are deductible.")]
    vs += [v(k, f"Nonprofits: {lab[0].lower() + lab[1:]} (IRS)",
             f"Tax-exempt organizations whose NTEE code (the activity code the IRS gives) starts with {', '.join(letters) if k != 'npo_unclassified' else 'Z, or that have no code'}: {lab[0].lower() + lab[1:]}.")
           for k, lab, letters in GROUPS]
    notes = {"organizations": len(b["rows"]), "placed_by": dict(how), "vintage": b["vintage"],
             "note": "An organization is counted where its headquarters address is, which may not be where it works. Puerto Rico's value counts every organization in the file, including those no municipio could be given."}
    return {"as_of": b["vintage"][:7], "years": [year], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    d = compute(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        same = old is not None and {**old, "built": None} == {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}
        print(f"{OUT.name} {'matches the cache' if same else 'is not what the cache gives: run python nonprofits.py'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"wrote {OUT.name}: {len(d['vars'])} variables, {OUT.stat().st_size / 1024:.1f} KB; placed by {d['notes']['placed_by']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
