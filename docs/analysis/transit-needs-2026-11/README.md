# Where a new route or connection is most needed (phase 5, first version), 2026-11

Phase 5 of [the transit analysis plan](../../transit-network-analysis-plan-2026-10.md): a ranked list of barrios and of places between routes to look at
first, with the reasons behind each, for FPR's review. Open data only, nothing requested from operators, no key. Asked for by a colleague on
2026-11-10; prepared with Claude (AI).

**This is a planning aid, not a demand forecast or an engineering study.** It is not on the public site. A public recommendation of new routes or
service changes is a policy position, which the plan's decision 4 reserves for FPR leadership; nothing under `site/` reads these files.

| File | What it is |
|---|---|
| `transit_needs.py` | Reads `site/data` and writes the files below in about 5 seconds. `--check` recomputes for the date in `summary.json` and fails if a file differs (`tests/test_transit_needs.py` runs it). `--as-of YYYY-MM-DD` sets the day a timetable must still run on. |
| `findings_es.md`, `findings.md` | The results in Spanish and English: the island summary, the 25 barrios to look at first, the 15 best placed where the timetables are current, and the 15 places where routes of different operators come close without meeting. |
| `barrios.csv` | All 901 barrios: the 746 ranked first (500 residents or more), then the rest by GEOID, with every measure below. |
| `connections.csv` | Every pair of routes that come close (26), with the place each belongs to (19). |
| `summary.json` | The island totals, the rules and the as-of date. |

## Method

It brings together the parts of phases 2 to 4 that open data allow, at the barrio level.

1. **Need (phase 4, proxies).** From the ACS 2020-2024 five-year estimates by barrio (`acs_barrio.json`): households with no vehicle, poverty,
   residents 65 and over, and residents with a disability; and residents per km2 (2020 Census blocks over the barrio's land). Each becomes a
   percentile among the 746 barrios with 500 residents or more, and the need index (0 to 100) is their weighted mean, with the no-vehicle share counted
   twice. A barrio is marked "low reliability" when the margin of error of its no-vehicle share is larger than the share.
2. **Useful service (phase 2).** A stop whose operator's timetable still runs on the as-of day (its `feed.end` in `operators.json`, as the site
   reads it) and that has 2 or more weekday departures an hour on average from 7:00 to 19:00, which is a bus every 30 minutes or better through
   the day (`transit_supply.json`). Eight systems time only the first and last stop of each trip (Bayamón, Caguas, Jayuya, Juncos, Patillas,
   San Lorenzo, San Sebastián, Vega Baja). For their other 856 stops, departures are estimated from the stop's routes: their trips by hour,
   halved for the two directions. A 2020 Census block counts as served when its point is within 400 m in a straight line of a useful stop.
3. **Gap.** The share of the barrio's residents beyond 400 m of a useful stop. The car-free households without useful service are the barrio's
   car-free households times that share, which assumes they are spread like everyone else.
4. **Priority.** Half the percentile of need × gap (how intense), half the percentile of car-free households without useful service (how
   many). The list is sorted by it.
5. **What the gap points to,** read from where the unserved residents live (their weighted center):
   - **More frequency:** 20 points or more of residents are near a current stop that has less than a bus every 30 minutes.
   - **Extension or feeder:** a stop with a bus every 30 minutes is within 1.5 km. The line names it and its routes.
   - **New service:** neither of the above.

   This is a reading aid, not a route design.
6. **Connections (phase 3, first part).** Pairs of current routes of different operators whose lines come within 250 to 800 m of each other
   (sampled every 100 m), when no stop of one is within 250 m of a stop of the other anywhere on the two routes. A short link, a new stop or a
   timed transfer could join them. Pairs whose closest points are within 400 m are one place. Places are ranked by the residents within 800 m
   of the closest point, then by the weekday trips of the less frequent route.
7. **Municipal timetable.** Each barrio carries the state of its municipality's own system in `operators.json`: current, expired (with its end
   date), none published, or no system listed. `timetable_known` is true when the municipal timetable is current, or when the municipality
   lists no system and has ATI stops.

## What it finds (as of 2026-11-10)

- **Little of the island has useful service in the published timetables.** 7.9% of residents live within 400 m of a stop with a bus every 30
  minutes or better on a weekday, and 21.5% within 400 m of any stop with a current timetable. The site's own measure (`exposure_barrio.json`,
  2026-10-29) gives 22.3% for the second, before Canóvanas's timetable expired on 2026-10-31.
- About 167,000 households have no vehicle; about 144,000 of them live in the unserved share of their barrio.
- **14 of the 25 barrios at the top are in municipalities whose own system publishes no timetable or has an expired one:** Mayagüez,
  Cayey, Comerío and Yauco (none published; 6 barrios), Ponce (expired 2024-12-31), Caguas and Fajardo (expired in 2026; 8 barrios). **7 more**
  are in Arecibo, Aguadilla, Guayama, Juana Díaz and Aguas Buenas, which list no system of their own and are not served by the ATI, so **21 of
  the 25** have no known timetable. There the first step is to learn what runs: the gap may be in the data, not in the service.
- Route pairs whose lines cross or come closer than 250 m without a pair of stops within 250 m are left out of the connection candidates by
  design (`transit_needs.py`, the 250 m rule); such crossings may still be good places for a new shared stop.
- **Where the timetables are current, the most common gap is frequency, not coverage.** The town centers of Manatí, Coamo, Utuado and Humacao,
  and Monacillo (San Juan), have stops near most residents but less than a bus every 30 minutes. Pájaros (Bayamón), the two Medianías (Loíza),
  Quebrada Negrito (Trujillo Alto) and Bajura Adentro (Manatí) have almost no current stop near.
- **The connection places are in the metro area.** Most are ATI routes and San Juan's municipal routes that run 400 to 700 m apart and never
  share a stop (for example, ATI 40 and San Juan 4 near 18.4074, -66.0300, with 10,000 residents within 800 m). Guaynabo's TORR and CANTAG and
  Bayamón's BR-3 come within 305 to 620 m of each other.

## Limits to state with every result

- **Públicos are in no timetable.** They are a large part of transit in Puerto Rico, especially in the town centers that top this list. "No
  useful service" means none in the published timetables.
- **Timetables are not service delivered.** They are what operators publish, not what ran.
- **Distances are straight lines.** This is how the site's `stop_*` measures work. The walking measures (`walk_*`, along mapped roads) would give
  less coverage, and the road file has no footpaths.
- **The ACS has margins of error.** Small barrios swing, which is why only barrios with 500 residents or more are ranked and the no-vehicle
  share carries a reliability flag. The window is 2020-2024.
- **No ridership or origin-destination data.** Phase 4's requests are not made (a colleague, 2026-10-09: open data only for now). Need is
  measured by proxies.
- **Phase 3 is only partly built.** Timed transfers (the wait between an arrival and the next departure) and journey times from the hubs are
  not computed, and the hubs are FPR's to choose (the plan's decision 3).
- **The weights are a choice.** No-vehicle households count twice in the need index, and the priority weighs intensity and count equally.
  `barrios.csv` carries every input, so another weighting can be tried.

## Decisions for FPR

1. **Weights:** confirm the need index (no-vehicle households counted twice; poverty, 65 and over, disability and density once each) and
   the 2-an-hour rule for useful service.
2. **Municipalities with no data:** decide whether to ask Mayagüez, Cayey, Comerío, Yauco, Carolina and the others for their timetables, and
   Ponce, Caguas, Fajardo, Juncos, San Lorenzo and Cidra to renew theirs. This would be a data request, held until FPR decides (2026-10-09).
3. **Publication:** whether any of this goes on the site needs FPR leadership's approval (the plan's decision 4).
4. **Next step:** test the top candidates with the route planner, and choose the hubs for journey times (phase 3).

## Re-run

```bash
python docs/analysis/transit-needs-2026-11/transit_needs.py --as-of 2026-11-10
```

Without `--as-of` it uses today, so a timetable that expires changes the result. Commit the files it writes together with the date.
