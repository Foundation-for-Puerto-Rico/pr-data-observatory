# Small-area survey series: barrios, census tracts and block groups (plan item 7)

Built 2026-10-06. The observatory now publishes American Community Survey (ACS) 5-year estimates **below the municipality**, each estimate with its margin of error where the Census Bureau gives one: 901 barrios, 981 census tracts and 2,555 block groups, for four windows (2017-2021 to 2020-2024); and the first series of the Population domain (age, sex, household type, veterans, disability) for the 78 municipalities. All of it is aggregated survey data from the Census Bureau: no personal data.

**Read this before using a value below the municipality: it is rough.** In 2020-2024, for example, the margin of error is above 30% of the estimate (the engine's flag for "less reliable") for 2% of the census tracts with residents and 73% of the block groups when the variable is the number of people, and for 36% of the tracts when it is the median household income. Some variables are almost always flagged below the municipality, and six of them are rough for municipalities too (section 4). The map of the observatory still shows municipalities only; the areas below are in the files, in a CSV by area and in the layer engine.

## 1. The files

| File | Areas | Variables | Raw | Compressed (gzip) | Read when |
|---|---|---|---|---|---|
| `population_series.json` | 78 municipalities and Puerto Rico | 8 | 31 KB | 11 KB | the Economy tab opens, with `economy_series.json` and `housing_series.json` |
| `acs_barrio.json` | 901 barrios | 34 | 1.2 MB | 454 KB | a person asks for the level: dataset window, "Barrios" |
| `acs_tract.json` | 981 census tracts | 34 | 1.3 MB | 478 KB | the same, "Census tracts" |
| `acs_blockgroup.json` | 2,555 block groups | 13 | 1.3 MB | 483 KB | the same, "Block groups" |
| `population_age.json` | 78 municipalities and Puerto Rico; the broad age groups also for 901 barrios and 981 census tracts | 54 (municipalities), 8 (barrios and tracts) | 0.85 MB | 331 KB | no page: a table for download (section 9) |

`population_series.json` has the shape of `economy_series.json` (`years`, `geo.ids` ending with `72`, `vars[]` with `years` and `moe` by window). Each level file is `{ built, level, windows: [2021, ..., 2024], geo: { ids }, vars: [{ key, years: {window: [one value per area]}, moe: {...} }], notes }`; an array follows the order of the crosswalk's ids for the level (`site/data/geo/crosswalk.json`) and `null` means there is no estimate (never zero) or, for a margin, no margin. Windows are labelled by their last year, as everywhere in the observatory.

## 2. Which variables, at which level

- **Block groups (13):** the 10 variables of the plan's first wave (population (survey estimate), housing units, households, owner-occupied share, vacancy, other vacant units, average household size, overcrowded homes, median home value, income per person), median age, and the shares of people under 18 and 65 and older.
- **Barrios and census tracts (34):** those 13 plus 21 more: median household income, median gross rent, rent as a share of income, median year built, seasonal units, detached homes, units in buildings of 5 or more, mobile homes, poverty, unemployment, employment, bachelor's degrees, households with no vehicle, internet subscription, no internet, the Gini index, women and girls, family households, households of one person, veterans, and people with a disability. That is the 16 variables of the plan's first and second waves (`docs/proposal-2026-10.md`, D1; internet is two columns) and 17 more from tables that the build already reads.
- **Municipalities and Puerto Rico:** every one of those variables, under the same key, in `housing_series.json`, `economy_series.json` or the new `population_series.json`. The layer engine reads a tract as one more level of the same dataset.
- **The Population domain's series (8 variables):** `acs_population`, `acs_under18_pct`, `acs_age65plus_pct`, `acs_female_pct`, `acs_family_households_pct`, `acs_living_alone_pct`, `acs_veteran_pct`, `acs_disability_pct`. Each is a share (or, for `acs_population`, a count) worked out again at every level from its table cells (below), never an average of smaller areas; the name of each says of what it is a share.

**Not published below the municipality, on purpose** (`small_area.EXCLUDED`): cost burden of renters and owners (the margin of the share is about 36 points for a tract and 55 for a block group, among the units with 20 or more renter households); the affordability measures of the 2023 study (a calculation with assumptions, not a survey figure); the rental and homeowner vacancy rates (the denominators are a handful of homes); median income by tenure and the owner costs, left for a later wave. **Tables the Census Bureau does not publish for block groups** (poverty B17001, the Gini index B19083, income by tenure B25119, disability B18101) have no block-group values; the block-group file has only the first wave. Race and ethnicity (B02001, B03002), also named in the plan (D6), are not built: see section 8.

## 3. How the values are made

`small_area.py` reads each table once per vintage and level through `acs_small.py` (byte ranges: 0.5 to 1.5 MB per table for all levels; `docs/geography.md` section 5) and works every variable out with the code that makes the municipal series: `housing_series.derive` and `economy_series.derive_econ` for the 26 variables that already existed, and `small_area.derive_pop` for the 8 new ones. A value therefore has the same definition at every level.

| Variable | Table | Cells |
|---|---|---|
| `acs_population` | B01003 Total Population | 001 |
| `acs_under18_pct` | B01001 Sex by Age | male 003-006 and female 027-030, over the total 001 |
| `acs_age65plus_pct` | B01001 | male 020-025 and female 044-049, over the total |
| `acs_female_pct` | B01001 | female total 026, over the total |
| `acs_family_households_pct` | B11001 Household Type (Including Living Alone) | family households 002, over all households 001 |
| `acs_living_alone_pct` | B11001 | householders living alone 008, over 001 |
| `acs_veteran_pct` | B21001 Sex by Age by Veteran Status for the Civilian Population 18 Years and Over | veterans 002, over 001 |
| `acs_disability_pct` | B18101 Sex by Age by Disability Status | the twelve "with a disability" cells, over 001 |

- **The cell numbers are checked against the Census Bureau's own labels** (its keyless variable definitions, `api.census.gov/data/<year>/acs/acs5/groups/<table>.json`) **in every vintage** at every build, and the build stops if one differs. The labels of the five tables are committed (`tests/fixtures/acs_labels`), so the same check runs in the tests without the cache or the network.
- **Margins** follow the Census Bureau's formulas: the margin of a sum is the square root of the sum of the squared margins; a share uses the proportion formula (`housing_series.pct`). A margin is at the 90% confidence level and is never added or averaged across areas.
- **A controlled total has no margin.** The Census Bureau forces some totals to its own population or housing estimates and prints no margin for them (marked *****: the estimate has no sampling error and its margin may be treated as zero). The total population of the island and of 76 of the 78 municipalities is one (only Culebra and Maricao have a margin), and so is the number of women in 52 municipalities in 2020-2024. `derive_pop` treats a total without a margin as having none, so a share of it keeps the margin of its numerator; the population count itself has no margin there and the Economy tab shows none. It is still the Census Bureau's estimate, not a count of everyone. (`housing_series.pct` would drop the margin of the share, which is why the controlled total is handled first.) The municipal series made before item 7 still follow the older rule (`housing_series.pct` leaves a share's margin blank when its denominator has none): the bachelor's share has a margin for only 5 of the 78 municipalities in 2020-2024, because the Census Bureau controls the adult total of the other 73 (documented in `housing.bachelors_pct`; HANDOFF decision 30). Its barrio and tract values have a margin.
- **Two things the Census Bureau prints are not estimates, and `small_area.clean` leaves them empty.** A **median at the edge of an open-ended interval** arrives as its boundary with no margin (code -333333333, marked ***): 51 for "rent is 50% or more of income", 2,499 for "under $2,500", 1938 for "built before 1939"; and a **median of 0** is the same edge in the oldest window (2017-2021 prints a median year built of 0 for two tracts and two barrios; the raw code is the same -333333333, and later windows print the boundary 1938 or a real median, 1946 to 1965). In 2020-2024 that is rent as a share of income in 74 census tracts, rent as a share of income in 47 barrios, median household income in 4 census tracts, median household income in 1 barrio, median year built in 2 census tracts, median home value in 1 barrio. A **share of exactly 100%** gets a margin of zero from the proportion formula (the numerator is the whole), which would read as exact: it is published without a margin. In 2020-2024 that is the owner-occupied share in 45 barrios, 1 census tract and 50 block groups, the share of detached homes in 59 barrios and 3 tracts, the share with an internet subscription in 39 barrios and 4 tracts, and the share of family households in 22 barrios. The formula also gives zero when the numerator's margin is exactly the share times the denominator's margin (43.64% of 440, 50% of 8 and 88.46% of 1,664 in three published values), and that margin is dropped too. A share of 0% keeps the margin the formula gives. A share of 100% from 141 households with a margin of 58 is not exact.
- **Nulls are not zeros.** The reader turns the Census Bureau's negative codes into `null`; a missing cell in a sum gives no value, not a share of what is left.
- **Windows and geography.** Windows 2017-2021 to 2020-2024 (table-based vintages 2021 to 2024) all use the 2020 geography, so no crosswalk is needed between them. Barrios are the Census Bureau's own county-subdivision rows: they do not nest in tracts and are never made from tracts. Adjacent windows share four of their five years, so the change from one window to the next is not a trend.

## 4. How rough are they (2020-2024, measured on the published files)

Each cell is the **typical margin of error as a share of the estimate** (the median over the areas that have both) / the **share of areas flagged "less reliable"** (margin above 30% of the estimate, or an estimate of zero with any margin: `reliability.isUnreliable`, counted among the areas that have a value). Where the Census Bureau prints no margin for most areas, the cell says so.

| Variable | Municipios | Barrios | Census tracts | Block groups |
|---|---|---|---|---|
| Population (survey estimate) (`acs_population`) | no margin for 76 of 78 | 28% / 47% (margin for 900 of 901) | 20% / 8% | 35% / 73% |
| Housing units (number) (`housing_units`) | 3% / 0% | 20% / 27% | 14% / 6% | 26% / 29% |
| Households (occupied housing units) (`households`) | 4% / 0% | 24% / 37% | 17% / 7% | 30% / 52% |
| Owner-occupied share of occupied units (`owner_occupied_pct`) | 4% / 0% | 15% / 17% (margin for 838 of 883) | 12% / 4% (margin for 919 of 920) | 20% / 25% (margin for 2434 of 2484) |
| Vacant housing units, % of all units (`vacancy_pct`) | 12% / 1% | 42% / 75% (margin for 883 of 891) | 34% / 66% (margin for 920 of 922) | 58% / 93% (margin for 2484 of 2490) |
| Other vacant units, % of all units (abandoned-housing proxy) (`other_vacant_pct`) | 15% / 5% | 53% / 86% (margin for 886 of 891) | 44% / 89% | 71% / 99% (margin for 2488 of 2490) |
| Average household size (`avg_household_size`) | 4% / 0% | 17% / 13% | 12% / <1% | 20% / 10% |
| Overcrowded homes (more than 1 person per room) (`overcrowded_pct`) | 53% / 92% | 165% / >99% | 169% / 100% | 207% / 100% |
| Median home value (`median_home_value`) | 5% / 1% | 17% / 25% | 12% / 8% | 19% / 28% |
| Per capita income (`per_capita_income`) | 8% / 0% | 25% / 35% | 20% / 11% | 30% / 50% |
| Median age (`median_age`) | 1% / 0% | 18% / 23% | 15% / 5% | 24% / 35% |
| People under 18, % of all people (`acs_under18_pct`) | 7% / 1% | 40% / 70% | 32% / 60% | 57% / 91% |
| People 65 and older, % of all people (`acs_age65plus_pct`) | 8% / 0% | 21% / 36% | 16% / 6% | 31% / 51% |
| Median household income (`median_hh_income`) | 9% / 0% | 30% / 49% | 25% / 36% | not published |
| Median gross rent (`median_gross_rent`) | 9% / 3% | 23% / 37% | 24% / 39% | not published |
| Median gross rent as a share of household income (`median_rent_pct_income`) | 17% / 13% | 42% / 64% | 42% / 66% | not published |
| Median year the home was built (`median_year_built`) | 0% / 0% | 0% / 0% | 0% / 0% | not published |
| Seasonal, recreational or occasional-use units, % of all units (`seasonal_pct`) | 30% / 50% | 94% / 97% | 93% / 97% (margin for 921 of 922) | not published |
| Single-family detached homes (`detached_house_pct`) | 4% / 0% | 11% / 8% (margin for 832 of 891) | 10% / 6% (margin for 919 of 922) | not published |
| Units in buildings of 5 or more (`apartments_5plus_pct`) | 30% / 49% | 75% / 90% | 56% / 84% | not published |
| Mobile homes (`mobile_home_pct`) | 118% / 99% | 157% / >99% | 158% / >99% | not published |
| Population below the poverty level (`poverty_pct`) | 9% / 1% | 31% / 53% (margin for 872 of 885) | 27% / 35% (margin for 919 of 920) | not published |
| Unemployment rate (ACS survey) (`unemployment_rate_pct`) | 28% / 45% | 82% / 96% (margin for 875 of 876) | 72% / >99% | not published |
| Employment rate, residents 16+ (ACS) (`employment_rate_pct`) | 6% / 0% | 30% / 50% (margin for 881 of 885) | 21% / 13% | not published |
| Adults 25+ with a bachelor's degree or higher (`bachelors_pct`) | no margin for 73 of 78 | 38% / 66% | 26% / 38% | not published |
| Households with no vehicle (`no_vehicle_hh_pct`) | 20% / 10% | 71% / 93% | 54% / 96% | not published |
| Households with an internet subscription (`internet_subscription_pct`) | 3% / 0% | 14% / 16% (margin for 844 of 883) | 10% / <1% (margin for 916 of 920) | not published |
| Households with no internet access (`no_internet_pct`) | 14% / 4% | 53% / 85% (margin for 879 of 883) | 45% / 89% (margin for 919 of 920) | not published |
| Income inequality (Gini index) (`gini`) | 6% / 0% | 18% / 20% | 13% / 1% | not published |
| Women and girls, % of all people (`acs_female_pct`) | no margin for 52 of 78 | 14% / 20% (margin for 882 of 885) | 10% / 3% | not published |
| Family households, % of all households (`acs_family_households_pct`) | 5% / 0% | 19% / 23% (margin for 861 of 883) | 16% / 3% | not published |
| One-person households, % of all households (`acs_living_alone_pct`) | 12% / 1% | 42% / 72% (margin for 874 of 883) | 30% / 50% | not published |
| Veterans, % of civilians 18 and older (`acs_veteran_pct`) | 35% / 62% | 96% / 98% | 88% / 100% | not published |
| People with a disability, % of people outside institutions (`acs_disability_pct`) | 8% / 4% | 27% / 45% | 21% / 17% | not published |
| People without health insurance, % of people outside institutions (`acs_uninsured_pct`) | 24% / 33% | 81% / 96% | 65% / >99% | not published |
| Adults 25+ without a high school diploma, % of adults 25+ (`acs_no_hs_pct`) | no margin for 73 of 78 | 36% / 62% | 32% / 57% | not published |
| People aged 18 to 44, % of all people (`acs_age18to44_pct`) | 5% / 0% | 24% / 39% | 18% / 7% | not published |
| People aged 45 to 64, % of all people (`acs_age45to64_pct`) | 5% / 0% | 20% / 31% | 16% / 4% | not published |
| People who speak English less than "very well", % of people 5 and older (`acs_english_lt_very_well_pct`) | 3% / 0% | 10% / 10% | 9% / <1% | not published |
| Households that received nutrition assistance (PAN), % of all households (`acs_pan_hh_pct`) | 7% / 0% | 24% / 34% (margin for 866 of 883) | 21% / 20% | not published |

- **Almost always flagged below the municipality** (at least 80% of the census tracts that have a value): overcrowded homes (100%), veterans (100%), mobile homes (more than 99%), the unemployment rate (more than 99%), seasonal or occasional-use units (97%), households with no vehicle (96%), other vacant units (89%), households with no internet access (89%), units in buildings of 5 or more (84%).
- **Rough for municipalities too:** six of those nine have a margin above 30% of the estimate for many of the 78 municipalities (flagged out of 78: mobile homes 77 of 78, overcrowded homes 72 of 78, veterans 48 of 78, seasonal or occasional-use units 39 of 78, units in buildings of 5 or more 38 of 78, the unemployment rate 35 of 78). Compare broad groups of municipalities with them, not two neighbours.
- **The zero rule.** An estimate of zero with any margin counts as less reliable. For the number of people it flags 60 of the 82 census tracts flagged, which have no residents at all; among the 921 tracts with residents the share flagged is 2%.
- **No estimate at all.** Median gross rent has no estimate for 41% of barrios and 13% of tracts (45% of block groups in the Census Bureau's table, which is not published here); the area is empty, not zero. See `docs/analysis/small-area-2026-10/` for the study that preceded the files (its README rounds a figure of one decimal again to a whole number, so a value there can differ from this table by one point).
- **Median year built** has a margin in years, not a share: the typical margin is 3 years for a tract and 5 for a barrio (2 for a municipality), so the 30% rule never flags it.
- Make this table again after a new window with `python small_area.py --measure` (it reads the published files only).

## 5. Checks

`python -m unittest tests.test_small_area` (29 tests; the two that need the cache of Census rows, the municipal parity and the rebuild, skip without it):

- the arithmetic of every Population variable on invented cells, the margin formula, a controlled total, an empty cell (no value, never zero), a real zero (stays zero), a median at the edge of an open interval or of 0 (no value), a share of exactly 100% and any share whose margin works out to zero (no margin) and a share of 0% (keeps its margin);
- the cell labels of every vintage (committed fixtures), and the build stops before it reads anything when one is wrong;
- nothing the plan leaves out is published, every variable has a formula, and the variables of each file are the planned ones;
- each file names its areas by the crosswalk's ids in its order; the municipal file ends with Puerto Rico in the order of the other series;
- **every published value is plausible, without the cache:** shares between 0 and 100, no margin without an estimate, no negative margin, no median of 0 or without a margin, no share with a margin of zero, and the areas with no margin for their population are exactly the controlled totals (77 values of the municipal file and one barrio in every window; no tract, no block group);
- **counts add up:** population, housing units and households of the block groups, tracts and barrios of each municipality equal the municipality, in every window; and the block groups of each tract add up to the tract;
- **parity:** the municipal values worked out here equal the ones `housing_series.json` publishes (1,716 values in 2020-2024, none different) and the cached Census rows give the published files again (`python small_area.py --check`; importing `housing_series` asks the Census Bureau's server whether a newer vintage exists, as it always did);
- **the figures of this guide and of the dictionary are the measured ones:** section 4 is the output of `--measure`, and every "margin is above 30% of the estimate ... for X% of ..." sentence of the entries is compared with it, so those sentences and the rent counts cannot go stale unnoticed after a new window (the tests do not look at the other figures of the text: check them by hand).

`node --test tests/core.test.js` covers `seriesFile`, `levelFile`, the residents rule and which datasets are offered the area buttons, on invented and real files.

## 6. In the engine and the pages

- `Core.adapters.seriesFile(E, doc, { dict: 'population.', group: 'Population · ' })` registers the Population datasets: windows, margins, `family: 'population'`, dictionary ids `population.<key>`. The count of residents has `residents: true`: it is not offered "per 1,000 residents" (that reads 1,000 everywhere) and starts shaded as people per km².
- `Core.adapters.levelFile(E, doc, { level, names })` adds a level to datasets that already exist (`ds.levels[level]`), so `E.series({ key }, period, 'tract')` answers the contract (`ids`, `names`, `values`, `moe`, `flags`, `meta`) beside the untouched municipal values. A period before the first window gets the first (flagged `early`), after the last the last. Only "as published" and "percentile among the areas of the level" are offered at a level: the other rescalings need each area's residents and land, and a margin is not carried through a percentile. `Core.adapters.levelsFor(ds, levels)` says which levels a dataset is offered: those the dictionary lists for it, for the datasets made from ACS tables (the exposure datasets exist at barrio and tract in other files that the tab does not read).
- The Economy tab reads `population_series.json` with its other series: three groups, "Population · People and age", "Population · Household types" and "Population · Disability and veterans". In a dataset's window (the information button), a dataset that exists below the municipality offers **Barrios, Census tracts and Block groups** buttons: each loads the level file and the crosswalk (a status line in the window says so, and says if it fails), then downloads a CSV with the GEOID, the area's name in the page language, the municipality and, for every window, the estimate and its margin of error. `ECON.loadLevel(level)` is the same load for scripts. The GEOID is written as digits: a spreadsheet may show a 12-digit block group GEOID in scientific notation, so import the column as text.
- The chat knows the new variables ("veterans", "discapacidad", "living alone", "family households", "children", "women"), and says for a survey window that adjacent windows share years, so the change is not a trend. It puts one of these groups beside another dataset only in a few clear wordings: a list ("poverty and women"), a phrase of relation ("poverty correlated with women"), or "with", "on" or "sobre" after a word that compares ("compare women with poverty"). In any other wording it shows the other dataset for all residents and says that the breakdown is not available (owner decision of 2026-10-12).
- Nothing else changed: the Housing page, the 3D view, the transit tools and the visitor-economy module read the same files as before.

## 7. Adding a variable or a window

A **new window** comes with the next vintage: add its year to `small_area.VINTAGES`, fetch its cell labels (`python small_area.py` does it and caches them; copy them to `tests/fixtures/acs_labels`), run `python small_area.py`, then `python small_area.py --measure` and paste the table into section 4, then the tests (they say which of the "above 30%" sentences of the dictionary quote an old figure; read the other figures by hand) and `python dictionary.py`. A **new variable**: write its formula in `housing_series.derive`, `economy_series.derive_econ` or `small_area.derive_pop`; add its key to `SELECTION` for the levels that should have it (a median goes in `MEDIANS`); read the margins it gets in section 4 before deciding the level; give it a dictionary entry with `where.files` for each file; then the checklist of `docs/adding-data.md`.

## 8. Not done on purpose

- **No map of barrios, tracts or block groups.** The outlines exist (`geo/tracts.geojson`, `geo/blockgroups.geojson`: draw, never measure) but no page draws them; the layers are municipal. Showing a rough tract map with its hatching is a decision for a later item.
- **No per-resident or per-km² views below the municipality** (they need the residents and land of each area; the crosswalk holds both and the engine can use them later).
- **Cost burden, affordability, rental vacancy** below the municipality (section 2).
- **Race and ethnicity** (ACS B02001 and B03002, named in the plan, D6): the same reader reads them, but they are sensitive categories and nobody has decided to publish them; `wanted.json` keeps the row.
- **Chat answers about areas below the municipality.** The chat ranks municipalities.
- **The "change since the base year" view** is offered for the Population series but the default base year (2014) is before their first window (2021), so it is empty until a later base year is chosen.
- **Windows ending 2020 or earlier** (2010 geography, per-sequence files) and the other ACS products.
- **`housing_series.py` keeps its own municipality reader.** `small_area.py` reads the same tables through `acs_small.py` and the parity test shows the two give the same values, so the switch can be made later with no change to a published value.
- **The CSV by area** is the only place where a value below the municipality is read (no map or table draws these areas). For each window it has the estimate, its margin of error and a "less reliable" mark (a margin above 30% of the estimate, or a share of exactly 100%, which has no margin); then the variable, its unit and dictionary entry, the source (neighbouring windows share four of their five years) and, where a margin is blank, why: the Census Bureau controls the figure, or the share is exactly 100%, or its margin works out to zero. A blank margin is never an exact value. Cite the dictionary entry (`population.*`, `methods.small_area_estimates`) and the Census Bureau's ACS 5-year estimates.
- **The cell labels are checked for the five Population tables only.** The other 20 tables behind the published values are read by the functions of the municipal series (`housing_series.derive`, `economy_series.derive_econ`). Their cell numbers were checked by hand against the Census Bureau's labels in the second review of pull request 4; a wrong cell there would show only in the tests that need the cache.
- **A margin above 100 points is not an interval.** 157 shares in 2020-2024 have one (123 barrios, 18 tracts, 16 block groups; the largest, 5,196 points, is 0% of the people 65 and older of a block group). Read it as "not known"; every one is marked less reliable.
- **The margin of a sum is the Census Bureau's approximation** (the square root of the sum of the squares of the margins of its cells): it can overstate the margin. Every zero cell of an area adds the same modelled margin (15 in most census tracts, 22 in the others); the Bureau's 2013-2017 guide (appendix, example A) says to count only one of them, and later editions say to use the fewest cells. In 2020-2024 the margin of overcrowded homes would be over 10% smaller for 78% of tracts and 93% of block groups, and that of the age and disability shares for 1 to 26% of the areas; the share marked less reliable moves by at most 3 points (people 65 and older in block groups: 51% to 48%). The same function makes the margins of the municipal series (HANDOFF decision 37).
- **Very small areas.** In 2020-2024, 30 of the 901 barrios have fewer than 50 estimated residents and 60 census tracts have none. 14 of those barrios show both a share of people with a disability and a share of veterans; one with 8 estimated residents reads 100% with a disability, plus or minus 580 points (HANDOFF decision 32).
- **Excel shows a long GEOID in scientific notation.** The CSV writes the GEOID as plain digits (11 for a census tract, 12 for a block group). Excel's General format shows a number of 12 or more digits as 7.2E+11 and cuts it to 15 digits, so format the column as text before you paste or import the file with that column set to text (the dataset window says so too). The values in the file are intact. A leading apostrophe would have kept Excel quiet and put a stray character into every other program.
- **Weights** are estimates (compressed bytes; transfer time at 1.6 Mbit/s with 150 ms of latency, not measured on a throttled connection): first load of the 2D map +21.6 KB (about +110 ms; Spanish +22.8 KB, about +117 ms), the dictionary +10.5 KB (about +54 ms), the Economy tab on first open +11.3 KB (`population_series.json`); a level is read only on request: a tract file is 478 KB (about 2.6 s on that connection, plus the crosswalk, 164 KB, the first time).

## 9. Age bands and age groups (2026-10-18)

The project lead approved the age data on 2026-10-18. The source is the same: ACS 5-year table B01001 (Sex by Age), plus B09001 (Population Under 18 Years by Age) for the youngest children, read by `acs_small.py` for the four windows, with the cell labels checked against the Census Bureau's in every vintage (`check_labels`; the B09001 labels are committed in `tests/fixtures/acs_labels`).

- **Five-year bands.** 0 to 4, 5 to 9 ... 80 to 84 and 85 and over: 18 bands. B01001's own groups are not all five years wide, so a band adds the groups inside it (15 to 19 is 15-17 plus 18-19; 20 to 24 is 20, 21 and 22-24; 60 to 64 is 60-61 plus 62-64; 65 to 69 is 65-66 plus 67-69); the cells are worked out from the labels (`small_area.age_cells`), never typed.
- **Age groups.** Under 3 and 3 to 4 (B09001: children in households only; in Puerto Rico they add up to B01001's children under 5 in the island row), 5 to 17, 18 to 24, 25 to 44, 45 to 64 and 65 and older, and the broad groups under 18 and 18 to 44.
- **Counts and shares.** Each band and group has its count and its share of all people (B01001_001), with 90% margins of error by the formulas of section 3. A count made only of cells the Census Bureau controls has no margin (it is not exact); a controlled total gets a margin of zero, so a share keeps its count's margin. The bands add up to all people in every area, and so do under 5, 5-17, 18-24, 25-44, 45-64 and 65+, and under 18, 18-44, 45-64 and 65+ (tests).

**What is published where, and why (reliability, 2020-2024).** Measured with the engine's rule (a margin above 30% of the estimate, or a zero with a margin):

| Age | Share flagged: municipios | barrios | census tracts | Published |
|---|---|---|---|---|
| Each five-year band | 3% to 26% | 89% to 97% | 96% to 100% | municipios only |
| Under 3 / 3 to 4 | 32% / 59% | 99% / more than 99% | 100% / 100% | municipios only |
| 5 to 17 | 1% | 79% | 77% | municipios only |
| 18 to 24 | 4% | 89% | 96% | municipios only |
| 25 to 44 | 1% | 53% | 19% | municipios only |
| 45 to 64 | 0% | 31% | 4% | municipios, barrios, tracts |
| 18 to 44 (broader group) | 0% | 39% | 7% | municipios, barrios, tracts |
| Under 18, 65 and older | 1%, 0% | 70%, 36% | 60%, 6% | already published (item 7) |

The rule: below the municipio an age group is published when its share is flagged for under half of the barrios. The five-year bands and the narrow groups fail it, so barrios and tracts get the four broad groups (under 18, 18 to 44, 45 to 64, 65 and older), which add up to all people; under 18 stays as published since item 7. Block groups get no new age variable (the broad groups are flagged for 48% to 92% of them).

**Where the values are.**
- `population_series.json`: the shares of under 3, 3 to 4, 5 to 17, 18 to 24, 25 to 44, 45 to 64 and 18 to 44 (keys `acs_age_under3_pct` ... `acs_age18to44_pct`), datasets of the Economy tab (Population · People and age), with 65 and older and under 18 as before.
- `population_series.json` also holds the counts of the nine age groups (`acs_age_under3`, `acs_age3to4`, `acs_age5to17`, `acs_age18to24`, `acs_age25to44`, `acs_age45to64`, `acs_age65plus`, `acs_under18`, `acs_age18to44`; added 2026-10-18 once the catalog's startup part had room, #59): 26 variables, all Economy tab datasets. The values are those of `population_age.json`.
- `acs_barrio.json`, `acs_tract.json`: `acs_age18to44_pct` and `acs_age45to64_pct`, so the Economy tab can shade them by barrio (Settings > Area) and the CSV by area has them. The five-year bands and the narrow groups stay at the municipio level.
- **The counts are municipio only (decided 2026-10-18, by the rule that an item below the municipio is published only when it is flagged for under half of the barrios).** Below the municipio a count is rougher than its share, because the share's margin (the proportion formula) takes out the uncertainty of the area's total. In 2020-2024 the count of 18 to 44 is flagged for 65% of the barrios (its share 39%), 45 to 64 for 61% (31%), 65 and older for 61% (36%) and under 18 for 84% (70%); for tracts 32%, 27%, 24% and 87%. So barrios and tracts get the shares; the counts by barrio and tract stay in `population_age.json` (`EXCLUDED` in `small_area.py` says why).
- `population_age.json`: the table for download (no page reads it): counts and shares with margins of every band and group for the municipios and Puerto Rico (`geo.ids`, `vars`), and of the four broad groups for barrios and tracts (`levels.barrio`, `levels.tract`, the crosswalk's ids and order). Dictionary entry `population.age_table`.

**Not built.** Single years of age, and age by sex below the municipio (B01001 has it; the cells are as rough as the bands). The 18 five-year bands are not datasets of the Economy tab (they are in the table, municipios only).

## 10. Language, nutrition assistance and poverty by age (2026-11-14, decision 107 step 1)

Four variables join the Population domain's series (`population_series.json`, 30 variables), from three tables read by the same reader. Two of them are also published for barrios and census tracts (`acs_barrio.json` and `acs_tract.json`, 40 variables each).

| Variable | Table | Cells | Levels |
|---|---|---|---|
| `acs_english_lt_very_well_pct` | B16004 Age by Language Spoken at Home by Ability to Speak English for the Population 5 Years and Over | 100 minus the share of the 15 cells "Speak only English" and 'Speak English "very well"' over the total 001 | municipio, barrio, tract |
| `acs_pan_hh_pct` | B22010 Receipt of Food Stamps/SNAP in the Past 12 Months by Disability Status for Households | households that received the benefit 002, over all households 001 | municipio, barrio, tract |
| `acs_child_poverty_pct` | B17001 Poverty Status in the Past 12 Months by Sex by Age | the twelve cells under 18 below the poverty level, over those and the twelve at or above it | municipio |
| `acs_senior_poverty_pct` | B17001 | the four cells 65 and over below the poverty level, over those and the four at or above it | municipio |

- **English ability** is the person's own rating. The complement of a share has the margin of the share, so the margin is that of the 15 cells. The people 5 and older of the island and of most municipios are a controlled total (no margin): it is treated as zero, as B01001's total is (section 3).
- **Nutrition assistance.** The Census Bureau titles the table Food Stamps/SNAP. Puerto Rico has no SNAP: the Puerto Rico Community Survey asks about the Nutritional Assistance Program (PAN; question 15 of the housing section, `quest23PR.pdf`) and tells people to leave out WIC, school lunches and food banks. It is a survey answer, not the program's records.
- **Below the municipio.** English ability is flagged less reliable (margin above 30% of the estimate) for 10% of the barrios and less than 1% of the census tracts that have a value; nutrition assistance for 34% and 20%. Both are under half, so both are published there. Poverty by age is not: the child share is flagged for 69% of the barrios and 65% of the tracts, the share at 65 and older for 64% and 57% (`small_area.EXCLUDED`). Neither table is read for block groups by the observatory's selection (`SELECTION`).
- **The cells** are checked against the Census Bureau's labels in every vintage, as the others (`check_labels`; the labels of B16004, B22010 and B17001 are committed in `tests/fixtures/acs_labels`).

**Tested and not published: movement in the past year (table B07003PR).** The table gives where the people of an area lived a year before. Measured for 2020-2024: 5.94% of the people of Puerto Rico aged 1 or older lived in another house a year before (margin 0.18), 2.03% in another municipio (0.09) and 0.77% in the United States (0.06; 24,685 people, margin 2,090). The island figures are solid. By municipio they are not: the share that moved is flagged less reliable for 50 of the 78 municipios, the share from another municipio for 70 and the share from the United States for 77. The observatory does not publish a dataset whose values are flagged for most municipios, so these stay out. The table counts people who moved in, never those who left.

**Still held: race and ethnicity** (B02001, B03002): decision 31 is open (section 8).
