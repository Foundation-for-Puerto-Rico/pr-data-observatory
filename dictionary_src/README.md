# Data dictionary: how it is built and how to add to it

The page `site/dictionary.html` is generated from the files in this folder by `python dictionary.py`, which writes `site/data/dictionary.json` and, made from it, the files the page reads: `dictionary_list.json` first and `dictionary_detail_<domain>.json` when an entry is opened (`docs/performance.md`).
The observatory's database only grows, so **every new dataset, field or layer needs an entry here, with domain tags**. `python dictionary.py --coverage` lists
anything published in `site/data/` that no entry documents; `build.py` runs it and warns. `build.py` also runs `python contract.py`, which checks the domain
registry and the data contract below and **stops the build on any violation**. The step-by-step guide for adding data is `docs/adding-data.md`.

```
dictionary_src/
  README.md        this file (the specification)
  domains.json     the domain registry: every domain and sub-domain, with Spanish and English names and descriptions, icon, accent, headline indicator (with its label and, for a municipal measure, the rule that gives the island figure), example questions
  groups.json      longer text for the dictionary page: a summary for a domain and a description for each group of entries (keyed by domain id)
  map_layers.json  which dictionary entries are a layer of the 2D map that the Catalog tab can switch on ("Add to map"); the value is the layer key of the page
  datasets.json    the data contract: one record per file in site/data/ (domains, geography, time type, sources, licence class, cadence, size tier, open reviews)
  sources.json     one record per source (publisher, link, licence, licence_class, credit line); "_aliases" maps old ids to canonical ones
  data_ledger.json written by registry.py (ledger.py), not by hand: each published file's first-published and last-updated dates, versions, content hash, size and counts,
                   and the history of the totals (docs/data-management.md); commit it with the data
  glossary.json    terms and abbreviations, each in English and Spanish and with its source (see "Glossary" below; docs/glossary.md)
  entries/*.json   JSON lists of entries, grouped in files by subject (the file name has no meaning for the page)
```

`domains.json` is the **only** place that lists domains. The dictionary page, the generated `docs/domains.md`, the data contract and (in later steps) the layers panel,
overview, catalog and chat read it. Adding a domain is adding one object to it; see `docs/adding-data.md`.

## Entry

```json
{
  "id": "municipalities.sfha_pct",
  "name": "Tourism places in a flood hazard area (%)",
  "domain": "economy.visitor-economy",
  "domains": ["economy.visitor-economy", "hazards"],
  "group": "Flood exposure of tourism places",
  "kind": "variable",
  "plain": "Out of every 100 tourism places in the municipality, how many sit inside a FEMA-mapped high-risk flood area.",
  "definition": "Tourism places whose coordinates fall inside a FEMA Special Flood Hazard Area (zones A, AE, AH, AO, A99, V, VE) divided by all tourism places in the municipality, times 100.",
  "unit": "% of tourism places",
  "value_type": "rate",
  "geography": "78 municipalities",
  "coverage": { "timeline": "snapshot", "first": 2026, "last": 2026, "frequency": "Rebuilt with each snapshot" },
  "method": "Point-in-polygon test of each place against the flood polygons, then a share per municipality. Places of worship are excluded.",
  "sources": ["overture", "fema_nfhl"],
  "source_detail": "Overture places; FEMA NFHL layer 28, DFIRM_ID LIKE '72%'",
  "how_to_read": "A high value means many of the municipality's visitor places could flood in a 1-in-100-year event. It says nothing about building elevation or insurance.",
  "caveats": ["Describes the mapped hazard at a point, not the building.", "A municipality with few places can swing widely."],
  "see_also": ["places.in_sfha", "layers.flood_zones"],
  "where": {
    "files": ["municipalities.json:sfha_pct"],
    "view": [{ "label": "Map, Layers tab: shade municipalities by", "href": "index.html#s=sfha_pct" }]
  },
  "added": "2026-10-01"
}
```

### Required fields
`id`, `name`, `domain`, `domains`, `group`, `kind`, `plain`, `definition`, `unit`, `value_type`, `geography`, `coverage`, `method`, `sources`, `where.files`, `added`.
Optional but expected where they apply: `source_detail`, `how_to_read`, `caveats`, `see_also`, `where.view`, `values` (for coded fields), `example`, `status`.

### Controlled vocabularies
- **domain** and **domains**: ids from `domains.json` (`python dictionary.py --domains` writes the current list to `docs/domains.md`). `domain` is the **primary** domain: what the thing measures *about*.
  `domains` lists the primary first, then any **secondary** domains (a school's flood flag is `["education", "hazards"]`). Entries that count tourism places inside a flood zone are about the places, so the primary
  is the visitor economy and the secondary is hazards. Documentation entries (methods, measures) use `system.docs`, the observatory's own tools use `system.tools`, boundaries use `system.geography`; a method written for one
  field takes that field as primary. Do not invent a domain for one dataset: see the placement guide.
- **kind**: `variable` (a number or code per place), `layer` (something drawn on a map), `table` (a table published in a study), `boundary` (a geography), `category` (a class in a classification), `measure` (a calculation the tools apply to variables), `method` (how something is done).
- **value_type**: `count`, `rate` (a percent or share), `level` (a typical value such as a median or a dollar amount), `ratio`, `index`, `flag` (yes/no), `code` (coded text), `text`, `date`, `geometry`.
- **coverage.timeline**: `snapshot`, `annual`, `five-year window`, `decennial`, `event-based`, `live`, `static`. `first` and `last` are years (numbers) when they apply.

### ids
`dataset.field`, lowercase letters, digits, `_`, `-` and `.`. Datasets: `places`, `municipalities`, `economy`, `housing`, `study` (published tables), `boundaries`, `hazards`, `land`, `transit`, `roads`, `layers`, `measures`, `methods`, `geo` (the geography crosswalk and the block table), `exposure` (residents and housing units inside hazards and protected land and near transit). For series use the catalog key: `economy.qcew_jobs`, `housing.median_gross_rent`.

### `where.files`
Every field of every published data file must be claimed by an entry, as `file:field`:
`municipalities.json:sfha_pct`, `places.json:category`, `flood.geojson:FLD_ZONE`, `economy_series.json:qcew_jobs`, `housing_series.json:vacancy_pct`.
Use `file:*` for a file that is documented as a whole (a binary, or a nested structure with its own entry), for example `roads.bin:*`. A file in a published subfolder is written with its folder: `geo/tracts.geojson:GEOID`, `geo/crosswalk.json:*`.
An entry may claim several fields. An entry that documents no data field (a method, a measure) leaves `files` as `[]`.

### Series variables (`economy.*`, `housing.*`)
`dictionary.py` fills `name`, `unit`, `coverage` and `sources` from the series catalogs and uses the catalog definition when `definition` is empty.
Your entry adds what the catalog cannot: `plain`, `method`, `how_to_read`, `caveats`, `see_also`, and a corrected `definition` when the catalog's is thin.

### `sources`
Use the canonical ids in `sources.json`. Old ids resolve through `_aliases`. Every entry names at least one source. Derived values name the sources of their inputs.

## Writing style (plain language; ISO 24495-1, W3C COGA, US Plain Writing Act)
- Lead with the answer. `plain` is one or two sentences a resident could repeat. Reading level about grade 8.
- Short sentences, active voice, concrete words. Say "people below the poverty line", not "poverty-status denominator". Define a term the first time it matters, or point to the glossary.
- Always give the unit and the year basis. Say who or what is counted (people, households, jobs, places, dollars of which year).
- Say what the number does **not** mean. Caveats are specific and true (suppression, survey margins, vintage breaks, workplace versus residence, snapshot dates).
- No marketing words, no hedging without a reason, no legal or tax advice. Licence text is what the source states; users must check the source's terms.
- No personal information of any kind (no names of private people, no contact details).
- Spell out acronyms once, in the glossary and the first use in each entry.
- Be exact: every claim must be checkable in the code (`build.py`, `housing_series.py`, `economy_series.py`, `network.py`, `transport.py`, `landuse.py`, `site/js/*.js`) or the data files.
- Write the entries in English. The Spanish summary of each entry (`plain` only) lives in `i18n_src/dictionary_plain.json`, keyed by entry id, with the English text it translates; `python i18n.py --check` warns for an entry without one, or whose English changed (see `docs/i18n.md`). The other fields are English only for now.

## Glossary (`glossary.json`)
One list of terms, the single source of truth for the Glossary section of the dictionary page and for the underlined words on every page (the highlighter, `site/js/core/glossary.js`; `docs/glossary.md`). `python dictionary.py` also writes the highlighter's four files from it (`site/data/glossary_forms_<lang>.json`, `glossary_defs_<lang>.json`). Unlike the entries, a term carries **both languages in the same record**.

```json
{
  "id": "data-file", "term": "Data file", "term_es": "Archivo de datos",
  "expansion": "", "expansion_es": "",
  "plain": "A file the observatory publishes in its data/ folder (JSON, GeoJSON or binary .bin), built from the sources; ...",
  "plain_es": "Archivo que el observatorio publica en su carpeta data/ (JSON, GeoJSON o binario .bin), construido a partir de las fuentes; ...",
  "source": { "name": "PR Data Observatory, data dictionary: Published data files", "name_es": "Observatorio de Datos de PR, diccionario de datos: Archivos de datos publicados",
              "url": "https://observatory.foundationpr.org/dictionary.html#files", "checked": "2026-10-19" },
  "match": { "en": ["data file", "data files"], "es": ["archivo de datos", "archivos de datos"] },
  "case_sensitive": false, "highlight": true, "priority": 1,
  "see_also": ["data.registry"], "section": "files"
}
```

- **Required** (`dictionary.py --check` and the build fail without them): `id` (the term's anchor, `g-<id>`: the English term without accents, lower case, other characters as `-`), `term`, `plain`, `plain_es`, `source` with `name`, an `https` `url` and the date the link was `checked`, `match.en` and `match.es`, `case_sensitive`, `highlight`, `priority`.
- **Definitions** are precise and technical, then plain: lead with the exact meaning, keep the standard term (estimate, margin of error at 90% confidence, median, percentile, block group, polygon, GeoJSON RFC 7946) and give units, confidence levels and standards; one or two sentences, in our own words (never copied from the source). The rule is in `docs/glossary.md`.
- **Source**: an official or authoritative page that defines the term (Census Bureau, FEMA, BLS, EPA, HUD, HRSA, NOAA, USGS, an IETF RFC, the GTFS reference, the OpenStreetMap wiki). For the observatory's own words, cite the dictionary entry or section that defines them (`dictionary.html#<entry id>` or `#files`); `dictionary.py` checks that the anchor exists and `--links` checks the link. Record the date you opened the link (`checked`, a real date written YYYY-MM-DD). A source on the observatory's own pages also needs `name_es`, its Spanish name, which Spanish pages show.
- **Matching**: `match` lists the exact forms to find in each language (plurals, accents, acronyms). A form written in capitals (an acronym: `STR`, `SFHA`) always matches only in capitals; `case_sensitive: true` makes every form of the term match its exact capitals (`PUT`, `AMA`, `Tren Urbano`). `highlight: false` for words too common to mark in running text (`rate`, `layer`, `barrio`). A form of a highlighted term may name only one term. When a longer name starts with a term's form but means something else, give the longer name as a form of its own term (HUD's "Departamento de la Vivienda y Desarrollo Urbano" starts with PRDOH's "Departamento de la Vivienda"): the longest form wins.
- **`priority`**: 1 blocks understanding of what the pages show, 2 helps, 3 is background.
- **`hold_es: "compliance"`**: the Spanish waits for Finance and Compliance review (federal grant content, HANDOFF decision 20). It stays here, but the published files leave out `plain_es`, `expansion_es` and the source's `name_es`, so Spanish pages show the English definition. WCRP, CDBG-DR and HUD were released under decision 51 (the WCRP wording the project lead approved on 2026-10-19).
- Optional: `term_es`, `expansion_es`, `see_also` (entry ids), `section` (`browse`, `sources`, `files`, `cite`), `highlight_why` (below), `not_match` (below).
- **`not_match`**: `{lang: [phrases]}`, longer phrases that hold one of the term's forms but are not the term (per capita: `{"es": ["por residente empleado"]}`). Where one is the longest match, the highlighter marks nothing. Each phrase must hold a form of the term in its language.
- **`highlight_why`**: a priority-1 term that appears in the interface (the static text of the pages or any string in `i18n_src/es/*.json`) must be highlighted. To leave one unmarked, set `highlight: false` and say why here; `dictionary.py` fails otherwise, and fails `highlight_why` on a highlighted term.
- **Standing rule**: a change that shows a new technical word on a page adds its term here, with a source, in the same PR, and runs `python dictionary.py`. The highlighter then underlines the word on every page by itself; no page needs a change. A page can mark a term on purpose, even in a heading, with `data-gloss="<id>"`, and keep a part unmarked with `data-gloss="off"`.

## The data contract (`datasets.json`) and licence classes

One record per file in `site/data/`. `python contract.py` fails when a record breaks a rule; the build runs it. A file without a record fails too.

| Field | Rule |
|---|---|
| `id`, `file`, `title.en`, `title.es` | unique id; the file must exist (a name in `site/data`, or in its `geo/` subfolder: `geo/crosswalk.json`); titles in both languages |
| `domains` | primary first; every id in `domains.json` |
| `geography.level` | island, region, municipio, barrio, tract, block-group, block, point, line, polygon, raster, network or none; levels with ids need `geography.key` |
| `geography.key`, `joins_to` | where the join ids are: `object-keys`, `field:NAME` or a dotted path (`geo.ids`). They are checked against the geography crosswalk (`site/data/geo/crosswalk.json`: tourism regions, 78 municipios, 901 barrios, 981 tracts, 2,555 block groups; see `docs/geography.md`). `joins_to` names the level when `geography.level` is not one of those (`region`, `municipio`, `barrio`, `tract` or `block-group`); more than 1% unmatched rows fails the build |
| `geography.ids_not_published` | block level only: `true` when the 15-digit block ids are kept out of the file on purpose (say why in `note`); otherwise a block-level file needs `geography.key` |
| `time.type` | point, period, window, vintage, snapshot, event or static; `years_path` lets the build check `first` and `last` against the file |
| `sources` | ids in `sources.json` |
| `licence_class` | open, open-with-conditions, own, unstated or licensed-not-open; never laxer than the worst class among the sources; licensed-not-open needs a `licence` review |
| `cadence` | static, snapshot, annual, monthly, weekly, daily, live or as-needed |
| `tier` | small (up to 1 MB), medium (up to 8 MB), large (up to 50 MB); a file over its tier fails |
| `review` | open questions about personal data (`pii`), licence or federal-grant compliance, each with a note. They are listed at every build until cleared. An open review has a short `summary` (`en`, `es`) and a cleared one the `date` it was cleared: the Data management page shows them in its Compliance review column |
| `flags` | optional: `federal-grant` (federal grant money or a grant-funded program; needs a `compliance` review) and `counts-only` (sensitive items counted but not drawn or named) |

Licence classes (also on each data source in `sources.json`): **open** (public domain or equivalent), **open-with-conditions** (an open licence with credit or share-alike, such as ODbL or CC BY),
**own** (FPR's own work), **unstated** (published, but the source states no licence: confirm before relying on it), **licensed-not-open** (needs written permission; publication must be documented).

Personal data: the build fails when a published file has a column named like personal or business contact data (address, website, email, phone, contact, mayor, contractor and similar) or values that look like
an email address, phone number or SSN, unless a `pii` review names it. The project rule is never to publish business contact details or any personal data; aggregated data only.

## Commands
```
python dictionary.py                   build site/data/dictionary.json and the page's files (dictionary_list.json, dictionary_detail_*.json)
python dictionary.py --check FILE...   validate entry files (schema, ids, sources, domain tags, cross-references)
python dictionary.py --coverage        list published fields that no entry documents
python dictionary.py --links           check that every "where it appears" link opens something real
python dictionary.py --index [DOMAIN]  list entries; --dump [DOMAIN] prints them in full (DOMAIN is a registry id; a parent includes its sub-domains)
python dictionary.py --domains         write docs/domains.md from the registry
python contract.py [--reviews]         check the domain registry and the data contract
python -m unittest discover -s tests   tests for the validators
```
