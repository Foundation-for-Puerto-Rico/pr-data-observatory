# Transportation upgrade: what the observatory has, what open data can add, and the order to build it (2026-11)

HANDOFF decision 105. Francis, 2026-11-13: "Check the information on transportation the observatory has, then search what additional information we can add to the map. There has to be more information about transportation and ways to display it. This is very important for gap analysis we need to conduct." And: "make visible the gaps where transportation routes can be added. Maybe this is a simulated layer that we can add in a knowledge area and connect the transportation systems between municipalities."

Prepared with Claude (AI). Every source below was opened and counted on 2026-11-13, without a key.

## 1. What the observatory has today

| Topic | What | Where |
|---|---|---|
| Timetabled transit | 165 routes, 3,781 stops and 3,297 weekday trips of 44 operators (ATI and 24 municipal feeds), refreshed every night; service by hour; residents far from service; integration points | Layers Transit routes and Transit stops; Transit tab; 3D time bar |
| Other transit points | 459 bus stops, 91 bus stations, 16 rail stations, 13 ferry terminals, 25 airports, 11 EV chargers, 9 taxi stands | Layers Stations, terminals and airports; Taxi stands and EV charging |
| Públicos | 16 routes from OpenStreetMap, no timetable | Transit routes layer |
| FPR's traced routes | 38 stretches, Eastern Region | Layer Municipal routes mapped by FPR |
| Roads | A routable graph of the drivable roads (OpenStreetMap) | Route planner, walking distances, area tools |
| Commuting (survey) | Long commutes, drive alone, transit, walk, work from home, households with no vehicle, by municipio and year (ACS) | Economy and Infrastructure indicators |
| Bridges | Bridges, and bridges in poor condition, by municipio, 2016-2025 (FHWA) | Infrastructure indicators |
| Air and sea gateways | Air passengers and departures, ferry passengers, by municipio | Infrastructure indicators |
| Walk to transit | Residents within 400 m of a stop, the climb on the walk | Exposure and climb indicators |
| Analyses | Route analysis (97 routes compared); barrio ranking of transit need (not published) | `route-analysis.html`; `docs/analysis/transit-needs-2026-11/` |

**What was missing for a gap analysis:**

1. **Where people travel.** Nothing said how many people go from one municipio to another. The plan of 2026-10 lists "no origin-destination data" as a limit.
2. **Públicos.** Sixteen routes, when públicos carry much of the travel between towns.
3. **Traffic.** No road has a vehicle count on the map.
4. **Road safety.** No crash data.
5. **Bridges, airports, ports, EV chargers** are counted by municipio or drawn from volunteer maps, not from the federal inventories.
6. **Between municipios.** Every transit measure stops at the municipal line.

## 2. What open data can add (checked 2026-11-13)

| # | Source | What it gives for Puerto Rico | Licence | Status |
|---|---|---|---|---|
| 1 | Census Bureau, County-to-County Commuting Flows, ACS 2016-2020 | Workers by municipio of residence and of work: 1,626 one-way flows, 532,691 workers between municipios, with margins of error | US Government work | **Built in this change** |
| 2 | Instituto de Estadísticas and ACT, Mapa de rutas de porteadores públicos (2020-03-19) | 361 rows, 334 público routes with their lines, codes and names | CC BY | **Built in this change** |
| 3 | FHWA HPMS 2025 (`geo.dot.gov`, `HPMS_FULL_PR_2025`) | 262,462 road segments with daily traffic (AADT), trucks, lanes, speed limit, pavement condition | US Government work | Step 2 |
| 4 | NHTSA FARS, through the Bureau of Transportation Statistics (NTAD) | Fatal crashes: 297 in 2023 (final), 275 in 2024 (first release), with pedestrians counted; a combined file holds 1,383 records for 2020-2024 | US Government work | Step 3: counts by municipio and year only (the exact place and time of a death can identify a person; `wanted.json`, `crashes`) |
| 5 | FHWA National Bridge Inventory (NTAD) | 2,433 bridges as points, with condition, year built, daily traffic and detour length | US Government work | Step 4 (the municipio counts are already live) |
| 6 | FAA aviation facilities (NTAD) | 47 airports, heliports and seaplane bases | US Government work | Step 4 |
| 7 | BTS National Census of Ferry Operators (NTAD) | 5 terminals and 6 route segments, with passengers and vehicles carried | US Government work | Step 4 |
| 8 | US DOE Alternative Fuels Data Center (NTAD copy) | 26 fuelling stations (EV chargers with their connectors and power); OpenStreetMap has 11 | US Government work | Step 4 (drop the telephone field) |
| 9 | FHWA National Highway System, National Highway Freight Network, Strategic Highway Network (NTAD) | 9,598 NHS segments, 38 freight-network segments, 3,612 STRAHNET segments | US Government work | Step 2, as classes of the traffic layer |
| 10 | FHWA Travel Monitoring stations (NTAD) | 31 continuous count stations | US Government work | Step 2, as points |
| 11 | FHWA National Tunnel Inventory (NTAD) | 4 tunnels | US Government work | Step 4 |
| 12 | BTS National Transit Map (NTAD) | 5,550 stops and 124 routes; the observatory already reads the same feeds directly and fresher | US Government work | Not needed |

**Looked for and not usable today:**

- **All crashes, not only fatal ones.** The Observatorio de Seguridad Vial (CST and UPR) has dashboards; no open download or licence was found. Ask: CST.
- **Live bus positions (GTFS-Realtime).** ATI still lists it as in development. The request draft is in `OUTREACH_TRANSIT_DATA.md`, not sent.
- **Jobs by block (LEHD LODES).** Does not cover Puerto Rico.
- **USDOT transportation cost burden and disadvantage indexes.** The tract files have no Puerto Rico rows.
- **Park-and-ride lots, truck parking, weigh stations, intercity bus.** The federal files have no Puerto Rico rows.
- **Current público routes.** The 2020 list is the only one; NTSP publishes none. Ask: NTSP and ACT for an updated list.
- **Travel speeds and congestion (NPMRDS).** Licensed to agencies, not open.

## 3. The order to build it

Each step is one pull request that shows on the site.

1. **Connections between municipios (this change).** The Knowledge Area page `transit-links.html`, the layers Público routes (2020 list) and Simulated connections between municipios, the data files and their documentation: `docs/transit-links.md`.
2. **Traffic on the roads (built 2026-11-13, `docs/traffic.md`).** A line layer of the roads with a traffic count (HPMS 2025), wider where more vehicles pass, with trucks, lanes and speed limit in the pop-up, and the count stations. Then the simulated connections can say how much traffic the road they follow carries.
3. **Road safety (built 2026-11-13, `docs/road-safety.md`).** Fatal crashes by municipio and year (FARS 2020-2024), with pedestrian deaths, as indicators and on the page. No points.
4. **The federal inventories as layers (built 2026-11-14, `docs/transport-inventories.md`).** Bridges and tunnels with their condition, airports and heliports, ferry routes with passengers (2024 census), public EV charging stations, completing the volunteer-mapped points.
5. **Gap analysis, second pass (built 2026-11-14, `docs/transit-links.md`, last section: time by timetable, need at each end, residents and bridges along each simulated connection; no ranking published).** Join steps 1 to 4 with what exists: households with no vehicle and poverty at each end of a connection, the barrio ranking of `docs/analysis/transit-needs-2026-11/`, journey time by timetable between town centres (with transfers), and the residents along each simulated connection. Publishing a ranking of where service should be added is a policy position: it needs leadership's approval first (plan decision 4).

## 4. Data gaps that open data cannot close (no requests will be sent)

**Retired 2026-11-16.** Francis: "I don't want to send data requests and just use the data available on the internet." The observatory works only from data a script can read from the internet. The gaps below stay as limits, stated on the pages (the Connections page's last finding and its notes); they are not pending work. If one of these sources is published openly later, the refresh checks of `refresh/sources.json` are the place to add it.


| Missing data | Who holds it | What it leaves open |
|---|---|---|
| A current list of público routes, with the date of each | NTSP, ACT | The list is of 2020; it decides whether a third of the travel between municipios has a route |
| The timetable feed of the 15 municipal systems that publish none, and of the 6 whose feed expired | Each municipio (`OUTREACH_TRANSIT_DATA.md`) | A missing feed looks like a gap |
| Crash records with location | CST, Observatorio de Seguridad Vial | Only fatal crashes are open |
| GTFS-Realtime | ATI | Service delivered, not only scheduled |
