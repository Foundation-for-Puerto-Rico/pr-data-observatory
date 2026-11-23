# Study areas (Phase 3, item 16, C4)

Plan: `docs/proposal-2026-10.md`, section C4 (J row 16). The workspace is the workbench's **Study areas** tab on the 2D map. Its code is `site/js/studyareas.js` and `site/js/core/study.js`. It loads the first time the tab opens, so the map's first load does not carry it.

A study area is a polygon someone brings: a neighbourhood, a corridor, a programme's service area. The observatory adds no study areas of its own.

## Area around a point (GIS tools step 1, 2026-11)

Plan: `docs/gis-tools-proposal-2026-11.md`, step 1 (HANDOFF decision 93). The box sits at the top of the Study areas view. **Tools › Map tools › Area around a point** (and each study-area tool there) opens it in one click; on a phone that button also closes the side panel so the workbench shows.

- **Simple:** choose 400 m, 800 m, 1 km, 1.6 km or 5 km, then **Pick a point on the map** (the next click on the map; Esc cancels) or **Use the centre of the map** (for the keyboard).
- **More settings:** any outer distance from 50 m to 20 km, an inner distance for a **ring** (800 m to 1.6 km, say: the land closest to the point is left out), and a latitude and longitude typed in.
- **The shape.** `Study.ring()` draws a polygon of 128 corners on the flat projection the summary already uses, pushed out slightly so its area equals the circle's (within 0.003% from 400 m to 20 km). A straight-line distance, not along the roads.
- **Where it goes.** Every point of a visit is one more area of a set called "Areas around points" (source "Drawn in this browser (Area around a point)"), saved in IndexedDB like a loaded file, so the summary compares the points side by side, and Export writes them as GeoJSON. "Start a new set of areas around points" begins another. Each area's name gives the distance, the point to 4 decimals (about 11 m) and the municipio it falls in.
- **The pick.** While a point is being picked, the map's click is caught before any layer sees it, so it does not also select a municipio or open a pop-up. The zoom buttons still work, and a drag still moves the map.

## Walking time (GIS tools step 6, 2026-11)

A box in the Study areas view: choose 5, 10, 15 or 20 minutes, then pick a point on the map or use the map's centre. The area within that walk along mapped roads becomes an area of the set "Walking areas", with the full summary (`Core.study.walkArea`).

- **The walk:** on the road graph the map already has (`roads.bin`, OpenStreetMap; js/roads.js, loaded on first use, about 3.3 MB), every road but motorways and their links, in both directions (one-way rules are for vehicles), as `walknet.py` walks it for the observatory's walking figures. The point snaps to the nearest walkable road within 150 m (the straight connector counts), and the walk spreads along the roads (Dijkstra) at **4.8 km/h (80 m a minute)**, a common planning pace for adults; older adults and children walk slower.
- **The area:** each reached stretch of road reaches off the road by up to 100 m, or by what is left of the walk if less, drawn on 25 m cells and kept as rectangles of cells (a MultiPolygon the measures use).
- **What it cannot see:** footpaths, steps, sidewalks and crossings are not on the map, and nothing stops a walk crossing a road a pedestrian could not; so a walk is an estimate, "along mapped roads", like every walking figure of the observatory.
- Checked 2026-11-11: a 15-minute walk from Old San Juan covers 1.10 km² (a 1.2 km circle is 4.52 km²: the islet has few roads out), 2,767 residents and 11 stops, in half a second; a point at sea gets "no walkable road within 150 m". The tests check that no corner of a walk lies beyond the straight-line reach, that a shorter walk covers less and that the area is a valid study area.

## Property parcels (CRIM) (2026-11-11)

A link, not a layer. "Pick a point on the map" or "Use the centre of the map" opens CRIM's Catastro Digital viewer (`https://catastro.crimpr.net/cdprpc/`) in a new tab, centred on the point at zoom level 18, where single parcels show (`Core.study.crimUrl`; points outside Puerto Rico are refused). The observatory reads, copies and draws nothing from the catastro: CRIM's parcel services need a token, and their licence says the parcels may be seen only in CRIM's own viewer and may not be shown through third-party portals without written authorization (`CATASTRO_ASSESSMENT_2026-10-01.md`, checked again 2026-11-11). CRIM shows its own notice when its viewer opens; the visitor accepts it there. `tests/study_tools.test.js` fails if any script calls CRIM's server, portal or proxy. Glossary: `cadastre`, `crim`.

## Build my region and Count my points (GIS tools step 4, 2026-11)

Plan: `docs/gis-tools-proposal-2026-11.md`, step 4 (HANDOFF decision 93). Both boxes are in the Study areas view, under Area around a point and What drains here.

**Build my region (a dissolve).** Choose municipios or barrios from a searchable list, or start from a ready-made region (`data/geo/regions.json`: the Eastern Region and the seven tourism regions), and **Add as a study area**: the parts become one area of the set "My regions" (`Core.study.merge`: a MultiPolygon, the parts kept; barrios and municipios do not overlap, so the area and the counts add up). Its summary works like any study area's: totals of whole municipios are their exact sum ("Sum of the whole municipios inside"), rates and levels the average weighted by residents. **Two or more municipios** also give **Open the regional profile** (`profile.html?ids=72029,72037,...`), the profile the Eastern Region uses: counts summed with their margins, rates pooled from their parts where those are published (⊕), every other value weighted by residents and marked as an estimate (≈). Checked 2026-11-11: the Eastern Region preset gives 15 municipios, 1,418.5 km² and 409,267 residents by block point (the profile: 409,525, the Census total).

**Count my points.** A CSV whose header names a latitude and a longitude column (lat/lon, latitude/longitude, latitud/longitud or y/x; comma, semicolon or tab; quotes allowed; a decimal comma with semicolons or tabs) or a GeoJSON of points, up to 200,000 points and 20 MB (`Core.study.points`). The file is read in this browser, never uploaded and never kept (not in IndexedDB either); **Forget the file** drops it.
- The points are counted by barrio and by municipio (the 15 areas with the most are listed), and in each area of the summary below (a row "Your points"). **Counts of 1 to 4 are shown as "fewer than 5"**, in the table, the summary, the map and the CSV.
- **The points are never drawn.** "Shade the map by count" colours the barrios or municipios in four classes of their counts, grey where a count is under 5.
- Rows with no usable coordinates and points outside Puerto Rico's box are counted and reported, not used.
- Why: a file of points may hold homes or people; the observatory's rule for such places is to count, never draw or name them.

## Download what's inside (GIS tools step 5, 2026-11)

Under the summary table of a set: a dataset, a format (GeoJSON or CSV) and **Download**. For every area of the set the file holds:
- **points inside the area, cut at its edge** (the same point-in-polygon test as the summary's counts): scheduled transit stops, tourism places, the 2020 census blocks (residents at each block's point, and the metres to a scheduled stop), fire and police stations, libraries, historic places, town halls, public housing, tax-credit housing (LIHTC), reservoir gauges and illegal dumping sites;
- **outlines that overlap the area, whole** (not cut: the observatory has no polygon clipping): FEMA flood hazard areas (A and V zones), protected areas, subwatersheds and barrios. A polygon overlaps when one of the area's grid points is inside it or one of its corners is inside the area (`Core.study.overlaps`).

Each row names its **area** and its **source** ("PR Data Observatory, data/<file>; licence and credit in the data dictionary"); a GeoJSON also says whether its features are points cut at the edge or whole outlines. **Withheld places** (homes, care services, holiday rentals) have no point in `places.json`, so they are never in a file. Checked 2026-11-11 on an 800 m circle in San Juan: 13 stops (the summary's 13), 69 tourism places, 85 census blocks, 1 library, 1 flood area and 3 barrios.

The Spanish label "Tax-credit housing (LIHTC)" is held for review (`i18n_src/held_for_review.json`, the rule for text about federal grant programs); the Spanish page shows it in English until Compliance releases it.

## Loading a set of areas

- **The file.** A GeoJSON `FeatureCollection` of `Polygon` or `MultiPolygon` features, in longitude and latitude (WGS 84, EPSG:4326). A single feature or a bare polygon also works.
- **Limits.** Up to 200 areas, 100,000 points and 5 MB. Every point must fall inside Puerto Rico, Vieques, Culebra and Mona.
- **Refused whole.** Any problem refuses the whole file, and the first 50 problems are listed. Problems include a point or a line, coordinates that are not longitude and latitude, a point outside Puerto Rico, a ring with fewer than three corners, a polygon with no area, or a name with an e-mail address or a telephone number.
- **What is kept.** Only each area's name and shape. The name is read from `name`, `nombre`, `NAME`, `NOMBRE`, `label` or `title`, or is "Area N". Every other property in the file is dropped. Open rings are closed, and a repeated name gets "(2)".
- **The set.** It needs a name and a **source** (an agency, a study or a team); the description is optional. None of them may hold an e-mail address or a telephone number.
- **Storage.** The browser keeps the set in IndexedDB (`pr-twin-studyareas`). The file is never uploaded.
- **Export.** Writes the set back as GeoJSON with a `study` member that holds its name, source and description, so a GIS opens it as is. Loading that file with the form empty restores the set as it was.

## What the summary gives

For each area:

| Measure | How | Kind |
|---|---|---|
| Area (km²) | the polygon on a flat projection at its latitude | measured |
| Residents | Census 2020 blocks whose centre (centroid) is inside | counted |
| Residents more than 800 m from a scheduled stop | the same blocks, by the distance the build stored for each block | counted |
| Scheduled transit stops | GTFS stops (ATI and municipal systems) inside | counted |
| Tourism places *(on request)* | Overture places inside | counted |
| % of the land in a FEMA flood hazard area *(on request)* | a grid of about 8,000 points over the area. Only points on land (inside a municipio) count; zones A and V only, not X | measured on a grid |
| % of the land in a protected area *(on request)* | the same grid against PAD-US | measured on a grid |
| Surface temperature, summer mornings and nights (°C) *(on request, second button)* | the mean of the same grid against the 60 m Landsat image and the ECOSTRESS image the map draws (`heat_surface.png`, `night_heat_surface.png`; `Study.raster` reads each pixel's step on the image's scale) | measured on a grid (zonal statistics) |
| Greenness (NDVI) *(on request, second button)* | the barrio medians (`vegetation_barrio.json`), averaged by each barrio's land inside | estimate |
| % of the land highly susceptible to landslides *(on request, second button)* | the barrio shares in the high, very high and extremely high USGS classes (`landslide_barrio.json`), averaged by each barrio's land inside | estimate |

The second button downloads about 2.6 MB: the two heat images, the barrio outlines and the two barrio files. An asterisk marks an area where part of the land has no value (the heat images leave out Mona and Desecheo; the landslide map covers the main island only). Surface temperature is of the ground, not the air.

**Checked against the build (2026-11-09):** the median of the browser's grid over the shape of 21 barrios (every 45th) matched the barrio medians `heat.py` computed from the same cells within 0.27 °C (mean 0.12 °C), less than one step of the image's scale (0.38 °C).

The three measures on request download about 5.5 MB (places, flood zones and protected areas), so they wait for a click.

**Every dataset of the Economy tab** is then estimated for each area, in the latest year or a year chosen. Datasets are published by municipio, so these are **estimates**, and each row names its method:

- **Totals** (counts and dollar totals): each municipio's total times the share of its residents inside the area, added up.
  - Totals measured in km² are shared by land instead of residents.
  - When the area holds whole municipios (99% or more of each inside) and the rest of the area holds at most 0.5% of its residents (or land), the whole municipios count in full and the result is their exact sum, plus the edge slivers shared as usual. The method then reads "Sum of the whole municipios inside".
  - Any other area is shared by residents (or land). A small area keeps its share: a neighbourhood with 0.4% of San Juan's residents gets 0.4% of San Juan's totals. No part of an area is ever dropped.
- **Rates, ratios and levels:** the values of the municipios the area covers, averaged and weighted by the residents of each inside the area. When the area has no residents, they are weighted by land. For a median (median household income, median rent), this average of municipio medians is not the median of the area itself.
- **Missing values:** an asterisk marks an area where some of the municipios it covers have no value. Its tooltip gives the share that has one.
- **Survey datasets** (ACS) say that their margins of error are not carried into the estimate.

**What an estimate assumes:** a municipio is the same throughout. A small area inside one municipio gets that municipio's rate, which may differ from the area's real rate.

**Speed.** The areas are measured one at a time, with "Measuring area k of n" on screen, so the page stays responsive; choosing another set stops the work. In headless Chrome, a set of the 78 municipio boundaries takes about 2 seconds for the basic measures and about 6 seconds more for the measures on request (measured 2026-10-15; the page never stops responding for more than about 0.6 s). A neighbourhood-size area takes a few milliseconds.

**Tables.** The tables show 12 areas side by side, with a picker for the next 12; the CSV holds every area.

**Download CSV** saves the summary: the measures, then every dataset with its year, one column per area, and the method.

## Checks

These tests in `tests/core.test.js` check the reading and the measures:

- **Reading files:**
  - Names and shapes are kept, and other properties are dropped (an e-mail address in a property does not survive).
  - Every kind of bad file is refused whole.
  - An exported file reads back as the same set.
- **Geometry:** area with a hole, point in polygon, and grid points that add up to the area.
- **San Juan's own boundary as an area:**
  - Residents by block centroid are within 0.2% of Census 2020.
  - Totals come back as San Juan's exact values ("whole").
  - Rates come back as San Juan's own rates.
  - The flood share found with the grid index equals testing every flood polygon.
- **A box across municipios:**
  - Totals are shared by residents.
  - Totals of land are shared by land.
  - Counts of people (survey counts, exposure counts) are shared by residents.
  - A weighted average lies between the municipios averaged.

## Not done in item 16

- **Smaller units.** No estimates from barrios or census tracts, even where a dataset has them. Estimates use municipios only.
- **Housing units by block.** The published blocks carry residents only.
- **Margins of error.** Not propagated into the estimates.
- **Drawing on the map.** An area can't be drawn by hand; it comes from a file, from a point (Area around a point, What drains here, Walking time), or from municipios and barrios (Build my region). Rings around a line or an area, and travel time along roads, are later steps of the GIS tools plan.
