# Surface heat by barrio and municipio (`heat.py`)

Step 1 of the terrain and climate plan (`docs/terrain-climate-proposal-2026-11.md`, HANDOFF decision 80, approved 2026-11-04). Built on 2026-11-04 on branch `data/urban-heat-landsat`.

`heat.py` writes two files:

- `heat_series.json`: 5 datasets for the 78 municipios and Puerto Rico.
- `heat_barrio.json`: the same 5 datasets for the 901 barrios.

They are shaded on the map's Economy tab, in the group "Environment · Surface heat (Landsat)", by municipio or by barrio.

## What it measures, and what it does not

**Land surface temperature** is the radiative temperature of the ground, roofs, pavement and tree canopy, measured by Landsat's thermal infrared sensor (TIRS, about 100 m). It is **not the air temperature** people breathe. On a sunny morning, a dark roof or a parking lot can be 20 °C or more above the air, and a forest stays close to it.

Landsat passes Puerto Rico at about **10:30 local time**. The figures are mid-morning values on **clear** days of **June to September of the last three complete summers** (2024–2026 in this build). They do not show the afternoon peak, the night (step 2 of the plan, ECOSTRESS) or cloudy days.

**Elevation cools the land.** The Cordillera's barrios are cooler than the coast's because they are higher, as well as because of their trees. Compare places at similar heights.

## The figures (build of 2026-11-04)

| Key | What | Puerto Rico |
|---|---|---|
| `heat_lst_med` | Median land surface temperature, summer mornings (°C) | 33.4 |
| `heat_lst_p90` | 90th percentile: the hottest tenth of the land starts here (°C) | 40.5 |
| `heat_hot_land_pct` | Share of land above Puerto Rico's 90th percentile (%) | 10.0, by construction |
| `heat_res_hot` | 2020 residents on that land (estimate) | 1,236,030 |
| `heat_res_hot_pct` | The same, as a share of residents (estimate, %) | 37.6 |

- **Hottest municipios:** the dry south coast and the San Juan area. By median: Santa Isabel (42.8 °C), Salinas (41.0), San Juan (40.9), Lajas (40.7), Guánica (40.0) and Cataño (39.9).
- **Coolest municipios:** the Cordillera. Jayuya (29.5 °C), Maricao (29.6) and Adjuntas (29.7).
- **Residents on hot land:** 37.6% of residents live on the hottest tenth of the land. That is far above 10% because people live on the warmer lowland and urban land. Santa Isabel (91.1%), Salinas (80.1%) and Ponce (75.7%) have the highest shares. Lares, Maricao and Orocovis have none.

## How it is made

**Scenes.** Every Landsat 8 and 9 Collection 2 Level-2 scene over Puerto Rico from June to September of the three summers, with less than 70% cloud cover.
- This build found 246 scenes, and 244 had at least one clear cell.
- They come from six path/rows (004–006 by 047–048), in UTM zones 19 and 20.
- They are read from Microsoft Planetary Computer's copy with its anonymous token. The AWS copy is requester-pays.

**Reading.** `raster.py` (`docs/raster.md`) reads each scene's surface temperature (ST_B10) and pixel quality (QA_PIXEL) at their first overview, 60 m.
- It uses HTTP range requests and only the tiles that hold land cells (`COG.values_at`): about 2 MB a scene for these two bands. The gap fill reads six more bands where USGS has no value, so the cache in `cache/heat/` holds 1.6 GB for the 246 scenes (measured 2026-11-04; this page first said 250 MB, which left out the gap fill's bands). Keep it outside a synced folder.
- A rebuild from the cache takes under 3 minutes and needs no network.

**Grid.** One 60 m grid in UTM zone 20 (EPSG:32620): 2,485,382 cells whose centre is in a barrio.
- Each cell takes the scene pixel under its centre.
- Scenes in zone 19 are mapped onto the grid with pyproj.

**Clear observations.** An observation counts when all of these hold:
- QA_PIXEL bit 6 says clear;
- bit 4 says no cloud shadow;
- bit 7 says not water;
- bit 0 says not fill.

There are 83.8 million clear observations in all.

**Composite.** Each cell's value is the **median** of its clear views. A thin cloud edge that the flags miss reads cold, and a median barely moves because of it.
- The typical cell has 30 views. A cell needs at least 3; every cell has a value in this build.
- The median is exact: all observations are kept in memory.
- A mean clipped at 2.5 standard deviations was tried first and dropped. With fewer than 8 views, one outlier widens the spread so much that it can never be clipped. The test `test_composite_median_and_minimum_views` covers this case.

**Areas.**
- A cell belongs to the barrio whose outline (`barrios.geojson`) holds its centre, as in `landslide.py`.
- Municipios and Puerto Rico **pool the cells** of their barrios. They are not averages of barrio figures.

**Hot land.** The cells above Puerto Rico's 90th percentile of the composite: 40.5 °C in this build.

**Residents.** Each 2020 census block with residents counts whole on the cell under its internal point.
- It counts in the barrio that the geography crosswalk gives it (`network.load_block_table` and `geo.block_barrios`, the rule of `exposure.py`). So the barrios' residents never exceed the crosswalk's and add up to the municipios'.
- 1,983 residents live in blocks whose point falls on water or off the generalised outlines. They count as not on hot land.
- These are estimates, rough for a barrio, where the edge of hot land can cut a block.

## Where USGS has no surface temperature (the gap fill)

The first build stopped on its own coverage check: only 86.8% of the cells had 3 clear views.
- **The gap is in the source, not the reader.** The cells without views were not cloudy. They formed whole areas: almost all of Aguada and Aguadilla, most of Rincón and Moca, about half of Isabela, and parts of the east (Fajardo, Luquillo).
- **The cause is emissivity.** USGS computes surface temperature with an emissivity from **ASTER GED**, a global emissivity dataset. Where ASTER GED has no value, USGS leaves ST_B10 empty in every scene. The scenes' emissivity band (ST_EMIS) is empty at those places, and their thermal radiance band (ST_TRAD) is not. Checked 2026-11-04 on LC09_L2SP_005047_20240608 and five other dates.

So there, and only there, `heat.py` computes the surface temperature itself with the same physics USGS uses:

- **Radiance and atmosphere.** It reads the scene's thermal radiance at the top of the atmosphere, upwelling and downwelling radiance, and atmospheric transmittance (ST_TRAD, ST_URAD, ST_DRAD, ST_ATRAN, all in every Level-2 scene).
- **Surface radiance.** It removes the atmosphere: L_surface = ((TRAD − URAD) / ATRAN − (1 − ε) · DRAD) / ε.
- **Temperature.** It inverts Planck's law with the band's constants K1 and K2 (Landsat 8: 774.8853, 1321.0789; Landsat 9: 799.0284, 1329.2405).
- **Emissivity ε.** It reads ε from NDVI (red and near infrared surface reflectance, SR_B4 and SR_B5) on a table fitted to **USGS's own emissivity**: the median of ST_EMIS for each NDVI step of 0.05, on six summer scenes of paths 004 and 005, 2.69 million clear pixels (`EMIS_NDVI` in `heat.py`).

**How good it is.**

- With USGS's own emissivity, this formula gives USGS's surface temperature within 0.15 K. That shows the radiance terms are read correctly.
- With the fitted emissivity, leaving each of the six scenes out of the fit in turn, the method gives USGS's value with a bias of −0.12 to +0.18 K and a spread of 0.60 to 0.85 K per pixel and view. A generic textbook emissivity from NDVI did worse: +0.52 K bias and 0.83 K spread.
- **Every build checks it again** (`fill_check`): on the three clearest scenes, every 7th clear cell where USGS has a value. The build stops if the bias passes 0.5 K or the spread 1.2 K. In this build:

| Scene | Pixels | Bias (K) | Spread (K) |
|---|---|---|---|
| LC08_L2SP_005047_20260926 | 215,211 | −0.12 | 0.81 |
| LC08_L2SP_005048_20260926 | 79,867 | −0.24 | 1.00 |
| LC09_L2SP_006048_20250704 | 1,850 | +0.21 | 0.48 |

- **What changes for a reader.** 13.5% of the cells are mostly filled. A cell's value is the median of about 30 views, and a barrio's of many cells, so the spread shrinks; the bias, a few tenths of a degree, stays. By comparison, the municipios range from 29.5 to 42.8 °C. The files record how much of each municipio was filled (`notes.gap_fill`): Aguada 99.8%, Aguadilla 99.6%, Rincón 95.0%, Moca 83.0%, Isabela 56.3%, Maricao 41.8%, Añasco 40.5%, Lares 35.0%, Las Marías 34.5%, Luquillo 29.0%, Fajardo 28.8%, San Sebastián 28.0%. Each dataset's caveats say so.

## The surface on the map (HANDOFF decision 88, prototype)

The 60 m composite is also drawn as one picture, so a visitor sees every cell, not only the averages by area. In the 3D view it is draped on the terrain under the 3D buildings, which gives the look of a city's heat map seen at an angle; on the 2D map it lies under every other layer. Switch: Explore › Map layers › Environment and climate › "Surface heat, summer mornings" (`l=surfheat`), and the same row in the 3D view's Layers tab.

- **Files.** `heat.py` writes `heat_surface.png` (an indexed PNG of 64 colour steps, transparent where there is no value; about 1.1 MB) and `heat_surface.json` (its corners, size, pixel size and scale), with `surface_image.py`. Both pages read them only when the switch is turned on.
- **Pixels.** One pixel is about one 60 m cell, in Web Mercator (the projection both maps stretch an image in). Each pixel takes the cell under its centre, so nothing is invented between cells. The image is 3,649 × 1,210 pixels, under the 4,096 that every phone's WebGL can hold as one texture; Mona, Monito and Desecheo are left out because the sea between them and the main island would make it wider.
- **Scale.** Diverging, from `core/palettes.js` DIVERGING: grey at Puerto Rico's median (33.4 °C in this build), dark blue and dark red at the median minus and plus the larger distance to the 2nd and 98th percentiles, rounded up (21.4 to 45.4 °C); values beyond are drawn at the ends. A rainbow scale like many city heat maps was not used: it is hard to read for people with colour blindness and has no neutral middle.
- **Colours that follow the view (decision 88, 2026-11-06).** By default the colours are recomputed for the land in view after each move (`site/js/core/surfscale.js`, loaded with the image): grey at the median of the land in view, the darkest blue and red at the larger distance from it to the 2nd and 98th percentiles (at least 1 °C). Over San Juan, where most land is above the island's median, the city then shows its own hot and cool places instead of one red. In the 3D view the ground in view is the lower 60% of the screen, so a tilted camera's horizon does not count. The legend's switch goes back to Puerto Rico's fixed scale, and its numbers always say which scale is drawn. No value changes: each pixel keeps its measured step (64 steps of 0.38 °C); only the colour given to a step changes. `tests/surfscale.test.js` checks that the page reads the steps with the image's own palette.
- **Morning and night (decision 88, 2026-11-06).** The legend's "Hora: Mañana / Noche" switch shows the night composite of `ecostress.py` instead: `night_heat_surface.png` and `.json`, drawn the same way on the same grid (ECOSTRESS read at 70 m), with its own scale around Puerto Rico's night median (24.0 °C; 19 to 29 °C). At night elevation dominates: the Cordillera and El Yunque stay coolest, the coasts and the San Juan metro area warmest. The Colours switch works on either image. `ecostress.py --from-cache` writes the night image without the NASA token, and the ECOSTRESS workflow keeps it with its files.
- **What the picture cannot show.** Landsat's thermal sensor sees about 100 m, so a street or a single roof is not resolved; a 10 m estimate by thermal sharpening with Sentinel-2 was tried (branch `data/heat-sharpen`, `heat_sharpen.py`) and not published: degrading the measured heat and sharpening it back beat plain smoothing only for targets of 180 m and coarser, so detail under that is not supported by the data (decision 88).
- **Check.** `python heat.py --check` also compares the image and its description with what the cache gives.

## Checks at every build

The build stops when any of these fails:

- Puerto Rico's median is between 25 and 45 °C (33.4).
- San Juan's median is above Puerto Rico's (40.9): urban heat.
- Jayuya's (29.5) and Adjuntas's (29.7) medians are below Puerto Rico's: the Cordillera.
- At least 95% of the cells have a value (100%).
- At least 150 scenes are found (246).
- The gap fill matches USGS (above).

`tests/test_heat.py` checks the scene reader, the composite and the published files:

- **The scene reader, on small Landsat-like scenes written in the test:** each QA flag, the scale to °C, cells outside a scene, and a zone-19 scene landing on the right cells.
- **The gap fill:** it recovers a known temperature from radiance made with the forward model.
- **The median:** odd, even and empty cells, and a cold outlier.
- **The published files:** shapes, ranges, residents that add up, Puerto Rico's 10%, and the physics above.

## Refresh

- **Unit `heat`** in `refresh/sources.json` runs `python heat.py --refresh`.
- **When it changes.** The source check (`usgs_landsat_c2_st`, calendar rule `summer`) turns each October, when a new summer is complete. The figures move then and only then.
- **Review.** A person reads the rebuild (review `human`), because a new summer moves every barrio's figures.
- **Cache.** `rebuild.yml` caches `cache/heat`, so a run downloads only the new summer's scenes.
- **Inputs.** The block table and the block-to-barrio table (`cache/network`, `cache/geo`) come from `network.py` and `geo.py`, as for `exposure.py`.

## Licence

USGS Landsat data are US Government work in the public domain; USGS asks for credit ("courtesy of the U.S. Geological Survey"). The source card is `usgs_landsat_c2_st` in `dictionary_src/sources.json`. Planetary Computer's terms cover access to its copy, not the data. No image is published, only figures by area.
