# Data management: what is published, how much of it, since when, and under what review

The Data management page (`site/data-management.html`, "Gestión de datos") is the public account of every data file the observatory publishes. It grew out
of the "Published data files" table of the data dictionary (Francis, 2026-10-19). For each file it gives what the file holds, its domain, its **records**,
**fields** and **values** (data points), its size, the date it was **first published** and **last updated**, the dictionary items that **document** it and
the state of its **compliance review**; for the whole folder it gives the totals, how they grew, and what is **not published**, as counts only.

| Piece | What it does |
|---|---|
| `ledger.py` | Counts each file (one adapter per family of files, section 2) and computes its content hash (section 4). Keeps the ledger. `python ledger.py --count FILE [--fields]` prints the counts of a file and the fields counted; `python ledger.py --backfill [REF]` rebuilds the ledger from git. |
| `dictionary_src/data_ledger.json` | The ledger, committed: for each file `first_published`, `last_updated`, `versions`, `hash`, `bytes`, `kind`, `records`, `fields`, `values`, `vertices`; files no longer published under `removed`; `history`, the totals on each date they changed. Written by `registry.py`, never by hand. |
| `registry.py` | Runs on every build (and on the nightly transit refresh): updates the ledger, then writes `site/data/registry.json` only when something other than the date changed. `python registry.py --check` fails when the ledger or `registry.json` does not describe the files as they are (CI runs it). |
| `site/data/registry.json` | What the page reads (one request, about 11 KB compressed): the file rows with their counts, dates, documenting items and review; `totals`, `history`, `domain_names`, `withheld`. The data dictionary and the chat read it too. |
| `site/js/datamgmt.js`, `site/css/datamgmt.css` | The page. Its pure functions (`DM`: sorting, totals, CSV, axis ticks) are tested in Node (`tests/datamgmt.test.js`). |
| `dictionary_src/datasets.json` | The data contract: the reviews (with a short `summary` for an open one and the `date` of a cleared one) and the `flags` the Compliance review column shows (section 5). |

## 1. Definitions

The register is that of a statistician: the standard terms, each defined once. The page repeats these definitions in its last section, and the glossary has
them as terms (section 8).

- **Record**: an observation unit. In a GeoJSON file, a feature. In a table, a row: a place, a stop, a trip, a road edge, a census block, a municipio. In a
  series file (`geo.ids` × the years of each variable), an area in a period that holds at least one value: a municipio in a year, a barrio in a five-year
  window. A file with several tables (patterns, routes and stops of each day in `transit_supply.json`) adds the rows of all of them.
- **Field**: a variable the records carry: a GeoJSON property, a series variable, a column. A margin of error is a field of its own. An object inside a
  record is a group of fields (`by_category.ATTRACTIONS`). A cell that holds a list (24 hourly counts, the stop times of a trip) is one field. A field is
  counted when at least one record has a value in it; in a file with several tables, the fields of each table are counted (`(table, field)` pairs).
- **Value (data point)**: a non-null scalar in a field of a record. A list cell counts its non-null elements. **Missing**: `null`, an absent key, the empty
  string, NaN. A coded value (99,999 metres: beyond the search limit) is a value.
- **Not values**: metadata (titles, labels, units, definitions, notes, sources, about, build stamps, method and check blocks, the `type` members of GeoJSON);
  geometry coordinates (counted as vertices); the keys a file stores once as a lookup (`geo.ids`, `geo.names`, the `years` list), which identify a record but
  are not observations of it; and lookup tables (the land-use legend, the CPI deflator of `economy_series.json`, the gazetteer). A key stored *inside* each
  record (a GeoJSON `geoid` property, a place's Overture id) is a value: the record carries it.
- **Vertex**: a position of a geometry: a GeoJSON coordinate pair (the closing position of each ring counts), a point's latitude and longitude in a table, a
  point of a route path (with its metres along the path, a measure coordinate), a node or interior shape point of `roads.bin`. Reported apart; a file
  without geometry has none.
- **Kind**: `data` (counted); `documentation`, a file whose primary domain is `system.docs` (the dictionary files, the catalog files, `meta.json`,
  `wanted.json`); `index`, `system.tools` (`gazetteer.json`, a search lookup of names already in other files). Documentation and index files are listed and
  sized but not counted; the table shows their entries ("859 entries") instead.
- **Size**: the bytes of the file with line ends counted as one byte (as GitHub Pages serves the repository's LF copy); 1 MB = 1,048,576 bytes. The limit of
  a GitHub Pages site is taken as 1,000 MB (`registry.PAGES_SITE_LIMIT`), so 81.1 million bytes are 7.7% of it.
- **Totals**: records, fields and values add the data files; size adds every listed file. A value repeated in two files counts in each (the barrio values
  of `municipalities.json` and `barrios.geojson`, the trips of `trips.json` and `transit_supply.json`), so the totals measure what is published, not distinct
  facts. The table's totals row adds the files shown. `registry.json` itself is not listed: it describes the others and is written after them.
- **Documented by**: the number of dictionary entries whose `where.files` name the file. An entry that names two files counts in each.

## 2. Adapters: what a record is in each family of files

| Family | Files | Record | Fields | Left out |
|---|---|---|---|---|
| GeoJSON | every `.geojson` (also `geo/`) | feature | properties | the collection's `source`, `vintage`, `notes`, `built`; geometry → vertices |
| Series | `*_series.json`, `acs_*.json`, `conditions_barrio.json`, `landslide_barrio.json`, `population_age.json` (three tables: municipio, barrio, tract), `wcrp_rvi_barrio.json` | area × period with a value | each variable, each margin of error; `economy_series.json` also `top_sector` (per area and year) and the island's `fed_unplaced_share` and `fema_pa_statewide_share`; `housing_series.json` the island's four cost-burden distributions (`tables.*`) | `geo`, `years`, `vars[].label/unit/definition/basis…`, `notes`, `sources`, `deflator` |
| Columnar | `exposure_*.json`, `wcrp_rvi_inputs.json`, `place_access.json` (with `tw_straight`, a flag stored as the list of the records that have it), `wcrp_social.json` (and its 710 communities, whose code has one character per asset flag: `1`, `0`, `-` missing) | position with a value | every list of one value per record, by its path | labels, parameters (`near_m`, `cap_m`), `geo` |
| Lists of records | `places.json` (the 1,005 rows counted but not drawn are records), `transport.json`, `municipalities.json` (keyed by name), `hurricanes.json` (a storm; its track is one field: each fix gives a vertex and three values: time, wind, status), `population_blocks.json` (a block: residents, metres to a stop, metres walking) | object | keys | latitude and longitude → vertices |
| Own tables | `transit_supply.json` (patterns, routes, stops for each day, and one island row per day), `trips*.json` (trips; paths with their kind and stops; path points → vertices), `operators.json` (operators, coverage, transfers), `geo/crosswalk.json` (units of every level; barrio–tract weights), `housing.json` (the study's island figures, the LIHTC table), `landuse_summary.json` (78 municipios, Puerto Rico, unassigned) | row of each table | columns | parameters, legends, live-feed notes, totals already in the rows |
| Binary | `roads.bin` | road edge (header `n_edges`) | length, road class, one-way | end nodes (topology); nodes and shape points → vertices (header `n_nodes + n_shape`) |
| Not counted | documentation and index files | — | — | entries are shown instead |

A new data file needs an adapter when it is neither GeoJSON nor a series file: `tests/test_ledger.py` (`test_every_published_data_file_has_an_adapter`) fails
until `ledger.FAMILY` knows it. Old versions read by the backfill go through the same adapters (trips files of format 1 included); a version an adapter cannot
read keeps the counts of the version before (the backfill of 2026-10-19 needed none).

## 3. Validation

- **Independent count.** `tests/test_ledger.py` (`IndependentCount`) counts four files again without `ledger.py`'s helpers, with plain loops, and compares:
  `municipalities.json` 78 records, 96 fields (nested objects flattened), 7,350 values; `barrios.geojson` 901, 13, 11,713 and 39,965 vertices (ring
  positions summed by hand); `places.json` 32,541, 24, 518,250 and 31,536 vertices (the rows with a point); `acs_barrio.json` 3,604 records (901 barrios × 4
  windows, every one with a value), 76 fields (38 variables and their margins), 261,296 values. All four agree.
- **By arithmetic.** `trips.json` 3,519 records = 3,297 trips + 222 paths; `transit_supply.json` 5,283 = (222 + 144 + 2,875 + 1) + (99 + 52 + 1,772 + 1) +
  (16 + 7 + 93 + 1); `operators.json` 488 = 44 operators + 78 municipios + 366 transfers; `geo/crosswalk.json` 6,580 = 4,523 units + 2,057 weights;
  `hurricanes.json` 20,971 values = 157 storms × 7 + 6,624 fixes × 3; `population_age.json` 7,844 = 79 × 4 + 901 × 4 + 981 × 4.
- **Unit tests** on small documents for every family, missing values, the content hash and the ledger rules; **mutants**: eleven deliberate errors in
  `ledger.py` and `registry.py` (first_published moving, every build an update, stamps hashed, empty text a value, coordinates as values, two history rows on a
  day, an empty area-period a record, a returning file dated anew, the build date compared, a clearance hiding an open review, the roads header misread) were
  each caught by `tests/test_ledger.py`.

### The crude count and this one

A crude count of the non-null scalar leaves of every JSON file, GeoJSON geometry left out, gave about 3.47 million (2.71 million numeric) before this work;
on the files of 2026-10-19 it gives 3,477,787. The rigorous count of the JSON data files is lower; with the binary road network, which the crude count could
not read, the total is higher:

| Step | Values |
|---|---:|
| Crude count, every JSON and GeoJSON file | 3,477,787 |
| less `registry.json` (the inventory) | −2,018 |
| less documentation (dictionary, catalog, `meta.json`, `wanted.json`) | −95,923 |
| less the place-name index (`gazetteer.json`, a lookup) | −249,853 |
| = crude count of the JSON data files | 3,129,993 |
| less coordinates inside records (latitude and longitude of places, stops, blocks, crosswalk units, transfers; storm fixes; path points), counted as vertices | −258,702 |
| less empty strings (missing) | −286 |
| less metadata, GeoJSON `type` members, lookups and keys stored once | −29,822 |
| = values of the JSON data files | 2,841,183 |
| plus `roads.bin` (226,421 edges × 3 fields) | +679,263 |
| = values of the 60 data files | 3,520,446 |

## 4. The ledger: first published, last updated, versions, growth

- **Content hash**: SHA-256 (first 16 hexadecimal digits) of the file's JSON in canonical form (keys sorted, no spaces), with the build stamps `built`,
  `generated_at` and `snapshot_built` left out wherever they are not inside a record (a key inside a list, such as a field of a row, is data). A file that is
  not JSON is hashed as bytes. So a rebuild that only writes a new date has the same hash; the hash does not depend on line ends or key order.
- **On each build** (`ledger.update`, called by `registry.apply`): a file whose hash changed gets `last_updated` = the build's Puerto Rico date and one more
  version; a new file gets both dates (or keeps its old `first_published` when it was published before and removed); `first_published` never moves; counts
  and sizes follow the files without moving a date; a file no longer published moves to `removed` with the date. The history gets a row when the totals
  (files, bytes, records, fields, values, dictionary items) differ from its last row; a second build on the same day replaces that day's row. A rebuild with
  the same content changes nothing at all, so `registry.json` is not rewritten either (its `built` is the date its content last changed, and compressed sizes,
  which can differ by a few bytes between zlib versions, do not count as a change).
- **Backfill** (`python ledger.py --backfill origin/main`, run once on 2026-10-19 and again after merging main): the first-parent history of main, oldest first
  (`git log --first-parent --reverse`): each commit is a publication, since GitHub Pages publishes what reaches main. For each commit, the files under
  `site/data/` that changed against its first parent (`git diff-tree`) are read from git (`git cat-file --batch`), hashed and counted (cached by blob), and the
  same `update` runs with the commit's Puerto Rico date (committer time, UTC−4). 98 commits; 14 history rows from 2026-10-01 (13 files, 728,325 values) to
  2026-10-19 (77 files, 3,520,446 values). Backfilled dates are the days changes were merged into main; from 2026-10-19 on, the date of the build that changed
  the file, usually the day of the merge or a few days before it.
- **First-published dates** (backfilled): `flood.geojson`, `municipalities.json`, `municipios.geojson`, `places.json`, `landuse.geojson`, `barrios.geojson`,
  `housing.json`, `transport.json`, `trips.json`, `hurricanes.json`, `transit_routes.geojson`, `protected.geojson` and `meta.json` 2026-10-01;
  `roads.bin`, `gazetteer.json`, `housing_series.json`, `operators.json`, `population_blocks.json` 2026-10-02; `economy_series.json`, `dictionary.json`
  2026-10-05; the exposure files, the crosswalk, the WCRP points and `catalog.json` 2026-10-06; `transit_supply.json` 2026-10-09; `health_series.json`
  2026-10-12; the ACS small-area files and the education, health, infrastructure and environment series 2026-10-14; the facility, conditions and
  nonprofit files 2026-10-17; the community, landslide and age files 2026-10-18; the WCRP index and Social Capital files 2026-10-19.
- **Nightly refresh**: `refresh_network.py` runs `registry.apply()` last, in both of its paths, and `refresh-transit.yml` commits
  `dictionary_src/data_ledger.json` with `site/data` (and counts it when it decides whether anything changed). `rebuild.yml` already ran `registry.py`; it now
  commits the ledger too. Both bot pull requests therefore pass `python registry.py --check` in `tests.yml`, which compares hashes, counts and sizes and never a
  date with today.
- **Conflicts**: two branches that change data both change the ledger. Take main's `data_ledger.json` and run `python registry.py`: the branch's changed files
  get the build date.
- **Versions** count every build that changed a file's content. A branch built several times with different content counts each build, although only the last
  is published; before opening or updating a pull request, `python ledger.py --backfill origin/main` and then `python registry.py` count the branch once.

## 5. The Compliance review column

From the file's record in `dictionary_src/datasets.json` (`registry.review_of`):

| Status | Shown | When |
|---|---|---|
| `open` | Pendiente: *reason* / Open: *reason* (one line per open review) | a review is open; *reason* is the review's `summary` (`en`, `es`) |
| `cleared` | Aprobada AAAA-MM-DD / Cleared YYYY-MM-DD | every review was cleared; the latest `date` |
| `unstated` | Licencia sin declarar: *sources* / License not stated: *sources* | no review, and at least one source states no licence: a file takes the most restrictive licence class of its sources (`contract.py` enforces it), so the cell names the sources that set it (`review.licence_from`, from their `short` names in `sources.json`) |
| `none` | No requiere / Not required | nothing to review |

Flags beside it: **Contenido de fondos federales / Federal grant content** (`flags: ["federal-grant"]`: HUD CDBG-DR, FEMA assistance, federal awards; the
contract fails a file so flagged that has no compliance review), **Solo conteos / Counts only** (`counts-only`), **Licencia sin declarar: *sources*** (licence
class `unstated`, when the status is not already that) and **Con licencia, no abierta: *sources*** (`licensed-not-open`). A file's other sources may well be
licensed: `barrios.geojson` takes "License not stated" from the municipal GTFS feeds alone. The review filter's "License not stated" keeps every file of that
class (status `unstated` or the `licence-unstated` flag: 24 files). `contract.py` checks the flags and warns about an open
review with no summary or a cleared one with no date. The Spanish summaries of federal grant reviews say only "revisión de Finanzas y Cumplimiento del
contenido de fondos federales": Spanish that names the programs waits for Finance and Compliance (`i18n_src/held_for_review.json`, decisions 20 and 21).

On 2026-10-19: **7 open reviews in 6 files**: `places.json` (personal data: names of drawn places), `municipalities.json` and `housing.json` (licence: the
short-term rental figures licensed to FPR; withdrawn on 2026-11-23 with the figures), `housing.json`, `housing_series.json` and `economy_series.json` (federal grant content), `health_series.json`
(licence: HRSA's terms). Cleared: the four WCRP files (2026-10-19), `historic_places.geojson` (2026-10-18), `public_housing.geojson`,
`facility_series.json`, `conditions_series.json`, `conditions_barrio.json` (2026-10-17). Federal grant content: the four WCRP files, `housing.json`,
`housing_series.json`, `economy_series.json`. Counts only: `places.json`, `historic_places.geojson`, `community_series.json`, `public_housing.geojson`,
`facility_series.json`, `health_series.json`, `care_series.json`, `nonprofit_series.json`. License not stated: 24 files, from 9 sources (the municipal GTFS
feeds set it for 15 files).

Three source classes were checked again on 2026-10-19 (`sources.json`, `terms_note` and `verified`): **NOAA's Sea Level Rise Viewer** (the Digital Coast data
page and the 2017 metadata state no license or public-domain notice: access constraints "None", use constraints that are cautions), **USAspending.gov** (no
terms for the data on its pages; Data.gov's record of its raw files says no license information was provided; GAO-19-72 found the site gives no comprehensive
licensing information) and **NOAA's 2022 sea level rise scenarios** (no license; the notice restricts one use). None states public domain, so all three stay
`unstated` until the publisher states its terms. This is a record of what the publishers state, not a legal opinion.

## 6. What is not published

`registry.withheld` reads each count from the published file at every build; the page shows the count, the rule (in both languages) and the dictionary entry
that gives it. No name and no location appears.

| Row | Count on 2026-10-19 | Read from | Rule in the dictionary |
|---|---|---|---|
| Tourism places counted but not drawn | 1,005 of 32,541 (holiday rentals 971, named by a street address 34) | rows of `places.json` with `withheld` | `places.withheld` |
| Listings that are not tourism, left out | 2,577 | `meta.json` `counts.not_tourism_dropped` | `places.withheld` |
| Health center service sites (points kept in the local cache) | 160 (127 permanent, 33 mobile vans) | `health_series.json` `notes.sites` | `health.sites_method` |
| Shelters | 0 published (hurricane lists state no licence: `wanted.json` row `shelters`, blocked; domestic-violence and children's shelters never) | `wanted.json` | `data.wanted` |
| National Register listings that are private homes | 73 of 342 | `community_series.json` `notes.historic_places` | `layers.historic_places` |
| Public housing at an approximate location | 132 of 304 | `facility_series.json` `notes.public_housing` | `layers.public_housing` |
| Treatment facilities (counts by municipio only) | 87 | `community_series.json` `notes.treatment_facilities` | `community.bh_all` |
| Tax-exempt organizations (counts only) | 2,572 | `nonprofit_series.json` `notes.organizations` | `nonprofits.npo_all` |

## 7. The page

- **Summary first**: files, size (and its share of the 1 GB limit), records, values (and fields), documented items, last update. Then the table (sortable on
  every column, numbers right-aligned in tabular figures, a totals row for the files shown, a text filter, filters by kind and by review, a CSV of what is shown
  with a final totals row; the file column stays in view when the table scrolls, which it does in its own box at phone width), the growth chart (one measure at
  a time as a step line, with a crosshair readout by pointer and arrow keys, and the table of every date), what is not published, and the definitions.
- **Language**: page `datamgmt` in `i18n_src/pages.json` (scopes `common` and `datamgmt`), Spanish released. "License not stated" is "Licencia sin declarar"
  everywhere now (the common scope said "Licencia no indicada").
- **Public and indexable** (Francis, 2026-10-20, HANDOFF decision 56(a): "La página de gestión de datos debe aparecer a todo el mundo para ser
  transparentes (pero solamente nosotros podemos hacer cambios)."): the page has no robots tag, and its canonical link and share tags (`og:*`,
  `twitter:card`) are those of the other pages. The site has no sitemap or `robots.txt`, so nothing else lists it. The dictionary, the Housing page and the
  area profile stay `noindex, follow` until Compliance reviews the pages that describe grant-funded and federal-award data (decision 13), and the WCRP page
  `noindex, nofollow` while its "In review" marker is on (decision 51). `tests/test_ledger.py` (`Page`) fails if the page gets a robots tag again.
- **Read-only**: the page is static. It has no editing control, and the CSV button builds a download of the table in the browser; nothing is sent back. Its
  hero says so in both languages ("Esta página se genera automáticamente a partir del repositorio del observatorio; solo el equipo de Foundation for Puerto
  Rico puede modificar los datos, mediante cambios revisados."; scope `datamgmt`). What it shows changes only when `site/data` changes, and that reaches
  the site only through a pull request to the repository, which is private: Azure Static Web Apps publishes what reaches `main` (`pages.yml`, on push to `main`),
  and a ruleset on `main`, with no bypass, requires a pull request and the `checks` job of `tests.yml`, and blocks force pushes and deleting the branch.
  The ruleset sets no required number of approving reviews; the team reviews the pull requests people open before merging them. The automatic refreshes
  (`refresh-transit.yml`, `rebuild.yml`) open pull requests too: a routine source merges itself once the same `checks` pass, and a new vintage, a licence
  under review or public money waits for a person (`docs/automation.md`). Who can write to the repository is set in its GitHub settings; neither the page
  nor these docs name anyone.
- **Links**: the dictionary's "Published data files" section (anchor `#files`, kept) is now a summary with a link; the About texts of the map and the 3D view
  name the page; no top-bar button.
- **Weight** (`dictionary_src/routes.json`, route `datamgmt`: first `registry.json`; budget 35 KB of scripts, 33 KB of data, compressed). `registry.json` grows by one row for each published file: the data line went from 25 to 30 KB and, on 2026-11-24 with the jobs within reach series (30.1 KB), to 33 KB.

## 8. Glossary terms

Added to `dictionary_src/glossary.json` in the schema of the glossary (both languages, a source, match forms, highlight, priority), each citing this page's
definitions: Record, Field, Value (data point), Vertex, First published, Last updated, Content hash, Compliance review. Record and Field are not highlighted
(too common in running text); the others are. Part 2 (the highlighter) needs nothing more. Added on 2026-10-20 for the read-only note: Repository /
Repositorio (source: GitHub Docs, About repositories), highlighted.

## 9. Checks

```
python registry.py --check          the ledger and registry.json are current
python ledger.py --count places.json --fields
python -m unittest tests.test_ledger tests.test_workflows
node --test tests/datamgmt.test.js
node tests/browser/datamgmt_page.js http://127.0.0.1:8041 <shots folder>     (a headless Chrome on CDP_PORT and serve_gzip.js; es and en, 1400 and 390 px)
```
