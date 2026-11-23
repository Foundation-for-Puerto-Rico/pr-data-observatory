# Raster reader (`raster.py`)

Step 0 of the terrain and climate plan (`docs/terrain-climate-proposal-2026-11.md`, HANDOFF decision 80, approved 2026-11-04). It publishes nothing: it is the piece the satellite and lidar steps build on.

## Why our own reader, not rasterio

Decision 80 (b) left the choice to this step. The build reads Cloud Optimized GeoTIFFs (COGs) with a small module of its own, `raster.py`, which uses only what `requirements.txt` already has (numpy, zlib, requests, pyproj, shapely). The reasons:

- **Only Puerto Rico's tiles are downloaded.** A COG keeps its tile index at the front of the file, so the reader fetches the header and then only the tiles under the area asked for, with HTTP range requests. Reading the 1 km around Cerro de Punta from a 3DEP tile took 2 requests and 0.9 MB, out of a file of about 450 MB.
- **No GDAL stack** in the build or the GitHub Actions runs. `landslide.py` already avoided rasterio for the same reason.
- **The family of files is small and known.** Every source the plan names uses the same few TIFF features (below). The reader refuses anything else with an error that names the tag, so a file it would misread is never summarised.

If a later source needs more (JPEG or WebP compression, several bands in one file, rotated grids), adding `rasterio` stays possible, and the summaries would not change.

## What it reads

What the sources use, read from their headers on 2026-11-04:

| Source | Compression | Predictor | Sample type | Tile |
|---|---|---|---|---|
| Landsat Collection 2 Level-2, Microsoft Planetary Computer | Deflate | none | uint16 | 256 |
| Sentinel-2 L2A, Earth Search on AWS | Deflate | horizontal | uint16, uint8 | 1024, 512 |
| USGS 3DEP 1 m and 1/3 arc-second, The National Map | LZW | floating point | float32 | 512 |

`raster.py` reads:

- classic TIFF and BigTIFF, in either byte order
- tiled images, one sample per pixel
- no compression, Deflate or LZW
- predictor 1 (none), 2 (horizontal) or 3 (floating point)
- integers and floats of 8 to 64 bits
- overviews and sparse tiles (no bytes: nodata)
- the GDAL nodata tag
- a north-up grid: ModelTiepoint plus ModelPixelScale, or ModelTransformation without rotation
- the CRS as an EPSG code from the GeoKeys; RasterPixelIsPoint is shifted half a pixel, as GDAL does

It refuses, with a `RasterError` naming the cause: striped TIFFs, several samples per pixel, other compressions, rotation, and a user-defined CRS.

## How to use it

```python
import raster
cog = raster.COG(url, cache="cache/raster/landsat")     # header only; a local path works too
arr, tr = cog.read_bbox((-66.2, 18.3, -65.9, 18.5))      # lon/lat box -> array and its transform in the raster's CRS
stats = raster.zonal(arr, tr, cog.epsg, shapes, nodata=cog.nodata, valid=clear_mask)
heights = cog.sample(lons, lats)                         # values at points (nan outside or on nodata)
```

- **Transform:** `(a, b, c, d, e, f)`, where x = a·col + c and y = e·row + f (GDAL's order).
- **Summaries (`zonal`):** a pixel belongs to a polygon when its centre is inside it, the rule of `landslide.py`. Each polygon gets `pixels` (centres inside), `valid` (with a value after nodata and the optional mask), and `mean`, `min`, `max`, `p10`, `p50`, `p90`. Polygons are reprojected to the raster's CRS with pyproj, and the statistics are `None` when no pixel is valid.
- **Values are returned as stored.** Scale and offset belong to the step that uses them, and that step names them. For example, Landsat surface temperature in kelvin is DN × 0.00341802 + 149.0.
- **Scattered pixels (`values_at`, added for `heat.py`):** `cog.values_at(cols, rows, level)` returns the stored values at pixel positions and reads only the tiles that hold them, in parallel. For Puerto Rico's land cells in a Landsat scene that is about 2 MB, against several times more for the rectangle around the island, which is mostly sea. `sample()` uses it.
- **Sentinel-2 (`vegetation.py`):** Earth Search's Sentinel-2 files carry overviews made with GDAL; the tag `OVR_RESAMPLING_ALG` says how. The 10 m bands' overviews are averaged (AVERAGE) and the scene classification's keep the most common class (MODE), so both can be read at an overview without mixing classes. Read the tag before using an overview of a class band: an averaged class is not a class.
- **A CRS given as text (`epsg=`, added for `ecostress.py`):** some files name their projection only as text (GeoKeys 32767, user-defined). `COG(src, epsg=32619)` gives it; a file that names its own EPSG code is never overruled (a different `epsg=` is an error).
- **Offline (`offline=True`):** any read that is not in the cache raises a `RasterError`, so a rebuild from the cache (`heat.py --check`) can never touch the network. The header is cached too (`header.bin` beside the tiles).
- **Cache:** tiles are kept under the folder given, keyed by the URL without its query string. Planetary Computer's short-lived token is in the query string, so a new token still finds the cached tiles. A second build reads nothing from the network. `cache/` is not committed.
- **Retries:** HTTP 429 and 5xx are retried four times with backoff. A server that ignores range requests stops the read with an error instead of downloading a whole scene.
- **Speed:** LZW is decoded in pure Python, about 0.35 s for a 512 × 512 float tile. Puerto Rico at 10 m is about 200 such tiles, so a minute or two the first time.

## How it is checked

- **`python -m unittest tests.test_raster`** (no network) writes small GeoTIFFs and reads them back exactly. It covers 144 combinations: byte order, classic or BigTIFF, three compressions, six sample types and two predictors each. It also checks windows across tile edges and outside the image, that only the tiles under a window are read, sparse tiles, overviews, the georeferencing cases, point sampling in lon/lat over a UTM grid, `zonal` against values counted by hand, the cache, and the refusals. Its LZW encoder sits in the test file and round-trips a 60,000-byte stream through every code width and a table reset.
- **Mutation check (2026-11-04):** six deliberate bugs in `raster.py` were each caught by the tests: LZW early change off by one, floating-point byte order, zonal counting the bounding box, pixel corner instead of centre, no PixelIsPoint shift, and sparse tiles read as data.
- **`python raster.py --check`** (network) reads real files and compares them with known facts. All passed on 2026-11-04:

| Check | Result |
|---|---|
| 3DEP 1/3 arc-second, highest cell within 1 km of Cerro de Punta | 1,335.9 m, against the published 1,338 m, from a 10 m cell |
| The same box at overview 2 | Mean 1,068.1 m, against 1,069.0 m at full resolution |
| Landsat 9 surface temperature over San Juan, LC09_L2SP_004047_20261029 | Median 37.7 °C at about 10:30 local time, 34,205 of 40,635 pixels with a value |
| Sentinel-2 NDVI over El Yunque, S2C_20QKF_20261028 | Median 0.76 (dense forest) |

  The Landsat pixels without a value are not water or scene fill: 60% of them are flagged cloud in QA_PIXEL. USGS leaves surface temperature unset there, and step 1 masks those pixels with QA_PIXEL. Scene footprints are slanted, and path/row 004/048 stops at about 18.41° N, so the check picks a scene whose footprint holds the whole box.

## Next

Step 1 of the plan builds on this: dry-season and summer Landsat surface temperature composites by barrio, masked with QA_PIXEL, with Sentinel-2 vegetation from the same months.
