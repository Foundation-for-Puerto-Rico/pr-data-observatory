# The 3D view's missing buildings (`buildings3d.py`)

Step A2 of the GeoAI sources plan (`docs/geoai-sources-proposal-2026-11.md`, HANDOFF decision 91, approved 2026-11-09). Built on 2026-11-10 on branch `data/buildings-3d`.

## What changes

The 3D view used to draw only the base map's buildings: OpenFreeMap tiles made from OpenStreetMap, about 1.5 million in Puerto Rico. Overture's buildings theme (release 2026-10-21.0) has 2,157,363. The other 656,964 come from Google Open Buildings and Microsoft ML Buildings, traced by machine learning, most of them in the countryside and the west. Those barrios are where OpenStreetMap has fewest buildings (`buildings.bld_ml_pct`, Moca 42.7%).

The "3D buildings" switch now draws both:

- the base map's buildings, as before;
- the new file `site/data/buildings_gap.pmtiles`, with the buildings that OpenStreetMap lacks.

Town centers are already mapped in OpenStreetMap; the new buildings are mostly houses on the outskirts and in the countryside. In Moca, Overture counts 31,987 buildings, of which 13,672 (43%) were traced by machine learning; the barrios with the most are Higuillar in Dorado (6,789) and Cañaboncito in Caguas (5,115, 41%), from `buildings_barrio.json`.

**Correction (2026-11-11).** This page and the dictionary first said that in the center of Moca the base map draws a handful of buildings and the new layer about 500. That was wrong: the counts came from MapLibre's `queryRenderedFeatures`, which miscounts 3D buildings drawn on terrain. On the live site, with each layer shown alone, the center of Moca draws its buildings from OpenStreetMap and the new layer adds houses around it.

## Hosting: measured first (decision 91 (c))

On 2026-11-10, Overture's tiles for the Puerto Rico box at zooms 13 and 14 (2,295 tiles):

| Option | Size |
|---|---|
| Overture's own tiles, as they are | 153.5 MB, over GitHub Pages' 100 MB a file |
| Every building, slimmed to outline, height and base height | 29.0 MB |
| **Only the buildings that are not from OpenStreetMap, slimmed** | **7.4 MB** (chosen) |

Reading Overture's tiles directly from their bucket (option 1) would cost nothing to host. It was not chosen for two reasons:

- Overture calls those tiles "for inspection, not production".
- Each monthly release has a new address.

## How it is made

1. `buildings3d.py` reads Overture's PMTiles for the release, the zoom 13 and 14 tiles over the box -67.97, 17.85 to -65.20, 18.57. It uses HTTP range requests, with 16 at a time, and takes about six minutes and 150 MB. The tiles go into `cache/buildings3d/` and are never published.
2. From each tile it keeps the buildings whose `@geometry_source` is not OpenStreetMap, with only their `height` and `min_height`. No id, name, class or source record is kept.
3. It writes one PMTiles file, layer `b`, zooms 13 and 14. The tiles are gzip-compressed with a fixed timestamp, so a rebuild from the cache gives the same bytes; `python buildings3d.py --check` confirms it.

The file's metadata holds the counts that `ledger.py` reads: 704,061 buildings at zoom 14, where a building on a tile edge counts in each tile.

Checks that stop the build:

- 550,000 to 800,000 buildings at zoom 14;
- a file under 20 MB;
- no building from OpenStreetMap.

## How the 3D view draws it

- **The library.** `3d.html` loads the PMTiles library (4.4.0, from unpkg, with an integrity hash; 7.7 KB compressed). The About page's list of outside services now names it.
- **The layer.** `twin3d.js` adds the source `bgap` and the layer `buildings-3d-gap` just above the base map's `buildings-3d`, with the same colors.
- **Heights.** A building without a height is drawn 6 m tall, as the base map's own. In this release none of the new buildings has a height.
- **The switch.** `showBuildings()` sets both layers from the "3D buildings" switch: when it is changed, after a base map change, and when a failed base map comes back.
- **Credit.** The source carries the credit "© Overture Maps Foundation", which MapLibre adds to the credit line while the layer is on.

## Limits

- **Where both have a building.** A building that OpenStreetMap volunteers mapped after Overture's release can appear twice, once from each source.
- **Machine-learning outlines** can include sheds and ruins and miss buildings under trees.
- **Outlines only.** No name, address or use is attached to a building. Most are homes; HANDOFF decision 91 allows drawing them, as a base map does, but no value per building.

## Refresh

The refresh unit `buildings` runs `buildings.py` and then `buildings3d.py`, so the barrio figures and the 3D tiles always come from the same Overture release. Its source `overture_buildings` is checked every 90 days, not monthly: each rebuild adds the 7 MB file again to the repository's history. A person looks at the 3D view before a rebuild is merged.

## Local test server

`tests/browser/serve_gzip.js` now answers byte ranges (206), as GitHub Pages does. PMTiles reads its file this way, and Python's `http.server` does not.
