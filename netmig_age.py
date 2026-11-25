"""Net migration by age for the PR Data Observatory: how many people each municipio gained or lost to migration between the 2010 and 2020 censuses, by age
group, measured by the residual (cohort survival) method. HANDOFF decision 107, step 9, sixth part (row derived-net-migration-age); docs/net-migration-age.md.
An estimate (decision 107 b): a demographic model, labeled so, with a check and a range.

    python netmig_age.py --refresh   # read the Census Bureau's municipio files by age and sex and the UN's life tables into cache/netmig/, then build
    python netmig_age.py             # build site/data/netmig_age_series.json from the cache (no network)
    python netmig_age.py --check     # rebuild and exit 1 when the published file is not what it gives (nothing written)

Method (the forward cohort survival residual, as in the US Census Bureau's and the UN's guides to indirect estimation):
  For each municipio, sex and five-year age group, the people aged a to a+4 on 1 April 2010 are aged a+10 to a+14 on 1 April 2020. The life table says what
  share of them would still be alive ten years later; the rest of the difference between the 2020 count and the survivors is net migration:
      net migration (a+10, 2020) = people (a+10, 2020) - people (a, 2010) x L(a+10) / L(a)
  with L the person-years lived in each age group (nLx) of Puerto Rico's life table for each sex, averaged over 2010-2019; the open group 75+ (85+ in 2020)
  uses T(85) / T(75). Children under 10 in 2020 were born during the decade and are left out (their number needs births by municipio).
  The counts: the Census Bureau's April 1, 2010 census counts (PRM-EST2020-AGESEX, YEAR 1) and April 1, 2020 estimates base, built from the 2020 census
  (CC-EST2025-AGESEX-72, YEAR 1), five-year groups by sex. The life table: UN World Population Prospects 2024, abridged life tables, Puerto Rico.
A rate is net migration per 100 of the survivors expected in 2020 (the people the age group would have had with no migration).
The range: the same with the life table of 2010 alone and of 2019 alone (mortality fell over the decade, then rose with the storms and COVID-19).
The check: the island's net migration for ages 10 and over against the demographic balance of the two censuses (change in population, minus births, plus
deaths, from the Census Bureau's estimates components) and against the Census Bureau's and the UN's own net migration for the decade.
"""

import argparse
import csv
import gzip
import io
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "netmig"
F2010 = CACHE / "prm-est2020-agesex.csv"
F2020 = CACHE / "cc-est2025-agesex-72.csv"
FNST = CACHE / "nst-est2020-alldata.csv"
FWPP = CACHE / "wpp_pr.json"
OUT = DATA / "netmig_age_series.json"
URLS = {
    F2010: "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/municipios/asrh/PRM-EST2020-AGESEX.csv",
    F2020: "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/puerto-rico/asrh/cc-est2025-agesex-72.csv",
    FNST: "https://www2.census.gov/programs-surveys/popest/datasets/2010-2020/state/totals/nst-est2020-alldata.csv",
}
WPP = "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/"
WPP_LT = WPP + "WPP2024_Life_Table_Abridged_Medium_1950-2023.csv.gz"
WPP_IND = WPP + "WPP2024_Demographic_Indicators_Medium.csv.gz"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
GROUPS = ["04", "59", "1014", "1519", "2024", "2529", "3034", "3539", "4044", "4549", "5054", "5559", "6064", "6569", "7074", "7579", "8084", "85PLUS"]
START = list(range(0, 90, 5))
BROAD = [("10_19", "10 to 19", 10, 19), ("20_29", "20 to 29", 20, 29), ("30_44", "30 to 44", 30, 44), ("45_64", "45 to 64", 45, 64), ("65_plus", "65 and over", 65, 200)]
G = "Population · Net migration by age, 2010-2020 (estimate)"


def log(*a):
    print(*a, flush=True)


def refresh():
    import requests
    CACHE.mkdir(parents=True, exist_ok=True)
    for p, u in URLS.items():
        r = requests.get(u, headers=UA, timeout=180)
        r.raise_for_status()
        p.write_bytes(r.content)
        log(f"  {p.name}: {len(r.content) / 1024:,.0f} KB")
    out = {"lt": [], "ind": []}
    for url, key in ((WPP_LT, "lt"), (WPP_IND, "ind")):   # about 145 MB and 17 MB: streamed, only Puerto Rico's rows kept
        with requests.get(url, headers=UA, timeout=1800, stream=True) as r:
            r.raise_for_status()
            with gzip.GzipFile(fileobj=r.raw) as gz:
                for x in csv.DictReader(io.TextIOWrapper(gz, encoding="utf-8-sig")):
                    if x["LocID"] == "630" and 2008 <= int(x["Time"]) <= 2025:
                        out[key].append(x if key == "lt" else {k: x[k] for k in ("Time", "NetMigrations", "TPopulation1July", "Births", "Deaths")})
    FWPP.write_text(json.dumps(out), encoding="utf-8")
    log(f"  UN WPP 2024: {len(out['lt'])} life-table rows, {len(out['ind'])} indicator rows for Puerto Rico")


def counts(path):
    """{geoid: {"m": [18 groups], "f": [18 groups]}} of YEAR 1 (the census base) of a Census Bureau age-sex file, and the Puerto Rico total."""
    out = {}
    for r in csv.DictReader(open(path, encoding="latin-1")):
        if r["YEAR"] != "1":
            continue
        gid = "72" + r["MUNICIPIO"].zfill(3)
        out[gid] = {"m": [int(r[f"AGE{g}_MALE"]) for g in GROUPS], "f": [int(r[f"AGE{g}_FEM"]) for g in GROUPS], "name": r["NAME"].replace(" Municipio", "")}
    if len(out) != 78:
        raise SystemExit(f"netmig_age: {len(out)} municipios in {path.name} (78 expected)")
    return out


def life_table(rows, years):
    """{sex: (L by 5-year group start 0..80 and T at 75 and 85)} averaged over `years`, from the UN's abridged table (0 and 1-4 joined into 0-4)."""
    out = {}
    for sid, sex in (("1", "m"), ("2", "f")):
        acc = {}
        for x in rows:
            if x["SexID"] != sid or int(x["Time"]) not in years:
                continue
            a = int(x["AgeGrpStart"])
            k = 0 if a < 5 else a
            acc.setdefault(k, []).append((int(x["Time"]), float(x["Lx"])))
            acc.setdefault(("T", a), []).append((int(x["Time"]), float(x["Tx"])))
        L = {}
        for k, v in acc.items():
            if isinstance(k, int):
                byy = {}
                for y, l in v:
                    byy[y] = byy.get(y, 0) + l
                L[k] = sum(byy.values()) / len(byy)
        T75 = sum(v for _, v in acc[("T", 75)]) / len(acc[("T", 75)])
        T85 = sum(v for _, v in acc[("T", 85)]) / len(acc[("T", 85)])
        out[sex] = (L, T75, T85)
    return out


def survival(lt):
    """{sex: [ten-year survival of the 2010 group i into the 2020 group i + 2]} for i = 0 .. 15 (0-4 -> 10-14, ..., 75+ -> 85+)."""
    out = {}
    for sex, (L, T75, T85) in lt.items():
        s = [L[START[i + 2]] / L[START[i]] for i in range(15)]
        s.append(T85 / T75)   # 75+ in 2010 into 85+ in 2020
        out[sex] = s
    return out


def residual(p10, p20, S):
    """(net migration, expected survivors) per 2020 group index 2..17 summed over sex, for one area."""
    nm, ex = [0.0] * 18, [0.0] * 18
    for sex in ("m", "f"):
        for i in range(16):
            j = i + 2
            src = p10[sex][i] if i < 15 else sum(p10[sex][15:])   # 75-79, 80-84 and 85+ of 2010 all reach 85+ in 2020
            e = src * S[sex][i]
            ex[j] += e
            nm[j] += (p20[sex][j] if j < 17 else p20[sex][17]) - e
    return nm, ex


def broad(nm, ex):
    """{broad group: (net migration, expected)} from the 2020 five-year groups."""
    out = {}
    for key, _, lo, hi in BROAD:
        idx = [j for j in range(2, 18) if lo <= START[j] <= hi]
        out[key] = (sum(nm[j] for j in idx), sum(ex[j] for j in idx))
    out["10_plus"] = (sum(nm[2:]), sum(ex[2:]))
    return out


def build(do_refresh=False, check=False):
    if do_refresh:
        refresh()
    if not all(p.exists() for p in (F2010, F2020, FNST, FWPP)):
        log("netmig_age: cache/netmig is missing (python netmig_age.py --refresh); nothing built")
        return 1 if check else 0
    c10, c20 = counts(F2010), counts(F2020)
    wpp = json.loads(FWPP.read_text(encoding="utf-8"))
    S = survival(life_table(wpp["lt"], range(2010, 2020)))
    S_lo, S_hi = survival(life_table(wpp["lt"], [2010])), survival(life_table(wpp["lt"], [2019]))
    ids = sorted(c10)
    res = {g: broad(*residual(c10[g], c20[g], S)) for g in ids}
    tot10 = {s: [sum(c10[g][s][i] for g in ids) for i in range(18)] for s in ("m", "f")}
    tot20 = {s: [sum(c20[g][s][i] for g in ids) for i in range(18)] for s in ("m", "f")}
    isl = broad(*residual(tot10, tot20, S))
    rng = {name: broad(*residual(tot10, tot20, s))["10_plus"][0] for name, s in (("life_table_2010", S_lo), ("life_table_2019", S_hi))}
    # the check: the demographic balance of the two censuses, and the Census Bureau's and the UN's own net migration
    nst = next(r for r in csv.DictReader(open(FNST, encoding="latin-1")) if r["STATE"] == "72")
    births = sum(int(nst[f"BIRTHS{y}"]) for y in range(2010, 2021))
    deaths = sum(int(nst[f"DEATHS{y}"]) for y in range(2010, 2021))
    pep_nm = sum(int(nst[f"NETMIG{y}"]) for y in range(2010, 2021))
    p10, p20 = int(nst["CENSUS2010POP"]), sum(sum(c20[g]["m"]) + sum(c20[g]["f"]) for g in ids)
    balance = (p20 - p10) - (births - deaths)
    un_nm = round(sum(float(x["NetMigrations"]) for x in wpp["ind"] if 2010 <= int(x["Time"]) <= 2019) * 1000)
    # the children born in the decade, for the balance: the 2020 count of ages 0-9 minus the births to 1 April 2020 that survive (the life table's share of a birth
    # alive at ages 0-9); a quarter of 2020's births (April to July) are left out of the births
    kids = sum(sum(c20[g][s][0:2]) for g in ids for s in ("m", "f"))
    lt = life_table(wpp["lt"], range(2010, 2020))
    alive = sum((lt[s][0][0] + lt[s][0][5]) / 1e6 for s in ("m", "f")) / 2
    b_apr = births - round(int(nst["BIRTHS2020"]) / 4)
    kids_nm = round(kids - b_apr * alive)
    year = 2020
    vars_ = []
    rate = lambda nm, ex: round(nm / ex * 100, 1) if ex else None   # noqa: E731
    common = (" An estimate by the residual method: the 2020 census count of each age group minus the survivors of the same people in the 2010 census, "
              "by sex, with Puerto Rico's life table (UN World Population Prospects 2024, 2010-2019). It counts moves to and from the rest of Puerto Rico and "
              "abroad together, net; errors in either census land in it, and in small municipios a few hundred people can move the figure.")
    for key, lab, lo, hi in BROAD + [("10_plus", "10 and over", 10, 200)]:
        vals = [rate(*res[g][key]) for g in ids] + [rate(*isl[key])]
        vars_.append({"key": f"netmig_{key}_pct", "group": G, "label": f"Net migration, ages {lab} in 2020, 2010-2020 (estimate, % of expected)", "unit": "%", "d": 1, "type": "rate",
                      "sources": ["census_pep", "un_wpp"], "ref": REF,
                      "definition": (f"Net migration between the 2010 and 2020 censuses of the people aged {lab} in 2020 (aged {max(lo - 10, 0)} to {hi - 10 if hi < 200 else 'over'} in 2010), "
                                     "per 100 of the people of that age the municipio would have had with no migration: positive, more came than left; negative, more left.") + common,
                      "family": "netmig_age", "counted": False, "noPerHU": True, "estimate": True, "years": {str(year): vals}})
    vars_.append({"key": "netmig_10_plus", "group": G, "label": "Net migration, ages 10 and over in 2020, 2010-2020 (estimate, people)", "unit": "people", "d": 0, "type": "count",
                  "sources": ["census_pep", "un_wpp"], "ref": REF,
                  "definition": "The number of people aged 10 and over in 2020 that the municipio gained (positive) or lost (negative) to migration between the 2010 and 2020 censuses, net." + common,
                  "family": "netmig_age", "counted": True, "noPerHU": True, "estimate": True,
                  "years": {str(year): [round(res[g]["10_plus"][0]) for g in ids] + [round(isl["10_plus"][0])]}})
    notes = {"window": "1 April 2010 to 1 April 2020", "method": "forward cohort survival residual, five-year groups by sex",
             "life_table": "UN WPP 2024, abridged, Puerto Rico, nLx averaged over 2010-2019 by sex",
             "counts": {"2010": "Census Bureau PRM-EST2020-AGESEX, YEAR 1 (1 April 2010 census)", "2020": "Census Bureau CC-EST2025-AGESEX-72, YEAR 1 (1 April 2020 estimates base, from the 2020 census)"},
             "island": {k: {"net_migration": round(v[0]), "expected": round(v[1]), "pct": rate(*v)} for k, v in isl.items()},
             "range": {"10_plus_net_migration": {**{k: round(v) for k, v in rng.items()}, "published": round(isl["10_plus"][0])}},
             "check": {"census_2010": p10, "census_2020_base": p20, "births_2010_2020": births, "deaths_2010_2020": deaths,
                       "demographic_balance_all_ages": balance, "children_0_9_net_migration": kids_nm,
                       "residual_all_ages": round(isl["10_plus"][0]) + kids_nm,
                       "residual_vs_balance_pct": round((round(isl["10_plus"][0]) + kids_nm) / balance * 100 - 100, 1), "census_bureau_net_migration_vintage_2020": pep_nm, "un_wpp_net_migration_2010_2019": un_nm,
                       "note": "The balance counts every age, children born in the decade included, and its births and deaths run to 1 July 2020; the residual counts ages 10 and over."},
             "left_out": "children under 10 in 2020 (born during the decade)"}
    doc = {"as_of": date.today().isoformat(), "years": [year], "geo": {"ids": [*ids, "72"], "names": [c10[g]["name"] for g in ids] + ["Puerto Rico"]}, "vars": vars_,
           "sources": SOURCES, "notes": notes}
    if check:
        old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else None
        strip = lambda x: {**x, "built": None, "as_of": None}   # noqa: E731
        same = old is not None and strip(old) == strip(json.loads(json.dumps(doc)))
        log(f"  {OUT.name}: {'matches' if same else 'DIFFERS'}")
        return 0 if same else 1
    OUT.write_text(json.dumps({"built": date.today().isoformat(), **doc}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    i = notes["island"]
    log(f"wrote {OUT.name}: island ages 10+ {i['10_plus']['net_migration']:,} ({i['10_plus']['pct']}%); " + ", ".join(f"{k} {v['pct']}%" for k, v in i.items() if k != "10_plus"))
    log(f"  range {notes['range']}; check {notes['check']}")
    return 0


REF = ("Estimated by the observatory: the 2010 and 2020 census counts by municipio, age and sex (Census Bureau estimates files, census bases) and Puerto Rico's "
       "life table (UN WPP 2024), by the residual method (netmig_age.py)")
SOURCES = {
    "census_pep": {"name": "US Census Bureau, 2010 and 2020 censuses by municipio, age and sex (the census bases of the Population Estimates files)",
                         "url": "https://www2.census.gov/programs-surveys/popest/datasets/", "license": "US Government work (no US copyright)",
                         "note": "PRM-EST2020-AGESEX (1 April 2010) and CC-EST2025-AGESEX-72 (1 April 2020 base); births and deaths 2010-2020 from NST-EST2020-ALLDATA for the check."},
    "un_wpp": {"name": "United Nations, World Population Prospects 2024: abridged life tables and demographic indicators, Puerto Rico", "url": "https://population.un.org/wpp/",
               "license": "CC BY 3.0 IGO", "note": "Person-years lived by age and sex (nLx), 2010-2019, and the UN's net migration for the check."},
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="read the Census Bureau files and the UN tables first")
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the published file")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return build(a.refresh, a.check)


if __name__ == "__main__":
    raise SystemExit(main())
