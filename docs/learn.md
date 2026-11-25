# Learn: lessons on maps and spatial analysis

The Learn page (`learn.html`, "Aprende" in Spanish) teaches how a map answers a question, with the observatory's own data and tools as the examples. HANDOFF decision 106; the plan, the 17 lessons and the five steps are in `docs/learn-proposal-2026-11.md`. **All five steps are built: the page, all seventeen lessons, the printable workshop guide, the link that opens a map tool, and the links from the map's tools, layers and glossary pop-ups to their lesson.**

| Lesson | Part | What it teaches | Real example |
|---|---|---|---|
| A1 Layers and shapes | Read a map | Points, lines, areas and grids; vector and raster | Tourism places, Watersheds and streams, Barrios, Surface heat |
| A5 Counts and rates | Read a map | A count shows where the most is; a rate shows where it is most common | Tourism places by municipio, as a count and per 1,000 residents |
| B1 How many, how much | Ask a question | Counting by area (a spatial join); the mean against the median | Tourism places by barrio; Count my points |
| B2 What overlaps | Ask a question | An overlay: what falls inside what | Tourism places inside FEMA's flood hazard area and the protected areas |
| B3 What is near | Ask a question | A buffer: a ring at a set distance, and what falls inside | Five distances around the plaza of Ponce; the Area around a point tool |
| B4 How to get there | Ask a question | Network analysis: a walk along the roads beside the ring of the same distance | Walks of 5 to 20 minutes from the plaza of Ponce; the Walking time tool |
| B5 Between measurements | Ask a question | Interpolation, and why the observatory paints no surface between stations | The rain gauges, against Slope and Contour lines |
| B6 Where things concentrate | Ask a question | Equal cells; a concentration is not a hot spot | Tourism places in hexagons of 10 km² |

## The pieces

| File | What it holds |
|---|---|
| `learn_src/lessons.json` | **The registry:** the four parts, all 17 lessons (built or planned) and what the figures read. |
| `learn.py` | Checks the registry and writes `site/js/learn_items.js`. `--check` fails when that file is out of date. `build.py` and the tests run it. |
| `site/js/learn_items.js` | `window.LEARN`: the parts, the **built** lessons and every figure a lesson quotes. Never edited by hand. |
| `site/js/learn_links.js` | `window.LEARN_LINKS`: for each map tool, layer and glossary term, the lesson that teaches it. Written by `learn.py`; see "Links to a lesson". |
| `learn_src/figures.js` | A Node helper that `learn.py` runs: the figures the map's own code must compute (the walk, the hexagons). |
| `site/learn.html` | The page: the lessons' own text, in English, and one card drawing for each built lesson (`<symbol id="lg-<id>">`). |
| `site/js/learn_page.js` | Draws the cards and, in each lesson, "In the observatory": the real figures and the two small demos. |
| `site/css/learn.css` | The page's styles. |
| `i18n_src/es/learn.json` | The Spanish of the page and of the script. The top bar's "Learn" is in `common.json`. |

A lesson is not a Knowledge Area item (it is teaching material, not FPR research), so Learn has its own registry and is not in `knowledge_src/items.json`.

## The registry

Each lesson has:

| Field | Meaning |
|---|---|
| `id` | Short id. Its section is `id="lesson-<id>"` and its card drawing `id="lg-<id>"`. |
| `code` | The part's letter and a number (A1, B3). The cards are ordered by it. |
| `part` | `read`, `ask`, `judge` or `further`. |
| `status` | `built`: on the page. `planned`: in the registry only; nothing about it reaches the site. |
| `title`, `term` | `{ en, es }`: the lesson's name in plain words and the GIS term it teaches. |
| `tools` | `data-mt` codes of the map's Tools › Map tools pane. `learn.py` reads each tool's name from the map's own page and its Spanish from the map's scopes, so a card never names a tool differently from the map. |
| `layers` | `l=` keys of the map's address (`site/js/core/viewstate.js`). |
| `glossary` | Ids of `dictionary_src/glossary.json`. |

`learn.py` fails when: an id or a code is used twice; a title or a term lacks a language; a tool, a layer key or a glossary term does not exist; a built lesson has no section or no card drawing on the page; or the page has a lesson section the registry does not call built. **A card is drawn only for a built lesson** (the rule of decision 97 (d)).

## The figures

**No lesson types a figure.** Each "In the observatory" block is empty in `learn.html` and filled from `window.LEARN.figures`, which `learn.py` computes from the published data files.

| Lesson | Figure | Read from |
|---|---|---|
| A1 | Tourism places drawn (confidence 0.50 or more, no places of worship, with a point) | `places.json` |
| A1 | Stream lines; barrios; municipios | `streams.geojson`, `barrios.geojson`, `municipios.geojson` |
| A1 | Cell size and cells across and down of Surface heat | `heat_surface.json` |
| A2 | The row of the barrio with the most tourism places, and what a join by its GEOID adds from the barrios' survey file (residents, median household income, median age, with margins); how many barrios the join matches; how many names more than one barrio shares | `barrios.geojson`, `acs_barrio.json` |
| A3 | Barrios in municipios; counted places inside a barrio outline, with a point in none, and with neither. The points in no barrio are tested against the municipios' outlines and measured to the nearest barrio outline **with the map's own point-in-polygon code** (`Core.study.inside`, in `learn_src/figures.js`) | `places.json`, `barrios.geojson`, `municipios.geojson` |
| A4 | The newest poverty rate of the 78 municipios in five classes by quantiles, equal intervals and natural breaks, **made by the map's own `Core.classify`** (in `learn_src/figures.js`), and how many municipios change class | `housing_series.json` |
| A6 | The newest five-year window; the poverty rates whose margin of error is above 30% of the estimate (the rule of `Core.reliability`), for the municipios and the barrios; two barrios' rates with their margins | `housing_series.json`, `acs_barrio.json` |
| C1 | The poverty rate of the newest window by municipio and by barrio (barrios only where the margin is within 30% of the estimate): each range, the barrios above the highest and below the lowest municipio, and the municipio whose barrios are furthest apart (its barrios are not named) | `housing_series.json`, `acs_barrio.json`, `barrios.geojson` |
| C2 | Adults with a bachelor's degree against the poverty rate: the 78 municipios as points, and the correlation by municipio and by barrio, **computed by the map's own `Core.stats.correlation`** (in `learn_src/figures.js`) | `housing_series.json`, `acs_barrio.json` |
| C3 | The tourism listings withheld by the privacy rule (`docs/places-privacy.md`), by reason; how many of them the map's basis counts; the barrios with no published median household income | `places.json`, `acs_barrio.json` |
| D1 | What Count my points and Study areas accept, **read from their own code** (`MAX_PTS`, `MAX_FILE`, `MIN_SHOWN` in `js/studyareas.js`; `MAX_AREAS`, `MAX_TEXT` in `js/core/study.js`) | (the scripts, not a data file) |
| D2 | The barrios and municipios layers as published (features and size), and the three parts of Santurce's GEOID | `barrios.geojson`, `municipios.geojson` |
| A5 | Tourism places, residents (2020 Census) and places per 1,000 residents, for the 78 municipios | `municipalities.json` (the rate is the published one, so the lesson and the map agree) |
| B3 | Tourism places, residents and area inside 400 m, 800 m, 1 km, 1.6 km and 5 km of the Plaza Pública de Ponce | `places.json`, `population_blocks.json` |

| B1 | Tourism places by barrio: the total, the mean, the median, the largest, and the barrios in each class of the chart | `barrios.geojson` |
| B2 | Tourism places inside FEMA's Special Flood Hazard Area and inside a protected area, with the five municipios of the largest share | `municipalities.json` |
| B4 | The area and the residents within a walk of 5, 10, 15 and 20 minutes from the plaza, beside the ring of the same distance | `roads.bin`, `population_blocks.json` |
| B5 | The rain gauges: how many, the land for each, and how far apart they are. **Read in the browser** from `rain_gauges.geojson` when the lesson comes near the screen | (not in `learn_items.js`) |
| B6 | Tourism places in hexagons of 10 km²: the hexagons, the fullest, and how few hold half of the places | `places.json` |

Three rules keep them right:

- **Only files the local build writes.** An automated rebuild commits `site/data` and nothing else, so a figure read from a file it writes would go stale behind a bot's pull request. The registry's `figures.inputs` lists what `learn.py` reads, and `tests/test_learn.py` fails if one of them is in a `"where": "ci"` unit of `refresh/sources.json` or if `learn.py` reads a file that is not listed. The nightly transit refresh rewrites two of the files, but not what is read from them: `places.json` (only its transit columns) and `population_blocks.json` (only its fourth column).
- **A4 classifies as the Analysis tab does, for the year shown.** The map cuts its classes from every year at once while "Same classes in every year" is ticked (`E.pool` in `core/engine.js`), so the lesson's three links turn it off (`e=poverty_pct.f.value.blue.<q|e|j>.1.0`): checked on 2026-11-16, the three legends gave the lesson's counts (16/16/15/16/15; 6/17/30/21/4; 6/17/29/22/4). Limits are rounded as the legend rounds them (63.65 shows as 63.6).
- **A6 flags as the map flags.** `learn.py` holds `MOE_SHARE = 0.3`; a Python and a Node test check it equals `Core.reliability`'s.
- **B3 measures as the tool measures.** Distances use the flat projection of `Core.study.ring` (110,574 m to a degree of latitude; 111,320 m × cos(latitude) to a degree of longitude), and the places are the ones the Area around a point tool counts in its summary: every listing that has a point, at any confidence and with the places of worship. So a visitor who opens the tool from the lesson gets the lesson's numbers. Checked on 2026-11-14: 800 m gave 2.0 km², 4,755 residents and 321 tourism places in the tool and in the lesson.
- **A walk moves with its start.** From points 3 m apart on the plaza, a 10-minute walk reached between 2,648 and 3,012 residents (the area is traced in cells of 25 m and a block is in or out). The lesson gives the figure for the plaza's own point and says the tool will come close, not repeat it. The ring of B3 does repeat.
- **B4 and B6 are computed by the map's own code.** `learn.py` runs `learn_src/figures.js` with Node, which calls `Core.study.walkArea` on the road graph of `js/roads.js` (the Walking time tool, 80 m a minute) and `Core.hexbin.bin` (Places in hexagons). `learn.py` and the build therefore need Node, as the tests already do.
- **B5 is read live.** The rain gauges are in a file an automated rebuild writes, so their count cannot be kept in `learn_items.js` (first rule). The page fetches the layer's own file and counts: the figure is always the day's. It is the page's only request, and it sends nothing.
- **The two bases are different on purpose, and the page says which it uses.** Approved by the project lead on 2026-11-17 (decision 106, step-1 choice 3). The map draws and counts tourism places at confidence 0.50 or more without places of worship (A1, A5). The Area around a point tool counts every listing with a point (B3). Around the plaza of Ponce, 800 m holds 230 on the first basis and 321 on the second.

## The link that opens a map tool

`index.html#mt=<code>` opens a tool of Tools › Map tools, where `<code>` is the tool's `data-mt` (for example `mt=b:study:saAroundH` for Area around a point). It is a one-time request like `wb=` (`docs/view-state.md`): `app.js` reads it before the map rewrites its address (`MT_LINK`), opens the pane once the map is ready (`openToolLink`), and the map never writes it back. It runs only when the pane has a button with exactly that code, so a link can start no more than a visitor's own click could. A lesson combines it with `c=` and `l=`: the B3 button opens the map on the plaza with Tourism places on and the tool ready.

## The top bar

"Learn" is the fifth view button of every page: the 10 pages written by hand and the 11 written by a `docs/analysis/*/make_page.py`, each of which now writes the link and lists the `school` icon.

The bar keeps the rule of 2026-11-14 (PR #252): **on a PC, wider than 860 px, every view button says what it is.** A fifth word did not fit on two pages, the map and the 3D view, whose bars also hold a search box and the snapshot date. `site/css/twin.css` makes room there and changes nothing on the other 20 pages:

| On the map and the 3D view | Before | Now |
|---|---|---|
| The page name and the snapshot date come back at | 1,401 px | 1,520 px |
| The line under the name comes back at | 1,520 px | 1,660 px |
| Spanish: the page name comes back at | 1,601 px | 1,660 px |
| Spanish: the snapshot date comes back at | 1,641 px | 1,780 px |
| Spanish: the search box is 150 px, the buttons are tighter and Ask is a round button, up to | 1,180 px | 1,320 px |
| Spanish: the buttons lose their icons below | 1,061 px | 1,121 px |
| Spanish: below 961 px the search box is 90 px and the buttons tighten once more | no such step | new |

Measured on 2026-11-14 with every page in an iframe, in English and Spanish, at 34 widths from 862 to 1,920 px (each width where something enters or leaves the bar, and between them): no bar is wider than its screen, every one of the five buttons shows its word, and the least room to spare is 10 px, on the map in English. A phone (860 px or less) keeps its two rows: the five round icons take 212 px of the second.

## Links to a lesson

Help where people need it (step 2). `learn.py` writes `site/js/learn_links.js` from the registry: each map tool (its `data-mt`), each layer (the key of its "?" button) and each glossary term (its id) points to the first built lesson, in the order of the codes, that names it.

| Where | What a visitor sees | Code |
|---|---|---|
| Tools › Map tools | "Lesson: What is near" under a tool's description | `js/maptools.js`, with `learnLinks()` of `app.js` |
| A layer's "?" | The same link under the help text, on the 2D map and in the 3D view | `app.js` and `twin3d.js` (`#helpLearn` in `index.html` and `3d.html`); `learn.py` reads the help keys of both pages, and the 3D tourism places' key `places3d` |
| A glossary pop-up, on every page | The link above "See in the glossary" | `js/core/glossary.js` (`tipHtml`, `opts.lesson`) |

A fault that was live blocked the second row and is fixed with it: a layer's "?" did nothing until the Analysis tab had been opened, because `js/help.js` used `TK` from `economy.js`, which loads on first use since PR #104. `help.js` now declares its own inside a block, so `economy.js` can still declare the page's.

The file is never part of a first load: the map asks for it the first time a help button is pressed or the Tools pane opens, and the glossary with its first definition. A pop-up or a pane works without it when it does not come. Adding a lesson to the registry adds its links; nothing else is edited.

## What a lesson is made of

1. The question, as a line under the title.
2. The idea in plain words, with a drawing where it helps.
3. **In the observatory:** the figures above, and a small demo where the idea needs movement (A5: count or rate; B3: the distance).
4. **Try it on the map:** one or two buttons that open the live map.
5. **Watch out:** the one mistake people make most.
6. **Check yourself:** two questions answered on the page (`<details>`). Nothing is stored or sent.
7. **Go further:** one outside source, checked when the lesson is written.

Rules (decision 106 (e) and (g)): a lesson states methods and facts, recommends no policy and judges no agency; no example draws or names a private home; no lesson uses a dataset whose Spanish is held for review (`i18n_src/held_for_review.json`). The page keeps its "In review" notice, the AI sentence and `noindex` until the project lead takes them off.

## How to add a lesson

1. Write its section in `learn.html` (`<section class="block lesson" id="lesson-<id>">`), its card drawing (`<symbol id="lg-<id>">`) and its link in the `.toc` bar.
2. In `learn_src/lessons.json`, set its `status` to `built` and check its tools, layers and glossary terms.
3. If it quotes figures, compute them in `learn.py` from files the local build writes, add the files to `figures.inputs`, and draw them in `learn_page.js`.
4. Add every new term to `dictionary_src/glossary.json` in English and Spanish with a source, and the Spanish of the lesson to `i18n_src/es/learn.json`.
5. Run `python learn.py`, `python i18n.py`, `python dictionary.py`, then the tests.

## Checks

- `tests/test_learn.py`: the registry is sound and written; only built lessons reach the site; the rules catch a broken registry; no figure reads a file an automated rebuild writes; the figures agree with the data files; every lesson has its parts; every page and every page generator has the Learn link and its icon.
- `tests/learn.test.js`: `learn_page.js` run on a page of its named elements (the cards in both languages, the figures, both demos, the links); `mt=` is read once, dropped on write and opens only a tool the pane has.
- By hand on 2026-11-14 (headless and in the preview): the page in English and Spanish, the three "Try it" links on a fresh load, and the tool's summary against the lesson's figures.

## Decided in the work, for the project lead's OK

- **"Aprende" (settled).** Step 1 used "Aprender" because the site's Spanish rule (`docs/i18n.md`, "Address") asks for the infinitive on menu items. The project lead chose "Aprende" on 2026-11-16, as decision 106 (a) said; `docs/i18n.md` records the exception.
- **The figures are in `js/learn_items.js`, not `site/data/learn.json`.** Approved by the project lead on 2026-11-17. The proposal named a data file. A script file (as the Knowledge registry does) needs no dataset record, license or ledger entry, and holds nothing that is not already published.
- **Six page generators were behind their pages.** Making the pages again would have set `chatboot.js?v=45` back to 35 or 36 on all six, and on two of them (Inflation, Route analysis) dropped three icons the pages list for the "All areas" menu (`bolt`, `price_change`, `wifi`). The generators now write what their pages already said. A test caught the icons; nothing checks the versions.

## Step 3, decided in the work

- **A real gap in place of a made-up one.** A3 needed an example of points and areas that do not fit. The data had one: 317 counted places have a point in no barrio, and 314 of them lie past the drawn coast, a median of 20 m out (beaches, piers). The lesson teaches with them and says what the build does with them; nothing on the map changes.
- **The Spanish of A4's link sentence names the panel's own words** ("Mismas clases en todos los años"), and A6 says "marks" rather than "hatches", because the barrio legend writes "less reliable" without the word "hatched".
- **Two barrios are named in A6** (the most populous with a published rate, and the one at the tenth of the barrios with the fewest residents): public Census Bureau estimates for public areas, chosen by a rule, not by hand.

## Step 4, decided in the work

- **C1 compares only sure barrio estimates.** With every barrio, the widest spread inside a municipio was 0% against 100%: the noise of tiny samples, which is lesson A6's point, not C1's. The lesson counts a barrio only where its margin is within 30% of the estimate (412 of 885), and says so.
- **C1 names the municipio, not its barrios.** The widest spread (Toa Baja, 32.4%: barrios from 28.9% to 95.6%) is given without the barrios' names, so the page does not single out a poor barrio. A test checks it.
- **C2 uses degrees and poverty** because the relation is strong by municipio (r = −0.73) and weaker by barrio (r = −0.54): it shows that a correlation depends on the areas, and the lesson says neither measure causes the other.
- **C3 counts the privacy rule's withheld listings** (1,005: 971 holiday rentals, 34 units named by an address), with no name or place, and links to no withheld listing.

## The workshop guide (step 5)

The section `#guide` of `learn.html`, after the lessons: a plan for 60 to 90 minutes (A1, A5, B3 and B4, C1 and C2, D1, then C3 and A6), three exercises on the live map, notes for the facilitator, and a one-page handout ("five questions before you trust a map"). It is part of the page, so it switches language with the page and needs no new page, route or generator.

**It prints alone.** The button "Print the guide and the handout" marks the body (`ln-print-guide`) while the browser prints; `learn.css` then hides everything in `main` but `#guide`, and the handout starts a new page. Checked on 2026-11-16 with headless Chrome: two pages, the guide and then the handout, nothing else from the page.

## Step 5, decided in the work

- **The guide is a section of the Learn page, not a separate page.** The plan asked for a printable guide in Spanish and English: the page's language switch gives both, and a separate page would have needed its own top bar, route, budget and Spanish scope.
- **D1's exercise needs no practice file.** A new sample data file would need a dataset record and a license. Instead the exercise draws an area, downloads the tourism places inside it as a CSV from Study areas (which writes `lat` and `lon`) and loads that file into Count my points.
- **D2 recommends EPSG:32161** (NAD83 / Puerto Rico & Virgin Is.) to measure in meters, and says the published files are GeoJSON in longitude and latitude (RFC 7946; `learn.py` fails if a file names another `crs`).

## Not yet

Decision 106 (h): a native Spanish reader reads each lesson, and a person who teaches workshops reads the guide, before the "In review" marker goes.
