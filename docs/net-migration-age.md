# Net migration by age (decision 107, step 9, sixth part)

Built 2026-11-24 (row `derived-net-migration-age`). For every municipio: how many people it gained or lost to migration between the 2010 and 2020 censuses, by age group, as a share of the people it would have had with no migration, and in people.
The code is `netmig_age.py`, the tests are `tests/test_netmig_age.py` and a test in `tests/core.test.js`, the file is `site/data/netmig_age_series.json` (labeled 2020, the end of the window).

**An estimate** (decision 107 b): a demographic model, with the word "estimate" in every name, a check and a range below.

## 1. Results for the island

| Age in 2020 | Net migration | Expected with no migration | Share |
|---|---|---|---|
| 10 to 19 | -81,846 | 463,882 | -17.6% |
| 20 to 29 | -154,563 | 550,290 | -28.1% |
| 30 to 44 | -152,426 | 744,916 | -20.5% |
| 45 to 64 | -14,325 | 933,656 | -1.5% |
| 65 and over | 19,060 | 711,919 | 2.7% |
| 10 and over (all) | -384,100 | 3,404,663 | -11.3% |

The young adults left most: more than a quarter of the people aged 20 to 29 in 2020 are missing against what survival alone would have left. People aged 65 and over show a small net gain, the return of retirees.

The municipios that lost the largest share of their people aged 10 and over, and those that lost the least:

| Municipio | Ages 10+ | Ages 20-29 | Ages 65+ | People, ages 10+ |
|---|---|---|---|---|
| Guánica | -28.0% | -50.2% | -12.2% | -4,943 |
| Maricao | -25.0% | -44.1% | -8.8% | -1,443 |
| Loíza | -22.8% | -42.1% | -7.3% | -6,397 |
| Arroyo | -19.8% | -42.7% | -1.8% | -3,580 |
| Guayama | -19.5% | -37.3% | -0.6% | -8,152 |
| … | | | | |
| Naranjito | -4.9% | -21.9% | 12.7% | -1,368 |
| Cabo Rojo | -4.7% | -28.8% | 7.7% | -2,147 |
| Hormigueros | -4.4% | -28.7% | 13.8% | -678 |
| Culebra | -0.3% | -12.6% | -5.7% | -6 |
| Rincón | 3.2% | -21.3% | 15.2% | 443 |

## 2. Method

The forward cohort survival residual (United Nations, Manual VI, the survival ratio method):

1. **Counts.** The Census Bureau's municipio files by age and sex: the 1 April 2010 census (PRM-EST2020-AGESEX, YEAR 1) and the 1 April 2020 estimates base, built from the 2020 census (CC-EST2025-AGESEX-72, YEAR 1). Five-year groups by sex. The Census API now asks for a key, so the build reads these public CSV files instead.
2. **Survival.** Puerto Rico's abridged life table by sex from the UN's World Population Prospects 2024, the person-years lived in each age group (nLx) averaged over 2010-2019. The ten-year survival of the group aged a to a+4 is L(a+10) / L(a); the open group 75+ (85+ in 2020) uses T(85) / T(75).
3. **Residual.** For each municipio, sex and group: net migration = people aged a+10 to a+14 in 2020 minus the survivors of those aged a to a+4 in 2010. Groups are summed over sex and into the published age groups (by age in 2020).
4. **Rate.** Net migration per 100 of the survivors expected in 2020.
5. **Left out:** children under 10 in 2020, born during the decade (their estimate needs births by municipio).

## 3. Range and check

**Range** (island, ages 10 and over): -362,347 with the life table of 2010 alone and -406,137 with that of 2019 (published -384,100).

**Check against the demographic balance.** The change in population between the censuses (3,725,789 to 3,285,874) minus births (317,675) plus deaths (300,724), from the Census Bureau's estimates components (NST-EST2020-ALLDATA), is **-456,866**: the net migration of all ages that both censuses imply. The residual for ages 10 and over, plus the children born in the decade (the 2020 count of ages 0 to 9 minus the surviving births to April 2020, about -44,868), is **-428,968**, 6.1% smaller. The births and deaths run to July 2020 and include the excess deaths after Hurricane María, which an average life table smooths out. Other figures for the decade: the UN's net migration for 2010-2019, -408,407; the Census Bureau's estimate made before the 2020 census, -583,765 (the census found more people than that estimate, so it overstated the loss).

## 4. Reading notes

- Net: moves within Puerto Rico and moves abroad are counted together, and arrivals cancel departures.
- College towns show a loss in the ages that were students in 2010: the census counts students where they study.
- Errors in either census land in the estimate, and the 2020 census added noise to protect privacy; in small municipios a few hundred people move a rate by several points.
- One life table for the island: where people die younger than average, the estimate shows a little more out-migration.
- The window is 2010-2020; the next needs the 2030 census. The Census Bureau's estimates since 2020 rest on its own migration assumptions, so the residual is not repeated on them.

## 5. Rebuilding

`python netmig_age.py --refresh` reads the three Census Bureau files (under 1 MB) and streams the UN's tables (about 160 MB) keeping Puerto Rico's rows; `python netmig_age.py` rebuilds from the cache (local; refresh unit `netmig_age`).
