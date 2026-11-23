"""Small-area American Community Survey series for the PR Data Observatory (plan item 7, data wave A): the first sub-municipal view of housing, income, work and people.

    python small_area.py             # build the four files below (downloads only what acs_small.py has not cached)
    python small_area.py --refresh   # read the Census Bureau's tables again
    python small_area.py --check     # rebuild in memory from the cache and say whether the published files are what it gives (no network)
    python small_area.py --measure   # how rough the published values are, per variable and level, as the table of docs/small-area.md (reads the published files only)

Writes, from the ACS 5-year tables read by acs_small.py (the table-based vintages 2021 to 2024, windows 2017-2021 to 2020-2024, all on the 2020 geography):
  site/data/population_series.json   the municipios and Puerto Rico: population, age, households, disability, veterans (the Population domain's first series)
  site/data/acs_barrio.json          901 barrios       (the Census Bureau's own county subdivision rows; barrios do not nest in tracts)
  site/data/acs_tract.json           981 census tracts
  site/data/acs_blockgroup.json      2,555 block groups
  site/data/population_age.json      age: five-year bands (municipios and Puerto Rico only) and the age groups (also barrios and census tracts where they are reliable enough), counts and shares
Every variable of these files also exists for the 78 municipios (housing_series.json, economy_series.json or population_series.json) and keeps its key, so the layer engine
reads a tract or a barrio as one more level of the same dataset (site/js/core/adapters.js, levelFile). Values and margins of error (90% confidence) are the Census Bureau's,
or are worked out by the Census Bureau's formulas in housing_series.derive and economy_series.derive_econ, the same code that makes the municipal values.

Rules (docs/small-area.md, docs/geography.md section 5): an empty estimate is null, never zero; margins are not added or averaged; a rate is worked out again from its
numerator and denominator; the five-year windows share years, so the change from one to the next is not a trend; cost burden is not published below municipio (the margin of
the share of renters paying 30% or more is about 36 points for a tract and 55 for a block group); some tables do not exist for block groups (poverty, Gini, income by tenure,
disability). Age: five-year bands are published for the municipios only (below them the margin is above 30% of the estimate for 89% or more of the barrios and 95%
or more of the tracts), and of the age groups only those whose share is flagged for fewer than half of the barrios are published below the municipio (AGE_SMALL).
"""

import json
import statistics
import sys
from collections import OrderedDict
from datetime import date
from math import sqrt
from pathlib import Path

import acs_small
import economy_series as es
import housing_series as hs

ROOT = Path(__file__).resolve().parent
OUT = hs.OUT
log = hs.log
VINTAGES = [2021, 2022, 2023, 2024]   # the table-based ACS 5-year vintages: windows 2017-2021 ... 2020-2024, all on the 2020 geography (docs/geography.md, section 5)
POP_TABLES = ["B01001", "B09001", "B11001", "B18101", "B21001", "B27010", "B15002", "B16004", "B22010", "B17001"]
TABLES = sorted(set(hs.TABLES) | set(es.ECON_TABLES) | set(POP_TABLES))
FILES = {"barrio": "acs_barrio.json", "tract": "acs_tract.json", "block-group": "acs_blockgroup.json"}
POP_FILE = "population_series.json"
AGE_FILE = "population_age.json"

# ── The variables of the Population domain (new) ─────────────────────────────
# B01001 sex by age: male cells 003-025 and female cells 027-049 in the same order of age groups (under 5, 5-9, 10-14, 15-17, 18-19, 20, 21, 22-24, 25-29, 30-34, 35-39, 40-44,
# 45-49, 50-54, 55-59, 60-61, 62-64, 65-66, 67-69, 70-74, 75-79, 80-84, 85 and over). The cell numbers are checked against the Census Bureau's own labels by check_labels().
UNDER18 = [3, 4, 5, 6, 27, 28, 29, 30]
AGE65 = [20, 21, 22, 23, 24, 25, 44, 45, 46, 47, 48, 49]
DISABILITY = [4, 7, 10, 13, 16, 19, 23, 26, 29, 32, 35, 38]   # B18101: "With a disability" in each age group of each sex
NO_COVERAGE = [17, 33, 50, 66]   # B27010: "No health insurance coverage" in each age group (under 19, 19-34, 35-64, 65 and over)
NO_DIPLOMA = [3, 4, 5, 6, 7, 8, 9, 10, 20, 21, 22, 23, 24, 25, 26, 27]   # B15002: men and women 25 and over from "No schooling completed" to "12th grade, no diploma"
# Language, nutrition assistance and poverty by age (added 2026-11-14, decision 107 step 1). The cell numbers are checked against the Census Bureau's labels by check_labels().
ENGLISH_WELL = [3, 5, 10, 15, 20, 25, 27, 32, 37, 42, 47, 49, 54, 59, 64]   # B16004 (people 5 and over): "Speak only English" and, for each language group, 'Speak English "very well"', in the three age groups
PAN = 2   # B22010: "Household received Food Stamps/SNAP in the past 12 months"; in Puerto Rico the survey asks about the Programa de Asistencia Nutricional (PAN)
CHILD_POOR, CHILD_NOT_POOR = [4, 5, 6, 7, 8, 9, 18, 19, 20, 21, 22, 23], [33, 34, 35, 36, 37, 38, 47, 48, 49, 50, 51, 52]   # B17001: boys and girls under 18 (six age groups each), below and at or above the poverty level
SENIOR_POOR, SENIOR_NOT_POOR = [15, 16, 29, 30], [44, 45, 58, 59]   # B17001: men and women 65 to 74 and 75 and over, below and at or above the poverty level

# Age (added 2026-10-18). B01001's age groups are not five years wide everywhere (15-17, 18-19, 20, 21, 22-24, 60-61, 62-64, 65-66, 67-69), so a band adds the cells inside it.
# Each entry: key, (first age, last age or None for "and over"); the cells are worked out from the labels (age_cells) and checked against them in every vintage.
AGE_BANDS = [(f"acs_age{a}to{a + 4}", (a, a + 4)) for a in range(0, 85, 5)] + [("acs_age85plus", (85, None))]
AGE_GROUPS = [("acs_age5to17", (5, 17)), ("acs_age18to24", (18, 24)), ("acs_age25to44", (25, 44)), ("acs_age45to64", (45, 64)), ("acs_age65plus", (65, None)),
              ("acs_under18", (0, 17)), ("acs_age18to44", (18, 44))]
YOUNG = {"acs_age_under3": 3, "acs_age3to4": 4}   # B09001 Population under 18 years by age: "In households: Under 3 years" (003) and "3 and 4 years" (004); B01001 starts at "Under 5"
AGE_COUNTS = ["acs_age_under3", "acs_age3to4", "acs_age5to17", "acs_age18to24", "acs_age25to44", "acs_age45to64", "acs_age65plus", "acs_under18", "acs_age18to44"]   # counts of the age groups, datasets of the Economy tab: municipios only (below them every count is flagged for more than half of the barrios; EXCLUDED)
AGE_SMALL = ["acs_under18", "acs_age18to44", "acs_age45to64", "acs_age65plus"]   # the age groups published below the municipio (counts and shares): their share is flagged less reliable for under half of the barrios in 2020-2024 (18-44: 39%, 45-64: 31%, 65+: 36%), except under 18 (70%), published since item 7; 5-17 (79%), 18-24 (89%), 25-44 (53%), under 3 and 3-4 (99% or more) and every five-year band (89% or more) are not

POP_VARS = OrderedDict([
    # key: (group, label, unit, decimals, type, definition, reference)
    ("acs_population", ("People and age", "Population (survey estimate)", "", 0, "count", "People living in the area, as estimated by the American Community Survey over five years. It differs from the Census count and from the yearly estimates of the Population Estimates Program, which have no margin of error and exist only for municipalities.", "ACS B01003")),
    ("acs_under18_pct", ("People and age", "People under 18, % of all people", "%", 1, "rate", "Share of the people of the area who are under 18 years old.", "ACS B01001")),
    ("acs_age65plus_pct", ("People and age", "People 65 and older, % of all people", "%", 1, "rate", "Share of the people of the area who are 65 years old or older.", "ACS B01001")),
    ("acs_age_under3_pct", ("People and age", "Children under 3, % of all people", "%", 1, "rate", "Children under 3 years old who live in households, as a share of all the people of the area. The survey gives this age group only for children in households (table B09001), so the few in group quarters are left out.", "ACS B09001, B01001")),
    ("acs_age3to4_pct", ("People and age", "Children aged 3 and 4, % of all people", "%", 1, "rate", "Children aged 3 or 4 who live in households, as a share of all the people of the area (table B09001, households only).", "ACS B09001, B01001")),
    ("acs_age5to17_pct", ("People and age", "People aged 5 to 17, % of all people", "%", 1, "rate", "Share of the people of the area who are 5 to 17 years old.", "ACS B01001")),
    ("acs_age18to24_pct", ("People and age", "People aged 18 to 24, % of all people", "%", 1, "rate", "Share of the people of the area who are 18 to 24 years old.", "ACS B01001")),
    ("acs_age25to44_pct", ("People and age", "People aged 25 to 44, % of all people", "%", 1, "rate", "Share of the people of the area who are 25 to 44 years old.", "ACS B01001")),
    ("acs_age45to64_pct", ("People and age", "People aged 45 to 64, % of all people", "%", 1, "rate", "Share of the people of the area who are 45 to 64 years old.", "ACS B01001")),
    ("acs_age18to44_pct", ("People and age", "People aged 18 to 44, % of all people", "%", 1, "rate", "Share of the people of the area who are 18 to 44 years old: the age group published for barrios and census tracts in place of 18 to 24 and 25 to 44, which are too rough there.", "ACS B01001")),
    # counts of the same age groups (added 2026-10-18, when the catalog had room): municipios only (EXCLUDED); the table population_age.json keeps the broad groups' counts below
    ("acs_age_under3", ("People and age", "Children under 3 (in households)", "", 0, "count", "Children under 3 years old who live in households (table B09001, households only: the few in group quarters are left out).", "ACS B09001")),
    ("acs_age3to4", ("People and age", "Children aged 3 and 4 (in households)", "", 0, "count", "Children aged 3 or 4 who live in households (table B09001, households only).", "ACS B09001")),
    ("acs_age5to17", ("People and age", "People aged 5 to 17", "", 0, "count", "People of the area who are 5 to 17 years old.", "ACS B01001")),
    ("acs_age18to24", ("People and age", "People aged 18 to 24", "", 0, "count", "People of the area who are 18 to 24 years old.", "ACS B01001")),
    ("acs_age25to44", ("People and age", "People aged 25 to 44", "", 0, "count", "People of the area who are 25 to 44 years old.", "ACS B01001")),
    ("acs_age45to64", ("People and age", "People aged 45 to 64", "", 0, "count", "People of the area who are 45 to 64 years old.", "ACS B01001")),
    ("acs_age65plus", ("People and age", "People 65 and older", "", 0, "count", "People of the area who are 65 years old or older.", "ACS B01001")),
    ("acs_under18", ("People and age", "People under 18", "", 0, "count", "People of the area who are under 18 years old.", "ACS B01001")),
    ("acs_age18to44", ("People and age", "People aged 18 to 44", "", 0, "count", "People of the area who are 18 to 44 years old: the age group published for barrios and census tracts in place of 18 to 24 and 25 to 44, which are too rough there.", "ACS B01001")),
    ("acs_female_pct", ("People and age", "Women and girls, % of all people", "%", 1, "rate", "Share of the people of the area who are female.", "ACS B01001")),
    ("acs_family_households_pct", ("Household types", "Family households, % of all households", "%", 1, "rate", "Share of households that are family households: the householder lives with at least one relative.", "ACS B11001")),
    ("acs_living_alone_pct", ("Household types", "One-person households, % of all households", "%", 1, "rate", "Share of households in which the householder lives alone.", "ACS B11001")),
    ("acs_veteran_pct", ("Disability and veterans", "Veterans, % of civilians 18 and older", "%", 1, "rate", "Share of civilians 18 and older who are veterans.", "ACS B21001")),
    ("acs_uninsured_pct", ("Health insurance", "People without health insurance, % of people outside institutions", "%", 1, "rate", "Share of the civilian population living outside institutions who have no health insurance coverage of any kind (private or public: employer, direct purchase, Medicare, Medicaid or Plan Vital, military or VA), as the survey asks.", "ACS B27010")),
    ("acs_no_hs_pct", ("Education level", "Adults 25+ without a high school diploma, % of adults 25+", "%", 1, "rate", "Share of adults 25 and older whose highest schooling is below a high school diploma or its equivalent (no schooling up to 12th grade without a diploma).", "ACS B15002")),
    ("acs_disability_pct", ("Disability and veterans", "People with a disability, % of people outside institutions", "%", 1, "rate", "Share of the civilian population living outside institutions who have a disability (hearing, vision, cognitive, walking, self-care or independent-living difficulty, as the survey asks).", "ACS B18101")),
    # added 2026-11-14 (decision 107, step 1)
    ("acs_english_lt_very_well_pct", ("Language", "People who speak English less than \"very well\", % of people 5 and older", "%", 1, "rate", "Share of people 5 and older who speak a language other than English at home and say they speak English \"well\", \"not well\" or \"not at all\". The rest speak only English at home or say they speak English \"very well\". The answer is the person's own rating, not a test.", "ACS B16004")),
    ("acs_pan_hh_pct", ("Poverty and assistance", "Households that received nutrition assistance (PAN), % of all households", "%", 1, "rate", "Share of households in which someone received benefits of the Programa de Asistencia Nutricional (PAN) in the past 12 months. The Census Bureau's table calls it Food Stamps/SNAP; in Puerto Rico the survey asks about the PAN.", "ACS B22010")),
    ("acs_child_poverty_pct", ("Poverty and assistance", "Children under 18 below the poverty level, % of children under 18", "%", 1, "rate", "Share of children under 18 whose family income in the past 12 months was below the federal poverty level, among the children for whom the survey determines poverty status.", "ACS B17001")),
    ("acs_senior_poverty_pct", ("Poverty and assistance", "People 65 and older below the poverty level, % of people 65 and older", "%", 1, "rate", "Share of people 65 and older whose income in the past 12 months was below the federal poverty level, among those for whom the survey determines poverty status.", "ACS B17001")),
])


def derive_pop(rec):
    """The Population domain's variables for one area: {key: (value, margin)} from the cells of B01003, B01001, B11001, B18101, B21001, B27010 and B15002."""
    c = hs.Cells(rec)
    one, out = c.cell, {}

    def put(k, v, m=None):
        if v is not None:
            out[k] = (round(v, 2) if isinstance(v, float) else v, None if m is None else round(m, 2))

    put("acs_population", *one("B01003", 1))
    tot = one("B01001", 1)
    if tot[0] is not None and tot[1] is None:   # the Census Bureau controls the total of the island and of 76 municipios to its own estimate and gives it no margin: it is given a margin of zero (the Bureau says it may be treated as zero), so a share of it keeps the margin of its numerator (hs.pct would drop it)
        tot = (tot[0], 0.0)
    put("acs_under18_pct", *hs.pct(c.sum("B01001", UNDER18), tot))
    put("acs_age65plus_pct", *hs.pct(c.sum("B01001", AGE65), tot))
    put("acs_female_pct", *hs.pct(one("B01001", 26), tot))
    ages = age_counts(c)
    for k in ("acs_age_under3", "acs_age3to4", "acs_age5to17", "acs_age18to24", "acs_age25to44", "acs_age45to64", "acs_age18to44"):
        put(k + "_pct", *hs.pct(ages[k], tot))
    for k in AGE_COUNTS:   # a count made only of cells the Census Bureau controls has no margin (it is not exact), never a zero one (as age_values)
        put(k, ages[k][0], ages[k][1] or None)
    hh = one("B11001", 1)
    put("acs_family_households_pct", *hs.pct(one("B11001", 2), hh))
    put("acs_living_alone_pct", *hs.pct(one("B11001", 8), hh))
    put("acs_veteran_pct", *hs.pct(one("B21001", 2), one("B21001", 1)))
    put("acs_disability_pct", *hs.pct(c.sum("B18101", DISABILITY), one("B18101", 1)))
    put("acs_uninsured_pct", *hs.pct(c.sum("B27010", NO_COVERAGE), one("B27010", 1)))
    put("acs_no_hs_pct", *hs.pct(c.sum("B15002", NO_DIPLOMA), one("B15002", 1)))
    five = one("B16004", 1)
    if five[0] is not None and five[1] is None:   # the people 5 and older of the island and of most municipios are a controlled total, as B01001's (above)
        five = (five[0], 0.0)
    well = hs.pct(c.sum("B16004", ENGLISH_WELL), five)
    if well[0] is not None:   # the complement of a share has the share's margin
        put("acs_english_lt_very_well_pct", round(100 - well[0], 2), well[1])
    put("acs_pan_hh_pct", *hs.pct(one("B22010", PAN), one("B22010", 1)))
    put("acs_child_poverty_pct", *part_of(c, "B17001", CHILD_POOR, CHILD_NOT_POOR))
    put("acs_senior_poverty_pct", *part_of(c, "B17001", SENIOR_POOR, SENIOR_NOT_POOR))
    return out


def part_of(c, table, part, rest):
    """The share (percent, margin) that the cells `part` are of `part` and `rest` together: an age group below the poverty level over the same age group below and at or above it."""
    a, b = c.sum(table, part), c.sum(table, rest)
    if a[0] is None or b[0] is None:
        return None, None
    return hs.pct(a, (a[0] + b[0], sqrt(a[1] ** 2 + b[1] ** 2)))


def age_cells(lo, hi):
    """The B01001 cells (men and women) of the age groups that lie inside [lo, hi] (hi None: 'and over'), from the labels in AGES."""
    out = []
    for i, label in enumerate(AGES):
        a, b = age_bounds(label)
        if a >= lo and (hi is None or (b is not None and b <= hi)):
            out += [3 + i, 27 + i]
    return sorted(out)


def age_bounds(label):
    """(first, last) age of a B01001 label: 'Under 5 years' (0, 4), '15 to 17 years' (15, 17), '60 and 61 years' (60, 61), '20 years' (20, 20), '85 years and over' (85, None)."""
    w = label.replace(" years", "").replace(" and over", "+").split()
    if w[0] == "Under":
        return 0, int(w[1]) - 1
    if w[0].endswith("+"):
        return int(w[0][:-1]), None
    if len(w) == 1:
        return int(w[0]), int(w[0])
    return int(w[0]), int(w[2])


def age_counts(c):
    """{key: (count, margin)} of every five-year band and age group of one area (hs.Cells over B01001 and B09001); a sum adds its margins in quadrature, a controlled cell adds none."""
    out = {k: c.sum("B01001", age_cells(*r)) for k, r in AGE_BANDS + AGE_GROUPS}
    for k, n in YOUNG.items():
        out[k] = c.cell("B09001", n)
    return out


# ── Which variables each level publishes ─────────────────────────────────────
WAVE1 = ["acs_population", "housing_units", "households", "owner_occupied_pct", "vacancy_pct", "other_vacant_pct", "avg_household_size", "overcrowded_pct", "median_home_value", "per_capita_income"]
AGE = ["median_age", "acs_under18_pct", "acs_age65plus_pct"]
WAVE2 = ["median_hh_income", "median_gross_rent", "median_rent_pct_income", "median_year_built", "seasonal_pct", "detached_house_pct", "apartments_5plus_pct", "mobile_home_pct",
         "poverty_pct", "unemployment_rate_pct", "employment_rate_pct", "bachelors_pct", "no_vehicle_hh_pct", "internet_subscription_pct", "no_internet_pct", "gini",
         "acs_female_pct", "acs_family_households_pct", "acs_living_alone_pct", "acs_veteran_pct", "acs_disability_pct", "acs_uninsured_pct", "acs_no_hs_pct",
         "acs_age18to44_pct", "acs_age45to64_pct",   # the two new age groups below the municipio (AGE_SMALL; 2026-10-18); their counts are municipio only (EXCLUDED)
         "acs_english_lt_very_well_pct", "acs_pan_hh_pct"]   # 2026-11-14 (decision 107): flagged for under half of the barrios in 2020-2024; poverty by age is municipio only (EXCLUDED)
SELECTION = {"block-group": WAVE1 + AGE, "tract": WAVE1 + AGE + WAVE2, "barrio": WAVE1 + AGE + WAVE2}
# what is not published below the municipio, and why (docs/small-area.md)
EXCLUDED = {
    "renter_cost_burden_pct": "the margin of the share of renters paying 30% or more of income is about 36 points for a tract and 55 for a block group",
    "renter_severe_burden_pct": "same",
    "owner_cost_burden_pct": "same",
    "max_affordable_loan": "a calculation with the assumptions of the 2023 study (30% of income, 5% interest), not a survey figure",
    "affordability_ratio": "same",
    "rental_vacancy_pct": "the denominators are a handful of homes",
    "homeowner_vacancy_pct": "the denominators are a handful of homes",
    "median_owner_income": "published for tracts but not block groups; left for a later wave",
    "median_renter_income": "same",
    "median_owner_costs_mortgage": "left for a later wave",
    "median_owner_costs_no_mortgage": "left for a later wave",
    "acs_age_under3_pct": "the margin is above 30% of the estimate for 99% or more of the barrios and tracts (2020-2024): municipios only",
    "acs_age3to4_pct": "same",
    "acs_age5to17_pct": "the share is flagged less reliable for 79% of the barrios (2020-2024): municipios only; under 18 is published below the municipio",
    "acs_age18to24_pct": "the share is flagged less reliable for 89% of the barrios (2020-2024): municipios only; 18 to 44 is published below the municipio",
    "acs_age25to44_pct": "the share is flagged less reliable for 53% of the barrios (2020-2024): municipios only; 18 to 44 is published below the municipio",
    "acs_age_under3": "as its share: municipios only",
    "acs_age3to4": "same",
    "acs_age5to17": "same",
    "acs_age18to24": "same",
    "acs_age25to44": "same",
    "acs_under18": "the count is flagged less reliable for 84% of the barrios (2020-2024; its share 70%): municipios only, by the rule that an item below the municipio must be flagged for under half of the barrios",
    "acs_age18to44": "the count is flagged for 65% of the barrios (its share 39%): municipios only, by the same rule",
    "acs_age45to64": "the count is flagged for 61% of the barrios (its share 31%): municipios only, by the same rule",
    "acs_age65plus": "the count is flagged for 61% of the barrios (its share 36%): municipios only, by the same rule",
    "acs_child_poverty_pct": "the share is flagged less reliable for 69% of the barrios and 65% of the census tracts (2020-2024): municipios only, by the same rule",
    "acs_senior_poverty_pct": "the share is flagged less reliable for 64% of the barrios and 57% of the census tracts (2020-2024): municipios only, by the same rule",
}
# Tables the Census Bureau does not publish for block groups (B17001 poverty, B19083 Gini, B25119 income by tenure, B18101 disability): level_file() finds that every value of their
# variables is empty at that level and leaves them out of the file (notes.left_out), whatever SELECTION says.


# ── Reading ──────────────────────────────────────────────────────────────────

def records(level, vintage, refresh=False):
    """{geoid: {cell: [estimate, margin]}} for every area of a level, from every table (cached by acs_small under cache/acs_small)."""
    rec = {}
    for t in TABLES:
        r = acs_small.read_table(t, vintage, [level], refresh=refresh)
        for gid, cells in r["levels"][level].items():
            rec.setdefault(gid, {}).update(cells)
    return rec


MEDIANS = {"median_age", "median_hh_income", "median_gross_rent", "median_rent_pct_income", "median_home_value", "median_year_built"}


def clean(out):
    """Takes out of {key: (value, margin)} what the Census Bureau prints but is not an estimate, and a margin that would read as exact:
    - a median that falls in the lowest or highest interval of an open-ended distribution arrives with its boundary as the value and no margin (code -333333333, marked ***: 51 for 'rent is 50% or
      more of income', 2,499 for 'under $2,500', 1938 for 'built before 1939'); a median of 0 is the same edge in the oldest window (the 2017-2021 file prints 0 where later files print the boundary 1938 or a real median). Neither is a median: no value.
    - a share whose margin works out to zero: the proportion formula gives zero for a share of 100% (the numerator is the whole) and whenever the numerator's margin equals the share times the denominator's
      margin (43.64% of 440, 50% of 8 and 88.46% of 1,664 are three of them). A margin of zero would read as exact: no margin. The Census Bureau prints a zero margin in none of its cells.
    A median with an estimate and no margin is what the first case looks like in the cache (it keeps None for every negative code); a median cannot be a controlled total."""
    for k in list(out):
        v, m = out[k]
        if k in MEDIANS and v is not None and (m is None or v == 0):
            del out[k]
        elif k.endswith("_pct") and m == 0:
            out[k] = (v, None)
    return out


def variables(rec, vintage):
    out = {}
    out.update(hs.derive(rec, vintage))
    out.update(es.derive_econ(rec))
    out.update(derive_pop(rec))
    return clean(out)


# ── The files ────────────────────────────────────────────────────────────────

def crosswalk(path=None):
    """{level: [ids in the order of the crosswalk]} from site/data/geo/crosswalk.json."""
    p = Path(path or OUT / "geo" / "crosswalk.json")
    cw = json.loads(p.read_text(encoding="utf-8"))
    return {lv: [r[0] for r in rows] for lv, rows in cw["units"].items()}


def tidy(x):
    """A whole number as an integer (the file is smaller and a count reads as a count)."""
    return int(x) if isinstance(x, float) and x == int(x) else x


def level_file(level, vintages=None, refresh=False, ids=None):
    """The document of one sub-municipal level: values and margins of error, one array per window, in the order of the crosswalk's ids for the level."""
    vintages = vintages or VINTAGES
    ids = ids or crosswalk()[level]
    keys = [k for k in SELECTION[level]]
    acc = {k: {"years": {}, "moe": {}} for k in keys}
    for v in vintages:
        log(f"  {level} {v - 4}-{v}")
        derived = {gid: variables(rec, v) for gid, rec in records(level, v, refresh).items()}
        for k in keys:
            vals = [derived.get(g, {}).get(k) for g in ids]
            acc[k]["years"][str(v)] = [None if x is None else tidy(x[0]) for x in vals]
            acc[k]["moe"][str(v)] = [None if x is None or x[1] is None else tidy(x[1]) for x in vals]
    vs, left_out = [], []
    for k in keys:
        if not any(x is not None for y in acc[k]["years"].values() for x in y):   # a table the Census Bureau does not publish for this level
            left_out.append(k)
            continue
        vs.append({"key": k, "years": acc[k]["years"], "moe": acc[k]["moe"]})
    notes = {"windows": [f"{v - 4}-{v}" for v in vintages], "left_out": left_out, "areas": len(ids), "source": "ACS 5-year table-based summary files, read by acs_small.py"}
    return {"built": date.today().isoformat(), "level": level, "windows": list(vintages), "geo": {"ids": ids}, "vars": vs, "notes": notes}


def population_file(vintages=None, refresh=False):
    """population_series.json: the Population domain's variables for the 78 municipios and Puerto Rico (the last entry), in the shape of economy_series.json."""
    vintages = vintages or VINTAGES
    names, fips = hs.municipalities()
    ids = list(fips) + ["72"]
    years, moes = {k: {} for k in POP_VARS}, {k: {} for k in POP_VARS}
    for v in vintages:
        rec = {}
        for t in ["B01003", *POP_TABLES]:
            r = acs_small.read_table(t, v, ["municipio", "island"], refresh=refresh)
            for lv in ("municipio", "island"):
                for gid, cells in r["levels"][lv].items():
                    rec.setdefault(gid, {}).update(cells)
        derived = {gid: clean(derive_pop(r)) for gid, r in rec.items()}
        for k in POP_VARS:
            vals = [derived.get(g, {}).get(k) for g in ids]
            years[k][str(v)] = [None if x is None else tidy(x[0]) for x in vals]
            moes[k][str(v)] = [None if x is None or x[1] is None else tidy(x[1]) for x in vals]
    vs = []
    for k, (group, label, unit, d, typ, definition, ref) in POP_VARS.items():
        vs.append({"key": k, "group": group, "label": label, "unit": unit, "d": d, "type": typ, "sources": ["acs"], "ref": ref, "definition": definition, "family": "population",
                   **({"residents": True} if k == "acs_population" else {}),   # the residents themselves: the engine does not divide them by the residents (core/normalize.js)
                   "years": years[k], "moe": moes[k]})
    return {"built": date.today().isoformat(), "years": list(vintages), "geo": {"ids": ids, "names": names + ["Puerto Rico"]}, "vars": vs}


AGE_LABELS = {   # what each count of population_age.json is, in English (the file is a table for download; no page shows these words)
    **{k: (f"People aged {lo} to {hi}" if hi is not None else f"People aged {lo} and over") for k, (lo, hi) in AGE_BANDS},
    "acs_age0to4": "Children under 5",
    "acs_age_under3": "Children under 3 (in households)", "acs_age3to4": "Children aged 3 and 4 (in households)", "acs_age5to17": "People aged 5 to 17",
    "acs_age18to24": "People aged 18 to 24", "acs_age25to44": "People aged 25 to 44", "acs_age45to64": "People aged 45 to 64", "acs_age65plus": "People 65 and older",
    "acs_under18": "People under 18", "acs_age18to44": "People aged 18 to 44",
}


def age_values(rec, keys):
    """{key and key_pct: (value, margin)} for one area: the count of each age band or group and its share of all people (B01001_001). A controlled total is given a margin of
    zero (derive_pop), so a share keeps the margin of its count; a count whose cells are all controlled has no margin (the Census Bureau prints none: it is not exact)."""
    c = hs.Cells(rec)
    tot = c.cell("B01001", 1)
    if tot[0] is not None and tot[1] is None:
        tot = (tot[0], 0.0)
    ages = age_counts(c)
    out = {}
    for k in keys:
        n, m = ages[k]
        if n is None:
            continue
        out[k] = (tidy(n), None if not m else round(m, 2))
        sh = hs.pct((n, m), tot)
        if sh[0] is not None:
            out[k + "_pct"] = (sh[0], None if sh[1] is None or sh[0] == 100 or sh[1] == 0 else sh[1])
    return out


AGE_MUNI = [k for k, _ in AGE_BANDS] + ["acs_age_under3", "acs_age3to4"] + [k for k, _ in AGE_GROUPS]


def age_file(vintages=None, refresh=False):
    """population_age.json: counts and shares (with margins) of the five-year age bands and the age groups, for the 78 municipios and Puerto Rico (geo.ids, the last is 72),
    and of the groups in AGE_SMALL for the 901 barrios and 981 census tracts (levels.barrio, levels.tract; the crosswalk's ids and order). Windows as the other files."""
    vintages = vintages or VINTAGES
    names, fips = hs.municipalities()
    cw = crosswalk()
    plan = {"municipio": (list(fips) + ["72"], AGE_MUNI), "barrio": (cw["barrio"], AGE_SMALL), "tract": (cw["tract"], AGE_SMALL)}
    acc = {lv: {} for lv in plan}
    for v in vintages:
        for lv, (ids, keys) in plan.items():
            levels = ["municipio", "island"] if lv == "municipio" else [lv]
            rec = {}
            for t in ("B01001", "B09001"):
                r = acs_small.read_table(t, v, levels, refresh=refresh)
                for x in levels:
                    for gid, cells in r["levels"][x].items():
                        rec.setdefault(gid, {}).update(cells)
            vals = {g: age_values(r, keys) for g, r in rec.items()}
            for k in keys:
                for kk in (k, k + "_pct"):
                    a = acc[lv].setdefault(kk, {"years": {}, "moe": {}})
                    got = [vals.get(g, {}).get(kk) for g in ids]
                    a["years"][str(v)] = [None if x is None else x[0] for x in got]
                    a["moe"][str(v)] = [None if x is None or x[1] is None else tidy(x[1]) for x in got]

    def block(lv):
        out = []
        for k in plan[lv][1]:
            out.append({"key": k, "label": AGE_LABELS[k], "unit": "people", **acc[lv][k]})
            out.append({"key": k + "_pct", "label": AGE_LABELS[k] + ", % of all people", "unit": "%", **acc[lv][k + "_pct"]})
        return out
    return {"built": date.today().isoformat(), "windows": list(vintages), "geo": {"ids": plan["municipio"][0], "names": names + ["Puerto Rico"]}, "vars": block("municipio"),
            "levels": {lv: {"ids": plan[lv][0], "vars": block(lv)} for lv in ("barrio", "tract")},
            "notes": {"windows": [f"{v - 4}-{v}" for v in vintages], "source": "ACS 5-year tables B01001 (Sex by Age) and B09001 (Population Under 18 Years by Age), read by acs_small.py",
                      "bands": "Five-year bands from B01001, whose own groups are added where they are narrower (15-17 and 18-19; 20, 21 and 22-24; 60-61 and 62-64; 65-66 and 67-69). Published for the municipios only: below them the margin is above 30% of the estimate for 89% or more of the barrios and 95% or more of the census tracts (2020-2024).",
                      "under_5": "Under 3 and 3-4 come from B09001, which counts children in households only; the band 0 to 4 (B01001) also counts the few in group quarters, so under 3 plus 3-4 can be a little below it.",
                      "below_the_municipio": "Barrios and census tracts get the age groups whose share is flagged less reliable (margin above 30% of the estimate) for under half of the barrios in 2020-2024: 18 to 44 (39%), 45 to 64 (31%), 65 and over (36%), and under 18 (70%), which the observatory has published since 2026-10-06. 5 to 17 (79%), 18 to 24 (89%), 25 to 44 (53%), under 3 and 3 to 4 (99% or more) are left out.",
                      "margins": "90% margins of error by the Census Bureau's formulas: a sum adds its cells' margins in quadrature; a share uses the proportion formula over all people. Where the Census Bureau controls a cell to its own estimates it prints no margin; such a cell adds none, and a count made only of such cells has no margin (it is not exact). A share of 100% has no margin.",
                      "sum": "In each area the five-year bands add up to all people (B01001_001), and so do under 5, 5-17, 18-24, 25-44, 45-64 and 65+; and under 18, 18-44, 45-64 and 65+."}}


# ── The cells are the ones the formulas say they are ─────────────────────────
AGES = ["Under 5 years", "5 to 9 years", "10 to 14 years", "15 to 17 years", "18 and 19 years", "20 years", "21 years", "22 to 24 years", "25 to 29 years", "30 to 34 years",
        "35 to 39 years", "40 to 44 years", "45 to 49 years", "50 to 54 years", "55 to 59 years", "60 and 61 years", "62 to 64 years", "65 and 66 years", "67 to 69 years", "70 to 74 years",
        "75 to 79 years", "80 to 84 years", "85 years and over"]
LABELS = acs_small.CACHE / "labels"
LABEL_FIXTURES = ROOT / "tests" / "fixtures" / "acs_labels"   # the labels of the five tables in every vintage, committed so that the check also runs where the cache is not


def group_labels(group, year):
    """{cell: label} of one table from the Census Bureau's own table definitions (a keyless metadata request, cached)."""
    import requests
    p = LABELS / f"{group}_{year}.json"
    for q in (p, LABEL_FIXTURES / p.name):
        if q.exists():
            return json.loads(q.read_text(encoding="utf-8"))
    r = requests.get(f"https://api.census.gov/data/{year}/acs/acs5/groups/{group}.json", headers=acs_small.UA, timeout=60)
    r.raise_for_status()
    out = {k[:-1]: v["label"] for k, v in r.json()["variables"].items() if k.endswith("E") and k[0] == "B"}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def check_labels(year=VINTAGES[-1]):
    """Problems (a list of texts) with the cell numbers the Population variables use, found by reading what the Census Bureau says each cell is."""
    bad = []
    L = group_labels("B01001", year)
    want_under, want_65 = set(), set()
    for sex, base in (("Male", 3), ("Female", 27)):
        for i, age in enumerate(AGES):
            cell = f"B01001_{base + i:03d}"
            if L.get(cell) != f"Estimate!!Total:!!{sex}:!!{age}":
                bad.append(f"{cell} is {L.get(cell)!r}, not {sex} {age}")
            if age in AGES[:4]:
                want_under.add(base + i)
            if i >= AGES.index("65 and 66 years"):
                want_65.add(base + i)
    if set(UNDER18) != want_under or set(AGE65) != want_65:
        bad.append("UNDER18 or AGE65 is not the set of cells for under 18 or 65 and older")
    if L.get("B01001_001") != "Estimate!!Total:" or L.get("B01001_026") != "Estimate!!Total:!!Female:":
        bad.append("B01001_001 or B01001_026 is not the total or the women")
    covered = sorted(c for _, r in AGE_BANDS for c in age_cells(*r))
    if covered != list(range(3, 26)) + list(range(27, 50)):
        bad.append("the five-year age bands do not cover every age cell of B01001 exactly once")
    for k, r in AGE_GROUPS:
        if not age_cells(*r):
            bad.append(f"{k}: no B01001 cell lies in ages {r}")
    if set(age_cells(0, 17)) != set(UNDER18) or set(age_cells(65, None)) != set(AGE65):
        bad.append("age_cells does not give the cells of UNDER18 and AGE65")
    y9 = group_labels("B09001", year)
    if (y9.get("B09001_001"), y9.get("B09001_003"), y9.get("B09001_004")) != ("Estimate!!Total:", "Estimate!!Total:!!In households:!!Under 3 years", "Estimate!!Total:!!In households:!!3 and 4 years"):
        bad.append("B09001 cells 1, 3 and 4 are not the total, children under 3 and children aged 3 and 4 in households")
    d = group_labels("B18101", year)
    with_dis = {int(k[-3:]) for k, v in d.items() if v.endswith("With a disability")}
    if with_dis != set(DISABILITY) or d.get("B18101_001") != "Estimate!!Total:":
        bad.append(f"DISABILITY is not the set of 'With a disability' cells of B18101: {sorted(with_dis)}")
    h = group_labels("B11001", year)
    if (h.get("B11001_001"), h.get("B11001_002"), h.get("B11001_008")) != ("Estimate!!Total:", "Estimate!!Total:!!Family households:", "Estimate!!Total:!!Nonfamily households:!!Householder living alone"):
        bad.append("B11001 cells 1, 2 and 8 are not the total, family households and householders living alone")
    v = group_labels("B21001", year)
    if (v.get("B21001_001"), v.get("B21001_002")) != ("Estimate!!Total:", "Estimate!!Total:!!Veteran"):
        bad.append("B21001 cells 1 and 2 are not the total and veterans")
    ins = group_labels("B27010", year)
    if {int(k[-3:]) for k, v in ins.items() if v.endswith("No health insurance coverage")} != set(NO_COVERAGE) or ins.get("B27010_001") != "Estimate!!Total:":
        bad.append("NO_COVERAGE is not the set of 'No health insurance coverage' cells of B27010")
    ed = group_labels("B15002", year)
    below = {"No schooling completed", "Nursery to 4th grade", "5th and 6th grade", "7th and 8th grade", "9th grade", "10th grade", "11th grade", "12th grade, no diploma"}
    if {int(k[-3:]) for k, v in ed.items() if v.split("!!")[-1] in below} != set(NO_DIPLOMA) or ed.get("B15002_001") != "Estimate!!Total:":
        bad.append("NO_DIPLOMA is not the set of cells below a high school diploma of B15002")
    if group_labels("B01003", year).get("B01003_001") != "Estimate!!Total":
        bad.append("B01003_001 is not the total population")
    lang = group_labels("B16004", year)
    well = {int(k[-3:]) for k, v in lang.items() if v.split("!!")[-1] in ("Speak only English", 'Speak English "very well"')}
    if well != set(ENGLISH_WELL) or lang.get("B16004_001") != "Estimate!!Total:":
        bad.append(f"ENGLISH_WELL is not the set of the cells of B16004 that speak only English or speak English very well: {sorted(well)}")
    pan = group_labels("B22010", year)
    if (pan.get("B22010_001"), pan.get(f"B22010_{PAN:03d}")) != ("Estimate!!Total:", "Estimate!!Total:!!Household received Food Stamps/SNAP in the past 12 months:"):
        bad.append("B22010 cells 1 and 2 are not the households and those that received Food Stamps/SNAP")
    pov = group_labels("B17001", year)
    kids = {"Under 5 years", "5 years", "6 to 11 years", "12 to 14 years", "15 years", "16 and 17 years"}
    old = {"65 to 74 years", "75 years and over"}
    for name, ages, below, above in (("CHILD", kids, CHILD_POOR, CHILD_NOT_POOR), ("SENIOR", old, SENIOR_POOR, SENIOR_NOT_POOR)):
        got = {side: {int(k[-3:]) for k, v in pov.items() if v.split("!!")[-1] in ages and f"!!Income in the past 12 months {side} poverty level:!!" in v} for side in ("below", "at or above")}
        if got["below"] != set(below) or got["at or above"] != set(above):
            bad.append(f"{name}_POOR or {name}_NOT_POOR is not the set of B17001 cells of that age below and at or above the poverty level: {sorted(got['below'])}, {sorted(got['at or above'])}")
    return bad


# ── How rough are the published values ───────────────────────────────────────

def unreliable(estimate, margin):
    """The engine's rule (site/js/core/reliability.js, isUnreliable): a margin of error above 30% of the estimate, or any margin on an estimate of zero."""
    return estimate is not None and margin is not None and margin > 0 and (estimate == 0 or margin / abs(estimate) > 0.3)


def measure(window=None):
    """{key: {level: {areas, value, typical, flagged, with_margin}}} for one window (the latest) of the published files, 'municipio' included: `value` is the number of areas with an estimate,
    `with_margin` those that also have a margin, `typical` the median margin as a percent of the estimate over the areas that have both, `flagged` the values the engine would call less reliable."""
    docs = {lv: json.loads((OUT / name).read_text(encoding="utf-8")) for lv, name in FILES.items()}
    window = str(window or VINTAGES[-1])
    mun = {}
    for name in (POP_FILE, "housing_series.json", "economy_series.json"):
        for v in json.loads((OUT / name).read_text(encoding="utf-8"))["vars"]:
            if (v.get("years") or {}).get(window) and (v.get("moe") or {}).get(window):
                mun[v["key"]] = (v["years"][window][:78], v["moe"][window][:78])   # the island is the last value: left out

    def stat(est, moe):
        have = [(e, m) for e, m in zip(est, moe) if e is not None]
        with_m = [(e, m) for e, m in have if m is not None]
        ratios = [m / abs(e) for e, m in with_m if e]
        return {"areas": len(est), "value": len(have), "typical": round(statistics.median(ratios) * 100, 2) if ratios else None,
                "flagged": sum(unreliable(e, m) for e, m in with_m), "with_margin": len(with_m)}
    out = OrderedDict()
    for lv in FILES:
        for v in docs[lv]["vars"]:
            row = out.setdefault(v["key"], OrderedDict())
            if v["key"] in mun and "municipio" not in row:
                row["municipio"] = stat(*mun[v["key"]])
            row[lv] = stat(v["years"][window], v["moe"][window])
    return out


def share_text(n, total):
    """n of total as a percent in words that stay true: 'less than 1%' and 'more than 99%' instead of a rounding to 0% or 100%."""
    if total == 0 or n == 0:
        return "0%"
    if n == total:
        return "100%"
    f = n / total * 100
    return "less than 1%" if f < 1 else "more than 99%" if f > 99 else f"{int(f + 0.5)}%"


def measure_table(window=None):
    """The measurement as a Markdown table: typical margin / share flagged, level by level."""
    labels = {v["key"]: v["label"] for name in (POP_FILE, "housing_series.json", "economy_series.json") for v in json.loads((OUT / name).read_text(encoding="utf-8"))["vars"]}

    def cell(r):
        if not r:
            return "not published"
        if r["with_margin"] < 0.5 * r["value"]:
            return f"no margin for {r['value'] - r['with_margin']} of {r['value']}"
        t = f"{int(r['typical'] + 0.5)}%" if r["typical"] is not None else "-"
        s = f"{t} / {share_text(r['flagged'], r['value']).replace('less than ', '<').replace('more than ', '>')}"
        return s + (f" (margin for {r['with_margin']} of {r['value']})" if r["with_margin"] < r["value"] else "")
    lines = ["| Variable | Municipios | Barrios | Census tracts | Block groups |", "|---|---|---|---|---|"]
    for k, row in measure(window).items():
        lines.append(f"| {labels.get(k, k)} (`{k}`) | " + " | ".join(cell(row.get(lv)) for lv in ("municipio", "barrio", "tract", "block-group")) + " |")
    return "\n".join(lines)


# ── Build and check ──────────────────────────────────────────────────────────

def dump(doc):
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


def build(refresh=False, check=False, vintages=None):
    vintages = vintages or VINTAGES
    problems = [f"{y}: {p}" for y in vintages for p in check_labels(y)]
    if problems:
        raise SystemExit("small_area: the Census Bureau's cell labels are not what the formulas expect:\n  " + "\n  ".join(problems))
    docs = {POP_FILE: population_file(vintages, refresh), AGE_FILE: age_file(vintages, refresh)}
    for level, name in FILES.items():
        docs[name] = level_file(level, vintages, refresh)
    stale = 0
    for name, doc in docs.items():
        p = OUT / name
        if check:
            old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
            same = old is not None and {**old, "built": None} == {**json.loads(dump(doc)), "built": None}
            print(f"  {name}: {'matches' if same else 'DIFFERS'}")
            stale += not same
            continue
        p.write_text(dump(doc), encoding="utf-8")
        log(f"wrote {name} ({p.stat().st_size / 1024:.0f} KB, {len(doc['vars'])} variables)")
    return 1 if stale else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--measure" in sys.argv:
        print(measure_table())
        raise SystemExit(0)
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
