# Social Vulnerability Index (decision 107, step 2)

`svi.py` writes two files from the CDC/ATSDR Social Vulnerability Index 2022:

- `site/data/svi_series.json`: four datasets for the 78 municipios, in the group **Vulnerability (CDC/ATSDR SVI)** of the Analysis tab and in the area profiles.
- `site/data/svi_tract.json`: the same four ranks for the census tracts. It is a file for download and for later steps (the hexagon grid of decision 107). No map draws census tracts yet.

## What the index is

CDC and ATSDR rank every area on 16 measures of the American Community Survey (here 2018-2022), in four themes, and publish a percentile rank from 0 (least vulnerable) to 1 (most vulnerable). The index is meant to show which communities may need more support before, during and after a disaster.

| Dataset | CDC's column | Made of |
|---|---|---|
| `svi_overall` | `RPL_THEMES` | The four themes together |
| `svi_socioeconomic` | `RPL_THEME1` | Below 150% of the poverty level, unemployed, housing cost burden, no high school diploma, no health insurance |
| `svi_household` | `RPL_THEME2` | 65 and older, 17 and younger, disability, single-parent households, English less than well |
| `svi_housing_transport` | `RPL_THEME4` | Buildings of 10 or more units, mobile homes, crowding, no vehicle, group quarters |

## Three rules for reading it

1. **It is a rank, not an amount.** 0.80 means more vulnerable than 80% of Puerto Rico's municipios (or tracts). Ranks are not added or averaged.
2. **Puerto Rico is ranked apart from the states.** A municipio is ranked among the 78 municipios and a tract among Puerto Rico's tracts. A value is never comparable with a state's, and a municipio's rank is not the average of its tracts' ranks.
3. **No value is not zero.** CDC's code -999 (a tract with no residents or too little data) is an empty value. 919 of the 981 census tracts have an overall rank; CDC's file holds 939 tracts.

## Why the third theme is not a dataset

Theme 3 is racial and ethnic minority status: the share of residents who are not non-Hispanic White. its largest rank among Puerto Rico's tracts is 0.5223, because in 897 of the 922 tracts with a value 95% or more of the residents are a minority by the national definition. It is inside the overall rank, as CDC computes it. The observatory publishes the other three themes and the overall rank as CDC computes it, and says so in each entry.

## What it shows

Most vulnerable municipios, overall: Loíza (1.00), Ponce (0.99), Salinas (0.97), Juana Díaz (0.96), Naranjito (0.95). Least: Guaynabo (0.00), Camuy (0.01), Dorado (0.03), Cidra (0.04), Aguada (0.05).

FPR's own WCRP vulnerability indicators (`wcrp.html`) rank **barrios** with a different method and more local inputs. The two indices are not the same and are not combined.

## Source, terms and edition

- CDC/ATSDR Social Vulnerability Index 2022, Puerto Rico: the county file and the tract file, CSV, no key (`svi.cdc.gov/Documents/Data/2022/csv/`).
- A US federal dataset. The page states no licence and asks for its suggested citation, which the source card carries.
- 2022 is the newest edition; the address of a 2024 edition answered "not found" on 2026-11-14.
- CDC says files downloaded between 2022-10-27 and 2026-01-15 were incorrect. These were downloaded on 2026-11-14.
- Rebuilt by hand when a new edition comes: change `EDITION` in `svi.py`, run `python svi.py --refresh`.

## Checks (`tests/test_svi.py`)

CDC's no-value code becomes empty and a rank of zero stays; a value outside 0 to 1 or a missing column stops the build; the municipios and tracts are the observatory's, in order; Puerto Rico has no rank; a tract without residents has no rank; a rebuild from the cached files gives the published files again.

## Tested and not published: EPA's National Walkability Index

Step 2 of decision 107 also named EPA's walkability index by block group. It is **not usable for Puerto Rico**, so nothing was built.

- The index is the average rank of four measures: intersection density, distance to transit, the mix of jobs, and the mix of jobs and households.
- For all 2,552 Puerto Rico block groups, three of the four are blank: the ranks `D2A_Ranked`, `D2B_Ranked` and `D4A_Ranked` are 1 (the lowest) everywhere, and total employment (`TotEmp`) is 0. The jobs data behind the index (LEHD) does not cover Puerto Rico, and no transit feed was read for it.
- Only intersection density varies. The published "index" for Puerto Rico is that one measure rescaled, on 2019 block groups, which is why no block group scores above 7.3 of 20.

The observatory can measure walkability itself, from the data it already holds: its road network, sidewalks and crossings in OpenStreetMap, the timetables, the places and the slope on the walk. That is a computed layer for a later step, not a download.
