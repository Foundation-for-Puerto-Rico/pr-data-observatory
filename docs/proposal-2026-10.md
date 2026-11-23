# Proposal: a general, cross-domain PR Digital Twin (Phase 2)

Date: 2026-10-05. Follows `docs/audit-2026-10.md`. **No code or data has been changed for this proposal.** It adopts the recommendations I made at the end of Phase 1, which you approved:

1. **Population and households** becomes the first new domain. Public money and recovery sits under Economy as a sub-domain until a governance domain has enough data.
2. **Bilingual names live in the registry from day one**, and a string layer (Spanish first) is built right after the registry and before the layer engine is generalised.
3. **Neutral landing view:** Puerto Rico with a cross-domain overview. Tourism pins become a toggle inside the visitor-economy module, off by default.
4. `dictionary_src/domains.json` is reshaped into the domain registry.
5. One mapping replaces the three domain vocabularies (dictionary areas, `wanted.json` themes, your list).

**At a glance.**
- **Architecture:** a domain registry and data contract; every dataset reduced to series on one geography crosswalk; one layer engine; Spanish-first strings (sections A-C).
- **Data (verified by research agents on 2026-10-05):** Education, Health and Infrastructure can become strong with keyless sources; tract, block-group and barrio Census data are available with margins; Population becomes a domain now; public safety and governance stay mostly blocked (section D).
- **First results from data we already hold:** residents and housing units exposed to flood, sea level rise and surge, and near transit, schools and hospitals, by municipio and barrio (item 5).
- **Plan:** 17 ranked items in section J, starting with two that change no screens (items 0 and 1). Decisions needed are in section K.

Effort scale: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks, **XL** more than 2 weeks of focused work. Value is my judgement of decision value for planners and for cross-analysis.

## 0. The idea that organises everything

**Reduce every dataset, in every domain, to a series on a shared geography at build time.** A series is: values for each area (a unit of the geography crosswalk) for each period, with optional margins of error. Point layers (schools, hospitals, tourism places, stops), polygon layers (flood, protected land, land use) and networks (transit, roads) stay as *display layers*, and each also publishes *aggregated series* (counts, densities, residents or housing units inside, share of area). The layer engine, the workbench, the profiles, the chat and the catalog then only need to understand series and a registry. A new dataset that follows the data contract appears everywhere with no UI code, which is the requirement in the brief.

## A. Information architecture and repositioning

### A1. The domain registry

One file, `dictionary_src/domains.json`, replaces `DOMAINS` in `dictionary.py`, the hard-coded groups in `economy.js`, the private domain map in `chat.js` and the themes in `wanted.json`.

```json
{
  "version": 1,
  "domains": [
    { "id": "housing", "parent": null, "order": 10,
      "name":        { "es": "Vivienda", "en": "Housing" },
      "description": { "es": "...", "en": "..." },
      "icon": "home_work", "accent": "--fpr-blue",
      "headline": { "variable": "housing.median_gross_rent", "norm": "value" },
      "examples": { "es": ["¿Dónde es más alto el alquiler?"], "en": ["Where is rent highest?"] },
      "status": "active" },
    { "id": "economy.visitor-economy", "parent": "economy", "order": 41, "...": "..." }
  ]
}
```

- **Fields:** `id` (dotted for sub-domains), `parent`, `order`, bilingual `name` and `description`, `icon`, `accent` (a design token), `headline` (the indicator for the overview), `examples` (starter questions for the chat), `status` (`active`, `planned`, `empty`). `system: true` marks non-data entries (base geography, methods, map tools) so they never appear in the overview.
- **Adding a domain = adding one object.** Everything else reads the registry: the layers panel, the catalog, the overview, the profiles, the chat chips, the dictionary page and the documentation (`python dictionary.py --domains` writes `docs/domains.md` so even the docs never hard-code names).
- **Colour is not the identifier.** FPR's palette has four hues; with seven or more domains, colour alone would fail WCAG ("not by colour alone") and the brand rule against colour-coding programmes. Icon plus name identify a domain; the accent token only tints the card.
- **Starting set** (ids): `housing`, `education`, `infrastructure` (sub-domain `infrastructure.mobility`), `economy` (sub-domains `economy.visitor-economy`, `economy.public-money`), `environment` (sub-domains `environment.hazards`, `environment.land`), `health`, `population`. Education and Health are `empty` until data lands, and say so in the overview.
- **Secondary domains:** every dataset and variable carries `domains: ["primary", "secondary", ...]`. School flood exposure is `["education", "environment.hazards"]`.

### A2. Dataset tagging and migration of the 594 existing items

A script maps each dictionary entry from its current area to registry domains, writes a review table, and I check the ambiguous ones with you.

| Current area | Primary domain | Notes |
|---|---|---|
| Housing | `housing` | income, poverty, employment, education items get `economy` or `education` as primary |
| Economy and work | `economy` | tourism jobs also `economy.visitor-economy` |
| Public money and recovery | `economy.public-money` | FEMA individual assistance also `housing` |
| Tourism supply | `economy.visitor-economy` | flood, protected, transit flags of places get a secondary domain (`environment.hazards`, `infrastructure.mobility`) |
| Population and households | `population` | |
| Hazards and environment | `environment.hazards` | protected areas and land use go to `environment.land` |
| Land and boundaries | `environment.land` (land use) or `system.geography` (boundaries) | |
| Mobility and transit | `infrastructure.mobility` | |
| Measures and methods, Map layers and tools | `system.docs`, `system.tools` | not data domains |

`wanted.json` gains a `domain` field using the same ids (its eight themes map: Hazards and resilience to `environment.hazards`, Infrastructure and services to `infrastructure`, Mobility and safety to `infrastructure.mobility` or `public-safety` if that domain is created, Health and education split in two, Land and buildings to `environment.land`, Governance and recovery to `economy.public-money` for now).

### A3. A neutral landing view

- **Opens on:** Puerto Rico, municipio boundaries only, no pins, no heat. The first load needs only `catalog.json` (registry plus dataset index, about 100-200 KB uncompressed) and the municipio boundaries (0.3 MB).
- **Overview panel (generated from the registry):** one card per domain showing its `headline` indicator for Puerto Rico (value, year, unit, a sparkline) and a "Show on map" button. Domains with no data show "No data yet" and a link to what is planned (from `wanted.json`), so empty domains are visible, not hidden.
- **Clicking a card** adds that indicator to the layer stack. Nothing is selected by default.
- **Visitor economy** is a module under Economy with its own card; its pins load only when switched on (this removes 2.9 MB of the first load).
- **3D, Housing and Dictionary pages** keep working and get the same header and domain navigation.

### A4. A single catalog

The dictionary page already searches 594 items. I propose to **extend it rather than build a second page**: domain and sub-domain tree from the registry; filters for geography level, years covered, source and licence class; every entry linked to its dictionary text; an **"Add to map"** button on each variable; a compact catalog tab inside the map panel that uses the same data. New domains appear automatically.

### A5. Rewritten text (for your approval; nothing is changed yet)

The static HTML cannot list domains (the brief forbids hard-coding them), so meta tags use generic wording; anything that lists domains is generated from the registry at run time.

**README intro (EN):**
> # PR Digital Twin
> A free, open model of Puerto Rico. It brings public information from many fields onto one map and one timeline, so you can compare and combine it: rent against income, flood zones against where people live, transit access against jobs, and how each has changed. Built by Foundation for Puerto Rico as a tool for public use and benefit. Open data only, no API keys. Personal data and business contact details are never published.
> The fields ("domains") are defined in `dictionary_src/domains.json` and grow as data are added; `docs/domains.md` lists the current set.

**README intro (ES):**
> # Gemelo Digital de Puerto Rico (PR Digital Twin)
> Un modelo abierto y gratuito de Puerto Rico. Reúne información pública de muchos campos en un mismo mapa y una misma línea de tiempo, para que puedas compararla y combinarla: el alquiler frente al ingreso, las zonas inundables frente a dónde vive la gente, el acceso a transporte frente a los empleos y cómo ha cambiado cada cosa. Creado por Foundation for Puerto Rico como herramienta para el uso y beneficio del público. Solo datos abiertos, sin claves de API. Nunca se publican datos personales ni datos de contacto de negocios.

**Replace README "What it answers" with:** What is where and how much; how places compare; what changed since a year; what two things have in common (and what that does not prove); what is exposed to a hazard; what is missing from the data.

**Page `<title>` and meta description (EN / ES):**
> PR Digital Twin / Gemelo Digital de PR
> A free, open model of Puerto Rico: public data from many fields on one map and one timeline, for all 78 municipalities. Developed by Foundation for Puerto Rico as a tool for public use and benefit.
> Un modelo abierto y gratuito de Puerto Rico: datos públicos de muchos campos en un mapa y una línea de tiempo, para los 78 municipios. Desarrollado por Foundation for Puerto Rico como herramienta para el uso y beneficio del público.

**Top-bar subtitle:** generated from the registry (the domain names in the user's language). Static fallback: "Datos públicos de todo Puerto Rico, en un solo mapa / Public data for all of Puerto Rico, on one map".

**About lead (EN):** "A living, open model of Puerto Rico. It puts public data from many fields on one map and one timeline so you can see how things connect: where people live and what is near them, what things cost and what people earn, what is exposed to risk, and how all of it has changed." (ES: "Un modelo vivo y abierto de Puerto Rico. Pone datos públicos de muchos campos en un mismo mapa y una misma línea de tiempo para ver cómo se conectan las cosas: dónde vive la gente y qué tiene cerca, cuánto cuestan las cosas y cuánto gana la gente, qué está expuesto a riesgos y cómo ha cambiado todo.") The "what it is for" list is generated from domain `description`s plus fixed audience lines (residents, planners, researchers, funders).

**SHARE.md paragraph (EN):** "The PR Digital Twin is an open model of Puerto Rico built by Foundation for Puerto Rico. It puts public data from many fields (housing, jobs, transport, hazards and more, growing over time) on one map and one timeline for all 78 municipalities, so anyone can compare them, ask questions and cite the source of every number." The ES paragraph mirrors it. SHARE.md may name examples; it is marketing copy, not product, but I will keep the list explicitly "and more".

**Chat starter chips:** one question per active domain, taken from each domain's `examples` field (so a new domain adds its own), plus "What data is missing?" and "¿Qué datos faltan?". Today's neutral chips stay until the registry exists.

**Layers tab, Municipality tab, Rankings:** rebuilt from the registry (A1, B), so the tourism-first ordering disappears with the code that produced it.

## B. One cross-domain layer engine

### B1. Dataset adapters feed one engine

| Adapter | Source data | Becomes |
|---|---|---|
| Area series | today's economy and housing series | series on municipio (later tract) |
| Snapshot fields | `municipalities.json` (47 non-housing fields) | one-period series, so they join the stack |
| Point aggregate | tourism places, schools, hospitals, stops | counts, density, share, per-resident series on any level and on hexagons |
| Polygon exposure | flood, protected land, land use | area share, residents, housing units, jobs inside, per area (block centroids give exact residents) |
| Derived | composites, ratios between series | computed in the browser from other layers, with the formula stored |

The engine's contract: `values(layer, period, level) -> { ids, values, moe, flags, meta }`. Everything else (legend, classification, hover, popups, workbench, chat, 3D) uses that and nothing else.

### B2. Hexagon and area aggregation of points
Build time: points are assigned to every level of the crosswalk and to an equal-area hexagon grid (H3 resolution 7 is about 1.8k cells and resolution 8 about 12k cells for the island; Apache-2.0 library, to be vetted for page weight before use). Browser time: a user-filtered point layer (for example one category of school) is re-binned client-side by a small square/hex binner, with the method shown ("points counted in each hexagon; hexagons are equal-area").

### B3. Shared controls, applied to every layer
- **Year control:** one control; each layer resolves its own period (section C3), and the legend says which period each layer shows.
- **Normalisation:** per 1,000 residents, per km², per resident, per housing unit, share, index (Puerto Rico = 100), change since base year, location quotient, percentile. Allowed options come from the contract (extensive versus intensive), as in the Economy tab today.
- **Classification:** natural breaks, quantile, equal interval, fixed breaks held across years (exists), plus user-entered breaks.
- **Reliability:** margins of error, small-number and suppression flags drawn as hatching or an icon in the legend, with the same caution text everywhere (workplace versus residence, survey noise, interpolation, "area patterns do not describe individuals").

### B4. Workbench additions
Keep: inspector, sortable table with CSV, scatter with correlation, trend. Add: a **correlation matrix** across any chosen variables (Pearson and Spearman, n shown, with the "pattern, not cause" note), **small multiples** (one map per year or per variable), **swipe or split-screen comparison** of two maps (two synchronised maps with a draggable divider), and a **table view for every map** (WCAG).

### B5. Area profiles
One page per area: `profile.html?area=72127` (municipio now; barrio, tract and block group when data exist). A section per domain is generated from the registry; each shows the domain's variables with latest value, margin of error, rank among peers, and trend. **Peers** are the 5 nearest municipios by standardised population and density (the method and the list are shown). The existing municipality tab becomes a compact view of the same component.

### B6. Composite index builder
Users choose variables from any domain; set direction (higher is better or worse), transformation (z-score, min-max or percentile rank) and weights. The result is a weighted mean of standardised values; an area needs at least 80% of the weight present or is left blank; contributions are shown per area. The method, inputs and weights are displayed next to the map and stored in the URL (`#ix=`). Every result is labelled **"User-built composite, not an official index."**

### B7. 2D and 3D
The 3D view's hard-coded 11 column metrics are replaced by the same engine (height from one series, colour from another); flood, protected land and transit stay as their 3D layers. Time bars stay as they are.

### B8. The contract that makes it automatic
A dataset that satisfies the data contract (section C1) appears in the catalog, the layer stack, the profiles, the dictionary and the chat with no UI change. The acceptance test for Phase 3: add a toy dataset in a new domain by editing only registry and data files, and see it everywhere.

## C. Data contract, geography and time

### C1. The data contract
One record per dataset, stored in `dictionary_src/datasets.json` (the file-level companion to the variable-level dictionary entries), validated by `build.py`. **The build fails on any violation.**

```json
{
  "id": "economy_series", "file": "economy_series.json",
  "domains": ["economy"], "geography": { "level": "municipio", "key": "geoid" },
  "time": { "type": "period", "unit": "calendar-year" },
  "sources": ["bls_qcew", "bls_laus", "acs5", "usaspending"],
  "licence_class": "open", "cadence": "annual", "published": "2026-10",
  "variables": "dictionary_src/entries (domain, unit, value_type, normalisations, moe)"
}
```

- **Required per dataset:** id, file, domain tags (primary first), geography level and join key, time type, sources (must exist in `sources.json`), licence class (`open`, `open-with-conditions`, `licensed-not-open`; the last blocks publication unless flagged and documented), cadence.
- **Required per variable (dictionary entry):** unit, value type, allowed normalisations, margin of error present or not, domains (default from the dataset), `where.files`.
- **Validated by the build:** ids unique; domains and sources exist; every join key resolves against the crosswalk, with the share of unmatched ids reported (fail above 1%); time type consistent with the years present; values finite and within declared bounds; margins of error shaped like values; file size within its budget (section E); no column or text matching a personal-data pattern (names, phone, email, address); and a dictionary entry for every variable (`dictionary.py --coverage` already does this).
- Python tests (pytest) cover the validator itself with small fixtures, so a change to the contract cannot silently weaken it.

### C2. Geography crosswalk with stable IDs
`site/data/geo/crosswalk.json` (one row per unit) and per-level boundary files:

| Level | Key | Parent | Boundary source | Count |
|---|---|---|---|---|
| island | `72` | none | derived | 1 |
| region | `reg-xx` | island | the Puerto Rico Tourism Company region list (tourism-defined: to be replaced or supplemented by a general planning region if one is found) | 7 |
| municipio | 5-digit GEOID | region | Census TIGER / cartographic | 78 |
| barrio | 10-digit county-subdivision GEOID | municipio | Census (already held) | 901 |
| tract | 11-digit GEOID | municipio | Census cartographic boundary file | confirmed in D |
| block group | 12-digit GEOID | tract | Census cartographic boundary file | confirmed in D |
| block | 15-digit GEOID | block group | needed only as weights; 36,570 populated blocks held without IDs | confirmed in D |

- Every unit has a stable id, Spanish and English display names (place names are the same), a normalised name, area in km², 2020 population and housing units (the weights), and a centroid.
- Barrios do not nest in tracts, so the crosswalk carries a **weights table** (barrio to tract by block population) rather than a parent link.
- The accent-stripping `norm()` string joins in six places are replaced by id joins. Name matching remains only for user input (search, chat).

### C3. Moving between levels
- **Aggregation** (finer to coarser, exact for counts): sum for counts, population-weighted mean for rates, recomputed from numerator and denominator when both are available (never average percentages).
- **Population-weighted areal interpolation** (barrio to tract, or any non-nested pair): block population as the weight; extensive variables are allocated by weight, intensive ones weighted-averaged.
- **Shown to users:** a "method" line on every transformed layer ("interpolated from tracts to barrios using 2020 block population"), the layer drawn with a pattern or tag, margins of error **not propagated** and flagged as such, and results never mixed with observed data without a label.

### C4. Study areas (mechanism only, no data added)
A user loads a GeoJSON polygon set in the browser (never uploaded). The twin validates it, asks for a name, description and source, stores it locally (IndexedDB) and in an exportable file, and summarises **every layer** inside each polygon: residents and housing units by block centroids (exact), area-weighted values from series, counts of points, and exposure to polygon layers. Results carry the same method and reliability labels. No study-area content is added by FPR.

### C5. Time model
Each dataset declares one time type; the year control treats it accordingly:

| Time type | Examples | What the year control does |
|---|---|---|
| `point` | census 2010, 2020; a dated snapshot | shown when the chosen year is within its tolerance, otherwise nearest earlier with the date shown |
| `period` | calendar or fiscal year (QCEW, USAspending) | exact year, else latest at or before (flagged) |
| `window` | ACS 5-year | the window ending at or before the year; label shows the window (2020-2024) |
| `vintage` | population estimates | the latest vintage for each year, with the break noted (2020) |
| `snapshot` | transit, places, flood | always current, labelled with its date; not animated |
| `event` | storms, declarations | filtered to the year, counted or listed |
| `static` | boundaries, land use plan | always shown |

Every legend states, per layer, which period it shows. This extends the nearest-year rule already in the Economy tab.

## D. Domain build-out (data)

### D0. How this was checked, and its limits

Six research agents tested sources with live requests on **2026-10-05** (one each for education, health, infrastructure, environment, tract-level Census data and candidate new domains). Each reported facts as "verified by request" or "documentation only". **I have not repeated their requests**; I read their reports and checked them against the repository. Sources change (the island zoning service answered 502 and then 500 during the session, and the FCC and CDC removed or restricted several files in 2025), so every item must be re-tested when it is built. The research transfers exceeded the 200 MB cap I set (about 0.5 GB for new domains, 250 MB for health, 175 MB for tracts, mostly national files downloaded to prove Puerto Rico is absent). Nothing large was kept and nothing in the repository was changed.

Verdicts: **PASS** (keyless, Puerto Rico covered, usable), **PARTIAL** (what is missing is stated), **FAIL** (and why).

### D1. Enablers that unlock most of the rest (verified by the tract researcher)

1. **Census small-area ACS is keyless.** For 2020-2024 the table-based files hold Puerto Rico rows for **981 tracts and 2,555 block groups with margins of error**, and for **939 county subdivisions (901 are the twin's barrios, matching IDs exactly)**. Files are sorted by `GEO_ID` and the server supports byte ranges, so a reader that binary-searches the file pulls only Puerto Rico rows: about 0.3 MB per table and level, about 6 MB for 25 tables per vintage. (The current reader stops after the municipio rows and cannot reach these; a naive full-file read costs 17-200 MB per table.) Older vintages exist in a different folder; 2010-2019 use 2010 tracts (945) and block groups (2,594), 2020-2024 use 2020 geography, so **no crosswalk is needed within 2020-2024** and the geography break must be shown between vintages.
2. **Barrios do not nest in tracts** (57% of barrios, holding 83% of residents, span two or more). So barrio statistics should come from the Census's **own barrio rows**, not from tract allocation. Tract-only products (resilience estimates) reach barrios only through block-weighted allocation, labelled as interpolated.
3. **Block IDs are recoverable.** All 36,570 populated blocks in `population_blocks.json` match a Census block uniquely on coordinates and population (0 ambiguous, 0 missing). `network.py` already fetches the 15-digit GEOID and keeps only 5 digits. The 2020 PL 94-171 file (15 MB) and TIGERweb give population and **housing units (exact; block population is noise-injected, so housing units are the better weight)**. Counts to carry in the crosswalk: 981 tracts, 2,555 block groups, 41,987 blocks (36,570 with residents), 939 county subdivisions.
4. **Boundaries:** cartographic files `cb_2020_72_tract_500k` (0.6 MB) and `cb_2020_72_bg_500k` (1.0 MB) are free with attribution but "should not be used for geographic analysis including area or perimeter calculation": use them for display only and the TIGER/Line files (3.4 MB and 5.5 MB) for any area math. Simplified GeoJSON is 0.27 MB (tracts) and 0.45 MB (block groups) compressed.
5. **Storage:** 20 variables x 5 years, with margins: tracts 0.39 MB, block groups 0.94 MB, barrios about 0.35 MB compressed (estimate, plus or minus 15%).
6. **Small-area cautions every user must see:** 90% margins everywhere; 45% of block groups have no median rent; poverty, Gini and income by tenure exist only at tract level; cost burden is not usable below municipio (median margin 21-37 points); adjacent windows share four of five years; medians and rates cannot be summed; null codes mean "not computable", not zero. Recommended first wave: population, housing units, households, owner share, vacancy, other-vacant share, household size, overcrowding, median home value, per capita income. Second wave (tract, margin shown): median income, unemployment, bachelor's degree, vehicles, internet, poverty.
7. **No keyless workplace data below the municipio.** LEHD LODES for Puerto Rico is empty; County Business Patterns is municipio-only; ZIP Business Patterns has no Puerto Rico ZIPs. Sub-municipal economy has to come from residence-based ACS tables.

### D2. Education (today: empty; becomes strong)

| Candidate | Verdict | Evidence (PR) | Geography, years | Notes |
|---|---|---|---|---|
| NCES Common Core of Data school directory | **PASS** | 865 PR rows in 2024-25 (855 open, 3 closed) | School ID (`NCESSCH`); annual 1986-87 to 2025-26 | Public domain site text; no coordinates in the CSV, join to EDGE; resolve file names through NCES's index |
| NCES EDGE school locations | **PASS** | 865 schools, 0 null coordinates; 426 of 901 barrios hold one | Point; one layer per year (1,329 schools in 2016-17 down to 847 in 2019-20, 865 in 2024-25) | Gives closures by year without island data |
| Urban Institute Education Data Portal API (CCD mirror) | **PASS** (attribution, ODC-By 1.0) | Enrolment by school 1995-2024: 627,620 (1995), 346,096 (2017), 235,819 (2024); 277 schools with enrolment in 2017 had none in 2018 | School, year | Third-party mirror of NCES; lunch eligibility, teachers |
| ACS education tables (B15003, B15002, B01001, B14002, B14001, B09001) | **PASS** | block groups for attainment and age; tract only for enrolment by level (B14001, B09001) | Tract, block group; 5-year windows | Same reader as D1 |
| IPEDS (postsecondary) | **PASS** | 129 PR institutions; fall enrolment 270,914 (2010), 167,883 (2023) | Campus, annual | Drop administrator names and phones |
| E-Rate (USAC open data) | **PASS** (public domain) | 1,269 school entities incl. private, 406 libraries | Entity point, 2016-2026 | Covers private schools NCES lacks; avoid the Form 470 sibling (contact names) |
| Head Start service locations | **PARTIAL** | 852 PR sites, 21,907 funded slots | Point; daily snapshot, no history | Licence not stated (ask OHS); archive snapshots to make a series |
| College Scorecard bulk | **PARTIAL** | 143 PR institutions | Campus; snapshot | Licence not stated; many fields suppressed |
| Civil Rights Data Collection | **PARTIAL** (low value) | 841 PR schools | School; biennial | Internet items all "not reported" |
| Island portals (datos.pr.gov, Instituto, Busca tu Escuela) and child-care licences | **FAIL today** | portals in maintenance or token-gated; no child-care file | | Re-test weekly; request lists from the Department of Education and ACUDEN |

### D3. Health (today: empty; becomes strong)

| Candidate | Verdict | Evidence (PR) | Notes |
|---|---|---|---|
| CMS hospital list and other facility lists | **PASS** | 59 hospitals (54 with ER); dialysis 50, nursing homes 9, home health 39, hospice 42 | Municipio, no coordinates for most: match to OSM/Overture by name and check by hand (Census geocoder matched 13 of 59) |
| HRSA health center sites | **PASS** | 169 active sites with coordinates; refreshed daily; "no usage limitations" | Drop official-name columns |
| HRSA HPSA and MUA/P | **PARTIAL** | HPSA designated: primary care 43, dental 100, mental health 75; MUA 72 designations, 6 municipios missing | Municipio only; component names double-encoded |
| HRSA Area Health Resources File 2024-25 | **PASS** | 78 rows, physicians, beds, births; mortality empty for PR | Annual editions back to 1999 |
| Medicare monthly enrollment (CMS) | **PASS** | PR county rows from 2013, by age and disability | Municipio |
| CDC SVI 2022 (tract) | **PASS** | 939 tracts, 158 columns; editions 2014-2022 | Ranks are within Puerto Rico only |
| ACS health tables (B27010 coverage, B01001 age; B27001, B18101 disability tract only) | **PASS** | block groups for age and coverage-by-type; tract for insurance and disability | Same reader; margins wide |
| PR Department of Health Biostatistics API | **PARTIAL** | keyless JSON, 39 paths: entities, surveillance series, row-level case files | Terms bar republishing without written consent; person-level rows exist: only aggregates, and only with consent |
| CDC PLACES, CDC Environmental Justice Index, HIFLD hospitals, Instituto vital statistics | **FAIL** | PLACES and EJI exclude Puerto Rico; HIFLD retired Aug 2025; Instituto portal fails TLS and the annual report stops at 2020 (PDF) | Record why in `wanted.json` so the chat can explain the gap |
| OpenStreetMap health features | **PARTIAL** | hospitals 89-94, pharmacies 340 | Fallback for coordinates; ODbL |

**Derived (in-house):** travel time and distance from the 36,570 populated blocks to the nearest ER and health center, by municipio and tract, on the twin's own road graph. Labelled as a computed estimate.

### D4. Infrastructure (today: strong for transit only)

| Candidate | Verdict | Evidence (PR) | Notes |
|---|---|---|---|
| Water: EPA ECHO drinking water systems | **PASS** | 402 active community systems serve 3.29 M people; 248 with a current violation flag | A compliance record, not proof water is unsafe; aggregate small private operators |
| Wastewater: EPA ECHO NPDES | **PASS** | 179 active permits with coordinates | |
| Power: EIA-860M generators | **PASS** | 228 generators, 67 plants, 6,474 MW, by municipio | Owner contact columns: drop |
| Power: grid assets (PRITS geoserver: substations, lines) | **PARTIAL** | 961 substations, 44,713 line segments (2014); no licence stated | HTTP only; runner access untested |
| Power: EAGLE-I outages (ORNL, CC BY 4.0) | **PARTIAL** | PR reported as six LUMA regions (about 1.5 M customers), not 78 municipios | Label as regional |
| Power: LUMA outage map and API | **FAIL** | Terms bar automated access without written permission | Not harvested; ask LUMA and the Energy Bureau in writing |
| Bridges (FHWA National Bridge Inventory) | **PASS** | 2,434 bridges; 14% poor; 1992-2025 | Format changes to SNBI in 2026 |
| Dams (USACE NID) | **PASS** | 36 dams, 12 poor or unsatisfactory | |
| Airports, heliports, ferries (BTS NTAD, **new host**) | **PASS** | 44 sites (15 airports, 10 public use); the host the build uses (`geo.dot.gov`) no longer answers | **Fix `transport.py` `FAA_URL` now**; new field names listed in the infrastructure report |
| Road condition and traffic (FHWA HPMS) | **PASS** (aggregates) | 180,776 PR segments, 2024 | About 90 calls; publish municipio aggregates |
| Hurricane shelters (PRITS geoserver) | **PASS** | 354 points (2023) | No capacity field; no licence stated |
| Fire stations (USGS), police stations (OSM) | **PARTIAL** | 94 fire/EMS; OSM 77 fire, 144 police | The PR geoserver police layer holds officer names and phones: never publish |
| Antenna towers (FCC ASR), landfills (EPA LMOP) | **PASS / PARTIAL** | 764 constructed towers; 32 landfills | Tower contacts: drop |
| Broadband beyond ACS | **FAIL** | FCC map 403, API 401; Form 477 stops June 2021 and overstates availability; ACS internet (B28002) at tract and block group works | Use ACS plus a clearly labelled 2021 legacy series |
| PRASA interruptions | **FAIL** | page 404; no open dataset | Ask PRASA |

### D5. Environment (today: partial; becomes strong)

| Candidate | Verdict | Evidence (PR) | Notes |
|---|---|---|---|
| **Florida flood polygon** | **Resolved: not a gap** | FEMA maps Florida entirely as minimal hazard (zone X, panels effective 2005-2009) | Record "mapped, minimal hazard" in metadata |
| FEMA National Risk Index (tract and municipio) | **PARTIAL** | 939 tracts, 78 municipios; expected annual loss $3.19 B a year (hurricane 1.48 B, earthquake 0.80 B, inland flood 0.31 B, landslide 0.29 B); version December 2025 | **Composite score, social vulnerability and resilience are empty for Puerto Rico**: say so on the page |
| Census Community Resilience Estimates 2024 | **PASS** | tract (981) and municipio, with margins; 2019, 2021-2024 | Fills the NRI gap; heat version has null values (fail) |
| CDC SVI 2022 | **PASS** | 939 tracts | See D3 |
| NHC storm surge (SLOSH, categories 1-5) | **PASS** at municipio level | 7.3 MB rasters, 2018; inundated land 100 km2 (Cat 1) to 369 km2 (Cat 5) | NHC: general awareness, not parcel level; housing-unit exposure through block counts |
| Landslide inventory after Hurricane María (UPRM mirror of USGS) | **PASS** (mirror caveat) | 71,431 points with municipio and barrio | Barrio names have typos: count by point in polygon |
| USGS landslide susceptibility raster | **PARTIAL** | 5 m raster, 290 MB zip | One-time job: percent area at high index per municipio |
| Zoning (Calificación) | **PARTIAL to PASS** | reachable on two other hosts: 1.49 M parcels (current service) and a September 2024 snapshot (1.44 M) | Harvest server-side summaries by municipio and class; no licence stated; the plan in force is still the 2015 PUT |
| NWI wetlands (USFWS FeatureServer) | **PASS** | 18,474 polygons, 1,345 mangrove-type | Official zip blocks scripts; use the service |
| Tree canopy (MRLC) 2011-2021, C-CAP land cover 2010 | **PASS** snapshots | canopy 91% to 87% in El Yunque | No land-cover change for PR |
| Tide gauges (13), USGS streamgages (new API, 7,318 locations), NOAA Atlas 14 rainfall, ComCat earthquakes (12,507 events in the 2019-20 sequence), GHCN stations (285) | **PASS** | | Earthquakes: magnitude 2.5 or more, paged by year |
| HURDAT2 through 2025 | **PASS** | NHC file dated 2026-09-23 | Refresh the existing file now |
| Heat: CDC tracker, Census LACE | **FAIL** | rate-limited; no PR rows | GHCN stations and CRE only |
| Air quality (EPA AirData) | **PARTIAL** | 8 of 78 municipios | AirNow and AQS APIs need keys |

### D6. Housing, Economy and Population extensions

- **Housing and Economy to tract, block group and barrio:** the D1 waves. These give the first sub-municipal view of rent, value, vacancy, income and education.
- **Population and households (new domain, justified now):**
  - Census population estimates by single year of age and sex, 2010-2025, municipio (**PASS**).
  - ACS tables B01001, B02001, B03002, B11001, B18101, B21001 at municipio, barrio, tract (**PASS**, heavy national files; use the range reader).
  - Puerto Rico-only migration and nativity tables (B07003PR, B07001PR, B05005PR, B05006PR) (**PASS**), and state-to-state migration with wide margins (**PASS**, state level).
  - 2020 DHC block file (**PASS**, 137 MB).
  - **No keyless data** for births and deaths by municipio (island total only; the annual report is a PDF to 2020), language at home, or ancestry. The domain would still be strong without them.

### D7. Candidate further domains (justified only where real data exist)

| Candidate domain | Verdict now | First harvestable data | Blocked or empty |
|---|---|---|---|
| **Public safety** | Defer; fold what exists into `infrastructure.mobility` and `infrastructure` | Fatal crashes (NHTSA FARS: 275 crashes in 2024, municipio from 2020, counts only); police and fire stations from OSM and USGS | The police incident feed answers without a token but holds 986,211 incident points with addresses and free text, and no terms: **not harvested**. FBI Crime Data Explorer needs a key. Ask the Police for an aggregated extract and a licence. |
| **Governance and public finance** | Small form possible, mostly blocked | Comptroller contract registry by entity and municipio, FY2012-13 to FY2022-23 (stale since; contractor names are personal data: aggregates only; no licence) | Census of Governments excludes Puerto Rico; Oversight Board plans are PDFs "as is"; official election results block scripts; the ABRE municipal index is a one-year, unlicensed file with mayors' names. Permissions needed before any of it. |
| **Agriculture and food** | Not yet a domain | Prime-farmland soils by municipio (NRCS, keyless); island nutrition-assistance series (monthly, island only) | The 2022 Census of Agriculture is island and 6 regions only in PDF; QuickStats needs a key; the food-access atlas excludes Puerto Rico |
| **Culture and heritage** | Not a domain; extend the visitor-economy module and land use | National Register of Historic Places (360 points; join on city, not county); library locations (40, without usage) | |

### D8. Sources that failed the licence or access check (for `wanted.json`, so the chat can say why)

Census Data API (key), datos.pr.gov and data.pr.gov (maintenance, 404), Instituto de Estadísticas portal (TLS chain, outages), FBI Crime Data Explorer API (key), Puerto Rico Police feeds (token, personal data, no terms), HIFLD Open (retired), CEE official results (bot block), ERS Food Access Atlas (no Puerto Rico), NASS QuickStats (key), Census of Governments (no Puerto Rico), IMLS museum files (retired), CDC PLACES and Environmental Justice Index (no Puerto Rico), CDC Heat tracker (rate limited), LACE (no Puerto Rico), FCC broadband map (403) and API (401), LUMA outage data (terms forbid automation), PRASA interruptions (none), EPA AirNow/AQS APIs (key), ZIP Business Patterns and LODES (no Puerto Rico data), Oversight Board plans (PDF only, "as is").

### D9. Personal-data flags found (none to be published)

Comptroller contract registry (contractor names), police incident feed (addresses, narratives), ABRE (mayor names), HRSA files (officials' names), Department of Health entity and case files (provider names, person-level cases), IPEDS administrators and phones, FCC tower contacts, EIA generator owner contacts, the island geoserver police layer (officer names and phones), FARS person file (exact date, time and place of a death can identify someone: counts by municipio and year only). The contract validator (C1) will reject these columns.

### D10. `wanted.json` changes (applied in Phase 3, step 1)

Add a `domain` field to every row and move each row's status from the research: `schools`, `hpsa`, `nri`, `earthquakes`, `landslide`, `tides`, `streamflow`, `landcover`, `water`, `crashes`, `traffic`, `agcensus`, `municipal-finance` to **checked** (with the corrected source and notes); `hurricanes` to **live** (tracks; add the 2025 file); `power` to **blocked** (LUMA) with new **checked** rows for plants, grid assets and regional outages; `broadband` stays **blocked** with a checked ACS row; new **checked** rows for storm surge, zoning, wetlands, resilience estimates, social vulnerability, colleges, ACS education and health, E-Rate, Head Start (licence to confirm), health facilities, AHRF, Medicare enrolment, bridges, dams, shelters, fire stations, towers, landfills, population estimates, ACS demographics, PR migration tables; new **blocked** rows for the failures in D8, each with its reason and who to contact (Police, CEE, ABRE, Comptroller, LUMA and the Energy Bureau, PRASA, Department of Health, Instituto de Estadísticas, Head Start office).


## E. Scale and performance

**Verified today:** GitHub Pages serves byte ranges (HTTP 206 with `Accept-Ranges`) and gzip, with `Access-Control-Allow-Origin: *` and `max-age=600`. That is what PMTiles and Parquet over HTTP need, so large layers do not require a separate host yet.

| Library (npm) | Licence | Size note | Use |
|---|---|---|---|
| `pmtiles` | BSD-3-Clause | 380 KB unpacked | Vector tiles from one file by range requests |
| `hyparquet` | MIT | 288 KB unpacked | Light Parquet reader for column reads in the browser |
| `@duckdb/duckdb-wasm` | MIT | engine is several MB (149 MB unpacked package) | SQL over Parquet; load lazily, only in an "advanced analysis" panel |
| `h3-js` | Apache-2.0 | about 7.7 MB unpacked package (the browser build is much smaller; measure before adopting) | hexagon grid |
| `apache-arrow` | Apache-2.0 | 5.8 MB unpacked | only if DuckDB-WASM is adopted |

Plan (no change until approved):
1. **Page-weight budget** per route, enforced by a script in the build: landing view at most 250 KB compressed of data plus 250 KB of scripts; each domain's summaries loaded only when the domain is opened; each large layer behind its toggle. The first load drops from 3.0 MB to roughly 0.4 MB compressed by not loading the 16.7 MB places file until the visitor-economy module is switched on.
2. **Tiers:** small summaries and series stay JSON (tens of KB per domain). Large geometry and points move to **PMTiles** when a layer passes about 5 MB compressed (places, land use, flood are the first). Tract and block-group series move to **Parquet** read by `hyparquet` for single-column pulls, with DuckDB-WASM only for the optional advanced panel.
3. **Lazy by domain and layer:** the registry declares each dataset's file, size and tier; the UI fetches on first use and caches. The map never needs `places.json` for the landing view.
4. **Tracking:** `registry.py` already lists every file and its share of the limit. It will also record tier, compressed size and the route(s) that load it, and fail the build when a route exceeds its budget.
5. **Measuring on a throttled mobile connection:** each change reports (a) compressed bytes per route, from the build script, and (b) a Lighthouse run with the Slow 4G profile, run locally if Chrome and Node are available. I will say which of the two I could run; I will not estimate a load time and call it measured. Baseline from the audit: map first load 3.0 MB compressed (estimate 16-20 s of transfer on Slow 4G).
6. **Growth guard:** at 60% of the 1 GB Pages limit, or any file above 50 MB, move that file to object storage (Azure Blob or similar, FPR's decision) with the same range-request access.

## F. Scenarios

Generalise the route planner's scoring into a **scenario workspace**.

- **A scenario** = `{ id, name, created, author-label, layer stack and settings, geometries (routes, facility points, polygons), inputs, outputs, notes, labels }` stored locally (IndexedDB) and exportable as one JSON file; the layer-state URL part is shareable.
- **Compare two scenarios** side by side with a difference table (every output metric: A, B, B minus A, percent) and a difference map for any series both define. Export GeoJSON and CSV.
- **Scoring generalised:** the planner's metrics (residents reached, places reached, no-service residents, overlap, exposure, municipios crossed) become instances of "metrics a scenario can compute": any point, line or polygon set scored against any series by the engine's exposure and aggregation adapters.
- **External model outputs:** a documented input format, validated on load. CSV or GeoJSON with: `geography_key`, `geography_level`, `period`, `variable`, `value`, `unit`, optional `lower`/`upper`, plus a header record with `model_name`, `model_version`, `run_id`, `date`, `assumptions_url`, `licence`, `contact_label`. It loads as a layer labelled **"Model output (not observed data)"** with those fields shown. FPR provides no model results; the format and a sample file with obviously fake values, labelled as such, ship with the documentation.

## G. "Ask the twin"

- **Lexicon from the registry, not code.** Concept rules (today 68 hand-written regexes) are generated from each variable's name, plain description, glossary terms and domain names, in Spanish and English, plus curated synonyms stored next to the dictionary entry (`aliases`). A new dataset is askable the day it is registered.
- **Cross-domain by construction.** The tools (`rank`, `correlate`, `trend`, `search_datasets`, and new `profile`, `compare_areas`, `exposure`, `composite`) all call the engine, so "Is rent higher where income is higher?" or "What share of residents live in a flood zone, by municipio?" work for any pair that shares a geography. When two variables are at different levels or periods the answer says which level and period it used, or declines and says why.
- **Same rules:** every sentence is computed from the data; it states year, unit and source (a dictionary link); it reports patterns, not causes; it shows margins of error and small-number caution when they apply; it says "no data" for empty domains and offers to add the request to the wishlist. Spanish first when the user's language is mixed.
- A model-assisted version stays optional and unbuilt (needs a hosted proxy; unchanged from the earlier decision).

## H. Placement guide (outline of `docs/adding-data.md`, written in Phase 3 step 1)

**Does a new dataset fit an existing domain?** Ask in order: (1) What is the thing being measured about (people, homes, schools, hospitals, jobs, roads, land, risk)? Pick the domain whose `description` covers that subject. (2) If it spans two, the subject picks the primary and the other becomes secondary (school flood exposure: primary education, secondary environment.hazards). (3) If the subject has no home, or the dataset would be the first of at least three coherent datasets with their own users, **create a domain**: add one object to `dictionary_src/domains.json` (id, bilingual name and description, icon, accent token, order, headline, examples). (4) If it is a sub-theme of an existing domain with a different audience (visitor economy, public money, hazards), add a sub-domain. (5) Do not create a domain for a single dataset; tag it and put it in `wanted.json` until siblings exist.

**Checklist to add a dataset end to end:** source check (keyless, licence class, terms, PII, cadence, Puerto Rico rows, evidence saved); pipeline script in the repository's style with caching; output file under `site/data/` in the registry layout and size tier; geography level and key resolved against the crosswalk; time type; dataset record in `dictionary_src/datasets.json`; dictionary entries for every variable with domains, unit, normalisations, margins, cautions, sources; `sources.json` record with credit line; `wanted.json` row moved to `live`; `python build.py` (contract validator passes); `python dictionary.py --coverage` and `--links`; `python registry.py` and the page-weight budget; chat aliases checked (the question "show X" finds it); tests (validator fixture, a sample query); a screenshot or note of the dataset in the catalog, layer stack and profile; HANDOFF and the findings file updated.

## I. Rules from the repository, and how each is kept

- **No keys, open data only, licence recorded:** the contract's `licence_class` and `sources` checks fail the build otherwise.
- **Dictionary and registry first:** every item below ends with `dictionary.py --coverage`, `--links` and `registry.py`.
- **No personal or contact data; aggregated only:** a PII scan in the contract validator, plus the existing build-time removal of contact fields. Anything found is flagged, not displayed.
- **Label what things are:** schedules, estimates, proxies, interpolated values, composites, scenarios and model outputs carry a visible label and a legend tag; none is ever drawn as observed.
- **Analytical cautions shown to users:** margins of error, small numbers, workplace versus residence, interpolation and "area patterns do not describe individuals" are attached to variables and layers in the registry and shown by the shared legend and popup.
- **No fabricated data:** anything that needs data not in the repository goes to `wanted.json` with source, licence, cadence and proposed domain (the file gains the domain field).
- **Existing features keep working** (visitor economy, transit tools, Housing page, 3D); view state stays in the URL; nothing is removed or restructured without asking.
- **Design and language:** Spanish first, plain language; FPR tokens only, with data palettes documented in `docs/palettes.md` (ColorBrewer-derived sequential and diverging schemes marked colour-blind safe; the bivariate grid generated from two such ramps; all run through a colour-vision simulation in a script, results recorded); one legend, popup and panel component for all domains; WCAG 2.1 AA with a table view for every map and chart.

## J. Ranked plan

Order by what unblocks the most, then by value per effort. Value: **H**igh, **M**edium, **L**ow. Dependencies refer to item numbers. Size impact is compressed bytes added to the first load of the route that uses it (the landing view stays at about 0.4 MB after item 3).

| # | Item | Value | Effort | Depends on | Main files affected | Data and licence checks | Size impact |
|---|---|---|---|---|---|---|---|
| 0 | **Quick fixes, independent**: airports host fix (`transport.py`), HURDAT2 2025 refresh, `wanted.json` status updates, store Florida "minimal hazard" note | M | S | none | `transport.py`, `timeseries.py`, `wanted.json` | Re-test URLs the day they are built | none |
| 1 | **Domain registry, dataset contract, tagging of the 594 items, build validator, placement guide** (A1, A2, C1, H) | H | L | none | `dictionary_src/*`, `dictionary.py`, `build.py`, `registry.py`, `docs/` | Contract enforces licence class and PII scan | +0.1 MB catalog |
| 2 | **Spanish-first string layer** (names and descriptions in the registry; UI strings extracted; language from browser and URL) | H | L | 1 | all `site/js`, `site/*.html`, dictionary text for the registry and About | none | +about 0.05 MB per language |
| 3 (built 2026-10-06, local) | **Repositioning and neutral landing**: new text (A5), overview from the registry, lazy visitor-economy module, catalog tab and dictionary filters (A3, A4) | H | M | 1, 2 | `index.html`, `app.js`, `3d.html`, `housing.html`, README, SHARE.md | none | **first load 3.0 MB to about 0.4 MB** |
| 4 (built 2026-10-06) | **Geography crosswalk and Census small-area base**: crosswalk file, block IDs and housing units, tract and block-group boundaries, range-based ACS reader incl. barrio rows (C2, C3, D1) | H | L | 1 | new `geo.py` / `acs_small.py`, `network.py` (keep block GEOID), `housing_series.py`, `site/data/geo/*` | Census terms (display-only cartographic files); cautions in D1 | +0.7 MB boundaries (lazy) |
| 5 (built 2026-10-06: flood, sea level rise, protected land and transit stops; storm surge, schools, hospitals and shelters wait for data, see docs/exposure.md) | **Cross-domain exposure series** (residents and housing units by municipio, barrio and tract inside flood, sea level rise, storm surge, protected land, within 400 m of transit, near a school, hospital or shelter) from blocks and existing layers | **H** (the first real cross-domain results from data we already hold) | M | 4 | build scripts; no UI | Method label: block internal points, 2020 weights; labelled as computed | +0.1-0.3 MB |
| 6 | **(built 2026-10-06; see HANDOFF.md and docs/engine.md) Shared core modules and the layer engine v1** (adapters for series, snapshot fields, point aggregates; one legend, popup and panel; year control with time types; shared normalisation and classification; hexagon and area aggregation) (B1-B3, C5) | H | XL | 1, 2, 4 | new `site/js/core/*`, `economy.js`, `app.js`, `housing.js`, `twin3d.js` | Palette documentation and colour-vision test | scripts about -0.1 MB by removing duplication |
| 7 | **(built 2026-10-06; see HANDOFF.md and docs/small-area.md) Data wave A: Census small-area** (Housing, Economy, Population to tract, block group and barrio; first and second waves in D1; Population domain created) (D1, D6) | H | L | 4, 6 | `housing_series.py`, `economy_series.py`, new series files | Margins shown, nulls not zero, no cost burden below municipio | +0.4-1.0 MB lazy per level |
| 8 | **Data wave B: Education** (D2) | H | M | 4, 6 | new `education_series.py` | ODC-By for the Urban mirror; Head Start licence to confirm | +0.3 MB |
| 9 | **Data wave C: Health** (D3), including travel time to care | H | L | 4, 5, 6 | new `health_series.py` | Consent needed for any Department of Health data; PII drops | +0.3 MB |
| 10 | **Data wave D: Infrastructure** (water, power, bridges, dams, shelters, fire stations, airports, broadband via ACS) (D4) | H | L | 4, 6 | new `infrastructure_series.py`, `transport.py` | LUMA not harvested; PRITS geoserver terms; regional outages labelled | +0.5 MB |
| 11 | **Data wave E: Environment** (risk and resilience bundle, storm surge, zoning, landslide, wetlands, canopy, gauges, earthquakes) (D5) | H | L | 4, 5 | `landuse.py`, new environment scripts | NHC surge use limits; zoning licence unstated; NRI gaps shown | +0.5 MB, zoning summaries small |
| 12 | **Workbench, profiles, composite builder** (B4-B6): correlation matrix, small multiples, swipe compare, area profile pages, composite index | H | XL | 6, at least two data waves | new `profile.html`, `core/*` | Composite labelling; interpolation labels | +0.2 MB scripts, lazy |
| 13 | **Scale tiers** (E): PMTiles for places, land use, flood; Parquet for tract series; page-weight budget in the build; Lighthouse run | M now, H as data grow | M | 3 (budget), 7 (tract series) | `registry.py`, build | Library licences (BSD-3, MIT, Apache-2.0) | lowers first load |
| 14 | **"Ask the twin" on the registry** (G): generated lexicon, cross-domain tools, empty-domain answers | H | M | 1, 6 | `chat.js` | none | small |
| 15 | **Scenario workspace** (F) | M | L-XL | 6, 12 | `plan.js`, new `core/scenario` | Model-output format; labelled | small, lazy |
| 16 | **3D on the engine; study areas** (B7, C4) | M | L | 6 | `twin3d.js`, new `core/study` | Local-only processing | small |
| 17 | **Outreach for blocked data** (Police extract, CEE, ABRE, Comptroller, LUMA and Energy Bureau, PRASA, Department of Health, Instituto, Head Start office) | M | S (drafts) | none | `OUTREACH_*.md` | Written permissions before any harvest | none |

**Where I depart from the order you suggested, and why:**
- **i18n sits right after the registry (item 2)**, not later, because the registry carries Spanish and English names and every later screen is built once in both languages. Retrofitting costs more.
- **The exposure series (item 5) is new.** It uses only data already in the repository (flood, sea level rise, protected land, transit, blocks) plus block IDs, and produces the first genuine cross-domain results (residents in flood zones, by municipio and barrio) before any new data wave.
- **The scale budget (part of 13) is partly pulled into item 3**, because a neutral landing view is only fast if the 16.7 MB places file stops loading at start. The PMTiles and Parquet tiers follow when tract series arrive.
- **Data waves (7-11) start only after the engine v1 exists (6)** so each wave is tested through the real catalog, layer stack and profile, but item 4 (crosswalk) and item 5 can run in parallel with item 3.

**Risks and what I will watch:** (1) Item 6 touches every page; I will migrate page by page behind the existing behaviour and keep every current feature working, checked by a feature list before and after. (2) Small-area estimates are noisy and easy to over-read; the engine will refuse some normalisations and always show margins. (3) External sources break without notice; each build records the date and the evidence and degrades by keeping the last good file. (4) Federal grant, recovery and licensed-data content needs Finance and Compliance review before external communication; the contract's `licence_class` makes that visible per dataset. (5) Page weight: every change reports compressed bytes per route, and Lighthouse timings only if I can run them.

## K. Decisions needed before Phase 3

1. **Approve or reorder the plan in J** (my departures are listed above). If you want only some items, name them; I will do them one at a time as agreed.
2. **Start point:** I recommend items 0 and 1 first (they change no screens), then 2 and 3.
3. **Public safety and governance** stay "planned, mostly blocked" and are not created as domains yet. Agree?
4. **Outreach:** may I draft the written requests in item 17 (for you to send)? I will not contact anyone.
5. **Measuring load time:** is Chrome with Node/Lighthouse available on the machine I run in? If not, I will report compressed bytes and label any time as an estimate.
6. **`dictionary.html` and the Economy tab** are public today. Keep as is while Phase 3 starts?

## L. Addendum, 2026-10-05: tourism places and transport access (proposed, awaiting approval)

During Phase 3 you asked how to connect tourism places to transport options. The method, the numbers and the timing are in [`visitor-transport-access-2026-10.md`](visitor-transport-access-2026-10.md); the evidence is in `docs/analysis/visitor-access-2026-10/`.
It adds one proposed item and places the rest inside items already in the plan:

| # | Item | Value | Effort | Depends on | Notes |
|---|---|---|---|---|---|
| **2b** (built 2026-10-06, committed locally) | **Access of tourism places to transport, first layers**: rebuild the stale place fields, relabel "near transit" as "near any mapped stop", add `ts_m`, `ts_calls`, `ts_we` and area shares, per-stop feed state and weekend calls | H | M | 1 | Corrects a published number (47.0% against 32.1% with a current timetable). Goes after item 2 and before item 3. Fields in a separate typed-column file (+66 KB gzip). |
| 5 (extended) | Walking distance (`tw_m`) and residents' access with the same corrected stop sets | | S–M added | 4 | One definition of "current scheduled stop" for places and residents. |
| 6 / 12 (extended) | Gateways file, hub distances in the browser, access-class legend and popup profile | | M added | 6 | Built once on the engine. |
| 10 (extended) | Weights for gateways: airport, ferry, cruise and park visits | | M added | 4, 6 | The 21 candidates are rows in `wanted.json`; licences to confirm first. |
| Later | Journey times from gateways (San Juan metro first) | M | L | 12, data repairs | Waits for the expired feeds to be renewed and the untimed calls to be written. |

Decision for K: approve item 2b as the next item after item 2?
