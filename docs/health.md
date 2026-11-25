# Health: HRSA health centers and shortage areas

Added 2026-10-06 at the request of the project owner: "I see you are missing Health Data. Can you add this dataset: https://data.hrsa.gov/ (only add if open source)."
The Health domain was empty. This is its first data: **11 datasets for the 78 municipalities and Puerto Rico**, in one 23.5 KB file (5 KB compressed), `site/data/health_series.json`,
built by `health_series.py`. They appear in the Economy tab's list of datasets (group "Health care ·") and in the Catalog tab.

## What is in, and what is not

| Dataset (dictionary id `health.<key>`) | What it says | Island value |
|---|---|---|
| `hc_sites` | Permanent sites of federally funded health centers (FQHC) and look-alikes that deliver care | sum |
| `hc_vans` | Mobile health center vans, counted where HRSA lists them | sum |
| `hpsa_pc_short`, `hpsa_dh_short`, `hpsa_mh_short` | Practitioners (FTE) still needed for a shortage designation to end: primary care physicians, dentists, psychiatrists (the one kind of practitioner that the mental health designations of Puerto Rico count) | sum |
| `hpsa_pc_met`, `hpsa_dh_met`, `hpsa_mh_met` | HRSA's "percent of need met": practitioners in place ÷ (in place + still needed) | total in place ÷ total needed |
| `hpsa_pc_score`, `hpsa_dh_score`, `hpsa_mh_score` | HRSA's priority score for the designation | none (a score is not added or averaged) |

**Not in the observatory, on purpose**

- **The Area Health Resources File (AHRF).** HRSA's download page says "Usage limitations: None", but the technical documentation inside the 2024-2025 release says: "Reproduction for re-use or sale is not authorized without the expressed permission of the Bureau. Further, data from the American Dental Association, the American Hospital Association, and the American Medical Association are subject to copyright restrictions." The stricter text wins. AHRF holds physicians, hospital beds and births by municipio, so it is the one that would add most; it is recorded in `wanted.json` as `blocked`, with who to ask (see below).
- **Medically Underserved Areas and Populations (MUA/P).** HRSA's file has 72 Puerto Rico rows, all of them designations of 1 November 1978, with an "underservice score" of 0.00 for 71 of them and 50.00 for one. The four indicators the score is made from (providers per 1,000, infant mortality, poverty, share aged 65 and over) are empty in all 72 rows, so the score cannot be checked. Six municipios have no designation (Fajardo, Guánica, Guayama, Guayanilla, Guaynabo, Morovis). A status that is the same for 72 of 78 municipios makes a poor map layer, so it is not published; the file is not read by the build.
- **Facility designations** (health centers, which HRSA designates by law, and one correctional facility) are left out of the municipal values; the correctional facility is kept apart in the file's notes so HRSA's own totals can be checked.
- **Names, addresses, telephone numbers, web addresses and coordinates** of the sites. Only counts for each municipality are published (standing rule: aggregated data only). The cache never holds them either (below), and it blanks the HPSA ID of a facility designation, which names one facility. A layer of points for travel time to care (plan item 9) is a separate decision.

## Source and license

HRSA (Health Resources and Services Administration, US Department of Health and Human Services), Data Warehouse downloads: https://data.hrsa.gov/data/download. Four files, no key:

| File | Used for |
|---|---|
| `Health_Center_Service_Delivery_and_LookAlike_Sites.csv` | `hc_sites`, `hc_vans` |
| `BCD_HPSA_FCT_DET_PC.csv`, `..._DH.csv`, `..._MH.csv` | the shortage-area datasets (primary care, dental health, mental health) |

The download page lists "Usage limitations: None" for each of the four files, and the data are the work of a US federal agency. Data.gov's record for the sites file gives its license as CC0 1.0 ("No rights reserved. This data is in the public domain.") but lists only the Excel version of the file; the build reads the CSV. Its record for the Shortage Designation Management System (published by HRSA's Bureau of Health Workforce; a file entry is dated 3 September 2026; Data.gov last crawled it on 28 September 2026) lists the three shortage-area files and gives the same license, but also sets the access level "restricted public" (the federal metadata schema defines it as "available under certain use restrictions") and marks every file "Restricted - Partly": the record contradicts itself. Data.gov's record for the HRSA Data Warehouse as a whole (modified 26 July 2023, last crawled 10 September 2026) names the Open Database License 1.0, which asks for credit and share-alike, and says the portal offers downloadable data files on health center sites and shortage areas: it may cover all four files, and if it did the credit line would need to say so and the re-sharing notes would add `health_series.json`. Both sources are therefore marked `link-works-licence-unclear` in `sources.json` (license class `open`, because the records that name the files say CC0) and the dataset has an open license review (`python contract.py --reviews`, HANDOFF decision 38). The observatory treats the files as open, credits HRSA in the dataset window, the data dictionary and the About tab, and asks HRSA nothing until the owner decides. Credit lines are in `dictionary_src/sources.json` (`hrsa_sites`, `hrsa_hpsa`). Checked 2026-10-07; this is not legal advice.

## How it is built

```
python health_series.py             # build site/data/health_series.json (downloads only what is missing; about 9 seconds with a connection)
python health_series.py --refresh   # download the HRSA files again (a new snapshot)
python health_series.py --check     # no network: does the file match the cached rows? exit 1 when it does not
```

`build.py` runs it after `economy_series.py`. Each HRSA file (10 to 50 MB for all states) is **streamed**: only the Puerto Rico rows, and only the columns listed in `FILES` in `health_series.py`, are written to `cache/hrsa/<key>.pr.csv` (git-ignored; 17 to 44 KB each). Names, addresses, telephone numbers, web addresses and coordinates are dropped as the bytes arrive; `tests/test_health_series.py` fails if a column that could hold one is ever added to the list. If HRSA renames a column the build stops and says which. It also stops, and writes nothing, when a value HRSA could rename ("Active", "Designated") leaves a count implausibly small, when a status is one it does not know, and when the four files were not made within a day of each other: otherwise it would publish a false "no site" and "no shortage area" for every municipality (`tests/test_health_series.py`, class `Safety`).

### How a municipality's figures are made

- **Sites.** A row counts when its status is `Active` and its type is a service delivery site or an administrative and service delivery site ("Administrative" alone delivers no care). Permanent rows give `hc_sites`, `Mobile Van` rows give `hc_vans`. A municipality with none shows **0**: HRSA lists none there. Of 169 Puerto Rico rows on 2026-10-06, 127 are permanent sites that deliver care, 33 are vans and 9 are administrative-only.
- **Shortage areas.** A designation counts when its status is `Designated` (or `Proposed For Withdrawal`, which HRSA still counts until the Federal Register notice) and its type is an *area*: `Geographic HPSA`, `HPSA Population` or `High Needs Geographic HPSA`. In Puerto Rico today there are 20 primary care, 77 dental and 52 mental health area designations, **one for each municipality**, and all but one are for **low-income residents** (the exception is one dental "high needs geographic" area). The value is read from the file's `HPSA Score`, `HPSA Shortage` and `HPSA FTE` columns.
- **No value is not zero.** A municipality with no area designation gets *no value*, never a 0: it is not rated as a shortage area (58 municipalities for primary care, 1 for dental care, 26 for mental health). For 57 of the 58, for the 1 and for all 26, HRSA withdrew an area designation the municipality once had (`notes.hpsa.<discipline>.municipios_without_one_that_had_one_withdrawn`), so no value is not proof that there are enough practitioners. Seventeen municipalities have only a *facility* designation for primary care (a health center or, in one, a correctional facility) and 11 for mental health (one of them the correctional facility); they also show no value.
- **Overlaps and splits.** If a municipality ever had two area designations the build keeps the highest score and the designation with the larger shortage (the groups overlap, so they are not added) and counts it in `notes.hpsa.<discipline>.overlaps` (0 today). A designation that spans two municipalities, or a county code that is not one of the 78, stops the build: there is no honest way to split it.
- **Need met** = FTE ÷ (FTE + shortage) × 100, HRSA's own definition (endnotes 4 to 6 of its quarterly summary). The island value is the summed FTE over the summed need, not an average of shares. It is stored with three decimals, so the figure printed with one decimal is the one the sums give (29.1%, not 29.2%).
- **The ratio HRSA works the figure out against.** The rules set limits for designation (42 CFR Part 5, Appendices A to C): 3,500 people for each primary care physician for a whole area and 3,000 for a low-income population group or an area of unusually high need; 5,000 and 4,000 for dentists; for mental health, 30,000 for each psychiatrist for a whole area and, for a population group, 20,000 or 15,000 together with 4,500 for each core mental health professional. HRSA's files state a goal for every designation (the column `HPSA Provider Ratio Goal`, checked on the live files on 2026-10-07 and not kept in the cache): 3,000 to 1 for all 20 primary care designations of Puerto Rico, 4,000 to 1 for all 77 dental ones and 20,000 to 1 for all 52 mental health ones. The shortage figures work out to the goal for primary care and dental (population ÷ (FTE + shortage) is about 3,000 and about 4,000 in every designation) but not for mental health, where it is about 15,000 (between 14,843 and 15,070): at the stated goal of 20,000 the 52 designations would need about 50.5 psychiatrists, not 69.5. The observatory publishes HRSA's figure as HRSA gives it and says so (`tests/test_health_dictionary.py` checks the ratios against the cached rows).

### What HRSA counts, so a reader does not over-read it

- **Physicians only, dentists only, psychiatrists only.** HRSA's formula for primary care counts physicians, not nurse practitioners or physician assistants. For mental health, every Puerto Rico designation read here is based on psychiatrists alone (`Provider Type` = Psychiatrist in 52 of 52), so psychologists, clinical social workers and other providers are not counted.
- **FTE for a low-income population** is built from the time a practitioner spends on low-income patients (Medicaid claims, or hours with Medicaid and sliding-fee patients), from hours that practitioners report in surveys run by the state primary care offices (HRSA's Shortage Designation Management System manual, August 2026, section IV). The manual also sets weights and exclusions for some practitioners (residents in training, federal providers, dentists' hours), so an FTE is not simply hours divided by 40. A practitioner who serves few such patients, or whose data HRSA does not have, adds little or nothing. **A need met of 0% means "HRSA counts no practitioner for this designation", not "no practitioner works here".** Six of 20 primary care designations, 7 of 77 dental and 44 of 52 mental health designations have an FTE of 0. **San Juan is the largest case:** its primary care designation has no practitioner in place, so its need met is 0% and its 81.1 practitioners still needed are 60% of the island's 135.2; read the island total and the map with that in mind.
- **Freshness.** Designations were set between 2012 and 2024 and last updated between 2016 and 2024 (`notes.hpsa.<discipline>.designated_years`, `.last_updated_years`), so a figure can be years behind the present.
- **Scores** run from 0 to 25 for primary care and mental health designations and from 0 to 26 for dental ones (HRSA's scoring documentation, linked from the source record) and rank priority for placing National Health Service Corps clinicians. They are an index built by HRSA's rules, not a measurement, and there is no value for Puerto Rico as a whole.

## Checked against HRSA's own totals

HRSA publishes the *Designated HPSA Quarterly Summary* (https://data.hrsa.gov/default/generatehpsaquarterlyreport; the one used is "as of September 30, 2026"). Its Puerto Rico rows against this file, on 2026-10-06 (the file adds the correctional facility to the municipal values because HRSA's totals include it):

| | Designations | Population of designated HPSAs | Practitioners needed | Percent of need met |
|---|---|---|---|---|
| Primary care, HRSA | 43 | 574,059 | 138 | 28.90% |
| Primary care, this file | 20 area + 23 facility | 572,469 + 1,590 = **574,059** | 135.2 + 1.6 = 136.8 | 28.91% |
| Dental, HRSA | 100 | 2,292,005 | 297 | 48.02% |
| Dental, this file | 77 area + 23 facility | 2,289,505 + 2,500 = **2,292,005** | 296.7 + 1.7 = 298.4 | 48.02% |
| Mental health, HRSA | 75 | 1,140,925 | 70 | 8.31% |
| Mental health, this file | 52 area + 23 facility | 1,138,425 + 2,500 = **1,140,925** | 69.5 + 1.2 = 70.7 | 8.32% |

The populations agree to the person, the designation counts agree, and the practitioners needed are each within 1.1% (HRSA rounds each designation: rounding the shortage of each designation to a whole number and adding gives HRSA's 138, 297 and 70 exactly, which `tests/test_health_series.py` repeats from the cached rows; HRSA's metadata does not define `HPSA Shortage`, so this match is the evidence that it is the column the summary adds). `tests/test_health_series.py` repeats the check from the notes in the file. The island values in the datasets leave out the facilities, so they read a little differently from HRSA's own (29.1%, 48.2% and 8.5% of need met).

## Where the pieces are

| Piece | File |
|---|---|
| Build, cache and checks | `health_series.py` (writes `site/data/health_series.json`) |
| Engine: reads the file as datasets | `site/js/core/adapters.js` (`snapshotFile`), loaded in `site/js/economy.js`; scores use `noIsland` in `site/js/core/normalize.js` |
| Dictionary | `dictionary_src/entries/health.json` (11 variables and 2 method entries: `health.sites_method`, `health.shortage_method`), `sources.json`, `datasets.json` (`health_series`), `groups.json`, `glossary.json` (FQHC, FTE, HPSA, HRSA, Look-alike, MUA/P) |
| Domain | `dictionary_src/domains.json`: `health` is now `partial`, with the headline "Permanent sites of health centers (with or without a federal grant)" |
| Spanish | `i18n_src/es/labels_health.json`; `i18n_src/pages.json` |
| Tests | `tests/test_health_series.py` (Python), `tests/core.test.js` (the adapter on the real file), `tests/test_catalog.py` |
| Candidates and blocks | `site/data/wanted.json`: `hpsa` and `hrsa-health-centers` are `live`; `ahrf` is `blocked` |

The file has the shape of `economy_series.json` with one snapshot year, so the next HRSA, CMS or CDC series that is a figure for each municipality can be added the same way: a builder that writes `vars`, one `snapshotFile` call, dictionary entries and Spanish labels. `docs/adding-data.md` has the checklist.

## Asking HRSA for permission to use the AHRF

Not sent. A draft the person who owns the relationship can adapt (the contact is on HRSA's Area Health Resources Files page, which names the National Center for Health Workforce Analysis):

> Foundation for Puerto Rico builds PR Data Observatory, a free public tool that shows open data for the 78 municipalities of Puerto Rico (https://observatory.foundationpr.org/). We would like to publish a small set of figures from the Area Health Resources File, 2024-2025 release, for Puerto Rico's municipalities (physicians, hospital beds and births), with the source credited, and we understand that the file's documentation requires the Bureau's permission to reproduce it for re-use and that some fields belong to the AMA, ADA and AHA. Could you tell us whether the Bureau permits this, and which fields we may publish?

## What the maps do with these datasets (seen in review, not changed)

- **A zero draws the smallest symbol.** On a symbol map every place with a value, a zero included, gets a dot of at least 2.5 px, as for every dataset: for the 33 mobile vans 61 of 78 municipalities are zeros and the map reads as if all had a van. HANDOFF decision 35.
- **Natural breaks and a second shaded layer.** A layer that starts with natural breaks (health center sites) shaded together with another layer gives a two-layer legend with very unequal classes (sites with poverty: 76, 1 and 1 municipalities in the three classes of sites). Choose "quantile" in the layer's panel to compare. HANDOFF decision 36.
- **The island value per 1,000 residents** divides the island's total by all of its residents, including those of the municipalities with no designation, so for psychiatrists (26 without one) it is below every municipality that has one; the dictionary says so.

## Next

- **Item 9 (Health)** can use these counts, and still needs a decision on coordinates for travel time to care: HRSA's file has them, the observatory does not publish them today.
- A **hospital and clinic layer**: CMS counts are live since item 9 (below); points for hospitals and clinics are not published.
- **Ask HRSA** about the AHRF (above) and, if FPR wants the re-use terms in writing, about the download page's "Usage limitations: None".

## Item 9: hospitals and care facilities, distance to a health center, Medicare, health insurance (2026-10-14)

Phase 3 item 9 (data wave C, `docs/proposal-2026-10.md` D3) adds three files and two survey variables. The HRSA file above (`health_series.json`) is unchanged.

### Hospitals and care facilities (`care_series.json`, `care_series.py`)

Counts for each municipality from CMS's Provider Data Catalog (US federal data, public domain), the Puerto Rico rows of five lists: hospitals (59 in 24 municipalities, 54 with emergency services), dialysis facilities (50), nursing homes certified by Medicare or Medicaid (9), home health agencies (39) and hospice providers (42).

- Only the municipality (county, or for home health the town), the ZIP code and, for hospitals, the type and the emergency flag are kept. Names, addresses, telephone numbers and certification numbers never reach the cache (`cache/cms/`).
- Four home health agencies name a barrio or sector as their town (Hato Rey, Coto Laurel, Altos de Luchetti, Palmas). `CMS_ZIP` places them by their ZIP code (San Juan, Ponce, Manatí, Cataño). Any other name that is not a municipality stops the build.
- These are Medicare-certified facilities only. Most long-term care homes on the island are not certified, so the nursing home count is small.

### Distance to a health center (`care_series.json`, `care_access.py`)

An estimate made by the observatory: how far residents live from the nearest permanent health center site of HRSA's list, along the roads.

- **Inputs:** HRSA's site points (124 permanent sites that deliver care, in the file of 2026-10-14), the 2020 census blocks with residents (36,570) and the observatory's OpenStreetMap road graph (`roads.bin`).
- **Coordinates.** HRSA geocodes each site. The owner decided on 2026-10-14 that the build may keep the site points in the local cache (`cache/hrsa/site_points.pr.csv`: longitude and latitude only) to compute distances. They are never published; the site shows figures for each municipality only.
- **Method.** One shortest-path search from all sites at once, over every road in both directions (it is a distance to care, not a driving route). Each block's internal point is snapped to the nearest road joined to the network within 2 km. A municipality's figure is the average over its residents. 3 blocks (46 residents) have no such road within 2 km and are left out.
- **Results.** Puerto Rico's residents live on average 5.13 km by road from the nearest health center, and 90.4% live within 10 km. The longest averages are Villalba (20.08 km), Sabana Grande (13.86 km), Juana Díaz (13.65 km); the shortest are Culebra (2.37 km), Arroyo (2.53 km), Florida (2.55 km).
- **Drive time** uses the observatory's planning speeds for each road class (free flow, no traffic): a rough estimate, labeled as one. The road distance is the firmer figure.
- **Not measured:** distance to a hospital or an emergency department. CMS's hospital list has no coordinates; matching the 59 hospitals to points needs a check by hand (the proposal's note), and is left for later.
- The site points (2026-10-14) and the counts of sites in `health_series.json` (HRSA's file of 2026-11-11) are from different dates: 124 permanent sites with a point against 120 counted. The distance to a health center is not yet recomputed from the newer list.

### Medicare enrollment (`medicare_series.json`, `medicare_series.py`)

CMS's Medicare Monthly Enrollment (data.cms.gov, public domain), the yearly rows by county: people enrolled in Medicare, the share in Medicare Advantage and other plans, and the share entitled by disability, for each municipality, 2013 to 2025. Puerto Rico had 711,896 people with Medicare in 2013 and 779,295 in 2025; the share in Medicare Advantage went from 72.97% to 85.93%. The municipalities add up to CMS's state row within a few people each year (the rest is CMS's "unknown" county, 72999). A count CMS suppresses is no value.

### Health insurance and schooling from the survey (`small_area.py`)

Two variables join the Population series and the barrio and tract files:
- `acs_uninsured_pct`: people without health insurance, from B27010 cells 017, 033, 050 and 066. 5.72% of Puerto Rico's civilian population outside institutions in 2020-2024.
- `acs_no_hs_pct`: adults 25 and older without a high school diploma, from B15002 cells 003-010 and 020-027. 18.83% in 2020-2024. This is the variable left over from item 8; its dictionary domain is education.

The cells are checked against the Census Bureau's labels at every build (`check_labels`). How rough each one is at each level is in `docs/small-area.md`, section 4.

### Not done in item 9

- **CDC Social Vulnerability Index (tract) and OpenStreetMap health features.** Still `checked` in `wanted.json`.
- **The Department of Health's data** need its written consent (`doh-biostatistics` is `blocked`).
- **The Area Health Resources File** stays out; see above.

