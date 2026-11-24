# Proposal: new satellite, building and places sources (GeoAI list)

Date: 2026-11-09. Status: **approved by the project lead on 2026-11-09 (decision 91 in HANDOFF.md), all five choices as proposed; nothing built yet.** This pull request changes no page and builds no data. It adds eight rows to the wanted-data list (`site/data/wanted.json`), rewrites the `buildings` row with what was measured, and adds five glossary terms (building footprint, land cover, tree cover loss, active fire detection, HLS).

**In one paragraph.** the project lead shared a list of 30 open geospatial sources on 2026-11-09. Six are already in the observatory (Sentinel-2, Landsat, OpenStreetMap, Overture places, Planetary Computer, and better elevation than SRTM). Fifteen are machine-learning training sets, tools or not about Puerto Rico. Nine would add something, and they are tested and ranked below. The first and largest gain is **buildings**: Overture adds 656,964 buildings from Google and Microsoft that the 3D view does not draw today. Next comes **land cover change since María**, then **fires**, a denser **greenness series**, and a second **places** source.

## What was tested (2026-11-09, no key needed for any test)

| Source | Result |
|---|---|
| Overture buildings, release 2026-10-21.0 (GeoParquet on S3, read with DuckDB) | Puerto Rico, Mona to Culebra: **2,157,363 buildings**. 1,500,399 from OpenStreetMap (what the 3D view already draws, through OpenFreeMap), 536,571 from Google, 120,393 from Microsoft. **203,060 (9.4%) have a height**, 8,499 a number of floors. Licence ODbL. |
| Overture building tiles (PMTiles) | `tiles/2026-10-21.0/buildings.pmtiles` on the `overturemaps-extras-us-west-2` bucket: 180 GB worldwide, answers range requests from any website (CORS `*`). Overture says the tiles are for inspection, not production, and each release has a new path. |
| Esri / Impact Observatory 10 m land cover (Planetary Computer `io-lulc-annual-v02`) | Years 2017 to 2023, 14 tiles over Puerto Rico, CC BY 4.0. **`raster.py` reads it** (UTM 20N). |
| ESA WorldCover 10 m (Planetary Computer `esa-worldcover`) | 2020 and 2021 only, CC BY 4.0. **`raster.py` reads it.** |
| Hansen tree cover loss v1.12 (2001-2024) | Tile 20N_070W downloads, CC BY 4.0, but it is a **striped** GeoTIFF: `raster.py` refuses it. |
| HLS v2.0 (Planetary Computer `hls2-s30`, `hls2-l30`) | Since 2020, **no NASA Earthdata login needed** on Planetary Computer. **`raster.py` reads it** (UTM 19N). |
| Microsoft building footprints (Planetary Computer `ms-buildings`) | A Puerto Rico partition exists (2022-07-06), ODbL. Not needed separately: Overture already includes it. |
| NASA FIRMS active fires | Needs a free MAP_KEY. Suomi NPP stopped feeding FIRMS on 2026-11-02; NOAA-20 and NOAA-21 continue. |
| Foursquare Open Source Places | Apache 2.0, but now **gated** on Hugging Face (contact details asked before download). Its `date_closed` is when Foursquare flagged a place closed, often missing. |
| GlobalBuildingAtlas heights | Heights and LoD1 models are **CC BY-NC 4.0** (non-commercial); polygons are a separate ODbL set. |

## The steps, first visible result first

Effort as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks.

### A. Buildings (Overture)
- **A1. Buildings by barrio (M). Shows on the site first.** **Built on 2026-11-09 (branch `data/buildings-barrio`): `buildings.py`, `buildings_series.json` and `buildings_barrio.json`, shaded on the Analysis tab (group "Housing · Buildings (Overture)"); method and checks in `docs/buildings.md`. It reads Overture with the `overturemaps` package already in `requirements.txt`, so DuckDB (choice b) was not needed. Landslide classes were left for later: the flood count came first.** A `buildings.py` step reads Overture's Puerto Rico buildings once per release and publishes only summaries by barrio and municipio: number of buildings, footprint area, share of land under roofs, buildings inside a FEMA flood hazard area and inside landslide susceptibility classes, and the share from each source. It shows as barrio shading in Explore (Housing, and Hazards and resilience) and in the place profile. **No building shape or value per building is published in this step.**
- **A2. Fill the gaps in the 3D buildings (M-L).** **Built on 2026-11-10 (branch `data/buildings-3d`): option 3, our own tiles of only the missing buildings, `buildings_gap.pmtiles` (7.4 MB), by `buildings3d.py`; measured first: Overture's tiles for Puerto Rico 153.5 MB, every building slimmed 29.0 MB. `docs/buildings3d.md`.** Draw the Google and Microsoft buildings that OpenStreetMap lacks under the same 3D switch. Three ways to host the tiles, to be chosen by measuring:
  1. read Overture's own PMTiles directly: nothing to host, but Overture calls them "not for production", and each monthly release needs a new path (the refresh bot would update it);
  2. our own Puerto Rico extract of those tiles (`pmtiles extract`): the size has to be measured; over 100 MB it cannot be on GitHub Pages, and would need the Azure Static Web Apps site (PR #106, open) or object storage;
  3. our own tiles of only the 656,964 buildings that OpenStreetMap lacks, the smallest option, on top of the base map's buildings.

  Buildings without a height get one flat default height and the popup says "height unknown". The PMTiles reader loads only when the 3D buildings are switched on, so the map's first-load scripts do not grow.
- **A3. A height for every building (M), after Compliance.** GlobalBuildingAtlas heights joined to the footprints, checked against the 3DEP lidar (surface minus terrain). Its CC BY-NC licence needs Compliance's OK first.

### B. Land cover change since María (L)
The yearly 10 m land cover 2017-2023, with ESA WorldCover as a check where the two overlap, and Hansen tree cover loss by year since 2001. Summaries by barrio and municipio and a Knowledge Area page, "How the land changed". Hansen needs a small addition to `raster.py` (read striped files; the strip index works with range requests like tiles) or a one-time download into the cache. Labels: modelled land cover changes include model noise; tree cover loss includes hurricane damage that regrows, so it is not called deforestation.

### C. Fires (S-M)
**Built on 2026-11-10 (branch `data/active-fires`): `fires.py`, `fires_series.json` (detections by municipio 2019-2025, per 100 km², and the last 12 months), workflow `fires.yml`; `docs/fires.md`. The complete years come from FIRMS's yearly country files, which need no key; the key (secret `FIRMS_MAP_KEY`, set by the project lead on 2026-11-10) is used only for the last 12 months.**
NASA FIRMS active fire detections (VIIRS 375 m), counted by municipio and month, refreshed daily by the bot. **The project lead needs to request the free MAP_KEY** (it is sent by email), and we store it as a GitHub Actions secret, as with ECOSTRESS. Detections are counted, never drawn as burned areas.

### D. Greenness through the seasons (M)
HLS every 2 to 3 days at 30 m, made into monthly greenness by barrio, so drought and recovery after storms show over time. It extends the live vegetation layer (`vegetation.py`), which has one summer composite.

### E. A second places source (S to check)
Foursquare Open Source Places, to measure how complete Overture's places are in Puerto Rico, and to test whether its dates say anything about businesses opening and closing. Downloading it means sharing FPR's contact details with Foursquare on Hugging Face, which needs the project lead's OK. Every point goes through `places_privacy.py`, as Overture's do.

### Later, each a proposal of its own
- **Disaster imagery** (Maxar Open Data, Copernicus EMS) for Fiona, María and the 2020 earthquakes: coverage, whether the Maxar program still runs, and Compliance on non-commercial terms first.
- **NASA Prithvi** (the geospatial foundation model) on HLS, for FPR's own flood, burn or crop maps. This is analysis, not data, and needs its own plan.

## Not taken, and why
- **Training sets for machine learning:** DSTL (Kaggle), SEN12MS, DeepSat SAT-4/SAT-6, SATIN, LandCover Aerial, xView2, Sen1Floods11. They train models; they are not maps of Puerto Rico. They only matter if the Prithvi work goes ahead.
- **Scottish lidar:** not Puerto Rico. **SRTM:** the USGS 3DEP lidar and 1/3 arc-second elevation are sharper.
- **Dynamic World and the Google Earth Engine catalogue:** both need an Earth Engine account and an export step, against the project lead's rule of 2026-11-04 that the observatory builds only from sources a script can read directly. Planetary Computer covers the same sources.
- **Google Dataset Search, the IBM-NASA Hugging Face collection:** tools to find datasets for this list, not layers.
- **Google Open Buildings, Microsoft footprints, OpenStreetMap buildings separately:** Overture already merges them.

## Rules that apply to every step
- **Private homes:** most buildings are homes. Shapes may be drawn as a base map draws them, but no value is attached to one building (no heat, flood or risk per house); figures are by barrio or larger.
- **Every technical word** gets a sourced English and Spanish glossary entry in the same PR (five added here).
- **Summaries, not images,** unless a step says otherwise; caches in `C:/t/cache`, never in the synced folder.
- **Credit lines:** "© Overture Maps Foundation, © OpenStreetMap contributors" (ODbL); "Impact Observatory, Esri" (CC BY 4.0); "Source: Hansen/UMD/Google/USGS/NASA"; "NASA FIRMS"; "ESA WorldCover"; HLS from NASA LP DAAC through Microsoft Planetary Computer.

## Decisions for the project lead (decision 91)
- (a) Approve the order: A1, A2, then B, C, D, E; A3 and the later items wait on Compliance or their own proposal.
- (b) A1 adds DuckDB to the refresh environment (`requirements-refresh.txt`) to read Overture's GeoParquet. It is one Python package with no GDAL.
- (c) A2 hosting: measure options 2 and 3 first, and use option 1 only if neither fits.
- (d) C: request the FIRMS MAP_KEY.
- (e) E: OK to share FPR's contact details with Foursquare on Hugging Face, or skip E.

## Sources checked
- Overture: [Buildings guide](https://docs.overturemaps.org/guides/buildings/), [cloud sources](https://docs.overturemaps.org/getting-data/cloud-sources/), [Overture + PMTiles](https://docs.overturemaps.org/examples/overture-tiles/), [STAC catalogue](https://stac.overturemaps.org/catalog.json)
- [Microsoft Planetary Computer STAC API](https://planetarycomputer.microsoft.com/api/stac/v1/collections)
- [Hansen Global Forest Change v1.12](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2024-v1.12/download.html)
- [NASA HLS project](https://hls.gsfc.nasa.gov/)
- [NASA FIRMS API](https://firms.modaps.eosdis.nasa.gov/api/) and [FIRMS FAQ](https://www.earthdata.nasa.gov/data/tools/firms/faq)
- [Foursquare: access FSQ OS Places](https://docs.foursquare.com/data-products/docs/access-fsq-os-places), [Hugging Face card](https://huggingface.co/datasets/foursquare/fsq-os-places)
- [GlobalBuildingAtlas, ESSD 2025](https://essd.copernicus.org/articles/17/6647/2025/) and [GBA.LoD1 card](https://huggingface.co/datasets/zhu-xlab/GBA.LoD1)
