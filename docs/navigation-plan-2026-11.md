# Organizing the observatory by domain: navigation plan (2026-11)

Date: 2026-11-04. Status: **approved by the project lead on 2026-11-04 ("Approve and merge"; HANDOFF decision 81).** Option A, the ten domains and the PR order of section 9 are approved; PR 1 and PR 2 are next. This document changes no code and no data.

**In short.** Today the map sorts data by *kind of data* (a "layer" in the Layers tab, a "dataset" in the Economy tab, a "measure" in the shading menu and in Rankings), not by *topic*. That is why night heat sits under Economy. The plan recommends **Option A**: one **Explore** tab that lists ten domains (heat goes under *Environment and climate*), and one **"On the map" panel** on the map itself that always shows what is on, its legend, the year and the area level, whatever tab is open. It ships in seven small pull requests. The first one that changes what visitors see is PR 2 (the "On the map" panel). Old links keep working.

## 1. What the project lead asked

The project lead, 2026-11-04: the heat data sits in the Economy section, and that is not intuitive. It must be intuitive yet powerful, organized by domain, and the active layers must stay clear while browsing other datasets. They asked for a plan and for the questions that would let them give direction.

## 2. The project lead's answers (2026-11-04)

| # | Question | Answer |
|---|---|---|
| 1 | Main users, in order | FPR program staff; researchers and journalists; residents and funders. (Municipal staff not chosen.) |
| 2 | Top-level domains | A short list of about ten (section 6). |
| 3 | One domain or several per dataset | One home domain, with "also in" mentions in other domains; search always finds it. |
| 4 | Places or topics first | Topics first; a place is one click away (click a municipio or barrio for everything about it). |
| 5 | Always one click away | All four: the active-layer list, the legend, the year control, the area level and the search. |
| 6 | Layers at once | One, sometimes two. |
| 7 | "Start from a view" presets | Keep them, one set of two to four per domain. |
| 8 | 2D, 3D and Knowledge Area | One layer list, three views: 2D and 3D share the domains and the active layers; Knowledge Area pages are FPR's analyses, linked from each domain. |
| 9 | Mobile | Rare. A phone must not break; no extra phone work. |
| 10 | Models | PolicyMap / Social Explorer (topic, then variable) and ArcGIS Hub / Living Atlas (catalog by theme, a "contents" panel). |
| 11 | What may move | Tabs may move and be renamed; every old link must still open the same map. |
| 12 | Who approves | the project lead only. |

## 3. What the site has today (main at 823ddaf)

### The 2D map's left panel: nine tabs of four kinds

| Kind | Tabs | What they hold |
|---|---|---|
| Start | Overview | One headline card per Catalog domain, each with "Show on map" |
| Data to put on the map | **Layers**, **Economy** | Layers: 7 groups of points, lines and areas drawn from files (`js/core/layers.js`), plus "Shade municipalities by" (`#choro`, 35 measures). Economy: **394 per-area datasets in 71 groups**, the year bar, the layer stack, presets, the workbench, composite indexes and scenarios |
| Finding data | Catalog | Search and filters over the data dictionary, by the registry's domains |
| A place | Municipality, Region | A municipio's tourism and exposure card; a region's profile |
| Tools | Rankings, Transit | Rankings: 30 measures. Transit: route planner, vehicles, residents far from service |
| About | About | Sources and method |

The Economy tab began as the economy's data engine. Every per-area series since then (housing, health, education, infrastructure, environment, satellite heat, vegetation, night heat, walk climb, WCRP) was added through the same engine (`js/core/datasets.js`), so it all lands in the Economy tab. Its opening sentence still reads "Put economic data on the map".

### The 71 groups by the dictionary's own domain

Every dataset already has a primary domain in the data dictionary (`dictionary_src/entries`, field `domain`), except the 64 exposure datasets (residents and housing units in a flood zone, sea level rise, protected land or near a stop). Measured with the engine on main:

| Dictionary domain | Datasets | Groups in the Economy tab today |
|---|---:|---|
| economy | 75 | Jobs and employers, Labor force, Industries, Income and poverty, Workers and commuting, Labor force by sex, Night-time lights, Nonprofit organizations |
| economy.public-money | 39 | Public money |
| economy.visitor-economy | 9 | Tourism supply |
| population | 45 | People, Population · …, Housing · Population, **Vulnerability (WCRP)** |
| housing | 36 | Housing · … |
| health | 30 | Health care · …, Health · Treatment facilities, Population · Health insurance |
| environment.hazards | 33 | Natural hazard risk, Landslides, Earthquakes, Community resilience, Landslide susceptibility, **Surface heat (Landsat)**, **Night surface heat (ECOSTRESS)** |
| environment.land | 10 | Land use (PUT 2015), Wetlands, Vegetation |
| environment | 8 | Regulated sites, Water and air quality (EPA) |
| infrastructure | 19 | Drinking water, Power plants, Bridges, Emergency services, Public safety |
| infrastructure.mobility | 15 | Transit access, Airports and ferries, Street connectivity, Climb on the walk to a stop |
| education | 11 | Public schools, Colleges, Libraries, **Historic places** |
| (none) | 64 | Residents · … and Housing units · … (flood, sea level, protected land, transit) |

So the domain is already known for 330 of 394 datasets. The Economy tab ignores it and sorts by the beginning of an English group name (`sortGroups`).

### Three ways of grouping the same things

1. **The registry's domains** (`dictionary_src/domains.json`): 9 domains and 6 sub-domains, used by the Catalog, the Overview cards and the dictionary.
2. **The layer menu** (`js/core/layers.js`, decision 55): 7 groups from the island down to single places (Territory; Hazards and environment; Land and housing; Infrastructure and mobility; Community services; Communities; Visitor economy). Shared by 2D and 3D.
3. **The Economy tab's 71 group names**, ordered by `sortGroups` to follow the layer menu loosely. The exposure groups are sorted by what they count ("Residents · …", "Housing units · …"), not by the hazard.

### Where the same data shows up in several places

| Data | Where a visitor can find it |
|---|---|
| Shading municipios | Layers › "Shade municipalities by" (35 measures), Economy (394), Rankings (30), Overview and Catalog "Show on map", 3D columns |
| Flood | Layers › FEMA flood zones; Economy › Residents/Housing units · Flood; Rankings and shading › places in a flood zone |
| Transit | Layers › routes, stops; Transit tab; Economy › Transit access, Residents near stops; Rankings |
| Tourism | Layers › tourism places; Economy › Tourism supply; Municipality tab; Rankings |
| Heat | Economy › Environment · Surface heat and Night surface heat; Knowledge Area › Urban heat; 3D columns |
| What is on the map | The "1 layer on" chip; the Economy tab's own "Layers on the map"; legends on the map |

### Where a visitor has to guess

- **Is it a "layer" or a "dataset"?** Flood zones are in Layers; the people living in them are in Economy. The split follows the file type, which a visitor cannot see.
- **Which tab holds a topic?** Heat, schools, hospitals, bridges and WCRP vulnerability all sit under "Economy".
- **What is on the map?** The Economy tab lists only its own layers; switches ticked in the Layers tab are listed only in the chip. Leaving the Economy tab hides its layer cards (opacity, order, mode).
- **Which year?** The Economy tab's year bar governs only Economy layers; it disappears when another tab opens.
- **Which shading wins?** "Shade municipalities by" and an Economy shaded layer can both be on.

### The 3D view and the Knowledge Area

- **3D** (`site/3d.html`): four tabs (Layers, Time, Route, About). Its Layers tab follows the same 7-group menu; its columns pick any engine dataset through menus grouped by `sortGroups`. It shares the chip (`activelayers.js`).
- **Knowledge Area**: 7 published pages (Housing, WCRP, Route analysis, Global Innovation Index, Women in the labor force, FEMA disaster funding and need, Urban heat), listed in `js/core/knowledge.js`. None says which domain it belongs to; the map does not link to them by topic.

### Page weight (measured on an LF copy of main 823ddaf, `budget.py`)

| Page | Scripts | Data |
|---|---|---|
| 2D map | **248.8 of 250 KB** | 146.0 of 250 KB |
| 3D view | 678.7 of 700 KB | 544.6 of 600 KB |
| Area profile | 110.1 of 120 KB | 610.7 of 650 KB |

The map has 1.2 KB to spare. Any new code there must be paid for by moving code into on-demand modules (`i18n_src/pages.json` `modules`, `docs/i18n.md` rule 15), as `econ_terrain`, `region`, `workbench` and `landuse` already do. The biggest first-load scripts (compressed): `chat.js` 72.4 KB, `app.js` 25.4, `economy.js` 22.0, `plan.js` 14.6, `adapters.js` 10.1, `network.js` 9.3, `catalog.js` 7.6, `activelayers.js` 5.5.

## 4. How mature map and data portals do it (only what helps decide)

- **Topic, then variable** (PolicyMap, Social Explorer, Data USA, CDC PLACES): a short list of topics; inside each, a picker of indicators; one map, one legend, one year control. Easy for non-specialists; the place profile opens on click.
- **Catalog plus "contents"** (ArcGIS Online Map Viewer, Living Atlas, ArcGIS Hub, QGIS): "Add data" browses a catalog by theme with a search box; a separate **Contents** panel lists every layer on the map with order, visibility, opacity, legend and remove. The contents panel never depends on where the layer came from.
- **Search first** (Living Atlas, Google Earth Engine catalog, Copernicus Browser): one search box over places and datasets, with theme facets.
- **Saved views** (PolicyMap's saved maps, ArcGIS web maps, Social Explorer's stories): a link restores the whole map. The observatory already does this (`docs/view-state.md`).
- **What they share:** (1) one list of what is on, always visible; (2) a short, stable topic list with search across everything; (3) one place per item, with cross-references; (4) "points from files" and "per-area figures" are not shown as different kinds of thing to a visitor.

## 5. Design rules from the answers

1. **Domain first, kind second.** A visitor picks a topic; inside it, per-area figures and points or lines sit together.
2. **One home per dataset**, "also in" elsewhere (answer 3). The home comes from the dictionary, not from a group-name prefix.
3. **One list of what is on**, outside the tabs, with the legend, the year and the area level (answer 5).
4. **One or two layers is the norm** (answer 6): keep the two-shading limit (bivariate) and points on top.
5. **Places one click away** (answer 4): clicking the map opens the place card; a "Place" tab holds municipio, region and barrio.
6. **2D and 3D share the domains and the "on the map" list** (answer 8).
7. **Old links keep working** (answer 11). Tabs are not in links today; `e=`, `l=`, `s=`, `rg=`, `r=` and the municipio name are, and they stay.
8. **Phone: do not break** (answer 9).
9. **Every visible technical word keeps its sourced es/en definition**; Spanish is the first language.

## 6. The ten domains (answer 2)

| # | Domain (es / en) | Id | Holds (examples) | From today's registry |
|---|---|---|---|---|
| 1 | Población / Population | `population` | People and age, households, disability, migration | `population` (without WCRP) |
| 2 | Economía / Economy | `economy` | Jobs, labor force, industries, income and poverty, commuting, nonprofits, night-time lights; **Economía del visitante / Visitor economy** as its last sub-domain | `economy`, `economy.visitor-economy` |
| 3 | Dinero público / Public money | `public-money` | Federal awards, FEMA, mitigation, LIHTC and NMTC money, municipal spending (Gasto Público) | promoted from `economy.public-money` |
| 4 | Vivienda / Housing | `housing` | Stock, prices, cost burden, public and tax credit housing (points and figures) | `housing` |
| 5 | Salud / Health | `health` | Health centers, shortage areas, hospitals, distance to care, Medicare, treatment | `health` |
| 6 | Educación / Education | `education` | Schools, colleges, libraries, education level | `education` |
| 7 | Ambiente y clima / Environment and climate | `environment` | **Day and night surface heat**, vegetation, wetlands, protected areas, land use, EPA sites, reservoirs | `environment`, `environment.land`, heat moved from hazards |
| 8 | Riesgos / Hazards | `hazards` | Flood zones, sea level rise, landslides, earthquakes, storms, hazard risk, community resilience, **residents and homes exposed** | promoted from `environment.hazards` |
| 9 | Infraestructura y movilidad / Infrastructure and mobility | `infrastructure` | Transit, roads, walk climb, airports and ferries, water, power, bridges, fire, EMS and police stations | `infrastructure`, `infrastructure.mobility` (kept as sub-domain) |
| 10 | Comunidades / Communities | `communities` | Comunidades Especiales, WCRP communities and vulnerability, city halls, historic places | new |

Plus **Referencia / Reference**, not a domain: municipio lines, barrios, base map. They stay on the "On the map" panel as settings.

**"Also in" examples:** night heat (home: Environment and climate; also in Health and Hazards); residents in a flood zone (Hazards; also Population); public housing (Housing; also Communities); health insurance (Health; also Population); walk climb (Infrastructure and mobility; also Health).

**Ids.** Promoting `economy.public-money` and `environment.hazards` changes two ids. The registry keeps the old ids as aliases so dictionary links and Catalog filters still resolve (decision 81 (b)).

## 7. Three options

### Option A (recommended): Explore by domain, and an "On the map" panel

- **Left panel, four tabs:** **Explorar / Explore** · **Lugar / Place** · **Herramientas / Tools** · **Acerca / About**.
  - *Explore* opens on the ten domain cards (today's Overview cards, one headline figure each). A search box at the top finds datasets, layers and Knowledge Area pages across all domains. A domain opens its page: presets (two to four views), per-area figures grouped by sub-topic, points and lines, "also in this domain", the Knowledge Area pages of the domain, and "all of it in the Catalog". The Catalog becomes Explore's "Search all data" view.
  - *Place*: Municipality and Region, with the area level (municipio, region, barrio).
  - *Tools*: Rankings (any dataset, the same picker as Explore), the route planner and Transit tools, the workbench, study areas, scenarios.
- **On the map, the "On the map" panel** (it grows out of today's chip): every layer that is on, whatever tab switched it on, with order, opacity, hide, remove and Shaded or Symbol; the legends; the year for all layers with play; the area level. Open on desktop as soon as a layer is on; folds to the chip; a bottom sheet on a phone.
- **The Economy tab** disappears as a tab. Its datasets move to their domains; its layer stack, year bar and links move to the panel; its workbench, composite and scenarios move to Tools. *Economy* stays as domain 2.
- **"Shade municipalities by"** (`#choro`) is retired: its 35 measures are datasets already, or become datasets. `s=` links open the same dataset.
- **3D:** its Layers tab uses the same ten domains for its switches and its columns' dataset menus; it shares the panel.
- **Trade-offs:** fixes both of the project lead's points and follows the PolicyMap and ArcGIS models they picked. Most work of the three (seven PRs). Tests that read the layer menu (`tests/layers_menu.test.js`) and the chip's tests must be rewritten for the domain order.

### Option B: rename and regroup, keep the tabs

- Economy tab renamed **Datos / Data**; its datasets grouped by the ten domains from the dictionary. The Layers tab regrouped by the same ten domains. The chip opens into a fuller list that includes the Economy layer cards.
- **Trade-offs:** cheap (three PRs, about 1 KB of scripts). Heat would sit under "Data › Environment and climate". But the split between "Layers" and "Data" stays, so a visitor still has to know whether flood zones are a layer or a dataset, and the nine tabs stay. Answers "heat in Economy" but only half of "intuitive".

### Option C: a GIS-style "Add data" catalog and a Contents panel

- The left panel becomes **Contents** (what is on, with legends and styling), **Place**, **Tools**, **About**. An **Add data** window searches and filters everything (domains as facets), in the style of ArcGIS Map Viewer.
- **Trade-offs:** the most powerful for analysts, easy on the budget (the window loads on demand). But a visitor who does not know what to look for faces an empty map and a search box: weak for residents and funders, and the project lead also chose the PolicyMap model. The biggest rebuild.

### Comparison

| | A | B | C |
|---|---|---|---|
| Heat found under a topic | Yes | Yes | Yes, by facet |
| One list of what is on, always visible | Yes | Partly (chip) | Yes |
| "Layer" versus "dataset" split hidden | Yes | No | Yes |
| Guided for non-specialists | Yes (domains, presets) | Partly | Weak |
| Powerful for analysts | Yes (Tools, search) | As today | Strongest |
| Pull requests | 7 | 3 | 7-8 |
| Map scripts after (estimate) | about 245-249 of 250 KB, with offsets | about 249.8 | about 240-245 |

## 8. Recommendation

**Option A**, with Option C's search across everything at the top of Explore. It matches every answer: topics first, one home per dataset, the four controls always near, one or two layers, domain presets, one layer list for 2D and 3D, old links kept.

## 9. Migration in small pull requests (Option A)

Each PR: browser test in Spanish and English at desktop and phone widths, `i18n.py --check`, `budget.py` on an LF copy, a glossary definition for every new technical word, `?v=` bumps, HANDOFF entry. Merged only on the project lead's word.

| PR | What it does | What visitors see after it | Map scripts |
|---|---|---|---|
| 1. Registry | The ten domains in `domains.json` (old ids kept as aliases); a home domain and "also in" for every engine dataset (the 64 exposure ones included) and every layer of `layers.js`; Knowledge Area pages get a domain; the dictionary and `catalog.json` rebuilt | The Overview cards and the Catalog's domain filter show the ten domains; heat appears under Environment and climate in the Catalog | 0 (data and docs only) |
| 2. Make room, then "On the map" | First move code that is not needed at load into on-demand modules (candidates: the route planner `plan.js`, 14.6 KB, loaded with a small stub that still reads `r=`; the Catalog list; the Spanish dataset labels of each domain, as `econ_terrain` does). Then the chip becomes the panel: all layers, the Economy layer cards, legends, the year bar, the area level | **The first visible change.** One panel on the map lists everything on, with its legend and year, and stays while any tab is open. The project lead's "layers active are clear" is met here | -12 to -14 KB, then +3 to +4 KB |
| 3. Explore tab | A new first tab: the ten domain cards (from Overview), each domain page with per-area figures by sub-topic and its points and lines. The point and line switches appear as proxies of the Layers tab's switches (the pattern of the Economy tab's "Also show on the map"), so no id changes yet. Search across datasets, layers and Knowledge Area pages | Heat is found under Environment and climate on the map. Economy and Layers tabs still there, for comparison | +5 to +7 KB (new `explore.js`), domain pages' Spanish loaded on demand |
| 4. Retire the old tabs | Layer rows move into the domain pages with the same ids; the tabs become Explore · Place · Tools · About; Rankings uses the dataset picker; `#choro` retired with `s=` mapped to datasets; `showTab('economy')`, `'layers'`, `'catalog'`, `'muni'`, `'region'`, `'rank'`, `'transit'` aliased to the new tabs; `layers_menu` tests rewritten for the domain order | Four tabs. No more "Economy" tab | -3 to -6 KB (one shading path fewer, Overview merged) |
| 5. 3D | The 3D Layers tab and the columns' dataset menus by domain; the shared panel | 2D and 3D look the same in organization | 3D: +1 to +2 KB of 700 |
| 6. Presets per domain | Two to four views per domain (for example Environment and climate: "Day and night heat", "Green cover"; Hazards: "Flood and sea level", "Who lives in a flood zone"), each with sources and defined terms; Knowledge Area pages link back to their domain on the map | Each domain opens with ready views | +1 KB, or on demand with the domain page |
| 7. Help and docs | Help pop-ups, About, `docs/layers.md`, `docs/domains.md`, `docs/adding-data.md` ("pick a home domain"), the presentation brief | Up-to-date help in both languages | 0 |

**Order and checkpoints.** PR 1 and PR 2 do not depend on each other and can be built at the same time. PR 3 needs PR 1. PR 4 needs PR 2 and PR 3. The project lead can stop after PR 2 (the panel alone) or after PR 3 (both old and new) if a test with staff suggests so.

**Links.** No published link names a tab. `e=` (dataset keys), `l=` (`LAYER_KEYS`), `ey=`, `eb=`, `ix=`, `sc=`, `r=`, `rg=`, `bm=`, `c=` and the municipio name keep their meaning; `s=` opens the same measure as a dataset. A link test (old links from `tests/browser`, the dictionary's ~270 view links, the Knowledge Area "Open on the map" links) runs in PR 2 and PR 4.

## 10. Risks and limits

- **Budget.** The map has 1.2 KB to spare. PR 2 must free room before anything is added; if the planner stub cannot read `r=` cheaply, the Catalog list and the per-domain Spanish labels are the fall-back offsets. Every PR states its measured weight.
- **Tests.** `tests/layers_menu.test.js`, the chip's tests and `test_catalog.py` encode today's groups; they are rewritten, not deleted, in PR 4.
- **Held content.** Content held for Compliance (`i18n_src/held_for_review.json`, Table 10 Spanish, the Public money headline) stays held wherever it moves. Public money becoming a top-level domain changes its place, not what is published.
- **Spanish.** Domain and tab names are new Spanish strings; a native reader should check them with the rest (decision 8).
- **Not in this plan:** new data, a merged 2D/3D page, a phone-first design, municipal-staff tasks (not chosen as a main user).

## 12. Ask everywhere (the project lead, 2026-11-04)

The project lead, after approving the plan: "Ask needs to be across the board available. Like a chat popup. So it helps people navigate the data, display it in the map and even analyze it. In general help answer questions."

**What exists (docs/ask.md).** The "Preguntar / Ask" button is in the top bar of every page but the 404 page; the chat loads on first use (`chatboot.js`, about 1.3 KB). On the 2D map and the 3D view it shades datasets, switches layers, moves the map and opens the workbench. On pages without a map (`askpage.js`) it answers in the chat (definitions, sources, numbers, rankings, trends, comparisons, patterns) and hands anything that needs the map to it with "Show on the map" (`index.html#ask=`).

**What changes, in the PRs above:**

| PR | Ask |
|---|---|
| 2. "On the map" | Everything Ask switches on or shades is listed in the panel, with its legend, and can be removed there; an Ask answer that changed the map says what it added and points to the panel. The chat stays a pop-up that leaves the panel visible (desktop: beside it; phone: one at a time). |
| 3. Explore | Ask knows the ten domains: "¿qué hay sobre calor?" names the home domain and offers "Abrir Ambiente y clima"; a dataset answer names its domain and "also in". Ask's suggested questions on the map follow the open domain. |
| 4. Retire the old tabs | Ask's map actions call the panel and the domain pages, not the old tab ids (aliases kept). |
| 5. 3D | The same in the 3D view. |
| 7. Help and docs | The 404 page gets the Ask button; `docs/ask.md` describes Ask by domain. |

**Analysis.** Ask's analysis answers (rank, compare, trend, the relation between two datasets with the workbench) keep the rule of decision 72: they state the figures and how they were computed, and draw no conclusions. A question about a place one click away ("¿cómo está Utuado?") opens the Place card.

**Not in this plan:** a new language model or service behind Ask (the chat stays the observatory's own rules and lexicon; an LLM endpoint is an FPR decision, see the twin's long-term notes), voice input, and saving chats.

## 11. Decision 81 (in HANDOFF.md)

Approved by the project lead on 2026-11-04, (a) to (g); (h) added the same day at their request:

- (a) **Option A**: Explore · Place · Tools · About on the left; the "On the map" panel on the map; the Economy tab retired as a tab.
- (b) **The ten domains** of section 6, with the old ids `economy.public-money` and `environment.hazards` kept as aliases.
- (c) **Heat's home** is Environment and climate, also in Health and Hazards. WCRP vulnerability's home is Communities (today Population).
- (d) **"Shade municipalities by" retired**; its measures become datasets and `s=` links still open them.
- (e) **Rankings** ranks any dataset, from Tools.
- (f) **The order of the PRs** in section 9, with PR 2 (the panel) as the first visible change, each merged only on the project lead's word.
- (g) **Names:** "Explorar / Explore", "Lugar / Place", "Herramientas / Tools", "En el mapa / On the map".
- (h) **Ask everywhere** (added 2026-11-04 at the project lead's request, section 12): one Ask pop-up on every page that helps people find data, put it on the map and analyze it.
