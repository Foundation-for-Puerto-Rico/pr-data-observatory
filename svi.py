"""CDC/ATSDR Social Vulnerability Index for Puerto Rico: the 78 municipios and the census tracts. HANDOFF decision 107, step 2; docs/svi.md.

    python svi.py              # build site/data/svi_series.json and site/data/svi_tract.json from the cache
    python svi.py --refresh    # download CDC's two files again
    python svi.py --check      # rebuild from the cache and exit 1 when a published file is not what the cache gives (no network, nothing written)

Source, no key: CDC/ATSDR Social Vulnerability Index 2022 (the newest edition; American Community Survey 2018-2022), the Puerto Rico files for counties
(municipios) and for census tracts. The index is a percentile rank from 0 (least vulnerable) to 1 (most vulnerable). CDC ranks Puerto Rico apart from the
states: a municipio is ranked among the 78 municipios and a tract among Puerto Rico's tracts, so a value is never comparable with a state's.

Published: the overall rank and three of the four themes (socioeconomic status; household characteristics; housing type and transportation). The third
theme, racial and ethnic minority status, is not published as a dataset: by the national definition 95% or more of the residents are a minority in
nearly every tract (the share is in the notes), so the theme cannot tell places apart (its rank never passes 0.53 among tracts). It is still inside CDC's overall rank, as CDC computes it.
CDC's code for "no value" (-999: a tract with no residents or too little data) is null, never zero.

Output: svi_series.json (municipios, in the shape of health_series.json: one snapshot, no value for Puerto Rico as a whole) and svi_tract.json (the tracts of
the crosswalk, in the shape of the level files of small_area.py; a file for download and for later steps: no map draws tracts yet).
"""

import csv
import datetime
import io
import json
import sys
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "svi"
OUT = hs.OUT / "svi_series.json"
OUT_T = hs.OUT / "svi_tract.json"
log = hs.log
EDITION = 2022
ACS = "2018-2022"
BASE = f"https://svi.cdc.gov/Documents/Data/{EDITION}/csv/"
FILES = {"municipio": ("PuertoRico_county.csv", BASE + "states_counties/PuertoRico_county.csv"), "tract": ("PuertoRico.csv", BASE + "states/PuertoRico.csv")}
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
NO_VALUE = -999
GROUP = "Vulnerability (CDC/ATSDR SVI)"
REF = f"CDC/ATSDR Social Vulnerability Index {EDITION}, Puerto Rico (American Community Survey {ACS})"
# key: (CDC's column, label, what the theme is made of)
VARS = {
    "svi_overall": ("RPL_THEMES", "Social vulnerability, overall (CDC/ATSDR SVI rank, 0 to 1)",
                    "CDC's overall rank, from the four themes together: socioeconomic status, household characteristics, racial and ethnic minority status, and housing type and transportation (16 survey measures)."),
    "svi_socioeconomic": ("RPL_THEME1", "Social vulnerability: socioeconomic status (SVI theme 1, 0 to 1)",
                          "The rank for theme 1: people below 150% of the poverty level, unemployed, with housing costs of 30% or more of income, without a high school diploma, and without health insurance."),
    "svi_household": ("RPL_THEME2", "Social vulnerability: household characteristics (SVI theme 2, 0 to 1)",
                      "The rank for theme 2: people 65 and older, 17 and younger, with a disability, single-parent households, and people who speak English less than well."),
    "svi_housing_transport": ("RPL_THEME4", "Social vulnerability: housing type and transportation (SVI theme 4, 0 to 1)",
                              "The rank for theme 4: homes in buildings of 10 or more units, mobile homes, crowded homes, households with no vehicle, and people in group quarters."),
}
MINORITY = "RPL_THEME3"   # not published (see the docstring); its largest tract rank is recorded in the notes


def fetch(name, url, refresh):
    p = CACHE / name
    if refresh or not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, headers=UA, timeout=120)
        r.raise_for_status()
        p.write_bytes(r.content)
        log(f"  downloaded {name} ({len(r.content) / 1024:,.0f} KB)")
    return p.read_bytes()


def rows(data):
    """{FIPS: row} of one of CDC's files; stops when a column the build reads is missing."""
    out = {r["FIPS"]: r for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig")))}
    need = {c for c, _, _ in VARS.values()} | {MINORITY, "E_TOTPOP", "EP_MINRTY"}
    have = set(next(iter(out.values())))
    if need - have:
        raise SystemExit(f"svi: CDC's file has no column {sorted(need - have)}")
    return out


def rank(row, col):
    """A rank between 0 and 1, or None where CDC gives its no-value code or the area is not in the file."""
    if row is None:
        return None
    v = float(row[col])
    if v == NO_VALUE:
        return None
    if not 0 <= v <= 1:
        raise SystemExit(f"svi: {row['FIPS']} {col} is {v}, not a rank between 0 and 1")
    return round(v, 4)


def documents(muni_rows, tract_rows):
    names, fips = hs.municipalities()
    ids = list(fips)
    if set(ids) != set(muni_rows):
        raise SystemExit("svi: CDC's county file does not hold the 78 municipios")
    cw = json.loads((hs.OUT / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    tracts = [r[0] for r in cw["units"]["tract"]]
    if set(tract_rows) - set(tracts):
        raise SystemExit(f"svi: CDC's tract file names tracts the crosswalk does not have: {sorted(set(tract_rows) - set(tracts))[:5]}")
    y = str(EDITION)
    sources = {"cdc_svi": {"name": "CDC/ATSDR Social Vulnerability Index " + str(EDITION), "url": "https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html",
                           "license": "US federal government data; CDC asks for its suggested citation",
                           "note": f"Percentile ranks from the American Community Survey {ACS}; Puerto Rico is ranked apart from the states."}}
    vs = []
    for key, (col, label, made) in VARS.items():
        vs.append({"key": key, "group": GROUP, "label": label, "unit": "", "d": 2, "type": "ratio", "sources": ["cdc_svi"], "ref": REF, "family": "svi",
                   "definition": made + " A rank of 0 is the least vulnerable municipio and 1 the most vulnerable, among the 78 municipios of Puerto Rico only: it cannot be compared with a state's.",
                   "counted": False, "noIsland": True, "tag": "rank", "noPerHU": True,
                   "years": {y: [rank(muni_rows[g], col) for g in ids] + [None]}})
    with_value = sum(1 for t in tracts if rank(tract_rows.get(t), "RPL_THEMES") is not None)
    minority = [rank(r, MINORITY) for r in tract_rows.values()]
    share = [float(r["EP_MINRTY"]) for r in tract_rows.values() if float(r["EP_MINRTY"]) != NO_VALUE]
    high = sum(1 for x in share if x >= 95)
    notes = {"edition": EDITION, "survey": f"American Community Survey {ACS}",
             "ranked_within": "Puerto Rico only: municipios among the 78 municipios, tracts among Puerto Rico's tracts",
             "no_value": f"CDC's code {NO_VALUE} is null: a tract with no residents or too little data",
             "theme_3": f"Racial and ethnic minority status is not published as a dataset: its largest rank among Puerto Rico's tracts is {max(x for x in minority if x is not None)}, because in {high} of the {len(share)} tracts with a value 95% or more of the residents are a minority by the national definition. It is inside the overall rank, as CDC computes it.",
             "corrected": "CDC says files downloaded between 2022-10-27 and 2026-01-15 were incorrect; these were downloaded after that"}
    today = datetime.date.today().isoformat()
    muni = {"built": today, "as_of": y, "years": [EDITION], "geo": {"ids": ids + ["72"], "names": names + ["Puerto Rico"]}, "vars": vs, "sources": sources, "notes": notes}
    tract = {"built": today, "level": "tract", "windows": [EDITION], "geo": {"ids": tracts},
             "vars": [{"key": key, "years": {y: [rank(tract_rows.get(t), col) for t in tracts]}} for key, (col, _, _) in VARS.items()],
             "notes": {**notes, "areas": len(tracts), "in_cdc_file": len(tract_rows), "with_overall_rank": with_value,
                       "source": REF + ", census tracts", "residents": {y: [None if t not in tract_rows else int(float(tract_rows[t]["E_TOTPOP"])) for t in tracts]}}}
    return muni, tract


def build(refresh=False, check=False):
    go = refresh and not check
    docs = dict(zip((OUT, OUT_T), documents(*(rows(fetch(*FILES[lv], go)) for lv in ("municipio", "tract")))))
    stale = 0
    for p, doc in docs.items():
        text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        if check:
            old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            same = old is not None and {**old, "built": None} == {**json.loads(text), "built": None}
            print(f"  {p.name}: {'matches' if same else 'DIFFERS'}")
            stale += not same
            continue
        p.write_text(text, encoding="utf-8", newline="\n")
        log(f"wrote {p.name} ({p.stat().st_size / 1024:.1f} KB)")
    return 1 if stale else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
