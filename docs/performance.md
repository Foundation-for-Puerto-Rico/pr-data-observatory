# Page weight and load time (Phase 3, item 13)

Plan: `docs/proposal-2026-10.md`, section E (J row 13). This file covers four things: what each page loads, the budget the build enforces, how load times are measured on a slow connection, and the decisions on the larger formats.

## The budget

`python budget.py` measures, compressed (gzip level 6), what each page loads before it is ready. `build.py` runs it and stops when a page is over its budget.

- **Declared in `dictionary_src/routes.json`:**
  - `first`: the data files a page fetches before it is ready.
  - `later`: the data files it fetches on its own right after (the 3D view's trips, the area profile's other fields).
  - `on_use`: the data files it fetches after it is ready, the first time a visitor needs them (the map's index of the dictionary, the dictionary's detail files). `budget.py` reports them as "on first use" and does not budget them.
  - `budget.py` names the largest `later` and `on_use` file of each page.
  - `external`: the compressed size of each library from another host.
  - `deferred` (since 2026-10-23, `docs/basemap.md`): the scripts and styles a page adds by itself once it is ready, which are not in its HTML. Today: the base map of the 2D map and of the WCRP page (`js/core/basemap.js`, MapLibre GL JS 4.7.1 and its stylesheet from cdnjs, and the vendored MapLibre GL Leaflet). `budget.py` reports them as "base map after ready" against `deferred_kb` (200 KB), never in the first load: 187.1 KB, of which MapLibre is 171.1 KB (the same file the 3D view loads, so a visitor's cache serves both).
  - Scripts and styles come from the page's HTML.
- **Counted as scripts:** the page's scripts, the libraries from other hosts and the Spanish bundle. Spanish is the first language, so its bundle always counts.
- **Reported but not budgeted:** HTML, styles, fonts, images and the map tiles.
- **Budgets:**
  - The map's budget is the plan's target for the landing view: 250 KB of scripts and 250 KB of data.
  - Each other page's budget sits 10% to 25% above its size on 2026-10-15. Growing past it is then a decision, not an accident.
- **The registry:** `registry.json` now gives each file's compressed size (`gzip_bytes`) and the pages that load it without a click (`loaded_by`).

| Page | Scripts (KB) | Data before ready (KB) | Data just after (KB) | Budget (scripts / data) |
|---|---|---|---|---|
| Map (`index.html`) | 240.0 | 165.4 | 0 | 250 / 250 |
| 3D (`3d.html`) | 612.7 | 541.8 | 325.1 | 700 / 600 |
| Area profile | 96.8 | 588.3 | 0 | 120 / 660 |
| Housing | 159.7 | 304.2 | 0 | 180 / 350 |
| Data dictionary | 27.7 | 652.9 | 0 | 40 / 720 |
| WCRP (`wcrp.html`, branch `wcrp-area`, 2026-10-17) | 65.3 | 307.6 | 0 | 75 / 350 |

`budget.py` also lists any published file above 5 MB compressed. That is the plan's line for moving a layer to PMTiles or Parquet. Since November 2026 one passes it: `soils.geojson` (5.4 MB compressed), which loads only when the Soils layer is switched on; it is accepted as it is for now, and is the first candidate for PMTiles.

## What item 13 changed

- **Map: the chat loads on first use.** `chat.js` is about 40 KB compressed. The map now carries a small starter, `chatboot.js`, which puts in the "Ask" button and loads the chat the first time someone presses it, a suggested question or an "Ask the observatory" button.
- **Map: Chart.js loads on first use.** It is about 60 KB compressed. It now loads the first time the workbench's Scatter or Trend view opens, which says "Loading the chart…" until it arrives.
- **Map scripts:** together these take the map's scripts from about 340 KB to 240 KB, inside the plan's budget.
- **3D view: the places arrive after the first paint.** The tourism places are about 2.2 MB compressed (2.8 MB until 2026-10-18, when the street addresses and websites were removed). The view no longer waits for them: the island, the municipalities and the transit routes draw first, then the places are fetched.
  - The count beside the layer says "loading…" until they arrive.
  - The layer keeps its place in the drawing order: above the municipalities, their columns, the hazard layers (flood, protected areas, land use, comunidades, sea-level rise) and the base map's labels; under the routes, stops, WCRP pins and plans.
  - The route planner waits for them; the place search finds places once they have arrived.
- **Already done before item 13:** the 2D map loads the places, land use, flood and roads only when their layer or tool is used. The plan's "3.0 MB first load" no longer applies to the map.

## Spanish for the parts that load on first use (2026-10-16)

The map's startup scripts had reached 250 of their 250 KB. Part of that was Spanish for parts of the map that load only on first use: the Scenarios and Study areas views, the land-use analysis and the barrio shading. Each now has its own bundle, `site/i18n/es.map.<module>.js`, which loads with its scripts (`docs/i18n.md`, "modules").

**Sizes:** gzip level 6, measured on files with LF line endings, as git stores them. A Windows checkout with `core.autocrlf` gets CRLF line endings, which add about 0.5 KB to the map's scripts. Main measured 250.1 KB that way and 249.6 KB with LF.

| | Before (main, 9b73e59) | After |
|---|---|---|
| Map scripts (`budget.py`) | 249.6 KB | 245.7 KB |
| `es.map.js` | 54.6 KB, 1,836 strings | 49.8 KB, 1,703 strings |
| Module bundles, each loaded on first use | none | scenarios 2.5 KB, study areas 2.8 KB, land use 0.8 KB, barrio shading 0.5 KB |
| `i18n.js` + `economy.js` + `app.js` | 57.4 KB | 58.3 KB |

The other pages change only by the 0.4 KB that `I18N.load()` adds to `i18n.js`.

**Slow 4G** (`throttle.js`, two runs each, map in Spanish): the map transfers 617 and 567 KB from the site, against 621 and 572 KB before. It is ready at 5.1 and 4.9 s, against 5.0 and 4.8 s before. (These runs came before the review fixes, which add 0.3 KB.) That difference is within the variation between runs: 5 KB takes about 0.03 s at 1.6 Mbit/s. The gain is headroom under the budget, not speed.

`throttle.js` exits 2 both before and after, for a reason this change does not touch: the area profile fetches `gateway_series.json` before it is ready, and `routes.json` does not list it.

## The WCRP page and the small maps (2026-10-17, branch `wcrp-area`)

The WCRP area (`wcrp.html`, `docs/wcrp.md`) adds a route to `routes.json` and 14 barrio datasets to the Economy tab. To keep the map's startup scripts from growing, `core/minimap.js` (1.5 KB compressed), which on the map page only the workbench's **Small multiples** view uses, now loads the first time that view opens ("Loading…" until it arrives); the area profiles still load it with the page.

| | Before (`knowledge-area`, a3166fe) | After |
|---|---|---|
| Map startup scripts (`budget.py`, LF copy) | 246.0 KB (251,952 bytes) | 245.2 KB (251,095 bytes) |
| Map data before ready | 169.9 KB | 170.5 KB (`catalog.json` indexes 17 more entries) |
| WCRP page | — | 64.1 KB scripts (budget 75), 307.6 KB data (budget 350), of which `barrios.geojson` is 265 KB; `wcrp_rvi_inputs.json` (76 KB) loads with the first pop-up |
| Economy tab, on first opening | — | + `wcrp_rvi_barrio.json`, 31 KB |

**Slow 4G** (`throttle.js`, this computer's headless Chrome on its own port, Spanish):
- Map, three runs each: ready at 4.8, 4.8 and 4.7 s before, 4.8, 4.8 and 4.8 s after; 568 and 567 KB from the site. No change beyond run-to-run noise (one earlier "after" run at 6.7 s was not repeated in three more).
- Housing, two runs each: 4.5 s before, 4.2 s after (the page itself only gained a tab).
- WCRP, two runs: ready at 3.4 and 3.5 s (the legend drawn), 668 KB transferred, 514 KB of it from the site.

`throttle.js` now takes `CDP_PORT` (another session's Chrome was holding 9333) and `PAGES=map,wcrp` to measure some pages only.

**After the Social Capital map and the merge of `main` (PR #55)** (`budget.py` on LF copies; `throttle.js`, own headless Chrome on port 9444, Spanish, two runs each):

| | `main` (005f575) | `wcrp-area` |
|---|---|---|
| Map startup scripts | 247.2 KB | 246.3 KB |
| Map data before ready | 171.2 KB | 171.8 KB (`catalog.json`: the 18 WCRP entries, less the shorter index rows) |
| Map on Slow 4G | ready 5.0 and 4.8 s; 798 and 748 KB | ready 4.9 and 4.7 s; 795 and 745 KB |
| WCRP page | — | 65.3 KB scripts, 307.6 KB data; ready 3.4 and 3.4 s, 670 KB (517 KB from the site) |
| WCRP Social Capital section, on approach | — | 74 KB (script 7.3, Spanish 3.2, `wcrp_social.json` 11.9, the four count files 18.5, the default points 33.4); Comunidades Especiales + 149 KB and protected areas + 414 KB when switched on |

`catalog.json` had reached 207,926 bytes with both branches' entries, over the 204,800 (200 KiB) the landing allows (`tests/test_catalog.py`). An index row now writes `null` for `domains` when it is just `[domain]` (562 of 808 rows); `catalog.js` reads it back. The file is now 200,303 bytes (32 KB compressed).
**After the merge of `main` with PRs #58 to #62 (2026-10-18).** Main's make-room change (PR #59) now loads `core/minimap.js` with `workbench.js` on first use, so the branch's own lazy load of `minimap.js` was dropped in the merge. Measured on LF copies: map startup scripts 235.3 KB (main 234.8), map data 145.5 KB (145.4), WCRP page 70.0 KB scripts and 308.6 KB data; the dictionary's data, 727.2 KB (main 714.6), is over its 720 KB budget, so the held branch raises that budget to 735 KB (`docs/wcrp.md`, "Page weight" and decision 6). Slow 4G figures are in `docs/wcrp.md`.

**After the merge of `main` with PRs #63 and #64 (2026-10-18).** Main's split of the dictionary (PR #64, below) leaves room: with the WCRP entries the dictionary page loads 490.7 KB of data before it is ready (main 480.2), so the branch's raise of the budget to 735 KB is removed and the budget is 720 again. The area profile leaves `wcrp_rvi_barrio.json` out of both its first and its later files (`LEFT_OUT` in `profile.js`). Figures in `docs/wcrp.md`, "Page weight".

**The WCRP page in plain language (2026-10-19, branch `wcrp-plain`).** The Social Capital map is now the page's first map and loads with it; the vulnerability map (`wcrp_vuln.js`, its Spanish and `barrios.geojson`) loads on approach, as the Social Capital section did before. Data before ready falls from 308.6 to 125.2 KB; scripts rise from 77.0 to 79.5 KB (budget 80, not raised). Slow 4G, three runs each in one session: 514 KB transferred and ready in 3.7 to 3.8 s, against 685 KB and 3.9 s on `main` (details in `docs/wcrp.md`, "Page weight").

**The dictionary in Spanish (PR #10, 2026-10-21).** The Spanish of `dictionary_src/es/` is in files that only the Spanish page reads: `dictionary_list_es.json` (92.3 KB compressed: names, labels, source cards, area texts, the search words of "how to read it", the held entries), fetched after the first paint of the ready page ('later'), and `dictionary_detail_<domain>_es.json`, fetched with the detail file of the same domain ('on_use'). Until it is in, the page shows the English; then it draws the list and the sources again with the same entries open and the same element at the same place (0 px moved in the browser check). Measured on LF copies: data before ready 552.0 KB (main 551.1; budget 720), scripts 32.5 KB (main 31.2), detail files on first use 680.7 KB with the Spanish ones (main 613.6). Slow 4G (`throttle.js`, six runs, median): in Spanish ready at 4.8 s (main 4.9), 874 KB transferred by 1.6 s after ready with the Spanish file (main 780); in English ready at 4.7 s (main 4.9) and 773 KB (main 771, +0.3%). In Spanish `first` and `later` match `routes.json`; in English the page fetches no Spanish file, so the run reports that `later` (the Spanish file) was not fetched, as expected. A first trial that put the Spanish in `dictionary_list.json` cost every page +84 KB and the Spanish page 0.8 s.

## Making room in the map's first load (2026-10-18)

The map's startup scripts were at 249.1 of their 250 KB and `catalog.json` at 204,646 of the 204,800 bytes its test allowed, so a branch that adds datasets could not fit. Nothing was removed: parts of the map that only run after a click now load on first use, as the chat, Chart.js and the Scenarios view already did.

**What moved:**
- **The index of the dictionary** left `catalog.json`. `catalog.py` now writes three files:
  - `catalog.json`, read first: the domains, their headline figures and trends, and the weight of every file.
  - `catalog_index.json`: one row for each dictionary entry, and the data sources behind them. The map fetches it the first time the Catalog tab opens or a card sends you there, the chat loads or answers, or the Economy tab loads (the dataset window's buttons for areas below the municipio come from it). The area profile fetches it with its first load. `withIndex()` in `common.js` fetches it once for every part of the page.
  - `catalog_es.json`: the words of each entry's Spanish summary, which the Catalog tab of a Spanish page fetches with the index, so a search for "pobreza" finds the entries whose summary says it.
  - `routes.json` lists the two files under the map's `on_use`, so `budget.py` still counts them.
- **Workbench views:** Scatter, Trend, Correlations, Small multiples, Compare two maps and the Composite builder are in `site/js/workbench.js`, which loads with `core/minimap.js` and its Spanish the first time one of them opens. The Inspector and Table views and the composite's dataset (so a link with `#ix=` is restored at once) stay in `economy.js`.
- **Help texts:** the texts of the map's help buttons are in `site/js/help.js`, which loads with its Spanish the first time a help button is pressed, as the public facilities' texts already did.
- **Spanish:** the strings of these parts moved to their own bundles (`es.map.workbench.js`, `es.map.help.js`), and the Spanish names of entries that are not series labels to `es.map.catalog.js`, which loads with the index.

**Sizes:** gzip level 6, files with LF line endings (`git archive` of the tree), `budget.py`.

| | Before (main, 434e21d) | After |
|---|---|---|
| Map scripts (`budget.py`) | 249.1 KB | 233.7 KB |
| Map data before ready | 173.3 KB | 145.4 KB |
| `catalog.json` | 204,646 bytes, 33.5 KB compressed | 18,511 bytes, 5.7 KB compressed |
| `catalog_index.json` (on first use) | (in `catalog.json`) | 186,184 bytes, 28.1 KB compressed |
| `catalog_es.json` (on first use, Spanish) | none | 119,447 bytes, 30.3 KB compressed |
| `es.map.js` | 51.7 KB | 45.3 KB |
| `economy.js` / `app.js` | 26.7 / 26.8 KB | 20.6 / 24.4 KB |
| Loaded on first use | | `workbench.js` 7.9 KB, `help.js` 3.4 KB, `core/minimap.js` 1.5 KB; Spanish: workbench 2.6 KB, help 5.4 KB, catalog names 0.6 KB |
| Area profile: scripts / data before ready | 101.8 / 610.3 KB | 95.8 / 610.5 KB |

The area profile's Spanish bundle is smaller too (50.0 to 43.6 KB): it shared the scopes whose strings moved. The 3D view, Housing and the dictionary change by 0.2 to 0.5 KB (`common.js`, `i18n.js`, the dictionary's text about these files).

**Size tests** (`tests/test_catalog.py`): `catalog.json` at most 32 KB (10 KB compressed) and with no index; `catalog_index.json` at most 256 KB (40 KB compressed); `catalog_es.json` at most 160 KB (44 KB compressed since 2026-11-18, when the degrees entries took it to 40.1 KB). Each has room for a few hundred more entries.

**Slow 4G** (`throttle.js`, two runs each, pages in Spanish):

| Page | Transferred from the site before → after (KB) | Ready before → after (s) |
|---|---|---|
| Map | 624, 575 → 581, 531 | 4.9, 4.9 → 4.8, 4.7 |
| 3D | 823 → 823 | 17.3, 17.7 → 17.3, 17.6 |
| Area profile | 895 → 889 | 5.7, 5.7 → 5.7, 5.8 |
| Housing | 554 → 554 | 4.3, 4.2 → 4.4, 4.3 |
| Data dictionary | 903 → 904 | 5.7, 5.7 → 5.8, 5.9 |

`throttle.js` exits 2 before and after for the same reason as on 2026-10-16: the area profile fetches `gateway_series.json`, which `routes.json` does not list.

## Making room on the dictionary and the area profile (2026-10-18)

The dictionary page loaded 714.6 of its 720 KB of data before it was ready, and the area profile 638.4 of its 650 KB, so a branch that adds entries or datasets could not fit (the held WCRP branch needs about 13 KB more on the dictionary page). Nothing was removed: what the first view does not show now loads after it, as on the map.

**The dictionary page.**
- `dictionary.json` stays the whole dictionary, for anyone who downloads it and for `catalog.py`, `contract.py`, `build.py` and the tests. The page no longer reads it. `dictionary.py` makes two kinds of smaller files from it (`page_files`):
  - `dictionary_list.json`, read first: the domains, the sources, the glossary, the area texts and, for each entry, what the list, the filters and the search need (name, domains, group, kind, unit, years, sources, files, margins of error), the first sentence of its summary in English and Spanish, and the words of the rest of its text.
  - `dictionary_detail_<domain>.json`, one for each top-level domain: the rest of each entry (the whole summaries, definition, method, how to read it, cautions, codes, geography, type, related entries, where it appears). The page fetches a domain's file the first time one of its entries is opened, by a click, a deep link (`dictionary.html#entry.id`) or "Expand all". The entry says "Loading the entry…" until it arrives; if it fails, the entry says so and opening it again tries again.
- **Search:** it used to look in the whole text of each entry (summaries in both languages, definition, method, geography, source notes, how to read it, cautions). The list file holds the words of that text instead, as the search sees them (no accents, lower case), without a word that is part of a longer one. A word typed has no space, so it is part of the text exactly when it is part of one of those words: the search finds the same entries in the same order. `tests/dictionary_page.test.js` checks this on every entry, with the first sentences and the split of every field.
- **Export and print:** "Download the dictionary (CSV)" fetches the detail files still missing first (the button says "Preparing the download…"). Printing cannot wait for a fetch, so the page reads the missing files before it prints (a synchronous request, only then).
- `routes.json` lists `dictionary_list.json` under `first` and the eight detail files under `on_use`. `tests/test_dictionary_page.py` checks that the published files are what `dictionary.py` makes from `dictionary.json`.

**The area profile.** It drew every field at once, after every file of `js/core/datasets.js` had arrived. It now draws twice:
- first, the title, the map, the similar municipios and the first field (Housing), with the files they need: the economy and housing series, exposure, facilities and conditions (`FIRST` in `profile.js`). Below it the page says "Loading the other fields…", and "Download CSV" waits for them;
- then it fetches the other thirteen files, adds every dataset again in the order of `datasets.js`, and draws every field. What it shows is what it showed before.
- `tests/profile_first.test.js` checks, for each of the 78 municipios, that the first field and the similar municipios are the same with the first files as with every file. When a Housing dataset moves to another file, the test fails until that file joins `FIRST`.
- `routes.json` lists the thirteen files under `later`, with `gateway_series.json`, which the page always fetched but the list left out: `throttle.js` now exits 0.

**Sizes:** gzip level 6, files with LF line endings (`git archive` of the tree), `budget.py`.

| | Before (main, abd177e) | After |
|---|---|---|
| Dictionary: data before ready | 714.6 of 720 KB | 480.2 KB |
| Dictionary: on first use | none | 591.4 KB in 8 files, one domain at a time: system 192.5, economy 151.5, infrastructure 91.1, housing 53.7, environment 52.9, population 23.1, health 16.7, education 9.9 |
| `dictionary.json` (not read by any page) | 708.1 KB | 708.5 KB |
| `dictionary_list.json` | none | 473.3 KB (1.97 MB raw: the search words are most of it) |
| Dictionary: scripts | 28.8 KB | 29.8 KB |
| Area profile: data before ready | 638.4 of 650 KB | 538.8 KB |
| Area profile: data just after | 0 (and `gateway_series.json`, 3.4 KB, uncounted) | 103.1 KB in 13 files |
| Area profile: scripts | 96.5 KB | 97.4 KB |
| Map: scripts / data before ready | 234.8 / 145.4 KB | 235.0 / 145.5 KB (`datasets.js`, `catalog.json`) |

The published files grow by 4.6 MB raw (the list and detail files repeat what `dictionary.json` holds): 76.3 MB in all, 7.6% of the 1 GB Pages limit.

**Slow 4G** (`throttle.js`, two runs each, pages in Spanish):

| Page | Transferred from the site before → after (KB) | Ready before → after (s) |
|---|---|---|
| Map | 532, 532 → 533, 533 | 4.7, 4.6 → 4.6, 4.6 |
| 3D | 824 → 824 | 17.4, 17.1 → 17.0, 17.3 |
| Area profile | 918 → 919 | 5.8, 5.8 → 5.0, 5.0 (first field); every field 5.8, 5.7 → 5.8, 5.8 |
| Housing | 554 → 554 | 4.2, 4.2 → 4.2, 4.2 |
| Data dictionary | 918 → 686 | 5.6, 5.6 → 4.4, 4.4 |

On the same connection, the first entry opened in a domain takes 0.5 s (Housing) to 1.2 s (System, the largest file) to fill in; the others in that domain open at once. "Every field" on the profile was measured with the same throttle by waiting for the loading note to go. `throttle.js` exits 2 on main (the profile's `gateway_series.json`) and 0 on this branch.

**Unchanged on screen:** main and this branch were compared in a headless Chrome, in Spanish and English, at 1,400 and 390 px: the dictionary (the whole page, 12 searches in both languages, 5 entries opened, 3 deep links (one by an old id), the `?licence=` filter for three classes, "Expand all", the CSV export, a series CSV and printing) and the profile (San Juan, Adjuntas, Culebra, a barrio code and a tract code, which show San Juan as before, the municipio picker and the CSV). The text is the same, apart from what this change writes: the published-files table and its counts (the nine new files), and four dictionary entries that describe these pages and files. No console errors, and `I18N.missed` is empty.

## The in-page glossary (2026-10-19, branch `glossary-highlight`)

The highlighter (`site/js/core/glossary.js`, `docs/glossary.md`) loads after each page is ready, so it adds only its loader to the budgeted first load: `common.js` grows by 0.25 KB compressed, the dictionary's `dictionary.js` by 17 bytes. Measured on LF copies of main (b7c4995) and of the branch:

| Page | Scripts, main → branch (budget) |
|---|---|
| Map | 243.3 → 243.5 (250) |
| 3D | 640.0 → 640.3 (700) |
| Area profile | 99.0 → 99.2 (120) |
| Knowledge Area | 164.1 → 164.3 (180) |
| WCRP | 79.6 → 79.8 (80) |
| Data management | 30.0 → 30.2 (35) |
| Dictionary | 30.8 → 31.0 (40) |

- **After ready (`later`):** the script (13.6 KB), its Spanish module (0.6–0.7 KB) and `glossary_forms_es.json` (4.4 KB). The loader waits until the page has fetched its data, its own `later` files included, and, on the pages that mark the moment they are ready (map, 3D, WCRP, data management), for that mark: `netBusy` does not count the 3D view's map style, tiles and terrain, and with slow tile hosts the forms used to come about 30 s before the 3D view was ready (fixed 2026-10-20; with tile requests delayed 8 s on Slow 4G, main fetched the forms at 7.0–7.5 s against ready at 40.5 s, the fix at 43.2 s).
- **On first use (`on_use`):** `glossary_defs_es.json` (30.3 KB), the first time a reader points at a word. The dictionary page fetches neither file: it reads the glossary it already has.
- **Slow 4G** (3 runs each, on main cbd20cd): the map is ready at 4.7 s on both, the 3D view at 16.8–16.9 s on main and 16.5–16.6 s on the branch, the dictionary at 4.7 and 4.8 s. The underlines are in at 6.1–6.2 s on the map, 5.4–5.6 s on the dictionary and about 26 s on the 3D view, which waits for its trips and first map tiles. `docs/glossary.md` has the details.

## Spanish that loads on demand: the WCRP page and the map's About tab (2026-10-21, branch `make-room-3`)

The WCRP page's scripts were at 79.9 of their 80 KB budget, and the map's at 245.5 of 250 KB. The project lead (2026-10-21): data and text can load on demand. Nothing the first view shows moved, and no budget changed. `i18n.py` can now leave text that only a module shows out of a page's Spanish bundle (`docs/i18n.md`, rule 15):

- **WCRP, the RVI input labels and the landslide notes** (`wcrp_rvi_barrio.json` `method.*`, `landslide_barrio.json`) now load with the vulnerability map's Spanish (`es.wcrp.vuln.js`), the only part of the page that shows them. Before, they came with the page bundle (`data_labels` `"modules"`).
- **WCRP, the facility layer texts of `core/facilities.js`**: the page does not load that script, so the page now takes from the `facilities` scope only the keys `wcrp_social.js` names (`"pick"`).
- **Map, the About tab's text** (module `about`, `es.map.about.js`) loads the first time the tab opens. Until it is translated, the tab's content stays hidden, so English never flashes.

`core/knowledge.js` stays in the first load: it draws the Knowledge Area tabs before the first paint, and loading it later would move the tabs.

**Sizes** (gzip level 6, LF copies from `git archive`, `budget.py`):

| | `main` (14b0e2d) | this branch |
|---|---|---|
| WCRP scripts | 79.9 KB (`es.wcrp.js` 15.4 KB) | 75.6 KB (`es.wcrp.js` 11.2 KB); budget 80 |
| WCRP vulnerability map's Spanish, on approach | 6.7 KB | 9.2 KB |
| Map scripts | 245.5 KB (`es.map.js` 47.0 KB) | 240.0 KB (`es.map.js` 41.1 KB); budget 250 |
| Map About tab's Spanish, on first opening | — | 6.7 KB |

The other pages are unchanged: 3D 645.4, area profile 99.5, Housing 164.4, data management 30.5, dictionary 31.2 KB of scripts. No data list changed.

**Slow 4G** (`throttle.js`, three runs each in one session, headless Chrome on its own port, Spanish, `PAGES=map,wcrp`): 

- **WCRP:** 530 KB transferred (376 KB from the site). On `main`, 534 KB (381 KB). Load at 2.8 s, ready at 3.2 to 3.3 s, the glossary at 4.1 s: the same as `main` (2.8, 3.2, 4.1 to 4.2 s).
- **Map:** 737 KB (559 KB from the site), against 742 KB (565 KB) on `main`. Ready at 4.7 to 4.8 s on both. One run of the branch counted 786 KB, as files still arriving within the 1.6 s window.

The first and later files match `routes.json` on both pages.

**Unchanged behavior, checked:** the browser tests (`wcrp_page.js` 90 checks; `active_layers.js`, `ask_chat.js`, `click_order.js`, `glossary.js` and `datamgmt_page.js` all pass), `I18N.missed` stays empty after the modules load, and the About tab gets the same 33 glossary marks as on `main`.

## Make room 4: the Economy tab and the 3D animation load on use (2026-10-29, branch `make-room-4`)

A colleague (2026-10-29): before adding layers, move what the first view does not show to "load when used". The map's scripts were at 247.6 of 250 KB and the 3D view's at 676.6 of 700 KB. No budget changed.

- **Map, the Economy tab.** Its engine (`core/time`, `format`, `normalize`, `reliability`, `engine`, `adapters`, `datasets`, `composite`, `popup`, `panel`) and `economy.js` load the first time the tab opens, or at start when the address carries an Economy view (`e=`, `ix=`, `sc=`, `wb=`, `wc=`). `js/econ_shell.js` stands in for `window.ECON` until then: other scripts (the chat, the catalog, the workbench) call the same `ECON.api`; a call that needs data loads the tab first, and the ones that only read state get an empty answer. The Spanish of the tab is the module `economy` of the map (`es.map.economy.js`, 21.4 KB); 17 strings the startup scripts also use moved to the page bundle. `core/stack.js` reads `reliability` when it draws a legend, not when it loads. The 3D view and the Ask page read `es.map.economy.js` beside `es.map.js` for the names of the datasets.
- **3D, deck.gl** (356 KB, the largest part of the view) draws only the animated layers (vehicles, storm tracks, service in the hour, a route profile), so `twin3d.js` adds it once the view is ready, with the same file and integrity; `routes.json` lists it under `deferred` with a 400 KB line. Until it arrives, `renderDeck` has nothing to draw and a click finds no deck.gl object.
- **3D, the time series panel and transit supply.** `series3d.js` loads at the first "Time series" link or automatic opening (`window.Series` is a stand-in until then); `supply3d.js` with the Time or Route tab, or the first use of the timetable day, the service layers or the expired-timetable box, which then gets its change again. `transport.json`, `transit_supply.json` and `operators.json` moved from `first` to `on_use`: the search, the stops, the transfer layer and the planner already fetch them when used.

**Sizes** (gzip level 6, `budget.py`, Windows working copy with CRLF; CI's LF copy is slightly smaller):

| | before | this branch |
|---|---|---|
| Map scripts | 247.6 KB | 185.0 KB after merging main on 2026-11-10 (184.7 before); budget 250 |
| Map Economy tab, on first opening | n/a | about 63 KB of scripts and 21.4 KB of Spanish |
| 3D scripts | 676.6 KB | 315.0 KB after merging main on 2026-11-10 (307.5 before); budget 700 |
| 3D libraries after ready | n/a | 356.3 KB (deck.gl); line 400 |
| 3D data before ready | with `transport.json`, `transit_supply.json`, `operators.json` | 336.4 KB; budget 600 |

**After merging `main` on 2026-11-11** (95 commits; `budget.py` on an LF worktree): map scripts 186.9 of 250 KB (main: 249.7); 3D scripts 321.9 of 700 KB, deck.gl 356.3 of 400 after ready; 3D data before ready 325.6 of 600 KB. `throttle.js` (Slow 4G, own headless Chrome, Spanish, two runs each): the map is ready at 3.9 and 3.6 s (main 4.2 and 3.9 s), the 3D view at 13.9 and 14.7 s (main 16.8 and 17.7 s); the 3D view's first files no longer include `transport.json`, `transit_supply.json` or `operators.json`. Both exit 2 for a reason this branch does not touch: the 3D view fetches `buildings_gap.pmtiles` before it is ready and `routes.json` does not list it. Code `main` added since needed the engine at start in four places, now fixed (HANDOFF.md, "Make room 4"). Checked in the browser on the merge: the first view without the engine; the Analysis tab (ready in about 300 ms); Explore's "Show on the map"; Ask; Rankings; Map tools' workbench buttons; links with `e=`, `ix=`, `wb=`, `wc=`, `sc=` and an old `s=`, against `main` on a second server; Spanish with `I18N.missed` empty; the 3D Time and Route tabs, the timetable day, Service at this hour, a `suproutes` link and the time series panel, with deck.gl out of the Tab order.

**Checked in the browser** (local server; es and en): the map starts without the Economy scripts; the tab opens in about 250 ms with a loading note; `ECON.api` answers before and after (334 datasets); links with `e=` open the tab. The 3D view is ready at 4.1 s and deck.gl starts then, with the vehicles running; the Time tab loads supply (the day buttons and the service layer work); an address with `suproutes` draws the layer; a "Time series" link opens the panel for San Juan. No console errors.

## Measured on a slow connection

`tests/browser/throttle.js` loads each page in a headless Chrome with its own profile:
- **Network:** Lighthouse's Slow 4G figures (150 ms round trip, 1.6 Mbit/s down, 750 kbit/s up).
- **Cache:** off, so every load is a first load.
- **Server:** `tests/browser/serve_gzip.js` serves the site with gzip, as GitHub Pages does.

**What it records:**
- The bytes transferred from every host. The map tiles and the libraries come over the real internet, throttled.
- When the load event fired.
- When the page was ready, by its own sign:
  - map and 3D: the loader is gone;
  - profile: the first field is drawn;
  - Housing and dictionary: the snapshot label is filled in.
- For the 3D view, when the places were drawn.
- Which data files were fetched before and after ready. It compares this with `routes.json` and exits 2 when they differ.
  - The script logs each data file's `fetch()` call in the page, on the page's own clock. The map and the 3D view set `performance.mark('ready')` where they hide the loader, and the script notes where that mark falls in the list of calls, so before and after are decided by order, not by time (the page clock is rounded to 0.1 ms, so a call in the same step can share the mark's timestamp): files asked for later in that step (the 3D view's trips and hurricanes) count as after. The other pages use a 10 ms poller with 20 ms of slack.

Lighthouse was installed afterward (the project lead, 2026-10-15) and run; see the next section.

## Lighthouse

Lighthouse 12.8.2 (installed with `npm install -g lighthouse@12`) was run once on each page on 2026-10-15, after the 3D view's places were switched off by default.
- **Settings:** the performance category only, at Lighthouse's standard mobile settings. These simulate Slow 4G (150 ms round trip, 1.6 Mbit/s) on a phone whose processor is four times slower than this computer.
- **Pages:** served by `tests/browser/serve_gzip.js`, in Spanish (`?lang=es`).
- **Variation:** one run each, so a score can move a few points between runs.

| Page | Score (0 to 100) | First content | Largest content | Main thread blocked | Layout shift | Bytes |
|---|---|---|---|---|---|---|
| Map | 56 | 3.3 s | 6.1 s | 0.5 s | 0.000 | 708 KB |
| 3D | 34 | 1.8 s | 10.1 s | 17.0 s | 0.015 | 3,789 KB |
| Area profile | 60 | 2.3 s | 6.8 s | 0.3 s | 0.156 | 915 KB |
| Housing | 48 | 2.4 s | 5.6 s | 1.1 s | 0.133 | 706 KB |
| Data dictionary | 63 | 2.3 s | 5.9 s | 0.2 s | 0.195 | 910 KB |

**How to read it:**
- **The map and the 2D pages** are limited mostly by the network: their largest content appears after 5 to 7 s on Slow 4G.
- **The 3D view** is limited by the processor. Drawing the island in 3D (MapLibre and deck.gl) blocks a slow phone's main thread for about 17 s (about 32 s of main-thread work in all).
- **The bytes** include the base-map tiles, which no budget counts.
- **The profile, Housing and dictionary pages** shift their layout while they fill in (shift 0.13 to 0.20; Lighthouse counts above 0.1 as needing work): space reserved for the tables would remove it.

**Run it again:**
```
lighthouse http://127.0.0.1:8045/index.html?lang=es --only-categories=performance --output=json --output-path=map.json --chrome-flags="--headless=new"
```

**Results on 2026-10-15.** Before is main at the merge of item 12; after is this branch. Each figure is the median of two runs; the runs agreed within 0.1 s.

| Page | Transferred before → after (KB) | Ready before → after (s) | Note |
|---|---|---|---|
| Map | 834 → 734 | 5.2 → 4.9 | the chat and Chart.js load on use |
| 3D | 7,212 → 7,475 | 39.1 → 17.0 | the places draw at 40.6 s (39.2 before) |
| Area profile | 864 → 864 | 5.9 → 5.7 | no change |
| Housing | 657 → 657 | 4.6 → 4.6 | no change |
| Data dictionary | 858 → 858 | 5.8 → 5.9 | no change |

The 3D view transfers the same files before and after. The 263 KB difference is `trips.json` (271 KB compressed): in the "before" runs it was still arriving when the measurement stopped, 1.5 s after the places.

**How to run it:**
```
chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run
node tests/browser/serve_gzip.js site 8042
node tests/browser/throttle.js http://127.0.0.1:8042 after 2
```

## Decisions and what is left

- **PMTiles (vector tiles) and Parquet: not adopted now.** Only `soils.geojson` (5.4 MB compressed, since November 2026, loaded on use) passes 5 MB. The next largest are land use (3.3 MB), the road graph (3.3 MB) and the places (2.2 MB since 2026-10-18), and the map loads all three only on use. The tract and block-group series (about 0.5 MB each) load only for a CSV download, so a Parquet reader would add a library for little gain. `budget.py` names the first file that passes the line.
- **3D places off by default (the project lead, 2026-10-15).** The Places layer of the 3D view starts switched off. Its file (about 2.2 MB compressed since 2026-10-18) and the access data (77 KB) load the first time it is switched on, so a 3D visitor who does not use it saves them; what the view downloads by itself after the first paint falls from 3,215 KB to 325 KB (the vehicle replay and the hurricane tracks). The place search lists tourism places once the layer has been switched on.
- **3D: the layers it shares with the 2D map load on first use (2026-10-19, `docs/layers.md`).** Barrios, public housing, the five service layers and the residents far from service start off and load their files the first time they are switched on; stops, taxi stands and the walk rings read `transport.json`, which the view already loads at the start; the facility layers' scripts (`core/facilities.js`, `facilities3d.js`) and their Spanish load with them. The 3D route of `routes.json` lists the view's layer files under `on_use` (the places, the hazard and land layers, the Communities layers and the new ones), so `budget.py` reports them as "on first use"; that figure is not new weight.
- **Knowledge Area tab "Análisis de ruta" (2026-10-21, PR #72, branch `knowledge/route-analysis`; LF copy, gzip 6).** Every Knowledge Area page loads `core/knowledge.js`, so the new area's registry entry adds 53 bytes compressed to each (2,248 to 2,301). The WCRP page loads 81,890 bytes of scripts (79.97 KB), 30 bytes under its 80 KB line, which stays at 80 (on main 81,837); Housing 164.5 of 180 KB. The routes are a data file loaded on demand (`route_compare.json`, 6.5 KB, the page's only first data load, 10 KB line), not embedded in the HTML: the page's scripts are 26.6 of 30 KB and its HTML and styles 20.1 KB. After merging main with `make-room-3` (PR #85) the WCRP page loads 75.7 KB of its 80.
- **Knowledge Area tab "Índice Global de Innovación" (2026-10-23, branch `knowledge/gii`; LF copy, gzip 6).** The page's scripts are 23.5 of 30 KB and its one first data load, `gii_profile.json`, 23.0 of 30 KB (loaded on demand, not embedded); HTML and styles 19.8 KB. The new registry entry adds 115 bytes compressed to `core/knowledge.js` on every area page (2,301 to 2,416); WCRP loads 75.8 of its 80 KB. Slow 4G (`throttle.js`, 2 runs): 254 KB transferred, ready in 1.7 s, the glossary in by 2.6-3.0 s.
- **Object storage:** `registry.py` already warns at 60% of the 1 GB Pages limit. The site is at 7.2%.
- **Not measured:** a phone's own CPU time. The throttle limits the network only.

## The area profile's data budget, 650 to 660 KB (2026-11-10)

On 2026-11-10 the area profile loaded 650.0 of its 650 KB of data before it was ready, mostly the catalog files (catalog.json, catalog_index.json) that grow with every dataset. The Eastern Region baseline layers (illegal dumping sites, municipal routes mapped by FPR) add two datasets and 0.2 KB to the catalog, so the budget is 660 KB. Moving the catalog index after the first view, as on the dictionary page, would give the room back.

**Opportunity Zones 2.0 (decision 103, 2026-11-13).** The two new dictionary entries, the two new datasets in `registry.json` and six glossary terms take the dictionary page's first data to 720.5 KB on an LF copy (main about 719.5), over its 720 KB budget, so the budget is 730 KB; with main's three base-map terms (PR #238) merged in, it is 723.1 KB. The new page `opportunity-zones.html` loads 34.0 KB of scripts and 46.8 KB of data before it is ready (budget 36 and 60 KB), then the tract outlines (`geo/tracts.geojson`, 241 KB) for its map. The map's startup is unchanged: the layer's file (`oz_tracts.geojson`, 60 KB compressed) and the shared facilities script load on first use.

**Connections between municipios (decision 105, 2026-11-13).** No budget changes. On an LF copy: the new page `transit-links.html` loads 32.4 KB of scripts and 20.8 KB of data before it is ready (budget 36 and 40 KB), then `municipios.geojson` and `simulated_links.geojson` for its map (186.9 KB after ready). The two new layers load on first use on both maps (`publicos.geojson` and `simulated_links.geojson`, listed under the 3D route's `on_use`): map scripts 189.6 / 250 KB, 3D scripts 326.9 / 700 KB. The three dictionary entries, three datasets, two sources and three glossary terms take the dictionary page's first data to 728.0 of 730 KB and the area profile's to 654.4 of 660 KB: the next dataset will need the catalog index moved after the first view, or a larger budget.

**Traffic on the main roads (decision 105, step 2, 2026-11-13).** The dictionary page's first data reached 732.5 KB on an LF copy with the seven traffic entries, two datasets and three glossary terms, over its 730 KB budget, so the budget is 740 KB. The layer file `traffic_roads.geojson` is 1,306 KB (276 KB gzip) and loads on first use on both maps (listed under the 3D route's `on_use`). Map scripts 189.7 / 250 KB; area profile 655.0 / 660 KB of data and 119.4 / 120 KB of scripts: the next series needs room made there (the catalog index after the first view, as on the dictionary page).

**Road deaths (decision 105, step 3, 2026-11-13).** The catalog index (`catalog_index.json`, read on first use of the catalog search) reached 40,966 bytes compressed, over its 40 KB test budget, so the budget is 48 KB (`tests/test_catalog.py`); the Spanish words (`catalog_es.json`) are at 38.2 of 40 KB compressed. On an LF copy: dictionary page 735.6 / 740 KB of first data, area profile 655.4 / 660 KB of data and 119.7 / 120 KB of scripts, map scripts 189.7 / 250 KB, connections page 33.5 / 36 KB of scripts and 23.5 / 40 KB of data. The next dataset needs room made on the dictionary page and the area profile first.

**Power plants and transmission lines (decision 104, steps 1 and 2, 2026-11-14).** On an LF copy after main's road deaths (#245), the dictionary page's first data reached 740.4 KB with the two layer entries, five glossary terms and the Power grid group, over its 740 KB budget, so the budget is 750 KB. `power_plants.geojson` (19 KB) and `power_lines.geojson` (62 KB, 19 KB gzip) load on first use on both maps (the 3D route's `on_use`). Map scripts 189.8 / 250 KB. The next dictionary entries need room made on the dictionary page first.

**Federal transportation inventories (decision 105, step 4, 2026-11-14).** On an LF copy after main's Energy page (#248), the dictionary page's first data reached 751.2 KB with the four layer entries, four datasets in `registry.json`, two source cards and five glossary terms, over its 750 KB budget. Listing each layer's fields as one wildcard (`bridges.geojson:*`, as the traffic layer does) saved 0.2 KB, so the budget is 760 KB (`dictionary_src/routes.json`); the page now loads 751.0 KB. This is the fourth raise in two days (720 → 760 KB): the next one should instead make room, for example by loading the source cards or the glossary of `dictionary_list.json` on first use. The four new map layers load on first use (2D: none before ready; 3D on-use files 26); map scripts 190.0 / 250 KB, area profile 656.6 / 660 KB (unchanged by this step). The Data management page loads only `registry.json`, one row per published file: with the four new files it reached 25.1 KB (167 files), over its 25 KB budget, so the budget is 30 KB, room for about 30 more files.

**Energy by municipio (decision 104, step 4, 2026-11-14).** The new series file adds one line to `core/datasets.js`, which every page with the Analysis engine loads, and takes the area profile's scripts to 120.1 KB on an LF copy after main's transportation inventories (#250), even with two duplicated comments in that file removed. The profile's script budget is now 122 KB. Making room on the dictionary page, as the note above asks: the page no longer waits for `registry.json` (24.8 KB compressed) but reads it right after the first paint (`later` in `routes.json`), and the "Any geography" filter, the file count and the files summary fill in then. With the six energy entries the dictionary page's first data is 727.5 of 760 KB (main 751.0 without them). The new files, `energy_series.json` and `energy_barrio.json`, load with the Analysis tab, not before the map is ready (map: 190.2 KB of scripts, 148.1 KB of data).

**Language, nutrition assistance and poverty by age (decision 107, step 1, 2026-11-14).** Four new variables in `population_series.json`, which the area profile reads before it is ready, with their four dictionary entries in the catalog files, take the profile's first data from 656.9 to 663.2 KB on an LF copy, over its 660 KB budget, so the budget is 670 KB. The note of 2026-11-10 still holds: moving the catalog index after the first view would give the room back. The map's startup is unchanged (190.4 KB of scripts, 148.1 KB of data): the series load with the Analysis tab. The dictionary page's first data is 730.4 of 760 KB. With the daytime population file (`commuting_series.json`, 7.7 KB, three datasets of the profile's first field, so it loads with the first files) the profile's first data is 666.8 of 670 KB and its scripts 120.5 of 122 KB; the map is at 190.6 KB of scripts and the dictionary page at 732.1 KB.

**Gap analysis, second pass (decision 105, step 5, 2026-11-14).** The Connections between municipios page gained two figure cards, four table columns, three method notes and their Spanish: its scripts (the page's script and its Spanish bundle, compressed) reached 36.4 KB on an LF copy, over its 36 KB budget, so the budget is 38 KB (`dictionary_src/routes.json`). Its data before ready: 27.6 / 40 KB (`transit_links.json` with the new fields).

**Learn (decision 106, step 1, 2026-11-14).** A new page, `learn.html`, with a budget of 40 KB of scripts and no data file before it is ready: its scripts are 27.2 KB on an LF copy (the lessons' figures are in `js/learn_items.js`, which `learn.py` writes; `docs/learn.md`). The fifth view button, Learn, adds two strings to the Spanish bundle of every page, about 0.1 KB: the Public spending page, at 40.9 of 41 KB, reached 41.0, so its script budget is 42 KB (`dictionary_src/routes.json`). The map's scripts are 190.7 of 250 KB with the link that opens a map tool (`mt=`).

**Room in the area profile (decision 107, step 3, 2026-11-16).** The profile read the whole catalog index (`catalog_index.json`, 42 KB compressed) with its first load, only to group its tables by domain. `catalog.py` now writes `catalog_domains.json` (each entry's domain, 7 KB compressed) and the profile reads that; the index loads on first use, when the chat needs it (`common.js` `withIndex`). The budget stays at 670 KB.

**Learn, step 3 (decision 106, 2026-11-16).** Four more lessons put the Learn page's scripts at about 48 KB on an LF copy, over its 40 KB budget: most of the growth is `js/learn_items.js` (the figures, with the 78 municipios' poverty rates and their class under each of three methods for lesson A4) and the four draw functions of `js/learn_page.js`. The budget became 52 KB (`dictionary_src/routes.json`). Nothing loads on the map: the link map `js/learn_links.js` still loads on first use.

**Learn, step 4 (decision 106, 2026-11-16).** Three more lessons put the scripts at 55.3 KB on an LF copy, over the 52 KB set in step 3: that budget did not leave the room for steps 4 and 5 that its note said. The budget is now 64 KB, measured to hold step 5 (two lessons) as well; most of the growth is the figures in `js/learn_items.js`, the draw functions and their Spanish.

**Room on the dictionary page (2026-11-16, the project lead: "make more room").** The page's first file, `dictionary_list.json`, carried the search words of every entry's long texts (field `w`): 330 of its 750 KB compressed. They are now in `dictionary_words.json` (`dictionary.py` PAGE_WORDS), which the page fetches right after it is ready, like the Spanish list and the registry; until it is in, a search reads names, groups, units, sources and summaries, and the list is drawn again when the words arrive if a search is typed. On an LF copy the page's data before ready fell from 749.7 to 402.1 KB, so its budget is 480 KB instead of 760 KB: the room is kept, not spent by the next raise.

## The area profile's Spanish: only the map strings it uses (2026-11-16, branch `data/climate-series`)

Adding the drought datasets (decision 107, step 5) took the area profile's scripts to 122.2 of 122 KB (LF copy). Its Spanish bundle, `es.profile.js`, was 57.0 of those KB: it held the whole `map`, `transit` and `access` scopes (1,039 strings), most of them map controls the profile never shows.

- **The change:** `i18n_src/pages.json` now lists `map`, `transit` and `access` under the profile's `"pick"`, so the bundle takes from them only the keys the profile's scripts ask for, its HTML shows or its data labels need. 995 keys left the bundle.
- **Kept by hand:** 31 of the 995 appear in data files the profile reads (domain names such as Economy and Hazards, facility names in `facility_exposure_series.json`, a few Spanish proper names). They are now in `i18n_src/es/profile.json`, with the same Spanish.
- **Checked:** `i18n.py --keys profile` finds 0 missing keys. In a browser, in Spanish, none of the 995 strings appears as text, title, label or placeholder on the profiles of Guánica, San Juan, Yabucoa, the Eastern Region and Porta Capital, with every section open; no console errors.
- **Sizes** (gzip, LF copy from `git archive`, `budget.py`): profile scripts 122.2 → 92.7 of 122 KB; `es.profile.js` 57.0 → 27.6 KB. No budget changed.
