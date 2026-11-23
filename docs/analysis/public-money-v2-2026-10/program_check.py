"""The checks behind decision 69 (Public money v2, step 2): which years of each assistance listing pass the placement rule, how the start years move when
the thresholds move, what share of all federal money to Puerto Rico the seven listings are, and whether USAspending's Social Security values by
municipio agree with the Social Security Administration's own county tables.

    python docs/analysis/public-money-v2-2026-10/program_check.py          # writes program_check.json beside this file

Reads the USAspending cache that `economy_series.py --programs` writes (cache/economy/usaspending/programs), site/data/economy_series.json and the
SSA tables in ssa/ ("OASDI Beneficiaries by State and County", Puerto Rico, Table 5, December 2013 and December 2024; ssa.gov refuses scripted
downloads, so they were saved from a browser on 2026-10-31). Needs openpyxl.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import economy_series as es  # noqa: E402

CACHE = ROOT / "cache" / "economy" / "usaspending" / "programs"


def cached():
    out = {}
    for f in CACHE.glob("*.json"):
        fy, prog = f.stem.split("_", 1)
        out.setdefault(prog, {})[int(fy)] = json.loads(f.read_text(encoding="utf-8"))
    return out


def start_year(data, min_places, max_sj):
    """kept_years() with other thresholds: the first year of the latest unbroken run of passing years."""
    ok = [fy for fy in sorted(data) if (lambda n, sj, u: n >= min_places and sj is not None and sj < max_sj and (u is None or u <= es.MAX_UNPLACED))(*es.placement(data[fy]))]
    if not ok:
        return None
    ys = sorted(data)
    s = ok[-1]
    for fy in reversed(ys[:ys.index(ok[-1])]):
        if fy not in ok:
            break
        s = fy
    return s


def ssa_table5(path):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True)["Table 5"]
    out = {}
    for r in ws.iter_rows(values_only=True):
        if isinstance(r[2], int) and r[2] > 72000:   # columns: retirement 4-6, survivors 7-8, disability 9-11, in thousands of dollars a month
            out[str(r[2])] = {"ss_retirement": sum(r[4:7]) * 12e3, "ss_survivors": sum(r[7:9]) * 12e3, "ss_disability": sum(r[9:12]) * 12e3}
    return out


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5


def main():
    data = cached()
    econ = json.loads((ROOT / "site" / "data" / "economy_series.json").read_text(encoding="utf-8"))
    V = {v["key"]: v for v in econ["vars"]}
    ids, names = econ["geo"]["ids"], econ["geo"]["names"]
    res = {"rule": {"min_places": es.MIN_PLACES, "max_san_juan_pct": es.MAX_SAN_JUAN, "max_unplaced_pct": es.MAX_UNPLACED}, "years": {}, "kept": {}, "sensitivity": {}, "coverage": {}, "ssa": {}}

    for prog, key in es.PROGRAMS.items():
        d = data[prog]
        res["years"][key] = {str(fy): dict(zip(("municipios", "san_juan_pct", "unplaced_pct"), es.placement(d[fy])), passes=es.passes(*es.placement(d[fy]))) for fy in sorted(d)}
        res["kept"][key] = [min(es.kept_years(d)), max(es.kept_years(d))]
        res["sensitivity"][key] = {f"{mp}/{sj}": start_year(d, mp, sj) for mp in (10, 20, 30) for sj in (35, 40, 45, 50)}

    keys = ["fed_prog_" + k for k in es.PROGRAMS.values()]
    for fy, a in sorted(V["fed_awards_total"]["years"].items()):
        seven = sum((V[k]["years"].get(fy) or [0] * 79)[-1] or 0 for k in keys)
        res["coverage"][fy] = {"seven_listings": round(seven), "all_federal_awards": a[-1], "pct": round(seven / a[-1] * 100, 1)}

    for year, fy in ((2013, "2014"), (2024, "2025")):   # December falls in the next federal fiscal year
        ssa = ssa_table5(HERE / "ssa" / f"oasdi_sc_{year}_pr.xlsx")
        for k in ("ss_retirement", "ss_disability", "ss_survivors"):
            a = V["fed_prog_" + k]["years"][fy]
            us, sa = [a[i] or 0 for i in range(78)], [ssa[ids[i]][k] for i in range(78)]
            su, ss = [x / sum(us) * 100 for x in us], [x / sum(sa) * 100 for x in sa]
            gap = max(range(78), key=lambda i: abs(su[i] - ss[i]))
            res["ssa"][f"{k}|FY{fy} vs December {year}"] = {
                "usaspending_total": round(sum(us)), "ssa_december_x12": round(sum(sa)), "total_ratio": round(sum(us) / sum(sa), 3),
                "share_correlation": round(corr(su, ss), 4), "largest_share_gap_points": round(abs(su[gap] - ss[gap]), 2), "largest_gap_municipio": names[gap],
                "san_juan_share": [round(su[names.index("San Juan")], 2), round(ss[names.index("San Juan")], 2)]}

    (HERE / "program_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in res["kept"].items():
        print(f"{k:16} kept FY{v[0]}-FY{v[1]}  start by (min municipios/max San Juan %): {res['sensitivity'][k]}")
    for k, v in res["ssa"].items():
        print(f"{k:40} r={v['share_correlation']}  largest gap {v['largest_share_gap_points']} pts ({v['largest_gap_municipio']})  totals ratio {v['total_ratio']}")
    print("coverage, last 5 years:", {fy: c["pct"] for fy, c in list(res["coverage"].items())[-5:]})


if __name__ == "__main__":
    main()
