/* PR Data Observatory: transit supply in the 3D view (site/data/transit_supply.json, built by supply.py from the timetables).
   Time tab: which day's timetable the replay plays (weekday, Saturday, Sunday), and "Service at this hour": routes drawn by trips in the
   hour on the clock, stops sized by their departures, and a chart of the day. Route tab: the profile of an existing route (its service
   hour by hour, each direction's waits and run time, its stops, and the routes of any operator that stop within 250 m of it).
   Loads after twin3d.js and uses its map, S, renderDeck, syncClock, pop, loadJson, transportData and fitTo; twin3d.js's click dispatcher asks card() for the card of a
   click on these layers. Timetables, not observed service. */
const Supply = (() => {
  const FILES = { wk: 'data/trips.json', sa: 'data/trips_sa.json', su: 'data/trips_su.json' };
  const BINS = [[6, '#205D7B', 7], [4, '#338CB3', 5], [2, '#5FAFDA', 3.5], [1, '#8FCAE8', 2]];   // trips (or departures) in the hour → color, width in px
  const bin = (n) => BINS.find(b => n >= b[0]);
  const rgb = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const hhmm = (s) => `${pad2(Math.floor(s / 3600))}:${pad2(Math.floor(s % 3600 / 60))}`;
  const MODE = () => ({ bus: T('Bus'), rail: T('Train'), ferry: T('Ferry') });
  const TIMETABLE = () => ({ wk: T('weekday timetable'), sa: T('Saturday timetable'), su: T('Sunday timetable') });   // for sentences (Spanish writes days in lowercase there)
  const X = { data: null, ops: {}, stops: null, docs: {}, day: 'wk', hour: -1, cache: null, sel: null, xferIndex: null, ready: null };

  // ── data ──
  function load() {
    if (!X.ready) X.ready = Promise.all([Data.json('data/transit_supply.json'), Data.json('data/operators.json'), transportData()])   // one request for transport.json, shared with the search and the stops, stations and taxi layers (twin3d.js)
      .then(([sup, ops, tr]) => {
        X.data = sup; S.transport = S.transport || tr;
        X.ops = Object.fromEntries(ops.operators.map(o => [o.id, o]));
        X.stops = new Map(tr.filter(f => String(f.id || '').startsWith('gtfs:')).map(f => [f.id, f]));
        fillRoutes(); renderHour(true);
      })
      .catch(e => { X.ready = null; $('#supHour').innerHTML = `<div class="note">${esc(T('The service figures could not be loaded. Check your connection and try again.'))}</div>`; throw e; });
    return X.ready;
  }
  async function doc(day) {
    if (!X.docs[day]) X.docs[day] = day === 'wk' && S.trips ? Promise.resolve(S.trips) : loadJson(FILES[day]);
    return X.docs[day];
  }
  const dayData = () => X.data && X.data.days[X.day];
  const keep = (row) => row.cur || $('#supExpired').checked;
  const opName = (o) => (X.ops[o] && (X.ops[o].short || X.ops[o].name)) || o;

  // ── the day the replay plays ──
  async function setDay(day) {
    if (!FILES[day]) return;
    X.day = day;
    document.querySelectorAll('#daySeg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.day === day)));
    try { S.trips = await doc(day); } catch { toast(T('That timetable could not be loaded. Check your connection and try again.'), 6000); return; }
    S.vehMinute = null; X.hour = -1; X.cache = null;
    syncClock(); renderHour(true); if (X.sel) showRoute(X.sel.key, false); renderDeck();
  }
  function dayLabel(time) { return { wk: T('{time} · weekday transit', { time }), sa: T('{time} · Saturday transit', { time }), su: T('{time} · Sunday transit', { time }) }[X.day]; }

  // ── service at this hour ──
  function onClock() { const h = Math.min(23, Math.floor(S.clock / 3600)); if (h !== X.hour) { X.hour = h; X.cache = null; renderHour(); } }
  function hourRows() {
    if (X.cache) return X.cache;
    const D = dayData(), h = X.hour; if (!D || !S.trips || h < 0) return null;
    const routes = D.patterns.filter(p => keep(p) && p.hours[h] > 0 && S.trips.paths[p.k]).sort((a, b) => a.hours[h] - b.hours[h])
      .map(p => ({ p, n: p.hours[h], path: S.trips.paths[p.k].map(q => [q[0], q[1]]) }));
    const stops = [];
    for (const [id, s] of Object.entries(D.stops)) { const f = X.stops.get(id); if (f && keep(s) && s.hours[h] > 0) stops.push({ id, s, f, n: s.hours[h] }); }
    stops.sort((a, b) => a.n - b.n);
    return (X.cache = { routes, stops });
  }
  function layers() {
    const out = [], c = (X.data && ($('#lySupRoutes').checked || $('#lySupStops').checked)) ? hourRows() : null;
    if (c && $('#lySupRoutes').checked) out.push(new deck.PathLayer({ id: 'sup-routes', data: c.routes, getPath: d => d.path, getColor: d => [...rgb(bin(d.n)[1]), 220], getWidth: d => bin(d.n)[2], widthUnits: 'pixels', capRounded: true, jointRounded: true, pickable: true }));
    if (c && $('#lySupStops').checked) out.push(new deck.ScatterplotLayer({ id: 'sup-stops', data: c.stops, getPosition: d => [d.f.lng, d.f.lat], getRadius: d => bin(d.n)[2] * .8 + 1, radiusUnits: 'pixels', getFillColor: d => [...rgb(bin(d.n)[1]), 235], stroked: true, getLineColor: [255, 255, 255], lineWidthMinPixels: 1, pickable: true }));
    if (X.sel && X.sel.paths) {
      out.push(new deck.PathLayer({ id: 'rp-under', data: X.sel.paths, getPath: d => d, getColor: [42, 46, 46, 230], getWidth: 9, widthUnits: 'pixels', capRounded: true, jointRounded: true, pickable: !!S.pickNoCard }));   // no card: pickable only for twin3d.js noCardAt
      out.push(new deck.PathLayer({ id: 'rp-line', data: X.sel.paths, getPath: d => d, getColor: [255, 166, 0, 255], getWidth: 5, widthUnits: 'pixels', capRounded: true, jointRounded: true, pickable: !!S.pickNoCard }));
      out.push(new deck.ScatterplotLayer({ id: 'rp-xfer', data: X.sel.xferStops, getPosition: d => [d.lng, d.lat], getRadius: 5, radiusUnits: 'pixels', getFillColor: [255, 255, 255, 255], stroked: true, getLineColor: [42, 46, 46, 255], lineWidthMinPixels: 2, pickable: true }));
      out.push(new deck.ScatterplotLayer({ id: 'rp-stops', data: X.sel.stops, getPosition: d => [d.lng, d.lat], getRadius: 4, radiusUnits: 'pixels', getFillColor: [255, 166, 0, 255], stroked: true, getLineColor: [42, 46, 46, 255], lineWidthMinPixels: 1.5, pickable: true }));
    }
    return out;
  }
  // The card of a click on one of these layers (twin3d.js, the click dispatcher, which gives a deck.gl object the click before the MapLibre layers): [where, html].
  const CARDS = ['sup-routes', 'sup-stops', 'rp-xfer', 'rp-stops'];   // the profile's line (rp-under, rp-line) has none
  function card(i) {
    const o = i.object, D = dayData();
    if (i.layer.id === 'sup-routes') return [i.coordinate, routePop(o.p, X.hour)];
    if (i.layer.id === 'sup-stops') return [[o.f.lng, o.f.lat], stopPop(o.f, o.s, X.hour)];
    return CARDS.includes(i.layer.id) ? [[o.lng, o.lat], stopPop(o, D && D.stops[o.id], X.hour)] : null;   // a stop of the route profile, or a stop of a connecting route
  }
  const waitTxt = (n) => n ? T('a departure every {n} min', { n: fmt(n) }) : T('no departures');
  function routePop(p, h) {
    return `<div class="pop"><h4>${icon(p.m === 'rail' ? 'subway' : p.m === 'ferry' ? 'directions_boat' : 'directions_bus', { size: 20 })}${esc(T('{operator} route {route}', { operator: opName(p.o), route: p.r }))}</h4>
      <div class="meta">${esc(T('{n} trips in this direction between {from} and {to}', { n: fmt(p.hours[h]), from: `${pad2(h)}:00`, to: `${pad2(h + 1)}:00` }))}<br>${esc(Tn(p.trips, '{n} trip all day in this direction', '{n} trips all day in this direction', { n: fmt(p.trips) }))} · ${esc(T('first {first}, last {last}', { first: hhmm(p.first), last: hhmm(p.last) }))}</div>
      ${p.cur ? '' : `<div class="meta">${esc(T('This operator\'s timetable has expired: the service may have changed.'))}</div>`}
      <div class="links"><a href="#" data-route-profile="${esc(p.o + '|' + p.r)}">${esc(T('Open the route profile'))}</a></div></div>`;
  }
  function stopPop(f, s, h) {
    if (!s) return `<div class="pop"><h4>${esc(f.name || T('Stop'))}</h4><div class="meta">${esc(T('No departures on this day.'))}</div></div>`;
    return `<div class="pop"><h4>${icon('directions_bus', { size: 20 })}${esc(f.name || T('Stop'))}</h4>
      <div class="meta">${esc(opName(f.operator))} · ${esc(T('Routes: {routes}', { routes: s.routes.join(', ') }))}</div>
      <div class="meta">${Th('<b>{n}</b> departures between {from} and {to}', { n: fmt(s.hours[h]), from: `${pad2(h)}:00`, to: `${pad2(h + 1)}:00` })} · ${esc(Tn(s.n, '{n} departure all day', '{n} departures all day', { n: fmt(s.n) }))}</div>
      <div class="meta">${esc(T('First {first}, last {last}', { first: hhmm(s.first), last: hhmm(s.last) }))}${s.gap != null ? ` · ${esc(T('longest wait between 06:00 and 22:00: {n} min', { n: fmt(s.gap) }))}` : ''}</div>
      ${s.cur ? '' : `<div class="meta">${esc(T('This operator\'s timetable has expired: the service may have changed.'))}</div>`}</div>`;
  }
  function bars(values, cur, label, onPick) {   // 24 bars, the current hour marked; returns SVG markup
    const max = Math.max(1, ...values), W = 288, H = 64, bw = W / 24;
    const rects = values.map((v, i) => { const h = Math.round(v / max * (H - 14)); return `<rect x="${(i * bw + 1).toFixed(1)}" y="${H - 12 - h}" width="${(bw - 2).toFixed(1)}" height="${Math.max(h, v ? 1 : 0)}" rx="1.5" fill="${i === cur ? '#FFA600' : '#5FAFDA'}"${onPick ? ` data-h="${i}" style="cursor:pointer"` : ''}><title>${pad2(i)}:00 · ${fmt(v)}</title></rect>`; }).join('');
    const ticks = [0, 6, 12, 18].map(i => `<text x="${(i * bw + 1).toFixed(1)}" y="${H - 1}" font-size="9" fill="#666">${pad2(i)}</text>`).join('');
    return `<svg class="sup-bars" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(label)}">${rects}${ticks}</svg>`;
  }
  function renderHour(force) {
    const box = $('#supHour'); if (!box) return;
    const D = dayData(); if (!D) { if (!X.data) box.innerHTML = `<div class="note" role="status">${esc(T('Loading the service figures…'))}</div>`; return; }
    if (!force && box.dataset.k === `${X.day}|${X.hour}|${$('#supExpired').checked}`) return;
    box.dataset.k = `${X.day}|${X.hour}|${$('#supExpired').checked}`;
    const h = Math.max(0, X.hour), I = D.island;
    const peak = I.vehicles.indexOf(Math.max(...I.vehicles));
    box.innerHTML = `<div class="sup-now">${Th('<b>{from}–{to}</b>, {timetable}: <b>{vehicles}</b> vehicles in service, <b>{routes}</b> routes running, <b>{stops}</b> stops with a departure, <b>{frequent}</b> of them with a departure every 15 minutes or better.',
        { from: `${pad2(h)}:00`, to: `${pad2(h + 1)}:00`, timetable: TIMETABLE()[X.day], vehicles: fmt(I.vehicles[h]), routes: fmt(I.routes[h]), stops: fmt(I.stops[h]), frequent: fmt(I.frequent_stops[h]) })}</div>
      ${bars(I.vehicles, h, T('Vehicles in service by hour; the busiest hour is {h}:00 with {n}.', { h: pad2(peak), n: fmt(I.vehicles[peak]) }), true)}
      <div class="note">${esc(T('Vehicles in service each hour (current timetables). Click a bar to move the clock.'))}</div>`;
    box.querySelectorAll('rect[data-h]').forEach(r => r.addEventListener('click', () => { S.clock = +r.dataset.h * 3600 + 1800; syncClock(); renderDeck(); }));
    $('#supLegend').innerHTML = `<div class="sup-legend">${BINS.slice().reverse().map(([n, c, w], i, a) => `<span><i style="background:${c};height:${Math.max(3, w)}px"></i>${esc(i === a.length - 1 ? T('{n} or more per hour', { n }) : n === a[i + 1][0] - 1 ? T('{n} per hour', { n }) : T('{a}–{b} per hour', { a: n, b: a[i + 1][0] - 1 }))}</span>`).join('')}</div>`;
  }

  // ── route profile ──
  function fillRoutes() {
    const sel = $('#rpSel'); if (!sel || !X.data) return;
    const all = new Map();
    for (const d of ['wk', 'sa', 'su']) for (const r of (X.data.days[d] || { routes: [] }).routes) if (!all.has(r.o + '|' + r.r)) all.set(r.o + '|' + r.r, r);
    const lname = {}; for (const f of ((S.routes || {}).features || [])) { const p = f.properties; lname[p.operator + '|' + (p.short_name || p.long_name)] = p.long_name; }
    const groups = {};
    for (const [k, r] of all) (groups[opName(r.o)] = groups[opName(r.o)] || []).push([k, r]);
    sel.innerHTML = `<option value="">${esc(T('Choose a route…'))}</option>` + Object.keys(groups).sort((a, b) => a.localeCompare(b, 'es')).map(g => `<optgroup label="${esc(g)}">${groups[g].sort((a, b) => a[1].r.localeCompare(b[1].r, 'es', { numeric: true })).map(([k, r]) => `<option value="${esc(k)}">${esc(r.r)}${lname[k] && lname[k] !== r.r ? ' · ' + esc(lname[k]) : ''}${r.cur ? '' : ' ' + esc(T('(expired timetable)'))}</option>`).join('')}</optgroup>`).join('');
  }
  function xferIndex() {   // stops with departures on a weekday, on a 0.0025° grid (about 250 m)
    if (X.xferIndex) return X.xferIndex;
    const g = new Map(), C = .0025, W = X.data.days.wk;
    for (const [id, s] of Object.entries(W.stops)) { const f = X.stops.get(id); if (!f) continue; const k = Math.floor(f.lat / C) * 100000 + Math.floor(f.lng / C); if (!g.has(k)) g.set(k, []); g.get(k).push({ f, s }); }
    return (X.xferIndex = { g, C });
  }
  async function showRoute(key, fit = true) {
    await load();
    const box = $('#rpCard'); if (!key) { X.sel = null; box.innerHTML = ''; renderDeck(); return; }
    const [o, r] = key.split('|'), byDay = {};
    for (const d of ['wk', 'sa', 'su']) { const D = X.data.days[d]; if (D) byDay[d] = { route: D.routes.find(x => x.o === o && x.r === r), patterns: D.patterns.filter(p => p.o === o && p.r === r) }; }
    const day = byDay[X.day] && byDay[X.day].route ? X.day : 'wk', base = byDay[day] && byDay[day].route ? day : Object.keys(byDay).find(d => byDay[d].route);
    if (!base) { box.innerHTML = `<div class="note">${esc(T('This route has no trips with times in the published timetables.'))}</div>`; return; }
    const tdoc = await doc(base), R = byDay[base].route, pats = byDay[base].patterns.slice().sort((a, b) => b.trips - a.trips);
    const stopIds = [...new Set(pats.flatMap(p => (tdoc.path_stops || [])[p.k] || []))], stops = stopIds.map(id => X.stops.get(id)).filter(Boolean);
    // routes of any operator with a departure from a stop within 250 m of this route's stops (weekday)
    const { g, C } = xferIndex(), near = new Map();
    for (const f of stops) { const cy = Math.floor(f.lat / C), cx = Math.floor(f.lng / C);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) for (const q of (g.get((cy + dy) * 100000 + cx + dx) || [])) {
        const d = Math.hypot((q.f.lng - f.lng) * 105700, (q.f.lat - f.lat) * 110540); if (d > 250) continue;
        for (const rr of q.s.routes) { const k = q.f.operator + '|' + rr; if (k === key) continue; const e = near.get(k); if (!e || d < e.d) near.set(k, { o: q.f.operator, r: rr, d, stop: q.f }); } } }
    const W = X.data.days.wk, wkr = new Map(W.routes.map(x => [x.o + '|' + x.r, x]));
    const conns = [...near.values()].map(c => ({ ...c, info: wkr.get(c.o + '|' + c.r) })).filter(c => c.info).sort((a, b) => (a.o === o) - (b.o === o) || b.info.trips - a.info.trips);
    X.sel = { key, paths: pats.map(p => tdoc.paths[p.k].map(q => [q[0], q[1]])), stops, xferStops: [...new Map(conns.map(c => [c.stop.id, c.stop])).values()] };
    renderDeck();
    if (fit) { const pts = X.sel.paths.flat(); if (pts.length) fitTo([[Math.min(...pts.map(p => p[0])), Math.min(...pts.map(p => p[1]))], [Math.max(...pts.map(p => p[0])), Math.max(...pts.map(p => p[1]))]], { maxZoom: 15 }); }   // [[west, south], [east, north]], as planHost.fit
    // the card
    const op = X.ops[o] || {}, feed = op.feed || {}, cur = R.cur;
    const status = cur ? T('Timetable current until {date}', { date: feed.end || '—' }) : T('Timetable expired on {date}: the service may have changed', { date: feed.end || '—' });
    const dir = (p) => { const ids = (tdoc.path_stops || [])[p.k] || [], a = X.stops.get(ids[0]), b = X.stops.get(ids[ids.length - 1]); return a && b ? `${a.name} → ${b.name}` : T('Direction {n}', { n: p.k }); };
    const cnt = (d) => byDay[d] && byDay[d].route ? fmt(byDay[d].route.trips) : '0';
    const hw = (v) => v == null ? '—' : fmt(v);
    const busiest = pats[0], bIds = (tdoc.path_stops || [])[busiest.k] || [], D0 = X.data.days[base];
    box.innerHTML = `<div class="rp">
      <h3>${esc(T('{operator} route {route}', { operator: opName(o), route: r }))}</h3>
      <div class="meta">${esc(MODE()[R.m] || R.m)} · ${esc(status)}</div>
      <div class="kpis"><div class="kpi"><div class="v">${cnt('wk')}</div><div class="l">${esc(T('weekday trips (both directions)'))}</div></div>
        <div class="kpi"><div class="v">${cnt('sa')} · ${cnt('su')}</div><div class="l">${esc(T('Saturday · Sunday trips'))}</div></div>
        <div class="kpi"><div class="v">${hhmm(R.first)}–${hhmm(R.last)}</div><div class="l">${esc(T('first and last departure ({timetable})', { timetable: TIMETABLE()[base] }))}</div></div>
        <div class="kpi"><div class="v">${R.peak_hw ? fmt(R.peak_hw) + ' min' : '—'}</div><div class="l">${esc(T('between departures at the morning peak (06:00–09:00), busiest direction'))}</div></div></div>
      ${bars(R.hours, Math.max(0, X.hour), T('Departures by hour, both directions; the most in one hour is {n}.', { n: fmt(Math.max(...R.hours)) }))}
      <div class="note">${esc(T('Departures by hour, both directions ({timetable}).', { timetable: TIMETABLE()[base] }))}</div>
      <div class="tbl-wrap" tabindex="0" role="region" aria-label="${esc(T('Directions of the route, scrollable'))}"><table class="pt rp-dirs"><thead><tr><th scope="col">${esc(T('Direction'))}</th><th scope="col">${esc(T('Trips'))}</th><th scope="col">${esc(T('Minutes between departures: morning, midday, afternoon, evening'))}</th><th scope="col">${esc(T('Run time'))}</th><th scope="col">${esc(T('Length'))}</th></tr></thead><tbody>
        ${pats.map(p => `<tr><td>${esc(dir(p))}${p.line ? '' : ` <small>${esc(T('(approximate path)'))}</small>`}</td><td>${fmt(p.trips)}</td><td>${['am', 'mid', 'pm', 'eve'].map(k => hw(p.periods[k].hw)).join(' · ')}</td><td>${fmt(p.run_min, 0)} min</td><td>${fmt(p.km, 1)} km${p.kmh ? ` <small>${fmt(p.kmh, 0)} km/h</small>` : ''}</td></tr>`).join('')}</tbody></table></div>
      <details class="rp-stops"><summary>${esc(Tn(bIds.length, '{n} stop in the busiest direction', '{n} stops in the busiest direction', { n: fmt(bIds.length) }))}</summary><ol>${bIds.map(id => { const f = X.stops.get(id), s = D0.stops[id]; return `<li>${esc(f ? f.name : id)} <small>· ${s ? esc(Tn(s.n, '{n} departure a day, all routes', '{n} departures a day, all routes', { n: fmt(s.n) })) + (s.gap != null ? ' · ' + esc(T('longest wait {n} min', { n: fmt(s.gap) })) : '') : esc(T('last stop'))}</small></li>`; }).join('')}</ol></details>
      <h4 class="rp-h">${esc(T('Connections within 250 m'))}</h4>
      ${conns.length ? `<ul class="plain-list rp-conns">${conns.slice(0, 14).map(c => `<li><a href="#" data-route-profile="${esc(c.o + '|' + c.r)}">${esc(T('{operator} route {route}', { operator: opName(c.o), route: c.r }))}</a> <small>· ${esc(Tn(c.info.trips, '{n} weekday trip', '{n} weekday trips', { n: fmt(c.info.trips) }))}${c.info.peak_hw ? ' · ' + esc(T('every {n} min at the morning peak', { n: fmt(c.info.peak_hw) })) : ''} · ${esc(T('{m} m away', { m: fmt(Math.round(c.d / 10) * 10) }))}${c.o !== o ? ' · <b>' + esc(T('other operator')) + '</b>' : ''}${c.info.cur ? '' : ' · ' + esc(T('expired timetable'))}</small></li>`).join('')}</ul>${conns.length > 14 ? `<div class="note">${esc(T('and {n} more', { n: fmt(conns.length - 14) }))}</div>` : ''}`
        : `<div class="note">${esc(T('No other route stops within 250 m of this route on a weekday.'))}</div>`}
      <div class="note">${esc(T('From the published timetables, not observed service. Waits are the average in each period; públicos are in no timetable. White dots on the map are the stops where the connecting routes stop.'))}</div></div>`;
  }

  // ── wiring ──
  function init() {
    document.querySelectorAll('#daySeg button').forEach(b => b.onclick = () => setDay(b.dataset.day));
    ['lySupRoutes', 'lySupStops'].forEach(id => $('#' + id).onchange = async e => { if (e.target.checked) { try { await load(); } catch { e.target.checked = false; refreshFolds(); return; } } X.cache = null; renderDeck(); });
    $('#supExpired').onchange = () => { X.cache = null; renderHour(true); renderDeck(); };
    $('#rpSel').onchange = e => showRoute(e.target.value);
    document.addEventListener('click', e => { const a = e.target.closest('[data-route-profile]'); if (!a) return; e.preventDefault(); showTab('route'); $('#rpSel').value = a.dataset.routeProfile; showRoute(a.dataset.routeProfile); if (pop) pop.remove(); });   // pop: the open popup (twin3d.js)
    load().catch(() => {});
  }
  return { init, layers, card, cardLayers: CARDS, get profileShown() { return !!(X.sel && X.sel.paths); }, onClock, dayLabel, setDay, showRoute, get day() { return X.day; } };
})();
window.Supply = Supply;
// Without WebGL twin3d.js stops before it creates the map and its helpers (webglOk), so there is nothing to wire: init would throw on transportData. The check is a try, as in
// series3d.js: a binding that does not exist, or exists uninitialized, throws a ReferenceError.
if ((() => { try { return !!map && typeof map.on === 'function'; } catch { return false; } })()) Supply.init();
