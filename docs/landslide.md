# Landslide susceptibility by barrio and municipio (2026-10-18, branch `age-landslide`)

The project lead approved this dataset on 2026-10-18. It is general observatory data from an official, current source.

`landslide.py` writes two files:

- `landslide_series.json`: 9 datasets for the 78 municipios and Puerto Rico, in the shape of `conditions_series.json` (one snapshot): the four below and, since the second step of 2026-10-18, the share of the land in each of the five classes (`ls_cls_low_pct` ... `ls_cls_extremely_high_pct`; until then a `classes` block that no page read).
- `landslide_barrio.json`: the same 9 datasets for the 901 barrios, in the shape of `conditions_barrio.json` (`level`, `geo.ids`, `vars[].years`). Each dataset names it (`barrioFile`), so the Economy tab can shade it by barrio.

## The source

Hughes, K.S., and Schulz, W.H., 2020, *Map depicting susceptibility to landslides triggered by intense rainfall, Puerto Rico*: USGS Open-File Report 2020-1022 (https://doi.org/10.3133/ofr20201022), and its GIS layer, a USGS data release (Schulz and Hughes, 2021, https://doi.org/10.5066/P990ZP4C). It is the current official map: no later release replaces it.

- **What it is.** A 5 m raster of the main island. Every cell is ranked by how likely it is to slide during or soon after intense rainfall (a frequency-ratio model of slope, curvature, soil, geology, rainfall, land cover, soil moisture and distance to roads and streams, trained on the 71,431 slope failures of Hurricane María). The cells are sorted into five classes by area: Low (the least susceptible 40% of the island), Moderate (30%), High (20%), Very High (9%) and Extremely High (the top 1%).
- **What it is not.** A probability, a forecast or a site study. It does not show where a slide travels downhill (runout), and deep bedrock slides and earthquake-triggered slides are poorly represented. The authors say it is not a substitute for a site-specific slope-stability investigation by licensed geologists and engineers.
- **Coverage.** The main island only. Vieques, Culebra, Mona and the other small islands are not in the model, so their 15 barrios (and the municipios of Vieques and Culebra) have no value, and the datasets say so (`noValue`).
- **Licence.** USGS data are in the public domain in the United States; the data release states CC0 1.0. Recorded as `usgs_landslide_map` in `dictionary_src/sources.json` (class `open`).

## How it is read

The data release sits on ScienceBase, which answers scripts with a bot check (Cloudflare). The observatory does not get around bot checks (the same rule as HUD User in `docs/conditions.md`). It reads the map the way `environment_series.py` reads the Hurricane María inventory: from the copy the first author keeps on ArcGIS Online at the University of Puerto Rico at Mayagüez.

**A direct USGS file, looked for again on 2026-10-18** (plain requests with a normal browser user agent; nothing done to pass a bot check):

- The DOI 10.5066/P990ZP4C redirects to the ScienceBase item `61087009d34ef8d70565c154`. The item's JSON (`?format=json`), its download link (`/catalog/file/get/<id>`) and the landing page all answer HTTP 403 with Cloudflare's challenge page. No file address can be read, so none can be scripted.
- DataCite's record of the DOI (https://api.datacite.org/dois/10.5066/P990ZP4C, open JSON) names only the ScienceBase page: no file address, size or format. It dates the release 2021 (registered 2021-08-18); this guide said 2022 before and is corrected.
- The report's own folder, https://pubs.usgs.gov/of/2020/1022/, is open to scripts but holds no classified raster: the map sheets (PDF, and georeferenced TIFF pictures of the printed sheet with its shading and labels), KMZ pictures for Google Earth, and `SI_raster_for_SMAP.zip` (276 MB), the susceptibility index **before** its soil-moisture term. The readme says a user must add reclassified NASA SMAP soil moisture and reclassify the sum by area to get the classes, so it is not the published map.
- So the build keeps the UPRM copy. Any other route to the same ScienceBase files (its cloud storage, for example, if that is public) would step around the bot check, so none was tried. A scriptable link would have to come from USGS (ask the Landslide Hazards Program or ScienceBase support) or from the first author.
- What is scriptable is a sign of a new release: the freshness check now reads the DOI record's last update at DataCite as well as the copy's edit date (Refresh, below).

- The copy is a tile service of the 5 m raster (`Susceptibilidad_Derrumbe_PR`, item `ae6770d5b81e4a0e918d58b001948cb3`): 256-pixel PNG tiles with a palette, one flat colour per class (grey Low, yellow Moderate, orange High, red Very High, blue-violet Extremely High; transparent where there is no data). A tile holds no other colour: no blending, no hill shading.
- The build reads the 7,294 tiles of zoom 15 that touch a barrio of the main island (4.78 m a pixel in Web Mercator, about 4.5 m on the ground at 18 degrees north, finer than the 5 m cells; about 65 MB in `cache/landslide/`, 18 minutes the first time) and turns every pixel's colour back into its class. **No raster library:** `rasterio` is not in the project's environment, so `landslide.py` decodes the PNGs itself with `zlib` and `numpy` (palette images, the five row filters). The build stops if a tile holds a colour outside the legend.
- **Why it can be trusted: two checks against the report, at every build** (the build stops if either fails):

| Class | Area in the report (table 5) | Area read from the tiles | Hurricane María slope failures, report (table 5) | Slope failures, read from the tiles |
|---|---|---|---|---|
| Low | 40% | 40.01% | 1.2% | 1.24% |
| Moderate | 30% | 29.99% | 10.0% | 10.21% |
| High | 20% | 20.01% | 29.4% | 29.42% |
| Very High | 9% | 9.00% | 44.6% | 44.43% |
| Extremely High | 1% | 1.00% | 14.9% | 14.69% |
| Total | 8,700.2 km² | 8,738.7 km² (+0.4%) | 71,431 | 71,430 placed |

  The class areas would match for any equal-area classing; the slope failures (the inventory of `environment_series.py`, `cache/environment`) show that the tiles are this model and not an earlier draft. The area read is 0.4% larger because a Web Mercator pixel is measured on a sphere and the edges of the coast are resampled.

## How each figure is made

| Key | What | Puerto Rico (main island) |
|---|---|---|
| `ls_land_high_pct` | Share of the land in the High, Very High or Extremely High class ("highly susceptible") | 30.0% |
| `ls_land_vhigh_pct` | Share of the land in the Very High or Extremely High class | 10.0% |
| `ls_res_high` | 2020 census residents in the High, Very High or Extremely High class (estimate) | 375,779 |
| `ls_res_high_pct` | The same, as a share of all 2020 residents (estimate) | 11.5% |
| `ls_cls_low_pct`, `ls_cls_moderate_pct`, `ls_cls_high_pct`, `ls_cls_very_high_pct`, `ls_cls_extremely_high_pct` | Share of the land in each of the five classes (they add up to 100%) | 40.0, 30.0, 20.0, 9.0, 1.0% |

- **Land.** Each classified pixel counts, with its ground area (a Web Mercator pixel's area shrinks with the square of the cosine of the latitude), in the barrio whose outline (`barrios.geojson`) holds its centre, or in the nearest outline within about 1 km (the generalised coast; 0.17 km² of classified land is farther and left out). A barrio's share is the area of the classes over all its classified land. A municipio's and Puerto Rico's shares come from the areas of their barrios.
- **Residents.** Each 2020 census block with residents (`population_blocks.json`) counts whole in the class of the pixel under its internal point, in the barrio whose outline holds that point; a municipio is the sum of its barrios. The share is over all the 2020 residents of the area (`geo/crosswalk.json`). This is the rule of `exposure.py`: exact to reproduce, but a block that a class edge crosses counts on one side, so a barrio's figure is rough. 1,080 residents live in blocks whose point falls on a pixel the map leaves unclassified (the coast); they count as not in the classes. The datasets carry `tag: "estimate"`.
- **Two bases for Puerto Rico's residents (review of PR #61).** The share (`ls_res_high_pct`, 11.5%) is over the main island's 3,275,833 residents in 2020, because Vieques and Culebra are not in the map and their residents cannot be placed in a class. The Economy tab's "per 1,000 residents" view of the count (`ls_res_high`) divides by all 3,285,874 residents of Puerto Rico, as it does for every dataset, so it reads 114.4. The engine's base was kept so that every per-1,000 figure on the tab shares one denominator; the dataset definitions and dictionary caveats name both bases, and the share is the figure to quote.
- **Barrios with no residents.** Cedro (Guayanilla), Emajagual (Juana Díaz) and Santa Rosa (Utuado) are on the map but had no residents in 2020, so they have no share of residents. `landslide_barrio.json` lists them under the dataset's `noValueWhy` (`[{why: "No residents in 2020", ids}]`), which `core/adapters.js` (levelFile, `flags.why`) and `econ_level.js` show in the tooltip and as their own legend row; "Not mapped" is said only of the 15 barrios of Vieques, Culebra and Isla de Mona (tests in `test_landslide.py` and `core.test.js`).
- **Highest values.** Land: Maricao (79.8%), Jayuya (70.4%) and Las Marías (69.5%); 229 barrios have half or more of their land highly susceptible, 55 have none. Residents: Las Marías (63.9%), Maricao (59.8%) and Naranjito (58.4%); most in number in Naranjito, Utuado and Mayagüez.

## On the map

- **Economy tab.** One new group, *Environment · Landslide susceptibility (USGS)*, with the nine datasets (a snapshot, "2020"). Highest share of land in the Extremely High class: Maricao (14.5%), Utuado (9.2%), Las Marías (6.1%); in the Low class: Cataño (99.8%) and Loíza (99.2%). The area profiles, the chat and the 3D columns get the municipal values (`core/datasets.js`).
- **By barrio.** Settings > Area > barrio, as for `conditions.py`: `econ_level.js` reads `landslide_barrio.json` (19 KB compressed) the first time. The legend says why the 15 barrios of Vieques, Culebra and Mona have no value.
- **No map layer of the raster.** The optional overlay was not added: the map's startup scripts are at 249.0 of 250 KB, and a layer would add its switch, its Spanish and its loader there. The first author's tile service could be added later as a lazily loaded overlay (it is public, no key), but that is a decision for later.

## Refresh

Unit `landslide` (`refresh/sources.json`, `rebuild.yml`, on a runner): `python landslide.py --refresh`. Its source `usgs_landslide_map` is checked every 30 days by two dates: the copy's last edit on ArcGIS Online (2019-11-01 on 2026-10-18) and the last update of the USGS release's DOI record at DataCite (2021-08-18), read with the json check's `per_url` paths (`freshness.py`). A person reviews any rebuild, because a new map moves every figure. A new USGS version shows at DataCite, but the build reads the copy: if USGS publishes and the copy does not follow, ask for a scriptable link (see above). The first run after this change sees a new fingerprint (two dates instead of one) and asks for a review once. `python landslide.py --check` rebuilds both files from the cached tiles with no network.

## Checks

`tests/test_landslide.py`: the PNG reader on tiles made in the test with every row filter, the colour rule (a colour outside the legend and a half-transparent pixel stop the build), pixel areas, the tile range; on the published files: 901 barrios in the crosswalk's order, shares between 0 and 100, the five class datasets that add up to 100 and agree with the high-or-above and very-high-or-above shares, Puerto Rico's class shares within a point of the report's, residents never above a barrio's and adding up to the municipios, no value only on the islands the model leaves out, the two checks against the report, no raster or tile published; and, with the cache, a rebuild that gives the files again.

## Weight

`landslide_series.json` 20.5 KB (4.7 KB compressed; 12.7 KB and 4.5 KB before the five class datasets, whose definitions repeat the method) joins the Economy tab's series files and the area profile's first load; `landslide_barrio.json` 51.8 KB (18.9 KB compressed) is read on first use. See HANDOFF.md for the measured page weights.
