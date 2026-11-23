# Proposal: terrain and climate (urban heat, slope, line of sight)

Date: 2026-11-04. Status: **approved by Francis on 2026-11-04 (decision 80 in HANDOFF.md); step 0 in progress.** This pull request changes no page and builds no data. It adds two rows to the wanted-data list (`ecostress-lst`, `urban-microclimate-sim`), extends three rows (`landsat-lst`, `lidar-terrain`, `towers`) with the uses below, and adds four glossary terms (land surface temperature, PET, UTCI, lidar).

**In one paragraph.** Puerto Rico's heat and its terrain shape who is exposed and who can get where. The observatory already has most of the pieces: the landslide susceptibility map (live), a 3D view with terrain and an exaggeration slider, a walking network that measures 400 m walks to transit stops, the registered towers and two checked satellite sources (Landsat surface temperature, Sentinel-2 vegetation). The proposal puts them together in six steps, cheapest first. The first four use open data and FPR's own build. The last two need more: a line-of-sight model and, for street-level heat, a research partner.

## Where the idea came from

Two LinkedIn posts Francis shared on 2026-11-03:

- **friGIS, Phase 2 (EcoRestoration Alliance):** a city digital twin first, then PALM-4U simulations of air temperature, thermal comfort (PET, UTCI), surface temperature and wind, day and night, made explorable for non-experts. The lesson: model output only helps when a non-expert can explore it, which is the observatory's purpose too.
- **A browser 3D terrain tool (built for defence planning):** elevation profiles, slope and climb, line of sight, sun direction and vertical exaggeration. The terrain methods have civilian uses here. **The defence features (own and enemy positions, cover and concealment, fire sectors) are out of scope** and are not proposed.

## What the observatory already has

| Piece | Where | State |
|---|---|---|
| Landslide susceptibility by barrio (slope is one of its inputs) | `landslide.py`, `docs/landslide.md` | Live |
| 3D terrain, hillshade, exaggeration slider (1× to 3×) | `site/js/twin3d.js`, `site/3d.html` | Live (Mapzen/AWS terrain tiles) |
| 400 m walks along mapped roads to transit stops | `walknet.py`, `roads.bin`, `docs/exposure.md` | Live (flat distance, no climb) |
| Registered antenna towers (FCC ASR, 764 built) | wanted row `towers` | Checked, not built |
| Daytime land surface temperature (Landsat) | wanted row `landsat-lst` | Checked, not built |
| Vegetation greenness (Sentinel-2 NDVI) | wanted row `sentinel2-ndvi` | Checked, not built |
| 1 m lidar terrain (USGS 3DEP) | wanted row `lidar-terrain` | Checked, low priority |
| Heat exposure from CDC and Census | wanted row `heat` | Blocked (no Puerto Rico rows) |
| Residents by age, poverty, health access; Community Resilience Estimates | ACS small-area tables, `hazard_series.json` | Live |

## The six steps

Effort scale as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks, **XL** more than 2 weeks.

### Step 0. A raster reader in the build (prerequisite, M)
**Built on 2026-11-04 (branch `build/raster-reader`): `raster.py`, our own reader, documented and checked in `docs/raster.md`.**
Every satellite and lidar step reads Cloud Optimized GeoTIFFs. `landslide.py` decodes PNG tiles with `zlib` and `numpy` because `rasterio` is not in the environment. Options: add `rasterio` (or `tifffile`) to the build environment, or read the COGs through a small reader of our own. Summaries are computed at build time; **no image is published**, only barrio and municipio figures (the map scripts are at 249.3 of 250 KB, so new views go in a Knowledge Area page or an on-demand module).

### Step 1. Daytime surface heat by barrio (M)
**Built on 2026-11-04 (branch `data/urban-heat-landsat`): `heat.py`, `heat_series.json` and `heat_barrio.json`, shaded on the Economy tab; method and checks in `docs/heat.md`. Sentinel-2 vegetation followed on the same day (branch `data/vegetation-sentinel2`): `vegetation.py`, `vegetation_series.json` and `vegetation_barrio.json`, from the same summers and on the same 60 m grid, so the two compare; `docs/vegetation.md`.**
A dry-season and a summer composite of Landsat 8 and 9 surface temperature (about 10:30 local time), cloud-masked, summarised by barrio and municipio: the median and the hottest tenth of the land. Shown next to Sentinel-2 vegetation from the same months. Each figure is labelled **surface** temperature: a roof or a parking lot can be 20 °C or more above the air on a sunny day, so this shows hot surfaces, not what people feel.

### Step 2. Night-time surface heat (M)
**Built on 2026-11-04 (branch `data/night-heat-ecostress`): `ecostress.py`, `night_heat_series.json` and `night_heat_barrio.json`, from the same summers and grid as steps 1; FPR's Earthdata token worked with no new terms; the build runs in GitHub Actions (`ecostress.yml`). Method and checks in `docs/ecostress.md`.**
NASA ECOSTRESS passes at varying hours, night included, at 70 m. Night heat matters most for health because bodies cannot cool down. FPR already holds an Earthdata login for night lights (decision 75), so this may need no new account; the LP DAAC may ask to accept its terms once, as LAADS did. Not tested yet (row `ecostress-lst`).

### Step 3. Heat and people (S, after step 1)
**Built on 2026-11-04 (branch `knowledge/urban-heat`): the Knowledge Area page `urban-heat.html` with `urban_heat.json` (`urban_heat.py`), barrio by barrio: morning heat, night heat and greenness beside residents 65 and older, poverty, households without a vehicle, people living alone and drive time to a general hospital, with margins of error; never combined, no conclusions. The Community Resilience Estimates have no barrio values, so they are not on the page. Published with the In review marker and the AI notice.**
Set the barrio heat figures against data already live: residents 65 and older, poverty, households without a vehicle, distance to health centres, the Community Resilience Estimates. Shown side by side in a Knowledge Area page "Urban heat", never combined into one score, with no conclusion in the text (the rule of the FEMA funding page, decision 72).

### Step 4. Terrain on the ground: climb on walks and sun direction (M, plus S)
**Built on 2026-11-04 (branch `data/walk-climb`): `climb.py` with `walknet.nearest_paths`, `climb_series.json` and `climb_barrio.json` (round-trip climb and walks steeper than a ramp may be, USGS 3DEP 10 m, refreshed with the nightly transit refresh; `docs/climb.md`), and a "Light from" control in the 3D view (the hillshade's light direction, tied to the map). The real sun position for a date and hour was left out: a fixed direction reads relief better.**
- **Climb on the 400 m walks.** For each walk the exposure figures already measure, add the total climb and the steepest grade, read from the terrain tiles the 3D view uses (or 3DEP lidar where finer detail changes the answer). Published as the share of residents whose walk to a current stop climbs more than a set height, by barrio. A flat 400 m and a 400 m up a hill in Barranquitas are not the same walk, especially for older adults.
- **Sun direction in the 3D view.** MapLibre's hillshade and light take a direction; a control (or the real sun position for a chosen date and hour) makes relief and shade easier to read. Small change in `twin3d.js`.

### Step 5. Line of sight from towers (M to L)
For each barrio, whether any registered tower within a set distance has a clear line over the terrain to the barrio's populated blocks. Published as the residents in blocks no tower can see. **Label it as terrain-only**: it ignores trees, buildings, antenna height and power, and frequency, and the FCC registry includes towers that carry no cellular service. It is a first check of possible gaps for emergency communications, not a coverage map, and it is never compared with a carrier's coverage claims.

### Step 6. Street-level heat simulation, PALM-4U pilot (XL, with a partner)
PALM-4U simulates air temperature, wind and the comfort indices PET and UTCI on a grid of a few metres, day and night, and can test what trees, shade or cool roofs would change. It needs 3D buildings, trees and surface materials for the pilot area and high-performance computing. FPR would not run it: a university or research centre would, for one or two pilot neighbourhoods (for example Santurce or Río Piedras), and the observatory would publish summaries and map tiles of the results, labelled as model output for a stated day (row `urban-microclimate-sim`). Approaching a partner is an FPR decision and needs leadership approval.

## What is not proposed

- Defence or targeting features of the source post.
- Treating surface temperature as air temperature, or any heat "risk score" that merges heat with social data.
- Publishing satellite images or lidar tiles (size and the map budget): summaries only.
- A radio coverage model.

## Compliance and approvals

- Not federal grant work (NASA, USGS and FCC open data; no HUD, USDA or EDA programme), so no Finance and Compliance review is needed for steps 0-5 (decision 9 applies to grant content).
- Health framing: the pages describe exposure; they give no medical advice and take no policy position.
- Step 6 (a partnership) and any public statement about heat adaptation need leadership approval.

## Decision 80 (in HANDOFF.md)

(a) Approve the plan's order, starting with step 0 and step 1. (b) Raster reader: add `rasterio` to the build environment, or keep a small reader of our own. (c) Whether step 2 may use FPR's existing Earthdata login. (d) Whether step 5 is wanted, with its terrain-only label. (e) Whether to explore a PALM-4U partner (step 6) now or later.
