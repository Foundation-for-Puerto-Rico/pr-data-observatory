# Knowledge Area: its areas and how to add one

The Knowledge Area is the part of the observatory that holds FPR's research and program tools, one area per page. The "Knowledge" button of every top bar opens the **Knowledge home page** (`knowledge.html`, since decision 90, PR 1): one card for every published area, grouped by topic, with its kind, review status and reviewer, the month it was updated, its other topics and the datasets it uses, a search box and filters (kept in the address: `#q=`, `#k=`, `#p=1`). Each area page starts its `.toc` bar with a **header** (since decision 90, PR 2), then a divider and the page's own sections: "Knowledge" (back to the home page) › the area's topic (`index.html#topic=<top domain>`), an "All areas" menu (a `<details>` whose panel lists every area that is not hidden, grouped by the top domain of its home domain, the page's own area current, and a link to the home page), the status badge with the reviewer (`statusText()`), and "Updated <month>". At the end of `main.page` a foot follows (`#kaFoot`): the related areas, the datasets the area uses and the way to every published file and to its cite text. `core/knowledge.js` carries what the header needs and nothing more: the areas' ids, names, pages, statuses, reviewers and dates, the topic names (`TOPICS`) and the reviewers' names (`REVIEWER_NAMES`), all written by `knowledge.py` and free of program terms, so a placeholder page can load it. After the page is ready it loads `js/knowledge_items.js` (`window.KNOWLEDGE`, the same file and `?v=` as the home page) and then `js/core/knowledge_more.js`, which fills the menu's panel (`menu()`, also at once if the menu is opened first) and draws the foot (`foot()`); neither weighs on the first load. The strip of tabs (`tabs()`) and `topicLink()` are gone.

## The registry

The source is **`knowledge_src/items.json`** (the Knowledge registry, `docs/knowledge-plan-2026-11.md`). `python knowledge.py` checks it and writes two files; `python knowledge.py --check` (run by the tests and by `build.py`) fails when either is out of date:

- the `AREAS` list of `site/js/core/knowledge.js` (`Core.knowledge.AREAS`), between its two marker lines, for every `public` item: a small script with no data file, so the tabs are drawn without a network wait;
- `site/js/knowledge_items.js` (`window.KNOWLEDGE`), read only by the home page: the published, public items with their cards, the kinds, the reviewers, the domains they use and the titles of the datasets they use.

Never edit either file by hand. Each item has the fields below, plus: `title` and `summary` (`{ en, es }`, for the card), `kind` (a key of `kinds`: `study`, `analysis`, `program_tool`, `index_profile`), `domains` (the home domain first; `domain` in `AREAS` is that first one), `datasets` (ids of `dictionary_src/datasets.json`), `related` (other item ids), `updated` (`YYYY-MM`, the snapshot of its content), `reviewer` (keys of `reviewers`, shown while it is in review), `audience` (`public`, or `internal`: never written into `site/`, for `fpr-platform`) and `cite` (the anchor of the page's cite text). `knowledge.py` reports any id, domain, dataset or reviewer that does not exist.

| Field | Meaning |
|---|---|
| `id` | Short id; the page names it in `data-ka`. |
| `label` | `{ en, es }`: the area's name in each language (like the registry's names, not a `T()` key). |
| `icon` | A Material Symbols name. Every area page lists it in its `icon_names`. |
| `page` | The area's page, for example `housing.html`. |
| `domain` | The area's home domain, an id of `dictionary_src/domains.json` (navigation plan, decision 81): the domain page on the map links to it. |
| `status` | `published`: a tab. `in_review`: a tab with the marker "In review" / "En revisión". `hidden`: no tab. The page of an area that is not published (in review or hidden) shows only the in-review message. |
| `review` | Optional, on a `published` area only: `true` keeps the "In review" / "En revisión" badge on its tab while its page shows its own content (see "Published, with the marker kept"). Leave it out for a plain published area. |
| `ai` | Optional: `true` when the area's content was drafted with the help of an AI model. Its page's notice then adds the standard sentence "Draft prepared with the help of Claude (artificial intelligence)." / "Borrador preparado con ayuda de Claude (inteligencia artificial).", and keeps it after the marker goes. Today: Route analysis, Global Innovation Index, Women in the labor force, FEMA disaster funding and need, Public spending, Urban heat, Inflation, Reservoirs, Broadband gaps, Energy in Puerto Rico, Opportunity Zones 2.0, Connections between municipios and Federal funds returned and unused. |

Today: Housing is `published` (`housing.html`); WCRP is `published` with `review: true` (`wcrp.html`, HANDOFF decision 51); Route analysis is `published` with `review: true` (`route-analysis.html`, HANDOFF decision 58: approved by the project lead on 2026-10-19, completed on 2026-10-21; its data and method are in `docs/analysis/route-analysis-2026-10/`); Global Innovation Index is `published` with `review: true` (`gii.html`, HANDOFF decision 59: requested by the project lead on 2026-10-23; FPR's 2021 profile kept as printed, the newest open values and an indicative GII 2026 comparison; its data and method are in `docs/analysis/gii-2021/`). Women in the labor force is `published` with `ai: true`, without the marker since 2026-10-31 (the project lead: public Census data, an analysis) (`women-labor.html`, HANDOFF decision 67: requested by the project lead on 2026-10-30 for the Human Capital chapter of the Eastern Region Strategic Vision; its data and method are in `docs/analysis/women-labor-2026-10/`). FEMA disaster funding and need is `published` with `review: true` and `ai: true` (`public-money.html`, HANDOFF decision 72: Public money v2, step 5, approved by the project lead on 2026-10-31; the marker and `noindex` stay while the Compliance review of the federal-money series is open; its data are `public_money_need.json` (`public_money_need.py`) and its page is written by `docs/analysis/public-money-v2-2026-10/make_page.py`). Public spending is `published` with `review: true` and `ai: true` (`public-spending.html`, HANDOFF decision 78: the Commonwealth budget from OGP's data sheets, requested by the project lead on 2026-11-04; the marker and `noindex` stay until leadership reviews the page (decision 73 (7)) and the function crosswalk is reviewed (decision 76); its data are `spending_state.json` (`ogp_budget.py`) and its page is written by `docs/analysis/public-spending-2026-11/make_page.py`). Urban heat is `published` with `review: true` and `ai: true` (`urban-heat.html`, HANDOFF decision 80: terrain and climate plan, step 3, 2026-11-04; the marker and `noindex` stay until the project lead takes them off; its data are `urban_heat.json` (`urban_heat.py`) and its page is written by `docs/analysis/urban-heat-2026-11/make_page.py`). Inflation is `published` with `review: true` and `ai: true` under Economy (`inflation.html`, HANDOFF decision 95: requested by the project lead on 2026-11-10; the marker and `noindex` stay until the project lead takes them off; its data are `inflation.json` (`inflation.py`), its page is written by `docs/analysis/inflation-2026-11/make_page.py`, and its plan and backtest are in `docs/inflation-plan-2026-11.md`). A new month of prices changes the page's text, so a refresh reruns `make_page.py` and `i18n.py` (refresh unit `inflation`, by hand). Reservoirs is `published` with `review: true` and `ai: true` (`reservoirs.html`, HANDOFF decision 98, 2026-11-10): written by `docs/analysis/reservoirs-2026-11/make_page.py`, data `reservoir_history.json` (`reservoirs.py`), and the page adds the latest USGS readings in the browser. Broadband gaps is `published` with `review: true` and `ai: true` (`broadband.html`, HANDOFF decision 99, 2026-11-12): written by `docs/analysis/broadband-2026-11/make_page.py` from the published `broadband_series.json` and `broadband_barrio.json` (`broadband.py`, decision 94), with `barrios.geojson` for its map; a new June release changes the page's text, so a refresh reruns `make_page.py` and `i18n.py`. Opportunity Zones 2.0 is `published` with `ai: true` under Economy (`opportunity-zones.html`, HANDOFF decision 103, 2026-11-13; the project lead took the marker and `noindex` off the same day, and the page opens with an introduction): written by `docs/analysis/opportunity-zones-2026-11/make_page.py` from `opportunity_zones.json` (`opportunity_zones.py`), with `geo/tracts.geojson` for its map; a new Treasury file changes the page's text, so a refresh reruns `make_page.py` and `i18n.py` (`docs/opportunity-zones.md`). Connections between municipios is `published` with `review: true` and `ai: true` under Infrastructure (`transit-links.html`, HANDOFF decision 105, 2026-11-13): written by `docs/analysis/transit-links-2026-11/make_page.py` from `transit_links.json` (`transit_links.py`), with `municipios.geojson` and `simulated_links.geojson` for its map; a rebuild changes the page's text, so a refresh reruns `make_page.py` and `i18n.py` (`docs/transit-links.md`). It describes where people travel and where a route is listed; it proposes no route (the transit plan's decision 4).

The marker and the in-review message are `T()` keys of the `knowledge` scope (`i18n_src/es/knowledge.json`: "In review", "This knowledge area is in review and will be published when the review is complete.", "Go to {area}", "Open the map"), so `i18n.py --check` and `tests/test_held_for_review.py` cover them. Every page that loads `core/knowledge.js` lists that scope. The scope also holds the static text of a placeholder page (its top bar), because a placeholder loads **only** this scope: its Spanish bundle (`site/i18n/es.<page>.js`; WCRP's, while it was a placeholder) carries nothing else. The `common` scope is not used there, because it carries the map's WCRP layer strings (the program's full name, the plan states).

**Tabs look the same.** Every tab has the same size, weight, color and spacing (`.toc a.ka-tab` in `housing.css`), and the current page's tab has the active style, whatever its status. An area in review, or a published area that keeps the marker, differs only by the small badge "En revisión" / "In review" inside its tab (`.ka-mark`). On the Housing page the bar scrolls back to its start at the top of the page, so the area tabs are in view on a phone and on a wide screen (`housing.js`).

The API: `AREAS`, `STATUSES`, `visible()`, `find(id)`, `marked(area)` (whether its tab carries the badge: `in_review`, or `published` with `review: true`), `label(area)`, `tabs(current)`, `reviewHtml(id)`, `notice(id)` (with `NOTICE` and `AI`, its two sentences) and `render()`. `render()` fills every `.ka-tabs[data-ka]` of the page; puts the way back to the area's topic on the map before the first group (`topicLink(area)`: "This topic on the map" / "Este tema en el mapa", `index.html#topic=<the top domain of its domain>`, navigation plan PR 6); when the page's own area is in review, fills `<main id="kaReview">` and sets the title; and writes the notice into the page's `[data-ka-note]` box (or takes the box away when there is nothing to say).

## Each area page

```html
<nav class="toc" id="toc" aria-label="On this page">
  <span class="ka-tabs" role="group" aria-label="Knowledge Area" data-ka="housing"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#headline">Headline</a> ...
</nav>
...
<script src="js/core/knowledge.js?v=3"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
```

`render()` runs before `I18N.apply()`. Each tab is already in the page language and carries `data-t="skip"`, so `I18N.apply()` leaves it alone.

## Adding an area

1. Add one item to `knowledge_src/items.json` and run `python knowledge.py`. Raise the `?v=` of `core/knowledge.js` on every area page and of `knowledge_items.js` on `knowledge.html`.
2. Make its page in the same family as `housing.html` (`twin.css`, `housing.css`, the same top bar with the Knowledge Area button marked `aria-current="page"`), with the tab group above and its `data-ka`.
3. Add the new icon to the `icon_names` of every area page (the Material Symbols font only has the icons it lists). A test checks this.
4. Add the page to `i18n_src/pages.json` (its scopes, including `knowledge`, with `core/knowledge.js` among its scripts), to `dictionary_src/routes.json` (its budget) and to `tests/browser/throttle.js`. Add it to the pages that `dictionary.py --links` accepts if a dictionary entry links to it.
5. Update the dictionary entry `layers.knowledge_area` (`dictionary_src/entries/views_layers.json`), which lists the areas.
6. Run `python i18n.py`, `python dictionary.py`, `python catalog.py` and `python registry.py`, then the checks.

## An area in review

An area whose content waits for a review (for example, Finance and Compliance for federal grant work) is `in_review` or `hidden` on `main`. Its page on `main` is a placeholder: the same top bar and tab bar, an empty `<main class="page" id="kaReview"></main>` that the registry fills, `<meta name="robots" content="noindex, nofollow">`, and no other script, data or map. `tests/knowledge.test.js` checks this for every area that is not published, reading each status from the registry:

- the page loads only `js/i18n.js` and `core/knowledge.js`; it has no data, map, frame, video or canvas; its only image is the FPR logo; its links go only to the other views (`index.html`, `3d.html`, `housing.html`, `dictionary.html` with no anchor), its own anchor, its icon, its styles and the font;
- its page in `i18n_src/pages.json` has the `knowledge` scope only, and its bundle (`site/i18n/es.<page>.js`) equals that scope, keys and values (a hand-edited bundle fails);
- no program terms in the page, its bundle, the `knowledge` scope, `core/knowledge.js`, the area's label and, while any area is not published, the `layers.knowledge_area` entry: its source, its Spanish summary and every `site/data/*.json` file that carries it.

"No program terms" is a pattern in the test (`BANNED`). It decodes HTML entities, then ignores case, accents and runs of spaces. It covers the program's name and plans (Whole Community, Resiliencia Comunitaria, Planificación Integral, resilience plans, "plan approved" / "plan aprobado", "plan in progress"), the agency (Department of Housing, Departamento de (la) Vivienda, Housing and Urban Development, Vivienda y Desarrollo Urbano, HUD, PRDOH), the money (CDBG, grant, subvención, federal funds, fondos federales, disaster recovery, recuperación ante desastres), the index and its tools (RVI, Hunter, vulnerab-, white paper, Social Capital, Capital Social), the communities list ("list of" a date, "lista de(l)" a date, list of communities) and the program's datasets and files (`wcrp.` or `wcrp_` or `wcrp-` before anything but `html`). The acronyms are matched as substrings ("PlanningCDBG"), except "rvi", which needs non-letter edges ("service"). The bare acronym "WCRP" and the page name `wcrp.html` pass. Every term was mutated into each file once to confirm the test fails.

The content stays on its own branch until the review is done.

These placeholder checks, and the ban on program terms, apply to areas that are `in_review` or `hidden` only. A `published` area may carry the program terms, with or without `review: true`.

The page says, in Spanish and English:

- "Esta área de conocimiento está en revisión y se publicará cuando concluya."
- "This knowledge area is in review and will be published when the review is complete."

with links to the first published area ("Ir a Vivienda" / "Go to Housing") and to the map ("Abrir el mapa" / "Open the map").

## Published, with the marker kept

When an area's content is approved but its owner wants to keep a visible marker for a while ("por si acaso"), set `status: 'published', review: true`. Then:

- its tab carries the small badge, exactly like an area in review; every tab keeps the same size, weight, color and spacing, and the current page's tab is active;
- its page shows its own content (the registry does not fill `kaReview`), with **one** notice near the top in the caution style: an empty `<div class="note caution review-note" role="note" data-ka-note></div>` that `render()` fills, so every page says the same (decision 65, 2026-10-29). The words are two `T()` keys of the `knowledge` scope: "**In review:** the content of this page is under review and may change." / "**En revisión:** el contenido de esta página está en revisión y puede cambiar.", plus, for an area with `ai: true`, "Draft prepared with the help of Claude (artificial intelligence)." / "Borrador preparado con ayuda de Claude (inteligencia artificial)." No page writes the notice itself (`tests/knowledge.test.js` checks it); its style is in `housing.css`, and the chat on such a page repeats it (`askpage.js`);
- the page keeps `<meta name="robots" content="noindex, nofollow">` while the marker is on;
- the placeholder checks and the ban on program terms in `tests/knowledge.test.js` do not apply to it (it is published).

To take the marker off later: delete `review: true` in `core/knowledge.js` (raise its `?v=` on every area page), remove the page's notice box (keep it when the area has `ai: true`: the notice then shows only the AI sentence) and its `noindex` line, and update the page's tests (`tests/test_wcrp_rvi.py` checks the marker, the notice and `noindex` for WCRP).

WCRP is the first area published this way (2026-10-19, decision 51, branch `wcrp-publish`): it followed the steps below, with `review: true` added in step 2.

## Publishing WCRP after the review (the held branch `wcrp-area`)

WCRP is a HUD CDBG-DR program. Its full page (program description, funding, the Risk and Vulnerability Indicators, the Social Capital map) waits on the branch `wcrp-area`, which is **not** edited from `main`. When Finance and Compliance approve:

1. Merge `wcrp-area` into a branch from `main`.
2. In `site/js/core/knowledge.js`, set WCRP's `status` to `published`.
3. Resolve the conflicts:
   - `site/wcrp.html`: take the full page from `wcrp-area`. Then:
     - replace its static `.ka-tabs` span with `<span class="ka-tabs" role="group" aria-label="Knowledge Area" data-ka="wcrp"></span>`;
     - replace `<script>I18N.apply();</script>` with the two lines above (`knowledge.js`, then `Core.knowledge.render(); I18N.apply();`);
     - raise `housing.css` to the version `main` uses (17 or later).
   - `site/housing.html`: keep `main`'s registry span (`data-ka="housing"`). The branch's static WCRP tab is what the registry now draws.
   - `i18n_src/pages.json`: take the branch's `wcrp` page (its own scopes, `common` and `wcrp`, and its module `social`), then add `knowledge` to its scopes and `core/knowledge.js` to its scripts. The full page then no longer has a placeholder bundle; the test of the placeholder bundle applies only while WCRP is `in_review`. `i18n_src/es/knowledge.json` stays: Housing and every future placeholder use it.
   - `dictionary_src/routes.json` and `tests/browser/throttle.js`: take the branch's `wcrp` line.
   - `site/i18n/es.*.js` and the generated `site/data/` files: rebuild them (`python i18n.py`, `python dictionary.py`, `python catalog.py`, `python registry.py`).
4. Raise `js/i18n.js` on every page above the higher of the two sides (`main` 43 on 2026-10-19, `wcrp-area` 41), because the merged bundles differ from both. Raise `knowledge.js` and `twin.css` too if either side changed them. **The same rule for every script and style sheet both sides changed since the merge base:** find them with `git diff --stat <base> origin/main -- site/js site/css` and `git diff --stat <base> origin/wcrp-area -- site/js site/css`; each file in both lists gets a `?v=` above both sides on every page that loads it, and so does any version a script writes inside another (for example `ENGINE_JS` in `twin3d.js`, `econ_level.js?v=` in `economy.js`), so a browser that cached either side's copy reloads. For a file only one side changed, take that side's version. On 2026-10-19 (base 23981cb) both sides had changed `economy.js` (base 42, `wcrp-area` 43, `main` 44: now 45) and `twin3d.js` (56, 57, 58: now 59); `app.js`, `network.js` and `supply3d.js` (main only) keep main's versions, and `engine.js`, `adapters.js`, `datasets.js`, `econ_level.js` and `profile.js` (branch only) keep the branch's, inside `ENGINE_JS` too.
5. Update `layers.knowledge_area` (WCRP is published), release the held Spanish as `docs/i18n.md` says, and remove `noindex` only when Compliance says so (with `review: true`, keep it while the marker is on).
6. Update three tests (found by a trial merge on 2026-10-19, which then passed every check):
   - `tests/test_wcrp_rvi.py`, `test_the_page_is_not_indexed_and_the_spanish_is_held` (line 289 on `wcrp-area`) expects a static `href="wcrp.html"` in `housing.html`. The tab is now drawn by the registry, so check the registry instead, for example:
     ```python
     knowledge = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
     self.assertRegex(knowledge, r"id: 'wcrp',.*page: 'wcrp\.html', status: 'published'", "the Knowledge Area's tabs link to WCRP (core/knowledge.js)")
     self.assertIn('data-ka="housing"', (ROOT / "site" / "housing.html").read_text(encoding="utf-8"))
     ```
   - `tests/knowledge.test.js` reads every status from the registry, so publishing WCRP needs no edit there: its tab loses the marker, its page keeps its own content, and the placeholder checks stop applying to it.
   - The check of `layers.knowledge_area` runs while any area is not published, and is skipped when all are. If another area is still in review when WCRP is published, the entry may say that WCRP is published but must stay free of the program terms; describe WCRP itself in its own entries (`dictionary_src/entries/wcrp.json` on the branch).
7. Run every check, and the browser check of both pages in both languages.
