# Slope of the land and contour lines (GIS tools step 2)

Plan: `docs/gis-tools-proposal-2026-11.md`, step 2 (HANDOFF decision 93). Code: `slope.py` (the figures and the image), `site/js/terrain.js` (the two map layers, loaded on first use), the threshold in `site/js/core/surfscale.js`.

## What visitors get

- **Explore › Environment and climate › Land:** two new layers on the 2D map.
  - **Slope:** the ground darker where it is steeper, from 0% to 60% or more. The legend's slider shows only the land at or above a slope (15% and 30% are marked). A click on the map gives the slope under the point.
  - **Contour lines:** lines of equal height, closer as you zoom in (100 m at the island's scale, then 50, 20 and 10 m), every fifth line thicker.
- **Three datasets by barrio and municipio** (group "Environment · Slope of the land (USGS 3DEP)"), for the map's shading, the area profiles, the workbench and the study areas: land steeper than 15%, land steeper than 30%, and the mean slope.
- **A threshold on the heat image too:** the Surface heat legend (2D map and 3D view) gets the same slider: "only the ground at X °C or hotter".

## How the figures are made (`slope.py`)

1. **Elevation:** USGS 3DEP 1/3 arc-second (about 10 m), the newest version of each one-degree tile over Puerto Rico (the tiles `climb.py` reads; version 2026-07-22), read with `raster.py` in 117 windows of 0.1 degree.
2. **Slope of each 10 m cell:** Horn's method (the eight neighbours, the nearest counting twice; as GDAL, QGIS and ArcGIS do it), with the cell's width and height in metres at its latitude, as rise over run × 100. A cell next to one with no height has no slope.
3. **Blocks of 6 × 6 cells** (2 arc-seconds, about 60 m): cells with a slope, cells steeper than 15% and than 30%, the sum of their slopes, their area. A block belongs to the barrio that holds its centre (the nearest within 100 m off the coast). **Blocks in no barrio are left out:** the elevation model covers the sea too, so without this a quarter of the cells would be sea (found by the build's own check on the first run).
4. **Areas:** the shares and the mean of the barrio's cells; municipios and Puerto Rico pool their barrios' cells.
5. **The image:** each land block's mean slope on a fixed scale of 64 steps from 0% to 60%, pale to dark earth (no blue, red or yellow, which the flood, landslide and heat layers use), one block per pixel in Web Mercator: 3,730 × 1,241 pixels of 58.8 m, 1.6 MB. Mona, Monito and Desecheo are left out of the image (not of the figures), as in the heat image.
6. **Cache:** the block grids are kept in `cache/slope/blocks_<version>.npz`, so `python slope.py --check` and a rebuild read no elevation again. The first read of the tiles takes about 25 minutes (the reader decodes LZW in Python).

**Checks that stop the build:** Puerto Rico's share steeper than 30% between 15% and 55%; Jayuya, Orocovis and Barranquitas steeper than Puerto Rico; Cataño under 5% of its land steeper than 15%; the counted cells cover 97% to 110% of the barrios' Census land area.

## Results (2026-11-10)

| | Steeper than 15% | Steeper than 30% | Mean slope |
|---|---|---|---|
| Puerto Rico | 61.7% | 44.1% | 29.7% |
| Steepest (30%) | Maricao 83.3%, Jayuya 77.2%, Adjuntas 76.1% | | Ciales 53.1%, Maricao 52.6% |
| Flattest | Loíza 1.2%, Cataño 2.0% | Cataño 0.1%, Loíza 0.5% | Loíza 1.6%, Cataño 2.6% |

The counted cells cover 101.7% of the barrios' Census land area (inland water inside the outlines counts as flat land).

**Checked against the soil survey (SSURGO, `soils.geojson`):** weighting each map unit's representative slope by its area gives a mean of 29.9%, against 29.7% here. Its shares are higher (70.8% of the mapped land steeper than 15%, 51.9% steeper than 30%) because a map unit carries one slope for all of its land, while here each 10 m cell is counted.

## The contour lines (`js/terrain.js`)

While the layer is on, the browser asks the terrain tiles the 3D view uses (AWS Terrain Tiles, Terrarium encoding; in Puerto Rico from USGS 3DEP) for the tiles in view up to zoom 15, decodes each pixel's height ((R × 256 + G + B / 256) − 32768 m), and traces the lines with marching squares (`marching()`, tested in `tests/terrain.test.js`), saddle cells split by the mean of their corners. Levels above 0 m only. Nothing is stored. A line can show a one-pixel gap where two tiles meet.

## The threshold (`core/surfscale.js`)

`floor(v)` makes `paint()` leave out the steps whose value is below `v`; `threshold()` draws the slider. Each slider names its image (`data-surf-min="<index>"`), so the heat and slope legends can be open together. On release the image is repainted (the page's `surfPaint()`, or for the slope layer `slopePaint()`); while it moves only its label follows.

## Not done here

- Slope and contours in the 3D view (it shows the terrain itself).
- Labels on the contour lines.
- Aspect (which way a slope faces) and hillshade on the 2D map.
