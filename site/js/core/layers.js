/* PR Data Observatory core: the layer menu of the 2D map (index.html, "Layers" tab) and the 3D view (3d.html, "Layers" tab), in one list (docs/layers.md).

   Both menus are static markup in their pages (so every id, legend and count slot stays where the pages' scripts, tests and links expect it); this file is
   the order and the names they must have. tests/layers_menu.test.js reads both pages and fails when a page's groups, their order, a row's group, order,
   name or source, or a name's Spanish differ from this list. The pages do not load this file.

     GROUPS     the groups by topic (decision 81 (e)): Reference first, then the domains that have layers in the order of dictionary_src/domains.json, the
                visitor economy last: { id, en, es, icon, rows }. Every group is in both views, in this order; a group with no row in a
                view shows its heading and a note that says where its layers are (data-elsewhere). setting: a group of settings of one view (the 3D
                scene), not data: it comes first and its rows are not counted.
     rows       { id, key, en, es, src, views }, in the order of the menu: areas, then lines, then points. id is the element id (checkbox or select) the
                pages' scripts, the dictionary's view links and the tests use; key is its l= key in the 2D map's address (app.js LAYER_KEYS), never
                changed. src is the source in the row's <small class="src">: a string is a name, the same in both languages (translate="no"), and
                { en, es } is translated. views: '2d', '3d' or both. counted: false, a row the group's "N layers on" and the chip leave out (class
                "layer nocount"). A row { head: { en, es } } is a subheading (h3.sec lsub) over the rows after it.
     domain     the row's home domain, an id of dictionary_src/domains.json (navigation plan, decision 81); also: the other domains that list it ("also in").
                null for a reference layer or a setting of the view (boundaries, barrios, shading, columns, terrain, buildings), which belongs to no topic.
     why        a row in one view only says why it cannot be drawn in the other (oneView(); tests/layers_menu.test.js requires it). Since phase B (2026-10-19)
                every layer that can be drawn in both views is in both. */
(function (name, root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('layers', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const B = ['2d', '3d'], D2 = ['2d'], D3 = ['3d'];
  const CENSUS = { en: 'Census 2020', es: 'Censo 2020' }, OSM = 'OpenStreetMap';
  const GROUPS = [
    { id: 'scene', en: '3D scene', es: 'Escena 3D', icon: 'terrain', setting: true, views: D3, rows: [
      { id: 'lyTerrain', domain: null, en: '3D terrain', es: 'Terreno en 3D', counted: false, src: { en: 'AWS / Mapzen elevation', es: 'Elevación de AWS / Mapzen' }, views: D3, why: 'a setting of the 3D scene: the 2D map is flat' },
      { id: 'lyBuildings', domain: null, en: '3D buildings', es: 'Edificios en 3D', counted: false, src: { en: 'OpenStreetMap and Overture', es: 'OpenStreetMap y Overture' }, views: D3, why: 'a setting of the 3D scene: building heights need the 3D camera; the 2D map is flat' },
    ] },
    { id: 'reference', en: 'Reference', es: 'Referencia', icon: 'map', rows: [   // the reference layers: no topic (navigation plan, section 6)
      { id: 'lyMuni', domain: null, key: 'muni', en: 'Municipal boundaries', es: 'Límites municipales', src: CENSUS, views: B, counted: false },   // the reference layer: off when the page opens (2026-11-13), never counted
      { id: 'lyBarrios', domain: null, key: 'barrios', en: 'Barrios', es: 'Barrios', src: CENSUS, views: B },
      { id: 'lyHexgrid', domain: null, key: 'hexgrid', en: 'Hexagon grid (1 km²)', es: 'Cuadrícula de hexágonos (1 km²)', src: CENSUS, views: B },
      { id: 'lyCols', domain: null, en: 'Columns by municipality', es: 'Columnas por municipio', views: D3, why: 'a column is a height, which a flat map cannot show; the 2D map shades the municipios with the same datasets instead (Explore, On the map)' },   // and columns in 3D (#metric picks the measure)
    ] },
    { id: 'economy', en: 'Economy', es: 'Economía', icon: 'work', rows: [
      { id: 'lyOz', domain: 'economy', also: ['communities', 'public-money'], key: 'oz', en: 'Opportunity Zones 2.0', es: 'Zonas de Oportunidad 2.0', src: { en: 'US Treasury', es: 'Tesoro de EE. UU.' }, views: B },
    ] },
    { id: 'housing', en: 'Housing', es: 'Vivienda', icon: 'home_work', rows: [
      { id: 'lyPubHousing', domain: 'housing', also: ['communities'], key: 'pubhousing', en: 'Public housing developments', es: 'Residenciales públicos', src: 'HUD', views: B },
      { id: 'lyLihtc', domain: 'housing', also: ['public-money'], key: 'lihtc', en: 'Tax credit housing projects', es: 'Proyectos de vivienda con crédito contributivo', src: 'HUD LIHTC', views: B },
    ] },
    { id: 'education', en: 'Education', es: 'Educación', icon: 'school', rows: [
      { id: 'lyLibraries', domain: 'education', also: ['communities'], key: 'libraries', en: 'Public libraries', es: 'Bibliotecas públicas', src: 'USAC E-Rate', views: B },
      { id: 'lySchools', domain: 'education', key: 'schools', en: 'Public schools', es: 'Escuelas públicas', src: 'NCES', views: B },
    ] },
    { id: 'environment', en: 'Environment and climate', es: 'Ambiente y clima', icon: 'forest', rows: [
      { id: 'lySurfHeat', domain: 'environment', also: ['health', 'hazards'], key: 'surfheat', en: 'Surface heat, summer mornings and nights', es: 'Calor de la superficie, mañanas y noches de verano', src: 'USGS Landsat', views: B },   // the 60 m image of heat.py (decision 88)
      { id: 'lyReservoirs', domain: 'environment', also: ['infrastructure', 'hazards'], key: 'reservoirs', en: 'Reservoir levels', es: 'Niveles de los embalses', src: 'USGS', views: B },
      { id: 'lyRivers', domain: 'environment', also: ['hazards', 'infrastructure'], key: 'rivers', en: 'River flow', es: 'Caudal de los ríos', src: 'USGS', views: B },
      { id: 'lyGroundwater', domain: 'environment', also: ['infrastructure', 'hazards'], key: 'groundwater', en: 'Groundwater levels', es: 'Niveles del agua subterránea', src: 'USGS', views: B },
      { id: 'lyRain', domain: 'environment', also: ['hazards'], key: 'rain', en: 'Rainfall', es: 'Lluvia', src: 'USGS', views: B },
      { id: 'lyWatersheds', domain: 'environment', also: ['hazards'], key: 'watersheds', en: 'Watersheds and streams', es: 'Cuencas y quebradas', src: 'USGS WBD, NHDPlus HR', views: D2, why: 'a preview on the 2D map first: the 3D view has no watershed layer yet' },
      { id: 'lyDumping', domain: 'environment', also: ['infrastructure'], key: 'dumping', en: 'Illegal dumping sites', es: 'Vertederos clandestinos', src: { en: 'FPR field survey', es: 'Encuesta de campo de FPR' }, views: B },
      { head: { en: 'Land and protected areas', es: 'Suelo y áreas protegidas' } },
      { id: 'lyProt', domain: 'environment.land', key: 'prot', en: 'Protected areas', es: 'Áreas protegidas', src: 'USGS PAD-US', views: B },
      { id: 'lyLanduse', domain: 'environment.land', also: ['housing'], key: 'landuse', en: 'Land use 2015', es: 'Uso de terrenos 2015', src: 'Junta de Planificación', views: B },
      { id: 'lySoil', domain: 'environment.land', also: ['hazards'], key: 'soil', en: 'Soils', es: 'Suelos', src: 'USDA NRCS SSURGO', views: B },
      { id: 'lySlope', domain: 'environment.land', also: ['hazards'], key: 'slope', en: 'Slope', es: 'Pendiente', src: 'USGS 3DEP', views: D2, why: 'a preview on the 2D map first: the 3D view shows the terrain itself' },
      { id: 'lyContours', domain: 'environment.land', key: 'contours', en: 'Contour lines', es: 'Curvas de nivel', src: 'USGS 3DEP', views: D2, why: 'a preview on the 2D map first: the 3D view shows the terrain itself' },
    ] },
    { id: 'hazards', en: 'Hazards', es: 'Riesgos', icon: 'flood', rows: [
      { id: 'lyFlood', domain: 'hazards', also: ['population', 'housing'], key: 'flood', en: 'Flood zones', es: 'Zonas inundables', src: 'FEMA', views: B },
      { id: 'lySlide', domain: 'hazards', also: ['environment.land'], key: 'slide', en: 'Landslide susceptibility', es: 'Susceptibilidad a deslizamientos', src: 'USGS', views: B },
      { id: 'lySlr', domain: 'hazards', also: ['population', 'housing'], key: 'slr', en: 'Sea level rise', es: 'Aumento del nivel del mar', src: 'NOAA', views: B },
    ] },
    { id: 'infrastructure', en: 'Infrastructure and mobility', es: 'Infraestructura y movilidad', icon: 'commute', rows: [
      { head: { en: 'Communications', es: 'Comunicaciones' } },
      { id: 'lyBroadband', domain: 'infrastructure', also: ['economy'], key: 'broadband', en: 'Broadband gaps (FCC hexagons)', es: 'Brechas de banda ancha (hexágonos de la FCC)', src: 'FCC', views: B },
      { head: { en: 'Energy', es: 'Energía' } },
      { id: 'lyPowerLines', domain: 'infrastructure.energy', also: ['hazards'], key: 'powerlines', en: 'Transmission lines', es: 'Líneas de transmisión', src: OSM, views: B },
      { id: 'lyPlants', domain: 'infrastructure.energy', also: ['environment'], key: 'plants', en: 'Power plants', es: 'Plantas de energía', src: 'EIA', views: B },
      { head: { en: 'Mobility and transit', es: 'Movilidad y transporte' } },
      { id: 'lyRoutes', domain: 'infrastructure.mobility', key: 'routes', en: 'Transit routes', es: 'Rutas de transporte colectivo', src: { en: 'ATI, municipal systems, OpenStreetMap', es: 'ATI, sistemas municipales, OpenStreetMap' }, views: B },
      { id: 'lyFprRoutes', domain: 'infrastructure.mobility', key: 'fprroutes', en: 'Municipal routes mapped by FPR', es: 'Rutas municipales trazadas por FPR', src: 'FPR', views: B },
      { id: 'lyPublicos', domain: 'infrastructure.mobility', key: 'publicos', en: 'Público routes (2020 list)', es: 'Rutas de públicos (lista de 2020)', src: { en: 'Instituto de Estadísticas, ACT', es: 'Instituto de Estadísticas, ACT' }, views: B },
      { id: 'lyTraffic', domain: 'infrastructure.mobility', key: 'traffic', en: 'Traffic on the main roads', es: 'Tránsito en las carreteras principales', src: 'FHWA HPMS', views: B },
      { id: 'lyLinks', domain: 'infrastructure.mobility', also: ['economy'], key: 'links', en: 'Simulated connections between municipios', es: 'Conexiones simuladas entre municipios', src: { en: 'FPR simulation', es: 'Simulación de FPR' }, views: B },
      { id: 'lyBridges', domain: 'infrastructure.mobility', also: ['hazards'], key: 'bridges', en: 'Bridges and tunnels', es: 'Puentes y túneles', src: 'FHWA', views: B },
      { id: 'lyAirports', domain: 'infrastructure.mobility', key: 'airports', en: 'Airports and heliports', es: 'Aeropuertos y helipuertos', src: 'FAA', views: B },
      { id: 'lyFerries', domain: 'infrastructure.mobility', key: 'ferries', en: 'Ferry routes and passengers', es: 'Rutas de lanchas y pasajeros', src: 'BTS', views: B },
      { id: 'lyEvCharge', domain: 'infrastructure.mobility', also: ['infrastructure.energy'], key: 'evcharge', en: 'Public EV charging stations', es: 'Estaciones públicas de carga de vehículos eléctricos', src: 'AFDC', views: B },
      { id: 'lyStops', domain: 'infrastructure.mobility', key: 'stops', en: 'Transit stops', es: 'Paradas de transporte colectivo', src: 'ATI, OpenStreetMap', views: B },
      { id: 'lyHubs', domain: 'infrastructure.mobility', key: 'hubs', en: 'Stations, terminals & airports', es: 'Estaciones, terminales y aeropuertos', src: 'ATI, OpenStreetMap, FAA', views: B },
      { id: 'lyTaxi', domain: 'infrastructure.mobility', key: 'taxi', en: 'Taxi stands & EV charging', es: 'Paradas de taxis y carga de vehículos eléctricos', src: OSM, views: B },
      { id: 'walkRings', domain: 'infrastructure.mobility', key: 'rings', en: 'Show 400 m walk radius around stops (zoomed in)', es: 'Mostrar radio de 400 m a pie alrededor de las paradas (al acercar el mapa)', views: B },   // after the points it rings (docs/layers.md)
      { id: 'lyTrips', domain: 'infrastructure.mobility', en: 'Scheduled vehicles', es: 'Vehículos con horario', src: { en: 'GTFS timetables (replay)', es: 'Horarios GTFS (reproducción)' }, views: D3, why: 'the replay runs on the 3D time bar (deck.gl TripsLayer); the 2D map shows the vehicles on their timetable now instead (Transit tab, lyNow)' },
      { head: { en: 'Safety and emergencies', es: 'Seguridad y emergencias' } },
      { id: 'lyFire', domain: 'infrastructure', key: 'fire', en: 'Fire and EMS stations', es: 'Estaciones de bomberos y de emergencias médicas', src: 'USGS', views: B },
      { id: 'lyPolice', domain: 'infrastructure', key: 'police', en: 'Police stations', es: 'Cuarteles de la policía', src: OSM, views: B },
    ] },
    { id: 'communities', en: 'Communities', es: 'Comunidades', icon: 'groups', rows: [
      { id: 'lyComunidades', domain: 'communities', also: ['environment.land', 'hazards'], key: 'comunidades', en: 'Comunidades Especiales', es: 'Comunidades Especiales', src: 'Junta de Planificación, 2006', views: B },
      { id: 'lyWcrp', domain: 'communities', also: ['hazards', 'public-money'], key: 'wcrp', en: 'WCRP communities', es: 'Comunidades WCRP', src: 'FPR', views: B },
      { id: 'lyTownhalls', domain: 'communities', also: ['infrastructure'], key: 'townhalls', en: 'City halls', es: 'Alcaldías', src: OSM, views: B },
      { id: 'lyHistoric', domain: 'communities', also: ['education', 'economy.visitor-economy'], key: 'historic', en: 'Historic places', es: 'Lugares históricos', src: { en: 'NPS, National Register', es: 'NPS, Registro Nacional' }, views: B },
    ] },
    { id: 'visitor', en: 'Visitor economy', es: 'Economía del visitante', icon: 'place', rows: [   // always the last group (the standing rule: tourism last)
      { id: 'lyPlaces', domain: 'economy.visitor-economy', key: 'places', en: 'Tourism places', es: 'Lugares turísticos', src: 'Overture', views: B },
    ] },
  ];

  const inView = (r, v) => !!r.views && r.views.includes(v);
  /** The groups of a view, in order, each with its rows and subheadings for that view (a subheading only over rows of the view). */
  function menu(view) {
    return GROUPS.filter(g => !g.views || g.views.includes(view)).map(g => {
      const rows = [];
      g.rows.forEach((r, i) => {
        if (r.head) { const next = g.rows.slice(i + 1); const end = next.findIndex(x => x.head); if ((end < 0 ? next : next.slice(0, end)).some(x => inView(x, view))) rows.push(r); }
        else if (inView(r, view)) rows.push(r);
      });
      return { ...g, rows };
    });
  }
  /** Every layer row (not the subheadings), in menu order. */
  const rows = () => GROUPS.flatMap(g => g.rows.filter(r => !r.head));
  /** The rows in one view only, each with the reason it cannot be drawn in the other (why). */
  const oneView = () => rows().filter(r => r.views.length === 1);
  return { GROUPS, menu, rows, oneView };
});
