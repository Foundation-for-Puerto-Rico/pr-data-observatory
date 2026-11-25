# Infrastructure data (Phase 3, item 10: data wave D)

`infrastructure_series.py` writes two files for the 78 municipios and Puerto Rico, on the Economy tab under "Infrastructure":

- `site/data/infrastructure_series.json`: one snapshot. It has drinking water (5 datasets) and power plants (3).
- `site/data/bridges_series.json`: one value a year, 2016 to 2025, for bridges and their condition (3 datasets).

Plan: `docs/proposal-2026-10.md` (J row 10, D4). All three sources are US federal data (public domain), and none needs a key.

## Drinking water (EPA ECHO)

The source is ECHO's Safe Drinking Water Act web services: the **active community water systems** of Puerto Rico. In October 2026 there were 404 of them, serving about 3.3 million people.

- **Columns kept:** seven (`ECHO_COLS`): system id, type, population served, owner type, enforcement priority, health-based violation flag and the FIPS codes of the municipalities served. The system's name, which ECHO's download always includes, is dropped before anything is written to disk.
- **Several municipalities.** 28 systems serve two to four municipalities each; together they serve 1.76 million people. A system counts in every municipality it serves, so the municipal values add up to more than Puerto Rico's, which counts each system once.
- **Population served** is an island figure only (in the file's notes). A large system's people cannot be split honestly among the municipalities it serves.
- **No municipality.** 5 small systems give Puerto Rico's code but no municipality. They count in the island values only.
- **The two flags**, as ECHO's search results help defines them:
  - **Health-based violation** (`HealthFlag`): a breach of a maximum contaminant level, a maximum residual disinfectant level or a treatment technique rule.
  - **Enforcement priority** (`SeriousViolator`): unresolved serious, multiple or continuing violations, which EPA designates as a priority for formal enforcement.
  - Both are compliance records, not proof that the water is unsafe today.
- **Left out:** ECHO's "current violation" flag. The help page does not define it.

October 2026: 239 systems have a health-based violation flag and 125 are an enforcement priority. The most priority systems are in Utuado, Adjuntas and Ponce.

### Systems outside PRASA (added 2026-10-18)

- **What counts.** EPA Region 2 defines non-PRASA systems as the privately owned ones. `water_nonprasa` counts the active community systems that SDWIS records as privately owned (owner type P, already among the seven columns kept): 207 in October 2026, serving 100,743 people, in 47 municipios. SDWIS records some community-run systems as local government, so the count can miss a few.
- **Residents served.** `water_nonprasa_pop` adds each system's own population figure to its municipio when the system serves that one alone. The 5 that serve two municipios (1,087 people) and 1 that gives no municipio (165) count in Puerto Rico's total only.
- **Flags.** 201 of the 207 carry ECHO's health-based violation flag (`notes.water.non_prasa`).
- **No names, no barrios.** Names are never kept: many systems are named after a person, a family or a farm. No open source gives their location below the municipio (`docs/community.md`, `wanted.json` row `non-prasa-locations`).

## Wastewater discharge permits (EPA ECHO, added 2026-11-11)

The `wastewater` row of `wanted.json`. `infrastructure_series.py` searches ECHO's Clean Water Act service for the active facilities of Puerto Rico (`cwa_rest_services`, no key) and keeps the 177 with an **individual NPDES permit**: sewage treatment plants, water filtration plants, power plants and factories that discharge wastewater into surface waters. Four datasets in `infrastructure_series.json`, group "Wastewater":

| Dataset | What it counts | Puerto Rico |
|---|---|---|
| `wastewater_permits` | facilities with an individual permit, in the municipality that holds their point | 177 |
| `wastewater_plants` | of those, publicly owned treatment works (public sewage treatment plants) | 51 |
| `wastewater_major` | of those, the ones EPA classes as major dischargers | 62 |
| `wastewater_violation` | of those, the ones whose current status is "Violation Identified" or "Significant/Category I Noncompliance" | 113 (7 in significant noncompliance) |

- **Left out.** The 1,097 facilities covered by a general permit (construction sites, industrial and municipal stormwater), which come and go with each project, and the 81 records ECHO attaches to another permit.
- **Counts only.** As for the other EPA sites (`docs/conditions.md`), no name and no point is published: the name is dropped as the download is read, and the point only places the facility in a municipality. ECHO's own county code comes from the mailing address and names another municipality for 6 facilities; the point decides.
- **How to read the violation count.** It is ECHO's status of the last reported quarter. A late or missing monitoring report counts the same as a discharge above a limit, so the count is a compliance record, not a measure of water quality. The dataset's card, its dictionary entry and its Spanish say so.
- **Not included, possible later.** Design flow of each plant, the pollutants over their limit, the receiving water, and a link from each plant to the municipalities it serves (no federal file gives the service area).
- **One rebuild.** Adding these datasets rebuilt the whole file: the water, power and bridge values came out identical to the published ones; only the EIA month moved from 2026-08 to 2026-09.

## Air pollution sources (EPA ECHO, added 2026-11-11)

`infrastructure_series.py` searches ECHO's Clean Air Act service for the active facilities of Puerto Rico (`air_rest_services`, no key): the stationary sources the Act regulates, from power plants and factories to a business with an emergency generator. Two datasets in `infrastructure_series.json`, group "Air pollution sources":

| Dataset | What it counts | Puerto Rico |
|---|---|---|
| `air_sources` | active regulated facilities, in the municipality that holds their point | 482 |
| `air_major` | of those, the ones EPA classes as major emissions sources (Title V) | 44 |

- **Counts only.** As for the wastewater permits, no name and no point is published. ECHO's own county code names another municipality for 33 facilities; the point decides.
- **No violation dataset.** ECHO showed 1 facility with a high priority violation on 2026-11-11. A count that small would point at one facility, so it is kept in the file's notes for Puerto Rico only.
- **How to read it.** Where permitted sources are, not where the air is dirty: it is not a measure of air quality, and moving sources are not counted. The `air-quality` row of `wanted.json` (EPA AirData monitors) is still open.
- **Where it lives.** With the other ECHO counts in `infrastructure_series.json`, because `conditions.py` (the other EPA sites, by barrio) could not be rebuilt without refreshing all of its sources. Since 2026-11-12 seven of the ECHO counts are also given by barrio, from this script, in `infrastructure_barrio.json` (see **By barrio** below).
- **One rebuild.** The other values of the file came out identical to the published ones.

## Hazardous waste handlers (EPA ECHO, added 2026-11-11)

`infrastructure_series.py` searches ECHO's hazardous waste service (RCRA, `rcra_rest_services`, no key) for the active handlers of Puerto Rico: the businesses and institutions that generate, transport, treat or store hazardous waste. Two datasets in `infrastructure_series.json`, group "Hazardous waste":

| Dataset | What it counts | Puerto Rico |
|---|---|---|
| `hazwaste_handlers` | active handlers, in the municipality that holds their point | 1,740 |
| `hazwaste_large` | of those, the large quantity generators (1,000 kg or more a month) | 113 |

- **Counts only.** No name and no point is published. ECHO's own county code names another municipality for 113 handlers; the point decides.
- **No violation dataset.** ECHO showed 17 handlers with a violation on record on 2026-11-11: too few to publish by municipio, so the number is kept in the file's notes for Puerto Rico only.
- **How to read it.** Where hazardous waste is generated or managed under the rules, not where it has been spilled. 1,203 of the handlers generate very small quantities, so the count follows where businesses are.
- **One rebuild.** The other values of the file came out identical to the published ones.

## Inspections and enforcement actions (EPA ECHO, added 2026-11-12)

`infrastructure_series.py` searches ECHO's all-programs service (`echo_rest_services`, no key) for every active facility of Puerto Rico that EPA regulates under the air, water, hazardous waste or drinking water laws (3,925). Two datasets in `infrastructure_series.json`, group "Environmental enforcement":

| Dataset | What it counts | Puerto Rico |
|---|---|---|
| `epa_inspected` | facilities inspected at least once in the last five years | 594 (1,074 inspections) |
| `epa_formal_action` | facilities with at least one formal enforcement action in the last five years | 347 (471 actions) |

- **Counts only.** No name and no point is published. Penalty amounts are not published: a sum of dollars for a municipality would often be one facility's.
- **Points off the island.** `locate(points, strict=False)` gives None for a point more than 2 km from every municipality (a head office on the mainland, a point at sea). 1 such facility is placed by ECHO's county code; 2 with neither are left out. The other datasets still stop the build on such a point.
- **How to read it.** An inspection is routine, and a formal action can be about reporting as well as pollution. Both follow where regulated facilities are.
- **Not included, possible later.** Inspections and actions by year (ECHO's case and inspection downloads), and informal actions.
- **One rebuild.** The other values of the file came out identical to the published ones.

## Toxic chemical releases (EPA TRI, added 2026-11-12)

`infrastructure_series.py` reads the TRI Basic Data File for Puerto Rico that `conditions.py` already reads for its count of facilities (`epa_tri`), and adds the amounts. Two datasets in `infrastructure_series.json`, group "Toxic chemical releases", reporting year 2024:

| Dataset | What it holds | Puerto Rico |
|---|---|---|
| `tri_release_lb` | pounds released on site and off site, summed by municipio | 2,686,420 |
| `tri_air_lb` | of those, pounds released on site to the air (stack and fugitive) | 1,264,140 |

- **No name, no point.** The script reads only the columns of `TRI_COLS`; the facility's name never reaches the cache.
- **One facility can be the whole figure.** 18 of the 43 municipalities with a reporting facility have only one, and one facility reported 32.6% of the island's total. TRI is public for each facility by name, so nothing confidential is shown; the entries say so.
- **How to read it.** Pounds of different chemicals are added together: amount, not toxicity or risk. EPA's RSEI scores weigh toxicity and are a possible later addition.
- **Refresh.** The `epa_tri` probe of `refresh/sources.json` belongs to the `conditions` unit. A new reporting year reaches these two datasets with the next infrastructure rebuild.
- **One rebuild.** The other values of the file came out identical to the published ones.

## Power plants (EIA-860M)

The source is EIA's monthly generator inventory, from the newest file that answers (August 2026 at the build), sheet `Operating_PR`.

- **Columns kept:** plant id, technology, nameplate capacity, status and the plant's point. Owner and plant names are dropped.
- **Location.** The county is blank for about a third of the generators, and one row names "Cupey" (a sector of San Juan). So each generator is placed in the municipality whose boundary holds its point (`site/data/municipios.geojson`). The points stay in the local cache (`cache/infrastructure/`) and are never published.
- **Capacity.** Generating capacity is nameplate capacity without batteries, which store power. Renewable capacity is solar, wind, hydroelectric and landfill gas.
- **Not covered:** plants whose generators add up to less than 1 MW, most rooftop solar among them, are not in EIA's inventory.
- **Standby.** EIA's operating list includes generators on standby and a few out of service for now (85 of 228 in August 2026, about 110 MW). EIA groups them with the operating ones, and so does this file.

August 2026: 228 operating generators at 67 plants, 6,436 MW without batteries (6,474 MW with 38 MW of batteries), of which 398 MW is renewable.

## Bridges (FHWA National Bridge Inventory)

The source is the yearly delimited file of Puerto Rico, 2016 to 2025.

- **Columns kept:** the county code and the condition ratings.
- **Condition rule.** Each bridge's condition follows FHWA's rule: the lowest of the deck, superstructure, substructure and culvert ratings. 4 or below is poor, 7 or above is good, and the rest is fair.
- **Check.** From 2019 the file gives FHWA's own condition column. The rule gives the same answer for every bridge in every such year, and the build stops otherwise.
- **Results.** 2,308 bridges in 2016 (268 poor, 11.6%) and 2,434 in 2025 (344 poor, 14.1%).
- **Format change.** FHWA moves to the Specifications for the National Bridge Inventory (SNBI) from 2026, and the reader will need an update then.

## Airports and ferries (BTS T-100, FAA, BTS ferry census)

`gateway_series.py` writes `site/data/gateway_series.json`: how many people board at each gateway, every year, for the 78 municipios and Puerto Rico. It appears on the Economy tab under "Infrastructure · Airports and ferries". All three sources are US federal data (public domain), and none needs a key.

| Dataset | Source | Years |
|---|---|---|
| `air_passengers`: passengers boarding commercial flights | BTS T-100 Segment Summary by Origin Airport | 2014 to 2025 |
| `air_departures`: commercial flights departing | BTS T-100 | 2014 to 2025 |
| `air_enplanements_faa`: passengers boarding, FAA's count | FAA Commercial Service Airports enplanements | 2023 to 2025 |
| `ferry_passengers`: passengers boarding ferries | BTS National Census of Ferry Operators | 2019, 2022, 2024 |

- **Where a gateway counts.** An airport counts in the municipality that holds it, by its FAA code in `transport.json`. San Juan's Luis Muñoz Marín airport (SJU) is in **Carolina**, and Isla Grande (SIG) is in San Juan. A ferry terminal counts in the municipality that holds its point (`infrastructure_series.locate`).
- **Boardings, not visitors.** Every figure counts passengers who board. Residents who travel and passengers who change planes are counted, and arriving passengers are not.
- **Full years only.** A year of T-100 is published once SJU has all twelve months. A smaller airport with fewer months had no commercial flights in the others: Ponce reported 3 months in 2020 and 9 in 2021.
- **FAA and T-100 agree.** For 2023 to 2025 the two island totals differ by less than 1%. FAA adds Ceiba's airport (RVR, 23,214 boardings in 2025), which T-100 does not have. FAA files from before 2024 are under other names that no longer answer.
- **Ferries.** Each census reports passengers on one-way segments. A segment's passengers board at its first terminal. The 2020 census gives data year 2019, and since 2022 BTS names each census for the year of its data. The 2018 census is left out: it does not state its data year, and its routes start at Fajardo, before the move to Ceiba.
- **Results.** 7.2 million air boardings in 2025 (6.7 million at SJU) and 2.5 million in 2020. Ferry boardings were 1.64 million in 2019, 1.15 million in 2022 and 1.62 million in 2024.
- **Not included.** Cruise passengers: the Tourism Company's and the cruise port's figures state no license (`wanted.json`, `cruise`). Arrivals by airport (Ports Authority report) and ferry vessels and trips are also not included.

`python gateway_series.py` downloads only what is missing from the cache. `--refresh` downloads again, and `--check` rebuilds the file from the cache and exits 1 if the published file differs. `build.py` runs it after the infrastructure series, because it needs `transport.json`.

## Not done in item 10

- **Dams (USACE National Inventory of Dams):** the download API answered HTTP 403 to automated requests on 2026-10-14 (noted in `wanted.json`).
- **Power outages:** LUMA's outage map bars automated access without written permission. EAGLE-I reports Puerto Rico only as six regions.
- **Grid assets, shelters, police and fire stations (island geoserver):** no license is stated, and the police layer holds officers' names and phones. These are not harvested.
- **Wastewater permits, antenna towers, landfills:** still `checked` in `wanted.json`.
- **Broadband:** the ACS internet shares are already published (`internet_subscription_pct`, `no_internet_pct`). The FCC's map refuses automated requests.

## How to update

`python infrastructure_series.py` downloads only what is missing from the cache. `--refresh` downloads again, and `--check` rebuilds both files from the cache and exits 1 if a published file differs. `build.py` runs it before the care and Medicare series.

## By barrio (2026-11-12)
- **What.** `infrastructure_series.py` also writes `infrastructure_barrio.json`: seven of its counts for the 901 barrios, under the same keys (`BARRIO_KEYS`): `wastewater_permits`, `wastewater_plants`, `wastewater_major`, `air_sources`, `air_major`, `hazwaste_handlers`, `hazwaste_large`. Those datasets carry `barrioFile`, so the Analysis tab offers them by barrio, as it does the EPA sites of `conditions.py`.
- **How.** `barrio()` reads the rows `compute()` cached and places each facility with `conditions.Barrios` (the barrio whose outline holds the point, or the nearest within 2 km). The total must equal the municipality file's, or the build stops. The notes give, for each count, the barrios with one or more facilities and the municipalities whose barrios add up to another count than the municipal boundary gives (2 for the hazardous waste handlers on 2026-11-12: a point near a municipal line).
- **What is not by barrio.** Wastewater violations, inspections, formal enforcement actions and the pounds of toxic releases stay at the municipality. In a barrio they would nearly always be one facility's own record, which the rule "aggregated data only" (`docs/adding-data.md`) does not clearly allow. That is a decision for the project owners.
- **No names or points.** As before, only counts are published.
