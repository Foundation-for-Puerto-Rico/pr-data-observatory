/* PR Data Observatory: the route planner, shared by the 2D map and the 3D view (split from plan.js on 2026-11-04, navigation plan PR 2).
   Needs plan.js (geometry, Data, Gaz, attachSearch). The 3D view loads it with the page; the 2D map loads it the first time the Plan a route section opens, a link carries a route (r=) or Route from / to here is pressed (network.js planLoad), which keeps about
   9 KB off the map's first load.
   - Plan     From / added stops / To by name, routed along the roads (roads.js), scored against the open data */

// ── Route planning ───────────────────────────────────────────────────────────
const Plan = {
  stops: [],           // [{text, pt: {lat, lng, label, sub} | null}]  first = From, last = To, between = added stops
  follow: true, roads: null, roadsError: false, picking: -1, clickMode: false, result: null, token: 0, host: null, root: null, segIndex: null, segFor: null,
  letter: (i) => String.fromCharCode(65 + i),
  init(host, root) {
    this.host = host; this.root = root; this.stops = [{ text: '', pt: null }, { text: '', pt: null }];
    this.render(); this.renderResult(); this.draw();
  },
  placed() { return this.stops.map((s, i) => s.pt ? { ...s.pt, row: i } : null).filter(Boolean); },   // row = which box it came from (A, B, ...)

  // -- input rows --
  render() {
    const n = this.stops.length;
    this.root.querySelector('.plan-rows').innerHTML = this.stops.map((s, i) => {
      const role = i === 0 ? T('From') : i === n - 1 ? T('To') : T('Stop {n}', { n: i });
      const ph = i === 0 ? T('From: a place, street or stop') : i === n - 1 ? T('To: a place, street or stop') : T('Added stop');
      const via = i > 0 && i < n - 1;
      return `<div class="plan-row${via ? ' via' : ''}" data-i="${i}"><span class="plan-dot ${i === 0 ? 'a' : i === n - 1 ? 'z' : 'v'}" aria-hidden="true">${this.letter(i)}</span>
        <div class="plan-field"><input type="text" class="plan-in" value="${esc(s.text)}" placeholder="${esc(ph)}" aria-label="${esc(role)}" maxlength="120"><div class="search-results plan-list" id="planList${i}"></div></div>
        <div class="plan-btns"><button type="button" class="icon-btn small" data-act="pick" aria-label="${esc(T('Choose {role} on the map', { role }))}" title="${esc(T('Choose on the map'))}" aria-pressed="${this.picking === i}">${icon('place', { size: 18 })}</button>
        ${via ? `<button type="button" class="icon-btn small" data-act="up" aria-label="${esc(T('Move {role} earlier', { role }))}" title="${esc(T('Move earlier'))}">${icon('arrow_upward', { size: 16 })}</button><button type="button" class="icon-btn small" data-act="down" aria-label="${esc(T('Move {role} later', { role }))}" title="${esc(T('Move later'))}">${icon('arrow_downward', { size: 16 })}</button><button type="button" class="icon-btn small" data-act="del" aria-label="${esc(T('Remove {role}', { role }))}" title="${esc(T('Remove'))}">${icon('close', { size: 16 })}</button>` : ''}</div></div>`;
    }).join('');
    if (this._ac) this._ac.abort();
    this._ac = new AbortController();
    this.root.querySelectorAll('.plan-row').forEach(row => {
      const i = +row.dataset.i, input = row.querySelector('input'), list = row.querySelector('.plan-list');
      attachSearch(input, list, { signal: this._ac.signal, online: true, warm: () => this.warm(), run: (q) => searchEverything(q, { pointsOnly: true, bias: this.host.center && this.host.center() }), onPick: r => this.setStop(i, r), emptyText: T('No match. Try a street, town, landmark or stop name, or a PR route such as PR-52.') });
      input.addEventListener('input', () => { this.stops[i].text = input.value; if (this.stops[i].pt && input.value !== this.stops[i].pt.label) { this.stops[i].pt = null; this.stopsChanged(); } });
    });
    this.root.querySelector('.plan-add').disabled = n >= 8;
  },
  warm() { Gaz.load().catch(() => {}); if (!this.roads && !this.roadsLoading) this.loadRoads().catch(() => {}); },
  async loadRoads() {
    if (this.roads) return this.roads;
    this.roadsLoading = this.roadsLoading || Roads.load('data/roads.bin').then(r => { this.roads = r; this.roadsError = false; return r; }).catch(e => { this.roadsError = true; this.roadsLoading = null; throw e; });
    return this.roadsLoading;
  },
  setStop(i, r) {
    const s = this.stops[i]; s.pt = { lat: r.lat, lng: r.lng, label: r.label, sub: r.sub || '' }; s.text = r.label;
    const input = this.root.querySelectorAll('.plan-in')[i]; if (input) input.value = r.label;
    this.stopsChanged(true);
    if (this.host.focusPoint) this.host.focusPoint(r);
  },
  stopsChanged(compute) { this.draw(); if (compute !== false && this.placed().length >= 2) this.compute(); else if (this.placed().length < 2) { this.result = null; this.renderResult(); this.host.drawRoute(null, this.placed()); } },
  addStop() { if (this.stops.length >= 8) return; this.stops.splice(this.stops.length - 1, 0, { text: '', pt: null }); this.render(); this.root.querySelectorAll('.plan-in')[this.stops.length - 2].focus(); },
  move(i, d) { const j = i + d; if (j < 1 || j > this.stops.length - 2) return; [this.stops[i], this.stops[j]] = [this.stops[j], this.stops[i]]; this.render(); this.stopsChanged(true); },
  remove(i) { this.stops.splice(i, 1); this.render(); this.stopsChanged(true); },
  swap() { this.stops.reverse(); this.render(); this.stopsChanged(true); },
  clear() {
    this.stops = [{ text: '', pt: null }, { text: '', pt: null }]; this.picking = -1; this.clickMode = false; this.token++; this.result = null;
    this.root.querySelector('.plan-click').setAttribute('aria-pressed', 'false');
    this.render(); this.renderResult(); this.host.drawRoute(null, []); this.host.picking && this.host.picking(false);
  },
  /** Shareable form of the placed points ('lat,lng;lat,lng'), and its inverse. */
  encode() { const p = this.placed(); return p.length >= 2 ? p.map(s => `${s.lat.toFixed(4)},${s.lng.toFixed(4)}`).join(';') : ''; },
  async restore(str) {
    const pts = String(str || '').split(';').slice(0, 8).map(t => t.split(',').map(Number)).filter(a => a.length === 2 && a.every(Number.isFinite) && Math.abs(a[0]) <= 90 && Math.abs(a[1]) <= 180);
    if (pts.length < 2) return;
    await Gaz.load().catch(() => {});
    this.stops = pts.map(([lat, lng]) => { const near = Gaz.nearest(lat, lng, 250), label = near ? T('Near {name}', { name: near.name }) : `${lat.toFixed(4)}, ${lng.toFixed(4)}`; return { text: label, pt: { lat, lng, label, sub: near && near.muni ? near.muni : T('Point on the map') } }; });
    this.render(); this.stopsChanged(true);
  },
  startPick(i) {
    this.picking = this.picking === i ? -1 : i; if (this.picking >= 0) this.clickMode = false;
    this.root.querySelector('.plan-click').setAttribute('aria-pressed', String(this.clickMode));
    this.root.querySelectorAll('[data-act=pick]').forEach((b, k) => b.setAttribute('aria-pressed', String(this.picking === k)));
    this.host.picking && this.host.picking(this.picking >= 0 || this.clickMode);
  },
  /** Click-to-add mode: each click fills the first empty box, then extends the route (the old end becomes a stop). */
  setClickMode(on) {
    this.clickMode = on; if (on) this.picking = -1;
    this.root.querySelector('.plan-click').setAttribute('aria-pressed', String(on));
    this.root.querySelectorAll('[data-act=pick]').forEach(b => b.setAttribute('aria-pressed', 'false'));
    this.host.picking && this.host.picking(on);
  },
  async appendPoint(lat, lng) {
    await Gaz.load().catch(() => {});
    const near = Gaz.nearest(lat, lng, 250), label = near ? T('Near {name}', { name: near.name }) : `${lat.toFixed(4)}, ${lng.toFixed(4)}`, pt = { lat, lng, label, sub: near && near.muni ? near.muni : T('Point on the map') };
    const empty = this.stops.findIndex(s => !s.pt);
    if (empty >= 0) { this.stops[empty].pt = pt; this.stops[empty].text = label; }
    else if (this.stops.length < 8) this.stops.push({ text: label, pt });
    else return;
    this.render(); this.stopsChanged(true);
  },
  /** A click on the map while choosing: fills the chosen row. */
  async mapPick(lat, lng) {
    let i = this.picking; if (i < 0) return false;
    const s = this.stops[i]; this.picking = -1; this.host.picking && this.host.picking(this.clickMode);
    await Gaz.load().catch(() => {});
    const near = Gaz.nearest(lat, lng, 250), label = near ? T('Near {name}', { name: near.name }) : `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    s.pt = { lat, lng, label, sub: near && near.muni ? near.muni : T('Point on the map') }; s.text = label;
    this.render(); this.stopsChanged(true);
    return true;
  },
  /** Drag of a marker on the map. */
  async movePoint(i, lat, lng) {
    const placed = this.stops.map((s, k) => s.pt ? k : -1).filter(k => k >= 0), si = placed[i];
    if (si == null) return;
    await Gaz.load().catch(() => {});
    const near = Gaz.nearest(lat, lng, 250), label = near ? T('Near {name}', { name: near.name }) : `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    this.stops[si].pt = { lat, lng, label, sub: near && near.muni ? near.muni : T('Point on the map') }; this.stops[si].text = label;
    this.render(); this.stopsChanged(true);
  },
  /** Plan button: resolves boxes that hold text but no chosen place to their best match, then routes. */
  async submit() {
    await Gaz.load().catch(() => {});
    const missing = [];
    for (let i = 0; i < this.stops.length; i++) {
      const s = this.stops[i]; if (s.pt || !s.text.trim()) continue;
      const rs = await searchEverything(s.text, { pointsOnly: true, bias: this.host.center && this.host.center() });
      if (rs[0]) { s.pt = { lat: rs[0].lat, lng: rs[0].lng, label: rs[0].label, sub: rs[0].sub || '' }; s.text = rs[0].label; } else missing.push(s.text);
    }
    this.render();
    if (missing.length) { this.root.querySelector('.plan-out').innerHTML = `<div class="note">${Th('No place found for {names}. Try another spelling, a street and municipality, or choose it on the map.', { names: missing.map(m => `“${m}”`).join(', ') })}</div>`; }
    if (this.placed().length >= 2) await this.compute(); else if (!missing.length) this.root.querySelector('.plan-out').innerHTML = `<div class="note">${esc(T('Enter a start and an end (and any stops between), or choose them on the map.'))}</div>`;
  },

  // -- routing and scoring --
  async compute() {
    const my = ++this.token, pts = this.placed(), out = this.root.querySelector('.plan-out');
    if (pts.length < 2) return;
    if (pts.every(p => p.lat === pts[0].lat && p.lng === pts[0].lng)) { out.innerHTML = `<div class="note">${esc(T('Those are all the same place. Choose a different end.'))}</div>`; return; }
    out.innerHTML = `<div class="note" role="status">${esc(T('Finding the route…'))}</div>`;
    let path, fallback = false;
    const ll = pts.map(p => [p.lng, p.lat]);
    if (this.follow) {
      try { const roads = await this.loadRoads(); path = roads.path(ll); } catch { fallback = true; }
    }
    if (!path) {
      const legs = ll.slice(1).map((b, i) => { const m = distM([ll[i][1], ll[i][0]], [b[1], b[0]]); return { ok: false, metres: m, secs: m / 8 }; });
      path = { coords: ll, metres: legs.reduce((a, l) => a + l.metres, 0), secs: legs.reduce((a, l) => a + l.secs, 0), legs, legAt: legs.map((_, i) => i), allOnRoads: false };
    }
    if (my !== this.token) return;
    this.result = { path, stops: pts, fallback, follow: this.follow, score: null };
    this.renderResult(); this.host.drawRoute(path.coords, pts); this.host.fit && this.host.fit(boundsOf(path.coords));
    try {
      const ctx = await this.host.data();
      if (my !== this.token) return;
      this.result.score = this.score(path.coords, pts, ctx);
    } catch { this.result.scoreError = true; }
    if (my === this.token) { this.renderResult(); this.host.resultReady && this.host.resultReady(this.result); }
  },
  segments(routes) {   // grid of the published (non-OSM) route segments, for "runs alongside an existing route"
    if (this.segFor === routes) return this.segIndex;
    const g = new Map(), C = .002, key = (x, y) => Math.floor((x + 70) / C) * 2048 + Math.floor((y - 17) / C);
    for (const f of routes.features) {
      const p = f.properties; if (p.operator === 'osm' || p.mode === 'ferry') continue;
      for (const ln of f.geometry.coordinates) for (let i = 1; i < ln.length; i++) {
        const a = ln[i - 1], b = ln[i], steps = Math.max(1, Math.min(60, Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])) / (C / 2)))), seg = [a[1], a[0], b[1], b[0]];
        let last = -1;
        for (let s = 0; s <= steps; s++) { const k = key(a[0] + (b[0] - a[0]) * s / steps, a[1] + (b[1] - a[1]) * s / steps); if (k !== last) { last = k; const arr = g.get(k); if (arr) arr.push(seg); else g.set(k, [seg]); } }
      }
    }
    this.segFor = routes; this.segIndex = g; return g;
  },
  score(coords, stops, ctx) {
    const full = coords.map(c => [c[1], c[0]]);   // [lat, lng]
    const pts = simplifyLine(full, 12), lenKm = lineKm(full);
    const step = lenKm > 100 ? 500 : lenKm > 30 ? 250 : 100, smp = samples(pts, step);
    const lat0 = Math.min(...pts.map(p => p[0])) - .0045, lat1 = Math.max(...pts.map(p => p[0])) + .0045, lng0 = Math.min(...pts.map(p => p[1])) - .006, lng1 = Math.max(...pts.map(p => p[1])) + .006;
    const closeTo = nearLine(pts), near = (lat, lng, d) => lat >= lat0 && lat <= lat1 && lng >= lng0 && lng <= lng1 && closeTo(lat, lng, d);
    let pop = 0, popNew = 0;
    if (ctx.blocks) for (const b of ctx.blocks) if (near(b[1], b[0], 400)) { pop += b[2]; if (b[3] > 400) popNew += b[2]; }
    let places = 0, lodging = 0;
    if (ctx.places) for (const p of ctx.places) { if (p.confidence < .5 || p.type === 'Places of Worship') continue; if (near(p.lat, p.lng, 400)) { places++; if (p.category === 'ACCOMMODATIONS') lodging++; } }
    const sched = (ctx.transport || []).filter(f => f.source === 'ati_gtfs' || f.source === 'muni_gtfs');
    const opName = Object.fromEntries((ctx.ops || []).map(o => [o.id, o.short || o.name])), nearOps = {};
    for (const f of sched) if (near(f.lat, f.lng, 250)) { const k = opName[f.operator] || f.operator_name || f.operator; nearOps[k] = (nearOps[k] || 0) + 1; }
    const ends = [stops[0], stops[stops.length - 1]].map(e => { let best = null; for (const f of sched) { const d = distM([e.lat, e.lng], [f.lat, f.lng]); if (d <= 300 && (!best || d < best.d)) best = { f, d }; } return best; });
    let par = 0;
    if (ctx.routes) { const g = this.segments(ctx.routes), C = .002; for (const sp of smp) { const cx = Math.floor((sp[1] + 70) / C), cy = Math.floor((sp[0] - 17) / C); let hit = false; for (let dx = -1; dx <= 1 && !hit; dx++) for (let dy = -1; dy <= 1 && !hit; dy++) { const a = g.get((cx + dx) * 2048 + cy + dy); if (a) for (const s of a) if (segDistM(sp, [s[0], s[1]], [s[2], s[3]]) <= 150) { hit = true; break; } } if (hit) par++; } }
    let flood = 0, prot = 0; const munis = new Set();
    for (const sp of smp) { const ll = { lat: sp[0], lng: sp[1] };
      if (ctx.flood && featuresAt(ctx.flood, ll, f => f.properties.SFHA_TF === 'T', 1).length) flood++;
      if (ctx.prot && featuresAt(ctx.prot, ll, () => true, 1).length) prot++;
      if (ctx.muniFc) { const m = featuresAt(ctx.muniFc, ll, () => true, 1)[0]; if (m) munis.add(m.properties.municipality); } }
    const pct = (n) => Math.round(n / smp.length * 100);
    // Existing service near the route (transit_supply.json, weekday timetable): only stops whose operator's timetable is current count as service.
    // A 0.005° grid (about 500 m) of those stops answers "is there one within 400 m?" for the route's samples and for the residents near it.
    let service = null;
    const W = ctx.supply && ctx.supply.days && ctx.supply.days.wk;
    if (W) {
      const cur = sched.filter(f => W.stops[f.id] && W.stops[f.id].cur), G = new Map(), C = .005;
      for (const f of cur) { const k = Math.floor(f.lat / C) * 100000 + Math.floor(f.lng / C); if (!G.has(k)) G.set(k, []); G.get(k).push(f); }
      const hasStop = (lat, lng) => { const cy = Math.floor(lat / C), cx = Math.floor(lng / C); for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const a = G.get((cy + dy) * 100000 + cx + dx); if (a) for (const f of a) if (distM([lat, lng], [f.lat, f.lng]) <= 400) return true; } return false; };
      const byKey = new Map(W.routes.map(r => [r.o + '|' + r.r, r])), keys = new Set(); let stopsNear = 0, peak = 0;
      for (const f of cur) if (near(f.lat, f.lng, 400)) { const st = W.stops[f.id]; stopsNear++; peak += st.hours[7]; st.routes.forEach(r => keys.add(f.operator + '|' + r)); }
      let gap = 0; for (const sp of smp) if (!hasStop(sp[0], sp[1])) gap++;
      let popNoCur = 0; if (ctx.blocks) for (const b of ctx.blocks) if (near(b[1], b[0], 400) && !hasStop(b[1], b[0])) popNoCur += b[2];
      const routes = [...keys].map(k => byKey.get(k)).filter(Boolean).sort((a, b) => b.trips - a.trips).map(r => ({ operator: opName[r.o] || r.o, route: r.r, trips: r.trips, peak_wait_min: r.peak_hw }));
      service = { stops: stopsNear, departures_7_to_8: peak, share_without_current_stop_pct: pct(gap), residents_without_current_stop: popNoCur, routes };
    }
    return { length_km: +lenKm.toFixed(2), residents_within_400m: pop, residents_not_served_today: service ? service.residents_without_current_stop : popNew, current_only: !!service, service, tourism_places_within_400m: ctx.places ? places : null, lodging_within_400m: ctx.places ? lodging : null, share_parallel_to_existing_routes_pct: pct(par), share_in_flood_hazard_area_pct: pct(flood), share_in_protected_areas_pct: pct(prot), municipalities: [...munis], ends, nearOps, haveBlocks: !!ctx.blocks, haveRoutes: !!ctx.routes };
  },

  // -- result card --
  renderResult() {
    const out = this.root.querySelector('.plan-out'), r = this.result;
    this.root.querySelector('.plan-actions .dl').disabled = !r;
    if (!r) { out.innerHTML = `<div class="note">${esc(T('Enter a start and an end, and any stops between, or choose them on the map. The route follows roads and is scored against the open data.'))}</div>`; return; }
    const { path, stops } = r, km = path.metres / 1000, mins = Math.max(1, Math.round(path.secs / 60));
    const lg = (i) => `${this.letter(stops[i].row)} → ${this.letter(stops[i + 1].row)}`;
    const bad = path.legs.map((l, i) => l.ok ? null : lg(i)).filter(Boolean);
    const legRows = path.legs.length > 1 ? `<div class="plan-legs">${path.legs.map((l, i) => `<div>${Th('<b>{leg}</b> {from} to {to} <span>{detail}</span>', { leg: lg(i), from: stops[i].label, to: stops[i + 1].label, detail: `${fmt(l.metres / 1000, 1)} km${l.ok ? `, ${fmt(Math.max(1, Math.round(l.secs / 60)))} min` : ''}` })}</div>`).join('')}</div>` : '';
    let html = `<div class="kpis"><div class="kpi"><div class="v">${fmt(km, 1)} km</div><div class="l">${esc(r.follow && path.allOnRoads ? T('by road') : r.follow ? T('partly by road') : T('straight line'))}</div></div>
      <div class="kpi"><div class="v">${r.follow && path.legs.some(l => l.ok) ? '~' + fmt(mins) + ' min' : '—'}</div><div class="l">${esc(T('at bus planning speeds, without stops or traffic'))}</div></div></div>${legRows}${this.host.extraButtons ? this.host.extraButtons() : ''}`;
    if (r.fallback) html += `<div class="note">${esc(T('The road data could not be loaded, so the route is drawn as straight lines. Check your connection and plan again.'))}</div>`;
    else if (bad.length) html += `<div class="note">${esc(Tn(bad.length, '{legs} cannot follow roads (no connected road within 500 m of an end, for example between islands, so a ferry or flight would be needed). It is drawn as a straight line and left out of the time.', '{legs} cannot follow roads (no connected road within 500 m of an end, for example between islands, so a ferry or flight would be needed). They are drawn as straight lines and left out of the time.', { legs: bad.join(', ') }))}</div>`;
    const s = r.score;
    if (s) {
      const pc = (n) => `${n}%`;
      const lodging = s.lodging_within_400m == null ? '' : Tn(s.lodging_within_400m, '{n} lodging', '{n} lodgings', { n: fmt(s.lodging_within_400m) });
      const near = Object.entries(s.nearOps).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${k} (${fmt(n)})`).join(', ');
      html += `<div class="kpis">
        <div class="kpi green"><div class="v">${fmt(s.residents_within_400m)}</div><div class="l">${esc(Tn(s.residents_within_400m, 'resident within 400 m of the route', 'residents within 400 m of the route'))}</div></div>
        <div class="kpi"><div class="v">${fmt(s.residents_not_served_today)}</div><div class="l">${esc(s.current_only ? Tn(s.residents_not_served_today, 'of them has no stop with a current timetable within 400 m', 'of them have no stop with a current timetable within 400 m') : Tn(s.residents_not_served_today, 'of them has no scheduled stop within 400 m today', 'of them have no scheduled stop within 400 m today'))}</div></div>
        ${s.tourism_places_within_400m == null ? `<div class="kpi"><div class="v">—</div><div class="l">${esc(T('tourism places within 400 m: not counted. Switch on the tourism places in Explore › Map layers, then plan again'))}</div></div>` : `<div class="kpi"><div class="v">${fmt(s.tourism_places_within_400m)}</div><div class="l">${esc(Tn(s.tourism_places_within_400m, 'tourism place within 400 m ({lodging})', 'tourism places within 400 m ({lodging})', { lodging }))}</div></div>`}
        <div class="kpi ${s.share_parallel_to_existing_routes_pct > 50 ? 'warn' : ''}"><div class="v">${pc(s.share_parallel_to_existing_routes_pct)}</div><div class="l">${esc(T('of the length runs within 150 m of an existing route'))}</div></div>
        <div class="kpi ${s.share_in_flood_hazard_area_pct > 20 ? 'warn' : ''}"><div class="v">${pc(s.share_in_flood_hazard_area_pct)}</div><div class="l">${esc(T('in a flood hazard area'))}${s.share_in_protected_areas_pct ? ` · ${esc(T('{pct} in protected areas', { pct: pc(s.share_in_protected_areas_pct) }))}` : ''}</div></div>
        <div class="kpi"><div class="v">${fmt(s.municipalities.length)}</div><div class="l">${s.municipalities.length ? esc(s.municipalities.slice(0, 4).join(', ')) + (s.municipalities.length > 4 ? ` ${esc(T('and {n} more', { n: fmt(s.municipalities.length - 4) }))}` : '') : esc(T('municipalities'))}</div></div></div>
        ${s.service ? this.serviceHtml(s.service) : ''}
        <div class="note">${Th('<b>Connections.</b> {start}<br>{end}<br>{ops}', { start: endTxt(s.ends[0], 'Start'), end: endTxt(s.ends[1], 'End'), ops: near ? T('Existing stops within 250 m of the route: {ops}.', { ops: near }) : T('Existing stops within 250 m of the route: none.') })}</div>
        <div class="note">${esc(T('Straight-line distances to the route, 2020 Census blocks, current schedules. A planning aid, not an engineering or demand forecast.'))}</div>
        ${s.tourism_places_within_400m == null ? '' : `<div class="note">${esc(T('Holiday rentals and rented units named by an address are counted by municipio, not drawn, so they are not in the tourism places count.'))}</div>`}`;
    } else if (r.scoreError) html += `<div class="note">${esc(T('The coverage figures could not be loaded. The route is still drawn.'))}</div>`;
    else html += `<div class="note" role="status">${esc(T('Measuring who and what it reaches…'))}</div>`;
    out.innerHTML = html;
  },
  serviceHtml(v) {
    const list = v.routes.slice(0, 8).map(r => `<li>${esc(T('{operator} route {route}', { operator: r.operator, route: r.route }))} <small>· ${esc(Tn(r.trips, '{n} weekday trip', '{n} weekday trips', { n: fmt(r.trips) }))}${r.peak_wait_min ? ` · ${esc(T('every {n} min at the morning peak', { n: fmt(r.peak_wait_min) }))}` : ''}</small></li>`).join('');
    return `<h3 class="plan-sub">${esc(T('Existing service near this route'))}</h3><div class="kpis">
      <div class="kpi"><div class="v">${fmt(v.stops)}</div><div class="l">${esc(Tn(v.stops, 'stop with a current timetable within 400 m', 'stops with a current timetable within 400 m'))}</div></div>
      <div class="kpi"><div class="v">${fmt(v.departures_7_to_8)}</div><div class="l">${esc(T('departures from those stops between 7:00 and 8:00 on a weekday'))}</div></div>
      <div class="kpi ${v.share_without_current_stop_pct > 50 ? 'warn' : ''}"><div class="v">${v.share_without_current_stop_pct}%</div><div class="l">${esc(T('of the length has no stop with a current timetable within 400 m'))}</div></div>
      <div class="kpi"><div class="v">${fmt(v.routes.length)}</div><div class="l">${esc(Tn(v.routes.length, 'route stops within 400 m', 'routes stop within 400 m'))}</div></div></div>
      ${list ? `<div class="note"><b>${esc(T('Routes that stop near it, busiest first'))}</b><ul class="plain-list">${list}</ul>${v.routes.length > 8 ? esc(T('and {n} more', { n: fmt(v.routes.length - 8) })) : ''}</div>` : ''}`;
  },
  geojson() {
    const r = this.result; if (!r) return null;
    const s = r.score || {};
    return { type: 'FeatureCollection', features: [
      { type: 'Feature', properties: { name: 'Planned route', created: new Date().toISOString().slice(0, 10), source: 'PR Data Observatory route planner', follows_roads: r.follow && r.path.allOnRoads, length_km: +(r.path.metres / 1000).toFixed(2), stops: r.stops.map(p => p.label).join(' > '), residents_within_400m: s.residents_within_400m, tourism_places_within_400m: s.tourism_places_within_400m, share_parallel_to_existing_routes_pct: s.share_parallel_to_existing_routes_pct, share_in_flood_hazard_area_pct: s.share_in_flood_hazard_area_pct, municipalities: (s.municipalities || []).join(', '),
        ...(s.service ? { current_stops_within_400m: s.service.stops, weekday_departures_7_to_8: s.service.departures_7_to_8, share_without_current_stop_pct: s.service.share_without_current_stop_pct, residents_without_current_stop: s.service.residents_without_current_stop, routes_nearby: s.service.routes.map(x => `${x.operator} ${x.route}`).join(', ') } : {}) }, geometry: { type: 'LineString', coordinates: r.path.coords } },
      ...r.stops.map((p, i) => ({ type: 'Feature', properties: { name: p.label, order: i + 1, role: i === 0 ? 'from' : i === r.stops.length - 1 ? 'to' : 'stop' }, geometry: { type: 'Point', coordinates: [+p.lng.toFixed(6), +p.lat.toFixed(6)] } })),
    ] };
  },
  download() {
    const gj = this.geojson(); if (!gj) return;
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(gj, null, 1)], { type: 'application/geo+json' })); a.download = 'planned_route.geojson'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  },
  draw() { /* the map is redrawn by host.drawRoute once there is a route; this keeps the stops visible before that */ this.host && this.host.drawRoute(this.result && this.result.path.coords, this.placed(), true); },
};
function endTxt(e, label) {   // plain text; label is 'Start' or 'End' (an identifier here, not shown as is)
  const v = e ? { name: e.f.name || T('stop'), operator: e.f.operator_name || '', d: fmt(Math.round(e.d)) } : null;
  if (label === 'Start') return e ? T('Start: {name} · {operator} ({d} m)', v) : T('Start: no scheduled stop within 300 m');
  return e ? T('End: {name} · {operator} ({d} m)', v) : T('End: no scheduled stop within 300 m');
}

/** The planner's markup; both pages place it inside a tab. Wires the buttons to Plan. */
function planMarkup() {
  return `<div class="plan-rows"></div>
    <div class="btn-row plan-actions"><button type="button" class="btn plan-add">${icon('add', { size: 16 })}${esc(T('Add a stop'))}</button><button type="button" class="btn plan-swap">${icon('swap_vert', { size: 16 })}${esc(T('Reverse'))}</button></div>
    <label class="toggle"><input type="checkbox" class="plan-follow" checked> ${esc(T('Follow roads'))}</label>
    <div class="btn-row"><button type="button" class="btn plan-click" aria-pressed="false">${icon('place', { size: 16 })}${esc(T('Add points by clicking the map'))}</button></div>
    <div class="btn-row plan-actions"><button type="button" class="btn primary plan-go">${esc(T('Plan route'))}</button><button type="button" class="btn plan-clear">${esc(T('Clear'))}</button><button type="button" class="btn dl" disabled>${icon('download', { size: 16 })}GeoJSON</button></div>
    <div class="plan-out" aria-live="polite"></div>`;
}
function planWire(root) {
  root.querySelector('.plan-add').onclick = () => Plan.addStop();
  root.querySelector('.plan-swap').onclick = () => Plan.swap();
  root.querySelector('.plan-go').onclick = () => Plan.submit();
  root.querySelector('.plan-clear').onclick = () => Plan.clear();
  root.querySelector('.plan-click').onclick = () => Plan.setClickMode(!Plan.clickMode);
  root.querySelector('.dl').onclick = () => Plan.download();
  root.querySelector('.plan-follow').onchange = e => { Plan.follow = e.target.checked; if (Plan.placed().length >= 2) Plan.compute(); };
  root.querySelector('.plan-rows').addEventListener('click', e => {
    const b = e.target.closest('button[data-act]'); if (!b) return; const i = +b.closest('.plan-row').dataset.i;
    ({ pick: () => Plan.startPick(i), up: () => Plan.move(i, -1), down: () => Plan.move(i, 1), del: () => Plan.remove(i) })[b.dataset.act]();
  });
}
