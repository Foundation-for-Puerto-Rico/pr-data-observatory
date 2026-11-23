"""The checks behind the Federal Audit Clearinghouse series (Public money v2, step 3): how audit names were matched to the 78 municipio governments,
which municipios filed each year, how the money splits by agency and between direct and pass-through awards, and how the municipios' Head Start and
FEMA Public Assistance spending compares with what USAspending and OpenFEMA show for the same programs.

    python docs/analysis/public-money-v2-2026-10/fac_check.py          # writes fac_check.json beside this file

Reads the FAC cache that `economy_series.py --fac` writes (cache/economy/fac) and site/data/economy_series.json. Makes no API call.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import economy_series as es  # noqa: E402
import housing_series as hs  # noqa: E402

CACHE = ROOT / "cache" / "economy" / "fac"


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5


def main():
    names, geoids = hs.municipalities()
    general = json.loads((CACHE / "general_pr.json").read_text(encoding="utf-8"))
    audits = es.fac_audits(names, geoids)
    lines = {}
    for p in CACHE.glob("awards_*.json"):
        lines.update(json.loads(p.read_text(encoding="utf-8")))
    by_name = {es.fac_name_key(n): g for n, g in zip(names, geoids)}
    kept = {a["report_id"] for a in audits.values()}
    name = dict(zip(geoids, names))
    left_out = sorted({r["auditee_name"] for r in general if r["report_id"] not in kept and "MUNICIP" in r["auditee_name"].upper()})
    res = {"audits_in_pr": len(general), "municipio_audits": len(audits),
           "matched_by_ein": sorted({r["auditee_name"] for r in general if r["report_id"] in kept and not es.fac_municipio(r["auditee_name"], by_name)}),
           # A count, not the names: several are housing projects for older adults that the places privacy rule withholds by name (2026-11-05). The names are printed.
           "left_out_with_municipio": len(left_out),
           "filed": {}, "not_filed": {}, "totals_million": {}, "agency_pct": {}, "direct_pct": None, "loan_pct": None, "lines_vs_audit_totals": 0, "comparisons": {}}
    for fy in sorted({y for _, y in audits}):
        res["filed"][fy] = sum(1 for _, y in audits if y == fy)
        res["not_filed"][fy] = [name[g] for g in geoids if (g, fy) not in audits]
        res["totals_million"][fy] = round(sum(float(a["total_amount_expended"]) for (_, y), a in audits.items() if y == fy) / 1e6, 1)
    agency, direct, loan, tot = Counter(), Counter(), 0, 0
    for (g, fy), a in audits.items():
        s = 0
        for x in lines[a["report_id"]]:
            v = x["amount_expended"] or 0
            s += v
            tot += v
            agency[es.FAC_AGENCIES.get(x["federal_agency_prefix"], "other")] += v
            direct[x["is_direct"]] += v
            loan += v if x["is_loan"] == "Y" else 0
        res["lines_vs_audit_totals"] += abs(s - float(a["total_amount_expended"])) > 1
    res["agency_pct"] = {k: round(v / tot * 100, 1) for k, v in agency.most_common()}
    res["direct_pct"], res["loan_pct"] = round(direct["Y"] / tot * 100, 1), round(loan / tot * 100, 1)

    econ = json.loads((ROOT / "site" / "data" / "economy_series.json").read_text(encoding="utf-8"))
    V, ids = {v["key"]: v for v in econ["vars"]}, econ["geo"]["ids"][:78]
    # Head Start: what the municipio governments spent (municipal fiscal years 2019-2024) against USAspending's obligations to every recipient placed in
    # the municipio (federal fiscal years 2019-2024). Different recipients and years, so the totals differ; the pattern should not.
    hsf = [sum(v for (gg, fy), a in audits.items() if gg == g and 2019 <= fy <= 2024 for v in [sum(x["amount_expended"] for x in lines[a["report_id"]] if x["federal_agency_prefix"] == "93" and x["federal_award_extension"] == "600")]) for g in ids]
    hsu = [sum((V["fed_prog_head_start"]["years"].get(str(fy)) or [0] * 79)[i] or 0 for fy in range(2019, 2025)) for i in range(78)]
    res["comparisons"]["head_start_fy2019_2024"] = {"fac_municipio_governments_million": round(sum(hsf) / 1e6, 1), "usaspending_all_recipients_million": round(sum(hsu) / 1e6, 1),
                                                    "correlation": round(corr(hsf, hsu), 3), "municipios_with_money": [sum(1 for x in hsf if x > 0), sum(1 for x in hsu if x > 0)]}
    # FEMA Public Assistance (97.036): spent by each municipio government in all its audits against the federal share OpenFEMA shows obligated to it as applicant
    paf = [sum(v for (gg, _), a in audits.items() if gg == g for v in [sum(x["amount_expended"] for x in lines[a["report_id"]] if x["federal_agency_prefix"] == "97" and x["federal_award_extension"] == "036")]) for g in ids]
    pao = [sum(V["fema_pa_obligated"]["years"][y][i] or 0 for y in V["fema_pa_obligated"]["years"]) for i in range(78)]
    ratio = sorted(a / b for a, b in zip(paf, pao) if b > 0)
    res["comparisons"]["fema_pa_all_years"] = {"fac_spent_million": round(sum(paf) / 1e6, 1), "openfema_obligated_million": round(sum(pao) / 1e6, 1), "correlation": round(corr(paf, pao), 3),
                                               "spent_over_obligated": {"p10": round(ratio[len(ratio) // 10], 2), "median": round(ratio[len(ratio) // 2], 2), "p90": round(ratio[9 * len(ratio) // 10], 2)}}
    (HERE / "fac_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False)[:3000])
    print("left out (names with a municipio, not written to fac_check.json):", *left_out, sep="\n  ")


if __name__ == "__main__":
    main()
