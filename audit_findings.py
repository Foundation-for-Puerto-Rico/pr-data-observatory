"""Audit findings that repeat, for the Knowledge Area page "Federal funds returned and unused" (HANDOFF decision 110, step 3).

    python audit_findings.py              # build site/data/audit_findings.json (downloads only what is missing from cache/spending/fac/)
    python audit_findings.py --refresh    # read the Federal Audit Clearinghouse again
    python audit_findings.py --check      # rebuild from the cache and exit 1 when the published file is not what the cache gives (no network, nothing written)

Source: the Federal Audit Clearinghouse API (api.fac.gov), the source of the municipio audit series (HANDOFF decision 70). It needs a free
api.data.gov key in FAC_API_KEY; without it the public DEMO_KEY is used, which allows ten calls an hour. A full read is about seventeen calls, so
with the public key the script stops when the limit is reached and a rerun an hour later resumes from the cache.

What is read. Every single audit filed by a body in Puerto Rico from audit year FIRST_YEAR (general), the findings of those audits (findings) and
the award lines that carry a finding (federal_awards). No contact field is read, and no body is named in the file: bodies are counted by the kind
the Clearinghouse itself records (entity_type). One exception, by code and not by name (decision 110 (d), public bodies): the 78 municipio
governments, for the "My municipio" section of the Public spending page (municipio_governments, keyed by the municipio's Census code).

How a finding is counted. The API lists a finding once for each award line it touches. Here a finding is one (audit, reference number), and it is
repeated, a material weakness or has questioned costs when any of its lines says so. In the breakdown by program a finding counts once in each
program it touches, so the programs add up to more than the findings.

A repeated finding is one the auditor marks as also reported in the audit before. It is the closest open measure of whether a problem found one
year was corrected by the next. Questioned costs are a yes or no: the Clearinghouse publishes no amount.

output: site/data/audit_findings.json. See docs/unused-funds.md.
"""
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import requests

import economy_series
import federal_outlays
import housing_series as hs
import muni_names

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "spending" / "fac"
OUT = ROOT / "site" / "data" / "audit_findings.json"
API = "https://api.fac.gov"
FIRST_YEAR = 2019
DEADLINE_MONTHS = 9   # a single audit is due nine months after the fiscal year ends (2 CFR 200.512)
GENERAL = "report_id,audit_year,auditee_name,entity_type,fy_end_date,total_amount_expended,fac_accepted_date"   # the name is read to make the request stable, and is never published
FINDINGS = "report_id,award_reference,reference_number,is_repeat_finding,is_questioned_costs,is_material_weakness,is_significant_deficiency,is_modified_opinion,type_requirement"
AWARDS = "report_id,award_reference,federal_agency_prefix,federal_award_extension,federal_program_name,amount_expended,findings_count"
MAX_ADDRESS = 7200   # the service refuses longer addresses, so the audits are asked for in chunks
KINDS = {"state": "state", "local": "local", "non-profit": "nonprofit", "higher-ed": "higher_ed", "tribal": "other", "unknown": "other"}
TERMS = "US Government work, public domain (Federal Audit Clearinghouse)"
# the federal agency of an assistance listing, by the first two digits of the listing: the full names USAspending uses, so the page's sections agree
AGENCY = {**{pre: name for name, pre in federal_outlays.AGENCY.items()}, "42": "Library of Congress", "45": "National Endowment for the Humanities",
          "89": "National Archives and Records Administration", "90": "Election Assistance Commission"}
OTHER_AGENCY = "Other federal agencies"
log = hs.log


class RateLimit(RuntimeError):
    pass


def get(table, query):
    key = os.environ.get("FAC_API_KEY") or "DEMO_KEY"
    for attempt in range(4):
        try:
            r = requests.get(f"{API}/{table}?{query}", headers={**hs.UA, "X-Api-Key": key}, timeout=300)
        except requests.RequestException:
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            raise RateLimit("the Federal Audit Clearinghouse limit is reached" + ("" if key != "DEMO_KEY" else " (the public key allows ten calls an hour): run again in an hour, or set FAC_API_KEY"))
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Federal Audit Clearinghouse {table}: no answer")


def chunks(ids):
    """The audit ids in groups whose address stays under MAX_ADDRESS."""
    out, cur, size = [], [], 0
    for i in ids:
        if cur and size + len(i) + 1 > MAX_ADDRESS:
            out.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(i) + 1
    return out + ([cur] if cur else [])


def load(refresh=False, check=False):
    """(index, audits, findings, award lines with findings) from the cache, downloading what is missing unless check."""
    index_p = CACHE / "index.json"
    index = json.loads(index_p.read_text(encoding="utf-8")) if index_p.exists() else {}
    if check and not index.get("complete"):
        return None, None, None, None
    if refresh and not check:
        for p in CACHE.glob("*.json"):
            p.unlink()
        index = {}
    CACHE.mkdir(parents=True, exist_ok=True)
    gp = CACHE / "general.json"
    if not gp.exists():
        gp.write_text(json.dumps(get("general", f"auditee_state=eq.PR&audit_year=gte.{FIRST_YEAR}&limit=20000&select={GENERAL}")), encoding="utf-8")
        index = {"read": date.today().isoformat(), "complete": False}
        index_p.write_text(json.dumps(index), encoding="utf-8")
    audits = json.loads(gp.read_text(encoding="utf-8"))
    index.setdefault("read", date.today().isoformat())
    cp = CACHE / "chunks.json"
    if not cp.exists():
        cp.write_text(json.dumps(chunks(sorted({a["report_id"] for a in audits}))), encoding="utf-8")
    groups = json.loads(cp.read_text(encoding="utf-8"))
    found, lines = [], []
    for table, sel, extra, out in (("findings", FINDINGS, "", found), ("federal_awards", AWARDS, "&findings_count=gt.0", lines)):
        for k, ch in enumerate(groups):
            p = CACHE / f"{table}_{k}.json"
            if not p.exists():
                p.write_text(json.dumps(get(table, f"report_id=in.({','.join(ch)})&limit=20000&select={sel}{extra}")), encoding="utf-8")
                log(f"  Federal Audit Clearinghouse: {table} {k + 1} of {len(groups)}")
            out += json.loads(p.read_text(encoding="utf-8"))
    if not index.get("complete"):
        index["complete"] = True
        index_p.write_text(json.dumps(index), encoding="utf-8")
    return index, audits, found, lines


def months_late(a):
    """Months from the end of the audited fiscal year to the day the Clearinghouse accepted the audit, or None."""
    try:
        end, acc = date.fromisoformat(a["fy_end_date"]), date.fromisoformat(a["fac_accepted_date"])
    except (TypeError, ValueError):
        return None
    return (acc - end).days / 30.44


def findings_of(found):
    """{(audit, reference number): {repeat, material, questioned, lines}}: one finding however many award lines it touches."""
    out = {}
    for f in found:
        s = out.setdefault((f["report_id"], f["reference_number"]), {"repeat": False, "material": False, "questioned": False, "lines": set()})
        s["repeat"] |= f["is_repeat_finding"] == "Y"
        s["material"] |= f["is_material_weakness"] == "Y"
        s["questioned"] |= f["is_questioned_costs"] == "Y"
        s["lines"].add(f["award_reference"])
    return out


def tally(items):
    items = list(items)
    return [len(items), sum(s["repeat"] for s in items), sum(s["material"] for s in items), sum(s["questioned"] for s in items)]


def municipio_governments(audits, seen, last_year):
    """{municipio code: [audits filed, findings, repeated, latest audit year filed]} over the three audit years up to last_year, for the audits
    whose name is the municipio's own government (economy_series.fac_municipio: not its housing projects, consortia or other bodies). A municipio
    with no audit filed in those years has [0, 0, 0, latest year it ever filed or None]."""
    known = muni_names.municipios()
    by_name = {economy_series.fac_name_key(n): g for n, g in known.items()}
    ids = sorted(set(known.values()))
    years = [last_year - 2, last_year - 1, last_year]
    out = {g: [0, 0, 0, None] for g in ids}
    per_audit = {}
    for k, s in seen.items():
        e = per_audit.setdefault(k[0], [0, 0])
        e[0] += 1
        e[1] += 1 if s["repeat"] else 0
    done = set()
    for a in sorted(audits, key=lambda a: (a["fac_accepted_date"] or "", a["report_id"])):
        g = economy_series.fac_municipio(a["auditee_name"], by_name)
        if not g:
            continue
        y = int(a["audit_year"])
        out[g][3] = max(out[g][3] or 0, y)
        if y in years and (g, y) not in done:   # two audits of one municipio and year: the first accepted is counted
            done.add((g, y))
            f = per_audit.get(a["report_id"], [0, 0])
            out[g][0] += 1
            out[g][1] += f[0]
            out[g][2] += f[1]
    return years, out


def summarise(index, audits, found, lines):
    seen = findings_of(found)
    by_id = {a["report_id"]: a for a in audits}
    years = sorted({int(a["audit_year"]) for a in audits})
    line = {(x["report_id"], x["award_reference"]): x for x in lines}
    agency = lambda pre: AGENCY.get(pre, OTHER_AGENCY)
    by_year = []
    for y in years:
        ya = [a for a in audits if int(a["audit_year"]) == y]
        ids = {a["report_id"] for a in ya}
        fs = {k: s for k, s in seen.items() if k[0] in ids}
        late = [m for m in (months_late(a) for a in ya) if m is not None]
        by_year.append([y, len(ya), len({k[0] for k in fs}), *tally(fs.values()), sum(1 for m in late if m > DEADLINE_MONTHS), round(statistics.median(late), 1) if late else None,
                        round(sum(a["total_amount_expended"] or 0 for a in ya))])
    done = int(index["read"][:4]) - 2   # the latest audit year whose audits have mostly arrived; later years are left out of the tally by kind
    kinds = {}
    for k, s in seen.items():
        if int(by_id[k[0]]["audit_year"]) <= done:
            kinds.setdefault(KINDS.get(by_id[k[0]]["entity_type"], "other"), []).append(s)
    kind_audits = {}
    for a in audits:
        if int(a["audit_year"]) <= done:
            kind_audits[KINDS.get(a["entity_type"], "other")] = kind_audits.get(KINDS.get(a["entity_type"], "other"), 0) + 1
    progs, ags, names = {}, {}, {}
    for k, s in seen.items():
        touched, touched_ag = set(), set()
        for ref in sorted(s["lines"]):
            x = line.get((k[0], ref))
            if x:
                code = f"{x['federal_agency_prefix']}.{x['federal_award_extension']}"
                touched.add(code)
                touched_ag.add(x["federal_agency_prefix"])
                names.setdefault(code, " ".join((x["federal_program_name"] or "").split()))
        for c in touched:
            progs.setdefault(c, []).append(s)
        for name in {agency(p) for p in touched_ag}:
            ags.setdefault(name, []).append(s)
    nice = {r[0]: r[1] for f in ("spending_federal.json", "spending_outlays.json") if (ROOT / "site" / "data" / f).exists()
            for r in json.loads((ROOT / "site" / "data" / f).read_text(encoding="utf-8")).get("rows", []) if r[2] == 0 and r[1] != r[0]}
    title = lambda c: nice.get(c) or names.get(c, "").title()
    muni_years, muni = municipio_governments(audits, seen, int(index["read"][:4]) - 2)
    return {"municipio_governments": {"years": muni_years, "columns": ["audits filed", "findings", "repeated", "latest audit year filed"], "by_code": muni},
            "version": 1, "built": index["read"], "read": index["read"], "years": years,
            "source": "Federal Audit Clearinghouse (api.fac.gov): the single audits filed by bodies in Puerto Rico, their findings and the award lines with a finding",
            "terms": TERMS,
            "rule": {"finding": "one finding for each audit and reference number, however many award lines it touches", "repeat": "marked by the auditor as also reported in the audit before",
                     "deadline_months": DEADLINE_MONTHS, "programs": "a finding counts once in each program it touches, so programs add up to more than findings"},
            "columns": {"by_year": ["audit year", "audits", "audits with a finding", "findings", "repeated", "material weakness", "questioned costs", "audits accepted after the deadline", "median months to acceptance", "federal dollars spent"],
                        "tally": ["findings", "repeated", "material weakness", "questioned costs"]},
            "totals": {"audits": len(audits), "audits_with_findings": len({k[0] for k in seen}), "tally": tally(seen.values()), "programs": len(progs)},
            "by_year": by_year,
            "kinds_years": [years[0], done], "kinds": {k: {"audits": kind_audits.get(k, 0), "tally": tally(v)} for k, v in sorted(kinds.items())},
            "agencies": sorted(([name, *tally(v)] for name, v in ags.items()), key=lambda r: (-r[1], r[0])),
            "listings": sorted(([c, title(c), agency(c.split(".")[0]), *tally(v)] for c, v in progs.items()), key=lambda r: (-r[3], r[0]))}


def build(refresh=False, check=False):
    try:
        index, audits, found, lines = load(refresh, check)
    except RateLimit as e:
        log(f"  audit_findings: {e}; the published file is kept")
        return 0
    if index is None:
        log("  audit_findings: no complete cache, nothing to check")
        return 0
    text = json.dumps(summarise(index, audits, found, lines), ensure_ascii=False, separators=(",", ":")) + "\n"
    if check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            log("  audit_findings.json is NOT what the cache gives: run python audit_findings.py")
            return 1
        log("  audit_findings.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    d = json.loads(text)
    t = d["totals"]["tally"]
    log(f"  wrote audit_findings.json: {d['totals']['audits']} audits, {t[0]} findings, {t[1]} repeated ({100 * t[1] / t[0]:.0f}%), {d['totals']['programs']} programs")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    return build(refresh="--refresh" in argv, check="--check" in argv)


if __name__ == "__main__":
    sys.exit(main())
