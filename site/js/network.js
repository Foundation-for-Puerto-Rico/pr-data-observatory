/* PR Data Observatory — transit network panel for the 2D map.
   Operators and the state of their public data, what is live and what is not, vehicles on their timetable right now,
   planning layers (service gaps, integration points) and the route planner (names, roads, scoring: see plan.js).
   Loaded after app.js and uses its globals (map, S, getJson, featuresAt, toast, ...). */

const NET = { ops: [], opById: {}, live: null, coverage: {}, transfers: [], blocks: null, trips: {}, hl: null, gapLayer: null, xferLayer: null, nowLayer: null, nowTimer: null };

const TYPE_COLOR = { regional: '#205D7B', ama: '#205D7B', municipal: '#607316', community: '#B56D00', publico: '#B56D00', ferry: '#338CB3' };
const STATUS = {   // [label, css class]: the label is an English key, shown through T() where it reaches the screen
  current: ['Current', 'ok'], expiring: ['Expires soon', 'warn'], expired: ['Expired', 'bad'], none: ['No public feed', 'none'],
  in_ati: ['In the ATI feed', 'info'], community: ['Community-mapped', 'info'], broken: ['Feed error', 'bad'], unknown: ['Dates unknown', 'none'],
};
const LIVE_BADGE = { 'not published': 'bad', 'app only': 'warn', 'private feed': 'warn', 'none found': 'bad', 'available, needs a relay': 'info' };
const prToday = () => new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Puerto_Rico' }));
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
// Days in the operator data are ISO text (2026-12-31). English shows them as written; Spanish spells the date out (31 de diciembre de 2026).
const dayText = (s) => I18N.lang !== 'en' && /^\d{4}-\d{2}-\d{2}$/.test(s || '') ? I18N.date(new Date(s + 'T00:00:00')) : (s || '');

// the state of a feed is worked out from its end date each time the page opens, so an old build never says "current" for an expired feed
function opStatus(o) {
  const f = o.feed || {};
  if (f.status !== 'current' && f.status !== 'expiring' && f.status !== 'expired') return f.status || 'none';
  if (!f.end) return 'unknown';
  const days = (new Date(f.end + 'T00:00:00') - new Date(isoDay(prToday()) + 'T00:00:00')) / 864e5;
  return days < 0 ? 'expired' : days <= 60 ? 'expiring' : 'current';
}
const opColor = (o) => TYPE_COLOR[o.type] || '#666';
const hms = (s) => s == null ? '' : `${String(Math.floor(s / 3600) % 24).padStart(2, '0')}:${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}`;

// ── Route drawing (used by app.js loadRoutes) ────────────────────────────────
function routeColor(p) {
  if (p.mode === 'rail') return '#B82415';
  if (p.mode === 'ferry') return '#338CB3';
  if (p.operator === 'osm') return '#B56D00';
  return p.operator === 'ati' ? '#205D7B' : '#607316';
}
function routeStyle(f) {
  const p = f.properties, dim = NET.hl && p.operator !== NET.hl;
  const w = Math.min(7, 2 + Math.log2(1 + (p.trips_weekday || 0)) * .7);
  const base = { color: routeColor(p), opacity: dim ? .12 : p.operator === 'osm' ? .8 : .85, weight: p.mode === 'rail' ? w + 1 : p.operator === 'osm' ? 2.5 : p.mode === 'ferry' ? 3 : w };
  if (p.mode === 'ferry') base.dashArray = '6 6';
  else if (p.geometry_source === 'stops') { base.dashArray = '1 6'; base.weight = Math.max(base.weight, 3); base.lineCap = 'round'; }          // no road path found: straight between the stops
  else if (p.geometry_source === 'roads_inferred') { base.dashArray = '8 5'; if (!dim) base.opacity = .6; }                                  // the feed lists the stops out of order: visit order inferred
  else if (p.operator === 'osm') base.dashArray = '10 5';
  return base;
}
// The build writes the note on a route whose stop order had to be inferred in English, with two variable parts: say it in the page language (any other note is shown as written).
function orderNote(n) {
  const m = /^The feed lists this route's stops (alphabetically|out of travel order) \(zig-zag ratio ([^)]+)\), so the order of visit is inferred and its times are not usable\.$/.exec(n || '');
  if (!m) return n || '';
  return m[1] === 'alphabetically'
    ? T("The feed lists this route's stops alphabetically (zig-zag ratio {ratio}), so the order of visit is inferred and its times are not usable.", { ratio: m[2] })
    : T("The feed lists this route's stops out of travel order (zig-zag ratio {ratio}), so the order of visit is inferred and its times are not usable.", { ratio: m[2] });
}
function routePopup(p) {
  const o = NET.opById[p.operator] || {}, st = opStatus(o), f = o.feed || {};
  const geo = { roads: T('The feed has no route shape, so the line follows the road network between the stops (OpenStreetMap roads); the exact street may differ.'), roads_inferred: p.order_note ? orderNote(p.order_note) : T('The order of the stops is inferred.'), stops: T('Approximate alignment: no road path was found, so the line joins the stops in order.'), osm: T('Mapped by volunteers in OpenStreetMap; incomplete and unscheduled.'), shape: T("Alignment from the operator's route shape.") }[p.geometry_source] || '';
  const trips = p.operator === 'osm' ? `<div class="meta">${esc(T('No timetable published for this route.'))}</div>` : `<div class="meta"><b>${fmt(p.trips_weekday)}</b> ${esc(Tn(p.trips_weekday, 'weekday trip', 'weekday trips'))} · ${esc(T('{n} Saturday', { n: fmt(p.trips_saturday) }))} · ${esc(T('{n} Sunday', { n: fmt(p.trips_sunday) }))}${p.first != null ? `<br>${esc(T('First departure {first}, last {last} (weekday)', { first: hms(p.first), last: hms(p.last) }))}` : ''}</div>`;
  return `<div class="pop"><h4>${icon(p.mode === 'rail' ? 'subway' : p.mode === 'ferry' ? 'directions_boat' : 'directions_bus', { size: 20, color: routeColor(p) })}<span>${esc(p.short_name)} ${esc(p.long_name)}</span></h4>
    <div class="meta">${esc(p.operator_name || p.agency || '')}${p.network ? ` · ${esc(p.network)}` : ''}</div>${trips}
    ${geo ? `<div class="meta">${esc(geo)}</div>` : ''}
    <div class="meta"><span class="pill ${(STATUS[st] || STATUS.none)[1]}">${esc(T((STATUS[st] || STATUS.none)[0]))}</span>${f.end ? ` ${esc(T('timetable valid {start} to {end}', { start: dayText(f.start), end: dayText(f.end) }))}` : ''}</div>
    <div class="src">${esc(p.operator === 'osm' ? T('© OpenStreetMap contributors') : p.operator === 'ati' ? T('ATI GTFS open data') : T('Municipal GTFS feed (National RTAP portal)'))}</div></div>`;
}
function restyleRoutes() { if (typeof routesLayer !== 'undefined' && routesLayer) routesLayer.setStyle(routeStyle); }

// ── Panel ────────────────────────────────────────────────────────────────────
function renderNetSummary() {
  const ops = NET.ops, by = {}; ops.forEach(o => { const s = opStatus(o); by[s] = (by[s] || 0) + 1; });
  const withFeed = ops.filter(o => ['current', 'expiring', 'expired'].includes(opStatus(o))).length;
  const cov = Object.values(NET.coverage), pop = cov.reduce((a, c) => a + c.pop, 0), walk = cov.some(c => c.walk_served != null);   // walking along mapped roads when published, else the straight line
  const served = cov.reduce((a, c) => a + (walk ? c.walk_served : c.served), 0), active = cov.reduce((a, c) => a + ((walk ? c.walk_served_active : c.served_active) || 0), 0);
  const routes = (S.meta.network || {}).routes;
  const pct = pop ? fmt(served / pop * 100) : '—';   // one line of the four figures, above the operator list; what each counts in the fold under it
  $('#netSummary').innerHTML = `<div class="note">${Th('<b>{a}</b> operators with a schedule · <b>{b}</b> with no public data · <b>{c}</b> routes · <b>{d}%</b> of residents within 400 m of a scheduled stop', { a: fmt(withFeed), b: fmt(by.none || 0), c: fmt(routes), d: pct })}</div>
    <details class="about-d"><summary>${esc(T('What these figures count'))}</summary><div class="kpis">
      <div class="kpi"><div class="v">${fmt(withFeed)}</div><div class="l">${esc(Tn(withFeed, 'operator publishes a schedule ({current} current, {expiring} expiring, {expired} expired)', 'operators publish a schedule ({current} current, {expiring} expiring, {expired} expired)', { current: by.current || 0, expiring: by.expiring || 0, expired: by.expired || 0 }))}</div></div>
      <div class="kpi ${by.none ? 'warn' : ''}"><div class="v">${fmt(by.none || 0)}</div><div class="l">${esc(Tn(by.none || 0, 'operator with no public schedule data', 'operators with no public schedule data'))}</div></div>
      <div class="kpi"><div class="v">${fmt(routes)}</div><div class="l">${esc(Tn(routes, 'route on the map', 'routes on the map'))}</div></div>
      <div class="kpi"><div class="v">${pct}%</div><div class="l">${esc(walk ? T('of residents live within a 400 m walk of a scheduled stop, along mapped roads ({pct}% counting only current timetables)', { pct: pop ? fmt(active / pop * 100) : '—' }) : T('of residents live within 400 m of a scheduled stop ({pct}% counting only current timetables)', { pct: pop ? fmt(active / pop * 100) : '—' }))}</div></div>
    </div>
    <div class="note">${esc(T('Every operator that reports to the federal transit database is listed below, with the state of its public data as of the build date ({built}). Where a feed has no route shape, the line follows the roads between its stops; dashed lines mark routes whose stop order had to be inferred.', { built: dayText((S.meta.network || {}).built) }))}</div></details>`;
}
function renderLiveStatus() {
  const live = NET.live; if (!live) return;
  // the name, status and detail of each source come from the build (network.py LIVE_SOURCES) in English: they reach the screen through T() and are listed under data_labels in i18n_src/pages.json
  $('#liveStatus').innerHTML = `<div class="note">${Th('<b>Real-time bus positions are not available to the public.</b> Checked {date}. What exists:', { date: dayText(live.checked) })}</div>` +
    live.sources.map(s => `<div class="live-row"><span class="pill ${LIVE_BADGE[s.status] || 'none'}">${esc(humanize(T(s.status)))}</span><div><b>${esc(T(s.name))}</b><small>${esc(T(s.detail))}${s.url ? ` <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(T('source'))}</a>` : ''}</small></div></div>`).join('');
}
function renderOpList() {
  const filt = $('#opFilter').value;
  const rows = NET.ops.filter(o => { const s = opStatus(o); return filt === 'all' || (filt === 'data' && ['current', 'expiring', 'expired', 'community'].includes(s)) || (filt === 'nodata' && s === 'none') || (filt === 'attention' && ['expired', 'expiring', 'none'].includes(s)); });
  $('#opList').innerHTML = rows.map(o => {
    const s = opStatus(o), [label, cls] = STATUS[s] || STATUS.none, f = o.feed || {};
    const detail = ['none'].includes(s) ? `${o.type === 'publico' ? T('Públicos run without a published schedule') : T('No GTFS feed found')}${o.ntd_id ? ` · FTA NTD ${o.ntd_id}` : ''}`
      : s === 'in_ati' ? T('Operated inside the ATI network') : `${Tn(o.routes, '{n} route', '{n} routes', { n: fmt(o.routes) })} · ${Tn(o.stops, '{n} stop', '{n} stops', { n: fmt(o.stops) })}${o.trips_weekday ? ` · ${Tn(o.trips_weekday, '{n} weekday trip', '{n} weekday trips', { n: fmt(o.trips_weekday) })}` : ''}${f.end ? ` · ${T('valid to {date}', { date: dayText(f.end) })}` : ''}${f.has_shapes === false ? ` · ${T('no route shapes (drawn along roads)')}` : ''}${f.order_issue ? ` · ${Tn(f.order_issue, '{n} route lists stops out of order', '{n} routes list stops out of order')}` : ''}`;
    const hasGeo = o.routes > 0;
    return `<div class="op-row" data-op="${esc(o.id)}"><span class="op-dot" style="background:${opColor(o)}"></span>
      <div class="op-main"><b translate="no">${esc(o.short || o.name)}</b> <span class="pill ${cls}">${esc(T(label))}</span><small translate="no">${esc(o.name)}</small><small>${esc(detail)}</small></div>
      ${hasGeo ? `<button type="button" class="btn op-btn" data-act="show" aria-pressed="${NET.hl === o.id}">${esc(NET.hl === o.id ? T('Showing') : T('Show'))}</button>` : o.municipality ? `<button type="button" class="btn op-btn" data-act="muni">${esc(T('Open {name}', { name: o.municipality }))}</button>` : ''}</div>`;
  }).join('') || `<div class="empty">${esc(T('No operators match.'))}</div>`;
}
function highlightOperator(id) {
  NET.hl = NET.hl === id ? null : id;
  restyleRoutes();
  if (NET.hl) {
    if (!$('#lyRoutes').checked) { $('#lyRoutes').checked = true; $('#lyRoutes').dispatchEvent(new Event('change')); }
    const wait = setInterval(() => {
      if (typeof routesLayer === 'undefined' || !routesLayer) return;
      clearInterval(wait); restyleRoutes();
      const ls = []; routesLayer.eachLayer(l => { if (l.feature.properties.operator === NET.hl) ls.push(l); });
      if (ls.length) map.fitBounds(L.featureGroup(ls).getBounds().pad(.15));
      ls.forEach(l => l.bringToFront());
    }, 150);
  }
  renderOpList();
}

// ── Vehicles on their timetable right now ────────────────────────────────────
async function updateNow() {
  const on = $('#lyNow').checked; if (!on) return;
  const d = prToday(), dow = d.getDay(), key = dow === 0 ? 'su' : dow === 6 ? 'sa' : 'wk', label = { su: T('Sunday timetables'), sa: T('Saturday timetables'), wk: T('weekday timetables') }[key];
  if (!NET.trips[key]) NET.trips[key] = await getJson(key === 'wk' ? 'data/trips.json' : `data/trips_${key}.json`, label);
  const sec = d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds();
  const pts = [], perOp = {};
  for (const t of NET.trips[key].trips) {
    const o = NET.opById[t.o]; if (!o || opStatus(o) === 'expired') continue;
    const p = tripPoints(NET.trips[key], t), first = p[0][2], last = p[p.length - 1][2];   // along the route line (common.js)
    if (sec < first || sec > last) continue;
    let i = 1; while (i < p.length - 1 && p[i][2] < sec) i++;
    const a = p[i - 1], b = p[i], f = b[2] === a[2] ? 0 : (sec - a[2]) / (b[2] - a[2]);
    pts.push({ ll: [a[1] + (b[1] - a[1]) * f, a[0] + (b[0] - a[0]) * f], t, o });
    perOp[o.short || o.id] = (perOp[o.short || o.id] || 0) + 1;
  }
  if (!NET.nowLayer) NET.nowLayer = L.layerGroup().addTo(map);
  NET.nowLayer.clearLayers();
  for (const v of pts) L.circleMarker(v.ll, { pane: 'now', radius: 6, color: '#fff', weight: 1.5, fillColor: v.t.m === 'rail' ? '#B82415' : v.t.m === 'ferry' ? '#338CB3' : v.o.type === 'regional' ? '#205D7B' : '#607316', fillOpacity: 1, interactive: true })
    .bindTooltip(Th('<b>{route}</b> · {operator}<br><small>on its timetable, not a GPS position</small>', { route: v.t.r, operator: v.o.short || v.o.name })).addTo(NET.nowLayer);
  const top = Object.entries(perOp).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, n]) => `${k} ${fmt(n)}`).join(' · ');
  $('#nowNote').innerHTML = Th('<b>{n}</b> {vehicles} in service on {timetables} at {time} Puerto Rico time{top}. Positions are interpolated from the timetable, not GPS. Expired timetables are left out; holidays are not modeled.', { n: fmt(pts.length), vehicles: Tn(pts.length, 'vehicle', 'vehicles'), timetables: label, time: hms(sec), top: top ? `: ${top}` : '' });
}
function setNow(on) {
  clearInterval(NET.nowTimer);
  if (!on) { if (NET.nowLayer) NET.nowLayer.clearLayers(); $('#nowNote').textContent = ''; return; }
  updateNow().catch(() => { $('#lyNow').checked = false; refreshFolds(); $('#tab-transit').foldRefresh(); });
  NET.nowTimer = setInterval(() => updateNow().catch(() => {}), 5000);
}

// ── Planning layers ──────────────────────────────────────────────────────────
async function loadBlocks() { if (!NET.blocks) NET.blocks = await getJson('data/population_blocks.json', T('population by block')); return NET.blocks; }
async function setGaps(on) {
  if (NET.gapLayer) { map.removeLayer(NET.gapLayer); NET.gapLayer = null; }
  if (!on) { $('#gapNote').textContent = ''; return; }
  const blocks = await loadBlocks();
  if (!$('#lyGaps').checked) return;
  const walk = blocks.length > 0 && blocks[0].length > 4, dist = b => walk ? b[4] : b[3];   // [lon, lat, residents, meters straight, meters walked along mapped roads]
  const far = blocks.filter(b => dist(b) > 800 && b[2] >= 40), people = blocks.filter(b => dist(b) > 800).reduce((a, b) => a + b[2], 0), all = blocks.reduce((a, b) => a + b[2], 0);
  NET.gapLayer = L.layerGroup(far.map(b => L.circleMarker([b[1], b[0]], { pane: 'gaps', radius: Math.min(14, 2 + Math.sqrt(b[2]) * .45), color: '#B56D00', weight: .6, fillColor: '#FFA600', fillOpacity: .45 })
    .bindTooltip(walk ? Th(b[4] >= 9999 ? '<b>{n}</b> residents · more than 1 km walking to the nearest scheduled stop ({s} m in a straight line)' : '<b>{n}</b> residents · {m} m walking to the nearest scheduled stop ({s} m in a straight line)', { n: fmt(b[2]), m: fmt(b[4]), s: fmt(b[3]) })
      : Th('<b>{n}</b> residents · {m} m to the nearest scheduled stop', { n: fmt(b[2]), m: fmt(b[3]) })))).addTo(map);
  $('#gapNote').innerHTML = walk ? Th('<b>{n}</b> residents ({pct}%) live more than an 800 m walk from any scheduled stop, along mapped roads. Circles show census blocks with 40 or more residents.', { n: fmt(people), pct: fmt(people / all * 100) })
    : Th('<b>{n}</b> residents ({pct}%) live more than 800 m from any scheduled stop. Circles show census blocks with 40 or more residents.', { n: fmt(people), pct: fmt(people / all * 100) });
}
function setXfer(on) {
  if (NET.xferLayer) { map.removeLayer(NET.xferLayer); NET.xferLayer = null; }
  if (!on) { $('#xferNote').textContent = ''; return; }
  const name = (id) => (NET.opById[id] || {}).short || id;
  NET.xferLayer = L.layerGroup(NET.transfers.map(x => L.circleMarker([x.lat, x.lng], { pane: 'gaps', radius: 7, color: '#205D7B', weight: 2, fillColor: '#fff', fillOpacity: .9 })
    .bindTooltip(Th('<b>{first}</b> “{firststop}”<br>↔ <b>{second}</b> “{secondstop}”<br><small>{d} m apart</small>', { first: name(x.a), firststop: x.an, second: name(x.b), secondstop: x.bn, d: fmt(x.d) })))).addTo(map);
  $('#xferNote').innerHTML = Th('<b>{n}</b> places where stops of two different systems are within 250 m of each other{drawn}. These are the natural places to coordinate timetables and fares.', { n: fmt(NET.transfersTotal), drawn: NET.transfersTotal > NET.transfers.length ? ` ${T('(the closest {n} are drawn)', { n: fmt(NET.transfers.length) })}` : '' });
}

// ── Plan a route ─────────────────────────────────────────────────────────────
// The planner itself (names, roads, scoring) is in plan.js and shared with the 3D view; this draws it on the Leaflet map.
const PLH = { casing: null, line: null, dashed: null, markers: [] };
const planMarker = (letter, cls) => L.divIcon({ className: 'plan-marker-wrap', html: `<div class="plan-marker ${cls}">${letter}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] });
const planHost = {
  center: () => map.getCenter(),
  picking(on) {
    map.getContainer().style.cursor = on ? 'crosshair' : '';
    if (on) { if (isMobile()) setPanel(false); toast(T('Click the map to place the point. Press Escape to stop.'), 5000); }
  },
  focusPoint(r) { if (Plan.placed().length < 2) { if (r.bbox) map.fitBounds(r.bbox, { maxZoom: 15 }); else map.setView([r.lat, r.lng], Math.max(map.getZoom(), 13)); } },
  async data() {
    const [blocks, transport, routes, flood, prot, supply] = await Promise.all([loadBlocks(), S.transport || Data.json('data/transport.json'), S.routes || Data.json('data/transit_routes.geojson'), S.flood || Data.json('data/flood.geojson'), S.prot || Data.json('data/protected.geojson'), Data.json('data/transit_supply.json').catch(() => null)]);
    if ($('#lyPlaces').checked && !S.placesLoaded) await ensurePlaces().catch(() => {});   // the switch is on and the listings are on their way (a shared link)
    return { blocks, transport, routes, flood, prot, ops: NET.ops, places: S.placesLoaded ? S.places : null, muniFc: S.muniFc, supply };   // supply: the existing service near the route (optional)   // no listings, no tourism count (the route card says so)
  },
  fit(b) { map.fitBounds(b, { padding: [50, 50], maxZoom: 16 }); if (isMobile()) toast(T('Route drawn. Close the panel to see it on the map.'), 5000); },
  drawRoute(coords, stops) {
    for (const k of ['casing', 'line', 'dashed']) if (PLH[k]) { map.removeLayer(PLH[k]); PLH[k] = null; }
    PLH.markers.forEach(m => map.removeLayer(m)); PLH.markers = [];
    const r = Plan.result;
    if (coords && coords.length > 1) {
      const ll = coords.map(c => [c[1], c[0]]), opt = { pane: 'sketch', lineCap: 'round', lineJoin: 'round', interactive: false };
      PLH.casing = L.polyline(ll, { ...opt, color: '#fff', weight: 9, opacity: .9 }).addTo(map);
      PLH.line = L.polyline(ll, { ...opt, color: '#2A2E2E', weight: 5, opacity: .95 }).addTo(map);
      if (r && !r.path.allOnRoads) {   // legs that could not follow a road are marked with red dots
        const parts = []; r.path.legs.forEach((l, i) => { if (!l.ok) parts.push(ll.slice(r.path.legAt[i], (r.path.legAt[i + 1] ?? ll.length - 1) + 1)); });
        PLH.dashed = L.polyline(parts, { ...opt, color: '#FF4D38', weight: 4, dashArray: '1 8' }).addTo(map);
      }
    }
    stops.forEach((s, i) => {
      const cls = s.row === 0 ? 'a' : s.row === Plan.stops.length - 1 ? 'z' : 'v';
      const m = L.marker([s.lat, s.lng], { icon: planMarker(Plan.letter(s.row), cls), draggable: true, keyboard: false, title: T('{label} (drag to move)', { label: s.label }), zIndexOffset: 900 }).addTo(map);
      m.on('dragend', () => { const p = m.getLatLng(); Plan.movePoint(i, p.lat, p.lng); });
      PLH.markers.push(m);
    });
    writeHash();
  },
};
async function focusRoute(f) {
  if (!$('#lyRoutes').checked) { $('#lyRoutes').checked = true; $('#lyRoutes').dispatchEvent(new Event('change')); }
  const p = f.properties, wait = setInterval(() => {
    if (!routesLayer || !map.hasLayer(routesLayer)) return;
    clearInterval(wait);
    let hit; routesLayer.eachLayer(l => { const q = l.feature.properties; if (q.route_id === p.route_id && q.operator === p.operator) hit = l; });
    if (hit) { map.fitBounds(hit.getBounds().pad(.2)); hit.bringToFront(); hit.openPopup(); }
  }, 150);
  if (isMobile()) setPanel(false);
}

// ── Start ────────────────────────────────────────────────────────────────────
/** The route planner (plan_route.js) loads on first use: the Plan a route section, a link with r=, Route from / to here. Its Spanish is in the map's bundle (scope map). */
let planP = null;
const planLoad = () => planP || (planP = (typeof Plan !== 'undefined' ? Promise.resolve() : addJs('js/plan_route.js?v=2')).then(() => {
  if (!Plan.root) { $('#planBox').innerHTML = planMarkup(); planWire($('#planBox')); Plan.init(planHost, $('#planBox')); }
}).catch(e => { planP = null; throw e; }));
const planInLink = parseHash().r;   // read now: the map rewrites the address (without the plan, not drawn yet) before the operators arrive below
async function onMapReady() {
  ['now', 'gaps', 'sketch'].forEach((k, i) => { map.createPane(k); map.getPane(k).style.zIndex = 400 + i * 5; });
  const tr = $('#tab-transit'); initFolds(tr); tr.querySelector('.fold-toggle').click();   // every section folds (common.js): Planning layers starts open, What is live, Operators and Plan a route closed; a closed heading counts its layers that are on
  tr.foldOpen = (el) => { const b = el.closest('.fold-body'); if (b && b.hidden) b.previousElementSibling.querySelector('.fold-toggle').click(); };   // opens the section that holds el
  tr.addEventListener('change', e => { if (e.target.checked) tr.foldOpen(e.target); }, true);   // a layer switched on from a link, the chat or Undo opens its section
  const d = await getJson('data/operators.json', T('transit operators')).catch(() => null);
  if (!d) { $('#netSummary').innerHTML = `<div class="note">${esc(T('The operator list could not be loaded.'))}</div>`; return; }
  NET.ops = d.operators; NET.opById = Object.fromEntries(d.operators.map(o => [o.id, o])); NET.live = d.live; NET.coverage = d.coverage; NET.transfers = d.transfers; NET.transfersTotal = d.transfers_total;
  renderNetSummary(); renderLiveStatus(); renderOpList(); restyleRoutes();
  $('#opFilter').onchange = renderOpList;
  $('#opList').addEventListener('click', e => { const b = e.target.closest('.op-btn'); if (!b) return; const id = b.closest('.op-row').dataset.op; if (b.dataset.act === 'show') highlightOperator(id); else { const o = NET.opById[id]; if (o && o.municipality) { selectMuni(o.municipality); } } });
  $('#lyNow').onchange = e => { setNow(e.target.checked); writeHash(); };
  $('#lyGaps').onchange = async e => { try { await setGaps(e.target.checked); } catch { e.target.checked = false; } writeHash(); };
  $('#lyXfer').onchange = e => { setXfer(e.target.checked); writeHash(); };
  $('#tvOnly').onclick = () => { for (const [id, on] of [['lyPlaces', false], ['lyRoutes', true]]) { const el = $('#' + id); if (el.checked !== on) { el.checked = on; el.dispatchEvent(new Event('change')); } } toast(T('Showing transit only. Turn tourism places back on in Home › Map layers.'), 5000); };
  const planHead = $('#planBox').closest('.fold-body'), planToggle = planHead && planHead.previousElementSibling.querySelector('.fold-toggle');
  if (planToggle) planToggle.addEventListener('click', () => { planLoad().catch(() => { $('#planBox').innerHTML = `<div class="note">${esc(T('The route planner could not be loaded. Check your connection and open the section again.'))}</div>`; }); });   // the planner loads when its section opens
  map.on('click', e => { if (typeof Plan === 'undefined' || !Plan.root) return; if (Plan.picking >= 0) Plan.mapPick(e.latlng.lat, e.latlng.lng); else if (Plan.clickMode) Plan.appendPoint(e.latlng.lat, e.latlng.lng); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && typeof Plan !== 'undefined' && Plan.root && (Plan.picking >= 0 || Plan.clickMode)) { Plan.picking = -1; Plan.setClickMode(false); Plan.root.querySelectorAll('[data-act=pick]').forEach(x => x.setAttribute('aria-pressed', 'false')); } });
  const hr = planInLink; if (hr) { let plan = ''; try { plan = decodeURIComponent(hr); } catch { /* a broken % in the link: the tab opens without the plan */ } showTab('transit', { open: false }); tr.foldOpen($('#planBox')); planLoad().then(() => { if (plan) Plan.restore(plan); }, () => null); }
  // layers requested in the URL
  ['lyNow', 'lyGaps', 'lyXfer'].forEach(id => { if ($('#' + id).checked) $('#' + id).dispatchEvent(new Event('change')); });
}
