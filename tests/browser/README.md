# Browser regression harness

Written for plan item 6 (the shared layer engine), which moved the colour, class, normalisation and legend code of four pages into shared modules. The question it answers: **does a change leave everything the pages show exactly as it was?** It is used by hand in a browser (the Claude Browser pane, or any browser); it is not part of `python -m unittest discover`.

## How it works

1. A **baseline** is a frozen copy of the site at a commit you trust: `git archive <commit> site | tar -x -C <dir>`, served on its own port (port 8022 in `.claude/launch.json`, entry `twin-baseline`).
2. A **collector** (`collector.py`, entry `twin-collect`, port 8099) receives what the capture scripts post and writes it to a folder of JSON files. It also serves the scripts, so one line starts a capture.
3. A **capture script** runs inside a page, drives it through its public surface (`ECON.api`, the shading menu, the year bar, `setMetric`, the chat), and posts what the page shows: legends and layer cards as HTML, the colour of each municipality on the map, values under every normalisation, the workbench's tables, the chat's answers, the paint of the 3D columns. Scripts name the capture `old_<page>_<lang>` when the page is on port 8022 and `new_<page>_<lang>` otherwise.
4. `compare.py` compares an `old_` and a `new_` capture. Numbers are compared with a relative tolerance of 1e-9; text and structure must be identical, except for what a change meant to add: `expected.json` lists those as **normalisers** (a substitution, a dropped key, a dropped item or pair) that are applied to both captures before they are compared, so everything else is still compared exactly, and the run says how many things each normaliser changed (a rule that matches nothing is visible). A path-only entry lets every difference under a path pass, and is kept for what cannot be normalised (new datasets).

| Script | Page | Capture name | What it records |
|---|---|---|---|
| `capture_economy.js` | `index.html` | `economy_<lang>` | the 108 datasets' options, units, formats and values (3 years, every normalisation, inflation-adjusted dollars); 26 layer stacks as the tab draws them (legend, layer cards, colour of each municipality, symbols, inspector, table, popup, scatter and trend data, link state); the dataset browser, presets, sources and three dataset dialogs |
| `capture_choro.js` | `index.html` | `choro_<lang>` | the shading menu (every option: legend, colours, link state) and the ranking table (every option) |
| `capture_chat.js` | `index.html` | `chat_<lang>` | 26 questions in English and Spanish, with the map state each leaves, and three of the chat's tools |
| `capture_housing.js` | `housing.html` | `housing_<lang>` | all 28 maps and charts for 7 combinations of year and base year (title, chip, statistics, readout, legend, colours, bars), the text of each block, the profile of three municipalities, six dataset dialogs |
| `capture_3d.js` | `3d.html` (tab in front) | `3d_<lang>` | the 18 column metrics: legend and the paint of the columns |

Run each capture in English and in Spanish (`?lang=en`, `?lang=es`). The Housing and 3D captures run in the background of the page and report through `window.__capture`; poll it.

The in-page glossary (`docs/glossary.md`) adds `<span class="gl-mark">` around technical words once a page is ready, which changes the HTML the captures record. (A test that audits the page's static text, such as `datamgmt_page.js`, takes the marks off its copy of the page first: a mark splits a text in pieces the audit would not find.) Turn it off in the browser before capturing, on both the baseline and the page under test: `localStorage.setItem('twin.gloss', 'off')`, then reload (a baseline from before 2026-10-19 has no glossary).

## Run it

```
# 1. servers: the site under test, the baseline, the collector (preview configs "twin", "twin-baseline", "twin-collect")
git archive <commit> site | tar -x -C <baseline dir>
# 2. in a browser tab on the baseline page, then on the page under test:
eval(await (await fetch('http://127.0.0.1:8099/s/capture_economy.js')).text())
# 3. compare
python tests/browser/compare.py <captures dir> economy_en --expect tests/browser/expected.json
```

When a change is meant to alter what a page shows, add a normaliser for it to `expected.json` with the reason, in the same commit, and re-run all ten captures (five pages, two languages). Take the captures in a page loaded fresh at 1280 × 900 with the tab in front (the 3D capture waits for the map and fails if the tab is in the background); load order, layer ids and the width of the page change what is captured.

## What it found, and its limits

- Run twice on identical code it gives identical captures (checked), apart from two sources of noise the scripts now avoid: the address bar of the Economy tab is written by a timer, and Chart.js writes sizes into its canvas tags.
- It sees what the capture scripts ask for. It cannot see a layer's look on the screen, the 3D scene, tile loading or keyboard use. Those still need a person looking at the page.
- The captures hold aggregates of published series and the text of the pages. They hold no personal data.

## The top bar by width (`bars.js`)

The harness above compares what the pages show. The top bar is about room: the longer name, the ES | EN switch and the Spanish labels leave little of it, and two reviews of pull request 3 found overflows that nobody had measured. `bars.js` opens each page in both languages at 37 widths from 320 to 1,700 px and reports anything that leaves the screen, overlaps another part of the bar, is clipped or makes the page scroll sideways (the search box counts as a part of the bar).

```
chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> about:blank
node tests/browser/bars.js [base URL, default http://127.0.0.1:8020] [pages, default index.html,3d.html,housing.html,dictionary.html] [widths]
```

It needs Chrome and a served copy of `site/`; `cdp.js` is its small DevTools client and `bar_check.js` the measurement that runs in the page. A run on the branch tip of pull request 3 (after the second round of review) found 0 problems in 296 combinations.

## The "layers on" chip (`active_layers.js`)

`active_layers.js` drives the chip at the top of the 2D map and the 3D view (`docs/active-layers.md`) in each language and width. It switches layers on from the menus, the Economy tab and the chat, and opens a link with many layers. It uses the list's buttons, "Turn all off" and Undo, and the keyboard alone. At each step it checks that the chip's number, its words and the list agree. It also checks that Límites and the 3D Scene settings stay out, and that the console stays clean. Pass a folder to save screenshots of the chip, the open list and the Undo message.

```
node tests/browser/active_layers.js http://127.0.0.1:8041 <screenshots folder> es,en 1400,390
```

A sixth argument gives the widths of the layout pass (default 1400,1024,768,390,320; at 1024 the chat is open). That pass checks that the open list ends above the map's controls and the 3D time bar, and starts below a message. The script waits for conditions in the page, not fixed times. It exits 3 when it stops before its end, 2 on an error, 1 when a check fails and 0 when all pass.

The 3D keyboard checks used to fail now and then ("Tab goes to the first layer's button", then Enter and Escape with it, more often under load). The cause was the glossary: when its pass ran while the list was open, it marked a technical word in a layer's name, Tab stopped on that word, Enter moved into its tooltip's link and Escape left the focus on the word. Pull request 98 keeps marks out of the chip (`data-no-glossary`). Before the first Tab and before the walk through the list, the script now asks the glossary to read the open list (`Core.glossary.mark`), waits until a slice of its work has run, and checks there is no mark in the list, so the old race happens every time and a mark fails a check that names it. On the code before pull request 98 those checks fail on every run.

Two more checks failed now and then. In the 3D layout pass the open list was fitted above the credits when it opened, and the credits then grew as the layers' sources loaded (from 40 to 100 px), so the list ended over them: the site now fits the list again when the map's bottom control corners or the time bar change size (`core/activelayers.js`, a `ResizeObserver`), and the script waits two frames before it measures and names the control it hits. In the rings pass the address's layers were compared as a string: the link is typed `flood,stops,muni,rings` and the map writes its own order (`muni` first) only at its first change, which under load came after `settle()`; they are compared as a set. A run under heavy load also caught a console error on the 2D map: Stops switched off while markercluster was still adding the stops in chunks (`Cannot read properties of null (reading 'getMinZoom')`); `app.js` now removes the group once markercluster has returned from its last chunk (the last `chunkProgress` call comes before markercluster finishes adding, so the removal waits one task).

## The WCRP page (`wcrp_page.js`)

`wcrp_page.js` drives `wcrp.html` (`docs/wcrp.md`) in each language and width. It checks that the Social Capital map comes first and gets the page ready while the vulnerability map has not loaded; that every explanation starts closed and that the version selector names its years from the start; that a version chosen before the map's script arrives is kept; that the legend's lines follow the area and the version; that the comparison section's button opens the change view and its bar goes back; that the municipio is shared, the pop-up stays inside the map, there is no horizontal scroll, no missing Spanish and a clean console. It then opens each closed `<details>` from a link to it, an old `#a=econ&v=change` link, and the page with `care_series.json` blocked: the Social Capital map must still draw its points and say what failed, and the vulnerability map must still load on approach. Pass a folder to save screenshots of the top, both maps and an opened section.

```
node tests/browser/wcrp_page.js http://127.0.0.1:8041 <screenshots folder> es,en 1400,390
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

`cdp.js` connects to the port in `CDP_PORT` when it is set (your own Chrome when 9333 is taken). Each evaluation in the page has a limit of 30 s unless the call gives its own (`p.eval(expr, { timeout })`); one that passes it fails with `eval did not finish within its … ms limit` and the start of the script, instead of Chrome's bare "Internal error".

## The in-page glossary (`glossary.js`)

`glossary.js` checks the underlined technical terms and their tooltip (`site/js/core/glossary.js`, `docs/glossary.md`) on the seven pages, in each language and width. On each page it waits for the glossary, then checks:
- the marks: there are some; none is in a heading (unless marked on purpose with `data-gloss`), a control, a link, a label, code, a map label or the chat; each is focusable and a button; only the word the tooltip is open for is described by it (`aria-describedby`), and a closed tooltip is empty;
- the tooltip: it opens on hover and closes when the pointer leaves (desktop); a tap opens it, a second tap closes it, a tap on plain text elsewhere closes it and stays on the page (phone, with a 1 px fingertip: Chrome moves a wider tap onto a link nearby); keyboard focus opens it, Enter moves the focus into it and Esc closes it with the focus back on the word; with the focus in a search box or another field, Esc closes it, the focus stays and the page gets the key; it stays inside the window with a 16 px gutter and links to the Glossary;
- a Leaflet pop-up (2D map) and a MapLibre pop-up (3D view) opened after load get their marks, and so does a fire station's pop-up of the 3D view's facilities module, which loads on first use;
- a clean console, no missing Spanish, no sideways scroll, and no slice of the first pass of 50 ms or more;
- on the 2D map, two seconds of panning: no glossary work meanwhile, and frames no slower than on the same map with the underlines off;
- across the pages, the words Francis named (margin of error, block group, SFHA, GeoJSON, domain, data file, estimate) are marked in each language.

It prints the marks and the first pass's main-thread time of each page, and a JSON report. Pass a folder to save a screenshot of each tooltip.

```
node tests/browser/glossary.js http://127.0.0.1:8041 <screenshots folder> es,en 1400,390 [map,3d,profile,housing,wcrp,dictionary,datamgmt]
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## A click on a point or a cluster opens no area card (`cluster_clicks.js`)

The review of pull request 75 found that a click on a cluster of stops in the 3D view zoomed in and also opened the municipality's or the barrio's card, and that a click on a stop of "Service at this hour" (deck.gl) was replaced by the card of the area under it. `cluster_clicks.js` clicks with the mouse, on land with barrios on: a cluster of stops (3D and 2D: it must zoom in and open no card), a stop of the hour (3D: a stop's card) and a fire station switched on before the barrios (3D: the station's card; bare land beside it: the barrio's). On the code before the fix it reports the two faults; after it, all checks pass.

```
node tests/browser/cluster_clicks.js http://127.0.0.1:8041 es,en 1400,390
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## One click opens what is drawn on top (`click_order.js`)

After pull request 75, the 3D view could still give a click to a layer drawn under another, depending on which layer was switched on first: a cluster of stops drawn over a circle of "Residents far from service" opened the circle's card instead of zooming in when the circles were switched on first; a flood zone inside a barrio opened the barrio's card or the flood zone's, depending on the order, and never both; the route planner, choosing a point on the map, also opened the card under the click and zoomed into a cluster; a stop or route of "Service at this hour" drawn over the same stop or route of the map showed the map's card. The click rules are now one dispatcher (`docs/layers.md`, "Clicks"). `click_order.js` checks each rule with real mouse clicks, in two pages per language and width that switch the same layers on in opposite orders:
- a cluster over a gaps circle zooms in and opens no card; a gaps circle alone opens its card;
- overlapping areas (a flood zone and a barrio; land use and a barrio; a Comunidad Especial, a flood zone, land use and a barrio) open one card with a section for each, the same text as the 2D map's sections for those features, the top area first and the barrio last, and the same card at the same place in both pages; the areas are stacked in the same order in both pages; the card's link opens the municipality's card;
- a stop inside a flood zone opens the stop's card; bare land opens the municipality's; the sea opens nothing;
- the route lines are drawn under the stops, as on the 2D map: a cluster on a route line zooms in and a stop on a route line opens the stop's card;
- a card opens at its top, the first area's heading in view, with the focus on its close button, and inside the map at 390 px; with the columns on and the camera tilted, the link names the municipality of the ground under the click, not of the column drawn over it; from the bottom: the places' heat map, the route lines, the stops, the places' points, the stations, the WCRP pins (the stations and pins switched on in opposite orders in the two pages);
- the route planner choosing point A on a cluster or in a flood zone, and "Add points by clicking the map": the point is placed, with no card and no zoom;
- deck.gl first: a stop of the hour over a cluster (its card, no zoom) and over the same stop of the Stops layer, a route of the hour over a route line, a storm track (what pointing at it shows);
- a vehicle over land and the line of a route profile open no card; a stop under a vehicle opens the stop's card (the clock is paused and moved until a vehicle covers a stop);
- a clean console and no missing Spanish.

It finds its places on the screen from the map (no fixed pixels), so it holds when the data change. With the terrain on, each `queryRenderedFeatures` reads the terrain's coordinates back from the GPU, one 1-pixel read per point of the query and per source (about 5 ms each here), so a scan of the screen for a spot could take more than the 30 s an evaluation may take, and the run stopped with "Internal error". While a search helper runs (synchronously, so no frame is drawn meanwhile), `frame()` serves those reads from one read of the whole coordinates buffer: the same bytes, so the same features (checked on 834 pixels at 1,400 and 390 px, flat and tilted: no difference), 8 to 20 times faster. Hidden layers are left out of the queries, as the page's click handler does. The page's own clicks are not touched. It reads the view's own list of clickable layers (`CLICKABLE`), so it runs on the code since this change only.

```
node tests/browser/click_order.js http://127.0.0.1:8041 es,en 1400,390
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## Ask the observatory (`ask_chat.js`)

`ask_chat.js` asks the chat a question of each kind on the 2D map and the 3D view (`docs/ask.md`), in each language and width, and checks what the page then shows: two topics ("transporte y vivienda": the routes and stops switched on, the rent shaded, the relation told as a pattern) and the chip listing them; "Turn all off" and Undo after a chat answer; a layer named alone; a place's barrios ranked and shaded by barrio; a typo read; an approximation labelled; a shelter for victims of violence not drawn; a glossary term defined; El Yunque reached beside its protected areas, a real word ("trees") answered as missing data with the nearest layers on, "turn off all layers"; the "See in 3D" hand-over (`3d.html#ask=`), the 3D buildings and storm tracks switched on; no horizontal scroll, no missing Spanish and a clean console. Pass a folder to save screenshots. It then opens Ask on every page without a map (the dictionary, Data management, the Knowledge Areas, an area profile; `docs/ask.md`, "Pages without a map"): the button before the views, the chat not loaded before use, a definition and a ranking answered in the chat, "what is this?" from the page, "Show on the map" handing the bus routes to `index.html#ask=` (where they come on) and 3D buildings to `3d.html#ask=`, the crisis and shelter replies with no map button, the Knowledge Area tabs in view and the focus back on the button. `ONLY_PAGES=1` runs only these.

```
node tests/browser/ask_chat.js http://127.0.0.1:8041 <screenshots folder> es,en 1400,390
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

`ask_timing.js` measures the time from a press of the Ask button to the first answer on Slow 4G (a first load, the cache off, the pointer over the button 300 ms before the press), three runs per language, and the compressed bytes of the chat's files: `node tests/browser/ask_timing.js http://127.0.0.1:8041 <label> 3`. `ASK_PAGE=dictionary.html` measures a page without a map instead.

## The 3D time series panel (`series_panel.js`)

`series_panel.js` drives the time series panel of the 3D view (`site/js/series3d.js`, `docs/engine.md`, "Time series panel") with real clicks and keys, in each language and width. It checks that a click on land with the columns off opens the card with its "Time series" link and loads no dataset; that the link opens the panel, loads the datasets then and moves the focus to the chart; that the key (the municipality's line, Puerto Rico's) shows at every width, inside the panel and clear of the title, the buttons and the chart; that on a desktop the panel does not cover the card's links and on a phone the card closes and the panel stays inside the screen; that poverty (ACS) shows its 5-year periods and margin of error in a band, the tooltip, the screen reader's text and the note; Home, End, the four arrows, Page Up and Page Down (five years) and "Latest", with the columns' year unchanged while the columns are off, and the tooltip of the year chosen with the keys inside the window, closed when the focus leaves; that Esc and the close button give the focus back; that with the "Any dataset" columns on a click on land opens the panel on a desktop only; that a flood zone over the sea and the route planner's pick mode open no panel; and a clean console, no Spanish missing and no sideways scroll.

```
node tests/browser/series_panel.js http://127.0.0.1:8041 es,en 1400,390 [screenshots folder]
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## The base map's fallback (`basemap_fallback.js`)

`basemap_fallback.js` blocks the base map's provider (`openfreemap.org`) and checks the 2D map, both WCRP maps and the 3D view (also at 390 px) in each language (`docs/basemap.md`, section 4): the page reaches `ready` on its plain background, the notice shows in the page's language, the data layers are drawn, no base-map credit stays, no request goes to `tile.openstreetmap.org` and the console is clean. On the 3D view it also blocks only the vector tiles after the style has loaded, holds every request to the provider (the 30 s rule) and blocks nothing (the base map draws and its credits show once). Given the port of a second Chrome started with `--disable-webgl --disable-3d-apis`, it checks the three pages without WebGL too. `cdp.js` blocks the requests of the page's web workers as well as the page's own: MapLibre fetches its tiles in workers.

```
node tests/browser/basemap_fallback.js http://127.0.0.1:8041 es,en 2d,wcrp,3d [WebGL-off Chrome port] [screenshots folder]
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## The 3D view without WebGL (`no_webgl_3d.js`)

`no_webgl_3d.js` loads `3d.html` in a browser started with `--disable-webgl --disable-3d-apis`, in each language. It checks that the loader says the 3D map cannot be drawn, that the time series panel is not built (`window.Series` is null), and that the console has no error besides twin3d.js's own stop (`Error: WebGL unavailable`, thrown on purpose to end its script), also after a click and Esc. It exits 2 when the browser has WebGL.

```
CDP_PORT=<port of the browser without WebGL> node tests/browser/no_webgl_3d.js http://127.0.0.1:8041 es,en
```

## The base map switcher (`basemap_switch.js`)

The review of pull request 92 found counts of clusters of stops drawn with no clusters after this sequence on the 3D view: Stops on, "No base map", Stops off, Liberty. The counts need the base map's fonts, so they are dropped with no base map and added again with a style that has fonts; they now take their clusters' visibility. `basemap_switch.js` runs that sequence (case 1) and checks that no count is drawn alone, then that switching Stops on shows all three layers.

Since branch `basemap-followups` (the rest of that review, `docs/basemap.md` section 4) it also checks the tile rules around a switch, with the provider's TileJSON rewritten so its vector tiles come from a local server (`tilejson.js`, port 8097 by default) that fails, holds or passes them on from the provider:
- case 2: the first tile fails and the others are held 7 s, then the first three fail: the 3D base map stays, with its credits once and no notice (on `main` at e843616 it hid at 6.1 s and stayed off);
- case 3: every vector tile fails: hidden with its notice and its source watched; "No base map" takes the notice away and resets `BM.why`; Liberty, the tiles answering, draws the base map and is kept as the viewer's default;
- case 4: every vector tile fails, then answers after a pan: the base map comes back with its credits once, the buildings as their switch says, `BM.why` null and no notice;
- case 5 (2D): a pick whose style is blocked is not kept and leaves its notice; a pick that loads is kept and takes the notice away.

```
node tests/browser/basemap_switch.js http://127.0.0.1:8041 [cases, default 1,2,3,4,5] [tile server port, default 8097]
```

## More base maps (`basemap_more.js`)

The styles added on 2026-11-13 (`docs/basemap.md`, "More base maps"), each opened fresh from its address: case 1, the 2D map with each new style in English and Spanish (it loads, the switcher and its headings in the page's language, the credits of its source once, the inspector enabled on an OpenStreetMap style and disabled on a USGS one, `bm=` kept, no 404 from the USGS, a clean console); case 2, the aerial imagery at 390 px in Spanish (the credits fold behind the "i" button once the USGS credit shows); case 3, the 3D view opened on the aerial imagery and switched to Liberty, Topographic, Dark and Shaded relief in each language (still on 8 s later, credits once, the inspector, the 3D buildings only on an OpenStreetMap style, fonts for the view's labels). It saves a screenshot of each when given a folder.

```
node tests/browser/basemap_more.js http://127.0.0.1:8041 [screenshot folder, or -] [cases, default 1,2,3]
```

It exits 2 on an error, 1 when a check fails and 0 when all pass. `basemap_fallback.js` uses `tilejson.js` too, for the TileJSON with its tiles on a host that does not exist (3D, 1400 and 390 px, timed).

## The view state shared by the 2D map and the 3D view (`view_state.js`)

`view_state.js` checks the address both views share (`site/js/core/viewstate.js`, `docs/view-state.md`), in each language and width. On the 2D map it selects Ponce, turns on flood zones and routes, shades the municipios, adds two Economy layers (one Shaded, one Symbol) and a year, and checks the address and the 3D link. It opens the 3D view from that link and checks the camera (the zoom one less), the layers (the 3D vehicles and terrain as by default), the columns (height from the Symbol layer, colour from the Shaded one, the year) and Ponce's card. It then changes layers, the camera and the columns' height, and checks that the address follows with no new history entry. Back on the 2D map from the 3D link, it checks the layers, the Economy layers and year, the shading (off: the columns, changed in 3D, show the Economy datasets), Ponce and the camera, with the 3D-only parts kept in the address. Last, an old 3D link (defaults) and a bogus one (what reads applied, the rest ignored and kept). A clean console throughout.

```
node tests/browser/view_state.js http://127.0.0.1:8041 es,en 1400
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## The OpenStreetMap inspector (`osm_inspect.js`)

`osm_inspect.js` drives the inspector of the base map (`site/js/core/osminspect.js`, `docs/basemap.md` section 8) on the 2D map and the 3D view, in each language and width, over Old San Juan on Liberty. It switches the toggle on with the keyboard, clicks a named place and a named road and reads the pop-up (kind, name, the OSM link from the feature's tile ID), clicks a house number taken from the tiles and checks a 12 × 12 grid (never a house number or a building), checks that the data layers take no click while it is on and the same click as before once Esc has turned it off, and that "No base map" disables it. It needs a Chrome with the GPU (MapLibre).

```
node tests/browser/osm_inspect.js http://127.0.0.1:8041 2d,3d es,en 1400,390 <screenshots folder>
node tests/browser/osm_inspect_lend.js http://127.0.0.1:8041 2d,3d
```

On the 2D map it also checks that, with the mode on, the controls over the map (the layers chip, the Undo of a message, the Economy legend) still work. `osm_inspect_lend.js` (review of PR #99) checks that a road label and a road line lend each other an ID or a name only when they are the same road: it walks every merged label and road line at three places, in 2D and 3D.

It exits 2 on an error, 1 when a check fails and 0 when all pass.

## The fixes of the usability pass (`usability.js`)

`usability.js` checks the small fixes of the first-visit usability pass of 2026-10-27, in each language and width: the Route analysis and Global Innovation Index pages start under their section bar (no empty band left for a year bar they do not have); the sort buttons of the route comparison table are at least 24 px tall and show the focus ring; the data dictionary opened with no link stays at its top while its Spanish arrives; the 2D map's Trend view (Economy workbench) is a slider for the keyboard (the arrows, Page Up, Page Down, Home and End move the year, which the chart's tooltip shows and a screen reader hears); the search box of the 2D map and the 3D view shows its long hint only where it fits (also at 1024 px); a clean console and no missing Spanish.

```
node tests/browser/usability.js http://127.0.0.1:8041 es,en 1400,390
```

It exits 2 on an error, 1 when a check fails and 0 when all pass.
