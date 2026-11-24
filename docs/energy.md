# Energy (HANDOFF decision 104)

The plan is `docs/energy-proposal-2026-11.md`, approved by the project lead on 2026-11-13 ("Approve, start step 1"), choices (a) to (g) as proposed. This page describes what is built.

## Step 1: the Power plants layer (`power_plants.py`)

**What it shows.** Every power plant of 1 MW or more in EIA's monthly generator inventory (EIA-860M), on the 2D map and the 3D view: Layers tab, Infrastructure and mobility, under the new subheading **Energy / Energía** (the sub-domain `infrastructure.energy`, decision 104 (e)). The link key is `l=plants`.

**Source.** EIA-860M, the newest monthly workbook that answers (US government data, public domain, no key), sheets `Operating_PR` and `Planned_PR`. `infrastructure_series.py` reads the same file for its counts by municipio; `power_plants.py` keeps its own cache (`cache/energy/eia860m_plants.pr.json`, the kept columns only) because `infrastructure_series.py` deletes the workbook after reading it.

**What is kept.** Plant id, plant name, technology, nameplate MW, battery MWh, status, operating year, planned month and year, point. **The owner (EIA's Entity Name) is never read** (decision 104 (b)). Every plant in the inventory has generators adding up to 1 MW or more: none is a home.

**One point per plant.** All of a plant's generators share EIA's point; the plant is placed in the municipio whose outline holds it (`facilities.Munis`). Technologies are grouped as the colours: oil, gas, coal, solar, wind, hydro, battery, landfill (`TECH`; an unknown technology stops the build). The main technology (`tech`) is the one with the most operating MW without batteries; a plant with only batteries is `battery`. `mw` is operating nameplate MW without batteries, with generators on standby (`sb`) and out of service (`out`) included, as EIA lists them. `plan` and `plan_ym` hold what is planned or under construction and the earliest expected month; a plant with nothing operating has `status: "planned"`.

**Drawing (`core/facilities.js`, kind `sized`).** Circle area in proportion to MW: radius 0.55 × √MW pixels, at least 3 (Aguirre's 1,534 MW is 21.5 px). Okabe-Ito colours, chosen to stay apart for readers with colour-vision deficiency: oil `#E69F00`, natural gas `#CC79A7`, coal `#000000`, solar `#F0E442`, wind `#56B4E9`, hydro `#009E73`, batteries `#0072B2`, landfill gas `#D55E00`, each with a dark grey ring so yellow shows on a light base map. The file is sorted largest first, so small circles are drawn on top (in 3D, `circle-sort-key`). A planned plant is hollow: dashed in 2D, with a coloured ring in 3D (MapLibre has no dashed circles). The legend under the switch lists only the technologies in the file, four sizes (10, 100, 500 and 1,500 MW) and the planned circle. The pop-up reads the plant from the loaded file by its EIA id, because MapLibre hands a 3D click its nested values (`by`, `plan`) as text.

**Figures (EIA-860M of September 2026).** 67 plants with an operating generator in 40 municipios: 6,436.1 MW without batteries, 397.7 MW of it renewable, 38.2 MW (12.6 MWh) of batteries, 101.6 MW on standby, 8.0 MW out of service; 1 planned plant (Bayamón, 2.2 MW) and 20 MW planned at Humacao Solar, 22.2 MW planned in all. File: 19 KB.

**What it leaves out.** Rooftop solar: each system is under 1 MW. LUMA counted 1,666 MW at 209,404 installations in September 2026 (its monthly metrics filed with the Energy Bureau), more than four times the renewable capacity of these plants; step 4 brings it in by municipio and district. Retired generators (EIA's `Retired_PR`) are not drawn yet.

**Refresh.** Unit `infrastructure` of `refresh/sources.json` runs `python power_plants.py --refresh` after `infrastructure_series.py`; the EIA-860M probe triggers it when a new month answers. `python power_plants.py --check` rebuilds from the cache and compares.

**Where else it shows.** The chat switches the layer on for "power plants", "plantas de energía" and similar words (`chat.js` `CH_CONTEXT`, both views); Study areas › Download what's inside offers the plants; the dictionary entry is `layers.plants`; the counts by municipio (`infrastructure.power_*`) moved to the Energy sub-domain, and their method now says the points are published.

**Glossary.** EIA-860M, Standby (generator), Megawatt-hour (MWh), with Nameplate capacity (MW) already there.

**Tests.** `tests/test_power_plants.py` (the published file: fields, no owner, points, totals, order) and `tests/facilities_plants.test.js` (sizes, colours, pop-up, legend, note).

## Step 2: the Transmission lines layer (`power_lines.py`)

**What it shows.** OpenStreetMap's high-voltage lines on the 2D map and the 3D view, under Energy, above Power plants in the menu and drawn under the plants (2D pane `facLines`, z 394; 3D before `fac-plants`). Link key `l=powerlines`.

**Source.** OpenStreetMap through the Overpass API (ODbL), ways tagged `power=line` or `power=cable`, and `power=substation` ways and nodes. The Overpass servers refuse GitHub's runners, so the file is renewed by hand each quarter with the other OpenStreetMap files (unit `osm` of `refresh/sources.json`, `python power_lines.py --refresh`); the raw answer is cached in `cache/energy/osm_power.json`.

**Decision 104 (c): the shape, not the detail.** A way's voltage is the highest value of its `voltage` tag; only 230, 115 and 38 kV are drawn. Ways of the same voltage and kind (line or cable) are joined (shapely `linemerge`) and simplified with Douglas-Peucker at 0.0009° (about 100 m). No name, operator, circuit number or tower is kept, and **no substation is drawn**: the 549 substations mapped are counted by municipio in the file's notes (the point inside the outline, or the centre of a mapped outline).

**Drawing (`core/facilities.js`, `line` + `byProp`).** Purples that stay apart from the plants' colours, and width by voltage for readers who cannot tell the shades apart: 230 kV `#4a1486` 3.4 px, 115 kV `#7b6bb5` 2.2 px, 38 kV `#a39fc9` 1.3 px; cables dashed in 2D (MapLibre's dash cannot vary by feature). The pop-up gives the voltage, the length mapped at that voltage and, for 38 kV, how much of the network is mapped.

**Figures (OpenStreetMap of 2026-11-14).** 230 kV 751.8 km (one connected network), 115 kV 900.0 km, 38 kV 1,052.3 km, 41.6 km of it cable; 281.0 km with no voltage tag left out; 2,917 points after simplifying; file 62 KB (19 KB compressed). Against the 2019 Integrated Resource Plan (665, 1,130 and 2,214 km of circuits) OpenStreetMap has the whole 230 kV network, about 82% of 115 kV and about half of 38 kV; circuit length counts each circuit on a shared tower line.

**Not yet.** The grid's exposure to hazards (km of line in FEMA flood areas, landslide classes and under sea level rise) goes on the Knowledge Area page (step 3), which reads this file.

**Glossary.** Transmission line, Kilovolt (kV), Substation. **Tests.** `tests/test_power_lines.py`, `tests/facilities_lines.test.js`.

## Step 3: the Knowledge Area page "Energy in Puerto Rico" (`energy_series.py`, `energy.html`)

**What it shows.** Puerto Rico now (plant capacity, rooftop solar, batteries, the renewable share, the residential price); where electricity comes from every full year since 2010; rooftop solar every month against the renewable plants, and batteries since 2021; batteries, electricity sales and smart meters by municipio; rooftop solar by LUMA's 34 commercial districts; SAIDI every month and by LUMA's 16 technical districts; the residential price against the United States; the transmission lines and plants inside FEMA flood hazard areas. Tab **Energy / Energía** (`energy`), published with the "In review" marker and the AI sentence, like the other new areas.

**Sources (`data/energy.json`, 33 KB).** LUMA's Exhibit 2 of the distributed generation data (case NEPR-MI-2019-0016) and monthly metrics workbook (case NEPR-MI-2019-0007), read on the Energy Bureau's site (decision 104 (d)); `energy_series.py --refresh` reads the case pages for the newest file names (kept in `cache/energy/sources.json`). EIA-861M sales to ultimate customers (2021 on). The observatory's `power_plants.geojson`, `power_lines.geojson`, `flood.geojson` and `municipios.geojson`. Refresh unit `energy` (sources `luma_bureau`, `eia_861m`, monthly).

**Checks on LUMA's file.** Exhibit 2 has two blocks of solar, wind and landfill-gas columns. The second (production by fuel) holds other quantities before October 2017 (in 73 months it differs from the first; its total includes them in another order), while the first (contracted renewable production) always adds up to its own total, so the first is read; the fossil fuels, hydro and rooftop exports come from the production block. 2025 checks against EIA-923: renewable plants 2.8% of production without rooftop exports here, 3.1% in EIA-923 (plants of 1 MW or more). LUMA's metrics leave the generation and all-in SAIDI rows empty, so the monthly SAIDI is transmission and distribution only; the page quotes EIA-861's 2025 all-events figure (3,547 minutes, stored with its source note). Smart-meter shares are fractions in LUMA's file and "N/A" where the rollout has not reached: shown as percent, blank where N/A.

**Figures (2025).** Renewables 7.5% of production with rooftop exports, 2.8% from the plants alone; 13 of 67 plants (1,449.0 of 6,436.1 MW) inside the 1% flood area; lines inside it: 230 kV 68.6 km, 115 kV 89.4 km, 38 kV 162.5 km (simplified lines). Sea level rise and landslides are not counted (the GIS library `exposure.py` uses is not in the test environment): a later step.

**Generator.** `docs/analysis/energy-2026-11/make_page.py` writes `site/energy.html` and `i18n_src/es/energy.json`; the page script is `site/js/energy_page.js` (charts as inline SVG, sortable tables). Glossary: SAIDI, net metering, renewable portfolio standard, smart meter (AMI), gigawatt-hour, V zone. Tests: `tests/test_energy_series.py`, `tests/energy_page.test.js`. Every area page's icon font gained `bolt` (the tabs show each area's icon).

## Step 4: energy datasets by municipio and barrio (`energy_municipios.py`)

**What it adds.** Six datasets in the Analysis tab, the area profiles, the chat and the dictionary (group **Energy by municipio**, sub-domain `infrastructure.energy`), in two Analysis groups:

- **Infrastructure · Energy (LUMA)**, every year from 2021, by municipio: home and business batteries (installations), their storage in MWh, electricity sales in GWh (calendar years with all twelve months: 2022 to 2025), and the share of customers with smart meters (AMI). Each year is December; the current year is the latest month in LUMA's file (September 2026 in the October 2026 workbook).
- **Infrastructure · Energy (ACS)**, five-year windows 2017-2021 to 2020-2024, by municipio and barrio, with margins of error: households paying $250 or more a month for electricity, as a share of those paying for it separately and as a count (ACS B25132, cells 009 over 003). The share's margin uses the Census Bureau's formula for a proportion.

**Files.** `energy_series.json` (municipios and Puerto Rico) and `energy_barrio.json` (901 barrios). Both are read from caches the step 3 script keeps (`cache/energy/`) and from the ACS summary files; `build.py` and refresh unit `energy` run the script after `energy_series.py`.

**Choices.** LUMA's San Juan, Río Piedras and Santurce areas are added together for batteries and sales (the municipio of San Juan). The smart-meter share is LUMA's San Juan area's, as LUMA gives shares, not counts. Shares LUMA marks "N/A" (the meters have not reached the area) are blank, not zero, and the Puerto Rico value is LUMA's own island figure. Rooftop solar by municipio is not here: LUMA gives it by commercial district only (the Knowledge Area page shows those 34 districts). Sales are not divided by housing units (`noPerHU`): they include businesses and industry.

**Figures.** Batteries 189,459 (September 2026), 3,154.7 MWh; sales 16,337.5 GWh in 2025; smart meters 20.4% of customers (September 2026); households paying $250 or more 11.8% ± 0.3 in 2020-2024, up from 7.3% in 2017-2021.

**Dictionary page.** The six entries pushed the dictionary page's first data past its budget, so `registry.json` (the geography filter, the file count and the files summary) now loads right after the first paint instead of before the page is ready (`later` in `routes.json`; `loadRegistry()` in `dictionary.js`). A link that names a geography level waits for it. The area profile's script budget is now 122 KB (`docs/performance.md`).

## Built solar plants that EIA does not list yet (`energy_src/plants_added.json`, 2026-11-17)

The project lead on 2026-11-17: the energy map was missing some solar projects. EIA-860M lists a plant only once it is in commercial operation (or reported as planned), so in its September 2026 file Puerto Rico's renewable plants were 397.7 MW, and the largest new solar farms were missing.

**What was found.** OpenStreetMap had 48 solar plant outlines in Puerto Rico. Four groups of large unnamed outlines, all traced from Esri World Imagery in 2025 and 2026, were not in EIA. Esri's Wayback imagery dates each one, and the Energy Bureau's filings and the press name them:

| Plant | Where (outline) | Solar | Batteries | Status | Source |
|---|---|---|---|---|---|
| CIRO One Salinas | 108.9 ha north of Salinas, built June 2024 to September 2025 | 90 MW | 51.5 MW, 206 MWh | Connected by LUMA in January 2026; commercial operation date not yet set (Energy Bureau, 10 August 2026) | PV Tech, 13 January 2026; NEPR-AP-2021-0001 |
| Marahú, Salinas site | 164.4 ha at the Salinas–Guayama line, built September 2025 to October 2026 | 120 MW | 175 MW, four hours | Built, not connected (5 October 2026) | San Juan Daily Star; Telemundo PR, 24 September 2025 |
| Marahú, Jobos site | 113.7 ha by the AES plant in Jobos, Guayama, same period | 80 MW | 110 MW, four hours | Built, not connected (5 October 2026) | same |
| Yabucoa Solar | 33.5 ha south of the Yabucoa fuel terminal, outlined September 2026 | 32.1 MW | none counted | Construction complete, first synchronization scheduled for September 2026 | LUMA's August 2026 report, NEPR-MI-2024-0005 |

Together: 322.1 MW of solar and 336.5 MW of batteries, about four-fifths of the 397.7 MW of renewable plants EIA lists.

**Choices.**
- The points come from the outlines (area-weighted centre), never from the GEM wiki (its Puerto Rico points are island-centre approximations, its statuses are out of date, and its text is CC BY-NC-SA).
- AES gives 120 MW for its "Salinas" site and 80 MW for Jobos. The larger of the two new farms (164 ha) is taken as the Salinas site, although most of it lies inside Guayama's census outline, so its pop-up says Guayama. The imagery shows no other new farm in Salinas.
- Yabucoa Solar: Esri's public imagery still predates the panels. The Energy Bureau's report says construction is complete, and the OpenStreetMap outline is at the site.
- They are drawn dashed, with status `built` (not in commercial operation). They stay out of the notes' totals (plants, MW, renewable MW), which remain EIA's. The pop-up gives the stage, the month and the source, and no owner.
- Each entry has an `eia_match` pattern. When EIA lists a plant whose name matches, `power_plants.py` drops the entry and logs it, so nothing is counted twice.
- Not drawn: utility-scale solar that is contracted but not built (the rest of procurement tranches 1, 2 and 4, such as Guayama Solar, Xzerta-Tec Solar I with a commercial operation date of December 2028, the Go Green parks in Yabucoa and Naguabo, San Juan Solar, Marisol Power, CS-UR Juncos, Lajas and Solaner in San Germán). The filings checked give no site.

**Also changed.** The Energy page's "Power plants" card adds "Another 322.1 MW of solar is built, not yet in commercial operation" (`energy.json` `capacity.built_mw`). `power_plants.geojson` now carries OpenStreetMap's attribution, so its licence class is open with conditions (ODbL). Tests: `tests/test_power_plants.py`, `tests/facilities_plants.test.js`.

**To keep it current.** Check the list when EIA publishes a new month, and when the Energy Bureau's monthly collaborative report (NEPR-MI-2024-0005) changes a project's status. Update `stage`, `as_of` and the source, or remove an entry once EIA lists the plant (the build does this by itself).

## Next steps (each its own pull request, on the project lead's word)

5. Solar and wind potential.
6. Outages (EAGLE-I, by LUMA region).
