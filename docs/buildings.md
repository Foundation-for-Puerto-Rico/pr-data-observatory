# Buildings by barrio and municipio (`buildings.py`)

Step A1 of the GeoAI sources plan (`docs/geoai-sources-proposal-2026-11.md`, HANDOFF decision 91, approved 2026-11-09). Built on 2026-11-09 on branch `data/buildings-barrio`.

`buildings.py` writes two files:

- `buildings_series.json`: 7 datasets for the 78 municipios and Puerto Rico.
- `buildings_barrio.json`: the same 7 datasets for the 901 barrios.

They are shaded on the map's Analysis tab, in the group "Housing · Buildings (Overture)", by municipio or by barrio. **Nothing is published per building.** Most buildings are homes, so the files hold only counts, areas and shares for barrios and larger areas.

## The source

The Overture Maps Foundation's **buildings theme** joins building footprints from several sources into one set:

1. OpenStreetMap, which comes first, so volunteers' edits win;
2. Google Open Buildings and Microsoft ML Buildings, traced from satellite images by machine learning;
3. Esri Community Maps and other sources (none in Puerto Rico in this release).

Overture publishes a new release every month as GeoParquet on public cloud storage, with no key. The licence is **ODbL 1.0** because the theme holds OpenStreetMap data. Credit: "© OpenStreetMap contributors, Overture Maps Foundation". Our two files are counts and shares derived from it, so they are offered under ODbL 1.0 too (source card `overture_buildings`).

The build reads the theme with the `overturemaps` package, which was already in `requirements.txt` for places. It reads a box around Puerto Rico (west -67.97, south 17.85, east -65.20, north 18.57; Saint Thomas begins at about -65.09). This takes about 3.5 minutes. HANDOFF decision 91 (b) had planned to use DuckDB; the package already in use reads the same files, so no new dependency was needed.

## How it is made

- **The cache.** For each building the build keeps:
  - one point inside its outline (shapely's point on surface);
  - its footprint area in m², on the Lambert equal-area plane of `conditions.Barrios`;
  - the dataset of its first source;
  - its height, when Overture has one.

  It keeps neither the outlines nor the ids. The file is `cache/buildings/<release>.npz`, 32 MB for release 2026-10-21.0, and is never published.
- **Areas.** A building belongs to the barrio whose outline holds its point. A point that falls on a shared edge goes to the barrio with the lower index, as `Barrios.at` does. A point just off the coast (a pier, a building on the shore) goes to the nearest barrio within 100 m; farther ones are left out (335 in this release). Municipios and Puerto Rico add up their barrios.
- **Flood.** A building counts as in a Special Flood Hazard Area when its point is inside one of the 1% annual chance areas of `flood.geojson`, as chosen by `exposure.flood_polygons`. This is the same rule as the flood exposure figures.
- **Land under roofs.** The footprints' area over the area's Census land area (the crosswalk's `km2`, water left out). A footprint traced from above is the roof's outline, so eaves count. Streets and parking lots do not, so this is not the impervious share of the land.
- **Machine learning.** A building whose first source is not OpenStreetMap counts as traced by machine learning. This describes the data, not the buildings: where the share is high, counts and sizes are less certain.

## The figures (release 2026-10-21.0, build of 2026-11-09)

| Key | What | Puerto Rico |
|---|---|---|
| `bld_n` | Buildings | 2,157,028 |
| `bld_per_km2` | Buildings per km² of land | 243.2 |
| `bld_roof_pct` | Land under roofs (%) | 3.3 |
| `bld_area_med` | Median footprint (m²) | 106 |
| `bld_sfha_n` | Buildings in a FEMA Special Flood Hazard Area | 193,704 |
| `bld_sfha_pct` | The same, as a share of the buildings (%) | 9.0 |
| `bld_ml_pct` | Buildings traced by machine learning (%) | 30.4 |

Of the 2,157,363 buildings in the box:

- 1,500,399 come from OpenStreetMap;
- 536,571 from Google Open Buildings;
- 120,393 from Microsoft ML Buildings.

203,060 have a height (9.4%).

Highlights by municipio:

- **Density:** San Juan has the most buildings per km² (1,014.6), followed by Cataño (971.8); Maricao has the fewest (51.7).
- **Flood:** the highest flood shares are Salinas (46.9%), Loíza (42.6%) and Cataño (37.2%).
- **Machine learning:** the highest shares are in the west, Moca (42.7%) and Aguada (42.6%); the lowest is San Juan (17.7%).

## Checks that stop the build

- 1.9 to 2.5 million buildings in the box.
- At least 99.5% of them placed in a barrio (99.98% in this build).
- San Juan denser than Puerto Rico.
- 1% to 30% of the buildings in a Special Flood Hazard Area.
- Across the barrios, more 2020 housing units means more buildings: a Spearman rank correlation of 0.6 or more. It is 0.965 in this build. Puerto Rico has 1.35 buildings for each 2020 housing unit, since sheds, garages, shops and other buildings count too.

`python buildings.py --check` rebuilds from the cache without the network and fails when a published file differs. `tests/test_buildings.py` checks:

- the barrio rule (inside, shared edge, coast, far);
- the flood rule;
- the rank correlation;
- the offline cache;
- that the published files add up, stay in range and hold nothing per building.

## Limits

- **One building is one footprint.** A row of attached houses may be one footprint or several, depending on who traced it.
- **Footprints traced by machine learning** can include sheds, carports and ruins, and miss buildings under trees.
- **Ground area, not floor area.** A three-storey building counts once.
- **Flood counts use one point per building.** A building partly inside a flood area may count as outside, and the reverse. FEMA's outlines in `flood.geojson` are simplified by about 5 m.
- **The date is Overture's release, not a census date.**

## Refresh

The refresh unit `buildings` runs `python buildings.py --refresh` and then `python buildings3d.py --refresh` (`docs/buildings3d.md`). The source `overture_buildings` checks Overture's release catalogue every 90 days, and a person reviews each rebuild. The GitHub Actions cache keeps `cache/buildings/`. A new release is downloaded once and replaces the old one.

## Next

Step A2 fills the gaps in the 3D buildings: the 656,964 Google and Microsoft footprints that the OpenStreetMap base map does not draw. Hosting is measured first (decision 91 (c)).
