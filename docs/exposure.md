# The exposure series: residents and homes inside hazards and protected land, and near transit

Built 2026-10-06 (plan item 5). For every municipio, barrio and census tract, the series says how many **residents** and how many **housing units** are inside a FEMA flood hazard area, inside the area flooded by 1 to 10 feet of sea level rise, inside the area a hurricane's storm surge may flood (added 2026-11-17, section 9), inside a protected area, or within 400 m of a transit stop.
The code is `exposure.py`, the tests are `tests/test_exposure.py`, and the evidence for the method is in `docs/analysis/exposure-2026-10/`.

**The figures are computed, not measured.** Each 2020 Census block is given to a layer by its one internal point, and all of its residents and housing units are counted in or out. Say so wherever a figure is shown: "computed from 2020 Census blocks counted by their internal point". The counts of a whole municipio are close; the counts of a single barrio or tract are rough (section 6).

## 1. Results for the island (2026-10-06)

| What | Residents | Share of residents | Housing units | Share of housing units |
|---|---|---|---|---|
| In a FEMA 1% annual chance flood area (`flood_sfha`) | 316,309 | 9.6% | 172,281 | 10.8% |
| In a 1% or a 0.2% annual chance flood area (`flood_any`) | 454,706 | 13.8% | 243,227 | 15.2% |
| In the area flooded by 1 ft of sea level rise (`slr_1ft`) | 11,005 | 0.3% | 7,143 | 0.4% |
| ... by 3 ft (`slr_3ft`) | 25,302 | 0.8% | 17,018 | 1.1% |
| ... by 10 ft (`slr_10ft`) | 213,681 | 6.5% | 128,658 | 8.1% |
| In a low-lying area that may flood at 7 ft, not connected to the ocean (`low_7ft`, the largest of the ten heights) | 7,148 | 0.2% | 4,109 | 0.3% |
| In the area flooded by storm surge in a category 1 hurricane (`surge_cat1`, added 2026-11-17) | 15,961 | 0.5% | 10,129 | 0.6% |
| ... category 3 (`surge_cat3`, added 2026-11-17) | 46,689 | 1.4% | 30,751 | 1.9% |
| ... category 5 (`surge_cat5`, added 2026-11-17) | 120,934 | 3.7% | 73,273 | 4.6% |
| ... under 3 ft of water or more, category 3 (`surge_deep_cat3`) | 14,025 | 0.4% | 8,888 | 0.6% |
| ... under 3 ft of water or more, category 5 (`surge_deep_cat5`) | 50,353 | 1.5% | 32,683 | 2.0% |
| Inside a protected area (`protected`) | 58,220 | 1.8% | 30,778 | 1.9% |
| Inside a strictly protected area, GAP status 1 or 2 (`protected_strict`) | 30,716 | 0.9% | 16,046 | 1.0% |
| Within 400 m of any mapped stop (`stop_any`) | 993,493 | 30.2% | 526,249 | 32.9% |
| ... of a stop with a timetable on file (`stop_sched`) | 925,020 | 28.2% | 487,061 | 30.5% |
| ... of a stop with a current timetable (`stop_cur`) | 729,507 | 22.2% | 388,902 | 24.3% |
| ... of a frequent stop, 20 or more weekday departures (`stop_freq`) | 437,851 | 13.3% | 244,288 | 15.3% |
| ... of a stop with Saturday service (`stop_sat`) | 536,815 | 16.3% | 292,249 | 18.3% |
| ... of a stop with Sunday service (`stop_sun`) | 46,014 | 1.4% | 28,623 | 1.8% |
| Within a 400 m walk along mapped roads of a stop with a current timetable (`walk_cur`) | 403,421 | 12.3% | 221,270 | 13.8% |
| ... of a frequent stop (`walk_freq`) | 223,057 | 6.8% | 129,192 | 8.1% |

The island has 3,285,874 residents and 1,598,159 housing units (2020 Census). The groups overlap (a resident can be in a flood area and near a stop), so the rows cannot be added. Weekend counts are low mainly because few timetables list weekend trips (3 of the 18 operators whose timetable had not ended list Saturday departures; 1 lists Sunday departures), not because there is no weekend service.
"Exposed" means "lives where the layer applies". It does not say that a home would be damaged, and it is not a forecast.

## 2. What was built

| File | What it holds | Size (raw, compressed) | Loaded by |
|---|---|---|---|
| `site/data/exposure_municipio.json` | 78 municipios, 42 families (30 at first, 2 walking ones on 2026-10-16, 10 storm surge ones on 2026-11-17), residents and housing units for each, and each area's own totals | 32 KB, 9.2 KB (2026-11-17) | no page yet |
| `site/data/exposure_barrio.json` | the same for 901 barrios | 194 KB, 28.7 KB (2026-11-17) | no page yet |
| `site/data/exposure_tract.json` | the same for 981 census tracts | 221 KB, 34.7 KB (2026-11-17) | no page yet |
| `cache/slr/` (build only, not published) | NOAA's File Geodatabase of sea level rise extents, 1 to 10 ft | 23 MB | `exposure.py`, once |
| `cache/surge/` (build only, not published) | NOAA NHC's storm surge maps for Puerto Rico, five GeoTIFFs (2026-11-17) | 7.3 MB zipped | `exposure.py`, once |
| `docs/analysis/exposure-2026-10/` | the check of whole-block counting (section 5), its script and its results | 37 KB | nothing |

The three files together are 343 KB raw and **58.6 KB compressed** (the plan allowed 0.1 to 0.3 MB). Nothing on the first load of any page changed: no page reads them yet. The layer engine (plan item 6) will be the first reader. If a page loaded all three, that is about 0.3 s on Slow 4G and 1.2 s on Slow 3G (estimated from the size, not measured).

## 3. What is in a file

```
{"version": 1, "built": "2026-10-06", "as_of": "2026-10-06", "level": "municipio",
 "basis": {"en": "Computed, not measured: ...", "es": "Calculado, no medido: ..."},
 "inputs": {"blocks": "...", "flood": "...", "slr": "...", "protected": "...", "transit": "..."},
 "measures": {"pop": {"en": "Residents (2020 Census)", "es": "..."}, "hu": {"en": "Housing units (2020 Census)", "es": "..."}},
 "groups": {"flood": {"en": "...", "es": "..."}, ...},
 "geo": {"level": "municipio", "ids": ["72001", "72003", ...]},       # the crosswalk's ids, in the crosswalk's order
 "total": {"pop": [...], "hu": [...]},                                 # each area's own residents and housing units
 "vars": {"flood_sfha": {"label": {"en": "...", "es": "..."}, "group": "flood", "kind": "polygon", "pop": [...], "hu": [...]}, ...}}
```

- Every array has one value per id in `geo.ids`, in the same order. Counts are whole numbers between 0 and the area's total.
- `as_of` is the date a transit timetable is judged "current" on. `built` is the date of the last full build. Both are dates of the build, not of the data.
- A **share** is a count divided by the matching total, worked out where it is shown. The files hold counts and totals, never shares, so any group of areas gets an exact share: add the counts, add the totals, divide. Do not average shares. An area with a total of zero has no share (5 barrios and 48 tracts have no residents).
- **Counts add up exactly between levels:** the barrio rows add up to the municipio rows, the tract rows add up to the municipio rows, and the municipio rows add up to the island. `python exposure.py --check` verifies it for every family.
- Keep ids as text (see `docs/geography.md`).

```python
import json
d = json.load(open("site/data/exposure_municipio.json", encoding="utf-8"))
i = d["geo"]["ids"].index("72127")                                   # San Juan
d["vars"]["flood_sfha"]["pop"][i] / d["total"]["pop"][i]            # 0.128: 43,841 of 342,259 residents
```

```js
const d = await (await fetch('data/exposure_municipio.json')).json();
const i = d.geo.ids.indexOf('72127');
const share = d.vars.slr_10ft.pop[i] / d.total.pop[i];              // 0.151 for San Juan
```

### The families (30 at first, 42 since 2026-11-17)

| Keys | A block is counted when its internal point is | Layer | Updated |
|---|---|---|---|
| `flood_sfha` | inside a Special Flood Hazard Area: the 1% annual chance (100-year) flood area, zones A, AE, AH, AO, A99, V and VE | FEMA National Flood Hazard Layer, `flood.geojson` | full build |
| `flood_any` | inside that area or inside the 0.2% annual chance (500-year) flood area | same | full build |
| `slr_1ft` to `slr_10ft` | inside NOAA's inundation polygon for that many feet of sea level rise above mean higher high water, in water connected to the ocean. Each height includes the lower ones | NOAA Sea Level Rise Viewer polygons (2017 data) | full build |
| `low_1ft` to `low_10ft` | inside a low-lying area at that height that NOAA says may flood but does not connect to the ocean. Not part of `slr_*`: no block is in both at the same height. It leaves this set when a higher water level connects it | same | full build |
| `surge_cat1` to `surge_cat5` | on a cell of NOAA's storm surge map for a category 1 to 5 hurricane that has any water (near worst case, high tide). The categories are not strictly nested (section 9) | NOAA NHC SLOSH MOM maps (2018), read with `raster.py` | full build, or `--surge` |
| `surge_deep_cat1` to `surge_deep_cat5` | the same, with 3 ft of water or more | same | full build, or `--surge` |
| `protected` | inside a USGS PAD-US protected area, except a proclamation boundary (which outlines whole islands or refuges, not managed land) | PAD-US 4.1, `protected.geojson` | full build |
| `protected_strict` | inside such an area with GAP status 1 or 2 (strict nature reserve, or managed for biodiversity) | same | full build |
| `stop_any` | within 400 m, in a straight line, of any mapped stop, station or terminal (ATI, municipal GTFS, OpenStreetMap) | `transport.json` | nightly |
| `stop_sched` | within 400 m of a stop with a timetable on file (expired timetables included) | same | nightly |
| `stop_cur` | within 400 m of a stop whose operator's timetable has not ended on `as_of` | `transport.json`, `operators.json` | nightly |
| `stop_freq` | within 400 m of a current stop with 20 or more weekday departures | same | nightly |
| `stop_sat`, `stop_sun` | within 400 m of a current stop with Saturday or Sunday service | same | nightly |
| `walk_cur`, `walk_freq` | within a 400 m walk along mapped roads (walknet.py, `roads.bin`, no motorways or footpaths) of a current stop, and of a frequent one; a block with no walkable road within 150 m keeps the straight-line test (2026-10-16) | same, and `roads.bin` | nightly |

Each set lies inside the one that holds it, for every block (checked at every build): `flood_sfha` in `flood_any`, `protected_strict` in `protected`, `slr_n` in `slr_n+1`, `stop_cur` in `stop_sched` in `stop_any`, and `stop_freq`, `stop_sat` and `stop_sun` in `stop_cur`; `walk_cur` in `stop_cur`, and `walk_freq` in `walk_cur` and in `stop_freq`.

## 4. How the counts are made

1. **The blocks.** The 2020 Census has 41,987 blocks in Puerto Rico, 36,570 of them with residents (`network.load_block_table`; see `docs/geography.md`, section 7). Each has 2020 residents, housing units and an internal point: the point the Census Bureau guarantees lies inside the block. The residents are noise-injected by the Census Bureau for privacy; the housing units are exact.
2. **In a layer.** A block is in a polygon layer when its internal point is inside any polygon of the layer (a point exactly on an edge counts as outside). The test is `exposure.points_in_polygons`: a point index queried with each polygon's bounding box, then one vectorized test per polygon. On this computer all 24 polygon layers (the two flood sets, 20 sea level rise layers and the two protected sets) take about 25 s in all, including reading NOAA's file.
3. **Near transit.** A block is near a stop when its internal point, rounded to 4 decimals (about 11 m), is within 400 m of the stop, by the same flat-earth distance `access.py` uses for tourism places. The rounding is what the Transit tab's coverage has always used, so the municipal figures agree with it.
4. **Adding up.** The residents and housing units of each block go to the municipio (the first 5 digits of the block id), the tract (the first 11 digits) and the barrio (the barrio polygon that holds the block's internal point, `geo.block_barrios`). The 38 offshore county subdivisions that are not barrios hold no residents and no housing units.
5. **Writing.** `exposure.build` writes nothing unless every area's residents and housing units equal the crosswalk's (so the blocks are the ones the crosswalk was built from) and every set lies inside its superset.

### The layers

- **Flood.** FEMA's layer as published in `flood.geojson`, whose outlines are simplified by about 5 m. A polygon is the 1% area when `SFHA_TF` is `T`, and the 0.2% area when its subtype says so. Unshaded zone X (minimal hazard), open water and unmapped areas are left out, exactly as for the tourism places. Florida (72054) is mapped entirely as minimal hazard, so its counts are zero: a result, not a gap. Counting from FEMA's full-resolution outlines would change the island count of residents in the 1% area by 0.3% (317,290 instead of 316,309).
- **Sea level rise.** The polygon version of the data behind the NOAA tiles the maps draw: `PR_slr_{n}ft` and `PR_low_{n}ft` in NOAA's File Geodatabase (`PR_slr_data_dist.zip`, 23 MB, file dated 2023-09-27, data from 2017). NOAA's method is a modified bathtub that follows tides and hydrological connectivity. The observatory keeps only counts, not the polygons. `exposure.py` reads them with GDAL's faster ring handling (`OGR_ORGANIZE_POLYGONS=ONLY_CCW`, the Esri convention); the result was identical to GDAL's default on three layers (see section 5).
- **Protected land.** PAD-US as in `protected.geojson` (665 units), with the same rules as the place flags: a proclamation boundary does not count; strict means GAP status 1 or 2.
- **Transit.** The six classes are `access.py`'s, on block points instead of tourism places. "Current" means the operator's feed ends on or after `as_of`. The count falls when a feed expires and rises when one is renewed, so a figure always needs its `as_of` date.

## 5. How it was checked

| Check | Result |
|---|---|
| The blocks add up to the crosswalk | exactly, for all 78 municipios, 901 barrios and 981 tracts; the build writes nothing otherwise |
| Each set lies inside its superset | for every block (all 16 pairs) |
| The three files agree | for 30 families and both measures, barrio and tract rows add up to the municipio rows |
| Transit against the Transit tab | `stop_cur` equals the tab's residents near a current stop (`pop_served_active_pct`) in all 78 municipios to the decimal shown (largest difference 0.046 points); `stop_sched` is within 0.5% of a municipio's residents of `pop_served_400m` (287 residents in Vega Baja, the largest) and 0.02% on the island, because the tab measures to the stop nearest in degrees and drops the fraction of a meter |
| Simplified flood outlines | 0.3% fewer residents in the 1% area than with FEMA's full-resolution outlines |
| Faster reading of NOAA's polygons | the same blocks as GDAL's default on three layers: inundation at 3 ft (1,392 blocks) and at 10 ft (3,936 blocks) and low-lying areas at 3 ft (68 blocks) |
| Connected and low-lying areas | no block is in both at any of the ten heights, and none that is low-lying at a height was flooded at a lower one; only 47 to 72 blocks are in low-lying areas at any height |
| The nightly step | changes nothing for today's date; with no feed renewed, `stop_cur` falls from 22.2% to 18.6% of residents on 2027-02-02 (9 of the 18 current feeds end by 2027-01-31) |
| Tests | 37 in `tests/test_exposure.py`: every rule on a seven-block invented island (including the whole build and the nightly step), the damage the checker must name, and the real files (totals, the figures the dictionary quotes, the tie-out with the Transit tab). `PRDT_SLOW=1` adds a full rebuild from the real inputs |

### Whole-block counting against area weighting

A block that a layer's edge cuts is counted whole in or out. `docs/analysis/exposure-2026-10/block_edge_bounds.py` samples every block outline (2,456,925 points in 36,611 blocks) and makes two comparisons (results in `block_edge_bounds.json`, aggregates only).

1. **Bounds that assume nothing.** The true count lies between the residents of blocks wholly inside the layer and the residents of every block the layer touches. For the 1% flood area that is 5.1% to 24.1% of the island's residents, against the 9.6% counted: wide, because rivers and coasts cut through many blocks. The internal-point count lies between the bounds in every one of the 78 municipios, 896 barrios and 933 tracts that have residents, for every layer tested.
2. **Residents spread evenly over each block's area**, on the 98.9% of residents who live in blocks with no water (outline area within 3% of the Census land area; water would need a land mask that the observatory does not have):

| Layer (residents) | Island, internal point | Island, by area | Municipio: middle and largest difference | Barrio or tract: 9 in 10 differ by less than | Largest barrio or tract difference |
|---|---|---|---|---|---|
| 1% flood area | 9.5% | 10.5% | 1.0 and 7.1 points | 6.2 points | 45 points |
| 1% or 0.2% flood area | 13.6% | 14.6% | 1.1 and 6.8 points | 6.5 points | 41 points |
| Sea level rise 1 ft | 0.3% | 0.2% | 0.0 and 1.4 points | 0.5 points | 43 points |
| Sea level rise 3 ft | 0.7% | 0.8% | 0.1 and 3.8 points | 1.2 points | 74 points |
| Sea level rise 10 ft | 6.3% | 6.6% | 0.1 and 11.2 points | 4.4 points | 55 points |
| Protected area | 1.7% | 1.5% | 0.3 and 2.7 points | 3.3 points | 39 points |
| Strictly protected area | 0.9% | 0.8% | 0.2 and 3.0 points | 1.9 points | 66 points |

"Points" are percentage points of the area's own residents. Reading: for the island and for most municipios, the two ways of counting agree to about a point. For a barrio or a tract, one in ten differs by several points and a few by a great deal. The internal-point count is lower than the area-weighted count for the flood areas (by about 1 point of the island's residents) and for sea level rise at 3 and 10 ft, and higher for protected areas and at 1 ft. It was not changed: the method is the one the plan names, it is fast and exact to reproduce, and it is the one the Transit tab already uses.

## 6. Reading the numbers, and what they do not say

1. **Computed, not measured.** No one counted the people inside the polygons. The method gives each block to a layer by one point.
2. **Small areas are rough.** Use the municipio for a statement about "how many". For a barrio or tract, show the count beside the total and say it is approximate. A zero can mean that no block's internal point is inside the layer, not that no home is near it: 35 municipios show no exposure at 10 ft, most of them inland, and a few coastal municipios can still have homes in blocks that the layer only touches.
3. **2020 weights.** The residents and housing units are the 2020 Census counts, not today's, while the layers are today's maps (FEMA's effective maps differ by community; NOAA's data are from 2017). The Census Bureau adds noise to resident counts of small areas; housing units are exact at block level.
4. **Hazard as mapped.** FEMA's maps show the mapped hazard at a block's point, not a building's elevation, mitigation or insurance. NOAA calls its sea level rise data a screening-level tool: no storm surge, rain, groundwater, erosion, subsidence or future construction, and not for navigation, permitting or legal purposes. Low-lying areas "may flood" and are shown apart for that reason.
5. **The groups overlap.** Do not add flood, sea level rise, protected land and transit counts. The files cannot answer a joint question such as "residents in a flood area with no stop within 400 m": that needs counts of blocks in two layers at once (section 10).
6. **Transit is a schedule.** Straight-line, schedule-based: no real-time service, hours, fares, stairs, traffic or safety of the walk; públicos, taxis and ride-hailing are in no timetable. An expired timetable means the timetable on file no longer covers the date, not that service has stopped.
7. **Housing units are not households.** A housing unit is a house, an apartment, a mobile home or a room meant as separate living quarters. People in group quarters (a dormitory, a nursing home) are residents but not in housing units: 53 blocks hold 6,503 residents and no housing units.
8. **No advice.** These figures describe exposure to mapped layers. They are not an assessment of risk to any person or property, and nothing here is legal, insurance or financial advice. Content for federal grant work still goes through Finance and Compliance before it is shared outside FPR.

## 7. The nightly refresh

`refresh_network.py` calls `exposure.apply_transit` after the transit files and `access.apply_files`. It recomputes only the six transit families from the published stops and `operators.json`, for today's date, and writes a file only when a value changed (a night with no change writes nothing, not even the dates). If the blocks no longer match the files (a new Census table or crosswalk) it writes nothing and says to run `python exposure.py`. Any failure is printed and never stops the transit refresh. The job's cache now holds `cache/geo` as well as `cache/network` (the block-to-barrio table is built once, then kept). The nightly environment needs nothing new: `exposure.py` imports `numpy`, `shapely` and `requests`, which `requirements-refresh.txt` has; `pyogrio` is read only by the full build.

The job runs on `main`, so this starts after the branch is merged.

## 8. Building and checking

```
python exposure.py                      # full build: downloads NOAA's polygons once into cache/slr, writes the three files
python exposure.py --transit            # the nightly step by hand (only the transit families, for today; add --as-of YYYY-MM-DD to judge "current" on another date, which rewrites the files)
python -c "import exposure, datetime; exposure.apply_transit(as_of=datetime.date(2027, 2, 2), write=False)"   # what the nightly step would do on another date (writes nothing)
python exposure.py --check              # check the published files against the crosswalk and each other (no network)
python exposure.py --refresh            # download the source layers again
python -m unittest discover -s tests    # includes tests/test_exposure.py (PRDT_SLOW=1 adds a full rebuild, about 40 s)
python docs/analysis/exposure-2026-10/block_edge_bounds.py   # section 5; downloads the block outlines once (about 40 MB)
```

`build.py` runs `exposure.build` after the crosswalk and before the contract check. It needs `pyogrio` (in `requirements.txt`). The dictionary entries (`dictionary_src/entries/exposure.json`) quote island figures; a test fails when a rebuild changes one, and the figures in the text must then be updated.

## 9. Adding a layer (storm surge, schools, hospitals, shelters)

The code takes a new layer without changing the existing files' numbers:

1. **A polygon layer** (a landslide or liquefaction map; a raster read at the block point, as the storm surge maps are, follows the same steps with a function like `surge_flags`): add its families to `_families()` (key, group, kind `polygon`, English and Spanish labels, sources), its group label to `GROUPS`, its input line to `INPUTS`, the polygons to `hazard_flags` (read the file, call `points_in_polygons`), and the nested pairs to `SUBSETS`. Run `python exposure.py`: the new families appear in all three files.
2. **A point layer within a distance** (residents within 800 m of a school, a hospital or a shelter): write a function like `transit_flags` that returns a boolean array over the blocks, call it in `build`, and add its families with a new kind (for example `points`). The full build writes them; the nightly step leaves them as they are, because it recomputes only the `stops` families.
3. **Documentation.** Every new family needs dictionary entries with domain tags (`dictionary_src/entries/exposure.json`), and the group's description in `dictionary_src/groups.json`. Run `python dictionary.py --coverage`, `python registry.py` and the tests.
4. **Data.** The layers this needs are on the wish list (`site/data/wanted.json`): `schools`, `cms-facilities` and `osm-health` (hospitals), `shelters`. Storm surge was added on 2026-11-17 (below).

### Storm surge (added 2026-11-17, decision 107, step 5, third part)

- **Source.** NOAA National Hurricane Center, SLOSH Maximum of MEOWs (MOM) maps for Puerto Rico, category 1 to 5 hurricanes at high tide: `PR_SLOSH_MOM_Inundation.zip`, 7.3 MB, dated 30 November 2018, public domain. Five GeoTIFFs of about 10 m cells (NAD83), each cell coded by the depth of water above ground in 1 ft bands (1 = under 1 ft, 2 = 1 to 2 ft, and so on; 255 = no data).
- **No polygons, no raster library.** The wish list planned to turn the rasters into polygons. That is not needed: the files are tiled, LZW-compressed and 8-bit, which the project's own reader (`raster.py`) reads, so `exposure.py` reads the one cell under each block's internal point (`surge_bins`). This is the same whole-block rule as the polygon layers.
- **Families.** `surge_cat1` to `surge_cat5`: any water. `surge_deep_cat1` to `surge_deep_cat5`: 3 ft or more (band 4 and up; NHC's own map starts its second color at 3 ft). Group `surge`, kind `raster`.
- **How it was added.** `python exposure.py --surge` adds or recomputes only these ten families in the three published files and leaves every other family as it was, so the transit and sea level rise counts did not move. The full build (`python exposure.py`) computes them with the rest.
- **Checks.** The area under water per category, counted from the cells, is 99, 159, 223, 288 and 367 km²; the cell counts equal the histogram NOAA ships in each file (for category 1, 1,049,909 cells). Every resident counted at category 1 is also inside FEMA's 1% annual chance flood area, which includes coastal surge; at category 3, 92.5%; at category 5, 63.0% (84.8% inside the 1% or 0.2% area).
- **The categories are not strictly nested.** Each map is the highest water of its own set of model storms. Five block points in San Juan (721270071002000, 721270070042006, 721270043062001, 721270070042010, 721270070042021; 247 residents and 124 housing units) are wet at category 4 and dry at category 5. So `SUBSETS` holds only "3 ft or more is inside any depth" for each category, not category 4 inside category 5.
- **Limits.** A near worst case, not one storm and not a forecast. NOAA says the maps are for awareness at a city or community level, not for a parcel; they leave out erosion, subsidence and future construction, and show nothing outside the SLOSH model's grids. They are not evacuation zones.

## 10. Not done in item 5, on purpose

- **No page shows the series.** The brief said "build scripts; no UI". The layer engine (plan item 6) reads the files.
- **Schools, hospitals and shelters** need data that is not harvested yet (section 9). Storm surge was added on 2026-11-17 (section 9).
- **The storm surge map is not drawn.** The counts are in the files and on the Analysis tab; a map layer of the surge area itself is a later step.
- **No joint counts.** A cross-tabulation (for example residents in a flood area with no current stop within 400 m) would need a few extra stored counts, chosen with the people who will use them.
- **No region or block-group level.** The plan names municipio, barrio and tract. The crosswalk has the tourism regions and 2,555 block groups; adding a level needs a branch in `unit_index`, a contract record and dictionary entries for the new file.
- **No area-weighted version.** Section 5 shows how far apart the two methods are. An area-weighted count needs the block outlines (about 40 MB) and a land mask; it is a refinement if small-area flood or sea level rise figures will be quoted outside FPR.
- **Spanish.** The Spanish labels are new and have not been read by a native speaker (terms are in `docs/i18n.md`).
