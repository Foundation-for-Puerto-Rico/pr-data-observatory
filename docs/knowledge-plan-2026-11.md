# Knowledge that is easy to find and share: plan (2026-11)

Date: 2026-11-09. Status: **approved by Francis on 2026-11-09 ("Approve and merge"; HANDOFF decision 90).** Option A, (a) to (f) of section 13 as proposed; PR 1 (registry fields and the Knowledge home page) is merged (#168); PR 2 (one header on each area page) is built on branch `knowledge/header`. This document changes no code and no data.

**In short.** The Knowledge Area has eight pages, and the only way between them is a strip of tabs at the top of each page. It already overflows: at 1440 px it holds 2,251 px of tabs in 1,415 px of space, so the current page's own tab and sections start off screen. The plan gives Knowledge a **home page** and a single **header** on each page, and it moves the list of pages into the **registry** the map and the dictionary already read. Then the map, the dictionary, Ask and the home page can all point to the same pieces of work. Each piece of work also records **who may see it** (public or internal) and **how far it is in review**, so FPR can build analysis internally and publish it by changing one field after review. It ships in five small pull requests. The first one visitors see is PR 1 (the home page).

The design boards are on the review canvas (private Design artifact `RD7raXGVsfaFNBHZBzazms`, row 3: "Knowledge Area today", "How it fits together", "Proposed Knowledge home").

## 1. What Francis asked

Francis, 2026-11-09: navigating the knowledge areas should be easier. Analyze it, and think about how it all fits together, because FPR will integrate a lot of analysis and share knowledge internally and with others.

## 2. What the site has today (live site and main at 4032ecb, checked 2026-11-09)

- **Eight areas** in `site/js/core/knowledge.js` (`AREAS`): Housing, WCRP, Route analysis, Global Innovation Index, Women in the labor force, FEMA disaster funding and need, Public spending, Urban heat. Each has one `domain`.
- **No front door.** The top bar's "Knowledge Area" button opens `housing.html`. No page lists every area with what it is, what it covers or when it was updated.
- **One strip for two jobs.** Each page's `.toc` bar holds "This topic on the map", the eight area tabs, a divider and then the page's own sections (5 to 13 of them). At 1440 px the bar holds 2,251 px of content in 1,415 px of space (measured on `urban-heat.html`). The page's own sections come last, so they are what is hidden.
- **Different kinds of work look the same.** A 2023 FPR study (Housing), a program tool (WCRP), analyses drafted in 2026 and FPR's 2021 index profile (GII) have the same tab. Kind, date and owner only appear inside each page.
- **"In review" on 6 of 8 tabs.** The badge (decision 65) no longer tells an approved study from a draft, and it doesn't say who is reviewing.
- **Links between data and analysis go one way.** Since navigation PR 6, a topic in Explore links to the areas whose `domain` it is, and each area links back to its topic. A dataset's dictionary entry and a layer on the map don't say which analyses use them. An area can't be "also in" a second topic, so the two Public money areas don't point to each other, and Urban heat doesn't appear under Health or Hazards.
- **Already built to share.** Urban heat keeps its chosen measures in the address (`#l=night&p=age65`). Every page checked (Housing, GII, Women in the labor force, Public spending, Urban heat) has cite text and a date. No page has a copy-link button for a section or a chart, or a print or PDF view.

## 3. Design rules

1. **One registry.** Domains, datasets and places already live in one registry that the map, the dictionary, the Catalog and Ask read (decision 81). Pieces of knowledge join it; nothing keeps its own list.
2. **Finding something and moving inside a page are separate.** Moving between areas happens on the home page and in an "All areas" menu. The bar on a page lists only that page's sections.
3. **Status lives on the page and in the list, never on every tab,** and says what is being reviewed and by whom.
4. **Every link works both ways.** A piece of work names the datasets it uses; each of those datasets then shows "Used in".
5. **Internal and public share one format.** Moving a piece of work from internal to public means changing one field after review. Internal content never reaches the public site's files.
6. **Nothing new on the map's first load.** The map's script budget is at 249 of 250 KB; the home page is its own page with its own budget.

## 4. The shape: five doors, one registry, two audiences

- **Doors:** Explore (topics on the map, 3D, time), Place (profiles), **Knowledge** (studies, analyses, program tools), Data (dictionary, Catalog, downloads, cite) and Ask (on every page). The top bar already has all of them except a Knowledge home: its button points at one study.
- **The registry** holds the 10 domains, the datasets (405 today), the places (4,523 areas) and, with this plan, the **knowledge items**.
- **Audiences:** the public site (GitHub Pages) shows published items, with `noindex` and the review notice while an item is in review, as today. Internal items go to the staff platform (`fpr-platform`, section 9).

## 5. The knowledge registry

The source of truth is a JSON file, `knowledge_src/items.json` (Spanish and English, like `dictionary_src/domains.json`). A build step writes it into `site/js/core/knowledge.js`, so pages still draw without waiting on the network, and into `catalog.json` and the dictionary for the "Used in" links. Today's `AREAS` fields stay as they are (`id`, `label`, `icon`, `page`, `status`, `review`, `ai`, `domain`). New fields:

| Field | Meaning |
|---|---|
| `kind` | `study` (an FPR publication), `analysis`, `program_tool`, `index_profile`. Shown on the card and as a filter. |
| `summary` | One sentence `{ es, en }`, written for the card. |
| `domains` | The home domain first (`domain` today), then "also in" domains. |
| `datasets` | Dictionary ids of the datasets it uses. Checked against the dictionary at build time. |
| `related` | Ids of related items (FEMA funding ↔ Public spending). |
| `updated` | The date its content was last updated (ISO). The study's own date stays on its page. |
| `reviewer` | While in review: `compliance`, `leadership`, `spanish` or more than one. Shown with the status. |
| `audience` | `public` or `internal`. Only `public` items are built into the public site. |
| `cite` | The cite text the page already has, so the home page and Ask can give it. |

The tests in `tests/knowledge.test.js` extend to the new fields: every `datasets` id exists, every `related` id exists, every `domains` id is a domain, and no `internal` item appears in any file under `site/`. The ban on program terms for `in_review` and `hidden` items stays exactly as it is.

## 6. The Knowledge home page (`knowledge.html`)

- **Top bar:** the button becomes "Knowledge" / "Conocimiento" and opens this page.
- **Cards grouped by home domain**, in the order of the 10 domains. Each card shows the kind, the status (and the reviewer, if in review), the title, the summary, the date, the main sources, and "also in" or "related". It links to Open, On the map (its topic) and Cite.
- **Search and filters:** search over titles, summaries and dataset names, from the registry file itself (no new index); filters for kind and "Published only".
- **Budget:** its own entry in `dictionary_src/routes.json`, about 40 KB of scripts; no map.

## 7. One header on each area page

The strip of eight tabs goes away. In its place, one header:

- **Breadcrumb:** Knowledge › home domain › this page.
- **Status and date:** one badge with the reviewer, and "Updated …".
- **Buttons:** "All areas" (a menu of every published area by domain), "This topic on the map", "Copy link", "Cite", "PDF".
- **Below it, the page's own sections only**, which then fit on one line at 1440 px for every page today.
- **At the foot of the page:** "Related" (cards of related items) and "Data used" (each dataset with its dictionary entry and a link that puts it on the map).

The review notice of decision 65 stays where it is, near the top of the page.

## 8. Links both ways

- **Dictionary:** each dataset entry used by a published item gets "Used in" with links.
- **Map:** the info of a layer in the "On the map" panel says "Used in …" when an item uses it.
- **Explore:** a topic lists every item whose `domains` include it, so Urban heat also appears under Health and Hazards.
- **Ask:** "What has FPR studied about heat?" answers from the registry with the cards, and "how do I cite this?" gives the item's cite text.

## 9. Sharing and the internal track

**Sharing kit** (on every area page):
- **Copy link:** to the page, to a section, or to a chart's current view (the address already holds the view; a button makes it findable).
- **Cite:** the item's cite text, with the date and the link.
- **PDF:** a print stylesheet that drops the top bar and the menus, prints the charts as they are, and adds the cite text and the date on the first page.
- **Embed:** a short guide for putting a page or a chart on the FPR website (`SHARE.md` has one for the map).

**Internal track.** `fpr-platform` already has public, internal and local tiers, a gate (`tools/fpr_gate.py`) and a staff-site design (Entra sign-in). An internal knowledge item uses the same page format and registry fields, with `audience: internal`. The gate keeps it out of the public build. Publishing means: review (Compliance, leadership, a native Spanish reader, as needed), then `audience: public`, then a normal PR to this repository. This part waits on IT: `fpr-platform` is not yet a GitHub repository, and the staff site is not set up.

## 10. Options

- **Option A (recommended): home page, one header, registry fields.** Everything in sections 5 to 9. It scales to dozens of items, and every door can point to the same items.
- **Option B: keep the strip, make it a menu.** Replace the eight tabs with one "All areas" menu, and keep everything else. One PR, but no home page, no kinds, no "also in", no "Used in".
- **Option C: a full research portal later.** Tags, authors, versions, comments. More than FPR needs now. Option A's registry leaves room for it.

## 11. Pull requests (Option A)

1. **Registry fields and the Knowledge home page.** `knowledge_src/items.json`, the build into `core/knowledge.js`, tests, `knowledge.html`, the top bar button. **First visible change.** The tabs stay until PR 2.
2. **One header on each area page.** Breadcrumb, status with the reviewer, "All areas", the page's own sections only; Related and Data used at the foot. Remove the strip.
3. **Links both ways.** "Used in" in the dictionary and in the "On the map" panel; Explore lists items by `domains`; Ask answers from the registry.
4. **Sharing kit.** Copy link, Cite, the print stylesheet, the embed guide.
5. **Internal track.** The same format in `fpr-platform` with the gate, after IT creates the repository and the staff site.

Each PR merges only on Francis's word. Every new word visitors see gets a sourced Spanish and English definition where it is technical, and goes through the Spanish string layer (`i18n_src/`).

## 12. Risks and limits

- **Summaries and dates must be checked.** The cards' one-line summaries and month dates on the canvas are drafts. PR 1 takes each from its page, and Francis or the page's owner confirms them.
- **Program terms.** The home page lists published items only, including those that keep the "In review" marker (they are published). Items that are `in_review` or `hidden` never get a card, so the ban on program terms is unchanged.
- **Spanish.** "Conocimiento", the kinds and the new buttons need a native reader, as every Spanish string does.
- **Weight.** Area pages get a small header script; each page's budget is checked in each PR.
- **Old links.** Every area keeps its page name. Links to `housing.html` from the old top bar keep working.

## 13. Decision 90 (approved by Francis on 2026-11-09: "Approve and merge", (a) to (f) as proposed)

- (a) **Option A**, B or C.
- (b) **The kinds:** study, analysis, program tool, index profile. Names in Spanish: estudio, análisis, herramienta del programa, perfil de índice.
- (c) **The top bar name:** "Knowledge" / "Conocimiento", or keep "Knowledge Area" / "Área de conocimiento".
- (d) **Status moves off the tabs** to the page header and the cards, with the reviewer named.
- (e) **The internal track waits on IT** (`fpr-platform` repository and staff site); PRs 1 to 4 do not depend on it.
- (f) **The order of the PRs** in section 11, PR 1 first.
