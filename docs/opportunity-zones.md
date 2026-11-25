# Opportunity Zones 2.0

HANDOFF decision 103 (2026-11-13). The project lead asked for a Knowledge Area page and a map layer that show "las 178 áreas de Puerto Rico designadas bajo Opportunity Zones 2.0". This settles option 3 of `PUBLIC_MONEY_V2_PLAN_2026-10-30.md` (decision 71 (f) left Opportunity Zones out "until plan decision 3 is settled"): the nominations are over and the designations are final, so the layer shows the designated zones and the page shows the eligible tracts beside them.

## What the program is

A Qualified Opportunity Zone is a low-income census tract in which a capital gain invested through a Qualified Opportunity Fund earns federal tax benefits (26 U.S.C. 1400Z-1 and 1400Z-2). The One Big Beautiful Bill Act (P.L. 119-21, section 70421, July 4, 2025) made the incentive permanent with a new round every ten years, and for Puerto Rico:

- ended the 2018 rule (Bipartisan Budget Act of 2018, section 41115) that deemed every low-income tract of Puerto Rico a zone: from 2027, Puerto Rico follows the limit of the states, a quarter of its eligible tracts, rounded up;
- narrowed the low-income community test: median family income at most 70% of the area's (was 80%), or a poverty rate of 20% or more with median family income at most 125% of the area's; contiguous tracts can no longer be zones;
- added larger benefits for zones made entirely of rural area (a 30% basis increase after five years instead of 10%, and a lower substantial-improvement threshold, Notice 2025-50).

Treasury published the eligible tracts with Rev. Proc. 2026-14 and designated the nominated tracts on 2026-11-05, effective 2027-01-01 for ten years. The first round's zones of Puerto Rico stay in effect until 2027-12-31 (Rev. Proc. 2026-14, section 2.02(3)(d)), so both sets apply during 2027.

It is a federal tax incentive for private investment, not a grant: the files and the page say so, and say nothing of who invested.

## Files

| File | What | Built by |
|---|---|---|
| `site/data/opportunity_zones.json` | Every 2020 tract (981): status (2 zone rural, 1 zone not rural, 0 eligible not designated, -1 not eligible), Treasury's rural flag, poverty rate, median family income and its percent of the area's (ACS 2020-2024, as Treasury published them), the comparison area, 2020 residents and housing units, land, barrios with residents; barrios (residents, in zones, in eligible tracts); municipios; Puerto Rico; medians by status; the first round | `opportunity_zones.py` |
| `site/data/oz_tracts.geojson` | The map layer: the 178 designated tracts, rural or not, with the pop-up's fields | `opportunity_zones.py` |

`python opportunity_zones.py` downloads what is missing into `cache/oz/`; `--refresh` reads Treasury's page again and takes the newest files it names; `--check` rebuilds from the cache and fails when a published file differs. `build.py` runs it after `geo.build` (it needs the crosswalk and the tract outlines). Refresh unit `oz` (`refresh/sources.json`): the probe reads the date in the name of Treasury's designation file every 30 days; a person reviews the rebuild.

## Sources (no key)

- **Treasury, Office of Tax Policy, Data Transparency for Qualified Opportunity Zones**: `OZ2-Designations-2027-Data-Transparency-10302026.xlsx` (6,576 tracts; Puerto Rico 178: 82 rural, 96 not) and `OZ2-Eligible-Tracts-Data-Transparency-10302026.xlsx` (85,529 tracts; Puerto Rico 981, of which 712 eligible). The page's HTML is minified, so the build reads the `href` with or without quotes.
- **CDFI Fund**: the full list of 2027 designations (`/media/8018881/download`, 2026-11-05), checked against Treasury's: the build stops if Puerto Rico's tracts or rural status differ (they do not); and the 2018 list (`designated-qozs.12.14.18.xlsx`: 863 Puerto Rico tracts, 837 low-income and 26 contiguous, including the two tracts Notice 2019-42 added, 72119130102 and 72137122002).
- **Census Bureau**: the observatory's crosswalk (2020 tracts, barrios and municipios with residents and housing units; residents of each barrio in each tract, blocks counted whole), the tract outlines (`geo/tracts.geojson`, 1:500,000), and TIGERweb's Census 2010 tracts (layer 14, `POP100`) for the first round's residents.

## Checks (the build stops on any)

- Every designated tract is eligible in Treasury's file, with the same rural status in both files and in the CDFI Fund's list.
- No more designated tracts than the limit (a quarter of the eligible, rounded up; 25 when a state has fewer than 100 eligible): 178 of 712, exactly the limit.
- Treasury's tracts are the crosswalk's 981; every designated tract has residents and an outline.
- The barrios and the municipios add up to Puerto Rico's residents in zones; no barrio has more residents in zones than in eligible tracts, or than it has.

One more check, run while building (not in the build): the law's test applied to Treasury's poverty rate and income percent gives exactly Treasury's eligibility for all 899 tracts with an income figure, and the poverty test alone for the 82 without one (0 differences). `tests/oz_page.test.js` keeps it true.

## Figures (designations of 2026-11-05)

- 178 zones: 96 not rural, 82 rural; 676,727 residents (20.6% of the 2020 Census), 331,024 housing units, 2,185.5 km² of land; every one of the 78 municipios has at least one (1 to 7).
- 712 eligible tracts (2,498,032 residents, 76.0%), 243 of them rural; 269 not eligible (221 with residents).
- Medians (ACS 2020-2024): poverty 49.1% (rural zones), 47.2% (zones not rural), 46.2% (eligible, not designated), 23.6% (not eligible); median family income 84.1%, 81.7%, 84.6% and 150.6% of the area's.
- First round: 863 of 945 tracts of 2010, with 3,634,395 residents (97.5% of the 2010 Census).
- Some announcements gave 97 tracts not rural (82 + 97 = 179); Treasury's and the CDFI Fund's files both have 96. The page says so in its method.

## The map layer

`oz` (Layers > Economy, `l=oz`), in the shared list `site/js/core/facilities.js` as an area layer (`area: { prop: 'c', breaks: [2], colors, labels, title }`): purple `#5e3c99` for zones not rural, orange `#e66101` for rural zones, a pair that color-blind readers tell apart. `labels` and `title` are new keys of the area kind: the classes' names when they are kinds, not ranges; `tip(k, p)` gives the 2D map's hover text of any area layer. The 2D map and the 3D view draw it with no code of their own. The eligible tracts that were not designated are only on the page, so the map does not read as a second kind of zone.

The layer adds a group **Economy** (icon `work`) to both menus, after Reference and before Housing (the order of `dictionary_src/domains.json`).

## The page (`opportunity-zones.html`)

Written by `docs/analysis/opportunity-zones-2026-11/make_page.py` (every string an English and Spanish pair; figures read from the data file); `site/js/oz_page.js` draws: the figures; a tract map in four statuses with a tract card (`#t=` in the address); the municipios (sortable); the barrios of a municipio or the 25 with the most residents in zones (`#m=`); a scatter of poverty rate against income percent with the law's lines and the medians by status; the two rounds side by side; what the incentive offers investors (from the statute as amended); method and sources. Published with the "In review" marker, the AI notice and `noindex` (`review: true`, `ai: true`), like the other new areas.

## Not done (for later, if wanted)

- No Economy-tab series (residents in zones by municipio as a dataset): the page and the layer cover it; a series would need the Economy tab's counts updated (see the Public money v2 notes).
- No investment data: Treasury publishes Opportunity Fund investment only in aggregate studies (Office of Tax Analysis, working papers 123 and 128), not by tract.
- No first-round layer (2010 tracts) and no tract-by-tract comparison of the rounds: different censuses.
- Puerto Rico's own incentives tied to the zones are not covered.
