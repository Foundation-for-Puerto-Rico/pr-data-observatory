# The layer engine and the shared modules (`site/js/core/`)

Built in plan item 6 (2026-10-06). One set of plain browser scripts now decides how a dataset is read, which year it shows, how it is rescaled, classed, coloured and described, and how a place speaks for it in a legend, a pop-up and a table. The Economy tab, the 2D map's shading menu, the Housing page and the 3D view all use it, so a class has the same colour, a number the same format and a warning the same words wherever it appears. Nothing a visitor could do before has been removed; `tests/browser/` proves it page by page (see "How it is checked").

Everything is plain JavaScript with no build step: each file registers itself on `window.Core.<name>` and can be `require`d in Node, which is how the unit tests run it (`tests/core.test.js`). Language comes from the page (`T`, `Tn`, `Th` in `js/i18n.js`); without a page the modules fall back to plain English, which is what the tests see.

## The modules

| File | What it does | Pages |
|---|---|---|
| `text.js` | the language and number helpers the others use (`T`, `Tn`, `Th`, `num`, `esc`, `lang`) | map, Housing, 3D |
| `palettes.js` | every colour the data layers use: five sequential ramps (blue, green, gold, red, gray), the diverging scale, the 3 × 3 bivariate grid, symbol and line colours, the no-value grey. See `docs/palettes.md` | map, Housing, 3D |
| `stats.js` | median, Pearson correlation, rank, percentile | map, Housing |
| `classify.js` | classes: quantile, equal interval, natural breaks (Fisher-Jenks, thinned above 1,500 values), manual limits, diverging scales; `classOf`; `minFirst` (mostly one value); `single`, `hidden` (how a legend names or leaves out a class); `inner`, `risingStops` (the 3D view's step expression), `parseBreaks` | map, Housing, 3D |
| `time.js` | time types and the year a dataset shows (`resolve`), the years the control offers, the period a legend names (`label`) | map, Housing |
| `format.js` | how a value is written, in full and compact (`1.2K`, `$2.5M`) | map |
| `normalize.js` | the rescalings a dataset offers (`options`), their units (`describe`) and arithmetic (`compute`) | map |
| `reliability.js` | which values are flagged less reliable, and the one wording of each caution. See "Reliability" | map, Housing |
| `engine.js` | the engine itself: datasets, the period each layer shows, classes, colours, symbol sizes, layer links, the contract `series()` | map |
| `adapters.js` | turns each published file into datasets: yearly series, snapshot fields, tourism counts, exposure, derived series, points | map |
| `hexbin.js` | counts points in hexagons of equal area | map |
| `legend.js`, `stack.js`, `popup.js`, `panel.js` | the markup of legends (`legend.js` is shared; `stack.js` is the map's), of the pop-up, hover card and inspector, of a layer's card and of the dataset browser | `legend.js` on the map, Housing and 3D; the rest on the map |

Load order in a page: `text`, `palettes`, `stats`, `classify`, `time`, `format`, `normalize`, `reliability`, `engine`, `hexbin`, `adapters`, `legend`, `stack`, `popup`, `panel`, then the page's own script. A page lists the core files it loads in `i18n_src/pages.json` so the language tool reads their strings.

## Datasets, layers and arrays

A **dataset** is what a published series becomes in the browser:

```js
{ key, label, group, unit, d,                  // identity, unit ('', '%', '$'), decimals
  type,                                        // 'count' | 'total$' | 'level$' | 'rate' | 'ratio' (what a rescaling may do to it)
  family, sources, ref, definition, dictId,    // where it comes from and where its dictionary entry is
  years: { 2024: [78 municipalities..., island] }, ys: [2010, ..., 2024],
  moe: { 2024: [...] },                        // 90% margins of error, same shape as years (optional)
  time: { type, windowYears },                 // 'window' for ACS, 'snapshot' for one date (optional)
  static, noShare, denom, levels, derived, withheld, counted, plain, residents,
  noIsland, noValue, noPerHU, dPer, classes, tag }   // flags a dataset sets for a figure of its own kind (below)
```

**Flags for a figure of its own kind** (all optional; the health datasets use them all): `noIsland` (no value for Puerto Rico as a whole, so no index or difference from it: a score is not added or averaged); `noValue` (what an empty place means, in English: the legend, pop-up, hover card, inspector and table say it instead of a dash, and `E.missing(layer, i)` returns it translated, or `null`); `noPerHU` (no "per 1,000 housing units" view: a count that does not sit on housing); `dPer` (decimals of the per-resident, per-housing-unit and per-km² views, and of the short numbers in a legend, when one is too few); `classes: 'jenks'` (a layer starts with natural breaks instead of quantiles: counts with many zeros, scores with few distinct values; a link that names a class method, or a choice in the panel, wins); `tag` (the word the dataset window shows for the kind of figure instead of the type: "score"); and `counted: false` (administrative counts and federal formula figures: no "fewer than 10 counted" flag).

**Arrays carry the island.** A value for each of the 78 municipalities in the order of `E.geo.ids` and, last, the value for Puerto Rico as a whole (index `E.geo.pr`). A dataset that has finer levels (barrio, tract, block group, hexagon) says so in `levels` (`levels[level] = { ids, ys, series(E, layer, resolved, period) }`) and answers through the contract below. `residents: true` marks the count of the residents themselves (the survey's population): it is not offered per 1,000 residents and starts shaded as people per km². `E.add` sets it on the population denominator (`E.denominators.pop`) too. A link asking for a view a dataset does not offer gets the dataset's own start (`E.restore`, and the Economy tab's link reader).

A **layer** is what a person puts on the map, and holds no data: `{ id, key, mode: 'fill' | 'symbol', norm, ramp, classes: 'quantile' | 'equal' | 'jenks' | 'manual', breaks, fixed, opacity, visible, real, color }`. The shading menu of the 2D map, the Housing page and the 3D view keep their own small state and use the same classification, palettes and legends.

## The contract

```js
const E = Core.engine.create();
Core.adapters.series(E, economy, housing, municipalities);   // adapters register datasets
E.series(layer, period, level)  // -> { ids, names, values, moe, flags, meta } or null
E.values(key, { year, norm, real, base })   // the numbers as a layer shows them: what the chat reads
```

`values` and `moe` are in the order of `ids` and, for the municipality level, end with Puerto Rico. `flags` carries `exact` (the period asked for is the one shown), `early` (the dataset starts after it) and `noValue`. `meta` names the dataset, level, period, time type, unit and decimals, and for a hexagon level the cell area and the method sentence. A level a dataset does not have returns `null`. Everything else (legend, classes, hover, pop-up, workbench, chat) reads a dataset through `E`: `E.resolve`, `E.calc`, `E.breaks`, `E.fillColors`, `E.symbols`, `E.title`, `E.chip`, `E.fmt`, `E.moe`, `E.reliability`, `E.missing`, `E.makeLayer`, `E.encode` and `E.restore`.

## Time

Each dataset declares one time type (`time.js`) and the year control treats it accordingly. A layer shows the year the control names if the dataset has it, otherwise the **latest year at or before it** (flagged in the legend), and if the dataset starts later, its first year ("first data 2014").

| Type | Example | Status in this build |
|---|---|---|
| `period` | calendar or fiscal year (QCEW, USAspending, LAUS) | the default; exact year, else latest at or before |
| `window` | ACS 5-year | **built**: a series made only from ACS tables is a window, and its chip names the whole window ("2020–2024") instead of its last year |
| `snapshot` | tourism places, transit, flood, exposure | **built**: always the current one, "snapshot 2026", not animated |
| `static` | land use plan, boundaries | **built**: always shown |
| `point`, `vintage`, `event` | census 2010 and 2020; population estimates with the 2020 break; storms | declared in `TYPES`, **no dataset uses them yet**. The census/estimate break of population is written in the dictionary (`methods.population_vintage_break`) and each year's basis is in the data (`basis`), but the legend chip does not show it yet |

A mixture (jobs per employed resident is a yearly count over a survey) is not a window, and says only its year.

## Rescaling (`normalize.js`)

A dataset offers the views that make sense for its kind; extensive numbers (counts, dollar totals) are rescaled before they are shaded, because a shaded map of raw jobs would only show which municipality is big.

| Id | Label | For | Blank when |
|---|---|---|---|
| `value` | As published | everything | |
| `shareArea` | % of the area's residents or housing units | exposure counts | the area's own total is missing or zero |
| `per1000` | Per 1,000 residents | counts (not the residents themselves, `residents: true`) | no population |
| `perHU` | Per 1,000 housing units | counts of things that sit on housing (not jobs, not exposure, not housing units themselves) | no housing units (ACS, the latest year at or before) |
| `perkm2` | Per km² | counts and dollar totals | no land area |
| `perCapita` | $ per resident | dollar totals | no population |
| `sharePR` | % of the Puerto Rico total | counts and dollar totals (not federal loans) | the island value is zero |
| `shareJobs`, `lq` | % of the municipality's jobs; location quotient | counts of jobs | no jobs |
| `index`, `diff` | Index (Puerto Rico = 100); difference from Puerto Rico | rates, levels and ratios | |
| `change` | change since the base year | everything that moves | at or before the base year |
| `pctile` | percentile among the municipalities | everything | |

A new shaded count starts as `per1000`, a new shaded dollar total as `perCapita`, an exposure count as `shareArea`, and everything else, including every layer of symbols, as published.

## Classes (`classify.js`)

Five classes for one shaded layer, three for each of two shaded layers together (the bivariate map). Quantile limits take the value at rank `floor(n·i/k)`; a value on a limit belongs to the lower class; with many ties a class can be empty and the legend shows it with a count of zero. **Mostly one value** (`classify.minFirst`, 2026-10-17): when the lowest value fills two classes or more (most places at 0), the first class holds that value alone and the other classes are the quantiles of the values above it, instead of several empty "0 to 0" classes; 64 datasets of the Economy tab start this way, among them the walking and transit access shares, the sea-level and flood exposures and the non-attainment areas. A class of one value is named by it ("0.00%", not "0.00% to 0.00%"), and a legend leaves out a class of one value above the first, because no value can fall in it (`classify.single`, `classify.hidden`). Scales around a centre (index, difference, change, location quotient) are cut at 0.1 and 0.5 of the largest distance from the centre. "Same classes in every year" pools every year of a dataset, so a colour means the same thing in all of them.

**Your own limits.** A layer's Classes menu can be set to "My own limits": four numbers in rising order, separated by commas. It starts from the limits the layer has at that moment, an invalid text falls back to quantiles (the field says so), the limits are kept in the link (`e=…m.…1~2~5~10`), and they apply to a single shaded layer (two layers together use three classes each; a scale around a centre keeps its cut-offs).

## Reliability (`reliability.js`)

Three things make a value less reliable than it looks. The observatory flags each one in the same way on the map, in the legend, in the pop-up and the tables, and on the Housing page.

| Flag | Rule | Why this threshold |
|---|---|---|
| **margin of error** | a published 90% margin above **30% of the estimate**; an estimate of zero with any margin counts. For a change since a base year, either of the two years | 30% is the rule the Housing page has always used; here it is applied everywhere, and zero estimates with a margin (across all years, 299 cells of the Housing series and 242 of the economy series) are now italic there too |
| **small number** | a rate or share built on a count of **fewer than 10** (not zero): `per1000`, `perHU`, `shareJobs`, `shareArea`, `lq` of a count, and a rate whose dataset names the count it rests on (`counted`; `counted: false` opts a dataset out: administrative counts and federal formula figures, such as health centers and shortage areas, are not estimates from a few cases) | a convention, not a statistical test; 10 is the usual point below which a count is treated as small |
| **withheld** | the source hides a figure that could identify one employer (QCEW sector series); the place has no value, and the legend says so | the definition of those series says it; a blank can also mean the sector has no employers there |

How it shows: a hatched municipality on a shaded map (a dark line beside a white one, so it reads on pale and dark colours and in print), a dashed outline on a symbol, a legend row in words ("Hatched: margin of error above 30% of the estimate", with a count), italics in the pop-up and the workbench table with a sentence under them, and hidden text for screen readers. **Margins of error are not carried through a rescaling**: the flags describe the published estimate, and the legend says so when a view other than "as published" is flagged. Each dataset's card lists the standing cautions of its kind (a survey estimate, counted at the workplace, a derived series, an area is not its people).

## Adapters (`adapters.js`)

An adapter reads one published file and registers datasets; nothing else knows how a file is laid out.

| Adapter | Reads | Becomes |
|---|---|---|
| `series(E, econ, hous, muni)` | `economy_series.json`, `housing_series.json` | the yearly datasets of the Economy tab and every other Housing series (so housing and economy layers share a map) |
| `tourism(E, muni, snapYear)` | `municipalities.json` | five counts of tourism listings, as snapshots |
| `snapshot(E, muni, snapYear)` | `municipalities.json` | nine fields (places in a flood or protected area, transit stops, residents near a stop, land by plan class), the island worked out by the rule of each field (a sum, a ratio of sums, or a mean weighted by residents or land) |
| `exposure(E, files)` | `exposure_municipio.json` (+ barrio, tract) | 60 datasets: residents and housing units inside a hazard, on protected land or near transit, each shaded by default as a share of the area's own total (`docs/exposure.md`) |
| `seriesFile(E, doc, { dict, group })` | `population_series.json` (the shape of `economy_series.json`) | the Population domain's datasets: survey windows with margins of error, in the order of the engine's places (the order of the file is looked up, not assumed) |
| `levelFile(E, doc, { level, names })` | `acs_barrio.json`, `acs_tract.json`, `acs_blockgroup.json` (`names`: one `{ es, en }` object for each area, from the crosswalk) | no new dataset: a level (`barrio`, `tract`, `block-group`) of the datasets that already exist under the same key, with values and margins of error by window; only "as published" and the percentile among the areas are offered there (docs/small-area.md) |
| `levelTable(E, key, level, { name, municipality })` | a level already loaded | the rows of the CSV by area: GEOID, name, municipio, then for each window the estimate, its margin of error and a "less reliable" mark, then the variable, its unit, its dictionary entry, the source and, where a margin is blank, why; `null` when the dataset has no values at that level |
| `snapshotFile(E, doc, o)` | `health_series.json` (any file in the shape of `economy_series.json` with one snapshot year) | the datasets of the file as snapshots; a value the file leaves empty stays empty (a score is not a zero) and a dataset marked `noIsland` has no value for Puerto Rico and offers no index or difference from it (`docs/health.md`) |
| `derived(E, spec)` | two datasets already registered | a ratio, difference or sum for the years both have, with the formula kept in `derived` and written in the definition; margins are not carried through. No dataset uses it yet (nothing is invented) |
| `points(E, spec)` | a list of points with a municipality | a count for each municipality and, as the `hex` level of the contract, a count for each hexagon, read with the filter as it is at that moment |

**Barrio-only datasets (WCRP).** `wcrp_rvi_barrio.json` holds values for the 901 barrios only. `datasets.js` reads it with two adapters above: `snapshotFile` (its ids match no municipio, so every municipio has no value, and `noIsland` leaves Puerto Rico without one) and `levelFile` (the barrio level). A dataset with `level: 'barrio'` starts a shaded layer by barrio (`makeLayer`) and is not offered the survey's CSV by area (`levelsFor`); `fifths: true` makes `econ_level.js` draw it by its ranks (`docs/wcrp.md`). The area profiles and the 3D view pass `['wcrp']` to `datasets.load` to leave the file out.

Adding a kind of file means adding an adapter. Adding a dataset to a file an adapter already reads needs no code: see `docs/adding-data.md`.

## Hexagons and counts by area (`hexbin.js`)

A point layer drawn as pins says where each place is; counted in hexagons it says how many are where. The Layers tab's "Show places as" menu draws the listings that pass its filters (category, confidence, places of worship) as hexagons of 2, 10 or 50 km², re-counted in the browser each time a filter changes. The legend gives the classes with the number of hexagons in each and writes the method: *points counted in each hexagon; hexagons are equal-area*.

Equal area is exact by construction: points are projected with a Lambert azimuthal equal-area projection centred on the island, in which equal areas on the plane are equal areas on the ground, and a regular hexagon grid is laid on the plane (on a sphere of the earth's mean radius; on the real earth the areas are right to about 0.3%). The tests check the projection and the area of sampled hexagons across the island, and that no listing is lost (the 31,536 listings with a point fall in cells that add up to 31,536; the 1,005 counted but not drawn have no point). Cell ids (`q,r`) depend on the cell size. The view is kept in the link (`pv=hex10`).

By area: three more choropleths in the shading menu count the places that pass the filters in each municipality (total, per 1,000 residents, per km²), so the municipal count follows the filters too. Finer areas (barrio, tract) would use the same counting once a point layer carries their ids; the crosswalk of `docs/geography.md` is the join.

## The panel, the legend and the pop-up (`panel.js`, `stack.js`, `popup.js`, `legend.js`)

They return markup and own no behaviour: the page wires the buttons by their attributes (`data-act`, `data-f`, `data-add`, `data-key`). The markup is whitespace-exact against what the pages drew before the engine was shared, which is what lets the browser harness compare it byte for byte. The legend of a layer says its period (the chip), its classes with counts, the number of places without a value, and the reliability lines. A layer's card carries two switches, Shaded and Symbol (`data-act="mode"`, `aria-pressed`): the page passes `layerCard` the same `on(key, mode)` the dataset list uses for its Shade and Symbols checkboxes, and `full` when two layers are shaded already (the bivariate limit), so the card says whether its dataset is shaded, shown as symbols, or both (2026-10-21; the golden card text drops the two labels).

## Links

The Economy tab keeps its state in the address (`e=`): layers joined by commas, each `key.mode.norm.ramp.classes.visible.fixed.real.opacity.colour[.limits]`, with `ey=` for the year and `eb=` for the base year. A link made before this build opens the same layers; a dataset the engine no longer has is skipped, and a rescaling a dataset does not offer becomes "as published". The 2D map's other state: `s=` (shading menu), `pv=` (places as hexagons), `l=` (layers), `c=` (view).

## How it is checked

- `node --test tests/core.test.js` (`python -m unittest discover tests` runs it too when Node is installed): the pure parts, then the engine against `tests/golden/economy.json`, made from the Economy tab as it was before the engine was shared (2,088 value fingerprints and the legends, cards, colours and symbols of 26 stacks), the adapters on the real files, the reliability rules against counts made independently in Python, the equal-area property, and the link round trip.
- `tests/browser/`: captures of the Economy tab, the shading menu, the chat, the Housing page and the 3D view, in English and Spanish, taken from the page before and after a change and compared with a tolerance of 1e-9. Intended changes are listed in `tests/browser/expected.json` as normalisers, so everything else is still compared exactly. With them this build matches the build before the engine (commit `8cc851a`) in both languages.
- A browser cannot be driven to see a layer's look on the screen, the 3D scene or keyboard use; those were looked at by a person (or by Claude in the browser pane) and are listed in `HANDOFF.md`.

## The 3D view (plan item 16, B7)

The 3D view's municipality columns can show any dataset of the Economy tab. In "Columns by municipality" (group Territory), the last choice, **Any dataset of the Economy tab…**, opens three selectors:

- **Height:** the dataset that sets each column's height.
- **Colour:** another dataset, or "Same as the height". The colour is cut into five classes exactly as the Economy tab cuts a shaded map it adds: one set of classes held across all years (a dataset of a single year uses that year), so a colour means the same in every year. Grey means no value.
- **Year:** "Latest" or a year. Each dataset shows its period for that year, labelled as on the map ("2020–2024", "latest at or before", or "first data 2017" when the dataset starts after the year chosen).

Each dataset is rescaled as a shaded map of the Economy tab starts it: counts per 1,000 residents, dollar totals per resident, the rest as published. A negative value (a loss) stands as tall as a gain of the same size, and the legend says so.

**Loading.** The engine scripts, the dataset files and, in Spanish, the map page's Spanish names load only when this choice is first made, so the 3D view's first load does not carry them. They are the same files at the same versions as the map page, so a browser that opened the map reuses them. Measured in headless Chrome: about 470 KB transferred in English and 520 KB in Spanish. `tests/core.test.js` checks three things: the 3D page does not load the engine at start, the versions match `index.html`, and the two pages' Spanish agrees on every shared term.

**What is unchanged.** The 17 measures the columns had before stay as they were (`municipalities.json`), and so do the flood, protected-land and transit layers and the time bars. The plan said the engine would replace the measures; they are kept because removing them would drop features people use. The pop-up of a column is the municipality's usual one; it does not show the engine's values.

**Time series panel** (`site/js/series3d.js`, PR #86). A municipality's card has a **Time series / Serie de tiempo** link. It opens a panel under the map with every year of the "Any dataset" height dataset (`ENG.h`, rescaled as the columns rescale it) for that municipality, with Puerto Rico as a dashed line on the same axis.
- **When it opens.** From the card's link, always. With the "Any dataset" columns on, a click on land also opens it on a desktop (700 px and wider), and while it is open a click on another municipality moves it there. On a phone it never opens by itself; when opened, the card closes so the panel does not cover it, and a click on the map closes the panel. A click with no municipality under it (a flood zone over the sea) or in the route planner's pick mode opens nothing. The engine and its datasets load when the panel opens, not with the card.
- **Year.** With the columns on, the chart and the columns share one year (`ENG.y`): a click on the chart or the keys set it, and the year menu moves the chart's marker. The chart is a slider: Left and Down go one year back, Right and Up one year on, Page Down and Page Up five years, Home and End to the ends, and the year chosen with the keys shows the pointer's tooltip over its point, inside the window, until the focus leaves the chart. With the columns off, the chart keeps a year of its own and the columns' year does not change. **Latest** goes back to the latest year.
- **ACS 5-year estimates.** A window dataset is drawn at the last year of each window; the axis shows that year, and the tooltip, the screen reader's text and the peak name the whole period ("2020–2024"). A note under the chart says that the periods overlap, so a change from one point to the next is not a year-to-year change. Where the engine has a margin of error for the value shown (`E.moe`: values as published, not rescaled), the tooltip and the screen reader's text give it (± at 90% confidence, in percentage points for a percentage) and the chart draws it as a band. For a rescaled ACS count the note says the margin is published for the values as estimated only.
- **Key.** The panel's key (the municipality's line, Puerto Rico's dashed line) shows at every width; under 860 px it takes a row of its own under the title and the buttons, and the panel is 18 px taller for it (2026-10-27; it was hidden there).
- **Focus.** Esc or the close button return the focus to the link that opened the panel, or to the map when that card has closed.
- **Without WebGL.** twin3d.js stops before it makes the map, so the panel is not built (`window.Series` is null) and nothing in series3d.js touches the map (PR #86's version threw `ReferenceError: map is not defined`).
- `tests/browser/series_panel.js` checks this in a browser. `tests/browser/no_webgl_3d.js` checks the view without WebGL.

## Not in this build

The workbench's correlation matrix, small multiples and swipe comparison, the area profiles and the composite builder (B4 to B6) were added in item 12 and are described in `docs/workbench.md`. Margins of error are not propagated through rescalings or derived series. The levels below the municipio answer the contract but no page draws them: the Economy tab reads them only to download a CSV by area (`docs/small-area.md`). The year control remains a control of each page; the semantics (which year a dataset shows, how a period is named) are shared.
