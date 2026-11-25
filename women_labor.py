"""Women in the labor force, by municipio and for any group of municipios: the data of the Knowledge Area analysis (2026-10-30).

Asked for the Human Capital chapter of FPR's Eastern Region Strategic Vision (ERSV): the women's labor force participation rate of the
region's 15 municipios, next to the island's, and the counts behind it (how many women are of working age, how many the survey interviewed).

    python women_labor.py              # reads the cached tables, writes site/data/women_labor.json and prints the region's figures
    python women_labor.py --refresh    # downloads the tables again
    python women_labor.py --check      # rebuilds in memory and compares with the published file (no write)

Sources (Census Bureau, American Community Survey, 5-year estimates; summary files, no key):
  B23001  Sex by age by employment status, population 16 and over          every window below
  B23003  Females 20 to 64 by presence and age of own children, by status   every window below
  B98003  Unweighted total population sample (final interviews)             2020-2024 (table-based file)
  B98001  Unweighted housing unit sample (final interviews)                 2020-2024

Windows: 2010-2014, 2015-2019 and 2020-2024, the three five-year windows that share no year, so they can be compared (overlapping windows cannot).
2015-2019 and 2010-2014 come from the per-sequence files (housing_series.acs_sequence), 2020-2024 from the table-based files (acs_small).

Method (docs/analysis/women-labor-2026-10/README.md):
  - Rates are pooled: the region's rate is the sum of its municipios' women in the labor force over the sum of its women 16 and over.
    An average of the 15 municipio rates gives each municipio the same weight whatever its size; it is computed only to show the difference.
  - Labor force participation = in the labor force (civilian and Armed Forces) / population 16 and over, as in ACS table S2301.
    Unemployment rate = unemployed / civilian labor force.
  - Margins of error are the Census Bureau's 90% margins. Sums: square root of the sum of squared margins. Proportions and ratios: the
    Census Bureau's formulas (ACS General Handbook, chapter 8). A difference is called significant when it is larger than its own margin (90%).
  - A region is compared with the rest of the island, not with the island total that contains it, so the two estimates do not share people.
  - Age-adjusted rate: the region's rates for each age group applied to the age mix of the rest of the island's women 16 and over (direct
    standardization). The gap with the rest of the island then splits into a part due to age mix and a part due to participation within each age (Kitagawa, 1955).
"""
import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
OUT = DATA / "women_labor.json"
WINDOWS = [2014, 2019, 2024]      # end years of 2010-2014, 2015-2019, 2020-2024
LATEST = WINDOWS[-1]
Z90 = 1.645

# Age groups: (label, first cells of B23001 for males; females are +86). Under 65 a block has 7 cells (total, in labor force, Armed Forces,
# civilian, employed, unemployed, not in labor force); from 65 a block has 5 (total, in labor force, employed, unemployed, not in labor force).
AGES = [("16-19", [3]), ("20-24", [10, 17]), ("25-34", [24, 31]), ("35-44", [38]), ("45-54", [45]), ("55-64", [52, 59, 66]), ("65+", [73, 78, 83])]
FEMALE_OFFSET = 86
B23001_CELLS, B23003_CELLS = 173, 30

# Females 20-64 by own children (B23003): (key, first cells). Each block has 7 cells like B23001's under 65.
KIDS = [("u6", [3, 10]), ("617", [17]), ("none", [24])]

from regions import ERSV  # noqa: E402  the 15 municipios of the ERSV, kept in one place (regions.py)
GROUPS = {
    "ersv": {"name": {"en": "Eastern Region (ERSV, 15 municipios)", "es": "Región Este (ERSV, 15 municipios)"}, "ids": sorted(ERSV),
             "source": {"en": "FPR, Eastern Region Strategic Vision, Human Capital chapter", "es": "FPR, Visión Estratégica de la Región Este, capítulo de Capital Humano"}},
}


def log(*a):
    print(*a, flush=True)


# ── Estimate-and-margin arithmetic ───────────────────────────────────────────

def esum(cells):
    """[estimate, margin] of a sum; None when any part has no estimate. A missing margin counts as 0 (the Census Bureau's controlled totals)."""
    if any(c is None or c[0] is None for c in cells):
        return None
    return [sum(c[0] for c in cells), math.sqrt(sum((c[1] or 0) ** 2 for c in cells))]


def prop(num, den):
    """Proportion num/den (num is part of den) as [value, margin], in percent. Falls back to the ratio formula when the root is negative."""
    if not num or not den or not den[0]:
        return None
    p = num[0] / den[0]
    under = num[1] ** 2 - p * p * den[1] ** 2
    if under < 0:
        under = num[1] ** 2 + p * p * den[1] ** 2
    return [100 * p, 100 * math.sqrt(under) / den[0]]


def diff(a, b):
    """a - b with its margin, and whether it is significant at 90% (larger than its margin)."""
    if not a or not b:
        return None
    d, m = a[0] - b[0], math.sqrt(a[1] ** 2 + b[1] ** 2)
    return {"v": d, "m": m, "sig": abs(d) > m}


def cv(e):
    """Coefficient of variation (%) of an estimate with a 90% margin."""
    return None if not e or not e[0] else 100 * (e[1] / Z90) / e[0]


# ── Reading the tables ───────────────────────────────────────────────────────

def read_window(year, refresh=False):
    """{geoid: {cell: [estimate, margin]}} for the island ('72') and the 78 municipios."""
    if year >= 2021:
        import acs_small
        out = {}
        for t in ("B23001", "B23003", "B98003", "B98001"):
            r = acs_small.read_table(t, vintage=year, levels=["island", "municipio"], refresh=refresh)
            for lv in ("island", "municipio"):
                for g, rec in r["levels"][lv].items():
                    out.setdefault(g, {}).update(rec)
        return out
    import housing_series
    return housing_series.acs_sequence(year, refresh, tables={"B23001": B23001_CELLS, "B23003": B23003_CELLS})


def cell(rec, t, n):
    v = rec.get(f"{t}_{n:03d}")
    return None if v is None or v[0] is None else [v[0], v[1] or 0]


def block(rec, t, starts, short):
    """Sums over blocks: total, labor force, civilian labor force, unemployed. `short` marks the 5-cell blocks of 65 and over."""
    pop, lf, clf, une = [], [], [], []
    for s in starts:
        pop.append(cell(rec, t, s)); lf.append(cell(rec, t, s + 1))
        if short:
            clf.append(cell(rec, t, s + 1)); une.append(cell(rec, t, s + 3))
        else:
            clf.append(cell(rec, t, s + 3)); une.append(cell(rec, t, s + 5))
    return [esum(pop), esum(lf), esum(clf), esum(une)]


def area_record(rec):
    """The compact record of one area and window: per sex, per age group, [pop, lf, clf, une] each [estimate, margin]; children; sample."""
    out = {}
    for sex, off in (("m", 0), ("f", FEMALE_OFFSET)):
        out[sex] = [block(rec, "B23001", [s + off for s in starts], label == "65+") for label, starts in AGES]
    if rec.get("B23003_001"):
        out["kids"] = {k: block(rec, "B23003", starts, False)[:2] for k, starts in KIDS}
    if rec.get("B98003_001"):
        out["sample"] = {"people": rec["B98003_001"][0], "homes": (rec.get("B98001_002") or [None])[0]}
    return out


def r1(x, d=1):
    return None if x is None else round(x, d)


def pack(rec):
    """Rounds for publication: counts to whole numbers, margins to whole numbers."""
    def pe(e):
        return None if e is None else [round(e[0]), round(e[1])]
    out = {s: [[pe(e) for e in g] for g in rec[s]] for s in ("m", "f")}
    if "kids" in rec:
        out["kids"] = {k: [pe(e) for e in v] for k, v in rec["kids"].items()}
    if "sample" in rec:
        out["sample"] = rec["sample"]
    return out


# ── Aggregating and the analysis ─────────────────────────────────────────────

def combine(records):
    """Adds area records (published, rounded form) cell by cell: a group of municipios."""
    out = {}
    for sex in ("m", "f"):
        out[sex] = [[esum([r[sex][a][k] for r in records]) for k in range(4)] for a in range(len(AGES))]
    if all("kids" in r for r in records):
        out["kids"] = {k: [esum([r["kids"][k][j] for r in records]) for j in range(2)] for k, _ in KIDS}
    if all("sample" in r for r in records):
        out["sample"] = {"people": sum(r["sample"]["people"] or 0 for r in records), "homes": sum(r["sample"]["homes"] or 0 for r in records)}
    return out


def totals(rec, sex, ages=None):
    """[pop, lf, clf, une] summed over age groups (all by default)."""
    idx = range(len(AGES)) if ages is None else ages
    return [esum([rec[sex][a][k] for a in idx]) for k in range(4)]


PRIME = [2, 3, 4]          # 25-54
WORKING = [0, 1, 2, 3, 4, 5]   # 16-64


def measures(rec):
    """The headline measures of one area or group."""
    f, m, fp, fw = totals(rec, "f"), totals(rec, "m"), totals(rec, "f", PRIME), totals(rec, "f", WORKING)
    out = {
        "women16": f[0], "women_lf": f[1], "women_une": f[3],
        "lfpr_f": prop(f[1], f[0]), "lfpr_m": prop(m[1], m[0]),
        "lfpr_f_prime": prop(fp[1], fp[0]), "lfpr_m_prime": prop(totals(rec, "m", PRIME)[1], totals(rec, "m", PRIME)[0]),
        "lfpr_f_16_64": prop(fw[1], fw[0]),
        "unemp_f": prop(f[3], f[2]), "unemp_m": prop(m[3], m[2]),
        "share_f_65": prop(rec["f"][6][0], f[0]),
        "by_age_f": [prop(rec["f"][a][1], rec["f"][a][0]) for a in range(len(AGES))],
        "by_age_m": [prop(rec["m"][a][1], rec["m"][a][0]) for a in range(len(AGES))],
        "age_mix_f": [prop(rec["f"][a][0], f[0]) for a in range(len(AGES))],
    }
    if "kids" in rec:
        out["lfpr_kids"] = {k: prop(rec["kids"][k][1], rec["kids"][k][0]) for k, _ in KIDS}
    if "sample" in rec:
        out["sample"] = rec["sample"]
    return out


def age_adjust(region, standard):
    """Direct standardization of the region's women's rate to the standard's age mix, and the Kitagawa split of the gap (points)."""
    ra = [region["f"][a][1][0] / region["f"][a][0][0] for a in range(len(AGES))]
    sa = [standard["f"][a][1][0] / standard["f"][a][0][0] for a in range(len(AGES))]
    rt, st = sum(region["f"][a][0][0] for a in range(len(AGES))), sum(standard["f"][a][0][0] for a in range(len(AGES)))
    rw = [region["f"][a][0][0] / rt for a in range(len(AGES))]
    sw = [standard["f"][a][0][0] / st for a in range(len(AGES))]
    crude_r, crude_s = sum(r * w for r, w in zip(ra, rw)), sum(r * w for r, w in zip(sa, sw))
    adjusted = sum(r * w for r, w in zip(ra, sw))
    mix = sum((rw[a] - sw[a]) * (ra[a] + sa[a]) / 2 for a in range(len(AGES)))
    rate = sum((ra[a] - sa[a]) * (rw[a] + sw[a]) / 2 for a in range(len(AGES)))
    return {"crude": 100 * crude_r, "standard": 100 * crude_s, "adjusted": 100 * adjusted, "gap": 100 * (crude_r - crude_s),
            "from_age_mix": 100 * mix, "from_rates": 100 * rate}


def unweighted_mean(areas, ids, key="lfpr_f"):
    vals = [measures(areas[g])[key][0] for g in ids]
    return sum(vals) / len(vals)


def analysis(areas, groups):
    """The figures the page leads with, for each group, every window: kept in the file so the page and the tests read the same numbers."""
    out = {}
    island_ids = [g for g in areas[str(LATEST)] if len(g) == 5]
    for gid, grp in groups.items():
        per = {}
        for w in WINDOWS:
            a = areas[str(w)]
            reg = combine([a[g] for g in grp["ids"]])
            rest = combine([a[g] for g in island_ids if g not in grp["ids"]])
            mr, mo, mi = measures(reg), measures(rest), measures(a["72"])
            per[str(w)] = {
                "region": mr, "rest": mo, "island": mi,
                "vs_rest": {k: diff(mr[k], mo[k]) for k in ("lfpr_f", "lfpr_f_prime", "lfpr_m", "unemp_f")},
                "gender_gap": diff(mr["lfpr_m"], mr["lfpr_f"]),
                "gender_gap_prime": diff(mr["lfpr_m_prime"], mr["lfpr_f_prime"]),
                "age_adjusted": age_adjust(reg, rest),
                "unweighted_mean_lfpr_f": unweighted_mean(a, grp["ids"]),
            }
        first, last = per[str(WINDOWS[0])]["region"], per[str(LATEST)]["region"]
        per["change"] = {k: diff(last[k], first[k]) for k in ("lfpr_f", "lfpr_f_prime", "lfpr_m", "women16")}
        out[gid] = per
    return out


def rounded(o):
    if isinstance(o, float):
        return round(o, 2)
    if isinstance(o, dict):
        return {k: rounded(v) for k, v in o.items()}
    if isinstance(o, list):
        return [rounded(v) for v in o]
    return o


def tourism_groups():
    cw = json.loads((DATA / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    regs = {r[0]: r for r in cw["units"]["region"]}
    out = {}
    for rid, r in regs.items():
        ids = sorted(u[0] for u in cw["units"]["municipio"] if u[1] == rid)
        out[rid] = {"name": {"en": r[3], "es": r[2]}, "ids": ids, "source": {"en": "Puerto Rico Tourism Company tourism regions", "es": "Regiones turísticas de la Compañía de Turismo de Puerto Rico"}}
    return out, {u[0]: u[2] for u in cw["units"]["municipio"]}


def build(refresh=False):
    tour, names = tourism_groups()
    for g, n in ERSV.items():
        if names.get(g) != n:
            raise RuntimeError(f"ERSV municipio {g}: the crosswalk says {names.get(g)!r}, the list says {n!r}")
    areas = {}
    for w in WINDOWS:
        raw = read_window(w, refresh)
        areas[str(w)] = {g: pack(area_record(rec)) for g, rec in raw.items() if g == "72" or g in names}
        if len(areas[str(w)]) != 79:
            raise RuntimeError(f"ACS {w - 4}-{w}: {len(areas[str(w)])} areas, expected 79")
        log(f"  ACS {w - 4}-{w}: 79 areas")
    groups = {**GROUPS, **tour}
    doc = {
        "built": date.today().isoformat(),
        "title": {"en": "Women in the labor force", "es": "Las mujeres en la fuerza laboral"},
        "windows": [f"{w - 4}-{w}" for w in WINDOWS], "window_ends": WINDOWS, "latest": LATEST,
        "ages": [a for a, _ in AGES], "prime": PRIME, "working": WORKING, "kids": [k for k, _ in KIDS],
        "cells": ["pop", "lf", "clf", "une"],
        "names": names,
        "groups": {k: {kk: vv for kk, vv in g.items()} for k, g in groups.items()},
        "sources": ["acs_b23001", "acs_b23003", "acs_b98003"],
        "areas": areas,
        "analysis": rounded(analysis(areas, {"ersv": groups["ersv"]})),
    }
    return doc


SERIES_OUT = DATA / "labor_sex_series.json"
SERIES_VARS = [
    # key, label, unit, decimals, type, definition
    ("lfpr_women", "Labor force participation, women 16 and over", "%", 1, "rate",
     "Women 16 and over in the labor force (working, or without work and looking for it; civilian or Armed Forces) as a share of all women 16 and over (ACS B23001)."),
    ("lfpr_men", "Labor force participation, men 16 and over", "%", 1, "rate",
     "Men 16 and over in the labor force as a share of all men 16 and over (ACS B23001)."),
    ("lfpr_women_prime", "Labor force participation, women 25 to 54", "%", 1, "rate",
     "Women 25 to 54 (the prime working ages) in the labor force as a share of all women 25 to 54 (ACS B23001). Less affected than the 16-and-over rate by how many women are retired or in school."),
    ("lfpr_gap", "Participation gap, men minus women (percentage points)", "", 1, "ratio",
     "The men's labor force participation rate minus the women's, in percentage points (ACS B23001). Positive when more men than women take part."),
    ("unemp_women", "Unemployment rate, women 16 and over", "%", 1, "rate",
     "Unemployed women as a share of women in the civilian labor force (ACS B23001)."),
    ("women_16plus", "Women 16 and over", "", 0, "count",
     "Women 16 and over living in the area: the working-age population the participation rate divides by (ACS B23001)."),
    ("women_in_lf", "Women in the labor force", "", 0, "count",
     "Women 16 and over in the labor force: working, or without work and looking for it (ACS B23001)."),
]


def series_doc(doc):
    """The map's datasets (labor_sex_series.json): one value and margin per municipio and window, in the order of economy_series.json."""
    econ = json.loads((DATA / "economy_series.json").read_text(encoding="utf-8"))
    ids = econ["geo"]["ids"]
    vals = {k: {} for k, *_ in SERIES_VARS}
    moes = {k: {} for k, *_ in SERIES_VARS}
    for w in WINDOWS:
        a = doc["areas"][str(w)]
        col = {k: [] for k, *_ in SERIES_VARS}
        for g in ids:
            m = measures(a[g])
            f = totals(a[g], "f")
            got = {"lfpr_women": m["lfpr_f"], "lfpr_men": m["lfpr_m"], "lfpr_women_prime": m["lfpr_f_prime"], "unemp_women": m["unemp_f"],
                   "women_16plus": f[0], "women_in_lf": f[1]}
            gap = diff(m["lfpr_m"], m["lfpr_f"])
            got["lfpr_gap"] = [gap["v"], gap["m"]] if gap else None
            for k, _, _, d, *_ in SERIES_VARS:
                e = got[k]
                col[k].append(None if e is None else [round(e[0], d), round(e[1], d)])
        for k in col:
            vals[k][str(w)] = [None if e is None else e[0] for e in col[k]]
            moes[k][str(w)] = [None if e is None else e[1] for e in col[k]]
    return {
        "built": doc["built"], "years": WINDOWS, "geo": {"ids": ids, "names": econ["geo"]["names"]},
        "vars": [{"key": k, "group": "Labor force by sex", "label": lab, "unit": u, "d": d, "type": t, "sources": ["acs"], "ref": "ACS B23001",
                  "definition": de, "family": "labor_sex", "years": vals[k], "moe": moes[k]} for k, lab, u, d, t, de in SERIES_VARS],
    }


def report(doc):
    a = doc["analysis"]["ersv"]
    for w in doc["window_ends"]:
        x = a[str(w)]
        r, i, o = x["region"], x["island"], x["rest"]
        log(f"{w - 4}-{w}: women 16+ {r['women16'][0]:,.0f} ±{r['women16'][1]:,.0f}; LFPR women region {r['lfpr_f'][0]:.1f} ±{r['lfpr_f'][1]:.1f}, "
            f"island {i['lfpr_f'][0]:.1f} ±{i['lfpr_f'][1]:.1f}, rest {o['lfpr_f'][0]:.1f}; diff vs rest {x['vs_rest']['lfpr_f']['v']:+.1f} ±{x['vs_rest']['lfpr_f']['m']:.1f} "
            f"sig={x['vs_rest']['lfpr_f']['sig']}; prime 25-54 {r['lfpr_f_prime'][0]:.1f} vs island {i['lfpr_f_prime'][0]:.1f}; men {r['lfpr_m'][0]:.1f}; "
            f"age-adjusted {x['age_adjusted']['adjusted']:.1f} (gap {x['age_adjusted']['gap']:+.1f} = mix {x['age_adjusted']['from_age_mix']:+.1f} + rates {x['age_adjusted']['from_rates']:+.1f}); "
            f"unweighted mean {x['unweighted_mean_lfpr_f']:.1f}; sample {r.get('sample')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true", help="rebuild in memory and compare with the published file")
    args = ap.parse_args(argv)
    doc = build(args.refresh)
    report(doc)
    ser = series_doc(doc)
    if args.check:
        bad = 0
        for path, new in ((OUT, doc), (SERIES_OUT, ser)):
            old = json.loads(path.read_text(encoding="utf-8"))
            same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(json.dumps(new)).items() if k != "built"}
            log(f"{path.name} is current" if same else f"{path.name} differs from a rebuild: run python women_labor.py")
            bad += not same
        return 1 if bad else 0
    for path, new in ((OUT, doc), (SERIES_OUT, ser)):
        path.write_text(json.dumps(new, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
