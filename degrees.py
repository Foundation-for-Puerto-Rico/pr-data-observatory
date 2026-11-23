"""Degrees and certificates awarded by colleges in Puerto Rico, by level and broad field, for the 78 municipalities and Puerto Rico, every academic year since
2014-15. HANDOFF decision 107, step 7, first part (row school-outcomes: "degrees by field"); docs/degrees.md.

    python degrees.py             # build site/data/degrees_series.json (downloads the years missing from cache/degrees)
    python degrees.py --refresh   # download every year again (NCES revises the previous year's file)
    python degrees.py --check     # rebuild from the cache and exit 1 when the published file is not what it gives (no network, nothing written)

Source, no key: NCES's IPEDS Data Center complete data files (US Government work, public domain), read straight from NCES rather than through the Urban
Institute's portal, which had no completions after 2021 for Puerto Rico on 2026-11-18:
  https://nces.ed.gov/ipeds/datacenter/data/C{year}_A.zip   Completions: awards by institution, 6-digit CIP field, award level and first or second major
  https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip    Directory: each institution's state and county (the municipio where the campus is)
The year is the end of the academic year: 2024 = July 2023 to June 2024. When NCES publishes a revised file (C{year}_a_RV.csv inside the ZIP), it is read.

What is counted. First majors only (MAJORNUM 1), so a student with two majors counts once. Each institution's awards go to the municipio of its campus
in that year's directory. Most university systems report campus by campus, but not all: NUC University reports all of its campuses and online programmes
from Bayamón (14,321 of the island's 48,725 awards in 2023-24, mostly certificates), so a municipio's count follows where a college reports, not always
where its students studied. The notes name each year's largest reporter. A municipio with no college has 0. The island is the sum.
  deg_total        every award: certificates, associate, bachelor's, master's and doctor's degrees (CIP 99, the file's own total)
  deg_associate    associate degrees (award level 3)
  deg_bachelor     bachelor's degrees (award level 5)
  deg_graduate     master's (7) and doctor's degrees (17 research, 18 professional practice, 19 other)
  deg_field_*      bachelor's or higher (levels 5, 7, 17, 18, 19) in a broad field, by the first two digits of the CIP code (FIELDS)
The fields add up to the bachelor's-or-higher total (the "other" field takes the rest), and the six-digit rows add up to the file's own total: both are checked.
"""

import csv
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "degrees"
OUT = DATA / "degrees_series.json"
FIRST, LAST = 2015, 2024
URL = "https://nces.ed.gov/ipeds/datacenter/data/{name}.zip"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
G = "Education · Degrees awarded (IPEDS)"
LEVELS = {"deg_associate": {"3"}, "deg_bachelor": {"5"}, "deg_graduate": {"7", "17", "18", "19"}}
HIGHER = {"5", "7", "17", "18", "19"}
FIELDS = [   # key, label, Spanish, 2-digit CIP families
    ("health", "Health", "Salud", {"51"}),
    ("business", "Business", "Negocios", {"52"}),
    ("education", "Education", "Educación", {"13"}),
    ("stem", "Science, technology, engineering and mathematics", "Ciencias, tecnología, ingeniería y matemáticas", {"01", "03", "11", "14", "15", "26", "27", "40", "41"}),
    ("social", "Social and behavioural sciences", "Ciencias sociales y de la conducta", {"42", "44", "45"}),
    ("arts", "Arts and humanities", "Artes y humanidades", {"05", "09", "16", "23", "24", "38", "39", "50", "54"}),
]
SOURCES = {"nces_ipeds": {"name": "NCES, Integrated Postsecondary Education Data System (IPEDS): completions and directory", "url": "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx",
                          "license": "US Government work (public domain)", "note": "Awards by institution, field and level; read from NCES's complete data files."}}


def log(*a):
    print(*a, flush=True)


def fetch(name, refresh=False, offline=False):
    p = CACHE / f"{name}.zip"
    if p.exists() and not refresh:
        return p
    if offline:
        raise SystemExit(f"degrees: {p.name} is not in the cache (python degrees.py downloads it; --check never does)")
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL.format(name=name), headers=UA, timeout=600)
    r.raise_for_status()
    p.write_bytes(r.content)
    return p


def rows(path):
    """The rows of the CSV in an IPEDS ZIP: the revised file (_RV) when there is one."""
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if n.lower().endswith(".csv")]
    pick = [n for n in names if "_rv" in n.lower()] or names
    return csv.DictReader(io.TextIOWrapper(z.open(pick[0]), encoding="utf-8-sig", errors="replace"))


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def year_counts(year, muni_ids, refresh=False, offline=False):
    """{key: [count per municipio]} for one academic year, and its checks."""
    hd = {r["UNITID"]: r for r in rows(fetch(f"HD{year}", refresh, offline)) if r["STABBR"] == "PR"}
    where = {u: r["COUNTYCD"] for u, r in hd.items()}
    by_inst = {}
    at = {m: i for i, m in enumerate(muni_ids)}
    keys = ["deg_total", *LEVELS, *[f"deg_field_{k}" for k, *_ in FIELDS], "deg_field_other"]
    out = {k: [0] * len(muni_ids) for k in keys}
    six_by_level, total_by_level, unplaced, inst = {}, {}, 0, set()
    for r in rows(fetch(f"C{year}_A", refresh, offline)):
        u = r["UNITID"]
        if u not in where or r["MAJORNUM"] != "1":
            continue
        i = at.get(str(where[u]).zfill(5))
        n = num(r["CTOTALT"])
        lv, cip = str(num(r["AWLEVEL"])), r["CIPCODE"].strip()   # older files pad the code ("05")
        if cip == "99":
            total_by_level[lv] = total_by_level.get(lv, 0) + n
            if i is None:
                unplaced += n
                continue
            inst.add(u)
            by_inst[u] = by_inst.get(u, 0) + n
            out["deg_total"][i] += n
            for k, lvls in LEVELS.items():
                if lv in lvls:
                    out[k][i] += n
            continue
        if "." not in cip:   # a two-digit summary row, if a file has one: the six-digit rows are counted instead
            continue
        six_by_level[lv] = six_by_level.get(lv, 0) + n
        if i is None or lv not in HIGHER:
            continue
        fam = cip.split(".")[0].zfill(2)
        k = next((f"deg_field_{key}" for key, _, _, fams in FIELDS if fam in fams), "deg_field_other")
        out[k][i] += n
    bad = {lv: (six_by_level.get(lv, 0), t) for lv, t in total_by_level.items() if six_by_level.get(lv, 0) != t}
    if bad:
        raise SystemExit(f"degrees {year}: the six-digit rows do not add up to the file's total for award levels {bad}")
    higher = sum(out[f"deg_field_{k}"][i] for k in [f[0] for f in FIELDS] + ["other"] for i in range(len(muni_ids)))
    want = sum(out["deg_bachelor"]) + sum(out["deg_graduate"])
    if higher != want:
        raise SystemExit(f"degrees {year}: the fields add up to {higher}, not to the {want} bachelor's and graduate degrees")
    big = max(by_inst, key=by_inst.get)
    tot = sum(total_by_level.values())
    return out, {"institutions_with_awards": len(inst), "awards_unplaced": unplaced, "file_total": tot,
                 "largest_reporter": {"name": hd[big]["INSTNM"].strip(), "municipio": str(where[big]).zfill(5), "awards": by_inst[big], "share_pct": round(by_inst[big] / tot * 100, 1)}}


def assemble(refresh=False, offline=False):
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    muni = cw["units"]["municipio"]
    ids, names = [r[0] for r in muni], [r[2] for r in muni]
    years = list(range(FIRST, LAST + 1))
    per, notes = {}, {}
    for y in years:
        per[y], notes[str(y)] = year_counts(y, ids, refresh, offline)
    REF = "NCES IPEDS completions (first majors) and directory, academic years ending 2015 to 2024, read from NCES's complete data files; counted by the municipio of each campus"
    WHERE = (" Counted at the campus that reports to IPEDS, not where the graduates live; a municipio with no college has 0. A college may report all its campuses from one place: "
             "NUC University reports its campuses and online programmes from Bayamón. The year is the end of the academic year (2024 = 2023-24).")

    def var(key, label, definition):
        return {"key": key, "group": G, "label": label, "unit": "", "d": 0, "type": "count", "sources": ["nces_ipeds"], "ref": REF, "definition": definition + WHERE,
                "family": "degrees", "years": {str(y): [*per[y][key], sum(per[y][key])] for y in years}}
    vs = [var("deg_total", "Degrees and certificates awarded (all levels)", "Every award colleges in the municipio gave in the academic year, first majors only: certificates and associate, bachelor's, master's and doctor's degrees."),
          var("deg_associate", "Associate degrees awarded", "Associate degrees awarded in the academic year (IPEDS award level 3), first majors only."),
          var("deg_bachelor", "Bachelor's degrees awarded", "Bachelor's degrees awarded in the academic year (IPEDS award level 5), first majors only."),
          var("deg_graduate", "Master's and doctor's degrees awarded", "Master's and doctor's degrees awarded in the academic year (IPEDS award levels 7, 17, 18 and 19: research, professional practice such as medicine and law, and other), first majors only.")]
    for key, en, _, fams in FIELDS:
        vs.append(var(f"deg_field_{key}", f"Bachelor's or higher degrees in {en.lower() if key != 'stem' else 'science, technology, engineering and mathematics (STEM)'}",
                      f"Bachelor's, master's and doctor's degrees awarded in the academic year in {en.lower()}: the CIP families {', '.join(sorted(fams))}, first majors only."))
    vs.append(var("deg_field_other", "Bachelor's or higher degrees in other fields",
                  "Bachelor's, master's and doctor's degrees awarded in the academic year in fields outside the six broad fields of this group (for example communication, law enforcement and protective services, legal studies, theology, family sciences), first majors only."))
    notes["fields"] = {k: {"en": en, "es": es, "cip": sorted(f)} for k, en, es, f in FIELDS}
    notes["first_majors_only"] = True
    return {"as_of": date.today().isoformat(), "years": years, "geo": {"ids": [*ids, "72"], "names": [*names, "Puerto Rico"]}, "vars": vs, "sources": SOURCES, "notes": notes}


def build(refresh=False, check=False):
    doc = assemble(refresh, offline=check)
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    log(f"wrote {OUT.name} ({OUT.stat().st_size / 1024:.1f} KB)")
    for v in doc["vars"]:
        log(f"  {v['key']:22s} " + "  ".join(f"{y}: {v['years'][str(y)][-1]:,}" for y in (FIRST, 2020, LAST)))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in sys.argv and not CACHE.exists():
        print(f"degrees: {CACHE} is not in the cache; nothing to check")
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
