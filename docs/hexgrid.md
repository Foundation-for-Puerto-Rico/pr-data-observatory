# The hexagon grid (decision 107, step 9, parts 1 and 2)

Built 2026-11-19 (row `derived-hex-grid`); heat, greenness and slope added 2026-11-20. One grid of equal hexagons of 1 km² over Puerto Rico, Vieques and Culebra, with residents, housing units, buildings, land under buildings, residents in FEMA's 1% flood area, surface temperature, greenness and slope in each cell. A map layer in the Explore tab (Reference → Hexagon grid (1 km²)) on the 2D map and in the 3D view, with a picker for the measure that shades it.
The code is `hexgrid.py`, the tests are `tests/test_hexgrid.py`, the file is `site/data/hex_grid.geojson` (9,398 cells, 6,887 with residents; 2.8 MB raw, about 390 KB compressed, loaded when the layer is switched on).

## 1. Why these hexagons

The map's own grid (`site/js/core/hexbin.js`, which already counts tourism places): a Lambert azimuthal equal-area projection centered on Puerto Rico (18.2 N, 66.45 W), pointy-topped hexagons laid on the plane. Every cell covers the same ground area (to about 0.3%), so with cells of 1 km² a count is a density per km². `hexgrid.py` ports `hexbin.js`'s functions; a test runs both on 2,000 points and gets the same cell ids.

**Changed from the plan:** the plan named H3 resolution 8, the FCC's hexagons. H3 cells differ in area across the island, and the FCC publishes only the H3 cell of each location, so broadband cannot be moved to another grid; it stays on its own layer (Broadband gaps).

## 2. What each cell holds

| Field | What | Source |
|---|---|---|
| `p` | residents, 2020 | Census blocks, each counted whole in the cell of its internal point |
| `h` | housing units, 2020 | the same |
| `b` | buildings | Overture footprints, release 2026-10-21.0, by their point |
| `bf` | land under buildings, % of the cell | the same footprints' area |
| `pf` | residents in FEMA's 1% annual chance flood area, % of the cell's residents | blocks whose internal point is in the area (exposure.py's rule) |
| `t` | land surface temperature of summer mornings, °C: median of the cell's 60 m cells | heat.py's composite (Landsat 8 and 9, June to September of the last three summers) |
| `g` | greenness (NDVI): median of the cell's 60 m cells | vegetation.py's composite (Sentinel-2, the same summers) |
| `s` | slope of the ground, %: mean of the cell's 10 m cells | slope.py's blocks of about 60 m (USGS 3DEP, 1/3 arc-second) |

`t`, `g` and `s` are empty when less than a tenth of the hexagon has a value (28 of its about 278 cells of 60 m; 1,000 of its about 10,000 cells of 10 m): mostly coastal cells. A hexagon of land with no resident and no building is kept with its counts at 0, so the three cover the island: 653 such cells, most of them forest and mountain.
`hexgrid.py` reads the 60 m values from a file that heat.py and vegetation.py leave in their caches (`cache/heat/cells_<scenes>.npz`, `cache/vegetation/cells_<scenes>.npz`, never published); when it is missing it builds the composite again from the cached scenes, with no network (about 6 and 5 minutes). The slope comes from `cache/slope/blocks_<version>.npz`.

## 3. Checks

- The cells add up exactly to the island: 3,285,874 residents, 1,598,159 housing units, 2,157,363 buildings.
- Residents in the flood area (316,309) equal the exposure series' `flood_sfha` total.
- The surfaces follow the barrio files' physics checks: a hexagon in Hato Rey (San Juan) is hotter (43.3 °C) and less green (NDVI 0.11) than one in the center of Jayuya (36.4 °C, 0.54); El Yunque reads 28.9 °C, 0.83 and a 38% slope.
- Across the hexagons: surface temperature 25.2 to 49.3 °C (median 33.5), NDVI 0.01 to 0.89 (median 0.79), slope 0 to 97% (median 29%).

## 4. Reading the numbers

- A census block is counted whole in one cell. A large rural block puts all its residents in one hexagon, so rural cells look lumpy; urban blocks are much smaller than a cell.
- `pf` is often 0% or 100% in rural cells for the same reason.
- Nothing about a single home is published: census blocks are public counts, and buildings are counted, not drawn.
- Surface temperature is the ground's (roofs, pavement, soil, canopy) on clear summer mornings at about 10:30, not the air's and not the afternoon peak.
- The surfaces are calculated from satellite and elevation data, not estimated; their accuracy is the source files' (see heat.py, vegetation.py and slope.py).

## 5. On the map

`core/facilities.js` gives an area layer an optional list of measures (`area.measures`, `area.pick`); the legend shows a "Shade by" picker, and the 2D map (`facilities.js`) and the 3D view (`facilities3d.js`) restyle when it changes. The pop-up of a hexagon lists every measure.

## 6. Next (step 9)

The layers that build on the grid or the road network: residents who can be cut off, what lies upstream of each reservoir, jobs within reach and net migration by age.
