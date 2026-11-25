# Drought by municipio and year (decision 107, step 5, first part)

`drought.py` writes `site/data/drought_series.json`: three yearly datasets for the 78 municipios and Puerto Rico, in the Analysis tab group *Hazards · Drought (US Drought Monitor)*.

| Dataset | What it counts | Years |
|---|---|---|
| `drought_area_pct` | The share of the municipio's area in drought (D1, moderate, or worse), averaged over the weeks of the year | 2000-2026 |
| `drought_weeks` | Weeks in which drought (D1 or worse) covered at least half the municipio | 2000-2026 |
| `drought_severe_weeks` | Weeks in which severe drought (D2) or worse covered at least half the municipio | 2000-2026 |

2026 holds the weeks published so far. The file is rebuilt each week: the refresh reads the newest map date and its pull request merges itself when the checks pass, because past weeks are not revised.

## Source

The US Drought Monitor, drawn each week by the National Drought Mitigation Center (University of Nebraska-Lincoln) with USDA and NOAA. Its data service needs no key:

- `usdmdataservices.unl.edu/api/CountyStatistics/GetDroughtSeverityStatisticsByAreaPercent?aoi=<municipio code>&statisticsType=1`, one request a municipio, every week since January 4, 2000.
- `StateStatistics` with `aoi=72` gives Puerto Rico. A `CountyStatistics` request with `aoi=72` returns nothing.
- The service answers JSON only with the header `Accept: application/json`; without it, it answers CSV.
- `statisticsType=1` gives cumulative shares: `d1` is the share in D1 or worse.

The Drought Monitor allows any use, commercial included, with this credit ([permission page](https://droughtmonitor.unl.edu/About/Permission.aspx)): **"Data courtesy of NDMC, via https://droughtmonitor.unl.edu"**. The credit is in the file's sources, in the dataset entry and on the dictionary page.

## Drought classes

| Class | Name | Conditions this dry happen about |
|---|---|---|
| D0 | Abnormally dry | 20-30% of the time |
| D1 | Moderate drought | 10-20% |
| D2 | Severe drought | 5-10% |
| D3 | Extreme drought | 2-5% |
| D4 | Exceptional drought | under 2% |

D0 is not counted as drought here: it marks areas going into or coming out of drought.

## What it shows

- **Most years before 2014 had little or no drought.** Puerto Rico's yearly average reached 10% or more only in 2015, 2016, 2019, 2021, 2022 and 2026.
- **2015 was the worst whole year:** on average 28.5% of the island was in drought. The east and center were hit hardest: Caguas (67.1%), Gurabo (66.2%) and Guayama (65.9%). Arroyo, Caguas, Guayama, Salinas and San Lorenzo had 35 weeks with drought over half their area. 22 municipios had none.
- **2025 was wet:** 0.1% on average.
- **2026 so far (to the map of November 10):** 26.5% on average, and the south-west leads: Lajas and Santa Isabel had 24 weeks with drought over half their area, Salinas 23. On the map of August 25, 44.5% of the island was in extreme drought (D3), the most since the series began; on November 10, 34.7% was in drought and 8.8% in severe drought.

## Rules

- **A week counts when the class covers at least half the area** (`HALF = 50`). The line is the observatory's, not the Drought Monitor's, so the entries say so and point to the average share as well.
- **The year is the calendar year of the map date** (each map is dated the Tuesday before its Thursday release). A year has 52 or 53 maps.
- **Puerto Rico's figure is the Drought Monitor's own** state figure, not a sum of municipios.

## What it does not say

- **It is a judgment, not a measurement.** The authors draw the map from rainfall, soil moisture, stream flow, reservoir levels and local reports. Its lines do not follow municipio borders.
- **Drought is not water rationing.** Rationing depends on the reservoirs and the pipes that serve each place; read the reservoir layer beside it.
- **2026 is not a whole year.** Compare it with past years by the average share, not by the count of weeks.

## Checks (`tests/test_drought.py`)

- Weighting each municipio's weekly share by its land area gives Puerto Rico's own figure within 0.12 points in every one of the 1,402 weeks (needs the cache).
- Every year has 52 or 53 weeks, except the current year.
- Shares are between 0 and 100; the weeks with severe drought never exceed the weeks with drought.
- With the cache, a rebuild gives the published file again (`python drought.py --check`).

## Room made on the area profile

The three datasets took the area profile's scripts over their 122 KB budget (122.2 KB). The profile's Spanish bundle now takes only the map strings it uses, which brings the scripts to 92.7 KB (`docs/performance.md`).

## Not in this part

Step 5 has two more parts, each its own pull request: the months for night-time light to return after Hurricanes María and Fiona, by barrio, and storm surge by hurricane category.
