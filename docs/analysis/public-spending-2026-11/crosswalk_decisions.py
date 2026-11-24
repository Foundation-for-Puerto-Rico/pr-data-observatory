"""The review of the function crosswalk's 40 flagged rows (HANDOFF decision 92). The project lead on 2026-11-09: "Decide optimally about crosswalk"; Claude
decided each row against the UN Classification of the Functions of Government (COFOG), mapped to the crosswalk's functions, keeping one rule across
rows of the same kind. make_crosswalk.py applies these decisions before it writes dictionary_src/spending_crosswalk.csv, so a rebuild keeps them;
`python crosswalk_decisions.py` applies them to the CSV as it is (no download) and writes crosswalk_review.md and crosswalk_decisions.md.

Each decision: (kind, code) -> (function or None to keep the draft's, why). A decided row gets flag "reviewed" and the decision after its reason.
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CSV = REPO / "dictionary_src" / "spending_crosswalk.csv"
DATE, DECISION = "2026-11-09", 92
KEEP = None
CONTRALOR = "Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented"

DECISIONS = {
    ("ogp_agency", "025"): (KEEP, "Kept 'other' for what the budget resolutions do not name; the object rows give every named line its function"),
    ("cfda", "97.036"): (KEEP, "Kept 'other' in the federal totals: Public Assistance spans every damage category, and its money is counted by category from OpenFEMA (dedup group fema_pa), never added here"),
    ("ogp_agency", "017"): (KEEP, "Kept general_government: government-wide items (COFOG 01.3 general services); the object rows give the named lines theirs"),
    ("ogp_program", "024-1551"): (KEEP, "Kept 'other': lottery operations are a commercial activity (prizes and sales costs), not a function of government"),
    ("ogp_agency", "311"): (KEEP, "Kept 'other': the Gaming Commission mostly distributes gaming revenue to several functions"),
    ("ogp_agency", "310"): (KEEP, "Kept debt_pensions: COFIM pays municipal debt service (COFOG 01.7 public debt transactions)"),
    ("cfda", "93.600"): (KEEP, "Kept education: Head Start is pre-primary education (COFOG 09.1), whoever runs it"),
    ("cfda", "14.228"): (KEEP, "Kept housing: CDBG is housing and community development (COFOG 06), its largest use in Puerto Rico"),
    ("ogp_program", "070-1138"): (KEEP, "Kept health: medical care is health (COFOG 07) inside any agency"),
    ("ogp_program", "024-1550"): (KEEP, "Kept 'other': lottery operations, as 024-1551"),
    ("ogp_agency", "276"): ("utilities_energy", "Changed to utilities_energy: the Authority's budget is the energy system's operation and generation contracts (COFOG 04.3 fuel and energy)"),
    ("ogp_agency", "162"): (KEEP, "Kept general_government: the Public Buildings Authority rents and maintains buildings for many agencies (COFOG 01.3); the schools' share is not in the sheets"),
    ("cfda", "66.458"): (KEEP, "Kept environment_natural_resources: wastewater is environmental protection (COFOG 05.2)"),
    ("ogp_program", "016-2076"): (KEEP, "Kept utilities_energy, whose label includes communications (COFOG 04.6)"),
    ("cfda", "66.468"): (KEEP, "Kept utilities_energy: water supply (COFOG 06.3) sits with the utilities, as the Aqueduct and Sewer Authority does"),
    ("cfda", "32.008"): (KEEP, "Kept utilities_energy: a subsidy is classed by what it buys, here communications (COFOG 04.6)"),
    ("cfda", "11.035"): (KEEP, "Kept utilities_energy: broadband is communications (COFOG 04.6)"),
    ("ogp_program", "162-1586"): (KEEP, "Kept general_government, as its agency 162"),
    ("cfda", "32.003"): (KEEP, "Kept utilities_energy: a phone subsidy, as 32.008"),
    ("ogp_program", "045-1224"): ("health", "Changed to health: ambulance and paramedical services are health (COFOG 07.2), whatever department runs them"),
    ("ogp_agency", "161"): (KEEP, "Kept economic_development: the Authority's own budget is its administration ($4 M); the works it finances are in other agencies' lines"),
    ("cfda", "21.027"): (KEEP, "Kept general_government: general fiscal transfers (COFOG 01.8)"),
    ("contralor_group", "1"): (KEEP, CONTRALOR),
    ("contralor_group", "16"): (KEEP, CONTRALOR),
    ("contralor_group", "17"): (KEEP, CONTRALOR),
    ("contralor_group", "2"): (KEEP, CONTRALOR),
    ("contralor_group", "23"): (KEEP, CONTRALOR),
    ("contralor_group", "8"): (KEEP, CONTRALOR),
    ("fema_category", "A"): ("environment_natural_resources", "Changed to environment_natural_resources: debris removal is waste management (COFOG 05.1)"),
    ("fema_category", "E"): (KEEP, "Kept general_government: the category mixes schools, hospitals and city halls; the applicant's own function applies where it is known"),
    ("ogp_concept", "011"): (KEEP, "Kept capex: equipment purchases are capital outlay in OGP's structure, and capex is never apportioned"),
    ("ogp_concept", "081"): (KEEP, "Kept 'other': a lump-sum appropriation's concept is what its object of expense says"),
    ("ogp_concept", "082"): (KEEP, "Kept transfers: the state match moves money into federal programs"),
    ("ogp_concept", "089"): (KEEP, "Kept 'other': prior-year bills are not bond debt service"),
    ("ogp_object", "017-E9761"): (KEEP, "Kept 'other' and transfers: a transfer within one fund; OGP's totals include it, so it stays and is labelled"),
    ("ogp_object", "025-E6170"): (KEEP, "Kept 'other': grants to 15 named entities of several functions"),
    ("ogp_object", "025-E6390"): (KEEP, "Kept 'other' for the years and funds no budget resolution names"),
    ("ogp_object", "025-E9760"): (KEEP, "Kept 'other' for FY2025, which mixes transit transfers and rum cover-over payments; FY2026 and FY2027 keep transportation"),
    ("ogp_object", "025-E9761"): (KEEP, "Kept 'other': compulsory auto insurance premiums passed to the insurers, a pass-through"),
    ("cfda", "21.019"): (KEEP, "Kept general_government: general fiscal relief (COFOG 01.8)"),
}


def apply(rows):
    """Apply the decisions to crosswalk rows (dicts, in place); returns the decided rows. A decision for a row that is not there stops."""
    at = {(r["kind"], r["code"]): r for r in rows}
    missing = [k for k in DECISIONS if k not in at]
    if missing:
        raise SystemExit(f"decisions for rows that are not in the crosswalk: {missing}")
    out = []
    for k, (fn, why) in DECISIONS.items():
        r = at[k]
        if r["flag"] == "reviewed":
            out.append(r)
            continue
        if fn is not None:
            r["function_category"] = fn
            if r["confidence"] == "low":
                r["confidence"] = "medium"
        r["flag"] = "reviewed"
        r["reason"] = (r["reason"] + " " if r["reason"] else "") + f"Reviewed {DATE} (decision {DECISION}): {why}."
        out.append(r)
    return out


def write_lists(rows):
    left = [r for r in rows if r["flag"] == "review"]
    nl = "\n"
    review = ["# Function crosswalk: rows for review", "",
              f"Generated from `dictionary_src/spending_crosswalk.csv`. The 40 rows flagged in the draft were decided on {DATE} (HANDOFF decision {DECISION}); "
              "see `crosswalk_decisions.md`. A row flagged `review` later appears here.", "",
              "| # | Kind | Code | Name | Function | Concept | Why it needs a look |", "|---|---|---|---|---|---|---|"]
    review += [f"| {i} | {r['kind']} | {r['code']} | {r['name']} | {r['function_category']} | {r['concept_of_expense']} | {r['reason']} |" for i, r in enumerate(left, 1)]
    (HERE / "crosswalk_review.md").write_text(nl.join(review) + nl, encoding="utf-8", newline=nl)
    done = [r for r in rows if r["flag"] == "reviewed"]
    dec = ["# Function crosswalk: the review decisions", "",
           f"the project lead asked on {DATE} for the flagged rows to be decided (HANDOFF decision {DECISION}). Each row was decided against the UN Classification of the Functions of Government (COFOG),",
           "mapped to the crosswalk's functions, with one rule for rows of the same kind. Three functions changed; the other rows keep the draft's choice, now reviewed.", "",
           "| Kind | Code | Name | Function | Decision |", "|---|---|---|---|---|"]
    dec += [f"| {r['kind']} | {r['code']} | {r['name']} | {r['function_category'] or '(from the entity)'} | {DECISIONS[(r['kind'], r['code'])][1]} |" for r in done]
    (HERE / "crosswalk_decisions.md").write_text(nl.join(dec) + nl, encoding="utf-8", newline=nl)
    return left, done


def main():
    with open(CSV, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        fields, rows = rd.fieldnames, list(rd)
    decided = apply(rows)
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    left, done = write_lists(rows)
    changed = [k for k, (fn, _) in DECISIONS.items() if fn is not None]
    print(f"{len(decided)} rows decided ({len(changed)} functions changed: {changed}); {len(left)} rows still flagged for review")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
