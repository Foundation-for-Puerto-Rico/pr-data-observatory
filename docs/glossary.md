# In-page glossary: content (part 1) and highlighter (part 2)

Francis asked on 2026-10-19, looking at the dictionary's "Published data files" table, "¿Qué consideras un data file?", and then for every technical word in the observatory to be defined with a source, shown with a highlight on the word and readable by holding the mouse over it. The goal is that a reader can answer that kind of question on the page.

- **Part 1 (PR #73, `glossary-terms`):** the content. `dictionary_src/glossary.json` holds 297 terms (252 in PR #73; PR #74 added 8 for the data management page; Repository was added on 2026-10-20 for that page's read-only note; Línea PAS on 2026-10-21 for the Ask chat's crisis replies; PR #72 added 13 for the Route analysis page on 2026-10-21: HPMS, FHWA, AADT, K factor, design-hour volume, peak hour, high-volume intersection, scheduled speed, signalised junction, roundabout, pedestrian bridge, express route, timepoint; the Global Innovation Index page added 15 on 2026-10-23: GII, pillar, sub-pillar, composite index, WGI, government effectiveness, regulatory quality, rule of law, PPP, GERD, gross enrolment ratio, school life expectancy, pupil-teacher ratio, inbound mobility, UIS; and 7 more the same day for its update 2: min-max normalization, winsorization, log transformation (GII), interquartile range, skewness, kurtosis, indicative position; and 4 on 2026-10-26 for the updated privacy note of the 2D map's Info tab: map tile, HTTP header, code library, terrain tile), each with an English and a Spanish definition, a source with the date its link was checked, the forms to find in text and a highlight flag. The dictionary page's Glossary section shows the sources. `dictionary.py` fails a term without a source or without both languages.
- **Part 2 (`glossary-highlight`):** the highlighter, `site/js/core/glossary.js`. It underlines the first occurrence of each term in each section of every page and shows its definition and source on hover, keyboard focus or tap. It needed no page markup beyond the version of `common.js` and two marks on purpose on the dictionary page (section 2).

What the observatory means by a data file, in the glossary's words: *Archivo que el observatorio publica en su carpeta data/ (JSON, GeoJSON o binario .bin), construido a partir de las fuentes; las páginas lo leen para dibujar mapas y tablas, y cualquiera puede descargarlo.*

## 1. The content (part 1)

### One source of truth
`dictionary_src/glossary.json`, specified in `dictionary_src/README.md` ("Glossary"). `python dictionary.py` copies it, sorted, into `site/data/dictionary.json` and `site/data/dictionary_list.json` (the dictionary page reads the second). Part 2 builds its small files from the same list; nothing else holds a definition.

### Writing rule for every definition (Francis, 2026-10-19)
The site is moderately technical on purpose, so that a technically trained reader sees that the observatory is accurate. Write like a statistician or an engineer:
- **Keep the standard term**, do not swap it for a lay word: estimate, margin of error (90% confidence), median, percentile, quintile, block group, polygon, GeoJSON (RFC 7946).
- **Lead with the exact technical meaning**, then add a plain clarification if one helps.
- **Give units, confidence levels and standards** where they apply (MW, km², 90% confidence, RFC 4180, the 0–9 bridge rating scale).
- **One or two sentences**, readable, in our own words. Never copy the source's text.
- **Spanish** follows `docs/i18n.md` (terminology table, formal register). Claude drafted it, so a native speaker should review it before it is promoted as community-facing text.

### Sources
Every term names an official or authoritative page that defines it: the Census Bureau's glossaries and the ACS handbook (chapter 7 for estimates, margins of error at 90% confidence, sampling error and statistical significance), FEMA's flood zone glossary, BLS, GAO's budget glossary, EPA, HUD, HRSA, NOAA, USGS and the PAD-US Standard Tables, IETF RFC 7946, 8259 and 4180, the GTFS reference, the OpenStreetMap wiki, the NIST/SEMATECH statistics handbook and the NIST Dataplot manual. Type I crimes cite the Police's own municipal table (December 2022 report, published by the Instituto de Estadísticas): it has eight Type I columns, human trafficking included, while the Instituto's product page lists seven; the observatory reads the Police's eight. For the observatory's own words (data file, snapshot, the 400 m rule, counted not drawn, domain, público, base map, cost burden), the source is the dictionary entry or section that defines them (`dictionary.html#<entry id>`, `#files`, `#browse`, or `wcrp.html`). These 55 sources also carry a Spanish name (`source.name_es`), which Spanish pages show. `dictionary.py` checks that the anchors exist and that the Spanish name is there, and `dictionary.py --links` checks those links with the others.

All links were opened on 2026-10-19 (`source.checked`):
- With `curl` and a browser user agent: HTTP 200, title read.
- bls.gov, fema.gov and gao.gov refuse curl (403), so those pages were opened with a page-reading tool, which confirmed each title.
- transit.dot.gov, bts.gov, hrsa.gov and its subdomains (except data.hrsa.gov), hhs.gov and ems.gov refuse automated clients from this network: curl, the page-reading tool and a headless browser all got 403. They open in a normal browser: the review of PR #73 opened `ems.gov/what-is-ems/`, `nhsc.hrsa.gov`, `hrsa.gov/about`, `hhs.gov/about`, `bts.gov/about-bts`, `transit.dot.gov/ntd` and `bphc.hrsa.gov/about-health-center-program/what-health-center` on 2026-10-19, so the terms cite these original pages. FTA cites the `transit.dot.gov` home page, on the same site as the NTD page.
- `source.checked` must be a real calendar date (`date.fromisoformat`, written YYYY-MM-DD).
- **Línea PAS** (`linea-pas`, checked 2026-10-21): when the links are re-checked, also re-open ASSMCA's pages and confirm the number 1-800-981-0023, the hours and the chat address, because `--links` checks only that the link opens and the chat gives this number in its crisis replies (`docs/ask.md`, "Línea PAS").

### Held Spanish
A term whose Spanish is about federal grant money has `hold_es: "compliance"`. This covers 45 terms: LIHTC, OpenFEMA, USAspending, IHP, Public and Individual Assistance, obligation, de-obligation, award types, place of performance, disaster declaration, loan subsidy cost and "recorded as statewide", and since 2026-10-30 (Public money v2, step 1) damage category, Section 406 mitigation, Hazard Mitigation Assistance, HMGP, subapplication and federal share, and since 2026-10-31 (step 2) assistance listing, Pell Grant, Head Start, Project-Based Rental Assistance, Social Security disability benefits and veterans disability compensation, in step 3 single audit, Federal Audit Clearinghouse, pass-through entity and federal awards expended, and in step 4 New Markets Tax Credit, qualified low-income community investment, Community Development Entity and placed in service, and since 2026-11-11 (Public spending, decision 96, steps 1 and 2) subaward, subrecipient and outlay, since 2026-11-17 (decision 109, step 2) project closeout, since 2026-11-12 (decision 100) CDBG, CDBG-MIT, entitlement grant and the CDBG State program, and since 2026-11-18 (decision 110, step 1) period of performance, and (step 3) audit finding, repeated finding and questioned costs. The rule is HANDOFF decision 20, and the same set is held in `i18n_src/held_for_review.json`.
- **Released under decision 51.** Francis approved the WCRP wording on 2026-10-19, its funding line included (Foundation for Puerto Rico runs WCRP in collaboration with PRDOH, with CDBG-DR funds from HUD). The WCRP, CDBG-DR and HUD terms use that framing, without the 2023 housing study, LIHTC or Table 10, and their Spanish is published. `tests/test_glossary.py` lists them as explicit exceptions.
- The Spanish stays in the source file.
- The published files leave out `plain_es`, `expansion_es` and the source's `name_es`, so Spanish pages show the English definition, marked `lang="en"`.
- `tests/test_glossary.py` guards this.
- To release a term, delete its `hold_es` and run `python dictionary.py`.

### Inventory (how the terms were chosen)
The terms were found by scanning the visible text of every page: the static HTML of the six pages, every interface string (the English keys and Spanish values of `i18n_src/es/*.json`, which include the legends and the help texts), the names and summaries of the 859 dictionary entries and the catalog. The scan counted the acronyms and the candidate words. Each term's match forms were then counted again in the same text.
- 196 of the 252 terms appear in visible interface text (counted after merging main with the `layer-menu` PR).
- The other 56 appear only in the dictionary's entries.
- `priority` ranks the terms: 1 blocks understanding of what a page shows (52 terms), 2 helps, 3 is background.
- The most frequent priority-1 terms in the interface: the 400 m rule, estimate, dataset, sea level rise, WCRP, ACS, median, current timetable, tourism place, OpenStreetMap, scheduled stop, licence, SFHA, straight-line distance, FEMA, USGS, margin of error, NOAA.

### Matching data
- `match.en` and `match.es` list the exact forms to find: plurals, accents and acronyms.
- A form written in capitals (STR, SFHA, CHAS, RVI) matches only in capitals, whatever the term's flag.
- `case_sensitive: true` makes every form of a term match its exact capitals (PUT, AMA, Tren Urbano). Terms whose phrases also appear capitalised in labels (CHAS, 303(d), nameplate capacity, VE zone, RVI, FTE, HPSA, HHI, GAP status, NTEE) are `false`: their acronyms still match only in capitals, and their phrases match "Severe housing problems" as well as "severe housing problems".
- **Word edges.** A form's first or last character that is a letter or a digit must not touch another letter or digit (accented letters count as letters), so "rate" never matches inside "separate". An edge that is punctuation needs no boundary: ".geojson" and ".bin" match the end of "flood.geojson" and "roads.bin", and the mark covers the whole file name (the run of characters without spaces that ends in the extension).
- **Forms that were too ambiguous were removed:** Spanish "nominal", "incumplimiento", "obligado", "obligación", "quinto", "mediano" (only "ingreso mediano", "valor mediano" and "alquiler bruto mediano" stay), "duplicados", "Tipo I"; English "fifth", "Type I", "pooled", "scatter". The longer phrases stay.
- `highlight: false` marks words that are too common to underline in running prose. There are 37, such as rate, share, layer, barrio, municipio, household and timetable; 215 terms are highlighted. They stay in the Glossary section, and a page can still mark one on purpose (`data-gloss`, below).
- A form of a highlighted term may belong to only one term. `dictionary.py` checks this.

## 2. The highlighter (part 2)

Built in the `glossary-highlight` PR (2026-10-19), from the design part 1 wrote here. The changes from that design are listed under "What changed from the design".

### What a reader sees
- The first occurrence of each technical term in each section of a page has a dotted underline in `--color-primary-dark`. The text keeps its font, weight, colour and `lang`.
- Pointing at the word (150 ms), focusing it with the keyboard or tapping it opens a tooltip with:
  - the term, with its expansion when the name does not already hold it ("CDBG-DR Subvención en Bloque para el Desarrollo Comunitario – Recuperación ante Desastres");
  - the definition in the page language;
  - "Fuente: / Source:" and the source's name, linked (new tab, `rel="noopener"`), with the date its link was checked;
  - "Ver en el glosario / See in the glossary", a link to `dictionary.html#g-<id>` (on the dictionary page, `#g-<id>`);
  - "Ocultar los subrayados / Hide the underlines" (see "Turning it off").
- A term held for Compliance review (the 13 terms of part 1, the six FEMA terms added on 2026-10-30, and the six program terms and four audit terms added on 2026-10-31) shows its English definition on Spanish pages, marked `lang="en"`, as the dictionary does. A source without a Spanish name and an English-only expansion are marked `lang="en"` too.
- The tooltip stays inside the window with a 16 px gutter: under the whole word (a word on two lines keeps both lines visible) at the left of the line under the pointer, or above it near the bottom of the window, at most 340 px wide, so at 390 px it fits between the gutters (measured: 34 to 374 px).

### Module
- **`site/js/core/glossary.js`** (`Core.glossary`, plain script, no dependencies). Its pure parts run in Node for the tests: `formCs`, `formsFrom`, `defsFrom`, `compile` (the matcher), `skipped`, `sectionOf`, `selfOf`, `plan` and `tipHtml`. In a page it also has `mark(el)`, `observe(el)`, `hide()`, `state` (`loading`, `on`, `off` or `error`), `marks` and `stats` (the main-thread time of its passes).
- **Loaded once the page has its data.** `common.js` (every page but 404: the map, 3D, area profile, Knowledge Area, WCRP, dictionary and data management) waits for the `load` event, then for an idle moment (`requestIdleCallback`, 2 s at most) in which no data file is being fetched: `fetchRetry` counts the fetches in flight (`netBusy`). `netBusy` does not count what a page's libraries fetch, such as the 3D view's map style, tiles and terrain, so a page that marks the moment it is ready to use (`performance.mark('ready')`: the map, the 3D view, the WCRP page and the data management page, listed in `READY_PAGES` by the `data-page` of `i18n.js`) also waits for that mark, for two minutes at most (since 2026-10-20: with slow tiles, the 3D view used to fetch the match forms about 30 s before it was ready). Then it adds the script tag. No page lists the script in its HTML, so it stays off every page's budgeted first load, and no page needed its own hook or markup.
  - This also waits for each page's "later" files (the 3D view's trips, the area profile's other fields), so the glossary never competes with them.
  - After 60 tries (30 s to 2.5 min) it loads anyway, in case a request hangs.
  - The 404 page has no technical words and does not load `common.js`, so it has no glossary.
- **Its styles** are in the script (about 1 KB raw) and are added to the page with it, so `twin.css` and its version number did not change.
- **Its Spanish** is the module `glossary` of every page (`i18n_src/es/glossary.json`, 12 strings; `site/i18n/es.<page>.glossary.js`, about 1.1 KB each, 0.6–0.7 KB compressed), loaded with `I18N.load('glossary')` by the module itself. The page bundles did not change.

### Data
`python dictionary.py` writes four files from the published glossary, so held Spanish never reaches them:

| File | What it holds | gzip | When a page fetches it |
|---|---|---|---|
| `data/glossary_forms_es.json`, `_en.json` | each highlighted term's id, match forms, and for each form whether it is compared with its capitals | 4.4 KB es, 4.0 KB en | just after the page is ready (`later`) |
| `data/glossary_defs_es.json`, `_en.json` | every term's tooltip: name, expansion, definition, source name, URL, date checked, and which of these are English on a Spanish page | 30.3 KB es, 27.7 KB en | the first time a reader points at a word (`on_use`) |

- The forms file holds the 222 highlighted terms. The definitions file holds all 261 terms, so a page can mark a term that is not highlighted on purpose (`data-gloss`, below).
- The dictionary page fetches neither: it builds both from its own copy of the glossary (`dictionary_list.json`) with `formsFrom` and `defsFrom`. `tests/glossary.test.js` checks that the module and `dictionary.py` give exactly the same files, so the capitals rule is the same in Python and in JavaScript.
- `routes.json` lists the Spanish files for the map, 3D, profile, Knowledge Area, WCRP and data management routes, and nothing for the dictionary. The contract (`datasets.json`) has a record for each file.

### Matching
- **Letter trees, not a regular expression.** The forms of a language go into two trees of characters, one compared in lower case and one with its capitals. A text is read once, left to right. One regular expression with the Spanish forms (368 of them then; 377 now) took about 600 ms the first time it ran (Node), most of it compiling; the trees build in a few milliseconds, and in Node they read the 190 KB of Spanish interface strings in about 20 ms.
- **The rules of part 1:**
  - The longest form wins at a given place ("census block group" over "block group", "Special Flood Hazard Area" over "flood hazard area").
  - A form's first or last character that is a letter or a digit must not touch another letter or digit; accented letters and combining accents count as letters. So "estimado" is not found in "subestimado" and "JSON" is not found inside "GeoJSON".
  - A form written in capitals (SFHA, MOE) matches only in capitals, and `case_sensitive` makes every form of a term exact. Other forms match in any case, accented capitals included ("MÁRGENES DE ERROR"); a form keeps its accents ("margenes de error" is not found).
  - Any run of white space, a line break or a no-break space included, matches the space between two words of a form.
  - An extension form (".geojson", ".json", ".bin") marks the whole file name, "data/flood.geojson", and takes the place of a match inside it.
- **Data fix.** PRDOH's Spanish form "Departamento de la Vivienda" also starts HUD's Spanish name, "Departamento de la Vivienda y Desarrollo Urbano". HUD now has its full name as a form in each language, so the longer name wins. A scan of the interface text for forms followed by a longer proper name found no other case.
- **Phrases that are not the term (`not_match`).** A term can list longer phrases that hold one of its forms but mean something else. Where such a phrase is the longest match, nothing is marked and the reading goes on after it. Per capita has one: "por residente empleado" (jobs per employed resident) is not a per-capita figure. In the forms file a phrase is a form with "!" in front; `dictionary.py` fails a phrase that holds none of the term's forms, and a form that starts with "!".
- **GTFS-Realtime** is a form of GTFS-RT in both languages, so "el archivo GTFS-Realtime de la ATI" is one mark of GTFS-RT, not GTFS and a stray word (the review of PR #76).

### What it marks
- **Sections.** A term is marked once in each section: the nearest `section`, `article`, `details`, `aside`, `dialog`, `main`, `nav`, `header`, `footer` or `fieldset`; a side-panel tab (`.tab-page`), a layer group (`.fold`), a legend (`.legend-box`, `.map-legend`, `.econ-legend`), a pop-up's content, the help pop-up, a source card, a dictionary entry's body, a profile field, a domain of the dictionary's list, each term of the Glossary, or the body. An element with `data-gloss-root` is a section too, and with `data-gloss-root="one"` it is one section with everything inside it: the dictionary's "Sources and licenses" uses it, so its 150 source cards mark each term once, not once per card.
  - A term already marked in a section is not marked again when the section draws more text. A section that is redrawn (its marks gone) gets its marks again.
  - A term's own definition in the Glossary does not mark the term.
  - On the dictionary page, English text on the Spanish page (`lang="en"`: definitions, methods, cautions) is read with the English forms.
  - The dictionary's Glossary list carries `data-gloss="off"`: the reader is already in the glossary there. An entry's body, once opened, marks each term once.
  - Text whose own element is not shown (`display: none`: the `hidden` attribute, a subtitle a page hides at its width) is not marked and does not take the section's first occurrence. The observers watch the `hidden` attribute, so a part that shows later (a layer group opened, a note shown) is read then. A tab that is not in front is read as usual: its text's own elements are shown.
- **Skipped:** headings (`h1`–`h6`), `a`, `button`, `input`, `select`, `textarea`, `label`, `option`, `summary`, `legend`, `dt`, `caption`, `code`, `kbd`, `pre`, `samp`, `var`, SVG and canvases; `[role]` button, link, tab, switch, checkbox, radio, option, menuitem (and its checkbox and radio kinds), slider, tooltip, heading and the like; `[aria-hidden=true]`, `[translate=no]`, `[contenteditable]`, `[data-gloss]`, `[data-no-glossary]`; icons (`.ms-icon`), `.sr-only`; the chat (`#chat`); the map's labels, markers, tooltips and controls (every Leaflet pane but the pop-up pane, `.leaflet-control`, `.maplibregl-ctrl`, `.maplibregl-canvas-container`, `.maplibregl-marker`, `.muni-label`); the hover boxes, the 3D tooltip and the data management chart's tooltip; the language switch, the loader and the toasts.
- **On purpose.** `data-gloss="<term id>"` marks the term's first form in that element, even in a heading, or the element's whole text when the term is not highlighted. Two marks are in place:
  - the dictionary's "Dominios / Domains" sidebar heading (`dictionary.js`);
  - the "Archivos de datos publicados / Published data files" heading (`dictionary.html`).

  `data-gloss="off"` keeps a part of a page unmarked.
- **Not inside a control (`data-no-glossary`).** A mark is a focusable button (`tabindex="0"`), so in a control it would add a second Tab stop and put a focusable inside a focusable, which screen readers and the keyboard cannot use. Text with an interactive control anywhere above it, up to the page's root, is never marked: the tags and roles in the list above. A part of a page that is made of controls without being one, such as the rows of a list of buttons, carries `data-no-glossary` (any value, or none): nothing under it is marked, now or when its content is drawn again (the observers read the same rule). The "layers on" chip of the 2D map and the 3D view (`#alWrap`, `core/activelayers.js`) carries it, so a layer's name in its list is not a stop between its × buttons. A term that appears only in a control is then not underlined; the control's own label and tooltip stay, and no `title` with the definition is added. `data-gloss="off"` does the same; `data-no-glossary` says why. **Marks on purpose follow the same rule** (2026-10-27, branch `osm-inspector`, from the review of the `glossary-controls` branch): `markExplicit` leaves an element with `data-gloss="<term id>"` unmarked when it is, or sits under, an interactive control or `data-no-glossary` (`inControl` in `core/glossary.js`). A heading, code or other non-interactive skip does not stop it, as before. The Route analysis table's rows (`#rcBody`, focusable `tr`) and the Ask page's message (`#chToast`, which used the unknown value `data-gloss="skip"`) carry `data-no-glossary`.
- **The mark:** `<span class="gl-mark" tabindex="0" role="button" data-gl="<id>">`; the word the tooltip is open for also has `aria-describedby="gl-tip"` while it is open (below). Text in a flex or grid box is first wrapped in a plain `<span class="gl-run">`, so the box keeps one item and nothing moves (found on the dictionary's counts, whose labels are flex boxes).

### Content drawn later
- **Map pop-ups** come through the libraries themselves: the module wraps `L.Popup.prototype.update` (Leaflet: the 2D map, Knowledge Area, WCRP, every map made later) and `maplibregl.Popup.prototype.setDOMContent` and `addTo` (the 3D view), so a pop-up is read when the library fills it. The map containers themselves are not observed: the tiles, shapes, markers and labels that change while a map moves cause no work.
- **Everything else** comes through one `MutationObserver` per content container, with `childList` and `subtree` only: the side panel (`#panel`: its tabs, the Economy panel, the legends in it), `.map-legend`, `.econ-legend`, the workbench and land-use views (`.econ-bench`), dialogs, the help pop-up, every `main` but the maps' (the Knowledge Area, WCRP with its details sections and area panel, the dictionary, the profile and data management) and the `.dict-side` columns. A container added to the body later is watched as it arrives.
  - A change in a skipped place (the 3D clock in its label, a slider's value) is remembered and ignored from then on, at the cost of one lookup.
  - The marks' own changes are dropped (`takeRecords`), and a text node is read once.
- **Throttled.** Changes are collected for 150 ms, then read in the browser's idle time in slices of about 8 ms (the text is read up to 6 ms, then every box is read before anything is written, so a slice costs one style pass). Nothing runs while the page scrolls, while a map is dragged (pointer down on a map) or for 300 ms after a wheel turn, a scroll or a drag.

### Tooltip behaviour
- **Hover** (mouse or pen): opens after 150 ms; moving from the word into the tooltip keeps it open; leaving both closes it after 250 ms.
- **Keyboard:** Tab onto a word opens it at once (only for keyboard focus, `:focus-visible`, so a click or a focus a library gives does not). Enter or Space moves the focus into it (it is then a non-modal dialog); Tab goes through its links and back to the word. Esc closes it. When the focus was on the word or in the tooltip, it goes back to the word and the key stops there; when the focus is elsewhere (a search box, the chat's input), the focus stays where it is and the key goes on to the page.
- **Touch:** a tap opens it; a second tap on the word closes it; a tap anywhere else closes it. A click with the mouse pins it the same way.
- **Accessibility:** one tooltip per page, `<div id="gl-tip" role="tooltip">`, made as the module starts. Only the word it is open for has `aria-describedby="gl-tip"`, set when it opens and taken off when it closes, and the tooltip is emptied when it closes, so no word is ever described by another word's definition (the review of PR #76 found every mark described by whatever the tooltip last held). Once the definitions are in, a keyboard focus fills it in the focus event itself, so the description is there when a screen reader reads the word. As a tooltip it has no label of its own, so what a screen reader hears as the word's description is the term, the definition and the source (checked in Chrome's accessibility tree); when Enter makes it a dialog it is labelled "Definición de {term} / Definition of {term}". Its Close button comes last. In a modal dialog it moves into the dialog, which is in the top layer.
- It closes when the page scrolls or the window changes size.
- **Print:** the dotted underlines and the tooltip are not printed (`@media print`).

### Turning it off
- "Ocultar los subrayados / Hide the underlines" in the tooltip removes every mark (the text is put back as it was) and is remembered in `localStorage` (`twin.gloss` = `off`, inside `try`/`catch`). The tooltip then says how to turn them on again; when that note closes, the focus goes back to where the word was (its element, focusable for the moment), not to the page's body.
- The dictionary's Glossary section has a switch, "Subrayar los términos técnicos en todas las páginas / Underline technical terms on every page", that turns them on and off.
- With the underlines off, the module still loads (13.6 KB compressed, after the page is ready) but fetches nothing.
- **For the regression captures** (`tests/browser/README.md`), which compare a page's HTML: turn the underlines off first (`localStorage.setItem('twin.gloss', 'off')`), or take the captures before the glossary loads.

### Weight and speed
Measured on LF copies (`git -c core.autocrlf=false archive`) of main (b7c4995, after PRs #74 and #75) and of this branch, `budget.py`, gzip level 6. The budgeted figures grow only by the loader in `common.js` (about 0.25 KB); the dictionary also by its `data-gloss` attribute.

| Page | Scripts, main → branch (budget) | Data before ready | Data just after ready | Data on first use |
|---|---|---|---|---|
| Map | 243.3 → 243.5 (250) | 145.6 → 145.6 | 0 → 4.4 | 61.5 → 92.0 |
| 3D | 640.0 → 640.3 (700) | 544.2 → 544.2 | 325.1 → 329.5 | 8,944.1 → 8,974.6 (the layers of #75 on demand) |
| Area profile | 99.0 → 99.2 (120) | 539.5 → 539.5 | 103.1 → 107.5 | 0 → 30.5 |
| Knowledge Area | 164.1 → 164.3 (180) | 305.4 → 305.4 | 0 → 4.4 | 0 → 30.5 |
| WCRP | 79.6 → 79.8 (80) | 125.2 → 125.2 | 0 → 4.4 | 938.5 → 969.0 |
| Data management | 30.0 → 30.2 (35) | 11.4 → 11.8 | 0 → 4.4 | 0 → 30.5 |
| Dictionary | 30.8 → 31.0 (40) | 549.1 → 549.5 | 0 → 0 | 611.7 → 611.7 |

- `common.js` grows from 5.9 to 6.2 KB (the fetch counter and the loader); the dictionary's `dictionary.js` by 17 bytes (its `data-gloss`). The data before ready grows by the new files' rows in `registry.json` and `catalog.json` (the size of every file), and by the new forms (HUD, GTFS-Realtime, the per-capita phrase).
- The WCRP page keeps 0.2 KB of its 80 KB script budget.
- Not budgeted, fetched after ready: `js/core/glossary.js` 13.6 KB, its Spanish 0.6–0.7 KB, the forms 4.4 KB (Spanish; 4.0 KB English). The definitions (30.3 KB Spanish, 27.7 KB English) wait for the first use.

**On Slow 4G** (`tests/browser/throttle.js`: 150 ms, 1.6 Mbit/s; Spanish; first loads with the cache off; LF copies of main, cbd20cd, and of this branch served with gzip; 3 runs each; before the merge of #75 and the fixes of the review, which added 1 KB to the module):

| Page | Ready, main | Ready, branch | Transferred by 1.6 s after ready, main → branch | Underlines in |
|---|---|---|---|---|
| Map | 4.7 s | 4.7 s | 719–720 → 738 KB | 6.1–6.2 s |
| 3D | 16.8–16.9 s | 16.5–16.6 s | 2,701–2,842 KB, both | 25.7–25.9 s |
| Dictionary | 4.7 s | 4.8 s | 761 → 776 KB | 5.4–5.6 s |

- The pages are ready when they were. The 15–18 KB more are the glossary's script, its Spanish and (except on the dictionary) the forms, all fetched after the page is ready.
- On the 3D view the underlines come about 9 s after the page is ready, once its trips, hurricanes and first map tiles are in: the glossary waits for the page's own files.
- What the browser fetched matches `routes.json`: `glossary_forms_es.json` after ready, the definitions never before a reader points at a word.

**Marks and the first pass** (`tests/browser/glossary.js`, 2026-10-19, after the review of PR #76, headless Chrome; the marks of each page as it first draws, before any tab, layer or entry is opened):

| Page | Marks, es (1400 / 390 px) | Marks, en (1400 / 390 px) | Terms marked, es / en | First pass, main-thread time |
|---|---|---|---|---|
| Map (`index.html`) | 67 | 77 | 42 / 44 | 13–42 ms |
| 3D (`3d.html`) | 19 | 21 | 15 / 17 | 4–11 ms |
| Area profile (San Juan) | 101 | 113 | 63 / 68 | 14–20 ms |
| Knowledge Area (`housing.html`) | 70 / 68 | 79 / 77 | 36 / 39 | 9 ms |
| WCRP (`wcrp.html`) | 89 | 96 | 35 / 38 | 15–17 ms |
| Data management | 74 | 81 | 62 / 66 | 13–17 ms |
| Dictionary | 100 | 256 | 90 / 150 | 19–28 ms |

- The first pass runs in slices of 3–9 ms in the browser's idle time; none reached 50 ms. Runs on a busier machine took up to twice as long, in more slices.
- At 390 px the Knowledge Area has two marks fewer: the text they were in is not shown at that width.
- Panning the 2D map for two seconds: the glossary did no work, and the median frame took 16.6–16.7 ms with the underlines and without them.
- The 3D count changes by one or two with what the view shows when the glossary arrives (a "loading…" note, the vehicle count).

### Tests
- **`tests/glossary.test.js`** (Node, 19 tests; `tests/test_core_js.py` runs it): capitals, accents, word edges, file names, the longest form, white space, `not_match` phrases (GTFS-Realtime, "por residente empleado"), `data-gloss-root="one"`, text that is not shown, the skip rules and the sections on plain objects that stand for elements, the first occurrence per section, English text on a Spanish page, the tooltip's markup (escaping, `safeHref`, held terms marked `lang="en"`), the parity of the module's files with `dictionary.py`'s, and the matcher's speed. Changing each rule of the module on purpose (21 changes) makes a test fail, except the no-break-space shortcut, which gives the same result as the general white-space test.
- **`tests/test_glossary.py`**: the four files are current, hold the right terms (and the `not_match` phrases) and no held Spanish; `routes.json` lists them; no page lists the script; every page has the `glossary` module; the two marks on purpose; the checks on `not_match` and `highlight_why`; the standing rule below.
- **`tests/browser/glossary.js`** (CDP), the seven pages in es and en at 1400 and 390 px: the marks and their attributes, none in a heading, control, link, label, code, map label or the chat; only the open word described by the tooltip, and an empty tooltip once closed; Esc with the focus in a search box keeping the focus and reaching the page; a word on two lines left visible; on the dictionary, "Hide the underlines" (focus back where the word was) and the switch; hover (desktop), keyboard focus, Enter, Esc and the focus kept, tap, second tap and tap outside (phone); the tooltip inside the window; a Leaflet and a MapLibre pop-up opened after load get their marks, and the pop-up of a fire station in the 3D view's facilities module, which loads on first use; the forms come from their file (the dictionary: from its own copy) and the definitions are not fetched before the first use; a clean console, no missing Spanish, no sideways scroll; no slice of 50 ms or more; and on the map, two seconds of panning with no glossary work and frames no slower than with the underlines off.
- **`tests/browser/throttle.js`** waits for the glossary before it closes its window, so the forms file is counted in `later`, and reports when the underlines were in (`gloss_s`).

### What changed from the design
- One loader in `common.js` that waits for the page's data, instead of a call in each page; no `data-gloss-root` on the pages, which find their sections by rule; the styles in the module instead of `twin.css`. The only page edits are the version of `common.js` and the two marks on purpose.
- Letter trees instead of one regular expression (its compile time).
- The definitions file holds every term, not only the highlighted ones, so `data-gloss` works for any term.
- Leaflet's and MapLibre's pop-ups through the libraries' own update, instead of the map's `popupopen` events: it covers every map, including the ones made later, without editing the page scripts.
- Text in flex and grid boxes is wrapped first, so marks never move it.
- The strings are 12, not 4: the tooltip's (Source:, link checked {date}, See in the glossary, Hide the underlines, Close, Definition of {term}, the loading and error notes, the note after hiding) and the dictionary's switch.

### Follow-ups
- A native Spanish speaker should review the 12 new strings (`i18n_src/es/glossary.json`) with the definitions of part 1.
- A screen reader hears the description when a word gets focus. The very first time, on a page that has not fetched the definitions yet, the tooltip says "Loading the definition…" for a moment; the definitions are fetched as soon as the pointer is over any mark, but not before the first keyboard focus.
- The dictionary page had 597 marks in Spanish and 833 in English, each a stop of the Tab key. With its sources as one section and its Glossary list off it has 100 and 256 (2026-10-19). If that still reads as noisy, the domain summaries of the list can carry `data-gloss="off"` too.

### The standing rule
Any PR that shows a new technical word on a page (a label, a legend, a help text, a pop-up, an entry name) adds that word to `dictionary_src/glossary.json` in the same PR. The term needs:
- an English and a Spanish definition, written to the rule above;
- a source, with the date its link was checked;
- its match forms and its highlight flag.

The highlighter then underlines it on every page by itself: there is nothing to add to the page. `python dictionary.py` (and `--check`) fails a term that lacks any of these, and a **priority-1 term that appears in the interface** (the static text of the seven pages and every interface string in `i18n_src/es/*.json`) **with `highlight: false`** unless its record says why in `highlight_why`. `tests/test_glossary.py` checks the same. Reviewers check that new words have terms. The same rule is in `dictionary_src/README.md` and `CONTRIBUTING.md`.
