# Route analysis (draft Knowledge Area tab), 2026-10

The data behind `site/route-analysis.html`, the "Análisis de ruta" (Route analysis) tab of the Knowledge Area. The tab was agreed with the project lead on
2026-10-19 as an area of its own (nothing added to Vivienda or WCRP). It is published with the "In review" marker kept and `noindex`, like
WCRP. Prepared by Zoralis Alicea with Claude (AI).

| File | What it is |
|---|---|
| `make_page.py` | Writes `site/route-analysis.html` (English), `site/data/route_compare.json` (the routes the page loads) and `i18n_src/es/routes.json` (the Spanish of the page and of `site/js/route_analysis.js`) from (English, Spanish) pairs. Run it, then the steps under "The published data file". |
| `route_compare.py` | Computes `route_compare.csv` and `route_compare.json` from `site/data` (trips.json, transit_routes.geojson, transport.json, population_blocks.json) and the four input files below. About 1 minute, no download. |
| `road_features.geojson` | One point per signalised junction, roundabout and pedestrian bridge (OpenStreetMap, Geofabrik extract of 2026-10-15; © OpenStreetMap contributors, ODbL). Only what `route_compare.py` reads is kept: `kind` and the OpenStreetMap ids it was built from (`osm_ids`, the key of `road_flow.csv`); names and the other tags were removed on 2026-10-21. |
| `road_flow.csv` | Estimated design-hour volume at each signalised junction and roundabout: the AADT of the busiest road that reaches it times its K factor, the design-hour volume (30th-busiest hour of the year) as a percentage of AADT (FHWA HPMS 2024, Field Manual item 26; US Government work). An estimate: `k_imputed` marks the 764 of 1,582 junctions (48%) whose road has no K, given the median K of their road class. |
| `transit_exposure.csv`, `transit_runtime.csv` | For each bus route, the busy junctions on its path and how often its trips pass them (6-9 and 16-19), and its scheduled time at peak and midday, from the same weekday timetables. |
| `route_compare.csv`, `route_compare.json` | 97 bus routes, one row each: the ATI and the municipal systems with a stop within 250 m of an ATI stop (San Juan, Bayamón, Guaynabo, Caguas, Canóvanas), and the eastern systems, which do not meet the ATI network (Fajardo, Humacao, Juncos, San Lorenzo, Patillas, Vieques). |

The measures, from the weekday timetables in `site/data/trips.json` (typical Wednesday):

1. Service: weekday trips, first and last departure, and the 6:00-9:00 headway on the busiest stop pattern.
2. Route: length of the main stop pattern and its scheduled speed (see "Timetable-only routes" below).
3. Peak-hour junctions: signalised junctions and roundabouts on its path with an estimated design-hour volume (AADT x K factor) of 2,000 vehicles an hour or more
   (OpenStreetMap and FHWA HPMS 2024), per 10 km, and how often its trips pass them 6:00-9:00 and 16:00-19:00
   (`passes_estimated` when only two stops are timed).
4. Connections: a stop within 300 m of a Tren Urbano station, and the other systems with a stop within 250 m.
5. Residents within 400 m of a stop (2020 Census blocks, each block once per route). Supplementary: footbridges within 30 m.

`timetable_expired` marks the systems whose feed ended before 2026-10-19 (Caguas, Fajardo, Juncos, San Lorenzo). The page computes it again
from each operator's `feed_end` and the day it is read, so Canóvanas (feed end 2026-10-31) is flagged from 2026-11-01 without a rebuild, and
the line under the table names the systems expired that day.

**Timetable-only routes** (`timepoints_only`): every route of Bayamón, Caguas, Juncos and San Lorenzo, and ATI express route 20, has a
timetable with a time at only two stops of each trip. Their length is that of the operator's route line in `transit_routes.geojson`, which
on some routes holds both directions or a loop: Bayamón BR-1's line is 32.1 km while its timed path in `trips.json` is 16.0 km (BR-2 28.4
and 8.9, BR-3 36.4 and 18.2, BT-1 7.4 and 2.3; Juncos Bo. Juncos Pueblo 8.9 and 3.8; San Lorenzo Yellow 14.8 and 7.7). Their speed is
that of the timed stretch and is left blank when the stretch is under half the line (the two timed stops are not the two ends). Their
crossings are estimated (`passes_estimated`): trips leaving in the period times the high-volume junctions on the line. The page marks
their length, speed and crossings with an asterisk and says so under the table.

The four input files come from the road-features analysis (`road_features.py`, `road_flow.py`, `transit_exposure.py`, which read the
OpenStreetMap extract and the HPMS downloads in `cache/`). Those scripts and the rest of that analysis (signals against roundabouts, crashes)
are not part of this tab and stay with that work until it is reviewed on its own.

Checked on 2026-10-21: `python route_compare.py`, run on the `site/data` of this branch, writes the committed `route_compare.csv` and
`route_compare.json` again, unchanged. So the congestion figures of the page reproduce from the repository: 69 of the 74 metro-area routes
pass at least one junction with an estimated 2,000 or more vehicles an hour, and ATI route 7 passes them 494 times from 6:00 to 9:00.

The flow is an **estimate**, and a **design-hour volume**, not a count and not a typical weekday peak. HPMS gives each reported road section
its AADT (annual average daily traffic, both directions) and its K factor, which the HPMS Field Manual (item 26,
https://www.fhwa.dot.gov/policyinformation/hpms/fieldmanual/page05.cfm) defines as the design-hour volume, the 30th-busiest hour of the year, as a percentage of AADT. AADT x K is that
design-hour volume, and the 2,000 vehicles an hour apply to it. A junction takes the flow of the busiest HPMS road within 30 m. HPMS requires
K only on Sample Panel sections and says statewide or system-wide values shall not be used; for 764 of the 1,582 junctions (48%) the road has
no K and the median K of its road class is used (`k_imputed`): the observatory's own estimate, which HPMS guidance does not endorse. HPMS
reports state and federal-aid roads, so a junction of local streets has no flow. It is how many vehicles, not how well they move. The page
says so in section 1 and in its sources, and notes by the headline that 15 of the 69 routes are timetable-only estimates (6 of Bayamón, 8 of
Caguas and ATI express route 20) and that Caguas's timetable has expired.

## The published data file

`make_page.py` publishes the routes as `site/data/route_compare.json` (about 7 KB compressed), which the page loads when it opens; only the headline
figures are written into the page. The file is registered like every other data file:

- the data contract (`dictionary_src/datasets.json`, record `route_compare`): domains `infrastructure.mobility` and `population`, sources
  `ati_gtfs`, `muni_gtfs`, `osm` (ODbL, credit "OpenStreetMap contributors"), `fhwa_hpms` (new source record: US Government work) and
  `census_tiger`; licence class `unstated`, that of the municipal GTFS feeds;
- the data dictionary (`dictionary_src/entries/route_analysis.json`, group "Route analysis"): `route_compare.file` and one entry for each of its
  31 fields (`route_compare.<field>`), with their Spanish summaries in `i18n_src/dictionary_plain.json`;
- the ledger (`ledger.py`, adapter `a_route_compare`: a route or an operator is a record), so it appears on the Data management page;
- the route budget (`dictionary_src/routes.json`, `routes`: the file loads first, within the 10 KB of data).

After a rebuild: `python make_page.py`, `python i18n.py`, `python dictionary.py`, `python catalog.py`, `python ledger.py --backfill origin/main`,
`python registry.py`.

## The page

Registered as docs/knowledge-areas.md asks: `i18n_src/pages.json` (scopes common, knowledge, routes; the glossary module),
`dictionary_src/routes.json` (budget 30 KB of scripts), `tests/browser/throttle.js`, the pages `dictionary.py`
scans and links to, and the entry `layers.knowledge_area`.
