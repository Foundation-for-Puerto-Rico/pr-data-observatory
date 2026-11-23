# Automatic data updates

How the observatory keeps its data current without a person running builds. Part 1 is the bot that publishes; part 2 is when each source is checked and rebuilt.

## 1. The bot: a GitHub App

`main` takes changes only through pull requests, and a pull request can merge only when its **checks** pass (the ruleset on `main`). The workflows' built-in token cannot open pull requests in the Foundation-for-Puerto-Rico organization: the organization does not allow it. So the scheduled jobs act as a **GitHub App** that belongs to FPR:

1. A job refreshes a source and runs its data checks.
2. If the data changed, it pushes a `bot/...` branch and opens a pull request **as the App**.
3. That pull request starts `tests.yml` like anyone's, and the job turns on **auto-merge**: GitHub merges it only when the required "checks" pass. If they fail, it stays open for a person.
4. The merge publishes the site (`pages.yml` runs on every push to `main` that touches `site/`).

Until the App exists, the jobs push their branch and say in the run summary that a pull request must be opened by hand.

### Setting up the App (an organization owner)

Creating an App for the organization and installing it on a repository needs an **owner of the Foundation-for-Puerto-Rico organization**. It takes about ten minutes.

1. **Create the App.** Organization settings → Developer settings → GitHub Apps → New GitHub App.
   - Name: for example `pr-data-observatory-bot`. Homepage URL: the repository's address.
   - Webhook: **untick Active** (the App receives no events).
   - Repository permissions:
     - Contents: **Read and write** (push the `bot/...` branches)
     - Pull requests: **Read and write** (open the pull request, turn on auto-merge)
     - Metadata: Read-only (always required)
     - Everything else: No access.
   - Where can this App be installed: **Only on this account**.
2. **Install it** on the organization, choosing **Only select repositories → pr-digital-twin**.
3. **Generate a private key** on the App's page (Private keys → Generate). The browser downloads a `.pem` file. Keep it private: whoever holds it can act as the App.
4. **Give the repository the App's ID and key.** Repository settings → Secrets and variables → Actions:
   - Variables tab → New repository variable: `BOT_APP_ID` = the App ID shown at the top of the App's page (a number; not secret).
   - Secrets tab → New repository secret: `BOT_APP_PRIVATE_KEY` = the whole content of the `.pem` file, from `-----BEGIN` to `END ... KEY-----`. Then delete the downloaded file.
5. **Auto-merge** is already allowed on the repository (Settings → General → Pull Requests → "Allow auto-merge", turned on 2026-10-15).
6. **Try it:** Actions → Refresh transit data → Run workflow. If the feeds changed, a pull request from the App appears, the checks run, and it merges itself.

Nobody needs to share the key with a person or an assistant: it goes straight from the App's page into the repository secret.

**Why an App and not a personal token.** A personal token acts as a person, stops working when that person leaves or the token expires, and usually reaches every repository the person can. An App belongs to the organization, reaches only this repository, can do only the two things above, and its token lasts one hour per run.

**Turning it off.** Delete the variable `BOT_APP_ID` (the jobs go back to pushing branches only), or uninstall the App.

## 2. When each source is checked: check often, rebuild rarely

The observatory reads about 30 sources that publish on very different rhythms. Transit timetables can change any night, unemployment figures every month, the Census ACS once a year, and the 2020 census never. One schedule for all of them would either waste hours re-downloading gigabytes that did not change, or leave new releases waiting for weeks. So the work is split in two.

1. **A cheap daily check.** `freshness.py` runs each morning from `freshness.yml`. For each source that is due, it asks whether the source has published something new, without downloading the data. It looks at a file's date or size, an API's latest date or count, or whether next year's file exists yet.
   - It compares the answer with the one it got last time. The answers are kept between runs in the Actions cache.
   - The first answer for a source is its baseline, not a change.
2. **A rebuild only for what changed.** `rebuild.yml` runs when a source has a new release and a clean GitHub runner can rebuild it in minutes. The daily check starts it for that source's script. The rebuild then:
   - keeps the result only if the data really changed (a new build date alone does not count);
   - moves the declared last year forward in `dictionary_src/datasets.json` when a file now reaches a later year;
   - runs the data contract;
   - opens a pull request as the App.

### Who approves

- **A rebuild merges itself only when every source its script reads is routine** (`"review": "auto"` in `refresh/sources.json`). A rebuild re-reads all the sources of its script, not only the one that changed, so a new year of one source could otherwise come along with a routine update of another.
- **Any rebuild that moves a dataset's last year waits for a person**, whatever the sources say: a new year is a new vintage.
- **A rebuild that changes a file listed under `"human_if_changed"` waits for a person**, whatever the sources say. The conditions unit lists the WCRP index files: its run ends with `python wcrp_rvi.py`, which rebuilds them from the new `conditions_barrio.json`, and WCRP content is always reviewed (`docs/wcrp.md`, "Refresh").
- Today every unit a runner rebuilds reads at least one source that is reviewed, so **every automatic rebuild opens a `[review]` pull request**. Only the nightly transit refresh merges by itself. A unit becomes automatic when all of its sources are routine.
- **Sources that are always reviewed.** These include:
  - a new annual vintage that moves headline figures (ACS, population estimates, QCEW jobs);
  - sources whose licence is under review (HRSA, the Police reports);
  - **public money** (USAspending, OpenFEMA), whose headline is held for Compliance (HANDOFF decision 21).

  Their pull request title starts with `[review]`, and a person merges it after reading it. When a newer rebuild of the same unit comes before the older pull request is merged, the newer one closes and replaces it.

### What a person does

The issue **"Data freshness"** always holds the latest report. It gets a comment, which notifies whoever watches the issue, when something is new or a check starts failing. A check that keeps failing (for example BLS without its contact) stays in the report each day but notifies only once. For each new release, the report says what happens next:

- **Rebuilt automatically:** nothing to do. For a `[review]` pull request, read it and merge it.
- **Rebuild locally:** a runner cannot do it, and the report gives the command. The rebuild then goes through a normal pull request. This happens when:
  - the source is too big for a runner (the ACS detail tables, Overture places, the flood zones and the land-use plan add up to about 3 GB);
  - or a runner cannot reach it (OpenStreetMap's Overpass, the Police reports' server).
- **Needs a code edit first:** a few scripts name their years in the code (for example `small_area.VINTAGES`). The report names the edit.

### The schedule

A source is checked daily during the months a release is expected, and otherwise every so many days. The table is generated from `refresh/sources.json` with `python freshness.py --doc`, and a test fails when the two differ.

<!-- schedule:start (python freshness.py --doc) -->
| Source | Checked | Daily in | Rebuilt | Merged |
|---|---|---|---|---|
| ATI GTFS feed | daily | — | nightly transit job | when the checks pass |
| Municipal GTFS feeds (registry) | daily | — | nightly transit job | when the checks pass |
| FTA National Transit Database list | every 30 days | — | nightly transit job after a code edit | after a person reviews it |
| Overture Maps places | every 7 days | — | by hand (local) | after a person reviews it |
| FEMA flood hazard areas | every 7 days | — | by hand (local) | after a person reviews it |
| USGS protected areas (PAD-US) | every 30 days | — | by hand (local) | after a person reviews it |
| FAA airports (NTAD) | every 90 days | — | by hand (local) | after a person reviews it |
| NOAA hurricane tracks (HURDAT2) | every 30 days | Mar, Apr, May, Jun, Sep | by hand (local) | after a person reviews it |
| Census ACS 5-year | every 30 days | Dec, Jan, Feb | by hand (local) after a code edit | after a person reviews it |
| Census population estimates (PEP) | every 30 days | May, Jun, Jul | by hand (local) | after a person reviews it |
| Census Community Resilience Estimates | every 30 days | Apr, May, Jun | automatic after a code edit | after a person reviews it |
| HRSA shortage areas | every 7 days | — | automatic | after a person reviews it |
| HRSA health center sites | every 7 days | — | by hand (local) | after a person reviews it |
| CMS facility lists | every 7 days | — | by hand (local) | after a person reviews it |
| CMS Medicare enrollment | every 30 days | Jan, Feb, Mar, Apr | automatic | after a person reviews it |
| BLS QCEW jobs and pay | every 30 days | Aug, Sep | by hand (local) | after a person reviews it |
| BLS unemployment (LAUS) | every 30 days | Mar, Apr | by hand (local) | after a person reviews it |
| BLS consumer prices (CPI) | every 30 days | Jan | by hand (local) | after a person reviews it |
| USAspending federal awards | every 30 days | Nov | by hand (local) | after a person reviews it |
| OpenFEMA assistance | every 30 days | — | by hand (local) | after a person reviews it |
| Federal Audit Clearinghouse single audits | every 30 days | — | by hand (local) | after a person reviews it |
| CDFI Fund New Markets Tax Credit public data release | every 30 days | Jul, Aug | by hand (local) | after a person reviews it |
| Police Type I crimes (December reports) | every 30 days | Jan, Feb, Mar | by hand (local) | after a person reviews it |
| NCES schools (Urban Institute mirror) | every 30 days | — | by hand (local) | after a person reviews it |
| IPEDS colleges (Urban Institute mirror) | with the schools | — | by hand (local) | after a person reviews it |
| NCES IPEDS completions | every 30 days | — | by hand (local) | after a person reviews it |
| Civil Rights Data Collection (Urban Institute portal) | every 90 days | — | by hand (local) | after a person reviews it |
| EDFacts state assessments (Urban Institute portal) | every 90 days | — | by hand (local) | after a person reviews it |
| EPA drinking water systems (ECHO) | every 7 days | Jan, Apr, Jul, Oct | automatic | when the checks pass |
| EPA wastewater discharge permits (ECHO) | every 7 days | Jan, Apr, Jul, Oct | automatic | when the checks pass |
| EPA air pollution sources (ECHO) | every 7 days | Jan, Apr, Jul, Oct | automatic | when the checks pass |
| EPA hazardous waste handlers (ECHO) | every 7 days | Jan, Apr, Jul, Oct | automatic | when the checks pass |
| EPA inspections and enforcement actions (ECHO) | every 7 days | Jan, Apr, Jul, Oct | automatic | when the checks pass |
| EIA power plants (860M): counts by municipio and the Power plants layer | every 7 days | — | automatic | when the checks pass |
| FHWA bridges (NBI) | every 30 days | Apr, May, Jun, Jul | automatic | after a person reviews it |
| FEMA National Risk Index | every 30 days | — | automatic | after a person reviews it |
| USFWS wetlands | every 90 days | — | automatic | after a person reviews it |
| USGS earthquakes | every 30 days | Jan | automatic | after a person reviews it |
| NOAA sea level rise | every 90 days | — | by hand (local) | after a person reviews it |
| NOAA NHC storm surge maps (SLOSH MOM, Puerto Rico) | every 90 days | — | by hand (local) | after a person reviews it |
| OpenStreetMap roads and places (Geofabrik) | every 30 days | — | by hand (local) | after a person reviews it |
| BTS airline passengers (T-100) | every 30 days | — | automatic | when the checks pass |
| FAA airport enplanements | every 30 days | Sep, Oct, Nov | automatic | after a person reviews it |
| BTS ferry census (NCFO) | every 30 days | — | automatic after a code edit | after a person reviews it |
| WCRP Risk and Vulnerability Indicators (ArcGIS, PlanningCDBG) | every 30 days | — | by hand (local) | after a person reviews it |
| HUD public housing developments | every 7 days | — | automatic | after a person reviews it |
| HUD LIHTC database (tax credit housing projects) | every 30 days | May, Jun | by hand (local) | after a person reviews it |
| USGS structures (fire and EMS stations) | every 30 days | — | automatic | when the checks pass |
| USAC E-Rate entities (libraries) | every 7 days | — | automatic | when the checks pass |
| IRS exempt organizations (EO BMF, Puerto Rico) | every 14 days | — | automatic | when the checks pass |
| EPA Toxics Release Inventory (Puerto Rico file) | every 30 days | Jul, Aug, Sep, Oct | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| EPA Facility Registry Service (RMP and NPL) | every 30 days | — | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| EPA ATTAINS assessment units (303(d) list) | every 30 days | — | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| EPA Green Book non-attainment areas (lead, sulfur dioxide) | every 30 days | — | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| EPA LMOP landfills | every 30 days | — | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| HUD CHAS by census tract (eGIS) | every 14 days | — | automatic | after a person reviews it |
| Census TIGER/Line EDGES (Puerto Rico) | every 30 days | Sep, Oct, Nov | automatic | when the checks pass (a person reviews it when `wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json` change) |
| NPS National Register of Historic Places (public locations) | every 30 days | — | automatic | when the checks pass |
| SAMHSA National Directories of treatment facilities (N-SUMHSS) | every 14 days | Feb, Mar, Apr | automatic | when the checks pass |
| USGS landslide susceptibility map of Puerto Rico (first author's tile copy at UPRM; the USGS release's DOI record) | every 30 days | — | automatic | after a person reviews it |
| USGS Landsat 8 and 9 Collection 2 Level-2 surface temperature (Planetary Computer): the summer window of surface heat | every 30 days | — | automatic | after a person reviews it |
| Copernicus Sentinel-2 Level-2A, Collection 1 (Earth Search on AWS): the summer window of vegetation greenness | every 30 days | — | automatic | after a person reviews it |
| Overture Maps buildings theme: the newest monthly release | every 90 days | — | automatic | after a person reviews it |
| NASA ECOSTRESS ECO_L2T_LSTE version 2 (LP DAAC, Earthdata login): the summer window of night surface heat | every 30 days | — | automatic | after a person reviews it |
| USGS reservoir levels, river flow, groundwater levels and rainfall (daily values and usual levels) | every 7 days | — | automatic | when the checks pass |
| NWS flood stages of the river gauges (National Water Prediction Service) | every 7 days | — | automatic | when the checks pass |
| NASA Black Marble VNP46A3 monthly night-time lights (LAADS DAAC) | every 30 days | — | automatic | after a person reviews it |
| FCC Broadband Data Collection: fixed broadband availability, June release | every 30 days | — | automatic | after a person reviews it |
| NASA FIRMS active fire detections (VIIRS on NOAA-20): yearly files and the last 12 months | every 30 days | — | automatic | after a person reviews it |
| OGP budget data sheets (Sábana) | every 7 days | Mar, Apr, May, Jun, Jul | automatic | after a person reviews it |
| Planning Board four-year investment program (PICA) | every 14 days | Jun, Jul, Aug, Sep | by hand (local) | after a person reviews it |
| DTRH consumer price index of Puerto Rico | every 7 days | — | by hand (local) | after a person reviews it |
| Cleveland Fed inflation expectations | every 30 days | — | by hand (local) | after a person reviews it |
| Philadelphia Fed Survey of Professional Forecasters | every 30 days | Feb, May, Aug, Nov | by hand (local) | after a person reviews it |
| Census ACS 1-year (median household income) | every 30 days | Sep, Oct | by hand (local) | after a person reviews it |
| US Treasury, Qualified Opportunity Zones: 2027 designations and eligible tracts (Data Transparency) | every 30 days | — | automatic | after a person reviews it |
| Census Bureau, County-to-County Commuting Flows (American Community Survey, every five years) | every 90 days | — | automatic | after a person reviews it |
| Instituto de Estadísticas de Puerto Rico, Mapa de rutas de porteadores públicos (ACT) | every 90 days | — | automatic | after a person reviews it |
| FHWA Highway Performance Monitoring System, Puerto Rico full join (geo.dot.gov) | every 30 days | — | automatic | after a person reviews it |
| NHTSA FARS, Puerto Rico file of the newest year | every 30 days | — | automatic | after a person reviews it |
| LUMA filings at the Energy Bureau (distributed generation data, monthly metrics) and EIA-861M | every 7 days | — | automatic | when the checks pass |
| EIA residential sales and revenue (861M) | every 7 days | — | automatic | when the checks pass |
| DOE Alternative Fuels Data Center stations (NTAD copy): the Public EV charging stations layer | every 30 days | — | automatic | when the checks pass |
| FHWA National Tunnel Inventory (NTAD): the tunnels on the Bridges and tunnels layer | every 90 days | — | automatic | when the checks pass |
| FDIC Summary of Deposits, Puerto Rico offices | every 30 days | Sep, Oct | automatic | after a person reviews it |
| HMDA Data Browser, Puerto Rico | every 30 days | Mar, Apr | automatic after a code edit | after a person reviews it |
| US Drought Monitor, Puerto Rico | every 7 days | — | automatic | when the checks pass |
| CMS NPPES monthly full file | every 30 days | — | by hand (local) | after a person reviews it |
<!-- schedule:end -->

Some sources are never checked, because they do not change or are not downloaded: the 2010 and 2020 censuses, the 2015 land-use plan, hand-kept lists, map tiles and libraries. They are listed under `static` in `refresh/sources.json`, each with the reason.

### Settings the checks use

- **`FRESHNESS_CONTACT`** (optional repository variable): an FPR role mailbox, such as a data team address, never a person's. The Bureau of Labor Statistics refuses requests that do not name a contact, so the unemployment and CPI checks fail until it is set.
- **`BOT_APP_ID` and `BOT_APP_PRIVATE_KEY`:** the App of part 1. Without them, rebuilds push their branch and ask for the pull request to be opened by hand.

### Running it by hand

- Actions → **Data freshness** → Run workflow. Tick "all" to run every check now.
- Actions → **Rebuild a data source** → Run workflow, and choose the unit.
- On a computer: `python freshness.py --all`. The answers go to `.freshness/`, which git ignores.

### Tested on a clean runner

Each unit was rebuilt on 2026-10-15 in an empty copy of the repository, as a GitHub runner would run it. Medicare (7 s), health (10 s), infrastructure (113 s) and environment (152 s) work. Infrastructure and environment gave the same data as the published files: only the build date differed, and for environment the month of the download, which the comparison sets aside. So a rebuild would have published nothing. Health found one more HRSA site, which is a real change and waits for a review.

Two units stay local:
- **Education:** the Urban Institute's API timed out after 13 minutes of downloading every school year.
- **Care:** it needs a file of census blocks that only the full build makes.

### Known limits

- **HRSA:** it remakes its files every day, so the file size is the only steady sign of a change. A change in content that keeps the same size is missed until the next size change.
- **OpenStreetMap:** it changes every day, so it is renewed by hand once a quarter instead of on a signal.
- **A failed rebuild:** the daily check records the new answer before the rebuild runs, so a rebuild that fails is not started again by itself. The new release stays in the issue, and the failed run shows in Actions; run "Rebuild a data source" by hand.
- **Lost answers:** a check compares with its last answer. If the Actions cache is lost (it is deleted after 7 days unused), the next run takes new baselines and reports nothing that day.
