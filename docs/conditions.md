# Local conditions by barrio and municipio (2026-10-17, branch `vuln-inputs`)

Francis approved these datasets on 2026-10-17 (HANDOFF decision 41). They are general observatory data from official sources. They also hold the inputs that the WCRP vulnerability index lacked in its rebuild (the held branch `wcrp-area`, `docs/wcrp.md`, "The rebuild"), but nothing here is WCRP content.

`conditions.py` writes two files:

- `conditions_series.json`: 14 datasets for the 78 municipios and Puerto Rico, in the shape of `facility_series.json` (a snapshot; each dataset in its source's vintage).
- `conditions_barrio.json`: the same 14 datasets for the 901 barrios, under the same keys, in the shape of `acs_barrio.json` (`level`, `geo.ids`, `vars[].years`).

## The datasets

| Key | What | Source | Licence | Vintage | Puerto Rico |
|---|---|---|---|---|---|
| `epa_tri` | Toxics Release Inventory facilities | EPA TRI Basic Data File, Puerto Rico (Envirofacts download) | EPA Standard Open Data License (public domain) | reporting year 2024 | 104 |
| `epa_rmp` | Risk Management Plan facilities, active | EPA Facility Registry Service, layer 8 | same | read 2026-10-17 | 33 |
| `epa_npl` | Superfund sites on the final National Priorities List | EPA Facility Registry Service, layer 22 (SEMS_NPL) | same | read 2026-10-17 | 18 |
| `epa_landfills`, `epa_landfills_open` | Municipal solid waste landfills, all and still open | EPA LMOP, "All Landfills in LMOP Database with Coordinates" | same | data edited 2024-09-20 | 32, 22 open |
| `epa_303d_pct` | Share of the area in a 303(d)-listed assessment unit | EPA ATTAINS, layer 2 (areas) | same | 2024 reporting cycle | 54.4% |
| `epa_naa_so2_pct`, `epa_naa_lead_pct` | Share of the area in a sulfur dioxide (2010) or lead (2008) non-attainment area | EPA Green Book map service, layers 4 and 3 | same; the service states no use constraints | read 2026-10-17 | 2.5%, 0.5% |
| `chas_severe_hh`, `chas_severe_pct` | Households with one or more of the four severe housing problems, and their share | HUD CHAS by census tract (HUD eGIS) | U.S. Public Domain (HUD's open data catalog) | 2016-2020 | 193,934; 16.1% |
| `street_intersections`, `street_intersection_density` | Street intersections, and per square mile of land | Census TIGER/Line EDGES | US Government work | TIGER/Line 2026 | 116,462; 34.0 |
| `hosp_drive_min`, `hosp_road_km` | Drive time and road distance to the nearest general hospital (estimate) | CMS Hospital General Information; OpenStreetMap and HHS hospital points; `roads.bin` (OpenStreetMap) | public domain; ODbL for OpenStreetMap | CMS read 2026-10-17 | 10.9 min; 8.4 km |

The licence of each source is recorded in `dictionary_src/sources.json`. EPA's data catalog (`edg.epa.gov/data.json`) lists every dataset used here under the EPA Standard Open Data License: EPA data are public domain unless otherwise specified. The files' class is `open-with-conditions` because the drive time uses OpenStreetMap (ODbL).

## How each figure is made

- **Sites** (TRI, RMP, NPL, landfills). Each site is counted in the barrio whose outline (`barrios.geojson`) holds its point, or in the nearest outline within 2 km (a coastal point). A municipio is the sum of its barrios. Puerto Rico adds any site no barrio holds (none on 2026-10-17).
  - TRI: the facilities with a report for the newest year EPA publishes (the build tries this year and the three before). A count of facilities, not of releases.
  - RMP: FRS lists 157 RMP interests in Puerto Rico; only the 33 marked active are counted.
  - NPL: the 18 sites currently on the final list; the 8 deleted ones are not counted.
- **Impaired waters and non-attainment.** The share of the barrio's area (as drawn) inside the union of the areas, on an equal-area plane centred on Puerto Rico. A barrio "touches" one when its share is above 0. A municipio's and Puerto Rico's shares come from the areas of their barrios.
  - Puerto Rico maps its river and stream assessment units as the land that drains to each assessed reach. So a listed unit covers a watershed, and 782 of 901 barrios touch one. The original WCRP index (2022) flagged 448 barrios; it does not say which representation of the waters it used.
  - Only units on the 303(d) list (category 5, `on303dlist = Y`, 179 of 336) count. Impaired units that already have a cleanup plan (category 4A, 128) do not.
  - Non-attainment: San Juan and Guayama-Salinas for sulfur dioxide (2018), Arecibo for lead (2011). Areas now in maintenance would not count.
- **Severe housing problems.** CHAS Table 2: owners plus renters with one or more of the four severe problems (no complete kitchen, no complete plumbing, more than 1.5 people per room, housing costs above half of income), over all households.
  - Municipios: exact sums of their tracts (tracts nest in municipios).
  - Barrios: **estimates**. Each tract's two counts are spread over its barrios in proportion to the 2020 housing units each barrio has in the tract (`geo/crosswalk.json` weights; `docs/geography.md`, section 4). The share is the two spread counts divided. The datasets carry `tag: "estimate"` and the barrio legend says so.
  - All 942 CHAS tracts are 2020 tracts; every one with households has 2020 housing units, and the 39 tracts CHAS does not list hold none.
- **Intersection density.** TIGER/Line, not the observatory's `roads.bin`, which comes from OpenStreetMap.
  - Each municipio's EDGES file; road edges (`ROADFLG = Y`), each counted once.
  - An intersection is a topological node where three or more street edges end: secondary roads, local streets, alleys and private roads (MTFCC S1200, S1400, S1730, S1740). Limited-access highways, ramps, service drives, trails, walkways, stairways, parking lot roads, bike and bridle paths are left out. A loop counts two legs.
  - Density: intersections over the 2020 Census land area in square miles.
  - Puerto Rico: 34.0 per square mile. The original WCRP index gave 124.5 with TIGER 2020; it does not say which roads or nodes it counted, so the figures are not comparable.
- **Drive time to a general hospital.** Measured as `care_access.py` measures the distance to a health center.
  - Hospitals: CMS's acute care (and critical access) hospitals with emergency services, 52 on 2026-10-17. VA, Department of Defense, psychiatric and children's hospitals are left out.
  - Each hospital is placed, in this order:
    1. at the OpenStreetMap hospital of its municipio whose name shares at least 60% of its words (29, from `gazetteer.json`);
    2. at the OpenStreetMap hospital within 1 km of HHS's geocoded address whose name says hospital or medical centre and shares a word with CMS's, when no other one there shares as many (8; `conditions.near_hhs`). Two independent signs must agree: the name and HHS's address. A word is compared without a final o, a or s, so "Metropolitan" meets "Metropolitano". Added on 2026-10-17 (branch `conditions-followups`): it places Ashford Presbyterian, Hospital del Maestro, San Lucas in Ponce, Menonita Guayama, Metropolitano, Manatí Medical Center, Professional in Guaynabo and Doctors' Center in Dorado at their buildings. The 2026-10-17 trap of rule 1 (Bayamón Medical Center against Doctors' Center Hospital Bayamón, 1.8 km away) stays out;
    3. at HHS's geocoded address (15; HHS stopped updating the dataset in 2024);
    4. or by hand (`conditions.HAND_POINTS`, empty).

    The build stops if a hospital has no point.
  - **Which barrios are 0 is uncertain near the 15 hospitals at HHS's point.** For the 27 hospitals rule 1 places that HHS also places, HHS's point lies a median 0.7 km and up to 5.6 km from the building, and **in another barrio for 13 of them** (`notes.hospitals.hhs_point_in_another_barrio`). That is why OpenStreetMap comes first. The datasets carry a `caution` that says so; the dataset's card (Cautions) and the barrio legend show it, in Spanish too, and the dictionary entries list it under cautions. None of the 15 has an OpenStreetMap hospital near HHS's point with a matching name: some are not mapped, and some are mapped under another name.
  - From the barrio's **population-weighted point** (the average of its 2020 census blocks' internal points weighted by residents, from `population_blocks.json`; the barrio's internal point when no one lives there), not its centroid as the original WCRP index did. The point is snapped to the nearest road within 2 km that reaches a hospital.
  - Along `roads.bin` in both directions of every road, at the observatory's free-flow planning speeds (`roads.SPEED_KMH`): an estimate, shorter than most real trips. The road distance is the firmer figure.
  - **A barrio that holds a hospital is 0** (41 barrios).
  - **Vieques and Culebra** have no road link to a hospital: their 14 barrios and both municipios have **no value**, and the datasets say why (`noValue`: "No road path to a general hospital"). Puerto Rico's figure leaves out their 10,041 residents. Two uninhabited barrios have no value either: Isla de Mona e Islote Monito (no road) and Santa Rosa in Utuado (no road within 2 km of its internal point).
  - A municipio's and Puerto Rico's figures are the average of their barrios weighted by 2020 residents.

## What is kept and published

- Only the columns in `conditions.KEEP` reach the cache (`cache/conditions/`). No street address, telephone, e-mail, contact, owner, parent company or web link is requested or kept.
- Site names and points, and hospital points, stay in the local cache. The published files hold counts, shares and times only. Hospital names, addresses and certification numbers are never cached (`tests/test_conditions.py` checks this).
- **No map layer of EPA sites was added.** Point layers were optional. The map's startup scripts are at 248.1 of 250 KB after this change; a layer would add its switch, its Spanish and its loader there. It would also publish the names and points of chemical facilities, which the index inputs do not need. Francis can ask for it later: `facilities.js` would take it as a fifth layer.

## On the map

- **Economy tab.** Five new groups: Environment · Regulated sites (EPA), Environment · Water and air quality (EPA), Housing · Severe housing problems, Infrastructure · Street connectivity, Health care · Distance to a general hospital. The area profiles, the chat and the 3D columns get the municipal values too (`core/datasets.js`).
- **By barrio.** Each variable names its barrio file (`barrioFile`). A shaded layer of one of these datasets offers Settings > Area > barrio, like the survey datasets. `econ_level.js` then reads `conditions_barrio.json` (57 KB, 15.4 KB compressed) instead of `acs_barrio.json`. Its legend names the snapshot year, says when the values are estimates, and says why a barrio has no value. The CSV by area stays for the survey's own files.

## Spanish

- Labels and groups: `i18n_src/es/labels_conditions.json` (map and area profile).
- The barrio legend's two new sentences: `econ_level.json`.
- Dictionary summaries: `dictionary_plain.json`.
- **Held for review** (`held_for_review.json`), because the repository holds Spanish that names HUD: the two CHAS labels, the Spanish titles of both files and the two CHAS dictionary summaries. CHAS is HUD planning data, not grant money, so Francis or Compliance can release them as public housing was.

## Refresh

One unit, `conditions`, rebuilt on a runner (`rebuild.yml`): `python conditions.py --refresh`. It needs only published files (`barrios.geojson`, `geo/crosswalk.json`, `population_blocks.json`, `roads.bin`, `gazetteer.json`) and the sources' public services.

| Source | Check (`refresh/sources.json`) | Review |
|---|---|---|
| `epa_tri` | the newest year with a Puerto Rico file (asks for one byte: Envirofacts answers HEAD with an error; `freshness.py` `ok: "get"`) | automatic |
| `epa_frs` | the counts of active RMP facilities and final NPL sites | automatic |
| `epa_attains` | the layer's last edit date | automatic |
| `epa_greenbook` | how many Puerto Rico areas are in non-attainment for each pollutant | automatic |
| `epa_lmop` | the layer's last edit date | automatic |
| `hud_chas` | the release the eGIS item states (2016-2020) | a person (HUD program data) |
| `census_tiger_lines` | the newest TIGER/Line year | automatic |

Because `hud_chas` waits for a person, every rebuild of the unit does.

Every download goes through `conditions.get`, which waits and asks again on HTTP 429 (too many requests) and on a 5xx answer, a timeout or a dropped connection: the server's `Retry-After` when it gives one (at most 120 s), else 4, 8, 16, 32 and 60 s, as `build.py` waits on ArcGIS servers; it gives up after six tries. ArcGIS Online can also answer a busy server inside the JSON (`{"error": {"code": 429}}`): `conditions.arcgis` asks for that page again the same way. HUD's CHAS query is the one that met a 429 (review of PR #56). `hhs_hospital_capacity` is static (HHS stopped updating it). The CMS hospital list is checked by the `care` unit; this unit re-reads it whenever it rebuilds.

`python conditions.py --check` rebuilds both files from the cache with no network.

## Not built

- **Open dumps and other solid waste facilities** (transfer stations, recycling, composting). EPA lists municipal solid waste landfills only. The only machine-readable list found, DRNA's "Vertederos Activos 2014" on ArcGIS Online, states no licence. `wanted.json`: `open-dumps`, blocked, with the question for DRNA.
- **The newest CHAS window** (2018-2022, on HUD User, also for county subdivisions, which would avoid the tract-to-barrio estimate). HUD User refuses scripted downloads behind a bot check, and the observatory does not get around it. `wanted.json`: `chas-latest`, blocked, with the question for HUD.

## Weight

Measured with gzip level 6 on an LF copy (`budget.py`); before is `main` at 005f575.

| Page | Scripts before → after (KB) | Data before ready, before → after (KB) |
|---|---|---|
| Map | 247.2 → 248.1 of 250 | 171.2 → 172.6 (the catalog) |
| Area profile | 100.0 → 100.9 | 597.6 → 606.2 of 650 (`conditions_series.json`, 7.1 KB, and the catalog) |
| Dictionary | 28.5 → 28.5 | 679.3 → 691.6 of 720 (`dictionary.json`) |
| 3D, Housing | unchanged | unchanged |

- **Loaded on first use:** `conditions_barrio.json` (15.4 KB compressed), the first time one of these datasets is shaded by barrio; the Economy tab's series files grow by `conditions_series.json` (7.1 KB).
- **The catalog** stays under 200 KB raw (196.6 KB) because its index now writes `domains` as null when an entry has only its primary domain; without that it would have been 204.9 KB.

Slow 4G (`tests/browser/throttle.js`, two runs, Spanish; a headless Chrome of its own on port 9351, through the new `CDP_PORT` variable, because 9333 was busy):

| Page | Transferred, before → after (KB) | Ready, before → after (s) |
|---|---|---|
| Map | 795 and 746 → 800 and 751 | 4.8 and 4.8 → 4.9 and 4.8 |
| 3D | 2,691 and 2,832 → 2,691 and 2,832 | 16.6 and 17.0 → 16.8 and 16.9 |
| Area profile | 883 → 893 | 5.6 → 5.6 |
| Housing | 660 → 660 | 4.5 and 4.1 → 4.2 and 4.1 |
| Dictionary | 888 → 900 | 5.4 → 5.5 |

`throttle.js` exits 2 before and after for a reason this change does not touch: `routes.json` does not list `gateway_series.json` for the area profile (branch `fix/profile-route-gateway-series`).

## Checks

`tests/test_conditions.py`: the rules on small fixtures; that no kept column can hold contact details and the caches hold only those; the 901 barrios in the crosswalk's order; counts adding up from barrios to municipios; shares between 0 and 100; barrio estimates of CHAS adding up to the tracts; drive times (0 where a hospital is, finite and below 90 minutes elsewhere, no value only in Vieques, Culebra and uninhabited barrios, no speed above 95 km/h); no name, point or contact text in the published files; and the `wanted.json` rows of what was skipped.
