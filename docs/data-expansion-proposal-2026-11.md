# Proposal: more dimensions for the observatory (new sources, and layers computed from data it already holds)

Date: 2026-11-14. Status: **approved by the project lead on 2026-11-14 ("Approve, start step 1"): decision 107 (a) to (h) as proposed. Step 1 is being built on branch `data/people-movement`.** This pull request changes no page and publishes no data. It adds this document and 27 rows to the wanted-data list (`site/data/wanted.json`), and moves one row (`fdic`) from candidate to checked.

**In one paragraph.** On 2026-11-14 the project lead asked what data the observatory could add, as map layers and in the catalogue, to support multidimensional analysis of Puerto Rico. They then asked for layers that do not exist yet but can be computed from data the observatory already holds, "like in algebra when you get the value of X based on the other variables". This proposal answers both. Track A adds sources: seven were tested that day and returned Puerto Rico rows with no key, and ten are still to confirm. Track B adds nine computed layers that need no new source. The observatory has room: it holds 140 MB of data against a limit of 1,000 MB (13%).

## What the observatory holds today (main, 2026-11-14)

- 132 data files, 1,080 dictionary entries and 113 sources.
- The wanted-data list had 137 rows: 46 live, 48 tested but not built, 15 untested and 28 blocked.

| Domain | Entries | Domain | Entries |
|---|---|---|---|
| Mobility and transit | 187 | Infrastructure | 39 |
| Visitor economy | 120 | Population and households | 39 |
| Economy | 111 | Health | 32 |
| Housing | 80 | Communities | 28 |
| Land and protected areas | 73 | Environment and climate | 26 |
| Hazards | 56 | Education | 13 |
| Public money | 48 | Energy | 12 |

Two limits cut across the domains:

- **Time.** 90 of the 132 files are one snapshot. Only 30 carry a series over time.
- **Detail below municipio.** Most figures stop at the municipio. Below it, nearly everything comes from the Census survey (ACS), plus hazards, heat, buildings and broadband.

## Where it is thin

| Dimension | The observatory has | It lacks |
|---|---|---|
| Credit and capital | Opportunity Zones, public money | Home loans, bank branches, deposits |
| Demographic change | Population and age | Race and ethnicity, language, migration, births and deaths |
| Health | Facilities, shortage areas, Medicare enrollment | Providers by specialty, health outcomes |
| Education | Counts of schools, students and teachers | Results, school points on the map, degrees by field |
| Housing | Survey data, public and tax credit housing, FEMA aid approved | Rent vouchers, lending, inspected damage |
| Climate over time | One summer picture of heat and vegetation | Drought, rainfall by year, recovery after storms |
| Daily needs | Distance to hospitals and health centers | Distance to a supermarket, pharmacy or bank |
| Nature and coast | Protected areas, wetlands, streams | Species records, beach water quality |

## Track A: new sources

### Tested on 2026-11-14 (no key; each returned Puerto Rico rows)

One request was made to each source. The licence and terms of each still need the usual check before anything is collected.

| Row | What it adds | Level | What the test returned |
|---|---|---|---|
| `hmda` | Home loans made and denied, with amounts | Census tract | 13,550 loans made in 2023, worth $2.24 billion |
| `fdic` | Bank branches and their deposits | Branch, municipio | 262 branches in the 2025 file. The cooperativas are not in it (COSSEC insures them) |
| `hud-vouchers` | Rent vouchers in use | Census tract | 942 tract rows |
| `drought-monitor` | Share of each municipio in drought, every week | Municipio | Weekly rows for Ponce up to 2026-11-10 |
| `fema-housing-damage` | Damage FEMA inspectors found in homes, owners and renters | ZIP code, municipio | 15,095 rows for owners |
| `nppes` | Health care providers by specialty | Municipio (counts) | Providers with practice address and specialty |
| `school-outcomes` | Reading and math proficiency, civil-rights data, degrees by field | School, municipio | 836 schools with proficiency (2018), 841 in the civil-rights file (2020), 861 with coordinates (2023) |
| `gbif` | Species records | Barrio or hexagon (counts) | 4,279,101 records |

A correction to what was said in the chat on 2026-11-14: FEMA's aid to households is not new. The observatory already publishes the amount approved and the households approved, by municipio (`housing.fema_ia_amount`, `housing.fema_ia_households`). The row adds the inspected damage and a level below municipio.

### Already tested on the wanted-data list, not built

These rows were tested on 2026-10-05 or later and wait only for a decision to build:

- Social Vulnerability Index by tract (`svi`) and walkability by block group (`walkability-epa`).
- Race and ethnicity (`acs-race-ethnicity`) and migration (`pr-migration`) from the ACS; population by age and sex each year (`pop-estimates`).
- Storm surge by hurricane category (`storm-surge`).
- Land cover each year (`landcover-annual`, `esa-worldcover`) and tree cover loss (`forest-loss`).
- Head Start sites (`head-start`, licence not stated) and college data (`college-scorecard`).
- Hotel occupancy by tourism region (`tourism-stats`) and cruise calls (`cruise`).

### Not confirmed (rows added as candidates)

| Row | State on 2026-11-14 |
|---|---|
| `acs-more-tables` | Not test-read. The reader the observatory already uses reads any ACS table file. (Built in step 1, see below.) |
| `nfip` (flood insurance) | The addresses tried answered "Page not found". |
| `ports` | A federal service lists San Juan, Guayama and Guaynabo; the file with cargo tonnage was not found. |
| `vital-components` | The Census Bureau's municipio files give population only; no births, deaths or migration were seen. |
| `medicare-geo-variation`, `lead-energy-burden`, `va-spending`, `beach-water`, `tsunami-zones`, `rainfall-grid` | Not tested. |
| `ssa-oasdi-zip` | Blocked: the Social Security site answered HTTP 403 to a script. |

## Track B: layers computed from data the observatory already holds

The project lead's question was whether gaps can be filled the way algebra solves for X. They can, in three ways. The three differ in how far the result can be trusted, so each layer says which kind it is.

| Kind | What it is | What it may claim |
|---|---|---|
| **Calculated** | Arithmetic on published figures. Nothing is assumed. | As exact as its inputs. It carries their margins of error. |
| **Overlaid** | One published layer laid on another: which points fall in which zones, what lies upstream. | Where things are. Not what will happen to them. |
| **Estimate** | A model with assumptions, such as a road time or a population spread over buildings. | A screening figure. It is published only with a check against something known, a range, and the word "estimate" in its name. |

The observatory already publishes layers of each kind: jobs per employed resident (calculated), residents in a flood zone (overlaid) and drive time to the nearest hospital (estimate).

### The nine layers

| Row | Layer | Kind | Built from | Checked against |
|---|---|---|---|---|
| `derived-daytime-population` | People in each municipio on a working day | Calculated | Commuting flows between municipios, residents | Its own identity: the island total equals the residents |
| `derived-storm-recovery` | Months for night-time light to return after María and Fiona, by barrio | Calculated, with a stated rule | Night-time light by month since 2012 | Regional outage records for Fiona |
| `derived-facility-exposure` | Public facilities and main roads inside flood, sea level rise and landslide zones | Overlaid | Facility layers, bridges, traffic roads, hazard zones | A sample read on the map |
| `derived-upstream` | Residents, buildings, wastewater plants and protected land upstream of each reservoir and river gauge | Overlaid | Catchments, block residents, EPA sites, protected areas | "What drains here" for the same points |
| `derived-access-essentials` | Road distance to the nearest supermarket, pharmacy, bank, library and fire station, by barrio | Estimate | Places, road network, block residents | OpenStreetMap pharmacies, FDIC branches |
| `derived-jobs-reach` | Jobs within 30 and 45 minutes by road, by municipio | Estimate | Jobs by municipio, road network | The commuting flows already published |
| `derived-net-migration-age` | Net migration by age group and municipio | Estimate | Population estimates by age and sex, a life table | The island's published net migration |
| `derived-cut-off-communities` | Residents who can be cut off when roads in flood zones or bridges in poor condition close | Estimate | Road network, flood zones, bridge condition, block residents | Cut-offs described in the WCRP community plans |
| `derived-hex-grid` | One hexagon grid for residents, buildings, heat, slope, flood and broadband | Calculated (surfaces); estimate (residents) | Census blocks, building footprints, the 60 m images, the broadband hexagons | Hexagons add up to the block and barrio totals |

The hexagon grid matters most for analysis. Barrios range from a few blocks to large rural areas, so a barrio average hides a great deal. The broadband layer already uses hexagons of about 0.74 km² (H3 resolution 8). Putting residents, buildings, heat, slope and flood on the same hexagons lets any two layers be crossed below barrio in one unit.

Many simple ratios need no new layer. The Analysis tab's "Show as" options already divide any dataset by residents, households or area, and its composite builder combines datasets. A ready-made view is enough for pairs such as children under 5 beside Head Start places.

### What the observatory will not solve for

- **Figures a publisher withheld.** The jobs data (QCEW) hides some cells to protect employers, and HUD hides small counts to protect households. Subtraction can sometimes recover them. The observatory will not do that.
- **Health outcomes below municipio.** There is no equation to solve: nothing the observatory holds determines how many people in a barrio have diabetes. CDC models such figures for the states from a health survey and leaves Puerto Rico out. Doing the same here would need the survey's records and a statistical model with outside review. It is not proposed.
- **Jobs and electricity use below municipio.** No open source places them below the municipio. Spreading a municipio's total over its barrios would draw a pattern that nobody measured.

## The steps, first visible result first

Effort as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks. Each step is its own pull request, merged only on the project lead's word.

1. **People and movement (M). Shows on the site first.** ACS tables by municipio, barrio and tract, each with its margin of error: language and English ability, nutrition assistance (PAN), poverty by age, race and ethnicity, migration. Daytime population by municipio. All appear in Explore, the Analysis tab and the area profiles. What was built, and what the data did not allow, is in "Step 1 as built" below.
2. **Vulnerability and walkability (S).** The Social Vulnerability Index by tract and the walkability index by block group.
3. **Facilities and roads in hazard zones (M).** Counts by municipio and a line in each facility's pop-up. School points join if (c) is yes.
4. **Credit and housing subsidy (M).** Home loans by tract, bank branches as points with deposits by municipio, rent vouchers by tract.
5. **Climate over time (M).** Drought every week by municipio; months for light to return after María and Fiona; storm surge by hurricane category.
6. **Access to essentials (M).** Road distance to a supermarket, pharmacy, bank, library and fire station, by barrio.
7. **School results and degrees (M).** Proficiency by school, civil-rights data, degrees by field.
8. **Health providers by specialty (M).** Counts by municipio.
9. **The hexagon grid (L), then the layers that build on it or on the road network:** residents who can be cut off (L), upstream of each reservoir (M), jobs within reach (S-M), net migration by age (M).

The sources not yet confirmed are tested when the project lead picks them in (g).

### Step 1 as built (2026-11-14)

Building step 1 changed four things in the plan above. Each is a finding, not a choice.

- **Households without a car were already published** (`economy.no_vehicle_hh_pct`, for municipios, barrios and census tracts since 2026-10-06). The analysis missed it. Nothing to build.
- **Published: four new datasets.** People who speak English less than "very well" and households that received nutrition assistance (PAN), for municipios, barrios and census tracts; children under 18 and people 65 and older below the poverty level, for municipios. Poverty by age stays at the municipio because below it the share is flagged less reliable for more than half of the barrios (`docs/small-area.md`, section 10).
- **Migration from the ACS is too rough by municipio.** The share of people who moved in the past year is flagged less reliable for 50 of the 78 municipios, and the share who came from the United States for 77. The island figures are solid and are quoted in the guide. No dataset is published. Net migration by age (step 9) is the better route.
- **Race and ethnicity are not built.** Decision 31 (2026-10-06) asks whether to publish them below the municipio, for the municipios only, or not at all, and is still open. The approval of this proposal did not answer it.

**Daytime population by municipio is built** (`commuting.py`, `docs/commuting.md`): three calculated datasets with margins of error. San Juan has 342,259 residents and about 450,689 people on a working day; 20 municipios fill and 58 empty.

### Step 2 as built (2026-11-14)

- **Social Vulnerability Index: built** (`svi.py`, `docs/svi.md`). Four datasets for the 78 municipios (the overall rank and three themes) and the same ranks for the census tracts as a file for download. Ranks are within Puerto Rico only. The theme of racial and ethnic minority status is not published as a dataset, because it cannot tell places apart here.
- **Walkability index: not usable for Puerto Rico.** Three of its four parts are blank for every block group (no jobs data and no transit feed for Puerto Rico), so the index is one measure, intersection density, rescaled. Nothing was built. The observatory can compute walkability from its own road network, timetables and places: a computed layer for a later step.

### Step 3 as built, first part (2026-11-16)

- **Built: the flood area** (`facility_exposure.py`, `docs/facility-exposure.md`). Seven overlaid datasets by municipio: public facilities, public schools and their students, and kilometres of main road inside FEMA's 1% flood area. In Puerto Rico: 327 of 2,274 facilities (corrected; first published as 356 of 2,508), 96 schools with 27,178 students, and 596.3 km of main road.
- **Changed from the plan:** bridges are left out, because a bridge over a river stands in the flood area by design.
- **Still to do in step 3:** sea level rise and landslide susceptibility, and the facility points with their flag on the map (public school points with them).

### Step 3 as built, second part (2026-11-16)

- **Built: sea level rise and landslides** in the same file and group (renamed *Facilities and roads in hazard areas*): ten more overlaid datasets. NOAA's 3 ft area: 17 facilities (0.7%; first published as 19), 17.0 km of main road. USGS High or higher landslide susceptibility (main island): 26 facilities (1.2%; first published as 68), 474.3 km of main road (8.9%).
- **Changed from the plan:** roads are read every 20 m for these two hazards (NOAA's coastline is too detailed to cut every road by it). A building's own cell reads low on the landslide map because buildings stand on levelled pads; the caveat says so, and roads are the better guide.
- **Room made first:** the area profile reads `catalog_domains.json` (7 KB compressed) instead of the whole catalog index (42 KB), which now loads on first use.
- **Still to do in step 3:** the facility points with their flag on the map, and public school points as a layer.

### Step 3 as built, third part (2026-11-16)

- **Built: the points on the map.** Public schools as a layer (`public_schools.geojson`, Education group, 2D and 3D) and the hazard flags in every facility's pop-up (`facility_hazards.json`). Step 3 is complete.
- **Correction:** points that share their coordinates with another point of the same layer (234, mostly libraries listed at one address) are no longer tested. The facility counts fell: flood 327 (was 356), sea level rise 17 (was 19), landslides 26 (was 68). Students and roads did not change.

### Step 4 as built (2026-11-16)

- **Built: bank offices, deposits and home loans** (`credit.py`, `docs/credit.md`). Six yearly datasets by municipio: offices of FDIC-insured banks and their deposits (June 30, 2000-2026), and home loans made, home purchase loans, their amount and the denial share (HMDA, 2018-2025). Puerto Rico had 571 bank offices in 2006 and 260 in 2026; 14,269 home loans were made in 2025 and 18.5% of decided applications were denied.
- **Changed from the plan:**
  - **No office points.** Since 2023 the FDIC places about half the offices at the centre of their ZIP code (113 of 260 have a street-level location), so the observatory counts offices by municipio and draws none. Geocoding the addresses is left for step 6, which needs bank points.
  - **HMDA by municipio, not by census tract.** The rows describe single borrowers, and municipio counts with a floor of 10 keep them unidentifiable.
  - **Rent vouchers are not published.** HUD leaves out every tract with 10 or fewer voucher holders: the 176 tracts shown hold 5,841 of about 26,000 vouchers in use. The `hud-vouchers` row is blocked with the numbers.

### Step 5 as built, first part (2026-11-16)

- **Built: drought by municipio and year** (`drought.py`, `docs/drought.md`). Three yearly datasets from every weekly US Drought Monitor map since January 2000: the average share of the area in drought (D1 or worse), and the weeks with drought, and with severe drought (D2 or worse), over half the area. 2015 was the worst whole year (28.5% of the island on average); 2026 so far is 26.5%, and on August 25, 44.5% of the island was in extreme drought, the most in the series.
- **Changed from the plan:** the weeks are added up by year, because the Analysis tab, the map and the profiles read yearly series. The file is rebuilt every week, so the current year stays up to date.
- **Still to do in step 5:** the months for night-time light to return after María and Fiona, and storm surge by hurricane category.

### Step 5 as built, second part (2026-11-17)

- **Built: storm recovery from night-time light** (`storm_recovery.py`, `docs/storm_recovery.md`), by municipio and barrio, for María (2017) and Fiona (2022). Two datasets:
  - The months until light was back to 80% of the same month the year before, two months in a row.
  - The darkest month after the storm, as a share of the same month the year before.
- **What it shows.** The island's light was back by May 2018 after María (8 months) and by October 2022 after Fiona. Vieques (26 months) and Maunabo (25) were slowest after María. The southwest got darkest after Fiona.
- **Checks.** The figures agree with the utility's restoration record and, for Fiona, with EAGLE-I's outage record for the seven LUMA regions.
- **Changed from the plan:**
  - The line is 80% for two months, not 90% for three. At 90%, the island would take 14 months after María, against about 8 in the restoration record.
  - Barrios too dim to read (under 0.5 nW/cm²/sr in the year before) have no figure.
- **Still to do in step 5:** storm surge by hurricane category (built the same day, below).

### Step 5 as built, third part (2026-11-17)

- **Built: residents and homes in the storm surge area** (`exposure.py --surge`, `docs/exposure.md`, section 9), by municipio, barrio and census tract, for hurricanes of category 1 to 5. Ten new families in the exposure series: any water, and 3 feet or more.
- **What it shows.** In the near worst case at high tide, storm surge reaches 15,961 residents (0.5%) in a category 1 hurricane and 120,934 (3.7%) in a category 5; 50,353 of them under 3 feet of water or more. Cataño has the largest share (52.3% at category 5); San Juan has the most people (32,165).
- **Checks.** The flooded area per category equals NOAA's own counts (99 to 367 km²). Every resident counted at category 1 is also inside FEMA's 1% flood area.
- **Changed from the plan:**
  - The maps were not turned into polygons. The observatory's own raster reader reads them directly, at each census block's point.
  - The five categories are not strictly nested in NOAA's maps (five blocks in San Juan), so the build does not require it.
- **Not done:** a map layer that draws the surge area. **Step 5 is complete.**

### Step 6 as built (2026-11-18)

- **Built: road distance to essentials** (`essentials.py`, `docs/essentials.md`), by municipio and barrio. Seven estimates: the average road distance from where residents live to a supermarket, any food store (colmados included), a pharmacy, a bank or cooperativa, a library and a fire or EMS station, and the share of residents more than 5 km from a supermarket.
- **What it shows.** On the island, residents live 2.81 km by road from a supermarket on average, 2.24 km from a pharmacy and 4.58 km from a fire or EMS station. 16.0% live more than 5 km from a supermarket. Maricao, Comerío and Yabucoa are the farthest from a supermarket.
- **Checks.** Most of OpenStreetMap's shops have an Overture shop within 300 m (76.0% of supermarkets, 87.1% of pharmacies, 84.1% of banks); the rest are added. Overture alone gives island figures within 0.15 km.
- **Changed from the plan:**
  - Banks come from Overture and OpenStreetMap, not FDIC: half of FDIC's offices sit at the centre of their ZIP code, and FDIC leaves out the cooperativas.
  - A distance to any food store was added: in small towns the only food stores either directory lists are colmados.
  - The libraries are USAC's list, which also counts community and church libraries and technology centres, so the label says "a library".
- **Not done:** travel time and transit; the shops are not drawn.

### Step 7 as built, first part (2026-11-18)

- **Built: degrees awarded by colleges** (`degrees.py`, `docs/degrees.md`), by level and broad field, by municipio of the reporting campus, academic years 2014-15 to 2023-24.
- **What it shows.** Bachelor's degrees fell from 20,459 to 14,779 (−28%); education degrees fell most (−57%); health and STEM held.
- **Changed from the plan:**
  - Read straight from NCES's IPEDS files, not the Urban Institute's portal, which has no completions after 2021 for Puerto Rico.
  - Counted where the college reports: NUC University reports all its campuses and online programmes from Bayamón (29.4% of the island's awards in 2023-24). Every definition says so.
- **Still to do in step 7:** school conditions from the Civil Rights Data Collection (2021-22) and reading and math proficiency (newest readable by school: 2017-18).

### Step 7 as built, second part (2026-11-18)

- **Built: public school conditions** (`school_conditions.py`, `docs/school_conditions.md`), by municipio, from the Civil Rights Data Collection.
- **What it shows.** 45.7% of public school students were chronically absent in 2021-22 (8.9% in 2017-18); there were 546 students per counselor, and 51.5% of schools reported no counselor.
- **Check.** KIDS COUNT (2024) reports 48% chronically absent around 2022-23.
- **Changed from the plan:** Puerto Rico's staff items are missing in 2017-18, so staff measures have 2021-22 only; first-year teachers are missing in 2021-22 and are not published.
- **Still to do in step 7:** reading and math proficiency (built the same day, below).

### Step 7 as built, third part (2026-11-18)

- **Built: test results** (`proficiency.py`, `docs/proficiency.md`): the share of public school students proficient in reading (Spanish) and math on META-PR, by municipio, 2014-15 to 2018-19.
- **What it shows.** In 2018-19, 45.2% were proficient in Spanish and 30.2% in math; Orocovis and Barranquitas were highest in both, Vieques lowest.
- **Check.** The Department of Education's own 2018-19 figures are 45.1% and 30.1%.
- **Changed from the plan:** the results run to 2018-19, not 2017-18: the portal's year is the fall of the school year. Nothing newer is published by school in a form a script can read.
- **Step 7 is complete.**

### Step 8 as built (2026-11-18)

- **Built: health care providers by type** (`providers.py`, `docs/providers.md`), by municipio, from CMS's NPPES registry: seven types, counts only, none from 1 to 9.
- **What it shows.** 12,375 physicians are registered with a Puerto Rico practice address; 5,406 of them updated their record in the last five years. San Juan holds the most of every type.
- **Changed from the plan:** the monthly full file is read as a stream instead of the paged API; registered nurses are left out (only nurses who bill need an NPI); each count comes with a range (registered against updated within five years) because the registry keeps providers who left.

### Step 9 as built, first part (2026-11-19)

- **Built: the hexagon grid** (`hexgrid.py`, `docs/hexgrid.md`): 8,745 equal hexagons of 1 km² with residents, housing units, buildings, land under buildings and residents in the flood area, as a map layer with a picker for the measure.
- **Checks.** The hexagons add up exactly to the island's residents, housing units and buildings; the residents in the flood area equal the exposure series.
- **Changed from the plan:** the observatory's own equal-area hexagons, not H3: every cell has the same area, and the map already draws them. Broadband stays on the FCC's H3 layer.
- **Next:** heat, slope and vegetation per hexagon; then the layers that build on the grid.

### Step 9 as built, second part (2026-11-20)

- **Built: heat, greenness and slope per hexagon** (`hexgrid.py`, `docs/hexgrid.md`): the median summer-morning surface temperature and greenness of each hexagon's 60 m cells, and the mean slope of its 10 m cells. 653 hexagons of land with no resident or building were added, so the grid covers the island (9,398 cells).
- **Checks.** San Juan is hotter and less green than the mountains, and the mountains steeper, as in the barrio files.

### Step 9 as built, third part (2026-11-20)

- **Built: residents cut off from hospitals** (`cutoff.py`, `docs/cutoff.md`), by municipio and barrio: the share with no open road to a hospital when the roads in FEMA's 1% flood area close, when bridges in poor condition close, and both.
- **What it shows.** 16.2% of residents (range 14.9% to 24.5%) in a worst case of floods; half of them live on dry streets. Bridges in poor condition alone cut off 0.1%.
- **Checks.** 5 of the 8 WCRP communities whose plans say they are cut off come out cut off, against 16 of the other 67.
- **Changed from the plan:** the test is a hospital, not the town centre (a town centre in the flood area is often itself cut off); expressways and sound bridges stay open; landslides are left out.

### Step 9 as built, fourth part (2026-11-23)

- **Built: what lies upstream of each reservoir and river gauge** (`upstream.py`, `docs/upstream.md`, Reservoirs page section 4): the land that drains to each of 25 reservoirs and 71 gauges, with its residents, buildings, wastewater treatment plants and protected land.
- **What it shows.** Carraízo (Lago Loíza) has the most people upstream: 281,551 residents on 530 km², with 3 wastewater plants.
- **Checks.** The land found is within 25% of USGS's own drainage area for 73 of 87 sites (median ratio 1.03); the rest are marked.
- **Changed from the plan:** six off-stream reservoirs have no figures; impaired waters are left out (not in the cache). Building it fixed the catchment network, which chained river mouths along the coast (`watersheds.py`).

### Step 9 as built, fifth part (2026-11-24)

- **Built: jobs within reach** (`jobs_reach.py`, `docs/jobs-reach.md`), by municipio: the jobs residents can reach within 30 and 45 minutes by car, and their share of Puerto Rico's jobs.
- **What it shows.** 236,860 jobs within 30 minutes on average (25.1% of 943,002); over half of Puerto Rico's jobs from Guaynabo, San Juan and Cataño, a few thousand from the mountain municipios.
- **Checks.** 95.9% of the workers in the commuting flows work in a municipio the model puts within 45 minutes of home.
- **Changed from the plan:** QCEW has no jobs below the municipio, so they are spread over business places to start the search; only municipio figures are published.

### Step 9 as built, sixth part (2026-11-24)

- **Built: net migration by age** (`netmig_age.py`, `docs/net-migration-age.md`), by municipio, 2010-2020: the residual method on the two censuses with Puerto Rico's UN life table.
- **What it shows.** The island lost 384,100 people aged 10 and over (-11.3% of expected); -28.1% of its people aged 20 to 29; a small gain at 65 and over.
- **Checks.** Within 6.1% of the demographic balance of the two censuses.
- **Changed from the plan:** census to census, not the yearly estimates (their age detail rests on the Census Bureau's own migration assumptions); the Census API needs a key, so the public CSV files are read. Step 9 is complete.

### Already planned under other decisions, not repeated here

- Rooftop solar potential by barrio and power outages: decision 104 (energy), steps 5 and 6.
- Land cover, the satellite image series and Foursquare places: decision 91.
- The second pass on transportation: decision 105, step 5.

## Rules that apply to every step

- Sources a script can read with no key. No data from the Contralor. Licence and terms confirmed before collecting.
- The newest source, or one a script can refresh, over a static copy.
- Private homes and sensitive sites are counted, never drawn or named.
- Rows about single people, loans or households (`hmda`, `nppes`, `fema-housing-damage`) are published as counts and sums only, with a minimum count per cell.
- Every estimate has the word "estimate" in its name, a method page, a range and a check against something known. It is never mixed into a ranking without that label.
- Every technical term a reader sees gets a sourced definition in Spanish and English.
- Each data step adds dictionary entries and profile figures. Measured on this branch (`budget.py`, 2026-11-14): the area profile's data is at 656.9 of 660 KB and its scripts at 120.1 of 122 KB; the dictionary page's data is at 727.5 of 760 KB; the map's scripts are at 190.2 of 250 KB. The area profile has the least room, so each step starts by measuring it and makes room if needed.

## Decisions for the project lead (decision 107)

- **(a) The order of the steps.** Proposed: 1 to 9 as above.
- **(b) The three kinds of computed layer and their labels** (calculated, overlaid, estimate), and the rule that an estimate is published only with a check and a range.
- **(c) School points on the map.** Proposed: yes. They are public buildings and the federal file gives their coordinates. Closed schools would be drawn apart from open ones.
- **(d) The minimum count** for cells built from rows about single people, loans or households. Proposed: 10, as the broadband layer's 10-location floor.
- **(e) Species records.** Proposed: use only the datasets under CC0 and CC BY, and leave the non-commercial ones out.
- **(f) The hexagon grid** as the observatory's unit below barrio. Proposed: yes, after steps 1 to 8.
- **(g) Which unconfirmed sources to test next.** Proposed: the ACS tables first (step 1 needs them), then flood insurance and rainfall.
- **(h) Tsunami zones.** If no open copy is found, asking the Red Sísmica in writing is a request to an outside body. Nothing is sent without the project lead's word.

## Sources checked on 2026-11-14

Each line is one request with no key. "Returned" means the answer held Puerto Rico rows.

- HMDA Data Browser API, `ffiec.cfpb.gov/v2/data-browser-api/view/aggregations` (states=PR, years=2023): returned.
- FDIC Summary of Deposits, `api.fdic.gov/banks/sod` (STALPBR:PR, YEAR:2025): returned, 262 branches.
- HUD open data, `Housing_Choice_Vouchers_by_Tract` (STATE = '72'): returned, 942 rows.
- US Drought Monitor, `usdmdataservices.unl.edu` county statistics (72113): returned. The island-wide call (aoi=72) returned an empty list.
- OpenFEMA `v2/HousingAssistanceOwners` (state eq 'PR'): returned, 15,095 rows. `v2/FimaNfipClaims` and `v2/FimaNfipPolicies`: page not found.
- NPPES registry API, `npiregistry.cms.hhs.gov/api` (state=PR): returned.
- Urban Institute Education Data API (fips=72): school directory 2023, civil-rights directory 2020, assessments 2018 and degrees by field 2022 returned. Graduation rates 2020 answered HTTP 500.
- GBIF occurrence search (country=PR): returned, 4,279,101 records.
- Census Bureau population estimates, Vintage 2025 folders: `prm-est2025-pop.xlsx`, `prm-est2025-chg.xlsx` and an age-and-sex folder. No components by municipio seen.
- BTS `NTAD_Hazard_Exposure_Principal_Ports`: lists San Juan, Guayama and Guaynabo.
- Social Security Administration, ZIP code workbook for Puerto Rico: HTTP 403, not bypassed.
