/* PR Data Observatory core: the public facility layers of the 2D map and the 3D view, in one place. Public housing developments (HUD), tax credit housing projects
   (HUD's LIHTC database), fire and EMS stations (USGS), police stations (OpenStreetMap), city halls (OpenStreetMap), public libraries (USAC E-Rate) and historic
   places (NPS), each from its own file (data/<layer>.geojson, built by facilities.py and community_assets.py), and FPR's Eastern Region baseline (fpr_baseline.py): illegal dumping
   sites and the municipal routes FPR traced. The files hold only what may be drawn: what is counted
   and not drawn (HUD developments and LIHTC projects placed only at the centre of an area, LIHTC projects for people who are homeless or living with HIV, NRHP private
   homes and haciendas, libraries whose point is in another town) is in each file's notes, never in its features.

     LAYERS[k]          { id (the switch), file, color, icon, label, source, attribution, line?, area? } for k in pubhousing, lihtc, fire, police, townhalls, libraries,
                        historic, reservoirs, rivers, groundwater, rain, dumping, fprroutes, publicos, links, traffic, bridges, airports, ferries, evcharge, broadband, oz, plants, powerlines; line: the file holds lines (FPR's traced routes, the público routes of the 2020 list, the simulated connections between municipios), drawn as lines, not circles, in one colour or by class and width (lineStyle);
                        area: the file holds polygons filled by one property in classes ({ prop, breaks, colors, labels?, title? }: broadband, the FCC's H3 hexagons;
                        oz, the Opportunity Zones 2.0, rural or not), with a legend; labels: the classes' names when they are kinds, not ranges of a number
                        sized: points whose circle AREA is in proportion to a number and whose colour is a category ({ prop, cat, k, min, cats, colors, labels, sizes, unit, title,
                        hollow }: plants, EIA's power plants by MW and main technology; bridges, FHWA's bridges by daily traffic and condition; evcharge, the charging
                        stations by ports); r instead of k: one radius for all (airports); hollow { prop, value, label, fill }: those features are drawn hollow, dashed in 2D
                        (a planned plant, a closed bridge, a station temporarily unavailable)
     areaClass(k, v)    the class (0..colors.length - 1) of a value of an area layer, -1 when there is none; legendHtml(k, d): its legend (area and sized layers), under the layer's note
     sizedStyle(k, p)   a sized layer's circle for a feature: { r (px), color, planned }; both renderers draw it the same way
     tip(k, p)          the 2D map's hover text of an area of an area layer
     popup(k, p, d)     the pop-up of a facility: its name, type, municipio, listing date (historic places), units and year placed in service (LIHTC) and source
                        line, nothing else (no contact fields, no address); for a layer with hazards: true, the hazard areas its point stands in (p.hz)
     HZ_FILE, attachHazards(k, d, hz)  facility_hazards.json (facility_exposure.py, decision 107 step 3): the flags of the flagged points of each tested layer, by
                        point; a renderer loads it once with the first tested layer and attaches each point's flags to its properties (p.hz: f flood, s sea level
                        rise, l landslide). The public schools (schools) carry their own flags in their file.
     noteText(k, d, where)  the note under the layer's switch: what is drawn, of how many, and what is counted but not drawn; where: where the view shows the counts by municipio
     addHelp(HELP)      the texts of the layers' help buttons (fac_<k>), translated when shown

   The renderers load this file first, on first use: js/facilities.js (2D, Leaflet; app.js facLoad) and js/facilities3d.js (3D, MapLibre; twin3d.js facLoad).
   Any renderer that reads Core.facilities draws every layer here, points, lines and areas alike, so a map added later gets them all (broadband included) by
   drawing the three kinds; a layer is added once, here.
   Their Spanish is the page's "facilities" module bundle (i18n_src/pages.json). */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('facilities', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc, num } = dep('text');
  const TK = (s) => s;   // an English text translated where it is shown, with T() (the language tool reads it like T())
  const FPR_SOURCE = TK('FPR, Eastern Region baseline field survey ({date})');
  const LAYERS = {
    pubhousing: { id: 'lyPubHousing', file: 'public_housing.geojson', hazards: true, color: '#6A3D9A', icon: 'home_work', label: TK('Public housing developments'),
      source: TK('HUD, Public Housing Developments (date of coverage {date})'), attribution: TK('Public housing: HUD') },
    lihtc: { id: 'lyLihtc', file: 'lihtc.geojson', color: '#AD1457', icon: 'house', label: TK('Tax credit housing projects'),
      source: TK('HUD, National LIHTC Database (release of {date})'), attribution: TK('Tax credit housing: HUD LIHTC Database') },
    fire: { id: 'lyFire', file: 'fire_stations.geojson', hazards: true, color: '#C62828', icon: 'health_and_safety', label: TK('Fire and EMS stations'),
      source: TK('USGS, National Structures Dataset (loaded up to {date})'), attribution: TK('Fire stations: USGS The National Map') },
    police: { id: 'lyPolice', file: 'police_stations.geojson', hazards: true, color: '#1F3A93', icon: 'shield', label: TK('Police stations'),
      source: TK('© OpenStreetMap contributors, ODbL (data of {date})'), attribution: TK('Police stations © OpenStreetMap contributors (ODbL)') },
    libraries: { id: 'lyLibraries', file: 'libraries.geojson', hazards: true, color: '#0F7B6C', icon: 'menu_book', label: TK('Public libraries'),
      source: TK('USAC, E-Rate Supplemental Entity Information (updated {date})'), attribution: TK('Libraries: USAC E-Rate') },
    schools: { id: 'lySchools', file: 'public_schools.geojson', hazards: true, color: '#E65100', icon: 'school', label: TK('Public schools'),
      source: TK('NCES, Common Core of Data school directory, school year {date} (Urban Institute Education Data API)'), attribution: TK('Public schools: NCES Common Core of Data') },
    historic: { id: 'lyHistoric', file: 'historic_places.geojson', color: '#8C4A12', icon: 'museum', label: TK('Historic places'),
      source: TK('NPS, National Register of Historic Places (edited up to {date})'), attribution: TK('Historic places: National Park Service') },
    townhalls: { id: 'lyTownhalls', file: 'town_halls.geojson', hazards: true, color: '#455A64', icon: 'account_balance', label: TK('City halls'),
      source: TK('© OpenStreetMap contributors, ODbL (data of {date})'), attribution: TK('City halls © OpenStreetMap contributors (ODbL)') },
    reservoirs: { id: 'lyReservoirs', file: 'reservoirs.geojson', color: '#1565C0', icon: 'water', label: TK('Reservoir levels'),
      source: TK('USGS Water Data: water-surface elevation (daily values to {date}; usual range from {years})'), attribution: TK('Reservoir levels: USGS Water Data') },
    rivers: { id: 'lyRivers', file: 'river_gauges.geojson', color: '#00838F', icon: 'water', label: TK('River flow'),
      source: TK('USGS Water Data: discharge (daily values to {date}; usual range from {years})'), attribution: TK('River flow: USGS Water Data') },
    groundwater: { id: 'lyGroundwater', file: 'groundwater.geojson', color: '#827717', icon: 'water', label: TK('Groundwater levels'),
      source: TK('USGS Water Data: depth to water (daily values to {date}; usual range from {years})'), attribution: TK('Groundwater levels: USGS Water Data') },
    rain: { id: 'lyRain', file: 'rain_gauges.geojson', color: '#EF6C00', icon: 'water', label: TK('Rainfall'),
      source: TK('USGS Water Data: precipitation (daily totals to {date}; usual range from {years})'), attribution: TK('Rainfall: USGS Water Data') },
    dumping: { id: 'lyDumping', file: 'illegal_dumping.geojson', color: '#6D4C41', icon: 'delete', label: TK('Illegal dumping sites'),
      source: FPR_SOURCE, attribution: TK('Illegal dumping sites: FPR') },
    fprroutes: { id: 'lyFprRoutes', file: 'fpr_routes.geojson', color: '#6A1B9A', icon: 'route', label: TK('Municipal routes mapped by FPR'), line: true,
      source: TK('FPR, routes traced in ArcGIS Pro for the Eastern Region baseline ({date})'), attribution: TK('Municipal routes mapped by FPR') },
    publicos: { id: 'lyPublicos', file: 'publicos.geojson', color: '#00695C', icon: 'directions_bus', label: TK('Público routes (2020 list)'), line: { weight: 2, opacity: .75 },
      source: TK('Instituto de Estadísticas de Puerto Rico and ACT, list of público routes published {date} (CC BY)'), attribution: TK('Público routes: Instituto de Estadísticas de Puerto Rico, ACT') },
    traffic: { id: 'lyTraffic', file: 'traffic_roads.geojson', color: '#cc4c02', icon: 'directions_car', label: TK('Traffic on the main roads'),
      line: { prop: 'c', colors: { 1: '#fee391', 2: '#fec44f', 3: '#fe9929', 4: '#ec7014', 5: '#cc4c02', 6: '#8c2d04' },
        labels: { 1: TK('Fewer than 2,000 vehicles a day'), 2: TK('2,000 to 5,000'), 3: TK('5,000 to 10,000'), 4: TK('10,000 to 20,000'), 5: TK('20,000 to 40,000'), 6: TK('40,000 or more') },
        width: { prop: 'a', max: 80000, lo: 1.2, hi: 7 }, opacity: .9, title: TK('Annual average daily traffic, vehicles a day') },   // c: the class of the count (traffic.py CLASSES); yellow to dark brown, ColorBrewer YlOrBr
      source: TK('FHWA Highway Performance Monitoring System, Puerto Rico, data year {date}'), attribution: TK('Traffic: FHWA HPMS') },
    links: { id: 'lyLinks', file: 'simulated_links.geojson', color: '#e66101', icon: 'route', label: TK('Simulated connections between municipios'),
      line: { prop: 'c', colors: { 1: '#e66101', 2: '#5e3c99' }, labels: { 1: TK('No route listed'), 2: TK('Público route on the 2020 list') }, width: { prop: 'workers', max: 7500, lo: 2, hi: 9 }, dash: [6, 5], opacity: .8,
        title: TK('Simulated connections, by what is listed today') },   // c: 1 no route listed, 2 a público route on the 2020 list (transit_links.py); orange and purple as on transit-links.html
      source: TK('Simulated by FPR from Census commuting flows {date}, published timetables and OpenStreetMap roads; not a proposed route'), attribution: TK('Simulated connections: FPR; Census Bureau; © OpenStreetMap contributors') },
    bridges: { id: 'lyBridges', file: 'bridges.geojson', color: '#b2182b', icon: 'foundation', label: TK('Bridges and tunnels'),
      // c: FHWA's condition (the lowest of the deck, superstructure and substructure ratings, or the culvert's); red to blue (ColorBrewer RdBu, safe for colour-vision deficiency)
      sized: { prop: 'a', cat: 'c', k: 0.024, min: 2.5, cats: ['P', 'F', 'G', 'T'], colors: { P: '#b2182b', F: '#f4a582', G: '#2166ac', T: '#424242' },
        labels: { P: TK('Poor condition'), F: TK('Fair condition'), G: TK('Good condition'), T: TK('Tunnel') }, sizes: [5000, 50000, 200000], unit: TK('vehicles a day, by circle area'),
        hollow: { prop: 'o', value: 'K', label: TK('closed'), fill: '#b2182b' }, title: TK('Bridges by condition; circle area by daily traffic') },
      source: TK('FHWA National Bridge Inventory {date} and National Tunnel Inventory'), attribution: TK('Bridges and tunnels: FHWA') },
    airports: { id: 'lyAirports', file: 'airports.geojson', hazards: true, color: '#0072B2', icon: 'flight', label: TK('Airports and heliports'),
      sized: { cat: 'cat', r: 6, cats: ['commercial', 'airport', 'heliport'], colors: { commercial: '#0072B2', airport: '#56B4E9', heliport: '#CC79A7' },
        labels: { commercial: TK('Airport certificated for airline service'), airport: TK('Public-use airport'), heliport: TK('Heliport owned by a public body') }, title: TK('Airports and heliports by kind') },
      source: TK('FAA airport data in effect {date} (through the National Transportation Atlas Database)'), attribution: TK('Airports: FAA') },
    ferries: { id: 'lyFerries', file: 'ferry_routes.geojson', color: '#0072B2', icon: 'directions_boat', label: TK('Ferry routes and passengers'),
      line: { width: { prop: 'pax', max: 650000, lo: 2.5, hi: 8 }, dash: [8, 5], opacity: .85 },
      source: TK('BTS National Census of Ferry Operators, data year {date}'), attribution: TK('Ferry routes: BTS') },
    evcharge: { id: 'lyEvCharge', file: 'ev_stations.geojson', color: '#009E73', icon: 'ev_station', label: TK('Public EV charging stations'),
      sized: { prop: 'ports', cat: 'kind', k: 3.7, min: 3.5, cats: ['dc', 'l2'], colors: { dc: '#009E73', l2: '#56B4E9' },
        labels: { dc: TK('With DC fast charging'), l2: TK('Level 2 only') }, sizes: [1, 3, 6], unit: TK('charging ports, by circle area'),
        hollow: { prop: 'status', value: 'unavailable', label: TK('temporarily unavailable'), fill: '#56B4E9' }, title: TK('Charging stations by the fastest charging; circle area by ports') },
      source: TK('US DOE Alternative Fuels Data Center, stations updated {date} (through the National Transportation Atlas Database)'), attribution: TK('EV charging: US DOE AFDC') },
    broadband: { id: 'lyBroadband', file: 'broadband_hex.geojson', color: '#c4452c', icon: 'wifi', label: TK('Broadband gaps (FCC hexagons)'),
      area: { prop: 'below_pct', breaks: [1, 5, 15, 35], colors: ['#fbe9e7', '#f4b9a7', '#e57f63', '#c4452c', '#8a2312'] },   // the classes and colours of broadband.html's map (decision 99 (c))
      source: TK('FCC, Broadband Data Collection: fixed broadband availability as of {date}; tiers as NTIA\'s BEAD program defines them'), attribution: TK('Broadband: FCC Broadband Data Collection') },
    hexgrid: { id: 'lyHexgrid', file: 'hex_grid.geojson', color: '#3182bd', icon: 'hexagon', label: TK('Hexagon grid (1 km²)'),
      area: { pick: 0, measures: [   // one grid, several measures: the legend's picker chooses which shades the hexagons (hexgrid.py; every cell is 1 km², so a count is a density)
        { prop: 'p', breaks: [50, 200, 500, 1500], colors: ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'], labels: [TK('fewer than 50'), TK('50–199'), TK('200–499'), TK('500–1,499'), TK('1,500 or more')], title: TK('Residents per km² (2020 Census)') },
        { prop: 'h', breaks: [25, 100, 250, 800], colors: ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'], labels: [TK('fewer than 25'), TK('25–99'), TK('100–249'), TK('250–799'), TK('800 or more')], title: TK('Housing units per km² (2020 Census)') },
        { prop: 'b', breaks: [50, 150, 400, 1000], colors: ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'], labels: [TK('fewer than 50'), TK('50–149'), TK('150–399'), TK('400–999'), TK('1,000 or more')], title: TK('Buildings per km²') },
        { prop: 'bf', breaks: [1, 2.5, 5, 15], colors: ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'], labels: [TK('under 1%'), TK('1–2.4%'), TK('2.5–4.9%'), TK('5–14.9%'), TK('15% or more')], title: TK('Land under buildings (% of the hexagon)') },
        { prop: 'pf', breaks: [1, 10, 50, 90], colors: ['#f7f7f7', '#c6dbef', '#6baed6', '#2171b5', '#08306b'], labels: [TK('under 1%'), TK('1–9%'), TK('10–49%'), TK('50–89%'), TK('90% or more')], title: TK('Residents in FEMA\'s 1% flood area (%)') },
        { prop: 't', d: 1, breaks: [30, 33, 36, 40], colors: ['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15'], labels: [TK('under 30 °C'), TK('30–32.9 °C'), TK('33–35.9 °C'), TK('36–39.9 °C'), TK('40 °C or more')], title: TK('Surface temperature, summer mornings (Landsat, °C, median)') },
        { prop: 'g', d: 2, breaks: [0.3, 0.5, 0.7, 0.8], colors: ['#ffffcc', '#c2e699', '#78c679', '#31a354', '#006837'], labels: [TK('under 0.30'), TK('0.30–0.49'), TK('0.50–0.69'), TK('0.70–0.79'), TK('0.80 or more')], title: TK('Greenness, summer (NDVI, Sentinel-2, median)') },
        { prop: 's', d: 1, breaks: [5, 15, 30, 45], colors: ['#f6e8c3', '#dfc27d', '#bf812d', '#8c510a', '#543005'], labels: [TK('under 5%'), TK('5–14.9%'), TK('15–29.9%'), TK('30–44.9%'), TK('45% or more')], title: TK('Slope of the land (%, mean)') }] },
      source: TK('Observatory hexagons of 1 km², all of equal area: 2020 Census blocks, building footprints (Overture, {release}), FEMA\'s flood hazard areas, Landsat surface temperature and Sentinel-2 greenness of the summers {summers}, and USGS 3DEP elevation. Contains modified Copernicus Sentinel data.'), attribution: TK('Hexagons: 2020 Census, Overture buildings, FEMA, USGS Landsat and 3DEP, Copernicus Sentinel-2') },
    oz: { id: 'lyOz', file: 'oz_tracts.geojson', color: '#5e3c99', icon: 'work', label: TK('Opportunity Zones 2.0'),
      area: { prop: 'c', breaks: [2], colors: ['#5e3c99', '#e66101'], labels: [TK('Zone, not rural'), TK('Zone, rural')], title: TK('Opportunity Zones 2.0, by rural status') },   // c: 1 not rural, 2 rural (opportunity_zones.py); purple and orange stay apart for colour-blind readers, as on opportunity-zones.html
      source: TK('US Treasury, Qualified Opportunity Zones designated on {date} for {from} to {to}; 2020 census tracts'), attribution: TK('Opportunity Zones: US Treasury') },
    plants: { id: 'lyPlants', file: 'power_plants.geojson', hazards: true, color: '#E69F00', icon: 'bolt', label: TK('Power plants'),
      // Okabe-Ito colours (safe for colour-vision deficiency), in the groups of power_plants.py TECH; circle area in proportion to MW (r = k * sqrt(MW) px, at least min)
      sized: { prop: 'mw', cat: 'tech', k: 0.55, min: 3, cats: ['oil', 'gas', 'coal', 'solar', 'wind', 'hydro', 'battery', 'landfill'],
        colors: { oil: '#E69F00', gas: '#CC79A7', coal: '#000000', solar: '#F0E442', wind: '#56B4E9', hydro: '#009E73', battery: '#0072B2', landfill: '#D55E00' },
        labels: { oil: TK('Oil'), gas: TK('Natural gas'), coal: TK('Coal'), solar: TK('Solar'), wind: TK('Wind'), hydro: TK('Hydroelectric'), battery: TK('Batteries'), landfill: TK('Landfill gas') },
        sizes: [10, 100, 500, 1500], unit: TK('MW, by circle area'), hollow: { prop: 'status', value: 'planned', label: TK('planned or under construction'), fill: '#F0E442' },
        title: TK('Power plants by main technology; circle area by capacity (MW)') },
      source: TK('US EIA, Form EIA-860M: plants of 1 MW or more, operating or planned, in the file of {date}'), attribution: TK('Power plants: US EIA (EIA-860M)') },
    powerlines: { id: 'lyPowerLines', file: 'power_lines.geojson', color: '#4a1486', icon: 'bolt', label: TK('Transmission lines'),
      // purples that stay apart from the plants' colours; width carries the voltage too, for readers who cannot tell the shades apart (decision 104 (c): shape only, no substations)
      line: { prop: 'kv', colors: { 230: '#4a1486', 115: '#7b6bb5', 38: '#a39fc9' }, widths: { 230: 3.4, 115: 2.2, 38: 1.3 }, order: ['230', '115', '38'], dashProp: 'cable', under: 'fac-plants',
        labels: { 230: TK('230 kV'), 115: TK('115 kV'), 38: TK('38 kV (about half mapped)') }, title: TK('Transmission lines by voltage') },
      source: TK('© OpenStreetMap contributors, ODbL: power lines and cables of 230, 115 and 38 kV, data of {date}, simplified to about 100 m'), attribution: TK('Transmission lines © OpenStreetMap contributors (ODbL)') },
  };
  const TYPES = [TK('Public housing development'), TK('Scattered-site public housing'), TK('Low-Income Housing Tax Credit project'),TK('Fire or EMS station'), TK('Municipal police'), TK('State police (Puerto Rico Police Bureau)'),
    TK('Police (agency not stated)'), TK('Main library'), TK('Library or branch'), TK('Library kiosk'), TK('Bookmobile'),
    TK('Historic building'), TK('Historic structure'), TK('Historic district'), TK('Historic site'), TK('Historic object'), TK('Listed place'), TK('City hall'), TK('City hall annex'), TK('Reservoir'), TK('River gauge'), TK('Groundwater well'), TK('Rain gauge'),
    TK('Illegal dumping site'), TK('Municipal route mapped by FPR'), TK('Público route between municipios'), TK('Público route within a municipio'),
    TK('Simulated connection, no route listed'), TK('Simulated connection, público route on the 2020 list'), TK('Power plant'),
    TK('Bridge'), TK('Tunnel'), TK('Public school'), TK('Airport'), TK('Heliport'), TK('Seaplane base'), TK('Ferry route'), TK('EV charging station')];   // the types the files hold, for the language tool
  const WORDS = [TK('Small (about 13 gallons, a kitchen bag)'), TK('Medium (about 30 gallons, a yard bag)'), TK('Large (more than 50 gallons)'), TK('recyclables'), TK('organic'),
    TK('general waste'), TK('construction debris'), TK('appliances'), TK('hazardous materials')];   // the values the baseline files hold (fpr_baseline.py), for the language tool
  const HELP_TEXT = {
    fac_pubhousing: [TK('Public housing developments'), TK('Public housing developments in HUD\'s list, each at the building with the most units. HUD says to map only the developments it could place at the building or the ZIP+4 area; the others are counted in their municipio (a dataset in Explore) but not drawn. The pop-up gives the name, type, municipio and source.')],
    fac_lihtc: [TK('Tax credit housing projects'), TK('Rental housing built or rehabilitated with Low-Income Housing Tax Credits (LIHTC), as the Puerto Rico Housing Finance Authority reports it to HUD: every project placed in service since 1987, including a few no longer monitored for the credit\'s rules. HUD placed only some projects at a point; the others are counted in their municipio (a dataset in Explore) but not drawn. Projects for people who are homeless or living with HIV, and care homes for older adults, are counted, never drawn or named. The pop-up gives the name, municipio, units, low-income units, year placed in service and source, never the address.')],
    fac_fire: [TK('Fire and EMS stations'), TK('Fire stations and emergency medical service stations in the US Geological Survey\'s National Structures Dataset, which is collected for emergency planning. A station can be missing or closed. The pop-up gives the name, type, municipio and source.')],
    fac_police: [TK('Police stations'), TK('Police stations as volunteers mapped them in OpenStreetMap: state and municipal stations and a few other police facilities. Stations are likely missing; anyone can add one at openstreetmap.org. The pop-up gives the name, type, municipio and source.')],
    fac_historic: [TK('Historic places'), TK('Buildings, structures, sites, objects and historic districts listed on the National Register of Historic Places, as the National Park Service maps them. Sensitive listings, such as archaeological sites, are not public. A historic road or district can have a point in several municipios. Private homes and privately owned haciendas, and listings whose name gives a street address, are counted in their municipio (a dataset in Explore) but not drawn. The pop-up gives the name, type, municipio, listing date and source.')],
    fac_townhalls: [TK('City halls'), TK('City halls (alcaldías) as volunteers mapped them in OpenStreetMap. Some municipios have none mapped yet; anyone can add one at openstreetmap.org. The pop-up gives the name, type, municipio and source.')],
    fac_libraries: [TK('Public libraries'), TK('Libraries registered as public libraries in the federal E-Rate program (USAC). In Puerto Rico most are community technology centres and community libraries, not only municipal libraries. A library whose recorded point falls in another town is counted in its municipio but not drawn.')],
    fac_reservoirs: [TK('Reservoir levels'), TK('The water-surface elevation of every reservoir with a live US Geological Survey gauge: the 19 that the Aqueduct and Sewer Authority (AAA) reports every morning and a few irrigation and flood-control reservoirs. When you switch the layer on, your browser asks USGS for the latest readings (nothing you typed is sent). The pop-up compares the level with the same week in 2011-2025 and draws the last 120 days. A level is not a volume: sediment has filled part of several reservoirs. AAA\'s own alert levels (seguridad, observación, ajustes, control) are not shown here, because AAA does not say they may be republished; the pop-up links to AAA\'s page.')],
    fac_rivers: [TK('River flow'), TK('How much water is passing every river and stream gauge of the US Geological Survey that is reporting now, in cubic metres per second (m³/s). When you switch the layer on, your browser asks USGS for the latest readings (nothing you typed is sent). The pop-up compares the flow with the same week in 2011-2025 and draws the last 120 days. Where the gauge reports them, it also gives the water level on the gauge, the water temperature, and how far the water is from the flood reference levels USGS has surveyed there. For most gauges it also gives the flood stages the National Weather Service has set, and where the water stands against them. None of this is a flood warning: a river can leave its banks between two gauges. For warnings, follow the National Weather Service. Recent readings are provisional, and USGS can correct them. Some gauges are below a dam or a water intake, so their flow is what the operator lets through.')],
    fac_groundwater: [TK('Groundwater levels'), TK('How far below the ground the water stands in every well of the US Geological Survey that is reporting now, in metres. When you switch the layer on, your browser asks USGS for the latest readings (nothing you typed is sent). The pop-up compares the depth with the same week in 2011-2025 and draws the last 120 days. A well shows the water at one point of one aquifer: pumping nearby can lower it within hours, and the next well can read differently. The layer says nothing about the quality of the water or how much can be pumped. Recent readings are provisional, and USGS can correct them.')],
    fac_rain: [TK('Rainfall'), TK('How much rain fell at every rain gauge of the US Geological Survey that is reporting now, in millimetres (25.4 mm is one inch). When you switch the layer on, your browser asks USGS for the readings of the last 24 hours and the daily totals of the last week (nothing you typed is sent). The pop-up adds them up, compares the last 7 days with the same time of year in 2011-2025 and draws the rain of each of the last 120 days. Many of these gauges stand at a river or reservoir station. A gauge measures the rain at one spot: a shower can miss it and soak the next valley. This is not a flood warning or a forecast; for those, follow the National Weather Service. Recent readings are provisional, and a gauge can clog or stop reporting in a storm.')],
    fac_dumping: [TK('Illegal dumping sites'), TK('Illegal dumping sites that FPR staff found at or near natural and cultural assets of the Eastern Region during the 2025 baseline site visits. It is a sample, not a census: only the assets visited were checked. The pop-up gives the asset nearby, the estimated size of the waste, its kinds and whether there were signs of burning. FPR keeps this list by hand.')],
    fac_hexgrid: [TK('Hexagon grid (1 km²)'), TK('One grid of equal hexagons of 1 km² over the island, to compare places below the barrio in the same unit. Choose what shades it under the layer: residents, housing units, buildings, land under buildings, residents in FEMA\'s 1% flood area, surface temperature, greenness or slope. Residents and housing units come from the 2020 Census blocks, each block counted whole in the hexagon of its centre point, so rural hexagons look lumpy. Surface temperature is the ground\'s temperature on clear summer mornings (Landsat), not the air\'s; greenness is NDVI (Sentinel-2) for the same summers; both are the median of the hexagon\'s 60 m cells. Slope is the mean of its 10 m cells (USGS 3DEP). A hexagon mostly over the sea has no heat, greenness or slope. The hexagons are the observatory\'s own equal-area grid, not the FCC\'s H3 hexagons of the broadband layer.')],
    fac_broadband: [TK('Broadband gaps (FCC hexagons)'), TK('Where home internet of 100/20 Mbps or more is missing, in the hexagons of about 0.74 km² (H3, resolution 8) in which the FCC places each broadband serviceable location. The shade is the share of the hexagon\'s locations that cannot get 100/20 Mbps over cable, fiber, copper or licensed fixed wireless with low latency: underserved (25/3 or more) or unserved. It is what providers report they can install, not what anyone subscribes to or the speed they get. Hexagons with fewer than 10 locations are not drawn, so no home is shown alone; they are counted in the note. The pop-up gives the locations, the shares below 100/20, unserved and with fiber, and the date of the FCC release. The Broadband gaps page has the same data by barrio and municipio.')],
    fac_oz: [TK('Opportunity Zones 2.0'), TK('The 178 census tracts of Puerto Rico that the US Treasury designated on November 5, 2026 as Qualified Opportunity Zones for ten years from January 1, 2027. Investors who put capital gains into a Qualified Opportunity Fund that invests in these tracts can defer and reduce the federal tax on those gains; the benefits are larger in zones made entirely of rural area (orange). It is a tax incentive for private investment, not a grant: no public money is paid to the zone. Puerto Rico\'s government could nominate up to a quarter of the 712 tracts that were eligible as low-income communities, and nominated 178. The zones of the first round, which covered nearly all of Puerto Rico, end on December 31, 2027. The pop-up gives the tract, its municipio and main barrios, its 2020 Census residents and the poverty rate and median family income Treasury used. The Opportunity Zones page has every tract, eligible or not, and the residents in zones by municipio and barrio.')],
    fac_powerlines: [TK('Transmission lines'), TK('The high-voltage lines that carry power from the plants to the substations near the towns: 230 kV, the backbone, 115 kV and 38 kV, as volunteers mapped them in OpenStreetMap. The 230 kV network is complete and the 115 kV nearly so; the 38 kV network is about half mapped, so a gap in it is not a gap on the ground. The lines are drawn simplified to about 100 m: the map shows where the network runs, not each tower. Substations are not drawn; the note says how many are mapped. The utility asks the Energy Bureau to treat the exact location of its lines as critical infrastructure information, so the layer keeps no name, operator or circuit number. The pop-up gives the voltage and the length mapped at that voltage.')],
    fac_plants: [TK('Power plants'), TK('Every power plant of 1 MW or more in the US Energy Information Administration\'s monthly inventory (EIA-860M): the utility\'s plants, the private wind, solar and gas plants that sell to the grid, and the generators of factories, hospitals and federal sites. The area of each circle is in proportion to the plant\'s nameplate capacity in megawatts (MW), and its colour is the technology with the most capacity; a dashed circle is a plant planned or under construction. Nameplate capacity is what the generators are built to produce, not what they produce. Generators on standby and out of service are included, as EIA lists them; the pop-up says how much. Rooftop solar systems are smaller than 1 MW and are not in this inventory. The pop-up gives the capacity by technology, the batteries, the years the generators entered service and EIA\'s plant number; owners are not shown.')],
    fac_fprroutes: [TK('Municipal routes mapped by FPR'), TK('Municipal bus and trolley routes of the Eastern Region that FPR traced in ArcGIS Pro for its 2025 baseline. Only the stretches the Transit routes layer does not already show are drawn (less than half within 75 m of a route there); when a municipio publishes a timetable feed, FPR takes its routes off this layer the next time it rebuilds it. FPR traced the path, not the schedule: there are no stops or trips here, and most stretches have no route name yet. FPR keeps this layer by hand.')],
    fac_publicos: [TK('Público routes (2020 list)'), TK('The público routes (shared vans and small buses with a fixed route and no timetable) that were listed as active when the Instituto de Estadísticas de Puerto Rico published the list of the Autoridad de Carreteras y Transportación on March 19, 2020. Each line has the code and name of its route. The list has no timetable or fares and has not been updated: a route drawn here may no longer run, and newer routes are missing. Use it as a record of where públicos were listed, not as a guide to the service of today.')],
    fac_links: [TK('Simulated connections between municipios'), TK('A line for each pair of municipios with 500 or more workers travelling between them (American Community Survey 2016-2020) and no direct route in a published timetable. The line follows the fastest roads between the two town centres and is thicker where more workers travel. Orange: no route is listed at all. Purple: a público route joined the pair on the 2020 list. It is a simulation to show where a connection is missing. It is not a proposed route, a service plan or a demand forecast: públicos run without timetables, the counts are survey estimates with a margin of error, and only work trips are counted.')],
    fac_traffic: [TK('Traffic on the main roads'), TK('How many vehicles pass each stretch of the main roads on an average day (annual average daily traffic, both directions on a two-way road), as Puerto Rico reports it to the Federal Highway Administration. Wider and darker lines carry more traffic. Only freeways, arterials and major collectors with a count are drawn; local streets are left out because their figures are estimates. Each stretch gives the year of its count, which can be up to several years old, and, where reported, the share of trucks, the lanes and the speed limit. The municipio totals are in the Analysis tab (Traffic).')],
    fac_bridges: [TK('Bridges and tunnels'), TK('Every bridge of 20 feet (6.1 m) or more on a public road in the Federal Highway Administration\'s National Bridge Inventory, and the four road tunnels of its National Tunnel Inventory. The colour is the bridge\'s condition as FHWA classes it from the lowest rating of its deck, superstructure and substructure (or of the culvert): good, fair or poor. Poor does not mean unsafe: an unsafe bridge is closed, and a closed bridge is drawn hollow. The area of each circle is in proportion to the vehicles that cross it on an average day; many counts are from 2017. The pop-up also gives the year built, whether a load limit is posted, whether the foundations are scour critical (a flood could undermine them), the detour if it closed and the last inspection. The Analysis tab has the counts by municipio and year.')],
    fac_schools: [TK('Public schools'), TK('The public schools that were open in the newest school year of the National Center for Education Statistics\' directory (Common Core of Data), at the point NCES publishes, with their students and grades. The names are as NCES writes them, in capitals and without accents. The pop-up also says whether the school stands in FEMA\'s 1% flood area, in NOAA\'s 3 ft sea level rise area or on land the USGS rates highly susceptible to landslides: where the building stands, not that harm will come to it. Private schools are not in this directory.')],
    fac_airports: [TK('Airports and heliports'), TK('The airports open to the public and the heliports owned by a public body (hospitals, health centres, the water utility, the Army), as the Federal Aviation Administration lists them every 28 days. Dark blue: the three airports certificated for airline service (San Juan, Aguadilla and Ponce). Private airports, heliports and seaplane bases owned by private parties are counted in the note but not drawn or named: some are at private homes. The pop-up gives the FAA identifier, who owns and may use the facility, the elevation and whether it has a control tower.')],
    fac_ferries: [TK('Ferry routes and passengers'), TK('The ferry routes of Puerto Rico in the Bureau of Transportation Statistics\' National Census of Ferry Operators: San Juan to Cataño, and Ceiba to Vieques and to Culebra. The line is wider where more passengers travel; the count adds both directions over the census\'s data year (2024), so it shows a year of service, not today\'s timetable. The pop-up gives the passengers, vehicles, trips a year and the time of a crossing. The timetabled ferry trips of today are on the Transit routes layer.')],
    fac_evcharge: [TK('Public EV charging stations'), TK('The public electric vehicle charging stations in the US Department of Energy\'s Alternative Fuels Data Center, which networks and owners update and the Department confirms. The area of each circle is in proportion to the charging ports; green: the station has DC fast charging, blue: Level 2 only (several hours for a full charge). A hollow circle is a station reported temporarily unavailable. Private chargers at homes and workplaces are not in this list. The Taxi stands and EV charging layer shows the chargers volunteers mapped in OpenStreetMap, which can differ.')],
  };
  const meta = (s) => `<div class="meta">${esc(s)}</div>`;
  function extra(k, p) {   // what FPR recorded, for the baseline layers
    if (k === 'dumping') return meta(T('Size: {s}', { s: T(p.size) })) + meta(T('Waste: {w}', { w: (p.waste || []).map(w => T(w)).join(', ') })) + (p.burning ? meta(T('Signs of burning')) : '');
    if (k === 'fprroutes') return (p.operator ? meta(T('Operator: {o}', { o: p.operator })) : '') + meta(T('{km} km traced; {c}% of it is within 75 m of a route on the Transit routes layer.', { km: p.km < 0.05 ? '<0.1' : num(p.km, 1), c: p.covered_pct }));
    return '';
  }
  const ic = (k) => typeof icon === 'function' ? icon(LAYERS[k].icon, { size: 20, color: LAYERS[k].color }) : '';   // icons.js, on both pages

  // ── Reservoir levels (reservoirs.py): the latest reading, asked of USGS when the layer is switched on, against the usual level of the same week ──
  const LIVE = 'https://api.waterdata.usgs.gov/ogcapi/v1/collections/latest-continuous/items';
  const AAA_PAGE = 'https://www.acueductos.pr.gov/infraestructura/niveles-de-los-embalses';
  const prDate = (t) => new Date(t).toLocaleDateString('en-CA', { timeZone: 'America/Puerto_Rico' });   // YYYY-MM-DD in Puerto Rico
  const weekOf = (iso) => { const [y, m, dd] = iso.split('-').map(Number); return Math.min(Math.floor((Date.UTC(y, m - 1, dd) - Date.UTC(y, 0, 1)) / 6048e5), 52); };   // as reservoirs.py week()
  const when = (t) => new Date(t).toLocaleString(dep('text').lang() === 'es' ? 'es-PR' : 'en-US', { timeZone: 'America/Puerto_Rico', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
  // every reservoir's latest reading in one request (keyless; made by the visitor's browser), at most once every ten minutes; on failure the file's levels stand
  // GAUGE[k]: the USGS parameter the layer reads live and what turns its unit into the file's (reservoirs: metres already; rivers: cubic feet per second to m³/s; groundwater: feet below the ground to metres)
  // more: the other readings some gauges of the layer report, each asked only for the gauges that have it in the file ([parameter, the file's key, the factor])
  const GAUGE = { reservoirs: { code: '72376', k: 1 }, rivers: { code: '00060', k: 0.0283168, more: [['00065', 'stage', 0.3048], ['00010', 'temp', 1]] }, groundwater: { code: '72019', k: 0.3048 }, rain: { code: '00045', k: 25.4, sum: true } };   // sum: no single reading means much, so liveRain adds them up
  async function live(k, d) {
    const g = GAUGE[k];
    if (!g || (d.liveAt && Date.now() - d.liveAt < 6e5)) return;
    if (g.sum) return liveRain(d, g);
    const ctl = typeof AbortController === 'function' ? new AbortController() : null, timer = ctl && setTimeout(() => ctl.abort(), 10000);
    const read = async (code, feats) => {   // {gauge: its latest reading of the parameter}
      const r = await fetch(`${LIVE}?f=json&parameter_code=${code}&limit=200&skipGeometry=true&properties=monitoring_location_id,time,value&monitoring_location_id=${feats.map(f => f.properties.usgs).join(',')}`, ctl ? { signal: ctl.signal } : {});
      if (!r.ok) throw new Error('USGS ' + r.status);
      const by = {};
      for (const f of (await r.json()).features || []) if (f.properties.value != null && isFinite(+f.properties.value)) by[f.properties.monitoring_location_id] = f.properties;
      return by;
    };
    try {
      const by = await read(g.code, d.features);
      for (const f of d.features) { const x = by[f.properties.usgs]; if (x) f.properties.live = { level: +x.value * g.k, time: x.time }; }   // level: the reading, a level in metres or a flow in m³/s
      d.liveAt = Date.now(); d.liveFailed = false;
      for (const [code, key, k] of g.more || []) {   // a failure here keeps the file's reading of that parameter; the flow above stands
        const has = d.features.filter(f => f.properties[key] != null);
        if (!has.length) continue;
        try { const m = await read(code, has); for (const f of has) { const x = m[f.properties.usgs]; if (x) (f.properties.liveMore = f.properties.liveMore || {})[key] = { v: +x.value * k, time: x.time }; } } catch { /* the file's reading stands */ }
      }
    } catch { d.liveFailed = true; } finally { if (timer) clearTimeout(timer); }
  }
  // Rainfall (rain_gauges.py): the 15-minute readings of the last 24 hours, added up for each gauge (asked as CSV, a twentieth of the JSON), then the daily totals of
  // the last 8 days. p.live = { level: mm in 24 hours, time: the last reading }; p.liveDays = { 'YYYY-MM-DD': mm }. A failure of the second request keeps the file's days.
  const COLL = LIVE.replace('latest-continuous/items', '');
  async function liveRain(d, g) {
    const ctl = typeof AbortController === 'function' ? new AbortController() : null, timer = ctl && setTimeout(() => ctl.abort(), 15000);
    const by = {}; for (const f of d.features) by[f.properties.usgs] = f.properties;
    const ask = async (coll, more) => { const r = await fetch(`${COLL}${coll}/items?parameter_code=${g.code}&skipGeometry=true&properties=monitoring_location_id,time,value&monitoring_location_id=${Object.keys(by).join(',')}${more}`, ctl ? { signal: ctl.signal } : {}); if (!r.ok) throw new Error('USGS ' + r.status); return r; };
    const iso = (t) => new Date(t).toISOString().slice(0, 19) + 'Z', now = Date.now();
    try {
      const rows = (await (await ask('continuous', `&f=csv&limit=10000&datetime=${iso(now - 864e5)}/${iso(now)}`)).text()).trim().split(/\r?\n/);
      const head = rows[0].split(','), ci = head.indexOf('monitoring_location_id'), ti = head.indexOf('time'), vi = head.indexOf('value');
      if (ci < 0 || ti < 0 || vi < 0) throw new Error('USGS: not the columns expected');
      const sum = {};
      for (const row of rows.slice(1)) {
        const c = row.split(','), v = +c[vi];
        if (!by[c[ci]] || c[vi] === '' || !isFinite(v)) continue;
        const s = sum[c[ci]] || (sum[c[ci]] = { level: 0, time: '', n: 0 }), t = c[ti].replace(' ', 'T');
        s.level += v * g.k; s.n++; if (t > s.time) s.time = t;
      }
      for (const [id, s] of Object.entries(sum)) by[id].live = s;
      d.liveAt = Date.now(); d.liveFailed = false;
      try {
        const j = await (await ask('daily', `&f=json&statistic_id=00006&limit=1000&datetime=${prDate(now - 8 * 864e5)}/..`)).json();
        for (const f of j.features || []) { const x = f.properties, p = by[x.monitoring_location_id]; if (p && x.value != null && isFinite(+x.value)) (p.liveDays = p.liveDays || {})[String(x.time).slice(0, 10)] = +x.value * g.k; }
      } catch { /* the file's days stand */ }
    } catch { d.liveFailed = true; } finally { if (timer) clearTimeout(timer); }
  }
  // three bands, at the 10th and 90th percentiles: a finer cut flagged centimetres where a reservoir is usually kept full (its middle half can be 10 cm wide)
  const usual = (lvl, q) => q.p10 == null ? null : lvl < q.p10 ? TK('Lower than usual for this time of year') : lvl <= q.p90 ? TK('Usual for this time of year') : TK('Higher than usual for this time of year');
  // the last 120 days (line) over the usual range of each day's week (10th-90th percentile, and 25th-75th darker), with the live reading as a dot
  function spark(p, now, o) {
    const tr = o && o.log ? (v) => Math.log10(Math.max(v, 0.001)) : (v) => v;   // rivers: a storm's flow is hundreds of times a dry week's, so the scale is logarithmic
    const W = 260, H = 64, n = p.recent.length, start = Date.parse(p.recent_start + 'T12:00:00Z');
    const wk = (i) => weekOf(new Date(start + i * 864e5).toISOString().slice(0, 10));
    const pts = p.recent.map((v, i) => [i, v]).filter(([, v]) => v != null);
    const days = now ? Math.round((Date.parse(prDate(now.time) + 'T12:00:00Z') - start) / 864e5) : -1;
    const ys = [...pts.map(x => tr(x[1])), ...(now ? [tr(now.level)] : [])];
    for (let i = 0; i < n; i++) for (const q of ['p10', 'p90']) if (p[q][wk(i)] != null) ys.push(tr(p[q][wk(i)]));
    if (ys.length < 2) return '';
    const lo = Math.min(...ys), hi = Math.max(...ys), pad = (hi - lo) * 0.08 || 0.5, span = Math.max(n - 1, days);
    const x = (i) => (i / span * (W - 4) + 2).toFixed(1), y = (v0) => { const f = (tr(v0) - lo + pad) / (hi - lo + 2 * pad) * (H - 4); return (o && o.flip ? 2 + f : H - 2 - f).toFixed(1); };   // flip: a depth, drawn downwards
    const band = (a, b) => { const up = [], dn = []; for (let i = 0; i < n; i++) { const q = wk(i); if (p[a][q] != null) { up.push(`${x(i)},${y(p[b][q])}`); dn.unshift(`${x(i)},${y(p[a][q])}`); } } return up.length ? `<polygon points="${up.concat(dn).join(' ')}"/>` : ''; };
    const line = pts.map(([i, v], j) => `${j ? 'L' : 'M'}${x(i)},${y(v)}`).join('');
    return `<svg class="res-spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T(o && o.label || TK('Level over the last 120 days, against the usual range of each week')))}"><g fill="#BBDEFB">${band('p10', 'p90')}</g><g fill="#90CAF9">${band('p25', 'p75')}</g><path d="${line}" fill="none" stroke="#0D47A1" stroke-width="1.6"/>${now && days >= 0 ? `<circle cx="${x(days)}" cy="${y(now.level)}" r="3" fill="#0D47A1"/>` : ''}</svg>`;
  }
  function resPopup(p0, d) {
    const p = (d.features.find(f => f.properties.usgs === p0.usgs) || {}).properties || p0;   // the file's feature: MapLibre hands the 3D view its arrays as text
    const now = p.live || { level: p.level, time: p.level_time }, day = prDate(now.time), w = weekOf(day), q = { p10: p.p10[w], p90: p.p90[w] };
    const back = Math.round((Date.parse(day + 'T12:00:00Z') - Date.parse(p.recent_start + 'T12:00:00Z')) / 864e5) - 7, then = back >= 0 && back < p.recent.length ? p.recent[back] : null;
    const st = usual(now.level, q), m = (v) => num(v, 2);
    return `<div class="pop"><h4>${ic('reservoirs')}${esc(p.name)}</h4><div class="meta">${esc(T('Reservoir'))} · ${esc(p.municipio)}</div>`
      + `<div><b>${esc(T('{v} m above mean sea level', { v: m(now.level) }))}</b></div><div class="meta">${esc(p.live ? T('Live reading, {t}', { t: when(now.time) }) : T('Reading of {t} (the live reading could not be loaded)', { t: when(now.time) }))}</div>`
      + (then != null ? `<div class="meta">${esc(T('{c} m in 7 days', { c: (now.level - then >= 0 ? '+' : '−') + m(Math.abs(now.level - then)) }))}</div>` : '')
      + (st ? `<div><b>${esc(T(st))}</b></div><div class="meta">${esc(T('In about 8 of every 10 years from 2011 to 2025, the level this week was between {a} and {b} m.', { a: m(q.p10), b: m(q.p90) }))}</div>` : `<div class="meta">${esc(T('No usual range for this week: fewer than 8 years of readings.'))}</div>`)
      + spark(p, p.live || null) + `<div class="meta">${esc(T('Line: the daily level. Shading: the usual range of each week (darker: the middle half).'))}</div>`
      + (p.aaa ? `<div class="meta"><a href="${AAA_PAGE}" target="_blank" rel="noopener">${esc(T('AAA\'s alert level for this reservoir'))}</a></div>` : '')
      + `<div class="src">${esc(T(LAYERS.reservoirs.source, { date: d.vintage || '—', years: (d.notes || {}).usual_years || '—' }))}</div></div>`;
  }
  // ── River flow (river_gauges.py): the same comparison for a flow, which has no flood level here ──
  const NWS_PAGE = 'https://www.weather.gov/sju/', USGS_SITE = 'https://waterdata.usgs.gov/monitoring-location/';
  const fl = (v) => num(v, v < 1 ? 2 : v < 100 ? 1 : 0);   // m³/s: a small stream needs its hundredths, a river in flood does not
  // A gauge's other readings (river_gauges.py): the live one when it loaded, otherwise the file's
  const moreOf = (p, key) => (p.liveMore && p.liveMore[key]) || (p[key] != null ? { v: p[key], time: p[key + '_time'] } : null);
  const REF = { bank: TK('Top of the riverbank'), chord: TK('Lowest beam of the bridge'), deck: TK('Deck of the bridge (the road)'), hwm: TK('High-water mark of a past flood'), other: TK('Reference level') };
  /** The flood reference levels of a gauge against the water's level now (both gauge heights, in metres): [{kind, label, level, gap}], lowest first; gap > 0: the level is above the water. */
  function floodRefs(p) {
    const s = moreOf(p, 'stage');
    return s && Array.isArray(p.refs) ? p.refs.map(r => ({ kind: REF[r.kind] ? r.kind : 'other', label: r.label || '', level: r.level, gap: Math.round((r.level - s.v) * 100) / 100 })) : [];
  }
  const NWS_STAGE = { action: TK('Action stage'), minor: TK('Minor flood stage'), moderate: TK('Moderate flood stage'), major: TK('Major flood stage') };
  const NWS_NOW = { none: TK('Now: below the action stage'), action: TK('Now: at or above the action stage'), minor: TK('Now: at or above the minor flood stage'), moderate: TK('Now: at or above the moderate flood stage'), major: TK('Now: at or above the major flood stage') };
  const NWS_GAUGE = 'https://water.noaa.gov/gauges/';
  /** The National Weather Service's flood stages of a gauge against the water's level now (gauge heights, in metres): { now: the highest stage reached or 'none',
      stages: [{kind, level, gap}] lowest first; gap > 0: the stage is above the water }; null when the gauge has none or no level. */
  function nwsStages(p) {
    const s = moreOf(p, 'stage');
    if (!s || !p.nws) return null;
    const stages = Object.keys(NWS_STAGE).filter(k => p.nws[k] != null).map(k => ({ kind: k, level: p.nws[k], gap: Math.round((p.nws[k] - s.v) * 100) / 100 }));
    return stages.length ? { now: stages.filter(x => x.gap <= 0).map(x => x.kind).pop() || 'none', stages } : null;
  }
  function nwsHtml(p) {
    const n = nwsStages(p);
    if (!n) return '';
    return `<div><b>${esc(T('Flood stages of the National Weather Service at this gauge'))}</b></div><div><b>${esc(T(NWS_NOW[n.now]))}</b></div>`
      + n.stages.map(r => `<div class="meta">${esc(T('{name} ({m} m on the gauge, {ft} ft)', { name: T(NWS_STAGE[r.kind]), m: num(r.level, 2), ft: num(r.level / 0.3048, 1) }))}: ${esc(r.gap > 0 ? T('{v} m above the water now', { v: num(r.gap, 2) }) : T('the water is at or above it, by {v} m', { v: num(-r.gap, 2) }))}</div>`).join('')
      + `<div class="meta">${esc(T('The stages are the National Weather Service\'s; the comparison with the water now is the observatory\'s, not an official warning.'))} <a href="${NWS_GAUGE}${encodeURIComponent(p.nws.lid)}" target="_blank" rel="noopener">${esc(T('This gauge at the National Weather Service: forecast and warnings'))}</a></div>`;
  }
  function moreHtml(p) {
    const s = moreOf(p, 'stage'), t = moreOf(p, 'temp'), refs = floodRefs(p);
    return (s ? `<div class="meta">${esc(T('Water level on the gauge: {v} m, {t}', { v: num(s.v, 2), t: when(s.time) }))}</div>` : '')
      + nwsHtml(p)
      + (refs.length ? `<div><b>${esc(T('Flood reference levels at this gauge'))}</b></div>` + refs.map(r => `<div class="meta">${esc(T(REF[r.kind]))}${r.label ? ` <span translate="no">(${esc(r.label)})</span>` : ''}: ${esc(r.gap > 0 ? T('{v} m above the water now', { v: num(r.gap, 2) }) : T('the water is at or above it, by {v} m', { v: num(-r.gap, 2) }))}</div>`).join('')
        + `<div class="meta">${esc(T('Levels surveyed by USGS. They do not replace a warning from the National Weather Service.'))}</div>` : '')
      + (t ? `<div class="meta">${esc(T('Water temperature: {v} °C, {t}', { v: num(t.v, 1), t: when(t.time) }))}</div>` : '');
  }
  function rivPopup(p0, d) {
    const p = (d.features.find(f => f.properties.usgs === p0.usgs) || {}).properties || p0;
    const now = p.live || { level: p.flow, time: p.flow_time }, day = prDate(now.time), w = weekOf(day), q = { p10: p.p10[w], p90: p.p90[w] };
    const back = Math.round((Date.parse(day + 'T12:00:00Z') - Date.parse(p.recent_start + 'T12:00:00Z')) / 864e5) - 7, then = back >= 0 && back < p.recent.length ? p.recent[back] : null;
    const st = usual(now.level, q);
    return `<div class="pop"><h4>${ic('rivers')}${esc(p.name)}</h4><div class="meta">${esc(T('River gauge'))} · ${esc(p.municipio)}</div>`
      + `<div><b>${esc(T('{v} m³/s (cubic metres of water per second)', { v: fl(now.level) }))}</b></div><div class="meta">${esc(p.live ? T('Live reading, {t}', { t: when(now.time) }) : T('Reading of {t} (the live reading could not be loaded)', { t: when(now.time) }))}</div>`
      + (then != null ? `<div class="meta">${esc(T('{v} m³/s seven days ago (the mean of that day)', { v: fl(then) }))}</div>` : '')
      + (st ? `<div><b>${esc(T(st))}</b></div><div class="meta">${esc(T('In about 8 of every 10 years from 2011 to 2025, the flow this week was between {a} and {b} m³/s.', { a: fl(q.p10), b: fl(q.p90) }))}</div>` : `<div class="meta">${esc(T('No usual range for this week: fewer than 8 years of readings.'))}</div>`)
      + spark(p, p.live || null, { log: true, label: TK('Flow over the last 120 days, against the usual range of each week') })
      + `<div class="meta">${esc(T('Line: the daily flow. Shading: the usual range of each week (darker: the middle half). The scale is stretched at the low end, so that low flows show.'))}</div>`
      + moreHtml(p)
      + `<div class="meta">${esc(T('A flow higher than usual is not a flood warning.'))} <a href="${NWS_PAGE}" target="_blank" rel="noopener">${esc(T('National Weather Service, San Juan'))}</a></div>`
      + `<div class="meta">${esc(T('USGS gauge:'))} <a href="${USGS_SITE}${encodeURIComponent(p.usgs)}/" target="_blank" rel="noopener" translate="no">${esc(p.station)}</a></div>`
      + `<div class="src">${esc(T(LAYERS.rivers.source, { date: d.vintage || '—', years: (d.notes || {}).usual_years || '—' }))}</div></div>`;
  }
  // ── Groundwater levels (groundwater.py): a depth below the ground, so a larger number is lower water ──
  function gwPopup(p0, d) {
    const p = (d.features.find(f => f.properties.usgs === p0.usgs) || {}).properties || p0;
    const now = p.live || { level: p.depth, time: p.depth_time }, day = prDate(now.time), w = weekOf(day), q = { p10: p.p10[w], p90: p.p90[w] }, m = (v) => num(v, 2);
    const back = Math.round((Date.parse(day + 'T12:00:00Z') - Date.parse(p.recent_start + 'T12:00:00Z')) / 864e5) - 7, then = back >= 0 && back < p.recent.length ? p.recent[back] : null;
    const st = q.p10 == null ? null : now.level > q.p90 ? TK('Water lower than usual for this time of year') : now.level >= q.p10 ? TK('Usual for this time of year') : TK('Water higher than usual for this time of year');
    const ch = then == null ? null : then - now.level;   // above zero: the water rose
    return `<div class="pop"><h4>${ic('groundwater')}${esc(p.name)}</h4><div class="meta">${esc(T('Groundwater well'))} · ${esc(p.municipio)}</div>`
      + `<div><b>${esc(T('Water {v} m below the ground', { v: m(now.level) }))}</b></div><div class="meta">${esc(p.live ? T('Live reading, {t}', { t: when(now.time) }) : T('Reading of {t} (the live reading could not be loaded)', { t: when(now.time) }))}</div>`
      + (ch != null ? `<div class="meta">${esc(Math.abs(ch) < 0.005 ? T('The water is where it was 7 days ago') : T(ch > 0 ? TK('The water rose {c} m in 7 days') : TK('The water fell {c} m in 7 days'), { c: m(Math.abs(ch)) }))}</div>` : '')
      + (st ? `<div><b>${esc(T(st))}</b></div><div class="meta">${esc(T('In about 8 of every 10 years from 2011 to 2025, the water this week was between {a} and {b} m below the ground.', { a: m(q.p10), b: m(q.p90) }))}</div>` : `<div class="meta">${esc(T('No usual range for this week: fewer than 8 years of readings.'))}</div>`)
      + spark(p, p.live || null, { flip: true, label: TK('Depth to water over the last 120 days, against the usual range of each week') })
      + `<div class="meta">${esc(T('Line: the daily depth to water (higher on the chart: nearer the ground). Shading: the usual range of each week (darker: the middle half).'))}</div>`
      + (p.well_depth ? `<div class="meta">${esc(T('The well is {v} m deep.', { v: num(p.well_depth, 1) }))}</div>` : '')
      + `<div class="meta">${esc(T('A well shows the water at one point of an aquifer. Pumping nearby can lower it within hours.'))}</div>`
      + `<div class="meta">${esc(T('USGS well:'))} <a href="${USGS_SITE}${encodeURIComponent(p.usgs)}/" target="_blank" rel="noopener" translate="no">${esc(p.station)}</a></div>`
      + `<div class="src">${esc(T(LAYERS.groundwater.source, { date: d.vintage || '—', years: (d.notes || {}).usual_years || '—' }))}</div></div>`;
  }
  // ── Rainfall (rain_gauges.py): totals, not a level: the last 24 hours, the last 7 whole days against the usual rain of a week, and a bar a day ──
  const dayBack = (iso, n) => new Date(Date.parse(iso + 'T12:00:00Z') - n * 864e5).toISOString().slice(0, 10);
  /** The rain of the last 7 whole days of a gauge: { mm, end, live }, from USGS's daily totals when they loaded, otherwise from the file; null when a day is missing.
      The last whole day is yesterday in Puerto Rico, or the day before while USGS has not yet posted yesterday's total. */
  function rainWeek(p, today) {
    const fileDay = (iso) => { const i = Math.round((Date.parse(iso + 'T12:00:00Z') - Date.parse(p.recent_start + 'T12:00:00Z')) / 864e5); return i >= 0 && i < p.recent.length ? p.recent[i] : null; };
    const total = (get, end) => { let mm = 0; for (let i = 0; i < 7; i++) { const v = get(dayBack(end, i)); if (v == null) return null; mm += v; } return mm; };
    if (p.liveDays) for (const end of [dayBack(today, 1), dayBack(today, 2)]) { const mm = total(day => p.liveDays[day] != null ? p.liveDays[day] : fileDay(day), end); if (mm != null) return { mm, end, live: true }; }
    const last = dayBack(p.recent_start, -(p.recent.length - 1));
    for (const end of [last, dayBack(last, 1), dayBack(last, 2)]) { const mm = total(fileDay, end); if (mm != null) return { mm, end, live: false }; }
    return null;
  }
  function rainBars(p) {   // one bar a day; the scale starts at 10 mm, so that a dry spell does not draw a drizzle as a storm
    const W = 260, H = 64, n = p.recent.length, top = Math.max(10, ...p.recent.map(v => v || 0)), bw = (W - 4) / n;
    const bars = p.recent.map((v, i) => v > 0 ? `<rect x="${(2 + i * bw).toFixed(1)}" y="${(H - 2 - v / top * (H - 4)).toFixed(1)}" width="${Math.max(bw - 0.4, 0.8).toFixed(1)}" height="${(v / top * (H - 4)).toFixed(1)}"/>` : '').join('');
    return `<svg class="res-spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('Rain of each day over the last 120 days'))}"><line x1="2" y1="${H - 2}" x2="${W - 2}" y2="${H - 2}" stroke="#90CAF9"/><g fill="#0D47A1">${bars}</g></svg>`
      + `<div class="meta">${esc(T('Bars: the rain of each day in the 120 days to {date}. The tallest bar is {v} mm.', { date: dayBack(p.recent_start, -(n - 1)), v: num(Math.max(0, ...p.recent.map(v => v || 0)), 1) }))}</div>`;
  }
  function rainPopup(p0, d) {
    const p = (d.features.find(f => f.properties.usgs === p0.usgs) || {}).properties || p0, mm = (v) => num(v, 1);
    const wk = rainWeek(p, prDate(Date.now())), w = wk ? weekOf(wk.end) : 0, q = { p10: p.p10[w], p90: p.p90[w] };
    const st = !wk || q.p10 == null ? null : wk.mm < q.p10 ? TK('Drier than usual for this time of year') : wk.mm <= q.p90 ? TK('Usual for this time of year') : TK('Wetter than usual for this time of year');
    return `<div class="pop"><h4>${ic('rain')}${esc(p.name)}</h4><div class="meta">${esc(T('Rain gauge'))} · ${esc(p.municipio)}</div>`
      + (p.live ? `<div><b>${esc(T('{v} mm of rain in the last 24 hours', { v: mm(p.live.level) }))}</b></div><div class="meta">${esc(T('Live readings, the last at {t}', { t: when(p.live.time) }))}</div>` : `<div class="meta">${esc(T('The readings of the last 24 hours could not be loaded.'))}</div>`)
      + (wk ? `<div><b>${esc(T('{v} mm in the 7 days to {date}', { v: mm(wk.mm), date: wk.end }))}</b></div>` : `<div class="meta">${esc(T('No total for the last 7 days: a day is missing.'))}</div>`)
      + (st ? `<div><b>${esc(T(st))}</b></div><div class="meta">${esc(T('In about 8 of every 10 years from 2011 to 2025, a week at this time of year had between {a} and {b} mm of rain.', { a: mm(q.p10), b: mm(q.p90) }))}</div>` : wk ? `<div class="meta">${esc(T('No usual range for this week: fewer than 8 years of readings.'))}</div>` : '')
      + rainBars(p)
      + `<div class="meta">${esc(T('A gauge measures the rain at one spot. This is not a flood warning or a forecast.'))} <a href="${NWS_PAGE}" target="_blank" rel="noopener">${esc(T('National Weather Service, San Juan'))}</a></div>`
      + `<div class="meta">${esc(T('USGS gauge:'))} <a href="${USGS_SITE}${encodeURIComponent(p.usgs)}/" target="_blank" rel="noopener" translate="no">${esc(p.station)}</a></div>`
      + `<div class="src">${esc(T(LAYERS.rain.source, { date: d.vintage || '—', years: (d.notes || {}).usual_years || '—' }))}</div></div>`;
  }

  // ── Broadband gaps (broadband.py): an H3 hexagon's locations and shares; no address, no provider ──
  /** The measure an area layer is shaded by: its one `area`, or the one its picker chose (area.measures[area.pick], the hexagon grid). */
  function areaSpec(k) { const a = LAYERS[k].area; return a && a.measures ? a.measures[a.pick || 0] : a; }
  function areaClass(k, v) { const a = areaSpec(k); if (!a || v == null || !isFinite(+v)) return -1; let i = 0; while (i < a.breaks.length && +v >= a.breaks[i]) i++; return i; }
  // the look of a line layer: one colour and width, or by class and by a number (line: { prop, colors, labels, width: { prop, max, lo, hi }, dash, weight, opacity });
  // widths: a width for each class (the transmission lines, by voltage); dashProp: the features with that property true are dashed (a cable); under: drawn under that layer
  function lineStyle(k, p) {
    const L0 = LAYERS[k], l = L0.line === true ? {} : L0.line || {}, w = l.width;
    return { color: l.colors && l.colors[p[l.prop]] || L0.color, weight: w ? w.lo + (w.hi - w.lo) * Math.sqrt(Math.min(1, Math.max(0, +p[w.prop] || 0) / w.max)) : l.widths && l.widths[p[l.prop]] || l.weight || 3.5,
      opacity: l.opacity || .9, dash: l.dashProp ? (p[l.dashProp] ? [5, 4] : null) : l.dash || null };
  }
  function legendHtml(k, d) {
    if (LAYERS[k].sized) return sizedLegend(k, d);
    const l = LAYERS[k].line;
    if (l && l.colors) return `<div class="fac-legend" role="img" aria-label="${esc(T(l.title))}" style="display:flex;flex-wrap:wrap;gap:2px 10px;margin-top:4px">${(l.order || Object.keys(l.colors)).map(c => `<span style="white-space:nowrap"><i style="display:inline-block;width:16px;height:0;margin-right:4px;vertical-align:3px;border-top:${l.widths ? l.widths[c] : 3}px ${l.dash ? 'dashed' : 'solid'} ${l.colors[c]}"></i>${esc(T(l.labels[c]))}</span>`).join('')}</div>`;
    const a = areaSpec(k); if (!a) return '';
    const ms = LAYERS[k].area.measures, pick = ms ? `<label style="display:block;margin-top:4px">${esc(T('Shade by'))} <select data-fac-measure="${k}">${ms.map((m, i) => `<option value="${i}"${i === (LAYERS[k].area.pick || 0) ? ' selected' : ''}>${esc(T(m.title))}</option>`).join('')}</select></label>` : '';
    const b = a.breaks, lab = a.labels ? a.labels.map(x => T(x)) : [T('below {a}%', { a: num(b[0]) }), ...b.slice(1).map((x, i) => T('{a}–{b}%', { a: num(b[i]), b: num(x) })), T('{a}% or more', { a: num(b[b.length - 1]) })];
    return pick + `<div class="fac-legend" role="img" aria-label="${esc(a.title ? T(a.title) : T('Share of locations below 100/20 Mbps'))}" style="display:flex;flex-wrap:wrap;gap:2px 10px;margin-top:4px">${a.colors.map((c, i) => `<span style="white-space:nowrap"><i style="display:inline-block;width:11px;height:11px;margin-right:4px;vertical-align:-1px;border:1px solid #0002;background:${c}"></i>${esc(lab[i])}</span>`).join('')}</div>`;   // inline styles: the pages share twin.css
  }
  function sizedLegend(k, d) {   // the categories the file holds, in the layer's order; circles for a few sizes; the dashed circle of a planned plant
    const s = LAYERS[k].sized, have = new Set(((d || {}).features || []).map(f => f.properties[s.cat])), cats = s.cats.filter(c => !d || have.has(c));
    const sw = cats.map(c => `<span style="white-space:nowrap"><i style="display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:4px;vertical-align:-1px;border:1px solid #424242;background:${s.colors[c]}"></i>${esc(T(s.labels[c]))}</span>`).join('');
    const sizes = s.sizes || [], big = s.k * Math.sqrt(sizes[sizes.length - 1] || 0), H = Math.ceil(2 * big + 4);
    let x = 2; const circ = sizes.map(v => { const r = Math.max(s.min, s.k * Math.sqrt(v)), cx = x + r; x += 2 * r + 34; return `<circle cx="${cx.toFixed(1)}" cy="${(H - 2 - r).toFixed(1)}" r="${r.toFixed(1)}" fill="none" stroke="#616161"/><text x="${(cx + r + 3).toFixed(1)}" y="${H - 3}" font-size="10" fill="currentColor">${esc(num(v))}</text>`; }).join('');
    const h = s.hollow, pr = 6, dash = h ? `<svg width="${2 * pr + 4}" height="${2 * pr + 4}" style="vertical-align:middle" aria-hidden="true"><circle cx="${pr + 2}" cy="${pr + 2}" r="${pr}" fill="${h.fill}" fill-opacity=".25" stroke="#616161" stroke-width="1.5" stroke-dasharray="3 2"/></svg>` : '';
    const foot = [s.unit ? esc(T(s.unit)) : '', h ? `${dash} ${esc(T(h.label))}` : ''].filter(Boolean).join(' · ');
    return `<div class="fac-legend" role="img" aria-label="${esc(T(s.title))}" style="margin-top:4px"><div style="display:flex;flex-wrap:wrap;gap:2px 10px">${sw}</div>`
      + (sizes.length ? `<svg width="${Math.ceil(x)}" height="${H}" style="display:block;margin-top:3px;max-width:100%" aria-hidden="true">${circ}</svg>` : '') + (foot ? `<div class="meta">${foot}</div>` : '') + '</div>';   // inline styles: the pages share twin.css
  }
  function hexPopup(p, d) {   // one hexagon of the grid: every measure it holds; a count per hexagon is a count per km²
    const row = (label, v, d1) => `<div class="meta">${esc(T(label))}: <b>${v == null ? '—' : esc(num(v, d1 || 0))}</b></div>`;
    return `<div class="pop"><h4>${esc(T('Hexagon of 1 km²'))}</h4>` + row('Residents (2020 Census)', p.p) + row('Housing units (2020 Census)', p.h) + row('Buildings', p.b)
      + row('Land under buildings (%)', p.bf, 1) + row('Residents in FEMA\'s 1% flood area (%)', p.pf, 1)
      + row('Surface temperature, summer mornings (Landsat, °C, median)', p.t, 1) + row('Greenness, summer (NDVI, Sentinel-2, median)', p.g, 2) + row('Slope of the land (%, mean)', p.s, 1)
      + `<div class="src">${esc(T(LAYERS.hexgrid.source, { release: (d.notes || {}).buildings_release || '—', summers: ((d.notes || {}).surfaces || {}).summers || '—' }))}</div></div>`;
  }
  function bbPopup(p, d) {
    const pct = (v) => T('{v}%', { v: num(v, 1) });
    return `<div class="pop"><h4>${ic('broadband')}${esc(T('Broadband in this hexagon'))}</h4><div class="meta">${esc(T('{n} broadband serviceable locations', { n: num(p.n) }))}</div>`
      + `<div><b>${esc(T('{v} cannot get 100/20 Mbps', { v: pct(p.below_pct) }))}</b></div>`
      + `<div class="meta">${esc(T('Unserved (below 25/3 Mbps): {v}', { v: pct(p.unserved_pct) }))}</div><div class="meta">${esc(T('Fiber available: {v}', { v: pct(p.fiber_pct) }))}</div>`
      + `<div class="meta"><a href="broadband.html">${esc(T('Broadband gaps page'))}</a></div>`
      + `<div class="src">${esc(T(LAYERS.broadband.source, { date: (d.notes || {}).as_of || '—' }))}</div></div>`;
  }
  // ── Opportunity Zones 2.0 (opportunity_zones.py): a designated census tract, rural or not, with what Treasury used to make it eligible ──
  const ozDay = (iso) => !iso ? '—' : new Date(iso + 'T12:00:00Z').toLocaleDateString(dep('text').lang() === 'es' ? 'es-PR' : 'en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  const ozKind = (p) => T(p.c === 2 ? TK('Opportunity Zone 2.0, rural') : TK('Opportunity Zone 2.0, not rural'));
  function ozPopup(p, d) {
    const n = d.notes || {}, pct = (v) => v == null ? '—' : T('{v}%', { v: num(v, 1) });
    return `<div class="pop"><h4>${ic('oz')}${esc(ozKind(p))}</h4><div class="meta">${esc(T('Census tract {t}', { t: p.t }))} · ${esc(p.m)}</div>`
      + (p.b ? `<div class="meta">${esc(T(p.nb > 3 ? TK('Barrios: {b} and {n} more') : TK('Barrios: {b}'), { b: p.b, n: num(p.nb - 3) }))}</div>` : '')
      + `<div><b>${esc(T('{n} residents (2020 Census)', { n: num(p.p) }))}</b></div>`
      + `<div class="meta">${esc(T('Poverty rate: {v}', { v: pct(p.pv) }))}</div><div class="meta">${esc(T('Median family income: {v} of the area\'s', { v: pct(p.mr) }))}</div>`
      + `<div class="meta">${esc(T('In effect from {from} to {to}', { from: ozDay(n.starts), to: ozDay(n.ends) }))}</div>`
      + `<div class="meta"><a href="opportunity-zones.html">${esc(T('Opportunity Zones page'))}</a></div>`
      + `<div class="src">${esc(T(LAYERS.oz.source, { date: ozDay(n.designated_on), from: (n.starts || '').slice(0, 4), to: (n.ends || '').slice(0, 4) }))} · ${esc(T('American Community Survey {y}', { y: n.acs || '—' }))}</div></div>`;
  }
  // ── Power plants (power_plants.py): circle area in proportion to capacity, colour by main technology; owners are never in the file ──
  const plantMw = (p) => p.mw || p.bat_mw || Object.values(p.plan || {}).reduce((a, b) => a + b, 0);   // a battery-only plant by its batteries, a planned one by what is planned
  // a sized layer's circle: the radius from the number (a plant's MW as plantMw counts it) or one radius (r), the colour from the category; planned: drawn hollow (s.hollow)
  function sizedStyle(k, p) { const s = LAYERS[k].sized, h = s.hollow; return { r: s.r || Math.max(s.min, s.k * Math.sqrt(k === 'plants' ? plantMw(p) : Math.max(0, +p[s.prop] || 0))), color: s.colors[p[s.cat]] || '#9e9e9e', planned: !!h && p[h.prop] === h.value }; }
  const techName = (c) => T(LAYERS.plants.sized.labels[c] || c);
  const monthYear = (ym) => !ym ? '—' : new Date(ym + '-15T12:00:00Z').toLocaleDateString(dep('text').lang() === 'es' ? 'es-PR' : 'en-US', { year: 'numeric', month: 'long', timeZone: 'UTC' });
  const EIA_PLANT = 'https://www.eia.gov/electricity/data/browser/#/plant/';
  function plantPopup(p0, d) {
    const p = (d.features.find(f => f.properties.eia === p0.eia) || {}).properties || p0;   // the file's own feature: MapLibre hands the 3D click its nested values (by, plan) as text
    const s = LAYERS.plants.sized, mw = (v) => num(v, 1), dot = (c) => `<i style="display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;background:${s.colors[c] || '#9e9e9e'};border:1px solid #424242"></i>`;
    const by = Object.entries(p.by || {}).map(([c, v]) => `<div class="meta">${dot(c)}${esc(c === 'battery' ? T('{t}: {v} MW, {e} MWh', { t: techName(c), v: mw(v), e: mw(p.bat_mwh || 0) }) : T('{t}: {v} MW', { t: techName(c), v: mw(v) }))}</div>`).join('');
    const plan = Object.entries(p.plan || {}).map(([c, v]) => T('{t}: {v} MW', { t: techName(c), v: mw(v) })).join('; ');
    const yrs = p.y0 == null ? '' : p.units === 1 ? T('1 generator, in service since {y}', { y: p.y0 }) : p.y0 === p.y1 ? T('{n} generators, in service since {y}', { n: num(p.units), y: p.y0 }) : T('{n} generators, entered service from {a} to {b}', { n: num(p.units), a: p.y0, b: p.y1 });
    return `<div class="pop"><h4>${ic('plants')}${esc(p.name)}</h4><div class="meta">${esc(T(p.status === 'planned' ? TK('Planned power plant') : TK('Power plant')))} · ${esc(p.municipio)}</div>`
      + (p.mw ? `<div><b>${esc(T('{v} MW of generating capacity (nameplate)', { v: mw(p.mw) }))}</b></div>` : '')
      + by
      + (p.sb ? `<div class="meta">${esc(T('On standby: {v} MW', { v: mw(p.sb) }))}</div>` : '') + (p.out ? `<div class="meta">${esc(T('Out of service: {v} MW', { v: mw(p.out) }))}</div>` : '')
      + (yrs ? `<div class="meta">${esc(yrs)}</div>` : '')
      + (plan ? `<div class="meta"><b>${esc(T('Planned or under construction: {list}', { list: plan }))}</b>${p.plan_ym ? ' ' + esc(T('(expected {when})', { when: monthYear(p.plan_ym) })) : ''}</div>` : '')
      + `<div class="meta">${esc(T('EIA plant'))} <a href="${EIA_PLANT}${encodeURIComponent(p.eia)}" target="_blank" rel="noopener" translate="no">${esc(p.eia)}</a></div>`
      + `<div class="src">${esc(T(LAYERS.plants.source, { date: monthYear(d.vintage) }))}</div></div>`;
  }
  /** The 2D map's hover text of a feature that has no name (an area of an area layer, a stretch of road) or of a point of a sized layer; null for the others. */
  function tip(k, p) {
    if (k === 'plants') return `${p.name} · ${T('{v} MW', { v: num(plantMw(p), 1) })}`;
    if (k === 'bridges') return p.type === 'Tunnel' ? p.name : `${p.name} · ${T(p.o === 'K' ? STATUS.K : COND[p.c] || TK('Condition not rated'))}`;
    if (k === 'airports') return p.name;
    if (k === 'evcharge') return `${p.name} · ${T(p.ports === 1 ? TK('{n} port') : TK('{n} ports'), { n: num(p.ports) })}`;
    if (k === 'powerlines') return T(p.cable ? '{kv} kV cable (underground or submarine)' : '{kv} kV transmission line', { kv: p.kv });
    if (k === 'traffic') return T('{r}: {n} vehicles a day', { r: p.r, n: num(p.a) });
    if (!LAYERS[k].area) return null;
    if (k === 'oz') return `${ozKind(p)} · ${T('Census tract {t}', { t: p.t })}, ${p.m}`;
    if (k === 'hexgrid') { const a = areaSpec(k), v = p[a.prop]; return `${T(a.title)}: ${v == null ? '—' : num(v, a.d != null ? a.d : a.prop === 'bf' || a.prop === 'pf' ? 1 : 0)}`; }
    return T('{v}% below 100/20 Mbps', { v: num(p[LAYERS[k].area.prop], 1) });
  }

  // name, type, municipio, the listing date of a historic place and the source line: the only fields the files keep (facilities.py, community_assets.py)
  // a simulated connection between two municipios (transit_links.py): the workers who travel between them, the road path and what is listed today
  function linkPopup(p, d) {
    const n = d.notes || {};
    return `<div class="pop"><h4>${ic('links')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))}</div>`
      + `<div><b>${esc(T('{n} workers travel between them (± {m})', { n: num(p.workers), m: num(p.moe) }))}</b></div>`
      + `<div class="meta">${esc(T('{km} km along the roads between the town centres, about {min} minutes by car without traffic', { km: num(p.km, 1), min: num(p.min) }))}</div>`
      + (p.publicos ? `<div class="meta">${esc(T(p.publicos === 1 ? TK('{n} público route on the 2020 list') : TK('{n} público routes on the 2020 list'), { n: num(p.publicos) }))}</div>` : '')
      + (p.via ? `<div class="meta">${esc(T('Timetabled routes join them with a transfer in another municipio.'))}</div>` : '')
      + (p.aadt_max ? `<div class="meta">${esc(T('The roads it follows carry {m} vehicles a day at the middle count and {x} on the busiest stretch (FHWA HPMS).', { m: num(p.aadt_med), x: num(p.aadt_max) }))}</div>` : '')
      + (p.deaths_5y != null ? `<div class="meta">${esc(T('{d} people were killed in crashes within 100 m of its roads in five years, {w} of them walking or cycling (NHTSA FARS).', { d: num(p.deaths_5y), w: num(p.walk_bike_5y) }))}</div>` : '')
      + (p.along_res != null ? `<div class="meta">${esc(T('{n} residents live within 1 km of its roads, {f} of them more than 400 m from a scheduled stop (2020 Census).', { n: num(p.along_res), f: num(p.along_far) }))}</div>` : '')
      + (p.bridges_poor ? `<div class="meta">${esc(T(p.bridges_poor === 1 ? TK('1 bridge in poor condition on its roads (FHWA).') : TK('{n} bridges in poor condition on its roads (FHWA).'), { n: num(p.bridges_poor) }))}</div>` : '')
      + (p.tt_best != null ? `<div class="meta">${esc(T('By the weekday timetables: {m} minutes from town centre to town centre, with transfers (fastest, leaving from 6 to 9 a.m.).', { m: num(p.tt_best) }))}</div>`
        : p.tt_why ? `<div class="meta">${esc(T(p.tt_why === 1 ? TK('No trip by the weekday timetables: a town centre has no timetabled stop within 1 km.') : TK('No trip by the weekday timetables within 3 hours.')))}</div>` : '')
      + `<div class="meta">${esc(T('A simulation, not a proposed route.'))} <a href="transit-links.html">${esc(T('Connections between municipios page'))}</a></div>`
      + `<div class="src">${esc(T(LAYERS.links.source, { date: n.flows_period || d.vintage || '—' }))}</div></div>`;
  }
  function pubPopup(p, d) {
    return `<div class="pop"><h4>${ic('publicos')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))}</div>`
      + (p.code ? `<div class="meta">${esc(T('Route code: {c}', { c: p.code }))}</div>` : '') + `<div class="meta">${esc(p.municipio)}</div>`
      + `<div class="meta">${esc(T('Listed in 2020; it may no longer run.'))}</div><div class="src">${esc(T(LAYERS.publicos.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  // a stretch of a main road (traffic.py): its count, the year of the count, trucks, lanes, speed limit and road class
  const FSYS = { 1: TK('Interstate'), 2: TK('Other freeway or expressway'), 3: TK('Other principal arterial'), 4: TK('Minor arterial'), 5: TK('Major collector') };
  function trafPopup(p, d) {
    return `<div class="pop"><h4>${ic('traffic')}${esc(p.r)}</h4><div class="meta">${esc(T(FSYS[p.f] || ''))}${p.o ? ' · ' + esc(T('one direction of a divided road')) : ''}</div>`
      + `<div><b>${esc(T('{n} vehicles a day', { n: num(p.a) }))}</b></div>`
      + `<div class="meta">${esc(T('Annual average daily traffic; count or estimate of {y}', { y: p.y || '—' }))}</div>`
      + (p.t != null ? `<div class="meta">${esc(T('Trucks: {v}% of vehicles', { v: num(p.t, 1) }))}</div>` : '')
      + `<div class="meta">${esc(T(p.l === 1 ? TK('{n} through lane') : TK('{n} through lanes'), { n: num(p.l) }))}${p.s ? ' · ' + esc(T('speed limit {mph} mph ({kmh} km/h)', { mph: num(p.s), kmh: num(Math.round(p.s * 1.609344)) })) : ''}</div>`
      + `<div class="src">${esc(T(LAYERS.traffic.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  // ── The federal transportation inventories (transport_inventories.py): bridges and tunnels, airports, ferry routes, EV charging ──
  const COND = { P: TK('Poor condition'), F: TK('Fair condition'), G: TK('Good condition') };
  const STATUS = { K: TK('Closed'), P: TK('Posted for load: a weight limit applies'), B: TK('Should be posted for load'), E: TK('Open with temporary support'), D: TK('Open with temporary support') };
  const OWNERS = { state: TK('the state highway agency'), toll: TK('the toll highway authority'), municipal: TK('the municipio'), federal: TK('a federal agency'), other: TK('another public or private owner') };
  const OWNED = { public: TK('publicly owned'), private: TK('privately owned'), military: TK('military'), other: TK('other owner') };
  function bridgePopup(p, d) {
    const n = d.notes || {}, tun = p.type === 'Tunnel';
    return `<div class="pop"><h4>${ic('bridges')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))} · ${esc(p.municipio)}</div>`
      + (p.x ? `<div class="meta">${esc(T(tun ? TK('Carries {x}') : TK('Over {x}'), { x: p.x }))}</div>` : '')
      + (tun ? '' : `<div><b>${esc(T(COND[p.c] || TK('Condition not rated')))}</b>${p.lr != null ? ' ' + esc(T('(lowest rating {r} of 9)', { r: p.lr })) : ''}</div>`)
      + (STATUS[p.o] ? `<div class="meta"><b>${esc(T(STATUS[p.o]))}</b></div>` : '')
      + (p.s ? `<div class="meta"><b>${esc(T('Scour critical: a flood could undermine its foundations'))}</b></div>` : '')
      + (p.y ? `<div class="meta">${esc(p.yr ? T('Built {y}, rebuilt {r}', { y: p.y, r: p.yr }) : T('Built {y}', { y: p.y }))}</div>` : '')
      + (p.a != null ? `<div class="meta">${esc(T('{n} vehicles a day (count of {y})', { n: num(p.a), y: p.ay || '—' }))}${p.t ? ' · ' + esc(T('Trucks: {v}% of vehicles', { v: num(p.t) })) : ''}</div>` : '')
      + (p.l ? `<div class="meta">${esc(T('{m} m long', { m: num(p.l, tun ? 0 : 1) }))}${p.d ? ' · ' + esc(T('detour if closed: {km} km', { km: num(p.d) })) : ''}</div>` : '')
      + (p.i ? `<div class="meta">${esc(T('Last inspection: {when}', { when: monthYear(p.i) }))}</div>` : '')
      + (p.w ? `<div class="meta">${esc(T('Owner: {o}', { o: T(OWNERS[p.w]) }))}</div>` : '')
      + (p.sn ? `<div class="meta">${esc(T(tun ? TK('Tunnel number {n}') : TK('Structure number {n}'), { n: p.sn }))}</div>` : '')
      + `<div class="src">${esc(T(LAYERS.bridges.source, { date: n.nbi_year || d.vintage || '—' }))}</div></div>`;
  }
  const HZ_WORDS = { f: TK('FEMA\'s 1% flood area'), s: TK('NOAA\'s 3 ft sea level rise area'), l: TK('land the USGS rates highly susceptible to landslides') };
  // the hazard areas a tested point stands in (facility_exposure.py): only what is flagged is said; no flag says nothing, rather than "safe"
  function hzLine(p) {
    const c = String(p.hz || '').split('').filter(x => HZ_WORDS[x]);
    return c.length ? `<div class="meta hz">${esc(T('Stands in: {areas}', { areas: c.map(x => T(HZ_WORDS[x])).join('; ') }))}</div>` : '';
  }
  const HZ_FILE = 'facility_hazards.json';
  const hzKey = (c) => `${(+c[0]).toFixed(5)},${(+c[1]).toFixed(5)}`;   // as facility_exposure.py point_key
  function attachHazards(k, d, hz) {   // each point's flags into its properties, once; a layer with no flagged point gets none
    const m = hz && hz.layers && hz.layers[k];
    if (!m || !d || !d.features || d.hzAttached) return;
    for (const f of d.features) { const g = f.geometry; if (g && g.type === 'Point') { const c = m[hzKey(g.coordinates)]; if (c) f.properties.hz = c; } }
    d.hzAttached = true;
  }
  function schoolPopup(p, d) {
    return `<div class="pop"><h4>${ic('schools')}${esc(p.name || T('No name recorded'))}</h4><div class="meta">${esc(T('Public school'))} · ${esc(p.municipio)}</div>`
      + (p.students != null ? `<div class="meta">${esc(T('{n} students', { n: num(p.students) }))}${p.grades ? ' · ' + esc(T('grades {g}', { g: p.grades })) : ''}</div>` : p.grades ? `<div class="meta">${esc(T('grades {g}', { g: p.grades }))}</div>` : '')
      + `<div class="src">${esc(T(LAYERS.schools.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  function airportPopup(p, d) {
    const s = LAYERS.airports.sized;
    return `<div class="pop"><h4>${ic('airports')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))} · ${esc(p.municipio)}</div>`
      + `<div><b>${esc(T(s.labels[p.cat] || p.type))}</b></div>`
      + `<div class="meta">${esc(T('FAA identifier: {id}', { id: p.faa }))}</div>`
      + `<div class="meta">${esc(T(p.use === 'public' ? TK('Open to public use') : TK('Private use')))} · ${esc(T(OWNED[p.own] || OWNED.other))}</div>`
      + (p.elev != null ? `<div class="meta">${esc(T('{f} feet above sea level', { f: num(p.elev) }))}</div>` : '') + (p.tower ? `<div class="meta">${esc(T('Control tower'))}</div>` : '')
      + `<div class="src">${esc(T(LAYERS.airports.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  function ferryPopup(p, d) {
    return `<div class="pop"><h4>${ic('ferries')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))}</div>`
      + `<div><b>${esc(T('{n} passengers in {y}, both directions', { n: num(p.pax), y: d.vintage || '—' }))}</b></div>`
      + (p.veh ? `<div class="meta">${esc(T('{n} vehicles', { n: num(p.veh) }))}</div>` : '')
      + `<div class="meta">${esc(T('{n} trips a year; about {m} minutes a crossing', { n: num(p.trips), m: num(p.min) }))}</div>`
      + `<div class="meta">${esc(T('Today\'s timetabled trips are on the Transit routes layer.'))}</div>`
      + `<div class="src">${esc(T(LAYERS.ferries.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  function evPopup(p, d) {
    const parts = [p.dc ? T('{n} DC fast', { n: num(p.dc) }) : '', p.l2 ? T('{n} Level 2', { n: num(p.l2) }) : '', p.l1 ? T('{n} Level 1', { n: num(p.l1) }) : ''].filter(Boolean).join(', ');
    return `<div class="pop"><h4>${ic('evcharge')}${esc(p.name)}</h4><div class="meta">${esc(T(p.type))} · ${esc(p.municipio)}</div>`
      + `<div><b>${esc(T(p.ports === 1 ? TK('{n} charging port: {list}') : TK('{n} charging ports: {list}'), { n: num(p.ports), list: parts }))}</b></div>`
      + (p.status === 'unavailable' ? `<div class="meta"><b>${esc(T('Temporarily unavailable'))}</b></div>` : '')
      + (p.net ? `<div class="meta">${esc(T('Network: {n}', { n: p.net }))}</div>` : '') + (p.conn ? `<div class="meta">${esc(T('Connectors: {c}', { c: p.conn.join(', ') }))}</div>` : '')
      + (p.confirmed ? `<div class="meta">${esc(T('Last confirmed: {d}', { d: p.confirmed }))}</div>` : '')
      + `<div class="src">${esc(T(LAYERS.evcharge.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  // ── Transmission lines (power_lines.py): OpenStreetMap's lines by voltage, simplified; no name, operator, circuit or substation ──
  function linePopup(p, d) {
    const n = d.notes || {}, kind = p.cable ? TK('{kv} kV cable (underground or submarine)') : TK('{kv} kV transmission line');
    return `<div class="pop"><h4>${ic('powerlines')}${esc(T(kind, { kv: p.kv }))}</h4>`
      + `<div class="meta">${esc(T('{km} km at {kv} kV mapped in Puerto Rico', { km: num(((n.km_by_kv || {})[p.kv]) || p.km, 0), kv: p.kv }))}</div>`
      + (p.kv === 38 ? `<div class="meta">${esc(T('The 38 kV network is about half mapped in OpenStreetMap: {a} km against {b} km of circuits in the utility\'s 2019 plan.', { a: num((n.km_by_kv || {})['38'], 0), b: num((n.irp_2019_circuit_km || {})['38'], 0) }))}</div>` : '')
      + `<div class="meta">${esc(T('Drawn simplified to about 100 m: the route, not each tower.'))}</div>`
      + `<div class="src">${esc(T(LAYERS.powerlines.source, { date: d.vintage || '—' }))}</div></div>`;
  }
  const withHz = (k, html, p) => {   // the hazard line goes before the source line
    if (!LAYERS[k] || !LAYERS[k].hazards) return html;
    const h = hzLine(p), at = html.lastIndexOf('<div class="src">');
    return !h ? html : at < 0 ? html.replace(/<\/div>$/, h + '</div>') : html.slice(0, at) + h + html.slice(at);
  };
  const popup = (k, p, d) => withHz(k, popup0(k, p, d), p);
  const popup0 = (k, p, d) => k === 'hexgrid' ? hexPopup(p, d) : k === 'schools' ? schoolPopup(p, d) : k === 'bridges' ? bridgePopup(p, d) : k === 'airports' ? airportPopup(p, d) : k === 'ferries' ? ferryPopup(p, d) : k === 'evcharge' ? evPopup(p, d) : k === 'powerlines' ? linePopup(p, d) : k === 'traffic' ? trafPopup(p, d) : k === 'links' ? linkPopup(p, d) : k === 'publicos' ? pubPopup(p, d) : k === 'plants' ? plantPopup(p, d) : k === 'broadband' ? bbPopup(p, d) : k === 'oz' ? ozPopup(p, d) : k === 'reservoirs' ? resPopup(p, d) : k === 'rivers' ? rivPopup(p, d) : k === 'groundwater' ? gwPopup(p, d) : k === 'rain' ? rainPopup(p, d) : `<div class="pop"><h4>${ic(k)}${esc(k === 'dumping' && p.name ? T('Near {name}', { name: p.name }) : p.name || (LAYERS[k].line ? T(p.type) : T('No name recorded')))}</h4><div class="meta">${p.name || !LAYERS[k].line ? esc(T(p.type)) + ' · ' : ''}${esc(p.municipio)}</div>${p.listed ? `<div class="meta">${esc(T('Listed: {date}', { date: p.listed }))}</div>` : ''}${k === 'lihtc' && p.units ? `<div class="meta">${esc(T('{units} units, {li} low-income', { units: num(p.units), li: num(p.li_units || 0) }))}${p.year ? ' · ' + esc(T('placed in service {year}', { year: p.year })) : ''}</div>` : ''}${extra(k, p)}<div class="src">${esc(T(LAYERS[k].source, { date: d.vintage || '—' }))}</div></div>`;

  function noteText(k, d, where) {   // what is drawn, of how many; the counted places that are not drawn, and where the counts are (the 2D map's Economy tab; the 3D columns' datasets)
    if (k === 'reservoirs') return T(d.liveFailed ? TK('{n} reservoirs, {a} of them in AAA\'s daily report. The latest readings could not be loaded from USGS: the levels are those of {date}.') : d.liveAt ? TK('{n} reservoirs, {a} of them in AAA\'s daily report; latest USGS readings loaded {t}') : TK('{n} reservoirs, {a} of them in AAA\'s daily report. Loading the latest readings from USGS…'), { n: num(d.features.length), a: num((d.notes || {}).aaa_monitored || 0), date: d.vintage || '—', t: d.liveAt ? when(d.liveAt) : '' });   // the reservoirs' note says whether the live readings came
    if (k === 'rivers') return T(d.liveFailed ? TK('{n} gauges on {r} rivers and streams. The latest readings could not be loaded from USGS: the flows are those of {date}.') : d.liveAt ? TK('{n} gauges on {r} rivers and streams; latest USGS readings loaded {t}') : TK('{n} gauges on {r} rivers and streams. Loading the latest readings from USGS…'), { n: num(d.features.length), r: num((d.notes || {}).rivers || 0), date: d.vintage || '—', t: d.liveAt ? when(d.liveAt) : '' });
    if (k === 'groundwater') return T(d.liveFailed ? TK('{n} wells in {m} municipios. The latest readings could not be loaded from USGS: the depths are those of {date}.') : d.liveAt ? TK('{n} wells in {m} municipios; latest USGS readings loaded {t}') : TK('{n} wells in {m} municipios. Loading the latest readings from USGS…'), { n: num(d.features.length), m: num((d.notes || {}).municipios || 0), date: d.vintage || '—', t: d.liveAt ? when(d.liveAt) : '' });
    if (k === 'rain') return T(d.liveFailed ? TK('{n} rain gauges in {m} municipios. The latest readings could not be loaded from USGS: the totals are those of {date}.') : d.liveAt ? TK('{n} rain gauges in {m} municipios; latest USGS readings loaded {t}') : TK('{n} rain gauges in {m} municipios. Loading the latest readings from USGS…'), { n: num(d.features.length), m: num((d.notes || {}).municipios || 0), date: d.vintage || '—', t: d.liveAt ? when(d.liveAt) : '' });
    if (k === 'hexgrid') { const n = d.notes || {}; return T('{n} hexagons of 1 km² over the land. Every hexagon has the same area, so a count is a density; a census block is counted whole in one hexagon. Heat and greenness are the median of the hexagon\'s 60 m cells; slope is the mean of its 10 m cells.', { n: num(n.cells) }); }
    if (k === 'broadband') { const n = d.notes || {}; return T('{n} hexagons with 10 or more locations, as of {date}; {h} hexagons with fewer ({l} locations) are not drawn.', { n: num(n.hexes_drawn), date: n.as_of || '—', h: num(n.hexes_left_out), l: num(n.locations_left_out) }); }
    if (k === 'traffic') { const n = d.notes || {}, cy = n.count_years || []; return T('{n} stretches, {km} km of arterials and major collectors with a traffic count, data year {y}; the counts were taken from {a} to {b}.', { n: num(n.stretches), km: num(n.km), y: n.data_year || '—', a: cy[0] || '—', b: cy[1] || '—' }); }
    if (k === 'publicos') { const n = d.notes || {}; return T('{n} routes listed on {date}, {b} of them between municipios. No timetable; a route may no longer run.', { n: num(n.routes), date: n.as_of || '—', b: num(n.between_municipios) }); }
    if (k === 'links') { const n = d.notes || {}; return T('{n} pairs of municipios with {w} workers or more and no timetabled route: {a} with no route listed, {b} with a público route on the 2020 list. A simulation, not proposed routes.', { n: num(n.links), w: num(n.min_workers), a: num(n.none_listed), b: num(n.with_publico_2020) }); }
    if (k === 'powerlines') { const n = d.notes || {}, by = n.km_by_kv || {}; return T('{a} km at 230 kV, {b} km at 115 kV and {c} km at 38 kV mapped in OpenStreetMap ({date}), drawn simplified to about 100 m. The 38 kV network is about half mapped. The {s} substations mapped are not drawn.', { a: num(by['230'], 0), b: num(by['115'], 0), c: num(by['38'], 0), date: d.vintage || '—', s: num(n.substations) }); }
    if (k === 'plants') { const n = d.notes || {}; return T(n.planned_plants ? TK('{n} plants of 1 MW or more in {m} municipios: {mw} MW, {r} MW of it renewable, and {b} MW of batteries; {p} more planned or under construction (EIA, {date}). Rooftop solar systems are smaller than 1 MW and are not in this inventory.') : TK('{n} plants of 1 MW or more in {m} municipios: {mw} MW, {r} MW of it renewable, and {b} MW of batteries (EIA, {date}). Rooftop solar systems are smaller than 1 MW and are not in this inventory.'), { n: num(n.plants), m: num(n.municipios), mw: num(n.mw), r: num(n.renewable_mw), b: num(n.battery_mw, 1), p: num(n.planned_plants), date: monthYear(d.vintage) }); }
    if (k === 'bridges') { const n = d.notes || {}, ay = n.adt_years || []; return T('{b} bridges of 20 feet or more and {t} tunnels (FHWA, {y}): {p} in poor condition, {c} closed, {s} scour critical. The traffic counts are from {a} to {z}.', { b: num(n.bridges), t: num(n.tunnels), y: n.nbi_year || '—', p: num(n.poor), c: num(n.closed), s: num(n.scour_critical), a: ay[0] || '—', z: ay[1] || '—' }); }
    if (k === 'schools') { const n = d.notes || {}; return T('{n} open public schools with {s} students, school year {y}; {f} of them stand in at least one hazard area (see each pop-up).', { n: num(n.schools || d.features.length), s: num(n.students), y: d.vintage || '—', f: num(n.flagged) }); }
    if (k === 'airports') { const n = d.notes || {}; return T('{n} airports and heliports open to the public or owned by a public body (FAA, {date}); {h} private airports, heliports and seaplane bases owned privately are counted, not drawn.', { n: num(n.drawn), date: d.vintage || '—', h: num(n.private_not_drawn) }); }
    if (k === 'ferries') { const n = d.notes || {}; return T('{n} routes between {t} terminals with {p} passengers in {y}, both directions (BTS census of {c}).', { n: num(n.routes), t: num(n.terminals), p: num(n.passengers), y: n.data_year || '—', c: n.census_year || '—' }); }
    if (k === 'evcharge') { const n = d.notes || {}; return T('{n} public charging stations with {p} ports in {m} municipios, {f} of them with DC fast charging; {u} temporarily unavailable (AFDC, {date}).', { n: num(n.stations), p: num(n.ports), m: num(n.municipios), f: num(n.dc_fast_stations), u: num(n.unavailable), date: d.vintage || '—' }); }
    if (k === 'oz') { const n = d.notes || {}; return T('{n} census tracts designated for {from} to {to}: {u} not rural, {r} rural, of {e} eligible. The Opportunity Zones page shows the eligible tracts that were not designated.', { n: num(n.designated), from: (n.starts || '').slice(0, 4), to: (n.ends || '').slice(0, 4), u: num(n.non_rural), r: num(n.rural), e: num(n.eligible) }); }
    const n = d.notes || {}, drawn = d.features.length, all = n.developments || n.projects || n.libraries || n.stations || drawn;
    return n.counted_not_drawn ? T('{n} points for {drawn} of {all} listings; {r} private homes and haciendas are counted by municipio ({where}) but not drawn.', { n: num(drawn), drawn: num(n.listings_drawn), all: num(n.listings), r: num(n.counted_not_drawn), where })
      : n.listings ? T('{n} points for {all} listings.', { n: num(drawn), all: num(n.listings) })
      : n.traced ? T('{n} stretches, {km} km; {c} more are on the Transit routes layer already.', { n: num(drawn), km: num(n.km, 1), c: num(n.covered_left_out) })
      : n.municipios_without_a_city_hall_mapped ? T('{n} drawn; {g} municipios have none mapped.', { n: num(drawn), g: num(n.municipios_without_a_city_hall_mapped.length) })
      : drawn < all ? T('{drawn} of {all} drawn; the counts by municipio ({where}) include all.', { drawn: num(drawn), all: num(all), where }) : T('{n} drawn.', { n: num(drawn) });
  }
  // the note's element, made under the layer's row the first time
  function noteEl(k, doc) {
    const id = `facNote-${k}`; let el = doc.getElementById(id);
    if (!el) { const row = doc.getElementById(LAYERS[k].id).closest('.layer'); row.insertAdjacentHTML('afterend', `<div class="note fac-note" id="${id}"></div>`); el = doc.getElementById(id); }
    return el;
  }
  // the help buttons of these layers: the page loads this file on the first click of one (translated when shown, after the Spanish has arrived)
  function addHelp(HELP) { for (const [k, [t, b]] of Object.entries(HELP_TEXT)) Object.defineProperty(HELP, k, { get: () => [T(t), T(b)], enumerable: true, configurable: true }); }

  return { LAYERS, TYPES, WORDS, HELP_TEXT, KEYS: Object.keys(LAYERS), popup, noteText, HZ_FILE, attachHazards, hzKey, noteEl, addHelp, live, usual, weekOf, GAUGE, floodRefs, nwsStages, rainWeek, areaClass, areaSpec, legendHtml, tip, lineStyle, sizedStyle };
});
