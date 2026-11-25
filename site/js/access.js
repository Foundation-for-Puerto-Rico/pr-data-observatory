/* PR Data Observatory: how close each tourism place is to a stop with a current timetable (map and 3D pages), and the pop-ups both pages show: a transit feature
   (transportPopup), a barrio (barrioPopup) and the card of a click on areas (areasPopup, with the sections of the flood zones, protected areas, land use and
   Comunidades Especiales). Needs common.js and icons.js. */

// ── Access of tourism places to transport (access.py; docs/visitor-transport-access-2026-10.md) ──
// place_access.json holds one value per place, in the order of places.json: ts_m (meters, straight line, to the nearest stop with a current timetable),
// ts_calls (weekday departures at the busiest such stop within 400 m; 0 = none) and ts_we (1 = Saturday, 2 = Sunday service at those stops),
// and the same three by walking along mapped roads: tw_m (99,999 past walk_bound_m), tw_calls, tw_we, with tw_straight listing the places that have no
// mapped road within 150 m and keep their straight-line values (walknet.py). The classes use walking when the file has it. Everything is schedule-based:
// no real-time data, and públicos, taxis and ride-hailing are in no timetable. The road map has no footpaths, so a walk is an estimate.
const ACCESS = { near: 400, far: 800, frequent: 20, bound: 1000 };
// places_privacy.py: a withheld place (a home, a holiday rental, housing, an address, a care service) has no name or point; it is counted, never drawn or listed
const placeDrawn = p => p.lat != null && p.lng != null && !p.withheld;
const fetchAccess = () => fetchJson('data/place_access.json').catch(() => null);
function attachAccess(places, access, meta) {   // joins the columns to the places; null (and the old "any mapped stop" badge) when the two files do not belong together
  const ok = access && access.n === places.length && (!meta || !meta.generated_at || access.built === meta.generated_at);
  if (access && !ok) console.warn('place_access.json does not match places.json; the access profile is not shown.');
  if (!ok) return null;
  places.forEach((p, i) => { p.ts_m = access.ts_m[i]; p.ts_calls = access.ts_calls[i]; p.ts_we = access.ts_we[i]; });
  if (Array.isArray(access.tw_m) && access.tw_m.length === places.length) {   // walking along mapped roads (an older file has none: the straight line stays)
    places.forEach((p, i) => { p.tw_m = access.tw_m[i]; p.tw_calls = access.tw_calls[i]; p.tw_we = access.tw_we[i]; });
    (access.tw_straight || []).forEach(i => { if (places[i]) places[i].tw_straight = true; });
    if (access.walk_bound_m) ACCESS.bound = access.walk_bound_m;
  }
  return access;
}
const distText = (m) => m < 1000 ? m + ' m' : (m / 1000).toFixed(1) + ' km';
const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const walkM = p => p.tw_m ?? p.ts_m;   // the distance the classes and shares use: walking when published, else the straight line
const walkCalls = p => p.tw_m != null ? p.tw_calls : p.ts_calls;
const walkWe = p => p.tw_m != null ? p.tw_we : p.ts_we;
function accessClass(p) {   // the same rule as access.py access_class(), on the walking fields when the file has them
  if (p.ts_m == null) return null;
  const m = walkM(p);
  if (m <= ACCESS.near) return walkCalls(p) >= ACCESS.frequent ? 'frequent' : 'basic';
  if (m <= ACCESS.far) return 'near';
  if (p.tw_m != null && p.ts_m <= ACCESS.far) return 'detour';   // a current stop close in a straight line but more than 800 m on foot (access.py: straight_m)
  return p.transit_m != null && p.transit_m < ACCESS.far ? 'paper' : 'none';   // transit_m is cut to whole meters: 800.x m reads 800 and is outside 800 m (access.py: any_m <= 800 on the exact distance)
}
const ACCESS_CLASS = () => ({   // words and an icon on every badge: color alone never carries the class
  frequent: { label: T('Frequent stop within 400 m'), icon: 'directions_bus', tone: 'prot' },
  basic: { label: T('Stop within 400 m'), icon: 'directions_bus', tone: 'prot' },
  near: { label: T('Stop 400–800 m away'), icon: 'directions_bus', tone: 'conf' },
  detour: { label: T('Stop within 800 m in a straight line, more than 800 m on foot'), icon: 'hiking', tone: 'conf' },
  paper: { label: T('Only expired or unscheduled stops within 800 m'), icon: 'warning', tone: 'low' },
  none: { label: T('No stop within 800 m'), icon: 'cancel', tone: 'conf' },
});
// The access block of a place pop-up: a badge (the class) and two lines. Without the access file only the old measure is shown, labeled as what it is.
function accessPopup(p) {
  const any = p.transit_m != null ? T('Any mapped stop (expired timetables and volunteer-mapped stops included): {distance}', { distance: distText(p.transit_m) }) : '';
  const cls = accessClass(p);
  if (!cls) {
    return { badge: p.transit_m == null ? '' : `<span class="badge ${p.transit_400m ? 'prot' : 'conf'}" title="${esc(p.nearest_stop || '')}">${icon('directions_bus', { size: 14 })}${esc(T('any mapped stop {distance}', { distance: distText(p.transit_m) }))}</span>`, lines: '' };
  }
  const c = ACCESS_CLASS()[cls];
  const straight = distText(p.ts_m);
  let first = p.tw_m == null ? T('Nearest stop with a current timetable: {distance}', { distance: straight })
    : p.tw_straight ? T('Nearest stop with a current timetable: {distance} in a straight line (no mapped road within 150 m of the place)', { distance: straight })
    : p.tw_m > ACCESS.bound ? T('Nearest stop with a current timetable: more than {distance} walking along mapped roads ({straight} in a straight line)', { distance: distText(ACCESS.bound), straight })
    : T('Nearest stop with a current timetable: {distance} walking along mapped roads ({straight} in a straight line)', { distance: distText(p.tw_m), straight });
  if (walkM(p) <= ACCESS.near) {
    const we = walkWe(p), calls = walkCalls(p);
    const weekend = we === 3 ? T('Saturday and Sunday service') : we === 1 ? T('Saturday service') : we === 2 ? T('Sunday service') : T('no weekend service in the published timetable');
    first += ` · ${Tn(calls, '{n} weekday departure', '{n} weekday departures', { n: fmt(calls) })} · ${weekend}`;
  }
  const title = esc(p.tw_m == null ? T('Schedule-based, straight line. A stop counts when its timetable has not ended; “frequent” means 20 or more departures on a typical weekday. Real-time service, walking distance, públicos and taxis are not included.')
    : T('Schedule-based. Distances are walked along mapped roads, which leave out footpaths, sidewalks, steps and crossings, so they are an estimate; a straight line is used where the place has no mapped road nearby. A stop counts when its timetable has not ended; “frequent” means 20 or more departures on a typical weekday. Real-time service, públicos and taxis are not included.'));
  const closer = p.transit_m != null && p.transit_m + 1 < p.ts_m;   // the any-mapped-stop line only when a stop without a current timetable is closer (ts_m is rounded up, transit_m cut, so one meter is the same stop)
  return { badge: `<span class="badge wrap ${c.tone}" title="${title}">${icon(c.icon, { size: 14 })}${esc(c.label)}</span>`,
           lines: `<div class="meta">${esc(first)}</div>${closer ? `<div class="meta" title="${esc(p.nearest_stop || '')}">${esc(any)}</div>` : ''}` };
}

// ── Transit features and barrios: the same pop-up on the 2D map and the 3D view (docs/layers.md) ──
// transport.json holds every stop, station, terminal, airport, taxi stand and EV charger: its kind sets the layer (stations, stops, taxi stands and EV charging).
const KIND = {
  transit_stop:   { label: T('Transit stop (ATI)'), icon: 'directions_bus', color: '#205D7B' },
  bus_stop:       { label: T('Bus stop (OSM)'), icon: 'directions_bus', color: '#5FAFDA' },
  bus_station:    { label: T('Bus station / terminal'), icon: 'transfer_within_a_station', color: '#2A2E2E' },
  rail_station:   { label: T('Tren Urbano station'), icon: 'subway', color: '#B82415' },
  ferry_terminal: { label: T('Ferry terminal'), icon: 'directions_boat', color: '#338CB3' },
  airport:        { label: T('Airport'), icon: 'flight', color: '#2A2E2E' },
  helipad:        { label: T('Helipad'), icon: 'flight', color: '#666666' },
  taxi:           { label: T('Taxi stand'), icon: 'local_taxi', color: '#B56D00' },
  bike_rental:    { label: T('Bike rental'), icon: 'commute', color: '#79901E' },
  ev_charging:    { label: T('EV charging'), icon: 'ev_station', color: '#79901E' },
};
const HUB_KINDS = ['bus_station', 'rail_station', 'ferry_terminal', 'airport'];
const STOP_KINDS = ['transit_stop', 'bus_stop'];
const TAXI_KINDS = ['taxi', 'ev_charging', 'bike_rental', 'helipad'];

function transportPopup(f) {
  const k = KIND[f.kind] || { label: f.kind, icon: 'place', color: '#666' };
  const rows = [];
  if (f.routes && f.routes.length) rows.push(`<div class="meta">${Th('<b>Routes:</b> {routes}', { routes: f.routes.join(', ') })}</div>`);
  if (f.modes && f.modes.length) rows.push(`<div class="meta">${f.modes.map(m => `<span class="badge conf">${icon(m === 'rail' ? 'subway' : m === 'ferry' ? 'directions_boat' : 'directions_bus', { size: 13 })}${esc(({ bus: T('bus'), rail: T('rail'), ferry: T('ferry') })[m] || m)}</span>`).join(' ')}</div>`);
  if (f.trips_weekday) rows.push(`<div class="meta">${Tn(f.trips_weekday, '<b>{n}</b> weekday departure', '<b>{n}</b> weekday departures', { n: fmt(f.trips_weekday) })}</div>`);
  if (f.feed_end) {   // a scheduled stop: weekend departures (none in the feed when the field is missing) and whether its timetable still covers today
    rows.push(`<div class="meta">${esc(f.calls_sat || f.calls_sun ? T('Weekend departures: Saturday {sat} · Sunday {sun}', { sat: f.calls_sat ? fmt(f.calls_sat) : T('none listed'), sun: f.calls_sun ? fmt(f.calls_sun) : T('none listed') }) : T('No weekend departures in the published timetable'))}</div>`);
    const over = f.feed_end < todayISO();
    rows.push(`<div class="meta">${over ? icon('warning', { size: 13, color: '#B56D00' }) + ' ' : ''}${esc(over ? T('Timetable ended {date}', { date: I18N.date(f.feed_end) }) : T('Timetable valid until {date}', { date: I18N.date(f.feed_end) }))}</div>`);
  }
  if (f.operator_name || f.operator) rows.push(`<div class="meta">${esc(T('Operator: {name}', { name: f.operator_name || f.operator }))}</div>`);
  if (f.kind === 'airport') rows.push(`<div class="meta">${esc(f.public_use === false ? T('Private use') : T('Public use'))}${f.code ? ` · ${esc(f.code)}` : ''}${f.iata ? ` · ${esc(f.iata)}` : ''}</div>`);
  if (f.wheelchair) rows.push(`<div class="meta">${icon('check_circle', { size: 13, color: '#79901E' })} ${esc(T('wheelchair accessible'))}</div>`);
  const src = { ati_gtfs: T('ATI GTFS open data'), muni_gtfs: T('Municipal GTFS feed (National RTAP portal)'), osm_transport: T('© OpenStreetMap contributors'), faa_airports: 'FAA / BTS NTAD' }[f.source] || f.source;
  return `<div class="pop"><h4><span class="type-icon" style="width:28px;height:28px;background:${k.color};color:#fff">${icon(k.icon, { size: 17 })}</span><span>${esc(f.name || k.label)}</span></h4><div class="meta">${esc(k.label)} · ${esc(f.municipality || '')}</div>${rows.join('')}<div class="src">${esc(src)}</div></div>`;
}

function barrioPopup(p, wrap = true) {
  const body = `<h4>${icon('location_city', { size: 20, color: '#205D7B' })}Barrio ${esc(p.barrio)}</h4><div class="meta">${esc(p.municipality)} · ${fmt(p.km2, 1)} km²</div><div class="meta">${Th('<b>{assets}</b> tourism places ({density} per km²) · <b>{sfha}</b> in flood hazard area', { assets: fmt(p.assets), density: fmt(p.assets_per_km2, 1), sfha: fmt(p.sfha) })}</div><div class="meta">${p.acc_walk400 != null ? Th('<b>{walk}</b> within a 400 m walk of a stop with a current timetable (<b>{freq}</b> frequent) · <b>{cur}</b> within 400 m in a straight line · <b>{transit}</b> within 400 m of any mapped stop', { walk: fmt(p.acc_walk400), freq: fmt(p.acc_wfreq400), cur: fmt(p.acc_cur400), transit: fmt(p.transit) }) : p.acc_cur400 != null ? Th('<b>{cur}</b> within 400 m of a stop with a current timetable (<b>{freq}</b> frequent) · <b>{transit}</b> within 400 m of any mapped stop', { cur: fmt(p.acc_cur400), freq: fmt(p.acc_freq400), transit: fmt(p.transit) }) : Th('<b>{transit}</b> within 400 m of any mapped stop', { transit: fmt(p.transit) })}</div><div class="src">${esc(T('Barrio boundaries: US Census Bureau county subdivisions (2020)'))}</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}

// ── The areas under a click: one card with a section for each, the same on the 2D map (app.js) and the 3D view (twin3d.js; docs/layers.md, "Clicks") ──
// PAD-US coded fields, spelled out for the card (USGS PAD-US data dictionary)
const PAD = {
  Des_Tp: { NP: T('National Park'), NF: T('National Forest'), NWR: T('National Wildlife Refuge'), SP: T('State Park'), SF: T('State Forest'), SW: T('State Wildlife Area'), LP: T('Local Park'), LCA: T('Local Conservation Area'), LREC: T('Local Recreation Area'), PUB: T('Public Land'), PROC: T('Proclamation'), MPA: T('Marine Protected Area'), RNA: T('Research Natural Area'), WA: T('Wilderness Area'), ACEC: T('Area of Critical Environmental Concern'), CONE: T('Conservation Easement'), PCON: T('Private Conservation'), UNK: T('Other protected area'), OTHF: T('Other federal'), OTHS: T('Other state'), OTHL: T('Other local'), REC: T('Recreation Management Area'), ECA: T('Ecological Conservation Area') },
  Pub_Access: { OA: T('open access'), RA: T('restricted access'), XA: T('closed'), UK: T('unknown') },
  GAP_Sts: { '1': T('GAP 1 (strict nature reserve)'), '2': T('GAP 2 (managed for biodiversity)'), '3': T('GAP 3 (multiple use, some extraction)'), '4': T('GAP 4 (no known biodiversity mandate)') },
};
const padTxt = (field, v) => (PAD[field] || {})[String(v)] || (v ? String(v) : T('not reported'));
function floodPopup(p, wrap = true) {
  const z = p.FLD_ZONE, sub = p.ZONE_SUBTY ? ` · ${esc(T(humanize(String(p.ZONE_SUBTY).toLowerCase())))}` : '';   // FEMA zone subtypes: '0.2 pct annual chance flood hazard', 'Area of minimal flood hazard', 'Floodway', 'Riverine floodway shown in coastal zone'
  const body = `<h4>${icon('flood', { size: 20, color: '#1F5F8B' })}${esc(T('Flood zone {zone}', { zone: z }))}</h4><div class="meta">${esc(p.SFHA_TF === 'T' ? T('Special flood hazard area: 1% annual chance (100-year) flood') : z === 'X' ? T('0.2% annual chance (500-year) flood, or reduced risk') : T('See FEMA zone definitions'))}${sub}</div><div class="src">${esc(T('FEMA National Flood Hazard Layer'))}</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}
function protPopup(p, wrap = true) {
  const body = `<h4>${icon('shield', { size: 20, color: '#47560F' })}${esc(p.Unit_Nm)}</h4><div class="meta">${esc(T('{type} · managed by {manager}', { type: padTxt('Des_Tp', p.Des_Tp), manager: p.Mang_Name || T('not reported') }))}</div><div class="meta">${esc(T('Public access: {access} · {acres} acres · {gap}', { access: padTxt('Pub_Access', p.Pub_Access), acres: fmt(p.GIS_Acres), gap: padTxt('GAP_Sts', p.GAP_Sts) }))}</div><div class="src">${esc(T('USGS Protected Areas Database (PAD-US 4.1)'))}</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}
function landusePopup(p, wrap = true) {
  const body = `<h4>${icon('landscape', { size: 20, color: p.color })}${esc(p.label)}</h4><div class="meta">${esc(p.cls)} · ${esc(p.municipio || '')}</div><div class="src">Junta de Planificación, Plan de Uso de Terrenos 2015</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}
function comunidadPopup(p, wrap = true) {
  const yn = v => v == null ? T('not reported') : v ? T('yes') : T('no');
  const body = `<h4>${icon('groups', { size: 20, color: '#FF4D38' })}${esc(p.nombre)}</h4><div class="meta">Comunidad Especial · ${esc(p.municipio)}${p.barrio ? ` · Barrio ${esc(p.barrio)}` : ''}</div><div class="meta">${Th('<b>{n}</b> housing units · {km2} km²{type}', { n: fmt(p.viviendas), km2: fmt(p.km2, 2), type: p.tipo ? ` · ${p.tipo}` : '' })}</div><div class="meta">${Th('<b>{pct}%</b> of its area ({km2} km²) in a FEMA flood hazard area', { pct: fmt(p.sfha_pct, 1), km2: fmt(p.sfha_km2, 3) })}</div><div class="meta">${esc(T('Reported in the 2006 inventory: flooding {flood} · landslides {slide}', { flood: yn(p.inundable), slide: yn(p.deslizamiento) }))}</div><div class="src">${esc(T('Junta de Planificación, delimitation of Comunidades Especiales (Ley 1-2001), 2006'))}</div>`;
  return wrap ? `<div class="pop">${body}</div>` : `<div class="id-sec">${body}</div>`;
}
/** The card of a click on areas: their sections (built with wrap = false), then a link to the profile of the municipality under the click (name), when there is one. */
function areasPopup(sections, name) {
  const open = name ? `<div class="links"><button type="button" class="linklike" id="idOpenMuni">${esc(T('Open the {name} profile', { name }))}</button></div>` : '';
  return `<div class="pop">${sections.join('')}${open}</div>`;
}
