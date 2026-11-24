# Proposal: GIS tools on the map (buffer, dissolve, watersheds and more)

Date: 2026-11-09. Status: **approved by the project lead on 2026-11-09 (decision 93 in HANDOFF.md), all five choices as proposed; nothing built yet.** This pull request changes no page and builds no data.

**In one paragraph.** the project lead shared a list of 15 basic GIS tools on 2026-11-09 and asked which ones the observatory lacks and could add, kept simple for most visitors but open to a power user. Measured against main (`6aeeca5`): **3 are there**, mostly inside the build, **7 are partly there** (they run in the build or inside one feature, but a visitor cannot use them on their own data), and **5 are missing**. The proposal adds no GIS toolbox. It adds a few tools that feed the summary the observatory already has (the Study areas summary), so one engine serves all of them: a ring around a place, a merged region, a watershed and a travel-time area all become study areas. Interpolation (IDW, kriging) is left out for now.

## 1. The 15 tools against what the observatory has

| # | Tool | Today | Where | Proposed |
|---|---|---|---|---|
| 12 | NDVI | **Have it** | `vegetation.py`, Urban heat page | Nothing new; its average joins the area summary (step 1) |
| 2 | Clip | **In the build** | `geo.py`, `raster.py`, `heat.py`, `landuse.py` cut every layer to Puerto Rico and to barrios | **Download what's inside** an area (step 5) |
| 7 | Extract by mask | **In the build** | heat, landslide and flood figures by barrio | The same figures for *any* area: zonal statistics in the summary (step 1) |
| 3 | Intersect | Partial | Study areas give % of land in a FEMA flood zone and in a protected area (8,000-point grid) | % of an area in *any* polygon layer (step 1) |
| 5 | Spatial join | Partial | The build joins census blocks, stops and places to areas; a visitor cannot join their own points | **Count my points** by barrio or municipio (step 4) |
| 6 | Raster calculator | Partial | The workbench's Composite builder, by area | Keep it by area; no cell-by-cell calculator (section 4) |
| 13 | Reclassify | Partial | Choropleth classes (`classify.js`); raster layers have fixed classes | A threshold on raster layers ("show only slope over 30%") (step 2) |
| 8 | Slope | Partial | Inside `climb.py` and `landslide.py`; 3D hillshade; colleague PR #161 adds SSURGO slope classes | A slope layer and "% of steep land" by barrio (step 2) |
| 1 | Buffer | Missing as a tool | Fixed 400 m and 800 m distances to stops in the build | **Area around** a point, line or area (step 1) |
| 4 | Dissolve | Missing | The Eastern Region is built once in the build (`regions.py`) | **Build my region** from municipios or barrios (step 4) |
| 9 | Contour | Missing | The 3D view loads terrain tiles but draws no lines | Contour lines (step 2) |
| 14 | Flow accumulation | Missing | — | Read from USGS's stream network, not computed (step 3) |
| 15 | Watershed | Missing | Water-quality units cover drainage areas (`conditions.py`), but no watershed layer | Watershed layer and **What drains here** (step 3) |
| 10 | IDW | Missing | — | Not proposed (section 4) |
| 11 | Kriging | Missing | — | Not proposed (section 4) |

Not on the list, but the tool power users ask for most: **travel time** (where can I walk in 15 minutes?). The walking network is already published (`site/data/roads.bin`, `walknet.py`), so it can run in the browser (step 6).

## 2. What was checked (2026-11-09)

| Item | Result |
|---|---|
| Map page budget (`budget.py` on an LF copy of main) | Scripts **249.8 of 250 KB**, data 146.9 of 250 KB. **Every new tool must load on first use**, like the workbench. |
| Routes page budget | Scripts 29.8 of 30 KB. Nothing is added there. |
| 2D map library | Leaflet (`app.js`); rasters are laid as indexed PNG images (`surface_image.py`, `L.imageOverlay`). |
| Study areas engine (`core/study.js`) | Has point-in-polygon, area on a local flat projection, an 8,000-point sampling grid and GeoJSON import and export. Steps 1, 3, 4 and 6 reuse it; **no Turf.js** (too large for the budget). |
| USGS Watershed Boundary Dataset, region 21 | `WBD_21_HU2_GDB.zip`, 7.5 MB, updated 2025-01-08, public domain, script-readable from the National Map bucket. |
| USGS NHDPlus HR (streams, catchments, flow) | `NHDPLUS_H_2101_HU4_GDB.zip` 37.2 MB and `2102` 6.4 MB, 2023-12-20, script-readable. Which subregion holds which islands is confirmed in step 3. |
| USGS 3DEP 10 m elevation | Tiles `USGS_13_n19w068`, `n19w067`, `n19w066`: 64, 260 and 86 MB, updated 2026-08-06. The south coast below 18° N is in the `n18` row, read the same way. `climb.py` already reads this elevation. |

## 3. The steps, first visible result first

Effort as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks.

Everything runs in two places only: **the build** (Python, heavy raster work, done once) and **the visitor's browser** (light vector work on the visitor's own areas). The site stays static: no GIS server.

### Step 1. Area around + a richer summary (M). **Shows on the site first.**
- **Simple:** in Tools, "Area around": click a place, a stop or a point on the map, pick 400 m, 800 m, 1 km or 5 km. The ring becomes a study area and the summary opens.
- **Power user:** any distance, a ring around a line (a road) or around a study area, and an outer ring only (800 m to 1.6 km).
- **The summary gains measures** (zonal statistics on the same 8,000-point grid): mean surface heat, greenness (NDVI), % in each landslide class, % in *any* polygon layer the visitor picks (intersect). Each measure says whether it is counted, measured on a grid or estimated, as the summary does today.
- Code: a new on-use module (`core/gistools.js`, with the Spanish in its own file). Nothing added to the map's first load.
- What a raster measure needs in the browser is measured in this step: the heat image's colour steps, or a small grid of values per layer (size checked against the on-use total before it is published).

### Step 2. Elevation pack: slope, contours, threshold (M).
- **Build:** one elevation step reads 3DEP 10 m once and writes (a) slope as a Web Mercator image like the heat surface (decision 88), (b) contour lines at 10, 50 and 100 m as simplified lines by zoom, (c) % of land steeper than 15% and 30% by barrio and municipio.
- **Simple:** "Slope" and "Contours" in Explore › Environment and climate.
- **Power user:** a threshold slider on slope and heat ("show only cells above X"), which repaints the image's colour steps (reclassify).
- Coordinated with colleague PR #161 (SSURGO soils and slope classes): this step is measured slope from elevation, PR #161 is the soil survey's mapped slope class. The legend says which is which.

### Step 3. Watersheds and "What drains here" (M-L).
- **Build:** read USGS WBD (HUC-8, HUC-10, HUC-12) and NHDPlus HR streams and catchments; publish watershed outlines, the main streams by size (stream order replaces a computed flow accumulation), and for each catchment the list of catchments upstream of it.
- **Simple:** "Watersheds" layer in Explore › Environment and climate, with residents and flood-zone share per HUC-12.
- **Power user:** "What drains here": click a point and the land upstream is drawn and summarised (residents, % impervious if land cover is built, % steep). The upstream area becomes a study area.
- No flow model is run: USGS's own network is the source (freshest-sources rule).

### Step 4. Build my region and Count my points (M).
- **Build my region (dissolve):** pick municipios or barrios, or a set such as the Eastern Region; they merge into one study area. Rates are **pooled, not averaged** (the rule used for the Eastern Region).
- **Count my points (spatial join):** load a CSV with latitude and longitude (or a GeoJSON of points). The browser counts them by barrio, municipio or study area and shades the map. **The file is never uploaded**, as with study areas today. Only counts are shown: the points are not drawn when a column suggests homes or people (the sensitive-places rule), and an area with fewer than a set number of points shows "fewer than N".

### Step 5. Download what's inside (S).
- For a study area (or ring, region, watershed): download the summary as CSV, and the features inside of each open layer as GeoJSON or CSV (clip). Withheld places stay withheld; the file carries each source's licence and citation.

### Step 6. Travel time (M), after step 1.
- Walking time along mapped roads from a point (5, 10, 15 minutes), computed in the browser on `roads.bin` with the method of `walknet.py`. The area becomes a study area. It is "along mapped roads", like every walking figure in the observatory; driving and transit times come later, if at all.

### Where the tools live
- **Simple:** the Tools section gets "Area around", "What drains here" and "Download what's inside". One click, defaults set, no settings shown.
- **Power user:** a "GIS tools" drawer in the same section with every setting: distance and ring type, intersect layer, dissolve, join, thresholds, contour interval, travel time. Settings go in the page address so a result can be shared as a link.

## 4. What is not proposed, and why

- **IDW and kriging.** Puerto Rico has few sample points for most variables (rain gauges, wells, air monitors), and a smooth surface looks more certain than it is. Where a surface is needed, a published gridded product is better (freshest-sources rule). Kriging would only be done in Python with its variance map published beside it, for a named question.
- **A cell-by-cell raster calculator in the browser.** Too heavy for the budget and rarely needed by the observatory's readers. The Composite builder already combines layers by area.
- **Flow accumulation computed from elevation.** USGS publishes the stream network; computing our own adds error and maintenance.
- **Uploading visitor files to a server.** All visitor data stays in the browser.

## 5. Terms

Each step's PR adds its terms to `dictionary_src/glossary.json` in English and Spanish with a source: buffer, zonal statistics, dissolve, spatial join, slope, contour line, watershed (HUC), catchment, stream order, travel-time area (isochrone). The wanted-data list gets rows for WBD and NHDPlus HR in step 3.

## 6. Decisions for the project lead (93)

- **(a)** The order: step 1 (Area around + richer summary, first visible), 2 elevation, 3 watersheds, 4 region and points, 5 download, 6 travel time.
- **(b)** The split: three one-click tools for everyone, every setting in a "GIS tools" drawer for power users.
- **(c)** IDW and kriging left out for now.
- **(d)** Step 2 publishes a slope image like the heat surface (decision 88), and coordinates with Zoralis's PR #161 on how the two slopes are labelled.
- **(e)** Count my points keeps visitor files in the browser, shows counts only, and hides counts below a minimum (proposed: fewer than 5).

**Approved by the project lead on 2026-11-09 ("Approve and merge"): (a) to (e) as proposed.** Each step is its own PR, merged only on the project lead's word; step 1 next.
