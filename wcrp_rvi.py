"""WCRP Risk and Vulnerability Indicators (RVI) by barrio: the original, as published, and a rebuild with the same method on current data.

    python wcrp_rvi.py              harvest the original (cached in cache/wcrp_rvi), rebuild, write site/data/wcrp_rvi_barrio.json and wcrp_rvi_inputs.json
    python wcrp_rvi.py --refresh    harvest the public ArcGIS services again (the original was last edited in March 2022; a new edit would show here)
    python wcrp_rvi.py --check      rebuild from the cache and say whether the published files are current

The conditions refresh (refresh/sources.json, unit conditions) runs this script after conditions.py, so a new conditions_barrio.json rebuilds both
files in the same pull request, which a person reviews (docs/wcrp.md, "Refresh with the local conditions").

The original. Hunter College built the RVI for Foundation for Puerto Rico's Whole Community Resilience Planning (WCRP) program, which FPR runs in
collaboration with the Puerto Rico Department of Housing with HUD CDBG-DR funds (white paper, December 2021; services published March 2022). Inputs are mostly ACS 2015-2019.
It is read live from the public ArcGIS REST services of the PlanningCDBG account: All_Indicator (the six area indices and the overall index of each
barrio, with their ranks) and Master_Data_Table_Update (the barrio input values behind the dashboard). Nothing is recomputed: the index values are
published as the services give them. The services state no license (licenseInfo and accessInformation are empty), so the files keep the license
class 'unstated' and carry a license review, cleared on 2026-10-19 (FPR confirmed that its approval covers republishing the original on the observatory;
others should ask PRDOH and FPR before re-use; HANDOFF decision 54), and a compliance review that records FPR's approval of 2026-10-19
(dictionary_src/datasets.json; HANDOFF decision 51); the page keeps an "In review" marker.

The rebuild follows the white paper's method on the observatory's current data: the survey (ACS 2020-2024) and, for the inputs the survey does not hold,
the local conditions of conditions.py (conditions_barrio.json: EPA sites, impaired waters and non-attainment areas, HUD CHAS severe housing problems,
TIGER street intersections, drive time to a general hospital; docs/conditions.md), each in its own source's vintage:
  1. each input becomes a percentile among the barrios that have a value: the share of those barrios with a strictly lower value (0 to 1, higher is more
     vulnerable); this is the definition that reproduces the original from its own published inputs (see `reproduce`);
  2. within an area (or a sub-indicator), the percentiles are summed and the sum is ranked again; a barrio that lacks an input gets the sum of the inputs it
     has, scaled up to the full count (the white paper's rule for Education, where the no-diploma percentile is doubled, applied to every area);
  3. the overall index is the percentile of the sum of the six area percentiles (equal weights);
  4. the rank is the fifth of the index: 1 = 0 to 0.20 (low) ... 5 = above 0.80 (high), as in the original (rank = ceil(5 x index), at least 1).
Inputs the observatory has no current barrio source for are listed in MISSING and left out; the area is then built from what remains, and the page
and the dictionary say so. No input is filled with a proxy. Where a current source defines an input differently from the original (ATTAINS units that are
watersheds, LMOP landfills without open dumps, active RMP facilities only), REBUILD_NOTE says how, and the page shows it.
"""
import bisect
import json
import math
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CACHE = ROOT / "cache" / "wcrp_rvi"
OUT = DATA / "wcrp_rvi_barrio.json"
OUT_INPUTS = DATA / "wcrp_rvi_inputs.json"
SERVICES = "https://services5.arcgis.com/phhDE88zbaXQ3N1m/arcgis/rest/services"
ALL_INDICATOR = "All_Indicator"
MASTER = "Master_Data_Table_Update"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico)"}

AREAS = ["overall", "econ", "edu", "envir", "health", "housing", "infra"]
AREA_LABEL = {"overall": "Overall", "econ": "Economy", "edu": "Education", "envir": "Environment", "health": "Health", "housing": "Housing", "infra": "Infrastructure"}
# All_Indicator: the index of each area and its rank, as the service names them (the names are cut at ten characters)
FIELD = {"overall": ("OVERALL", "OVERA_RANK"), "econ": ("ECON", "ECON_RANK"), "edu": ("EDU", "EDU_RANK"), "envir": ("ENVIR", "ENVIR_RANK"),
         "health": ("HEALTH", "HEALTH_RAN"), "housing": ("HOUSING", "HOUSING_RA"), "infra": ("INFRA", "INFRA_RANK")}
# Master_Data_Table_Update: the barrio columns of each indicator's rows (the municipio and Puerto Rico columns are left out: several are mislabeled, see KNOWN_ERRORS)
MASTER_INDICATOR = {"econ": "ECON", "edu": "EDU", "envir": "ENVIR", "health": "HEALTH", "housing": "Housing", "infra": "INFRA", "overall": "OVERALL"}
ORIGINAL_INPUTS = [   # (key, area, field in the Master table, label, unit); labels from the dashboard's barrio list, checked against the white paper
    ("o_public_assist_pct", "econ", "Var1", "Population on public assistance (%)", "%"),
    ("o_per_capita_income", "econ", "Var2", "Per capita income ($; shown in the table, not an input of the index per the white paper)", "$"),
    ("o_poverty_pct", "econ", "Var3", "Population below the poverty line (%)", "%"),
    ("o_unemployed_pct", "econ", "Va4", "Unemployed (%)", "%"),
    ("o_not_enrolled_3_24_pct", "edu", "Var1", "People aged 3 to 24 not enrolled in school (%)", "%"),
    ("o_no_diploma_pct", "edu", "Var2", "Adults 25+ without a high school diploma (%)", "%"),
    ("o_nonattainment", "envir", "Var1", "In a sulfur dioxide or lead non-attainment area (1 = yes)", ""),
    ("o_impaired_water", "envir", "Var2", "Impaired water body, EPA 303(d) (1 = yes)", ""),
    ("o_rmp_sites", "envir", "Var3", "Risk Management Plan sites (count)", ""),
    ("o_dumps", "envir", "Va4", "Municipal landfill or open dump (1 = yes)", ""),
    ("o_solid_waste", "envir", "Var5", "Solid waste facility (1 = yes)", ""),
    ("o_npl_sites", "envir", "Var6", "Superfund (National Priorities List) sites (count)", ""),
    ("o_tri_facilities", "envir", "Var7", "Toxics Release Inventory facilities (count)", ""),
    ("o_lead_paint_pct", "envir", "Var8", "Lead-paint indicator: homes built before 1960 (%)", "%"),
    ("o_disability_pct", "health", "Var1", "People with a disability (%)", "%"),
    ("o_uninsured_pct", "health", "Var2", "People without health insurance (%)", "%"),
    ("o_hospital_min", "health", "Var3", "Travel time to the nearest general hospital (minutes)", "min"),
    ("o_vacancy_pct", "housing", "Var1", "Vacant housing units (%)", "%"),
    ("o_built_pre1990_pct", "housing", "Var2", "Homes built before 1990 (%)", "%"),
    ("o_severe_problems_pct", "housing", "Var3", "Severe housing problems, HUD CHAS definition (%)", "%"),
    ("o_intersections_sqmi", "infra", "Var1", "Street intersections per square mile (TIGER 2020)", ""),
    ("o_no_vehicle_pct", "infra", "Var2", "Households with no vehicle (%)", "%"),
    ("o_no_computer_pct", "infra", "Var3", "Households without a computer (%)", "%"),
    ("o_no_internet_pct", "infra", "Va4", "Households without internet (%)", "%"),
    ("o_no_broadband_pct", "infra", "Var5", "Households without broadband (%)", "%"),
]
# the 14 barrios with no residents or structures (white paper, appendix B): no value in the original
# the 21 barrios with nobody aged 3 to 24 (appendix C): left out of the enrollment percentile, the no-diploma percentile doubled
APPENDIX_C = ("7201114978 7210719364 7214145594 7203561676 7203560644 7203537854 7207338198 7214170018 7215301777 7215372684 7200755527 "
              "7206707453 7209749378 7208366621 7211122460 7210924481 7203522761 7204929426 7203541638 7214517988 7209308872").split()

# The rebuild's inputs: (key, area, sub-indicator, label, how it is read). "acs_barrio:KEY" is a variable of site/data/acs_barrio.json; "conditions_barrio:..." is read
# from site/data/conditions_barrio.json (conditions.py); a table is read by acs_small.py. Housing is one flat group: that is what gives back the original (see `reproduce`).
REBUILD_INPUTS = [
    ("poverty_pct", "econ", None, "People below the poverty line (%)", "acs_barrio:poverty_pct"),
    ("public_assist_hh_pct", "econ", None, "Households with cash public assistance income (%)", "B19057: 002 / 001"),
    ("unemployment_rate_pct", "econ", None, "Unemployment rate (%)", "acs_barrio:unemployment_rate_pct"),
    ("not_enrolled_3_24_pct", "edu", None, "People aged 3 to 24 not enrolled in school (%)", "B14003: not enrolled aged 3 to 24 / everyone aged 3 to 24"),
    ("acs_no_hs_pct", "edu", None, "Adults 25+ without a high school diploma (%)", "acs_barrio:acs_no_hs_pct"),
    ("built_pre1960_pct", "envir", None, "Lead-paint indicator: homes built before 1960 (%)", "B25034: 009 + 010 + 011 / 001"),
    ("nonattainment_flag", "envir", None, "In a sulfur dioxide or lead non-attainment area (1 = yes)", "conditions_barrio: epa_naa_so2_pct > 0 or epa_naa_lead_pct > 0"),
    ("impaired_water_flag", "envir", None, "In a 303(d)-listed water assessment unit, EPA ATTAINS (1 = yes)", "conditions_barrio: epa_303d_pct > 0"),
    ("rmp_sites", "envir", None, "Risk Management Plan facilities, active (count)", "conditions_barrio:epa_rmp"),
    ("landfill_flag", "envir", None, "Municipal solid waste landfill, open or closed, EPA LMOP (1 = yes)", "conditions_barrio: epa_landfills > 0"),
    ("npl_sites", "envir", None, "Superfund (National Priorities List) sites (count)", "conditions_barrio:epa_npl"),
    ("tri_facilities", "envir", None, "Toxics Release Inventory facilities (count)", "conditions_barrio:epa_tri"),
    ("acs_disability_pct", "health", None, "People with a disability (%)", "acs_barrio:acs_disability_pct"),
    ("acs_uninsured_pct", "health", None, "People without health insurance (%)", "acs_barrio:acs_uninsured_pct"),
    ("hospital_drive_min", "health", None, "Drive time to the nearest general hospital (minutes, estimate)", "conditions_barrio:hosp_drive_min"),
    ("vacancy_pct", "housing", None, "Vacant housing units (%)", "acs_barrio:vacancy_pct"),
    ("built_pre1990_pct", "housing", None, "Homes built before 1990 (%)", "B25034: 006 to 011 / 001"),
    ("severe_problems_pct", "housing", None, "Households with severe housing problems, CHAS 2016–2020 (%, estimate)", "conditions_barrio:chas_severe_pct"),
    ("no_computer_pct", "infra", "telecom", "Households without a computer (%)", "B28003: 006 / 001"),
    ("no_internet_pct", "infra", "telecom", "Households with no internet access (%)", "acs_barrio:no_internet_pct"),
    ("no_broadband_pct", "infra", "telecom", "Households without broadband (%)", "B28002: (001 - 004) / 001"),
    ("no_vehicle_hh_pct", "infra", "transport", "Households with no vehicle (%)", "acs_barrio:no_vehicle_hh_pct"),
    ("intersection_density", "infra", "transport", "Street intersections per square mile, TIGER/Line 2026 (fewer is more vulnerable)", "conditions_barrio:street_intersection_density"),
]
REBUILD_UNIT = {"nonattainment_flag": "", "impaired_water_flag": "", "rmp_sites": "", "landfill_flag": "", "npl_sites": "", "tri_facilities": "", "hospital_drive_min": "min", "intersection_density": ""}   # the rest are shares (%)
FEWER_IS_WORSE = {"intersection_density"}   # an input whose lower values are the more vulnerable: its percentile is taken on the negated value, as the original's
# How a current source defines an input differently from the original: shown under the inputs table (with counts from `checks`) and in the dictionary
REBUILD_NOTE = {
    "impaired_water_flag": "Puerto Rico maps the assessment units of its rivers as the land that drains to each assessed reach, so a listed unit covers a watershed and far more barrios touch one than in the original, which does not say how it drew the waters. The input separates barrios less than the original's.",
    "landfill_flag": "EPA's Landfill Methane Outreach Program lists municipal solid waste landfills only (open or closed), not open dumps; the original's landfill or open dump layer was supplied by FPR.",
    "rmp_sites": "Only the facilities the Facility Registry Service marks active are counted, far fewer than the original counted; it does not say which it took.",
    "nonattainment_flag": "Areas still in non-attainment in the EPA Green Book: San Juan and Guayama-Salinas for sulfur dioxide, Arecibo for lead.",
    "hospital_drive_min": "The observatory's estimate along OpenStreetMap roads at free-flow speeds, from each barrio's population-weighted point to the nearest general hospital with an emergency department (CMS list); 0 where the barrio holds one. Vieques, Culebra and Isla de Mona have no road to a hospital and no value: their health level uses the other two inputs.",
    "severe_problems_pct": "CHAS is published for census tracts, not barrios: the barrio value is an estimate, the tract counts spread by 2020 housing units. 2016–2020 is the newest window a script may read.",
    "intersection_density": "Intersections where three or more street edges meet (TIGER/Line 2026; no highways, ramps or paths) over land area. The original counted TIGER 2020 roads in a way it does not describe, so only the order of the barrios compares, not the values.",
}
MISSING = [   # inputs of the original that the rebuild leaves out, and why
    ("envir", None, "Solid waste facilities (transfer stations, recycling, open dumps)", "No public source states terms: EPA lists municipal landfills only, and the only list of open dumps found (DRNA, 2014) states no license."),
]
REBUILD_TABLES = ("B19057", "B25034", "B28003", "B28002", "B14003")
B14003_AGES_3_24 = (range(4, 10), range(13, 19), range(22, 28), range(32, 38), range(41, 47), range(50, 56))   # public, private, not enrolled; male then female
B14003_NOT_ENROLLED = (range(22, 28), range(50, 56))
STRUCTURE = {   # how each area is put together: a list of sub-indicators, each a list of input areas' keys (rebuild); see build_area
    "econ": [None], "edu": [None], "envir": [None], "health": [None], "housing": [None], "infra": ["telecom", "transport"],
}
CONDITIONS = DATA / "conditions_barrio.json"
# Context, not inputs: the white paper's index has no age input (its Appendix A lists "vulnerable populations (children, elderly, disabilities)" among the
# economy candidates, not among the inputs chosen), but the original dashboard showed each barrio's age groups beside the index (All_Indicator UNDER17, OVER65
# and the age bands, ACS 2015-2019: its "vulnerable population"). The rebuild shows the current survey's shares of the same groups, with their margins of
# error, in the pop-up; they change no rank. (key in wcrp_rvi_inputs.json, label, variable of acs_barrio.json, built by small_area.py from B01001)
CONTEXT = [
    ("age_under18_pct", "Residents under 18 (%, survey estimate)", "acs_under18_pct"),
    ("age_18to44_pct", "Residents aged 18 to 44 (%, survey estimate)", "acs_age18to44_pct"),
    ("age_45to64_pct", "Residents aged 45 to 64 (%, survey estimate)", "acs_age45to64_pct"),
    ("age_65plus_pct", "Residents aged 65 and over (%, survey estimate)", "acs_age65plus_pct"),
]
CONTEXT_NOTE = ("Not an input of the index. The white paper's method has no age input; the original dashboard showed each barrio's age groups (under 17, over 65 "
                "and age bands, ACS 2015-2019) beside the index as its vulnerable population. The updated version shows the same groups from the current survey; they change no level.")
# Hazards are context too: the white paper keeps flooding, landslides and earthquakes out of the index, in separate layers. The page reads the observatory's
# landslide susceptibility by barrio (landslide_barrio.json, landslide.py) on the first pop-up; nothing of it is copied into these files.
HAZARD_CONTEXT = [
    ("ls_land_high_pct", "Land highly susceptible to landslides (USGS, %)", "landslide_barrio.json"),
    ("ls_res_high_pct", "Residents on land highly susceptible to landslides (estimate, %)", "landslide_barrio.json"),
]
HAZARD_NOTE = ("Not an input of the index: the white paper keeps natural hazards such as flooding, landslides and earthquakes in separate layers. The landslide "
               "susceptibility map (USGS, Hughes and Schulz 2020) covers the main island only.")


def log(*a):
    print(*a, flush=True)


# ── The method ───────────────────────────────────────────────────────────────

def percentile(values):
    """The percentile of each value among the values that are not None: the share of them strictly lower (0 to 1). None stays None."""
    xs = sorted(v for v in values if v is not None)
    n = len(xs)
    return [None if v is None else bisect.bisect_left(xs, v) / n for v in values]


def rank(p):
    """The fifth of an index from 0 to 1: 1 (0 to 0.20, low) to 5 (above 0.80, high); None for no value."""
    if p is None:
        return None
    return min(5, max(1, math.ceil(round(p * 5, 9))))


def combine(parts):
    """The percentile of the sum of several percentile lists (one per input or sub-indicator). A place that lacks some gets the sum of the ones it has,
    scaled to the full count (the white paper's Education rule: two inputs, one missing, the other doubled). A place with none has no value."""
    k = len(parts)
    sums = []
    for i in range(len(parts[0])):
        have = [p[i] for p in parts if p[i] is not None]
        sums.append(round(sum(have) * k / len(have), 9) if have else None)   # rounded so that float noise cannot break a tie
    return percentile(sums)


def build_area(inputs, structure):
    """An area's index from its inputs: {sub-indicator (or None): [value lists]}. Each sub-indicator is the percentile of the sum of its inputs'
    percentiles; the area is the percentile of the sum of its sub-indicators. An area with one sub-indicator is that sub-indicator."""
    subs = [combine([percentile(v) for v in inputs[s]]) for s in structure if inputs.get(s)]
    return subs[0] if len(subs) == 1 else combine(subs)


def build_index(columns, structure=STRUCTURE, active=None):
    """Every area and the overall index. `columns` = {area: {sub: [value lists]}}; `active` (list of bool) marks the places to rank (others: None)."""
    n = len(next(iter(next(iter(columns.values())).values()))[0])
    active = active or [True] * n
    mask = lambda vals: [v if active[i] else None for i, v in enumerate(vals)]
    areas = {a: build_area({s: [mask(v) for v in vs] for s, vs in columns[a].items()}, structure[a]) for a in structure}
    areas["overall"] = combine([areas[a] for a in ("econ", "edu", "envir", "health", "housing", "infra")])
    return areas


# ── Small statistics for the checks ──────────────────────────────────────────

def avg_ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    ra, rb = avg_ranks([p[0] for p in pairs]), avg_ranks([p[1] for p in pairs])
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return round(cov / math.sqrt(va * vb), 4) if va and vb else None


# ── Harvest (the original) ───────────────────────────────────────────────────

def _get(url, params=None, tries=4):
    for t in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=90)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise RuntimeError(f"{url}: {d['error']}")
            return d
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(2 * (t + 1))


def _query(service, where, fields):
    rows, off = [], 0
    while True:
        d = _get(f"{SERVICES}/{service}/FeatureServer/0/query", {"where": where, "outFields": fields, "returnGeometry": "false", "orderByFields": "GEOID",
                                                                  "resultOffset": off, "resultRecordCount": 2000, "f": "json"})
        feats = [f["attributes"] for f in d.get("features", [])]
        rows += feats
        if not d.get("exceededTransferLimit") and len(feats) < 2000:
            return rows
        off += len(feats)


def _about(service):
    """What the service and its ArcGIS Online item say about themselves: the last edit of the data and the license fields."""
    layer = _get(f"{SERVICES}/{service}/FeatureServer/0", {"f": "json"})
    svc = _get(f"{SERVICES}/{service}/FeatureServer", {"f": "json"})
    item_id = svc.get("serviceItemId")
    item = _get(f"https://www.arcgis.com/sharing/rest/content/items/{item_id}", {"f": "json"}) if item_id else {}
    edited = (layer.get("editingInfo") or {}).get("dataLastEditDate")
    return {"service": service, "url": f"{SERVICES}/{service}/FeatureServer/0", "item": item_id, "data_last_edit": time.strftime("%Y-%m-%d", time.gmtime(edited / 1000)) if edited else None,
            "licenseInfo": item.get("licenseInfo") or None, "accessInformation": item.get("accessInformation") or None, "owner": item.get("owner")}


def harvest(refresh=False):
    """The two services, cached in cache/wcrp_rvi. Returns {"all": rows, "master": rows, "about": [...], "harvested": date}."""
    path = CACHE / "harvest.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    log("harvest: All_Indicator (one row per barrio: the OVERALL rows carry every area's index and rank)")
    fields = ",".join(["GEOID", "NAME", "County", "Indicator", "TOTPOP"] + [x for a in AREAS for x in FIELD[a]])
    allrows = _query(ALL_INDICATOR, "Indicator='OVERALL'", fields)
    log(f"  {len(allrows)} rows")
    log("harvest: Master_Data_Table_Update (the barrio inputs)")
    mrows = _query(MASTER, "1=1", ",".join(["GEOID", "Indicator", "Index_Val", "Rank", "Var1", "Var2", "Var3", "Va4", "Var5", "Var6", "Var7", "Var8", "Var9", "Var10", "Var11", "Var12", "Var13", "Var14", "Var15", "Var16", "Var17", "Var18", "Var19", "Var20", "Var21", "Var22", "Var23", "Var24"]))
    log(f"  {len(mrows)} rows")
    about = [_about(ALL_INDICATOR), _about(MASTER)]
    out = {"harvested": date.today().isoformat(), "about": about, "all": allrows, "master": mrows}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return out


def num(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def original(h, ids):
    """The original, as published, in the order of `ids`: {area: [index 0-1]}, {area: [rank]}, population, inputs, and the checks."""
    by = {r["GEOID"]: r for r in h["all"]}
    if len(by) != len(h["all"]):
        raise SystemExit("wcrp_rvi: All_Indicator has more than one OVERALL row for a barrio")
    missing = [g for g in ids if g not in by]
    extra = sorted(set(by) - set(ids))
    if missing or extra:
        raise SystemExit(f"wcrp_rvi: All_Indicator barrios do not match barrios.geojson: {len(missing)} missing, {len(extra)} not in the observatory")
    idx = {a: [num(by[g][FIELD[a][0]]) for g in ids] for a in AREAS}
    rk = {a: [by[g][FIELD[a][1]] or None for g in ids] for a in AREAS}   # 0 = no value in the service
    for a in AREAS:   # the published rank must be the fifth of the published index; a harvest where it is not stops the build
        bad = [g for g, v, r in zip(ids, idx[a], rk[a]) if rank(v) != r]
        if bad:
            raise SystemExit(f"wcrp_rvi: {a}: {len(bad)} published ranks are not the fifth of the published index (first {bad[0]})")
    pop = [by[g]["TOTPOP"] for g in ids]
    master = {}
    for r in h["master"]:
        g = str(int(r["GEOID"]))   # a number in this table, a string in All_Indicator
        master.setdefault(r["Indicator"], {})[g] = r
    inputs = {}
    for key, area, fld, _, _ in ORIGINAL_INPUTS:
        rows = master[MASTER_INDICATOR[area]]
        inputs[key] = [num(rows[g][fld]) if g in rows else None for g in ids]
    for g in APPENDIX_C:   # a 0 in the service where the white paper says no value could be computed (nobody aged 3 to 24)
        if g in ids:
            inputs["o_not_enrolled_3_24_pct"][ids.index(g)] = None
    return {"index": idx, "rank": rk, "pop": pop, "inputs": inputs, "master": master}


def known_errors(h, orig):
    """The errors the page discloses, measured on the harvest: the mislabeled comparison columns and the shares above 100%."""
    m = orig["master"]
    lead_muni = [num(r["Var16"]) for r in m["ENVIR"].values() if num(r["Var16"]) is not None]
    lead_bar = [v for v in orig["inputs"]["o_lead_paint_pct"] if v is not None]
    pre90 = [v for v in orig["inputs"]["o_built_pre1990_pct"] if v is not None]
    econ = list(m["ECON"].values())
    pr = econ[0]
    return {
        "lead_paint_municipio_range": [round(min(lead_muni), 1), round(max(lead_muni), 1)],
        "lead_paint_municipio_over_100": len({r["Var16"] for r in m["ENVIR"].values() if (num(r["Var16"]) or 0) > 100}),   # distinct municipio values
        "lead_paint_barrio_over_100": sum(1 for v in lead_bar if v > 100),
        "built_pre1990_barrio_max": round(max(pre90), 1),
        "built_pre1990_barrio_over_100": sum(1 for v in pre90 if v > 100),
        "econ_pr_columns": {"poverty": num(pr["Var9"]), "unemployed": num(pr["Var10"]), "public_assistance": num(pr["Var11"]), "per_capita_income": num(pr["Var12"])},
    }


def reproduce(orig, ids):
    """How well the method, applied to the original's own published inputs, gives back the original's published index (Spearman rank correlation,
    and the share of barrios whose rank is the same). A check of the method as implemented here, and a disclosure of where the original cannot be traced."""
    I = orig["inputs"]
    active = [v is not None for v in orig["index"]["overall"]]
    m = lambda key: [v if a else None for v, a in zip(I[key], active)]
    P = lambda key: percentile(m(key))
    out = {}
    trials = {
        "econ": combine([P("o_public_assist_pct"), P("o_poverty_pct"), P("o_unemployed_pct")]),
        # a reviewer's hypothesis (2026-10-17): public assistance, poverty and per capita income, income counted as more vulnerable when higher, no unemployment
        "econ_income_as_higher_no_unemployment": combine([P("o_public_assist_pct"), P("o_poverty_pct"), P("o_per_capita_income")]),
        "edu": combine([P("o_not_enrolled_3_24_pct"), P("o_no_diploma_pct")]),
        "envir": combine([P(k) for k in ("o_nonattainment", "o_impaired_water", "o_rmp_sites", "o_dumps", "o_solid_waste", "o_npl_sites", "o_tri_facilities", "o_lead_paint_pct")]),
        "health": combine([P("o_disability_pct"), P("o_uninsured_pct"), P("o_hospital_min")]),
        "housing": combine([P("o_vacancy_pct"), P("o_built_pre1990_pct"), P("o_severe_problems_pct")]),
        "housing_two_sub_indicators": combine([P("o_severe_problems_pct"), combine([P("o_vacancy_pct"), P("o_built_pre1990_pct")])]),
        "infra": combine([combine([P("o_no_computer_pct"), P("o_no_internet_pct"), P("o_no_broadband_pct")]),
                          combine([percentile([None if v is None else -v for v in m("o_intersections_sqmi")]), P("o_no_vehicle_pct")])]),
        "overall": combine([orig["index"][a] for a in ("econ", "edu", "envir", "health", "housing", "infra")]),
    }
    for name, z in trials.items():
        pub = orig["index"][name.split("_")[0]]   # the area a trial is compared with: the first word of its name
        same = [rank(a) == rank(b) for a, b in zip(z, pub) if a is not None and b is not None]
        out[name] = {"spearman": spearman(z, pub), "same_rank_pct": round(100 * sum(same) / len(same), 1) if same else None}
    return out


# ── The rebuild ──────────────────────────────────────────────────────────────

def _share(num_, den):
    return None if num_ is None or not den else round(100 * num_ / den, 3)


def rebuild_inputs(ids, refresh=False, window=None, context=None):
    """The rebuild's input values for each barrio, in the order of `ids`, and the window they come from (the newest of acs_barrio.json unless given).
    `context` (a dict of "values" and "moe"), when given, receives the age groups of the same window (CONTEXT): shown beside the index, never an input."""
    import acs_small
    acs = json.loads((DATA / "acs_barrio.json").read_text(encoding="utf-8"))
    window = window or max(acs["windows"])
    at = {g: i for i, g in enumerate(acs["geo"]["ids"])}
    V = {v["key"]: v for v in acs["vars"]}

    def from_acs(key):
        arr = V[key]["years"][str(window)]
        return [arr[at[g]] if g in at else None for g in ids]
    T = {t: acs_small.read_table(t, vintage=window, levels=["barrio"], refresh=refresh)["levels"]["barrio"] for t in REBUILD_TABLES}

    def cell(t, g, n):
        row = T[t].get(g)
        v = row.get(f"{t}_{n:03d}") if row else None
        return v[0] if v else None

    def total(t, g, cells):
        vals = [cell(t, g, n) for n in cells]
        return None if any(v is None for v in vals) else sum(vals)
    out = {}
    for key, area, sub, label, how in REBUILD_INPUTS:
        if how.startswith("acs_barrio:"):
            out[key] = from_acs(how.split(":", 1)[1])
    out["public_assist_hh_pct"] = [_share(cell("B19057", g, 2), cell("B19057", g, 1)) for g in ids]
    out["built_pre1960_pct"] = [_share(total("B25034", g, (9, 10, 11)), cell("B25034", g, 1)) for g in ids]
    out["built_pre1990_pct"] = [_share(total("B25034", g, range(6, 12)), cell("B25034", g, 1)) for g in ids]
    out["no_computer_pct"] = [_share(cell("B28003", g, 6), cell("B28003", g, 1)) for g in ids]
    out["no_broadband_pct"] = [None if cell("B28002", g, 1) in (None, 0) or cell("B28002", g, 4) is None else _share(cell("B28002", g, 1) - cell("B28002", g, 4), cell("B28002", g, 1)) for g in ids]
    out["not_enrolled_3_24_pct"] = [_share(total("B14003", g, [n for r in B14003_NOT_ENROLLED for n in r]), total("B14003", g, [n for r in B14003_AGES_3_24 for n in r])) for g in ids]
    out.update(conditions_inputs(ids))
    pop = from_acs("acs_population")
    if context is not None:
        for key, _, var in CONTEXT:   # the age groups of the same window, with their margins of error (context, not inputs)
            context["values"][key] = from_acs(var)
            m = (V[var].get("moe") or {}).get(str(window))
            context["moe"][key] = [m[at[g]] if m and g in at else None for g in ids]
    return out, pop, window


def conditions_inputs(ids):
    """The rebuild's inputs from conditions_barrio.json (conditions.py): EPA sites, impaired waters, non-attainment, CHAS, intersections, hospital drive time.
    Each source in its own vintage, so an older survey window gets the same values. A flag is 1 where the barrio's share of the area is above 0."""
    doc = json.loads(CONDITIONS.read_text(encoding="utf-8"))
    at = {g: i for i, g in enumerate(doc["geo"]["ids"])}
    if set(at) != set(ids):
        raise SystemExit("wcrp_rvi: conditions_barrio.json does not hold the 901 barrios of barrios.geojson (python conditions.py)")
    V = {v["key"]: next(iter(v["years"].values())) for v in doc["vars"]}

    def col(k):
        return [V[k][at[g]] for g in ids]

    def flag(*ks):
        cols = [col(k) for k in ks]
        return [None if any(c[i] is None for c in cols) else int(any(c[i] > 0 for c in cols)) for i in range(len(ids))]
    return {"nonattainment_flag": flag("epa_naa_so2_pct", "epa_naa_lead_pct"), "impaired_water_flag": flag("epa_303d_pct"), "rmp_sites": col("epa_rmp"),
            "landfill_flag": flag("epa_landfills"), "npl_sites": col("epa_npl"), "tri_facilities": col("epa_tri"), "hospital_drive_min": col("hosp_drive_min"),
            "severe_problems_pct": col("chas_severe_pct"), "intersection_density": col("street_intersection_density")}


def rebuild(values, pop):
    """The rebuild's areas and overall index (0 to 1) from the input values; a barrio with no residents in the window has no value."""
    active = [p is not None and p > 0 for p in pop]
    columns = {a: {} for a in STRUCTURE}
    for key, area, sub, _, _ in REBUILD_INPUTS:
        columns[area].setdefault(sub, []).append([None if v is None else -v for v in values[key]] if key in FEWER_IS_WORSE else values[key])
    return build_index(columns, active=active)


# ── Files ────────────────────────────────────────────────────────────────────

V_ORIG, V_REB = "orig", "rebuild"
SOURCES = {
    "wcrp_rvi": {"name": "Hunter College for Foundation for Puerto Rico (WCRP) — Risk and Vulnerability Indicators, ArcGIS services (2022)", "license": "No open license stated (licenseInfo and accessInformation are empty); FPR publishes it with the program's approval; ask PRDOH and FPR before re-use", "url": f"{SERVICES}/{ALL_INDICATOR}/FeatureServer/0"},
    "acs": {"name": "US Census Bureau — American Community Survey 5-year estimates", "license": "US Government work; cite the Census Bureau as the source", "url": "https://www2.census.gov/programs-surveys/acs/summary_file/"},
    "conditions": {"name": "PR Data Observatory, local conditions by barrio (conditions_barrio.json): EPA TRI, Facility Registry Service, ATTAINS, Green Book and LMOP; HUD CHAS 2016-2020; Census TIGER/Line 2026; drive time to a CMS general hospital along OpenStreetMap roads",
                   "license": "Public domain (EPA, HUD, Census Bureau, CMS); the drive time uses OpenStreetMap roads (ODbL)", "url": "https://observatory.foundationpr.org/dictionary.html#conditions.epa_tri"},
}


# What each rebuilt area takes from conditions_barrio.json (economy and education use the survey only); a test checks this against REBUILD_INPUTS
CONDITIONS_IN = {"overall": "the observatory's current EPA, HUD CHAS, TIGER and hospital drive-time data",
                 "envir": "the observatory's current EPA data (TRI, Facility Registry Service, ATTAINS, Green Book, LMOP)",
                 "health": "the observatory's drive time to a general hospital",
                 "housing": "HUD CHAS severe housing problems (estimated by barrio)",
                 "infra": "TIGER/Line street intersections"}


def pct100(v):
    return None if v is None else round(v * 100, 2)   # two decimals: the original publishes some indices with four (0.8002), which one decimal would push into the rank below


def make_files(ids, orig, reb, reb_values, reb_pop, window, h, checks, context):
    built = date.today().isoformat()
    vars_ = []
    for ver, data, year in ((V_ORIG, orig["index"], 2019), (V_REB, reb, window)):
        for a in AREAS:
            what = "overall" if a == "overall" else a
            if ver == V_ORIG:
                label = f"WCRP vulnerability, {AREA_LABEL[a].lower()}: original 2022 (ACS 2015–2019)"
                definition = (f"The {AREA_LABEL[a].lower()} index of the Risk and Vulnerability Indicators that Hunter College built for FPR's WCRP program, as published in March 2022 (inputs mostly ACS 2015–2019): "
                              "the barrio's percentile among the 887 barrios with residents, times 100 (higher is more vulnerable). Ranks are its fifths: 1 (0–20) low to 5 (above 80) high. Not recomputed.")
                sources = ["wcrp_rvi", "acs"]
            else:
                label = f"WCRP vulnerability, {AREA_LABEL[a].lower()}: updated {window - 4}–{window}"   # the version's name on the page (the project lead, 2026-10-19): Updated 2020–2024
                local = CONDITIONS_IN.get(a, "")
                definition = (f"The {AREA_LABEL[a].lower()} index updated by the observatory with the RVI white paper's method on ACS {window - 4}–{window}{' and ' + local if local else ''}: "
                              "percentiles of each input among barrios, summed within the area and ranked again (the overall index sums the six areas). Times 100; ranks are fifths."
                              + (" One input of the original, solid waste facilities other than landfills, has no current source and is left out (see the dictionary)." if a in ("overall", "envir") else ""))
                sources = ["acs", "conditions"] if local else ["acs"]
            vars_.append({"key": f"rvi_{what}_{ver}", "group": "Original 2022 (ACS 2015–2019)" if ver == V_ORIG else f"Updated {window - 4}–{window}",
                          "label": label, "unit": "", "d": 2, "type": "rate", "family": "wcrp", "sources": sources,
                          "ref": "WCRP Risk and Vulnerability Indicators (Hunter College, 2022), as published" if ver == V_ORIG else "Updated by the observatory with the RVI method (wcrp_rvi.py)",
                          "definition": definition, "noIsland": True, "noValue": "Ranked among barrios only: shown by barrio", "level": "barrio", "fifths": True,
                          "years": {str(year): [pct100(v) for v in data[a]]}})
    doc = {"version": 1, "built": built, "as_of": built, "level": "barrio",
           "about": "WCRP Risk and Vulnerability Indicators by barrio: each area's index (percentile among barrios, 0 to 100) in the original as published and in the observatory's updated version (same method, current data). "
                    "The arrays follow geo.ids; a null is a barrio with no value (no residents). Ranks are the fifths of the index. Built by wcrp_rvi.py; method, inputs and known errors on wcrp.html and in the data dictionary.",
           "geo": {"ids": ids}, "sources": SOURCES,
           "versions": {V_ORIG: {"window": "2015–2019", "published": "2022-03", "harvested": h["harvested"], "services": h["about"]},
                        V_REB: {"window": f"{window - 4}–{window}", "built": built}},
           "method": {V_ORIG: [{"key": k, "area": a, "label": l, "unit": u} for k, a, _, l, u in ORIGINAL_INPUTS],
                      V_REB: [{"key": k, "area": a, "sub": s_, "label": l, "from": how, "unit": REBUILD_UNIT.get(k, "%"), **({"note": REBUILD_NOTE[k]} if k in REBUILD_NOTE else {}),
                               **({"fewer_is_worse": True} if k in FEWER_IS_WORSE else {})} for k, a, s_, l, how in REBUILD_INPUTS],
                      "missing": [{"area": a, "sub": s_, "label": l, "why": w} for a, s_, l, w in MISSING],
                      "context": [{"key": k, "label": l, "from": f"acs_barrio:{v}", "unit": "%", "estimate": True} for k, l, v in CONTEXT],
                      "context_note": CONTEXT_NOTE,
                      "hazards": [{"key": k, "label": l, "file": f} for k, l, f in HAZARD_CONTEXT],
                      "hazards_note": HAZARD_NOTE},
           "checks": checks,
           "vars": vars_}
    inputs = {"version": 1, "built": built, "level": "barrio",
              "about": "The input values behind each barrio's WCRP vulnerability index, for the pop-up of wcrp.html: the original's as published (Master_Data_Table_Update, barrio columns only) and the updated version's (ACS and conditions_barrio.json). "
                       "Arrays follow geo.ids; the labels and sources of the inputs are in wcrp_rvi_barrio.json (method).",
              "geo": {"ids": ids},
              V_ORIG: {"population": orig["pop"], "values": {k: orig["inputs"][k] for k, *_ in ORIGINAL_INPUTS}},
              V_REB: {"population": reb_pop, "values": {k: [None if v is None else round(v, 1) for v in reb_values[k]] for k, *_ in REBUILD_INPUTS},
                      "context": {k: [None if v is None else round(v, 1) for v in context["values"][k]] for k, *_ in CONTEXT},
                      "context_moe": {k: [None if v is None else round(v, 1) for v in context["moe"][k]] for k, *_ in CONTEXT}}}
    return doc, inputs


def compare(orig_idx, reb):
    """How much the rebuild moves each area's rank: barrios ranked in both, the share whose rank changed, moved two ranks or more, and the rank correlation."""
    out = {}
    for a in AREAS:
        pairs = [(rank(o), rank(r)) for o, r in zip(orig_idx[a], reb[a]) if o is not None and r is not None]
        out[a] = {"n": len(pairs), "changed_pct": round(100 * sum(x != y for x, y in pairs) / len(pairs), 1), "moved2_pct": round(100 * sum(abs(x - y) >= 2 for x, y in pairs) / len(pairs), 1),
                  "spearman": spearman(orig_idx[a], reb[a])}
    return out


SAME_INPUT = {"poverty_pct": "o_poverty_pct", "public_assist_hh_pct": "o_public_assist_pct", "unemployment_rate_pct": "o_unemployed_pct", "not_enrolled_3_24_pct": "o_not_enrolled_3_24_pct",
              "acs_no_hs_pct": "o_no_diploma_pct", "built_pre1960_pct": "o_lead_paint_pct", "acs_disability_pct": "o_disability_pct", "acs_uninsured_pct": "o_uninsured_pct",
              "vacancy_pct": "o_vacancy_pct", "built_pre1990_pct": "o_built_pre1990_pct", "no_computer_pct": "o_no_computer_pct", "no_internet_pct": "o_no_internet_pct",
              "no_broadband_pct": "o_no_broadband_pct", "no_vehicle_hh_pct": "o_no_vehicle_pct", "nonattainment_flag": "o_nonattainment", "impaired_water_flag": "o_impaired_water",
              "rmp_sites": "o_rmp_sites", "landfill_flag": "o_dumps", "npl_sites": "o_npl_sites", "tri_facilities": "o_tri_facilities", "hospital_drive_min": "o_hospital_min",
              "severe_problems_pct": "o_severe_problems_pct", "intersection_density": "o_intersections_sqmi"}   # the original's column for each input the rebuild keeps


def definitions(ids, orig, reb, values):
    """Counts the page gives beside the inputs whose current source differs from the original's: barrios flagged or with a site, among those ranked
    in each version, and the barrios ranked in health with no hospital drive time (Vieques and Culebra), by municipio code."""
    on_r = [i for i in range(len(ids)) if reb["overall"][i] is not None]
    on_o = [i for i in range(len(ids)) if orig["index"]["overall"][i] is not None]
    I = orig["inputs"]
    pos = lambda arr, on: sum(1 for i in on if (arr[i] or 0) > 0)
    tot = lambda arr, on: int(sum(arr[i] or 0 for i in on))
    no_hosp = [i for i in on_r if reb["health"][i] is not None and values["hospital_drive_min"][i] is None]
    return {"ranked": {V_ORIG: len(on_o), V_REB: len(on_r)},
            "impaired_water": {V_ORIG: pos(I["o_impaired_water"], on_o), V_REB: pos(values["impaired_water_flag"], on_r)},
            "nonattainment": {V_ORIG: pos(I["o_nonattainment"], on_o), V_REB: pos(values["nonattainment_flag"], on_r)},
            "landfill": {V_ORIG: pos(I["o_dumps"], on_o), V_REB: pos(values["landfill_flag"], on_r)},
            "rmp_sites": {V_ORIG: tot(I["o_rmp_sites"], on_o), V_REB: tot(values["rmp_sites"], on_r)},
            "npl_sites": {V_ORIG: tot(I["o_npl_sites"], on_o), V_REB: tot(values["npl_sites"], on_r)},
            "tri_facilities": {V_ORIG: tot(I["o_tri_facilities"], on_o), V_REB: tot(values["tri_facilities"], on_r)},
            "health_without_hospital": {"barrios": len(no_hosp), "municipios": sorted({ids[i][2:5] for i in no_hosp}), "geoids": [ids[i] for i in no_hosp]}}


def levels_by_window(ids, refresh, reb, window):
    """The updated version's level (1 to 5) of each area in every five-year window the survey publishes for barrios, for the page's slider (the project lead,
    2026-11-04: "see how it changes each year, with 2022 as the original"). Each window is rebuilt with the same method; the inputs that do not come from
    the survey keep their own vintage, so only the survey moves. A level list is a string of digits in the order of geo.ids, 0 for no level.
    Windows that share years are not independent: `steps` gives the share of barrios whose overall level changes from one window to the next."""
    windows = sorted(json.loads((DATA / "acs_barrio.json").read_text(encoding="utf-8"))["windows"])
    out, prev = {"windows": [f"{w - 4}–{w}" for w in windows], "ends": windows, "levels": {a: [] for a in AREAS}, "steps": []}, None
    for w in windows:
        idx = reb if w == window else rebuild(*rebuild_inputs(ids, refresh, window=w)[:2])
        for a in AREAS:
            out["levels"][a].append("".join(str(rank(v) or 0) for v in idx[a]))
        cur = out["levels"]["overall"][-1]
        if prev is not None:
            both = [(x, y) for x, y in zip(prev, cur) if x != "0" and y != "0"]
            out["steps"].append({"from": f"{w - 5}–{w - 1}", "to": f"{w - 4}–{w}", "changed_pct": round(100 * sum(x != y for x, y in both) / max(1, len(both)), 1)})
        prev = cur
        log(f"  levels {w - 4}-{w}: done")
    return out


def build(refresh=False, write=True):
    ids = [f["properties"]["geoid"] for f in json.loads((DATA / "barrios.geojson").read_text(encoding="utf-8"))["features"]]
    if len(ids) != 901 or len(set(ids)) != 901:
        raise SystemExit("wcrp_rvi: barrios.geojson should hold 901 distinct barrios")
    ids = sorted(ids)
    h = harvest(refresh)
    orig = original(h, ids)
    context = {"values": {}, "moe": {}}
    values, pop, window = rebuild_inputs(ids, refresh, context=context)
    reb = rebuild(values, pop)
    # where the differences come from: (1) the original's own 2015-2019 inputs with only the inputs the rebuild keeps; (2) the rebuild on an older window of the same survey
    fewer = rebuild({k: orig["inputs"][o] for k, o in SAME_INPUT.items()}, [1 if v is not None else 0 for v in orig["index"]["overall"]])
    first = min(json.loads((DATA / "acs_barrio.json").read_text(encoding="utf-8"))["windows"])
    v0, p0, w0 = rebuild_inputs(ids, refresh, window=first)
    older = rebuild(v0, p0)
    checks = {"reproduced": reproduce(orig, ids), "known_errors": known_errors(h, orig), "rebuild_vs_original": compare(orig["index"], reb),
              "fewer_inputs_vs_original": compare(orig["index"], fewer), "rebuild_vs_fewer_inputs": compare(fewer, reb),
              "rebuild_vs_older_window": {"window": f"{w0 - 4}–{w0}", **compare(older, reb)},
              "ranked": {V_ORIG: sum(v is not None for v in orig["index"]["overall"]), V_REB: sum(v is not None for v in reb["overall"])},
              "means": {k: round(sum(x for x in vals if x is not None) / max(1, sum(x is not None for x in vals)), 1) for k, vals in [*orig["inputs"].items(), *values.items()]},   # unweighted mean over barrios, to compare definitions
              "partial_inputs": {a: sum(1 for i in range(len(ids)) if reb[a][i] is not None and any(values[k][i] is None for k, ar, *_ in REBUILD_INPUTS if ar == a)) for a in STRUCTURE},
              "definitions": definitions(ids, orig, reb, values)}
    series = levels_by_window(ids, refresh, reb, window)
    doc, inputs = make_files(ids, orig, reb, values, pop, window, h, checks, context)
    doc["series"] = series
    if write:
        for path, d in ((OUT, doc), (OUT_INPUTS, inputs)):
            path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            log(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size / 1024:.0f} KB)")
        log(json.dumps(checks, indent=1))
    return doc, inputs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        doc, inputs = build(write=False)
        same = True
        for path, d in ((OUT, doc), (OUT_INPUTS, inputs)):
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            for x in (old, d):
                if x:
                    x.pop("built", None), x.pop("as_of", None), (x.get("versions") or {}).get(V_REB, {}).pop("built", None)
            if old != d:
                log(f"{path.name}: not current (run python wcrp_rvi.py)")
                same = False
        log("wcrp_rvi: current" if same else "wcrp_rvi: rebuild needed")
        return 0 if same else 1
    build(refresh="--refresh" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
