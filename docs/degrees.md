# Degrees awarded by colleges (decision 107, step 7, first part)

Built 2026-11-18 (row `school-outcomes`, "degrees by field"). Degrees and certificates awarded by colleges in Puerto Rico, by level and broad field, for the 78 municipios and the island, every academic year from 2014-15 to 2023-24.
The code is `degrees.py`, the tests are `tests/test_degrees.py`, the file is `site/data/degrees_series.json`.

## 1. Results for the island

| Key | Dataset | 2014-15 | 2019-20 | 2023-24 |
|---|---|---|---|---|
| `deg_total` | Degrees and certificates awarded (all levels) | 60,533 | 49,376 | 48,725 |
| `deg_associate` | Associate degrees awarded | 9,143 | 6,689 | 5,837 |
| `deg_bachelor` | Bachelor's degrees awarded | 20,459 | 19,866 | 14,779 |
| `deg_graduate` | Master's and doctor's degrees awarded | 7,204 | 6,647 | 6,558 |
| `deg_field_health` | Bachelor's or higher degrees in health | 5,848 | 6,742 | 5,196 |
| `deg_field_business` | Bachelor's or higher degrees in business | 6,126 | 5,155 | 3,808 |
| `deg_field_education` | Bachelor's or higher degrees in education | 2,758 | 1,878 | 1,183 |
| `deg_field_stem` | Bachelor's or higher degrees in science, technology, engineering and mathematics (STEM) | 4,959 | 5,209 | 5,082 |
| `deg_field_social` | Bachelor's or higher degrees in social and behavioral sciences | 3,460 | 2,929 | 2,375 |
| `deg_field_arts` | Bachelor's or higher degrees in arts and humanities | 1,640 | 1,737 | 1,544 |
| `deg_field_other` | Bachelor's or higher degrees in other fields | 2,872 | 2,863 | 2,149 |

Bachelor's degrees fell by 28% in nine years and associate degrees by 36%; master's and doctor's degrees fell by 9%. Education is the field that fell most (−57%); health and STEM held.

## 2. Source

NCES's IPEDS complete data files, read straight from NCES (US Government work, public domain): `C{year}_A.zip` (completions) and `HD{year}.zip` (directory). The Urban Institute's portal, which `education_series.py` uses for enrollment, had no completions for Puerto Rico after 2021 on 2026-11-18. The revised file in a ZIP (`_RV`) is read when there is one.

## 3. What is counted

- First majors only (MAJORNUM 1).
- Levels: associate 3, bachelor's 5, master's 7, doctor's 17, 18 and 19. Older files pad the code ("05"); the build reads it as a number.
- Fields are the first two digits of the CIP code, bachelor's or higher:

| Field | CIP families |
|---|---|
| Health | 51 |
| Business | 52 |
| Education | 13 |
| Science, technology, engineering and mathematics | 01, 03, 11, 14, 15, 26, 27, 40, 41 |
| Social and behavioral sciences | 42, 44, 45 |
| Arts and humanities | 05, 09, 16, 23, 24, 38, 39, 50, 54 |
| Other | everything else |

- Each award goes to the municipio of the reporting campus in that year's directory.

## 4. Where a college reports

Most systems report campus by campus (the University of Puerto Rico, Ana G. Méndez, Inter American), but not all. The largest single reporter each year:

| Year | Institution | Awards | Share of the island |
|---|---|---|---|
| 2015 | Instituto de Banca y Comercio Inc | 7,054 | 11.7% |
| 2016 | Instituto de Banca y Comercio Inc | 6,647 | 11.4% |
| 2017 | Instituto de Banca y Comercio Inc | 6,110 | 10.7% |
| 2018 | Instituto de Banca y Comercio Inc | 5,626 | 10.8% |
| 2019 | Instituto de Banca y Comercio Inc | 4,966 | 9.8% |
| 2020 | NUC University | 9,632 | 19.5% |
| 2021 | NUC University | 10,955 | 22.3% |
| 2022 | NUC University | 9,792 | 21.3% |
| 2023 | NUC University | 10,526 | 23.6% |
| 2024 | NUC University | 14,321 | 29.4% |

NUC University reports all of its campuses and online programs from Bayamón, mostly certificates, so Bayamón's count is far above where its students study. The island figures are not affected. The dictionary entries and the dataset definitions say so.

## 5. Checks

Two checks run for every year and stop the build if they fail: the six-digit rows add up to the file's own total (CIP 99) at every award level, and the fields add up to the bachelor's and graduate degrees. Every award was placed in a municipio in all ten years.

## 6. Rebuilding

```
python degrees.py             # build (downloads the years missing from cache/degrees)
python degrees.py --refresh   # download every year again (takes NCES's revision of the year before)
python degrees.py --check     # rebuild from the cache and compare (no network)
```

Refresh unit `degrees` (local). The freshness check walks `C{year}_A.zip` forward every 30 days; when the next year appears, raise `LAST` in `degrees.py` and rebuild.

## 7. Not done (later parts of step 7)

- School conditions from the Civil Rights Data Collection (2021-22): part 2.
- Reading and math proficiency by school (newest readable: 2017-18): part 3.
