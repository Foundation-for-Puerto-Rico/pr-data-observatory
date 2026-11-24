# The federal transportation inventories as map layers

HANDOFF decision 105, step 4 (2026-11-14). The project lead approved step 4 of `docs/transportation-upgrade-2026-11.md` ("Sí, paso 4"): bridges with their condition, airports, ferry routes with passengers, EV charging stations and tunnels, from the federal inventories, completing the points volunteers mapped.

## Files

| File | Layer (2D map and 3D view) | What |
|---|---|---|
| `site/data/bridges.geojson` | Bridges and tunnels (`l=bridges`) | 2,426 bridges of the National Bridge Inventory 2025 and the 4 tunnels of the National Tunnel Inventory |
| `site/data/airports.geojson` | Airports and heliports (`l=airports`) | 17 facilities open to public use or owned by a public body (FAA data in effect 2026-10-29) |
| `site/data/ferry_routes.geojson` | Ferry routes and passengers (`l=ferries`) | 3 crossings with passengers, vehicles and trips (National Census of Ferry Operators 2024) |
| `site/data/ev_stations.geojson` | Public EV charging stations (`l=evcharge`) | 26 public stations with their ports (Alternative Fuels Data Center, 2026-11-14) |

All four are built by `transport_inventories.py` (cache `cache/inventories/`) and drawn by the shared list `site/js/core/facilities.js`, under Infrastructure and mobility: Mobility and transit, after the simulated connections.

    python transport_inventories.py            # downloads only what the cache lacks
    python transport_inventories.py --refresh  # every source again (refresh unit inventories; the bridges also run with unit infrastructure)
    python transport_inventories.py --check    # rebuild from the cache; exit 1 when a published file differs

## Sources (no key, all US Government work)

- **Bridges:** FHWA's National Bridge Inventory, the newest Puerto Rico delimited file (`PR25.txt`, 2,434 records), the same files `infrastructure_series.py` counts by municipio. Items 16 and 17 give the point (degrees, minutes, seconds). FHWA moves to the new SNBI format from 2026: the build stops with the missing columns named rather than read a file it does not know.
- **Tunnels:** FHWA's National Tunnel Inventory through NTAD (`state_code_i3=72`): Minillas (De Diego Expressway, 211,700 vehicles a day), Tenebroso (PR-52) and the two bores of the Vicente Morales Lebrón tunnel (PR-53).
- **Airports:** the NTAD copy of the FAA's 28-day airport data, every facility type (44 in Puerto Rico).
- **Ferries:** the newest National Census of Ferry Operators on data.bts.gov (2024; passengers, vehicles, trips and minutes for each one-way segment), with the line of each crossing from NTAD's ferry routes (the 2020 census, same terminal ids). The NTAD routes alone carry 2019 figures; the 2024 census is fresher, so its figures are the ones published.
- **EV charging:** the NTAD copy of the Alternative Fuels Data Center stations (BTS refreshes it daily; the direct API needs a key).

## What each file keeps, and what it never keeps

- **Bridges:** structure number, road carried, feature crossed, FHWA's condition (good, fair, poor, from the lowest of the deck, superstructure, substructure or culvert ratings), the lowest rating, year built and rebuilt, daily traffic and its year (most counts are from 2017), trucks, detour, length, status (open, posted for load, should be posted, temporary support, closed), scour critical (item 113 codes 0-3), last inspection and the owner's class. Eight bridges whose point falls outside every municipio are left out and listed in the notes.
- **Airports:** FAA identifier, kind, whether the airport holds a Part 139 certificate (airline service: San Juan, Aguadilla, Ponce), use, owner class, elevation and tower. **Private airports, heliports and seaplane bases owned privately (27) are counted by kind in the notes and never drawn or named**: a private heliport can be at a home (sensitive places rule).
- **Ferries:** both directions of each crossing added. Culebra–Vieques (two trips a year, 234 passengers in 2024) has no line in NTAD and is counted in the notes, not drawn.
- **EV charging:** public stations open or temporarily unavailable; ports by level, network, connectors, status and the date last confirmed. The telephone and street address are never read.

## How the map draws them

The `sized` kind of `core/facilities.js` (first used by the power plants) is now general: a circle's area is in proportion to a number (`prop`, radius `k·√value`, at least `min`), or one radius for all (`r`); the colour is a category; `hollow` names the features drawn hollow (dashed in 2D) and the legend's label for them; `unit` is the legend's size note.

- Bridges: area by daily traffic (k 0.024, min 2.5), colour by condition in ColorBrewer RdBu (poor `#b2182b`, fair `#f4a582`, good `#2166ac`; tunnels grey), closed bridges hollow. The file is sorted busiest first, so quieter bridges are drawn on top.
- Airports: one radius (6), dark blue for the certificated airports, light blue for the other public-use airports, pink for the heliports.
- Ferries: a dashed blue line, wider with passengers (650,000 a year at the widest).
- EV charging: area by ports (k 3.7, min 3.5), green with DC fast charging, light blue Level 2 only, hollow when temporarily unavailable.

## Checks

`tests/test_transport_inventories.py` (the degree conversion, names, owners, the private-facility rule, the two directions of a ferry crossing, the station filter on made-up rows; the published notes; no private facility drawn; no phone or address; `--check`) and `tests/facilities_inventories.test.js` (circle sizes, hollow features, pop-ups, notes, legends; the power plants keep their legend). Cross-checks made on 2026-11-14: 2,434 NBI records against `bridges_series.json` for 2025; the condition counts against FHWA's own `BRIDGE_CONDITION` (411 good, 1,671 fair, 344 poor).

## Limits

- Poor does not mean unsafe: a bridge that is not safe is closed.
- The airport layer and the Stations, terminals and airports layer overlap (the second also takes the FAA list); the EV layer and the Taxi stands and EV charging layer (OpenStreetMap, 11 chargers) differ. Both pairs are left side by side for now (decision 105 (x)).
- The ferry census reports a year of operation, not today's timetable, which is on the Transit routes layer.
