# Regions: the map's Region tab and the regional area profile (2026-10-31)

The project lead asked for a regional profile view "just like the municipality view". A region is a **group of whole municipios**. The observatory now offers:

- the **Eastern Region** of FPR's Eastern Region Strategic Vision (ERSV): Canóvanas, Ceiba, Culebra, Fajardo, Humacao, Juncos, Las Piedras, Loíza, Luquillo, Maunabo, Naguabo, Río Grande, San Lorenzo, Vieques and Yabucoa;
- the Puerto Rico Tourism Company's **seven tourism regions** (from the crosswalk, `docs/geography.md`).

## The list: `site/data/geo/regions.json`

Written by `python regions.py` (`--check` compares a rebuild). Each region has `id` (`ersv`, or the crosswalk's `reg-` code), `kind` (`planning` or `tourism`), `name` `{en, es}`, `source` `{en, es}`, `ids` (municipio codes) and `names`. No figure is stored. `women_labor.py` takes the ERSV list from `regions.py`, so there is one list.

**To add a region:** add it to `PLANNING` in `regions.py` (codes and names; the script checks each name against the crosswalk), run `python regions.py`, `python dictionary.py`, `python registry.py`, and the tests. The map's tab, the regional profile and the Women in the labor force page pick it up. A region that is not made of whole municipios (a corridor, a watershed) belongs in the workbench's Study areas instead (`docs/study-areas.md`).

## How a region's figures are made

Never an average of percentages when the parts are published:

| Kind of value | Region's value | Mark |
|---|---|---|
| A count or a dollar total | the sum of its municipios, exact; its 90% margin is the square root of the summed squared margins (ACS General Handbook, ch. 8) | Σ |
| A share whose numerator and base are both published | the sum of the numerators over the sum of the bases, exact; the margin of a proportion | ⊕ |
| Any other rate, ratio, median or level | **Region tab:** the range of its municipios. **Regional profile:** the average of its municipios weighted by their residents, marked as an estimate, with no margin (an average of medians is not the region's median) | ≈ |

A value is left out when one of its municipios has none, so a sum is never short of a municipio.

The pooled pairs (`POOL` in `site/js/profile_region.js`) were checked on 2026-10-31: count ÷ base × 100 equals the published rate in all 79 areas to its rounding, and `tests/profile_region.test.js` keeps that true. Today: women's labor force participation; vacancy, seasonal and other-vacant shares (survey and census); the BLS unemployment rate; the government share of jobs; and the nine age-group shares.

## The map's Region tab

`site/js/region.js`, loaded with its Spanish (module `region`) the first time the tab opens, so the map's first load does not carry it. The tab bar of the 2D map has five columns (`.tabs.tabs-5` in `twin.css`). The tab:

- outlines the region on the map and zooms to it (the outline goes when another tab opens);
- lists its municipios (each opens the Municipality tab);
- gives People (residents, change 2010-2020, women's labor force participation pooled with its margin, residents per km²), Visitor economy, Mobility and Housing, built from `municipalities.json` and `labor_sex_series.json` by the rules above;
- links to the regional profile and to the Women in the labor force page for that region.

## The regional area profile: `profile.html?region=<id>`

`site/js/profile_region.js`, with `profile.js`. Every dataset of the area profile, with three values: the region, the rest of Puerto Rico (the other municipios, built the same way) and Puerto Rico, plus the region's trend. Ranks and similar municipios are not shown for a region. The page's selector lists the regions first, then the municipios. "Download CSV" saves every row with its method.

## The region filter of the Layers tab (2026-11-24, HANDOFF decision 113)

The project lead asked to filter by region from the Layers tab, in the Reference group. The 2D map and the 3D view both have a **Region** menu there (under the base map in 2D, first in Reference in 3D): "All of Puerto Rico", then the FPR planning regions and the tourism regions of `regions.json`, each with its number of municipios. No region is defined anywhere else.

- **What it does:** it outlines each of the region's municipios, lays a white veil (55% opacity) over the other municipios and frames the map on the region. The note under the menu says how many municipios are outlined and links to the regional profile.
- **What it does not do (the choice of decision 113):** it does not cut the data layers. A layer still draws the whole island (faded outside the region), and every legend, count, ranking, Explore panel and download still covers all of Puerto Rico. Cutting each layer to a region would change what its numbers mean in every panel without saying so; the Region tab and the regional profile already give a region's own figures, built by the rules above. The filter is a way of looking, not a new geography.
- **Clicks:** the veil and the outlines never take a click (2D: their own pane, `regionfilter`, z-index 410, above the data panes and the canvas of the points, under the markers and pop-ups, with `pointer-events: none`; 3D: a flat fill and a line under the base map's labels). The tourism places' pins and clusters sit above the veil, so they are not faded.
- **The address:** `rg=<id>` (`core/viewstate.js`, `docs/view-state.md`), written by both views and carried in their links. An address with `rg=` and its own camera (`c=`) keeps the camera; without `c=` the map frames the region. The regional profile's "Open on the map" (`index.html#rg=<id>`, no `c=`) still opens the Region tab, and now also sets the filter; an address the map wrote (it always has `c=`) does not open the tab. An id that is not in `regions.json` is dropped.
- **Code:** `site/js/core/regionfilter.js` (`split`, `bbox`, `options`, `leaflet`, `maplibre`, `control`), loaded on use by `app.js` and `twin3d.js` (`startRegionFilter`, `whenShown`), with `data/geo/regions.json` ("on_use" in `dictionary_src/routes.json`): the first time the Reference group is opened, or at ready when the address has `rg=`. Until then the menu is disabled. Nothing is added to the first load or to the libraries loaded after ready (the map's are at 196 of 200 KB). Its Spanish is the page scope `regionfilter` of both pages. The Region tab is unchanged and draws its own orange highlight while it is open.
- **Checks:** `tests/regionfilter.test.js` (the split, the bounding box, the menu, unknown ids) and `tests/viewstate.test.js` (`rg=` read and kept); in a browser, `tests/browser/region_filter.js` (headless Chrome: both views, the address, a base-map switch in 3D).

## Checks

`tests/profile_region.test.js`: the regions file (15 ERSV municipios; the tourism regions cover the 78 once each), every pooled pair, the ERSV's pooled women's participation against `women_labor.py`, a sum and its margin, a missing municipio, and the residents-weighted estimate.
