# Test results in public schools, META-PR (decision 107, step 7, third part)

Built 2026-11-18 (row `school-outcomes`, "reading and math proficiency"). The share of public school students who scored proficient or above in reading (Spanish) and math on Puerto Rico's test, all tested grades together, by municipio and for the island, school years 2014-15 to 2018-19.
The code is `proficiency.py`, the tests are `tests/test_proficiency.py`, the file is `site/data/proficiency_series.json`.

## 1. Results for the island

| School year | Schools | Reading (Spanish), % proficient (band) | Math, % proficient (band) |
|---|---|---|---|
| 2014-15 | 1,365 | 43.6% (42.4–44.7) | 29.8% (28.5–31.1) |
| 2015-16 | 1,309 | 50.7% (49.5–51.9) | 33.5% (32.3–34.8) |
| 2016-17 | 1,272 | 48.8% (47.6–50.0) | 32.7% (31.4–33.9) |
| 2017-18 | 1,090 | 45.9% (44.8–47.0) | 32.6% (31.5–33.8) |
| 2018-19 | 836 | 45.2% (44.3–46.0) | 30.2% (29.3–31.1) |

The band is the island's figure from the bottom and the top of every range small schools report (section 3).

## 2. Source and why it ends in 2018-19

The Urban Institute's Education Data Portal (ODC-By 1.0), which republishes the US Department of Education's EDFacts assessment files: `schools/edfacts/assessments/{year}/grade-99`, Puerto Rico, all-students row.

- **The portal's year is the school year that starts in it.** Its 2018 file has 836 schools, the count after the 2018 closures; its 2017 file has 1,090. So 2018 is 2018-19 (tested in spring 2019).
- **Nothing newer is readable by a script, by school** (checked 2026-11-18): the portal has no Puerto Rico rows after 2018 (2019-20 was not tested); ED Data Express answers a script with an empty page; the Department of Education's school profile (perfilescolar.dde.pr) is a Power BI report; the Instituto de Estadísticas publishes the island's 2018-19 figures only.

## 3. Method

- Each school is placed in a municipio by its NCES id in the Common Core of Data directory of the same year. Every school placed, every year.
- A municipio's share is pooled: the sum over its schools of (share proficient × students tested) over the students tested.
- To protect students, a small school's share comes as a range (for example 20% to 29%); the middle is used, and the notes keep the island's figure from the bottom and the top of every range.

## 4. Check

The Department of Education's own 2018-19 results: 45.1% proficient in Spanish and 30.1% in math ([UPRM summary of the results](https://www.uprm.edu/ppm/wp-content/uploads/sites/47/2025/03/Resultados-Pruebas-META-2018-2019-1.pdf)). This file: 45.2% and 30.2%.

## 5. Reading the numbers

- Puerto Rico sets its own test and its own line for proficient: do not compare with a state or with NAEP.
- About 265 schools closed after 2017-18; a municipio's share can move because its students moved to other schools.
- Highest in 2018-19: Orocovis and Barranquitas in both subjects; lowest: Vieques in both.

## 6. Rebuilding

```
python proficiency.py             # build (downloads what is missing into cache/edfacts)
python proficiency.py --refresh   # download again
python proficiency.py --check     # rebuild from the cache and compare (no network)
```

Refresh unit `proficiency` (local); the freshness check is a quarterly reminder to look for a newer year on the portal.
