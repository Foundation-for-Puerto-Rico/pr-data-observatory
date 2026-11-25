# Public spending (Gasto Público): record schema, allocation tiers and the rules for adding up

Where public money goes in Puerto Rico: Commonwealth agencies (state), municipio governments (municipal) and federal money that reaches the island (federal to PR), by sector and type of expense, placed in the 78 municipios when the source allows it. HANDOFF decision 73 records the plan and the project lead's approvals; the Phase 0 audit is `PUBLIC_SPENDING_PHASE0_2026-11-01.md` in the VIEWPR folder.

This page describes the schema (PR 1). The ingestors, the function crosswalk and the views come in later PRs, one at a time.

## Where it lives

- **Domain:** `public-money` (a sub-domain of economy until the navigation plan, decision 81, made it a domain of its own). No new domain. Gasto Público gets its own Knowledge Area page in a later PR; `public-money.html`, renamed "FEMA disaster funding and need" on 2026-11-03, stays a FEMA page.
- **Code:** `spending.py` (schema, checks, the rules for adding up, the tags of the published series) and `muni_names.py` (municipio names to FIPS ids).
- **Raw downloads:** `cache/spending/<source>/`, untouched and git-ignored, like every other source.
- **Normalized records:** `cache/spending/records/<source>.csv`, one row per record, never published. Check them with `python spending.py --check <file>`.
- **Published files:** aggregates only, built from the records, in the series shape of `economy_series.json` (municipio × year), plus a state table (agency × fund × concept × year × stage) for the budget views.

## The record

| Field | Values | Notes |
|---|---|---|
| `municipio_fips` | `72001`–`72153`, or empty | Empty = island-wide or not placed. Names go through `muni_names.municipio_id()` |
| `fiscal_year` | year | The year the source names (a Puerto Rico fiscal year is named by the year it ends) |
| `fiscal_year_basis` | `pr_jul_jun`, `federal_oct_sep`, `calendar`, `declaration_year` | The brief named the first two. `calendar` (NMTC investments) and `declaration_year` (FEMA Public Assistance, by the year of the disaster declaration) were added because the live series already use them |
| `level` | `state`, `municipal`, `federal_to_pr` | Who spends: a Commonwealth agency, a municipio government, or federal money reaching PR |
| `source_system` | source id | The id in `dictionary_src/sources.json` |
| `stage` | `proposed`, `approved`, `obligated`, `disbursed`, `actual` | `actual` = spent (OGP "Gastado", single audits) |
| `fund_origin` | `general`, `federal`, `special`, `bond_other` | OGP: Fondo General, Fondos Federales, Fondos Especiales |
| `agency_or_entity`, `program` | text | As the source writes them (OGP: "081 Departamento de Educación") |
| `function_category` | `education`, `health`, `public_safety`, `transportation`, `housing`, `parks_recreation`, `environment_natural_resources`, `economic_development`, `utilities_energy`, `social_services`, `debt_pensions`, `general_government`, `other` | From the function crosswalk (PR 2, reviewed by the project lead before use) |
| `concept_of_expense` | `payroll`, `purchased_services`, `transfers`, `capex`, `debt_service`, `other` | OGP's concept codes map onto these |
| `recipient_type` | `agency`, `municipality`, `nonprofit`, `private`, `individual_aggregate` | Never an individual: people are only ever a total |
| `allocation_tier`, `allocation_driver`, `allocation_confidence` | see below | |
| `amount_usd` | number | Nominal dollars. The CPI deflator in `economy_series.json` puts years on one footing |
| `population_basis`, `per_capita_usd` | text, number | Per resident uses one basis (below) |
| `dedup_group` | id from `DEDUP_GROUPS` | Money that more than one source reports |
| `retrieved_at`, `source_url`, `terms_of_use` | date, URL, text | Provenance on every row |

`validate()` refuses unknown fields. That keeps personal data (vendor owners, employees, beneficiaries) out of the records even if a source exposes it.

## Allocation tiers

- **direct:** the source places the money in a municipio (capital projects with a location, contracts with a place of execution, federal place of performance, FEMA applicants, municipal audits).
- **apportioned:** an estimate. An agency's operating spend is spread across municipios by a stated driver already in the repository: Education by school enrollment, and later Health by facilities, Transportation by road-km and Environment by protected area once those drivers exist. **Only operating spend is apportioned, never capital spending or federal awards** (`validate()` refuses it). When a driver is missing, the gap is recorded and no proxy is used. Parks has no driver today. Apportioned figures appear only on sector pages, labeled as estimates. They are never added into the municipio totals: `add_up()` leaves them out unless they are asked for alone.
- **island_wide:** debt service, pensions, central administration, and anything without a defensible driver. Shown next to every map ("no geography"), never dropped: `add_up()` keeps it under an empty municipio.

## Rules for adding up (`spending.add_up`)

1. **One fiscal-year basis.** Puerto Rico, federal, calendar and declaration years are never added together.
2. **One stage.** Approved and spent are two measures of the same money.
3. **No copies.** Each dedup group names its authoritative source, and only that source is added up:

| Group | Authoritative | Also reported by |
|---|---|---|
| `fema_pa` | OpenFEMA | COR3, USAspending |
| `fema_hma` | OpenFEMA | COR3, USAspending |
| `cdbg_dr` | Vivienda (CDBG-DR/MIT portal) | COR3, USAspending, single audits |
| `ogp_federal` | OGP (federal funds in the Commonwealth budget) | USAspending |

4. **Direct and island-wide by default.** Apportioned estimates only when asked for, and then alone.

## Per resident: one population basis

Every per-resident figure uses the Census Bureau's yearly residents: the 2010 and 2020 counts and the July 1 estimates in between. This is the `population` series of the Housing page, which the map engine already divides by. The series steps up in 2020, because 2011–2019 estimates were never revised to the 2020 count, and the dictionary says so (`methods.population_vintage_break`). A record's `population_basis` names the vintage and year. The FEMA disaster funding page (`public-money.html`) divides 2017–2025 sums by 2020 residents; Gasto Público figures use the yearly basis.

## Tags on the series already published

The 37 public-money series in `economy_series.json` (USAspending, OpenFEMA, the Federal Audit Clearinghouse, NMTC) each carry a `spend` object in the record's terms: `level`, `source_system`, `fiscal_year_basis`, `stage`, `fund_origin`, `allocation_tier`, and where it applies `dedup_group`, `function_category`, `recipient_type`, `part_of`, `split`, `in_totals` and `note`. The two FEMA Individual Assistance series of the Housing page are not tagged yet.

- `part_of` names the series this one is a part of. Never add a part to its whole.
- `split` names a breakdown whose parts add up to the whole: award types, damage categories, direct vs pass-through, federal agency. `tests/test_spending.py` checks this for every year and every municipio. A part with no split (Pell, Head Start, the Social Security programs) is only a subset.
- `in_totals: false` marks figures that are not public spending: counts, NMTC investments (private money made with a tax credit), and the Section 406 project cost.
- The `function_category` tags on these series follow the function crosswalk, reviewed on 2026-11-09 (decision 92).

The tags live in `SERIES_TAGS` (`spending.py`). `economy_series.py` writes them on every build, and `python spending.py --tag` writes them into the published file without a download. They added 0.8 KB gzip to `economy_series.json`, which loads on demand.

## The source manifest

Two optional fields in `dictionary_src/sources.json`, checked by `contract.py` (`validate_sources`):

- `authority`: `authoritative` (the publisher of record for its figures) or `secondary` (repeats another publisher, like the Observatorio Fiscal).
- `lineage`: `{ "en": "..." }`, where the figures come from and which other source reports the same dollars. A secondary source must have one.

Cadence and freshness stay in `refresh/sources.json` (`every_days`), as for every source. The `spending` refresh unit arrives with the first ingestor.

## Compliance

Federal and CDBG-DR content stays under the decision 21 hold: no headline figure, Spanish summaries held, Finance and Compliance review before anything leaves the build. State budget figures are not federal grant work, but leadership sees the Gasto Público page before it is public (decision 73). Data are only ever totals by municipio, agency, program or function, never by named person.

## The function crosswalk (HANDOFF decision 76, reviewed in decision 92)

`dictionary_src/spending_crosswalk.csv` maps every code a source uses to a `function_category`, and where it applies to a `concept_of_expense` and an `allocation`. It is a **draft until the project lead reviews it**: the 40 rows flagged `review` are listed, largest money first, in `docs/analysis/public-spending-2026-11/crosswalk_review.md`. Edit the CSV, then run the tests.

| Kind | Code | What it covers |
|---|---|---|
| `ogp_concept` | 3 digits (A001 / C001 → `001`) | OGP's 19 concepts of expense → the six concepts. `009` debt amortization and `030` pensions are `override`: function `debt_pensions` and island-wide, whatever the agency |
| `ogp_agency` | 3 digits | The 108 agencies of the FY26 and FY27 data sheets. Their function is the default for every program and object |
| `ogp_program` | agency-program (`050-1159`) | The programs whose function differs from their agency's (parks inside DRNA, unemployment inside Labor, the lottery inside Hacienda, broadband inside OGP) |
| `ogp_object` | agency-E-code (`025-E8990`) | Objects of expense inside the two custodial accounts (Hacienda Custodia, OGP Custodia), by E-code, which both years' data sheets share (FY27 writes `632006-…-E8990`, FY26 `009-E8990: …`), which have one program each |
| | | The custodial rows of Hacienda (025) are matched to the named assignments of the budget resolutions (FY27 Certified Budget Resolution, FY26 Resolución Conjunta 14, the Oversight Board's FY25 certified budget letter). A row can name a fund (`025-E6390@general`) and carry `years` (`2025-2027`): it then applies only to those fiscal years, and other years fall back to the plain row or the agency. The $1.13 B General Fund line "Otras compensaciones no clasificadas" of FY27 is the Pension Reserve Trust contribution ($970.3 M in FY25, $970.5 M in FY26). The transfer line E9760 is the highway and transit transfers in FY26-FY27 but mixes them with rum cover-over payments in FY25. FY24 uses other object codes, so its custodial lines stay `other` |
| `cfda_agency` | 2 digits | The default per federal agency, for listings not named. A lookup that falls back to one is low confidence |
| `cfda` | `84.010` | The 67 named listings: 96.8% of federal dollars placed in Puerto Rico in FY2023–2025 (of 760 listings) |
| `fema_category` | A–G, Z | FEMA Public Assistance damage categories (the same functions as the `spend` tags) |
| `contralor_group` | 1–23 | The Registro de Contratos service groups. Most say what was bought (a concept), not what for. A blank function means "from the contracting entity". The groups' sub-types load by script on the Contralor's site, so they come with the client in PR 5 |

**Lookups.** `ogp_function(agency, program, concept, object)` checks, in order: a concept that overrides, the object, the program, then the agency.
- A program or object keeps its agency's `allocation` only when it has the agency's function.
- Capital spending is never apportioned.
- An agency or concept the crosswalk doesn't list raises an error, so a new code stops the ingestor instead of landing silently in "other".

`cfda_function(listing)` looks up the listing, and falls back to its agency's default.

**`allocation` values:**
- `apportion:school_enrollment`: Education only (decision 73).
- `pending_driver:<driver>`: Health, Transportation and Environment, which wait for their drivers.
- `no_driver`: Parks.
- `island_wide`, or blank: island-wide until a driver exists.

**Evidence and how to rebuild.** The code lists are in `docs/analysis/public-spending-2026-11/`:
- `ogp_codes.json`: the agencies, programs (with FY26 and FY27 approved amounts) and concepts from the two OGP data sheets.
- `cfda_listings.json`: USAspending's listings for Puerto Rico, FY2023–2025.

The tests check the crosswalk against them. To rebuild after a new data sheet:
1. `dump_ogp.py` reads the sheets.
2. `make_crosswalk.py` writes the CSV, the code lists and the review list. Its tables are where the choices live.

**What it can't decide yet:**
- **Hacienda Custodia (025, $3.4 B in FY27):** now matched to the budget resolutions for FY25-FY27 (see the `ogp_object` row above); FY24's lines and a few mixed ones (grants to legal aid and cultural entities, the FY25 transfer line) stay `other`.
- **Gaming Commission (311, $0.5 B) and the P3 Authority (276, $0.2 B):** one program each. They need object detail.
- **FEMA Public Assistance (97.036):** has no single function. Its money goes by damage category.

## The Commonwealth budget (OGP), PR 3

`ogp_budget.py` writes `site/data/spending_state.json`: what the agencies in the fiscal plan spent, were approved to spend and were proposed to spend, by agency, fund, function and concept of expense. It's island-wide, because the budget names no municipio.
- `python ogp_budget.py --refresh` reads the budget site again.
- `--check` compares a rebuild from the cache with the published file.
- The refresh unit is `spending` (source `ogp`: checked weekly, daily from March to July; a person reviews each rebuild).

**Where the data come from.** OGP publishes one "Sábana" data sheet (XLSX) per approved and per proposed budget, and the folder names change every year. So the script follows the links of www.presupuestos.pr.gov, its page for each budget and the separate sites of earlier budgets. On 2026-11-03 it found six sheets.

**How each column is chosen.** A fiscal year and stage (actual = "Gastado", approved = "Aprobado", proposed = the last "Propuesto" column) comes from the newest sheet whose lines add up to its own stated total within 0.5%. `notes` in the file records every column it didn't use and why:
- The FY27 approved sheet leaves out lines that have no FY27 money, so its FY25 spent and FY26 approved columns fall short of its totals (by $3.6 B and $3.9 B). They come from the FY27 proposed sheet instead.
- The May 2025 proposal gives FY24 spent as $30.40 B; the June 2025 approved sheet, which is newer, gives $30.78 B, and that one is used.
- The draft FY27 proposal of 2026-03-17 is marked "Privileged & Confidential". It is posted publicly, but it is not read.
- "Solicitado" (what agencies asked for) and "Baseline" columns are not read.

| Stage | FY2023 | FY2024 | FY2025 | FY2026 | FY2027 |
|---|---|---|---|---|---|
| Actual (spent) | $27.37 B | $30.78 B | $29.23 B | | |
| Approved | | $31.34 B | $33.28 B | $32.71 B | $33.58 B |
| Proposed | | | $33.47 B | $32.61 B | $33.57 B |

FY2023 spent, FY2024 approved and FY2025 proposed come from the 2025 budget's own site (`presupuesto2025.pr.gov/Sabana_Files/`, added 2026-11-17 after the project lead saw that FY2024 had no approved figure). The home page links that site, and the site links its sheets by a relative address. It does not send its intermediate certificate, so the certificate list that `requests` ships cannot check it. `ogp_budget.get` then tries again with the operating system's certificates, which can. Verification is never turned off: on a computer that cannot check the site, its sheets are skipped, the log says so, and those three columns are missing from the file.

Every column equals OGP's own total (`stated_total`); `tests/test_ogp_budget.py` checks that.

**Records.** Every line also becomes a normalized record in `cache/spending/records/ogp.csv` (112,146 on 2026-11-17), checked against the schema:
- level `state`, fiscal-year basis `pr_jul_jun`, tier `island_wide`, recipient `agency`
- function and concept from the crosswalk
- dedup group `ogp_federal` for federal funds

**What it doesn't cover:**
- Public corporations that run their own budgets.
- Budgets before the 2025 one (spent before FY2023, approved before FY2024): the current site links no data sheet for them.
- The recipients of Hacienda Custodia's lump sums: the Resolución Conjunta lists them, and parsing it is the next step for this source.
- A municipio for any line.

## The Public spending page, PR 4

`site/public-spending.html` is the first page that shows this dimension. It is a Knowledge Area page (area id `publicspending`, icon `account_balance`), published with the "In review" marker, the AI notice and `noindex`, like the FEMA disaster funding page. It reads only `spending_state.json`.

- **The budget:** pick a column (a fiscal year and a stage). The tiles show the total and the three funds, and a treemap shows the money by function; select a function to see its agencies. A table holds the same figures.
- **Approved and spent:** a dot plot by function for the latest year that has both columns (FY2025: $29.23 B spent of $33.28 B approved, 88%). Approved is a hollow dot and spent a filled one, so the two are told apart by shape, not by a second color.
- **Where the money comes from:** every column by fund, as labeled stacked bars.
- **What it pays for:** the chosen column by concept of expense.
- **CSV:** every row of the file, with agency names and one column per year and stage.

The fund colors are general `#338CB3`, federal `#D17F00` and special `#7A5BA6`, in that order. They pass the palette validator against the light surface (lightness band, chroma, color-blind and normal-vision separation, 3:1 contrast). The treemap uses one blue, because identity there is carried by the labels.

The page and its Spanish are written by `docs/analysis/public-spending-2026-11/make_page.py` from (English, Spanish) pairs, with every figure in the text read from the data. A string the site already translates keeps that Spanish. Dollars are written with the sign first in both languages ($29.23 mil millones). Tests: `tests/public_spending.test.js`.

## Capital projects by municipio (PICA), PR 5

`pica.py` writes `site/data/spending_pica.json`: the capital projects of the Planning Board's adopted Four-Year Investment Program (Programa de Inversiones de Cuatro Años, PICA), by municipio, agency and fiscal year. This is the dimension's first data placed in municipios.
- `python pica.py --refresh` reads jp.pr.gov again; `--check` compares a rebuild from the cache with the published file.
- It needs `pdftotext` (poppler), so its refresh unit `spending-pica` runs locally, not on the clean runner. The source `jp_pica` is checked every 14 days, daily from June to September.

**How it reads the program.**
- The adopted program is a PDF. Its agency tables (Tabla 3 onward, up to Apéndice A) have one line per project: description, municipio, type, four fiscal years and their total, in thousands of dollars.
- `pdftotext -raw` keeps each line together. Tables are assigned by page, because the text can show a page's rows before its "Tabla" header.
- A line counts only when its four years add up to its total.
- The municipio is the name right before the type, read with `muni_names`. A line that lists several municipios ("Adjuntas, Utuado") is split equally among them, as Hazard Mitigation is. A line for a region ("Región Metro"), several unnamed municipios, the island or no defined place is unplaced.
- A random check of 12 lines against the text found one wrong placement: a two-municipio line had been given to the second municipio only. The equal split fixes it.

**What it found (PICA 2025-2026 to 2028-2029).**
- 1,277 rows: $11.86 B of the $11.89 B the program states (99.7%). The rest is lines the text does not lay out whole, plus the Península de Cantera company, whose $4.2 M has no table.
- $10.18 B (86%) is placed in 77 municipios; Cataño has no project. $1.68 B is unplaced, mostly regional water works of the Aqueduct and Sewer Authority.
- The program includes public corporations that the OGP budget leaves out (the Aqueduct and Sewer Authority, $7.7 B; the Highways and Transportation Authority; the Metropolitan Bus Authority).

**On the page.** Section 4 of the Public spending page maps it:
- dollars per resident (the Census Bureau's 2025 estimate) or in total, for all agencies or one;
- five classes of equal count among the municipios with projects, in one blue ramp, and "no projects" in gray;
- the money not placed in a municipio beside the map, so nothing silently disappears;
- the ten municipios with the most, or one municipio's agencies when it is selected;
- a table.

The choices are kept in the address (`pm`, `pa`, `pg`).

**Stage.** A plan of recommended projects (`stage: proposed`), not appropriations or spending. Part of it is federal money (FEMA Section 406, HUD, EPA revolving funds) and Commonwealth budget capital, which other sources report, so it is never added to them.

## Federal money in Puerto Rico by function (USAspending), PR 6

`federal_awards.py` writes `site/data/spending_federal.json`: what federal agencies obligated for work or benefits in Puerto Rico in each final federal fiscal year since 2019, by program (assistance listing), award type and function. It is island-wide; the municipio figures stay in `economy_series.json` (`fed_awards_total` and its parts).

- `python federal_awards.py` downloads only the years missing from `cache/spending/usaspending/`; `--refresh` reads the last two years again; `--check` compares a rebuild from the cache with the published file.
- Source: USAspending's `spending_by_category` API, place of performance Puerto Rico, one call per year and award type (grants, direct payments, contracts, loans, other). Assistance is read by listing; contracts have none and are read by awarding agency. No key.
- A federal fiscal year counts as final from 15 November, as in `economy_series.py`.
- It runs with the `economy` refresh unit (the `usaspending` source is checked every 30 days, daily in November).

**Function.** A listing takes its crosswalk row (`spending.cfda_function`), or else its agency prefix's default with low confidence. A contract takes its awarding agency's default (`CONTRACT_AGENCY`). A prefix with no crosswalk row is counted as "other" and named in `unmapped` (none now: `cfda_agency,44` for the National Credit Union Administration was added with this PR).

**What it found (federal FY2025).** $38.44 B, equal to USAspending's own total: $28.05 B in direct payments (73%), $9.45 B in grants, $0.92 B in contracts. By function: social services $17.68 B (Social Security, nutrition), health $13.31 B (Medicare, Medicaid), education $2.17 B. "Other" is $1.44 B, all FEMA Public Assistance (97.036), which the crosswalk leaves as other because its categories mix purposes. The highest year was FY2021 ($65.23 B), with pandemic relief.

**Never add.**
- The Commonwealth budget's federal funds are federal grants here too (dedup group `ogp_federal`).
- FEMA Public Assistance (97.036) and Hazard Mitigation (97.039) are counted from OpenFEMA, so their records carry `fema_pa` and `fema_hma`.
- Records carry `recipient_type: mixed` for grants, loans and other (a federal total over recipients of several kinds; added to `spending.RECIPIENT_TYPES` with this PR), `individual_aggregate` for direct payments and `private` for contracts.

**On the page.** Section 5 of the Public spending page: tiles by award type, one column per year, the year chosen by function, the 15 largest programs and a CSV. The year is kept in the address (`fy`). The file loads after the budget is drawn (`later` in `routes.json`).

## More charts on the Public spending page, PR 7

Step 7 of the Phase 0 build order: three drawings from data the page already has. They are in `site/js/public_spending_charts.js`, which `public_spending.js` loads once the budget is drawn (`deferred` in `routes.json`, budget 10 KB), so the page's first-load scripts stay under their 40 KB.

- **Pipeline (section 1).** For each fiscal year, the proposed, approved and spent columns of the budget side by side, for the whole budget or for the function chosen in the treemap. A stage the data sheets do not give for a year is drawn as a dot. A table has the figures.
- **From fund to function (section 2).** The budget chosen at the top, as bands from the fund the money comes from (General Fund, federal, special) to the function it pays for; a band's width is its dollars. Every function keeps room for its label; on a phone the names wrap and a legend names the funds.
- **Equal hexagons (section 4).** A "View" choice draws the capital projects map as 78 equal hexagons with a short label each, so a small municipio counts on the screen as much as a large one. The choice is kept in the address (`pv=hex`).

**The hex layout.** `docs/analysis/public-spending-2026-11/make_hex.py` writes it into the script from `site/data/municipios.geojson`: each municipio's centroid is scaled to a 13-column grid (from the main island's width), each takes the free cell nearest its centroid, farthest from the center first, then pairs swap cells while that lowers the total squared distance. Vieques and Culebra keep their place east of the main island. Labels are the initials of a name of several words, else its first three letters, with another pick on a clash. `tests/test_spending_hex.py` checks that the script's layout is what the generator makes now and that the island keeps its shape; `tests/public_spending_charts.test.js` checks one hexagon per municipio, distinct labels and no overlap.

## Sector view, data age and README, PR 8

Step 8 of the Phase 0 build order (HANDOFF decision 87).

**Section 6, one sector across the sources.** `site/js/public_spending_sectors.js`, loaded after the page is ready (`deferred` in `routes.json`), sets side by side for the function chosen (`sx` in the address):
- the Commonwealth budget: last approved year and its share of the budget, and the last year with both approved and spent;
- federal obligations of the last federal fiscal year;
- the capital projects of the four-year program whose agency has that function;
- approved dollars per resident. One population basis (decision 73 (3)): the Census Bureau's estimate for July 1, 2025, the one the capital projects map uses;
- the function's largest agencies.

The lines are never added together, and the section says so.

**Education.** It adds the Department of Education's (OGP agency 081) spending in the last spent fiscal year, divided by public school students in the matching school year (`sch_enroll` in `education_series.json`, loaded on first use: FY2025 = the 2024-25 school year). FY2025: $3.88 B for 235,819 students, $16,465 per student. The estimate by municipio is the apportioned tier of decision 73 (5): that spending split by each municipio's share of the students. It is labeled an estimate, sits in a closed table, and is never added into any total. A test checks the estimates add up to the spending they split.

**Data age.** Each data section says when its file was built (the file's `built` date) and is marked when the file is older than two update cycles. The cycle comes from the dataset's `cadence` in `dictionary_src/datasets.json` (annual = 365 days), written into the page by `make_page.py` (`data-age`, `data-cycle`).

**README.** A section on the Public spending Knowledge Area and the four scripts in the layout list.

## Disaster recovery subawards by municipio, PR 9

Step 6 of the Phase 0 build order, built from the one source that met the lean rule (HANDOFF decision 89). The 2026-11-05 check:
- **COR3 (recovery.pr.gov).** Its data comes from the portal's own API, which did not answer a plain script, and it is not worked around. The public ArcGIS layers (arcgis.recovery.pr) can be read, but they state no license and hold FEMA Public Assistance projects that OpenFEMA already gives the site.
- **Vivienda (recuperacion.pr.gov).** The transparency portal has report pages and dashboards, but no CSV or Excel file and no license.

`cdbg_dr.py` writes `site/data/spending_cdbgdr.json` from USAspending's `spending_by_geography`, filtered to the Puerto Rico Department of Housing's disaster grant numbers (`DR_AWARDS`: DM, DP, DE, DF, DZ, DN, DI; the yearly block grants, DC, and the COVID grant, DW, are left out). Final federal fiscal years since 2019 are covered. For each year it reads subawards by municipio, subawards for Puerto Rico as a whole and the prime grants for Puerto Rico as a whole. Subawards for Puerto Rico that name no municipio are kept as `unplaced`.

**What it found (FY2019 to FY2025).**

| Measure | Amount |
|---|---|
| Prime grants obligated (USAspending places them in San Juan) | $19.10 B |
| First-tier subawards reported | $4.90 B (26% of the prime grants) |
| Subawards placed in municipios (67 of the 78) | $4.33 B |
| Subawards not placed in a municipio | $0.56 B |

Per resident, Culebra, San Juan and Vieques lead. A subaward is placed where the work is reported.

**Never add.** Subawards are part of the prime grants, which are also inside section 5's federal money (assistance listing 14.228). The records carry `dedup_group: cdbg_dr`.

**On the page.** Section 7 is drawn by `site/js/public_spending_recovery.js`, loaded after ready. It shows:
- a map by municipio, per resident or in total, summed from the year chosen;
- the prime grants, the subawards, the part on the map and the part not placed, beside the map;
- the ten municipios with the most;
- a table.

**Spanish module.** The Spanish that only the after-ready parts use (charts, sector view, recovery: 31 strings) moved to the page's module `after` (`i18n_src/es/public_spending_after.json`, `es.publicspending.after.js`). `public_spending.js` loads it before those scripts, and sections 6 and 7 wait unseen until it is in. This keeps the page's first-load scripts within 40 KB (39.5). Strings that name CDBG stay in English on the Spanish page (decision 21).

## The crosswalk review, 2026-11-09

The project lead asked for the 40 flagged rows to be decided (HANDOFF decision 92). Each row was decided against the UN Classification of the Functions of Government (COFOG), mapped to the crosswalk's functions, with one rule for rows of the same kind. The decisions are in `docs/analysis/public-spending-2026-11/crosswalk_decisions.py`, with the list in `crosswalk_decisions.md`. `make_crosswalk.py` applies them before it writes the CSV, so a rebuild keeps them. A decided row has flag `reviewed` (added to `spending.FLAGS`) and its decision after its reason.

**Three functions changed:**
- the Public-Private Partnerships Authority (OGP agency 276), from other to utilities_energy: its budget is the energy system's contracts;
- emergency medical services (program 045-1224), from public_safety to health: COFOG puts ambulance services under health;
- FEMA debris removal (category A), from general_government to environment_natural_resources: COFOG puts waste management under environmental protection.

**Kept as drafted (31 rows),** now marked reviewed. Lottery, gaming and custodial pass-throughs stay "other": they are not a function of government, or they mix several. Communications subsidies stay with utilities, energy and communications. FEMA Public Assistance stays "other" in the federal totals, because OpenFEMA counts it by damage category.

**Retired (6 rows).** The six Contralor contract groups are kept only so the codes stay documented: the Contralor source was dropped on 2026-11-04.

**Effect.** In the FY2027 approved budget, $196.1 M moved from "other" to utilities and energy, and $35.7 M from public safety to health. The federal file is unchanged.

**Same day.** Leadership approved the page (decision 73 (7)). Its "In review" marker and `noindex` were taken off, and the AI notice stays (`ai: true`). The Compliance reviews of the federal grant content (decision 21) stay open, with the CDBG and HUD Spanish held.

## Stage and basis of every figure (decision 96, step 1)

Plan: `docs/spending-execution-proposal-2026-11.md`, step 1. A CPA colleague's review (2026-11-10) asked that every figure say how far the money has gone and whether it is reported or audited. No new data.
- **A "Stage and basis" line in every data section** (`<p class="ps-stage">`): proposed, approved and spent (reported by the agencies to OGP, not audited) for the budget; planned for the capital program; obligated (reported to USAspending, not paid out) for federal money; subawarded for disaster recovery. Section 6 gets a "Two fiscal years" line instead: the Commonwealth's year runs July to June and the federal one October to September, and each line shows its source's latest year.
- **The FY2025 difference** between approved and spent gets a note: what it can come from (reserves, payments after June 30, legal restrictions, accounting differences, amendments), that the two figures come from two OGP data sheets (`make_page.py` asserts it), that it does not show inefficiency alone, and that the audited close is Hacienda's Basic Financial Statements (latest found: FY2023).
- **Scope:** the lede names municipal budgets as outside, next to the public corporations; the capital map's caution says where a project is built is not who runs the money or who benefits; "What the page does not do" now says the two maps place plans and subawards, and that the page shows assignment, not results.
- **Leftover fixed:** section 5's caution still called the crosswalk a draft.
- **Loading:** the stage lines and the gap note carry `data-t-wait` and their Spanish is in the "after" module (`make_page.py` strips them from `outside`), so the page's first-load scripts stay within budget (40.7 of 41 KB); `public_spending.js` translates and shows every `main [data-t-wait]` when the module is in.
- **Glossary:** subaward (held for Compliance, like obligation), COFOG and Basic Financial Statements.

## Obligated and paid out (decision 96, step 2)

Plan: `docs/spending-execution-proposal-2026-11.md`, step 2. `federal_outlays.py` writes `site/data/spending_outlays.json`; section 5 of the page shows it in the "Obligated and paid out" card (`site/js/public_spending_outlays.js`, loaded after ready with the page's "after" Spanish module).
- **Source:** USAspending.gov's award search (`spending_by_award`), place of performance Puerto Rico, awards **signed** in each federal fiscal year (`date_type: date_signed`), every page, cached in `cache/spending/outlays/`. Each award gives its obligation over its life (`Award Amount`) and its outlays to date (`Total Outlays`). Outlays start in FY2020, so only awards signed from FY2020 are read; the two latest signing years are read again on `--refresh`, since their outlays still grow.
- **Read:** grants (02 to 05) and contracts (A to D). Not read: direct payments (paid when recorded), loans and insurance (no outlays). FEMA Public Assistance (97.036) is kept apart in `excluded`: USAspending's awards do not follow its projects (step 3 counts it from OpenFEMA).
- **Capping:** an award's paid-out amount counts up to its obligation; awards reporting more are counted in `totals.*.over_n` and `over_usd` (46 grants, $0.66 B, mostly Medicaid), and awards with no outlay in `no_outlay` (4,335 of 14,501 contracts, so the contracts' share is understated).
- **First run (2026-11-13), FY2020 to FY2025:** grants $68.0 B obligated, $41.1 B paid out; contracts $7.9 B and $1.6 B. By function: Housing 34% paid out, Health 74%, Education 91%, Public safety 12%.
- **Never added** to `spending_federal.json`: the same awards, counted by the year each obligation is made rather than the year the award was signed.

## Share paid out by signing year (decision 109, step 1)

Plan: `docs/spending-questions-2026-11.md`, step 1. The "Obligated and paid out" card now shows, above the bars by function, one column per signing year with the share paid out (`#psOutYrs`, drawn by `public_spending_outlays.js` from the same `spending_outlays.json`), with the caution that older awards have had more time to pay out and that a low share shows where to ask, not non-compliance. With grants and contracts, FY2020 to FY2025: 53%, 45%, 61%, 64%, 63% and 68% (2026-11-13 build). The after-ready budget of the page (`routes.json`, `deferred_kb`) went from 15 to 16 KB for it: it is loaded after the page is ready and never blocks the first view.

## FEMA Public Assistance by stage and age (decision 109, step 2)

Plan: `docs/spending-questions-2026-11.md`, step 2 (also decision 96, step 3). `fema_pa_stage.py` writes `site/data/spending_fema_pa.json`; section 8 of the page shows it (`site/js/public_spending_fema.js`, after ready, Spanish in the "after" module).
- **Source:** OpenFEMA Public Assistance Funded Projects Details, every Puerto Rico row, cached in `cache/spending/openfema_pa.json` with the date read. Federal share obligated: OpenFEMA has no payments.
- **Stage:** closed = Project Closed Out; open = Obligated; pending = any Pending step. **Age:** years from a project's first obligation to the day read; medians are weighted by dollars.
- **Place:** county code to municipio (FIPS 72 + code); Statewide projects are summed apart, never spread.
- **First read (2026-11-17):** 23,059 projects, $39.05 B; closed $4.05 B, open $28.74 B, pending $6.25 B; Statewide $30.41 B (78%); median age of open money 4.8 years; $16.7 B open more than five years.
- **Page:** tiles by stage, a stage bar with the Statewide share, open money by age, a municipio map (dollars open more than five years per resident, share closed out, or median age of what is open) with the ten highest beside it, tables by municipio, disaster and damage category, and a link to the Disaster funding and need page.
- **Budget:** the page's after-ready budget (`deferred_kb`) goes from 16 to 20 KB for the new module and its Spanish; the first load is unchanged.
- **Never added** to section 5 or to the FEMA series of the Analysis tab: the same money.

## CDBG-DR draws: the prime grants, obligated and paid out (decision 109, step 3)

Plan: `docs/spending-questions-2026-11.md`, step 3 (also decision 96, step 4). `cdbg_dr.py` now also reads, in one award-search call cached in `cache/spending/usaspending/cdbgdr_grants.json`, each prime grant's obligation over its life and its outlays to date, into `spending_cdbgdr.json` (`grants`, `grants_read`). Section 7 shows them as bars (`#psRecGrants`, `public_spending_recovery.js` v2), each with its purpose (`PSRecovery.kind`: DP-0002 is mitigation, the other DP grants and DM are the 2017 hurricanes, DE the electrical grid, DZ the 2020 earthquakes, DN Hurricane Fiona, DI the 2008 floods, DF other disasters).
- **First read (2026-11-17):** $20.64 B obligated, $6.35 B paid out (31%). B-17-DM 80%, B-18-DP-0001 51%, B-18-DP-0002 (mitigation) 8%, B-18-DE (grid) 9%, B-19-DP 24%, B-21-DZ 13%, B-23-DN 0.1%.
- **Check against HUD (decision 96 (c): a check, never published):** HUD's CDBG-DR Grant Expenditure Report and CDBG-MIT Grant Financial Report for 1 September 2026 (hud.gov, CPD documents, CDBG-DR) give award minus balance. For four of the six grants over $100 million they are within 2% of USAspending's outlays; the mitigation grant (4.2%) and the 2020 earthquakes grant (19%) are lower at HUD, whose report is dated 1 September 2026 while USAspending was read on 2026-11-17: B-17-DM $1,209 M (USAspending $1,210 M), B-18-DP-0001 $4,117 M ($4,181 M), B-18-DP-0002 $652 M ($680 M), B-18-DE $171 M ($172 M), B-19-DP $67 M ($67 M), B-21-DZ $21 M ($25 M). HUD also rates each grant's pace; that rating is not used.
- **Budget:** the page's after-ready budget goes from 20 to 22 KB for the grant bars and their Spanish; the first load is unchanged.
- The grants' outlays count what the Treasury paid the Department of Housing, not what it has paid its contractors or subrecipients, and never what the work achieved.

## Where each line's function comes from (decision 109, step 4)

Plan: `docs/spending-questions-2026-11.md`, step 4. `spending.ogp_basis` names where `ogp_function` takes a line's function from, in its own order: a concept that overrides (debt service, pensions), an object row, a program row, or the agency's general function. `ogp_budget.py` sums the budget by basis for every column (`spending_state.json` `basis.by_column`, in `basis.kinds` order) and, for the latest approved budget (`basis.column`), lists each agency with its total, its dollars by agency default, the number of functions its money reaches (debt and pensions aside) and its general function (`basis.agencies`).
- **FY2027 approved:** program 7.0%, object 7.3%, concept 10.9%, agency default 74.8%; nine agencies split their money across functions (Treasury custody 025 reaches six). The largest agencies classified only by their general function: the Health Insurance Administration ($5.44 B, health), the Department of Housing ($3.29 B), ADSEF ($3.25 B).
- **Page:** a card in the Method section (`#basis`, `PSCharts.basis` in `public_spending_charts.js` v3; Spanish in the "after" module) with a stacked bar and the shares per budget, the eight largest agencies classified only by their general function (95% or more by default), and the agencies whose money is split.
- **Budget:** the page's after-ready budget goes from 22 to 24 KB (22.3 used). Over decision 109 it went from 15 to 24 KB, all after the page is ready; the first load stayed within 42 KB.
- **Use:** the next crosswalk review starts with the largest agencies classified by default.

## My municipio (decision 109, step 5)

Plan: `docs/spending-questions-2026-11.md`, step 5. Section 9 of the page has a municipio picker. On the first choice the page loads the Spanish module "municipio" (`i18n_src/es/public_spending_municipio.json`, written by `make_page.py` for the keys only `public_spending_municipio.js` uses) and then the script, which fetches `spending_municipio.json` (`municipio_view.py`). Like the map's Economy engine, the script loads on first use: it is not in the HTML or in the page's after-ready list (`routes.json` lists the data file under "on_use").
- **Data:** one row per municipio, only from published files: the capital plan and its three largest agencies, CDBG-DR subawards, FEMA Public Assistance by stage and age, federal awards (latest year and five-year average), and the municipio's ABRE Tu Municipio slug (`abretumunicipio.org/municipio/<slug>?year=2024`; decision 109 (c): link, never copy).
- **The view:** what is in the territory and who runs each part; the four questions of decision 109 answered for the municipio, with question 2 (paid) marked as not published by municipio, and why; what could be requested to evaluate execution (text for readers: FPR makes no requests); the link to the municipal government's finances on ABRE Tu Municipio.
- **Scope note:** the page's lede now links ABRE Tu Municipio for municipal finances.
- **Placeholders** in strings that reach the Compliance filter (`CDBG|LIHTC|WCRP|HUD`) are named so they do not hold a string by accident (`{sub}`, not `{cdbg}`).

## Section 3 opens, clearer titles, federal money from FY2008 (2026-11-17)

The project lead on 2026-11-17: section 3 should say more and open item by item; chart titles were hard to tell from the text; "the ten municipios with the most dollars" did not say dollars of what; could the federal money go back to 2000?
- **Section 3:** each concept of expense is a `<details>` row (first-load markup in `public_spending.js`); opening it calls `PSCharts.concept` (`public_spending_charts.js` v4): a definition of the concept, its split by function and its six largest agencies in the budget chosen.
- **Titles:** `.ps-head` and card titles have a left accent bar, 16 px bold in the primary dark color; card subtitles (`h4`) are small capitals. `housing.css` (v21, every Knowledge Area page) makes `.card-head h3` and a card's first `h3` 16 px bold in the same color.
- **Rankings:** "Capital projects planned (per resident | in dollars): the ten highest municipios" and "Disaster recovery subawards (per resident | in dollars): the ten highest municipios".
- **Federal money from FY2008:** `federal_awards.FIRST_YEAR` is 2008, the first year USAspending's search API answers (FY2001 to FY2007 exist only in its bulk archives; FY2000 not at all). Older years have assistance with no listing, kept as one "none" row with function "other". Years before the DATA Act (2017) are less complete (FY2008 grants $1.1 B against $3 B to $4 B after); the chart says so. FY2026 is left out of this build (its grants were $3.9 B against $9.4 B in FY2025 on 2026-11-17, still being reported); the next refresh adds it.

## Approved and reported spent, by agency and fund (decision 112, step 2)

Section 1 of the page has a part "By agency and fund". The reader chooses a fund and a fiscal year, and the page lists the agencies by the difference between their approved budget and what they reported as spent.

- **No new data.** It reads `site/data/spending_state.json`, which the page already loads: the columns of a fiscal year with both stages (`approved` and `actual`). On 2026-11-20 those are fiscal years 2024 and 2025. A new year appears by itself when the data sheets give both stages.
- **Loaded on first use.** `site/js/public_spending_agencies.js` (`PSAgencies`) and its Spanish (module `agencies` of the page in `i18n_src/pages.json`, scope `public_spending_agencies`) load when the reader first chooses a fund, like My municipio. `public_spending.js` only fills the fund list and loads the module.
- **The funds are never mixed.** General Fund, federal funds and special funds each have their own table and their own caution: federal money is often awarded for several years, and special funds depend on their own revenue.
- **Agency codes that moved are joined** (`JOIN` in the module). One so far: the data sheets approve the Police inside code 045 through fiscal year 2026, and the fiscal year 2027 sheets, which also give what was spent in 2025, report it under its own code 040. Read apart, 040 shows spending with no budget and 045 a budget barely spent. The joined row carries both names and a mark. Add a pair to `JOIN` only when the data sheets show the same move; a test checks that no agency with more than $20 million has only one of the two stages.
- **Wording.** "Difference" and "reported spent". Never a surplus, a loss or money left over: the data sheets give the budget as approved, not as amended, and "spent" is what each agency told OGP in the next budget process, not the audited close.
- **What it does not say.** Why a difference exists, and what was done with each one. **The rule is explained since 2026-11-23,** from OGP's Manual of the Budget Process (https://gestion-presupuestaria.ogp.pr.gov/, section "Reasignaciones y reprogramaciones"): in the General Fund, money of an earlier fiscal year cannot be used unless the certified budget says so; in special revenue funds, the income of earlier years can be used under the rules that apply; federal money follows each grant. The note under the tables gives the one that fits the fund chosen.

Tests: `tests/public_spending_agencies.test.js`.

## Notes and corrections (decision 112, step 3)

Short notes where readers stumble, each in the place where its figure is. They are static text of the page; the generator (`docs/analysis/public-spending-2026-11/make_page.py`) computes their figures from `spending_state.json`, newest approved budget, and stops if an agency code no longer carries the expected name.

- **The Oversight Board.** The paragraph above the chart of proposed, approved and spent says who proposes (the Governor), who adopts (the Legislature) and who certifies (the Oversight Board), and that the budget in force is the certified one. The Board has no column: the data sheets give three stages. Source: PROMESA, section 202 (48 U.S.C. 2142). The paragraph links to the cycle page.
- **The way back from a function.** A function chosen in the treemap also filters the stages chart, which is far below. That chart has its own "All functions" control (`psBack2`), shown only while a function is chosen; it leaves the reader at the chart.
- **Where "spent" comes from.** The "Gastado" column of OGP's data sheets: what each agency reported in the next budget process. The page reads no figure from Hacienda and none is audited. Said in the stage line of section 1 and under the stages chart.
- **Custodial appropriations and the two housing bodies** (hero). Codes 025 and 017 are not the own budgets of Hacienda (024) and OGP (016). The Department of Housing (078) and the Public Housing Administration (106) are two bodies; the second is attached to the first and runs the public housing projects (Act 66 of 1989, as OGP's budget document for the agency describes it).
- **Debt service** (section 3). What it is, its amount and the share under Hacienda's custody, and the order of payment of the Constitution of Puerto Rico, Article VI, section 8 (text read on 2026-11-20). The note does not call it a fixed claim.
- **Grants and loans** (section 5). A loan is repaid; the Loans figure is the cost to the federal government, not the amount lent.
- **Why municipios differ** (section 9). Public Assistance is obligated by project that an applicant requests and documents, and the large recovery grants to Commonwealth agencies are recorded in San Juan. The note names no HUD program, so its Spanish is not held (decision 21).
- **Not written:** that the capital plan mixes Commonwealth and federal money. `spending_pica.json` carries no fund for a project, so the page cannot show it; the page already says the program is a plan, not money approved or spent.

**Weight.** The notes carry `data-t-wait`, so their Spanish is in the after-ready module (`public_spending_after`), not in the first load (42.4 of 43 KB). The page's after-ready limit (`deferred_kb` in `dictionary_src/routes.json`) went from 25 to 27 KB; 26.2 is used.

Tests: `tests/public_spending.test.js` (the last test).

## OGP's Manual of the Budget Process as a source (2026-11-23)

https://gestion-presupuestaria.ogp.pr.gov/ is OGP's own manual of the budget process (six chapters; updated 2025-11-18; the whole text is also a PDF there). Read on 2026-11-23: the stages (chapter 2.3), the glossary (1.3.1), reserves (3.2), reassignments and reprogramming (3.5) and special revenue funds (3.6).

- **Stages.** Ten: the Board's calendar; OGP's budget letter; the multi-year financial plan; the agencies' requests; target meetings; the Governor sends the proposed budget to the Board; the Board approves it or notifies violations; the approved version goes to the Legislature; the Legislature evaluates; the Governor signs the joint resolution and the Board issues the certification. The paragraph of the stages chart and the cycle page follow this order.
- **What the three columns are** (the manual's glossary): proposed is the budget the Governor presents to the Board and the Legislature; approved is the budget the Board certified; spent is the budget used during the fiscal year (July 1 to June 30).
- **Money of earlier years** (reassignments and reprogramming): not in the General Fund unless the certified budget says so; allowed in special revenue funds. The same section says a move from one agency to another is allowed with OGP's approval, which is why an agency can report more than its approved budget.
- **Reserves:** OGP may hold back resources during the year, with the Board; the Legislature may add reserves in the joint resolution.
- **Citing it.** The number in a section's address is not the number its own menu shows, so cite a section by its title.
- **A word the pages do not take.** The manual says "sobrantes" for differences in operating and payroll lines. The pages keep "difference": their figures compare two data sheets and are not the manual's measure (decision 112 (c)).
