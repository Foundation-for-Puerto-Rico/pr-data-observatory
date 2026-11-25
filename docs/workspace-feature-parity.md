# Workspace redesign: feature parity checklist

State on 2026-11-24, branch `feat/carto-workspace-refresh`, against `main` at `2d3fac9`.

The redesign gives the observatory the look of the CARTO-style workspace prototype. It keeps the repository as the foundation: the Leaflet map, the shared engine (`site/js/core/`), every route, the data in `site/data/` and the connector. The design guide is `docs/workspace.md`.

This list was made from the code, the registered datasets, the routes and the tests, not from the README. It covers both versions: the current observatory and the prototype (`site/workspace/` of the local trial, never published).

## Status words

- **Kept**: the code is unchanged and the feature is reached where the table says.
- **New**: added by the redesign.
- **Partial**: works for part of the task. The gap is named.
- **Not carried over**: in the prototype, not in this branch. The reason is given.

## How it was checked

| Check | What it covers | Result |
|---|---|---|
| A. Values | `tests/…` are unchanged for the engine. In a browser, every dataset's values (562 datasets, 5 years, every normalization: 15,115 cells) on this branch against a copy of `main` | 0 differences. 97,653 missing values stay missing |
| B. Links | Five links in the old address form (`e=`, `ey=`, `eb=`, `l=`, `slr=`, a legacy `s=`, a bare municipio) opened on both | The same layers, year, base year and place on both |
| C. Journey | 55 scripted steps in headless Chrome: the timeline, undo and redo, the eight panel tabs, the ten workbench views, Ask, the widgets, saved maps, four widths, twelve other pages | 55 pass |
| D. Repository checks | `python -m unittest discover -s tests`, `node --test tests/*.test.js`, `contract.py`, `i18n.py --check`, `catalog.py --check`, `registry.py --check`, `dictionary.py --check`, `budget.py`, `check_refresh.py` | All pass (two tests updated, see the pull request) |
| E. Looked at | Screenshots of all 28 pages in the dark theme, and of the map in both themes, in Spanish, at 1440, 1024 and 390 px | Read by Claude, not by a person. No screen-reader pass |

"Loads" below means: the page or tool opened in check C with no console error. It does not mean every control was exercised.

## 1. The shell, on every page

| Feature | Before | Now | Status | Checked |
|---|---|---|---|---|
| Top bar: logo, page name, search (map, 3D), Ask, ES / EN | Static header in each page | Same markup, compact style from `css/ws.css` | Kept | C, E |
| Navigation between views | Five buttons in the top bar | A rail down the left side (a bar along the bottom under 900 px): Explore, Data, Map, Workflows, 3D + Time, Knowledge, Data dictionary, Learn | New | C: eight links on every page |
| Light and dark | Light only | Both. A switch beside ES / EN; the choice is kept in the browser (`twin.theme`); pages open dark without one | New | C, E |
| English and Spanish | `i18n.js` and bundles | Same. New text is in `i18n_src/es/workspace.json`, `workspace_pages.json` and `common.json` | Kept, extended | D; C in Spanish. The new Spanish was written with Claude and needs a native speaker |
| Glossary underlines, help buttons, lesson links | `core/glossary.js`, `help.js` | Unchanged | Kept | D |
| Embedded pages (`?embed`) | No top bar | No top bar and no rail | Kept | Not opened in a browser |

## 2. The map (`index.html`)

| Feature | Implementation | Where it is now | Status | Checked |
|---|---|---|---|---|
| Layout | `twin.css` | Layers panel on the left (foldable), the project bar, the map, the timeline, the workbench below, widgets on the right (foldable; a drawer under 1100 px) | New | C at 1280, 1024, 768, 390 |
| Explore by topic, topic pages, search of all data | `catalog.js` | Left panel, Explore › Topics. Also `explore.html` | Kept | C: tab opens |
| Map layers: about 50 switches in nine groups, with their legends and settings | `app.js`, `core/layers.js`, `facilities.js`, `soil.js`, `terrain.js` | Left panel, Explore › Map layers | Kept | D (`layers_menu.test.js`); C: flood and sea level rise switched |
| Data Catalog tab | `catalog.js` | Left panel, Explore › Data Catalog. Also `data.html` | Kept | C |
| "On the map" chip and panel: layer cards, Turn all off with Undo | `core/activelayers.js` | On the map, as before | Kept | C: undo uses its snapshot |
| Layer cards: shaded or symbols, normalization, classes and own limits, palettes, opacity, fixed classes, inflation adjustment, barrio shading, two-variable maps, less-reliable hatching, margins of error | `economy.js`, `core/panel.js`, `core/classify.js`, `core/normalize.js`, `core/reliability.js`, `econ_level.js` | "On the map" panel | Kept | A for values. Controls not exercised one by one |
| Legend, "Match periods", "View the map as a table" | `core/stack.js`, `core/legend.js` | On the map | Kept | D (`core.test.js`) |
| Municipality profile, region profile, rankings, CSV | `app.js`, `region.js` | Left panel, Place | Kept | C: tabs open |
| Place search, online address lookup, "Route from / to here" | `plan.js`, `app.js` | Top bar | Kept | Not exercised |
| Map inspection (click card), OSM inspector, base map, region filter | `app.js`, `core/osminspect.js`, `core/basemap.js`, `core/regionfilter.js` | As before | Kept | D |
| Base map in the dark theme | `core/basemap.js` | The 2D maps open on the Dark style in the dark theme, unless the viewer chose one (`bm=` or a saved default) | New | D (`basemap.test.js`) |
| Map tools (21): measure, draw an area, area around a point, walking time, what drains here, CRIM parcels, build my region, count my points, study areas, land-use analysis, slope, contours, watersheds, sea level rise, plan a route, residents far from service, walk radius, compare two maps, small multiples, composite index, scenarios, places in hexagons, save as image, copy link, map as a table | `maptools.js` and the modules it loads | Left panel, Tools › Map tools | Kept | C: the pane lists them; D. Each tool not run |
| Transit: operators, timetable status, vehicles on their timetable now, residents far from service, integration points, route planner and scoring | `network.js`, `plan_route.js` | Left panel, Tools › Transit | Kept | C: tab opens |
| Analysis: 562 datasets, presets, dataset browser, sources, dataset dialog with CSV | `economy.js` | Left panel, Tools › Analysis | Kept | A, C |
| Workbench: Inspector, Table, Scatter, Trend, Correlations, Small multiples, Compare (swipe), Composite, Scenarios, Study areas | `economy.js`, `workbench.js`, `scenarios.js`, `studyareas.js` | Below the map | Kept | C: all ten open |
| Workbench size | Fixed by CSS | A grip on its top edge: drag, arrow keys, double-click to reset; kept in the browser | New | C |
| Ask | `chatboot.js`, `chat.js`, `ask.js` | Top bar. It takes the place of the widgets while open | Kept | C: opens |
| Clean view, save as image | `core/cleanview.js`, `mapimage.js` | As before. Clean view also hides the project bar, the timeline and the widgets | Kept | D. The image export was not run on the new layout |
| Share link and saved state | `core/viewstate.js` | Unchanged address form. "Copy link" in the project bar | Kept | B |
| Project bar: map name, Undo, Redo, Copy link, Save, My maps | — | Above the map | New | C |
| Undo and redo | — | The layer switches, the engine's layers, the planned route and the year, up to 60 steps (Ctrl + Z, Ctrl + Y). It reuses the snapshot that "Turn all off" restores | New | C |
| Saved maps | Scenarios only | Named maps in the browser (`twin.maps`): save, open, copy link, delete, download and open a file. A saved map is its address | New | C: saved and listed. Reopening reloads the page |
| Widgets | — | Key figure, over time, spread, by tourism region, highest and lowest, for one dataset on the map. They follow the timeline. Region and range filters and "only what the map shows" state what they count and clear with one button | New | C |
| Widgets filter the map and the workbench | Prototype | The filters change the widgets only. The page says so | **Partial** | — |
| Widgets a person adds, removes and reorders | Prototype | Fixed set; each one folds | **Partial** | — |

### The timeline

| Requirement | State | Checked |
|---|---|---|
| A horizontal slider replaces the year dropdown | Done. The old dropdown and slider stay in the page (hidden) so nothing that reads them breaks | C |
| Ticks, selected-period label, previous and next, play and pause, speed, Latest | Done | C |
| Mouse, touch, keyboard, visible focus, screen-reader values | A native range input: arrow keys, Home, End, Page Up and Down. `aria-valuetext` gives the year or "Latest available, 2026" | C for the attributes. Not tried with a screen reader |
| Reduced motion | Playback is never faster than one step in two seconds, and transitions are off | Code read; not measured |
| Bounds and steps from real data | `ECON.api.years()`: the years any moving dataset has (2010 to 2026 today). Nothing is hardcoded | A, C |
| Each layer shows its real period | A chip per layer: "2011–2015", "2020–2024 (latest at or before 2026)", "snapshot 2026", "first data 2014". Uses the engine's own rule and words | C |
| No interpolation, no zero for missing | The engine is unchanged | A |
| Other clocks stay separate | Sea level rise (feet, a scenario) and "vehicles on their timetable now" (Puerto Rico time, a schedule estimate) keep their controls; the timeline names them when they are on. The 3D view keeps its own time bar with its day, year and storm modes | C for the 2D notes |
| Single-period and static datasets | The timeline says a snapshot does not change with it; with no dataset it says what to do | C |
| The year in share links and saved maps | `ey=`, as before | B, C |
| Rapid movement | Slider moves are applied once per frame and the last one wins. The engine sets the year from memory, with no request in flight | C: 41 moves in one task end on the last |
| Rankings and the place profiles follow the year | They show the latest year, as on `main` | **Not changed** |
| A date-range mode | Not added: no operation of the engine aggregates across years | — |

## 3. The new areas

| Area | What it holds | Source of its lists | Status | Checked |
|---|---|---|---|---|
| Explore (`explore.html`) | 19 ready-made views, the ten topics, the maps saved in the browser, "Continue where you left off", 24 topic pages and tools | `catalog_views.json`, `catalog.json`, `knowledge_items.js` | New | C |
| Data (`data.html`) | All 1,174 documented entries as cards: 496 datasets by year, 46 map layers and sets of places, 632 documented only. Search (also by Spanish name and summary), filters by topic, what it holds, geography, license, period and source. The filters are in the address | `catalog.json`, `catalog_index.json`, `catalog_es.json` | New | C |
| Data: preview of values on a card | Prototype (sparkline, highest and lowest rows) | Not carried over: it would load the 43 series files on the catalog page. The card opens the data dictionary entry instead | **Not carried over** | — |
| Workflows (`workflows.html`) | Source, filter, "lie inside", summary by municipio, output. 17 sources (every published file of points) and six kinds of area | `registry.json` | New | C: the example gives 95 schools and 27,114 students in the 1% flood area and names 13 schools within 5 m of an edge, the prototype's figures |
| Workflow output on the map | Prototype: datasets on the map at once | The table downloads as CSV, and in the model-output form that the map's Scenarios tool reads | **Partial** | The download was not opened on the map |
| Import a CSV or GeoJSON | Prototype: points and tables | The map's own tools do this: Count my points, Study areas (GeoJSON), model outputs (CSV) | Kept (existing tools) | D |

## 4. The other pages

Each keeps its route, scripts and data. Each gained the shell and both themes.

| Page | Features (unchanged) | Checked |
|---|---|---|
| `3d.html` | Terrain, buildings, columns by any dataset with its year, time bar (day of transit, sea level by year, storms since 1851), service at this hour, route planner, Ask | C: loads. Its time controls were not exercised |
| `profile.html` | Municipio and region profiles, ranks, trends, similar municipios, CSV | C: loads |
| `housing.html` | The 2023 study with live series; its own year bar (previous, next, slider, play, base year) | C: loads |
| `dictionary.html`, `data-management.html` | Entries, sources, glossary, files, cite; the file inventory | C: load |
| `knowledge.html`, `learn.html` | The Knowledge home and the lessons | C: load |
| `public-spending.html`, `wcrp.html` | Budget and spending; WCRP maps | C: load |
| `broadband`, `energy`, `gii`, `inflation`, `money-cycle`, `opportunity-zones`, `public-money`, `reservoirs`, `route-analysis`, `transit-links`, `transit-reach`, `unused-funds`, `urban-heat`, `women-labor`, `404` | Each page's own maps, charts and tables | E: dark theme looked at. Not opened in check C |
| The 14 pages written by `docs/analysis/*/make_page.py` | — | The generators now write the same header. They were not run |

## 5. Behind the pages

| Item | State |
|---|---|
| Data files, calculations, generators | Unchanged, except `registry.json` (which page loads which file) |
| Connector (`connector/`) | Unchanged. It reads no page file; its map links (`e=`, `ey=`) work as before (check B) |
| Scheduled refreshes and the nightly bot | Unchanged |
| Deployment (`pages.yml`: Azure Static Web Apps) | Unchanged |
| Page weight | Map scripts 211.7 of 250 KB. Ten page budgets rise by 1 to 2 KB for the theme switch. Three new routes |
| Privacy checks | Unchanged, passing |

## 6. Known limits

1. The widgets' filters do not dim the map or filter the workbench table.
2. A workflow's result reaches the map through a download, not directly.
3. Rankings and the place profiles do not follow the timeline (as on `main`).
4. The new Spanish needs a native speaker's review.
5. No screen-reader or keyboard-only walk-through was done by a person.
6. `tests/browser/usability.js` (manual) expects the old two-row phone top bar, and `tests/browser/bars.js` the old button bar. Both need updating before they are used again.
7. The base-map tiles, the icons and the fonts still come from other hosts, as before.
8. Charts that draw with fixed light colors inside a page (for example the projection band on the inflation page) were not all restyled for the dark theme.
