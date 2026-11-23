# Night surface heat by barrio and municipio (`ecostress.py`)

Step 2 of the terrain and climate plan (`docs/terrain-climate-proposal-2026-11.md`, HANDOFF decision 80, approved 2026-11-04), beside the morning surface heat (`docs/heat.md`) and the vegetation (`docs/vegetation.md`). Built on 2026-11-04 on branch `data/night-heat-ecostress`.

`ecostress.py` writes two files:

- `night_heat_series.json`: 5 datasets for the 78 municipios and Puerto Rico.
- `night_heat_barrio.json`: the same 5 datasets for the 901 barrios.

They are shaded on the map's Economy tab, in the group "Environment · Night surface heat (ECOSTRESS)", by municipio or by barrio. They use the same summers and the same 60 m grid as the morning heat figures.

## Why night heat

A hot day is easier to bear when the night cools down; health harm from heat rises when it does not, because bodies cannot recover. Pavement, roofs and walls store heat during the day and give it back at night, so built land cools least. Landsat (step 1) only passes in mid-morning. **ECOSTRESS**, a NASA thermal instrument on the International Space Station, passes at a different hour each time, night included.

## What it measures, and what it does not

**Land surface temperature at night**: the radiative temperature of the ground, roofs, pavement and canopy, **not the air temperature**. At night the two are closer than in the day, but built surfaces still stay warmer than the air above fields and forest.

- **Clear summer nights** (June to September 2024–2026), passes between **21:00 and 06:00** Atlantic Standard Time that NASA also flags as night.
- **The hour varies.** Each cell's value mixes passes from different hours (below); a place seen mostly before midnight reads a little warmer than one seen mostly before dawn.
- **The sea keeps the coast warm.** The sea around Puerto Rico stays warm through summer nights, so land near the coast cools less. A warm coastal barrio is not only urban heat: compare coastal places with each other.
- **Elevation cools the land.** Compare the Cordillera with itself.

## The figures (build of 2026-11-04)

| Key | What | Puerto Rico |
|---|---|---|
| `night_lst_med` | Median land surface temperature, summer nights (°C) | 24.0 |
| `night_lst_p90` | 90th percentile: the warmest tenth of the land starts here (°C) | 26.2 |
| `night_hot_land_pct` | Share of land above Puerto Rico's night 90th percentile (%) | 10.0, by construction |
| `night_res_hot` | 2020 residents on that land (estimate) | 847,717 |
| `night_res_hot_pct` | The same, as a share of residents (estimate, %) | 25.8 |

- **Night is 9.4 °C cooler than the morning** across Puerto Rico (24.0 against 33.4 °C in `heat_series.json`).
- **Warmest municipios at night:** Culebra (26.5 °C), San Juan (26.4) and Loíza (26.4): the coast and the city. The warmest tenth of the land is warmest in Mayagüez (28.0), Culebra (27.5) and San Juan (27.4).
- **Coolest:** the Cordillera. Adjuntas (19.8 °C), Jayuya (19.9) and Orocovis (20.0).
- **Residents:** 25.8% of residents live on the warmest tenth of the land at night. The highest shares are Loíza (82.6%), Culebra (77.4%) and San Juan (76.0%).
- **Morning and night mostly agree, but the order changes.** Across the municipios the rank correlation of the night and morning medians is 0.79. Santa Isabel, the hottest in the morning, is 8th of 78 at night (25.8 °C); San Juan is 2nd at night and Culebra 1st.

## How it is made

**Granules.** Every ECOSTRESS Tiled Land Surface Temperature and Emissivity granule, version 2 (ECO_L2T_LSTE.002, 70 m), over Puerto Rico from June to September of the three summers, that NASA flags as night and that was taken between 21:00 and 05:59 local time.
- This build found 295 granules (2024: 96, 2025: 91, 2026: 108) from 47 passes of the space station; 39 passes had at least one clear cell.
- By local hour: 21h 31, 22h 29, 23h 36, 00h 22, 01h 45, 02h 36, 03h 30, 04h 35, 05h 31 (`notes.window.granules_by_local_hour`).
- They come from NASA's open catalogue (CMR) and are read from the LP DAAC's cloud store.

**The login.** The files need a NASA Earthdata login. The build uses FPR's Earthdata token, the one night lights uses (decisions 75 and 80; `docs/nightlights-setup.md`):
- The token is sent only to NASA's hosts (`NASA_HOSTS`). The LP DAAC answers with a short-lived signed address of the file, read without the token.
- The build runs in GitHub Actions (`.github/workflows/ecostress.yml`, on a tag `ecostress-run-*`), where the token is a secret, and keeps the files and the per-granule values with the run. A person copies the files into a pull request. A rebuild from those values (`--check`, `--from-cache`) needs no token.
- NASA answers 429 or 5xx now and then; the build waits and asks again (six times), and the workflow saves what it has read even when a run stops.

**Reading.** `raster.py` reads four layers of each granule at 70 m: the temperature (`LST`, kelvin, empty where not produced), the quality flags (`QC`), the cloud mask and the water mask. The tiles carry their map projection as text, not as an EPSG code, so the build gives it from the tile's name (19QHA is UTM zone 19, EPSG:32619; `raster.COG(..., epsg=)`). The layers must share one grid, or the build stops.

**Grid.** `heat.py`'s 60 m grid in UTM zone 20: 2,485,382 cells. Each cell takes the 70 m pixel under its centre.

**Clear observations.** An observation counts when the temperature is set, QC bits 0–1 say best (0) or nominal (1) quality, the cloud mask is 0, the water mask is 0, and the value is between 250 and 350 K. There are 33.7 million clear observations.

**One view per pass.** Where two tiles of the same pass overlap, a cell keeps one value.

**Composite.** Each cell's value is the **median** of its clear night views, exact. The typical cell has 13 views; a cell needs at least 3. ECOSTRESS's cloud mask misses some thin cloud at night, which reads cold; the median of many nights limits it.

**Cache.** For each granule, the cells it saw clear and their temperature (`cache/ecostress/values/`, 47 MB for the 295 granules). The folder's name holds the reading rule (`RULE`).

**Areas, warm land and residents** follow `heat.py`: a cell belongs to the barrio that holds its centre; municipios and Puerto Rico pool their barrios' cells; warm land is the cells above Puerto Rico's night 90th percentile (26.2 °C); residents count by `heat.block_cells`. 4,515 residents live in blocks whose point falls on no cell with a value and count as not on warm land.

**Coverage.** 99.5% of the cells have a value. Every municipio has at least 94.9% (Hormigueros, the lowest; `notes.municipios_cover_pct`).

## Checks at every build

The build stops when any of these fails:

- Puerto Rico's night median is between 15 and 35 °C (24.0).
- It is below Puerto Rico's morning median in `heat_series.json` (33.4).
- San Juan's night median is above Puerto Rico's (26.4).
- Jayuya's (19.9) and Adjuntas's (19.8) are below it.
- At least 90% of the cells have a value (99.5%).
- At least 150 night granules are found (295).

`tests/test_ecostress.py` checks:

- **The granule reader, on small ECOSTRESS-like tiles written in the test:** each mask, each QC grade, kelvin to °C, impossible values, cells outside a tile, and layers on different grids.
- **The cache:** it gives back what was read and answers offline.
- **The token** goes only to NASA's hosts, and the signed address is read without it.
- **The night window** and a tile's UTM zone.
- **The composite:** one view per pass and the median.
- **The published files**, when present: shapes, ranges, residents that add up, and the checks above.

## Refresh

- **Unit `night_heat`** in `refresh/sources.json` runs `python ecostress.py --refresh`; `rebuild.yml` passes the Earthdata token to this unit and to night lights only.
- **When it changes.** The source check (`nasa_ecostress_lste`, calendar rule `summer`) turns each October. Rebuild heat first: the night build checks itself against the morning file.
- **Review.** A person reads the rebuild (review `human`).
- **The token** expires (FPR's, on 2027-01-02): see `docs/nightlights-setup.md`.

## Licence

NASA's data use guidance: data from NASA-led missions carry no restriction on use (CC0), and users are strongly urged to cite them. Citation: Hook, S., Hulley, G. (2022). ECOSTRESS Tiled Land Surface Temperature and Emissivity Instantaneous L2 Global 70 m V002. NASA EOSDIS Land Processes DAAC. https://doi.org/10.5067/ECOSTRESS/ECO_L2T_LSTE.002. The source card is `nasa_ecostress_lste`. No image is published, only figures by area.

## The night surface on the map (HANDOFF decision 88)

The build also writes `night_heat_surface.png` and `night_heat_surface.json` with `surface_image.py`: every 60 m cell of the night composite as one Web Mercator picture on a blue-grey-red scale around Puerto Rico's night median, like `heat.py`'s morning image (docs/heat.md, "The surface on the map"). The maps show it when the surface heat layer's legend is switched to Night. `--check` compares it with what the cache gives; `--from-cache` writes it with no network and no token.
