# Public facilities and nonprofits (2026-10-17, branch `facility-layers`)

Two harvesters add four point layers to the 2D map and 17 datasets for the 78 municipios and Puerto Rico:

- `facilities.py` writes `public_housing.geojson`, `fire_stations.geojson`, `police_stations.geojson`, `libraries.geojson` and `facility_series.json` (counts by municipio).
- `nonprofits.py` writes `nonprofit_series.json` (counts only).

The project lead approved points with a name, a type and a location only. A pop-up shows the name, type, municipio and source, nothing else.

## Sources

Each source is read through its live service, never a static copy, except HUD's LIHTC database (added 2026-10-31, decision 71), whose archive is saved by hand because HUD USER refuses scripts. Each layer and count carries its own vintage (the files' `vintage` and `notes.vintages`, and each dataset's reference line).

| Layer | Source and service | License | Vintage (2026-10-17) | Count |
|---|---|---|---|---|
| Public housing developments | HUD eGIS, Public Housing Developments (ArcGIS REST) | U.S. Public Domain (HUD's open data catalog) | date of coverage 06/2026; HUD updates quarterly | 304 developments, 54,094 units; 172 drawn |
| Tax credit housing projects (LIHTC) | HUD USER, National LIHTC Database (`LIHTCPUB.ZIP`, saved by hand to `cache/facilities/`; `python facilities.py --only lihtc`) | US Government work (17 U.S.C. 105) | release of 2026-05-28: projects placed in service 1987 to 2024 | 245 projects, 22,890 low-income units; 67 drawn |
| Fire and EMS stations | USGS The National Map, National Structures Dataset, layer 51 (ArcGIS REST) | US federal data, public domain | newest load 2026-07-17 | 94 |
| Police stations | OpenStreetMap, `amenity=police`, through the Overpass API | ODbL 1.0, credit © OpenStreetMap contributors | OSM data of 2026-10-17 | 141 (144 features; 3 mapped twice) |
| Public libraries | USAC E-Rate Supplemental Entity Information (Socrata) | Public Domain (stated on the dataset) | updated 2026-10-16; USAC updates daily | 1,229 placed; 1,101 drawn |
| Nonprofits (counts only) | IRS Exempt Organizations Business Master File, Puerto Rico file | US federal work, public domain (17 U.S.C. 105); the IRS states no license | file of 2026-10-13; about monthly | 2,572 organizations |

**Why these sources:**
- **Fire stations: USGS.** USGS has 94 stations and OpenStreetMap 77, and 74 of those 77 lie within 500 m of a USGS station.
- **Police stations: OpenStreetMap.** USGS has only 8 police stations for Puerto Rico.
- **Libraries: USAC.** IMLS's Public Libraries Survey has no Puerto Rico rows.

## Rules

- **What is kept.** Only the columns in `facilities.KEEP` and `nonprofits.KEEP` reach the cache (`cache/facilities/`, `cache/nonprofits/`).
  - The queries never ask for HUD's housing authority telephone, e-mail or director, USAC's contacts, or OSM's addresses.
  - 17 USAC library names had a telephone number written into them. `clean_name` removes telephone numbers, e-mail and web addresses from every name.
  - Nonprofits: no name, EIN or address is kept.
- **Public housing.** HUD says to map only developments geocoded to the rooftop or the ZIP+4 centroid (`LVL2KX` R or 4).
  - The other 132 sit at the center of a block group or tract, so they are counted in their municipio but not drawn.
  - The layer's note says "172 of 304 drawn".
- **Tax credit housing (LIHTC).** Every project counts in the county of its 2020 tract, or the municipio of the city HUD lists (163 of 245). Drawn only where HUD placed it at a point in a 2020 tract within 1 km of that municipio (67). The 20 projects for people who are homeless or living with HIV, or whose name says they are a care home (an égida, a "Hogar ...", "Golden Living": the sensitive-place words of `places_privacy.py`), are counted, never drawn or named (2026-11-05: 14 care-home names, 6 of them drawn before). No address is kept. The pop-up adds units, low-income units and the year placed in service.
- **Libraries.** The list holds active E-Rate entities of type Library that USAC marks as public.
  - Each library is placed in the municipio of its address: the city or county, or a known postal place such as Río Piedras.
  - It is drawn only where USAC's point lies within 1 km of that municipio. 107 points fall in another town and 21 have no point.
  - In Puerto Rico most entries are community technology centers and community libraries, not only municipal libraries. The dictionary and the help text say so.
- **Police.** The type (municipal, state, or agency not stated) is read from the name and operator tags. A node and its building outline with the same name, within 30 m, count once.
- **Nonprofits.**
  - The municipio is found in this order: the IRS city when it is a municipio's name (2,456); a known postal place, such as Saint Just in Trujillo Alto (28); the municipio holding most of the land of the ZIP code, from the Census 2020 ZCTA-to-county file (88).
  - Groups are the ten NTEE major groups NCCS uses; Z and no code are counted together.
  - Organizations registered only under Puerto Rico law are not in the IRS file.
- **Shelters: not built.** No hurricane-shelter source states a license. See the `shelters` row of `wanted.json` for the sources checked and the question to ask PRDOH. Domestic-violence and child-protection shelters are never published. `tests/test_facilities.py` checks that no shelter file exists and that no facility name reads like one.

## On the map and in the engine

- **Layers tab.** Three new groups when they were added: Housing · public housing, Infrastructure · emergency services and Education · USAC E-Rate. Since 2026-10-19 public housing is in Land and housing, and fire, police and libraries in Community services (Servicios comunitarios; named Services to the community until 2026-10-20; `docs/layers.md`). The layer keys are `pubhousing`, `fire`, `police` and `libraries` (`l=` in the link).
- **Lazy loading.** `js/facilities.js` and its Spanish (`es.map.facilities.js`) load the first time one of these layers or help buttons is used (`app.js` `facLoad`). Each layer's file loads the first time it is switched on. Since 2026-10-18 the same module also draws historic places and city halls (`docs/community.md`).
- **Both views (2026-10-19, phase B of `docs/layers.md`).** What the two views share is `js/core/facilities.js` (`Core.facilities`): each layer's file, switch, color, icon, label, source line and credit, the pop-up (name, type, municipio, listing date of a historic place, source; no contact field), the note under the switch (what is drawn, of how many, and what is counted but not drawn) and the help texts. The 2D map's `facilities.js` keeps its Leaflet drawing; the 3D view's `facilities3d.js` draws the same files with MapLibre, above the areas and under the base map's labels. Each view loads the core file with its own renderer, on first use (`app.js` and `twin3d.js` `facLoad`), with its page's `facilities` bundle (`es.map.facilities.js`, `es.threed.facilities.js`). The rules on what is drawn are in the files, so both views keep them: HUD developments placed at a block group or tract center, NRHP private homes and haciendas and libraries whose point lies in another town are counted by municipio and not drawn.
- **The Reservoirs page (2026-11-10, decision 98).** `reservoirs.py` also writes `reservoir_history.json` for the Knowledge Area page `reservoirs.html`: each reservoir's range and record low, the mean of each week in each year 2011-2025, its monthly means since its gauge began and its last 400 days. The history of a gauge starts after the last year before 2011 whose median lies more than one 2011-2025 range outside it (Toa Vaca reported a depth until 2005; Cerrillos was filling in 1991-1992), and single values more than three ranges below the low are left out. The page uses the map layer's rule for 'usual' and adds the latest readings and daily values from USGS in the browser (`fetchRetry`).
- **Reservoir levels (2026-11-02).** The same module draws `reservoirs.geojson` (`reservoirs.py`, USGS Water Data; HANDOFF decision 74) with a pop-up of its own (`resPopup` in `core/facilities.js`): level now, change in 7 days, where it falls against the same week in 2011-2025, and a 120-day chart. `Core.facilities.live()` asks USGS for the latest readings when the layer is switched on (one request, at most every 10 minutes); both renderers call it and update the note. In the 3D view the pop-up reads the reservoir's arrays from the file, because MapLibre returns a clicked feature's arrays as text. **Checked** on 2026-11-02: the USGS reading (72376) matched the level on AAA's 05:00 chart to within 0.08 m for 18 of its 19 reservoirs (La Plata differed by 0.26 m, a rise during the day); AAA's chart was read on its website and is not kept here, because its alert levels are not published (decision 74 d).
- **River levels and flood reference levels (2026-11-12).** `river_gauges.py` now also keeps each gauge's height of water (`stage`, USGS parameter 00065, meters on the gauge's own scale; all 71 gauges report it) and the flood reference levels USGS has surveyed (`refs`, from USGS Real-Time Flood Impacts: the top of the riverbank, the lowest beam and the deck of a bridge, a past flood's high-water mark). Puerto Rico has four, all at one gauge (Río de la Plata at Comerío). The pop-up gives the level and how far the water is from each reference (`floodRefs`, `moreHtml` in `core/facilities.js`); `Core.facilities.live()` asks for the gauge heights in one more request (`GAUGE.rivers.more`). Water temperature (00010) is read the same way, but no river gauge reported it on 2026-11-12. The flows, the history and the usual ranges of the file are unchanged (built from the same cache).
- **Flood stages of the National Weather Service (2026-11-12).** `river_gauges.py` reads NWS's National Water Prediction Service (`api.water.noaa.gov/nwps/v1/gauges`, no key, public domain; source record `nws_nwps`): the gauges NWS lists for Puerto Rico (118), each with its USGS site number and its flood categories as a stage in feet. 66 of the 71 river gauges get an `nws` field (the NWS id and the action, minor, moderate and major stages in meters of gauge height). The pop-up (`nwsStages`, `nwsHtml` in `core/facilities.js`) says which stage the water has reached and how far it is from each, with the feet beside the meters, a line that the comparison is the observatory's and not an official warning, and a link to the gauge's NWS page. The stages are read at build time only; the live gauge height they are compared with is the one the layer already asks USGS for.
- **Rainfall (2026-11-12).** `rain_gauges.geojson` (`rain_gauges.py`, the same USGS Water Data API): one point per site that reported precipitation in the last 30 days (54 gauges in 30 municipios on 2026-11-12; 20 rain gauges of their own, the others at river, reservoir and well stations). No single reading means much, so this layer's live step is its own (`liveRain` in `core/facilities.js`, `GAUGE.rain.sum`): the 15-minute readings of the last 24 hours, asked as CSV (about 13 KB compressed; the JSON is 1.3 MB) and added up, then the daily totals of the last 8 days. The pop-up (`rainPopup`) gives the 24-hour total, the total of the last 7 whole days (`rainWeek`), where it falls against the usual rain of that week in 2011-2025, one bar a day for the file's 120 days, a line that this is not a flood warning or a forecast (with a link to the National Weather Service in San Juan) and the gauge's USGS page. Rain is in millimeters (inches x 25.4). 9 gauges have fewer than 8 years of daily totals and no usual range.
- **Groundwater levels (2026-11-12).** `groundwater.geojson` (`groundwater.py`, the same USGS Water Data API) is the third layer that reads USGS live: one point per well that reported a depth to water in the last 30 days (34 wells in 24 municipios on 2026-11-12, of 5,197 well sites USGS lists). The pop-up (`gwPopup`) gives the depth to water now in meters below the ground, the change in seven days, where it falls against the same week in 2011-2025, a 120-day chart drawn with the ground toward the top (`spark` with `flip`), the depth of the well and its USGS page. A depth is read upside down: deeper than the 90th percentile is water lower than usual. A well with fewer than 8 years of daily values is drawn without a usual range (5 on 2026-11-12). `Core.facilities.GAUGE.groundwater` is parameter 72019, feet to meters.
- **River flow (2026-11-11).** `river_gauges.geojson` (`river_gauges.py`, the same USGS Water Data API) is the Reservoir levels layer's sibling: one point per stream gauge that reported a discharge in the last 30 days and has 8 years of daily values in 2011-2025 (71 gauges on 54 rivers and streams on 2026-11-11, of 1,083 stream sites USGS lists). The pop-up (`rivPopup`) gives the flow now in m³/s, the flow seven days ago, where it falls against the same week in 2011-2025, a 120-day chart on a logarithmic scale, a line that a high flow is not a flood warning (with a link to the National Weather Service in San Juan) and the gauge's USGS page. `Core.facilities.GAUGE` names the layers that read USGS live and their parameter (reservoirs 72376, rivers 00060, converted from cubic feet per second); `live()` serves both. Without a key USGS limits the requests an hour: `river_gauges.py` waits when it answers 429 and keeps what it downloaded in `cache/river_gauges/`. Not included: flood stages (the National Weather Service's, `wanted.json` row `streamflow`) and rainfall.
- **Datasets.** `core/datasets.js` adds the two series files as snapshots. The Economy tab, the chat, the area profiles and the 3D columns get 17 datasets, which the engine offers per 1,000 residents. Public housing units are also offered per 1,000 housing units.
- **Spanish held for review.** The Spanish text that names HUD is held in `i18n_src/held_for_review.json`, so the Spanish pages show it in English:
  - two dataset labels;
  - the public housing source line and help;
  - the public housing file's title;
  - two dictionary summaries.

  This follows the repository's safety net (`tests/test_held_for_review.py`). Public housing is not grant money, so the project lead or Compliance can release them.

## Refresh

| Unit | Command | Where | Review |
|---|---|---|---|
| `facilities` | `python facilities.py --refresh hud,usgs,usac` | a runner (`rebuild.yml`) | a person (HUD is `human`) |
| `nonprofits` | `python nonprofits.py --refresh` | a runner | automatic |
| `reservoirs` | `python reservoirs.py --refresh`, then `python river_gauges.py --refresh`, `python groundwater.py --refresh` and `python rain_gauges.py --refresh` (the unit rebuilds the four USGS Water Data files) | a runner, once a month (calendar rule `month`) | automatic |
| `osm` (police) | `python facilities.py --refresh osm` | by hand | a person |

- **Police on a runner.** A runner cannot reach Overpass, so a clean runner rebuilds the police layer from its published file.
- **Freshness checks** (`refresh/sources.json`):
  - HUD's last edit date;
  - the count of USGS Puerto Rico stations;
  - the count of USAC's active public libraries in Puerto Rico;
  - the IRS file's `Last-Modified` date.
- **Checking without the network.** `--check` rebuilds both harvesters from the cache.

## Weight

Measured with gzip level 6 on an LF copy (`budget.py`):

- **Map scripts:** 246.0 → 247.1 KB of 250. This adds the layer switches, their Spanish, the dataset labels and the loader.
- **Map data:** 169.9 → 171.2 KB. This is the catalog.
- **Loaded on first use:**
  - `facilities.js` 2.6 KB and its Spanish 1.6 KB;
  - public housing 4.7 KB;
  - fire stations 2.6 KB;
  - police stations 5.1 KB;
  - libraries 22.0 KB.
- **The two series files** add 5.7 KB to the Economy tab and the profile.

Slow 4G (`throttle.js`, two runs, Spanish):

| Page | Transferred, before → after (KB) | Ready, before → after (s) |
|---|---|---|
| Map | 795 and 746 → 797 and 748 | 5.2 and 5.0 → 5.2 and 5.0 |
| Area profile | 875 → 883 | 5.7 and 5.8 → 5.8 and 5.8 |
| Dictionary | 877 → 888 | 6.1 → 6.1 |

**Area layers.** `core/facilities.js` also holds area layers (`area: { prop, breaks, colors }`), drawn as filled polygons with a legend by both renderers: the FCC broadband hexagons (`broadband`, `broadband_hex.geojson`, built by `broadband.py`; `docs/broadband.md`, decision 101) and the Opportunity Zones 2.0 (`oz`, `oz_tracts.geojson`, built by `opportunity_zones.py`; `docs/opportunity-zones.md`, decision 103). An area layer whose classes are kinds rather than ranges of a number names them in `labels` and the legend in `title`; `tip(k, p)` is the 2D map's hover text of any area layer.

**Line layers.** A layer with `line: true` is drawn as lines in one color (`fprroutes`). `line` can also be an object, `{ prop, colors, labels, width: { prop, max, lo, hi }, dash, weight, opacity, title }`: the público routes of the 2020 list (`publicos`, thinner lines) and the simulated connections between municipios (`links`: colored by class, wider where more workers travel, dashed, with a legend). `Core.facilities.lineStyle(k, properties)` gives the 2D renderer a feature's color, width and dash; the 3D renderer builds the same from the layer's spec. Both files are built by `transit_links.py` (`docs/transit-links.md`, decision 105). The traffic layer (`traffic`, `traffic_roads.geojson`, built by `traffic.py`, `docs/traffic.md`) uses the same line spec: six color classes by vehicles a day and a width by the count, solid; its legend draws solid lines because it has no `dash`. `tip(k, p)` gives the 2D hover text of a stretch (route and count) and returns null for layers whose features have a name.
