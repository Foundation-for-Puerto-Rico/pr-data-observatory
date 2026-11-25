# Traffic on the main roads

HANDOFF decision 105, step 2 (2026-11-13). The project lead approved step 2 of `docs/transportation-upgrade-2026-11.md` ("Sí, paso 2"): traffic on the roads, from the Federal Highway Administration's Highway Performance Monitoring System (HPMS), and the traffic on the roads each simulated connection between municipios follows.

## Files

| File | What | Built by |
|---|---|---|
| `site/data/traffic_roads.geojson` | The map layer `traffic`: 3,829 stretches, 5,396 km of arterials and major collectors with a count, wider and darker where more vehicles pass | `traffic.py` |
| `site/data/traffic_series.json` | Six figures for the 78 municipios and Puerto Rico (Analysis tab, group Infrastructure · Traffic) | `traffic.py` |
| `site/data/transit_links.json`, `simulated_links.geojson` | Each simulated connection gains `aadt_med`, `aadt_max` and `counted_pct` | `transit_links.py` (reads the traffic layer) |

`python traffic.py` downloads what is missing into `cache/traffic/` (about 160 requests, 2 minutes) and builds in about 20 seconds; `--refresh` looks for a newer `HPMS_FULL_PR_<year>` service and downloads again; `--check` rebuilds from the cache. Run `transit_links.py` after it, then `make_page.py` of the connections page and `i18n.py`. `build.py` runs both in that order; the refresh unit `traffic` runs both.

## Source (no key)

FHWA, Office of Highway Policy Information, **HPMS Full Join, Puerto Rico, data year 2025**, on geo.dot.gov (`HPMS_FULL_PR_2025`): 262,462 road sections, 252,455 with an annual average daily traffic (AADT). Collected by the DTOP in 2025 and submitted in 2026. US Government work. The Route analysis keeps its own 2024 snapshot (BTS `HPMS_National_Current`) until it is redone.

Fields used (HPMS Field Manual): `aadt` and `aadt_vd` (its date), `aadt_single_unit`, `aadt_combination`, `f_system` (functional class), `facility_type`, `section_length` (miles), `through_lanes`, `speed_limit` (mph), `iri` (International Roughness Index, inches per mile), `county_id`.

Not used: `aadt_vt`. Puerto Rico fills it with `C` or `D`, and the Field Manual leaves the value text to each state, so its meaning is not documented. Nearly every local-street section is `D` with one of a handful of repeated low values (10, 17, 25, 50 vehicles a day), which is why the layer leaves local streets out.

## How each figure is made

- **Each road once.** Facility types 1 (one-way) and 2 (two-way). Type 6 is the non-inventory direction of a divided road and repeats its line; type 4 is a ramp. Both are left out.
- **The layer.** Classes 1 to 5 (interstate, other freeway or expressway, other principal arterial, minor arterial, major collector) with a count. Consecutive sections of one route and direction with the same count, lanes, speed limit and date are joined into one stretch, and lines are simplified to 12 m. Color by class of vehicles a day: under 2,000; 2,000-5,000; 5,000-10,000; 10,000-20,000; 20,000-40,000; 40,000 or more (ColorBrewer YlOrBr). Width by the square root of the count, up to 80,000.
- **Vehicle-km a day** (`traffic_vkt`): AADT x length, every class (local streets with their estimates). Puerto Rico: 75,159,323 a day, about 27,400 million a year. Cross-check: FHWA's Highway Statistics table VM-2 gives Puerto Rico 15,449 million vehicle-miles for 2024 (about 24,860 million vehicle-km; https://www.fhwa.dot.gov/policyinformation/statistics/2024/vm2.cfm), and notes that Puerto Rico changed how it estimates summary travel that year; the 2025 sum here is about 10% higher, a different year added section by section.
- **Per resident** (`traffic_vkt_pc`): over the 2020 Census residents (22.9 for Puerto Rico). It counts every vehicle on a municipio's roads, so it is high where through traffic is heavy (Salinas, Santa Isabel, Cayey on PR-52).
- **Main roads, km** (`traffic_main_km`): classes 1 to 5: 5,418.9 km.
- **Busiest road** (`traffic_max_aadt`): the highest count on a class 1-5 section: 266,200 vehicles a day on PR-18 in San Juan.
- **Trucks** (`traffic_truck_pct`): single-unit plus combination trucks over all vehicles, in vehicle-km, on class 1-5 sections that report trucks: 5.2% for Puerto Rico.
- **Rough pavement** (`traffic_poor_pct`): km of class 1-5 with an IRI measurement over 170 inches per mile (FHWA's poor threshold, 23 CFR 490.313) over the measured km: 77.4%. The median IRI is 142 on interstates and 262 to 269 on minor arterials and major collectors, so the share follows the data. It is roughness alone; FHWA's full pavement rating also uses cracking and rutting or faulting.
- **Traffic along a simulated connection.** Points every 100 m along each line take the AADT of the counted road within 25 m. `aadt_med` is the median, `aadt_max` the highest, `counted_pct` the share of points on a counted road. The median over the 181 connections is 31,898 vehicles a day. A point next to a crossing road can take that road's count, which can lift `aadt_max`; the median is little affected.

## Checks

`tests/test_traffic.py`: color classes at their edges; consecutive sections with one count join and a gap breaks them; the truck share is weighted by length and left out when no section reports trucks; the series has 79 places and the municipios add up to Puerto Rico; the layer matches its notes and classes and is sorted busiest last; the connections carry their traffic; `--check` where the pages are cached. `tests/transit_links_page.test.js`: the layer's style, solid legend, pop-up and hover text.

Sanity checks made on 2026-11-13: the counts of sections by class and of sections with AADT match the service's own statistics (`returnCountOnly` and `outStatistics`); the low counts on arterials and collectors (1,967 sections under 500) are almost all rural and municipal collectors (for example PR-988, 48 vehicles a day); the IRI medians by class were read from the service with `percentile_cont`.

## Limits

- Counts of different years: the layer gives each stretch's year (2017 to 2026 in the file; most 2020-2025).
- AADT is not congestion: it says how many vehicles pass, not how fast.
- The pavement share uses roughness alone, measured in 2024 and 2025 on the main roads.
