# Tourism assets and transport links: exploratory spike for the PR Digital Twin

Read-only spike for Foundation for Puerto Rico (FPR). Analysis date 2026-10-05. Data: the published files in the repository's `site/data/` (places and stops built 2026-10-02; feed status recalculated for 2026-10-05). No network, no browser, no change to the repository. Every number below was read from the output of a script in this folder (list in section 9). Business names and addresses are not reproduced anywhere; the figures are aggregates.

## 1. The answer

**Today's "near transit" figure is about 1.5 times what current scheduled service supports.** 47.0% of the 26,579 default-basis tourism places are within 400 m (straight line) of some mapped stop (the twin publishes 46.5%; the gap is mostly the stale Jayuya fix). Require a scheduled stop whose operator feed is current and it is **32.1%** (14.9 points, 32% fewer places). Require 20 or more weekday calls at that stop and it is **21.3%**; require Saturday service, **22.5%**; Sunday service, **6.1%**; a Tren Urbano station or ferry terminal, **2.8%**.

Decision-relevant numbers:

1. Of the 12,497 places the twin calls "near", 8,524 (68.2%) have a current scheduled stop within 400 m; 2,320 (18.6%) rely only on stops from expired timetables and 1,653 (13.2%) only on volunteer-mapped OpenStreetMap stops (no timetable).
2. 33 municipalities look partly served (above 0%) but have 0.0% once a current timetable is required. Examples (any stop, then current scheduled stop): Juncos 92.8% to 0.0%; San Lorenzo 78.2% to 0.0%; Fajardo 70.4% to 0.0%; Ponce 79.1% to 0.1%. Ponce's feed ended 2024-12-31. 47 of 78 municipalities have no place within 400 m of a current scheduled stop; 59 have none near a stop with 20 or more weekday calls.
3. Walking changes the picture again: along mapped roads the network distance is a median 1.42 times the straight line (90th percentile 2.36). 14.8% of the places within 400 m by straight line of a current scheduled stop are beyond 400 m on the road network, so 32.1% becomes 26.6%. `roads.bin` holds no footways, paths, steps, pedestrian streets or service roads; a full OSM walking network moves the result by only 0.4 point (27.0%).
4. The whole-island walking run (3,834 bounded searches from the scheduled stops to 35,118 places) took 0.9 s in the final run (0.9 to 4.5 s across 5 runs on a shared machine); loading the graph, snapping and searching together took 5.0 s in the final run (5.0 to 25.6 s across the 5 runs). This is measured, not estimated.
5. Gateways in the data: 10 FAA public-use airports (SJU, BQN, PSE, MAZ and six more), 16 Tren Urbano stations, 6 ATI ferry terminals on 4 ferry routes, 91 bus stations and terminals (15 ATI, 29 municipal, 47 OpenStreetMap), and one cruise pier (mapped in OpenStreetMap as a ferry terminal). The Ceiba ferry terminal, the gateway to Vieques and Culebra, is 31.5 km from the nearest ATI bus stop; no scheduled land link to it exists in the data.
6. Scheduled transit from SJU (weekday 10:00, 3 boardings at most): 9.9% of places within 60 minutes, 13.9% within 90, 18.3% within 120. A free-flow driving estimate on the road graph gives 54.8%, 72.7% and 86.1%. Only the San Juan metro area is connected: 55.4% of Porta Capital places are within 120 minutes by transit; Porta Caribe, Porta Cordillera and both Porta del Sol regions have none.
7. Data problems that would distort a naive analysis: 7 operators with expired timetables hold 966 of 3,847 scheduled stops (25.1%); the trip files drop 8.9% of weekday calls (up to 96% for one municipal feed); the published place fields are stale for Jayuya (111 default-basis places wrongly lack the 400 m flag); one Jayuya stop is still 44 km from its municipality; 905 pairs of scheduled stops lie within 30 m of each other.
8. Added weight of the recommended core (three per-place fields): 135 KB gzip inside `places.json` (today 2.881 MB gzip), or 66 KB as a separate typed-column file; the per-area series add about 23 KB gzip. Build cost: seconds for Tier 1 (3.5 to 14.5 s for the whole baseline script, which computes 15 stop sets), 5.0 to 25.6 s more for walking distances, and 0.02 s per gateway and departure for the journey scan in the final run; all measured on a shared machine over 5 runs.

**Recommended method in brief** (details in section 8):

- Treat access as a **profile, not a score**. For each place publish: distance to the nearest *current scheduled* stop, the weekday calls and weekend flags at stops within 400 m, and (for walking) the network distance. Show the old "any stop" figure only as a labelled legacy field.
- **Tier 1 (cheap, robust, no road graph):** `ts_m`, `ts_calls`, `ts_we` per place and shares at 400 m and 800 m per municipality, region and barrio. Checked two independent ways to within 0.1 point.
- **Tier 2 (needs the road graph):** `tw_m`, the walking distance along mapped roads (bounded to 1,000 m). Use it for the 400 m flag; label it an estimate that ignores footpaths, sidewalks, fences and crossings.
- **Tier 3 (prototype now, needs better timetable data to scale):** scheduled journey times and a driving comparator from named gateways. Only gateways inside the San Juan metro area (SJU, Old San Juan, the Cataño ferry, Tren Urbano and ATI terminals) have a current scheduled stop within 400 m; for every other airport and ferry terminal publish "no scheduled link in the data", not a time.
- **Hubs:** for the 63.7% of places with no current scheduled stop within 800 m, compute distance to the nearest gateway (airport, ferry terminal, rail station, bus terminal) from a small `gateways.json` in the browser instead of adding a per-place field.
- **Fix first:** rebuild the stale place fields, put feed status and Saturday/Sunday calls on every stop inside `parse_gtfs`, write untimed calls into the trip files, and fold duplicate OSM and cross-operator stops. These fixes change the numbers more than any new method does.
- **Never claim:** that a place is "accessible by public transport" for a visitor, anything real-time, door-to-door times, or service quality from `trips_weekday` alone (section 8.9).

## 2. Definitions used throughout

- **Default basis:** places with confidence 0.50 or higher and no places of worship, the rule in `site/js/app.js` `visible(p)` with the initial state (`conf: 0.5`, `worship: false`). 26,579 of 35,118 places: Accommodations 3,106, Attractions 5,676, Gastronomy 17,178, Visitor services 619.
- **Stop sets** (all from `transport.json`): *any stop* = the twin's own set (kinds transit_stop, bus_stop, bus_station, rail_station, ferry_terminal from every source and feed: 4,360 features); *scheduled* = ATI and municipal GTFS stops (3,847); *current* = scheduled stops whose operator feed has not ended on 2026-10-05 (2,881; includes 92 Canóvanas stops whose feed ends 2026-10-31); *expired* = 966 stops of 7 operators; *OSM-only* = 513 volunteer-mapped stops with no timetable.
- **Weekday calls** = `trips_weekday` of a stop: scheduled calls on a typical Wednesday, both directions if the stop serves both. A one-direction stop shows about half of a two-way stop with the same headway.
- **Distances** are straight-line metres in EPSG:32161 (Puerto Rico State Plane), computed with a spatial index. The twin's own flat-earth formula gives the same shares to within 0.1 point (checked by brute force, section 3.7).
- **Eastern region** = the Puerto Rico Tourism Company region *Porta del Mar* (15 municipalities, including Vieques and Culebra); the app has no region called "East".

## 3. Question 1: baseline today, and what changes with real service

### 3.1 Island, default basis

| Stop set (default basis, 26,579 places) | Stops in set | Within 400 m | Within 800 m | Places within 400 m |
|---|---|---|---|---|
| (a) any stop, as the twin does today | 4,360 | 47.0% | 55.5% | 12,497 |
| scheduled stop, any feed (expired included) | 3,847 | 40.8% | 46.2% | 10,844 |
| (b) scheduled stop, feed current | 2,881 | 32.1% | 36.3% | 8,524 |
| (c) current, 10 or more weekday calls | 2,027 | 26.5% | 31.4% | 7,056 |
| (c) current, 20 or more weekday calls | 1,190 | 21.3% | 25.9% | 5,664 |
| (c) current, 40 or more weekday calls | 521 | 14.2% | 18.7% | 3,787 |
| (d) current, Saturday service | 1,777 | 22.5% | 25.6% | 5,975 |
| (d) current, Sunday service | 94 | 6.1% | 10.7% | 1,623 |
| (e) rail station or ferry terminal | 29 | 2.8% | 5.9% | 737 |

Reading: the first row is what the twin shows now. Each further condition removes places. The 3,973 places that drop out between rows (a) and (b) are the "served on paper" places. Sunday service exists only on ATI (94 stop locations: Tren Urbano, bus routes 3, 30, 40, ferry routes CC, CI, CSJ).

If expired feeds are also counted (scheduled stops of any feed), the shares within 400 m are 29.4% / 22.5% / 15.2% for 10 / 20 / 40 or more weekday calls and 22.6% / 6.1% for Saturday / Sunday service (Sunday is ATI only, so it does not change). Of the 29 rail and ferry features, 22 are scheduled in current feeds (the other seven are OpenStreetMap ferry nodes); counting only those gives 2.7% within 400 m.

Residents, same stop sets (Census block centres, 3,285,874 people): within 400 m of any stop 30.3%, of a current scheduled stop 22.2%, with 20 or more weekday calls 13.3%, with Saturday service 16.4%, next to rail or ferry 0.6%. Places are better served than residents, probably because listings concentrate in town centres where stops are (not tested).

### 3.2 By category, within 400 m (percent of places)

Columns: A any stop, A1 scheduled stop of any feed, B current scheduled, C10 / C20 / C40 current with 10 / 20 / 40 or more weekday calls, D-Sat / D-Sun current with Saturday / Sunday service, E rail station or ferry terminal.

| Category | Places | A | A1 | B | C10 | C20 | C40 | D-Sat | D-Sun | E |
|---|---|---|---|---|---|---|---|---|---|---|
| Accommodations | 3,106 | 33.4 | 29.7 | 24.6 | 19.4 | 14.7 | 10.7 | 15.8 | 3.4 | 1.4 |
| Attractions | 5,676 | 42.0 | 37.3 | 30.2 | 25.2 | 20.7 | 14.0 | 22.5 | 6.1 | 2.8 |
| Gastronomy | 17,178 | 51.0 | 43.8 | 33.9 | 28.1 | 22.4 | 14.6 | 23.4 | 6.2 | 2.8 |
| Visitor services | 619 | 52.2 | 45.1 | 36.3 | 33.0 | 29.2 | 23.6 | 30.9 | 17.6 | 8.6 |
| All default | 26,579 | 47.0 | 40.8 | 32.1 | 26.5 | 21.3 | 14.2 | 22.5 | 6.1 | 2.8 |

### 3.3 By category, within 800 m (percent of places)

| Category | Places | A | A1 | B | C10 | C20 | C40 | D-Sat | D-Sun | E |
|---|---|---|---|---|---|---|---|---|---|---|
| Accommodations | 3,106 | 44.3 | 37.2 | 30.2 | 24.7 | 18.4 | 14.1 | 18.7 | 7.8 | 4.0 |
| Attractions | 5,676 | 51.4 | 43.8 | 35.4 | 30.7 | 25.8 | 19.0 | 26.6 | 11.0 | 6.3 |
| Gastronomy | 17,178 | 58.7 | 48.4 | 37.5 | 32.6 | 26.9 | 19.0 | 26.1 | 10.7 | 5.9 |
| Visitor services | 619 | 59.6 | 50.2 | 40.5 | 37.6 | 34.2 | 28.9 | 35.4 | 21.8 | 11.8 |
| All default | 26,579 | 55.5 | 46.2 | 36.3 | 31.4 | 25.9 | 18.7 | 25.6 | 10.7 | 5.9 |

### 3.4 By tourism region, within 400 m (percent of places)

| PRTC region | Places | A | A1 | B | C10 | C20 | C40 | D-Sat | D-Sun | E |
|---|---|---|---|---|---|---|---|---|---|---|
| Porta Atlántico | 3,370 | 32.7 | 27.2 | 23.0 | 12.3 | 7.5 | 2.5 | 10.2 | 0.0 | 0.1 |
| Porta Capital | 8,505 | 81.2 | 77.2 | 70.8 | 66.0 | 58.0 | 42.3 | 64.0 | 18.3 | 7.8 |
| Porta Caribe | 3,090 | 39.9 | 35.9 | 6.1 | 3.8 | 2.8 | 0.0 | 0.0 | 0.0 | 0.0 |
| Porta Cordillera | 2,269 | 30.0 | 21.4 | 16.5 | 10.2 | 5.7 | 1.9 | 0.0 | 0.0 | 0.0 |
| Porta del Mar | 3,417 | 39.2 | 33.5 | 16.1 | 10.6 | 4.8 | 0.5 | 5.6 | 2.0 | 2.2 |
| Porta del Sol Norte | 3,274 | 14.5 | 3.8 | 3.8 | 1.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Porta del Sol Sur | 2,654 | 28.5 | 18.5 | 18.5 | 10.3 | 3.7 | 1.7 | 0.0 | 0.0 | 0.0 |

Porta Capital is the only region where a visitor without a car finds frequent scheduled service near most places (58.0% within 400 m of a stop with 20 or more weekday calls). Porta Caribe shows 39.9% under today's measure but 6.1% with a current timetable, because Ponce's feed ended 2024-12-31. Porta del Sol Norte has 0.0% of places near a stop with 20 or more weekday calls and Porta del Sol Sur 3.7%; neither region has a place near Saturday service (0.0% and 0.0%).

### 3.5 By type (selected, within 400 m, percent of places)

| Type | Places | A any | B current | C20 | D-Sat | E rail/ferry |
|---|---|---|---|---|---|---|
| Beaches | 841 | 26.6 | 21.5 | 14.0 | 15.5 | 1.8 |
| Hotels | 1,042 | 38.2 | 29.6 | 20.1 | 20.2 | 2.0 |
| Resorts | 36 | 19.4 | 16.7 | 13.9 | 13.9 | 2.8 |
| Vacation Properties | 426 | 27.5 | 20.2 | 7.5 | 8.2 | 0.9 |
| Lodging | 1,493 | 31.7 | 22.0 | 12.8 | 14.5 | 0.9 |
| Historic Sites | 1,996 | 41.8 | 31.5 | 22.3 | 25.1 | 2.2 |
| Museums | 162 | 72.2 | 45.1 | 30.9 | 27.8 | 5.6 |
| Parks | 950 | 44.4 | 28.8 | 17.5 | 20.7 | 1.8 |
| Restaurants | 10,284 | 52.2 | 35.5 | 23.6 | 24.9 | 2.8 |
| Marinas | 74 | 48.6 | 32.4 | 25.7 | 27.0 | 9.5 |
| Scenic Areas | 399 | 18.5 | 12.8 | 7.0 | 6.3 | 1.0 |
| Tourist Attractions | 791 | 46.9 | 33.6 | 24.0 | 25.2 | 3.8 |
| Nature Reserves | 59 | 28.8 | 20.3 | 8.5 | 8.5 | 0.0 |
| Tour Operators | 116 | 48.3 | 28.4 | 23.3 | 23.3 | 10.3 |
| Adventure Operators | 148 | 34.5 | 24.3 | 15.5 | 18.2 | 2.7 |

Against the all-places figure of 32.1% near a current scheduled stop, museums (45.1%), restaurants (35.5%) and tourist attractions (33.6%) sit above, while beaches (21.5%), hotels (29.6%), parks (28.8%) and scenic areas (12.8%) sit below. Only 1.8% of beaches and 2.0% of hotels are near a rail station or ferry terminal.

### 3.6 Municipalities

Full tables: `q1_by_municipality_full.csv` (every stop set at 400 m and 800 m) and `q1_by_municipality.csv` (with the cause split below). 14 municipalities have no place near any stop of any kind; 47 have none near a current scheduled stop; 59 none near a stop with 20 or more weekday calls; 63 none near Saturday service; 69 none near Sunday service. Only 13 municipalities reach 50% near a current scheduled stop.

**Municipalities that look "served" only because of expired or OSM-only stops** (37 municipalities where the current-service share is under one third of the any-stop share; 33 of them at 0.0%). Cause counts: expired feed only 5, expired feed and OSM stops 4, OSM stops only 28. In the OSM-only cases the "service" is usually one volunteer-mapped bus terminal with no timetable (the twin's own dictionary says most such terminals are carros públicos terminals).

| Municipality | Region | Places | Any stop % | Current scheduled % | Near places on expired feed only | Near places on OSM stops only | Cause |
|---|---|---|---|---|---|---|---|
| Juncos | Porta del Mar | 152 | 92.8 | 0.0 | 141 | 0 | expired feed |
| Ponce | Porta Caribe | 1,165 | 79.1 | 0.1 | 921 | 0 | expired feed |
| San Lorenzo | Porta del Mar | 193 | 78.2 | 0.0 | 151 | 0 | expired feed |
| Fajardo | Porta del Mar | 433 | 70.4 | 0.0 | 303 | 2 | expired feed and OSM stops |
| Caguas | Porta Capital | 916 | 77.4 | 17.6 | 540 | 8 | expired feed and OSM stops |
| Hatillo | Porta Atlántico | 332 | 42.5 | 0.0 | 141 | 0 | expired feed |
| Cidra | Porta Cordillera | 270 | 40.7 | 0.0 | 110 | 0 | expired feed |
| Sabana Grande | Porta del Sol Sur | 135 | 35.6 | 0.0 | 0 | 48 | OSM stops only |
| San Germán | Porta del Sol Sur | 241 | 32.4 | 0.0 | 0 | 78 | OSM stops only |
| Comerío | Porta Cordillera | 109 | 31.2 | 0.0 | 0 | 34 | OSM stops only |
| Lares | Porta del Sol Norte | 155 | 31.0 | 0.0 | 0 | 48 | OSM stops only |
| Aguas Buenas | Porta Capital | 125 | 30.4 | 0.0 | 0 | 38 | OSM stops only |
| Aibonito | Porta Cordillera | 199 | 28.1 | 0.0 | 0 | 56 | OSM stops only |
| Moca | Porta del Sol Norte | 217 | 28.1 | 0.0 | 0 | 61 | OSM stops only |
| Adjuntas | Porta Cordillera | 157 | 28.0 | 0.0 | 0 | 44 | OSM stops only |
| Gurabo | Porta Capital | 211 | 27.0 | 0.0 | 11 | 46 | expired feed and OSM stops |
| Luquillo | Porta del Mar | 260 | 25.0 | 0.0 | 0 | 65 | OSM stops only |
| Naguabo | Porta del Mar | 168 | 25.0 | 0.0 | 0 | 42 | OSM stops only |
| Cayey | Porta Capital | 346 | 22.5 | 0.0 | 0 | 78 | OSM stops only |
| Quebradillas | Porta del Sol Norte | 177 | 20.9 | 0.0 | 0 | 37 | OSM stops only |
| Juana Díaz | Porta Caribe | 280 | 19.6 | 0.0 | 0 | 55 | OSM stops only |
| Dorado | Porta Atlántico | 349 | 20.1 | 0.9 | 0 | 67 | OSM stops only |
| Ciales | Porta Cordillera | 147 | 17.7 | 0.0 | 0 | 26 | OSM stops only |
| Guayama | Porta Caribe | 288 | 17.7 | 0.0 | 0 | 51 | OSM stops only |
| Mayagüez | Porta del Sol Sur | 661 | 21.8 | 4.2 | 0 | 116 | OSM stops only |
| Barceloneta | Porta Atlántico | 246 | 17.5 | 0.0 | 0 | 43 | OSM stops only |
| Naranjito | Porta Cordillera | 204 | 17.2 | 0.0 | 0 | 35 | OSM stops only |
| Rincón | Porta del Sol Norte | 470 | 16.4 | 0.0 | 0 | 77 | OSM stops only |
| Camuy | Porta Atlántico | 211 | 15.6 | 0.0 | 0 | 33 | OSM stops only |
| Las Piedras | Porta del Mar | 169 | 15.4 | 0.0 | 2 | 24 | expired feed and OSM stops |
| Aguada | Porta del Sol Norte | 476 | 14.9 | 0.0 | 0 | 71 | OSM stops only |
| Yabucoa | Porta del Mar | 172 | 14.5 | 0.0 | 0 | 25 | OSM stops only |
| Santa Isabel | Porta Caribe | 177 | 10.7 | 0.0 | 0 | 19 | OSM stops only |
| Lajas | Porta del Sol Sur | 236 | 9.7 | 0.0 | 0 | 23 | OSM stops only |
| Aguadilla | Porta del Sol Norte | 682 | 8.2 | 0.0 | 0 | 56 | OSM stops only |
| Río Grande | Porta del Mar | 414 | 6.5 | 0.0 | 0 | 27 | OSM stops only |
| Arecibo | Porta Atlántico | 675 | 5.6 | 0.0 | 0 | 38 | OSM stops only |

Best-served municipalities (50 or more places):

| Municipality | Places | Any stop % | Current % | >=20 calls % | Sat % | Sun % |
|---|---|---|---|---|---|---|
| San Juan | 3,753 | 94.7 | 92.8 | 77.3 | 85.0 | 32.0 |
| Guaynabo | 693 | 91.9 | 90.8 | 70.7 | 90.5 | 1.6 |
| Carolina | 970 | 91.4 | 86.0 | 73.5 | 80.8 | 6.4 |
| Vega Alta | 218 | 84.4 | 84.4 | 16.1 | 84.4 | 0.0 |
| Canóvanas | 211 | 83.4 | 83.4 | 10.0 | 0.0 | 0.0 |
| Jayuya | 157 | 70.7 | 70.7 | 40.8 | 0.0 | 0.0 |
| Vega Baja | 381 | 69.8 | 69.8 | 16.3 | 0.5 | 0.0 |
| Bayamón | 1,091 | 69.4 | 68.7 | 46.4 | 47.0 | 8.8 |
| Cataño | 167 | 68.3 | 67.7 | 67.7 | 67.7 | 15.0 |
| Patillas | 148 | 67.6 | 67.6 | 20.3 | 0.0 | 0.0 |
| Cabo Rojo | 773 | 58.1 | 58.1 | 12.8 | 0.0 | 0.0 |
| Manatí | 288 | 57.6 | 57.6 | 0.0 | 0.0 | 0.0 |

### 3.7 Replication of the published figure

- The published `transit_400m` gives 46.5% for the default basis. Recomputing with the twin's own formula and the current `transport.json` gives 47.0%. The difference is 112 places (111 in Jayuya) that should carry the flag; none lose it.
- `places.json` was built before the Jayuya longitude fix reached `transport.json`. Jayuya: median distance 9,927 m published against 201 m recomputed; share within 400 m 0.0% published against 70.7%.
- Municipal `transit_pct` matches the recomputed any-stop share to within 0.5 point everywhere except Culebra (24.3 against 27.1), Jayuya (0.0 against 70.7), Naguabo (24.4 against 25.0).
- Independent check of sets B, C20, C40, D and E: brute-force nearest distance with the twin's flat-earth formula (no projection, no index) gives within 0.1 point of the indexed figures (for example B 32.0% against 32.1%, C20 21.3% against 21.3%).
- Counting the 92 Canóvanas stops (feed ends 2026-10-31) as not current changes B from 32.1% to 31.8%.
- Frequency thresholds counted on stop locations (adding up co-located stop IDs) instead of single IDs change C10, C20, C40 from 26.5%, 21.3%, 14.2% to 27.0%, 21.9%, 14.3%.

### 3.8 How weekend service was derived, and its error

The trip files hold `[lng, lat, seconds]` per stop call and no stop ID. `network.py` rounds every stop coordinate to five decimals (about 1.1 m) before writing both `transport.json` and the trip files, so equality is exact. **Rule:** a call at (lng, lat) on a trip of operator O counts for the scheduled stop(s) of operator O with those coordinates; stop IDs of one operator sharing a coordinate are merged into one stop location (3,847 stops make 3,698 locations; 122 locations hold 271 stops).

Error, in order of size:

1. **Matching itself is exact:** all 130,931 calls (78,414 weekday, 47,052 Saturday, 5,465 Sunday) matched a scheduled stop (0 unmatched).
2. **Calls missing from the trip files.** `parse_gtfs` writes only calls that have a time and leaves out routes with a non-geographic stop order (5 Patillas routes). The files hold 78,414 weekday calls against 86,067 in the feeds (-8.9%). At 917 of 3,698 locations the file has fewer calls than the feed, and 844 have none (383 of them on current feeds). For this reason weekday frequency tiers use the feed's own `trips_weekday` per stop, not the trip files.
3. **Weekend flags cross-checked.** I derived Saturday and Sunday service a second way, from the route calendars (`trips_saturday`, `trips_sunday` in `transit_routes.geojson`, matched to the routes listed at each stop). Current feeds agree exactly. The only difference is 131 Juncos locations with Saturday service in the calendar but no timed call in the file (Juncos' feed is expired). Sunday: 94 against 94.
4. **What a missing flag means.** No Saturday or Sunday service in the data is not proof of none: the operators whose feeds contain Saturday service are ATI, Guaynabo, Juncos, Vega Alta (Juncos is expired); the only one with Sunday service is ATI. Most municipal feeds carry weekday calendars only.

## 4. Question 2: straight line against walking along the road network

### 4.1 What the graph contains

`roads.bin` (read with `roads.Roads`): 193,507 nodes, 226,421 edges, 33,056 km. Classes present: motorway, motorway_link, trunk, trunk_link, primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, unclassified, residential, living_street, busway. **It has no footways, paths, steps, pedestrian streets, cycleways, tracks or service roads** (`roads.py` `CLASSES` lists none of them, `_usable()` drops every `highway=service`, and ways with `access=no/private` or `motor_vehicle=no` are dropped). 10.2% of edges are one-way; pedestrians ignore that, so the walking run treats every edge as two-way and drops motorways and motorway links (1,100 km). The cached OpenStreetMap extract (`cache/roads/puerto-rico.osm.pbf`, read only) holds a further 11,744 km of ways a pedestrian can use that `roads.bin` lacks: service 4,257 km, tracks 5,791 km, paths 897 km, footways 767 km, pedestrian ways 7 km, steps 6 km. Footways are 1.8% of the 43,735 km of walkable ways in the extract, so even the full extract holds little sidewalk detail.

Snapping (shapely nearest edge, 150 m limit): 3,834 of 3,847 scheduled stops snap (median connector 6.6 m); 25,484 of 26,579 default places snap (median connector 13.4 m, 90th percentile 49 m); 1,095 places have no walkable road within 150 m (453 not within 300 m). The snap distance matches `roads.Roads.snap` (median difference 0.01 m on 60 places). Network distance = connector to the road + path along edges + connector to the stop.

### 4.2 Sample result

Sample: 1,000 places drawn at random (seed 20261005) from the 12,271 default places within 800 m straight line of a scheduled stop (any feed); place-side bounded Dijkstra, cut-off 1,000 m.

| Measure (sample of 1,000 default places within 800 m straight line of a scheduled stop) | Value |
|---|---|
| Places with a road within 150 m (could be snapped) | 973 of 1000 |
| Network distance found within the 1,000 m cut-off | 941 of 973 |
| Ratio network / straight line to the nearest stop: median | 1.42 |
| Ratio: 25th to 75th percentile | 1.27 to 1.77 |
| Ratio: 90th percentile | 2.36 |
| Ratio: 95th percentile | 2.93 |
| Detour factor to the same (straight-line nearest) stop: median / 90th | 1.45 / 2.69 |
| Extra metres (network minus straight line): median / 90th percentile | 52.4 / 204.4 |
| Share of places with ratio above 1.5 / above 2 | 42.5% / 17.7% |
| Places within 400 m straight line | 870 |
| of which beyond 400 m on the network (road within 150 m) | 122 (14.3%) |
| of which no road within 150 m (cannot be tested) | 18 |
| Places beyond 400 m straight line but within 400 m on the network | 0 |

By straight-line band (median / 90th percentile ratio): 0-200 m: 1.46 / 2.53 (n=658); 200-400 m: 1.41 / 2.18 (n=188); 400-600 m: 1.31 / 1.69 (n=74); 600-800 m: 1.32 / 1.51 (n=21).

**Flips across the 400 m line:** 122 of the 852 sampled places within 400 m straight line that have a road within 150 m (14.3%) are farther than 400 m on the network; 18 more have no road within 150 m and cannot be tested. No place goes the other way (a walking route cannot beat a straight line). At 800 m, 70 of 973 snapped places are beyond 800 m on the network.

### 4.3 Whole island

| Island, default basis (26,579 places) | Straight line | Walking, roads.bin | Walking, full OSM network |
|---|---|---|---|
| Within 400 m of a current scheduled stop | 32.1% | 26.6% | 27.0% |
| Within 800 m of a current scheduled stop | 36.3% | 33.0% | 33.5% |
| Within 400 m of any scheduled stop (expired included) | 40.8% | 33.5% | 34.0% |
| Places lost at 400 m (share of those near by straight line), current stops | - | 17.2% (1,467 places) | 15.9% |

On the default basis 1,467 places drop out at 400 m when walking is measured against current scheduled stops: 1,226 are true detours (14.8% of the 8,283 near places that have a road within 150 m) and 241 have no road within 150 m. By category the share of straight-line-near places lost at 400 m is: Accommodations 25.0%; Attractions 22.8%; Gastronomy 14.1%; Visitor services 28.0%. Accommodations and visitor services lose most (the reason was not investigated).

### 4.4 How reliable is a roads-only distance

I built a second graph from the same OpenStreetMap extract with every pedestrian-usable way (309,829 nodes, 365,729 edges, 43,666 km) and repeated the island run. Island share within 400 m of a current scheduled stop: roads-only 26.6%, full walking network 27.0%, straight line 32.1%. 284 of the 1,467 places lost on the roads-only graph come back inside 400 m on the full network, and places with no walkable road within 150 m fall from 1,095 to 358. Where both graphs find a path, the full-network distance has a median ratio 1.0 to the roads-only one (10th to 90th percentile 0.907 to 1.134).

**Conclusion:** the roads-only graph is reliable enough for an *aggregate* walking-access share (about 0.4 point on the island; municipal shares differ from the full-network ones by a median 0.0 points, 90th percentile 0.99, largest 11.3 (Hormigueros), over 73 municipalities with 100 or more places) and for flagging places where a detour is likely. It is less reliable for one individual place: 19.4% of the places lost on the roads-only graph come back within 400 m once footpaths, tracks, steps and service roads are added. Neither graph can see rivers without bridges, highways without crossings, fences, hills or missing sidewalks, so every walking figure must be labelled an estimate.

### 4.5 Run time (measured on this machine, single-threaded Python)

| Step | Time |
|---|---|
| Load `roads.bin` with `roads.Roads` and build the walking graph (222,254 edges, spatial index) | 3.5 s (one-off per build; 3.1 s of it is `roads.Roads`) |
| Snap 3,847 stops / 35,118 places | 0.06 s / 0.44 s |
| Bounded Dijkstra (1,000 m) from each of 3,834 scheduled stops to all 35,118 places | **0.9 s** (0.2 ms per stop; mean 141 nodes settled per search) |
| Same search from the place side for the 1,000-place sample | 0.2 ms per place |
| Island run end to end (load graph, snap, search) | **5.0 s** |
| Whole script incl. sample, checks, tables | 9.3 s |
| Full OSM walking graph: read the 74 MB extract (one-off) / build graph / island run | 12.9 s / 3.3 s / 2.2 s |

These are the timings of the final run. The machine was shared, and the same steps varied between the 5 runs made here: island search 0.9 to 4.5 s, graph load 3.5 to 18.5 s, end to end 5.0 to 25.6 s, reading the 74 MB extract 11.8 to 60.9 s (`timing_history.json`).

Place-side and stop-side searches agree exactly (0 mismatches over 973 places). As a plausibility check, on 40 place-to-stop pairs the walking distance never exceeded the length of the `roads.Roads.route` path (median ratio router/walk 1.002). A search settles only 141 nodes on average because `roads.bin` edges are long (mean edge about 146 m).

## 5. Question 3: gateways, ferry routes, the Eastern region, Vieques and Culebra

### 5.1 What is in the data

| Gateway kind | ATI GTFS | Municipal GTFS | OpenStreetMap | FAA | Total |
|---|---|---|---|---|---|
| Airports | - | - | 11 | 14 (10 public use) | 25 |
| Rail stations (Tren Urbano) | 16 | - | 0 | - | 16 |
| Ferry terminals | 6 | - | 7 | - | 13 |
| Bus stations and terminals | 15 | 29 | 47 | - | 91 |

- **Airports:** FAA public-use: ABO, BQN, CPX, MAZ, PSE, RVR, SIG, SJU, VQS, X63; 4 private-use strips. OpenStreetMap adds Diego Jiménez Torres in Fajardo (FAJ), two seaplane bases (Fajardo, San Juan) and 8 other airfields (historic, closed, military, on Mona Island or unnamed). FAJ is missing from the FAA list in the published file.
- **Rail:** 16 Tren Urbano stations (San Juan 12, Bayamón 3, Guaynabo 1), 166 weekday trips per station; no other rail.
- **Bus terminals:** 15 ATI (Covadonga in Old San Juan, Sagrado Corazón, Piñero, Cupey, Bayamón, Cataño, Carolina, Iturregui, Campanilla and others), 29 in municipal feeds (8 in San Lorenzo's expired feed), and 47 volunteer-mapped OpenStreetMap stations with no timetable. 26 of 78 municipalities have no bus station in any source.
- **Taxi and ride-hailing:** 9 mapped taxi stands in 4 municipalities; Uber's cities page lists 57 municipalities (a yes/no listing, not coverage).

### 5.2 Ferry routes in the timetable and route files

| Route | Name | Operator in the data | Stops | Trips weekday | Sat | Sun | First to last departure (weekday) | Crossing time |
|---|---|---|---|---|---|---|---|---|
| CSJ | Cataño-Viejo San Juan | ATI GTFS feed | Terminal de Lancha Cataño - Terminal de Lancha San Juan | 32 | 30 | 31 | 05:30-22:00 | 12 min |
| CC | Ceiba-Culebra | ATI GTFS feed | Terminal de Lanchas Culebra - Terminal de Lanchas de Ceiba | 16 | 18 | 18 | 03:30-21:30 | 45 min |
| CI | Ceiba-Vieques | ATI GTFS feed | Terminal de Lanchas Vieques (Isabel II) - Terminal de Lanchas de Ceiba | 12 | 16 | 16 | 04:30-21:30 | 45 min |
| CM | Ceiba-Mosquitos | ATI GTFS feed | Terminal de Lanchas Vieques (Mosquito) - Terminal de Lanchas de Ceiba | 4 | 0 | 0 | 04:45-19:15 | 45 min |

Trips are one-way sailings (CSJ: 16 each way). The data hold no ferry operator other than ATI: Fajardo's terminal, private passenger boats and any other lake or bay ferries have no timetable.

### 5.3 Link from each gateway to land transit

| Public-use airport (FAA code) | Municipality | Nearest current bus stop | Current bus stops within 400 m | Weekday calls at the busiest of them |
|---|---|---|---|---|
| BQN | Aguadilla | 20.9 km | 0 | - |
| ABO | Arecibo | 18.8 km | 0 | - |
| RVR | Ceiba | 21.1 km | 0 | - |
| X63 | Humacao | 2.0 km | 0 | - |
| CPX | Culebra | 23.2 km | 0 | - |
| VQS | Vieques | 2.1 km | 0 | - |
| MAZ | Mayagüez | 11.2 km | 0 | - |
| PSE | Ponce | 17.9 km | 0 | - |
| SIG | San Juan | 677 m | 0 | - |
| SJU | Carolina | 290 m | 1 | 117 |

Only SJU has a current scheduled stop within 400 m (3 stops lie within 500 m of its reference point, at 290, 465, 481 m; ATI routes 40, 5, 53 stop there). The next closest are SIG at 677 m, X63 at 2.0 km and VQS at 2.1 km; the rest are more than 11 km from any current bus stop.

| Ferry terminal | Source | Nearest current bus stop | Current bus stops within 400 m | Weekday calls at the busiest |
|---|---|---|---|---|
| Vieques / Culebra Ferry Service | OpenStreetMap | 18.0 km | 0 | - |
| Acuaexpreso Hato Rey | OpenStreetMap | 162 m | 7 | 191 |
| (unnamed OSM node) | OpenStreetMap | 6.5 km | 0 | - |
| (unnamed OSM node) | OpenStreetMap | 405 m | 0 | - |
| Terminal de Lanchas de Fajardo | OpenStreetMap | 24.8 km | 0 | - |
| Servicios de Lanchas | OpenStreetMap | 17.4 km | 0 | - |
| Terminal de Lanchas Vieques (Mosquito) | ATI feed | 4.0 km | 0 | - |
| Terminal de Lanchas Vieques (Isabel II) | ATI feed | 407 m | 0 | - |
| Terminal de Lancha Cataño | ATI feed | 79 m | 6 | 108 |
| Terminal de Lancha San Juan | ATI feed | 180 m | 4 | 508 |
| Terminal de Lanchas Culebra | ATI feed | 22.4 km | 0 | - |
| Terminal de Lanchas de Ceiba | ATI feed | 18.0 km | 0 | - |
| Cruise pier 4, Old San Juan (mapped as a ferry terminal) | OpenStreetMap | 222 m | 3 | 508 |

Tren Urbano: 15 of 16 stations have current bus stops within 400 m (3 to 22 stops; up to 367 weekday calls at the busiest); Jardines has none within 560 m. Of the 15 ATI bus terminals, 13 have other current bus stops within 400 m; Terminal Transporte Publico de Caguas: nearest at 448 m; Terminal Campanilla: nearest at 5,715 m.

### 5.4 Cruise and port facilities, and what is missing

- **Cruise:** one feature, a pier in Old San Juan mapped as `amenity=ferry_terminal`. No cruise or port facility is recorded elsewhere on the island. The build's OpenStreetMap query asks only for stops, stations, ferry terminals, taxi stands, bicycle rental, charging stations, aerodromes and helipads, so port, harbour and pier features are not captured. Old San Juan has good last-mile data: Terminal Covadonga is 312 m from the pier and has 508 weekday calls on the busiest stop within 400 m of it.
- **Passenger counts:** none in the data (no FAA enplanements, port statistics or ferry ridership), so gateways cannot be weighted by visitor volume.
- **Ferries without a timetable:** none of the 7 OpenStreetMap ferry terminals carries a timetable: Fajardo's terminal (82 m from a stop of Fajardo's municipal feed, which has expired), an unnamed San Juan node, an unnamed node on a reservoir in Arecibo, the AcuaExpreso node at Hato Rey (no service in the ATI feed), the cruise pier, and two nodes in Ceiba that are 209 m and 550 m from the ATI Ceiba terminal and probably the same facility.
- **Públicos (carros públicos):** the main non-metro mode is not in any timetable. Only the 47 volunteer-mapped bus stations exist; 26 municipalities have no bus station in any source.
- **Rental cars, taxis, ride-hailing:** 9 taxi stands, a yes/no Uber list and the Overture places of type Transportation (206 listings, aggregate only). No fares or availability.
- **Real time:** none (the twin's own table says ATI's GTFS-Realtime feed is "en desarrollo").

### 5.5 Eastern region (Porta del Mar), Vieques and Culebra

| Area | Default places | Accomm. / Attr. / Gastr. / Visitor serv. | Any stop 400 m | Current scheduled 400 m | >=20 calls 400 m | Rail or ferry 400 m | Median distance to a ferry terminal |
|---|---|---|---|---|---|---|---|
| Porta del Mar (PRTC Eastern region, 15 municipalities incl. Vieques and Culebra) | 3,417 | 553 / 838 / 1,910 / 116 | 39.2% | 16.1% | 4.8% | 2.2% | 17.9 km |
| Porta del Mar without Vieques and Culebra | 3,030 | 418 / 717 / 1,803 / 92 | 40.2% | 14.0% | 5.4% | 0.3% | 19.6 km |
| Vieques | 247 | 81 / 76 / 76 / 14 | 34.8% | 34.8% | 0.0% | 10.9% | 2.8 km |
| Culebra | 140 | 54 / 45 / 31 / 10 | 27.1% | 27.1% | 0.0% | 27.1% | 1.2 km |

By municipality in Porta del Mar:

| Municipality | Default places | Scheduled stops (current / expired) | OSM stops | Any stop 400 m | Current scheduled 400 m | Municipal feed today |
|---|---|---|---|---|---|---|
| Canóvanas | 211 | 117 (117 / 0) | 1 | 83.4% | 83.4% | expiring |
| Ceiba | 97 | 1 (1 / 0) | 2 | 2.1% | 2.1% | no municipal system |
| Culebra | 140 | 1 (1 / 0) | 0 | 27.1% | 27.1% | no municipal system |
| Fajardo | 433 | 81 (0 / 81) | 5 | 70.4% | 0.0% | expired |
| Humacao | 414 | 18 (18 / 0) | 0 | 25.1% | 25.1% | current |
| Juncos | 152 | 128 (0 / 128) | 0 | 92.8% | 0.0% | expired |
| Las Piedras | 169 | 1 (0 / 1) | 1 | 15.4% | 0.0% | no municipal system |
| Loíza | 257 | 43 (43 / 0) | 2 | 59.5% | 55.6% | no municipal system |
| Luquillo | 260 | 0 (0 / 0) | 2 | 25.0% | 0.0% | no municipal system |
| Maunabo | 90 | 0 (0 / 0) | 0 | 0.0% | 0.0% | no municipal system |
| Naguabo | 168 | 0 (0 / 0) | 1 | 25.0% | 0.0% | no municipal system |
| Río Grande | 414 | 1 (1 / 0) | 1 | 6.5% | 0.0% | no municipal system |
| San Lorenzo | 193 | 159 (0 / 159) | 0 | 78.2% | 0.0% | expired |
| Vieques | 247 | 18 (18 / 0) | 0 | 34.8% | 34.8% | current |
| Yabucoa | 172 | 0 (0 / 0) | 1 | 14.5% | 0.0% | no municipal system |

Transport links in the data:

- **Ferries (ATI):** Ceiba to Vieques (CI, 12 trips weekdays, 16 Saturday and Sunday), Ceiba to Vieques Mosquito (CM, 4 weekdays only), Ceiba to Culebra (CC, 16 weekdays, 18 weekends); the median crossing is 45 minutes. Four ATI ferry terminals serve the islands (Ceiba, Culebra, Vieques Isabel II, Vieques Mosquito); the two Vieques terminals carry no municipality in the file (11 scheduled features, four of them ferry terminals, fall outside the shoreline-clipped boundaries).
- **Airports:** Vieques VQS, Culebra CPX, Ceiba RVR, Humacao X63 (FAA public use); Fajardo FAJ and a seaplane base (OpenStreetMap). No scheduled bus serves any of them.
- **Vieques municipal bus:** 1 route, 19 stops, 4 weekday trips, feed valid to 2027-12-31. 32.8% of Vieques' 247 default places are within 400 m of one of its stops and 10.9% within 400 m of an ATI ferry terminal (34.8% either); none is near a stop with 20 or more calls.
- **Culebra:** no municipal system, no bus stop of any source. The 27.1% of Culebra places near a "scheduled stop" are all near the ferry dock (72.1% are within 2 km of it).
- **Land side:** the easternmost ATI bus stop is in Canóvanas. The Ceiba ferry terminal is 31.5 km from the nearest ATI bus stop and 10.4 km from the nearest other scheduled stop, which belongs to Fajardo's municipal feed (expired 2026-06-15). In the scan from SJU the Ceiba, Vieques and Culebra terminals are never reached.
- **Eastern mainland:** Canóvanas (83.4% of places near a current scheduled stop; ATI plus a municipal feed that ends 2026-10-31), Loíza (55.6%, ATI) and Humacao (25.1%, a current municipal feed with 18 stops) are served; Fajardo, Juncos and San Lorenzo show high any-stop shares only because of expired feeds; Luquillo, Naguabo, Yabucoa, Maunabo, Las Piedras and Río Grande have no place near a current scheduled stop. Mona Island has 4 default places and one OpenStreetMap airfield run by the Department of Natural and Environmental Resources; no scheduled service.

## 6. Question 4: journey times from SJU (prototype)

### 6.1 Method and what the data allow

- **Algorithm:** earliest-arrival scan in rounds (connection scan with RAPTOR-style rounds): at most 3 boardings (2 transfers), walking links up to 400 m straight line at 4.8 km/h between stops, 180 s buffer on every boarding after the first, no buffer for the first boarding. Start 10:00 on a typical weekday. Horizon 4 hours. Places are reached from stops within 400 m (arrival at the stop plus walking); a place needs at least one vehicle leg.
- **Origin:** the 3 scheduled stops within 500 m of the FAA reference point of SJU (290, 465, 481 m; walking 3.6 to 6 minutes). The reference point is the airfield centre, not the terminal door; I widened the radius from 400 m to 500 m so the curbside stops count.
- **Timetable used:** weekday file, current feeds only: 2,925 trips, 71,258 stop-to-stop connections, 2,408 stops with calls. The 7 expired feeds are left out (372 trips); including them changes nothing because none of their stops is reachable.
- **What the files do not support, exactly:** trips have no stop ID, trip ID or route-pattern ID (a stop is a coordinate, a trip a list position), calls without a time are absent (so on routes that publish only timepoints the intermediate stops are missing), five Patillas routes are removed, there are no calendar exceptions or holidays, no frequency-based trips and no fare or transfer rules. The best this data can do is what is shown here: a schedule-based, timepoint-level estimate. Cross-feed transfers rely on a 400 m walk between coordinates.
- **Verification:** a brute-force computation of 1, 2 and 3 boardings gives the same earliest arrival at all 1,581 reached stops (0 mismatches).

### 6.2 Results: share of default places reachable within 60, 90 and 120 minutes

By category (transit = scheduled, weekday 10:00; drive = free-flow estimate, see 6.4):

| Group | Places | Transit 60 min | Transit 90 min | Transit 120 min | Drive 60 min | Drive 90 min | Drive 120 min |
|---|---|---|---|---|---|---|---|
| All default places | 26,579 | 9.9% | 13.9% | 18.3% | 54.8% | 72.7% | 86.1% |
| Accommodations | 3,106 | 9.1% | 11.1% | 12.7% | 45.8% | 61.0% | 76.3% |
| Attractions | 5,676 | 10.4% | 14.4% | 18.2% | 53.2% | 70.1% | 81.4% |
| Gastronomy | 17,178 | 9.6% | 13.8% | 19.0% | 57.0% | 75.9% | 89.7% |
| Visitor services | 619 | 20.4% | 24.2% | 27.9% | 54.3% | 66.2% | 76.6% |

By tourism region:

| PRTC region | Places | Transit 60 | Transit 90 | Transit 120 | Drive 60 | Drive 90 | Drive 120 |
|---|---|---|---|---|---|---|---|
| Porta Atlántico | 3,370 | 0.0% | 0.0% | 0.2% | 65.1% | 98.4% | 98.6% |
| Porta Capital | 8,505 | 29.9% | 42.0% | 55.4% | 98.4% | 98.5% | 98.5% |
| Porta Caribe | 3,090 | 0.0% | 0.0% | 0.0% | 1.6% | 82.5% | 97.5% |
| Porta Cordillera | 2,269 | 0.0% | 0.0% | 0.0% | 51.2% | 80.9% | 98.1% |
| Porta del Mar | 3,417 | 2.8% | 3.6% | 4.3% | 81.8% | 85.7% | 85.7% |
| Porta del Sol Norte | 3,274 | 0.0% | 0.0% | 0.0% | 0.0% | 9.7% | 80.3% |
| Porta del Sol Sur | 2,654 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 14.3% |

Of the 5,948 places reachable within 4 hours by transit, the median is 69 minutes. 10 of 78 municipalities have any place within 120 minutes and 2 reach 50% (`q4_sju_by_municipality.csv`). The scan reaches 1,581 stops by vehicle: 78 with one boarding, 533 with two, 970 with three. Within 120 minutes, 1,603 places need one boarding, 1,396 two and 1,870 three.

Stops reached by operator (all feeds loaded): ATI 1,299 of 1,437, San Juan municipal 182 of 219, Guaynabo 97 of 273, Bayamón 4 of 4; **none of the other 18 municipal feeds is connected** (no stop within a 400 m walk of an ATI stop within 3 boardings).

Sensitivity (share of default places within the stated time):

| Variant (all other rules unchanged) | Within 60 min | Within 90 min | Within 120 min |
|---|---|---|---|
| Main run: weekday 10:00, current feeds, 3 boardings, 3 min buffer | 9.9% | 13.9% | 18.3% |
| Including expired feeds | 9.9% | 13.9% | 18.3% |
| Weekday 07:00 | 8.7% | 13.2% | 19.7% |
| Weekday 14:00 | 7.7% | 13.4% | 18.3% |
| Weekday 18:00 | 7.8% | 13.0% | 17.9% |
| Saturday 10:00 | 2.8% | 11.5% | 17.2% |
| Sunday 10:00 | 0.4% | 1.9% | 5.5% |
| At most 2 boardings | 8.3% | 12.0% | 14.2% |
| At most 1 boarding | 6.6% | 6.8% | 6.8% |
| No transfer buffer | 10.3% | 14.5% | 19.1% |

Time of day matters little; the day of week matters a lot (Sunday only 5.5% within 120 minutes). Fewer boardings sharply lower reach: with one boarding only 6.8% of places are reachable at all.

Other origins, same rules (share within 60 / 90 / 120 minutes): Terminal Covadonga (Old San Juan) 11.3% / 16.6% / 20.4%; the Old San Juan cruise pier 9.0% / 14.5% / 18.8%; the Ceiba ferry terminal 0.0% / 0.0% / 0.0%. From the Ceiba terminal only the ferries connect: 65 places are reachable within 4 hours (Culebra 38, Vieques 27).

### 6.3 Plausibility checks (public facilities)

| From SJU at 10:00 to | Minutes (any means) | Boardings if by vehicle |
|---|---|---|
| Terminal Covadonga, Old San Juan | 55 | 1 |
| Tren Urbano Río Piedras | 57 | 2 |
| Tren Urbano Bayamón terminus | 78 | 2 |
| Terminal de Carolina | 118 | 2 |
| Caguas public transport terminal | 115 | 3 |
| Cataño ferry terminal | 123 | 2 |
| Ceiba / Vieques / Culebra ferry terminals | not reached | - |

These times are internally consistent (a bus to Old San Juan needs one boarding; the Tren Urbano needs a bus plus a train) but were not checked against the operator's journey planner or rider experience.

### 6.4 Driving comparison (estimate)

**Estimate, not a measurement.** Dijkstra over `roads.bin` from the road nearest SJU (623 m from the reference point, a primary road), one-way rules obeyed, the planning speeds of `roads.py` (motorway 90, trunk 75, primary 55, secondary 48, tertiary 40, residential 25 km/h; these are planning ratios, not speed limits), a 20 km/h connector from the road to the place, no traffic, signals, tolls, parking or waiting. It was not validated against measured drive times (median 83 minutes to Porta Caribe places). Places with no road path from the main graph, mainly Vieques, Culebra, Mona and a few remote sites, count as unreachable: 3.3% of default places.

Where transit reaches a place within 120 minutes, it takes a median 58 minutes against 13 by car (ratio 4.4, inter-quartile 3.6 to 5.5). Of the places within 60 minutes of SJU by car, 17.6% are within 60 minutes by transit and 32.9% within 120.

## 7. Question 5: data problems that would distort the analysis

| Problem | Count | Effect | What to do |
|---|---|---|---|
| Expired timetables | 7 operators, 966 stops (25.1% of 3,847); Ponce ended 2024-12-31 (643 days ago), Hatillo 2025-12-31, Cidra 2026-01-15, Caguas 2026-01-31, San Lorenzo 2026-02-28, Fajardo 2026-06-15, Juncos 2026-07-31; one more ends 2026-10-31 (Canóvanas, 92 stops) | 2,320 default places count as near only because of them; the any-stop measure, `pop_served_pct` and the 800 m gaps layer all include them | Evaluate feed status at build time and per stop; show both counts. Expiry means the published timetable does not cover today, not that service stopped. Ask the operators for new feeds (OUTREACH_TRANSIT_DATA.md) |
| Stale place fields | 112 default places lack a 400 m flag they should have (111 in Jayuya); 892 places in the file (683 on the default basis) have a `transit_m` that differs by more than 2 m from today's stop list: 183 in Jayuya and 709 elsewhere; the published value is the longer one in 892 of the 892 cases | Jayuya shows 0.0% instead of 70.7%; the nightly refresh rewrites stops but never `places.json` | Compute place access fields in a function called by both `build.py` and `refresh_network.py` |
| Wrong stop coordinates | 58 Jayuya stops had positive longitudes (fixed in `transport.json`); 1 Jayuya stop (9 weekday calls) is still 44 km from Jayuya (lng -66.1126), the only municipal stop more than 3 km outside its own municipality; 13 scheduled stops are over 150 m from any road (2 over 500 m) | A bad stop creates false "served" places (or false gaps) near its wrong position | Add a sanity check to `parse_gtfs`: distance to the operator's municipality and to the nearest road; drop or flag outliers |
| Duplicate stops | 905 pairs of scheduled stops within 30 m (737 same operator, 168 across operators: ATI with San Juan 92, ATI with Guaynabo 43, ATI with Bayamón 25, ATI with Canóvanas 5, ATI with Caguas 2, Juncos with San Lorenzo 1); 122 locations hold 271 stop IDs; 506 OSM bus stops and stations: 394 tagged AMA (whose routes are already in the ATI feed), 226 within 100 m of a scheduled stop (2 within 30 m, which the build should have folded) | Inflates stop counts and "stops per municipality"; hardly changes distances | Fold OSM stops within 100 m and flag cross-operator pairs as one physical stop |
| Calls missing from the trip files | 8.9% of weekday calls (78,414 of 86,067); 844 locations (22.8%) have none; Caguas keeps 162 of 1,836, Juncos keeps 96 of 1,264, Bayamón keeps 170 of 1,736, San Lorenzo keeps 132 of 1,291, Patillas keeps 15 of 391 | Journey times and the timetable replay understate municipal service; weekend flags rely on the route calendar for these | Interpolate untimed calls (GTFS rule) or write all calls with a flag; keep stop IDs in the trip files |
| Route/stop mismatches | 5 Patillas routes have a non-geographic stop order and 0 trips in the file; 103 of 118,782 bus hops are implausible (zero or negative time over 500 m, or over 100 km/h in a straight line); 1 stop with no route and no weekday trip | Small; they affect individual connections, not shares | Keep the `order_note` rule; reject hops above a speed limit in `parse_gtfs` |
| Zero-trip stops | 1 scheduled stop. 1,777 of 2,881 current stops have Saturday service, 94 have Sunday service | Weekend access is almost entirely ATI, Guaynabo and Vega Alta | Carry Saturday and Sunday calls per stop |
| No timetable at all | 15 municipal systems in the NTD list and the públicos authority publish no feed; 24 municipal systems do; públicos are in no feed; 41 of 78 municipalities have no scheduled stop | Absence of a stop is not absence of transport | Say so in every label |
| Municipality of stops and places | 11 scheduled features have no municipality (piers and shoreline stops, up to 1.0 km from a polygon); 331 default places (1.2%) fall outside every polygon and take the nearest centre | Municipal stop counts miss the Vieques, Cataño and San Juan ferry terminals; a few places may be assigned to the wrong municipality | Use nearest-polygon assignment with a distance limit |
| Resident file | `population_blocks.json` column 4 is metres to the nearest scheduled stop (capped at 9,999; 6,419 of 36,570 blocks capped), not housing units as the brief assumes; it includes expired feeds | A reader taking it for housing units would get nonsense; the distance ignores feed status | Document it; add a current-feeds distance |
| Airports list | FAA public-use list has 10; FAJ (Fajardo) is only in OpenStreetMap; HANDOFF says the old 14-record airports file is still published | Gateway tables are incomplete | Next full build (already fixed in code) |
| Personal data check | `places.json` carries business name for all 35,118 places, address for 28,810 and website for 9,683; some may identify individuals (sole traders). Stop names can embed business or organisation names. No email pattern in `transport.json` or `operators.json`; no personal cloud link in `operators.json` | Not printed here. Anything published from this analysis must stay aggregate | Keep access series aggregate; do not add names to new files |

A further caution on places: 1,501 default places share a map point with another place (up to 18 at one point), so their distances are identical; counts of places near transit are counts of listings, not of businesses or visitors.

## 8. Question 6: recommended method

### 8.1 Principle

Link each tourism place to transport in three layers, from most to least certain: (1) the nearest *scheduled stop with a current timetable* and what it offers; (2) a walking-distance check on the road graph; (3) hub and gateway proximity and journey times. Publish the layers as separate, labelled fields. Do not merge them into one score: the weights would be a policy choice that FPR has not made, and a score would hide that 64% of places have no current scheduled stop within 800 m.

Access classes for the default basis (computed from the Tier 1 distances; a candidate legend):

| Access class (default basis) | Places | Share |
|---|---|---|
| frequent: current scheduled stop within 400 m with at least 20 weekday calls | 5,664 | 21.3% |
| basic: current scheduled stop within 400 m (fewer than 20 calls at every such stop) | 2,860 | 10.8% |
| near: current scheduled stop 400-800 m away | 1,122 | 4.2% |
| paper only: no current scheduled stop within 800 m, but an expired-feed or volunteer-mapped stop within 800 m | 5,100 | 19.2% |
| none: no stop of any kind within 800 m | 11,833 | 44.5% |

The 16,933 places in the last two rows are where a hub connection matters: 66.9% are within 5 km and 91.0% within 10 km of some gateway (airport, ferry terminal, rail station or bus terminal, counting the volunteer-mapped ones); for all default places the median distance to a bus terminal is 2.7 km, to an airport 12.2 km, to a ferry terminal 22.5 km, to a rail station 34.6 km.

### 8.2 Tiers

| Tier | What it adds | Needs road graph | Build cost (measured) | Added first-load weight (gzip) | Status |
|---|---|---|---|---|---|
| 0. Fix and relabel | Rebuild stale place fields; call the old field "any mapped stop"; show feed status | No | seconds | 0 | Do first |
| 1. Service-qualified stop (cheap, robust) | `ts_m`, `ts_calls`, `ts_we`; shares at 400 and 800 m per area; access classes | No | 1.5 s for 15 stop sets on 35,118 places (the three fields need three of them); 3.5 s for the whole script | 135 KB in `places.json`, or 66 KB as typed columns; areas about 9 KB (municipalities) and 14 KB (barrios) | Ready; checked two ways |
| 2. Walking distance | `tw_m`; share within 400 m walking per area | Yes (`roads.bin`; optional full OSM walking graph) | 5.0 s end to end with `roads.bin` (0.9 s of searches); a full OSM graph adds a one-off read of the extract (11.8 to 60.9 s over 5 runs) and 2.2 s per run in the final run | 40 KB (JSON) or 19 KB (typed column) | Ready as an estimate |
| 3. Gateway journey times | `gw` times by transit and by car from named gateways; area series | Transit scan: no. Driving comparator: yes | timetable 0.2 s, scan 0.02 s per origin and departure, driving graph 4.2 s once | 67 KB per gateway (JSON, three fields) or 27 KB as typed columns | Prototype; not ready to publish beyond the San Juan metro |
| 4. Data to obtain, not compute | Current municipal feeds; untimed calls; carros públicos routes and terminals; ATI GTFS-Realtime; cruise and port facilities; ferry operators other than ATI; sidewalks and footpaths | - | - | - | Open requests; see `OUTREACH_TRANSIT_DATA.md` |

### 8.3 Per-place fields (name, unit, definition)

| Field | Unit | Definition | Tier |
|---|---|---|---|
| `ts_m` | metres (integer, 99,999 cap) | Straight-line distance to the nearest scheduled stop whose operator feed has not ended on the build date. Scheduled = ATI or municipal GTFS. Excludes OpenStreetMap-only stops, airports, taxi stands and chargers. Replaces the use of `transit_m` for access statements. | 1 |
| `ts_calls` | calls per weekday (integer; missing = none within 400 m) | Largest `trips_weekday` among current scheduled stops within 400 m: scheduled stop events on a typical Wednesday, both directions if served. A frequency proxy, not a headway. | 1 |
| `ts_we` | bit flags (1 = Saturday, 2 = Sunday; missing = none in the data) | OR of the Saturday and Sunday flags of current scheduled stops within 400 m, taken from the feed calendar inside `parse_gtfs` (not by coordinate matching). Missing means no weekend service in the published feed. | 1 |
| `tw_m` | metres (integer; missing = more than 1,000 m or no road within 150 m) | Walking distance along mapped roads (`roads.bin`, motorways excluded, one-way rules ignored) from the place to the nearest current scheduled stop, including connectors. An estimate: no footways, sidewalks, stairs or crossings. | 2 |
| `transit_m`, `transit_400m`, `nearest_stop` | unchanged | Keep for continuity; relabel as "nearest mapped stop of any kind, including expired timetables and volunteer-mapped stops". | 0 |
| `gw_t_<id>`, `gw_b_<id>`, `gw_d_<id>` | minutes; boardings (1 to 3); minutes | Per gateway `<id>` from `gateways.json`: earliest scheduled-transit arrival minutes (weekday 10:00, at most 3 boardings, walking links up to 400 m at 4.8 km/h, 3-minute buffer; missing = not reached within 240 minutes), boardings, and free-flow driving minutes (planning speeds, no traffic; missing = no road path). Start with SJU and Old San Juan. | 3 |

Nearest hub of each kind (rail station, ferry terminal, airport, bus terminal): compute in the browser from `gateways.json` (about 5 KB gzip, 141 records) rather than storing per-place fields; storing `hub_m` and `hub` for every place would add about 151 KB gzip.

### 8.4 Per-area series (municipality, tourism region, barrio)

All are shares of default-basis tourism places in the area unless stated. Publish the denominator (`access_n`) and the date (`access_as_of`); suppress shares where `access_n` is below 10 (many barrios) and say so.

| Field | Unit | Definition |
|---|---|---|
| `acc_any400_pct`, `acc_any800_pct` | % of places | A mapped stop of any kind within 400 / 800 m (the legacy measure; equals `transit_pct` at 400 m once the stale fields are rebuilt). |
| `acc_cur400_pct`, `acc_cur800_pct` | % of places | A current scheduled stop within 400 / 800 m. |
| `acc_freq400_pct` | % of places | A current scheduled stop with 20 or more weekday calls within 400 m (state the threshold in the field's metadata; 10 and 40 can be added). |
| `acc_sat400_pct`, `acc_sun400_pct` | % of places | A current scheduled stop with Saturday / Sunday service within 400 m. |
| `acc_hub400_pct`, `acc_hub800_pct` | % of places | A rail station or ferry terminal within 400 / 800 m. |
| `acc_walk400_pct` | % of places | Walking distance (Tier 2) of 400 m or less to a current scheduled stop. Estimate. |
| `acc_paper_pct` | % of places | Places whose only stop within 400 m comes from an expired timetable or from OpenStreetMap: the "served on paper" gap. Together with `acc_cur400_pct` it explains the difference from `acc_any400_pct`. |
| `stops_current`, `stops_expired`, `stops_osm` | count | Stops by feed state in the area, with `feed_end` (latest end date of the operators serving it). |
| `pop_served_freq_pct`, `pop_served_sat_pct` | % of residents | Same tests for residents (Census block centres), next to the existing `pop_served_*` fields. |
| `gw_<id>_t60_pct`, `_t90_pct`, `_t120_pct`, `_d60_pct`, `_d90_pct`, `_d120_pct` | % of places | Share reachable within 60 / 90 / 120 minutes from a gateway by scheduled transit (`_t`) and by car estimate (`_d`). Publish only where the transit scan reaches the area; otherwise show "no scheduled link in the data". |
| `access_n`, `access_as_of` | count; date | Denominator and the build or feed date. |

### 8.5 Added file size and build time (all measured)

| Addition | Raw added | Gzip added |
|---|---|---|
| places.json today (reference) | 16.7 MB | 2.881 MB |
| Core three fields in `places.json` (`ts_m`, `ts_calls`, `ts_we`) | 636 KB | 135 KB |
| Two fields only (`ts_m`, `ts_calls`) | 559 KB | 132 KB |
| Five fields (core three plus `hub_m`, `hub`) | 1,388 KB | 286 KB |
| Six fields (adds `tw_m`) | 1,516 KB | 326 KB |
| Nine fields (adds `sju_t`, `sju_b`, `sju_d` for one gateway) | 2,051 KB | 393 KB |
| Alternative: core three as typed columns in a separate file | 171 KB | 66 KB |
| Alternative: all nine as typed columns | 514 KB | 180 KB |
| `municipalities.json`: 26 new fields x 78 | 46 KB | 9 KB |
| `barrios.geojson`: 4 new fields x 901 | 69 KB | 14 KB |
| `transport.json`: `calls_sat`, `calls_sun`, `feed` on 3,847 stops | 148 KB | 4 KB |
| `gateways.json` (new, 141 records) | 29 KB | 5 KB |

The figures come from re-serialising the real file in memory with the real values added (same JSON settings as `build.py`; the re-serialised baseline has exactly the same length in bytes as the published file) and gzip level 6. The values used for the per-area fields are random numbers with one decimal, which is why their gzip size is not trivially small. Load time on a throttled connection was not measured.

Build time: each figure in the tier table is the measured time of the step on this machine, and timings vary two to three times between runs with machine load. None needs more than a minute, so adding Tiers 1 to 3 to `build.py` and Tier 1 plus Tier 3 to the nightly refresh is practical. The refresh currently never touches `places.json`; either call the access computation from `refresh_network.py` or compute Tier 1 in the browser from the nightly `transport.json` and `operators.json`.

### 8.6 Which parts need the road graph

- **Tier 2 (`tw_m`, `acc_walk400_pct`):** yes. `roads.bin` is enough for the aggregate; a full OSM walking graph (rebuilt from the extract: a one-off read of 11.8 to 60.9 s, then 3.3 s to build; 11.4 MB in the `roads.bin` layout if it were shipped) is only needed if individual-place accuracy matters. Do not ship either graph to the browser for this; compute at build time.
- **Tier 3 driving comparator:** yes, same graph, one-way rules obeyed.
- **Tier 1 and the transit scan:** no.

### 8.7 Labels the app must show

- **Schedule-based, not real-time.** Every transit figure comes from published timetables (a typical Wednesday, Saturday or Sunday); no live positions exist. Holidays and calendar exceptions are not modelled.
- **Feed coverage and date.** "24 of 39 municipal systems publish a feed; 7 feeds have expired (list); 15 publish none; públicos are not included." Always show the feed end date next to a stop or area and the build or refresh date.
- **Straight line versus walking.** Say which one a number uses. Walking figures read "estimated walking distance along mapped roads; excludes footpaths, sidewalks, stairs, crossings and barriers."
- **Estimates and proxies.** `ts_calls` is a frequency proxy, not a headway. Journey times read "scheduled estimate, weekday 10:00, up to 3 boardings, walking up to 400 m at 4.8 km/h, 3-minute transfer buffer; not door to door." Driving times read "free-flow estimate at planning speeds; no traffic, signals or parking."
- **What counts as a stop.** "Current scheduled stop" versus "mapped stop (no timetable or expired)". Show the old measure only with the second label.
- **Missing is not zero.** "No Saturday service in the published data" is not "no Saturday service"; "no scheduled link in the data" is not "no link".
- **Counts are listings.** Places are Overture listings (confidence 0.50 or higher, no places of worship), not businesses, rooms or visitors.
- **Small numbers.** Suppress or flag shares for areas with fewer than 10 places.

### 8.8 Fix first (these change the numbers more than any new method)

1. Rebuild the place access fields from the current stops (111 Jayuya places wrong today) and call that code from the nightly refresh too.
2. In `parse_gtfs`, store per stop: feed state, Saturday and Sunday calls, first and last weekday departure. This replaces the coordinate matching used in this spike.
3. Write untimed calls to the trip files (interpolate between timepoints) and keep stop IDs, so municipal feeds are not understated by up to 96%.
4. Fold OpenStreetMap stops within 100 m of scheduled stops, mark cross-operator duplicates, correct the 1 Jayuya stop 44 km off, and give every pier stop a municipality.
5. Add port, harbour and cruise-pier features to the stop inventory (OpenStreetMap `harbour`, `landuse=port`, `amenity=ferry_terminal`) and take the FAJ airport from OpenStreetMap until the FAA file is refreshed.
6. Renew or replace the 7 expired municipal feeds; a Ponce feed alone would move about 921 places from "on paper" to "served" if the service still runs.

### 8.9 What I would not claim

- That a place is "accessible by public transport", "car-free" or "reachable" for visitors. The data show scheduled stops near a listing, not whether a visitor can use them (luggage, accessibility, safety, fares, language, real timetable adherence).
- Anything real-time, or that a timetable is running today; expired feeds mean "not covered by a published timetable".
- That no stop means no transport: públicos, taxis, ride-hailing, rental cars, tour shuttles and informal ferries are outside the data.
- A walking time or a door-to-door journey time. Only distances along mapped roads and stop-to-stop schedule times are available.
- Service quality from `trips_weekday` alone. It mixes directions and gives no headway, hours or reliability.
- Comparisons across municipalities as if feeds were equally complete: Ponce's 0.1% reflects a lapsed feed, not an absence of buses.
- Visitor numbers, demand, equity or causality. Counts are listings; shares over 78 places show patterns, not causes.
- Journey times outside the San Juan metro area. Only ATI, San Juan, Guaynabo and Bayamón stops connect today.

### 8.10 Decisions for FPR

- Whether to rename the published "within 400 m of transit" measure now (recommended) or keep it as is until Tier 1 is live.
- Whether Tier 1 fields live in `places.json` (+135 KB gzip) or in a separate typed-column file (+66 KB gzip, needs the lazy loading planned as Phase 3 item 3).
- Which gateways to publish first (only gateways inside the San Juan metro area connect to scheduled transit today) and which departure times.
- Who contacts the 7 operators with expired feeds, and ATI about GTFS-Realtime, untimed calls and stop IDs (a draft exists in `OUTREACH_TRANSIT_DATA.md`).
- Review path before anything new goes on a public page: the dictionary page is `noindex` until Compliance has reviewed pages that describe grant-funded data; new access entries should follow the same path. These transit series use no federal grant data.

## 9. Scripts, outputs and reproducibility

All files are in this folder. Run `<repo>/venv/Scripts/python.exe run_all.py` to rebuild everything (1.8 minutes in the last run, more when the machine is busy; reading the OpenStreetMap extract alone took 11.8 to 60.9 s over 5 runs). Scripts write only here and read the repository without changing it (`sys.dont_write_bytecode` is set so no `.pyc` is written into it).

| Script | What it does |
|---|---|
| `common.py`, `service.py`, `walknet.py`, `csa.py` | Loaders and shared code: projection, stop sets, feed status, stop locations, walking engine, scan |
| `01_baseline.py`, `01b_stale_check.py`, `01c_bruteforce_check.py`, `07b_location_sensitivity.py` | Q1: shares by stop set, category, region, municipality, type; stale-field check; brute-force and location-level checks. Outputs `q1_*.json`, `q1_by_municipality*.csv`, `q1_by_region.csv` |
| `02_walk.py`, `02b_osm_walk_ways.py`, `02c_walk_osm_compare.py`, `02d_muni_graph_diff.py` | Q2: walking distances on `roads.bin`, OSM inventory, full OSM walking graph comparison. Outputs `q2*.json`, `q2_walk_by_municipality.csv`, `q2_sample_ids.npy` |
| `03_gateways.py`, `03b_east_and_osm.py` | Q3: gateways, ferry routes, Eastern region, land links. Outputs `q3_gateways.json`, `q3b_east_and_osm.json` |
| `04_journey.py`, `04c_check_csa.py` | Q4: timetable scan, driving estimate, brute-force check. Outputs `q4_journey.json`, `q4c_check.json`, `q4_sju_by_municipality.csv`, `q4_sju_times.npz` |
| `05_problems.py` | Q5: data problems. Output `q5_problems.json` |
| `06_design_numbers.py`, `07_extra_and_tables.py`, `make_report.py` | Q6 sizes and classes, extra numbers, tables, this report. Outputs `q6_design_numbers.json`, `q_extra.json`, `tables.md`, `REPORT.md` |
| `run_all.py`, `record_history.py`, `99_privacy_scan.py`, `timings.json`, `timing_history.json`, `logs/` | Runner, wall-clock time per script and over runs, privacy scan of the outputs, console output |

Wall-clock time per script on this machine (12 cores, Python 3.12, numpy 2.5, shapely 2.1; the machine was shared, so figures vary): `01_baseline.py` 4.2 s, `01b_stale_check.py` 7.3 s, `01c_bruteforce_check.py` 7.3 s, `07b_location_sensitivity.py` 1.4 s, `02_walk.py` 10.7 s, `02b_osm_walk_ways.py` 16.1 s, `02c_walk_osm_compare.py` 10.5 s, `02d_muni_graph_diff.py` 1.0 s, `03_gateways.py` 1.5 s, `03b_east_and_osm.py` 1.7 s, `04_journey.py` 7.4 s, `04c_check_csa.py` 1.3 s, `05_problems.py` 6.2 s, `06_design_numbers.py` 7.5 s, `07_extra_and_tables.py` 3.0 s, `record_history.py` 0.6 s, `99_privacy_scan.py` 17.6 s.

### Limits of this spike

- One snapshot (places and stops of 2026-10-02) and one day type per scan; no validation against real trips or counts.
- Walking and driving are estimates from OpenStreetMap-based graphs; no field check.
- SJU was located by the FAA reference point, not the terminal door.
- "Eastern region" is read as the PRTC region Porta del Mar; a different definition of the east would change the Q3 counts.
- The 1,000-place walking sample is random, but the island run covers every place, so the island figures do not depend on it.
- Not tested: the app's browser code; I did not open the site.

### Process notes

- Three files that were in this folder at first were not created by this analysis and were not used: `ati_gtfs.zip`, `ati_open.html`, `ati_urbana.html` (they appeared at 17:10 to 17:11 on 2026-10-05, after the folder was created, from some other process, and were gone again by the end of the work). The brief says no network use; the GTFS zip (2,234,433 bytes) has the same size as the repository's cached ATI feed.
- While this analysis ran, other files in the repository changed: a check at the end found 42 files modified since 17:00 (the Spanish-interface work: `i18n.py`, `i18n_src/`, `site/index.html`, `site/js/app.js`, `README.md`, `docs/` and others) and a git commit had appeared. None is in `site/data`, `cache` or `__pycache__`. They come from another process; this analysis only read `site/data/*`, the cached OpenStreetMap extract and the repository's `roads.py` and `municipalities.py` (imported with bytecode writing off).
- A privacy scan (`99_privacy_scan.py`) compared every text output in this folder with the business names, addresses and websites in `places.json` and with e-mail patterns. No website or e-mail matched; the only name and address matches are generic phrases and public place names (for example the neighbourhood names Old San Juan and Río Piedras, the Ceiba ferry terminal and the phrase "rest stop"). `q3_gateways.json` keeps names only for airports, ferry terminals and stations.
- One `git status --short` was run early, to check that no stray files had been written. It is read-only in effect but can refresh the index's timestamps, so strictly it touched git state. It showed one untracked file (`site/js/i18n.js`) that is not from this analysis. No other git command was run, and these scripts wrote no file, cache or git state inside the repository.
