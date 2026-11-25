# The workspace: how the observatory looks and where things are

Since November 2026 every page shares one look, taken from a CARTO-style prototype: a compact top bar, a rail of areas down the left side, a light and a dark theme, and on the map a layers panel, widgets, a workbench and a timeline. This file says how it is built, how to run it, how data reaches it and how a change goes to production.

What was kept from the earlier pages, and what is only partly done, is in `docs/workspace-feature-parity.md`.

## Run it on your computer

```
git clone https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory.git
cd pr-data-observatory
python -m http.server 8151 --bind 127.0.0.1 --directory site
```

Then open `http://127.0.0.1:8151/index.html`. The address works on that computer only. The page needs the internet for the base map, the icons and the map libraries. There is no build step for the pages: `site/` is what is published.

After a change, run the checks that `tests.yml` runs:

```
pip install -r requirements.txt
python -m unittest discover -s tests
node --test tests/*.test.js
python contract.py
python i18n.py --check
python i18n.py            # writes site/i18n/; commit what it writes
python catalog.py --check
python registry.py --check
python dictionary.py --check
python budget.py
python check_refresh.py
```

## The pieces

| Piece | File | What it does |
|---|---|---|
| The look | `site/css/ws.css` | Loaded last on every page. Tokens for the two themes, the top bar and the rail, the parts (buttons, fields, cards), the map workspace, and the three workspace pages. It holds no data and no behavior |
| Light or dark | `site/js/i18n.js` (`theme`, `setTheme`) | Sets `html[data-theme]` before the first paint and adds the switch beside ES / EN. The choice is kept in the browser as `twin.theme`. Without one the pages open dark: change `theme()` to change that. A page that draws with colors of its own listens for `themechange` on the document |
| The rail | The `<nav class="views">` of each page | Plain links, in the page's HTML. `ws.css` places them down the left side, or along the bottom under 900 px |
| The map workspace | `site/js/ws_map.js` | The project bar, the timeline, the widgets, the workbench grip, undo and redo, saved maps |
| Explore | `site/explore.html`, `site/js/ws_explore.js` | Ready-made views, topics, saved maps, topic pages |
| Data | `site/data.html`, `site/js/ws_data.js` | The catalog as cards |
| Workflows | `site/workflows.html`, `site/js/ws_flows.js` | Steps that run in the browser on the published files |

Everything else is as it was: the Leaflet map (`app.js`), the shared engine (`site/js/core/`, `docs/engine.md`), the topic pages, the 3D view and the connector. The redesign changed no renderer, no data file and no calculation.

### Themes and colors

- The dark theme replaces the tokens of `twin.css` (`--color-surface`, `--color-text`, the tints…) under `html[data-theme=dark]`. A rule written against a token follows the theme with no further work.
- White grounds and neutral grays that were written as fixed colors in the page stylesheets are now tokens (`--color-surface`, `--ws-n-ink`, `--ws-n-paper`, `--ws-n-line`…) with the same values in the light theme.
- **The data's own colors are never themed**: ramps, categories, hazard zones. A legend must keep matching its map.
- No blur behind panels (`backdrop-filter`): `tests/test_overlays.py` keeps the FPR rule.
- A new page loads `css/ws.css` after its own stylesheets and uses tokens, not fixed grays.

### The timeline

The timeline is a control for the year the engine already had (`EC.year`; `ey=` in the address; `null` means the latest). It adds no second state.

- Its steps are `ECON.api.years()`: the years that at least one moving dataset has. Nothing is hardcoded.
- Moving it calls `ECON.api.setYear()`. The engine redraws the map, the legend, the layer cards and the workbench, and the widgets follow.
- Each layer's chip gives the period it really shows, by the engine's rule (`core/time.js`): the chosen year, or the latest at or before it, and the whole window for a five-year survey estimate. A 2020–2024 estimate is never called a 2026 observation.
- Nothing is estimated between years and a missing value stays missing.
- The engine loads on first use, so the timeline is disabled until a dataset is on the map, and says so.
- Sea level rise (feet, a scenario), the timetable replay (Puerto Rico time) and the 3D view's storms keep their own controls. Their units are not years.
- `ws_map.js` hears the engine through `Core.activelayers.changed()` and `dock()`, which the engine already calls on every draw, so `economy.js` was not changed.

### Widgets and their figures

The widgets compute no statistic of their own, with one rule that is theirs. A figure for several municipios (a region, a filtered set) is the **sum** when the dataset is a count or a dollar total as published, and otherwise the **median of the municipal values**, labeled with those words. It is not a pooled rate. With no filter the key figure is Puerto Rico's own published value.

A filter in the widgets changes the widgets only, and the panel says so.

### What is kept in the browser

| Key | What |
|---|---|
| `twin.theme` | Light or dark |
| `twin.maps` | Saved maps: a name, a date and the map's address |
| `twin.ws.last` | The map as it was last left, for Explore and for Data's "Add to my map" |
| `twin.ws.right`, `twin.ws.bench`, `twin.ws.closed`, `twin.ws.speed`, `twin.ws.name` | The widgets panel, the workbench height, folded widgets, playback speed, the map's name |
| `twin.flows` | Saved workflows |

Nothing is sent anywhere. There are no accounts. A saved map is its address, so it holds no data.

## How new data appears

Nothing in the workspace is a list kept by hand.

| Where | Reads | Written by |
|---|---|---|
| Data: every card, the counts, the filters | `data/catalog.json`, `data/catalog_index.json`, `data/catalog_es.json` | `catalog.py`, from `dictionary_src/` |
| Explore: topics and ready-made views | `data/catalog.json`, `data/catalog_views.json` | `catalog.py` |
| Explore: topic pages | `js/knowledge_items.js` | `knowledge.py`, from `knowledge_src/items.json` |
| Workflows: sources | `data/registry.json`: every `.geojson` whose title says "points" | `registry.py` |
| The timeline's years, the widgets' datasets | The engine (`core/datasets.js`) | `docs/adding-data.md` |

So adding a dataset is what it was (`docs/adding-data.md`): once the build has run and the generated files are committed, the dataset is in Data, on the map and on the timeline. A new area file for Workflows is the one exception: add a line to `AREAS` in `ws_flows.js`.

## A new page

1. Copy the `<header class="topbar">` of an existing page, with its eight links. `tests/test_learn.py` checks the Learn link on every page.
2. Load `css/ws.css` after the page's stylesheets.
3. Register the page in `i18n_src/pages.json` (with the `glossary` module) and in `dictionary_src/routes.json`.
4. For a page written by a generator in `docs/analysis/`, change the generator: its header is a template there.

## From GitHub to production

1. Work on a branch from an up-to-date `main`. Nobody pushes to `main`: a ruleset blocks it (`CONTRIBUTING.md`).
2. Open a pull request. `tests.yml` runs on it; the ruleset requires its `checks` job.
3. **Merging publishes.** `pages.yml` runs on every push to `main` that touches `site/` or `connector/` and deploys them to Azure Static Web Apps, which serves `observatory.foundationpr.org` (`docs/azure.md`). It first runs the privacy checks and bundles the connector's data. Keep a pull request as a draft if it must not go out yet.
4. **To undo a release**, open a pull request that reverts the merge (`git revert -m 1 <merge commit>`) and merge it. The site is published again from the reverted `main`. Do not rewrite the history of `main`.
5. Files are cached for 10 minutes (`staticwebapp.config.json`). A changed script or stylesheet needs its `?v=` raised in every page that loads it, and in the generator of a generated page.
