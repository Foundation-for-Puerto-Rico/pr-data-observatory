# Women in the labor force: the Eastern Region and Puerto Rico (Knowledge Area analysis, 2026-10-30)

**Question (the project lead, 2026-10-30):** for the Human Capital chapter of FPR's Eastern Region Strategic Vision (ERSV), what is the women's labor force participation rate of the region, rather than the island-wide figure, and what is behind it (how many women are of working age, how many people the survey interviewed)?

**The region:** the 15 municipios of the ERSV: Canóvanas, Ceiba, Culebra, Fajardo, Humacao, Juncos, Las Piedras, Loíza, Luquillo, Maunabo, Naguabo, Río Grande, San Lorenzo, Vieques, Yabucoa (FPR, Eastern Region Economic Development Council, *Human Capital Demographic Profile*, 2025). Not Patillas, Gurabo, Caguas or Carolina.

## Files

| File | What |
|---|---|
| `women_labor.py` (repository root) | Reads the ACS tables, writes `site/data/women_labor.json` (the page's data) and `site/data/labor_sex_series.json` (the map's datasets). `--check` rebuilds and compares. |
| `make_page.py` (this folder) | Writes `site/women-labor.html` and its Spanish, `i18n_src/es/women_labor.json`, with every figure read from the data file. |
| `site/js/women_labor.js` | The page: charts, the municipio map and the region builder. Its arithmetic is the pipeline's (`tests/women_labor.test.js` checks they agree). |
| `tests/test_women_labor.py`, `tests/women_labor.test.js` | Formula checks, the published files, the parity of Python and JavaScript, the island equal to the sum of its 78 municipios. |

## Data

U.S. Census Bureau, American Community Survey 5-year estimates, read from the summary files (no key):

- **B23001** Sex by age by employment status, population 16 and over. Seven age groups are kept (16-19, 20-24, 25-34, 35-44, 45-54, 55-64, 65+), each with population, labor force (civilian and Armed Forces), civilian labor force and unemployed, with 90% margins.
- **B23003** Females 20 to 64 in households, by presence and age of own children, by employment status.
- **B98003** and **B98001** Unweighted sample: people and housing units interviewed (2020-2024 only; the per-sequence files of older windows are not read for them).

Windows: **2010-2014, 2015-2019, 2020-2024**, the three that share no year. Five-year windows that overlap are not independent and are never compared.

Checks made on 2026-10-30: the sum of men and women over the seven age groups equals table B23025 (employment status, both sexes) exactly in all 79 areas (island and 78 municipios) for 2020-2024; the island row equals the sum of its 78 municipios, cell by cell, in every window.

## Method

- **Labor force participation** = in the labor force (civilian and Armed Forces) / population 16 and over, as in table S2301. **Unemployment rate** = unemployed / civilian labor force.
- **Pooled rates.** A group's rate is the sum of its municipios' counts, divided. The simple average of the municipio rates is shown only to explain why it is wrong for a region (it gives Culebra the weight of Humacao).
- **Margins of error** (90%): sums by the square root of the summed squares (every zero estimate's margin is kept, which is slightly conservative: the Handbook keeps only the largest); proportions by the Census Bureau's formula, with the ratio formula when the root is negative (ACS General Handbook, chapter 8).
- **Significance:** a difference is significant when it is larger than its margin, the square root of the sum of the two squared margins (z = 1.645). An area is compared with **the rest of Puerto Rico**, never with the island total that contains it.
- **Age-adjusted rate** (direct standardization) with the age mix of the women in the rest of the island, and the **Kitagawa (1955) split** of the gap into age mix and participation within each age. The two parts add up to the gap exactly; they carry no margin of error.
- **Reliability:** coefficient of variation = (margin / 1.645) / estimate; over 30% is flagged, the observatory's rule, and so is a zero estimate with a margin.

## Results (2020-2024, as the file gives them on 2026-10-30)

- Women 16 and over in the region: 183,952 ± 1,752; in the labor force: 77,240 ± 1,684.
- Women's participation: **42.0% ± 0.8** in the region, 41.9% ± 0.3 in the rest of Puerto Rico and on the island. Difference +0.1 ± 0.9 points: **not significant**.
- Men: 51.0% ± 0.9. Gap, men minus women: **9.0 ± 1.2 points**, significant.
- Women 25 to 54: 70.0% ± 1.5 (rest of the island 69.9%), up 7.8 ± 1.9 points since 2010-2014 (62.3%). Women 16 and over: up 1.3 ± 1.1 points (40.7% to 42.0%), while their estimated number fell by about 9,000 (counts from different windows are controlled to different population estimates, so part of a change in counts comes from those controls; rates are much less affected).
- By age, the region differs from the rest of the island significantly only at 55-64 (31.1% against 37.5%, −6.4 ± 2.4) and 65+ (−2.3). Age-adjusted rate 40.7%: the region's slightly younger women raise its rate by 1.3 points and lower participation after 55 lowers it by 1.2; the two cancel.
- Women 20 to 64 (from 2015-2019 the Census Bureau counts only the householder's own children, so the 2010-2014 figures are not comparable) with children under 6: 66.6% (rest 65.7%); with children 6 to 17 only: 70.9% (72.3%); without own children under 18: 55.7% (56.6%). None of the differences is significant.
- Municipios: from 64.0% ± 10.4 in Culebra and 49.6% in Canóvanas to 33.4% in Yabucoa and 32.5% in Humacao.
- Sample: 16,930 people (all ages, both sexes) and 10,139 housing units interviewed in the region in five years. The survey does not publish the number of women 16 and over interviewed.

**On the chapter's current figure:** the *Human Capital Demographic Profile* gives "an average labor force participation rate of 45.37%" for 2019-2023. That is an average of the 15 municipio rates for both sexes. The pooled rate for both sexes, 2020-2024, is 46.2% ± 0.6 (the simple average gives 46.2% too in this window, but not in others, and not for women: 42.6% against 42.0%). For women the figure to use is the pooled 42.0% ± 0.8.

## What this analysis adds to the observatory (and what the next ones can reuse)

1. **A region builder with honest arithmetic.** Any group of municipios gets pooled rates, margins of error and a significance test against the rest of the island, in the page and in the CSV. The arithmetic lives in one script per language and a test keeps them equal.
2. **The denominator and the sample on screen.** Every rate shows how many people it divides by and how many people the survey interviewed, so a reader can judge it.
3. **Age adjustment and decomposition.** A crude rate compares populations of different ages; the page separates the age mix from behavior.
4. **Comparable windows only.** Trends use windows that share no year.
5. **Map datasets.** `labor_sex_series.json` puts seven variables on the map's Economy tab and area profiles (women's and men's participation, prime age, gap, women's unemployment, counts), with margins, so they combine with every other layer.

Next analyses of the same kind can reuse `women_labor.py`'s helpers (`esum`, `prop`, `diff`, `combine`, `age_adjust`) and the page's region builder. Candidates that the same tables or their neighbors answer: earnings by sex (B20017), education by sex (B15002), occupation by sex (C24010), poverty by sex and age (B17001), disability and employment (C18120), commuting by sex (B08006).
