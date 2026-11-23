# Public money v2, step 2: which federal programs can be mapped by municipio (decision 69)

Checks run on 2026-10-31 for HANDOFF decision 69. USAspending can split federal money by assistance listing and municipio, but for many programs it records the money where a Commonwealth agency is (San Juan) or names no municipio at all. A map of that money would show where it was recorded, not where it went. This folder holds the rule the observatory uses, the evidence behind it and an outside check.

## The placement rule
A listing is mapped, and a fiscal year of it kept, only when the year passes all three tests (`economy_series.py`, `placement()`, `passes()`, `kept_years()`):

- at least **20 municipios** have money;
- **San Juan holds under 40%** of the money placed in municipios;
- **at most 50%** of Puerto Rico's money names no municipio.

A series keeps its **latest unbroken run** of passing years. A newer year that fails is left out (the build prints a warning) instead of cutting the series.

## Files
- `candidates.py` and `candidates_fy2019_fy2024.json`: the first screen, 26 listings and 15 agencies in FY2019 and FY2024 (municipios with money, San Juan's share).
- `program_check.py` and `program_check.json`: for the seven listings kept, every year's three tests, the years kept, the start year under other thresholds, coverage of all federal awards, and the comparison with SSA.
- `ssa/`: SSA, *OASDI Beneficiaries by State and County*, Puerto Rico workbooks for December 2013 and December 2024 (US government work). ssa.gov refuses scripted downloads, so they were saved from a browser.

## Results
- **Kept:** Social Security retirement, disability and survivors (FY2012 to FY2025), veterans disability compensation (FY2011 to FY2025), Pell Grants (FY2015 to FY2025), Head Start (FY2017 to FY2025), Project-Based Rental Assistance (FY2019 to FY2025).
- **Not mapped:** agency totals (FY2024 San Juan shares: HHS 78%, Homeland Security 97%, HUD 70%, Education 63%, Commerce 99%), COVID money (99%) and infrastructure-law money (90%); Section 8 vouchers (52-54%); Medicaid, nutrition assistance, highways, the revolving funds, school lunch and WIC, which name no municipio.
- **Breaks, not trends.** Each early failure ends in one step: Social Security goes from 54-69% in San Juan in FY2011 to 13-15% in FY2012, Head Start from 58% (FY2016) to 38% (FY2017), rental assistance from 55% (FY2018) to 32% (FY2019). That is a change in how the agency reported the place, so the series start after it.
- **Sensitivity.** With 10, 20 or 30 municipios and 35%, 40%, 45% or 50% for San Juan, Social Security and veterans compensation start in the same year every time; Head Start and rental assistance move only at 35%. **Pell depends on the limit**: FY2014 has 43% in San Juan, so it starts in FY2011 at 45%, FY2015 at 40% and FY2018 at 35%. The rule was set before these results and is not changed to fit; the Pell entry says so.
- **Outside check (Social Security).** Each municipio's share of USAspending's money matches its share of benefits in SSA's county table, which counts beneficiaries where they live: FY2025 against December 2024, correlation 0.9999 to 1.0 and largest gap 0.1 percentage points; FY2014 against December 2013, correlation 0.990 to 0.998 and largest gap 0.63 points. Totals differ by 0.4% to 9%, as expected between a fiscal year's obligations and twelve times one month's benefits. Veterans compensation, Pell, Head Start and rental assistance were not checked against an outside source.
- **Coverage.** The seven listings are 39.7% of all federal awards to Puerto Rico in FY2025 (17.6% to 39.7% over FY2021 to FY2025). Most federal money is not mapped by program; every entry says so.

## Step 3: Federal Audit Clearinghouse (decision 70)
`fac_check.py` and `fac_check.json` (no API call; reads `cache/economy/fac`): how the 3,039 Puerto Rico audits were narrowed to the 755 of the 78 municipio governments (two matched by EIN, 25 names with a municipio in them left out), who filed each year, totals, agency and direct shares, and two comparisons.

- **The award lines add up.** In every audit the award lines sum to the total the audit reports.
- **Who filed.** All 78 for FY2016, FY2021 and FY2022; 74 for FY2017, 77 for FY2018 and FY2019 (Culebra missing), 76 for FY2020, 77 for FY2023, 75 for FY2024 and 65 so far for FY2025.
- **Head Start.** The municipio governments' Head Start spending, FY2019 to FY2024, follows USAspending's Head Start money by municipio: correlation 0.849, $1.33 billion against $1.50 billion (USAspending also counts nonprofit grantees, and uses federal fiscal years).
- **FEMA Public Assistance.** Spent in all audits: $1.54 billion; obligated to the municipios as applicants (OpenFEMA): $8.65 billion; correlation 0.709; the median municipio has spent 21% (10th to 90th percentile 7% to 42%). Spent and obligated measure different things, and audits for FY2025 are incomplete.

Re-run after `economy_series.py --programs`:

    python docs/analysis/public-money-v2-2026-10/program_check.py

and after `economy_series.py --fac`:

    python docs/analysis/public-money-v2-2026-10/fac_check.py

## Step 4: tax credit housing and New Markets Tax Credits (decision 71)

No script: the checks are in the builders and the tests.

- **NMTC.** The sum of the Puerto Rico financial notes, $219.3 million in 73 investments, equals the sum of the 36 Puerto Rico projects' QLICI amounts in the file's project sheet ($219,280,101). Every note's tract is a Puerto Rico tract.
- **LIHTC.** All 245 Puerto Rico projects of HUD's database (release of 2026-05-28) are placed in a municipio. The tract's county and the listed city disagree for 2 of the 82 projects that have a tract (a city near a municipal line), which is why the tract wins. HUD's eGIS layer (last edited 2024-12-09) has 231 projects, placed in service through 2020 and 3 with the year not confirmed; the database has 245, 9 of them placed in service from 2021 to 2023.

## Step 5: money compared with need (decision 72)

The Knowledge Area page `site/public-money.html`, written by `make_page.py` here from `site/data/public_money_need.json` (`python public_money_need.py`, then `python docs/analysis/public-money-v2-2026-10/make_page.py`, then `python i18n.py`). The data file adds no source: it sums the FEMA series of `economy_series.json` and `housing_series.json` over 2017 to 2025 and copies two need measures from `environment_series.json` and `hazard_series.json`.

- Share of each program a municipio map can show, 2017 to 2025: Public Assistance 22.0% ($8.54 B of $38.90 B), Individual Assistance 100.0%, Hazard Mitigation 63.9%.
- Hazard Mitigation for Puerto Rico: $3.67 B approved, $0.77 B obligated, $1.06 B awaiting a decision, 543 approved subapplications; a payment is reported for 163 of 1,134 subapplications, so money paid is not shown.
- Rank correlations (Spearman, 78 municipios), money per resident against need: Public Assistance and expected loss per resident 0.12, Public Assistance and residents with three or more risk factors 0.39. The page shows the figure for whatever pair is chosen; it draws no conclusion from it.
- Checks: `tests/test_public_money_need.py` (the file equals a rebuild, placed money never exceeds the island, the page's figures come from the data, the hold is kept, every string has its Spanish) and `tests/public_money.test.js` (thirds, rank correlation with ties, median).
