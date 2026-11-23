# Road deaths

HANDOFF decision 105, step 3 (2026-11-13). Francis approved step 3 of `docs/transportation-upgrade-2026-11.md` ("Sí, paso 3"): fatal crashes by municipio and year, counts only.

## Files

| File | What | Built by |
|---|---|---|
| `site/data/crashes_series.json` | Six figures for the 78 municipios and Puerto Rico (Analysis tab, group Infrastructure · Road safety) | `crashes.py` |
| `site/data/transit_links.json`, `simulated_links.geojson` | Each simulated connection gains `deaths_5y` and `walk_bike_5y` (five-year totals within 100 m of its line) | `transit_links.py` (reads the crash points from `cache/crashes/` through `crashes.points()`) |

`python crashes.py` downloads the yearly files missing from `cache/crashes/` (one zip of about 200 KB a year, 2015 on) and builds in a few seconds; `--refresh` downloads every year again (NHTSA replaces a year's first release with its final file); `--check` rebuilds from the cache. Run it after `traffic.py` (for the rate per vehicle-km) and before `transit_links.py`. `build.py` runs them in that order; the refresh unit `crashes` runs `crashes.py` and `transit_links.py`.

## Source (no key)

NHTSA, **Fatality Analysis Reporting System (FARS), Puerto Rico files**, one a year at `static.nhtsa.gov/nhtsa/downloads/FARS/<year>/Puerto Rico/FARS<year>PuertoRicoCSV.zip`: `accident.csv` (one row per fatal crash) and `person.csv` (one row per person). US Government work. 2015 to 2024 are published; 2024 is the Annual Report File (first release), 2023 and earlier are final.

The files give the municipio (`COUNTY`, the county code) from 2020. Before 2020 every crash has the same code, so 2015-2019 are Puerto Rico totals only (in `notes.island`). One crash of 2020 has county code 72 ("Puerto Rico"): its death counts in Puerto Rico's total and in `notes.municipio_not_given`, not in a municipio.

## How each figure is made

- **People killed** (`crash_deaths`): the sum of `FATALS` of the municipio's crashes. FARS counts deaths within 30 days of a crash on a public road.
- **Fatal crashes** (`crash_fatal`): the crashes.
- **Pedestrians and bicyclists killed** (`crash_walk_bike`): people with a fatal injury (`INJ_SEV` 4) who were pedestrians (`PER_TYP` 5) or cyclists (6, 7).
- **Motorcyclists killed** (`crash_moto`): drivers and passengers (`PER_TYP` 1, 2) with a fatal injury in a motorcycle (`BODY_TYP` 80-89).
- **Deaths per 100,000 residents, 2020-2024** (`crash_rate_5y`): five years of deaths over the sum of the municipio's residents in those years (Census Bureau population estimates, `housing_series.json`), times 100,000. Puerto Rico: 8.9. It is high where much traffic passes through (Santa Isabel, Guánica, Salinas).
- **Deaths per 100 million vehicle-km, 2020-2024** (`crash_per_vkm`): five years of deaths over five times the yearly vehicle-km of HPMS data year 2025 (`traffic_series.json`), times 100 million: the risk per kilometre driven. Puerto Rico: 1.05, about 1.69 per 100 million vehicle-miles, above the US average of about 1.3 (NHTSA, 2023).
- **Along a simulated connection** (`deaths_5y`, `walk_bike_5y`): the people killed in located crashes of 2020-2024 within 100 m of the connection's line. The page divides by the connection's length (per 10 km). Connections share roads, so these counts must not be added up; a crash at a crossing road within 100 m counts too. 1,383 of the 1,390 crashes of 2020-2024 have a location.

## Privacy

FARS records hold each crash's place, date and time, and the age and sex of each person. The observatory publishes only counts by municipio and year, five-year rates and five-year totals along a simulated connection. No crash is drawn, and the coordinates are read only inside the build. `tests/test_crashes.py` checks that the published file holds no coordinates, case numbers, days, months or hours (`wanted.json`, row `crashes`: "the exact date, time and place of a death can identify a person").

## Checks

`tests/test_crashes.py`: who counts as a pedestrian, cyclist or motorcyclist, and the codes for an unknown location, on made-up files; the municipios plus the deaths not placed add up to Puerto Rico each year; the file holds no crash; the rates are in range; the connections carry their counts; `--check` where the files are cached. Cross-check made on 2026-11-13: the yearly totals equal BTS's national FARS layers (NTAD) for Puerto Rico: 297 crashes and 307 deaths in 2023 (final release), 275 crashes and 288 deaths in 2024 (initial release).

## Limits

- A municipio has few deaths a year; read several years, or the five-year rates.
- The Puerto Rico Traffic Safety Commission keeps its own count, which can differ from FARS.
- Only deaths: the open data have no injury crashes. The Observatorio de Seguridad Vial (CST and UPR) has them, with no open download (`docs/transportation-upgrade-2026-11.md`, section 4).
