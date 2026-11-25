# Environment data (Phase 3, item 11: data wave E)

`environment_series.py` writes two files for the 78 municipios and Puerto Rico, on the Economy tab under "Environment":

- `site/data/environment_series.json`: one snapshot. It has natural hazard loss (7 datasets), landslides (2) and wetlands (3). Each dataset carries its source's year: 2025 for the National Risk Index, 2017 for the landslides and 1983 for the wetlands (the year of the photographs behind almost all of the wetland area).
- `site/data/hazard_series.json`: one value a year. It has community resilience, 2019 and 2021 to 2024, with margins (3 datasets), and earthquakes, 2000 to 2025 (2).

Plan: `docs/proposal-2026-10.md` (J row 11, D5). All five sources are US federal data (public domain), and none needs a key.

## Natural hazard risk (FEMA National Risk Index)

The source is FEMA's county table, version December 2025, read from FEMA's own ArcGIS Online service. The download page refuses scripts.

- **What is published:** the expected annual loss in dollars, in all and for six hazards: hurricane wind, earthquake, inland flooding, landslide, coastal flooding and tsunami. Puerto Rico's value is the sum of the municipios.
- **What it is:** FEMA's model of the average yearly loss to buildings, agriculture and lives. Lives are valued in dollars by FEMA's rule. It is an estimate, tagged "estimate" on the map, not a record of losses.
- **Tsunami:** FEMA does not model a tsunami for 34 municipios; their value is blank, not zero.
- **Coastal flooding:** FEMA's coastal flooding loss for the island is small ($3 million a year). It is FEMA's number as given.
- **Empty for Puerto Rico:** FEMA leaves the composite risk score, social vulnerability and community resilience empty. The build records this in the file's notes, and a test fails if FEMA fills them, so they can be added. The Community Resilience Estimates below fill part of the gap.
- **On the map:** a dollar total is shaded per resident, like the other dollar totals.

December 2025: $3.19 billion a year for Puerto Rico. Hurricane wind is $1.48 billion, earthquake $0.80 billion, inland flooding $0.31 billion and landslide $0.29 billion. San Juan has the largest total ($435 million).

## Landslides after Hurricane María (USGS)

The source is the USGS data release *Map of slope-failure locations in Puerto Rico after Hurricane María* (Hughes and others, 2019, doi:10.5066/P9BVMD74).

- **Where it is read:** the USGS catalog (ScienceBase) refuses scripts. The build reads the copy the release's first author keeps on ArcGIS Online at the University of Puerto Rico at Mayagüez. Only the points are read; the copy's municipio and barrio names have typos and are not used.
- **Placing:** each point goes to the municipal boundary that holds it. All 71,431 fall inside one.
- **Reading:** a record of one storm, not a forecast. The USGS susceptibility map is built since 2026-10-18 by barrio and municipio (`landslide.py`, `docs/landslide.md`).

71,431 landslides; the most in Utuado (17,762), Maricao (5,806) and Jayuya (4,874). Maricao and Utuado have about 60 per km² of land.

## Wetlands (National Wetlands Inventory)

The source is the US Fish and Wildlife Service's inventory, read from its map service (the official zip refuses scripts).

- **Types kept:** estuarine and marine wetlands (mangroves, beaches, tidal flats), freshwater emergent wetlands (marshes) and freshwater forested and shrub wetlands (swamps). Lakes, ponds, rivers and deepwater are left out.
- **Mangroves:** the polygons coded E2FO3 or E2SS3 (estuarine intertidal forested or scrub-shrub, broad-leaved evergreen), which in Puerto Rico are mangroves.
- **Area:** each polygon is split among the municipal boundaries in meters (NAD83 Puerto Rico, EPSG:32161). The part beyond the drawn coast goes to the municipio with the largest share. A polygon more than 2 km from every boundary is left out: 1.2 km² in October 2026. Two polygons whose outline cannot be read are left out.
- **Share of land:** wetland area over the Census land area. A coastal wetland can lie partly on what the Census counts as water, so a small coastal municipio's share can be high: Loíza's is 72%: 14 km² of mangroves and 15 km² of freshwater marsh on 50 km² of land.
- **Date:** the inventory's Data_Source service shows that the coasts (about a third of the island) were mapped from color-infrared photographs of February 1983, and most of the interior has only the inventory's interim "scalable" product; a few small areas come from later photographs. Almost all of the wetland area, and all the mangroves, lie in the parts mapped in 1983. Wetlands filled or restored since then are not shown. The datasets carry the year 1983.

488 km² of wetlands (5.5% of the land), of which 95 km² are mangroves. The most wetland is in Lajas, Loíza and Cabo Rojo.

## Community resilience (Census Bureau)

The source is the Community Resilience Estimates for Puerto Rico: each release's municipio file and the island row of its tract file. There is no 2020 release.

- **What is published:** the share of residents with no risk factors, one or two, and three or more, with margins of error at 90% confidence.
- **Risk factors:** the Census Bureau's ten risk factors that make it harder to withstand and recover from a disaster: household income below 130% of the poverty line, only one or no adults aged 18 to 64 in the household, more than 0.75 people per room, limited English or no one with a high-school diploma in the household, no one employed full-time year-round, a disability, no health insurance, age 65 or over, no vehicle and no broadband. The ten factors are the same in every release, but from 2023 the Census Bureau computes municipio margins a new way (smaller), so compare margins across 2022 and 2023 with care.
- **English:** One factor is a household where no one speaks English very well (or no one has a high-school diploma), so in Puerto Rico it counts many Spanish-speaking households and raises the shares with risk factors.
- **Reading:** modeled estimates; read the margin before comparing two places.

Puerto Rico: 46.1% with three or more risk factors in 2019 (± 1.6 points) and 40.2% in 2024 (± 0.7). Highest in 2024: Maricao (54.8%), Las Marías and Vieques.

## Earthquakes (USGS ComCat)

The source is USGS's catalog, one request a year for magnitude 2.5 or more in a box around Puerto Rico.

- **Placing:** an earthquake goes to the municipio whose boundary holds its epicenter. Offshore, it goes to the nearest municipio if that is within 25 km of the coast; otherwise it is left out. Each earthquake counts once, so the municipal values add up to Puerto Rico's.
- **Years:** whole years only. The last two are downloaded again with each build.
- **Reading:** a count of events, not of damage. The catalog records more small earthquakes in later years as the seismic network grew.

2000 to 2025: 16,845 of the 24,260 earthquakes in the box are placed. 2020 had 6,297 (the southwest sequence, strongest 6.4), most in Guánica (2,980) and Guayanilla (1,701).

## Privacy

None of the five sources holds personal data. No point, outline or epicenter is published: the files hold counts, areas, shares and dollars for each municipio.

## Not done in item 11

- **Storm surge (NHC SLOSH), tree canopy and land cover:** these are rasters, and the build has no raster reader. Since 2026-11-04 the build has one, `raster.py` (`docs/raster.md`, HANDOFF decision 80): it reads Cloud Optimized GeoTIFFs by HTTP range requests, without rasterio. The landslide susceptibility map was built on 2026-10-18 without one: its first author's copy is a tile service with one flat color per class, which `landslide.py` decodes with zlib and numpy (`docs/landslide.md`); the same trick does not work for continuous rasters.
- **Zoning (Junta de Planificación):** no license is stated, so it is not harvested.
- **Tide gauges, stream gauges, rainfall stations, air quality:** station data, not built in this item. Air quality covers 8 of the 78 municipios.
- **Heat:** the CDC tracker and Census LACE have no Puerto Rico rows (still `blocked` in `wanted.json`).

## How to update

`python environment_series.py` downloads only what is missing from the cache (`cache/environment/`). `--refresh` downloads again, and `--check` rebuilds both files from the cache and exits 1 if a published file differs. `build.py` runs it after the infrastructure series.
