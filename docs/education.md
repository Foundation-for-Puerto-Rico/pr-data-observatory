# Education data (Phase 3, item 8: data wave B)

`education_series.py` writes `site/data/education_series.json`: seven datasets for the 78 municipios and Puerto Rico, one value for each school year from 2010 (2010-11) to 2024 (2024-25). The Economy tab lists them under "Education · Public schools" and "Education · Colleges and universities". Plan: `docs/proposal-2026-10.md` (J row 8, D2).

## Source and license

The Urban Institute's Education Data Portal API (https://educationdata.urban.org), no key. It republishes two US federal collections of the National Center for Education Statistics (NCES):

- **Common Core of Data (CCD) school directory**: one row for each public school each school year, with its county, status, students and teachers.
- **IPEDS**: the directory of colleges, universities and other postsecondary institutions, and their fall enrollment.

The portal's data are under the Open Data Commons Attribution License (ODC-By 1.0): credit the Urban Institute and NCES. The NCES data themselves are US federal and in the public domain. License class: `open-with-conditions` (attribution). The dictionary, the dataset window and the source records (`urban_ccd`, `urban_ipeds` in `dictionary_src/sources.json`) carry the credit line.

## Privacy

Only the columns in `KEEP` (in `education_series.py`) reach the cache (`cache/education/`) or the output. School and college names, addresses, telephone numbers, web addresses, officers' names and coordinates are dropped as each row is read. The output holds counts for each municipality only. `tests/test_education_series.py` checks the kept columns against a list of personal and contact fields, and checks the cache files themselves.

## Variables

| Key | What it counts | Notes |
|---|---|---|
| `sch_open` | Public schools open in the school year | CCD status open, new, added, changed agency or reopened (codes 1, 3, 4, 5, 8). Private schools are not in the CCD. |
| `sch_enroll` | Students in those schools | Fall count. A school with no count is left out; a municipality whose open schools all lack one has no value. |
| `sch_teachers` | Teachers, full-time equivalents | |
| `sch_ptr` | Students per teacher | Only schools that report both. Not class size. |
| `sch_closed` | Schools open the year before and not this year | By NCES school id; no value for 2010. A new id counts as a closure and an opening. |
| `he_inst` | Postsecondary institutions in the IPEDS directory | Includes technical and vocational schools. Only rows with a sector above 0 count: the central offices of university systems (sector 0, three in San Juan every year) and the records marked "not applicable" (sector -1, 13 in 2020) are not institutions and have no fall enrollment. |
| `he_enroll` | Their fall students, undergraduate and graduate | Counted where the institution reports (a university that reports as a whole: its main office). |

Urban codes a missing value as a negative number (-1 missing, -2 not applicable, -3 suppressed). The build reads these as no value, never as zero.

## Checks

- **Published totals.** Puerto Rico's public school enrollment is 346,096 in 2017-18 and 235,819 in 2024-25, the same as the figures in the plan (D2). College enrollment is 270,920 in fall 2010 (the plan gives 270,914) and 170,009 in fall 2023. The plan gives 167,883 for 2023, probably from a different count (degree-seeking students only, for example); the observatory adds the undergraduate and graduate totals.
- **Closures.** The series shows the waves of closures: 162 schools in 2017-18 and 277 in 2018-19. Open schools went from 1,473 in 2010 to 862 in 2024.
- **Recodes.** A school that NCES gives a new id would count as a closure and an opening. That can be at most a handful a year: from 2011 to 2024 no more than 7 open schools a year have an id that was not open the year before (0 in 2017 and 2019), against 162 and 277 closures in the closure years. The file's `notes.closures_reopened_next_year` counts something else, the closures that are open again the next year under the same id: 0 or 1 a year.
- **Colleges.** The IPEDS directory also lists the central offices of university systems (sector 0, three in San Juan every year) and, in 2020, 13 records marked "not applicable" (sector -1). They are not institutions and have no fall enrollment, so `he_inst` leaves them out (found by the review of PR #17; before the fix the series showed a false rise to 155 in 2020). The series is 152 institutions in 2010 and 126 in 2024.
- **Guards.** The build stops if a year has fewer than 600 open schools, fewer than 150,000 students or fewer than 60 institutions (a sign that Urban changed a code or a column), or if a school's county is not one of the 78 municipios.
- **Sums.** Every island value is the sum of the municipal values (except the ratio, which is worked out from the same schools). A test checks this.

## Not done (left for later)

- **School points on the map.** The CCD has coordinates for each school. They are not published here; a school layer is an institution layer (not personal data) and could come later if FPR wants it.
- **Adults without a high school diploma** (ACS B15002, the table that already gives `bachelors_pct`). Adding it means rebuilding the Housing series of every year, which takes hours; it waits for the next full build.
- **The chat.** It does not yet recognize words such as "schools" or "students" (item 14 builds the chat's vocabulary from the registry).
- **Head Start, College Scorecard, Civil Rights Data Collection, E-Rate.** Still `checked` in `wanted.json`: Head Start and the Scorecard state no license, the CRDC adds little for Puerto Rico, and E-Rate (which covers private schools) is the next candidate.

## How to update

`python education_series.py` downloads only the years missing from the cache; `--refresh` downloads every year again; `--check` rebuilds from the cache and exits 1 if the published file differs. `build.py` runs it after the health series. When a new school year appears, the build adds it on its own (it reads years until the API has none).
