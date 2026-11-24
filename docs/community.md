# Community assets: historic places, city halls, treatment facilities and non-PRASA water (2026-10-18, branch `community-assets`)

The project lead approved these four datasets on 2026-10-18. They come from official, current sources (not WCRP).

- `community_assets.py` writes `historic_places.geojson`, `town_halls.geojson` and `community_series.json` (counts by municipio).
- `infrastructure_series.py` adds two datasets on water systems outside PRASA to `infrastructure_series.json`.

## What was built

| Layer | Source | Licence | Vintage (2026-10-18) | Count | Refresh |
|---|---|---|---|---|---|
| Historic places (points and counts) | NPS, National Register of Historic Places, public locations map service, layers 0 and 1 | Public domain: a US Government work; the service's licence field says "For general public distribution" (decided by FPR on 2026-10-18) | edits up to 2026-08-07; newest listing 2026-01 | 342 listings counted, in 74 municipios; 277 points for 269 listings drawn; 73 counted only | unit `community` on a runner; monthly count check |
| City halls (points) | OpenStreetMap, `amenity=townhall`, through Overpass | ODbL 1.0, credit © OpenStreetMap contributors | OSM data of 2026-10-18 | 65 features: 63 city halls in 62 municipios, 2 annexes | by hand: `--refresh townhall` (runners cannot reach Overpass); guide to map the 16 missing: `docs/osm-city-halls.md` |
| Treatment facilities (counts only) | SAMHSA, 2025 National Directories (N-SUMHSS 2024), Excel | Public domain (SAMHSA's Public Domain Notice; not for resale) | survey of 2024, released 2026-03-06 | 87 facilities: 28 substance use only, 17 mental health only, 42 both | unit `community`; the check reads the newest year on the National Directories page |
| Water systems outside PRASA (counts only) | EPA ECHO, Safe Drinking Water Act (the same download as `water_systems`) | US federal data (public domain) | ECHO of 2026-10-14 | 207 systems serving 100,743 people, in 47 municipios | unit `infrastructure` |

## Rules

- **Points carry only** name, type, municipio and GEOID; historic places add the listing date, city halls the OpenStreetMap id. A pop-up shows those and the source.
- **Historic places.**
  - Placed by their point, not by NPS's county field, which often names another municipio.
  - One point per listing and municipio. A historic road or irrigation system with points in several municipios counts in each, and once in Puerto Rico's total.
  - 14 listings have only an outline: each is placed at a point inside it.
  - Two points at sea (a lighthouse on a cay, a crash site) go to the municipio their listing's city names; one irrigation point at sea is left out of the municipios.
  - **Private homes are counted, not drawn** (decided by FPR on 2026-10-18). A listing that is a private residence, or whose name holds a street address or house number, counts in its municipio (`nrhp_places`) but gets no point, and its name is in no published file. The points file's notes give how many by municipio (`counted_not_drawn_by_municipio`).
  - **How residences are found.** NPS's public service has no ownership, category or use field (only the resource type: building, structure, site, district, object), so the build picks names to review by pattern: Casa, Casona, House, Residencia, Residence, Home, Villa, Chalet, Quinta, Manor, Dwelling, Apartments, Retreat, Mansion, Hacienda, any number, `#`, Calle, Street, Avenida, Avenue. Each match is decided by hand in `nrhp_review.json`, with a reason: `public` (drawn: city halls, museums, public heritage sites, government and university buildings, numbered bridges, roads and lodges) or `residence` (counted only; listed by NPS reference number only, so the file does not repeat their names). `residence` also holds one house the patterns miss (NPS spells it "Case"). A listing that matches and is in neither list is counted only until someone reviews it; `tests/test_community.py` fails when that happens.
  - **On 2026-10-18:** 114 listings match; 43 are public and drawn, 71 are residences (7 of them named by a street address or house number, 10 of them haciendas), plus the one the patterns miss: 72 counted only, 270 drawn. After the final review of PR #60, one more listing (85003087, a home for the elderly when listed in 1985; current use not confirmed) is counted only: 73 counted only, 269 drawn.
  - **Haciendas** (added to the patterns on 2026-10-18, after a review found six plantation listings drawn only because their names matched no pattern; no listing is named Finca or Estancia). A hacienda is drawn only when it is publicly owned or operated, or a public heritage site; when ownership or use is not confirmed it is counted only. Drawn: Hacienda Azucarera La Esperanza and Hacienda Buena Vista (Para la Naturaleza, open to the public). Counted only, by NPS reference number: 100010389 in Moca (privately owned; a family's private museum, by appointment), 100011591 in Guayanilla (still owned by its founding family; use not confirmed), 85000295 in Camuy (private and unoccupied when listed), 06000896 in Lares (private when listed; the municipio announced in 2025 a restoration as its tourism office, but public ownership is not confirmed), 95000287 in Sabana Grande and 88001848 in Dorado (private, a single dwelling per their nominations), 84003147 in Guánica (a religious order's convent), 83004662 in Toa Baja (private and abandoned when listed; ruins), plus 77001548 and 87000735, reviewed before. Sources: the NPS nomination forms (NPGallery), Para la Naturaleza, Primera Hora and El Nuevo Día, read on 2026-10-18.
  - **Borderline decisions** (marked "borderline" in the file; a person who knows the places can move them). Drawn: Casa Dr. Agustín Stahl Stamm (bought by the municipio of Bayamón, museum not yet open), Casa Dra. Concha Meléndez Ramírez (owned by the Government of Puerto Rico per its nomination; use not confirmed), Casa Franceschi Antongiorgi (municipal property, a museum closed since the 2020 earthquakes), Figueroa Apartments (an apartment building: the name identifies no household), Residencia Aboy-Lompré (a privately run cultural centre), Superintendent of Lighthouses' Dwelling (federal quarters on the Coast Guard base). Counted only (by NPS reference number, as in the file): 06000896 in Lares and 100010389 in Moca (see Haciendas), 88000966 in Arecibo (the house where a religious congregation began; reported in ruins, owner not confirmed), 77001548 in Vieques (a plantation house later a guest house; current use not confirmed), 83002293 in Naguabo (privately owned when listed, now in ruins), 100008175 in San Juan (a physician's house; no public use found). Apartment and office buildings whose names match no pattern (for example La Giralda, now offices) stay drawn.
  - The reasons come from the listings' names and types and from public descriptions read on 2026-10-18 (NPS nomination records, museum and news pages); NPS gives no ownership data.
- **City halls.** Gaps are reported, never filled. On 2026-10-18 there is none mapped in Adjuntas, Aguas Buenas, Arroyo, Barceloneta, Barranquitas, Cidra, Coamo, Florida, Guayama, Hormigueros, Juana Díaz, Juncos, Orocovis, Quebradillas, Río Grande and San Sebastián (`notes.municipios_without_a_city_hall_mapped`). No count dataset: every municipio has one city hall. FPR decided on 2026-10-18 that a person at FPR will add the missing ones in OpenStreetMap from official sources; `docs/osm-city-halls.md` is the guide. The build still adds none by hand.
- **Treatment facilities.** Counts only, by municipio and type: substance use only, mental health only, both. No names, addresses or points, because these are sensitive services.
  - The two Excel files are read in memory. The cache keeps the directory, the city, the state, the type-of-care codes and a one-way hash of the name and address (to join the two directories). Nothing else reaches the disk.
  - The Economy tab shows them per 1,000 residents when shaded.
  - The directories leave out facilities that did not answer the survey and most individual practitioners.
- **Water systems outside PRASA.**
  - EPA Region 2 defines non-PRASA systems as the privately owned ones; the count is the systems SDWIS records as privately owned (owner type P). FPR accepted this measure, with the caveat below, on 2026-10-18.
  - SDWIS records some community-run systems as local government, PRASA's owner type, so the count can miss a few (EPA Region 2 counted 241 community systems serving about 93,500 people in 2025).
  - Residents served are given to a municipio only when the system serves that one alone (5 systems with 1,087 people serve two municipios; they count in Puerto Rico's total).
  - Names are never kept or published: many systems are named after a person, a family or a farm.
  - **No barrio figures.** No open source gives where these systems are below the municipio (see "Skipped").

## Skipped, and why

- **Non-PRASA locations by barrio.** ECHO and SDWIS give municipios only. EPA's Community Water System Service Area Boundaries has 70 Puerto Rico systems, almost all PRASA's. FRS points match 77 of 404 systems. EPA Region 2's assessment database (2022-2024) has coordinates but is not public. `wanted.json` row `non-prasa-locations` (blocked) holds the question for EPA Region 2 and the Department of Health.
- **SAMHSA's live locator (FindTreatment.gov API).** Its guide states no licence and speaks of "approved users"; a test query for Puerto Rico returned nothing. `wanted.json` row `samhsa-locator` holds the question.

## On the map and in the engine

- **Layers tab.** Two switches, loaded on first use through `js/facilities.js` (and its Spanish): City halls (`townhalls`) and Historic places (`historic`). Since 2026-10-19 both are in the group Community services (Servicios comunitarios; named Services to the community until 2026-10-20; `docs/layers.md`), under Government and Education and culture, in the 2D map and the 3D view (`js/facilities3d.js`; both views draw them with `js/core/facilities.js`, see `docs/facilities.md`).
- **Economy tab, chat, area profiles and 3D columns.** 7 new datasets, in two new groups (Education · Historic places; Health · Treatment facilities (SAMHSA)) and in Infrastructure · Drinking water: 295 in all.
- **Chat.** Two fixes found while checking: "historic places" no longer reads as a question about change over time, and an "ask" phrase now matches a question that writes it with a hyphen ("non-PRASA water systems").

## Refresh

| Unit | Command | Where | Review |
|---|---|---|---|
| `community` | `python community_assets.py --refresh nps,samhsa` | a runner (`rebuild.yml`) | automatic |
| `osm` (city halls) | `python community_assets.py --refresh townhall` | by hand | a person |
| `infrastructure` (non-PRASA) | `python infrastructure_series.py --refresh` | a runner | automatic |

Freshness checks (`refresh/sources.json`): `nps_nrhp` counts Puerto Rico's points and polygons every 30 days (the layers have no edit date); `samhsa_nsumhss` reads the newest directory year every 14 days, daily in February to April. `python community_assets.py --check` rebuilds from the cache with no network.

## Weight

Measured with gzip level 6 on an LF copy (`budget.py`); before is `main` at 9ba7077.

- **Map scripts:** 248.7 → 249.1 KB of 250 (the two switches, their Spanish, the dataset labels and one line of `core/datasets.js`).
- **Map data:** 172.7 → 173.3 KB (the catalog, 204,647 bytes of its 204,800 limit).
- **Area profile data:** 606.5 → 610.1 KB of 650 (`community_series.json`, 2.5 KB compressed); 610.3 KB after decision 44 (the notes on residences).
- **Dictionary data:** 692.1 → 698.8 KB of 720 (`dictionary.json`); 699.3 KB after decision 44.
- **Loaded on first use:** `historic_places.geojson` (10.5 KB compressed; 9.2 KB after decision 44, with 286 points instead of 350; 9.0 KB with 278 points after the hacienda review) and `town_halls.geojson` (2.5 KB); `facilities.js` grows from 2.5 to 3.1 KB and its Spanish from 1.6 to 2.3 KB (both with the residence note).
- Decision 44 left the map's scripts (249.1 KB of 250) and data (173.3 KB) unchanged; measured on an LF copy of the staged tree. The hacienda review (2026-10-18) left them unchanged too: map 249.1 KB scripts, 173.3 KB data; area profile 610.3 KB; dictionary 699.3 KB; catalog 204,646 bytes.

Slow 4G (`tests/browser/throttle.js`, two runs, Spanish, own Chrome on port 9361): map 798 and 749 → 802 and 753 KB, ready 4.8 and 4.7 → 4.9 and 4.8 s; area profile 894 → 898 KB, ready 5.6 → 5.7 s; dictionary 901 → 907 KB, ready 5.5 → 5.5 s; 3D and Housing unchanged. `throttle.js` exits 2 before and after for the known reason (`routes.json` omits `gateway_series.json` for the profile).
