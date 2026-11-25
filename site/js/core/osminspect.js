/* PR Data Observatory core: the OpenStreetMap feature inspector of the base map (docs/basemap.md, section 8). Loaded on first use of the "Inspect map" toggle of
   the 2D map (index.html, app.js) and the 3D view (3d.html, twin3d.js), with its Spanish (I18N.load('osminspect')); the pages keep only the toggle and a few lines.

   In inspect mode a click or tap on the map asks MapLibre for the base map's features under the pointer (queryRenderedFeatures; in 2D on the MapLibre map of the
   Leaflet bridge) and shows a small pop-up for the topmost one it may show: its kind in plain words, its name (and road number), and a link to its page on
   openstreetmap.org. Outside inspect mode nothing here runs, and the observatory's own layers take every click as before.

   The OpenStreetMap ID. OpenFreeMap's tiles are built by Planetiler with the OpenMapTiles profile (planetiler-openmaptiles). Planetiler writes each feature's
   vector-tile ID as osm_id × 10 + a type code: 1 node, 2 way, 3 relation, and 0 for a feature from another source or merged from several (PlanetilerConfig
   "feature_source_id_multiplier", OsmElement.vectorTileFeatureId, FeatureMerge.makeMergedId). A link is shown only for an ID that ends in 1, 2 or 3, on a layer whose
   features all come from OpenStreetMap elements (LINK_LAYERS); never a guessed one. Checked on OpenFreeMap's tiles of 2026-10-25 (docs/basemap.md, section 8).

   Privacy (the observatory's standing rules: no personal data; sensitive places are counted, never drawn or named). Never anything from the housenumber layer;
   buildings carry no name in the OpenMapTiles schema and are passed over; swimming pools (often at homes) are passed over; for a sensitive kind of place
   (SENSITIVE) only a generic kind is shown, with no name and no link. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('osminspect', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc } = dep('text');
  const TK = (s) => s;   // a label translated where it is shown (docs/i18n.md, rule 14)
  const OSM = 'https://www.openstreetmap.org/';
  const TYPES = { 1: 'node', 2: 'way', 3: 'relation' };

  // ── Which layers of the OpenMapTiles schema are read ───────────────────────────────────────────────────────────────────────────────────────────
  // SHOWN: the layers whose features can be inspected. Never housenumber (addresses), building (no name in the schema; a home is a building) or boundary.
  const SHOWN = new Set(['poi', 'place', 'transportation_name', 'transportation', 'aerodrome_label', 'mountain_peak', 'water_name', 'waterway', 'aeroway', 'park', 'landuse', 'landcover', 'water']);
  // LINK_LAYERS: layers whose IDs come from OpenStreetMap elements (every layer shown). In `water`, lakes and ponds carry their way or relation (checked on
  // api.openstreetmap.org); the ocean comes from coastline polygons, with an ID ending in 0, so it gets no link and says why.
  const LINK_LAYERS = new Set(SHOWN);

  /** The OpenStreetMap element of a vector-tile feature ID on `layer`: { type: 'node'|'way'|'relation', id, url }, or null when the ID is missing, not a safe
   *  positive integer, ends in 0 (another source, or merged), on a layer whose IDs are not OSM's, or anything else. Never a guess. */
  function osmRef(id, layer) {
    if (!LINK_LAYERS.has(layer)) return null;
    const n = typeof id === 'string' && /^\d+$/.test(id) ? Number(id) : id;
    if (typeof n !== 'number' || !Number.isSafeInteger(n) || n < 11) return null;
    const type = TYPES[n % 10], osm = Math.floor(n / 10);
    return type && osm > 0 ? { type, id: osm, url: `${OSM}${type}/${osm}` } : null;
  }

  // ── Sensitive kinds: a generic kind, no name, no link (docs/basemap.md, section 8, "Privacy") ────────────────────────────────────────────────────
  // Places where being seen says something about a person's health, safety or private life, places that are often a home, and offices often named after one
  // person. The kind shown is generic; the base map may still draw the label (its style is the provider's), but the inspector adds nothing to it.
  const SENSITIVE = {
    health: { kind: TK('Health care'), poi: ['clinic', 'doctors', 'dentist', 'nursing_home', 'physician', 'therapist', 'psychotherapist', 'alternative', 'healthcare', 'counselling', 'rehabilitation', 'hospice'] },
    social: { kind: TK('Social services'), poi: ['social_facility', 'shelter', 'refugee_site', 'group_home', 'assisted_living', 'social_centre', 'women_shelter'] },
    child: { kind: TK('Child care or preschool'), poi: ['kindergarten', 'childcare'] },
    home: { kind: TK('Lodging'), poi: ['guest_house', 'bed_and_breakfast', 'chalet', 'apartment', 'holiday_home'] },
    adult: { kind: TK('Business'), poi: ['erotic', 'massage', 'brothel', 'stripclub', 'swingerclub', 'love_hotel'] },
    dwelling: { kind: TK('Populated place'), place: ['isolated_dwelling', 'farm'] },
  };
  const SENS = new Map();
  for (const g of Object.values(SENSITIVE)) for (const layer of ['poi', 'place']) for (const v of g[layer] || []) SENS.set(layer + ':' + v, g.kind);
  // Offices are shown only when they are public bodies or institutions; the others (lawyer, accountant, physician…) are often one person's practice.
  const PUBLIC_OFFICE = new Set(['government', 'diplomatic', 'quango', 'educational_institution', 'university', 'research', 'water_utility', 'energy_supplier', 'harbour_master', 'ngo', 'association', 'foundation', 'charity', 'political_party', 'religion', 'union', 'newspaper', 'telecommunication', 'cooperative']);

  /** The generic kind (an English label) when a feature is of a sensitive kind, else null. */
  function sensitive(layer, p) {
    p = p || {};
    if (layer === 'poi') {
      const k = SENS.get('poi:' + p.subclass) || SENS.get('poi:' + p.class);
      if (k) return k;
      if (p.class === 'office' && !PUBLIC_OFFICE.has(p.subclass)) return TK('Office');
    }
    if (layer === 'place') return SENS.get('place:' + p.class) || null;
    if (layer === 'landuse' && (p.class === 'kindergarten' || p.class === 'childcare')) return SENSITIVE.child.kind;   // the grounds of a preschool or child care, often a home (review of PR #99)
    return null;
  }

  // ── Kinds in plain words (English keys; their Spanish is in i18n_src/es/osminspect.json) ─────────────────────────────────────────────────────────
  const ROAD = {
    motorway: TK('Motorway'), trunk: TK('Trunk highway'), primary: TK('Primary road'), secondary: TK('Secondary road'), tertiary: TK('Tertiary road'),
    minor: TK('Local street'), service: TK('Service road'), track: TK('Unpaved track'), path: TK('Path'), busway: TK('Bus lane or busway'), raceway: TK('Racetrack'),
    rail: TK('Railway'), transit: TK('Rail transit line'), ferry: TK('Ferry route'), pier: TK('Pier'), bridge: TK('Bridge'), aerialway: TK('Aerial lift'),
    cable_car: TK('Aerial lift'), gondola: TK('Aerial lift'),
    pedestrian: TK('Pedestrian street'), footway: TK('Footway'), sidewalk: TK('Sidewalk'), cycleway: TK('Cycleway'), steps: TK('Steps'), bridleway: TK('Bridleway'),
    platform: TK('Platform'), subway: TK('Metro line'), light_rail: TK('Light rail line'), tram: TK('Tram line'), monorail: TK('Monorail'), narrow_gauge: TK('Railway'),
  };
  const POI = {
    hospital: TK('Hospital'), pharmacy: TK('Pharmacy'), chemist: TK('Pharmacy'), veterinary: TK('Veterinary clinic'),
    police: TK('Police station'), fire_station: TK('Fire station'), townhall: TK('City hall'), courthouse: TK('Courthouse'), prison: TK('Prison'), public_building: TK('Public building'),
    community_centre: TK('Community center'), town_hall: TK('Public building'), post_office: TK('Post office'), post_box: TK('Post box'), post: TK('Post office'), library: TK('Library'), books: TK('Bookshop'),
    school: TK('School'), college: TK('College or university'), university: TK('College or university'),
    place_of_worship: TK('Place of worship'), cemetery: TK('Cemetery'), grave_yard: TK('Cemetery'),
    bank: TK('Bank'), atm: TK('ATM'), fuel: TK('Fuel station'), charging_station: TK('EV charging station'), parking: TK('Parking'), bicycle_parking: TK('Bicycle parking'), motorcycle_parking: TK('Motorcycle parking'),
    bus_stop: TK('Bus stop'), bus_station: TK('Bus station'), bus: TK('Bus stop'), railway: TK('Rail station'), station: TK('Station'), halt: TK('Rail stop'), tram_stop: TK('Tram stop'),
    subway_entrance: TK('Station entrance'), train_station_entrance: TK('Station entrance'), entrance: TK('Entrance'), ferry_terminal: TK('Ferry terminal'), taxi: TK('Taxi stand'),
    airport: TK('Airport'), harbor: TK('Harbor or marina'), marina: TK('Marina'), dock: TK('Dock'),
    restaurant: TK('Restaurant'), fast_food: TK('Fast food'), food_court: TK('Food court'), cafe: TK('Café'), bar: TK('Bar'), pub: TK('Bar'), beer: TK('Bar'), biergarten: TK('Bar'), nightclub: TK('Night club'), ice_cream: TK('Ice cream shop'),
    lodging: TK('Lodging'), hotel: TK('Hotel'), motel: TK('Motel'), hostel: TK('Hostel'), campsite: TK('Campsite'), camp_site: TK('Campsite'), caravan_site: TK('Campsite'),
    museum: TK('Museum'), theatre: TK('Theater'), cinema: TK('Cinema'), art_gallery: TK('Art gallery'), arts_centre: TK('Arts center'), gallery: TK('Art gallery'), artwork: TK('Artwork'), attraction: TK('Tourist attraction'),
    viewpoint: TK('Viewpoint'), information: TK('Tourist information'), castle: TK('Castle or fort'), ruins: TK('Ruins'), monument: TK('Monument'), memorial: TK('Memorial'), fort: TK('Castle or fort'), historic: TK('Historic site'),
    park: TK('Park'), playground: TK('Playground'), garden: TK('Garden'), pitch: TK('Sports field'), sports_centre: TK('Sports center'), stadium: TK('Stadium'), golf: TK('Golf course'), golf_course: TK('Golf course'),
    swimming: TK('Swimming area'), swimming_area: TK('Swimming area'), water_park: TK('Water park'), beach: TK('Beach'), zoo: TK('Zoo'), aquarium: TK('Aquarium'), fitness_centre: TK('Gym'),
    shop: TK('Shop'), grocery: TK('Grocery store'), supermarket: TK('Supermarket'), convenience: TK('Convenience store'), mall: TK('Shopping center'), department_store: TK('Department store'), marketplace: TK('Market'),
    clothing_store: TK('Clothing store'), clothes: TK('Clothing store'), hardware: TK('Hardware store'), doityourself: TK('Hardware store'), alcohol_shop: TK('Liquor store'), bakery: TK('Bakery'),
    car: TK('Car shop or garage'), car_repair: TK('Car repair'), laundry: TK('Laundry'), hairdresser: TK('Hairdresser'), music: TK('Music shop'),
    office: TK('Office'), government: TK('Government office'), diplomatic: TK('Consulate or embassy'), ngo: TK('Nonprofit organization'),
    toilets: TK('Public toilets'), drinking_water: TK('Drinking water'), recycling: TK('Recycling point'), telephone: TK('Telephone'), lighthouse: TK('Lighthouse'),
  };
  const PLACE = {
    continent: TK('Continent'), country: TK('Country'), state: TK('State or territory'), province: TK('Province'), city: TK('City'), town: TK('Town'),
    village: TK('Village'), hamlet: TK('Hamlet'), suburb: TK('Suburb'), quarter: TK('City district'), neighbourhood: TK('Neighborhood'), island: TK('Island'), islet: TK('Islet'),
  };
  const WATER = {
    ocean: TK('Ocean'), sea: TK('Sea'), bay: TK('Bay'), strait: TK('Strait'), lake: TK('Lake'), lagoon: TK('Lagoon'), reservoir: TK('Reservoir'), pond: TK('Pond'),
    river: TK('River'), stream: TK('Stream'), canal: TK('Canal'), drain: TK('Drain'), ditch: TK('Ditch'), wetland: TK('Wetland'),
  };
  const AREA = {
    residential: TK('Residential area'), commercial: TK('Commercial area'), retail: TK('Commercial area'), industrial: TK('Industrial area'), cemetery: TK('Cemetery'),
    hospital: TK('Hospital grounds'), school: TK('School grounds'), college: TK('Campus'), university: TK('Campus'), stadium: TK('Stadium'), pitch: TK('Sports field'),
    military: TK('Military area'), railway: TK('Rail yard'), quarry: TK('Quarry'), farmland: TK('Farmland'), farm: TK('Farmland'), playground: TK('Playground'), garages: TK('Garages'),
    wood: TK('Woodland'), forest: TK('Woodland'), grass: TK('Grassland'), wetland: TK('Wetland'), sand: TK('Sand'), rock: TK('Bare rock'), beach: TK('Beach'), ice: TK('Ice'),
    national_park: TK('National park'), nature_reserve: TK('Nature reserve'), protected_area: TK('Protected area'), park: TK('Park'),
    aerodrome: TK('Airport grounds'), runway: TK('Runway'), taxiway: TK('Taxiway'), apron: TK('Apron'), helipad: TK('Helipad'), heliport: TK('Heliport'), gate: TK('Airport gate'),
    international: TK('International airport'), public: TK('Airport'), regional: TK('Airport'), other: TK('Airport'), private: TK('Private airfield'),
    peak: TK('Peak'), volcano: TK('Volcano'), saddle: TK('Mountain pass'), ridge: TK('Ridge'), cliff: TK('Cliff'),
  };
  const FALLBACK = {
    poi: TK('Place of interest'), place: TK('Place'), transportation: TK('Road or path'), transportation_name: TK('Road or path'), aerodrome_label: TK('Airport'),
    mountain_peak: TK('Peak'), water_name: TK('Body of water'), waterway: TK('Waterway'), aeroway: TK('Airport area'), park: TK('Park or protected area'),
    landuse: TK('Land use area'), landcover: TK('Land cover'), water: TK('Body of water'),
  };
  const pick = (table, p) => table[p.subclass] || table[p.class] || null;
  /** A feature's kind, in plain words (an English label; T() it to show it). */
  function kindOf(layer, p) {
    p = p || {};
    let k = null;
    if (layer === 'transportation' || layer === 'transportation_name') {
      if (/_construction$/.test(p.class || '')) return TK('Road under construction');
      if (p.subclass === 'junction') return TK('Motorway exit');   // transportation_name: a motorway junction node, its ref the exit number
      k = pick(ROAD, p);
    } else if (layer === 'poi') k = pick(POI, p);
    else if (layer === 'place') k = PLACE[p.class] || null;
    else if (layer === 'water_name' || layer === 'waterway' || layer === 'water') k = WATER[p.class] || null;
    else k = pick(AREA, p);
    return k || FALLBACK[layer] || null;
  }
  const nameOf = (p) => { const n = p && (p.name || p['name:latin'] || p.name_int); return typeof n === 'string' && n.trim() ? n.trim() : null; };

  /**
   * What the inspector shows for one feature ({ layer: { id }, sourceLayer, id, properties }, as MapLibre gives it), or null when it shows nothing for it
   * (the next feature down is then tried): { layer, kind, bridge, name, ref, osm ({ type, id, url } or null), why ('sensitive', 'merged', 'source' or null) }.
   */
  function describe(f) {
    const layer = f && f.sourceLayer, p = (f && f.properties) || {};
    if (!SHOWN.has(layer)) return null;   // housenumber, building, boundary, or a layer of another source
    if (p.class === 'swimming_pool' || p.subclass === 'swimming_pool') return null;   // pools: often at homes
    const s = sensitive(layer, p);
    if (s) return { layer, kind: s, bridge: false, name: null, ref: null, exit: false, osm: null, why: 'sensitive' };
    const k = kindOf(layer, p), osm = osmRef(f.id, layer);
    const out = { layer, kind: k, bridge: p.brunnel === 'bridge' && p.class !== 'bridge', name: nameOf(p), ref: null, osm, why: null };
    if (layer === 'transportation' || layer === 'transportation_name') out.ref = typeof p.ref === 'string' && p.ref.trim() ? p.ref.trim() : null;
    out.exit = layer === 'transportation_name' && p.subclass === 'junction';
    if (!osm) out.why = layer === 'water' ? 'water' : LINK_LAYERS.has(layer) && f.id != null && Number(f.id) % 10 === 0 ? 'merged' : 'source';
    return out;
  }
  /** The first feature (top first, as queryRenderedFeatures gives them) the inspector shows, described; null when there is none. */
  function topmost(fs) { for (const f of fs || []) { const d = describe(f); if (d) return d; } return null; }

  // ── The pop-up ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  const TYPE_LINE = { node: TK('OSM element: node {id}'), way: TK('OSM element: way {id}'), relation: TK('OSM element: relation {id}') };
  function credit() {
    const B = root.Core && root.Core.basemap, l = root.I18N && root.I18N.lang === 'en' ? 'en' : (root.I18N ? 'es' : 'en');
    return B ? B.SOURCES.osm.credit[l] : '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  }
  /** The pop-up's HTML for a description (null: nothing to show here). Names are OpenStreetMap's, shown as they are (translate="no"). */
  function html(d) {
    const rows = [];
    if (!d) rows.push(`<p class="osmi-none">${esc(T('Nothing to show here. Click a street, a place name or a point of interest.'))}</p>`);
    else {
      rows.push(`<div class="osmi-kind">${esc(T(d.kind))}${d.bridge ? ` <span class="osmi-sub">(${esc(T('bridge'))})</span>` : ''}</div>`);
      if (d.name) rows.push(`<div class="osmi-name" translate="no">${esc(d.name)}</div>`);
      if (d.ref) rows.push(`<div class="osmi-ref">${esc(d.exit ? T('Exit number: {ref}', { ref: d.ref }) : T('Road number: {ref}', { ref: d.ref }))}</div>`);
      if (d.why === 'sensitive') rows.push(`<p class="osmi-note">${esc(T('Name and link withheld: the observatory does not identify places of this kind.'))}</p>`);
      else if (d.osm) {
        rows.push(`<div class="osmi-el">${esc(T(TYPE_LINE[d.osm.type], { id: String(d.osm.id) }))}</div>`);
        rows.push(`<a class="osmi-link" href="${esc(d.osm.url)}" target="_blank" rel="noopener noreferrer" data-no-glossary>${esc(T('View on OpenStreetMap'))}<span class="sr-only"> ${esc(T('(opens in a new tab)'))}</span></a>`);
      } else rows.push(`<p class="osmi-note">${esc(d.why === 'merged' ? T('No link at this zoom: the map tiles join this feature with others. Zoom in and click again.') : d.why === 'water' ? T('No link: this water area is drawn from coastline data, not from one OpenStreetMap element.') : T('No link: the map tiles carry no OpenStreetMap ID for this feature.'))}</p>`);
    }
    rows.push(`<div class="osmi-credit">${credit()} · ODbL</div>`);
    return `<div class="osmi" data-layer="${d ? esc(d.layer) : ''}">${rows.join('')}</div>`;   // data-layer: the schema layer shown (tests/browser/osm_inspect.js)
  }

  // ── Reading the map ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  const isBase = (gl, srcId) => {
    const B = root.Core && root.Core.basemap, s = gl.getStyle && gl.getStyle().sources[srcId];
    return !!(s && s.type === 'vector' && B && B.isProvider(s.url || (s.tiles || [])[0]));
  };
  // A road's name and number are in transportation_name, drawn as labels along the line, so a click on the line seldom hits them; and a label line that was
  // merged at this zoom (ID ending 0) has no OSM ID, while the road's own line under it has one. One may lend to the other only when they are the same road
  // at the click (review of PR #99: the nearest line within 8 px was the cross street at 4 of 101 points): the candidate passes within ALONG px of the point
  // of the clicked line nearest the click, at a bearing within ANGLE degrees, every vertex of it within REACH px of that point lies within SIDE px of the
  // clicked line, and it is the only candidate that does (two distinct roads that fit: none lends). Otherwise no name is borrowed, and no link is shown.
  const ALONG = 2.5, ANGLE = 12, REACH = 40, SIDE = 3;
  function segDist(p, a, b) {
    const dx = b.x - a.x, dy = b.y - a.y, l = dx * dx + dy * dy, t = l ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / l)) : 0;
    return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
  }
  /** The nearest segment of `lines` (arrays of screen points) to `p`: { d, a, b, q } (q: the nearest point), or null. */
  function nearestSeg(p, lines) {
    let best = null;
    for (const l of lines) for (let i = 1; i < l.length; i++) {
      const a = l[i - 1], b = l[i], dx = b.x - a.x, dy = b.y - a.y, n = dx * dx + dy * dy, t = n ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / n)) : 0;
      const q = { x: a.x + t * dx, y: a.y + t * dy }, d = Math.hypot(p.x - q.x, p.y - q.y);
      if (!best || d < best.d) best = { d, a, b, q };
    }
    return best;
  }
  const bearing = (s) => Math.atan2(s.b.y - s.a.y, s.b.x - s.a.x);
  function angleDiff(s, t) { let d = Math.abs(bearing(s) - bearing(t)) % Math.PI; if (d > Math.PI / 2) d = Math.PI - d; return d * 180 / Math.PI; }   // undirected
  /**
   * Which of `cands` ([{ key, lines }], screen points) is the same line as `lines` at the click `p`: its key, or null when none or more than one distinct key fits
   * (the rule above). Pure: tested in Node (tests/osminspect.test.js).
   */
  function sameAlong(p, lines, cands) { const m = alongMatch(p, lines, cands); return m ? m.key : null; }
  /** sameAlong's match itself: { key, c }, `c` being the nearest candidate that fits (never another one that only shares its key, such as a second "Calle 1"), or null. */
  function alongMatch(p, lines, cands) {
    const s = nearestSeg(p, lines);
    if (!s || s.d > ALONG + SIDE) return null;
    const ref = s.q, keys = new Set();
    let best = null;
    for (const c of cands) {
      const t = nearestSeg(ref, c.lines);
      if (!t || t.d > ALONG || angleDiff(s, t) > ANGLE) continue;
      const near = c.lines.flat().filter(v => Math.hypot(v.x - ref.x, v.y - ref.y) <= REACH);
      if (near.some(v => { const u = nearestSeg(v, lines); return !u || u.d > SIDE; })) continue;
      keys.add(c.key);
      if (!best || t.d < best.d) best = { d: t.d, c };
    }
    return keys.size === 1 ? { key: best.c.key, c: best.c } : null;
  }
  const screenLines = (gl, geom) => (geom.type === 'LineString' ? [geom.coordinates] : geom.type === 'MultiLineString' ? geom.coordinates : []).map(l => l.map(c => gl.project(c)));
  /** The feature of `sourceLayer`, of the class of `f`, that is the same road as `f` at the click (sameAlong), or null. `key(g)` names a candidate (null: skip it). */
  function sameRoad(gl, pt, f, sourceLayer, key) {
    let fs = [];
    try { fs = gl.querySourceFeatures(f.source, { sourceLayer, filter: ['==', ['get', 'class'], f.properties.class] }); } catch (e) { return null; }
    const own = f.geometry ? screenLines(gl, f.geometry) : [];
    if (!own.length) return null;
    const cands = [];
    for (const g of fs) { const k = g.geometry && key(g); if (k != null) cands.push({ key: k, g, lines: screenLines(gl, g.geometry) }); }
    const m = alongMatch(pt, own, cands);
    return m ? m.c.g : null;
  }
  /** The features under a point of a MapLibre map, top first, from the base map's own vector source only (never the observatory's layers). */
  function query(gl, pt) {
    const r = 3, fs = gl.queryRenderedFeatures([[pt.x - r, pt.y - r], [pt.x + r, pt.y + r]]);
    return fs.filter(f => f.sourceLayer && isBase(gl, f.source));
  }
  /** What to show at a point: the topmost feature described, a road's name and number filled in from its label line. */
  function at(gl, pt) {
    const fs = query(gl, pt);
    for (const f of fs) {
      const d = describe(f);
      if (!d) continue;
      if (d.layer === 'transportation_name' && !d.osm) {   // a merged label line: the ID of the road's own line under it, when it is the same road (sameAlong)
        const r = sameRoad(gl, pt, f, 'transportation', g => (osmRef(g.id, 'transportation') && !g.properties.ramp ? g.id : null));
        if (r) { d.osm = osmRef(r.id, 'transportation'); d.why = null; }
      }
      if (d.layer === 'transportation' && (!d.name || !d.osm)) {   // a road's line: the name and number of its label line, when it is the same road; never a merged label's ID
        const n = sameRoad(gl, pt, f, 'transportation_name', g => nameOf(g.properties));
        if (n) {
          d.name = d.name || nameOf(n.properties); d.ref = d.ref || (typeof n.properties.ref === 'string' && n.properties.ref.trim()) || null;
          if (!d.osm) { const o = osmRef(n.id, 'transportation_name'); if (o) { d.osm = o; d.why = null; } }
        }
      }
      return d;
    }
    return null;
  }

  // ── The mode: a toggle, a bar over the map (under the layers chip; a message or a notice may cover it for a moment), Esc, the pop-up ─────────────────────────────────────────────────────────────────────────────────────
  let styled = false;
  function addStyle() {
    if (styled || !root.document) return; styled = true;
    const s = root.document.createElement('style');
    s.textContent = `.osmi-btn[aria-pressed="true"]{background:var(--color-primary,#205D7B);color:#fff;border-color:var(--color-primary,#205D7B)}`
      + `.osmi-on,.osmi-on .leaflet-interactive,.osmi-on .maplibregl-canvas,.osmi-on .leaflet-grab{cursor:crosshair!important}`
      + `.osmi-bar{position:absolute;top:56px;left:8px;right:8px;margin:0 auto;width:fit-content;max-width:440px;z-index:850;box-sizing:border-box;display:flex;gap:8px;align-items:center;padding:6px 6px 6px 12px;background:#0f3b52;color:#fff;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.25);font-size:12.5px;line-height:1.35}`
      + `.osmi-bar button{flex:none;border:1px solid rgba(255,255,255,.6);background:transparent;color:#fff;border-radius:4px;font:inherit;font-weight:600;padding:3px 10px;cursor:pointer}`
      + `.osmi-bar button:focus-visible{outline:2px solid #fff;outline-offset:2px}`
      + `.osmi{font-size:13px;line-height:1.4;max-width:260px}.osmi-kind{font-weight:600;color:#0f3b52}.osmi-sub{font-weight:400;color:#4a5560}.osmi-name{font-size:14px;margin-top:2px}`
      + `.osmi-ref,.osmi-el{color:#4a5560;font-size:12px;margin-top:2px}.osmi-link{display:inline-block;margin-top:6px;font-weight:600}.osmi-note,.osmi-none{margin:6px 0 0;color:#4a5560;font-size:12px}`
      + `.osmi-credit{margin-top:8px;padding-top:6px;border-top:1px solid #e3e8ec;color:#4a5560;font-size:11px}`;
    root.document.head.appendChild(s);
  }

  /**
   * The inspect mode of one map. o: { container (the map's element), button (the toggle), gl() (the MapLibre map, or null when there is no base map),
   * popup(lngLat, html) (opens the pop-up; null closes it), lngLatAt(point) / pointOf(event) (2D only: Leaflet coordinates), listen(on) (the page wires or unwires
   * its click: 2D captures the clicks before Leaflet's layers; 3D's own click handler steps aside while data-inspect is on) }. Returns { on, off, toggle, click, active }.
   */
  function mode(o) {
    addStyle();
    const el = o.container, btn = o.button;
    let active = false, bar = null;
    // a control the viewer can reach: drawn, and not in an inert part of the page (on a phone the closed panel is inert, though still drawn off screen)
    const shown = (b) => !!(b && b.getClientRects().length && b.offsetParent && !b.closest('[inert]'));
    const back = () => {   // where the focus goes when the mode ends: the toggle; on a phone, where it is in the closed panel, the menu button that opens the panel
      const m = root.document.getElementById('menuBtn');
      if (shown(btn)) btn.focus({ preventScroll: true }); else if (shown(m)) m.focus({ preventScroll: true });
    };
    const key = (e) => { if (e.key === 'Escape' && active) { off(); back(); } };
    function on() {
      if (active || !o.gl()) return;
      active = true; el.classList.add('osmi-on'); el.dataset.inspect = 'on';
      if (btn) btn.setAttribute('aria-pressed', 'true');
      bar = root.document.createElement('div'); bar.className = 'osmi-bar'; bar.setAttribute('data-no-glossary', '');
      bar.innerHTML = `<span role="status">${esc(T('Inspect mode: click a street or place on the base map. Esc to leave.'))}</span><button type="button">${esc(T('Leave'))}</button>`;
      bar.querySelector('button').onclick = () => { off(); back(); };
      ['click', 'mousedown', 'pointerdown', 'dblclick', 'touchstart'].forEach(t => bar.addEventListener(t, e => e.stopPropagation()));
      el.appendChild(bar);
      root.document.addEventListener('keydown', key);
      if (o.listen) o.listen(true);
      if (typeof isMobile === 'function' && isMobile() && typeof setPanel === 'function') setPanel(false);   // common.js: on a phone the panel would cover the map
      if (!shown(btn)) bar.querySelector('button').focus({ preventScroll: true });   // the toggle is hidden now: the focus goes to a visible control (review of PR #99)
    }
    function off() {
      if (!active) return;
      active = false; el.classList.remove('osmi-on'); delete el.dataset.inspect;
      if (btn) btn.setAttribute('aria-pressed', 'false');
      if (bar) { bar.remove(); bar = null; }
      root.document.removeEventListener('keydown', key);
      if (o.listen) o.listen(false);
      o.popup(null);
    }
    /** A click at `lngLat` (and the MapLibre point `pt`): the pop-up for what is there. */
    function click(lngLat, pt) {
      const gl = o.gl();
      if (!active || !gl) return null;
      let d = null;
      try { d = at(gl, pt || gl.project(lngLat)); } catch (e) { d = null; }
      o.popup(lngLat, html(d));
      return d;
    }
    return { on, off, toggle: () => (active ? off() : on()), click, get active() { return active; } };
  }

  /** The 2D map (Leaflet, with the base map of core/basemap.js as the handle `bm()`): clicks are taken before the observatory's layers while the mode is on. */
  function leaflet(map, bm, btn) {
    const L = root.L, el = map.getContainer();
    let pop = null, down = null;
    const gl = () => { const h = bm(); return h && h.state === 'on' && h.layer && h.layer.getMaplibreMap ? h.layer.getMaplibreMap() : null; };
    // Only clicks on the map itself (Leaflet's map pane: the base map, the observatory's shapes and markers), never on what sits over it in the container
    // (the layers chip and its list, messages and their Undo, legends, notices, controls) nor on a pop-up (review of PR #99). Keys are never caught.
    const mine = (t) => !!(t && t.closest && t.closest('.leaflet-map-pane') && !t.closest('.leaflet-popup'));
    const onDown = (e) => { down = mine(e.target) ? [e.clientX, e.clientY] : null; };
    const onClick = (e) => {
      if (!mine(e.target)) return;
      e.stopPropagation(); e.preventDefault();
      const moved = down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5; down = null;
      if (moved) return;   // the end of a drag
      const ll = map.mouseEventToLatLng(e), g = gl();
      if (g) m.click({ lng: ll.lng, lat: ll.lat }, g.project([ll.lng, ll.lat]));
    };
    const m = mode({
      container: el, button: btn, gl,
      popup: (ll, h) => {
        if (pop) { map.closePopup(pop); pop = null; }
        if (h) pop = L.popup({ maxWidth: 280, className: 'osmi-popup', autoPanPadding: [16, 16] }).setLatLng([ll.lat, ll.lng]).setContent(h).openOn(map);
      },
      listen: (on) => {
        const f = on ? 'addEventListener' : 'removeEventListener';
        el[f]('pointerdown', onDown, true); el[f]('click', onClick, true);
      },
    });
    return m;
  }

  /** The 3D view (MapLibre): its click handler steps aside while the container has data-inspect="on"; this one answers. */
  function maplibre(map, btn, baseOn) {
    let pop = null;
    const m = mode({
      container: map.getContainer(), button: btn, gl: () => (baseOn() ? map : null),
      popup: (ll, h) => {
        if (pop) { pop.remove(); pop = null; }
        if (h) pop = new root.maplibregl.Popup({ maxWidth: '280px', className: 'osmi-popup' }).setLngLat([ll.lng, ll.lat]).setHTML(h).addTo(map);
      },
    });
    map.on('click', (e) => { if (m.active) m.click(e.lngLat, e.point); });
    return m;
  }

  return { SHOWN, LINK_LAYERS, SENSITIVE, PUBLIC_OFFICE, osmRef, sensitive, kindOf, describe, topmost, html, segDist, sameAlong, alongMatch, mode, leaflet, maplibre, at };
});
