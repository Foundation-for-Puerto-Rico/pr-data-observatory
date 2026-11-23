# Transit supply, demand and connections: analysis plan

**Status:** proposal, 2026-10-09. Nothing here is built yet. Numbers are from Snapshot 2026-10.

**Goal.** Understand the transit routes Puerto Rico has today, how much service each one offers, where people need it, and where routes could connect or feed each other. The observatory should then be able to point to places where a new route, a new connection or a timetable change would help most.

**The short answer.** We can measure **supply** well today, and the files now have what we need: trips grouped by route pattern, with exact stop times. We can measure **coverage** with small fixes. We can find **connections** once the transfer list checks timetables, not only distance. We **cannot measure demand (ridership)** yet. No ridership data is in the observatory, and commute flows (where people travel from and to) do not exist for Puerto Rico in the usual Census source. So the plan builds on what we have first (phases 1 to 3), uses proxies for demand while we ask for ridership (phase 4), and only then ranks places for new service (phase 5).

## What we can answer now, and what needs new data

| Question | Can we answer it now? | With what |
|---|---|---|
| How often does each route run, and when? | **Yes** | `trips.json` (weekday), `trips_sa.json`, `trips_su.json`: each trip's stop pattern (`k`) and stop times (`t`) |
| Who lives near service, and near frequent service? | **Mostly** | `population_blocks.json`, `exposure_*.json`; some measures still count expired timetables as service (phase 2 fixes this) |
| Where do routes of different operators meet? | **Partly** | `operators.json` → `transfers` (366 pairs of stops within 250 m), by distance only |
| Does a connection work in time (a short wait)? | **No, but buildable** | the same stop times, plus a transfer rule (phase 3) |
| How many people ride each route? | **No** | needs ridership data (phase 4) |
| Where do people travel from and to? | **No** | LEHD LODES has no Puerto Rico data (see `docs/proposal-2026-10.md`); needs another source (phase 4) |
| Where is a new route most needed? | **Not yet** | combines all of the above (phase 5) |

## What the observatory already has

- **Network.** 44 operators, 25 with a timetable feed (17 current, 7 expired, 1 expiring); 165 routes; 3,847 scheduled stops; 3,297 weekday trips (`meta.json` → `network`).
- **Timetables (format 2, since PR #14).** Trips that stop at the same places in the same order share one path along the road: 222 stop patterns on a weekday. Each trip keeps where its stops are on the path (`s`) and its stop times (`t`). 3,191 of 3,297 weekday trips follow their route's road line. About 8.9% of weekday stop calls have no time in the feeds and are not in the files.
- **Coverage.** Residents within 400 m (a quarter mile, straight line) of any scheduled stop: 925,788 of 3,285,874. Residents and housing units near stops with a current timetable, frequent service (20+ weekday departures) and weekend service, by municipality, barrio and tract (`exposure_*.json`). Tourism places near current and frequent stops (`place_access.json`).
- **Transfers.** 366 pairs of stops of different operators within 250 m, mostly ATI with San Juan (228), Guaynabo (69) and Bayamón (46) (`network.transfers`, layer "Integration points").
- **Demand proxies.** By municipality: share of workers who commute by public transportation, households with no vehicle, long commutes, workers (American Community Survey); jobs (QCEW); 35,118 tourism places; residents by 2020 Census block.
- **Tools.** The road network (`roads.bin`: 193,507 nodes, drivable roads only) with routing in the browser; the route planner, which reports residents and places within 400 m of a drawn route, overlap with existing routes, and nearby stops of other operators; and the prototypes from the visitor-access study (walking distance on roads, `walknet.py`; journey times with transfers, `csa.py`).

## Phase 1. Supply by route pattern (no new data)

Measure the service each route and pattern offers, hour by hour.

- **Measures, for each stop pattern and route:** trips per hour by hour of day; first and last trip (span of service); the usual wait between buses (headway) at peak and off-peak; weekday, Saturday and Sunday service; run time and average scheduled speed; length; whether the timetable is current.
- **Measures, for each stop:** departures per hour, routes and operators that serve it, and the longest gap in service during the day.
- **How.** From the stop times (`t`) and stop positions (`s`) of each trip, grouped by pattern (`k`). Stops are matched by their position on the pattern's path. A stop id per stop in the trips files would make this cleaner: add it to `trip_paths.py` as part of this phase.
- **Outputs.** A `transit_supply.json` file (one row per pattern and per stop), dictionary entries, a supply layer (routes drawn by frequency) and a table in the Transporte tab.
- **Size:** small to medium.

## Phase 2. Coverage and gaps, current service only

Who lives, works or visits near useful service, and who does not.

- **Fix first.** Count only current timetables everywhere. Today, `population_blocks.json` and the route planner still treat expired feeds as service. Ponce's feed ended 2024-12-31, for example.
- **Use walking distance, not straight lines.** Along mapped roads, walking is a median 1.42 times the straight line (visitor-access study). Promote `walknet.py` from the prototype to the build. Footpaths are not in the road file, so say "along mapped roads". **Built 2026-10-16** for tourism places (`walknet.py`, `tw_m`, the `acc_walk` shares) and for residents (`pop_walk_*`, the blocks' fifth value, `walk_cur` and `walk_freq`); see docs/visitor-transport-access-2026-10.md. The route planner's 400 m around a drawn route is still a straight line.
- **Weight by service, not only distance.** Residents within a 400 m walk of a stop with, for example, a bus every 30 minutes or better during the day, and of weekend service.
- **Outputs.** Coverage by municipality, barrio and tract with these definitions; a map of residents with no useful service; the same for jobs by municipality and for tourism places.
- **Size:** medium.

## Phase 3. Connections between routes and operators

Where routes meet, where they could feed each other, and whether a transfer works in time.

- **Timetable-aware transfers.** For each pair of stops of different routes within a short walk (start with 250 m, as today), measure the waits: for each arrival, the time until the next departure on the other route. Report the share of arrivals with a wait under 10 and under 20 minutes, by hour.
- **Near misses.** Routes that end or pass within 250 to 800 m of another operator's route with no stop near the other: candidates for a short extension or a new stop.
- **Feeder candidates.** Municipal routes whose ends are not near a frequent ATI line, Tren Urbano or a terminal, and frequent lines whose stops have no local route nearby.
- **Journey times.** Promote the journey-time prototype (`csa.py`: up to 3 boardings, 400 m walking links, 180 s transfer buffer) to answer "how long from each barrio to the main job and service centres, at 7:00 on a weekday". The visitor-access study found 18.3% of tourism places reachable from the airport (SJU) within 120 minutes by transit, against 86.1% by car.
- **Outputs.** A transfers file with waits, a "connections" layer, and journey-time maps from a short list of hubs (agreed with FPR).
- **Size:** medium to large.

## Phase 4. Demand: proxies now, ridership as it arrives

**Proxies we have, by municipality:** residents and density by block; households with no vehicle; workers who commute by public transportation; long commutes; jobs (QCEW); tourism places and lodging. They point to likely need. They are not ridership.

**Real demand data to request or obtain:**

| Source | What it gives | Access | Notes |
|---|---|---|---|
| National Transit Database (NTD), monthly ridership | Trips, vehicle miles and hours by **agency and mode**, by month | Public download | Not by route or stop. Good for trends and cost per trip. Check which Puerto Rico agencies report. |
| ATI (AMA buses, Tren Urbano, Metrobús, AcuaExpreso) | Boardings by route and stop: automatic passenger counters, fare cards or fare boxes | **Data request** | The most useful source. Ask what exists, at what level, and under what terms. |
| Municipal operators | Ridership logs by route | **Data requests** | Likely uneven; start with the municipalities with current feeds (San Juan, Guaynabo, Bayamón, Caguas). |
| Ferry passenger counts | Passengers by route | Listed in `wanted.json` (`ferry-census`, checked) | The only ridership-like row today. |
| On-board or household travel survey | Origins, destinations, purpose, transfers | New collection | Costly; consider only after the requests above. |
| Commercial mobile-location data | Origin-destination flows | Purchase | Privacy and cost questions; FPR decision. |

Add each of these to `wanted.json` so the gap is visible on the site.

**Size:** small to start (requests and NTD); the rest depends on what the sources share.

## Phase 5. Where new routes or connections are needed

Bring phases 1 to 4 together into a short list of places and corridors to look at first.

**First version built 2026-11-10** (`docs/analysis/transit-needs-2026-11/`, not on the site): the 746 barrios with 500 residents or more ranked by need (ACS proxies) and by the share of residents beyond 400 m of a stop with a bus every 30 minutes, and 19 places where routes of different operators come within 250 to 800 m without sharing a stop. It builds the parts of phases 2 to 4 it needs from open data; timed transfers, journey times and ridership are still to come.

- **Need:** residents (and later riders) with high proxies of transit need, such as no-vehicle households, density and long commutes.
- **Supply:** low or no current, useful service (phase 2), or long journey times to centres (phase 3).
- **Connection value:** a gap between existing routes that a short link or a timed transfer would close (phase 3).
- **Test candidates** with the route planner, which already reports residents, places, overlap with existing routes and nearby stops of other operators. Add frequency, run time and the transfers each candidate creates.
- **Output:** a ranked list of areas and corridors with the reasons behind each, for FPR's review. The ranking is a planning aid, not a demand forecast or an engineering study.

**Size:** medium, after phases 1 to 3.

## Decisions and data requests (who acts)

1. **FPR:** confirm the purpose and audience of the analysis (internal planning, partners, or the public site), because that decides how findings are worded and reviewed.
2. **FPR:** approve data requests to ATI and the municipal operators, and name who sends them.
3. **FPR:** choose the hubs for journey-time maps (for example SJU, Río Piedras, Bayamón, Caguas, Ponce, Mayagüez centres).
4. **FPR leadership:** a public recommendation for new routes or service changes is a policy position. It needs leadership approval before it is published.
5. **Development:** phases 1 to 3 can start now, in that order.

## Limits to state with every result

- **Públicos are not in any timetable.** They are a large part of transit in Puerto Rico. The observatory has 16 routes from OpenStreetMap (públicos and others), without times. Every "no service" finding must say this.
- **Timetables are not service delivered.** They show what operators publish, not what ran. Expired feeds (7 operators, 25.1% of stops) may still run, or may not.
- **Distances.** Straight line unless the result says "along mapped roads". The road file has no footpaths, sidewalks or crossings.
- **Survey data** (American Community Survey) have margins of error, are by municipality, and lag by one to two years.
- **No origin-destination data** until phase 4 brings it.
- **Data quality to fix along the way:** 905 pairs of stops within 30 m of each other; two Ponce trips whose times go back to the start of the day; about 8.9% of stop calls with no time.

## Related

- `docs/visitor-transport-access-2026-10.md` and `docs/analysis/visitor-access-2026-10/`: the visitor-access study, with the walking-distance and journey-time prototypes this plan builds on.
- `trip_paths.py`: the trips file format (format 2) and how trips follow the route lines.
- Data dictionary entries "Timetable replay files" and "Trip record".
