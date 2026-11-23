"""Test for the proposal docs/unused-federal-funds-proposal-2026-11.md: do the single audits of Puerto Rico bodies say which findings repeat?

Reads the Federal Audit Clearinghouse API (the source of decision 70) for one audit year: the audits filed by Puerto Rico bodies, their findings
and the award lines that carry a finding. A finding is counted once per audit (report and reference number), though the API lists it once per
award line it touches. No contact field is read and no nonprofit is named in the output: bodies are grouped by kind.

Run from the repository root:  python docs/analysis/unused-funds-2026-11/fac_findings.py [year]
Needs FAC_API_KEY for a full run; the public DEMO_KEY allows about ten calls an hour, enough for one year from the cache.
"""
import collections
import json
import os
import pathlib
import re
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
CACHE = pathlib.Path(os.environ.get("TWIN_CACHE", "C:/t/cache")) / "spending" / "fac_findings"
URL = "https://api.fac.gov"
UA = {"User-Agent": "Mozilla/5.0 (compatible; pr-digital-twin research dashboard; +https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory)"}
GENERAL = "report_id,audit_year,auditee_name,entity_type,fy_end_date,total_amount_expended,fac_accepted_date"
FINDINGS = "report_id,award_reference,reference_number,is_repeat_finding,is_questioned_costs,is_material_weakness,is_significant_deficiency,is_modified_opinion,type_requirement"
AWARDS = "report_id,award_reference,federal_agency_prefix,federal_award_extension,federal_program_name,amount_expended,findings_count"


def get(path, params, name):
    p = CACHE / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    r = requests.get(f"{URL}/{path}", params=params, headers={**UA, "X-Api-Key": os.environ.get("FAC_API_KEY") or "DEMO_KEY"}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"FAC {path}: {r.status_code} {r.text[:200]}")
    CACHE.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(r.json()), encoding="utf-8")
    return r.json()


def kind(name):
    u = name.upper()
    if re.search(r"MUNICIP", u):
        return "municipio bodies"
    if re.search(r"COMMONWEALTH|DEPARTMENT|DEPARTAMENTO|AUTHORITY|AUTORIDAD|ADMINISTRATION|ADMINISTRACI|PUERTO RICO PUBLIC|UNIVERSITY OF PUERTO RICO|UNIVERSIDAD DE PUERTO RICO|OFFICE OF|OFICINA|GOVERNMENT|GOBIERNO|COMMISSION|COMISI|COUNCIL|CONSEJO", u):
        return "Commonwealth bodies and public corporations"
    return "nonprofits and other bodies"


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2023"
    audits = get("general", {"auditee_state": "eq.PR", "audit_year": f"eq.{year}", "limit": 20000, "select": GENERAL}, f"general_{year}")
    ids = sorted({a["report_id"] for a in audits})
    findings, awards = [], []
    for i in range(0, len(ids), 120):
        chunk = f"in.({','.join(ids[i:i + 120])})"
        findings += get("findings", {"report_id": chunk, "limit": 20000, "select": FINDINGS}, f"findings_{year}_{i}")
        awards += get("federal_awards", {"report_id": chunk, "findings_count": "gt.0", "limit": 20000, "select": AWARDS}, f"awards_{year}_{i}")
    by_id = {a["report_id"]: a for a in audits}
    seen = {}
    for f in findings:
        k = (f["report_id"], f["reference_number"])
        s = seen.setdefault(k, {"repeat": False, "questioned": False, "material": False, "listings": set()})
        s["repeat"] |= f["is_repeat_finding"] == "Y"
        s["questioned"] |= f["is_questioned_costs"] == "Y"
        s["material"] |= f["is_material_weakness"] == "Y"
        s["listings"].add((f["report_id"], f["award_reference"]))
    line = {(a["report_id"], a["award_reference"]): a for a in awards}

    def tally(keys):
        return {"findings": len(keys), "repeat": sum(seen[k]["repeat"] for k in keys), "questioned_costs": sum(seen[k]["questioned"] for k in keys),
                "material_weakness": sum(seen[k]["material"] for k in keys)}

    kinds = collections.defaultdict(list)
    for k in seen:
        kinds[kind(by_id[k[0]]["auditee_name"])].append(k)
    agencies = collections.defaultdict(set)
    programs = collections.defaultdict(set)
    for k, s in seen.items():
        for ref in s["listings"]:
            a = line.get(ref)
            if a:
                agencies[a["federal_agency_prefix"]].add(k)
                programs[(f"{a['federal_agency_prefix']}.{a['federal_award_extension']}", (a["federal_program_name"] or "").strip().upper())].add(k)
    late = []
    for a in audits:
        try:
            end, acc = time.strptime(a["fy_end_date"], "%Y-%m-%d"), time.strptime(a["fac_accepted_date"], "%Y-%m-%d")
            late.append((time.mktime(acc) - time.mktime(end)) / 86400 / 30.44)
        except (TypeError, ValueError):
            pass
    late.sort()
    with_findings = {k[0] for k in seen}
    listings = collections.defaultdict(set)
    for (n, _t), ks in programs.items():
        listings[n] |= ks
    names = {}
    for (n, t) in programs:
        names.setdefault(n, t)
    summary = {
        "read": time.strftime("%Y-%m-%d"), "audit_year": year, "audits": len(audits), "audits_with_findings": len(with_findings),
        "expended": round(sum(a["total_amount_expended"] or 0 for a in audits)), **tally(list(seen)),
        "by_kind": {k: dict(tally(v), audits=len({x[0] for x in v})) for k, v in sorted(kinds.items())},
        "by_federal_agency_prefix": sorted(({"prefix": p, **tally(list(v))} for p, v in agencies.items()), key=lambda x: -x["findings"])[:10],
        "listings_with_findings": len(listings),
        "by_listing": sorted(({"listing": n, "title": names[n], **tally(list(v))} for n, v in listings.items()), key=lambda x: -x["findings"])[:20],
        "months_to_acceptance": {"median": round(late[len(late) // 2], 1), "over_9_months": sum(m > 9 for m in late), "over_18_months": sum(m > 18 for m in late), "audits": len(late)},
    }
    (HERE / f"fac_summary_{year}.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
