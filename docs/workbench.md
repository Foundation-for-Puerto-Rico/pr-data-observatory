# Workbench views, area profiles and the composite builder (Phase 3, item 12)

Plan: `docs/proposal-2026-10.md`, sections B4 to B6 (J row 12). Each feature reads datasets through the shared layer engine (`docs/engine.md`), so a dataset added to the engine appears in all of them with no other change.

## What was added

| Feature | Where | Code |
|---|---|---|
| Correlation matrix | Workbench, "Correlations" tab | `ecBenchMatrix` (workbench.js), `Core.stats.matrix` |
| Small multiples | Workbench, "Small multiples" tab | `ecBenchMultiples`, `Core.minimap` |
| Two maps compared (swipe) | Workbench, "Compare two maps" tab | `ecBenchSwipe` |
| A table for every map | "View the map as a table" at the foot of the legend opens the Table tab | `ecRenderLegend` |
| Composite builder | Workbench, "Composite" tab; link part `#ix=` | `ecBenchComposite` (workbench.js), `ecIxApply` (economy.js), `Core.composite` |
| Area profiles | `profile.html?area=72127`; links from the map pop-up and the Municipality tab | `profile.js`, `Core.datasets`, `Core.stats.peers` |

New shared modules in `site/js/core/`:

- **`datasets.js`** lists the files the Economy tab reads and adds them to an engine in a fixed order. The area profiles read the same list, and so does the test engine (`tests/core.test.js`, `tabEngine`). A new series file goes here once.
- **`composite.js`** holds the composite's arithmetic and its link format.
- **`minimap.js`** draws the 78 municipal outlines as SVG for the small maps: no tiles and no base map.

**Loading (2026-10-18):** the Scatter, Trend, Correlations, Small multiples, Compare two maps and Composite views are in `site/js/workbench.js`. The map loads it, with `core/minimap.js` and its Spanish (`es.map.workbench.js`), the first time one of these views opens (`ecWorkbenchLib` in economy.js); until then the view says "Loading…". The Inspector and Table views, the composite's dataset (`ecIxApply`, so a link with `#ix=` is restored before any view opens) and `Core.composite` stay in the first load (docs/performance.md).

**Trend view and the keyboard (2026-10-27):** the Trend chart is a slider (`ecTrendKeys` in workbench.js): with the focus on it, Left and Down go one year back, Right and Up one year on, Page Down and Page Up five years, Home and End to the ends. The chosen year opens the chart's own tooltip for every visible line, and a screen reader hears the year and each line's value (`aria-valuetext`). The tooltip closes when the focus leaves. `tests/browser/usability.js` checks it.
- **`stats.js`** gained ranks, Spearman correlation, pairwise-complete correlation, the matrix, z-scores and peers.

## Correlations

The tab takes up to eight visible layers, each as the map shows it (year, rescaling, settings).

- **What each cell shows:** r and n. n is the number of municipalities with a value for both layers. Each pair uses its own municipalities (pairwise complete), so n can differ from cell to cell.
- **Methods:**
  - Pearson measures a straight-line pattern.
  - Spearman is Pearson on the ranks; tied values share the mean of their ranks.
- **Small pairs:** fewer than 3 municipalities gives no r.
- **Colors:** the cells use the diverging palette at the cut points ±0.1 and ±0.5.
- **Reading the result:** the "pattern, not cause" note stays above the table.

## Small multiples and the swipe view

**By year:** one map for each of the last 12 years with values of one layer.

- The classes come from every year together, the same rule as "Hold classes fixed across years". A color therefore means the same in each map.
- The Puerto Rico value is under each map.

**By layer:** one map for each visible layer (up to 8), each with its own classes. The note says the colors are not comparable between maps.

**Swipe view:** two layers on one SVG; the second is clipped at the divider.

- The divider is a range input, so it works with the keyboard and a screen reader.
- Each side keeps its own classes and legend.

## Composite builder

A person picks 2 to 12 datasets, a direction for each (higher is better or worse), a weight from 0.1 to 100 and one scale. A new input starts with no direction ("Choose…"): nothing is assumed about what is better, and "Put on the map" stays off until each input has one (the project lead, 2026-10-15).

1. **Read each input** as a shaded map starts it: counts per 1,000 residents, dollar totals per resident, the rest as published. The year is the one the year control picks; with "Latest", each input's latest year.
2. **Put each input on the chosen scale** across the 78 municipios:
   - z-score: the population standard deviation of the municipios.
   - 0 to 100 between the lowest and the highest.
   - Percentile rank 0 to 100: the share of the other municipios with a lower value, tied values sharing the mean of their ranks.
   An input that has the same value in every municipio (or a value in only one) counts as missing everywhere, on all three scales: with more than 20% of the weight it leaves every municipio blank. The tab says which inputs do not vary.
3. **Turn round** the inputs where lower is better.
4. **Score** each municipio as the weighted mean of the inputs it has. A municipio with less than 80% of the weight present is left blank; exactly 80% is enough. Puerto Rico as a whole is never scored.
5. **Show the results.** The table lists the score, the share of the weight present and what each input adds; the additions sum to the score. A CSV holds the same.

The result is a dataset of the engine (`user_composite`, a snapshot of the year its inputs show), so it shades, shows in the pop-up and joins the other workbench views like any other.

- **Label:** wherever it appears it is called "User-built composite, not an official index".
- **Method text:** its definition lists every input with its rescaling, year, direction and weight. It shows above the results table and in the dataset's information window.
- **Year control:** the composite is worked out again whenever the year changes.
- **Two shaded layers already on:** the scores are computed and a message says to remove a shaded layer to map it.

**The link:** `#ix=z,poverty_pct:l:2,qcew_avg_pay:h:1` holds the scale (`z`, `mm`, `pct`), then each input as `key:direction:weight` (`h` higher is better, `l` lower is better).

- On load, the composite is rebuilt before the layers of `#e=`, so a link that shades it opens with it on the map.
- Reading the link drops unknown datasets, repeated inputs, other directions and weights outside 0 to 100.
- "Clear all", a preset that clears the stack and the "Remove the composite" button all remove it.

## Area profiles

`profile.html?area=` takes a municipio's five-digit code (`72127` is San Juan). An unknown code shows San Juan and says so.

**Loading:** the page loads the same files as the Economy tab (`Core.datasets`), plus `catalog.json` and its index, `catalog_index.json`, for the fields of the registry. It draws twice (2026-10-18, `docs/performance.md`): first with the files of its first field, Housing, and of the peers (`FIRST` in `profile.js`: the economy and housing series, exposure, facilities, conditions), then, once the other files have arrived, with every dataset, added again in the order of `datasets.js`. Until then the page says it is loading the other fields and "Download CSV" waits. `tests/profile_first.test.js` checks, for the 78 municipios, that the first field and the peers are the same with the first files as with all of them.

**Layout:**
- Each top-level field (domain) gets a table, and inside it each dataset's group gets a band.
- A row has:
  - the latest value as published, with its margin of error;
  - the value a shaded map compares (per 1,000 residents, per resident, a share);
  - the rank among the municipios with a value (1 is the highest, `Core.stats.rank`);
  - Puerto Rico's value on the same measure;
  - an SVG trend line of up to 15 years.
- Datasets with no value for the place are left out, and the page counts them. The exception is a dataset that gives an empty place a meaning (a shortage area): it shows that meaning instead.

**Peers:** the five municipios nearest on the logarithms of population and of residents per km², each put on z-scores across the 78 (`Core.stats.peers`). The page states this method next to the list. A small map marks the place and its peers.

**Download:** "Download CSV" saves every row.

**Links in:** the map's pop-up ("Area profile") and the Municipality tab.

**Regions (2026-10-31):** `profile.html?region=<id>` shows a region (a group of whole municipios: the Eastern Region of the ERSV and the seven tourism regions) with the region, the rest of Puerto Rico and Puerto Rico side by side; `docs/regions.md`.

**Not done:** the plan's "the existing municipality tab becomes a compact view of the same component". The tab links to the profile instead. Profiles below the municipio wait for data at those levels on the map.

## Page weight

Estimated, not measured on a throttled connection: see HANDOFF.md, item 12.

- The 2D map's first load grows by the three new core modules and the workbench code.
- The profile page loads the Economy tab's series files, the outlines and the catalog when it opens.
