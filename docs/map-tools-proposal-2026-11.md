# Proposal: the Tools tab becomes the map's toolbox

Date: 2026-11-10. Status: **approved by the project lead on 2026-11-11 ("Aprobar y construir"), choices (a) to (e) as proposed (decision 97 in HANDOFF.md). Step 1 built on branch `tools/map-tools-list`.**

**In one paragraph.** On 2026-11-10 the project lead said the Tools tab (Herramientas) opens on a ranking of municipalities, and that it should hold the mapping tools people can use instead, with the ranking kept wherever it fits best. Checked against main (`1f407f6`): the observatory already has **15 tools a visitor can use on the map**, but only one of them, "Area around a point", has a button in Tools. The others are switches in Map layers, views of the workbench under the map, a panel of their own or sections of Transit. The proposal builds no new analysis in its first step. It gathers the tools that exist into one list in Tools, each with one button that opens it where it already works, moves the ranking to Place, and fixes an English button on the Spanish page. New tools come after, one at a time.

## 1. What Tools holds today

| Subtab | Content | File |
|---|---|---|
| Rankings (opens first) | "Rank municipalities by any dataset": a dataset, "Show as", "Show on the map", the ranked table and a CSV download | `site/index.html` `#tab-rank` |
| Transit | Planning layers, what is live, operators, **Plan a route** | `#tab-transit`, `network.js`, `plan_route.js` |
| Analysis | One "Area around a point" button, then the Economy tab's datasets (`#econRoot`) that feed the workbench | `#tab-economy`, `economy.js` |

**A bug seen in the project lead's screenshot.** The ranking's button reads "Show on the map" in English on the Spanish page. The Spanish text exists only in `i18n_src/es/studyareas.json` and `wcrp.json`, which load later; `map.json` lacks it.

## 2. The tools the observatory already has

| Group | Tool | What a visitor does | Where it is today | How it opens |
|---|---|---|---|---|
| Measure an area | **Area around a point** | A circle or ring of 400 m to 20 km around a point; residents, stops, heat, greenness, landslide | Tools › Analysis, workbench › Study areas | `data-ecbench="study"` |
| | **Study areas** | Load their own GeoJSON, measure what each area holds, export it | Workbench under the map | workbench view `study` |
| | **Land-use analysis** | Share of each land-use class, Puerto Rico and each municipio | Its own panel under the map | `openLanduse` (`app.js`) |
| Terrain and water | **Slope, with a threshold** | Shade the slope; the slider shows only ground at or above a slope | Map layers | `#lySlope` |
| | **Contour lines** | Lines every 100, 50, 20 or 10 m, following the zoom | Map layers | `#lyContours` |
| | **Sea level rise** | NOAA's flooded area for a rise of 1 to 10 ft | Map layers | `#lySlr` + `#slr` |
| Getting around | **Plan a route** | A route along the roads, with who and what it reaches and where it connects | Tools › Transit | `#planBox` |
| | **400 m walk radius** | Rings around stops | Map layers (transport) | `#walkRings` |
| | **Residents far from service** | Where people live beyond a walk to a scheduled stop | Tools › Transit | `#lyGaps` |
| Compare and combine | **Compare two maps** | A swipe between two layers | Workbench | view `swipe` |
| | **Small multiples** | Several layers side by side | Workbench | view `multiples` |
| | **Composite index** | Combine layers with chosen weights into one map | Workbench | view `composite` |
| | **Scenarios** | Save a view with its figures; export it | Workbench | view `scenarios` |
| Density | **Hexagons of equal area** | Count tourism places in hexagons of 2, 10 or 50 km² | Map layers (tourism places) | `#placesView` |
| Share and download | Copy a link, see the map as a table, download CSV | Spread over the page | several |

Scatter, Trend and Correlations are charts, not map tools. They stay in the workbench.

## 3. The proposal

### 3.1 Tools: one list, grouped, opening what exists
- Tools opens on a new first subtab, **Map tools** (Herramientas de mapa), with the five groups of section 2. Each tool is one row: an icon, its name, one plain sentence, one button.
- The button **opens the tool where it already works**: it switches the layer on and opens its fold, opens the workbench view, or opens the panel. On a phone it closes the side panel so the map shows (`isMobile()`/`setPanel(false)`). No tool is copied; Map layers keeps its switches.
- **Transit** stays as the second subtab. **Analysis** stays as the third, without its "Area around a point" button, which moves into the list.
- A tool that is not built has no row. There are no "coming soon" rows.

### 3.2 The ranking moves to Place
- **Place › Rankings**, third subtab after Municipality and Region. The ranking compares municipios, as Place already does. Nothing in it changes.
- Code and links that open the ranking keep working: `showTab('rank')` finds a pane by name in any group (`common.js`). The help texts that say "The Tools tab ranks the municipalities" (`map.json`, About) are rewritten.
- **PR #186** (rank ranges), which changed the same tab, merged on 2026-11-10; the move builds on it.

### 3.3 Fix the English button
- "Show on the map" is added to `i18n_src/es/map.json`.

### 3.4 Size
- Map scripts are **249.2 of 250 KB** on main (`budget.py`, LF copy); PR #186 brings them to 250.0. The list is markup in `index.html` (counted as html+css, not scripts). The few lines that make each button work load the first time Map tools opens, or space is made in the same PR. The number is measured before and after and given in the PR.

## 4. Tools that are missing

Already approved in **decision 93** (GIS tools); all four were built on 2026-11-11 as stacked PRs #194 to #197. Each gets its row once it is on main:
- Step 3: **Watersheds** and "What drains here".
- Step 4: **Build my region** (pooled, not averaged) and **Count my points** (private homes and sensitive sites are counted, never drawn or named).
- Step 5: **Download what is inside** an area.
- Step 6: **Walking travel time** on the published road network.

Not proposed before, and expected by most map users:
- **Measure distance and area**: click points on the map, read metres or km² (on the local flat projection `core/study.js` already uses).
- **Save the map as an image** (PNG), with its legend, source line and date.
- **Draw an area** and send it to Study areas, so a visitor does not need a GeoJSON file.

Each loads on first use, like the workbench.

## 5. Choices for the project lead

- **(a)** Tools opens on **Map tools**, grouped as in section 2; Transit and Analysis stay as subtabs.
- **(b)** The ranking moves to **Place › Rankings** (PR #186, which changed it, is merged).
- **(c)** Each row opens the existing tool; nothing is duplicated, and Map layers keeps its switches.
- **(d)** No rows for tools that are not built.
- **(e)** After this, the order of new tools: **Measure distance and area** and **Draw an area** first (small, used by everyone), then **Save the map as an image**, then decision 93 steps 3 to 6.

## 6. Steps

Effort as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days.

1. **Map tools list + ranking to Place + Spanish fix (S-M). Shows on the site.** One pull request: (a) to (d). Checked in the browser in Spanish and English, desktop and phone, with every button opening its tool. **Built 2026-11-11:** 22 tools in five groups (decision 93 steps 3 to 6 were on main by then, so What drains here, Walking time, Build my region and Count my points have rows; Places in hexagons joined Compare and combine). The buttons' code is `site/js/maptools.js`, loaded the first time the pane opens; the pane's Spanish loads with it (module `maptools`, as the About tab), because the map's Spanish bundle counts against its 250 KB of scripts.
2. **Measure and draw (S-M).** One on-use module; drawn areas join Study areas. **Built 2026-11-11** (branch `tools/measure-draw`, `docs/measure.md`): distance by the haversine formula, area in km², hectares, cuerdas (Ley 145 de 1968) and acres, a warning when edges cross, and "Add as a study area" into the set "Drawn areas".
3. **Save the map as an image (S).** **Built 2026-11-11** (branch `tools/map-image`, `docs/map-image.md`): a PNG of the map on screen with its legends, scale bar, sources, date and address.
4. Decision 93 steps 3 to 6, each on his word, each adding its row.

One pull request per step, each on the project lead's go-ahead.
