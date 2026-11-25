# Linking tourism places to transport: method and timing

Written 2026-10-05. **Status (2026-10-06): layers 0 and 1 (item 2b) are built and committed locally (not pushed); walking distance, the access layer on the engine and journey times are not.** The numbers in sections 1 to 8
come from an exploratory run on the published data (places and stops built 2026-10-02, feed status for 2026-10-05). Every figure can be reproduced from
[`docs/analysis/visitor-access-2026-10/`](analysis/visitor-access-2026-10/README.md). What was built, and where it differs from the plan, is in "As built (item 2b)" below.

**Update 2026-10-18 (HANDOFF decision 47).** The counts now leave out the listings that are not tourism (homes, housing estates, condominiums and care services filed under tourism categories; `docs/places-privacy.md`). On the new default basis (24,209 places, 26,579 before) the island figures as of 2026-10-06 are: any mapped stop 47.5%, a stop with a current timetable 32.2%, frequent 21.3%, Saturday 22.4%, Sunday 6.4%, rail station or ferry terminal 2.9%, near only an expired or unscheduled stop 15.4%; within a 400 m walk 28.0%, an 800 m walk 34.4%, a frequent stop on foot 18.0%; 64% have no stop with a current timetable within 800 m. The five classes: frequent 5,163 (21.3%), basic 2,627 (10.9%), near 964 (4.0%), on paper only 4,690 (19.4%), none 10,765 (44.5%). Carolina's walk drop is now 88.5% to 70.7%; 1,074 places (4.4%) keep the straight line. The figures in the rest of this document are those of the earlier basis and of the exploratory run, as written at the time.

## The answer

**How.** Link each tourism place to transport through the infrastructure around it, in three layers, and publish the result as an access **profile**, not a single score:

1. **The nearest stop that has a current timetable**, and what it offers (weekday calls, Saturday and Sunday service). Straight-line distance, computed without the road graph.
2. **The walking distance** to that stop along mapped roads. An estimate.
3. **The gateways**: the nearest airport, ferry terminal, rail station and bus terminal, and, for the San Juan metro only, scheduled journey times from a gateway.

A score would need weights, and the weights are a policy choice FPR has not made. A score would also hide the main finding: 64% of the 26,579 places on the map's default view have no stop with a
current timetable within 800 m.

**The first job is to fix the measure the twin already publishes.** "Within 400 m of transit" counts any mapped stop, including stops whose timetable ended months ago and stops that
volunteers drew on OpenStreetMap with no timetable. It reads 47.0% (46.5% as published). With a current timetable required it is **32.1%**, with frequent service **21.3%**, with Sunday service **6.1%**.
Thirty-three municipalities look partly served but have 0.0% once the timetable must be current. Ponce goes from 79.1% to 0.1% because its feed ended on 2024-12-31.

**When.** Do the fix and the cheap, robust first layer **next, as a new item 2b (after item 2, before item 3)**. Do walking distance and residents' access inside item 5, hubs and the access layer on the
engine (items 6 and 12), and journey times last, after the timetable data are repaired. Section 6 gives the reasons and the order.

## As built (item 2b, 2026-10-06)

- **Code.** `access.py` computes everything from the published stops, places and operators, and is run by `build.py` (full build) and by `refresh_network.py` (the nightly job, once the repository is pushed),
  so a place's fields cannot fall behind its stops again. `network.py` writes per stop `calls_sat`, `calls_sun` (from the calendar flags; missing means none in the feed) and `feed_end`. `refresh_network.py --offline` re-reads the cached feeds.
  Tests: `tests/test_access.py` (21) and `tests/test_gtfs_service.py` (4, need shapely).
- **Files.** `place_access.json` (new): `ts_m`, `ts_calls`, `ts_we`, one value per place in the order of `places.json`; `built` equals `meta.generated_at`, and the pages ignore the file when the two disagree.
  `places.json`: `transit_m`, `transit_400m`, `nearest_stop` rebuilt (1,204 places had gone stale: 892 whose distance differed by more than 2 m, all 183 places in Jayuya among them, and 312 by a meter or two or in the stop name only; 130 gained the 400 m flag and none lost it).
  `municipalities.json`: `acc_cur400_pct`, `acc_cur800_pct`, `acc_freq400_pct`, `acc_sat400_pct`, `acc_sun400_pct`, `acc_hub400_pct`, `acc_paper_pct`, `access_n`, `access_as_of`, `stops_current`, `stops_expired`, `stops_osm`;
  `transit_pct`, `places_near_transit` and the stop counts rebuilt (Jayuya 0 to 54 stops, Culebra 59 to 1, Utuado 47 to 50). `barrios.geojson`: `acc_cur400`, `acc_freq400` (full builds only). `meta.json`: an `access` block.
  `transport.json`: `calls_sat`, `calls_sun`, `feed_end`. The contract has a record for the new file; `barrios.geojson` moved to the medium tier (just over 1 MB).
- **Island figures as shipped** (default basis, 26,579 places): any mapped stop 47.0%, a stop with a current timetable **32.0%**, frequent 21.3%, Saturday 22.4%, Sunday 6.1%, rail station or ferry terminal 2.7%, near only an expired or unscheduled stop 14.9%.
  The exploratory run measured in projected meters (EPSG:32161) and read 32.1%, 22.5% and 2.8%; the twin's flat-earth distance (111,320 m per degree of latitude) is about 0.6% long north to south and reads up to 0.1 point lower. It is used on purpose: places, residents and the route planner stay on one scale.
  The five access classes as shipped: frequent 5,655 (21.3%), basic 2,858 (10.8%), near 1,131 (4.3%), on paper only 5,093 (19.2%), none 11,842 (44.6%). The class table in section 1 keeps the exploratory counts.
- **On screen.** The tourism-place pop-up says which access class the place is in and gives the nearest stop with a current timetable (distance, weekday departures, Saturday and Sunday service) and, when a stop without a current timetable is closer, the nearest mapped stop of any kind.
  The Municipality tab shows live shares near a stop with a current timetable, near a frequent stop and near any mapped stop, residents near a stop with a current timetable, and the stop counts by timetable state. Six new municipality shading and ranking options, the barrio pop-up, the stop pop-up (weekend departures and the end of its timetable) and the Housing profile follow.
  The old "within 400 m of transit" is now "within 400 m of any mapped stop" everywhere. The 3D page has the same pop-up and three of the new column options.
  The 14 municipalities with no stop inside their border have no color, rank or tile for any of the eight shares that depend on stops in the 2D map and in the municipality CSV (the file holds 0.0, or 0.4 for Toa Alta and 0.8 for Arroyo). The 3D page and the Housing profile still show the stored value; say if they should follow the 2D rule.
  The Layers tab of both maps is now a set of collapsible groups, all closed when the page opens, with the tourism places last.
- **Not built yet:** the hub distances from a gateways file, the access-class legend as a map layer, a distance to current stops for residents' blocks, and journey times. Everything in sections 3 and 4 that needs outreach or outside data is untouched.
- **Weight.** Compressed (gzip level 9 of the files as a commit stores them, against the previous commit): `place_access.json` adds 76.9 KB to the first load of the map and the 3D page (fetched in parallel with `places.json`); `municipalities.json` +1.6 KB and `meta.json` +0.2 KB, so +78.6 KB of data on the first load; scripts, pages and styles add 4.4 KB to the map and 3.8 KB to the 3D page (1.3 KB of that is the collapsible Layers groups). First load, English: map 2,960 KB to 3,043 KB (+82.8 KB), 3D page 3,460 KB to 3,542 KB (+82.3 KB); the Spanish bundles add 1.4 KB (map) and 0.7 KB (3D). When their layers load: `transport.json` +2.9 KB and `barrios.geojson` +1.8 KB. The data dictionary page grows by 22.1 KB (`dictionary.json` 472 KB to 494 KB). Load time on a throttled mobile connection was not measured. Estimated from the size alone: on Slow 4G (1.6 Mbit/s) the extra first-load data take about 0.4 s of transfer (the whole first load about 15 s, of which `places.json` is 2.7 MB), and on Slow 3G (400 kbit/s) about 1.7 s. Item 3 takes `place_access.json` out of the first load together with `places.json`.

## Walking distance (Tier 2, 2026-10-16)

- **Method.** `walknet.py` (promoted from the study's prototype, `docs/analysis/visitor-access-2026-10/walknet.py`) builds a walking network from the published `site/data/roads.bin`: every road except motorways and motorway links, both directions. Places and stops with a current timetable snap to the nearest walkable road within 150 m; `access.py` searches from each such stop up to 1,000 m (bounded Dijkstra). Distances use the observatory's flat-earth scale on a plane centered on Puerto Rico, so a walk and a straight line compare directly, and a walk is never shorter than the straight line (`tw_m >= ts_m`). Fallbacks, so nothing is dropped silently: a place with no road within 150 m keeps its straight-line values and is listed in `tw_straight`; a stop with no road within 150 m counts at its straight-line distance. The nightly refresh runs it too (it reads only `roads.bin`, about 20 s).
- **Files.** `place_access.json`: `tw_m` (99,999 past `walk_bound_m`), `tw_calls`, `tw_we`, `tw_straight`. `municipalities.json`: `acc_walk400_pct`, `acc_walk800_pct`, `acc_wfreq400_pct`. `barrios.geojson`: `acc_walk400`, `acc_wfreq400` (regenerated with `build_barrios` from the cached boundaries; identical to the previous file apart from the two fields). `meta.json` `access`: `walk400_pct`, `walk800_pct`, `wfreq400_pct` and a `walk` block. The straight-line fields keep their names and meaning.
- **Island figures** (default basis, as of 2026-10-06): within a 400 m walk of a stop with a current timetable **27.5%** (straight line 32.0%), within an 800 m walk 34.2% (36.3%), frequent 17.7% (21.3%). 1,101 places (4.1%) have no road within 150 m and keep the straight line; counting them out instead gives 26.6%, the study's figure. Walking is a median 1.43 times the straight line (90th percentile 2.45). Most municipalities change little (median 0.0 points); Carolina drops from 85.8% to 67.2%, around the airport and Plaza Carolina, where large grounds have no mapped public road.
- **Checks.** Searching from each place instead of from each stop gives the same distance for all 1,434 sampled places with a road nearby; the study's prototype (EPSG:32161) agrees on the 400 m test for all 495 compared places (distances a median 0.56% longer, the documented gap between the two scales). The study's full OpenStreetMap walking network (footpaths included) moved the island share by 0.4 point and municipal shares by a median 0.0 (largest 11.3, Hormigueros).
- **On screen.** The access classes and the place pop-up use the walk ("853 m walking along mapped roads (657 m in a straight line)"), or say that a place is measured in a straight line. A new class, "Stop within 800 m in a straight line, more than 800 m on foot" (545 places on the default basis), keeps such places out of "Only expired or unscheduled stops". The Municipality tab, the shading and ranking menus, the barrio and 3D pop-ups and the Housing profile lead with the walking shares; the straight-line options stay, labeled "(straight line)". Residents: see the next section.
- **Weight and load time** (Slow 4G, 3 runs each, `tests/browser/throttle.js`): map 564 KB to 567 KB of the site's files, ready in 4.9 s before and after; 3D page 812 KB to 814 KB, ready in 16.5 to 17.5 s before and after. `place_access.json` grows 37 KB compressed (78.9 KB to 116.9 KB), loaded only with the place listings.

## Walking distance for residents (2026-10-16)

- **Method.** The same engine for the 36,570 populated 2020 Census blocks, at their internal points: `network.coverage` (the Transit tab, the municipality panel, the Overview headline, the "Residents far from service" layer and the study areas) and `exposure.py` (`walk_cur`, `walk_freq` by municipio, barrio and tract). A walk is rounded up, as for places, so the two give the same 403,421 residents near a stop with a current timetable. Each block in `population_blocks.json` gains a fifth value, the meters walked to the nearest scheduled stop. Fallbacks are as for places; 4,002 blocks with 455,383 residents (13.9%) have no walkable road within 150 m and keep the straight line.
- **Island figures** (2020 residents): within a 400 m walk of a scheduled stop **15.5%** (straight line 28.2%); of a stop with a current timetable **12.3%** (22.2%). More than an 800 m walk from any scheduled stop: 2,251,110 residents (69%; 60% in a straight line). San Juan goes from 80.9% to 50.0%, Guaynabo from 77.8% to 43.3%; the median municipality does not move (most have no stop within 400 m either way).
- **Why the drop is larger than for places** (32.0% to 27.5%). Stops are on main roads; tourism places mostly face them, homes mostly do not. Among blocks joined to the road network, walking is a median 1.60 times the straight line (1.49 counting the blocks measured in a straight line; places: 1.43), because urbanizations reach the avenue through an entrance or around a block.
- **Checks.** The full OpenStreetMap walking network (footways, paths, steps and service roads included, the study's rules) gives 15.5% (roads only 15.6%); municipal shares move a median 0.0 points, at most 1.7 (Carolina). So the drop is not from missing footpaths. The figure does depend on how a block joins the network: the nearest road only (built) 15.5%; also every road within 30 m 15.6%, 60 m 17.1%, 100 m 19.1%. The dictionary gives this range. The straight-line coverage recomputed from the published stops matches the published files exactly before the walk is added.
- **Labels.** The Mobility headline on the Overview is now the walking share of residents near a stop with a current timetable (12%; it was 22%). The straight-line fields keep their names and stay in the menus, labeled "(straight line)". The route planner still measures 400 m around a drawn route in a straight line, as its note says.

## 1. What the numbers say

Default view: 26,579 places (confidence 0.50 or higher, no places of worship). Straight-line distance, 400 m.

| Test | Places | Share |
|---|---|---|
| A mapped stop of any kind (what the twin shows today) | 12,497 | 47.0% |
| A stop that belongs to a scheduled feed, expired feeds included | 10,844 | 40.8% |
| **A stop whose feed is current** | 8,524 | **32.1%** |
| … with 20 or more calls on a weekday | 5,664 | 21.3% |
| … with Saturday service | 5,975 | 22.5% |
| … with Sunday service | 1,623 | 6.1% |
| A rail station or ferry terminal | 737 | 2.8% |

- **Of the 12,497 places called "near", only 8,524 (68.2%) have a current scheduled stop.** 2,320 (18.6%) rest on stops from expired timetables and 1,653 (13.2%) on OpenStreetMap stops with no timetable.
- **47 of 78 municipalities have no place near a current scheduled stop**, and 59 have none near a stop with 20 or more weekday calls. Only 13 municipalities reach 50%.
- **Only the capital region has frequent service near most places.** Porta Capital: 58.0% near a stop with 20 or more calls. Porta del Sol Norte: 0.0%. Porta Caribe reads 39.9% today and 6.1% with a current timetable.
- **Walking changes the result again.** Along mapped roads the distance is a median 1.42 times the straight line (90th percentile 2.36). 14.8% of the places that look near are beyond 400 m on the road network, so 32.1% becomes
  **26.6%** (27.0% on a full OpenStreetMap walking network). The road file holds no footpaths, steps or service roads, so every walking figure is an estimate.
- **Residents fare worse than places** (Census block centers, 3.29 million people): 30.3% within 400 m of any stop, 22.2% of a current scheduled stop, 13.3% of a stop with 20 or more calls.
- **Gateways connect poorly to the island's transit.** Of 10 public airports only San Juan (SJU) has a current scheduled bus stop within 400 m (one stop, at 290 m; ATI routes 5, 40 and 53 serve the three stops within 500 m). The Ceiba ferry terminal, the gateway to Vieques and Culebra,
  is 31.5 km from the nearest ATI bus stop. The data hold 16 Tren Urbano stations, 6 ATI ferry terminals on 4 routes, 91 bus stations and terminals, and one cruise pier.
- **Journeys from SJU by scheduled transit** (weekday 10:00, up to 3 boardings): 9.9% of places within 60 minutes, 13.9% within 90, 18.3% within 120. By car (a free-flow estimate): 54.8%, 72.7%, 86.1%.
  Only the San Juan metro connects: 55.4% of Porta Capital places are within 120 minutes by transit, and the other regions have almost none.

**Access classes** (a candidate legend, computed from the first layer):

| Class | Definition | Places | Share |
|---|---|---|---|
| Frequent | Current scheduled stop within 400 m with 20 or more weekday calls | 5,664 | 21.3% |
| Basic | Current scheduled stop within 400 m, fewer calls | 2,860 | 10.8% |
| Near | Current scheduled stop 400–800 m away | 1,122 | 4.2% |
| On paper only | No current scheduled stop within 800 m, but an expired-feed or volunteer-mapped stop | 5,100 | 19.2% |
| None | No stop of any kind within 800 m | 11,833 | 44.5% |

The last two classes (16,933 places) are where hub connections matter: 66.9% of them are within 5 km and 91.0% within 10 km of some gateway (counting volunteer-mapped bus terminals).

## 2. The method

| Layer | What it adds | Needs the road graph | Build time (measured) | Weight added (gzip, measured by re-serializing the real file) |
|---|---|---|---|---|
| 0. Fix and relabel | Rebuild stale place fields; call the old measure "any mapped stop"; show feed status | No | seconds | 0 |
| 1. Stop with a current timetable | `ts_m`, `ts_calls`, `ts_we` per place; shares at 400 and 800 m per municipality, region and barrio; the access classes | No | 1.5 s for 15 stop sets | 135 KB inside `places.json` (2.88 MB today), or **66 KB** as typed columns in a separate file; areas about 23 KB |
| 2. Walking distance | `tw_m` per place; share within 400 m walking per area | Yes (`roads.bin` is enough) | 5.0 s end to end (0.9 s of searches) | 40 KB as JSON, 19 KB as a typed column |
| 3. Gateways | Hub distances in the browser from a 141-record `gateways.json`; journey times by transit and by car from named gateways | Car times: yes. Transit scan: no | 0.02 s per gateway and departure; 4.2 s once for the driving graph | `gateways.json` 5 KB; 67 KB per gateway as JSON, 27 KB as typed columns |

Timings vary two to three times with machine load; none needs more than a minute. Load time on a throttled mobile connection was **not measured**; the weights above are the first-load cost the change would add.

**Per-place fields**

| Field | Meaning |
|---|---|
| `ts_m` | Meters, straight line, to the nearest scheduled stop whose feed has not ended on the build date. Excludes volunteer-mapped stops, airports, taxi stands and chargers. |
| `ts_calls` | Largest number of weekday calls at a current scheduled stop within 400 m. A frequency proxy, not a headway. |
| `ts_we` | Saturday and Sunday flags of current scheduled stops within 400 m, read from the feed calendar. Missing means no such service in the published feed. |
| `tw_m` | Walking meters along mapped roads (motorways excluded, one-way rules ignored). An estimate; no footpaths, sidewalks, steps or crossings. |
| `transit_m`, `transit_400m`, `nearest_stop` | Keep for continuity and relabel: "nearest mapped stop of any kind, including expired timetables and volunteer-mapped stops". |

**Per-area series** (municipality, tourism region, barrio): shares of places with a current stop within 400 and 800 m, with 20 or more calls, with Saturday and Sunday service, near a rail station or ferry terminal,
walking within 400 m, and the "on paper" gap, each with its denominator (`access_n`) and date (`access_as_of`). Suppress shares where the area has fewer than 10 places, and say so.

**Dictionary and registry.** The place fields are about tourism places, so the placement guide makes them `economy.visitor-economy` with `infrastructure.mobility` as secondary. The per-stop fields (feed state,
Saturday and Sunday calls) are `infrastructure.mobility`. Every new field needs its dictionary entry, its Spanish label and its contract record (`docs/adding-data.md`).

**What the app must say**

- Schedule-based, not real-time: a typical Wednesday, Saturday or Sunday. No holidays. No live positions exist.
- Feed coverage and date: how many municipal systems publish a feed, which feeds have expired, which publish none; públicos are not in any timetable.
- Straight line or walking: say which one a number uses. Walking: "estimated along mapped roads; excludes footpaths, sidewalks, stairs, crossings and barriers".
- Estimates and proxies: `ts_calls` is a proxy. Journey times read "scheduled estimate, weekday 10:00, up to 3 boardings, walking up to 400 m, 3-minute transfer buffer; not door to door". Car times read "free-flow estimate; no traffic, signals or parking".
- Missing is not zero: "no Saturday service in the published data" is not "no Saturday service"; "no scheduled link in the data" is not "no link".
- Counts are listings (Overture), not businesses, rooms or visitors.

**What I would not claim:** that a place is "accessible by public transport" for a visitor; anything real-time; that no stop means no transport (públicos, taxis, ride-hailing, rental cars and tour shuttles are outside the data);
a walking time or a door-to-door time; service quality from weekday calls alone; a comparison between municipalities as if their feeds were equally complete (Ponce's 0.1% reflects a lapsed feed, not an absence of buses); journey
times outside the San Juan metro; demand or causality.

## 3. Fix first

These change the numbers more than any new method does.

1. **Rebuild the place access fields from today's stops** and call that code from the nightly refresh too. Today 111 Jayuya places lack the 400 m flag they should have, and the refresh never touches `places.json`.
2. **Store, per stop, in `parse_gtfs`:** feed state, Saturday and Sunday calls, first and last weekday departure.
3. **Write the untimed calls to the trip files** and keep stop IDs. The files drop 8.9% of weekday calls (up to 96% for one municipal feed), so journey times understate municipal service.
4. **Fold duplicate stops.** 905 pairs of scheduled stops lie within 30 m, and 226 of 506 OpenStreetMap bus stops are within 100 m of a scheduled stop. Correct the one Jayuya stop still 44 km off. Give every pier stop a municipality.
5. **Add ports and cruise piers** to the stop inventory (OpenStreetMap `harbour`, `landuse=port`, `amenity=ferry_terminal`) and take the Fajardo airport (FAJ) from OpenStreetMap until the FAA file is refreshed.
6. **Renew or replace the 7 expired municipal feeds** (966 of 3,847 scheduled stops, 25.1%). A Ponce feed alone would move about 921 places from "on paper" to "served" if the service still runs. This is outreach, not code: a draft exists in `OUTREACH_TRANSIT_DATA.md`.

Also document that `population_blocks.json` column 4 is meters to the nearest stop (it ignores feed status), not housing units.

## 4. Data from outside the repository

A second pass checked open, keyless sources (report: [`EXTERNAL_DATA.md`](analysis/visitor-access-2026-10/EXTERNAL_DATA.md)). The 21 resulting candidates are rows in `site/data/wanted.json`; none has been harvested.

| Use in the method | Source | State |
|---|---|---|
| Weights for gateways | FAA enplanements (2025), BTS T-100 monthly passengers, Ports Authority and PRTC monthly reports, cruise calls and passengers, BTS ferry census (2024: Vieques 641,183, Culebra 546,258, Cataño 428,604 passengers) | Federal files pass. PRTC and Ports Authority publish PDF or spreadsheets with **no license stated**. |
| Ferry timetables and fares | Official itineraries (PDF, 2026-08-01 to 2026-11-30) and ATI's fare regulation | The ATI GTFS is the only machine-readable schedule, but its Culebra times and its weekend Vieques times differ from the PDFs. Use 60 and 90 minute crossings. Non-residents pay 11.25 USD plus a 2 USD fee; vehicles board only if owned by residents. **Do not publish ferry journey times from the GTFS until it is corrected.** |
| More stops | BTS National Transit Map: 1,642 stops in 13 municipalities where the twin has no feed | Locations only, no timetables, so they can join the "mapped stop" class, not the "current scheduled" one. **Check this before sending the municipal outreach drafts.** |
| Last mile | Official taxi fixed fares (airport and piers, 21 USD to Old San Juan), airport ground-transport page, 25 EV chargers (OpenStreetMap has 11), island geoserver layers | Usable as notes and small tables; the fare tables sit in a 5 MB PDF and must be keyed by hand. |
| Tempering walking estimates | EPA National Walkability Index, 2,552 block groups | Passes. It rests on 2019 boundaries and possibly licensed street data: read the user guide before republishing. |
| **Blocked** | Opening hours at scale (Overture has no field; OpenStreetMap has them for about 6% of attractions); real-time positions (ATI says GTFS-RT is in development); current públicos and franchises; El Yunque visits; rooms by property | Each row names who to ask. |

Housekeeping found: the `cruise` row's URL did not resolve (now `tourism.pr.gov/statistics` and `prpa.pr.gov`); the `traffic` row now names the HPMS condition fields.
PRTC, NTSP and the Ports Authority state no license: confirm reuse in writing before harvesting anything from them.

## 5. What it costs

- **Work.** Layer 0 and 1: about one working session (pipeline, dictionary, Spanish labels, contract, tests, the corrected labels in the existing map text). Layer 2 adds about half a session inside item 5. Gateways and the access
  layer ride on the engine. Journey times are the large piece, because they need the data repairs in section 3.
- **Page weight.** Layer 1 as a separate typed-column file adds about 66 KB gzip. Today both pages fetch `places.json` at start, so the file loads with it; after item 3 it loads with the lazy visitor-economy module and the landing view carries none of it. Placing the fields in `places.json` instead adds 135 KB gzip to a file that is already 2.88 MB gzip. Load time on a throttled mobile connection is not measured; the figures are gzip sizes.
- **Build time.** Seconds for layers 0 and 1, about 5 s for walking, seconds for gateways. The nightly refresh can recompute layer 1 from the refreshed `transport.json`.

## 6. When to do it

| Step | What | Place in the plan | Why then | Size |
|---|---|---|---|---|
| **2b** (built 2026-10-06, committed locally) | Layers 0 and 1: fix the stale fields, relabel the old measure, add `ts_m`, `ts_calls`, `ts_we` and the area shares, per-stop feed state and weekend calls; correct the text where the map shows "near transit" | **Next: after item 2, before item 3** | It corrects a number the site publishes today (47.0% against 32.1%). Item 3 rewrites the landing text and makes the visitor-economy module lazy, and item 5 reuses the stop sets, so both should start from the corrected measure. It needs no road graph, no new geography and no engine. | M |
| Now, no code | Ask the 7 operators with expired feeds and ATI (untimed calls, stop IDs, GTFS-RT); check the BTS stops first; confirm licenses for PRTC, NTSP and the Ports Authority | Item 17 (outreach), started early | Replies take weeks. Better data is worth more than any method. | S |
| 3 | Landing and lazy visitor-economy module | As planned | The typed-column file loads only with the module. | |
| 4–5 | Layer 2: walking distance, and residents' and housing units' access with the same corrected stop sets, by barrio and tract | Inside **item 5** | Item 5 already measures "within 400 m of transit" for residents on the new geography base. One definition of "current scheduled stop" serves both. | S–M |
| 6 | Gateways: `gateways.json`, hub distances in the browser, the access-class legend and popup profile as engine adapters | Item 6, then item 12 profiles | Built once on the engine instead of twice (now and again). | M |
| 10 | Weights for gateways: airport, ferry, cruise and park visits | With data wave D (infrastructure includes airports); the ferry census, cruise and park visits join as visitor-economy additions | Together they are three or more datasets with the same users, which is what the placement guide asks for before adding a set. Hubs can be ranked by volume only after this. | M |
| Later | Journey times from gateways: SJU, Old San Juan and the Cataño ferry first | After the repairs in section 3, the outreach replies and item 12 | Outside the San Juan metro the data support no honest time. Publishing earlier would show a lapsed feed as "no link". | L |

If you prefer to wait for the engine for everything, the cost is that the 47.0% figure, and the municipal "transit" shares built on it, stay public through items 3 to 6 (the largest items in the plan).

## 7. Decisions for you

1. **Approve item 2b** (layers 0 and 1) as the next item after item 2? Recommended.
2. **Rename the published measure now**, to "within 400 m of any mapped stop, including expired timetables and volunteer-mapped stops"? Recommended: yes, in 2b.
3. **Where do the new fields live?** In a separate typed-column file (+66 KB gzip, loaded with the visitor-economy module; recommended) or in `places.json` (+135 KB gzip).
4. **Which gateways and departure times first** when journey times come: SJU, Old San Juan and the Cataño ferry at weekday 10:00 is the proposal.
5. **Who contacts the operators and ATI.** The draft in `OUTREACH_TRANSIT_DATA.md` should be reconciled with the BTS finding first.
6. **Review path.** These transit series use no federal grant data. The dictionary page stays `noindex` until Compliance has reviewed pages that describe grant-funded data; new access entries follow the same path.
7. **Which outside sources to harvest, and when** (section 4); each needs license confirmation first.

## 8. Limits

One snapshot (places and stops built 2026-10-02) and one day type per scan. Walking and driving times are estimates from OpenStreetMap-based graphs, with no field check. San Juan airport is located by the FAA reference point, not the terminal door.
"Eastern region" is read as the Tourism Company region Porta del Mar (15 municipalities, including Vieques and Culebra). Passenger numbers, demand and fares are not in the twin yet. The browser code was not tested; the site was not touched.
The outside-source findings were compiled by a research agent and have not been re-checked by FPR staff.
