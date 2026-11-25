# Inflation in Puerto Rico and the United States: plan (HANDOFF decision 95)

The project lead on 2026-11-10: add an inflation analysis to the Knowledge areas, filed under Economy; track inflation in Puerto Rico and the US, compare them, and project the next five years. The first thing a visitor sees is Puerto Rico's inflation rate beside the US rate, from 2000 to the latest month, with the projection. The page ends with what it means for an individual and a family. Prepared with Claude (AI) for FPR; the analysis was written as a data scientist and economist would, and every figure is read from the data file the build writes.

## 1. Categories for the Knowledge areas

Every Knowledge item already has a home domain (`knowledge_src/items.json`, `domains[0]`), from the map's domain list (decision 81). That domain is the item's category:

- the Knowledge home page (`knowledge.html`, decision 90 PR 1, live) groups its cards by it: Economy holds the Global Innovation Index and Women in the labor force;
- Knowledge PR 2 (decision 90 (f), in progress on `knowledge/header`) replaces the strip of tabs on each area page with a header "Knowledge › Economy" and an "All areas" menu grouped by the same categories.

The inflation item takes `domains: ["economy"]`, so it lands under Economy in both places with no new taxonomy. A separate "Knowledge category" list was considered and set aside: it would duplicate the domains and drift from the map.

## 2. Data sources (all read by a script, no key)

| Source | What | Span | License |
|---|---|---|---|
| Puerto Rico Department of Labor and Human Resources (DTRH), Negociado de Estadísticas del Trabajo: workbook "Serie Histórica Índice de Precios al Consumidor" (`mercadolaboral.pr.gov/lmi/Excel/IPC/Serie Historica a Publicar.xls`) | Official CPI of Puerto Rico, all items and the 8 major groups, monthly, base December 2006 = 100 (2010 revision, geometric means) | January 2007 to the latest month (September 2026, published 2026-10-26) | Government of Puerto Rico public information |
| DTRH on `indicadores.pr` (CKAN dataset `indice-de-precios-al-consumidor`), CSV | The same index concatenated back to January 1984, about 78 items, and the 2000-01 basket weights | 1984 to April 2026 | Creative Commons Attribution |
| US Bureau of Labor Statistics, public API v1 | CPI-U US city average (CUUR0000SA0), CPI-W (CWUR0000SA0), the 8 major groups, energy, electricity; not seasonally adjusted | 1999 to the latest month (October 2026) | US Government work |
| Federal Reserve Bank of Cleveland, inflation expectations model (`inflation-expectations.xlsx`, doi 10.26509/frbc-infexp) | Expected US CPI inflation over 1 to 30 years, every month | 1982 to October 2026 | Free with citation |
| Federal Reserve Bank of Philadelphia, Survey of Professional Forecasters (`Inflation.xlsx`) | Median 1-year and 10-year CPI forecasts | 1981 to 2026 Q3 | Free with citation |
| US Census Bureau, American Community Survey 1-year (summary files on www2.census.gov) | Median household income (B19013), Puerto Rico and the US, with margins of error | 2010 to 2025 (no standard 2020 release) | US Government work |

Checked on 2026-11-10: the 2025 ACS 1-year file was already out and is read (2010-2025); the two DTRH files agree on 230 of 231 overlapping months (August 2015 differs by 0.01 point); the CSV skips July 2025, which the workbook has; BLS has no October 2025 CPI (the 2025 lapse in appropriations), so the US change over 12 months for October 2026 is not computed and the model reads that month as the geometric mean of September and November 2025. Not used: FRED (it mirrors BLS and the Cleveland Fed and timed out from scripts), CBO's projections page (refuses scripts, HTTP 403), the Census API (now requires a key).

## 3. What the page shows, in order

1. **Headline chart (the first thing seen):** 12-month inflation, Puerto Rico and the US, monthly from January 2000 to the latest month, then the projection to 2031 with 80% and 95% bands; the latest values and the gap in figures above the chart.
2. **Inflation by year:** calendar-year averages 2001 to 2025 and the projected years, side by side, with a table and CSV.
3. **What drives it:** the 8 major groups in Puerto Rico and their US counterparts, 12-month change and change since January 2020.
4. **The projection and how good it is:** method, the backtest table, the bands, what would change it.
5. **What it means for a person and a family:** purchasing power of a dollar since 2000 and 2020; median household income in current and constant dollars, Puerto Rico and the US, 2010 to 2024; a budget calculator (a monthly amount, a start date, the cost today and in 2031 by group, using the DTRH basket weights); Social Security's cost-of-living adjustment (tied to the US CPI-W) beside prices in Puerto Rico.
6. **Method and sources.**

## 4. The projection

Candidates, each tested the same way: 44 forecast origins (each quarter, 2011 to 2021), forecasts of Puerto Rico's average inflation over the next 12 to 60 months, compared with what happened. The US input at each origin is the Cleveland Fed's expected-inflation curve of that month, so no candidate sees the future.

| Candidate | RMSE, 12 months | 24 | 36 | 48 | 60 |
|---|---|---|---|---|---|
| Puerto Rico follows expected US inflation (Cleveland Fed) | **2.03** | **1.84** | **1.55** | **1.30** | **1.18** |
| Monthly ARDL of Puerto Rico on US inflation, US path from the Cleveland Fed | 2.15 | 2.04 | 1.81 | 1.60 | 1.49 |
| Last 12 months persist | 2.07 | 2.20 | 2.13 | 1.95 | 1.87 |
| Puerto Rico's own average since 2008 | 2.13 | 1.95 | 1.75 | 1.58 | 1.50 |
| Expected US inflation plus the last 10 years' Puerto Rico-US gap | 2.39 | 2.29 | 2.09 | 1.90 | 1.78 |

(Percentage points of average annual inflation; the build of 2026-11-10, recomputed by `inflation.py` at every build and checked by `tests/test_inflation.py`.) The ARDL's long-run pass-through of US to Puerto Rico inflation is about 1.1, with a constant of about -1.0 point a year; even fed the US inflation that actually happened, it did worse than the first line at 48 and 60 months. So the central path is the first line: what markets and forecasters expect for US consumer prices, year by year (the Cleveland Fed's curve turned into one-year forward rates). Puerto Rico shares the dollar and the Federal Reserve's policy and imports most of what it consumes; its own departures from the US path have been large but have not been predictable.

The bands are that method's own past errors: for each horizon, the errors of the 44 backtest forecasts against Puerto Rico's actual inflation (and, for the US line, of the same curve against US inflation from 88 quarterly origins of 2000 to 2021). The page says plainly that the 2021-2022 surge was outside almost every forecast and that the bands come from a short history.

## 5. Build and files

- `inflation.py`: downloads and caches the six sources (`cache/inflation/`), checks them against each other, runs the backtest and the projection, writes `site/data/inflation.json`; `--check` rebuilds in memory and compares. Added to `build.py`, `refresh/sources.json` and the freshness table.
- `docs/analysis/inflation-2026-11/make_page.py`: writes `site/inflation.html` and its Spanish (`i18n_src/es/inflation.json`), every figure from the data file.
- `site/js/inflation.js`, `site/css/inflation.css`: the charts (SVG, no library), tables, CSV downloads and the calculator.
- Registry item `inflation` (kind analysis, domains economy, `review: true`, `ai: true`), page registrations (pages, routes, throttle, links), a dataset entry and dictionary entry, glossary terms with sources (consumer price index, inflation rate, base period, purchasing power, pass-through, prediction interval, backtest, expected inflation, cost-of-living adjustment).
- Tests: the data file's structure and recomputed headline numbers, the page's figures against the file, the Spanish layer.

## 6. Limits stated on the page

- Puerto Rico's index before 2007 is DTRH's older method concatenated to the new base; its rise in 2005-2008 partly reflects that method (stale weights from the 1970s basket). The model is estimated on 2008 onward only.
- The two indexes are not the same measurement: DTRH aggregates with geometric means within items (since 2010) and weights rent and owners' equivalent rent much less than BLS. Part of the long-run gap is measurement, not prices.
- The basket weights are from the 2000-01 survey of DTRH; families differ.
- The projection is not a forecast of FPR or of any agency; it shows what the US expectation implies for Puerto Rico and how wrong this method has been.

## 7. Decision 95 (for the project lead)

(a) Categories = the home domain (no new taxonomy; Inflation under Economy). (b) The six sources above. (c) The central path = expected US inflation, bands from the method's own backtest errors. (d) The page `inflation.html` published with `review: true` and `ai: true` (the marker and `noindex` stay until the project lead takes them off). (e) One PR on `knowledge/inflation`, merged only on their word; it conflicts with Knowledge PR 2 and PR #180 in generated files and HANDOFF, fixed by whichever merges second. Follow-up, not in this PR: the Economy tab's real-dollar series deflate with the US CPI-U today (`economy_series.py`, source `cpi`, "an approximation of the island's inflation"); they could use Puerto Rico's index.
