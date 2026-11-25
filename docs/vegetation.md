# Vegetation greenness by barrio and municipio (`vegetation.py`)

Step 1 of the terrain and climate plan (`docs/terrain-climate-proposal-2026-11.md`, HANDOFF decision 80, approved 2026-11-04), beside surface heat (`docs/heat.md`). Built on 2026-11-04 on branch `data/vegetation-sentinel2`.

`vegetation.py` writes two files:

- `vegetation_series.json`: 5 datasets for the 78 municipios and Puerto Rico.
- `vegetation_barrio.json`: the same 5 datasets for the 901 barrios.

They are shaded on the map's Economy tab, in the group "Environment · Vegetation (Sentinel-2)", by municipio or by barrio. They use the same summers and the same 60 m grid as the surface heat figures, so the two can be set side by side.

## What it measures, and what it does not

**NDVI**, the normalized difference vegetation index, is (near-infrared − red) / (near-infrared + red). Green leaves reflect near-infrared light and absorb red light, so NDVI is near 0 on pavement, roofs and bare ground and about 0.6 to 0.9 under dense forest. It shows **how green the land looks from above**. It is **not tree cover**: a pasture or a lawn in full leaf can read as green as a forest, and a tree that shades a street counts only for the part of the pixel it fills.

Sentinel-2 passes at about 10:30 local solar time (about 11:00 Atlantic Standard Time). The figures are the vegetation of **clear** days of **June to September of the last three complete summers** (2024–2026 in this build), the window of the heat figures. A drought, a dry season or a hurricane lowers NDVI; this window does not show those.

## The figures (build of 2026-11-04)

| Key | What | Puerto Rico |
|---|---|---|
| `veg_ndvi_med` | Median NDVI of the land on clear summer days | 0.78 |
| `veg_dense_pct` | Share of land with dense vegetation, NDVI 0.6 or more (%) | 75.7 |
| `veg_sparse_pct` | Share of land with little or no vegetation, NDVI below 0.2 (%) | 4.2 |
| `veg_res_sparse` | 2020 residents on land with little or no vegetation (estimate) | 875,584 |
| `veg_res_sparse_pct` | The same, as a share of residents (estimate, %) | 26.6 |

- **Greenest municipios:** the western Cordillera. Las Marías (0.87), Utuado (0.85) and Maricao (0.85); Maricao has 97.4% of its land densely vegetated.
- **Least green:** San Juan (0.31), Cataño (0.37) and Santa Isabel (0.41). The dry south coast (Santa Isabel, Lajas, Guánica) has the least dense vegetation; San Juan and Cataño have the most land with little or none (36%).
- **Residents:** 26.6% of residents live on land with little or no vegetation, though it is 4.2% of the land, because people live where the land is built. The highest shares are Santa Isabel (53.1%), San Juan (49.9%) and Cataño (49.1%).
- **Greener is cooler.** Across the 901 barrios, the rank correlation between median NDVI and median morning surface temperature (`heat_barrio.json`) is −0.89. Shade and evaporation cool the land, and elevation adds to it: the Cordillera is both greener and higher, so this is not a measure of how much trees alone cool a place.

## How it is made

**Scenes.** Every Sentinel-2 Level-2A scene over Puerto Rico from June to September of the three summers, with less than 70% cloud cover.
- This build found 984 scenes (2024: 265, 2025: 341, 2026: 378) in 241 passes; 230 passes had at least one clear cell.
- They come from eight 110 km MGRS tiles (19QFA, 19QFV, 19QGA, 19QGV, 19QHA, 19QHV, 20QKE, 20QKF), in UTM zones 19 and 20.
- They are **Collection 1**: ESA reprocessed the archive with one processing baseline, so a 2024 scene and a 2026 scene compare. The reflectance is the stored number × 0.0001 − 0.1 (each scene's own scale and offset are read from the catalog).
- They are read from **Earth Search** on AWS (Element 84, collection `sentinel-2-c1-l2a`), whose files are public and need no key.
**Reading.** `raster.py` (`docs/raster.md`) reads three files of each scene at **40 m**: the red band (B04) and the near-infrared band (B08) at their second overview, and the scene classification (SCL) at its first.
- The files' overviews are made with GDAL and say how (`OVR_RESAMPLING_ALG`): the bands' are averaged from the 10 m pixels and the classification's keep the most common class, so a class is never averaged. The build stops if the two overviews are not one grid.
- Only the tiles under the barrios are read, by HTTP range requests (`COG.values_at`).

**Grid.** `heat.py`'s 60 m grid in UTM zone 20 (EPSG:32620): 2,485,382 cells whose center is in a barrio. Each cell takes the 40 m pixel under its center; scenes in zone 19 are mapped onto the grid with pyproj.

**Clear observations.** An observation counts when the scene classification says **vegetation (4)** or **not vegetated (5)** and both reflectances are above zero. Clouds (8, 9), thin cirrus (10), cloud shadow (3), dark area or terrain shadow (2), water (6), unclassified (7), saturated or defective (1) and no data (0) are left out.

**One view per pass.** Where two MGRS tiles of the same pass overlap (the same satellite on the same day), a cell keeps one value, from the first tile in name order, so a pass is not counted twice.

**Composite.** Each cell's value is the **median** of its clear views, exact, as in `heat.py`. A cell needs at least 3 views. The median is computed in eight blocks of cells, so the build never holds all the observations in memory at once.

**Cache.** The build keeps, for each scene, the cells it saw clear and their NDVI (`cache/vegetation/values/`), not the image tiles. It holds 197 MB for the 984 scenes, against several GB for the tiles, which keeps the nightly rebuild's cache small; a rebuild from it takes about 90 seconds. A rebuild from the cache needs no network. The folder's name holds the reading rule (`RULE` in `vegetation.py`): a change in how a scene is read must change it, so old values are never mixed with new ones.

**Areas.** A cell belongs to the barrio whose outline holds its center. Municipios and Puerto Rico **pool the cells** of their barrios.

**Classes.** USGS reads NDVI this way: barren rock, sand or snow at 0.1 or less; sparse vegetation such as shrubs and grassland at about 0.2 to 0.5; dense vegetation such as forests and crops at their peak at about 0.6 to 0.9. The build uses:
- **dense vegetation:** NDVI 0.6 or more;
- **little or no vegetation:** NDVI below 0.2. In Puerto Rico that is mostly pavement, roofs and bare soil.

A 40 m pixel mixes a roof, a yard and a tree, so a street lined with trees reads in between. The shares depend on the pixel size; compare places with each other, not with figures made at another resolution.

**Residents.** As in `heat.py` (`heat.block_cells`, shared): each 2020 census block with residents counts whole on the cell under its internal point, in the barrio the geography crosswalk gives it. So the barrios' residents never exceed the crosswalk's and add up to the municipios'. These are estimates, rough for a barrio.

## Checks at every build

The build stops when any of these fails:

- Puerto Rico's median NDVI is between 0.4 and 0.9 (0.78).
- San Juan's median is below Puerto Rico's (0.31).
- Jayuya's (0.84) and Adjuntas's (0.84) medians are above Puerto Rico's.
- At least 95% of the cells have a value (99.4%; the typical cell has 30 views; 11,079 residents live in blocks whose point falls on no cell with a value and count as not on bare land).
- At least 600 scenes are found (984).
- Greener barrios are cooler: across the barrios, the Spearman rank correlation of median NDVI with median surface temperature in `heat_barrio.json` is −0.3 or less (−0.894), when that file is there.

`tests/test_vegetation.py` checks the scene reader, the cache, the composite and the published files:

- **The scene reader, on small Sentinel-2-like scenes written in the test:** each class of the scene classification, NDVI from reflectance, a pixel with no data, cells outside a scene, and overviews that are not one grid.
- **The cache:** it gives back what was read and answers offline; a missing scene stops an offline rebuild.
- **One view per pass** and the grouping of tiles by pass.
- **The composite:** the median, the minimum of three views, an overlapping tile that must not add a view, and the same answer in one block or three.
- **The published files:** shapes, ranges, residents that add up, and the checks above.

## Refresh

- **Unit `vegetation`** in `refresh/sources.json` runs `python vegetation.py --refresh`.
- **When it changes.** The source check (`copernicus_sentinel2_l2a`, calendar rule `summer`) turns each October, when a new summer is complete, as heat's does. Rebuild heat first: the vegetation build checks itself against the heat file.
- **Review.** A person reads the rebuild (review `human`), because a new summer moves every barrio's figures.
- **Cache.** `rebuild.yml` caches `cache/vegetation`, so a run reads only the new summer's scenes.

## License

Copernicus Sentinel data are free, full and open to use, including for commercial use, with the credit "Contains modified Copernicus Sentinel data [year]" for modified data such as these figures. The source card is `copernicus_sentinel2_l2a` in `dictionary_src/sources.json`. Earth Search and the AWS Registry of Open Data serve the copy; their terms cover access, not the data. No image is published, only figures by area.
