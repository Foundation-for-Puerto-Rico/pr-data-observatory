# Adding data to the PR Data Observatory: placement guide and checklist

The observatory is a general model of Puerto Rico. Its fields of information are called **domains** and they are an open set: the list lives in one file,
`dictionary_src/domains.json`, and `docs/domains.md` (generated) shows the current set. Nothing in the pages, the chat, the catalog or the documentation
may hard-code a domain name or how many domains there are.

Rules that apply to every addition (from the project brief):

- **Open data only, no API keys.** Record the license, the terms and the source. One exception (HANDOFF decision 70): the Federal Audit Clearinghouse API needs a free api.data.gov key, which the build reads from the `FAC_API_KEY` environment variable. It is never written to the repository, the cache or the site. A second one waits on HANDOFF decision 75: a free NASA Earthdata token for night-time lights, read by `nightlights.py` from `EARTHDATA_TOKEN` (a GitHub secret) under the same rules (`docs/nightlights-setup.md`). A third (HANDOFF decision 94): FPR's FCC account for the Broadband Data Collection API, read by `broadband.py` from `FCC_BDC_USERNAME` and `FCC_BDC_HASH` (GitHub secrets; `docs/broadband.md`). Ask before adding any other key.
- **No personal data and no business contact details.** Aggregated data only. If you find personal data in a source, flag it and do not display it.
- **Do not fabricate data.** If something needs data that is not in the repository, add it to `site/data/wanted.json` with the source, license, cadence and proposed domain.
- **Label what a number is:** schedules, estimates, proxies, interpolated values, composites and scenarios must say so on screen and in the dictionary.
- **Keep every existing feature working** and keep view state in the URL. Do not remove or restructure features without asking.
- **Federal grant work** (HUD CDBG-DR and MIT, USDA, EDA) needs Finance and Compliance review before external communication. Record it as a `compliance` review on the dataset.
- **Public spending** records follow one schema (`spending.py`, `docs/spending.md`): never add up two fiscal-year bases, two stages, or two sources that report the same dollars.
- Every new dataset or field gets a dictionary entry with domain tags. Report page weight and load time for the change (say when a figure is only an estimate).

## 1. Does the new data fit an existing domain?

Ask in this order.

1. **What is the thing measured about?** People, homes, schools, hospitals, jobs, roads, land, risk. Pick the domain whose description covers that subject. That is the **primary** domain.
2. **Does it span two?** The subject picks the primary and the other becomes **secondary**. School flood exposure is about schools: primary `education`, secondary `hazards`.
   Tourism places inside a flood zone are about tourism places: primary `economy.visitor-economy`, secondary `hazards`.
3. **Is it a sub-theme with a different audience?** (visitor economy and public money inside economy; hazards and land inside environment.) Add a **sub-domain**: `parent.child` with `parent` set.
4. **Does the subject have no home?** If the dataset is the first of at least three coherent datasets with their own users, **create a domain** (section 2).
5. **Is it a single dataset with no siblings?** Do not create a domain. Tag it with the nearest one and add what you still want to `wanted.json` until siblings exist.
6. **Is it about the observatory itself** (a method, a measure, a tool, boundaries)? Use `system.docs`, `system.tools` or `system.geography`. System domains never appear in the overview by field.

## 2. Create a domain (one object, nothing else)

Add one object to `dictionary_src/domains.json`:

| Field | Meaning |
|---|---|
| `id` | lowercase letters, digits and hyphens; dots make a sub-domain (`hazards`) |
| `parent` | `null` for a top-level domain, else the id before the last dot |
| `order` | whole number; domains and sub-domains are shown in this order within their parent |
| `name`, `description` | **both `es` and `en`**; plain language, one or two sentences. Spanish first in the UI once the string layer lands |
| `icon` | a Material Symbols name. Icon plus name identify the domain; color never does (WCAG, and FPR's rule against color-coding programs) |
| `accent` | a color token defined in `site/css/twin.css` (it only tints a card) |
| `headline` | `null`, or `{ "variable": "<dictionary entry id>", "norm": "value", "label": { "es": "...", "en": "..." }, "island": {...} }`. The overview card shows `label` and the Puerto Rico figure of the variable. A yearly series (a field of `housing_series.json` or `economy_series.json`) needs nothing more: the figure is its Puerto Rico value and the trend its history. A field of `municipalities.json` also needs `island`, the rule that turns the 78 municipal values into one figure: `{ "sum": "field" }`, `{ "ratio": { "num": "field", "den": "field", "scale": 100 } }` (a ratio of two sums) or `{ "wmean": { "field": "field", "weight": "field" } }` (an average weighted by another field), with optional `"unit"` and `"d"` (decimals). `python catalog.py` writes the figures into `site/data/catalog.json` and stops when a snapshot headline has no rule |
| `examples` | one or more starter questions in each language (they become the chat's chips) |
| `presets` | optional: the topic's ready-made views (navigation plan PR 6, decision 81), one to four, shown at the top of its Explore page. Each is `{ "id", "name": {es, en}, "note": {es, en}, "show": [[dataset key, "fill" or "symbol", { "norm": scale, "ramp": colours }]], "on": [l= layer keys] }`: at most two shaded datasets, the note says in plain words what each shading, circle, point or area is, and uses the glossary's words where it can so they are defined. `python catalog.py` writes them, with the ids of their data sources, to `site/data/catalog_views.json` (read only when a topic page opens) and stops on an unknown dataset or layer, a third shaded layer, an unknown color ramp or a missing language; `tests/presets.test.js` checks each scale against the engine. A view replaces what is on the map. Views about federal money need Finance/Compliance approval of their wording before they are added (decisions 20 and 86) |
| `status` | `active` (data live), `partial` (some data live) or `planned` (no data yet: shown as "no data yet", not hidden) |
| `system` | `true` only for entries that are not a field of data |

Then run:

```
python contract.py                   # registry and data contract
python dictionary.py --domains       # refreshes docs/domains.md
python -m unittest discover -s tests
```

## 3. Checklist: add a dataset end to end

1. **Source check.** Keyless, Puerto Rico rows present, license class, terms, personal data, cadence. Save the evidence (URL, date, row counts). If it fails, add it to `wanted.json` as `blocked` with the reason and who to ask in writing.
2. **Pipeline script** in the repository's style (`requests`, cache in `cache/`, `--refresh`, prints counts). Write only aggregates to `site/data/`.
3. **Output file** in `site/data/`, in the smallest form that works. Keep it under its size tier (small up to 1 MB, medium up to 8 MB, large up to 50 MB); explain a larger tier in the record's `note`. Only the `geo/` subfolder is published besides the top level; to publish another, add it to `SUBDIRS` in `contract.py`.
4. **Geography.** Name the level and the join key. Use ids (GEOID), not names; when a source gives only municipio names, turn them into ids with `muni_names.municipio_id()`. The build resolves keys against the geography crosswalk (`site/data/geo/crosswalk.json`, built by `geo.py`): the tourism regions, the 78 municipios, 901 barrios, 981 census tracts and 2,555 block groups. Below the municipio, join by the Census GEOID; to move numbers between areas that do not nest (barrios and tracts) use the crosswalk weights; to read a survey table for small areas use `acs_small.py`. Read `docs/geography.md` first. To count residents or housing units inside a hazard or a protected area, or near a facility, add a family to the exposure series (`exposure.py`; `docs/exposure.md`, section 8) rather than writing a new pipeline. For a variable at barrio, census tract or block group, read `docs/small-area.md` first: the margins are wide, and section 7 of that guide gives the steps.
5. **Time type.** point, period, window (ACS 5-year), vintage, snapshot, event or static. Give `years_path` so the build can check `first` and `last`. The year control treats each type its own way (`docs/engine.md`, "Time"): a yearly series shows the latest year at or before the one chosen, a window names its five years, a snapshot is always the current one.
6. **Contract record** in `dictionary_src/datasets.json` (`domains`, `geography`, `time`, `sources`, `licence_class`, `cadence`, `tier`, `review`).
7. **Source record** in `dictionary_src/sources.json` with `licence`, `licence_class`, `credit` and `access`.
8. **Dictionary entries** for every variable, with `domain` and `domains`. **Pick a home domain** (`domain`): the topic a visitor would open first to look for it in Explore (heat's home is Environment and climate, not Economy); list the other topics it belongs to in `domains`, where it shows under "Also in this topic". The home domain also places it in the dataset menus and, for a layer, in the layer menu (`site/js/core/layers.js`, `domain` and `also`). Then the entry's unit, value type, years, method, how to read it, cautions and sources. Follow `dictionary_src/README.md`. Give each variable an `ask` list when people would name it with words that are not its label (`{"en": ["bridges in poor condition"], "es": ["puentes en mal estado"]}`: lower case, no accents needed, no question marks); the chat reads them (`docs/ask.md`).
9. **Spanish.** Every label, group and unit that reaches the screen needs Spanish: add it to `i18n_src/es/labels_*.json` (and register the file and path under `data_labels` in `i18n_src/pages.json` if it is a new source of labels). `python i18n.py --check` lists what is missing and the build stops on it. Registry names and descriptions carry `es` and `en` already. See `docs/i18n.md`.
10. **`wanted.json`.** Move the row to `live` (or add it as `live`), with `checked_on`.
11. **Run** `python build.py` (the contract runs at the end and fails the build on any violation), then `python dictionary.py --coverage`, `python dictionary.py --links`, `python catalog.py` (the map's catalog and overview; build.py runs it after the dictionary), `python registry.py` (the inventory and the ledger: a new file gets its first-published date, a changed file its last-updated date; commit `dictionary_src/data_ledger.json` with the data; `docs/data-management.md`) and `python -m unittest discover -s tests`. A new data file also needs a counting adapter in `ledger.py` when it is not GeoJSON or a series file (`tests/test_ledger.py` fails until it has one). A dictionary entry whose `where.files` names a field of a series file or of `municipalities.json` gets an "Add to map" button in the Catalog tab with no further work (a field of `municipalities.json` also needs its option in the "Shade municipalities by" menu of `site/index.html`, or the page does not offer the button). A map layer needs one line in `dictionary_src/map_layers.json` (the entry id and the layer key of `LAYER_KEYS` in `site/js/app.js`).
12. **Look at it.** Open the page, check the layer, legend, popup and dictionary entry, the Catalog tab ("Add to map") and, for a domain, its topic in Explore (card, page and ready-made views) and the chat: "show X" and "¿dónde es más alto X?" must find it, by its label or its `ask` words (`docs/ask.md`; `node tests/chat_lexicon_replay.js` shows that no older question changed).
13. **Page weight.** Report compressed bytes added to the first load of each route that uses the file and, if you can measure it, load time on a throttled mobile connection. Say when a figure is an estimate.
14. **Describe** the change in the pull request: what it adds, the checks you ran and what is still open.

## 4. What the build checks (and fails on)

`python contract.py` stops the build when: a domain id is duplicated, lacks a Spanish or English name, has a parent that does not exist or an unknown accent token, names a headline variable that is not in the dictionary,
or a data domain has no example questions; a published file has no record, a record names a missing file, an unknown domain or an unknown source; a license class is laxer than the sources it uses, or a
`licensed-not-open` dataset has no license review; a join key matches fewer than 99% of rows; the years in the record disagree with the file; a file is over its size tier; a column looks like personal or business contact
data or values look like an email address, phone number or SSN and no `pii` review names them. Open reviews are listed at every run (`python contract.py --reviews`) so they are not forgotten.

## 5. Reviews: how to handle what you find

- **Personal or business contact data in a source:** do not publish the columns. If it is already published, add a `pii` review (status `open`, fields, note) and ask for a decision; do not remove features without asking.
- **A source with no stated license:** class `unstated`; confirm with the publisher before relying on it.
- **A source whose data are licensed:** class `licensed-not-open`, with a `licence` review that says what permission is needed. Publication stays flagged until it is cleared.
- **Federal grant content (HUD, USDA, EDA):** add a `compliance` review and the flag `federal-grant` (`"flags": ["federal-grant"]`); Finance and Compliance review comes before any external communication.
- **Sensitive items counted but not drawn or named** (private homes, care and treatment services, points kept local): add the flag `counts-only`.
- **What the Data management page shows:** an open review needs a short `summary` in `en` and `es` (it follows "Open:"); a cleared review needs the `date` it was cleared (YYYY-MM-DD). `contract.py` warns when either is missing.

## 6. How a dataset reaches the layer stack, the legend and the pop-up

The shared engine (`site/js/core/`, `docs/engine.md`) reads a published file through an **adapter**, so a dataset that fits an adapter can be put on the map from Explore, the Catalog and Rankings, and on Tools › Analysis (as a shaded layer or symbols), in its legend, pop-up, workbench and CSV, in the chat's numbers and in the Catalog's "Add to map", with no change to a page.

- **A snapshot of figures for each municipio** (one date, no years), written by a script in the shape of `economy_series.json`: one `Core.adapters.snapshotFile(E, doc, { dict, group })` call in `economy.js`, as `health_series.json` does (`docs/health.md`); add the file to `SERIES_FILES` in `catalog.py` and to the file lists in `dictionary.py`.
- **A yearly series** in `economy_series.json` or `housing_series.json`: nothing to write. Its `type` (`count`, `total$`, `level$`, `rate`, `ratio`) decides which rescalings it offers (per 1,000 residents, per km², share, index, change, percentile), so choose the type that is true. Give `moe` (the 90% margins, same shape as the values) when it is a survey estimate: values whose margin is above 30% of the estimate are then flagged less reliable everywhere. A series made only from ACS tables is a five-year window (its legend names the window); one that mixes a yearly count in is not.
- **A field of `municipalities.json`**: add it to `SNAPSHOT_FIELDS` in `site/js/core/adapters.js` with its label, unit, decimals, `type`, group, sources and definition, and the rule that gives the island's figure (`'sum'`, `{ ratio: [num, den] }` or `{ mean: weightField }`); a share built on a count that can be small names that count (`counted`). It also needs its option in the "Shade municipalities by" menu of `site/index.html`, if the Layers tab should shade it.
- **An exposure family** (residents or housing units inside an area, near a stop): `docs/exposure.md`, section 8; the 60 exposure datasets are made from the file with no code.
- **A list of points that carry a municipality** (schools, clinics): `Core.adapters.points(E, { key, label, group, points, filter, ... })` gives a count for each municipality and a count for each hexagon of equal area.
- **A series computed from two others**: `Core.adapters.derived(E, { key, label, of: [a, b], op: 'ratio' | 'diff' | 'sum', scale })` keeps the formula and says on the dataset's card that it is derived and that margins of error are not carried through.
- **A new kind of file** needs a new adapter (a function in `adapters.js` that calls `E.add`), a Node test on the real file in `tests/core.test.js`, and an entry in the golden harness if the Economy tab's output changes (`tests/browser/README.md`).

What every dataset on the stack must say about itself: unit and decimals, the sources (ids in `sources.json`), a definition, `dictId` (the dictionary entry its "Full entry" link opens), whether the source **withholds** small cells (the QCEW sector series do), and, if it is rescaled in the browser, nothing else: the engine labels rescaled, derived and less reliable values as what they are.
