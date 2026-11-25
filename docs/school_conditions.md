# Public school conditions from the Civil Rights Data Collection (decision 107, step 7, second part)

Built 2026-11-18 (row `school-outcomes`, "civil-rights data"). Four measures of Puerto Rico's public schools, by municipio and for the island, from the US Department of Education's Civil Rights Data Collection (CRDC): school years 2017-18 and 2021-22.
The code is `school_conditions.py`, the tests are `tests/test_school_conditions.py`, the file is `site/data/school_conditions_series.json`.

## 1. Results for the island

| Key | Dataset | 2017-18 | 2021-22 |
|---|---|---|---|
| `crdc_absent_pct` | Students chronically absent (%) | 8.9 | 45.7 |
| `crdc_students_counselor` | Students per school counselor | — | 546 |
| `crdc_nurse_pct` | Schools with a nurse (%) | — | 96.2 |
| `crdc_no_counselor_pct` | Schools with no school counselor (%) | — | 51.5 |

In 2021-22, 118,064 of 258,457 enrolled students were chronically absent; 475 counselors (full-time equivalents) served 843 schools.

## 2. Source

The Urban Institute's Education Data Portal (ODC-By 1.0), which republishes the CRDC (public domain): `schools/crdc/enrollment`, `chronic-absenteeism` and `teachers-staff`, Puerto Rico only, all-students rows only (race, sex, disability, English learner and homeless all 99). The portal timed out often on 2026-11-18; the script tries each page up to six times and caches the rows in `cache/crdc/`.

## 3. Method

- Each school is placed in a municipio by its NCES id in the Common Core of Data directory of the same year (`cache/education`, from `education_series.py`). One school of 844 in 2021-22 is not in the directory and is left out (counted in the notes).
- Ratios are pooled: a municipio's share is the sum of its schools' numerators over the sum of their denominators, over the schools that report both. Negative codes are no value.
- Chronically absent: absent 15 or more school days in the year, for any reason.

## 4. Gaps in the source

- Puerto Rico's staff items (counselors, nurses, teachers) are all missing (code −1) in 2017-18, so the three staff measures have 2021-22 only.
- First-year teachers are missing in 2021-22, so the measure the plan named is not published.
- 2019-20 was not collected (the pandemic). 2023-24 is the next collection.

## 5. Check

The Annie E. Casey Foundation's 2024 KIDS COUNT release for Puerto Rico (with the Instituto del Desarrollo de la Juventud) reports 48% of public school students chronically absent around 2022-23, beside 45.7% here for 2021-22.

## 6. Reading the numbers

- Chronic absence in 2021-22 ranges from 11% (Guaynabo) to 83% (Las Marías), and three western municipios are above 77%. Differences this large between neighbors may come partly from how each education region recorded absences: read neighbors together.
- 2017-18 was the school year of Hurricane María; schools that did not reopen are not in it.
- Schools report their own figures; the Office for Civil Rights does not audit them.

## 7. Rebuilding

```
python school_conditions.py             # build (downloads what is missing into cache/crdc)
python school_conditions.py --refresh   # download again
python school_conditions.py --check     # rebuild from the cache and compare (no network)
```

Refresh unit `school_conditions` (local); the freshness check is a quarterly reminder to look for the 2023-24 collection.
