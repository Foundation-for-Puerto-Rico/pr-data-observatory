# Public facilities, students and main roads in hazard areas (decision 107, step 3)

`facility_exposure.py` writes `site/data/facility_exposure_series.json`: 17 datasets for the 78 municipios and Puerto Rico, in the group **Hazards · Facilities and roads in hazard areas** of the Analysis tab. It is an **overlaid** layer in the sense of decision 107: one published layer laid on another, with nothing assumed.

The observatory already counted the residents, housing units and buildings inside the flood area. This adds what serves them: the public buildings, the schools and their students, and the main roads.

## What is laid on what

- **The flood area:** FEMA's 1% annual chance flood area (the Special Flood Hazard Area) of the observatory's flood layer, `flood.geojson`, by the same rule as the exposure series.
- **Facilities:** the point layers the map draws (fire and EMS stations, police stations, city halls, libraries, public housing developments, power plants, airports) and the public schools open in school year 2024 (NCES school directory, through the Urban Institute's Education Data API, no key), each with its students.
- **Main roads:** `traffic_roads.geojson`, the arterials and major collectors with a traffic count (5,346.1 km). Each line is cut by the municipio outlines and each piece by the flood polygons.

## What it shows

In Puerto Rico, **327 of the 2,274 facilities** tested stand in the 1% flood area (14.4%).

| Kind | Tested | In the 1% flood area | Share |
|---|---|---|---|
| Airports and heliports | 17 | 3 | 18% |
| City halls | 65 | 10 | 15% |
| Fire and EMS stations | 94 | 10 | 11% |
| Libraries | 883 | 145 | 16% |
| Police stations | 141 | 27 | 19% |
| Power plants | 68 | 13 | 19% |
| Public housing developments | 144 | 23 | 16% |
| Public schools | 862 | 96 | 11% |

- **Schools:** 96 open public schools, with **27,178 students** (11.5% of public school students). Most students: Ponce (4,246), Carolina (3,318), San Juan (3,132).
- **Main roads:** **596.3 km** of 5,346.1 km (11.2%). Highest shares: Loíza (58.2%), Cataño (53.6%), Hormigueros (47.4%).

## What it does not say

- **It says where a building or road stands, not that it floods.** The floor height of a building and the height of a road are not known. A raised road inside the area is counted like any other stretch.
- **The flood layer is a simplified copy** of FEMA's map, and FEMA's 1% area is the regulatory map: it has no sea level rise, and some places flood that it does not show.
- **Bridges are left out.** A bridge over a river stands in the flood area by design.
- **Public housing developments whose location is approximate** are not drawn on the map and are not tested.
- **Points that share their coordinates with another point of the same layer are not tested** (234: libraries 216, public housing developments 18). Several facilities listed at one address, such as a municipio's technology centers at its main library, are not where the buildings stand; counting each would multiply one spot's hazard by the size of the stack.
- **Library points within 150 m of an open public school may be the same building; both are counted.**
- **A share in a municipio with few facilities** moves a lot with one building: read the count beside it.

## Sea level rise (added 2026-11-16)

The same points and roads laid on NOAA's extent of **3 ft of sea level rise** above mean higher high water, connected to the ocean (the height of the exposure series headline). Five datasets: facilities (count and share), the share of public school students, and main-road km (count and share). Roads are read every 20 m: NOAA's coastline is too detailed to cut every road piece by it in reasonable time.

In Puerto Rico, **17 of 2,274 facilities** (0.7%), 0.1% of public school students and **17.0 km** of main road (0.3%) stand in that area.

| Kind | Tested | In the 3 ft area |
|---|---|---|
| Airports and heliports | 17 | 0 |
| City halls | 65 | 0 |
| Fire and EMS stations | 94 | 0 |
| Libraries | 883 | 12 |
| Police stations | 141 | 2 |
| Power plants | 68 | 1 |
| Public housing developments | 144 | 0 |
| Public schools | 862 | 2 |

It says where a building stands today, not when or whether the sea reaches it. Waves, storm surge and erosion are not in NOAA's extent, and low-lying areas cut off from the ocean are not counted.

## Landslide susceptibility (added 2026-11-16)

The class of the USGS landslide susceptibility map (Hughes and Schulz, 2020) under each point, read from the same zoom-15 tiles as `landslide.py`. A point counts when its cell is **High, Very High or Extremely High**, the most susceptible 30% of the main island. Roads are read every 20 m. Vieques and Culebra are not in the map, so they have no value and Puerto Rico's figure is of the main island.

On the main island, **26 of 2,249 facilities** (1.2%), 0.0% of public school students and **474.3 km** of main road (8.9%) stand on that land. 2 points fall on a cell with no class and count as not high.

| Kind | Tested | On High or higher |
|---|---|---|
| Airports and heliports | 14 | 0 |
| City halls | 63 | 0 |
| Fire and EMS stations | 92 | 0 |
| Libraries | 876 | 23 |
| Police stations | 140 | 0 |
| Power plants | 66 | 3 |
| Public housing developments | 143 | 0 |
| Public schools | 855 | 0 |

It says what the ground is rated, not that a slide will happen. It is not a substitute for a site-specific slope-stability study. **A building's own cell reads low:** a building stands on a leveled pad, and the 5 m map rates the pad by its own slope. 94% of public schools read Low, while 11.5% of residents (census block points, as `landslide.py` counts them) live on High or higher land. A low count means the building's own cell is not rated high, not that it is safe from a slide above or below it. Roads, read every 20 m, are a better guide here: 8.9% of main road km run on High or higher land. Checked: this reader gives 11.48% of residents on High or higher land with the census block points, against 11.47% published by `landslide.py`.

## On the map (added 2026-11-16)

- **Public schools** are a layer of their own (Education group, 2D and 3D): `public_schools.geojson`, the open public schools of school year 2024-25, each with its students, grades and flags.
- **Every facility's pop-up** says which of the three areas its point stands in, from `facility_hazards.json` (only the flagged points are listed, keyed by their coordinates to 5 decimals). A point with no flag says nothing, rather than "safe".

## Correction (2026-11-16)

The first figures (PRs #261 and #264) counted every point, including stacks of facilities listed at one address. The largest were libraries: 17 technology centers at one point in Guaynabo, 12 in Ciales, 12 in Villalba. Those stacks carried 42 of the 68 facilities first counted on high landslide land, which put Ciales and Villalba at the top of that list, and 27 of the 356 first counted in the flood area. With stacked points left out: 327 facilities in the flood area, 17 in the 3 ft sea level rise area and 26 on high landslide land. Students and roads did not change.

## Checks (`tests/test_facility_exposure.py`)

On invented points, roads and a square flood area: a point inside counts and a point outside does not; students follow their school; a road is cut at the municipio line and at the flood edge; shares are of the municipio's own total; Puerto Rico is the sum. On the published file: the areas and their order, counts no larger than what was tested, shares between 0 and 100, and the island row equal to the sum of the municipios. For sea level rise and landslides: a municipio the map does not cover gets no value and is left out of Puerto Rico's figure; a road read every 20 m counts the right length; inland municipios have nothing in the sea level rise area; Vieques and Culebra are the only municipios without a landslide value. With the cached school directory, sea level rise extents and landslide tiles: a rebuild gives the published file again.
