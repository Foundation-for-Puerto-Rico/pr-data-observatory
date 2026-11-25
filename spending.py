"""Public spending (Gasto Público): the one record shape every spending source is normalized to, its checks, and the rules for adding records up.

    python spending.py --check cache/spending/records/<source>.csv   # check a normalized file against the schema
    python spending.py --tag                                          # write the spending tags into the public-money series of economy_series.json

Each source keeps its raw download untouched under cache/spending/<source>/ and writes its normalized records to cache/spending/records/<source>.csv
(cache only, never published). Published files are aggregates built from these records. The record fields, their allowed values and the allocation
tiers are explained in docs/spending.md (HANDOFF decision 73).

The function crosswalk (dictionary_src/spending_crosswalk.csv, reviewed on 2026-11-09, HANDOFF decision 92) puts each OGP concept, agency, program and object,
federal assistance listing, FEMA damage category and Contralor contract group into a function_category; `ogp_function()` and `cfda_function()` read it.

Rules this module enforces:
- One fiscal-year basis per total. Puerto Rico's fiscal year (July to June), the federal one (October to September) and calendar or declaration years are
  never added together (`add_up` refuses).
- One stage per total: proposed, approved, obligated, disbursed and actual dollars are different measures of the same money.
- No double counting across sources. Money that more than one source reports (FEMA Public Assistance in OpenFEMA, COR3 and USAspending) belongs to a
  dedup group; only the group's authoritative source is added up (DEDUP_GROUPS).
- Apportioned values are estimates of where operating spend lands, never added into direct totals (`add_up` refuses to mix tiers unless asked).
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "site" / "data"
CROSSWALK = ROOT / "dictionary_src" / "spending_crosswalk.csv"

FISCAL_YEAR_BASES = ["pr_jul_jun", "federal_oct_sep", "calendar", "declaration_year"]
LEVELS = ["state", "municipal", "federal_to_pr"]
STAGES = ["proposed", "approved", "obligated", "disbursed", "actual"]
FUND_ORIGINS = ["general", "federal", "special", "bond_other"]
CONCEPTS = ["payroll", "purchased_services", "transfers", "capex", "debt_service", "other"]
RECIPIENT_TYPES = ["agency", "municipality", "nonprofit", "private", "individual_aggregate", "mixed"]  # mixed: a federal total over recipients of several kinds
TIERS = ["direct", "apportioned", "island_wide"]
CONFIDENCE = ["high", "medium", "low"]
FUNCTIONS = ["education", "health", "public_safety", "transportation", "housing", "parks_recreation", "environment_natural_resources",
             "economic_development", "utilities_energy", "social_services", "debt_pensions", "general_government", "other"]

# name: (required, allowed values or a type check)
FIELDS = {
    "municipio_fips": (False, "fips"),            # empty = island-wide or not placed
    "fiscal_year": (True, "year"),
    "fiscal_year_basis": (True, FISCAL_YEAR_BASES),
    "level": (True, LEVELS),
    "source_system": (True, "id"),
    "stage": (True, STAGES),
    "fund_origin": (True, FUND_ORIGINS),
    "agency_or_entity": (True, "text"),
    "program": (False, "text"),
    "function_category": (True, FUNCTIONS),
    "concept_of_expense": (True, CONCEPTS),
    "recipient_type": (True, RECIPIENT_TYPES),
    "allocation_tier": (True, TIERS),
    "allocation_driver": (False, "text"),          # required for apportioned, empty otherwise
    "allocation_confidence": (True, CONFIDENCE),
    "amount_usd": (True, "number"),
    "population_basis": (False, "text"),           # e.g. "Census PEP V2025, 2024"; required when per_capita_usd is given
    "per_capita_usd": (False, "number"),
    "dedup_group": (False, "id"),
    "retrieved_at": (True, "date"),
    "source_url": (True, "url"),
    "terms_of_use": (True, "text"),
}

# Money more than one source reports. Only the authoritative source counts toward a total; the others are kept for comparison.
DEDUP_GROUPS = {
    "fema_pa": {"authoritative": "openfema", "also_in": ["cor3", "usaspending"], "note": "FEMA Public Assistance: OpenFEMA by applicant; COR3 and USAspending report the same obligations"},
    "fema_hma": {"authoritative": "openfema", "also_in": ["cor3", "usaspending"], "note": "FEMA Hazard Mitigation: OpenFEMA subapplications"},
    "cdbg_dr": {"authoritative": "vivienda_cdbgdr", "also_in": ["cor3", "usaspending", "fac"], "note": "HUD CDBG-DR/MIT: Vivienda's program figures; USAspending puts the prime award in San Juan, and its subawards by municipio (spending_cdbgdr.json) are part of the prime award, so neither is added to the other"},
    "cdbg": {"authoritative": "usaspending", "also_in": [], "note": "HUD yearly CDBG (14.218 entitlement, 14.228 state program): the prime grants are rows of spending_federal.json; the entitlement grants by municipio and the state program's subawards by municipio (spending_cdbg.json) are part of them, so neither is added to the other"},
    "ogp_federal": {"authoritative": "ogp", "also_in": ["usaspending"], "note": "Federal funds in the Commonwealth budget are also federal awards in USAspending"},
}

FIPS_RE = re.compile(r"^72\d{3}$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _bad(kind, v):
    """Why value v fails check kind, or None."""
    if isinstance(kind, list):
        return None if v in kind else f"'{v}' is not one of {kind}"
    if kind == "fips":
        return None if FIPS_RE.match(str(v)) else f"'{v}' is not a municipio id (72001-72153)"
    if kind == "year":
        return None if re.fullmatch(r"(19|20)\d{2}", str(v)) else f"'{v}' is not a year"
    if kind == "id":
        return None if ID_RE.match(str(v)) else f"'{v}' is not a lower-case id"
    if kind == "date":
        return None if DATE_RE.match(str(v)) else f"'{v}' is not YYYY-MM-DD"
    if kind == "url":
        return None if str(v).startswith(("https://", "http://")) else f"'{v}' is not a URL"
    if kind == "number":
        try:
            x = float(v)
        except (TypeError, ValueError):
            return f"'{v}' is not a number"
        return None if math.isfinite(x) else f"'{v}' is not finite"
    return None if str(v).strip() else "empty"


def validate(rec):
    """A list of problems with one record (a dict of strings or values); empty when it is valid."""
    P = [f"unknown field '{k}'" for k in rec if k not in FIELDS]
    for k, (required, kind) in FIELDS.items():
        v = rec.get(k)
        if v in (None, ""):
            if required:
                P.append(f"{k}: missing")
            continue
        why = _bad(kind, v)
        if why:
            P.append(f"{k}: {why}")
    tier = rec.get("allocation_tier")
    if tier == "apportioned" and not rec.get("allocation_driver"):
        P.append("allocation_driver: an apportioned record names its driver")
    if tier != "apportioned" and rec.get("allocation_driver"):
        P.append("allocation_driver: only apportioned records have a driver")
    if tier == "direct" and not rec.get("municipio_fips"):
        P.append("municipio_fips: a direct record carries its municipio")
    if tier == "island_wide" and rec.get("municipio_fips"):
        P.append("municipio_fips: an island-wide record has no municipio")
    if tier == "apportioned" and (rec.get("concept_of_expense") == "capex" or rec.get("level") == "federal_to_pr"):
        P.append("allocation_tier: only operating spend is apportioned, never capital spending or federal awards")
    if rec.get("per_capita_usd") not in (None, "") and not rec.get("population_basis"):
        P.append("population_basis: a per-resident figure names its population")
    g = rec.get("dedup_group")
    if g and g not in DEDUP_GROUPS:
        P.append(f"dedup_group: '{g}' is not in DEDUP_GROUPS")
    return P


def counts(rec):
    """Whether a record may be added into a total: not a copy of money another source is authoritative for."""
    g = rec.get("dedup_group")
    return not g or DEDUP_GROUPS[g]["authoritative"] == rec.get("source_system")


def add_up(records, by=("municipio_fips",), tiers=("direct", "island_wide")):
    """Totals of amount_usd by the fields in `by`. Refuses records of more than one fiscal-year basis or stage, leaves out copies (dedup groups)
    and, unless asked, apportioned estimates. Island-wide and unplaced money is kept under municipio_fips '' so nothing disappears."""
    recs = [r for r in records if r.get("allocation_tier") in tiers and counts(r)]
    for f in ("fiscal_year_basis", "stage"):
        seen = {r.get(f) for r in recs}
        if len(seen) > 1:
            raise ValueError(f"cannot add up records of more than one {f}: {sorted(map(str, seen))}")
    out = {}
    for r in recs:
        k = tuple(r.get(f) or "" for f in by)
        out[k] = out.get(k, 0.0) + float(r["amount_usd"])
    return out


def check_file(path):
    """Problems in a normalized CSV, as (row number, problem)."""
    P = []
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        missing = [k for k, (req, _) in FIELDS.items() if req and k not in (rd.fieldnames or [])]
        if missing:
            return [(1, f"columns missing: {missing}")]
        for i, r in enumerate(rd, start=2):
            P += [(i, p) for p in validate(r)]
    return P


# ── Tags for the public-money series already published in economy_series.json ─────────────────────────────────────────
# Each series says which money it measures in the record's terms. `part_of` names the series it is a part of (never add the two); `split` names
# the breakdown it belongs to: the parts of one split add up to the whole (tests/test_spending.py checks every year), a part with no split is only a subset.
# `in_totals: false` marks figures that are not public spending (counts, tax credit investments, project costs).
_FED = {"level": "federal_to_pr", "source_system": "usaspending", "fiscal_year_basis": "federal_oct_sep", "stage": "obligated", "fund_origin": "federal", "allocation_tier": "direct"}
_PA = {"level": "federal_to_pr", "source_system": "openfema", "fiscal_year_basis": "declaration_year", "stage": "obligated", "fund_origin": "federal", "allocation_tier": "direct",
       "dedup_group": "fema_pa", "function_category": "general_government"}
_HMA = {"level": "federal_to_pr", "source_system": "openfema", "fiscal_year_basis": "federal_oct_sep", "fund_origin": "federal", "allocation_tier": "direct",
        "dedup_group": "fema_hma", "function_category": "environment_natural_resources"}
_FAC = {"level": "federal_to_pr", "source_system": "fac", "fiscal_year_basis": "pr_jul_jun", "stage": "actual", "fund_origin": "federal", "allocation_tier": "direct",
        "recipient_type": "municipality"}
SERIES_TAGS = {
    "fed_awards_total": {**_FED},
    **{k: {**_FED, "part_of": "fed_awards_total", "split": "award_type"} for k in ("fed_contracts", "fed_grants", "fed_direct_payments", "fed_other")},
    "fed_loans": {**_FED, "part_of": "fed_awards_total", "split": "award_type", "note": "subsidy cost, not the amount lent"},
    **{k: {**_FED, "part_of": "fed_direct_payments", "recipient_type": "individual_aggregate", "function_category": "social_services"}
       for k in ("fed_prog_ss_retirement", "fed_prog_ss_disability", "fed_prog_ss_survivors", "fed_prog_va_compensation")},
    "fed_prog_pell": {**_FED, "part_of": "fed_awards_total", "function_category": "education"},
    "fed_prog_head_start": {**_FED, "part_of": "fed_grants", "function_category": "education"},
    "fed_prog_pbra": {**_FED, "part_of": "fed_awards_total", "function_category": "housing"},
    "fema_pa_obligated": {**_PA},
    "fema_pa_cat_a": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "environment_natural_resources"},   # debris: waste management (COFOG 05.1), decision 92
    "fema_pa_cat_b": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "public_safety"},
    "fema_pa_cat_c": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "transportation"},
    "fema_pa_cat_d": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "environment_natural_resources"},
    "fema_pa_cat_e": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "general_government"},
    "fema_pa_cat_f": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "utilities_energy"},
    "fema_pa_cat_g": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "parks_recreation"},
    "fema_pa_cat_z": {**_PA, "part_of": "fema_pa_obligated", "split": "damage_category", "function_category": "general_government"},
    "fema_pa_406_mitigation": {**_PA, "stage": "proposed", "in_totals": False, "note": "project cost, not the federal share"},
    "hma_approved_federal": {**_HMA, "stage": "approved"},
    "hma_obligated": {**_HMA, "stage": "obligated"},
    "hma_pending_federal": {**_HMA, "stage": "proposed"},
    "hma_projects": {**_HMA, "stage": "approved", "in_totals": False, "note": "count"},
    "fac_expended": {**_FAC},
    **{k: {**_FAC, "part_of": "fac_expended", "split": "channel"} for k in ("fac_direct", "fac_passthrough")},
    **{k: {**_FAC, "part_of": "fac_expended", "split": "agency"} for k in ("fac_hhs", "fac_hud", "fac_dhs", "fac_treasury", "fac_other")},
    "nmtc_qlici": {"level": "federal_to_pr", "source_system": "nmtc", "fiscal_year_basis": "calendar", "stage": "actual", "fund_origin": "federal",
                   "allocation_tier": "direct", "function_category": "economic_development", "in_totals": False, "note": "private investment made with a federal tax credit, not federal spending"},
    "nmtc_projects": {"level": "federal_to_pr", "source_system": "nmtc", "fiscal_year_basis": "calendar", "stage": "actual", "fund_origin": "federal",
                      "allocation_tier": "direct", "function_category": "economic_development", "in_totals": False, "note": "count"},
}
TAG_KEYS = {"level", "source_system", "fiscal_year_basis", "stage", "fund_origin", "allocation_tier", "dedup_group", "function_category", "recipient_type", "part_of", "split", "in_totals", "note"}


def check_tags(tags=SERIES_TAGS):
    """Problems in SERIES_TAGS (values outside the schema, a part_of that is not a tagged series)."""
    P = []
    allowed = {"level": LEVELS, "fiscal_year_basis": FISCAL_YEAR_BASES, "stage": STAGES, "fund_origin": FUND_ORIGINS, "allocation_tier": TIERS,
               "function_category": FUNCTIONS, "recipient_type": RECIPIENT_TYPES, "dedup_group": list(DEDUP_GROUPS)}
    for key, t in tags.items():
        P += [f"{key}: unknown tag '{k}'" for k in t if k not in TAG_KEYS]
        P += [f"{key}: {k} '{t[k]}' is not one of {v}" for k, v in allowed.items() if k in t and t[k] not in v]
        P += [f"{key}: missing {k}" for k in ("level", "source_system", "fiscal_year_basis", "stage", "fund_origin", "allocation_tier") if k not in t]
        if t.get("part_of") and t["part_of"] not in tags:
            P.append(f"{key}: part_of '{t['part_of']}' is not a tagged series")
        if t.get("part_of") and any(t.get(f) != tags[t["part_of"]].get(f) for f in ("fiscal_year_basis", "stage")):
            P.append(f"{key}: a part has the fiscal-year basis and stage of the series it is part of")
    return P


def tag_vars(vars_):
    """Write each tagged series' tags into its catalog entry as `spend` (in place); returns how many were tagged."""
    n = 0
    for v in vars_:
        t = SERIES_TAGS.get(v.get("key"))
        if t:
            v["spend"] = dict(t)
            n += 1
    return n


def tag_published(path=DATA / "economy_series.json"):
    doc = json.loads(path.read_text(encoding="utf-8"))
    n = tag_vars(doc["vars"])
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  tagged {n} public-money series in {path.name}")
    return n


# ── The function crosswalk ──────────────────────────────────────────────────────────────────────────────────────────
CROSSWALK_KINDS = ["ogp_concept", "ogp_agency", "ogp_program", "ogp_object", "cfda_agency", "cfda", "fema_category", "contralor_group"]
CROSSWALK_FIELDS = ["kind", "code", "name", "function_category", "concept_of_expense", "allocation", "confidence", "flag", "reason", "years"]
YEARS_RE = re.compile(r"^(|\d{4}-\d{4})$")   # blank: every year; "2026-2027": only the fiscal years a budget resolution confirms
ALLOCATION_RE = re.compile(r"^(|island_wide|no_driver|apportion:[a-z_]+|pending_driver:[a-z_]+)$")
FLAGS = ["", "review", "reviewed", "override"]   # reviewed: a row decided in the review of 2026-11-09 (HANDOFF decision 92)


def load_crosswalk(path=CROSSWALK):
    """{(kind, code): row} from the crosswalk CSV."""
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["kind"], r["code"]): r for r in csv.DictReader(f)}


def check_crosswalk(cw):
    """Problems in the crosswalk: unknown kinds or values, low confidence without a review flag, rows with no function where one is needed."""
    P = []
    for (kind, code), r in cw.items():
        k = f"{kind} {code}"
        if kind not in CROSSWALK_KINDS:
            P.append(f"{k}: unknown kind")
        if r["function_category"] and r["function_category"] not in FUNCTIONS:
            P.append(f"{k}: function '{r['function_category']}' is not one of FUNCTIONS")
        if r["concept_of_expense"] and r["concept_of_expense"] not in CONCEPTS:
            P.append(f"{k}: concept '{r['concept_of_expense']}' is not one of CONCEPTS")
        if not ALLOCATION_RE.match(r["allocation"]):
            P.append(f"{k}: allocation '{r['allocation']}' is not island_wide, no_driver, apportion:<driver> or pending_driver:<driver>")
        if r["confidence"] not in CONFIDENCE or r["flag"] not in FLAGS:
            P.append(f"{k}: confidence or flag outside {CONFIDENCE} / {FLAGS}")
        if r["confidence"] == "low" and r["flag"] not in ("review", "reviewed"):
            P.append(f"{k}: a low-confidence row is flagged for review")
        if kind in ("ogp_agency", "ogp_program", "ogp_object", "cfda_agency", "cfda", "fema_category") and not r["function_category"]:
            P.append(f"{k}: needs a function")
        if kind == "ogp_concept" and not r["concept_of_expense"]:
            P.append(f"{k}: needs a concept of expense")
        if not YEARS_RE.match(r.get("years") or ""):
            P.append(f"{k}: years '{r.get('years')}' is not blank or YYYY-YYYY")
        elif r.get("years") and kind != "ogp_object":
            P.append(f"{k}: only an object row is limited to some years")
        if kind == "ogp_object" and not re.match(r"^\d{3}-E\d{4}(@(general|special|federal))?$", code):
            P.append(f"{k}: an object row is agency-E-code, optionally @fund")
        if r["allocation"].startswith("apportion:") and kind != "ogp_agency":
            P.append(f"{k}: only an agency's operating spend is apportioned")
    return P


def in_years(r, year):
    """Whether a row applies to a fiscal year: a row with no years applies to all; a row limited to some years applies only when the year is given and in range."""
    ys = r.get("years") or ""
    if not ys:
        return True
    lo, hi = (int(x) for x in ys.split("-"))
    return year is not None and lo <= int(year) <= hi


def ogp_function(agency, program=None, concept=None, obj=None, cw=None, fund=None, year=None):
    """(function_category, concept_of_expense, allocation, confidence) of one OGP budget line, by its three-digit agency code, four-digit program
    number, three-digit concept number and object E-code (E7003: the code both years' data sheets share), with its fund and fiscal year. Order: a
    concept that overrides (debt service, pensions), then the object for that fund, the object, the program and the agency; an object row limited to
    some years (those a budget resolution confirms) is skipped in other years. Raises KeyError for an agency or concept the crosswalk does not list,
    so a new code stops the ingestor instead of landing in 'other'."""
    cw = cw or load_crosswalk()
    a = cw[("ogp_agency", agency)]
    c = cw[("ogp_concept", concept)] if concept else None
    if c and c["flag"] == "override":
        return c["function_category"], c["concept_of_expense"], c["allocation"], c["confidence"]
    objs = [cw.get(("ogp_object", f"{agency}-{obj}@{fund}")) if obj and fund else None, cw.get(("ogp_object", f"{agency}-{obj}")) if obj else None]
    objs = [r for r in objs if r and in_years(r, year)]
    for r in (objs[0] if objs else None, cw.get(("ogp_program", f"{agency}-{program}")) if program else None, a):
        if r:
            concept_ = r["concept_of_expense"] or (c["concept_of_expense"] if c else "")
            # a program or object keeps the agency's allocation only when it has the agency's function (parks inside DRNA do not take its driver)
            alloc = r["allocation"] or (a["allocation"] if r["function_category"] == a["function_category"] else "")
            if concept_ == "capex" and alloc.startswith("apportion:"):
                alloc = ""   # never apportion capital spending
            return r["function_category"], concept_, alloc, r["confidence"]


BASES = ["program", "object", "concept", "agency"]


def ogp_basis(agency, program=None, concept=None, obj=None, cw=None, fund=None, year=None):
    """Where ogp_function takes a line's function from, in the same order: "concept" (debt service and pensions override), "object" (an object
    row for the line's fund or for all funds, in its years), "program" or, when none of those has a row, "agency" (the agency's general function).
    HANDOFF decision 109, step 4."""
    cw = cw or load_crosswalk()
    c = cw.get(("ogp_concept", concept)) if concept else None
    if c and c["flag"] == "override":
        return "concept"
    objs = [cw.get(("ogp_object", f"{agency}-{obj}@{fund}")) if obj and fund else None, cw.get(("ogp_object", f"{agency}-{obj}")) if obj else None]
    if any(r and in_years(r, year) for r in objs):
        return "object"
    if program and cw.get(("ogp_program", f"{agency}-{program}")):
        return "program"
    return "agency"


def cfda_function(listing, cw=None):
    """(function_category, confidence) of a federal assistance listing ('84.010'): the listing's row, else its agency prefix's default (low confidence)."""
    cw = cw or load_crosswalk()
    r = cw.get(("cfda", listing))
    if r:
        return r["function_category"], r["confidence"]
    return cw[("cfda_agency", listing.split(".")[0])]["function_category"], "low"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--tag" in sys.argv:
        bad = check_tags()
        if bad:
            sys.exit("\n".join(bad))
        tag_published()
    elif "--check" in sys.argv:
        files = [a for a in sys.argv[1:] if not a.startswith("--")]
        probs = [(f, i, p) for f in files for i, p in check_file(f)]
        for f, i, p in probs[:200]:
            print(f"  {f}:{i}  {p}")
        print(f"spending: {len(probs)} problems in {len(files)} files")
        sys.exit(1 if probs else 0)
    else:
        print(__doc__)
